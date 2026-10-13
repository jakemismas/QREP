"""Finished sizing in one place: the square sizes the pattern offers, border
snapping, the reconcile of a requested size, and size_pattern (A10, #132).

All lengths are integer eighths. Cells are square and border bands add
identically to both axes, so a quilt cannot take an arbitrary W x H:
W - H = (cols - rows) * cell_size exactly. Sizing never changes the counts,
so the size moves in whole squares and whole blocks; changing the block
count to reach a size is editing, not sizing.

The pattern rule (any square step but the sprint 3 one-eighth step): on each
requested axis, pick the offered square whose achieved extent (the squares
plus the borders scaled to that square and snapped) is nearest the request;
when two squares miss by the same amount, the larger wins, the half-up
direction round_div rounds. With both axes given, take the smaller of the two
squares, so the quilt never grows past one asked-for side to come closer to
the other. Offered squares run in 1/4 in steps (SQUARE_STEP) and borders snap
to 1/4 in, so every square's cut size is a whole quarter inch.

The one-eighth step is the sprint 3 reconcile, kept exactly for its callers
(the crop-screen size and the editor's size edit): the exact cell rounded
half-up per axis, the smaller of the two, borders to the eighth. Both rules
use the frozen clamps (PARITY item 4; REBASELINE.md literals B8 to B10, and
C3 for the pattern's band cap): an entry outside them returns the size at the
clamp with its miss reported, never an error. Callers receive {requested,
achieved}; size_pattern also stores both in the model's size basis.
"""

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
# pattern path, recorded in the size basis as its rounding step. Keep it a
# multiple of 1/4 in, or cut sizes stop being whole quarter inches.
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


def _offered(quilt: Quilt, step: int) -> list[int]:
    sizes = [square for square in square_sizes(step) if _fits_units(quilt, square)]
    if not sizes:
        raise ValueError(
            f"no square size in {step} e steps keeps this quilt's corner legs whole eighths"
        )
    return sizes


def _nearest_square(
    target: int, cells: int, bands0: list[int], cell0: int, sizes: list[int]
) -> int:
    # The extent rises with the square, so the misses fall, then rise, and a
    # tie can only fall between the two sizes either side of the request.
    best, best_miss = sizes[0], None
    for square in sizes:
        extent = cells * square + 2 * sum(_pattern_band(b, cell0, square) for b in bands0)
        miss = abs(extent - target)
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


def apply_finished_size(
    quilt: Quilt, width: int | None, height: int | None, step: int = 1
) -> tuple[Quilt, dict, dict]:
    """Reconcile a requested finished size onto the quilt's grid.

    width/height are integer eighths; either may be None. step is the square
    size step in eighths: 1, the default, is the sprint 3 reconcile; any
    other step is the pattern rule (the module docstring has both). Returns
    (updated quilt, requested, achieved). Never raises for out-of-range
    requests: the clamps and the misses are the honest answer. The updated
    quilt carries no size basis, because the old one no longer describes it;
    size_pattern writes a new one."""
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
        if not candidates:
            raise ValueError("apply_finished_size needs a width or a height")
        cell = max(CELL_MIN, min(CELL_MAX, min(candidates)))
        if not _fits_units(quilt, cell):
            raise ValueError(
                f"a {cell} e square leaves a corner leg off whole eighths; size the pattern "
                "in its own square steps"
            )
        new_bands = [max(BAND_FLOOR, round_div(w * cell, cell0)) for w in bands0]
    else:
        sizes = _offered(quilt, step)
        candidates = []
        if width is not None:
            candidates.append(_nearest_square(width, cols, bands0, cell0, sizes))
        if height is not None:
            candidates.append(_nearest_square(height, rows, bands0, cell0, sizes))
        if not candidates:
            raise ValueError("apply_finished_size needs a width or a height")
        cell = min(candidates)
        new_bands = [_pattern_band(w, cell0, cell) for w in bands0]

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
    return updated, requested, achieved


def size_at(
    quilt: Quilt, square: int, borders: list[int] | None = None, step: int | None = None
) -> Quilt:
    """The quilt at a chosen finished square size and border widths.

    square must be one of square_sizes(step) and keep every corner leg whole.
    borders gives one width per band, each snapped to 1/4 in; None keeps the
    model's widths, snapped. The counts never change, so the achieved size,
    the returned quilt's finished width and height, moves in whole squares
    and blocks. The returned quilt carries no size basis: the basis has no
    source for a chosen square yet."""
    offered = square_sizes(step)
    if square not in offered:
        raise ValueError(
            f"a finished square of {square} e is not offered; choose one of {list(offered)}"
        )
    if not _fits_units(quilt, square):
        raise ValueError(f"a {square} e square leaves a corner leg off whole eighths")
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


def _preset_size(name: str) -> tuple[int, int]:
    for preset, width, height in PRESETS:
        if preset == name:
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
                "estimate to label as one; size the model the read returned"
            )
        return basis.confidence
    return 1.0 if _hand_authored(quilt) else UNMEASURED_ESTIMATE


def size_pattern(quilt: Quilt, request: SizeRequest) -> SizeResult:
    """Sizes the pattern for the size you set, for the bridge's size_pattern
    (SPEC.md section 6.3): a typed or preset size snaps by the pattern rule in
    1/4 in squares, and the default fits the model's own estimate the same
    way. Returns the sized model, whose size basis matches its finished size,
    and that basis."""
    if request.source == "typed":
        width, height = request.width, request.height
        confidence = 1.0
    elif request.source == "preset":
        width, height = _preset_size(request.preset)
        confidence = 1.0
    else:
        width, height = quilt.finished_width, quilt.finished_height
        confidence = _estimate_confidence(quilt)

    sized, _requested, _achieved = apply_finished_size(quilt, width, height, step=SQUARE_STEP)
    if request.source == "default":
        width = height = None
    sized.size_basis = FinishedSizeBasis(
        source=request.source,
        requested_width=width,
        requested_height=height,
        achieved_width=sized.finished_width,
        achieved_height=sized.finished_height,
        rounding_step=SQUARE_STEP,
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
