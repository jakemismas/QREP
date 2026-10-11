"""The confirmed read's sampling (ticket B2a): downsample, warp, and the
median float CIELAB of each square's inner 60 percent.

Expected colors are worked by hand from the sRGB to CIELAB formulas with
the D65 constants OpenCV uses (plain arithmetic, no cv2):
  lin(v) = v/12.92 if v <= 0.04045, else ((v + 0.055)/1.055)^2.4, v = c/255
  X = 0.412453R + 0.357580G + 0.180423B, Y = 0.212671R + 0.715160G + 0.072169B,
  Z = 0.019334R + 0.119193G + 0.950227B; Xn = 0.950456, Zn = 1.088754
  f(t) = t^(1/3) for t > 0.008856, else 7.787t + 16/116
  L = 116 f(Y) - 16 (903.3 Y at or below 0.008856), a = 500 (f(X/Xn) - f(Y)),
  b = 200 (f(Y) - f(Z/Zn))
For a gray the matrix rows sum to Xn, 1 and Zn, so X/Xn = Y = Z/Zn and
a = b = 0. Tolerances cover float32 rounding only.
"""

import ast
from pathlib import Path

import numpy as np
import pytest

from qrep.contract import BorderBand, Corners, Counts, FieldFrame, OuterEdgeFrame, Point
import qrep.vision.read
from qrep.vision.read.diagnosis import Diagnosis
from qrep.vision.read.geometry import confirm
from qrep.vision.read.sample import INSET, MIN_PX_PER_SQUARE, P, Squares, read_squares, to_lab

TOL = 0.01

# Gray L by hand: lin, then f(Y) = Y^(1/3), then L = 116 f - 16.
#   32: lin 0.014444, f 0.243535, L 12.2500
#   64: lin 0.051269, f 0.371495, L 27.0934
#   96: lin 0.116971, f 0.489056, L 40.7305
#  128: lin 0.215861, f 0.599871, L 53.5850
#  160: lin 0.351533, f 0.705757, L 65.8678
#  192: lin 0.527115, f 0.807796, L 77.7044
#  224: lin 0.745404, f 0.906701, L 89.1773
#  255: lin 1, f 1, L 100; 0: Y 0, L 0
GRAY_L = {
    0: 0.0,
    32: 12.2500,
    64: 27.0934,
    96: 40.7305,
    128: 53.5850,
    160: 65.8678,
    192: 77.7044,
    224: 89.1773,
    255: 100.0,
}
# Primaries by hand (lin of 255 is 1, of 0 is 0, so XYZ is one matrix column):
#   red   XYZ (0.412453, 0.212671, 0.019334), f (0.757090, 0.596902, 0.260894)
#         L 116 x 0.596902 - 16 = 53.2406, a 500 x 0.160188 = 80.0942,
#         b 200 x 0.336008 = 67.2015
#   green XYZ (0.357580, 0.715160, 0.119193), f (0.721906, 0.894268, 0.478381)
#         L 87.7351, a 500 x -0.172362 = -86.1813, b 200 x 0.415887 = 83.1775
#   blue  XYZ (0.180423, 0.072169, 0.950227), f (0.574716, 0.416342, 0.955651)
#         L 32.2957, a 500 x 0.158374 = 79.1870, b 200 x -0.539309 = -107.8617
RED = (53.2406, 80.0942, 67.2015)
GREEN = (87.7351, -86.1813, 83.1775)
BLUE = (32.2957, 79.1870, -107.8617)
# BGR, the order cv2 decodes a photo in.
BGR = {"red": (0, 0, 255), "green": (0, 255, 0), "blue": (255, 0, 0)}


def gray(level):
    return (GRAY_L[level], 0.0, 0.0)


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


def sample(image, frame, grid):
    height, width = image.shape[:2]
    geometry = confirm(frame, grid, (width, height), Point(x=0, y=0), corners_source="user")
    return read_squares(image, geometry)


