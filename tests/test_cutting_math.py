"""Cutting math vectors: strip yields, strip sets, borders and top fabrics.

Every expected value is copied from docs/sprint-5/MATH.md sections 4.1 and
4.2 (or from the F2 edge-case arithmetic it gives) with its arithmetic in the
comment beside it; expectations flow one way, hand computation -> assertion.
Lengths are integer eighths (1 in = 8 e, 1/4 yd = 72 e). Every width, join
loss, margin and increment is passed explicitly, so a change to a Settings
default cannot move a vector.
"""

import ast
from pathlib import Path

import pytest

from qrep.construct import cutting
from qrep.construct.cutting import (
    border_bands,
    joined_strip_count,
    pieces_per_strip,
    purchase_increments,
    strip_set_plan,
    strip_yield,
    top_fabric_plan,
    with_margin,
)

# MATH.md section 4 defaults, in eighths
U40 = 320
U42 = 336
JOIN = 4  # j = 1/2 in per straight join
SEAM = 2  # a = 1/4 in
MARGIN = 10  # p = 10 percent
QY = 72  # r = 1/4 yd


# --- 4.1 unit checks -------------------------------------------------------

@pytest.mark.parametrize(
    ("length", "increments"),
    [
        # V-UNIT-01, qy = ceil(e / 72)
        (0, 0),  # 0 e -> 0 qy (no line printed)
        (1, 1),  # ceil(1 / 72) = 1
        (72, 1),  # 72 / 72 = 1 exactly
        (73, 2),  # ceil(73 / 72) = 2
        (1008, 14),  # 1008 e (126 in) / 72 = 14 exactly -> 3 1/2 yd
    ],
)
def test_purchase_increments_v_unit_01(length, increments):
    assert purchase_increments(length, QY) == increments


@pytest.mark.parametrize(
    ("length", "purchase"),
    [
        # V-UNIT-02, purchase = ceil(e x 110 / 100)
        (1008, 1109),  # 110880 / 100 = 1108.8 -> 1109
        (1200, 1320),  # 132000 / 100 = 1320 exactly
        (20, 22),  # 2200 / 100 = 22 exactly
        (288, 317),  # 31680 / 100 = 316.8 -> 317
        # 22000 / 100 = 220 exactly; a floating-point ceil(200 x 1.1) gives 221,
        # so this is the case that catches a decimal margin factor
        (200, 220),
    ],
)
def test_with_margin_v_unit_02(length, purchase):
    assert with_margin(length, MARGIN) == purchase


@pytest.mark.parametrize(
    ("piece_length", "strips"),
    [
        # V-UNIT-04, k(Lp) = 1 if Lp <= 320 else ceil((Lp - 4) / 316)
        (320, 1),  # 40 in fits one strip
        (321, 2),  # ceil(317 / 316) = 2
        (636, 2),  # ceil(632 / 316) = 2 exactly (79 1/2 in = 2 x 40 - 1/2)
        (637, 3),  # ceil(633 / 316) = 3
    ],
)
def test_joined_strip_count_v_unit_04(piece_length, strips):
    assert joined_strip_count(piece_length, U40, JOIN) == strips


@pytest.mark.parametrize(
    ("cut", "usable_width", "per"),
    [
        # V-UNIT-05, floor(U / cut)
        (16, U40, 20),  # 2 in: 320 // 16 = 20
        (16, U42, 21),  # 2 in: 336 // 16 = 21
        (20, U40, 16),  # 2 1/2 in: 320 // 20 = 16
        (20, U42, 16),  # 2 1/2 in: 336 // 20 = 16
        (28, U40, 11),  # 3 1/2 in: 320 // 28 = 11
        (28, U42, 12),  # 3 1/2 in: 336 // 28 = 12
    ],
)
def test_pieces_per_strip_v_unit_05(cut, usable_width, per):
    assert pieces_per_strip(cut, usable_width) == per


