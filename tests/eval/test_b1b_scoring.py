"""B1b spike: the corner-error helpers, the decision rule and the outer-edge methods on
synthetic photos.

Every expected value is worked by hand in the comments beside its assertion, from the issue's
own numbers (#135), the percentile formula, or the construction of the synthetic image; none
comes from running the spike. The synthetic images are built in Lab and converted to BGR, so a
designed color reaches the methods as the same color (to rounding: one uint8 level moves a Lab
value by well under 1 unit).
"""

import ast
import importlib.util
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from spikes import b1b_corners as b1b

# --- Square size and corner error ---------------------------------------------------------


def test_square_size_from_field_corners():
    # A 200 x 100 px field of 20 x 10 squares: 200 / 20 = 10 px across, 100 / 10 = 10 px down,
    # mean 10 px. The outer edge and the bands are not used when the field corners are known.
    field = np.array([[0.0, 0.0], [200.0, 0.0], [200.0, 100.0], [0.0, 100.0]])
    outer = np.array([[-50.0, -50.0], [250.0, -50.0], [250.0, 150.0], [-50.0, 150.0]])
    assert b1b.square_size(outer, field, (20, 10), [9.0]) == pytest.approx(10.0)
    # A 210 x 100 field of 20 x 10: 10.5 across and 10 down, mean 10.25.
    wide = np.array([[0.0, 0.0], [210.0, 0.0], [210.0, 100.0], [0.0, 100.0]])
    assert b1b.square_size(outer, wide, (20, 10), []) == pytest.approx(10.25)


def test_square_size_from_outer_edge_and_bands():
    # No field corners: the outer edge spans the counts plus each band twice. A 240 x 140 px
    # outer edge, 20 x 10 squares and bands of 1.5 and 0.5 squares (2 squares, so 4 more per
    # axis): 240 / (20 + 4) = 10 across, 140 / (10 + 4) = 10 down, mean 10.
    outer = np.array([[0.0, 0.0], [240.0, 0.0], [240.0, 140.0], [0.0, 140.0]])
    assert b1b.square_size(outer, None, (20, 10), [1.5, 0.5]) == pytest.approx(10.0)
    # No bands: the outer edge is the field. 240 / 20 = 12 and 140 / 10 = 14, mean 13.
    assert b1b.square_size(outer, None, (20, 10), []) == pytest.approx(13.0)


def test_corner_errors_in_square_units():
    # Truth corners of a 400 x 200 px quad, squares of 20 px. Suggested corners moved by
    # (3, 4), (0, 0), (-6, 8) and (0, -10): distances 5, 0, 10 and 10 px, so
    # 5 / 20 = 0.25, 0, 10 / 20 = 0.5 and 0.5 square.
    truth = np.array([[100.0, 100.0], [500.0, 100.0], [500.0, 300.0], [100.0, 300.0]])
    moved = truth + np.array([[3.0, 4.0], [0.0, 0.0], [-6.0, 8.0], [0.0, -10.0]])
    errors = b1b.corner_errors(moved, truth, 20.0)
    assert errors.tolist() == pytest.approx([0.25, 0.0, 0.5, 0.5])


def test_to_source_maps_pixel_centres():
    # At scale (0.5, 0.25), staged centre x = 10 is edge coordinate 10.5, source edge
    # 10.5 / 0.5 = 21, source centre 20.5; y = 20 is 20.5, then 20.5 / 0.25 = 82, centre 81.5.
    # Staged pixel 0 at scale 0.5 averages source pixels 0 and 1, whose centres average 0.5:
    # (0 + 0.5) / 0.5 - 0.5 = 0.5; at scale 0.25 it averages rows 0 to 3, centre 1.5:
    # (0 + 0.5) / 0.25 - 0.5 = 1.5. At scale 1 the map is the identity: (c + 0.5) / 1 - 0.5 = c.
    staged = np.array([[10.0, 20.0], [0.0, 0.0]])
    assert b1b.to_source(staged, (0.5, 0.25)).ravel().tolist() == pytest.approx([20.5, 81.5, 0.5, 1.5])
    assert b1b.to_source(staged, (1.0, 1.0)).ravel().tolist() == pytest.approx([10.0, 20.0, 0.0, 0.0])


def test_order_corners():
    # Top left has the smallest x + y, bottom right the largest; top right the largest x - y,
    # bottom left the smallest. Shuffled corners of a tilted quad come back in that order.
    quad = np.array([[310.0, 260.0], [60.0, 40.0], [40.0, 240.0], [330.0, 60.0]])
    assert b1b.order_corners(quad).tolist() == [[60, 40], [330, 60], [310, 260], [40, 240]]


# --- Tier summaries and the decision rule -------------------------------------------------


