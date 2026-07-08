"""Repeat detection: axis-aligned autocorrelation on the fabric-id grid.

The Double Irish Chain also repeats along the (5, 5) diagonal by block
parity; the contract asks for the axis-aligned periods (10, 10), so shifts
are evaluated along one axis at a time.
"""

import numpy as np
from pydantic import BaseModel

MATCH_THRESHOLD = 0.999  # exact repeat on clean grids; tolerate a stray cell


class RepeatResult(BaseModel):
    period_rows: int  # 0 when no repeat found
    period_cols: int
    confidence: float


def _axis_period(grid: np.ndarray, axis: int) -> tuple[int, float]:
    n = grid.shape[axis]
    best_period, best_score = 0, 0.0
    for shift in range(1, n // 2 + 1):
        if axis == 0:
            a, b = grid[:-shift, :], grid[shift:, :]
        else:
            a, b = grid[:, :-shift], grid[:, shift:]
        score = float(np.mean(a == b))
        if score >= MATCH_THRESHOLD:
            return shift, score
        if score > best_score:
            best_period, best_score = shift, score
    return best_period, best_score


def detect_repeat(assignments: list[list[int]]) -> RepeatResult:
    grid = np.array(assignments)
    period_rows, score_rows = _axis_period(grid, 0)
    period_cols, score_cols = _axis_period(grid, 1)
    return RepeatResult(
        period_rows=period_rows,
        period_cols=period_cols,
        confidence=float(min(score_rows, score_cols)),
    )
