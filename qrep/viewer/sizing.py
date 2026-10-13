"""Sizing math for the viewer, mirrored exactly by the JS in template.html.

The JS cannot call Python, so the template reimplements these formulas with
the same half-up integer arithmetic; these are the tested source of truth,
and build_view_config feeds the JS the same numbers. All lengths are integer
eighths.

PRESETS and round_div live in qrep/model/sizing.py (A10) and are re-exported
here, so this module's callers keep working until A7 deletes the viewer.
"""

from pydantic import BaseModel

from qrep.construct.strategies import infer_block_structure
from qrep.model.schema import Quilt
from qrep.model.sizing import PRESETS, round_div

__all__ = [
    "PRESETS",
    "SizingResult",
    "build_view_config",
    "locked_resize",
    "round_div",
    "unlocked_resize",
]


class SizingResult(BaseModel):
    rows: int
    cols: int
    cell_size: int
    achieved_width: int
    achieved_height: int


def locked_resize(
    rows: int,
    cols: int,
    cell_size: int,
    border_total: int,
    target_width: int | None = None,
    target_height: int | None = None,
    target_cell: int | None = None,
) -> SizingResult:
    """Proportion lock ON: grid counts never change; only cell size scales.

    border_total is the SUM of band widths (added twice per axis). Exactly one
    target should be given; width wins over height over cell if several are.
    """
    if target_width is not None:
        cell = max(1, round_div(max(target_width - 2 * border_total, 0), cols))
    elif target_height is not None:
        cell = max(1, round_div(max(target_height - 2 * border_total, 0), rows))
    elif target_cell is not None:
        cell = max(1, target_cell)
    else:
        cell = cell_size
    return SizingResult(
        rows=rows,
        cols=cols,
        cell_size=cell,
        achieved_width=cols * cell + 2 * border_total,
        achieved_height=rows * cell + 2 * border_total,
    )


def unlocked_resize(
    rows: int,
    cols: int,
    cell_size: int,
    border_total: int,
    block: int,
    target_width: int | None = None,
    target_height: int | None = None,
) -> SizingResult:
    """Proportion lock OFF: cell size fixed; whole blocks added or removed,
    each axis independent and quantized to the block size."""
    new_cols, new_rows = cols, rows
    if target_width is not None:
        blocks = max(1, round_div(max(target_width - 2 * border_total, 0), block * cell_size))
        new_cols = blocks * block
    if target_height is not None:
        blocks = max(1, round_div(max(target_height - 2 * border_total, 0), block * cell_size))
        new_rows = blocks * block
    return SizingResult(
        rows=new_rows,
        cols=new_cols,
        cell_size=cell_size,
        achieved_width=new_cols * cell_size + 2 * border_total,
        achieved_height=new_rows * cell_size + 2 * border_total,
    )


def build_view_config(quilt: Quilt) -> dict:
    """The config object embedded in the viewer; the JS reads exactly this."""
    structure = infer_block_structure(quilt.center.cells)
    if structure is None:
        block = 1
        checker = False
        block_types = None
        layout = None
    else:
        block = structure.size
        layout = structure.layout
        block_types = [[list(row) for row in t] for t in structure.types]
        checker = len(structure.types) == 2 and all(
            layout[br][bc] == (br + bc) % 2
            for br in range(len(layout))
            for bc in range(len(layout[0]))
        )
    return {
        "rows": quilt.center.rows,
        "cols": quilt.center.cols,
        "cellSize": quilt.center.cell_size,
        "borders": [b.width for b in quilt.borders],
        "block": block,
        "checker": checker,
        "wof": quilt.settings.wof,
        "presets": [{"name": n, "w": w, "h": h} for n, w, h in PRESETS],
        "blockTypes": block_types,
        "layout": layout,
    }
