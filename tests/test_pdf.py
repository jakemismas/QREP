"""Tests for the PDF booklet exporter.

Sections are asserted on directly; the PDF itself is only structure-tested
(text extracted with pypdf), never byte-compared, because reportlab embeds a
build timestamp. Every expected literal traces back to the fixture quilt or the
strip plan, never to observed output.
"""

import csv
import re
from pathlib import Path

import pypdf
import pytest

from qrep.construct.strategies import STRATEGIES
from qrep.export.cutlist import render_cutlist_csv
from qrep.export.pdf import SECTION_TITLES, build_sections, render_booklet
from qrep.model import load

FIXTURE = Path(__file__).parent / "fixtures" / "double_irish_chain.json"


@pytest.fixture
def quilt():
    return load(FIXTURE)


@pytest.fixture
def plan(quilt):
    # The strip strategy gives the richest booklet: strip sets plus block-row
    # assembly steps.
    return STRATEGIES["strip"](quilt)


def _normalize(text: str) -> str:
    # One normalization for both sides of every containment check: pypdf mangles
    # whitespace and can drop straight-quote inch marks, so collapse all
    # whitespace runs to single spaces and remove the double-quote inch marks.
    return re.sub(r"\s+", " ", text.replace('"', "")).strip()


def _sections_by_title(quilt, plan):
    return {s.title: s for s in build_sections(quilt, plan)}


def test_sections_are_the_eight_titles_in_order(quilt, plan):
    sections = build_sections(quilt, plan)
    assert tuple(s.title for s in sections) == SECTION_TITLES
    assert len(sections) == 8


def test_cutting_rows_cover_both_fabrics_with_positive_quantities(quilt, plan):
    table = _sections_by_title(quilt, plan)["Cutting"].tables[0]
    assert table.header == ["Fabric", "Piece", "Component", "Quantity", "Cut size", "Finished size"]
    fabric_names = {f.name for f in quilt.palette.fabrics}
    quantity_by_fabric = {name: 0 for name in fabric_names}
    for fabric, _piece, _component, quantity, _cut, _finished in table.rows:
        assert fabric in fabric_names
        parsed = int(quantity)
        assert parsed > 0
        quantity_by_fabric[fabric] += parsed
    # Both palette fabrics appear and each contributes at least one piece.
    assert all(total > 0 for total in quantity_by_fabric.values())


def test_strip_sets_table_has_at_least_five_rows(quilt, plan):
    # The Double Irish Chain has two block types spanning five distinct block-row
    # signatures, so the strip plan yields at least five strip sets.
    strip = _sections_by_title(quilt, plan)["Strip sets"]
    assert strip.tables, "strip strategy produces a strip-set table"
    assert len(strip.tables[0].rows) >= 5


def test_assembly_has_at_least_ten_numbered_steps(quilt, plan):
    assembly = _sections_by_title(quilt, plan)["Assembly"]
    assert len(assembly.numbered) >= 10


def test_fabrics_purchase_table_lists_binding_and_backing(quilt, plan):
    fabrics = _sections_by_title(quilt, plan)["Fabrics"]
    # tables[0] is the palette, tables[1] is the purchase/yardage table.
    purchase_names = [row[0] for row in fabrics.tables[1].rows]
    assert any("Binding" in name for name in purchase_names)
    assert any("backing" in name for name in purchase_names)


def test_pdf_contains_titles_fabric_names_and_every_cut_size(tmp_path, quilt, plan):
    out = tmp_path / "booklet.pdf"
    render_booklet(quilt, plan, out)
    assert out.exists() and out.stat().st_size > 0

    reader = pypdf.PdfReader(str(out))
    text = _normalize("\n".join((page.extract_text() or "") for page in reader.pages))

    for title in SECTION_TITLES:
        assert _normalize(title) in text
    for fabric in quilt.palette.fabrics:
        assert _normalize(fabric.name) in text

    cut_sizes = {row["cut_size"] for row in csv.DictReader(render_cutlist_csv(quilt, plan).splitlines())}
    assert cut_sizes, "cut list CSV yields at least one cut size"
    for size in cut_sizes:
        assert _normalize(size) in text
