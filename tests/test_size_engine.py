"""S6 size engine: reconcile math, presets, provenance (sprint 3, #72).

Every expected value is hand-computed in the comments beside it. FROZEN at
test-write time: ASPECT_TOL = 0.04 for the unique-preset suggestion
(detection aspect residue measures 2-3%; Twin and Throw sit 1.1% apart, so
they are structurally ambiguous and the uniqueness rule yields None there
by design). The editor clamps CELL_MIN=6 / CELL_MAX=32 eighths are the
frozen approval decision reused verbatim.
"""

import json
from pathlib import Path

import pytest

from qrep import bridge
from qrep.model import load, loads
from qrep.model.finished_size import (
    ASPECT_TOL,
    apply_finished_size,
    suggest_preset,
)
from qrep.model.schema import Binding, Fabric, GridRegion, Palette, Quilt, QuiltMetadata
from qrep.render import save_render
from qrep.vision import reverse
from qrep.viewer.sizing import PRESETS

FIXTURE = Path(__file__).parent / "fixtures" / "double_irish_chain.json"


def _grid_model(rows: int, cols: int, cell: int, band: int | None) -> Quilt:
    fabrics = [Fabric(id="a", name="A", color="#333366"), Fabric(id="b", name="B", color="#eeeedd")]
    cells = [["a" if (r + c) % 2 == 0 else "b" for c in range(cols)] for r in range(rows)]
    return Quilt(
        metadata=QuiltMetadata(name="probe"),
        palette=Palette(fabrics=fabrics),
        center=GridRegion(rows=rows, cols=cols, cell_size=cell, cells=cells),
        borders=[] if band is None else [{"fabric_id": "b", "width": band}],
        binding=Binding(fabric_id="a"),
    )


# ---------------------------------------------------------------------------
# reconcile math (hand-computed)
# ---------------------------------------------------------------------------


def test_reconcile_happy_path_hand_math():
    # borderless 10 rows x 13 cols, request 30 x 24.5 in = 240 x 196 eighths:
    #   cell from W = round_div(240, 13) = (240 + 6) // 13 = 18
    #   cell from H = round_div(196, 10) = (196 + 5) // 10 = 20
    #   min = 18, inside [6, 32] -> cell 18
    #   achieved W = 13 * 18 = 234 (29 1/4 in), H = 10 * 18 = 180 (22 1/2 in)
    #   the reconcile identity: W - H = (13 - 10) * 18 = 54 = 234 - 180
    quilt = _grid_model(10, 13, 12, None)
    updated, requested, achieved = apply_finished_size(quilt, 240, 196)
    assert updated.center.cell_size == 18
    assert achieved == {"width": 234, "height": 180, "cell_size": 18, "borders": []}
    assert requested == {"width": 240, "height": 196}
    assert achieved["width"] - achieved["height"] == (13 - 10) * 18


def test_reconcile_plan_contract_86_by_67_5_clamps():
    # THE PLAN'S NAMED CASE: 86 x 67.5 in = 688 x 540 eighths over a
    # borderless 13 x 10 grid.
    #   cell from W = round_div(688, 13) = (688 + 6) // 13 = 53
    #   cell from H = round_div(540, 10) = (540 + 5) // 10 = 54
    #   min = 53 -> ABOVE CELL_MAX = 32 (the 4 in editor ceiling, frozen at
    #   approval) -> achieved-at-clamp: cell 32
    #   achieved W = 13 * 32 = 416 (52 in), H = 10 * 32 = 320 (40 in)
    # Deltas are reported, never an error.
    quilt = _grid_model(10, 13, 12, None)
    updated, requested, achieved = apply_finished_size(quilt, 688, 540)
    assert updated.center.cell_size == 32
    assert achieved["width"] == 416 and achieved["height"] == 320
    assert requested == {"width": 688, "height": 540}
    assert achieved["width"] != requested["width"]  # non-representable, honest


def test_reconcile_with_band_hand_math():
    # 10 rows x 13 cols, cell0 = 12, one band b0 = 8; request W = 60 in
    # (480 eighths), H = 47 in (376 eighths):
    #   cell from W = round_div(480 * 12, 13*12 + 2*8) = round_div(5760, 172)
    #              = (5760 + 86) // 172 = 33
    #   cell from H = round_div(376 * 12, 10*12 + 2*8) = round_div(4512, 136)
    #              = (4512 + 68) // 136 = 33
    #   min = 33 -> clamps to 32
    #   band = max(2, round_div(8 * 32, 12)) = max(2, (256 + 6) // 12) = 21
    #   achieved W = 13*32 + 2*21 = 458; H = 10*32 + 2*21 = 362
    quilt = _grid_model(10, 13, 12, 8)
    updated, _requested, achieved = apply_finished_size(quilt, 480, 376)
    assert updated.center.cell_size == 32
    assert updated.borders[0].width == 21
    assert achieved == {"width": 458, "height": 362, "cell_size": 32, "borders": [21]}


def test_reconcile_lower_clamp():
    # request tiny: 10 x 8 in = 80 x 64 eighths over 10 x 13:
    #   cell from W = round_div(80, 13) = (80 + 6) // 13 = 6
    #   cell from H = round_div(64, 10) = (64 + 5) // 10 = 6 (69 // 10)
    #   min = 6 = CELL_MIN exactly (no clamping needed, boundary case)
    quilt = _grid_model(10, 13, 12, None)
    updated, _req, achieved = apply_finished_size(quilt, 80, 64)
    assert updated.center.cell_size == 6
    assert achieved["width"] == 78 and achieved["height"] == 60

    # request even tinier: 5 x 4 in = 40 x 32: candidates 4 and 3 -> min 3
    # -> clamps UP to CELL_MIN 6; achieved 78 x 60, delta reported
    updated2, _req2, achieved2 = apply_finished_size(quilt, 40, 32)
    assert updated2.center.cell_size == 6
    assert achieved2["width"] == 78