def test_pieces_per_strip_refuses_a_cut_wider_than_the_strip():
    # 41 in (328 e) cannot be cut off a 40 in strip
    with pytest.raises(ValueError, match="usable width"):
        pieces_per_strip(328, U40)


# --- 4.2 strip yields (F2) -------------------------------------------------

def test_strip_yield_v_yield_01_squares():
    # V-YIELD-01: 200 squares cut 2 1/2 in (20 e), U = 40
    #   per = 320 // 20 = 16; strips = ceil(200 / 16) = ceil(12.5) = 13
    #   length = 13 x 2.5 = 32.5 in (260 e); last strip = 200 - 12 x 16 = 8
    plan = strip_yield(200, 20, 20, U40, JOIN)
    assert plan.strip_width == 20
    assert plan.subcut == 20
    assert plan.pieces_per_strip == 16
    assert plan.strips == 13
    assert plan.strips_per_piece == 1
    assert plan.length == 260
    assert plan.last_strip_pieces == 8


@pytest.mark.parametrize(("side_a", "side_b"), [(20, 36), (36, 20)])
def test_strip_yield_v_yield_02_tie_at_42_keeps_the_narrower_strip(side_a, side_b):
    # V-YIELD-02, U = 42 (336 e), 160 rectangles cut 2 1/2 x 4 1/2 in (20 x 36 e)
    #   2 1/2 in strips: per = 336 // 36 = 9; strips = ceil(160 / 9) = 18; 18 x 20 = 360 e
    #   4 1/2 in strips: per = 336 // 20 = 16; strips = ceil(160 / 16) = 10; 10 x 36 = 360 e
    #   tie at 45 in -> the narrower 2 1/2 in strip, whichever side is passed first
    #   last strip = 160 - 17 x 9 = 7
    plan = strip_yield(160, side_a, side_b, U42, JOIN)
    assert plan.strip_width == 20
    assert plan.subcut == 36
    assert plan.pieces_per_strip == 9
    assert plan.strips == 18
    assert plan.length == 360
    assert plan.last_strip_pieces == 7


def test_strip_yield_v_yield_02_flips_at_40():
    # V-YIELD-02, U = 40 (320 e)
    #   2 1/2 in strips: per = 320 // 36 = 8; strips = ceil(160 / 8) = 20; 20 x 20 = 400 e
    #   4 1/2 in strips: per = 320 // 20 = 16; strips = 10; 10 x 36 = 360 e
    #   keep 4 1/2 in strips; last strip = 160 - 9 x 16 = 16 (full)
    plan = strip_yield(160, 20, 36, U40, JOIN)
    assert plan.strip_width == 36
    assert plan.subcut == 20
    assert plan.pieces_per_strip == 16
    assert plan.strips == 10
    assert plan.length == 360
    assert plan.last_strip_pieces == 16


def test_strip_yield_v_yield_03_joins_a_piece_longer_than_u():
    # V-YIELD-03: 4 pieces cut 2 1/2 x 60 1/2 in (20 x 484 e), U = 40
    #   joined: k = ceil((484 - 4) / 316) = ceil(480 / 316) = 2; strips = 4 x 2 = 8;
    #           length = 8 x 20 = 160 e (20 in)
    #   orientation 2: per = 320 // 20 = 16; strips = ceil(4 / 16) = 1; length = 484 e
    #   keep the joined cut (160 < 484): (8) 2 1/2 in strips, 2 joined per piece
    plan = strip_yield(4, 20, 484, U40, JOIN)
    assert plan.strip_width == 20
    assert plan.subcut == 484
    assert plan.strips_per_piece == 2
    assert plan.strips == 8
    assert plan.length == 160
    assert plan.pieces_per_strip is None
    assert plan.last_strip_pieces is None


