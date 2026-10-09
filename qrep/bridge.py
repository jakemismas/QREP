"""Engine-side seam for the web UI (S1, issue #41).

Pure functions taking and returning JSON strings. Every function returns a
typed envelope serialized as JSON:

    {"ok": true, "result": ...}
    {"ok": false, "error": {"kind": "...", "message": "..."}}

Error kinds (engine-16) tell your input errors from engine bugs:
schema (malformed JSON or unknown schema_version); validation (a model that
fails pydantic validation, a call with the wrong number of arguments, or a
bridge argument with the wrong type or structure, with the field named);
value (an input the engine cannot use: an unknown strategy or preset, a
level, seed, scale or fabric count out of range, a missing or unreadable
image, each named); not_implemented (stubbed
strategies, and a v2 call whose implementation has not landed); internal
(anything else, including a KeyError, TypeError or AttributeError raised
inside the engine, which signals an engine bug; generic message, no
stringified tracebacks reach the UI, which get printed to stderr instead).

The v2 entry points (read_confirmed, size_pattern, export_pattern) take
and return the models in qrep/contract.py, and every v2 result names its
outcome.

contract_version() reports CONTRACT_VERSION (qrep/contract.py), which the
web worker checks at boot before it serves any call.

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
import inspect
import json
import math
import shutil
import tempfile
import traceback
import uuid
from importlib import import_module
from pathlib import Path

from pydantic import BaseModel, ValidationError

from qrep.construct import get_strategy
from qrep.construct.yardage import compute_purchase_lines
from qrep.construct.strategies import STRATEGIES, infer_block_structure
from qrep.contract import (
    CONTRACT_VERSION,
    FABRICS_MAX,
    FABRICS_MIN,
    PatternResult,
    ReadRequest,
    SizeRequest,
    SizeResult,
)
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

# Largest render() scale, in pixels per inch (engine-16). The web renders at
# 10 (its demo and round-trip panel) and so does the renderer by default, so
# 20 doubles the headroom. The bound caps the multiplier, not the image: the
# image also grows with the quilt, which render() does not bound. For scale,
# a quilt at the 140" resize ceiling (DIM_MAX) renders at 2800 px plus a
# 224 px margin per side (renderer MARGIN_FRACTION 0.08 x 2800): 3248 x 3248
# px, about 10.5 megapixels. Levels 1 to 3 build float64 working arrays of
# that order, 3248 x 3248 x 3 x 8 bytes (about 253 MB) for a full RGB copy,
# and every one grows with the square of the scale.
RENDER_SCALE_MAX = 20

# Smallest render() scale x square size, in pixels per inch x eighths: 12 is
# 1.5 px per square. The renderer fills each square from px(start) to
# px(end) - 1 with half-up rounding, so a square under 1 px can get no pixels
# and Pillow refuses its rectangle. Levels 1 to 3 re-derive the scale from
# the rounded image width, which shrinks a square by at most half a pixel
# (the width rounds by 0.5 px or less over a quilt at least one square
# wide), so 1.5 px keeps every square at 1 px or more on every level.
RENDER_SQUARE_SPAN_MIN = 12

# reverse()'s forced fabric count follows the read's, FABRICS_MIN to
# FABRICS_MAX (qrep/contract.py; SPEC.md section 12.1).


class _ArgumentError(Exception):
    """A bridge argument has the wrong type or structure (kind validation)."""

    def __init__(self, field: str, problem: str):
        super().__init__(f"{field}: {problem}")


def _ok(result) -> str:
    return json.dumps({"ok": True, "result": result})


def _error(kind: str, message: str) -> str:
    return json.dumps({"ok": False, "error": {"kind": kind, "message": message}})


def _envelope(fn):
    """Wraps a bridge body: exceptions become typed error envelopes."""
    signature = inspect.signature(fn)

    def wrapper(*args, **kwargs) -> str:
        try:
            signature.bind(*args, **kwargs)
        except TypeError as e:
            # A call with the wrong number of arguments is the request's
            # shape, not an engine bug; binding first keeps it out of the
            # catch-all below.
            return _error("validation", f"argument failed validation: {fn.__name__}: {e}")
        try:
            return _ok(fn(*args, **kwargs))
        except _ArgumentError as e:
            return _error("validation", f"argument failed validation: {e}")
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
        except (ValueError, FileNotFoundError) as e:
            return _error("value", str(e))
        except Exception:  # noqa: BLE001 - the seam must never leak internals
            # A KeyError lands here too: known input errors raise ValueError
            # at entry, so a KeyError from the engine is a bug, not your input.
            # The traceback goes to stderr, never into the envelope: Pyodide
            # sends stderr to the browser console (console.warn), where the
            # message below points.
            traceback.print_exc()
            return _error("internal", "internal engine error; see the browser console log")

    wrapper.__name__ = fn.__name__
    wrapper.__doc__ = fn.__doc__
    # Marks the RPC surface; test_bridge keeps worker.ts's allowlist equal to it.
    wrapper.is_envelope = True
    return wrapper


def _text(field: str, value) -> str:
    if not isinstance(value, str):
        raise _ArgumentError(field, f"must be a string, got {type(value).__name__}")
    return value


def _json_object(field: str, value) -> dict:
    data = json.loads(_text(field, value))
    if not isinstance(data, dict):
        raise _ArgumentError(field, f"must be a JSON object, got {type(data).__name__}")
    return data


def _whole(field: str, value) -> int:
    # Exact whole numbers only: int() would truncate 20.9 to 20 past a range
    # check and read true or "600" as numbers. The web sends integer eighths,
    # which Pyodide hands over as int.
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise _ArgumentError(field, f"must be a whole number, got {type(value).__name__}")


def _load(model_json: str, field: str = "model_json") -> Quilt:
    return loads(_text(field, model_json))


def _strategy(name):
    """Resolves a strategy name; an unknown name is your input error (kind value)."""
    _text("strategy", name)
    if name not in STRATEGIES:
        raise ValueError(f"unknown strategy {name!r}; available: {', '.join(STRATEGIES)}")
    return get_strategy(name)


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
def contract_version() -> dict:
    """The bridge contract this engine speaks; the web worker refuses to
    boot when it differs from the app's (web/src/engine/contract.ts)."""
    return {"contract_version": CONTRACT_VERSION}


