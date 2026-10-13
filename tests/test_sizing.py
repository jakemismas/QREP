"""A10: rotary-friendly finished sizing in one model module (#132).

Every expected value is hand-computed in the comment beside it. The double
Irish chain fixture (tests/fixtures/double_irish_chain.json) is 45 columns by
55 rows of 1 1/2 in squares (12 e) inside one 3 3/4 in border (30 e):
45 x 12 + 2 x 30 = 600 e (75 in) by 55 x 12 + 60 = 720 e (90 in).

On the pattern path a border scales with the square and snaps to 1/4 in
(2 e), half-up: at square s the DIC border is
2 x round_div(30 x s, 2 x 12) = 2 x round_div(30 s, 24) = 2 x ((30 s + 12) // 24).
"""

import json
from pathlib import Path

import pytest

from qrep import bridge
from qrep.contract import SizeBasis, SizeRequest
from qrep.model import dumps, load, loads
from qrep.model import finished_size, sizing
from qrep.model.schema import (
    Binding,
    ConfirmedBlocks,
    Fabric,
    FinishedSizeBasis,
    GridRegion,
    Palette,
    Quilt,
    QuiltMetadata,
)
from qrep.model.sizing import apply_finished_size, round_div, size_pattern
from qrep.viewer import sizing as viewer_sizing

FIXTURE = Path(__file__).parent / "fixtures" / "double_irish_chain.json"


def _grid_model(rows: int, cols: int, cell: int, band: int | None = None) -> Quilt:
    fabrics = [Fabric(id="a", name="A", color="#333366"), Fabric(id="b", name="B", color="#eeeedd")]
    cells = [["a" if (r + c) % 2 == 0 else "b" for c in range(cols)] for r in range(rows)]
    return Quilt(
        metadata=QuiltMetadata(name="probe"),
        palette=Palette(fabrics=fabrics),
        center=GridRegion(rows=rows, cols=cols, cell_size=cell, cells=cells),
        borders=[] if band is None else [{"fabric_id": "b", "width": band}],
        binding=Binding(fabric_id="a"),
    )


def _read_shaped(cell: int, band: int, basis: dict | None = None) -> Quilt:
    """The DIC as a photo read stores it: a guessed square and border."""
    data = json.loads(dumps(load(FIXTURE)))
    data["center"]["cell_size"] = cell
    data["borders"][0]["width"] = band
    data["provenance"] = {"source": "cv", "stage_confidence": {}}
    data["size_basis"] = basis
    return loads(json.dumps(data))


def _typed(width: int | None = None, height: int | None = None) -> SizeRequest:
    return SizeRequest(source="typed", width=width, height=height)


# ---------------------------------------------------------------------------
# one home for the moved names
# ---------------------------------------------------------------------------


def test_round_div_half_up():
    # 29/2 = 14.5 rounds UP to 15 (half-up, not banker's)
    assert round_div(29, 2) == 15
    # 12/5 = 2.4 -> 2; 13/5 = 2.6 -> 3
    assert round_div(12, 5) == 2
    assert round_div(13, 5) == 3
    # 660/45 = 14.67 -> 15
    assert round_div(660, 45) == 15
    assert round_div(0, 45) == 0


def test_moved_names_have_one_home():
    # The viewer and finished_size keep handing out these names until A7, so
    # each must be the sizing module's own object, never a copy that drifts.
    assert viewer_sizing.PRESETS is sizing.PRESETS
    assert viewer_sizing.round_div is sizing.round_div
    assert finished_size.apply_finished_size is sizing.apply_finished_size
    for name in ("CELL_MIN", "CELL_MAX", "BAND_FLOOR"):
        assert getattr(finished_size, name) == getattr(sizing, name)


def test_clamps_are_the_frozen_literals():
    # REBASELINE.md literals B8 (3/4 in = 6 e), B9 (4 in = 32 e), B10
    # (1/4 in = 2 e) and C3's band cap (14 in = 14 x 8 = 112 e)
    assert (sizing.CELL_MIN, sizing.CELL_MAX, sizing.BAND_FLOOR, sizing.BAND_MAX) == (6, 32, 2, 112)
    # the 1/4 in step: 8 e per inch / 4 = 2 e
    assert sizing.SQUARE_STEP == 2


