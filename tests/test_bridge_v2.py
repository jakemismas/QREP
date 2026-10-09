"""Bridge v2 entry points (E1b, issue #175): the confirmed read's request,
the lazily loaded sizing and pattern calls, and the pattern summary.

Contract-level checks only, so they hold after A10 provides size_pattern
and A4d switches build_pattern to the new document; the interim's own
method choice is pinned in one test, test_interim_pattern_picks_strip_or_
historical. The read_confirmed stub and the TS agreement checks live in
tests/test_bridge.py, which the contract lease holders own.
"""

import base64
import io
import json
import subprocess
import sys
import types
from pathlib import Path

import pypdf
import pytest

from qrep import bridge
from qrep.construct import compute_purchase_lines, get_strategy
from qrep.construct.yardage import BACKING_NAME
from qrep.contract import (
    BorderBand,
    Counts,
    OuterEdgeFrame,
    PatternResult,
    ReadRequest,
    Reason,
    SizeBasis,
    SizeRequest,
    SizeResult,
)
from qrep.model.io import loads

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"


@pytest.fixture
def model_json() -> str:
    return FIXTURE_PATH.read_text(encoding="utf-8")


def ok_result(raw: str) -> dict:
    envelope = json.loads(raw)
    assert envelope["ok"] is True, f"expected ok envelope, got {envelope}"
    return envelope["result"]


def error_of(raw: str) -> dict:
    envelope = json.loads(raw)
    assert envelope["ok"] is False, "expected error envelope"
    assert "Traceback" not in envelope["error"]["message"]
    return envelope["error"]


# A 5 x 7 grid of 20-eighth squares, one 2-eighth band, two fabrics.
# gcd(5, 7) = 1, so infer_block_structure finds no block period.
def mini_model(cell_confidence=None) -> str:
    cells = [["c"] * 7 for _ in range(5)]
    cells[0][0] = "b"
    center = {"rows": 5, "cols": 7, "cell_size": 20, "cells": cells}
    if cell_confidence is not None:
        center["cell_confidence"] = cell_confidence
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
            "center": center,
            "borders": [{"fabric_id": "c", "width": 2}],
            "binding": {"fabric_id": "b"},
        }
    )


CORNERS = {
    "top_left": {"x": 10, "y": 12},
    "top_right": {"x": 410.5, "y": 14},
    "bottom_right": {"x": 404, "y": 512.25},
    "bottom_left": {"x": 8, "y": 506},
}

READ_REQUEST = {
    "token": "/staging/photo-1.png",
    "frame": {"kind": "field", "corners": CORNERS},
    "crop_offset": {"x": 120, "y": 64},
    "counts": {
        "blocks_across": 9,
        "blocks_down": 11,
        "squares_per_block_across": 5,
        "squares_per_block_down": 5,
    },
    "fabric_count": 2,
}


# ------------------------------------------------------------ read request


def test_read_request_takes_the_field_corners():
    request = ReadRequest.model_validate_json(json.dumps(READ_REQUEST))
    assert request.frame.kind == "field"
    assert request.frame.corners.top_right.x == 410.5
    assert request.crop_offset.x == 120
    assert request.counts.squares_per_block_down == 5
    assert request.fabric_count == 2


def test_read_request_takes_an_outer_edge_with_bands_in_part_squares():
    # Bands from the outside in, each one width in squares that need not be
    # whole: a 2.5-square border, then a 1-square border.
    frame = {
        "kind": "outer_edge",
        "corners": CORNERS,
        "bands": [{"width_squares": 2.5}, {"width_squares": 1}],
    }
    request = ReadRequest.model_validate_json(json.dumps({**READ_REQUEST, "frame": frame}))
    assert isinstance(request.frame, OuterEdgeFrame)
    assert [band.width_squares for band in request.frame.bands] == [2.5, 1.0]


def test_read_request_fabric_count_is_optional():
    request = {key: value for key, value in READ_REQUEST.items() if key != "fabric_count"}
    assert ReadRequest.model_validate_json(json.dumps(request)).fabric_count is None


def _with(path: str, value) -> dict:
    """READ_REQUEST with one dotted path set; the value None deletes it."""
    request = json.loads(json.dumps(READ_REQUEST))
    *parents, last = path.split(".")
    node = request
    for key in parents:
        node = node[key]
    if value is None:
        del node[last]
    else:
        node[last] = value
    return request


