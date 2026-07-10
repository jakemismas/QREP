"""Grid estimation: edge projections plus autocorrelation for pitch and phase.

Works on the rectified quilt image (border included). The border band has no
interior edges, so the autocorrelation pitch comes from the center field; the
phase then places grid lines across the whole quilt, and border detection
later decides which outer strips break periodicity.
"""

import cv2
import numpy as np
from pydantic import BaseModel

from qrep.vision.repeats import BlockLatticeResult
from qrep.vision.verdict import INTEGER_RATIO_EPSILON, T1, T4

MIN_PITCH_PX = 5

# --- S3 plausibility guards (sprint 3, issue #69) --------------------------
# NO_EDGE_FLOOR: mean absolute Sobel response per pixel below which an image
# has no piecing edges at all (measured populations: no-pattern panels
# <= 0.04, the weakest patterned fixture - the low-contrast HST pair -
# >= 0.95; the floor sits 7x above the former, 3x below the latter).
NO_EDGE_FLOOR = 0.3
# Guard (a) isotropy tolerance TOL(m) = BASE + FACTOR * warp_magnitude.
# Hand derivation (test_grid_guards.py header): the warp target preserves
# image-plane edge lengths; a corner pull of m*max_dim moves opposite edge
# lengths apart by up to 2*m*max_dim and max_dim/extent <= 1.5 over our
# aspect range, bounding the legitimate pitch-ratio skew at ~3m; 0.06
# covers frontal rounding jitter.
ISOTROPY_BASE_TOL = 0.06
ISOTROPY_WARP_FACTOR = 3.0
# S4 (issue #70) integer-ratio feedback: candidates period/k, k = 1..MAX_K,
# scored by the same lattice fit as the re-search; the SMALLEST comparably
# strong candidate wins (grid.py's fundamental philosophy), and a winner
# within 1% of the current pitch keeps the current float bit-exactly.
FEEDBACK_MAX_K = 24
FEEDBACK_COMPARABLE = 0.5
FEEDBACK_REFINE = 1.05  # same-lattice candidate adopted only on a 5%+ better fit
# Confidence cap when a guard's violation stands: strictly below the frozen
# verdict floor T1 = 0.60, so S4's tree reads the result as no_grid.
GUARD_CONFIDENCE_CAP = 0.5
HARMONIC_FACTORS = (1.0, 2.0, 3.0, 0.5, 1.0 / 3.0)


def cell_count_bounds(extent_px: int) -> tuple[int, int]:
    """Plausible recovered cells per axis: [2, extent / MIN_PITCH_PX].

    Product decision (recorded on issue #69): the lower bound is 2 because
    a one-cell axis has no interior grid line to detect; the upper bound is
    the detector envelope - a pitch below MIN_PITCH_PX is unresolvable, so
    claiming more cells than extent/MIN_PITCH_PX contradicts the detector
    itself. Derived from the envelope, not from the design doc.
    """
    return 2, extent_px // MIN_PITCH_PX


class AxisGrid(BaseModel):
    pitch: float
    offset: float  # first grid line position in [0, pitch)
    boundaries: list[float]  # cell edges including 0 and the image extent
    confidence: float


class GridResult(BaseModel):
    x: AxisGrid
    y: AxisGrid
    diagnosis: str | None = None  # S3 guard verdict; None on a clean read

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
    # S3 (issue #69, the #33 AC1 class): a SYSTEMATIC pitch alternation
    # (cells 14/16 px) plateaus the fundamental peak and the parabolic fit
    # lands up to half a pixel off. The multi-harmonic average - autocorr
    # peaks near k * fundamental divided by k - is immune to the plateau.
    # It replaces the parabolic estimate ONLY when the two disagree by
    # more than 1 percent, so clean renders keep bit-identical floats.
    base = lo + fundamental
    harmonic_estimates: list[float] = []
    for k in range(2, 7):
        center = k * base
        if center + 2 >= len(corr):
            break
        lo_k, hi_k = center - 2, center + 3
        segment = corr[lo_k:hi_k]
        peak_at = lo_k + int(np.argmax(segment))
        if corr[peak_at] > 0:
            harmonic_estimates.append(peak_at / k)
    if harmonic_estimates:
        harmonic = float(np.mean(harmonic_estimates))
        if abs(harmonic - pitch) / max(harmonic, 1e-9) > 0.01:
            pitch = harmonic
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


