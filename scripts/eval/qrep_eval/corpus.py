"""The eval's view of the corpus: which photos, which split, which truth.

Photos come from corpus/manifest.csv (the eval set's rows), their annotations
from corpus/annotations/, and their source images from the cache the fetch
script fills (the main checkout's corpus/private/cache/), checked against the
row's sha256 before any read. A row counts toward a gate only when its truth is
gate truth (plan 5.D); a row built on proposals is labeled provisional.
"""

import csv
import hashlib
import math
from dataclasses import dataclass, field
from pathlib import Path

from qrep.contract import Counts
from qrep_eval import annotation as an

# The app's resolution caps (web/src/model/downscale.ts): as fetched, desktop, phone.
RESOLUTIONS: dict[str, int | None] = {"full": None, "desktop-2000": 2000, "phone-1400": 1400}

# The report's device classes, from each photo's capture. A nested screenshot is a
# screenshot, never a phone capture (approaches-25).
DEVICE_CLASS = {
    "museum_scan": "museum scan",
    "direct_screenshot": "screenshot",
    "nested_screenshot": "screenshot",
    "camera": "phone camera",
}

# Proposals stand in only where no truth exists, and then label the row provisional.
PROPOSALS = ("proposed-a", "proposed-b")


def cap_size(width: int, height: int, cap: int | None) -> tuple[int, int]:
    """The app's targetSize: the longest side down to the cap, the other side rounded
    half up as JavaScript's Math.round does; never upscaled."""
    longest = max(width, height)
    if cap is None or longest <= cap:
        return width, height
    factor = cap / longest
    return math.floor(width * factor + 0.5), math.floor(height * factor + 0.5)


def split_of(sha256: str) -> str:
    return "holdout" if an.in_holdout(sha256) else "dev"


@dataclass
class TruthView:
    """What the simulated user confirms, and whether it is gate truth."""

    corners: list[tuple[float, float]] | None
    bands: list[float]
    counts: Counts | None
    fabric_count: int | None
    construction: str | None
    provenance: dict[str, str] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return "gate" if self.provenance and all(
            code in an.FRAME_TRUTH for code in self.provenance.values()) else "provisional"


def truth_view(annotation: an.Annotation) -> TruthView:
    """Corners, bands, counts and class from verified-jake claims, else from the
    proposals (labeled provisional). The fabric count also accepts the square-truth
    codes, since a gold layout's roles fix it."""
    framed = an.pick(annotation.frame, an.FRAME_TRUTH) or an.pick(annotation.frame, PROPOSALS)
    counted = an.pick(annotation.counts, an.FRAME_TRUTH) or an.pick(annotation.counts, PROPOSALS)
    built = (an.pick(annotation.construction_class, an.FRAME_TRUTH)
             or an.pick(annotation.construction_class, PROPOSALS))
    fabrics = an.pick(annotation.fabrics, an.TRUTH) or an.pick(annotation.fabrics, PROPOSALS)
    provenance = {}
    corners = None
    bands: list[float] = []
    if framed is not None:
        c = framed.value.outer_edge.corners
        corners = [(p.x, p.y) for p in (c.top_left, c.top_right, c.bottom_right, c.bottom_left)]
        bands = [band.width_squares for band in framed.value.outer_edge.bands]
        provenance["frame"] = framed.provenance
    if counted is not None:
        provenance["counts"] = counted.provenance
    if built is not None:
        provenance["construction_class"] = built.provenance
    return TruthView(
        corners=corners,
        bands=bands,
        counts=counted.value if counted is not None else None,
        fabric_count=fabrics.value.count if fabrics is not None else None,
        construction=built.value if built is not None else None,
        provenance=provenance,
    )


@dataclass
class Photo:
    stem: str
    row: dict[str, str]
    annotation: an.Annotation
    source: Path

    @property
    def tier(self) -> str:
        return self.row["tier"]

    @property
    def split(self) -> str:
        return split_of(self.row["sha256"])

    @property
    def device_class(self) -> str:
        claim = an.pick(self.annotation.capture, ("verified-jake", "screened"))
        return DEVICE_CLASS[claim.value if claim else self.row["capture"]]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_photos(corpus_dir: Path, cache_dir: Path, eval_set: str = "v0") -> list[Photo]:
    """Every eval-set row with its annotation and its verified source image, in
    manifest order. A missing or changed source image stops the run: a silently
    skipped photo would shrink n without saying so."""
    with (corpus_dir / "manifest.csv").open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle) if row.get("eval_set") == eval_set]
    photos = []
    for row in rows:
        stem = Path(row["file"]).stem
        annotation = an.load(corpus_dir / "annotations" / f"{stem}.json")
        source = cache_dir / Path(row["file"]).name
        if not source.exists():
            raise FileNotFoundError(f"{stem}: source image {source} is not in the cache")
        if sha256_of(source) != row["sha256"]:
            raise ValueError(f"{stem}: {source} does not match the manifest sha256")
        photos.append(Photo(stem, row, annotation, source))
    return photos
