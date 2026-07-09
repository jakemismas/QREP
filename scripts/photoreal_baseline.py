"""S0 photoreal baseline report (sprint 3, issue #66).

Runs the CURRENT pipeline on every committed photoreal fixture plus the
L0-L3 seed-42 renders and prints per-fixture numbers: detected-quad IoU vs
the sidecar ground truth, recovered vs true dims, cell accuracy, palette
fidelity, stage confidences, and repeat period. Red baselines are recorded,
not asserted; the slices that fix them write the red tests.

Also computes two PROTOTYPE measurements that exist only to give the
T1/T2/T3 verdict-threshold proposal measured evidence (S4 writes the real
implementations test-first):
- periodicity: zero-lag-normalized autocorrelation peak (the wasm-gate dft
  op) on the ground-truth-cropped grayscale, so the score's separability is
  measured independent of today's broken detection;
- coherence: interior-vs-boundary edge-energy ratio on the ground-truth
  grid, after a pitch-scaled blur (sigma = pitch/8) that kills print
  speckle but keeps piecing seams.

Never imported by CI tests. Usage:
  .venv/Scripts/python scripts/photoreal_baseline.py
"""

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from qrep.vision.compare import _lab_of_hex  # noqa: E402
from qrep.vision.metrics import cell_accuracy, palette_fidelity_hex, quad_iou  # noqa: E402

PHOTOREAL = REPO_ROOT / "tests" / "fixtures" / "photoreal"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = _load_module("photoreal_generator", PHOTOREAL / "generator.py")
OPS = _load_module("wasm_gate_ops", REPO_ROOT / "tests" / "fixtures" / "wasm_gate" / "ops.py")


def truth_crop(image: np.ndarray, quad: list) -> np.ndarray:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    x0, x1 = max(0, int(min(xs))), min(image.shape[1], int(max(xs)))
    y0, y1 = max(0, int(min(ys))), min(image.shape[0], int(max(ys)))
    return image[y0:y1, x0:x1]


def periodicity_prototype(image: np.ndarray, quad: list) -> float:
    """Autocorrelation peak of the HIGH-PASSED grayscale (per the S4 spec).

    Removing only the mean leaves the smooth envelope dominating: a flat
    vignetted panel scores ~0.99 at every lag. Subtracting a wide Gaussian
    (sigma = 5 percent of the crop) kills the envelope so the score
    measures actual lattice repetition."""
    crop = truth_crop(image, quad)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
    sigma = max(2.0, 0.05 * min(gray.shape))
    highpass = gray - cv2.GaussianBlur(gray, (0, 0), sigma)
    bgr = cv2.cvtColor(
        np.clip(highpass + 128.0, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR
    )
    result = OPS.dft_autocorr_op(bgr)
    return max(result["val_x"], result["val_y"])


def coherence_prototype(image: np.ndarray, side: dict) -> float | None:
    grid = side.get("grid")
    if not grid:
        return None
    crop = truth_crop(image, side["quad"])
    h, w = crop.shape[:2]
    span_x = grid["cols"] + 2 * grid["border_pitches"]
    span_y = grid["rows"] + 2 * grid["border_pitches"]
    pitch_x, pitch_y = w / span_x, h / span_y
    sigma = max(0.8, min(pitch_x, pitch_y) / 8.0)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).astype(np.float32)
    blurred = cv2.GaussianBlur(gray, (0, 0), sigma)
    energy = np.abs(cv2.Sobel(blurred, cv2.CV_32F, 1, 0)) + np.abs(
        cv2.Sobel(blurred, cv2.CV_32F, 0, 1)
    )
    xs = np.arange(w, dtype=np.float64)
    ys = np.arange(h, dtype=np.float64)
    # distance to the nearest grid line, in pitch units; the lattice is
    # PHASE-OFFSET by the border width (2.5 pitches on the irish chain, so
    # lines sit at half-pitch offsets from the crop edge)
    off = grid["border_pitches"]
    dx = np.abs((xs / pitch_x - off) - np.rint(xs / pitch_x - off))
    dy = np.abs((ys / pitch_y - off) - np.rint(ys / pitch_y - off))
    near_x = dx < 0.12
    near_y = dy < 0.12
    boundary = near_x[None, :] | near_y[:, None]
    boundary_mean = float(energy[boundary].mean()) if boundary.any() else 0.0
    interior_mean = float(energy[~boundary].mean()) if (~boundary).any() else 0.0
    if boundary_mean <= 0:
        return None
    return interior_mean / boundary_mean


def palette_mapping(truth_hex: list[str], recovered_hex: list[str]) -> dict[int, int]:
    truth_labs = [_lab_of_hex(c) for c in truth_hex]
    mapping: dict[int, int] = {}
    used: set[int] = set()
    for i, rec in enumerate(recovered_hex):
        lab = _lab_of_hex(rec)
        candidates = [
            (float(np.linalg.norm(lab - t)), j) for j, t in enumerate(truth_labs) if j not in used
        ]
        if not candidates:
            break
        _d, best = min(candidates)
        mapping[i] = best
        used.add(best)
    return mapping


