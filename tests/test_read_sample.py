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

Warped values follow OpenCV's bilinear map: output pixel i of a warp that
scales by s reads the source at center coordinate s(i + 0.5) - 0.5, and the
inner pixels of a 32 px square are 6..25 (centers 6.5 to 25.5, inside
0.2 x 32 = 6.4 to 25.6).
"""

import ast
from pathlib import Path

import numpy as np
import pytest

import qrep.vision.read
from qrep.contract import BorderBand, Corners, Counts, FieldFrame, OuterEdgeFrame, Point
from qrep.vision.read.diagnosis import Diagnosis
from qrep.vision.read.geometry import confirm
from qrep.vision.read.sample import (
    INSET,
    MIN_PX_PER_SQUARE,
    P,
    Squares,
    read_squares,
    to_lab,
    warp_matrix,
)

TOL = 0.01

# Gray L by hand: lin, then f(Y) = Y^(1/3), then L = 116 f - 16.
#   16: lin ((0.062745 + 0.055)/1.055)^2.4 = 0.0051815, at or below 0.008856,
#       so L = 903.3 x 0.0051815 = 4.6805
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
    16: 4.6805,
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
# A dark blue, RGB (0, 0, 40), takes the linear branch of f on two channels:
#   lin(40) = ((0.156863 + 0.055)/1.055)^2.4 = 0.021219
#   X/Xn = 0.180423 x 0.021219 / 0.950456 = 0.004028, f = 7.787 x 0.004028
#     + 0.137931 = 0.169297; Y = 0.072169 x 0.021219 = 0.0015314, f = 0.149856;
#   Z/Zn = 0.950227 x 0.021219 / 1.088754 = 0.0185192, f = 0.26457 (cube root)
#   L = 903.3 x 0.0015314 = 1.3833, a = 500 x 0.019441 = 9.7205,
#   b = 200 x -0.114714 = -22.9429
DARK_BLUE = (1.3833, 9.7205, -22.9429)
# BGR, the order cv2 decodes a photo in.
BGR = {"red": (0, 0, 255), "green": (0, 255, 0), "blue": (255, 0, 0), "dark_blue": (40, 0, 0)}


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


def outer_frame(width, height, *bands) -> OuterEdgeFrame:
    return OuterEdgeFrame(
        kind="outer_edge",
        corners=corners((0, 0), (width, 0), (width, height), (0, height)),
        bands=[BorderBand(width_squares=w) for w in bands],
    )


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


def test_to_lab_follows_the_formulas():
    # The hand-worked values above, through the read's own conversion; gray 16
    # and the dark blue pin the linear branches of L and of f.
    fills = [0, 16, 32, 128, 255]
    pixels = np.array(
        [
            [(v, v, v) for v in fills]
            + [BGR[name] for name in ("red", "green", "blue", "dark_blue")]
        ],
        dtype=np.uint8,
    )
    lab = to_lab(pixels)
    assert lab.dtype == np.float32
    expected = [gray(v) for v in fills] + [RED, GREEN, BLUE, DARK_BLUE]
    for got, want in zip(lab[0], expected, strict=True):
        assert_lab(got, want, tol=0.001)


def test_each_solid_square_samples_its_own_fill_exactly():
    # Source: plan B2a, the synthetic 4 x 3 grid of solid 40 px squares.
    # 40 px per square is under 2P = 64, so no downsample; the warp makes
    # each square 32 px, and its inner pixels 6..25 read source x =
    # (i + 0.5) x 40/32 - 0.5, so 7.625..31.375: pixels 7..32 of the square's
    # 0..39, all one fill.
    result = sample(four_by_three_image(), rect_field(10, 20, 170, 140), counts(4, 3))
    assert isinstance(result, Squares)
    assert result.lab.shape == (3, 4, 3)
    assert result.spread.shape == (3, 4, 3)
    assert result.downsample == (1.0, 1.0)
    assert result.field_bgr.shape == (3 * 32, 4 * 32, 3)
    for r, row in enumerate(FILLS):
        for c, fill in enumerate(row):
            assert_lab(result.lab[r, c], lab_of(fill))
            assert_lab(result.spread[r, c], (0.0, 0.0, 0.0))


def test_each_square_of_a_perspective_grid_samples_its_own_fill():
    # The 4 x 3 fills drawn through the hand-built homography of
    # test_read_geometry.py: x = 8 + 240u / (4 + u), y = 8 + 160v / (4 + u)
    # for u in 0..4, v in 0..3, corners (8, 8), (128, 8), (128, 68), (8, 128).
    # The narrowest squares, in the right column, run x 8 + 720/7 = 110.86 to
    # 128; the 0.2 inset ends at u = 3.8, x = 8 + 912/7.8 = 124.92, so every
    # sample stays at least 3.0 px inside the drawn edges, which
    # fillConvexPoly places within 1 px: every square reads its own fill.
    import cv2

    def point(u, v):
        return (8 + 240 * u / (4 + u), 8 + 160 * v / (4 + u))

    image = np.full((140, 140, 3), (40, 200, 120), dtype=np.uint8)
    for r, row in enumerate(FILLS):
        for c, fill in enumerate(row):
            quad = [point(c, r), point(c + 1, r), point(c + 1, r + 1), point(c, r + 1)]
            # 4 fractional bits keep the drawn corners within 1/16 px.
            vertices = np.round(np.array(quad) * 16).astype(np.int32)
            cv2.fillConvexPoly(image, vertices, bgr(fill), shift=4)
    frame = FieldFrame(kind="field", corners=corners((8, 8), (128, 8), (128, 68), (8, 128)))
    result = sample(image, frame, counts(4, 3))
    for r, row in enumerate(FILLS):
        for c, fill in enumerate(row):
            assert_lab(result.lab[r, c], lab_of(fill))


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


def test_the_inset_is_a_fifth_of_the_square_on_each_side():
    # One 32 px square read at 32 px per square, so the warp is the identity.
    # Columns 11..20 are black, the rest white. Inset 0.2 keeps columns 6..25:
    # 10 white (6..10, 21..25) and 10 black, 200 pixels each, so the median
    # is (0 + 100) / 2 = 50 and every pixel lies 50 from it. Inset 0.3 would
    # keep columns 10..21 (10 black, 2 white: L 0), inset 0.1 columns 3..28
    # (16 white, 10 black: L 100).
    image = np.full((32, 32, 3), 255, dtype=np.uint8)
    image[:, 11:21] = 0
    result = sample(image, rect_field(0, 0, 32, 32), counts(1, 1))
    assert_lab(result.lab[0, 0], (50.0, 0.0, 0.0))
    assert_lab(result.spread[0, 0], (50.0, 0.0, 0.0))


def test_the_spread_is_the_median_absolute_deviation():
    # One 32 px square read at the identity. The inner rows 6..25 are rows
    # 6..15 of gray 64 and rows 16..25 of gray 192, 200 pixels each. The
    # median of an even count averages the two middle values: L (27.0934 +
    # 77.7044) / 2 = 52.3989. Every pixel is (77.7044 - 27.0934) / 2 = 25.3055
    # from it, so the spread is 25.3055.
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    image[:16] = 64
    image[16:] = 192
    result = sample(image, rect_field(0, 0, 32, 32), counts(1, 1))
    assert_lab(result.lab[0, 0], (52.3989, 0.0, 0.0))
    assert_lab(result.spread[0, 0], (25.3055, 0.0, 0.0))


def test_the_sample_is_a_median_not_a_mean():
    # As above, but rows 6..17 are gray 64 (12 rows x 20 = 240 pixels) and rows
    # 18..25 gray 192 (160 pixels). Both middle values (the 200th and 201st)
    # are gray 64, so the median is L 27.0934, and 240 of the 400 deviations
    # are 0, so the spread is 0. A mean would give (240 x 27.0934 + 160 x
    # 77.7044) / 400 = 47.3378, and a standard deviation would not be 0.
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    image[:18] = 64
    image[18:] = 192
    result = sample(image, rect_field(0, 0, 32, 32), counts(1, 1))
    assert_lab(result.lab[0, 0], gray(64))
    assert_lab(result.spread[0, 0], (0.0, 0.0, 0.0))


def test_a_large_field_is_area_downsampled_before_the_warp():
    # Source: plan B2a criterion 5 (exp0: warpPerspective ignores INTER_AREA).
    # Two 256 px squares whose columns repeat black, white, white, black.
    # Every square side is 256 px, over 2P = 64, so the read first scales by
    # 64 / 256 = 0.25 with INTER_AREA: each output pixel averages a 4 x 4
    # block holding one period, two black and two white columns, so
    # (2 x 0 + 2 x 255) / 4 = 127.5, stored as 128. The 2x warp of that
    # uniform gray keeps 128: L 53.5850. Other paths read otherwise:
    #   INTER_LINEAR at 0.25 samples x = 4k + 1.5, between the white columns
    #   4k + 1 and 4k + 2: L 100.
    #   INTER_NEAREST takes column 4k, black: L 0.
    #   A direct 8x warp samples x = 8i + 3.5, between the black columns
    #   8i + 3 and 8i + 4: L 0.
    image = np.zeros((256, 512, 3), dtype=np.uint8)
    image[:, 1::4] = 255
    image[:, 2::4] = 255
    result = sample(image, rect_field(0, 0, 512, 256), counts(2, 1))
    assert result.downsample == (0.25, 0.25)
    for c in range(2):
        assert_lab(result.lab[0, c], gray(128))


def test_each_axis_downsamples_on_its_own():
    # A 2 x 2 grid over 256 x 32 px: squares 128 px wide and 16 px tall, as
    # a field seen at a grazing angle. Along x the largest square is 128 px,
    # so 64 / 128 = 0.5 (and P / 128 = 0.25 is smaller); along y it is 16 px,
    # under 2P, so 1. One scale for both axes would cut the squares to 8 px
    # tall. After the halving each square is 64 x 16 px of one fill, and the
    # warp reads inner x = 2i + 0.5 (12.5..50.5) and y = 0.5j - 0.25
    # (2.75..12.25 in square row 0), inside each fill.
    image = np.zeros((32, 256, 3), dtype=np.uint8)
    image[:16, :128] = 32
    image[:16, 128:] = 96
    image[16:, :128] = 160
    image[16:, 128:] = 224
    result = sample(image, rect_field(0, 0, 256, 32), counts(2, 2))
    assert result.downsample == (0.5, 1.0)
    assert_lab(result.lab[0, 0], gray(32))
    assert_lab(result.lab[0, 1], gray(96))
    assert_lab(result.lab[1, 0], gray(160))
    assert_lab(result.lab[1, 1], gray(224))


def test_the_warp_matrix_maps_pixel_centers():
    # A 40 px square warped to 32 px: on pixel edges the map is x = 1.25u,
    # y = 1.25v. warpPerspective works on centers, so output center i, at
    # edge i + 0.5, reads edge 1.25 (i + 0.5), center 1.25i + 0.625 - 0.5 =
    # 1.25i + 0.125, on both axes.
    m = warp_matrix(((0, 0), (40, 0), (40, 40), (0, 40)), 32, 32)
    assert m == pytest.approx(np.array([[1.25, 0, 0.125], [0, 1.25, 0.125], [0, 0, 1]]))


def test_the_warp_samples_where_the_matrix_says():
    # Columns 0 and 1 of a 40 px square are black, the rest white. Output
    # column 1 reads source x = 1.25 + 0.125 = 1.375, three eighths of the way
    # from black column 1 to white column 2: 0.375 x 255 = 95.6, which
    # OpenCV's fixed-point bilinear rounds to 96. Without the half-pixel shift
    # it would read x = 1.25 (63.75, so 64); shifted the wrong way, x = 1.125
    # (31.9, so 32). The same holds for rows.
    across = np.full((40, 40, 3), 255, dtype=np.uint8)
    across[:, :2] = 0
    result = sample(across, rect_field(0, 0, 40, 40), counts(1, 1))
    assert np.all(result.field_bgr[:, 1] == 96)
    down = np.full((40, 40, 3), 255, dtype=np.uint8)
    down[:2] = 0
    result = sample(down, rect_field(0, 0, 40, 40), counts(1, 1))
    assert np.all(result.field_bgr[1] == 96)


def test_band_strips_are_sampled_side_by_side_and_band_by_band():
    # Counts 4 x 3 and bands of 0.5 then 1.5 squares: 8 x 7 squares at 20 px.
    # Band 0 (0 to 10 px in) has a fill per side and black corners; band 1
    # (10 to 40 px in) is gray 64; the field is gray 128. Each strip leaves
    # out its band's corners and samples its inner region, so each side reads
    # its own fill exactly. Band 0's top strip warps to 7 x 32 by 0.5 x 32 =
    # 224 x 16 px; its inner rows 3..12 read y = (j + 0.5) x 10/16 - 0.5 =
    # 1.69..7.31 and its inner columns 3..220 read x = 10 + (i + 0.5) x
    # 140/224 - 0.5 = 11.69..147.31, all red. Reversed or averaged bands would
    # put band 0's strip over gray 64.
    image = np.zeros((140, 160, 3), dtype=np.uint8)
    image[10:130, 10:150] = 64
    image[40:100, 40:120] = 128
    image[0:10, 10:150] = BGR["red"]
    image[10:130, 150:160] = BGR["green"]
    image[130:140, 10:150] = BGR["blue"]
    image[10:130, 0:10] = 255
    result = sample(image, outer_frame(160, 140, 0.5, 1.5), counts(4, 3))
    strips = {(s.band, s.side): s for s in result.strips}
    assert len(strips) == 8
    assert_lab(strips[(0, "top")].lab, RED)
    assert_lab(strips[(0, "right")].lab, GREEN)
    assert_lab(strips[(0, "bottom")].lab, BLUE)
    assert_lab(strips[(0, "left")].lab, gray(255))
    for side in ("top", "right", "bottom", "left"):
        assert_lab(strips[(0, side)].spread, (0.0, 0.0, 0.0))
        assert_lab(strips[(1, side)].lab, gray(64))
        assert_lab(strips[(1, side)].spread, (0.0, 0.0, 0.0))
    for r in range(3):
        for c in range(4):
            assert_lab(result.lab[r, c], gray(128))


def test_a_strip_is_inset_a_fifth_of_its_band_width():
    # Counts 1 x 1 and one band of 1 square, at 32 px per square: band 0's top
    # strip is x 32..64, y 0..32, warped by the identity to 32 x 32 px. Its
    # rows 11..20 are black, the rest white. The inset across the band is
    # 0.2 x 32 = 6.4 px, so rows 6..25: 10 black and 10 white, median 50 and
    # spread 50. No inset would keep rows 0..31 (22 white: L 100); inset 0.3
    # rows 10..21 (10 black, 2 white: L 0).
    image = np.full((96, 96, 3), 255, dtype=np.uint8)
    image[11:21, 32:64] = 0
    result = sample(image, outer_frame(96, 96, 1.0), counts(1, 1))
    top = next(s for s in result.strips if (s.band, s.side) == (0, "top"))
    assert_lab(top.lab, (50.0, 0.0, 0.0))
    assert_lab(top.spread, (50.0, 0.0, 0.0))


def test_a_wide_band_beside_a_short_field_still_samples_its_strips():
    # A runner: counts 12 x 1 and one band of 2.5 squares, so 17 x 6 squares
    # at 8 px over 136 x 48 px. The left and right strips are 1 square long
    # and 2.5 wide: 80 x 32 px warped. Across the band the inset is 0.2 x 2.5
    # x 32 = 16 px (columns 16..63); along the strip it is capped at a fifth
    # of its length, 0.2 x 1 x 32 = 6.4 px (rows 6..25), so the sample is not
    # empty. Columns read x = (i + 0.5) x 20/80 - 0.5 = 3.63..15.38, rows
    # y = 20 + (j + 0.5) x 8/32 - 0.5 = 21.13..25.88: all band gray 64.
    image = np.full((48, 136, 3), 64, dtype=np.uint8)
    image[20:28, 20:116] = 128
    result = sample(image, outer_frame(136, 48, 2.5), counts(12, 1))
    for strip in result.strips:
        assert_lab(strip.lab, gray(64))
        assert_lab(strip.spread, (0.0, 0.0, 0.0))
    assert_lab(result.lab[0, 11], gray(128))


def test_too_few_pixels_reports_the_measured_pixels_per_square():
    # Source: plan B2a criterion 7. A 20 x 20 grid over 120 x 120 px: every
    # square side is 120 / 20 = 6 px, under the floor of 7.
    image = np.full((120, 120, 3), 128, dtype=np.uint8)
    result = sample(image, rect_field(0, 0, 120, 120), counts(20, 20))
    assert isinstance(result, Diagnosis)
    assert result.code == "too_few_pixels"
    assert result.pixels_per_square == pytest.approx(6.0)


def test_the_floor_sees_the_smallest_square_under_perspective():
    # The trapezoid of test_read_geometry.py scaled by 0.375 about its corner
    # and moved to (3, 3): x = 3 + 90u / (4 + u), y = 3 + 60v / (4 + u), so
    # corners (3, 3), (48, 3), (48, 25.5), (3, 48). Its shortest square side,
    # the top of square (0, 3), is x(4) - x(3) = 45 - 270/7 = 45/7 = 6.428571,
    # under 7, although every edge averages at least 22.5 / 3 = 7.5 px.
    image = np.full((52, 52, 3), 128, dtype=np.uint8)
    frame = FieldFrame(kind="field", corners=corners((3, 3), (48, 3), (48, 25.5), (3, 48)))
    result = sample(image, frame, counts(4, 3))
    assert isinstance(result, Diagnosis)
    assert result.code == "too_few_pixels"
    assert result.pixels_per_square == pytest.approx(45 / 7)


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
