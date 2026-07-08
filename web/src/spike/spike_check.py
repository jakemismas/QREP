"""S0 spike checks, executed inside Pyodide (issue #40).

phase_a exercises the engine's export surface on the benchmark fixture and
returns the produced bytes (base64) so the browser test can byte-compare the
CSV against the canonical golden and hand the PDF to the native pypdf checks.
The CSV goes through export_cutlist's file write path (not a string return)
so the bytes are produced exactly as the golden was.

phase_b runs reverse() on the L0 render AFTER the JS side has staged the PNG
bytes onto MEMFS via pyodide.FS.writeFile, proving the photo-bytes staging
shape S1 will formalize.
"""

import base64
import json
import sys
import time
from pathlib import Path


def _version_of(module):
    for attr in ("__version__", "VERSION", "Version", "version"):
        value = getattr(module, attr, None)
        if isinstance(value, str):
            return value
    return "unknown"


def collect_versions():
    import cv2
    import numpy
    import PIL
    import pydantic
    import reportlab
    import svgwrite

    import qrep

    return {
        "python": sys.version.split()[0],
        "numpy": _version_of(numpy),
        "cv2": _version_of(cv2),
        "PIL": _version_of(PIL),
        "pydantic": _version_of(pydantic),
        "reportlab": _version_of(reportlab),
        "svgwrite": _version_of(svgwrite),
        "qrep": _version_of(qrep),
    }


def phase_a(fixture_json: str) -> str:
    from qrep.construct import get_strategy
    from qrep.export import export_cutlist
    from qrep.export.pdf import render_booklet
    from qrep.model.io import loads
    from qrep.render import save_render

    timings = {}
    quilt = loads(fixture_json)

    t0 = time.perf_counter()
    plan = get_strategy("strip")(quilt)
    timings["planMs"] = (time.perf_counter() - t0) * 1000

    out_dir = Path("/tmp/exports")
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    written = export_cutlist(quilt, plan, out_dir)
    timings["cutlistMs"] = (time.perf_counter() - t0) * 1000
    csv_bytes = next(p for p in written if p.suffix == ".csv").read_bytes()

    t0 = time.perf_counter()
    render_booklet(quilt, plan, "/tmp/booklet.pdf")
    timings["pdfMs"] = (time.perf_counter() - t0) * 1000
    pdf_bytes = Path("/tmp/booklet.pdf").read_bytes()

    t0 = time.perf_counter()
    png_path, _sidecar = save_render(
        quilt, Path("/tmp/render_l0.png"), level=0, seed=42, scale=10
    )
    timings["renderMs"] = (time.perf_counter() - t0) * 1000
    png_bytes = Path(png_path).read_bytes()

    return json.dumps(
        {
            "versions": collect_versions(),
            "timings": timings,
            "csvB64": base64.b64encode(csv_bytes).decode(),
            "pdfB64": base64.b64encode(pdf_bytes).decode(),
            "pngB64": base64.b64encode(png_bytes).decode(),
        }
    )


def phase_b(fixture_json: str, staged_path: str) -> str:
    from qrep.model.io import loads
    from qrep.vision import compare_models, reverse

    t0 = time.perf_counter()
    result = reverse(staged_path)
    wall_ms = (time.perf_counter() - t0) * 1000

    recovered = result.quilt
    report = compare_models(loads(fixture_json), recovered)
    return json.dumps(
        {
            "rows": recovered.center.rows,
            "cols": recovered.center.cols,
            "wallMs": wall_ms,
            "cellAccuracy": report.cell_accuracy,
            "dimsMatch": report.dims_match,
            "stageConfidence": dict(recovered.provenance.stage_confidence),
        }
    )
