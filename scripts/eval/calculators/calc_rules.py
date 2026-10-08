"""MATH.md section 2 formulas, parameterized so the D2 harness can label calculator differences.

Lengths enter and leave as inches in Fractions and are computed in integer eighths (1 in = 8 e),
as MATH.md section 1.2 requires; yards come back as Fractions. The one exception is the
Quilter's Paradise rounding (qp_backing_display, qp_strip_yards), which deliberately repeats
that site's IEEE double arithmetic, because its float fraction decides some displayed results
(MATH.md 5.2, king 110 x 108).

Parameter sets that reproduce each source live in BACKING_SETS, BINDING_SETS, WIDE_SETS and
BORDER_SETS; pass one as keyword arguments and override single values as needed.

Stdlib only, because the test also runs under Pyodide.
"""

from __future__ import annotations

import math
import re
from fractions import Fraction
from types import MappingProxyType

__all__ = [
    "BACKING_SETS",
    "BINDING_SETS",
    "BORDER_SETS",
    "NO_PACKAGE_LABEL",
    "PACKAGES",
    "SOURCES",
    "WIDE_SETS",
    "backing",
    "batting",
    "binding",
    "border",
    "border_join_count",
    "border_pair_strips",
    "ceil_div",
    "from_eighths",
    "mfqs_backing",
    "panels",
    "purchase_yards",
    "qc_border",
    "qp_backing_display",
    "qp_strip_yards",
    "sewbecca_border",
    "stitchdesk_backing",
    "stitchdesk_binding",
    "to_eighths",
    "wide_back",
]

E_PER_INCH = 8
QUARTER_YARD_E = 72
EIGHTH_YARD_E = 36
HALF_INCH_E = 4  # cut = finished + 1/2 in; also j, the straight-join loss (MATH.md 1.3)

# MATH.md F12, in the order they are tried; (name, width, length) in inches.
PACKAGES = (
    ("crib", 45, 60),
    ("twin", 72, 90),
    ("full", 90, 96),
    ("queen", 90, 108),
    ("king", 124, 120),
)
NO_PACKAGE_LABEL = "larger than a king package (124 x 120 in)"


# ---------------------------------------------------------------------------------------------
# Integer eighths
# ---------------------------------------------------------------------------------------------


def to_eighths(value: int | Fraction | str) -> int:
    """Inches as whole eighths; anything finer is refused rather than rounded."""
    eighths = Fraction(value) * E_PER_INCH
    if eighths.denominator != 1:
        raise ValueError(f"{value!r} in is not a whole number of eighths of an inch")
    return eighths.numerator


def from_eighths(eighths: int) -> Fraction:
    return Fraction(eighths, E_PER_INCH)


def ceil_div(a: int, b: int) -> int:
    """ceil(a / b) in integers, the MATH.md 1.2 form (a + b - 1) // b."""
    if b <= 0:
        raise ValueError(f"ceil_div needs a positive divisor, got {b}")
    return (a + b - 1) // b


def purchase_yards(length_e: int, increment: str) -> Fraction:
    """Round a purchase length up to the increment: "quarter" (72 e) or "eighth" (36 e)."""
    if increment == "quarter":
        return Fraction(ceil_div(length_e, QUARTER_YARD_E), 4)
    if increment == "eighth":
        return Fraction(ceil_div(length_e, EIGHTH_YARD_E), 8)
    raise ValueError(f"unknown increment {increment!r}; expected 'quarter' or 'eighth'")


# ---------------------------------------------------------------------------------------------
# Quilter's Paradise rounding, emulated in IEEE doubles (Python floats are the same doubles JS
# uses, and + - * / round identically)
# ---------------------------------------------------------------------------------------------

_LADDER_STEPS = (
    Fraction(1, 8),
    Fraction(1, 4),
    Fraction(1, 3),
    Fraction(3, 8),
    Fraction(1, 2),
    Fraction(5, 8),
    Fraction(2, 3),
    Fraction(3, 4),
    Fraction(7, 8),
)
# The backing page compares with the JS values 1/3 and 2/3; the binding and border pages with the
# decimals 0.33 and 0.67. The difference shows on 12 in of strips (12 / 36 = 0.3333 > 0.33).
_QP_BACKING_LIMITS = (0.125, 0.25, 1 / 3, 0.375, 0.5, 0.625, 2 / 3, 0.75, 0.875)
_QP_STRIP_LIMITS = (0.125, 0.25, 0.33, 0.375, 0.5, 0.625, 0.67, 0.75, 0.875)


def _qp_round(yards: float, limits: tuple[float, ...]) -> Fraction:
    whole = math.floor(yards)
    # Exact in doubles: removing the integer part of a double loses no bits.
    frac = yards - whole
    if frac == 0:
        return Fraction(whole)
    for limit, step in zip(limits, _LADDER_STEPS, strict=True):
        if frac <= limit:
            return whole + step
    return Fraction(whole + 1)


