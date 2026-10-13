"""Lays a PatternDocument out as the pattern PDF (PATTERN-SPEC section 2.0).

The page rules every section shares: US Letter portrait with 3/4" side margins
(G-01); a footer on every page with the name, "page N of M" and the QREP
version, and no date (G-02); Helvetica at or above the L-10 sizes (G-03); the
cover alone on page 1, each step on the page of its figure and table rows that
never split (G-04); cited figures numbered in reading order (G-05); and the
same bytes for the same document on every run (G-11, PS-04).

Figures come from qrep.export.figures (A5a, A5b). Its DRAWERS mapping takes a
figure kind to a function that receives the FigureRequest and returns a
reportlab Drawing no larger than the request. A kind it does not provide, or
the module's absence, gets a labeled placeholder frame, which the A11 checker
counts (tests/pattern_checks.py:placeholder_frames).
"""

from __future__ import annotations

import importlib
import io
import itertools
from collections.abc import Callable, Iterator, Mapping
from functools import partial
from xml.sax.saxutils import escape

from reportlab import rl_config
from reportlab.graphics.shapes import String
from reportlab.lib.colors import HexColor, black
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.rl_accel import fp_str
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfgen.textobject import PDFTextObject
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Spacer,
    TableStyle,
)
from reportlab.platypus import Paragraph as TextFlowable
from reportlab.platypus import Table as TableFlowable

from qrep import __version__
from qrep.export.pattern.document import (
    FIGURE_KINDS,
    Block,
    Figure,
    FigureRequest,
    Paragraph,
    PatternDocument,
    PrintScaleSquare,
    Steps,
    Subheading,
    Swatch,
    Table,
    check_text,
)

PAGE_WIDTH, PAGE_HEIGHT = 612, 792
SIDE_MARGIN = 54
TOP_MARGIN = 54
BOTTOM_MARGIN = 72
FOOTER_BASELINE = 36
CONTENT_WIDTH = PAGE_WIDTH - 2 * SIDE_MARGIN
FRAME_HEIGHT = PAGE_HEIGHT - TOP_MARGIN - BOTTOM_MARGIN

FONT = "Helvetica"
BOLD = "Helvetica-Bold"
BODY_SIZE = 10
# Tables print at the body size, above L-10's 9 pt floor: A11's PS-42 reads a
# wrapped cell's lone line as body text, which needs 10 pt.
TABLE_SIZE = 10
LABEL_MIN = 7
# A footer line holding one run, such as a long name set above the page mark,
# is body text to PS-42 too.
FOOTER_SIZE = 10
LEADING = 13
INDENT = 18
# A figure leaves room on its page for one line of text and its caption.
MAX_FIGURE_HEIGHT = FRAME_HEIGHT - 3 * LEADING

FIGURES_MODULE = "qrep.export.figures"

_OUTLINE = HexColor("#333333")
_FRAME = HexColor("#808080")

_BODY = ParagraphStyle("body", fontName=FONT, fontSize=BODY_SIZE, leading=LEADING, spaceAfter=6)
_TITLE = ParagraphStyle("title", fontName=BOLD, fontSize=28, leading=34, spaceAfter=18)
_HEADING = ParagraphStyle(
    "heading", fontName=BOLD, fontSize=16, leading=20, spaceBefore=14, spaceAfter=8, keepWithNext=1
)
_SUBHEADING = ParagraphStyle(
    "subheading", fontName=BOLD, fontSize=12, leading=15, spaceBefore=8, spaceAfter=4, keepWithNext=1
)
_STEP = ParagraphStyle(
    "step", parent=_BODY, leftIndent=INDENT, firstLineIndent=-INDENT, spaceAfter=3
)
_DETAIL = ParagraphStyle("detail", parent=_BODY, leftIndent=2 * INDENT, spaceAfter=3)
_CELL = ParagraphStyle("cell", fontName=FONT, fontSize=TABLE_SIZE, leading=12)
_CELL_HEAD = ParagraphStyle("cellhead", parent=_CELL, fontName=BOLD)
_CAPTION = ParagraphStyle("caption", parent=_BODY, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10)
_PLACEHOLDER = ParagraphStyle("placeholder", parent=_BODY, alignment=TA_CENTER, spaceAfter=0)

