"""Finished sizing in one place: the square sizes the pattern offers, border
snapping, the reconcile of a requested size, and size_pattern (A10, #132).

All lengths are integer eighths. Cells are square and border bands add
identically to both axes, so a quilt cannot take an arbitrary W x H:
W - H = (cols - rows) * cell_size exactly. Sizing never changes the counts,
so the size moves in whole squares and whole blocks; changing the block
count to reach a size is editing, not sizing.

The reconcile rule: on each requested axis, pick the offered square whose
achieved extent (the squares plus the borders scaled to that square) is
nearest the request; when two squares miss by the same amount, the larger
wins, the half-up direction round_div rounds. With both axes given, take the
smaller square, so the quilt never overshoots one axis to meet the other.
The model stores only the achieved size; callers receive {requested,
achieved} for the asked-for-against-achieved presentation.

The pattern path offers squares in 1/4 in steps (SQUARE_STEP) and snaps
borders to 1/4 in, so every cut size is a whole quarter inch. The default
step of one eighth keeps the sprint 3 reconcile values
(tests/test_size_engine.py). The clamps are the frozen approval values (PARITY
item 4; REBASELINE.md literals B8 to B10, and C3 for the band cap): an entry
outside them returns the size at the clamp with its miss reported, never an
error.
"""

from qrep.contract import SizeBasis, SizeRequest, SizeResult
from qrep.model.schema import FinishedSizeBasis, Quilt

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
# pattern path, recorded in the size basis as its rounding step.
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


def square_sizes(step: int = SQUARE_STEP) -> tuple[int, ...]:
    """The finished square sizes offered: every multiple of step from
    CELL_MIN to CELL_MAX."""
    sizes = tuple(s for s in range(CELL_MIN, CELL_MAX + 1) if step > 0 and s % step == 0)
    if not sizes:
        raise ValueError(
            f"a square step of {step} e offers no size between {CELL_MIN} and {CELL_MAX} e"
        )
    return sizes


def snap_border(width: int) -> int:
    """A border width to the nearest 1/4 in, half-up, within
    [BAND_FLOOR, BAND_MAX]."""
    return max(BAND_FLOOR, min(BAND_MAX, BORDER_STEP * round_div(width, BORDER_STEP)))


def _band_at(width0: int, cell0: int, square: int, step: int) -> int:
    """A band scaled with the square (the PARITY locked-resize rule). It
    rounds to 1/4 in on the pattern path and to the eighth on the one-eighth
    path, whose sprint 3 values must hold."""
    unit = min(step, BORDER_STEP)
    scaled = unit * round_div(width0 * square, cell0 * unit)
    return max(BAND_FLOOR, min(BAND_MAX, scaled))


def _nearest_square(target: int, cells: int, bands0: list[int], cell0: int, step: int) -> int:
    best, best_miss = CELL_MIN, None
    for square in square_sizes(step):
        extent = cells * square + 2 * sum(_band_at(b, cell0, square, step) for b in bands0)
        miss = abs(extent - target)
        # Sizes ascend, so <= hands a tie to the larger square.
        if best_miss is None or miss <= best_miss:
            best, best_miss = square, miss
    return best


def apply_finished_size(
    quilt: Quilt, width: int | None, height: int | None, step: int = 1
) -> tuple[Quilt, dict, dict]:
    """Reconcile a requested finished size onto the quilt's grid.

    width/height are integer eighths; either may be None. step is the square
    size step in eighths: 1 for the sprint 3 callers, SQUARE_STEP for the
    pattern. Returns (updated quilt, requested, achieved). Never raises for
    out-of-range requests: the clamps and the misses are the honest answer.
    The updated quilt carries no size basis, because the old one no longer
    describes it; size_pattern writes a new one."""
    rows, cols = quilt.center.rows, quilt.center.cols
    cell0 = quilt.center.cell_size
    bands0 = [band.width for band in quilt.borders]

    candidates = []
    if width is not None:
        candidates.append(_nearest_square(width, cols, bands0, cell0, step))
    if height is not None:
        candidates.append(_nearest_square(height, rows, bands0, cell0, step))
    if not candidates:
        raise ValueError("apply_finished_size needs a width or a height")
    cell = min(candidates)

    updated = quilt.model_copy(deep=True)
    updated.center.cell_size = cell
    for band, width0 in zip(updated.borders, bands0):
        band.width = _band_at(width0, cell0, cell, step)
    updated.size_basis = None
    new_bands = [band.width for band in updated.borders]
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
    quilt: Quilt, square: int, borders: list[int] | None = None, step: int = SQUARE_STEP
) -> Quilt:
    """The quilt at a chosen finished square size and border widths.

    square must be one of square_sizes(step). borders gives one width per
    band, each snapped to 1/4 in; None keeps the model's widths, snapped. The
    counts never change, so the achieved size, the returned quilt's finished
    width and height, moves in whole squares and blocks."""
    if square not in square_sizes(step):
        raise ValueError(
            f"a finished square of {square} e is not offered; choose one of "
            f"{list(square_sizes(step))}"
        )
    widths = [band.width for band in quilt.borders] if borders is None else list(borders)
    if len(widths) != len(quilt.borders):
        raise ValueError(f"{len(widths)} border widths given for {len(quilt.borders)} border bands")
    updated = quilt.model_copy(deep=True)
    updated.center.cell_size = square
    for band, width in zip(updated.borders, widths):
        band.width = snap_border(width)
    updated.size_basis = None
    return updated


def _preset_size(name: str) -> tuple[int, int]:
    for preset, width, height in PRESETS:
        if preset == name:
            return width, height
    names = ", ".join(preset for preset, _w, _h in PRESETS)
    raise ValueError(f"unknown preset {name!r}; presets: {names}")


def _estimate_confidence(quilt: Quilt) -> float:
    """The confidence of the size a default request keeps: the estimate's own,
    1.0 for a hand-authored model, and UNMEASURED_ESTIMATE for a read that
    recorded none."""
    basis = quilt.size_basis
    if basis is not None:
        if basis.source != "default":
            raise ValueError(
                f"this model's size was set by a {basis.source} size, so it holds no photo "
                "estimate to label as one; size the model the read returned"
            )
        return basis.confidence
    if quilt.provenance.source == "authored":
        return 1.0
    return UNMEASURED_ESTIMATE


def size_pattern(quilt: Quilt, request: SizeRequest) -> SizeResult:
    """Sizes the pattern for the size you set, for the bridge's size_pattern
    (SPEC.md section 6.3): a typed or preset size snaps to the nearest
    achievable size in 1/4 in squares, and the default fits the model's own
    estimate the same way. Returns the sized model, whose size basis matches
    its finished size, and that basis."""
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
