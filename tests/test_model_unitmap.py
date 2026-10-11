"""Unit map tests: hand-authored triangle blocks at confidence 1.0.

Every expected value is worked by hand in the comments beside it. Areas are
quadrupled square eighths (qrep.model.unitmap.AREA_SCALE): four times the area
in square eighths, which stays a whole number for every unit kind, including a
quarter-square triangle on an odd square size.
"""

import json
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from qrep.model import (
    AREA_SCALE,
    UNIT_MAP_SCHEMA_VERSION,
    Binding,
    CornerUnit,
    Fabric,
    GooseUnit,
    GridRegion,
    HstUnit,
    Palette,
    PlainUnit,
    QrepSchemaError,
    QstUnit,
    Quilt,
    QuiltMetadata,
    dumps,
    loads,
    quadrupled_area_by_fabric,
)

FIXTURE = Path(__file__).parent / "fixtures" / "double_irish_chain.json"

# Hand-authored data records confidence 1.0 (CLAUDE.md); units state it.
HAND = 1.0


def two_fabric_quilt(region: GridRegion, a: str, b: str) -> Quilt:
    return Quilt(
        metadata=QuiltMetadata(name="unit block"),
        palette=Palette(
            fabrics=[
                Fabric(id=a, name="Dark", color="#223355"),
                Fabric(id=b, name="Light", color="#f4efe2"),
            ]
        ),
        center=region,
        binding=Binding(fabric_id=a),
    )


def pinwheel() -> Quilt:
    # A 2 x 2 pinwheel of 2 in squares (16 eighths). Every diagonal runs
    # through the block center: the top-left and bottom-right squares run
    # top-left to bottom-right (tl_br), the other two top-right to bottom-left
    # (tr_bl). Turning the block a quarter turn clockwise moves the red half
    # of each square onto the red half of the next, so each square has one red
    # half and one white half. "upper" is the half that holds the top edge.
    # Every cell says red, so counting whole cells would give red everything.
    units = [
        HstUnit(row=0, col=0, diagonal="tl_br", upper="r", lower="w", confidence=HAND),
        HstUnit(row=0, col=1, diagonal="tr_bl", upper="w", lower="r", confidence=HAND),
        HstUnit(row=1, col=0, diagonal="tr_bl", upper="r", lower="w", confidence=HAND),
        HstUnit(row=1, col=1, diagonal="tl_br", upper="w", lower="r", confidence=HAND),
    ]
    region = GridRegion(rows=2, cols=2, cell_size=16, cells=[["r", "r"], ["r", "r"]], unit_map=units)
    return two_fabric_quilt(region, "r", "w")


def hourglass() -> Quilt:
    # A 2 x 2 block of two-fabric hourglass units on squares of 11 eighths
    # (1 3/8 in), an odd size on purpose: navy on top and bottom of the
    # top-left and bottom-right units, cream on top and bottom of the others.
    # Every cell says navy, so counting whole cells would give navy everything.
    def unit(row: int, col: int, ends: str, sides: str) -> QstUnit:
        return QstUnit(
            row=row, col=col, top=ends, right=sides, bottom=ends, left=sides, confidence=HAND
        )

    units = [unit(0, 0, "n", "c"), unit(0, 1, "c", "n"), unit(1, 0, "c", "n"), unit(1, 1, "n", "c")]
    region = GridRegion(rows=2, cols=2, cell_size=11, cells=[["n", "n"], ["n", "n"]], unit_map=units)
    return two_fabric_quilt(region, "n", "c")


def snowball() -> Quilt:
    # MATH.md V-TRI-07: a snowball with F = 6 in (48 eighths) and corner leg
    # c = 2 in, which is 1/3 of the side: 48 x 1/3 = 16 eighths = 2 in. The
    # base is the cell's fabric, cream; all four corners are blue.
    corners = {"top_left": "b", "top_right": "b", "bottom_right": "b", "bottom_left": "b"}
    region = GridRegion(
        rows=1,
        cols=1,
        cell_size=48,
        cells=[["c"]],
        unit_map=[CornerUnit(row=0, col=0, corners=corners, leg="1/3", confidence=HAND)],
    )
    return two_fabric_quilt(region, "b", "c")


