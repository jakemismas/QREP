"""The block-consistent vote of the confirmed read (ticket B2b).

Every expected value is worked by hand from the vote criterion of #137 and
the rules qrep/vision/read/vote.py states for it:
  majority at a position: the label with the largest summed confidence over
    the blocks of a type; ties go to the larger count, then the lower label;
    a position whose confidences are all 0 uses counts
  share: the majority's summed confidence over the position's total
  agreement of a block with a pattern: the block's confidence on the squares
    that equal the pattern over its total confidence (plain share at 0)
  a square of a voting type that differs from its majority takes it below
    the threshold (a Change, with the share) and is a Break otherwise
  attach: beside a voting type, the block of a type of one copy (wild) joins
    the type a whole number of block periods away when it agrees with that
    type's majority on at least the attach share of its squares; the period
    is the one below, taken over the blocks that are not wild, with at least
    one such pair at the shift in every column (rows) or row (columns)
  an attached block takes its type for the layout, the repeat and the breaks
    only: it does not move the majority or count as a copy, and each of its
    squares that differs from the majority is a Break, whatever its
    confidence
  repeat: the smallest row and column periods of the type layout, each at
    most half the layout (two whole copies), else the whole layout, times the
    block size; the whole field for a 1 x 1 block, which confirms no repeat
  agreement: over the squares of every type with at least two copies, the
    share whose read before the vote equals their type majority; 0.0 when no
    such type exists or the block is 1 x 1

The tests pass the knob values their arithmetic uses (below) explicitly, so
a provisional knob that D5 moves does not change a hand computation; one
test pins the defaults to qrep/vision/read/knobs.py.
"""

import inspect
import json
from pathlib import Path

import numpy as np
import pytest

from qrep.vision.read.knobs import (
    ATTACH_AGREEMENT,
    TYPE_AGREEMENT,
    VOTE_MIN_COPIES,
    VOTE_THRESHOLD,
)
from qrep.vision.read.vote import Break, Change, vote

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "double_irish_chain.json"

THRESHOLD = 0.8
MIN_COPIES = 3
AGREEMENT = 0.75
ATTACH = 0.5
TOL = 1e-12


def _vote(labels, confidence, block_rows, block_cols, **knobs):
    settings = {
        "threshold": THRESHOLD,
        "min_copies": MIN_COPIES,
        "type_agreement": AGREEMENT,
        "attach_agreement": ATTACH,
    }
    settings.update(knobs)
    return vote(
        np.array(labels), np.array(confidence, dtype=float), block_rows, block_cols, **settings
    )


def _approx(value):
    return pytest.approx(value, abs=TOL)


# Shared by the misread and the break tests: a 3 x 3 block with three labels.
M = [[0, 1, 0], [1, 2, 1], [0, 1, 0]]


def _three_copies_with_misread(read: int, conf: float):
    """Three copies of M across (3 x 9 squares), all confidence 0.9, with the
    centre square of the third copy, field (1, 7), read as `read` at `conf`."""
    labels = np.hstack([M, M, M])
    confidence = np.full((3, 9), 0.9)
    labels[1, 7] = read
    confidence[1, 7] = conf
    return labels, confidence


def test_defaults_are_the_knobs():
    # Source: knobs.py holds every vote knob once; vote() takes them as
    #   defaults (ticket B2b, "keep every knob in knobs.py").
    # Formula: the signature's default is the knob object itself.
    # Inputs: VOTE_THRESHOLD, VOTE_MIN_COPIES, TYPE_AGREEMENT,
    #   ATTACH_AGREEMENT.
    # Arithmetic: none, identity.
    # Expected: each default is its knob.
    params = inspect.signature(vote).parameters
    assert params["threshold"].default is VOTE_THRESHOLD
    assert params["min_copies"].default is VOTE_MIN_COPIES
    assert params["type_agreement"].default is TYPE_AGREEMENT
    assert params["attach_agreement"].default is ATTACH_AGREEMENT


def test_period_of_one_never_votes_even_with_many_copies():
    labels = [[0, 1, 0], [1, 0, 1], [0, 1, 0]]
    confidence = np.full((3, 3), 0.5)

    # With type_agreement 0 every 1 x 1 block joins the one type: its
    # agreement with any pattern (1 or 0) is at least 0.
    merged = _vote(labels, confidence, 1, 1, type_agreement=0.0)
    # Source: ticket step 6, "never vote with a period of 1".
    # Formula: a type votes only when block_rows x block_cols > 1.
    # Inputs: one type of 9 copies (at least min_copies 3), every square at
    #   confidence 0.5 (below the threshold 0.8), block 1 x 1.
    # Arithmetic: block size 1 x 1 = 1, not > 1, so no type votes. Had it
    #   voted, label 0 weighs 5 x 0.5 = 2.5 against label 1's 4 x 0.5 = 2.0,
    #   and the four 1s would have changed; none does.
    #   A 1 x 1 block confirms no repeat (vision-22), so the repeat is the
    #   whole 3 x 3 field and no type counts toward the agreement: 0.0.
    # Expected: voted False, labels and confidence unchanged, no changes or
    #   breaks, agreement 0.0, types all 0, repeat (3, 3).
    assert merged.voted is False
    np.testing.assert_array_equal(merged.labels, labels)
    np.testing.assert_array_equal(merged.confidence, confidence)
    assert merged.changes == ()
    assert merged.breaks == ()
    assert merged.agreement == 0.0
    np.testing.assert_array_equal(merged.types, np.zeros((3, 3), dtype=int))
    assert merged.repeat == (3, 3)

    split = _vote(labels, confidence, 1, 1)
    # Source: ticket steps 4 and 5; vision-22 for the repeat.
    # Formula: a 1 x 1 block agrees with a pattern 1.0 when equal, else 0.0,
    #   so at type_agreement 0.75 each label is its own type, numbered by
    #   first appearance; a 1 x 1 block confirms no repeat, so the repeat is
    #   the whole field whatever the layout's period.
    # Inputs: (0, 0) reads 0, (0, 1) reads 1.
    # Arithmetic: label 0 -> type 0, label 1 -> type 1. The layout repeats
    #   every 2 squares each way, but the block is 1 x 1, so the repeat is
    #   the whole field, (3, 3).
    # Expected: types equal the labels, repeat (3, 3), no vote, agreement 0.0.
    assert split.voted is False
    np.testing.assert_array_equal(split.types, labels)
    assert split.repeat == (3, 3)
    assert split.changes == ()
    assert split.agreement == 0.0


