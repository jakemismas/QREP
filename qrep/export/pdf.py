"""PDF pattern booklet exporter.

Two layers: build_sections turns a quilt and its construction plan into an
ordered list of structured Section models (title, paragraphs, tables, numbered
steps), and render_booklet lays those sections out as a reportlab platypus PDF.
Keeping the structure separate from the layout lets tests assert on section
content without parsing PDF bytes. reportlab only; weasyprint is banned. All
lengths are integer eighths (see qrep.model.units); the one place they become
strings is format_inches / format_yards.
"""

from __future__ import annotations

from math import ceil
from pathlib import Path
from xml.sax.saxutils import escape

from pydantic import BaseModel
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from qrep.construct.plan import ConstructionPlan
from qrep.construct.yardage import compute_purchase_lines
from qrep.export.yardage_report import format_yards
from qrep.model.schema import Quilt
from qrep.model.units import format_inches

# Batting is cut to the finished top plus 8 inches on each dimension (4 inches
# of overhang per side), the standard long-arm loading allowance.
BATTING_MARGIN_EIGHTHS = 64

SECTION_TITLES = (
    "Introduction",
    "Fabrics",
    "Cutting",
    "Strip sets",
    "Assembly",
    "Borders",
    "Binding",
    "Finishing",
)


class SectionTable(BaseModel):
    header: list[str]
    rows: list[list[str]]


class Section(BaseModel):
    title: str
    paragraphs: list[str] = []
    tables: list[SectionTable] = []
    numbered: list[str] = []  # rendered as "1. ...", "2. ..." in order


def build_sections(quilt: Quilt, plan: ConstructionPlan) -> list[Section]:
    """Return the eight booklet sections, in SECTION_TITLES order.

    Every derived value comes from the quilt or the plan, so the same inputs
    always produce the same sections.
    """
    names = {f.id: f.name for f in quilt.palette.fabrics}
    cell_counts: dict[str, int] = {}
    for row in quilt.center.cells:
        for fid in row:
            cell_counts[fid] = cell_counts.get(fid, 0) + 1
    purchase = compute_purchase_lines(quilt, plan)

    return [
        _introduction(quilt, plan),
        _fabrics(quilt, cell_counts, purchase),
        _cutting(plan, names),
        _strip_sets(plan),
        _assembly(plan),
        _borders(quilt, names),
        _binding(quilt, names),
        _finishing(quilt, purchase),
    ]


def _introduction(quilt: Quilt, plan: ConstructionPlan) -> Section:
    metrics = plan.metrics
    label = metrics.heuristic_label
    return Section(
        title="Introduction",
        paragraphs=[
            f"{quilt.metadata.name} finishes at "
            f"{format_inches(quilt.finished_width)} wide by "
            f"{format_inches(quilt.finished_height)} tall.",
            f"This booklet plans the quilt with the {plan.strategy} strategy. "
            f"The finished top has {metrics.piece_count} pieces.",
            f"Difficulty is {metrics.difficulty} on a {label}.",
            f"Estimated piecing time is {metrics.time_minutes} minutes on a {label}.",
        ],
    )


def _fabrics(quilt: Quilt, cell_counts: dict[str, int], purchase) -> Section:
    fabric_table = SectionTable(
        header=["Fabric", "ID", "Color", "Cells"],
        rows=[
            [f.name, f.id, f.color, str(cell_counts.get(f.id, 0))]
            for f in quilt.palette.fabrics
        ],
    )
    # compute_purchase_lines already emits the binding and backing lines.
    purchase_table = SectionTable(
        header=["Purchase", "Length", "Yards"],
        rows=[
            [line.name, format_inches(line.length_needed), format_yards(line.quarter_yards)]
            for line in purchase.lines
        ],
    )
    return Section(
        title="Fabrics",
        paragraphs=["Palette fabrics and the yardage to buy, rounded up per fabric."],
        tables=[fabric_table, purchase_table],
    )


def _cutting(plan: ConstructionPlan, names: dict[str, str]) -> Section:
    rows = []
    for p in plan.cut_pieces:
        # This cut-size string must match the cut list CSV cut_size column
        # exactly (qrep.export.cutlist); a test cross-checks the two.
        cut_size = f"{format_inches(p.cut_width)} x {format_inches(p.cut_height)}"
        finished_size = f"{format_inches(p.finished_width)} x {format_inches(p.finished_height)}"
        rows.append(
            [names[p.fabric_id], p.label, p.component, str(p.quantity), cut_size, finished_size]
        )
    return Section(
        title="Cutting",
        tables=[
            SectionTable(
                header=["Fabric", "Piece", "Component", "Quantity", "Cut size", "Finished size"],
                rows=rows,
            )
        ],
    )


def _strip_sets(plan: ConstructionPlan) -> Section:
    if not plan.strip_sets:
        return Section(title="Strip sets", paragraphs=["No strip sets for this strategy."])
    rows = [
        [
            s.id,
            " ".join(s.sequence),
            format_inches(s.strip_cut_width),
            str(s.sets_needed),
            str(s.segments_per_set),
            str(s.segments_needed),
        ]
        for s in plan.strip_sets
    ]
    return Section(
        title="Strip sets",
        paragraphs=[
            f"Crosscut every strip set at "
            f"{format_inches(plan.strip_sets[0].segment_cut_width)}."
        ],
        tables=[
            SectionTable(
                header=[
                    "Set",
                    "Strips",
                    "Strip cut width",
                    "Sets to make",
                    "Segments per set",
                    "Segments needed",
                ],
                rows=rows,
            )
        ],
    )


