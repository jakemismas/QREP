"""Tests for the PATTERN-SPEC section 6 checker in tests/pattern_checks.py (A11).

Every PDF here is drawn directly with the reportlab canvas, never by qrep.export, so the
checker is tested against documents whose every number was worked out by hand below. The
complete pattern is a 60" x 72" throw: 20 blocks of 12" (nine-patch blocks alternating with
plain blocks) from 4" squares, a 6" border and a binding-only fabric. A second document
carries triangle and stitch-and-flip units. Each check gets a passing case and a failing
case made by one edit to a passing document.
"""

import ast
import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from reportlab.lib.colors import HexColor
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

import pattern_checks as pc

HERE = Path(__file__).parent
NAME = "Lantern Grid"
COLORS = {"A": "#f2e8d5", "B": "#3b5b92", "C": "#b03a2e"}
IDS = {"A": "c", "B": "b", "C": "r"}

# Every check the checker implements: section 6's [S] checks less PS-04 and PS-40.
IMPLEMENTED = ["PS-01", "PS-02", "PS-03", "PS-05", "PS-06", "PS-07", "PS-08", "PS-09",
               "PS-10", "PS-11", "PS-12", "PS-13", "PS-14", "PS-15", "PS-16", "PS-17",
               "PS-18", "PS-19", "PS-20", "PS-21", "PS-22", "PS-23", "PS-24", "PS-25",
               "PS-26", "PS-27", "PS-28", "PS-29", "PS-30", "PS-31", "PS-33", "PS-38",
               "PS-39", "PS-41", "PS-42", "PS-43"]

NINE = ("BAB", "ABA", "BAB")
PLAIN = ("AAA", "AAA", "AAA")


def block_letter(r: int, c: int) -> str:
    # Blocks of 3 x 3 squares; (block row + block column) even is a nine-patch, so the
    # top-left block is Block 1 and each row of 4 blocks holds 2 of each.
    return (NINE if (r // 3 + c // 3) % 2 == 0 else PLAIN)[r % 3][c % 3]


def throw_model() -> dict:
    # Center 12 x 15 squares of 4 in (32 e) = 48 x 60 in; one 6 in (48 e) border band, so
    # the quilt finishes at 48 + 12 = 60 by 60 + 12 = 72 in.
    return {
        "schema_version": "1",
        "metadata": {"name": NAME, "notes": ""},
        "palette": {"fabrics": [{"id": IDS[k], "name": n, "color": COLORS[k]}
                                for k, n in (("A", "Background"), ("B", "Blue"),
                                             ("C", "Red"))]},
        "center": {"kind": "grid", "rows": 15, "cols": 12, "cell_size": 32,
                   "cells": [[IDS[block_letter(r, c)] for c in range(12)] for r in range(15)]},
        "borders": [{"fabric_id": "c", "width": 48}],
        "binding": {"fabric_id": "r", "strip_width": 20},
        "settings": {"seam_allowance": 2, "wof": 320, "binding_strip_width": 20,
                     "binding_extra": 80, "backing_margin": 64, "backing_width": 336,
                     "wide_back_width": 864, "backing_pieced_allowance": 72,
                     "backing_one_piece_allowance": 36, "purchase_increment": 72,
                     "top_margin": 10},
        "provenance": {"source": "authored", "stage_confidence": {}},
        "confirmed_blocks": {"blocks_across": 4, "blocks_down": 5, "squares_across": 3,
                             "squares_down": 3, "confidence": 1.0},
        "size_basis": {"source": "typed", "requested_width": 480, "requested_height": 576,
                       "achieved_width": 480, "achieved_height": 576, "rounding_step": 8,
                       "confidence": 1.0},
    }


# ---------------------------------------------------------------- drawing


def P(text, size=10, indent=0):
    return ("p", text, size, indent)


def ROW(cells, swatch=None, size=10):
    return ("row", cells, swatch, size)


def FIG(*rows):
    return ("fig", rows)


def _fill(c, letter):
    c.setFillColor(HexColor(COLORS[letter]))


def _draw_p(c, item, y):
    _, text, size, indent = item
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", size)
    for line in simpleSplit(text, "Helvetica", size, 500 - indent):
        c.drawString(54 + indent, y, line)
        y -= size * 1.4
    return y - 4


def _draw_row(c, item, y):
    _, cells, swatch, size = item
    if swatch:
        _fill(c, swatch)
        c.rect(54, y - 1, 10, 10, fill=1, stroke=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", size)
    for dx, text in cells:
        c.drawString(70 + dx, y, text)
    return y - size * 1.6


def _draw_fabric(c, item, y):
    return _draw_row(c, ROW([(0, f"{item[1]} {item[2]}")], item[1]), y)


def _draw_fig(c, item, y, cell=14, x0=220):
    top = y - 24
    for r, row in enumerate(item[1]):
        for k, letter in enumerate(row):
            _fill(c, letter)
            c.rect(x0 + k * cell, top - (r + 1) * cell, cell, cell, fill=1, stroke=1)
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica", 7)
            c.drawCentredString(x0 + k * cell + cell / 2, top - (r + 1) * cell + 4, letter)
    return top - len(item[1]) * cell - 30


def _draw_render(c, item, y, label_w='60"', label_h='72"'):
    # 2 1/2 pt per inch: 4 in squares are 10 pt and the 6 in border is 15 pt.
    x0, top = 230, y - 20
    _fill(c, "A")
    c.rect(x0, top - 180, 150, 180, fill=1, stroke=1)
    for r in range(15):
        for k in range(12):
            _fill(c, block_letter(r, k))
            c.rect(x0 + 15 + k * 10, top - 15 - (r + 1) * 10, 10, 10, fill=1, stroke=0)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", item[3] if len(item) > 3 else 7)
    c.drawCentredString(x0 + 75, top - 192, item[1] if len(item) > 1 else label_w)
    c.drawString(x0 + 156, top - 90, item[2] if len(item) > 2 else label_h)
    return top - 220


def _draw_square(c, item, y):
    c.setStrokeColorRGB(0, 0, 0)
    side = item[1] if len(item) > 1 else 72
    c.rect(54, y - 72, side, side, fill=0, stroke=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 10)
    c.drawString(140, y - 40, 'Print at 100 percent. This square should measure 1" x 1".')
    return y - 90


def _draw_chart(c, item, y, cell=18):
    dots = item[1] if len(item) > 1 else ()
    x0, top = 80, y - 24
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0, 0, 0)
    if len(item) > 2:
        # A split part's range label, 14 pt above the chart's top edge.
        c.drawString(x0, top + 14, item[2])
    for k in range(12):
        c.drawCentredString(x0 + k * cell + cell / 2, top + 4, str(k + 1))
    for r in range(15):
        base = top - (r + 1) * cell
        c.setFillColorRGB(0, 0, 0)
        c.drawRightString(x0 - 4, base + 6, str(r + 1))
        for k in range(12):
            letter = block_letter(r, k)
            _fill(c, letter)
            c.rect(x0 + k * cell, base, cell, cell, fill=1, stroke=1)
            c.setFillColorRGB(1, 1, 1) if letter == "B" else c.setFillColorRGB(0, 0, 0)
            c.drawCentredString(x0 + k * cell + cell / 2, base + 6, letter)
            if (r, k) in dots:
                c.setFillColorRGB(0, 0, 0)
                c.circle(x0 + k * cell + 14, base + 14, 2, fill=1, stroke=0)
    return top - 15 * cell - 20


def _draw_outline(c, item, y):
    c.setStrokeColorRGB(0, 0, 0)
    for r in range(15):
        for k in range(12):
            c.rect(245 + k * 10, y - 50 - r * 10, 10, 10, fill=0, stroke=1)
    return y - 220


def _draw_fat_quarter(c, item, y):
    # An 18 x 21 in fat quarter at 3 pt per inch, labeled inside the outline.
    top = y - 24
    _fill(c, "B")
    c.rect(220, top - 63, 54, 63, fill=1, stroke=1)
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 7)
    c.drawString(226, top - 30, '18" x 21"')
    return top - 100


def _draw_gap(c, item, y):
    return y - item[1]


def _draw_at(c, item, y):
    # Body text at a fixed baseline, leaving the flow where it was.
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 10)
    c.drawString(54, item[2], item[1])
    return y


DRAW = {"p": _draw_p, "row": _draw_row, "fabric": _draw_fabric, "fig": _draw_fig,
        "fig_left": lambda c, item, y: _draw_fig(c, item, y, x0=54),
        "render": _draw_render, "square": _draw_square, "chart": _draw_chart,
        "outline": _draw_outline, "fat_quarter": _draw_fat_quarter, "gap": _draw_gap,
        "at": _draw_at}


def render(pages, path, *, name=NAME, footer_size=10, odd_page=None, footer_layout="one line"):
    c = canvas.Canvas(str(path), pagesize=(612, 792), invariant=1)
    for n, items in enumerate(pages, start=1):
        c.setPageSize((612, 790) if n == odd_page else (612, 792))
        y = 740
        for item in items:
            y = DRAW[item[0]](c, item, y)
        c.setFillColorRGB(0, 0, 0)
        c.setFont("Helvetica", footer_size)
        mark = f"page {n} of {len(pages)}"
        if footer_layout == "name above":
            c.drawString(54, 42, name)
            c.drawString(54, 30, f"{mark}  |  QREP 0.4.0")
        elif footer_layout == "version above":
            c.drawString(54, 42, "QREP 0.4.0")
            c.drawString(54, 30, f"{name}  |  {mark}")
        else:
            c.drawString(54, 30, f"{name}  |  {mark}  |  QREP 0.4.0")
        c.showPage()
    c.save()


def edit(pages, old, new):
    """One edit to a passing document; it must change something, or the test proves nothing."""
    pages = copy.deepcopy(pages)
    hits = 0
    for items in pages:
        for i, item in enumerate(items):
            if item[0] == "p" and old in item[1]:
                items[i] = ("p", item[1].replace(old, new), *item[2:])
                hits += 1
            elif item[0] == "row" and any(old in t for _, t in item[1]):
                items[i] = ("row", [(dx, t.replace(old, new)) for dx, t in item[1]], *item[2:])
                hits += 1
    assert hits, f"edit found no {old!r}"
    return pages


# ---------------------------------------------------------------- the throw pattern

