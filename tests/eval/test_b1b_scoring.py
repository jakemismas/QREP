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


@pytest.mark.parametrize("method", ["backdrop_hull", "backdrop_lines", "tiered"])
@pytest.mark.parametrize("corners", [RECT, TILTED], ids=["rect", "tilted"])
def test_methods_find_a_quilt_on_a_plain_backdrop(method, corners):
    # The quilt covers the quad (to the half pixel of the warp's pixel-centre convention) on
    # a uniform backdrop 40 or more color units away. Every method separates the two:
    # - backdrop: the border ring is the backdrop alone (a MAD of 0, so the floor tolerance of
    #   6 units), the quilt is the one component off it, and its outline sits on the boundary
    #   pixels' centres, within a pixel of the edge; the 1 px blur moves the crossing by under
    #   a pixel, because 6 units is a small share of a step over 40 units.
    # - tiered: tier 1 (all four strips uniform and equal) masks every pixel over 25 BGR units
    #   from the backdrop, which is the quilt, and fits its hull to four corners.
    # Each suggested corner therefore lands within 2 px of its constructed corner.
    image = _scene((300, 400), corners)
    suggestion = b1b.METHODS[method](image)
    assert suggestion is not None
    assert np.abs(suggestion.corners - corners).max() <= 2.0
    assert 0.0 <= suggestion.confidence <= 1.0


@pytest.mark.parametrize("method", ["backdrop_hull", "backdrop_lines"])
def test_backdrop_gives_no_suggestion_when_the_quilt_runs_off_the_frame(method):
    # The quilt spans x = 100 to 400 in a 400 px wide photo, so it covers the whole right
    # border column (rows 60 to 239, 180 of 300 rows): its right edge is not in the photo.
    # The method gives no suggestion and never the full frame.
    corners = np.array([[100.0, 60.0], [400.0, 60.0], [400.0, 240.0], [100.0, 240.0]])
    assert b1b.METHODS[method](_scene((300, 400), corners)) is None


def test_backdrop_gives_no_suggestion_without_a_backdrop():
    # A checkerboard of 10 px squares over the whole 400 x 300 frame: every border strip holds
    # 20 squares of each fabric (400 / 10 = 40 across, 300 / 10 = 30 down, half each). The
    # per-channel median of an even split lies midway between the fabrics, half their
    # distance of sqrt(10^2 + 70^2 + 40^2) = 81.2 from each, so the MAD is 40.6, over the
    # 4 unit ceiling. (Were the split uneven, the median would sit on one fabric and only about
    # half the strip would be inliers, under the 0.9 floor.) No strip is uniform, so there is
    # no backdrop to segment.
    image = _lab_to_bgr(_checker_lab(300, 400, 10))
    assert b1b.backdrop_hull(image) is None
    assert b1b.backdrop_lines(image) is None


def test_tiered_maps_the_full_frame_to_no_suggestion(monkeypatch):
    # Tier 3 is rectify's last resort, the full-image quad. The spike records it as no
    # suggestion (issue #135 criterion 3: a missing suggestion is never replaced by the full
    # frame).
    full = np.array([[0.0, 0.0], [400.0, 0.0], [400.0, 300.0], [0.0, 300.0]])
    monkeypatch.setattr(b1b, "_detect_tiered", lambda image: (full, 0.0, 3, None))
    assert b1b.tiered(np.zeros((300, 400, 3), np.uint8)) is None
    # Tier 1's quad passes through with its tier.
    quad = RECT.copy()
    monkeypatch.setattr(b1b, "_detect_tiered", lambda image: (quad, 0.01, 1, None))
    suggestion = b1b.tiered(np.zeros((300, 400, 3), np.uint8))
    assert suggestion.corners.tolist() == RECT.tolist()
    assert suggestion.tier == 1
    # Its confidence is rectify's residual term, 1 - min(10 x 0.01, 1) = 0.9.
    assert suggestion.confidence == pytest.approx(0.9)


# --- Band proposals -----------------------------------------------------------------------


