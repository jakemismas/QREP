"""B1a spike: the scoring helpers and the count methods on synthetic grids.

Every expected value is worked by hand in the comments beside its assertion, from the issue's
own example (#134), the Wilson formula, or the construction of the synthetic image; none comes
from running the spike. The synthetic images are built in Lab and converted to BGR, so a
designed step in the a channel reaches the methods as the same step (to rounding: one uint8
level moves a by well under 1 unit).
"""

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


def test_joint_outcomes():
    # Truth (50, 50). Top-1 (10, 10): wrong, and 50 % 10 == 0 on both axes, so harmonic.
    assert b1a.score_ranking([(10, 10), (50, 50)], (50, 50)) == b1a.Outcome(False, True, True)
    # Top-1 (25, 50): x is harmonic (50 % 25 == 0) and y is right, so harmonic.
    assert b1a.score_ranking([(25, 50)], (50, 50)) == b1a.Outcome(False, False, True)
    # Top-1 (50, 49): y is a near miss (50 % 49 == 1), so the pair is not harmonic.
    assert b1a.score_ranking([(50, 49)], (50, 50)) == b1a.Outcome(False, False, False)


# --- Quilter units and harmonic alternates -----------------------------------------------


def test_quilter_units():
    # 40 squares with a block period of 5: 40 / 5 = 8 blocks of 5 squares.
    assert b1a.quilter_units(40, 5) == (8, 5)
    # 40 % 3 == 1: a period that does not divide the count gives one block of 40.
    assert b1a.quilter_units(40, 3) == (1, 40)
    # No period found (0), or a period equal to the count: one block of 40.
    assert b1a.quilter_units(40, 0) == (1, 40)
    assert b1a.quilter_units(40, 40) == (1, 40)


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
    #        = 0.735826.
    # half = z * sqrt(p(1-p)/n + z^2/(4n^2)) / denom
    #      = 1.96 * sqrt(0.148760/11 + 3.8416/484) / 1.349236
    #      = 1.96 * sqrt(0.013524 + 0.007937) / 1.349236 = 1.96 * 0.146495 / 1.349236 = 0.212813.
    # Interval: 0.735826 -/+ 0.212813 = [0.523013, 0.948639].
    lo, hi = b1a.wilson(9, 11)
    assert lo == pytest.approx(0.523013, abs=1e-5)
    assert hi == pytest.approx(0.948639, abs=1e-5)
    # n = 0 has no information: the whole unit interval.
    assert b1a.wilson(0, 0) == (0.0, 1.0)


def test_decision_rule():
    # Issue #134 criterion 6: ship when top-3 recall >= 0.8 and the fit score rejects every
    # wrong top-1: every wrong top-1's fit sits below the lowest true-count fit.
    # 0.82 >= 0.8, and max wrong 1.3 < min truth 1.5: go.
    assert b1a.decide(0.82, wrong_fits=[1.1, 1.3], truth_fits=[1.5, 2.0])
    # A wrong top-1 at 1.6 is not below the truth's 1.5: the fit would pass it unnoticed.
    assert not b1a.decide(0.82, wrong_fits=[1.6], truth_fits=[1.5])
    # 0.79 is under the bar whatever the fit says.
    assert not b1a.decide(0.79, wrong_fits=[], truth_fits=[1.5])
    # The bar is inclusive, and no wrong top-1 leaves nothing to reject.
    assert b1a.decide(0.8, wrong_fits=[], truth_fits=[1.5])


# --- Geometry ----------------------------------------------------------------------------


def test_jitter_moves_each_corner_by_the_radius():
    # Each corner moves r * (cos t, sin t), whose length is r * sqrt(cos^2 t + sin^2 t) = r.
    corners = np.array([[0.0, 0.0], [300.0, 0.0], [300.0, 400.0], [0.0, 400.0]])
    moved = b1a.jitter_corners(corners, 4.0, np.random.default_rng(7))
    assert np.linalg.norm(moved - corners, axis=1) == pytest.approx([4.0] * 4, abs=1e-9)
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


@pytest.mark.parametrize("method", ["autocorr", "fit"])
def test_checkerboard_methods_find_twelve(method):
    # A 12 x 12 checkerboard of 20 px squares fills the 240 x 240 field. Every one of the 11
    # interior seams on each axis is the same step, and nothing else changes inside a square.
    # Autocorrelation: the binarized edge profile spikes every 20 px, so its smallest strong
    # lag is 20 and the count is 240 / 20 = 12.
    # Fit: at 12 every seam sample lands on a step and every centre sample on flat fabric,
    # and every half-pitch-shifted square straddles a step while every aligned square is
    # flat. A divisor (6) puts its centres on steps (edge gain about 1); a multiple (24) puts
    # half its seams on flat fabric (lower seam mean); any other count misses most steps.
    # So both rank 12 first on both axes.
    field = b1a.FieldImage.from_bgr(_checkerboard(), FULL_FIELD)
    ranking_x, ranking_y = b1a.METHODS[method](field)
    assert ranking_x[0] == 12
    assert ranking_y[0] == 12


def test_tap_seed_on_checkerboard_finds_twelve():
    # A tap at the centre of square (5, 5), (110, 110), with no jitter. The local window
    # (half-size 0.15 x 240 = 36 px, so x and y in [74, 146]) holds the steps at 80, 100,
    # 120 and 140. The nearest steps around the tap are 100 and 120: a 20 px square. The
    # window's autocorrelation peaks at 20 and 40; the smallest strong lag no wider than
    # 1.3 x 20 = 26 px is 20, so the pitch is 20 px and the count is 240 / 20 = 12.
    field = b1a.FieldImage.from_bgr(_checkerboard(), FULL_FIELD)
    ranking_x, ranking_y = b1a.tap_seed(field, (110.0, 110.0))
    assert ranking_x[0] == 12
    assert ranking_y[0] == 12


def test_seam_energy_prefers_the_block_count():
    # A 12-square column pattern of 20 px squares (240 px wide), constant down the image,
    # with L = 60, b = 0 and these a values per square (3 x 3 blocks, block seams strong):
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