# ---------------------------------------------------------------------------
# the square sizes the pattern offers, and border snapping
# ---------------------------------------------------------------------------


def test_offered_square_sizes_are_quarter_inch_steps():
    # every 1/4 in (2 e) from 3/4 in (6 e) to 4 in (32 e):
    # (32 - 6) / 2 + 1 = 14 sizes
    assert sizing.square_sizes() == (6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32)
    # cut size = finished + 2 x 1/4 in seam allowance = finished + 4 e, and an
    # even number of eighths is a whole quarter inch. The reference cut sizes:
    # 6 + 4 = 10 e (1 1/4 in), 16 + 4 = 20 e (2 1/2 in), 32 + 4 = 36 e (4 1/2 in)
    cuts = [square + 4 for square in sizing.square_sizes()]
    assert all(cut % 2 == 0 for cut in cuts)
    assert {10, 20, 36} <= set(cuts)


def test_square_step_is_a_setting():
    # a 1/2 in step (4 e) starts at the first multiple of 4 at or above 6,
    # which is 8: 8, 12, ..., 32 is (32 - 8) / 4 + 1 = 7 sizes
    assert sizing.square_sizes(4) == (8, 12, 16, 20, 24, 28, 32)
    # the one-eighth step offers every eighth: 32 - 6 + 1 = 27 sizes
    assert sizing.square_sizes(1) == tuple(range(6, 33))
    # a step of 0 offers nothing, and so does 5 in (40 e): no multiple of 40
    # lies between 6 and 32
    with pytest.raises(ValueError, match="step"):
        sizing.square_sizes(0)
    with pytest.raises(ValueError, match="step"):
        sizing.square_sizes(40)


def test_border_snaps_to_quarter_inch_within_floor_and_cap():
    # 21 e (2 5/8 in): round_div(21, 2) = (21 + 1) // 2 = 11 -> 22 e (2 3/4 in)
    assert sizing.snap_border(21) == 22
    # 30 e (3 3/4 in) is already a whole quarter inch
    assert sizing.snap_border(30) == 30
    # 1 e: round_div(1, 2) = (1 + 1) // 2 = 1 -> 2 e, the BAND_FLOOR
    assert sizing.snap_border(1) == 2
    # 113 e: round_div(113, 2) = 57 -> 114 e, above the cap -> 112 e
    assert sizing.snap_border(113) == 112
    assert sizing.snap_border(400) == 112


# ---------------------------------------------------------------------------
# the achieved size from a chosen square size and border widths
# ---------------------------------------------------------------------------


def test_size_at_a_chosen_square_counts_whole_squares_and_blocks():
    # the DIC at 2 in squares (16 e), keeping its 3 3/4 in border:
    #   45 x 16 + 2 x 30 = 720 + 60 = 780 e (97 1/2 in)
    #   55 x 16 + 2 x 30 = 880 + 60 = 940 e (117 1/2 in)
    quilt = load(FIXTURE)
    sized = sizing.size_at(quilt, 16)
    assert sized.center.cell_size == 16
    assert [band.width for band in sized.borders] == [30]
    assert (sized.finished_width, sized.finished_height) == (780, 940)
    # The counts never change, so the size moves in whole blocks too: with
    # 9 x 11 blocks of 5 x 5 squares, 9 x 5 x 16 + 60 = 780 and
    # 11 x 5 x 16 + 60 = 940.
    blocks = ConfirmedBlocks(blocks_across=9, blocks_down=11, squares_across=5, squares_down=5)
    blocked = sizing.size_at(quilt.model_copy(update={"confirmed_blocks": blocks}), 16)
    assert blocked.confirmed_blocks == blocks
    assert (blocked.center.cols, blocked.center.rows) == (9 * 5, 11 * 5)
    assert (blocked.finished_width, blocked.finished_height) == (780, 940)
    # the input model is left as it was
    assert quilt.center.cell_size == 12


def test_size_at_snaps_the_border_widths_you_choose():
    # a chosen 21 e border snaps to 22 e; at 1 1/2 in squares:
    #   45 x 12 + 2 x 22 = 540 + 44 = 584 e, 55 x 12 + 44 = 660 + 44 = 704 e
    sized = sizing.size_at(load(FIXTURE), 12, [21])
    assert [band.width for band in sized.borders] == [22]
    assert (sized.finished_width, sized.finished_height) == (584, 704)


