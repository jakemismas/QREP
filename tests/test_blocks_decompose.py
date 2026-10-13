"""A3a: block structure, merged runs, strip-set signatures and the rows layout.

Every expected value is computed by hand in the comment beside it, from
PATTERN-SPEC section 3 (M-03 to M-07, the worked example), its literals L-03
and L-13, and MATH.md F1 to F3. Lengths are eighths: 1 in = 8, and a square
cut size is finished + 1/2 in (F1), so a 1 1/2 in square cuts 12 + 4 = 16.
"""

import random
from pathlib import Path

import pytest

from qrep.construct.blocks import (
    Square,
    block_structure,
    grid_squares,
    passes_block_gate,
    tile_blocks,
)
from qrep.construct.cutting import strip_yield
from qrep.construct.decompose import (
    decompose_blocks,
    decompose_lines,
    merge_line,
    rows_layout,
)
from qrep.model.fixtures import BLOCK_A, BLOCK_B, make_double_irish_chain
from qrep.model.io import load
from qrep.model.schema import (
    Binding,
    ConfirmedBlocks,
    Fabric,
    GridRegion,
    Palette,
    Quilt,
    QuiltMetadata,
    Settings,
)
from qrep.model.unitmap import HstUnit, PlainUnit

ODD_BLOCK = Path(__file__).parent / "fixtures" / "pattern_models" / "dic_odd_block.json"

COLORS = ("#112233", "#445566", "#778899", "#aabbcc", "#ddeeff", "#102030")


def quilt_from(rows, cell=12, wof=320, units=None, confirmed=None):
    """A square-grid quilt from rows of one-letter fabric ids. units maps a
    square to its non-plain unit; every other square gets a plain unit."""
    named = {f for unit in (units or {}).values() for f in unit.fabric_ids()}
    fabrics = sorted({f for row in rows for f in row} | named | {"a", "b"})
    unit_map = None
    if units is not None:
        unit_map = [
            units.get((r, c)) or PlainUnit(row=r, col=c, confidence=1.0)
            for r in range(len(rows))
            for c in range(len(rows[0]))
        ]
    return Quilt(
        metadata=QuiltMetadata(name="test"),
        palette=Palette(
            fabrics=[Fabric(id=f, name=f, color=COLORS[i]) for i, f in enumerate(fabrics)]
        ),
        center=GridRegion(
            rows=len(rows),
            cols=len(rows[0]),
            cell_size=cell,
            cells=[list(row) for row in rows],
            unit_map=unit_map,
        ),
        binding=Binding(fabric_id="a"),
        settings=Settings(wof=wof),
        confirmed_blocks=confirmed,
    )


def plain(text):
    return [Square(fabric_id=f) for f in text]


def random_rows(seed):
    rng = random.Random(seed)
    return ["".join(rng.choice("bc") for _ in range(40)) for _ in range(40)]


def dic_at_40_in():
    data = make_double_irish_chain().model_dump()
    data["settings"]["wof"] = 320
    return Quilt.model_validate(data)


def lines_of(decomposition):
    return [(c.fabric_id, c.role, c.short, c.long, c.quantity) for c in decomposition.cut_lines]


# --- M-03 gate (L-13) -------------------------------------------------------


