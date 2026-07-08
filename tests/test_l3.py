"""S8 stretch: L3 runs to completion and records accuracy. NO threshold, by
contract: L3 is report-only and the honest number lives in
docs/stretch/NOTES.md and the recorded artifact."""

from pathlib import Path

from qrep.model import load
from qrep.render import save_render
from qrep.vision import compare_models, reverse

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"
GENERATED_DIR = Path(__file__).parent / "fixtures" / "_generated"


def test_l3_runs_to_completion_and_records_accuracy():
    truth = load(FIXTURE_PATH)
    GENERATED_DIR.mkdir(exist_ok=True)
    png, _ = save_render(truth, GENERATED_DIR / "l3_seed42.png", level=3, seed=42)
    result = reverse(png)
    report = compare_models(truth, result.quilt)
    # run-to-completion assertions only: a valid model with populated stages
    assert result.quilt.center.rows > 0 and result.quilt.center.cols > 0
    assert set(result.quilt.provenance.stage_confidence) == {
        "rectify",
        "palette",
        "grid",
        "cells",
        "repeat",
        "border",
    }
    (GENERATED_DIR / "l3_accuracy.txt").write_text(
        f"L3 seed 42: dims {report.recovered_dims}, accuracy {report.cell_accuracy:.4f}\n",
        encoding="utf-8",
    )
    assert 0.0 <= report.cell_accuracy <= 1.0