@_envelope
def validate(model_json: str) -> dict:
    """Validate a model document and return its UI summary."""
    return _summary(_load(model_json))


@_envelope
def plan(model_json: str, strategy: str) -> dict:
    """Compute a construction plan plus yardage and the UI summary."""
    quilt = _load(model_json)
    result = _strategy(strategy)(quilt)
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
    return {"text": render_cutlist_md(quilt, _strategy(strategy)(quilt))}


@_envelope
def export_cutlist_csv(model_json: str, strategy: str) -> dict:
    quilt = _load(model_json)
    return {"text": render_cutlist_csv(quilt, _strategy(strategy)(quilt))}


@_envelope
def export_yardage(model_json: str, strategy: str) -> dict:
    from qrep.construct.yardage import compute_purchase_lines

    quilt = _load(model_json)
    report = compute_purchase_lines(quilt, _strategy(strategy)(quilt))
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
    result = _strategy(strategy)(quilt)
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
    """Render the synthetic PNG; returns PNG bytes plus the sidecar dict.

    scale is pixels per inch, from 1 to RENDER_SCALE_MAX, and at least
    RENDER_SQUARE_SPAN_MIN / cell size (1.5 px per square), rounded up.
    """
    from qrep.render import save_render

    level = _whole("level", level)
    seed = _whole("seed", seed)
    scale = _whole("scale", scale)
    if not 0 <= level <= 3:
        raise ValueError(f"level must be 0..3, got {level}")
    if seed < 0:
        raise ValueError(f"seed must be 0 or more, got {seed}")
    if not 1 <= scale <= RENDER_SCALE_MAX:
        raise ValueError(f"scale must be 1..{RENDER_SCALE_MAX} pixels per inch, got {scale}")
    quilt = _load(model_json)
    cell = quilt.center.cell_size
    if scale * cell < RENDER_SQUARE_SPAN_MIN:
        floor = -(-RENDER_SQUARE_SPAN_MIN // cell)
        raise ValueError(
            f"scale must be at least {floor} pixels per inch for {cell}-eighth squares "
            f"(1.5 pixels per square), got {scale}"
        )
    scratch = _scratch_dir()
    try:
        png_path, sidecar_path = save_render(
            quilt, scratch / "render.png", level=level, seed=seed, scale=scale
        )
        png_bytes = Path(png_path).read_bytes()
        sidecar = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return {"png_b64": base64.b64encode(png_bytes).decode("ascii"), "sidecar": sidecar}


@_envelope
def detect_quad(image_path: str) -> dict:
    """Detection tiers only, no full reverse (S2, issue #68).

    Runs the S1 tiered detector on a staged image and returns the quad in
    NORMALIZED [0,1] image coordinates plus tier, confidence, and the
    predicted_size field ({width_px, height_px, aspect, preset}). preset is
    the one standard size whose aspect matches the quad's
    (qrep.model.finished_size.suggest_preset), or null when no preset or
    more than one matches, or the quad has no area.
    An unreadable all-background image answers with the honest tier-3 full
    frame at low confidence, never an error: the crop screen makes that
    visible and fixable.
    """
    path = Path(_text("image_path", image_path))
    if not path.exists():
        raise ValueError(f"image file not found: {image_path}")
    import cv2

    from qrep.vision.rectify import TIER3_CONFIDENCE, rectify

    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"could not read image: {image_path}")
    height, width = image.shape[:2]
    try:
        detected = rectify(image)
        corners = [(float(x), float(y)) for x, y in detected.corners]
        tier = detected.tier
        confidence = float(detected.confidence)
    except ValueError:
        corners = [
            (0.0, 0.0),
            (float(width), 0.0),
            (float(width), float(height)),
            (0.0, float(height)),
        ]
        tier = 3
        confidence = TIER3_CONFIDENCE

    def _dist(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    # quad extents from mean opposite edge lengths (the rectify warp-target
    # convention), so the aspect survives a perspective quad
    quad_w = (_dist(corners[0], corners[1]) + _dist(corners[3], corners[2])) / 2
    quad_h = (_dist(corners[0], corners[3]) + _dist(corners[1], corners[2])) / 2
    return {
        "quad": [[x / width, y / height] for x, y in corners],
        "tier": tier,
        "confidence": confidence,
        "predicted_size": {
            "width_px": quad_w,
            "height_px": quad_h,
            "aspect": (quad_w / quad_h) if quad_h > 0 else None,
            "preset": _preset_suggestion(quad_w, quad_h),
        },
    }


def _preset_suggestion(quad_w: float, quad_h: float):
    if quad_w <= 0 or quad_h <= 0:
        return None
    from qrep.model.finished_size import suggest_preset

    return suggest_preset(quad_w / quad_h)


@_envelope
def reverse(image_path: str, options_json: str) -> dict:
    """Reverse a staged image path into a recovered model.

    The caller stages the bytes (MEMFS in wasm) and owns the file; the
    bridge only reads it. options, every key optional: {"corners":
    [[x, y]] * 4 in image pixels, "fabrics": int, "finished_width": int,
    "finished_height": int}, the finished sizes in eighths.
    """
    _text("image_path", image_path)
    no_options = options_json is None or options_json == ""
    options = {} if no_options else _json_object("options_json", options_json)
    corners = options.get("corners")
    if corners is not None:
        corners = _corners(corners)
    fabrics = options.get("fabrics")
    if fabrics is not None:
        fabrics = _whole("options_json.fabrics", fabrics)
        if not FABRICS_MIN <= fabrics <= FABRICS_MAX:
            raise ValueError(f"fabrics must be {FABRICS_MIN}..{FABRICS_MAX}, got {fabrics}")

    def _size_option(key: str) -> int | None:
        value = options.get(key)
        return _whole(f"options_json.{key}", value) if value is not None else None

    finished_width = _size_option("finished_width")
    finished_height = _size_option("finished_height")
    path = Path(image_path)
    if not path.exists():
        raise ValueError(f"image file not found: {image_path}")
    from qrep.vision import reverse as reverse_pipeline

    result = reverse_pipeline(
        path,
        corners=corners,
        fabrics=fabrics,
        finished_width=finished_width,
        finished_height=finished_height,
    )
    diagnostics = _jsonable(result.diagnostics)
    # S4 (issue #70): the envelope grows additively from {"model"} to
    # {"model", "verdict", "diagnostics"} per the verdict contract
    envelope = {
        "model": result.quilt.model_dump(mode="json"),
        "verdict": diagnostics.get("verdict"),
        "diagnostics": diagnostics,
    }
    if diagnostics.get("size_achieved") is not None:
        envelope["requested"] = diagnostics.get("size_requested")
        envelope["achieved"] = diagnostics.get("size_achieved")
    return envelope


def _corners(value) -> list[tuple[float, float]]:
    # Exactly four points: rectify's corner ordering silently keeps four
    # extremes of any longer list, so a malformed request would read a
    # different quad than the one you sent.
    field = "options_json.corners"
    shape = "must be four [x, y] points"
    if not isinstance(value, list) or len(value) != 4:
        raise _ArgumentError(field, shape)
    points = []
    for point in value:
        if not isinstance(point, list) or len(point) != 2:
            raise _ArgumentError(field, shape)
        points.append((_coordinate(field, point[0]), _coordinate(field, point[1])))
    return points


def _coordinate(field: str, value) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            number = float(value)
        except OverflowError:
            number = math.inf
        if math.isfinite(number):
            return number
    raise _ArgumentError(field, "each coordinate must be a finite number")


def _jsonable(value):
    """Diagnostics carry numpy scalars and tuples; JSON needs plain types."""
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, (int, float, str)):
        return value
    if hasattr(value, "item"):
        return value.item()
    return str(value)


