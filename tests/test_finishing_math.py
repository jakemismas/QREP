"""Finishing math vectors: binding, backing, wide-back and batting.

Every expected value is copied from docs/sprint-5/MATH.md section 4 with its
arithmetic in the comment beside it; expectations flow one way, hand
computation -> assertion. Lengths are integer eighths (1 in = 8 e, 1/4 yd =
72 e). Each test builds its Settings with every field explicit, so a change
to a Settings default cannot move a vector.

V-MOM-01 is reserved for the backing case Jake's mother reported (MATH.md
section 6, Q1). When Jake supplies it, it lands here as a failing
hand-computed test before any fix.
"""

import pytest
from pydantic import ValidationError

from qrep.construct import compute_purchase_lines, plan_strip
from qrep.construct.finishing import (
    BACKING_SEAM_LOSS,
    backing_panel_count,
    backing_plan,
    batting_package_text,
    batting_plan,
    binding_plan,
    wide_back_plan,
)
from qrep.export.pdf import build_sections
from qrep.export.yardage_report import render_yardage_md
from qrep.model import Quilt, Settings
from qrep.model.fixtures import make_double_irish_chain


def explicit_settings(**changes: int) -> Settings:
    """The MATH.md section 4 defaults, each passed explicitly."""
    values = {
        "seam_allowance": 2,
        "wof": 320,
        "binding_strip_width": 20,
        "binding_extra": 80,
        "backing_margin": 64,
        "backing_width": 336,
        "wide_back_width": 864,
        "backing_pieced_allowance": 72,
        "backing_one_piece_allowance": 36,
        "purchase_increment": 72,
    }
    values.update(changes)
    return Settings(**values)


def test_backing_seam_loss_is_one_inch():
    # MATH.md 1.3: s = 1 in = 8 e per seam (a 1/2 in seam allowance on each panel)
    assert BACKING_SEAM_LOSS == 8


# --- 4.1 unit checks -------------------------------------------------------

@pytest.mark.parametrize(
    ("dimension", "fabric_width", "panels"),
    [
        # V-UNIT-03, B = 42 (336 e), B - 8 = 328
        (336, 336, 1),  # n(336) = 1 (42 in)
        (337, 336, 2),  # n(337) = ceil(329 / 328) = 2
        (664, 336, 2),  # n(664) = ceil(656 / 328) = 2 exactly (83 in = 2 x 42 - 1)
        (665, 336, 3),  # n(665) = ceil(657 / 328) = 3
        (992, 336, 3),  # n(992) = ceil(984 / 328) = 3 exactly (124 in = 3 x 42 - 2)
        (993, 336, 4),  # n(993) = ceil(985 / 328) = 4
        # V-UNIT-03, B = 40 (320 e), B - 8 = 312
        (320, 320, 1),  # n(320) = 1
        (321, 320, 2),  # n(321) = 2
        (632, 320, 2),  # n(632) = ceil(624 / 312) = 2 (79 in)
        (633, 320, 3),  # n(633) = 3
        (944, 320, 3),  # n(944) = ceil(936 / 312) = 3 (118 in)
        (945, 320, 4),  # n(945) = 4
        # V-UNIT-06, B = 43 in = 344 e, no overhang (Quilter's Paradise example)
        (416, 344, 2),  # n(52 in = 416 e) = ceil((416 - 8) / (344 - 8)) = ceil(408 / 336) = 2
        (768, 344, 3),  # n(96 in = 768 e) = ceil(760 / 336) = ceil(2.262) = 3
    ],
)
def test_backing_panel_count_v_unit_03_and_06(dimension, fabric_width, panels):
    assert backing_panel_count(dimension, fabric_width) == panels


def test_backing_panel_count_refuses_a_width_no_wider_than_the_seam_loss():
    # B - s must be positive or no number of panels ever grows the backing
    with pytest.raises(ValueError, match="backing fabric width"):
        backing_panel_count(400, 8)


# --- 4.3 binding -------------------------------------------------------------

