"""S1 block-lattice SNR evidence detector (sprint 4, issue #93).

Every expected value is hand-computed in the comment beside it (values flow
one way, hand computation to assertion) or is threshold-relative to a frozen
literal; never observed output. The block-lattice statistic itself is a
CV-derived value, so assertions on it are stated against the frozen floor
T4 or against hand-derived fixture geometry, exactly as the sprint 3
periodicity/coherence tests are stated against T2/T3.

Frozen inputs used here: T4 = 1.5 (block-lattice SNR floor, frozen on #91,
2026-07-10); ladder = (1.5, 3.0, 6.0). The detector MIRRORS the wasm-gate op
in tests/fixtures/wasm_gate/ops.py; the cross-check below pins the two
byte-aligned so production and the parity reference cannot drift.
"""

import importlib.util
import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from qrep.vision import grid as grid_mod
from qrep.vision import reverse, verdict
from qrep.vision.repeats import (
    LADDER_SIGMAS,
    SNR_HARMONICS,
    SNR_MIN_LAG,
    BlockLatticeResult,
    _block_axis_fundamental,
    _block_axis_snr,
    _block_config_snr,
    block_lattice_snr,
)
from qrep.vision.verdict import T4

PHOTOREAL = Path(__file__).parent / "fixtures" / "photoreal"
GATE_DIR = Path(__file__).parent / "fixtures" / "wasm_gate"


def _load_ops():
    spec = importlib.util.spec_from_file_location("wasm_gate_ops", GATE_DIR / "ops.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


OPS = _load_ops()


# ---------------------------------------------------------------------------
# hand-computed axis SNR on tiny profiles
# ---------------------------------------------------------------------------


def test_axis_snr_hand_computed_comb():
    # A length-30 profile with three unit-height*10 comb peaks at the
    # fundamental period 8 and its harmonics (lags 8, 16, 24), zero elsewhere.
    # The search band is profile[SNR_MIN_LAG:hi] = profile[5:30], N = 25 values:
    # 22 zeros and 3 peaks of height H = 10.
    #   median: >half are zero, so the median is 0.
    #   mean = 3H/N = 30/25 = 1.2
    #   E[x^2] = 3H^2/N = 300/25 = 12; var = 12 - 1.2^2 = 10.56; std = 3.249615
    #   each harmonic peak SNR = (H - 0)/std = 10/3.249615 = 3.077287
    #   averaged over k=1..3 (all equal) = 3.077287 = N/sqrt(3(N-3)) = 25/sqrt(66)
    profile = np.zeros(30, dtype=np.float32)
    profile[8] = profile[16] = profile[24] = 10.0
    expected = 25.0 / math.sqrt(66.0)
    assert _block_axis_snr(profile, 8, 30) == pytest.approx(expected, abs=1e-4)
    assert expected == pytest.approx(3.077287, abs=1e-5)


def test_axis_snr_flat_band_is_zero():
    # a band with zero variance carries no SNR (std below the floor -> 0.0)
    assert _block_axis_snr(np.zeros(30, dtype=np.float32), 8, 30) == 0.0


def test_axis_snr_subminimal_period_is_zero():
    # a period below SNR_MIN_LAG is the zero-lag envelope, never a lattice
    profile = np.zeros(30, dtype=np.float32)
    profile[8] = profile[16] = 10.0
    assert _block_axis_snr(profile, SNR_MIN_LAG - 1, 30) == 0.0


def test_axis_fundamental_prefers_smallest_comparable_peak():
    # two local maxima: lag 6 at 0.6 and lag 12 at 1.0. The fundamental rule
    # takes the SMALLEST peak that is comparably strong (>= 0.5x the strongest).
    # 0.6 >= 0.5*1.0, so the fundamental is 6, not its harmonic 12.
    profile = np.zeros(25, dtype=np.float32)
    profile[6] = 0.6
    profile[12] = 1.0
    assert _block_axis_fundamental(profile, 20) == 6


def test_axis_fundamental_skips_too_weak_subharmonic():
    # same layout but the lag-6 peak is only 0.3 < 0.5x the lag-12 peak, so it
    # is NOT comparably strong; the fundamental falls through to lag 12.
    profile = np.zeros(25, dtype=np.float32)
    profile[6] = 0.3
    profile[12] = 1.0
    assert _block_axis_fundamental(profile, 20) == 12


# ---------------------------------------------------------------------------
# the ladder recovers a fine block a single fixed sigma misses (phone-cap class)
# ---------------------------------------------------------------------------


def _fine_lattice(period: int, size: int = 300) -> np.ndarray:
    """A thin-line square lattice at `period` px over a slow illumination ramp
    (the coarse trend the detrend must remove). Deterministic; no RNG."""
    img = np.full((size, size, 3), 128, np.uint8)
    for x in range(0, size, period):
        img[:, x : x + 1] = 128 - 40
    for y in range(0, size, period):
        img[y : y + 1, :] = 128 - 40
    ramp = np.linspace(-30, 30, size).astype(np.float32)
    img = np.clip(
        img.astype(np.float32) + ramp[None, :, None] + ramp[:, None, None], 0, 255
    ).astype(np.uint8)
    return cv2.GaussianBlur(img, (0, 0), 1.2)


def test_ladder_recovers_fine_lattice_single_sigma_misses():
    # A 12 px block (the phone-cap fine class). A single fixed FINE sigma reads
    # the WRONG period: at sigma 1.5 the fundamental rule (which excludes the
    # zero-lag lag <= SNR_MIN_LAG) locks the half-period 6 with SNR ~0.88,
    # BELOW the floor T4 = 1.5 - the true 12 px lattice is lost. Sweeping the
    # frozen ladder recovers period 12 at SNR >= T4. This is the ladder's whole
    # reason to exist: no single detrend scale certifies every block.
    img = _fine_lattice(12)
    result = block_lattice_snr(img)
    assert result.period_x == 12
    assert result.period_y == 12
    assert result.snr >= T4

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2Lab).astype(np.float32)
    hi = img.shape[0] // 4
    single = _block_config_snr(lab[:, :, result.channel], 1.5, hi, hi)
    assert single is not None
    single_snr, single_px = single[0], single[1]
    assert single_px != 12  # aliases to the half-period
    assert single_snr < T4  # and falls below the floor