def test_fewer_copies_than_min_copies_do_not_vote():
    labels = [[0, 0, 0, 0], [1, 1, 1, 0]]
    confidence = [[1.0, 1.0, 1.0, 1.0], [1.0, 1.0, 1.0, 0.1]]

    held = _vote(labels, confidence, 2, 2)
    # Source: ticket step 6, VOTE_MIN_COPIES.
    # Formula: a type votes only with at least min_copies blocks.
    # Inputs: blocks [[0,0],[1,1]] and [[0,0],[1,0]], the second's (1, 1) at
    #   confidence 0.1.
    # Arithmetic: the second block agrees with the first on 3 squares of
    #   weight 1.0: 3.0 / 3.1 = 0.968 >= 0.75, so one type of 2 copies;
    #   2 < 3, so it does not vote. Its two copies still count toward the
    #   agreement: at (1, 1) label 1 at 1.0 beats label 0 at 0.1, so 7 of the
    #   8 squares read their majority before the vote, 7/8.
    # Expected: voted False, labels unchanged, no changes, agreement 0.875,
    #   types [[0, 0]], repeat (2, 2).
    assert held.voted is False
    np.testing.assert_array_equal(held.labels, labels)
    assert held.changes == ()
    assert held.agreement == _approx(7 / 8)
    np.testing.assert_array_equal(held.types, [[0, 0]])
    assert held.repeat == (2, 2)

    voted = _vote(labels, confidence, 2, 2, min_copies=2)
    # Source: ticket step 6, the same type at min_copies 2.
    # Formula: share = majority weight / total weight at the position.
    # Inputs: position (1, 1): label 1 at 1.0, label 0 at 0.1.
    # Arithmetic: majority 1, share 1.0 / 1.1 = 10/11 = 0.90909; the 0 at
    #   field (1, 3) has confidence 0.1 < 0.8, so it takes 1. Agreement: 7 of
    #   the 8 squares equal their majority, 7/8.
    # Expected: one Change (1, 3, 0 -> 1, 10/11), agreement 0.875.
    assert voted.voted is True
    assert voted.changes == (Change(1, 3, 0, 1, _approx(10 / 11)),)
    assert voted.labels[1, 3] == 1
    assert voted.agreement == _approx(7 / 8)


def test_low_confidence_misread_takes_the_majority():
    labels, confidence = _three_copies_with_misread(read=0, conf=0.3)
    result = _vote(labels, confidence, 3, 3)
    # Source: ticket steps 4 to 6 and 8.
    # Formula: typing agreement = matching weight / block weight; share =
    #   majority weight / total weight; a differing square below the
    #   threshold takes the majority.
    # Inputs: three copies of M at confidence 0.9; the third copy's centre,
    #   field (1, 7), reads 0 at 0.3 where M has 2.
    # Arithmetic: third copy agreement 8 x 0.9 / (8 x 0.9 + 0.3) = 7.2 / 7.5
    #   = 0.96 >= 0.75, one type of 3 copies, so it votes. Centre: label 2 at
    #   0.9 + 0.9 = 1.8, label 0 at 0.3; majority 2, share 1.8 / 2.1 = 6/7 =
    #   0.857143; 0.3 < 0.8, so (1, 7) takes 2. Agreement: 26 of 27 squares
    #   equal their majority, 26/27. Repeat: one type, so (3, 3).
    # Expected: Change (1, 7, 0 -> 2, 6/7), the labels three clean copies of
    #   M, (1, 7)'s confidence 6/7, every other confidence unchanged.
    assert result.voted is True
    assert result.changes == (Change(1, 7, 0, 2, _approx(6 / 7)),)
    assert result.breaks == ()
    np.testing.assert_array_equal(result.labels, np.hstack([M, M, M]))
    assert result.confidence[1, 7] == _approx(6 / 7)
    others = np.ones((3, 9), dtype=bool)
    others[1, 7] = False
    np.testing.assert_array_equal(result.confidence[others], confidence[others])
    assert result.agreement == _approx(26 / 27)
    np.testing.assert_array_equal(result.types, [[0, 0, 0]])
    assert result.repeat == (3, 3)


@pytest.mark.parametrize("conf", [0.8, 0.95])
def test_confident_disagreement_keeps_its_read_as_a_break(conf):
    labels, confidence = _three_copies_with_misread(read=0, conf=conf)
    result = _vote(labels, confidence, 3, 3)
    # Source: ticket step 6, "otherwise it keeps its read and is listed as a
    #   Break".
    # Formula: a differing square at or above the threshold is a Break with
    #   its read, the majority and its own confidence.
    # Inputs: as the misread test, but (1, 7) at 0.8 (the threshold itself)
    #   or 0.95.
    # Arithmetic: third copy agreement 7.2 / (7.2 + 0.8) = 0.9 or 7.2 / 8.15
    #   = 0.883, both >= 0.75, one type that votes. Centre: label 2 at 1.8
    #   beats label 0 at 0.8 or 0.95, majority 2; 0.8 and 0.95 are not below
    #   0.8. Agreement 26/27 as before.
    # Expected: Break (1, 7, read 0, majority 2, conf), labels and confidence
    #   unchanged, no changes.
    assert result.voted is True
    assert result.breaks == (Break(1, 7, 0, 2, _approx(conf)),)
    assert result.changes == ()
    np.testing.assert_array_equal(result.labels, labels)
    np.testing.assert_array_equal(result.confidence, confidence)
    assert result.agreement == _approx(26 / 27)


def test_alternating_types_vote_within_each_type():
    a = np.array([[1, 0, 1], [0, 1, 0], [1, 0, 1]])
    b = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])
    misread = np.array([[0, 0, 0], [1, 1, 1], [0, 1, 0]])
    labels = np.block([[a, b], [misread, a], [a, b]])
    confidence = np.ones((9, 6))
    confidence[3, 1] = 0.3
    result = _vote(labels, confidence, 3, 3)
    # Source: ticket steps 4 to 7, "alternating layouts vote within each
    #   type".
    # Formula: as above; types by agreement >= 0.75, numbered in raster
    #   order.
    # Inputs: a checkerboard of A (an X) and B (a plus), 3 blocks down by 2
    #   across; block (1, 0) is B with its (0, 1), field (3, 1), read as A's
    #   0 at confidence 0.3; all else 1.0.
    # Arithmetic: A and B agree only on the centre, 1/9 < 0.75, so two types.
    #   The misread copy agrees with A on (0, 1) and the centre, (0.3 + 1.0)
    #   / 8.3 = 0.157, and with B on all but (0, 1), 8.0 / 8.3 = 0.964, so it
    #   is B. Types [[0, 1], [1, 0], [0, 1]], 3 copies each, both vote. B at
    #   (0, 1): label 1 at 1.0 + 1.0 = 2.0, label 0 at 0.3; majority 1, share
    #   2.0 / 2.3 = 20/23 = 0.869565; 0.3 < 0.8, so (3, 1) takes 1. One vote
    #   over all six copies would give label 0 3 x 1.0 + 0.3 = 3.3 against
    #   label 1's 2.0 and keep the misread. Agreement: 53 of 54 squares, 53/54.
    #   Repeat: a period needs two whole copies, p <= 3 // 2 = 1 down, and
    #   row 1 differs from row 0, so py = 3, the whole height (rows 0 and 2
    #   alone match, one block, no evidence of a repeat); across p <= 1 and
    #   the columns differ, px = 2, the whole width; (3 x 3, 2 x 3).
    # Expected: Change (3, 1, 0 -> 1, 20/23), repeat (9, 6).
    assert result.voted is True
    assert result.changes == (Change(3, 1, 0, 1, _approx(20 / 23)),)
    assert result.breaks == ()
    np.testing.assert_array_equal(result.labels, np.block([[a, b], [b, a], [a, b]]))
    np.testing.assert_array_equal(result.types, [[0, 1], [1, 0], [0, 1]])
    assert result.repeat == (9, 6)
    assert result.agreement == _approx(53 / 54)


