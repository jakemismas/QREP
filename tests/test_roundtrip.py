"""Round-trip harness: render with fixed seeds at test time, reverse with the
image path ALONE, compare per the design-doc accuracy definitions.

THRESHOLD LITERALS ARE CONTRACTUAL: copied verbatim from issue #10 and never
edited. L0: exact dims, 100 percent accuracy, identity path. L1: exact dims,
>= 98 percent. L2: spacing within 2 percent both axes, >= 90 percent,
non-identity found by the pipeline itself. Borders within 5 percent of 3.75
inches per side at L0/L1. Test images are generated into
tests/fixtures/_generated/ (gitignored) and never committed or hand-edited.
"""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qrep.cli import app
from qrep.model import STAGES, load, save
from qrep.render import save_render
from qrep.vision import compare_models, render_comparison, reverse

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"
GENERATED_DIR = Path(__file__).parent / "fixtures" / "_generated"

runner = CliRunner()


@pytest.fixture(scope="module")
def truth():
    return load(FIXTURE_PATH)


def _roundtrip(truth, level: int):
    GENERATED_DIR.mkdir(exist_ok=True)
    png, sidecar = save_render(truth, GENERATED_DIR / f"roundtrip_l{level}.png", level=level, seed=42)
    # the pipeline under test gets the image path alone; the sidecar is
    # harness-only ground truth
    result = reverse(png)
    report = compare_models(truth, result.quilt)
    return result, report, sidecar


@pytest.fixture(scope="module")
def l0(truth):
    return _roundtrip(truth, 0)


@pytest.fixture(scope="module")
def l1(truth):
    return _roundtrip(truth, 1)


@pytest.fixture(scope="module")
def l2(truth):
    return _roundtrip(truth, 2)


def test_l0_exact_dims_and_perfect_accuracy(l0):
    _result, report, _ = l0
    # exact interior grid dims after border exclusion: 45x55 cells
    assert report.dims_match
    assert report.recovered_dims == (55, 45)
    # 100 percent cell accuracy (verbatim threshold)
    assert report.cell_accuracy == 1.0
    assert report.compared_cells == 2475


def test_l0_identity_homography_path(l0):
    result, _report, _ = l0
    assert result.diagnostics["identity"] is True
    assert result.quilt.provenance.stage_confidence["rectify"] == 1.0


def test_l1_exact_dims_and_accuracy(l1):
    _result, report, _ = l1
    assert report.dims_match
    assert report.recovered_dims == (55, 45)
    # >= 98 percent (verbatim threshold)
    assert report.cell_accuracy >= 0.98


def test_l2_spacing_accuracy_and_nonidentity(l2):
    result, report, _ = l2
    # the pipeline found a non-identity homography by itself (no corners fed)
    assert result.diagnostics["identity"] is False
    # grid spacing within 2 percent on both axes: true pitch in the rectified
    # image is its extent over 50 horizontal / 60 vertical cell pitches
    # (45 + 2 x 2.5 border pitches; 55 + 5)
    rect_w, rect_h = result.diagnostics["rectified_size"]
    pitch_x, pitch_y = result.diagnostics["pitch_px"]
    assert abs(pitch_x - rect_w / 50) / (rect_w / 50) <= 0.02
    assert abs(pitch_y - rect_h / 60) / (rect_h / 60) <= 0.02
    # >= 90 percent cell accuracy (verbatim threshold)
    assert report.cell_accuracy >= 0.90


def test_l2_diagnostic_with_ground_truth_corners(l2, truth):
    """Escape-hatch diagnostic: reports its numbers regardless of pass/fail."""
    _result, _report, sidecar_path = l2
    sidecar = json.loads(Path(sidecar_path).read_text(encoding="utf-8"))
    corners = [(x, y) for x, y in sidecar["corners"]]
    result = reverse(GENERATED_DIR / "roundtrip_l2.png", corners=corners)
    report = compare_models(truth, result.quilt)
    lines = [
        f"L2 with supplied ground-truth corners: dims {report.recovered_dims}, "
        f"accuracy {report.cell_accuracy:.4f}",
        render_comparison(report),
    ]
    (GENERATED_DIR / "l2_corner_diagnostic.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(lines[0])
    # no pass/fail threshold by contract: only that the numbers exist
    assert 0.0 <= report.cell_accuracy <= 1.0


@pytest.mark.parametrize("fixture_name", ["l0", "l1"])
def test_fabric_count_recovered(fixture_name, request):
    result, _report, _ = request.getfixturevalue(fixture_name)
    assert len(result.quilt.palette.fabrics) == 2


@pytest.mark.parametrize("fixture_name", ["l0", "l1"])
def test_repeat_period_exact(fixture_name, request):
    result, _report, _ = request.getfixturevalue(fixture_name)
    # block size 5 with a two-block alternation = 10x10 cell pitch period
    assert result.diagnostics["repeat_period"] == [10, 10]


@pytest.mark.parametrize("fixture_name", ["l0", "l1"])
def test_border_width_within_five_percent(fixture_name, request):
    result, _report, _ = request.getfixturevalue(fixture_name)
    # true border is 3.75 inches = 37.5 px at the render scale of 10 px/inch
    for side, width_px in result.diagnostics["border_widths_px"].items():
        assert abs(width_px - 37.5) / 37.5 <= 0.05, (side, width_px)


def test_every_stage_populated_and_l2_strictly_lower(l0, l2):
    result0, _r0, _ = l0
    result2, _r2, _ = l2
    conf0 = result0.quilt.provenance.stage_confidence
    conf2 = result2.quilt.provenance.stage_confidence
    assert set(conf0) == set(STAGES) == set(conf2)
    assert all(0.0 < v <= 1.0 for v in conf0.values())
    assert all(0.0 < v <= 1.0 for v in conf2.values())
    assert min(conf2.values()) < min(conf0.values())


def test_compare_cli_reconciles_with_harness(l0, truth, tmp_path):
    result, report, _ = l0
    truth_path = tmp_path / "truth.json"
    recovered_path = tmp_path / "recovered.json"
    save(truth, truth_path)
    save(result.quilt, recovered_path)
    cli = runner.invoke(app, ["compare", str(truth_path), str(recovered_path)])
    assert cli.exit_code == 0
    assert f"cell accuracy: {report.cell_accuracy:.4f}" in cli.output
    assert "MATCH" in cli.output
    assert f"recovered {report.recovered_dims[0]}x{report.recovered_dims[1]}" in cli.output


def test_reverse_cli_writes_recovered_model(tmp_path, truth):
    png, _ = save_render(truth, GENERATED_DIR / "cli_reverse_l0.png", level=0, seed=42)
    out = tmp_path / "recovered.json"
    cli = runner.invoke(app, ["reverse", str(png), "-o", str(out)])
    assert cli.exit_code == 0, cli.output
    recovered = load(out)
    assert recovered.provenance.source == "cv"
    assert recovered.center.rows == 55 and recovered.center.cols == 45
    assert "confidence rectify" in cli.output
