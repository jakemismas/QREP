"""Scoring tests for the eval harness (plan D4a; vision-11, data-44).

Every expected value is worked by hand in the comments from the plan's text,
the CIE 1976 definitions or the Wilson score formula, never copied from a run.
"""

import math

import pytest

from qrep.contract import Counts
from qrep_eval import corpus, harness, readers, report, scoring, stats

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
    # A region ending at column 1, rows 0..3, cols 0..1 (half-open), stops before (1, 1):
    # column 1 is not below 1, so the square stays confident-wrong: 1.
    left = scoring.score_squares(TRUTH, read, mapping, confidence, flagged_regions=[(0, 0, 3, 1)])
    assert left.confident_wrong == 1
    # Accuracy does not depend on flags: still 8/9 in every case.
    assert {at.correct, above.correct, region.correct, beside.correct, left.correct} == {8}


def test_many_to_one_breaks_a_tie_toward_the_lower_role():
    # Two gold roles of one color, #ff0000 and #ff0000: a read #ff0000 lies 0 from each,
    # a tie, and the lower index wins: role 0.
    assert scoring.map_many_to_one([RED], [RED, RED]) == [0]


def test_a_fabric_index_outside_the_mapping_counts_wrong():
    # Mapping [0, 1] covers read fabrics 0 and 1. The read puts fabric -1 on (0, 1) and
    # fabric 2 on (1, 0), both truth role 1: neither indexes the mapping, so both map to
    # no role and count wrong (Python's mapping[-1] would have been role 1, and
    # mapping[2] an IndexError). Correct 9 - 2 = 7; wrong and confident-wrong 2.
    read = [row[:] for row in TRUTH]
    read[0][1], read[1][0] = -1, 2
    score = scoring.score_squares(TRUTH, read, [0, 1], ONES)
    assert (score.correct, score.wrong, score.confident_wrong) == (7, 2, 2)


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
    # CIE 1976 distances, by hand. A shade of one primary (one channel c, the others 0)
    # stays in the cube-root branch here, so its (L* + 16, a*, b*) is the full primary's
    # vector times s = cbrt(linear(c)), and two shades of one primary lie |s1 - s2| times
    # that vector's norm apart. From test_srgb_to_lab_by_hand: red (L* + 16, a*, b*) =
    # (69.2408, 80.0925, 67.2032), norm sqrt(4794.288 + 6414.809 + 4516.270)
    # = sqrt(15725.367) = 125.4008; blue (#0000ff) Lab = (32.2970, 79.1875, -107.8602)
    # by the same steps, so (L* + 16, a*, b*) = (48.2970, 79.1875, -107.8602), norm
    # sqrt(2332.600 + 6270.660 + 11633.823) = sqrt(20237.083) = 142.2571.
    # linear(240) = ((240/255 + 0.055) / 1.055)^2.4 = 0.9442431^2.4 = 0.8713671, s = 0.9551401.
    # linear(192) = ((192/255 + 0.055) / 1.055)^2.4 = 0.7658211^2.4 = 0.5271151, s = 0.8077962
    # (its Z/Zn = 0.0177566 x 0.5271151 = 0.0093598, still above (6/29)^3 = 0.0088565).
    # #f00000 to red: (1 - 0.9551401) x 125.4008 = 0.0448599 x 125.4008 = 5.6255.
    # #0000f0 to blue: 0.0448599 x 142.2571 = 6.3816.
    # #c00000 to red: (1 - 0.8077962) x 125.4008 = 0.1922038 x 125.4008 = 24.1025.
    # Across primaries: #f00000 = (69.2408 x 0.9551401 - 16, 80.0925 x 0.9551401,
    # 67.2032 x 0.9551401) = (50.1347, 76.4995, 64.1885); to blue: d = (17.8377, -2.6880,
    # 172.0487), sqrt(318.18 + 7.23 + 29600.75) = 172.9918.
    # #0000f0 = (48.2970 x 0.9551401 - 16, 79.1875 x 0.9551401, -107.8602 x 0.9551401)
    # = (30.1304, 75.6352, -103.0216); to red: d = (-23.1104, -4.4573, -170.2248),
    # sqrt(534.09 + 19.87 + 28976.48) = 171.8443.
    # #c00000 = (69.2408 x 0.8077962 - 16, 80.0925 x 0.8077962, 67.2032 x 0.8077962)
    # = (39.9325, 64.6984, 54.2865); to blue: d = (7.6355, -14.4891, 162.1467),
    # sqrt(58.30 + 209.93 + 26291.55) = 162.9717.
    # Many-to-one, nearest: 5.6255 < 172.9918, 6.3816 < 171.8443 and 24.1025 < 162.9717,
    # so 0 -> 0, 1 -> 1, 2 -> 0.
    many = scoring.map_many_to_one(read_colors, [RED, BLUE])
    assert many == [0, 1, 0]
    m2o = scoring.score_squares(TRUTH, read, many, ONES)
    # Every square maps to its truth role: 9 of 9, accuracy 1.
    assert (m2o.correct, m2o.accuracy) == (9, 1.0)
    # The k mismatch is reported separately: 3 read fabrics - 2 roles = +1, so the
    # interior is not fully correct even with every square right (G1 needs exact k).
    assert scoring.k_mismatch(k_read=3, k_truth=2) == 1
    assert scoring.fully_correct_interior(m2o, k_truth=2, k_read=3, bands_ok=True) is False
    # One-to-one, minimum cost: two pairs can be made. Red with fabric 0 and blue with
    # fabric 1 total 5.6255 + 6.3816 = 12.0071; red with fabric 2 instead totals
    # 24.1025 + 6.3816 = 30.4841; any pairing that matches a red shade with blue (or the
    # blue shade with red) costs over 160 on that pair alone.
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