# The fixture's two blocks, transcribed from rows 0 to 4 of its cells: A at
# columns 0 to 4, B at columns 5 to 9, with b (chain blue) as 0 and c
# (background cream) as 1.
FIX_A = np.array(
    [
        [0, 0, 1, 0, 0],
        [0, 0, 0, 0, 0],
        [1, 0, 0, 0, 1],
        [0, 0, 0, 0, 0],
        [0, 0, 1, 0, 0],
    ]
)
FIX_B = np.array(
    [
        [0, 1, 1, 1, 0],
        [1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1],
        [1, 1, 1, 1, 1],
        [0, 1, 1, 1, 0],
    ]
)


def _fixture_labels() -> np.ndarray:
    cells = json.loads(FIXTURE_PATH.read_text())["center"]["cells"]
    ids = {"b": 0, "c": 1}
    labels = np.array([[ids[c] for c in row] for row in cells])
    # Precondition, not an expected value: the fixture is the 11 x 9
    # checkerboard of the two transcribed blocks, A where i + j is even.
    checker = np.indices((11, 9)).sum(axis=0) % 2
    tiled = np.block([[FIX_B if t else FIX_A for t in row] for row in checker])
    np.testing.assert_array_equal(labels, tiled)
    return labels


def test_double_irish_chain_fixture_votes_without_change():
    labels = _fixture_labels()
    result = vote(labels, np.ones(labels.shape), 5, 5)
    # Source: ticket test 5 and the plan's S7-5 replacement criterion, with
    #   the default knobs.
    # Formula: as above.
    # Inputs: the fixture, 55 x 45 squares in 5 x 5 blocks (11 down by 9
    #   across), every confidence 1.0.
    # Arithmetic: A and B agree on the 4 corners and 4 edge midpoints, 8/25 =
    #   0.32 < 0.75, so two types; every copy equals its type's pattern, so
    #   every block agrees 1.0 with its own type. A sits where i + j is even:
    #   6 even rows x 5 even columns + 5 odd rows x 4 odd columns = 30 + 20 =
    #   50 copies; B 99 - 50 = 49; both >= 3, so both vote, and no square
    #   differs from its majority. Agreement 2475 / 2475. Types: A first at
    #   (0, 0) is 0, B at (0, 1) is 1, so (i + j) % 2. Repeat: row 1 differs
    #   from row 0 and row 2 equals it, py = 2; px = 2 likewise; (10, 10).
    # Expected: labels unchanged, no changes or breaks, agreement 1.0,
    #   repeat (10, 10).
    assert result.voted is True
    np.testing.assert_array_equal(result.labels, labels)
    assert result.changes == ()
    assert result.breaks == ()
    assert result.agreement == 1.0
    np.testing.assert_array_equal(result.types, np.indices((11, 9)).sum(axis=0) % 2)
    assert result.repeat == (10, 10)


@pytest.mark.parametrize("block", [(0, 0), (3, 4), (10, 8)])
def test_a_varied_copy_keeps_its_breaks_and_the_repeat(block):
    # Source: criteria 5 and 6 of #137; PR #251 round 1: one varied block
    #   started its own type, its squares never reached the breaks, and the
    #   repeat moved with its position.
    # Inputs: the fixture with every confidence 1.0, then, in the block at
    #   (bi, bj), block rows 1 (all 5 squares) and 3 (the first 3) flipped
    #   (A's 0s there read 1, B's 1s read 0), 8 squares at confidence 0.9.
    #   (0, 0) and (10, 8) are A blocks (bi + bj even), (3, 4) is B.
    # Arithmetic: total weight 17 x 1.0 + 8 x 0.9 = 24.2. The block equals its
    #   own type on its 17 unflipped squares, 17 / 24.2 = 0.702, and the
    #   other type on the 8 squares A and B share plus the 8 flipped ones,
    #   (8 + 7.2) / 24.2 = 0.628, both under 0.75: a type of one copy. Beside
    #   A (50 copies) and B (49), it is wild for the period: the other blocks
    #   alternate, so rows 1 and 0 differ wherever neither block is wild, and
    #   at 2 blocks every column (and row) holds equal pairs of blocks that
    #   are not wild (11 blocks down, 9 across, one wild); the blocks an even
    #   number of blocks away share its own type; 0.702 >= 0.5, so it joins
    #   that type. The type's majority comes from its 49 or 48 own copies,
    #   its clean pattern, so the 8 flipped squares differ, and an attached
    #   block's are breaks: 8 breaks, labels kept. Agreement (2475 - 8) / 2475. Types
    #   (i + j) % 2 as the clean fixture; repeat 2 x 5 = 10 each way.
    # Expected: 8 breaks at the flipped squares, read the flipped label and
    #   majority the clean one, at 0.9; no changes; labels unchanged; types
    #   and repeat (10, 10) as the clean fixture.
    clean = _fixture_labels()
    labels = clean.copy()
    confidence = np.ones(labels.shape)
    bi, bj = block
    flipped = [(bi * 5 + 1, bj * 5 + c) for c in range(5)]
    flipped += [(bi * 5 + 3, bj * 5 + c) for c in range(3)]
    for r, c in flipped:
        labels[r, c] = 1 - clean[r, c]
        confidence[r, c] = 0.9
    result = _vote(labels, confidence, 5, 5)
    assert result.breaks == tuple(
        Break(r, c, int(labels[r, c]), int(clean[r, c]), _approx(0.9)) for r, c in sorted(flipped)
    )
    assert result.changes == ()
    np.testing.assert_array_equal(result.labels, labels)
    np.testing.assert_array_equal(result.types, np.indices((11, 9)).sum(axis=0) % 2)
    assert result.agreement == _approx(2467 / 2475)
    assert result.repeat == (10, 10)


