"""Finished sizing in one place: the square sizes the pattern offers, border
snapping, the reconcile of a requested size, and size_pattern (A10, #132).

All lengths are integer eighths. Cells are square and border bands add
identically to both axes, so a quilt cannot take an arbitrary W x H:
W - H = (cols - rows) * cell_size exactly. Sizing never changes the counts,
so the size moves in whole squares and whole blocks; changing the block
count to reach a size is editing, not sizing.

The pattern rule (a square step in whole quarter inches): each offered square
gives an achieved size, the squares plus the borders scaled to that square
and snapped; pick the square whose combined miss, the sum of the misses on
the axes you set, is smallest. When two squares miss by the same amount, the
larger wins, the half-up direction round_div rounds. Offered squares run in
1/4 in steps (SQUARE_STEP), narrowed to those that keep every corner leg a
whole eighth, and borders snap to 1/4 in, so square, border and plain-piece
cut sizes are whole quarter inches. Triangle cut sizes follow MATH.md F14:
an exact half-square triangle cuts at F + 7/8 in, never a whole quarter.

The one-eighth step is the sprint 3 reconcile for its callers (the crop-screen
size and the editor's size edit): the exact cell rounded half-up per axis,
the smaller of the two, borders to the eighth. Both rules use the frozen
clamps and cap borders at BAND_MAX (PARITY item 4; REBASELINE.md literals B8
to B10, and C3 for the band cap): a size of at least 1 e outside them returns
the size at the clamp with its miss reported, not an error. Callers receive
{requested, achieved}, and the model records both in its size basis.
"""

from math import lcm

from qrep.contract import SizeBasis, SizeRequest, SizeResult
from qrep.model.schema import FinishedSizeBasis, Quilt
from qrep.model.unitmap import CornerUnit

# Standard quilt sizes, finished inches converted to eighths (w, h).
PRESETS = (
    ("Crib", 36 * 8, 52 * 8),
    ("Throw", 50 * 8, 65 * 8),
    ("Twin", 70 * 8, 90 * 8),
    ("Full", 84 * 8, 90 * 8),
    ("Queen", 90 * 8, 108 * 8),
    ("King", 110 * 8, 108 * 8),
)

CELL_MIN = 6  # 3/4"
CELL_MAX = 32  # 4"
BAND_FLOOR = 2  # 1/4"
BAND_MAX = 112  # 14", the bridge's band cap, which the model lacked
# A setting, not a formula: the step the finished square size snaps to on the
# pattern path. The size basis records it as its rounding step, or the
# coarser step a corner leg needs. It must be a multiple of 1/4 in, or cut
# sizes stop being whole quarter inches; the pattern path refuses any other.
SQUARE_STEP = 2  # 1/4"
BORDER_STEP = 2  # 1/4"

# A read that recorded no confidence for its size estimate assumed a pixel
# resolution, which measures nothing about the quilt's physical size.
UNMEASURED_ESTIMATE = 0.0