def test_a_mismatched_read_that_flags_every_square_is_not_confident():
    # The same 3 x 2 read against the 3 x 3 truth: 9 truth squares wrong either way.
    read = [[0, 1], [1, 0], [0, 1]]
    # Every one of the read's 6 squares at confidence 0.5, below 0.9: all flagged, so
    # nothing it shows is confident: 0 confident-wrong.
    low = scoring.score_squares(TRUTH, read, [0, 1], [[0.5, 0.5]] * 3, low_confidence_below=0.9)
    assert (low.wrong, low.confident_wrong) == (9, 0)
    # One read square at 0.95, not below 0.9: not every square is flagged, so all 9
    # truth squares count confident-wrong.
    one = [[0.5, 0.5], [0.5, 0.95], [0.5, 0.5]]
    assert scoring.score_squares(TRUTH, read, [0, 1], one, low_confidence_below=0.9).confident_wrong == 9
    # A flagged region rows 0..3, cols 0..2 (half-open) covers all 6 read squares: 0. One
    # ending at column 1 leaves column 1 unflagged: 9.
    ones = [[1.0, 1.0]] * 3
    assert scoring.score_squares(TRUTH, read, [0, 1], ones, flagged_regions=[(0, 0, 3, 2)]).confident_wrong == 0
    assert scoring.score_squares(TRUTH, read, [0, 1], ones, flagged_regions=[(0, 0, 3, 1)]).confident_wrong == 9


def test_srgb_to_lab_by_hand():
    # CIE 1976 L*a*b* from sRGB (IEC 61966-2-1) with the D65 white of the sRGB matrix.
    # Black: linear 0 -> Y/Yn = 0 -> f = 4/29 (the linear branch) -> L* = 116 * 4/29 - 16
    # = 16 - 16 = 0; a* = b* = 0 because X, Y and Z give the same f.
    assert scoring.srgb_to_lab("#000000") == pytest.approx((0.0, 0.0, 0.0), abs=1e-9)
    # White: linear 1 on every channel -> X/Xn = Y/Yn = Z/Zn = 1 -> f = 1 ->
    # L* = 116 - 16 = 100, a* = b* = 0.
    assert scoring.srgb_to_lab("#ffffff") == pytest.approx((100.0, 0.0, 0.0), abs=1e-9)
    # Gray #808080: 128/255 = 0.50196078; (0.50196078 + 0.055) / 1.055 = 0.52792491;
    # ln 0.52792491 = ln 0.5 + ln 1.05584982 = -0.69314718 + 0.05434597 = -0.63880121;
    # x 2.4 = -1.53312291; exp = 0.21586050 = Y/Yn.
    # Y/Yn > (6/29)^3 = 0.008856, so f = cube root: exp(-1.53312291 / 3) = exp(-0.51104097)
    # = 0.59987081. L* = 116 * 0.59987081 - 16 = 69.585014 - 16 = 53.585014.
    # X/Xn = Z/Zn = Y/Yn for a gray, so a* = b* = 0.
    lab = scoring.srgb_to_lab("#808080")
    assert lab[0] == pytest.approx(53.585014, abs=1e-4)
    assert lab[1:] == pytest.approx((0.0, 0.0), abs=1e-9)
    # Red #ff0000: linear R = ((255/255 + 0.055) / 1.055)^2.4 = 1^2.4 = 1; G = B = 0 / 12.92
    # = 0. So X, Y, Z are the matrix's first column: 0.4124564, 0.2126729, 0.0193339.
    # White = row sums: Xn = 0.4124564 + 0.3575761 + 0.1804375 = 0.9504700;
    # Yn = 0.2126729 + 0.7151522 + 0.0721750 = 1.0000001;
    # Zn = 0.0193339 + 0.1191920 + 0.9503041 = 1.0888300.
    # X/Xn = 0.4124564 / 0.95047 = 0.4339499; Y/Yn = 0.2126729 / 1.0000001 = 0.2126729;
    # Z/Zn = 0.0193339 / 1.08883 = 0.0177566. Each is above (6/29)^3 = 0.0088565, so
    # f = cube root: fx = 0.7570883, fy = 0.5969034, fz = 0.2608874.
    # L* = 116 x 0.5969034 - 16 = 69.240794 - 16 = 53.240794;
    # a* = 500 x (0.7570883 - 0.5969034) = 500 x 0.1601849 = 80.09245;
    # b* = 200 x (0.5969034 - 0.2608874) = 200 x 0.3360160 = 67.20320.
    assert scoring.srgb_to_lab("#ff0000") == pytest.approx((53.2408, 80.0925, 67.2032), abs=1e-3)


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
    # centre = (p + z^2/(2n)) / denom = (0.933333 + 0.128049) / 1.256097 = 1.061382 / 1.256097
    # = 0.844984;
    # half = z * sqrt(p(1-p)/n + z^2/(4n^2)) / denom
    #      = 1.959964 * sqrt(0.0041481 + 0.0042683) / 1.256097 = 0.143149;
    # interval 0.844984 - 0.143149 = 0.701835 to 0.844984 + 0.143149 = 0.988133.
    lo, hi = stats.wilson(14, 15)
    assert (lo, hi) == (pytest.approx(0.701835, abs=1e-5), pytest.approx(0.988133, abs=1e-5))
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
    assert math.isclose(stats.rate(14, 15)["wilson95"][0], 0.701835, abs_tol=1e-5)
    # Capped at 1, since no rate exceeds it: n = 1 -> min(1, 3/1 = 3) = 1; n = 3 ->
    # min(1, 3/3 = 1) = 1; n = 4 -> min(1, 3/4 = 0.75) = 0.75.
    assert (stats.rule_of_three(1), stats.rule_of_three(3)) == (1.0, 1.0)
    assert stats.rule_of_three(4) == pytest.approx(0.75)


