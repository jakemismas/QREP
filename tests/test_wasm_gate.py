"""S0 wasm gate: cv2.grabCut and cv2.dft parity against the committed
native reference (sprint 3 S0, issue #66).

This file runs in BOTH runtimes. Under native CI it re-derives the ops and
compares against the committed reference (same-library agreement, absorbing
OS/SIMD variation). Under the pytest-under-Pyodide job it is THE gate: the
wasm cv2 4.11 wheel must agree with the natively captured reference within
the tolerances below.

TOLERANCES - frozen at write time, BEFORE any wasm parity run, per the
plan's threshold rule; chosen from failure-mode reasoning, not from
observed output:
- GRABCUT_IOU_TOL = 0.95. GMM float paths may flip boundary pixels across
  builds/versions; a segmentation that differs for a REAL reason (different
  region found) drops far below 0.95, while boundary jitter stays far
  above it.
- DFT peak lags match EXACTLY (integer lattice property of the fixture).
- DFT_VALUE_TOL = 0.01 absolute on zero-lag-normalized autocorrelation
  values (in [-1, 1]); FFT reordering noise is ~1e-6, so 0.01 is three
  orders above noise yet far below any structural difference.

Determinism: cv2.setRNGSeed precedes every grabCut call inside the op;
the same-process repeat check asserts byte-identical masks.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

GATE_DIR = Path(__file__).parent / "fixtures" / "wasm_gate"

GRABCUT_IOU_TOL = 0.95
DFT_VALUE_TOL = 0.01
# ladder-autocorr SNR tolerance, frozen at write time BEFORE any wasm parity
# run, from failure-mode reasoning: the canonical-config fundamental lags are
# integer-exact across runtimes (as the dft peaks are), and the SNR is O(1-13)
# with a global-background median/std whose FFT-reordering noise is ~1e-4; a
# genuine structural divergence (the ladder landing on a different period)
# shifts SNR by more than 1, so 0.25 is far above float noise and far below
# any real difference. The argmax (channel, sigma) may flip on a near-tie, so
# only the canonical config's lags are pinned exactly; the argmax period is
# checked within a loose band that still catches a gross divergence.
LADDER_SNR_TOL = 0.25
LADDER_PERIOD_BAND = 3


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"wasm_gate_{name}", GATE_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OPS = _load("ops")
CAPTURE = _load("capture")


@pytest.fixture(scope="module")
def reference():
    path = CAPTURE.reference_path()
    assert path.exists(), (
        "wasm_gate/reference.json missing: run "
        "`python tests/fixtures/wasm_gate/capture.py write` once and commit"
    )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name,cap", OPS.GRABCUT_CASES, ids=[f"{n}-{c}" for n, c in OPS.GRABCUT_CASES])
def test_grabcut_agrees_with_native_reference(reference, name, cap):
    import cv2

    fg = OPS.grabcut_op(OPS.load_fixture_bgr(name, cap))
    ref_entry = reference["grabcut"][f"{name}_{cap}"]
    ref_mask = cv2.imread(str(GATE_DIR / ref_entry["mask_file"]), cv2.IMREAD_GRAYSCALE)
    assert ref_mask is not None
    assert ref_mask.shape == fg.shape
    iou = OPS.mask_iou(fg, ref_mask)
    assert iou >= GRABCUT_IOU_TOL, (
        f"grabCut mask IoU {iou:.4f} vs native reference below {GRABCUT_IOU_TOL}"
    )


def test_grabcut_repeat_determinism_same_process():
    image = OPS.load_fixture_bgr("render_on_wood", 1400)
    first = OPS.grabcut_op(image)
    second = OPS.grabcut_op(image)
    assert np.array_equal(first, second), "setRNGSeed must make grabCut repeatable in-process"


@pytest.mark.parametrize("name,cap", OPS.DFT_CASES, ids=[f"{n}-{c}" for n, c in OPS.DFT_CASES])
def test_dft_autocorr_agrees_with_native_reference(reference, name, cap):
    result = OPS.dft_autocorr_op(OPS.load_fixture_bgr(name, cap))
    ref = reference["dft"][f"{name}_{cap}"]
    assert result["peak_x"] == ref["peak_x"]
    assert result["peak_y"] == ref["peak_y"]
    assert abs(result["val_x"] - ref["val_x"]) <= DFT_VALUE_TOL
    assert abs(result["val_y"] - ref["val_y"]) <= DFT_VALUE_TOL
    for got, want in zip(result["profile_x"], ref["profile_x"]):
        assert abs(got - want) <= DFT_VALUE_TOL
    for got, want in zip(result["profile_y"], ref["profile_y"]):
        assert abs(got - want) <= DFT_VALUE_TOL


@pytest.mark.parametrize(
    "name,cap", OPS.LADDER_CASES, ids=[f"{n}-{c}" for n, c in OPS.LADDER_CASES]
)
def test_ladder_autocorr_agrees_with_native_reference(reference, name, cap):
    result = OPS.lab_ladder_autocorr_op(OPS.load_fixture_bgr(name, cap))
    ref = reference["ladder"][f"{name}_{cap}"]
    # canonical config (L channel, finest sigma): lags integer-exact
    assert result["ref_lag_x"] == ref["ref_lag_x"]
    assert result["ref_lag_y"] == ref["ref_lag_y"]
    assert abs(result["ref_snr"] - ref["ref_snr"]) <= LADDER_SNR_TOL
    # argmax config: SNR within tol; periods within a loose band (a near-tie
    # may flip the winning channel/sigma across runtimes)
    assert abs(result["snr"] - ref["snr"]) <= LADDER_SNR_TOL
    assert abs(result["period_x"] - ref["period_x"]) <= LADDER_PERIOD_BAND
    assert abs(result["period_y"] - ref["period_y"]) <= LADDER_PERIOD_BAND


def test_ladder_autocorr_repeat_determinism_same_process():
    image = OPS.load_fixture_bgr("antique_wash_chain", 1400)
    first = OPS.lab_ladder_autocorr_op(image)
    second = OPS.lab_ladder_autocorr_op(image)
    assert first == second