@_envelope
def presets() -> dict:
    """The shipped standard-size table, verbatim (S6, issue #72): the
    single source of truth for size chips - no second table anywhere."""
    from qrep.viewer.sizing import PRESETS

    return {"presets": [{"name": n, "width": w, "height": h} for n, w, h in PRESETS]}


@_envelope
def apply_finished_size(model_json: str, width, height) -> dict:
    """Re-derive cell and borders on an existing model for a user-entered
    finished size, without re-running vision (S6, issue #72). width/height
    are integer eighths; either may be null."""
    from qrep.model.finished_size import apply_finished_size as apply_size

    quilt = _load(model_json)
    w = _whole("width", width) if width is not None else None
    h = _whole("height", height) if height is not None else None
    if w is None and h is None:
        raise ValueError("apply_finished_size needs a width or a height")
    updated, requested, achieved = apply_size(quilt, w, h)
    updated.metadata.notes = (
        "Recovered by the QREP CV pipeline. Finished size provided by "
        "you; squares and borders were fitted to it."
    )
    return {
        "model": updated.model_dump(mode="json"),
        "requested": requested,
        "achieved": achieved,
        "size_source": "user",
    }


@_envelope
def compare(truth_json: str, recovered_json: str) -> dict:
    from qrep.vision import compare_models

    report = compare_models(_load(truth_json, "truth_json"), _load(recovered_json, "recovered_json"))
    return report.model_dump(mode="json")