def _no_git(args, **kwargs):
    raise OSError("no git in this test")


def _row(photo, outcome, *, tier="A", truth="gate", device="museum scan", radius=0, variant="true",
         reader="auto-corners", **extra):
    return {"photo": photo, "group": "corpus", "tier": tier, "truth": truth, "device_class": device,
            "resolution": "full", "condition": "clean", "reader": reader, "radius_px": radius,
            "variant": variant, "outcome": outcome, **extra}


# Hand-built rows for one reader at one resolution. p1, p2 and p7 are gate tier A museum
# scans with cell truth (p1 and p2 also have two 4 px trials each), p3 a provisional
# warned read with a miscount trial, p5 a screenshot whose read errored, and p4 and p6
# gate refusal-tier photos, p6 skipped for want of a frame.
ROWS = [
    _row("p1", "read", dims_exact=True, cell_truth=True, squares=9, confident_wrong=1, fully_correct=False),
    _row("p1", "held", radius=4, trial=0, dims_exact=False, radius_squares=0.2),
    _row("p1", "read", radius=4, trial=1, dims_exact=True, radius_squares=0.2),
    _row("p2", "held", dims_exact=False, cell_truth=True, squares=16, confident_wrong=0, fully_correct=False),
    _row("p2", "read", radius=4, trial=0, dims_exact=True, radius_squares=0.2),
    _row("p2", "read", radius=4, trial=1, dims_exact=True, radius_squares=0.2),
    _row("p7", "read", dims_exact=True, cell_truth=True, squares=4, confident_wrong=0, fully_correct=True),
    _row("p3", "warned", truth="provisional", dims_exact=True, cell_truth=False),
    _row("p3", "refused", truth="provisional", variant="square +1 across"),
    _row("p5", "error", device="screenshot", error="RuntimeError('x')"),
    _row("p4", "refused", tier="R"),
    _row("p6", "skipped", tier="R", reason=harness.SKIP_REASON),
]


def _gate(agg, device, truth):
    return next(e for e in agg["gate_metrics"] if (e["device_class"], e["truth"]) == (device, truth))


def test_gate_metrics_count_photos_at_true_corners_and_split_gate_from_provisional():
    agg = report.aggregate(ROWS, runner=_no_git)
    # Groups: (auto-corners, museum scan, full) and (auto-corners, screenshot, full), each
    # with a gate and a provisional entry, then the pooled (auto-corners, full) pair:
    # 2 x 2 + 2 = 6.
    assert len(agg["gate_metrics"]) == 6
    gate = _gate(agg, "museum scan", "gate")
    # Photo rows (radius 0, true counts): p1 read, p2 held, p7 read in tier A; p4 refused
    # and p6 skipped in tier R. The 4 px trials never enter.
    # G1: gold rows p1, p2, p7; fully correct only p7: 1 of 3.
    assert (gate["G1"]["k"], gate["G1"]["n"]) == (1, 3)
    # G2: confident-wrong 1 + 0 + 0 = 1 over squares 9 + 16 + 4 = 29: 1/29 = 0.0344828,
    # behind 3 gold photos.
    assert (gate["G2"]["k"], gate["G2"]["n"], gate["G2"]["photos"]) == (1, 29, 3)
    assert gate["G2"]["rate"] == pytest.approx(0.0344828, abs=1e-6)
    # G4: p4 refused counts 1 of 1; p6 skipped never enters n and is counted beside it.
    assert (gate["G4"]["k"], gate["G4"]["n"], gate["G4"]["skipped"], gate["G4"]["errors"]) == (1, 1, 1, 0)
    # G5 at true corners only: p2 held of p1, p2, p7: 1 of 3. Counting the trials would
    # have given 2 of 7.
    assert (gate["G5"]["k"], gate["G5"]["n"]) == (1, 3)
    # Provisional: p3 warned is no hold or refusal, 0 of 1, so its 3/n bound is
    # min(1, 3/1) = 1.0; its miscount trial (refused) never enters. No gold rows, no
    # refusal photos: n = 0.
    prov = _gate(agg, "museum scan", "provisional")
    assert (prov["G5"]["k"], prov["G5"]["n"], prov["G5"]["rule_of_three"]) == (0, 1, 1.0)
    assert prov["G1"]["n"] == 0 and prov["G4"]["n"] == 0
    # The screenshot's only row errored: n = 0 with 1 error.
    shot = _gate(agg, "screenshot", "gate")
    assert (shot["G5"]["n"], shot["G5"]["errors"]) == (0, 1)
    # Pooled over the device classes, gate: p1, p2, p7 (museum) and p5 (screenshot, an
    # error): p2 held of 3 scored, 1 error. G1, G2 and G4 are not pooled.
    pooled = _gate(agg, "all in scope", "gate")
    assert (pooled["G5"]["k"], pooled["G5"]["n"], pooled["G5"]["errors"]) == (1, 3, 1)
    assert (pooled["G1"], pooled["G2"], pooled["G4"]) == (None, None, None)
    pooled = _gate(agg, "all in scope", "provisional")
    assert (pooled["G5"]["k"], pooled["G5"]["n"], pooled["conflict_rows"]) == (0, 1, 0)
    assert agg["miscount_trials"] == 1
    assert [e["photo"] for e in agg["errors"]] == ["p5"]


