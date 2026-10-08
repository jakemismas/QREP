"""D2 calculator harness: parsers for displayed calculator output, and the MATH.md rules.

Expected values come from MATH.md's hand arithmetic (cited by vector id and line of
docs/sprint-5/MATH.md) or from hand arithmetic written beside the case. None comes from running
QREP or a calculator (MATH.md rule 3). Fragments are hand-written in the shape each page writes;
no saved third-party page is used.
"""

import sys
from fractions import Fraction as F
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "eval" / "calculators"))

import pytest  # noqa: E402

import calc_parse as cp  # noqa: E402
import calc_rules as cr  # noqa: E402
import calc_vectors as cv  # noqa: E402

# ---------------------------------------------------------------------------------------------
# html_text
# ---------------------------------------------------------------------------------------------


def test_html_text_turns_br_into_newlines():
    assert cp.html_text("a<br>b<br/>c<BR >d") == "a\nb\nc\nd"


def test_html_text_decodes_entities_and_nbsp():
    # &nbsp; is U+00A0 once decoded; it counts as a space and collapses with its neighbours.
    assert cp.html_text("&nbsp;3/8&nbsp;&nbsp;yd&nbsp;") == "3/8 yd"
    assert cp.html_text("9 strips needed (360&quot; total length)") == (
        '9 strips needed (360" total length)'
    )


def test_html_text_collapses_whitespace_per_line_and_strips():
    # A source newline is HTML whitespace, not a line break; only <br> breaks the line.
    assert cp.html_text("  <span> 9 \n  strips </span>  <br>   needed  ") == "9 strips\nneeded"


def test_html_text_drops_script_content():
    assert cp.html_text("<script>var x = 1;</script>4 Yards") == "4 Yards"


# ---------------------------------------------------------------------------------------------
# parse_yards
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("8 3/8", F(67, 8)),  # 8 + 3/8 = 67/8 yd
        (" 3/8", F(3, 8)),  # leading space: no whole part, 3/8 yd
        ("8 ", F(8)),  # trailing space: whole yards only
        ("3/4", F(3, 4)),
        ("5 1/3", F(16, 3)),  # 5 + 1/3 = 16/3 yd
        ("9 2/3", F(29, 3)),  # 9 + 2/3 = 29/3 yd
        ("4", F(4)),
        ("4 Yards + 9 Inches", F(17, 4)),  # 4 + 9/36 = 4 + 1/4 = 17/4 yd
        ("1 Yard", F(1)),
        ("27 Inches", F(3, 4)),  # 27/36 = 3/4 yd
        ("1 Inch", F(1, 36)),  # 1/36 yd
        ("2 Yards", F(2)),
        ("5 Yards + 27 Inches", F(23, 4)),  # 5 + 27/36 = 5 + 3/4 = 23/4 yd
        ("\xa08 3/8\xa0", F(67, 8)),  # a decoded &nbsp; on both sides is whitespace
        ("  8   3/8  ", F(67, 8)),  # runs of spaces collapse
    ],
)
def test_parse_yards_forms(text, expected):
    assert cp.parse_yards(text) == expected


def test_parse_yards_after_html_text_with_nbsp():
    # "&nbsp;3/8" decodes to " 3/8": 3/8 yd.
    assert cp.parse_yards(cp.html_text("&nbsp;3/8")) == F(3, 8)


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "N/A",
        "n/a",
        "-",
        "--",
        "\u2013",
        "\u2014",
        "NaN",
        "8 3/0",  # zero denominator
        "eight",
        "3/8/2",
        "8.5",  # these pages print fractions; a decimal means the output shape changed
        "4 Yards +",
        "+ 9 Inches",
        "8 3/8 yd",
    ],
)
def test_parse_yards_rejects(text):
    with pytest.raises(ValueError):
        cp.parse_yards(text)


# ---------------------------------------------------------------------------------------------
# parse_decimal_inches and parse_count
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("301.5", F(603, 2)),  # 301 1/2 in = 603/2
        ("12", F(12)),
        ("24.125", F(193, 8)),  # 24 + 1/8 = 193/8
        (" 83.5 ", F(167, 2)),  # surrounding spaces are not part of the number
        # Float noise: JS prints the shortest decimal that round-trips the double, so binary error
        # shows. 116 / 36 x 3 x 36 (the king's 9 2/3 yd back in inches) prints as
        # 348.00000000000006, 6e-14 from 348.000, inside 1e-9, so it snaps to 348.
        ("348.00000000000006", F(348)),
        ("300.00000000000006", F(300)),  # 6e-14 from 300.000
        ("0.30000000000000004", F(3, 10)),  # 0.1 x 3 in doubles; 4e-17 from 0.300
        # 12.3456 is 4e-4 from 12.346, far outside 1e-9: a real value, kept exactly.
        ("12.3456", F(123456, 10000)),
    ],
)
def test_parse_decimal_inches(text, expected):
    assert cp.parse_decimal_inches(text) == expected


@pytest.mark.parametrize(
    "text", ["", "N/A", "-", chr(0x2014), "12,5", "1e3", ".5", "12.", "-3", "abc"]
)
def test_parse_decimal_inches_rejects(text):
    with pytest.raises(ValueError):
        cp.parse_decimal_inches(text)


def test_parse_count():
    assert cp.parse_count(" 10 ") == 10
    for bad in ("", "N/A", "-", "2.5", "ten"):
        with pytest.raises(ValueError):
            cp.parse_count(bad)


# ---------------------------------------------------------------------------------------------
# parse_qp_backing
# ---------------------------------------------------------------------------------------------


