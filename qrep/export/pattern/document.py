"""The pattern document as typed data (PATTERN-SPEC section 2).

A section builder (A4b to A4d) turns a model into a PatternDocument: the
sections in the PS-02 order, each a list of blocks, and typed requests for the
figures A5a and A5b draw. render.py lays the document out on the page rules
(G-01 to G-04). Keeping the content apart from the layout lets tests assert on
what a section says without parsing PDF bytes, as the v1 booklet did
(pdf.py:1-10).

Every number reaches the text through the formatters here, so lengths stay
C-09 fractions and dimensions keep C-10's " x ". check_text refuses the PS-05
and PS-06 forms; the renderer applies it to every string it prints.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import StrEnum

from qrep.model.units import format_inches


class SectionKind(StrEnum):
    """The sections in the PS-02 order; a value is the printed heading."""

    # The cover prints the pattern name instead of a heading (S1).
    COVER = "Cover"
    FABRIC_REQUIREMENTS = "Fabric requirements"
    BEFORE_YOU_BEGIN = "Before you begin"
    CUTTING = "Cutting"
    UNITS = "Making the units"
    BLOCKS = "Making the blocks"
    QUILT_ASSEMBLY = "Quilt assembly"
    BORDERS = "Borders"
    FINISHING = "Finishing"
    LAYOUT_CHART = "Layout chart"
    COLORING_PAGE = "Coloring page"


SECTION_ORDER = tuple(SectionKind)

# What qrep.export.figures can be asked to draw (PATTERN-SPEC ticket map: A5),
# with the plain words a placeholder frame prints for each.
FIGURE_KINDS = {
    "cover_render": "cover render",
    "symbol_legend": "symbol legend",
    "fat_quarter": "fat quarter diagram",
    "hst_unit": "half-square triangle unit figure",
    "qst_unit": "quarter-square triangle unit figure",
    "snowball_unit": "snowball unit figure",
    "flying_geese_unit": "flying geese unit figure",
    "strip_set": "strip set figure",
    "sub_unit": "plain sub-unit figure",
    "block": "block figure",
    "assembly": "quilt assembly figure",
    "borders": "border figure",
    "backing": "backing figure",
    "binding_corner": "binding corner figure",
    "layout_chart": "layout chart",
    "coloring_page": "coloring page",
}
# G-05 has a step cite every figure; only these stand alone, without a number.
UNCITED_KINDS = frozenset({"cover_render", "layout_chart", "coloring_page"})

_HEX = re.compile(r"#[0-9a-fA-F]{6}")


@dataclass(frozen=True)
class FigureRequest:
    """One figure a section needs, sized in points.

    subject carries whatever the drawer for this kind needs (the quilt, a unit,
    a strip set); label names the figure in plain words for its placeholder.
    """

    kind: str
    width: float
    height: float
    label: str
    # Out of the hash, so a request with a dict or list subject can key a dict.
    subject: object = field(default=None, hash=False)

    def __post_init__(self) -> None:
        if self.kind not in FIGURE_KINDS:
            raise ValueError(f"unknown figure kind {self.kind!r}; known: {', '.join(FIGURE_KINDS)}")
        if not (self.width > 0 and self.height > 0):
            raise ValueError(f"figure {self.label!r} needs a positive size")
        if not self.label.strip():
            raise ValueError(f"a {self.kind} figure needs a label")


@dataclass(frozen=True)
class Subheading:
    """A unit, block or fabric heading; swatch is the fabric color drawn left of it (C-04)."""

    text: str
    swatch: str | None = None

    def __post_init__(self) -> None:
        if self.swatch is not None:
            _check_color(self.swatch)


@dataclass(frozen=True)
class Paragraph:
    """Body text. indent counts nesting levels; a figure is cited from the text."""

    text: str
    indent: int = 0
    figure: FigureRequest | None = None

    def __post_init__(self) -> None:
        # Three levels (54 pt) is deeper than any section nests, and each level
        # narrows the column the text wraps in.
        if not 0 <= self.indent <= 3:
            raise ValueError(f"indent is 0 to 3 levels, got {self.indent}")


@dataclass(frozen=True)
class Step:
    """A numbered step; details print indented beneath it, such as S4's subcuts."""

    text: str
    details: tuple[str, ...] = ()
    figure: FigureRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "details", _items(self.details, "details"))


