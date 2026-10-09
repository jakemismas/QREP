"""Report generator for the D2 calculator conformance baseline (plan ticket D2, MATH.md 5.2).

    .venv/Scripts/python scripts/eval/calculators/baseline.py --start-sha 3fa671e --work <dir>
        --out-json <path> --out-md <path> (--raw <raw.json> | --drive --shots <dir>)
        [--finished-size <calculator>] ...

It builds the job list for drive.mjs (one job per calculator, matrix row and variant), or reads a
saved raw record file, parses every record with calc_parse, computes QREP's own values at the
start SHA, places the MATH.md vectors beside them, labels every difference with the MATH.md
causes shown to account for it (_status), and writes the JSON record and the Markdown report.

Expected values come from calc_vectors (MATH.md hand arithmetic). A calculator's number never
changes a vector or a parameter set: a difference that only the page's own rule reproduces, or
that nothing accounts for, is listed for the A1 and A2 owners.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from fractions import Fraction as F
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DRIVER = HERE / "drive.mjs"
SEARCHES = HERE / "searches.json"

# The sibling modules are plain scripts, not a package.
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import calc_parse  # noqa: E402
import calc_rules  # noqa: E402
import calc_vectors as cv  # noqa: E402

LINE_TYPES = ("backing", "binding", "batting", "borders")
LIST_DATE = "2026-10-07"  # MATH.md 5.2: all five listed calculators were opened on this date
TEXT_CAP = 4000  # displayed text kept per key; a page-wide capture (Omni) would swamp the JSON
# The Stitch Desk's "Buy off the roll" is its package answer when no precut fits, so it is
# recorded and compared as a value; None would read as a missing model.
SD_OFF_THE_ROLL = "off the roll"

# Which size the three single-band border calculators receive: "center" (the quilt before the
# border) or "finished". Not settled yet, so it is a setting; --finished-size flips one per run.
# The driver's page notes (drive.mjs at b75184f) found all three take the center size.
BORDER_SIZE_BASIS = {"dtq_border": "center", "sewbecca_border": "center", "qc_border": "center"}

# V-YIELD spot checks for the Quilter's Paradise piece count page, transcribed from MATH.md 4.2.
# One full-width strip as the large piece, so the page's count is the vector's per-strip yield.
# (row_id, variant, label, piece_w, piece_l, large_w, large_l, expected pieces, citation)
YIELD_ROWS = [
    (
        "V-YIELD-01", "40",
        "squares cut 2 1/2 in from one 40 x 2 1/2 in strip",
        F("2.5"), F("2.5"), F(40), F("2.5"), 16,
        "MATH.md line 574: per = floor(40 / 2.5) = 16 (320 // 20)",
    ),
    (
        "V-YIELD-02", "40",
        "rectangles cut 2 1/2 x 4 1/2 in from one 40 x 4 1/2 in strip",
        F("2.5"), F("4.5"), F(40), F("4.5"), 16,
        "MATH.md line 589: 4 1/2 in strips, per = floor(40 / 2.5) = 16",
    ),
    (
        "V-YIELD-02", "42",
        "rectangles cut 2 1/2 x 4 1/2 in from one 42 x 4 1/2 in strip",
        F("2.5"), F("4.5"), F(42), F("4.5"), 16,
        "MATH.md line 583: 4 1/2 in strips, per = floor(42 / 2.5) = 16 (336 // 20)",
    ),
]  # fmt: skip


# ---------------------------------------------------------------------------------------------
# Number formatting
# ---------------------------------------------------------------------------------------------


def dec(x: F | int) -> str:
    """A form value as a plain decimal string ("92.5", "3.75"); eighths always terminate."""
    x = F(x)
    if x.denominator == 1:
        return str(x.numerator)
    text = format(Decimal(x.numerator) / Decimal(x.denominator), "f")
    if F(text) != x:
        raise ValueError(f"{x} has no short decimal form")
    return text


def mixed(x: F | int | None) -> str:
    """8 3/8, 3/4, 4; None prints as a dash."""
    if x is None:
        return "-"
    x = F(x)
    sign = "-" if x < 0 else ""
    whole, rest = divmod(abs(x), 1)
    whole = int(whole)
    if rest == 0:
        return f"{sign}{whole}"
    d = rest.denominator
    while d % 2 == 0 or d % 3 == 0:
        d //= 2 if d % 2 == 0 else 3
    if d != 1:
        # A page that prints decimals (Omni's 3.78 yd) reads better as the decimal it showed.
        try:
            return sign + dec(abs(x))
        except ValueError:
            pass
    frac = f"{rest.numerator}/{rest.denominator}"
    return f"{sign}{whole} {frac}" if whole else f"{sign}{frac}"


def num(x):
    """JSON form of a parsed or computed number: Fractions and ints as strings ("67/8")."""
    if isinstance(x, bool) or x is None:
        return x
    if isinstance(x, (int, F)):
        return str(x)
    if isinstance(x, dict):
        return {k: num(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [num(v) for v in x]
    return x


def jsonable(x):
    """Fractions as strings everywhere, ints left alone (counts stay numbers)."""
    if isinstance(x, F):
        return str(x)
    if isinstance(x, dict):
        return {str(k): jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [jsonable(v) for v in x]
    if isinstance(x, Path):
        return str(x)
    return x


# Third-party text reaches the Markdown only through this table; anything left over fails the
# report, because the evidence file is ASCII by rule.
_ASCII_MAP = {
    chr(cp): plain
    for cp, plain in (
        (0x00A0, ' '), (0x2002, ' '), (0x2003, ' '), (0x2009, ' '), (0x202F, ' '), (0x2010, '-'),
        (0x2011, '-'), (0x2012, '-'), (0x2013, '-'), (0x2014, '-'), (0x2015, '-'), (0x2212, '-'),
        (0x2018, "'"), (0x2019, "'"), (0x201C, '"'), (0x201D, '"'), (0x2032, "'"), (0x2033, '"'),
        (0x2026, '...'), (0x00D7, 'x'), (0x2192, '->'), (0x2190, '<-'), (0x2022, '*'), (0x00B7, '*'),
        (0x2726, '*'), (0x00BD, ' 1/2'), (0x00BC, ' 1/4'), (0x00BE, ' 3/4'), (0x2153, ' 1/3'),
        (0x2154, ' 2/3'), (0x215B, ' 1/8'), (0x215C, ' 3/8'), (0x215D, ' 5/8'), (0x215E, ' 7/8'),
        (0x00B0, ' deg'), (0x2713, 'ok'), (0x2715, 'x'), (0x00AE, '(R)'), (0x2122, '(TM)'),
        (0x00A9, '(C)'),
    )
}  # fmt: skip


def ascii_text(text: str) -> str:
    out = "".join(_ASCII_MAP.get(ch, ch) for ch in str(text))
    return re.sub(r"(?<=\d)  (?=\d/\d)", " ", out)


def md_cell(text) -> str:
    return ascii_text(text).replace("|", "/").replace("\n", " ")


# ---------------------------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Job:
    calculator: str
    row_id: str
    base: str
    variant: str
    inputs: dict
    line_types: tuple[str, ...]
    width: F
    length: F
    fabric: F | None = None
    bands: tuple[F, ...] = ()
    applicable: bool = True
    band_count: int | None = None

    def as_driver_job(self) -> dict:
        job = {"calculator": self.calculator, "row_id": self.row_id, "inputs": self.inputs}
        if self.band_count is not None:
            job["bands"] = self.band_count
        return job


def _matrix_jobs(key: str, variants, make_inputs) -> list[Job]:
    jobs = []
    for rid, _label, w, ln in cv.MATRIX:
        for variant, fabric, lts in variants:
            jobs.append(
                Job(key, f"{rid}@{variant}", rid, variant, make_inputs(w, ln, fabric), lts, w,
                    ln, fabric)
            )  # fmt: skip
    return jobs


def _border_jobs(key: str, make_inputs, max_bands: int, bases) -> list[Job]:
    jobs = []
    for rid, _label, cw, cl, bands in cv.BORDER_ROWS:
        if len(bands) > max_bands:
            # Empty inputs keep the driver from typing a row the page cannot hold.
            jobs.append(
                Job(key, f"{rid}@40", rid, "40", {}, ("borders",), cw, cl, F(40), bands,
                    applicable=False, band_count=len(bands))
            )  # fmt: skip
            continue
        for basis in bases:
            grow = 2 * sum(bands) if basis == "finished" else 0
            variant = "40-finished" if basis == "finished" else "40"
            w, ln = cw + grow, cl + grow
            jobs.append(
                Job(key, f"{rid}@{variant}", rid, variant, make_inputs(w, ln, bands), ("borders",),
                    w, ln, F(40), bands, band_count=len(bands) if max_bands > 1 else None)
            )  # fmt: skip
    return jobs


def _jobs_qp_backing(_basis) -> list[Job]:
    return _matrix_jobs(
        "qp_backing",
        [("42", F(42), ("backing",)), ("40", F(40), ("backing",)),
         ("batting120", F(120), ("batting",))],
        lambda w, ln, fw: {"Fabric_Width": dec(fw), "Width": dec(w), "Length": dec(ln),
                           "Overage": "4"},
    )  # fmt: skip


def _jobs_qp_binding(_basis) -> list[Job]:
    return _matrix_jobs(
        "qp_binding",
        [("40", F(40), ("binding",))],
        lambda w, ln, fw: {"Fabric_Width": dec(fw), "Width": dec(w), "Length": dec(ln),
                           "Strip_Width": "2 1/2"},
    )  # fmt: skip


def _jobs_qp_border(_basis) -> list[Job]:
    def inputs(w, ln, bands):
        out = {"Fabric_Width": "40", "Width": dec(w), "Length": dec(ln)}
        out.update({f"Border{i}Width": dec(b) for i, b in enumerate(bands, 1)})
        return out

    return _border_jobs("qp_border", inputs, 5, ["center"])


def _jobs_mfqs(_basis) -> list[Job]:
    return _matrix_jobs(
        "mfqs_backing",
        [("42", F(42), ("backing", "batting"))],
        lambda w, ln, fw: {"length": dec(ln), "width": dec(w), "overage": "4",
                           "fabric_width": dec(fw)},
    )  # fmt: skip


def _jobs_nqc(_basis) -> list[Job]:
    return _matrix_jobs(
        "nqc",
        [("40", F(40), ("backing", "binding")), ("108", F(108), ("backing",)),
         ("118", F(118), ("backing",))],
        lambda w, ln, fw: {"width": dec(w), "length": dec(ln), "fabricWidth": dec(fw)},
    )  # fmt: skip


def _jobs_stitchdesk_backing(_basis) -> list[Job]:
    return _matrix_jobs(
        "stitchdesk_backing",
        [("42", F(42), ("backing", "batting"))],
        lambda w, ln, fw: {"w": dec(w), "l": dec(ln), "oh": "4", "bo": "4", "fw": dec(fw),
                           "sa": "1/2"},
    )  # fmt: skip


def _jobs_stitchdesk_binding(_basis) -> list[Job]:
    return _matrix_jobs(
        "stitchdesk_binding",
        [("42", F(42), ("binding",))],
        lambda w, ln, fw: {"bqW": dec(w), "bqL": dec(ln), "bsw": "2.5", "bfw": dec(fw)},
    )


def _jobs_quiltkeeper(_basis) -> list[Job]:
    return _matrix_jobs(
        "quiltkeeper_binding",
        [("40", F(40), ("binding",))],
        lambda w, ln, fw: {"quilt-width": dec(w), "quilt-height": dec(ln), "strip-width": "2.5",
                           "fabric-width": dec(fw), "overage": "10"},
    )  # fmt: skip


def _jobs_omni(_basis) -> list[Job]:
    # The page adds 4 in per side itself, so its own overage field stays 0.
    jobs = []
    for mode, variant, lts in (("backing", "42", ("backing",)),
                               ("batting", "42-batting", ("batting",))):  # fmt: skip
        jobs += _matrix_jobs(
            "omni_backing",
            [(variant, F(42), lts)],
            lambda w, ln, fw, m=mode: {"mode": m, "width": dec(w), "length": dec(ln),
                                       "fabric_width": dec(fw), "overage": "0"},
        )  # fmt: skip
    return jobs


def _jobs_dtq(basis) -> list[Job]:
    return _border_jobs(
        "dtq_border",
        lambda w, ln, bands: {"number-1": dec(w), "number-2": dec(ln), "number-4": "40",
                              "number-5": dec(bands[0])},
        1, basis,
    )  # fmt: skip


def _jobs_sewbecca(basis) -> list[Job]:
    return _border_jobs(
        "sewbecca_border",
        lambda w, ln, bands: {"quiltWidth": dec(w), "quiltLength": dec(ln),
                              "borderWidth": dec(bands[0]), "fabricWidth": "40"},
        1, basis,
    )  # fmt: skip


def _jobs_qc(basis) -> list[Job]:
    def inputs(w, ln, bands):
        out = {"width": dec(w), "length": dec(ln), "fabric_width": "40"}
        out.update({f"border{i}_width": dec(b) for i, b in enumerate(bands, 1)})
        return out

    return _border_jobs("qc_border", inputs, 3, basis)


def _jobs_piece_count(_basis) -> list[Job]:
    return [
        Job("qp_piece_count", f"{rid}@{variant}", rid, variant,
            {"piece_width": dec(pw), "piece_length": dec(pl), "large_piece_width": dec(lw),
             "large_piece_length": dec(ll)},
            ("yield",), lw, ll, lw)
        for rid, variant, _label, pw, pl, lw, ll, _n, _cite in YIELD_ROWS
    ]  # fmt: skip


# ---------------------------------------------------------------------------------------------
# Extractors: parser output to canonical values per line type
# ---------------------------------------------------------------------------------------------
# Canonical shapes (all lengths in inches, yards in yards, Fractions):
#   backing: {"fabric": F, "layouts": {"vertical"|"horizontal": {"yards", "panels"}},
#             "chosen": "vertical"|"horizontal"|None, "wide": {"width", "yards"}|None}
#   wide:    {"fabric": F, "layouts": {...}}            (Nebraska at 108 and 118 in)
#   binding: {"strips", "yards", "binding_length"}
#   batting: {"width", "length", "package"} or, for a roll, {"roll_width", "roll_yards",
#             "roll_length", "panels", "other"}
#   borders: {"bands": [{"strips", "yards", "strip_width"}]}
#   yield:   {"pieces"}


def _html(rec: dict) -> dict:
    html = rec.get("html") or {}
    if not isinstance(html, dict):
        raise ValueError("record html is not an element map")
    return {k: (v or "") for k, v in html.items()}


def _extract_qp_backing(parser, job: Job, rec: dict) -> dict:
    html = _html(rec)
    layouts = {}
    for element, layout in (("yardage1", "vertical"), ("yardage2", "horizontal")):
        if element not in html:
            raise ValueError(f"missing element {element!r}")
        got = parser(html[element])
        typed = (job.width, job.length) if layout == "vertical" else (job.length, job.width)
        if (got["width"], got["length"]) != typed:
            raise ValueError(
                f"{element} reports width {got['width']} and length {got['length']}, typed "
                f"{typed[0]} and {typed[1]}"
            )
        layouts[layout] = {"yards": got["yards"], "panels": got["seams"] + 1,
                           "inches": got["inches"]}  # fmt: skip
    if job.variant.startswith("batting"):
        v = layouts["vertical"]
        return {
            "batting": {
                "roll_width": job.fabric,
                "roll_yards": v["yards"],
                "roll_length": v["inches"],
                "panels": v["panels"],
                "other": layouts["horizontal"],
            }
        }
    return {"backing": {"fabric": job.fabric, "layouts": layouts, "chosen": None, "wide": None}}


def _extract_qp_binding(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    return {"binding": {"strips": got["strips"], "yards": got["yards"],
                        "binding_length": got["binding_length"]}}  # fmt: skip


def _extract_qp_border(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec), len(job.bands))
    return {
        "borders": {
            "bands": [
                {"strips": b["strips"], "yards": b["yards"], "strip_width": b["strip_width"]}
                for b in got["bands"]
            ],
            "overall": [got["overall_width"], got["overall_length"]],
        }
    }


def _extract_nqc(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    layouts = {
        lay: {"yards": got[lay]["yards"], "panels": got[lay]["panels"],
              "coverage": got[lay]["coverage"]}
        for lay in ("vertical", "horizontal")
    }  # fmt: skip
    if job.variant == "40":
        return {
            "backing": {"fabric": job.fabric, "layouts": layouts, "chosen": None, "wide": None},
            "binding": {
                "strips": got["binding"]["strips"],
                "yards": got["binding"]["yards"],
                "strips_length": got["binding"]["total_length"],
            },
        }
    return {"wide": {"fabric": job.fabric, "layouts": layouts}}


def _seam_layout(seams: str | None) -> str | None:
    # "horizontal seams" stack the panels: MATH.md's horizontal layout; likewise vertical.
    return seams if seams in ("vertical", "horizontal") else None


def _one_panel_layout(cut_length, job: Job) -> str | None:
    if cut_length is None:
        return None
    if cut_length == job.length + 8:
        return "vertical"
    if cut_length == job.width + 8:
        return "horizontal"
    return None


def _extract_mfqs(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    b = got["backing"]
    lay = _seam_layout(b["seams"]) or "one piece"
    out = {
        "backing": {
            "fabric": b["fabric_width"],
            "layouts": {lay: {"yards": b["yards"], "panels": b["panels"]}},
            "chosen": lay,
            "wide": None,
        },
        "batting": {
            "width": got["batting"]["width"],
            "length": got["batting"]["length"],
            "package": got["batting"]["package"],
        },
    }
    if got.get("wide"):
        out["backing"]["wide"] = {"width": got["wide"]["fabric_width"],
                                  "yards": got["wide"]["yards"],
                                  "panels": got["wide"]["panels"]}  # fmt: skip
    return out


def _extract_stitchdesk_backing(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    b = got["backing"]
    lay = _seam_layout(b["seams"])
    if lay is None and b["panels"] == 1:
        lay = _one_panel_layout(b["cut_length"], job)
    lay = lay or "one piece"
    out = {
        "backing": {
            "fabric": b["fabric_width"],
            "layouts": {lay: {"yards": b["yards"], "panels": b["panels"]}},
            "chosen": lay,
            "wide": None,
        },
        "batting": {
            "width": got["batting"]["width"],
            "length": got["batting"]["length"],
            "package": got["batting"]["precut"] or SD_OFF_THE_ROLL,
        },
    }
    if got.get("wide"):
        out["backing"]["wide"] = {"width": got["wide"]["fabric_width"],
                                  "yards": got["wide"]["yards"], "panels": None}  # fmt: skip
    return out


def _extract_stitchdesk_binding(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    if got["type"] != "straight":
        raise ValueError(f"expected a straight-grain result, got {got['type']!r}")
    return {"binding": {"strips": got["strips"], "yards": got["yards"],
                        "binding_length": got["perimeter"] + got["extra"]}}  # fmt: skip


def _extract_quiltkeeper(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    return {"binding": {"strips": got["strips"], "yards": got["yards"],
                        "binding_length": got["binding_length"]}}  # fmt: skip


def _extract_sewbecca(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    return {"borders": {"bands": [{"strips": got["strips"], "yards": got["yards"],
                                   "strip_width": None}]}}  # fmt: skip


def _extract_qc(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    shown = got["borders"]
    if len(shown) < len(job.bands):
        raise ValueError(f"{len(shown)} border(s) shown for {len(job.bands)} typed")
    for typed, b in zip(job.bands, shown, strict=False):
        if b["width"] != typed:
            raise ValueError(f"border {b['index']} shows {b['width']} in wide, typed {typed}")
    out = {"borders": {"bands": [{"strips": None, "yards": b["yards"], "strip_width": None}
                                 for b in shown[: len(job.bands)]]}}  # fmt: skip
    if len(shown) > len(job.bands):
        # The page keeps a default second border; it is computed after band 1 and is ignored.
        out["borders"]["extra_bands_shown"] = [
            {"width": b["width"], "yards": b["yards"]} for b in shown[len(job.bands):]
        ]
    return out


def _omni_layout(got: dict, job: Job) -> str:
    if got["pieces"] == 1:
        return "one piece"
    if got["piece_length"] == job.width + 8:
        return "horizontal"
    # A width split prints each piece's run along the quilt length as its width (W).
    if got["piece_width"] == job.length + 8:
        return "vertical"
    return "unstated"


def _omni_size(pieces, piece_width, piece_length, layout) -> tuple | None:
    # Pieces sit side by side, so their short sides add up across the seams. A length split
    # prints the short side as W, a width split as L (calc_rules.omni_backing).
    if pieces is None:
        return None
    if layout == "one piece":
        return (piece_width, piece_length)
    if layout == "horizontal":
        return (piece_length, pieces * piece_width)
    if layout == "vertical":
        return (pieces * piece_length, piece_width)
    return None


def _extract_omni(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    if got["too_many_pieces"]:
        raise ValueError("the page says the quilt needs more than 5 pieces")
    lay = _omni_layout(got, job)
    if job.variant.endswith("batting"):
        size = _omni_size(got["pieces"], got["piece_width"], got["piece_length"], lay)
        if size is None:
            raise ValueError("the page's piece sizes match neither a length nor a width split")
        # The page names no batting package, so none is recorded or compared.
        return {"batting": {"width": size[0], "length": size[1], "yards": got["yards"],
                            "pieces": got["pieces"]}}  # fmt: skip
    return {"backing": {"fabric": job.fabric,
                        "layouts": {lay: {"yards": got["yards"], "panels": got["pieces"]}},
                        "chosen": lay, "wide": None}}  # fmt: skip


def _extract_dtq(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    s = got["straight"]
    return {"borders": {"bands": [{"strips": s["strips"], "yards": s["yards"],
                                   "strip_width": got["cut_width"]}],
                        "mitered": got["mitered"]}}  # fmt: skip


def _extract_piece_count(parser, job: Job, rec: dict) -> dict:
    got = parser(_html(rec))
    return {"yield": {"pieces": got["as_typed"]["pieces"], "turned": got["turned"]["pieces"]}}


def _pick(data, *paths):
    for path in paths:
        cur = data
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                cur = None
                break
        if cur is not None:
            return cur
    return None


def _as_number(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, F)):
        return value
    if isinstance(value, float):
        return F(value).limit_denominator(1000)
    if isinstance(value, str):
        try:
            return F(value.strip())
        except (ValueError, ZeroDivisionError):
            return None
    return None


def _layout_word(value) -> str | None:
    text = str(value or "").lower()
    if "horizontal" in text:
        return "horizontal"
    if "vertical" in text:
        return "vertical"
    return None


def _generic_extract(parsed: dict, job: Job, line_types: tuple[str, ...]) -> dict:
    """Parsers written after this file read the newer pages; their key names are guessed here
    and a value that is not found stays absent rather than being invented."""
    if not isinstance(parsed, dict):
        raise ValueError(f"parser returned {type(parsed).__name__}, expected a dict")
    out = {}
    if "backing" in line_types:
        layouts = {}
        for lay in ("vertical", "horizontal"):
            sub = _pick(parsed, f"backing.layouts.{lay}", f"layouts.{lay}", f"backing.{lay}", lay)
            if isinstance(sub, dict) and _as_number(sub.get("yards")) is not None:
                layouts[lay] = {"yards": _as_number(sub.get("yards")),
                                "panels": _as_number(sub.get("panels"))}  # fmt: skip
        yards = _as_number(_pick(parsed, "backing.yards", "yards"))
        chosen = _layout_word(
            _pick(parsed, "backing.layout", "backing.orientation", "backing.seam",
                  "backing.seams", "backing.direction", "layout", "orientation", "seam",
                  "seam_direction", "direction")
        )  # fmt: skip
        if yards is not None and not layouts:
            panels = _as_number(_pick(parsed, "backing.panels", "panels"))
            layouts[chosen or "unstated"] = {"yards": yards, "panels": panels}
        wide_yards = _as_number(
            _pick(parsed, "wide.yards", "wide_back.yards", "wide108.yards", "backing_108.yards",
                  "wide_yards")
        )  # fmt: skip
        wide = None
        if wide_yards is not None:
            width = _as_number(_pick(parsed, "wide.width", "wide_back.width")) or F(108)
            wide = {"width": width, "yards": wide_yards}
        if layouts or wide:
            out["backing"] = {"fabric": job.fabric, "layouts": layouts, "chosen": chosen,
                              "wide": wide}  # fmt: skip
    if "batting" in line_types:
        bat = {
            "width": _as_number(_pick(parsed, "batting.width", "batting_width")),
            "length": _as_number(
                _pick(parsed, "batting.length", "batting.height", "batting_length")
            ),
            "package": _pick(parsed, "batting.package", "batting.precut", "package", "precut"),
        }
        if any(v is not None for v in bat.values()):
            if bat["package"] is not None:
                bat["package"] = str(bat["package"])
            out["batting"] = bat
    if "binding" in line_types:
        bind = {
            "strips": _as_number(_pick(parsed, "binding.strips", "strips")),
            "yards": _as_number(_pick(parsed, "binding.yards", "yards")),
            "binding_length": _as_number(
                _pick(parsed, "binding.binding_length", "binding_length", "length")
            ),
        }
        if bind["strips"] is not None or bind["yards"] is not None:
            out["binding"] = bind
    if "borders" in line_types:
        bands = _pick(parsed, "borders.bands", "bands")
        if not isinstance(bands, list):
            one = {"strips": _as_number(parsed.get("strips")),
                   "yards": _as_number(parsed.get("yards"))}  # fmt: skip
            bands = [one] if any(v is not None for v in one.values()) else []
        clean = [
            {"strips": _as_number(b.get("strips")), "yards": _as_number(b.get("yards")),
             "strip_width": _as_number(b.get("strip_width"))}
            for b in bands
            if isinstance(b, dict)
        ]  # fmt: skip
        if clean:
            out["borders"] = {"bands": clean}
    if "yield" in line_types:
        pieces = _as_number(_pick(parsed, "pieces", "count", "best.pieces"))
        if pieces is None:
            options = _pick(parsed, "results", "orientations")
            if isinstance(options, list):
                counts = [_as_number(_pick(o, "pieces", "count")) for o in options]
                counts = [c for c in counts if c is not None]
                pieces = max(counts) if counts else None
        if pieces is not None:
            out["yield"] = {"pieces": pieces}
    return out


def _generic(parser, job: Job, rec: dict, line_types: tuple[str, ...]) -> dict:
    html = _html(rec)
    params = [
        p
        for p in inspect.signature(parser).parameters.values()
        if p.default is inspect.Parameter.empty
        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    parsed = parser(html, len(job.bands)) if len(params) >= 2 else parser(html)
    return _generic_extract(parsed, job, line_types)


# ---------------------------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Model:
    """A calculator modeled by its own page-script function in calc_rules rather than by a
    MATH.md parameter set. proxy is a MATH.md parameter set that matches the page on most rows;
    it names causes only on a row where it gives the model's value. causes, per quantity kind,
    are the page rule's differences from MATH.md, used when the proxy does not fit. params are
    the page's own values for parameters those causes name (the proxy's when None), so a cause
    the page shares with the reference set is dropped (page_causes)."""

    fn: str
    proxy: dict | None = None
    causes: dict = field(default_factory=dict)
    params: dict | None = None


@dataclass(frozen=True)
class Calc:
    key: str
    vendor: str
    page: str
    url: str
    line_types: tuple[str, ...]
    on_list: bool
    parser: str
    jobs: Callable
    extract: Callable | None = None
    rules: dict = field(default_factory=dict)  # line type -> parameter set name in calc_rules
    rule_source: str = ""
    record_only: bool = False
    fixed: str = ""  # settings the driver sets that the jobs do not type
    lead: str | None = None
    models: dict = field(default_factory=dict)  # line type -> Model


QP = "https://www.quiltersparadiseesc.com/Calculators/"

_SD_BACKING_RULE = "page rule: usable = fabric width - 2 in selvage, panels = ceil(D / (usable - 1))"
_SD_BINDING_RULE = (
    "page rule: 4 x strip width + 10 in extra, 1/2 in more per join, usable = fabric width - 2"
)
_SB_STRIP_RULE = (
    "page rule: strips = ceil(2 L / fw + 2 (W + b) / fw), no seam allowance and no join loss"
)
_SB_YARD_RULE = "page rule: yards = strips x b / fw (fabric width, not 36), up to 1/8 yd"
_QC_RULE = "page rule: strips = ceil((2 W + 2 L + 4 b + 12) / (fw - 1/2)), (b + 1/2) wide"
_OMNI_RULE = (
    "page rule: pieces = the fewest of 2 to 5 that fit the bolt, no seam loss, yards up to 0.01"
)
_DTQ_RULE = "page rule: strips = ceil((T / fw + T) / fw), T = 2 (W + 2 b + 1) + 2 (L + 1)"

REGISTRY: dict[str, Calc] = {
    c.key: c
    for c in [
        Calc(
            "qp_backing", "Quilter's Paradise", "Backing and Batting",
            QP + "Backing%20and%20Batting%20Calculator.php", ("backing", "batting"), True,
            "parse_qp_backing", _jobs_qp_backing, _extract_qp_backing,
            {"backing": "qp", "batting": "qp"},
            "MATH.md 5.2 and the page script: 1 in per seam, no allowance, 1/8 yd with 1/3 steps",
            fixed="batting rows: bolt 120 in, one width for every matrix size",
        ),
        Calc(
            "qp_binding", "Quilter's Paradise", "Binding", QP + "Binding%20Calculator.php",
            ("binding",), True, "parse_qp_binding", _jobs_qp_binding, _extract_qp_binding,
            {"binding": "qp"}, "MATH.md 5.2: same strip formula as F7, its own yard rounding",
        ),
        Calc(
            "qp_border", "Quilter's Paradise", "Border", QP + "Border%20Calculator.php",
            ("borders",), True, "parse_qp_border", _jobs_qp_border, _extract_qp_border,
            {"borders": "qp"}, "MATH.md 5.2: pools all strips, adds 1/2 in to border widths",
            fixed="non-mitred corners, end-to-end joins (driver default)",
        ),
        Calc(
            "mfqs_backing", "My Favorite Quilt Store", "Backing and Batting",
            "https://myfavoritequiltstore.com/toolbox/backing-calculator", ("backing", "batting"),
            True, "parse_mfqs_backing", _jobs_mfqs, _extract_mfqs, {},
            "calc_rules.mfqs_backing, from the page script (MATH.md 5.2: record only)",
            record_only=True, fixed="batting type Cotton (driver default)",
            models={"backing": Model("mfqs_backing"), "batting": Model("mfqs_backing"),
                    "wide": Model("mfqs_backing")},
        ),
        Calc(
            "nqc", "Nebraska Quilt Company", "Backing and Binding",
            "https://www.nebraskaquiltcompany.com/pages/backing-binding-calculator",
            ("backing", "binding"), True, "parse_nqc", _jobs_nqc, _extract_nqc,
            {"backing": "nqc", "binding": "nqc", "wide": "nqc"},
            "backing: MATH.md 5.2 (+8 in, 1/2 in per seam, 1/4 yd, no allowance); binding: the "
            "page script (+12 in, strips over the full 40 in), not stated in MATH.md 5.2",
        ),
        Calc(
            "stitchdesk_backing", "The Stitch Desk", "Backing Calculator",
            "https://thestitchdesk.com/calculators/backing-calculator", ("backing", "batting"),
            False, "parse_stitchdesk_backing", _jobs_stitchdesk_backing,
            _extract_stitchdesk_backing, {}, "calc_rules.stitchdesk_backing, from the page script",
            fixed="price left empty",
            models={
                "backing": Model(
                    "stitchdesk_backing",
                    {"B": 40, "overhang_per_side": 4, "s": 1, "allowance_pieced": 0,
                     "allowance_one": 0, "increment": "eighth", "keep": "least_total"},
                    {"yards": ("fabric width", "allowance", "rounding increment or thirds",
                               _SD_BACKING_RULE),
                     "panels": ("fabric width", "seam loss", _SD_BACKING_RULE)},
                ),
                "wide": Model(
                    "stitchdesk_backing",
                    {"B": 106, "overhang_per_side": 4, "s": 1, "allowance_pieced": 0,
                     "allowance_one": 0, "increment": "eighth", "keep": "least_total"},
                    {"yards": ("fabric width", "allowance", "rounding increment or thirds",
                               _SD_BACKING_RULE)},
                ),
                "batting": Model(
                    "stitchdesk_backing",
                    causes={"size": ("page rule: batting overhang per side",),
                            "package": ("page rule: its own precut table, Craft to King",)},
                ),
            },
        ),
        Calc(
            "stitchdesk_binding", "The Stitch Desk", "Binding Calculator",
            "https://thestitchdesk.com/calculators/binding-calculator", ("binding",), False,
            "parse_stitchdesk_binding", _jobs_stitchdesk_binding, _extract_stitchdesk_binding,
            {}, "calc_rules.stitchdesk_binding, from the page script",
            fixed="straight grain (driver default), price left empty",
            models={
                "binding": Model(
                    "stitchdesk_binding",
                    {"U": 40, "w": F(5, 2), "extra": 20, "join_aware": True,
                     "increment": "eighth"},
                    {"strips": ("binding extra length", "join loss", _SD_BINDING_RULE),
                     "yards": ("binding extra length", "join loss",
                               "rounding increment or thirds", _SD_BINDING_RULE)},
                ),
            },
        ),
        Calc(
            "quiltkeeper_binding", "QuiltKeeper Studio", "Binding",
            "https://quiltkeeperstudio.com/calculators/binding", ("binding",), False,
            "parse_quiltkeeper_binding", _jobs_quiltkeeper, _extract_quiltkeeper,
            {"binding": "quiltkeeper"}, "calc_rules.BINDING_SETS['quiltkeeper'], from the page "
            "script: strips over the full fabric width, 1/8 yd",
        ),
        Calc(
            "omni_backing", "Omni Calculator", "Quilt Calculator",
            "https://www.omnicalculator.com/everyday-life/quilt", ("backing", "batting"), False,
            "parse_omni_backing", _jobs_omni, _extract_omni, {},
            "calc_rules.omni_backing, from the page script",
            fixed="non-directional fabric, additional overage 0 (the page adds 4 in per side); "
                  "batting size = its displayed pieces side by side (pieces x piece size)",
            models={
                "backing": Model("omni_backing", None, {
                    "yards": ("seam loss", "allowance", "rounding increment or thirds",
                              _OMNI_RULE),
                    "panels": ("seam loss", _OMNI_RULE)},
                    params={"s": 0, "allowance_pieced": 0, "allowance_one": 0}),
                "batting": Model("omni_backing", None, {
                    "size": ("page rule: in batting mode a piece is (piece length + 8) / k wide",),
                    "size vertical": ("rounding increment or thirds",
                                      "page rule: piece sizes round up to 0.1 in")}),
            },
        ),
        Calc(
            "dtq_border", "Designed to Quilt", "Quilt Border Calculator",
            "https://designedtoquilt.com/quilt-border-calculator/", ("borders",), False,
            "parse_dtq_border", _jobs_dtq, _extract_dtq, {},
            "calc_rules.dtq_border, from the page's form formulas",
            fixed="center size; fabric width 40; straight joins compared, mitered recorded",
            models={"borders": Model("dtq_border", None,
                                     {"strips": ("pooled border strips", _DTQ_RULE),
                                      "yards": ("pooled border strips",
                                                "rounding increment or thirds", _DTQ_RULE)})},
        ),
        Calc(
            "sewbecca_border", "Sew Becca", "Border Calculator", "https://sewbecca.com/border-calc",
            ("borders",), False, "parse_sewbecca_border", _jobs_sewbecca, _extract_sewbecca, {},
            "calc_rules.sewbecca_border, from the page script", fixed="center size",
            models={"borders": Model("sewbecca_border", None,
                                     {"strips": ("pooled border strips", _SB_STRIP_RULE),
                                      "yards": (_SB_YARD_RULE,)})},
        ),
        Calc(
            "qc_border", "Quilt Calculator", "Border Calculator",
            "https://quiltcalculator.com/border-calculator", ("borders",), False,
            "parse_qc_border", _jobs_qc, _extract_qc, {},
            "calc_rules.qc_border, from the page script",
            fixed="center size; URL found from the site's home page link at run time; up to 3 bands",
            models={"borders": Model("qc_border", None,
                                     {"strips": ("pooled border strips", _QC_RULE),
                                      "yards": ("pooled border strips",
                                                "rounding increment or thirds", _QC_RULE)})},
        ),
        Calc(
            "qp_piece_count", "Quilter's Paradise", "Piece Count",
            QP + "Piece%20Count%20Calculator.php", ("yield",), True, "parse_qp_piece_count",
            _jobs_piece_count, _extract_piece_count, {},
            "calc_rules.qp_piece_count, from the page script",
            fixed="spot check of V-YIELD-01 and V-YIELD-02 (MATH.md 5.2 note); the typed "
                  "orientation is compared, the turned one recorded",
            models={"yield": Model("qp_piece_count", None, {
                "pieces": ("page rule: floor(LW / w) x floor(LL / l) on the typed orientation",)})},
        ),
    ]
}  # fmt: skip

_SETS = {"backing": "BACKING_SETS", "binding": "BINDING_SETS", "borders": "BORDER_SETS",
         "batting": "BACKING_SETS", "wide": "BACKING_SETS"}  # fmt: skip


def rule_set(line_type: str, name: str | None):
    if not name:
        return None
    sets = getattr(calc_rules, _SETS.get(line_type, ""), None)
    if sets is None or name not in sets:
        return None
    return dict(sets[name])


def parser_for(calc: Calc):
    """The parse function, or None while it is missing or still a NotImplementedError stub."""
    fn = getattr(calc_parse, calc.parser, None)
    if fn is None:
        return None
    try:
        src = inspect.getsource(fn)
    except (OSError, TypeError):
        return fn
    body = src.split(":", 1)[-1]
    if "raise NotImplementedError" in body and body.count("\n") < 12:
        return None
    return fn


def all_jobs(basis: dict, both_bases: bool = False) -> list[Job]:
    jobs = []
    for calc in REGISTRY.values():
        if calc.key in BORDER_SIZE_BASIS:
            bases = ["center", "finished"] if both_bases else [basis[calc.key]]
            jobs.extend(calc.jobs(bases))
        else:
            jobs.extend(calc.jobs(None))
    return jobs


def driver_calculators() -> tuple[set[str] | None, set[str]]:
    """Calculator and probe keys that drive.mjs defines; (None, set()) if its layout moved."""
    try:
        text = DRIVER.read_text(encoding="utf-8")
        start = text.index("const CALCULATORS = {")
        end = text.index("\n};", start)
        calcs = set(re.findall(r"^  ([A-Za-z_]\w*): \{", text[start:end], re.M))
        probes_m = re.search(r"const PROBES = \{([^}]*)\}", text)
        probes = set(re.findall(r"(\w+):", probes_m.group(1))) if probes_m else set()
        return calcs, probes
    except (OSError, ValueError):
        return None, set()


# ---------------------------------------------------------------------------------------------
# QREP at the start SHA
# ---------------------------------------------------------------------------------------------

QREP_MODES = (("default", None), ("wof320", 320))


def _e(n: int) -> F:
    return F(n, 8)


def qrep_view(raw: dict) -> dict:
    """calc_qrep's eighths as inches and yards."""
    return {
        "wof": _e(raw["wof"]),
        "finished": [_e(raw["finished_width"]), _e(raw["finished_height"])],
        "backing": {
            "yards": F(raw["backing"]["quarter_yards"], 4),
            "panels": raw["backing"]["panels"],
            "layout": raw["backing"]["layout"],
            "length_needed": _e(raw["backing"]["length_needed"]),
        },
        "binding": {
            "strips": raw["binding"]["strips"],
            "yards": F(raw["binding"]["quarter_yards"], 4),
            "length_needed": _e(raw["binding"]["length_needed"]),
        },
        "batting": {"width": _e(raw["batting"]["width"]), "length": _e(raw["batting"]["height"])},
        "wide_back": raw["wide_back"],
        "borders": [
            {
                "yards": F(b["quarter_yards"], 4),
                "pieces": b["pieces"],
                "length_needed": _e(b["length_needed"]),
                "cut_lengths": [_e(c) for c in b["cut_lengths"]],
            }
            for b in raw["borders"]
        ],
    }


