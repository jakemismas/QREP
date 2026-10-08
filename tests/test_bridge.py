"""Bridge module tests (S1, issue #41).

qrep/bridge.py is the engine-side seam for the web UI: pure functions taking
and returning JSON strings, every one wrapped in the typed envelope
{"ok": true, "result": ...} | {"ok": false, "error": {"kind", "message"}}.
Byte payloads (PDF, PNG) ride inside the envelope base64-encoded so byte
producers still return typed envelopes.

Every expected value here is hand-computed (derivation in the comment) or a
cross-check against the frozen goldens / the already-hand-tested sprint 1
implementations. Never observed output.

Fixture geometry (design doc, do not re-derive): 45x55 cells of 12 eighths
(1 1/2in), one border band of 30 eighths (3 3/4in), block 5, finished top
600x720 eighths (75in x 90in).
"""

import ast
import base64
import inspect
import json
import re
import struct
from pathlib import Path

import pypdf
import pytest

from qrep import bridge
from qrep.contract import CONTRACT_VERSION
from qrep.export.pdf import SECTION_TITLES
from qrep.export.yardage_report import render_yardage_md
from qrep.construct.strategies import STRATEGIES
from qrep.model import load
from qrep.render import save_render

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"
GOLDEN_DIR = Path(__file__).parent / "golden"
# The Pyodide suite mounts the whole checkout at /repo, so the web sources
# resolve there too.
ENGINE_TS_DIR = Path(__file__).parent.parent / "web" / "src" / "engine"


@pytest.fixture
def model_json() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


@pytest.fixture
def quilt():
    return load(FIXTURE_PATH)


def ok_result(raw: str) -> dict:
    envelope = json.loads(raw)
    assert envelope["ok"] is True, f"expected ok envelope, got {envelope}"
    return envelope["result"]


def error_of(raw: str) -> dict:
    envelope = json.loads(raw)
    assert envelope["ok"] is False, "expected error envelope"
    error = envelope["error"]
    assert set(error) >= {"kind", "message"}
    assert "Traceback" not in error["message"], "no stringified tracebacks reach the UI"
    return error


# A minimal valid model for clamp-edge tests: grid of 20-eighth (2 1/2in)
# squares, one 2-eighth (1/4in) border band, two fabrics. All-background cells
# except one accent square at (0,0) so the palette is exercised. The default
# 5x7 shape has gcd(rows,cols)=1, so infer_block_structure finds no block
# period and unlocked resize moves one square at a time.
def mini_model(cell_size: int = 20, band_width: int = 2, rows: int = 5, cols: int = 7) -> str:
    cells = [["c"] * cols for _ in range(rows)]
    cells[0][0] = "b"
    return json.dumps(
        {
            "schema_version": "1",
            "metadata": {"name": "mini"},
            "palette": {
                "fabrics": [
                    {"id": "c", "name": "Background", "color": "#f5f0e6"},
                    {"id": "b", "name": "Accent", "color": "#7a9cc6"},
                ]
            },
            "center": {
                "rows": rows,
                "cols": cols,
                "cell_size": cell_size,
                "cells": cells,
            },
            "borders": [{"fabric_id": "c", "width": band_width}],
            "binding": {"fabric_id": "b"},
        }
    )


# ---------------------------------------------------------------- module shape


def test_bridge_never_imports_typer():
    # The design doc pins the bridge as typer-free. Structural check on the
    # source: no import statement mentions typer (or click).
    source = Path(bridge.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for name in names:
            assert not name.startswith(("typer", "click")), f"bridge imports {name}"


@pytest.mark.skipif(
    __import__("sys").platform == "emscripten",
    reason="subprocess is unavailable under wasm; the import graph is "
    "platform-independent and verified on native CPython",
)
def test_bridge_import_does_not_load_cv2():
    # S6 (issue #46): the vision wheel lazy-loads in the browser on first
    # photo use, so importing the bridge must not pull cv2 - otherwise the
    # worker boot would need opencv. Clean interpreter via subprocess.
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import qrep.bridge, sys; raise SystemExit(0 if 'cv2' not in sys.modules else 1)",
        ],
        capture_output=True,
    )
    assert result.returncode == 0, "importing qrep.bridge must not import cv2"


# ------------------------------------------------------------------- validate


