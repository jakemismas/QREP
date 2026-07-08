"""Construction plan data model.

A strategy is a pure function Quilt -> ConstructionPlan; running the same
strategy on the same quilt twice yields equal serialized plans. All lengths
are integer eighths (see qrep.model.units); areas are eighths squared.
"""

from typing import Literal

from pydantic import BaseModel, Field

HEURISTIC_LABEL = "rough heuristic"

Component = Literal["center", "border", "binding"]

# How a piece gets cut: "rotary" pieces are cut individually; "strip_set"
# pieces arrive pre-joined inside crosscut segments, so yardage counts their
# fabric through the strip sets, not through these lines.
Source = Literal["rotary", "strip_set"]


class CutPiece(BaseModel):
    """One line of the cut list: identical pieces grouped with a quantity."""

    fabric_id: str
    component: Component
    source: Source = "rotary"
    finished_width: int = Field(gt=0)
    finished_height: int = Field(gt=0)
    cut_width: int = Field(gt=0)
    cut_height: int = Field(gt=0)
    quantity: int = Field(gt=0)
    label: str

    @property
    def finished_area(self) -> int:
        return self.finished_width * self.finished_height * self.quantity

    @property
    def cut_area(self) -> int:
        return self.cut_width * self.cut_height * self.quantity


class StripSet(BaseModel):
    """One distinct WOF strip set: strips sewn lengthwise, then crosscut."""

    id: str
    sequence: list[str] = Field(description="fabric ids, strip order top to bottom")
    strip_cut_width: int = Field(gt=0, description="cut width of each WOF strip, eighths")
    segment_cut_width: int = Field(gt=0, description="crosscut width, eighths")
    segments_needed: int = Field(gt=0)
    segments_per_set: int = Field(gt=0, description="floor(WOF / segment width)")
    sets_needed: int = Field(gt=0)


class AssemblyStep(BaseModel):
    number: int = Field(gt=0)
    title: str
    detail: str = ""
    substeps: list[str] = Field(default_factory=list)


class PlanMetrics(BaseModel):
    piece_count: int = Field(description="pieces in the finished top (center + borders)")
    cut_count: int = Field(description="rotary-cut operations, incl. binding strips")
    seam_count: int
    strip_set_count: int = Field(description="physical strip sets sewn (0 for non-strip)")
    waste: float = Field(description="(purchased - cut area) / purchased, palette fabrics")
    bias_percent: float = Field(
        default=0.0,
        description="fraction of cut edges off-grain; 0.0 for all v1 rectilinear strategies",
    )
    difficulty: int = Field(description=f"{HEURISTIC_LABEL}: round(log10(pieces) + seams/sqft)")
    time_minutes: int = Field(
        description=f"{HEURISTIC_LABEL}: pieces x 1.5 min + strip-set ops x 10 min"
    )
    heuristic_label: str = HEURISTIC_LABEL


class ConstructionPlan(BaseModel):
    strategy: str
    quilt_name: str
    cut_pieces: list[CutPiece]
    strip_sets: list[StripSet] = Field(default_factory=list)
    assembly: list[AssemblyStep]
    metrics: PlanMetrics

    def top_finished_area(self) -> int:
        """Summed finished area of the pieces that make up the top (no binding)."""
        return sum(p.finished_area for p in self.cut_pieces if p.component != "binding")
