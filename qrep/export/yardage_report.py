"""Yardage report markdown: one line per palette fabric plus the dedicated
backing line. Yards are quarter-yard multiples by construction."""

from qrep.construct.yardage import YardageReport
from qrep.model.units import format_inches


def format_yards(quarter_yards: int) -> str:
    whole, quarters = divmod(quarter_yards, 4)
    fraction = {0: "", 1: " 1/4", 2: " 1/2", 3: " 3/4"}[quarters]
    if whole == 0 and quarters:
        return f"{fraction.strip()} yd"
    return f"{whole}{fraction} yd"


def render_yardage_md(report: YardageReport) -> str:
    lines = [
        f"# Yardage ({report.strategy} strategy)",
        "",
        "| Fabric | Length needed | Yards |",
        "| --- | --- | --- |",
    ]
    for line in report.lines:
        label = f"{line.name} ({line.fabric_id})" if line.fabric_id else line.name
        lines.append(
            f"| {label} | {format_inches(line.length_needed)} "
            f"| {format_yards(line.quarter_yards)} |"
        )
    lines += [
        "",
        "Yardage rounds up to the nearest 1/4 yard per fabric. "
        "Backing is a dedicated line item, never a palette fabric.",
        "",
    ]
    return "\n".join(lines)
