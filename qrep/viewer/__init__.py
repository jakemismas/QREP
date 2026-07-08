"""Sizing viewer: static HTML template and emit logic."""

from qrep.viewer.emit import emit_viewer, write_viewer
from qrep.viewer.sizing import (
    PRESETS,
    SizingResult,
    build_view_config,
    locked_resize,
    round_div,
    unlocked_resize,
)

__all__ = [
    "PRESETS",
    "SizingResult",
    "build_view_config",
    "emit_viewer",
    "locked_resize",
    "round_div",
    "unlocked_resize",
    "write_viewer",
]
