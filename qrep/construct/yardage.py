"""Yardage math: per-fabric quarter-yard purchase lines plus the backing line.

Backing is a dedicated line item ("backing, any 42-inch WOF fabric"), never
taken from the palette fabrics. One quarter yard = 9" = 72 eighths.
"""

from math import ceil

from pydantic import BaseModel, Field

from qrep.construct.plan import ConstructionPlan, CutPiece, StripSet
from qrep.model.schema import Quilt

QUARTER_YARD = 72  # eighths of an inch

BACKING_NAME = "backing, any 42-inch WOF fabric"


class YardageLine(BaseModel):
    fabric_id: str | None = Field(default=None, description="None for the backing line")
    name: str
    purpose: str = Field(default="top", description="top | binding | backing")
    length_needed: int = Field(ge=0, description="fabric length required, eighths")
    quarter_yards: int = Field(ge=0)

    @property
    def yards(self) -> float:
        return self.quarter_yards / 4


class YardageReport(BaseModel):
    strategy: str
    lines: list[YardageLine]


def backing_line(quilt: Quilt) -> YardageLine:
    """panels = ceil((width + margin) / WOF); length = panels x (height + margin)."""
    settings = quilt.settings
    panels = ceil((quilt.finished_width + settings.backing_margin) / settings.wof)
    length = panels * (quilt.finished_height + settings.backing_margin)
    return YardageLine(
        fabric_id=None,
        name=BACKING_NAME,
        purpose="backing",
        length_needed=length,
        quarter_yards=ceil(length / QUARTER_YARD),
    )


def _line_from_area(fabric_id: str, name: str, purpose: str, area: int, wof: int) -> YardageLine:
    length = ceil(area / wof) if area else 0
    return YardageLine(
        fabric_id=fabric_id,
        name=name,
        purpose=purpose,
        length_needed=length,
        quarter_yards=ceil(length / QUARTER_YARD) if length else 0,
    )


def compute_purchase_lines(quilt: Quilt, plan: "ConstructionPlan") -> YardageReport:
    """Human-facing purchase table: one line per palette fabric for the top
    (center + borders, strip sets included), a dedicated line per binding
    fabric, and the backing line. Rounding happens per line, so this can
    exceed the aggregate compute_yardage totals that metrics use."""
    wof = quilt.settings.wof
    top_area: dict[str, int] = {f.id: 0 for f in quilt.palette.fabrics}
    binding_area: dict[str, int] = {}
    for piece in plan.cut_pieces:
        if piece.component == "binding":
            binding_area[piece.fabric_id] = (
                binding_area.get(piece.fabric_id, 0) + piece.cut_area
            )
        elif piece.source == "rotary":
            top_area[piece.fabric_id] += piece.cut_area
    for strip_set in plan.strip_sets:
        strip_area = strip_set.strip_cut_width * wof
        for fabric_id in strip_set.sequence:
            top_area[fabric_id] += strip_area * strip_set.sets_needed
    lines = []
    for fabric in quilt.palette.fabrics:
        if top_area[fabric.id]:
            lines.append(
                _line_from_area(fabric.id, f"{fabric.name}", "top", top_area[fabric.id], wof)
            )
    for fabric in quilt.palette.fabrics:
        if fabric.id in binding_area:
            lines.append(
                _line_from_area(
                    fabric.id, f"Binding - {fabric.name}", "binding", binding_area[fabric.id], wof
                )
            )
    lines.append(backing_line(quilt))
    return YardageReport(strategy=plan.strategy, lines=lines)


def cut_area_by_fabric(
    quilt: Quilt, cut_pieces: list[CutPiece], strip_sets: list[StripSet]
) -> dict[str, int]:
    """Fabric consumed, eighths squared. strip_set-sourced pieces are excluded
    (their fabric arrives through the WOF strips of the sets)."""
    wof = quilt.settings.wof
    area: dict[str, int] = {f.id: 0 for f in quilt.palette.fabrics}
    for piece in cut_pieces:
        if piece.source == "rotary":
            area[piece.fabric_id] += piece.cut_area
    for strip_set in strip_sets:
        strip_area = strip_set.strip_cut_width * wof
        for fabric_id in strip_set.sequence:
            area[fabric_id] += strip_area * strip_set.sets_needed
    return area


def compute_yardage_from_components(
    quilt: Quilt, strategy: str, cut_pieces: list[CutPiece], strip_sets: list[StripSet]
) -> YardageReport:
    """Length per fabric = ceil(cut area / WOF), rounded up to the quarter yard.

    Strip strategies buy whole WOF strips, so their yardage legitimately
    exceeds historical's; cut areas are reported, never asserted equal.
    """
    wof = quilt.settings.wof
    areas = cut_area_by_fabric(quilt, cut_pieces, strip_sets)
    lines = []
    for fabric in quilt.palette.fabrics:
        area = areas[fabric.id]
        length = ceil(area / wof) if area else 0
        lines.append(
            YardageLine(
                fabric_id=fabric.id,
                name=fabric.name,
                length_needed=length,
                quarter_yards=ceil(length / QUARTER_YARD) if length else 0,
            )
        )
    lines.append(backing_line(quilt))
    return YardageReport(strategy=strategy, lines=lines)


def compute_yardage(quilt: Quilt, plan: ConstructionPlan) -> YardageReport:
    return compute_yardage_from_components(
        quilt, plan.strategy, plan.cut_pieces, plan.strip_sets
    )
