"""The confirmed read's geometry (ticket B2a): frame validation, counts,
homographies, the field derived from the outer edge and its bands.

Coordinates are pixel edges: the image spans [0, W] x [0, H], and pixel
(i, j) covers [i, i + 1) x [j, j + 1), as the renderer's sidecar corners do.
"""

import math

import pytest

from qrep.contract import BorderBand, Corners, Counts, FieldFrame, OuterEdgeFrame, Point
from qrep.vision.read.diagnosis import CODES, Diagnosis
from qrep.vision.read.geometry import Geometry, confirm


def corners(tl, tr, br, bl) -> Corners:
    return Corners(
        top_left=Point(x=tl[0], y=tl[1]),
        top_right=Point(x=tr[0], y=tr[1]),
        bottom_right=Point(x=br[0], y=br[1]),
        bottom_left=Point(x=bl[0], y=bl[1]),
    )


def field(tl, tr, br, bl) -> FieldFrame:
    return FieldFrame(kind="field", corners=corners(tl, tr, br, bl))


def outer(tl, tr, br, bl, *widths) -> OuterEdgeFrame:
    bands = [BorderBand(width_squares=w) for w in widths]
    return OuterEdgeFrame(kind="outer_edge", corners=corners(tl, tr, br, bl), bands=bands)


# 2 blocks of 2 squares across and 3 blocks of 1 square down: a 4 x 3 grid.
FOUR_BY_THREE = Counts(
    blocks_across=2, blocks_down=3, squares_per_block_across=2, squares_per_block_down=1
)
# The 4 x 3 grid of 40 px squares at offset (10, 20) in a 200 x 180 image.
GRID_40 = field((10, 20), (170, 20), (170, 140), (10, 140))
NO_OFFSET = Point(x=0, y=0)


def read(frame, counts=FOUR_BY_THREE, size=(200, 180), offset=NO_OFFSET, source="user"):
    return confirm(frame, counts, size, offset, corners_source=source)


def approx_quad(quad, expected, tol=1e-6):
    assert len(quad) == 4
    for got, want in zip(quad, expected, strict=True):
        assert got == pytest.approx(want, abs=tol)


def test_counts_give_rows_cols_and_the_block_size():
    # Source: plan B2a criterion 1, counts in quilter units.
    # cols = blocks_across x squares_per_block_across = 2 x 2 = 4
    # rows = blocks_down x squares_per_block_down = 3 x 1 = 3
    # block size: 1 square down by 2 across
    geometry = read(GRID_40)
    assert isinstance(geometry, Geometry)
    assert (geometry.rows, geometry.cols) == (3, 4)
    assert (geometry.block_rows, geometry.block_cols) == (1, 2)
    assert (geometry.blocks_down, geometry.blocks_across) == (3, 2)


def test_every_confirmed_value_is_recorded_at_confidence_one():
    # CLAUDE.md and plan section 2.2: user-confirmed corners, counts and bands
    # are user facts at 1.0; nothing here comes from the pixels.
    geometry = read(outer((8, 8), (248, 8), (248, 208), (8, 208), 1.0), size=(256, 216))
    assert geometry.confidence == 1.0
    assert geometry.counts == FOUR_BY_THREE
    assert geometry.frame.kind == "outer_edge"
    assert [band.width_squares for band in geometry.frame.bands] == [1.0]
    with pytest.raises(ValueError, match="confidence 1.0"):
        Geometry(**{**geometry.__dict__, "confidence": 0.875})


@pytest.mark.parametrize("source", ["user", "suggestion"])
def test_the_result_records_who_set_the_corners(source):
    # data-48: evaluation separates corner error from read error.
    assert read(GRID_40, source=source).corners_source == source


def test_an_unknown_corner_source_is_refused():
    with pytest.raises(ValueError, match="corners_source"):
        read(GRID_40, source="guess")


def test_square_centers_follow_the_homography_of_an_axis_aligned_field():
    # Source: plan B2a, the synthetic 4 x 3 grid of solid 40 px squares.
    # The field spans x 10..170 and y 20..140, so the map from the squares'
    # plane is x = 10 + 40u, y = 20 + 40v, and square (r, c) has its center
    # at u = c + 0.5, v = r + 0.5: x = 10 + 40c + 20, y = 20 + 40r + 20.
    # Square (2, 3): x = 10 + 120 + 20 = 150, y = 20 + 80 + 20 = 120.
    centers = read(GRID_40).square_centers()
    assert centers.shape == (3, 4, 2)
    for r in range(3):
        for c in range(4):
            assert tuple(centers[r, c]) == pytest.approx((30 + 40 * c, 40 + 40 * r), abs=1e-9)
    assert tuple(centers[2, 3]) == pytest.approx((150, 120), abs=1e-9)


