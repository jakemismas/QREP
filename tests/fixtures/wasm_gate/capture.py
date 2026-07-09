"""Native reference capture for the wasm gate (sprint 3 S0, issue #66).

Runs the shared ops natively and commits the results as the reference the
parity test compares against in EVERY runtime: native CI re-derives them
(near-exact, same library), the Pyodide job re-derives them under wasm
cv2 4.11 (the actual gate). Captured once via
`python tests/fixtures/wasm_gate/capture.py write`; frozen at S0 landing.
"""

import importlib.util
import json
import platform
import sys
from pathlib import Path

GATE_DIR = Path(__file__).resolve().parent
REPO_ROOT = GATE_DIR.parents[2]


def _ops():
    spec = importlib.util.spec_from_file_location("wasm_gate_ops", GATE_DIR / "ops.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reference_path() -> Path:
    return GATE_DIR / "reference.json"


def mask_path(name: str, cap: int) -> Path:
    return GATE_DIR / f"{name}_{cap}_fg.png"


def write_all() -> None:
    import cv2
    import numpy as np

    ops = _ops()
    reference: dict = {
        "capture_environment": {
            "platform": platform.system(),
            "python": platform.python_version(),
            "cv2": cv2.__version__,
            "numpy": np.__version__,
        },
        "grabcut": {},
        "dft": {},
    }
    for name, cap in ops.GRABCUT_CASES:
        fg = ops.grabcut_op(ops.load_fixture_bgr(name, cap))
        cv2.imwrite(str(mask_path(name, cap)), fg)
        reference["grabcut"][f"{name}_{cap}"] = {
            "mask_file": mask_path(name, cap).name,
            "fg_fraction": float((fg > 0).mean()),
        }
        print(f"grabcut {name}_{cap}: fg_fraction={float((fg > 0).mean()):.4f}")
    for name, cap in ops.DFT_CASES:
        reference["dft"][f"{name}_{cap}"] = ops.dft_autocorr_op(ops.load_fixture_bgr(name, cap))
        r = reference["dft"][f"{name}_{cap}"]
        print(f"dft {name}_{cap}: peak_x={r['peak_x']} peak_y={r['peak_y']}")
    reference_path().write_text(
        json.dumps(reference, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print("wrote reference.json")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "write":
        write_all()
    else:
        print("usage: python capture.py write   (captures the native reference once)")
