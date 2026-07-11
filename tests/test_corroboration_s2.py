"""S2 corroborated verdicts (sprint 4, issue #94).

The four council property tests are acceptance-criteria checkboxes, not
optional: (1) absence-identity, (2) end-to-end inertness, (3) backdoor-lock,
(4) negative-control verdict pins. Every expected value is hand-computed in
the comment beside it (values flow one way, hand computation to assertion);
CV-derived block-lattice values are asserted threshold-relative to the frozen
literals T4/T5/T3, exactly as the sprint 3 tests are stated against T1-T3.

FROZEN literals used here (immutable, #91/#94 freeze, 2026-07-10): T4 = 1.5,
T5 = 0.70, T3 = 1.05, INTEGER_RATIO_EPSILON = 0.15,
RESCUE_MIN_PITCH_PX = 10.0 (= 2 x grid.MIN_PITCH_PX).
"""

import itertools
from pathlib import Path

import cv2
import numpy as np
import pytest

from qrep.vision import reverse
from qrep.vision import grid as grid_mod
from qrep.vision import verdict as verdict_mod
from qrep.vision.repeats import (
    SNR_MIN_LAG,
    block_lattice_coherence,
    coherence_with_sublattice,
    _uniform_block_boundaries,
)
from qrep.vision.verdict import (
    T1,
    T2,
    T3,
    T4,
    T5,
    CorroborationEvidence,
    decide_verdict,
)

PHOTOREAL = Path(__file__).parent / "fixtures" / "photoreal"


def _frozen_tree(gc: float, ps: float, coh: float, label: bool) -> str:
    """The sprint-3 frozen tree, hand-transcribed as the absence-identity
    reference (this is exactly what decide_verdict was before S2)."""
    if gc < T1:
        return "no_grid"
    if ps < T2:
        return "readable" if label else "readable_no_repeat"
    if coh > T3:
        return "non_square_repeat"
    return "readable"


# ---------------------------------------------------------------------------
# frozen literals: imported, never inlined; RESCUE_MIN_PITCH_PX = 2*MIN_PITCH_PX
# ---------------------------------------------------------------------------


def test_t5_and_rescue_floor_are_frozen_literals():
    # the #91/#94 freeze values, and the derivation that documents the floor.
    assert verdict_mod.T5 == 0.70
    assert verdict_mod.RESCUE_MIN_PITCH_PX == 10.0
    assert verdict_mod.RESCUE_MIN_PITCH_PX == 2 * grid_mod.MIN_PITCH_PX


def test_t5_and_rescue_floor_not_inlined_in_pipeline_source():
    # the pipeline references the imported symbols, not bare magic numbers.
    source = (Path(__file__).parents[1] / "qrep" / "vision" / "pipeline.py").read_text(
        encoding="utf-8"
    )
    assert "min_pitch >= RESCUE_MIN_PITCH_PX" in source
    assert ">= 10.0" not in source and ">= 10 " not in source
    # T5 lives only in decide_verdict (verdict.py); the pipeline never gates on it
    assert "0.70" not in source


# ---------------------------------------------------------------------------
# (1) absence-identity: corroboration=None is byte-identical to the frozen tree
# ---------------------------------------------------------------------------


def test_absence_identity_across_threshold_straddling_sweep():
    # every combination of values straddling T1/T2/T3 (below, just-below, at,
    # just-above, high) with corroboration omitted must equal the frozen tree.
    gcs = [0.0, T1 - 0.01, T1, T1 + 0.01, 0.99]
    pss = [0.0, T2 - 0.01, T2, T2 + 0.01, 0.99]
    cohs = [0.0, T3 - 0.01, T3, T3 + 0.01, 2.0]
    for gc, ps, coh, label in itertools.product(gcs, pss, cohs, (True, False)):
        assert decide_verdict(gc, ps, coh, label) == _frozen_tree(gc, ps, coh, label)


def test_absence_identity_explicit_none_matches_omitted():
    # passing corroboration=None explicitly is identical to omitting it.
    for gc, ps, coh, label in itertools.product(
        (0.3, 0.7), (0.2, 0.8), (0.3, 1.4), (True, False)
    ):
        assert decide_verdict(gc, ps, coh, label, corroboration=None) == decide_verdict(
            gc, ps, coh, label
        )


