"""Unit map: what each square of a grid region is made of.

A grid region's cells give one fabric per square. Its optional unit map says
how each square is pieced, one unit per square, except a flying goose, which
covers two. Every unit sits at the row and column of its top-left square and
states a confidence in [0, 1]: a read's confidence in its classification and
parts, or 1.0 for a hand-authored map. It has no default, so a read cannot
store a guess as certain by leaving it out. The cells keep one fabric per
square for code that reads only the cells.

Each square has one spelling: the region keeps its map in row-major order,
corners keep one order, and a unit that a simpler kind writes is refused (an
hst or goose in one fabric, a qst that is an hst or plain, a corner in its base
fabric, a corner leg of the whole side).

- plain: one fabric, the square's cell.
- hst: two halves split by a diagonal, tl_br (top-left to bottom-right) or
  tr_bl; upper is the half that holds the top edge, lower the other.
- qst: four quarters, one fabric each: top, right, bottom and left.
- corner: a snowball square; each corner with a triangle names its fabric,
  every triangle has the same leg as a fraction of the side, and the base is
  the square's cell.
- goose: a flying goose over two squares, body and sky fabrics. One pointing
  up or down lies across its square and the next column; one pointing left or
  right lies down its square and the next row.

Areas: a quarter-square triangle's quarter of an odd square has a doubled
area of s * s / 2, which is not a whole number of square eighths (11 eighths:
60.5). Quadrupled areas are whole for every kind, so the area check counts in
quadrupled square eighths (AREA_SCALE) and stays exact.
"""

import re
from fractions import Fraction
from math import gcd
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    PlainSerializer,
    PlainValidator,
    ValidationError,
    field_validator,
    model_validator,
)

if TYPE_CHECKING:
    from qrep.model.schema import GridRegion

AREA_SCALE = 4

Corner = Literal["top_left", "top_right", "bottom_right", "bottom_left"]

_SIDES = (
    ("top", ("top_left", "top_right")),
    ("right", ("top_right", "bottom_right")),
    ("bottom", ("bottom_left", "bottom_right")),
    ("left", ("top_left", "bottom_left")),
)

CORNER_ORDER: tuple[Corner, ...] = ("top_left", "top_right", "bottom_right", "bottom_left")

_LEG_RE = re.compile(r"([1-9][0-9]*)/([1-9][0-9]*)")


def _leg(value: object) -> Fraction:
    # One spelling per value, "p/q" in lowest terms, so a map read and written
    # again keeps its text; a float could not hold 1/3 exactly.
    if isinstance(value, Fraction):
        leg = value
    elif isinstance(value, str) and (match := _LEG_RE.fullmatch(value)):
        num, den = int(match[1]), int(match[2])
        if gcd(num, den) != 1:
            raise ValueError(f"corner leg {value!r} must be a fraction in lowest terms")
        leg = Fraction(num, den)
    else:
        raise ValueError(f'corner leg must be a fraction of the side such as "1/3", got {value!r}')
    if leg <= 0:
        raise ValueError(f"corner leg {leg} must be more than 0")
    if leg >= 1:
        # A whole-side corner is half the square, which the hst kind writes.
        raise ValueError(f"corner leg {leg} must be less than the whole side")
    return leg


Leg = Annotated[
    Fraction,
    PlainValidator(_leg),
    PlainSerializer(lambda leg: f"{leg.numerator}/{leg.denominator}", return_type=str),
]

# Strict, so JSON true or "0.5" is refused instead of read as a number.
Confidence = Annotated[float, Field(ge=0.0, le=1.0, strict=True)]
# Strict, so JSON true is not read as square 1 and rewritten as 1.
Index = Annotated[int, Field(ge=0, strict=True)]


class PlainUnit(BaseModel):
    kind: Literal["plain"] = "plain"
    row: Index
    col: Index
    confidence: Confidence

    def squares(self) -> list[tuple[int, int]]:
        return [(self.row, self.col)]

    def fabric_ids(self) -> set[str]:
        return set()


