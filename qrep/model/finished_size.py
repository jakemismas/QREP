"""Preset suggestion (sprint 3 S6, #72), and the names sizing kept here.

The reconcile (apply_finished_size) and the clamps moved to
qrep/model/sizing.py (A10), the one home of the model's sizing math; they
are re-exported here, values unchanged, for the callers that import them
from this module.

ASPECT_TOL (frozen at test-write time, tests/test_size_engine.py):
suggestion requires a UNIQUE preset within 0.04 of the orientation-
normalized aspect - detection residue measures 2-3%, and presets closer
than 2x0.04 (Twin/Throw at 1.1%) are structurally ambiguous, which the
uniqueness rule reports honestly as no suggestion.
"""

from qrep.model.sizing import BAND_FLOOR, CELL_MAX, CELL_MIN, PRESETS, apply_finished_size

__all__ = [
    "ASPECT_TOL",
    "BAND_FLOOR",
    "CELL_MAX",
    "CELL_MIN",
    "apply_finished_size",
    "suggest_preset",
]

ASPECT_TOL = 0.04


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