def rect_field(x0, y0, x1, y1) -> FieldFrame:
    return FieldFrame(kind="field", corners=corners((x0, y0), (x1, y0), (x1, y1), (x0, y1)))


def assert_lab(got, want, tol=TOL):
    assert tuple(float(v) for v in got) == pytest.approx(want, abs=tol)


# The 4 x 3 grid's fills, row by row, and their hand-worked CIELAB.
FILLS = [
    [("gray", 0), ("gray", 32), ("gray", 64), ("gray", 96)],
    [("gray", 128), ("gray", 160), ("gray", 192), ("gray", 224)],
    [("gray", 255), ("red", None), ("green", None), ("blue", None)],
]
EXPECTED = {"red": RED, "green": GREEN, "blue": BLUE}


def bgr(fill):
    kind, level = fill
    return (level, level, level) if kind == "gray" else BGR[kind]


def lab_of(fill):
    kind, level = fill
    return gray(level) if kind == "gray" else EXPECTED[kind]


def four_by_three_image():
    """Solid 40 px squares at offset (10, 20) in a 200 x 180 image whose
    margin is a color no square uses."""
    image = np.full((180, 200, 3), (40, 200, 120), dtype=np.uint8)
    for r, row in enumerate(FILLS):
        for c, fill in enumerate(row):
            image[20 + 40 * r : 60 + 40 * r, 10 + 40 * c : 50 + 40 * c] = bgr(fill)
    return image


def test_the_knobs_are_the_plan_values():
    # Plan B2a: P = 32 and inset 0.2 (the prototype values, provisional);
    # the floor 7 px per square (exp3, provisional).
    assert (P, INSET, MIN_PX_PER_SQUARE) == (32, 0.2, 7)


def test_each_solid_square_samples_its_own_fill_exactly():
    # Source: plan B2a, the synthetic 4 x 3 grid of solid 40 px squares.
    # 40 px per square is under 2P = 64, so no downsample; the warp makes
    # each square 32 px, whose inner pixels 6..25 (centers 6.5..25.5, inside
    # 0.2 x 32 = 6.4 to 25.6) sample source x = (i + 0.5) x 40/32 - 0.5, so
    # 7.625..31.375: pixels 7..32 of the square's 0..39, all one fill.
    result = sample(four_by_three_image(), rect_field(10, 20, 170, 140), counts(4, 3))
    assert isinstance(result, Squares)
    assert result.lab.shape == (3, 4, 3)
    assert result.spread.shape == (3, 4, 3)
    assert result.downsample == 1.0
    assert result.field_lab.shape == (3 * 32, 4 * 32, 3)
    for r, row in enumerate(FILLS):
        for c, fill in enumerate(row):
            assert_lab(result.lab[r, c], lab_of(fill))
            assert_lab(result.spread[r, c], (0.0, 0.0, 0.0))


def test_the_inset_keeps_the_seam_frame_out_of_the_sample():
    # A 2 x 2 grid of 40 px squares, each a white fill inside a 6 px black
    # frame (square pixels 0..5 and 34..39). The sample reads pixels 7..32
    # (above), so only white: L 100. The frame covers 1 - (28/40)^2 = 51
    # percent of each square, so a median without the inset reads black.
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    for r in range(2):
        for c in range(2):
            image[40 * r + 6 : 40 * r + 34, 40 * c + 6 : 40 * c + 34] = 255
    result = sample(image, rect_field(0, 0, 80, 80), counts(2, 2))
    for r in range(2):
        for c in range(2):
            assert_lab(result.lab[r, c], gray(255))
            assert_lab(result.spread[r, c], (0.0, 0.0, 0.0))