@pytest.mark.parametrize(
    ("layout", "repeat"),
    [
        # Rows X, Y, Y, X: p <= 4 // 2 = 2; p = 1 compares [Y, Y, X] with
        #   [X, Y, Y] and p = 2 [Y, X] with [X, Y], both differ, so py = 4,
        #   the whole height (p = 3 would match the first row with the last).
        ([[0], [1], [1], [0]], (4, 1)),
        # Rows X, Y, X, Y: p = 2 matches [X, Y] with [X, Y], two whole copies.
        ([[0], [1], [0], [1]], (2, 1)),
    ],
    ids=["xyyx", "xyxy"],
)
def test_a_period_needs_two_whole_copies(layout, repeat):
    # Source: PR #251 round 1: a period that overlaps only the first block
    #   with the last is no evidence of a repeat.
    # Inputs: a field of 1 x 2 blocks, all 0 (X) or all 1 (Y), stacked as the
    #   layout lists, one block across, confidence 1.0; each type has 2
    #   copies, so neither votes and no block is wild.
    # Formula: py = the smallest p <= blocks down // 2 with every row equal
    #   to the row p above, else blocks down; repeat (py x 1, 1 x 2).
    # Expected: the listed repeat in blocks, times the 1 x 2 block size.
    labels = np.repeat(np.array(layout), 2, axis=1)
    result = _vote(labels, np.ones(labels.shape), 1, 2)
    assert result.repeat == (repeat[0], repeat[1] * 2)


def _plain_with_pieced(down, across, pieced, design_conf):
    """down x across blocks of 5 x 5 squares, every square label 0 at 1.0,
    except that the m-th block listed in pieced (m = 1, 2, ..) reads label m
    on its centre 3 x 3 squares, at design_conf."""
    labels = np.zeros((down * 5, across * 5), dtype=int)
    confidence = np.ones(labels.shape)
    for m, (i, j) in enumerate(pieced, start=1):
        labels[i * 5 + 1 : i * 5 + 4, j * 5 + 1 : j * 5 + 4] = m
        confidence[i * 5 + 1 : i * 5 + 4, j * 5 + 1 : j * 5 + 4] = design_conf
    return labels, confidence


@pytest.mark.parametrize("design_conf", [0.6, 0.75])
def test_unique_blocks_between_plain_blocks_stay_their_own(design_conf):
    pieced = [(i, j) for i in range(5) for j in range(5) if (i + j) % 2]
    labels, confidence = _plain_with_pieced(5, 5, pieced, design_conf)
    result = _vote(labels, confidence, 5, 5)
    # Source: PR #251 round 2 (critical): a sampler whose unique blocks
    #   alternate with plain blocks read a period of 1 from no comparison at
    #   all, and its unique blocks joined the plain type and lost their
    #   designs.
    # Inputs: _plain_with_pieced(5, 5, ...): plain blocks where i + j is
    #   even, 13 of them; the 12 others pieced in raster order, m = 1 to 12,
    #   their designs at design_conf.
    # Arithmetic: a pieced block agrees with the plain pattern, and with any
    #   other pieced block, on its 16 border squares: 16 / (16 + 9 x 0.6) =
    #   16 / 21.4 = 0.7477, or 16 / (16 + 9 x 0.75) = 16 / 22.75 = 0.7033;
    #   both under 0.75, so each is a type of one copy, and a plain block
    #   agrees with a pieced type on 16 / 25 = 0.64. Plain has 13 copies and
    #   votes; the 12 pieced blocks are wild. Down, at p = 1 every pair of
    #   vertical neighbours holds a block with i + j odd, so no column holds
    #   a pair of blocks that are not wild: no evidence of p = 1. At p = 2
    #   column 0 holds the plain pairs at rows 2 and 0 and rows 4 and 2, and
    #   column 1 the pair at rows 3 and 1, all equal, and so on: p = 2.
    #   Across, likewise 2. The blocks a whole number of periods from a
    #   pieced block all have i + j odd, so all are wild, no type is
    #   predicted, and none attaches. Types: plain 0, pieced m. Repeat: row 1
    #   differs from row 0, and row 2 from row 0 (two different pieced blocks
    #   in column 1), so py = 5 and px = 5 likewise, (25, 25). Plain's 13
    #   copies equal its pattern: no change. Agreement: plain is the one
    #   type of two or more copies, all its squares equal the pattern, 1.0.
    # Expected: types 0 where i + j is even and m at the m-th pieced block,
    #   repeat (25, 25), no changes or breaks, labels unchanged, agreement 1.0.
    types = np.zeros((5, 5), dtype=int)
    for m, (i, j) in enumerate(pieced, start=1):
        types[i, j] = m
    np.testing.assert_array_equal(result.types, types)
    assert result.repeat == (25, 25)
    assert result.changes == ()
    assert result.breaks == ()
    np.testing.assert_array_equal(result.labels, labels)
    assert result.agreement == 1.0


def test_unique_blocks_in_plain_sashing_stay_their_own():
    pieced = [(1, 1), (1, 3), (3, 1), (3, 3)]
    labels, confidence = _plain_with_pieced(5, 5, pieced, 0.6)
    result = _vote(labels, confidence, 5, 5)
    # Source: PR #251 round 2 (critical), the same class: plain sashing
    #   blocks fill every even row and column of blocks.
    # Inputs: _plain_with_pieced(5, 5, ...): plain wherever i or j is even,
    #   21 blocks; pieced at (1, 1), (1, 3), (3, 1), (3, 3), m = 1 to 4,
    #   designs at 0.6.
    # Arithmetic: each pieced block agrees with plain, and with the others,
    #   on 16 / 21.4 = 0.7477 < 0.75: four wild blocks beside plain's 21
    #   copies. Down, at p = 1 column 1 reads plain, pieced, plain, pieced,
    #   plain, so each of its pairs holds a wild block: no evidence of p = 1
    #   (column 0 alone, all plain, would have given p = 1). At p = 2 column
    #   1 holds the plain pairs at rows 2 and 0 and rows 4 and 2, columns 0,
    #   2 and 4 are all plain, all equal: p = 2. Across, likewise 2. The
    #   blocks a whole number of periods from (1, 1) are (1, 3), (3, 1) and
    #   (3, 3), all wild: none attaches. Types: plain 0, pieced 1 to 4.
    #   Repeat: row 2 equals row 0, but row 3 differs from row 1 (types 3
    #   and 1 in column 1), so py = 5, and px = 5 likewise, (25, 25).
    # Expected: those types, repeat (25, 25), no changes or breaks, labels
    #   unchanged.
    types = np.zeros((5, 5), dtype=int)
    for m, (i, j) in enumerate(pieced, start=1):
        types[i, j] = m
    np.testing.assert_array_equal(result.types, types)
    assert result.repeat == (25, 25)
    assert result.changes == ()
    assert result.breaks == ()
    np.testing.assert_array_equal(result.labels, labels)