@dataclass(frozen=True)
class Steps:
    """Numbered steps. G-04 restarts the count at 1 under each subheading; start
    continues a list that a note interrupts under the same subheading."""

    items: tuple[Step, ...]
    start: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", _items(self.items, "items"))
        if not self.items:
            raise ValueError("a step list needs at least one step")
        if not isinstance(self.start, int) or isinstance(self.start, bool) or self.start < 1:
            raise ValueError(f"a step list starts at 1 or later, got {self.start!r}")


@dataclass(frozen=True)
class Swatch:
    """A table cell holding a fabric's color square (C-04)."""

    color: str

    def __post_init__(self) -> None:
        _check_color(self.color)


@dataclass(frozen=True)
class Table:
    """A table whose rows never split across pages (G-04).

    An empty header prints no header row, as for a piece list. widths, when
    given, are relative column weights.
    """

    header: tuple[str, ...]
    rows: tuple[tuple[str | Swatch, ...], ...]
    widths: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "header", _items(self.header, "header"))
        object.__setattr__(
            self, "rows", tuple(_items(row, "row") for row in _items(self.rows, "rows"))
        )
        if not self.header and not self.rows:
            raise ValueError("a table needs a header or a row")
        columns = self.columns
        if self.widths is not None:
            object.__setattr__(self, "widths", tuple(self.widths))
            if len(self.widths) != columns or min(self.widths) <= 0:
                raise ValueError("a table needs one positive width per column")
        for row in self.rows:
            if len(row) != columns:
                raise ValueError(f"row {row!r} has {len(row)} cells for {columns} columns")

    @property
    def columns(self) -> int:
        return len(self.header) if self.header else len(self.rows[0])


@dataclass(frozen=True)
class Figure:
    """A figure no text cites, such as the cover render: it gets no Fig. number."""

    request: FigureRequest

    def __post_init__(self) -> None:
        if self.request.kind not in UNCITED_KINDS:
            raise ValueError(
                f"a {self.request.kind} figure is cited from its step or paragraph (G-05); "
                f"only {', '.join(sorted(UNCITED_KINDS))} stand alone"
            )


@dataclass(frozen=True)
class PrintScaleSquare:
    """The 1" square that proves the print scale, with its note beside it (G-09)."""

    note: str


Block = Subheading | Paragraph | Steps | Table | Figure | PrintScaleSquare