def test_validate_happy_summary(model_json):
    # Hand-computed: fixture is 55 rows x 45 cols, 2 fabrics; finished
    # 600x720 eighths; batting per PARITY item 9 = finished + 4in per side
    # = +64 eighths per axis -> 664x784 (83in x 98in); usable width =
    # settings default 336 (42in).
    result = ok_result(bridge.validate(model_json))
    # The fixture's authored metadata.name (tests/fixtures/double_irish_chain.json).
    assert result["name"] == "Double Irish Chain 75x90"
    assert result["rows"] == 55
    assert result["cols"] == 45
    assert result["fabric_count"] == 2
    assert result["finished_width"] == 600
    assert result["finished_height"] == 720
    assert result["batting_width"] == 664
    assert result["batting_height"] == 784
    assert result["usable_width"] == 336


def test_validate_summary_fabric_census(model_json):
    # S2 fabric-summary criterion: per-fabric center-cell counts come from
    # the bridge, not JS. Design-doc census over the 45x55 center field:
    # 1246 blue (b), 1229 cream (c), total 2475 (also pinned by the fixture
    # tests). Names/colors are the fixture's authored palette.
    result = ok_result(bridge.validate(model_json))
    fabrics = {f["id"]: f for f in result["fabrics"]}
    assert fabrics["b"]["cell_count"] == 1246
    assert fabrics["c"]["cell_count"] == 1229
    assert fabrics["b"]["name"] == "Chain blue"
    assert fabrics["c"]["name"] == "Background cream"
    assert fabrics["b"]["color"].startswith("#")


def test_validate_malformed_json_is_schema_kind():
    assert error_of(bridge.validate("{not json"))["kind"] == "schema"


def test_validate_unknown_schema_version_is_schema_kind(model_json):
    doc = json.loads(model_json)
    doc["schema_version"] = "2"
    assert error_of(bridge.validate(json.dumps(doc)))["kind"] == "schema"


def test_validate_missing_field_is_validation_kind(model_json):
    doc = json.loads(model_json)
    del doc["palette"]
    assert error_of(bridge.validate(json.dumps(doc)))["kind"] == "validation"


# ----------------------------------------------------------------------- plan


def test_plan_strip_carries_plan_summary_and_yardage(model_json):
    result = ok_result(bridge.plan(model_json, "strip"))
    # strip_set_count 25 is the hand-computed design-doc number, pinned by
    # test_construct.test_fixture_strip_sets_match_design_doc.
    assert result["plan"]["strategy"] == "strip"
    assert result["plan"]["metrics"]["strip_set_count"] == 25
    # Summary duplicates the validate() numbers (same derivation).
    assert result["summary"]["batting_width"] == 664
    assert result["summary"]["usable_width"] == 336
    # Yardage includes binding and backing lines (purpose taxonomy from the
    # yardage module).
    purposes = {line["purpose"] for line in result["yardage"]["lines"]}
    assert {"top", "binding", "backing"} <= purposes


def test_plan_historical_piece_count(model_json):
    # Hand-computed in test_construct: 2475 center cells + 4 border pieces =
    # 2479 pieces for the historical strategy.
    result = ok_result(bridge.plan(model_json, "historical"))
    assert result["plan"]["metrics"]["piece_count"] == 2479


def test_plan_unknown_strategy_is_value_kind(model_json):
    assert error_of(bridge.plan(model_json, "no-such-strategy"))["kind"] == "value"


def test_plan_stub_strategy_is_not_implemented_kind(model_json):
    assert error_of(bridge.plan(model_json, "fpp"))["kind"] == "not_implemented"


def test_plan_internal_errors_are_wrapped(model_json, monkeypatch):
    def boom(_quilt):
        raise RuntimeError("secret internals: /home/user/qrep/construct.py line 42")

    monkeypatch.setitem(STRATEGIES, "historical", boom)
    error = error_of(bridge.plan(model_json, "historical"))
    assert error["kind"] == "internal"
    # The raw exception text must not leak through the seam.
    assert "secret internals" not in error["message"]


# -------------------------------------------------------------------- exports


def test_export_cutlist_csv_matches_frozen_golden(model_json):
    # Double anchor: byte-equal to the frozen golden AND to the tested
    # sprint 1 renderer output.
    result = ok_result(bridge.export_cutlist_csv(model_json, "strip"))
    golden = (GOLDEN_DIR / "cutlist_strip.csv").read_bytes()
    assert result["text"].encode("utf-8") == golden


def test_export_cutlist_md_matches_frozen_golden(model_json):
    result = ok_result(bridge.export_cutlist_md(model_json, "strip"))
    golden = (GOLDEN_DIR / "cutlist_strip.md").read_bytes()
    assert result["text"].encode("utf-8") == golden


