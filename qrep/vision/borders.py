"""Border detection: outermost cell strips that break grid periodicity.

A border strip is a full row or column of cells with one dominant fabric.
The fixture border is 2.5 cell pitches wide by design; that IS the
periodicity break the grid phase exposes (a half-pitch partial strip at the
edge plus two full strips), so the three uniform outer strips on each side
are the border.
"""

import numpy as np
from pydantic import BaseModel

UNIFORMITY = 0.93  # tolerate a few noisy cells per strip at L1/L2


class BorderResult(BaseModel):
    strips: dict[str, int]  # uniform strips per side: left right top bottom
    widths_px: dict[str, float]
    fabric_index: int | None
    confidence: float


def detect_borders(
    assignments: list[list[int]],
    x_boundaries: list[float],
    y_boundaries: list[float],
) -> BorderResult:
    grid = np.array(assignments)
    rows, cols = grid.shape

    def uniformity(values: np.ndarray) -> tuple[float, int]:
        # trimmed modal fraction: up to 15 percent of a strip may be occluded
        # or noisy (an L3 corner occluder) without hiding a real border strip;
        # interior rows/cols stay far below the bar (fixture worst case 0.71
        # trimmed vs the 0.93 threshold)
        counts = np.bincount(values)
        modal = int(np.argmax(counts))
        keep = max(1, len(values) - int(0.15 * len(values)))
        return min(1.0, float(counts[modal] / keep)), modal

    strips = {"left": 0, "right": 0, "top": 0, "bottom": 0}
    fabrics: list[int] = []
    scores: list[float] = []
    # scan inward from each edge; stop at the first non-uniform strip and
    # never consume more than a quarter of the grid per side
    for side, take in (
        ("left", lambda i: grid[:, i]),
        ("right", lambda i: grid[:, cols - 1 - i]),
        ("top", lambda i: grid[i, :]),
        ("bottom", lambda i: grid[rows - 1 - i, :]),
    ):
        limit = (cols if side in ("left", "right") else rows) // 4
        for i in range(limit):
            score, modal = uniformity(take(i))
            if score < UNIFORMITY:
                break
            strips[side] += 1
            fabrics.append(modal)
            scores.append(score)

    widths_px = {
        "left": float(x_boundaries[strips["left"]] - x_boundaries[0]),
        "right": float(x_boundaries[-1] - x_boundaries[len(x_boundaries) - 1 - strips["right"]]),
        "top": float(y_boundaries[strips["top"]] - y_boundaries[0]),
        "bottom": float(y_boundaries[-1] - y_boundaries[len(y_boundaries) - 1 - strips["bottom"]]),
    }
    fabric_index = None
    if fabrics:
        fabric_index = int(np.bincount(np.array(fabrics)).argmax())
    return BorderResult(
        strips=strips,
        widths_px=widths_px,
        fabric_index=fabric_index,
        confidence=float(np.mean(scores)) if scores else 1.0,
    )