@dataclass(frozen=True)
class Section:
    kind: SectionKind
    blocks: tuple[Block, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", SectionKind(self.kind))
        object.__setattr__(self, "blocks", _items(self.blocks, "blocks"))
        # An empty section prints a bare heading, such as "Borders" for a quilt
        # without borders, which PS-02 fails; the builder leaves it out instead.
        if not self.blocks and self.kind is not SectionKind.COVER:
            raise ValueError(f"the {self.kind.value} section has no blocks")


@dataclass(frozen=True)
class PatternDocument:
    """The whole pattern: its name and its sections, the cover first, in PS-02 order."""

    name: str
    sections: tuple[Section, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", _items(self.sections, "sections"))
        # The name prints in every footer, where no date may appear (G-02, PS-03).
        check_name(self.name)
        kinds = [section.kind for section in self.sections]
        if not kinds or kinds[0] is not SectionKind.COVER:
            raise ValueError("the cover must be the first section")
        positions = [SECTION_ORDER.index(kind) for kind in kinds]
        if any(b <= a for a, b in zip(positions, positions[1:])):
            raise ValueError(f"sections must follow the PS-02 order once each, got {kinds}")

    def cited_figures(self) -> list[FigureRequest]:
        """Figures cited from text, in reading order; the n-th is Fig. n (G-05)."""
        cited = []
        for section in self.sections:
            for block in section.blocks:
                if isinstance(block, Paragraph) and block.figure is not None:
                    cited.append(block.figure)
                elif isinstance(block, Steps):
                    cited += [step.figure for step in block.items if step.figure is not None]
        return cited

    def texts(self) -> Iterator[str]:
        """Every string the sections print, figure labels included."""
        for section in self.sections:
            for block in section.blocks:
                yield from _block_texts(block)


def _block_texts(block: Block) -> Iterator[str]:
    if isinstance(block, Subheading | PrintScaleSquare):
        yield block.text if isinstance(block, Subheading) else block.note
    elif isinstance(block, Paragraph):
        yield block.text
        if block.figure is not None:
            yield block.figure.label
    elif isinstance(block, Steps):
        for step in block.items:
            yield step.text
            yield from step.details
            if step.figure is not None:
                yield step.figure.label
    elif isinstance(block, Table):
        yield from block.header
        for row in block.rows:
            yield from (cell for cell in row if isinstance(cell, str))
    elif isinstance(block, Figure):
        yield block.request.label


def _items(value, what: str) -> tuple:
    """value as a tuple; a lone string is refused, since tuple() would split it
    into one-character items that each print on their own line or cell."""
    if isinstance(value, str):
        raise TypeError(f"{what} is a sequence, not the string {value!r}")
    return tuple(value)


def _check_color(color: str) -> None:
    if not _HEX.fullmatch(color):
        raise ValueError(f"a swatch color is #rrggbb, got {color!r}")


# ---------------------------------------------------------------- formatters


def inches(eighths: int) -> str:
    """A length in integer eighths as a C-09 mixed fraction with an inch mark."""
    if not isinstance(eighths, int) or isinstance(eighths, bool):
        raise TypeError(f"lengths are integer eighths, got {eighths!r}")
    if eighths < 0:
        raise ValueError(f"a printed length cannot be negative, got {eighths}")
    return format_inches(eighths)


def rectangle(a: int, b: int) -> str:
    """A rectangle, short side first (C-10)."""
    short, long = sorted((a, b))
    return f"{inches(short)} x {inches(long)}"


def square(side: int) -> str:
    return f"{inches(side)} square"


def size(width: int, height: int) -> str:
    """The quilt or quilt center, width first, as on the cover (C-10)."""
    return f"{inches(width)} x {inches(height)}"


# ---------------------------------------------------------------- text guard


class PatternTextError(ValueError):
    """Text the pattern must never print (PS-05, PS-06, G-02)."""


_MONTH = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|"
    r"December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?"
)
_DATE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}-\d{1,2}-\d{4}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b|"
    r"\b\d{4}/\d{1,2}/\d{1,2}\b|"
    rf"\b{_MONTH} (?:\d{{1,2}}(?:st|nd|rd|th)?|\d{{4}})\b|"
    rf"\b\d{{1,2}}(?:st|nd|rd|th)? {_MONTH}(?![a-z])"
)
_BANNED = [
    (re.compile(r"\b(?:historical|modern|strip strategy|difficulty|minutes|heuristic)\b",
                re.IGNORECASE), "a strategy name, difficulty or time word"),
    (re.compile(r"\b(?:total pieces|pieces total|piece total|piece count|pieces in all)\b|"
                r"\b(?:has|have|totals?|of) [\d,]+ pieces\b|\b[\d,]+ pieces (?:to cut|in all)\b|"
                # No step cuts 100 loose pieces; cutting lines count in parentheses (S4).
                r"\bpieces?: ?[\d,]+|\b(?:\d{3,}|\d{1,3}(?:,\d{3})+) pieces\b",
                re.IGNORECASE), "a piece total"),
    (re.compile(r"\bf\d+\b"), "an internal fabric id"),
    (_HEX, "a hex color"),
    # C-07 lets the pattern echo a centimeter size the user typed, such as 152.4 cm.
    (re.compile(r"\.\d+(?!\d)(?! ?cm\b)"), "a decimal number"),
    # A hyphen or any Unicode dash between the whole number and the fraction.
    (re.compile(r"\b\d+[-\u2010-\u2015]\d+/\d+\b"), "a hyphenated fraction"),
    (re.compile("[¼-¾⅐-⅞⁄\u2215]"), "a fraction glyph"),
    (_DATE, "a date"),
]
_FRACTION = re.compile(r"\b(\d+)/(\d+)\b")
# A fraction is only ever a length or a yardage, so it carries its unit (C-07).
_BARE_FRACTION = re.compile(r'\b\d+/\d+\b(?!"| yd\b)')
_SEPARATOR = re.compile(r"\d( ?)([xX×])( ?)(?=\d|WOF)")
_BY = re.compile(r"\d by \d")
# Lengths in the places a cut size takes. These read the text with its quotes,
# since an inch mark is a straight double quote (C-07).
_NUMBER = r'(\d+(?: \d+/\d+)?)("?)'
# Not after a letter, so a piece label such as "each A2 square" is no length.
_STRIP_OR_SQUARE = re.compile(rf'(?<![\w/.]){_NUMBER} (?:x WOF|squares?)\b')
_RECTANGLE = re.compile(rf'(?<![\w/.]){_NUMBER} x {_NUMBER} rectangles?\b')
_CURLY_MARK = re.compile(r"\d[\N{RIGHT DOUBLE QUOTATION MARK}\N{DOUBLE PRIME}]")


