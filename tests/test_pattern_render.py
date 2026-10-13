"""Tests for the pattern document renderer and its page rules (A4a).

Expected values come from PATTERN-SPEC (G-01 to G-05, L-10, C-09, C-10 and the
section 6 checks PS-01 to PS-06, PS-38, PS-41 and PS-42) and from the hand
arithmetic in the comments. The A11 checker in tests/pattern_checks.py, which
never imports qrep, judges the page checks on a full synthetic document.

qrep.export.figures does not exist until A5a, and its drawers will expect real
subjects, so every test here decides what that module holds: by default it is
absent (the autouse fixture), and a test that needs drawers installs fakes.
"""

import importlib.abc
import importlib.machinery
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import types

import pypdf
import pytest
from reportlab import rl_config
from reportlab.graphics.shapes import Drawing, Group, Rect, String
from reportlab.graphics.widgetbase import Widget
from reportlab.lib.colors import HexColor
from reportlab.platypus import Spacer

import pattern_checks as pc
import qrep
from qrep.export.pattern import render
from qrep.export.pattern.document import (
    Figure,
    FigureRequest,
    Paragraph,
    PatternDocument,
    PatternTextError,
    PrintScaleSquare,
    Section,
    SectionKind,
    Step,
    Steps,
    Subheading,
    Swatch,
    Table,
    check_text,
    inches,
    rectangle,
    size,
    square,
)

REPO = Path(__file__).resolve().parent.parent
NAME = "Lantern Rows"
CREAM, NAVY, RUST = "#f2e8d5", "#3b5b92", "#b03a2e"
# The model JSON the A11 checker reads beside the PDF: the palette colors find
# figure patches, and one border band means the Borders heading must appear.
MODEL = {
    "palette": {
        "fabrics": [
            {"id": "cream", "color": CREAM},
            {"id": "navy", "color": NAVY},
            {"id": "rust", "color": RUST},
        ]
    },
    "borders": [{"width": 48}],
}
PAGE_CHECKS = ["PS-01", "PS-02", "PS-03", "PS-05", "PS-06", "PS-38", "PS-41", "PS-42"]


@pytest.fixture(autouse=True)
def no_figures_module(monkeypatch):
    monkeypatch.setitem(sys.modules, render.FIGURES_MODULE, None)


def normalize(text: str) -> str:
    # PATTERN-SPEC section 6: collapse whitespace, drop straight double quotes.
    return re.sub(r"\s+", " ", text.replace('"', "")).strip()


def write(tmp_path, document, filename="pattern.pdf"):
    path = tmp_path / filename
    path.write_bytes(render.render_pdf(document))
    return path


def page_texts(path) -> list[str]:
    return [normalize(page.extract_text()) for page in pypdf.PdfReader(path).pages]


def page_of(texts: list[str], needle: str) -> int:
    pages = [n for n, text in enumerate(texts, start=1) if needle in text]
    assert len(pages) == 1, f"{needle!r} found on pages {pages}"
    return pages[0]


def full_document(name=NAME) -> PatternDocument:
    """Every section kind and every block type, with QREP's own made-up content."""

    def unit_figure(n):
        return FigureRequest("hst_unit", 200, 120, f"HST unit 1, step {n}")

    return PatternDocument(
        name,
        [
            Section(
                SectionKind.COVER,
                [
                    # 480 e = 60", 576 e = 72"
                    Paragraph(f"Finished size {size(480, 576)}"),
                    Paragraph(f'20 blocks, {inches(96)} finished, set 4 x 5, sewn in rows'),
                    Paragraph("3 fabrics, plus backing"),
                    Figure(FigureRequest("cover_render", 300, 300, "the whole quilt top")),
                ],
            ),
            Section(
                SectionKind.FABRIC_REQUIREMENTS,
                [
                    Table(
                        ("", "Fabric", "Name", "Yards"),
                        [
                            (Swatch(CREAM), "A", "Background", "2 1/4 yd"),
                            (Swatch(NAVY), "B", "Navy", "1 1/2 yd"),
                            (Swatch(RUST), "C", "Rust", "3/4 yd"),
                        ],
                        widths=(1, 1, 4, 2),
                    ),
                    PrintScaleSquare(
                        "Print this page at 100 percent. The square measures 1 inch on each side."
                    ),
                ],
            ),
            Section(
                SectionKind.BEFORE_YOU_BEGIN,
                [
                    Steps(
                        [
                            Step("Read the whole pattern before cutting."),
                            Step(f"Every piecing seam is {inches(2)}."),
                            Step("RST means right sides together."),
                        ]
                    ),
                    Paragraph(
                        "The figures use these symbols.",
                        figure=FigureRequest("symbol_legend", 300, 80, "pressing and line symbols"),
                    ),
                ],
            ),
            Section(
                SectionKind.CUTTING,
                [
                    Subheading("A Background", swatch=CREAM),
                    Steps(
                        [
                            Step(
                                f"Cut (6) {inches(36)} x WOF strips.",
                                details=(f"A1: subcut (6) strips into (48) {square(36)}s, 8 per strip.",),
                            )
                        ]
                    ),
                ],
            ),
            Section(
                SectionKind.UNITS,
                [
                    Subheading("HST unit 1"),
                    Steps(
                        [
                            Step("Draw a line corner to corner on each A2 square.", figure=unit_figure(1)),
                            Step("Sew on both sides of the line.", figure=unit_figure(2)),
                        ]
                    ),
                    Paragraph("Make 40."),
                ],
            ),
            Section(
                SectionKind.BLOCKS,
                [
                    Subheading("Block 1"),
                    Steps([Step("Sew the units into rows, then join the rows.")]),
                    Paragraph(f"Block 1 should measure {square(100)}."),
                ],
            ),
            Section(
                SectionKind.QUILT_ASSEMBLY,
                [
                    Paragraph(
                        "Lay out the blocks in 5 rows of 4.",
                        figure=FigureRequest("assembly", 300, 200, "the quilt center in rows"),
                    )
                ],
            ),
            Section(
                SectionKind.BORDERS,
                [Paragraph("Sew the side borders first, then the top and bottom borders.")],
            ),
            Section(
                SectionKind.FINISHING,
                [
                    Steps(
                        [
                            Step("Layer the backing, batting and top."),
                            Step("Quilt the layers."),
                            Step("Bind the quilt."),
                        ]
                    )
                ],
            ),
            Section(
                SectionKind.LAYOUT_CHART,
                [Figure(FigureRequest("layout_chart", 400, 400, "rows 1 to 20, columns 1 to 16"))],
            ),
            Section(
                SectionKind.COLORING_PAGE,
                [Figure(FigureRequest("coloring_page", 400, 400, "the quilt outline"))],
            ),
        ],
    )


def small_document(*blocks, name=NAME) -> PatternDocument:
    return PatternDocument(
        name,
        [
            Section(SectionKind.COVER, [Paragraph("3 fabrics, plus backing")]),
            Section(SectionKind.FABRIC_REQUIREMENTS, list(blocks)),
        ],
    )


def assert_checks_pass(path, only=PAGE_CHECKS):
    results = pc.run_checks(path, MODEL, only=only)
    assert [r.check for r in results] == only
    failed = [r.line() for r in results if r.status != "pass"]
    assert not failed, failed


