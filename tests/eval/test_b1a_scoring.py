"""B1a spike: the scoring helpers and the count methods on synthetic grids.

Every expected value is worked by hand in the comments beside its assertion, from the issue's
own example (#134), the Wilson formula, or the construction of the synthetic image; none comes
from running the spike. The synthetic images are built in Lab and converted to BGR, so a
designed step in the a channel reaches the methods as the same step (to rounding: one uint8
level moves a by well under 1 unit).
"""

import importlib.util
import shutil
import sys

import cv2
import numpy as np
import pytest

from spikes import b1a_counts as b1a

# --- Outcomes of one ranking -------------------------------------------------------------


def test_issue_example_top1_miss_top3_hit_harmonic():
    # Source: issue #134, criterion 1. Truth 40 x 40, candidates 8, 40, 10 in rank order.
    # top-1 is 8, not 40: a miss. 40 is among the first three: a top-3 hit.
    # 40 % 8 == 0, so the top-1 divides the truth: harmonic.
    outcome = b1a.score_ranking([8, 40, 10], 40)
    assert outcome == b1a.Outcome(top1=False, top3=True, harmonic=True)


def test_near_miss_is_not_harmonic():
    # Truth 40, top-1 39: 40 % 39 == 1 and 39 % 40 == 39, so neither divides the other.
    assert b1a.score_ranking([39, 41, 38], 40) == b1a.Outcome(False, False, False)
    # Truth 40, top-1 41: 40 % 41 == 40 and 41 % 40 == 1. Not harmonic; 40 is not in the list.
    assert b1a.score_ranking([41, 39, 42], 40) == b1a.Outcome(False, False, False)


def test_multiple_is_harmonic_and_hit_is_not():
    # Truth 20, top-1 40: 40 % 20 == 0, a multiple, so harmonic; 20 at rank 2 is a top-3 hit.
    assert b1a.score_ranking([40, 20], 20) == b1a.Outcome(False, True, True)
    # A correct top-1 is never a harmonic error.
    assert b1a.score_ranking([20, 40, 10], 20) == b1a.Outcome(True, True, False)
    # An empty ranking (a method that found nothing) misses everything.
    assert b1a.score_ranking([], 20) == b1a.Outcome(False, False, False)
    # Truth 12 at rank 4 of [4, 8, 6, 12] is outside the first three: a top-3 miss. 12 % 4 == 0.
    assert b1a.score_ranking([4, 8, 6, 12], 12) == b1a.Outcome(False, False, True)


def test_joint_outcomes():
    # Truth (50, 50). Top-1 (10, 10): wrong, and 50 % 10 == 0 on both axes, so harmonic.
    assert b1a.score_ranking([(10, 10), (50, 50)], (50, 50)) == b1a.Outcome(False, True, True)
    # Top-1 (25, 50): x is harmonic (50 % 25 == 0) and y is right, so harmonic.
    assert b1a.score_ranking([(25, 50)], (50, 50)) == b1a.Outcome(False, False, True)
    # Top-1 (50, 49): y is a near miss (50 % 49 == 1), so the pair is not harmonic.
    assert b1a.score_ranking([(50, 49)], (50, 50)) == b1a.Outcome(False, False, False)
    # Top-1 (25, 49): x is harmonic but y is a near miss, and every wrong axis must be harmonic.
    assert b1a.score_ranking([(25, 49)], (50, 50)) == b1a.Outcome(False, False, False)


# --- Quilter units and harmonic alternates -----------------------------------------------


def test_quilter_units():
    # 40 squares with a block period of 5: 40 / 5 = 8 blocks of 5 squares.
    assert b1a.quilter_units(40, 5) == (8, 5)
    # 40 % 3 == 1: a period that does not divide the count gives one block of 40.
    assert b1a.quilter_units(40, 3) == (1, 40)
    # No period found (0), or a period equal to the count: one block of 40.
    assert b1a.quilter_units(40, 0) == (1, 40)
    assert b1a.quilter_units(40, 40) == (1, 40)
    # A repeat of 10 (two alternating blocks of 5) in 55 squares: gcd(10, 55) = 5, since
    # 10 = 2 x 5 and 55 = 11 x 5, so 11 blocks of 5.
    assert b1a.quilter_units(55, 10) == (11, 5)


