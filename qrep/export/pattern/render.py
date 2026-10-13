"""Lays a PatternDocument out as the pattern PDF (PATTERN-SPEC section 2.0).

The page rules every section shares: US Letter portrait with 3/4" side margins
(G-01); a footer on every page with the name, "page N of M" and the QREP
version, and no date (G-02); Helvetica at or above the L-10 sizes (G-03); the
cover alone on page 1, each step on the page of its figure and table rows that
never split (G-04); cited figures numbered in reading order (G-05); and the
same bytes for the same document on every run (G-11, PS-04).

Figures come from qrep.export.figures (A5a, A5b). Its DRAWERS mapping takes a
figure kind to a function that receives the FigureRequest and returns a
reportlab Drawing no larger than the request, or a list of them for a figure
that spans pages. Its labels are Helvetica at 7 pt or more. A kind it does not
provide, or the module's absence, gets a labeled placeholder frame, which the
A11 checker counts (tests/pattern_checks.py:placeholder_frames).
"""

from __future__ import annotations

import importlib
import io
import itertools
import math
import os
import re
import threading
from collections.abc import Callable, Iterator, Mapping
from functools import partial
from xml.sax.saxutils import escape

from reportlab import rl_config
from reportlab.graphics.shapes import Drawing, String, UserNode
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
# G-03: one sans-serif family, in any of its built-in weights and slants.
LABEL_FONTS = frozenset({FONT, BOLD, "Helvetica-Oblique", "Helvetica-BoldOblique"})
TITLE_SIZE = 28
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
# Space after a table, a figure or the test square. It is spaceAfter, never a
# trailing Spacer: reportlab drops spaceAfter at a page end, but a Spacer that no
# longer fits starts a page of its own, blank but for the footer.
BLOCK_GAP = 10
PLACEHOLDER_PAD = 6
# A figure leaves room on its page for a section heading (20 pt and 8 pt after),
# a subheading with a swatch (a 23 pt row), one line of text with 6 pt after it
# and the caption (3 pt before and 13 pt): 20 + 8 + 23 + 13 + 6 + 3 + 13 = 86 pt.
# So the first figure of a section always shares a page with its headings.
MAX_FIGURE_HEIGHT = FRAME_HEIGHT - 86

# reportlab settings an RL_ environment variable or a settings file can change,
# each of which moves the layout or the bytes; every build runs on these values.
_PINNED = {"invariant": 1, "overlapAttachedSpace": 1, "useA85": 1, "wrapA85": 0}
# The settings and SOURCE_DATE_EPOCH are process-wide, so builds take turns.
_BUILD = threading.Lock()

_NBSP = chr(0xA0)
_FRACTION_SPACE = re.compile(r"(?<=\d) (?=\d+/\d)")
_TIMES = re.compile(r'(?<=[\d"]) x (?=\d|WOF)')

FIGURES_MODULE = "qrep.export.figures"

_OUTLINE = HexColor("#333333")
_FRAME = HexColor("#808080")

_BODY = ParagraphStyle("body", fontName=FONT, fontSize=BODY_SIZE, leading=LEADING, spaceAfter=6)
_TITLE = ParagraphStyle("title", fontName=BOLD, fontSize=TITLE_SIZE, leading=TITLE_SIZE + 6,
                        spaceAfter=18)
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
# Words never split in a cell; _table refuses a word wider than its column.
_CELL = ParagraphStyle("cell", fontName=FONT, fontSize=TABLE_SIZE, leading=12, splitLongWords=0)
_CELL_HEAD = ParagraphStyle("cellhead", parent=_CELL, fontName=BOLD)
_CAPTION = ParagraphStyle("caption", parent=_BODY, alignment=TA_CENTER, spaceBefore=3, spaceAfter=10)
# splitLongWords=0 keeps "placeholder" whole for the checker; the frame grows to fit.
_PLACEHOLDER = ParagraphStyle("placeholder", parent=_BODY, alignment=TA_CENTER, spaceAfter=0,
                              splitLongWords=0)

Drawer = Callable[[FigureRequest], "Drawing | list[Drawing]"]