def qrep_tables(calc_qrep) -> tuple[dict, dict]:
    to_e = calc_rules.to_eighths
    matrix = {
        rid: {
            mode: qrep_view(calc_qrep.qrep_values(to_e(w), to_e(ln), [], wof))
            for mode, wof in QREP_MODES
        }
        for rid, _label, w, ln in cv.MATRIX
    }
    borders = {
        rid: {
            mode: qrep_view(
                calc_qrep.qrep_values(to_e(cw), to_e(cl), [to_e(b) for b in bands], wof)
            )
            for mode, wof in QREP_MODES
        }
        for rid, _label, cw, cl, bands in cv.BORDER_ROWS
    }
    return matrix, borders


# ---------------------------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------------------------

STATUS_RANK = {"ok": 0, "no value": 1, "parse error": 2, "parser missing": 3, "failed": 4,
               "not applicable": 5, "unmatched": 6}  # fmt: skip
FAILED = ("failed", "parse error")


@dataclass
class Rec:
    raw: dict
    job: Job | None
    matched_by: str
    source: str = ""
    shots: Path | None = None
    status: str = "ok"
    detail: str | None = None
    values: dict = field(default_factory=dict)
    displayed: dict = field(default_factory=dict)
    failure_id: str | None = None


def _same_input(a, b) -> bool:
    if a == b:
        return True
    try:
        # Some pages pad what they hold ("67.500"), so values compare as numbers.
        return F(str(a).strip()) == F(str(b).strip())
    except (ValueError, ZeroDivisionError):
        return False