def _lattice_score(profile: np.ndarray, pitch: float) -> float:
    """Lattice-fit score for a pitch candidate on the RAW profile.

    A line HITS when it lands within 1 px of a genuine spike (value at
    least mean + 0.5 std - plain above-mean is too weak on dense curved
    content, where every position clears the mean). Score = hit_fraction
    squared times the mean hit energy: the squared fraction punishes
    lattices whose extra lines land on nothing (a too-fine pitch), the
    mean (not total) energy stops line COUNT from beating line QUALITY."""
    if pitch < MIN_PITCH_PX or pitch > len(profile) / 2:
        return 0.0
    offset = _find_offset(profile, pitch)
    lines = np.arange(offset, len(profile), pitch)
    idx = np.clip(np.round(lines).astype(int), 0, len(profile) - 1)
    if idx.size == 0:
        return 0.0
    floor = float(profile.mean()) + 0.5 * float(profile.std())
    hits = 0
    captured = 0.0
    for i in idx:
        lo, hi = max(0, i - 1), min(len(profile), i + 2)
        peak = float(profile[lo:hi].max())
        if peak >= floor:
            hits += 1
            captured += peak
    if hits == 0:
        return 0.0
    fraction = hits / idx.size
    return fraction * fraction * (captured / hits)


def _lattice_prominence(profile: np.ndarray, pitch: float) -> float:
    """Periodicity strength of an ADOPTED lattice: the strongest normalized
    RAW-profile autocorrelation over its first few multiples. The binarized
    spike train weights all lines equally, which under-represents a lattice
    whose alternate boundaries are legitimately weak (merged piecing pairs);
    the raw profile keeps that structure. Adopted paths only - the clean
    detection path keeps the sprint 1 binarized prominence bit-exactly."""
    corr = _autocorrelate(profile)
    best = 0.0
    for m in range(1, 5):
        lag = int(round(pitch * m))
        if 0 < lag < len(corr):
            best = max(best, float(corr[lag]))
    return max(0.0, min(1.0, best))


def _isotropy_tolerance(warp_magnitude: float) -> float:
    return ISOTROPY_BASE_TOL + ISOTROPY_WARP_FACTOR * warp_magnitude


def _apply_period_feedback(
    profile: np.ndarray, pitch: float, prominence: float, period: float, extent: int
) -> tuple[float, float]:
    """S4 integer-ratio feedback: the image-level period constrains the
    pitch to period/k; adopt the smallest comparably strong candidate."""
    if period <= 0:
        return pitch, prominence
    # feedback engages only on the plan's own triggers: the read is failing
    # (below the verdict floor) or the period contradicts the pitch (non-
    # integer ratio). A healthy, integer-confirmed read is left untouched -
    # the L0-L2 pin freezes its floats and prominences byte-exactly.
    ratio = period / max(pitch, 1e-9)
    ratio_ok = round(ratio) >= 1 and abs(ratio - round(ratio)) <= INTEGER_RATIO_EPSILON
    if prominence >= T1 and ratio_ok:
        return pitch, prominence
    candidates = sorted(
        {
            period / k
            for k in range(1, FEEDBACK_MAX_K + 1)
            if MIN_PITCH_PX <= period / k <= extent / 4
        }
    )
    if not candidates:
        return pitch, prominence
    current_score = _lattice_score(profile, pitch)
    scored = [(c, _lattice_score(profile, c)) for c in candidates]
    best = max([current_score] + [s for _c, s in scored])
    if best <= 0:
        return pitch, prominence
    for candidate, score in scored:  # ascending: smallest comparable wins
        if score >= FEEDBACK_COMPARABLE * best:
            if abs(candidate - pitch) / max(pitch, 1e-9) <= 0.01:
                # same lattice - but a parabolic mis-rounding of the pitch
                # can park every sampled lag one pixel off a razor-sharp
                # autocorr peak (council finding, issue #70: raw corr 0.36
                # at lag 85 vs 0.82 at 86 on the HST star). The period-
                # derived candidate replaces it only when its lattice fit
                # is MATERIALLY better AND the current measurement sits
                # below the verdict floor - the only regime the artifact
                # matters; healthy reads keep sprint 1's floats bit-exact
                # (the L0-L2 pin is the contract there).
                if score >= FEEDBACK_REFINE * current_score and prominence < T1:
                    return float(candidate), _lattice_prominence(profile, candidate)
                return pitch, prominence
            return float(candidate), _lattice_prominence(profile, candidate)
    return pitch, prominence


def _pitch_skew(pitch_x: float, pitch_y: float) -> float:
    ratio = max(pitch_x, pitch_y) / max(min(pitch_x, pitch_y), 1e-9)
    return ratio - 1.0