def geese_row() -> Quilt:
    # MATH.md V-TRI-05: geese finished 2 x 4 in. On 2 in squares (16 eighths)
    # a goose pointing right is one square wide and two tall, so four geese
    # flying right fill a 2-row by 4-column row, each anchored on row 0.
    units = [
        GooseUnit(row=0, col=col, points="right", body="g", sky="s", confidence=HAND)
        for col in range(4)
    ]
    region = GridRegion(rows=2, cols=4, cell_size=16, cells=[["g"] * 4, ["g"] * 4], unit_map=units)
    return two_fabric_quilt(region, "g", "s")


BLOCKS = {"pinwheel": pinwheel, "hourglass": hourglass, "snowball": snowball, "geese": geese_row}


@pytest.mark.parametrize("name", sorted(BLOCKS))
def test_each_block_round_trips_exactly_through_json(name):
    # Criterion S1-1: the model survives the writer and the reader unchanged,
    # and writing what was read reproduces the same text.
    quilt = BLOCKS[name]()
    text = dumps(quilt)
    again = loads(text)
    assert again == quilt
    assert dumps(again) == text
    # Hand-authored maps record every unit at confidence 1.0.
    assert {unit.confidence for unit in again.center.unit_map} == {1.0}


def every_kind(confidences: list[float]) -> GridRegion:
    """2 x 4 squares of 12 eighths, every kind once: the one-square kinds on
    row 0, two geese across row 1. The corner leg is 12 x 1/3 = 4 eighths."""
    c = iter(confidences)
    units = [
        PlainUnit(row=0, col=0, confidence=next(c)),
        HstUnit(row=0, col=1, diagonal="tr_bl", upper="a", lower="b", confidence=next(c)),
        QstUnit(row=0, col=2, top="a", right="b", bottom="a", left="b", confidence=next(c)),
        CornerUnit(row=0, col=3, corners={"bottom_left": "b"}, leg="1/3", confidence=next(c)),
        GooseUnit(row=1, col=0, points="up", body="a", sky="b", confidence=next(c)),
        GooseUnit(row=1, col=2, points="down", body="b", sky="a", confidence=next(c)),
    ]
    return GridRegion(rows=2, cols=4, cell_size=12, cells=[["a"] * 4, ["a"] * 4], unit_map=units)


def test_a_read_confidence_survives_the_round_trip():
    # A read's confidences, one per unit, come back unchanged: 1/8 to 6/8.
    confidences = [0.125, 0.25, 0.375, 0.5, 0.625, 0.75]
    quilt = two_fabric_quilt(every_kind(confidences), "a", "b")
    again = loads(dumps(quilt))
    assert again == quilt
    assert [unit.confidence for unit in again.center.unit_map] == confidences


@pytest.mark.parametrize("unit_class", [PlainUnit, HstUnit, QstUnit, CornerUnit, GooseUnit])
def test_every_unit_states_its_confidence(unit_class):
    # No default: a read that leaves the confidence out, or misspells it, is
    # refused instead of stored as certain.
    unit = next(u for u in every_kind([HAND] * 6).unit_map if isinstance(u, unit_class))
    data = unit.model_dump()
    del data["confidence"]
    with pytest.raises(ValidationError, match=r"confidence\n  Field required"):
        unit_class.model_validate(data)
    with pytest.raises(ValidationError, match=r"confidence\n  Field required"):
        unit_class.model_validate({**data, "confidance": 0.25})


@pytest.mark.parametrize("name", sorted(BLOCKS))
def test_a_model_with_a_unit_map_writes_the_new_minor_version(name):
    # Criterion S1-2 with the bump: built with the default "1", a model that
    # carries a unit map is written as "1.1".
    assert UNIT_MAP_SCHEMA_VERSION == "1.1"
    assert json.loads(dumps(BLOCKS[name]()))["schema_version"] == "1.1"


def test_the_snowball_writes_its_leg_as_a_fraction():
    unit = json.loads(dumps(snowball()))["center"]["unit_map"][0]
    assert unit == {
        "kind": "corner",
        "row": 0,
        "col": 0,
        "corners": {"top_left": "b", "top_right": "b", "bottom_right": "b", "bottom_left": "b"},
        "leg": "1/3",
        "confidence": 1.0,
    }
    assert snowball().center.unit_map[0].leg == Fraction(1, 3)