def match_job(raw: dict, universe: list[Job], by_id: dict) -> tuple[Job | None, str]:
    """Exact row id first; else the one planned job whose inputs agree with the record's
    (earlier runs used other row ids); else, for an untyped row, the one job on that base row."""
    key, rid = raw.get("calculator"), raw.get("row_id")
    job = by_id.get((key, rid))
    if job is not None:
        return job, "row_id"
    inputs = raw.get("inputs") or {}
    if inputs:
        how = "inputs"
        cands = [
            j
            for j in universe
            if j.calculator == key
            and j.applicable
            and set(inputs) <= set(j.inputs)
            and all(_same_input(v, j.inputs[k]) for k, v in inputs.items())
        ]
    else:
        how = "base row id"
        cands = [j for j in universe if j.calculator == key and j.base == rid]
    if len(cands) == 1:
        return cands[0], how
    return None, "unmatched"


def displayed_text(raw: dict) -> dict:
    out = {}
    for key, value in (raw.get("html") or {}).items():
        text = calc_parse.html_text(value or "")
        if len(text) > TEXT_CAP:
            text = f"{text[:TEXT_CAP]} [truncated from {len(text)} characters]"
        out[key] = text
    return out


def process(raw: dict, job: Job | None, how: str) -> Rec:
    rec = Rec(raw, job, how, displayed=displayed_text(raw))
    if job is None:
        rec.status, rec.detail = "unmatched", "no planned job has this row id or these inputs"
        return rec
    calc = REGISTRY[job.calculator]
    if raw.get("skipped"):
        rec.status, rec.detail = "not applicable", str(raw["skipped"])
        return rec
    if raw.get("error"):
        rec.status, rec.detail = "failed", str(raw["error"])
        return rec
    parser = parser_for(calc)
    if parser is None:
        rec.status = "parser missing"
        rec.detail = f"calc_parse.{calc.parser} is missing or still a stub"
        return rec
    try:
        if calc.extract is not None:
            rec.values = calc.extract(parser, job, raw)
        else:
            rec.values = _generic(parser, job, raw, job.line_types)
    except NotImplementedError as exc:
        rec.status, rec.detail = "parser missing", f"NotImplementedError: {exc}"
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        rec.status, rec.detail = "parse error", f"{type(exc).__name__}: {exc}"
    else:
        if not rec.values:
            rec.status, rec.detail = "no value", "the parser returned nothing this report compares"
    return rec


