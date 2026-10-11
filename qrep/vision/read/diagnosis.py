"""Typed outcomes that stop the confirmed read.

A read that cannot go on returns a Diagnosis value. Callers branch on its
code, never on message text, because the old pipeline derived its failure
reason by matching exception text and broke when the text changed
(vision-18). The bridge (B2b) turns a code into a hold or a refusal reason,
and the web (C3) owns the words a user sees.
"""

from dataclasses import dataclass
from typing import Literal, get_args

Code = Literal[
    # A corner lies outside the image; corner names it.
    "corner_outside_image",
    # The corners run counterclockwise on screen, so two are swapped.
    "corner_order",
    # The quad is concave or crosses itself.
    "not_convex",
    # Two corners coincide or three lie on one line.
    "degenerate_quad",
    # A count below 1.
    "bad_counts",
    # A border band whose width is not a positive number.
    "no_field",
    # The field holds fewer source pixels per square than the floor.
    "too_few_pixels",
]
CODES: tuple[str, ...] = get_args(Code)


@dataclass(frozen=True)
class Diagnosis:
    code: Code
    message: str
    corner: str | None = None
    pixels_per_square: float | None = None

    def __post_init__(self):
        if self.code not in CODES:
            raise ValueError(f"unknown diagnosis code {self.code!r}, expected one of {CODES}")
        if (self.code == "corner_outside_image") != (self.corner is not None):
            raise ValueError("a corner is named by corner_outside_image, and only by it")
        if (self.code == "too_few_pixels") != (self.pixels_per_square is not None):
            raise ValueError("pixels_per_square goes with too_few_pixels, and only with it")
