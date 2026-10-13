"""The confirmed read's fabrics (ticket B2b): clustering in L-weighted float
CIELAB, the fabric count by silhouette, one shading correction shared by
every fabric, and each square's label and confidence.

Formulas used throughout, from the ticket:
  distance   d = sqrt((w dL)^2 + da^2 + db^2), w the L weight
  silhouette s = (b - a) / max(a, b) per point, a its weighted mean distance
             to the other members of its fabric, b the smallest weighted
             mean distance to another fabric; s = 0 for a point alone in its
             fabric; the read's silhouette is the weighted mean of s
  confidence (d2 - d1) / d2 over a sample's two nearest fabric colors among
             the fabrics that hold samples; 0 when fewer than two do
  lightness  L* = 116 Y^(1/3) - 16 for luminance Y > 0.008856
A fabric that holds no sample leaves the silhouette undefined.
The light is one fit over every sample at once; with fewer than 18 samples
(SHADING_MIN_SQUARES) the read fits none, so the corrected points are the
samples.
"""

import ast
import math
from pathlib import Path

import numpy as np
import pytest

import qrep.vision.read.fabrics as fabrics_module
from qrep.contract import BorderBand, Corners, Counts, FieldFrame, OuterEdgeFrame, Point
from qrep.vision.read.fabrics import (
    Fabrics,
    Refusal,
    _samples,
    _subset,
    cluster,
    read_fabrics,
)
from qrep.vision.read.geometry import confirm
from qrep.vision.read.sample import P, Squares, StripSample, read_squares

GOLDEN = 0.6180339887498949


def corners(tl, tr, br, bl) -> Corners:
    return Corners(
        top_left=Point(x=tl[0], y=tl[1]),
        top_right=Point(x=tr[0], y=tr[1]),
        bottom_right=Point(x=br[0], y=br[1]),
        bottom_left=Point(x=bl[0], y=bl[1]),
    )


def counts(cols, rows) -> Counts:
    return Counts(
        blocks_across=1, blocks_down=1, squares_per_block_across=cols, squares_per_block_down=rows
    )