def test_ladder_recovers_ten_px_lattice():
    # the literal AC case: a 10 px lattice at the phone cap is recovered above
    # the floor (every rung sees it, but the ladder's max is what the detector
    # reports).
    result = block_lattice_snr(_fine_lattice(10))
    assert result.period_x == 10
    assert result.period_y == 10
    assert result.snr >= T4


def test_flat_image_yields_empty_evidence():
    # a solid panel high-passes to numerical dust below the signal floor on
    # every channel and rung: no lattice, channel -1, snr 0.
    flat = np.full((300, 300, 3), 150, np.uint8)
    result = block_lattice_snr(flat)
    assert result.channel == -1
    assert result.period_x == 0 and result.period_y == 0
    assert result.snr == 0.0


# ---------------------------------------------------------------------------
# mirror parity with the frozen wasm-gate op (production must not drift)
# ---------------------------------------------------------------------------


def test_ladder_literals_match_wasm_gate_op():
    # the frozen ladder + SNR shape are re-declared in production (it cannot
    # import from tests/); they must equal the wasm-gate op's literals exactly.
    assert LADDER_SIGMAS == OPS.LADDER_SIGMAS == (1.5, 3.0, 6.0)
    assert tuple(SNR_HARMONICS) == tuple(OPS.SNR_HARMONICS) == (1, 2, 3)
    assert SNR_MIN_LAG == OPS.SNR_MIN_LAG


@pytest.mark.parametrize(
    "name,cap", OPS.LADDER_CASES, ids=[f"{n}-{c}" for n, c in OPS.LADDER_CASES]
)
def test_block_lattice_snr_mirrors_wasm_gate_op(name, cap):
    # the production detector and the parity op are the SAME algorithm; on the
    # same input in the same runtime they agree bit-for-bit (periods, channel,
    # sigma exact; snr equal within float-reordering noise).
    image = cv2.imread(str(PHOTOREAL / f"{name}_{cap}.png"))
    assert image is not None
    got = block_lattice_snr(image)
    ref = OPS.lab_ladder_autocorr_op(image)
    assert got.period_x == ref["period_x"]
    assert got.period_y == ref["period_y"]
    assert got.channel == ref["channel"]
    assert got.sigma == ref["sigma"]
    assert got.snr == pytest.approx(ref["snr"], abs=1e-9)


def test_block_lattice_snr_is_deterministic_same_process():
    image = cv2.imread(str(PHOTOREAL / "antique_wash_chain_1400.png"))
    assert block_lattice_snr(image) == block_lattice_snr(image)


# ---------------------------------------------------------------------------
# T4 is imported, never inlined
# ---------------------------------------------------------------------------


def test_t4_is_a_single_frozen_literal_imported_everywhere():
    # verdict.py owns T4; grid.py binds the SAME object (no re-declared magic
    # number). Value is the #91 freeze.
    assert verdict.T4 == 1.50
    assert grid_mod.T4 is verdict.T4


def test_t4_not_inlined_in_grid_source():
    # the admissibility gate references the imported symbol, not a bare 1.5
    source = (Path(__file__).parents[1] / "qrep" / "vision" / "grid.py").read_text(
        encoding="utf-8"
    )
    assert "block_lattice.snr >= T4" in source
    assert "block_lattice.snr >= 1.5" not in source


# ---------------------------------------------------------------------------
# inertness and verdict-neutrality on every committed fixture (both caps)
# ---------------------------------------------------------------------------