# Hand computation of every number the throw prints (MATH.md section 1.3 defaults:
# U = 40 in = 320 e, B = 42 in, BW = 108 in, o = 4 in, w = 2 1/2 in, t = 10 in):
# - Blocks: 4 across x 5 down = 20; 10 nine-patch (Block 1) and 10 plain (Block 2).
#   Block finished 3 x 4 = 12 in; checkpoint 12 1/2 in (PATTERN-SPEC S6).
# - Strip set 1 (B A B, rows 1 and 3 of a nine-patch): 2 per block x 10 = 20 segments,
#   cut 4 + 1/2 = 4 1/2 in (36 e); per set floor(320 / 36) = 8; sets ceil(20 / 8) = 3
#   (MATH.md F3). Strips: B1 2 x 3 = 6, A1 1 x 3 = 3.
# - Strip set 2 (A B A, row 2): 1 per block x 10 = 10 segments; sets ceil(10 / 8) = 2.
#   Strips: A2 2 x 2 = 4, B2 1 x 2 = 2.
# - Segment checkpoint: 4 1/2 x (3 x 4 + 1/2) = 4 1/2 x 12 1/2 in.
# - Plain blocks merge into one piece (PATTERN-SPEC M-04): 10 squares cut 12 1/2 in (100 e);
#   per strip floor(320 / 100) = 3; strips ceil(10 / 3) = 4; last strip 10 - 3 x 3 = 1
#   (MATH.md F2).
# - Border (MATH.md F4): strips 6 1/2 in (52 e); sides Ls = 60 + 1/2 = 60 1/2 in (484 e),
#   top and bottom Lt = 48 + 12 + 1/2 = 60 1/2 in; both > 40 in, so
#   k = ceil((484 - 4) / (320 - 4)) = ceil(480 / 316) = 2 (V-UNIT-04, as in V-YIELD-03);
#   strips 2 x 2 + 2 x 2 = 8.
# - Fabric A (MATH.md F5): 8 x 52 + 3 x 36 + 4 x 36 + 4 x 100 = 416 + 108 + 144 + 400
#   = 1068 e; purchase ceil(1068 x 110 / 100) = ceil(1174.8) = 1175 e;
#   qy ceil(1175 / 72) = ceil(16.32) = 17 -> 4 1/4 yd.
# - Fabric B: (6 + 2) x 36 = 288 e; purchase 317 e (V-UNIT-02); qy ceil(317 / 72) = 5
#   -> 1 1/4 yd.
# - Binding, fabric C: V-BIND-13 (throw 60 x 72): (8) strips, 3/4 yd.
# - Backing: V-BACK-02: 4 1/4 yd, (2) lengths of 68 in, seams across (horizontal).
# - Wide back: V-WIDE-02: 2 1/4 yd of 108 in.  Batting: V-BATT-03: 68 x 80 in, twin.
# - Areas (C-02): Background 130 squares + border, Blue 50 squares, so A Background,
#   B Blue, C Red (binding only, last).
# - Quilt center checkpoint: 48 1/2 x 60 1/2 in.


def throw_pages():
    cover = [
        P(NAME, size=24),
        P('Finished size 60" x 72"'),
        P('20 blocks, 12" finished, set 4 x 5, strip pieced'),
        P("3 fabrics, plus backing"),
        P('You asked for 60" x 72"; this pattern makes 60" x 72" with 4" finished squares.'),
        P("QREP recovers the layout of a pictured quilt. If this quilt comes from a designer's "
          "published pattern, buy that pattern to support the designer."),
        ("render",),
    ]
    requirements = [
        P("Fabric requirements", size=14),
        ROW([(0, "A"), (20, "Background"), (230, "4 1/4 yd")], "A"),
        ROW([(0, "B"), (20, "Blue"), (230, "1 1/4 yd")], "B"),
        ROW([(0, "C"), (20, "Red"), (230, "3/4 yd"), (290, 'Binding: (8) 2 1/2" x WOF strips')],
            "C"),
        ROW([(0, "Backing"), (80, '4 1/4 yd: 2 lengths of 68" at 42" wide, seams run across '
                                  'the quilt;')]),
        ROW([(80, 'or 2 1/4 yd of 108" wide backing')]),
        ROW([(0, "Batting"), (80, '68" x 80", twin package (72" x 90")')]),
        P('Fabric amounts are rounded up to the next 1/4 yd, and top fabrics include 10 percent '
          'extra. Strips assume 40" of usable width (WOF). Backing assumes 42" wide fabric with '
          'the selvages trimmed. Borders are cut across the WOF and joined with straight seams.'),
        P('Supplies: rotary cutter and mat, 6" x 24" ruler, neutral thread.'),
        ("square",),
    ]
    begin = [
        P("Before you begin", size=14),
        P("1. Read the whole pattern before cutting."),
        P('2. Every piecing seam is 1/4", and every cut size already includes seam allowances.'),
        P('3. Should-measure sizes are unfinished: they include the 1/4" allowance on every '
          'edge.'),
        P("4. RST means right sides together, and yd means yard."),
        P('5. WOF means width of fabric. Strips are cut across the full width; yields assume '
          '40" of usable width per strip, a safe planning figure.'),
        P('6. Backing yardage assumes 42" wide backing fabric with the selvages trimmed, joined '
          'with 1/2" seams pressed open, 4" past the quilt on every side, in the layout that '
          'uses less fabric.'),
        P("7. Press every seam to one side so that seams meet in opposite directions and nest. "
          "An arrow means press toward the arrow; a dashed line means sew here; a dotted line "
          "means cut here."),
        P("8. Fabrics carry letters with a swatch; each piece carries a label such as A1, its "
          "fabric letter and a number."),
        P('9. Bind with double-fold binding from 2 1/2" strips joined with diagonal seams, '
          'mitered at the corners and finished by hand, with 10" extra for the corners and the '
          'final join.'),
    ]
    cutting = [
        P("Cutting", size=14),
        ("fabric", "A", "Background"),
        P('1. Cut (8) 6 1/2" x WOF strips. For each side border, join (2) strips end to end '
          'with straight seams and trim to 60 1/2". For the top and bottom borders, join (2) '
          'strips each and trim to 60 1/2".'),
        P('2. Cut (3) 4 1/2" x WOF strips. Set aside the strips (A1) for strip set 1.'),
        P('3. Cut (4) 4 1/2" x WOF strips. Set aside the strips (A2) for strip set 2.'),
        P('4. Cut (4) 12 1/2" x WOF strips.'),
        P('A3: subcut (4) strips into (10) 12 1/2" squares, 3 per strip. The last strip gives '
          '(1).', indent=20),
        ("fabric", "B", "Blue"),
        P('1. Cut (6) 4 1/2" x WOF strips. Set aside the strips (B1) for strip set 1.'),
        P('2. Cut (2) 4 1/2" x WOF strips. Set aside the strips (B2) for strip set 2.'),
        ("fabric", "C", "Red"),
        P('1. Cut (8) 2 1/2" x WOF strips for binding.'),
    ]
    units = [
        P("Making the units", size=14),
        P("Two blocks repeat across the quilt, so you sew long strips together and cut them "
          "into segments instead of cutting every square."),
        P("Sewing order: strip sets, then blocks, then rows, then borders."),
        P("Strip set 1", size=12),
        P("B1 (2)"),
        P("A1 (1)"),
        P("1. Sew the strips lengthwise in this order: B1, A1, B1. Press toward B1. Fig. 1"),
        P('2. Crosscut (20) 4 1/2" segments, 8 per set. Fig. 1'),
        FIG("BBB", "AAA", "BBB"),
        P('Each segment should measure 4 1/2" x 12 1/2".'),
        P("Make 3."),
        P("Strip set 2", size=12),
        P("A2 (2)"),
        P("B2 (1)"),
        P("1. Sew the strips lengthwise in this order: A2, B2, A2. Press toward B2. Fig. 2"),
        P('2. Crosscut (10) 4 1/2" segments, 8 per set. Fig. 2'),
        FIG("AAA", "BBB", "AAA"),
        P('Each segment should measure 4 1/2" x 12 1/2".'),
        P("Make 2."),
    ]
    blocks = [
        P("Making the blocks", size=14),
        P("Block 1", size=12),
        P("1. Lay out two Strip set 1 segments with one Strip set 2 segment between them. "
          "Fig. 3"),
        P("2. Sew the segments together and press the seams toward the center. Fig. 3"),
        FIG(*NINE),
        P('Block 1 should measure 12 1/2" square.'),
        P("Make 10."),
        P("Block 2", size=12),
        P("A3 (1)"),
        P("Block 2 is one A3 square. Fig. 4"),
        FIG(*PLAIN),
        P('Block 2 should measure 12 1/2" square.'),
        P("Make 10."),
    ]
    assembly = [
        P("Quilt assembly", size=14),
        P("Lay out the blocks in 5 rows of 4, alternating Block 1 and Block 2 as shown in "
          "Fig. 5."),
        P("Sew the blocks in each row together, pressing toward Block 2, and join the rows, "
          "pressing the row seams in one direction."),
        P('The quilt center should measure 48 1/2" x 60 1/2".'),
        FIG("BAB", "ABA"),
    ]
    borders = [
        P("Borders", size=14),
        P("1. Measure the quilt through its center and trim the A borders to match if needed. "
          "Sew the side borders first, then the top and bottom borders. Press toward the "
          "border. Fig. 6"),
        FIG("AAAA", "ABBA", "AAAA"),
    ]
    finishing = [
        P("Finishing", size=14),
        P('1. Backing: cut 2 lengths of 68", trim the selvages, sew them together along the long '
          'edges with 1/2" seams and press the seams open. Fig. 7'),
        FIG("AAAA", "AAAA", "AAAA"),
        P("2. Layer the backing right side down, then the batting, then the top right side up; "
          "smooth and baste."),
        P("3. Quilt as desired; an allover design suits this quilt."),
        P("4. Join the (8) binding strips with diagonal seams and press them open. Press the "
          'long strip in half lengthwise. Sew it to the front, stop 1/4" from each corner and '
          "fold to miter. Join the two ends, turn the binding to the back and stitch it by "
          "hand. Fig. 8"),
        FIG("CCC", "CAA", "CAA"),
    ]
    chart = [P("Layout chart", size=14), ("chart",)]
    coloring = [P("Coloring page", size=14), ("outline",)]
    return [cover, requirements, begin, cutting, units, blocks, assembly, borders, finishing,
            chart, coloring]


def results(tmp_path, pages, model=None, *, render_kw=None, **kw):
    pdf = tmp_path / "pattern.pdf"
    render(pages, pdf, **(render_kw or {}))
    return {r.check: r for r in pc.run_checks(pdf, model or throw_model(), **kw)}


def test_complete_pattern_passes_every_check(tmp_path):
    got = results(tmp_path, throw_pages())
    assert list(got) == IMPLEMENTED
    failing = {k: r.evidence for k, r in got.items() if r.status == "fail"}
    assert failing == {}
    # PATTERN-SPEC section 6: PS-39 runs only with a local reference directory.
    assert got["PS-39"].status == "not run"
    assert all(r.status == "pass" for k, r in got.items() if k != "PS-39")


