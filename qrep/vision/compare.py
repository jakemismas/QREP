"""Model comparison: the round-trip harness measurement, exposed as a CLI.

Accuracy definitions per the design doc: recovered palette entries map to
truth fabrics by nearest Lab distance (greedy, bijective); cell accuracy is
correct cells over the center-field grid only; on a dimension mismatch the
accuracy is computed over the overlapping top-left region and the deviation
is reported alongside.
"""

import cv2
import numpy as np
from pydantic import BaseModel

from qrep.model.schema import STAGES, Quilt


class ComparisonReport(BaseModel):
    truth_dims: tuple[int, int]  # rows, cols
    recovered_dims: tuple[int, int]
    dims_match: bool
    cell_accuracy: float
    compared_cells: int
    palette_mapping: dict[str, str]  # recovered fabric id -> truth fabric id
    stage_confidence: dict[str, dict[str, float]]


def _lab_of_hex(color: str) -> np.ndarray:
    rgb = [int(color[i : i + 2], 16) for i in (1, 3, 5)]
    bgr = np.array([[rgb[::-1]]], dtype=np.uint8)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2Lab)[0, 0].astype(np.float64)


def map_palettes(truth: Quilt, recovered: Quilt) -> dict[str, str]:
    """Greedy nearest-Lab bijective mapping, recovered -> truth."""
    truth_labs = {f.id: _lab_of_hex(f.color) for f in truth.palette.fabrics}
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for fabric in recovered.palette.fabrics:
        lab = _lab_of_hex(fabric.color)
        candidates = [
            (float(np.linalg.norm(lab - t_lab)), t_id)
            for t_id, t_lab in truth_labs.items()
            if t_id not in used
        ]
        if not candidates:
            break
        _dist, best = min(candidates)
        mapping[fabric.id] = best
        used.add(best)
    return mapping


def compare_models(truth: Quilt, recovered: Quilt) -> ComparisonReport:
    mapping = map_palettes(truth, recovered)
    truth_cells = truth.center.cells
    mapped = [
        [mapping.get(fid, "?") for fid in row] for row in recovered.center.cells
    ]
    truth_dims = (truth.center.rows, truth.center.cols)
    recovered_dims = (recovered.center.rows, recovered.center.cols)
    rows = min(truth_dims[0], recovered_dims[0])
    cols = min(truth_dims[1], recovered_dims[1])
    correct = sum(
        1 for r in range(rows) for c in range(cols) if mapped[r][c] == truth_cells[r][c]
    )
    compared = rows * cols
    stage = {
        s: {
            "truth": truth.provenance.effective_stage_confidence()[s],
            "recovered": recovered.provenance.effective_stage_confidence()[s],
        }
        for s in STAGES
    }
    return ComparisonReport(
        truth_dims=truth_dims,
        recovered_dims=recovered_dims,
        dims_match=truth_dims == recovered_dims,
        cell_accuracy=correct / compared if compared else 0.0,
        compared_cells=compared,
        palette_mapping=mapping,
        stage_confidence=stage,
    )


def render_comparison(report: ComparisonReport) -> str:
    lines = [
        f"grid dims: truth {report.truth_dims[0]}x{report.truth_dims[1]} vs "
        f"recovered {report.recovered_dims[0]}x{report.recovered_dims[1]} "
        f"({'MATCH' if report.dims_match else 'MISMATCH'})",
        f"cell accuracy: {report.cell_accuracy:.4f} over {report.compared_cells} cells",
        "palette mapping: "
        + ", ".join(f"{k} -> {v}" for k, v in sorted(report.palette_mapping.items())),
        "stage confidence (truth | recovered):",
    ]
    for stage, pair in report.stage_confidence.items():
        lines.append(f"  {stage}: {pair['truth']:.4f} | {pair['recovered']:.4f}")
    return "\n".join(lines)