def test_square_centers_follow_a_perspective_homography():
    # A hand-built homography from the squares' plane (u in 0..4, v in 0..3):
    #   x = 8 + 60u / (1 + u/4) = 8 + 240u / (4 + u)
    #   y = 8 + 40v / (1 + u/4) = 8 + 160v / (4 + u)
    # Its corners: (0, 0) -> (8, 8); (4, 0) -> 8 + 960/8 = 128, so (128, 8);
    # (4, 3) -> (128, 8 + 480/8) = (128, 68); (0, 3) -> (8, 8 + 480/4) = (8, 128).
    # Four corners fix a homography, so the read's must equal this one.
    # Square (1, 3): u = 3.5, v = 1.5: x = 8 + 840/7.5 = 120, y = 8 + 240/7.5 = 40.
    # Square (0, 0): u = v = 0.5: x = 8 + 120/4.5 = 34.6667, y = 8 + 80/4.5 = 25.7778.
    trapezoid = field((8, 8), (128, 8), (128, 68), (8, 128))
    centers = read(trapezoid).square_centers()
    assert tuple(centers[1, 3]) == pytest.approx((120, 40), abs=1e-9)
    assert tuple(centers[0, 0]) == pytest.approx((34.666667, 25.777778), abs=1e-6)
    for r in range(3):
        for c in range(4):
            u, v = c + 0.5, r + 0.5
            expected = (8 + 240 * u / (4 + u), 8 + 160 * v / (4 + u))
            assert tuple(centers[r, c]) == pytest.approx(expected, abs=1e-9)


def test_pixels_per_square_are_the_shortest_and_longest_square_sides():
    # The trapezoid above, x = 8 + 240u / (4 + u), y = 8 + 160v / (4 + u).
    # Grid vertices: x(u) = 8, 56, 88, 110.857143, 128 for u = 0..4, and at
    # u the rows are 160 / (4 + u) px tall. The shortest side is the top of
    # square (0, 3): x(4) - x(3) = 120 - 720/7 = 120/7 = 17.142857 (shorter
    # than any edge average: the right edge gives 60 / 3 = 20). The longest is
    # the bottom of square (2, 0), from (8, 128) to (56, 8 + 480/5 = 104):
    # sqrt(48^2 + 24^2) = sqrt(2880) = 53.665631.
    geometry = read(field((8, 8), (128, 8), (128, 68), (8, 128)))
    assert geometry.pixels_per_square_min == pytest.approx(120 / 7)
    assert geometry.pixels_per_square_max == pytest.approx(math.sqrt(2880))
    # Bounding boxes: square (r, c) is x(c + 1) - x(c) wide, from 48 (c = 0)
    # down to 120/7 (c = 3), and 160(r + 1)/(4 + c) - 160r/(5 + c) tall, from
    # 160/7 = 22.857143 (square (0, 3)) to 120 - 64 = 56 (square (2, 0)).
    assert geometry.square_span_x == pytest.approx((120 / 7, 48))
    assert geometry.square_span_y == pytest.approx((160 / 7, 56))
    grid = read(GRID_40)
    assert (grid.pixels_per_square_min, grid.pixels_per_square_max) == pytest.approx((40, 40))
    assert grid.square_span_x == pytest.approx((40, 40))


def test_a_field_frame_is_its_own_outer_edge_and_has_no_bands():
    geometry = read(GRID_40)
    approx_quad(geometry.field, [(10, 20), (170, 20), (170, 140), (10, 140)])
    assert geometry.outer == geometry.field
    assert geometry.bands == ()


def test_one_band_of_one_square_gives_the_field_quad_axis_aligned():
    # Source: plan B2a criterion 4. Counts 4 x 3 plus one band of 1 square:
    # the outer rectangle is 4 + 2 = 6 squares by 3 + 2 = 5. The outer edge
    # spans 8..248 by 8..208, so 240 / 6 = 40 and 200 / 5 = 40 px per square,
    # and the field is inset 40 px on every side:
    # (48, 48), (208, 48), (208, 168), (48, 168).
    geometry = read(outer((8, 8), (248, 8), (248, 208), (8, 208), 1.0), size=(256, 216))
    approx_quad(geometry.field, [(48, 48), (208, 48), (208, 168), (48, 168)])
    approx_quad(geometry.outer, [(8, 8), (248, 8), (248, 208), (8, 208)])