def test_an_attached_block_keeps_every_square_and_shows_each_difference():
    labels, confidence = _plain_with_pieced(4, 4, [(1, 1), (2, 3)], 0.6)
    result = _vote(labels, confidence, 5, 5)
    # Source: PR #251 round 2 (critical): a block that typing found too
    #   different to be a copy must not have its squares voted away when
    #   the block period attaches it.
    # Inputs: _plain_with_pieced(4, 4, ...): all plain but blocks (1, 1)
    #   and (2, 3), whose centre squares read 1 and 2 at 0.6.
    # Arithmetic: each pieced block agrees with plain on 16 / 21.4 = 0.7477
    #   < 0.75: two wild blocks beside plain's 14 copies. Down, at p = 1
    #   column 1 reads plain, pieced, plain, plain and holds the plain pair
    #   at rows 3 and 2, column 3 (plain, plain, pieced, plain) the pair at
    #   rows 1 and 0, columns 0 and 2 are all plain; all equal, so p = 1.
    #   Across, row 1 (plain, pieced, plain, plain) and row 2 (plain, plain,
    #   plain, pieced) hold plain pairs too: p = 1. Every other block is a
    #   whole number of periods away and the 14 not wild are plain, so each
    #   pieced block's predicted type is plain, and 0.7477 >= 0.5 attaches
    #   it. Types all 0, repeat (5, 5). Plain votes; its majority comes from
    #   its 14 own copies, label 0 everywhere. An attached block's squares
    #   never take the majority: its 9 design squares differ, so each is a
    #   Break at its own 0.6, read 1 or 2, majority 0, though 0.6 < 0.8.
    #   Agreement: the one repeated type covers 400 squares, 18 differ,
    #   382 / 400.
    # Expected: types all 0, repeat (5, 5), no changes, the 18 design squares
    #   as breaks in raster order, labels unchanged, agreement 382 / 400.
    np.testing.assert_array_equal(result.types, np.zeros((4, 4), dtype=int))
    assert result.repeat == (5, 5)
    assert result.changes == ()
    design = zip(*(axis.tolist() for axis in np.nonzero(labels)))
    assert result.breaks == tuple(
        Break(r, c, int(labels[r, c]), 0, _approx(0.6)) for r, c in design
    )
    assert len(result.breaks) == 18
    np.testing.assert_array_equal(result.labels, labels)
    assert result.agreement == _approx(382 / 400)


