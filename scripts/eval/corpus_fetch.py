"""Corpus v0 fetch: search, rights check, download and manifest rows (plan D3a, section 8).

Sources are an allowlist: the Met collection API (search v1.1, object records v1), Smithsonian
Open Access, the Art Institute of Chicago and hand-picked LACMA images; any other host is
refused. Each object needs its institution's own rights flag (data-56), and an object made in
1930 or later is skipped before its image is fetched, so no modern designer quilt reaches the
cache (data-55). Requests go out at most one per second across all hosts, which also keeps AIC
under its 60 per minute, with a User-Agent that carries no personal contact details.

The Smithsonian API runs on api.data.gov. Without a key it uses DEMO_KEY, whose limits are 30
requests per hour and 50 per day per IP (api.data.gov developer manual), and api.si.edu reported
X-Ratelimit-Limit 10 on 2026-10-10; one search with rows up to 1000 returns every CC0 quilt
record, so a fetch or a recheck spends one request. Image downloads from ids.si.edu carry no key.

Usage (cache defaults to the main checkout's corpus/private/cache/):
    python scripts/eval/corpus_fetch.py search [--source met|aic|smithsonian]
    python scripts/eval/corpus_fetch.py download [--source ...]
    python scripts/eval/corpus_fetch.py rows SCREEN_CSV
    python scripts/eval/corpus_fetch.py verify
    python scripts/eval/corpus_fetch.py attribution
    python scripts/eval/corpus_fetch.py --recheck
"""

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "corpus" / "manifest.csv"
ATTRIBUTION = REPO / "corpus" / "ATTRIBUTION.md"
# Fetches land in the main checkout's ignored corpus/private/cache/ (WORKER.md R1, its
# private-data exception), so every worktree reads one copy and no fetched image can be staged.
DEFAULT_CACHE = Path("C:/Users/Jake Mismas/QREP/corpus/private/cache")

COLUMNS = (
    "file", "license", "source", "object_id", "title", "landing_url", "image_url",
    "rights_flag", "policy_url", "credit", "dimensions_text", "finished_in", "sha256",
    "file_sha256", "px_w", "px_h", "tier", "class", "capture", "commit_ok",
)
TIERS = ("A", "B", "R", "X")
IN_SCOPE = ("squares", "hst", "qst", "snowball", "flying_geese")
REFUSALS = ("on_point", "curve", "applique", "medallion", "hexagon", "diamond_star", "other")
# Why a tier X photo is excluded from every eval set.
EXCLUSIONS = ("partial_view", "duplicate", "not_a_quilt", "unreadable")
CLASSES_BY_TIER = {"A": IN_SCOPE, "B": IN_SCOPE, "R": REFUSALS, "X": EXCLUSIONS}

# A plain User-Agent with no personal contact details (plan D3a, criterion 1).
USER_AGENT = "QREP-corpus/0.4 (+https://github.com/jakemismas/QREP)"
MIN_INTERVAL_S = 1.0

# The open-access allowlist (plan D3a, criterion 1). V&A, Quilt Index, the International Quilt
# Museum, the Library of Congress, Mia and Wikimedia Commons are absent on purpose
# (corpus/README.md says why).
ALLOWED_HOSTS = frozenset({
    "collectionapi.metmuseum.org", "images.metmuseum.org", "www.metmuseum.org",
    "api.si.edu", "ids.si.edu", "collections.si.edu", "www.si.edu",
    "api.artic.edu", "www.artic.edu",
    "collections.lacma.org", "collections-images.lacma.org", "www.lacma.org",
    # Cooper Hewitt is a Smithsonian museum whose record pages live on its own domain.
    "collection.cooperhewitt.org",
})
# Smithsonian museums publish record pages on their own si.edu subdomains (americanart,
# nmaahc, postalmuseum and others); the leading dot keeps a look-alike domain out.
ALLOWED_SUFFIXES = (".si.edu",)
# Objects made in this year or later may be modern designer quilts, whose layout and colors
# Boisson v. Banian protects (data-55); a photo's rights flag clears the photo, not the design.
MODERN_FROM = 1930
SI_DEMO_KEY = "DEMO_KEY"