BINDING_VECTORS = [
    # (id, W e, L e, w e, U e, T e, strips, length_needed e, qy)
    # V-BIND-01 fixture 75 x 90: T = 2 (75 + 90) + 10 = 340 in (2720 e)
    #   strips = ceil(2720 / 300) = 10; length = 10 x 20 = 200 e; qy = ceil(200 / 72) = 3
    pytest.param(600, 720, 20, 320, 2720, 10, 200, 3, id="V-BIND-01"),
    # V-BIND-02 76 x 85: T = 2 (76 + 85) + 10 = 332 in (2656 e)
    #   strips = ceil(332 / 37.5) = ceil(8.853) = 9; 180 e; qy = ceil(2.5) = 3
    pytest.param(608, 680, 20, 320, 2656, 9, 180, 3, id="V-BIND-02"),
    # V-BIND-03 53 1/2 x 67: T = 2 (53.5 + 67) + 10 = 251 in (2008 e)
    #   strips = ceil(251 / 37.5) = ceil(6.693) = 7; 140 e; qy = ceil(1.94) = 2
    pytest.param(428, 536, 20, 320, 2008, 7, 140, 2, id="V-BIND-03"),
    # V-BIND-04 70 x 88: T = 2 (70 + 88) + 10 = 326 in (2608 e)
    #   strips = ceil(326 / 37.5) = ceil(8.693) = 9; 180 e; qy = 3
    pytest.param(560, 704, 20, 320, 2608, 9, 180, 3, id="V-BIND-04"),
    # V-BIND-05 queen 92 1/2 x 115: T = 2 (92.5 + 115) + 10 = 425 in (3400 e)
    #   strips = ceil(425 / 37.5) = ceil(11.333) = 12; 240 e; qy = ceil(3.33) = 4
    pytest.param(740, 920, 20, 320, 3400, 12, 240, 4, id="V-BIND-05"),
    # V-BIND-06 102 1/2 x 120: T = 2 (102.5 + 120) + 10 = 455 in (3640 e)
    #   strips = ceil(455 / 37.5) = ceil(12.133) = 13; 260 e; qy = ceil(3.61) = 4
    pytest.param(820, 960, 20, 320, 3640, 13, 260, 4, id="V-BIND-06"),
    # V-BIND-07 68 x 68: T = 4 x 68 + 10 = 282 in (2256 e)
    #   strips = ceil(282 / 37.5) = ceil(7.52) = 8; 160 e; qy = ceil(2.22) = 3
    pytest.param(544, 544, 20, 320, 2256, 8, 160, 3, id="V-BIND-07"),
    # V-BIND-08 (a) fixture at w = 2 1/4 (18 e): U - w = 37.75 in (302 e)
    #   strips = ceil(340 / 37.75) = ceil(9.007) = 10; length = 10 x 18 = 180 e; qy = 3
    pytest.param(600, 720, 18, 320, 2720, 10, 180, 3, id="V-BIND-08a"),
    # V-BIND-08 (b) 94 x 108: T = 2 (94 + 108) + 10 = 414 in (3312 e)
    #   w = 2 1/2: strips = ceil(414 / 37.5) = ceil(11.04) = 12; 240 e; qy = 4
    pytest.param(752, 864, 20, 320, 3312, 12, 240, 4, id="V-BIND-08b-w20"),
    #   w = 2 1/4: strips = ceil(414 / 37.75) = ceil(10.967) = 11; 11 x 18 = 198 e; qy = 3
    pytest.param(752, 864, 18, 320, 3312, 11, 198, 3, id="V-BIND-08b-w18"),
    # V-BIND-09 fixture at U = 42 (336 e): U - w = 39.5 in (316 e)
    #   strips = ceil(340 / 39.5) = ceil(8.608) = 9; 180 e; qy = 3
    pytest.param(600, 720, 20, 336, 2720, 9, 180, 3, id="V-BIND-09"),
    # V-BIND-10 42 x 52: T = 2 (42 + 52) + 10 = 198 in (1584 e)
    #   strips = ceil(198 / 37.5) = ceil(5.28) = 6; 120 e; qy = ceil(1.67) = 2
    pytest.param(336, 416, 20, 320, 1584, 6, 120, 2, id="V-BIND-10"),
    # V-BIND-11 crib 36 x 52: T = 2 (36 + 52) + 10 = 186 in (1488 e)
    #   strips = ceil(186 / 37.5) = ceil(4.96) = 5; 100 e; qy = ceil(1.39) = 2
    pytest.param(288, 416, 20, 320, 1488, 5, 100, 2, id="V-BIND-11"),
    # V-BIND-12 throw 50 x 65: T = 2 (50 + 65) + 10 = 240 in (1920 e)
    #   strips = ceil(240 / 37.5) = ceil(6.4) = 7; 140 e; qy = 2
    pytest.param(400, 520, 20, 320, 1920, 7, 140, 2, id="V-BIND-12"),
    # V-BIND-13 throw 60 x 72: T = 2 (60 + 72) + 10 = 274 in (2192 e)
    #   strips = ceil(274 / 37.5) = ceil(7.307) = 8; 160 e; qy = 3
    pytest.param(480, 576, 20, 320, 2192, 8, 160, 3, id="V-BIND-13"),
    # V-BIND-14 twin 70 x 90: T = 2 (70 + 90) + 10 = 330 in (2640 e)
    #   strips = ceil(330 / 37.5) = ceil(8.8) = 9; 180 e; qy = 3
    pytest.param(560, 720, 20, 320, 2640, 9, 180, 3, id="V-BIND-14"),
    # V-BIND-15 full 84 x 90: T = 2 (84 + 90) + 10 = 358 in (2864 e)
    #   strips = ceil(358 / 37.5) = ceil(9.547) = 10; 200 e; qy = 3
    pytest.param(672, 720, 20, 320, 2864, 10, 200, 3, id="V-BIND-15"),
    # V-BIND-16 queen 90 x 108: T = 2 (90 + 108) + 10 = 406 in (3248 e)
    #   strips = ceil(406 / 37.5) = ceil(10.827) = 11; 220 e; qy = ceil(3.06) = 4
    pytest.param(720, 864, 20, 320, 3248, 11, 220, 4, id="V-BIND-16"),
    # V-BIND-17 king 110 x 108: T = 2 (110 + 108) + 10 = 446 in (3568 e)
    #   strips = ceil(446 / 37.5) = ceil(11.893) = 12; 240 e; qy = 4
    pytest.param(880, 864, 20, 320, 3568, 12, 240, 4, id="V-BIND-17"),
    # V-BIND-18 58 x 66: T = 2 (58 + 66) + 10 = 258 in (2064 e)
    #   strips = ceil(258 / 37.5) = ceil(6.88) = 7; 140 e; qy = 2
    pytest.param(464, 528, 20, 320, 2064, 7, 140, 2, id="V-BIND-18"),
]


