"""Text export tests: goldens, CSV reconciliation, yardage report, and the
golden protocol's missing-file path."""

import csv
import io
from pathlib import Path

import pytest
from _pytest.outcomes import Failed

from qrep.construct import compute_purchase_lines, plan_strip
from qrep.export import export_all, render_cutlist_csv, render_cutlist_md
from qrep.export.yardage_report import format_yards, render_yardage_md
from qrep.model import load

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"


@pytest.fixture
def fixture_quilt():
    return load(FIXTURE_PATH)


def test_golden_cutlist_md(fixture_quilt, golden):
    plan = plan_strip(fixture_quilt)
    golden("cutlist_strip.md", render_cutlist_md(fixture_quilt, plan))


def test_golden_cutlist_csv(fixture_quilt, golden):
    plan = plan_strip(fixture_quilt)
    golden("cutlist_strip.csv", render_cutlist_csv(fixture_quilt, plan))


def test_missing_golden_fails_with_run_bless(golden, bless_mode):
    if bless_mode:
        pytest.skip("bless mode writes goldens; the missing-file path needs a plain run")
    with pytest.raises(Failed, match="run --bless"):
        golden("never_blessed_anywhere.txt", "content")


def test_csv_reconciles_piece_count(fixture_quilt):
    """Parse the CSV as a consumer would; the top piece count must match the
    plan metrics exactly (2475 cells + 4 border pieces = 2479)."""
    plan = plan_strip(fixture_quilt)
    text = render_cutlist_csv(fixture_quilt, plan)
    rows = list(csv.DictReader(io.StringIO(text)))
    top_quantity = sum(int(r["quantity"]) for r in rows if r["component"] != "binding")
    assert top_quantity == plan.metrics.piece_count == 2479


def test_yardage_report_has_binding_and_backing_lines(fixture_quilt):
    plan = plan_strip(fixture_quilt)
    report = compute_purchase_lines(fixture_quilt, plan)
    purposes = [line.purpose for line in report.lines]
    assert "binding" in purposes
    assert purposes[-1] == "backing"
    # binding: 9 WOF strips x 20 eighths = 180 eighths; ceil(180/72) = 3
    # quarter yards = 0.75 yd
    binding = next(line for line in report.lines if line.purpose == "binding")
    assert binding.length_needed == 180
    assert binding.yards == 0.75
    # backing: 2 panels x 784 = 1568 eighths -> 22 quarter yards = 5.5 yd
    backing = report.lines[-1]
    assert backing.yards == 5.5
    # every value is a whole multiple of 0.25 yd
    assert all((line.yards * 4).is_integer() for line in report.lines)
    text = render_yardage_md(report)
    assert "Binding - Chain blue" in text
    assert "backing, any 42-inch WOF fabric" in text


def test_format_yards():
    # hand-computed: 22 quarter yards = 5 wholes + 2/4 = 5 1/2 yd
    assert format_yards(22) == "5 1/2 yd"
    assert format_yards(3) == "3/4 yd"
    assert format_yards(8) == "2 yd"
    assert format_yards(1) == "1/4 yd"


def test_export_twice_is_byte_identical(fixture_quilt, tmp_path):
    plan = plan_strip(fixture_quilt)
    first = export_all(fixture_quilt, plan, tmp_path / "one")
    second = export_all(fixture_quilt, plan, tmp_path / "two")
    assert [p.name for p in first] == [p.name for p in second]
    for a, b in zip(first, second):
        # PDF is structure-tested via pypdf, never byte-tested: reportlab
        # embeds timestamps (design doc, determinism section)
        if a.suffix == ".pdf":
            continue
        assert a.read_bytes() == b.read_bytes(), a.name


def test_export_unknown_format_raises(fixture_quilt, tmp_path):
    plan = plan_strip(fixture_quilt)
    with pytest.raises(KeyError, match="unknown export format"):
        export_all(fixture_quilt, plan, tmp_path, ["holograph"])
