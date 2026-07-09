"""Engine-side seam for the web UI (S1, issue #41).

Pure functions taking and returning JSON strings. Every function returns a
typed envelope serialized as JSON:

    {"ok": true, "result": ...}
    {"ok": false, "error": {"kind": "...", "message": "..."}}

Error kinds map the exception taxonomy the CLI already handles:
schema (malformed JSON or unknown schema_version), validation (pydantic),
value (bad arguments, unknown strategy, unreadable image), not_implemented
(stubbed strategies), internal (anything else; generic message, no
stringified tracebacks reach the UI).

Byte payloads (PDF, PNG) ride inside the envelope base64-encoded so byte
producers still return typed envelopes; the UI's RPC layer decodes them to
transferables.

MEMFS staging contract (wasm): the UI writes uploaded image bytes to a
caller-owned path (e.g. /staging/photo.png via pyodide.FS.writeFile) and
passes that path to reverse(). The bridge only READS the staged path; the
caller owns its lifecycle (delete after use, or keep it for a corner-pin
re-run). Bridge-internal scratch files live under /tmp/qrep-bridge/<uuid>
and are removed before the call returns.

This module must never import typer or click (enforced by test_bridge).

Resize semantics (PARITY.md item 4; engine-authoritative reconciliation):
the cell-size and block-quantization math reuses qrep/viewer/sizing.py
unchanged - its hand-computed unit-test numbers hold exactly here. The new
layer on top: requested dimensions are rounded to the nearest 1/4" then
clamped to [20", 140"]; the cell clamps to [3/4", 4"]; locked resize scales
every border band by the achieved cell factor (round_div, floor 1/4", cap
14"); a preset resolves to the smaller of its by-width / by-height cells
(the mock's min-ratio rule); unlocked resize keeps cell and bands, moves
whole blocks per axis, preserves content anchored top-left, and extends by
tiling the grid's minimal row/column period (new squares get confidence 1.0
when a confidence grid exists).
"""

import base64
import json
import shutil
import tempfile
import uuid
from pathlib import Path

from pydantic import ValidationError

from qrep.construct import get_strategy
from qrep.construct.yardage import compute_purchase_lines
from qrep.construct.strategies import infer_block_structure
from qrep.export.cutlist import render_cutlist_csv, render_cutlist_md
from qrep.export.pdf import render_booklet
from qrep.export.svg import render_top_svg
from qrep.export.yardage_report import render_yardage_md
from qrep.model import QrepSchemaError
from qrep.model.io import loads
from qrep.model.schema import Quilt
from qrep.viewer.sizing import locked_resize, round_div, unlocked_resize

# qrep.vision AND qrep.render import cv2 at module load (the renderer for
# its L2 homography); the browser lazy-loads the vision wheel on first
# photo use, so reverse(), render(), and compare() import them lazily
# (enforced by test_bridge_import_does_not_load_cv2).

# PARITY item 4 clamps, integer eighths.
CELL_MIN = 6  # 3/4"
CELL_MAX = 32  # 4"
DIM_MIN = 160  # 20"
DIM_MAX = 1120  # 140"
BAND_MIN = 2  # 1/4"
BAND_MAX = 112  # 14"
QUARTER = 2  # 1/4" in eighths


def _ok(result) -> str:
    return json.dumps({"ok": True, "result": result})


def _error(kind: str, message: str) -> str:
    return json.dumps({"ok": False, "error": {"kind": kind, "message": message}})


def _envelope(fn):
    """Wraps a bridge body: exceptions become typed error envelopes."""

    def wrapper(*args, **kwargs) -> str:
        try:
            return _ok(fn(*args, **kwargs))
        except json.JSONDecodeError as e:
            return _error("schema", f"malformed JSON: {e.msg} (line {e.lineno})")
        except QrepSchemaError as e:
            return _error("schema", str(e))
        except ValidationError as e:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()
            )
            return _error("validation", f"model failed validation: {problems}")
        except NotImplementedError as e:
            return _error("not_implemented", str(e))
        except KeyError as e:
            return _error("value", str(e.args[0]) if e.args else "unknown key")
        except (ValueError, FileNotFoundError) as e:
            return _error("value", str(e))
        except Exception:  # noqa: BLE001 - the seam must never leak internals
            return _error("internal", "internal engine error; see the browser console log")

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    return wrapper


def _load(model_json: str) -> Quilt:
    if not isinstance(model_json, str):
        raise ValueError("model_json must be a JSON string")
    return loads(model_json)


def _summary(quilt: Quilt) -> dict:
    # Batting per PARITY item 9: finished dims + 4" per side = +64 eighths
    # per axis (the same margin convention as the backing formula).
    counts: dict[str, int] = {}
    for row in quilt.center.cells:
        for fabric_id in row:
            counts[fabric_id] = counts.get(fabric_id, 0) + 1
    return {
        "name": quilt.metadata.name,
        "rows": quilt.center.rows,
        "cols": quilt.center.cols,
        "fabric_count": len(quilt.palette.fabrics),
        "fabrics": [
            {
                "id": f.id,
                "name": f.name,
                "color": f.color,
                "cell_count": counts.get(f.id, 0),
            }
            for f in quilt.palette.fabrics
        ],
        "finished_width": quilt.finished_width,
        "finished_height": quilt.finished_height,
        "batting_width": quilt.finished_width + quilt.settings.backing_margin,
        "batting_height": quilt.finished_height + quilt.settings.backing_margin,
        "usable_width": quilt.settings.wof,
    }


