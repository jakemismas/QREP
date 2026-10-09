"""CLI tests through typer's CliRunner: validate, plan, export."""

import json
import runpy
import sys
import warnings
from pathlib import Path

import pytest
from typer.testing import CliRunner

from qrep.cli import app

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"

runner = CliRunner()


def test_validate_ok_exits_zero():
    result = runner.invoke(app, ["validate", str(FIXTURE_PATH)])
    assert result.exit_code == 0
    assert "OK" in result.output
    assert "Double Irish Chain" in result.output


def test_validate_corrupted_json_exits_nonzero(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": "9", "metadata": {}}', encoding="utf-8")
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code != 0
    assert "unsupported schema_version" in result.output


def test_validate_truncated_json_exits_nonzero(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": "1", "metadata"', encoding="utf-8")
    result = runner.invoke(app, ["validate", str(bad)])
    assert result.exit_code != 0
    assert "not valid JSON" in result.output


def test_validate_missing_file_exits_nonzero(tmp_path):
    result = runner.invoke(app, ["validate", str(tmp_path / "nope.json")])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_plan_prints_metrics_and_writes_json(tmp_path):
    out = tmp_path / "plan.json"
    result = runner.invoke(
        app, ["plan", str(FIXTURE_PATH), "--strategy", "strip", "-o", str(out)]
    )
    assert result.exit_code == 0
    assert "pieces in top: 2479" in result.output
    assert "cut operations: 633" in result.output
    assert "strip sets: 25 physical (5 distinct)" in result.output
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["strategy"] == "strip"
    assert data["metrics"]["piece_count"] == 2479


def test_plan_unknown_strategy_exits_nonzero():
    result = runner.invoke(app, ["plan", str(FIXTURE_PATH), "--strategy", "quantum"])
    assert result.exit_code != 0
    assert "unknown strategy" in result.output


def test_plan_stub_strategy_reports_not_implemented():
    result = runner.invoke(app, ["plan", str(FIXTURE_PATH), "--strategy", "fpp"])
    assert result.exit_code != 0
    assert "not implemented in v1" in result.output


def test_export_writes_expected_files(tmp_path):
    out = tmp_path / "dist"
    result = runner.invoke(
        app, ["export", str(FIXTURE_PATH), "--strategy", "strip", "--out", str(out)]
    )
    assert result.exit_code == 0
    assert (out / "cutlist.md").exists()
    assert (out / "cutlist.csv").exists()
    assert (out / "yardage.md").exists()


def test_export_formats_subset(tmp_path):
    out = tmp_path / "dist"
    result = runner.invoke(
        app,
        [
            "export",
            str(FIXTURE_PATH),
            "--strategy",
            "historical",
            "--out",
            str(out),
            "--formats",
            "cutlist",
        ],
    )
    assert result.exit_code == 0
    assert (out / "cutlist.md").exists()
    assert not (out / "yardage.md").exists()


def test_plan_prints_purchase_lines_and_the_wide_back():
    result = runner.invoke(app, ["plan", str(FIXTURE_PATH), "--strategy", "strip"])
    assert result.exit_code == 0
    # binding at the stored 42 in: 9 strips x 20 e = 180 e; ceil(180 / 72) = 3 qy = 3/4 yd
    assert "yardage - Binding - Chain blue (b): 3/4 yd" in result.output
    # V-BACK-09: 1568 + 72 = 1640 e; ceil(1640 / 72) = 23 qy = 5 3/4 yd
    assert (
        'yardage - backing, 42" wide fabric: (2) panels 98" long, vertical seams: 5 3/4 yd'
        in result.output
    )
    # V-WIDE-08: 664 + 36 = 700 e; ceil(700 / 72) = 10 qy = 2 1/2 yd
    assert (
        'yardage - instead of the backing line, wide backing, 108" wide fabric: '
        'one piece 83" long: 2 1/2 yd' in result.output
    )


def test_module_entry_point_runs_the_app(monkeypatch, capsys):
    # engine-20: without a __main__ guard, python -m qrep.cli exits 0 with no
    # output. runpy runs the module as __main__ in-process, so this also runs
    # under Pyodide, which has no subprocess.
    monkeypatch.setattr(sys, "argv", ["qrep", "--help"])
    with warnings.catch_warnings():
        # qrep.cli is already imported by this file, and runpy warns about that
        warnings.filterwarnings("ignore", "'qrep.cli' found in sys.modules", RuntimeWarning)
        with pytest.raises(SystemExit) as exit_info:
            runpy.run_module("qrep.cli", run_name="__main__")
    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    assert "validate" in output
    assert "plan" in output
