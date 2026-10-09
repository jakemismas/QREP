"""MATH.md section 4 vectors transcribed for the D2 calculator matrix (MATH.md section 5.2).

Every expected value here is copied from MATH.md's hand arithmetic and cited by vector id and
line (line numbers of docs/sprint-5/MATH.md in this worktree). Nothing is computed. Every table
holds every matrix row: a size with no vector maps to None, so the report prints "no vector",
because a computed stand-in would let the formulas under test grade themselves.

Lengths are inches and yards are yards, both as Fractions; counts are ints.

Stdlib only, because the test also runs under Pyodide.
"""

from __future__ import annotations

from fractions import Fraction as F

__all__ = [
    "BACKING_B40",
    "BACKING_B42",
    "BACKING_POLICY",
    "BATTING",
    "BINDING_U40",
    "BINDING_U42",
    "BORDER",
    "BORDER_ROWS",
    "MATRIX",
    "POLICY_COLUMNS",
    "WIDE",
]

# ---------------------------------------------------------------------------------------------
# The size matrix (MATH.md 5.2, line 1160): the eight section 4.7 sizes, then the seven others.
# (row_id, label, W, L), finished inches.
# ---------------------------------------------------------------------------------------------

MATRIX: list[tuple[str, str, F, F]] = [
    ("36x52", "crib 36 x 52", F(36), F(52)),
    ("50x65", "throw 50 x 65", F(50), F(65)),
    ("60x72", "throw 60 x 72", F(60), F(72)),
    ("70x90", "twin 70 x 90", F(70), F(90)),
    ("84x90", "full 84 x 90", F(84), F(90)),
    ("90x108", "queen 90 x 108", F(90), F(108)),
    ("92.5x115", "queen 92 1/2 x 115", F("92.5"), F(115)),
    ("110x108", "king 110 x 108", F(110), F(108)),
    ("75x90", "fixture 75 x 90", F(75), F(90)),
    ("42x52", "42 x 52", F(42), F(52)),
    ("76x85", "76 x 85", F(76), F(85)),
    ("68x68", "68 x 68", F(68), F(68)),
    ("102.5x120", "102 1/2 x 120", F("102.5"), F(120)),
    ("58x66", "58 x 66", F(58), F(66)),
    ("24x58", "24 x 58", F(24), F(58)),
]

_ROW_IDS = [row[0] for row in MATRIX]


def _inches_text(value: F) -> str:
    whole, rest = divmod(value, 1)
    if rest == 0:
        return str(whole)
    return f"{whole} {rest.numerator}/{rest.denominator}" if whole else str(rest)


# One 3 3/4 in band (the fixture's, V-BORD-01) around a center 7 1/2 in smaller each way, so the
# bordered quilt finishes at the matrix size.
_MATRIX_BAND = F(15, 4)
_BAND_TAKES = 2 * _MATRIX_BAND

# (row_id, label, center_W, center_L, bands), finished inches.
BORDER_ROWS: list[tuple[str, str, F, F, tuple[F, ...]]] = [
    (
        f"{row_id}-b3.75",
        f"{label}: center {_inches_text(w - _BAND_TAKES)} x {_inches_text(ln - _BAND_TAKES)},"
        " band 3 3/4",
        w - _BAND_TAKES,
        ln - _BAND_TAKES,
        (_MATRIX_BAND,),
    )
    for row_id, label, w, ln in MATRIX
] + [
    ("V-BORD-02", "crib: center 32 x 48, band 2", F(32), F(48), (F(2),)),
    ("V-BORD-03", "center 60 x 72, bands 2 then 5", F(60), F(72), (F(2), F(5))),
    ("V-BORD-04", "tiny: center 4 x 4, band 1", F(4), F(4), (F(1),)),
]


def _complete(table: dict[str, dict | None], ids: list[str]) -> dict[str, dict | None]:
    """Every row id in matrix order, None where MATH.md has no vector."""
    unknown = set(table) - set(ids)
    if unknown:
        raise ValueError(f"vector rows outside the matrix: {sorted(unknown)}")
    return {row_id: table.get(row_id) for row_id in ids}


