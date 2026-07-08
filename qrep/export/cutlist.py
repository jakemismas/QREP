"""Cut list exports: markdown for quilters, CSV for machines.

Deterministic: pieces come out in plan order (palette order, descending
size), strip sets in first-appearance order, LF newlines, no timestamps.
"""

import csv
import io

from qrep.construct.plan import ConstructionPlan
from qrep.model.schema import Quilt
from qrep.model.units import format_inches


def _size(width: int, height: int) -> str:
    return f"{format_inches(width)} x {format_inches(height)}"


def render_cutlist_md(quilt: Quilt, plan: ConstructionPlan) -> str:
    lines = [
        f"# Cut list - {plan.quilt_name} ({plan.strategy} strategy)",
        "",
    ]
    for fabric in quilt.palette.fabrics:
        pieces = [p for p in plan.cut_pieces if p.fabric_id == fabric.id]
        if not pieces:
            continue
        lines += [f"## {fabric.name} ({fabric.id})", ""]
        lines.append("| Piece | Component | Source | Quantity | Cut size | Finished size |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for p in pieces:
            source = "strip sets" if p.source == "strip_set" else "rotary"
            lines.append(
                f"| {p.label} | {p.component} | {source} | {p.quantity} "
                f"| {_size(p.cut_width, p.cut_height)} "
                f"| {_size(p.finished_width, p.finished_height)} |"
            )
        lines.append("")
    if plan.strip_sets:
        lines += ["## Strip cutting chart", ""]
        lines.append(
            "| Set | Strips (top to bottom) | Strip cut width "
            "| Sets to make | Segments per set | Segments needed |"
        )
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for s in plan.strip_sets:
            lines.append(
                f"| {s.id} | {' '.join(s.sequence)} | {format_inches(s.strip_cut_width)} "
                f"| {s.sets_needed} | {s.segments_per_set} | {s.segments_needed} |"
            )
        lines.append(
            f"\nCrosscut every set at {format_inches(plan.strip_sets[0].segment_cut_width)}."
        )
        lines.append("")
    return "\n".join(lines)


CSV_COLUMNS = [
    "fabric_id",
    "fabric_name",
    "component",
    "source",
    "label",
    "quantity",
    "cut_width_eighths",
    "cut_height_eighths",
    "finished_width_eighths",
    "finished_height_eighths",
    "cut_size",
    "finished_size",
]


def render_cutlist_csv(quilt: Quilt, plan: ConstructionPlan) -> str:
    names = {f.id: f.name for f in quilt.palette.fabrics}
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for p in plan.cut_pieces:
        writer.writerow(
            [
                p.fabric_id,
                names[p.fabric_id],
                p.component,
                p.source,
                p.label,
                p.quantity,
                p.cut_width,
                p.cut_height,
                p.finished_width,
                p.finished_height,
                _size(p.cut_width, p.cut_height),
                _size(p.finished_width, p.finished_height),
            ]
        )
    return buffer.getvalue()