@pytest.mark.parametrize(
    ("width", "height", "strip_width", "wof", "total", "strips", "length", "qy"),
    BINDING_VECTORS,
)
def test_binding_v_bind(width, height, strip_width, wof, total, strips, length, qy):
    plan = binding_plan(width, height, strip_width, explicit_settings(wof=wof))
    assert plan.total_length == total
    assert plan.strips == strips
    assert plan.length_needed == length
    assert plan.increments == qy
    # F7 loop check: n strips joined into a loop supply n x (U - w) >= T
    assert plan.strips * (wof - strip_width) >= total


def test_binding_refuses_a_strip_as_wide_as_the_usable_width():
    with pytest.raises(ValueError, match="binding strip width"):
        binding_plan(600, 720, 320, explicit_settings(wof=320))


# --- 4.4 backing, pieced -----------------------------------------------------

BACKING_VECTORS = [
    # (W e, L e, settings changes, panels, panel cut length e, seams,
    #  length_needed e, purchase e, qy)
    # V-BACK-01 queen 92 1/2 x 115: Wb = 100.5 in (804 e), Lb = 123 in (984 e)
    #   vertical: n(100.5) = ceil(99.5 / 41) = 3; 3 x 123 = 369; + 9 = 378
    #   horizontal: n(123) = ceil(122 / 41) = 3; 3 x 100.5 = 301.5 in (2412 e); + 9 = 310.5 (2484 e)
    #   keep horizontal; qy = ceil(2484 / 72) = ceil(34.5) = 35
    pytest.param(740, 920, {}, 3, 804, "horizontal", 2412, 2484, 35, id="V-BACK-01"),
    # V-BACK-02 throw 60 x 72: Wb = 68 in (544 e), Lb = 80 in (640 e)
    #   vertical: n(68) = 2; 2 x 80 = 160; + 9 = 169
    #   horizontal: n(80) = ceil(79 / 41) = 2; 2 x 68 = 136 in (1088 e); + 9 = 145 in (1160 e)
    #   keep horizontal; qy = ceil(1160 / 72) = ceil(16.11) = 17
    pytest.param(480, 576, {}, 2, 544, "horizontal", 1088, 1160, 17, id="V-BACK-02"),
    # V-BACK-03 crib 36 x 52: Wb = 44 in (352 e), Lb = 60 in (480 e)
    #   vertical: n(44) = 2; 2 x 60 = 120; + 9 = 129
    #   horizontal: n(60) = 2; 2 x 44 = 88 in (704 e); + 9 = 97 in (776 e)
    #   keep horizontal; qy = ceil(776 / 72) = ceil(10.78) = 11
    pytest.param(288, 416, {}, 2, 352, "horizontal", 704, 776, 11, id="V-BACK-03"),
    # V-BACK-04 throw 50 x 65: Wb = 58 in (464 e), Lb = 73 in (584 e)
    #   vertical: n(58) = 2; 2 x 73 = 146; + 9 = 155
    #   horizontal: n(73) = 2; 2 x 58 = 116 in (928 e); + 9 = 125 in (1000 e)
    #   keep horizontal; qy = ceil(1000 / 72) = ceil(13.89) = 14
    pytest.param(400, 520, {}, 2, 464, "horizontal", 928, 1000, 14, id="V-BACK-04"),
    # V-BACK-05 twin 70 x 90: Wb = 78 in (624 e), Lb = 98 in (784 e)
    #   vertical: n(78) = ceil(77 / 41) = 2; 2 x 98 = 196 in (1568 e); + 9 = 205 in (1640 e)
    #   horizontal: n(98) = ceil(97 / 41) = 3; 3 x 78 = 234; + 9 = 243
    #   keep vertical; qy = ceil(1640 / 72) = ceil(22.78) = 23
    pytest.param(560, 720, {}, 2, 784, "vertical", 1568, 1640, 23, id="V-BACK-05"),
    # V-BACK-06 full 84 x 90: Wb = 92 in (736 e), Lb = 98 in (784 e)
    #   vertical: n(92) = ceil(91 / 41) = 3; 3 x 98 = 294; + 9 = 303
    #   horizontal: n(98) = 3; 3 x 92 = 276 in (2208 e); + 9 = 285 in (2280 e)
    #   keep horizontal; qy = ceil(2280 / 72) = ceil(31.67) = 32
    pytest.param(672, 720, {}, 3, 736, "horizontal", 2208, 2280, 32, id="V-BACK-06"),
    # V-BACK-07 queen 90 x 108: Wb = 98 in (784 e), Lb = 116 in (928 e)
    #   vertical: n(98) = 3; 3 x 116 = 348; + 9 = 357
    #   horizontal: n(116) = ceil(115 / 41) = 3; 3 x 98 = 294 in (2352 e); + 9 = 303 in (2424 e)
    #   keep horizontal; qy = ceil(2424 / 72) = ceil(33.67) = 34
    pytest.param(720, 864, {}, 3, 784, "horizontal", 2352, 2424, 34, id="V-BACK-07"),
    # V-BACK-08 king 110 x 108: Wb = 118 in (944 e), Lb = 116 in (928 e)
    #   vertical: n(118) = ceil(117 / 41) = 3; 3 x 116 = 348 in (2784 e); + 9 = 357 in (2856 e)
    #   horizontal: n(116) = 3; 3 x 118 = 354; + 9 = 363
    #   keep vertical; qy = ceil(2856 / 72) = ceil(39.67) = 40
    pytest.param(880, 864, {}, 3, 928, "vertical", 2784, 2856, 40, id="V-BACK-08"),
    # V-BACK-09 fixture 75 x 90 (zero slack): Wb = 83 in (664 e), Lb = 98 in (784 e)
    #   vertical: n(83) = ceil(82 / 41) = 2 exactly; 2 x 98 = 196 in (1568 e); + 9 = 205 (1640 e)
    #   horizontal: n(98) = 3; 3 x 83 = 249; + 9 = 258
    #   keep vertical; qy = ceil(1640 / 72) = 23
    pytest.param(600, 720, {}, 2, 784, "vertical", 1568, 1640, 23, id="V-BACK-09"),
    # V-BACK-10 76 x 85: Wb = 84 in (672 e), Lb = 93 in (744 e)
    #   vertical: n(84) = ceil(83 / 41) = 3; 3 x 93 = 279; + 9 = 288
    #   horizontal: n(93) = ceil(92 / 41) = 3; 3 x 84 = 252 in (2016 e); + 9 = 261 in (2088 e)
    #   keep horizontal; qy = 2088 / 72 = 29 exactly
    pytest.param(608, 680, {}, 3, 672, "horizontal", 2016, 2088, 29, id="V-BACK-10"),
    # V-BACK-11 42 x 52: Wb = 50 in (400 e), Lb = 60 in (480 e)
    #   vertical: n(50) = 2; 2 x 60 = 120; + 9 = 129
    #   horizontal: n(60) = 2; 2 x 50 = 100 in (800 e); + 9 = 109 in (872 e)
    #   keep horizontal; qy = ceil(872 / 72) = ceil(12.11) = 13
    pytest.param(336, 416, {}, 2, 400, "horizontal", 800, 872, 13, id="V-BACK-11"),
    # V-BACK-12 28 x 28: Wb = Lb = 36 in (288 e) <= 42 -> n = 1 both ways
    #   length 36; + 4.5 = 40.5 in (324 e) both ways; tie -> vertical
    #   qy = ceil(324 / 72) = ceil(4.5) = 5
    pytest.param(224, 224, {}, 1, 288, "vertical", 288, 324, 5, id="V-BACK-12"),
    # V-BACK-13 68 x 68: Wb = Lb = 76 in (608 e); n(76) = ceil(75 / 41) = 2 both ways
    #   2 x 76 = 152 in (1216 e); + 9 = 161 in (1288 e) both ways; tie -> vertical
    #   qy = ceil(1288 / 72) = ceil(17.89) = 18
    pytest.param(544, 544, {}, 2, 608, "vertical", 1216, 1288, 18, id="V-BACK-13"),
    # V-BACK-14 24 x 58: Wb = 32 in (256 e), Lb = 66 in (528 e)
    #   vertical: n(32) = 1; length 66 in (528 e); + 4.5 = 70.5 in (564 e)
    #   horizontal: n(66) = ceil(65 / 41) = 2; 2 x 32 = 64 in (512 e); + 9 = 73 in (584 e)
    #   keep vertical (70.5 < 73) although the horizontal raw length is shorter
    #   qy = ceil(564 / 72) = ceil(7.83) = 8
    pytest.param(192, 464, {}, 1, 528, "vertical", 528, 564, 8, id="V-BACK-14"),
    # V-BACK-15 140 x 140: Wb = Lb = 148 in (1184 e); n(148) = ceil(147 / 41) = 4 both ways
    #   4 x 148 = 592 in (4736 e); + 9 = 601 in (4808 e); tie -> vertical
    #   qy = ceil(4808 / 72) = ceil(66.78) = 67
    pytest.param(1120, 1120, {}, 4, 1184, "vertical", 4736, 4808, 67, id="V-BACK-15"),
    # V-BACK-16 102 1/2 x 120: Wb = 110.5 in (884 e), Lb = 128 in (1024 e)
    #   vertical: n(110.5) = ceil(109.5 / 41) = 3; 3 x 128 = 384 in (3072 e); + 9 = 393 (3144 e)
    #   horizontal: n(128) = ceil(127 / 41) = 4; 4 x 110.5 = 442; + 9 = 451
    #   keep vertical; qy = ceil(3144 / 72) = ceil(43.67) = 44
    pytest.param(820, 960, {}, 3, 1024, "vertical", 3072, 3144, 44, id="V-BACK-16"),
    # V-BACK-17 53 1/2 x 67: Wb = 61.5 in (492 e), Lb = 75 in (600 e)
    #   vertical: n(61.5) = 2; 2 x 75 = 150; + 9 = 159
    #   horizontal: n(75) = ceil(74 / 41) = 2; 2 x 61.5 = 123 in (984 e); + 9 = 132 in (1056 e)
    #   keep horizontal; qy = ceil(1056 / 72) = ceil(14.67) = 15
    pytest.param(428, 536, {}, 2, 492, "horizontal", 984, 1056, 15, id="V-BACK-17"),
    # V-BACK-18 queen 92 1/2 x 115 at B = 40 (320 e): n = ceil((D - 1) / 39)
    #   vertical: n(100.5) = ceil(99.5 / 39) = 3; 3 x 123 = 369 in (2952 e); + 9 = 378 in (3024 e)
    #   horizontal: n(123) = ceil(122 / 39) = 4; 4 x 100.5 = 402; + 9 = 411
    #   keep vertical; qy = 3024 / 72 = 42
    pytest.param(
        740, 920, {"backing_width": 320}, 3, 984, "vertical", 2952, 3024, 42, id="V-BACK-18"
    ),
    # V-BACK-19 throw 60 x 72 at B = 40
    #   vertical: n(68) = ceil(67 / 39) = 2; 2 x 80 = 160 in (1280 e); + 9 = 169 in (1352 e)
    #   horizontal: n(80) = ceil(79 / 39) = 3; 3 x 68 = 204; + 9 = 213
    #   keep vertical; qy = ceil(1352 / 72) = ceil(18.78) = 19
    pytest.param(
        480, 576, {"backing_width": 320}, 2, 640, "vertical", 1280, 1352, 19, id="V-BACK-19"
    ),
    # V-BACK-20 fixture 75 x 90 at B = 40
    #   vertical: n(83) = ceil(82 / 39) = 3; 3 x 98 = 294; + 9 = 303
    #   horizontal: n(98) = ceil(97 / 39) = 3; 3 x 83 = 249 in (1992 e); + 9 = 258 in (2064 e)
    #   keep horizontal; qy = ceil(2064 / 72) = ceil(28.67) = 29
    pytest.param(
        600, 720, {"backing_width": 320}, 3, 664, "horizontal", 1992, 2064, 29, id="V-BACK-20"
    ),
    # V-BACK-21 queen 92 1/2 x 115, domestic overhang 2o = 4 in (32 e)
    #   Wb = 96.5 in (772 e), Lb = 119 in (952 e)
    #   vertical: n(96.5) = ceil(95.5 / 41) = 3; 3 x 119 = 357; + 9 = 366
    #   horizontal: n(119) = ceil(118 / 41) = 3; 3 x 96.5 = 289.5 in (2316 e); + 9 = 298.5 (2388 e)
    #   keep horizontal; qy = ceil(2388 / 72) = ceil(33.17) = 34
    pytest.param(
        740, 920, {"backing_margin": 32}, 3, 772, "horizontal", 2316, 2388, 34, id="V-BACK-21"
    ),
    # V-BACK-22 throw 60 x 72, domestic overhang: Wb = 64 in (512 e), Lb = 76 in (608 e)
    #   vertical: n(64) = 2; 2 x 76 = 152; + 9 = 161
    #   horizontal: n(76) = 2; 2 x 64 = 128 in (1024 e); + 9 = 137 in (1096 e)
    #   keep horizontal; qy = ceil(1096 / 72) = ceil(15.22) = 16
    pytest.param(
        480, 576, {"backing_margin": 32}, 2, 512, "horizontal", 1024, 1096, 16, id="V-BACK-22"
    ),
    # V-BACK-23 58 x 66: Wb = 66 in (528 e), Lb = 74 in (592 e)
    #   vertical: n(66) = 2; 2 x 74 = 148; + 9 = 157
    #   horizontal: n(74) = ceil(73 / 41) = 2; 2 x 66 = 132 in (1056 e); + 9 = 141 in (1128 e)
    #   keep horizontal; qy = ceil(1128 / 72) = ceil(15.67) = 16
    pytest.param(464, 528, {}, 2, 528, "horizontal", 1056, 1128, 16, id="V-BACK-23"),
]