@pytest.mark.parametrize(
    ("quantity", "strip_width", "length"),
    [
        # MATH.md F2 edge cases, 2 1/2 x 60 1/2 in (20 x 484 e) at U = 40:
        # joined = q x 2 strips x 20 e = 40q e; orientation 2 = ceil(q / 16) x 484 e
        (12, 20, 480),  # joined 480 < 484
        (13, 484, 484),  # joined 520 > 484
        (16, 484, 484),  # joined 640 > 484
        (17, 20, 680),  # joined 680 < ceil(17 / 16) x 484 = 968
        (24, 20, 960),  # joined 960 < 968
        (25, 484, 968),  # joined 1000 > 968
        (32, 484, 968),  # joined 1280 > 968
        (33, 20, 1320),  # joined 1320 < ceil(33 / 16) x 484 = 1452
        (36, 20, 1440),  # joined 1440 < 1452
        (37, 484, 1452),  # joined 1480 > 1452
    ],
)
def test_strip_yield_compares_the_joined_cut_for_every_quantity(quantity, strip_width, length):
    plan = strip_yield(quantity, 20, 484, U40, JOIN)
    assert (plan.strip_width, plan.length) == (strip_width, length)


def test_strip_yield_refuses_a_piece_longer_than_u_both_ways():
    # 41 x 42 in (328 x 336 e) exceeds 40 in in both directions
    with pytest.raises(ValueError, match="both sides"):
        strip_yield(1, 328, 336, U40, JOIN)


# --- 4.2 strip sets (F3) ---------------------------------------------------

# The fixture's five strip sets (V-SET-01): b = blue, c = cream, with the
# segments its 50 A and 49 B blocks need. Segments are cut 2 in (16 e).
FIXTURE_SETS = {
    "SS1": ("bbcbb", 100),
    "SS2": ("bbbbb", 100),
    "SS3": ("cbbbc", 50),
    "SS4": ("bcccb", 98),
    "SS5": ("ccccc", 147),
}


@pytest.mark.parametrize(
    ("name", "sets"),
    [
        # V-SET-01, per_set = 320 // 16 = 20
        ("SS1", 5),  # ceil(100 / 20) = 5
        ("SS2", 5),  # ceil(100 / 20) = 5
        ("SS3", 3),  # ceil(50 / 20) = ceil(2.5) = 3
        ("SS4", 5),  # ceil(98 / 20) = ceil(4.9) = 5
        ("SS5", 8),  # ceil(147 / 20) = ceil(7.35) = 8
    ],
)
def test_strip_set_plan_v_set_01(name, sets):
    sequence, needed = FIXTURE_SETS[name]
    plan = strip_set_plan(needed, 16, sequence, U40)
    assert plan.per_set == 20
    assert plan.sets == sets


def test_strip_set_plan_v_set_01_total():
    # V-SET-01: 5 + 5 + 3 + 5 + 8 = 26 sets
    plans = [strip_set_plan(needed, 16, seq, U40) for seq, needed in FIXTURE_SETS.values()]
    assert sum(plan.sets for plan in plans) == 26


@pytest.mark.parametrize(
    ("name", "blue", "cream"),
    [
        # V-SET-02, strips per fabric = sets x its count in the sequence
        ("SS1", 20, 5),  # bbcbb: blue 4 x 5 = 20, cream 1 x 5 = 5
        ("SS2", 25, 0),  # bbbbb: blue 5 x 5 = 25
        ("SS3", 9, 6),  # cbbbc: blue 3 x 3 = 9, cream 2 x 3 = 6
        ("SS4", 10, 15),  # bcccb: blue 2 x 5 = 10, cream 3 x 5 = 15
        ("SS5", 0, 40),  # ccccc: cream 5 x 8 = 40
    ],
)
def test_strip_set_plan_v_set_02_fabric_strips(name, blue, cream):
    sequence, needed = FIXTURE_SETS[name]
    strips = strip_set_plan(needed, 16, sequence, U40).fabric_strips
    assert strips.get("b", 0) == blue
    assert strips.get("c", 0) == cream


