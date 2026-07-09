"""Local photo smoke (sprint 3 hands-off policy, issue #66).

Runs the full reverse pipeline on every image in the gitignored
local-photos/ folder and prints, per photo: the detected quad, recovered
grid dims, the verdict (n/a until S4 lands it in diagnostics), and the six
stage confidences. A raising pipeline is REPORTED, not fatal: raw failures
are exactly the field evidence this script exists to surface.

The folder holds rights-unclean shop photos; it is never committed and is
absent on CI. This script is never imported by CI tests.

Usage: .venv/Scripts/python scripts/local_photo_smoke.py
"""

import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PHOTO_DIR = REPO_ROOT / "local-photos"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def describe(path: Path) -> None:
    from qrep.vision import reverse

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
    print(f"  quad: {quad}  (identity={diag['identity']})")
    print(f"  dims: {rows} rows x {cols} cols; pitch_px={diag['pitch_px']}")
    print(f"  repeat_period: {diag['repeat_period']}; palette_k={diag['palette_k']}")
    print(f"  verdict: {diag.get('verdict', 'n/a (pre-S4)')}")
    conf = result.quilt.provenance.stage_confidence
    print("  confidences: " + "  ".join(f"{k}={v:.3f}" for k, v in conf.items()))


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
