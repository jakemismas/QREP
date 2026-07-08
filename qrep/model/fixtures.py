'''Benchmark fixture: two-fabric Double Irish Chain.

The traditional Double Irish Chain uses three fabrics; this fixture collapses
dark and medium into one blue, which is a legitimate two-fabric variant --
do not research pattern variants, the geometry below is the contract.

One horizontally adjacent Block A | Block B pair (b = chain blue, c = cream),
local coordinates are (row, col):

        Block A         Block B
    col 01234       col 01234
  row 0 b b c b b | b c c c b
  row 1 b b b b b | c c c c c
  row 2 c b b b c | c c c c c
  row 3 b b b b b | c c c c c
  row 4 b b c b b | b c c c b

Chain continuity across the A-to-B boundary is diagonal: A(1,4) is blue and
B(0,0) is blue (diagonally adjacent), likewise A(3,4) and B(4,0). The main
diagonal of the center field runs through Block A diagonals -- A(0,0), A(1,1),
A(2,2), A(3,3), A(4,4) are all blue -- so blue is 8-connected end to end.
'''

from qrep.model.schema import (
    Binding,
    BorderBand,
    Fabric,
    GridRegion,
    Palette,
    Quilt,
    QuiltMetadata,
)

# 5x5 block rows, top to bottom. Block A: 21 blue, 4 cream. Block B: 4 blue, 21 cream.
BLOCK_A = ("bbcbb", "bbbbb", "cbbbc", "bbbbb", "bbcbb")
BLOCK_B = ("bcccb", "ccccc", "ccccc", "ccccc", "bcccb")
BLOCK_SIZE = 5


def make_double_irish_chain(
    blocks_across: int = 9,
    blocks_down: int = 11,
    cell_size: int = 12,
    border_width: int = 30,
) -> Quilt:
    """Build the benchmark quilt: 9x11 blocks of 1.5in cells, 3.75in cream border.

    Block A sits wherever block row + block col is even, so with both counts
    odd Block A lands on all four corners. Defaults give a finished top of
    exactly 75in x 90in (600 x 720 eighths).
    """
    if blocks_across % 2 == 0 or blocks_down % 2 == 0:
        raise ValueError("block counts must both be odd so Block A lands on all four corners")

    rows = blocks_down * BLOCK_SIZE
    cols = blocks_across * BLOCK_SIZE
    cells: list[list[str]] = []
    for r in range(rows):
        row_chars: list[str] = []
        for c in range(cols):
            block = BLOCK_A if (r // BLOCK_SIZE + c // BLOCK_SIZE) % 2 == 0 else BLOCK_B
            row_chars.append(block[r % BLOCK_SIZE][c % BLOCK_SIZE])
        cells.append(row_chars)

    return Quilt(
        metadata=QuiltMetadata(
            name="Double Irish Chain 75x90",
            notes=(
                "Benchmark fixture: two-fabric Double Irish Chain, light blue chain "
                "on cream. 1.5in finished cells, 5x5 blocks, 9x11 block layout, "
                "3.75in cream border, blue binding."
            ),
        ),
        palette=Palette(
            fabrics=[
                Fabric(id="b", name="Chain blue", color="#9db8d9"),
                Fabric(id="c", name="Background cream", color="#f2e8d5"),
            ]
        ),
        center=GridRegion(rows=rows, cols=cols, cell_size=cell_size, cells=cells),
        borders=[BorderBand(fabric_id="c", width=border_width)],
        binding=Binding(fabric_id="b", strip_width=20),
    )
