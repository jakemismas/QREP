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
    units = [
        HstUnit(row=0, col=0, diagonal="tl_br", upper="r", lower="w"),
        HstUnit(row=0, col=1, diagonal="tr_bl", upper="w", lower="r"),
        HstUnit(row=1, col=0, diagonal="tr_bl", upper="r", lower="w"),
        HstUnit(row=1, col=1, diagonal="tl_br", upper="w", lower="r"),
    ]
    region = GridRegion(
        rows=2, cols=2, cell_size=16, cells=[["r", "w"], ["r", "w"]], unit_map=units
    )
    return two_fabric_quilt(region, "r", "w")


def hourglass() -> Quilt:
    # A 2 x 2 block of two-fabric hourglass units on squares of 11 eighths
    # (1 3/8 in), an odd size on purpose: navy on top and bottom of the
    # top-left and bottom-right units, cream on top and bottom of the others.
    def unit(row: int, col: int, ends: str, sides: str) -> QstUnit:
        return QstUnit(row=row, col=col, top=ends, right=sides, bottom=ends, left=sides)

    units = [unit(0, 0, "n", "c"), unit(0, 1, "c", "n"), unit(1, 0, "c", "n"), unit(1, 1, "n", "c")]
    region = GridRegion(
        rows=2, cols=2, cell_size=11, cells=[["n", "c"], ["c", "n"]], unit_map=units
    )
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
        unit_map=[CornerUnit(row=0, col=0, corners=corners, leg="1/3")],
    )
    return two_fabric_quilt(region, "b", "c")


def geese_row() -> Quilt:
    # MATH.md V-TRI-05: geese finished 2 x 4 in. On 2 in squares (16 eighths)
    # a goose pointing right is one square wide and two tall, so four geese
    # flying right fill a 2-row by 4-column row, each anchored on row 0.
    units = [GooseUnit(row=0, col=col, points="right", body="g", sky="s") for col in range(4)]
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
    assert quadrupled_area_by_fabric(hourglass().center) == {"n": 968, "c": 968}


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


def test_a_region_without_a_map_counts_whole_squares():
    # 2 x 3 squares of 8 eighths, three of each fabric: 3 x (4 x 8 x 8) = 768
    # each. Total 1536 = 4 x (24 x 16).
    region = GridRegion(rows=2, cols=3, cell_size=8, cells=[["r", "w", "r"], ["w", "r", "w"]])
    assert quadrupled_area_by_fabric(region) == {"r": 768, "w": 768}


@pytest.mark.parametrize("name", sorted(BLOCKS))
def test_the_areas_sum_to_the_region(name):
    # S2-4 for triangles: the parts add up exactly to the finished region.
    region = BLOCKS[name]().center
    assert sum(quadrupled_area_by_fabric(region).values()) == AREA_SCALE * region.width * region.height


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


def test_a_unit_map_read_under_version_one_is_written_as_one_point_one():
    data = json.loads(dumps(pinwheel()))
    data["schema_version"] = "1"
    assert loads(json.dumps(data)).schema_version == "1.1"


def test_version_one_point_one_without_a_map_loads_as_written():
    data = json.loads(dumps(two_fabric_quilt(GridRegion(rows=1, cols=1, cell_size=8, cells=[["a"]]), "a", "b")))
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


def plain_map(rows: int, cols: int, skip: tuple[int, int] | None = None) -> list:
    return [
        PlainUnit(row=r, col=c) for r in range(rows) for c in range(cols) if (r, c) != skip
    ]


def region(units: list, rows: int = 2, cols: int = 2, cell_size: int = 8) -> GridRegion:
    return GridRegion(
        rows=rows,
        cols=cols,
        cell_size=cell_size,
        cells=[["a"] * cols for _ in range(rows)],
        unit_map=units,
    )


def test_a_unit_fabric_missing_from_the_palette_is_refused():
    units = plain_map(2, 2, skip=(1, 1)) + [
        HstUnit(row=1, col=1, diagonal="tl_br", upper="a", lower="ghost")
    ]
    with pytest.raises(ValidationError, match=r"\['ghost'\] referenced but not in palette"):
        two_fabric_quilt(region(units), "a", "b")


@pytest.mark.parametrize(
    "unit",
    [
        GooseUnit(row=0, col=0, points="up", body="a", sky="b"),
        QstUnit(row=0, col=0, top="a", right="b", bottom="a", left="ghost"),
        CornerUnit(row=0, col=0, corners={"top_left": "ghost"}, leg="1/2"),
    ],
)
def test_every_part_fabric_is_checked(unit):
    # A goose up at (0, 0) covers (0, 0) and (0, 1). Each unit names one
    # fabric outside the palette, except the goose, whose palette lacks "b".
    covered = set(unit.squares())
    units = [unit] + [PlainUnit(row=r, col=c) for r in range(2) for c in range(2) if (r, c) not in covered]
    quilt_fabrics = ("a", "c") if isinstance(unit, GooseUnit) else ("a", "b")
    with pytest.raises(ValidationError, match="not in palette"):
        two_fabric_quilt(region(units), *quilt_fabrics)