def fixture_set_strips(fabric: str) -> int:
    return sum(
        strip_set_plan(needed, 16, seq, U40).fabric_strips.get(fabric, 0)
        for seq, needed in FIXTURE_SETS.values()
    )


def test_strip_set_plan_v_set_02_totals():
    # V-SET-02: blue 20 + 25 + 9 + 10 + 0 = 64 strips; cream 5 + 0 + 6 + 15 + 40 = 66
    assert fixture_set_strips("b") == 64
    assert fixture_set_strips("c") == 66


# --- 4.2 borders (F4) ------------------------------------------------------

def test_border_bands_v_bord_01_fixture_at_40():
    # V-BORD-01: center 67 1/2 x 82 1/2 (540 x 660 e), b = 3 3/4 (30 e), U = 40
    #   cut strip width = 30 + 4 = 34 e (4 1/4 in)
    #   sides Ls = 660 + 4 = 664 e (83 in): k = ceil((664 - 4) / 316) = ceil(660 / 316) = 3 -> 6
    #   top/bottom Lt = 540 + 60 + 4 = 604 e (75 1/2 in): k = ceil(600 / 316) = 2 -> 4
    #   total 10 strips; length = 10 x 34 = 340 e (42 1/2 in)
    (band,) = border_bands(540, 660, [30], U40, JOIN, SEAM)
    assert band.strip_width == 34
    assert (band.sides.cut_length, band.sides.strips_per_piece, band.sides.strips) == (664, 3, 6)
    assert (band.top_bottom.cut_length, band.top_bottom.strips_per_piece,
            band.top_bottom.strips) == (604, 2, 4)
    assert band.strips == 10
    assert band.length == 340


def test_border_bands_v_bord_01_fixture_at_42():
    # V-BORD-01, U = 42 (336 e), U - j = 332
    #   sides k = ceil(660 / 332) = ceil(1.988) = 2 -> 4
    #   top/bottom k = ceil(600 / 332) = ceil(1.807) = 2 -> 4
    #   total 8 strips; length = 8 x 34 = 272 e (34 in)
    (band,) = border_bands(540, 660, [30], U42, JOIN, SEAM)
    assert (band.sides.strips_per_piece, band.sides.strips) == (2, 4)
    assert (band.top_bottom.strips_per_piece, band.top_bottom.strips) == (2, 4)
    assert band.strips == 8
    assert band.length == 272


def test_border_bands_v_bord_02_crib():
    # V-BORD-02: center 32 x 48 (256 x 384 e), b = 2 (16 e), U = 40
    #   cut width 16 + 4 = 20 e
    #   Ls = 384 + 4 = 388 e: k = ceil(384 / 316) = ceil(1.215) = 2 -> 4 strips
    #   Lt = 256 + 32 + 4 = 292 e <= 320: per = 320 // 292 = 1 -> ceil(2 / 1) = 2 strips
    #   total 6 strips; length = 6 x 20 = 120 e (15 in)
    (band,) = border_bands(256, 384, [16], U40, JOIN, SEAM)
    assert band.strip_width == 20
    assert (band.sides.cut_length, band.sides.strips_per_piece, band.sides.strips) == (388, 2, 4)
    assert (band.top_bottom.cut_length, band.top_bottom.strips_per_piece,
            band.top_bottom.strips) == (292, 1, 2)
    assert band.strips == 6
    assert band.length == 120