def render_pdf(document: PatternDocument) -> bytes:
    """The document as PDF bytes; identical documents give identical bytes."""
    for text in document.texts():
        check_text(text)
    if stringWidth(document.name, FONT, FOOTER_SIZE) > CONTENT_WIDTH:
        raise ValueError(f"the pattern name {document.name!r} is too wide for one footer line")
    probe = _PageProbe()
    story = _keep_headings(_story(document, _drawers(), probe))
    out = io.BytesIO()
    # The canvas takes invariant=1 from the template, which fixes the timestamp
    # and the document id. renderPDF orders a drawing's state changes only under
    # the module setting (renderPDF.py:213), so that is pinned for the build too.
    # reportlab stamps SOURCE_DATE_EPOCH even in invariant mode, and fails on a
    # value that is not a number (lib/utils.py:1270), so the build runs without it.
    with _BUILD:
        saved = {key: getattr(rl_config, key) for key in _PINNED}
        epoch = os.environ.pop("SOURCE_DATE_EPOCH", None)
        try:
            for key, value in _PINNED.items():
                setattr(rl_config, key, value)
            template = _template(out, document.name)
            template.build(story, canvasmaker=partial(_FooterCanvas, pattern_name=document.name))
        finally:
            for key, value in saved.items():
                setattr(rl_config, key, value)
            if epoch is not None:
                os.environ["SOURCE_DATE_EPOCH"] = epoch
    # The probe opens the page after the cover, so the cover took one page less
    # than the probe's page number; with no page after it, the cover is all pages.
    cover_pages = probe.page - 1 if len(document.sections) > 1 else template.page
    if cover_pages != 1:
        raise ValueError("the cover does not fit on page 1, which it must have to itself")
    return out.getvalue()


def _template(out: io.BytesIO, name: str) -> BaseDocTemplate:
    """The page template, made inside the pinned build: the frame reads
    overlapAttachedSpace when it is made."""
    template = BaseDocTemplate(
        out,
        pagesize=(PAGE_WIDTH, PAGE_HEIGHT),
        leftMargin=SIDE_MARGIN,
        rightMargin=SIDE_MARGIN,
        topMargin=TOP_MARGIN,
        bottomMargin=BOTTOM_MARGIN,
        title=name,
        author="QREP",
        creator="QREP",
        invariant=1,
        # Explicit, so RL_pageCompression in the environment cannot change the bytes.
        pageCompression=1,
    )
    frame = Frame(
        SIDE_MARGIN, BOTTOM_MARGIN, CONTENT_WIDTH, FRAME_HEIGHT,
        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, id="body",
        overlapAttachedSpace=1,
    )
    template.addPageTemplates([PageTemplate(id="page", frames=[frame])])
    return template


def _hold(text: str) -> str:
    """text with its lengths and dimensions held on one line: a break after the
    whole number of 2 1/2" or beside the x of 2" x 8" reads as another size."""
    return _TIMES.sub(f"{_NBSP}x{_NBSP}", _FRACTION_SPACE.sub(_NBSP, text))


def _markup(text: str) -> str:
    return escape(_hold(text))


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


class _Group(list):
    """Flowables that share one page: a step or paragraph with its figure, a step
    with its details, or one part of a figure."""


def _story(document: PatternDocument, drawers: Mapping[str, Drawer], probe: Flowable) -> list:
    numbers = itertools.count(1)
    cover, *rest = document.sections
    items = [_title(document.name)]
    for block in cover.blocks:
        items += _block(block, numbers, drawers)
    if rest:
        items += [PageBreak(), probe]
    for section in rest:
        items.append(TextFlowable(escape(section.kind.value), _HEADING))
        for block in section.blocks:
            items += _block(block, numbers, drawers)
    return items


def _title(name: str) -> TextFlowable:
    """The cover title at 28 pt, smaller in 2 pt steps until its longest word fits
    the line, so no word of the name breaks mid-word."""
    longest = max(name.split(), key=lambda word: stringWidth(word, BOLD, 1))
    size = TITLE_SIZE
    while size > BODY_SIZE and stringWidth(longest, BOLD, size) > CONTENT_WIDTH:
        size -= 2
    if stringWidth(longest, BOLD, size) > CONTENT_WIDTH:
        raise ValueError(f"the word {longest!r} is too wide for the cover title at {size} pt")
    style = ParagraphStyle(f"title{size}", parent=_TITLE, fontSize=size, leading=size + 6)
    return TextFlowable(escape(name), style)


