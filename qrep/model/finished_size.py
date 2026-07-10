"""Finished-size reconciliation and preset suggestion (sprint 3 S6, #72).

The model cannot represent arbitrary W x H: cells are square integer
eighths and border bands add identically to both axes, so
W - H = (cols - rows) * cell_size exactly. The reconcile rule (plan,
Slice 6): derive a cell candidate per requested axis, take the MIN that
satisfies the editor's clamps, rescale bands by the PARITY band rule, and
store ONLY achieved dimensions in the model; callers receive
{requested, achieved} for the asked-for-vs-you-get presentation.

Photo-derived models honor the editor's CELL_MIN/CELL_MAX clamps (frozen
approval decision): an entry whose derived cell falls outside them returns
achieved-at-clamp with the delta reported, never an error.

ASPECT_TOL (frozen at test-write time, tests/test_size_engine.py):
suggestion requires a UNIQUE preset within 0.04 of the orientation-
normalized aspect - detection residue measures 2-3%, and presets closer
than 2x0.04 (Twin/Throw at 1.1%) are structurally ambiguous, which the
uniqueness rule reports honestly as no suggestion.
"""

from qrep.model.schema import Quilt
from qrep.viewer.sizing import PRESETS, round_div

# the editor's clamps, integer eighths (PARITY item 4; single source is the
# bridge's resize layer - mirrored here as the same frozen approval values)
CELL_MIN = 6  # 3/4"
CELL_MAX = 32  # 4"
BAND_FLOOR = 2  # 1/4"

ASPECT_TOL = 0.04


def _cell_candidate(target: int, cells: int, cell0: int, band_total0: int) -> int:
    """Cell size (eighths) whose scaled quilt best meets one axis target.

    Bands scale with the cell (the PARITY locked-resize rule), so the
    finished extent is cells*cell + 2*band_total0*(cell/cell0); solving for
    cell gives target*cell0 / (cells*cell0 + 2*band_total0)."""
    if band_total0 > 0:
        return round_div(target * cell0, cells * cell0 + 2 * band_total0)
    return round_div(target, cells)


def apply_finished_size(
    quilt: Quilt, width: int | None, height: int | None
) -> tuple[Quilt, dict, dict]:
    """Reconcile a requested finished size onto the quilt's grid.

    width/height are integer eighths; either may be None. Returns
    (updated quilt, requested, achieved). Never raises for out-of-range
    requests: the cell clamps and the deltas are the honest answer."""
    rows, cols = quilt.center.rows, quilt.center.cols
    cell0 = quilt.center.cell_size
    band_total0 = sum(band.width for band in quilt.borders)

    candidates = []
    if width is not None:
        candidates.append(_cell_candidate(width, cols, cell0, band_total0))
    if height is not None:
        candidates.append(_cell_candidate(height, rows, cell0, band_total0))
    if not candidates:
        raise ValueError("apply_finished_size needs a width or a height")
    cell = max(CELL_MIN, min(CELL_MAX, min(candidates)))

    updated = quilt.model_copy(deep=True)
    updated.center.cell_size = cell
    new_bands = []
    for band in updated.borders:
        band.width = max(BAND_FLOOR, round_div(band.width * cell, cell0))
        new_bands.append(band.width)
    band_total = sum(new_bands)

    achieved = {
        "width": cols * cell + 2 * band_total,
        "height": rows * cell + 2 * band_total,
        "cell_size": cell,
        "borders": new_bands,
    }
    requested = {"width": width, "height": height}
    return updated, requested, achieved


def suggest_preset(aspect: float) -> str | None:
    """The UNIQUE preset whose orientation-normalized aspect (long/short)
    sits within ASPECT_TOL; None on zero or multiple matches."""
    if aspect <= 0:
        return None
    normalized = aspect if aspect >= 1 else 1.0 / aspect
    matches = []
    for name, w, h in PRESETS:
        preset_aspect = max(w, h) / min(w, h)
        if abs(normalized - preset_aspect) <= ASPECT_TOL:
            matches.append(name)
    return matches[0] if len(matches) == 1 else None
