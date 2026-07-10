"""Palette extraction: seeded k-means in Lab with silhouette k-selection.

k scans 2..8 maximizing mean SIMPLIFIED silhouette (per point: a = distance
to own centroid, b = distance to nearest other centroid, s = (b-a)/max(a,b)).
The classic pairwise silhouette on 20k points would need 400M distances; the
simplified form is deterministic, O(nk), and standard. Documented deviation:
none in selection behavior for well-separated fabric clusters.
"""

import cv2
import numpy as np
from pydantic import BaseModel

SUBSAMPLE = 20_000
K_RANGE = range(2, 9)

# --- S5 lighting normalization (sprint 3, issue #71 / #33 AC2) -------------
# Gate: large-scale L variation, measured as p95/p5 of a heavily blurred
# (sigma = 10% of min dim) L channel over the quilt pixels. Measured
# populations: every flat-lit render and fixture <= 1.072 (the L2 render's
# deliberately mild 0.88-floor lighting is the max), the strong-gradient
# population starts at 1.45. The gate at 1.20 GUARANTEES identity on the
# L0-L2 byte-law pins while firing on real gradients.
GRADIENT_GATE = 1.20
GRADIENT_BLUR_FRACTION = 0.10


class PaletteResult(BaseModel):
    colors_bgr: list[tuple[int, int, int]]
    colors_hex: list[str]
    centers_lab: list[list[float]]
    k: int
    confidence: float  # mean simplified silhouette


def _fit_illumination(luminance: np.ndarray, selected: np.ndarray) -> np.ndarray:
    """Least-squares quadratic illumination field over the selected pixels.

    The 6x6 normal-equation solve is local Gaussian elimination
    (deterministic); the accumulation uses the platform BLAS, so
    cross-runtime agreement is semantic (CV outputs carry no cross-runtime
    byte promises), while the L0-L2 byte pins are safe because the gate
    never fires on flat-lit renders. Coordinates are normalized to [0, 1]
    to keep the system well conditioned."""
    h, w = luminance.shape
    ys, xs = np.nonzero(selected)
    if ys.size > 20_000:
        step = ys.size // 20_000 + 1
        ys, xs = ys[::step], xs[::step]
    x = xs.astype(np.float64) / max(w - 1, 1)
    y = ys.astype(np.float64) / max(h - 1, 1)
    design = np.stack([np.ones_like(x), x, y, x * x, y * y, x * y], axis=1)
    target = luminance[ys, xs].astype(np.float64)
    ata = design.T @ design
    atb = design.T @ target
    coeffs = _solve_sym(ata, atb)
    gx = np.arange(w, dtype=np.float64) / max(w - 1, 1)
    gy = np.arange(h, dtype=np.float64) / max(h - 1, 1)
    gxx, gyy = np.meshgrid(gx, gy)
    field = (
        coeffs[0]
        + coeffs[1] * gxx
        + coeffs[2] * gyy
        + coeffs[3] * gxx * gxx
        + coeffs[4] * gyy * gyy
        + coeffs[5] * gxx * gyy
    )
    return np.maximum(field, 1.0).astype(np.float32)