def test_size_at_refuses_a_square_off_the_list_or_a_wrong_border_count():
    # 1 1/8 in (9 e) is not a whole quarter inch
    with pytest.raises(ValueError, match="square"):
        sizing.size_at(load(FIXTURE), 9)
    # the DIC has one border band, so two widths do not fit it
    with pytest.raises(ValueError, match="border"):
        sizing.size_at(load(FIXTURE), 12, [20, 20])


# ---------------------------------------------------------------------------
# the nearest achievable size for a typed or preset size
# ---------------------------------------------------------------------------


def test_dic_at_75_by_90_returns_exactly_75_by_90():
    # 75 x 90 in = 600 x 720 e. At 1 1/2 in (12 e) the border is
    # 2 x round_div(360, 24) = 2 x (372 // 24) = 2 x 15 = 30 e, so
    #   width 45 x 12 + 2 x 30 = 600, a miss of 0
    #   height 55 x 12 + 2 x 30 = 720, a miss of 0
    result = size_pattern(load(FIXTURE), _typed(600, 720))
    assert result.outcome == "sized"
    assert result.model.center.cell_size == 12
    assert [band.width for band in result.model.borders] == [30]
    assert (result.model.finished_width, result.model.finished_height) == (600, 720)
    assert result.basis == SizeBasis(
        source="typed",
        requested_width=600,
        requested_height=720,
        achieved_width=600,
        achieved_height=720,
    )
    assert result.model.size_basis == FinishedSizeBasis(
        source="typed",
        requested_width=600,
        requested_height=720,
        achieved_width=600,
        achieved_height=720,
        rounding_step=2,
        confidence=1.0,
    )


def test_a_request_halfway_between_two_sizes_takes_the_larger_square():
    # a typed width of 551 e (68 7/8 in) on the DIC:
    #   1 1/4 in (10 e): border 2 x round_div(300, 24) = 2 x (312 // 24) = 26,
    #     45 x 10 + 2 x 26 = 502, short by 551 - 502 = 49
    #   1 1/2 in (12 e): 600, over by 600 - 551 = 49
    # A tie: the larger square wins, so 1 1/2 in and 600 x 720.
    result = size_pattern(load(FIXTURE), _typed(width=551))
    assert result.model.center.cell_size == 12
    assert (result.basis.achieved_width, result.basis.achieved_height) == (600, 720)
    assert (result.basis.requested_width, result.basis.requested_height) == (551, None)
    # One eighth less, 550 e, is 48 from 502 and 50 from 600, so 1 1/4 in:
    # 502 by 55 x 10 + 52 = 602.
    result = size_pattern(load(FIXTURE), _typed(width=550))
    assert result.model.center.cell_size == 10
    assert (result.basis.achieved_width, result.basis.achieved_height) == (502, 602)


def test_a_request_below_the_smallest_square_clamps_to_three_quarter_inch():
    # 24 x 30 in = 192 x 240 e. Even 3/4 in (6 e) squares overshoot it: the
    # border is 2 x round_div(180, 24) = 2 x (192 // 24) = 16, so
    #   width 45 x 6 + 2 x 16 = 302 (over by 110)
    #   height 55 x 6 + 32 = 362 (over by 122)
    # and every larger square misses by more -> 3/4 in, 302 x 362 e
    # (37 3/4 x 45 1/4 in), with the miss reported beside the request.
    result = size_pattern(load(FIXTURE), _typed(192, 240))
    assert result.model.center.cell_size == 6
    assert [band.width for band in result.model.borders] == [16]
    assert (result.basis.achieved_width, result.basis.achieved_height) == (302, 362)
    assert (result.basis.requested_width, result.basis.requested_height) == (192, 240)


