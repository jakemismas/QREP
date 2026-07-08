"""Construction strategies: historical, strip, modern, plus v1 stubs.

Every strategy is a pure function Quilt -> ConstructionPlan. Iteration is
ordered everywhere (palette order, reading order, first-appearance order) so
the same quilt always serializes to the same plan.
"""

from collections import Counter
from math import ceil, gcd, log10

from qrep.construct.plan import (
    AssemblyStep,
    ConstructionPlan,
    CutPiece,
    PlanMetrics,
    StripSet,
)
from qrep.construct.yardage import (
    QUARTER_YARD,
    compute_yardage_from_components,
    cut_area_by_fabric,
)
from qrep.model.schema import Quilt
from qrep.model.units import format_inches

SQFT = 96 * 96  # one square foot in eighths squared

BlockGrid = tuple[tuple[str, ...], ...]


class BlockStructure:
    """A grid decomposed into p x p blocks with few distinct types."""

    def __init__(self, size: int, types: list[BlockGrid], layout: list[list[int]]):
        self.size = size
        self.types = types  # by first appearance in reading order
        self.layout = layout  # type index per (block_row, block_col)
        self.counts = [0] * len(types)
        for row in layout:
            for idx in row:
                self.counts[idx] += 1

    def label(self, idx: int) -> str:
        return f"Block {chr(ord('A') + idx)}"


