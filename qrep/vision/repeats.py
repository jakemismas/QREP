"""Repeat detection (sprint 1 label detector + sprint 3 S4 image level).

Label level: mean(a == b) over the overlap of a grid and its shifted self IS
the normalized 2D autocorrelation of the one-hot fabric encoding, evaluated
axis-aligned. The >= MATCH_THRESHOLD exact-match early return is the
sprint 1 path, preserved VERBATIM (it keeps the L0-L2 legacy pin byte-law
trivially); the S4 soft vote engages only when no exact match exists and
picks the SMALLEST period whose score is within SOFT_FACTOR of the best,
preserving minimal-period selection on noisy grids.

Image level (S4, issue #70): FFT-accelerated normalized autocorrelation of
the high-passed rectified grayscale over a FIXED-FRACTION central inset
(the detected-border interior is garbage exactly when this matters most).
Fundamental selection mirrors grid.py's frozen rule: the smallest local
maximum comparably strong (>= 0.5x) to the strongest, under a max-lag cap.

Intra-cell coherence (S4): edge energy inside cells vs on the boundary
bands after a pitch-scaled blur (sigma = pitch/8) that kills print speckle
but keeps piecing seams. Measured S0 populations: squares <= 0.904 (the
quilting-shadow fixture is the worst), non-square >= 1.216; the frozen
T3 = 1.05 separates them.
"""

import cv2
import numpy as np
from pydantic import BaseModel

MATCH_THRESHOLD = 0.999  # exact repeat on clean grids; tolerate a stray cell
SOFT_FACTOR = 0.95  # soft vote: smallest period within 5% of the best score
INSET_FRACTION = 0.75  # fixed central inset for image-level periodicity
MAX_LAG_FRACTION = 0.5  # periodicity search cap, fraction of inset extent
FUNDAMENTAL_FACTOR = 0.5  # mirrors grid.py's comparably-strong rule
HIGHPASS_SIGMA_FRACTION = 0.05  # detrend Gaussian, fraction of min dim
COHERENCE_BAND = 0.12  # boundary band half-width, in pitch units
VOTE_MIN_COPIES = 3  # frozen: minimum periodic copies on a voted axis
VOTE_HIGH_MARGIN = 0.8  # cells at or above this margin are never mutated
SUBLATTICE_MIN_ENERGY = 0.25  # admissibility floor for the half-pitch probe

# --- S1 (issue #93): block-lattice SNR evidence detector -----------------
# The FROZEN ladder + SNR shape, proposed by S0's baseline report on #92 and
# frozen by Jake on #91 (2026-07-10). These literals MIRROR the wasm-gate op
# in tests/fixtures/wasm_gate/ops.py exactly (production cannot import from
# tests/, so they are re-declared here and a cross-check test pins the two
# byte-aligned). A high pass only removes structure FINER than its sigma, so
# the fine rungs rescue the phone-cap ~10 px block that a single fixed detrend
# sigma collapses to SNR 0; large motif periods survive every rung.
LADDER_SIGMAS = (1.5, 3.0, 6.0)
SNR_HARMONICS = (1, 2, 3)  # fundamental + first two harmonics of the comb
SNR_MIN_LAG = 5  # grid.MIN_PITCH_PX; ignore the zero-lag envelope
SNR_STD_FLOOR = 1e-6  # a flat band carries no SNR
SNR_CHANNEL_FLOOR = 0.5  # a detrended channel below this std has no signal


class RepeatResult(BaseModel):
    period_rows: int  # 0 when no repeat found
    period_cols: int
    confidence: float


class PeriodicityResult(BaseModel):
    period_x: int  # 0 when no repetition found on the axis
    period_y: int
    score_x: float
    score_y: float

    @property
    def score(self) -> float:
        return max(self.score_x, self.score_y)


class BlockLatticeResult(BaseModel):
    """Peak-contrast 2D lattice evidence (S1, issue #93). period_* are 0 and
    channel is -1 when no lattice survives any ladder rung; snr is the
    min-over-axes statistic at the argmax (channel, sigma)."""

    period_x: int
    period_y: int
    snr: float  # min over axes at the argmax config: the block-lattice floor
    snr_x: float
    snr_y: float
    channel: int  # winning Lab channel index (0=L,1=a,2=b); -1 when none
    sigma: float  # winning detrend sigma; 0.0 when none