class HstUnit(BaseModel):
    kind: Literal["hst"] = "hst"
    row: Index
    col: Index
    diagonal: Literal["tl_br", "tr_bl"]
    upper: str = Field(description="fabric of the half that holds the top edge")
    lower: str = Field(description="fabric of the half that holds the bottom edge")
    confidence: Confidence

    @model_validator(mode="after")
    def _two_fabrics(self) -> "HstUnit":
        if self.upper == self.lower:
            raise ValueError(f"an hst in one fabric ({self.upper}) is a plain square")
        return self

    def squares(self) -> list[tuple[int, int]]:
        return [(self.row, self.col)]

    def fabric_ids(self) -> set[str]:
        return {self.upper, self.lower}


class QstUnit(BaseModel):
    kind: Literal["qst"] = "qst"
    row: Index
    col: Index
    top: str
    right: str
    bottom: str
    left: str
    confidence: Confidence

    @model_validator(mode="after")
    def _not_a_simpler_kind(self) -> "QstUnit":
        # Top and right together are the upper half of a tl_br diagonal, top
        # and left the upper half of a tr_bl one.
        if len({self.top, self.right, self.bottom, self.left}) == 1:
            raise ValueError(f"a qst in one fabric ({self.top}) is a plain square")
        if self.top == self.right and self.bottom == self.left:
            raise ValueError("a qst whose top matches its right and bottom its left is a tl_br hst")
        if self.top == self.left and self.bottom == self.right:
            raise ValueError("a qst whose top matches its left and bottom its right is a tr_bl hst")
        return self

    def squares(self) -> list[tuple[int, int]]:
        return [(self.row, self.col)]

    def fabric_ids(self) -> set[str]:
        return {self.top, self.right, self.bottom, self.left}


class CornerUnit(BaseModel):
    kind: Literal["corner"] = "corner"
    row: Index
    col: Index
    corners: dict[Corner, str] = Field(min_length=1, description="fabric of each corner triangle")
    leg: Leg = Field(description="leg of every corner triangle, as a fraction of the side")
    confidence: Confidence

    @field_validator("corners")
    @classmethod
    def _corners_in_order(cls, v: dict[Corner, str]) -> dict[Corner, str]:
        # One order, so equal units write the same bytes.
        return {corner: v[corner] for corner in CORNER_ORDER if corner in v}

    @model_validator(mode="after")
    def _corners_fit_each_side(self) -> "CornerUnit":
        # PATTERN-SPEC S5.3: the legs along one side total at most the side,
        # so no two triangles overlap and the base keeps a whole area.
        for side, ends in _SIDES:
            total = self.leg * sum(1 for end in ends if end in self.corners)
            if total > 1:
                raise ValueError(
                    f"corner legs along the {side} side total more than the side ({total})"
                )
        return self

    def squares(self) -> list[tuple[int, int]]:
        return [(self.row, self.col)]

    def fabric_ids(self) -> set[str]:
        return set(self.corners.values())


class GooseUnit(BaseModel):
    kind: Literal["goose"] = "goose"
    row: Index
    col: Index
    points: Literal["up", "down", "left", "right"]
    body: str
    sky: str
    confidence: Confidence

    @model_validator(mode="after")
    def _two_fabrics(self) -> "GooseUnit":
        if self.body == self.sky:
            raise ValueError(f"a goose in one fabric ({self.body}) is two plain squares")
        return self

    @property
    def horizontal(self) -> bool:
        return self.points in ("up", "down")

    def squares(self) -> list[tuple[int, int]]:
        if self.horizontal:
            return [(self.row, self.col), (self.row, self.col + 1)]
        return [(self.row, self.col), (self.row + 1, self.col)]

    def fabric_ids(self) -> set[str]:
        return {self.body, self.sky}


Unit = Annotated[
    PlainUnit | HstUnit | QstUnit | CornerUnit | GooseUnit, Field(discriminator="kind")
]