def test_the_spread_is_the_median_absolute_deviation():
    # One 32 px square read at 32 px per square: the warp is the identity, so
    # the inner rows 6..25 are rows 6..15 of gray 64 and rows 16..25 of gray
    # 192, 200 pixels each. The median of an even count averages the two
    # middle values: L (27.0934 + 77.7044) / 2 = 52.3989. Every pixel is
    # (77.7044 - 27.0934) / 2 = 25.3055 from it, so the spread is 25.3055.
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    image[:16] = 64
    image[16:] = 192
    result = sample(image, rect_field(0, 0, 32, 32), counts(1, 1))
    assert_lab(result.lab[0, 0], (52.3989, 0.0, 0.0))
    assert_lab(result.spread[0, 0], (25.3055, 0.0, 0.0))


def test_a_large_field_is_area_downsampled_before_the_warp():
    # Source: plan B2a criterion 5 (exp0: warpPerspective ignores INTER_AREA).
    # Two 128 px squares whose columns repeat black, white, white, black.
    # 128 px is over 2P = 64, so the read first halves the image with
    # INTER_AREA: output column k averages source columns 2k and 2k + 1, a
    # black and a white for every k, so (0 + 255) / 2 = 127.5, stored as 128.
    # The 2x warp of that uniform gray keeps 128: L 53.5850.
    # A direct warp from 128 to 32 px would sample x = 4i + 1.5, between the
    # two white columns 4i + 1 and 4i + 2: L 100.
    image = np.zeros((128, 256, 3), dtype=np.uint8)
    image[:, 1::4] = 255
    image[:, 2::4] = 255
    result = sample(image, rect_field(0, 0, 256, 128), counts(2, 1))
    assert result.downsample == pytest.approx(0.5)
    for c in range(2):
        assert_lab(result.lab[0, c], gray(128))


def test_band_strips_are_sampled_side_by_side_and_band_by_band():
    # Counts 4 x 3 and two bands of 1 square: 8 x 7 squares at 20 px. Band 0
    # (outermost) has a fill per side and black corners; band 1 is gray 64;
    # the field is gray 128. Each strip leaves out its band's corners and
    # samples its inner region (inset 0.2 of the band width on every side),
    # so each side reads its own fill exactly.
    image = np.zeros((140, 160, 3), dtype=np.uint8)
    image[0:20, 20:140] = BGR["red"]
    image[20:120, 140:160] = BGR["green"]
    image[120:140, 20:140] = BGR["blue"]
    image[20:120, 0:20] = 255
    image[20:120, 20:140] = 64
    image[40:100, 40:120] = 128
    frame = OuterEdgeFrame(
        kind="outer_edge",
        corners=corners((0, 0), (160, 0), (160, 140), (0, 140)),
        bands=[BorderBand(width_squares=1.0), BorderBand(width_squares=1.0)],
    )
    result = sample(image, frame, counts(4, 3))
    strips = {(s.band, s.side): s for s in result.strips}
    assert len(strips) == 8
    assert_lab(strips[(0, "top")].lab, RED)
    assert_lab(strips[(0, "right")].lab, GREEN)
    assert_lab(strips[(0, "bottom")].lab, BLUE)
    assert_lab(strips[(0, "left")].lab, gray(255))
    for side in ("top", "right", "bottom", "left"):
        assert_lab(strips[(1, side)].lab, gray(64))
        assert_lab(strips[(1, side)].spread, (0.0, 0.0, 0.0))
    for r in range(3):
        for c in range(4):
            assert_lab(result.lab[r, c], gray(128))


def test_too_few_pixels_reports_the_measured_pixels_per_square():
    # Source: plan B2a criterion 7. A 20 x 20 grid over 120 x 120 px: every
    # edge is 120 / 20 = 6 px per square, under the floor of 7.
    image = np.full((120, 120, 3), 128, dtype=np.uint8)
    result = sample(image, rect_field(0, 0, 120, 120), counts(20, 20))
    assert isinstance(result, Diagnosis)
    assert result.code == "too_few_pixels"
    assert result.pixels_per_square == pytest.approx(6.0)