@_envelope
def validate(model_json: str) -> dict:
    """Validate a model document and return its UI summary."""
    return _summary(_load(model_json))


@_envelope
def plan(model_json: str, strategy: str) -> dict:
    """Compute a construction plan plus yardage and the UI summary."""
    quilt = _load(model_json)
    result = get_strategy(strategy)(quilt)
    # The human-facing purchase table (per-fabric top lines, binding lines,
    # backing) - the same source the yardage export and PDF booklet use.
    yardage = compute_purchase_lines(quilt, result)
    return {
        "plan": result.model_dump(mode="json"),
        "yardage": yardage.model_dump(mode="json"),
        "summary": _summary(quilt),
    }


@_envelope
def export_cutlist_md(model_json: str, strategy: str) -> dict:
    quilt = _load(model_json)
    return {"text": render_cutlist_md(quilt, get_strategy(strategy)(quilt))}


@_envelope
def export_cutlist_csv(model_json: str, strategy: str) -> dict:
    quilt = _load(model_json)
    return {"text": render_cutlist_csv(quilt, get_strategy(strategy)(quilt))}


@_envelope
def export_yardage(model_json: str, strategy: str) -> dict:
    from qrep.construct.yardage import compute_purchase_lines

    quilt = _load(model_json)
    report = compute_purchase_lines(quilt, get_strategy(strategy)(quilt))
    return {"text": render_yardage_md(report)}


@_envelope
def export_svg(model_json: str) -> dict:
    return {"text": render_top_svg(_load(model_json))}


@_envelope
def export_pdf(model_json: str, strategy: str) -> dict:
    """Render the booklet reproducibly: byte-identical for identical inputs.

    reportlab embeds timestamps by default; invariant mode pins them. The
    flag is set only around this call so the sprint 1 exporter's own
    behavior is untouched elsewhere.
    """
    quilt = _load(model_json)
    result = get_strategy(strategy)(quilt)
    from reportlab import rl_config

    scratch = _scratch_dir()
    previous = rl_config.invariant
    try:
        rl_config.invariant = 1
        path = scratch / "booklet.pdf"
        render_booklet(quilt, result, path)
        pdf_bytes = path.read_bytes()
    finally:
        rl_config.invariant = previous
        shutil.rmtree(scratch, ignore_errors=True)
    return {"pdf_b64": base64.b64encode(pdf_bytes).decode("ascii")}


@_envelope
def render(model_json: str, level: int, seed: int, scale: int) -> dict:
    """Render the synthetic PNG; returns PNG bytes plus the sidecar dict."""
    from qrep.render import save_render

    if not 0 <= int(level) <= 3:
        raise ValueError(f"level must be 0..3, got {level}")
    quilt = _load(model_json)
    scratch = _scratch_dir()
    try:
        png_path, sidecar_path = save_render(
            quilt, scratch / "render.png", level=int(level), seed=int(seed), scale=int(scale)
        )
        png_bytes = Path(png_path).read_bytes()
        sidecar = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return {"png_b64": base64.b64encode(png_bytes).decode("ascii"), "sidecar": sidecar}


@_envelope
def reverse(image_path: str, options_json: str) -> dict:
    """Reverse a staged image path into a recovered model.

    The caller stages the bytes (MEMFS in wasm) and owns the file; the
    bridge only reads it. options: {"corners": [[x,y]*4]?, "fabrics": int?}.
    """
    options = json.loads(options_json) if options_json else {}
    path = Path(image_path)
    if not path.exists():
        raise ValueError(f"image file not found: {image_path}")
    corners = options.get("corners")
    if corners is not None:
        corners = [(float(x), float(y)) for x, y in corners]
    from qrep.vision import reverse as reverse_pipeline

    result = reverse_pipeline(path, corners=corners, fabrics=options.get("fabrics"))
    return {"model": result.quilt.model_dump(mode="json")}


@_envelope
def compare(truth_json: str, recovered_json: str) -> dict:
    from qrep.vision import compare_models

    report = compare_models(_load(truth_json), _load(recovered_json))
    return report.model_dump(mode="json")


def _scratch_dir() -> Path:
    root = Path(tempfile.gettempdir()) / "qrep-bridge" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _normalized_dim(value) -> int:
    """Requested dims round to the nearest 1/4in then clamp to [20in, 140in]."""
    rounded = round_div(int(value), QUARTER) * QUARTER
    return _clamp(rounded, DIM_MIN, DIM_MAX)