def _scratch_dir() -> Path:
    root = Path(tempfile.gettempdir()) / "qrep-bridge" / uuid.uuid4().hex
    root.mkdir(parents=True, exist_ok=True)
    return root


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _normalized_dim(value, field: str) -> int:
    """Requested dims round to the nearest 1/4in then clamp to [20in, 140in]."""
    rounded = round_div(_whole(field, value), QUARTER) * QUARTER
    return _clamp(rounded, DIM_MIN, DIM_MAX)


def _parse_targets(target_json: str) -> dict:
    return _json_object("target_json", target_json)


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
        if not isinstance(preset, dict):
            raise _ArgumentError(
                "target_json.preset", "must be an object with a width and a height in eighths"
            )
        # A preset object without both sizes was kind value before the
        # KeyError mapping went; it stays value, now naming the preset.
        if not {"width", "height"} <= preset.keys():
            raise ValueError(
                f"unknown preset {json.dumps(preset)}; a preset target gives a width "
                "and a height in eighths"
            )
        width = _normalized_dim(preset["width"], "target_json.preset.width")
        height = _normalized_dim(preset["height"], "target_json.preset.height")
        requested = {"width": width, "height": height}
        by_width = locked_resize(rows, cols, old_cell, border_total, target_width=width)
        by_height = locked_resize(rows, cols, old_cell, border_total, target_height=height)
        new_cell = min(by_width.cell_size, by_height.cell_size)
    elif "width" in target:
        width = _normalized_dim(target["width"], "target_json.width")
        requested = {"width": width}
        new_cell = locked_resize(rows, cols, old_cell, border_total, target_width=width).cell_size
    elif "height" in target:
        height = _normalized_dim(target["height"], "target_json.height")
        requested = {"height": height}
        new_cell = locked_resize(
            rows, cols, old_cell, border_total, target_height=height
        ).cell_size
    elif "cell" in target:
        new_cell = _whole("target_json.cell", target["cell"])
        requested = {"cell": new_cell}
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
        width = _normalized_dim(target["width"], "target_json.width")
        requested["width"] = width
    if "height" in target:
        height = _normalized_dim(target["height"], "target_json.height")
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