def test_summarize_tier():
    # Three photos: errors (0.1, 0.2, 0.1, 0.0), (0.3, 0.5, 0.2, 0.1), and no suggestion.
    # The 8 corners sorted: 0.0, 0.1, 0.1, 0.1, 0.2, 0.2, 0.3, 0.5.
    # Median, linear interpolation: position 0.5 x 7 = 3.5, between 0.1 and 0.2: 0.15.
    # 90th percentile: position 0.9 x 7 = 6.3, 0.3 + 0.3 x (0.5 - 0.3) = 0.36.
    # Every corner within 0.22: photo 1 (largest 0.2) yes; photo 2 (0.5) no; photo 3 has no
    # suggestion, so no: 1 of 3. No suggestion: 1 of 3.
    summary = b1b.summarize_tier([
        np.array([0.1, 0.2, 0.1, 0.0]), np.array([0.3, 0.5, 0.2, 0.1]), None])
    assert (summary["photos"], summary["suggested"], summary["corners"]) == (3, 2, 8)
    assert summary["median"] == pytest.approx(0.15)
    assert summary["p90"] == pytest.approx(0.36)
    assert (summary["within"], summary["none"]) == (1, 1)
    assert summary["within_rate"] == pytest.approx(1 / 3)
    assert summary["none_rate"] == pytest.approx(1 / 3)


def test_summarize_tier_bar_is_inclusive_and_empty_tier_has_no_numbers():
    # A photo whose largest corner error is exactly 0.22 counts as within 0.22 ("within" is
    # at most).
    assert b1b.summarize_tier([np.array([0.22, 0.0, 0.1, 0.22])])["within"] == 1
    # A tier with no photos has no percentiles and no rates.
    empty = b1b.summarize_tier([])
    assert (empty["photos"], empty["corners"], empty["median"], empty["p90"]) == (0, 0, None, None)
    assert (empty["within_rate"], empty["none_rate"]) == (None, None)
    # A tier where no photo got a suggestion has photos but no corners, so no percentiles.
    blank = b1b.summarize_tier([None, None])
    assert (blank["photos"], blank["corners"], blank["p90"], blank["none"]) == (2, 0, None, 2)


def test_decision_rule():
    # Issue #135 criterion 5: go when the 90th-percentile corner error is at most 0.22 of a
    # square on both the screenshot tier and the museum tier.
    # Both tiers at or under the bar, and the bar is inclusive (0.22 <= 0.22): go.
    assert b1b.decide({"museum": {"corners": 44, "p90": 0.22},
                       "screenshot": {"corners": 8, "p90": 0.10}})
    # The museum tier just over the bar: no-go.
    assert not b1b.decide({"museum": {"corners": 44, "p90": 0.2201},
                           "screenshot": {"corners": 8, "p90": 0.10}})
    # A tier with n = 0 (no corners, so no percentile) cannot show the bar is met: no-go,
    # however good the other tier is.
    assert not b1b.decide({"museum": {"corners": 44, "p90": 0.05},
                           "screenshot": {"corners": 0, "p90": None}})
    # A tier that is missing altogether: no-go.
    assert not b1b.decide({"museum": {"corners": 44, "p90": 0.05}})
    # The bar is the issue's number.
    assert b1b.BAR == 0.22


def test_wilson_interval():
    # k = 9, n = 11, z = 1.96 (the same worked case as B1a's test): p = 0.818182,
    # denom = 1 + 3.8416 / 11 = 1.349236, centre = (0.818182 + 0.174618) / 1.349236 = 0.735824,
    # half = 1.96 x sqrt(0.013524 + 0.007937) / 1.349236 = 0.212810: [0.523014, 0.948634].
    lo, hi = b1b.wilson(9, 11)
    assert lo == pytest.approx(0.523014, abs=2e-6)
    assert hi == pytest.approx(0.948634, abs=2e-6)
    assert b1b.wilson(0, 0) == (0.0, 1.0)


# --- Lines and quads ----------------------------------------------------------------------


def test_quad_from_lines():
    # Lines as (vx, vy, x0, y0): top y = 10, right x = 205, bottom y = 110, left x = 5, with the
    # right side leaning: through (205, 10) toward (215, 110), direction (0.1, 1) unnormalized.
    # Top meets left at (5, 10) and right at (205, 10). The right line at y = 110 is at
    # x = 205 + 0.1 x 100 = 215, so bottom meets right at (215, 110) and left at (5, 110).
    lines = [(1.0, 0.0, 0.0, 10.0), (0.1, 1.0, 205.0, 10.0), (1.0, 0.0, 50.0, 110.0),
             (0.0, 1.0, 5.0, 0.0)]
    corners = b1b.quad_from_lines(lines)
    assert corners.ravel().tolist() == pytest.approx([5, 10, 205, 10, 215, 110, 5, 110])
    # Parallel neighbours never meet: no quad.
    assert b1b.quad_from_lines([(1.0, 0.0, 0.0, 0.0)] * 4) is None


# --- The outer-edge methods on synthetic photos --------------------------------------------


def _lab_to_bgr(lab: np.ndarray) -> np.ndarray:
    bgr = cv2.cvtColor(lab.astype(np.float32), cv2.COLOR_Lab2BGR)
    return np.clip(np.round(bgr * 255.0), 0, 255).astype(np.uint8)


# A warm white paper backdrop and two fabrics far from it: in L*0.5 Lab the backdrop sits at
# (47.5, 0, 4) and the fabrics at (20, 40, 20) and (30, -30, -20), over 40 units away.
BACKDROP = (95.0, 0.0, 4.0)
FABRICS = ((40.0, 40.0, 20.0), (60.0, -30.0, -20.0))


