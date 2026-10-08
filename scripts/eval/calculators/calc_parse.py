"""Parse the text that the D2 calculators display into exact numbers.

Each parser reads the HTML a page wrote into its result elements (the innerHTML the Playwright
driver captures) and returns Fractions for inches and yards and ints for counts. Anything that
does not match the recorded output shape raises ValueError: a guessed number would turn a page
change into a silent wrong comparison.

Stdlib only, because the test also runs under Pyodide. Non-ASCII glyphs the pages print are named
by code point (chr) so this source stays ASCII.
"""

from __future__ import annotations

import re
from fractions import Fraction
from html.parser import HTMLParser

__all__ = [
    "html_text",
    "parse_count",
    "parse_decimal_inches",
    "parse_dtq_border",
    "parse_mfqs_backing",
    "parse_nqc",
    "parse_omni_backing",
    "parse_qc_border",
    "parse_qp_backing",
    "parse_qp_binding",
    "parse_qp_border",
    "parse_qp_piece_count",
    "parse_quiltkeeper_binding",
    "parse_sewbecca_border",
    "parse_stitchdesk_backing",
    "parse_stitchdesk_binding",
    "parse_yards",
]

INCHES_PER_YARD = 36

# Text a page shows when it has no value. Named here so the error says "no value" instead of
# "unrecognized", which points the reader at the inputs rather than at this parser.
_PLACEHOLDERS = {"N/A", "NA", "NAN", "INFINITY", "-INFINITY", "UNDEFINED", "-", "--"}
_DASHES = {chr(0x2012), chr(0x2013), chr(0x2014), chr(0x2015), chr(0x2212)}

# Glyphs the newer pages print, rewritten to the ASCII forms the patterns below read.
_VULGAR_FRACTIONS = {
    chr(0x215B): "1/8",
    chr(0x00BC): "1/4",
    chr(0x215C): "3/8",
    chr(0x00BD): "1/2",
    chr(0x215D): "5/8",
    chr(0x00BE): "3/4",
    chr(0x215E): "7/8",
    chr(0x2153): "1/3",
    chr(0x2154): "2/3",
}
_GLYPHS = {
    chr(0x2033): '"',  # double prime: The Stitch Desk and QuiltKeeper inch marks
    chr(0x201D): '"',  # right double quotation mark used as an inch mark
    chr(0x00D7): " x ",  # multiplication sign between dimensions
    chr(0x2192): " -> ",  # arrow in My Favorite Quilt Store's shrinkage line
    chr(0x2014): " - ",  # em dash in labels, and alone where a page has no value
    chr(0x2013): " - ",
    chr(0x2726): " ",  # decorative star before Quilt Calculator's "Results"
}

_NUM = r"[0-9]+"
_DEC = r"[0-9]+(?:\.[0-9]+)?"
_MIXED = re.compile(rf"({_NUM}) ({_NUM})/({_NUM})")
_FRACTION = re.compile(rf"({_NUM})/({_NUM})")
_WHOLE = re.compile(_NUM)
_NQC_YARDS_INCHES = re.compile(rf"({_NUM}) yards? ?\+ ?({_DEC}) inch(?:es)?", re.IGNORECASE)
_NQC_YARDS = re.compile(rf"({_NUM}) yards?", re.IGNORECASE)
_NQC_INCHES = re.compile(rf"({_DEC}) inch(?:es)?", re.IGNORECASE)
_DECIMAL = re.compile(_DEC)
_INCH_MARKS = '"' + chr(0x201D) + chr(0x2033)

# A displayed quantity: "3 7/8", "7/8", "42" or "82.5".
_QTY = rf"{_NUM} {_NUM}/{_NUM}|{_NUM}/{_NUM}|{_DEC}"

# JS prints the shortest decimal that round-trips a double, so binary error can surface as
# 348.00000000000006. Every true value these pages derive from eighth-inch inputs has at most
# three decimals (1/8 = 0.125), and such noise sits within about 1e-13 of it, so a value within
# 1e-9 of a thousandth is that thousandth. Anything farther away is a real value and stays exact.
_NOISE = Fraction(1, 10**9)

_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "wbr"}
)
_BLOCK_TAGS = frozenset(
    {
        "address", "article", "aside", "blockquote", "dd", "div", "dl", "dt", "figcaption",
        "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "li", "main",
        "nav", "ol", "p", "section", "table", "tbody", "td", "tfoot", "th", "thead", "tr", "ul",
    }
)  # fmt: skip