def test_absence_identity_l0_render_is_inert(tmp_path):
    # the L0 double-irish-chain render reads readable on its own (grid conf >=
    # T1); the block hint is never computed, so the corroboration leg is inert
    # and the legacy byte-law is untouched (test_legacy_regression pins bytes).
    from qrep.model import load
    from qrep.render import save_render

    truth = load(Path(__file__).parent / "fixtures" / "double_irish_chain.json")
    png, _ = save_render(truth, tmp_path / "l0.png", level=0, seed=42)
    d = reverse(png).diagnostics
    assert d["verdict"] == "readable"
    assert d["lattice_snr"] is None


# ---------------------------------------------------------------------------
# exit (a) readable rescue: falls through the REMAINING frozen tree
# ---------------------------------------------------------------------------


def _passes_a(block_coherence: float = 0.0) -> CorroborationEvidence:
    # snr 2.0 >= T4=1.5, integer-locked, mcc 0.80 >= T5=0.70; block_coherence
    # defaults BELOW T3 so exit (b) never masks a negated exit-(a) gate.
    return CorroborationEvidence(
        min_axis_snr=2.0, integer_lock=True, mean_cell_confidence=0.80, block_coherence=block_coherence
    )


def test_exit_a_falls_through_the_frozen_tree():
    ev = _passes_a()
    gc = 0.4  # below T1: without corroboration this is no_grid
    # exit (a) rescues, then the SAME T2/T3 tree decides:
    # periodicity 0.2 < T2, label True  -> readable
    assert decide_verdict(gc, 0.2, 0.3, True, corroboration=ev) == "readable"
    # periodicity 0.2 < T2, label False -> readable_no_repeat
    assert decide_verdict(gc, 0.2, 0.3, False, corroboration=ev) == "readable_no_repeat"
    # periodicity 0.9 >= T2, coherence 1.4 > T3 -> non_square_repeat
    assert decide_verdict(gc, 0.9, 1.4, False, corroboration=ev) == "non_square_repeat"
    # periodicity 0.9 >= T2, coherence 0.3 <= T3 -> readable
    assert decide_verdict(gc, 0.9, 0.3, False, corroboration=ev) == "readable"


def test_exit_a_is_inert_above_t1():
    # when the 1D read already passes (grid conf >= T1) the corroboration is
    # never consulted: the healthy tree stands, byte-identical to the frozen one.
    ev = _passes_a()
    for ps, coh, label in itertools.product((0.2, 0.9), (0.3, 1.4), (True, False)):
        assert decide_verdict(0.9, ps, coh, label, corroboration=ev) == _frozen_tree(
            0.9, ps, coh, label
        )


# ---------------------------------------------------------------------------
# exit (b) block-structure rescue: non_square_repeat, no T5
# ---------------------------------------------------------------------------


def test_exit_b_returns_non_square_repeat_without_t5():
    # snr 2.0 >= T4, integer_lock False (exit a cannot fire), block coherence
    # 1.2 > T3 -> non_square_repeat. mcc is low (0.1) to prove exit (b) does
    # NOT consult T5. periodicity/coherence are the tree's, and must be IGNORED.
    ev = CorroborationEvidence(
        min_axis_snr=2.0, integer_lock=False, mean_cell_confidence=0.1, block_coherence=1.2
    )
    assert decide_verdict(0.4, 0.9, 0.3, False, corroboration=ev) == "non_square_repeat"
    assert decide_verdict(0.4, 0.2, 2.0, True, corroboration=ev) == "non_square_repeat"


def test_exit_b_below_t3_is_no_grid():
    # block coherence exactly at / below T3 does not rescue (boundary: not above)
    ev = CorroborationEvidence(
        min_axis_snr=2.0, integer_lock=False, mean_cell_confidence=0.9, block_coherence=T3
    )
    assert decide_verdict(0.4, 0.9, 0.3, False, corroboration=ev) == "no_grid"


# ---------------------------------------------------------------------------
# (3) backdoor-lock
# ---------------------------------------------------------------------------


def test_backdoor_exit_b_reaches_only_no_grid_or_non_square_repeat():
    # with exit (a) disabled (integer_lock False), the only reachable outcomes
    # are no_grid or non_square_repeat, for EVERY tree input - readable and
    # readable_no_repeat are unreachable via the corroboration branch's exit (b).
    for snr, bcoh, ps, coh, label in itertools.product(
        (0.0, T4, 3.0), (0.0, T3, 1.5), (0.2, 0.9), (0.3, 1.4), (True, False)
    ):
        ev = CorroborationEvidence(
            min_axis_snr=snr, integer_lock=False, mean_cell_confidence=0.9, block_coherence=bcoh
        )
        assert decide_verdict(0.4, ps, coh, label, corroboration=ev) in (
            "no_grid",
            "non_square_repeat",
        )