Drawer = Callable[[FigureRequest], Flowable]


def render_pdf(document: PatternDocument) -> bytes:
    """The document as PDF bytes; identical documents give identical bytes."""
    for text in document.texts():
        check_text(text, document.name)
    if stringWidth(document.name, FONT, FOOTER_SIZE) > CONTENT_WIDTH:
        raise ValueError(f"the pattern name {document.name!r} is too wide for one footer line")
    probe = _PageProbe()
    story = _story(document, _drawers(), probe)
    out = io.BytesIO()
    template = BaseDocTemplate(
        out,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        leftMargin=SIDE_MARGIN,
        rightMargin=SIDE_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=document.name,
        author="QREP",
        creator="QREP",
        invariant=1,
    )
    frame = Frame(
        SIDE_MARGIN, BOTTOM_MARGIN, CONTENT_WIDTH, FRAME_HEIGHT,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="body",
    )
    template.addPageTemplates([PageTemplate(id="page", frames=[frame])])
    # The canvas takes invariant=1 from the template, which fixes the timestamp
    # and the document id; pdfdoc also reads the module setting, so it is pinned
    # for the build and restored after.
    previous = rl_config.invariant
    rl_config.invariant = 1
    try:
        template.build(story, canvasmaker=partial(_FooterCanvas, pattern_name=document.name))
    finally:
        rl_config.invariant = previous
    if probe.page != 1:
        raise ValueError("the cover does not fit on page 1, which it must have to itself")
    return out.getvalue()


def _drawers() -> Mapping[str, Drawer]:
    try:
        module = importlib.import_module(FIGURES_MODULE)
    except ModuleNotFoundError as missing:
        # Only the module's own absence means "no drawers yet"; a dependency it
        # fails to import is a bug to surface, not a reason for placeholders.
        if missing.name != FIGURES_MODULE:
            raise
        return {}
    return getattr(module, "DRAWERS", {})


def _story(document: PatternDocument, drawers: Mapping[str, Drawer], probe: Flowable) -> list:
    numbers = itertools.count(1)
    cover, *rest = document.sections
    story = [TextFlowable(escape(document.name), _TITLE)]
    for block in cover.blocks:
        story += _block(block, numbers, drawers, document.name)
    story.append(probe)
    if rest:
        story.append(PageBreak())
    for section in rest:
        story.append(TextFlowable(escape(section.kind.value), _HEADING))
        for block in section.blocks:
            story += _block(block, numbers, drawers, document.name)
    return story


def _block(block: Block, numbers: Iterator[int], drawers: Mapping[str, Drawer], name: str) -> list:
    if isinstance(block, Subheading):
        return [_subheading(block)]
    if isinstance(block, Paragraph):
        style = ParagraphStyle(f"body{block.indent}", parent=_BODY, leftIndent=block.indent * INDENT)
        if block.figure is None:
            return [TextFlowable(escape(block.text), style)]
        number = next(numbers)
        parts = [TextFlowable(escape(_cite(block.text, number)), style)]
        return [_together(parts + _figure(block.figure, number, drawers, name), "the paragraph")]
    if isinstance(block, Steps):
        flowables = []
        for n, step in enumerate(block.items, start=1):
            number = next(numbers) if step.figure is not None else None
            parts = [TextFlowable(f"{n}. {escape(_cite(step.text, number))}", _STEP)]
            parts += [TextFlowable(escape(detail), _DETAIL) for detail in step.details]
            if step.figure is not None:
                parts += _figure(step.figure, number, drawers, name)
            flowables.append(_together(parts, f"step {n}", check=step.figure is not None))
        return flowables
    if isinstance(block, Table):
        return [_table(block), Spacer(1, 10)]
    if isinstance(block, Figure):
        return [KeepTogether(_figure(block.request, None, drawers, name))]
    if isinstance(block, PrintScaleSquare):
        return [_print_scale_square(block), Spacer(1, 10)]
    raise TypeError(f"no layout for block {block!r}")


def _cite(text: str, number: int | None) -> str:
    """Text that cites its figure: "Sew the pair (Fig. 3)." (G-05)."""
    if number is None:
        return text
    text = text.rstrip()
    if text and text[-1] in ".:!?":
        return f"{text[:-1]} (Fig. {number}){text[-1]}"
    return f"{text} (Fig. {number})"


