"""Text export tests: goldens, CSV reconciliation, yardage report, and the
golden protocol's missing-file path."""

import csv
import io
from pathlib import Path

import pytest

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
    with pytest.raises(pytest.fail.Exception, match="run --bless"):
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
    # backing (MATH.md V-BACK-09): 2 panels x 784 = 1568 eighths + the 72 e
    # pieced allowance = 1640 -> ceil(1640/72) = 23 quarter yards = 5.75 yd
    backing = report.lines[-1]
    assert backing.yards == 5.75
    # every value is a whole multiple of 0.25 yd
    assert all((line.yards * 4).is_integer() for line in report.lines)
    text = render_yardage_md(report)
    assert "Binding - Chain blue" in text
    # the name is built from the fixture's backing width, 336 e = 42"
    assert 'backing, 42" wide fabric' in text


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


def test_format_yards_prints_mixed_fractions_of_the_increment():
    # F13: yards as mixed fractions of the purchase increment; 1 yd = 288 e
    # 1/8 yd (36 e): 11 x 36 = 396 e = 288 + 108 -> 1 + 108/288 = 1 3/8 yd
    assert format_yards(11, 36) == "1 3/8 yd"
    # 4 x 36 = 144 e = 144/288 = 1/2 yd
    assert format_yards(4, 36) == "1/2 yd"
    # 8 x 36 = 288 e = 1 yd
    assert format_yards(8, 36) == "1 yd"
    # 5 x 36 = 180 e = 180/288 = 5/8 yd
    assert format_yards(5, 36) == "5/8 yd"
    # the default stays quarter yards: 22 x 72 = 1584 e = 5 x 288 + 144 -> 5 1/2 yd
    assert format_yards(22, 72) == "5 1/2 yd"


def test_yardage_report_shows_purchase_lengths_and_allowances(fixture_quilt):
    report = compute_purchase_lines(fixture_quilt, plan_strip(fixture_quilt))
    text = render_yardage_md(report)
    assert "| Fabric | Length needed | Purchase length | Yards |" in text
    # V-BACK-09: 1568 e = 196 in needed; + 72 e pieced allowance = 1640 e = 205 in;
    # ceil(1640 / 72) = 23 qy = 5 3/4 yd
    assert (
        '| backing, 42" wide fabric: (2) panels 98" long, vertical seams '
        '| 196" | 205" | 5 3/4 yd |'
    ) in text
    # V-WIDE-08: 664 e = 83 in; + 36 e = 700 e = 87 1/2 in; ceil(700 / 72) = 10 qy = 2 1/2 yd
    wide = next(line for line in text.splitlines() if line.startswith("Or replace"))
    assert wide == (
        'Or replace the backing line with wide backing, 108" wide fabric: one piece 83" long '
        '(83" needed, 87 1/2" with its squaring allowance), 2 1/2 yd.'
    )
    assert wide.count(":") == 1
    # footer: p = 10 percent; the backing allowance 1640 - 1568 = 72 e = 9 in; r = 72 e = 1/4 yd
    assert "adds a 10 percent margin to each quilt-top fabric" in text
    assert 'a 9" squaring allowance to the backing' in text
    assert "Each line rounds up to the nearest 1/4 yd." in text


def test_yardage_report_at_an_eighth_yard_increment(fixture_quilt):
    quilt = fixture_quilt.model_copy(
        update={"settings": fixture_quilt.settings.model_copy(update={"purchase_increment": 36})}
    )
    text = render_yardage_md(compute_purchase_lines(quilt, plan_strip(quilt)))
    # binding at the stored 42 in: 9 strips x 20 e = 180 e = 22 1/2 in, no allowance;
    # ceil(180 / 36) = 5 eighths of a yard = 5/8 yd
    assert '| Binding - Chain blue (b) | 22 1/2" | 22 1/2" | 5/8 yd |' in text
    assert "Each line rounds up to the nearest 1/8 yd." in text
