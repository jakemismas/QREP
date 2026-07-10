"""Local photo smoke (sprint 3 hands-off policy, issue #66).

Runs the full reverse pipeline on every image in the gitignored
local-photos/ folder and prints, per photo: the detected quad, recovered
grid dims, the verdict, and the six stage confidences. Sprint 4 S0 (issue
#92) adds a block-lattice evidence line per photo: block_lattice_snr,
the integer-ratio lock of the block period to the 1D pitch, mean cell
confidence, and block-lattice coherence - the corroboration inputs measured
on the pipeline's OWN rectified image (which for a full-frame screenshot is
the whole frame - exactly the crop-aware-contingency evidence). A raising
pipeline is REPORTED, not fatal: raw failures are the field evidence this
script exists to surface.

The folder holds rights-unclean shop photos; it is never committed and is
absent on CI. This script is never imported by CI tests.

Usage: .venv/Scripts/python scripts/local_photo_smoke.py
"""

import importlib.util
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PHOTO_DIR = REPO_ROOT / "local-photos"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _load_ops():
    path = REPO_ROOT / "tests" / "fixtures" / "wasm_gate" / "ops.py"
    spec = importlib.util.spec_from_file_location("wasm_gate_ops", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _block_evidence(image_bgr) -> str:
    """The four sprint-4 corroboration metrics on the rectified image."""
    import numpy as np

    from qrep.vision.cells import assign_cells
    from qrep.vision.grid import estimate_grid
    from qrep.vision.palette import extract_palette
    from qrep.vision.repeats import coherence_with_sublattice
    from qrep.vision.verdict import INTEGER_RATIO_EPSILON

    ops = _load_ops()
    r = ops.lab_ladder_autocorr_op(image_bgr)
    px, py = r["period_x"], r["period_y"]
    try:
        grid = estimate_grid(image_bgr)
        pitch = (grid.x.pitch, grid.y.pitch)
        prom = grid.confidence
        palette = extract_palette(image_bgr, None)
        cells = assign_cells(image_bgr, grid.x.boundaries, grid.y.boundaries, palette.centers_lab)
        mcc = f"{cells.confidence:.3f}"
    except ValueError:
        pitch = (0.0, 0.0)
        prom = -1.0
        mcc = "refused"

    def lock(period: int, pit: float) -> str:
        if period <= 0 or pit <= 0:
            return "----(no-pitch)"
        ratio = period / pit
        k = round(ratio)
        ok = k >= 1 and abs(ratio - k) <= INTEGER_RATIO_EPSILON
        return f"{'LOCK' if ok else '----'} r={ratio:.2f}"

    xb = [float(v) for v in np.arange(0.0, float(image_bgr.shape[1]), float(max(px, 5)))] + [
        float(image_bgr.shape[1])
    ]
    yb = [float(v) for v in np.arange(0.0, float(image_bgr.shape[0]), float(max(py, 5)))] + [
        float(image_bgr.shape[0])
    ]
    block_coh = coherence_with_sublattice(image_bgr, xb, yb) if px >= 5 and py >= 5 else 0.0
    prom_txt = "refused" if prom < 0 else f"{prom:.3f}"
    return (
        f"  block: snr={r['snr']:.2f} p=({px},{py}) ch={r['channel']} sig={r['sigma']} | "
        f"1Dpitch=({pitch[0]:.1f},{pitch[1]:.1f}) prom={prom_txt} | "
        f"lockX={lock(px, pitch[0])} lockY={lock(py, pitch[1])} | "
        f"meanCellConf={mcc} blockCoh={block_coh:.3f}"
    )


def describe(path: Path) -> None:
    import cv2

    from qrep.vision import reverse
    from qrep.vision.rectify import rectify

    print(f"\n=== {path.name} ===")
    try:
        result = reverse(path)
    except Exception as error:  # noqa: BLE001 - raw failures ARE the data here
        print(f"  PIPELINE RAISED: {type(error).__name__}: {error}")
        traceback.print_exc(limit=1)
        return
    diag = result.diagnostics
    quad = ", ".join(f"({x:.0f}, {y:.0f})" for x, y in diag["detected_corners"])
    rows, cols = diag["interior_dims"]
    tier = diag.get("detection_tier", "n/a (pre-S1)")
    print(f"  quad: {quad}  (identity={diag['identity']}, tier={tier})")
    print(f"  dims: {rows} rows x {cols} cols; pitch_px={diag['pitch_px']}")
    print(f"  repeat_period: {diag['repeat_period']}; palette_k={diag['palette_k']}")
    print(f"  grid_diagnosis: {diag.get('grid_diagnosis', 'n/a (pre-S3)')}")
    print(f"  verdict: {diag.get('verdict', 'n/a (pre-S4)')}")
    conf = result.quilt.provenance.stage_confidence
    print("  confidences: " + "  ".join(f"{k}={v:.3f}" for k, v in conf.items()))
    try:
        image = cv2.imread(str(path))
        rect = rectify(image, None)
        print(_block_evidence(rect.image))
    except Exception as error:  # noqa: BLE001 - hands-off, never fatal
        print(f"  block evidence unavailable: {type(error).__name__}: {error}")


def main() -> int:
    if not PHOTO_DIR.is_dir():
        print(f"local-photos/ absent at {PHOTO_DIR}: nothing to smoke (no-op).")
        return 0
    photos = sorted(p for p in PHOTO_DIR.iterdir() if p.suffix.lower() in EXTENSIONS)
    if not photos:
        print("local-photos/ is empty: nothing to smoke (no-op).")
        return 0
    print(f"smoking {len(photos)} local photo(s) through the full reverse")
    for photo in photos:
        describe(photo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
