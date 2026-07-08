"""Viewer tests: sizing math (hand-computed), emitter output, view CLI.

The JS in template.html mirrors these formulas; these tests pin the numbers
both sides must agree on (fixture: 55x45 cells of 12 eighths, border 30,
block 5, so interior width = target - 60)."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from qrep.cli import app
from qrep.model import load
from qrep.viewer import (
    PRESETS,
    build_view_config,
    emit_viewer,
    locked_resize,
    round_div,
    unlocked_resize,
    write_viewer,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"

runner = CliRunner()


@pytest.fixture
def quilt():
    return load(FIXTURE_PATH)


def test_round_div_half_up():
    # 29/2 = 14.5 rounds UP to 15 (half-up, not banker's)
    assert round_div(29, 2) == 15
    # 12/5 = 2.4 -> 2; 13/5 = 2.6 -> 3
    assert round_div(12, 5) == 2
    assert round_div(13, 5) == 3
    # 660/45 = 14.67 -> 15
    assert round_div(660, 45) == 15
    assert round_div(0, 45) == 0


def test_locked_resize_queen_width():
    # queen preset width 720: interior 720 - 60 = 660; cell = round(660/45) = 15;
    # achieved = 45*15 + 60 = 735 (91 7/8"), 55*15 + 60 = 885 (110 5/8")
    result = locked_resize(55, 45, 12, 30, target_width=720)
    assert result.cell_size == 15
    assert (result.rows, result.cols) == (55, 45)  # counts never change locked
    assert result.achieved_width == 735
    assert result.achieved_height == 885


def test_locked_resize_identity():
    # width 600 = the fixture's own width: cell (600-60)/45 = 12 exactly
    result = locked_resize(55, 45, 12, 30, target_width=600)
    assert result.cell_size == 12
    assert result.achieved_width == 600
    assert result.achieved_height == 720


def test_locked_resize_by_cell():
    # cell 16 (2"): 45*16 + 60 = 780, 55*16 + 60 = 940
    result = locked_resize(55, 45, 12, 30, target_cell=16)
    assert result.achieved_width == 780
    assert result.achieved_height == 940


def test_locked_resize_clamps_to_one_eighth():
    result = locked_resize(55, 45, 12, 30, target_width=0)
    assert result.cell_size == 1


def test_unlocked_resize_exact_block_fit():
    # width 780: interior 720; blocks = round(720 / (5*12)) = 12; cols = 60;
    # achieved 60*12 + 60 = 780 exact; rows untouched -> height stays 720
    result = unlocked_resize(55, 45, 12, 30, 5, target_width=780)
    assert result.cols == 60
    assert result.rows == 55
    assert result.cell_size == 12  # cell never changes unlocked
    assert result.achieved_width == 780
    assert result.achieved_height == 720


def test_unlocked_resize_quantizes():
    # width 700: interior 640; 640/60 = 10.67 -> 11 blocks -> 55 cols;
    # achieved 55*12 + 60 = 720, reported next to the 700 requested
    result = unlocked_resize(55, 45, 12, 30, 5, target_width=700)
    assert result.cols == 55
    assert result.achieved_width == 720


def test_unlocked_resize_height_independent():
    result = unlocked_resize(55, 45, 12, 30, 5, target_height=780)
    assert result.rows == 60
    assert result.cols == 45
    assert result.achieved_height == 780


def test_unlocked_clamps_to_one_block():
    result = unlocked_resize(55, 45, 12, 30, 5, target_width=1)
    assert result.cols == 5


def test_build_view_config_fixture(quilt):
    config = build_view_config(quilt)
    assert config["rows"] == 55
    assert config["cols"] == 45
    assert config["cellSize"] == 12
    assert config["borders"] == [30]
    assert config["block"] == 5
    assert config["checker"] is True
    assert config["wof"] == 336
    assert len(config["blockTypes"]) == 2
    # preset table pinned in eighths
    assert config["presets"][0] == {"name": "Crib", "w": 288, "h": 416}
    assert [p["name"] for p in config["presets"]] == [n for n, _, _ in PRESETS]


def test_emitted_viewer_is_self_contained(quilt):
    html = emit_viewer(quilt)
    # model JSON embedded, zero external references of any protocol
    assert '"schema_version"' in html
    assert "Double Irish Chain 75x90" in html
    assert "http" not in html.lower()
    assert "/*__QREP_MODEL__*/" not in html  # placeholder actually replaced
    assert "/*__QREP_CONFIG__*/" not in html
    assert "__QREP_BORDER_INPUTS__" not in html


def test_emitted_viewer_contains_required_controls(quilt):
    html = emit_viewer(quilt)
    assert 'id="ruler-x"' in html and 'id="ruler-y"' in html
    for label in (
        "Crib 36 x 52",
        "Throw 50 x 65",
        "Twin 70 x 90",
        "Full 84 x 90",
        "Queen 90 x 108",
        "King 110 x 108",
    ):
        assert label in html, label
    assert 'id="proportion-lock"' in html
    # pre-rendered border input carries the shared formatter's value
    assert 'id="border-width-0"' in html
    assert 'value="3 3/4"' in html
    # the JS consumes the exact config numbers the Python helper was tested on
    assert '"cols": 45' in html
    assert '"block": 5' in html
    assert '"checker": true' in html


def test_emit_twice_identical(quilt):
    assert emit_viewer(quilt) == emit_viewer(quilt)


def test_view_cli_writes_single_file(tmp_path):
    out = tmp_path / "viewer.html"
    result = runner.invoke(app, ["view", str(FIXTURE_PATH), "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists() and out.stat().st_size > 0
    assert list(tmp_path.iterdir()) == [out]  # exactly one file, no assets


def test_write_viewer_returns_path(quilt, tmp_path):
    out = write_viewer(quilt, tmp_path / "v.html")
    assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