@pytest.mark.parametrize(
    ("counts", "passes"),
    [
        # #120 comment vector 1: 7 types (<= 8), but 6 of them are used once and
        # L-13 allows at most 1 single-use type.
        ([2, 1, 1, 1, 1, 1, 1], False),
        # #120 comment vector 2: 4 types over 2 + 2 + 2 + 2 = 8 blocks; a quarter of
        # 8 is 2, and 4 > 2.
        ([2, 2, 2, 2], False),
        # The DIC: 2 types, none used once, 2 <= 99 / 4.
        ([50, 49], True),
        # Quarter boundary: 2 types over 8 blocks, 2 x 4 = 8 <= 8.
        ([4, 4], True),
        # One single-use type is allowed: 2 types over 11 blocks, 2 x 4 = 8 <= 11.
        ([10, 1], True),
        # Two single-use types are not: 3 types over 12 blocks, 3 x 4 = 12 <= 12,
        # so only the single-use rule fails.
        ([10, 1, 1], False),
        # Type cap boundary: 8 types over 32 blocks, 8 x 4 = 32 <= 32.
        ([4] * 8, True),
        # 9 types over 36 blocks: 9 x 4 = 36 <= 36 holds, so only the cap of 8 fails.
        ([4] * 9, False),
    ],
)
def test_block_gate_applies_the_l13_numbers(counts, passes):
    assert passes_block_gate(counts) is passes


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_random_two_fabric_grid_has_no_block_structure(seed):
    # Source: PATTERN-SPEC Appendix B, C5, and M-03.
    # The 20 x 20 tiling of a 40 x 40 grid has 4 blocks of 400 random squares;
    # two of them match with probability 2^-400, so it is 4 types used once each.
    # L-13: 4 single-use types > 1, and 4 types > 4 blocks / 4 = 1, so it fails.
    quilt = quilt_from(random_rows(seed))
    tiled = tile_blocks(grid_squares(quilt.center), 20, 20, "gate")
    assert tiled.counts == [1, 1, 1, 1]
    assert passes_block_gate(tiled.counts) is False
    assert block_structure(quilt) is None


def test_confirmed_structure_is_taken_without_the_gate():
    # A9: the confirmed counts are a user fact, so the structure stands even
    # where the gate rejects it: 2 x 2 blocks of 20 x 20 random squares are 4
    # types used once each (C5 above).
    blocks = ConfirmedBlocks(blocks_across=2, blocks_down=2, squares_across=20, squares_down=20)
    structure = block_structure(quilt_from(random_rows(1), confirmed=blocks))
    assert structure.source == "confirmed"
    assert (structure.blocks_across, structure.blocks_down) == (2, 2)
    assert (structure.squares_across, structure.squares_down) == (20, 20)
    assert structure.counts == [1, 1, 1, 1]


def test_confirmed_structure_may_be_rectangular():
    # Blocks 3 squares across by 2 down, 2 across and 2 down. Reading order:
    # (0, 0) aab/abb is type 0; (0, 1) aab/abb is type 0; (1, 0) aab/abb is
    # type 0; (1, 1) ccc/ccc is type 1. Counts [3, 1].
    rows = ["aabaab", "abbabb", "aabccc", "abbccc"]
    blocks = ConfirmedBlocks(blocks_across=2, blocks_down=2, squares_across=3, squares_down=2)
    structure = block_structure(quilt_from(rows, confirmed=blocks))
    assert structure.layout == [[0, 0], [0, 1]]
    assert structure.counts == [3, 1]
    assert structure.types[0] == [plain("aab"), plain("abb")]


def test_confirmed_structure_that_does_not_tile_the_grid_is_refused():
    # 3 blocks of 5 squares need 15 squares across; the grid has 10.
    blocks = ConfirmedBlocks(blocks_across=3, blocks_down=2, squares_across=5, squares_down=5)
    with pytest.raises(ValueError, match="confirmed"):
        block_structure(quilt_from(["ab" * 5] * 10, confirmed=blocks))


def test_dic_passes_the_gate_as_5_x_5_blocks():
    # fixtures.py: 9 x 11 blocks of 5 x 5; Block A where block row + block col
    # is even: 6 even block rows x 5 even cols + 5 odd rows x 4 odd cols = 50,
    # Block B the other 99 - 50 = 49. Gate: 2 types, none single-use, 8 <= 99.
    structure = block_structure(dic_at_40_in())
    assert structure.source == "gate"
    assert (structure.blocks_across, structure.blocks_down) == (9, 11)
    assert (structure.squares_across, structure.squares_down) == (5, 5)
    assert structure.counts == [50, 49]
    assert structure.types == [[plain(r) for r in BLOCK_A], [plain(r) for r in BLOCK_B]]


# --- M-04 merged runs ---------------------------------------------------------


