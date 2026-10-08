"""Parse the text that the D2 calculators display into exact numbers.

Each parser reads the HTML a page wrote into its result elements (the innerHTML the Playwright
driver captures) and returns Fractions for inches and yards and ints for counts. Anything that
does not match the recorded output shape raises ValueError: a guessed number would turn a page
change into a silent wrong comparison.

Stdlib only, because the test also runs under Pyodide.
"""

from __future__ import annotations

import re
from fractions import Fraction
from html.parser import HTMLParser

__all__ = [
    "html_text",
    "parse_count",
    "parse_decimal_inches",
    "parse_mfqs",
    "parse_nqc",
    "parse_qp_backing",
    "parse_qp_binding",
    "parse_qp_border",
    "parse_yards",
]

INCHES_PER_YARD = 36

# Text a page shows when it has no value. Named here so the error says "no value" instead of
# "unrecognized", which points the reader at the inputs rather than at this parser.
_PLACEHOLDERS = {"N/A", "NA", "NAN", "INFINITY", "-INFINITY", "UNDEFINED", "-", "--"}
_DASHES = {"\u2012", "\u2013", "\u2014", "\u2015", "\u2212"}

_NUM = r"[0-9]+"
_DEC = r"[0-9]+(?:\.[0-9]+)?"
_MIXED = re.compile(rf"({_NUM}) ({_NUM})/({_NUM})")
_FRACTION = re.compile(rf"({_NUM})/({_NUM})")
_WHOLE = re.compile(_NUM)
_NQC_YARDS_INCHES = re.compile(rf"({_NUM}) yards? ?\+ ?({_DEC}) inch(?:es)?", re.IGNORECASE)
_NQC_YARDS = re.compile(rf"({_NUM}) yards?", re.IGNORECASE)
_NQC_INCHES = re.compile(rf"({_DEC}) inch(?:es)?", re.IGNORECASE)
_DECIMAL = re.compile(_DEC)
_INCH_MARKS = "\"\u201d\u2033"

# JS prints the shortest decimal that round-trips a double, so binary error can surface as
# 348.00000000000006. Every true value these pages derive from eighth-inch inputs has at most
# three decimals (1/8 = 0.125), and such noise sits within about 1e-13 of it, so a value within
# 1e-9 of a thousandth is that thousandth. Anything farther away is a real value and stays exact.
_NOISE = Fraction(1, 10**9)


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[list[str]] = [[]]
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "br":
            self.lines.append([])
        elif tag in ("script", "style"):
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.lines[-1].append(data)


def html_text(fragment: str) -> str:
    """Visible text of an HTML fragment: <br> ends a line, entities are decoded (&nbsp; is a
    space), whitespace collapses within each line, and the result is stripped."""
    collector = _TextCollector()
    collector.feed(fragment)
    collector.close()
    # str.split() treats U+00A0 as whitespace, so a decoded &nbsp; collapses like a space; a
    # newline in the source is HTML whitespace too, so only <br> breaks a line.
    lines = [" ".join("".join(parts).split()) for parts in collector.lines]
    return "\n".join(lines).strip()


def _clean(text: str, what: str) -> str:
    if not isinstance(text, str):
        raise ValueError(f"{what}: expected text, got {type(text).__name__}")
    cleaned = " ".join(text.split())
    if not cleaned:
        raise ValueError(f"{what}: empty text")
    if cleaned.upper() in _PLACEHOLDERS or cleaned in _DASHES:
        raise ValueError(f"{what}: the page shows no value ({text!r})")
    return cleaned


def _ratio(numerator: str, denominator: str, text: str) -> Fraction:
    if int(denominator) == 0:
        raise ValueError(f"yards: zero denominator in {text!r}")
    return Fraction(int(numerator), int(denominator))


def parse_yards(text: str) -> Fraction:
    """Yards shown as "8 3/8", " 3/8", "8 ", "3/4", "4", or Nebraska's "4 Yards + 9 Inches",
    "1 Yard", "27 Inches" (whole yards + inches / 36)."""
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


def parse_decimal_inches(text: str) -> Fraction:
    """Inches printed by JS as a plain decimal ("301.5", "12", "24.125"), exact, with float
    noise within 1e-9 of a thousandth snapped to it."""
    cleaned = _clean(text, "inches")
    if not _DECIMAL.fullmatch(cleaned):
        raise ValueError(f"inches: not a plain decimal {text!r}")
    value = Fraction(cleaned)
    nearest = Fraction(round(value * 1000), 1000)
    if abs(value - nearest) <= _NOISE:
        return nearest
    return value


def parse_count(text: str) -> int:
    """A whole count such as a strip or panel number."""
    cleaned = _clean(text, "count")
    if not _WHOLE.fullmatch(cleaned):
        raise ValueError(f"count: not a whole number {text!r}")
    return int(cleaned)


def _field(html_by_id: dict[str, str], element_id: str) -> str:
    if element_id not in html_by_id:
        raise ValueError(f"missing element id {element_id!r}; have {sorted(html_by_id)}")
    return html_text(html_by_id[element_id])


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
    m = pattern.fullmatch(_clean(text, what))
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
# My Favorite Quilt Store: reserved
# ---------------------------------------------------------------------------------------------
# MATH.md 5.2 lists this page as "record only" with undocumented internals, and its displayed
# result has not been recorded yet. The parser is written against a recorded browser run, so it
# reads what the page really shows instead of an invented shape.


def parse_mfqs(html_by_id: dict[str, str]) -> dict:
    raise NotImplementedError(
        "My Favorite Quilt Store output format is not recorded yet; record a real browser run "
        "of its result elements, then write this parser against that record"
    )
