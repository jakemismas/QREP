"""Yardage math: one purchase line per fabric use, built from the cutting layout.

Every top-fabric line is the sum of its strip plans (MATH.md F2 to F4) plus the
stated margin (F5), never an area estimate. Binding and backing are dedicated
lines from qrep.construct.finishing; backing is named from the backing width
setting, never taken from the palette fabrics. One quarter yard = 9" = 72
eighths.
"""

from pydantic import BaseModel, Field

from qrep.construct.cutting import (
    border_bands,
    purchase_increments,
    strip_set_plan,
    strip_yield,
    top_fabric_plan,
)
from qrep.construct.finishing import backing_plan, quilt_binding_plan, wide_back_plan
from qrep.construct.plan import ConstructionPlan, CutPiece, StripSet
from qrep.model.schema import Quilt
from qrep.model.units import format_inches

QUARTER_YARD = 72  # eighths of an inch
BORDER_JOIN_LOSS = 4  # MATH.md 1.3, j: a straight 1/4 in seam uses 1/2 in per join

# The fields marked exclude stay out of model_dump, so the bridge response
# keeps its v2 shape (qrep/contract.py); the bridge, web and PDF read
# quarter_yards until they move to increments.


class YardageLine(BaseModel):
    fabric_id: str | None = Field(default=None, description="None for the backing line")
    name: str
    purpose: str = Field(default="top", description="top | binding | backing | wide_back")
    length_needed: int = Field(ge=0, description="plan length before any allowance, eighths")
    purchase: int = Field(ge=0, exclude=True, description="length plus margin or allowance")
    increments: int = Field(ge=0, exclude=True, description="purchase in purchase increments")
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
    top_margin: int = Field(ge=0, exclude=True, description="percent added to top fabrics")
    increment: int = Field(gt=0, exclude=True, description="purchase rounding step, eighths")


def _line(
    fabric_id: str | None, name: str, purpose: str, length: int, purchase: int, increment: int
) -> YardageLine:
    return YardageLine(
        fabric_id=fabric_id,
        name=name,
        purpose=purpose,
        length_needed=length,
        purchase=purchase,
        increments=purchase_increments(purchase, increment),
        quarter_yards=purchase_increments(purchase, QUARTER_YARD),
    )


def backing_line(quilt: Quilt) -> YardageLine:
    settings = quilt.settings
    plan = backing_plan(quilt.finished_width, quilt.finished_height, settings)
    fabric = format_inches(settings.backing_width)
    length = format_inches(plan.panel_length)
    if plan.panels == 1:
        layout = f"one piece {length} long"
    else:
        layout = f"({plan.panels}) panels {length} long, {plan.seams} seams"
    return _line(
        None,
        f"backing, {fabric} wide fabric: {layout}",
        "backing",
        plan.length_needed,
        plan.purchase,
        settings.purchase_increment,
    )


def wide_back_line(quilt: Quilt) -> YardageLine | None:
    settings = quilt.settings
    plan = wide_back_plan(quilt.finished_width, quilt.finished_height, settings)
    if plan is None:
        return None
    return _line(
        None,
        f"wide backing, {format_inches(plan.fabric_width)} wide fabric: "
        f"one piece {format_inches(plan.length_needed)} long",
        "wide_back",
        plan.length_needed,
        plan.purchase,
        settings.purchase_increment,
    )


def top_plan_lengths(
    quilt: Quilt, cut_pieces: list[CutPiece], strip_sets: list[StripSet]
) -> dict[str, list[int]]:
    """Each palette fabric's strip-plan lengths, eighths: F2 per rotary center
    cut line, F3 per strip set and F4 per border band. Border cut pieces are
    skipped because F4 replans the bands as joined strips."""
    usable = quilt.settings.wof
    lengths: dict[str, list[int]] = {f.id: [] for f in quilt.palette.fabrics}
    for piece in cut_pieces:
        if piece.component == "center" and piece.source == "rotary":
            plan = strip_yield(
                piece.quantity, piece.cut_width, piece.cut_height, usable, BORDER_JOIN_LOSS
            )
            lengths[piece.fabric_id].append(plan.length)
    for strip_set in strip_sets:
        plan = strip_set_plan(
            strip_set.segments_needed, strip_set.segment_cut_width, strip_set.sequence, usable
        )
        for fabric_id, strips in plan.fabric_strips.items():
            lengths[fabric_id].append(strips * strip_set.strip_cut_width)
    bands = border_bands(
        quilt.center.width,
        quilt.center.height,
        [band.width for band in quilt.borders],
        usable,
        BORDER_JOIN_LOSS,
        quilt.settings.seam_allowance,
    )
    for band, plan in zip(quilt.borders, bands, strict=True):
        lengths[band.fabric_id].append(plan.length)
    return lengths


def purchase_lines(
    quilt: Quilt, strategy: str, cut_pieces: list[CutPiece], strip_sets: list[StripSet]
) -> YardageReport:
    """The one purchase-line builder: a top line per palette fabric the top
    uses, the binding line, then the backing line, with the wide-back
    alternative when F11 offers it. Each line rounds up on its own."""
    settings = quilt.settings
    increment = settings.purchase_increment
    lengths = top_plan_lengths(quilt, cut_pieces, strip_sets)
    lines = []
    for fabric in quilt.palette.fabrics:
        if lengths[fabric.id]:
            plan = top_fabric_plan(lengths[fabric.id], settings.top_margin, increment)
            lines.append(
                _line(fabric.id, fabric.name, "top", plan.length_needed, plan.purchase, increment)
            )
    binding = quilt_binding_plan(quilt)
    binding_name = next(f.name for f in quilt.palette.fabrics if f.id == quilt.binding.fabric_id)
    # Binding has no allowance beyond its extra length and join-aware count (MATH.md 1.4).
    lines.append(
        _line(
            quilt.binding.fabric_id,
            f"Binding - {binding_name}",
            "binding",
            binding.length_needed,
            binding.length_needed,
            increment,
        )
    )
    lines.append(backing_line(quilt))
    return YardageReport(
        strategy=strategy,
        lines=lines,
        wide_back=wide_back_line(quilt),
        top_margin=settings.top_margin,
        increment=increment,
    )


def compute_purchase_lines(quilt: Quilt, plan: ConstructionPlan) -> YardageReport:
    """Human-facing purchase table that the CLI, the metrics and every exporter read."""
    return purchase_lines(quilt, plan.strategy, plan.cut_pieces, plan.strip_sets)


def cut_area_by_fabric(
    quilt: Quilt, cut_pieces: list[CutPiece], strip_sets: list[StripSet]
) -> dict[str, int]:
    """Fabric consumed, eighths squared, for the waste metric only.
    strip_set-sourced pieces are excluded (their fabric arrives through the
    WOF strips of the sets)."""
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