def _keep_headings(items: list) -> list:
    """Each group as a KeepTogether that also holds the headings just before it.

    reportlab's keepWithNext never joins a heading to a KeepTogether
    (doctemplate.py, _ktAllow), so a heading followed by steps or a figure would
    otherwise sit alone at the foot of a page. MAX_FIGURE_HEIGHT leaves room for
    the headings above a one-line step and its figure; a longer step that leaves
    none is refused, since its headings would print alone on a page. A text-only
    group taller than a page splits anyway, with its headings at its start.
    """
    story, pending = [], []
    for item in items:
        if isinstance(item, _Group):
            if pending:
                height = _height([*pending, *item])
                if height > FRAME_HEIGHT and _height(item) <= FRAME_HEIGHT:
                    raise ValueError(
                        f"a heading and the step or figure after it need {height:.0f} pt, "
                        f"more than one page holds"
                    )
                item = [*pending, *item]
            story.append(KeepTogether(list(item)))
            pending = []
        elif item.getKeepWithNext():
            pending.append(item)
        else:
            story += [*pending, item]
            pending = []
    return story + pending


def _height(parts: list) -> float:
    """The height parts need at the top of a frame, spaced as the frame spaces
    them with overlapAttachedSpace on: the larger of one part's space after and
    the next one's space before, no space before the first and none after the
    last (frames.py, Frame._add)."""
    total = 0.0
    for previous, part in zip([None, *parts], parts):
        total += part.wrap(CONTENT_WIDTH, FRAME_HEIGHT)[1]
        if previous is not None:
            total += max(previous.getSpaceAfter(), part.getSpaceBefore())
    return total


def _block(block: Block, numbers: Iterator[int], drawers: Mapping[str, Drawer]) -> list:
    if isinstance(block, Subheading):
        return [_subheading(block)]
    if isinstance(block, Paragraph):
        style = ParagraphStyle(f"body{block.indent}", parent=_BODY, leftIndent=block.indent * INDENT)
        if block.figure is None:
            return [TextFlowable(_markup(block.text), style)]
        number = next(numbers)
        parts = [TextFlowable(_markup(_cite(block.text, number)), style)]
        return [_with_figure(parts, block.figure, number, drawers, "the paragraph")]
    if isinstance(block, Steps):
        groups = []
        for n, step in enumerate(block.items, start=block.start):
            number = next(numbers) if step.figure is not None else None
            parts = [TextFlowable(f"{n}. {_markup(_cite(step.text, number))}", _STEP)]
            parts += [TextFlowable(_markup(detail), _DETAIL) for detail in step.details]
            if step.figure is None:
                groups.append(_Group(parts))
            else:
                groups.append(_with_figure(parts, step.figure, number, drawers, f"step {n}"))
        return groups
    if isinstance(block, Table):
        return [_table(block)]
    if isinstance(block, Figure):
        return [_Group([_Spaced(part)]) for part in _figure_parts(block.request, drawers)]
    if isinstance(block, PrintScaleSquare):
        return [_print_scale_square(block)]
    raise TypeError(f"no layout for block {block!r}")


def _cite(text: str, number: int | None) -> str:
    """Text that cites its figure: "Sew the pair (Fig. 3)." (G-05)."""
    if number is None:
        return text
    text = text.rstrip()
    if text and text[-1] in ".:!?":
        return f"{text[:-1]} (Fig. {number}){text[-1]}"
    return f"{text} (Fig. {number})"


def _with_figure(parts: list, request: FigureRequest, number: int, drawers: Mapping[str, Drawer],
                 what: str) -> _Group:
    figure = _figure_parts(request, drawers)
    if len(figure) != 1:
        raise ValueError(
            f"the figure {request.label!r} is cited from text, so it must be one drawing, "
            f"not {len(figure)}"
        )
    group = _Group([*parts, figure[0], TextFlowable(f"Fig. {number}", _CAPTION)])
    # KeepTogether falls back to splitting a group taller than a page, so text and
    # its figure that cannot share one page are refused rather than split.
    height = _height(group)
    if height > FRAME_HEIGHT:
        raise ValueError(f"{what} and its figure do not fit on one page ({height:.0f} pt)")
    return group