def test_tier_and_device_tables_count_photos():
    agg = report.aggregate(ROWS, runner=_no_git)
    tier_a = agg["by_tier"]["auto-corners | A | full"]
    # Tier A photo rows: p1, p2, p7, p3 (warned) and p5 (error): 5 photos, 5 rows.
    assert (tier_a["n_photos"], tier_a["n_rows"], tier_a["errors"], tier_a["skipped"]) == (5, 5, 1, 0)
    # Outcomes over the 4 scored rows: read p1, p7; warned p3; held p2.
    assert tier_a["outcomes"] == {"read": 2, "warned": 1, "held": 1}
    # False warning: held or refused, p2 only, of 4 scored: 1 of 4, with p5's error beside it.
    fw = tier_a["false_warning"]
    assert (fw["k"], fw["n"], fw["errors"]) == (1, 4, 1)
    # Count top-1: dims exact for p1, p7, p3, not p2: 3 of 4.
    assert (tier_a["count_top1"]["k"], tier_a["count_top1"]["n"]) == (3, 4)
    # Truth behind the 4 scored rows: p1, p2, p7 gate; p3 provisional; none in conflict.
    assert tier_a["truth_rows"] == {"gate": 3, "provisional": 1, "conflict": 0}
    tier_r = agg["by_tier"]["auto-corners | R | full"]
    assert (tier_r["n_photos"], tier_r["refusal_recall"]["k"], tier_r["refusal_recall"]["n"],
            tier_r["refusal_recall"]["skipped"]) == (2, 1, 1, 1)
    # The device table splits tiers: museum tier A, screenshot tier A, museum tier R.
    assert set(agg["by_device_class"]) == {
        "auto-corners | A | museum scan | full", "auto-corners | A | screenshot | full",
        "auto-corners | R | museum scan | full"}
    museum_a = agg["by_device_class"]["auto-corners | A | museum scan | full"]
    # p1, p2, p7, p3: 4 photos; false warning p2 of 4.
    assert museum_a["n_photos"] == 4
    assert (museum_a["false_warning"]["k"], museum_a["false_warning"]["n"]) == (1, 4)
    # corpus.DEVICE_CLASS names museum scan, screenshot and phone camera; the rows hold the
    # first two.
    assert agg["device_classes_without_photos"] == ["phone camera"]


def test_jitter_counts_trials_without_an_interval():
    agg = report.aggregate(ROWS, runner=_no_git)
    four = agg["jitter"]["auto-corners | full | 4"]
    # Trials at 4 px: p1 held, p1 read, p2 read, p2 read. False warning 1 of 4 trials on
    # 2 photos; count top-1 3 of 4 (p1's held trial missed); mean radius (4 x 0.2) / 4 = 0.2.
    assert four["false_warning"] == {"k": 1, "n": 4, "photos": 2, "errors": 0, "skipped": 0}
    assert four["count_top1"] == {"k": 3, "n": 4, "photos": 2, "errors": 0, "skipped": 0}
    assert four["mean_radius_squares"] == pytest.approx(0.2)
    text = report.markdown({"header": {"title": "t"}, "aggregate": agg})
    line = next(row for row in text.splitlines() if row.startswith("| auto-corners | full | 4 |"))
    assert "1/4 trials, 2 photos" in line and "3/4 trials, 2 photos" in line
    # No Wilson interval and no 3/n bound on a trial row.
    assert "[" not in line and "3/n" not in line
    assert "not independent" in text


def test_markdown_rate_cells_name_errors_and_skips():
    agg = report.aggregate(ROWS, runner=_no_git)
    text = report.markdown({"header": {"title": "t"}, "aggregate": agg}).splitlines()
    gate = next(row for row in text if row.startswith("| auto-corners | museum scan | full | gate |"))
    cells = [c.strip() for c in gate.split("|")[1:-1]]
    # Columns: reader, device, resolution, truth, G1, G2, G4, G5.
    # G2: 1/29 = 0.0344828 -> 0.0345 at 4 places, behind 3 photos.
    assert cells[5].startswith("3 photos: 1/29 squares = 0.0345 [")
    # G4: 1/1 = 1.000 with an interval, then the skipped refusal photo, and why a corner
    # reader skips refusal photos.
    assert cells[6].startswith("1/1 = 1.000 [")
    assert cells[6].endswith(", 1 skipped; no frame or counts on the v0 refusal photos (#243)")
    shot = next(row for row in text if row.startswith("| auto-corners | screenshot | full | gate |"))
    assert shot.split("|")[8].strip() == "n = 0, 1 errors"
    tier = next(row for row in text if row.startswith("| auto-corners | museum tier A (in scope) | full |"))
    # Outcomes read / warned / held / refused: 2 / 1 / 1 / 0; gate / provisional / conflict
    # rows 3 / 1 / 0.
    assert "| 2 / 1 / 1 / 0 |" in tier and "| 3 / 1 / 0 |" in tier
    assert any("G2 counts squares, which cluster by photo" in row for row in text)
    assert any("#237 tracks loading it" in row for row in text)