_FIXTURES = [
    "render_on_white",
    "render_on_wood",
    "render_perspective_jpeg",
    "screenshot_composite",
    "tall_chrome",
    "edge_to_edge",
    "white_border_on_white",
    "lighting_gradient",
    "fabric_print",
    "seam_shadows",
    "hst_star",
    "drunkards_path",
    "busy_print_squares",
    "low_contrast_hst",
    "solid_fabric",
    "antique_wash_chain",
    "quarter_circle_fine",
    "two_color_garbage",
    "degraded_render_on_white",
    "degraded_drunkards_path",
    "degraded_hst_star",
    "degraded_busy_print",
]
_ALL_CASES = [(n, c) for n in _FIXTURES for c in (1400, 2000)]


@pytest.mark.parametrize("name,cap", _ALL_CASES, ids=[f"{n}-{c}" for n, c in _ALL_CASES])
def test_passing_fixtures_never_compute_the_block_hint(name, cap):
    # INERTNESS: a fixture whose 1D read succeeds (verdict != no_grid, i.e.
    # grid confidence >= T1) never triggers block_lattice_snr, so lattice_snr
    # is None and estimate_grid ran byte-identically to pre-S1. Conversely, a
    # failing read is the only place the detector runs at all.
    result = reverse(PHOTOREAL / f"{name}_{cap}.png")
    d = result.diagnostics
    if d["verdict"] != "no_grid":
        assert d["lattice_snr"] is None, f"{name}_{cap}: block hint leaked into a passing read"


@pytest.mark.parametrize("name,cap", _ALL_CASES, ids=[f"{n}-{c}" for n, c in _ALL_CASES])
def test_block_hint_never_rescues_a_verdict_in_s1(name, cap):
    # VERDICT-NEUTRALITY (S1 non-goal: verdict changes are S2). Wherever the
    # block-lattice detector DID run (lattice_snr present), the outcome is
    # still no_grid - the additive corroboration leg that turns evidence into
    # a rescued verdict lands in S2, not here. The decisive S0 finding is that
    # pitch feedback alone keeps the recomputed prominence below T1.
    result = reverse(PHOTOREAL / f"{name}_{cap}.png")
    d = result.diagnostics
    if d["lattice_snr"] is not None:
        assert d["verdict"] == "no_grid", f"{name}_{cap}: S1 flipped a verdict via the block hint"


def test_lattice_snr_diagnostic_shape_when_present():
    # busy_print_squares reads no_grid today (garbage 5 px 1D pitch), so the
    # detector runs and the diagnostic carries the documented shape.
    d = reverse(PHOTOREAL / "busy_print_squares_1400.png").diagnostics
    ls = d["lattice_snr"]
    assert ls is not None
    assert set(ls) == {"period_px", "snr", "channel", "sigma"}
    assert len(ls["period_px"]) == 2
    assert ls["channel"] in (0, 1, 2)


# ---------------------------------------------------------------------------
# degraded tier: the detector engages on failing reads (S0 baseline)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["degraded_render_on_white", "degraded_drunkards_path"]
)
def test_degraded_failing_read_engages_block_lattice(name):
    # at the 1400 (phone) cap these degraded renders read below T1 today; the
    # S0 baseline measures a strong block lattice (SNR well over T4) on both.
    # S1 computes it and feeds the pitch, but the verdict stays no_grid.
    d = reverse(PHOTOREAL / f"{name}_1400.png").diagnostics
    assert d["verdict"] == "no_grid"
    ls = d["lattice_snr"]
    assert ls is not None
    assert ls["snr"] >= T4
    assert ls["period_px"][0] > 0 and ls["period_px"][1] > 0


def test_two_color_garbage_block_is_rejected_by_the_contract_gates():
    # D3: the 2-color garbage control is NOT admitted. Its block lattice is
    # rejected by at least one required gate - either the SNR floor T4 or the
    # integer-lock's "block period >= 1D pitch" (garbage locks a ~7 px texture
    # period far below its ~20-28 px 1D pitch). Verdict stays no_grid.
    for cap in (1400, 2000):
        d = reverse(PHOTOREAL / f"two_color_garbage_{cap}.png").diagnostics
        assert d["verdict"] == "no_grid"
        ls = d["lattice_snr"]
        assert ls is not None
        pitch_x = d["pitch_px"][0]
        block_x = ls["period_px"][0]
        rejected = ls["snr"] < T4 or block_x < pitch_x
        assert rejected, f"garbage_{cap} slipped past both admissibility gates"


def test_solid_fabric_never_reaches_the_detector():
    # solid fabric raises out of estimate_grid (no edges) before the block
    # stage; the fallback result carries lattice_snr None, no_grid.
    d = reverse(PHOTOREAL / "solid_fabric_1400.png").diagnostics
    assert d["verdict"] == "no_grid"
    assert d["lattice_snr"] is None


# ---------------------------------------------------------------------------
# model surface
# ---------------------------------------------------------------------------


def test_block_lattice_result_is_json_safe():
    # diagnostics are json-round-tripped downstream; the model dumps cleanly
    result = BlockLatticeResult(
        period_x=12, period_y=12, snr=2.6, snr_x=2.6, snr_y=2.9, channel=0, sigma=1.5
    )
    assert result.model_dump()["period_x"] == 12
