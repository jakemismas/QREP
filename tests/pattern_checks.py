"""Scripted acceptance checks for the QREP pattern PDF (PATTERN-SPEC section 6).

Usage:
    python tests/pattern_checks.py <pdf> <model.json> [--references DIR] [--denylist FILE]
        [--reference-names FILE]

It prints one line per check, "<id> <pass|fail|not run>: <evidence>", then the count of
figure placeholder frames, and exits 1 when any check fails. run_checks() returns the same
results to a test.

The checker never imports qrep, so a bug shared with qrep.construct or qrep.export cannot
pass both. From the model JSON alone it recomputes, in integer eighths, MATH.md F4 (border
strips), F6 to F12 (binding, backing, wide back, batting), the block census (block types and
make counts), the quilt-center and strip-set checkpoints, and the fabric area order. Applied
to the printed cut lines and the model's settings, it recomputes F2 and F3 (yields, strip and
set counts) and F5 (purchase lines). Which pieces a construction method needs is A3's
decision and is not re-derived here: a short cut list that is consistent with itself and with
its own make counts passes PS-19 and PS-20 as long as the block census holds. pypdf is
imported inside read_pdf, so the module also loads where pypdf is missing.

It implements every [S] check of section 6 except PS-04 (two generations; A4a, C2a and A6
carry it) and PS-40 (the web screen; C2's end-to-end test carries it), plus the [M] parts
that the model JSON can answer. [V] checks are D8's and E4's. PS-39 runs only when a local
reference directory is passed and reports "not run" otherwise.

Text is extracted with pypdf, then normalized as section 6 says: whitespace runs collapse
to one space and straight double quotes drop out, so 6 1/2" reads 6 1/2. The checker groups
the text runs into lines itself, because pypdf's plain extraction puts each table cell on a
line of its own. The phrases it parses, all taken from PATTERN-SPEC and MATH.md (shown
normalized):

- Section headings: a line that is exactly the PS-02 heading, optionally "(continued)".
- Footer: "page N of M", the pattern name and "QREP x.y.z" on the bottom lines of a page.
- Subheadings: "HST unit 1", "QST unit 1", "Snowball unit 1", "Flying geese unit 1",
  "Unit 1", "Strip set 1" (Making the units) and "Block 1" (Making the blocks).
- Steps: lines that start "N. "; a step runs on until the next structural line.
- Cutting: a fabric heading is a letter and name with a swatch to its left; steps read
  "Cut (N) W x WOF strips."; subcuts read "A2: subcut (6) strips into (120) 2 squares,
  20 per strip." (a rectangle as "W x L rectangles"), and a partly used last strip is
  stated with "last strip" and its piece count; strip-set strips read "Set aside ... (A1)
  for strip set 1"; unit pieces end "for HST unit 1"; spare pieces "(k) spare"; binding
  strips "for binding"; borders "For each side border, join (k) strips ... trim to L. For
  the top and bottom borders, join (k) strips each and trim to L."
- Piece lists: a line that starts "A1 ... (q)" or "(q) A1" inside a unit or block.
- Make counts "Make N." (mirror pairs "Make 8 (4 of each)"); checkpoints "should measure
  W x H", "should measure S square" and "Trim to S square".
- Fabric requirements: a row per fabric starting with its letter and ending in "N yd",
  with a swatch; the binding row with "(N) 2 1/2 x WOF strips"; the backing row with
  "N lengths of L", "seams run across the quilt" or "seams run along the quilt" and
  "or Y yd of 108 wide backing"; the batting row "W x H" plus the package class and size.
- Before you begin: numbered rules; an abbreviation is defined by a rule that holds both
  the abbreviation and its expansion; photo reads state "(N) squares read with low
  confidence".
- Quilt assembly: "The quilt center should measure W x H."
- Layout chart: row and column numbers, a letter per cell, split parts labeled "Rows a to
  b, columns c to d", uncertain cells marked by dots (small filled round paths).
- Figure placeholders: any line containing the word "placeholder".
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# MATH.md section 1.3 defaults, in eighths, for settings a model JSON leaves out. They
# mirror qrep/model/schema.py by value only; importing it would share its bugs.
SETTING_DEFAULTS = {
    "seam_allowance": 2,
    "wof": 320,
    "binding_extra": 80,
    "backing_margin": 64,
    "backing_width": 336,
    "wide_back_width": 864,
    "backing_pieced_allowance": 72,
    "backing_one_piece_allowance": 36,
    "purchase_increment": 72,
    "top_margin": 10,
}
BINDING_STRIP_DEFAULT = 20
BORDER_JOIN_LOSS = 4  # MATH.md j: 1/2 in per straight join
BACKING_SEAM_LOSS = 8  # MATH.md s: 1 in per backing seam
# MATH.md F12: packages in the order they are tried, in inches.
BATTING_PACKAGES = (("crib", 45, 60), ("twin", 72, 90), ("full", 90, 96), ("queen", 90, 108),
                    ("king", 124, 120))

HEADINGS = ("Fabric requirements", "Before you begin", "Cutting", "Making the units",
            "Making the blocks", "Quilt assembly", "Borders", "Finishing", "Layout chart",
            "Coloring page")
REQUIRED_HEADINGS = ("Fabric requirements", "Before you begin", "Cutting", "Quilt assembly",
                     "Finishing", "Layout chart")
TRIANGLE_KINDS = ("HST", "QST", "Snowball", "Flying geese")
ABBREVIATIONS = {"WOF": "width of fabric", "RST": "right sides together",
                 "HST": "half-square triangle", "QST": "quarter-square triangle", "yd": "yard"}
STOP_IDS = {"a", "an", "and", "as", "at", "be", "by", "i", "if", "in", "is", "it", "of", "on",
            "or", "the", "to", "x", "yd"}

NUM = r"(?:\d+ \d+/\d+|\d+/\d+|\d+)"
LETTER = r"[A-HJ-NP-Z]"
LABEL = r"[A-HJ-NP-Z]\d{1,2}"
YARDS_RE = re.compile(rf"({NUM}) yd\b")
FOOTER_RE = re.compile(r"\bpage (\d+) of (\d+)\b")
VERSION_RE = re.compile(r"\bQREP (\d+(?:\.\d+)+)\b")
STEP_RE = re.compile(r"^(\d+)\. (.*)$")
UNIT_HEAD_RE = re.compile(r"^(?:(HST|QST|Snowball|Flying geese) unit|Unit|Strip set) (\d+)$")
BLOCK_HEAD_RE = re.compile(r"^Block (\d+)$")
FABRIC_HEAD_RE = re.compile(rf"^({LETTER}) ([A-Z][A-Za-z]*(?: [A-Za-z]+){{0,3}})$")
SUBCUT_RE = re.compile(
    rf"^({LABEL}): subcut \((\d+)\) strips? into \((\d+)\) ({NUM})(?: x ({NUM}))? "
    r"(squares?|rectangles?)\b(.*)$")
SET_ASIDE_RE = re.compile(rf"Set aside\b[^.]*?\(({LABEL})\)[^.]*?\bstrip set (\d+)")
CUT_STEP_RE = re.compile(rf"^Cut \((\d+)\) ({NUM}) x WOF strips?\b")
MAKE_RE = re.compile(r"\bMake (\d+)(?: \((\d+) of each\))?")
CHECKPOINT_RE = re.compile(
    rf"(?:should measure|Trim(?: each unit)? to) ({NUM})(?: x ({NUM}))?(?: square)?")
FIG_RE = re.compile(r"\bFig\. (\d+)")
PIECE_RE = re.compile(rf"^(?:({LABEL})\b[^()]*\((\d+)\)|\((\d+)\) ({LABEL})\b)")
MIRROR_RE = re.compile(r"mirror image of (?:(HST|QST|Snowball|Flying geese) )?unit (\d+)")
DATE_RES = (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
            re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|"
                       r"October|November|December) \d{1,2}(?:, \d{4})?\b"))
ALTERNATE_RE = re.compile(r"\balternat(?:e|ive|ively)\b|\bor you can\b|\boptionally\b|"
                          r"\banother (?:method|way|technique)\b", re.IGNORECASE)


# ---------------------------------------------------------------- numbers and text


def normalize(text: str) -> str:
    """Section 6 normalization: collapse whitespace, drop straight double quotes."""
    return re.sub(r"\s+", " ", text.replace('"', "")).strip()


def eighths(text: str) -> int | None:
    """Parse "6 1/2", "3/4" or "40" into eighths; None when it is not a whole eighth."""
    parts = text.split()
    whole, frac = (0, parts[0]) if len(parts) == 1 else (int(parts[0]), parts[1])
    if "/" not in frac:
        return int(frac) * 8 if len(parts) == 1 else None
    num, den = (int(v) for v in frac.split("/"))
    if den not in (2, 4, 8) or num <= 0 or num >= den:
        return None
    return whole * 8 + num * (8 // den)


def fmt(e: int) -> str:
    """Eighths as a C-09 mixed fraction without the inch mark: 52 -> "6 1/2"."""
    whole, rem = divmod(e, 8)
    if not rem:
        return str(whole)
    g = math.gcd(rem, 8)
    frac = f"{rem // g}/{8 // g}"
    return f"{whole} {frac}" if whole else frac


def fmt_yd(e: int) -> str:
    """A purchase length in eighths of an inch as yards in eighths of a yard (36 e)."""
    return f"{fmt(e // 36)} yd"


def ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def len_pattern(e: int) -> str:
    # A bare "60" must not match the "60" of "60 1/2".
    return rf"(?<![\d/]){re.escape(fmt(e))}(?![\d/])(?! \d+/\d)"


def has_len(text: str, e: int) -> bool:
    return re.search(len_pattern(e), text) is not None


def has_pair(text: str, a: int, b: int) -> bool:
    return re.search(rf"{len_pattern(a)} x {len_pattern(b)}", text) is not None


def sentences(text: str) -> list[str]:
    text = FIG_RE.sub("Fig", text)
    return [s for s in re.split(r"(?<=[.!?]) (?=[A-Z(])", text) if s.strip()]


# ---------------------------------------------------------------- the PDF as data


@dataclass
class Run:
    page: int
    x: float
    y: float
    size: float
    font: str
    text: str
    width: float


@dataclass
class Shape:
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    fill: tuple | None
    curves: int
    image: bool = False

    @property
    def w(self) -> float:
        return self.x1 - self.x0

    @property
    def h(self) -> float:
        return self.y1 - self.y0


@dataclass
class Line:
    page: int
    y: float
    runs: list
    raw: str
    text: str
    section: str = "cover"
    figure: bool = False
    swatch: tuple | None = None


@dataclass
class Page:
    number: int
    width: float
    height: float
    rotate: int
    runs: list = field(default_factory=list)
    shapes: list = field(default_factory=list)
    fonts: dict = field(default_factory=dict)
    lines: list = field(default_factory=list)
    regions: list = field(default_factory=list)


def _apply(m, x, y):
    return m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]


def _matmul(a, b):
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def _string_width(text: str, font: str, font_dict, size: float) -> float:
    try:
        from reportlab.pdfbase import pdfmetrics

        if font in pdfmetrics.standardFonts:
            return pdfmetrics.stringWidth(text, font, size)
    except ImportError:
        pass
    widths = font_dict.get("/Widths") if font_dict else None
    first = int(font_dict.get("/FirstChar", 0)) if font_dict else 0
    if widths:
        total = 0.0
        for ch in text:
            i = ord(ch) - first
            total += float(widths[i]) if 0 <= i < len(widths) else 500.0
        return total * size / 1000.0
    return 0.5 * size * len(text)


class _Painter:
    """Collects text runs and painted shapes from pypdf's visitor callbacks."""

    def __init__(self, page: Page):
        self.page = page
        self.fill = (0.0, 0.0, 0.0)
        self.stack = []
        self.points = []
        self.curves = 0

    def op(self, op, args, cm, tm):
        op = op.decode("latin-1") if isinstance(op, bytes) else op
        nums = [float(a) for a in args if isinstance(a, (int, float))]
        if op == "q":
            self.stack.append(self.fill)
        elif op == "Q" and self.stack:
            self.fill = self.stack.pop()
        elif op in ("rg", "sc", "scn") and len(nums) == 3:
            self.fill = tuple(nums)
        elif op in ("g", "sc", "scn") and len(nums) == 1:
            self.fill = (nums[0],) * 3
        elif op == "k" and len(nums) == 4:
            c, m, y, k = nums
            self.fill = ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
        elif op in ("m", "l") and len(nums) >= 2:
            self.points.append(_apply(cm, nums[0], nums[1]))
        elif op in ("c", "v", "y") and len(nums) >= 4:
            self.curves += 1
            for i in range(0, len(nums) - 1, 2):
                self.points.append(_apply(cm, nums[i], nums[i + 1]))
        elif op == "re" and len(nums) == 4:
            x, y, w, h = nums
            self.points += [_apply(cm, x, y), _apply(cm, x + w, y + h),
                            _apply(cm, x + w, y), _apply(cm, x, y + h)]
        elif op in ("f", "F", "f*", "B", "B*", "b", "b*", "S", "s", "n"):
            if self.points and op != "n":
                xs = [p[0] for p in self.points]
                ys = [p[1] for p in self.points]
                filled = op not in ("S", "s")
                self.page.shapes.append(Shape(self.page.number, min(xs), min(ys), max(xs),
                                              max(ys), self.fill if filled else None,
                                              self.curves))
            self.points, self.curves = [], 0
        elif op == "Do":
            corners = [_apply(cm, x, y) for x, y in ((0, 0), (1, 0), (0, 1), (1, 1))]
            xs = [p[0] for p in corners]
            ys = [p[1] for p in corners]
            self.page.shapes.append(Shape(self.page.number, min(xs), min(ys), max(xs),
                                          max(ys), None, 0, image=True))

    def text(self, text, cm, tm, font_dict, font_size):
        clean = text.replace("\n", "").replace("\r", "")
        if not clean.strip():
            return
        m = _matmul(tm, cm)
        x, y = m[4], m[5]
        scale = math.sqrt(abs(m[0] * m[3] - m[1] * m[2])) or 1.0
        name = str(font_dict.get("/BaseFont", "")).lstrip("/") if font_dict else ""
        name = name.split("+", 1)[-1]
        if font_dict is not None:
            self.page.fonts[name] = "/ToUnicode" in font_dict
        size = font_size * scale
        width = _string_width(clean, name, font_dict, font_size) * scale
        self.page.runs.append(Run(self.page.number, x, y, size, name, clean, width))


