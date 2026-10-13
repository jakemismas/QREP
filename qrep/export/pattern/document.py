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
from dataclasses import dataclass
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
    "block": "block figure",
    "assembly": "quilt assembly figure",
    "borders": "border figure",
    "backing": "backing figure",
    "binding_corner": "binding corner figure",
    "layout_chart": "layout chart",
    "coloring_page": "coloring page",
}

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
    subject: object = None

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
        object.__setattr__(self, "details", tuple(self.details))


@dataclass(frozen=True)
class Steps:
    """Numbered steps. G-04 restarts the count at 1 under each subheading; start
    continues a list that a note interrupts under the same subheading."""

    items: tuple[Step, ...]
    start: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "items", tuple(self.items))
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
        object.__setattr__(self, "header", tuple(self.header))
        object.__setattr__(self, "rows", tuple(tuple(row) for row in self.rows))
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
        object.__setattr__(self, "blocks", tuple(self.blocks))


@dataclass(frozen=True)
class PatternDocument:
    """The whole pattern: its name and its sections, the cover first, in PS-02 order."""

    name: str
    sections: tuple[Section, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "sections", tuple(self.sections))
        if not self.name.strip() or "\n" in self.name:
            raise ValueError("a pattern needs a one-line name")
        check_printable(self.name)
        # The name prints in every footer, where no date may appear (G-02, PS-03).
        if _DATE.search(self.name):
            raise PatternTextError(f"the pattern name {self.name!r} holds a date")
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
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b|"
    rf"\b{_MONTH} \d{{1,2}}\b|\b\d{{1,2}} {_MONTH}(?![a-z])"
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
    (re.compile(r"\.\d"), "a decimal number"),
    # A hyphen or any Unicode dash between the whole number and the fraction.
    (re.compile(r"\b\d+[-‐-―]\d+/\d+\b"), "a hyphenated fraction"),
    (re.compile("[¼-¾⅐-⅞⁄∕]"), "a fraction glyph"),
    (_DATE, "a date"),
]
_FRACTION = re.compile(r"\b(\d+)/(\d+)\b")
# A fraction is only ever a length or a yardage, so it carries its unit (C-07).
_BARE_FRACTION = re.compile(r'\b\d+/\d+\b(?!"| yd\b)')
_SEPARATOR = re.compile(r"\d( ?)([xX×])( ?)(?=\d|WOF)")
_BY = re.compile(r"\d by \d")


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


def check_text(text: str, name: str = "") -> None:
    """Raise PatternTextError when text holds a PS-05 item or breaks PS-06.

    The text is read as section 6 reads it: whitespace collapsed and straight
    double quotes dropped, so '2"x8"' is caught as "2x8". The pattern name is
    left out, as the PS-05 check leaves it out.
    """
    check_printable(text)
    plain = re.sub(r"\s+", " ", text.replace('"', ""))
    if name:
        plain = plain.replace(re.sub(r"\s+", " ", name.replace('"', "")), " ")
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
