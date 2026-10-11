"""Corpus annotation format: what one photo shows, field by field, and who said so.

One JSON file per photo, corpus/annotations/<photo stem>.json, validated by the
Annotation model below and by its export, corpus/schema/annotation.schema.json,
which the dev annotate page (C3a) writes against. The frame, band and count
shapes are qrep/contract.py's own models, imported rather than redefined, so the
UI, the eval and the corpus share one shape (plan section 5.E, E1b).

Coordinates are pixels of the source image as fetched (canvas = its width and
height), whichever file photo names: a committed copy under corpus/images/ is
downsized, so to_read_request scales the corners to the size of the image the
request stages.

Every annotated field is a list of claims, each a value with a provenance code,
so a later verification sits beside the proposals instead of overwriting them,
and the eval can count only gate truth (plan section 8.2). Annotation values
are judgments by people or agents, never engine output, so they carry
provenance rather than a CV confidence; agent proposals never count as truth.
The identity fields (schema_version, photo, sha256, canvas) are not claims:
they are the key that binds the file to its manifest row, and
licensed_photo_problems checks each of them against that row.
"""

import json
import re
from pathlib import Path
from typing import Annotated, Literal, TypeVar, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from qrep.contract import (
    FABRICS_MAX,
    FABRICS_MIN,
    Corners,
    Counts,
    FieldFrame,
    OuterEdgeFrame,
    Point,
    ReadRequest,
)

SCHEMA_VERSION = 1

Provenance = Literal[
    "proposed-a",
    "proposed-b",
    "adjudicated",
    "verified-jake",
    "hand-authored",
    "source-record",
    "screened",
]
PROVENANCES: tuple[str, ...] = get_args(Provenance)
# Gate truth (plan section 5.D): verified-jake for corners, counts and bands,
# hand-authored plus adjudicated for squares. source-record marks a value copied
# from the institution's own record (its dimensions text), and screened a value
# the screen sets from the photo's source (a museum photo's capture and device);
# nobody judged either one photo by photo, so neither is ever truth.
TRUTH: tuple[str, ...] = ("verified-jake", "adjudicated", "hand-authored")
# Corners, bands and counts count as truth only when Jake verified them.
FRAME_TRUTH: tuple[str, ...] = ("verified-jake",)

# The dev annotate page's classes (plan C3a), so its JSON validates here.
ConstructionClass = Literal["squares", "hst", "qst", "snowball", "flying_geese", "out_of_scope"]
CONSTRUCTION_CLASSES: tuple[str, ...] = get_args(ConstructionClass)
# The refusal classes plan D3a lists, and only those.
RefusalClass = Literal["on_point", "curve", "applique", "medallion", "hexagon", "diamond_star"]
REFUSAL_CLASSES: tuple[str, ...] = get_args(RefusalClass)
# The photoreal sidecar's character vocabulary (tests/fixtures/photoreal/generator.py).
Character = Literal["squares", "non_square", "no_pattern", "garbage"]
# A nested screenshot is a screenshot of a screen showing a photo; it never
# counts as a phone capture (approaches-25).
Capture = Literal["museum_scan", "direct_screenshot", "nested_screenshot", "camera"]
CAPTURES: tuple[str, ...] = get_args(Capture)
DeviceClass = Literal["museum", "phone", "tablet", "computer", "camera"]
DEVICE_CLASSES: tuple[str, ...] = get_args(DeviceClass)
MaskReason = Literal["label", "occlusion", "other"]

# The licenses corpus-guard admits (scripts/corpus_guard.py ALLOWED_LICENSES).
LICENSES = ("CC0-1.0", "PDM-1.0")

SHA256_PATTERN = r"^[0-9a-f]{64}$"
HEX_COLOR_PATTERN = r"^#[0-9a-f]{6}$"
_SHA256 = re.compile(SHA256_PATTERN)

class _Strict(BaseModel):
    # The contract's rule: refuse a wrong type or an unknown field instead of
    # coercing it, so a misspelled field never reads as absent.
    model_config = ConfigDict(strict=True, extra="forbid")


class AnnotatedFrame(_Strict):
    """The outer edge with its bands from the outside in (no border: no bands),
    and the field corners when they can be seen."""

    outer_edge: OuterEdgeFrame
    field: FieldFrame | None = None


