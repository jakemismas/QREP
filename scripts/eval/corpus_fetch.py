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
import subprocess
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


def default_cache() -> Path:
    """The main checkout's ignored corpus/private/cache/ (WORKER.md R1, its private-data
    exception), found through git so every worktree reads one copy and no fetched image can be
    staged; a worktree's git common dir is the main checkout's .git."""
    common = subprocess.run(
        ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
        cwd=REPO, capture_output=True, text=True, check=True,
    ).stdout.strip()
    return Path(common).parent / "corpus" / "private" / "cache"


class NotPrivate(ValueError):
    """A write target outside the main checkout's ignored corpus/private/."""


def require_private(path: Path) -> Path:
    """path, when it lies inside the main checkout's corpus/private/ and git ignores it.

    Fetched images and every view of them are written only there, because corpus-guard never
    sees a file outside corpus/, and a file git does not ignore can be staged by accident."""
    private = default_cache().parent.resolve()
    target = path.resolve()
    if not target.is_relative_to(private):
        raise NotPrivate(f"refusing {path}: write only inside {private}")
    ignored = subprocess.run(
        ["git", "-C", str(private.parents[1]), "check-ignore", "-q", "--no-index", str(target)],
        capture_output=True,
    )
    if ignored.returncode != 0:
        raise NotPrivate(f"refusing {path}: git does not ignore it")
    return path


COLUMNS = (
    "file", "license", "source", "object_id", "title", "landing_url", "image_url",
    "rights_flag", "policy_url", "credit", "dimensions_text", "finished_in", "sha256",
    "file_sha256", "px_w", "px_h", "tier", "class", "capture", "commit_ok", "date_end",
    "eval_set",
)
TIERS = ("A", "B", "R", "X")
IN_SCOPE = ("squares", "hst", "qst", "snowball", "flying_geese")
REFUSALS = ("on_point", "curve", "applique", "medallion", "hexagon", "diamond_star")
# Why a tier X photo is excluded from every eval set. whole_cloth has no piecing to read;
# outside_classes is an out-of-scope photo that none of plan D3a's six refusal classes names, so
# it cannot be a tier R row as the plan defines R.
EXCLUSIONS = ("partial_view", "duplicate", "not_a_quilt", "unreadable", "whole_cloth",
              "outside_classes")
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
    # Smithsonian Open Access's own media bucket (registry.opendata.aws/smithsonian-open-access);
    # ids.si.edu/ids/download redirects most image requests there. This bucket only: every
    # other amazonaws.com host stays refused.
    "smithsonian-open-access.s3-us-west-2.amazonaws.com",
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
        # An undated object may be modern too, so it is skipped with the modern ones.
        return self.date_end is None or self.date_end >= MODERN_FROM


def _decade_end(first: int) -> int:
    # A decade ends with its last year: the 1850s with 1859, because date_end is the last year
    # the record's date gives (corpus/README.md). A "00s" decade is also how a century is
    # written (the 1900s), so it reads the century's last year: the later end errs toward the
    # modern skip.
    return first + (99 if first % 100 == 0 else 9)


def _two_digit_end(start: str, end: str) -> int:
    # An end below the start's last two digits crosses into the next century: 1895-05 is 1905.
    century = int(start[:2]) + (1 if int(end) < int(start[2:]) else 0)
    return century * 100 + int(end)


def _years(text: str) -> list[int]:
    # Digit guards rather than word boundaries, so a decade such as 1850s still reads 1850.
    years = [int(y) for y in re.findall(r"(?<!\d)(1[5-9]\d\d|20\d\d)(?!\d)", text)]
    # Records write the decade's apostrophe straight or curly (1920's, 1920\u2019s).
    for decade in re.findall(r"(?<!\d)(1[5-9]\d0|20\d0)['\u2019]?s\b", text):
        years.append(_decade_end(int(decade)))
    # A decade range with a two-digit end, 1920s-30s, ends with the later decade's last year.
    for start, end in re.findall(
        r"(?<!\d)(1[5-9]\d0|20\d0)['\u2019]?s\s*[-\u2013/]\s*(\d0)['\u2019]?s\b", text
    ):
        years.append(_decade_end(_two_digit_end(start, end)))
    # A range written 1925-35 ends in 1935; museum records write the dash as a hyphen or an en
    # dash, and some write a range as 1929/30.
    for start, end in re.findall(r"(?<!\d)(1[5-9]\d\d|20\d\d)\s*[-\u2013/]\s*(\d\d)(?!\d)", text):
        years.append(_two_digit_end(start, end))
    # A century ends with its last year: the 19th century with 1900.
    for number in re.findall(r"(?<!\d)(1[5-9]|20)(?:st|nd|rd|th)\s+century", text, re.IGNORECASE):
        years.append(int(number) * 100)
    return years


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


