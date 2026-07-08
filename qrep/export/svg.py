"""SVG diagrams via svgwrite: quilt top with inch rulers, per-block diagrams,
strip-set diagrams, and an assembly schematic.

True to scale at PX_PER_INCH. Deterministic: every coordinate goes through
_fmt ({:.3f}), iteration follows model order, no ids, no timestamps.
"""

import svgwrite

from qrep.construct.plan import ConstructionPlan
from qrep.construct.strategies import infer_block_structure
from qrep.model.schema import Quilt
from qrep.model.units import format_inches

PX_PER_INCH = 10
RULER_SPACE = 40.0  # px reserved for each ruler
PAD = 10.0

MAJOR_EVERY = 5  # labeled major tick every 5 inches
MINOR_LEN = 4.0
MAJOR_LEN = 9.0


def _px(eighths: int, ppi: int = PX_PER_INCH) -> float:
    return eighths * ppi / 8


def _fmt(value: float) -> str:
    return f"{value:.3f}"


def _inch_label(eighths: int) -> str:
    # ruler labels are inch numbers without the trailing quote mark
    return format_inches(eighths)[:-1]


def render_top_svg(quilt: Quilt) -> str:
    """Full quilt top, true to scale, rulers on the x (top) and y (left) axes.

    Rulers show finished dimensions only; extents match the model's computed
    finished width and height exactly.
    """
    quilt_w = _px(quilt.finished_width)
    quilt_h = _px(quilt.finished_height)
    total_w = RULER_SPACE + quilt_w + PAD
    total_h = RULER_SPACE + quilt_h + PAD
    colors = {f.id: f.color for f in quilt.palette.fabrics}

    dwg = svgwrite.Drawing(
        size=(_fmt(total_w), _fmt(total_h)),
        viewBox=f"0 0 {_fmt(total_w)} {_fmt(total_h)}",
    )
    ox, oy = RULER_SPACE, RULER_SPACE

    # border bands: outermost first so inner bands and cells paint on top
    inset = 0
    for band in reversed(quilt.borders):
        dwg.add(
            dwg.rect(
                insert=(_fmt(ox + _px(inset)), _fmt(oy + _px(inset))),
                size=(
                    _fmt(_px(quilt.finished_width - 2 * inset)),
                    _fmt(_px(quilt.finished_height - 2 * inset)),
                ),
                fill=colors[band.fabric_id],
                class_="border-band",
            )
        )
        inset += band.width

    # center field cells
    border_total = sum(b.width for b in quilt.borders)
    cell = quilt.center.cell_size
    cx0 = ox + _px(border_total)
    cy0 = oy + _px(border_total)
    for r, row in enumerate(quilt.center.cells):
        for c, fabric_id in enumerate(row):
            dwg.add(
                dwg.rect(
                    insert=(_fmt(cx0 + _px(c * cell)), _fmt(cy0 + _px(r * cell))),
                    size=(_fmt(_px(cell)), _fmt(_px(cell))),
                    fill=colors[fabric_id],
                    class_="cell",
                )
            )

    # x ruler along the top
    dwg.add(
        dwg.line(
            start=(_fmt(ox), _fmt(oy - 2)),
            end=(_fmt(ox + quilt_w), _fmt(oy - 2)),
            stroke="#333333",
            stroke_width="1",
            class_="ruler-x",
        )
    )
    for inch in range(quilt.finished_width // 8 + 1):
        x = ox + inch * PX_PER_INCH
        major = inch % MAJOR_EVERY == 0
        length = MAJOR_LEN if major else MINOR_LEN
        dwg.add(
            dwg.line(
                start=(_fmt(x), _fmt(oy - 2)),
                end=(_fmt(x), _fmt(oy - 2 - length)),
                stroke="#333333",
                stroke_width="1",
                class_="tick-x-major" if major else "tick-x-minor",
            )
        )
        if major:
            dwg.add(
                dwg.text(
                    _inch_label(inch * 8),
                    insert=(_fmt(x), _fmt(oy - 2 - MAJOR_LEN - 3)),
                    text_anchor="middle",
                    font_size="9",
                    font_family="sans-serif",
                    fill="#333333",
                    class_="ruler-label-x",
                )
            )

    # y ruler along the left
    dwg.add(
        dwg.line(
            start=(_fmt(ox - 2), _fmt(oy)),
            end=(_fmt(ox - 2), _fmt(oy + quilt_h)),
            stroke="#333333",
            stroke_width="1",
            class_="ruler-y",
        )
    )
    for inch in range(quilt.finished_height // 8 + 1):
        y = oy + inch * PX_PER_INCH
        major = inch % MAJOR_EVERY == 0
        length = MAJOR_LEN if major else MINOR_LEN
        dwg.add(
            dwg.line(
                start=(_fmt(ox - 2), _fmt(y)),
                end=(_fmt(ox - 2 - length), _fmt(y)),
                stroke="#333333",
                stroke_width="1",
                class_="tick-y-major" if major else "tick-y-minor",
            )
        )
        if major:
            dwg.add(
                dwg.text(
                    _inch_label(inch * 8),
                    insert=(_fmt(ox - 2 - MAJOR_LEN - 3), _fmt(y + 3)),
                    text_anchor="end",
                    font_size="9",
                    font_family="sans-serif",
                    fill="#333333",
                    class_="ruler-label-y",
                )
            )
    return dwg.tostring()


BLOCK_PPI = 40  # per-block diagrams are drawn larger for readability


def render_block_svgs(quilt: Quilt) -> dict[str, str]:
    """One diagram per distinct block type, keyed by lowercase label ('a', 'b').

    Returns an empty dict when the grid has no block structure.
    """
    structure = infer_block_structure(quilt.center.cells)
    if structure is None:
        return {}
    colors = {f.id: f.color for f in quilt.palette.fabrics}
    cell = quilt.center.cell_size
    out: dict[str, str] = {}
    for idx, block in enumerate(structure.types):
        p = structure.size
        side = _px(cell, BLOCK_PPI)
        width = p * side + 20
        height = p * side + 40
        dwg = svgwrite.Drawing(
            size=(_fmt(width), _fmt(height)),
            viewBox=f"0 0 {_fmt(width)} {_fmt(height)}",
        )
        dwg.add(
            dwg.text(
                f"{structure.label(idx)} - make {structure.counts[idx]}",
                insert=(_fmt(10.0), _fmt(16.0)),
                font_size="12",
                font_family="sans-serif",
                fill="#333333",
                class_="block-title",
            )
        )
        for r in range(p):
            for c in range(p):
                dwg.add(
                    dwg.rect(
                        insert=(_fmt(10 + c * side), _fmt(24 + r * side)),
                        size=(_fmt(side), _fmt(side)),
                        fill=colors[block[r][c]],
                        stroke="#666666",
                        stroke_width="0.5",
                        class_="cell",
                    )
                )
        out[structure.label(idx)[-1].lower()] = dwg.tostring()
    return out


def render_strip_sets_svg(quilt: Quilt, plan: ConstructionPlan) -> str | None:
    """Distinct strip sets, true to scale: WOF-long strips stacked in sewing
    order with dashed crosscut marks. None when the plan has no strip sets."""
    if not plan.strip_sets:
        return None
    colors = {f.id: f.color for f in quilt.palette.fabrics}
    wof_px = _px(quilt.settings.wof)
    gap = 28.0
    set_heights = [
        len(s.sequence) * _px(s.strip_cut_width) for s in plan.strip_sets
    ]
    total_h = sum(set_heights) + gap * len(plan.strip_sets) + 10
    total_w = wof_px + 20
    dwg = svgwrite.Drawing(
        size=(_fmt(total_w), _fmt(total_h)),
        viewBox=f"0 0 {_fmt(total_w)} {_fmt(total_h)}",
    )
    y = 10.0
    for strip_set, set_h in zip(plan.strip_sets, set_heights):
        dwg.add(
            dwg.text(
                f"{strip_set.id}: make {strip_set.sets_needed}, "
                f"crosscut {strip_set.segments_needed} segments at "
                f"{format_inches(strip_set.segment_cut_width)}",
                insert=(_fmt(10.0), _fmt(y + 12)),
                font_size="11",
                font_family="sans-serif",
                fill="#333333",
                class_="strip-set-title",
            )
        )
        y += 18
        strip_h = _px(strip_set.strip_cut_width)
        for i, fabric_id in enumerate(strip_set.sequence):
            dwg.add(
                dwg.rect(
                    insert=(_fmt(10.0), _fmt(y + i * strip_h)),
                    size=(_fmt(wof_px), _fmt(strip_h)),
                    fill=colors[fabric_id],
                    stroke="#666666",
                    stroke_width="0.5",
                    class_="strip",
                )
            )
        seg_px = _px(strip_set.segment_cut_width)
        marks = int(wof_px // seg_px)
        for k in range(1, marks + 1):
            dwg.add(
                dwg.line(
                    start=(_fmt(10 + k * seg_px), _fmt(y)),
                    end=(_fmt(10 + k * seg_px), _fmt(y + set_h - 18)),
                    stroke="#333333",
                    stroke_width="0.5",
                    stroke_dasharray="3,3",
                    class_="crosscut",
                )
            )
        y += set_h - 18 + gap
    return dwg.tostring()


ASSEMBLY_BLOCK_PX = 30.0


def render_assembly_svg(quilt: Quilt) -> str:
    """Numbered assembly schematic: the block layout with row numbers in
    joining order. Falls back to a cell-row schematic without block structure."""
    structure = infer_block_structure(quilt.center.cells)
    if structure is None:
        rows = quilt.center.rows
        dwg = svgwrite.Drawing(size=("300.000", _fmt(30 + rows * 12)))
        dwg.add(
            dwg.text(
                f"Assembly: sew {rows} cell rows top to bottom",
                insert=("10.000", "16.000"),
                font_size="12",
                font_family="sans-serif",
                fill="#333333",
                class_="assembly-title",
            )
        )
        return dwg.tostring()
    block_rows = len(structure.layout)
    blocks_across = len(structure.layout[0])
    width = 40 + blocks_across * ASSEMBLY_BLOCK_PX + 10
    height = 30 + block_rows * ASSEMBLY_BLOCK_PX + 10
    dwg = svgwrite.Drawing(
        size=(_fmt(width), _fmt(height)), viewBox=f"0 0 {_fmt(width)} {_fmt(height)}"
    )
    dwg.add(
        dwg.text(
            "Assembly: piece blocks, join numbered rows top to bottom",
            insert=("10.000", "16.000"),
            font_size="11",
            font_family="sans-serif",
            fill="#333333",
            class_="assembly-title",
        )
    )
    for br in range(block_rows):
        y = 30 + br * ASSEMBLY_BLOCK_PX
        dwg.add(
            dwg.text(
                str(br + 1),
                insert=(_fmt(30.0), _fmt(y + ASSEMBLY_BLOCK_PX / 2 + 4)),
                text_anchor="end",
                font_size="10",
                font_family="sans-serif",
                fill="#333333",
                class_="row-number",
            )
        )
        for bc in range(blocks_across):
            x = 40 + bc * ASSEMBLY_BLOCK_PX
            dwg.add(
                dwg.rect(
                    insert=(_fmt(x), _fmt(y)),
                    size=(_fmt(ASSEMBLY_BLOCK_PX), _fmt(ASSEMBLY_BLOCK_PX)),
                    fill="#ffffff",
                    stroke="#666666",
                    stroke_width="0.5",
                    class_="block-outline",
                )
            )
            dwg.add(
                dwg.text(
                    structure.label(structure.layout[br][bc])[-1],
                    insert=(
                        _fmt(x + ASSEMBLY_BLOCK_PX / 2),
                        _fmt(y + ASSEMBLY_BLOCK_PX / 2 + 4),
                    ),
                    text_anchor="middle",
                    font_size="10",
                    font_family="sans-serif",
                    fill="#333333",
                    class_="block-letter",
                )
            )
    return dwg.tostring()