# ---------------------------------------------------------------- figures


def _figure_parts(request: FigureRequest, drawers: Mapping[str, Drawer]) -> list:
    """The drawing for a request, or its parts when one figure spans pages (S10).

    Every part fits the requested size, which fits one page's figure area.
    """
    if request.width > CONTENT_WIDTH or request.height > MAX_FIGURE_HEIGHT:
        raise ValueError(
            f"figure {request.label!r} ({request.width:g} x {request.height:g} pt) does not fit "
            f"the {CONTENT_WIDTH} x {MAX_FIGURE_HEIGHT} pt figure area"
        )
    draw = drawers.get(request.kind)
    if draw is None:
        return [_Placeholder(request)]
    drawn = draw(request)
    parts = list(drawn) if isinstance(drawn, list | tuple) else [drawn]
    if not parts:
        raise ValueError(f"the {request.kind} drawer returned nothing for {request.label!r}")
    for part in parts:
        # Only a Drawing exposes its labels to the L-10, G-03 and PS-05 checks below.
        if not isinstance(part, Drawing):
            raise TypeError(
                f"the {request.kind} drawer returned {type(part).__name__} for "
                f"{request.label!r}; it must return a reportlab Drawing"
            )
        _check_drawing(part, request)
        part.hAlign = "CENTER"
    return parts


def _check_drawing(drawing: Drawing, request: FigureRequest) -> None:
    width, height = drawing.wrap(CONTENT_WIDTH, FRAME_HEIGHT)
    if width > request.width + 0.5 or height > request.height + 0.5:
        raise ValueError(
            f"the {request.kind} drawer returned {width:g} x {height:g} pt, larger than the "
            f"{request.width:g} x {request.height:g} pt requested for {request.label!r}"
        )
    # A shape past the drawing's own box prints past the size it declared, into
    # the margins or over the text beside it.
    bounds = drawing.getBounds()
    if bounds is not None and (
        bounds[0] < -0.5 or bounds[1] < -0.5
        or bounds[2] > drawing.width + 0.5 or bounds[3] > drawing.height + 0.5
    ):
        raise ValueError(
            f"the {request.kind} drawer draws outside its {drawing.width:g} x "
            f"{drawing.height:g} pt drawing for {request.label!r}"
        )
    for label, size in _labels(drawing):
        if size < LABEL_MIN - 0.01:
            raise ValueError(
                f"figure label {label.text!r} in {request.label!r} prints at {size:g} pt; "
                f"L-10 needs at least {LABEL_MIN} pt"
            )
        if label.fontName not in LABEL_FONTS:
            raise ValueError(
                f"figure label {label.text!r} in {request.label!r} is set in "
                f"{label.fontName}; G-03 allows Helvetica only"
            )
        check_text(label.text)


def _labels(node, scale: float = 1.0, root: bool = True) -> Iterator[tuple[String, float]]:
    """Every string in a drawing with the size it prints at, through each
    group's transform and the drawing's render scale. A widget's strings exist
    only once it draws itself, so each widget is expanded as the renderer would.
    renderPDF applies renderScale to the drawing it is given and draws a nested
    Drawing as a plain group (renderbase.py), so only the root's counts."""
    if isinstance(node, UserNode):
        node = node.provideNode()
    a, b, c, d = (getattr(node, "transform", None) or (1, 0, 0, 1))[:4]
    scale *= math.sqrt(abs(a * d - b * c)) * (getattr(node, "renderScale", 1.0) if root else 1.0)
    if isinstance(node, String):
        yield node, node.fontSize * scale
    for child in getattr(node, "contents", ()):
        yield from _labels(child, scale, root=False)