def test_pinwheel_areas_split_evenly():
    # Each half-square triangle has area s^2 / 2 = 16 x 16 / 2 = 128 square
    # eighths, quadrupled 512. Each fabric holds one half of each of the four
    # squares: 4 x 512 = 2048. Total 4096 = 4 x (32 x 32).
    assert AREA_SCALE == 4
    assert quadrupled_area_by_fabric(pinwheel().center) == {"r": 2048, "w": 2048}


def test_hourglass_areas_on_an_odd_square_stay_whole():
    # A quarter of an 11-eighth square has area 121 / 4 square eighths.
    # Doubled it is 60.5, not a whole number; quadrupled it is 121. Each unit
    # gives each fabric two quarters: 2 x 121 = 242. Four units: 4 x 242 = 968
    # per fabric. Total 1936 = 4 x (22 x 22) = 4 x 484.
    area = quadrupled_area_by_fabric(hourglass().center)
    assert area == {"n": 968, "c": 968}
    assert all(type(value) is int for value in area.values())


def test_snowball_areas():
    # Leg 16 eighths: each corner triangle has area 16 x 16 / 2 = 128,
    # quadrupled 512; four corners 2048 of blue. The square: 48 x 48 = 2304,
    # quadrupled 9216; the cream base keeps 9216 - 2048 = 7168.
    assert quadrupled_area_by_fabric(snowball().center) == {"b": 2048, "c": 7168}


def test_flying_geese_areas():
    # Each goose covers 16 x 32 = 512 square eighths, quadrupled 2048. The body
    # is the triangle from the left edge to the point: 32 x 16 / 2 = 256,
    # quadrupled 1024. The two sky triangles have legs 16 and 16: 2 x 128 =
    # 256, quadrupled 1024. Four geese: 4 x 1024 = 4096 each. Total
    # 8192 = 4 x (64 x 32) = 4 x 2048.
    assert quadrupled_area_by_fabric(geese_row().center) == {"g": 4096, "s": 4096}


ONE_UNIT_AREAS = [
    # Squares of 8 eighths: a whole square is 8 x 8 = 64, quadrupled 256. The
    # cell fabric x belongs to no part except a plain square or a corner base.
    # Plain: the whole square is the cell's.
    (1, PlainUnit(row=0, col=0, confidence=HAND), {"x": 256}),
    # Half-square triangle: each half 64 / 2 = 32, quadrupled 128.
    (
        1,
        HstUnit(row=0, col=0, diagonal="tl_br", upper="u", lower="l", confidence=HAND),
        {"u": 128, "l": 128},
    ),
    # Quarter-square triangle: each quarter 64 / 4 = 16, quadrupled 64.
    (
        1,
        QstUnit(row=0, col=0, top="t", right="r", bottom="b", left="l", confidence=HAND),
        {"t": 64, "r": 64, "b": 64, "l": 64},
    ),
    # Corner leg 8 x 1/2 = 4: each triangle 4 x 4 / 2 = 8, quadrupled 32; the
    # base keeps 256 - 2 x 32 = 192.
    (
        1,
        CornerUnit(
            row=0, col=0, corners={"top_left": "p", "bottom_right": "q"}, leg="1/2", confidence=HAND
        ),
        {"p": 32, "q": 32, "x": 192},
    ),
    # A goose up over 2 squares, 16 x 8 = 128, quadrupled 512: the body is
    # half, 256; the two sky triangles (legs 8 and 8, 32 each, quadrupled 128)
    # make 256.
    (2, GooseUnit(row=0, col=0, points="up", body="g", sky="s", confidence=HAND), {"g": 256, "s": 256}),
]


@pytest.mark.parametrize(
    ("cols", "unit", "expected"), ONE_UNIT_AREAS, ids=["plain", "hst", "qst", "corner", "goose"]
)
def test_each_part_counts_only_its_own_share(cols, unit, expected):
    region = GridRegion(rows=1, cols=cols, cell_size=8, cells=[["x"] * cols], unit_map=[unit])
    area = quadrupled_area_by_fabric(region)
    assert area == expected
    assert all(type(value) is int for value in area.values())


def test_a_region_without_a_map_counts_whole_squares():
    # 2 x 3 squares of 8 eighths, three of each fabric: 3 x (4 x 8 x 8) = 768
    # each. Total 1536 = 4 x (24 x 16).
    region = GridRegion(rows=2, cols=3, cell_size=8, cells=[["r", "w", "r"], ["w", "r", "w"]])
    assert quadrupled_area_by_fabric(region) == {"r": 768, "w": 768}


