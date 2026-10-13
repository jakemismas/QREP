"""Scoring tests for the eval harness (plan D4a; vision-11, data-44).

Every expected value is worked by hand in the comments from the plan's text,
the CIE 1976 definitions or the Wilson score formula, never copied from a run.
"""

import math

import pytest

from qrep_eval import scoring, stats

RED, BLUE = "#ff0000", "#0000ff"

# A 3 x 3 truth in two roles, 0 = red and 1 = blue, as a checkerboard.
TRUTH = [
    [0, 1, 0],
    [1, 0, 1],
    [0, 1, 0],
]
ONES = [[1.0] * 3 for _ in range(3)]


def test_one_swapped_square_scores_as_the_plan_states():
    # Source: plan D4a, the scoring-tests criterion: "a 3 x 3 truth and a read with
    # one swapped square gives a fully correct interior of 0, an accuracy of 8/9, and
    # one confident-wrong square when that square's confidence is 0.5 and it lies in
    # no flagged region".
    # Read: the truth with the centre square (1, 1) swapped from role 0 to role 1,
    # in the same two colors, so each read fabric's nearest role is itself.
    read = [row[:] for row in TRUTH]
    read[1][1] = 1
    confidence = [row[:] for row in ONES]
    confidence[1][1] = 0.5
    mapping = scoring.map_many_to_one([RED, BLUE], [RED, BLUE])
    # Nearest role of red is red (distance 0), of blue is blue (distance 0).
    assert mapping == [0, 1]
    score = scoring.score_squares(TRUTH, read, mapping, confidence)
    # Squares: 9. Wrong: only (1, 1). Correct: 9 - 1 = 8. Accuracy: 8/9.
    assert (score.squares, score.correct, score.wrong) == (9, 8, 1)
    assert score.accuracy == pytest.approx(8 / 9)
    # No flag threshold and no flagged region: the one wrong square is confident-wrong.
    assert score.confident_wrong == 1
    # Fully correct interior needs every square right: 1 wrong square gives 0.
    assert scoring.fully_correct_interior(score, k_truth=2, k_read=2, bands_ok=True) is False
    assert score.dims_match is True


def test_a_flag_or_a_flagged_region_keeps_the_wrong_square_from_being_confident():
    read = [row[:] for row in TRUTH]
    read[1][1] = 1
    confidence = [row[:] for row in ONES]
    confidence[1][1] = 0.5
    mapping = [0, 1]
    # A threshold of exactly 0.5: 0.5 is not below 0.5 (the contract's boundary rule,
    # qrep/vision/verdict.py: at-threshold is not below), so the square stays
    # confident-wrong: 1.
    at = scoring.score_squares(TRUTH, read, mapping, confidence, low_confidence_below=0.5)
    assert at.confident_wrong == 1
    # A threshold of 0.9 (the old app's UNCERTAIN_THRESHOLD): 0.5 < 0.9 flags it: 0.
    above = scoring.score_squares(TRUTH, read, mapping, confidence, low_confidence_below=0.9)
    assert above.confident_wrong == 0
    # A flagged region rows 1..2, cols 1..2 (half-open) covers (1, 1): 0.
    region = scoring.score_squares(TRUTH, read, mapping, confidence, flagged_regions=[(1, 1, 2, 2)])
    assert region.confident_wrong == 0
    # A region next to it, rows 0..1, cols 0..3, misses (1, 1): 1.
    beside = scoring.score_squares(TRUTH, read, mapping, confidence, flagged_regions=[(0, 0, 1, 3)])
    assert beside.confident_wrong == 1
    # Accuracy does not depend on flags: still 8/9 in every case.
    assert {at.correct, above.correct, region.correct, beside.correct} == {8}


def test_a_perfect_read_is_a_fully_correct_interior():
    score = scoring.score_squares(TRUTH, [row[:] for row in TRUTH], [0, 1], ONES)
    # 9 of 9 right, k 2 = 2, bands match: fully correct.
    assert (score.correct, score.wrong, score.confident_wrong) == (9, 0, 0)
    assert scoring.fully_correct_interior(score, k_truth=2, k_read=2, bands_ok=True) is True
    # The same read with a band off by more than 1/4 in is not fully correct (G1).
    assert scoring.fully_correct_interior(score, k_truth=2, k_read=2, bands_ok=False) is False