def test_same_fabric_runs_merge_along_a_row():
    # Worked example, Block A row 1 "b b c b b", 1 1/2 in (12 e) squares:
    # blue run of 2: 2 x 12 + 4 = 28 (3 1/2 in); cream 1: 12 + 4 = 16 (2 in);
    # blue run of 2: 28. Each is one square tall: 12 + 4 = 16.
    pieces = merge_line(plain("bbcbb"), cell=12, cut_add=4, usable=320)
    assert [(p.kind, p.fabric_id, p.start, p.squares, p.cut_length) for p in pieces] == [
        ("piece", "b", 0, 2, 28),
        ("piece", "c", 2, 1, 16),
        ("piece", "b", 3, 2, 28),
    ]
    assert {p.cut_width for p in pieces} == {16}


def test_full_width_single_fabric_rows_merge_into_one_rectangle():
    # Worked example, Block B: row 1 "b c c c b" is blue 16, cream 3 x 12 + 4 =
    # 40, blue 16; rows 2 to 4 are all cream, so they are one rectangle 5 x 12 +
    # 4 = 64 long (8 in) and 3 x 12 + 4 = 40 wide (5 in); row 5 repeats row 1.
    bands = decompose_lines([plain(r) for r in BLOCK_B], cell=12, cut_add=4, usable=320)
    assert [(b.line, b.lines) for b in bands] == [(0, 1), (1, 3), (4, 1)]
    assert [(p.fabric_id, p.cut_length, p.cut_width) for p in bands[0].pieces] == [
        ("b", 16, 16),
        ("c", 40, 16),
        ("b", 16, 16),
    ]
    assert [(p.fabric_id, p.squares, p.lines, p.cut_length, p.cut_width) for p in bands[1].pieces] == [
        ("c", 5, 3, 64, 40)
    ]


def test_adjacent_rows_of_different_fabrics_stay_apart():
    # Two full-width rows, blue then cream: each is its own 1-row rectangle.
    bands = decompose_lines([plain("bbbbb"), plain("ccccc")], cell=12, cut_add=4, usable=320)
    assert [(b.line, b.lines, [p.fabric_id for p in b.pieces]) for b in bands] == [
        (0, 1, ["b"]),
        (1, 1, ["c"]),
    ]


def test_no_merge_includes_a_unit_square():
    # Two all-blue rows; row 2 has an HST at column 3. Row 1 stays a 1-row
    # rectangle (row 2 is not all plain), and row 2 splits around the unit:
    # blue 2 squares (28), the unit, blue 2 squares (28).
    hst = HstUnit(row=1, col=2, diagonal="tl_br", upper="b", lower="c", confidence=1.0)
    quilt = quilt_from(["bbbbb", "bbbbb"], units={(1, 2): hst})
    bands = decompose_lines(grid_squares(quilt.center), cell=12, cut_add=4, usable=320)
    assert [(b.line, b.lines) for b in bands] == [(0, 1), (1, 1)]
    assert [(p.kind, p.fabric_id, p.squares) for p in bands[0].pieces] == [("piece", "b", 5)]
    assert [(p.kind, p.fabric_id, p.start, p.squares, p.cut_length) for p in bands[1].pieces] == [
        ("piece", "b", 0, 2, 28),
        ("unit", None, 2, 1, None),
        ("piece", "b", 3, 2, 28),
    ]


# --- M-04 cap at the strip-cutting width (MATH.md Q8) ---------------------------


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        # At U = 320 and 12 e squares, a piece of n squares cuts 12n + 4 <= 320, so
        # n <= (320 - 4) // 12 = 26: 26 squares cut 316, 27 squares would cut 328.
        (26, [(0, 26, 316)]),
        # 27 squares: ceil(27 / 26) = 2 pieces, 14 + 13; 14 x 12 + 4 = 172, 13 x 12 + 4 = 160.
        (27, [(0, 14, 172), (14, 13, 160)]),
        # 30 squares: ceil(30 / 26) = 2 pieces, 15 + 15; 15 x 12 + 4 = 184 each.
        (30, [(0, 15, 184), (15, 15, 184)]),
    ],
)
def test_merged_run_is_capped_at_the_usable_width(run, expected):
    pieces = merge_line(plain("b" * run), cell=12, cut_add=4, usable=320)
    assert [(p.start, p.squares, p.cut_length) for p in pieces] == expected
    assert all(p.cut_length <= 320 for p in pieces)