# ---------------------------------------------------------------- page geometry and footer


def test_every_page_is_us_letter_portrait(tmp_path):
    # G-01, PS-01: US Letter is 8 1/2" x 11"; at 72 pt per inch, 8.5 x 72 = 612 and
    # 11 x 72 = 792.
    reader = pypdf.PdfReader(write(tmp_path, full_document()))
    # The cover, then sections that cannot all share one page: at least 3 pages.
    assert len(reader.pages) >= 3
    for page in reader.pages:
        box = page.mediabox
        assert (float(box.left), float(box.bottom), float(box.width), float(box.height)) == (
            0, 0, 612, 792)
        assert int(page.get("/Rotate", 0) or 0) == 0


def test_text_and_drawings_keep_36_pt_side_margins(tmp_path):
    # G-01, PS-38: side margins of at least 1/2" = 36 pt, so nothing sits left of
    # x = 36 or right of 612 - 36 = 576.
    pages = pc.read_pdf(write(tmp_path, full_document()))
    for page in pages:
        for run in page.runs:
            assert run.x >= 36 and run.x + run.width <= 576, (page.number, run.text)
        for shape in page.shapes:
            assert shape.x0 >= 36 and shape.x1 <= 576, (page.number, shape)


def test_every_page_has_the_footer_and_no_date(tmp_path):
    # G-02, PS-03: the pattern name, "page N of M" and "QREP <version>" on every page
    # (version source: qrep/__init__.py), and no date anywhere.
    path = write(tmp_path, full_document())
    texts = page_texts(path)
    total = len(texts)
    for number, text in enumerate(texts, start=1):
        assert NAME in text
        assert f"page {number} of {total}" in text
        assert f"QREP {qrep.__version__}" in text
        assert not re.search(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b", text)


def test_a_long_name_moves_above_the_page_mark_and_stays_whole(tmp_path):
    # A name wider than the footer's left part prints on its own line just above
    # the page mark, so the whole name is still in every footer (PS-03). The left
    # part is 612 / 2 - 54 - 12 = 240 pt less half the widest page mark; "page 9 of
    # 9" is 50.04 pt by the Helvetica 10 pt widths, so 240 - 25.02 = 214.98 pt. This
    # 60-character name measures 291.22 pt: too wide for that, narrow enough for the
    # 504 pt line above.
    name = "The Long Winter Evenings Lantern Rows Medallion Free Sampler"
    path = write(tmp_path, full_document(name=name))
    for text in page_texts(path):
        assert name in text
    assert_checks_pass(path, ["PS-03"])


def test_a_name_too_wide_for_one_footer_line_is_refused():
    # By the Helvetica 10 pt widths, "Lantern " is 36.69 pt and "Rows" 25 pt, so this
    # 148-character name is 18 x 36.69 + 25 = 685.42 pt, past the 504 pt content
    # width (612 - 2 x 54): no footer line holds it whole.
    with pytest.raises(ValueError, match="footer"):
        render.render_pdf(full_document(name="Lantern " * 18 + "Rows"))


def test_a_long_one_word_title_shrinks_until_the_word_fits_the_line(tmp_path):
    # By the Helvetica-Bold widths per 1000 em (L 611, a 556, n 611, t 333, e 556,
    # r 389, o 611, w 778, s 556, l 278, q 611, u 611, i 278), "Lanternrows" is 6001,
    # "lanternrows" 6001 - 611 + 278 = 5668 and "quilt" 2111, so this one word is
    # 6001 + 2 x 5668 + 2111 = 19448. At 28 pt it is 544.5 pt and at 26 pt 505.6 pt,
    # both past the 504 pt line; at 24 pt it is 466.8 pt, so the title prints at
    # 24 pt in one piece instead of breaking mid-word. The footer holds it at 10 pt.
    name = "Lanternrowslanternrowslanternrowsquilt"
    path = write(tmp_path, small_document(Paragraph("Buy 3/4 yd."), name=name))
    assert page_texts(path)[0].count(name) == 2
    assert {round(run.size, 2) for run in pc.read_pdf(path)[0].runs if run.text == name} == {
        24, 10}


def test_a_name_holding_a_date_is_refused():
    # G-02: no page shows a date, and the name prints in every footer.
    with pytest.raises(PatternTextError, match="date"):
        full_document(name="Quilt of 2026-10-13")


def test_the_a11_page_checks_pass_on_a_full_document(tmp_path):
    assert_checks_pass(write(tmp_path, full_document()))


# ---------------------------------------------------------------- type sizes (L-10)


def test_text_meets_the_l10_minimums(tmp_path):
    # L-10: body 10 pt, tables 9 pt, figure labels 7 pt. With no drawer every figure
    # is a placeholder frame, whose text is body text, so every run is 10 pt or more.
    pages = pc.read_pdf(write(tmp_path, full_document()))
    sizes = {round(run.size, 2) for page in pages for run in page.runs}
    assert min(sizes) >= 10


def test_a_drawer_label_at_7_pt_prints_and_one_below_it_is_refused(tmp_path, monkeypatch):
    # L-10: figure labels are 7 pt or more, so 7 pt prints and 6.9 pt is refused.
    def drawer(font_size):
        def draw(request):
            drawing = Drawing(request.width, request.height)
            drawing.add(Rect(0, 0, request.width, request.height, fillColor=HexColor(NAVY)))
            drawing.add(String(20, 20, "B1", fontName="Helvetica", fontSize=font_size))
            return drawing
        return draw

    request = FigureRequest("block", 120, 120, "Block 1")
    document = small_document(Paragraph("Sew the block.", figure=request))
    install_figures(monkeypatch, {"block": drawer(7)})
    path = write(tmp_path, document)
    assert "B1" in page_texts(path)[1]
    assert_checks_pass(path, ["PS-42"])
    install_figures(monkeypatch, {"block": drawer(6.9)})
    with pytest.raises(ValueError, match="7 pt"):
        render.render_pdf(document)


def test_a_label_scaled_below_7_pt_is_refused(monkeypatch):
    # An 8 pt label in a group scaled by 1/2 prints at 8 x 1/2 = 4 pt.
    def draw(request):
        drawing = navy_block(request)
        drawing.add(Group(String(20, 20, "B2", fontName="Helvetica", fontSize=8),
                          transform=(0.5, 0, 0, 0.5, 0, 0)))
        return drawing

    install_figures(monkeypatch, {"block": draw})
    document = small_document(Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1")))
    with pytest.raises(ValueError, match="7 pt"):
        render.render_pdf(document)


def test_a_drawing_with_shapes_outside_its_own_box_is_refused(monkeypatch):
    # A rectangle from x = -20 to 90 + 20 inside a 90 pt drawing prints 20 pt past
    # each side of the size it declared.
    def draw(request):
        drawing = Drawing(request.width, request.height)
        drawing.add(Rect(-20, 0, request.width + 40, request.height, fillColor=HexColor(NAVY)))
        return drawing

    install_figures(monkeypatch, {"block": draw})
    document = small_document(Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1")))
    with pytest.raises(ValueError, match="outside"):
        render.render_pdf(document)


# ---------------------------------------------------------------- deterministic bytes (PS-04)

RENDER_SCRIPT = r"""
import sys, time
from reportlab import rl_config

clock, mode = float(sys.argv[1]), sys.argv[2]
assert rl_config.invariant == 0, "the renderer, not the process, must set invariant mode"
time.time = lambda: clock
sys.modules["qrep.export.figures"] = None
if mode == "control":
    import io
    from reportlab.pdfgen import canvas

    out = io.BytesIO()
    c = canvas.Canvas(out)
    c.drawString(72, 72, "Lantern Rows")
    c.save()
    sys.stdout.buffer.write(out.getvalue())
else:
    import types

    sys.path.insert(0, "tests")
    import test_pattern_render as t
    from qrep.export.pattern.render import render_pdf

    figures = types.ModuleType("qrep.export.figures")
    figures.DRAWERS = {"hst_unit": t.navy_block}
    sys.modules["qrep.export.figures"] = figures
    sys.stdout.buffer.write(render_pdf(t.full_document()))
"""


def run_render(clock: int, mode: str, hash_seed: str = "0") -> bytes:
    # reportlab stamps the PDF with the clock unless invariant mode is on, and it uses
    # SOURCE_DATE_EPOCH when that is set, so the variable is cleared to control it.
    # Each process gets its own hash seed, so set and dict order cannot line up by luck.
    env = {k: v for k, v in os.environ.items() if k != "SOURCE_DATE_EPOCH"}
    env["PYTHONHASHSEED"] = hash_seed
    result = subprocess.run(
        [sys.executable, "-c", RENDER_SCRIPT, str(clock), mode],
        capture_output=True,
        env=env,
        cwd=REPO,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


@pytest.mark.skipif(
    sys.platform == "emscripten",
    reason="subprocess is unavailable under wasm; the in-process test covers both runtimes",
)
def test_two_command_line_renders_give_identical_bytes():
    # PS-04, engine-20: two separate processes render the full document, its HST
    # figures drawn and the rest placeholders, with clocks a day apart
    # (1_000_000_000 s and 1_000_086_400 s since 1970).
    first = run_render(1_000_000_000, "pattern", hash_seed="1")
    assert first.startswith(b"%PDF")
    assert run_render(1_000_086_400, "pattern", hash_seed="2") == first
    # Control: a plain reportlab canvas without invariant mode does take the faked
    # clock, so the identical bytes above are the renderer's doing.
    assert run_render(1_000_000_000, "control") != run_render(1_000_086_400, "control")


def test_renders_ignore_the_clock_and_leave_invariant_mode_as_found(monkeypatch):
    # PS-04 in either runtime: the renderer sets invariant mode itself and restores
    # the process setting afterwards.
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    monkeypatch.setattr(rl_config, "invariant", 0)
    document = full_document()
    monkeypatch.setattr(time, "time", lambda: 1_000_000_000.0)
    first = render.render_pdf(document)
    monkeypatch.setattr(time, "time", lambda: 1_000_086_400.0)
    assert render.render_pdf(document) == first
    assert rl_config.invariant == 0


@pytest.mark.parametrize("epoch", ["1000000000", "x"])
def test_source_date_epoch_neither_changes_the_bytes_nor_breaks_a_render(monkeypatch, epoch):
    # reportlab stamps SOURCE_DATE_EPOCH into the PDF even in invariant mode, and
    # a value that is not a number makes it raise. A render ignores the variable
    # and leaves it as it found it.
    document = full_document()
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    plain = render.render_pdf(document)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", epoch)
    assert render.render_pdf(document) == plain
    assert os.environ["SOURCE_DATE_EPOCH"] == epoch


@pytest.mark.parametrize(
    ("setting", "value"),
    [("pageCompression", 0), ("useA85", 0), ("overlapAttachedSpace", 0), ("invariant", 0)],
)
def test_process_reportlab_settings_do_not_change_the_bytes(monkeypatch, setting, value):
    # An RL_ environment variable sets these in rl_config: uncompressed or unencoded
    # page streams, or a frame that adds both spaces between blocks, would change
    # the bytes and the layout.
    document = full_document()
    plain = render.render_pdf(document)
    monkeypatch.setattr(rl_config, setting, value)
    assert render.render_pdf(document) == plain
    assert getattr(rl_config, setting) == value


# ---------------------------------------------------------------- section order (PS-02, G-04)


def test_sections_print_in_ps02_order_with_the_cover_alone(tmp_path):
    # PS-02: no heading on page 1, then the headings in this order.
    path = write(tmp_path, full_document())
    texts = page_texts(path)
    # PATTERN-SPEC PS-02, verbatim and in order.
    headings = ["Fabric requirements", "Before you begin", "Cutting", "Making the units",
                "Making the blocks", "Quilt assembly", "Borders", "Finishing", "Layout chart",
                "Coloring page"]
    assert not any(heading in texts[0] for heading in ["Fabric requirements", "Before you begin"])
    assert texts[1].startswith("Fabric requirements")
    joined = " ".join(texts)
    positions = [joined.index(heading) for heading in headings]
    assert positions == sorted(positions)


def test_every_heading_shares_a_page_with_what_follows_it(tmp_path):
    # The renderer's rule (render.py, _keep_headings): no heading sits alone. Each
    # heading here is paired with the first text after it in full_document; a subheading between
    # them (A Background, HST unit 1, Block 1) travels with both.
    follows = {
        "Fabric requirements": "Background",
        "Before you begin": "1. Read the whole pattern",
        "Cutting": "1. Cut (6)",
        "Making the units": "1. Draw a line corner to corner",
        "Making the blocks": "1. Sew the units into rows",
        "Quilt assembly": "Lay out the blocks in 5 rows of 4",
        "Borders": "Sew the side borders first",
        "Finishing": "1. Layer the backing",
        "Layout chart": "rows 1 to 20, columns 1 to 16",
        "Coloring page": "the quilt outline",
    }
    texts = page_texts(write(tmp_path, full_document()))
    for heading, first in follows.items():
        assert page_of(texts, heading) == page_of(texts, first), heading


@pytest.mark.parametrize(
    "kinds",
    [
        [SectionKind.COVER, SectionKind.CUTTING, SectionKind.FABRIC_REQUIREMENTS],
        [SectionKind.COVER, SectionKind.CUTTING, SectionKind.CUTTING],
        [SectionKind.FABRIC_REQUIREMENTS, SectionKind.COVER],
        [SectionKind.FABRIC_REQUIREMENTS],
        [],
    ],
)
def test_sections_out_of_order_twice_or_without_the_cover_first_are_refused(kinds):
    with pytest.raises(ValueError, match="order|cover"):
        PatternDocument(NAME, [Section(kind, [Paragraph("Sew.")]) for kind in kinds])


def test_a_section_without_blocks_is_refused():
    # An empty Borders section would print a bare heading for a quilt with no
    # borders, which PS-02 fails; the cover alone may be empty (its title prints).
    with pytest.raises(ValueError, match="no blocks"):
        Section(SectionKind.BORDERS)
    Section(SectionKind.COVER)


def test_paragraph_indent_is_zero_to_three_levels():
    Paragraph("Press.", indent=3)
    for bad in (-1, 4):
        with pytest.raises(ValueError):
            Paragraph("Press.", indent=bad)


def test_a_step_list_may_continue_its_numbering(tmp_path):
    # G-04 restarts the count at 1 under each subheading, so a list that a note
    # interrupts under one subheading continues from 3.
    document = small_document(
        Subheading("HST unit 1"),
        Steps([Step("Draw the line."), Step("Sew both sides.")]),
        Paragraph("Press toward the darker fabric."),
        Steps([Step("Cut on the line."), Step("Trim the units.")], start=3),
    )
    text = page_texts(write(tmp_path, document))[1]
    for n, words in enumerate(
        ["Draw the line.", "Sew both sides.", "Cut on the line.", "Trim the units."], start=1
    ):
        assert f"{n}. {words}" in text
    with pytest.raises(ValueError):
        Steps([Step("Sew.")], start=0)


def test_a_cover_that_overflows_page_1_is_refused():
    # The cover is alone on page 1 (PS-02), so a cover that needs a second page is a
    # builder error, never a cover that spills onto page 2. Each paragraph is a
    # 13 pt line with 6 pt after it, so 80 need 80 x 19 = 1,520 pt against a 666 pt
    # frame (792 - 54 - 72).
    cover = [Paragraph(f"Cover line {n}.") for n in range(80)]
    document = PatternDocument(
        NAME, [Section(SectionKind.COVER, cover),
               Section(SectionKind.FABRIC_REQUIREMENTS, [Paragraph("Buy 3/4 yd.")])]
    )
    with pytest.raises(ValueError, match="page 1"):
        render.render_pdf(document)


def test_a_document_of_only_a_cover_is_one_page_or_refused(tmp_path):
    # With no section after it, the cover is every page: 3 lines fit on one page,
    # and 80 lines (over 1,000 pt) do not.
    def cover_only(lines):
        return PatternDocument(NAME, [Section(SectionKind.COVER,
                                              [Paragraph(f"Cover line {n}.") for n in range(lines)])])

    assert len(page_texts(write(tmp_path, cover_only(3)))) == 1
    with pytest.raises(ValueError, match="page 1"):
        render.render_pdf(cover_only(80))


def test_a_cover_that_exactly_fills_page_1_is_accepted_and_one_point_more_is_refused(tmp_path):
    # The title is one 34 pt line with 18 pt after it; each paragraph a 13 pt line
    # with 6 pt after it. The frame spaces two neighbors by the larger of their two
    # spaces, so the title and two paragraphs take 34 + 18 + 13 + 6 + 13 + 6 = 90 pt,
    # and a 576 pt cover figure fills the 666 pt frame exactly (90 + 576 = 666).
    # That cover is alone on page 1. A 577 pt figure needs 667 pt, so it moves to
    # page 2. Both fit the 580 pt figure area.
    def cover(height):
        blocks = [Paragraph("Finished size 60\" x 72\""), Paragraph("3 fabrics, plus backing"),
                  Figure(FigureRequest("cover_render", 300, height, "the whole quilt top"))]
        return PatternDocument(NAME, [Section(SectionKind.COVER, blocks),
                                      Section(SectionKind.FABRIC_REQUIREMENTS,
                                              [Paragraph("Buy 3/4 yd.")])])

    assert len(page_texts(write(tmp_path, cover(576)))) == 2
    with pytest.raises(ValueError, match="page 1"):
        render.render_pdf(cover(577))


FILLER = [Paragraph(f"Filler line {n}.") for n in range(1, 30)]


@pytest.mark.parametrize(
    ("blocks", "last"),
    [
        # The heading is one 20 pt line with 8 pt after it and each filler paragraph
        # one 13 pt line with 6 pt after it, so 2 fillers end 28 + 2 x 19 = 66 pt down
        # the 666 pt frame, leaving 600 pt. 37 one-line rows of 12 pt leading and
        # 2 + 2 pt padding take 37 x 16 = 592 pt and end 8 pt above the frame foot.
        ((*FILLER[:2], Table((), [(f"Row {n}", "(4) squares") for n in range(1, 38)])),
         "Row 37"),
        # 4 fillers end 28 + 4 x 19 = 104 pt down, leaving 562 pt; a 557 pt figure
        # fits with 5 pt to spare.
        ((*FILLER[:4], Figure(FigureRequest("layout_chart", 400, 557, "rows 1 to 20"))),
         "rows 1 to 20"),
        # 29 fillers end 28 + 29 x 19 = 579 pt down; the square's row is 72 pt with
        # 3 + 3 pt default padding, so it ends at 579 + 78 = 657 pt, 9 pt from the foot.
        ((*FILLER[:29], PrintScaleSquare("The square measures 1 inch on each side.")),
         "measures 1 inch"),
    ],
)
def test_space_after_a_last_block_never_starts_a_blank_page(tmp_path, blocks, last):
    # Each block ends 10 pt or less above the frame foot, where 10 pt of trailing
    # space no longer fits. Space after a block is dropped at a page end, so the
    # document stays two pages and the block is on page 2 (PS-41: no page without
    # instruction text).
    texts = page_texts(write(tmp_path, small_document(*blocks)))
    assert len(texts) == 2
    assert page_of(texts, last) == 2


def test_each_step_stays_on_the_page_of_its_figure(tmp_path):
    # G-04, PS-44. The frame is 792 - 54 - 72 = 666 pt tall, and it spaces two
    # neighbors by the larger of their two spaces. Each step here is one 13 pt line,
    # 3 pt, a 260 pt figure, 3 pt and its 13 pt caption: 292 pt, with 10 pt after the
    # caption. On page 2 the heading takes 20 + 8 = 28 pt and two steps 292 + 10 +
    # 292 pt, so 28 + 594 = 622 pt, which leaves 666 - 622 - 10 = 34 pt: room for the
    # third step's line but not its figure. A flow that does not keep them together
    # prints that line at the foot of the page and its figure on the next. Later
    # pages hold two steps each (594 pt), so 7 steps fill pages 2 to 5.
    steps = [
        Step(f"Step marker {n}: sew the pair.",
             figure=FigureRequest("hst_unit", 300, 260, f"figure marker {n}"))
        for n in range(1, 8)
    ]
    texts = page_texts(write(tmp_path, small_document(Steps(steps))))
    assert len(texts) == 5
    for n in range(1, 8):
        # G-04: numbered from 1, each step on the page of its figure.
        assert page_of(texts, f"{n}. Step marker {n}:") == page_of(texts, f"figure marker {n}")


def test_headings_a_one_line_paragraph_and_the_tallest_figure_share_a_page(tmp_path):
    # The heading (20 pt, 8 pt after), a swatch subheading (a 23 pt row: 15 pt text,
    # 6 pt and 2 pt padding), the paragraph (13 pt, 6 pt after), the 580 pt figure
    # and its caption (3 pt before, 13 pt) take 20 + 8 + 23 + 13 + 6 + 580 + 3 + 13
    # = 666 pt, the whole frame. So a heading never prints alone above the first
    # figure of its section; a figure 1 pt taller does not fit the figure area.
    def document(height):
        return small_document(
            Subheading("A Background", swatch=CREAM),
            Paragraph("Paragraph marker: sew.",
                      figure=FigureRequest("hst_unit", 300, height, "figure marker")),
        )

    texts = page_texts(write(tmp_path, document(580)))
    assert len(texts) == 2
    for text in ["Fabric requirements", "A Background", "Paragraph marker", "figure marker"]:
        assert page_of(texts, text) == 2
    with pytest.raises(ValueError, match="figure area"):
        render.render_pdf(document(581))


def test_a_heading_that_cannot_share_a_page_with_its_first_figure_is_refused():
    # "Sew. " is 2501 / 1000 em (S 667, e 556, w 722, period 278, space 278), so 25.01
    # pt at 10 pt, and 21 of them (525.21 pt) wrap to 2 or more lines of 504 pt:
    # 26 pt or more. With the headings above, the group needs at least 20 + 8 + 23 +
    # 26 + 6 + 580 + 3 + 13 = 679 pt, past the 666 pt frame, though the paragraph
    # and its figure alone (at least 628 pt) fit. The heading would print alone.
    document = small_document(
        Subheading("A Background", swatch=CREAM),
        Paragraph("Sew. " * 21, figure=FigureRequest("hst_unit", 300, 580, "a tall figure")),
    )
    with pytest.raises(ValueError, match="more than one page"):
        render.render_pdf(document)


def test_a_step_too_tall_to_share_a_page_with_its_figure_is_refused():
    # 120 x 25.01 = 3,001.2 pt of "Sew. " wraps to a 504 pt first line (the number
    # hangs in the 18 pt indent) and 486 pt lines after it: (3,001.2 - 504) / 486 =
    # 5.14, so 7 lines or more, 91 pt or more. With 3 pt, the 570 pt figure, 3 pt and
    # the 13 pt caption, the step needs at least 91 + 3 + 570 + 3 + 13 = 680 pt of
    # the 666 pt frame.
    step = Step("Sew. " * 120, figure=FigureRequest("hst_unit", 300, 570, "a tall figure"))
    with pytest.raises(ValueError, match="one page"):
        render.render_pdf(small_document(Steps([step])))


def test_a_table_row_never_splits_across_pages(tmp_path):
    # G-04. Each long cell wraps in 504 x 6/7 - 3 - 3 = 426 pt. "The long cell keeps
    # going so that it wraps. " is 18898 / 1000 em by the Helvetica widths, 188.98
    # pt, so the 5, 10 or 15 sentences of a row (944.9, 1,889.8 or 2,834.7 pt) need
    # at least 3, 5 or 7 lines: rows of at least 40, 64 or 88 pt (12 pt lines, 2 + 2
    # pt padding). A page break can fall inside such a row, where a table allowed to
    # split rows would split one. Rows n = 1 to 40 carry 1 + n % 3 fives: 13 rows of
    # 5, 14 of 10 and 13 of 15 sentences, at least 13 x 40 + 14 x 64 + 13 x 88 =
    # 2,560 pt, more than three 666 pt frames, so the table takes at least 4 pages
    # after the cover. A row's first and last words share a page.
    filler = "The long cell keeps going so that it wraps. " * 5
    rows = [(str(n), f"Row {n} begins. {filler * (1 + n % 3)}Row {n} ends.")
            for n in range(1, 41)]
    texts = page_texts(write(tmp_path, small_document(Table(("Row", "Text"), rows, widths=(1, 6)))))
    assert len(texts) >= 5
    for n in range(1, 41):
        assert page_of(texts, f"Row {n} begins.") == page_of(texts, f"Row {n} ends.")


def test_a_table_word_wider_than_its_column_is_refused():
    # widths (11, 1) give the name column 504 / 12 = 42 pt, 36 pt inside its 3 + 3 pt
    # padding. "Background" is 5336 / 1000 em (B 667, a 556, c 500, k 500, g 556,
    # r 333, o 556, u 556, n 556, d 556), 53.36 pt at 10 pt, so it cannot print whole.
    table = Table(("Piece", "Name"), [("A", "Background")], widths=(11, 1))
    with pytest.raises(ValueError, match="wider than its"):
        render.render_pdf(small_document(table))


def test_a_length_or_dimension_never_breaks_across_lines(tmp_path):
    # The step's first line has the full 504 pt (its number hangs in the indent).
    # "1. " is 11.12 pt, "Sew " 22.23 pt (2223 / 1000 em) and "Cut (6) 2" 38.90 pt
    # (3890 / 1000 em), so 11.12 + 20 x 22.23 + 38.90 = 494.62 pt fits, and adding
    # ' 1/2"' (20.23 pt) makes 514.85 pt, which does not. A break at that space would
    # leave "Cut (6) 2" on the first line, which reads as a 2" strip. The renderer
    # holds the whole size on one line.
    step = Step("Sew " * 20 + 'Cut (6) 2 1/2" x WOF strips.')
    path = write(tmp_path, small_document(Steps([step])))
    lines = [normalize(line) for line in pypdf.PdfReader(path).pages[1].extract_text().splitlines()]
    assert any("2 1/2 x WOF strips." in line for line in lines), lines


# ---------------------------------------------------------------- figures


def install_figures(monkeypatch, drawers):
    module = types.ModuleType(render.FIGURES_MODULE)
    module.DRAWERS = drawers
    monkeypatch.setitem(sys.modules, render.FIGURES_MODULE, module)


def navy_block(request):
    drawing = Drawing(request.width, request.height)
    drawing.add(Rect(0, 0, request.width, request.height, fillColor=HexColor(NAVY)))
    drawing.add(String(10, 10, "B1", fontName="Helvetica", fontSize=8))
    return drawing


def test_a_registered_kind_is_drawn_by_qrep_export_figures(tmp_path, monkeypatch):
    calls = []

    def draw(request):
        calls.append(request)
        return navy_block(request)

    request = FigureRequest("block", 150, 150, "Block 1 assembled", subject={"block": 1})
    install_figures(monkeypatch, {"block": draw})
    path = write(tmp_path, small_document(Paragraph("Join the rows.", figure=request)))
    assert calls == [request] and calls[0] is request
    assert "B1" in page_texts(path)[1]
    assert pc.placeholder_frames(path, MODEL) == []


def test_a_kind_the_module_lacks_gets_a_labeled_placeholder_the_checker_reports(
    tmp_path, monkeypatch
):
    install_figures(monkeypatch, {"block": navy_block})
    document = small_document(
        Paragraph("Join the rows.", figure=FigureRequest("block", 150, 150, "Block 1 assembled")),
        Paragraph("Trim the unit.", figure=FigureRequest("hst_unit", 150, 150, "HST unit 1 trimmed")),
    )
    path = write(tmp_path, document)
    page = page_texts(path)[1]
    assert "placeholder" in page and "HST unit 1 trimmed" in page
    # Both figures fit page 2, the first page after the cover; only the HST one is
    # a placeholder, framed by an unfilled 150 x 150 pt outline.
    assert pc.placeholder_frames(path, MODEL) == [2]
    frames = [s for s in pc.read_pdf(path)[1].shapes
              if s.fill is None and abs(s.w - 150) < 1 and abs(s.h - 150) < 1]
    assert len(frames) == 1


def test_a_small_placeholder_grows_to_hold_its_words_whole(tmp_path):
    # A 36 x 30 pt request is narrower than the widest word of its text,
    # "placeholder:" (p 556, l 222, a 556, c 500, e 556, h 556, o 556, l 222, d 556,
    # e 556, r 333, colon 278: 5447 / 1000 em, 54.47 pt at 10 pt). The frame widens
    # to 54.47 + 6 + 6 = 66.47 pt. In its 54.47 pt column the text wraps to 6 lines:
    # "Figure", "placeholder:", "HST unit 1" (47.24 pt), "(half-square" (53.35 pt),
    # "triangle unit" (51.69 pt) and "figure)", so it grows to 6 x 13 + 6 + 6 = 90 pt.
    # The checker reads "placeholder" as a whole word, and every run of the text
    # lies inside the frame's outline.
    request = FigureRequest("hst_unit", 36, 30, "HST unit 1")
    path = write(tmp_path, small_document(Paragraph("Trim the unit.", figure=request)))
    assert pc.placeholder_frames(path, MODEL) == [2]
    page = pc.read_pdf(path)[1]
    (frame,) = [s for s in page.shapes if s.fill is None]
    assert (round(frame.w, 2), round(frame.h, 2)) == (66.47, 90)
    inside = [run for run in page.runs if frame.y0 < run.y < frame.y1]
    assert normalize(" ".join(run.text for run in inside)) == (
        "Figure placeholder: HST unit 1 (half-square triangle unit figure)")
    for run in inside:
        assert frame.x0 <= run.x and run.x + run.width <= frame.x1, run.text


def test_without_the_figures_module_every_figure_is_a_placeholder(tmp_path):
    # full_document requests 7 figures: cover render, symbol legend, two HST steps,
    # assembly, layout chart and coloring page.
    path = write(tmp_path, full_document())
    assert len(pc.placeholder_frames(path, MODEL)) == 7


class _BrokenFigures(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    """A qrep.export.figures whose own import fails on a missing dependency."""

    def find_spec(self, name, path, target=None):
        return importlib.machinery.ModuleSpec(name, self) if name == render.FIGURES_MODULE else None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        raise ModuleNotFoundError("No module named 'missing_dependency'", name="missing_dependency")


def test_a_figures_module_that_fails_to_import_is_not_mistaken_for_an_absent_one(monkeypatch):
    monkeypatch.delitem(sys.modules, render.FIGURES_MODULE)
    monkeypatch.setattr(sys, "meta_path", [_BrokenFigures(), *sys.meta_path])
    document = small_document(Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1")))
    with pytest.raises(ModuleNotFoundError, match="missing_dependency"):
        render.render_pdf(document)


@pytest.mark.parametrize(("extra_width", "extra_height"), [(10, 0), (0, 10)])
def test_a_drawing_larger_than_its_request_is_refused(monkeypatch, extra_width, extra_height):
    install_figures(monkeypatch, {"block": lambda request: Drawing(
        request.width + extra_width, request.height + extra_height)})
    document = small_document(Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1")))
    with pytest.raises(ValueError, match="larger"):
        render.render_pdf(document)


@pytest.mark.parametrize(
    "draw",
    [
        lambda request: Spacer(request.width, request.height),
        lambda request: [navy_block(request), Spacer(10, 10)],
    ],
)
def test_a_drawer_must_return_reportlab_drawings(monkeypatch, draw):
    # A flowable that is not a Drawing hides its labels from the L-10 and PS-05
    # checks, so the renderer refuses it.
    install_figures(monkeypatch, {"block": draw})
    document = small_document(Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1")))
    with pytest.raises(TypeError, match="Drawing"):
        render.render_pdf(document)


class SmallLabel(Widget):
    """A widget whose label exists only once the widget draws itself."""

    def draw(self):
        return Group(String(5, 5, "B3", fontName="Helvetica", fontSize=6))


def test_a_label_inside_a_widget_is_checked_too(monkeypatch):
    # L-10: a 6 pt label is below the 7 pt floor wherever it sits in the drawing.
    def draw(request):
        drawing = navy_block(request)
        drawing.add(SmallLabel())
        return drawing

    install_figures(monkeypatch, {"block": draw})
    document = small_document(Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1")))
    with pytest.raises(ValueError, match="7 pt"):
        render.render_pdf(document)


@pytest.mark.parametrize("font", [None, "Times-Roman", "Courier-Bold"])
def test_a_drawer_label_outside_the_helvetica_family_is_refused(monkeypatch, font):
    # G-03: one sans-serif family. A String with no fontName is Times-Roman in
    # reportlab, so a drawer that forgets the font breaks the rule.
    def draw(request):
        drawing = navy_block(request)
        drawing.add(String(10, 40, "B2", fontSize=8, **({"fontName": font} if font else {})))
        return drawing

    install_figures(monkeypatch, {"block": draw})
    document = small_document(Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1")))
    with pytest.raises(ValueError, match="Helvetica"):
        render.render_pdf(document)


def test_bold_and_oblique_helvetica_labels_are_allowed(tmp_path, monkeypatch):
    def draw(request):
        drawing = navy_block(request)
        for n, font in enumerate(["Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"]):
            drawing.add(String(10, 25 + 15 * n, f"B{n + 2}", fontName=font, fontSize=8))
        return drawing

    install_figures(monkeypatch, {"block": draw})
    path = write(tmp_path, small_document(
        Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1"))))
    assert all(label in page_texts(path)[1] for label in ["B2", "B3", "B4"])


def chart_parts(request):
    parts = []
    for n in (1, 2, 3):
        part = Drawing(request.width, request.height)
        part.add(String(20, 20, f"Chart part {n}", fontName="Helvetica", fontSize=10))
        parts.append(part)
    return parts


def test_a_figure_may_span_pages_in_parts_each_on_its_own_page(tmp_path, monkeypatch):
    # S10: a large layout chart splits across pages. Each 500 pt part with its 10 pt
    # spacer needs 510 pt, and two need 1,020 pt of a 666 pt frame, so the three
    # parts land on three pages in order.
    install_figures(monkeypatch, {"layout_chart": chart_parts})
    document = PatternDocument(NAME, [
        Section(SectionKind.COVER, [Paragraph("3 fabrics, plus backing")]),
        Section(SectionKind.LAYOUT_CHART,
                [Figure(FigureRequest("layout_chart", 400, 500, "the whole grid"))]),
    ])
    texts = page_texts(write(tmp_path, document))
    pages = [page_of(texts, f"Chart part {n}") for n in (1, 2, 3)]
    assert pages == [2, 3, 4]
    assert page_of(texts, "Layout chart") == 2


def test_a_figure_cited_from_text_must_be_one_drawing(monkeypatch):
    install_figures(monkeypatch, {"layout_chart": chart_parts})
    figure = FigureRequest("layout_chart", 400, 500, "the whole grid")
    with pytest.raises(ValueError, match="one drawing"):
        render.render_pdf(small_document(Paragraph("See the chart.", figure=figure)))


def test_a_figure_label_with_banned_text_is_refused(monkeypatch):
    def draw(request):
        drawing = navy_block(request)
        drawing.add(String(10, 40, "f3", fontName="Helvetica", fontSize=8))
        return drawing

    install_figures(monkeypatch, {"block": draw})
    document = small_document(Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1")))
    with pytest.raises(PatternTextError, match="fabric id"):
        render.render_pdf(document)


def test_cited_figures_are_numbered_in_reading_order(tmp_path):
    # G-05: Fig. 1, Fig. 2 and so on through the document, each cited from its text.
    # full_document cites four: the symbol legend (Before you begin), the two HST
    # steps (Making the units) and the assembly (Quilt assembly). The cover render,
    # layout chart and coloring page are not cited, so they carry no number.
    document = full_document()
    assert [f.label for f in document.cited_figures()] == [
        "pressing and line symbols", "HST unit 1, step 1", "HST unit 1, step 2",
        "the quilt center in rows"]
    joined = " ".join(page_texts(write(tmp_path, document)))
    citations = [
        "The figures use these symbols (Fig. 1).",
        "Draw a line corner to corner on each A2 square (Fig. 2).",
        "Sew on both sides of the line (Fig. 3).",
        "Lay out the blocks in 5 rows of 4 (Fig. 4).",
    ]
    positions = [joined.index(citation) for citation in citations]
    assert positions == sorted(positions)
    assert "Fig. 5" not in joined
    # Each cited figure carries its caption on a line of its own, in the same order.
    lines = pc.build_doc(pc.read_pdf(tmp_path / "pattern.pdf"), MODEL).lines
    assert [ln.text for ln in lines if re.fullmatch(r"Fig\. \d+", ln.text)] == [
        "Fig. 1", "Fig. 2", "Fig. 3", "Fig. 4"]


def test_only_the_cover_render_layout_chart_and_coloring_page_stand_uncited():
    # G-05: a step cites every figure; the cover render (S1), the layout chart (S10)
    # and the coloring page (S11) print on their own, without a Fig. number.
    for kind in ["cover_render", "layout_chart", "coloring_page"]:
        Figure(FigureRequest(kind, 100, 100, "the quilt"))
    for kind in ["hst_unit", "block", "sub_unit", "symbol_legend"]:
        with pytest.raises(ValueError, match="cited"):
            Figure(FigureRequest(kind, 100, 100, "the quilt"))


def test_a_request_with_a_dict_subject_can_key_a_set():
    request = FigureRequest("block", 150, 150, "Block 1", subject={"block": 1})
    assert request in {request}


def test_a_nested_drawing_render_scale_does_not_count_for_label_size(monkeypatch):
    # renderPDF scales only the drawing it is given; a nested Drawing draws as a
    # plain group, so its 4 pt label prints at 4 pt though its renderScale is 2.
    def draw(request):
        drawing = navy_block(request)
        inner = Drawing(40, 40)
        inner.renderScale = 2
        inner.add(String(5, 5, "B2", fontName="Helvetica", fontSize=4))
        drawing.add(inner)
        return drawing

    install_figures(monkeypatch, {"block": draw})
    document = small_document(Paragraph("Join.", figure=FigureRequest("block", 90, 90, "Block 1")))
    with pytest.raises(ValueError, match="7 pt"):
        render.render_pdf(document)


def test_figure_requests_name_a_known_kind_a_size_and_a_label():
    with pytest.raises(ValueError, match="kind"):
        FigureRequest("watercolor", 100, 100, "a quilt")
    with pytest.raises(ValueError, match="size"):
        FigureRequest("block", 0, 100, "Block 1")
    with pytest.raises(ValueError, match="label"):
        FigureRequest("block", 100, 100, " ")


def test_a_figure_fits_the_page_frame_with_room_for_a_line_and_its_caption(tmp_path):
    # The frame is 504 pt wide (612 - 2 x 54) and 666 pt tall; a figure leaves 86 pt
    # for its headings, one line of text and its caption (render.py), so it may be up
    # to 666 - 86 = 580 pt tall.
    write(tmp_path, small_document(Figure(FigureRequest("layout_chart", 504, 580, "rows 1 to 80"))))
    for width, height in [(505, 300), (400, 581)]:
        figure = Figure(FigureRequest("layout_chart", width, height, "rows 1 to 80"))
        with pytest.raises(ValueError, match="fit"):
            render.render_pdf(small_document(figure))


# ---------------------------------------------------------------- formatters (C-09, C-10)


@pytest.mark.parametrize(
    ("eighths", "text"),
    [
        (12, '1 1/2"'),  # 12 / 8 = 1 4/8 = 1 1/2
        (30, '3 3/4"'),  # 30 / 8 = 3 6/8 = 3 3/4
        (2, '1/4"'),  # 2 / 8 = 1/4, no whole part
        (7, '7/8"'),  # already lowest terms
        (20, '2 1/2"'),  # 20 / 8 = 2 4/8 = 2 1/2
        (600, '75"'),  # 600 / 8 = 75, no fraction
    ],
)
def test_lengths_print_as_mixed_eighths_with_an_inch_mark(eighths, text):
    assert inches(eighths) == text


def test_dimensions_use_x_with_spaces_and_rectangles_put_the_short_side_first():
    # C-10: 16 e = 2" and 64 e = 8", short side first in either argument order.
    assert rectangle(64, 16) == '2" x 8"'
    assert rectangle(16, 64) == '2" x 8"'
    # The quilt is width x height: 600 e = 75", 720 e = 90" (the DIC finished size).
    assert size(600, 720) == '75" x 90"'
    assert square(32) == '4" square'


@pytest.mark.parametrize("bad", [1.5, -8, True])
def test_lengths_must_be_whole_nonnegative_eighths(bad):
    with pytest.raises((TypeError, ValueError)):
        inches(bad)


# ---------------------------------------------------------------- banned text (PS-05, PS-06)

BANNED = [
    "This quilt has difficulty 16.",  # engine-15: the booklet printed difficulty 16
    "Allow 3968 minutes.",  # engine-15: and 3968 minutes
    "The strip strategy suits it.",
    "It uses the historical method.",
    "It follows a heuristic.",
    "There are 2479 pieces in all.",  # GAP-04: the DIC piece total
    "The piece count is large.",
    "Cut f0 into squares.",  # an internal fabric id
    "Its color is #3b5b92.",
    'Cut 1.5" squares.',  # decimal size
    'Cut 1-1/2" squares.',  # hyphenated fraction
    "Cut 1½ inch squares.",  # fraction glyph
    'Cut 6/8" strips.',  # 6/8 is 3/4 in lowest terms
    'Cut 1/3" strips.',  # thirds are not eighths
    'Cut 2"x8" rectangles.',  # C-10 needs " x "
    'Cut 2" X 8" rectangles.',
    "Printed 2026-10-13.",  # G-02: no date
    "Printed 10/13/2026.",
    "Printed October 13, 2026.",
    'Cut 3/16" strips.',  # sixteenths are finer than C-09's eighths
    'Cut 2" × 8" rectangles.',  # a multiplication sign is not C-10's x
    "Cut (6) 2 1/2 x WOF strips.",  # C-07: a length without its inch mark
    "Trim to 6 1/2 square.",
    'Cut .5" strips.',  # a decimal with no leading digit
    "Printed 13 October 2026.",
    "Printed Oct 13, 2026.",
    "Pieces: 2479",
    "The quilt uses 2,479 pieces.",  # the guard reads 100 or more pieces as a total
    "Cut 120 pieces from the strips.",
    'Cut 1\u22152" strips.',  # the division slash is a fraction glyph
    'Cut 1\u20131/2" squares.',  # an en dash between whole and fraction
    'Cut 1\u20141/2" squares.',  # an em dash
    'Cut 2" by 8" rectangles.',  # C-10: a dimension uses " x "
    "Cut 2 by 8 rectangles.",
    "Cut (6) 2 x WOF strips.",  # C-07: a whole-inch length still carries its mark
    "Trim the block to 6 square.",
    'Cut (2) 2 x 8" rectangles.',
    'Cut (2) 8" x 2" rectangles.',  # C-10: short side first
    "Cut (4) 2\N{RIGHT DOUBLE QUOTATION MARK} squares.",  # C-07: a straight quote
    "Printed October 2026.",
    "Printed October 13th, 2026.",
    "Printed 13-10-2026.",
]


@pytest.mark.parametrize("text", BANNED)
def test_banned_text_is_refused(text):
    with pytest.raises(PatternTextError):
        check_text(text)
    with pytest.raises(PatternTextError):
        render.render_pdf(small_document(Paragraph(text)))


@pytest.mark.parametrize(
    "block",
    [
        Subheading("Difficulty notes"),
        Table(("Fabric", "Yards"), [("A", "1.5 yd")]),
        Table(("Fabric", "Minutes"), [("A", "1 yd")]),
        Steps([Step("Cut the strips.", details=("A1: subcut f2 strips.",))]),
        PrintScaleSquare("Printed 2026-10-13 at 100 percent."),
        Figure(FigureRequest("cover_render", 100, 100, "a modern quilt")),
        Steps([Step("Use the historical method.")]),
        Steps([Step("Join.", figure=FigureRequest("block", 90, 90, "difficulty 3"))]),
        Paragraph("Join.", figure=FigureRequest("block", 90, 90, "f3 corner")),
    ],
)
def test_every_block_that_prints_text_is_checked(block):
    with pytest.raises(PatternTextError):
        render.render_pdf(small_document(block))


def test_allowed_text_passes():
    # The guard's own limits: piece counts in parentheses and totals under 100 are
    # not piece totals; a piece label before "square" is not a length; C-07 lets a
    # centimeter size the user typed print as typed; ordinals are not dates.
    for text in ['Cut (6) 2 1/2" x WOF strips.', "Sew in rows 1 to 4.", '6 1/2" x 8 3/4"',
                 "Buy 3/4 yd.", 'Cut (120) 2 1/2" squares.', "Press the seam (Fig. 2). 3 rows",
                 "Make 40 pieces.", "Sew the rows one by one.", 'Cut (2) 2" x 8" rectangles.',
                 "Draw a line on each A2 square.", "Made for a 152.4 cm wide bed.",
                 "Sew the 4th row to the 3rd."]:
        check_text(text)


@pytest.mark.parametrize(
    "name",
    ["Modern Lanterns", "Rows of f2", "Rows 2x8", "Waltz in 3/4 Time", "Lantern\rRows",
     "Lantern  Rows", " Lantern Rows", "Lantern Rows "],
)
def test_the_name_obeys_every_text_rule_and_is_one_clean_line(name):
    # PS-05 bans its items anywhere, and the name prints on every page (G-02), so no
    # rule exempts it. A control character or an extra space would print as it is in
    # the footer while the title collapses it.
    with pytest.raises(ValueError):
        PatternDocument(name, [Section(SectionKind.COVER)])


def test_a_fraction_glyph_is_refused_as_a_fraction_glyph():
    # The division slash, the fraction slash and one eighth are outside cp1252 too;
    # the guard names the rule they break, not the encoding.
    for code in (0x2215, 0x2044, 0x215B):
        with pytest.raises(PatternTextError, match="fraction glyph"):
            check_text(f'Cut 1{chr(code)}2" strips.')


@pytest.mark.parametrize(
    "build",
    [
        lambda: Step("Cut the strips.", details="A1: subcut the strips."),
        lambda: Table("Yards", [("1 yd",) * 5]),
        lambda: Table(("Yards",), "1 yd"),
        lambda: Steps("Cut the strips."),
    ],
)
def test_a_string_where_a_sequence_belongs_is_refused(build):
    # tuple() would split the string into one-character lines or cells.
    with pytest.raises(TypeError):
        build()


def test_text_helvetica_cannot_print_is_refused():
    # Built-in Helvetica prints the WinAnsi (cp1252) characters only; others print
    # as empty boxes. L and a with ogonek are outside it, in the text or the name.
    with pytest.raises(PatternTextError, match="Helvetica"):
        check_text("\u0141\u0105ka green")
    with pytest.raises(PatternTextError):
        render.render_pdf(small_document(Paragraph("\u0141\u0105ka green")))
    with pytest.raises(PatternTextError):
        full_document(name="\u0141\u0105ka Rows")


def test_an_accented_name_prints_and_extracts_intact(tmp_path):
    # e with acute is in cp1252, so the name prints in the title and every footer.
    name = "Caf\u00e9 Lantern Rows"
    texts = page_texts(write(tmp_path, full_document(name=name)))
    assert texts[0].count(name) == 2
    assert all(name in text for text in texts)


def test_a_table_may_have_no_header_row(tmp_path):
    # A piece list (S5, S6) is rows only; an empty header prints no header row. A
    # header row is a 12 pt line with 2 + 2 pt padding, 16 pt, so without one the
    # same first row sits 16 pt higher on the page.
    rows = [("A1", "(12) squares"), ("B1", "(4) squares")]

    def first_row_baseline(header):
        path = write(tmp_path, small_document(Table(header, rows)), f"header{len(header)}.pdf")
        return next(run.y for run in pc.read_pdf(path)[1].runs if run.text.startswith("A1"))

    assert round(first_row_baseline(()) - first_row_baseline(("Piece", "Count")), 2) == 16
    with pytest.raises(ValueError):
        Table((), [])


# ---------------------------------------------------------------- extractable text (G-10, PS-41)


def test_wrapped_lines_sit_one_leading_apart_where_the_checker_reads_them(tmp_path):
    # A paragraph of about 310 characters wraps to three or four lines in the
    # 504 pt column, and its baselines step down by the 13 pt body leading. pypdf,
    # which A11's checker reads positions through, scales a T* line advance by the
    # font size, so the renderer advances with Td; the checker sees 13 pt steps.
    text = " ".join(["Sew the long seam slowly."] * 12)
    pages = pc.read_pdf(write(tmp_path, small_document(Paragraph(text))))
    baselines = sorted({round(run.y, 2) for run in pages[1].runs if "seam" in run.text},
                       reverse=True)
    assert len(baselines) >= 3
    assert [round(a - b, 2) for a, b in zip(baselines, baselines[1:])] == [13] * (
        len(baselines) - 1)


def test_every_printed_string_extracts_as_text(tmp_path):
    document = full_document()
    joined = " ".join(page_texts(write(tmp_path, document)))
    for text in document.texts():
        # A text that cites a figure prints "(Fig. N)" before its closing mark.
        assert normalize(text).rstrip(".:!?") in joined, text
    assert NAME in joined