def _parse_targets(target_json: str) -> dict:
    target = json.loads(target_json)
    if not isinstance(target, dict):
        raise ValueError("resize target must be a JSON object")
    return target


def _achieved(quilt: Quilt) -> dict:
    return {
        "width": quilt.finished_width,
        "height": quilt.finished_height,
        "cell_size": quilt.center.cell_size,
        "rows": quilt.center.rows,
        "cols": quilt.center.cols,
        "borders": [b.width for b in quilt.borders],
    }


@_envelope
def resize_locked(model_json: str, target_json: str) -> dict:
    """Proportion lock ON: counts never change; cell scales, bands follow."""
    quilt = _load(model_json)
    target = _parse_targets(target_json)
    rows, cols = quilt.center.rows, quilt.center.cols
    old_cell = quilt.center.cell_size
    border_total = sum(b.width for b in quilt.borders)
    requested: dict = {}

    if "preset" in target:
        preset = target["preset"]
        width = _normalized_dim(preset["width"])
        height = _normalized_dim(preset["height"])
        requested = {"width": width, "height": height}
        by_width = locked_resize(rows, cols, old_cell, border_total, target_width=width)
        by_height = locked_resize(rows, cols, old_cell, border_total, target_height=height)
        new_cell = min(by_width.cell_size, by_height.cell_size)
    elif "width" in target:
        width = _normalized_dim(target["width"])
        requested = {"width": width}
        new_cell = locked_resize(rows, cols, old_cell, border_total, target_width=width).cell_size
    elif "height" in target:
        height = _normalized_dim(target["height"])
        requested = {"height": height}
        new_cell = locked_resize(
            rows, cols, old_cell, border_total, target_height=height
        ).cell_size
    elif "cell" in target:
        requested = {"cell": int(target["cell"])}
        new_cell = int(target["cell"])
    else:
        raise ValueError("resize target needs width, height, cell, or preset")

    new_cell = _clamp(new_cell, CELL_MIN, CELL_MAX)
    resized = quilt.model_copy(deep=True)
    resized.center.cell_size = new_cell
    for band in resized.borders:
        band.width = _clamp(round_div(band.width * new_cell, old_cell), BAND_MIN, BAND_MAX)
    return {
        "model": resized.model_dump(mode="json"),
        "requested": requested,
        "achieved": _achieved(resized),
    }


def _min_period(sequences: list) -> int:
    """Smallest p >= 1 with seq[i] == seq[i-p] for every i >= p (whole length
    when aperiodic)."""
    n = len(sequences)
    for p in range(1, n):
        if all(sequences[i] == sequences[i - p] for i in range(p, n)):
            return p
    return n


def _regrid(cells: list[list[str]], new_rows: int, new_cols: int) -> list[list[str]]:
    """Top-left preservation: kept cells unchanged; extension tiles the
    minimal row/column period so block patterns continue correctly."""
    rows, cols = len(cells), len(cells[0])
    row_period = _min_period([tuple(row) for row in cells])
    col_period = _min_period([tuple(row[c] for row in cells) for c in range(cols)])

    def source(r: int, c: int) -> str:
        sr = r if r < rows else r % row_period
        sc = c if c < cols else c % col_period
        return cells[sr][sc]

    return [[source(r, c) for c in range(new_cols)] for r in range(new_rows)]


@_envelope
def resize_unlocked(model_json: str, target_json: str) -> dict:
    """Proportion lock OFF: cell and bands fixed; whole blocks per axis."""
    quilt = _load(model_json)
    target = _parse_targets(target_json)
    if "width" not in target and "height" not in target:
        raise ValueError("resize target needs width or height")
    structure = infer_block_structure(quilt.center.cells)
    # A single-type structure is the degenerate all-identical tiling of a
    # uniform grid, not a real block pattern: PARITY item 15 pins that a
    # blank grid resizes one square at a time.
    block = structure.size if structure is not None and len(structure.types) > 1 else 1
    border_total = sum(b.width for b in quilt.borders)
    requested: dict = {}
    width = height = None
    if "width" in target:
        width = _normalized_dim(target["width"])
        requested["width"] = width
    if "height" in target:
        height = _normalized_dim(target["height"])
        requested["height"] = height

    sized = unlocked_resize(
        quilt.center.rows,
        quilt.center.cols,
        quilt.center.cell_size,
        border_total,
        block,
        target_width=width,
        target_height=height,
    )
    resized = quilt.model_copy(deep=True)
    resized.center.rows = sized.rows
    resized.center.cols = sized.cols
    resized.center.cells = _regrid(quilt.center.cells, sized.rows, sized.cols)
    if quilt.center.cell_confidence is not None:
        old_conf = quilt.center.cell_confidence
        old_rows, old_cols = quilt.center.rows, quilt.center.cols
        resized.center.cell_confidence = [
            [
                old_conf[r][c] if r < old_rows and c < old_cols else 1.0
                for c in range(sized.cols)
            ]
            for r in range(sized.rows)
        ]
    return {
        "model": resized.model_dump(mode="json"),
        "requested": requested,
        "achieved": _achieved(resized),
    }