def test_pending_metrics_ask_git_in_the_repo_through_an_injected_runner():
    seen = []

    class Done:
        returncode = 0
        stdout = "abc1234 Merge pull request #300 from jakemismas/slice/s5-a3b-method\n"

    def runner(args, **kwargs):
        seen.append((args, kwargs.get("cwd")))
        return Done()

    assert report.merged_in_tree("slice/s5-a3b-", runner) is True
    assert report.merged_in_tree("slice/s5-b3-", runner) is False
    # git runs at the repo root, whatever the caller's directory.
    assert all(cwd == report.REPO for _, cwd in seen)
    assert (report.REPO / "scripts" / "eval" / "qrep_eval" / "report.py").is_file()
    pending = report._pending(runner)
    assert pending["G6"].startswith("n/a: A3b is merged")
    assert pending["G3"].startswith("n/a until B3 merges") and "#237" in pending["G3"]
    # No git: None, and the text says so.
    assert report.merged_in_tree("slice/s5-a3b-", _no_git) is None
    assert report._pending(_no_git)["G6"] == "n/a until A3b merges (git unavailable)"


def _unit(*, counts=None, cells=TRUTH, fabrics=2, bands=()) -> harness.Unit:
    counts = counts or Counts(blocks_across=1, blocks_down=1, squares_per_block_across=3,
                              squares_per_block_down=3)
    truth = corpus.TruthView(corners=[(0.0, 0.0), (30.0, 0.0), (30.0, 30.0), (0.0, 30.0)], bands=list(bands),
                             counts=counts, fabric_count=fabrics, construction="squares",
                             # A hand-authored count is square truth, so a gate row scores k on it.
                             provenance={"frame": "verified-jake", "fabrics": "hand-authored"})
    return harness.Unit(photo="p", group="corpus", tier="A", split="dev", license="CC0-1.0",
                        device_class="museum scan", resolution="full", cap=None, condition="clean",
                        source="unused.png", canvas=(40, 40), truth=truth, truth_label="gate",
                        readers=("auto",), radii=(0,), trials=1, seed="t", truth_cells=cells,
                        truth_colors=[RED, BLUE] if cells is not None else None)


def _reading(outcome, *, colors=(RED, BLUE), cells=None, confidence=None, verdict=None, received=None,
             low=0.9, bands=(), dims=None) -> readers.Reading:
    rows, cols = dims or ((len(cells), len(cells[0])) if cells else (0, 0))
    return readers.Reading(outcome=outcome, verdict=verdict, rows=rows, cols=cols,
                           colors=list(colors), cells=cells, confidence=confidence, cell_size_eighths=16,
                           band_eighths=list(bands), low_confidence_below=low, flagged_regions=[], seconds=0.0,
                           received=received if received is not None else {"fabrics": None})


def _swapped():
    read = [row[:] for row in TRUTH]
    read[1][1] = 1
    return read


def test_score_a_refusal_ships_nothing():
    out = harness.score(_unit(), _reading("refused", colors=(), verdict="no_grid"))
    # A refusal shows no grid: dims and k are not exact, and no square is scored right
    # or confidently wrong (no PDF ships). Squares in the truth: 3 x 3 = 9.
    assert (out["dims_exact"], out["harmonic"], out["k_exact"]) == (False, False, False)
    assert out["k_truth"] == 2
    assert (out["squares"], out["accuracy_many_to_one"], out["confident_wrong"],
            out["fully_correct"]) == (9, None, 0, False)


def test_score_a_warned_read_ships_its_squares():
    reading = _reading("warned", cells=_swapped(), confidence=[row[:] for row in ONES],
                       verdict="non_square_repeat")
    out = harness.score(_unit(), reading)
    # A warned read still ships a PDF, so its squares count: 8 of 9 right, and the swapped
    # square at confidence 1.0 is not below 0.9, so it is confident-wrong: 1.
    assert (out["dims_exact"], out["k_exact"]) == (True, True)
    assert out["accuracy_many_to_one"] == pytest.approx(8 / 9)
    assert (out["confident_wrong"], out["fully_correct"]) == (1, False)


def test_score_a_doubled_count_is_a_harmonic():
    # Truth 1 block of 6 x 6 squares: 6 rows, 6 columns. Read 12 rows, 6 columns:
    # 12 / 6 = 2, a harmonic in HARMONICS; not exact.
    six = Counts(blocks_across=1, blocks_down=1, squares_per_block_across=6, squares_per_block_down=6)
    cells = [[0] * 6 for _ in range(12)]
    out = harness.score(_unit(counts=six, cells=None),
                        _reading("read", cells=cells, confidence=[[1.0] * 6 for _ in range(12)]))
    assert out["truth_dims"] == [6, 6] and out["read_dims"] == [12, 6]
    assert (out["dims_exact"], out["harmonic"], out["periodic"]) == (False, True, False)


def test_score_a_phantom_fabric_fails_g1_only_through_k():
    # The phantom-fabric read of test_a_phantom_fabric_is_absorbed_many_to_one_but_not_one_to_one:
    # many-to-one maps every square to its role (accuracy 9/9 = 1), the bands match (none
    # on either side), and the only G1 condition that fails is k: 3 read against 2 roles.
    # One-to-one leaves fabric 2 unmatched: 7/9.
    cells = [[2, 1, 0], [1, 0, 1], [0, 1, 2]]
    reading = _reading("read", colors=("#f00000", "#0000f0", "#c00000"), cells=cells,
                       confidence=[row[:] for row in ONES])
    out = harness.score(_unit(), reading)
    assert out["accuracy_many_to_one"] == pytest.approx(1.0)
    assert out["accuracy_one_to_one"] == pytest.approx(7 / 9)
    assert (out["bands_ok"], out["k_mismatch"], out["fully_correct"], out["confident_wrong"]) == (
        True, 1, False, 0)
    assert out["k_exact"] is False


