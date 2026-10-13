"""Simulated confirmations (plan 7.2): what a user would confirm, with pin error.

Corners come from the annotation, each moved by the jitter radius in its own
random direction; counts are the truth's, or one of the miscount variants G3
scores; the scope picker's answer is always "Works with these", refusals
included, so G4 measures the read's own detection rather than the picker.
Until D10 measures the pin radius, every radius in RADII_PX is reported.
"""

import math
import random
from dataclasses import dataclass

from qrep.contract import Counts

RADII_PX = (0, 2, 4, 6, 8)
PICKER_ANSWER = "Works with these"

Point = tuple[float, float]


def jitter(corners: list[Point], radius: float, rng: random.Random, *, bounds: tuple[int, int]) -> list[Point]:
    """Move each corner radius px in a direction drawn from rng, then keep it on the
    image (bounds is its width and height): a tap cannot land off the photo."""
    if radius == 0:
        return [(float(x), float(y)) for x, y in corners]
    width, height = bounds
    moved = []
    for x, y in corners:
        angle = rng.uniform(0.0, 2 * math.pi)
        nx, ny = x + radius * math.cos(angle), y + radius * math.sin(angle)
        moved.append((min(max(nx, 0.0), float(width)), min(max(ny, 0.0), float(height))))
    return moved


@dataclass(frozen=True)
class CornerTrial:
    radius_px: float
    trial: int
    corners: list[Point]
    # Each corner's displacement after clamping, which falls short of radius_px where
    # the photo's edge stopped it.
    moved_px: tuple[float, float, float, float]
    picker: str = PICKER_ANSWER


def corner_trials(
    corners: list[Point], radii: tuple[float, ...], trials: int, key: str, *, bounds: tuple[int, int]
) -> list[CornerTrial]:
    """One trial at radius 0 and trials draws at each other radius, each seeded from
    key, radius and trial, so a rerun or a single row reproduces on its own."""
    out = []
    for radius, trial in trial_ids(radii, trials):
        rng = random.Random(f"{key}|{radius}|{trial}")
        moved = jitter(corners, radius, rng, bounds=bounds)
        out.append(CornerTrial(radius, trial, moved, tuple(_side(a, b) for a, b in zip(corners, moved))))
    return out


def trial_ids(radii: tuple[float, ...], trials: int) -> list[tuple[float, int]]:
    """The (radius, trial) pairs corner_trials draws, for rows that stand in for reads
    never made."""
    return [(radius, trial) for radius in radii for trial in range(1 if radius == 0 else trials)]


def _side(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def square_pitch(corners: list[Point], counts: Counts, band_widths: list[float]) -> float:
    """Pixels per square along the outer edge: the mean edge length across over the
    columns plus both borders, averaged with the same down."""
    tl, tr, br, bl = corners
    border = 2 * sum(band_widths)
    cols = counts.blocks_across * counts.squares_per_block_across + border
    rows = counts.blocks_down * counts.squares_per_block_down + border
    across = (_side(tl, tr) + _side(bl, br)) / 2 / cols
    down = (_side(tl, bl) + _side(tr, br)) / 2 / rows
    return (across + down) / 2


def radius_in_squares(radius: float, pitch: float) -> float:
    return radius / pitch


_AXES = (("across", "blocks_across", "squares_per_block_across"),
         ("down", "blocks_down", "squares_per_block_down"))


def miscount_variants(counts: Counts) -> tuple[list[tuple[str, Counts]], list[tuple[str, str]]]:
    """G3's miscounts of the true counts, in quilter units: one square per block more
    or fewer on either axis, one block more or fewer on either axis, half (the squares
    per block halved on both axes, or the blocks where the squares per block are odd)
    and double (twice the squares per block on both axes). A variant no count can
    express (0 blocks, or no whole half) is skipped with its reason."""
    base = counts.model_dump()
    variants: list[tuple[str, Counts]] = []
    skipped: list[tuple[str, str]] = []
    for unit, prefix in (("square", 2), ("block", 1)):
        for axis, *fields in _AXES:
            field = fields[prefix - 1]
            for step in (1, -1):
                kind = f"{unit} {step:+d} {axis}"
                value = base[field] + step
                if value < 1:
                    skipped.append((kind, f"{field} would be {value}"))
                else:
                    variants.append((kind, Counts(**{**base, field: value})))
    half = dict(base)
    for axis, blocks, squares in _AXES:
        if base[squares] % 2 == 0:
            half[squares] = base[squares] // 2
        elif base[blocks] % 2 == 0:
            half[blocks] = base[blocks] // 2
        else:
            skipped.append(("half", f"no whole half {axis}: {base[blocks]} x {base[squares]} squares"))
            break
    else:
        variants.append(("half", Counts(**half)))
    variants.append(("double", Counts(**{
        **base,
        "squares_per_block_across": base["squares_per_block_across"] * 2,
        "squares_per_block_down": base["squares_per_block_down"] * 2,
    })))
    return variants, skipped