def check_printable(text: str) -> None:
    """Raise PatternTextError for a character built-in Helvetica cannot print.

    The standard fonts carry the WinAnsi encoding, which is cp1252; any other
    character prints as an empty box and extracts as nothing useful (PS-41).
    """
    try:
        text.encode("cp1252")
    except UnicodeEncodeError as bad:
        raise PatternTextError(
            f"{text[bad.start]!r} in {text!r} is outside the characters Helvetica prints"
        ) from None


def check_text(text: str) -> None:
    """Raise PatternTextError when text holds a PS-05 item or breaks PS-06.

    The text is read as section 6 reads it: whitespace collapsed and straight
    double quotes dropped, so '2"x8"' is caught as "2x8". Nothing is exempt,
    the pattern name included: PS-05 bans its items anywhere, and the name
    prints on every page (G-02).
    """
    raw = re.sub(r"\s+", " ", text)
    plain = raw.replace('"', "")
    for pattern, what in _BANNED:
        found = pattern.search(plain)
        if found:
            raise PatternTextError(f"{what} {found.group(0)!r} in {text!r}")
    for found in _FRACTION.finditer(plain):
        num, den = int(found.group(1)), int(found.group(2))
        if den not in (2, 4, 8) or not 0 < num < den or math.gcd(num, den) != 1:
            raise PatternTextError(f"fraction {found.group(0)!r} is not in lowest eighths in {text!r}")
    found = _BARE_FRACTION.search(text)
    if found:
        raise PatternTextError(f"fraction {found.group(0)!r} has no inch mark or yd in {text!r}")
    for found in _SEPARATOR.finditer(plain):
        if found.group(1, 2, 3) != (" ", "x", " "):
            raise PatternTextError(f"dimension {found.group(0)!r} needs ' x ' in {text!r}")
    found = _BY.search(plain)
    if found:
        raise PatternTextError(f"dimension {found.group(0)!r} needs ' x ' in {text!r}")
    found = _CURLY_MARK.search(raw)
    if found:
        raise PatternTextError(f"the inch mark in {found.group(0)!r} is not a straight quote in {text!r}")
    for found in _STRIP_OR_SQUARE.finditer(raw):
        if not found.group(2):
            raise PatternTextError(f"length {found.group(0)!r} has no inch mark in {text!r}")
    for found in _RECTANGLE.finditer(raw):
        if not (found.group(2) and found.group(4)):
            raise PatternTextError(f"rectangle {found.group(0)!r} needs inch marks in {text!r}")
        if _value(found.group(1)) > _value(found.group(3)):
            raise PatternTextError(f"rectangle {found.group(0)!r} needs its short side first in {text!r}")
    # Last, so a fraction glyph outside cp1252 is reported as a fraction glyph.
    check_printable(text)


def _value(number: str) -> float:
    """A printed length such as "2 1/2" in inches, to compare two sides."""
    whole, _, fraction = number.partition(" ")
    if "/" in whole:
        whole, fraction = "0", whole
    num, _, den = fraction.partition("/")
    return int(whole) + (int(num) / int(den) if den else 0)


def check_name(name: str) -> None:
    """Raise when the pattern name cannot print whole on one footer line.

    The name prints in the title and every footer, so it obeys every text rule
    and is one clean line: control characters or doubled or edge spaces would
    print in the footer as they are while the title collapses them.
    """
    if not name or name != " ".join(name.split()) or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValueError(f"a pattern needs a one-line name without extra spaces, got {name!r}")
    check_text(name)
