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


class PaletteResult(BaseModel):
    colors_bgr: list[tuple[int, int, int]]
    colors_hex: list[str]
    centers_lab: list[list[float]]
    k: int
    confidence: float  # mean simplified silhouette


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
    image_bgr: np.ndarray, fabrics: int | None = None, mask: np.ndarray | None = None
) -> PaletteResult:
    """K-means over quilt pixels only: with a mask, background wedges between
    the quad and its bounding box are excluded per the design doc.

    fabrics forces k (the CLI escape hatch); otherwise k maximizes silhouette.
    """
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2Lab).reshape(-1, 3).astype(np.float32)
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
