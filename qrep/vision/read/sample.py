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
from qrep.vision.read.geometry import Geometry, Quad, apply, homography

# Warped pixels per square: the confirmed-grid prototype's value (plan B2a).
P = 32
# Share of the square's side left out at each seam (plan B2a): the sample is
# the pixels whose centers lie in the inner 60 percent, 20 of P = 32.
INSET = 0.2
# A square side shorter than this returns too_few_pixels: L*0.5 stayed at or
# above 0.98 down to 7 px after JPEG q70 with exact corners (exp3); D5 and D10
# set the final floor.
MIN_PX_PER_SQUARE = 7
# Float noise in the homography solve, which differs between the native and
# the Pyodide LAPACK builds, can put an exact 7 px side a hair under 7; the
# floor allows that much and no more.
FLOOR_SLACK_PX = 1e-6
# The most squares the read warps. The web stages a crop of at most 2000 px on
# its longest side (plan C3b), and a side under the floor does not read, so no
# staged crop holds more than 2000 // 7 = 285 squares a side: 285 x 285 =
# 81,225, whose warped field takes 81,225 x 32 x 32 x 3 bytes, about 250 MB.
# A 48 MP crop at the floor would hold about 980,000 squares, about 3 GB.
STAGED_CROP_PX = 2000
MAX_SQUARES = (STAGED_CROP_PX // MIN_PX_PER_SQUARE) ** 2
# Float CIELAB takes 12 bytes a pixel and its conversion holds a few such
# arrays at once, so the field converts, and each warp writes, in bands of
# square rows of about this many pixels (one square row when a row alone
# holds more), and the peak stays flat whatever the row count. Band strips
# are small and convert whole.
CHUNK_PX = 1 << 21
# Comparisons of computed lengths allow this much float noise.
_EPS = 1e-9

# sRGB to CIELAB with the D65 constants OpenCV documents. The read applies
# the formulas itself: native OpenCV 5.0's float conversion runs about 0.1 L
# below them in the midtones (gray 64 gives 26.98, the formula 27.09), and the
# native and browser builds ship different OpenCV versions. These numpy steps
# agree between the two runtimes to float32 rounding, about 1e-4 in L, from
# the order the matrix product sums in.
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
    CIELAB); B3 and B4a convert the parts they read with to_lab. downsample
    has shape (rows, cols, 2): the integer area factors on x and on y applied
    under each square before the warp, 1 for none.
    """

    geometry: Geometry
    lab: np.ndarray
    spread: np.ndarray
    strips: tuple[StripSample, ...]
    field_bgr: np.ndarray
    downsample: np.ndarray
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


def warp_matrix(
    quad: Quad,
    width: int,
    height: int,
    *,
    offset: tuple[float, float] = (0, 0),
    origin: tuple[float, float] = (0, 0),
    scale: tuple[float, float] = (1.0, 1.0),
) -> np.ndarray:
    """The map warpPerspective takes, with WARP_INVERSE_MAP, from a width x
    height output onto quad. offset is the top-left pixel of the output tile
    the map fills, and the source is a region of the image whose top-left
    pixel is origin, resized by scale on x and on y. The homography works on
    pixel edges and warpPerspective on pixel centers, so the map shifts by
    half a pixel on both sides."""
    to_edges = np.array([[1, 0, offset[0] + 0.5], [0, 1, offset[1] + 0.5], [0, 0, 1]])
    to_region = np.array(
        [[scale[0], 0, -origin[0] * scale[0]], [0, scale[1], -origin[1] * scale[1]], [0, 0, 1]]
    )
    to_centers = np.array([[1, 0, -0.5], [0, 1, -0.5], [0, 0, 1]])
    return to_centers @ to_region @ homography(quad, width, height) @ to_edges


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


def _factors(corners: np.ndarray, widths: np.ndarray, heights: np.ndarray) -> np.ndarray:
    """Each output cell's integer area factors on x and on y, shape (cells
    down, cells across, 2).

    corners holds every cell corner's source position, shape (cells down + 1,
    cells across + 1, 2), and widths and heights the cells' output sizes. A
    side over its output length is the source step of one output pixel along
    it, and an output pixel's footprint on an axis is the larger top or
    bottom step there plus the larger left or right one. The least factor
    that brings the footprint to 2 px or less, so the warp decimates by no
    more than 2 (exp0), is ceil(footprint / 2). No factor may shorten a step
    under 1 px, or one already under 1 px at all, because the warp would then
    lack detail the source held. Where that binds, on a foreshortened or
    sheared cell, the cell takes the allowed pair whose larger residual
    footprint is least, ties going to the smaller other one, and its warp
    aliases a little on that axis instead.
    """
    top = (corners[:-1, 1:] - corners[:-1, :-1]) / widths[None, :, None]
    bottom = (corners[1:, 1:] - corners[1:, :-1]) / widths[None, :, None]
    left = (corners[1:, :-1] - corners[:-1, :-1]) / heights[:, None, None]
    right = (corners[1:, 1:] - corners[:-1, 1:]) / heights[:, None, None]
    steps = np.stack([top, bottom, left, right], axis=2)
    size = np.abs(steps)
    footprint = size[:, :, :2].max(axis=2) + size[:, :, 2:].max(axis=2)
    least = np.maximum(1, np.ceil(footprint / 2 - _EPS)).astype(int)
    shortest = np.minimum(np.linalg.norm(steps, axis=-1), 1.0) - _EPS
    best = np.ones_like(least)
    high, low = footprint.max(axis=-1), footprint.min(axis=-1)
    for fx in range(1, int(least[..., 0].max()) + 1):
        for fy in range(1, int(least[..., 1].max()) + 1):
            pair = np.array([fx, fy])
            allowed = (
                (fx <= least[..., 0])
                & (fy <= least[..., 1])
                & np.all(np.linalg.norm(steps / pair, axis=-1) >= shortest, axis=-1)
            )
            residual = footprint / pair
            hi, lo = residual.max(axis=-1), residual.min(axis=-1)
            better = allowed & ((hi < high - _EPS) | ((hi <= high + _EPS) & (lo < low - _EPS)))
            best[better] = pair
            high, low = np.where(better, hi, high), np.where(better, lo, low)
    return best


def _span(lo: float, hi: float, factor: int, margin: int, limit: int) -> tuple[int, int]:
    """The pixel run [start, stop) that covers lo..hi plus margin pixels on
    each side, clamped to [0, limit] and grown to a multiple of factor where
    the image has room, so each area-downsampled pixel averages exactly
    factor source pixels."""
    start = max(0, math.floor(lo + _EPS) - margin)
    stop = min(limit, math.ceil(hi - _EPS) + margin)
    short = -(stop - start) % factor
    grow = min(short, limit - stop)
    return max(0, start - (short - grow)), stop + grow


def _area_warp(cv2, image: np.ndarray, quad: Quad, width: int, height: int):
    """Warps quad to a width x height px BGR image at P px per square, and
    returns it with each output cell's factors.

    The output splits into P x P cells: the squares of the field, or
    square-sized pieces of a band strip, the last ones partial. The source
    under each cell is area-downsampled by the cell's own factors (_factors)
    before the warp, because warpPerspective ignores INTER_AREA (exp0), so a
    near square under perspective shrinks to about 2P px while a far one keeps
    every pixel. Cells that share factors share one downsampled region: the
    bounding box of their corners, clamped to the image, so every slice bound
    lies between 0 and the image size.
    """
    xs = np.append(np.arange(0, width, P), width)
    ys = np.append(np.arange(0, height, P), height)
    cell_w, cell_h = np.diff(xs), np.diff(ys)
    u, v = np.meshgrid(xs, ys)
    corners = apply(homography(quad, width, height), np.stack([u, v], axis=-1))
    factors = _factors(corners, cell_w, cell_h)
    quads = np.stack([corners[:-1, :-1], corners[:-1, 1:], corners[1:, 1:], corners[1:, :-1]], 2)
    out = np.empty((height, width, 3), dtype=np.uint8)
    image_h, image_w = image.shape[:2]
    for fx, fy in np.unique(factors.reshape(-1, 2), axis=0).tolist():
        cells = np.all(factors == (fx, fy), axis=-1)
        rows, cols = np.nonzero(cells)
        low, high = quads[cells].min(axis=(0, 1)), quads[cells].max(axis=(0, 1))
        # A bilinear read reaches up to one downsampled pixel past its cell,
        # and a region the image cuts short can end in a partial pixel, so
        # two downsampled pixels of margin keep both off every cell.
        x0, x1 = _span(low[0], high[0], fx, 2 * fx, image_w)
        y0, y1 = _span(low[1], high[1], fy, 2 * fy, image_h)
        region = image[y0:y1, x0:x1]
        if fx > 1 or fy > 1:
            size = (max(1, round((x1 - x0) / fx)), max(1, round((y1 - y0) / fy)))
            region = cv2.resize(region, size, interpolation=cv2.INTER_AREA)
        scale = (region.shape[1] / (x1 - x0), region.shape[0] / (y1 - y0))
        c0, c1 = int(cols.min()), int(cols.max()) + 1
        r_end = int(rows.max()) + 1
        tile_w = int(xs[c1] - xs[c0])
        step = max(1, CHUNK_PX // (tile_w * P))
        for r0 in range(int(rows.min()), r_end, step):
            r1 = min(r_end, r0 + step)
            matrix = warp_matrix(
                quad, width, height, offset=(xs[c0], ys[r0]), origin=(x0, y0), scale=scale
            )
            tile = cv2.warpPerspective(
                region,
                matrix,
                (tile_w, int(ys[r1] - ys[r0])),
                flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
                borderMode=cv2.BORDER_REPLICATE,
            )
            mine = np.repeat(np.repeat(cells[r0:r1, c0:c1], cell_h[r0:r1], 0), cell_w[c0:c1], 1)
            np.copyto(out[ys[r0] : ys[r1], xs[c0] : xs[c1]], tile, where=mine[..., None])
    return out, factors


def read_squares(image: np.ndarray, geometry: Geometry) -> Squares | Diagnosis:
    """Samples every square and band strip of the confirmed geometry in a
    BGR uint8 image of the geometry's size, or returns the diagnosis that
    stops the read: bad_image, too_many_squares or too_few_pixels."""
    expected = (geometry.image_height, geometry.image_width, 3)
    if not isinstance(image, np.ndarray) or image.shape != expected or image.dtype != np.uint8:
        got = (getattr(image, "shape", None), getattr(image, "dtype", type(image).__name__))
        return Diagnosis(
            code="bad_image", message=f"expected a {expected} uint8 BGR image, got {got}"
        )
    rows, cols = geometry.rows, geometry.cols
    if rows * cols > MAX_SQUARES:
        return Diagnosis(
            code="too_many_squares",
            message=f"the field holds {rows} x {cols} = {rows * cols} squares; the read "
            f"warps at most {MAX_SQUARES}",
        )
    if geometry.pixels_per_square_min < MIN_PX_PER_SQUARE - FLOOR_SLACK_PX:
        return Diagnosis(
            code="too_few_pixels",
            message=f"the field's shortest square side is {geometry.pixels_per_square_min:.2f} "
            f"px; the read needs at least {MIN_PX_PER_SQUARE}",
            pixels_per_square=geometry.pixels_per_square_min,
        )
    import cv2

    field_bgr, downsample = _area_warp(cv2, image, geometry.field, cols * P, rows * P)
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
            strip = to_lab(_area_warp(cv2, image, side.quad, width, height)[0])
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
        downsample=downsample,
    )
