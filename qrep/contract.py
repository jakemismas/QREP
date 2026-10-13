"""Bridge v2 contract: the Python half of web/src/engine/contract.ts.

The web worker checks CONTRACT_VERSION at boot through
bridge.contract_version() and refuses to boot on a mismatch, so a cached
wheel never serves a page built for another contract. Any change to the
bridge's request or response shapes bumps the version here and in
contract.ts in the same commit; tests/test_bridge.py fails when the two
literals differ (plan section 4.2), and when a model's field names differ
from its TS interface.

The models are strict: a field of the wrong type is refused rather than
coerced (true is not a count, "10" is not a coordinate), and an unknown
field is refused, so a misspelled field never reads as absent. The frame,
band and count models stand on their own, because D3a's corpus annotations
reuse them, so the UI, the eval and the corpus share one shape.

Lengths are integer eighths of an inch; coordinates are staged-image pixels.
Like the bridge, this module must never import cv2, typer or click.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from qrep.model.schema import Quilt

CONTRACT_VERSION = 3

# The read's optional fabric count (SPEC.md section 12.1). Below 2 there is
# nothing to tell apart; above 12 is a scrappy quilt (SPEC.md section 3), which
# the read itself refuses as too_many_fabrics.
FABRICS_MIN = 2
FABRICS_MAX = 12

# Every v2 result names its outcome; a refusal or hold carries its reason.
OUTCOMES = ("read", "held", "refused", "sized", "pattern_ready")


class _Shape(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class Point(_Shape):
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class Corners(_Shape):
    top_left: Point
    top_right: Point
    bottom_right: Point
    bottom_left: Point


class BorderBand(_Shape):
    """One border band, its width in finished squares (need not be whole)."""

    width_squares: float = Field(gt=0, allow_inf_nan=False)


class FieldFrame(_Shape):
    """The four corners of the pieced field."""

    kind: Literal["field"]
    corners: Corners


class OuterEdgeFrame(_Shape):
    """The four outer-edge corners plus the border bands from the outside in,
    for a quilt whose field corners are hidden; the engine derives the field."""

    kind: Literal["outer_edge"]
    corners: Corners
    bands: list[BorderBand]


Frame = Annotated[FieldFrame | OuterEdgeFrame, Field(discriminator="kind")]


class Counts(_Shape):
    """Counts in quilter units: blocks across and down, squares per block."""

    blocks_across: int = Field(ge=1)
    blocks_down: int = Field(ge=1)
    squares_per_block_across: int = Field(ge=1)
    squares_per_block_down: int = Field(ge=1)


class ReadRequest(_Shape):
    """The confirmed read's request (SPEC.md sections 4 and 12.1).

    token is the staged image (a MEMFS path in the browser). The frame's
    corners are pixels of that staged crop, and crop_offset is the crop's
    top-left corner in the decoded photo (#101).
    """

    token: str = Field(min_length=1)
    frame: Frame
    crop_offset: Point
    counts: Counts
    fabric_count: int | None = Field(default=None, ge=FABRICS_MIN, le=FABRICS_MAX)

    @model_validator(mode="after")
    def _offset_inside_the_photo(self):
        if self.crop_offset.x < 0 or self.crop_offset.y < 0:
            raise ValueError("crop_offset must not be negative")
        return self


class Reason(_Shape):
    """Why a result was held or refused: a stable code and a plain message."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


def _check_reason(result, success: tuple[str, ...]):
    succeeded = result.outcome in success
    if succeeded == (result.reason is not None):
        needs = "carries no reason" if succeeded else "needs a reason"
        raise ValueError(f"a {result.outcome} result {needs}")
    return result


Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class FabricCount(_Shape):
    """The fabric count the read used: the one you set (source user, at 1.0)
    or the read's own suggestion, with that suggestion's confidence."""

    value: int = Field(ge=1)
    source: Literal["user", "suggestion"]
    confidence: Confidence


class FabricRead(_Shape):
    """A palette fabric as the read found it: its model id and the confidence
    of its color."""

    fabric_id: str = Field(min_length=1)
    confidence: Confidence


class StripRead(_Shape):
    """One side strip of a border band (band 0 is the outermost): the fabric
    it reads as and the confidence of that label."""

    band: int = Field(ge=0)
    side: Literal["top", "right", "bottom", "left"]
    fabric_id: str = Field(min_length=1)
    confidence: Confidence


class VoteChange(_Shape):
    """A square the block vote changed: the fabric it read, the block
    majority it took, and the vote's confidence."""

    row: int = Field(ge=0)
    col: int = Field(ge=0)
    read: str = Field(min_length=1)
    voted: str = Field(min_length=1)
    confidence: Confidence


class RepeatBreak(_Shape):
    """A confidently read square that differs from its block majority. It
    keeps its read, so a deliberate variation is never voted away."""

    row: int = Field(ge=0)
    col: int = Field(ge=0)
    read: str = Field(min_length=1)
    majority: str = Field(min_length=1)
    confidence: Confidence


class Repeat(_Shape):
    """The repeat of the read squares, in squares: a whole multiple of the
    block period you confirmed."""

    across: int = Field(ge=1)
    down: int = Field(ge=1)


class ReadDetails(_Shape):
    """What the read found beyond the model, each CV value with its
    confidence (SPEC.md section 4). corners_source says whether you set the
    corners or kept a suggestion, so evaluation can tell corner error from
    read error."""

    corners_source: Literal["user", "suggestion"]
    fabric_count: FabricCount
    fabrics: list[FabricRead]
    strips: list[StripRead]
    repeat: Repeat
    vote_changes: list[VoteChange]
    repeat_breaks: list[RepeatBreak]


class ReadResult(_Shape):
    outcome: Literal["read", "held", "refused"]
    model: Quilt | None = None
    details: ReadDetails | None = None
    reason: Reason | None = None

    @model_validator(mode="after")
    def _consistent(self):
        read = self.outcome == "read"
        if read != (self.model is not None) or read != (self.details is not None):
            raise ValueError(
                "a read result carries the model and its details, and only a read result does"
            )
        return _check_reason(self, ("read",))


SizeSource = Literal["typed", "preset", "default"]


class SizeRequest(_Shape):
    """The size you set: typed (a width, a height or both, in eighths), a
    preset by name, or the default, which sets nothing."""

    source: SizeSource
    width: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    preset: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _matches_source(self):
        if self.source == "typed" and self.width is None and self.height is None:
            raise ValueError("a typed size needs a width or a height")
        if self.source != "typed" and (self.width is not None or self.height is not None):
            raise ValueError(f"a {self.source} size takes no width or height")
        if (self.source == "preset") != (self.preset is not None):
            raise ValueError("a preset name goes with source preset, and only with it")
        return self


class SizeBasis(_Shape):
    """How the finished size was set: its source, the size you asked for
    (null for a default) and the size achieved, in eighths."""

    source: SizeSource
    requested_width: int | None = Field(gt=0)
    requested_height: int | None = Field(gt=0)
    achieved_width: int = Field(gt=0)
    achieved_height: int = Field(gt=0)


class SizeResult(_Shape):
    outcome: Literal["sized"]
    model: Quilt
    basis: SizeBasis


class FabricLine(_Shape):
    """A palette fabric: the letter the PDF labels it with, its name and the
    yards the top needs. The interim booklet's label is the model's fabric
    id, so the screen and the PDF name the same fabric."""

    letter: str = Field(min_length=1)
    fabric_id: str
    name: str
    yards: float = Field(ge=0, allow_inf_nan=False)


class PurchaseLine(_Shape):
    """A binding, backing or wide-back line; fabric_id is null for backing."""

    fabric_id: str | None
    name: str
    yards: float = Field(ge=0, allow_inf_nan=False)


class BattingSize(_Shape):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class PatternSummary(_Shape):
    """What Your pattern shows, from the same data as the PDF (PS-40).

    size_basis is null when the model records none. wide_back is null when
    no wide-back line was computed. strip_width and backing_width are the
    two width-of-fabric assumptions, in eighths; uncertain_squares counts
    squares read below the uncertain mark.
    """

    finished_width: int = Field(gt=0)
    finished_height: int = Field(gt=0)
    size_basis: SizeBasis | None
    method: str = Field(min_length=1)
    method_reason: str = Field(min_length=1)
    fabrics: list[FabricLine]
    binding: list[PurchaseLine]
    backing: PurchaseLine
    wide_back: PurchaseLine | None
    batting: BattingSize
    strip_width: int = Field(gt=0)
    backing_width: int = Field(gt=0)
    uncertain_squares: int = Field(ge=0)


class PatternResult(_Shape):
    """The one pattern download: the PDF, base64, with its summary."""

    outcome: Literal["pattern_ready", "refused"]
    # An empty PDF is no pattern, so a ready result never carries one.
    pdf_b64: str | None = Field(default=None, min_length=1)
    summary: PatternSummary | None = None
    reason: Reason | None = None

    @model_validator(mode="after")
    def _consistent(self):
        ready = self.outcome == "pattern_ready"
        if ready != (self.pdf_b64 is not None) or ready != (self.summary is not None):
            raise ValueError("a pattern_ready result carries the PDF and its summary, and only it")
        return _check_reason(self, ("pattern_ready",))


# Each model mirrors one TS interface in web/src/engine/contract.ts.
CONTRACT_MODELS = (
    Point,
    Corners,
    BorderBand,
    FieldFrame,
    OuterEdgeFrame,
    Counts,
    ReadRequest,
    Reason,
    FabricCount,
    FabricRead,
    StripRead,
    VoteChange,
    RepeatBreak,
    Repeat,
    ReadDetails,
    ReadResult,
    SizeRequest,
    SizeBasis,
    SizeResult,
    FabricLine,
    PurchaseLine,
    BattingSize,
    PatternSummary,
    PatternResult,
)