def round_div(a: int, b: int) -> int:
    """Half-up integer division for a >= 0, b > 0; JS mirrors this exactly as
    Math.floor((a + Math.floor(b / 2)) / b). Never use round(): Python rounds
    half to even and JS Math.round differs at negative halves."""
    return (a + b // 2) // b


def square_sizes(step: int | None = None) -> tuple[int, ...]:
    """The finished square sizes offered: every multiple of step (default
    SQUARE_STEP) from CELL_MIN to CELL_MAX."""
    step = SQUARE_STEP if step is None else step
    sizes = tuple(s for s in range(CELL_MIN, CELL_MAX + 1) if step > 0 and s % step == 0)
    if not sizes:
        raise ValueError(
            f"a square step of {step} e offers no size between {CELL_MIN} and {CELL_MAX} e"
        )
    return sizes


def snap_border(width: int) -> int:
    """A chosen border width to the nearest 1/4 in, half-up, at most
    BAND_MAX. Any width of at least one eighth rounds to at least
    BAND_FLOOR."""
    if width < 1:
        raise ValueError(f"a border width must be at least 1 e, got {width}")
    return min(BAND_MAX, BORDER_STEP * round_div(width, BORDER_STEP))


def _pattern_band(width0: int, cell0: int, square: int) -> int:
    """A band scaled with the square (the PARITY locked-resize rule), then
    snapped half-up to 1/4 in within [BAND_FLOOR, BAND_MAX]."""
    scaled = BORDER_STEP * round_div(width0 * square, cell0 * BORDER_STEP)
    return max(BAND_FLOOR, min(BAND_MAX, scaled))


def _fits_units(quilt: Quilt, square: int) -> bool:
    """A corner leg must stay a whole number of eighths at the square size
    (qrep/model/unitmap.py), because its cut size cannot be rounded."""
    units = quilt.center.unit_map or []
    return all(
        (unit.leg * square).denominator == 1 for unit in units if isinstance(unit, CornerUnit)
    )


def _square_step(quilt: Quilt, step: int) -> int:
    """The step the offered squares actually move in: a leg p/q in lowest
    terms is whole on multiples of q, so the squares are the multiples of
    lcm(step, every leg's q)."""
    units = quilt.center.unit_map or []
    return lcm(step, *(unit.leg.denominator for unit in units if isinstance(unit, CornerUnit)))


def _check_pattern_step(step: int) -> None:
    if step < 1 or step % BORDER_STEP:
        raise ValueError(
            f"a pattern square step must be a whole quarter inch ({BORDER_STEP} e), got {step} e"
        )


def offered_squares(quilt: Quilt, step: int | None = None) -> tuple[int, ...]:
    """The finished square sizes the pattern offers this quilt: square_sizes(step)
    narrowed to the sizes that keep every corner leg a whole eighth. Raises
    for a step that is not a whole quarter inch, and when a leg leaves no
    size, because the pattern cannot size that quilt."""
    step = SQUARE_STEP if step is None else step
    _check_pattern_step(step)
    whole = _square_step(quilt, step)
    sizes = tuple(square for square in square_sizes(step) if square % whole == 0)
    if not sizes:
        raise ValueError(
            f"no square size in {step} e steps keeps this quilt's corner legs whole eighths: "
            f"they need a multiple of {whole} e, and the largest square is {CELL_MAX} e"
        )
    return sizes


def _nearest_square(
    width: int | None,
    height: int | None,
    cols: int,
    rows: int,
    bands0: list[int],
    cell0: int,
    sizes: tuple[int, ...],
) -> int:
    best, best_miss = sizes[0], None
    for square in sizes:
        border = 2 * sum(_pattern_band(b, cell0, square) for b in bands0)
        miss = 0
        if width is not None:
            miss += abs(cols * square + border - width)
        if height is not None:
            miss += abs(rows * square + border - height)
        # Sizes ascend, so <= hands a tie to the larger square.
        if best_miss is None or miss <= best_miss:
            best, best_miss = square, miss
    return best


def _sprint3_cell(target: int, cells: int, cell0: int, band_total0: int) -> int:
    """Cell size (eighths) whose scaled quilt best meets one axis target.

    Bands scale with the cell (the PARITY locked-resize rule), so the
    finished extent is cells*cell + 2*band_total0*(cell/cell0); solving for
    cell gives target*cell0 / (cells*cell0 + 2*band_total0)."""
    if band_total0 > 0:
        return round_div(target * cell0, cells * cell0 + 2 * band_total0)
    return round_div(target, cells)


def _reconcile(
    quilt: Quilt, width: int | None, height: int | None, step: int
) -> tuple[Quilt, dict, dict, int]:
    """apply_finished_size without the basis, plus the step it applied."""
    if width is None and height is None:
        raise ValueError("apply_finished_size needs a width or a height")
    for name, value in (("width", width), ("height", height)):
        if value is not None and value < 1:
            raise ValueError(f"a finished {name} must be at least 1 e, got {value}")
    rows, cols = quilt.center.rows, quilt.center.cols
    cell0 = quilt.center.cell_size
    bands0 = [band.width for band in quilt.borders]

    if step == 1:
        band_total0 = sum(bands0)
        candidates = []
        if width is not None:
            candidates.append(_sprint3_cell(width, cols, cell0, band_total0))
        if height is not None:
            candidates.append(_sprint3_cell(height, rows, cell0, band_total0))
        cell = max(CELL_MIN, min(CELL_MAX, min(candidates)))
        if not _fits_units(quilt, cell):
            raise ValueError(
                f"a {cell} e square leaves a corner leg off whole eighths; size the pattern "
                "in its own square steps"
            )
        # Capping changes no cell pick; it changes only a band past 14 in.
        new_bands = [max(BAND_FLOOR, min(BAND_MAX, round_div(w * cell, cell0))) for w in bands0]
        applied = 1
    else:
        sizes = offered_squares(quilt, step)
        cell = _nearest_square(width, height, cols, rows, bands0, cell0, sizes)
        new_bands = [_pattern_band(w, cell0, cell) for w in bands0]
        applied = _square_step(quilt, step)

    updated = quilt.model_copy(deep=True)
    updated.center.cell_size = cell
    for band, new_width in zip(updated.borders, new_bands):
        band.width = new_width
    updated.size_basis = None
    band_total = sum(new_bands)

    achieved = {
        "width": cols * cell + 2 * band_total,
        "height": rows * cell + 2 * band_total,
        "cell_size": cell,
        "borders": new_bands,
    }
    requested = {"width": width, "height": height}
    return updated, requested, achieved, applied


def apply_finished_size(
    quilt: Quilt, width: int | None, height: int | None, step: int = 1
) -> tuple[Quilt, dict, dict]:
    """Reconcile a finished size you entered onto the quilt's grid.

    width/height are integer eighths, at least 1; either may be None. step is
    the square size step in eighths: 1, the default, is the sprint 3
    reconcile; a step in whole quarter inches is the pattern rule (the module
    docstring has both). Returns (updated quilt, requested, achieved). A size
    outside the clamps returns the size at the clamp with its miss. Raises
    ValueError with no width and no height, for a size below 1 e, for a step
    that is neither 1 nor a whole quarter inch, and when no square keeps
    every corner leg whole (at step 1, when the reconciled square breaks
    one).

    Every caller passes a size you entered (the crop-screen size and the
    editor's size edit), so the updated quilt records a typed size basis at
    1.0 with the step applied; a basis the old size had cannot describe the
    new one. A preset chip on those screens arrives as a width and height, so
    it is recorded as typed too, until #244."""
    updated, requested, achieved, applied = _reconcile(quilt, width, height, step)
    updated.size_basis = FinishedSizeBasis(
        source="typed",
        requested_width=width,
        requested_height=height,
        achieved_width=achieved["width"],
        achieved_height=achieved["height"],
        rounding_step=applied,
        confidence=1.0,
    )
    return updated, requested, achieved


def size_at(
    quilt: Quilt, square: int, borders: list[int] | None = None, step: int | None = None
) -> Quilt:
    """The quilt at a chosen finished square size and border widths.

    square must be one of offered_squares(quilt, step). borders gives one
    width per band, each snapped to 1/4 in; None keeps the model's widths,
    snapped. The counts never change, so the achieved size, the returned
    quilt's finished width and height, moves in whole squares and blocks.
    The returned quilt carries no size basis: the basis has no source for a
    chosen square yet (#240)."""
    step = SQUARE_STEP if step is None else step
    offered = offered_squares(quilt, step)
    if square not in offered:
        reason = (
            "leaves a corner leg off whole eighths"
            if square in square_sizes(step)
            else "is not offered"
        )
        raise ValueError(f"a finished square of {square} e {reason}; choose one of {list(offered)}")
    widths = [band.width for band in quilt.borders] if borders is None else list(borders)
    if len(widths) != len(quilt.borders):
        raise ValueError(f"{len(widths)} border widths given for {len(quilt.borders)} border bands")
    snapped = [snap_border(width) for width in widths]
    updated = quilt.model_copy(deep=True)
    updated.center.cell_size = square
    for band, width in zip(updated.borders, snapped):
        band.width = width
    updated.size_basis = None
    return updated


def _preset_size(name: str, quilt: Quilt) -> tuple[int, int]:
    """The preset's size in the orientation suggest_preset matches it in.

    suggest_preset (qrep/model/finished_size.py) compares long side over
    short side, so it pairs the quilt's long side with the preset's. A preset
    listed the other way round from the quilt is turned to fit that pairing;
    a square quilt takes it as listed, since turning cannot change its miss."""
    for preset, width, height in PRESETS:
        if preset == name:
            if (width - height) * (quilt.finished_width - quilt.finished_height) < 0:
                return height, width
            return width, height
    names = ", ".join(preset for preset, _w, _h in PRESETS)
    raise ValueError(f"unknown preset {name!r}; presets: {names}")


def _hand_authored(quilt: Quilt) -> bool:
    """Authored provenance with every recorded confidence at 1.0. A missing
    provenance defaults to authored, so a read's own confidences decide."""
    if quilt.provenance.source != "authored":
        return False
    if any(value != 1.0 for value in quilt.provenance.effective_stage_confidence().values()):
        return False
    if any(value != 1.0 for row in quilt.center.effective_cell_confidence() for value in row):
        return False
    return all(unit.confidence == 1.0 for unit in quilt.center.unit_map or [])


def _estimate_confidence(quilt: Quilt) -> float:
    """The confidence of the size a default request keeps: the estimate's own,
    1.0 for a hand-authored model, and UNMEASURED_ESTIMATE otherwise."""
    basis = quilt.size_basis
    if basis is not None:
        if basis.source != "default":
            raise ValueError(
                f"this model's size was set by a {basis.source} size, so it holds no photo "
                "estimate to label as one; send that size as a typed or preset request, or "
                "size the model the read returned"
            )
        return basis.confidence
    return 1.0 if _hand_authored(quilt) else UNMEASURED_ESTIMATE


def size_pattern(quilt: Quilt, request: SizeRequest) -> SizeResult:
    """Sizes the pattern for the size you set, for the bridge's size_pattern
    (SPEC.md section 6.3): a typed or preset size snaps by the pattern rule in
    1/4 in squares, a preset with its long side along the quilt's long side,
    and the default fits the model's own estimate the same way. Returns the
    sized model, whose size basis matches its finished size, and that basis.
    Raises ValueError for an unknown preset, a default on a model whose basis
    records a size you set, and a corner leg no offered square keeps whole;
    the bridge returns each as kind value."""
    if request.source == "typed":
        width, height = request.width, request.height
        confidence = 1.0
    elif request.source == "preset":
        width, height = _preset_size(request.preset, quilt)
        confidence = 1.0
    else:
        width, height = quilt.finished_width, quilt.finished_height
        confidence = _estimate_confidence(quilt)

    # Step 1 would select the sprint 3 reconcile, whose borders round to the
    # eighth, so the pattern step is checked before _reconcile sees it.
    _check_pattern_step(SQUARE_STEP)
    sized, _requested, _achieved, applied = _reconcile(quilt, width, height, SQUARE_STEP)
    if request.source == "default":
        width = height = None
    sized.size_basis = FinishedSizeBasis(
        source=request.source,
        requested_width=width,
        requested_height=height,
        achieved_width=sized.finished_width,
        achieved_height=sized.finished_height,
        rounding_step=applied,
        confidence=confidence,
    )
    basis = SizeBasis(
        source=request.source,
        requested_width=width,
        requested_height=height,
        achieved_width=sized.finished_width,
        achieved_height=sized.finished_height,
    )
    return SizeResult(outcome="sized", model=sized, basis=basis)