def _bad_page_size(pages):
    return pages, {"odd_page": 3}


def _move(pages, page, src, dst):
    pages = copy.deepcopy(pages)
    pages[page].insert(dst, pages[page].pop(src))
    return pages


# One edit per check; each comment says why the edited document breaks that check.
FAILING = {
    # PS-01: page 3 is 612 x 790 pt, not Letter.
    "PS-01": lambda p: _bad_page_size(p),
    # PS-02: without its heading the Layout chart section is missing.
    "PS-02": lambda p: edit(p, "Layout chart", "Chart of the layout"),
    # PS-03: a page shows a date.
    "PS-03": lambda p: edit(p, "Supplies:", "Printed 2026-10-11. Supplies:"),
    # PS-05: "difficulty" is banned.
    "PS-05": lambda p: edit(p, "3 fabrics, plus backing", "3 fabrics, plus backing, difficulty 2"),
    # PS-06: 3/16 is not a whole eighth.
    "PS-06": lambda p: edit(p, 'stop 1/4" from', 'stop 3/16" from'),
    # PS-07: the model uses 3 fabrics (c, b, r).
    "PS-07": lambda p: edit(p, "3 fabrics, plus backing", "2 fabrics, plus backing"),
    # PS-10: Blue (50 squares) lettered before Background (130 squares plus the border).
    "PS-10": lambda p: _swap_rows(p),
    # PS-11: Finishing says 9 binding strips; MATH.md F7 (V-BIND-13) gives 8.
    "PS-11": lambda p: edit(p, "Join the (8) binding", "Join the (9) binding"),
    # PS-12: V-BACK-02 keeps horizontal seams, which run across the quilt.
    "PS-12": lambda p: edit(p, "seams run across", "seams run along"),
    # PS-13: V-BATT-03 picks the twin package, not the full.
    "PS-13": lambda p: edit(p, 'twin package (72" x 90")', 'full package (90" x 96")'),
    # PS-14: the 10 percent allowance is not stated.
    "PS-14": lambda p: edit(p, "include 10 percent extra", "include extra"),
    # PS-15: the WOF rule claims the 40 in is measured after trimming selvages.
    "PS-15": lambda p: edit(p, "a safe planning figure.", "measured after trimming selvages."),
    # PS-16: 4 strips x 2 per strip = 8 < 10 squares.
    "PS-16": lambda p: edit(p, '12 1/2" squares, 3 per strip', '12 1/2" squares, 2 per strip'),
    # PS-17: strip set 1 lists the cut square A3 instead of its set-aside strip A1.
    "PS-17": lambda p: edit(p, "A1 (1)", "A3 (1)"),
    # PS-18: A5 is used in Making the blocks but never cut, and A3 is cut but never used.
    "PS-18": lambda p: edit(p, "Block 2 is one A3 square", "Block 2 is one A5 square"),
    # PS-19: 4 sets x 2 B1 strips = 8, but Cutting sets aside 6.
    "PS-19": lambda p: edit(p, "Make 3.", "Make 4."),
    # PS-20: MATH.md F5 gives fabric A 4 1/4 yd (hand computation above).
    "PS-20": lambda p: _replace_item(p, 1, 1, ROW([(0, "A"), (20, "Background"), (230, "4 yd")],
                                                  "A")),
    # PS-21: a fat quarter offer with no fat quarter diagram in Cutting.
    "PS-21": lambda p: edit(p, "1 1/4 yd", "1 1/4 yd or 2 fat quarters"),
    # PS-22: a strip set step cites no figure.
    "PS-22": lambda p: edit(p, "Press toward B1. Fig. 1", "Press toward B1."),
    # PS-25: 12 in finished + 1/2 in = 12 1/2 in, not 13 in.
    "PS-25": lambda p: edit(p, 'Block 1 should measure 12 1/2" square.',
                            'Block 1 should measure 13" square.'),
    # PS-26: the center is 48 x 60 in finished, so it measures 48 1/2 x 60 1/2 in.
    "PS-26": lambda p: edit(p, '48 1/2" x 60 1/2"', '48" x 60"'),
    # PS-27: a numbered step per row.
    "PS-27": lambda p: edit(p, "Lay out the blocks in 5 rows", "1. Lay out the blocks in 5 rows"),
    # PS-28: MATH.md F4 trims the top and bottom borders to 60 1/2 in, not 60 in.
    "PS-28": lambda p: edit(p, 'each and trim to 60 1/2".', 'each and trim to 60".'),
    # PS-29: binding before quilting.
    "PS-29": lambda p: _move(p, 8, 5, 4),
    # PS-30: the miter step repeated in Borders.
    "PS-30": lambda p: edit(p, "Press toward the border. Fig. 6",
                            "Press toward the border and miter the corners. Fig. 6"),
    # PS-31: one dotted cell, but Before you begin counts none.
    "PS-31": lambda p: _replace_item(p, 9, 1, ("chart", {(0, 0)})),
    # PS-33: strip set 2 repeats strip set 1's B A B signature.
    "PS-33": lambda p: edit(p, "order: A2, B2, A2", "order: B2, A2, B2"),
    # PS-38: the test square is 60 pt, not 72 pt.
    "PS-38": lambda p: _replace_item(p, 1, 9, ("square", 60)),
    # PS-41: the coloring page carries no text but its footer.
    "PS-41": lambda p: _replace_item(p, 10, 0, ("gap", 20)),
    # PS-42: the footer is body text, drawn at 8 pt below the 10 pt minimum.
    "PS-42": lambda p: (p, {"footer_size": 8}),
    # PS-43: the render labels the width 62 in, a number the text never prints.
    "PS-43": lambda p: _replace_item(p, 0, 6, ("render", '62"', '72"')),
}


# Defects the self-review found, one regression case each: (check, old text, new text).
MORE_FAILING = [
    # PS-05: a piece total in a sentence (GAP-04 prints one today).
    ("PS-05", "3 fabrics, plus backing", "3 fabrics, plus backing. The top has 2479 pieces."),
    # PS-05: a model fabric id on the wrapped second line of a step.
    ("PS-05", "turn the binding to the back", "turn the r binding to the back"),
    # PS-09: a typed size needs the sentence that echoes it; "Finished size" is not one.
    ("PS-09", 'You asked for 60" x 72"; this pattern makes 60" x 72" with 4" finished squares.',
     "Sizes are in inches."),
    # PS-26: a segment of 3 strips of 4 in squares is 4 1/2 x (3 x 4 + 1/2) = 12 1/2 in long.
    ("PS-26", '4 1/2" x 12 1/2"', '4 1/2" x 16 1/2"'),
    # PS-26: a block of 3 x 3 squares of 4 in measures 12 1/2 in on both sides.
    ("PS-26", 'Block 1 should measure 12 1/2" square.', 'Block 1 should measure 12 1/2" x 16 1/2".'),
]


@pytest.mark.parametrize("check_id,old,new", MORE_FAILING)
def test_review_regressions_fail(tmp_path, check_id, old, new):
    got = results(tmp_path, edit(throw_pages(), old, new))[check_id]
    assert got.status == "fail", got.evidence


def test_ps25_make_counts_follow_the_block_census(tmp_path):
    # The model's 20 blocks are 10 nine-patch (Block 1, first in reading order) and 10 plain;
    # 12 + 8 still sums to the build line's 20, so only the census catches it.
    pages = _replace_item(throw_pages(), 5, 6, P("Make 12."))
    pages[5][12] = P("Make 8.")
    got = results(tmp_path, pages)["PS-25"]
    assert got.status == "fail" and "reading order" in got.evidence, got.evidence
    assert pc.block_census(throw_model()) == [10, 10]


def _swap_rows(pages):
    pages = copy.deepcopy(pages)
    rows = pages[1]
    rows[1] = ROW([(0, "A"), (20, "Blue"), (230, "4 1/4 yd")], "B")
    rows[2] = ROW([(0, "B"), (20, "Background"), (230, "1 1/4 yd")], "A")
    return pages


def _replace_item(pages, page, index, item):
    pages = copy.deepcopy(pages)
    pages[page][index] = item
    return pages


@pytest.mark.parametrize("check_id", sorted(FAILING))
def test_each_check_fails_on_its_broken_document(tmp_path, check_id):
    edited = FAILING[check_id](throw_pages())
    pages, render_kw = edited if isinstance(edited, tuple) else (edited, None)
    got = results(tmp_path, pages, render_kw=render_kw)
    assert got[check_id].status == "fail", got[check_id].evidence


def test_ps08_denylisted_name_fails(tmp_path):
    pages = throw_pages()
    assert results(tmp_path, pages, denylist=["Harbor Grid"])["PS-08"].status == "pass"
    got = results(tmp_path, pages, denylist=["lantern grid"])["PS-08"]
    assert got.status == "fail", got.evidence


def test_ps08_in_the_style_of_fails(tmp_path):
    pages = edit(throw_pages(), "3 fabrics, plus backing", "3 fabrics, in the style of a modern quilt")
    assert results(tmp_path, pages)["PS-08"].status == "fail"


def test_ps09_estimated_size_needs_the_photo_sentence(tmp_path):
    model = throw_model()
    model["size_basis"] = {"source": "default", "achieved_width": 480, "achieved_height": 576,
                           "rounding_step": 8, "confidence": 0.8}
    # The typed-size sentence does not say the size is estimated from the photo.
    assert results(tmp_path, throw_pages(), model)["PS-09"].status == "fail"
    pages = edit(throw_pages(), 'You asked for 60" x 72"; this pattern makes 60" x 72" with 4" '
                                'finished squares.',
                 'The size is estimated from the photo, assuming 4" finished squares.')
    # PATTERN-SPEC S1: the estimate names the 4 in (32 e) square it assumed.
    assert results(tmp_path, pages, model)["PS-09"].status == "pass"


def test_ps09_without_a_size_basis_does_not_apply(tmp_path):
    model = throw_model()
    del model["size_basis"]
    got = results(tmp_path, throw_pages(), model)["PS-09"]
    assert got.status == "pass" and "not applicable" in got.evidence


def test_ps21_offer_with_its_diagram_passes(tmp_path):
    pages = edit(throw_pages(), "1 1/4 yd", "1 1/4 yd or 2 fat quarters")
    pages[3] += [P("Fat quarter cutting diagram for B, Fig. 9."), ("fat_quarter",)]
    assert results(tmp_path, pages)["PS-21"].status == "pass"