def _together(parts: list, what: str, check: bool = True) -> KeepTogether:
    # KeepTogether falls back to splitting a group taller than a page, so a step
    # and its figure that cannot share one page are refused rather than split.
    if check:
        height = sum(
            p.wrap(CONTENT_WIDTH, FRAME_HEIGHT)[1] + p.getSpaceBefore() + p.getSpaceAfter()
            for p in parts
        )
        if height > FRAME_HEIGHT:
            raise ValueError(f"{what} and its figure do not fit on one page ({height:.0f} pt)")
    return KeepTogether(parts)


# ---------------------------------------------------------------- figures


def _figure(request: FigureRequest, number: int | None, drawers: Mapping[str, Drawer],
            name: str) -> list:
    if request.width > CONTENT_WIDTH or request.height > MAX_FIGURE_HEIGHT:
        raise ValueError(
            f"figure {request.label!r} ({request.width:g} x {request.height:g} pt) does not fit "
            f"the {CONTENT_WIDTH} x {MAX_FIGURE_HEIGHT} pt figure area"
        )
    draw = drawers.get(request.kind)
    body = _Placeholder(request) if draw is None else _drawn(draw, request, name)
    if number is None:
        return [body, Spacer(1, 10)]
    return [body, TextFlowable(f"Fig. {number}", _CAPTION)]


def _drawn(draw: Drawer, request: FigureRequest, name: str) -> Flowable:
    drawing = draw(request)
    width, height = drawing.wrap(CONTENT_WIDTH, FRAME_HEIGHT)
    if width > request.width + 0.5 or height > request.height + 0.5:
        raise ValueError(
            f"the {request.kind} drawer returned {width:g} x {height:g} pt, larger than the "
            f"{request.width:g} x {request.height:g} pt requested for {request.label!r}"
        )
    for label in _strings(drawing):
        if label.fontSize < LABEL_MIN:
            raise ValueError(
                f"figure label {label.text!r} in {request.label!r} is {label.fontSize:g} pt; "
                f"L-10 needs at least {LABEL_MIN} pt"
            )
        check_text(label.text, name)
    drawing.hAlign = "CENTER"
    return drawing


def _strings(node) -> Iterator[String]:
    if isinstance(node, String):
        yield node
    for child in getattr(node, "contents", ()):
        yield from _strings(child)


class _Placeholder(Flowable):
    """A frame the size of the requested figure that says which figure is missing."""

    def __init__(self, request: FigureRequest):
        super().__init__()
        self.width, self.height = request.width, request.height
        self.text = f"Figure placeholder: {request.label} ({FIGURE_KINDS[request.kind]})"
        self.hAlign = "CENTER"

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        canv = self.canv
        canv.saveState()
        canv.setStrokeColor(_FRAME)
        canv.setLineWidth(0.75)
        canv.rect(0, 0, self.width, self.height, stroke=1, fill=0)
        text = TextFlowable(escape(self.text), _PLACEHOLDER)
        _, height = text.wrap(max(self.width - 12, 1), self.height)
        text.drawOn(canv, 6, max((self.height - height) / 2, 0))
        canv.restoreState()


# ---------------------------------------------------------------- tables, swatches, test square


class _Swatch(Flowable):
    """The fabric's color in a small square with a thin dark outline (C-04, G-08)."""

    SIDE = 10

    def __init__(self, color: str):
        super().__init__()
        self.color = HexColor(color)
        self.width = self.height = self.SIDE

    def wrap(self, available_width, available_height):
        return self.SIDE, self.SIDE

    def draw(self):
        self.canv.saveState()
        self.canv.setFillColor(self.color)
        self.canv.setStrokeColor(_OUTLINE)
        self.canv.setLineWidth(0.5)
        self.canv.rect(0, 0, self.SIDE, self.SIDE, stroke=1, fill=1)
        self.canv.restoreState()