def test_harmonic_alternates():
    # Divisors of 40 other than 1 and 40: 2, 4, 5, 8, 10, 20. Multiples x2 and x3: 80, 120.
    assert b1a.harmonic_alternates(40, lo=2, hi=120) == [2, 4, 5, 8, 10, 20, 80, 120]
    # hi = 100 drops 120; lo = 5 drops 2 and 4.
    assert b1a.harmonic_alternates(40, lo=5, hi=100) == [5, 8, 10, 20, 80]


def test_is_periodic():
    # lacma-54871's proposal: 10 blocks of 5 each way, so the block repeats.
    assert b1a.is_periodic(blocks_across=10, blocks_down=10)
    # A stair-step quilt is recorded as one block per axis: no repeating block.
    assert not b1a.is_periodic(blocks_across=1, blocks_down=1)
    # A repeat on one axis is enough.
    assert b1a.is_periodic(blocks_across=1, blocks_down=3)


# --- Joint ranking under the square-grid prior -------------------------------------------


def test_joint_ranking_rank_sum_and_pitch_prior():
    # Field 1000 x 1040 px; per-axis rankings x = [50, 10, 25], y = [10, 50, 52]; prior 1.15.
    # Pitch ratio of a pair = max(px, py) / min(px, py), px = 1000 / nx, py = 1040 / ny:
    #   (50, 10): 20 vs 104 -> 5.2, dropped.     (50, 50): 20 vs 20.8 -> 1.04, kept, ranks 0+1.
    #   (10, 10): 100 vs 104 -> 1.04, kept, 1+0. (50, 52): 20 vs 20 -> 1.0, kept, 0+2.
    #   (10, 50): 100 vs 20.8, dropped. (10, 52): 100 vs 20, dropped. (25, 10): 40 vs 104,
    #   dropped. (25, 50): 40 vs 20.8 -> 1.92, dropped. (25, 52): 40 vs 20 -> 2.0, dropped.
    # Sort key (rank sum, larger rank, x rank): (50, 50) -> (1, 1, 0) before (10, 10) -> (1, 1, 1),
    # then (50, 52) -> (2, 2, 0).
    ranked = b1a.joint_ranking([50, 10, 25], [10, 50, 52], width=1000, height=1040, k=3)
    assert ranked == [(50, 50), (10, 10), (50, 52)]


def test_joint_ranking_empty_axis():
    # A method that found nothing on one axis offers no pair.
    assert b1a.joint_ranking([], [10], width=100, height=100, k=3) == []


# --- Rates, intervals and the decision rule ----------------------------------------------


def test_summarize_rates():
    # Four trials: (hit, hit, -), (miss, hit, harmonic), (miss, miss, -), (miss, hit, -).
    # top-1 1 of 4 = 0.25; top-3 3 of 4 = 0.75; harmonic top-1 1 of 4 = 0.25.
    outcomes = [
        b1a.Outcome(True, True, False),
        b1a.Outcome(False, True, True),
        b1a.Outcome(False, False, False),
        b1a.Outcome(False, True, False),
    ]
    summary = b1a.summarize(outcomes)
    assert (summary["n"], summary["top1"], summary["top3"], summary["harmonic"]) == (4, 1, 3, 1)
    assert summary["top1_rate"] == pytest.approx(0.25)
    assert summary["top3_rate"] == pytest.approx(0.75)
    assert summary["harmonic_rate"] == pytest.approx(0.25)