def test_the_field_is_derived_in_the_rectified_plane_under_perspective():
    # A hand-built homography over the outer rectangle (u in 0..6, v in 0..5):
    #   x = 8 + 80u / (1 + u/6) = 8 + 480u / (6 + u)
    #   y = 8 + 40v / (1 + u/6) = 8 + 240v / (6 + u)
    # Outer corners: (8, 8); (6, 0) -> (8 + 2880/12, 8) = (248, 8);
    # (6, 5) -> (248, 8 + 1200/12) = (248, 108); (0, 5) -> (8, 208).
    # The field is u 1..5 by v 1..4:
    #   (1, 1): x = 8 + 480/7 = 76.571429, y = 8 + 240/7 = 42.285714
    #   (5, 1): x = 8 + 2400/11 = 226.181818, y = 8 + 240/11 = 29.818182
    #   (5, 4): x = 226.181818, y = 8 + 960/11 = 95.272727
    #   (1, 4): x = 76.571429, y = 8 + 960/7 = 145.142857
    # Interpolating in the image instead would put the top-left corner at
    # x = 8 + 240/6 = 48, so this pins the rectified-plane derivation.
    geometry = read(outer((8, 8), (248, 8), (248, 108), (8, 208), 1.0), size=(256, 216))
    approx_quad(
        geometry.field,
        [
            (76.571429, 42.285714),
            (226.181818, 29.818182),
            (226.181818, 95.272727),
            (76.571429, 145.142857),
        ],
    )


def test_each_band_keeps_its_own_geometry():
    # Source: plan B2a criterion 4, never one averaged band. Counts 4 x 3,
    # bands of 1 and 1 square from the outside in: the outer rectangle is
    # 4 + 4 = 8 by 3 + 4 = 7 squares over 160 x 140 px, so 20 px per square.
    # Band 0 runs from the edge to 20 px in; band 1 from 20 to 40 px in.
    geometry = read(outer((0, 0), (160, 0), (160, 140), (0, 140), 1.0, 1.0), size=(160, 140))
    assert [band.index for band in geometry.bands] == [0, 1]
    first, second = geometry.bands
    approx_quad(first.outer, [(0, 0), (160, 0), (160, 140), (0, 140)])
    approx_quad(first.inner, [(20, 20), (140, 20), (140, 120), (20, 120)])
    approx_quad(second.outer, [(20, 20), (140, 20), (140, 120), (20, 120)])
    approx_quad(second.inner, [(40, 40), (120, 40), (120, 100), (40, 100)])
    approx_quad(geometry.field, second.inner)
    # Each side strip leaves out the band's corners: band 0's top strip runs
    # u 1..7, v 0..1 (x 20..140, y 0..20); its left strip u 0..1, v 1..6.
    top = first.side("top")
    approx_quad(top.quad, [(20, 0), (140, 0), (140, 20), (20, 20)])
    assert (top.length_squares, top.width_squares) == (6, 1)
    left = first.side("left")
    approx_quad(left.quad, [(0, 20), (20, 20), (20, 120), (0, 120)])
    assert (left.length_squares, left.width_squares) == (5, 1)
    assert [side.name for side in second.sides] == ["top", "right", "bottom", "left"]


def test_unequal_bands_keep_their_order_and_widths():
    # Bands of 0.5 then 1.5 squares from the outside in, counts 4 x 3: the
    # outer rectangle is 4 + 4 = 8 by 3 + 4 = 7 squares over 160 x 140 px, so
    # 20 px per square. Band 0 runs 0 to 0.5 x 20 = 10 px in, band 1 from 10
    # to (0.5 + 1.5) x 20 = 40 px in. Reversed bands would put band 0's inner
    # edge at 30 px, and two averaged bands at 20 px.
    geometry = read(outer((0, 0), (160, 0), (160, 140), (0, 140), 0.5, 1.5), size=(160, 140))
    first, second = geometry.bands
    assert (first.width_squares, first.inset_squares) == (0.5, 0)
    assert (second.width_squares, second.inset_squares) == (1.5, 0.5)
    approx_quad(first.inner, [(10, 10), (150, 10), (150, 130), (10, 130)])
    approx_quad(second.outer, first.inner)
    approx_quad(second.inner, [(40, 40), (120, 40), (120, 100), (40, 100)])
    # Band 0's top strip runs u 0.5..7.5, v 0..0.5 (x 10..150, y 0..10);
    # band 1's runs u 2..6, v 0.5..2 (x 40..120, y 10..40).
    approx_quad(first.side("top").quad, [(10, 0), (150, 0), (150, 10), (10, 10)])
    assert (first.side("top").length_squares, first.side("top").width_squares) == (7, 0.5)
    approx_quad(second.side("top").quad, [(40, 10), (120, 10), (120, 40), (40, 40)])
    assert (second.side("left").length_squares, second.side("left").width_squares) == (3, 1.5)


def test_a_negative_crop_offset_is_refused():
    # The contract refuses it in ReadRequest; a caller that builds the parts
    # itself gets the same refusal, never a field placed outside the photo.
    with pytest.raises(ValueError, match="crop_offset"):
        read(GRID_40, offset=Point.model_construct(x=-1.0, y=0.0))