def test_reconcile_width_only():
    # width alone: the height candidate is absent, cell derives from W only
    # round_div(240, 13) = 18; achieved H follows the model: 10*18 = 180
    quilt = _grid_model(10, 13, 12, None)
    updated, requested, achieved = apply_finished_size(quilt, 240, None)
    assert updated.center.cell_size == 18
    assert requested == {"width": 240, "height": None}
    assert achieved["height"] == 180


# ---------------------------------------------------------------------------
# preset suggestion (frozen ASPECT_TOL = 0.04, orientation-normalized)
# ---------------------------------------------------------------------------


def test_suggest_preset_unique_match():
    # Crib 36x52: aspect 52/36 = 1.4444; nearest other is Throw 65/50 = 1.30
    # (0.144 away) so 1.44 matches Crib uniquely within 0.04
    assert suggest_preset(1.4444) == "Crib"
    # orientation-normalized: 36/52 = 0.6923 must hit the same preset
    assert suggest_preset(0.6923) == "Crib"


def test_suggest_preset_ambiguous_is_none():
    # Twin 90/70 = 1.2857 and Throw 65/50 = 1.30 differ by 1.1%: an aspect
    # of 1.29 sits within 0.04 of BOTH -> uniqueness rule yields None
    assert suggest_preset(1.29) is None


def test_suggest_preset_no_match_is_none():
    # aspect 2.0 is 0.55+ from every preset
    assert suggest_preset(2.0) is None


def test_presets_bridge_export_verbatim():
    result = json.loads(bridge.presets())
    assert result["ok"] is True
    assert result["result"]["presets"] == [
        {"name": name, "width": w, "height": h} for name, w, h in PRESETS
    ]


def test_detect_quad_populates_preset_suggestion():
    # the render_on_white quad spans 50 x 60 pitches -> orientation-
    # normalized aspect 60/50 = 1.2 = Queen (108/90) exactly; the nearest
    # other preset is Twin at 1.2857 (0.086 away) -> unique within 0.04
    envelope = json.loads(
        bridge.detect_quad(str(Path("tests/fixtures/photoreal/render_on_white_1400.png")))
    )
    assert envelope["ok"] is True
    assert envelope["result"]["predicted_size"]["preset"] == "Queen"


# ---------------------------------------------------------------------------
# provenance + options threading
# ---------------------------------------------------------------------------


def test_reverse_options_thread_size_and_provenance(tmp_path):
    truth = load(FIXTURE)
    png, _ = save_render(truth, tmp_path / "l0.png", level=0, seed=42)
    sized = reverse(png, finished_width=600, finished_height=720)
    assert sized.diagnostics["size_source"] == "user"
    assert sized.diagnostics["size_is_guess"] is False
    # the achieved dims obey the reconcile identity on the recovered grid
    quilt = sized.quilt
    band_total = sum(b.width for b in quilt.borders)
    width = quilt.center.cols * quilt.center.cell_size + 2 * band_total
    height = quilt.center.rows * quilt.center.cell_size + 2 * band_total
    assert width - height == (quilt.center.cols - quilt.center.rows) * quilt.center.cell_size
    # the user path re-words the note; ASSUMED_PPI text is the guess path only
    assert "guess" not in quilt.metadata.notes.lower()

    unsized = reverse(png)
    assert unsized.diagnostics["size_source"] == "guess"
    assert unsized.diagnostics["size_is_guess"] is True
    assert "guess" in unsized.quilt.metadata.notes.lower()


def test_bridge_reverse_options_json_round_trip(tmp_path):
    truth = load(FIXTURE)
    png, _ = save_render(truth, tmp_path / "l0.png", level=0, seed=42)
    envelope = json.loads(
        bridge.reverse(str(png), json.dumps({"finished_width": 600, "finished_height": 720}))
    )
    assert envelope["ok"] is True
    result = envelope["result"]
    assert result["diagnostics"]["size_source"] == "user"
    assert "requested" in result and "achieved" in result
    assert result["requested"] == {"width": 600, "height": 720}


def test_apply_finished_size_bridge_equivalence(tmp_path):
    # applying a size to an already-recovered model must equal a fresh
    # reverse at the same size (same helper, structural equivalence)
    truth = load(FIXTURE)
    png, _ = save_render(truth, tmp_path / "l0.png", level=0, seed=42)
    fresh = json.loads(
        bridge.reverse(str(png), json.dumps({"finished_width": 600, "finished_height": 720}))
    )["result"]
    plain = json.loads(bridge.reverse(str(png), "{}"))["result"]
    applied = json.loads(
        bridge.apply_finished_size(json.dumps(plain["model"]), 600, 720)
    )["result"]
    assert applied["model"]["center"] == fresh["model"]["center"]
    assert applied["model"]["borders"] == fresh["model"]["borders"]
    assert applied["achieved"] == fresh["achieved"]
    # and the applied model still validates as a quilt
    loads(json.dumps(applied["model"]))


def test_no_new_confidence_stage(tmp_path):
    # size trust lives in diagnostics; the six-stage schema is frozen
    truth = load(FIXTURE)
    png, _ = save_render(truth, tmp_path / "l0.png", level=0, seed=42)
    sized = reverse(png, finished_width=600, finished_height=720)
    assert set(sized.quilt.provenance.stage_confidence) == {
        "rectify", "palette", "grid", "cells", "repeat", "border",
    }


def test_aspect_tol_is_the_frozen_literal():
    assert ASPECT_TOL == pytest.approx(0.04)
