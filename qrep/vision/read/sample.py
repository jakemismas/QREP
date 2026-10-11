"""Sampling for the confirmed read: warp the field and every band strip to
P px per square, then take each square's median float CIELAB.

The knobs below are provisional (plan section 5.B): D5 measures the new read
and Jake freezes them, and B2b moves them into the read's knob table.

cv2 is imported inside read_squares only.
"""

import math
from dataclasses import dataclass

import numpy as np

from qrep.vision.read.diagnosis import Diagnosis
from qrep.vision.read.geometry import Geometry, Quad, homography, square_sides

# Warped pixels per square: the confirmed-grid prototype's value (plan B2a).
P = 32
# warpPerspective ignores INTER_AREA, so a larger source aliases in the warp
# (exp0); the read first area-downsamples to about 2P px per square.
DOWNSAMPLE_PX = 2 * P
# Share of the square's side left out at each seam (plan B2a): the sample is
# the pixels whose centers lie in the inner 60 percent, 20 of P = 32.
INSET = 0.2
# A square side shorter than this returns too_few_pixels: L*0.5 stayed at or
# above 0.98 down to 7 px after JPEG q70 with exact corners (exp3); D5 and D10
# set the final floor.
MIN_PX_PER_SQUARE = 7
# Float CIELAB takes 12 bytes a pixel and its conversion holds a few such
# arrays at once, so the field converts in bands of square rows of about this
# many pixels (one square row when a row alone holds more), and the peak stays
# flat whatever the row count. Band strips are small and convert whole.
CHUNK_PX = 1 << 21

# sRGB to CIELAB with the D65 constants OpenCV documents. The read applies
# the formulas itself: native OpenCV 5.0's float conversion runs about 0.1 L
# below them in the midtones (gray 64 gives 26.98, the formula 27.09), and the
# native and browser builds ship different OpenCV versions, while these numpy
# steps give the same numbers in both runtimes.
_CODES = np.arange(256) / 255
_LINEAR = np.where(_CODES <= 0.04045, _CODES / 12.92, ((_CODES + 0.055) / 1.055) ** 2.4).astype(
    np.float32
)
# Rows give X / Xn, Y and Z / Zn from linear R, G and B.
_TO_XYZ = (
    np.array(
        [
            [0.412453, 0.357580, 0.180423],
            [0.212671, 0.715160, 0.072169],
            [0.019334, 0.119193, 0.950227],
        ]
    )
    / np.array([[0.950456], [1.0], [1.088754]])
).astype(np.float32)
_EPSILON = np.float32(0.008856)


@dataclass(frozen=True)
class StripSample:
    """The median float CIELAB of one band side's inner region, and its
    median absolute deviation per channel."""

    band: int
    side: str
    lab: np.ndarray
    spread: np.ndarray


@dataclass(frozen=True, eq=False)
class Squares:
    """What the read samples, for the fabrics and the vote (B2b), the fit
    check (B3) and the unit classifier (B4a).

    lab and spread have shape (rows, cols, 3): each square's median float
    CIELAB (L in 0..100) over its inner pixels, and the median absolute
    deviation per channel. These are measurements, not model values: B2b
    derives each square's label and its confidence from them, and the spread
    beside each sample says how far to trust it. field_bgr is the warped
    field, rows x P by cols x P px, kept as uint8 BGR (a quarter of its float
    CIELAB); B3 and B4a convert the parts they read with to_lab. downsample is
    the area scale applied on x and on y before the warp, 1.0 for none.
    """

    geometry: Geometry
    lab: np.ndarray
    spread: np.ndarray
    strips: tuple[StripSample, ...]
    field_bgr: np.ndarray
    downsample: tuple[float, float]
    px_per_square: int = P
    inset: float = INSET


def to_lab(bgr: np.ndarray) -> np.ndarray:
    """Float CIELAB (L in 0..100) of a BGR uint8 image, as float32."""
    xyz = _LINEAR[bgr[..., ::-1]] @ _TO_XYZ.T
    f = np.where(xyz > _EPSILON, np.cbrt(xyz), np.float32(7.787) * xyz + np.float32(16 / 116))
    fx, fy, fz = f[..., 0], f[..., 1], f[..., 2]
    y = xyz[..., 1]
    lightness = np.where(y > _EPSILON, np.float32(116) * fy - 16, np.float32(903.3) * y)
    return np.stack([lightness, 500 * (fx - fy), 200 * (fy - fz)], axis=-1).astype(np.float32)


def warp_matrix(quad: Quad, width: int, height: int) -> np.ndarray:
    """The map warpPerspective takes, with WARP_INVERSE_MAP, from a width x
    height output onto quad. The homography works on pixel edges and
    warpPerspective on pixel centers, so the map shifts by half a pixel on
    both sides."""
    to_edges = np.array([[1, 0, 0.5], [0, 1, 0.5], [0, 0, 1]])
    to_centers = np.array([[1, 0, -0.5], [0, 1, -0.5], [0, 0, 1]])
    return to_centers @ homography(quad, width, height) @ to_edges