def test_a_fractional_band_width_is_kept():
    # Bands need not be whole squares (plan B2a criterion 1). Counts 4 x 3 and
    # one band of 2.5: 4 + 5 = 9 by 3 + 5 = 8 squares over 180 x 160 px, so
    # 20 px per square and the field inset 2.5 x 20 = 50 px.
    geometry = read(outer((0, 0), (180, 0), (180, 160), (0, 160), 2.5), size=(180, 160))
    approx_quad(geometry.field, [(50, 50), (130, 50), (130, 110), (50, 110)])
    assert geometry.bands[0].width_squares == 2.5


def test_the_crop_offset_places_the_field_in_the_photo():
    # #101: corners are pixels of the staged crop, and the offset is the
    # crop's top-left corner in the decoded photo. (10, 20) + (1000, 500) =
    # (1010, 520); (170, 140) + (1000, 500) = (1170, 640).
    geometry = read(GRID_40, offset=Point(x=1000, y=500))
    assert geometry.crop_offset == (1000, 500)
    approx_quad(geometry.field_in_photo(), [(1010, 520), (1170, 520), (1170, 640), (1010, 640)])


@pytest.mark.parametrize(
    ("name", "quad"),
    [
        ("top_left", ((-0.5, 20), (170, 20), (170, 140), (10, 140))),
        ("top_right", ((10, 20), (170, -1), (170, 140), (10, 140))),
        ("bottom_right", ((10, 20), (170, 20), (200.5, 140), (10, 140))),
        ("bottom_left", ((10, 20), (170, 20), (170, 140), (10, 181))),
    ],
)
def test_a_corner_outside_the_image_is_named(name, quad):
    # Source: plan B2a criterion 3; vision-15. The image is 200 x 180.
    diagnosis = read(field(*quad))
    assert diagnosis == Diagnosis(
        code="corner_outside_image", message=diagnosis.message, corner=name
    )
    assert name.replace("_", " ") in diagnosis.message


def test_a_corner_on_the_image_edge_is_inside():
    # The image spans [0, 200] x [0, 180], edges included.
    geometry = read(field((0, 0), (200, 0), (200, 180), (0, 180)))
    assert isinstance(geometry, Geometry)


@pytest.mark.parametrize(
    ("code", "quad"),
    [
        # TR lies on the line from TL to BR: the turn at TR has cross 0.
        ("degenerate_quad", ((10, 20), (90, 20), (170, 20), (10, 140))),
        # Two corners coincide: an edge of length 0.
        ("degenerate_quad", ((10, 20), (10, 20), (170, 140), (10, 140))),
        # Mirrored: the corners run counterclockwise on screen.
        ("corner_order", ((170, 20), (10, 20), (10, 140), (170, 140))),
        # A bowtie: BR and BL swapped, so the edges cross.
        ("not_convex", ((10, 20), (170, 20), (10, 140), (170, 140))),
        # An arrowhead: BR pulled inside; turns (6400, -2000, 10800, 19200).
        ("not_convex", ((10, 20), (170, 20), (100, 60), (10, 140))),
    ],
)
def test_a_bad_quad_returns_its_typed_diagnosis(code, quad):
    diagnosis = read(field(*quad))
    assert isinstance(diagnosis, Diagnosis)
    assert diagnosis.code == code
    assert diagnosis.corner is None


def test_a_count_below_one_returns_bad_counts():
    # The contract refuses a count of 0; built past it, the read still refuses.
    counts = Counts.model_construct(
        blocks_across=2, blocks_down=0, squares_per_block_across=2, squares_per_block_down=1
    )
    assert read(GRID_40, counts=counts).code == "bad_counts"


@pytest.mark.parametrize("width", [0.0, -1.0, math.inf, math.nan])
def test_a_band_that_leaves_no_field_returns_no_field(width):
    # A positive width always leaves the field inside the outer rectangle,
    # which is cols + 2T by rows + 2T squares for a total band width T.
    band = BorderBand.model_construct(width_squares=width)
    frame = OuterEdgeFrame.model_construct(
        kind="outer_edge", corners=GRID_40.corners, bands=[BorderBand(width_squares=1.0), band]
    )
    assert read(frame).code == "no_field"


def test_every_code_is_named_once():
    assert len(CODES) == len(set(CODES))
    assert {"corner_outside_image", "too_few_pixels"} <= set(CODES)
    with pytest.raises(ValueError, match="unknown"):
        Diagnosis(code="no_grid", message="x")
    with pytest.raises(ValueError, match="corner"):
        Diagnosis(code="corner_outside_image", message="x")
    with pytest.raises(ValueError, match="pixels_per_square"):
        Diagnosis(code="too_few_pixels", message="x")
