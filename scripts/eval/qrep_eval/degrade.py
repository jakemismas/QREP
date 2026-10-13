"""Photometric stress degradations, generated at run time (plan 8.1; data-43).

Each takes a BGR uint8 image (low_res_jpeg also returns its scale) and, where it
is placed on the quilt, the field box (x0, y0, x1, y1) in that image's pixels.
The parameters are stated here and printed in every report. There is no
homography-only variant: exact corners scored 0.9988 at every tilt, so it would
test resampling, not capture (exp6). Drape and home light come from real phone
captures, which no synthetic version reproduces (plan 8.1).
"""

import math
from dataclasses import dataclass

import cv2
import numpy as np

Box = tuple[float, float, float, float]

GRADIENT_LOW = 0.55
JPEG_LONGEST = 600
JPEG_QUALITY = 40
BLUR_SIGMA = 2.0
GLARE_CENTER = (0.35, 0.35)
GLARE_SIGMA = 0.15
GLARE_STRENGTH = 0.85
PATCH_CENTER = (0.6, 0.6)
PATCH_SIDE = 0.25
PATCH_GRAY = 128
# Glare and the gradient work in float64 one band of rows at a time: over a whole
# 117 MP scan their float copies exceeded 5 GB in one process, while a band of a
# 10292 px wide scan holds about 63 MB per copy. The formula per pixel is unchanged.
BAND_ROWS = 256


def _to_uint8(values: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(values), 0, 255).astype(np.uint8)


def _bands(height: int):
    for top in range(0, height, BAND_ROWS):
        yield slice(top, min(top + BAND_ROWS, height))


def grayscale(image: np.ndarray) -> np.ndarray:
    """Value only: hue and saturation removed, as a black-and-white photo."""
    return cv2.cvtColor(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)


def lighting_gradient(image: np.ndarray, low: float = GRADIENT_LOW) -> np.ndarray:
    """Light falling off across the photo: brightness times 1.0 at the left edge,
    down linearly to low at the right edge."""
    width = image.shape[1]
    ramp = 1.0 - (1.0 - low) * np.arange(width) / max(width - 1, 1)
    out = np.empty(image.shape, np.uint8)
    for rows in _bands(image.shape[0]):
        out[rows] = _to_uint8(image[rows].astype(np.float64) * ramp[None, :, None])
    return out


def low_res_jpeg(
    image: np.ndarray, longest: int = JPEG_LONGEST, quality: int = JPEG_QUALITY
) -> tuple[np.ndarray, float]:
    """A small, heavily compressed copy: the longest side area-downsampled to longest
    px (never upscaled), then JPEG at quality. Returns the image and its scale."""
    height, width = image.shape[:2]
    size = _jpeg_size((width, height), longest)
    small = cv2.resize(image, size, interpolation=cv2.INTER_AREA) if size != (width, height) else image
    ok, data = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return cv2.imdecode(data, cv2.IMREAD_COLOR), size[0] / width


def _jpeg_size(size: tuple[int, int], longest: int) -> tuple[int, int]:
    width, height = size
    scale = min(1.0, longest / max(width, height))
    return math.floor(width * scale + 0.5), math.floor(height * scale + 0.5)


def read_size(name: str, size: tuple[int, int]) -> tuple[int, int]:
    """The (width, height) a degradation applied by name hands the reader, given the
    size it receives: only low_res_jpeg changes it."""
    return _jpeg_size(size, JPEG_LONGEST) if name == "low_res_jpeg" else size


def gaussian_blur(image: np.ndarray, sigma: float = BLUR_SIGMA) -> np.ndarray:
    """Defocus or shake: a Gaussian blur of sigma px."""
    return cv2.GaussianBlur(image, (0, 0), sigma)


def glare(image: np.ndarray, box: Box) -> np.ndarray:
    """A specular spot on the field: a Gaussian blend toward white, peak
    GLARE_STRENGTH at GLARE_CENTER of the field box, sigma GLARE_SIGMA of its
    shorter side."""
    x0, y0, x1, y1 = box
    cx, cy = x0 + GLARE_CENTER[0] * (x1 - x0), y0 + GLARE_CENTER[1] * (y1 - y0)
    sigma = GLARE_SIGMA * min(x1 - x0, y1 - y0)
    dx2 = (np.arange(image.shape[1]) - cx) ** 2
    out = np.empty(image.shape, np.uint8)
    for rows in _bands(image.shape[0]):
        dy2 = (np.arange(rows.start, rows.stop) - cy) ** 2
        alpha = GLARE_STRENGTH * np.exp(-(dx2[None, :] + dy2[:, None]) / (2 * sigma * sigma))
        alpha = alpha[..., None]
        out[rows] = _to_uint8(image[rows].astype(np.float64) * (1 - alpha) + 255.0 * alpha)
    return out


def occlusion(image: np.ndarray, box: Box) -> np.ndarray:
    """Something over part of the field: a flat gray patch PATCH_SIDE of the field
    box's width by PATCH_SIDE of its height, centred at PATCH_CENTER of the box."""
    x0, y0, x1, y1 = box
    w, h = math.floor(PATCH_SIDE * (x1 - x0) + 0.5), math.floor(PATCH_SIDE * (y1 - y0) + 0.5)
    left = math.floor(x0 + PATCH_CENTER[0] * (x1 - x0) - w / 2 + 0.5)
    top = math.floor(y0 + PATCH_CENTER[1] * (y1 - y0) - h / 2 + 0.5)
    out = image.copy()
    out[max(top, 0) : top + h, max(left, 0) : left + w] = PATCH_GRAY
    return out


@dataclass(frozen=True)
class Degradation:
    name: str
    params: dict


DEGRADATIONS = (
    Degradation("grayscale", {}),
    Degradation("lighting_gradient", {"factor_left": 1.0, "factor_right": GRADIENT_LOW}),
    Degradation("low_res_jpeg", {"longest_px": JPEG_LONGEST, "jpeg_quality": JPEG_QUALITY}),
    Degradation("gaussian_blur", {"sigma_px": BLUR_SIGMA}),
    Degradation("glare", {"center_of_field": list(GLARE_CENTER), "sigma_of_short_side": GLARE_SIGMA,
                          "peak_blend_to_white": GLARE_STRENGTH}),
    Degradation("occlusion", {"center_of_field": list(PATCH_CENTER), "side_of_field": PATCH_SIDE,
                              "gray": PATCH_GRAY}),
)


def apply(name: str, image: np.ndarray, box: Box) -> tuple[np.ndarray, float]:
    """Apply one degradation; returns the image and its scale against the input."""
    if name == "grayscale":
        return grayscale(image), 1.0
    if name == "lighting_gradient":
        return lighting_gradient(image), 1.0
    if name == "low_res_jpeg":
        return low_res_jpeg(image)
    if name == "gaussian_blur":
        return gaussian_blur(image), 1.0
    if name == "glare":
        return glare(image, box), 1.0
    if name == "occlusion":
        return occlusion(image, box), 1.0
    raise ValueError(f"unknown degradation {name!r}")
