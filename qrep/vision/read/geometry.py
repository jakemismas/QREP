"""Geometry of the confirmed read: the frame and counts the user confirmed,
validated, with the field and each border band located in the image.

Coordinates are pixel edges of the staged crop: the image spans [0, W] x
[0, H] and pixel (i, j) covers [i, i + 1) x [j, j + 1), the convention of
the web's canvas and of the renderer's sidecar corners. Positions inside the
quilt are measured in squares: the field's plane runs u from 0 to cols and v
from 0 to rows, and an outer edge's plane adds the total band width T on
every side.

This module imports no cv2 itself. Its parent package, qrep.vision, still
imports the old pipeline and cv2 with it, until B6b removes them.
"""

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np

from qrep.contract import Counts, FieldFrame, OuterEdgeFrame, Point
from qrep.vision.read.diagnosis import Diagnosis

CORNER_NAMES = ("top_left", "top_right", "bottom_right", "bottom_left")
SIDE_NAMES = ("top", "right", "bottom", "left")

CornersSource = Literal["user", "suggestion"]
Quad = tuple[tuple[float, float], ...]

# Corners are placed to a pixel at best (dragged on screen and mapped to the
# image's pixels), so two corners closer than this, or a corner closer than
# this to the line through its two neighbors, cannot be told from coinciding
# or collinear corners at the image's resolution.
_PLACEMENT_PX = 1.0
# A square side shorter than this does not read (sample.py returns
# too_few_pixels): L*0.5 stayed at or above 0.98 down to 7 px after JPEG q70
# with exact corners (exp3); D5 and D10 set the final floor.
MIN_PX_PER_SQUARE = 7
# The most squares a read takes. The web stages a crop of at most 2000 px on
# its longest side (plan C3b), and a side under the floor does not read, so no
# staged crop holds more than 2000 // 7 = 285 squares a side: 285 x 285 =
# 81,225, whose warped field takes 81,225 x 32 x 32 x 3 bytes, about 250 MB.
# A 48 MP crop at the floor would hold about 980,000 squares, about 3 GB. The
# geometry refuses more before it maps a single grid vertex.
STAGED_CROP_PX = 2000
MAX_SQUARES = (STAGED_CROP_PX // MIN_PX_PER_SQUARE) ** 2


@dataclass(frozen=True)
class BandSide:
    """One side strip of a band, its corners left out, so a cornerstone of
    another fabric never mixes into a side's sample. length_squares runs
    along the side and width_squares across it."""

    name: str
    quad: Quad
    length_squares: float
    width_squares: float

    @property
    def extent(self) -> tuple[float, float]:
        """The strip's size in squares along x and along y of its quad."""
        if self.name in ("top", "bottom"):
            return (self.length_squares, self.width_squares)
        return (self.width_squares, self.length_squares)


@dataclass(frozen=True)
class Band:
    """One border band; index 0 is the outermost."""

    index: int
    width_squares: float
    inset_squares: float
    outer: Quad
    inner: Quad
    sides: tuple[BandSide, ...]

    def side(self, name: str) -> BandSide:
        return next(side for side in self.sides if side.name == name)


@dataclass(frozen=True)
class Geometry:
    """The confirmed geometry of one read.

    confidence is the confidence of every user-confirmed input it records
    (the frame's corners or outer edge, each band, the counts) and of every
    value derived from them here, so it is always 1.0 (docs/SPEC.md section
    4). crop_offset places the staged crop in the decoded photo; the web sets
    it when it cuts the crop, so it is no CV value either.

    pixels_per_square_min and pixels_per_square_max are the shortest and
    longest side of any square, in source pixels: the shortest sets the pixel
    floor, because under perspective its square is the worst resolved.
    """

    frame: FieldFrame | OuterEdgeFrame
    counts: Counts
    corners_source: CornersSource
    rows: int
    cols: int
    blocks_down: int
    blocks_across: int
    block_rows: int
    block_cols: int
    field: Quad
    outer: Quad
    bands: tuple[Band, ...]
    image_width: int
    image_height: int
    crop_offset: tuple[float, float]
    pixels_per_square_min: float
    pixels_per_square_max: float
    confidence: float = 1.0

    def __post_init__(self):
        if self.confidence != 1.0:
            raise ValueError(
                f"a confirmed geometry is a user fact at confidence 1.0, got {self.confidence}"
            )

    def square_centers(self) -> np.ndarray:
        """Each square's center in image pixels, shape (rows, cols, 2)."""
        u, v = np.meshgrid(np.arange(self.cols) + 0.5, np.arange(self.rows) + 0.5)
        return apply(homography(self.field, self.cols, self.rows), np.stack([u, v], axis=-1))

    def grid_vertices(self) -> np.ndarray:
        """Every grid vertex of the field in image pixels, shape (rows + 1,
        cols + 1, 2)."""
        return _grid_vertices(self.field, self.rows, self.cols)


def homography(quad: Quad, width: float, height: float) -> np.ndarray:
    """The 3 x 3 map from the rectangle [0, width] x [0, height] onto quad,
    corner to corner in the order top left, top right, bottom right, bottom
    left. Four point pairs fix a homography, solved here as eight linear
    equations with h33 = 1."""
    rect = ((0.0, 0.0), (width, 0.0), (width, height), (0.0, height))
    a, b = [], []
    for (u, v), (x, y) in zip(rect, quad, strict=True):
        a.append([u, v, 1, 0, 0, 0, -u * x, -v * x])
        a.append([0, 0, 0, u, v, 1, -u * y, -v * y])
        b += [x, y]
    h = np.linalg.solve(np.array(a, dtype=float), np.array(b, dtype=float))
    return np.append(h, 1.0).reshape(3, 3)


def apply(h: np.ndarray, points) -> np.ndarray:
    """Maps points of shape (..., 2) through the homography h."""
    points = np.asarray(points, dtype=float)
    mapped = points @ h[:, :2].T + h[:, 2]
    return mapped[..., :2] / mapped[..., 2:]


def _quad(h: np.ndarray, u0: float, v0: float, u1: float, v1: float) -> Quad:
    corners = apply(h, [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    return tuple((float(x), float(y)) for x, y in corners)


def _shape(quad: Quad) -> Diagnosis | None:
    """None for a convex quad whose corners run clockwise on screen (y down)."""
    degenerate = Diagnosis(
        code="degenerate_quad",
        message=f"two corners lie within {_PLACEMENT_PX:g} px of each other, or a corner "
        f"within {_PLACEMENT_PX:g} px of the line through its neighbors",
    )
    turns = []
    for i in range(4):
        (x0, y0), (x1, y1), (x2, y2) = quad[i - 1], quad[i], quad[(i + 1) % 4]
        # Corner i's neighbors nearly coinciding fold the quad onto itself.
        diagonal = math.hypot(x2 - x0, y2 - y0)
        if diagonal < _PLACEMENT_PX:
            return degenerate
        # The turn at corner i. Over the diagonal it is the corner's distance
        # from the line through its two neighbors, never more than its
        # distance from either, so it also catches two adjacent corners.
        cross = (x1 - x0) * (y2 - y1) - (y1 - y0) * (x2 - x1)
        if abs(cross) < _PLACEMENT_PX * diagonal:
            return degenerate
        turns.append(cross > 0)
    if all(turns):
        return None
    if not any(turns):
        return Diagnosis(
            code="corner_order",
            message="the corners run counterclockwise: two corners are swapped",
        )
    return Diagnosis(code="not_convex", message="the corners do not make a convex shape")


def _sides(h: np.ndarray, o: float, w: float, big_u: float, big_v: float) -> tuple[BandSide, ...]:
    """The four side strips of the band from o to o + w squares in from the
    outer edge, each between the band's inner corner lines."""
    along_u, along_v = big_u - 2 * (o + w), big_v - 2 * (o + w)
    return (
        BandSide("top", _quad(h, o + w, o, big_u - o - w, o + w), along_u, w),
        BandSide("right", _quad(h, big_u - o - w, o + w, big_u - o, big_v - o - w), along_v, w),
        BandSide("bottom", _quad(h, o + w, big_v - o - w, big_u - o - w, big_v - o), along_u, w),
        BandSide("left", _quad(h, o, o + w, o + w, big_v - o - w), along_v, w),
    )


def _grid_vertices(field: Quad, rows: int, cols: int) -> np.ndarray:
    """Every grid vertex in image pixels, shape (rows + 1, cols + 1, 2)."""
    u, v = np.meshgrid(np.arange(cols + 1), np.arange(rows + 1))
    return apply(homography(field, cols, rows), np.stack([u, v], axis=-1))


def square_sides(vertices: np.ndarray) -> np.ndarray:
    """Every square side as a vector in image pixels, shape (n, 2)."""
    across = vertices[:, 1:] - vertices[:, :-1]
    down = vertices[1:] - vertices[:-1]
    return np.concatenate([across.reshape(-1, 2), down.reshape(-1, 2)])


def _square_sizes(field: Quad, rows: int, cols: int) -> tuple[float, float]:
    """The shortest and longest square side, from every grid vertex mapped
    into the image, so a foreshortened far square counts at its own size."""
    lengths = np.linalg.norm(square_sides(_grid_vertices(field, rows, cols)), axis=-1)
    return float(lengths.min()), float(lengths.max())


def confirm(
    frame: FieldFrame | OuterEdgeFrame,
    counts: Counts,
    image_size: tuple[int, int],
    crop_offset: Point,
    *,
    corners_source: CornersSource,
) -> Geometry | Diagnosis:
    """Validates the confirmed frame and counts against an image of
    image_size (width, height) and derives the read's geometry.

    corners_source says whether the user set the corners or accepted a
    suggestion, so evaluation can separate corner error from read error
    (data-48). The v2 request carries no such field yet (#231), so the caller
    names it.
    """
    if corners_source not in ("user", "suggestion"):
        return Diagnosis(
            code="bad_corners_source",
            message=f"corners_source must be 'user' or 'suggestion', got {corners_source!r}",
        )
    if not all(math.isfinite(v) and v >= 0 for v in (crop_offset.x, crop_offset.y)):
        return Diagnosis(
            code="bad_crop_offset",
            message="the crop offset must be finite and not negative, "
            f"got ({crop_offset.x}, {crop_offset.y})",
        )
    numbers = (
        counts.blocks_across,
        counts.blocks_down,
        counts.squares_per_block_across,
        counts.squares_per_block_down,
    )
    if any(n < 1 for n in numbers):
        return Diagnosis(
            code="bad_counts", message=f"every count must be at least 1, got {numbers}"
        )
    squares = (counts.blocks_across * counts.squares_per_block_across) * (
        counts.blocks_down * counts.squares_per_block_down
    )
    if squares > MAX_SQUARES:
        return Diagnosis(
            code="too_many_squares",
            message=f"the field holds {squares} squares; the read takes at most {MAX_SQUARES}",
        )
    widths = [band.width_squares for band in getattr(frame, "bands", [])]
    if not all(math.isfinite(w) and w > 0 for w in widths):
        return Diagnosis(
            code="no_field",
            message=f"every border band needs a positive width in squares, got {widths}",
        )
    width, height = image_size
    given = tuple(
        (getattr(frame.corners, name).x, getattr(frame.corners, name).y) for name in CORNER_NAMES
    )
    for name, (x, y) in zip(CORNER_NAMES, given, strict=True):
        if not (0 <= x <= width and 0 <= y <= height):
            return Diagnosis(
                code="corner_outside_image",
                message=f"the {name.replace('_', ' ')} corner ({x}, {y}) lies outside the "
                f"{width} x {height} image",
                corner=name,
            )
    shape = _shape(given)
    if shape is not None:
        return shape

    cols = counts.blocks_across * counts.squares_per_block_across
    rows = counts.blocks_down * counts.squares_per_block_down
    total = sum(widths)
    big_u, big_v = cols + 2 * total, rows + 2 * total
    h = homography(given, big_u, big_v)
    outer = tuple((float(x), float(y)) for x, y in given)
    bands = []
    inset = 0.0
    for index, w in enumerate(widths):
        bands.append(
            Band(
                index=index,
                width_squares=w,
                inset_squares=inset,
                outer=_quad(h, inset, inset, big_u - inset, big_v - inset),
                inner=_quad(h, inset + w, inset + w, big_u - inset - w, big_v - inset - w),
                sides=_sides(h, inset, w, big_u, big_v),
            )
        )
        inset += w
    field = _quad(h, total, total, total + cols, total + rows) if bands else outer
    shortest, longest = _square_sizes(field, rows, cols)
    return Geometry(
        frame=frame,
        counts=counts,
        corners_source=corners_source,
        rows=rows,
        cols=cols,
        blocks_down=counts.blocks_down,
        blocks_across=counts.blocks_across,
        block_rows=counts.squares_per_block_down,
        block_cols=counts.squares_per_block_across,
        field=field,
        outer=outer,
        bands=tuple(bands),
        image_width=width,
        image_height=height,
        crop_offset=(crop_offset.x, crop_offset.y),
        pixels_per_square_min=shortest,
        pixels_per_square_max=longest,
    )