@pytest.mark.parametrize("name", sorted(BLOCKS))
def test_the_areas_sum_to_the_region(name):
    # An identity on each block: the parts add up to the finished region, the
    # shape of the S2-4 check. The hand-computed shares above test each part.
    region = BLOCKS[name]().center
    assert sum(quadrupled_area_by_fabric(region).values()) == AREA_SCALE * region.width * region.height


def test_the_area_count_refuses_a_map_its_region_outgrew():
    # model_copy skips validation, as a resize does: on 50-eighth squares the
    # snowball's 1/3 leg is 50/3 eighths, which the count refuses instead of
    # rounding.
    region = snowball().center.model_copy(update={"cell_size": 50})
    with pytest.raises(ValueError, match="not a whole number of eighths"):
        quadrupled_area_by_fabric(region)


def test_a_model_without_a_unit_map_keeps_its_bytes():
    # The committed fixture has no unit map: read and written again, it is
    # byte for byte the same file, version "1" and no unit_map key.
    text = FIXTURE.read_text(encoding="utf-8")
    quilt = loads(text)
    assert quilt.center.unit_map is None
    assert dumps(quilt) == text
    data = json.loads(text)
    assert data["schema_version"] == "1"
    assert "unit_map" not in data["center"]


@pytest.mark.parametrize(("declared", "written"), [("1", "1.1"), ("1.0", "1.1"), ("1.5", "1.5")])
def test_a_unit_map_is_written_at_minor_one_or_later(declared, written):
    # "1" and "1.0" predate the map, so a map moves them to 1.1; a later
    # minor already has it and stays as written.
    data = json.loads(dumps(pinwheel()))
    data["schema_version"] = declared
    quilt = loads(json.dumps(data))
    assert quilt.schema_version == written
    assert json.loads(dumps(quilt))["schema_version"] == written


def test_a_map_added_without_validation_is_still_written_as_one_point_one():
    # model_copy skips the validator, so the writer applies the same rule.
    plain = two_fabric_quilt(GridRegion(rows=2, cols=2, cell_size=16, cells=[["r"] * 2] * 2), "r", "w")
    copied = plain.model_copy(update={"center": pinwheel().center})
    assert copied.schema_version == "1"
    assert json.loads(dumps(copied))["schema_version"] == "1.1"


def test_version_one_point_one_without_a_map_loads_as_written():
    region = GridRegion(rows=1, cols=1, cell_size=8, cells=[["a"]])
    data = json.loads(dumps(two_fabric_quilt(region, "a", "b")))
    data["schema_version"] = "1.1"
    assert loads(json.dumps(data)).schema_version == "1.1"


@pytest.mark.parametrize("version", ["2", "2.1", "0.9"])
def test_an_unknown_major_version_with_a_unit_map_still_raises(version):
    data = json.loads(dumps(pinwheel()))
    data["schema_version"] = version
    with pytest.raises(QrepSchemaError, match="unsupported schema_version"):
        loads(json.dumps(data))


def test_a_missing_version_with_a_unit_map_still_raises():
    data = json.loads(dumps(pinwheel()))
    del data["schema_version"]
    with pytest.raises(QrepSchemaError, match="missing"):
        loads(json.dumps(data))


def plain_map(rows: int, cols: int, skip: set[tuple[int, int]] = frozenset()) -> list:
    return [
        PlainUnit(row=r, col=c, confidence=HAND)
        for r in range(rows)
        for c in range(cols)
        if (r, c) not in skip
    ]


def region(units: list, rows: int = 2, cols: int = 2, cell_size: int = 8) -> GridRegion:
    return GridRegion(
        rows=rows,
        cols=cols,
        cell_size=cell_size,
        cells=[["a"] * cols for _ in range(rows)],
        unit_map=units,
    )


ALL_A = {
    "hst": {"diagonal": "tl_br", "upper": "a", "lower": "a"},
    "qst": {"top": "a", "right": "a", "bottom": "a", "left": "a"},
    "corner": {"corners": {corner: "a" for corner in ("top_left", "top_right", "bottom_right", "bottom_left")}, "leg": "1/2"},
    "goose": {"points": "up", "body": "a", "sky": "a"},
}
UNIT_CLASSES = {"hst": HstUnit, "qst": QstUnit, "corner": CornerUnit, "goose": GooseUnit}
PARTS = [
    ("hst", "upper"),
    ("hst", "lower"),
    ("qst", "top"),
    ("qst", "right"),
    ("qst", "bottom"),
    ("qst", "left"),
    ("corner", "top_left"),
    ("corner", "top_right"),
    ("corner", "bottom_right"),
    ("corner", "bottom_left"),
    ("goose", "body"),
    ("goose", "sky"),
]