def _checker_lab(height: int, width: int, pitch: int) -> np.ndarray:
    ys, xs = np.mgrid[0:height, 0:width]
    odd = ((ys // pitch) + (xs // pitch)) % 2 == 1
    lab = np.empty((height, width, 3), np.float32)
    for channel in range(3):
        lab[..., channel] = np.where(odd, FABRICS[1][channel], FABRICS[0][channel])
    return lab


def _scene(shape: tuple[int, int], corners: np.ndarray, pitch: int = 10) -> np.ndarray:
    """A checkerboard quilt warped into corners (TL, TR, BR, BL) on the backdrop."""
    height, width = shape
    quilt = _lab_to_bgr(_checker_lab(200, 200, pitch))
    source = np.array([[0, 0], [200, 0], [200, 200], [0, 200]], np.float32)
    matrix = cv2.getPerspectiveTransform(source, corners.astype(np.float32))
    backdrop = _lab_to_bgr(np.array([[BACKDROP]], np.float32))[0, 0]
    return cv2.warpPerspective(quilt, matrix, (width, height), flags=cv2.INTER_NEAREST,
                               borderMode=cv2.BORDER_CONSTANT,
                               borderValue=tuple(int(v) for v in backdrop))


RECT = np.array([[80.0, 60.0], [320.0, 60.0], [320.0, 240.0], [80.0, 240.0]])
TILTED = np.array([[60.0, 40.0], [330.0, 60.0], [310.0, 260.0], [40.0, 240.0]])
# Each suggested corner coordinate's largest distance from the constructed one, derived in
# test_methods_find_a_quilt_on_a_plain_backdrop.
RECT_BOUND = 1.0
TILTED_BOUND = 1.5
# backdrop_lines meets the derived bound only to float32 rounding: cv2.fitLine returns its
# point and unit direction as float32, so the point is off by up to half the float32 spacing
# at 256 to 512 px, 2^-15 / 2 = 1.5e-5, and the direction by up to 2^-24 = 6e-8 per
# component, which the extrapolation to a corner, at most a 400 px side away, makes
# 400 x 6e-8 = 2.4e-5. Two lines meeting add under 1e-4 between them.
FIT_SLACK = 1e-4


@pytest.mark.parametrize("method", ["backdrop_hull", "backdrop_lines", "tiered"])
@pytest.mark.parametrize("corners, bound", [(RECT, RECT_BOUND), (TILTED, TILTED_BOUND)],
                         ids=["rect", "tilted"])
def test_methods_find_a_quilt_on_a_plain_backdrop(method, corners, bound):
    # Both quads are parallelograms, so _scene's warp is affine, p = corner + J (u, v). With
    # INTER_NEAREST it reads each pixel centre p from source pixel round(J^-1 (p - corner)), so
    # the quilt covers the centres whose source point lies in [-0.5, 199.5) each way: the
    # constructed quad moved by J (-0.5, -0.5).
    # RECT: J = diag(240 / 200, 180 / 200) = diag(1.2, 0.9), moved by (-0.6, -0.45): x in
    # [79.4, 319.4) and y in [59.55, 239.55), so the quilt covers pixel centres 80 to 319 and
    # 60 to 239.
    # - tiered: tier 1 (four pure-backdrop strips, equal, MAD 0, so the 25 BGR unit floor, far
    #   under any fabric's distance) masks exactly those pixels; a 5 x 5 closing leaves a
    #   rectangle as it is, and the hull's vertices are (80, 60), (319, 60), (319, 239) and
    #   (80, 239): 0 or 1 px from each corner coordinate.
    # - backdrop_hull and backdrop_lines: the border ring is backdrop alone (MAD 0, so the 6
    #   unit floor). The sigma 1 blur (taps 0.399, 0.242, 0.054, 0.004 from the centre out)
    #   gives the first backdrop pixel outside a side 0.242 + 0.054 + 0.004 = 0.30 of the step to
    #   the quilt and the second 0.054 + 0.004 = 0.06. The step is at least 42 L*0.5 Lab units
    #   (FABRICS[1]: sqrt(17.5^2 + 30^2 + 24^2) = 42.2; FABRICS[0]: sqrt(27.5^2 + 40^2 + 16^2) =
    #   51.1), so the first pixel sits 12.6 or more units off the backdrop, over 6, and joins
    #   the quilt; the second at most 0.06 x 51.1 = 3.1, under 6, and stays backdrop. The mask
    #   holds columns 80 to 319 and rows 60 to 239 and lies within columns 79 to 320 and rows 59
    #   to 240, so its hull vertices and the lines through its sides are within 1 px of each
    #   corner coordinate.
    # TILTED: J has columns (270, 20) / 200 = (1.35, 0.1) and (-20, 200) / 200 = (-0.1, 1.0),
    # so the covered quad is the constructed one moved by -(1.35 - 0.1, 0.1 + 1.0) / 2 =
    # (-0.625, -0.55): its top and left sides move 0.50 and 0.68 px out, its right and bottom
    # sides 0.68 and 0.50 px in.
    # - tiered: the covered centre nearest each corner, by solving for its source point, is
    #   (60, 40) (source (0, 0)), (329, 60) ((199.26, 0.07); (330, 60) is at u = 200), (309, 259)
    #   and (40, 239): 0 or 1 px from each corner coordinate.
    # - backdrop_hull: the blur adds the next pixel out across each side, as in RECT, and not
    #   the diagonal one off a corner (0.30 x 0.30 = 0.09 of a step, at most 4.6 units), so a
    #   hull corner moves at most 1 px outward in one coordinate from tiered's. Each coordinate
    #   that tiered has 1 px off lies inside the constructed one (329 < 330, 309 < 310, 259 <
    #   260, 239 < 240), so an outward move cannot take it to 2: top left becomes (60, 39) or
    #   (59, 40), top right (330, 60) or (329, 59), still within 1 px.
    # - backdrop_lines: the mask's outermost pixels along a tilted side form a staircase whose
    #   offset from the moved side runs evenly through 0 to 1 px, so the fitted line sits half a
    #   pixel out from the moved side: on the left 0.68 + 0.5 = 1.18 px out of the constructed
    #   side, on the top 0.50 + 0.5 = 1.00. Where two such lines meet at a near right angle,
    #   the corner moves about as much per coordinate. At a stair step the blur can add a
    #   second pixel out (0.30 x 0.30 + 0.06 x 0.70 = 0.13 of a step, 5.6 to 6.7 units, at the
    #   6 unit tolerance), one point in 10 to 14 along a side, which pulls the fit a little
    #   further.
    # So TILTED's bound is the 1 px mask bound plus half a pixel where two staircase edges
    # meet: 1.5 px, which covers the lines' 1.18 with room for that pull.
    image = _scene((300, 400), corners)
    suggestion = b1b.METHODS[method](image)
    assert suggestion is not None
    assert np.abs(suggestion.corners - corners).max() <= bound + FIT_SLACK
    assert 0.0 <= suggestion.confidence <= 1.0


@pytest.mark.parametrize("method", ["backdrop_hull", "backdrop_lines"])
def test_backdrop_gives_no_suggestion_when_the_quilt_runs_off_the_frame(method):
    # The quilt spans x = 100 to 400 in a 400 px wide photo, so it covers the whole right
    # border column (rows 60 to 239, 180 of 300 rows): its right edge is not in the photo.
    # The method gives no suggestion and never the full frame.
    # The right ring strip (6 px, 2 percent of 300) is quilt on 180 of its 300 rows, so it is
    # not uniform; the other three are pure backdrop, and three uniform sides are enough to
    # segment. The quilt then covers 180 / 300 = 0.6 of the right border column, over the 0.02
    # it may touch, and that is the reason given.
    corners = np.array([[100.0, 60.0], [400.0, 60.0], [400.0, 240.0], [100.0, 240.0]])
    image = _scene((300, 400), corners)
    assert b1b.METHODS[method](image) is None
    assert b1b.explain(method, image) == (None, "component touches the photo's border")


def test_backdrop_gives_no_suggestion_without_a_backdrop():
    # A checkerboard of 10 px squares over the whole 400 x 300 frame: the top and bottom strips
    # hold 20 squares of each fabric across (400 / 10 = 40), the left and right strips 15 of
    # each down (300 / 10 = 30). The
    # per-channel median of an even split lies midway between the fabrics, half their
    # distance of sqrt(10^2 + 70^2 + 40^2) = 81.2 from each, so the MAD is 40.6, over the
    # 4 unit ceiling. (Were the split uneven, the median would sit on one fabric and only about
    # half the strip would be inliers, under the 0.9 floor.) No strip is uniform, so there is
    # no backdrop to segment.
    image = _lab_to_bgr(_checker_lab(300, 400, 10))
    assert b1b.backdrop_hull(image) is None
    assert b1b.backdrop_lines(image) is None
    assert b1b.explain("backdrop_hull", image) == (None, "no backdrop: under 2 uniform ring sides")


def test_tiered_maps_the_full_frame_to_no_suggestion(monkeypatch):
    # Tier 3 is rectify's last resort, the full-image quad. The spike records it as no
    # suggestion (issue #135 criterion 3: a missing suggestion is never replaced by the full
    # frame).
    full = np.array([[0.0, 0.0], [400.0, 0.0], [400.0, 300.0], [0.0, 300.0]])
    monkeypatch.setattr(b1b, "_detect_tiered", lambda image: (full, 0.0, 3, None))
    assert b1b.tiered(np.zeros((300, 400, 3), np.uint8)) is None
    assert b1b.explain("tiered", np.zeros((300, 400, 3), np.uint8)) == (
        None, "tier 3, the full frame")
    # Tier 1's quad passes through with its tier.
    quad = RECT.copy()
    monkeypatch.setattr(b1b, "_detect_tiered", lambda image: (quad, 0.01, 1, None))
    suggestion = b1b.tiered(np.zeros((300, 400, 3), np.uint8))
    assert suggestion.corners.tolist() == RECT.tolist()
    assert suggestion.tier == 1
    # Its confidence is rectify's residual term, 1 - min(10 x 0.01, 1) = 0.9.
    assert suggestion.confidence == pytest.approx(0.9)


def test_tiered_gives_no_suggestion_on_an_empty_renderer_frame():
    # A frame of the renderer's #404040 alone, BGR (64, 64, 64) everywhere: the pooled strip
    # median is (64, 64, 64), BACKGROUND_BGR itself, distance 0 <= LEGACY_EPSILON (8), so tier
    # 0 runs. Every pixel is at distance 0 from the background, not over 40, so its mask is
    # empty, the closing keeps it empty, there is no contour, and _detect_quad raises. The
    # spike records that as no suggestion, with its reason, instead of failing the run.
    image = np.full((300, 400, 3), 64, np.uint8)
    assert b1b.explain("tiered", image) == (None, "tier 0 found no quilt")
    assert b1b.tiered(image) is None


# --- Band proposals -----------------------------------------------------------------------


def _banded() -> np.ndarray:
    # A 300 x 300 outer edge: band A for depths 0 to 14 (15 px) on every side, band B inside it,
    # and a checkerboard field of 15 px squares at x 60 to 269 and y 45 to 254 (210 / 15 = 14
    # squares each way), set off center so that band B is deeper on some sides. The inner edge
    # of A sits at depth 15 on every side, the field's edge at 45 on the top, 300 - 270 = 30 on
    # the right, 300 - 255 = 45 on the bottom and 60 on the left.
    lab = np.empty((300, 300, 3), np.float32)
    lab[...] = (70.0, 10.0, 40.0)  # band A
    lab[15:285, 15:285] = (50.0, -30.0, 30.0)  # band B
    lab[45:255, 60:270] = _checker_lab(210, 210, 15)
    return _lab_to_bgr(lab)


BANDED_OUTER = np.array([[0.0, 0.0], [300.0, 0.0], [300.0, 300.0], [0.0, 300.0]])
BANDED_FIELD = np.array([[60.0, 45.0], [270.0, 45.0], [270.0, 255.0], [60.0, 255.0]])


def test_band_change_points_on_synthetic_bands():
    # The outer edge is the whole image, so the warp is the identity. Each side's profile is the
    # mean color across its middle 60 percent (columns or rows int(0.2 x 300) = 60 to
    # int(0.8 x 300) - 1 = 239) at depths 0 to int(0.25 x 300) - 1 = 74, unblurred, with a
    # window of max(3, round(0.01 x 300)) = 3 px, so peaks are searched at depths 4 to 71.
    # Inside the field those 180 px span exactly 12 squares: on the top and bottom, field
    # columns 0 to 179 (squares 0 to 11); on the left and right, field rows 15 to 194 (squares
    # 1 to 12). Each holds 6 squares of each fabric, so every field depth has the same mean and
    # the field adds no change point.
    # The two-window difference |mean(p[d:d + w]) - mean(p[d - w:d])| of a step at depth s
    # rises linearly to the full step at d = s and falls after, so it peaks exactly at each
    # band edge: top [15, 45], right [15, 30], bottom [15, 45], left [15, 60], each step over
    # the floor of 2 (A to B: sqrt(10^2 + 40^2 + 10^2) = 42.4 in L*0.5 Lab; B to the field's
    # mean color (25, 5, 0): sqrt(0 + 35^2 + 30^2) = 46.1). The outer edge (depth 0) is outside
    # the search.
    proposals = b1b.band_proposals(_banded(), BANDED_OUTER)
    assert proposals == {"top": [15, 45], "right": [15, 30], "bottom": [15, 45], "left": [15, 60]}


def test_band_truth_on_an_off_center_field():
    # The same geometry as _banded. The outer edge is the whole 300 x 300 image, so the warp is
    # the identity and the field corners stay (60, 45), (270, 45), (270, 255), (60, 255). The
    # square is the field's 210 px over 14 squares each way: 210 / 14 = 15 px. Bands of 1 and 2
    # squares put the running sums at 1 and 3; the innermost edge comes from the field corners
    # instead: top 45 / 15 = 3, right (300 - 270) / 15 = 2, bottom (300 - 255) / 15 = 3, left
    # 60 / 15 = 4.
    square, truth = b1b.band_truth(BANDED_OUTER, BANDED_FIELD, (14, 14), [1.0, 2.0])
    assert square == pytest.approx(15.0)
    assert truth["top"] == pytest.approx([1.0, 3.0])
    assert truth["right"] == pytest.approx([1.0, 2.0])
    assert truth["bottom"] == pytest.approx([1.0, 3.0])
    assert truth["left"] == pytest.approx([1.0, 4.0])


def test_change_points_need_both_neighbours_measured():
    # A 60-depth profile and a window of 10: strengths are measured at depths 10 to 50, so a
    # peak, which needs both neighbours measured, can sit at depths 11 to 49.
    # A step of 30 units at depth 2 (depths 0 and 1 at 0, the rest at 30): at d = 10 the window
    # before holds depths 0 to 9, two of them at 0, mean 30 x 8 / 10 = 24 against 30 after,
    # strength 6; at d = 11 one of them, mean 27, strength 3; from d = 12 both windows are all
    # 30, strength 0. Depth 10 is not searchable (depth 9 was never measured) and depth 11, over
    # the floor of 2, is no peak (3 < 6): no proposal.
    shallow = np.zeros((60, 3))
    shallow[2:, 0] = 30.0
    assert b1b.change_points(shallow, 10) == []
    # The mirror at the far end, a step at depth 58: d = 50 sees two of 30 in its window after
    # (strength 6), d = 49 one (3), so again depth 50 is not searchable and 49 is no peak.
    deep = np.zeros((60, 3))
    deep[58:, 0] = 30.0
    assert b1b.change_points(deep, 10) == []
    # A step at depth 30, well inside: strength (d - 20) / 10 x 30 from d = 20 to 30 and
    # (40 - d) / 10 x 30 from 30 to 40, so the one peak is 30 (30 > 27 before it, 30 >= 27
    # after).
    inside = np.zeros((60, 3))
    inside[30:, 0] = 30.0
    assert b1b.change_points(inside, 10) == [30]


def test_band_window_and_searchable_edges():
    # The window is 1 percent of the warped outer edge's shorter side, at least 3 px: 300 x 300
    # gives round(3.0) = 3, 1000 x 800 gives round(8.0) = 8, and 250 x 200 gives round(2.0) = 2,
    # raised to 3.
    assert b1b.band_window((300, 300)) == 3
    assert b1b.band_window((1000, 800)) == 8
    assert b1b.band_window((250, 200)) == 3
    # With a 4 px window the first searchable depth is 4 + 1 = 5 px, 5 / 10 = 0.5 of a 10 px
    # square: an edge at 0.4 squares is too shallow to propose, one at exactly 0.5 can be.
    assert b1b.searchable([0.4, 0.5, 0.6], 4, 10.0) == [False, True, True]


def test_band_summary_counts_searchable_edges_only():
    # Three side records. Of the six edges, two are unsearchable (the 0.05 in the first record
    # and the second, unproposed, edge in the second), so they are counted apart and nowhere
    # else, although the 0.05 is within 0.22. The four searchable edges: errors 0.1, 0.3 and
    # 0.2, and one with no proposal (the first edge of the second record).
    # Median of 0.1, 0.2, 0.3: 0.2. 90th percentile: position 0.9 x 2 = 1.8, so
    # 0.2 + 0.8 x (0.3 - 0.2) = 0.28. Within 0.22: 0.1 and 0.2, so 2. Proposals per side: (2 + 0
    # + 2) / 3 records = 4 / 3. Photos: p1 and p2.
    records = [
        {"photo": "p1", "proposals": [0.1, 1.1], "errors": [0.05, 0.1], "searchable": [False, True]},
        {"photo": "p1", "proposals": [], "errors": [None, None], "searchable": [True, False]},
        {"photo": "p2", "proposals": [1.3, 3.2], "errors": [0.3, 0.2], "searchable": [True, True]},
    ]
    summary = b1b._band_summary(records)
    assert (summary["edges"], summary["missing"], summary["unsearchable"]) == (4, 1, 2)
    assert summary["median"] == pytest.approx(0.2)
    assert summary["p90"] == pytest.approx(0.28)
    assert summary["within"] == 2
    assert summary["proposals_per_side"] == pytest.approx(4 / 3)
    assert summary["photos"] == 2


def test_band_errors_in_squares():
    # Proposals at 15 and 45 px with 15 px squares are 1 and 3 squares in. Bands of 1 and 2
    # squares put their inner edges at 1 and 1 + 2 = 3 squares: errors 0 and 0. A proposal set
    # of [16, 60] instead gives 1 / 15 = 0.0667 for the first edge and |60 - 45| / 15 = 1 for
    # the second (each truth edge takes its nearest proposal); an empty set gives no error
    # (None) for each edge.
    assert b1b.band_errors([15, 45], [1.0, 3.0], 15.0) == pytest.approx([0.0, 0.0])
    assert b1b.band_errors([16, 60], [1.0, 3.0], 15.0) == pytest.approx([1 / 15, 1.0])
    assert b1b.band_errors([], [1.0, 3.0], 15.0) == [None, None]


# --- Independence from the detector, the dev split, the run header ------------------------


def _vision_names(source: str) -> list[str]:
    """Every way the source names qrep.vision: an import of it or of a module under it,
    `from qrep import vision`, or the attribute chain qrep.vision."""
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
            if node.module == "qrep":
                names += [f"qrep.{alias.name}" for alias in node.names]
        elif isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
              and node.value.id == "qrep" and node.attr == "vision"):
            names.append("qrep.vision")
    return [name for name in names if name == "qrep.vision" or name.startswith("qrep.vision.")]


def test_vision_names_finds_every_form():
    # Five lines that each reach qrep.vision, one per form, and two that do not: the checker
    # must list exactly the five (ast.walk goes breadth first, so compare them sorted).
    source = ("import qrep.vision.rectify\n"
              "from qrep.vision import grid\n"
              "from qrep import vision\n"
              "import qrep\n"
              "qrep.vision.rectify.detect\n"
              "from qrep import contract\n"
              "import qrep.vision\n")
    assert sorted(_vision_names(source)) == ["qrep.vision"] * 4 + ["qrep.vision.rectify"]


def test_spike_needs_no_module_b6b_deletes(monkeypatch):
    # B6b deletes the qrep.vision package (plan B6b), rectify.py included. No statement anywhere
    # in the script, inside a function or not, may name qrep.vision. At run time, a None entry
    # in sys.modules makes any import of that name raise ImportError, and removing the package's
    # vision attribute stops `from qrep import vision` and qrep.vision from finding a copy
    # another test imported, so with both done the script must still load, and its methods,
    # its band search and its corpus read must still run.
    import qrep

    assert _vision_names(Path(b1b.__file__).read_text(encoding="utf-8")) == []
    blocked = ["qrep.vision", "qrep.vision.rectify", "qrep.vision.grid"]
    blocked += [name for name in sys.modules if name.startswith("qrep.vision.")]
    for name in blocked:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.delattr(qrep, "vision", raising=False)
    spec = importlib.util.spec_from_file_location("b1b_isolated", b1b.__file__)
    isolated = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "b1b_isolated", isolated)
    spec.loader.exec_module(isolated)
    # The expectation of the plain-backdrop test on RECT: every corner coordinate within
    # RECT_BOUND, to the line fit's float32 rounding.
    image = _scene((300, 400), RECT)
    for method in ("backdrop_hull", "backdrop_lines", "tiered"):
        found, reason = isolated.explain(method, image)
        assert reason == "suggested"
        assert np.abs(found.corners - RECT).max() <= RECT_BOUND + FIT_SLACK
    # And of the band test: proposals at 15 and 45 px on the top side, 15 and 30 on the right.
    proposals = isolated.band_proposals(_banded(), BANDED_OUTER)
    assert (proposals["top"], proposals["right"]) == ([15, 45], [15, 30])
    # The committed corpus: corpus/manifest.csv puts lacma-54871 in tier A and eval_set v0,
    # outside the holdout (its sha256 starts 89f771d8, 68 mod 3 = 2, worked in
    # test_load_photos_reads_the_dev_split_only), with frame and counts claims in its committed
    # annotation, so it loads, and every photo loaded is a museum photo.
    photos, _skipped = isolated.load_photos()
    assert "lacma-54871" in [p.stem for p in photos]
    assert {p.tier for p in photos} == {"museum"}