_JS_DECIMAL = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def _js_number(value: int | Fraction | str) -> float:
    """The double JS gets from a typed form value.

    A string goes through float(), which rounds a decimal exactly as JS's string-to-number does.
    A number must be whole eighths: k/8 is a dyadic rational, so its double is exact and equals
    what JS gets from the same value typed as a decimal.
    """
    if isinstance(value, str):
        text = value.strip()
        if not _JS_DECIMAL.fullmatch(text):
            raise ValueError(f"not a plain decimal form value: {value!r}")
        return float(text)
    return float(from_eighths(to_eighths(value)))


def qp_backing_display(
    width: int | Fraction | str,
    length: int | Fraction | str,
    bolt: int | Fraction | str,
    overage: int | Fraction | str,
) -> tuple[Fraction, int]:
    """Quilter's Paradise Backing and Batting for one orientation: (displayed yards, panels).

    Repeats its script: left = W + 2 overage; add a panel while left - bolt > 0, carrying
    1 in per seam; yards = (L + 2 overage) / 36 * panels, in that order, then its 1/8 ladder
    with 1/3 and 2/3 steps. The other orientation swaps width and length.
    """
    w, ln, fw, o = (_js_number(v) for v in (width, length, bolt, overage))
    if fw <= 1:
        raise ValueError(f"bolt width {bolt!r} must exceed the 1 in seam")
    left = w + 2 * o
    count = 1
    while True:
        togo = left - fw
        if togo <= 0:
            break
        left = togo + 1
        count += 1
    yards = (ln + 2 * o) / 36 * count
    return _qp_round(yards, _QP_BACKING_LIMITS), count


def qp_strip_yards(strips: int, strip_width: int | Fraction | str) -> Fraction:
    """Quilter's Paradise binding and border yards: (strips x strip width) / 36 in doubles, then
    the ladder with the decimal steps 0.33 and 0.67."""
    yards = (strips * _js_number(strip_width)) / 36
    return _qp_round(yards, _QP_STRIP_LIMITS)


# ---------------------------------------------------------------------------------------------
# F9 and F10: backing
# ---------------------------------------------------------------------------------------------


def panels(D: int | Fraction, B: int | Fraction, s: int | Fraction) -> int:
    """F9 panel count for a backing dimension D from fabric B wide, losing s per seam:
    1 if D <= B else ceil((D - s) / (B - s)). s = 0 is today's seam-blind ceil(D / B),
    s = 1/2 Nebraska's rule, s = 1 MATH.md's and Quilter's Paradise's."""
    d, b, seam = to_eighths(D), to_eighths(B), to_eighths(s)
    if d <= 0:
        raise ValueError(f"backing dimension must be positive, got {D}")
    if not 0 <= seam < b:
        raise ValueError(f"seam loss {s} must be at least 0 and less than the width {B}")
    if d <= b:
        return 1
    return ceil_div(d - seam, b - seam)


_KEEPS = ("least_total", "vertical_only")
_BACKING_INCREMENTS = ("quarter", "eighth", "qp_backing")


def backing(
    W: int | Fraction,
    L: int | Fraction,
    *,
    B: int | Fraction,
    overhang_per_side: int | Fraction,
    s: int | Fraction,
    allowance_pieced: int | Fraction,
    allowance_one: int | Fraction,
    increment: str,
    keep: str,
) -> dict:
    """F8 to F10 for both layouts and the kept one.

    Vertical seams: panels(Wb) panels, each Lb long. Horizontal seams: panels(Lb) panels, each
    Wb long. total = raw + allowance (pieced when 2 or more panels, else one-piece).
    keep "least_total" keeps the smaller total, vertical on a tie (F10); "vertical_only" is
    today's D-01. increment "qp_backing" shows Quilter's Paradise's displayed yards, which needs
    its own parameters: s = 1 and no allowance.

    Returns {backing_width, backing_length, vertical, horizontal, kept} where each layout is
    {panels, panel_length, raw, allowance, total, yards}, plus the kept layout's panels,
    panel_length, raw, allowance, total and yards at the top level.
    """
    if keep not in _KEEPS:
        raise ValueError(f"unknown keep {keep!r}; expected one of {_KEEPS}")
    if increment not in _BACKING_INCREMENTS:
        raise ValueError(f"unknown increment {increment!r}; expected one of {_BACKING_INCREMENTS}")
    if increment == "qp_backing" and (
        to_eighths(s) != E_PER_INCH or to_eighths(allowance_pieced) or to_eighths(allowance_one)
    ):
        raise ValueError(
            "qp_backing emulates Quilter's Paradise, which seams at 1 in and adds no allowance; "
            "its float order (L / 36 * panels) cannot carry one"
        )
    o_e = to_eighths(overhang_per_side)
    wb_e = to_eighths(W) + 2 * o_e
    lb_e = to_eighths(L) + 2 * o_e
    layouts = {}
    for name, across_e, along_e, typed in (
        ("vertical", wb_e, lb_e, (W, L)),
        ("horizontal", lb_e, wb_e, (L, W)),
    ):
        n = panels(from_eighths(across_e), B, s)
        raw_e = n * along_e
        allowance_e = to_eighths(allowance_pieced if n >= 2 else allowance_one)
        total_e = raw_e + allowance_e
        if increment == "qp_backing":
            # Its loop counts the same panels as F9 with s = 1: it stops at the first i with
            # Wb <= i (B - 1) + 1, which is ceil((Wb - 1) / (B - 1)) when Wb > B and 1 otherwise.
            yards, _count = qp_backing_display(typed[0], typed[1], B, overhang_per_side)
        else:
            yards = purchase_yards(total_e, increment)
        layouts[name] = {
            "panels": n,
            "panel_length": from_eighths(along_e),
            "raw": from_eighths(raw_e),
            "allowance": from_eighths(allowance_e),
            "total": from_eighths(total_e),
            "yards": yards,
        }
    if keep == "vertical_only":
        kept = "vertical"
    elif layouts["horizontal"]["total"] < layouts["vertical"]["total"]:
        kept = "horizontal"
    else:
        kept = "vertical"
    return {
        "backing_width": from_eighths(wb_e),
        "backing_length": from_eighths(lb_e),
        "vertical": layouts["vertical"],
        "horizontal": layouts["horizontal"],
        "kept": kept,
        **layouts[kept],
    }