def _solve_sym(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """6x6 Gaussian elimination with partial pivoting (deterministic)."""
    n = a.shape[0]
    m = np.concatenate([a.copy(), b.reshape(-1, 1)], axis=1)
    for i in range(n):
        pivot = i + int(np.argmax(np.abs(m[i:, i])))
        if pivot != i:
            m[[i, pivot]] = m[[pivot, i]]
        m[i] = m[i] / m[i, i]
        for j in range(n):
            if j != i:
                m[j] = m[j] - m[j, i] * m[i]
    return m[:, n]


def _simplified_silhouette(points: np.ndarray, centers: np.ndarray, labels: np.ndarray) -> float:
    distances = np.linalg.norm(points[:, None, :] - centers[None, :, :], axis=2)
    n = points.shape[0]
    own = distances[np.arange(n), labels]
    distances[np.arange(n), labels] = np.inf
    nearest_other = distances.min(axis=1)
    denom = np.maximum(own, nearest_other)
    denom[denom == 0] = 1.0
    return float(np.mean((nearest_other - own) / denom))


def extract_palette(
    image_bgr: np.ndarray,
    fabrics: int | None = None,
    mask: np.ndarray | None = None,
    lighting_detrend: bool = False,
) -> PaletteResult:
    """K-means over quilt pixels only: with a mask, background wedges between
    the quad and its bounding box are excluded per the design doc.

    fabrics forces k (the CLI escape hatch); otherwise k maximizes silhouette.
    lighting_detrend (S5, issue #71): the caller asserts the image is a
    TRUSTED quilt crop (detection tiers 0-2 or user corners). On a tier-3
    full frame the low-frequency L field measures content (quilt vs
    background), not lighting - detrending there merges fabrics with the
    background (measured on #71), so the pipeline keeps it off.
    """
    source_bgr = image_bgr
    if lighting_detrend:
        # S5 (#33 AC2): flatten large-scale luminance variation before
        # k selection and kmeans, gated so flat-lit renders take the
        # sprint 1 code path bit-exactly (constants documented above).
        # The GATE uses the blurred-L p95/p5 ratio (the measured
        # populations above); the CORRECTION field is a least-squares
        # quadratic in (x, y) - a Gaussian field is border-biased
        # (reflection flattens the ramp near edges, under-correcting the
        # dark corner by ~25%, measured on #71), while a quadratic matches
        # linear and gently curved lighting exactly. Correction is
        # MULTIPLICATIVE flat-fielding in BGR anchored at the field's p95
        # (the least-shadowed illumination): dimming scales chroma as well
        # as L, so an additive L shift leaves colors desaturated.
        luminance = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2Lab)[:, :, 0].astype(np.float32)
        blur_sigma = max(2.0, GRADIENT_BLUR_FRACTION * min(luminance.shape))
        blurred = cv2.GaussianBlur(luminance, (0, 0), blur_sigma)
        selected = mask > 0 if mask is not None else np.ones(luminance.shape, dtype=bool)
        gate_field = blurred[selected]
        p5, p95 = np.percentile(gate_field, 5), np.percentile(gate_field, 95)
        if p5 > 0 and p95 / p5 > GRADIENT_GATE:
            # the field must be fit on LINEAR luminance: Lab L is cube-root
            # compressed, so an L-derived ratio under-corrects a 0.45
            # dimming to ~0.77 (measured on #71); grayscale is linear in
            # the multiplicative lighting model
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
            field = _fit_illumination(gray, selected)
            # anchor at the fitted field's masked MAXIMUM: the field is a
            # smooth polynomial (no outliers to be robust against), and a
            # percentile anchor under-reaches the bright end by the ramp's
            # tail thinness (~7%, measured on #71), leaving every corrected
            # color uniformly dark by the same factor
            anchor = float(field[selected].max())
            ratio = np.clip(field / max(anchor, 1e-6), 0.3, 1.0)
            source_bgr = np.clip(
                image_bgr.astype(np.float32) / ratio[:, :, None], 0, 255
            ).astype(np.uint8)
    lab = cv2.cvtColor(source_bgr, cv2.COLOR_BGR2Lab).reshape(-1, 3).astype(np.float32)
    if mask is not None:
        lab = lab[mask.reshape(-1) > 0]
    rng = np.random.default_rng(42)
    if lab.shape[0] > SUBSAMPLE:
        idx = rng.choice(lab.shape[0], SUBSAMPLE, replace=False)
        sample = lab[np.sort(idx)]
    else:
        sample = lab

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.5)
    best: tuple[float, int, np.ndarray, np.ndarray] | None = None
    candidates = [fabrics] if fabrics is not None else list(K_RANGE)
    for k in candidates:
        cv2.setRNGSeed(42)
        _compactness, labels, centers = cv2.kmeans(
            sample, k, None, criteria, 10, cv2.KMEANS_PP_CENTERS
        )
        score = _simplified_silhouette(sample, centers, labels.ravel())
        if best is None or score > best[0]:
            best = (score, k, centers, labels)
    score, k, centers, _labels = best

    # order palette entries darkest-to-lightest L for determinism
    order = np.argsort(centers[:, 0])
    centers = centers[order]
    centers_bgr = cv2.cvtColor(centers.reshape(1, -1, 3).astype(np.uint8), cv2.COLOR_Lab2BGR)
    colors_bgr = [tuple(int(v) for v in c) for c in centers_bgr.reshape(-1, 3)]
    colors_hex = [f"#{b[2]:02x}{b[1]:02x}{b[0]:02x}" for b in colors_bgr]
    return PaletteResult(
        colors_bgr=colors_bgr,
        colors_hex=colors_hex,
        centers_lab=[[float(v) for v in c] for c in centers],
        k=k,
        confidence=max(0.0, min(1.0, score)),
    )
