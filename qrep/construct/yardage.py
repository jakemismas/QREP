"""Yardage math: per-fabric quarter-yard purchase lines plus the backing line.

Backing is a dedicated line item named from the backing width setting, never
taken from the palette fabrics; its math lives in qrep.construct.finishing.
One quarter yard = 9" = 72 eighths.
"""

from math import ceil

from pydantic import BaseModel, Field

from qrep.construct.finishing import backing_plan, wide_back_plan
from qrep.construct.plan import ConstructionPlan, CutPiece, StripSet
from qrep.model.schema import Quilt
from qrep.model.units import format_inches

QUARTER_YARD = 72  # eighths of an inch


class YardageLine(BaseModel):
    fabric_id: str | None = Field(default=None, description="None for the backing line")
    name: str
    purpose: str = Field(default="top", description="top | binding | backing | wide_back")
    length_needed: int = Field(ge=0, description="fabric length required, eighths")
    quarter_yards: int = Field(ge=0)

    @property
    def yards(self) -> float:
        return self.quarter_yards / 4


class YardageReport(BaseModel):
    strategy: str
    lines: list[YardageLine]
    wide_back: YardageLine | None = Field(
        default=None,
        description="one piece of wide fabric that replaces the pieced backing line; "
        "set only when MATH.md F11 offers it",
    )


# The line model and format_yards speak quarter yards, so the purchase lines
# round to QUARTER_YARD; the finishing plans also report increments of
# settings.purchase_increment.


def backing_line(quilt: Quilt) -> YardageLine:
    plan = backing_plan(quilt.finished_width, quilt.finished_height, quilt.settings)
    fabric = format_inches(quilt.settings.backing_width)
    length = format_inches(plan.panel_length)
    if plan.panels == 1:
        layout = f"one piece {length} long"
    else:
        layout = f"({plan.panels}) panels {length} long, {plan.seams} seams"
    return YardageLine(
        fabric_id=None,
        name=f"backing, {fabric} wide fabric: {layout}",
        purpose="backing",
        length_needed=plan.length_needed,
        quarter_yards=-(-plan.purchase // QUARTER_YARD),
    )


def wide_back_line(quilt: Quilt) -> YardageLine | None:
    plan = wide_back_plan(quilt.finished_width, quilt.finished_height, quilt.settings)
    if plan is None:
        return None
    return YardageLine(
        fabric_id=None,
        name=(
            f"wide backing, {format_inches(plan.fabric_width)} wide fabric: "
            f"one piece {format_inches(plan.length_needed)} long"
        ),
        purpose="wide_back",
        length_needed=plan.length_needed,
        quarter_yards=-(-plan.purchase // QUARTER_YARD),
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
    return YardageReport(strategy=plan.strategy, lines=lines, wide_back=wide_back_line(quilt))


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