# ---------------------------------------------------------------------------------------------
# F6 and F7: binding
# ---------------------------------------------------------------------------------------------

_BINDING_INCREMENTS = ("quarter", "eighth", "qp_strip")


def binding(
    W: int | Fraction,
    L: int | Fraction,
    *,
    U: int | Fraction,
    w: int | Fraction,
    extra: int | Fraction,
    join_aware: bool,
    increment: str,
) -> dict:
    """F6 and F7: T = 2 (W + L) + extra; strips = ceil(T / (U - w)) when join_aware, else
    ceil(T / U); length = strips x w; yards by increment ("quarter", "eighth", "qp_strip").

    Returns {binding_length (T), strips, length, yards, joined}, where joined is what the strips
    supply once sewn with diagonal joins, strips x (U - w), whichever count rule chose them.
    """
    if increment not in _BINDING_INCREMENTS:
        raise ValueError(f"unknown increment {increment!r}; expected one of {_BINDING_INCREMENTS}")
    t_e = 2 * (to_eighths(W) + to_eighths(L)) + to_eighths(extra)
    u_e, w_e = to_eighths(U), to_eighths(w)
    if not 0 < w_e < u_e:
        raise ValueError(f"strip width {w} must be positive and less than the usable width {U}")
    strips = ceil_div(t_e, u_e - w_e if join_aware else u_e)
    length_e = strips * w_e
    if increment == "qp_strip":
        yards = qp_strip_yards(strips, w)
    else:
        yards = purchase_yards(length_e, increment)
    return {
        "binding_length": from_eighths(t_e),
        "strips": strips,
        "length": from_eighths(length_e),
        "yards": yards,
        "joined": from_eighths(strips * (u_e - w_e)),
    }


# ---------------------------------------------------------------------------------------------
# F11 and F12: wide-back and batting
# ---------------------------------------------------------------------------------------------


def wide_back(
    W: int | Fraction,
    L: int | Fraction,
    *,
    BW: int | Fraction,
    overhang_per_side: int | Fraction,
    allowance: int | Fraction,
    increment: str,
    pieced_panels: int,
) -> dict | None:
    """F11: one piece of BW-wide fabric. None when the pieced backing has fewer than 2 panels
    (the line is omitted) or neither backing side fits within BW.

    Returns {length, allowance, total, yards}; length is the cut length along the bolt.
    """
    if pieced_panels < 2:
        return None
    o_e = to_eighths(overhang_per_side)
    wb_e = to_eighths(W) + 2 * o_e
    lb_e = to_eighths(L) + 2 * o_e
    bw_e = to_eighths(BW)
    if wb_e <= bw_e and lb_e <= bw_e:
        length_e = min(wb_e, lb_e)
    elif wb_e <= bw_e:
        length_e = lb_e
    elif lb_e <= bw_e:
        length_e = wb_e
    else:
        return None
    allowance_e = to_eighths(allowance)
    total_e = length_e + allowance_e
    return {
        "length": from_eighths(length_e),
        "allowance": from_eighths(allowance_e),
        "total": from_eighths(total_e),
        "yards": purchase_yards(total_e, increment),
    }


