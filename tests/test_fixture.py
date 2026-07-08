"""Benchmark fixture tests: exact Double Irish Chain geometry from the design doc."""

from pathlib import Path

from qrep.model import dumps, load
from qrep.model.fixtures import BLOCK_SIZE, make_double_irish_chain

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"


def block_kind(block_row: int, block_col: int) -> str:
    """Block A wherever block row + block col is even; A on all four corners."""
    return "A" if (block_row + block_col) % 2 == 0 else "B"


def test_committed_fixture_validates_and_matches_regeneration():
    committed = load(FIXTURE_PATH)
    regenerated = make_double_irish_chain()
    assert committed == regenerated
    assert FIXTURE_PATH.read_text(encoding="utf-8") == dumps(regenerated)


def test_finished_dimensions_exactly_75_by_90():
    quilt = make_double_irish_chain()
    # center: 9 blocks x 5 cells x 12 eighths = 540 (67.5") wide,
    #         11 blocks x 5 cells x 12 = 660 (82.5") tall
    assert quilt.center.width == 540
    assert quilt.center.height == 660
    # border 30 eighths (3.75") both sides: 540 + 60 = 600 (75"), 660 + 60 = 720 (90")
    assert quilt.finished_width == 600
    assert quilt.finished_height == 720
    # binding: perimeter 2 x (600 + 720) = 2640 (330") + 80 (10") = 2720 (340")
    assert quilt.binding_length == 2720


def test_cell_census():
    quilt = make_double_irish_chain()
    flat = [cell for row in quilt.center.cells for cell in row]
    # 50 A blocks x 21 blue + 49 B blocks x 4 blue = 1050 + 196 = 1246 blue
    assert flat.count("b") == 1246
    # 50 A x 4 cream + 49 B x 21 cream = 200 + 1029 = 1229 cream
    assert flat.count("c") == 1229
    # 45 x 55 = 2475 center cells
    assert len(flat) == 2475


def test_chain_continuity_at_docstring_coordinates():
    """The exact coordinates the fixture docstring ASCII shows.

    Block (0,0) is A, block (0,1) is B. A local (1,4) is global (1,4); B local
    (0,0) is global (0,5): diagonally adjacent, both blue. Likewise A(3,4) at
    global (3,4) and B(4,0) at global (4,5).
    """
    cells = make_double_irish_chain().center.cells
    assert cells[1][4] == "b" and cells[0][5] == "b"
    assert cells[3][4] == "b" and cells[4][5] == "b"


def test_diagonal_blue_pair_across_every_a_to_b_boundary():
    quilt = make_double_irish_chain()
    cells = quilt.center.cells
    block_rows = quilt.center.rows // BLOCK_SIZE
    block_cols = quilt.center.cols // BLOCK_SIZE

    def has_diagonal_blue_pair_horizontal(block_row: int, block_col: int) -> bool:
        """Blue-blue diagonal across the boundary between (br, bc) and (br, bc+1)."""
        left_col = block_col * BLOCK_SIZE + (BLOCK_SIZE - 1)
        right_col = left_col + 1
        top = block_row * BLOCK_SIZE
        for r in range(top, top + BLOCK_SIZE):
            for dr in (-1, 1):
                r2 = r + dr
                if top <= r2 < top + BLOCK_SIZE:
                    if cells[r][left_col] == "b" and cells[r2][right_col] == "b":
                        return True
        return False

    def has_diagonal_blue_pair_vertical(block_row: int, block_col: int) -> bool:
        """Blue-blue diagonal across the boundary between (br, bc) and (br+1, bc)."""
        bottom_row = block_row * BLOCK_SIZE + (BLOCK_SIZE - 1)
        next_row = bottom_row + 1
        left = block_col * BLOCK_SIZE
        for c in range(left, left + BLOCK_SIZE):
            for dc in (-1, 1):
                c2 = c + dc
                if left <= c2 < left + BLOCK_SIZE:
                    if cells[bottom_row][c] == "b" and cells[next_row][c2] == "b":
                        return True
        return False

    checked = 0
    for br in range(block_rows):
        for bc in range(block_cols):
            if bc + 1 < block_cols and block_kind(br, bc) != block_kind(br, bc + 1):
                assert has_diagonal_blue_pair_horizontal(br, bc), f"boundary ({br},{bc})-h"
                checked += 1
            if br + 1 < block_rows and block_kind(br, bc) != block_kind(br + 1, bc):
                assert has_diagonal_blue_pair_vertical(br, bc), f"boundary ({br},{bc})-v"
                checked += 1
    # every adjacent pair alternates A/B: 11 rows x 8 horizontal + 10 x 9 vertical = 178
    assert checked == 178


def test_main_diagonal_blue_8_connected_end_to_end():
    cells = make_double_irish_chain().center.cells
    # (i, i) always lands in an A block at local (i%5, i%5); the A diagonal is
    # all blue (b at (0,0), (1,1), (2,2), (3,3), (4,4)). Consecutive (i, i) and
    # (i+1, i+1) are diagonal neighbors, so all-blue means 8-connected.
    size = min(len(cells), len(cells[0]))  # 45: the diagonal spans the full width
    assert size == 45
    for i in range(size):
        assert cells[i][i] == "b", f"main diagonal broken at ({i},{i})"


def test_fixture_confidences_all_default_to_one():
    quilt = load(FIXTURE_PATH)
    stage = quilt.provenance.effective_stage_confidence()
    assert set(stage) == {"rectify", "palette", "grid", "cells", "repeat", "border"}
    assert all(v == 1.0 for v in stage.values())
    conf = quilt.center.effective_cell_confidence()
    assert len(conf) == 55 and all(len(row) == 45 for row in conf)
    assert all(v == 1.0 for row in conf for v in row)
    # the hand-authored fixture omits the raw arrays entirely
    assert quilt.provenance.stage_confidence == {}
    assert quilt.center.cell_confidence is None
