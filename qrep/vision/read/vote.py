"""The block-consistent vote of the confirmed read (ticket B2b).

The confirmed block period drives a vote, so a few misread squares cannot
flip the construction method, while squares that confidently break the
repeat stay visible instead of being voted away (plan section 2.2). Block
copies are grouped by type first, so alternating layouts (the two blocks of a
Double Irish Chain) vote within each type.

It replaces vote_cells in qrep/vision/repeats.py, which B6b deletes. Its
knobs are provisional and live in knobs.py.
"""

from dataclasses import dataclass

import numpy as np

from qrep.vision.read.knobs import ATTACH_AGREEMENT, TYPE_AGREEMENT, VOTE_MIN_COPIES, VOTE_THRESHOLD

# Weighted sums that tie in exact arithmetic can differ in the last bits
# with the order numpy sums in, which differs between the native and the
# Pyodide builds, so ties and the type_agreement bound allow this much.
_EPS = 1e-9
# Typing compares a run of blocks with every type at once; runs hold at most
# this many square comparisons, so each step's temporaries stay a few MB.
_CHUNK = 1 << 18


@dataclass(frozen=True)
class Change:
    """A square the vote changed: its read before the vote, the block
    majority it took, and the vote's confidence, the majority's weighted
    share at that position."""

    row: int
    col: int
    read: int
    voted: int
    confidence: float


@dataclass(frozen=True)
class Break:
    """A confident square that disagrees with its block majority. It keeps
    its read and its own confidence, so the break stays visible."""

    row: int
    col: int
    read: int
    majority: int
    confidence: float


@dataclass(frozen=True, eq=False)
class Vote:
    """The read after the vote.

    labels and confidence have shape (rows, cols): unchanged squares keep
    their confidence, and a changed square takes its Change's. changes and
    breaks are sorted by (row, col). types has shape (blocks down, blocks
    across), numbered by first appearance in raster order. repeat is (down,
    across) in squares, derived only from the confirmed block period and the
    types, at least two whole copies each way or else the whole field, and
    the whole field for a 1 x 1 block, which confirms no repeat.
    agreement, in [0, 1], is the share of the squares of every type with at
    least two copies whose read before the vote equals their type majority,
    0.0 when no such type exists or the block is 1 x 1: as an undefined
    silhouette gives 0, a read with no repeated block has no evidence of a
    repeat. voted says whether any type voted.
    """

    labels: np.ndarray
    confidence: np.ndarray
    changes: tuple[Change, ...]
    breaks: tuple[Break, ...]
    types: np.ndarray
    repeat: tuple[int, int]
    agreement: float
    voted: bool