# ---------------------------------------------------------------- bridge v2
#
# The v2 entry points (E1b) take and return the models in qrep/contract.py;
# every result names its outcome. size_pattern and export_pattern load their
# implementations lazily from fixed module paths, so the tickets that write
# them (A10; A4a to A4d) never touch this contract file.


def _request(model: type[BaseModel], field: str, value) -> BaseModel:
    """Validates a JSON request: malformed JSON is kind schema, a bad shape
    kind validation naming the field."""
    raw = _text(field, value)
    json.loads(raw)
    return model.model_validate_json(raw)


def _delegate(module: str, name: str):
    """The engine function that implements a v2 call, or not_implemented
    while its ticket has not landed. Only the delegate's own module may be
    missing: a dependency that fails to import inside it is an engine bug."""
    try:
        found = getattr(import_module(module), name, None)
    except ModuleNotFoundError as e:
        if e.name != module:
            raise
        found = None
    if found is None:
        raise NotImplementedError(f"{name} is not implemented yet ({module})")
    return found


def _result(model: type[BaseModel], produce):
    """Runs a delegate and returns its result as JSON data. The request was
    validated before, so a delegate that fails validation or returns another
    type is an engine bug (kind internal), not your input."""
    try:
        result = produce()
    except ValidationError as e:
        raise RuntimeError("the engine produced an invalid result") from e
    if not isinstance(result, model):
        raise TypeError(f"expected {model.__name__}, got {type(result).__name__}")
    return result.model_dump(mode="json")


@_envelope
def read_confirmed(request_json: str) -> dict:
    """The confirmed read (SPEC.md sections 4, 5 and 12.1): reads the staged
    photo the request's token names, with your frame, counts and optional
    fabric count, and returns a ReadResult.

    A stub until B2b switches it to the real read in qrep/vision/read/: it
    validates the request, then returns kind not_implemented.
    """
    _request(ReadRequest, "request_json", request_json)
    raise NotImplementedError("read_confirmed is not implemented yet")


@_envelope
def size_pattern(model_json: str, request_json: str) -> dict:
    """Sizes the pattern for the size you set (SPEC.md section 6.3): returns a
    SizeResult with the sized model and its size basis. Implemented by
    qrep.model.sizing:size_pattern(quilt, request)."""
    quilt = _load(model_json)
    request = _request(SizeRequest, "request_json", request_json)
    size = _delegate("qrep.model.sizing", "size_pattern")
    return _result(SizeResult, lambda: size(quilt, request))


@_envelope
def export_pattern(model_json: str) -> dict:
    """The one pattern download: a PatternResult with the PDF (base64) and
    the summary Your pattern shows. The engine picks the method, so the call
    takes no strategy (SPEC.md section 12.1). Implemented by
    qrep.export.pattern:build_pattern(quilt)."""
    quilt = _load(model_json)
    build = _delegate("qrep.export.pattern", "build_pattern")
    return _result(PatternResult, lambda: build(quilt))