def test_ps31_dots_match_the_uncertain_count(tmp_path):
    model = throw_model()
    model["provenance"] = {"source": "photo", "stage_confidence": {}}
    pages = edit(throw_pages(), "1. Read the whole pattern before cutting.",
                 "1. Read the whole pattern before cutting. (2) squares were read with low "
                 "confidence; each has a dot on the layout chart.")
    pages[9][1] = ("chart", {(0, 0), (4, 7)})
    got = results(tmp_path, pages, model)
    # Two dots drawn, two squares counted.
    assert got["PS-31"].status == "pass", got["PS-31"].evidence
    assert got["PS-15"].status == "pass", got["PS-15"].evidence
    pages[9][1] = ("chart", {(0, 0)})
    assert results(tmp_path, pages, model)["PS-31"].status == "fail"


def test_ps15_photo_read_needs_the_uncertain_count(tmp_path):
    model = throw_model()
    model["provenance"] = {"source": "photo", "stage_confidence": {}}
    got = results(tmp_path, throw_pages(), model)["PS-15"]
    assert got.status == "fail" and "low-confidence" in got.evidence


# ---------------------------------------------------------------- triangle units

# Units from MATH.md F14 with PATTERN-SPEC L-06's oversize-and-trim mode:
# - HST unit 1, F = 3 in: squares 3 + 1 = 4 in, trim to 3 1/2 in (as V-TRI-02 at F = 2).
#   Make 12, two per pair, so ceil(12 / 2) = 6 squares of each fabric. 4 in = 32 e:
#   floor(320 / 32) = 10 per strip, 1 strip, the last strip gives 6.
# - QST unit 1 and its mirror QST unit 2, F = 3 in: squares 3 + 1 1/2 = 4 1/2 in, trim to
#   3 1/2 in (V-TRI-04). The document declares unit 2 the mirror of unit 1, so the checker
#   counts one unit of each hand per pair, the Appendix A case of three-fabric star points (a
#   two-fabric hourglass would come out symmetric, and this synthetic document does not model
#   the third fabric). Make 4 of each takes 4 squares of each listed fabric; 36 e gives
#   floor(320 / 36) = 8 per strip.
# - Flying geese unit 1, 2 x 4 in: rectangle 2 1/2 x 4 1/2 in and two 2 1/2 in squares
#   (V-TRI-05); Make 4 takes 4 rectangles and 8 squares. The rectangle's 2 1/2 in strip
#   (20 e) wins over a 4 1/2 in strip (MATH.md F2: 1 x 20 e < 1 x 36 e), floor(320 / 36)
#   = 8 per strip; squares floor(320 / 20) = 16 per strip.
# - Snowball unit 1, F = 6 in, corner leg 2 in: base 6 1/2 in, four 2 1/2 in corners
#   (V-TRI-07); Make 2 takes 2 bases (floor(320 / 52) = 6 per strip) and 8 corners.


def units_pages():
    cover = [P("Starling Units", size=24), P("Unit test document")]
    requirements = [
        P("Fabric requirements", size=14),
        P("Fabric amounts are rounded up to the next 1/4 yd, and top fabrics include 10 percent "
          'extra. Strips assume 40" of usable width (WOF). Backing assumes 42" wide fabric.'),
        P('Supplies: rotary cutter and mat, 6" x 24" ruler, neutral thread, a marking tool for '
          "diagonal lines and a square ruler with a 45 degree line."),
    ]
    cutting = [
        P("Cutting", size=14),
        ("fabric", "A", "Background"),
        P('1. Cut (1) 4" x WOF strips.'),
        P('A1: subcut (1) strip into (6) 4" squares, 10 per strip, for HST unit 1. The last '
          'strip gives (6).', indent=20),
        P('2. Cut (1) 4 1/2" x WOF strips.'),
        P('A2: subcut (1) strip into (4) 4 1/2" squares, 8 per strip, for QST unit 1. The last '
          'strip gives (4).', indent=20),
        P('3. Cut (1) 2 1/2" x WOF strips.'),
        P('A3: subcut (1) strip into (8) 2 1/2" squares, 16 per strip, for Flying geese unit 1. '
          'The last strip gives (8).', indent=20),
        P('4. Cut (1) 6 1/2" x WOF strips.'),
        P('A4: subcut (1) strip into (2) 6 1/2" squares, 6 per strip, for Snowball unit 1. The '
          'last strip gives (2).', indent=20),
        ("fabric", "B", "Blue"),
        P('1. Cut (1) 4" x WOF strips.'),
        P('B1: subcut (1) strip into (6) 4" squares, 10 per strip, for HST unit 1. The last '
          'strip gives (6).', indent=20),
        P('2. Cut (1) 4 1/2" x WOF strips.'),
        P('B2: subcut (1) strip into (4) 4 1/2" squares, 8 per strip, for QST unit 1. The last '
          'strip gives (4).', indent=20),
        P('3. Cut (1) 2 1/2" x WOF strips.'),
        P('B3: subcut (1) strip into (4) 2 1/2" x 4 1/2" rectangles, 8 per strip, for Flying '
          'geese unit 1. The last strip gives (4).', indent=20),
        P('4. Cut (1) 2 1/2" x WOF strips.'),
        P('B4: subcut (1) strip into (8) 2 1/2" squares, 16 per strip, for Snowball unit 1. The '
          'last strip gives (8).', indent=20),
    ]
    units = [
        P("Making the units", size=14),
        P("No block repeats, so you sew the quilt row by row from the layout chart."),
        P("HST unit 1", size=12),
        P("A1 (1)"),
        P("B1 (1)"),
        P("1. Pair an A1 and a B1 square RST and draw a diagonal line on the back of A1. Fig. 1"),
        P('2. Sew 1/4" from the line on both sides, cut on the line and press toward B. Fig. 2'),
        P('3. Trim each unit with the 45 degree line on the seam. Fig. 3'),
        P('Trim to 3 1/2" square.'),
        P("Make 12."),
        P("QST unit 1", size=12),
        P("A2 (1)"),
        P("B2 (1)"),
        P("1. Make two HSTs from the pair without trimming and press them open. Fig. 4"),
        P("2. Place them RST with contrasting fabrics facing, sew on both sides of the crossing "
          "diagonal and cut. Fig. 5"),
        P('Trim to 3 1/2" square.'),
        P("Make 4."),
        P("QST unit 2", size=12),
        P("QST unit 2 is the mirror image of unit 1, made in the same steps. Do not mix the "
          "two."),
        P('Trim to 3 1/2" square.'),
        P("Make 4."),
        P("Flying geese unit 1", size=12),
        P("B3 (1)"),
        P("A3 (2)"),
        P("1. Draw a diagonal line on each A3 square and sew one to an end of B3; press. Fig. 6"),
        P("2. Repeat at the other end with the line mirrored and press. Fig. 7"),
        P('Unit should measure 2 1/2" x 4 1/2".'),
        P("Make 4."),
        P("Snowball unit 1", size=12),
        P("A4 (1)"),
        P("B4 (4)"),
        P("1. Draw a diagonal line on each B4 square, sew one to each corner of A4 and press "
          "toward the corner. Fig. 8"),
        P('Unit should measure 6 1/2" square.'),
        P("Make 2."),
    ]
    return [cover, requirements, cutting, units]


UNIT_CHECKS = ("PS-06", "PS-14", "PS-19", "PS-22", "PS-23", "PS-24")


def test_triangle_units_pass(tmp_path):
    got = results(tmp_path, units_pages(), only=UNIT_CHECKS)
    assert {k: r.status for k, r in got.items()} == {k: "pass" for k in UNIT_CHECKS}, \
        {k: r.evidence for k, r in got.items()}


UNIT_FAILING = {
    # PS-06: a rectangle written long side first.
    "PS-06": ('2 1/2" x 4 1/2" rectangles', '4 1/2" x 2 1/2" rectangles'),
    # PS-14: triangle units need a marking tool in the supplies.
    "PS-14": ("a marking tool for diagonal lines and ", ""),
    # PS-19: ceil(14 / 2) = 7 pairs need 7 squares of each fabric; 6 are cut.
    "PS-19": ("Make 12.", "Make 14."),
    # PS-22: an HST step cites no figure.
    "PS-22": ("on the seam. Fig. 3", "on the seam."),
    # PS-23: a 4 1/4 in square is neither the exact 3 7/8 in nor the trimmed 4 in (V-TRI-02).
    "PS-23": ('(6) 4" squares, 10 per strip, for HST', '(6) 4 1/4" squares, 10 per strip, for HST'),
    # PS-24: the mirror unit loses its warning.
    "PS-24": (" Do not mix the two.", ""),
}


@pytest.mark.parametrize("check_id", sorted(UNIT_FAILING))
def test_each_unit_check_fails_on_its_broken_document(tmp_path, check_id):
    old, new = UNIT_FAILING[check_id]
    got = results(tmp_path, edit(units_pages(), old, new), only=(check_id,))
    assert got[check_id].status == "fail", got[check_id].evidence


def test_ps23_flying_geese_rectangle_must_match(tmp_path):
    # V-TRI-05: a 2 x 4 in goose needs a 2 1/2 x 4 1/2 in rectangle, not 2 1/2 x 4 in.
    pages = edit(units_pages(), '2 1/2" x 4 1/2" rectangles', '2 1/2" x 4" rectangles')
    assert results(tmp_path, pages, only=("PS-23",))["PS-23"].status == "fail"


# ---------------------------------------------------------------- PS-39, CLI, imports


def test_ps39_runs_only_with_a_reference_folder(tmp_path):
    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "notes.txt").write_text("A different text about something else entirely, with no "
                                    "shared run of words.", encoding="utf-8")
    pages = throw_pages()
    assert results(tmp_path, pages)["PS-39"].status == "not run"
    assert results(tmp_path, pages, references=refs)["PS-39"].status == "pass"
    # Ten consecutive words of the pattern's own assembly text.
    (refs / "copy.json").write_text(json.dumps({"page": "Sew the blocks in each row together, "
                                                        "pressing toward Block 2, and join"}),
                                    encoding="utf-8")
    got = results(tmp_path, pages, references=refs)["PS-39"]
    # Counts only: no matched word reaches the evidence (R9), in either case.
    assert got.status == "fail" and "sew the blocks" not in got.evidence.lower()


def test_ps39_reference_names_fail(tmp_path):
    refs = tmp_path / "refs"
    refs.mkdir()
    got = results(tmp_path, throw_pages(), references=refs,
                  reference_names=["Lantern Grid"])["PS-39"]
    assert got.status == "fail"


def test_cli_prints_one_line_per_check(tmp_path, capsys):
    pdf = tmp_path / "pattern.pdf"
    model = tmp_path / "model.json"
    render(throw_pages(), pdf)
    model.write_text(json.dumps(throw_model()), encoding="utf-8")
    assert pc.main([str(pdf), str(model)]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in out[:-1]] == IMPLEMENTED
    assert all(line.split()[1] == "pass:" for line in out[:-1] if not line.startswith("PS-39"))
    assert [line for line in out if line.startswith("PS-39")][0].startswith("PS-39 not run:")
    assert out[-1] == "placeholder frames: 0"
    render(edit(throw_pages(), "Make 3.", "Make 4."), pdf)
    assert pc.main([str(pdf), str(model)]) == 1
    assert "PS-19 fail:" in capsys.readouterr().out