@pytest.mark.parametrize(("kind", "part"), PARTS, ids=lambda v: v)
def test_every_part_fabric_must_be_in_the_palette(kind, part):
    # One part at a time names "ghost"; every other part, and every cell, is
    # "a", which the palette holds. A goose up at (0, 0) covers (0, 0) and
    # (0, 1); plain squares fill the rest of the 2 x 2 grid.
    fields = json.loads(json.dumps(ALL_A[kind]))
    if kind == "corner":
        fields["corners"][part] = "ghost"
    else:
        fields[part] = "ghost"
    unit = UNIT_CLASSES[kind](row=0, col=0, confidence=HAND, **fields)
    units = [unit] + plain_map(2, 2, skip=set(unit.squares()))
    with pytest.raises(ValidationError, match=r"\['ghost'\] referenced but not in palette"):
        two_fabric_quilt(region(units), "a", "b")
    # The same unit with "ghost" back to "a" is accepted.
    accepted = UNIT_CLASSES[kind](row=0, col=0, confidence=HAND, **ALL_A[kind])
    two_fabric_quilt(region([accepted] + plain_map(2, 2, skip=set(unit.squares()))), "a", "b")


def test_a_unit_outside_the_grid_is_refused():
    outside = PlainUnit(row=2, col=0, confidence=HAND)
    with pytest.raises(ValidationError, match=r"row 2, col 0 covers a square outside the 2 x 2 grid"):
        region(plain_map(2, 2) + [outside])


@pytest.mark.parametrize(
    ("points", "row", "col", "rows", "cols"),
    [
        # Up or down lies across: at the last of 3 columns its second square
        # would be column 3, outside the grid.
        ("up", 0, 2, 1, 3),
        ("down", 0, 2, 1, 3),
        # Left or right lies down: at the last of 3 rows its second square
        # would be row 3.
        ("left", 2, 0, 3, 1),
        ("right", 2, 0, 3, 1),
    ],
)
def test_a_goose_must_cover_two_squares_of_the_grid(points, row, col, rows, cols):
    goose = GooseUnit(row=row, col=col, points=points, body="a", sky="a", confidence=HAND)
    others = plain_map(rows, cols, skip={(row, col)})
    with pytest.raises(ValidationError, match=f"outside the {rows} x {cols} grid"):
        region(others + [goose], rows=rows, cols=cols)


def test_a_goose_covers_its_square_and_the_next():
    # Up and down lie across two columns; left and right down two rows.
    def at(points: str) -> list[tuple[int, int]]:
        return GooseUnit(row=1, col=2, points=points, body="a", sky="b", confidence=HAND).squares()

    assert at("up") == [(1, 2), (1, 3)]
    assert at("down") == [(1, 2), (1, 3)]
    assert at("left") == [(1, 2), (2, 2)]
    assert at("right") == [(1, 2), (2, 2)]


def test_a_square_covered_twice_is_refused():
    # The goose at (0, 0) pointing up also covers (0, 1), which a plain unit holds.
    goose = GooseUnit(row=0, col=0, points="up", body="a", sky="a", confidence=HAND)
    with pytest.raises(ValidationError, match=r"row 0, col 1 is covered by 2 units"):
        region(plain_map(2, 2, skip={(0, 0)}) + [goose])


def test_a_square_no_unit_covers_is_refused():
    with pytest.raises(ValidationError, match=r"row 1, col 1 is covered by no unit"):
        region(plain_map(2, 2, skip={(1, 1)}))


def test_a_corner_leg_must_land_on_a_whole_eighth():
    # 1/3 of an 8-eighth square is 8/3 eighths, which no rotary cut can make
    # (MATH.md F14 cuts the corner square at leg + 1/2 in). On a 12-eighth
    # square the same leg is 4 eighths and is accepted.
    unit = CornerUnit(row=0, col=0, corners={"top_left": "a"}, leg="1/3", confidence=HAND)
    with pytest.raises(ValidationError, match="is 8/3 eighths, not a whole number of eighths"):
        region([unit], rows=1, cols=1, cell_size=8)
    assert region([unit], rows=1, cols=1, cell_size=12).unit_map == [unit]