# ---------------------------------------------------------------------------------------------
# Backing, pieced (MATH.md 4.4). kept layout, its panel count and panel cut length, raw length,
# total (raw + allowance) and yards; today_yards is the vector's "today" line (None when the
# vector states none).
# ---------------------------------------------------------------------------------------------


def _back(vector, line, kept, panels, panel_length, raw, total, yards, today_yards=None):
    return {
        "vector": vector,
        "line": line,
        "kept": kept,
        "panels": panels,
        "panel_length": F(panel_length),
        "raw": F(raw),
        "total": F(total),
        "yards": F(yards),
        "today_yards": None if today_yards is None else F(today_yards),
    }


BACKING_B42 = _complete(
    {
        # V-BACK-03 line 819: horizontal 2 x 44 = 88; + 9 = 97 in; 11 qy; today 14 qy
        "36x52": _back("V-BACK-03", 819, "horizontal", 2, 44, 88, 97, F(11, 4), F(7, 2)),
        # V-BACK-04 line 826: horizontal 2 x 58 = 116; + 9 = 125 in; 14 qy; today 17 qy
        "50x65": _back("V-BACK-04", 826, "horizontal", 2, 58, 116, 125, F(7, 2), F(17, 4)),
        # V-BACK-02 line 811: horizontal 2 x 68 = 136; + 9 = 145 in; 17 qy; today 18 qy
        "60x72": _back("V-BACK-02", 811, "horizontal", 2, 68, 136, 145, F(17, 4), F(9, 2)),
        # V-BACK-05 line 833: vertical 2 x 98 = 196; + 9 = 205 in; 23 qy; today 22 qy
        "70x90": _back("V-BACK-05", 833, "vertical", 2, 98, 196, 205, F(23, 4), F(11, 2)),
        # V-BACK-06 line 840: horizontal 3 x 92 = 276; + 9 = 285 in; 32 qy; today 33 qy
        "84x90": _back("V-BACK-06", 840, "horizontal", 3, 92, 276, 285, F(8), F(33, 4)),
        # V-BACK-07 line 847: horizontal 3 x 98 = 294; + 9 = 303 in; 34 qy; today 39 qy
        "90x108": _back("V-BACK-07", 847, "horizontal", 3, 98, 294, 303, F(17, 2), F(39, 4)),
        # V-BACK-01 line 801: horizontal 3 x 100.5 = 301.5; + 9 = 310.5 in; 35 qy; today 41 qy
        "92.5x115": _back(
            "V-BACK-01", 801, "horizontal", 3, F("100.5"), F("301.5"), F("310.5"), F(35, 4),
            F(41, 4),
        ),  # fmt: skip
        # V-BACK-08 line 854: vertical 3 x 116 = 348; + 9 = 357 in; 40 qy; today 39 qy
        "110x108": _back("V-BACK-08", 854, "vertical", 3, 116, 348, 357, F(10), F(39, 4)),
        # V-BACK-09 line 861: vertical 2 x 98 = 196; + 9 = 205 in; 23 qy; today 22 qy
        "75x90": _back("V-BACK-09", 861, "vertical", 2, 98, 196, 205, F(23, 4), F(11, 2)),
        # V-BACK-11 line 876: horizontal 2 x 50 = 100; + 9 = 109 in; 13 qy; today 14 qy
        "42x52": _back("V-BACK-11", 876, "horizontal", 2, 50, 100, 109, F(13, 4), F(7, 2)),
        # V-BACK-10 line 868: horizontal 3 x 84 = 252; + 9 = 261 in; 29 qy; today 21 qy
        "76x85": _back("V-BACK-10", 868, "horizontal", 3, 84, 252, 261, F(29, 4), F(21, 4)),
        # V-BACK-13 line 888: tie, vertical 2 x 76 = 152; + 9 = 161 in; 18 qy; today 17 qy
        "68x68": _back("V-BACK-13", 888, "vertical", 2, 76, 152, 161, F(9, 2), F(17, 4)),
        # V-BACK-16 line 909: vertical 3 x 128 = 384; + 9 = 393 in; 44 qy; today 43 qy
        "102.5x120": _back("V-BACK-16", 909, "vertical", 3, 128, 384, 393, F(11), F(43, 4)),
        # V-BACK-23 line 951: horizontal 2 x 66 = 132; + 9 = 141 in; 16 qy; no today line
        "58x66": _back("V-BACK-23", 951, "horizontal", 2, 66, 132, 141, F(4)),
        # V-BACK-14 line 894: vertical 1 x 66; + 4.5 = 70.5 in; 8 qy; today 8 qy
        "24x58": _back("V-BACK-14", 894, "vertical", 1, 66, 66, F("70.5"), F(2), F(2)),
    },
    _ROW_IDS,
)