@pytest.mark.parametrize(("changed", "attaches"), [(12, True), (13, False)])
def test_the_attach_floor_decides_whether_a_varied_copy_joins(changed, attaches):
    clean = _fixture_labels()
    labels = clean.copy()
    squares = [(n // 5, n % 5) for n in range(changed)]
    for r, c in squares:
        labels[r, c] = 2
    result = _vote(labels, np.ones(labels.shape), 5, 5)
    # Source: knobs.ATTACH_AGREEMENT (0.5, passed as ATTACH); PR #251 round
    #   2: nothing pinned the floor.
    # Inputs: the fixture at confidence 1.0, with the first `changed`
    #   squares of block (0, 0), an A block, in raster order read 2, a label
    #   no block holds.
    # Arithmetic: block (0, 0) equals A on 25 - changed squares, 13 / 25 =
    #   0.52 or 12 / 25 = 0.48, and B on at most the 8 squares A and B share,
    #   8 / 25 = 0.32; all under 0.75, so it is a type of one copy, wild
    #   beside A (49 other copies) and B (49). As in the varied-copy test,
    #   the period is 2 blocks each way and the blocks an even number of
    #   blocks away are A. 0.52 >= 0.5 attaches; 0.48 < 0.5 does not.
    #   Attached: types (i + j) % 2, repeat (10, 10), each changed square a
    #   Break (read 2, majority A's clean label, 1.0), no changes, agreement
    #   (2475 - 12) / 2475. Not attached: block (0, 0) is type 0, B (first at
    #   (0, 1)) 1 and A (first at (0, 2)) 2; block (0, 0) is in row 0 and
    #   column 0 and no other block has its type, so no row p <= 5 equals
    #   row 0 and no column p <= 4 equals column 0: the repeat is the whole
    #   field, (55, 45). Its type has one copy and does not vote: no breaks,
    #   no changes; A and B keep their clean patterns, agreement 2450 / 2450.
    # Expected: as listed for each case.
    assert result.changes == ()
    np.testing.assert_array_equal(result.labels, labels)
    if attaches:
        np.testing.assert_array_equal(result.types, np.indices((11, 9)).sum(axis=0) % 2)
        assert result.repeat == (10, 10)
        assert result.breaks == tuple(
            Break(r, c, 2, int(clean[r, c]), _approx(1.0)) for r, c in squares
        )
        assert result.agreement == _approx(2463 / 2475)
    else:
        types = 2 - np.indices((11, 9)).sum(axis=0) % 2
        types[0, 0] = 0
        np.testing.assert_array_equal(result.types, types)
        assert result.repeat == (55, 45)
        assert result.breaks == ()
        assert result.agreement == 1.0


def test_double_irish_chain_misread_takes_its_own_types_majority():
    clean = _fixture_labels()
    labels = clean.copy()
    labels[1, 6] = 0
    confidence = np.ones(labels.shape)
    confidence[1, 6] = 0.3
    result = _vote(labels, confidence, 5, 5)
    # Source: ticket test 5, a misread planted in a type-B copy.
    # Formula: as above.
    # Inputs: field (1, 6) is block (0, 1), a B copy, at in-block (1, 1),
    #   where B has c (1) and A has b (0); it reads b at 0.3.
    # Arithmetic: block (0, 1) is the first B in raster order; against A it
    #   matches on the 8 shared squares plus the misread, 8.3 / 24.3 = 0.342 <
    #   0.75, so it starts type 1. Block (0, 3) matches it on 24 of 25 squares
    #   at weight 1.0, 0.96, joins, and at (1, 1) c at 1.0 now beats b at 0.3.
    #   Final B at (1, 1): c at 48 x 1.0 = 48.0, b at 0.3; majority c, share
    #   48 / 48.3 = 160/161 = 0.993789; 0.3 < 0.8, so it takes c (1), not A's
    #   b. Agreement 2474 / 2475; types and repeat as the clean fixture.
    # Expected: Change (1, 6, 0 -> 1, 160/161) and the clean fixture back.
    assert result.changes == (Change(1, 6, 0, 1, _approx(160 / 161)),)
    assert result.breaks == ()
    np.testing.assert_array_equal(result.labels, clean)
    assert result.agreement == _approx(2474 / 2475)
    assert result.repeat == (10, 10)


@pytest.mark.parametrize(
    ("labels", "block", "types", "repeat"),
    [
        # One type: three rows of [0, 1] twice in 1 x 2 blocks; every block
        # is [0, 1], so types all 0 and py = px = 1; repeat (1 x 1, 1 x 2).
        ([[0, 1, 0, 1]] * 3, (1, 2), [[0, 0], [0, 0], [0, 0]], (1, 2)),
        # All distinct: 2 x 2 blocks, block (i, j) all label 3i + j; any two
        # blocks agree on 0 of 4 squares, so six types numbered 0 to 5 in
        # raster order; no row or column period below the layout, py = 2,
        # px = 3; repeat (4, 6), the whole field.
        (
            np.kron([[0, 1, 2], [3, 4, 5]], np.ones((2, 2), dtype=int)),
            (2, 2),
            [[0, 1, 2], [3, 4, 5]],
            (4, 6),
        ),
        # Checkerboard: 2 x 2 blocks of all 0 (A) and all 1 (B) as [[A, B],
        # [B, A]]; they agree on 0 squares, types [[0, 1], [1, 0]]; row 1
        # differs from row 0, so py = 2 = blocks down, px = 2 likewise;
        # repeat (4, 4), twice the block size.
        (
            np.kron([[0, 1], [1, 0]], np.ones((2, 2), dtype=int)),
            (2, 2),
            [[0, 1], [1, 0]],
            (4, 4),
        ),
        # Rows alternate in 1 x 2 blocks: [5, 5] and [7, 7] agree on 0 of 2
        # squares, so they number as types 0 and 1 by first appearance; row 1
        # differs from row 0, rows 2 and 3 repeat rows 0 and 1, py = 2; one
        # block across, px = 1; repeat (2 x 1, 1 x 2) = (2, 2).
        ([[5, 5], [7, 7], [5, 5], [7, 7]], (1, 2), [[0], [1], [0], [1]], (2, 2)),
        # The same rows in 1 x 1 blocks: the types are the labels, 5 -> 0 and
        # 7 -> 1, with period 2 down, but a 1 x 1 block confirms no repeat
        # (vision-22), so the repeat is the whole 4 x 2 field.
        ([[5, 5], [7, 7], [5, 5], [7, 7]], (1, 1), [[0, 0], [1, 1], [0, 0], [1, 1]], (4, 2)),
    ],
    ids=["one-type", "all-distinct", "checkerboard", "row-period", "one-by-one"],
)
def test_repeat_comes_from_the_type_layout(labels, block, types, repeat):
    # Source: ticket step 7.
    # Formula: py is the smallest p with T[i] == T[i - p] for every i >= p,
    #   px likewise on columns; repeat = (py x block_rows, px x block_cols).
    # Inputs, Arithmetic: in each case's comment above; confidence 1.0.
    # Expected: the listed types and repeat.
    labels = np.array(labels)
    result = _vote(labels, np.ones(labels.shape), *block)
    np.testing.assert_array_equal(result.types, types)
    assert result.repeat == repeat


def test_agreement_counts_only_types_with_two_or_more_copies():
    a = np.array([[0, 0, 0], [0, 1, 0], [0, 0, 0]])
    labels = np.hstack([a, a, a, np.full((3, 3), 2)])
    confidence = np.ones((3, 12))
    labels[2, 3], confidence[2, 3] = 1, 0.2
    labels[0, 6], confidence[0, 6] = 1, 0.4
    labels[2, 8], confidence[2, 8] = 1, 0.9
    result = _vote(labels, confidence, 3, 3)
    # Source: ticket steps 6 and 8.
    # Formula: agreement = squares equal to their type majority / squares,
    #   over the types with at least two copies only.
    # Inputs: blocks A, A with (2, 0) read 1 at 0.2, A with (0, 0) read 1 at
    #   0.4 and (2, 2) read 1 at 0.9, then an all-2 block; all else 1.0.
    # Arithmetic: copy 1 agrees 8.0 / 8.2 = 0.976, copy 2 7.0 / 8.3 = 0.843,
    #   both join A; the all-2 block agrees 0 with A, its own type of 1 copy,
    #   which does not vote. A at (0, 0): 0 at 1.0 + 1.0 = 2.0, 1 at 0.4,
    #   share 2.0 / 2.4 = 5/6, field (0, 6) changes. A at (2, 0): 0 at 2.0, 1
    #   at 0.2, share 2.0 / 2.2 = 10/11, field (2, 3) changes. A at (2, 2): 0
    #   at 2.0 beats 1 at 0.9, but 0.9 >= 0.8, so (2, 8) is a Break.
    #   Agreement: 24 of A's 27 squares, 24/27 = 8/9 (counting the all-2
    #   block too would give 33/36). Changes sort by (row, col), so (0, 6)
    #   precedes (2, 3) although its block comes later.
    # Expected: the two changes in that order, one break, agreement 8/9,
    #   types [[0, 0, 0, 1]], repeat (3, 12).
    assert result.changes == (
        Change(0, 6, 1, 0, _approx(5 / 6)),
        Change(2, 3, 1, 0, _approx(10 / 11)),
    )
    assert result.breaks == (Break(2, 8, 1, 0, _approx(0.9)),)
    assert result.agreement == _approx(8 / 9)
    np.testing.assert_array_equal(result.types, [[0, 0, 0, 1]])
    assert result.repeat == (3, 12)


def test_all_zero_weights_fall_back_to_counts():
    labels = [[5, 1, 5, 1, 5, 0, 5, 1]]
    confidence = [[1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 0.0, 0.0]]
    result = _vote(labels, confidence, 1, 2)
    # Source: ticket steps 2, 3 and 6, the zero-weight rules.
    # Formula: with all weights 0, counts pick the majority and its share,
    #   and a block of weight 0 agrees by its plain share of equal squares.
    # Inputs: 1 x 2 blocks [5, 1], [5, 1], [5, 0], [5, 1]; the second square
    #   of each at 0.0, the last block at 0.0 throughout.
    # Arithmetic: blocks 2 and 3 agree on weight 1.0 / 1.0 = 1.0 (their
    #   second square weighs 0). Block 4 weighs 0, so its plain share against
    #   [5, 1] is 2/2 = 1.0, and it joins: one type of 4 copies. Position 1
    #   weighs 0 in all four, so counts: 1 three times, 0 once; majority 1,
    #   share 3/4; field (0, 5) at 0.0 < 0.8 takes 1. Agreement 7/8.
    # Expected: Change (0, 5, 0 -> 1, 0.75), types [[0, 0, 0, 0]].
    assert result.changes == (Change(0, 5, 0, 1, _approx(0.75)),)
    np.testing.assert_array_equal(result.types, [[0, 0, 0, 0]])
    assert result.agreement == _approx(7 / 8)


def test_majority_ties_go_to_the_larger_count_then_the_lower_label():
    lower = _vote(
        [[9, 9, 9, 4, 9, 9, 9, 6, 9, 9, 9, 4, 9, 9, 9, 6]],
        [[1, 1, 1, 0.5] * 4],
        1,
        4,
    )
    # Source: ticket step 2, ties go to the larger count, then the lower label.
    # Formula: as above.
    # Inputs: four 1 x 4 blocks [9, 9, 9, x] with x = 4, 6, 4, 6 at 0.5.
    # Arithmetic: each joins at 1.0 or 3.0 / 3.5 = 0.857. Position 3: label 4
    #   at 0.5 + 0.5 = 1.0 from 2 squares, label 6 the same; the weight and
    #   the count tie, so the lower label 4 wins, share 1.0 / 2.0 = 0.5; the
    #   two 6s at 0.5 < 0.8 take 4. Agreement 14/16.
    # Expected: changes at (0, 7) and (0, 15), 6 -> 4, share 0.5.
    assert lower.changes == (Change(0, 7, 6, 4, _approx(0.5)), Change(0, 15, 6, 4, _approx(0.5)))
    assert lower.agreement == _approx(14 / 16)

    count = _vote(
        [[9, 9, 9, 3, 9, 9, 9, 3, 9, 9, 9, 2]], [[1, 1, 1, 0.4, 1, 1, 1, 0.4, 1, 1, 1, 0.8]], 1, 4
    )
    # Source: ticket step 2.
    # Formula: as above.
    # Inputs: three 1 x 4 blocks [9, 9, 9, x] with x = 3 at 0.4, 3 at 0.4,
    #   2 at 0.8.
    # Arithmetic: the third joins at 3.0 / 3.8 = 0.789. Position 3: label 3
    #   at 0.4 + 0.4 = 0.8 from 2 squares, label 2 at 0.8 from 1; the weight
    #   ties and the larger count wins, 3, although 2 is the lower label. The
    #   2 at 0.8 is not below 0.8, so a Break. Agreement 11/12.
    # Expected: Break (0, 11, read 2, majority 3, 0.8), no changes.
    assert count.breaks == (Break(0, 11, 2, 3, _approx(0.8)),)
    assert count.changes == ()
    assert count.agreement == _approx(11 / 12)


def test_type_ties_go_to_the_lower_type_id():
    labels = np.array([[1, 1, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0]])
    result = _vote(labels, np.ones((1, 12)), 1, 4)
    # Source: ticket steps 4 and 5, "ties: the lower type id".
    # Formula: agreement = equal squares / 4 (all weights 1.0).
    # Inputs: 1 x 4 blocks b0 = 1100, b1 = 0000, b2 = 1000.
    # Arithmetic: b0 starts t0; b1 vs t0 2/4 starts t1; b2 scores 3/4 against
    #   both, joins t0, and t0's position 1 ties 1 against 0, lower label, so
    #   t0 = 1000. Pass 2: b0 3/4 vs 2/4, t0; b1 3/4 vs 4/4, t1; b2 4/4, t0.
    #   Ties to the higher id would put b2 in t1 instead and keep it there in
    #   pass 2 (3/4 against t0 = 1100 and t1 = 0000), giving [0, 1, 1].
    #   Repeat: a period needs two whole copies, p <= 3 // 2 = 1, and [1, 0]
    #   differs from [0, 1], so px = 3, the whole row.
    # Expected: types [[0, 1, 0]], repeat (1, 3 x 4).
    np.testing.assert_array_equal(result.types, [[0, 1, 0]])
    assert result.repeat == (1, 12)


def test_refinement_pass_reassigns_and_renumbers_types():
    blocks = [
        [0, 0, 0, 0, 0, 0, 1, 1],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [1, 1, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 1, 1, 1, 1],
        [0, 0, 0, 0, 0, 1, 1, 1],
        [0, 0, 0, 0, 0, 0, 1, 1],
    ]
    labels = np.array(blocks).reshape(1, 48)
    result = _vote(labels, np.ones((1, 48)), 1, 8)
    # Source: ticket steps 4 and 5.
    # Formula: agreement = equal squares / 8 (all weights 1.0); join the best
    #   type at >= 0.75 (ties to the lower id), else a new type.
    # Inputs: six 1 x 8 blocks b0 to b5 as listed.
    # Arithmetic, pass 1:
    #   b0 starts t0 (majority 00000011).
    #   b1 vs t0: 6/8 = 0.75, joins; positions 6 and 7 tie, lower label 0,
    #     majority 00000000.
    #   b2 vs t0: 6/8, joins; majority stays 00000000 (0 wins 2 to 1).
    #   b3 vs t0: 4/8, starts t1 (00001111).
    #   b4 vs t0 5/8, vs t1 7/8, joins t1; position 4 ties, 0: 00000111.
    #   b5 vs t0 6/8, vs t1 7/8, joins t1; majority 00000111.
    # Pass 2 against t0 = 00000000 and t1 = 00000111: b0 scores 6/8 and 7/8,
    #   moves to t1; b1 8/8 and 5/8, t0; b2 6/8 and 3/8, t0; b3 4/8 and 7/8,
    #   b4 5/8 and 8/8, b5 6/8 and 7/8, all t1. Old ids [1, 0, 0, 1, 1, 1]
    #   renumber by first appearance to [0, 1, 1, 0, 0, 0].
    # Majorities: type 0 = b0, b3, b4, b5: position 4 reads 0, 1, 0, 0 -> 0;
    #   position 5 reads 0, 1, 1, 0, a full tie -> 0; so 00000011. Type 1 =
    #   b1, b2 has 2 copies and does not vote; its positions 0 and 1 read 0
    #   and 1, a full tie -> 0, so its majority is 00000000.
    # Vote, all confidence 1.0, so differences are Breaks: b3 at positions 4
    #   and 5 (columns 3 x 8 + 4 = 28 and 29), b4 at position 5 (column 37).
    #   Agreement: 29 of type 0's 32 squares, and, since type 1 has two
    #   copies, 8 + 6 = 14 of its 16 (b2 differs at positions 0 and 1):
    #   (29 + 14) / (32 + 16) = 43/48.
    # Repeat: a period needs two whole copies, p <= 6 // 2 = 3; shifted by 1,
    #   2 and 3, [0, 1, 1, 0, 0, 0] differs from itself ([1, 1, 0, 0, 0] vs
    #   [0, 1, 1, 0, 0], [1, 0, 0, 0] vs [0, 1, 1, 0], [0, 0, 0] vs
    #   [0, 1, 1]), so px = 6, the whole row: repeat (1, 6 x 8). (p = 5
    #   would match [0] with [0], one block.)
    # Expected: as listed. Without pass 2 the types would be [0, 0, 0, 1, 1, 1].
    np.testing.assert_array_equal(result.types, [[0, 1, 1, 0, 0, 0]])
    assert result.breaks == (
        Break(0, 28, 1, 0, _approx(1.0)),
        Break(0, 29, 1, 0, _approx(1.0)),
        Break(0, 37, 1, 0, _approx(1.0)),
    )
    assert result.changes == ()
    assert result.agreement == _approx(43 / 48)
    assert result.repeat == (1, 48)


def test_a_one_by_one_block_confirms_no_repeat():
    labels = [[0, 1, 0, 1], [0, 1, 0, 1]]
    result = _vote(labels, np.ones((2, 4)), 1, 1)
    # Source: vision-22, a 1 x 1 block confirms no repeat.
    # Formula: block_rows x block_cols = 1, so repeat = (rows, cols), whatever
    #   the labels.
    # Inputs: two rows of [0, 1, 0, 1] in 1 x 1 blocks, confidence 1.0.
    # Arithmetic: the types are the labels, with period 1 down and 2 across,
    #   which would give (1, 2); the block is 1 x 1, so the repeat is the
    #   whole 2 x 4 field.
    # Expected: repeat (2, 4).
    np.testing.assert_array_equal(result.types, labels)
    assert result.repeat == (2, 4)


def test_agreement_is_zero_without_a_repeated_block():
    distinct = np.kron([[0, 1, 2], [3, 4, 5]], np.ones((2, 2), dtype=int))
    result = _vote(distinct, np.ones((4, 6)), 2, 2)
    # Source: vision-22 and the rule that an undefined silhouette gives 0,
    #   never 1: no repeated block is no evidence of a repeat.
    # Formula: agreement over the squares of the types with at least two
    #   copies, 0.0 when there are none.
    # Inputs: the all-distinct case of test_repeat_comes_from_the_type_layout,
    #   six 2 x 2 blocks of one label each.
    # Arithmetic: any two blocks agree on 0 of 4 squares, so six types of one
    #   copy each, none with two.
    # Expected: no vote, agreement 0.0.
    assert result.voted is False
    assert result.agreement == 0.0

    uniform = _vote(np.zeros((3, 3), dtype=int), np.ones((3, 3)), 1, 1)
    # Inputs: a 3 x 3 field of label 0 in 1 x 1 blocks, one type of 9 copies.
    # Arithmetic: a 1 x 1 block never counts toward the agreement, however
    #   many copies its type has, and its repeat is the whole field.
    # Expected: agreement 0.0, repeat (3, 3).
    assert uniform.agreement == 0.0
    assert uniform.repeat == (3, 3)


def test_a_type_of_two_copies_counts_toward_agreement_without_voting():
    result = _vote([[0, 1, 0, 0]], [[1.0, 1.0, 1.0, 0.2]], 1, 2)
    # Source: vision-22, agreement over every type with at least two copies.
    # Formula: block agreement = matching weight / block weight; majority by
    #   summed weight.
    # Inputs: 1 x 2 blocks [0, 1] and [0, 0], the second's last square at 0.2.
    # Arithmetic: the second block agrees 1.0 / 1.2 = 0.833 >= 0.75, so one
    #   type of 2 copies, under min_copies 3, so no vote. Position 1: label 1
    #   at 1.0 beats label 0 at 0.2, majority 1. Squares equal to their
    #   majority: (0, 0), (0, 1) and (0, 2), not (0, 3): 3 of 4.
    # Expected: no vote, no changes, types [[0, 0]], agreement 3/4.
    assert result.voted is False
    assert result.changes == ()
    np.testing.assert_array_equal(result.types, [[0, 0]])
    assert result.agreement == _approx(3 / 4)


def test_inputs_are_not_mutated():
    labels, confidence = _three_copies_with_misread(read=0, conf=0.3)
    labels_before, confidence_before = labels.copy(), confidence.copy()
    result = vote(labels, confidence, 3, 3)
    # Source: ticket, "inputs are never mutated".
    # Formula, Inputs, Arithmetic: the misread case, which changes (1, 7).
    # Expected: both inputs equal their copies, and the result owns its arrays.
    assert result.changes
    np.testing.assert_array_equal(labels, labels_before)
    np.testing.assert_array_equal(confidence, confidence_before)
    assert not np.shares_memory(result.labels, labels)
    assert not np.shares_memory(result.confidence, confidence)


@pytest.mark.parametrize(
    ("labels", "confidence", "block"),
    [
        (np.zeros((3, 4), dtype=int), np.ones((3, 4)), (2, 2)),
        (np.zeros((4, 3), dtype=int), np.ones((4, 3)), (2, 2)),
        (np.zeros((4, 4), dtype=int), np.ones((4, 2)), (2, 2)),
        (np.zeros(4, dtype=int), np.ones(4), (1, 1)),
        (np.zeros((0, 0), dtype=int), np.ones((0, 0)), (1, 1)),
        (np.zeros((4, 4), dtype=int), np.ones((4, 4)), (0, 2)),
        (np.zeros((4, 4)), np.ones((4, 4)), (2, 2)),
        (np.zeros((4, 4), dtype=int), np.full((4, 4), 1.5), (2, 2)),
        (np.zeros((4, 4), dtype=int), np.full((4, 4), np.nan), (2, 2)),
    ],
    ids=[
        "rows-not-multiple",
        "cols-not-multiple",
        "shape-mismatch",
        "one-dimensional",
        "empty",
        "zero-block",
        "float-labels",
        "confidence-above-1",
        "confidence-nan",
    ],
)
def test_bad_inputs_raise(labels, confidence, block):
    # Source: ticket, "raise ValueError otherwise"; labels are int fabric
    #   ids and confidence lies in [0, 1].
    # Expected: ValueError.
    with pytest.raises(ValueError):
        vote(labels, confidence, *block)