def test_a_given_fabric_count_is_not_scored_as_k():
    # extract_palette forces k to a given count, so k_exact is left out and k_truth kept.
    cells = [row[:] for row in TRUTH]
    for received in ({"fabrics": 2}, {"request": {"fabric_count": 2}}):
        out = harness.score(_unit(), _reading("read", cells=cells, confidence=ONES, received=received))
        assert "k_exact" not in out and out["k_truth"] == 2
    out = harness.score(_unit(), _reading("read", cells=cells, confidence=ONES,
                                          received={"request": {"fabric_count": None}}))
    # Chosen by the read: k = 2 of 2 colors read, the truth's 2: exact.
    assert out["k_exact"] is True


def test_missing_confidence_flags_no_square():
    # No confidences: nothing says a square was doubted, so the swapped square stays
    # confident-wrong (1) and the row says the confidence was missing.
    for confidence in (None, []):
        out = harness.score(_unit(), _reading("read", cells=_swapped(), confidence=confidence))
        assert out["confidence_missing"] is True
        assert out["confident_wrong"] == 1
    # With a stated 0.5 on that square: 0.5 < 0.9 flags it, so 0 confident-wrong.
    stated = [row[:] for row in ONES]
    stated[1][1] = 0.5
    out = harness.score(_unit(), _reading("read", cells=_swapped(), confidence=stated))
    assert out["confident_wrong"] == 0 and "confidence_missing" not in out


def test_r1_reports_the_automatic_read_on_tier_a_photos_only():
    rows = [
        # auto on tier A: q1 and q2 periodic, q3 and q4 not; q2 read a doubled grid.
        _row("q1", "read", reader="auto", radius=None, periodic=True, dims_exact=True, harmonic=False,
             k_exact=True),
        _row("q2", "read", reader="auto", radius=None, periodic=True, dims_exact=False, harmonic=True,
             k_exact=False),
        _row("q3", "read", reader="auto", radius=None, periodic=False, dims_exact=True, harmonic=False,
             k_exact=True),
        _row("q4", "read", reader="auto", radius=None, periodic=False, dims_exact=True, harmonic=False,
             k_exact=False),
        # Neither a tier B photo nor another reader enters R1.
        _row("q5", "read", reader="auto", tier="B", radius=None, periodic=True, dims_exact=False,
             harmonic=True, k_exact=False),
        _row("q1", "read", periodic=True, dims_exact=False, harmonic=True, k_exact=False),
    ]
    r1 = report.aggregate(rows, runner=_no_git)["r1"]["by_resolution"]
    assert list(r1) == ["full"]
    full = r1["full"]
    # Periodic: q1 exact, q2 not: 1 of 2. Non-periodic: q3 and q4 exact: 2 of 2.
    # Harmonic: q2 of q1..q4: 1 of 4. Fabric count exact: q1 and q3 of 4: 2 of 4 (count
    # top-1 over all four is 3 of 4, so the two cannot stand in for each other).
    # The tier B row or the auto-corners row leaking in would make these 1 of 3, and
    # 2 of 5 and 2 of 5.
    got = {key: (full[key]["k"], full[key]["n"]) for key in (
        "count_top1_periodic", "count_top1_non_periodic", "harmonic_error", "fabric_count_suggestion_exact")}
    assert got == {"count_top1_periodic": (1, 2), "count_top1_non_periodic": (2, 2),
                   "harmonic_error": (1, 4), "fabric_count_suggestion_exact": (2, 4)}
    assert full["count_top3"].startswith("n/a")


def test_named_latency_per_photo_and_jitter_take_their_own_rows():
    named = {**_row("busy", "read", reader="auto", radius=None, seconds=10.0), "group": "named",
             "tier": "named", "truth": "synthetic"}
    rows = [
        named,
        {**named, "variant": "half", "seconds": 50.0},
        _row("s1", "read", reader="auto", radius=None, seconds=1.0),
        _row("s2", "read", seconds=2.0, dims_exact=True),
        _row("s2", "read", variant="half", seconds=100.0),
        _row("s1", "read", radius=4, trial=0, seconds=4.0, dims_exact=True),
        _row("s3", "read", tier="B", radius=4, trial=0, seconds=3.0, dims_exact=True),
        _row("s4", "error", error="x"),
        _row("s5", "read", tier="B"),
    ]
    agg = report.aggregate(rows, runner=_no_git)
    # Named: the named row with the true counts only.
    assert agg["named"] == [named]
    # Latency: the scored rows with the true counts, every group: 10, 1, 2, 4 and 3 s;
    # sorted 1, 2, 3, 4, 10, median 3 over 5 reads. The miscount rows (50 and 100 s) and
    # the error row stay out.
    latency = agg["r1"]["latency"]
    assert (latency["native_median_seconds_per_read"], latency["n_reads"]) == (3.0, 5)
    # Per photo: corpus tier A at true corners only: s1 by auto, s2 and s4 by auto-corners;
    # not s5, a tier B photo at true corners.
    picked = [(p["photo"], p["reader"]) for p in report.per_photo(rows)]
    assert picked == [("s1", "auto"), ("s2", "auto-corners"), ("s4", "auto-corners")]
    # Jitter: tier A only, so the 4 px group holds s1's trial and not s3's (tier B).
    assert set(agg["jitter"]) == {"auto-corners | full | 0", "auto-corners | full | 4"}
    assert agg["jitter"]["auto-corners | full | 4"]["n_rows"] == 1