def test_export_yardage_equals_sprint1_renderer(model_json, quilt):
    # Equivalence to the hand-tested sprint 1 implementation (no yardage
    # golden exists; test_construct pins its numbers).
    from qrep.construct.yardage import compute_purchase_lines

    plan_obj = STRATEGIES["strip"](quilt)
    expected = render_yardage_md(compute_purchase_lines(quilt, plan_obj))
    result = ok_result(bridge.export_yardage(model_json, "strip"))
    assert result["text"] == expected


def test_export_svg_matches_frozen_golden(model_json):
    result = ok_result(bridge.export_svg(model_json))
    golden = (GOLDEN_DIR / "top.svg").read_bytes()
    assert result["text"].encode("utf-8") == golden


def test_export_bad_strategy_is_value_kind(model_json):
    assert error_of(bridge.export_cutlist_csv(model_json, "nope"))["kind"] == "value"


def test_export_yardage_bad_model_is_schema_kind():
    assert error_of(bridge.export_yardage("[]", "strip"))["kind"] == "schema"


def test_export_svg_bad_model_is_validation_kind(model_json):
    doc = json.loads(model_json)
    doc["center"]["rows"] = -1
    assert error_of(bridge.export_svg(json.dumps(doc)))["kind"] == "validation"


# ------------------------------------------------------------------------ pdf


def test_export_pdf_passes_pypdf_section_checks(model_json, quilt, tmp_path):
    result = ok_result(bridge.export_pdf(model_json, "strip"))
    pdf_bytes = base64.b64decode(result["pdf_b64"])
    assert pdf_bytes[:5] == b"%PDF-"
    out = tmp_path / "bridge-booklet.pdf"
    out.write_bytes(pdf_bytes)
    reader = pypdf.PdfReader(str(out))
    text = re.sub(
        r"\s+", " ", "\n".join((page.extract_text() or "") for page in reader.pages)
    )
    for title in SECTION_TITLES:
        assert title in text
    for fabric in quilt.palette.fabrics:
        assert fabric.name in text


def test_export_pdf_twice_is_byte_identical(model_json):
    # The bridge produces reproducible PDFs (reportlab invariant mode inside
    # the bridge only; the sprint 1 exporter's own output is unchanged).
    first = ok_result(bridge.export_pdf(model_json, "strip"))["pdf_b64"]
    second = ok_result(bridge.export_pdf(model_json, "strip"))["pdf_b64"]
    assert first == second


def test_export_pdf_bad_strategy_is_value_kind(model_json):
    assert error_of(bridge.export_pdf(model_json, "nope"))["kind"] == "value"


# ---------------------------------------------------------------------- render