def _axis_period(grid: np.ndarray, axis: int) -> tuple[int, float]:
    n = grid.shape[axis]
    scores: list[tuple[int, float]] = []
    for shift in range(1, n // 2 + 1):
        if axis == 0:
            a, b = grid[:-shift, :], grid[shift:, :]
        else:
            a, b = grid[:, :-shift], grid[:, shift:]
        score = float(np.mean(a == b))
        if score >= MATCH_THRESHOLD:
            # sprint 1 exact path, preserved verbatim (legacy byte-law)
            return shift, score
        scores.append((shift, score))
    if not scores:
        return 0, 0.0
    best_score = max(score for _shift, score in scores)
    if best_score <= 0:
        return 0, 0.0
    # S4 soft vote: the smallest period comparably strong to the best
    for shift, score in scores:
        if score >= SOFT_FACTOR * best_score:
            return shift, score
    return 0, 0.0


def detect_repeat(assignments: list[list[int]]) -> RepeatResult:
    grid = np.array(assignments)
    period_rows, score_rows = _axis_period(grid, 0)
    period_cols, score_cols = _axis_period(grid, 1)
    return RepeatResult(
        period_rows=period_rows,
        period_cols=period_cols,
        confidence=float(min(score_rows, score_cols)),
    )


# ---------------------------------------------------------------------------
# S4 image-level periodicity
# ---------------------------------------------------------------------------


def _profile_fundamental(profile: np.ndarray) -> tuple[int, float]:
    """Smallest comparably-strong local maximum (grid.py's frozen rule)."""
    lo = 5
    if len(profile) <= lo + 2:
        return 0, 0.0
    peaks = [
        i
        for i in range(lo + 1, len(profile) - 1)
        if profile[i] >= profile[i - 1] and profile[i] >= profile[i + 1] and profile[i] > 0
    ]
    if not peaks:
        return 0, 0.0
    strongest = max(float(profile[i]) for i in peaks)
    fundamental = next(i for i in peaks if profile[i] >= FUNDAMENTAL_FACTOR * strongest)
    return fundamental, float(profile[fundamental])


def image_periodicity(image_bgr: np.ndarray) -> PeriodicityResult:
    """Normalized autocorrelation periodicity of the high-passed grayscale
    over the fixed central inset; scores are zero-lag normalized (in [-1, 1],
    ~1 at a true lattice period, ~0 for aperiodic content)."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape
    inset_y = int(round(h * (1 - INSET_FRACTION) / 2))
    inset_x = int(round(w * (1 - INSET_FRACTION) / 2))
    crop = gray[inset_y : h - inset_y, inset_x : w - inset_x]
    if crop.shape[0] < 32 or crop.shape[1] < 32:
        return PeriodicityResult(period_x=0, period_y=0, score_x=0.0, score_y=0.0)
    sigma = max(2.0, HIGHPASS_SIGMA_FRACTION * min(crop.shape))
    highpass = crop - cv2.GaussianBlur(crop, (0, 0), sigma)
    # signal floor: a panel with no pattern detrends to (near-)zero, and
    # normalizing its numerical dust would score ~1 at every lag; any real
    # pattern's detrended std is orders of magnitude above half a gray level
    if float(highpass.std()) < 0.5:
        return PeriodicityResult(period_x=0, period_y=0, score_x=0.0, score_y=0.0)
    spectrum = cv2.dft(highpass, flags=cv2.DFT_COMPLEX_OUTPUT)
    power = spectrum[..., 0] ** 2 + spectrum[..., 1] ** 2
    packed = np.stack([power, np.zeros_like(power)], axis=-1)
    autocorr = cv2.dft(
        packed, flags=cv2.DFT_INVERSE | cv2.DFT_SCALE | cv2.DFT_COMPLEX_OUTPUT
    )[..., 0]
    zero_lag = float(autocorr[0, 0])
    if zero_lag <= 0:
        return PeriodicityResult(period_x=0, period_y=0, score_x=0.0, score_y=0.0)
    max_x = int(crop.shape[1] * MAX_LAG_FRACTION)
    max_y = int(crop.shape[0] * MAX_LAG_FRACTION)
    profile_x = autocorr[0, :max_x] / zero_lag
    profile_y = autocorr[:max_y, 0] / zero_lag
    period_x, score_x = _profile_fundamental(profile_x)
    period_y, score_y = _profile_fundamental(profile_y)
    return PeriodicityResult(
        period_x=period_x, period_y=period_y, score_x=score_x, score_y=score_y
    )


# ---------------------------------------------------------------------------
# S1 block-lattice SNR evidence (issue #93)
# ---------------------------------------------------------------------------
# A faithful mirror of lab_ladder_autocorr_op in tests/fixtures/wasm_gate/
# ops.py (the wasm-gate op): normalized 2D autocorrelation of the high-passed
# best Lab channel over the frozen sigma ladder; per axis the fundamental's
# harmonic-comb SNR over a global background; statistic = min over axes at the
# argmax (channel, sigma). The op is the parity reference; this is the
# production entry the pipeline calls on the rectified quilt.


def _block_autocorr_axis_lines(field: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Zero-lag-normalized axis profiles of the 2D autocorrelation of `field`.

    Pads to cv2.getOptimalDFTSize so the two DFTs stay fast on odd widths; the
    zero pad beyond the signal divides out under the zero-lag normalization.
    Returns (profile_x over columns, profile_y over rows) or None when the
    field is flat (degenerate zero-lag)."""
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


def _block_axis_fundamental(profile: np.ndarray, hi: int) -> int:
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
    fundamental = next(i for i in peaks if window[i] >= FUNDAMENTAL_FACTOR * strongest)
    return lo + fundamental


def _block_axis_snr(profile: np.ndarray, period: int, hi: int) -> float:
    """Peak SNR of the harmonic comb over a global background.

    For each harmonic k the peak at lag k*period (with +/-1 lag jitter) is
    scored against the whole search band's median and std. A global (not local)
    background does not collapse in the trough of a clean lattice, so the
    statistic stays bounded and thresholdable; averaging over k=1..3 rewards a
    genuine comb over a lone accidental peak."""
    if period < SNR_MIN_LAG:
        return 0.0
    band = profile[SNR_MIN_LAG:hi]
    if band.size == 0:
        return 0.0
    median = float(np.median(band))
    std = float(np.std(band))
    if std < SNR_STD_FLOOR:
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


def _block_config_snr(channel: np.ndarray, sigma: float, hi_x: int, hi_y: int):
    """(min-axis SNR, period_x, period_y, snr_x, snr_y) for one (channel,
    sigma) config, or None when the detrended channel carries no signal."""
    highpass = channel - cv2.GaussianBlur(channel, (0, 0), sigma)
    if float(highpass.std()) < SNR_CHANNEL_FLOOR:
        return None
    lines = _block_autocorr_axis_lines(highpass)
    if lines is None:
        return None
    profile_x, profile_y = lines
    period_x = _block_axis_fundamental(profile_x, hi_x)
    period_y = _block_axis_fundamental(profile_y, hi_y)
    snr_x = _block_axis_snr(profile_x, period_x, hi_x)
    snr_y = _block_axis_snr(profile_y, period_y, hi_y)
    return min(snr_x, snr_y), period_x, period_y, snr_x, snr_y


def block_lattice_snr(image_bgr: np.ndarray) -> BlockLatticeResult:
    """Block-lattice evidence: the max min-axis SNR over the Lab channel sweep
    (L, a, b) and the frozen detrend-sigma ladder, with the argmax config's
    per-axis block periods. Periods are at the INPUT image resolution (no
    internal downscale, so phone-cap fine periods survive and lags stay
    integer-exact). Runs on the rectified quilt when the 1D read is failing;
    the pipeline gates the call, this function always measures."""
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2Lab).astype(np.float32)
    h, w = lab.shape[:2]
    hi_x, hi_y = w // 4, h // 4

    best = None  # (snr, period_x, period_y, snr_x, snr_y, channel, sigma)
    for channel_index in range(3):
        channel = lab[:, :, channel_index]
        for sigma in LADDER_SIGMAS:
            result = _block_config_snr(channel, sigma, hi_x, hi_y)
            if result is None:
                continue
            snr, period_x, period_y, snr_x, snr_y = result
            if best is None or snr > best[0]:
                best = (snr, period_x, period_y, snr_x, snr_y, channel_index, sigma)

    if best is None:
        return BlockLatticeResult(
            period_x=0, period_y=0, snr=0.0, snr_x=0.0, snr_y=0.0, channel=-1, sigma=0.0
        )
    return BlockLatticeResult(
        period_x=best[1],
        period_y=best[2],
        snr=best[0],
        snr_x=best[3],
        snr_y=best[4],
        channel=best[5],
        sigma=best[6],
    )