def truth_cells(side: dict):
    if side.get("cells") is not None:
        return side["cells"]
    if side.get("cells_ref") == "double_irish_chain":
        from qrep.model import load

        quilt = load(REPO_ROOT / "tests" / "fixtures" / "double_irish_chain.json")
        ids = [f.id for f in quilt.palette.fabrics]
        return [[ids.index(fid) for fid in row] for row in quilt.center.cells]
    return None


def baseline_row(name: str, cap: int) -> str:
    from qrep.vision import reverse

    png = PHOTOREAL / f"{name}_{cap}.png"
    side = json.loads((PHOTOREAL / f"{name}_{cap}.json").read_text(encoding="utf-8"))
    image = cv2.imread(str(png))
    period = periodicity_prototype(image, side["quad"])
    coherence = coherence_prototype(image, side)
    proto = (
        f"proto[period={period:.3f}"
        + (f" coherence={coherence:.3f}]" if coherence is not None else " coherence=n/a]")
    )
    try:
        result = reverse(png)
    except Exception as error:  # noqa: BLE001 - raising IS the red baseline
        return f"{name}_{cap}: RAISES {type(error).__name__}: {error} | {proto}"
    diag = result.diagnostics
    iou = quad_iou(
        [tuple(p) for p in diag["detected_corners"]], [tuple(p) for p in side["quad"]]
    )
    rows, cols = diag["interior_dims"]
    grid = side.get("grid")
    dims_txt = f"dims {rows}x{cols}"
    if grid:
        ok = "OK" if (rows, cols) == (grid["rows"], grid["cols"]) else "RED"
        dims_txt += f" vs {grid['rows']}x{grid['cols']} {ok}"
    accuracy_txt = ""
    cells = truth_cells(side)
    if cells is not None and side.get("character") == "squares":
        recovered_hex = [f.color for f in result.quilt.palette.fabrics]
        mapping = palette_mapping(side["palette_hex"], recovered_hex)
        ids = [f.id for f in result.quilt.palette.fabrics]
        rec_cells = [[ids.index(v) for v in row] for row in result.quilt.center.cells]
        acc, compared = cell_accuracy(cells, rec_cells, mapping=mapping)
        accuracy_txt = f" acc={acc:.3f}/{compared}"
    fidelity = palette_fidelity_hex(
        side["palette_hex"], [f.color for f in result.quilt.palette.fabrics]
    )
    conf = result.quilt.provenance.stage_confidence
    conf_txt = " ".join(f"{k[:4]}={v:.2f}" for k, v in conf.items())
    return (
        f"{name}_{cap}: IoU={iou:.3f} {dims_txt}{accuracy_txt} "
        f"palfid={fidelity:.1f} rep={diag['repeat_period']} k={diag['palette_k']} | "
        f"{conf_txt} | {proto}"
    )


def render_row(level: int) -> str:
    from qrep.model import load
    from qrep.render import save_render
    from qrep.vision import compare_models, reverse

    truth = load(REPO_ROOT / "tests" / "fixtures" / "double_irish_chain.json")
    with tempfile.TemporaryDirectory() as tmp:
        png, sidecar = save_render(truth, Path(tmp) / f"l{level}.png", level=level, seed=42)
        corners = json.loads(Path(sidecar).read_text(encoding="utf-8"))["corners"]
        image = cv2.imread(str(png))
        period = periodicity_prototype(image, corners)
        result = reverse(png)
        report = compare_models(truth, result.quilt)
    diag = result.diagnostics
    iou = quad_iou([tuple(p) for p in diag["detected_corners"]], [tuple(p) for p in corners])
    conf = result.quilt.provenance.stage_confidence
    conf_txt = " ".join(f"{k[:4]}={v:.2f}" for k, v in conf.items())
    return (
        f"render_l{level}_seed42: IoU={iou:.3f} dims "
        f"{report.recovered_dims[0]}x{report.recovered_dims[1]} "
        f"acc={report.cell_accuracy:.3f} rep={diag['repeat_period']} | {conf_txt} | "
        f"proto[period={period:.3f}]"
    )


def main() -> int:
    print("== L0-L3 seed-42 renders (current pipeline) ==")
    for level in (0, 1, 2, 3):
        try:
            print(render_row(level))
        except Exception as error:  # noqa: BLE001
            print(f"render_l{level}_seed42: RAISES {type(error).__name__}: {error}")
    print("\n== photoreal fixtures (current pipeline) ==")
    for name in GEN.FIXTURES:
        for cap in GEN.CAPS:
            print(baseline_row(name, cap))
    return 0


if __name__ == "__main__":
    sys.exit(main())