def pick_records(recs: list[Rec]) -> dict[tuple[str, str], Rec]:
    """One record per job: the best status, then the latest timestamp."""
    best: dict[tuple[str, str], Rec] = {}
    for rec in recs:
        if rec.job is None:
            continue
        key = (rec.job.calculator, rec.job.row_id)
        cur = best.get(key)
        if cur is None:
            best[key] = rec
            continue
        mine = (STATUS_RANK[rec.status], rec.raw.get("timestamp") or "")
        theirs = (STATUS_RANK[cur.status], cur.raw.get("timestamp") or "")
        if mine[0] < theirs[0] or (mine[0] == theirs[0] and mine[1] > theirs[1]):
            best[key] = rec
    return best


# ---------------------------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------------------------

CAUSES = {
    "B": "fabric width",
    "U": "fabric width",
    "BW": "fabric width",
    "overhang_per_side": "overhang",
    "s": "seam loss",
    "allowance_pieced": "allowance",
    "allowance_one": "allowance",
    "allowance": "allowance",
    "margin_percent": "allowance",
    "increment": "rounding increment or thirds",
    "keep": "orientation",
    "w": "strip width",
    "extra": "binding extra length",
    "join_aware": "join loss",
    "j": "join loss",
    "rule": "pooled border strips",
}
TODAY_DEFECTS = {"keep": "D-01", "s": "D-02", "join_aware": "D-08"}


def cause(param: str, today: bool) -> str:
    name = CAUSES.get(param, param)
    if today and param in TODAY_DEFECTS:
        return f"{name} ({TODAY_DEFECTS[param]})"
    return name


def explain(evaluate: Callable, ref: dict, mine: dict, skip=("keep",)) -> tuple[list[str], bool]:
    """Parameters whose one-at-a-time switch from the reference set changes the value.

    A switch the rules refuse on its own (Quilter's Paradise rounding needs its own seam and no
    allowance) is tried the other way, from the calculator's set back to the reference value.
    When no single switch moves the value but the full set does, the parameters act only
    together, so each one switched back from the calculator's set is named and joint is True.
    """

    def run(params):
        try:
            return True, evaluate(params)
        except ValueError:
            return False, None

    ok_ref, base = run(ref)
    ok_mine, value = run(mine)
    keys = [k for k in mine if k in ref and k not in skip and mine[k] != ref[k]]
    found = []
    for k in keys:
        ok, v = run({**ref, k: mine[k]})
        if ok and ok_ref:
            if v != base:
                found.append(k)
            continue
        ok, v = run({**mine, k: ref[k]})
        if ok and ok_mine and v != value:
            found.append(k)
    if found and ok_mine:
        # A parameter that moves the value only alongside a named one is a cause too: its
        # switch back from the calculator's set changes the shown value.
        for k in keys:
            if k not in found:
                ok, v = run({**mine, k: ref[k]})
                if ok and v != value:
                    found.append(k)
    if found or not (ok_ref and ok_mine) or base == value:
        return found, False
    joint = []
    for k in keys:
        ok, v = run({**mine, k: ref[k]})
        if ok and v != value:
            joint.append(k)
    return joint, True


def switch_labels(evaluate, ref, mine, today) -> tuple[list[str], bool]:
    params, joint = explain(evaluate, ref, mine)
    return _dedupe(cause(p, today) for p in params), joint and bool(params)


def switch_proof(evaluate: Callable, ref: dict, mine: dict, skip=("keep",)) -> dict:
    """What the labeled switches alone reach: the reference set's value (start) and the
    calculator's set with every unlabeled parameter put back to the reference (after). The
    labels account for a difference only when after is the shown value (Builder.compare)."""
    found, _joint = explain(evaluate, ref, mine, skip)
    keys = [k for k in mine if k in ref and k not in skip and mine[k] != ref[k]]
    params = dict(mine)
    for k in keys:
        # An unlabeled parameter the rules refuse to put back is a precondition of a labeled
        # switch (Quilter's Paradise rounding allows no allowance), not a cause; it stays.
        if k not in found and _safe(evaluate, {**params, k: ref[k]}) is not None:
            params[k] = ref[k]
    return {"kind": "switch", "start": _safe(evaluate, ref), "after": _safe(evaluate, params)}


def _status(labels, proof, shown, target, eq, anchor=None, bridge=None) -> tuple[str, str | None]:
    """The status of a difference whose rule reproduces the shown value, and why it is not
    explained. Explained needs its labels shown to carry the target to the shown value: the
    reference set gives the target (anchor, or its own value here; a bridge label covers the
    step between them), and the labeled switches alone give the shown value. A page model with
    no such proof is "page rule"."""
    if not labels or proof is None:
        return "unexplained", "its rule reproduces the shown value, but no label names a cause"
    if proof["kind"] == "page":
        return "page rule", None
    if proof["kind"] == "fixed":
        return ("explained", None) if proof["ok"] else ("unexplained", proof["why"])
    after = proof["after"]
    if after is None or not eq(after, shown):
        return "unexplained", (f"the labeled switches alone give {fmt_value(after)}, not the "
                               f"shown {fmt_value(shown)}")  # fmt: skip
    if bridge == "D-11":
        return "explained", None
    base = anchor if bridge == "orientation" else proof["start"]
    if base is None or not eq(base, target):
        return "unexplained", (f"the reference set gives {fmt_value(base)}, not the target "
                               f"{fmt_value(target)}, so the labels do not reach it")  # fmt: skip
    return "explained", None


def page_causes(spec: Model, kind: str, ref: dict | None) -> list[str]:
    # A cause stays unless every parameter it names is one the page shares with the reference
    # (Omni's seam loss against today's s = 0); page-rule text names no parameter, so it stays.
    causes = list(spec.causes.get(kind, ()))
    page = spec.params if spec.params is not None else spec.proxy
    if not page or not ref:
        return causes

    def shared(label: str) -> bool:
        keys = [p for p, name in CAUSES.items() if name == label and p in page]
        return bool(keys) and all(p in ref and ref[p] == page[p] for p in keys)

    return [c for c in causes if not shared(c)]


def _dedupe(items) -> list:
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _with(params, **overrides) -> dict | None:
    return None if params is None else {**params, **overrides}


def _set_text(name: str | None, params: dict | None) -> str | None:
    if params is None:
        return None
    inner = ", ".join(
        f"{k} {mixed(v) if isinstance(v, (int, F)) and not isinstance(v, bool) else v}"
        for k, v in params.items()
    )
    return f"{name}: {inner}"


def _safe(fn, *args):
    if any(a is None for a in args):
        return None
    try:
        return fn(*args)
    except ValueError:
        return None


# Page models from calc_rules, read as the quantities the report compares.


def _sd_backing(job: Job):
    return calc_rules.stitchdesk_backing(
        job.width, job.length, fabric_width=job.fabric, overhang_per_side=4,
        batting_overhang_per_side=4, seam_allowance=F(1, 2),
    )  # fmt: skip


def _size_kind(calc: Calc, job: Job) -> str:
    # Omni's width split shows only its 0.1 in piece rounding in the batting size; its length
    # split also shows the batting-mode width formula, so the two carry different causes.
    if calc.key == "omni_backing":
        r = calc_rules.omni_backing(job.width, job.length, bolt_width=job.fabric, overage=0,
                                    mode="batting")  # fmt: skip
        if r["seams"] == "vertical":
            return "size vertical"
    return "size"


def _same_package(a, b) -> bool:
    def norm(v):
        return "" if v is None or v == SD_OFF_THE_ROLL else str(v).strip().lower()

    return norm(a) == norm(b)


def model_value(calc: Calc, line: str, job: Job, quantity: str, layout=None, band=0):
    """The page model's value for one displayed quantity, or None without a model."""
    key = calc.key
    try:
        if key == "stitchdesk_backing":
            r = _sd_backing(job)
            if line == "backing":
                lay = layout if layout in ("vertical", "horizontal") else r["kept"]
                if quantity == "panels":
                    return r[lay]["panels"]
                if lay == r["kept"]:
                    return r["yards"]
                raw_e = calc_rules.to_eighths(r[lay]["raw"])
                return calc_rules.purchase_yards(raw_e, "eighth")
            if line == "wide":
                return None if r["wide"] is None or quantity != "yards" else r["wide"]["yards"]
            if line == "batting":
                bat = r["batting"]
                if quantity == "size":
                    return (bat["width"], bat["length"])
                return bat["precut"] or SD_OFF_THE_ROLL
        if key == "mfqs_backing":
            r = calc_rules.mfqs_backing(job.width, job.length, fabric_width=job.fabric, overage=4)
            if line == "backing":
                return r["backing"][quantity]
            if line == "wide":
                return None if r["wide"] is None else r["wide"][quantity]
            if line == "batting":
                bat = r["batting"]
                return (bat["width"], bat["length"]) if quantity == "size" else bat["package"]
        if key == "omni_backing":
            mode = "batting" if line == "batting" else "backing"
            r = calc_rules.omni_backing(job.width, job.length, bolt_width=job.fabric, overage=0,
                                        mode=mode)  # fmt: skip
            if r["too_many_pieces"]:
                return None
            lay = {"none": "one piece"}.get(r["seams"], r["seams"])
            if line == "batting":
                if quantity != "size":
                    return None
                return _omni_size(r["pieces"], r["piece_width"], r["piece_length"], lay)
            if layout is not None and layout != lay:
                return None
            return r["yards"] if quantity == "yards" else r["pieces"]
        if key == "dtq_border":
            r = calc_rules.dtq_border(job.width, job.length, job.bands[0],
                                      fabric_width=job.fabric)  # fmt: skip
            return r["straight"][quantity]
        if key == "qp_piece_count":
            pw, pl = (F(job.inputs[k]) for k in ("piece_width", "piece_length"))
            return calc_rules.qp_piece_count(pw, pl, job.width, job.length)["as_typed"]["pieces"]
        if key == "stitchdesk_binding":
            r = calc_rules.stitchdesk_binding(job.width, job.length, strip_width=F(5, 2),
                                              fabric_width=job.fabric)  # fmt: skip
            return r[quantity]
        if key == "sewbecca_border":
            r = calc_rules.sewbecca_border(job.width, job.length, job.bands[0],
                                           fabric_width=job.fabric)  # fmt: skip
            return r[quantity]
        if key == "qc_border":
            r = calc_rules.qc_border(job.width, job.length, list(job.bands),
                                     fabric_width=job.fabric)  # fmt: skip
            return r["borders"][band][quantity]
    except (ValueError, KeyError, IndexError):
        return None
    return None


# ---------------------------------------------------------------------------------------------
# Comparisons
# ---------------------------------------------------------------------------------------------

PREFIX = {"backing": "BK", "wide": "WB", "binding": "BD", "batting": "BT", "borders": "BR",
          "yield": "PC"}  # fmt: skip
LAYOUT_ABBR = {"vertical": "V", "horizontal": "H", "one piece": "1 pc", "unstated": "?"}