def test_g1_counts_errors_and_skips_among_the_gold_photos_only():
    rows = [
        _row("g1", "read", cell_truth=True, squares=4, confident_wrong=0, fully_correct=True),
        _row("g2", "error", cell_truth=True, error="x"),
        _row("g3", "error", cell_truth=False, error="x"),
        _row("g4", "skipped", cell_truth=False),
        _row("g5", "skipped", cell_truth=True),
    ]
    gate = _gate(report.aggregate(rows, runner=_no_git), "museum scan", "gate")
    # Gold rows g1, g2, g5: G1 1 of 1 scored, with g2's error and g5's skip beside it.
    assert {k: gate["G1"][k] for k in ("k", "n", "errors", "skipped")} == {
        "k": 1, "n": 1, "errors": 1, "skipped": 1}
    # G5 counts every in-scope row: g1 scored, 2 errors (g2, g3) and 2 skipped (g4, g5).
    assert {k: gate["G5"][k] for k in ("k", "n", "errors", "skipped")} == {
        "k": 0, "n": 1, "errors": 2, "skipped": 2}


def test_conflict_rows_count_toward_no_gate_and_g5_pools_the_devices():
    rows = [
        _row("c1", "read"),
        _row("c2", "held", device="screenshot"),
        _row("c3", "refused", truth="provisional"),
        _row("c4", "held", truth="conflict"),
        _row("c5", "refused", tier="R", truth="conflict"),
    ]
    agg = report.aggregate(rows, runner=_no_git)
    # Museum gate G5: c1 only, 0 of 1. Museum provisional G5: c3 refused, 1 of 1; its G4
    # has no provisional refusal photo (c5 is a conflict): n = 0. The museum group holds
    # 2 conflict rows, c4 and c5.
    gate = _gate(agg, "museum scan", "gate")["G5"]
    assert (gate["k"], gate["n"]) == (0, 1)
    prov = _gate(agg, "museum scan", "provisional")
    assert (prov["G5"]["k"], prov["G5"]["n"], prov["G4"]["n"], prov["conflict_rows"]) == (1, 1, 0, 2)
    # Pooled gate: c1 (museum) and c2 (screenshot), c2 held: 1 of 2. Pooled provisional:
    # c3, 1 of 1, beside 1 in-scope conflict row (c4).
    pooled_gate = _gate(agg, "all in scope", "gate")["G5"]
    assert (pooled_gate["k"], pooled_gate["n"]) == (1, 2)
    pooled = _gate(agg, "all in scope", "provisional")
    assert (pooled["G5"]["k"], pooled["G5"]["n"], pooled["conflict_rows"]) == (1, 1, 1)
    # The tier table pools labels and names the mix: c1, c2 gate; c3 provisional; c4 conflict.
    assert agg["by_tier"]["auto-corners | A | full"]["truth_rows"] == {
        "gate": 2, "provisional": 1, "conflict": 1}
    text = report.markdown({"header": {"title": "t"}, "aggregate": agg}).splitlines()
    line = next(r for r in text if r.startswith("| auto-corners | all in scope | full | provisional"))
    assert line.split("|")[4].strip() == "provisional (1 conflict rows)"
    assert [c.strip() for c in line.split("|")[5:8]] == ["n/a", "n/a", "n/a"]


def test_score_a_refusal_that_matches_the_truth_still_scores_nothing():
    # A refused reading whose grid (3 x 3) and k (2) equal the truth's: nothing was
    # shown, so dims and k are not exact.
    out = harness.score(_unit(), _reading("refused", cells=[row[:] for row in TRUTH], confidence=ONES,
                                          verdict="no_grid"))
    assert (out["dims_exact"], out["k_exact"]) == (False, False)
    # A refused 6 x 3 against the 3 x 3 truth (6 / 3 = 2) is no harmonic either.
    out = harness.score(_unit(cells=None), _reading("refused", dims=(6, 3)))
    assert out["harmonic"] is False


def test_score_bands_in_inches_at_the_reads_square_size():
    # Truth band 1.5 squares; the read square is 16 eighths (2 in): 1.5 x 16 / 8 = 3.0 in.
    # A read band of 24 eighths is 24 / 8 = 3.0 in: a match, and with every square right
    # and k 2 = 2 the interior is fully correct.
    cells = [row[:] for row in TRUTH]
    out = harness.score(_unit(bands=[1.5]), _reading("read", cells=cells, confidence=ONES, bands=[24]))
    assert (out["bands_ok"], out["fully_correct"]) == (True, True)
    # 26 eighths = 3.25 in: 0.25 off, inside the inclusive 1/4 in. 27 eighths = 3.375 in:
    # 0.375 off, not a match, so not fully correct.
    out = harness.score(_unit(bands=[1.5]), _reading("read", cells=cells, confidence=ONES, bands=[26]))
    assert out["bands_ok"] is True
    out = harness.score(_unit(bands=[1.5]), _reading("read", cells=cells, confidence=ONES, bands=[27]))
    assert (out["bands_ok"], out["fully_correct"]) == (False, False)