class HostRefused(ValueError):
    """A URL off the allowlist, or not https."""


class NotCleared(ValueError):
    """A record whose per-object rights flag does not clear its image."""


@dataclass(frozen=True)
class Source:
    name: str
    institution: str
    license: str
    rights_flag: str
    policy_url: str


SOURCES: dict[str, Source] = {
    "met": Source(
        "met", "The Metropolitan Museum of Art", "CC0-1.0", "isPublicDomain=true",
        "https://www.metmuseum.org/about-the-met/policies-and-documents/image-resources",
    ),
    "smithsonian": Source(
        "smithsonian", "Smithsonian Institution", "CC0-1.0", "media.usage.access=CC0",
        "https://www.si.edu/openaccess",
    ),
    "aic": Source(
        "aic", "Art Institute of Chicago", "PDM-1.0", "is_public_domain=true",
        "https://www.artic.edu/image-licensing",
    ),
    "lacma": Source(
        "lacma", "Los Angeles County Museum of Art", "PDM-1.0", "publicDomain=1",
        "https://www.lacma.org/about/contact-us/terms-use",
    ),
}
# LACMA asks that a public-domain image's citation include the URL www.lacma.org.
LACMA_CITATION = "Image courtesy of the Los Angeles County Museum of Art, www.lacma.org"


@dataclass
class Candidate:
    """One object that cleared its rights flag, before and after its image is fetched."""

    source: str
    object_id: str
    title: str
    landing_url: str
    image_url: str
    credit: str
    dimensions_text: str
    date_end: int | None
    sha256: str = ""
    px_w: int = 0
    px_h: int = 0

    @property
    def cache_file(self) -> str:
        return cache_name(self.source, self.object_id)

    def modern(self) -> bool:
        return self.date_end is not None and self.date_end >= MODERN_FROM


def _years(text: str) -> list[int]:
    # Digit guards rather than word boundaries, so a decade such as 1850s still reads 1850.
    return [int(y) for y in re.findall(r"(?<!\d)(1[5-9]\d\d|20\d\d)(?!\d)", text)]


def met_candidate(record: dict) -> Candidate:
    """A Met object record (v1 objects endpoint); isPublicDomain must be true."""
    if record.get("isPublicDomain") is not True:
        raise NotCleared(f"met {record.get('objectID')}: isPublicDomain is not true")
    if not record.get("primaryImage"):
        raise NotCleared(f"met {record.get('objectID')}: no primary image")
    end = record.get("objectEndDate")
    return Candidate(
        "met", str(record["objectID"]), clean_text(record.get("title") or ""),
        record.get("objectURL") or "", record["primaryImage"],
        clean_text(record.get("creditLine") or ""), clean_text(record.get("dimensions") or ""),
        end if isinstance(end, int) else None,
    )


AIC_IIIF = "https://www.artic.edu/iiif/2"
# AIC documents 843 px wide as its standard size and 1686 px for public-domain works.
AIC_WIDTH = 1686


def aic_candidate(record: dict) -> Candidate:
    """An AIC artwork from the search API; is_public_domain must be true."""
    if record.get("is_public_domain") is not True:
        raise NotCleared(f"aic {record.get('id')}: is_public_domain is not true")
    if not record.get("image_id"):
        raise NotCleared(f"aic {record.get('id')}: no image")
    end = record.get("date_end")
    return Candidate(
        "aic", str(record["id"]), clean_text(record.get("title") or ""),
        f"https://www.artic.edu/artworks/{record['id']}",
        f"{AIC_IIIF}/{record['image_id']}/full/{AIC_WIDTH},/0/default.jpg",
        clean_text(record.get("credit_line") or ""), clean_text(record.get("dimensions") or ""),
        end if isinstance(end, int) else None,
    )


