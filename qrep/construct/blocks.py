"""Block structure: the blocks a quilt center is sewn from (PATTERN-SPEC M-03).

A confirmed block structure (Quilt.confirmed_blocks) is a user fact and is
taken as it stands, so a few misread squares cannot change the method. Without
one, a square period is accepted only when the blocks it gives pass the
plausibility gate with the L-13 numbers; a random grid gets no structure.

Two blocks are the same type only when every square matches in fabric and in
unit, so a block with a half-square triangle never shares a type with one that
has a plain square there.
"""

import json
from collections.abc import Sequence
from math import gcd
from typing import Literal

from pydantic import BaseModel, ConfigDict

from qrep.model.schema import GridRegion, Quilt
from qrep.model.unitmap import PlainUnit

# L-13 (PATTERN-SPEC S0): at most 8 block types, at most one type used only
# once, and no more types than a quarter of the blocks.
MAX_BLOCK_TYPES = 8
MAX_SINGLE_USE_TYPES = 1
BLOCKS_PER_TYPE = 4


class Square(BaseModel):
    """One square: its cell fabric, and for a pieced unit a descriptor that
    names the unit (kind, fabrics, orientation) and which of its squares this is."""

    model_config = ConfigDict(frozen=True)

    fabric_id: str
    unit: str | None = None

    @property
    def plain(self) -> bool:
        return self.unit is None


Block = list[list[Square]]


def grid_squares(region: GridRegion) -> list[list[Square]]:
    """The region's squares in rows. The unit descriptor leaves out position
    and confidence, so equal blocks read at different confidence match."""
    units: dict[tuple[int, int], str] = {}
    for unit in region.unit_map or []:
        if isinstance(unit, PlainUnit):
            continue
        fields = unit.model_dump(mode="json", exclude={"row", "col", "confidence"})
        name = json.dumps(fields, sort_keys=True)
        for offset, square in enumerate(unit.squares()):
            units[square] = f"{name}#{offset}"
    return [
        [Square(fabric_id=fabric, unit=units.get((r, c))) for c, fabric in enumerate(row)]
        for r, row in enumerate(region.cells)
    ]


class BlockStructure(BaseModel):
    source: Literal["confirmed", "gate"]
    blocks_across: int
    blocks_down: int
    squares_across: int
    squares_down: int
    types: list[Block]  # by first appearance in reading order
    layout: list[list[int]]  # type index per block row, block column
    counts: list[int]  # blocks of each type


def tile_blocks(
    squares: Sequence[Sequence[Square]],
    squares_across: int,
    squares_down: int,
    source: Literal["confirmed", "gate"],
) -> BlockStructure:
    rows, cols = len(squares), len(squares[0])
    if rows % squares_down or cols % squares_across:
        raise ValueError(
            f"blocks of {squares_across} x {squares_down} squares do not tile a "
            f"{cols} x {rows} grid"
        )
    types: list[Block] = []
    index: dict[tuple[tuple[Square, ...], ...], int] = {}
    layout: list[list[int]] = []
    for top in range(0, rows, squares_down):
        layout_row = []
        for left in range(0, cols, squares_across):
            block = tuple(
                tuple(squares[top + r][left : left + squares_across]) for r in range(squares_down)
            )
            if block not in index:
                index[block] = len(types)
                types.append([list(row) for row in block])
            layout_row.append(index[block])
        layout.append(layout_row)
    counts = [0] * len(types)
    for layout_row in layout:
        for idx in layout_row:
            counts[idx] += 1
    return BlockStructure(
        source=source,
        blocks_across=cols // squares_across,
        blocks_down=rows // squares_down,
        squares_across=squares_across,
        squares_down=squares_down,
        types=types,
        layout=layout,
        counts=counts,
    )


def passes_block_gate(counts: Sequence[int]) -> bool:
    """M-03 with the L-13 numbers, for a structure nobody confirmed."""
    single_use = sum(1 for count in counts if count == 1)
    return (
        len(counts) <= MAX_BLOCK_TYPES
        and single_use <= MAX_SINGLE_USE_TYPES
        and BLOCKS_PER_TYPE * len(counts) <= sum(counts)
    )


def _units_inside_blocks(region: GridRegion, squares_across: int, squares_down: int) -> bool:
    # A block seam through a flying goose could only be sewn with a partial
    # seam (M-13), so such a period is no block structure.
    for unit in region.unit_map or []:
        blocks = {(r // squares_down, c // squares_across) for r, c in unit.squares()}
        if len(blocks) > 1:
            return False
    return True


def block_structure(quilt: Quilt) -> BlockStructure | None:
    """The confirmed structure when the model has one; otherwise the smallest
    square period whose blocks keep every unit whole and pass the gate, or
    None (engine-11)."""
    region = quilt.center
    squares = grid_squares(region)
    confirmed = quilt.confirmed_blocks
    if confirmed is not None:
        across = confirmed.blocks_across * confirmed.squares_across
        down = confirmed.blocks_down * confirmed.squares_down
        if (across, down) != (region.cols, region.rows):
            raise ValueError(
                f"the confirmed blocks cover {across} x {down} squares, but the grid is "
                f"{region.cols} x {region.rows}"
            )
        return tile_blocks(squares, confirmed.squares_across, confirmed.squares_down, "confirmed")
    g = gcd(region.rows, region.cols)
    for p in range(2, g + 1):
        if g % p == 0 and _units_inside_blocks(region, p, p):
            structure = tile_blocks(squares, p, p, "gate")
            if passes_block_gate(structure.counts):
                return structure
    return None
