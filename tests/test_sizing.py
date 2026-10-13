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
from qrep.model.unitmap import CornerUnit, PlainUnit
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


def _snowball_grid() -> Quilt:
    """4 x 4 squares of 12 e in one 16 e border; the top-left square is a
    snowball corner unit whose leg is 1/3 of the side (12 x 1/3 = 4 e)."""
    units = [CornerUnit(row=0, col=0, corners={"top_left": "b"}, leg="1/3", confidence=1.0)]
    units += [
        PlainUnit(row=r, col=c, confidence=1.0)
        for r in range(4)
        for c in range(4)
        if (r, c) != (0, 0)
    ]
    fabrics = [Fabric(id="a", name="A", color="#333366"), Fabric(id="b", name="B", color="#eeeedd")]
    return Quilt(
        metadata=QuiltMetadata(name="snowball"),
        palette=Palette(fabrics=fabrics),
        center=GridRegion(
            rows=4, cols=4, cell_size=12, cells=[["a"] * 4 for _ in range(4)], unit_map=units
        ),
        borders=[{"fabric_id": "b", "width": 16}],
        binding=Binding(fabric_id="a"),
    )


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


def test_the_square_step_setting_is_read_when_sizing(monkeypatch):
    # Set the step to 1/2 in (4 e): the offered list follows it, as above, and
    # the DIC at 75 x 90 in still lands on 1 1/2 in (12 e, a multiple of 4):
    # 45 x 12 + 2 x 30 = 600 and 55 x 12 + 60 = 720, recorded at step 4.
    monkeypatch.setattr(sizing, "SQUARE_STEP", 4)
    assert sizing.square_sizes() == (8, 12, 16, 20, 24, 28, 32)
    result = size_pattern(load(FIXTURE), _typed(600, 720))
    assert result.model.center.cell_size == 12
    assert result.model.size_basis.rounding_step == 4


def test_border_snaps_to_quarter_inch_within_floor_and_cap():
    # 21 e (2 5/8 in): round_div(21, 2) = (21 + 1) // 2 = 11 -> 22 e (2 3/4 in)
    assert sizing.snap_border(21) == 22
    # 30 e (3 3/4 in) is already a whole quarter inch
    assert sizing.snap_border(30) == 30
    # 1 e: round_div(1, 2) = (1 + 1) // 2 = 1 -> 2 e; the rounding alone
    # reaches the BAND_FLOOR from any width of at least one eighth
    assert sizing.snap_border(1) == 2
    # 113 e: round_div(113, 2) = 57 -> 114 e, above the cap -> 112 e
    assert sizing.snap_border(113) == 112
    assert sizing.snap_border(400) == 112
    # no border is zero or less wide
    with pytest.raises(ValueError, match="border width"):
        sizing.snap_border(0)
    with pytest.raises(ValueError, match="border width"):
        sizing.snap_border(-10)


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


def test_size_at_snaps_kept_borders_and_drops_the_basis():
    # The read-shaped DIC keeps its 23 e border, which snaps:
    # round_div(23, 2) = (23 + 1) // 2 = 12 -> 24 e (3 in). At 1 1/4 in:
    # 45 x 10 + 2 x 24 = 498, 55 x 10 + 48 = 598.
    sized = sizing.size_at(_read_shaped(9, 23), 10)
    assert [band.width for band in sized.borders] == [24]
    assert (sized.finished_width, sized.finished_height) == (498, 598)
    # A typed basis says 600 x 720; at 2 in squares the quilt is 780 x 940,
    # so the stale basis goes.
    typed = size_pattern(load(FIXTURE), _typed(600, 720)).model
    assert sizing.size_at(typed, 16).size_basis is None


