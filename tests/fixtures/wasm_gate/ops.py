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

# --- sprint 4 S0 (issue #92): block-lattice SNR evidence op --------------
# The FROZEN core of the block_lattice_snr detector S1 lands in
# qrep/vision/repeats.py: the exact Lab-channel-swept, scale-swept-detrend 2D
# autocorrelation the wasm gate measures. One definition, every runtime.
#
# Candidate frozen sigma ladder and SNR shape proposed here; Jake freezes the
# ladder, T4, and T5 from S0's baseline report before S1 (parent-issue
# checkbox). The rungs span the fine detrend scales the phone-cap mill-wheel
# class needs (spike: a single fixed 5%-of-inset sigma collapses its ~10 px
# block to SNR 0.00); a coarse rung is unnecessary because a high pass only
# removes structure FINER than its sigma, so large motif periods survive
# every rung.
LADDER_SIGMAS = (1.5, 3.0, 6.0)
SNR_HARMONICS = (1, 2, 3)  # fundamental + first two harmonics of the comb
SNR_MIN_LAG = 5  # grid.py's MIN_PITCH_PX; ignore the zero-lag envelope
# canonical parity config (channel index, sigma): the L channel at the finest
# rung. Deterministic and config-flip-proof, so its fundamental lags pin
# EXACTLY across runtimes while the argmax config's SNR pins within abs-tol.
LADDER_REF_CHANNEL = 0
LADDER_REF_SIGMA = 1.5


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


# ---------------------------------------------------------------------------
# sprint 4 S0: block-lattice SNR ladder autocorrelation
# ---------------------------------------------------------------------------