def test_the_sample_at_86_by_67_5():
    # 86 x 67.5 in = 688 x 540 e (the case C2b re-expresses in size.spec.ts).
    # Height 540: the exact square is 540 x 12 / 720 = 9 e, halfway between
    # 1 in and 1 1/4 in, but the snapped borders break that tie:
    #   1 in (8 e): border 2 x round_div(240, 24) = 2 x (252 // 24) = 20,
    #     55 x 8 + 2 x 20 = 480, short by 60
    #   1 1/4 in (10 e): border 26, 55 x 10 + 52 = 602, over by 62 -> 1 in
    # Width 688:
    #   1 1/2 in (12 e): 600, short by 88
    #   1 3/4 in (14 e): border 2 x round_div(420, 24) = 2 x (432 // 24) = 36,
    #     45 x 14 + 72 = 702, over by 14
    #   2 in (16 e): border 2 x round_div(480, 24) = 2 x (492 // 24) = 40,
    #     45 x 16 + 80 = 800, over by 112 -> 1 3/4 in
    # The smaller of the two squares, 1 in: 45 x 8 + 2 x 20 = 400 by 480 e
    # (50 x 60 in).
    result = size_pattern(load(FIXTURE), _typed(688, 540))
    assert result.model.center.cell_size == 8
    assert [band.width for band in result.model.borders] == [20]
    assert (result.basis.achieved_width, result.basis.achieved_height) == (400, 480)


def test_a_preset_records_its_size_as_requested():
    # Twin is 70 x 90 in = 560 x 720 e (PRESETS).
    #   width 560: 1 1/4 in gives 502 (short by 58), 1 1/2 in gives 600
    #     (over by 40) -> 1 1/2 in
    #   height 720: 1 1/2 in gives 720 exactly -> 1 1/2 in
    # -> 600 x 720, and the preset's own size is the size asked for.
    result = size_pattern(load(FIXTURE), SizeRequest(source="preset", preset="Twin"))
    assert result.basis == SizeBasis(
        source="preset",
        requested_width=560,
        requested_height=720,
        achieved_width=600,
        achieved_height=720,
    )
    assert result.model.size_basis.source == "preset"
    assert result.model.size_basis.confidence == 1.0


def test_an_unknown_preset_is_refused():
    with pytest.raises(ValueError, match="Palace"):
        size_pattern(load(FIXTURE), SizeRequest(source="preset", preset="Palace"))


# ---------------------------------------------------------------------------
# the default size and the size basis
# ---------------------------------------------------------------------------


def test_a_default_size_is_never_recorded_as_typed():
    # No size set: the model's own 600 x 720 e is fitted, and 1 1/2 in
    # squares meet it exactly (as in the 75 x 90 case). The fixture is
    # hand-authored, so its estimate stands at 1.0 (CLAUDE.md).
    result = size_pattern(load(FIXTURE), SizeRequest(source="default"))
    assert result.basis == SizeBasis(
        source="default",
        requested_width=None,
        requested_height=None,
        achieved_width=600,
        achieved_height=720,
    )
    assert result.model.size_basis == FinishedSizeBasis(
        source="default",
        achieved_width=600,
        achieved_height=720,
        rounding_step=2,
        confidence=1.0,
    )


def test_a_default_size_from_a_read_carries_no_measured_confidence():
    # The read's estimate: 45 x 9 + 2 x 23 = 451 by 55 x 9 + 46 = 541 e. Its
    # border scales with the square: 2 x round_div(23 s, 2 x 9).
    # width 451:
    #   1 in (8 e): border 2 x round_div(184, 18) = 2 x (193 // 18) = 20,
    #     45 x 8 + 40 = 400, short by 51
    #   1 1/4 in (10 e): border 2 x round_div(230, 18) = 2 x (239 // 18) = 26,
    #     45 x 10 + 52 = 502, over by 51
    #   a tie -> 1 1/4 in
    # height 541: 55 x 8 + 40 = 480 (short by 61), 55 x 10 + 52 = 602 (over
    #   by 61), a tie -> 1 1/4 in
    # -> 502 x 602 e. The read recorded no confidence for its assumed
    # resolution, which measures nothing, so the estimate carries 0.0.
    result = size_pattern(_read_shaped(9, 23), SizeRequest(source="default"))
    assert result.model.center.cell_size == 10
    assert [band.width for band in result.model.borders] == [26]
    assert (result.basis.achieved_width, result.basis.achieved_height) == (502, 602)
    assert result.model.size_basis.source == "default"
    assert result.model.size_basis.confidence == 0.0