def test_merged_rectangle_height_is_capped_too():
    # 30 all-blue rows 1 square wide: one group of 30 rows, split like a run
    # into 15 + 15 rows, each band cut 16 long and 15 x 12 + 4 = 184 wide.
    bands = decompose_lines([plain("b")] * 30, cell=12, cut_add=4, usable=320)
    assert [(b.line, b.lines) for b in bands] == [(0, 15), (15, 15)]
    assert [(p.cut_length, p.cut_width) for b in bands for p in b.pieces] == [(16, 184), (16, 184)]


def test_square_wider_than_the_strip_is_refused():
    # 320 + 4 = 324 > 320: no piece of one square fits a strip (MATH.md F2).
    with pytest.raises(ValueError, match="usable width"):
        merge_line(plain("b"), cell=320, cut_add=4, usable=320)


# --- M-05 strip-set signatures ------------------------------------------------


def one_row_blocks(rows, units=None):
    """Each grid row is one block, len(row) squares across and 1 down."""
    blocks = ConfirmedBlocks(
        blocks_across=1, blocks_down=len(rows), squares_across=len(rows[0]), squares_down=1
    )
    quilt = quilt_from(rows, units=units, confirmed=blocks)
    return decompose_blocks(quilt, block_structure(quilt))


def test_seven_strips_make_a_set_and_eight_do_not():
    # 12 e squares at U = 320: per_set = 320 // 16 = 20 (F3); 10 blocks need 10
    # segments, 2 x 10 >= 20 fills half a set (L-03), ceil(10 / 20) = 1 set.
    seven = one_row_blocks(["abababa"] * 10)
    assert [(s.fabric_ids, s.strip_widths, s.segments_needed, s.sets) for s in seven.signatures] == [
        (list("abababa"), [16] * 7, 10, 1)
    ]
    assert [b.role for b in seven.recipes[0]] == ["strip_set"]
    # 8 strips is over the cap of 7, so the row is pieced: 4 a and 4 b squares
    # per block, 16 x 16, times 10 blocks.
    eight = one_row_blocks(["abababab"] * 10)
    assert eight.signatures == []
    assert [b.role for b in eight.recipes[0]] == ["pieced"]
    assert lines_of(eight) == [("a", "piece", 16, 16, 40), ("b", "piece", 16, 16, 40)]


def test_a_row_and_its_reverse_share_one_set():
    # "aab" is a 28, b 16; "baa" is its reverse. 5 blocks of each: alone each
    # needs 5 segments, and 2 x 5 < 20 would fail L-03; shared they need 10,
    # 2 x 10 >= 20, so one set, ceil(10 / 20) = 1.
    shared = one_row_blocks(["aab", "baa"] * 5)
    assert [(s.fabric_ids, s.strip_widths, s.segments_needed, s.sets) for s in shared.signatures] == [
        (["a", "b"], [28, 16], 10, 1)
    ]
    assert [(b.role, b.signature, b.reversed) for r in shared.recipes for b in r] == [
        ("strip_set", 0, False),
        ("strip_set", 0, True),
    ]


@pytest.mark.parametrize(("blocks", "role"), [(10, "strip_set"), (9, "pieced")])
def test_a_signature_must_fill_half_a_set(blocks, role):
    # per_set = 20 (above). L-03: 2 x needed >= 20. 10 blocks: 20 >= 20 holds;
    # 9 blocks: 18 < 20 fails, so the row is cut piece by piece.
    decomposition = one_row_blocks(["aba"] * blocks)
    assert [b.role for b in decomposition.recipes[0]] == [role]
    assert len(decomposition.signatures) == (1 if role == "strip_set" else 0)


def test_a_single_piece_row_is_a_rectangle():
    # "aaa" merges to one piece: 3 x 12 + 4 = 40 by 16, cut as a rectangle, x 10.
    decomposition = one_row_blocks(["aaa"] * 10)
    assert decomposition.signatures == []
    assert [b.role for b in decomposition.recipes[0]] == ["rectangle"]
    assert lines_of(decomposition) == [("a", "rectangle", 16, 40, 10)]