# ---------------------------------------------------------------------------
# S4 intra-cell coherence
# ---------------------------------------------------------------------------


def coherence_with_sublattice(
    image_bgr: np.ndarray, x_boundaries: list[float], y_boundaries: list[float]
) -> float:
    """Classification coherence: the max over the detected lattice and its
    half-pitch sub-lattice. Piecing hides INSIDE detected cells exactly when
    merged same-fabric pairs make alternate boundaries invisible (the HST
    pair and drunkards-path cases); the sub-lattice probe sees it. A phantom
    sub-lattice (flat squares content) is inadmissible: its boundary bands
    must carry at least SUBLATTICE_MIN_ENERGY of the detected lattice's."""
    ratio1, boundary1 = _coherence_parts(image_bgr, x_boundaries, y_boundaries)
    if boundary1 <= 0:
        return ratio1
    half_x = _with_midpoints(x_boundaries)
    half_y = _with_midpoints(y_boundaries)
    ratio2, boundary2 = _coherence_parts(image_bgr, half_x, half_y)
    if boundary2 >= SUBLATTICE_MIN_ENERGY * boundary1:
        return max(ratio1, ratio2)
    return ratio1


def _with_midpoints(boundaries: list[float]) -> list[float]:
    out: list[float] = []
    for i, b in enumerate(boundaries[:-1]):
        out.append(b)
        out.append((b + boundaries[i + 1]) / 2.0)
    out.append(boundaries[-1])
    return out