# B = 40 configured (V-BACK-18 to V-BACK-20).
BACKING_B40 = _complete(
    {
        # V-BACK-18 line 923: vertical 3 x 123 = 369; + 9 = 378 in; 42 qy
        "92.5x115": _back("V-BACK-18", 923, "vertical", 3, 123, 369, 378, F(21, 2)),
        # V-BACK-19 line 929: vertical 2 x 80 = 160; + 9 = 169 in; 19 qy
        "60x72": _back("V-BACK-19", 929, "vertical", 2, 80, 160, 169, F(19, 4)),
        # V-BACK-20 line 934: horizontal 3 x 83 = 249; + 9 = 258 in; 29 qy
        "75x90": _back("V-BACK-20", 934, "horizontal", 3, 83, 249, 258, F(29, 4)),
    },
    _ROW_IDS,
)

# Policy columns, MATH.md lines 958 to 963: A default (+9 / +4 1/2 in, 1/4 yd); B the allowance
# at 1/8 yd; C no allowance at 1/4 yd; D no allowance at 1/8 yd.
POLICY_COLUMNS = {
    "A": {"allowance_pieced": F(9), "allowance_one": F(9, 2), "increment": "quarter"},
    "B": {"allowance_pieced": F(9), "allowance_one": F(9, 2), "increment": "eighth"},
    "C": {"allowance_pieced": F(0), "allowance_one": F(0), "increment": "quarter"},
    "D": {"allowance_pieced": F(0), "allowance_one": F(0), "increment": "eighth"},
}


def _policy(vector, line, a, b, c, d, today):
    return {
        "vector": vector,
        "line": line,
        "A": F(a),
        "B": F(b),
        "C": F(c),
        "D": F(d),
        "today": F(today),
    }


# The policy table, MATH.md lines 966 to 977 (yards per column, then today's).
BACKING_POLICY = _complete(
    {
        "36x52": _policy("V-BACK-03", 968, F(11, 4), F(11, 4), F(5, 2), F(5, 2), F(7, 2)),
        "50x65": _policy("V-BACK-04", 969, F(7, 2), F(7, 2), F(13, 4), F(13, 4), F(17, 4)),
        "60x72": _policy("V-BACK-02", 970, F(17, 4), F(33, 8), F(4), F(31, 8), F(9, 2)),
        "70x90": _policy("V-BACK-05", 971, F(23, 4), F(23, 4), F(11, 2), F(11, 2), F(11, 2)),
        "84x90": _policy("V-BACK-06", 972, F(8), F(8), F(31, 4), F(31, 4), F(33, 4)),
        "90x108": _policy("V-BACK-07", 973, F(17, 2), F(17, 2), F(33, 4), F(33, 4), F(39, 4)),
        "92.5x115": _policy("V-BACK-01", 974, F(35, 4), F(69, 8), F(17, 2), F(67, 8), F(41, 4)),
        "110x108": _policy("V-BACK-08", 975, F(10), F(10), F(39, 4), F(39, 4), F(39, 4)),
        "75x90": _policy("V-BACK-09", 976, F(23, 4), F(23, 4), F(11, 2), F(11, 2), F(11, 2)),
        # Today 5 1/4 yd is short on this size (two panels give 83 in against 84 in).
        "76x85": _policy("V-BACK-10", 977, F(29, 4), F(29, 4), F(7), F(7), F(21, 4)),
    },
    _ROW_IDS,
)