@pytest.mark.parametrize(
    ("side", "ends"),
    [
        ("top", ("top_left", "top_right")),
        ("right", ("top_right", "bottom_right")),
        ("bottom", ("bottom_left", "bottom_right")),
        ("left", ("top_left", "bottom_left")),
    ],
)
def test_corner_legs_along_each_side_total_at_most_the_side(side, ends):
    # PATTERN-SPEC S5.3: two corners on one side at 1/2 each total 1, the
    # whole side, and are accepted; at 2/3 each they total 4/3 and overlap.
    corners = {end: "a" for end in ends}
    assert CornerUnit(row=0, col=0, corners=corners, leg="1/2", confidence=HAND).leg == Fraction(1, 2)
    with pytest.raises(ValidationError, match=f"along the {side} side total more than the side"):
        CornerUnit(row=0, col=0, corners=corners, leg="2/3", confidence=HAND)


@pytest.mark.parametrize("ends", [("top_left", "bottom_right"), ("top_right", "bottom_left")])
def test_opposite_corners_share_no_side(ends):
    # Opposite corners touch no common side, so 2/3 each fits.
    corners = {end: "a" for end in ends}
    assert CornerUnit(row=0, col=0, corners=corners, leg="2/3", confidence=HAND).leg == Fraction(2, 3)


@pytest.mark.parametrize(
    ("leg", "message"),
    [
        ("0/1", 'such as "1/3"'),
        ("1/0", 'such as "1/3"'),
        ("01/3", 'such as "1/3"'),
        ("1/3 ", 'such as "1/3"'),
        ("1/3\n", 'such as "1/3"'),
        ("one third", 'such as "1/3"'),
        (0.5, 'such as "1/3"'),
        (1, 'such as "1/3"'),
        (True, 'such as "1/3"'),
        ("2/6", "lowest terms"),
        ("4/3", "at most the whole side"),
        (Fraction(4, 3), "at most the whole side"),
        (Fraction(0), "more than 0"),
        (Fraction(-1, 3), "more than 0"),
    ],
    ids=repr,
)
def test_a_corner_leg_is_a_lowest_terms_fraction_of_the_side(leg, message):
    with pytest.raises(ValidationError, match=message):
        CornerUnit(row=0, col=0, corners={"top_left": "a"}, leg=leg, confidence=HAND)


def test_a_corner_leg_may_be_given_as_a_fraction():
    unit = CornerUnit(row=0, col=0, corners={"top_left": "a"}, leg=Fraction(1, 4), confidence=HAND)
    assert json.loads(unit.model_dump_json())["leg"] == "1/4"


def test_corners_are_kept_in_one_order():
    # Equal units write the same bytes whatever order the corners came in.
    given = CornerUnit(
        row=0, col=0, corners={"bottom_left": "a", "top_left": "b"}, leg="1/2", confidence=HAND
    )
    reverse = CornerUnit(
        row=0, col=0, corners={"top_left": "b", "bottom_left": "a"}, leg="1/2", confidence=HAND
    )
    assert list(given.corners) == ["top_left", "bottom_left"]
    assert given.model_dump_json() == reverse.model_dump_json()


def test_a_corner_unit_needs_a_corner():
    with pytest.raises(ValidationError, match="Dictionary should have at least 1 item"):
        CornerUnit(row=0, col=0, corners={}, leg="1/2", confidence=HAND)


def test_an_unknown_corner_or_kind_is_refused():
    with pytest.raises(ValidationError, match=r"corners\.middle\.\[key\]"):
        CornerUnit(row=0, col=0, corners={"middle": "a"}, leg="1/2", confidence=HAND)
    with pytest.raises(ValidationError, match=r"tag 'curve'"):
        GridRegion.model_validate(
            {"rows": 1, "cols": 1, "cell_size": 8, "cells": [["a"]],
             "unit_map": [{"kind": "curve", "row": 0, "col": 0, "confidence": 1.0}]}
        )


@pytest.mark.parametrize(("row", "col"), [(True, 0), (0, False), (1.0, 0)])
def test_a_square_index_is_a_whole_number_not_a_bool(row, col):
    # JSON true would otherwise load as square 1 and be written back as 1.
    with pytest.raises(ValidationError, match="Input should be a valid integer"):
        PlainUnit(row=row, col=col, confidence=HAND)