@pytest.mark.parametrize(
    ("width", "height", "changes", "panels", "panel_length", "seams", "length", "purchase", "qy"),
    BACKING_VECTORS,
)
def test_backing_v_back(width, height, changes, panels, panel_length, seams, length, purchase, qy):
    plan = backing_plan(width, height, explicit_settings(**changes))
    assert plan.panels == panels
    assert plan.panel_length == panel_length
    assert plan.seams == seams
    assert plan.length_needed == length
    assert plan.purchase == purchase
    assert plan.increments == qy


def test_backing_purchase_increment_reads_the_setting():
    # MATH.md 1.4: a 1/8 yd increment is ceil(purchase / 36 e) eighths of a yard.
    # V-BACK-01 at r = 36 e: ceil(2484 / 36) = 69 (the policy table's column B, 8 5/8 yd)
    plan = backing_plan(740, 920, explicit_settings(purchase_increment=36))
    assert plan.purchase == 2484
    assert plan.increments == 69


# --- 4.5 wide-back -----------------------------------------------------------

WIDE_VECTORS = [
    # (W e, L e, BW e, length_needed e, purchase e, qy)
    # V-WIDE-01 queen 92 1/2 x 115: Wb 100.5 <= 108, Lb 123 > 108 -> length = Lb = 123 in (984 e)
    #   + 4.5 = 127.5 in (1020 e); qy = ceil(1020 / 72) = ceil(14.17) = 15
    pytest.param(740, 920, 864, 984, 1020, 15, id="V-WIDE-01"),
    # V-WIDE-02 throw 60 x 72: both fit -> min(68, 80) = 68 in (544 e)
    #   + 4.5 = 72.5 in (580 e); qy = ceil(580 / 72) = ceil(8.06) = 9
    pytest.param(480, 576, 864, 544, 580, 9, id="V-WIDE-02"),
    # V-WIDE-03 76 x 85: both fit -> min(84, 93) = 84 in (672 e); + 4.5 = 88.5 in (708 e)
    #   qy = ceil(708 / 72) = ceil(9.83) = 10
    pytest.param(608, 680, 864, 672, 708, 10, id="V-WIDE-03"),
    # V-WIDE-04 queen 90 x 108: Wb 98 fits, Lb 116 > 108 -> length 116 in (928 e)
    #   + 4.5 = 120.5 in (964 e); qy = ceil(964 / 72) = ceil(13.39) = 14
    pytest.param(720, 864, 864, 928, 964, 14, id="V-WIDE-04"),
    # V-WIDE-05 king 110 x 108 at BW = 118 (944 e): both fit -> min(118, 116) = 116 in (928 e)
    #   + 4.5 -> 964 e -> 14 qy
    pytest.param(880, 864, 944, 928, 964, 14, id="V-WIDE-05-bw118"),
    # V-WIDE-06 102 1/2 x 120 at BW = 118: Wb 110.5 fits, Lb 128 > 118 -> length 128 in (1024 e)
    #   + 4.5 = 132.5 in (1060 e); qy = ceil(1060 / 72) = ceil(14.72) = 15
    pytest.param(820, 960, 944, 1024, 1060, 15, id="V-WIDE-06-bw118"),
    # V-WIDE-08 fixture 75 x 90: both fit -> min(83, 98) = 83 in (664 e)
    #   + 4.5 = 87.5 in (700 e); qy = ceil(700 / 72) = ceil(9.72) = 10
    pytest.param(600, 720, 864, 664, 700, 10, id="V-WIDE-08"),
    # V-WIDE-09 42 x 52: both fit -> min(50, 60) = 50 in (400 e); + 4.5 = 54.5 in (436 e)
    #   qy = ceil(436 / 72) = ceil(6.06) = 7
    pytest.param(336, 416, 864, 400, 436, 7, id="V-WIDE-09"),
    # V-WIDE-10 standard sizes, both dimensions fit, length = the smaller dimension
    #   crib 36 x 52: min(44, 60) = 44 -> 48.5 in (388 e) -> ceil(5.39) = 6 qy
    pytest.param(288, 416, 864, 352, 388, 6, id="V-WIDE-10-crib"),
    #   throw 50 x 65: min(58, 73) = 58 -> 62.5 in (500 e) -> ceil(6.94) = 7 qy
    pytest.param(400, 520, 864, 464, 500, 7, id="V-WIDE-10-throw"),
    #   twin 70 x 90: min(78, 98) = 78 -> 82.5 in (660 e) -> ceil(9.17) = 10 qy
    pytest.param(560, 720, 864, 624, 660, 10, id="V-WIDE-10-twin"),
    #   full 84 x 90: min(92, 98) = 92 -> 96.5 in (772 e) -> ceil(10.72) = 11 qy
    pytest.param(672, 720, 864, 736, 772, 11, id="V-WIDE-10-full"),
]