# ---------------------------------------------------------------------------------------------
# Wide-back (MATH.md 4.5). Per width key: a dict {length, total, yards}; None when the vector
# states there is no line at that width; key absent when the vector does not state that width.
# ---------------------------------------------------------------------------------------------


def _wide(length, total, yards):
    return {"length": F(length), "total": F(total), "yards": F(yards)}


WIDE = _complete(
    {
        # V-WIDE-01 line 985: Lb = 123; + 4.5 = 127.5 in; 15 qy
        "92.5x115": {"vector": "V-WIDE-01", "line": 985, "bw108": _wide(123, F("127.5"), F(15, 4))},
        # V-WIDE-02 line 989: min(68, 80) = 68; + 4.5 = 72.5 in; 9 qy
        "60x72": {"vector": "V-WIDE-02", "line": 989, "bw108": _wide(68, F("72.5"), F(9, 4))},
        # V-WIDE-03 line 993: min(84, 93) = 84; + 4.5 = 88.5 in; 10 qy
        "76x85": {"vector": "V-WIDE-03", "line": 993, "bw108": _wide(84, F("88.5"), F(5, 2))},
        # V-WIDE-04 line 996: Lb = 116; + 4.5 = 120.5 in; 14 qy
        "90x108": {"vector": "V-WIDE-04", "line": 996, "bw108": _wide(116, F("120.5"), F(7, 2))},
        # V-WIDE-05 line 1000: no 108 in line; at 118 min(118, 116) = 116; 964 e; 14 qy
        "110x108": {
            "vector": "V-WIDE-05",
            "line": 1000,
            "bw108": None,
            "bw118": _wide(116, F("120.5"), F(7, 2)),
        },
        # V-WIDE-06 line 1004: no 108 in line; at 118 Lb = 128; + 4.5 = 132.5 in; 15 qy
        "102.5x120": {
            "vector": "V-WIDE-06",
            "line": 1004,
            "bw108": None,
            "bw118": _wide(128, F("132.5"), F(15, 4)),
        },
        # V-WIDE-08 line 1011: min(83, 98) = 83; + 4.5 = 87.5 in; 10 qy
        "75x90": {"vector": "V-WIDE-08", "line": 1011, "bw108": _wide(83, F("87.5"), F(5, 2))},
        # V-WIDE-09 line 1014: min(50, 60) = 50; + 4.5 = 54.5 in; 7 qy
        "42x52": {"vector": "V-WIDE-09", "line": 1014, "bw108": _wide(50, F("54.5"), F(7, 4))},
        # V-WIDE-10 lines 1018 to 1021: the smaller dimension; + 4.5 in
        "36x52": {"vector": "V-WIDE-10", "line": 1018, "bw108": _wide(44, F("48.5"), F(3, 2))},
        "50x65": {"vector": "V-WIDE-10", "line": 1019, "bw108": _wide(58, F("62.5"), F(7, 4))},
        "70x90": {"vector": "V-WIDE-10", "line": 1020, "bw108": _wide(78, F("82.5"), F(5, 2))},
        "84x90": {"vector": "V-WIDE-10", "line": 1021, "bw108": _wide(92, F("96.5"), F(11, 4))},
    },
    _ROW_IDS,
)

# ---------------------------------------------------------------------------------------------
# Binding (MATH.md 4.3). binding_length is T = 2 (W + L) + 10; today holds only the values the
# vector's "today" line states (strips, and length or yards when given), or None.
# ---------------------------------------------------------------------------------------------


def _bind(vector, line, t, strips, length, yards, today=None):
    return {
        "vector": vector,
        "line": line,
        "binding_length": F(t),
        "strips": strips,
        "length": F(length),
        "yards": F(yards),
        "today": today,
    }