def test_a_unit_outside_the_grid_is_refused():
    with pytest.raises(ValidationError, match=r"row 2, col 0 .*outside the 2 x 2 grid"):
        region(plain_map(2, 2) + [PlainUnit(row=2, col=0)])


@pytest.mark.parametrize(
    ("unit", "rows", "cols"),
    [
        # Up or down lies across: at the last of 3 columns its second square
        # would be column 3, outside the grid.
        (GooseUnit(row=0, col=2, points="up", body="a", sky="a"), 1, 3),
        (GooseUnit(row=0, col=2, points="down", body="a", sky="a"), 1, 3),
        # Left or right lies down: at the last of 3 rows its second square
        # would be row 3.
        (GooseUnit(row=2, col=0, points="left", body="a", sky="a"), 3, 1),
        (GooseUnit(row=2, col=0, points="right", body="a", sky="a"), 3, 1),
    ],
)
def test_a_goose_must_cover_two_squares_of_the_grid(unit, rows, cols):
    others = [PlainUnit(row=r, col=c) for r in range(rows) for c in range(cols) if (r, c) != (unit.row, unit.col)]
    with pytest.raises(ValidationError, match="outside the"):
        region(others + [unit], rows=rows, cols=cols)


def test_a_goose_covers_its_square_and_the_next():
    # Up and down lie across two columns; left and right down two rows.
    assert GooseUnit(row=1, col=2, points="up", body="a", sky="b").squares() == [(1, 2), (1, 3)]
    assert GooseUnit(row=1, col=2, points="down", body="a", sky="b").squares() == [(1, 2), (1, 3)]
    assert GooseUnit(row=1, col=2, points="left", body="a", sky="b").squares() == [(1, 2), (2, 2)]
    assert GooseUnit(row=1, col=2, points="right", body="a", sky="b").squares() == [(1, 2), (2, 2)]


def test_a_square_covered_twice_is_refused():
    # The goose at (0, 0) pointing up also covers (0, 1), which a plain unit holds.
    units = plain_map(2, 2, skip=(0, 0)) + [GooseUnit(row=0, col=0, points="up", body="a", sky="a")]
    with pytest.raises(ValidationError, match=r"row 0, col 1 is covered by 2 units"):
        region(units)


def test_a_square_no_unit_covers_is_refused():
    with pytest.raises(ValidationError, match=r"row 1, col 1 is covered by no unit"):
        region(plain_map(2, 2, skip=(1, 1)))


def test_a_corner_leg_must_land_on_a_whole_eighth():
    # 1/3 of an 8-eighth square is 8/3 eighths, which no rotary cut can make
    # (MATH.md F14 cuts the corner square at leg + 1/2 in). On a 12-eighth
    # square the same leg is 4 eighths and is accepted.
    unit = CornerUnit(row=0, col=0, corners={"top_left": "a"}, leg="1/3")
    with pytest.raises(ValidationError, match="whole number of eighths"):
        region([unit], rows=1, cols=1, cell_size=8)
    assert region([unit], rows=1, cols=1, cell_size=12).unit_map == [unit]


def test_corner_legs_along_one_side_total_at_most_the_side():
    # PATTERN-SPEC S5.3: two corners on the top side at 1/2 each total 1, the
    # whole side, and are accepted; at 2/3 each they total 4/3 and overlap.
    both_top = {"top_left": "a", "top_right": "a"}
    assert CornerUnit(row=0, col=0, corners=both_top, leg="1/2").leg == Fraction(1, 2)
    with pytest.raises(ValidationError, match="total more than"):
        CornerUnit(row=0, col=0, corners=both_top, leg="2/3")
    # Corners on opposite ends of a diagonal share no side, so 2/3 fits.
    diagonal = {"top_left": "a", "bottom_right": "a"}
    assert CornerUnit(row=0, col=0, corners=diagonal, leg="2/3").leg == Fraction(2, 3)


@pytest.mark.parametrize("leg", ["0/1", "4/3", "2/6", "1/0", "1/3 ", "one third", 0.5, 1])
def test_a_corner_leg_is_a_lowest_terms_fraction_of_the_side(leg):
    with pytest.raises(ValidationError, match="leg"):
        CornerUnit(row=0, col=0, corners={"top_left": "a"}, leg=leg)


def test_a_corner_leg_may_be_given_as_a_fraction():
    unit = CornerUnit(row=0, col=0, corners={"top_left": "a"}, leg=Fraction(1, 4))
    assert json.loads(unit.model_dump_json())["leg"] == "1/4"


def test_a_corner_unit_needs_a_corner():
    with pytest.raises(ValidationError, match="corners"):
        CornerUnit(row=0, col=0, corners={}, leg="1/2")


def test_an_unknown_corner_or_kind_is_refused():
    with pytest.raises(ValidationError, match="corners"):
        CornerUnit(row=0, col=0, corners={"middle": "a"}, leg="1/2")
    with pytest.raises(ValidationError, match="curve"):
        GridRegion.model_validate(
            {"rows": 1, "cols": 1, "cell_size": 8, "cells": [["a"]],
             "unit_map": [{"kind": "curve", "row": 0, "col": 0}]}
        )