def test_wilson_interval():
    # k = 9, n = 11, z = 1.96: p = 9/11 = 0.818182, z^2 = 3.8416.
    # denom = 1 + z^2/n = 1 + 0.349236 = 1.349236.
    # centre = (p + z^2/(2n)) / denom = (0.818182 + 0.174618) / 1.349236 = 0.992800 / 1.349236
    #        = 0.735824.
    # half = z * sqrt(p(1-p)/n + z^2/(4n^2)) / denom
    #      = 1.96 * sqrt(0.148760/11 + 3.8416/484) / 1.349236
    #      = 1.96 * sqrt(0.013524 + 0.007937) / 1.349236 = 1.96 * 0.146495 / 1.349236 = 0.212810.
    # Interval: 0.735824 -/+ 0.212810 = [0.523014, 0.948634] (the last digit carries rounding).
    lo, hi = b1a.wilson(9, 11)
    assert lo == pytest.approx(0.523014, abs=2e-6)
    assert hi == pytest.approx(0.948634, abs=2e-6)
    # k = 0 puts the centre's lower bound at 0, never below it.
    assert b1a.wilson(0, 5)[0] == 0.0
    # n = 0 has no information: the whole unit interval.
    assert b1a.wilson(0, 0) == (0.0, 1.0)


def test_two_part_fit_rule():
    # exp2's two scores: truths (ratio, MAD) (1.8, 1.2) and (1.6, 1.5) set the thresholds at
    # ratio 1.6 (lowest truth) and MAD 1.5 (highest truth).
    truths = [(1.8, 1.2), (1.6, 1.5)]
    # (1.5, 1.0): ratio 1.5 < 1.6, rejected.
    assert b1a.two_part_rejects((1.5, 1.0), truths)
    # (2.0, 1.7): MAD 1.7 > 1.5, rejected.
    assert b1a.two_part_rejects((2.0, 1.7), truths)
    # (1.7, 1.4): ratio 1.7 >= 1.6 and MAD 1.4 <= 1.5, so it passes both scores unnoticed.
    assert not b1a.two_part_rejects((1.7, 1.4), truths)


def test_decision_rule_two_part():
    # Issue #134 criterion 6 as the Go column records it: ship when top-3 recall >= BAR (0.8)
    # and exp2's two-part rule rejects every wrong top-1 (one flag per wrong top-1).
    # 0.82 >= 0.8 and both wrong top-1s rejected: go.
    assert b1a.decide_two_part(0.82, [True, True])
    # One wrong top-1 passes both thresholds unnoticed: no-go, however high the recall.
    assert not b1a.decide_two_part(0.95, [True, False])
    # 0.79 < 0.8: no-go, even with every wrong top-1 rejected.
    assert not b1a.decide_two_part(0.79, [True])
    # The bar is inclusive (0.8 >= 0.8), and no wrong top-1 leaves nothing to reject:
    # all([]) is True.
    assert b1a.decide_two_part(0.8, [])


def test_decision_rule():
    # The product reading of criterion 6 (go_product in the JSON; the recorded Go uses
    # decide_two_part): ship when top-3 recall >= 0.8 and every wrong top-1's product fit
    # sits below the lowest true-count fit.
    # 0.82 >= 0.8, and max wrong 1.3 < min truth 1.5: go.
    assert b1a.decide(0.82, wrong_fits=[1.1, 1.3], truth_fits=[1.5, 2.0])
    # A wrong top-1 at 1.6 is not below the truth's 1.5: the fit would pass it unnoticed.
    assert not b1a.decide(0.82, wrong_fits=[1.6], truth_fits=[1.5])
    # 0.79 is under the bar whatever the fit says.
    assert not b1a.decide(0.79, wrong_fits=[], truth_fits=[1.5])
    # The bar is inclusive, and no wrong top-1 leaves nothing to reject.
    assert b1a.decide(0.8, wrong_fits=[], truth_fits=[1.5])
    # A wrong top-1 that ties the worst truth is not rejected: the threshold cannot split them.
    assert not b1a.decide(0.9, wrong_fits=[1.5], truth_fits=[1.5, 2.0])