BINDING_U40 = _complete(
    {
        # V-BIND-11 line 751: ceil(186 / 37.5) = 5; 12.5 in; 2 qy; today 5 strips, 1/2 yd
        "36x52": _bind(
            "V-BIND-11", 751, 186, 5, F("12.5"), F(1, 2), {"strips": 5, "yards": F(1, 2)}
        ),
        # V-BIND-12 line 756: ceil(240 / 37.5) = 7; 17.5 in; 2 qy; today 6 strips
        "50x65": _bind("V-BIND-12", 756, 240, 7, F("17.5"), F(1, 2), {"strips": 6}),
        # V-BIND-13 line 761: ceil(274 / 37.5) = 8; 20 in; 3 qy; today 7 strips, 1/2 yd
        "60x72": _bind("V-BIND-13", 761, 274, 8, 20, F(3, 4), {"strips": 7, "yards": F(1, 2)}),
        # V-BIND-14 line 766: ceil(330 / 37.5) = 9; 22.5 in; 3 qy; today 8 strips
        "70x90": _bind("V-BIND-14", 766, 330, 9, F("22.5"), F(3, 4), {"strips": 8}),
        # V-BIND-15 line 771: ceil(358 / 37.5) = 10; 25 in; 3 qy; today 9 strips
        "84x90": _bind("V-BIND-15", 771, 358, 10, 25, F(3, 4), {"strips": 9}),
        # V-BIND-16 line 776: ceil(406 / 37.5) = 11; 27.5 in; 4 qy; today 10 strips, 25 in, 3/4
        "90x108": _bind(
            "V-BIND-16", 776, 406, 11, F("27.5"), F(1),
            {"strips": 10, "length": F(25), "yards": F(3, 4)},
        ),  # fmt: skip
        # V-BIND-05 line 717: ceil(425 / 37.5) = 12; 30 in; 4 qy; today 11 strips, 27.5 in, 1 yd
        "92.5x115": _bind(
            "V-BIND-05", 717, 425, 12, 30, F(1),
            {"strips": 11, "length": F("27.5"), "yards": F(1)},
        ),  # fmt: skip
        # V-BIND-17 line 781: ceil(446 / 37.5) = 12; 30 in; 4 qy; today 11 strips
        "110x108": _bind("V-BIND-17", 781, 446, 12, 30, F(1), {"strips": 11}),
        # V-BIND-01 line 695: ceil(340 / 37.5) = 10; 25 in; 3 qy; today 9 strips, 22.5 in, 3/4
        "75x90": _bind(
            "V-BIND-01", 695, 340, 10, 25, F(3, 4),
            {"strips": 9, "length": F("22.5"), "yards": F(3, 4)},
        ),  # fmt: skip
        # V-BIND-10 line 746: ceil(198 / 37.5) = 6; 15 in; 2 qy; today 5 strips
        "42x52": _bind("V-BIND-10", 746, 198, 6, 15, F(1, 2), {"strips": 5}),
        # V-BIND-02 line 702: ceil(332 / 37.5) = 9; 22.5 in; 3 qy; today 8 strips
        "76x85": _bind("V-BIND-02", 702, 332, 9, F("22.5"), F(3, 4), {"strips": 8}),
        # V-BIND-07 line 727: ceil(282 / 37.5) = 8; 20 in; 3 qy; today 7 strips
        "68x68": _bind("V-BIND-07", 727, 282, 8, 20, F(3, 4), {"strips": 7}),
        # V-BIND-06 line 722: ceil(455 / 37.5) = 13; 32.5 in; 4 qy; today 11 strips
        "102.5x120": _bind("V-BIND-06", 722, 455, 13, F("32.5"), F(1), {"strips": 11}),
        # V-BIND-18 line 786: ceil(258 / 37.5) = 7; 17.5 in; 2 qy; no today line
        "58x66": _bind("V-BIND-18", 786, 258, 7, F("17.5"), F(1, 2)),
    },
    _ROW_IDS,
)

# U = 42 configured.
BINDING_U42 = _complete(
    {
        # V-BIND-09 line 742: ceil(340 / 39.5) = 9; 22.5 in; 3 qy
        "75x90": _bind("V-BIND-09", 742, 340, 9, F("22.5"), F(3, 4)),
    },
    _ROW_IDS,
)

# ---------------------------------------------------------------------------------------------
# Batting (MATH.md 4.6, o = 4 in per side). package None means no package covers it.
# ---------------------------------------------------------------------------------------------


def _batt(vector, line, width, length, package):
    return {
        "vector": vector,
        "line": line,
        "width": F(width),
        "length": F(length),
        "package": package,
    }