def test_border_bands_v_bord_03_two_bands():
    # V-BORD-03: center 60 x 72 (480 x 576 e), band 1 b = 2 (16 e), band 2 b = 5 (40 e), U = 40
    band1, band2 = border_bands(480, 576, [16, 40], U40, JOIN, SEAM)
    # band 1: cut 20 e; Ls = 576 + 4 = 580 e: k = ceil(576 / 316) = ceil(1.823) = 2 -> 4;
    #   Lt = 480 + 32 + 4 = 516 e: k = ceil(512 / 316) = ceil(1.620) = 2 -> 4;
    #   8 strips; 8 x 20 = 160 e (20 in)
    assert (band1.inner_width, band1.inner_length) == (480, 576)
    assert band1.strip_width == 20
    assert (band1.sides.cut_length, band1.sides.strips) == (580, 4)
    assert (band1.top_bottom.cut_length, band1.top_bottom.strips) == (516, 4)
    assert (band1.strips, band1.length) == (8, 160)
    # inner size for band 2 = (480 + 2 x 16) x (576 + 2 x 16) = 512 x 608 e (64 x 76 in)
    # band 2: cut 40 + 4 = 44 e; Ls = 608 + 4 = 612 e: k = ceil(608 / 316) = ceil(1.924) = 2 -> 4;
    #   Lt = 512 + 80 + 4 = 596 e: k = ceil(592 / 316) = ceil(1.873) = 2 -> 4;
    #   8 strips; 8 x 44 = 352 e (44 in)
    assert (band2.inner_width, band2.inner_length) == (512, 608)
    assert band2.strip_width == 44
    assert (band2.sides.cut_length, band2.sides.strips) == (612, 4)
    assert (band2.top_bottom.cut_length, band2.top_bottom.strips) == (596, 4)
    assert (band2.strips, band2.length) == (8, 352)


def test_border_bands_v_bord_04_short_pieces_share_a_strip():
    # V-BORD-04: center 4 x 4 (32 x 32 e), b = 1 (8 e), U = 40; cut width 12 e
    #   Ls = 32 + 4 = 36 e: per = 320 // 36 = 8 -> ceil(2 / 8) = 1 strip
    #   Lt = 32 + 16 + 4 = 52 e: per = 320 // 52 = 6 -> ceil(2 / 6) = 1 strip
    #   total 2 strips; length = 2 x 12 = 24 e (3 in)
    (band,) = border_bands(32, 32, [8], U40, JOIN, SEAM)
    assert band.strip_width == 12
    assert (band.sides.cut_length, band.sides.strips_per_piece, band.sides.strips) == (36, 1, 1)
    assert (band.top_bottom.cut_length, band.top_bottom.strips_per_piece,
            band.top_bottom.strips) == (52, 1, 1)
    assert band.strips == 2
    assert band.length == 24


# --- 4.2 top fabrics (F5) --------------------------------------------------

FIXTURE_BORDER = (540, 660, [30])  # V-BORD-01 center and band


def test_top_fabric_v_top_01_fixture_historical_blue():
    # V-TOP-01: 1246 squares cut 2 in (16 e), U = 40
    #   per = 20; strips = ceil(1246 / 20) = ceil(62.3) = 63; last strip = 1246 - 62 x 20 = 6
    #   length_needed = 63 x 16 = 1008 e (126 in)
    squares = strip_yield(1246, 16, 16, U40, JOIN)
    assert (squares.strips, squares.last_strip_pieces, squares.length) == (63, 6, 1008)
    #   purchase = ceil(1008 x 110 / 100) = ceil(1108.8) = 1109 e; qy = ceil(1109 / 72) = 16
    plan = top_fabric_plan([squares.length], MARGIN, QY)
    assert (plan.length_needed, plan.purchase, plan.increments) == (1008, 1109, 16)
    #   without margin: 1008 / 72 = 14 exactly -> 3 1/2 yd with 0 in to spare
    bare = top_fabric_plan([squares.length], 0, QY)
    assert (bare.length_needed, bare.purchase, bare.increments) == (1008, 1008, 14)