# --- Geometry ----------------------------------------------------------------------------


def test_jitter_moves_each_corner_by_the_radius():
    # Each corner moves r * (cos t, sin t), whose length is r * sqrt(cos^2 t + sin^2 t) = r.
    corners = np.array([[0.0, 0.0], [300.0, 0.0], [300.0, 400.0], [0.0, 400.0]])
    moved = b1a.jitter_corners(corners, 4.0, np.random.default_rng(7))
    assert np.linalg.norm(moved - corners, axis=1) == pytest.approx([4.0] * 4, abs=1e-9)
    # Each corner draws its own direction (four independent uniform angles), so the move is not
    # one shared translation.
    angles = np.round(np.arctan2(*(moved - corners).T[::-1]), 6)
    assert len(set(angles)) == 4
    # Radius 0 leaves every corner in place.
    still = b1a.jitter_corners(corners, 0.0, np.random.default_rng(7))
    assert np.array_equal(still, corners)


def test_field_size_means_opposite_edges():
    # A 300 x 400 rectangle: top and bottom 300, left and right 400.
    rect = np.array([[0.0, 0.0], [300.0, 0.0], [300.0, 400.0], [0.0, 400.0]])
    assert b1a.field_size(rect) == (300, 400)
    # Top 100; bottom from (0, 50) to (110, 50) is 110; mean 105.
    # Left 50; right from (100, 0) to (110, 50) is sqrt(10^2 + 50^2) = 50.99; mean 50.495 -> 50.
    skew = np.array([[0.0, 0.0], [100.0, 0.0], [110.0, 50.0], [0.0, 50.0]])
    assert b1a.field_size(skew) == (105, 50)


# --- The methods on synthetic grids ------------------------------------------------------


def _lab_to_bgr(lab: np.ndarray) -> np.ndarray:
    bgr = cv2.cvtColor(lab.astype(np.float32), cv2.COLOR_Lab2BGR)
    return np.clip(np.round(bgr * 255.0), 0, 255).astype(np.uint8)