def test_parse_qp_backing_mixed_yards():
    html = (
        "8 3/8 (301.5 inches) when width is 100.5 and length is 123<br>"
        "2 seam(s) will be needed."
    )
    # "8 3/8" yd = 8 + 3/8 = 67/8 yd; 67/8 x 36 = 301 1/2 in, the same as the inches shown.
    assert cp.parse_qp_backing(html) == {
        "yards": F(67, 8),
        "inches": F(603, 2),
        "width": F(201, 2),  # 100.5 = 201/2
        "length": F(123),
        "seams": 2,
    }


def test_parse_qp_backing_leading_space_yards():
    html = " 3/8 (13.5 inches) when width is 40 and length is 5.5<br>0 seam(s) will be needed."
    # " 3/8" yd = 3/8 yd; 3/8 x 36 = 13 1/2 in.
    got = cp.parse_qp_backing(html)
    assert got["yards"] == F(3, 8)
    assert got["inches"] == F(27, 2)
    assert got["length"] == F(11, 2)  # 5.5 = 11/2
    assert got["seams"] == 0


def test_parse_qp_backing_trailing_space_yards_and_nbsp():
    html = "8&nbsp; (288 inches) when width is 42 and length is 280<br>1 seam(s) will be needed."
    # "8 " yd = 8 yd; 8 x 36 = 288 in.
    got = cp.parse_qp_backing(html)
    assert got["yards"] == F(8)
    assert got["inches"] == F(288)
    assert got["width"] == F(42)
    assert got["seams"] == 1


def test_parse_qp_backing_float_noise_inches():
    html = (
        "8 1/3 (300.00000000000006 inches) when width is 84 and length is 92<br>"
        "2 seam(s) will be needed."
    )
    # 8 1/3 yd x 36 = 300 in; the JS noise 6e-14 snaps to 300.
    got = cp.parse_qp_backing(html)
    assert got["yards"] == F(25, 3)  # 8 + 1/3 = 25/3
    assert got["inches"] == F(300)


@pytest.mark.parametrize(
    "html",
    [
        "",
        "N/A (0 inches) when width is 42 and length is 50<br>0 seam(s) will be needed.",
        "8 3/8 (301.5 inches) when width is 100.5 and length is 123",  # no seam line
        "8 3/8 inches when width is 100.5 and length is 123<br>2 seam(s) will be needed.",
        "8 3/8 (301.5 inches) when width is wide and length is 123<br>2 seam(s) will be needed.",
    ],
)
def test_parse_qp_backing_rejects(html):
    with pytest.raises(ValueError):
        cp.parse_qp_backing(html)


# ---------------------------------------------------------------------------------------------
# parse_qp_binding
# ---------------------------------------------------------------------------------------------


def test_parse_qp_binding():
    # Fixture 75 x 90 at 40 in: T = 2 (75 + 90) + 10 = 340 in; ceil(340 / 37.5) = 10 strips;
    # " 3/4" yd = 3/4 yd.
    html_by_id = {"binding length": "340", "yardage": " 3/4", "number strips": "10"}
    assert cp.parse_qp_binding(html_by_id) == {
        "binding_length": F(340),
        "yards": F(3, 4),
        "strips": 10,
    }


def test_parse_qp_binding_mixed_yards():
    # "1 1/8" yd = 1 + 1/8 = 9/8 yd; 425.5 in = 851/2.
    html_by_id = {"binding length": "425.5", "yardage": "1 1/8", "number strips": "<b>12</b>"}
    assert cp.parse_qp_binding(html_by_id) == {
        "binding_length": F(851, 2),
        "yards": F(9, 8),
        "strips": 12,
    }


def test_parse_qp_binding_rejects():
    with pytest.raises(ValueError):
        cp.parse_qp_binding({"binding length": "340", "yardage": " 3/4"})  # no strip count
    with pytest.raises(ValueError):
        cp.parse_qp_binding({"binding length": "340", "yardage": "N/A", "number strips": "10"})


# ---------------------------------------------------------------------------------------------
# parse_qp_border
# ---------------------------------------------------------------------------------------------


def test_parse_qp_border_two_bands():
    # Shaped like V-BORD-03 (center 60 x 72, bands 2 then 5) under QP's pooled count at 40 in:
    # band 1 pools 2 x 72 + 2 x (60 + 4) = 272 in, ceil(272 / 39.5) = 7 strips of 2 1/2 in,
    # 17.5 in = 1/2 yd; band 2 pools 2 x 76 + 2 x (64 + 10) = 300 in, ceil(300 / 39.5) = 8 strips
    # of 5 1/2 in, 44 in = 1 1/4 yd; overall 60 + 4 + 10 = 74 by 72 + 4 + 10 = 86.
    html_by_id = {
        "StripWidth1": "2.5",
        "Border1Yardage": " 1/2",
        "NumStrips1": "7",
        "StripWidth2": "5.5",
        "Border2Yardage": "1 1/4",
        "NumStrips2": "8",
        "OverallWidth": "74",
        "OverallLength": "86",
    }
    assert cp.parse_qp_border(html_by_id, 2) == {
        "bands": [
            {"strip_width": F(5, 2), "yards": F(1, 2), "strips": 7},
            {"strip_width": F(11, 2), "yards": F(5, 4), "strips": 8},
        ],
        "overall_width": F(74),
        "overall_length": F(86),
    }