def rect_field(x0, y0, x1, y1) -> FieldFrame:
    return FieldFrame(kind="field", corners=corners((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


def outer_frame(width, height, *bands) -> OuterEdgeFrame:
    return OuterEdgeFrame(
        kind="outer_edge",
        corners=corners((0, 0), (width, 0), (width, height), (0, height)),
        bands=[BorderBand(width_squares=w) for w in bands],
    )


def squares_of(lab, geometry=None, strips=()) -> Squares:
    """A Squares built straight from hand-set samples, so the expected
    colors are exact and no image or cv2 is involved."""
    lab = np.asarray(lab, dtype=float)
    rows, cols = lab.shape[:2]
    if geometry is None:
        size = (cols * P, rows * P)
        geometry = confirm(
            rect_field(0, 0, *size),
            counts(cols, rows),
            size,
            Point(x=0, y=0),
            corners_source="user",
        )
    return Squares(
        geometry=geometry,
        lab=lab,
        spread=np.zeros_like(lab),
        strips=tuple(strips),
        field_bgr=np.zeros((rows * P, cols * P, 3), dtype=np.uint8),
        downsample=np.ones((rows, cols, 2), dtype=int),
    )


def in_a_row(n):
    """n positions across the middle of the field, all inside it."""
    return np.stack([(np.arange(n) + 0.5) / n, np.full(n, 0.5)], axis=1)


def same_partition(labels, groups):
    """True when labels put each group in one fabric and no two groups in
    the same one; k-means numbers its fabrics in no fixed order."""
    names = [set(labels[list(group)].tolist()) for group in groups]
    return all(len(n) == 1 for n in names) and len(set().union(*names)) == len(groups)


# Three fabrics, F0 to F2, darkest first, on a 12 x 12 grid at (r + c) mod 3,
# each with a small deterministic jitter on a* only: square i (raster order)
# adds 2 (frac((i + 1) x 0.618...) - 0.5), spread evenly over [-1, 1).
THREE = np.array([(30.0, 0.0, 0.0), (50.0, 40.0, 20.0), (70.0, -20.0, 50.0)])


def three_fabrics():
    rows = cols = 12
    r, c = np.divmod(np.arange(rows * cols), cols)
    truth = (r + c) % 3
    lab = THREE[truth].copy()
    lab[:, 1] += 2 * ((np.arange(rows * cols) + 1) * GOLDEN % 1.0 - 0.5)
    return lab.reshape(rows, cols, 3), truth.reshape(rows, cols)


def test_the_silhouette_follows_the_hand_computation():
    # Source: the ticket's silhouette rule, on four points along a* only.
    # Inputs: a* = 0, 1, 10, 12 with weights 1, 1, 2, 1; L* = 50, b* = 0 for
    #   all, so the L weight cancels; k = 2. Fabrics {0, 1} and {10, 12} by
    #   construction (any other split costs more: {0}, {1, 10, 12} has a
    #   weighted inertia over 40 against 0.5 + 2.7).
    # Formula: a = sum w_j d_ij / sum w_j over the other members; b the same
    #   over the other fabric.
    # Arithmetic:
    #   0:  a = 1;  b = (2 x 10 + 12) / 3 = 32/3;  s = (29/3) / (32/3) = 29/32
    #   1:  a = 1;  b = (2 x 9 + 11) / 3 = 29/3;   s = 26/29
    #   10: a = 2;  b = (10 + 9) / 2 = 9.5;        s = 7.5 / 9.5 = 15/19
    #   12: a = (2 x 2) / 2 = 2; b = (12 + 11) / 2 = 11.5; s = 9.5 / 11.5 = 19/23
    #   mean = (29/32 + 26/29 + 2 x 15/19 + 19/23) / 5
    #        = (0.906250 + 0.896552 + 1.578947 + 0.826087) / 5 = 0.841567
    #   fabric {0, 1}: (0.906250 + 0.896552) / 2 = 0.901401
    #   fabric {10, 12}: (1.578947 + 0.826087) / 3 = 0.801678
    # Expected: silhouette 0.841567; center confidences 0.901401 and 0.801678.
    lab = np.array([(50, 0, 0), (50, 1, 0), (50, 10, 0), (50, 12, 0)], dtype=float)
    result = cluster(lab, [1, 1, 2, 1], in_a_row(4), 2)
    assert same_partition(result.labels, [(0, 1), (2, 3)])
    assert result.silhouette == pytest.approx(0.841567, abs=1e-6)
    assert result.center_confidence[result.labels[0]] == pytest.approx(0.901401, abs=1e-6)
    assert result.center_confidence[result.labels[2]] == pytest.approx(0.801678, abs=1e-6)


def test_a_point_alone_in_its_fabric_scores_zero():
    # Source: the ticket's silhouette rule, s = 0 for a point alone.
    # Inputs: a* = 0, 1, 10, weights 1, L* = 50; k = 2, fabrics {0, 1} and
    #   {10} (inertia 0.5 against 40.5 for {0}, {1, 10}).
    # Arithmetic: 0: a = 1, b = 10, s = 0.9; 1: a = 1, b = 9, s = 8/9 =
    #   0.888889; 10: alone, s = 0. Three points over two fabrics, so the mean
    #   is defined: (0.9 + 0.888889 + 0) / 3 = 0.596296. Fabric {0, 1}:
    #   (0.9 + 0.888889) / 2 = 0.894444; fabric {10}: 0.
    # Expected: silhouette 0.596296; center confidences 0.894444 and 0.0.
    lab = np.array([(50, 0, 0), (50, 1, 0), (50, 10, 0)], dtype=float)
    result = cluster(lab, [1, 1, 1], in_a_row(3), 2)
    assert same_partition(result.labels, [(0, 1), (2,)])
    assert result.silhouette == pytest.approx(0.596296, abs=1e-6)
    assert result.center_confidence[result.labels[0]] == pytest.approx(0.894444, abs=1e-6)
    assert result.center_confidence[result.labels[2]] == 0.0


def test_the_silhouette_is_undefined_with_no_more_points_than_fabrics():
    # Source: the ticket: undefined when the sampled points number at most
    # the fabrics present. Inputs: two points, k = 2, one per fabric.
    # Expected: silhouette None, every center confidence 0.0.
    lab = np.array([(50, 0, 0), (50, 10, 0)], dtype=float)
    result = cluster(lab, [1, 1], in_a_row(2), 2)
    assert result.silhouette is None
    assert result.center_confidence.tolist() == [0.0, 0.0]


def test_three_separated_fabrics_read_as_three_darkest_first():
    # Source: plan B2b criterion 1 (k by silhouette over 2..12).
    # Inputs: THREE above; scaled by w = 0.5 on L: F0 (15, 0, 0),
    #   F1 (25, 40, 20), F2 (35, -20, 50).
    # Arithmetic: distances d01 = sqrt(100 + 1600 + 400) = 45.83,
    #   d02 = sqrt(400 + 400 + 2500) = 57.45, d12 = sqrt(100 + 3600 + 900) =
    #   67.82. The jitter spans 2 in a* (mean gap within a fabric 2/3).
    #   k = 3: a <= 2, b >= 45.83 - 2, so s >= 1 - 2/43.83 = 0.954 everywhere.
    #   k = 2 merges the closest pair, F0 and F1: their points have a near
    #   45.83 x 48/95 = 23.2 and b near 57.45 (F0) or 67.82 (F1), so s near
    #   0.60 and 0.66, and F2 near 1: mean near (0.60 + 0.66 + 1) / 3 = 0.75.
    #   k = 4 splits one fabric's even spread of width 2 in halves; for a
    #   point at t in [0, 1/2] of a unit spread a = t^2 + (1/2 - t)^2 and
    #   b = 3/4 - t, so s = 1 - a/b runs 0.67, 0.74, 0.76, 0.71, 0.51, 0 at
    #   t = 0, 0.1 .. 0.5, mean near 0.61; with the two whole fabrics near
    #   0.98, the mean is near (2 x 0.98 + 0.61) / 3 = 0.86. More fabrics
    #   split more and score lower still.
    # Expected: k = 3, and darkest first the labels are the construction's
    #   (r + c) mod 3; L* and b* do not vary within a fabric, so each center
    #   carries its fabric's L* and b* exactly.
    lab, truth = three_fabrics()
    result = read_fabrics(squares_of(lab))
    assert isinstance(result, Fabrics)
    assert result.k == 3
    assert result.k_source == "suggestion"
    assert np.array_equal(result.labels, truth)
    assert result.strip_labels == ()
    assert result.centers[:, 0] == pytest.approx(THREE[:, 0], abs=1e-9)
    assert result.centers[:, 2] == pytest.approx(THREE[:, 2], abs=1e-9)


@pytest.mark.parametrize("k", [1, 0, -3, 2.5, 2.0, True, False, "3"])
def test_a_requested_count_outside_the_whole_numbers_2_to_12_is_refused(k):
    # Source: plan B2b criterion 1: a requested k is an integer from 2 to 12.
    # Expected: 1, 0 and -3 lie below 2; 2.5, 2.0 and "3" are not integers;
    # True and False are bools, not counts: bad_fabric_count for each.
    lab, _ = three_fabrics()
    result = read_fabrics(squares_of(lab), k)
    assert isinstance(result, Refusal)
    assert result.code == "bad_fabric_count"


def test_a_requested_count_over_12_is_too_many_fabrics():
    # Source: plan B2b criterion 2: a request for more than 12 fabrics.
    # Expected: 13 gives too_many_fabrics.
    lab, _ = three_fabrics()
    result = read_fabrics(squares_of(lab), 13)
    assert isinstance(result, Refusal)
    assert result.code == "too_many_fabrics"


@pytest.mark.parametrize("k", [2, 12, np.int64(5)])
def test_a_requested_count_from_2_to_12_is_kept(k):
    # Source: plan B2b criterion 1. Expected: k is kept as the user's, at
    # confidence 1.0; the three fabrics give 2 or 12 fabrics as asked (at 12
    # the jitter spreads split into the surplus).
    lab, _ = three_fabrics()
    result = read_fabrics(squares_of(lab), k)
    assert isinstance(result, Fabrics)
    assert result.k == int(k)
    assert result.k_source == "user"
    assert result.k_confidence == 1.0
    assert result.centers.shape == (int(k), 3)
    assert result.labels.min() >= 0 and result.labels.max() < int(k)


def test_more_fabrics_than_the_cap_refuse_as_too_many_fabrics():
    # Source: criterion 2 of #137 (never merge fabrics silently); the
    #   margin rule in fabrics.suggest.
    # Inputs: 13 colors at L* 50 (the L weight cancels): 12 on a lattice,
    #   a* in {-60, -20, 20, 60} by b* in {-40, 0, 40}, 40 apart, and a 13th
    #   at (64, 40), 4 from lattice color (60, 40). An 8 x 13 grid at
    #   (r + c) mod 13 holds each color 8 times. Every square is exact and
    #   the light flat, so the shared light fits at 1 and moves no distance.
    # Arithmetic at k = 12: merging the close pair costs inertia
    #   2 x 8 x 2^2 = 64, any other merge at least 2 x 8 x 20^2 = 6400, so
    #   the pair shares a fabric and each lattice color has its own. Lone
    #   colors: a = 0, b > 0, s = 1 (11 x 8 points). The pair: a = 4 x 8 / 15
    #   = 2.133333; (60, 40) has b = 40 (lattice neighbors (20, 40) and
    #   (60, 0)), s = 1 - 2.133333/40 = 0.946667; (64, 40) has b =
    #   sqrt(4^2 + 40^2) = 40.199502, s = 0.946931. Mean = (88 + 8 x 0.946667
    #   + 8 x 0.946931) / 104 = 0.991815.
    # At k = 11 two lattice colors 40 apart also share a fabric: a = 40 x 8 /
    #   15 = 21.33 and b <= 40.1 (a perpendicular neighbor), so s <= 0.468,
    #   and the mean is at most (9 x 8 + 16 x 1 + 16 x 0.468) / 104 = 0.918.
    #   Fewer fabrics merge more far colors and score lower still.
    # Expected: the best silhouette is the one at 12, within any margin of
    #   itself, so the read refuses with too_many_fabrics instead of merging
    #   two fabrics silently.
    lattice = [(50.0, a, b) for b in (-40, 0, 40) for a in (-60, -20, 20, 60)]
    colors = np.array(lattice + [(50.0, 64.0, 40.0)])
    rows, cols = 8, 13
    r, c = np.divmod(np.arange(rows * cols), cols)
    index = (r + c) % 13
    lab = colors[index].reshape(rows, cols, 3)

    positions = np.stack([(c + 0.5) / cols, (r + 0.5) / rows], axis=1)
    at_12 = cluster(lab.reshape(-1, 3), np.ones(rows * cols), positions, 12)
    assert same_partition(at_12.labels, [np.flatnonzero(index == i) for i in range(11)])
    assert set(at_12.labels[index == 11]) == set(at_12.labels[index == 12])
    assert at_12.silhouette == pytest.approx(0.991815, abs=1e-6)

    result = read_fabrics(squares_of(lab))
    assert isinstance(result, Refusal)
    assert result.code == "too_many_fabrics"


def test_an_undefined_silhouette_gives_palette_confidence_zero():
    # Source: plan B2b criterion 1: an undefined silhouette sets the palette
    # confidence to 0, never 1.
    # Inputs: a 4 x 4 grid of one color, (50, 10, 10).
    # Arithmetic: one distinct color, under K_MIN = 2, so no count is tried
    #   and the read takes K_MIN = 2, the least count criterion 1 allows: the
    #   second fabric repeats the first and stays empty (distance ties go to
    #   the lower index), so one fabric holds samples, the silhouette is
    #   undefined, every center confidence is 0.0, and with no second held
    #   fabric to tell a square from, each square's confidence is 0.0. A
    #   request for k = 2 reads the same, at k confidence 1.0.
    # Expected: suggested: k 2, palette and k confidence 0.0, both centers
    #   (50, 10, 10), every label 0, confidence 0.0. Requested: k 2 at
    #   confidence 1.0, palette confidence 0.0, every label 0, confidence 0.0.
    lab = np.tile(np.array([50.0, 10.0, 10.0]), (4, 4, 1))
    suggested = read_fabrics(squares_of(lab))
    assert suggested.k == 2
    assert suggested.palette_confidence == 0.0
    assert suggested.k_confidence == 0.0
    assert suggested.center_confidence.tolist() == [0.0, 0.0]
    assert suggested.centers.tolist() == [[50.0, 10.0, 10.0]] * 2
    assert np.all(suggested.labels == 0)
    assert np.all(suggested.confidence == 0.0)

    requested = read_fabrics(squares_of(lab), 2)
    assert requested.k == 2
    assert requested.k_confidence == 1.0
    assert requested.palette_confidence == 0.0
    assert np.all(requested.labels == 0)
    assert np.all(requested.confidence == 0.0)


def test_assignment_confidence_is_the_margin_over_the_second_center():
    # Source: plan B2b criterion 4: confidence (d2 - d1) / d2.
    # Inputs: A (20, 0, 0) weight 10, p (30, 12, 0) and m (10, -12, 0) weight
    #   1 each, B (62, 0, 0) weight 10; k = 2. A, p and m share a fabric
    #   (inertia 2 x 169 = 338 at w = 0.5; moving p or m to B costs more), and
    #   its weighted mean is ((200 + 30 + 10) / 12, (12 - 12) / 12, 0) =
    #   (20, 0, 0): the centers are A and B exactly. With 4 samples, under
    #   the 18 the light needs, the read fits none, so nothing changes.
    # Arithmetic, w = 0.5 (scaled L: A 10, B 31, p 15, m 5):
    #   p: d1 = sqrt(5^2 + 12^2) = 13, d2 = sqrt(16^2 + 12^2) = 20; 7/20 = 0.35
    #   m: d1 = 13, d2 = sqrt(26^2 + 12^2) = sqrt(820) = 28.635642;
    #      15.635642 / 28.635642 = 0.546020
    #   A, B: d1 = 0, d2 = 21; 1.0
    # w = 1.0 (L unscaled: A 20, B 62, p 30, m 10):
    #   p: d1 = sqrt(10^2 + 12^2) = 15.620499, d2 = sqrt(32^2 + 12^2) =
    #      34.176015; 18.555516 / 34.176015 = 0.542940
    #   m: d1 = 15.620499, d2 = sqrt(52^2 + 12^2) = 53.366656;
    #      37.746157 / 53.366656 = 0.707299
    # Expected: [1.0, 0.35, 0.546020, 1.0] at w = 0.5 and
    #   [1.0, 0.542940, 0.707299, 1.0] at w = 1.0.
    lab = np.array([(20, 0, 0), (30, 12, 0), (10, -12, 0), (62, 0, 0)], dtype=float)
    weights = [10, 1, 1, 10]
    half = cluster(lab, weights, in_a_row(4), 2, l_weight=0.5)
    assert same_partition(half.labels, [(0, 1, 2), (3,)])
    assert sorted(half.centers.tolist()) == [[20.0, 0.0, 0.0], [62.0, 0.0, 0.0]]
    assert half.confidence == pytest.approx([1.0, 0.35, 0.546020, 1.0], abs=1e-6)
    full = cluster(lab, weights, in_a_row(4), 2, l_weight=1.0)
    assert same_partition(full.labels, [(0, 1, 2), (3,)])
    assert full.confidence == pytest.approx([1.0, 0.542940, 0.707299, 1.0], abs=1e-6)


def test_one_fabric_has_no_margin_and_an_empty_fabric_takes_no_part():
    # Source: the ticket's seeding, k-means and confidence rules.
    # Inputs: L* 20 three times, then L* 60 three times, a* = b* = 0,
    #   weights 1.
    # Arithmetic, k = 3, seeding 0: u0 = frac(0.618034) = 0.618034; the
    #   weights' CDF is 1..6 of 6, and 0.618034 x 6 = 3.708 falls in sample
    #   3's run (3 to 4): L* 60. Then weight x D^2 at w = 0.5 is 20^2 = 400
    #   for each L* 20 sample, 0 for the rest; u1 = frac(1.236068) = 0.236068
    #   and 0.236068 x 1200 = 283.3 falls in sample 0's run (0 to 400): L* 20.
    #   Every D^2 is now 0, so the third center repeats L* 20. Lloyd: L* 60
    #   goes to center 0, L* 20 ties centers 1 and 2 and takes the lower, 1;
    #   the means do not move. Inertia 0, which no later seeding beats.
    #   Confidence among the fabrics that hold samples, 0 and 1 (center 2 is
    #   empty): an L* 20 sample has d1 = 0 and d2 = 0.5 x 40 = 20, so 1.0, and
    #   an L* 60 sample likewise. Fabric 2 holds no sample, so the silhouette
    #   is undefined; fabrics 0 and 1 each have a = 0 and b = 20 at every
    #   point, s = 1, so their center confidence is 1.0, and fabric 2's is 0.
    #   k = 1: one fabric, no second to tell a square from, confidence 0.0,
    #   center the mean (40, 0, 0), and the silhouette undefined.
    # Expected: as above.
    lab = np.array([(20, 0, 0)] * 3 + [(60, 0, 0)] * 3, dtype=float)
    three = cluster(lab, np.ones(6), in_a_row(6), 3)
    assert three.labels.tolist() == [1, 1, 1, 0, 0, 0]
    assert three.centers.tolist() == [[60.0, 0.0, 0.0], [20.0, 0.0, 0.0], [20.0, 0.0, 0.0]]
    assert three.confidence.tolist() == [1.0] * 6
    assert three.silhouette is None
    assert three.center_confidence.tolist() == [1.0, 1.0, 0.0]
    one = cluster(lab, np.ones(6), in_a_row(6), 1)
    assert one.labels.tolist() == [0] * 6
    assert one.confidence.tolist() == [0.0] * 6
    assert one.centers.tolist() == [[40.0, 0.0, 0.0]]
    assert one.silhouette is None


def test_an_empty_fabric_leaves_the_silhouette_undefined_and_the_margins_clean():
    # Source: the ticket: an undefined silhouette gives the palette confidence
    #   0, never 1; each margin counts only the fabrics that hold samples.
    # Inputs: a 4 x 4 checkerboard of two flat colors, F0 (30, 0, 0) where
    #   r + c is even and F1 (70, 0, 0) where it is odd; a requested k = 3.
    # Arithmetic: two distinct colors for three fabrics, so seeding repeats a
    #   chosen center and one fabric stays empty (distance ties go to the
    #   lower index); with it the silhouette is undefined, palette confidence
    #   0.0, and the empty fabric's center confidence 0.0. Each square sits on
    #   its own fabric, d1 = 0, and the other held fabric is 0.5 x 40 = 20
    #   away, so (20 - 0) / 20 = 1.0; the empty twin, also at 0, is not
    #   counted. The held fabrics have a = 0, b = 20, s = 1: 1.0 each.
    # Expected: k 3, palette confidence 0.0, one empty fabric at center
    #   confidence 0.0, the others at 1.0, labels by the checkerboard, every
    #   square's confidence 1.0.
    r, c = np.divmod(np.arange(16), 4)
    truth = (r + c) % 2
    colors = np.array([(30.0, 0.0, 0.0), (70.0, 0.0, 0.0)])
    result = read_fabrics(squares_of(colors[truth].reshape(4, 4, 3)), 3)
    assert isinstance(result, Fabrics)
    assert result.k == 3
    assert result.palette_confidence == 0.0
    empty = sorted(set(range(3)) - set(result.labels.ravel().tolist()))
    assert len(empty) == 1
    held = [i for i in range(3) if i not in empty]
    assert result.center_confidence[empty[0]] == 0.0
    assert result.center_confidence[held] == pytest.approx([1.0, 1.0], abs=1e-12)
    assert same_partition(result.labels.ravel(), [np.flatnonzero(truth == i) for i in (0, 1)])
    assert np.all(result.confidence == 1.0)


def falloff_grid(stripes=False, drop=0.3):
    """Two grays, a* = b* = 0, on a 16 x 16 checkerboard (dark where r + c is
    even), or in column stripes (dark where c is even), lit by a falloff that
    scales luminance by 1 - drop x c / 15: 1.0 at column 0 down to 1 - drop
    at column 15 (1 - 0.02c for the default 30 percent)."""
    rows = cols = 16
    r, c = np.divmod(np.arange(rows * cols), cols)
    truth = c % 2 if stripes else (r + c) % 2
    luminance = np.where(truth == 0, 0.24, 0.30) * (1 - drop * c / 15)
    lab = np.zeros((rows * cols, 3))
    lab[:, 0] = 116 * np.cbrt(luminance) - 16
    return lab.reshape(rows, cols, 3), truth.reshape(rows, cols)


def test_the_shading_correction_reads_a_value_only_falloff_grid():
    # Source: plan B2b criterion 3 (exp7: a,b only fails on value-only
    # fabrics; vision-07: fit the palette and assign on the same correction).
    # Inputs: falloff_grid above; luminance 0.24 (dark) and 0.30 (light),
    #   scaled by f = 1 - 0.02c, a 30 percent falloff across the quilt; both
    #   fabrics appear in every column, so both span the whole falloff.
    # Formula: L* = 116 Y^(1/3) - 16, Y > 0.008856 throughout (Y >= 0.168).
    # Arithmetic: 0.24^(1/3) = 0.621447, 0.30^(1/3) = 0.669433,
    #   0.21^(1/3) = 0.594392, 0.168^(1/3) = 0.551785.
    #   dark  column 0: 116 x 0.621447 - 16 = 56.088; column 15 (Y 0.168): 48.007
    #   light column 0: 116 x 0.669433 - 16 = 61.654; column 15 (Y 0.21): 52.950
    #   The ranges [48.007, 56.088] and [52.950, 61.654] overlap on
    #   [52.950, 56.088]. Without correction, a* = b* = 0 and two centers
    #   split the squares at one L* threshold t: t <= 52.950 leaves the dark
    #   column 0 square (56.088) over it, and t > 52.950 puts the light
    #   column 15 square (52.950) under it, so some square is misread.
    #   With the correction each fabric's L* is 116 Y^(1/3) f^(1/3) - 16, a
    #   smooth curve in x that a quadratic follows within a few hundredths,
    #   while the fabrics stay 116 (0.669433 - 0.621447) f^(1/3) >= 5.566 x
    #   0.7^(1/3) = 4.94 apart in L* (2.47 at w = 0.5) in every column.
    #   At the field center x = 0.5, column 7.5, f = 0.85: dark L* =
    #   116 x 0.204^(1/3) - 16 = 116 x 0.588677 - 16 = 52.287, light L* =
    #   116 x 0.255^(1/3) - 16 = 116 x 0.634133 - 16 = 57.559; the fit's
    #   error there is the quartic term of f^(1/3), under 0.01.
    # Expected: with shading_rounds = 0 at least one square is misread; with
    #   the default correction every square reads its fabric (dark 0, light
    #   1, darkest first) and the centers sit at 52.287 and 57.559.
    lab, truth = falloff_grid()
    plain = read_fabrics(squares_of(lab), 2, shading_rounds=0)
    assert np.any(plain.labels != truth)
    corrected = read_fabrics(squares_of(lab), 2)
    assert np.array_equal(corrected.labels, truth)
    assert corrected.centers[:, 0] == pytest.approx([52.287, 57.559], abs=0.05)


def test_the_shading_correction_reads_stripes_along_the_falloff():
    # Source: PR #251 round 1 (the stripes case on #248): column stripes run
    #   along the falloff, so each fabric holds whole columns.
    # Inputs: falloff_grid(stripes=True): the same two grays and falloff as
    #   the checkerboard test above, dark on even columns, light on odd.
    # Arithmetic: as in the checkerboard test, the L* ranges [48.007, 56.088]
    #   and [52.950, 61.654] overlap, so one threshold misreads a square
    #   (dark column 0 at 56.088, light column 15 at 52.950). Each fabric
    #   still holds a column at every other x, so the one light the fabrics
    #   share is seen across the whole field, and with it the fabrics stay
    #   at least 4.94 apart in L* in every column.
    # Expected: with shading_rounds = 0 at least one square is misread; with
    #   the default correction every square reads its fabric.
    lab, truth = falloff_grid(stripes=True)
    plain = read_fabrics(squares_of(lab), 2, shading_rounds=0)
    assert np.any(plain.labels != truth)
    corrected = read_fabrics(squares_of(lab), 2)
    assert np.array_equal(corrected.labels, truth)


@pytest.mark.parametrize("stripes", [False, True], ids=["checkerboard", "stripes"])
def test_a_65_percent_falloff_keeps_the_uncorrected_read_past_the_cap(stripes):
    # Source: knobs.LIGHT_MAX_RATIO 2.0 and the ruling in #137 comment
    #   6149208104: past the cap the read is the uncorrected read, and an
    #   amplitude cap cannot read this falloff right without misreading value
    #   ramps (#261).
    # Inputs: falloff_grid(stripes, drop 0.65): the same two grays, the
    #   luminance scaled by f = 1 - 0.65c / 15, down to 0.35 at column 15.
    # Formula: L* = 116 Y^(1/3) - 16, Y > 0.008856 throughout (Y >= 0.084).
    # Arithmetic: 0.084^(1/3) = 0.437952, 0.105^(1/3) = 0.471769.
    #   dark  column 0: 56.088 (as above); column 15 (Y 0.084): 116 x
    #     0.437952 - 16 = 34.802
    #   light column 0: 61.654; column 15 (Y 0.105): 116 x 0.471769 - 16 =
    #     38.725
    #   The ranges [34.802, 56.088] and [38.725, 61.654] overlap, so one L*
    #   threshold misreads a square. The light varies 1 / 0.35 = 2.857 in
    #   luminance across the field, over the cap 2.0: a fit that finds it
    #   passes the cap, and the read drops the correction and keeps k-means'
    #   labels and centers, as with shading_rounds 0. (Measured on #248: the
    #   fit passes 2.0 in round 2, at 2.36 on the checkerboard and 2.11 on
    #   the stripes.)
    # Expected: with shading_rounds = 0 at least one square is misread; with
    #   the default correction labels and centers equal that read's.
    lab, truth = falloff_grid(stripes=stripes, drop=0.65)
    plain = read_fabrics(squares_of(lab), 2, shading_rounds=0)
    assert np.any(plain.labels != truth)
    corrected = read_fabrics(squares_of(lab), 2)
    assert np.array_equal(corrected.labels, plain.labels)
    assert np.array_equal(corrected.centers, plain.centers)


def bands_of_rising_lightness(sigma, seed):
    """Four grays, L* 25, 45, 65 and 85 with a* = b* = 0, in 14-row bands of a
    56 x 44 grid under flat light, plus Gaussian noise of sd sigma on every
    channel from numpy's PCG64 generator, which draws the same values on
    every platform."""
    rows, cols = 56, 44
    r, c = np.divmod(np.arange(rows * cols), cols)
    truth = r // 14
    lab = np.zeros((rows * cols, 3))
    lab[:, 0] = 25 + 20 * truth
    lab += np.random.default_rng(seed).normal(0.0, sigma, lab.shape)
    positions = np.stack([(c + 0.5) / cols, (r + 0.5) / rows], axis=1)
    return lab, positions, truth


def share_right(labels, truth):
    """The share of squares whose fabric's most common truth is their own."""
    named = {v: np.bincount(truth[labels == v]).argmax() for v in np.unique(labels)}
    return float(np.mean(np.array([named[v] for v in labels]) == truth))


@pytest.mark.parametrize(("sigma", "least"), [(3, 0.9967), (4, 0.98)])
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_the_shading_correction_keeps_bands_of_rising_lightness(sigma, least, seed):
    # Source: PR #251 round 1 (critical): a surface per fabric, fitted only
    #   over its own rows, swung outside them and read 0.47 to 0.95 of these
    #   squares right; the light is now one surface every fabric shares.
    # Inputs: bands_of_rising_lightness(sigma, seed), k = 4.
    # Formula: d = sqrt((0.5 dL)^2 + da^2 + db^2). Every band has a* = b* =
    #   0, so a square's da and db are the same to every band's color and
    #   only dL decides: under flat light it reads its own band unless its L*
    #   noise passes the midpoint 10 away, |n| > 10.
    # Arithmetic: sigma 4: P(N > 10 / 4 = 2.5) = 0.00621. The two inner bands
    #   misread on either side, 2 x 0.00621 = 0.01242, the two outer bands
    #   on one, 0.00621; on average (2 x 0.01242 + 2 x 0.00621) / 4 =
    #   0.00932, so an exact flat read gets 1 - 0.00932 = 0.9907 right, with
    #   sd sqrt(2464 x 0.00932) = 4.8 squares; 0.98 leaves 49 misreads, 5
    #   sd past the 23 expected. sigma 3: P(N > 3.333) = 0.000429, on average
    #   0.000644, so 0.99936 right, 1.59 misreads expected with sd
    #   sqrt(2464 x 0.000644) = 1.26; 5 sd past it is 1.59 + 6.30 = 7.9
    #   misreads, 1 - 7.9 / 2464 = 0.99679, so 0.9967 (8.1 misreads).
    # Expected: at least 0.98 (sigma 4) and 0.9967 (sigma 3) of squares
    #   right.
    lab, positions, truth = bands_of_rising_lightness(sigma, seed)
    result = cluster(lab, np.ones(len(lab)), positions, 4)
    assert share_right(result.labels, truth) >= least


def test_a_light_that_runs_away_keeps_the_flat_read():
    # Source: knobs.LIGHT_MAX_RATIO (PR #251 rounds 2 and 3; #137 comment
    #   6148562029): with no cap this grid's light runs past 8 in 10 rounds
    #   and the read keeps 0.56 of squares. At cap 2.0 the light passes the
    #   cap in round 4 (#248 comment 6149362474). The test fails with no cap
    #   and with 2 or 3 rounds (0.94 and 0.92); it passes at any cap up to 8,
    #   which the light passes by round 10.
    # Inputs: bands_of_rising_lightness(5, 0), k = 4, the default rounds.
    # Formula: as the band test above; past the cap the read is k-means'.
    # Arithmetic: sigma 5: P(N > 10 / 5 = 2) = 0.02275; on average (2 x 2 x
    #   0.02275 + 2 x 0.02275) / 4 = 0.03413 misread, so a flat read gets
    #   0.9659 right, 84.1 misreads expected with sd sqrt(2464 x 0.03413 x
    #   0.9659) = 9.0; 0.95 leaves 123 misreads, 4.3 sd past them.
    # Expected: at least 0.95 of squares right.
    lab, positions, truth = bands_of_rising_lightness(5, 0)
    result = cluster(lab, np.ones(len(lab)), positions, 4)
    assert share_right(result.labels, truth) >= 0.95


def value_ramp(seed):
    """Six grays, L* 25 + 12i for i = 0 to 5 with a* = b* = 0, in bands of a
    56 x 44 grid under flat light (row r in band floor(6r / 56): 10, 9, 9, 10,
    9 and 9 rows), plus Gaussian noise of sd 3 on every channel from numpy's
    PCG64 generator."""
    rows, cols = 56, 44
    r, c = np.divmod(np.arange(rows * cols), cols)
    truth = r * 6 // rows
    lab = np.zeros((rows * cols, 3))
    lab[:, 0] = 25 + 12 * truth
    lab += np.random.default_rng(seed).normal(0.0, 3, lab.shape)
    positions = np.stack([(c + 0.5) / cols, (r + 0.5) / rows], axis=1)
    return lab, positions, truth


@pytest.mark.parametrize("seed", range(8))
def test_a_value_ramp_reads_no_worse_with_the_light_than_without(seed):
    # Source: the ruling in #137 comment 6149208104: the light correction
    #   never reads a quilt worse than the uncorrected read. At cap 6 these
    #   grids read 0.625 to 0.952 against 0.952 to 0.968 uncorrected (#261).
    # Inputs: value_ramp(seed), k = 6, the default rounds and cap, and the
    #   same grid with shading_rounds 0.
    # Formula: every band has a* = b* = 0, so only dL decides: under flat
    #   light a square reads its own band unless its L* noise passes the
    #   midpoint 12 / 2 = 6 away, |n| > 6.
    # Arithmetic: P(N > 6 / 3 = 2) = 0.02275. The outer bands (10 + 9 = 19
    #   rows) misread on one side, the inner four (9 + 9 + 10 + 9 = 37 rows)
    #   on both: 44 x 0.02275 x (19 + 2 x 37) = 44 x 0.02275 x 93 = 93.1
    #   misreads expected of 2464, so an exact flat read gets 1 - 93.1 / 2464
    #   = 0.9622 right, with sd sqrt(2464 x 0.0378 x 0.9622) = 9.5 squares;
    #   0.94 leaves 147.8 misreads, 5.8 sd past the 93.1 expected.
    # Expected: the corrected read gets at least the uncorrected read's
    #   share right, and at least 0.94.
    lab, positions, truth = value_ramp(seed)
    weights = np.ones(len(lab))
    corrected = share_right(cluster(lab, weights, positions, 6).labels, truth)
    plain = share_right(cluster(lab, weights, positions, 6, shading_rounds=0).labels, truth)
    assert corrected >= plain
    assert corrected >= 0.94


def test_a_light_past_the_cap_keeps_the_plain_read(monkeypatch):
    # Source: knobs.LIGHT_MAX_RATIO: a fitted light that varies more than
    #   the cap in luminance drops the correction.
    # Inputs: falloff_grid(); the cap lowered to 1.0, which any light that
    #   varies at all passes.
    # Arithmetic: the falloff scales luminance from 1.0 to 0.7, a ratio of
    #   1 / 0.7 = 1.43 > 1.0, so the first light fitted passes the cap and
    #   the read keeps k-means' labels and centers, as with shading_rounds 0.
    # Expected: labels and centers equal the shading_rounds = 0 read's.
    lab, _ = falloff_grid()
    monkeypatch.setattr(fabrics_module, "LIGHT_MAX_RATIO", 1.0)
    capped = read_fabrics(squares_of(lab), 2)
    plain = read_fabrics(squares_of(lab), 2, shading_rounds=0)
    assert np.array_equal(capped.labels, plain.labels)
    assert np.array_equal(capped.centers, plain.centers)


def test_a_fabric_away_from_the_center_shows_its_own_color():
    # Source: PR #251 round 1: a fabric in rows 0 to 2 shipped #410000 for
    #   #584982, its own surface carried to the field center.
    # Inputs: a 55 x 45 grid, rows 0 to 2 at (35, 20, -30), the rest at
    #   (85, 0, 10), flat light, Gaussian noise of sd 1 on every channel
    #   (PCG64, seed 0); k = 2.
    # Arithmetic: the fabric holds 3 x 45 = 135 squares, so the mean of its
    #   noise has sd 1 / sqrt(135) = 0.086 per channel; its color is its own
    #   squares' color under the shared light, which flat light leaves near
    #   1 everywhere, so the center lies within 0.5 (5.8 sd) of (35, 20, -30).
    # Expected: every square right and the dark center within 0.5 of
    #   (35, 20, -30) in each channel.
    rows, cols = 55, 45
    r, c = np.divmod(np.arange(rows * cols), cols)
    truth = (r > 2).astype(int)
    colors = np.array([(35.0, 20.0, -30.0), (85.0, 0.0, 10.0)])
    lab = colors[truth] + np.random.default_rng(0).normal(0.0, 1.0, (rows * cols, 3))
    result = read_fabrics(squares_of(lab.reshape(rows, cols, 3)), 2)
    assert np.array_equal(result.labels.ravel(), truth)
    assert result.centers[0] == pytest.approx(colors[0], abs=0.5)


def test_a_small_far_fabric_is_seeded_and_kept():
    # Source: PR #251 round 2: four golden-ratio seedings all missed a
    #   9-square accent, and the read shipped two background colors.
    # Inputs: a 55 x 45 grid at (85, 0, 10) with a 3 x 3 accent at rows 40
    #   to 42, columns 5 to 7, at (35, 20, -30), flat light, Gaussian noise
    #   of sd 3 on every channel (PCG64, seed 0); k = 2.
    # Formula: d^2 = (0.5 dL)^2 + da^2 + db^2.
    # Arithmetic: the accent sits (0.5 x 50)^2 + 20^2 + 40^2 = 625 + 400 +
    #   1600 = 2625 from the background in squared distance, sqrt 51.235,
    #   against noise of 1.5^2 + 3^2 + 3^2 = 20.25 per square, so the
    #   farthest-first seeding takes an accent square as its second center.
    #   The read with the accent costs the noise alone. A read that splits
    #   the background in two instead removes at most the 2 / pi share of
    #   one sd-3 channel's variance, 2466 x 9 x 2 / pi = 14130, and moves
    #   each half's center 3 sqrt(2 / pi) = 2.39 from the background's, so
    #   the accent's 9 squares stay at least (51.235 - 2.39)^2 = 2386 away,
    #   9 x 2386 = 21471 > 14130: the read with the accent has the lower
    #   inertia and is kept. The accent's mean of 9 squares has noise sd
    #   3 / 3 = 1 per channel.
    # Expected: every square right (the accent darkest, fabric 0) and its
    #   center within 5 (5 sd) of (35, 20, -30).
    rows, cols = 55, 45
    truth = np.ones((rows, cols), dtype=int)
    truth[40:43, 5:8] = 0
    colors = np.array([(35.0, 20.0, -30.0), (85.0, 0.0, 10.0)])
    lab = colors[truth.ravel()] + np.random.default_rng(0).normal(0.0, 3.0, (rows * cols, 3))
    result = read_fabrics(squares_of(lab.reshape(rows, cols, 3)), 2)
    assert np.array_equal(result.labels, truth)
    assert result.centers[0] == pytest.approx(colors[0], abs=5.0)


@pytest.mark.parametrize("seed", range(30))
def test_heavy_strips_do_not_hide_a_small_far_fabric(seed):
    # Source: PR #251 round 2 self-review: weighted by area, a band strip
    #   near the first center outranked the accent in the farthest-first
    #   seeding, and the read lost the accent on 15 of these 30 grids.
    # Inputs: the grid of the test above with noise seed `seed`, then, from
    #   the same generator, 4 band strips at (81, 0, 10), a border 4 darker
    #   than the background, plus noise of sd 0.5, at the area weights of a
    #   2.5-square band (112.5 and 137.5) and outside the field; k = 2,
    #   through fabrics.cluster.
    # Arithmetic: a strip sits about (0.5 x 4)^2 = 4 from the background
    #   color in squared distance and the accent 2625, so by distance alone
    #   the sample farthest from a first center on the background or a strip
    #   is an accent square, and from one in the accent a background sample
    #   or strip: one center per fabric. The strips cost a read with the
    #   accent about 4 x 125 x 4 = 2000, and a split read saves at most that
    #   plus the 14130 of the test above, about 16130 < 21471, the least it
    #   loses on the accent.
    # Expected: the accent's 9 squares share one label, every other square
    #   and every strip the other.
    rows, cols = 55, 45
    truth = np.ones((rows, cols), dtype=int)
    truth[40:43, 5:8] = 0
    colors = np.array([(35.0, 20.0, -30.0), (85.0, 0.0, 10.0)])
    rng = np.random.default_rng(seed)
    squares = colors[truth.ravel()] + rng.normal(0.0, 3.0, (rows * cols, 3))
    strips = np.array([81.0, 0.0, 10.0]) + rng.normal(0.0, 0.5, (4, 3))
    lab = np.vstack([squares, strips])
    weights = np.concatenate([np.ones(rows * cols), [112.5, 137.5, 112.5, 137.5]])
    r, c = np.divmod(np.arange(rows * cols), cols)
    field = np.stack([(c + 0.5) / cols, (r + 0.5) / rows], axis=1)
    outside = np.array([(0.5, -0.02), (1.03, 0.5), (0.5, 1.02), (-0.03, 0.5)])
    result = cluster(lab, weights, np.vstack([field, outside]), 2)
    expected = np.concatenate([truth.ravel(), np.ones(4, dtype=int)])
    assert same_partition(result.labels, [np.flatnonzero(expected == i) for i in (0, 1)])


def test_strips_join_at_their_area_and_their_center():
    # Source: the ticket's sample rule for band strips.
    # Inputs: counts 4 x 3 and bands 0.5 then 1.5 squares (as in
    #   test_read_sample.py): T = 2, outer edge 8 x 7 squares.
    # Formula: weight = length x width; center across the band at
    #   o + w/2 - T in field-plane squares; position (u / cols, v / rows).
    # Arithmetic:
    #   band 0 (o 0, w 0.5): across = 0.25 - 2 = -1.75; lengths 8 - 1 = 7
    #     along x and 7 - 1 = 6 along y: top and bottom 7 x 0.5 = 3.5, left
    #     and right 6 x 0.5 = 3.0. top (2, -1.75) -> (0.5, -0.583333), right
    #     (4 + 1.75, 1.5) -> (1.4375, 0.5), bottom (2, 3 + 1.75) ->
    #     (0.5, 1.583333), left (-1.75, 1.5) -> (-0.4375, 0.5).
    #   band 1 (o 0.5, w 1.5): across = 1.25 - 2 = -0.75; lengths 8 - 4 = 4
    #     and 7 - 4 = 3: top and bottom 6.0, left and right 4.5. top
    #     (0.5, -0.25), right (4.75 / 4, 0.5) = (1.1875, 0.5), bottom
    #     (0.5, 3.75 / 3) = (0.5, 1.25), left (-0.1875, 0.5).
    #   squares: raster order, weight 1, square 5 (r 1, c 1) at
    #     (1.5 / 4, 1.5 / 3) = (0.375, 0.5).
    # Expected: as above, strips after the 12 squares in squares.strips order.
    geometry = confirm(
        outer_frame(160, 140, 0.5, 1.5),
        counts(4, 3),
        (160, 140),
        Point(x=0, y=0),
        corners_source="user",
    )
    strips = [
        StripSample(band=b, side=s, lab=np.array([10.0 * b, i, 0.0]), spread=np.zeros(3))
        for b in (0, 1)
        for i, s in enumerate(("top", "right", "bottom", "left"))
    ]
    lab, weights, positions = _samples(squares_of(np.zeros((3, 4, 3)), geometry, strips))
    assert lab.shape == (20, 3)
    assert lab[12:].tolist() == [s.lab.tolist() for s in strips]
    assert weights.tolist() == [1.0] * 12 + [3.5, 3.0, 3.5, 3.0, 6.0, 4.5, 6.0, 4.5]
    assert positions[5].tolist() == [0.375, 0.5]
    assert positions[12:] == pytest.approx(
        np.array(
            [
                (0.5, -1.75 / 3),
                (1.4375, 0.5),
                (0.5, 4.75 / 3),
                (-0.4375, 0.5),
                (0.5, -0.25),
                (1.1875, 0.5),
                (0.5, 1.25),
                (-0.1875, 0.5),
            ]
        )
    )


def test_a_border_fabric_absent_from_the_field_gets_its_own_fabric():
    # Source: plan B2b (a border fabric that never appears in the field).
    # Inputs: counts 4 x 4 and one band of 1 square at 32 px per square, a
    #   192 x 192 image: the field (x, y 32..160) a checkerboard of gray 64
    #   (r + c even) and gray 192, the band red, BGR (0, 0, 255). Every square
    #   and strip warps by the identity and samples its own fill exactly
    #   (test_read_sample.py): gray 64 L 27.0934, gray 192 L 77.7044, red
    #   (53.2406, 80.0942, 67.2015). Each strip weighs 4 x 1 = 4.
    # Arithmetic: three distinct colors, so the read tries k = 2 and 3. At 3
    #   each fabric is one exact color: a = 0, b > 0, s = 1 everywhere, mean
    #   1.0. At 2 two colors share a fabric and its points have a > 0, so
    #   s < 1 there: the mean falls under 1.0. k = 3.
    # Expected: darkest first gray 64 -> 0, red -> 1, gray 192 -> 2; every
    #   strip label 1; the field labels 0 and 2 by the checkerboard.
    image = np.full((192, 192, 3), (0, 0, 255), dtype=np.uint8)
    for r in range(4):
        for c in range(4):
            level = 64 if (r + c) % 2 == 0 else 192
            image[32 + 32 * r : 64 + 32 * r, 32 + 32 * c : 64 + 32 * c] = level
    geometry = confirm(
        outer_frame(192, 192, 1.0),
        counts(4, 4),
        (192, 192),
        Point(x=0, y=0),
        corners_source="user",
    )
    result = read_fabrics(read_squares(image, geometry))
    assert isinstance(result, Fabrics)
    assert result.k == 3
    assert result.strip_labels == (1, 1, 1, 1)
    r, c = np.divmod(np.arange(16), 4)
    assert result.labels.reshape(-1).tolist() == np.where((r + c) % 2 == 0, 0, 2).tolist()
    assert result.centers == pytest.approx(
        np.array([(27.0934, 0, 0), (53.2406, 80.0942, 67.2015), (77.7044, 0, 0)]), abs=0.01
    )


def test_fabrics_order_darkest_first_then_by_a_then_b():
    # Source: the ticket's order rule (L* ascending, ties by a* then b*).
    # Inputs: a 6 x 6 grid at (r + c) mod 3 of colors 0 (50, 10, 0),
    #   1 (50, -10, 0) and 2 (50, -10, -20); k = 3.
    # Arithmetic: all at L* 50; by a*, colors 1 and 2 (-10) come before 0
    #   (10); between 1 and 2, b* -20 before 0: order 2, 1, 0.
    # Expected: label = [2, 1, 0][color], so color 2 reads 0 and color 0 reads 2.
    colors = np.array([(50.0, 10.0, 0.0), (50.0, -10.0, 0.0), (50.0, -10.0, -20.0)])
    r, c = np.divmod(np.arange(36), 6)
    index = (r + c) % 3
    result = read_fabrics(squares_of(colors[index].reshape(6, 6, 3)), 3)
    assert result.labels.reshape(-1).tolist() == np.array([2, 1, 0])[index].tolist()
    # The light, fitted as 1 on a flat grid, leaves float noise in the centers.
    assert result.centers == pytest.approx(colors[[2, 1, 0]], abs=1e-9)


def test_the_silhouette_keeps_every_strip_and_a_golden_ratio_pick_of_squares():
    # Source: the ticket's silhouette subsample, SILHOUETTE_SAMPLES = 2000.
    # Inputs: 2116 squares inside the field (weight 1), then 4 strips outside
    #   it (weights 3, 3, 5, 5).
    # Formula: square j of the pick is floor(frac((j + 1) x 0.618034) x n),
    #   the first m distinct values, sorted.
    # Arithmetic: 2000 - 4 = 1996 places for squares, so m = 1996 of n = 2116,
    #   each standing for 2116 / 1996 = 529/499 squares. The first picks:
    #   j = 0: 0.618034 x 2116 = 1307.76 -> 1307; j = 1: frac(1.236068) =
    #   0.236068 x 2116 = 499.52 -> 499; j = 2: frac(1.854102) = 0.854102 x
    #   2116 = 1807.28 -> 1807.
    # Expected: 1996 distinct sorted square indices under 2116, among them
    #   499, 1307 and 1807, then 2116..2119; weights 529/499 for the squares
    #   and 3, 3, 5, 5 for the strips; 2000 points.
    positions = np.concatenate([np.full((2116, 2), 0.5), [(0.5, -0.1), (1.1, 0.5)] * 2])
    weights = np.concatenate([np.ones(2116), [3.0, 3.0, 5.0, 5.0]])
    index, w = _subset(positions, weights)
    kept = index[:1996].tolist()
    assert len(index) == 2000
    assert kept == sorted(set(kept)) and kept[-1] < 2116
    assert {499, 1307, 1807} <= set(kept)
    assert index[1996:].tolist() == [2116, 2117, 2118, 2119]
    assert w[:1996] == pytest.approx([529 / 499] * 1996, abs=1e-12)
    assert w[1996:].tolist() == [3.0, 3.0, 5.0, 5.0]


def test_the_silhouette_sees_a_fabric_on_odd_columns():
    # Source: the ticket's silhouette subsample; a stride of 2 on a field of
    #   48 columns kept only the even columns, so a fabric there was unscored.
    # Inputs: a 48 x 48 field, 2304 squares; F1 (50, 60, 0) on the odd columns
    #   of rows 0 to 5 (6 x 24 = 144 squares); elsewhere F0 (30, 0, 0) where
    #   r + c is even and F2 (70, 0, 0) where it is odd; a requested k = 3.
    # Arithmetic: 2304 > 2000, so the pick keeps m = 2000. Square r x 48 + c
    #   is odd exactly when c is, so the old stride ceil(2304 / 2000) = 2 kept
    #   no F1 square. The golden-ratio pick keeps j = 4: frac(5 x 0.618034) =
    #   0.090170 x 2304 = 207.75 -> 207 = 4 x 48 + 15, and j = 12:
    #   frac(13 x 0.618034) = 0.034442 x 2304 = 79.35 -> 79 = 1 x 48 + 31,
    #   both F1 (odd column, row under 6). Each fabric is one flat color, so
    #   the one light fitted over all 2304 samples is flat, 1 up to float
    #   noise, and the corrected points are the samples: a = 0 and b > 0 at
    #   every kept point, s = 1, so the silhouette and every center confidence
    #   are 1.0.
    # Expected: labels as built (darkest first F0, F1, F2), palette and every
    #   center confidence 1.0, F1's above 0 in particular.
    rows = cols = 48
    r, c = np.divmod(np.arange(rows * cols), cols)
    truth = np.where((r < 6) & (c % 2 == 1), 1, np.where((r + c) % 2 == 0, 0, 2))
    colors = np.array([(30.0, 0.0, 0.0), (50.0, 60.0, 0.0), (70.0, 0.0, 0.0)])
    index, _ = _subset(np.stack([(c + 0.5) / cols, (r + 0.5) / rows], axis=1), np.ones(r.size))
    assert {79, 207} <= set(index.tolist())

    result = read_fabrics(squares_of(colors[truth].reshape(rows, cols, 3)), 3)
    assert np.array_equal(result.labels.ravel(), truth)
    assert result.palette_confidence == pytest.approx(1.0, abs=1e-12)
    assert result.center_confidence[1] > 0
    assert result.center_confidence == pytest.approx([1.0, 1.0, 1.0], abs=1e-12)


def test_the_read_is_deterministic():
    # Source: the ticket (no random draws; the same code runs in Pyodide).
    # Expected: two reads of one grid give identical labels, centers and
    # confidences, for a suggested and a requested count.
    lab, _ = three_fabrics()
    for k in (None, 5):
        first = read_fabrics(squares_of(lab), k)
        second = read_fabrics(squares_of(lab), k)
        assert np.array_equal(first.labels, second.labels)
        assert np.array_equal(first.centers, second.centers)
        assert np.array_equal(first.confidence, second.confidence)
        assert first.palette_confidence == second.palette_confidence


@pytest.mark.parametrize(
    "lab, expected",
    [
        ((53.5850, 0, 0), "#808080"),
        ((4.6805, 0, 0), "#101010"),
        ((100.0, 0, 0), "#ffffff"),
        ((0.0, 0, 0), "#000000"),
        ((53.2406, 80.0942, 67.2015), "#ff0000"),
        ((87.7351, -86.1813, 83.1775), "#00ff00"),
        ((32.2957, 79.1870, -107.8617), "#0000ff"),
        ((1.3833, 9.7205, -22.9429), "#000028"),
    ],
)
def test_a_center_shows_as_the_srgb_color_it_was_sampled_from(lab, expected):
    # Source: the forward values worked by hand in test_read_sample.py (gray
    # 128, 16, 255 and 0; red, green, blue; RGB (0, 0, 40)), so the inverse
    # returns their codes by construction.
    # Arithmetic for gray 16, which takes the linear branches: L 4.6805 is at
    #   most 903.3 x 0.008856 = 8.0, so Y = 4.6805 / 903.3 = 0.0051816; a
    #   gray has X/Xn = Y = Z/Zn, so linear R = G = B = 0.0051816, over
    #   0.0031308, so 1.055 x 0.0051816^(1/2.4) - 0.055 = 1.055 x 0.111607 -
    #   0.055 = 0.062745, and 0.062745 x 255 = 16.000, code 16: #101010.
    # Expected: the codes each value was computed from, as lowercase hex.
    assert fabrics_module.to_hex(np.array(lab)) == expected


def test_a_center_outside_the_gamut_clips_to_it():
    # L 50 with a* 120 lies past sRGB's red: X/Xn = (fy + 0.24)^3 with fy =
    # 66 / 116 = 0.568966, so 0.808966^3 = 0.529; the red channel solves past
    # 1 and clips to code 255, and the result stays a valid #rrggbb.
    color = fabrics_module.to_hex(np.array([50.0, 120.0, 0.0]))
    assert len(color) == 7 and color.startswith("#ff")
    assert all(ch in "0123456789abcdef" for ch in color[1:])


def test_a_refusal_code_is_typed():
    # Callers branch on the code, so an unknown code is a programming error.
    with pytest.raises(ValueError):
        Refusal(code="scrappy", message="")


def test_fabrics_use_numpy_alone():
    # Source: the ticket: numpy only, no generator, so the module runs the
    # same under Pyodide. No import of cv2, sklearn or scipy at any depth, and
    # no attribute named random.
    tree = ast.parse(Path(fabrics_module.__file__).read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    assert names <= {"dataclasses", "typing", "numpy", "qrep"}
    assert not any(isinstance(n, ast.Attribute) and n.attr == "random" for n in ast.walk(tree))
    assert math.isclose(GOLDEN, (math.sqrt(5) - 1) / 2)


# The 40 x 40 grids of the fabric-count measurement (#137 comment
# 6147407435), drawn from one numpy default_rng(seed) per grid in this order:
# each fabric's L* uniform on [20, 90], a* and b* on [-40, 40] (spaced grids
# redraw a fabric closer than 15 to an earlier one), then each square's
# fabric uniformly, then Gaussian noise of sd `noise` on every channel.
def _fabric_color(rng):
    return np.array([rng.uniform(20, 90), rng.uniform(-40, 40), rng.uniform(-40, 40)])


def counted_grid(fabrics, seed, noise, spaced=False):
    rng = np.random.default_rng(seed)
    colors = []
    while len(colors) < fabrics:
        color = _fabric_color(rng)
        if not spaced or all(np.linalg.norm(color - c) >= 15.0 for c in colors):
            colors.append(color)
    assign = rng.integers(0, fabrics, size=(40, 40)).ravel()
    lab = np.stack(colors)[assign] + rng.normal(0.0, noise, size=(1600, 3))
    r, c = np.divmod(np.arange(1600), 40)
    positions = np.stack([(c + 0.5) / 40, (r + 0.5) / 40], axis=1)
    return lab, positions


@pytest.mark.parametrize(("fabrics", "seed"), [(20, 0), (30, 0), (30, 1), (30, 2)])
def test_a_scrappy_quilt_is_refused(fabrics, seed):
    # Source: criterion 2 of #137 (never merge fabrics silently); the
    #   orchestrator's decision in #137 on the margin rule.
    # Inputs: counted_grid(fabrics, seed, noise 1.5), more fabrics than the
    #   cap of 12 by construction. These are the four measured grids whose
    #   silhouette peaked under 12 (at 11, 11, 10 and 11), which a refusal
    #   only at a peak of 12 merged; the last is the measurement's closest
    #   scrappy grid to the margin. The margin was set on these grids, so
    #   this test cannot fail for its value; knobs.COUNT_CAP_MARGIN records
    #   how it does out of sample.
    # Expected: too_many_fabrics, since the quilt holds more than 12.
    lab, positions = counted_grid(fabrics, seed, 1.5)
    result = fabrics_module.suggest(lab, np.ones(len(lab)), positions)
    assert isinstance(result, Refusal)
    assert result.code == "too_many_fabrics"


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_a_quilt_of_11_fabrics_keeps_its_count(seed):
    # Source: criterion 2 of #137: only a quilt of more than 12 fabrics
    #   refuses.
    # Inputs: counted_grid(11, seed, noise 1.5, spaced), 11 fabrics at least
    #   15 apart by construction; the measurement's closest grids to the
    #   margin from this side, since splitting one of 11 fabrics costs the
    #   silhouette least. The margin was set on these grids too; out of
    #   sample, 11-fabric grids refuse at noise 2.0 and up and some read 10
    #   (knobs.COUNT_CAP_MARGIN, #248).
    # Expected: no refusal, and the count read is the 11 the grid holds.
    lab, positions = counted_grid(11, seed, 1.5, spaced=True)
    result = fabrics_module.suggest(lab, np.ones(len(lab)), positions)
    assert not isinstance(result, Refusal)
    assert result.k == 11


@pytest.mark.parametrize("seed", [0, 1])
def test_a_noisy_three_fabric_quilt_is_not_refused(seed):
    # Source: criterion 2 of #137: a quilt within the cap never refuses.
    # Inputs: counted_grid(3, seed, noise 4), 3 fabrics by construction.
    # Expected: no refusal. It shows only that the margin leaves this grid
    #   alone, not that the read never merges: the count read may be 2 when
    #   two fabrics sit close, as on seed 1, 15.3 apart (#248).
    lab, positions = counted_grid(3, seed, 4.0)
    result = fabrics_module.suggest(lab, np.ones(len(lab)), positions)
    assert not isinstance(result, Refusal)