def _table(block: Table) -> TableFlowable:
    data = [[TextFlowable(escape(text), _CELL_HEAD) for text in block.header]]
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, _FRAME),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for r, row in enumerate(block.rows, start=1):
        cells = []
        for c, cell in enumerate(row):
            if isinstance(cell, Swatch):
                cells.append(_Swatch(cell.color))
                # Against the next cell, so the swatch reads as that letter's (C-04).
                style.append(("ALIGN", (c, r), (c, r), "RIGHT"))
            else:
                cells.append(TextFlowable(escape(cell), _CELL))
        data.append(cells)
    weights = block.widths or (1,) * len(block.header)
    widths = [CONTENT_WIDTH * w / sum(weights) for w in weights]
    # reportlab splits a table between rows only, never inside one (G-04), and
    # repeats the header row on each page the table continues on.
    table = TableFlowable(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle(style))
    return table


def _subheading(block: Subheading) -> Flowable:
    text = TextFlowable(escape(block.text), _SUBHEADING)
    if block.swatch is None:
        return text
    row = TableFlowable([[_Swatch(block.swatch), text]], colWidths=[16, CONTENT_WIDTH - 16])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    row.keepWithNext = 1
    return row


class _Square(Flowable):
    """72 x 72 pt, which prints as 1" at 100 percent (G-09, PS-38)."""

    def wrap(self, available_width, available_height):
        return 72, 72

    def draw(self):
        self.canv.saveState()
        self.canv.setStrokeColor(black)
        self.canv.setLineWidth(0.5)
        self.canv.rect(0, 0, 72, 72, stroke=1, fill=0)
        self.canv.restoreState()


def _print_scale_square(block: PrintScaleSquare) -> Flowable:
    row = TableFlowable(
        [[_Square(), TextFlowable(escape(block.note), _BODY)]],
        colWidths=[84, CONTENT_WIDTH - 84],
    )
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return row


# ---------------------------------------------------------------- pages


class _PageProbe(Flowable):
    """Records the page it lands on; it sits after the cover's last block."""

    def __init__(self):
        super().__init__()
        self.page = None

    def wrap(self, available_width, available_height):
        return 0, 0

    def draw(self):
        self.page = self.canv.getPageNumber()


class _LineText(PDFTextObject):
    """Moves to the next line with "0 -TL Td" instead of T*.

    The two mean the same (PDF 32000-1 section 9.4.2), but pypdf 6.14 scales TL
    by the font size, so it reads every wrapped line after a paragraph's first
    far below where it prints, and A11's checker reads positions through pypdf.
    """

    def _textOut(self, text, TStar=0):
        self._code.append(self._formatText(text))
        if TStar:
            # Its own code item: moveCursor folds a trailing lone Td into the
            # next move, and two Td moves add.
            self._code.append(f"0 {fp_str(-self._leading)} Td")


class _FooterCanvas(Canvas):
    """Holds every page until save, when the page count M is known (G-02)."""

    def __init__(self, *args, pattern_name: str, **kwargs):
        super().__init__(*args, **kwargs)
        self._pattern_name = pattern_name
        self._held_pages: list[dict] = []

    def beginText(self, x=0, y=0, direction=None):
        return _LineText(self, x, y, direction=direction)

    def showPage(self):
        self._held_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._held_pages)
        for state in self._held_pages:
            self.__dict__.update(state)
            self._footer(total)
            super().showPage()
        super().save()

    def _footer(self, total: int) -> None:
        mark = f"page {self.getPageNumber()} of {total}"
        widest = stringWidth(f"page {total} of {total}", FONT, FOOTER_SIZE)
        room = PAGE_WIDTH / 2 - widest / 2 - 12 - SIDE_MARGIN
        # A name too long to sit left of the page mark gets the line above it, on
        # every page alike, so the footer still holds the whole name.
        fits = stringWidth(self._pattern_name, FONT, FOOTER_SIZE) <= room
        self.saveState()
        self.setFont(FONT, FOOTER_SIZE)
        self.setFillColor(black)
        self.drawCentredString(PAGE_WIDTH / 2, FOOTER_BASELINE, mark)
        self.drawRightString(PAGE_WIDTH - SIDE_MARGIN, FOOTER_BASELINE, f"QREP {__version__}")
        name_y = FOOTER_BASELINE if fits else FOOTER_BASELINE + FOOTER_SIZE + 3
        self.drawString(SIDE_MARGIN, name_y, self._pattern_name)
        self.restoreState()

