"""Evaluation metrics for the photo-reality evidence base (sprint 3, S0).

These are harness measurements, not pipeline stages: quad IoU against a known
placement, exact grid-dims match, cell accuracy on label grids, and palette
fidelity as the max Lab distance over matched entries. The polygon math is
pure numpy (Sutherland-Hodgman clip + shoelace area) so the same code path
produces identical values on native cv2 5.x and the wasm cv2 4.11 wheel.
"""

import numpy as np

from qrep.vision.compare import _lab_of_hex

Point = tuple[float, float]


def _shoelace_area(points: np.ndarray) -> float:
    x, y = points[:, 0], points[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def _as_ccw(points: list[Point]) -> np.ndarray:
    arr = np.asarray(points, dtype=np.float64)
    if _shoelace_area(arr) < 0:
        arr = arr[::-1]
    return arr


def _clip(subject: np.ndarray, clip_poly: np.ndarray) -> np.ndarray:
    """Sutherland-Hodgman: clip a convex subject polygon by a CCW convex clip
    polygon. Returns the intersection polygon (possibly empty)."""
    output = subject
    n = len(clip_poly)
    for i in range(n):
        if len(output) == 0:
            break
        a, b = clip_poly[i], clip_poly[(i + 1) % n]
        edge = b - a
        input_pts = output
        output_list: list[np.ndarray] = []
        # inside = left of the directed edge a->b (CCW polygon interior)
        cross = edge[0] * (input_pts[:, 1] - a[1]) - edge[1] * (input_pts[:, 0] - a[0])
        for j in range(len(input_pts)):
            current, prev = input_pts[j], input_pts[j - 1]
            cur_in, prev_in = cross[j] >= 0, cross[j - 1] >= 0
            if cur_in != prev_in:
                d = current - prev
                denom = edge[0] * d[1] - edge[1] * d[0]
                if abs(denom) > 1e-12:
                    t = (edge[0] * (a[1] - prev[1]) - edge[1] * (a[0] - prev[0])) / denom
                    output_list.append(prev + t * d)
            if cur_in:
                output_list.append(current)
        output = np.array(output_list) if output_list else np.empty((0, 2))
    return output


def quad_iou(quad_a: list[Point], quad_b: list[Point]) -> float:
    """Intersection-over-union of two convex quads, in [0, 1]."""
    a, b = _as_ccw(quad_a), _as_ccw(quad_b)
    area_a, area_b = _shoelace_area(a), _shoelace_area(b)
    if area_a <= 0 or area_b <= 0:
        return 0.0
    intersection = _clip(a, b)
    inter_area = abs(_shoelace_area(intersection)) if len(intersection) >= 3 else 0.0
    union = area_a + area_b - inter_area
    return inter_area / union if union > 0 else 0.0


def grid_dims_match(truth_dims: tuple[int, int], recovered_dims: tuple[int, int]) -> bool:
    """Exact (rows, cols) equality; a transposed answer is not a match."""
    return tuple(truth_dims) == tuple(recovered_dims)


def cell_accuracy(
    truth_cells: list[list],
    recovered_cells: list[list],
    mapping: dict | None = None,
) -> tuple[float, int]:
    """Fraction of agreeing cells over the overlapping top-left region.

    Labels are compared as-is; an optional mapping translates recovered
    labels into truth labels first (the palette-permutation case). Returns
    (accuracy, compared_cells); an empty overlap is (0.0, 0) by contract.
    """
    rows = min(len(truth_cells), len(recovered_cells))
    if rows == 0:
        return 0.0, 0
    cols = min(
        min(len(r) for r in truth_cells[:rows]),
        min(len(r) for r in recovered_cells[:rows]),
    )
    if cols == 0:
        return 0.0, 0
    correct = 0
    for r in range(rows):
        for c in range(cols):
            recovered = recovered_cells[r][c]
            if mapping is not None:
                recovered = mapping.get(recovered, recovered)
            if recovered == truth_cells[r][c]:
                correct += 1
    compared = rows * cols
    return correct / compared, compared


def palette_fidelity_lab(
    truth_lab: list[tuple[float, float, float]],
    recovered_lab: list[tuple[float, float, float]],
) -> float:
    """Max Lab distance over greedily matched palette entries.

    Greedy bijective matching in recovered order (the compare.map_palettes
    convention). Unmatched entries on EITHER side contribute their distance
    to the nearest entry on the other side: a merged fabric (k too small)
    and a phantom fabric (k too large) both hurt fidelity.
    """
    truth = [np.asarray(t, dtype=np.float64) for t in truth_lab]
    recovered = [np.asarray(r, dtype=np.float64) for r in recovered_lab]
    if not truth or not recovered:
        return float("inf")
    distances: list[float] = []
    used: set[int] = set()
    unmatched_recovered: list[np.ndarray] = []
    for rec in recovered:
        candidates = [
            (float(np.linalg.norm(rec - t)), i) for i, t in enumerate(truth) if i not in used
        ]
        if not candidates:
            unmatched_recovered.append(rec)
            continue
        dist, best = min(candidates)
        distances.append(dist)
        used.add(best)
    for i, t in enumerate(truth):
        if i not in used:
            distances.append(min(float(np.linalg.norm(t - rec)) for rec in recovered))
    for rec in unmatched_recovered:
        distances.append(min(float(np.linalg.norm(rec - t)) for t in truth))
    return max(distances)


def palette_fidelity_hex(truth_hex: list[str], recovered_hex: list[str]) -> float:
    """palette_fidelity_lab over hex colors, via the compare.py Lab convention."""
    truth = [tuple(_lab_of_hex(c)) for c in truth_hex]
    recovered = [tuple(_lab_of_hex(c)) for c in recovered_hex]
    return palette_fidelity_lab(truth, recovered)