OUTER_EDGE_ZERO_BAND = {"kind": "outer_edge", "corners": CORNERS, "bands": [{"width_squares": 0}]}
FIELD_WITH_BANDS = {"kind": "field", "corners": CORNERS, "bands": []}


@pytest.mark.parametrize(
    ("request_dict", "named"),
    [
        (_with("fabric_count", 1), "fabric_count"),
        (_with("fabric_count", 13), "fabric_count"),
        (_with("fabric_count", 2.5), "fabric_count"),
        (_with("fabric_count", True), "fabric_count"),
        (_with("counts.blocks_across", 0), "blocks_across"),
        (_with("counts.squares_per_block_down", None), "squares_per_block_down"),
        (_with("frame.kind", "quad"), "frame"),
        (_with("frame.corners.bottom_left", None), "bottom_left"),
        (_with("frame.corners.top_left.x", "10"), "x"),
        (_with("crop_offset.y", -1), "crop_offset"),
        (_with("token", ""), "token"),
        (_with("strategy", "strip"), "strategy"),
        (_with("frame", OUTER_EDGE_ZERO_BAND), "width_squares"),
        (_with("frame", FIELD_WITH_BANDS), "bands"),
    ],
    ids=[
        "one-fabric",
        "thirteen-fabrics",
        "fractional-fabric-count",
        "boolean-fabric-count",
        "zero-blocks",
        "missing-count",
        "unknown-frame-kind",
        "missing-corner",
        "string-coordinate",
        "negative-crop-offset",
        "empty-token",
        "unknown-field",
        "zero-width-band",
        "bands-on-a-field-frame",
    ],
)
def test_read_confirmed_refuses_a_malformed_request_naming_the_field(request_dict, named):
    error = error_of(bridge.read_confirmed(json.dumps(request_dict)))
    assert error["kind"] == "validation"
    assert named in error["message"]


def test_read_confirmed_refuses_a_non_finite_coordinate():
    # JSON has no infinity, but 1e400 overflows a double to inf on parse.
    raw = json.dumps(READ_REQUEST).replace('"x": 10,', '"x": 1e400,', 1)
    error = error_of(bridge.read_confirmed(raw))
    assert error["kind"] == "validation"
    assert "top_left.x" in error["message"]


def test_read_confirmed_reports_malformed_json_as_schema():
    assert error_of(bridge.read_confirmed("{not json"))["kind"] == "schema"