def test_size_at_refuses_a_square_off_the_list_or_a_wrong_border():
    # 1 1/8 in (9 e) is not a whole quarter inch
    with pytest.raises(ValueError, match="square"):
        sizing.size_at(load(FIXTURE), 9)
    # the DIC has one border band, so two widths do not fit it
    with pytest.raises(ValueError, match="border"):
        sizing.size_at(load(FIXTURE), 12, [20, 20])
    # a border of no width
    with pytest.raises(ValueError, match="border width"):
        sizing.size_at(load(FIXTURE), 12, [0])


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
    # A typed size is a user fact at 1.0 (CLAUDE.md; schema.py's basis rule).
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
    # a preset is a user fact at 1.0, like a typed size
    assert result.model.size_basis.source == "preset"
    assert result.model.size_basis.confidence == 1.0


def test_a_size_you_set_on_a_read_stays_a_user_fact():
    # The read's own estimate is unmeasured (0.0, below), but a typed or
    # preset size is yours, so its basis stands at 1.0 on a read as well.
    read = _read_shaped(9, 23)
    typed = size_pattern(read, _typed(600, 720)).model.size_basis
    preset = size_pattern(read, SizeRequest(source="preset", preset="Twin")).model.size_basis
    assert (typed.source, typed.confidence) == ("typed", 1.0)
    assert (preset.source, preset.confidence) == ("preset", 1.0)


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


def test_a_default_from_a_read_without_provenance_is_not_hand_authored():
    # A model that drops its provenance defaults to "authored", but its
    # squares were read at confidence 0.3, so the estimate is a read's: 0.0.
    data = json.loads(dumps(_read_shaped(9, 23)))
    data["center"]["cell_confidence"] = [[0.3] * 45 for _ in range(55)]
    del data["provenance"]
    result = size_pattern(loads(json.dumps(data)), SizeRequest(source="default"))
    assert result.model.size_basis.confidence == 0.0


def test_a_default_refuses_a_size_you_set():
    # A typed or preset size replaced the read's estimate, so no estimate is
    # left to label as one.
    typed = size_pattern(load(FIXTURE), _typed(600, 720)).model
    with pytest.raises(ValueError, match="typed"):
        size_pattern(typed, SizeRequest(source="default"))
    preset = size_pattern(load(FIXTURE), SizeRequest(source="preset", preset="Twin")).model
    with pytest.raises(ValueError, match="preset"):
        size_pattern(preset, SizeRequest(source="default"))


@pytest.mark.parametrize(
    ("request_", "achieved"),
    [
        # 86 x 67.5 in: 400 x 480, worked in test_the_sample_at_86_by_67_5
        (SizeRequest(source="typed", width=688, height=540), (400, 480)),
        # Queen 90 x 108 in = 720 x 864 e. Width: 1 3/4 in gives 45 x 14 + 2 x 36
        # = 702 (short by 18), 2 in gives 800 (over by 80) -> 14. Height:
        # 55 x 14 + 72 = 842 (short by 22), 55 x 16 + 80 = 960 (over by 96)
        # -> 14. So 702 x 842.
        (SizeRequest(source="preset", preset="Queen"), (702, 842)),
        # the model's own 600 x 720, met exactly at 1 1/2 in
        (SizeRequest(source="default"), (600, 720)),
    ],
    ids=["typed", "preset", "default"],
)
def test_every_basis_matches_its_sized_model(request_, achieved):
    result = size_pattern(load(FIXTURE), request_)
    model, basis, stored = result.model, result.basis, result.model.size_basis
    assert (model.finished_width, model.finished_height) == achieved
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


def test_the_one_eighth_step_keeps_the_sprint_3_reconcile():
    # The DIC asked for 690 e (86 1/4 in) tall at the default step. Sprint 3
    # rounds the exact cell: round_div(690 x 12, 55 x 12 + 2 x 30)
    # = round_div(8280, 720) = (8280 + 360) // 720 = 12, border
    # round_div(30 x 12, 12) = 30, so 600 x 720. It stays 12 although 11 e
    # (55 x 11 + 2 x round_div(330, 12) = 605 + 56 = 661, short by 29) misses
    # by less than 12 e (720, over by 30): the default step is the sprint 3
    # rule, kept exactly for its callers.
    updated, _requested, achieved = apply_finished_size(load(FIXTURE), None, 690)
    assert updated.center.cell_size == 12
    assert (achieved["width"], achieved["height"]) == (600, 720)