class Builder:
    def __init__(self, recs: dict, jobs: list[Job], qrep: dict, qrep_borders: dict, leads: dict):
        self.recs = recs
        self.qrep = qrep
        self.qrep_borders = qrep_borders
        self.leads = leads
        self.jobs_by_row: dict[tuple[str, str], list[Job]] = {}
        for job in jobs:
            self.jobs_by_row.setdefault((job.calculator, job.base), []).append(job)
        self.comparisons: list[dict] = []
        self.unexplained: list[dict] = []
        self.page_rule: list[dict] = []
        self.cells: dict[tuple, dict] = {}
        self.counter = dict.fromkeys(PREFIX.values(), 0)

    def row_jobs(self, calc: Calc, base: str, line_type: str) -> list[Job]:
        jobs = self.jobs_by_row.get((calc.key, base), [])
        return [j for j in jobs if line_type in j.line_types]

    def cell(self, table: str, row: str, job: Job) -> tuple[dict, Rec | None]:
        rec = self.recs.get((job.calculator, job.row_id))
        cell = {"status": rec.status if rec else "not run", "ids": [], "rec": rec, "job": job}
        self.cells[(table, row, job.calculator, job.variant)] = cell
        return cell, rec

    def rule_for(self, calc, line, evaluate, quantity, *, overrides=None, model=None, kind=None):
        """(has_rule, rule value, labeler(ref, today), rule text) for one displayed quantity:
        the calculator's MATH.md parameter set, else its page model, whose causes are looked up
        by kind (the quantity unless given)."""
        name = calc.rules.get(line)
        params = _with(rule_set(line, name), **(overrides or {}))
        if params is not None:
            value = _safe(evaluate, params) if evaluate else None

            def by_set(ref, today):
                labels, joint = switch_labels(evaluate, ref, params, today)
                return labels, joint, [], switch_proof(evaluate, ref, params)

            return True, value, by_set, _set_text(name, params)
        spec = calc.models.get(line)
        if spec is None or model is None:
            return False, None, None, None
        kind = kind or (quantity.split()[-1] if quantity.startswith("band") else quantity)

        def by_model(ref, today):
            if spec.proxy is not None and evaluate is not None and ref is not None:
                if _safe(evaluate, spec.proxy) == model:
                    labels, joint = switch_labels(evaluate, ref, spec.proxy, today)
                    if labels:
                        note = (f"labels from the proxy set ({_set_text('proxy', spec.proxy)}), "
                                "which gives the page model's value on this row")  # fmt: skip
                        return labels, joint, [note], switch_proof(evaluate, ref, spec.proxy)
            note = (f"labels list the page rule's differences from the reference "
                    f"(calc_rules.{spec.fn}); no MATH.md parameter set reproduces this row")  # fmt: skip
            return page_causes(spec, kind, ref), False, [note], {"kind": "page"}

        return True, model, by_model, f"calc_rules.{spec.fn}"

    def compare(
        self, cell, *, table, row, calc, job, quantity, shown, against, target, today,
        rule=(False, None, None, None), ref=None, pre_labels=(), notes=(), same=None,
        anchor=None, bridge=None,
    ) -> dict:  # fmt: skip
        """One comparison. anchor is the reference set's value for the target's own layout or
        size when the caller computes it; bridge names a pre-label that carries the target to
        the reference set's value here ("orientation": the anchor is the target's layout;
        "D-11": QREP today buys by area, which no parameter set models)."""
        has_rule, rule_value, labeler, rule_text = rule
        comp = {
            "line_type": "backing" if table == "wide" else table,
            "table": table,
            "row": row,
            "calculator": calc.key,
            "variant": job.variant,
            "row_id": job.row_id,
            "quantity": quantity,
            "shown": shown,
            "against": against,
            "target": target,
            "rule": rule_text,
            "rule_value": rule_value if has_rule else None,
            "reproduced": None,
            "labels": [],
            "joint": False,
            "notes": list(notes),
            "id": None,
        }
        eq = same or (lambda a, b: a == b)
        if has_rule:
            comp["reproduced"] = rule_value is not None and eq(rule_value, shown)
        if eq(shown, target):
            comp["status"] = "match"
        elif calc.record_only:
            comp["status"] = "record only"
            if comp["reproduced"]:
                comp["notes"].append(f"{rule_text} reproduces the shown value")
            elif has_rule:
                comp["notes"].append(f"{rule_text} gives {fmt_value(rule_value)}")
        elif not has_rule:
            comp["status"] = "unexplained"
            comp["notes"].append("no parameter set or page model covers this calculator")
        elif not comp["reproduced"]:
            comp["status"] = "unexplained"
            comp["notes"].append(
                f"its rule gives {fmt_value(rule_value)}, not the shown {fmt_value(shown)}"
            )
        else:
            labels, joint, more, proof = (labeler(ref, today) if labeler
                                          else ([], False, [], None))  # fmt: skip
            comp["labels"] = _dedupe([*pre_labels, *labels])
            comp["joint"] = joint
            comp["notes"] += more
            comp["status"], why = _status(comp["labels"], proof, shown, target, eq, anchor, bridge)
            if why:
                comp["notes"].append(why)
        if comp["status"] != "match":
            prefix = PREFIX[table]
            self.counter[prefix] += 1
            comp["id"] = f"{prefix}-{self.counter[prefix]}"
            cell["ids"].append(comp["id"])
        if comp["status"] in ("unexplained", "page rule"):
            entry = {k: comp[k] for k in ("id", "line_type", "row", "calculator", "variant",
                                          "quantity", "shown", "against", "target", "rule",
                                          "rule_value", "labels", "notes")}  # fmt: skip
            entry["lead"] = self.leads.get(calc.key)
            (self.unexplained if comp["status"] == "unexplained" else self.page_rule).append(entry)
        self.comparisons.append(comp)
        return comp

    # -- backing ---------------------------------------------------------------------------

    def backing(self):
        for rid, _label, w, ln in cv.MATRIX:
            for calc in _calcs("backing"):
                for job in self.row_jobs(calc, rid, "backing"):
                    cell, rec = self.cell("backing", rid, job)
                    if rec is None or rec.status != "ok":
                        continue
                    if "backing" not in rec.values:
                        if "wide" not in rec.values:
                            cell["status"] = "no backing value"
                        continue
                    self._backing_cell(cell, calc, job, rec, rid, w, ln)

    def _backing_cell(self, cell, calc, job, rec, rid, w, ln):
        b = rec.values["backing"]
        fabric = job.fabric
        vector = {F(42): cv.BACKING_B42, F(40): cv.BACKING_B40}.get(fabric, {}).get(rid)
        mode = {F(42): "default", F(40): "wof320"}.get(fabric)
        layout = choose_layout(b, vector["kept"] if vector else None)
        cell["compared"] = layout
        shown = b["layouts"][layout]
        targets = []
        if vector:
            ref = _with(calc_rules.BACKING_SETS["math"], B=fabric)
            targets.append((False, vector["vector"], vector, vector["kept"], ref))
        if mode:
            today = self.qrep[rid][mode]["backing"]
            ref = _with(calc_rules.BACKING_SETS["today"], B=fabric)
            name = "QREP today" if mode == "default" else "QREP at wof 320"
            targets.append((True, name, today, "vertical", ref))
        for quantity in ("yards", "panels"):
            value = shown.get(quantity)
            if value is None:
                continue

            def evaluate(params, q=quantity):
                got = calc_rules.backing(w, ln, **params)
                return got[layout][q] if layout in LAYOUTS else got[q]

            rule = self.rule_for(
                calc, "backing", evaluate, quantity, overrides={"B": fabric},
                model=model_value(calc, "backing", job, quantity, layout),
            )  # fmt: skip
            for today, target_id, target, kept, ref in targets:
                pre, notes = [], []
                if layout in LAYOUTS and layout != kept:
                    pre.append(cause("keep", today))
                ref_value = _safe(lambda p, q=quantity, k=kept: calc_rules.backing(w, ln, **p)[k][q],
                                  ref)  # fmt: skip
                if ref_value is not None and ref_value != target[quantity]:
                    notes.append(f"the reference set gives {fmt_value(ref_value)} here")
                self.compare(
                    cell, table="backing", row=rid, calc=calc, job=job, quantity=quantity,
                    shown=value, against=target_id, target=target[quantity], today=today,
                    rule=rule, ref=ref, pre_labels=pre, notes=notes, anchor=ref_value,
                    bridge="orientation" if pre else None,
                )  # fmt: skip

    # -- wide-back ---------------------------------------------------------------------------

    def wide(self):
        for rid, _label, w, ln in cv.MATRIX:
            vec_row = cv.WIDE.get(rid)
            for calc in _calcs("backing"):
                for job in self.row_jobs(calc, rid, "backing"):
                    rec = self.recs.get((job.calculator, job.row_id))
                    if "wide" in calc.rules and job.variant in ("108", "118"):
                        cell, rec = self.cell("wide", rid, job)
                        if rec is None or rec.status != "ok" or "wide" not in rec.values:
                            continue
                        bw = job.fabric
                        layouts = rec.values["wide"]["layouts"]
                    elif rec is not None and rec.status == "ok" and (
                        (rec.values.get("backing") or {}).get("wide")
                    ):
                        cell, rec = self.cell("wide", rid, job)
                        wide = rec.values["backing"]["wide"]
                        bw = wide["width"]
                        layouts = {"one piece": {"yards": wide["yards"],
                                                 "panels": wide.get("panels")}}  # fmt: skip
                    else:
                        continue
                    self._wide_cell(cell, calc, job, rid, w, ln, vec_row, bw, layouts)

    def _wide_cell(self, cell, calc, job, rid, w, ln, vec_row, bw, layouts):
        ref = _with(calc_rules.BACKING_SETS["math"], B=bw)
        kept = calc_rules.backing(w, ln, **ref)["kept"]
        layout = kept if kept in layouts else choose_layout({"layouts": layouts}, None)
        cell.update(compared=layout, width=bw, layouts=layouts)
        key = f"bw{F(bw).numerator}" if F(bw).denominator == 1 else None
        if vec_row is None or key not in vec_row:
            cell["note"] = "no vector at this width"
            return
        vector = vec_row[key]
        if vector is None:
            cell["note"] = f"MATH.md prints no wide line at {mixed(bw)} in ({vec_row['vector']})"
            return
        shown = layouts[layout]
        # F11 is one piece of wide fabric, so the vector's panel count is 1 by definition.
        target = {"yards": vector["yards"], "panels": 1}
        for quantity in ("yards", "panels"):
            value = shown.get(quantity)
            if value is None:
                continue

            def evaluate(params, q=quantity):
                got = calc_rules.backing(w, ln, **params)
                return got[layout][q] if layout in LAYOUTS else got[q]

            notes = []
            ref_value = _safe(evaluate, ref)
            if ref_value is not None and ref_value != target[quantity]:
                notes.append(f"the reference set gives {fmt_value(ref_value)} here")
            rule = self.rule_for(
                calc, "wide", evaluate, quantity, overrides={"B": bw},
                model=model_value(calc, "wide", job, quantity),
            )  # fmt: skip
            self.compare(
                cell, table="wide", row=rid, calc=calc, job=job, quantity=quantity, shown=value,
                against=vec_row["vector"], target=target[quantity], today=False, rule=rule,
                ref=ref, notes=notes,
            )  # fmt: skip

    # -- binding -----------------------------------------------------------------------------

    def binding(self):
        for rid, _label, w, ln in cv.MATRIX:
            today = self.qrep[rid]["default"]["binding"]
            for calc in _calcs("binding"):
                for job in self.row_jobs(calc, rid, "binding"):
                    cell, rec = self.cell("binding", rid, job)
                    if rec is None or rec.status != "ok":
                        continue
                    if "binding" not in rec.values:
                        cell["status"] = "no binding value"
                        continue
                    self._binding_cell(cell, calc, job, rec, rid, w, ln, today)

    def _binding_cell(self, cell, calc, job, rec, rid, w, ln, today):
        shown = rec.values["binding"]
        vec42 = cv.BINDING_U42.get(rid)
        if job.fabric == 42 and vec42:
            vector, vec_u = vec42, 42
        else:
            vector, vec_u = cv.BINDING_U40.get(rid), 40
        cell["vector"] = vector["vector"] if vector else None
        targets = []
        if vector:
            targets.append((False, vector["vector"], vector,
                            _with(calc_rules.BINDING_SETS["math"], U=vec_u)))  # fmt: skip
        targets.append((True, "QREP today", today, dict(calc_rules.BINDING_SETS["today"])))
        for quantity in ("strips", "yards"):
            value = shown.get(quantity)
            if value is None:
                continue

            def evaluate(params, q=quantity):
                return calc_rules.binding(w, ln, **params)[q]

            rule = self.rule_for(calc, "binding", evaluate, quantity,
                                 model=model_value(calc, "binding", job, quantity))  # fmt: skip
            for is_today, target_id, target, ref in targets:
                notes = []
                ref_value = _safe(evaluate, ref)
                if ref_value is not None and ref_value != target[quantity]:
                    notes.append(f"the reference set gives {fmt_value(ref_value)} here")
                self.compare(
                    cell, table="binding", row=rid, calc=calc, job=job, quantity=quantity,
                    shown=value, against=target_id, target=target[quantity], today=is_today,
                    rule=rule, ref=ref, notes=notes,
                )  # fmt: skip

    # -- batting -----------------------------------------------------------------------------

    def batting(self):
        for rid, _label, w, ln in cv.MATRIX:
            vector = cv.BATTING.get(rid)
            today = self.qrep[rid]["default"]["batting"]
            for calc in _calcs("batting"):
                for job in self.row_jobs(calc, rid, "batting"):
                    cell, rec = self.cell("batting", rid, job)
                    if rec is None or rec.status != "ok":
                        continue
                    if "batting" not in rec.values:
                        cell["status"] = "no batting value"
                        continue
                    bat = rec.values["batting"]
                    if "roll_length" in bat:
                        self._roll(cell, calc, job, rid, w, ln, bat, vector, today)
                    else:
                        self._size(cell, calc, job, rid, bat, vector, today)

    def _roll(self, cell, calc, job, rid, w, ln, bat, vector, today):
        # The page sells batting as a roll length on the typed width, and the vector is a size:
        # the roll length is set against the size's length, and the page's rounding explains it.
        try:
            yards, widths = calc_rules.qp_backing_display(w, ln, job.fabric, 4)
        except ValueError:
            yards, widths = None, None
        notes = []
        if widths is not None and widths != 1:
            notes.append(f"its rule needs {widths} widths of {mixed(job.fabric)} in")
        # Rounding accounts for the gap only when the page's unrounded length, L + 2 x 4 on one
        # width, is the target itself.
        raw = F(ln) + 8

        def labeler(target):
            ok = widths == 1 and target == raw
            why = None if ok else (f"the page's unrounded length is {fmt_value(raw)} in on "
                                   f"{widths} width(s), not the target {fmt_value(target)}")  # fmt: skip
            return lambda ref, today: ([cause("increment", today)], False, [],
                                       {"kind": "fixed", "ok": ok, "why": why})  # fmt: skip

        targets = [(vector["vector"], vector["length"], False)] if vector else []
        targets.append(("QREP today", today["length"], True))
        for target_id, target, is_today in targets:
            rule = (yards is not None, None if yards is None else yards * 36, labeler(target),
                    f"qp_backing_display, bolt {mixed(job.fabric)}, overage 4")  # fmt: skip
            self.compare(
                cell, table="batting", row=rid, calc=calc, job=job, quantity="roll length (in)",
                shown=bat["roll_length"], against=target_id, target=target, today=is_today,
                rule=rule, notes=notes,
            )  # fmt: skip

    def _size(self, cell, calc, job, rid, bat, vector, today):
        def same_size(a, b):
            return a == b or (a is not None and b is not None and (a[1], a[0]) == tuple(b))

        if bat.get("width") is not None and bat.get("length") is not None:
            shown = (bat["width"], bat["length"])
            rule = self.rule_for(calc, "batting", None, "size",
                                 model=model_value(calc, "batting", job, "size"),
                                 kind=_size_kind(calc, job))  # fmt: skip
            targets = [(vector["vector"], (vector["width"], vector["length"]), False)] if vector else []
            targets.append(("QREP today", (today["width"], today["length"]), True))
            for target_id, target, is_today in targets:
                self.compare(
                    cell, table="batting", row=rid, calc=calc, job=job, quantity="size (in)",
                    shown=shown, against=target_id, target=target, today=is_today, rule=rule,
                    same=same_size,
                )  # fmt: skip
        if vector and "package" in bat:
            rule = self.rule_for(calc, "batting", None, "package",
                                 model=model_value(calc, "batting", job, "package"))  # fmt: skip
            self.compare(
                cell, table="batting", row=rid, calc=calc, job=job, quantity="package",
                shown=bat["package"], against=vector["vector"], target=vector["package"],
                today=False, rule=rule, same=_same_package,
            )  # fmt: skip

    # -- borders -----------------------------------------------------------------------------

    def borders(self):
        for rid, _label, _cw, _cl, bands in cv.BORDER_ROWS:
            vector = cv.BORDER.get(rid)
            today = self.qrep_borders[rid]["wof320"]["borders"]
            for calc in _calcs("borders"):
                for job in self.row_jobs(calc, rid, "borders"):
                    cell, rec = self.cell("borders", rid, job)
                    if rec is None or rec.status != "ok":
                        continue
                    if "borders" not in rec.values:
                        cell["status"] = "no border value"
                        continue
                    self._border_cell(cell, calc, job, rid, bands, vector, today, rec)

    def _border_cell(self, cell, calc, job, rid, bands, vector, today, rec):
        shown_bands = rec.values["borders"]["bands"]
        row_w, row_l = next((cw, cl) for r, _lb, cw, cl, _b in cv.BORDER_ROWS if r == rid)
        # The rules get the size the page was given: the center, or the finished size on a
        # finished-size row.
        cw, cl = job.width, job.length
        ref = dict(calc_rules.BORDER_SETS["math"])
        for i in range(len(bands)):
            if i >= len(shown_bands):
                cell.setdefault("notes", []).append(f"band {i + 1} not shown")
                continue
            sb = shown_bands[i]

            def evaluate(params, i=i):
                return calc_rules.border(cw, cl, list(bands), **params)["bands"][i]["strips"]

            if sb.get("strips") is not None and vector:
                target = vector["bands"][i]["strips"]
                notes = []
                ref_value = _safe(
                    lambda p, i=i: calc_rules.border(row_w, row_l, list(bands), **p)["bands"][i][
                        "strips"
                    ],
                    ref,
                )
                if ref_value is not None and ref_value != target:
                    notes.append(f"the reference set gives {fmt_value(ref_value)} here")
                rule = self.rule_for(
                    calc, "borders", evaluate, f"band {i + 1} strips",
                    model=model_value(calc, "borders", job, "strips", band=i),
                )  # fmt: skip
                self.compare(
                    cell, table="borders", row=rid, calc=calc, job=job,
                    quantity=f"band {i + 1} strips", shown=sb["strips"], against=vector["vector"],
                    target=target, today=False, rule=rule, ref=ref, notes=notes,
                )  # fmt: skip
            if sb.get("yards") is not None and i < len(today):
                self._border_yards(cell, calc, job, rid, bands, i, sb, today, cw, cl)

    def _border_yards(self, cell, calc, job, rid, bands, i, sb, today, cw, cl):
        def evaluate(params, i=i):
            return calc_rules.border(cw, cl, list(bands), **params)["bands"][i]["yards"]

        rule = self.rule_for(calc, "borders", evaluate, f"band {i + 1} yards",
                             model=model_value(calc, "borders", job, "yards", band=i))  # fmt: skip
        # QREP today buys borders by area (D-11), which no parameter set models, so the chain is
        # today -> MATH.md's strip set (D-11, and today's 1/4 yd where it differs) -> the
        # calculator's set by labeled switches. D-11 is named only where the strip set's value
        # differs from today's.
        target = today[i]["yards"]
        strip_set = rule_set("borders", "math")
        strip_value = _safe(evaluate, strip_set)
        pre, notes, bridge = [], [], None
        if strip_value is not None and strip_value != target:
            pre, bridge = ["border area (D-11)"], "D-11"
            notes.append(f"MATH.md's strip set gives {fmt_value(strip_value)} here")
            params = rule_set("borders", calc.rules.get("borders"))
            band = _safe(lambda p: calc_rules.border(cw, cl, list(bands), **p)["bands"][i], params)
            if band is not None:
                quarter = calc_rules.purchase_yards(calc_rules.to_eighths(band["length"]),
                                                    "quarter")  # fmt: skip
                if quarter != band["yards"]:
                    pre.append(cause("increment", True))
        self.compare(
            cell, table="borders", row=rid, calc=calc, job=job, quantity=f"band {i + 1} yards",
            shown=sb["yards"], against="QREP at wof 320", target=target, today=True,
            rule=rule, ref=strip_set, pre_labels=pre, notes=notes, bridge=bridge,
        )  # fmt: skip

    # -- piece count -------------------------------------------------------------------------

    def pieces(self):
        calc = REGISTRY["qp_piece_count"]
        for rid, variant, _label, _pw, _pl, _lw, _ll, expected, cite in YIELD_ROWS:
            for job in self.row_jobs(calc, rid, "yield"):
                if job.variant != variant:
                    continue
                cell, rec = self.cell("yield", f"{rid}@{variant}", job)
                if rec is None or rec.status != "ok" or "yield" not in rec.values:
                    continue
                rule = self.rule_for(calc, "yield", None, "pieces",
                                     model=model_value(calc, "yield", job, "pieces"))  # fmt: skip
                self.compare(
                    cell, table="yield", row=f"{rid}@{variant}", calc=calc, job=job,
                    quantity="pieces", shown=rec.values["yield"]["pieces"], against=rid,
                    target=expected, today=False, rule=rule, notes=[cite],
                )  # fmt: skip

    def run(self):
        self.backing()
        self.wide()
        self.binding()
        self.batting()
        self.borders()
        self.pieces()
        return self


