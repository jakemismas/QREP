"""Cell fabric assignment: median cell color in Lab to the nearest palette
entry, with a per-cell margin confidence.

The margin is the RELATIVE margin (d2 - d1) / d2 rather than the raw Lab
distance difference the design doc sketches: the schema requires cell
confidence in [0, 1], and the relative form is scale-free in Lab. Same
ordering, bounded range."""

import cv2
import numpy as np
from pydantic import BaseModel


class CellsResult(BaseModel):
    assignments: list[list[int]]  # palette index per cell
    cell_confidence: list[list[float]]  # relative margin per cell
    confidence: float  # mean margin


def assign_cells(
    image_bgr: np.ndarray,
    x_boundaries: list[float],
    y_boundaries: list[float],
    centers_lab: list[list[float]],
) -> CellsResult:
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2Lab).astype(np.float32)
    centers = np.array(centers_lab, dtype=np.float32)
    assignments: list[list[int]] = []
    margins: list[list[float]] = []
    for r in range(len(y_boundaries) - 1):
        row_assign: list[int] = []
        row_margin: list[float] = []
        y0, y1 = int(round(y_boundaries[r])), int(round(y_boundaries[r + 1]))
        for c in range(len(x_boundaries) - 1):
            x0, x1 = int(round(x_boundaries[c])), int(round(x_boundaries[c + 1]))
            patch = lab[max(y0, 0) : max(y1, y0 + 1), max(x0, 0) : max(x1, x0 + 1)]
            median = np.median(patch.reshape(-1, 3), axis=0)
            distances = np.linalg.norm(centers - median, axis=1)
            order = np.argsort(distances)
            nearest = int(order[0])
            d1 = float(distances[order[0]])
            d2 = float(distances[order[1]]) if len(order) > 1 else d1 + 1.0
            margin = (d2 - d1) / d2 if d2 > 0 else 0.0
            row_assign.append(nearest)
            row_margin.append(max(0.0, min(1.0, margin)))
        assignments.append(row_assign)
        margins.append(row_margin)
    flat = [m for row in margins for m in row]
    return CellsResult(
        assignments=assignments,
        cell_confidence=margins,
        confidence=float(np.mean(flat)) if flat else 0.0,
    )