def _si_record_id(row: dict) -> str:
    nonrep = (row.get("content") or {}).get("descriptiveNonRepeating") or {}
    return nonrep.get("record_ID") or row.get("id") or ""


def _si_media(row: dict) -> list[dict]:
    nonrep = (row.get("content") or {}).get("descriptiveNonRepeating") or {}
    return (nonrep.get("online_media") or {}).get("media") or []


# The physicalDescription labels that carry a size: NMAH records say "Measurements" and other
# Smithsonian units "Dimensions"; "Physical Description" and "Medium" entries name materials.
SI_SIZE_LABELS = ("Dimensions", "Measurements")


def si_candidate(row: dict) -> Candidate:
    """A Smithsonian Open Access search row; one image medium must be usage CC0."""
    content = row.get("content") or {}
    nonrep = content.get("descriptiveNonRepeating") or {}
    record_id = _si_record_id(row)
    media = _si_media(row)
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
            if e.get("label") in SI_SIZE_LABELS]
    years = [y for text in _texts(freetext.get("date")) for y in _years(text)]
    link = nonrep.get("record_link") or ""
    if not link.startswith("https://"):
        link = f"https://collections.si.edu/search/detail/{row.get('id') or record_id}"
    return Candidate(
        "smithsonian", record_id, clean_text((nonrep.get("title") or {}).get("content", "")),
        link, full[0] if full else medium.get("content", ""),
        # Some records carry no credit line; the holding museum's name still credits the image.
        clean_text("; ".join(_texts(freetext.get("creditLine"))) or nonrep.get("data_source") or ""),
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
    rf"(?:\b(?P<l1>[HWL])(?:\.|eight|idth|ength)?\s*)?(?P<a>{_NUM})\s*(?:in\.?|inches|cm)?\s*x\s*"
    rf"(?:\b(?P<l2>[HWL])(?:\.|eight|idth|ength)?\s*)?(?P<b>{_NUM})\s*(?:in\.?|inches|cm)?"
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


# The words that make a size the mount's or the frame's rather than the object's own.
_MOUNT = re.compile(r"\b(?:mount(?:ed|s)?|frame[ds]?)\b", re.IGNORECASE)
_UNMOUNTED = re.compile(r"\bwithout\s+(?:\w+\s+){0,2}(?:mount|frame)", re.IGNORECASE)
_FEET = re.compile(rf"(?P<ft>\d+)\s*ft\.?\s*(?:(?P<inch>{_NUM})\s*in\b\.?)?", re.IGNORECASE)


def _feet_to_inches(match: re.Match) -> str:
    inches = int(match["ft"]) * 12 + (_number(match["inch"]) if match["inch"] else 0)
    return f"{inches:g} in."


def orient(size: tuple[float, float], px_w: int, px_h: int) -> tuple[float, float]:
    """(width, height) turned to match the photo: museums disagree on which number comes
    first, but the quilt's longer side is the photo's longer side."""
    width, height = size
    if (px_w > px_h and width < height) or (px_w < px_h and width > height):
        return (height, width)
    return (width, height)


def parse_finished_size(text: str) -> tuple[float, float] | None:
    """(width, height) in inches from a museum dimensions text, or None.

    Inches win over centimetres. An unlabeled pair reads height x width, the
    museum convention for flat textiles; H., W. and L. labels win over order,
    one label alone included, and L. (length) reads as the height, because a
    museum that gives L x W for a flat textile measures its long side down. A
    size the text gives with the object's mount or frame yields to the object's
    own size (without mount, or the sight size) when the text gives both. The
    result is approximate: a museum measures the object, not the pattern."""
    normalized = _FEET.sub(_feet_to_inches, text.replace("\u00d7", "x").replace("\u00a0", " "))
    pairs = list(_PAIR.finditer(normalized))
    if not pairs:
        return None
    mounted, end = [], 0
    for match in pairs:
        before = normalized[end:match.start()]
        if mounted and not re.search(r"[A-Za-z]", before):
            # Only punctuation since the last pair, as in "(53.3 x 99.1 cm)" or NMAH's
            # "40 in x 30 in; 101 cm x 76 cm": the same size restated in the other unit.
            mounted.append(mounted[-1])
        else:
            # Only the words of this pair's own clause qualify it, so "Quilt mounted on
            # linen. Overall: 80 x 70 in." stays the object's size.
            clause = re.split(r"[.;]", before)[-1]
            mounted.append(bool(_MOUNT.search(clause)) and not _UNMOUNTED.search(clause))
        end = match.end()
    # The object's own size before its mount's or frame's, inches before centimetres, and
    # otherwise the order the text gives.
    _, chosen = min(
        ((mounted[i], m["unit"].lower().startswith("cm"), i), m) for i, m in enumerate(pairs))
    scale = 1 / 2.54 if chosen["unit"].lower().startswith("cm") else 1.0
    a, b = (round(_number(chosen[k]) * scale, 2) for k in ("a", "b"))
    labels = tuple((chosen[k] or "").upper().replace("L", "H") for k in ("l1", "l2"))
    # A width first, or a height second, puts the width first whether or not the other number
    # carries a label.
    if labels in {("W", "H"), ("W", ""), ("", "H")}:
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

    def get_final(
        self, url: str, headers: dict[str, str] | None = None
    ) -> tuple[bytes, str, int]:
        """The body, the URL that answered after any redirects, and its HTTP status."""
        check_host(url)
        self.limiter.wait()
        host = urllib.parse.urlsplit(url).hostname or ""
        self.requests[host] = self.requests.get(host, 0) + 1
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
        with self.opener.open(request, timeout=180) as response:
            return response.read(), response.geturl(), response.status

    def get(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        return self.get_final(url, headers)[0]

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
            reason = f"made {MODERN_FROM} or later, or undated"
            skipped[reason] = skipped.get(reason, 0) + 1
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


def _image_facts(data: bytes) -> tuple[str, int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    with Image.open(io.BytesIO(data)) as image:
        width, height = image.size
    return hashlib.sha256(data).hexdigest(), width, height


def _image_headers(source: str) -> dict[str, str]:
    # AIC asks every client, image requests included, to identify itself in AIC-User-Agent.
    return {"AIC-User-Agent": USER_AGENT} if source == "aic" else {}


def download(client: Client, cache: Path, sources: list[str]) -> dict:
    """Fetch each candidate's image once; verify a cached one against its recorded sha256."""
    candidates = load_candidates(cache)
    failed = {}
    for c in candidates:
        if c.source not in sources:
            continue
        path = cache / c.cache_file
        try:
            # Validate before caching: a challenge page or an error body answered with 200 must
            # not sit in the cache, where it would block every later fetch of that image.
            data = path.read_bytes() if path.exists() else client.get(
                c.image_url, _image_headers(c.source))
            sha, width, height = _image_facts(data)
            if not path.exists():
                path.write_bytes(data)
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
    """Manifest rows for every screened candidate that still clears.

    screen_csv columns: stem, tier, class, commit_ok, and optionally eval_set. Without an
    eval_set column each row's eval_set is None, which merge_rows reads as "keep the old
    row's", so a re-screen never drops a photo from the eval set unasked. committed maps a
    cache file to the committed copy's corpus-relative path and its own sha256."""
    by_stem = {Path(c.cache_file).stem: c for c in load_candidates(cache) if c.sha256}
    with screen_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        decisions = list(reader)
        has_eval_set = "eval_set" in (reader.fieldnames or [])
    missing = [d["stem"] for d in decisions if d["stem"] not in by_stem]
    if missing:
        # A decision for a photo that is not fetched (or no longer clears) is a screening error,
        # not a row to drop quietly.
        raise ValueError(f"screen decisions with no fetched candidate: {missing}")
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
            "finished_in": format_finished(*orient(parsed, c.px_w, c.px_h)) if parsed else "",
            "sha256": c.sha256, "file_sha256": file_sha, "px_w": str(c.px_w),
            "px_h": str(c.px_h), "tier": d["tier"], "class": d["class"],
            "capture": "museum_scan", "commit_ok": d["commit_ok"], "date_end": str(c.date_end),
            "eval_set": (d["eval_set"] or "") if has_eval_set else None,
        })
    return out


def committed_copies(rows: Iterable[dict[str, str]]) -> dict[str, tuple[str, str]]:
    """The committed copies the manifest already binds, keyed by cache file."""
    return {cache_name(r["source"], r["object_id"]): (r["file"], r["file_sha256"])
            for r in rows if r["file"].startswith("images/")}


def merge_rows(old: Iterable[dict[str, str]], new: Iterable[dict[str, str]]) -> list[dict]:
    """old with each photo that new screens replaced by its new row, and new photos added.

    A new row whose eval_set is None (or absent) keeps the old row's eval_set, and a new photo
    gets "", because a screen that says nothing about the eval set must not change it."""
    merged = {(r["source"], r["object_id"]): r for r in old}
    for row in new:
        key = (row["source"], row["object_id"])
        if row.get("eval_set") is None:
            previous = merged.get(key) or {}
            row = row | {"eval_set": previous.get("eval_set") or ""}
        merged[key] = row
    return list(merged.values())


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


def live_flag(source: str, record: dict, image_url: str | None = None) -> str:
    """The record's own rights value, written as a manifest rights_flag, whether or not it clears.

    A flag that clears renders exactly as SOURCES gives it, so a row whose flag still holds
    compares equal; anything else renders what the record says, so a change names itself.
    image_url is the row's image; a Smithsonian record reads the access of the medium that
    serves it, because a record can hold a CC0 medium beside the restricted one the row uses."""
    if source in ("met", "aic"):
        key = "isPublicDomain" if source == "met" else "is_public_domain"
        return f"{key}={json.dumps(record[key]) if key in record else 'missing'}"
    if source == "smithsonian":
        images = [m for m in _si_media(record) if m.get("type") == "Images"]
        own = [m for m in images if image_url is not None and (
            m.get("content") == image_url
            or any(r.get("url") == image_url for r in m.get("resources") or []))]
        accesses = [(m.get("usage") or {}).get("access") for m in own or images]
        # With no medium serving the row's image, as si_candidate clears a record on any CC0
        # image medium, any CC0 medium reads CC0; otherwise the first medium's value shows what
        # the record says now.
        access = accesses[0] if own else (
            "CC0" if "CC0" in accesses else (accesses[0] if accesses else None))
        return f"media.usage.access={access if access is not None else 'missing'}"
    if source == "lacma":
        flags = _PUBLIC_DOMAIN.findall(record["html"])
        if not flags:
            return "publicDomain=missing"
        return "publicDomain=" + ("1" if all(f == "1" for f in flags) else ",".join(flags))
    raise ValueError(f"unknown source {source!r}")


def _record_id(source: str, record: dict) -> str:
    if source == "met":
        return str(record.get("objectID"))
    if source == "aic":
        return str(record.get("id"))
    if source == "smithsonian":
        return _si_record_id(record)
    return record["object_id"]


def _live_flags(
    client: Client, rows: list[dict[str, str]], cache: Path
) -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str]]:
    """Each row's live_flag by (source, object_id), and why any row's record could not be read.
    A row in neither map has no live record."""
    flags: dict[tuple[str, str], str] = {}
    errors: dict[tuple[str, str], str] = {}
    image_urls = {(r["source"], r["object_id"]): r.get("image_url") or None for r in rows}

    def read(source: str, wanted: list[str], fetch: Callable[[], list[dict]]) -> None:
        # The flag is rendered inside the guard too, so a record of an unexpected shape is that
        # row's problem rather than a traceback that hides every other row's result.
        try:
            by_id = {_record_id(source, record): record for record in fetch()}
            found = {oid: live_flag(source, by_id[oid], image_urls[(source, oid)])
                     for oid in wanted if oid in by_id}
        except Exception as err:  # noqa: BLE001 - one unreadable record must not hide the rest
            reason = f"{type(err).__name__}: {err}"
            errors.update({(source, object_id): reason for object_id in wanted})
            return
        flags.update({(source, oid): flag for oid, flag in found.items()})

    ids = {name: [r["object_id"] for r in rows if r["source"] == name] for name in SOURCES}
    for oid in ids["met"]:
        read("met", [oid], lambda oid=oid: [client.json(f"{MET}/v1/objects/{oid}")])
    for start in range(0, len(ids["aic"]), 100):
        batch = ids["aic"][start:start + 100]
        url = f"{AIC_API}/artworks?" + _query(
            {"ids": ",".join(batch), "fields": AIC_FIELDS, "limit": "100"})
        read("aic", batch,
             lambda url=url: client.json(url, {"AIC-User-Agent": USER_AGENT}).get("data") or [])
    if ids["smithsonian"]:
        read("smithsonian", ids["smithsonian"], lambda: si_rows(client, cache, refresh=True))
    for oid in ids["lacma"]:
        read("lacma", [oid], lambda oid=oid: [{"object_id": oid, "html": client.get(
            f"https://collections.lacma.org/object/{oid}").decode("utf-8")}])
    return flags, errors