def test_a_phantom_fabric_is_absorbed_many_to_one_but_not_one_to_one():
    # vision-11: a read with a third, phantom fabric. Read fabrics: 0 = #f00000 (red,
    # 15 below full), 1 = #0000f0 (blue), 2 = #c00000 (a darker red). Gold roles:
    # 0 = red #ff0000, 1 = blue #0000ff.
    read_colors = ["#f00000", "#0000f0", "#c00000"]
    # The read uses the phantom fabric 2 on two of the red squares, (0, 0) and (2, 2).
    read = [
        [2, 1, 0],
        [1, 0, 1],
        [0, 1, 2],
    ]
    # Many-to-one, nearest: both reds are nearer red than blue (a blue-red pair differs
    # in hue by far more than two reds differ in lightness), so 0 -> 0, 1 -> 1, 2 -> 0.
    many = scoring.map_many_to_one(read_colors, [RED, BLUE])
    assert many == [0, 1, 0]
    m2o = scoring.score_squares(TRUTH, read, many, ONES)
    # Every square maps to its truth role: 9 of 9, accuracy 1.
    assert (m2o.correct, m2o.accuracy) == (9, 1.0)
    # The k mismatch is reported separately: 3 read fabrics - 2 roles = +1, so the
    # interior is not fully correct even with every square right (G1 needs exact k).
    assert scoring.k_mismatch(k_read=3, k_truth=2) == 1
    assert scoring.fully_correct_interior(m2o, k_truth=2, k_read=3, bands_ok=True) is False
    # One-to-one, minimum cost: two pairs can be made. Pairing red with fabric 0
    # (#f00000) costs less than with fabric 2 (#c00000), because along pure reds the
    # Lab distance to #ff0000 grows as the channel falls, and blue pairs with fabric 1.
    # So fabric 2 is left unmatched and its two squares count wrong: 9 - 2 = 7.
    one = scoring.map_one_to_one(read_colors, [RED, BLUE])
    assert one == [0, 1, None]
    o2o = scoring.score_squares(TRUTH, read, one, ONES)
    assert (o2o.correct, o2o.wrong) == (7, 2)
    assert o2o.accuracy == pytest.approx(7 / 9)


def test_one_to_one_minimizes_the_total_not_each_choice():
    # Greedy darkest-first (compare.map_palettes' rule) can pick a pair that forces a
    # worse total. Read fabrics: 0 = #808080 (gray), 1 = #ffffff (white). Roles:
    # 0 = #ffffff (white), 1 = #000000 (black). Lab L*: black 0, gray 53.585, white 100
    # (worked in test_srgb_to_lab_by_hand); grays have a* = b* = 0, so distances are |dL|.
    # Option A: gray -> white, white -> black: |53.585 - 100| + |100 - 0| = 146.415.
    # Option B: gray -> black, white -> white: |53.585 - 0| + |100 - 100| = 53.585.
    # Minimum total: option B, so the mapping is [1, 0].
    assert scoring.map_one_to_one(["#808080", "#ffffff"], ["#ffffff", "#000000"]) == [1, 0]
    # With more roles than read fabrics, a role is left over and every read fabric maps.
    assert scoring.map_one_to_one(["#ffffff"], ["#000000", "#ffffff"]) == [1]


def test_mismatched_dimensions_score_every_square_wrong_and_confident():
    # A read whose grid differs from the truth's (3 x 2 against 3 x 3) locates no truth
    # square: all 9 count wrong, and with no flag every one is confident-wrong.
    read = [[0, 1], [1, 0], [0, 1]]
    score = scoring.score_squares(TRUTH, read, [0, 1], [[1.0, 1.0]] * 3)
    assert (score.squares, score.correct, score.wrong, score.confident_wrong) == (9, 0, 9, 9)
    assert score.dims_match is False


def test_srgb_to_lab_by_hand():
    # CIE 1976 L*a*b* from sRGB (IEC 61966-2-1) with the D65 white of the sRGB matrix.
    # Black: linear 0 -> Y/Yn = 0 -> f = 4/29 (the linear branch) -> L* = 116 * 4/29 - 16
    # = 16 - 16 = 0; a* = b* = 0 because X, Y and Z give the same f.
    assert scoring.srgb_to_lab("#000000") == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    # White: linear 1 on every channel -> X/Xn = Y/Yn = Z/Zn = 1 -> f = 1 ->
    # L* = 116 - 16 = 100, a* = b* = 0.
    assert scoring.srgb_to_lab("#ffffff") == pytest.approx((100.0, 0.0, 0.0), abs=1e-9)
    # Gray #808080: 128/255 = 0.50196078; (0.50196078 + 0.055) / 1.055 = 0.52792491;
    # ln 0.52792491 = -0.63880132; x 2.4 = -1.53312317; exp = 0.21586040 = Y/Yn.
    # Y/Yn > (6/29)^3 = 0.008856, so f = cube root: exp(-1.53312317 / 3) = 0.59987076.
    # L* = 116 * 0.59987076 - 16 = 53.585008. X/Xn = Z/Zn = Y/Yn for a gray, so a* = b* = 0.
    lab = scoring.srgb_to_lab("#808080")
    assert lab[0] == pytest.approx(53.585008, abs=1e-4)
    assert lab[1:] == pytest.approx((0.0, 0.0), abs=1e-9)


