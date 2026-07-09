"""Wasm-gate operations (sprint 3 S0, issue #66).

The exact cv2.grabCut and cv2.dft procedures the S0 gate measures, shared
by the native reference capture, the parity test (which runs under BOTH
native CI and the pytest-under-Pyodide job), and the perf script. One
definition, every runtime.

The grabCut seeding here is the gate's fixed probe shape (border ring =
background, centered inner rect = probable foreground); S1 owns the real
strip-uniformity seeding logic.
"""

from pathlib import Path

import cv2
import numpy as np

DETECT_LONGEST = 600  # the ~600 px detection downscale from the plan
GRABCUT_ITERS = 5
GRABCUT_SEED = 42
BORDER_RING_FRACTION = 0.03
INNER_RECT_INSET = 0.25
MAX_LAG_FRACTION = 0.25
PROFILE_LAGS = 60


def load_fixture_bgr(name: str, cap: int) -> np.ndarray:
    path = Path(__file__).resolve().parents[1] / "photoreal" / f"{name}_{cap}.png"
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"could not read fixture {path}")
    return image


def grabcut_op(image_bgr: np.ndarray) -> np.ndarray:
    """Seeded grabCut at the detection downscale; returns the uint8
    foreground mask (255 = foreground) at the downscaled size."""
    h, w = image_bgr.shape[:2]
    scale = DETECT_LONGEST / max(h, w)
    resized = cv2.resize(
        image_bgr, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA
    )
    rh, rw = resized.shape[:2]
    ring = max(2, int(round(BORDER_RING_FRACTION * max(rh, rw))))
    mask = np.full((rh, rw), cv2.GC_PR_BGD, np.uint8)
    inset_y, inset_x = int(round(INNER_RECT_INSET * rh)), int(round(INNER_RECT_INSET * rw))
    mask[inset_y : rh - inset_y, inset_x : rw - inset_x] = cv2.GC_PR_FGD
    mask[:ring, :] = cv2.GC_BGD
    mask[-ring:, :] = cv2.GC_BGD
    mask[:, :ring] = cv2.GC_BGD
    mask[:, -ring:] = cv2.GC_BGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.setRNGSeed(GRABCUT_SEED)
    cv2.grabCut(resized, mask, None, bgd, fgd, GRABCUT_ITERS, cv2.GC_INIT_WITH_MASK)
    fg = np.isin(mask, (cv2.GC_FGD, cv2.GC_PR_FGD))
    return (fg * 255).astype(np.uint8)


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    fa, fb = a > 0, b > 0
    union = np.logical_or(fa, fb).sum()
    if union == 0:
        return 1.0
    return float(np.logical_and(fa, fb).sum() / union)


def dft_autocorr_op(image_bgr: np.ndarray) -> dict:
    """FFT autocorrelation of the detrended grayscale via cv2.dft; returns
    zero-lag-normalized axis profiles and their peak lags."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    centered = gray - float(gray.mean())
    spectrum = cv2.dft(centered, flags=cv2.DFT_COMPLEX_OUTPUT)
    power = spectrum[..., 0] ** 2 + spectrum[..., 1] ** 2
    packed = np.stack([power, np.zeros_like(power)], axis=-1)
    autocorr = cv2.dft(packed, flags=cv2.DFT_INVERSE | cv2.DFT_SCALE | cv2.DFT_COMPLEX_OUTPUT)[
        ..., 0
    ]
    zero_lag = float(autocorr[0, 0])
    if zero_lag <= 0:
        raise ValueError("degenerate autocorrelation (flat image)")
    h, w = gray.shape
    profile_x = autocorr[0, : max(PROFILE_LAGS + 1, int(w * MAX_LAG_FRACTION))] / zero_lag
    profile_y = autocorr[: max(PROFILE_LAGS + 1, int(h * MAX_LAG_FRACTION)), 0] / zero_lag

    def peak(profile: np.ndarray) -> int:
        # strongest LOCAL maximum past the low-lag envelope (argmax alone
        # degenerates to the window floor because the quilt-vs-background
        # envelope dominates small lags); grid.py's convention
        lo = 5
        candidates = [
            i
            for i in range(lo + 1, len(profile) - 1)
            if profile[i] >= profile[i - 1] and profile[i] >= profile[i + 1]
        ]
        if not candidates:
            return lo + int(np.argmax(profile[lo:]))
        return max(candidates, key=lambda i: float(profile[i]))

    px, py = peak(profile_x), peak(profile_y)
    return {
        "peak_x": px,
        "peak_y": py,
        "val_x": float(profile_x[px]),
        "val_y": float(profile_y[py]),
        "profile_x": [float(v) for v in profile_x[1 : PROFILE_LAGS + 1]],
        "profile_y": [float(v) for v in profile_y[1 : PROFILE_LAGS + 1]],
    }


# the gate's op instances: (kind, fixture name, cap)
GRABCUT_CASES = [
    ("render_on_wood", 1400),
    ("render_on_wood", 2000),
    ("screenshot_composite", 1400),
]
DFT_CASES = [
    ("render_on_white", 1400),
    ("render_on_white", 2000),
    ("hst_star", 1400),
]