def _policy_problem(client: Client, url: str) -> str | None:
    try:
        _, final, status = client.get_final(url)
    except urllib.error.HTTPError as err:
        return f"policy page {url} answers HTTP {err.code}"
    except urllib.error.URLError as err:
        return f"policy page {url} unreachable ({err.reason})"
    except Exception as err:  # noqa: BLE001 - a redirect off the allowlist raises HostRefused
        return f"policy page {url} unreadable ({type(err).__name__}: {err})"
    if final != url:
        return f"policy page {url} redirects to {final}"
    if status != 200:
        return f"policy page {url} answers HTTP {status}"
    return None


def recheck(client: Client, rows: list[dict[str, str]], cache: Path) -> list[str]:
    """Re-read each row's rights value from its live record and every policy page the rows
    cite; any change is a problem.

    A row passes when its live record renders, through live_flag with the row's image_url, to
    the row's own rights_flag, and its license, rights_flag and policy_url are the ones its
    source sets in SOURCES. A record that cannot be fetched, or is missing, is a problem. A
    policy page passes only on HTTP 200 at the URL the row cites: any error
    status (403 and 429 included), any redirect and any unreachable page is a problem. The
    recheck fails closed, with nothing left to a human check, because a policy page that blocks
    scripted reads is one whose terms the recheck cannot confirm."""
    flags, errors = _live_flags(client, rows, cache)
    problems = []
    for row in rows:
        file, key = row["file"], (row["source"], row["object_id"])
        source = SOURCES.get(row["source"])
        if source is None:
            problems.append(f"{file}: unknown source {row['source']!r}")
            continue
        for column, expected in (("license", source.license),
                                 ("rights_flag", source.rights_flag),
                                 ("policy_url", source.policy_url)):
            if row[column] != expected:
                problems.append(f"{file}: {column} {row[column]} is not {expected}, "
                                f"the {column} {source.name} sets")
        if key in errors:
            problems.append(f"{file}: live record unreadable ({errors[key]})")
        elif key not in flags:
            problems.append(f"{file}: no live record (withdrawn, or no longer flagged)")
        elif flags[key] != row["rights_flag"]:
            problems.append(
                f"{file}: rights flag changed from {row['rights_flag']} to {flags[key]}")
    for url in sorted({row["policy_url"] for row in rows}):
        problem = _policy_problem(client, url)
        if problem is not None:
            problems.append(problem)
    return problems


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="backslashreplace")
    if argv[:1] == ["--recheck"]:
        argv = ["recheck", *argv[1:]]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["search", "download", "rows", "verify",
                                            "attribution", "recheck"])
    parser.add_argument("screen_csv", nargs="?", type=Path)
    parser.add_argument("--cache", type=Path, default=None)
    parser.add_argument("--source", action="append", choices=sorted(FETCHERS))
    parser.add_argument("--refresh", action="store_true", help="re-request cached API answers")
    args = parser.parse_args(argv)
    sources = args.source or sorted(FETCHERS)
    args.cache = require_private(args.cache or default_cache())
    client = Client()
    if args.command in {"search", "download"}:
        args.cache.mkdir(parents=True, exist_ok=True)
        report = (search(client, args.cache, sources, args.refresh) if args.command == "search"
                  else download(client, args.cache, sources))
        print(json.dumps({"report": report, "requests": client.requests}, indent=1))
        return 1 if report.get("failed") else 0
    if args.command == "rows":
        if args.screen_csv is None:
            parser.error("rows needs SCREEN_CSV")
        write_manifest(merge_rows(read_manifest(), build_rows(
            args.cache, args.screen_csv, committed_copies(read_manifest()))))
        print(MANIFEST)
        return 0
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