class Fabrics(_Strict):
    """How many fabrics, and optionally each one's pattern role and color."""

    count: int = Field(ge=1)
    roles: list[str] = Field(default_factory=list)
    palette_hex: list[str] = Field(default_factory=list)

    @field_validator("roles")
    @classmethod
    def _roles_named(cls, roles: list[str]) -> list[str]:
        if any(not role.strip() for role in roles):
            raise ValueError("a fabric role must not be blank")
        if len(set(roles)) != len(roles):
            raise ValueError("fabric roles must differ")
        return roles

    @field_validator("palette_hex")
    @classmethod
    def _hex_colors(cls, colors: list[str]) -> list[str]:
        for color in colors:
            if not re.fullmatch(HEX_COLOR_PATTERN, color):
                raise ValueError(f"palette color {color!r} is not #rrggbb in lower case")
        return colors

    @model_validator(mode="after")
    def _one_entry_per_fabric(self):
        for name in ("roles", "palette_hex"):
            entries = getattr(self, name)
            if entries and len(entries) != self.count:
                raise ValueError(f"{name} lists {len(entries)} fabrics, count says {self.count}")
        return self


class FinishedSize(_Strict):
    """The finished quilt in inches, width across the photo and height down it."""

    width_in: float = Field(gt=0, allow_inf_nan=False)
    height_in: float = Field(gt=0, allow_inf_nan=False)
    approximate: bool
    source_text: str = Field(min_length=1)


class Mask(_Strict):
    """A region the eval ignores, such as an accession label on a slide scan."""

    polygon: list[Point] = Field(min_length=3)
    reason: MaskReason


class Grid(_Strict):
    """The photoreal sidecar's grid: squares down and across the field, and the border's
    total width in squares (None when the bands are not known)."""

    rows: int = Field(ge=1)
    cols: int = Field(ge=1)
    border_pitches: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class _Claim(_Strict):
    provenance: Provenance


class FrameClaim(_Claim):
    value: AnnotatedFrame


class CountsClaim(_Claim):
    value: Counts


class ConstructionClassClaim(_Claim):
    value: ConstructionClass


class RefusalClassClaim(_Claim):
    value: RefusalClass


class FabricsClaim(_Claim):
    value: Fabrics


class FinishedSizeClaim(_Claim):
    value: FinishedSize


class CaptureClaim(_Claim):
    value: Capture


class DeviceClassClaim(_Claim):
    value: DeviceClass


class MasksClaim(_Claim):
    value: list[Mask]


class QuadClaim(_Claim):
    """The sidecar's quad: the outer edge as [x, y] pairs, top left first, clockwise."""

    value: list[tuple[float, float]] = Field(min_length=4, max_length=4)


class GridClaim(_Claim):
    value: Grid


class RepeatCellsClaim(_Claim):
    """The sidecar's repeat_cells: [down, across] squares per block, or None for one block."""

    value: tuple[Annotated[int, Field(ge=1)], Annotated[int, Field(ge=1)]] | None


class CharacterClaim(_Claim):
    value: Character


class GoldLayoutClaim(_Claim):
    """A path under corpus/gold/ (D3b)."""

    value: str = Field(min_length=1)


C = TypeVar("C", bound=_Claim)