def intra_cell_coherence(
    image_bgr: np.ndarray, x_boundaries: list[float], y_boundaries: list[float]
) -> float:
    """Interior-vs-boundary edge-energy ratio on the given lattice."""
    ratio, _boundary = _coherence_parts(image_bgr, x_boundaries, y_boundaries)
    return ratio


def _coherence_parts(
    image_bgr: np.ndarray, x_boundaries: list[float], y_boundaries: list[float]
) -> tuple[float, float]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    h, w = gray.shape
    if len(x_boundaries) < 3 or len(y_boundaries) < 3:
        return 0.0, 0.0
    pitch_x = (x_boundaries[-1] - x_boundaries[0]) / (len(x_boundaries) - 1)
    pitch_y = (y_boundaries[-1] - y_boundaries[0]) / (len(y_boundaries) - 1)
    sigma = max(0.8, min(pitch_x, pitch_y) / 8.0)
    blurred = cv2.GaussianBlur(gray, (0, 0), sigma)
    energy = np.abs(cv2.Sobel(blurred, cv2.CV_32F, 1, 0)) + np.abs(
        cv2.Sobel(blurred, cv2.CV_32F, 0, 1)
    )
    near_x = np.zeros(w, dtype=bool)
    for b in x_boundaries:
        lo = max(0, int(np.floor(b - COHERENCE_BAND * pitch_x)))
        hi = min(w, int(np.ceil(b + COHERENCE_BAND * pitch_x)) + 1)
        near_x[lo:hi] = True
    near_y = np.zeros(h, dtype=bool)
    for b in y_boundaries:
        lo = max(0, int(np.floor(b - COHERENCE_BAND * pitch_y)))
        hi = min(h, int(np.ceil(b + COHERENCE_BAND * pitch_y)) + 1)
        near_y[lo:hi] = True
    boundary = near_x[None, :] | near_y[:, None]
    if not boundary.any() or boundary.all():
        return 0.0, 0.0
    boundary_mean = float(energy[boundary].mean())
    interior_mean = float(energy[~boundary].mean())
    if boundary_mean <= 0:
        return 0.0, 0.0
    return interior_mean / boundary_mean, boundary_mean


# ---------------------------------------------------------------------------
# S4 repeat voting
# ---------------------------------------------------------------------------


def vote_cells(
    assignments: list[list[int]],
    margins: list[list[float]],
    period_rows: int,
    period_cols: int,
) -> tuple[list[list[int]], int]:
    """Confidence-weighted plurality over periodic copies.

    Labels are categorical, so this is a WEIGHTED PLURALITY, never a median.
    Guards, all structural: the vote runs only when the voted axis has at
    least VOTE_MIN_COPIES periodic copies, and cells at or above
    VOTE_HIGH_MARGIN are never mutated - the post-vote high-margin
    agreement invariant holds by construction. Returns (voted grid, number
    of cells changed, whether the vote applied at all)."""
    grid = np.array(assignments)
    weight = np.array(margins, dtype=np.float64)
    rows, cols = grid.shape
    vote_rows = period_rows > 0 and rows // period_rows >= VOTE_MIN_COPIES
    vote_cols = period_cols > 0 and cols // period_cols >= VOTE_MIN_COPIES
    if not (vote_rows or vote_cols):
        return grid.tolist(), 0, False

    voted = grid.copy()
    changed = 0
    labels = np.unique(grid)
    for r in range(rows):
        for c in range(cols):
            if weight[r, c] >= VOTE_HIGH_MARGIN:
                continue
            copies_r = range(r % period_rows, rows, period_rows) if vote_rows else [r]
            copies_c = range(c % period_cols, cols, period_cols) if vote_cols else [c]
            tally: dict[int, float] = {int(label): 0.0 for label in labels}
            for rr in copies_r:
                for cc in copies_c:
                    tally[int(grid[rr, cc])] += float(weight[rr, cc])
            winner = max(tally.items(), key=lambda kv: (kv[1], -kv[0]))[0]
            if winner != int(grid[r, c]):
                voted[r, c] = winner
                changed += 1
    return voted.tolist(), changed, True