def test_pattern_borders_never_exceed_the_cap():
    # 10 x 13 at 12 e with a 100 e border, asked for 250 in (2000 e) wide in
    # 1/4 in steps: every square misses short, so the largest, 32 e, wins. The
    # border would scale to 2 x round_div(100 x 32, 2 x 12)
    # = 2 x (3212 // 24) = 266 e and stops at the 112 e cap:
    # 13 x 32 + 2 x 112 = 416 + 224 = 640 e.
    quilt = _grid_model(10, 13, 12, 100)
    updated, _requested, achieved = apply_finished_size(quilt, 2000, None, step=2)
    assert updated.center.cell_size == 32
    assert updated.borders[0].width == 112
    assert achieved["width"] == 640


def test_pattern_borders_never_fall_below_the_floor():
    # 10 x 13 at 32 e with a 1 e border, asked for 10 in (80 e) wide in 1/4 in
    # steps. At 3/4 in the border scales to 2 x round_div(1 x 6, 2 x 32)
    # = 2 x (38 // 64) = 0 and rises to the 2 e floor: 13 x 6 + 2 x 2 = 82
    # (over by 2); at 1 in it is 0 again, so 2 e: 13 x 8 + 4 = 108 (over by
    # 28) -> 3/4 in with a 2 e border.
    quilt = _grid_model(10, 13, 32, 1)
    updated, _requested, achieved = apply_finished_size(quilt, 80, None, step=2)
    assert updated.center.cell_size == 6
    assert updated.borders[0].width == 2
    assert achieved["width"] == 82


@pytest.mark.parametrize("step", [1, 2], ids=["sprint-3", "pattern"])
def test_apply_finished_size_drops_a_stale_basis(step):
    # Sized to 75 x 90 in by a typed size, then resized to 502 e wide: the
    # basis would still say 600 x 720, so it goes on either path.
    typed = size_pattern(load(FIXTURE), _typed(600, 720)).model
    assert typed.size_basis is not None
    resized, _requested, _achieved = apply_finished_size(typed, 502, None, step=step)
    assert resized.size_basis is None


# ---------------------------------------------------------------------------
# corner units keep their legs whole
# ---------------------------------------------------------------------------


def test_sizing_skips_squares_that_break_a_corner_leg():
    # A 1/3 leg stays whole only on squares divisible by 3, so the 1/4 in list
    # narrows to 6, 12, 18, 24 and 30 e. Width 108 e on _snowball_grid, its
    # border 2 x round_div(16 s, 24):
    #   12 e: border 2 x (204 // 24) = 16, 4 x 12 + 32 = 80, short by 28
    #   18 e: border 2 x (300 // 24) = 24, 4 x 18 + 48 = 120, over by 12
    #   24 e: border 2 x (396 // 24) = 32, 4 x 24 + 64 = 160, over by 52
    # -> 18 e (2 1/4 in), 120 x 120, leg 18 / 3 = 6 e. (16 e would meet 108
    # exactly, 4 x 16 + 2 x 22, but leaves the leg at 16/3 e.)
    result = size_pattern(_snowball_grid(), _typed(width=108))
    assert result.model.center.cell_size == 18
    assert (result.basis.achieved_width, result.basis.achieved_height) == (120, 120)
    # the sized model loads again, corner legs and all
    assert loads(dumps(result.model)).center.cell_size == 18


def test_a_square_that_breaks_a_corner_leg_is_refused():
    # 16 e is on the 1/4 in list, but a 1/3 leg of it is 16/3 e
    with pytest.raises(ValueError, match="corner leg"):
        sizing.size_at(_snowball_grid(), 16)
    # The sprint 3 rule picks round_div(108 x 12, 4 x 12 + 2 x 16)
    # = round_div(1296, 80) = 1336 // 80 = 16 e: refused, never rounded.
    with pytest.raises(ValueError, match="corner leg"):
        apply_finished_size(_snowball_grid(), 108, None)


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