def batting(W: int | Fraction, L: int | Fraction, *, overhang_per_side: int | Fraction) -> dict:
    """F12: size (W + 2o) x (L + 2o) and the first package that covers it either way.

    Returns {width, length, package, package_width, package_length, turned, label}; with no
    package, package, package_width, package_length and turned are None and label is
    NO_PACKAGE_LABEL.
    """
    o_e = to_eighths(overhang_per_side)
    bw_e = to_eighths(W) + 2 * o_e
    bh_e = to_eighths(L) + 2 * o_e
    size = {"width": from_eighths(bw_e), "length": from_eighths(bh_e)}
    for name, pw, ph in PACKAGES:
        pw_e, ph_e = pw * E_PER_INCH, ph * E_PER_INCH
        upright = bw_e <= pw_e and bh_e <= ph_e
        turned = bw_e <= ph_e and bh_e <= pw_e
        if upright or turned:
            return {
                **size,
                "package": name,
                "package_width": pw,
                "package_length": ph,
                "turned": not upright,
                "label": f"{name} {pw} x {ph}",
            }
    return {
        **size,
        "package": None,
        "package_width": None,
        "package_length": None,
        "turned": None,
        "label": NO_PACKAGE_LABEL,
    }


# ---------------------------------------------------------------------------------------------
# F4: borders
# ---------------------------------------------------------------------------------------------


def border_join_count(
    Lp: int | Fraction, *, U: int | Fraction, j: int | Fraction = Fraction(1, 2)
) -> int:
    """Strips joined end to end for one border piece: 1 if Lp <= U else ceil((Lp - j) / (U - j))."""
    lp, u, jj = to_eighths(Lp), to_eighths(U), to_eighths(j)
    if lp <= u:
        return 1
    return ceil_div(lp - jj, u - jj)