def test_load_photos_reads_the_dev_split_only(tmp_path, monkeypatch):
    # A temporary corpus with five manifest rows, in this order:
    # 1. lacma-54871, tier A, eval_set v0, with its committed annotation. Its sha256 starts
    #    89f771d8: 8 + 9 + 15 + 7 + 7 + 1 + 13 + 8 = 68 and 68 mod 3 = 2 (16 = 1 mod 3, so a hex
    #    number mod 3 is its digit sum mod 3): outside the holdout (corpus/README.md: the first
    #    8 hex digits, read as an integer, divisible by 3).
    # 2. held, tier A, v0, sha256 starting 00000003: 3 mod 3 = 0, in the holdout.
    # 3. bare, tier A, v0, sha256 starting 00000001: outside, with no annotation.
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
    shutil.copy(b1b.REPO / "corpus" / "annotations" / "lacma-54871.json", tmp_path / "annotations")
    for stem in ("held", "tier-b", "tier-c"):
        (tmp_path / "annotations" / f"{stem}.json").write_text("not json", encoding="utf-8")
    monkeypatch.setattr(b1b, "CORPUS", tmp_path)
    photos, skipped = b1b.load_photos()
    # Only row 1 is read, as a museum photo. corpus/annotations/lacma-54871.json gives
    # proposed-a these outer-edge and field corners (top left, top right, bottom right, bottom
    # left), bands of 0.1, 2.2 and 0.7 squares from the outside in, and 10 blocks of 5 squares
    # each way, 50 x 50.
    assert [(p.stem, p.tier, sorted(p.truth)) for p in photos] == [
        ("lacma-54871", "museum", ["proposed-a", "proposed-b"])]
    truth = photos[0].truth["proposed-a"]
    assert truth["outer"].tolist() == [[16, 144], [3795, 138], [3847, 4009], [84, 3905]]
    assert truth["field"].tolist() == [[221, 336], [3606, 334], [3659, 3804], [264, 3732]]
    assert truth["bands"] == [0.1, 2.2, 0.7]
    assert truth["counts"] == (50, 50)
    # The canvas is the annotation's canvas field, [3873, 4096], which corpus/manifest.csv's
    # lacma-54871 row also gives as px_w 3873 and px_h 4096.
    assert photos[0].canvas == (3873, 4096)
    # The holdout row is counted without its name; row 3 has no frame to read.
    assert skipped == [{"stem": None, "tier": "museum", "reason": "holdout"},
                       {"stem": "bare", "tier": "museum", "reason": "no frame and counts claims"}]