def test_a_default_keeps_the_estimate_confidence_a_read_recorded():
    basis = {
        "source": "default",
        "achieved_width": 451,
        "achieved_height": 541,
        "rounding_step": 1,
        "confidence": 0.4,
    }
    result = size_pattern(_read_shaped(9, 23, basis), SizeRequest(source="default"))
    assert result.model.size_basis.confidence == 0.4
    # the new basis states the 1/4 in step it applied
    assert result.model.size_basis.rounding_step == 2


def test_a_default_refuses_a_size_you_set():
    # A typed size replaced the read's estimate, so no estimate is left to
    # label as one.
    typed = size_pattern(load(FIXTURE), _typed(600, 720)).model
    with pytest.raises(ValueError, match="typed"):
        size_pattern(typed, SizeRequest(source="default"))


@pytest.mark.parametrize(
    "request_",
    [
        SizeRequest(source="typed", width=688, height=540),
        SizeRequest(source="preset", preset="Queen"),
        SizeRequest(source="default"),
    ],
    ids=["typed", "preset", "default"],
)
def test_every_basis_matches_its_sized_model(request_):
    result = size_pattern(load(FIXTURE), request_)
    model, basis, stored = result.model, result.basis, result.model.size_basis
    assert (basis.achieved_width, basis.achieved_height) == (
        model.finished_width,
        model.finished_height,
    )
    assert (stored.source, stored.requested_width, stored.requested_height) == (
        basis.source,
        basis.requested_width,
        basis.requested_height,
    )
    assert (stored.achieved_width, stored.achieved_height) == (
        basis.achieved_width,
        basis.achieved_height,
    )


# ---------------------------------------------------------------------------
# apply_finished_size: the step, the cap and a stale basis
# ---------------------------------------------------------------------------


def test_apply_finished_size_takes_a_step():
    # a borderless 10 x 13 grid at a width of 247 e:
    #   one-eighth step: 13 x 19 = 247 exactly -> 19 e
    #   1/4 in step: 18 e gives 13 x 18 = 234 (short by 13) and 20 e gives
    #   13 x 20 = 260 (over by 13); a tie -> the larger, 20 e
    quilt = _grid_model(10, 13, 12)
    eighth, _requested, achieved = apply_finished_size(quilt, 247, None)
    assert eighth.center.cell_size == 19
    assert achieved["width"] == 247
    quarter, _requested, achieved = apply_finished_size(quilt, 247, None, step=2)
    assert quarter.center.cell_size == 20
    assert achieved["width"] == 260


def test_borders_never_exceed_the_cap():
    # 10 x 13 at 12 e with a 100 e border, asked for 250 in (2000 e) wide:
    # every square misses short, so the largest, 32 e, wins. The border would
    # scale to round_div(100 x 32, 12) = 3206 // 12 = 267 e and stops at the
    # 112 e cap: 13 x 32 + 2 x 112 = 416 + 224 = 640 e.
    quilt = _grid_model(10, 13, 12, 100)
    updated, _requested, achieved = apply_finished_size(quilt, 2000, None)
    assert updated.center.cell_size == 32
    assert updated.borders[0].width == 112
    assert achieved["width"] == 640


def test_apply_finished_size_drops_a_stale_basis():
    # Sized to 75 x 90 in by a typed size, then resized to 502 e wide on the
    # v1 path: the basis would still say 600 x 720, so it goes.
    typed = size_pattern(load(FIXTURE), _typed(600, 720)).model
    assert typed.size_basis is not None
    resized, _requested, _achieved = apply_finished_size(typed, 502, None, step=2)
    assert resized.size_basis is None


# ---------------------------------------------------------------------------
# through the bridge's v2 entry point
# ---------------------------------------------------------------------------


def test_the_bridge_returns_the_sized_pattern():
    # the 75 x 90 in case above, through E1b's size_pattern entry point
    envelope = json.loads(
        bridge.size_pattern(
            dumps(load(FIXTURE)), json.dumps({"source": "typed", "width": 600, "height": 720})
        )
    )
    assert envelope["ok"] is True
    result = envelope["result"]
    assert result["outcome"] == "sized"
    assert result["basis"] == {
        "source": "typed",
        "requested_width": 600,
        "requested_height": 720,
        "achieved_width": 600,
        "achieved_height": 720,
    }
    assert result["model"]["size_basis"]["rounding_step"] == 2
    assert result["model"]["center"]["cell_size"] == 12
