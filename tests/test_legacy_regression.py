"""Pinned legacy regression (sprint 3 S0, issue #66).

The committed pins under tests/fixtures/legacy_regression/ capture what the
pipeline detected on the L0-L2 seed-42 renders at S0 time: corners plus the
full recovered-model JSON. S1's tier-0 legacy branch must keep this path
byte-stable; a diff here is a behavior change in the legacy path until
proven otherwise.

Skipped under Pyodide: the web design doc grants CV output no cross-runtime
byte promises (cv2.kmeans float accumulation may differ under wasm); the
wasm runtime is covered by the semantic thresholds in test_roundtrip.py.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

PIN_DIR = Path(__file__).parent / "fixtures" / "legacy_regression"


def _load_capture():
    spec = importlib.util.spec_from_file_location("legacy_capture", PIN_DIR / "capture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAP = _load_capture()

pytestmark = pytest.mark.skipif(
    sys.platform == "emscripten",
    reason="no cross-runtime byte promises for CV output (web design doc)",
)


@pytest.mark.parametrize("level", CAP.LEVELS)
def test_pin_committed(level):
    assert CAP.pin_path(level).exists(), (
        f"l{level}_seed42.json missing: run "
        "`python tests/fixtures/legacy_regression/capture.py write` once and commit"
    )


@pytest.mark.parametrize("level", CAP.LEVELS)
def test_legacy_path_byte_stable(level):
    pinned = json.loads(CAP.pin_path(level).read_text(encoding="utf-8"))
    current = CAP.build_pin(level)
    assert current["corners"] == pinned["corners"], (
        f"L{level} detected corners drifted from the S0 pin"
    )
    assert current["model"] == pinned["model"], (
        f"L{level} recovered model drifted from the S0 pin"
    )