def _written_photo(tmp_path: Path, canvas: tuple[int, int]) -> "b1b.Photo":
    # A 1600 x 1200 photo: the backdrop, with a checkerboard quilt of 60 px squares painted on
    # pixels x 200 to 1399 and y 150 to 1049, so its edges are x = 200 and 1400 and y = 150 and
    # 1050, and it is 1200 / 60 = 20 squares across and 900 / 60 = 15 down. PNG keeps every
    # pixel as built.
    lab = np.empty((1200, 1600, 3), np.float32)
    lab[...] = BACKDROP
    lab[150:1050, 200:1400] = _checker_lab(900, 1200, 60)
    cv2.imwrite(str(tmp_path / "scene.png"), _lab_to_bgr(lab))
    outer = np.array([[200.0, 150.0], [1400.0, 150.0], [1400.0, 1050.0], [200.0, 1050.0]])
    truth = {"outer": outer, "field": outer.copy(), "bands": [], "counts": (20, 15)}
    return b1b.Photo(stem="scene", tier="museum", file="images/scene.png", sha256="0" * 64,
                     canvas=canvas, truth={"proposed-a": truth})


def test_run_photo_scores_a_written_photo_end_to_end(tmp_path):
    photo = _written_photo(tmp_path, (1600, 1200))
    corners, bands = b1b.run_photo((photo, str(tmp_path)))
    report = b1b.build_report(corners, bands, [photo], [], {"stub": True})
    # The square: the field is the outer edge, 1200 / 20 = 60 px across and 900 / 15 = 60 down.
    assert [r["square_px"] for r in corners] == pytest.approx([60.0] * len(corners))
    # No bands, so no band records.
    assert bands == []
    # The bound for backdrop_hull at the phone cap. The scale is 1400 / 1600 = 1050 / 1200 =
    # 0.875. The x edges 200 and 1400 land on staged edges 175 and 1225, whole pixels: staged
    # columns 175 to 1224 are all quilt and 174 and 1225 all backdrop. The y edges 150 and
    # 1050 land on 131.25 and 918.75: staged rows 131 and 918 are 0.75 quilt, 132 to 917 all
    # quilt.
    # After the sigma 1 blur (taps 0.399, 0.242, 0.054, 0.004 from the centre out), columns
    # 174 and 1225 carry 0.242 + 0.054 + 0.004 = 0.30 of the step (12.6 units or more, over
    # 6) and 173 and 1226 carry 0.06 (at most 3.1 units, under 6); rows 130 and 919 carry
    # 0.75 x 0.242 + 0.054 + 0.004 = 0.24 (10.1 units or more, over) and 129 and 920 carry
    # 0.75 x 0.054 + 0.004 = 0.045 (at most 2.3 units, under). So the mask's outermost columns
    # are 174 and 1225 and its outermost rows 130 and 919. A corner pixel carries 0.30 x 0.24
    # = 0.07 of a step and drops out, and its neighbour along the side (0.70 x 0.24 = 0.17 of a
    # 42.2 unit step is 7.1, near the 6 unit tolerance) may too, so a hull corner's coordinate
    # is its side's outermost pixel or up to two pixels in: x 174 to 176 and 1223 to 1225, y 130
    # to 132 and 917 to 919.
    # to_source, (c + 0.5) / 0.875 - 0.5, maps those to x 198.93 to 201.21 and 1397.79 to
    # 1400.07, y 148.64 to 150.93 and 1048.07 to 1050.36. The farthest from 200, 1400, 150 and
    # 1050 are 2.21 px in x (staged 1223) and 1.93 px in y (staged 917), so every corner is
    # within sqrt(2.21^2 + 1.93^2) = 2.94 px, 2.94 / 60 = 0.049 of a square.
    bound = 0.049
    group = next(g for g in report["groups"] if (g["provenance"], g["cap"], g["method"])
                 == ("proposed-a", "phone", "backdrop_hull"))
    museum = group["museum"]
    assert (museum["photos"], museum["none"], museum["corners"]) == (1, 0, 4)
    assert museum["p90"] <= bound
    record = next(r for r in corners if (r["cap"], r["method"]) == ("phone", "backdrop_hull"))
    assert record["staged_px"] == [1400, 1050]
    assert max(record["errors"]) <= bound
    # The screenshot tier has no photos (n = 0), so the bar cannot be shown met: no go.
    assert group["screenshot"]["corners"] == 0
    assert group["go"] is False


