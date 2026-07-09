"""Metric helpers for the sprint 3 photo-reality evidence base (S0, issue #66).

Every expected value below is hand-computed in the comment beside it; values
flow one way, hand computation to assertion, per the repo non-negotiables.
"""

import numpy as np
import pytest

from qrep.vision.metrics import (
    cell_accuracy,
    grid_dims_match,
    palette_fidelity_hex,
    palette_fidelity_lab,
    quad_iou,
)

# ---------------------------------------------------------------------------
# quad IoU
# ---------------------------------------------------------------------------


def test_quad_iou_identical_squares_is_one():
    # identical 10x10 squares: intersection 100, union 100, IoU 100/100 = 1.0
    square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    assert quad_iou(square, square) == pytest.approx(1.0)


def test_quad_iou_half_overlap_is_one_third():
    # A = (0,0)-(10,10), B = (5,0)-(15,10): both area 100,
    # intersection = 5 wide x 10 tall = 50, union = 100 + 100 - 50 = 150,
    # IoU = 50 / 150 = 1/3
    a = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    b = [(5.0, 0.0), (15.0, 0.0), (15.0, 10.0), (5.0, 10.0)]
    assert quad_iou(a, b) == pytest.approx(1.0 / 3.0, abs=1e-6)


def test_quad_iou_contained_square():
    # A = (0,0)-(10,10) area 100, B = (2,2)-(8,8) area 36 fully inside A:
    # intersection = 36, union = 100, IoU = 36 / 100 = 0.36
    a = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    b = [(2.0, 2.0), (8.0, 2.0), (8.0, 8.0), (2.0, 8.0)]
    assert quad_iou(a, b) == pytest.approx(0.36, abs=1e-6)


def test_quad_iou_disjoint_is_zero():
    # squares 10 apart share no area: intersection 0, IoU 0
    a = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    b = [(20.0, 0.0), (30.0, 0.0), (30.0, 10.0), (20.0, 10.0)]
    assert quad_iou(a, b) == 0.0


def test_quad_iou_tilted_quad():
    # A = axis square (0,0)-(2,2) area 4; B = the diamond with vertices at the
    # edge midpoints (1,0),(2,1),(1,2),(0,1). Diamond area = d1*d2/2 =
    # 2*2/2 = 2 and it lies entirely inside A, so intersection = 2,
    # union = 4, IoU = 2/4 = 0.5
    a = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    b = [(1.0, 0.0), (2.0, 1.0), (1.0, 2.0), (0.0, 1.0)]
    assert quad_iou(a, b) == pytest.approx(0.5, abs=1e-6)


def test_quad_iou_is_symmetric():
    # IoU is symmetric by definition; both orders give the same value
    a = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    b = [(5.0, 0.0), (15.0, 0.0), (15.0, 10.0), (5.0, 10.0)]
    assert quad_iou(a, b) == pytest.approx(quad_iou(b, a), abs=1e-9)


# ---------------------------------------------------------------------------
# grid dims
# ---------------------------------------------------------------------------


def test_grid_dims_match_exact_only():
    # (rows, cols) exact equality; a transposed answer is NOT a match
    assert grid_dims_match((55, 45), (55, 45)) is True
    assert grid_dims_match((55, 45), (45, 55)) is False
    assert grid_dims_match((55, 45), (55, 44)) is False


# ---------------------------------------------------------------------------
# cell accuracy on label grids
# ---------------------------------------------------------------------------


def test_cell_accuracy_perfect():
    # 2x2, all four agree: 4 correct / 4 compared = 1.0
    truth = [[0, 1], [1, 0]]
    accuracy, compared = cell_accuracy(truth, truth)
    assert accuracy == 1.0
    assert compared == 4


def test_cell_accuracy_one_wrong_of_four():
    # one wrong cell of four: 3 / 4 = 0.75
    truth = [[0, 1], [1, 0]]
    recovered = [[0, 1], [1, 1]]
    accuracy, compared = cell_accuracy(truth, recovered)
    assert accuracy == pytest.approx(0.75)
    assert compared == 4