def infer_block_structure(cells: list[list[str]], max_types: int = 8) -> BlockStructure | None:
    """Smallest period p > 1 dividing both dimensions with <= max_types distinct
    p x p blocks. Returns None when the grid has no usable block period."""
    rows, cols = len(cells), len(cells[0])
    g = gcd(rows, cols)
    for p in range(2, g + 1):
        if g % p:
            continue
        types: list[BlockGrid] = []
        index: dict[BlockGrid, int] = {}
        layout: list[list[int]] = []
        for br in range(rows // p):
            layout_row = []
            for bc in range(cols // p):
                block = tuple(
                    tuple(cells[br * p + r][bc * p + c] for c in range(p)) for r in range(p)
                )
                if block not in index:
                    index[block] = len(types)
                    types.append(block)
                layout_row.append(index[block])
            layout.append(layout_row)
        if len(types) <= max_types:
            return BlockStructure(p, types, layout)
    return None


# --- shared piece builders ---------------------------------------------------


def _size_label(fw: int, fh: int, cw: int, ch: int) -> str:
    if fw == fh:
        return f"{format_inches(fw)} square, cut {format_inches(cw)} x {format_inches(ch)}"
    return (
        f"{format_inches(fw)} x {format_inches(fh)}, "
        f"cut {format_inches(cw)} x {format_inches(ch)}"
    )


def border_pieces(quilt: Quilt) -> list[CutPiece]:
    """Per band, inner to outer: two sides at the running height, then top and
    bottom spanning the widened width. One piece per side (v1 simplification,
    identical across strategies so comparisons hold)."""
    pieces: list[CutPiece] = []
    add = quilt.settings.cut_add
    width, height = quilt.center.width, quilt.center.height
    for i, band in enumerate(quilt.borders, start=1):
        pieces.append(
            CutPiece(
                fabric_id=band.fabric_id,
                component="border",
                finished_width=band.width,
                finished_height=height,
                cut_width=band.width + add,
                cut_height=height + add,
                quantity=2,
                label=(
                    f"border {i} side, "
                    f"{format_inches(band.width)} x {format_inches(height)} finished"
                ),
            )
        )
        width += 2 * band.width
        pieces.append(
            CutPiece(
                fabric_id=band.fabric_id,
                component="border",
                finished_width=width,
                finished_height=band.width,
                cut_width=width + add,
                cut_height=band.width + add,
                quantity=2,
                label=(
                    f"border {i} top/bottom, "
                    f"{format_inches(width)} x {format_inches(band.width)} finished"
                ),
            )
        )
        height += 2 * band.width
    return pieces


def binding_pieces(quilt: Quilt) -> list[CutPiece]:
    """WOF strips; finished dims equal cut dims because binding never counts
    toward the finished-top area."""
    wof = quilt.settings.wof
    strips = ceil(quilt.binding_length / wof)
    width = quilt.binding.strip_width
    return [
        CutPiece(
            fabric_id=quilt.binding.fabric_id,
            component="binding",
            finished_width=width,
            finished_height=wof,
            cut_width=width,
            cut_height=wof,
            quantity=strips,
            label=f"binding strip, {format_inches(width)} x WOF",
        )
    ]


def _grouped_center_pieces(
    quilt: Quilt,
    rects: list[tuple[str, int, int]],
    source: str,
) -> list[CutPiece]:
    """Group (fabric, finished w, finished h) rectangles into cut-list lines,
    ordered by palette then descending size."""
    add = quilt.settings.cut_add
    counts = Counter(rects)
    palette_order = {f.id: i for i, f in enumerate(quilt.palette.fabrics)}
    pieces = []
    for (fabric_id, fw, fh), qty in sorted(
        counts.items(), key=lambda kv: (palette_order[kv[0][0]], -kv[0][1], -kv[0][2])
    ):
        pieces.append(
            CutPiece(
                fabric_id=fabric_id,
                component="center",
                source=source,
                finished_width=fw,
                finished_height=fh,
                cut_width=fw + add,
                cut_height=fh + add,
                quantity=qty,
                label=_size_label(fw, fh, fw + add, fh + add),
            )
        )
    return pieces


# --- shared assembly + metrics -----------------------------------------------


def _row_sequence(structure: BlockStructure, block_row: int) -> str:
    return " ".join(structure.label(idx)[-1] for idx in structure.layout[block_row])


def _finishing_steps(
    quilt: Quilt, structure: BlockStructure | None, number: int
) -> tuple[list[AssemblyStep], int]:
    """Join rows, attach borders, prepare and attach binding. Returns steps and
    the seam count they contribute."""
    steps: list[AssemblyStep] = []
    seams = 0
    if structure is not None:
        block_rows = len(structure.layout)
        blocks_across = len(structure.layout[0])
        for br in range(block_rows):
            steps.append(
                AssemblyStep(
                    number=number,
                    title=f"Join block row {br + 1} of {block_rows}",
                    detail=(
                        f"Sew the {blocks_across} blocks left to right: "
                        f"{_row_sequence(structure, br)}."
                    ),
                )
            )
            number += 1
            seams += blocks_across - 1
        steps.append(
            AssemblyStep(
                number=number,
                title="Join the block rows",
                detail=f"Sew the {block_rows} rows together top to bottom.",
            )
        )
        number += 1
        seams += block_rows - 1
    else:
        rows = quilt.center.rows
        steps.append(
            AssemblyStep(
                number=number,
                title="Join the cell rows",
                detail=f"Sew the {rows} rows of cells together top to bottom.",
            )
        )
        number += 1
        seams += rows - 1
    for i, band in enumerate(quilt.borders, start=1):
        steps.append(
            AssemblyStep(
                number=number,
                title=f"Attach border {i}",
                detail=f"{format_inches(band.width)} finished band, all four sides.",
                substeps=[
                    "Sew the two side pieces, press toward the border.",
                    "Sew the top and bottom pieces, press toward the border.",
                ],
            )
        )
        number += 1
        seams += 4
    strips = ceil(quilt.binding_length / quilt.settings.wof)
    steps.append(
        AssemblyStep(
            number=number,
            title="Prepare the binding",
            detail=(
                f"Join {strips} WOF strips of "
                f"{format_inches(quilt.binding.strip_width)} end to end; "
                "press in half lengthwise."
            ),
        )
    )
    number += 1
    seams += strips - 1
    steps.append(
        AssemblyStep(
            number=number,
            title="Bind the quilt",
            detail="Attach the binding to the quilt edge; miter the corners.",
        )
    )
    number += 1
    seams += 1
    return steps, seams


def _metrics(
    quilt: Quilt,
    strategy: str,
    cut_pieces: list[CutPiece],
    strip_sets: list[StripSet],
    cut_count: int,
    seam_count: int,
) -> PlanMetrics:
    piece_count = sum(p.quantity for p in cut_pieces if p.component != "binding")
    total_sets = sum(s.sets_needed for s in strip_sets)
    yardage = compute_yardage_from_components(quilt, strategy, cut_pieces, strip_sets)
    wof = quilt.settings.wof
    purchased = sum(
        line.quarter_yards * QUARTER_YARD * wof for line in yardage.lines if line.fabric_id
    )
    cut_area = sum(cut_area_by_fabric(quilt, cut_pieces, strip_sets).values())
    waste = (purchased - cut_area) / purchased if purchased else 0.0
    sqft = quilt.finished_width * quilt.finished_height / SQFT
    return PlanMetrics(
        piece_count=piece_count,
        cut_count=cut_count,
        seam_count=seam_count,
        strip_set_count=total_sets,
        waste=waste,
        # all v1 strategies cut rectilinear pieces parallel to the grain
        bias_percent=0.0,
        difficulty=round(log10(piece_count) + seam_count / sqft),
        time_minutes=round(piece_count * 1.5 + total_sets * 10),
    )


# --- historical ---------------------------------------------------------------


def plan_historical(quilt: Quilt) -> ConstructionPlan:
    """Patch by patch: one cut square per cell, blocks pieced row by row."""
    grid = quilt.center
    cell = grid.cell_size
    rects = [(fid, cell, cell) for row in grid.cells for fid in row]
    center = _grouped_center_pieces(quilt, rects, "rotary")
    pieces = center + border_pieces(quilt) + binding_pieces(quilt)

    structure = infer_block_structure(grid.cells)
    steps: list[AssemblyStep] = []
    number = 1
    seams = 0
    if structure is not None:
        p = structure.size
        for idx, block in enumerate(structure.types):
            substeps = [
                f"Row {r + 1}: sew {' '.join(block[r])} left to right." for r in range(p)
            ]
            substeps.append(f"Join the {p} rows to finish the block.")
            steps.append(
                AssemblyStep(
                    number=number,
                    title=f"Piece {structure.label(idx)} (make {structure.counts[idx]})",
                    detail=f"{p} x {p} cells of {format_inches(cell)} finished.",
                    substeps=substeps,
                )
            )
            number += 1
            seams += structure.counts[idx] * (p * p - 1)
    else:
        rows, cols = grid.rows, grid.cols
        steps.append(
            AssemblyStep(
                number=number,
                title="Piece each cell row",
                detail=f"Sew each of the {rows} rows of {cols} cells left to right.",
            )
        )
        number += 1
        seams += rows * (cols - 1)
    finishing, finishing_seams = _finishing_steps(quilt, structure, number)
    steps.extend(finishing)
    seams += finishing_seams

    cut_count = sum(p.quantity for p in pieces)
    return ConstructionPlan(
        strategy="historical",
        quilt_name=quilt.metadata.name,
        cut_pieces=pieces,
        strip_sets=[],
        assembly=steps,
        metrics=_metrics(quilt, "historical", pieces, [], cut_count, seams),
    )


# --- strip ---------------------------------------------------------------------


def plan_strip(quilt: Quilt) -> ConstructionPlan:
    """Block-granularity WOF strip sets: distinct block-row signatures become
    strip sets, crosscut into segments, segments stacked into blocks."""
    grid = quilt.center
    structure = infer_block_structure(grid.cells)
    if structure is None:
        raise ValueError(
            "strip strategy requires a block-periodic grid "
            "(no repeating block structure found)"
        )
    p = structure.size
    cell = grid.cell_size
    add = quilt.settings.cut_add
    segment_width = cell + add
    wof = quilt.settings.wof
    per_set = wof // segment_width

    # Distinct row signatures in first-appearance order (block label, then row).
    signatures: list[tuple[str, ...]] = []
    sig_index: dict[tuple[str, ...], int] = {}
    needed: Counter[int] = Counter()
    block_rows_by_type: list[list[int]] = []
    for idx, block in enumerate(structure.types):
        rows_for_block = []
        for r in range(p):
            sig = block[r]
            if sig not in sig_index:
                sig_index[sig] = len(signatures)
                signatures.append(sig)
            needed[sig_index[sig]] += structure.counts[idx]
            rows_for_block.append(sig_index[sig])
        block_rows_by_type.append(rows_for_block)

    strip_sets = [
        StripSet(
            id=f"SS{i + 1}",
            sequence=list(sig),
            strip_cut_width=segment_width,
            segment_cut_width=segment_width,
            segments_needed=needed[i],
            segments_per_set=per_set,
            sets_needed=ceil(needed[i] / per_set),
        )
        for i, sig in enumerate(signatures)
    ]

    rects = [(fid, cell, cell) for row in grid.cells for fid in row]
    center = _grouped_center_pieces(quilt, rects, "strip_set")
    pieces = center + border_pieces(quilt) + binding_pieces(quilt)

    steps: list[AssemblyStep] = []
    number = 1
    seams = 0
    for strip_set in strip_sets:
        steps.append(
            AssemblyStep(
                number=number,
                title=f"Sew strip set {strip_set.id} (make {strip_set.sets_needed})",
                detail=(
                    f"{len(strip_set.sequence)} WOF strips cut "
                    f"{format_inches(strip_set.strip_cut_width)}, sewn lengthwise "
                    f"in order: {' '.join(strip_set.sequence)}."
                ),
            )
        )
        number += 1
        seams += (len(strip_set.sequence) - 1) * strip_set.sets_needed
    steps.append(
        AssemblyStep(
            number=number,
            title="Crosscut the strip sets",
            detail=f"Crosscut every set at {format_inches(segment_width)}.",
            substeps=[
                f"{s.id}: cut {s.segments_needed} segments "
                f"({s.sets_needed} sets x {s.segments_per_set} per set)."
                for s in strip_sets
            ],
        )
    )
    number += 1
    for idx, rows_for_block in enumerate(block_rows_by_type):
        sequence = " ".join(f"SS{i + 1}" for i in rows_for_block)
        steps.append(
            AssemblyStep(
                number=number,
                title=f"Assemble {structure.label(idx)} (make {structure.counts[idx]})",
                detail=f"Stack segments top to bottom: {sequence}.",
            )
        )
        number += 1
        seams += structure.counts[idx] * (p - 1)
    finishing, finishing_seams = _finishing_steps(quilt, structure, number)
    steps.extend(finishing)
    seams += finishing_seams

    strip_cuts = sum(s.sets_needed * len(s.sequence) for s in strip_sets)
    crosscuts = sum(s.segments_needed for s in strip_sets)
    rotary = sum(p_.quantity for p_ in pieces if p_.source == "rotary" and p_.component != "center")
    cut_count = strip_cuts + crosscuts + rotary
    return ConstructionPlan(
        strategy="strip",
        quilt_name=quilt.metadata.name,
        cut_pieces=pieces,
        strip_sets=strip_sets,
        assembly=steps,
        metrics=_metrics(quilt, "strip", pieces, strip_sets, cut_count, seams),
    )


# --- modern --------------------------------------------------------------------


def _decompose(cells: BlockGrid) -> list[tuple[int, int, int, int, str]]:
    """Greedy maximal-rectangle cover of same-fabric cells.

    Returns (row, col, height, width, fabric) in discovery order. Tie-break:
    largest area, then topmost, then leftmost, then widest -- deterministic.
    """
    rows, cols = len(cells), len(cells[0])
    covered = [[False] * cols for _ in range(rows)]
    out: list[tuple[int, int, int, int, str]] = []
    remaining = rows * cols
    while remaining:
        best: tuple[int, int, int, int, int] | None = None  # area, -r, -c, w, h
        for r in range(rows):
            for c in range(cols):
                if covered[r][c]:
                    continue
                fabric = cells[r][c]
                width = cols - c
                for h in range(1, rows - r + 1):
                    run = 0
                    while (
                        run < width
                        and not covered[r + h - 1][c + run]
                        and cells[r + h - 1][c + run] == fabric
                    ):
                        run += 1
                    width = run
                    if width == 0:
                        break
                    key = (width * h, -r, -c, width, h)
                    if best is None or key > best:
                        best = key
        assert best is not None
        area, neg_r, neg_c, w, h = best
        r0, c0 = -neg_r, -neg_c
        for r in range(r0, r0 + h):
            for c in range(c0, c0 + w):
                covered[r][c] = True
        remaining -= w * h
        out.append((r0, c0, h, w, cells[r0][c0]))
    return out


def plan_modern(quilt: Quilt) -> ConstructionPlan:
    """Merge same-fabric adjacent cells into larger cut pieces (block-local:
    no seam is visually required inside a same-fabric rectangle)."""
    grid = quilt.center
    cell = grid.cell_size
    structure = infer_block_structure(grid.cells)

    rects: list[tuple[str, int, int]] = []
    seams = 0
    steps: list[AssemblyStep] = []
    number = 1
    if structure is not None:
        decompositions = [_decompose(block) for block in structure.types]
        for idx, decomposition in enumerate(decompositions):
            count = structure.counts[idx]
            for _r, _c, h, w, fabric in decomposition:
                rects.extend([(fabric, w * cell, h * cell)] * count)
            seams += count * (len(decomposition) - 1)
            substeps = [
                f"{format_inches(w * cell)} x {format_inches(h * cell)} {fabric} "
                f"at row {r + 1}, col {c + 1}"
                for r, c, h, w, fabric in decomposition
            ]
            steps.append(
                AssemblyStep(
                    number=number,
                    title=(
                        f"Piece {structure.label(idx)} from merged pieces "
                        f"(make {structure.counts[idx]})"
                    ),
                    detail=f"{len(decomposition)} pieces replace "
                    f"{structure.size * structure.size} squares.",
                    substeps=substeps,
                )
            )
            number += 1
    else:
        decomposition = _decompose(tuple(tuple(row) for row in grid.cells))
        for _r, _c, h, w, fabric in decomposition:
            rects.append((fabric, w * cell, h * cell))
        seams += len(decomposition) - 1
        steps.append(
            AssemblyStep(
                number=number,
                title="Piece the top from merged pieces",
                detail=f"{len(decomposition)} merged pieces cover the center field.",
            )
        )
        number += 1

    center = _grouped_center_pieces(quilt, rects, "rotary")
    pieces = center + border_pieces(quilt) + binding_pieces(quilt)
    finishing, finishing_seams = _finishing_steps(quilt, structure, number)
    steps.extend(finishing)
    seams += finishing_seams

    cut_count = sum(p_.quantity for p_ in pieces)
    return ConstructionPlan(
        strategy="modern",
        quilt_name=quilt.metadata.name,
        cut_pieces=pieces,
        strip_sets=[],
        assembly=steps,
        metrics=_metrics(quilt, "modern", pieces, [], cut_count, seams),
    )


# --- registry ------------------------------------------------------------------


def _stub(name: str, human: str):
    def planner(quilt: Quilt) -> ConstructionPlan:
        raise NotImplementedError(
            f"{human} ({name}) is not implemented in v1; "
            "available strategies: historical, strip, modern"
        )

    return planner


STRATEGIES = {
    "historical": plan_historical,
    "strip": plan_strip,
    "modern": plan_modern,
    "fpp": _stub("fpp", "Foundation paper piecing"),
    "epp": _stub("epp", "English paper piecing"),
    "hand": _stub("hand", "Hand piecing"),
    "longarm": _stub("longarm", "Longarm quilting"),
}


def get_strategy(name: str):
    if name not in STRATEGIES:
        raise KeyError(f"unknown strategy {name!r}; available: {', '.join(STRATEGIES)}")
    return STRATEGIES[name]