def test_score_harmonics_on_unequal_axes():
    # Truth 1 block of 5 across x 6 down: 6 rows, 5 columns.
    counts = Counts(blocks_across=1, blocks_down=1, squares_per_block_across=5, squares_per_block_down=6)
    unit = _unit(counts=counts, cells=None)
    # Read 12 x 5: rows 12 / 6 = 2, a harmonic; columns equal.
    out = harness.score(unit, _reading("read", dims=(12, 5)))
    assert out["truth_dims"] == [6, 5]
    assert (out["dims_exact"], out["harmonic"]) == (False, True)
    # Read 5 x 12 (the axes swapped): 5 / 6 and 12 / 5 = 2.4 are no harmonics; not exact.
    out = harness.score(unit, _reading("read", dims=(5, 12)))
    assert (out["dims_exact"], out["harmonic"]) == (False, False)
    # Read 0 x 12 against 6 x 6: a zero axis is no grid, so no harmonic, though 12 / 6 = 2.
    six = Counts(blocks_across=1, blocks_down=1, squares_per_block_across=6, squares_per_block_down=6)
    out = harness.score(_unit(counts=six, cells=None), _reading("read", dims=(0, 12)))
    assert out["harmonic"] is False


def test_score_periodic_needs_more_than_one_block():
    # 2 blocks across x 1 down = 2 blocks: periodic. 1 x 1 = 1 block: not.
    two = Counts(blocks_across=2, blocks_down=1, squares_per_block_across=3, squares_per_block_down=3)
    assert harness.score(_unit(counts=two, cells=None), _reading("read", dims=(3, 6)))["periodic"] is True
    assert harness.score(_unit(cells=None), _reading("read", dims=(3, 3)))["periodic"] is False


def test_given_fabrics_keeps_the_reads_range():
    # The read accepts 2 to 12 fabrics (qrep/contract.py FABRICS_MIN, FABRICS_MAX).
    def view(count):
        return corpus.TruthView(corners=None, bands=[], counts=None, fabric_count=count, construction=None,
                                provenance={"fabrics": "hand-authored"})

    assert [harness.given_fabrics(view(n), "gate") for n in (None, 1, 2, 12, 13)] == [None, None, 2, 12, None]


def test_stress_rows_key_on_reader_condition_device_and_resolution():
    def stress(photo, outcome, device, resolution):
        return {**_row(photo, outcome, reader="auto", radius=None, device=device), "group": "stress",
                "condition": "glare", "resolution": resolution}

    rows = [stress("t1", "read", "museum scan", "full"), stress("t1", "held", "museum scan", "phone-1400"),
            stress("t2", "refused", "screenshot", "full")]
    agg = report.aggregate(rows, runner=_no_git)
    assert set(agg["stress"]) == {"auto | glare | museum scan | full", "auto | glare | museum scan | phone-1400",
                                  "auto | glare | screenshot | full"}
    # Each group holds one photo: t1 at full read (0 of 1 blocked), t1 at phone-1400 held
    # (1 of 1), t2 refused (1 of 1).
    got = {key: (s["false_warning"]["k"], s["false_warning"]["n"]) for key, s in agg["stress"].items()}
    assert got == {"auto | glare | museum scan | full": (0, 1), "auto | glare | museum scan | phone-1400": (1, 1),
                   "auto | glare | screenshot | full": (1, 1)}
    text = report.markdown({"header": {"title": "t"}, "aggregate": agg})
    assert "| auto | glare | museum scan | phone-1400 | 1 |" in text


def test_the_g4_note_appears_only_beside_skipped_refusal_photos():
    # Refusal photos all scored (none skipped): the G4 cell is the rate alone.
    agg = report.aggregate([_row("r1", "refused", tier="R")], runner=_no_git)
    text = report.markdown({"header": {"title": "t"}, "aggregate": agg}).splitlines()
    line = next(r for r in text if r.startswith("| auto-corners | museum scan | full | gate |"))
    assert "#243" not in line.split("|")[7]
    # One more refusal photo skipped: the note joins the cell.
    agg = report.aggregate([_row("r1", "refused", tier="R"), _row("r2", "skipped", tier="R")], runner=_no_git)
    text = report.markdown({"header": {"title": "t"}, "aggregate": agg}).splitlines()
    line = next(r for r in text if r.startswith("| auto-corners | museum scan | full | gate |"))
    assert line.split("|")[7].strip().endswith(", 1 skipped; no frame or counts on the v0 refusal photos (#243)")


def test_jitter_reports_the_realized_move_beside_the_radius():
    # Two 4 px trials at pitch 20 px: nominal 4 / 20 = 0.2 squares each. One moved the full
    # 4 px (0.2 squares), one was clamped to 2 px (2 / 20 = 0.1): mean (0.2 + 0.1) / 2 = 0.15.
    rows = [_row("j1", "read", radius=4, trial=0, radius_squares=0.2, moved_squares=0.2),
            _row("j1", "read", radius=4, trial=1, radius_squares=0.2, moved_squares=0.1)]
    four = report.aggregate(rows, runner=_no_git)["jitter"]["auto-corners | full | 4"]
    assert four["mean_radius_squares"] == pytest.approx(0.2)
    assert four["mean_moved_squares"] == pytest.approx(0.15)
    text = report.markdown({"header": {"title": "t"}, "aggregate": report.aggregate(rows, runner=_no_git)})
    assert "| auto-corners | full | 4 | 0.200 | 0.150 | 2 |" in text