def read_pdf(path) -> list[Page]:
    import pypdf  # lazy: tests/ also runs under Pyodide (A11 acceptance criteria)

    reader = pypdf.PdfReader(str(path))
    pages = []
    for number, pdf_page in enumerate(reader.pages, start=1):
        box = pdf_page.mediabox
        page = Page(number, float(box.width), float(box.height),
                    int(pdf_page.get("/Rotate", 0) or 0))
        painter = _Painter(page)
        pdf_page.extract_text(visitor_operand_before=painter.op, visitor_text=painter.text)
        pages.append(page)
    return pages


def _rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _same_color(a, b) -> bool:
    return a is not None and b is not None and all(abs(p - q) <= 0.006 for p, q in zip(a, b))


def _figure_regions(page: Page, palette: list) -> list:
    """Bounding boxes of figures: clusters of palette-filled shapes wider and taller than a
    24 pt swatch, grown by 18 pt so dimension labels just outside the patches count as figure
    labels. A column of swatches stays out, being one swatch wide."""
    patches = [s for s in page.shapes
               if not s.image and any(_same_color(s.fill, c) for c in palette)]
    clusters = []
    for s in patches:
        box = [s.x0, s.y0, s.x1, s.y1]
        merged = True
        while merged:
            merged = False
            for c in clusters:
                if box[0] <= c[2] + 18 and c[0] <= box[2] + 18 and \
                        box[1] <= c[3] + 18 and c[1] <= box[3] + 18:
                    box = [min(box[0], c[0]), min(box[1], c[1]), max(box[2], c[2]),
                           max(box[3], c[3])]
                    clusters.remove(c)
                    merged = True
                    break
        clusters.append(box)
    return [(c[0] - 18, c[1] - 18, c[2] + 18, c[3] + 18) for c in clusters
            if c[2] - c[0] > 24 and c[3] - c[1] > 24]


def _in_region(run: Run, regions) -> bool:
    return any(r[0] <= run.x <= r[2] and r[1] <= run.y <= r[3] for r in regions)


def _build_lines(page: Page) -> None:
    runs = sorted(page.runs, key=lambda r: (-r.y, r.x))
    groups = []
    for run in runs:
        if groups and abs(groups[-1][0].y - run.y) <= max(1.0, 0.25 * run.size):
            groups[-1].append(run)
        else:
            groups.append([run])
    for group in groups:
        group.sort(key=lambda r: r.x)
        raw = group[0].text
        for prev, run in zip(group, group[1:]):
            gap = run.x - (prev.x + prev.width)
            if gap > 0.2 * run.size and not raw.endswith(" ") and not run.text.startswith(" "):
                raw += " "
            raw += run.text
        line = Line(page.number, group[0].y, group, raw, normalize(raw))
        line.figure = all(_in_region(r, page.regions) for r in group)
        first = group[0]
        for s in page.shapes:
            if s.fill is not None and not s.image and s.w <= 24 and s.h <= 24 and \
                    s.x1 <= first.x + 1 and s.x0 >= first.x - 48 and \
                    s.y0 <= first.y + first.size and s.y1 >= first.y - 0.5 * first.size:
                line.swatch = s.fill
        page.lines.append(line)


@dataclass
class Doc:
    pages: list
    lines: list
    name: str
    model: dict

    def section(self, name: str) -> list:
        return [ln for ln in self.lines if ln.section == name]

    def text(self, *names: str) -> str:
        return " ".join(ln.text for ln in self.lines if ln.section in names)

    def body(self, name: str) -> list:
        return [ln for ln in self.section(name) if not _heading(ln.text) and not ln.figure]

    def all_text(self) -> str:
        return " ".join(ln.text for ln in self.lines)


def _heading(text: str) -> str | None:
    for h in HEADINGS:
        if text == h or text == f"{h} (continued)":
            return h
    return None


def build_doc(pages: list, model: dict) -> Doc:
    palette = [_rgb(f["color"]) for f in model["palette"]["fabrics"]]
    lines = []
    for page in pages:
        page.regions = _figure_regions(page, palette)
        _build_lines(page)
        footer_y = max((ln.y for ln in page.lines if FOOTER_RE.search(ln.text)), default=None)
        for ln in page.lines:
            if footer_y is not None and ln.y <= footer_y + 24:
                ln.section = "footer"
        lines += page.lines
    current = "cover"
    for ln in lines:
        if ln.section == "footer":
            continue
        h = _heading(ln.text)
        if h and ln.page > 1:
            current = h
        ln.section = current if ln.page > 1 else "cover"
    cover = [ln for ln in lines if ln.page == 1 and ln.section == "cover"]
    name = max(cover, key=lambda ln: (max(r.size for r in ln.runs), ln.y)).text if cover else ""
    return Doc(pages, lines, name, model)


# ---------------------------------------------------------------- model arithmetic


def _settings(model: dict) -> dict:
    return {**SETTING_DEFAULTS, **(model.get("settings") or {})}


def _finished(model: dict) -> tuple:
    c = model["center"]
    band = 2 * sum(b["width"] for b in model.get("borders", []))
    return c["cols"] * c["cell_size"] + band, c["rows"] * c["cell_size"] + band


def _strip_width(model: dict) -> int:
    return model["binding"].get("strip_width", BINDING_STRIP_DEFAULT)


def binding_strips(model: dict) -> int:
    """MATH.md F6 and F7: T = 2 (W + L) + t; strips = ceil(T / (U - w))."""
    s = _settings(model)
    w, h = _finished(model)
    return ceil_div(2 * (w + h) + s["binding_extra"], s["wof"] - _strip_width(model))


def backing_plan(model: dict) -> dict:
    """MATH.md F8 to F11."""
    s = _settings(model)
    w, h = _finished(model)
    wb, lb = w + s["backing_margin"], h + s["backing_margin"]
    width = s["backing_width"]

    def panels(d):
        return 1 if d <= width else ceil_div(d - BACKING_SEAM_LOSS, width - BACKING_SEAM_LOSS)

    def allowance(n):
        return s["backing_pieced_allowance"] if n >= 2 else s["backing_one_piece_allowance"]

    nv, nh = panels(wb), panels(lb)
    tv, th = nv * lb + allowance(nv), nh * wb + allowance(nh)
    if tv <= th:
        plan = {"panels": nv, "length": lb, "total": tv, "seams": "along"}
    else:
        plan = {"panels": nh, "length": wb, "total": th, "seams": "across"}
    inc = s["purchase_increment"]
    plan["yards"] = ceil_div(plan["total"], inc) * inc
    bw = s["wide_back_width"]
    wide = None
    if plan["panels"] >= 2:
        if wb <= bw and lb <= bw:
            wide = min(wb, lb)
        elif wb <= bw:
            wide = lb
        elif lb <= bw:
            wide = wb
    plan["wide"] = None if wide is None else \
        ceil_div(wide + s["backing_one_piece_allowance"], inc) * inc
    plan["batting"] = (wb, lb)
    return plan