def check_unit_map(
    units: list[Unit], rows: int, cols: int, cell_size: int, cells: list[list[str]]
) -> None:
    """Raise ValueError unless every unit keeps its own rules and the units
    tile the grid: each inside it, each square covered exactly once, each
    corner leg a whole number of eighths and each corner off its base fabric.
    """
    counts = [[0] * cols for _ in range(rows)]
    for unit in units:
        # model_copy and assignment skip a unit's own validation, so a unit
        # rebuilt from its fields proves its bounds, leg and side rules again.
        try:
            type(unit).model_validate(unit.model_dump())
        except ValidationError as error:
            first = error.errors()[0]
            where = ".".join(str(part) for part in first["loc"]) or "unit"
            raise ValueError(
                f"{unit.kind} unit at row {unit.row}, col {unit.col}: {where}: {first['msg']}"
            ) from None
        for r, c in unit.squares():
            if not (0 <= r < rows and 0 <= c < cols):
                raise ValueError(
                    f"{unit.kind} unit at row {unit.row}, col {unit.col} covers a square "
                    f"outside the {rows} x {cols} grid"
                )
            counts[r][c] += 1
        if isinstance(unit, CornerUnit) and (unit.leg * cell_size).denominator != 1:
            # Lengths are whole eighths, and the corner square is cut at the
            # leg plus 1/2 in (MATH.md F14), so a resize must not round it.
            raise ValueError(
                f"corner leg {unit.leg} of a {cell_size}-eighth square is "
                f"{unit.leg * cell_size} eighths, not a whole number of eighths"
            )
        if isinstance(unit, CornerUnit) and cells[unit.row][unit.col] in unit.corners.values():
            raise ValueError(
                f"corner unit at row {unit.row}, col {unit.col} has a corner in its base "
                f"fabric {cells[unit.row][unit.col]}; leave that corner out"
            )
    for r in range(rows):
        for c in range(cols):
            if counts[r][c] != 1:
                times = "no unit" if counts[r][c] == 0 else f"{counts[r][c]} units"
                raise ValueError(f"square at row {r}, col {c} is covered by {times}")


def quadrupled_area_by_fabric(region: "GridRegion") -> dict[str, int]:
    """Each fabric's finished area in the region, in quadrupled square eighths.

    The values sum to AREA_SCALE * region.width * region.height exactly. A
    region without a unit map is all plain squares. The map is checked again
    first, because model_copy and assignment skip validation, and a resize
    that left a leg off the eighths must raise here instead of rounding.
    """
    if region.unit_map is not None:
        check_unit_map(region.unit_map, region.rows, region.cols, region.cell_size, region.cells)
    s = region.cell_size
    whole = AREA_SCALE * s * s
    area: dict[str, int] = {}

    def add(fabric_id: str, amount: int) -> None:
        area[fabric_id] = area.get(fabric_id, 0) + amount

    if region.unit_map is None:
        for row in region.cells:
            for fabric_id in row:
                add(fabric_id, whole)
        return area
    for unit in region.unit_map:
        cell = region.cells[unit.row][unit.col]
        if isinstance(unit, PlainUnit):
            add(cell, whole)
        elif isinstance(unit, HstUnit):
            add(unit.upper, whole // 2)
            add(unit.lower, whole // 2)
        elif isinstance(unit, QstUnit):
            for fabric_id in (unit.top, unit.right, unit.bottom, unit.left):
                add(fabric_id, whole // 4)
        elif isinstance(unit, CornerUnit):
            leg = int(unit.leg * s)
            # A corner triangle with legs leg x leg: area leg^2 / 2.
            triangle = AREA_SCALE * leg * leg // 2
            for fabric_id in unit.corners.values():
                add(fabric_id, triangle)
            add(cell, whole - triangle * len(unit.corners))
        else:
            # Over two squares: the body is half the goose, each sky triangle
            # (legs s and s) a quarter.
            add(unit.body, whole)
            add(unit.sky, whole)
    return area
