"""Yardage report markdown: one line per palette fabric, the binding and the
dedicated backing line, then the wide-back alternative when the report offers
one. Yards print as mixed fractions of the purchase increment (MATH.md F13)."""

from fractions import Fraction

from qrep.construct.yardage import QUARTER_YARD, YardageReport
from qrep.model.units import format_inches

YARD = 288  # eighths of an inch


def format_yards(increments: int, increment: int = QUARTER_YARD) -> str:
    whole, rest = divmod(increments * increment, YARD)
    if not rest:
        return f"{whole} yd"
    fraction = Fraction(rest, YARD)
    text = f"{fraction.numerator}/{fraction.denominator}"
    return f"{whole} {text} yd" if whole else f"{text} yd"


def render_yardage_md(report: YardageReport) -> str:
    lines = [
        f"# Yardage ({report.strategy} strategy)",
        "",
        "| Fabric | Length needed | Purchase length | Yards |",
        "| --- | --- | --- | --- |",
    ]
    for line in report.lines:
        label = f"{line.name} ({line.fabric_id})" if line.fabric_id else line.name
        lines.append(
            f"| {label} | {format_inches(line.length_needed)} "
            f"| {format_inches(line.purchase)} "
            f"| {format_yards(line.increments, report.increment)} |"
        )
    if report.wide_back is not None:
        wide = report.wide_back
        lines += [
            "",
            f"Or replace the backing line with {wide.name} "
            f"({format_inches(wide.length_needed)} needed, "
            f"{format_inches(wide.purchase)} with its squaring allowance), "
            f"{format_yards(wide.increments, report.increment)}.",
        ]
    backing = next(line for line in report.lines if line.purpose == "backing")
    allowance = format_inches(backing.purchase - backing.length_needed)
    lines += [
        "",
        f"Purchase length adds a {report.top_margin} percent margin to each quilt-top fabric "
        f"and a {allowance} squaring allowance to the backing. "
        f"Each line rounds up to the nearest {format_yards(1, report.increment)}. "
        "Backing is a dedicated line item, never a palette fabric.",
        "",
    ]
    return "\n".join(lines)