class Annotation(_Strict):
    schema_version: Literal[1]
    # The photo's corpus/manifest.csv file value, its source image's sha256,
    # and that image's [width, height] in pixels, as the photoreal sidecar
    # writes canvas.
    photo: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256_PATTERN)
    canvas: tuple[int, int]
    frame: list[FrameClaim] = Field(default_factory=list)
    counts: list[CountsClaim] = Field(default_factory=list)
    construction_class: list[ConstructionClassClaim] = Field(default_factory=list)
    refusal_class: list[RefusalClassClaim] = Field(default_factory=list)
    fabrics: list[FabricsClaim] = Field(default_factory=list)
    finished_size: list[FinishedSizeClaim] = Field(default_factory=list)
    capture: list[CaptureClaim] = Field(default_factory=list)
    device_class: list[DeviceClassClaim] = Field(default_factory=list)
    masks: list[MasksClaim] = Field(default_factory=list)
    gold_layout: list[GoldLayoutClaim] = Field(default_factory=list)
    # The photoreal sidecar fields this format extends; sidecar_view derives any that a
    # provenance leaves out from its frame, counts and class.
    quad: list[QuadClaim] = Field(default_factory=list)
    grid: list[GridClaim] = Field(default_factory=list)
    repeat_cells: list[RepeatCellsClaim] = Field(default_factory=list)
    character: list[CharacterClaim] = Field(default_factory=list)

    @field_validator("canvas")
    @classmethod
    def _positive_canvas(cls, canvas: tuple[int, int]) -> tuple[int, int]:
        if min(canvas) < 1:
            raise ValueError("canvas width and height must be at least 1 pixel")
        return canvas

    @model_validator(mode="after")
    def _one_claim_per_provenance(self):
        for name in CLAIM_FIELDS:
            codes = [claim.provenance for claim in getattr(self, name)]
            if len(set(codes)) != len(codes):
                raise ValueError(f"{name} has two claims with one provenance code")
        return self

    @model_validator(mode="after")
    def _points_on_canvas(self):
        width, height = self.canvas

        def on_canvas(x: float, y: float, what: str) -> None:
            if not (0 <= x <= width and 0 <= y <= height):
                raise ValueError(f"{what} ({x}, {y}) lies off the {width} x {height} canvas")

        for claim in self.frame:
            frames = [claim.value.outer_edge] + ([claim.value.field] if claim.value.field else [])
            for frame in frames:
                for corner in _corner_points(frame):
                    on_canvas(corner.x, corner.y, f"{claim.provenance} corner")
        for claim in self.masks:
            for mask in claim.value:
                for point in mask.polygon:
                    on_canvas(point.x, point.y, f"{claim.provenance} mask point")
        for claim in self.quad:
            for x, y in claim.value:
                on_canvas(x, y, f"{claim.provenance} quad point")
        return self

    @model_validator(mode="after")
    def _quads_in_order(self):
        for claim in self.frame:
            edge = _corner_points(claim.value.outer_edge)
            _check_quad(edge, f"{claim.provenance} outer edge")
            if claim.value.field is not None:
                field = _corner_points(claim.value.field)
                _check_quad(field, f"{claim.provenance} field")
                # The field lies inside the outer edge (on it when there is no border).
                for corner in field:
                    if any(_cross(a, b, corner) < 0 for a, b in _edges(edge)):
                        raise ValueError(
                            f"{claim.provenance} field corner ({corner.x}, {corner.y}) lies "
                            "outside the outer edge")
        for claim in self.quad:
            _check_quad([Point(x=x, y=y) for x, y in claim.value], f"{claim.provenance} quad")
        return self


CLAIM_FIELDS: tuple[str, ...] = tuple(
    name
    for name in Annotation.model_fields
    if name not in {"schema_version", "photo", "sha256", "canvas"}
)


def _corner_points(frame: OuterEdgeFrame | FieldFrame) -> list[Point]:
    c = frame.corners
    return [c.top_left, c.top_right, c.bottom_right, c.bottom_left]


def _cross(a: Point, b: Point, c: Point) -> float:
    # z of (b - a) x (c - a); with y pointing down, positive means c turns clockwise from a-b.
    return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)


def _edges(quad: list[Point]) -> list[tuple[Point, Point]]:
    return [(quad[i], quad[(i + 1) % 4]) for i in range(4)]


def _check_quad(quad: list[Point], what: str) -> None:
    """Corners top left, top right, bottom right, bottom left: a convex quad traced clockwise
    on screen, each corner on its own side, so a swapped, crossed or flat quad fails."""
    tl, tr, br, bl = quad
    if not (tl.x < tr.x and bl.x < br.x and tl.y < bl.y and tr.y < br.y):
        raise ValueError(f"{what} corners are out of order")
    if any(_cross(quad[i], quad[(i + 1) % 4], quad[(i + 2) % 4]) <= 0 for i in range(4)):
        raise ValueError(f"{what} is crossed, concave or flat")


def schema() -> dict:
    """The JSON Schema that corpus/schema/annotation.schema.json holds."""
    return Annotation.model_json_schema()


def schema_text() -> str:
    return json.dumps(schema(), indent=2, sort_keys=True) + "\n"


def load(path: str | Path) -> Annotation:
    # JSON mode, as the page's output arrives: strict JSON accepts an array for
    # the canvas tuple and an integer for a coordinate.
    return Annotation.model_validate_json(Path(path).read_text(encoding="utf-8"))