def test_parse_qp_border_rejects():
    one_band = {
        "StripWidth1": "4.25",
        "Border1Yardage": "1",
        "NumStrips1": "8",
        "OverallWidth": "75",
        "OverallLength": "90",
    }
    assert cp.parse_qp_border(one_band, 1)["bands"][0]["strip_width"] == F(17, 4)  # 4 1/4 in
    with pytest.raises(ValueError):
        cp.parse_qp_border(one_band, 2)  # band 2 ids are missing
    with pytest.raises(ValueError):
        cp.parse_qp_border(one_band, 0)


# ---------------------------------------------------------------------------------------------
# parse_nqc
# ---------------------------------------------------------------------------------------------


def test_parse_nqc():
    # Shaped like 60 x 72 at 40 in: binding T = 2 (60 + 72) + 12 = 276 in, ceil(276 / 40) = 7
    # strips, 7 x 40 = 280 in total; 7 x 2 1/2 = 17.5 in rounds to 18 in = 1/2 yd.
    # Backing vertical 2 panels (2 x 40 - 1/2 = 79.5 in across): "4 Yards + 18 Inches"
    # = 4 + 18/36 = 4 1/2 yd; horizontal 3 panels (3 x 40 - 1 = 119 in): "5 Yards + 27 Inches"
    # = 5 + 27/36 = 5 3/4 yd.
    html_by_id = {
        "bindingValue": "18 Inches",
        "bindingDetails": "7 strips needed (280&quot; total length)",
        "verticalBacking": "4 Yards + 18 Inches",
        "verticalPanels": "2",
        "verticalCoverage": "79.5&quot;",
        "horizontalBacking": "5 Yards + 27 Inches",
        "horizontalPanels": "3",
        "horizontalCoverage": '119.0"',
    }
    assert cp.parse_nqc(html_by_id) == {
        "binding": {"yards": F(1, 2), "strips": 7, "total_length": F(280)},
        "vertical": {"yards": F(9, 2), "panels": 2, "coverage": F(159, 2)},
        "horizontal": {"yards": F(23, 4), "panels": 3, "coverage": F(119)},
    }


def test_parse_nqc_singular_strip_and_whole_yards():
    html_by_id = {
        "bindingValue": "9 Inches",  # 9/36 = 1/4 yd
        "bindingDetails": '1 strip needed (40" total length)',
        "verticalBacking": "1 Yard",
        "verticalPanels": "1",
        "verticalCoverage": '108.0"',
        "horizontalBacking": "2 Yards",
        "horizontalPanels": "1",
        "horizontalCoverage": '108.0"',
    }
    got = cp.parse_nqc(html_by_id)
    assert got["binding"] == {"yards": F(1, 4), "strips": 1, "total_length": F(40)}
    assert got["vertical"] == {"yards": F(1), "panels": 1, "coverage": F(108)}
    assert got["horizontal"]["yards"] == F(2)


def test_parse_nqc_rejects():
    good = {
        "bindingValue": "1 Yard",
        "bindingDetails": '9 strips needed (360" total length)',
        "verticalBacking": "4 Yards + 9 Inches",
        "verticalPanels": "2",
        "verticalCoverage": '79.5"',
        "horizontalBacking": "5 Yards",
        "horizontalPanels": "3",
        "horizontalCoverage": '119.0"',
    }
    assert cp.parse_nqc(good)["binding"]["total_length"] == F(360)
    for key, bad in (
        ("bindingDetails", "9 strips (360 total length)"),
        ("verticalCoverage", "79.5"),  # no inch mark
        ("horizontalBacking", "N/A"),
        ("verticalPanels", "-"),
    ):
        with pytest.raises(ValueError):
            cp.parse_nqc({**good, key: bad})
    missing = dict(good)
    del missing["horizontalCoverage"]
    with pytest.raises(ValueError):
        cp.parse_nqc(missing)


# ---------------------------------------------------------------------------------------------
# calc_vectors structure
# ---------------------------------------------------------------------------------------------

ROW_IDS = [row[0] for row in cv.MATRIX]


def test_matrix_rows():
    assert ROW_IDS == [
        "36x52", "50x65", "60x72", "70x90", "84x90", "90x108", "92.5x115", "110x108",
        "75x90", "42x52", "76x85", "68x68", "102.5x120", "58x66", "24x58",
    ]  # fmt: skip
    assert dict((r[0], (r[2], r[3])) for r in cv.MATRIX)["92.5x115"] == (F(185, 2), F(115))


@pytest.mark.parametrize(
    "table",
    ["BACKING_B42", "BACKING_B40", "BACKING_POLICY", "WIDE", "BINDING_U40", "BINDING_U42",
     "BATTING"],
)  # fmt: skip
def test_every_matrix_row_is_explicit(table):
    # A missing size must be an explicit None, so the report prints "no vector" instead of
    # silently skipping a row.
    assert list(getattr(cv, table)) == ROW_IDS


def test_border_rows():
    ids = [row[0] for row in cv.BORDER_ROWS]
    assert ids == [f"{r}-b3.75" for r in ROW_IDS] + ["V-BORD-02", "V-BORD-03", "V-BORD-04"]
    assert list(cv.BORDER) == ids
    fixture = dict((row[0], row) for row in cv.BORDER_ROWS)["75x90-b3.75"]
    # 75 - 7 1/2 = 67 1/2 and 90 - 7 1/2 = 82 1/2: the V-BORD-01 center.
    assert fixture[2:] == (F(135, 2), F(165, 2), (F(15, 4),))