def batting_package(wb: int, lb: int):
    """MATH.md F12: the first package that covers the size in either orientation."""
    for name, pw, ph in BATTING_PACKAGES:
        pw8, ph8 = pw * 8, ph * 8
        if (wb <= pw8 and lb <= ph8) or (wb <= ph8 and lb <= pw8):
            return name, pw, ph
    return None


def border_plan(model: dict) -> list:
    """MATH.md F4, per band, inner to outer."""
    s = _settings(model)
    u = s["wof"]
    c = model["center"]
    wi, li = c["cols"] * c["cell_size"], c["rows"] * c["cell_size"]
    bands = []
    for band in model.get("borders", []):
        b = band["width"]
        side, top = li + 4, wi + 2 * b + 4

        def strips(lp):
            if lp <= u:
                return ceil_div(2, u // lp), 1
            k = ceil_div(lp - BORDER_JOIN_LOSS, u - BORDER_JOIN_LOSS)
            return 2 * k, k

        (ns, ks), (nt, kt) = strips(side), strips(top)
        bands.append({"width": b + 4, "side": side, "top": top, "strips": ns + nt,
                      "k_side": ks, "k_top": kt})
        wi, li = wi + 2 * b, li + 2 * b
    return bands


def block_census(model: dict) -> list | None:
    """Block counts per type in order of first appearance, reading order (PATTERN-SPEC S6);
    a turned block is the same type, a mirror image is not. None without confirmed blocks."""
    cb = model.get("confirmed_blocks")
    if not cb:
        return None
    cells = model["center"]["cells"]
    sa, sd = cb["squares_across"], cb["squares_down"]
    counts = {}
    for br in range(cb["blocks_down"]):
        for bc in range(cb["blocks_across"]):
            block = tuple(tuple(cells[br * sd + r][bc * sa + c] for c in range(sa))
                          for r in range(sd))
            turns = [block, tuple(tuple(row[::-1]) for row in block[::-1])]
            if sa == sd:
                turns += [tuple(zip(*block[::-1])), tuple(zip(*block))[::-1]]
            key = min(turns)
            counts[key] = counts.get(key, 0) + 1
    return list(counts.values())


def fabric_areas(model: dict) -> dict:
    c = model["center"]
    cell = c["cell_size"]
    areas = {f["id"]: 0 for f in model["palette"]["fabrics"]}
    for row in c["cells"]:
        for fid in row:
            areas[fid] += cell * cell
    wi, li = c["cols"] * cell, c["rows"] * cell
    for band in model.get("borders", []):
        b = band["width"]
        areas[band["fabric_id"]] += (wi + 2 * b) * (li + 2 * b) - wi * li
        wi, li = wi + 2 * b, li + 2 * b
    return areas


# ---------------------------------------------------------------- document structure


def steps(lines: list) -> list:
    """Numbered steps as (number, text), each running on until a structural line."""
    out = []
    for ln in lines:
        m = STEP_RE.match(ln.text)
        if m:
            out.append([int(m.group(1)), m.group(2)])
        elif _structural(ln.text):
            if out and out[-1] is not None:
                out.append(None)
        elif out and out[-1] is not None:
            out[-1][1] += " " + ln.text
    return [tuple(s) for s in out if s]


def _structural(text: str) -> bool:
    return bool(_heading(text) or UNIT_HEAD_RE.match(text) or BLOCK_HEAD_RE.match(text)
                or SUBCUT_RE.match(text) or PIECE_RE.match(text) or FIG_RE.match(text)
                or text.startswith("Make ") or CHECKPOINT_RE.search(text)
                or FABRIC_HEAD_RE.match(text))


def subsections(lines: list, head_re) -> list:
    """(heading text, match, lines) for each subheading in a section."""
    out = []
    for ln in lines:
        m = head_re.match(ln.text)
        if m and not ln.figure:
            out.append((ln.text, m, []))
        elif out:
            out[-1][2].append(ln)
    return out


def cutting_blocks(doc: Doc) -> dict:
    """Cutting grouped by fabric letter: {letter: {"name", "steps", "subcuts", ...}}."""
    blocks = {}
    current = None
    for ln in doc.body("Cutting"):
        m = FABRIC_HEAD_RE.match(ln.text)
        if m and ln.swatch is not None:
            current = blocks.setdefault(m.group(1), {"name": m.group(2), "lines": []})
            continue
        if current is not None:
            current["lines"].append(ln)
    for block in blocks.values():
        block["steps"] = steps(block["lines"])
        block["subcuts"] = []
        step_no = last = None
        for ln in block["lines"]:
            sm = STEP_RE.match(ln.text)
            m = SUBCUT_RE.match(ln.text)
            if sm:
                step_no, last = int(sm.group(1)), None
            elif m:
                last = {"label": m.group(1), "strips": int(m.group(2)),
                        "total": int(m.group(3)), "a": eighths(m.group(4)),
                        "b": eighths(m.group(5)) if m.group(5) else None, "shape": m.group(6),
                        "rest": m.group(7), "step": step_no}
                block["subcuts"].append(last)
            elif last is not None and not _structural(ln.text):
                # A subcut that wraps keeps its tail: the unit it feeds, the last strip.
                last["rest"] += " " + ln.text
            else:
                last = None
    return blocks


def subcut_yield(sub: dict) -> int | None:
    m = re.search(r"\b(\d+) per strip\b", sub["rest"])
    return int(m.group(1)) if m else None


def requirement_rows(doc: Doc) -> list:
    rows = []
    for ln in doc.body("Fabric requirements"):
        m = re.match(rf"^({LETTER}) (.+?) ({NUM}) yd\b", ln.text)
        if m:
            rows.append({"letter": m.group(1), "name": m.group(2), "yards": eighths(m.group(3)),
                         "binding": "binding" in ln.text.lower(), "line": ln})
    return rows


def _segment(text: str, start: str, stops: tuple) -> str:
    m = re.search(start, text)
    if not m:
        return ""
    rest = text[m.start():]
    ends = [rest.find(s, 1) for s in stops]
    ends = [e for e in ends if e > 0]
    return rest[:min(ends)] if ends else rest


# ---------------------------------------------------------------- the checks


@dataclass(frozen=True)
class Result:
    check: str
    status: str
    evidence: str

    def line(self) -> str:
        return f"{self.check} {self.status}: {self.evidence}"


CHECKS = {}


def check(check_id: str):
    def register(fn):
        CHECKS[check_id] = fn
        return fn
    return register


def _fail_or_pass(problems: list, ok: str):
    return (False, "; ".join(problems[:4])) if problems else (True, ok)


@check("PS-01")
def ps01(doc: Doc, opts):
    bad = [p.number for p in doc.pages
           if (round(p.width), round(p.height)) != (612, 792) or p.rotate % 360]
    if not doc.pages:
        return False, "the PDF has no pages"
    return _fail_or_pass([f"pages not 612 x 792 portrait: {bad}"] if bad else [],
                         f"1 PDF, {len(doc.pages)} pages, all 612 x 792 pt portrait")


@check("PS-02")
def ps02(doc: Doc, opts):
    problems = []
    order = []
    for ln in doc.lines:
        h = _heading(ln.text)
        if h and ln.page == 1:
            problems.append(f"heading {h!r} on the cover page")
        elif h and (not order or order[-1] != h):
            order.append(h)
    if len(order) != len(set(order)):
        problems.append(f"a heading returns after another section: {order}")
    idx = [HEADINGS.index(h) for h in order]
    if idx != sorted(idx):
        problems.append(f"headings out of order: {order}")
    missing = [h for h in REQUIRED_HEADINGS if h not in order]
    if missing:
        problems.append(f"missing headings {missing}")
    has_borders = bool(doc.model.get("borders"))
    if has_borders != ("Borders" in order):
        problems.append(f"Borders heading {'missing' if has_borders else 'present'} "
                        f"for a model with {len(doc.model.get('borders', []))} bands")
    if not [ln for ln in doc.lines if ln.page == 1 and ln.section == "cover"]:
        problems.append("page 1 has no cover text")
    return _fail_or_pass(problems, f"cover alone on page 1, then {', '.join(order)}")


@check("PS-03")
def ps03(doc: Doc, opts):
    problems = []
    total = len(doc.pages)
    versions = set()
    for page in doc.pages:
        foot = [ln for ln in page.lines if ln.section == "footer"]
        text = " ".join(ln.text for ln in foot)
        marks = FOOTER_RE.findall(text)
        if marks != [(str(page.number), str(total))]:
            problems.append(f"page {page.number}: footer page marks {marks}, "
                            f"expected page {page.number} of {total}")
        if not doc.name or doc.name not in text:
            problems.append(f"page {page.number}: footer lacks the name {doc.name!r}")
        v = VERSION_RE.findall(text)
        if not v:
            problems.append(f"page {page.number}: footer lacks 'QREP x.y.z'")
        versions.update(v)
        page_text = " ".join(ln.text for ln in page.lines)
        for date_re in DATE_RES:
            if date_re.search(page_text):
                problems.append(f"page {page.number} shows a date "
                                f"{date_re.search(page_text).group(0)!r}")
    if len(versions) > 1:
        problems.append(f"footers name different versions {sorted(versions)}")
    return _fail_or_pass(problems, f"{total} footers carry {doc.name!r}, page N of {total} and "
                                   f"QREP {''.join(sorted(versions))}; no date")


def _text_without_name(doc: Doc) -> str:
    text = doc.all_text()
    return text.replace(doc.name, " ") if doc.name else text


@check("PS-05")
def ps05(doc: Doc, opts):
    text = _text_without_name(doc)
    problems = []
    for word in ("historical", "modern", "strip strategy", "difficulty", "minutes",
                 "heuristic"):
        if re.search(rf"\b{word}\b", text, re.IGNORECASE):
            problems.append(f"banned word {word!r}")
    if re.search(r"\b(?:total pieces|pieces total|piece total|piece count|pieces in all)\b|"
                 r"\b(?:has|have|totals?|of) [\d,]+ pieces\b|\b[\d,]+ pieces (?:to cut|in all)\b",
                 text, re.IGNORECASE):
        problems.append("a piece total")
    for pattern, what in ((r"\bf\d+\b", "an internal fabric id"),
                          (r"#[0-9a-fA-F]{6}\b", "a hex color"),
                          (r"\b\d+-\d+/\d+\b", "a hyphenated fraction"),
                          ("[¼-¾⅐-⅞⁄]", "a fraction glyph")):
        m = re.search(pattern, text)
        if m:
            problems.append(f"{what} {m.group(0)!r}")
    m = re.search(r"\b\d+\.\d+\b", VERSION_RE.sub(" ", text))
    if m:
        problems.append(f"a decimal number {m.group(0)!r}")
    step_text = " ".join(t for h in HEADINGS for _, t in steps(doc.body(h)))
    for fabric in doc.model["palette"]["fabrics"]:
        fid = fabric["id"]
        if fid.lower() in STOP_IDS or re.fullmatch(r"[A-Z]", fid):
            continue
        if re.search(rf"(?<![\w/]){re.escape(fid)}(?![\w/])", step_text):
            problems.append(f"model fabric id {fid!r} in a step")
    return _fail_or_pass(problems, "no strategy name, difficulty, minutes, heuristic, piece "
                                   "total, fabric id, hex color, decimal or fraction glyph")


@check("PS-06")
def ps06(doc: Doc, opts):
    text = _text_without_name(doc)
    problems = []
    for m in re.finditer(r"\b(\d+)/(\d+)\b", text):
        num, den = int(m.group(1)), int(m.group(2))
        if den not in (2, 4, 8) or num >= den or math.gcd(num, den) != 1:
            problems.append(f"fraction {m.group(0)!r} is not in lowest eighths")
    for m in re.finditer(r"(\d)( ?)([xX×])( ?)(?=\d|WOF)", text):
        if m.group(2) != " " or m.group(3) != "x" or m.group(4) != " ":
            problems.append(f"dimension separator {m.group(0)!r} is not ' x '")
    cutting = doc.text("Cutting")
    for m in re.finditer(rf"({NUM}) x ({NUM}) rectangles?\b", cutting):
        a, b = eighths(m.group(1)), eighths(m.group(2))
        if a is not None and b is not None and a > b:
            problems.append(f"rectangle {m.group(0)!r} is not short side first")
    return _fail_or_pass(problems, "fractions in eighths, ' x ' separators, rectangles short "
                                   "side first")


@check("PS-07")
def ps07(doc: Doc, opts):
    cover = [ln for ln in doc.lines if ln.page == 1 and ln.section == "cover"]
    text = " ".join(ln.text for ln in cover)
    w, h = _finished(doc.model)
    problems = []
    if not doc.name:
        problems.append("no pattern name on page 1")
    authored = (doc.model.get("provenance") or {}).get("source", "authored") == "authored"
    if authored and normalize(doc.model["metadata"]["name"]) != doc.name:
        problems.append(f"name {doc.name!r} is not the model's {doc.model['metadata']['name']!r}")
    if not has_pair(text, w, h):
        problems.append(f"finished size {fmt(w)} x {fmt(h)} not on page 1")
    if not re.search(r"\bfinished\b", text) or not re.search(
            r"\bblocks?\b[^.]*\bset \d+ x \d+|\bgrid of\b", text):
        problems.append("no build line (blocks and setting, or grid of squares)")
    used = {fid for row in doc.model["center"]["cells"] for fid in row}
    used |= {b["fabric_id"] for b in doc.model.get("borders", [])}
    used.add(doc.model["binding"]["fabric_id"])
    m = re.search(r"\b(\d+) fabrics?\b", text)
    if not m or int(m.group(1)) != len(used):
        problems.append(f"fabric count {m.group(0) if m else 'missing'}, model uses {len(used)}")
    if doc.model.get("size_basis") and not re.search(
            r"estimated from the photo|asked for|requested", text):
        problems.append("no size basis line")
    if not any(not s.image and s.fill is not None for s in doc.pages[0].shapes):
        problems.append("no render on page 1")
    return _fail_or_pass(problems, f"{doc.name!r}, {fmt(w)} x {fmt(h)}, build line, "
                                   f"{len(used)} fabrics, render")


@check("PS-08")
def ps08(doc: Doc, opts):
    deny = [d.strip() for d in opts.get("denylist") or () if d.strip()]
    problems = []
    for entry in deny:
        if entry.lower() in doc.name.lower():
            problems.append(f"the name {doc.name!r} is on the denylist")
    if re.search(r"\bin the style of\b", doc.all_text(), re.IGNORECASE):
        problems.append("a page says 'in the style of'")
    used = f"{len(deny)}-entry denylist" if deny else "no denylist supplied"
    return _fail_or_pass(problems, f"name checked against {used}; no 'in the style of'")


@check("PS-09")
def ps09(doc: Doc, opts):
    basis = doc.model.get("size_basis")
    if not basis:
        return True, "not applicable: the model records no size basis"
    cell = doc.model["center"]["cell_size"]
    found = []
    # Cover lines carry no closing periods, so split each line on its own.
    cover = [s for ln in doc.lines if ln.page == 1 and ln.section == "cover"
             for s in sentences(ln.text)]
    for sentence in cover:
        if basis["source"] == "default":
            if "estimated from the photo" in sentence and has_len(sentence, cell):
                found.append(sentence)
        elif re.search(r"\basked for\b|\brequested\b", sentence) and has_pair(
                sentence, basis["achieved_width"], basis["achieved_height"]) and all(
                has_len(sentence, basis[k]) for k in ("requested_width", "requested_height")
                if basis.get(k)):
            found.append(sentence)
    if not found:
        return False, f"no size basis sentence for a {basis['source']} size on page 1"
    return True, f"{basis['source']} size stated: {found[0][:80]!r}"


@check("PS-10")
def ps10(doc: Doc, opts):
    rows = [r for r in requirement_rows(doc) if not r["binding"]]
    if not rows:
        return False, "no fabric rows in Fabric requirements"
    problems = []
    letters = [r["letter"] for r in rows]
    expected = [c for c in "ABCDEFGHJKLMNPQRSTUVWXYZ"][:len(rows)]
    if letters != expected:
        problems.append(f"letters {letters}, expected {expected}")
    names = [r["name"] for r in rows]
    if len(set(names)) != len(names):
        problems.append(f"names repeat: {names}")
    if any(r["line"].swatch is None for r in rows):
        problems.append("a fabric row has no swatch")
    areas = fabric_areas(doc.model)
    colors = {f["id"]: _rgb(f["color"]) for f in doc.model["palette"]["fabrics"]}
    order = []
    for r in rows:
        match = [fid for fid, c in colors.items() if _same_color(r["line"].swatch, c)]
        if len(match) != 1:
            problems.append(f"row {r['letter']} swatch matches no single model fabric")
        else:
            order.append(areas[match[0]])
    if order and order != sorted(order, reverse=True):
        problems.append(f"letters do not follow area order (areas {order})")
    top = sorted(a for a in areas.values() if a > 0)
    if order and len(order) != len(top):
        problems.append(f"{len(rows)} fabric rows for {len(top)} top fabrics")
    return _fail_or_pass(problems, f"rows {letters} in area order, unique names, swatches")


def _binding_counts(text: str, w: int) -> set:
    found = set()
    for m in re.finditer(rf"\((\d+)\) (?:({NUM}) x WOF )?(?:binding )?strips?\b", text):
        if m.group(2) is None and "binding strip" not in m.group(0):
            continue
        if m.group(2) is not None and eighths(m.group(2)) != w:
            continue
        found.add(int(m.group(1)))
    return found


@check("PS-11")
def ps11(doc: Doc, opts):
    want = binding_strips(doc.model)
    w = _strip_width(doc.model)
    problems = []
    req = [r["line"].text for r in requirement_rows(doc) if r["binding"]]
    for name, text in (("Fabric requirements", " ".join(req)),
                       ("Cutting", " ".join(s for s in sentences(doc.text("Cutting"))
                                            if "binding" in s)),
                       ("Finishing", " ".join(s for s in sentences(doc.text("Finishing"))
                                              if "binding" in s.lower()))):
        found = _binding_counts(text, w)
        if found != {want}:
            problems.append(f"{name} binding strip counts {sorted(found)}, MATH.md F7 "
                            f"gives {want}")
    return _fail_or_pass(problems, f"({want}) binding strips in Fabric requirements, Cutting "
                                   f"and Finishing, equal to MATH.md F7")


@check("PS-12")
def ps12(doc: Doc, opts):
    plan = backing_plan(doc.model)
    s = _settings(doc.model)
    seg = _segment(doc.text("Fabric requirements"), r"\bBacking\b", ("Batting", "Binding"))
    if not seg:
        return False, "no backing row in Fabric requirements"
    problems = []
    y = YARDS_RE.search(seg)
    if not y or eighths(y.group(1)) != plan["yards"] // 36:
        problems.append(f"backing yards {y.group(0) if y else 'missing'}, MATH.md F10 gives "
                        f"{fmt_yd(plan['yards'])}")
    m = re.search(rf"\(?(\d+)\)? lengths? of ({NUM})", seg)
    if not m or (int(m.group(1)), eighths(m.group(2))) != (plan["panels"], plan["length"]):
        problems.append(f"panels {m.group(0) if m else 'missing'}, MATH.md F10 gives "
                        f"{plan['panels']} lengths of {fmt(plan['length'])}")
    if plan["panels"] >= 2 and f"seams run {plan['seams']} the quilt" not in seg:
        problems.append(f"seam direction is not 'seams run {plan['seams']} the quilt'")
    if not has_len(seg, s["backing_width"]):
        problems.append(f"the backing width {fmt(s['backing_width'])} is not stated")
    wide = re.search(rf"or ({NUM}) yd of ({NUM}) wide backing", seg)
    if plan["wide"] is None and wide:
        problems.append(f"wide-back line {wide.group(0)!r} where MATH.md F11 shows none")
    if plan["wide"] is not None and (not wide or eighths(wide.group(1)) != plan["wide"] // 36
                                     or eighths(wide.group(2)) != s["wide_back_width"]):
        problems.append(f"wide-back line {wide.group(0) if wide else 'missing'}, MATH.md F11 "
                        f"gives {fmt_yd(plan['wide'])} of {fmt(s['wide_back_width'])}")
    wide_text = f", or {fmt_yd(plan['wide'])} wide" if plan["wide"] else ", no wide-back line"
    return _fail_or_pass(problems, f"{fmt_yd(plan['yards'])}, {plan['panels']} lengths of "
                                   f"{fmt(plan['length'])}, seams {plan['seams']}{wide_text}")


@check("PS-13")
def ps13(doc: Doc, opts):
    wb, lb = backing_plan(doc.model)["batting"]
    seg = _segment(doc.text("Fabric requirements"), r"\bBatting\b", ("Backing", "Binding",
                                                                       "rounded"))
    if not seg:
        return False, "no batting row in Fabric requirements"
    problems = []
    if not has_pair(seg, wb, lb):
        problems.append(f"batting size {fmt(wb)} x {fmt(lb)} not stated")
    pkg = batting_package(wb, lb)
    if pkg:
        name, pw, ph = pkg
        if not re.search(rf"\b{name}\b", seg, re.IGNORECASE) or not has_pair(seg, pw * 8,
                                                                               ph * 8):
            problems.append(f"package is not {name} {pw} x {ph} (MATH.md F12)")
    elif "larger than a king" not in seg or not has_pair(seg, 124 * 8, 120 * 8):
        problems.append("no 'larger than a king package (124 x 120)' statement")
    label = f"{pkg[0]} {pkg[1]} x {pkg[2]}" if pkg else "larger than a king"
    return _fail_or_pass(problems, f"batting {fmt(wb)} x {fmt(lb)}, {label}")


def _has_triangle_units(doc: Doc) -> bool:
    return any(re.match(rf"^(?:{'|'.join(TRIANGLE_KINDS)}) unit \d+$", ln.text)
               for ln in doc.lines)


@check("PS-14")
def ps14(doc: Doc, opts):
    s = _settings(doc.model)
    text = doc.text("Fabric requirements")
    low = text.lower()
    problems = []
    if "rounded up" not in low or fmt_yd(s["purchase_increment"]) not in text:
        problems.append(f"no rounding statement to {fmt_yd(s['purchase_increment'])}")
    if not re.search(rf"\b{s['top_margin']} percent\b", text):
        problems.append(f"no {s['top_margin']} percent allowance")
    for what, value in (("strip-cutting", s["wof"]), ("backing", s["backing_width"])):
        if not has_len(text, value):
            problems.append(f"the {what} width {fmt(value)} is not stated")
    needs = ["rotary cutter", "mat", "ruler", "thread"]
    if _has_triangle_units(doc):
        needs += ["marking tool", "square ruler"]
    missing = [n for n in needs if n not in low]
    if missing:
        problems.append(f"supplies lack {missing}")
    return _fail_or_pass(problems, f"rounding, {s['top_margin']} percent, widths "
                                   f"{fmt(s['wof'])} and {fmt(s['backing_width'])}, supplies")


def uncertain_count(doc: Doc) -> int | None:
    m = re.search(r"\((\d+)\) squares? (?:were |was )?read with low confidence",
                  doc.text("Before you begin"))
    return int(m.group(1)) if m else None


@check("PS-15")
def ps15(doc: Doc, opts):
    s = _settings(doc.model)
    rules = [t for _, t in steps(doc.body("Before you begin"))]
    if not rules:
        return False, "no numbered rules in Before you begin"
    problems = []

    def rule_with(*words):
        return [r for r in rules if all(w.lower() in r.lower() for w in words)]

    for words in (("1/4", "seam"), ("cut size", "include"), ("unfinished",),
                  ("RST", "right sides together"), ("label",), ("press",),
                  ("arrow",), ("dashed",), ("dotted",)):
        if not rule_with(*words):
            problems.append(f"no rule covers {' and '.join(words)}")
    wof = rule_with("WOF", "width of fabric")
    if not wof or not has_len(wof[0], s["wof"]) or "selvage" in wof[0].lower():
        problems.append(f"the WOF rule must state {fmt(s['wof'])} and make no selvage claim")
    if not [r for r in rule_with("backing") if has_len(r, s["backing_width"])]:
        problems.append(f"no rule states the {fmt(s['backing_width'])} backing width")
    binding = [x for x in sentences(doc.text("Before you begin")) if "binding" in x.lower()]
    if len(binding) != 1:
        problems.append(f"{len(binding)} sentences about binding, expected 1")
    photo = doc.model["center"].get("cell_confidence") is not None or \
        (doc.model.get("provenance") or {}).get("source", "authored") != "authored"
    if photo and uncertain_count(doc) is None:
        problems.append("a photo read without the low-confidence count")
    full = doc.all_text()
    for abbr, expansion in ABBREVIATIONS.items():
        if re.search(rf"\b{abbr}\b", full) and not rule_with(abbr, expansion):
            problems.append(f"{abbr} is used but not defined in Before you begin")
    return _fail_or_pass(problems, f"{len(rules)} rules cover seams, cut sizes, checkpoints, "
                                   f"RST, WOF {fmt(s['wof'])}, backing, pressing, legend, "
                                   f"labels, binding, abbreviations")


@check("PS-16")
def ps16(doc: Doc, opts):
    blocks = cutting_blocks(doc)
    if not blocks:
        return False, "no fabric blocks in Cutting"
    problems = []
    n_steps = n_subs = 0
    for letter, block in blocks.items():
        nums = [n for n, _ in block["steps"]]
        if nums != list(range(1, len(nums) + 1)):
            problems.append(f"fabric {letter} steps numbered {nums}")
        strips_by_step = {}
        for number, text in block["steps"]:
            n_steps += 1
            m = CUT_STEP_RE.match(text)
            if not m:
                problems.append(f"fabric {letter} step {number} does not read 'Cut (N) W x "
                                f"WOF strips'")
                continue
            strips_by_step[number] = int(m.group(1))
        used = {}
        for sub in block["subcuts"]:
            n_subs += 1
            per = subcut_yield(sub)
            strips, total = sub["strips"], sub["total"]
            used[sub["step"]] = used.get(sub["step"], 0) + strips
            if per is None:
                problems.append(f"{sub['label']} gives no per-strip yield")
                continue
            if strips * per < total or (strips - 1) * per >= total:
                problems.append(f"{sub['label']}: {strips} strips x {per} per strip does not "
                                f"fit {total}")
            last = total - (strips - 1) * per
            if last < per:
                said = re.search(r"last strip[^.]*?\(?(\d+)\)?", sub["rest"])
                if not said or int(said.group(1)) != last:
                    problems.append(f"{sub['label']}: the partial last strip ({last}) is not "
                                    f"stated")
        for step, count in used.items():
            if step not in strips_by_step or strips_by_step[step] != count:
                problems.append(f"fabric {letter} step {step}: subcuts use {count} strips, the "
                                f"step cuts {strips_by_step.get(step)}")
    return _fail_or_pass(problems, f"{n_steps} cutting steps and {n_subs} subcuts read 'Cut "
                                   f"(N) W x WOF strips' with consistent yields")


def _set_aside(doc: Doc) -> dict:
    """{label: (strip set number, strips)} from the Cutting set-aside sentences."""
    out = {}
    for block in cutting_blocks(doc).values():
        for _, text in block["steps"]:
            m = SET_ASIDE_RE.search(text)
            c = CUT_STEP_RE.match(text)
            if m:
                out[m.group(1)] = (int(m.group(2)), int(c.group(1)) if c else None)
    return out


@check("PS-17")
def ps17(doc: Doc, opts):
    aside = _set_aside(doc)
    subcut_labels = {s["label"] for b in cutting_blocks(doc).values() for s in b["subcuts"]}
    sets = [(h, ls) for h, m, ls in subsections(doc.body("Making the units"), UNIT_HEAD_RE)
            if h.startswith("Strip set")]
    if not aside and not sets:
        return True, "not applicable: no strip sets"
    problems = []
    both = sorted(set(aside) & subcut_labels)
    if both:
        problems.append(f"labels both subcut and set aside for strip sets: {both}")
    for head, lines in sets:
        labels = set(re.findall(rf"(?<![\w/])({LABEL})(?![\w/])",
                                " ".join(ln.text for ln in lines)))
        cut = sorted(labels & subcut_labels)
        if cut:
            problems.append(f"{head} uses cut pieces {cut}")
        if not labels or not labels <= set(aside):
            problems.append(f"{head} uses strips {sorted(labels)} not set aside in Cutting")
    return _fail_or_pass(problems, f"{len(sets)} strip sets use only set-aside strips "
                                   f"{sorted(aside)}")


def _later_text(doc: Doc) -> str:
    return doc.text("Making the units", "Making the blocks", "Quilt assembly", "Borders",
                    "Finishing")


@check("PS-18")
def ps18(doc: Doc, opts):
    defined = []
    for block in cutting_blocks(doc).values():
        defined += [s["label"] for s in block["subcuts"]]
    defined += list(_set_aside(doc))
    problems = []
    dupes = sorted({x for x in defined if defined.count(x) > 1})
    if dupes:
        problems.append(f"labels defined twice: {dupes}")
    used = set(re.findall(rf"(?<![\w/])({LABEL})(?![\w/])", _later_text(doc)))
    unused = sorted(set(defined) - used)
    undefined = sorted(used - set(defined))
    if unused:
        problems.append(f"defined in Cutting but never used: {unused}")
    if undefined:
        problems.append(f"used but not defined in Cutting: {undefined}")
    return _fail_or_pass(problems, f"{len(set(defined))} labels, each defined once in Cutting "
                                   f"and used later")


def _unit_subsections(doc: Doc) -> list:
    out = []
    for head, m, lines in subsections(doc.body("Making the units"), UNIT_HEAD_RE):
        text = " ".join(ln.text for ln in lines)
        kind = m.group(1) or ("Strip set" if head.startswith("Strip set") else "Unit")
        mirror = MIRROR_RE.search(text)
        out.append({"head": head, "kind": kind, "lines": lines, "text": text,
                    "mirror_of": f"{mirror.group(1) or kind} unit {mirror.group(2)}"
                    if mirror else None})
    return out


def _make(text: str):
    m = MAKE_RE.search(text)
    return (int(m.group(1)), int(m.group(2)) if m.group(2) else None) if m else (None, None)


def _pieces(lines: list) -> dict:
    out = {}
    for ln in lines:
        m = PIECE_RE.match(ln.text)
        if m:
            label = m.group(1) or m.group(4)
            out[label] = out.get(label, 0) + int(m.group(2) or m.group(3))
    return out


@check("PS-19")
def ps19(doc: Doc, opts):
    totals = {}
    for block in cutting_blocks(doc).values():
        for sub in block["subcuts"]:
            spare = re.search(r"\((\d+)\) spare", sub["rest"])
            totals[sub["label"]] = sub["total"] - (int(spare.group(1)) if spare else 0)
    for label, (_, strips) in _set_aside(doc).items():
        totals[label] = strips
    units = _unit_subsections(doc)
    mirrored = {u["mirror_of"] for u in units if u["mirror_of"]}
    need = {}
    problems = []
    groups = units + [{"head": h, "kind": "Block", "lines": ls, "mirror_of": None,
                       "text": " ".join(x.text for x in ls)}
                      for h, m, ls in subsections(doc.body("Making the blocks"), BLOCK_HEAD_RE)]
    for g in groups:
        make, _ = _make(g["text"])
        pieces = _pieces(g["lines"])
        if g["mirror_of"]:
            if pieces:
                problems.append(f"{g['head']} is a mirror unit but lists its own pieces")
            continue
        if make is None:
            if pieces:
                problems.append(f"{g['head']} lists pieces but no make count")
            continue
        # MATH.md F14: two at a time, so ceil(units / 2) pairs; a mirror pair is one unit
        # of each hand per pair, so its pairs equal the make count of either hand.
        sets = make if g["head"] in mirrored else \
            ceil_div(make, 2) if g["kind"] in ("HST", "QST") else make
        for label, q in pieces.items():
            need[label] = need.get(label, 0) + q * sets
    for label in sorted(set(totals) | set(need)):
        if totals.get(label) != need.get(label):
            problems.append(f"{label}: cut {totals.get(label)}, used {need.get(label)}")
    blocks = [_make(g["text"])[0] for g in groups if g["kind"] == "Block"]
    confirmed = doc.model.get("confirmed_blocks")
    if confirmed and blocks and sum(b or 0 for b in blocks) != \
            confirmed["blocks_across"] * confirmed["blocks_down"]:
        problems.append(f"block make counts sum to {sum(b or 0 for b in blocks)}, the model "
                        f"confirms {confirmed['blocks_across'] * confirmed['blocks_down']}")
    return _fail_or_pass(problems, f"{len(totals)} labels: each cut total equals pieces per "
                                   f"unit or block times the make count")


@check("PS-20")
def ps20(doc: Doc, opts):
    s = _settings(doc.model)
    u, inc = s["wof"], s["purchase_increment"]
    if inc % 36:
        return False, f"purchase increment {inc} e is not a whole eighth of a yard"
    rows = requirement_rows(doc)
    blocks = cutting_blocks(doc)
    problems = []
    checked = []
    for letter, block in blocks.items():
        top = binding = 0
        for _, text in block["steps"]:
            m = CUT_STEP_RE.match(text)
            if not m or eighths(m.group(2)) is None:
                continue
            length = int(m.group(1)) * eighths(m.group(2))
            if "for binding" in text:
                binding += length
            else:
                top += length
        for sub in block["subcuts"]:
            step = next((t for n, t in block["steps"] if n == sub["step"]), "")
            m = CUT_STEP_RE.match(step)
            width = eighths(m.group(2)) if m else None
            dims = (sub["a"], sub["a"]) if sub["b"] is None else (sub["a"], sub["b"])
            if width not in dims:
                problems.append(f"{sub['label']}: strip width {width} is not a side of the piece")
                continue
            along = dims[1] if width == dims[0] else dims[0]
            per = subcut_yield(sub)
            if per != u // along or sub["strips"] != ceil_div(sub["total"], max(per or 1, 1)):
                problems.append(f"{sub['label']}: MATH.md F2 gives {u // along} per strip and "
                                f"{ceil_div(sub['total'], u // along)} strips")
            if sub["b"] is not None and along <= u and width <= u:
                # MATH.md F2: keep the orientation with less fabric, a tie to the narrower.
                other = ceil_div(sub["total"], u // width) * along
                mine = ceil_div(sub["total"], u // along) * width
                if other < mine or (other == mine and along < width):
                    problems.append(f"{sub['label']}: a {fmt(along)} strip uses less fabric")
        for kind, length in (("top", top), ("binding", binding)):
            if not length:
                continue
            purchase = ceil_div(length * (100 + s["top_margin"]), 100) if kind == "top" \
                else length
            want = ceil_div(purchase, inc) * inc
            row = [r for r in rows if r["letter"] == letter and r["binding"] == (kind ==
                                                                                "binding")]
            if not row or row[0]["yards"] != want // 36:
                got = fmt(row[0]["yards"]) + " yd" if row and row[0]["yards"] else "no row"
                problems.append(f"fabric {letter} {kind}: {got}, MATH.md "
                                f"{'F5' if kind == 'top' else 'F7'} gives {fmt_yd(want)} from "
                                f"{fmt(length)} of strips")
            else:
                checked.append(f"{letter} {kind} {fmt_yd(want)}")
    for r in rows:
        if r["letter"] not in blocks:
            problems.append(f"row {r['letter']} has no Cutting block")
    return _fail_or_pass(problems, f"purchase lines equal the strip plan: {', '.join(checked)}")


@check("PS-21")
def ps21(doc: Doc, opts):
    offers = re.findall(r"or (\d+) fat quarters?", doc.text("Fabric requirements"))
    if not offers:
        return True, "not applicable: no fat quarter offer"
    cutting = doc.text("Cutting")
    labels = [ln for ln in doc.lines if ln.section == "Cutting" and ln.figure
              and re.search(r"\b18 x 21\b", ln.text)]
    if "fat quarter" not in cutting.lower() or not labels:
        return False, f"{len(offers)} fat quarter offers but no 18 x 21 diagram in Cutting"
    return True, f"{len(offers)} fat quarter offers, {len(labels)} labeled 18 x 21 diagrams"


@check("PS-22")
def ps22(doc: Doc, opts):
    units = _unit_subsections(doc)
    if not units:
        return True, "not applicable: no units"
    problems = []
    for u in units:
        nums = [n for n, _ in steps(u["lines"])]
        if not u["mirror_of"]:
            if not nums or nums != list(range(1, len(nums) + 1)):
                problems.append(f"{u['head']} steps numbered {nums}")
            for n, text in steps(u["lines"]):
                if not FIG_RE.search(text):
                    problems.append(f"{u['head']} step {n} cites no figure")
        if not CHECKPOINT_RE.search(u["text"]):
            problems.append(f"{u['head']} has no checkpoint")
        if _make(u["text"])[0] is None:
            problems.append(f"{u['head']} has no 'Make N.'")
        if "press" not in u["text"].lower() and not u["mirror_of"]:
            problems.append(f"{u['head']} states no pressing")
        if ALTERNATE_RE.search(u["text"]):
            problems.append(f"{u['head']} offers an alternative")
    return _fail_or_pass(problems, f"{len(units)} units: steps from 1 with figures, checkpoint, "
                                   f"make count, pressing, one technique")


def _unit_checkpoint(text: str):
    m = CHECKPOINT_RE.search(text)
    if not m:
        return None
    a = eighths(m.group(1))
    return (m.group(0).startswith("Trim"), a, eighths(m.group(2)) if m.group(2) else a)


@check("PS-23")
def ps23(doc: Doc, opts):
    units = {u["head"]: u for u in _unit_subsections(doc) if u["kind"] in TRIANGLE_KINDS}
    feeds = {}
    for block in cutting_blocks(doc).values():
        for sub in block["subcuts"]:
            m = re.search(rf"\bfor ((?:{'|'.join(TRIANGLE_KINDS)}) unit \d+)", sub["rest"])
            if m:
                feeds.setdefault(m.group(1), []).append(sub)
    if not units and not feeds:
        return True, "not applicable: no triangle or stitch-and-flip units"
    problems = []
    for head, u in units.items():
        if u["mirror_of"]:
            continue
        cp = _unit_checkpoint(u["text"])
        subs = feeds.get(head, [])
        if not subs or cp is None:
            problems.append(f"{head}: {'no cut line names it' if not subs else 'no checkpoint'}")
            continue
        trim, cw, ch = cp
        squares = sorted(s["a"] for s in subs if s["b"] is None)
        rects = [(s["a"], s["b"]) for s in subs if s["b"] is not None]
        # MATH.md F14; PATTERN-SPEC S5: a trimmed unit's checkpoint is F + 1/2.
        f = cw - 4
        if u["kind"] == "HST":
            want = {f + 8} if trim else {f + 7}
        elif u["kind"] == "QST":
            want = {f + 12} if trim else {f + 10}
        elif u["kind"] == "Flying geese":
            hgt = cw - 4
            want = {hgt + 4}
            if ch != 2 * hgt + 4 or rects != [(hgt + 4, 2 * hgt + 4)]:
                problems.append(f"{head}: goose rectangle {rects}, MATH.md F14 gives "
                                f"{fmt(hgt + 4)} x {fmt(2 * hgt + 4)}")
        else:
            want = {cw}
            squares = squares[-1:]
            if len(subs) < 2 or min(s["a"] for s in subs) >= cw:
                problems.append(f"{head}: no corner square smaller than the {fmt(cw)} base")
        if not squares or set(squares) != want:
            problems.append(f"{head}: squares {[fmt(x) for x in squares]}, MATH.md F14 gives "
                            f"{[fmt(x) for x in sorted(want)]}")
    return _fail_or_pass(problems, f"{len(units)} unit types cut to the MATH.md F14 sizes")


@check("PS-24")
def ps24(doc: Doc, opts):
    units = _unit_subsections(doc)
    mirrors = [u for u in units if u["mirror_of"]]
    if not mirrors:
        return True, "not applicable: no mirror-image units"
    by_head = {u["head"]: u for u in units}
    problems = []
    for u in mirrors:
        partner = by_head.get(u["mirror_of"])
        if partner is None:
            problems.append(f"{u['head']} mirrors {u['mirror_of']}, which has no subheading")
            continue
        if not re.search(r"\bnot\b[^.]*\bmix", (u["text"] + " " + partner["text"]),
                         re.IGNORECASE):
            problems.append(f"{u['head']} has no warning not to mix it with {u['mirror_of']}")
        mine, pair = _make(u["text"]), _make(partner["text"])
        if mine[0] is None:
            problems.append(f"{u['head']} has no make count of its own")
        elif u["kind"] == "QST" and mine[0] != pair[0]:
            problems.append(f"{u['head']} makes {mine[0]}, its mirror {pair[0]}: a QST pair "
                            f"gives one of each hand")
        for make, each in (mine, pair):
            if each is not None and make != 2 * each:
                problems.append(f"'Make {make} ({each} of each)' does not add up")
    return _fail_or_pass(problems, f"{len(mirrors)} mirror units named, warned and counted")


def _build_line(doc: Doc):
    cover = " ".join(ln.text for ln in doc.lines if ln.page == 1 and ln.section == "cover")
    m = re.search(rf"\b(\d+) blocks, ({NUM}) finished, set (\d+) x (\d+)", cover)
    return (int(m.group(1)), eighths(m.group(2)), int(m.group(3)), int(m.group(4))) if m \
        else None


@check("PS-25")
def ps25(doc: Doc, opts):
    blocks = subsections(doc.body("Making the blocks"), BLOCK_HEAD_RE)
    if not blocks:
        return True, "not applicable: no blocks"
    build = _build_line(doc)
    problems = []
    if [int(m.group(1)) for _, m, _ in blocks] != list(range(1, len(blocks) + 1)):
        problems.append("blocks are not numbered 1, 2, 3 in order")
    makes = []
    for head, m, lines in blocks:
        text = " ".join(ln.text for ln in lines)
        if not FIG_RE.search(text):
            problems.append(f"{head} cites no figure")
        cp = re.search(rf"{head} should measure ({NUM})(?: x ({NUM}))?(?: square)?", text)
        if not cp:
            problems.append(f"{head} has no 'should measure' checkpoint")
        elif build and eighths(cp.group(1)) != build[1] + 4:
            problems.append(f"{head} measures {cp.group(1)}, the build line's "
                            f"{fmt(build[1])} block plus 1/2 is {fmt(build[1] + 4)}")
        make, _ = _make(text)
        makes.append(make or 0)
        if make is None:
            problems.append(f"{head} has no 'Make N.'")
    if build and sum(makes) != build[0]:
        problems.append(f"make counts sum to {sum(makes)}, the build line says {build[0]} blocks")
    census = block_census(doc.model)
    if census is not None and makes != census:
        problems.append(f"make counts {makes}, the model's blocks in reading order give {census}")
    return _fail_or_pass(problems, f"{len(blocks)} block types with figures, checkpoints and "
                                   f"make counts summing to {sum(makes)}")


@check("PS-26")
def ps26(doc: Doc, opts):
    cell = doc.model["center"]["cell_size"]
    cw, ch = doc.model["center"]["cols"] * cell, doc.model["center"]["rows"] * cell
    problems = []
    n = 0
    for u in _unit_subsections(doc):
        cp = _unit_checkpoint(u["text"])
        if cp is None:
            continue
        n += 1
        for side in cp[1:]:
            if side is None or side <= 4 or (side - 4) % cell:
                problems.append(f"{u['head']}: checkpoint {fmt(side or 0)} is not whole "
                                f"{fmt(cell)} squares plus 1/2")
        order = re.search(rf"\border:? ((?:{LABEL}, )+{LABEL})", u["text"])
        if u["kind"] == "Strip set" and order:
            # A segment is one square wide and as long as its strips, each one square.
            want = sorted((cell + 4, len(order.group(1).split(", ")) * cell + 4))
            if sorted(cp[1:]) != want:
                problems.append(f"{u['head']}: segment {fmt(cp[1])} x {fmt(cp[2])}, its strips "
                                f"give {fmt(want[0])} x {fmt(want[1])}")
    build = _build_line(doc)
    confirmed = doc.model.get("confirmed_blocks")
    for head, m, lines in subsections(doc.body("Making the blocks"), BLOCK_HEAD_RE):
        cp = CHECKPOINT_RE.search(" ".join(ln.text for ln in lines))
        if not cp:
            continue
        n += 1
        sides = (eighths(cp.group(1)), eighths(cp.group(2)) if cp.group(2) else
                 eighths(cp.group(1)))
        want = (confirmed["squares_across"] * cell + 4, confirmed["squares_down"] * cell + 4) \
            if confirmed else ((build[1] + 4,) * 2 if build else None)
        if None in sides or any((s - 4) % cell for s in sides) or \
                (want is not None and sides != want):
            problems.append(f"{head}: checkpoint {cp.group(0)!r}, its squares plus 1/2 give "
                            f"{' x '.join(fmt(w) for w in want) if want else 'whole squares'}")
    m = re.search(rf"quilt center should measure ({NUM}) x ({NUM})", doc.text("Quilt assembly"))
    if not m:
        problems.append("no quilt-center checkpoint")
    elif (eighths(m.group(1)), eighths(m.group(2))) != (cw + 4, ch + 4):
        problems.append(f"quilt center {m.group(1)} x {m.group(2)}, the model gives "
                        f"{fmt(cw + 4)} x {fmt(ch + 4)}")
    return _fail_or_pass(problems, f"{n + 1} checkpoints equal their parts' finished sizes plus "
                                   f"1/2, quilt center {fmt(cw + 4)} x {fmt(ch + 4)}")


@check("PS-27")
def ps27(doc: Doc, opts):
    lines = doc.body("Quilt assembly")
    text = " ".join(ln.text for ln in lines)
    problems = []
    if any(STEP_RE.match(ln.text) for ln in lines):
        problems.append("numbered steps in Quilt assembly")
    prose = [x for x in sentences(text) if len(x.split()) >= 4 and "should measure" not in x]
    if not 2 <= len(prose) <= 3:
        problems.append(f"{len(prose)} sentences, expected 2 or 3")
    low = text.lower()
    if "press" not in low or not re.search(r"\b(?:join|sew)\b", low):
        problems.append("no pressing or joining sentence")
    if "quilt center should measure" not in text:
        problems.append("no quilt-center checkpoint")
    if not FIG_RE.search(text):
        problems.append("no exploded layout figure cited")
    return _fail_or_pass(problems, f"{len(prose)} sentences, checkpoint and one figure, no "
                                   f"numbered steps")


@check("PS-28")
def ps28(doc: Doc, opts):
    bands = border_plan(doc.model)
    if not bands:
        return True, "not applicable: no borders"
    u = _settings(doc.model)["wof"]
    border_steps = [t for b in cutting_blocks(doc).values() for _, t in b["steps"]
                    if "border" in t]
    problems = []
    for i, band in enumerate(bands, start=1):
        match = None
        for text in border_steps:
            side = re.search(rf"side borders?\b[^.]*?(?:join \((\d+)\) strips[^.]*?)?"
                             rf"(?:trim(?: each)? to|cut) ({NUM})", text)
            top = re.search(rf"top and bottom borders?\b[^.]*?(?:join \((\d+)\) strips"
                            rf"[^.]*?)?(?:trim(?: each)? to|cut) ({NUM})", text)
            if side and top and (eighths(side.group(2)), eighths(top.group(2))) == \
                    (band["side"], band["top"]):
                match = (text, side, top)
        if not match:
            problems.append(f"band {i}: no cutting step trims sides to {fmt(band['side'])} and "
                            f"top and bottom to {fmt(band['top'])} (MATH.md F4)")
            continue
        text, side, top = match
        c = CUT_STEP_RE.match(text)
        if not c or (int(c.group(1)), eighths(c.group(2))) != (band["strips"], band["width"]):
            problems.append(f"band {i}: {c.group(0) if c else 'no Cut step'}, MATH.md F4 gives "
                            f"({band['strips']}) {fmt(band['width'])} x WOF strips")
        for what, m, k, length in (("side", side, band["k_side"], band["side"]),
                                   ("top and bottom", top, band["k_top"], band["top"])):
            joined = int(m.group(1)) if m.group(1) else 1
            if length > u and joined != k:
                problems.append(f"band {i}: {what} joins {joined} strips, MATH.md F4 gives {k}")
            if length <= u and m.group(1):
                problems.append(f"band {i}: {what} pieces fit one strip and need no join")
        if re.search(r"\bjoin (?:all|every)\b", text) or ("join" in text and "each" not in text):
            problems.append(f"band {i}: the wording is not per piece")
        if "join" in text and "straight" not in text:
            problems.append(f"band {i}: the join type is not stated as straight seams")
    text = doc.text("Borders")
    low = text.lower()
    side_at, top_at = low.find("side border"), low.find("top and bottom border")
    if side_at < 0 or top_at < 0 or side_at > top_at:
        problems.append("Borders does not sew the sides first, then top and bottom")
    if "toward the border" not in low or "press" not in low:
        problems.append("Borders does not press toward the border")
    if "measure" not in low:
        problems.append("Borders has no measure-and-trim instruction")
    return _fail_or_pass(problems, f"{len(bands)} bands: strips, joins and lengths equal "
                                   f"MATH.md F4, sides first, press toward the border")


@check("PS-29")
def ps29(doc: Doc, opts):
    low = doc.text("Finishing").lower()
    marks = []
    for what, pattern in (("backing", r"\bbacking\b"), ("layering and basting",
                                                         r"\blayer|\bbaste"),
                          ("quilting", r"\bquilt as desired\b|\bquilting\b"),
                          ("binding", r"\bbinding\b")):
        m = re.search(pattern, low)
        marks.append((what, m.start() if m else -1))
    missing = [w for w, at in marks if at < 0]
    if missing:
        return False, f"Finishing lacks {missing}"
    if [at for _, at in marks] != sorted(at for _, at in marks):
        return False, f"Finishing order is {[w for w, _ in sorted(marks, key=lambda x: x[1])]}"
    return True, "Finishing runs backing, layering and basting, quilting, binding"


@check("PS-30")
def ps30(doc: Doc, opts):
    fin = doc.text("Finishing")
    low = fin.lower()
    problems = []
    for what, pattern in (("diagonal joins", r"\bdiagonal\b"), ("fold", r"\bfold|\bin half\b"),
                          ("miter", r"\bmiter"), ("join the ends", r"\bjoin the (?:two )?ends\b"),
                          ("hand finish", r"\bby hand\b")):
        if not re.search(pattern, low):
            problems.append(f"Finishing binding steps lack {what}")
    binding_steps = [t for _, t in steps(doc.body("Finishing")) if "binding" in t.lower()]
    if not any(FIG_RE.search(t) for t in binding_steps):
        problems.append("the binding steps cite no corner figure")
    for section in ("Making the units", "Making the blocks", "Quilt assembly", "Borders",
                    "Layout chart", "Coloring page", "Cutting"):
        if re.search(r"\bmiter", doc.text(section), re.IGNORECASE):
            problems.append(f"binding procedure also in {section}")
    byb = [x for x in sentences(doc.text("Before you begin")) if "binding" in x.lower()]
    if len(byb) != 1:
        problems.append(f"Before you begin has {len(byb)} sentences about binding")
    return _fail_or_pass(problems, "binding procedure only in Finishing, with a figure; one "
                                   "binding sentence in Before you begin")


def _dots(doc: Doc, pages: set) -> int:
    return sum(1 for p in doc.pages if p.number in pages for s in p.shapes
               if s.fill is not None and s.curves >= 4 and s.w <= 8 and s.h <= 8)


@check("PS-31")
def ps31(doc: Doc, opts):
    # The chart's numbers and letters sit inside the chart figure, so read the whole section.
    if not [ln for ln in doc.section("Layout chart") if not _heading(ln.text)]:
        return False, "no Layout chart content"
    rows, cols = doc.model["center"]["rows"], doc.model["center"]["cols"]
    text = " ".join(ln.text for ln in doc.section("Layout chart"))
    tokens = text.split()
    numbers = {int(t) for t in tokens if t.isdigit()}
    problems = []
    if not set(range(1, max(rows, cols) + 1)) <= numbers:
        problems.append(f"row and column numbers 1 to {rows} and 1 to {cols} are not all "
                        f"printed")
    letters = sum(1 for t in tokens if re.fullmatch(LETTER, t))
    if letters < rows * cols:
        problems.append(f"{letters} cell letters for {rows * cols} cells")
    parts = re.findall(r"Rows (\d+) to (\d+), columns (\d+) to (\d+)", text)
    if parts:
        spans = [tuple(int(v) for v in p) for p in parts]
        for a, b in zip(spans, spans[1:]):
            if not ((b[0] == a[1] and b[2:] == a[2:]) or (b[2] == a[3] and b[:2] == a[:2])):
                problems.append(f"parts {a} and {b} do not share one row or column")
        if min(s[0] for s in spans) != 1 or max(s[1] for s in spans) != rows or \
                min(s[2] for s in spans) != 1 or max(s[3] for s in spans) != cols:
            problems.append("the labeled parts do not cover the grid")
    pages = {ln.page for ln in doc.section("Layout chart")}
    if len(pages) > 1 and not parts:
        problems.append(f"the chart spans pages {sorted(pages)} without range labels")
    dots = _dots(doc, pages)
    said = uncertain_count(doc) or 0
    if dots != said:
        problems.append(f"{dots} dotted cells, Before you begin counts {said}")
    return _fail_or_pass(problems, f"{rows} x {cols} chart with numbers and letters, "
                                   f"{dots} dots matching the count of {said}")


@check("PS-33")
def ps33(doc: Doc, opts):
    u = _settings(doc.model)["wof"]
    problems = []
    first = next((s for s in ("Making the units", "Making the blocks", "Quilt assembly")
                  if doc.body(s)), None)
    if first is None:
        return False, "no construction section"
    opening = doc.body(first)[0].text
    if STEP_RE.match(opening) or _structural(opening) or len(opening.split()) < 6:
        problems.append(f"{first} does not open with the reason sentence")
    construction = doc.text("Making the units", "Making the blocks", "Quilt assembly")
    if ALTERNATE_RE.search(construction):
        problems.append(f"an alternative is offered: {ALTERNATE_RE.search(construction)[0]!r}")
    seqs = []
    for unit in _unit_subsections(doc):
        if unit["kind"] != "Strip set":
            continue
        order = re.search(rf"\border:? ((?:{LABEL}, )+{LABEL})", unit["text"])
        # A signature is the fabric sequence; two sets differ in labels even when they match.
        seq = tuple(x[0] for x in order.group(1).split(", ")) if order else ()
        if not 2 <= len(seq) <= 7:
            problems.append(f"{unit['head']} has {len(seq)} strips in its sewing order")
        if len(set(seq)) < 2:
            problems.append(f"{unit['head']} is a single-fabric strip set")
        if seq in seqs or seq[::-1] in seqs:
            problems.append(f"{unit['head']} repeats another set or its reverse")
        seqs.append(seq)
        cross = re.search(rf"crosscut \((\d+)\) ({NUM}) segments?, (\d+) per set", unit["text"],
                          re.IGNORECASE)
        sets, _ = _make(unit["text"])
        if not cross or sets is None:
            problems.append(f"{unit['head']} gives no crosscut count and make count")
            continue
        need, seg, per = int(cross.group(1)), eighths(cross.group(2)), int(cross.group(3))
        if need < 2:
            problems.append(f"{unit['head']} makes {need} segment: its signature does not "
                            f"repeat")
        if per != u // seg or sets != ceil_div(need, per):
            problems.append(f"{unit['head']}: MATH.md F3 gives {u // seg} per set and "
                            f"{ceil_div(need, u // seg)} sets")
    for block in cutting_blocks(doc).values():
        for sub in block["subcuts"]:
            if max(sub["a"], sub["b"] or 0) > u:
                problems.append(f"{sub['label']} is cut longer than the {fmt(u)} strip width")
    return _fail_or_pass(problems, f"one method, reason sentence first, {len(seqs)} strip sets "
                                   f"with distinct multi-fabric signatures")


@check("PS-38")
def ps38(doc: Doc, opts):
    problems = []
    if len(doc.pages) < 2:
        return False, "no page 2"
    squares = [s for s in doc.pages[1].shapes if abs(s.w - 72) <= 0.5 and abs(s.h - 72) <= 0.5]
    if not squares:
        problems.append("page 2 has no 72 x 72 pt test square")
    else:
        sq = squares[0]
        near = [ln for ln in doc.pages[1].lines if re.search(r"\b100 percent\b", ln.text)
                and sq.y0 - 36 <= ln.y <= sq.y1 + 36]
        if not near:
            problems.append("no print-at-100-percent note beside the test square")
    for page in doc.pages:
        for r in page.runs:
            if r.x < 36 - 0.5 or r.x + r.width > page.width - 36 + 0.5:
                problems.append(f"page {page.number}: text {r.text[:20]!r} inside the 36 pt "
                                f"margin")
                break
        for s in page.shapes:
            if s.x0 < 36 - 1 or s.x1 > page.width - 36 + 1:
                problems.append(f"page {page.number}: a drawing inside the 36 pt margin")
                break
    return _fail_or_pass(problems, "72 x 72 pt test square with its note on page 2; side "
                                   "margins at least 36 pt")


def _words(text: str) -> list:
    return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())


def _reference_text(folder: Path) -> str:
    chunks = []
    for path in sorted(folder.rglob("*")):
        if path.suffix.lower() in (".txt", ".md"):
            chunks.append(path.read_text(encoding="utf-8", errors="ignore"))
        elif path.suffix.lower() == ".json":
            def strings(v):
                if isinstance(v, str):
                    chunks.append(v)
                elif isinstance(v, dict):
                    for x in v.values():
                        strings(x)
                elif isinstance(v, list):
                    for x in v:
                        strings(x)
            try:
                strings(json.loads(path.read_text(encoding="utf-8", errors="ignore")))
            except ValueError:
                pass
    return "\n".join(chunks)


@check("PS-39")
def ps39(doc: Doc, opts):
    folder = opts.get("references")
    if not folder:
        return None, "no local reference directory given (never run in CI)"
    folder = Path(folder)
    if not folder.is_dir():
        return False, f"reference directory {folder} does not exist"
    mine = _words(doc.all_text())
    theirs = _words(_reference_text(folder))
    grams = {tuple(theirs[i:i + 10]) for i in range(len(theirs) - 9)}
    hits = sum(1 for i in range(len(mine) - 9) if tuple(mine[i:i + 10]) in grams)
    names = [n.strip() for n in opts.get("reference_names") or () if n.strip()]
    named = sum(1 for n in names if n.lower() in doc.all_text().lower())
    # Counts only: the matched words are reference text and stay off every report.
    if hits or named:
        return False, f"{hits} runs of 10 words match the references; {named} reference names " \
                      f"appear"
    return True, f"0 runs of 10 words shared with {len(theirs)} reference words; " \
                 f"{len(names)} names absent"


@check("PS-41")
def ps41(doc: Doc, opts):
    problems = []
    for page in doc.pages:
        if not [ln for ln in page.lines if ln.section != "footer"]:
            problems.append(f"page {page.number} has no extractable text")
        for font, unicode_map in page.fonts.items():
            if not unicode_map and font not in _standard_fonts():
                problems.append(f"page {page.number}: font {font} has no ToUnicode map")
    return _fail_or_pass(sorted(set(problems)), f"text extracts on all {len(doc.pages)} pages")


def _standard_fonts() -> set:
    return {"Courier", "Courier-Bold", "Courier-Oblique", "Courier-BoldOblique", "Helvetica",
            "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique", "Times-Roman",
            "Times-Bold", "Times-Italic", "Times-BoldItalic", "Symbol", "ZapfDingbats"}


@check("PS-42")
def ps42(doc: Doc, opts):
    worst = {"figure label": (99.0, None), "table": (99.0, None), "body": (99.0, None)}
    problems = []
    for page in doc.pages:
        for ln in page.lines:
            cells = len(ln.runs) >= 2 and any(
                b.x - (a.x + a.width) >= 12 for a, b in zip(ln.runs, ln.runs[1:]))
            for r in ln.runs:
                kind = "figure label" if _in_region(r, page.regions) else \
                    "table" if cells else "body"
                minimum = {"figure label": 7, "table": 9, "body": 10}[kind]
                if r.size < minimum - 0.05:
                    problems.append(f"page {page.number}: {kind} {r.text[:20]!r} at "
                                    f"{r.size:.1f} pt, minimum {minimum}")
                if r.size < worst[kind][0]:
                    worst[kind] = (r.size, r.text)
    sizes = ", ".join(f"{k} {v[0]:.1f}" for k, v in worst.items() if v[1] is not None)
    return _fail_or_pass(problems, f"smallest sizes in pt: {sizes}")


@check("PS-43")
def ps43(doc: Doc, opts):
    figure = [ln for ln in doc.lines if ln.figure]
    text = " ".join(ln.text for ln in doc.lines if not ln.figure and ln.section != "footer")
    numbers = []
    for ln in figure:
        numbers += [m.group(0) for m in re.finditer(rf"{NUM} x {NUM}|\d+ \d+/\d+|\d+/\d+",
                                                    ln.text)]
        numbers += [m.group(1) for m in re.finditer(r'(\d+(?: \d+/\d+)?)"', ln.raw)]
    if not numbers:
        return True, "not applicable: no measurements in figure labels"
    missing = sorted({n for n in numbers
                      if not re.search(rf"(?<![\d/]){re.escape(n)}(?![\d/])(?! \d+/\d)", text)})
    if missing:
        return False, f"figure numbers not in the text: {missing[:6]}"
    return True, f"{len(numbers)} figure measurements all appear in the text"


# ---------------------------------------------------------------- entry points


def run_checks(pdf_path, model, *, references=None, denylist=(), reference_names=(),
               only=None) -> list:
    """Every implemented check on one PDF; `model` is a path or the parsed JSON dict."""
    if not isinstance(model, dict):
        model = json.loads(Path(model).read_text(encoding="utf-8"))
    doc = build_doc(read_pdf(pdf_path), model)
    opts = {"references": references, "denylist": list(denylist),
            "reference_names": list(reference_names)}
    results = []
    for check_id, fn in CHECKS.items():
        if only and check_id not in only:
            continue
        ok, evidence = fn(doc, opts)
        status = "not run" if ok is None else "pass" if ok else "fail"
        results.append(Result(check_id, status, evidence))
    return results


def placeholder_frames(pdf_path, model) -> list:
    """Pages that carry a figure placeholder frame (A4a draws one for a missing figure)."""
    if not isinstance(model, dict):
        model = json.loads(Path(model).read_text(encoding="utf-8"))
    doc = build_doc(read_pdf(pdf_path), model)
    return [ln.page for ln in doc.lines if re.search(r"\bplaceholder\b", ln.text, re.I)]


def _lines_of(path) -> list:
    return Path(path).read_text(encoding="utf-8").splitlines() if path else []


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf")
    parser.add_argument("model")
    parser.add_argument("--references", help="local folder of private reference extractions")
    parser.add_argument("--reference-names", help="file of reference titles and designer names")
    parser.add_argument("--denylist", help="file of names the pattern name must avoid")
    args = parser.parse_args(argv)
    results = run_checks(args.pdf, args.model, references=args.references,
                         denylist=_lines_of(args.denylist),
                         reference_names=_lines_of(args.reference_names))
    for result in results:
        print(result.line())
    frames = placeholder_frames(args.pdf, args.model)
    print(f"placeholder frames: {len(frames)}" + (f" on pages {sorted(set(frames))}"
                                                  if frames else ""))
    return 1 if any(r.status == "fail" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
