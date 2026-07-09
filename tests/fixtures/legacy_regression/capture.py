"""Legacy-regression pin capture (sprint 3 S0, issue #66).

Captures the CURRENT pipeline's detected corners and full recovered-model
JSON on the L0-L2 seed-42 renders. This is the byte-stability contract S1's
tier-0 legacy branch is held to: after the tiered-detector refactor, the
renderer-background path must reproduce these files exactly.

Captured once via `python tests/fixtures/legacy_regression/capture.py write`
and committed; frozen from the moment S0 lands. The capture environment is
recorded in each pin for diagnosis if a platform ever disagrees.

Renders are generated at test time (deterministic by the renderer contract);
only the pipeline OUTPUT is pinned here, never the render itself.
"""

import json
import platform
import sys
import tempfile
from pathlib import Path

PIN_DIR = Path(__file__).resolve().parent
REPO_ROOT = PIN_DIR.parents[2]
LEVELS = (0, 1, 2)


def build_pin(level: int) -> dict:
    import cv2
    import numpy as np

    from qrep.model import dumps, load
    from qrep.render import save_render
    from qrep.vision import reverse

    truth = load(REPO_ROOT / "tests" / "fixtures" / "double_irish_chain.json")
    with tempfile.TemporaryDirectory() as tmp:
        png, _sidecar = save_render(
            truth, Path(tmp) / f"legacy_l{level}.png", level=level, seed=42
        )
        result = reverse(png)
    return {
        "level": level,
        "seed": 42,
        "scale": 10,
        "capture_environment": {
            "platform": platform.system(),
            "python": platform.python_version(),
            "cv2": cv2.__version__,
            "numpy": np.__version__,
        },
        "corners": [[float(x), float(y)] for x, y in result.diagnostics["detected_corners"]],
        "model": json.loads(dumps(result.quilt)),
    }


def pin_path(level: int) -> Path:
    return PIN_DIR / f"l{level}_seed42.json"


def write_all() -> None:
    for level in LEVELS:
        pin = build_pin(level)
        pin_path(level).write_text(
            json.dumps(pin, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        print(f"pinned l{level}_seed42.json")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "write":
        sys.path.insert(0, str(REPO_ROOT))
        write_all()
    else:
        print("usage: python capture.py write   (captures the pin once)")