# ---------------------------------------------------------------------------------------------
# Rules: unit vectors
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("d", "b", "n"),
    [
        # V-UNIT-03, MATH.md lines 539 to 549, n(D) = 1 if D <= B else ceil((D - 8) / (B - 8)) e
        (F(42), 42, 1),  # line 541: n(336) = 1
        (F(337, 8), 42, 2),  # line 542: ceil(329 / 328) = 2
        (F(83), 42, 2),  # line 543: ceil(656 / 328) = 2 exactly
        (F(665, 8), 42, 3),  # line 544: ceil(657 / 328) = 3
        (F(124), 42, 3),  # line 545: ceil(984 / 328) = 3 exactly
        (F(993, 8), 42, 4),  # line 546: ceil(985 / 328) = 4
        (F(40), 40, 1),  # line 548: n(320) = 1
        (F(321, 8), 40, 2),  # line 548: n(321) = 2
        (F(79), 40, 2),  # line 548: ceil(624 / 312) = 2
        (F(633, 8), 40, 3),  # line 548: n(633) = 3
        (F(118), 40, 3),  # line 549: ceil(936 / 312) = 3
        (F(945, 8), 40, 4),  # line 549: n(945) = 4
    ],
)
def test_panels_v_unit_03(d, b, n):
    assert cr.panels(d, b, 1) == n


def test_panels_v_unit_06():
    # V-UNIT-06, MATH.md line 562: B = 43, no overhang.
    assert cr.panels(52, 43, 1) == 2  # ceil(408 / 336) = 2
    assert cr.panels(96, 43, 1) == 3  # ceil(760 / 336) = 3


def test_panels_other_seam_rules():
    # Seam blind (s = 0, today's D-01/D-02): n = ceil(D / B).
    assert cr.panels(98, 42, 0) == 3  # ceil(98 / 42) = ceil(2.33) = 3
    assert cr.panels(84, 42, 0) == 2  # 84 / 42 = 2 exactly: the D-02 76 x 85 case
    # Nebraska (s = 1/2): ceil((D - 1/2) / (B - 1/2)).
    assert cr.panels(80, 40, F(1, 2)) == 3  # ceil(79.5 / 39.5) = ceil(2.013) = 3
    assert cr.panels(F(159, 2), 40, F(1, 2)) == 2  # 79.5: ceil(79 / 39.5) = 2 exactly
    with pytest.raises(ValueError):
        cr.panels(80, 1, 1)  # s >= B never covers anything
    with pytest.raises(ValueError):
        cr.panels(F(1, 3), 42, 1)  # not a whole number of eighths


@pytest.mark.parametrize(
    ("lp", "k"),
    [
        # V-UNIT-04, MATH.md lines 551 to 555, k = 1 if Lp <= 320 e else ceil((Lp - 4) / 316)
        (F(40), 1),  # line 552: k(320) = 1
        (F(321, 8), 2),  # line 553: ceil(317 / 316) = 2
        (F(159, 2), 2),  # line 554: ceil(632 / 316) = 2 exactly (79 1/2 in)
        (F(637, 8), 3),  # line 555: ceil(633 / 316) = 3
    ],
)
def test_border_join_count_v_unit_04(lp, k):
    assert cr.border_join_count(lp, U=40) == k


# ---------------------------------------------------------------------------------------------
# Rules at MATH.md defaults against the transcribed vectors
# ---------------------------------------------------------------------------------------------


def _vector_rows(table):
    """Matrix rows that have a vector, with the vector id and MATH.md line in the test id."""
    rows = []
    for row_id, _label, w, length in cv.MATRIX:
        vec = table[row_id]
        if vec is not None:
            rows.append(
                pytest.param(w, length, vec, id=f"{row_id}-{vec['vector']}-L{vec['line']}")
            )
    return rows


def _check_backing(got, vec):
    assert got["kept"] == vec["kept"]
    for key in ("panels", "panel_length", "raw", "total", "yards"):
        assert got[key] == vec[key], key


@pytest.mark.parametrize(("w", "length", "vec"), _vector_rows(cv.BACKING_B42))
def test_backing_b42_vectors(w, length, vec):
    _check_backing(cr.backing(w, length, **cr.BACKING_SETS["math"]), vec)


@pytest.mark.parametrize(("w", "length", "vec"), _vector_rows(cv.BACKING_B40))
def test_backing_b40_vectors(w, length, vec):
    # V-BACK-18 to V-BACK-20: the MATH.md rule with B configured to 40 in.
    _check_backing(cr.backing(w, length, **{**cr.BACKING_SETS["math"], "B": 40}), vec)


@pytest.mark.parametrize(("w", "length", "vec"), _vector_rows(cv.BACKING_POLICY))
@pytest.mark.parametrize("column", ["A", "B", "C", "D"])
def test_backing_policy_columns(w, length, vec, column):
    # MATH.md section 4.4 policy table, lines 958 to 977: A default, B 1/8 yd, C no allowance,
    # D no allowance and 1/8 yd.
    params = {**cr.BACKING_SETS["math"], **cv.POLICY_COLUMNS[column]}
    assert cr.backing(w, length, **params)["yards"] == vec[column]


def _wide_rows():
    """Wide-back rows paired with their pieced panel count from the backing vector (F11 shows
    the line only when the pieced backing needs two or more panels)."""
    rows = []
    for row_id, _label, w, length in cv.MATRIX:
        vec = cv.WIDE[row_id]
        if vec is not None:
            pieced = cv.BACKING_B42[row_id]["panels"]
            rows.append(
                pytest.param(
                    w, length, pieced, vec, id=f"{row_id}-{vec['vector']}-L{vec['line']}"
                )
            )
    return rows