@pytest.mark.parametrize(("width", "height", "wide", "length", "purchase", "qy"), WIDE_VECTORS)
def test_wide_back_v_wide(width, height, wide, length, purchase, qy):
    plan = wide_back_plan(width, height, explicit_settings(wide_back_width=wide))
    assert plan is not None
    assert plan.fabric_width == wide
    assert plan.length_needed == length
    assert plan.purchase == purchase
    assert plan.increments == qy


@pytest.mark.parametrize(
    ("width", "height"),
    [
        # V-WIDE-05 king 110 x 108: Wb 118 > 108 and Lb 116 > 108 -> no 108 in line
        pytest.param(880, 864, id="V-WIDE-05"),
        # V-WIDE-06 102 1/2 x 120: Wb 110.5 > 108 and Lb 128 > 108 -> no 108 in line
        pytest.param(820, 960, id="V-WIDE-06"),
        # V-WIDE-07 28 x 28: the pieced layout is one panel (V-BACK-12) -> no wide-back line
        pytest.param(224, 224, id="V-WIDE-07-28x28"),
        # V-WIDE-07 the tiny quilt, 6 x 6: Wb = Lb = 14 in <= 42 -> one panel -> no line
        pytest.param(48, 48, id="V-WIDE-07-tiny"),
    ],
)
def test_wide_back_omitted(width, height):
    assert wide_back_plan(width, height, explicit_settings(wide_back_width=864)) is None