def test_placeholder_frames_are_counted(tmp_path):
    pdf = tmp_path / "pattern.pdf"
    pages = throw_pages()
    pages[5].append(P("Figure placeholder: block figure not drawn yet"))
    render(pages, pdf)
    assert pc.placeholder_frames(pdf, throw_model()) == [6]


def test_module_loads_without_pypdf(monkeypatch):
    monkeypatch.setitem(sys.modules, "pypdf", None)
    spec = importlib.util.spec_from_file_location("pattern_checks_fresh",
                                                  HERE / "pattern_checks.py")
    module = importlib.util.module_from_spec(spec)
    # dataclass() resolves annotations through sys.modules, so register the fresh copy.
    monkeypatch.setitem(sys.modules, "pattern_checks_fresh", module)
    spec.loader.exec_module(module)
    assert "PS-11" in module.CHECKS
    with pytest.raises(ImportError):
        module.read_pdf(HERE / "missing.pdf")


def test_checker_imports_nothing_from_qrep():
    tree = ast.parse((HERE / "pattern_checks.py").read_text(encoding="utf-8"))
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not [n for n in names if n.split(".")[0] == "qrep"]


# ---------------------------------------------------------------- MATH.md recomputation


def sized_model(width: int, height: int, cell: int = 4) -> dict:
    """A plain quilt of the given finished size in eighths, no borders, MATH.md defaults."""
    model = throw_model()
    model["center"] = {"kind": "grid", "rows": height // cell, "cols": width // cell,
                       "cell_size": cell,
                       "cells": [["c"] * (width // cell) for _ in range(height // cell)]}
    model["borders"] = []
    return model


def fixture_model() -> dict:
    return json.loads((HERE / "fixtures" / "double_irish_chain.json").read_text("utf-8"))


def test_binding_strips_match_math_vectors():
    # V-BIND-13: T = 2 (60 + 72) + 10 = 274 in; ceil(274 / 37.5) = 8.
    assert pc.binding_strips(throw_model()) == 8
    # V-BIND-09, the fixture at its stored U = 42 in: ceil(2720 / (336 - 20)) = 9.
    assert pc.binding_strips(fixture_model()) == 9


def test_backing_plan_matches_math_vectors():
    # V-BACK-02 and V-WIDE-02 (throw 60 x 72): horizontal, 2 panels of 68 in (544 e),
    # 17 qy = 1224 e (4 1/4 yd); wide 9 qy = 648 e (2 1/4 yd); batting 68 x 80 in.
    plan = pc.backing_plan(throw_model())
    assert (plan["panels"], plan["length"], plan["seams"], plan["yards"], plan["wide"]) == \
        (2, 544, "across", 1224, 648)
    assert plan["batting"] == (544, 640)
    # V-BACK-09 and V-WIDE-08 (fixture 75 x 90): vertical, 2 panels of 98 in (784 e),
    # 23 qy = 1656 e (5 3/4 yd); wide 10 qy = 720 e (2 1/2 yd).
    plan = pc.backing_plan(fixture_model())
    assert (plan["panels"], plan["length"], plan["seams"], plan["yards"], plan["wide"]) == \
        (2, 784, "along", 1656, 720)
    # V-BACK-08 and V-WIDE-05 (king 110 x 108): vertical, 3 panels of 116 in (928 e),
    # 40 qy = 2880 e (10 yd); no 108 in line.
    plan = pc.backing_plan(sized_model(880, 864))
    assert (plan["panels"], plan["length"], plan["seams"], plan["yards"], plan["wide"]) == \
        (3, 928, "along", 2880, None)


def test_batting_package_matches_math_vectors():
    # V-BATT-03: 68 x 80 in -> twin. V-BATT-08: 100 1/2 x 123 in -> king, turned.
    # V-BATT-10: 110 1/2 x 128 in -> none ("larger than a king package").
    assert pc.batting_package(544, 640) == ("twin", 72, 90)
    assert pc.batting_package(804, 984) == ("king", 124, 120)
    assert pc.batting_package(884, 1024) is None


def test_border_plan_matches_math_vectors():
    # V-BORD-01 at the fixture's configured U = 42 in: 4 1/4 in strips (34 e), sides 83 in
    # (664 e) and top and bottom 75 1/2 in (604 e), k = 2 each, 8 strips.
    assert pc.border_plan(fixture_model()) == [
        {"width": 34, "side": 664, "top": 604, "strips": 8, "k_side": 2, "k_top": 2}]
    # V-BORD-03: center 60 x 72, bands of 2 and 5 in at U = 40.
    model = sized_model(480, 576)
    model["borders"] = [{"fabric_id": "c", "width": 16}, {"fabric_id": "b", "width": 40}]
    assert pc.border_plan(model) == [
        {"width": 20, "side": 580, "top": 516, "strips": 8, "k_side": 2, "k_top": 2},
        {"width": 44, "side": 612, "top": 596, "strips": 8, "k_side": 2, "k_top": 2}]
    # V-BORD-04: center 4 x 4, band 1 in: both pairs fit one strip each, 2 strips.
    model = sized_model(32, 32)
    model["borders"] = [{"fabric_id": "c", "width": 8}]
    assert pc.border_plan(model) == [
        {"width": 12, "side": 36, "top": 52, "strips": 2, "k_side": 1, "k_top": 1}]


def test_lengths_parse_and_format_in_eighths():
    # MATH.md section 1.2: 1 in = 8 e.
    assert pc.eighths("12 1/2") == 100 and pc.eighths("3/4") == 6 and pc.eighths("40") == 320
    # 3/16 is no whole eighth. 2/4 still reads as 4 e; PS-06 is what rejects the form.
    assert pc.eighths("3/16") is None and pc.eighths("2/4") == 4
    assert pc.fmt(52) == "6 1/2" and pc.fmt(6) == "3/4" and pc.fmt(320) == "40"
    # 17 qy x 72 e = 1224 e = 34 eighths of a yard = 4 1/4 yd.
    assert pc.fmt_yd(1224) == "4 1/4 yd"
    assert pc.normalize('Cut (8) 6 1/2"  x\nWOF strips.') == "Cut (8) 6 1/2 x WOF strips."


# ---------------------------------------------------------------- correctness review regressions


def _split_item(pages, page, old, first, second, indent=0):
    """One paragraph drawn as two physical lines, the way a long line wraps."""
    pages = copy.deepcopy(pages)
    items = pages[page]
    i = next(k for k, it in enumerate(items) if it[0] == "p" and it[1] == old)
    items[i:i + 1] = [P(first, indent=indent), P(second, indent=indent)]
    return pages


def _s4_wordings(pages):
    # PATTERN-SPEC S4 words strip-set fabric "Set aside (N) W x WOF strips (A1) for strip
    # set 1." and binding "(N) 2 1/2 x WOF strips for binding.", neither starting with Cut.
    pages = edit(pages, 'Cut (6) 4 1/2" x WOF strips. Set aside the strips (B1)',
                 'Set aside (6) 4 1/2" x WOF strips (B1)')
    pages = edit(pages, 'Cut (2) 4 1/2" x WOF strips. Set aside the strips (B2)',
                 'Set aside (2) 4 1/2" x WOF strips (B2)')
    return _replace_item(pages, 3, 11, P('(8) 2 1/2" x WOF strips for binding.'))


def test_s4_set_aside_and_binding_wordings_pass(tmp_path):
    got = results(tmp_path, _s4_wordings(throw_pages()))
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


def test_ps20_checks_a_fabric_cut_only_by_set_aside_steps(tmp_path):
    # Fabric B: (6 + 2) x 36 e = 288 e of strips; MATH.md F5 purchase ceil(288 x 110 / 100)
    # = 317 e; ceil(317 / 72) = 5 qy = 1 1/4 yd (V-UNIT-02), so 1 yd is short.
    pages = edit(_s4_wordings(throw_pages()), "1 1/4 yd", "1 yd")
    got = results(tmp_path, pages)["PS-20"]
    assert got.status == "fail" and "fabric B top" in got.evidence, got.evidence


def test_ps20_fails_a_row_whose_fabric_cuts_no_strips(tmp_path):
    # Fabric C keeps its heading and its binding row but cuts no binding strips.
    got = results(tmp_path, _replace_item(throw_pages(), 3, 11, ("gap", 0)))["PS-20"]
    assert got.status == "fail" and "C binding" in got.evidence, got.evidence


def test_a_piece_longer_than_the_strip_width_fails_without_a_crash(tmp_path):
    # 42 1/2 in = 340 e > U = 320 e: a 12 1/2 in strip yields floor(320 / 340) = 0 such
    # pieces, and MATH.md F2 rules that orientation out when the long side exceeds U.
    pages = edit(throw_pages(), '(10) 12 1/2" squares, 3 per strip',
                 '(10) 12 1/2" x 42 1/2" rectangles, 3 per strip')
    got = results(tmp_path, pages)
    assert list(got) == IMPLEMENTED
    assert got["PS-20"].status == "fail" and "42 1/2" in got["PS-20"].evidence
    assert got["PS-33"].status == "fail" and "A3" in got["PS-33"].evidence


def test_a_size_outside_eighths_fails_without_a_crash(tmp_path):
    # 12 1/3 in is no whole eighth (C-09), so no check can compute with it.
    pages = edit(throw_pages(), '(10) 12 1/2" squares', '(10) 12 1/3" squares')
    pages = edit(pages, 'Cut (4) 12 1/2" x WOF', 'Cut (4) 12 1/3" x WOF')
    got = results(tmp_path, pages)
    assert list(got) == IMPLEMENTED
    for check_id in ("PS-06", "PS-20", "PS-33"):
        assert got[check_id].status == "fail", (check_id, got[check_id].evidence)


def test_a_check_that_raises_is_reported_as_a_fail(tmp_path, monkeypatch):
    def broken(doc, opts):
        raise ValueError("bad input")

    monkeypatch.setitem(pc.CHECKS, "PS-01", broken)
    got = results(tmp_path, throw_pages())
    assert list(got) == IMPLEMENTED
    assert got["PS-01"].status == "fail" and "ValueError: bad input" in got["PS-01"].evidence
    assert got["PS-02"].status == "pass"


def test_a_step_that_wraps_before_a_count_and_label_stays_one_step(tmp_path):
    # The continuation line starts "(4) B4", which alone would read as a piece list line.
    pages = _split_item(units_pages(), 3,
                        "1. Draw a diagonal line on each B4 square, sew one to each corner of A4 "
                        "and press toward the corner. Fig. 8",
                        "1. Draw a diagonal line on the back of each of the",
                        "(4) B4 squares, sew one to each corner of A4 and press toward the "
                        "corner. Fig. 8")
    got = results(tmp_path, pages, only=UNIT_CHECKS)
    assert {k: r.status for k, r in got.items()} == {k: "pass" for k in UNIT_CHECKS}, \
        {k: r.evidence for k, r in got.items()}


def test_a_subcut_that_wraps_before_its_shape_word_parses(tmp_path):
    pages = _split_item(throw_pages(), 3,
                        'A3: subcut (4) strips into (10) 12 1/2" squares, 3 per strip. The last '
                        'strip gives (1).',
                        'A3: subcut (4) strips into (10) 12 1/2"',
                        'squares, 3 per strip. The last strip gives (1).', indent=20)
    got = results(tmp_path, pages)
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


def test_body_text_just_below_a_figure_stays_body_text(tmp_path):
    pages = copy.deepcopy(throw_pages())
    # Strip set 1's figure drawn at the left margin, as a reportlab Drawing would be, with the
    # checkpoint baseline 30 - 16 = 14 pt below its bottom edge: inside the 18 pt band that
    # small figure labels get.
    assert pages[4][8] == FIG("BBB", "AAA", "BBB")
    pages[4][8:9] = [("fig_left", ("BBB", "AAA", "BBB")), ("gap", -16)]
    got = results(tmp_path, pages)
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


def test_a_body_line_above_the_footer_is_not_footer(tmp_path):
    # The footer baseline is y = 30; Block 2's "Make 10." sits 20 pt above it, at y = 50.
    assert throw_pages()[5][12] == P("Make 10.")
    got = results(tmp_path, _replace_item(throw_pages(), 5, 12, ("at", "Make 10.", 50)))
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


def test_alternate_rows_is_not_an_alternative_method(tmp_path):
    pages = edit(throw_pages(), "pressing the row seams in one direction",
                 "pressing the seams of alternate rows in opposite directions")
    got = results(tmp_path, pages)["PS-33"]
    assert got.status == "pass", got.evidence
    for offer in ("Alternatively, sew", "For an alternate approach, sew"):
        pages = edit(throw_pages(), "Sew the blocks in each row together,",
                     f"{offer} the blocks in each row together,")
        assert results(tmp_path, pages)["PS-33"].status == "fail", offer


def test_ps28_border_pieces_that_fit_one_strip_need_no_join(tmp_path):
    # V-BORD-04: center 4 x 4 in, one 1 in band. Strips 1 + 1/2 = 1 1/2 in; sides 4 + 1/2
    # = 4 1/2 in; top and bottom 4 + 2 x 1 + 1/2 = 6 1/2 in. Both fit 40 in, so k = 1: the
    # sides come from one strip (floor(40 / 4 1/2) = 8 >= 2) and the top and bottom from
    # another (floor(40 / 6 1/2) = 6 >= 2), 2 strips in all.
    model = sized_model(32, 32)
    model["borders"] = [{"fabric_id": "c", "width": 8}]

    def pages(side, top):
        return [[P("Tiny Border", size=24)],
                [P("Cutting", size=14), ("fabric", "A", "Background"),
                 P(f'1. Cut (2) 1 1/2" x WOF strips. For the side borders, cut (2) {side} from '
                   f'one strip. For the top and bottom borders, cut (2) {top} from the other '
                   f'strip.')],
                [P("Borders", size=14),
                 P("1. Measure the quilt through its center and trim the borders to match if "
                   "needed. Sew the side borders first, then the top and bottom borders. Press "
                   "toward the border.")]]

    # Both the "pieces L long" and the S4 "W x L rectangles" wordings name the length.
    for side, top in (('pieces 4 1/2" long', 'pieces 6 1/2" long'),
                      ('1 1/2" x 4 1/2" rectangles', '1 1/2" x 6 1/2" rectangles')):
        got = results(tmp_path, pages(side, top), model, only=("PS-28",))["PS-28"]
        assert got.status == "pass", (side, got.evidence)
    got = results(tmp_path, pages('pieces 4 1/2" long', 'pieces 6" long'), model,
                  only=("PS-28",))["PS-28"]
    assert got.status == "fail", got.evidence


def test_a_long_name_that_wraps_on_the_cover_passes(tmp_path):
    name = "Lantern Grid on a Quiet Winter Evening by the Northern Harbor Wall"
    # The cover draws the name at 24 pt in a 500 pt column, where it takes two lines.
    assert len(simpleSplit(name, "Helvetica", 24, 500)) == 2
    model = throw_model()
    model["metadata"]["name"] = name
    pages = _replace_item(throw_pages(), 0, 0, P(name, size=24))
    got = results(tmp_path, pages, model, render_kw={"name": name})
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


def test_a_same_size_line_under_the_name_is_not_part_of_it(tmp_path):
    # The finished size set at the name's 24 pt: the footer never prints it after the name.
    pages = _replace_item(throw_pages(), 0, 1, P('Finished size 60" x 72"', size=24))
    got = results(tmp_path, pages)
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


def test_a_caption_line_before_a_piece_list_keeps_the_list(tmp_path):
    # Only a step or a subcut runs on into the next line, so an unpunctuated caption above
    # Block 2's piece list leaves "A3 (1)" a piece line.
    pages = copy.deepcopy(throw_pages())
    assert pages[5][8] == P("A3 (1)")
    pages[5].insert(8, P("Pieces for one block"))
    got = results(tmp_path, pages)
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


@pytest.mark.parametrize("layout", ["name above", "version above"])
def test_a_footer_on_two_lines_passes(tmp_path, layout):
    # G-02 asks for the name, "page N of M" and a version line; one sits 12 pt above.
    got = results(tmp_path, throw_pages(), render_kw={"footer_layout": layout})
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


def test_render_labels_at_body_size_are_still_figure_labels(tmp_path):
    # 12 pt dimension labels just outside the render: 60 in matches the text, 62 in does not.
    pages = _replace_item(throw_pages(), 0, 6, ("render", '60"', '72"', 12))
    got = results(tmp_path, pages)
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}
    pages = _replace_item(throw_pages(), 0, 6, ("render", '62"', '72"', 12))
    assert results(tmp_path, pages)["PS-43"].status == "fail"


def test_a_binding_step_that_wraps_before_its_strip_count_stays_one_step(tmp_path):
    # Outside Cutting, "(8) 2 1/2 x WOF strips for binding" starts no cut of its own.
    pages = _split_item(throw_pages(), 8,
                        "4. Join the (8) binding strips with diagonal seams and press them open. "
                        'Press the long strip in half lengthwise. Sew it to the front, stop 1/4" '
                        "from each corner and fold to miter. Join the two ends, turn the binding "
                        "to the back and stitch it by hand. Fig. 8",
                        "4. Join the",
                        '(8) 2 1/2" x WOF strips for binding with diagonal seams and press them '
                        'open. Press the long strip in half lengthwise. Sew it to the front, stop '
                        '1/4" from each corner and fold to miter. Join the two ends, turn the '
                        "binding to the back and stitch it by hand. Fig. 8")
    got = results(tmp_path, pages)
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


def test_a_step_that_wraps_after_fig_keeps_its_citation(tmp_path):
    # The line breaks between "Fig." and its number, so the next line opens "1. Draw".
    pages = _split_item(units_pages(), 3,
                        "1. Pair an A1 and a B1 square RST and draw a diagonal line on the back "
                        "of A1. Fig. 1",
                        "1. Pair an A1 and a B1 square RST as shown in Fig.",
                        "1. Draw a diagonal line on the back of A1.")
    got = results(tmp_path, pages, only=UNIT_CHECKS)
    assert {k: r.status for k, r in got.items()} == {k: "pass" for k in UNIT_CHECKS}, \
        {k: r.evidence for k, r in got.items()}


# ---------------------------------------------------------------- review 2: merged strip sets

# PATTERN-SPEC section 3 worked example (the DIC fixture: 1 1/2 in finished cells, 12 e), at
# the U = 40 in (320 e) the example uses; the stored fixture keeps U = 42 in (MATH.md 1.3), so
# the model below sets 320. Letters by C-02 area order: A cream, B blue (fixture ids c and
# b). Cut width = finished width + 1/2 in (MATH.md F1); M-04 merges a same-fabric run into
# one strip.
# - Strip set 1 (Block A row 1, b b c b b): B 3 + 1/2 = 3 1/2 in, A 1 1/2 + 1/2 = 2 in,
#   B 3 1/2 in. Segment (S5.5): (1 1/2 + 1/2) x (3 + 1 1/2 + 3 + 1/2) = 2 x 8 in.
# - Strip set 2 (Block A row 3, c b b b c): A 2 in, B 4 1/2 + 1/2 = 5 in, A 2 in. Segment
#   2 x (1 1/2 + 4 1/2 + 1 1/2 + 1/2) = 2 x 8 in.
# - Strip set 3 (Block B end rows, b c c c b): B 2 in, A 5 in, B 2 in; segment 2 x 8 in.
# - Sets 1 and 3 share the letters B A B, but their widths differ: (B 3 1/2, A 2, B 3 1/2)
#   against (B 2, A 5, B 2), so M-05 counts two signatures.
# - MATH.md F3 and V-UNIT-05: per set floor(320 / 16) = 20. Set 1: 2 per Block A x 50 = 100
#   segments, ceil(100 / 20) = 5 sets; set 2: 1 x 50 = 50, ceil(50 / 20) = 3; set 3: 2 per
#   Block B x 49 = 98, ceil(98 / 20) = 5 (the worked example's 5, 3 and 5).
# - Strips, sets x count in the sequence (F3): B1 5 x 2 = 10, A1 5 x 1 = 5; A2 3 x 2 = 6,
#   B2 3 x 1 = 3; B3 5 x 2 = 10, A3 5 x 1 = 5. Cream: 5 + 6 = 11 strips of 2 in and 5 of
#   5 in, the worked example's "(5 + 3 x 2) = (11) 2 in strips and (5) 5 in strips".
# - Quilt center 45 x 55 cells of 1 1/2 in = 67 1/2 x 82 1/2 in (V-BORD-01); checkpoint
#   67 1/2 + 1/2 = 68 by 82 1/2 + 1/2 = 83 in.

DIC_CHECKS = ("PS-16", "PS-17", "PS-18", "PS-19", "PS-22", "PS-26", "PS-33")


def dic_model() -> dict:
    model = fixture_model()
    model["settings"]["wof"] = 320
    # The figures are drawn in the test colors, so the palette carries them.
    model["palette"]["fabrics"] = [{"id": "c", "name": "Cream", "color": COLORS["A"]},
                                   {"id": "b", "name": "Blue", "color": COLORS["B"]}]
    return model


def _strip_set(n, pieces, order, press, need, sets, fig, segment='2" x 8"'):
    return [P(f"Strip set {n}", size=12), *[P(p) for p in pieces],
            P(f"1. Sew the strips lengthwise in this order: {order}. Press toward {press}. "
              f"Fig. {n}"),
            P(f'2. Crosscut ({need}) 2" segments, 20 per set. Fig. {n}'),
            FIG(*fig),
            P(f"Each segment should measure {segment}."),
            P(f"Make {sets}.")]


def dic_strip_pages(segment1='2" x 8"', a1='2"', b1='3 1/2"'):
    cutting = [
        P("Cutting", size=14),
        ("fabric", "A", "Cream"),
        P(f"1. Cut (5) {a1} x WOF strips. Set aside the strips (A1) for strip set 1."),
        P('2. Cut (6) 2" x WOF strips. Set aside the strips (A2) for strip set 2.'),
        P('3. Cut (5) 5" x WOF strips. Set aside the strips (A3) for strip set 3.'),
        ("fabric", "B", "Blue"),
        P(f"1. Cut (10) {b1} x WOF strips. Set aside the strips (B1) for strip set 1."),
        P('2. Cut (3) 5" x WOF strips. Set aside the strips (B2) for strip set 2.'),
        P('3. Cut (10) 2" x WOF strips. Set aside the strips (B3) for strip set 3.'),
    ]
    units = [P("Making the units", size=14),
             P("Two blocks repeat across the quilt, so you sew long strips together and cut "
               "them into segments instead of cutting every square."),
             *_strip_set(1, ("B1 (2)", "A1 (1)"), "B1, A1, B1", "B1", 100, 5,
                         ("BBBB", "AAAA", "BBBB"), segment1),
             *_strip_set(2, ("A2 (2)", "B2 (1)"), "A2, B2, A2", "B2", 50, 3,
                         ("AAAA", "BBBB", "AAAA"))]
    more_units = _strip_set(3, ("B3 (2)", "A3 (1)"), "B3, A3, B3", "B3", 98, 5,
                            ("BBBB", "AAAA", "BBBB"))
    assembly = [P("Quilt assembly", size=14), P('The quilt center should measure 68" x 83".')]
    return [[P("Chain Study", size=24)], cutting, units, more_units, assembly]


def test_dic_strip_sets_pass_the_strip_set_checks(tmp_path):
    got = results(tmp_path, dic_strip_pages(), dic_model(), only=DIC_CHECKS)
    assert {k: r.status for k, r in got.items()} == {k: "pass" for k in DIC_CHECKS}, \
        {k: r.evidence for k, r in got.items()}


def test_ps26_a_merged_strip_set_segment_sums_its_strip_widths(tmp_path):
    got = results(tmp_path, dic_strip_pages(), dic_model(), only=("PS-26",))["PS-26"]
    assert got.status == "pass", got.evidence
    # One square per strip would give 2 x (3 x 1 1/2 + 1/2) = 2 x 5 in, which set 1's merged
    # strips (3 + 1 1/2 + 3 + 1/2 = 8 in long) rule out.
    got = results(tmp_path, dic_strip_pages(segment1='2" x 5"'), dic_model(),
                  only=("PS-26",))["PS-26"]
    assert got.status == "fail" and "Strip set 1" in got.evidence, got.evidence


def test_ps26_each_strip_must_be_whole_squares_wide(tmp_path):
    # B1 cut 3 3/4 in (30 e) finishes 30 - 4 = 26 e and A1 cut 1 1/2 in (12 e) finishes 8 e;
    # neither is a whole number of 12 e squares, though the length still adds up:
    # 26 + 8 + 26 + 4 = 64 e = 8 in, the printed 2 x 8 in.
    pages = dic_strip_pages(a1='1 1/2"', b1='3 3/4"')
    got = results(tmp_path, pages, dic_model(), only=("PS-26",))["PS-26"]
    assert got.status == "fail" and "not whole" in got.evidence and "B1" in got.evidence, \
        got.evidence


def test_ps33_strip_sets_with_the_same_letters_but_other_widths_differ(tmp_path):
    # Sets 1 and 3 both read B A B; M-05's signature carries the widths, so they differ. The
    # throw's FAILING PS-33 case (both sets 4 1/2 in B A B) still repeats.
    got = results(tmp_path, dic_strip_pages(), dic_model(), only=("PS-33",))["PS-33"]
    assert got.status == "pass", got.evidence


# ---------------------------------------------------------------- review 2: mirror QSTs


def test_a_mirror_pair_counts_each_hand(tmp_path):
    # C-11 writes a mirror pair as "Make 8 (4 of each)": 8 units, 4 of each hand. S5.2 and
    # Appendix A: one pair of starting squares (one A2, one B2) gives two QSTs, one of each
    # hand, so 4 of each hand take 4 pairs, the (4) A2 and (4) B2 that Cutting cuts. QST
    # unit 2, the mirror, makes its own hand: 4, equal to unit 1's 4 of each.
    pages = units_pages()
    assert pages[3][10] == P("QST unit 1", size=12) and pages[3][16] == P("Make 4.")
    pages = _replace_item(pages, 3, 16, P("Make 8 (4 of each)."))
    got = results(tmp_path, pages, only=UNIT_CHECKS)
    assert {k: r.status for k, r in got.items()} == {k: "pass" for k in UNIT_CHECKS}, \
        {k: r.evidence for k, r in got.items()}
    # 8 is not 2 x 3, so "Make 8 (3 of each)" does not add up.
    pages = _replace_item(pages, 3, 16, P("Make 8 (3 of each)."))
    assert results(tmp_path, pages, only=("PS-24",))["PS-24"].status == "fail"


# ---------------------------------------------------------------- review 2: figure labels


def test_a_small_step_below_a_figure_is_body_text(tmp_path):
    # L-10 (PS-42): body text is at least 10 pt. Strip set 1's step 2 set at 8 pt with its
    # baseline 30 - 16 = 14 pt below the figure's bottom edge lies inside the 18 pt label band,
    # but a step sentence is never a label, so it is 8 pt body text.
    pages = copy.deepcopy(throw_pages())
    step = '2. Crosscut (20) 4 1/2" segments, 8 per set. Fig. 1'
    assert pages[4][7] == P(step) and pages[4][8] == FIG("BBB", "AAA", "BBB")
    pages[4][7:9] = [("fig_left", ("BBB", "AAA", "BBB")), ("gap", -16), P(step, size=8)]
    got = results(tmp_path, pages)
    assert got["PS-42"].status == "fail", got["PS-42"].evidence
    assert "body '2. Crosscut" in got["PS-42"].evidence, got["PS-42"].evidence
    assert {k for k, r in got.items() if r.status == "fail"} == {"PS-42"}, \
        {k: r.evidence for k, r in got.items() if r.status == "fail"}


def test_a_small_range_label_beside_the_chart_is_a_figure_label(tmp_path):
    # S10 labels a chart part "Rows a to b, columns c to d". At 7 pt (the L-10 figure-label
    # minimum), 14 pt above the chart, it is a figure label; the throw's single part covers
    # rows 1 to 15 and columns 1 to 12.
    pages = _replace_item(throw_pages(), 9, 1, ("chart", (), "Rows 1 to 15, columns 1 to 12"))
    got = results(tmp_path, pages)
    assert {k: r.evidence for k, r in got.items() if r.status == "fail"} == {}


# ---------------------------------------------------------------- review 2: PS-39 fails closed


def test_ps39_fails_on_an_empty_reference_folder(tmp_path):
    refs = tmp_path / "refs"
    refs.mkdir()
    got = results(tmp_path, throw_pages(), references=refs)["PS-39"]
    assert got.status == "fail" and "no reference text" in got.evidence, got.evidence


def test_ps39_fails_on_a_folder_it_cannot_read(tmp_path):
    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "notes.pdf").write_bytes(b"%PDF-1.4 Sew the blocks in each row together")
    got = results(tmp_path, throw_pages(), references=refs)["PS-39"]
    assert got.status == "fail" and "1 of 1 reference files" in got.evidence, got.evidence
    # Counts only: no file name and no reference word reaches the evidence.
    for secret in ("notes", ".pdf", "sew the blocks"):
        assert secret not in got.evidence.lower(), got.evidence


def test_ps39_fails_when_any_reference_file_is_unreadable(tmp_path):
    refs = tmp_path / "refs"
    refs.mkdir()
    (refs / "notes.txt").write_text("A different text about something else entirely, with no "
                                    "shared run of words.", encoding="utf-8")
    # A name that starts with "." is skipped, so the folder still reads cleanly.
    (refs / ".DS_Store").write_bytes(b"\x00\x01")
    assert results(tmp_path, throw_pages(), references=refs)["PS-39"].status == "pass"
    (refs / "extract.docx").write_bytes(b"PK\x03\x04 binary")
    got = results(tmp_path, throw_pages(), references=refs)["PS-39"]
    assert got.status == "fail" and "1 of 2 reference files" in got.evidence, got.evidence
    for secret in ("extract", ".docx", "something else"):
        assert secret not in got.evidence.lower(), got.evidence


# ---------------------------------------------------------------- review 2: PS-07


def test_ps07_reads_the_size_on_the_finished_size_line(tmp_path):
    # throw_model finishes at 60 x 72 in. The size-basis sentence also prints 60 x 72, so only
    # a check bound to the "Finished size" line sees a wrong size there.
    pages = edit(throw_pages(), 'Finished size 60" x 72"', 'Finished size 62" x 72"')
    got = results(tmp_path, pages)["PS-07"]
    assert got.status == "fail" and "Finished size" in got.evidence, got.evidence
    pages = edit(throw_pages(), 'Finished size 60" x 72"', '60" x 72"')
    got = results(tmp_path, pages)["PS-07"]
    assert got.status == "fail" and "Finished size" in got.evidence, got.evidence


# ---------------------------------------------------------------- review 2: [M] coverage


def test_ps20_binding_line_carries_no_allowance(tmp_path):
    # V-BIND-03, 53 1/2 x 67 in (428 x 536 e): T = 2 (53 1/2 + 67) + 10 = 251 in (2008 e);
    # strips ceil(2008 / 300) = 7; length 7 x 20 = 140 e; qy ceil(140 / 72) = 2 -> 1/2 yd.
    # With the 10 percent top allowance (F5) it would be ceil(140 x 110 / 100) = 154 e and
    # ceil(154 / 72) = 3 qy = 3/4 yd, so the allowance changes the printed line.
    model = sized_model(428, 536)

    def pages(yards):
        return [[P("Small Plain", size=24)],
                [P("Fabric requirements", size=14),
                 ROW([(0, "C"), (20, "Red"), (230, yards),
                      (290, 'Binding: (7) 2 1/2" x WOF strips')], "C")],
                [P("Cutting", size=14), ("fabric", "C", "Red"),
                 P('1. Cut (7) 2 1/2" x WOF strips for binding.')],
                [P("Finishing", size=14),
                 P("1. Join the (7) binding strips with diagonal seams. Fig. 1")]]

    got = results(tmp_path, pages("1/2 yd"), model, only=("PS-11", "PS-20"))
    assert {k: r.status for k, r in got.items()} == {"PS-11": "pass", "PS-20": "pass"}, \
        {k: r.evidence for k, r in got.items()}
    got = results(tmp_path, pages("3/4 yd"), model, only=("PS-20",))["PS-20"]
    assert got.status == "fail" and "C binding" in got.evidence, got.evidence


def test_border_plan_matches_join_thresholds_and_the_crib():
    # V-UNIT-04: k(Lp) = 1 if Lp <= 320 else ceil((Lp - 4) / 316). Each center below is
    # cells of 1 e, so the side and top lengths land on the thresholds; band b = 1 in (8 e),
    # cut 8 + 4 = 12 e. F4: Ls = Li + 4, Lt = Wi + 2b + 4.
    # Center 301 x 316 e: Ls = 316 + 4 = 320, k(320) = 1, per floor(320 / 320) = 1, so
    # ceil(2 / 1) = 2 strips; Lt = 301 + 16 + 4 = 321, k(321) = ceil(317 / 316) = 2, 2 x 2 = 4
    # strips; band strips 2 + 4 = 6.
    model = sized_model(301, 316, cell=1)
    model["borders"] = [{"fabric_id": "c", "width": 8}]
    assert pc.border_plan(model) == [
        {"width": 12, "side": 320, "top": 321, "strips": 6, "k_side": 1, "k_top": 2}]
    # Center 617 x 632 e: Ls = 632 + 4 = 636, k(636) = ceil(632 / 316) = 2 exactly, 4 strips;
    # Lt = 617 + 16 + 4 = 637, k(637) = ceil(633 / 316) = 3, 6 strips; band strips 4 + 6 = 10.
    model = sized_model(617, 632, cell=1)
    model["borders"] = [{"fabric_id": "c", "width": 8}]
    assert pc.border_plan(model) == [
        {"width": 12, "side": 636, "top": 637, "strips": 10, "k_side": 2, "k_top": 3}]
    # V-BORD-02, crib: center 32 x 48 in (256 x 384 e, 4 in cells), b = 2 in (16 e). Cut
    # 16 + 4 = 20 e; Ls = 384 + 4 = 388 e > 320, k = ceil(384 / 316) = 2, 4 strips;
    # Lt = 256 + 32 + 4 = 292 e <= 320, per floor(320 / 292) = 1, ceil(2 / 1) = 2 strips;
    # 4 + 2 = 6 strips.
    model = sized_model(256, 384, cell=32)
    model["borders"] = [{"fabric_id": "c", "width": 16}]
    assert pc.border_plan(model) == [
        {"width": 20, "side": 388, "top": 292, "strips": 6, "k_side": 2, "k_top": 1}]


def test_backing_plan_matches_tie_total_and_side_vectors():
    # V-BACK-12, 28 x 28 in (224 e): Wb = Lb = 224 + 64 = 288 e <= 336, n = 1 both ways;
    # 288 + 36 = 324 e both ways, a tie, kept vertical (one piece, seams "along");
    # qy ceil(324 / 72) = 5 -> 5 x 72 = 360 e (1 1/4 yd). V-WIDE-07: one panel, no wide line.
    plan = pc.backing_plan(sized_model(224, 224))
    assert (plan["panels"], plan["length"], plan["seams"], plan["yards"], plan["wide"]) == \
        (1, 288, "along", 360, None)
    # V-BACK-13, 68 x 68 in (544 e): Wb = Lb = 608 e; n = ceil((608 - 8) / 328) =
    # ceil(600 / 328) = 2 both ways; 2 x 608 + 72 = 1288 e both ways, a tie, kept vertical;
    # qy ceil(1288 / 72) = 18 -> 1296 e (4 1/2 yd).
    plan = pc.backing_plan(sized_model(544, 544))
    assert (plan["panels"], plan["length"], plan["seams"], plan["yards"]) == \
        (2, 608, "along", 1296)
    # V-BACK-14, 24 x 58 in (192 x 464 e): Wb = 256 e, Lb = 528 e. Vertical n(256) = 1,
    # 528 + 36 = 564 e; horizontal n(528) = ceil(520 / 328) = 2, 2 x 256 + 72 = 584 e. Keep
    # vertical on the total (564 < 584) though 512 < 528 raw; qy ceil(564 / 72) = 8 -> 576 e
    # (2 yd). F11: one panel, so no wide line.
    plan = pc.backing_plan(sized_model(192, 464))
    assert (plan["panels"], plan["length"], plan["seams"], plan["yards"], plan["wide"]) == \
        (1, 528, "along", 576, None)
    # V-BACK-01 and V-WIDE-01, queen 92 1/2 x 115 in (740 x 920 e): Wb = 804 e, Lb = 984 e.
    # Vertical n(804) = ceil(796 / 328) = 3, 3 x 984 + 72 = 3024 e; horizontal n(984) =
    # ceil(976 / 328) = 3, 3 x 804 + 72 = 2484 e; keep horizontal (seams across), qy
    # ceil(2484 / 72) = 35 -> 2520 e (8 3/4 yd). Wide: Wb 804 <= 864, Lb 984 > 864, so the
    # length is Lb = 984 e; 984 + 36 = 1020 e; qy ceil(1020 / 72) = 15 -> 1080 e (3 3/4 yd).
    plan = pc.backing_plan(sized_model(740, 920))
    assert (plan["panels"], plan["length"], plan["seams"], plan["yards"], plan["wide"]) == \
        (3, 804, "across", 2520, 1080)
    # V-BACK-07 and V-WIDE-04, queen 90 x 108 in (720 x 864 e): Wb = 784 e, Lb = 928 e.
    # Vertical n(784) = ceil(776 / 328) = 3, 3 x 928 + 72 = 2856 e; horizontal n(928) =
    # ceil(920 / 328) = 3, 3 x 784 + 72 = 2424 e; keep horizontal, qy ceil(2424 / 72) = 34
    # -> 2448 e (8 1/2 yd). Wide: Wb 784 fits, Lb 928 > 864, length 928 e; 928 + 36 = 964 e;
    # qy ceil(964 / 72) = 14 -> 1008 e (3 1/2 yd).
    plan = pc.backing_plan(sized_model(720, 864))
    assert (plan["panels"], plan["length"], plan["seams"], plan["yards"], plan["wide"]) == \
        (3, 784, "across", 2448, 1008)


# V-BACK-02 (throw 60 x 72): 4 1/4 yd, (2) panels cut 68 in, seams across. Each edit breaks
# one number: 4 yd is the length without the 9 in pieced allowance (ceil(1088 / 72) = 16 qy,
# V-BACK-02's column C); 3 panels is not n(80 in) = ceil(79 / 41) = 2; 80 in is the vertical
# layout's panel length, not the kept horizontal Wb = 68 in.
PS12_EDITS = [('4 1/4 yd: 2 lengths of 68"', '4 yd: 2 lengths of 68"'),
              ('4 1/4 yd: 2 lengths of 68"', '4 1/4 yd: 3 lengths of 68"'),
              ('4 1/4 yd: 2 lengths of 68"', '4 1/4 yd: 2 lengths of 80"')]


@pytest.mark.parametrize("old,new", PS12_EDITS)
def test_ps12_fails_on_a_wrong_backing_number(tmp_path, old, new):
    got = results(tmp_path, edit(throw_pages(), old, new), only=("PS-12",))["PS-12"]
    assert got.status == "fail", got.evidence


def test_ps12_fails_on_a_wide_back_line_the_king_does_not_get(tmp_path):
    # V-BACK-08, king 110 x 108 in (880 x 864 e): Wb = 118 in (944 e), Lb = 116 in (928 e);
    # vertical n(118) = ceil(117 / 41) = 3, 3 x 116 + 9 = 357 in; horizontal n(116) = 3,
    # 3 x 118 + 9 = 363 in; keep vertical (seams along), qy ceil(2856 / 72) = 40 -> 10 yd.
    # V-WIDE-05: Wb 118 > 108 and Lb 116 > 108, so no 108 in line; 3 1/2 yd is the 118 in
    # wide-back figure, printed against the wrong width.
    model = sized_model(880, 864)

    def pages(wide):
        rows = [ROW([(0, "Backing"), (80, '10 yd: 3 lengths of 116" at 42" wide, seams run '
                                          'along the quilt')])]
        rows += [ROW([(80, 'or 3 1/2 yd of 108" wide backing')])] if wide else []
        return [[P("King Plain", size=24)], [P("Fabric requirements", size=14), *rows]]

    assert results(tmp_path, pages(False), model, only=("PS-12",))["PS-12"].status == "pass"
    got = results(tmp_path, pages(True), model, only=("PS-12",))["PS-12"]
    assert got.status == "fail" and "shows none" in got.evidence, got.evidence


def test_ps13_fails_on_a_wrong_batting_size(tmp_path):
    # V-BATT-03: 60 x 72 + 2 x 4 in = 68 x 80 in. 64 x 76 in adds the 4 in once per axis; the
    # twin package still covers it, so only the size is wrong.
    pages = edit(throw_pages(), '68" x 80", twin', '64" x 76", twin')
    got = results(tmp_path, pages, only=("PS-13",))["PS-13"]
    assert got.status == "fail" and "68 x 80" in got.evidence, got.evidence


def test_ps13_a_quilt_larger_than_a_king_needs_the_statement(tmp_path):
    # V-BATT-10: 102 1/2 x 120 in (820 x 960 e) -> 110 1/2 x 128 in; king no (128 > 120;
    # turned 128 > 124), so no package covers it and the row says "larger than a king".
    model = sized_model(820, 960)

    def pages(package):
        return [[P("Wide Plain", size=24)],
                [P("Fabric requirements", size=14),
                 ROW([(0, "Batting"), (80, f'110 1/2" x 128", {package} (124" x 120")')])]]

    got = results(tmp_path, pages("larger than a king package"), model, only=("PS-13",))
    assert got["PS-13"].status == "pass", got["PS-13"].evidence
    got = results(tmp_path, pages("king package"), model, only=("PS-13",))["PS-13"]
    assert got.status == "fail" and "larger than a king" in got.evidence, got.evidence