@pytest.mark.parametrize(("w", "length", "pieced", "vec"), _wide_rows())
def test_wide_back_vectors(w, length, pieced, vec):
    for key, bw in (("bw108", 108), ("bw118", 118)):
        if key not in vec:
            continue
        got = cr.wide_back(
            w,
            length,
            BW=bw,
            overhang_per_side=4,
            allowance=F(9, 2),
            increment="quarter",
            pieced_panels=pieced,
        )
        if vec[key] is None:
            assert got is None, key
        else:
            for field in ("length", "total", "yards"):
                assert got[field] == vec[key][field], (key, field)


def test_wide_back_omitted_for_one_panel():
    # V-WIDE-07, MATH.md line 1009: 28 x 28 backs with one panel (V-BACK-12, line 883: Wb = Lb
    # = 36 in <= 42), so there is no wide-back line.
    back = cr.backing(28, 28, **cr.BACKING_SETS["math"])
    assert back["panels"] == 1
    assert back["total"] == F(81, 2)  # 36 + 4 1/2 = 40 1/2 in
    assert back["yards"] == F(5, 4)  # ceil(324 / 72) = 5 qy
    got = cr.wide_back(
        28, 28, BW=108, overhang_per_side=4, allowance=F(9, 2), increment="quarter",
        pieced_panels=back["panels"],
    )  # fmt: skip
    assert got is None


@pytest.mark.parametrize(("w", "length", "vec"), _vector_rows(cv.BINDING_U40))
def test_binding_u40_vectors(w, length, vec):
    got = cr.binding(w, length, **cr.BINDING_SETS["math"])
    for key in ("binding_length", "strips", "length", "yards"):
        assert got[key] == vec[key], key


@pytest.mark.parametrize(("w", "length", "vec"), _vector_rows(cv.BINDING_U42))
def test_binding_u42_vectors(w, length, vec):
    # V-BIND-09: the MATH.md rule with U configured to 42 in.
    got = cr.binding(w, length, **{**cr.BINDING_SETS["math"], "U": 42})
    for key in ("binding_length", "strips", "length", "yards"):
        assert got[key] == vec[key], key


@pytest.mark.parametrize(("w", "length", "vec"), _vector_rows(cv.BATTING))
def test_batting_vectors(w, length, vec):
    got = cr.batting(w, length, overhang_per_side=4)
    assert (got["width"], got["length"]) == (vec["width"], vec["length"])
    assert got["package"] == vec["package"]
    if vec["package"] is None:
        # V-BATT-10, MATH.md line 1044: the printed text when no package covers the batting.
        assert got["label"] == "larger than a king package (124 x 120 in)"


def test_batting_turned_v_batt_08():
    # V-BATT-08, MATH.md line 1041: 100 1/2 x 123 misses king upright (123 > 120) and fits it
    # turned (100.5 <= 120, 123 <= 124).
    got = cr.batting(F(185, 2), 115, overhang_per_side=4)
    assert got["package"] == "king"
    assert got["turned"] is True
    assert got["label"] == "king 124 x 120"


def _border_rows():
    rows = []
    for row_id, _label, cw, cl, bands in cv.BORDER_ROWS:
        vec = cv.BORDER[row_id]
        if vec is not None:
            rows.append(
                pytest.param(cw, cl, bands, vec, id=f"{row_id}-{vec['vector']}-L{vec['line']}")
            )
    return rows


BAND_KEYS = (
    "strip_width", "side_length", "side_strips", "top_length", "top_strips", "strips", "length",
)  # fmt: skip


@pytest.mark.parametrize(("cw", "cl", "bands", "vec"), _border_rows())
def test_border_vectors(cw, cl, bands, vec):
    got = cr.border(cw, cl, bands, U=40, rule="per_piece")
    assert len(got["bands"]) == len(vec["bands"])
    for got_band, vec_band in zip(got["bands"], vec["bands"], strict=True):
        for key in BAND_KEYS:
            assert got_band[key] == vec_band[key], key
    if vec["finished"] is not None:
        assert (got["finished_width"], got["finished_length"]) == vec["finished"]
    if vec.get("bands_u42") is not None:
        got42 = cr.border(cw, cl, bands, U=42, rule="per_piece")
        for got_band, vec_band in zip(got42["bands"], vec["bands_u42"], strict=True):
            for key in BAND_KEYS:
                assert got_band[key] == vec_band[key], ("U42", key)


# ---------------------------------------------------------------------------------------------
# Today's math (the start SHA), from the "today" lines of the vectors
# ---------------------------------------------------------------------------------------------


def test_today_backing_queen_90x108():
    # MATH.md V-BACK-07 "today" (line 852): vertical only, seam blind: Wb = 98, n = ceil(98 / 42)
    # = 3, 3 x 116 = 348 in, no allowance; 348 in = 2784 e, ceil(2784 / 72) = 39 qy = 9 3/4 yd.
    got = cr.backing(90, 108, **cr.BACKING_SETS["today"])
    assert got["kept"] == "vertical"
    assert got["panels"] == 3
    assert got["raw"] == F(348)
    assert got["total"] == F(348)
    assert got["yards"] == F(39, 4)


def test_today_backing_76x85_is_short():
    # V-BACK-10 "today" (line 873): ceil(84 / 42) = 2 panels x 93 = 186 in = 1488 e;
    # ceil(1488 / 72) = ceil(20.67) = 21 qy = 5 1/4 yd, although two seamed widths give 83 in.
    got = cr.backing(76, 85, **cr.BACKING_SETS["today"])
    assert got["panels"] == 2
    assert got["raw"] == F(186)
    assert got["yards"] == F(21, 4)


@pytest.mark.parametrize(
    ("w", "length", "vec"),
    [p for p in _vector_rows(cv.BACKING_B42) if p.values[2]["today_yards"] is not None],
)
def test_today_backing_vectors(w, length, vec):
    assert cr.backing(w, length, **cr.BACKING_SETS["today"])["yards"] == vec["today_yards"]