def _banded(size: int = 300) -> np.ndarray:
    # From every side inward: band A for depths 0 to 14 (15 px), band B for 15 to 44 (30 px),
    # then a checkerboard field of 15 px squares from 45 to 254. With 15 px squares the bands
    # are 1 and 2 squares wide, so their inner edges sit 1 and 3 squares in.
    lab = np.empty((size, size, 3), np.float32)
    lab[...] = (70.0, 10.0, 40.0)  # band A
    lab[15:size - 15, 15:size - 15] = (50.0, -30.0, 30.0)  # band B
    field = _checker_lab(size - 90, size - 90, 15)
    lab[45:size - 45, 45:size - 45] = field
    return _lab_to_bgr(lab)


def test_band_change_points_on_synthetic_bands():
    # The profile of each side is the mean color across the side's middle 60 percent (columns
    # or rows 60 to 239) at each depth, unblurred. In the field, that run is 180 px, 12 squares
    # (field columns 15 to 194), six of each fabric, so every field depth has the same mean and
    # the field adds no change point.
    # The two-window difference |mean(p[d:d + w]) - mean(p[d - w:d])| of a step at depth s
    # rises linearly to the full step at d = s and falls after, so it peaks exactly at the
    # band edges, 15 and 45, on every side. The outer edge (depth 0) is outside the search.
    image = _banded()
    outer = np.array([[0.0, 0.0], [300.0, 0.0], [300.0, 300.0], [0.0, 300.0]])
    proposals = b1b.band_proposals(image, outer)
    assert set(proposals) == {"top", "right", "bottom", "left"}
    for side in proposals.values():
        assert side == [15, 45]


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


def test_spike_needs_no_module_b6b_deletes(monkeypatch):
    # B6b deletes the qrep.vision package (plan B6b), rectify.py included. A None entry in
    # sys.modules makes any import of that name raise ImportError, so with every qrep.vision
    # module blocked the script must still load, and every method must still run. No import
    # statement anywhere in the script, inside a function or not, may name qrep.vision either.
    tree = ast.parse(Path(b1b.__file__).read_text(encoding="utf-8"))
    imported = [node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
    imported += [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                 for alias in node.names]
    assert [name for name in imported if name.startswith("qrep.vision")] == []
    blocked = ["qrep.vision", "qrep.vision.rectify", "qrep.vision.grid"]
    blocked += [name for name in sys.modules if name.startswith("qrep.vision.")]
    for name in blocked:
        monkeypatch.setitem(sys.modules, name, None)
    spec = importlib.util.spec_from_file_location("b1b_isolated", b1b.__file__)
    isolated = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "b1b_isolated", isolated)
    spec.loader.exec_module(isolated)
    # The expectation of the plain-backdrop test: every corner within 2 px.
    image = _scene((300, 400), RECT)
    for method in ("backdrop_hull", "backdrop_lines", "tiered"):
        assert np.abs(isolated.METHODS[method](image).corners - RECT).max() <= 2.0
    # And of the band test: proposals at 15 and 45 px on the top side.
    outer = np.array([[0.0, 0.0], [300.0, 0.0], [300.0, 300.0], [0.0, 300.0]])
    assert isolated.band_proposals(_banded(), outer)["top"] == [15, 45]


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
    # The holdout row is counted without its name; row 3 has no frame to read.
    assert skipped == [{"stem": None, "tier": "museum", "reason": "holdout"},
                       {"stem": "bare", "tier": "museum", "reason": "no frame and counts claims"}]


def test_qrep_path_names_the_checkout():
    # A qrep inside the checkout prints as <checkout folder>/qrep/__init__.py; one outside it
    # prints its file name only, so no local folder above the checkout is printed.
    inside = b1b.REPO / "qrep" / "__init__.py"
    assert b1b._qrep_path(str(inside)) == f"{b1b.REPO.name}/qrep/__init__.py"
    outside = b1b.REPO.parent / "elsewhere" / "qrep" / "__init__.py"
    assert b1b._qrep_path(str(outside)) == "<outside this checkout>/__init__.py"