def in_holdout(sha256: str) -> bool:
    """The holdout rule (corpus/README.md): the first 8 hex digits of the source
    image's sha256, read as an integer, divisible by 3."""
    if not _SHA256.fullmatch(sha256):
        raise ValueError(f"not a lowercase sha256: {sha256!r}")
    return int(sha256[:8], 16) % 3 == 0


def licensed_photo_problems(
    doc: Annotation | dict, stem: str | None, rows_by_file: dict[str, dict[str, str]]
) -> list[str]:
    """Why an annotation or gold file may not be committed, or [] when it may.

    The rule of issue #113: a committed annotation names a photo with a
    CC0-1.0 or PDM-1.0 manifest row that binds the same source image, because a
    cell model of a private photo can reveal a modern design (plan section 8.2);
    such annotations stay in corpus/private/. doc is an Annotation, whose file
    sits under its photo's stem (stem is its file name's stem), or any parsed
    JSON document such as a D3b gold layout (stem None, so its file name is
    D3b's to choose), of which only the photo and sha256 keys are read, and its
    canvas when it names one.
    """
    if isinstance(doc, Annotation):
        photo, sha256, canvas = doc.photo, doc.sha256, list(doc.canvas)
    else:
        photo, sha256, canvas = doc.get("photo"), doc.get("sha256"), doc.get("canvas")
    names_canvas = isinstance(doc, Annotation) or "canvas" in doc
    row = rows_by_file.get(photo) if isinstance(photo, str) else None
    if row is None:
        return [f"photo {photo!r} has no row in corpus/manifest.csv"]
    problems = []
    if row.get("license") not in LICENSES:
        problems.append(f"row {photo!r} is licensed {row.get('license')!r}")
    if row.get("sha256") != sha256:
        problems.append(f"row {photo!r} binds another source image")
    if stem is not None and Path(photo).stem != stem:
        problems.append(f"file stem {stem!r} is not the photo's stem")
    if names_canvas and (not isinstance(canvas, list) or [
        row.get("px_w"), row.get("px_h")
    ] != [str(n) for n in canvas]):
        problems.append(f"canvas {canvas!r} is not the row's px_w and px_h")
    return problems


def pick(claims: list[C], prefer: tuple[str, ...] = TRUTH) -> C | None:
    """The claim whose provenance comes first in prefer, or None."""
    by_code = {claim.provenance: claim for claim in claims}
    for code in prefer:
        if code in by_code:
            return by_code[code]
    return None


def to_read_request(
    annotation: Annotation,
    token: str,
    image_size: tuple[int, int],
    *,
    frame: Literal["outer_edge", "field"] = "outer_edge",
    prefer: tuple[str, ...] = FRAME_TRUTH,
) -> ReadRequest:
    """The read request a user who confirmed this annotation would send.

    token names the staged image and image_size is its (width, height) in
    pixels: the canvas for the source image, or a committed copy's own size,
    whose aspect ratio must be the canvas's within 1 percent. The corners are
    scaled from canvas pixels to the staged image's pixels, because a
    request's corners index the image it stages. frame chooses what
    the user confirmed: the outer edge with its bands, or the field corners.
    prefer orders the provenance codes to accept; the default accepts gate
    truth only, so a proposal never stands in for truth unless the caller asks.
    """
    framed, counted = pick(annotation.frame, prefer), pick(annotation.counts, prefer)
    if framed is None or counted is None:
        raise ValueError(f"{annotation.photo}: no frame or counts with provenance in {prefer}")
    chosen = framed.value.outer_edge if frame == "outer_edge" else framed.value.field
    if chosen is None:
        raise ValueError(f"{annotation.photo}: the {framed.provenance} frame has no field corners")
    fabrics = pick(annotation.fabrics, prefer)
    count = fabrics.value.count if fabrics else None
    # A count outside the read's range (one fabric, or a scrappy quilt above 12) leaves the read
    # to choose, as a user who skips the count would, instead of failing the request.
    if count is not None and not FABRICS_MIN <= count <= FABRICS_MAX:
        count = None
    if min(image_size) < 1:
        raise ValueError(f"image size {image_size} must be at least 1 pixel each way")
    # A downsized copy keeps the canvas's shape; a size whose shape differs by more than 1
    # percent is usually (height, width) passed as (width, height), which would stretch the
    # corners off the quilt.
    image_ratio = image_size[0] / image_size[1]
    canvas_ratio = annotation.canvas[0] / annotation.canvas[1]
    if abs(image_ratio - canvas_ratio) / canvas_ratio > 0.01:
        raise ValueError(
            f"image size {image_size} is not the shape of the canvas {annotation.canvas}; "
            "pass (width, height)")
    sx, sy = image_size[0] / annotation.canvas[0], image_size[1] / annotation.canvas[1]
    c = chosen.corners
    scaled = Corners(**{
        name: Point(x=point.x * sx, y=point.y * sy)
        for name, point in (("top_left", c.top_left), ("top_right", c.top_right),
                            ("bottom_right", c.bottom_right), ("bottom_left", c.bottom_left))
    })
    return ReadRequest(
        token=token,
        frame=chosen.model_copy(update={"corners": scaled}),
        crop_offset=Point(x=0.0, y=0.0),
        counts=counted.value,
        fabric_count=count,
    )