def border_pair_strips(
    Lp: int | Fraction, *, U: int | Fraction, j: int | Fraction = Fraction(1, 2)
) -> int:
    """F4 strips for a pair of identical pieces: 1 when both fit one strip, 2 when one fits,
    else 2k joined strips."""
    lp, u = to_eighths(Lp), to_eighths(U)
    if lp <= 0:
        raise ValueError(f"border piece length must be positive, got {Lp}")
    if lp <= u:
        return ceil_div(2, u // lp)
    return 2 * border_join_count(Lp, U=U, j=j)


_BORDER_RULES = ("per_piece", "qp_pooled")
DEFAULT_TOP_MARGIN_PERCENT = 10  # p, MATH.md 1.3


def border(
    center_W: int | Fraction,
    center_L: int | Fraction,
    bands: list[int | Fraction] | tuple[int | Fraction, ...],
    *,
    U: int | Fraction,
    rule: str,
    margin_percent: int | None = None,
) -> dict:
    """Border bands of finished widths `bands`, inner size growing by 2b per band.

    rule "per_piece" is F4: sides Ls = Li + 1/2, top and bottom Lt = Wi + 2b + 1/2, strips per
    pair from border_pair_strips; yards are F5's purchase for the band as a border-only fabric
    (margin_percent, default 10, then up to 1/4 yd).
    rule "qp_pooled" is Quilter's Paradise: pooled = 2 Li + 2 (Wi + 2b) in finished lengths,
    strips = ceil(pooled / (U - 1/2)), yards from qp_strip_yards; it takes no margin.

    Every band has {width, strip_width, inner_width, inner_length, strips, length, yards};
    per_piece adds side_length, side_strips, top_length, top_strips and qp_pooled adds
    pooled_length. Returns {bands, finished_width, finished_length}.
    """
    if rule not in _BORDER_RULES:
        raise ValueError(f"unknown border rule {rule!r}; expected one of {_BORDER_RULES}")
    if rule == "qp_pooled" and margin_percent is not None:
        raise ValueError("qp_pooled emulates Quilter's Paradise, which adds no margin")
    margin = DEFAULT_TOP_MARGIN_PERCENT if margin_percent is None else margin_percent
    if margin < 0:
        raise ValueError(f"margin_percent must not be negative, got {margin_percent}")
    wi_e, li_e = to_eighths(center_W), to_eighths(center_L)
    u_e = to_eighths(U)
    out = []
    for b in bands:
        b_e = to_eighths(b)
        if b_e <= 0:
            raise ValueError(f"border width must be positive, got {b}")
        strip_w_e = b_e + HALF_INCH_E
        band = {
            "width": from_eighths(b_e),
            "strip_width": from_eighths(strip_w_e),
            "inner_width": from_eighths(wi_e),
            "inner_length": from_eighths(li_e),
        }
        if rule == "per_piece":
            ls_e = li_e + HALF_INCH_E
            lt_e = wi_e + 2 * b_e + HALF_INCH_E
            side = border_pair_strips(from_eighths(ls_e), U=U)
            top = border_pair_strips(from_eighths(lt_e), U=U)
            strips = side + top
            length_e = strips * strip_w_e
            purchase_e = ceil_div(length_e * (100 + margin), 100)
            band.update(
                side_length=from_eighths(ls_e),
                side_strips=side,
                top_length=from_eighths(lt_e),
                top_strips=top,
                strips=strips,
                length=from_eighths(length_e),
                yards=purchase_yards(purchase_e, "quarter"),
            )
        else:
            pooled_e = 2 * li_e + 2 * (wi_e + 2 * b_e)
            # Exact integers give the page's float ceil: in eighths a non-integer quotient sits
            # at least 1 / (u_e - 4) from an integer, far beyond double error at these sizes.
            strips = ceil_div(pooled_e, u_e - HALF_INCH_E)
            length_e = strips * strip_w_e
            band.update(
                pooled_length=from_eighths(pooled_e),
                strips=strips,
                length=from_eighths(length_e),
                yards=qp_strip_yards(strips, from_eighths(strip_w_e)),
            )
        out.append(band)
        wi_e += 2 * b_e
        li_e += 2 * b_e
    return {
        "bands": out,
        "finished_width": from_eighths(wi_e),
        "finished_length": from_eighths(li_e),
    }


# ---------------------------------------------------------------------------------------------
# Parameter sets
# ---------------------------------------------------------------------------------------------
# "math" is MATH.md's defaults (section 1.3); "today" is the code at the start SHA (D-01, D-03,
# D-08); "qp" and "nqc" are the MATH.md 5.2 driving parameters for Quilter's Paradise and
# Nebraska Quilt Company. Read-only, so one test cannot change another's parameters.

BACKING_SETS = MappingProxyType(
    {
        "math": MappingProxyType(
            {
                "B": 42,
                "overhang_per_side": 4,
                "s": 1,
                "allowance_pieced": 9,
                "allowance_one": Fraction(9, 2),
                "increment": "quarter",
                "keep": "least_total",
            }
        ),
        "today": MappingProxyType(
            {
                "B": 42,
                "overhang_per_side": 4,
                "s": 0,
                "allowance_pieced": 0,
                "allowance_one": 0,
                "increment": "quarter",
                "keep": "vertical_only",
            }
        ),
        "qp": MappingProxyType(
            {
                "B": 42,
                "overhang_per_side": 4,
                "s": 1,
                "allowance_pieced": 0,
                "allowance_one": 0,
                "increment": "qp_backing",
                "keep": "least_total",
            }
        ),
        "nqc": MappingProxyType(
            {
                "B": 40,
                "overhang_per_side": 4,
                "s": Fraction(1, 2),
                "allowance_pieced": 0,
                "allowance_one": 0,
                "increment": "quarter",
                "keep": "least_total",
            }
        ),
    }
)

BINDING_SETS = MappingProxyType(
    {
        "math": MappingProxyType(
            {"U": 40, "w": Fraction(5, 2), "extra": 10, "join_aware": True, "increment": "quarter"}
        ),
        "today": MappingProxyType(
            {"U": 42, "w": Fraction(5, 2), "extra": 10, "join_aware": False, "increment": "quarter"}
        ),
        "qp": MappingProxyType(
            {"U": 40, "w": Fraction(5, 2), "extra": 10, "join_aware": True, "increment": "qp_strip"}
        ),
        "nqc": MappingProxyType(
            {"U": 40, "w": Fraction(5, 2), "extra": 12, "join_aware": False, "increment": "quarter"}
        ),
        # QuiltKeeper Studio, from its page script (SOURCES["quiltkeeper_binding"]): strips =
        # ceil((2 (W + H) + overage) / fabric width), yards = strips x width / 36 rounded up to
        # 1/8. U is the 40 in the D2 run types; the page defaults to 42.
        "quiltkeeper": MappingProxyType(
            {"U": 40, "w": Fraction(5, 2), "extra": 10, "join_aware": False, "increment": "eighth"}
        ),
    }
)

WIDE_SETS = MappingProxyType(
    {
        "math": MappingProxyType(
            {
                "BW": 108,
                "overhang_per_side": 4,
                "allowance": Fraction(9, 2),
                "increment": "quarter",
            }
        ),
    }
)

BORDER_SETS = MappingProxyType(
    {
        "math": MappingProxyType({"U": 40, "rule": "per_piece"}),
        "qp": MappingProxyType({"U": 40, "rule": "qp_pooled"}),
    }
)


# ---------------------------------------------------------------------------------------------
# Calculators added by the D2 search, each modeled from its page's own script (read 2026-10-08).
# They count in exact eighths where that equals the page's floats: their quotients and yard
# values have small denominators, so a double never lands on the wrong side of a ceil. Sew Becca
# divides by the fabric width and is emulated in floats instead.
# ---------------------------------------------------------------------------------------------

SOURCES = MappingProxyType(
    {
        "mfqs_backing": "https://myfavoritequiltstore.com/assets/chunks/chunk-B-7na-F7.js",
        "stitchdesk_backing": "https://thestitchdesk.com/assets/calc.js",
        "stitchdesk_binding": "https://thestitchdesk.com/assets/calc.js",
        "quiltkeeper_binding": (
            "https://quiltkeeperstudio.com/_next/static/chunks/app/calculators/binding/"
            "page-de20c3006a96819f.js"
        ),
        "sewbecca_border": "https://sewbecca.com/border-calc",
        "qc_border": "https://quiltcalculator.com/_next/static/chunks/277-b1b795edf50fbbec.js",
    }
)


def _fits_package(width_e: int, length_e: int, packages, *, sorted_sides: bool) -> str | None:
    for name, pw, ph in packages:
        pw_e, ph_e = pw * E_PER_INCH, ph * E_PER_INCH
        if sorted_sides:
            fits = min(pw_e, ph_e) >= min(width_e, length_e) and max(pw_e, ph_e) >= max(
                width_e, length_e
            )
        else:
            fits = (width_e <= pw_e and length_e <= ph_e) or (
                width_e <= ph_e and length_e <= pw_e
            )
        if fits:
            return name
    return None


def _js_to_fixed(value: float, digits: int) -> Fraction:
    """JS Number.prototype.toFixed for value >= 0: the n nearest value x 10^digits, the larger n
    on a tie, read from the double's exact binary value."""
    if value < 0:
        raise ValueError(f"toFixed emulation covers values >= 0, got {value}")
    scale = 10**digits
    return Fraction(math.floor(Fraction(value) * scale + Fraction(1, 2)), scale)


# My Favorite Quilt Store: qx (backing) and xe (batting) in its shared chunk.
_MFQS_WIDE_E = 108 * E_PER_INCH
_MFQS_PACKAGES = (
    ("Crib", 45, 60),
    ("Twin", 72, 90),
    ("Full", 81, 96),
    ("Queen", 90, 108),
    ("King", 120, 120),
)
_MFQS_SHRINKAGE = {
    "Cotton": 0.04,
    "Polyester": 0.005,
    "Cotton/Poly Blend": 0.02,
    "Wool": 0.04,
    "Bamboo": 0.03,
}


def _mfqs_layout(fabric_e: int, wb_e: int, lb_e: int) -> dict:
    fits = []
    if wb_e <= fabric_e:
        fits.append(lb_e)
    if lb_e <= fabric_e:
        fits.append(wb_e)
    if fits:
        raw_e = min(fits)
        return {
            "panels": 1,
            "seams": "none",
            "raw": from_eighths(raw_e),
            "yards": purchase_yards(raw_e, "eighth"),
        }
    usable_e = fabric_e - E_PER_INCH  # 1 in off every panel, not every seam
    across_l = ceil_div(lb_e, usable_e)
    across_w = ceil_div(wb_e, usable_e)
    horizontal_e, vertical_e = across_l * wb_e, across_w * lb_e
    if horizontal_e <= vertical_e:
        n, seams, raw_e = across_l, "horizontal", horizontal_e
    else:
        n, seams, raw_e = across_w, "vertical", vertical_e
    return {
        "panels": n,
        "seams": seams,
        "raw": from_eighths(raw_e),
        "yards": purchase_yards(raw_e, "eighth"),
    }


def mfqs_backing(
    W: int | Fraction,
    L: int | Fraction,
    *,
    fabric_width: int | Fraction = 42,
    overage: int | Fraction = 4,
    batting: str = "Cotton",
) -> dict:
    """My Favorite Quilt Store backing and batting (defaults are the page's).

    Backing (Wb = W + 2 overage, Lb = L + 2 overage): one piece when either side fits the fabric
    width, cut the shorter qualifying length; otherwise panels = ceil(side / (fabric width - 1))
    both ways, horizontal (ceil(Lb / (fw - 1)) panels of Wb) kept unless vertical is shorter;
    yards rounded up to 1/8. The 108 in line is the same rule at 108 in, absent when the typed
    fabric is 108. Batting is Wb x Lb, the first package covering it, and the shrinkage line.

    Returns {backing: {panels, seams, raw, yards}, wide: {...} or None, batting: {width, length,
    package, shrink_width, shrink_length, washed_width, washed_length}}.
    """
    if batting not in _MFQS_SHRINKAGE:
        raise ValueError(
            f"unknown MFQS batting {batting!r}; expected one of {list(_MFQS_SHRINKAGE)}"
        )
    o_e = max(to_eighths(overage), 0)  # the page treats a missing or negative overage as 0
    wb_e = to_eighths(W) + 2 * o_e
    lb_e = to_eighths(L) + 2 * o_e
    fabric_e = to_eighths(fabric_width)
    if fabric_e <= E_PER_INCH:
        raise ValueError(f"fabric width {fabric_width} must exceed the 1 in panel loss")
    rate = _MFQS_SHRINKAGE[batting]
    # The shrinkage line is JS float arithmetic printed with toFixed(1).
    shrink_w, shrink_l = float(from_eighths(wb_e)) * rate, float(from_eighths(lb_e)) * rate
    return {
        "backing": _mfqs_layout(fabric_e, wb_e, lb_e),
        "wide": None if fabric_e == _MFQS_WIDE_E else _mfqs_layout(_MFQS_WIDE_E, wb_e, lb_e),
        "batting": {
            "width": from_eighths(wb_e),
            "length": from_eighths(lb_e),
            "package": _fits_package(wb_e, lb_e, _MFQS_PACKAGES, sorted_sides=True),
            "shrink_width": _js_to_fixed(shrink_w, 1),
            "shrink_length": _js_to_fixed(shrink_l, 1),
            "washed_width": _js_to_fixed(float(from_eighths(wb_e)) - shrink_w, 1),
            "washed_length": _js_to_fixed(float(from_eighths(lb_e)) - shrink_l, 1),
        },
    }


# The Stitch Desk: plan, nearestBatting and bindingStraight in calc.js.
STITCHDESK_SELVAGE = 2
_STITCHDESK_PRECUTS = (
    ("Craft", 36, 45),
    ("Crib", 45, 60),
    ("Throw", 60, 60),
    ("Twin", 72, 90),
    ("Full", 81, 96),
    ("Queen", 90, 108),
    ("King", 120, 120),
)


def _stitchdesk_plan(wb_e: int, lb_e: int, usable_e: int, sa_e: int) -> dict:
    eff_e = usable_e - 2 * sa_e
    if eff_e <= 0:
        raise ValueError("seam allowance leaves no usable panel width")
    pv = 1 if wb_e <= usable_e else ceil_div(wb_e, eff_e)
    ph = 1 if lb_e <= usable_e else ceil_div(lb_e, eff_e)
    layouts = {
        "vertical": {"panels": pv, "panel_length": from_eighths(lb_e), "raw": pv * lb_e},
        "horizontal": {"panels": ph, "panel_length": from_eighths(wb_e), "raw": ph * wb_e},
    }
    # Its yV <= yH compares pV x Lb / 36 with pH x Wb / 36, so vertical wins ties.
    vertical_wins = layouts["vertical"]["raw"] <= layouts["horizontal"]["raw"]
    kept = "vertical" if vertical_wins else "horizontal"
    raw_e = layouts[kept]["raw"]
    for layout in layouts.values():
        layout["raw"] = from_eighths(layout["raw"])
    return {
        **layouts,
        "kept": kept,
        "panels": layouts[kept]["panels"],
        "cut_length": layouts[kept]["panel_length"],
        "raw": from_eighths(raw_e),
        "yards": purchase_yards(raw_e, "eighth"),
    }


def stitchdesk_backing(
    W: int | Fraction,
    L: int | Fraction,
    *,
    fabric_width: int | Fraction = 42,
    overhang_per_side: int | Fraction = 4,
    batting_overhang_per_side: int | Fraction = 4,
    seam_allowance: int | Fraction = Fraction(1, 2),
) -> dict:
    """The Stitch Desk backing and batting (defaults are the page's).

    usable = fabric width - 2 (selvage); eff = usable - 2 x seam allowance; each side needs 1
    panel when it fits usable, else ceil(side / eff). Vertical is panels(Wb) x Lb, horizontal
    panels(Lb) x Wb; the smaller wins, vertical on a tie; yards rounded up to 1/8. Below 108 in
    it also plans 108 in (usable 106) and shows that line only when cheaper.

    Returns {backing_width, backing_length, usable, vertical, horizontal (each {panels,
    panel_length, raw}), kept, panels, cut_length, raw, yards, wide: {yards, cheaper, saves} or
    None on 108 in or wider, batting: {width, length, precut}}; precut None means "Buy off the
    roll".
    """
    o_e, bo_e = to_eighths(overhang_per_side), to_eighths(batting_overhang_per_side)
    wb_e, lb_e = to_eighths(W) + 2 * o_e, to_eighths(L) + 2 * o_e
    fabric_e = to_eighths(fabric_width)
    sa_e = to_eighths(seam_allowance)
    usable_e = fabric_e - STITCHDESK_SELVAGE * E_PER_INCH
    plan = _stitchdesk_plan(wb_e, lb_e, usable_e, sa_e)
    wide = None
    if fabric_e < 108 * E_PER_INCH:
        alt = _stitchdesk_plan(wb_e, lb_e, (108 - STITCHDESK_SELVAGE) * E_PER_INCH, sa_e)
        cheaper = alt["yards"] < plan["yards"]
        wide = {
            "yards": alt["yards"],
            "cheaper": cheaper,
            "saves": plan["yards"] - alt["yards"] if cheaper else None,
        }
    bw_e, bl_e = to_eighths(W) + 2 * bo_e, to_eighths(L) + 2 * bo_e
    return {
        "backing_width": from_eighths(wb_e),
        "backing_length": from_eighths(lb_e),
        "usable": from_eighths(usable_e),
        **plan,
        "wide": wide,
        "batting": {
            "width": from_eighths(bw_e),
            "length": from_eighths(bl_e),
            "precut": _fits_package(bw_e, bl_e, _STITCHDESK_PRECUTS, sorted_sides=False),
        },
    }


def stitchdesk_binding(
    W: int | Fraction,
    L: int | Fraction,
    *,
    strip_width: int | Fraction = Fraction(5, 2),
    fabric_width: int | Fraction = 42,
) -> dict:
    """The Stitch Desk straight-grain binding (defaults are the page's; bias is not modeled).

    total = 2 (W + L) + 4 x strip width + 10; usable = fabric width - 2; strips start at
    ceil(total / usable) and are recounted as ceil((total + (strips - 1) (strip width + 1/2)) /
    usable) until stable, at most ten passes as the page does; yards = strips x strip width / 36
    rounded up to 1/8.

    Returns {perimeter, extra, total, strips, joins, yards}.
    """
    w_e = to_eighths(strip_width)
    usable_e = to_eighths(fabric_width) - STITCHDESK_SELVAGE * E_PER_INCH
    if w_e <= 0 or usable_e <= 0:
        raise ValueError("strip width and usable fabric width must be positive")
    perimeter_e = 2 * (to_eighths(W) + to_eighths(L))
    extra_e = 4 * w_e + 10 * E_PER_INCH
    total_e = perimeter_e + extra_e
    join_e = w_e + HALF_INCH_E
    strips = ceil_div(total_e, usable_e)
    for _ in range(10):
        recount = ceil_div(total_e + (strips - 1) * join_e, usable_e)
        if recount == strips:
            break
        strips = recount
    return {
        "perimeter": from_eighths(perimeter_e),
        "extra": from_eighths(extra_e),
        "total": from_eighths(total_e),
        "strips": strips,
        "joins": strips - 1,
        "yards": purchase_yards(strips * w_e, "eighth"),
    }


def sewbecca_border(
    W: int | Fraction | str,
    L: int | Fraction | str,
    border_width: int | Fraction | str,
    *,
    fabric_width: int | Fraction | str = 42,
) -> dict:
    """Sew Becca's border (calculateFabric), in the page's float order:
    strips = ceil(2 L / fw + 2 (W + b) / fw); yards = strips x b / fw (its divisor is the fabric
    width, not 36) rounded up to 1/8. Returns {strips, yards}."""
    w, ln, b, fw = (_js_number(v) for v in (W, L, border_width, fabric_width))
    if fw <= 0:
        raise ValueError(f"fabric width must be positive, got {fabric_width!r}")
    strips = math.ceil(((ln * 2) / fw) + (((w + b) * 2) / fw))
    yards = (strips * b) / fw
    return {"strips": strips, "yards": Fraction(math.ceil(yards * 8), 8)}


def qc_border(
    W: int | Fraction,
    L: int | Fraction,
    borders: list[int | Fraction] | tuple[int | Fraction, ...],
    *,
    fabric_width: int | Fraction = 44,
) -> dict:
    """Quilt Calculator's border (default width is the page's 44 in), one result per enabled
    border in order: strips = ceil((2 W + 2 L + 4 b + 12) / (fabric width - 1/2)); yards =
    strips x (b + 1/2) / 36 rounded up to 1/8; then W and L grow by 2 b.

    Returns {borders: [{index, width, strips, yards, width_after, length_after}]}.
    """
    w_e, l_e = to_eighths(W), to_eighths(L)
    usable_e = to_eighths(fabric_width) - HALF_INCH_E
    if usable_e <= 0:
        raise ValueError(f"fabric width {fabric_width} leaves no usable width")
    out = []
    for index, b in enumerate(borders, start=1):
        b_e = to_eighths(b)
        if b_e <= 0:
            raise ValueError(f"border width must be positive, got {b}")
        strips = ceil_div(2 * w_e + 2 * l_e + 4 * b_e + 12 * E_PER_INCH, usable_e)
        w_e += 2 * b_e
        l_e += 2 * b_e
        out.append(
            {
                "index": index,
                "width": from_eighths(b_e),
                "strips": strips,
                "yards": purchase_yards(strips * (b_e + HALF_INCH_E), "eighth"),
                "width_after": from_eighths(w_e),
                "length_after": from_eighths(l_e),
            }
        )
    return {"borders": out}
