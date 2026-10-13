"""Merged runs, strip-set signatures and the rows layout (PATTERN-SPEC M-04, M-05, M-07 c).

The planner that picks one method (A3b) chooses from this data. A line is a row
of squares, or a column when the rows layout turns to columns. Lengths are
integer eighths, and every cut size is finished + the seam allowances (MATH.md F1).
"""

from collections import Counter
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel

from qrep.construct.blocks import BlockStructure, Square, grid_squares
from qrep.construct.cutting import pieces_per_strip
from qrep.model.schema import Quilt

# M-05: a strip set sews 2 to 7 strips.
MIN_SET_STRIPS = 2
MAX_SET_STRIPS = 7


def _ceil_div(numerator: int, denominator: int) -> int:
    return -(-numerator // denominator)


class Piece(BaseModel):
    """A merged run of plain squares, or one square of a unit (cut as A3c says)."""

    kind: Literal["piece", "unit"]
    fabric_id: str | None  # None for a unit square
    start: int  # first square along the line
    squares: int  # squares along the line
    lines: int = 1  # lines the piece spans across
    cut_length: int | None = None  # along the line; None for a unit square
    cut_width: int | None = None


class Band(BaseModel):
    """One line, or consecutive single-fabric lines merged into rectangles."""

    line: int
    lines: int
    pieces: list[Piece]

    @property
    def has_unit(self) -> bool:
        return any(piece.kind == "unit" for piece in self.pieces)

    @property
    def single_fabric(self) -> bool:
        return not self.has_unit and len({piece.fabric_id for piece in self.pieces}) == 1


def _most_squares(cell: int, cut_add: int, usable: int) -> int:
    most = (usable - cut_add) // cell
    if most < 1:
        raise ValueError(
            f"a square cut {cell + cut_add} long does not fit the usable width {usable}"
        )
    return most


def _split(count: int, most: int) -> list[int]:
    # M-04 fixes the count, the fewest pieces that fit, and leaves the sizes
    # open; near-equal sizes give repeated runs one cut size instead of a full
    # piece and a remainder.
    parts = _ceil_div(count, most)
    size, longer = divmod(count, parts)
    return [size + 1] * longer + [size] * (parts - longer)


def merge_line(squares: Sequence[Square], cell: int, cut_add: int, usable: int) -> list[Piece]:
    """M-04 along one line: each run of plain squares of one fabric is one piece,
    split at square boundaries when its cut would be longer than the usable width."""
    most = _most_squares(cell, cut_add, usable)
    pieces: list[Piece] = []
    i = 0
    while i < len(squares):
        if not squares[i].plain:
            pieces.append(Piece(kind="unit", fabric_id=None, start=i, squares=1))
            i += 1
            continue
        fabric = squares[i].fabric_id
        end = i
        while end < len(squares) and squares[end].plain and squares[end].fabric_id == fabric:
            end += 1
        start = i
        for count in _split(end - i, most):
            pieces.append(
                Piece(
                    kind="piece",
                    fabric_id=fabric,
                    start=start,
                    squares=count,
                    cut_length=count * cell + cut_add,
                    cut_width=cell + cut_add,
                )
            )
            start += count
        i = end
    return pieces


def _one_fabric(line: Sequence[Square]) -> bool:
    return all(square.plain and square.fabric_id == line[0].fabric_id for square in line)


def decompose_lines(
    grid: Sequence[Sequence[Square]], cell: int, cut_add: int, usable: int
) -> list[Band]:
    """M-04 over a block or a whole grid: merged runs in every line, and
    consecutive lines of one plain fabric across the full width as one band of
    rectangles, capped at the usable width in both directions."""
    most = _most_squares(cell, cut_add, usable)
    bands: list[Band] = []
    r = 0
    while r < len(grid):
        pieces = merge_line(grid[r], cell, cut_add, usable)
        if not _one_fabric(grid[r]):
            bands.append(Band(line=r, lines=1, pieces=pieces))
            r += 1
            continue
        end = r + 1
        while (
            end < len(grid)
            and _one_fabric(grid[end])
            and grid[end][0].fabric_id == grid[r][0].fabric_id
        ):
            end += 1
        line = r
        for lines in _split(end - r, most):
            stacked = [
                piece.model_copy(update={"lines": lines, "cut_width": lines * cell + cut_add})
                for piece in pieces
            ]
            bands.append(Band(line=line, lines=lines, pieces=stacked))
            line += lines
        r = end
    return bands


class Signature(BaseModel):
    """A strip set: one strip per merged piece, sewn in order and crosscut."""

    fabric_ids: list[str]
    strip_widths: list[int]  # each piece's cut length
    segment_cut_width: int
    segments_needed: int
    per_set: int
    sets: int

    @property
    def long_seams(self) -> int:
        return (len(self.fabric_ids) - 1) * self.sets


class RecipeBand(BaseModel):
    band: Band
    role: Literal["strip_set", "rectangle", "pieced"]
    signature: int | None = None  # index into BlockDecomposition.signatures
    reversed: bool = False  # the segment is turned end for end


class CutLine(BaseModel):
    """Identical pieces of one fabric, short side first (PATTERN-SPEC C-10).
    A rectangle and a piece of one size share a line, because each line gets
    its own strips (MATH.md F2)."""

    fabric_id: str
    short: int
    long: int
    quantity: int


class BlockDecomposition(BaseModel):
    structure: BlockStructure
    recipes: list[list[RecipeBand]]  # per block type, top to bottom
    signatures: list[Signature]
    cut_lines: list[CutLine]  # pieces cut one by one; strip sets are not here

    @property
    def long_seams(self) -> int:
        return sum(signature.long_seams for signature in self.signatures)

    def set_strips(self) -> Counter[tuple[str, int]]:
        """Strips for all strip sets by (fabric, strip width)."""
        strips: Counter[tuple[str, int]] = Counter()
        for signature in self.signatures:
            for fabric, width in zip(signature.fabric_ids, signature.strip_widths, strict=True):
                strips[(fabric, width)] += signature.sets
        return strips


def _add_cut_lines(lines: dict[tuple[str, int, int], int], band: Band, quantity: int) -> None:
    for piece in band.pieces:
        if piece.kind == "piece":
            short, long = sorted((piece.cut_length, piece.cut_width))
            key = (piece.fabric_id, short, long)
            lines[key] = lines.get(key, 0) + quantity


def _cut_line_list(lines: dict[tuple[str, int, int], int]) -> list[CutLine]:
    return [
        CutLine(fabric_id=fabric, short=short, long=long, quantity=quantity)
        for (fabric, short, long), quantity in lines.items()
    ]


def _can_strip_piece(band: Band) -> bool:
    # A row with a unit is sewn in the block steps. Two strips of one fabric
    # side by side (a single-fabric row, or a run split at the cap) would sew a
    # fabric to itself (M-05; engine-05).
    return (
        band.lines == 1
        and not band.has_unit
        and MIN_SET_STRIPS <= len(band.pieces) <= MAX_SET_STRIPS
        and all(a.fabric_id != b.fabric_id for a, b in zip(band.pieces, band.pieces[1:]))
    )


def decompose_blocks(quilt: Quilt, structure: BlockStructure) -> BlockDecomposition:
    """Per block type, merged bands; strip-set signatures shared with their
    reverse and kept only when they fill half a set (L-03); the rest cut lines."""
    cell = quilt.center.cell_size
    cut_add = quilt.settings.cut_add
    usable = quilt.settings.wof
    segment = cell + cut_add
    per_set = pieces_per_strip(segment, usable)
    bands_by_type = [decompose_lines(block, cell, cut_add, usable) for block in structure.types]

    found: dict[tuple[tuple[str | None, int | None], ...], tuple[int, bool]] = {}
    shapes: list[tuple[tuple[str | None, int | None], ...]] = []
    needed: list[int] = []
    for kind, bands in enumerate(bands_by_type):
        for band in bands:
            if not _can_strip_piece(band):
                continue
            shape = tuple((piece.fabric_id, piece.cut_length) for piece in band.pieces)
            if shape not in found:
                found[shape] = (len(shapes), False)
                found.setdefault(shape[::-1], (len(shapes), True))
                shapes.append(shape)
                needed.append(0)
            needed[found[shape][0]] += structure.counts[kind]

    # L-03: below half a set, most of the segments a set yields go unused.
    kept = [i for i in range(len(shapes)) if 2 * needed[i] >= per_set]
    renumber = {old: new for new, old in enumerate(kept)}
    signatures = [
        Signature(
            fabric_ids=[fabric for fabric, _ in shapes[i]],
            strip_widths=[width for _, width in shapes[i]],
            segment_cut_width=segment,
            segments_needed=needed[i],
            per_set=per_set,
            sets=_ceil_div(needed[i], per_set),
        )
        for i in kept
    ]

    recipes: list[list[RecipeBand]] = []
    lines: dict[tuple[str, int, int], int] = {}
    for kind, bands in enumerate(bands_by_type):
        recipe = []
        for band in bands:
            shape = tuple((piece.fabric_id, piece.cut_length) for piece in band.pieces)
            match = found.get(shape) if _can_strip_piece(band) else None
            if match is not None and match[0] in renumber:
                recipe.append(
                    RecipeBand(
                        band=band, role="strip_set", signature=renumber[match[0]], reversed=match[1]
                    )
                )
                continue
            role = "rectangle" if band.single_fabric else "pieced"
            recipe.append(RecipeBand(band=band, role=role))
            _add_cut_lines(lines, band, structure.counts[kind])
        recipes.append(recipe)
    return BlockDecomposition(
        structure=structure, recipes=recipes, signatures=signatures, cut_lines=_cut_line_list(lines)
    )


class RowsLayout(BaseModel):
    axis: Literal["rows", "columns"]
    bands: list[Band]
    cut_lines: list[CutLine]

    @property
    def piece_count(self) -> int:
        return sum(1 for band in self.bands for piece in band.pieces if piece.kind == "piece")


def _units_whole(quilt: Quilt, axis: Literal["rows", "columns"]) -> bool:
    # A flying goose covers two squares; sewn across two lines it would need a
    # partial seam (M-13).
    index = 0 if axis == "rows" else 1
    return all(
        len({square[index] for square in unit.squares()}) == 1
        for unit in quilt.center.unit_map or []
    )


def rows_layout(quilt: Quilt) -> RowsLayout:
    """M-07 c: the grid sewn line by line from merged pieces and units, by
    columns only when that cuts fewer pieces. Each unit is made once either
    way, so only plain pieces decide, among the axes that keep every unit in
    one line."""
    cell = quilt.center.cell_size
    cut_add = quilt.settings.cut_add
    usable = quilt.settings.wof
    rows = grid_squares(quilt.center)
    columns = [list(column) for column in zip(*rows, strict=True)]
    candidates = [
        RowsLayout(axis=axis, bands=decompose_lines(lines, cell, cut_add, usable), cut_lines=[])
        for axis, lines in (("rows", rows), ("columns", columns))
        if _units_whole(quilt, axis)
    ]
    if not candidates:
        raise ValueError(
            "flying geese lie both across and down, so no row or column layout keeps "
            "every goose whole"
        )
    # min keeps the first of equals, so rows win a tie.
    layout = min(candidates, key=lambda candidate: candidate.piece_count)
    cut_lines: dict[tuple[str, int, int], int] = {}
    for band in layout.bands:
        _add_cut_lines(cut_lines, band, 1)
    return layout.model_copy(update={"cut_lines": _cut_line_list(cut_lines)})