def sidecar_view(annotation: Annotation, prefer: tuple[str, ...] = FRAME_TRUTH) -> dict:
    """The photoreal sidecar fields, in the sidecar's own shapes, so the eval
    can score both with one code path. A stored quad, grid, repeat_cells or
    character claim wins when its provenance ranks at or before, in prefer,
    the provenance of the claim the derived value comes from (frame for quad,
    counts for grid and repeat_cells, construction_class for character), or
    when there is no derived value, so a proposal never overrides a verified
    derivation. Otherwise each is derived: quad is the outer edge
    (the sidecar's quad spans its border); grid.border_pitches is the bands'
    total width in squares, or None when no frame gives the bands;
    repeat_cells is [down, across] squares per block, or None for one block per
    axis; an in-scope class reads squares or non_square, and out_of_scope,
    which the sidecar vocabulary has no word for, reads None."""
    framed, counted = pick(annotation.frame, prefer), pick(annotation.counts, prefer)
    built = pick(annotation.construction_class, prefer)
    fabrics = pick(annotation.fabrics, prefer)
    view: dict = {
        "canvas": list(annotation.canvas),
        "quad": None,
        "grid": None,
        "repeat_cells": None,
        "palette_hex": list(fabrics.value.palette_hex) if fabrics else None,
        "character": None,
    }
    if framed is not None:
        edge = framed.value.outer_edge
        view["quad"] = [[p.x, p.y] for p in _corner_points(edge)]
    if counted is not None:
        n = counted.value
        bands = framed.value.outer_edge.bands if framed is not None else None
        view["grid"] = {
            "rows": n.blocks_down * n.squares_per_block_down,
            "cols": n.blocks_across * n.squares_per_block_across,
            "border_pitches": (
                sum(band.width_squares for band in bands) if bands is not None else None),
        }
        if (n.blocks_across, n.blocks_down) != (1, 1):
            view["repeat_cells"] = [n.squares_per_block_down, n.squares_per_block_across]
    if built is not None and built.value != "out_of_scope":
        view["character"] = "squares" if built.value == "squares" else "non_square"
    # out_of_scope derives no character, so a stored character stands against it.
    derived_from = {
        "quad": framed, "grid": counted, "repeat_cells": counted,
        "character": built if built is not None and built.value != "out_of_scope" else None,
    }
    stored = {}
    for name, source in derived_from.items():
        claim = pick(getattr(annotation, name), prefer)
        if claim is not None and (
            source is None or prefer.index(claim.provenance) <= prefer.index(source.provenance)
        ):
            stored[name] = claim
    if "quad" in stored:
        view["quad"] = [list(point) for point in stored["quad"].value]
    if "grid" in stored:
        view["grid"] = stored["grid"].value.model_dump()
    if "repeat_cells" in stored:
        cells = stored["repeat_cells"].value
        view["repeat_cells"] = list(cells) if cells is not None else None
    if "character" in stored:
        view["character"] = stored["character"].value
    return view


if __name__ == "__main__":
    # Regenerates the committed schema: python scripts/eval/qrep_eval/annotation.py
    out = Path(__file__).resolve().parents[3] / "corpus" / "schema" / "annotation.schema.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(schema_text(), encoding="utf-8", newline="\n")
    print(out)