@pytest.mark.parametrize(
    ("w", "length", "vec"),
    [p for p in _vector_rows(cv.BINDING_U40) if p.values[2]["today"] is not None],
)
def test_today_binding_vectors(w, length, vec):
    got = cr.binding(w, length, **cr.BINDING_SETS["today"])
    for key, value in vec["today"].items():
        assert got[key] == value, key


# ---------------------------------------------------------------------------------------------
# Nebraska Quilt Company parameter set (40 in, s = 1/2, +8 in, no allowance, 1/4 yd)
# ---------------------------------------------------------------------------------------------


def test_nebraska_backing_throw_60x72_at_40():
    # Wb = 68, Lb = 80. Vertical: 68 > 40, n = ceil((68 - 1/2) / 39.5) = ceil(1.709) = 2;
    # 2 x 80 = 160 in = 1280 e; ceil(1280 / 72) = ceil(17.78) = 18 qy = 4 1/2 yd.
    # Horizontal: 2 panels cover 2 x 40 - 0.5 = 79.5 < 80, so n = ceil(79.5 / 39.5) = 3;
    # 3 x 68 = 204 in = 1632 e; ceil(1632 / 72) = ceil(22.67) = 23 qy = 5 3/4 yd.
    # Least total: 160 < 204, vertical.
    got = cr.backing(60, 72, **cr.BACKING_SETS["nqc"])
    assert got["vertical"]["panels"] == 2
    assert got["vertical"]["yards"] == F(9, 2)
    assert got["horizontal"]["panels"] == 3
    assert got["horizontal"]["raw"] == F(204)
    assert got["horizontal"]["yards"] == F(23, 4)
    assert got["kept"] == "vertical"


def test_nebraska_backing_queen_92_5x115_at_40():
    # Wb = 100.5, Lb = 123. Vertical: n = ceil((100.5 - 0.5) / 39.5) = ceil(2.53) = 3;
    # 3 x 123 = 369 in = 2952 e = 41 qy exactly = 10 1/4 yd.
    # Horizontal: 3 panels cover 3 x 40 - 1 = 119 < 123, n = ceil(122.5 / 39.5) = ceil(3.10) = 4;
    # 4 x 100.5 = 402 in = 3216 e; ceil(3216 / 72) = ceil(44.67) = 45 qy = 11 1/4 yd.
    got = cr.backing(F(185, 2), 115, **cr.BACKING_SETS["nqc"])
    assert (got["vertical"]["panels"], got["vertical"]["yards"]) == (3, F(41, 4))
    assert (got["horizontal"]["panels"], got["horizontal"]["yards"]) == (4, F(45, 4))
    assert got["kept"] == "vertical"


def test_nebraska_backing_queen_92_5x115_at_108():
    # Vertical: 100.5 <= 108, one panel of 123 in = 984 e; ceil(984 / 72) = ceil(13.67) = 14 qy
    # = 3 1/2 yd. Horizontal: n = ceil(122.5 / 107.5) = 2; 2 x 100.5 = 201 in = 1608 e;
    # ceil(1608 / 72) = ceil(22.33) = 23 qy = 5 3/4 yd.
    got = cr.backing(F(185, 2), 115, **{**cr.BACKING_SETS["nqc"], "B": 108})
    assert (got["vertical"]["panels"], got["vertical"]["yards"]) == (1, F(7, 2))
    assert (got["horizontal"]["panels"], got["horizontal"]["yards"]) == (2, F(23, 4))
    assert got["kept"] == "vertical"


def test_nebraska_binding_fixture():
    # T = 2 (75 + 90) + 12 = 342 in = 2736 e; not join aware: ceil(2736 / 320) = ceil(8.55) = 9;
    # 9 x 2 1/2 = 22.5 in = 180 e; ceil(180 / 72) = ceil(2.5) = 3 qy = 3/4 yd. Joined with
    # diagonal seams the 9 strips give 9 x 37.5 = 337.5 in, short of the 342 in asked for.
    got = cr.binding(75, 90, **cr.BINDING_SETS["nqc"])
    assert got["binding_length"] == F(342)
    assert got["strips"] == 9
    assert got["length"] == F(45, 2)
    assert got["yards"] == F(3, 4)
    assert got["joined"] == F(675, 2)


def test_plain_binding_eighth_increment_fixture():
    # Plain +10 at 40 in, 1/8 yd: T = 340 in = 2720 e; ceil(2720 / 320) = ceil(8.5) = 9 strips;
    # 9 x 2 1/2 = 22.5 in = 180 e; ceil(180 / 36) = 5 eighths = 5/8 yd.
    got = cr.binding(
        75, 90, U=40, w=F(5, 2), extra=10, join_aware=False, increment="eighth"
    )
    assert (got["strips"], got["yards"]) == (9, F(5, 8))


# ---------------------------------------------------------------------------------------------
# Quilter's Paradise emulation (IEEE doubles, the same as JS)
# ---------------------------------------------------------------------------------------------