def test_render_returns_png_and_is_deterministic(model_json):
    result = ok_result(bridge.render(model_json, level=0, seed=42, scale=2))
    png = base64.b64decode(result["png_b64"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    again = ok_result(bridge.render(model_json, level=0, seed=42, scale=2))
    assert result["png_b64"] == again["png_b64"]
    # Sidecar ground truth rides along for harness use.
    assert "corners" in result["sidecar"]


def test_render_bad_level_is_value_kind(model_json):
    assert error_of(bridge.render(model_json, level=7, seed=42, scale=2))["kind"] == "value"


# --------------------------------------------------------------------- reverse


def test_reverse_recovers_fixture_dims(model_json, quilt, tmp_path):
    # Stage an L0 render to a file path exactly as the UI stages uploaded
    # bytes onto MEMFS, then reverse the path. Interior dims are the fixture
    # geometry: 55 rows x 45 cols.
    png_path, _ = save_render(quilt, tmp_path / "l0.png", level=0, seed=42, scale=10)
    result = ok_result(bridge.reverse(str(png_path), "{}"))
    assert result["model"]["center"]["rows"] == 55
    assert result["model"]["center"]["cols"] == 45
    assert result["model"]["provenance"]["source"] != "authored"
    assert set(result["model"]["provenance"]["stage_confidence"]) >= {"rectify", "grid"}


def test_reverse_missing_file_is_value_kind():
    assert error_of(bridge.reverse("/no/such/photo.png", "{}"))["kind"] == "value"


def test_reverse_bad_options_is_schema_kind(tmp_path, quilt):
    png_path, _ = save_render(quilt, tmp_path / "l0b.png", level=0, seed=42, scale=2)
    assert error_of(bridge.reverse(str(png_path), "{nope"))["kind"] == "schema"


# --------------------------------------------------------------------- compare


def test_compare_truth_with_itself(model_json):
    result = ok_result(bridge.compare(model_json, model_json))
    assert result["dims_match"] is True
    assert result["cell_accuracy"] == 1.0


def test_compare_bad_recovered_is_schema_kind(model_json):
    assert error_of(bridge.compare(model_json, "{broken"))["kind"] == "schema"


# ---------------------------------------------------------------- resize locked
#
# PARITY item 4 semantics. The cell-size math reuses qrep/viewer/sizing.py
# (its literals hold exactly); the NEW layer scales border bands by the cell
# factor with round_div, floor 1/4in (2), cap 14in (112); requested dims are
# quarter-rounded then clamped [20in,140in] = [160,1120]; cell clamps
# [3/4in,4in] = [6,32].


def test_resize_locked_width_scales_cell_and_bands(model_json):
    # Width 720: interior 720-60=660; cell = round_div(660,45) = 15 (the
    # test_viewer queen literal). Band factor 15/12: round_div(30*15,12) =
    # round_div(450,12) = floor(456/12) = 38. Achieved: 45*15+2*38 = 751;
    # 55*15+2*38 = 901.
    result = ok_result(bridge.resize_locked(model_json, json.dumps({"width": 720})))
    assert result["model"]["center"]["cell_size"] == 15
    assert result["model"]["center"]["rows"] == 55
    assert result["model"]["center"]["cols"] == 45
    assert [b["width"] for b in result["model"]["borders"]] == [38]
    assert result["achieved"]["width"] == 751
    assert result["achieved"]["height"] == 901
    assert result["requested"]["width"] == 720


def test_resize_locked_identity(model_json):
    # Width 600 is the fixture's own width: cell (600-60)/45 = 12 exactly;
    # band factor 12/12 leaves the band at 30; achieved = 600x720 unchanged.
    result = ok_result(bridge.resize_locked(model_json, json.dumps({"width": 600})))
    assert result["model"]["center"]["cell_size"] == 12
    assert [b["width"] for b in result["model"]["borders"]] == [30]
    assert result["achieved"]["width"] == 600
    assert result["achieved"]["height"] == 720


def test_resize_locked_by_cell(model_json):
    # Cell 16 (2in): bands scale by 16/12: round_div(30*16,12) = 40.
    # Achieved: 45*16+80 = 800; 55*16+80 = 960.
    result = ok_result(bridge.resize_locked(model_json, json.dumps({"cell": 16})))
    assert result["model"]["center"]["cell_size"] == 16
    assert [b["width"] for b in result["model"]["borders"]] == [40]
    assert result["achieved"]["width"] == 800
    assert result["achieved"]["height"] == 960


def test_resize_locked_preset_takes_min_ratio_and_clamps_cell(model_json):
    # Crib preset 288x416. By width: round_div(288-60,45) = round_div(228,45)
    # = floor(250/45) = 5. By height: round_div(416-60,55) = round_div(356,55)
    # = floor(383/55) = 6. min(5,6) = 5, clamped up to the 3/4in floor = 6.
    # Bands: round_div(30*6,12) = 15. Achieved: 45*6+30 = 300; 55*6+30 = 360.
    target = {"preset": {"width": 288, "height": 416}}
    result = ok_result(bridge.resize_locked(model_json, json.dumps(target)))
    assert result["model"]["center"]["cell_size"] == 6
    assert [b["width"] for b in result["model"]["borders"]] == [15]
    assert result["achieved"]["width"] == 300
    assert result["achieved"]["height"] == 360


def test_resize_locked_clamps_requested_width(model_json):
    # 1200 exceeds the 140in cap: requested records the clamped 1120. Cell =
    # round_div(1120-60,45) = floor((1060+22)/45) = 24 (within [6,32]).
    # Bands: round_div(30*24,12) = 60.
    result = ok_result(bridge.resize_locked(model_json, json.dumps({"width": 1200})))
    assert result["requested"]["width"] == 1120
    assert result["model"]["center"]["cell_size"] == 24
    assert [b["width"] for b in result["model"]["borders"]] == [60]


def test_resize_locked_quarter_rounds_requested_width(model_json):
    # 723 eighths (90 3/8in) rounds to the nearest quarter inch: 724 (90 1/2in).
    # Cell = round_div(724-60,45) = floor((664+22)/45) = 15.
    result = ok_result(bridge.resize_locked(model_json, json.dumps({"width": 723})))
    assert result["requested"]["width"] == 724
    assert result["model"]["center"]["cell_size"] == 15


def test_resize_locked_band_floor_quarter_inch():
    # Mini model: cell 20, band 2 (1/4in). Target cell 6: band factor 6/20:
    # round_div(2*6,20) = floor((12+10)/20) = 1, floored to 2 (1/4in).
    result = ok_result(bridge.resize_locked(mini_model(), json.dumps({"cell": 6})))
    assert result["model"]["center"]["cell_size"] == 6
    assert [b["width"] for b in result["model"]["borders"]] == [2]


def test_resize_locked_no_target_is_value_kind(model_json):
    assert error_of(bridge.resize_locked(model_json, "{}"))["kind"] == "value"


def test_resize_locked_bad_model_is_schema_kind():
    assert error_of(bridge.resize_locked("{bad", "{}"))["kind"] == "schema"


# -------------------------------------------------------------- resize unlocked
#
# Cell size and bands never change; whole blocks are added or removed per
# axis (block inferred from the grid, 5 for the fixture), content preserved
# anchored top-left, extension tiles the grid's minimal row/col period.


def test_resize_unlocked_grows_whole_blocks(model_json):
    # Width 780: interior 720; blocks = round_div(720, 5*12) = 12 -> 60 cols
    # (the test_viewer exact-block-fit literal). Bands stay 30. Achieved:
    # 60*12+60 = 780 wide, 55*12+60 = 720 high.
    result = ok_result(bridge.resize_unlocked(model_json, json.dumps({"width": 780})))
    center = result["model"]["center"]
    assert (center["rows"], center["cols"]) == (55, 60)
    assert center["cell_size"] == 12
    assert [b["width"] for b in result["model"]["borders"]] == [30]
    assert result["achieved"]["width"] == 780
    assert result["achieved"]["height"] == 720
    # Regrid continuation, hand-derived: the fixture's column period is 10
    # (A/B blocks alternate 2-wide). New col 45 continues as col 45%10 = 5.
    # Cell (0,45): block-row 0, block-col 9 -> type (0+9)%2 = B; B row 0 is
    # bcccb, local col 0 -> 'b'. Old cell (0,5) is the same 'b' by the same
    # derivation on block-col 1.
    assert center["cells"][0][45] == "b"
    # Cell (0,54): block-col 10 -> type (0+10)%2 = A; A row 0 is bbcbb,
    # local col 4 -> 'b'.
    assert center["cells"][0][54] == "b"
    # Cell (2,47): block-col 9 type B; B row 2 is ccccc, local col 2 -> 'c'.
    assert center["cells"][2][47] == "c"


def test_resize_unlocked_quantizes_to_blocks(model_json):
    # Width 700: interior 640; 640/60 = 10.67 -> 11 blocks -> 55 cols;
    # achieved 55*12+60 = 720 (the test_viewer quantize literal).
    result = ok_result(bridge.resize_unlocked(model_json, json.dumps({"width": 700})))
    assert result["model"]["center"]["cols"] == 55
    assert result["achieved"]["width"] == 720
    assert result["requested"]["width"] == 700


def test_resize_unlocked_height_independent(model_json):
    # Height 780: interior 720; blocks = 12 -> 60 rows; cols untouched
    # (the test_viewer height literal). Row continuation: row 55 continues
    # the period-10 pattern as row 5 (block-row 1), NOT row 0 - the
    # checkerboard parity must alternate.
    result = ok_result(bridge.resize_unlocked(model_json, json.dumps({"height": 780})))
    center = result["model"]["center"]
    assert (center["rows"], center["cols"]) == (60, 45)
    assert result["achieved"]["height"] == 780
    # Hand-derived: block-row 11 -> type (11+0)%2 = B for block-col 0; B row 0
    # is bcccb -> cell (55,0) = 'b', cell (55,1) = 'c'. Row 5 (block-row 1,
    # same parity) starts identically.
    assert center["cells"][55][0] == "b"
    assert center["cells"][55][1] == "c"
    assert center["cells"][55] == center["cells"][5]


def test_resize_unlocked_shrinks_by_truncation(model_json, quilt):
    # Width 480: interior 420; blocks = round_div(420,60) = 7 -> 35 cols.
    # Content anchored top-left: every kept cell equals the original.
    result = ok_result(bridge.resize_unlocked(model_json, json.dumps({"width": 480})))
    center = result["model"]["center"]
    assert center["cols"] == 35
    original = quilt.center.cells
    assert all(
        center["cells"][r][c] == original[r][c] for r in range(0, 55, 7) for c in range(35)
    )


def test_resize_unlocked_blockless_model_moves_by_one():
    # The 5x7 mini model has gcd(5,7)=1 so no block period exists: block = 1.
    # Width 170: interior 170-4 = 166; cells = round_div(166,20) =
    # floor((166+10)/20) = 8 -> 8 cols of cell 20; achieved 8*20+4 = 164.
    # Extension: the accent at (0,0) makes every column period fail until the
    # full width, so the minimal column period is 7 and the new col 7 tiles
    # from col 0, accent included.
    result = ok_result(bridge.resize_unlocked(mini_model(), json.dumps({"width": 170})))
    center = result["model"]["center"]
    assert center["cols"] == 8
    assert result["achieved"]["width"] == 164
    assert center["cells"][0][7] == "b"
    assert center["cells"][1][7] == "c"


def test_resize_unlocked_uniform_grid_moves_by_single_squares():
    # PARITY item 15: a uniform single-fabric grid has no real block
    # structure - the trivial all-identical-blocks tiling must not quantize
    # resize. Blank-grid-like model: 24 rows x 18 cols of 20 eighths, one
    # 20-eighth border (border total 20). Width 420: interior 420-40 = 380;
    # single-square steps give round_div(380,20) = floor((380+10)/20) = 19
    # cols. (A degenerate block-2 reading would give round_div(380,40)*2 =
    # 20 - that is the bug this test pins against.)
    doc = json.loads(mini_model(cell_size=20, band_width=20, rows=24, cols=18))
    doc["center"]["cells"] = [["c"] * 18 for _ in range(24)]
    result = ok_result(bridge.resize_unlocked(json.dumps(doc), json.dumps({"width": 420})))
    assert result["model"]["center"]["cols"] == 19
    assert result["achieved"]["width"] == 19 * 20 + 40


def test_resize_unlocked_no_target_is_value_kind(model_json):
    assert error_of(bridge.resize_unlocked(model_json, "{}"))["kind"] == "value"


# ------------------------------------------------------ contract version (E1a)


def test_contract_version_literals_agree():
    # Plan section 4.2: a contract change bumps CONTRACT_VERSION in Python and
    # TypeScript together, so the two literals must never differ.
    source = (ENGINE_TS_DIR / "contract.ts").read_text(encoding="utf-8")
    found = re.findall(r"^export const CONTRACT_VERSION = (\d+);$", source, re.MULTILINE)
    assert len(found) == 1, f"expected one CONTRACT_VERSION literal in contract.ts, got {found}"
    assert int(found[0]) == CONTRACT_VERSION
    # E1a starts the v2 contract (SPEC.md section 12.1); later bumps only grow it.
    assert CONTRACT_VERSION >= 2


def test_contract_version_reports_the_python_literal():
    assert ok_result(bridge.contract_version()) == {"contract_version": CONTRACT_VERSION}


def _worker_bridge_methods() -> set[str]:
    source = (ENGINE_TS_DIR / "worker.ts").read_text(encoding="utf-8")
    block = re.search(r"const BRIDGE_METHODS = new Set\(\[(.*?)\]\);", source, re.DOTALL)
    assert block is not None, "BRIDGE_METHODS not found in worker.ts"
    names = set(re.findall(r'"([A-Za-z_]\w*)"', block.group(1)))
    assert names, "BRIDGE_METHODS parsed to an empty set"
    return names


def test_worker_allowlist_equals_bridge_envelope_functions():
    # The worker rejects any method outside BRIDGE_METHODS without touching
    # Python, so a bridge function missing from it is unreachable and a stale
    # name in it reaches Python as an AttributeError.
    public = {
        name
        for name, fn in inspect.getmembers(bridge, inspect.isfunction)
        if fn.__module__ == bridge.__name__ and not name.startswith("_")
    }
    unwrapped = sorted(
        name for name in public if not getattr(getattr(bridge, name), "is_envelope", False)
    )
    assert unwrapped == [], f"public bridge functions without the envelope: {unwrapped}"
    assert _worker_bridge_methods() == public


# ------------------------------------------------------ error mapping (E1a)
#
# engine-16: validation for a wrong argument type or structure, naming the
# field; value for a well-formed input the engine rejects, naming the input;
# internal for an exception that signals an engine bug.

NO_PHOTO = "/no/such/photo.png"


@pytest.mark.parametrize(
    ("call", "field"),
    [
        (lambda m: bridge.validate(42), "model_json"),
        (lambda m: bridge.compare(m, None), "recovered_json"),
        (lambda m: bridge.plan(m, 7), "strategy"),
        (lambda m: bridge.export_pdf(m, ["strip"]), "strategy"),
        (lambda m: bridge.render(m, "abc", 42, 2), "level"),
        (lambda m: bridge.render(m, True, 42, 2), "level"),
        (lambda m: bridge.render(m, 0, 42, None), "scale"),
        # 20.9 is not a whole scale; truncating it to 20 would pass the range.
        (lambda m: bridge.render(m, 0, 42, 20.9), "scale"),
        (lambda m: bridge.detect_quad(17), "image_path"),
        (lambda m: bridge.reverse(17, "{}"), "image_path"),
        (lambda m: bridge.reverse(NO_PHOTO, 5), "options_json"),
        (lambda m: bridge.reverse(NO_PHOTO, 0), "options_json"),
        (lambda m: bridge.reverse(NO_PHOTO, "[]"), "options_json"),
        (
            lambda m: bridge.reverse(NO_PHOTO, json.dumps({"corners": [[0, 0], [9, 0], [9, 9]]})),
            "options_json.corners",
        ),
        (
            lambda m: bridge.reverse(NO_PHOTO, json.dumps({"corners": [["a", 0]] * 4})),
            "options_json.corners",
        ),
        (
            lambda m: bridge.reverse(NO_PHOTO, json.dumps({"corners": [["1", "1"]] * 4})),
            "options_json.corners",
        ),
        (
            lambda m: bridge.reverse(NO_PHOTO, json.dumps({"corners": [[float("nan"), 0]] * 4})),
            "options_json.corners",
        ),
        (
            lambda m: bridge.reverse(NO_PHOTO, json.dumps({"corners": [[float("inf"), 0]] * 4})),
            "options_json.corners",
        ),
        (
            # 10**400 overflows float, so it is no finite coordinate.
            lambda m: bridge.reverse(NO_PHOTO, json.dumps({"corners": [[10**400, 0]] * 4})),
            "options_json.corners",
        ),
        (
            lambda m: bridge.reverse(NO_PHOTO, json.dumps({"finished_width": "abc"})),
            "options_json.finished_width",
        ),
        (
            lambda m: bridge.reverse(NO_PHOTO, json.dumps({"finished_width": True})),
            "options_json.finished_width",
        ),
        (
            lambda m: bridge.reverse(NO_PHOTO, json.dumps({"fabrics": "three"})),
            "options_json.fabrics",
        ),
        (lambda m: bridge.apply_finished_size(m, "abc", None), "width"),
        (lambda m: bridge.apply_finished_size(m, True, None), "width"),
        (lambda m: bridge.apply_finished_size(m, None, [600]), "height"),
        (lambda m: bridge.resize_locked(m, 5), "target_json"),
        (lambda m: bridge.resize_locked(m, "[]"), "target_json"),
        (lambda m: bridge.resize_locked(m, json.dumps({"width": "abc"})), "target_json.width"),
        (lambda m: bridge.resize_locked(m, json.dumps({"width": "600"})), "target_json.width"),
        (lambda m: bridge.resize_locked(m, json.dumps({"cell": None})), "target_json.cell"),
        (lambda m: bridge.resize_locked(m, json.dumps({"preset": "Queen"})), "target_json.preset"),
        (
            lambda m: bridge.resize_locked(m, json.dumps({"preset": {"width": "x", "height": 416}})),
            "target_json.preset.width",
        ),
        (lambda m: bridge.resize_unlocked(m, json.dumps({"height": [1]})), "target_json.height"),
    ],
    ids=[
        "validate-model",
        "compare-recovered",
        "plan-strategy",
        "export-pdf-strategy",
        "render-level",
        "render-level-bool",
        "render-scale",
        "render-scale-fraction",
        "detect-quad-path",
        "reverse-path",
        "reverse-options-number",
        "reverse-options-zero",
        "reverse-options-array",
        "reverse-three-corners",
        "reverse-text-corners",
        "reverse-numeric-text-corners",
        "reverse-nan-corners",
        "reverse-infinite-corners",
        "reverse-overflowing-corners",
        "reverse-finished-width",
        "reverse-finished-width-bool",
        "reverse-fabrics",
        "apply-size-width",
        "apply-size-width-bool",
        "apply-size-height",
        "resize-target-number",
        "resize-target-array",
        "resize-width-text",
        "resize-width-numeric-text",
        "resize-cell-null",
        "resize-preset-name",
        "resize-preset-width-text",
        "resize-unlocked-height-list",
    ],
)
def test_argument_shape_errors_are_validation_kind_naming_the_field(model_json, call, field):
    error = error_of(call(model_json))
    assert error["kind"] == "validation"
    assert error["message"].startswith(f"argument failed validation: {field}: ")


@pytest.mark.parametrize(
    ("call", "named"),
    [
        (lambda m: bridge.plan(m), "strategy"),
        (lambda m: bridge.render(m, 0, 42), "scale"),
        (lambda m: bridge.contract_version(1), "too many"),
        (lambda m: bridge.validate(m, "extra"), "too many"),
    ],
    ids=["plan-missing", "render-missing", "contract-version-extra", "validate-extra"],
)
def test_wrong_argument_count_is_validation_kind(model_json, call, named):
    error = error_of(call(model_json))
    assert error["kind"] == "validation"
    assert named in error["message"]


def test_unknown_strategy_stays_value_kind_naming_it(model_json):
    error = error_of(bridge.plan(model_json, "no-such-strategy"))
    assert error["kind"] == "value"
    assert "no-such-strategy" in error["message"]


@pytest.mark.parametrize(
    ("preset", "named"),
    [({"width": 288}, '"width": 288'), ({}, "{}")],
    ids=["preset-missing-height", "preset-empty"],
)
def test_unknown_preset_stays_value_kind_naming_it(model_json, preset, named):
    # A preset object without both sizes was kind value through the old
    # KeyError mapping; it stays value, and the message now quotes the preset.
    error = error_of(bridge.resize_locked(model_json, json.dumps({"preset": preset})))
    assert error["kind"] == "value"
    assert error["message"].startswith("unknown preset ")
    assert named in error["message"]


@pytest.mark.parametrize(
    ("call", "named"),
    [
        (lambda: bridge.render(mini_model(), 0, -1, 2), "seed"),
        (lambda: bridge.reverse(NO_PHOTO, json.dumps({"fabrics": 0})), "fabrics"),
        # 13 is one past FABRICS_MAX = 12 (SPEC.md section 12.1).
        (lambda: bridge.reverse(NO_PHOTO, json.dumps({"fabrics": 13})), "fabrics"),
    ],
    ids=["render-negative-seed", "reverse-zero-fabrics", "reverse-thirteen-fabrics"],
)
def test_out_of_range_inputs_are_value_kind_naming_them(call, named):
    error = error_of(call())
    assert error["kind"] == "value"
    assert named in error["message"]


@pytest.mark.parametrize("options_json", [None, ""], ids=["none", "empty"])
def test_reverse_without_options_reaches_the_image_check(options_json):
    # No options is a valid request: the call gets past option parsing and
    # stops at the missing image, the first check after it.
    error = error_of(bridge.reverse(NO_PHOTO, options_json))
    assert error["kind"] == "value"
    assert error["message"] == f"image file not found: {NO_PHOTO}"


def test_render_accepts_integral_floats():
    # 0.0, 42.0 and 2.0 are whole numbers; the sidecar records scale 2.
    result = ok_result(bridge.render(mini_model(), 0.0, 42.0, 2.0))
    assert result["sidecar"]["scale"] == 2


@pytest.mark.parametrize("exception", [KeyError, TypeError, AttributeError])
def test_engine_bug_exceptions_are_internal_kind(model_json, monkeypatch, exception):
    def boom(_quilt):
        raise exception("secret internals: /home/user/qrep/construct.py line 42")

    monkeypatch.setitem(STRATEGIES, "historical", boom)
    error = error_of(bridge.plan(model_json, "historical"))
    assert error["kind"] == "internal"
    assert "secret internals" not in error["message"]


# --------------------------------------------------------- render scale (E1a)


@pytest.mark.parametrize("scale", [0, 21])
def test_render_scale_outside_the_documented_range_is_value_kind(scale):
    error = error_of(bridge.render(mini_model(), 0, 42, scale))
    assert error["kind"] == "value"
    # The message names the documented range, 1 to RENDER_SCALE_MAX = 20.
    assert "20" in error["message"]
    assert bridge.RENDER_SCALE_MAX == 20


def test_render_scale_at_the_maximum_renders():
    # Mini model: finished width 7 cols x 20 + 2 x 2 = 144 eighths (18in),
    # height 5 x 20 + 4 = 104 eighths (13in). At 20 px per inch:
    # 144 x 20 / 8 = 360 px and 104 x 20 / 8 = 260 px; margin =
    # round(0.08 x 360) = round(28.8) = 29 px per side (renderer.py
    # MARGIN_FRACTION). L0 adds nothing else: 360 + 58 = 418 by 260 + 58 = 318.
    result = ok_result(bridge.render(mini_model(), 0, 42, 20))
    png = base64.b64decode(result["png_b64"])
    width, height = struct.unpack(">II", png[16:24])  # IHDR width, height
    assert (width, height) == (418, 318)