LAYOUTS = ("vertical", "horizontal")


def _calcs(line_type: str) -> list[Calc]:
    return [c for c in REGISTRY.values() if line_type in c.line_types]


def choose_layout(b: dict, vector_kept: str | None) -> str:
    """The vector's kept layout when the page shows it (MATH.md 5.2), else the page's own
    choice, else the cheaper of the two it shows, vertical on a tie (F10)."""
    layouts = b["layouts"]
    if vector_kept in layouts:
        return vector_kept
    if b.get("chosen") in layouts:
        return b["chosen"]
    if "vertical" in layouts and "horizontal" in layouts:
        v, h = layouts["vertical"]["yards"], layouts["horizontal"]["yards"]
        return "horizontal" if h < v else "vertical"
    return next(iter(layouts))


def fmt_value(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, tuple):
        return " x ".join(mixed(v) for v in value)
    if isinstance(value, (int, F)) and not isinstance(value, bool):
        return mixed(value)
    return str(value)


# ---------------------------------------------------------------------------------------------
# Coverage, counts and the search summary
# ---------------------------------------------------------------------------------------------

COVER_TYPES = ("backing", "binding", "batting", "borders", "yield")


def _returned(rec: Rec | None, line_type: str) -> bool:
    if rec is None or rec.status != "ok":
        return False
    if line_type == "backing":
        return "backing" in rec.values or "wide" in rec.values
    return line_type in rec.values


def coverage(plan: list[Job], universe: list[Job], picked: dict) -> dict:
    """Per calculator and line type: planned jobs, rows tried (a record that was not a
    not-applicable skip) and rows that returned a parsed value."""
    out = {}
    for calc in REGISTRY.values():
        row = {}
        for lt in COVER_TYPES:
            if lt not in calc.line_types:
                continue
            planned = [j for j in plan if j.calculator == calc.key and lt in j.line_types
                       and j.applicable]  # fmt: skip
            seen = {j.row_id for j in planned}
            extra = [j for j in universe if j.calculator == calc.key and lt in j.line_types
                     and j.row_id not in seen and (j.calculator, j.row_id) in picked]  # fmt: skip
            recs = [picked.get((j.calculator, j.row_id)) for j in planned + extra]
            tried = [r for r in recs if r is not None and r.status != "not applicable"]
            row[lt] = {
                "planned": len(planned),
                "tried": len(tried),
                "returned": sum(_returned(r, lt) for r in tried),
            }
        out[calc.key] = row
    return out


def line_counts(cov: dict) -> dict:
    out = {}
    for lt in LINE_TYPES:
        got = [k for k in REGISTRY if lt in cov[k] and cov[k][lt]["returned"]]
        on = [k for k in got if REGISTRY[k].on_list]
        added = [k for k in got if not REGISTRY[k].on_list]
        out[lt] = {
            "on_list": on,
            "added": added,
            "n_on_list": len(on),
            "n_added": len(added),
            "n": len(got),
            "shortfall_from_four": max(0, 4 - len(got)),
        }
    return out


def _norm_url(url: str) -> str:
    return url.strip().rstrip("/").lower()


def search_summary() -> dict:
    data = json.loads(SEARCHES.read_text(encoding="utf-8"))
    registry_urls = {_norm_url(c.url) for c in REGISTRY.values()}
    per = {}
    for lt in LINE_TYPES:
        queries = [q for q in data["queries"] if q["line_type"] == lt]
        qualified = [q for q in data["qualified"] if lt in q["line_types"]]
        per[lt] = {
            "queries": len(queries),
            "results_listed": sum(q.get("result_count", 0) for q in queries),
            "qualified": len(qualified),
            "qualified_vendors": [q["vendor"] for q in qualified],
            "added": [c.key for c in REGISTRY.values() if not c.on_list and lt in c.line_types],
        }
    return {
        "searched_on": data.get("searched_on"),
        "method": data.get("method"),
        "per_line_type": per,
        "queries_total": len(data["queries"]),
        "qualified_total": len(data["qualified"]),
        "qualified_not_driven": [
            {"vendor": q["vendor"], "url": q["url"]}
            for q in data["qualified"]
            if _norm_url(q["url"]) not in registry_urls
        ],
        "rejected": len(data["rejected"]),
    }


def calculator_leads() -> dict:
    """What is known of each calculator's rule, as a lead for the A1 and A2 owners."""
    data = json.loads(SEARCHES.read_text(encoding="utf-8"))
    formulas = {_norm_url(q["url"]): q.get("formula") for q in data["qualified"]}
    out = {}
    for calc in REGISTRY.values():
        parts = [calc.lead, calc.rule_source, formulas.get(_norm_url(calc.url))]
        parts = [ascii_text(p) for p in parts if p]
        out[calc.key] = "; ".join(parts) if parts else None
    return out


# ---------------------------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------------------------


def md_table(headers, rows) -> list[str]:
    out = ["| " + " | ".join(md_cell(h) for h in headers) + " |",
           "| " + " | ".join("---" for _ in headers) + " |"]  # fmt: skip
    out += ["| " + " | ".join(md_cell(c) for c in row) + " |" for row in rows]
    return out


def _ids(cell) -> str:
    return f" [{', '.join(cell['ids'])}]" if cell and cell["ids"] else ""


def _status_text(cell) -> str | None:
    if cell is None:
        return "not run"
    status = cell["status"]
    if status == "ok":
        return None
    rec = cell.get("rec")
    if status in FAILED and rec is not None and rec.failure_id:
        return f"{status} [{rec.failure_id}]"
    if status == "not applicable":
        detail = (rec.detail if rec and rec.detail else "").removeprefix("not applicable")
        return "n/a" + (f" ({detail.lstrip(': ')})" if detail.strip(": ") else "")
    return status


def _layouts_text(layouts: dict, first: str | None) -> str:
    order = ([first] if first in layouts else []) + [k for k in layouts if k != first]
    parts = []
    for lay in order:
        v = layouts[lay]
        panels = f" ({v['panels']})" if v.get("panels") is not None else ""
        parts.append(f"{LAYOUT_ABBR.get(lay, lay)} {mixed(v['yards'])}{panels}")
    return "; ".join(parts)


def cell_text(table: str, cell) -> str:
    status = _status_text(cell)
    if status is not None:
        return status
    values = cell["rec"].values
    if table == "backing":
        b = values["backing"]
        return _layouts_text(b["layouts"], cell.get("compared")) + _ids(cell)
    if table == "wide":
        text = _layouts_text(cell["layouts"], cell.get("compared"))
        if cell["job"].calculator != "nqc":
            text = f"{mixed(cell['width'])} in: {text}"
        note = f" ({cell['note']})" if cell.get("note") else ""
        return text + note + _ids(cell)
    if table == "binding":
        b = values["binding"]
        strips = "-" if b.get("strips") is None else f"{b['strips']} strips"
        return f"{strips}, {mixed(b.get('yards'))}" + _ids(cell)
    if table == "batting":
        b = values["batting"]
        if "roll_length" in b:
            text = f"{mixed(b['roll_yards'])} yd = {mixed(b['roll_length'])} in"
        else:
            text = f"{mixed(b.get('width'))} x {mixed(b.get('length'))}"
            if b.get("package") is not None:
                text += f", {b['package']}"
        return text + _ids(cell)
    if table == "borders":
        parts = []
        for i, b in enumerate(values["borders"]["bands"], 1):
            strips = "" if b.get("strips") is None else f"{b['strips']} strips, "
            parts.append(f"b{i}: {strips}{mixed(b.get('yards'))}")
        return "; ".join(parts) + _ids(cell)
    if table == "yield":
        y = values["yield"]
        turned = f" (turned {y['turned']})" if y.get("turned") is not None else ""
        return f"{y['pieces']} pieces{turned}" + _ids(cell)
    return "?"


def _columns(builder: Builder, table: str, spec) -> list[tuple[str, str, str]]:
    """(calculator, variant, header) for each spec entry that has a planned or recorded job."""
    out = []
    for key, variant, header in spec:
        if any(k[0] == table and k[2] == key and k[3] == variant for k in builder.cells):
            out.append((key, variant, header))
    return out


def _calc_cells(builder, table, row, cols) -> list[str]:
    return [cell_text(table, builder.cells.get((table, row, key, variant)))
            for key, variant, _h in cols]  # fmt: skip


def _vector_backing(v) -> str:
    if v is None:
        return "no vector"
    return f"{v['vector']}: {LAYOUT_ABBR[v['kept']]} {mixed(v['yards'])} ({v['panels']})"


def _qrep_backing(q) -> str:
    return f"V {mixed(q['yards'])} ({q['panels']})"