def _warp(cv2, image: np.ndarray, quad: Quad, width: int, height: int) -> np.ndarray:
    return cv2.warpPerspective(
        image,
        warp_matrix(quad, width, height),
        (width, height),
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _inner(n: int, inset_px: float) -> slice:
    """The pixels of a run of n whose centers, at i + 0.5, lie inset_px or
    more from both ends. A run thinner than its two insets keeps its middle
    pixel, so a sample is never empty whatever the inset knob says."""
    lo, hi = math.ceil(inset_px - 0.5), math.floor(n - inset_px - 0.5)
    if hi < lo:
        lo = hi = (n - 1) // 2
    return slice(lo, hi + 1)


def _median_and_spread(pixels: np.ndarray, axis: int) -> tuple[np.ndarray, np.ndarray]:
    median = np.median(pixels, axis=axis)
    spread = np.median(np.abs(pixels - np.expand_dims(median, axis)), axis=axis)
    return median, spread


def _axis_scale(span: tuple[float, float]) -> float:
    smallest, largest = span
    return min(1.0, max(DOWNSAMPLE_PX / largest, P / smallest))


def _downsample(geometry: Geometry) -> tuple[float, float]:
    """The area scale on x and on y. Each axis shrinks until its largest
    square spans about 2P px, so the warp decimates by little more than 2
    (exp0), but never so far that its smallest square spans fewer than P px.
    A bounding box understates a sheared or foreshortened square's sides, so
    when the two scales would bring any side under P px (or shorten one that
    is already under P), both axes take the one scale that keeps every side
    there: the warp then aliases a little on the largest squares instead."""
    scale = np.array([_axis_scale(geometry.square_span_x), _axis_scale(geometry.square_span_y)])
    sides = square_sides(geometry.grid_vertices())
    lengths = np.linalg.norm(sides, axis=-1)
    if np.any(np.linalg.norm(sides * scale, axis=-1) < np.minimum(lengths, P) - 1e-9):
        longest, shortest = geometry.pixels_per_square_max, geometry.pixels_per_square_min
        uniform = min(1.0, max(DOWNSAMPLE_PX / longest, P / shortest))
        return (uniform, uniform)
    return (float(scale[0]), float(scale[1]))


def read_squares(image: np.ndarray, geometry: Geometry) -> Squares | Diagnosis:
    """Samples every square and band strip of the confirmed geometry in a
    BGR uint8 image of the geometry's size, or returns too_few_pixels."""
    expected = (geometry.image_height, geometry.image_width, 3)
    if image.shape != expected or image.dtype != np.uint8:
        raise ValueError(f"expected a {expected} uint8 BGR image, got {image.shape} {image.dtype}")
    if geometry.pixels_per_square_min < MIN_PX_PER_SQUARE:
        return Diagnosis(
            code="too_few_pixels",
            message=f"the field's shortest square side is {geometry.pixels_per_square_min:.2f} "
            f"px; the read needs at least {MIN_PX_PER_SQUARE}",
            pixels_per_square=geometry.pixels_per_square_min,
        )
    import cv2

    # Only the frame's bounding box is read. The validated corners lie inside
    # the image, so every slice bound here is between 0 and the image size.
    xs = [x for x, _ in geometry.outer]
    ys = [y for _, y in geometry.outer]
    x0, y0 = max(0, math.floor(min(xs))), max(0, math.floor(min(ys)))
    x1 = min(geometry.image_width, max(x0 + 1, math.ceil(max(xs))))
    y1 = min(geometry.image_height, max(y0 + 1, math.ceil(max(ys))))
    source = image[y0:y1, x0:x1]
    scale_x, scale_y = _downsample(geometry)
    if scale_x < 1.0 or scale_y < 1.0:
        size = (max(1, round((x1 - x0) * scale_x)), max(1, round((y1 - y0) * scale_y)))
        source = cv2.resize(source, size, interpolation=cv2.INTER_AREA)
    sx, sy = source.shape[1] / (x1 - x0), source.shape[0] / (y1 - y0)

    def local(quad: Quad) -> Quad:
        return tuple(((x - x0) * sx, (y - y0) * sy) for x, y in quad)

    rows, cols = geometry.rows, geometry.cols
    field_bgr = _warp(cv2, source, local(geometry.field), cols * P, rows * P)
    lab = np.empty((rows, cols, 3), dtype=np.float32)
    spread = np.empty((rows, cols, 3), dtype=np.float32)
    keep = _inner(P, INSET * P)
    step = max(1, CHUNK_PX // (cols * P * P))
    for r0 in range(0, rows, step):
        r1 = min(rows, r0 + step)
        block = to_lab(field_bgr[r0 * P : r1 * P]).reshape(r1 - r0, P, cols, P, 3)
        inner = block[:, keep, :, keep, :].transpose(0, 2, 1, 3, 4).reshape(r1 - r0, cols, -1, 3)
        lab[r0:r1], spread[r0:r1] = _median_and_spread(inner, axis=2)

    strips = []
    for band in geometry.bands:
        for side in band.sides:
            along_x, along_y = side.extent
            width, height = max(1, round(along_x * P)), max(1, round(along_y * P))
            strip = to_lab(_warp(cv2, source, local(side.quad), width, height))
            # The inset is a share of the band's width on both axes, as for a
            # square, but never more than a fifth of a short strip's length.
            keep_y = _inner(height, INSET * min(band.width_squares, along_y) * P)
            keep_x = _inner(width, INSET * min(band.width_squares, along_x) * P)
            median, deviation = _median_and_spread(strip[keep_y, keep_x].reshape(-1, 3), axis=0)
            strips.append(
                StripSample(band=band.index, side=side.name, lab=median, spread=deviation)
            )

    return Squares(
        geometry=geometry,
        lab=lab,
        spread=spread,
        strips=tuple(strips),
        field_bgr=field_bgr,
        downsample=(sx, sy),
    )