def estimate_grid(
    image_bgr: np.ndarray,
    mask: np.ndarray | None = None,
    warp_magnitude: float = 0.0,
    period_hint: tuple[float, float] | None = None,
    block_lattice: BlockLatticeResult | None = None,
) -> GridResult:
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

    # too-short depends only on extent, so it is checked FIRST: the answer
    # must not vary with how much edge energy a runtime's crop happens to
    # keep (max_pitch = extent // 4 must exceed MIN_PITCH_PX to search)
    if width // 4 <= MIN_PITCH_PX or height // 4 <= MIN_PITCH_PX:
        raise ValueError("profile too short for grid detection")

    # S3 no-edge floor: an image with essentially no piecing edges has no
    # grid to find; the pipeline converts this to a typed no_periodicity
    if (
        float(grad_x.mean()) / max(height, 1) < NO_EDGE_FLOOR
        and float(grad_y.mean()) / max(width, 1) < NO_EDGE_FLOOR
    ):
        raise ValueError("no periodicity found in edge profile")

    pitch_x, prom_x = _find_pitch(grad_x, max_pitch=width // 4)
    pitch_y, prom_y = _find_pitch(grad_y, max_pitch=height // 4)

    if period_hint is not None:
        pitch_x, prom_x = _apply_period_feedback(grad_x, pitch_x, prom_x, period_hint[0], width)
        pitch_y, prom_y = _apply_period_feedback(grad_y, pitch_y, prom_y, period_hint[1], height)

    # S1 (issue #93) block-lattice hint: the peak-contrast 2D evidence period
    # feeds the SAME feedback, per axis, ONLY where the 1D read is failing
    # (prominence < T1), the block-lattice statistic clears T4, and the block
    # period is at least the cell pitch. The T2 healthy-photo hint above takes
    # precedence: where it lifted prominence to T1 the gate below is closed, so
    # a passing read is byte-untouched. This adopts a better PITCH; the decisive
    # S0 finding is that the recomputed prominence stays below T1 (rescue is the
    # additive corroboration leg S2 lands), so this leg never flips a verdict.
    if block_lattice is not None and block_lattice.snr >= T4:
        if prom_x < T1 and block_lattice.period_x >= pitch_x:
            pitch_x, prom_x = _apply_period_feedback(
                grad_x, pitch_x, prom_x, float(block_lattice.period_x), width
            )
        if prom_y < T1 and block_lattice.period_y >= pitch_y:
            pitch_y, prom_y = _apply_period_feedback(
                grad_y, pitch_y, prom_y, float(block_lattice.period_y), height
            )

    diagnosis: str | None = None
    tolerance = _isotropy_tolerance(warp_magnitude)
    if _pitch_skew(pitch_x, pitch_y) > tolerance:
        # guard (a) fired: joint harmonic re-search over both axes. Among
        # ISOTROPIC candidate pairs comparably strong (>= 0.5x the best
        # pair), the SMALLEST pitches win - the same fundamental philosophy
        # as _find_pitch, so a strong 2x harmonic pair cannot outrank the
        # true pitch pair that also fits. No viable pair: the violation
        # stands and confidence is capped below T1.
        pairs: list[tuple[float, float, float]] = []
        for fx in HARMONIC_FACTORS:
            for fy in HARMONIC_FACTORS:
                cx, cy = pitch_x * fx, pitch_y * fy
                if _pitch_skew(cx, cy) > tolerance:
                    continue
                score = _lattice_score(grad_x, cx) + _lattice_score(grad_y, cy)
                if score > 0:
                    pairs.append((score, cx, cy))
        if pairs:
            best_score = max(score for score, _cx, _cy in pairs)
            viable = [
                (cx, cy) for score, cx, cy in pairs if score >= FEEDBACK_COMPARABLE * best_score
            ]
            pitch_x, pitch_y = min(viable, key=lambda p: p[0] + p[1])
            prom_x = _lattice_prominence(grad_x, pitch_x)
            prom_y = _lattice_prominence(grad_y, pitch_y)
        else:
            diagnosis = "anisotropic_pitch"
            prom_x = min(prom_x, GUARD_CONFIDENCE_CAP)
            prom_y = min(prom_y, GUARD_CONFIDENCE_CAP)

    offset_x = _find_offset(grad_x, pitch_x)
    offset_y = _find_offset(grad_y, pitch_y)
    boundaries_x = _boundaries(width, pitch_x, offset_x, grad_x)
    boundaries_y = _boundaries(height, pitch_y, offset_y, grad_y)

    # guard (b): recovered cell counts must fit the detector envelope
    if diagnosis is None:
        low_x, high_x = cell_count_bounds(width)
        low_y, high_y = cell_count_bounds(height)
        cells_x = len(boundaries_x) - 1
        cells_y = len(boundaries_y) - 1
        if not (low_x <= cells_x <= high_x and low_y <= cells_y <= high_y):
            diagnosis = "implausible_dims"
            prom_x = min(prom_x, GUARD_CONFIDENCE_CAP)
            prom_y = min(prom_y, GUARD_CONFIDENCE_CAP)

    # a read whose periodicity is already below the frozen verdict floor
    # carries the structured reason S4's tree folds in; nothing is capped
    # here - the confidence already says it
    if diagnosis is None and min(prom_x, prom_y) < T1:
        diagnosis = "weak_periodicity"

    return GridResult(
        x=AxisGrid(
            pitch=pitch_x,
            offset=offset_x,
            boundaries=boundaries_x,
            confidence=prom_x,
        ),
        y=AxisGrid(
            pitch=pitch_y,
            offset=offset_y,
            boundaries=boundaries_y,
            confidence=prom_y,
        ),
        diagnosis=diagnosis,
    )