def test_a_row_with_a_unit_is_never_strip_pieced():
    # "aba" x 10 makes a set (half-set test above); an HST on the first square
    # of every row leaves b 16 and a 16 beside the unit, cut one by one.
    units = {
        (r, 0): HstUnit(row=r, col=0, diagonal="tl_br", upper="a", lower="b", confidence=1.0)
        for r in range(10)
    }
    decomposition = one_row_blocks(["aba"] * 10, units=units)
    assert decomposition.structure.counts == [10]
    assert decomposition.signatures == []
    assert [b.role for b in decomposition.recipes[0]] == ["pieced"]
    assert lines_of(decomposition) == [("b", "piece", 16, 16, 10), ("a", "piece", 16, 16, 10)]


# --- PATTERN-SPEC section 3 worked example --------------------------------------


def test_worked_example_on_the_dic_at_40_in():
    quilt = dic_at_40_in()
    decomposition = decompose_blocks(quilt, block_structure(quilt))
    # Segments are 1 1/2 + 1/2 = 2 in (16 e); per_set = floor(40 / 2) = 20.
    # Set 1, Block A rows 1 and 5 "b b c b b": blue 28, cream 16, blue 28;
    #   2 per Block A x 50 = 100 segments, ceil(100 / 20) = 5 sets.
    # Set 2, Block A row 3 "c b b b c": cream 16, blue 40, cream 16;
    #   1 x 50 = 50 segments, ceil(50 / 20) = ceil(2.5) = 3 sets.
    # Set 3, Block B rows 1 and 5 "b c c c b": blue 16, cream 40, blue 16;
    #   2 x 49 = 98 segments, ceil(98 / 20) = ceil(4.9) = 5 sets.
    assert [
        (s.fabric_ids, s.strip_widths, s.segment_cut_width, s.segments_needed, s.per_set, s.sets)
        for s in decomposition.signatures
    ] == [
        (["b", "c", "b"], [28, 16, 28], 16, 100, 20, 5),
        (["c", "b", "c"], [16, 40, 16], 16, 50, 20, 3),
        (["b", "c", "b"], [16, 40, 16], 16, 98, 20, 5),
    ]
    # 5 + 3 + 5 = 13 three-strip sets; 2 long seams each: 26.
    assert sum(s.sets for s in decomposition.signatures) == 13
    assert decomposition.long_seams == 26
    # Block A rows 2 and 4 are all blue and not adjacent: each a 16 x 64
    # (2 x 8 in) rectangle, 2 per block x 50 = 100. Block B rows 2 to 4 are one
    # 40 x 64 (5 x 8 in) cream rectangle, 1 per block x 49 = 49.
    assert lines_of(decomposition) == [
        ("b", "rectangle", 16, 64, 100),
        ("c", "rectangle", 40, 64, 49),
    ]
    assert [[b.role for b in recipe] for recipe in decomposition.recipes] == [
        ["strip_set", "rectangle", "strip_set", "rectangle", "strip_set"],
        ["strip_set", "rectangle", "strip_set"],
    ]
    # Cream set strips: 2 in (16) is 1 per set 1 x 5 + 2 per set 2 x 3 = 11;
    # 5 in (40) is 1 per set 3 x 5 = 5.
    strips = decomposition.set_strips()
    assert (strips[("c", 16)], strips[("c", 40)]) == (11, 5)
    # Cream rectangles, F2: 5 in strips, floor(320 / 64) = 5 per strip,
    # ceil(49 / 5) = 10 strips (50 in); the 8 in strips would take
    # ceil(49 / floor(320 / 40)) = ceil(49 / 8) = 7 x 8 in = 56 in, so 5 in wins.
    cream = strip_yield(49, 40, 64, 320, 4)
    assert (cream.strip_width, cream.pieces_per_strip, cream.strips) == (40, 5, 10)


# --- M-07 c rows layout ---------------------------------------------------------


def seven_bars(vertical):
    # 7 bars, each 2 squares wide and 20 long, a and b alternating (a, b, a,
    # b, a, b, a: 4 bars of a, 3 of b), 3 in (24 e) squares.
    row = "".join(("a" if i % 2 == 0 else "b") * 2 for i in range(7))
    if vertical:
        return [row] * 20
    return ["".join(row[r] for _ in range(20)) for r in range(14)]


