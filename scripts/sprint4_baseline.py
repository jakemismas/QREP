"""S0 sprint-4 evidence baseline (issue #92).

Measures the four block-lattice-corroboration metrics on every committed
photoreal fixture at both caps, so T4 (block-lattice SNR floor), T5 (mean
cell confidence floor), and the frozen sigma ladder can be proposed from
measured populations rather than the research spike's numbers:

- block_lattice_snr: the frozen ladder-autocorr op (Lab channel sweep +
  scale-swept detrend), min over axes, at the argmax (channel, sigma);
- 1D pitch + prominence: today's estimate_grid on the same crop (the leg the
  corroboration rescues when it reads below T1);
- integer-ratio lock: block period / 1D pitch within INTEGER_RATIO_EPSILON of
  an integer and block period >= 1D pitch (exit-a gate);
- mean cell confidence: assign_cells on the estimate_grid cell grid (the
  exit-a T5 quality floor);
- block-lattice coherence: coherence_with_sublattice on the SNR-derived block
  boundaries (the exit-b > T3 gate).

Runs on the ground-truth-quad crop of each fixture (the quilt region S1's
detector sees on rect.image). Never imported by CI tests. Usage:
  .venv/Scripts/python scripts/sprint4_baseline.py
"""

import importlib.util
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from qrep.vision.cells import assign_cells  # noqa: E402
from qrep.vision.grid import estimate_grid  # noqa: E402
from qrep.vision.palette import extract_palette  # noqa: E402
from qrep.vision.repeats import coherence_with_sublattice  # noqa: E402
from qrep.vision.verdict import INTEGER_RATIO_EPSILON  # noqa: E402

PHOTOREAL = REPO_ROOT / "tests" / "fixtures" / "photoreal"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = _load("photoreal_generator", PHOTOREAL / "generator.py")
OPS = _load("wasm_gate_ops", REPO_ROOT / "tests" / "fixtures" / "wasm_gate" / "ops.py")

# fixtures grouped by the role each plays in the T4/T5 proposal
PASSING = [
    "render_on_white",
    "render_on_wood",
    "render_perspective_jpeg",
    "drunkards_path",
    "hst_star",
    "busy_print_squares",
    "low_contrast_hst",
    "seam_shadows",
    "fabric_print",
]
DEGRADED = [
    "degraded_render_on_white",
    "degraded_drunkards_path",
    "degraded_hst_star",
    "degraded_busy_print",
]
FIELD_CLASS = ["antique_wash_chain", "quarter_circle_fine"]
NEGATIVE = ["two_color_garbage", "solid_fabric"]


def truth_crop(image: np.ndarray, quad: list) -> np.ndarray:
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    x0, x1 = max(0, int(min(xs))), min(image.shape[1], int(max(xs)))
    y0, y1 = max(0, int(min(ys))), min(image.shape[0], int(max(ys)))
    return image[y0:y1, x0:x1]


def _block_boundaries(extent: int, period: int) -> list[float]:
    if period < 5:
        return []
    edges = [float(v) for v in np.arange(0.0, float(extent), float(period))]
    return edges + [float(extent)]


def _integer_lock(period: int, pitch: float) -> tuple[float, bool]:
    """Exit-a per-axis lock: block period / 1D pitch is within the frozen
    epsilon of an integer >= 1 (block period at least the cell pitch)."""
    if period <= 0 or pitch <= 0:
        return 0.0, False
    ratio = period / pitch
    k = round(ratio)
    return ratio, k >= 1 and abs(ratio - k) <= INTEGER_RATIO_EPSILON