# LACMA is hand-picked (plan D3a, criterion 1): a screened sample of its public-domain quilt
# search on 2026-10-10 (POST /api/search, query quilt, publicDomain true: 115 results), whose
# object pages each carry "publicDomain":1. The site's download dialog offers images only for
# objects flagged 1; restricted objects carry 0.
LACMA_PICKS = (
    "2048", "30012", "33726", "44818", "44868", "52521", "52522", "54813", "54852", "54853",
    "54871", "54874", "54876", "54904", "54905", "56077", "58735", "59557", "60126", "60154",
    "61555", "61642", "63229", "63255", "63267",
)
_LD_JSON = re.compile(r'<script type="application/ld\+json">(\{.*?\})</script>', re.DOTALL)
_PUBLIC_DOMAIN = re.compile(r'\\?"publicDomain\\?":\s*(\d+)')
_DESKTOP = re.compile(r"https://collections-images\.lacma\.org/images/(\d+)/\1-1-desktop\.jpg")


def lacma_candidate(record: dict) -> Candidate:
    """A LACMA object page ({"object_id", "html"}); every publicDomain flag on it must be 1."""
    object_id, html = record["object_id"], record["html"]
    flags = _PUBLIC_DOMAIN.findall(html)
    if not flags or any(flag != "1" for flag in flags):
        raise NotCleared(f"lacma {object_id}: publicDomain is not 1 on every image")
    image = _DESKTOP.search(html)
    found = _LD_JSON.search(html)
    if image is None or found is None:
        raise NotCleared(f"lacma {object_id}: no desktop image or no object data")
    data = json.loads(found.group(1))
    years = _years(data.get("dateCreated") or "")
    return Candidate(
        "lacma", object_id, clean_text(data.get("name") or ""),
        f"https://collections.lacma.org/object/{object_id}", image.group(0),
        clean_text(data.get("creditText") or ""), clean_text(data.get("size") or ""),
        max(years) if years else None,
    )


def _texts(entries) -> list[str]:
    if isinstance(entries, str):
        return [entries]
    return [e.get("content", "") for e in entries or [] if isinstance(e, dict)]


def si_candidate(row: dict) -> Candidate:
    """A Smithsonian Open Access search row; one image medium must be usage CC0."""
    content = row.get("content") or {}
    nonrep = content.get("descriptiveNonRepeating") or {}
    record_id = nonrep.get("record_ID") or row.get("id") or ""
    media = (nonrep.get("online_media") or {}).get("media") or []
    cleared = [
        m for m in media
        if (m.get("usage") or {}).get("access") == "CC0" and m.get("type") == "Images"
    ]
    if not cleared:
        raise NotCleared(f"smithsonian {record_id}: no CC0 image")
    medium = cleared[0]
    full = [r.get("url") for r in medium.get("resources") or []
            if r.get("label") == "High-resolution JPEG" and r.get("url")]
    freetext = content.get("freetext") or {}
    dims = [e.get("content", "") for e in freetext.get("physicalDescription") or []
            if e.get("label") == "Dimensions"]
    years = [y for text in _texts(freetext.get("date")) for y in _years(text)]
    link = nonrep.get("record_link") or ""
    if not link.startswith("https://"):
        link = f"https://collections.si.edu/search/detail/{row.get('id') or record_id}"
    return Candidate(
        "smithsonian", record_id, clean_text((nonrep.get("title") or {}).get("content", "")),
        link, full[0] if full else medium.get("content", ""),
        clean_text("; ".join(_texts(freetext.get("creditLine")))),
        clean_text("; ".join(dims)), max(years) if years else None,
    )