def test_cell_accuracy_dim_mismatch_compares_overlap():
    # truth 2x3 vs recovered 2x2: overlap is the top-left 2x2 region.
    # truth overlap [[0,1],[1,0]] vs recovered [[0,1],[1,1]]: 3 / 4 = 0.75
    truth = [[0, 1, 0], [1, 0, 1]]
    recovered = [[0, 1], [1, 1]]
    accuracy, compared = cell_accuracy(truth, recovered)
    assert accuracy == pytest.approx(0.75)
    assert compared == 4


def test_cell_accuracy_with_label_mapping():
    # recovered labels are permuted (0<->1); with mapping {0: 1, 1: 0} all
    # four cells agree: 4 / 4 = 1.0
    truth = [[0, 1], [1, 0]]
    recovered = [[1, 0], [0, 1]]
    accuracy, compared = cell_accuracy(truth, recovered, mapping={0: 1, 1: 0})
    assert accuracy == 1.0
    assert compared == 4


def test_cell_accuracy_empty_recovered_is_zero():
    # nothing recovered: 0 compared cells, accuracy 0.0 by contract
    accuracy, compared = cell_accuracy([[0, 1]], [])
    assert accuracy == 0.0
    assert compared == 0


# ---------------------------------------------------------------------------
# palette fidelity (max Lab distance over greedily matched entries)
# ---------------------------------------------------------------------------


def test_palette_fidelity_identical_palettes_is_zero():
    # identical Lab points match at distance 0; max distance = 0.0
    truth = [(50.0, 0.0, 0.0), (80.0, 10.0, 10.0)]
    assert palette_fidelity_lab(truth, truth) == pytest.approx(0.0)


def test_palette_fidelity_hand_computed_distances():
    # truth (50,0,0) matches recovered (52,0,0): distance sqrt(2^2) = 2
    # truth (80,10,10) matches recovered (80,10,13): distance sqrt(3^2) = 3
    # max distance = 3.0
    truth = [(50.0, 0.0, 0.0), (80.0, 10.0, 10.0)]
    recovered = [(52.0, 0.0, 0.0), (80.0, 10.0, 13.0)]
    assert palette_fidelity_lab(truth, recovered) == pytest.approx(3.0, abs=1e-9)


def test_palette_fidelity_order_independent():
    # same pairs presented in swapped order match identically: max still 3.0
    truth = [(80.0, 10.0, 10.0), (50.0, 0.0, 0.0)]
    recovered = [(52.0, 0.0, 0.0), (80.0, 10.0, 13.0)]
    assert palette_fidelity_lab(truth, recovered) == pytest.approx(3.0, abs=1e-9)


def test_palette_fidelity_greedy_bijective_matching():
    # recovered has one entry, truth has two: the single recovered entry
    # (49,0,0) greedily matches truth (50,0,0) at distance 1; the unmatched
    # truth entry contributes the distance to ITS nearest recovered entry,
    # sqrt((80-49)^2 + 10^2 + 10^2) = sqrt(961+100+100) = sqrt(1161)
    # ~= 34.073; max = sqrt(1161). Unmatched truth entries must count:
    # a one-fabric recovery of a two-fabric quilt is NOT high fidelity.
    truth = [(50.0, 0.0, 0.0), (80.0, 10.0, 10.0)]
    recovered = [(49.0, 0.0, 0.0)]
    expected = float(np.sqrt(1161.0))
    assert palette_fidelity_lab(truth, recovered) == pytest.approx(expected, abs=1e-9)


def test_palette_fidelity_extra_recovered_entry_counts():
    # truth has one entry, recovered has two: (50,0,0) matches at distance 0;
    # the extra phantom entry (60,0,0) contributes its distance to the
    # nearest truth entry, sqrt(10^2) = 10; max = 10.0. Phantom fabrics
    # (the #33 lighting-split failure) must hurt fidelity.
    truth = [(50.0, 0.0, 0.0)]
    recovered = [(50.0, 0.0, 0.0), (60.0, 0.0, 0.0)]
    assert palette_fidelity_lab(truth, recovered) == pytest.approx(10.0, abs=1e-9)


def test_palette_fidelity_hex_identical_is_zero():
    # identical hex palettes convert to identical Lab points: max distance 0.0
    colors = ["#aad4ff", "#f5efe0"]
    assert palette_fidelity_hex(colors, list(reversed(colors))) == pytest.approx(0.0)