def test_backdoor_each_exit_a_gate_negated_returns_no_grid():
    # a scenario where exit (a) rescues to readable; block coherence is below T3
    # so exit (b) cannot mask the negation. Negating any one exit-(a) gate ->
    # no_grid.
    gc, ps, coh, label = 0.4, 0.2, 0.3, True
    assert decide_verdict(gc, ps, coh, label, corroboration=_passes_a()) == "readable"
    # snr below T4
    ev = CorroborationEvidence(
        min_axis_snr=T4 - 0.01, integer_lock=True, mean_cell_confidence=0.80, block_coherence=0.0
    )
    assert decide_verdict(gc, ps, coh, label, corroboration=ev) == "no_grid"
    # integer lock false
    ev = CorroborationEvidence(
        min_axis_snr=2.0, integer_lock=False, mean_cell_confidence=0.80, block_coherence=0.0
    )
    assert decide_verdict(gc, ps, coh, label, corroboration=ev) == "no_grid"
    # mean cell confidence below T5
    ev = CorroborationEvidence(
        min_axis_snr=2.0, integer_lock=True, mean_cell_confidence=T5 - 0.01, block_coherence=0.0
    )
    assert decide_verdict(gc, ps, coh, label, corroboration=ev) == "no_grid"


def test_snr_below_t4_blocks_both_exits():
    # the shared floor: below T4 neither exit fires, whatever the other fields.
    ev = CorroborationEvidence(
        min_axis_snr=T4 - 0.01, integer_lock=True, mean_cell_confidence=0.99, block_coherence=1.9
    )
    assert decide_verdict(0.4, 0.9, 1.9, True, corroboration=ev) == "no_grid"


def test_boundary_snr_and_mcc_at_threshold_are_admitted():
    # exactly-at-threshold semantics: snr == T4 and mcc == T5 are NOT below.
    ev = CorroborationEvidence(
        min_axis_snr=T4, integer_lock=True, mean_cell_confidence=T5, block_coherence=0.0
    )
    assert decide_verdict(0.4, 0.2, 0.3, True, corroboration=ev) == "readable"


def test_corroboration_evidence_is_json_safe():
    ev = CorroborationEvidence(
        min_axis_snr=2.6, integer_lock=True, mean_cell_confidence=0.9, block_coherence=1.3
    )
    assert ev.model_dump()["integer_lock"] is True


# ---------------------------------------------------------------------------
# block_lattice_coherence entry (thin wrapper over uniform boundaries)
# ---------------------------------------------------------------------------


def test_block_lattice_coherence_wraps_uniform_boundaries():
    # the entry is exactly coherence_with_sublattice on evenly-spaced block
    # boundaries; proven equal on a committed fixture (relational, not observed).
    img = cv2.imread(str(PHOTOREAL / "quarter_circle_fine_1400.png"))
    xb = _uniform_block_boundaries(img.shape[1], 20)
    yb = _uniform_block_boundaries(img.shape[0], 20)
    assert block_lattice_coherence(img, 20, 20) == coherence_with_sublattice(img, xb, yb)


def test_block_lattice_coherence_zero_for_subminimal_period():
    # a period below the min resolvable lag builds no boundaries -> 0.0.
    img = np.full((100, 100, 3), 128, np.uint8)
    assert block_lattice_coherence(img, SNR_MIN_LAG - 1, 20) == 0.0
    assert block_lattice_coherence(img, 20, SNR_MIN_LAG - 1) == 0.0


# ---------------------------------------------------------------------------
# (4) negative-control verdict pins (end-to-end)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name,cap",
    [
        ("solid_fabric", 1400),
        ("solid_fabric", 2000),
        ("two_color_garbage", 1400),
        ("two_color_garbage", 2000),
        ("busy_print_squares", 1400),
        ("busy_print_squares", 2000),
        ("degraded_busy_print", 1400),
        ("fabric_print", 2000),
    ],
)
def test_negative_controls_stay_no_grid(name, cap):
    # none of these is a readable square recovery: solid/noise carry no lattice;
    # the 2-color garbage fails the integer-lock (block finer than its 1D
    # pitch); busy_print / degraded_busy_print / fabric_print_2000 invert to a
    # sub-cell TEXTURE pitch, so the plausibility gate (pitch < RESCUE_MIN_PITCH
    # or a hard structural guard) refuses to build corroboration. All stay
    # no_grid; #82's inversion cannot leak a garbage "readable".
    d = reverse(PHOTOREAL / f"{name}_{cap}.png").diagnostics
    assert d["verdict"] == "no_grid", f"{name}_{cap} was falsely rescued"
    assert d["verdict"] != "non_square_repeat"


