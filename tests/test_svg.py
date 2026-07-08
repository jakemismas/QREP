"""SVG diagram tests: golden, cell fidelity, rulers, blocks, strips, assembly."""

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from qrep.construct import plan_historical, plan_strip
from qrep.export import export_all
from qrep.export.svg import (
    render_assembly_svg,
    render_block_svgs,
    render_strip_sets_svg,
    render_top_svg,
)
from qrep.model import load

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"
NS = "{http://www.w3.org/2000/svg}"


@pytest.fixture
def quilt():
    return load(FIXTURE_PATH)


def _elements(svg_text: str, tag: str, cls: str) -> list:
    root = ET.fromstring(svg_text)
    return [e for e in root.iter(f"{NS}{tag}") if e.attrib.get("class") == cls]


def test_golden_top_svg(quilt, golden):
    golden("top.svg", render_top_svg(quilt))


def test_render_top_twice_identical(quilt):
    assert render_top_svg(quilt) == render_top_svg(quilt)


def test_cell_fidelity(quilt):
    svg = render_top_svg(quilt)
    cells = _elements(svg, "rect", "cell")
    # 45 x 55 center cells exactly
    assert len(cells) == 45 * 55 == 2475
    fills = {c.attrib["fill"] for c in cells}
    assert fills == {f.color for f in quilt.palette.fabrics} == {"#9db8d9", "#f2e8d5"}


def test_ruler_extents_and_labels(quilt):
    svg = render_top_svg(quilt)
    # ruler lines span exactly the finished dimensions at 10 px per inch
    (ruler_x,) = _elements(svg, "line", "ruler-x")
    assert float(ruler_x.attrib["x2"]) - float(ruler_x.attrib["x1"]) == 750.0
    (ruler_y,) = _elements(svg, "line", "ruler-y")
    assert float(ruler_y.attrib["y2"]) - float(ruler_y.attrib["y1"]) == 900.0
    # major labels every 5 inches: 0..75 on x (16 labels), 0..90 on y (19)
    labels_x = [t.text for t in _elements(svg, "text", "ruler-label-x")]
    assert labels_x == [str(i) for i in range(0, 76, 5)]
    labels_y = [t.text for t in _elements(svg, "text", "ruler-label-y")]
    assert labels_y == [str(i) for i in range(0, 91, 5)]
    # minor ticks each whole inch: 76 x-ticks total, 16 of them major
    assert len(_elements(svg, "line", "tick-x-minor")) == 76 - 16
    assert len(_elements(svg, "line", "tick-x-major")) == 16


def test_block_svgs(quilt):
    blocks = render_block_svgs(quilt)
    assert set(blocks) == {"a", "b"}
    for key, expected_make in (("a", "make 50"), ("b", "make 49")):
        cells = _elements(blocks[key], "rect", "cell")
        assert len(cells) == 25
        (title,) = _elements(blocks[key], "text", "block-title")
        assert expected_make in title.text


def test_strip_sets_svg(quilt):
    strip_svg = render_strip_sets_svg(quilt, plan_strip(quilt))
    # 5 distinct sets x 5 strips each
    assert len(_elements(strip_svg, "rect", "strip")) == 25
    assert len(_elements(strip_svg, "text", "strip-set-title")) == 5
    assert render_strip_sets_svg(quilt, plan_historical(quilt)) is None


def test_assembly_svg(quilt):
    svg = render_assembly_svg(quilt)
    letters = [t.text for t in _elements(svg, "text", "block-letter")]
    # 9 x 11 block layout, A wherever row+col is even
    assert len(letters) == 99
    assert letters.count("A") == 50 and letters.count("B") == 49
    numbers = [t.text for t in _elements(svg, "text", "row-number")]
    assert numbers == [str(i) for i in range(1, 12)]


def test_export_svg_files(quilt, tmp_path):
    strip_files = export_all(quilt, plan_strip(quilt), tmp_path / "strip", ["svg"])
    names = {p.name for p in strip_files}
    assert names == {"top.svg", "block_a.svg", "block_b.svg", "strip_sets.svg", "assembly.svg"}
    hist_files = export_all(quilt, plan_historical(quilt), tmp_path / "hist", ["svg"])
    assert "strip_sets.svg" not in {p.name for p in hist_files}
