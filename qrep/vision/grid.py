"""Grid estimation: edge projections plus autocorrelation for pitch and phase.

Works on the rectified quilt image (border included). The border band has no
interior edges, so the autocorrelation pitch comes from the center field; the
phase then places grid lines across the whole quilt, and border detection
later decides which outer strips break periodicity.
"""

import cv2
import numpy as np
from pydantic import BaseModel

MIN_PITCH_PX = 5


class AxisGrid(BaseModel):
    pitch: float
    offset: float  # first grid line position in [0, pitch)
    boundaries: list[float]  # cell edges including 0 and the image extent
    confidence: float


class GridResult(BaseModel):
    x: AxisGrid
    y: AxisGrid

    @property
    def confidence(self) -> float:
        return min(self.x.confidence, self.y.confidence)


def _autocorrelate(profile: np.ndarray) -> np.ndarray:
    centered = profile - profile.mean()
    corr = np.correlate(centered, centered, mode="full")[len(centered) - 1 :]
    if corr[0] <= 0:
        return np.zeros_like(corr)
    return corr / corr[0]


def _binarize(profile: np.ndarray) -> np.ndarray:
    """Equal-weight spike train of edge locations.

    Raw gradient strengths correlate most strongly at block-scale lags (the
    strip pattern repeats there), which makes the strongest autocorrelation
    peak a HARMONIC of the cell pitch. Binarizing local maxima gives every
    grid line the same weight, so the fundamental pitch peaks as strongly as
    its multiples and picking the smallest strong peak is safe."""
    threshold = profile.mean() + profile.std()
    spikes = np.zeros_like(profile)
    for i in range(1, len(profile) - 1):
        if profile[i] > threshold and profile[i] >= profile[i - 1] and profile[i] >= profile[i + 1]:
            spikes[i] = 1.0
    # dilate by one pixel to absorb RANDOM half-pixel edge jitter; a
    # SYSTEMATIC alternation (cells alternating 14/16 px) is a genuine
    # 2-cell period this cannot and should not erase -- see the vision
    # robustness follow-up issue
    return np.minimum(spikes + np.roll(spikes, 1) + np.roll(spikes, -1), 1.0)


def _find_pitch(profile: np.ndarray, max_pitch: int) -> tuple[float, float]:
    """Fundamental repeat distance and its normalized peak prominence."""
    corr = _autocorrelate(_binarize(profile))
    lo, hi = MIN_PITCH_PX, min(max_pitch, len(corr) - 1)
    window = corr[lo:hi]
    if window.size == 0:
        raise ValueError("profile too short for grid detection")
    # local maxima only, so a slow downward ramp does not win
    peaks = [
        i
        for i in range(1, window.size - 1)
        if window[i] >= window[i - 1] and window[i] >= window[i + 1] and window[i] > 0
    ]
    if not peaks:
        raise ValueError("no periodicity found in edge profile")
    strongest = max(window[i] for i in peaks)
    # smallest lag that is comparably strong = the fundamental, not a harmonic
    fundamental = next(i for i in peaks if window[i] >= 0.5 * strongest)
    pitch = float(lo + fundamental)
    i = lo + fundamental
    # refine to sub-pixel with a parabolic fit around the peak
    if 1 <= i < len(corr) - 1:
        denom = corr[i - 1] - 2 * corr[i] + corr[i + 1]
        if abs(denom) > 1e-9:
            shift = 0.5 * (corr[i - 1] - corr[i + 1]) / denom
            pitch += float(np.clip(shift, -0.5, 0.5))
    # "prominence": the lag-0-normalized autocorrelation height at the
    # fundamental, not the topographic saddle-relative kind; already in
    # [0, 1] and monotone in periodicity strength, which is what the
    # confidence contract needs
    prominence = float(max(0.0, min(1.0, corr[i])))
    return pitch, prominence


def _find_offset(profile: np.ndarray, pitch: float) -> float:
    """Phase in [0, pitch) maximizing edge energy on the grid lines."""
    positions = np.arange(len(profile))
    best_offset, best_score = 0.0, -1.0
    for candidate in np.arange(0, pitch, 0.25):
        lines = np.arange(candidate, len(profile), pitch)
        idx = np.clip(np.round(lines).astype(int), 0, len(profile) - 1)
        score = float(profile[idx].sum())
        if score > best_score:
            best_offset, best_score = float(candidate), score
    del positions
    return best_offset


def _snap(line: float, profile: np.ndarray, pitch: float) -> float:
    """Pull a grid line onto the nearest strong local gradient peak.

    A tenth of a pixel of pitch error drifts to several pixels across fifty
    cells; snapping each line independently absorbs that. Lines in edgeless
    regions (border bands) stay where the lattice puts them."""
    radius = max(1, int(round(pitch * 0.2)))
    center = int(round(line))
    lo = max(0, center - radius)
    hi = min(len(profile), center + radius + 1)
    if hi <= lo:
        return line
    window = profile[lo:hi]
    peak = int(np.argmax(window))
    if window[peak] > 2.0 * profile.mean():
        return float(lo + peak)
    return line


def _boundaries(extent: int, pitch: float, offset: float, profile: np.ndarray) -> list[float]:
    lines = [_snap(v, profile, pitch) for v in np.arange(offset, extent, pitch)]
    edges = [0.0] + [float(v) for v in lines] + [float(extent)]
    # drop near-duplicate edges at the extremes (offset ~ 0 or ~ pitch)
    cleaned = [edges[0]]
    for edge in edges[1:]:
        if edge - cleaned[-1] > pitch * 0.3:
            cleaned.append(edge)
        elif edge == float(extent):
            cleaned[-1] = edge
    return cleaned


def estimate_grid(image_bgr: np.ndarray, mask: np.ndarray | None = None) -> GridResult:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    grad = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
    grad_v = np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    if mask is not None:
        # quilt-quad pixels only: background wedges at the crop edges would
        # otherwise inject strong spurious edges into the projections
        eroded = cv2.erode(mask, np.ones((5, 5), np.uint8))
        grad = grad * (eroded > 0)
        grad_v = grad_v * (eroded > 0)
    grad_x = grad.sum(axis=0)
    grad_y = grad_v.sum(axis=1)
    height, width = gray.shape

    pitch_x, prom_x = _find_pitch(grad_x, max_pitch=width // 4)
    pitch_y, prom_y = _find_pitch(grad_y, max_pitch=height // 4)
    offset_x = _find_offset(grad_x, pitch_x)
    offset_y = _find_offset(grad_y, pitch_y)
    return GridResult(
        x=AxisGrid(
            pitch=pitch_x,
            offset=offset_x,
            boundaries=_boundaries(width, pitch_x, offset_x, grad_x),
            confidence=prom_x,
        ),
        y=AxisGrid(
            pitch=pitch_y,
            offset=offset_y,
            boundaries=_boundaries(height, pitch_y, offset_y, grad_y),
            confidence=prom_y,
        ),
    )