def test_gaussian_noise_control_is_no_grid(tmp_path):
    # a pure-noise field has no lattice; its block SNR sits at the noise floor
    # (< T4), so it never rescues. Deterministic seed - the control is the
    # invariant "noise is no_grid", not any specific pixel value.
    rng = np.random.default_rng(0)
    noise = rng.integers(0, 256, size=(900, 900, 3), dtype=np.uint8)
    png = tmp_path / "noise.png"
    cv2.imwrite(str(png), noise)
    d = reverse(png).diagnostics
    assert d["verdict"] == "no_grid"


def test_busy_print_keeps_its_lattice_but_is_not_rescued():
    # the block detector still RUNS on busy_print (its 1D read fails), so the
    # lattice_snr diagnostic is present - but the plausibility gate keeps the
    # verdict no_grid and the honest weak/implausible diagnosis, not a rescue.
    d = reverse(PHOTOREAL / "busy_print_squares_1400.png").diagnostics
    assert d["lattice_snr"] is not None
    assert d["verdict"] == "no_grid"
    assert d["grid_diagnosis"] != "non_square_content"  # squares, not curved content


# ---------------------------------------------------------------------------
# degraded-tier rescue pins + non_square_content emission
# ---------------------------------------------------------------------------


def test_degraded_squares_render_rescued_readable_via_exit_a():
    # degraded_render_on_white at the phone cap reads below T1 on its own;
    # exit (a) (snr >> T4, integer lock at the block, mcc >= T5) rescues it to
    # readable through the frozen tree. Its adopted cell pitch (~14 px) clears
    # RESCUE_MIN_PITCH_PX, so it is quilt-plausible.
    d = reverse(PHOTOREAL / "degraded_render_on_white_1400.png").diagnostics
    assert d["verdict"] == "readable"
    assert d["lattice_snr"]["snr"] >= T4


@pytest.mark.parametrize(
    "name,cap",
    [
        ("degraded_drunkards_path", 1400),
        ("degraded_drunkards_path", 2000),
        ("low_contrast_hst", 2000),
    ],
)
def test_degraded_non_square_rescued_and_marked_non_square_content(name, cap):
    # curved / triangle content whose 1D read fails: exit (a)'s tree routes it
    # to non_square_repeat (coherence > T3), and the coarse block lattice makes
    # the diagnosis non_square_content (the honest curved-quilt copy driver),
    # never the wrong steep-angle message.
    d = reverse(PHOTOREAL / f"{name}_{cap}.png").diagnostics
    assert d["verdict"] == "non_square_repeat"
    assert d["grid_diagnosis"] == "non_square_content"
    assert d["lattice_snr"]["snr"] >= T4


def test_steep_angle_diagnosis_survives_on_genuine_skew():
    # render_perspective_jpeg at the phone cap is a genuinely skewed square
    # quilt: its "block" (~6 px) is FINER than the cell pitch, so no coarse
    # block is found and the anisotropic_pitch (steep-angle) diagnosis stands -
    # the non_square_content override fires only when a coarse block exists.
    d = reverse(PHOTOREAL / "render_perspective_jpeg_1400.png").diagnostics
    assert d["verdict"] == "no_grid"
    assert d["grid_diagnosis"] == "anisotropic_pitch"


# ---------------------------------------------------------------------------
# (2) end-to-end inertness: every currently-passing fixture is untouched
# ---------------------------------------------------------------------------

_PASSING_TODAY = [
    ("render_on_white", "readable"),
    ("render_on_wood", "readable"),
    ("antique_wash_chain", "readable"),
    ("quarter_circle_fine", "readable"),
    ("drunkards_path", "non_square_repeat"),
    ("hst_star", "non_square_repeat"),
    ("low_contrast_hst", "non_square_repeat"),  # 1400 passes on its own
    ("degraded_hst_star", "non_square_repeat"),
]


@pytest.mark.parametrize("name,expected", _PASSING_TODAY)
def test_currently_passing_fixtures_are_inert(name, expected):
    # a fixture whose 1D read succeeds (grid conf >= T1) keeps its verdict and
    # never builds corroboration - the block hint is None, so the model is
    # byte-identical to pre-S2 on it.
    d = reverse(PHOTOREAL / f"{name}_1400.png").diagnostics
    assert d["verdict"] == expected
    assert d["lattice_snr"] is None