def render(ctx: dict) -> str:
    b: Builder = ctx["builder"]
    p = ctx["provenance"]
    out = ["# D2 calculator conformance baseline", ""]
    out += [f"Generated on {p['date']} by:", "", "```", p["command"], "```", ""]
    if p.get("driver_command"):
        out += ["The driver ran as:", "", "```", p["driver_command"], "```", ""]
    runs = p.get("calculator_runs") or {}
    out += md_table(
        ["Item", "Value"],
        [
            ("qrep imported from", p["qrep_file"]),
            ("git HEAD", p["head"]),
            ("Harness tree (scripts/eval/calculators at git HEAD)",
             f"{p['harness_tree']}; uncommitted changes there: "
             f"{'yes' if p['harness_uncommitted'] else 'none'}"),
            ("Start SHA", f"{p['start_sha']} (given as {p['start_sha_arg']})"),
            ("qrep tree at the start SHA", p["qrep_tree"]),
            ("OpenCV (cv2)", f"{p['cv2']}; decode path: {p['decode_path']}"),
            ("Raw record files", "; ".join(f"{r['path']} (n = {r['records']} records)"
                                           for r in p["raw_files"])),  # fmt: skip
            ("Calculator runs (record timestamps)",
             f"{runs.get('first') or '-'} to {runs.get('last') or '-'}"),
            ("Border size basis", ", ".join(f"{k} {v}" for k, v in p["border_size_basis"].items())),
        ],
    )  # fmt: skip
    out += [
        "",
        "QREP values come from qrep.bridge.plan at the start SHA (calc_qrep.py), at the engine "
        "default (wof 336, 42 in) and configured at wof 320 (40 in). MATH.md vectors come from "
        "calc_vectors.py, transcribed from MATH.md section 4. Yards print as mixed fractions; "
        "V and H are vertical and horizontal seams; (n) after a yardage is its panel count; the "
        "first layout in a calculator cell is the one compared. Bracketed ids point to the "
        "labeled differences.",
        "",
        "## Inputs",
        "",
        f"### Size matrix (n = {len(cv.MATRIX)}, MATH.md 5.2)",
        "",
    ]
    out += md_table(["Row", "Quilt", "W x L (in)"],
                    [(rid, label, f"{mixed(w)} x {mixed(ln)}") for rid, label, w, ln in cv.MATRIX])
    out += ["", f"### Border rows (n = {len(cv.BORDER_ROWS)})", ""]
    out += md_table(
        ["Row", "Label", "Center (in)", "Bands, outside last (in)", "Finished (in)"],
        [
            (rid, label, f"{mixed(cw)} x {mixed(cl)}", ", ".join(mixed(x) for x in bands),
             f"{mixed(cw + 2 * sum(bands))} x {mixed(cl + 2 * sum(bands))}")
            for rid, label, cw, cl, bands in cv.BORDER_ROWS
        ],
    )  # fmt: skip
    out += ["", f"### Piece count spot checks (n = {len(YIELD_ROWS)})", ""]
    out += md_table(
        ["Row", "Check", "Expected pieces", "Source"],
        [(f"{rid}@{var}", label, n, cite) for rid, var, label, *_rest, n, cite in YIELD_ROWS],
    )
    out += ["", f"### Calculators (n = {len(REGISTRY)})", ""]
    out += md_table(
        ["Key", "Vendor and page", "URL", "Line types", "MATH.md 5.2 list", "Inputs typed",
         "Set by the driver", "Parser", "Rule"],
        [
            (c["key"], f"{c['vendor']}: {c['page']}", c["url"], ", ".join(c["line_types"]),
             "yes" if c["on_list"] else "added", "; ".join(c["inputs_typed"]), c["fixed"] or "-",
             c["parser_status"],
             (c["rule"] or "none") + (f" ({c['rule_source']})" if c["rule_source"] else ""))
            for c in ctx["calculators"]
        ],
    )  # fmt: skip

    out += ["", "## Coverage", "",
            "Rows that returned a parsed value, of rows tried (a record that was not a "
            "not-applicable skip); the planned row count follows when it differs.", ""]  # fmt: skip
    cov = ctx["coverage"]
    rows = []
    for key in REGISTRY:
        cells = [key]
        for lt in COVER_TYPES:
            c = cov[key].get(lt)
            if c is None:
                cells.append("-")
            else:
                planned = f" (planned n = {c['planned']})" if c["planned"] != c["tried"] else ""
                cells.append(f"n = {c['returned']} of {c['tried']}{planned}")
        rows.append(cells)
    out += md_table(["Calculator", "Backing", "Binding", "Batting", "Borders", "Piece count"],
                    rows)  # fmt: skip

    out += ["", "## Backing", "", "### Pieced at 42 in", ""]
    cols = _columns(b, "backing", [("qp_backing", "42", "Quilter's Paradise 42"),
                                   ("mfqs_backing", "42", "My Favorite Quilt Store 42 (record only)"),
                                   ("stitchdesk_backing", "42", "Stitch Desk 42"),
                                   ("omni_backing", "42", "Omni 42")])  # fmt: skip
    out += md_table(
        ["Row", "MATH.md vector (B 42)", "QREP today (wof 336)"] + [h for *_k, h in cols],
        [[rid, _vector_backing(cv.BACKING_B42.get(rid)),
          _qrep_backing(ctx["qrep"][rid]["default"]["backing"]),
          *_calc_cells(b, "backing", rid, cols)] for rid, *_r in cv.MATRIX],
    )  # fmt: skip
    out += ["", "### Pieced at 40 in", ""]
    cols = _columns(b, "backing", [("qp_backing", "40", "Quilter's Paradise 40"),
                                   ("nqc", "40", "Nebraska 40")])  # fmt: skip
    out += md_table(
        ["Row", "MATH.md vector (B 40)", "QREP at wof 320"] + [h for *_k, h in cols],
        [[rid, _vector_backing(cv.BACKING_B40.get(rid)),
          _qrep_backing(ctx["qrep"][rid]["wof320"]["backing"]),
          *_calc_cells(b, "backing", rid, cols)] for rid, *_r in cv.MATRIX],
    )  # fmt: skip
    out += ["", "### Wide-back", "",
            "QREP today has no wide-back line (D-06). A 42 in calculator's cell shows the wide "
            "line it prints beside its pieced result.", ""]  # fmt: skip
    cols = _columns(b, "wide", [("nqc", "108", "Nebraska 108"), ("nqc", "118", "Nebraska 118"),
                                ("stitchdesk_backing", "42", "Stitch Desk wide line"),
                                ("mfqs_backing", "42", "My Favorite Quilt Store wide line")])

    def wide_vec(rid, width):
        row = cv.WIDE.get(rid)
        if row is None or f"bw{width}" not in row:
            return "no vector"
        v = row[f"bw{width}"]
        if v is None:
            return f"{row['vector']}: no {width} in line"
        return f"{row['vector']}: {mixed(v['yards'])} ({mixed(v['length'])} in)"

    out += md_table(
        ["Row", "MATH.md vector 108", "MATH.md vector 118"] + [h for *_k, h in cols],
        [[rid, wide_vec(rid, 108), wide_vec(rid, 118), *_calc_cells(b, "wide", rid, cols)]
         for rid, *_r in cv.MATRIX],
    )  # fmt: skip

    out += ["", "## Binding", "",
            "Vectors at U = 40 (V-BIND-09 at U = 42 for the fixture, used for 42 in "
            "calculators). QREP today joins blind at 42 in (D-08).", ""]  # fmt: skip
    cols = _columns(b, "binding", [("qp_binding", "40", "Quilter's Paradise 40"),
                                   ("nqc", "40", "Nebraska 40"),
                                   ("stitchdesk_binding", "42", "Stitch Desk 42"),
                                   ("quiltkeeper_binding", "40", "QuiltKeeper 40")])  # fmt: skip

    def bind_vec(rid):
        v = cv.BINDING_U40.get(rid)
        text = "no vector" if v is None else f"{v['vector']}: {v['strips']}, {mixed(v['yards'])}"
        v42 = cv.BINDING_U42.get(rid)
        if v42:
            text += f"; at 42 {v42['vector']}: {v42['strips']}, {mixed(v42['yards'])}"
        return text

    out += md_table(
        ["Row", "MATH.md vector (strips, yd)", "QREP today (wof 336)"] + [h for *_k, h in cols],
        [[rid, bind_vec(rid),
          "{strips}, {yd}".format(strips=ctx["qrep"][rid]["default"]["binding"]["strips"],
                                  yd=mixed(ctx["qrep"][rid]["default"]["binding"]["yards"])),
          *_calc_cells(b, "binding", rid, cols)] for rid, *_r in cv.MATRIX],
    )  # fmt: skip

    out += ["", "## Batting", "",
            "Quilter's Paradise sells batting as a roll length on a 120 in bolt; its implied "
            "length is set against the batting length.", ""]  # fmt: skip
    cols = _columns(b, "batting", [("qp_backing", "batting120", "Quilter's Paradise roll 120"),
                                   ("mfqs_backing", "42", "My Favorite Quilt Store (record only)"),
                                   ("stitchdesk_backing", "42", "Stitch Desk"),
                                   ("omni_backing", "42-batting", "Omni")])  # fmt: skip

    def batt_vec(rid):
        v = cv.BATTING.get(rid)
        if v is None:
            return "no vector"
        return f"{v['vector']}: {mixed(v['width'])} x {mixed(v['length'])}, {v['package']}"

    out += md_table(
        ["Row", "MATH.md vector", "QREP today"] + [h for *_k, h in cols],
        [[rid, batt_vec(rid),
          "{w} x {h}".format(w=mixed(ctx["qrep"][rid]["default"]["batting"]["width"]),
                             h=mixed(ctx["qrep"][rid]["default"]["batting"]["length"])),
          *_calc_cells(b, "batting", rid, cols)] for rid, *_r in cv.MATRIX],
    )  # fmt: skip

    out += ["", "## Borders", "",
            "Vectors are F4 per piece at U = 40 (strips per band). QREP today cuts one piece per "
            "side and buys by area, with no strip count (D-11); its yards are shown at wof 320 "
            "and, in brackets, at the default wof 336.", ""]  # fmt: skip
    spec = []
    for key, name in (("qp_border", "Quilter's Paradise"), ("dtq_border", "Designed to Quilt"),
                      ("sewbecca_border", "Sew Becca"), ("qc_border", "Quilt Calculator")):
        spec += [(key, "40", f"{name} 40"), (key, "40-finished", f"{name} 40, finished size")]
    cols = _columns(b, "borders", spec)

    def bord_vec(rid):
        v = cv.BORDER.get(rid)
        if v is None:
            return "no vector"
        return f"{v['vector']}: " + "; ".join(
            f"b{i}: {x['strips']} strips ({mixed(x['length'])} in)"
            for i, x in enumerate(v["bands"], 1)
        )

    def bord_qrep(rid):
        q320 = ctx["qrep_borders"][rid]["wof320"]["borders"]
        q336 = ctx["qrep_borders"][rid]["default"]["borders"]
        return "; ".join(f"b{i}: {mixed(a['yards'])} ({mixed(c['yards'])}), {a['pieces']} pieces"
                         for i, (a, c) in enumerate(zip(q320, q336, strict=True), 1))  # fmt: skip

    out += md_table(
        ["Row", "MATH.md vector", "QREP at wof 320 (wof 336)"] + [h for *_k, h in cols],
        [[rid, bord_vec(rid), bord_qrep(rid), *_calc_cells(b, "borders", rid, cols)]
         for rid, *_r in cv.BORDER_ROWS],
    )  # fmt: skip

    out += ["", "## Piece count spot check", ""]
    out += md_table(
        ["Row", "MATH.md vector", "Quilter's Paradise"],
        [[f"{rid}@{var}", f"{n} pieces ({cite})",
          cell_text("yield", b.cells.get(("yield", f"{rid}@{var}", "qp_piece_count", var)))]
         for rid, var, _label, *_rest, n, cite in YIELD_ROWS],
    )  # fmt: skip

    diffs = [c for c in b.comparisons if c["status"] != "match"]
    order = {p: i for i, p in enumerate(PREFIX.values())}
    diffs.sort(key=lambda c: (order[c["id"].split("-")[0]], int(c["id"].split("-")[1])))
    n_match = sum(c["status"] == "match" for c in b.comparisons)
    tally = {s: sum(c["status"] == s for c in diffs)
             for s in ("explained", "page rule", "unexplained", "record only")}  # fmt: skip
    out += ["", "## Labeled differences", "",
            f"Comparisons: n = {len(b.comparisons)}; matches n = {n_match}; differences "
            f"n = {len(diffs)} (explained by a MATH.md cause n = {tally['explained']}, "
            f"explained only by the page's own rule n = {tally['page rule']}, unexplained "
            f"n = {tally['unexplained']}, record only n = {tally['record only']}).",
            "",
            "Explained means a MATH.md 5.2 cause is shown to account for the difference: the "
            "calculator's MATH.md parameter set (or a page model's proxy set) reproduces the "
            "shown value, the reference set (MATH.md defaults against a vector, today's set "
            "against QREP) gives the target, and switching only the labeled parameters from the "
            "reference set gives the shown value. A layout the page keeps that differs from the "
            "target's is labeled orientation and checked from the target's layout; border yards "
            "against QREP today go through MATH.md's strip set, since today buys by area "
            "(D-11). 'Jointly' marks parameters that act only together. Page rule means the "
            "calculator's own page model in calc_rules reproduces the shown value but no MATH.md "
            "parameter set does; its labels list how that rule differs from the reference, "
            "unproved, and the row is listed for the A1 and A2 owners. Unexplained means no "
            "rule reproduces the shown value or the labels do not reach it.", ""]  # fmt: skip
    out += md_table(
        ["ID", "Row", "Calculator", "Value", "Shown", "Against", "Target", "Status", "Labels",
         "Notes"],
        [(c["id"], c["row"], f"{c['calculator']} @{c['variant']}", c["quantity"],
          fmt_value(c["shown"]), c["against"], fmt_value(c["target"]), c["status"],
          ", ".join(c["labels"]) + (" (jointly)" if c["joint"] else "") or "-",
          "; ".join(c["notes"]) or "-")
         for c in diffs],
    )  # fmt: skip

    out += ["", "## Explained only by the page's own rule, for the A1 and A2 owners", "",
            f"n = {len(b.page_rule)}. The page model reproduces each shown value; the listed "
            "differences of its rule from the reference are not proved to account for the gap.",
            ""]  # fmt: skip
    out += md_table(
        ["ID", "Row", "Calculator", "Value", "Shown", "Against", "Target", "Page rule",
         "Rule differences"],
        [(u["id"], u["row"], f"{u['calculator']} @{u['variant']}", u["quantity"],
          fmt_value(u["shown"]), u["against"], fmt_value(u["target"]), u["rule"] or "-",
          ", ".join(u["labels"]) or "-")
         for u in b.page_rule],
    )  # fmt: skip

    out += ["", "## Unexplained, for the A1 and A2 owners", "",
            f"n = {len(b.unexplained)}. Each lead is the calculator's observed rule where one "
            "is recorded (searches.json, the registry and calc_rules); the vectors and "
            "parameter sets were not changed to match.", ""]  # fmt: skip
    out += md_table(
        ["ID", "Row", "Calculator", "Value", "Shown", "Against", "Target", "Rule gives", "Lead",
         "Notes"],
        [(u["id"], u["row"], f"{u['calculator']} @{u['variant']}", u["quantity"],
          fmt_value(u["shown"]), u["against"], fmt_value(u["target"]), fmt_value(u["rule_value"]),
          u["lead"] or "none recorded", "; ".join(u["notes"]) or "-")
         for u in b.unexplained],
    )  # fmt: skip

    counts = ctx["counts"]
    search = ctx["search"]
    out += ["", "## Calculators per line type (plan section 9, item 13)", "",
            "A calculator counts for a line type when at least one of its rows returned a parsed "
            "value for it.", ""]  # fmt: skip
    out += md_table(
        ["Line type", "MATH.md 5.2 list", "Added", "Total", "Shortfall from four"],
        [(lt, f"n = {c['n_on_list']}: {', '.join(c['on_list']) or 'none'}",
          f"n = {c['n_added']}: {', '.join(c['added']) or 'none'}", f"n = {c['n']}",
          f"n = {c['shortfall_from_four']}") for lt, c in counts.items()],
    )  # fmt: skip
    out += ["", f"### Search summary (searches.json, searched on {search['searched_on']})", "",
            f"Queries n = {search['queries_total']}; qualified pages n = "
            f"{search['qualified_total']}; rejected candidates n = {search['rejected']}.", ""]
    out += md_table(
        ["Line type", "Queries", "Results listed", "Qualified", "Added to the harness"],
        [(lt, f"n = {s['queries']}", f"n = {s['results_listed']}",
          f"n = {s['qualified']}: {', '.join(s['qualified_vendors']) or 'none'}",
          f"n = {len(s['added'])}: {', '.join(s['added']) or 'none'}")
         for lt, s in search["per_line_type"].items()],
    )  # fmt: skip
    if search["qualified_not_driven"]:
        out += ["", f"Qualified but not driven (n = {len(search['qualified_not_driven'])}): "
                + "; ".join(f"{q['vendor']} {q['url']}" for q in search["qualified_not_driven"])
                + "."]  # fmt: skip

    out += ["", "## Failures", "",
            f"n = {len(ctx['failures'])}. A failed record carries the driver's error and its "
            "screenshot; a parse error is a record the driver accepted but the parser refused.",
            ""]  # fmt: skip
    out += md_table(
        ["ID", "Calculator", "Row", "Status", "Error", "Screenshot", "Used in the tables"],
        [(f["id"], f["calculator"], f["row_id"], f["status"], f["error"],
          f["screenshot"] or "none",
          "yes" if f["used"] else f"no: a later record of this row is used ({f['used_status']})")
         for f in ctx["failures"]],
    )  # fmt: skip
    out += ["", "## Not compared", ""]
    nc = ctx["not_compared"]
    out += md_table(
        ["Reason", "Records", "Detail"],
        [(reason, f"n = {len(items)}", "; ".join(items)) for reason, items in nc.items()]
        + ([("planned, no record", f"n = {sum(ctx['not_run'].values())}",
             "; ".join(f"{k} n = {v}" for k, v in ctx["not_run"].items()))]
           if ctx["not_run"] else []),
    )  # fmt: skip
    text = "\n".join(ascii_text(line) for line in out) + "\n"
    bad = [(i, ch) for i, ch in enumerate(text) if ord(ch) > 127]
    if bad:
        i, ch = bad[0]
        raise SystemExit(
            f"baseline.py: the Markdown still holds non-ASCII U+{ord(ch):04X} near "
            f"{text[max(0, i - 40):i].encode('ascii', 'replace')!r}; add it to _ASCII_MAP"
        )
    return text