def check_host(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    if parts.scheme != "https" or not (host in ALLOWED_HOSTS or host.endswith(ALLOWED_SUFFIXES)):
        raise HostRefused(f"refusing {url!r}: only https on {sorted(ALLOWED_HOSTS)}")
    return url


class RateLimiter:
    """At most one request per interval, across every host (plan section 8.3)."""

    def __init__(
        self,
        interval_s: float = MIN_INTERVAL_S,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.interval_s, self.clock, self.sleep = interval_s, clock, sleep
        self.last: float | None = None

    def wait(self) -> None:
        if self.last is not None:
            remaining = self.interval_s - (self.clock() - self.last)
            if remaining > 0:
                self.sleep(remaining)
        self.last = self.clock()


# ---------------------------------------------------------------------------------------------
# Finished sizes
# ---------------------------------------------------------------------------------------------

_NUM = r"\d+(?:\.\d+)?(?:\s+\d+/\d+)?|\d+/\d+"
# A pair, or a triple whose third number (the depth) is dropped, then its unit.
_PAIR = re.compile(
    rf"(?:\b(?P<l1>[HW])(?:\.|eight|idth)?\s*)?(?P<a>{_NUM})\s*(?:in\.?|inches|cm)?\s*x\s*"
    rf"(?:\b(?P<l2>[HW])(?:\.|eight|idth)?\s*)?(?P<b>{_NUM})\s*(?:in\.?|inches|cm)?"
    rf"(?:\s*x\s*(?:\bD\.?\s*)?(?:{_NUM}))?\s*(?P<unit>in\b\.?|inches|cm\b)",
    re.IGNORECASE,
)


def _number(text: str) -> float:
    whole, _, fraction = text.strip().partition(" ")
    if "/" in whole:
        whole, fraction = "0", whole
    value = float(whole)
    if fraction:
        top, bottom = fraction.split("/")
        value += int(top) / int(bottom)
    return value


def parse_finished_size(text: str) -> tuple[float, float] | None:
    """(width, height) in inches from a museum dimensions text, or None.

    Inches win over centimetres. An unlabeled pair reads height x width, the
    museum convention for flat textiles; H. and W. labels win over order. The
    result is approximate: a museum measures the object, not the pattern."""
    normalized = text.replace("\u00d7", "x").replace("\u00a0", " ")
    pairs = list(_PAIR.finditer(normalized))
    chosen = next((m for m in pairs if not m["unit"].lower().startswith("cm")), None)
    chosen = chosen or (pairs[0] if pairs else None)
    if chosen is None:
        return None
    scale = 1 / 2.54 if chosen["unit"].lower().startswith("cm") else 1.0
    a, b = (round(_number(chosen[k]) * scale, 2) for k in ("a", "b"))
    labels = ((chosen["l1"] or "").upper(), (chosen["l2"] or "").upper())
    if labels == ("W", "H"):
        return (a, b)
    return (b, a)


def format_finished(width: float, height: float) -> str:
    return f"~{round(width, 2):g} x {round(height, 2):g}"


# ---------------------------------------------------------------------------------------------
# Manifest and attribution
# ---------------------------------------------------------------------------------------------


def cache_name(source: str, object_id: str, ext: str = "jpg") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", object_id.lower()).strip("-")
    return f"{source}-{slug}.{ext}"


def clean_text(text: str) -> str:
    # House text rule (WORKER.md R15): no en or em dashes in committed text, museum text
    # included, so ranges such as 1840-1850 keep a plain hyphen.
    return " ".join(text.replace("\u2013", "-").replace("\u2014", "-").split())


def read_manifest(path: Path = MANIFEST) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def manifest_text(rows: Iterable[dict[str, str]]) -> str:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in sorted(rows, key=lambda r: (r["source"], r["object_id"])):
        writer.writerow({column: row.get(column, "") for column in COLUMNS})
    return out.getvalue()


def write_manifest(rows: Iterable[dict[str, str]], path: Path = MANIFEST) -> None:
    path.write_text(manifest_text(rows), encoding="utf-8", newline="")


def attribution_markdown(rows: Iterable[dict[str, str]]) -> str:
    """corpus/ATTRIBUTION.md, generated from the manifest."""
    rows = sorted(rows, key=lambda r: (r["source"], r["object_id"]))
    lines = [
        "# Corpus attribution",
        "",
        "Generated from corpus/manifest.csv by `python scripts/eval/corpus_fetch.py attribution`;",
        "edit the manifest, then regenerate. Each image below is dedicated CC0 by its institution",
        "or marked public domain by it, per its own per-object rights flag. QREP credits every",
        "institution, and cites LACMA as LACMA asks.",
    ]
    for name, source in SOURCES.items():
        mine = [r for r in rows if r["source"] == name]
        if not mine:
            continue
        lines += ["", f"## {source.institution} ({source.license})", "",
                  f"Rights: `{source.rights_flag}` on every object; policy: {source.policy_url}"]
        if name == "lacma":
            lines += ["", f"Citation: {LACMA_CITATION}."]
        lines.append("")
        for r in mine:
            where = f", committed as corpus/{r['file']}" if r["file"].startswith("images/") else ""
            lines.append(
                f"- {r['title']} ({r['object_id']}). {r['credit']}. {r['landing_url']}{where}"
            )
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------------------------

MET = "https://collectionapi.metmuseum.org/public/collection"
AIC_API = "https://api.artic.edu/api/v1"
AIC_FIELDS = "id,title,is_public_domain,image_id,date_end,dimensions,credit_line"
SI_API = "https://api.si.edu/openaccess/api/v1.0"
SI_QUERY = "quilt AND online_media_type:Images AND media_usage:CC0"


class _AllowlistRedirects(urllib.request.HTTPRedirectHandler):
    # A redirect is a new request: it must land on the allowlist too.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_host(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    """Every request: allowlisted host, rate limit, plain User-Agent, counted per host."""

    def __init__(self, limiter: RateLimiter | None = None):
        self.limiter = limiter or RateLimiter()
        self.opener = urllib.request.build_opener(_AllowlistRedirects)
        self.requests: dict[str, int] = {}

    def get(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        check_host(url)
        self.limiter.wait()
        host = urllib.parse.urlsplit(url).hostname or ""
        self.requests[host] = self.requests.get(host, 0) + 1
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
        with self.opener.open(request, timeout=180) as response:
            return response.read()

    def json(self, url: str, headers: dict[str, str] | None = None) -> dict:
        return json.loads(self.get(url, headers))


def _cached_json(path: Path, fetch: Callable[[], dict], refresh: bool = False) -> dict:
    if path.exists() and not refresh:
        return json.loads(path.read_text(encoding="utf-8"))
    data = fetch()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return data


def _query(params: dict[str, str]) -> str:
    return urllib.parse.urlencode(params, quote_via=urllib.parse.quote)


def met_records(client: Client, cache: Path, refresh: bool = False) -> list[dict]:
    """Every Met object whose title matches quilt and that has images (v1.1 search)."""
    ids: list[int] = []
    offset = 0
    while True:
        url = f"{MET}/v1.1/search?" + _query(
            {"q": "quilt", "title": "true", "hasImages": "true", "limit": "500",
             "offset": str(offset)})
        page = _cached_json(cache / "raw" / f"met-search-{offset}.json",
                            lambda u=url: client.json(u), refresh)
        ids += page.get("objectIDs") or []
        offset += 500
        if offset >= (page.get("total") or 0):
            break
    return [
        _cached_json(cache / "raw" / "met" / f"{oid}.json",
                     lambda oid=oid: client.json(f"{MET}/v1/objects/{oid}"), refresh)
        for oid in dict.fromkeys(ids)
    ]


def aic_records(client: Client, cache: Path, refresh: bool = False) -> list[dict]:
    """Every AIC artwork titled quilt and flagged public domain (q ranks, so filter in query)."""
    records: list[dict] = []
    page = 1
    while True:
        url = f"{AIC_API}/artworks/search?" + _query({
            "query[bool][must][0][match][title]": "quilt",
            "query[bool][must][1][term][is_public_domain]": "true",
            "fields": AIC_FIELDS, "limit": "100", "page": str(page)})
        data = _cached_json(cache / "raw" / f"aic-search-{page}.json",
                            lambda u=url: client.json(u, {"AIC-User-Agent": USER_AGENT}), refresh)
        records += data.get("data") or []
        if page >= ((data.get("pagination") or {}).get("total_pages") or 0):
            break
        page += 1
    return records


def si_rows(client: Client, cache: Path, refresh: bool = False) -> list[dict]:
    """Every CC0 Smithsonian image record matching quilt: one DEMO_KEY request."""
    url = f"{SI_API}/search?" + _query(
        {"q": SI_QUERY, "rows": "1000", "start": "0", "api_key": SI_DEMO_KEY})
    data = _cached_json(cache / "raw" / "si-search.json", lambda: client.json(url), refresh)
    return (data.get("response") or {}).get("rows") or []


def lacma_records(client: Client, cache: Path, refresh: bool = False) -> list[dict]:
    """The hand-picked LACMA object pages."""
    records = []
    for object_id in LACMA_PICKS:
        path = cache / "raw" / "lacma" / f"{object_id}.html"
        if refresh or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            page = client.get(f"https://collections.lacma.org/object/{object_id}")
            path.write_text(page.decode("utf-8"), encoding="utf-8")
        records.append({"object_id": object_id, "html": path.read_text(encoding="utf-8")})
    return records


PARSERS: dict[str, Callable[[dict], Candidate]] = {
    "met": met_candidate, "aic": aic_candidate, "smithsonian": si_candidate,
    "lacma": lacma_candidate,
}
FETCHERS = {"met": met_records, "aic": aic_records, "smithsonian": si_rows,
            "lacma": lacma_records}


def names_a_quilt(source: str, record: dict, candidate: Candidate) -> bool:
    """Title first; Smithsonian also by object type, because many of its quilts carry only a
    pattern name (Double Irish Chain, Log Cabin) as their title."""
    if "quilt" in candidate.title.lower():
        return True
    if source != "smithsonian":
        return False
    types = ((record.get("content") or {}).get("indexedStructured") or {}).get("object_type")
    return any("quilt" in str(t).lower() for t in types or [])


def screen_records(source: str, records: list[dict]) -> tuple[list[Candidate], dict[str, int]]:
    """Candidates whose flag clears, titled quilt, made before MODERN_FROM; skips by reason."""
    kept, skipped = [], {}
    for record in records:
        try:
            candidate = PARSERS[source](record)
        except NotCleared as err:
            reason = str(err).split(": ", 1)[1]
            skipped[reason] = skipped.get(reason, 0) + 1
            continue
        if not names_a_quilt(source, record, candidate):
            skipped["title does not name a quilt"] = skipped.get("title does not name a quilt", 0) + 1
        elif candidate.modern():
            skipped[f"made {MODERN_FROM} or later"] = skipped.get(f"made {MODERN_FROM} or later", 0) + 1
        else:
            kept.append(candidate)
    return kept, skipped


def _candidates_path(cache: Path) -> Path:
    return cache / "candidates.json"


def load_candidates(cache: Path) -> list[Candidate]:
    path = _candidates_path(cache)
    if not path.exists():
        return []
    return [Candidate(**c) for c in json.loads(path.read_text(encoding="utf-8"))]


def save_candidates(cache: Path, candidates: list[Candidate]) -> None:
    ordered = sorted(candidates, key=lambda c: (c.source, c.object_id))
    _candidates_path(cache).write_text(
        json.dumps([c.__dict__ for c in ordered], indent=1), encoding="utf-8")


def search(client: Client, cache: Path, sources: list[str], refresh: bool) -> dict:
    found = {c.cache_file: c for c in load_candidates(cache) if c.source not in sources}
    report = {}
    for source in sources:
        records = FETCHERS[source](client, cache, refresh)
        kept, skipped = screen_records(source, records)
        old = {c.cache_file: c for c in load_candidates(cache) if c.source == source}
        for c in kept:
            if c.cache_file in old:
                c.sha256, c.px_w, c.px_h = old[c.cache_file].sha256, old[c.cache_file].px_w, \
                    old[c.cache_file].px_h
            found[c.cache_file] = c
        report[source] = {"records": len(records), "kept": len(kept), "skipped": skipped}
    save_candidates(cache, list(found.values()))
    return report


def _image_facts(path: Path) -> tuple[str, int, int]:
    from PIL import Image

    data = path.read_bytes()
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
    return hashlib.sha256(data).hexdigest(), width, height


def download(client: Client, cache: Path, sources: list[str]) -> dict:
    """Fetch each candidate's image once; verify a cached one against its recorded sha256."""
    candidates = load_candidates(cache)
    failed = {}
    for c in candidates:
        if c.source not in sources:
            continue
        path = cache / c.cache_file
        try:
            if not path.exists():
                data = client.get(c.image_url)
                path.write_bytes(data)
            sha, width, height = _image_facts(path)
        except Exception as err:  # noqa: BLE001 - one bad image must not stop the run
            failed[c.cache_file] = f"{type(err).__name__}: {err}"
            continue
        if c.sha256 and c.sha256 != sha:
            raise SystemExit(f"{c.cache_file}: cached bytes hash {sha}, recorded {c.sha256}")
        c.sha256, c.px_w, c.px_h = sha, width, height
        save_candidates(cache, candidates)
    return {"fetched": sum(1 for c in candidates if c.sha256), "failed": failed}


# ---------------------------------------------------------------------------------------------
# Rows, verification and the recheck
# ---------------------------------------------------------------------------------------------


def build_rows(cache: Path, screen_csv: Path, committed: dict[str, tuple[str, str]]) -> list[dict]:
    """Manifest rows for every screened candidate.

    screen_csv columns: stem, tier, class, commit_ok. committed maps a cache file to the
    committed copy's corpus-relative path and its own sha256."""
    by_stem = {Path(c.cache_file).stem: c for c in load_candidates(cache) if c.sha256}
    with screen_csv.open(encoding="utf-8", newline="") as handle:
        decisions = list(csv.DictReader(handle))
    out = []
    for d in decisions:
        c = by_stem[d["stem"]]
        source = SOURCES[c.source]
        parsed = parse_finished_size(c.dimensions_text) if c.dimensions_text else None
        file, file_sha = committed.get(c.cache_file, ("private/cache/" + c.cache_file, ""))
        out.append({
            "file": file, "license": source.license, "source": c.source,
            "object_id": c.object_id, "title": c.title, "landing_url": c.landing_url,
            "image_url": c.image_url, "rights_flag": source.rights_flag,
            "policy_url": source.policy_url, "credit": c.credit,
            "dimensions_text": c.dimensions_text,
            "finished_in": format_finished(*parsed) if parsed else "",
            "sha256": c.sha256, "file_sha256": file_sha, "px_w": str(c.px_w),
            "px_h": str(c.px_h), "tier": d["tier"], "class": d["class"],
            "capture": "museum_scan", "commit_ok": d["commit_ok"],
        })
    return out


def verify(cache: Path, rows: list[dict[str, str]]) -> list[str]:
    """Re-hash every fetched image against its manifest row."""
    problems = []
    for row in rows:
        path = cache / cache_name(row["source"], row["object_id"])
        if not path.exists():
            problems.append(f"{path.name}: not in the cache")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            problems.append(f"{path.name}: bytes differ from the manifest sha256")
    return problems


def recheck(client: Client, rows: list[dict[str, str]], cache: Path) -> list[str]:
    """Re-read each row's rights flag from its live record; any change is a problem.

    The policy pages answer scripted reads with 403 or 429 (2026-10-10), so the
    recheck fails on a policy page that is gone (404 or 410) and leaves a blocked
    one to the release's human check (E4)."""
    problems = []
    live: dict[tuple[str, str], Candidate | str] = {}
    sources = sorted({row["source"] for row in rows})
    with_rows = {s: [r for r in rows if r["source"] == s] for s in sources}
    if "met" in sources:
        for row in with_rows["met"]:
            record = client.json(f"{MET}/v1/objects/{row['object_id']}")
            live[("met", row["object_id"])] = _parse_or_reason("met", record)
    if "aic" in sources:
        ids = [row["object_id"] for row in with_rows["aic"]]
        for start in range(0, len(ids), 100):
            url = f"{AIC_API}/artworks?" + _query(
                {"ids": ",".join(ids[start:start + 100]), "fields": AIC_FIELDS, "limit": "100"})
            for record in client.json(url, {"AIC-User-Agent": USER_AGENT}).get("data") or []:
                live[("aic", str(record.get("id")))] = _parse_or_reason("aic", record)
    if "smithsonian" in sources:
        for record in si_rows(client, cache, refresh=True):
            parsed = _parse_or_reason("smithsonian", record)
            key = parsed.object_id if isinstance(parsed, Candidate) else record.get("id", "")
            live[("smithsonian", key)] = parsed
    if "lacma" in sources:
        for row in with_rows["lacma"]:
            page = client.get(f"https://collections.lacma.org/object/{row['object_id']}")
            record = {"object_id": row["object_id"], "html": page.decode("utf-8")}
            live[("lacma", row["object_id"])] = _parse_or_reason("lacma", record)
    for row in rows:
        found = live.get((row["source"], row["object_id"]))
        source = SOURCES[row["source"]]
        if found is None:
            problems.append(f"{row['file']}: no live record (withdrawn, or no longer flagged)")
        elif isinstance(found, str):
            problems.append(f"{row['file']}: {found}")
        elif (row["license"], row["rights_flag"], row["policy_url"]) != (
            source.license, source.rights_flag, source.policy_url
        ):
            problems.append(f"{row['file']}: license, flag or policy URL differs from the source's")
    for source in sources:
        url = SOURCES[source].policy_url
        try:
            client.get(url)
        except urllib.error.HTTPError as err:
            if err.code in (404, 410):
                problems.append(f"{source}: policy page {url} answers {err.code}")
        except urllib.error.URLError as err:
            problems.append(f"{source}: policy page {url} unreachable ({err.reason})")
    return problems


def _parse_or_reason(source: str, record: dict) -> Candidate | str:
    try:
        return PARSERS[source](record)
    except NotCleared as err:
        return str(err)


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="backslashreplace")
    if argv[:1] == ["--recheck"]:
        argv = ["recheck", *argv[1:]]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["search", "download", "rows", "verify",
                                            "attribution", "recheck"])
    parser.add_argument("screen_csv", nargs="?", type=Path)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--source", action="append", choices=sorted(FETCHERS))
    parser.add_argument("--refresh", action="store_true", help="re-request cached API answers")
    args = parser.parse_args(argv)
    sources = args.source or sorted(FETCHERS)
    client = Client()
    if args.command in {"search", "download"}:
        args.cache.mkdir(parents=True, exist_ok=True)
        report = (search(client, args.cache, sources, args.refresh) if args.command == "search"
                  else download(client, args.cache, sources))
        print(json.dumps({"report": report, "requests": client.requests}, indent=1))
        return 0
    if args.command == "rows":
        raise SystemExit("rows is driven by the screening step; see corpus/README.md")
    if args.command == "attribution":
        ATTRIBUTION.write_text(attribution_markdown(read_manifest()), encoding="utf-8",
                               newline="\n")
        print(ATTRIBUTION)
        return 0
    rows = read_manifest()
    problems = verify(args.cache, rows) if args.command == "verify" else recheck(
        client, rows, args.cache)
    for problem in problems:
        print(problem)
    print(f"{args.command}: {len(rows)} rows, {len(problems)} problem(s); requests {client.requests}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