def test_run_photo_refuses_an_image_that_is_not_the_canvas(tmp_path):
    # The annotation says 1601 x 1200 but the file is 1600 x 1200: the truth corners would be
    # scaled for another image, so the run stops before scoring anything.
    photo = _written_photo(tmp_path, (1601, 1200))
    with pytest.raises(ValueError, match="canvas"):
        b1b.run_photo((photo, str(tmp_path)))


def test_qrep_path_names_the_checkout():
    # A qrep inside the checkout prints as <checkout folder>/qrep/__init__.py; one outside it
    # prints its file name only, so no local folder above the checkout is printed.
    inside = b1b.REPO / "qrep" / "__init__.py"
    assert b1b._qrep_path(str(inside)) == f"{b1b.REPO.name}/qrep/__init__.py"
    outside = b1b.REPO.parent / "elsewhere" / "qrep" / "__init__.py"
    assert b1b._qrep_path(str(outside)) == "<outside this checkout>/__init__.py"


def test_to_staged_inverts_to_source():
    # At scale 0.5, source centre 99.5 is edge coordinate 100, staged edge 50, staged centre
    # 49.5: (99.5 + 0.5) x 0.5 - 0.5 = 49.5; and 9.5 gives (9.5 + 0.5) x 0.5 - 0.5 = 4.5.
    # to_source maps them back: (49.5 + 0.5) / 0.5 - 0.5 = 99.5 and (4.5 + 0.5) / 0.5 - 0.5 = 9.5.
    staged = b1b.to_staged(np.array([[99.5, 9.5]]), (0.5, 0.5))
    assert staged.tolist() == [[49.5, 4.5]]
    assert b1b.to_source(staged, (0.5, 0.5)).tolist() == [[99.5, 9.5]]