def test_bands_match_within_a_quarter_inch():
    # G1: bands match to 1/4 in, inclusive. Truth 1.0 and 2.5 in.
    # Read 1.25 and 2.25: differences 0.25 and 0.25, each <= 0.25: match.
    assert scoring.bands_match([1.0, 2.5], [1.25, 2.25]) is True
    # Read 1.3 and 2.5: 0.3 > 0.25: no match.
    assert scoring.bands_match([1.0, 2.5], [1.3, 2.5]) is False
    # A missing band is no match; no bands on either side is a match.
    assert scoring.bands_match([1.0, 2.5], [1.0]) is False
    assert scoring.bands_match([], []) is True


def test_band_inches_use_the_reads_own_square_size():
    # A truth band 1.5 squares wide on a read whose square is 16 eighths (2 in):
    # 1.5 * 16 / 8 = 3.0 in. A read band of 20 eighths is 20 / 8 = 2.5 in.
    assert scoring.truth_band_inches([1.5], cell_size_eighths=16) == [3.0]
    assert scoring.read_band_inches([20]) == [2.5]


def test_wilson_interval_by_hand():
    # Wilson score interval, z = 1.959964 (two-sided 95 percent), z^2 = 3.841459.
    # 14 of 15 (plan 7.2's G1 example, "0.70 to 0.99"): p = 0.933333;
    # denom = 1 + z^2/n = 1 + 0.256097 = 1.256097;
    # centre = (p + z^2/(2n)) / denom = (0.933333 + 0.128049) / 1.256097 = 0.844985;
    # half = z * sqrt(p(1-p)/n + z^2/(4n^2)) / denom
    #      = 1.959964 * sqrt(0.0041481 + 0.0042683) / 1.256097 = 0.143149;
    # interval 0.701836 to 0.988134.
    lo, hi = stats.wilson(14, 15)
    assert (lo, hi) == (pytest.approx(0.701836, abs=1e-5), pytest.approx(0.988134, abs=1e-5))
    # 0 of 15: lower 0; upper = z^2 / (n + z^2) = 3.841459 / 18.841459 = 0.203883.
    lo, hi = stats.wilson(0, 15)
    assert lo == pytest.approx(0.0, abs=1e-12)
    assert hi == pytest.approx(0.203883, abs=1e-5)
    # 15 of 15: upper 1; lower = n / (n + z^2) = 15 / 18.841459 = 0.796117.
    lo, hi = stats.wilson(15, 15)
    assert lo == pytest.approx(0.796117, abs=1e-5)
    assert hi == pytest.approx(1.0, abs=1e-12)
    # No photos: no interval.
    assert stats.wilson(0, 0) is None


def test_rate_reports_n_and_the_rule_of_three_for_zero():
    # Plan 7.2, G5: with 0 false warnings in n photos the bound is 3/n.
    # 0 of 30 -> 3/30 = 0.1; 0 of 15 -> 3/15 = 0.2.
    assert stats.rule_of_three(30) == pytest.approx(0.1)
    zero = stats.rate(0, 15)
    assert (zero["k"], zero["n"], zero["rate"]) == (0, 15, 0.0)
    assert zero["rule_of_three"] == pytest.approx(0.2)
    # A non-zero count carries no rule-of-three bound: 2 of 10 = 0.2.
    two = stats.rate(2, 10)
    assert two["rate"] == pytest.approx(0.2) and two["rule_of_three"] is None
    # n = 0 reads not measured, never 0 percent.
    empty = stats.rate(0, 0)
    assert empty["rate"] is None and empty["wilson95"] is None
    assert math.isclose(stats.rate(14, 15)["wilson95"][0], 0.701836, abs_tol=1e-5)