BATTING = _complete(
    {
        "36x52": _batt("V-BATT-02", 1033, 44, 60, "crib"),
        "50x65": _batt("V-BATT-04", 1035, 58, 73, "twin"),
        "60x72": _batt("V-BATT-03", 1034, 68, 80, "twin"),
        "70x90": _batt("V-BATT-05", 1036, 78, 98, "queen"),
        "84x90": _batt("V-BATT-06", 1038, 92, 98, "king"),
        "90x108": _batt("V-BATT-07", 1040, 98, 116, "king"),
        "92.5x115": _batt("V-BATT-08", 1041, F("100.5"), 123, "king"),  # turned
        "110x108": _batt("V-BATT-09", 1042, 118, 116, "king"),
        "75x90": _batt("V-BATT-01", 1030, 83, 98, "queen"),
        "42x52": _batt("V-BATT-13", 1047, 50, 60, "twin"),
        "68x68": _batt("V-BATT-11", 1045, 76, 76, "full"),
        # Prints "larger than a king package (124 x 120 in)" (line 1044).
        "102.5x120": _batt("V-BATT-10", 1043, F("110.5"), 128, None),
    },
    _ROW_IDS,
)

# ---------------------------------------------------------------------------------------------
# Borders (MATH.md 4.2, F4 per piece, U = 40 unless the key says otherwise). Per band: cut strip
# width, side length and strips for the side pair, top/bottom length and strips for that pair,
# band strips and band length. finished is (W, L) where the vector states it, else None.
# ---------------------------------------------------------------------------------------------


def _band(strip_width, side_length, side_strips, top_length, top_strips, strips, length):
    return {
        "strip_width": F(strip_width),
        "side_length": F(side_length),
        "side_strips": side_strips,
        "top_length": F(top_length),
        "top_strips": top_strips,
        "strips": strips,
        "length": F(length),
    }


BORDER = _complete(
    {
        # V-BORD-01 line 615: cut 4.25; sides 83 in, k 3 -> 6; top/bottom 75.5 in, k 2 -> 4;
        # 10 strips, 42.5 in. At U = 42 (lines 624 to 626): 4 + 4 = 8 strips, 34 in.
        "75x90-b3.75": {
            "vector": "V-BORD-01",
            "line": 615,
            "bands": [_band(F("4.25"), 83, 6, F("75.5"), 4, 10, F("42.5"))],
            "bands_u42": [_band(F("4.25"), 83, 4, F("75.5"), 4, 8, 34)],
            "finished": None,
        },
        # V-BORD-02 line 628: cut 2.5; sides 48.5 in, k 2 -> 4; top/bottom 36.5 in -> 2;
        # 6 strips, 15 in; finished 36 x 52.
        "V-BORD-02": {
            "vector": "V-BORD-02",
            "line": 628,
            "bands": [_band(F("2.5"), F("48.5"), 4, F("36.5"), 2, 6, 15)],
            "finished": (F(36), F(52)),
        },
        # V-BORD-03 line 634: band 1 cut 2.5, 72.5 -> 4, 64.5 -> 4, 8 strips, 20 in; band 2 on
        # 64 x 76, cut 5.5, 76.5 -> 4, 74.5 -> 4, 8 strips, 44 in; finished 74 x 86.
        "V-BORD-03": {
            "vector": "V-BORD-03",
            "line": 634,
            "bands": [
                _band(F("2.5"), F("72.5"), 4, F("64.5"), 4, 8, 20),
                _band(F("5.5"), F("76.5"), 4, F("74.5"), 4, 8, 44),
            ],
            "finished": (F(74), F(86)),
        },
        # V-BORD-04 line 644: cut 1.5; sides 4.5 in -> 1; top/bottom 6.5 in -> 1; 2 strips, 3 in.
        "V-BORD-04": {
            "vector": "V-BORD-04",
            "line": 644,
            "bands": [_band(F("1.5"), F("4.5"), 1, F("6.5"), 1, 2, 3)],
            "finished": None,
        },
    },
    [row[0] for row in BORDER_ROWS],
)