def _assembly(plan: ConstructionPlan) -> Section:
    items = []
    for step in plan.assembly:
        text = f"{step.title}. {step.detail}"
        # Fold substeps into the step text so the numbering stays one item per
        # AssemblyStep (deterministic choice per the section contract).
        if step.substeps:
            text = f"{text} {' '.join(step.substeps)}"
        items.append(text)
    return Section(title="Assembly", numbered=items)


def _borders(quilt: Quilt, names: dict[str, str]) -> Section:
    if not quilt.borders:
        return Section(title="Borders", paragraphs=["No border bands."])
    paras = [
        f"Border {i}: {names[b.fabric_id]}, "
        f"{format_inches(b.width)} finished band on all four sides."
        for i, b in enumerate(quilt.borders, start=1)
    ]
    return Section(title="Borders", paragraphs=paras)


def _binding(quilt: Quilt, names: dict[str, str]) -> Section:
    strips = ceil(quilt.binding_length / quilt.settings.wof)
    return Section(
        title="Binding",
        paragraphs=[
            f"Bind with {names[quilt.binding.fabric_id]}. "
            f"Cut {format_inches(quilt.binding.strip_width)} strips and join "
            f"{strips} widths of fabric for "
            f"{format_inches(quilt.binding_length)} of binding.",
        ],
    )


def _finishing(quilt: Quilt, purchase) -> Section:
    backing = next(line for line in purchase.lines if line.purpose == "backing")
    settings = quilt.settings
    panels = ceil((quilt.finished_width + settings.backing_margin) / settings.wof)
    batting_w = quilt.finished_width + BATTING_MARGIN_EIGHTHS
    batting_h = quilt.finished_height + BATTING_MARGIN_EIGHTHS
    if quilt.quilting.motifs:
        density = quilt.quilting.density
        note = f"Quilting: {len(quilt.quilting.motifs)} authored motif(s)"
        note += f" at {density} stitches per inch." if density is not None else "."
    else:
        note = (
            "Quilting: no motifs are authored. Quilt as desired, for example an "
            "allover edge-to-edge design."
        )
    return Section(
        title="Finishing",
        paragraphs=[
            f"Backing: piece {panels} panel(s) for "
            f"{format_inches(backing.length_needed)} of 42-inch fabric.",
            f"Batting: at least {format_inches(batting_w)} by {format_inches(batting_h)}, "
            f"the finished top plus {format_inches(BATTING_MARGIN_EIGHTHS)} on each dimension.",
            note,
        ],
    )


# Columns that hold long text get a heavier share of the row width so cut-size
# cells stay on one line and text extraction does not fragment them.
_COL_WEIGHTS = {
    "Piece": 2.6,
    "Cut size": 1.7,
    "Finished size": 1.7,
    "Strips": 2.0,
    "Purchase": 2.2,
}


def _col_widths(header: list[str], content_width: float) -> list[float]:
    weights = [_COL_WEIGHTS.get(h, 1.0) for h in header]
    total = sum(weights)
    return [content_width * w / total for w in weights]


def _table_flowable(
    section_table: SectionTable,
    content_width: float,
    cell: ParagraphStyle,
    head: ParagraphStyle,
) -> Table:
    data = [[Paragraph(escape(h), head) for h in section_table.header]]
    for row in section_table.rows:
        data.append([Paragraph(escape(str(c)), cell) for c in row])
    table = Table(data, colWidths=_col_widths(section_table.header, content_width), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def render_booklet(quilt: Quilt, plan: ConstructionPlan, path: str | Path) -> None:
    """Render the pattern booklet to a letter-size PDF at path.

    Built-in Helvetica only; PDF metadata is fixed (title = quilt name, author
    QREP) so the output carries no incidental content beyond the sections.
    """
    sections = build_sections(quilt, plan)
    styles = getSampleStyleSheet()
    cell = ParagraphStyle(
        "cell",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        spaceBefore=0,
        spaceAfter=0,
    )
    head = ParagraphStyle("cellhead", parent=cell, fontName="Helvetica-Bold")

    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
        title=quilt.metadata.name,
        author="QREP",
    )
    story = [
        Paragraph(escape(quilt.metadata.name), styles["Title"]),
        Spacer(1, 24),
        Paragraph("QREP pattern booklet", styles["Heading3"]),
        PageBreak(),
    ]
    for section in sections:
        story.append(Paragraph(escape(section.title), styles["Heading2"]))
        for para in section.paragraphs:
            story.append(Paragraph(escape(para), styles["BodyText"]))
        for i, item in enumerate(section.numbered, start=1):
            story.append(Paragraph(f"{i}. {escape(item)}", styles["BodyText"]))
        for table in section.tables:
            story.append(_table_flowable(table, doc.width, cell, head))
            story.append(Spacer(1, 12))
    doc.build(story)