def test_the_floor_itself_reads():
    # 140 / 20 = 7 px per square: not fewer than 7, so the read goes on.
    image = np.full((140, 140, 3), 128, dtype=np.uint8)
    result = sample(image, rect_field(0, 0, 140, 140), counts(20, 20))
    assert isinstance(result, Squares)
    assert result.lab.shape == (20, 20, 3)
    assert_lab(result.lab[19, 19], gray(128))


def test_an_image_that_does_not_match_the_geometry_is_refused():
    geometry = confirm(
        rect_field(0, 0, 32, 32), counts(1, 1), (32, 32), Point(x=0, y=0), corners_source="user"
    )
    with pytest.raises(ValueError, match="image"):
        read_squares(np.zeros((40, 32, 3), dtype=np.uint8), geometry)
    with pytest.raises(ValueError, match="image"):
        read_squares(np.zeros((32, 32), dtype=np.uint8), geometry)


def test_the_read_imports_cv2_only_inside_functions():
    # Plan B2a criterion 9. No module of the read imports cv2 at import time:
    # every cv2 import sits inside a function. The parent package qrep.vision
    # still imports the old pipeline, and cv2 with it, until B6b removes it.
    folder = Path(qrep.vision.read.__file__).parent
    modules = sorted(folder.glob("*.py"))
    assert {m.name for m in modules} >= {"__init__.py", "diagnosis.py", "geometry.py", "sample.py"}
    lazy = 0
    for module in modules:
        tree = ast.parse(module.read_text(encoding="utf-8"))
        for node in tree.body:
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else []
            if isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert not any(n.split(".")[0] == "cv2" for n in names), module.name
        lazy += sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.Import) and any(a.name == "cv2" for a in node.names)
        )
    # sample.py reads pixels, so it imports cv2 once, inside read_squares.
    assert lazy == 1


def test_to_lab_follows_the_formulas():
    # The hand-worked values above, through the read's own conversion.
    pixels = np.array(
        [
            [
                [0, 0, 0],
                [32, 32, 32],
                [128, 128, 128],
                [255, 255, 255],
                BGR["red"],
                BGR["green"],
                BGR["blue"],
            ]
        ],
        dtype=np.uint8,
    )
    lab = to_lab(pixels)
    assert lab.dtype == np.float32
    for got, want in zip(
        lab[0], [gray(0), gray(32), gray(128), gray(255), RED, GREEN, BLUE], strict=True
    ):
        assert_lab(got, want, tol=0.001)


def test_each_square_of_a_perspective_grid_samples_its_own_fill():
    # The 4 x 3 fills drawn through the hand-built homography of
    # test_read_geometry.py: x = 8 + 240u / (4 + u), y = 8 + 160v / (4 + u)
    # for u in 0..4, v in 0..3, corners (8, 8), (128, 8), (128, 68), (8, 128).
    # The smallest squares, in the right column, run x 8 + 720/7 = 110.86 to
    # 128 (17.14 px) and are 160/8 = 20 to 160/7 = 22.86 px tall, so the 0.2
    # inset keeps each sample at least 3.4 px inside the drawn edges, which
    # fillConvexPoly places within 1 px: every square reads its own fill.
    import cv2

    def point(u, v):
        return (8 + 240 * u / (4 + u), 8 + 160 * v / (4 + u))

    image = np.full((140, 140, 3), (40, 200, 120), dtype=np.uint8)
    for r, row in enumerate(FILLS):
        for c, fill in enumerate(row):
            quad = [point(c, r), point(c + 1, r), point(c + 1, r + 1), point(c, r + 1)]
            # 4 fractional bits keep the drawn corners within 1/16 px.
            cv2.fillConvexPoly(
                image, np.round(np.array(quad) * 16).astype(np.int32), bgr(fill), shift=4
            )
    frame = FieldFrame(kind="field", corners=corners((8, 8), (128, 8), (128, 68), (8, 128)))
    result = sample(image, frame, counts(4, 3))
    for r, row in enumerate(FILLS):
        for c, fill in enumerate(row):
            assert_lab(result.lab[r, c], lab_of(fill))