def _checkerboard(n: int = 12, pitch: int = 20) -> np.ndarray:
    # Two fabrics that differ in value and chroma: Lab (50, 30, 20) and (70, -30, -20). The
    # value step keeps the gray edge profile of the autocorrelation method well above zero.
    size = n * pitch
    lab = np.empty((size, size, 3), np.float32)
    ys, xs = np.mgrid[0:size, 0:size]
    odd = ((ys // pitch) + (xs // pitch)) % 2 == 1
    lab[..., 0] = np.where(odd, 70.0, 50.0)
    lab[..., 1] = np.where(odd, -30.0, 30.0)
    lab[..., 2] = np.where(odd, -20.0, 20.0)
    return _lab_to_bgr(lab)


FULL_FIELD = np.array([[0.0, 0.0], [240.0, 0.0], [240.0, 240.0], [0.0, 240.0]])


@pytest.mark.parametrize("method", ["autocorr", "fit", "fit_interior"])
def test_checkerboard_methods_find_twelve(method):
    # A 12 x 12 checkerboard of 20 px squares fills the 240 x 240 field. Every one of the 11
    # interior seams on each axis is the same step, and nothing else changes inside a square.
    # Autocorrelation: the binarized edge profile spikes every 20 px, so its smallest strong
    # lag is 20 and the count is 240 / 20 = 12.
    # Fit: at 12 every seam sample lands on a step and every centre sample on flat fabric,
    # and every half-pitch-shifted square straddles a step while every aligned square is
    # flat. A divisor (6) puts its centres on steps (edge gain about 1); a multiple (24) puts
    # half its seams on flat fabric (lower seam mean). The divisor 4 puts its seams on steps
    # and its centres (30, 90, ...) on flat fabric, so its edge ratio ties 12's; it loses on
    # the chroma gain, because its aligned squares hold four fabrics' worth of steps while
    # 12's are flat. Any other count misses most steps.
    # Fit interior samples each square's inner 70 percent (3 to 17 px of a 20 px square): at 12
    # those samples sit 3 px or more from a step, where the blurred step has fallen to about a
    # quarter of its height, so the interior mean is about a tenth of the seam mean; at 24, 12
    # of the 23 seam samples sit on flat fabric while the 10 px squares' interiors come within
    # 1.5 px of a step; a divisor's interior samples land on the steps inside its squares,
    # which lowers its edge ratio, and other counts miss most steps.
    # So all three rank 12 first on both axes.
    field = b1a.FieldImage.from_bgr(_checkerboard(), FULL_FIELD)
    ranking_x, ranking_y = b1a.METHODS[method](field)
    assert ranking_x[0] == 12
    assert ranking_y[0] == 12


def test_tap_seed_on_checkerboard_finds_twelve():
    # A tap at the centre of square (5, 5), (110, 110), with no jitter. Its 4-connected
    # same-fabric region is that square alone (same-fabric squares meet it only at corners).
    # Blur (sigma 1 on the image, then 2 in tap_region: about 2.2 px together) moves each
    # side in until the color is within 10 of the tapped fabric; the fabrics differ by about
    # 73 (L*0.5, a, b), so that is the 14 percent point of the blurred step, about 1.1 sigma
    # or 2.5 px inside, give or take a pixel. So the region is between 10 and 20 px, the pitch
    # search range [0.5 b, 2 b] holds 20, and it excludes 40 because b < 20. The window's
    # autocorrelation peaks every 20 px, so the pitch is 20 and the count is 240 / 20 = 12.
    field = b1a.FieldImage.from_bgr(_checkerboard(), FULL_FIELD)
    region_x, region_y = b1a.tap_region(field, (110.0, 110.0))
    assert 10 < region_x < 20 and 10 < region_y < 20
    ranking_x, ranking_y = b1a.tap_seed(field, (110.0, 110.0))
    assert ranking_x[0] == 12
    assert ranking_y[0] == 12


def test_seam_energy_prefers_the_block_count():
    # A 12-square column pattern of 20 px squares (240 px wide), constant down the image,
    # with L = 60, b = 0 and these a values per square (4 blocks of 3 squares, 4 x 3 in
    # quilter units, block seams strong):
    #   a = -35 -25 -35 | 35 25 35 | -25 -15 -25 | 35 25 35
    # Steps at seams k = 1..11 (x = 20k): 10 10 70 10 10 60 10 10 60 10 10.
    # Mean seam step for a count N samples x = 240 j / N, j = 1..N-1 (candidates start at
    # b1a.MIN_COUNT = 4):
    #   N = 4: k = 3, 6, 9 -> (70 + 60 + 60) / 3 = 63.33
    #   N = 8: x = 30, 60, ..., 210 -> k = 3, 6, 9 plus four flat centres -> 190 / 7 = 27.14
    #   N = 12: every seam -> (8 x 10 + 70 + 60 + 60) / 11 = 270 / 11 = 24.55
    #   N = 6: k = 2, 4, 6, 8, 10 -> (4 x 10 + 60) / 5 = 20
    #   N = 16: x = 60, 120, 180 on seams, 12 samples at 5 px or more from any seam
    #     -> about 190 / 15 = 12.7; N = 24: every seam plus 12 flat centres -> 270 / 23 = 11.7;
    #     every other N lands nearly all its samples 3 px or more from a seam.
    # The same blur scales every isolated step alike, so the order holds: the scorer ranks
    # the block count 4 first, a harmonic of the true 12 (12 % 4 == 0), as exp9 did on image0.
    a_values = [-35, -25, -35, 35, 25, 35, -25, -15, -25, 35, 25, 35]
    lab = np.empty((240, 240, 3), np.float32)
    lab[..., 0] = 60.0
    lab[..., 2] = 0.0
    lab[..., 1] = np.repeat(np.array(a_values, np.float32), 20)[None, :]
    field = b1a.FieldImage.from_bgr(_lab_to_bgr(lab), FULL_FIELD)
    ranking_x, _ = b1a.seam_energy(field)
    assert ranking_x[:4] == [4, 8, 12, 6]
    # 12 is third, after 4 and 8: a top-1 miss, a top-3 hit, and a harmonic top-1.
    assert b1a.score_ranking(ranking_x, 12) == b1a.Outcome(False, True, True)


def test_fit_2d_prefers_the_true_pair_on_checkerboard():
    # The whole-field fit of a pair, on the 12 x 12 checkerboard. At (12, 12) every seam
    # sample is a step, every centre is flat, and every half-shifted square straddles a step
    # while every aligned square is flat. (24, 24) puts half its seams on flat fabric; (6, 6)
    # puts its centres on steps (edge ratio about 1); (4, 4) ties 12's edge ratio but its
    # aligned squares hold steps (chroma gain about 1). So (12, 12) fits best.
    field = b1a.FieldImage.from_bgr(_checkerboard(), FULL_FIELD)
    true_fit = b1a.fit_2d(field, 12, 12)["fit"]
    for wrong in ((24, 24), (6, 6), (4, 4)):
        assert b1a.fit_2d(field, *wrong)["fit"] < true_fit


# --- Quilter-unit periods, the dev split and the run header ------------------------------


def _stripes(n: int = 12, pitch: int = 20) -> np.ndarray:
    # Three fabrics on diagonal stripes: square (row, col) takes fabric (row + col) mod 3. The
    # fabrics sit at least 40 units apart on a or b, so k-means with k = 3 gives each fabric
    # its own label.
    fabrics = np.array([(40.0, 40.0, 0.0), (60.0, -40.0, 20.0), (80.0, 0.0, -40.0)], np.float32)
    rows, cols = np.mgrid[0:n * pitch, 0:n * pitch] // pitch
    return _lab_to_bgr(fabrics[(rows + cols) % 3])


def test_block_periods_on_diagonal_stripes():
    # The k-means labels relabel the fabrics, so two squares share a label exactly when they
    # share a fabric. Shifting the 12 x 12 label grid by s rows (or columns) compares fabric
    # (r + c) mod 3 with (r + c + s) mod 3: a match on every square when s mod 3 == 0, on none
    # for s = 1 or 2. _axis_period tries s = 1, 2, 3 and stops at 3, a full match (1.0 >=
    # 0.999). So the block period is 3 squares each way, and quilter_units(12, 3) gives
    # gcd(3, 12) = 3 squares per block and 12 / 3 = 4 blocks.
    field = b1a.FieldImage.from_bgr(_stripes(), FULL_FIELD)
    assert b1a.block_periods(field, 12, 12) == (3, 3)
    assert b1a.quilter_units(12, 3) == (4, 3)


def test_spike_needs_no_module_b6b_deletes(monkeypatch):
    # B6b deletes the qrep.vision package (plan B6b: grid.py, repeats.py, __init__.py and the
    # rest). A None entry in sys.modules makes any import of that name raise ImportError, so
    # with every qrep.vision module blocked the script must still load, and the code that once
    # called grid and repeats (autocorr, the tap and block_periods) must still run.
    blocked = ["qrep.vision", "qrep.vision.grid", "qrep.vision.repeats"]
    blocked += [name for name in sys.modules if name.startswith("qrep.vision.")]
    for name in blocked:
        monkeypatch.setitem(sys.modules, name, None)
    spec = importlib.util.spec_from_file_location("b1a_isolated", b1a.__file__)
    isolated = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "b1a_isolated", isolated)
    spec.loader.exec_module(isolated)
    # The expectations of the checkerboard and stripe tests: 240 / 20 = 12 squares each way,
    # and a block period of 3 squares on the stripes.
    board = isolated.FieldImage.from_bgr(_checkerboard(), FULL_FIELD)
    assert isolated.autocorr_period(board)[0][0] == 12
    assert isolated.tap_seed(board, (110.0, 110.0))[1][0] == 12
    stripes = isolated.FieldImage.from_bgr(_stripes(), FULL_FIELD)
    assert isolated.block_periods(stripes, 12, 12) == (3, 3)


def test_load_photos_reads_the_dev_split_only(tmp_path, monkeypatch):
    # A temporary corpus with five manifest rows, in this order:
    # 1. lacma-54871, tier A, eval_set v0, with its committed annotation. Its sha256 starts
    #    89f771d8. 16 = 1 mod 3, so a hex number mod 3 is its digit sum mod 3:
    #    8 + 9 + 15 + 7 + 7 + 1 + 13 + 8 = 68, and 68 mod 3 = 2: outside the holdout
    #    (corpus/README.md: the first 8 hex digits, read as an integer, divisible by 3).
    # 2. held, tier A, v0, sha256 starting 00000003: 3 mod 3 = 0, in the holdout.
    # 3. bare, tier A, v0, sha256 starting 00000001: 1 mod 3 = 1, outside, no annotation.
    # 4. tier-b, tier B, eval_set empty, and 5. tier-c, tier C, v0: outside the dev split.
    # Rows 2, 4 and 5 get annotation files that are not JSON, so reading one would raise.
    sha = "89f771d81045dcfb801d0f22e1de8855f2a76a73d47967a572b93be469b179db"
    other = "00000001" + "0" * 56
    rows = [
        ("images/lacma-54871.jpg", "A", sha, "v0"),
        ("images/held.jpg", "A", "00000003" + "0" * 56, "v0"),
        ("images/bare.jpg", "A", other, "v0"),
        ("images/tier-b.jpg", "B", other, ""),
        ("images/tier-c.jpg", "C", other, "v0"),
    ]
    (tmp_path / "manifest.csv").write_text(
        "file,tier,sha256,eval_set\n" + "".join(",".join(row) + "\n" for row in rows),
        encoding="utf-8")
    (tmp_path / "annotations").mkdir()
    shutil.copy(b1a.REPO / "corpus" / "annotations" / "lacma-54871.json", tmp_path / "annotations")
    for stem in ("held", "tier-b", "tier-c"):
        (tmp_path / "annotations" / f"{stem}.json").write_text("not json", encoding="utf-8")
    monkeypatch.setattr(b1a, "CORPUS", tmp_path)
    photos, skipped = b1a.load_photos()
    # Only row 1 is read. corpus/annotations/lacma-54871.json gives both proposal passes 10
    # blocks of 5 squares each way, and proposed-a these field and outer-edge corners
    # (top left, top right, bottom right, bottom left).
    assert [(p.stem, p.tier, sorted(p.truth)) for p in photos] == [
        ("lacma-54871", "A", ["proposed-a", "proposed-b"])]
    truth = photos[0].truth["proposed-a"]
    assert truth["counts"] == (10, 5, 10, 5)
    assert truth["field"].tolist() == [[221, 336], [3606, 334], [3659, 3804], [264, 3732]]
    assert truth["outer"].tolist() == [[16, 144], [3795, 138], [3847, 4009], [84, 3905]]
    # The holdout row is counted without its name; the bare row has no claims to read.
    assert skipped == [{"stem": None, "tier": "A", "reason": "holdout"},
                       {"stem": "bare", "tier": "A", "reason": "no frame and counts claims"}]


def test_qrep_path_names_the_checkout():
    # A qrep inside the checkout prints as <checkout folder>/qrep/__init__.py: the folder's
    # name tells which tree ran, and no folder above it is printed.
    inside = b1a.REPO / "qrep" / "__init__.py"
    assert b1a._qrep_path(str(inside)) == f"{b1a.REPO.name}/qrep/__init__.py"
    # A qrep outside the checkout prints its file name only.
    outside = b1a.REPO.parent / "elsewhere" / "qrep" / "__init__.py"
    assert b1a._qrep_path(str(outside)) == "<outside this checkout>/__init__.py"
