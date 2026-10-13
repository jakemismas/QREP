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
from reportlab.lib.colors import HexColor

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


def run_render(clock: int, mode: str) -> bytes:
    # reportlab stamps the PDF with the clock unless invariant mode is on, and it uses
    # SOURCE_DATE_EPOCH when that is set, so the variable is cleared to control it.
    env = {k: v for k, v in os.environ.items() if k != "SOURCE_DATE_EPOCH"}
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
    first = run_render(1_000_000_000, "pattern")
    assert first.startswith(b"%PDF")
    assert run_render(1_000_086_400, "pattern") == first
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
    # G-04: a heading never sits alone at the foot of a page. Each heading here is
    # paired with the first text after it in full_document; a subheading between
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
    with pytest.raises(ValueError):
        PatternDocument(NAME, [Section(kind) for kind in kinds])


def test_a_cover_that_overflows_page_1_is_refused():
    # The cover is alone on page 1 (G-09, X-08), so a cover that needs a second page
    # is a builder error, never a cover that spills onto page 2. At 13 pt per line,
    # 80 paragraphs need over 1,000 pt against a 666 pt frame (792 - 54 - 72).
    cover = [Paragraph(f"Cover line {n}.") for n in range(80)]
    document = PatternDocument(
        NAME, [Section(SectionKind.COVER, cover), Section(SectionKind.FABRIC_REQUIREMENTS)]
    )
    with pytest.raises(ValueError, match="page 1"):
        render.render_pdf(document)


def test_each_step_stays_on_the_page_of_its_figure(tmp_path):
    # G-04, PS-44. The frame is 792 - 54 - 72 = 666 pt tall. Each step here is one
    # 13 pt line, a 260 pt figure and its 13 pt caption, with spacing about 300 pt
    # all told. After the heading (about 25 pt) two steps fill 625 pt, which leaves
    # about 41 pt: room for the third step's line but not its figure. A flow that
    # does not keep them together prints that line at the foot of the page and its
    # figure on the next; the same happens on every page after.
    steps = [
        Step(f"Step marker {n}: sew the pair.",
             figure=FigureRequest("hst_unit", 300, 260, f"figure marker {n}"))
        for n in range(1, 8)
    ]
    texts = page_texts(write(tmp_path, small_document(Steps(steps))))
    # Two steps a page from page 2 on: 7 steps need pages 2 to 5.
    assert len(texts) >= 5
    for n in range(1, 8):
        # G-04: numbered from 1, each step on the page of its figure.
        assert page_of(texts, f"{n}. Step marker {n}:") == page_of(texts, f"figure marker {n}")


def test_a_one_line_step_and_a_figure_of_the_full_627_pt_share_a_page(tmp_path):
    # The step line (13 pt and 3 pt after), the figure (627 pt) and the caption
    # (3 pt before, 13 pt) need 13 + 3 + 627 + 3 + 13 = 659 pt of the 666 pt frame;
    # the caption's space after never has to fit.
    step = Step("Step marker: sew.", figure=FigureRequest("hst_unit", 300, 627, "figure marker"))
    texts = page_texts(write(tmp_path, small_document(Steps([step]))))
    assert page_of(texts, "1. Step marker: sew") == page_of(texts, "figure marker")


def test_a_step_too_tall_to_share_a_page_with_its_figure_is_refused():
    # "Sew. " is 22.78 pt at 10 pt, so 120 of them (2,734 pt) wrap to 6 or more lines
    # of the 486 pt step column (504 - 18 indent): at least 78 pt. With the 620 pt
    # figure, which fits the 627 pt figure area, and the 13 pt caption, the step
    # needs at least 78 + 620 + 13 = 711 pt of the 666 pt frame.
    step = Step("Sew. " * 120, figure=FigureRequest("hst_unit", 300, 620, "a tall figure"))
    with pytest.raises(ValueError, match="one page"):
        render.render_pdf(small_document(Steps([step])))


def test_a_table_row_never_splits_across_pages(tmp_path):
    # G-04: each row's long cell wraps in a 432 pt column (504 pt x 6/7). Rows carry
    # 5, 10 or 15 filler sentences, about 3, 6 or 9 lines (40, 76 or 112 pt), so a
    # page break can fall inside a row, where a table allowed to split rows would
    # split one. 40 rows of about 76 pt on average need about 3,000 pt, over four
    # 666 pt frames. A row's first and last words share a page.
    filler = "The long cell keeps going so that it wraps. " * 5
    rows = [(str(n), f"Row {n} begins. {filler * (1 + n % 3)}Row {n} ends.")
            for n in range(1, 41)]
    texts = page_texts(write(tmp_path, small_document(Table(("Row", "Text"), rows, widths=(1, 6)))))
    assert len(texts) >= 5
    for n in range(1, 41):
        assert page_of(texts, f"Row {n} begins.") == page_of(texts, f"Row {n} ends.")


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


def test_figure_requests_name_a_known_kind_a_size_and_a_label():
    with pytest.raises(ValueError, match="kind"):
        FigureRequest("watercolor", 100, 100, "a quilt")
    with pytest.raises(ValueError, match="size"):
        FigureRequest("block", 0, 100, "Block 1")
    with pytest.raises(ValueError, match="label"):
        FigureRequest("block", 100, 100, " ")


def test_a_figure_fits_the_page_frame_with_room_for_a_line_and_its_caption(tmp_path):
    # The frame is 504 pt wide (612 - 2 x 54) and 666 pt tall; a figure leaves 3 lines
    # of 13 pt for its step and caption, so it may be up to 666 - 39 = 627 pt tall.
    write(tmp_path, small_document(Figure(FigureRequest("layout_chart", 504, 627, "rows 1 to 80"))))
    for width, height in [(505, 300), (400, 628)]:
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


def test_allowed_text_passes_and_the_name_is_exempt(tmp_path):
    # PS-05 reads the text with the pattern name left out, so a name may hold a
    # word the body may not.
    for text in ['Cut (6) 2 1/2" x WOF strips.', "Sew in rows 1 to 4.", '6 1/2" x 8 3/4"',
                 "Buy 3/4 yd."]:
        check_text(text)
    path = write(tmp_path, small_document(Paragraph("Lay out the Modern Lanterns blocks."),
                                          name="Modern Lanterns"))
    assert "Modern Lanterns" in page_texts(path)[0]
    assert "Lay out the Modern Lanterns blocks." in page_texts(path)[1]
    with pytest.raises(PatternTextError):
        check_text("Lay out the Modern Lanterns blocks.")


def test_a_table_may_have_no_header_row(tmp_path):
    # A piece list (S5, S6) is rows only; an empty header prints no header row.
    table = Table((), [("A1", "(12) squares"), ("B1", "(4) squares")])
    texts = page_texts(write(tmp_path, small_document(table)))
    assert "A1 (12) squares B1 (4) squares" in texts[1]
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