# --- 4.6 batting -------------------------------------------------------------

BATTING_VECTORS = [
    # (W e, L e, batting width e, batting height e, package)
    # V-BATT-01 fixture 75 x 90 -> 83 x 98: crib no; twin no (83 > 72, turned 98 > 72);
    #   full no (98 > 96, turned 98 > 90); queen 83 <= 90 and 98 <= 108 -> queen
    pytest.param(600, 720, 664, 784, "queen", id="V-BATT-01"),
    # V-BATT-02 crib 36 x 52 -> 44 x 60: crib (44 <= 45, 60 <= 60)
    pytest.param(288, 416, 352, 480, "crib", id="V-BATT-02"),
    # V-BATT-03 throw 60 x 72 -> 68 x 80: crib no (68 > 60); twin 68 <= 72, 80 <= 90 -> twin
    pytest.param(480, 576, 544, 640, "twin", id="V-BATT-03"),
    # V-BATT-04 throw 50 x 65 -> 58 x 73: crib no (58 > 45; turned 73 > 45); twin -> twin
    pytest.param(400, 520, 464, 584, "twin", id="V-BATT-04"),
    # V-BATT-05 twin 70 x 90 -> 78 x 98: twin no; full no; queen 78 <= 90, 98 <= 108 -> queen
    pytest.param(560, 720, 624, 784, "queen", id="V-BATT-05"),
    # V-BATT-06 full 84 x 90 -> 92 x 98: full no (92 > 90); queen no (92 > 90) -> king
    pytest.param(672, 720, 736, 784, "king", id="V-BATT-06"),
    # V-BATT-07 queen 90 x 108 -> 98 x 116: queen no (98 > 90); king 98 <= 124, 116 <= 120 -> king
    pytest.param(720, 864, 784, 928, "king", id="V-BATT-07"),
    # V-BATT-08 queen 92 1/2 x 115 -> 100 1/2 x 123: king upright no (123 > 120);
    #   turned 100.5 <= 120 and 123 <= 124 -> king (turned)
    pytest.param(740, 920, 804, 984, "king", id="V-BATT-08"),
    # V-BATT-09 king 110 x 108 -> 118 x 116: king (118 <= 124, 116 <= 120)
    pytest.param(880, 864, 944, 928, "king", id="V-BATT-09"),
    # V-BATT-10 102 1/2 x 120 -> 110 1/2 x 128: king no (128 > 120; turned 128 > 124) -> none
    pytest.param(820, 960, 884, 1024, None, id="V-BATT-10"),
    # V-BATT-11 68 x 68 -> 76 x 76: twin no (76 > 72 both ways); full 76 <= 90, 76 <= 96 -> full
    pytest.param(544, 544, 608, 608, "full", id="V-BATT-11"),
    # V-BATT-12 tiny 6 x 6 -> 14 x 14: crib
    pytest.param(48, 48, 112, 112, "crib", id="V-BATT-12"),
    # V-BATT-13 42 x 52 -> 50 x 60: crib no (50 > 45; turned 60 > 45); twin 50 <= 72, 60 <= 90
    pytest.param(336, 416, 400, 480, "twin", id="V-BATT-13"),
]