def measure(name: str, cap: int) -> dict:
    png = PHOTOREAL / f"{name}_{cap}.png"
    side = json.loads((PHOTOREAL / f"{name}_{cap}.json").read_text(encoding="utf-8"))
    image = cv2.imread(str(png))
    crop = truth_crop(image, side["quad"])

    r = OPS.lab_ladder_autocorr_op(crop)
    snr, px, py = r["snr"], r["period_x"], r["period_y"]

    pitch_x = pitch_y = 0.0
    prominence = 0.0
    mean_cell_conf = None
    try:
        grid = estimate_grid(crop)
        pitch_x, pitch_y = grid.x.pitch, grid.y.pitch
        prominence = grid.confidence
        palette = extract_palette(crop, None)
        cells = assign_cells(crop, grid.x.boundaries, grid.y.boundaries, palette.centers_lab)
        mean_cell_conf = cells.confidence
    except ValueError:
        prominence = -1.0  # estimate_grid refused (no edges / too short)

    ratio_x, lock_x = _integer_lock(px, pitch_x)
    ratio_y, lock_y = _integer_lock(py, pitch_y)

    xb = _block_boundaries(crop.shape[1], px)
    yb = _block_boundaries(crop.shape[0], py)
    block_coh = coherence_with_sublattice(crop, xb, yb) if xb and yb else 0.0

    return {
        "snr": snr,
        "period": (px, py),
        "channel": r["channel"],
        "sigma": r["sigma"],
        "pitch": (pitch_x, pitch_y),
        "prominence": prominence,
        "lock": lock_x and lock_y,
        "ratio": (ratio_x, ratio_y),
        "mean_cell_conf": mean_cell_conf,
        "block_coherence": block_coh,
        "character": side.get("character"),
    }


def _fmt(m: dict) -> str:
    mcc = f"{m['mean_cell_conf']:.3f}" if m["mean_cell_conf"] is not None else " n/a "
    prom = "refused" if m["prominence"] < 0 else f"{m['prominence']:.3f}"
    lock = "LOCK" if m["lock"] else "----"
    return (
        f"snr={m['snr']:5.2f} p=({m['period'][0]:>3},{m['period'][1]:>3}) "
        f"ch={m['channel']} sig={m['sigma']:<4} | 1Dpitch=({m['pitch'][0]:5.1f},{m['pitch'][1]:5.1f}) "
        f"prom={prom:>7} {lock} r=({m['ratio'][0]:.2f},{m['ratio'][1]:.2f}) | "
        f"meanCellConf={mcc} blockCoh={m['block_coherence']:.3f}"
    )


def _section(title: str, names: list[str]) -> list[tuple[str, dict]]:
    print(f"\n== {title} ==")
    rows = []
    for name in names:
        for cap in GEN.CAPS:
            m = measure(name, cap)
            rows.append((f"{name}_{cap}", m))
            print(f"  {name}_{cap:<4}: {_fmt(m)}")
    return rows


def main() -> int:
    print("sprint 4 S0 evidence baseline (crop = ground-truth quad)")
    print(f"ladder sigmas={OPS.LADDER_SIGMAS} harmonics={OPS.SNR_HARMONICS}")
    passing = _section("passing fixtures (block SNR is INERT here; 1D read passes)", PASSING)
    _section("degraded tier", DEGRADED)
    field = _section("field-class composites (exit-a chain, exit-b quarter-circle)", FIELD_CLASS)
    negative = _section("negative controls", NEGATIVE)

    def snrs(rows):
        return [m["snr"] for _n, m in rows]

    print("\n== separation summary ==")
    chain = [m for n, m in field if n.startswith("antique_wash_chain")]
    qc = [m for n, m in field if n.startswith("quarter_circle_fine")]
    garbage = [m for n, m in negative if n.startswith("two_color_garbage")]
    solid = [m for n, m in negative if n.startswith("solid_fabric")]
    print(f"  antique_wash_chain SNR: {[round(m['snr'], 2) for m in chain]}")
    print(f"  quarter_circle_fine SNR: {[round(m['snr'], 2) for m in qc]}")
    print(f"  two_color_garbage SNR: {[round(m['snr'], 2) for m in garbage]}")
    print(f"  solid_fabric SNR: {[round(m['snr'], 2) for m in solid]}")
    print(f"  passing-fixture SNR range: {min(snrs(passing)):.2f}..{max(snrs(passing)):.2f}")
    print(
        f"  chain mean cell conf: {[round(m['mean_cell_conf'], 3) for m in chain if m['mean_cell_conf'] is not None]}"
        f"  garbage mean cell conf: {[round(m['mean_cell_conf'], 3) for m in garbage if m['mean_cell_conf'] is not None]}"
    )
    print(
        f"  quarter-circle block coherence: {[round(m['block_coherence'], 3) for m in qc]}"
        f"  (exit-b needs > T3 = 1.05)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