class _Placeholder(Flowable):
    """A frame that says which figure is missing: the requested size, or larger
    when its words need more room, so each word prints whole inside it."""

    def __init__(self, request: FigureRequest):
        super().__init__()
        self.text = f"Figure placeholder: {request.label} ({FIGURE_KINDS[request.kind]})"
        widest = max(stringWidth(word, FONT, BODY_SIZE) for word in self.text.split())
        self.width = max(request.width, widest + 2 * PLACEHOLDER_PAD)
        if self.width > CONTENT_WIDTH:
            raise ValueError(f"the figure label {request.label!r} has a word too wide for a page")
        _, text_height = self._paragraph().wrap(self.width - 2 * PLACEHOLDER_PAD, PAGE_HEIGHT)
        self.height = max(request.height, text_height + 2 * PLACEHOLDER_PAD)
        if self.height > MAX_FIGURE_HEIGHT:
            raise ValueError(f"the placeholder for {request.label!r} is too tall for a page")
        self.hAlign = "CENTER"

    def _paragraph(self) -> TextFlowable:
        return TextFlowable(escape(self.text), _PLACEHOLDER)

    def wrap(self, available_width, available_height):
        return self.width, self.height

    def draw(self):
        canv = self.canv
        canv.saveState()
        canv.setStrokeColor(_FRAME)
        canv.setLineWidth(0.75)
        canv.rect(0, 0, self.width, self.height, stroke=1, fill=0)
        text = self._paragraph()
        _, height = text.wrap(self.width - 2 * PLACEHOLDER_PAD, self.height)
        text.drawOn(canv, PLACEHOLDER_PAD, (self.height - height) / 2)
        canv.restoreState()


class _Spaced(Flowable):
    """A figure part with BLOCK_GAP after it; a Drawing refuses a spaceAfter of its own."""

    def __init__(self, part: Flowable):
        super().__init__()
        self.part = part
        self.spaceAfter = BLOCK_GAP
        self.hAlign = "CENTER"

    def wrap(self, available_width, available_height):
        self.width, self.height = self.part.wrap(available_width, available_height)
        return self.width, self.height

    def draw(self):
        self.part.drawOn(self.canv, 0, 0)


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


def _cell(text: str, style: ParagraphStyle, width: float) -> TextFlowable:
    """A cell's text; a word wider than the column is refused, since a split
    word ("Backgro" "und") no longer matches its name in the text (G-10)."""
    held = _hold(text)
    room = width - 2 * 3
    for word in held.split(" "):
        if stringWidth(word, style.fontName, style.fontSize) > room:
            raise ValueError(f"{word!r} in the table cell {text!r} is wider than its {room:g} pt column")
    return TextFlowable(escape(held), style)


def _table(block: Table) -> TableFlowable:
    head = 1 if block.header else 0
    weights = block.widths or (1,) * block.columns
    widths = [CONTENT_WIDTH * w / sum(weights) for w in weights]
    data = [[_cell(text, _CELL_HEAD, widths[c]) for c, text in enumerate(block.header)]] if head else []
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, _FRAME),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    for r, row in enumerate(block.rows, start=head):
        cells = []
        for c, cell in enumerate(row):
            if isinstance(cell, Swatch):
                cells.append(_Swatch(cell.color))
                # Against the next cell, so the swatch reads as that letter's (C-04).
                style.append(("ALIGN", (c, r), (c, r), "RIGHT"))
            else:
                cells.append(_cell(cell, _CELL, widths[c]))
        data.append(cells)
    # Split between rows only, never inside one (G-04), repeating the header row
    # on each page the table continues on.
    table = TableFlowable(data, colWidths=widths, repeatRows=head, splitByRow=1, splitInRow=0,
                          spaceAfter=BLOCK_GAP)
    table.setStyle(TableStyle(style))
    return table


def _subheading(block: Subheading) -> Flowable:
    text = TextFlowable(_markup(block.text), _SUBHEADING)
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
        [[_Square(), TextFlowable(_markup(block.note), _BODY)]],
        colWidths=[84, CONTENT_WIDTH - 84],
        spaceAfter=BLOCK_GAP,
    )
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return row


# ---------------------------------------------------------------- pages


class _PageProbe(Flowable):
    """Records the page it lands on; it opens the first page after the cover."""

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