def test_qp_backing_king_110x108_bolt_42():
    # MATH.md 5.2: 348 in is exactly 9 2/3 yd, yet the page shows 9 3/4.
    # Panels: left = 110 + 8 = 118; 118 - 42 = 76 > 0 -> left 77, i 2; 77 - 42 = 35 > 0 -> left
    # 36, i 3; 36 - 42 <= 0 -> 3 panels. yards = (108 + 8) / 36 * 3.
    # Float: 116 / 36 = 29/9 = 11.001110001110..._2 (2/9 repeats 001110). A double in [2, 4)
    # keeps 51 bits after the point; the bits after them, 110001110..., are 7/9 of an ulp, so it
    # rounds up: fl(29/9) = 29/9 + (2/9) 2^-51. The exact product with 3 is
    # 29/3 + (2/3) 2^-51 = 29/3 + (1/6) 2^-49, in [8, 16) where the ulp is 2^-49.
    # 29/3 = 1001.101010..._2 lies (1/3) 2^-49 above its 49-bit truncation T, so the product is
    # T + (1/3 + 1/6) 2^-49 = T + half an ulp: a tie. T ends in a 1 bit, so ties-to-even rounds
    # up to 29/3 + (2/3) 2^-49. Its fraction 2/3 + (2/3) 2^-49 is above
    # fl(2/3) = 2/3 - (1/3) 2^-53, so "<= 2/3" fails and "<= 0.75" shows 9 3/4.
    assert cr.qp_backing_display("110", "108", "42", "4") == (F(39, 4), 3)


def test_qp_backing_full_84x90_horizontal_shows_a_third():
    # MATH.md 5.2 lists full 84 x 90 (276 in, 7 2/3) as a thirds case. Typed width 90, length
    # 84: left = 98 -> 57 (i 2) -> 16 (i 3), 3 panels; yards = 92 / 36 * 3.
    # Float: 92 / 36 = 23/9 = 10.100011100011..._2 (5/9 repeats 100011). After 51 fraction bits
    # the rest is 0.011100011..._2 = 4/9 ulp, so it rounds down: fl(23/9) = 23/9 - (4/9) 2^-51.
    # Times 3: 23/3 - (4/3) 2^-51 = 23/3 - (2/3) 2^-50, in [4, 8) where the ulp is 2^-50.
    # 23/3 = 111.101010..._2 lies (2/3) 2^-50 above its 50-bit truncation, so the product is
    # that truncation exactly: 23/3 - (2/3) 2^-50. Its fraction 2/3 - (2/3) 2^-50 is below
    # fl(2/3) = 2/3 - (1/3) 2^-53 and above 0.625, so it shows 7 2/3.
    assert cr.qp_backing_display("90", "84", "42", "4") == (F(23, 3), 3)


def test_qp_backing_58x66_horizontal_shows_a_third():
    # MATH.md 5.2 lists 58 x 66 (132 in, 3 2/3). Typed width 66, length 58: left = 74 -> 33
    # (i 2), 2 panels; yards = 66 / 36 * 2. Float: 66 / 36 = 11/6 = 1.1101010..._2; after 52
    # fraction bits the rest is 0.0101..._2 = 1/3 ulp, rounds down: fl(11/6) = 11/6 -
    # (1/3) 2^-52. Doubling is exact: 11/3 - (2/3) 2^-52, fraction 2/3 - (2/3) 2^-52, below
    # fl(2/3) = 2/3 - (1/6) 2^-52, so it shows 3 2/3.
    assert cr.qp_backing_display("66", "58", "42", "4") == (F(11, 3), 2)


def test_qp_backing_queen_92_5x115_horizontal_is_8_3_8():
    # Typed width 115, length 92.5: left = 123 -> 82 (i 2) -> 41 (i 3), 3 panels;
    # yards = 100.5 / 36 * 3. Float: 100.5 / 36 = 67/24 = 10.1100101010..._2; after 51
    # fraction bits the rest is 0.0101..._2 = 1/3 ulp, rounds down: fl(67/24) = 67/24 -
    # (1/3) 2^-51. Times 3: 67/8 - 2^-51 = 8.375 - (1/4) 2^-49, which rounds to 8.375 in [8, 16)
    # (ulp 2^-49). Fraction exactly 0.375 -> "<= 0.375" -> 8 3/8, the planning case figure
    # MATH.md 5.1 infers for V-BACK-01.
    assert cr.qp_backing_display("115", "92.5", "42", "4") == (F(67, 8), 3)


def test_qp_backing_v_unit_06_published_example():
    # V-UNIT-06, MATH.md line 562: 52 x 96 on 43 in, no overage, 2 and 3 panels.
    # Width 52: left 52 -> 10 (i 2) -> done; yards = 96 / 36 * 2. fl(8/3) = 8/3 - (1/3) 2^-51
    # (10.1010..._2, tail 1/3 ulp, down); doubled exactly: 16/3 - (2/3) 2^-51, fraction
    # 1/3 - (2/3) 2^-51 < fl(1/3) = 1/3 - (1/3) 2^-54 and > 0.25 -> 5 1/3.
    assert cr.qp_backing_display("52", "96", "43", "0") == (F(16, 3), 2)
    # Width 96: left 96 -> 54 (i 2) -> 12 (i 3) -> done; yards = 52 / 36 * 3.
    # 13/9 = 1.011100011100..._2 (4/9 repeats 011100); after 52 fraction bits the rest is 1/9
    # ulp, down: fl(13/9) = 13/9 - (1/9) 2^-52. Times 3: 13/3 - (1/3) 2^-52; 13/3 lies (1/3)
    # 2^-50 above its 50-bit truncation T in [4, 8), so the product is T + (1/4) 2^-50, which
    # rounds down to T = 13/3 - (1/3) 2^-50. Fraction below fl(1/3), above 0.25 -> 4 1/3.
    assert cr.qp_backing_display("96", "52", "43", "0") == (F(13, 3), 3)