class _Collector(HTMLParser):
    """Visible text of a fragment, by line and by element.

    A <br> always ends a line. With blocks=True the start and end of a block element do too, the
    way a browser's innerText separates <p> and <div> content. Each element also records its own
    text, with a line break wherever a nested block or <br> starts or ends.
    """

    def __init__(self, blocks: bool) -> None:
        super().__init__(convert_charrefs=True)
        self._blocks = blocks
        self.lines: list[list[str]] = [[]]
        self.elements: list[tuple[str, dict[str, str | None], list[str]]] = []
        self._open: list[tuple[str, dict[str, str | None], list[str]]] = []
        self._skip_depth = 0

    def _break(self) -> None:
        self.lines.append([])
        for _tag, _attrs, parts in self._open:
            parts.append("\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br" or (self._blocks and tag in _BLOCK_TAGS):
            self._break()
        if tag in ("script", "style"):
            self._skip_depth += 1
        if tag not in _VOID_TAGS:
            record = (tag, dict(attrs), [])
            self.elements.append(record)
            self._open.append(record)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1
        for i in range(len(self._open) - 1, -1, -1):
            if self._open[i][0] == tag:
                del self._open[i:]
                break
        if self._blocks and tag in _BLOCK_TAGS:
            self._break()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        self.lines[-1].append(data)
        for _tag, _attrs, parts in self._open:
            parts.append(data)


def _collapse(text: str) -> str:
    # str.split() treats U+00A0 as whitespace, so a decoded &nbsp; collapses like a space.
    return " ".join(text.split())


def html_text(fragment: str, *, blocks: bool = False) -> str:
    """Visible text of an HTML fragment: <br> ends a line, entities are decoded (&nbsp; is a
    space), whitespace collapses within each line, and the result is stripped. With blocks=True,
    block elements (p, div, li, ...) also end a line and empty lines are dropped."""
    collector = _Collector(blocks)
    collector.feed(fragment)
    collector.close()
    # A newline in the source is HTML whitespace, so only <br> (and blocks) break a line.
    lines = [_collapse("".join(parts)) for parts in collector.lines]
    if blocks:
        lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def _ascii(text: str) -> str:
    """Rewrite the page glyphs to ASCII and collapse whitespace on each line."""
    for glyph, plain in _VULGAR_FRACTIONS.items():
        # The leading space splits "3" from a glued fraction ("3 7/8" from 3 and 7/8).
        text = text.replace(glyph, f" {plain} ")
    for glyph, plain in _GLYPHS.items():
        text = text.replace(glyph, plain)
    return "\n".join(_collapse(line) for line in text.split("\n")).strip()


def _lines(fragment: str) -> list[str]:
    """Non-empty ASCII lines of a fragment, split at <br> and block elements."""
    return [line for line in _ascii(html_text(fragment, blocks=True)).split("\n") if line]


def _elements(fragment: str) -> list[tuple[str, dict[str, str | None], str]]:
    """(tag, attributes, ASCII text) for every element, in document order."""
    collector = _Collector(blocks=True)
    collector.feed(fragment)
    collector.close()
    return [(tag, attrs, _ascii("".join(parts))) for tag, attrs, parts in collector.elements]


def _texts_by_id(fragment: str, what: str) -> dict[str, str]:
    texts: dict[str, str] = {}
    for _tag, attrs, text in _elements(fragment):
        element_id = attrs.get("id")
        if element_id is None:
            continue
        if element_id in texts:
            raise ValueError(f"{what}: element id {element_id!r} appears twice")
        texts[element_id] = text
    return texts


def _label_values(fragment: str, what: str) -> list[tuple[str, str]]:
    """(label, value) pairs from rows written as two consecutive <span> elements."""
    spans = [text for tag, _attrs, text in _elements(fragment) if tag == "span"]
    if len(spans) % 2:
        raise ValueError(f"{what}: {len(spans)} spans do not pair into label and value rows")
    return list(zip(spans[0::2], spans[1::2], strict=True))


def _clean(text: str, what: str) -> str:
    if not isinstance(text, str):
        raise ValueError(f"{what}: expected text, got {type(text).__name__}")
    if _collapse(text) in _DASHES:
        raise ValueError(f"{what}: the page shows no value ({text!r})")
    cleaned = _collapse(_ascii(text))
    if not cleaned:
        raise ValueError(f"{what}: empty text")
    if cleaned.upper() in _PLACEHOLDERS:
        raise ValueError(f"{what}: the page shows no value ({text!r})")
    return cleaned


def _ratio(numerator: str, denominator: str, text: str) -> Fraction:
    if int(denominator) == 0:
        raise ValueError(f"zero denominator in {text!r}")
    return Fraction(int(numerator), int(denominator))


def parse_yards(text: str) -> Fraction:
    """Yards shown as "8 3/8", " 3/8", "8 ", "3/4", "4", a glyph form ("3" + U+215E for 3 7/8),
    or Nebraska's "4 Yards + 9 Inches", "1 Yard", "27 Inches" (whole yards + inches / 36)."""
    cleaned = _clean(text, "yards")
    if m := _MIXED.fullmatch(cleaned):
        return int(m[1]) + _ratio(m[2], m[3], text)
    if m := _FRACTION.fullmatch(cleaned):
        return _ratio(m[1], m[2], text)
    if _WHOLE.fullmatch(cleaned):
        return Fraction(int(cleaned))
    if m := _NQC_YARDS_INCHES.fullmatch(cleaned):
        return int(m[1]) + Fraction(m[2]) / INCHES_PER_YARD
    if m := _NQC_YARDS.fullmatch(cleaned):
        return Fraction(int(m[1]))
    if m := _NQC_INCHES.fullmatch(cleaned):
        return Fraction(m[1]) / INCHES_PER_YARD
    raise ValueError(f"yards: unrecognized text {text!r}")


def _decimal(cleaned: str, text: str, what: str) -> Fraction:
    if not _DECIMAL.fullmatch(cleaned):
        raise ValueError(f"{what}: not a plain decimal {text!r}")
    value = Fraction(cleaned)
    nearest = Fraction(round(value * 1000), 1000)
    if abs(value - nearest) <= _NOISE:
        return nearest
    return value


def parse_decimal_inches(text: str) -> Fraction:
    """Inches printed by JS as a plain decimal ("301.5", "12", "24.125"), exact, with float
    noise within 1e-9 of a thousandth snapped to it."""
    return _decimal(_clean(text, "inches"), text, "inches")


def _quantity(text: str, what: str) -> Fraction:
    """A displayed number in any of the pages' forms: "3 7/8", "7/8", "42" or "82.5"."""
    cleaned = _clean(text, what)
    if m := _MIXED.fullmatch(cleaned):
        return int(m[1]) + _ratio(m[2], m[3], text)
    if m := _FRACTION.fullmatch(cleaned):
        return _ratio(m[1], m[2], text)
    return _decimal(cleaned, text, what)


def parse_count(text: str) -> int:
    """A whole count such as a strip or panel number."""
    cleaned = _clean(text, "count")
    if not _WHOLE.fullmatch(cleaned):
        raise ValueError(f"count: not a whole number {text!r}")
    return int(cleaned)


def _need(mapping: dict[str, str], key: str, what: str) -> str:
    if key not in mapping:
        raise ValueError(f"{what}: missing {key!r}; have {sorted(mapping)}")
    return mapping[key]


def _field(html_by_id: dict[str, str], element_id: str) -> str:
    return html_text(_need(html_by_id, element_id, "element"))


def _rx(template: str) -> re.Pattern[str]:
    """Compile a pattern in which {Q} stands for one captured displayed quantity."""
    return re.compile(template.replace("{Q}", f"({_QTY})"), re.IGNORECASE)


def _match(pattern: re.Pattern[str], text: str, what: str) -> re.Match[str]:
    m = pattern.fullmatch(text)
    if m is None:
        raise ValueError(f"{what}: unrecognized text {text!r}")
    return m


_YARDS_WORD = _rx(r"(.+?) yards?")
_YD = _rx(r"(.+?) yd")
_COST_NONE = "Add a price per yard to see this"
_COST = _rx(r"\$([0-9]+\.[0-9]{2}) at \$([0-9]+\.[0-9]{2})/yd")


def _cost(text: str, what: str) -> dict | None:
    """The Stitch Desk cost line: None until a price is entered, else {cost, price} in dollars."""
    if text == _COST_NONE:
        return None
    m = _match(_COST, text, what)
    return {"cost": Fraction(m[1]), "price": Fraction(m[2])}


# ---------------------------------------------------------------------------------------------
# Quilter's Paradise
# ---------------------------------------------------------------------------------------------

_QP_BACKING = re.compile(
    rf"(?P<yards>[^()\n]*?) ?\((?P<inches>[^()\n]*?) inches\) when width is (?P<width>\S+)"
    rf" and length is (?P<length>\S+)\s+(?P<seams>{_NUM}) seam(?:s|\(s\))? will be needed\.?",
    re.IGNORECASE,
)


def parse_qp_backing(html: str) -> dict:
    """The Backing and Batting page's result element:
    "<yards> (<inches> inches) when width is <W> and length is <L><br><N> seam(s) will be
    needed." Returns {yards, inches, width, length, seams}."""
    text = html_text(html)
    m = _QP_BACKING.fullmatch(text)
    if m is None:
        raise ValueError(f"QP backing: unrecognized result {text!r}")
    return {
        "yards": parse_yards(m["yards"]),
        "inches": parse_decimal_inches(m["inches"]),
        "width": parse_decimal_inches(m["width"]),
        "length": parse_decimal_inches(m["length"]),
        "seams": int(m["seams"]),
    }


def parse_qp_binding(html_by_id: dict[str, str]) -> dict:
    """The Binding page's elements "binding length", "yardage" and "number strips".
    Returns {binding_length, yards, strips}."""
    return {
        "binding_length": parse_decimal_inches(_field(html_by_id, "binding length")),
        "yards": parse_yards(_field(html_by_id, "yardage")),
        "strips": parse_count(_field(html_by_id, "number strips")),
    }


QP_MAX_BORDERS = 5  # the Border page offers up to five borders (MATH.md 5.2)


def parse_qp_border(html_by_id: dict[str, str], band_count: int) -> dict:
    """The Border page's per-band StripWidth{i}, Border{i}Yardage, NumStrips{i} (straight joins)
    and OverallWidth, OverallLength. Returns {bands: [{strip_width, yards, strips}],
    overall_width, overall_length}."""
    if isinstance(band_count, bool) or not 1 <= band_count <= QP_MAX_BORDERS:
        raise ValueError(f"QP border: band_count must be 1 to {QP_MAX_BORDERS}, got {band_count}")
    bands = [
        {
            "strip_width": parse_decimal_inches(_field(html_by_id, f"StripWidth{i}")),
            "yards": parse_yards(_field(html_by_id, f"Border{i}Yardage")),
            "strips": parse_count(_field(html_by_id, f"NumStrips{i}")),
        }
        for i in range(1, band_count + 1)
    ]
    return {
        "bands": bands,
        "overall_width": parse_decimal_inches(_field(html_by_id, "OverallWidth")),
        "overall_length": parse_decimal_inches(_field(html_by_id, "OverallLength")),
    }


# ---------------------------------------------------------------------------------------------
# Nebraska Quilt Company
# ---------------------------------------------------------------------------------------------

_NQC_DETAILS = re.compile(
    rf"({_NUM}) strips? needed \(({_DEC})[{_INCH_MARKS}] total length\)", re.IGNORECASE
)
_NQC_COVERAGE = re.compile(rf"({_DEC})[{_INCH_MARKS}]")


def _nqc_inch_mark(text: str, pattern: re.Pattern[str], what: str) -> re.Match[str]:
    if _collapse(text) in _DASHES:
        raise ValueError(f"NQC {what}: the page shows no value ({text!r})")
    m = pattern.fullmatch(_collapse(text))
    if m is None:
        raise ValueError(f"NQC {what}: unrecognized text {text!r}")
    return m


def parse_nqc(html_by_id: dict[str, str]) -> dict:
    """The Backing and Binding page's bindingValue, bindingDetails and, per layout,
    {vertical,horizontal}{Backing,Panels,Coverage}. Returns {binding: {yards, strips,
    total_length}, vertical: {yards, panels, coverage}, horizontal: {...}}."""
    details = _nqc_inch_mark(_field(html_by_id, "bindingDetails"), _NQC_DETAILS, "bindingDetails")
    result = {
        "binding": {
            "yards": parse_yards(_field(html_by_id, "bindingValue")),
            "strips": int(details[1]),
            "total_length": parse_decimal_inches(details[2]),
        }
    }
    for layout in ("vertical", "horizontal"):
        coverage_id = f"{layout}Coverage"
        coverage = _nqc_inch_mark(_field(html_by_id, coverage_id), _NQC_COVERAGE, coverage_id)
        result[layout] = {
            "yards": parse_yards(_field(html_by_id, f"{layout}Backing")),
            "panels": parse_count(_field(html_by_id, f"{layout}Panels")),
            "coverage": parse_decimal_inches(coverage[1]),
        }
    return result


# ---------------------------------------------------------------------------------------------
# My Favorite Quilt Store (backing and batting; results_1 and results_2)
# ---------------------------------------------------------------------------------------------

_MFQS_FABRIC = _rx(r'{Q}" fabric')
_MFQS_WIDE = '108" wide backing'
_MFQS_ONE_PIECE = _rx(r"Fits in one piece - no seam needed\.")
_MFQS_PIECED = _rx(r"([0-9]+) panels, pieced with (horizontal|vertical) seams?\.")
_MFQS_SIZE = _rx(r'Size needed: {Q}" x {Q}"')
_MFQS_PACKAGE = _rx(r"Recommended package: (.+)")
_MFQS_SHRINK = _rx(r'Estimated shrinkage {Q}" x {Q}" -> about {Q}" x {Q}" after the first wash\.')
_MFQS_PACKAGES = ("Crib", "Twin", "Full", "Queen", "King")
_MFQS_NO_PACKAGE = "Larger than King - consider batting by the roll"


def _mfqs_block(header: str, yards: str, layout: str, *, wide: bool) -> dict:
    if wide:
        if header != _MFQS_WIDE:
            raise ValueError(f"MFQS backing: expected {_MFQS_WIDE!r}, got {header!r}")
        fabric_width = Fraction(108)
    else:
        fabric_width = _quantity(_match(_MFQS_FABRIC, header, "MFQS fabric")[1], "MFQS fabric")
    if _MFQS_ONE_PIECE.fullmatch(layout):
        panels, seams = 1, "none"
    else:
        m = _match(_MFQS_PIECED, layout, "MFQS layout")
        panels, seams = int(m[1]), m[2].lower()
    return {
        "fabric_width": fabric_width,
        "yards": parse_yards(_match(_YARDS_WORD, yards, "MFQS yards")[1]),
        "panels": panels,
        "seams": seams,
    }


def parse_mfqs_backing(html_by_id: dict[str, str]) -> dict:
    """My Favorite Quilt Store's results_1 (backing on the typed fabric, then 108 in wide unless
    the typed fabric is 108) and results_2 (batting).

    Returns {backing: {fabric_width, yards, panels, seams}, wide: {...} or None,
    batting: {width, length, package, shrink_width, shrink_length, washed_width, washed_length}};
    seams is "horizontal", "vertical" or "none", and package is None when the page recommends
    batting by the roll.
    """
    lines = _lines(_need(html_by_id, "results_1", "MFQS"))
    if not lines or lines[0] != "Backing" or len(lines) not in (4, 7):
        raise ValueError(f"MFQS backing: unrecognized result {lines!r}")
    backing = _mfqs_block(*lines[1:4], wide=False)
    wide = _mfqs_block(*lines[4:7], wide=True) if len(lines) == 7 else None

    lines = _lines(_need(html_by_id, "results_2", "MFQS"))
    if len(lines) != 4 or lines[0] != "Batting":
        raise ValueError(f"MFQS batting: unrecognized result {lines!r}")
    size = _match(_MFQS_SIZE, lines[1], "MFQS batting size")
    package = _match(_MFQS_PACKAGE, lines[2], "MFQS package")[1]
    if package == _MFQS_NO_PACKAGE:
        package = None
    elif package not in _MFQS_PACKAGES:
        raise ValueError(f"MFQS package: unknown name {package!r}")
    shrink = _match(_MFQS_SHRINK, lines[3], "MFQS shrinkage")
    batting = {
        "width": _quantity(size[1], "MFQS batting"),
        "length": _quantity(size[2], "MFQS batting"),
        "package": package,
        "shrink_width": _quantity(shrink[1], "MFQS shrinkage"),
        "shrink_length": _quantity(shrink[2], "MFQS shrinkage"),
        "washed_width": _quantity(shrink[3], "MFQS shrinkage"),
        "washed_length": _quantity(shrink[4], "MFQS shrinkage"),
    }
    return {"backing": backing, "wide": wide, "batting": batting}


# ---------------------------------------------------------------------------------------------
# The Stitch Desk (backing and batting; binding). Both write one "results" block whose values
# sit in elements with fixed ids.
# ---------------------------------------------------------------------------------------------

_SD_HEAD = _rx(r'You need (.+?) yd of {Q}" backing\.')
_SD_SUB = _rx(r'Backing finishes at {Q}" x {Q}", giving {Q}" overhang on every side\.')
_SD_CUT = _rx(r'Cut ([0-9]+) panels, each {Q}" long\. Join with (vertical|horizontal) seams\.')
_SD_CUT_ONE = _rx(r'One panel, cut {Q}" long\. No seam needed\.')
_SD_BATTING = _rx(
    r'{Q}" x {Q}" at {Q}" overhang\. (?:Nearest precut: ([A-Za-z]+)|Buy off the roll)'
)
_SD_ALT = _rx(r'(.+?) yd of 108" wide back saves (.+?) yd')
_SD_ALT_CHEAPER = _rx(r'{Q}" is already the cheaper option here')
_SD_ALT_WIDE = "You are already on wide backing"
_SD_PRECUTS = ("Craft", "Crib", "Throw", "Twin", "Full", "Queen", "King")


def parse_stitchdesk_backing(html_by_id: dict[str, str]) -> dict:
    """The Stitch Desk backing calculator's "results" block (ids rHead, rSub, rCut, rBat, rAlt,
    rCost).

    Returns {backing: {fabric_width, yards, backing_width, backing_length, overhang, panels,
    cut_length, seams}, batting: {width, length, overhang, precut}, wide: {fabric_width, yards,
    saves} or None, wide_note, cost}. wide_note is None when the 108 in line shows a saving,
    "fabric_cheaper" when the typed fabric is already cheaper, "already_wide" on 108 in or wider;
    cost is None until a price is entered, else {cost, price}. precut is None for "Buy off the
    roll".
    """
    what = "Stitch Desk backing"
    texts = _texts_by_id(_need(html_by_id, "results", what), what)
    head = _match(_SD_HEAD, _need(texts, "rHead", what), what)
    sub = _match(_SD_SUB, _need(texts, "rSub", what), what)
    cut_text = _need(texts, "rCut", what)
    if m := _SD_CUT_ONE.fullmatch(cut_text):
        panels, cut_length, seams = 1, _quantity(m[1], what), "none"
    else:
        m = _match(_SD_CUT, cut_text, what)
        panels, cut_length, seams = int(m[1]), _quantity(m[2], what), m[3].lower()
    bat = _match(_SD_BATTING, _need(texts, "rBat", what), what)
    if bat[4] is not None and bat[4] not in _SD_PRECUTS:
        raise ValueError(f"{what}: unknown precut {bat[4]!r}")
    alt_text = _need(texts, "rAlt", what)
    wide, wide_note = None, None
    if alt_text == _SD_ALT_WIDE:
        wide_note = "already_wide"
    elif _SD_ALT_CHEAPER.fullmatch(alt_text):
        wide_note = "fabric_cheaper"
    else:
        alt = _match(_SD_ALT, alt_text, what)
        wide = {
            "fabric_width": Fraction(108),
            "yards": parse_yards(alt[1]),
            "saves": parse_yards(alt[2]),
        }
    return {
        "backing": {
            "fabric_width": _quantity(head[2], what),
            "yards": parse_yards(head[1]),
            "backing_width": _quantity(sub[1], what),
            "backing_length": _quantity(sub[2], what),
            "overhang": _quantity(sub[3], what),
            "panels": panels,
            "cut_length": cut_length,
            "seams": seams,
        },
        "batting": {
            "width": _quantity(bat[1], what),
            "length": _quantity(bat[2], what),
            "overhang": _quantity(bat[3], what),
            "precut": bat[4],
        },
        "wide": wide,
        "wide_note": wide_note,
        "cost": _cost(_need(texts, "rCost", what), what),
    }


_SDB_HEAD = _rx(r"You need (.+?) yd for binding\.")
_SDB_SUB = _rx(r'Perimeter is {Q}", plus {Q}" for mitred corners and the closing join\.')
_SDB_STRIPS = _rx(r'Cut ([0-9]+) strips? at {Q}" wide')
_SDB_BIAS_SQUARE = _rx(r'Continuous bias from one {Q}" square')
_SDB_BIAS_STRIPS = "Bias strips cut across the width"
_SDB_JOINS = _rx(r"([0-9]+) diagonal joins?, pressed open")
_SDB_BIAS_JOINS = "None, bias is cut as one continuous strip"
_SDB_FINISHED = _rx(r'About {Q}" once folded and sewn')


def parse_stitchdesk_binding(html_by_id: dict[str, str]) -> dict:
    """The Stitch Desk binding calculator's "results" block (ids bHead, bSub, bStrips, bJoins,
    bFin, bCost).

    Returns {type, yards, perimeter, extra, strips, strip_width, joins, bias_square,
    finished_width, cost}. type is "straight" or "bias"; a bias result has strips, strip_width
    and joins None, and bias_square the cut square (None when cut across the width).
    """
    what = "Stitch Desk binding"
    texts = _texts_by_id(_need(html_by_id, "results", what), what)
    head = _match(_SDB_HEAD, _need(texts, "bHead", what), what)
    sub = _match(_SDB_SUB, _need(texts, "bSub", what), what)
    strips_text = _need(texts, "bStrips", what)
    joins_text = _need(texts, "bJoins", what)
    strips = strip_width = joins = bias_square = None
    if m := _SDB_STRIPS.fullmatch(strips_text):
        kind = "straight"
        strips, strip_width = int(m[1]), _quantity(m[2], what)
        joins = int(_match(_SDB_JOINS, joins_text, what)[1])
    else:
        kind = "bias"
        if strips_text != _SDB_BIAS_STRIPS:
            bias_square = _quantity(_match(_SDB_BIAS_SQUARE, strips_text, what)[1], what)
        if joins_text != _SDB_BIAS_JOINS:
            raise ValueError(f"{what}: bias strips with join text {joins_text!r}")
    return {
        "type": kind,
        "yards": parse_yards(head[1]),
        "perimeter": _quantity(sub[1], what),
        "extra": _quantity(sub[2], what),
        "strips": strips,
        "strip_width": strip_width,
        "joins": joins,
        "bias_square": bias_square,
        "finished_width": _quantity(
            _match(_SDB_FINISHED, _need(texts, "bFin", what), what)[1], what
        ),
        "cost": _cost(_need(texts, "bCost", what), what),
    }


# ---------------------------------------------------------------------------------------------
# QuiltKeeper Studio (binding; "results" rows of label and value spans)
# ---------------------------------------------------------------------------------------------

_QK_CUT = _rx(r'Cut ([0-9]+) strips? at {Q}" x WOF')
_QK_INCHES = _rx(r'{Q}"')
_QK_LABELS = (
    "Yardage to buy",
    "Cutting instruction",
    "Strips needed",
    "Binding length",
    "Perimeter",
)


def parse_quiltkeeper_binding(html_by_id: dict[str, str]) -> dict:
    """QuiltKeeper Studio's binding "results" rows. Returns {yards, strips, strip_width,
    binding_length, perimeter}; the strip count shown twice must agree."""
    what = "QuiltKeeper binding"
    rows: dict[str, str] = {}
    for label, value in _label_values(_need(html_by_id, "results", what), what):
        if label not in _QK_LABELS or label in rows:
            raise ValueError(f"{what}: unexpected row {label!r}")
        rows[label] = value
    cut = _match(_QK_CUT, _need(rows, "Cutting instruction", what), what)
    strips = parse_count(_need(rows, "Strips needed", what))
    if int(cut[1]) != strips:
        raise ValueError(f"{what}: the cutting line says {cut[1]} strips, the count {strips}")
    return {
        "yards": parse_yards(_match(_YD, _need(rows, "Yardage to buy", what), what)[1]),
        "strips": strips,
        "strip_width": _quantity(cut[2], what),
        "binding_length": _quantity(
            _match(_QK_INCHES, _need(rows, "Binding length", what), what)[1], what
        ),
        "perimeter": _quantity(_match(_QK_INCHES, _need(rows, "Perimeter", what), what)[1], what),
    }


# ---------------------------------------------------------------------------------------------
# Sew Becca (border; "result")
# ---------------------------------------------------------------------------------------------

_SB_YARDS = _rx(r"Yardage Required: (.+?) yards?")
_SB_STRIPS = _rx(r"Number of Strips Required: ([0-9]+)")


def parse_sewbecca_border(html_by_id: dict[str, str]) -> dict:
    """Sew Becca's border "result" list. Returns {yards, strips}."""
    what = "Sew Becca border"
    items = [text for tag, _attrs, text in _elements(_need(html_by_id, "result", what))
             if tag == "li"]  # fmt: skip
    if len(items) != 2:
        raise ValueError(f"{what}: expected 2 result lines, got {items!r}")
    return {
        "yards": parse_yards(_match(_SB_YARDS, items[0], what)[1]),
        "strips": int(_match(_SB_STRIPS, items[1], what)[1]),
    }


# ---------------------------------------------------------------------------------------------
# Quilt Calculator (border; "results" rows of label and value spans)
# ---------------------------------------------------------------------------------------------

_QC_BORDER = _rx(r'Border ([0-9]+): {Q}" wide - yardage')
_QC_AFTER = _rx(r"Quilt size after border ([0-9]+)")
_QC_SIZE = _rx(r'{Q}" x {Q}"')


def parse_qc_border(html_by_id: dict[str, str]) -> dict:
    """Quilt Calculator's border "results": per enabled border a yardage row and a size row.
    Returns {borders: [{index, width, yards, width_after, length_after}]}."""
    what = "Quilt Calculator border"
    rows = _label_values(_need(html_by_id, "results", what), what)
    if not rows or len(rows) % 2:
        raise ValueError(f"{what}: expected yardage and size rows in pairs, got {rows!r}")
    borders = []
    for k in range(0, len(rows), 2):
        (border_label, yards), (after_label, size) = rows[k], rows[k + 1]
        border = _match(_QC_BORDER, border_label, what)
        after = _match(_QC_AFTER, after_label, what)
        index = len(borders) + 1
        if int(border[1]) != index or int(after[1]) != index:
            raise ValueError(f"{what}: rows out of order at border {index}: {rows[k:k + 2]!r}")
        dims = _match(_QC_SIZE, size, what)
        borders.append(
            {
                "index": index,
                "width": _quantity(border[2], what),
                "yards": parse_yards(_match(_YARDS_WORD, yards, what)[1]),
                "width_after": _quantity(dims[1], what),
                "length_after": _quantity(dims[2], what),
            }
        )
    return {"borders": borders}


# ---------------------------------------------------------------------------------------------
# Omni Calculator (quilt backing and batting). The driver records the result region's visible
# text (innerText) under "results_text", so this parser reads lines, not HTML.
# ---------------------------------------------------------------------------------------------

_OMNI_NEED = _rx(r"You need {Q} yards \({Q} m\) of fabric\.")
_OMNI_CUT = _rx(r"Cut your fabric into ([0-9]+) pieces, each:")
_OMNI_ONE = "Your quilt backing is in 1 piece that's:"
_OMNI_DIM = _rx(r"{Q} inches ?\({Q} cm\) (wide|long) \((W|L)\)(?:, and|\.)")
_OMNI_ADDED = _rx(
    r"We automatically add {Q} inches \({Q} cm\) of extra backing/batting to all sides of the"
    r" quilt top\."
)
_OMNI_TOO_MANY = (
    "You will need more than 5 pieces of fabric. We recommend that you buy a bigger bolt of"
    " fabric."
)


def parse_omni_backing(html_by_id: dict[str, str]) -> dict:
    """Omni's quilt calculator result text (backing or batting mode), key "results_text".

    Returns {yards, meters, pieces, piece_width, piece_width_cm, piece_length, piece_length_cm,
    added_per_side, added_per_side_cm, too_many_pieces}. When the page says it needs more than
    5 pieces, too_many_pieces is True and every other value is None.
    """
    what = "Omni backing"
    text = _need(html_by_id, "results_text", what)
    if not isinstance(text, str):
        raise ValueError(f"{what}: expected text, got {type(text).__name__}")
    lines = [line for line in (_ascii(part) for part in text.split("\n")) if line]
    if lines and lines[0] == "Results":
        lines = lines[1:]
    if lines == [_OMNI_TOO_MANY]:
        keys = ("yards", "meters", "pieces", "piece_width", "piece_width_cm", "piece_length",
                "piece_length_cm", "added_per_side", "added_per_side_cm")  # fmt: skip
        return {**dict.fromkeys(keys), "too_many_pieces": True}
    if len(lines) != 5:
        raise ValueError(f"{what}: unrecognized result {lines!r}")
    need = _match(_OMNI_NEED, lines[0], what)
    if lines[1] == _OMNI_ONE:
        pieces = 1
    else:
        pieces = int(_match(_OMNI_CUT, lines[1], what)[1])
    dims = {}
    for line in lines[2:4]:
        m = _match(_OMNI_DIM, line, what)
        word, letter = m[3].lower(), m[4].upper()
        if (word, letter) not in (("wide", "W"), ("long", "L")) or word in dims:
            raise ValueError(f"{what}: unexpected dimension line {line!r}")
        dims[word] = (_quantity(m[1], what), _quantity(m[2], what))
    if set(dims) != {"wide", "long"}:
        raise ValueError(f"{what}: expected one width and one length line, got {lines[2:4]!r}")
    added = _match(_OMNI_ADDED, lines[4], what)
    return {
        "yards": _quantity(need[1], what),
        "meters": _quantity(need[2], what),
        "pieces": pieces,
        "piece_width": dims["wide"][0],
        "piece_width_cm": dims["wide"][1],
        "piece_length": dims["long"][0],
        "piece_length_cm": dims["long"][1],
        "added_per_side": _quantity(added[1], what),
        "added_per_side_cm": _quantity(added[2], what),
        "too_many_pieces": False,
    }


# ---------------------------------------------------------------------------------------------
# Designed to Quilt (border; a Forminator form whose computed fields calculation-1 to -13 the
# driver records as "value:calculation-N")
# ---------------------------------------------------------------------------------------------

_DTQ_LAYOUTS = {
    "straight": {"top_length": 1, "side_length": 2, "total_length": 5, "strips": 7,
                 "length": 12, "yards": 8},
    "mitered": {"top_length": 3, "side_length": 4, "total_length": 6, "strips": 10,
                "length": 13, "yards": 11},
}  # fmt: skip
_DTQ_CUT_WIDTH = 9


def parse_dtq_border(html_by_id: dict[str, str]) -> dict:
    """Designed to Quilt's computed border fields, keyed "value:calculation-N" (or
    "calculation-N"). Returns {cut_width, straight: {top_length, side_length, total_length,
    strips, length, yards}, mitered: {...}}; lengths in inches, yards as shown (decimal)."""
    what = "Designed to Quilt border"
    fields: dict[str, str] = {}
    for key, value in html_by_id.items():
        name = key.removeprefix("value:")
        if name in fields:
            raise ValueError(f"{what}: {name!r} appears under two keys")
        fields[name] = value

    def value(n: int) -> str:
        return html_text(_need(fields, f"calculation-{n}", what))

    result: dict = {"cut_width": _quantity(value(_DTQ_CUT_WIDTH), what)}
    for layout, ids in _DTQ_LAYOUTS.items():
        result[layout] = {
            key: parse_count(value(n)) if key == "strips" else _quantity(value(n), what)
            for key, n in ids.items()
        }
    return result


# ---------------------------------------------------------------------------------------------
# Quilter's Paradise piece count
# ---------------------------------------------------------------------------------------------


def parse_qp_piece_count(html_by_id: dict[str, str]) -> dict:
    """The Piece Count page's results_num_pieces{1,2}, results_piece_width{1,2} and
    results_piece_length{1,2}: 1 cuts the piece as typed (W x L), 2 turned (L x W).
    Returns {as_typed: {pieces, piece_width, piece_length}, turned: {...}}."""
    result = {}
    for name, i in (("as_typed", 1), ("turned", 2)):
        result[name] = {
            "pieces": parse_count(_field(html_by_id, f"results_num_pieces{i}")),
            "piece_width": parse_decimal_inches(_field(html_by_id, f"results_piece_width{i}")),
            "piece_length": parse_decimal_inches(_field(html_by_id, f"results_piece_length{i}")),
        }
    return result