def test_seven_bar_quilt_plans_merged_bar_pieces_by_columns():
    # Rows: every row is 7 runs of 2 squares and no row is one fabric, so
    # 20 rows x 7 = 140 pieces. Columns: each bar is 2 columns of one fabric,
    # one rectangle 2 x 24 + 4 = 52 wide and 20 squares long. Cap: (320 - 4) //
    # 24 = 13 squares, so 20 splits into ceil(20 / 13) = 2 pieces of 10, each
    # 10 x 24 + 4 = 244 long (6 1/2 x 30 1/2 in): 7 bars x 2 = 14 pieces.
    layout = rows_layout(quilt_from(seven_bars(vertical=True), cell=24))
    assert layout.axis == "columns"
    assert layout.piece_count == 14
    assert [(c.fabric_id, c.role, c.short, c.long, c.quantity) for c in layout.cut_lines] == [
        ("a", "rectangle", 52, 244, 8),
        ("b", "rectangle", 52, 244, 6),
    ]


def test_seven_bar_quilt_turned_a_quarter_keeps_rows():
    # The same bars lying across: each bar is 2 full-width rows, 52 x 244 twice
    # (as above), 14 pieces; columns would cut 20 x 7 = 140.
    layout = rows_layout(quilt_from(seven_bars(vertical=False), cell=24))
    assert layout.axis == "rows"
    assert layout.piece_count == 14


def test_rows_layout_keeps_rows_on_a_tie():
    # "ab" over "ba": 2 pieces per row, 2 per column, 4 either way: rows win.
    layout = rows_layout(quilt_from(["ab", "ba"]))
    assert (layout.axis, layout.piece_count) == ("rows", 4)


# --- the odd-block model for A3b ------------------------------------------------


def test_odd_block_model_keeps_its_confirmed_5_x_5_structure():
    quilt = load(ODD_BLOCK)
    assert quilt.confirmed_blocks == ConfirmedBlocks(
        blocks_across=9, blocks_down=11, squares_across=5, squares_down=5
    )
    # The center block (block row 5, block col 4; 5 + 4 odd, so Block B) has a
    # blue center square: grid row 5 x 5 + 2 = 27, col 4 x 5 + 2 = 22. Every
    # other square matches the DIC.
    dic = make_double_irish_chain().center.cells
    diffs = [
        (r, c, dic[r][c], quilt.center.cells[r][c])
        for r in range(55)
        for c in range(45)
        if dic[r][c] != quilt.center.cells[r][c]
    ]
    assert diffs == [(27, 22, "c", "b")]
    # Types by first appearance: Block A (0, 0), Block B (0, 1), the odd block
    # (5, 4). Counts: A 50, B 49 - 1 = 48, odd 1.
    structure = block_structure(quilt)
    assert structure.source == "confirmed"
    assert structure.counts == [50, 48, 1]
    assert structure.layout[5][4] == 2
    decomposition = decompose_blocks(quilt, structure)
    # The odd block's rows 1 and 5 are "b c c c b", set 3: 2 x 48 + 2 x 1 = 98
    # segments, 5 sets as before; its row 3 "c c b c c" (cream 28, blue 16,
    # cream 28) is needed once, 2 x 1 < 20, so it is pieced.
    assert [s.segments_needed for s in decomposition.signatures] == [100, 50, 98]
    assert [b.role for b in decomposition.recipes[2]] == [
        "strip_set",
        "rectangle",
        "pieced",
        "rectangle",
        "strip_set",
    ]
    # Cut lines by first appearance: Block A's blue 16 x 64 x 2 x 50 = 100;
    # Block B's cream 40 x 64 x 48; the odd block's rows 2 and 4 are single
    # cream rows, 16 x 64 x 2; its row 3 pieces: cream 16 x 28 x 2, blue 16 x 16 x 1.
    assert lines_of(decomposition) == [
        ("b", "rectangle", 16, 64, 100),
        ("c", "rectangle", 40, 64, 48),
        ("c", "rectangle", 16, 64, 2),
        ("c", "piece", 16, 28, 2),
        ("b", "piece", 16, 16, 1),
    ]