def test_qp_backing_through_the_backing_rule():
    # King 110 x 108 at 42 with QP's parameters (4 in overage, 1 in seams, no allowance).
    # Vertical is QP typed as width 110, length 108: 9 3/4 (test above), raw 3 x 116 = 348 in.
    # Horizontal is QP typed as width 108, length 110: left 116 -> 75 (i 2) -> 34 (i 3);
    # yards = 118 / 36 * 3, about 9.833, fraction 0.833 far from any step -> "<= 0.875" -> 9 7/8;
    # raw 3 x 118 = 354 in. Least total: 348 < 354, vertical.
    got = cr.backing(110, 108, **cr.BACKING_SETS["qp"])
    assert (got["vertical"]["panels"], got["vertical"]["yards"]) == (3, F(39, 4))
    assert (got["horizontal"]["panels"], got["horizontal"]["yards"]) == (3, F(79, 8))
    assert (got["kept"], got["raw"], got["yards"]) == ("vertical", F(348), F(39, 4))
    with pytest.raises(ValueError):
        # QP adds no allowance, and its float order cannot be reproduced with one.
        cr.backing(110, 108, **{**cr.BACKING_SETS["qp"], "allowance_pieced": 9})


def test_qp_binding_fixture_and_throw():
    # Fixture 75 x 90 at 40: T = 340 in = 2720 e; ceil(2720 / 300) = ceil(9.07) = 10 strips;
    # 10 x 2.5 / 36 = 25/36 = 0.694, above 0.67 and below 0.75 -> 3/4 yd.
    got = cr.binding(75, 90, **cr.BINDING_SETS["qp"])
    assert (got["strips"], got["length"], got["yards"]) == (10, F(25), F(3, 4))
    # Throw 60 x 72: T = 274 in = 2192 e; ceil(2192 / 300) = ceil(7.31) = 8 strips;
    # 8 x 2.5 / 36 = 20/36 = 0.556, above 0.5 and below 0.625 -> 5/8 yd.
    got = cr.binding(60, 72, **cr.BINDING_SETS["qp"])
    assert (got["strips"], got["yards"]) == (8, F(5, 8))


def test_qp_strip_ladder_uses_decimal_thirds():
    # 8 strips x 1 1/2 in = 12 in; 12 / 36 = 0.3333, which is above the strip pages' 0.33 step,
    # so it shows 3/8 rather than 1/3.
    assert cr.qp_strip_yards(8, "1.5") == F(3, 8)
    # The backing page's step is the double 1/3: (12 + 0) / 36 x 1 = fl(1/3), and
    # fl(1/3) <= fl(1/3), so it shows 1/3 (one panel: 30 <= 42).
    assert cr.qp_backing_display("30", "12", "42", "0") == (F(1, 3), 1)
    # 24 in / 36 = 0.6667 <= 0.67 -> 2/3 on the strip pages.
    assert cr.qp_strip_yards(8, "3") == F(2, 3)


def test_qp_pooled_border_fixture():
    # V-BORD-01 center 67 1/2 x 82 1/2, band 3 3/4, QP pooled finished lengths:
    # 2 x 82.5 + 2 x (67.5 + 7.5) = 165 + 150 = 315 in = 2520 e.
    # At 40: ceil(2520 / 316) = ceil(7.97) = 8 strips; 8 x 4 1/4 = 34 in; 34 / 36 = 0.944,
    # above 0.875 -> 1 yd. At 42: ceil(2520 / 332) = ceil(7.59) = 8, the same 34 in and 1 yd.
    for u in (40, 42):
        got = cr.border(F(135, 2), F(165, 2), [F(15, 4)], U=u, rule="qp_pooled")
        band = got["bands"][0]
        assert band["pooled_length"] == F(315)
        assert (band["strips"], band["strip_width"], band["length"]) == (8, F(17, 4), F(34))
        assert band["yards"] == F(1)


def test_qp_pooled_border_two_bands():
    # V-BORD-03 shape at 40, pooled: band 1 2 x 72 + 2 x 64 = 272 in = 2176 e,
    # ceil(2176 / 316) = ceil(6.89) = 7 strips, 7 x 2.5 = 17.5 in, 17.5 / 36 = 0.486 -> 1/2 yd.
    # Band 2 inner 64 x 76: 2 x 76 + 2 x 74 = 300 in = 2400 e, ceil(2400 / 316) = ceil(7.59) = 8,
    # 8 x 5.5 = 44 in, 44 / 36 = 1.222, fraction 0.222 <= 0.25 -> 1 1/4 yd. Finished 74 x 86.
    got = cr.border(60, 72, [2, 5], U=40, rule="qp_pooled")
    assert [(b["strips"], b["length"], b["yards"]) for b in got["bands"]] == [
        (7, F(35, 2), F(1, 2)),
        (8, F(44), F(5, 4)),
    ]
    assert (got["finished_width"], got["finished_length"]) == (F(74), F(86))


def test_per_piece_border_yards_fixture():
    # V-BORD-01 band alone as a border-only fabric (F5): 42.5 in = 340 e;
    # purchase = ceil(340 x 110 / 100) = 374 e exactly; ceil(374 / 72) = ceil(5.19) = 6 qy
    # = 1 1/2 yd. Without the margin: ceil(340 / 72) = ceil(4.72) = 5 qy = 1 1/4 yd.
    got = cr.border(F(135, 2), F(165, 2), [F(15, 4)], U=40, rule="per_piece")
    assert got["bands"][0]["yards"] == F(3, 2)
    got = cr.border(F(135, 2), F(165, 2), [F(15, 4)], U=40, rule="per_piece", margin_percent=0)
    assert got["bands"][0]["yards"] == F(5, 4)
    with pytest.raises(ValueError):
        cr.border(60, 72, [2], U=40, rule="qp_pooled", margin_percent=10)
