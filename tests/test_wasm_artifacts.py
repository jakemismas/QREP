"""Structure checks for browser-produced artifacts (S0 web spike, issue #40).

The web e2e spike generates the PDF booklet inside Pyodide and saves the raw
bytes to web/test-results/spike/booklet.pdf. This module runs the SAME pypdf
structure checks as test_pdf.py against those browser-produced bytes,
native-side, per the S0 acceptance criterion.

Opt-in: set QREP_WASM_PDF to the booklet path. Without the env var the module
skips, keeping the native suite self-contained. With it set, a missing or
malformed file FAILS: the wasm bytes must pass the native structure checks.
"""

import csv
import os
import re
from pathlib import Path

import pypdf
import pytest

from qrep.construct.strategies import STRATEGIES
from qrep.export.cutlist import render_cutlist_csv
from qrep.export.pdf import SECTION_TITLES
from qrep.model import load

FIXTURE = Path(__file__).parent / "fixtures" / "double_irish_chain.json"

pytestmark = pytest.mark.skipif(
    "QREP_WASM_PDF" not in os.environ,
    reason="QREP_WASM_PDF not set; wasm artifact checks are opt-in (the web e2e run produces the file)",
)


def _normalize(text: str) -> str:
    # Mirrors test_pdf.py: pypdf mangles whitespace and can drop straight-quote
    # inch marks, so collapse whitespace runs and remove inch marks on both
    # sides of every containment check.
    return re.sub(r"\s+", " ", text.replace('"', "")).strip()


def test_wasm_booklet_passes_native_structure_checks():
    pdf_path = Path(os.environ["QREP_WASM_PDF"])
    assert pdf_path.exists(), f"wasm booklet missing: {pdf_path} (run the web e2e spike first)"
    assert pdf_path.stat().st_size > 0

    # Expected content derives from the fixture and the strip plan computed
    # natively; only the PDF bytes under test come from the browser.
    quilt = load(FIXTURE)
    plan = STRATEGIES["strip"](quilt)

    reader = pypdf.PdfReader(str(pdf_path))
    text = _normalize("\n".join((page.extract_text() or "") for page in reader.pages))

    for title in SECTION_TITLES:
        assert _normalize(title) in text
    for fabric in quilt.palette.fabrics:
        assert _normalize(fabric.name) in text

    cut_sizes = {
        row["cut_size"] for row in csv.DictReader(render_cutlist_csv(quilt, plan).splitlines())
    }
    assert cut_sizes, "cut list CSV yields at least one cut size"
    for size in cut_sizes:
        assert _normalize(size) in text