def test_top_fabric_v_top_02_fixture_historical_cream():
    # V-TOP-02: 1229 squares cut 2 in, plus the V-BORD-01 band, U = 40
    #   per = 20; strips = ceil(1229 / 20) = ceil(61.45) = 62; last strip = 1229 - 61 x 20 = 9
    #   squares 62 x 16 = 992 e + border 340 e = 1332 e (166 1/2 in) = length_needed
    squares = strip_yield(1229, 16, 16, U40, JOIN)
    assert (squares.strips, squares.last_strip_pieces, squares.length) == (62, 9, 992)
    (band,) = border_bands(*FIXTURE_BORDER, U40, JOIN, SEAM)
    #   purchase = ceil(1332 x 110 / 100) = ceil(1465.2) = 1466 e; qy = ceil(1466 / 72) = 21
    plan = top_fabric_plan([squares.length, band.length], MARGIN, QY)
    assert (plan.length_needed, plan.purchase, plan.increments) == (1332, 1466, 21)
    #   without margin: 1332 / 72 = 18.5 -> 19 qy
    assert top_fabric_plan([squares.length, band.length], 0, QY).increments == 19


def test_top_fabric_v_top_03_fixture_strip_strategy():
    # V-TOP-03, U = 40: strips from V-SET-02 at 2 in (16 e), border from V-BORD-01
    (band,) = border_bands(*FIXTURE_BORDER, U40, JOIN, SEAM)
    # blue: 64 x 16 = 1024 e (128 in); purchase = ceil(1024 x 110 / 100) = ceil(1126.4) = 1127 e;
    #   qy = ceil(1127 / 72) = ceil(15.65) = 16; without margin ceil(1024 / 72) = 15
    blue_lengths = [fixture_set_strips("b") * 16]
    blue = top_fabric_plan(blue_lengths, MARGIN, QY)
    assert (blue.length_needed, blue.purchase, blue.increments) == (1024, 1127, 16)
    assert top_fabric_plan(blue_lengths, 0, QY).increments == 15
    # cream: 66 x 16 + 340 = 1056 + 340 = 1396 e (174 1/2 in);
    #   purchase = ceil(1396 x 110 / 100) = ceil(1535.6) = 1536 e;
    #   qy = ceil(1536 / 72) = ceil(21.33) = 22; without margin ceil(1396 / 72) = 20
    cream_lengths = [fixture_set_strips("c") * 16, band.length]
    cream = top_fabric_plan(cream_lengths, MARGIN, QY)
    assert (cream.length_needed, cream.purchase, cream.increments) == (1396, 1536, 22)
    assert top_fabric_plan(cream_lengths, 0, QY).increments == 20


def test_top_fabric_v_top_04_tiny_quilt():
    # V-TOP-04: 2 x 2 cells of 2 in (cut 2 1/2 in = 20 e), red and white on the
    # diagonals, 1 in white border (V-BORD-04), U = 40
    # red top: 2 squares, per 16 -> 1 strip -> 20 e; purchase ceil(20 x 110 / 100) = 22 e; qy 1
    red_squares = strip_yield(2, 20, 20, U40, JOIN)
    red = top_fabric_plan([red_squares.length], MARGIN, QY)
    assert (red.length_needed, red.purchase, red.increments) == (20, 22, 1)
    # white top: 2 squares -> 1 strip (20 e) + border 24 e = 44 e (5.5 in);
    #   purchase ceil(44 x 110 / 100) = ceil(48.4) = 49 e; qy 1
    white_squares = strip_yield(2, 20, 20, U40, JOIN)
    (band,) = border_bands(32, 32, [8], U40, JOIN, SEAM)
    white = top_fabric_plan([white_squares.length, band.length], MARGIN, QY)
    assert (white.length_needed, white.purchase, white.increments) == (44, 49, 1)


# --- module boundary -------------------------------------------------------

def test_cutting_imports_neither_the_strategies_nor_the_schema():
    # A2b wires these functions in; until then they must not depend on the
    # planners or the model, so they can merge without moving any pin.
    tree = ast.parse(Path(cutting.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "cutting.py uses a relative import"
            imported.add(node.module)
    banned = {"qrep.construct", "qrep.construct.strategies", "qrep.model", "qrep.model.schema"}
    assert not imported & banned