# ---------------------------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------------------------


_WORK: Path | None = None


def _show_path(path: Path) -> str:
    # The evidence files are public and cite repo paths only (WORKER.md R12), so a
    # local work folder prints as <work> and any other local path by its name alone.
    path = Path(path).resolve()
    try:
        return path.relative_to(REPO.resolve()).as_posix()
    except ValueError:
        pass
    if _WORK is not None:
        try:
            return f"<work>/{path.relative_to(_WORK).as_posix()}"
        except ValueError:
            pass
    return f"<outside the repo>/{path.name}"


def _show_command(argv: list[str]) -> str:
    shown = [_show_path(Path(a)) if ("/" in a or "\\" in a) else a for a in argv]
    return shlex.join([".venv/Scripts/python", *shown])


def _template(job: Job) -> dict:
    subs = {dec(job.width): "W", dec(job.length): "L"}
    subs.update({dec(b): f"b{i}" for i, b in enumerate(job.bands, 1)})
    if job.calculator == "qp_piece_count":
        subs = {}
    return {k: subs.get(v, v) for k, v in job.inputs.items()}


def calculator_rows(plan: list[Job], driver_keys: set[str] | None) -> list[dict]:
    rows = []
    for calc in REGISTRY.values():
        typed = []
        for job in plan:
            if job.calculator != calc.key or not job.applicable:
                continue
            if calc.key != "qp_piece_count" and any(x.startswith(f"@{job.variant}: ")
                                                    for x in typed):  # fmt: skip
                continue
            inner = ", ".join(f"{k} {v}" for k, v in _template(job).items())
            typed.append(f"@{job.variant}: {inner}")
        parser = parser_for(calc)
        status = f"calc_parse.{calc.parser}" if parser else f"parser missing ({calc.parser})"
        rules = [f"{lt}: {name}" for lt, name in calc.rules.items()
                 if rule_set(lt, name) is not None]  # fmt: skip
        models = sorted({f"calc_rules.{m.fn}" for m in calc.models.values()})
        rows.append(
            {
                "key": calc.key,
                "vendor": calc.vendor,
                "page": calc.page,
                "url": calc.url,
                "accessed": LIST_DATE if calc.on_list else _accessed(calc.url),
                "line_types": list(calc.line_types),
                "on_list": calc.on_list,
                "record_only": calc.record_only,
                "inputs_typed": typed,
                "fixed": calc.fixed,
                "parser": calc.parser,
                "parser_status": status,
                "rule": "; ".join(rules + models) or None,
                "rule_source": calc.rule_source or None,
                "driver_known": None if driver_keys is None else calc.key in driver_keys,
            }
        )
    return rows


def _accessed(url: str) -> str | None:
    data = json.loads(SEARCHES.read_text(encoding="utf-8"))
    for q in data["qualified"]:
        if _norm_url(q["url"]) == _norm_url(url):
            return q.get("accessed")
    return None


def parse_args(argv):
    ap = argparse.ArgumentParser(
        description="Build the D2 calculator conformance baseline from driven or saved records."
    )
    ap.add_argument("--start-sha", required=True, help="the engine under test (plan 4.4)")
    ap.add_argument("--work", required=True, type=Path, help="folder for jobs.json and raw.json")
    ap.add_argument("--out-json", required=True, type=Path)
    ap.add_argument("--out-md", required=True, type=Path)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--raw", type=Path, action="append",
                     help="saved drive.mjs record file; repeat to merge several")  # fmt: skip
    src.add_argument("--drive", action="store_true", help="run drive.mjs on the jobs first")
    ap.add_argument("--shots", type=Path,
                    help="screenshot folder (required with --drive; with --raw the default is the "
                         "raw file's sibling shots<suffix> folder)")  # fmt: skip
    ap.add_argument("--finished-size", action="append", default=[], metavar="CALCULATOR",
                    choices=sorted(BORDER_SIZE_BASIS),
                    help="type the finished size instead of the center into this border "
                         "calculator")  # fmt: skip
    args = ap.parse_args(argv)
    if args.drive and args.shots is None:
        ap.error("--drive needs --shots")
    return args


def _shots_for(raw_path: Path, given: Path | None) -> Path | None:
    if given is not None:
        return given
    m = re.fullmatch(r"raw(.*)", raw_path.stem)
    cand = raw_path.parent / f"shots{m.group(1) if m else ''}"
    return cand if cand.is_dir() else None


def main(argv=None) -> int:
    if os.environ.get("CI"):
        print("baseline.py: refusing to run because CI is set. The calculator baseline drives "
              "third-party websites and runs only by hand.", file=sys.stderr)  # fmt: skip
        return 1
    args = parse_args(argv)
    global _WORK
    _WORK = Path(args.work).resolve()
    import calc_qrep

    # Provenance first: a checkout whose qrep/ is not the start SHA's must not be measured.
    engine = calc_qrep.engine_provenance(args.start_sha)
    import cv2

    basis = dict(BORDER_SIZE_BASIS)
    for key in args.finished_size:
        basis[key] = "finished"
    plan = all_jobs(basis)
    universe = all_jobs(basis, both_bases=True)
    driver_keys, _probes = driver_calculators()
    drivable = [j for j in plan if driver_keys is None or j.calculator in driver_keys]
    args.work.mkdir(parents=True, exist_ok=True)
    jobs_file = args.work / "jobs.json"
    with open(jobs_file, "w", encoding="ascii", newline="\n") as fh:
        json.dump([j.as_driver_job() for j in drivable], fh, ensure_ascii=True, indent=1)
        fh.write("\n")

    driver_command = None
    if args.drive:
        raw_paths = [args.work / "raw.json"]
        cmd = ["node", _show_path(DRIVER), "--jobs", str(jobs_file), "--out", str(raw_paths[0]),
               "--shots", str(args.shots)]  # fmt: skip
        driver_command = shlex.join(
            [cmd[0], cmd[1], *(_show_path(Path(a)) if i % 2 else a for i, a in enumerate(cmd[2:]))]
        )
        done = subprocess.run(cmd, cwd=REPO, check=False)
        if done.returncode != 0:
            print(f"baseline.py: drive.mjs exited with {done.returncode}; no report written",
                  file=sys.stderr)  # fmt: skip
            return done.returncode or 1
    else:
        raw_paths = args.raw

    by_id = {(j.calculator, j.row_id): j for j in universe}
    recs: list[Rec] = []
    raw_files = []
    for raw_path in raw_paths:
        records = json.loads(Path(raw_path).read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise SystemExit(f"baseline.py: {raw_path} does not hold a record list")
        shots = args.shots if args.drive else _shots_for(Path(raw_path), args.shots)
        raw_files.append({"path": _show_path(raw_path), "records": len(records),
                          "shots": _show_path(shots) if shots else None})  # fmt: skip
        for raw in records:
            job, how = match_job(raw, universe, by_id)
            rec = process(raw, job, how)
            rec.source, rec.shots = _show_path(raw_path), shots
            recs.append(rec)
    failures = []
    for rec in recs:
        if rec.status in FAILED:
            rec.failure_id = f"F{len(failures) + 1}"
            shot = rec.raw.get("screenshot")
            shot_path = None
            if shot:
                shot_path = _show_path(rec.shots / shot) if rec.shots else shot
            failures.append({
                "id": rec.failure_id,
                "calculator": rec.raw.get("calculator"),
                "row_id": rec.job.row_id if rec.job else rec.raw.get("row_id"),
                "status": rec.status,
                "error": ascii_text(rec.detail or ""),
                "screenshot": shot_path if shot else (
                    "none (the driver saw no error)" if rec.status == "parse error" else None),
                "source": rec.source,
            })  # fmt: skip
    picked = pick_records(recs)
    by_failure = {r.failure_id: r for r in recs if r.failure_id}
    for f in failures:
        rec = by_failure[f["id"]]
        used = picked.get((rec.job.calculator, rec.job.row_id)) if rec.job else None
        f["used"] = used is rec
        f["used_status"] = used.status if used is not None else None
        # Third-party page crops are published only where they document a failure that
        # stands; a row a later record answered keeps its error text, not its image.
        if not f["used"] and f["used_status"] == "ok" and f["screenshot"]:
            f["screenshot"] = "not kept: a later record of this row returned values"

    qrep, qrep_borders = qrep_tables(calc_qrep)
    builder = Builder(picked, universe, qrep, qrep_borders, calculator_leads()).run()
    cov = coverage(plan, universe, picked)
    counts = line_counts(cov)
    stamps = sorted(r.raw["timestamp"] for r in recs if r.raw.get("timestamp"))
    not_compared: dict[str, list[str]] = {}
    for rec in recs:
        if rec.status in ("parser missing", "not applicable", "unmatched", "no value"):
            label = rec.job.row_id if rec.job else str(rec.raw.get("row_id"))
            not_compared.setdefault(rec.status, []).append(f"{rec.raw.get('calculator')} {label}")
    not_run = [f"{j.calculator} {j.row_id}" for j in plan
               if j.applicable and (j.calculator, j.row_id) not in picked]  # fmt: skip
    not_run_by_calc = {
        k: sum(x.startswith(k + " ") for x in not_run)
        for k in REGISTRY
        if any(x.startswith(k + " ") for x in not_run)
    }

    provenance = {
        "date": date.today().isoformat(),
        "command": _show_command(sys.argv),
        "driver_command": driver_command,
        "qrep_file": engine["qrep_file"],
        "head": engine["head"],
        "harness_tree": engine["harness_tree"],
        "harness_uncommitted": engine["harness_uncommitted"],
        "start_sha": engine["start_sha"],
        "start_sha_arg": args.start_sha,
        "qrep_tree": engine["qrep_tree"],
        "cv2": cv2.__version__,
        "decode_path": "not applicable (no images decoded)",
        "python": sys.version.split()[0],
        "raw_files": raw_files,
        "jobs_file": _show_path(jobs_file),
        "jobs_written": len(drivable),
        "jobs_planned": len(plan),
        "calculator_runs": {"first": stamps[0] if stamps else None,
                            "last": stamps[-1] if stamps else None},  # fmt: skip
        "border_size_basis": basis,
    }
    calculators = calculator_rows(plan, driver_keys)
    ctx = {
        "provenance": provenance,
        "builder": builder,
        "calculators": calculators,
        "coverage": cov,
        "counts": counts,
        "search": search_summary(),
        "failures": failures,
        "not_compared": not_compared,
        "not_run": not_run_by_calc,
        "qrep": qrep,
        "qrep_borders": qrep_borders,
    }
    markdown = render(ctx)

    doc = {
        "provenance": provenance,
        "inputs": {
            "matrix": [{"row_id": r, "label": lb, "width": w, "length": ln}
                       for r, lb, w, ln in cv.MATRIX],
            "border_rows": [{"row_id": r, "label": lb, "center": [cw, cl], "bands": list(bs)}
                            for r, lb, cw, cl, bs in cv.BORDER_ROWS],
            "piece_count_rows": [{"row_id": f"{r}@{v}", "label": lb, "expected": n, "source": c}
                                 for r, v, lb, *_x, n, c in YIELD_ROWS],
        },  # fmt: skip
        "calculators": calculators,
        "jobs": [j.as_driver_job() for j in plan],
        "records": [
            {
                "calculator": rec.raw.get("calculator"),
                "url": rec.raw.get("url"),
                "row_id": rec.raw.get("row_id"),
                "job_row_id": rec.job.row_id if rec.job else None,
                "matched_by": rec.matched_by,
                "source": rec.source,
                "inputs": rec.raw.get("inputs"),
                "held": rec.raw.get("held"),
                "displayed": rec.displayed,
                "parsed": num(rec.values) if rec.values else None,
                "timestamp": rec.raw.get("timestamp"),
                "status": rec.status,
                "error": rec.detail if rec.status in FAILED else rec.raw.get("error"),
                "skipped": rec.raw.get("skipped"),
                "screenshot": rec.raw.get("screenshot"),
                "failure_id": rec.failure_id,
            }
            for rec in recs
        ],
        "qrep": {"matrix": qrep, "borders": qrep_borders},
        "vectors": {
            rid: {
                "backing_b42": cv.BACKING_B42.get(rid),
                "backing_b40": cv.BACKING_B40.get(rid),
                "backing_policy": cv.BACKING_POLICY.get(rid),
                "wide": cv.WIDE.get(rid),
                "binding_u40": cv.BINDING_U40.get(rid),
                "binding_u42": cv.BINDING_U42.get(rid),
                "batting": cv.BATTING.get(rid),
            }
            for rid, *_r in cv.MATRIX
        }
        | {f"border:{rid}": cv.BORDER.get(rid) for rid, *_r in cv.BORDER_ROWS},
        "comparisons": [{k: num(v) if k in ("shown", "target", "rule_value") else v
                         for k, v in c.items()} for c in builder.comparisons],
        "coverage": cov,
        "counts": counts,
        "search_summary": ctx["search"],
        "unexplained": [{k: num(v) if k in ("shown", "target", "rule_value") else v
                         for k, v in u.items()} for u in builder.unexplained],
        "page_rule_only": [{k: num(v) if k in ("shown", "target", "rule_value") else v
                            for k, v in u.items()} for u in builder.page_rule],
        "failures": failures,
        "not_compared": not_compared,
        "not_run": not_run_by_calc,
    }  # fmt: skip
    for path in (args.out_json, args.out_md):
        path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_json, "w", encoding="ascii", newline="\n") as fh:
        json.dump(jsonable(doc), fh, ensure_ascii=True, indent=1)
        fh.write("\n")
    with open(args.out_md, "w", encoding="ascii", newline="\n") as fh:
        fh.write(markdown)
    print(f"baseline.py: {len(recs)} record(s), {len(builder.comparisons)} comparison(s), "
          f"{len(builder.page_rule)} page rule only, {len(builder.unexplained)} unexplained -> "
          f"{args.out_json}, {args.out_md}")  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