@pytest.mark.skipif(
    sys.platform == "emscripten",
    reason="subprocess is unavailable under wasm; the native suite checks the import graph",
)
def test_frame_band_and_count_models_import_on_their_own():
    # D3a's annotation format reuses these models, so importing them must not
    # pull in the bridge, the vision stack or the PDF renderer.
    code = (
        "import sys\n"
        "from qrep.contract import BorderBand, Corners, Counts, FieldFrame, OuterEdgeFrame\n"
        "heavy = ('cv2', 'qrep.bridge', 'qrep.vision', 'qrep.render', 'reportlab')\n"
        "print([name for name in heavy if name in sys.modules])\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "[]"
    assert BorderBand(width_squares=0.5).width_squares == 0.5
    assert Counts(
        blocks_across=1, blocks_down=1, squares_per_block_across=3, squares_per_block_down=3
    ).blocks_across == 1


# ------------------------------------------------------- size_pattern (A10)


def _sized(quilt, request: SizeRequest) -> SizeResult:
    return SizeResult(
        outcome="sized",
        model=quilt,
        basis=SizeBasis(
            source=request.source,
            requested_width=request.width,
            requested_height=request.height,
            achieved_width=quilt.finished_width,
            achieved_height=quilt.finished_height,
        ),
    )


@pytest.mark.parametrize(
    ("request_dict", "named"),
    [
        ({"source": "typed"}, "width"),
        ({"source": "typed", "width": 600, "preset": "Twin"}, "preset"),
        ({"source": "preset"}, "preset"),
        ({"source": "preset", "preset": "Twin", "width": 600}, "width"),
        ({"source": "default", "height": 720}, "height"),
        ({"source": "typed", "width": 0}, "width"),
        ({"source": "typed", "width": 600.5}, "width"),
        ({"source": "measured"}, "source"),
    ],
    ids=[
        "typed-without-a-size",
        "typed-with-a-preset",
        "preset-without-a-name",
        "preset-with-a-width",
        "default-with-a-height",
        "zero-width",
        "fractional-eighths",
        "unknown-source",
    ],
)
def test_size_pattern_refuses_a_malformed_request_before_loading_its_delegate(
    model_json, monkeypatch, request_dict, named
):
    monkeypatch.setitem(sys.modules, "qrep.model.sizing", None)
    error = error_of(bridge.size_pattern(model_json, json.dumps(request_dict)))
    assert error["kind"] == "validation"
    assert named in error["message"]


def test_size_pattern_is_not_implemented_without_its_module(model_json, monkeypatch):
    # None in sys.modules fails the import as if A10's module were absent.
    monkeypatch.setitem(sys.modules, "qrep.model.sizing", None)
    error = error_of(bridge.size_pattern(model_json, json.dumps({"source": "default"})))
    assert error["kind"] == "not_implemented"
    assert "size_pattern" in error["message"]


def test_size_pattern_is_not_implemented_without_its_function(model_json, monkeypatch):
    monkeypatch.setitem(sys.modules, "qrep.model.sizing", types.ModuleType("qrep.model.sizing"))
    error = error_of(bridge.size_pattern(model_json, json.dumps({"source": "default"})))
    assert error["kind"] == "not_implemented"


def test_size_pattern_passes_the_delegate_result_through(model_json, monkeypatch):
    seen = []

    def size_pattern(quilt, request):
        seen.append((quilt, request))
        return _sized(quilt, request)

    fake = types.ModuleType("qrep.model.sizing")
    fake.size_pattern = size_pattern
    monkeypatch.setitem(sys.modules, "qrep.model.sizing", fake)
    result = ok_result(
        bridge.size_pattern(model_json, json.dumps({"source": "typed", "width": 600}))
    )
    assert result["outcome"] == "sized"
    # The fixture's finished size, 600 x 720 eighths (test_bridge's validate
    # test hand computes it).
    assert result["basis"] == {
        "source": "typed",
        "requested_width": 600,
        "requested_height": None,
        "achieved_width": 600,
        "achieved_height": 720,
    }
    assert result["model"]["center"]["rows"] == 55
    (quilt, request), = seen
    assert quilt.center.cols == 45
    assert isinstance(request, SizeRequest)
    assert request.width == 600


def test_size_pattern_reports_a_wrong_delegate_result_as_internal(model_json, monkeypatch):
    fake = types.ModuleType("qrep.model.sizing")
    fake.size_pattern = lambda quilt, request: {"outcome": "sized"}
    monkeypatch.setitem(sys.modules, "qrep.model.sizing", fake)
    error = error_of(bridge.size_pattern(model_json, json.dumps({"source": "default"})))
    assert error["kind"] == "internal"


def test_a_failing_import_inside_the_delegate_is_internal(model_json, monkeypatch):
    # Only the delegate's own module may be absent; a dependency it fails to
    # import is an engine bug, not a missing implementation.
    def import_module(name):
        raise ModuleNotFoundError("No module named 'missing_dependency'", name="missing_dependency")

    monkeypatch.setattr(bridge, "import_module", import_module)
    error = error_of(bridge.size_pattern(model_json, json.dumps({"source": "default"})))
    assert error["kind"] == "internal"


# ----------------------------------------------------- export_pattern (A4)


def test_export_pattern_takes_no_strategy(model_json):
    error = error_of(bridge.export_pattern(model_json, "strip"))
    assert error["kind"] == "validation"
    assert "export_pattern" in error["message"]


def test_export_pattern_is_not_implemented_without_its_module(model_json, monkeypatch):
    monkeypatch.setitem(sys.modules, "qrep.export.pattern", None)
    error = error_of(bridge.export_pattern(model_json))
    assert error["kind"] == "not_implemented"
    assert "build_pattern" in error["message"]


def test_export_pattern_reports_a_wrong_delegate_result_as_internal(model_json, monkeypatch):
    fake = types.ModuleType("qrep.export.pattern")
    fake.build_pattern = lambda quilt: PatternResult(
        outcome="refused", reason=Reason(code="test", message="test")
    ).model_dump()
    monkeypatch.setitem(sys.modules, "qrep.export.pattern", fake)
    assert error_of(bridge.export_pattern(model_json))["kind"] == "internal"


def test_export_pattern_returns_the_pdf_and_its_summary(model_json):
    quilt = loads(model_json)
    result = ok_result(bridge.export_pattern(model_json))
    assert result["outcome"] == "pattern_ready"
    assert result["reason"] is None
    pdf = base64.b64decode(result["pdf_b64"])
    assert pdf.startswith(b"%PDF-")
    summary = result["summary"]
    # Fixture: 45 cols x 12 eighths + 2 x 30-eighth band = 600 eighths (75in)
    # wide, 55 rows x 12 + 60 = 720 eighths (90in) tall.
    assert (summary["finished_width"], summary["finished_height"]) == (600, 720)
    # The model records no size basis before A9, so the summary names none.
    assert summary["size_basis"] is None
    assert summary["method"]
    assert summary["method_reason"]
    # One letter per palette fabric, in palette order.
    assert [f["letter"] for f in summary["fabrics"]] == ["A", "B"]
    assert [f["name"] for f in summary["fabrics"]] == [f.name for f in quilt.palette.fabrics]
    assert summary["backing"]["name"] == BACKING_NAME
    assert summary["wide_back"] is None
    # Batting: finished size plus 4in per side, 64 eighths per axis:
    # 600 + 64 = 664 by 720 + 64 = 784 (83in x 98in).
    assert summary["batting"] == {"width": 664, "height": 784}
    # Both width assumptions come from the fixture's settings: wof 336 (42in).
    assert (summary["strip_width"], summary["backing_width"]) == (336, 336)
    # Authored data carries confidence 1.0, so no square is uncertain.
    assert summary["uncertain_squares"] == 0
    # PS-40: the screen's fabric names are the PDF's.
    text = "".join(page.extract_text() for page in pypdf.PdfReader(io.BytesIO(pdf)).pages)
    for fabric in summary["fabrics"]:
        assert fabric["name"] in text


def test_export_pattern_is_reproducible(model_json):
    # Byte-identical PDFs for identical inputs, like export_pdf, so the native
    # and wasm builds can be compared.
    first = ok_result(bridge.export_pattern(model_json))["pdf_b64"]
    assert ok_result(bridge.export_pattern(model_json))["pdf_b64"] == first


def test_export_pattern_counts_squares_below_0_9_confidence_as_uncertain():
    # 5 x 7 confidence grid, all 1.0 except three squares: 0.89 and 0.5 are
    # below the 0.9 mark the web uses (web/src/state/project.tsx:63); 0.9
    # itself is not. Uncertain: 2.
    grid = [[1.0] * 7 for _ in range(5)]
    grid[0][1], grid[2][3], grid[4][6] = 0.89, 0.5, 0.9
    summary = ok_result(bridge.export_pattern(mini_model(cell_confidence=grid)))["summary"]
    assert summary["uncertain_squares"] == 2


def test_interim_pattern_picks_strip_or_historical(model_json):
    # Interim only (E1b): A4d switches build_pattern to the new document, and
    # this test goes with the interim. The engine picks strip when
    # infer_block_structure finds blocks and historical otherwise, and the
    # summary's lines are that method's purchase lines.
    for raw, method in [(model_json, "strip"), (mini_model(), "historical")]:
        quilt = loads(raw)
        summary = ok_result(bridge.export_pattern(raw))["summary"]
        assert summary["method"] == method
        report = compute_purchase_lines(quilt, get_strategy(method)(quilt))
        quarters = {
            (line.purpose, line.fabric_id): line.quarter_yards / 4 for line in report.lines
        }
        for fabric in summary["fabrics"]:
            assert fabric["yards"] == quarters.get(("top", fabric["fabric_id"]), 0)
        assert [(b["fabric_id"], b["yards"]) for b in summary["binding"]] == [
            (fabric_id, yards) for (purpose, fabric_id), yards in quarters.items()
            if purpose == "binding"
        ]
        assert summary["backing"]["yards"] == quarters[("backing", None)]