def _autocorr_axis_lines(field: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Zero-lag-normalized axis profiles of the 2D autocorrelation of `field`.

    Pads to cv2.getOptimalDFTSize so the two DFTs stay fast on the odd
    fixture widths (1754 = 2 x 877 is a worst case for a raw FFT); the pad is
    zeros beyond the signal, which the autocorrelation's zero-lag
    normalization divides out. Returns (profile_x over columns, profile_y over
    rows) or None when the field is flat (degenerate zero-lag)."""
    h, w = field.shape
    oh, ow = cv2.getOptimalDFTSize(h), cv2.getOptimalDFTSize(w)
    padded = np.zeros((oh, ow), np.float32)
    padded[:h, :w] = field
    spectrum = cv2.dft(padded, flags=cv2.DFT_COMPLEX_OUTPUT)
    power = spectrum[..., 0] ** 2 + spectrum[..., 1] ** 2
    packed = np.stack([power, np.zeros_like(power)], axis=-1)
    autocorr = cv2.dft(
        packed, flags=cv2.DFT_INVERSE | cv2.DFT_SCALE | cv2.DFT_COMPLEX_OUTPUT
    )[..., 0]
    zero_lag = float(autocorr[0, 0])
    if zero_lag <= 0:
        return None
    return autocorr[0, :w] / zero_lag, autocorr[:, 0][:h] / zero_lag


def _axis_fundamental(profile: np.ndarray, hi: int) -> int:
    """Smallest comparably-strong (>= 0.5x the strongest) local maximum in
    [SNR_MIN_LAG, hi) - grid.py's frozen fundamental rule, so the coarse block
    period wins over its own harmonics rather than an aliased multiple."""
    lo = SNR_MIN_LAG
    if hi <= lo + 2:
        return 0
    window = profile[lo:hi]
    peaks = [
        i
        for i in range(1, len(window) - 1)
        if window[i] >= window[i - 1] and window[i] >= window[i + 1] and window[i] > 0
    ]
    if not peaks:
        return 0
    strongest = max(float(window[i]) for i in peaks)
    fundamental = next(i for i in peaks if window[i] >= 0.5 * strongest)
    return lo + fundamental


def _axis_snr(profile: np.ndarray, period: int, hi: int) -> float:
    """Peak SNR of the harmonic comb over a global background.

    For each harmonic k the peak value at lag k*period (with +/-1 lag jitter)
    is scored against the whole search band's median and std. A global (not
    local) background does not collapse to zero in the trough of a clean
    lattice, so the statistic stays in a bounded, thresholdable range instead
    of exploding on noiseless renders; averaging over k=1..3 rewards a genuine
    comb over a lone accidental peak."""
    if period < SNR_MIN_LAG:
        return 0.0
    band = profile[SNR_MIN_LAG:hi]
    if band.size == 0:
        return 0.0
    median = float(np.median(band))
    std = float(np.std(band))
    if std < 1e-6:
        return 0.0
    snrs: list[float] = []
    for k in SNR_HARMONICS:
        center = int(round(k * period))
        if center + 1 >= len(profile):
            break
        peak = float(profile[max(0, center - 1) : center + 2].max())
        snrs.append((peak - median) / std)
    if not snrs:
        return 0.0
    return float(sum(snrs) / len(snrs))


def _config_snr(channel: np.ndarray, sigma: float, hi_x: int, hi_y: int):
    """(min-axis SNR, period_x, period_y) for one (channel, sigma) config, or
    None when the detrended channel carries no signal."""
    highpass = channel - cv2.GaussianBlur(channel, (0, 0), sigma)
    if float(highpass.std()) < 0.5:
        return None
    lines = _autocorr_axis_lines(highpass)
    if lines is None:
        return None
    profile_x, profile_y = lines
    period_x = _axis_fundamental(profile_x, hi_x)
    period_y = _axis_fundamental(profile_y, hi_y)
    snr_x = _axis_snr(profile_x, period_x, hi_x)
    snr_y = _axis_snr(profile_y, period_y, hi_y)
    return min(snr_x, snr_y), period_x, period_y, snr_x, snr_y


def lab_ladder_autocorr_op(image_bgr: np.ndarray) -> dict:
    """Block-lattice evidence: the max min-axis SNR over the Lab channel sweep
    (L, a, b) and the frozen detrend-sigma ladder.

    Returns the argmax config's per-axis block periods and SNR plus a fixed
    canonical-config (L channel, finest sigma) measurement whose fundamental
    lags pin exactly across runtimes even when a near-tie flips the argmax
    channel or sigma. Periods are at the INPUT image resolution (no internal
    downscale, so the phone-cap fine periods survive and the lags stay
    integer-exact)."""
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2Lab).astype(np.float32)
    h, w = lab.shape[:2]
    hi_x, hi_y = w // 4, h // 4

    best = None  # (snr, period_x, period_y, snr_x, snr_y, channel, sigma)
    ref = None  # canonical-config measurement
    for channel_index in range(3):
        channel = lab[:, :, channel_index]
        for sigma in LADDER_SIGMAS:
            result = _config_snr(channel, sigma, hi_x, hi_y)
            if result is None:
                continue
            snr, period_x, period_y, snr_x, snr_y = result
            candidate = (snr, period_x, period_y, snr_x, snr_y, channel_index, sigma)
            if best is None or snr > best[0]:
                best = candidate
            if channel_index == LADDER_REF_CHANNEL and sigma == LADDER_REF_SIGMA:
                ref = (period_x, period_y, snr)

    if best is None:
        return {
            "period_x": 0, "period_y": 0, "snr": 0.0, "snr_x": 0.0, "snr_y": 0.0,
            "channel": -1, "sigma": 0.0,
            "ref_lag_x": 0, "ref_lag_y": 0, "ref_snr": 0.0,
        }
    ref = ref if ref is not None else (0, 0, 0.0)
    return {
        "period_x": best[1],
        "period_y": best[2],
        "snr": best[0],
        "snr_x": best[3],
        "snr_y": best[4],
        "channel": best[5],
        "sigma": best[6],
        "ref_lag_x": ref[0],
        "ref_lag_y": ref[1],
        "ref_snr": ref[2],
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
# ladder-autocorr parity cases: strong dominant configs (stable argmax) plus
# the phone-cap composites that exercise the fine-period rescue path. The
# composite names land with the degraded tier in this same slice.
LADDER_CASES = [
    ("render_on_white", 1400),
    ("hst_star", 1400),
    ("antique_wash_chain", 1400),
    ("quarter_circle_fine", 1400),
    ("two_color_garbage", 1400),
]