def _majority(weight: np.ndarray, count: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The majority label index at each position, and its share, from the
    summed weights and counts per label along axis 0. Ties go to the larger
    count, then the lower label; a position of total weight 0 uses counts."""
    total = weight.sum(axis=0)
    unweighted = total == 0
    key = np.where(unweighted, count, weight)
    top = key >= key.max(axis=0) - _EPS
    tied = np.where(top, count, -1)
    top &= tied == tied.max(axis=0)
    # Label indices ascend with the labels, so the first candidate is the
    # lowest label.
    winner = top.argmax(axis=0)
    won = np.take_along_axis(key, winner[None], axis=0)[0]
    return winner, won / np.where(unweighted, count.sum(axis=0), total)


def _agreement(
    codes: np.ndarray, weights: np.ndarray, totals: np.ndarray, patterns: np.ndarray
) -> np.ndarray:
    """Each block's agreement with each pattern, shape (blocks, patterns):
    its weight on the squares that equal the pattern over its total weight,
    or its plain share of equal squares when its weights sum to 0."""
    same = codes[:, None, :] == patterns[None, :, :]
    weighted = totals > 0
    matched = (same * weights[:, None, :]).sum(axis=2) / np.where(weighted, totals, 1)[:, None]
    return np.where(weighted[:, None], matched, same.mean(axis=2))


def _best(agreement: np.ndarray) -> np.ndarray:
    """Each row's highest agreement's column, ties to the lower type id."""
    return (agreement >= agreement.max(axis=1, keepdims=True) - _EPS).argmax(axis=1)


def _period(layout: np.ndarray, wild: np.ndarray | None = None) -> int:
    """The smallest p, at most half the rows, with layout[i] == layout[i - p]
    wherever neither block is wild; the row count when none. A repeat needs
    two whole copies: a p past half compares only the first rows with the
    last, so rows X, Y, Y, X would read as a period of 3."""
    n = layout.shape[0]
    if wild is None:
        wild = np.zeros(layout.shape, dtype=bool)
    for p in range(1, n // 2 + 1):
        known = ~(wild[p:] | wild[:-p])
        if np.all((layout[p:] == layout[:-p]) | ~known):
            return p
    return n


def _attach(layout, wild, period, codes, weights, n_labels: int, floor: float) -> np.ndarray:
    """The layout with each wild block moved to the type its block period
    predicts when it agrees with that type's majority on at least floor of
    its squares, renumbered by first appearance.

    The predicted type is the most common one among the blocks that are not
    wild a whole number of periods away (ties to the lower id). A block with
    no such neighbor, or one that agrees with it on fewer squares than floor
    (a block made different on purpose, not a varied copy), keeps its own
    type."""
    down, across = period
    size = codes.shape[1]
    positions = np.arange(size)
    out = layout.copy()
    for i, j in zip(*(axis.tolist() for axis in np.nonzero(wild))):
        near = layout[i % down :: down, j % across :: across]
        known = near[~wild[i % down :: down, j % across :: across]]
        if not known.size:
            continue
        t = int(np.bincount(known).argmax())
        members = np.flatnonzero((layout.ravel() == t) & ~wild.ravel())
        weight_sum = np.zeros((n_labels, size))
        count_sum = np.zeros((n_labels, size), dtype=np.int64)
        np.add.at(weight_sum, (codes[members], positions), weights[members])
        np.add.at(count_sum, (codes[members], positions), 1)
        pattern = _majority(weight_sum, count_sum)[0]
        b = slice(i * layout.shape[1] + j, i * layout.shape[1] + j + 1)
        agreement = _agreement(codes[b], weights[b], weights[b].sum(axis=1), pattern[None])
        if agreement[0, 0] >= floor - _EPS:
            out[i, j] = t
    kept, seen = np.unique(out, return_index=True)
    rank = np.empty(int(out.max()) + 1, dtype=np.intp)
    rank[kept[np.argsort(seen)]] = np.arange(len(kept))
    return rank[out]


def _block_count(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < 1:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")
    return int(value)


def _type_blocks(
    codes: np.ndarray, weights: np.ndarray, n_labels: int, type_agreement: float
) -> np.ndarray:
    """Each block's type: a raster pass that joins the best type or starts
    one, then one refinement against the pass's final majorities, numbered
    by first appearance. codes and weights have shape (blocks, squares).

    A block that joins a type whose majority it equals cannot move that
    majority: at every position the majority label gains weight and a count,
    and it stays ahead under each tie rule. So the raster pass decides runs
    of such blocks at once against fixed majorities, and takes one at a time
    only a block that starts a type or joins one it differs from. Runs double
    while they last, so a field of clean copies, or of 1 x 1 blocks whose
    types each hold one label, costs a few vectorized steps instead of one
    per block; a field may hold geometry.MAX_SQUARES, 285 x 285 squares.
    """
    n_blocks, size = codes.shape
    totals = weights.sum(axis=1)
    positions = np.arange(size)
    patterns = np.empty((n_blocks, size), dtype=np.intp)
    weight_sums: list[np.ndarray] = []
    count_sums: list[np.ndarray] = []
    first = np.empty(n_blocks, dtype=np.intp)

    b, run = 0, 1
    while b < n_blocks:
        n_types = len(weight_sums)
        stop = min(n_blocks, b + run, b + max(1, _CHUNK // (max(1, n_types) * size)))
        if n_types:
            agreement = _agreement(
                codes[b:stop], weights[b:stop], totals[b:stop], patterns[:n_types]
            )
            best = _best(agreement)
            joins = agreement[np.arange(stop - b), best] >= type_agreement - _EPS
            quiet = joins & np.all(codes[b:stop] == patterns[best], axis=1)
        else:
            best = joins = quiet = np.zeros(stop - b, dtype=bool)
        n_quiet = stop - b if quiet.all() else int(quiet.argmin())
        if n_quiet:
            for t in np.unique(best[:n_quiet]).tolist():
                members = b + np.flatnonzero(best[:n_quiet] == t)
                index = (codes[members], positions)
                np.add.at(weight_sums[t], index, weights[members])
                np.add.at(count_sums[t], index, 1)
            first[b : b + n_quiet] = best[:n_quiet]
        if b + n_quiet == stop:
            b, run = stop, 2 * run
            continue
        e = b + n_quiet
        t = int(best[n_quiet]) if joins[n_quiet] else n_types
        if t == n_types:
            weight_sums.append(np.zeros((n_labels, size)))
            count_sums.append(np.zeros((n_labels, size), dtype=np.int64))
        # One block holds one label per position, so plain indexing adds
        # without collisions.
        weight_sums[t][codes[e], positions] += weights[e]
        count_sums[t][codes[e], positions] += 1
        patterns[t] = _majority(weight_sums[t], count_sums[t])[0]
        first[e] = t
        b, run = e + 1, max(1, 2 * n_quiet)

    n_types = len(weight_sums)
    refined = first.copy()
    step = max(1, _CHUNK // (n_types * size))
    for b in range(0, n_blocks, step):
        stop = min(n_blocks, b + step)
        agreement = _agreement(codes[b:stop], weights[b:stop], totals[b:stop], patterns[:n_types])
        best = _best(agreement)
        joins = agreement[np.arange(stop - b), best] >= type_agreement - _EPS
        refined[b:stop][joins] = best[joins]

    kept, seen = np.unique(refined, return_index=True)
    rank = np.empty(n_types, dtype=np.intp)
    rank[kept[np.argsort(seen)]] = np.arange(len(kept))
    return rank[refined]


def vote(
    labels: np.ndarray,
    confidence: np.ndarray,
    block_rows: int,
    block_cols: int,
    *,
    threshold: float = VOTE_THRESHOLD,
    min_copies: int = VOTE_MIN_COPIES,
    type_agreement: float = TYPE_AGREEMENT,
    attach_agreement: float = ATTACH_AGREEMENT,
) -> Vote:
    """Types the confirmed blocks and votes within each type.

    labels (rows, cols) holds int fabric ids and confidence (rows, cols) each
    square's confidence in [0, 1]; rows is a multiple of block_rows and cols
    of block_cols. A type votes with at least min_copies blocks, and never
    with a 1 x 1 block. Beside a voting type, the block of a type of one
    copy joins the type its block period predicts when it agrees with it on
    at least attach_agreement of its squares (_attach). A square of a voting
    type that differs from its type majority takes it below threshold and is
    a Break otherwise. Raises
    ValueError on any other input. Inputs are never mutated.
    """
    lab = np.asarray(labels)
    conf = np.asarray(confidence, dtype=float)
    if lab.ndim != 2 or lab.shape != conf.shape or lab.size == 0:
        raise ValueError(
            f"labels and confidence must share one non-empty 2-D shape, got {lab.shape} "
            f"and {conf.shape}"
        )
    if not np.issubdtype(lab.dtype, np.integer):
        raise ValueError(f"labels must be integer fabric ids, got dtype {lab.dtype}")
    if not np.all((conf >= 0) & (conf <= 1)):
        raise ValueError("confidence must lie in [0, 1]")
    br, bc = _block_count("block_rows", block_rows), _block_count("block_cols", block_cols)
    rows, cols = lab.shape
    if rows % br or cols % bc:
        raise ValueError(f"a {rows} x {cols} field does not split into {br} x {bc} blocks")

    down, across = rows // br, cols // bc
    size = br * bc
    classes, inverse = np.unique(lab, return_inverse=True)
    # The inverse comes back flat or shaped like the input depending on the
    # numpy 2.x release, and the native and Pyodide builds differ.
    field_codes = inverse.reshape(rows, cols)

    def to_blocks(field: np.ndarray) -> np.ndarray:
        return field.reshape(down, br, across, bc).transpose(0, 2, 1, 3).reshape(-1, size)

    def to_field(blocks: np.ndarray) -> np.ndarray:
        return blocks.reshape(down, across, br, bc).transpose(0, 2, 1, 3).reshape(rows, cols)

    codes, weights = to_blocks(field_codes), to_blocks(conf)
    types = _type_blocks(codes, weights, len(classes), type_agreement)
    layout = types.reshape(down, across)
    # A copy with many squares confidently changed agrees with its type on
    # too few squares to join it, so typing starts a type of one copy that
    # never votes: its squares never reach the breaks, and the repeat would
    # move with where it sits. Beside a type that votes, such a block is wild
    # for the period that predicts its type; once attached it repeats like
    # its type, while a block that stays its own type is part of the layout.
    copies = np.bincount(types)
    if size > 1 and (copies >= min_copies).any() and (copies == 1).any():
        wild = copies[layout] == 1
        period = (_period(layout, wild), _period(layout.T, wild.T))
        layout = _attach(layout, wild, period, codes, weights, len(classes), attach_agreement)
        types = layout.ravel()
    n_types = int(types.max()) + 1

    weight_sum = np.zeros((len(classes), n_types, size))
    count_sum = np.zeros((len(classes), n_types, size), dtype=np.int64)
    index = (codes, types[:, None], np.arange(size)[None, :])
    np.add.at(weight_sum, index, weights)
    np.add.at(count_sum, index, 1)
    majority, share = _majority(weight_sum, count_sum)

    copies = np.bincount(types, minlength=n_types)
    voting = copies >= min_copies if size > 1 else np.zeros(n_types, dtype=bool)
    in_vote = to_field(np.repeat(voting[types][:, None], size, axis=1))
    field_majority = to_field(majority[types])
    field_share = to_field(share[types])
    differs = in_vote & (field_codes != field_majority)
    low = conf < threshold
    changed, held = differs & low, differs & ~low

    out_labels = lab.copy()
    out_labels[changed] = classes[field_majority[changed]]
    out_confidence = conf.copy()
    out_confidence[changed] = field_share[changed]
    # nonzero walks the field in raster order, so both lists come out sorted
    # by (row, col).
    changes = tuple(
        Change(r, c, int(lab[r, c]), int(classes[field_majority[r, c]]), float(field_share[r, c]))
        for r, c in zip(*(axis.tolist() for axis in np.nonzero(changed)))
    )
    breaks = tuple(
        Break(r, c, int(lab[r, c]), int(classes[field_majority[r, c]]), float(conf[r, c]))
        for r, c in zip(*(axis.tolist() for axis in np.nonzero(held)))
    )
    # A type of one copy is its own majority, so it agrees by construction
    # and is no evidence of a repeat; a type of two copies is, voting or not.
    repeated = copies >= 2 if size > 1 else np.zeros(n_types, dtype=bool)
    in_repeat = to_field(np.repeat(repeated[types][:, None], size, axis=1))
    agreement = (
        float(np.mean(field_codes[in_repeat] == field_majority[in_repeat]))
        if repeated.any()
        else 0.0
    )

    if size == 1:
        # A 1 x 1 block is the square itself, so its types are the labels,
        # and their period is the pattern's, not a block repeat you confirmed.
        repeat = (rows, cols)
    else:
        repeat = (_period(layout) * br, _period(layout.T) * bc)
    return Vote(
        labels=out_labels,
        confidence=out_confidence,
        changes=changes,
        breaks=breaks,
        types=layout,
        repeat=repeat,
        agreement=agreement,
        voted=bool(voting.any()),
    )