@pytest.mark.parametrize(("width", "height", "bat_w", "bat_h", "package"), BATTING_VECTORS)
def test_batting_v_batt(width, height, bat_w, bat_h, package):
    plan = batting_plan(width, height, explicit_settings(backing_margin=64))
    assert (plan.width, plan.height) == (bat_w, bat_h)
    assert plan.package == package


def test_batting_package_text_names_the_package_and_its_size():
    # V-BATT-01: queen package, 90 x 108 in (720 x 864 e)
    assert batting_package_text(batting_plan(600, 720, explicit_settings())) == (
        "queen package (90 x 108 in)"
    )
    # V-BATT-10: no package covers 110 1/2 x 128 -> the F12 wording
    assert batting_package_text(batting_plan(820, 960, explicit_settings())) == (
        "larger than a king package (124 x 120 in)"
    )


def test_batting_reads_the_backing_margin():
    # D-13: batting follows settings.backing_margin. Fixture 75 x 90 at 2o = 4 in (32 e):
    #   600 + 32 = 632 (79 in), 720 + 32 = 752 (94 in); twin no (79 > 72; turned 94 > 72);
    #   full 79 <= 90 and 94 <= 96 -> full
    plan = batting_plan(600, 720, explicit_settings(backing_margin=32))
    assert (plan.width, plan.height) == (632, 752)
    assert plan.package == "full"


# --- one function per line: the plan, the purchase table and the PDF -------

def fixture_with(**changes: int) -> Quilt:
    """The 75 x 90 benchmark fixture (600 x 720 e), at its stored 42 in WOF
    unless a test changes it."""
    quilt = make_double_irish_chain()
    settings = explicit_settings(**{"wof": 336, **changes})
    return quilt.model_copy(update={"settings": settings})


def _paragraph(quilt: Quilt, title: str, starts: str) -> str:
    section = next(s for s in build_sections(quilt, plan_strip(quilt)) if s.title == title)
    return next(p for p in section.paragraphs if p.startswith(starts))


@pytest.mark.parametrize(
    ("wof", "strips"),
    [
        # V-BIND-09: U = 42 (336 e): ceil(2720 / 316) = 9 (today's ceil(2720 / 336) is also 9)
        (336, 9),
        # V-BIND-01: U = 40 (320 e): ceil(2720 / 300) = 10, where today's
        #   ceil(2720 / 320) = ceil(8.5) = 9 strips join to 9 x 37.5 = 337.5 in < T = 340 in
        (320, 10),
    ],
)
def test_strip_plan_binding_count_is_join_aware(wof, strips):
    quilt = fixture_with(wof=wof)
    plan = plan_strip(quilt)
    binding = next(p for p in plan.cut_pieces if p.component == "binding")
    assert binding.quantity == strips
    step = next(s for s in plan.assembly if s.title == "Prepare the binding")
    assert step.detail.startswith(f"Join {strips} WOF strips")
    assert f"join {strips} widths of fabric" in _paragraph(quilt, "Binding", "Bind with")


