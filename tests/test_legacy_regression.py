"""Legacy regression checks (sprint 3 S0, issue #66; sprint 5 A8, issue #130).

test_legacy_path_byte_stable once compared the full recovered-model JSON of
the L0-L2 seed-42 renders with pins captured in sprint 3. The pins stored
every model field, settings included, so a new Settings field failed them
although the read did not change. HANDOFF 2.3 turns them into semantic
checks: each render is read with its sidecar corners and judged against the
hand-authored fixture, with the issue #10 thresholds kept verbatim
(REBASELINE.md criteria S7-1 to S7-3). Nothing is re-captured, and the checks
read neither the pins nor capture.py.

test_pin_committed still loads capture.py (CAP) to locate the pin files. B6b
retires it, CAP, capture.py and the pins together, which leaves the semantic
checks with no tie to either.

No Pyodide skip: the checks promise semantics, not bytes, so a failure that
happens only under wasm is a real cross-runtime divergence (criterion W14).
"""

import importlib.util
import json
from pathlib import Path

import pytest

from qrep.model import load
from qrep.render import save_render
from qrep.vision import compare_models, reverse

PIN_DIR = Path(__file__).parent / "fixtures" / "legacy_regression"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"


def _load_capture():
    spec = importlib.util.spec_from_file_location("legacy_capture", PIN_DIR / "capture.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CAP = _load_capture()


@pytest.mark.parametrize("level", CAP.LEVELS)
def test_pin_committed(level):
    assert CAP.pin_path(level).exists(), (
        f"l{level}_seed42.json missing: run "
        "`python tests/fixtures/legacy_regression/capture.py write` once and commit"
    )


@pytest.fixture(scope="module")
def truth():
    return load(FIXTURE_PATH)


# The name outlives the byte compare because REBASELINE.md and B6a cite these
# node ids.
@pytest.mark.parametrize("level", (0, 1, 2))
def test_legacy_path_byte_stable(level, truth, tmp_path):
    # Source: qrep/model/fixtures.py:37-56, make_double_irish_chain defaults.
    # Formula: rows = blocks_down x BLOCK_SIZE; cols = blocks_across x BLOCK_SIZE.
    # Inputs: blocks_down = 11, blocks_across = 9, BLOCK_SIZE = 5.
    # Arithmetic: 11 x 5 = 55 rows; 9 x 5 = 45 cols.
    # Expected: (rows, cols) = (55, 45), the 45 x 55 interior.
    interior_dims = (55, 45)
    # Source: qrep/model/fixtures.py:74-82. The palette holds b (chain blue)
    # and c (background cream); the blocks use b and c, the border c and the
    # binding b, so the quilt shows no third fabric.
    # Formula: fabrics = |{b, c}|.
    # Expected: 2.
    fabric_count = 2
    # Source: issue #10 thresholds, verbatim at tests/test_roundtrip.py:65, :80
    # and :95 (REBASELINE.md criteria S7-1 to S7-3). Cell accuracy is correct
    # cells over compared cells, so it is at most 1.0 and the L0 floor of 1.0
    # demands an exact read.
    # Expected: L0 1.0, L1 0.98, L2 0.90.
    accuracy_floor = {0: 1.0, 1: 0.98, 2: 0.90}[level]

    # The hand counts above describe the fixture this test reads.
    assert (truth.center.rows, truth.center.cols) == interior_dims
    assert len(truth.palette.fabrics) == fabric_count

    png, sidecar_path = save_render(
        truth, tmp_path / f"legacy_l{level}.png", level=level, seed=42
    )
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    corners = [(x, y) for x, y in sidecar["corners"]]
    result = reverse(png, corners=corners)
    report = compare_models(truth, result.quilt)

    assert report.recovered_dims == interior_dims, (
        f"L{level} interior dims {report.recovered_dims}, expected {interior_dims}"
    )
    assert len(result.quilt.palette.fabrics) == fabric_count, (
        f"L{level} read {len(result.quilt.palette.fabrics)} fabrics, expected {fabric_count}"
    )
    assert report.cell_accuracy >= accuracy_floor, (
        f"L{level} cell accuracy {report.cell_accuracy:.4f} below {accuracy_floor}"
    )
