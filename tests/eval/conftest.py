"""Puts scripts/eval on the import path for the eval tests (plan section 5.D).

The eval code lives outside the wheel the browser loads, so `from qrep_eval import
annotation` and `import corpus_fetch` resolve from here; tests/conftest.py stays untouched.
"""

import sys
from pathlib import Path

EVAL = Path(__file__).resolve().parents[2] / "scripts" / "eval"
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))