def test_purchase_backing_line_is_built_from_the_backing_width():
    # V-BACK-09 at B = 42: (2) panels 98 in long, vertical seams; 1568 e raw, 23 qy
    report = compute_purchase_lines(fixture_with(), plan_strip(fixture_with()))
    backing = report.lines[-1]
    assert backing.purpose == "backing"
    assert backing.length_needed == 1568
    assert backing.quarter_yards == 23
    assert backing.name == 'backing, 42" wide fabric: (2) panels 98" long, vertical seams'
    # V-BACK-20 at B = 40: (3) panels 83 in long, horizontal seams; 1992 e raw, 29 qy
    narrow = fixture_with(backing_width=320)
    backing = compute_purchase_lines(narrow, plan_strip(narrow)).lines[-1]
    assert backing.length_needed == 1992
    assert backing.quarter_yards == 29
    assert backing.name == 'backing, 40" wide fabric: (3) panels 83" long, horizontal seams'


def test_purchase_report_carries_the_wide_back_alternative():
    # V-WIDE-08: fixture, both sides fit 108 in -> 83 in (664 e) + 4.5 in = 700 e -> 10 qy
    quilt = fixture_with()
    report = compute_purchase_lines(quilt, plan_strip(quilt))
    assert report.wide_back is not None
    assert report.wide_back.purpose == "wide_back"
    assert report.wide_back.length_needed == 664
    assert report.wide_back.quarter_yards == 10
    assert all(line.purpose != "wide_back" for line in report.lines)
    assert 'wide backing, 108" wide fabric: one piece 83" long' in render_yardage_md(report)
    assert "2 1/2 yd" in render_yardage_md(report)


def test_purchase_report_omits_the_wide_back_line_when_nothing_fits():
    # F11 at BW = 75 in (600 e): Wb 83 in > 75 and Lb 98 in > 75 -> no wide-back line
    quilt = fixture_with(wide_back_width=600)
    report = compute_purchase_lines(quilt, plan_strip(quilt))
    assert report.wide_back is None
    assert "wide backing" not in render_yardage_md(report)


def test_pdf_finishing_text_routes_through_the_shared_functions():
    quilt = fixture_with()
    # V-BACK-09: (2) panels 98 in long from 42 in fabric, vertical seams, 23 qy = 5 3/4 yd
    assert _paragraph(quilt, "Finishing", "Backing:") == (
        'Backing: cut (2) panels 98" long from 42" wide fabric and join them side by side '
        'with 1/2" seams pressed open, so the seams run top to bottom. Buy 5 3/4 yd.'
    )
    # V-WIDE-08: one piece of 108 in fabric, 83 in long, 10 qy = 2 1/2 yd
    assert _paragraph(quilt, "Finishing", "Or use") == (
        'Or use one piece of 108" wide fabric, 83" long, with no seams. Buy 2 1/2 yd.'
    )
    # V-BATT-01: 83 x 98 in, queen package (90 x 108 in)
    assert _paragraph(quilt, "Finishing", "Batting:") == (
        'Batting: at least 83" by 98", the finished top plus 8" on each dimension; '
        "a queen package (90 x 108 in) covers it."
    )


def test_pdf_batting_follows_the_backing_margin():
    # D-13: 2o = 4 in (32 e): 632 x 752 e = 79 x 94 in -> full package (see the vector above)
    assert _paragraph(fixture_with(backing_margin=32), "Finishing", "Batting:") == (
        'Batting: at least 79" by 94", the finished top plus 4" on each dimension; '
        "a full package (90 x 96 in) covers it."
    )


def test_pdf_backing_text_stacks_horizontal_seam_panels():
    # V-BACK-20 at B = 40 (320 e): (3) panels 83 in long, horizontal seams, so the
    # panels are stacked; qy = 29 -> 7 1/4 yd
    assert _paragraph(fixture_with(backing_width=320), "Finishing", "Backing:") == (
        'Backing: cut (3) panels 83" long from 40" wide fabric and join them one above the '
        'other with 1/2" seams pressed open, so the seams run side to side. Buy 7 1/4 yd.'
    )


def test_pdf_batting_names_no_package_past_the_king():
    # F12 with 2o = 35 in (280 e): 600 + 280 = 880 (110 in), 720 + 280 = 1000 (125 in);
    #   king upright no (125 > 120); turned 110 <= 120 but 125 > 124, no -> no package
    assert _paragraph(fixture_with(backing_margin=280), "Finishing", "Batting:") == (
        'Batting: at least 110" by 125", the finished top plus 35" on each dimension; '
        "it is larger than a king package (124 x 120 in)."
    )


def test_settings_refuse_a_backing_width_no_wider_than_a_seam():
    # B - s must stay positive: at B = 1 in (8 e) no panel count covers the backing
    with pytest.raises(ValidationError, match="backing_width"):
        explicit_settings(backing_width=8)
