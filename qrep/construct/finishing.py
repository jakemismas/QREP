"""Finishing math: binding, backing, wide-back and batting (MATH.md F6 to F12).

One function per purchase line, so the cut list, the assembly steps, the
purchase table and the PDF all read the same numbers. Every length is integer
eighths and every division rounds up in integers, never through a float.
"""

from typing import Literal

from pydantic import BaseModel

from qrep.model.schema import Quilt, Settings

# A 1/2 in seam allowance on each of two panels: each backing seam covers
# 1 in less than the two widths it joins (MATH.md F9).
BACKING_SEAM_LOSS = 8

# (name, width, height) in eighths, smallest first; MATH.md F12. Package sizes
# vary by brand, and only these five were verified.
BATTING_PACKAGES = (
    ("crib", 360, 480),
    ("twin", 576, 720),
    ("full", 720, 768),
    ("queen", 720, 864),
    ("king", 992, 960),
)


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


class BindingPlan(BaseModel):
    total_length: int  # T = perimeter + binding_extra
    strips: int
    length_needed: int  # strips x strip width; binding has no allowance
    increments: int


class BackingPlan(BaseModel):
    panels: int
    panel_length: int  # cut length of each panel
    seams: Literal["vertical", "horizontal"]
    length_needed: int  # panels x panel_length, before the allowance
    purchase: int  # length_needed + the pieced or one-piece allowance
    increments: int


class WideBackPlan(BaseModel):
    fabric_width: int
    length_needed: int
    purchase: int
    increments: int


class BattingPlan(BaseModel):
    width: int
    height: int
    package: str | None  # None when no package covers it
    package_width: int | None
    package_height: int | None


def binding_strip_count(total_length: int, usable_width: int, strip_width: int) -> int:
    """F7: each diagonal join, the closing one included, uses one strip width,
    so a loop of n strips supplies n x (U - w)."""
    if strip_width >= usable_width:
        raise ValueError(
            f"binding strip width {strip_width} must be narrower than the usable width "
            f"{usable_width}"
        )
    return _ceil_div(total_length, usable_width - strip_width)


def binding_plan(width: int, height: int, strip_width: int, settings: Settings) -> BindingPlan:
    total = 2 * (width + height) + settings.binding_extra
    strips = binding_strip_count(total, settings.wof, strip_width)
    length = strips * strip_width
    return BindingPlan(
        total_length=total,
        strips=strips,
        length_needed=length,
        increments=_ceil_div(length, settings.purchase_increment),
    )


def quilt_binding_plan(quilt: Quilt) -> BindingPlan:
    return binding_plan(
        quilt.finished_width, quilt.finished_height, quilt.binding.strip_width, quilt.settings
    )


def backing_panel_count(dimension: int, fabric_width: int) -> int:
    """F9: n panels of width B joined with 1/2 in seams cover n x B - (n - 1) in."""
    if fabric_width <= BACKING_SEAM_LOSS:
        raise ValueError(
            f"backing fabric width {fabric_width} must exceed the seam loss {BACKING_SEAM_LOSS}"
        )
    if dimension <= fabric_width:
        return 1
    return _ceil_div(dimension - BACKING_SEAM_LOSS, fabric_width - BACKING_SEAM_LOSS)


def _backing_allowance(panels: int, settings: Settings) -> int:
    if panels >= 2:
        return settings.backing_pieced_allowance
    return settings.backing_one_piece_allowance


def backing_plan(width: int, height: int, settings: Settings) -> BackingPlan:
    """F8 to F10: both seam orientations, the smaller total wins.

    Totals, not raw lengths, are compared so a one-piece backing wins when its
    smaller allowance makes it cheaper (V-BACK-14); a tie keeps vertical seams.
    """
    backing_w = width + settings.backing_margin
    backing_h = height + settings.backing_margin
    fabric = settings.backing_width
    vertical = (backing_panel_count(backing_w, fabric), backing_h, "vertical")
    horizontal = (backing_panel_count(backing_h, fabric), backing_w, "horizontal")

    def total(layout: tuple[int, int, str]) -> int:
        panels, panel_length, _ = layout
        return panels * panel_length + _backing_allowance(panels, settings)

    panels, panel_length, seams = (
        horizontal if total(horizontal) < total(vertical) else vertical
    )
    length = panels * panel_length
    purchase = length + _backing_allowance(panels, settings)
    return BackingPlan(
        panels=panels,
        panel_length=panel_length,
        seams=seams,
        length_needed=length,
        purchase=purchase,
        increments=_ceil_div(purchase, settings.purchase_increment),
    )


def wide_back_plan(width: int, height: int, settings: Settings) -> WideBackPlan | None:
    """F11: one piece of wide fabric, offered only when the pieced backing
    needs two or more panels and one backing side fits within the wide width."""
    if backing_plan(width, height, settings).panels < 2:
        return None
    backing_w = width + settings.backing_margin
    backing_h = height + settings.backing_margin
    wide = settings.wide_back_width
    if backing_w <= wide and backing_h <= wide:
        length = min(backing_w, backing_h)
    elif backing_w <= wide:
        length = backing_h
    elif backing_h <= wide:
        length = backing_w
    else:
        return None
    purchase = length + settings.backing_one_piece_allowance
    return WideBackPlan(
        fabric_width=wide,
        length_needed=length,
        purchase=purchase,
        increments=_ceil_div(purchase, settings.purchase_increment),
    )


def batting_plan(width: int, height: int, settings: Settings) -> BattingPlan:
    """F12: the backing's size, and the smallest package that covers it in
    either orientation."""
    batting_w = width + settings.backing_margin
    batting_h = height + settings.backing_margin
    for name, pack_w, pack_h in BATTING_PACKAGES:
        if (batting_w <= pack_w and batting_h <= pack_h) or (
            batting_w <= pack_h and batting_h <= pack_w
        ):
            return BattingPlan(
                width=batting_w,
                height=batting_h,
                package=name,
                package_width=pack_w,
                package_height=pack_h,
            )
    return BattingPlan(
        width=batting_w, height=batting_h, package=None, package_width=None, package_height=None
    )


def _package_size(width: int, height: int) -> str:
    # Package sizes are whole inches, so this prints no fractions.
    return f"{width // 8} x {height // 8} in"


def batting_package_text(plan: BattingPlan) -> str:
    if plan.package is None:
        name, width, height = BATTING_PACKAGES[-1]
        return f"larger than a {name} package ({_package_size(width, height)})"
    return f"{plan.package} package ({_package_size(plan.package_width, plan.package_height)})"
