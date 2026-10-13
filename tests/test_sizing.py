"""A10: rotary-friendly finished sizing in one model module (#132).

Every expected value is hand-computed in the comment beside it. The double
Irish chain fixture (tests/fixtures/double_irish_chain.json) is 45 columns by
55 rows of 1 1/2 in squares (12 e) inside one 3 3/4 in border (30 e):
45 x 12 + 2 x 30 = 600 e (75 in) by 55 x 12 + 60 = 720 e (90 in).

On the pattern path a border scales with the square and snaps to 1/4 in
(2 e), half-up: at square s the DIC border is
2 x round_div(30 x s, 2 x 12) = 2 x round_div(30 s, 24) = 2 x ((30 s + 12) // 24).
"""

import ast
import inspect
import json
import re
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
from qrep.render import save_render
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


def _two_bands(rows: int, cols: int, cell: int, band: int) -> Quilt:
    """_grid_model with two border bands of `band` e each."""
    data = json.loads(dumps(_grid_model(rows, cols, cell, band)))
    data["borders"] = data["borders"] * 2
    return loads(json.dumps(data))


def _read_shaped(cell: int, band: int, basis: dict | None = None) -> Quilt:
    """The DIC as a photo read stores it: a guessed square and border."""
    data = json.loads(dumps(load(FIXTURE)))
    data["center"]["cell_size"] = cell
    data["borders"][0]["width"] = band
    data["provenance"] = {"source": "cv", "stage_confidence": {}}
    data["size_basis"] = basis
    return loads(json.dumps(data))


def _snowball_grid(
    cell: int = 12, leg: str = "1/3", unit_confidence: float = 1.0, stages: dict | None = None
) -> Quilt:
    """4 x 4 squares of `cell` e in one 16 e border; the top-left square is a
    snowball corner unit whose leg is `leg` of the side (by default 1/3 of
    12 e = 4 e)."""
    units = [
        CornerUnit(row=0, col=0, corners={"top_left": "b"}, leg=leg, confidence=unit_confidence)
    ]
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
            rows=4, cols=4, cell_size=cell, cells=[["a"] * 4 for _ in range(4)], unit_map=units
        ),
        borders=[{"fabric_id": "b", "width": 16}],
        binding=Binding(fabric_id="a"),
        provenance={"source": "authored", "stage_confidence": stages or {}},
    )


def _top_level_bindings(module) -> set[str]:
    """Names a module's top level binds other than by import."""
    names = set()
    for node in ast.parse(inspect.getsource(module)).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
            continue
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            continue
        for target in targets:
            names |= {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}
    return names


def _envelope_error(envelope_json: str) -> dict:
    envelope = json.loads(envelope_json)
    assert envelope["ok"] is False
    return envelope["error"]


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
    # Small ints carry no identity, so an equal value cannot tell an import
    # from a redefined literal; the shims' top level must bind none of the
    # moved names except by import (plain, annotated, augmented or tuple
    # assignment, or a def).
    moved = {"PRESETS", "CELL_MIN", "CELL_MAX", "BAND_FLOOR", "BAND_MAX", "round_div"}
    moved |= {"apply_finished_size"}
    for module in (finished_size, viewer_sizing):
        assert not moved & _top_level_bindings(module), module
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
    # cut size = finished + 2 x 1/4 in seam allowance = finished + 4 e, so
    # the references' cut sizes are on the list above: 6 + 4 = 10 e
    # (1 1/4 in), 16 + 4 = 20 e (2 1/2 in) and 32 + 4 = 36 e (4 1/2 in).


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
    # The DIC asked for 502 e (62 3/4 in) wide. At the 1/4 in step, 1 1/4 in
    # (10 e) meets it exactly: border 2 x round_div(300, 24) = 2 x (312 // 24)
    # = 26, 45 x 10 + 2 x 26 = 450 + 52 = 502.
    result = size_pattern(load(FIXTURE), _typed(width=502))
    assert result.model.center.cell_size == 10
    assert result.model.size_basis.rounding_step == 2
    # Set the step to 1/2 in (4 e): 10 e is off the list (8, 12, ..., 32).
    #   8 e: border 2 x round_div(240, 24) = 2 x (252 // 24) = 20,
    #     45 x 8 + 40 = 400, short by 102
    #   12 e: 600, over by 98 -> 12 e, recorded at step 4
    monkeypatch.setattr(sizing, "SQUARE_STEP", 4)
    assert sizing.square_sizes() == (8, 12, 16, 20, 24, 28, 32)
    result = size_pattern(load(FIXTURE), _typed(width=502))
    assert result.model.center.cell_size == 12
    assert result.model.size_basis.rounding_step == 4


def test_a_pattern_step_off_whole_quarter_inches_is_refused(monkeypatch):
    # A 3 e step would offer 6, 9, ..., 30: 9 + 4 = 13 e cuts at 1 5/8 in,
    # not a whole quarter inch. Step 1 is the sprint 3 reconcile, not a
    # pattern step.
    with pytest.raises(ValueError, match="quarter inch"):
        apply_finished_size(load(FIXTURE), 600, None, step=3)
    # the public list and a chosen square refuse it too, so a picker built
    # from offered_squares never offers a square size_at refuses
    with pytest.raises(ValueError, match="quarter inch"):
        sizing.offered_squares(load(FIXTURE), 3)
    with pytest.raises(ValueError, match="quarter inch"):
        sizing.size_at(load(FIXTURE), 12, step=3)
    # The setting at 3 e, or at 1 e (which would select the sprint 3 rule,
    # borders to the eighth), is refused on the pattern path.
    for step in (3, 1):
        monkeypatch.setattr(sizing, "SQUARE_STEP", step)
        with pytest.raises(ValueError, match="quarter inch"):
            size_pattern(load(FIXTURE), _typed(600, 720))
        with pytest.raises(ValueError, match="quarter inch"):
            sizing.offered_squares(load(FIXTURE))


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
    # the input model is left as it was
    assert quilt.center.cell_size == 12


def test_sizing_never_changes_the_counts():
    # The size moves in whole blocks because no sizing call edits the counts
    # or the confirmed blocks (9 x 11 blocks of 5 x 5 squares = 45 x 55).
    blocks = ConfirmedBlocks(blocks_across=9, blocks_down=11, squares_across=5, squares_down=5)
    quilt = load(FIXTURE).model_copy(update={"confirmed_blocks": blocks})
    sized = [
        sizing.size_at(quilt, 16),
        size_pattern(quilt, _typed(688, 540)).model,
        apply_finished_size(quilt, 2000, None)[0],
    ]
    for model in sized:
        assert (model.center.cols, model.center.rows) == (45, 55)
        assert model.confirmed_blocks == blocks
        assert model.center.cells == quilt.center.cells


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
    # On the snowball grid the refusal lists only the squares that keep its
    # 1/3 leg whole: 6, 12, 18, 24 and 30 e
    with pytest.raises(ValueError, match=re.escape("[6, 12, 18, 24, 30]")):
        sizing.size_at(_snowball_grid(), 9)
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
    # With both sides set, the combined miss is the sum of the two misses,
    # |width - 688| + |height - 540|. At each square s the DIC border is
    # 2 x round_div(30 s, 24):
    #   1 in (8 e): border 2 x (252 // 24) = 20,
    #     45 x 8 + 40 = 400 and 55 x 8 + 40 = 480: 288 + 60 = 348
    #   1 1/4 in (10 e): border 2 x (312 // 24) = 26,
    #     45 x 10 + 52 = 502 and 55 x 10 + 52 = 602: 186 + 62 = 248
    #   1 1/2 in (12 e): border 30, 600 and 720: 88 + 180 = 268
    #   1 3/4 in (14 e): border 2 x (432 // 24) = 36,
    #     45 x 14 + 72 = 702 and 55 x 14 + 72 = 842: 14 + 302 = 316
    # From 8 e down both sides fall further short, and from 14 e up both
    # overshoot further, so 1 1/4 in wins: 502 x 602 e (62 3/4 x 75 1/4 in).
    result = size_pattern(load(FIXTURE), _typed(688, 540))
    assert result.model.center.cell_size == 10
    assert [band.width for band in result.model.borders] == [26]
    assert (result.basis.achieved_width, result.basis.achieved_height) == (502, 602)


def test_the_combined_miss_is_the_plain_sum():
    # The DIC asked for 400 x 720 e (50 x 90 in). Misses per square, as
    # (width miss, height miss):
    #   1 in (8 e): 400 x 480, (0, 240)
    #   1 1/4 in (10 e): 502 x 602, (102, 118)
    #   1 1/2 in (12 e): 600 x 720, (200, 0)
    #   1 3/4 in (14 e): 702 x 842, (302, 122)
    # The plain sum: 240, 220, 200, 424 -> 12 e. Other measures pick 10 e,
    # so this vector tells them apart: the largest miss (240, 118, 200, 302)
    # and the sum of squares (57600, 10404 + 13924 = 24328, 40000, ...).
    # Source: docs/SPEC.md section 6.3, the combined miss.
    result = size_pattern(load(FIXTURE), _typed(400, 720))
    assert result.model.center.cell_size == 12
    assert (result.basis.achieved_width, result.basis.achieved_height) == (600, 720)


def test_a_height_alone_is_fitted_on_the_rows():
    # Source: docs/SPEC.md section 6.3, with one side set the combined miss is
    # that side's own miss. Formula: miss = |rows x s + 2 x band - height|,
    # band = 2 x round_div(30 s, 24). Inputs: the DIC (55 rows, cell0 12 e,
    # one 30 e band), a typed height of 850 e (106 1/4 in) and no width.
    #   12 e: band 30, 55 x 12 + 60 = 720, short by 130
    #   14 e: band 2 x round_div(420, 24) = 2 x (432 // 24) = 36,
    #     55 x 14 + 72 = 770 + 72 = 842, short by 8
    #   16 e: band 2 x round_div(480, 24) = 2 x (492 // 24) = 40,
    #     55 x 16 + 80 = 880 + 80 = 960, over by 110
    # Below 12 e the height falls further short and above 16 e it overshoots
    # further. Expected: 14 e, 45 x 14 + 72 = 630 + 72 = 702 by 842.
    # Fitting 850 on the 45 columns instead would pick 16 e (800, 50 short,
    # against 902 at 18 e, 52 over), and ignoring it would tie every square
    # at 0 and take 32 e, so 14 e tells the height was read on the rows.
    result = size_pattern(load(FIXTURE), _typed(height=850))
    assert result.model.center.cell_size == 14
    assert [band.width for band in result.model.borders] == [36]
    assert (result.basis.achieved_width, result.basis.achieved_height) == (702, 842)
    assert (result.basis.requested_width, result.basis.requested_height) == (None, 850)


def test_each_band_snaps_on_its_own_not_the_band_total():
    # Source: docs/SPEC.md section 6.3, border widths snap to the nearest
    # 1/4 in, half-up, from 1/4 in to 14 in; each band is its own border.
    # Formula: band = max(2, min(112, 2 x round_div(w0 x s, 2 x cell0))).
    # Inputs: 13 columns by 10 rows, cell0 12 e, two 3 e bands, a typed
    # 172 x 136 e. Each band at s is 2 x round_div(3 s, 24):
    #   10 e: 2 x round_div(30, 24) = 2 x (42 // 24) = 2 e each, 4 in total:
    #     13 x 10 + 2 x 4 = 138 by 10 x 10 + 8 = 108, misses 34 + 28 = 62
    #   12 e: 2 x round_div(36, 24) = 2 x (48 // 24) = 4 e each, 8 in total:
    #     13 x 12 + 2 x 8 = 172 by 10 x 12 + 16 = 136, misses 0 + 0 = 0
    #   14 e: 2 x round_div(42, 24) = 2 x (54 // 24) = 4 e each, 8 in total:
    #     13 x 14 + 16 = 198 by 10 x 14 + 16 = 156, misses 26 + 20 = 46
    # Expected: 12 e, bands [4, 4], 172 x 136. Snapping the 6 e total as one
    # band, 2 x round_div(72, 24) = 2 x 3 = 6 e, would give 168 x 132.
    result = size_pattern(_two_bands(10, 13, 12, 3), _typed(172, 136))
    assert result.model.center.cell_size == 12
    assert [band.width for band in result.model.borders] == [4, 4]
    assert (result.basis.achieved_width, result.basis.achieved_height) == (172, 136)


def test_each_band_stops_at_the_cap_on_its_own():
    # Source: docs/SPEC.md section 6.3 and REBASELINE.md literal C3, each
    # border at most 14 in (BAND_MAX = 112 e). Inputs: 13 columns by 10 rows,
    # cell0 12 e, two 100 e bands, a typed width of 2000 e (250 in).
    # The width grows with the square, and at the largest, 32 e, each band
    # would scale to 2 x round_div(100 x 32, 24) = 2 x ((3200 + 12) // 24)
    # = 2 x 133 = 266 e and stops at 112 e:
    #   width 13 x 32 + 2 x (112 + 112) = 416 + 448 = 864, short of 2000
    #   height 10 x 32 + 448 = 320 + 448 = 768
    # so every square falls short and 32 e misses least. Expected: bands
    # [112, 112], 864 x 768. Capping the 200 e total as one band at 112 e
    # would give 416 + 224 = 640 wide.
    result = size_pattern(_two_bands(10, 13, 12, 100), _typed(width=2000))
    assert result.model.center.cell_size == 32
    assert [band.width for band in result.model.borders] == [112, 112]
    assert (result.basis.achieved_width, result.basis.achieved_height) == (864, 768)


def test_a_preset_records_its_size_as_requested():
    # Twin is 70 x 90 in = 560 x 720 e (PRESETS). Combined misses:
    #   1 1/4 in: 502 x 602, 58 + 118 = 176
    #   1 1/2 in: 600 x 720, 40 + 0 = 40
    #   1 3/4 in: 702 x 842, 142 + 122 = 264
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


def test_a_preset_fits_the_orientation_suggest_preset_matched():
    # The DIC's counts, square and border turned on its side: 55 columns by
    # 45 rows of 12 e in one 30 e band, 55 x 12 + 2 x 30 = 720 e wide by
    # 45 x 12 + 60 = 600 e tall.
    # Source: suggest_preset (qrep/model/finished_size.py) compares long side
    # over short side, so it pairs the quilt's long side with the preset's.
    #   quilt 720 / 600 = 1.2; Queen 108 / 90 = 1.2, a difference of 0, the
    #   only preset within 0.04 (Twin 90 / 70 = 1.286, Throw 65 / 50 = 1.3,
    #   Full 90 / 84 = 1.071, Crib 52 / 36 = 1.444, King 110 / 108 = 1.019)
    # so Queen's 108 in side lies along the 720 e width: 864 x 720 e.
    # Formula: combined miss = |W - 864| + |H - 720|, band = 2 x round_div(30 s, 24).
    #   12 e: band 30, 720 x 600, misses 144 + 120 = 264
    #   14 e: band 2 x (432 // 24) = 36, 55 x 14 + 72 = 842 by
    #     45 x 14 + 72 = 702, misses 22 + 18 = 40
    #   16 e: band 2 x (492 // 24) = 40, 55 x 16 + 80 = 960 by
    #     45 x 16 + 80 = 800, misses 96 + 80 = 176
    # Below 12 e both sides fall further short and above 16 e both overshoot
    # further. Expected: 14 e, 842 x 702. Queen as listed, 720 x 864, picks
    # 12 e instead: 0 + 264 = 264 against 122 + 162 = 284 at 14 e.
    turned = _grid_model(45, 55, 12, 30)
    assert (turned.finished_width, turned.finished_height) == (720, 600)
    assert finished_size.suggest_preset(720 / 600) == "Queen"
    result = size_pattern(turned, SizeRequest(source="preset", preset="Queen"))
    assert result.model.center.cell_size == 14
    assert (result.basis.requested_width, result.basis.requested_height) == (864, 720)
    assert (result.basis.achieved_width, result.basis.achieved_height) == (842, 702)


def test_a_preset_lies_long_side_along_an_upright_quilt():
    # The upright DIC is 600 x 720 e, taller than wide, so the preset's long
    # side runs down it (suggest_preset's long-over-short pairing).
    # Queen is listed taller than wide, 90 x 108 in = 720 x 864 e, so it
    # applies as listed. Combined misses, |W - 720| + |H - 864|:
    #   12 e: 600 x 720, 120 + 144 = 264
    #   14 e: band 2 x (432 // 24) = 36, 45 x 14 + 72 = 702 by
    #     55 x 14 + 72 = 842, 18 + 22 = 40
    #   16 e: band 40, 45 x 16 + 80 = 800 by 55 x 16 + 80 = 960, 80 + 96 = 176
    # Expected: 14 e, 702 x 842, asked as 720 x 864.
    queen = size_pattern(load(FIXTURE), SizeRequest(source="preset", preset="Queen"))
    assert queen.model.center.cell_size == 14
    assert (queen.basis.requested_width, queen.basis.requested_height) == (720, 864)
    assert (queen.basis.achieved_width, queen.basis.achieved_height) == (702, 842)
    # King is listed wider than tall, 110 x 108 in = 880 x 864 e, so on the
    # upright DIC it turns to 864 x 880 e. Combined misses, |W - 864| + |H - 880|:
    #   14 e: 702 x 842, 162 + 38 = 200
    #   16 e: 800 x 960, 64 + 80 = 144
    #   18 e: band 2 x round_div(540, 24) = 2 x (552 // 24) = 46,
    #     45 x 18 + 92 = 902 by 55 x 18 + 92 = 1082, 38 + 202 = 240
    # Expected: 16 e, 800 x 960, asked as 864 x 880. King as listed lands on
    # 16 e as well (80 + 96 = 176 against 200 at 14 e and 240 at 18 e), so the
    # asked size alone shows the orientation.
    king = size_pattern(load(FIXTURE), SizeRequest(source="preset", preset="King"))
    assert king.model.center.cell_size == 16
    assert (king.basis.requested_width, king.basis.requested_height) == (864, 880)
    assert (king.basis.achieved_width, king.basis.achieved_height) == (800, 960)


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
    #   3/4 in (6 e): border 2 x round_div(138, 18) = 2 x (147 // 18) = 16,
    #     302 x 362, combined miss 149 + 179 = 328
    #   1 in (8 e): border 2 x round_div(184, 18) = 2 x (193 // 18) = 20,
    #     45 x 8 + 40 = 400 by 55 x 8 + 40 = 480, 51 + 61 = 112
    #   1 1/4 in (10 e): border 2 x round_div(230, 18) = 2 x (239 // 18) = 26,
    #     45 x 10 + 52 = 502 by 55 x 10 + 52 = 602, 51 + 61 = 112
    #   1 1/2 in (12 e): border 2 x round_div(276, 18) = 2 x (285 // 18) = 30,
    #     600 x 720, 149 + 179 = 328
    # A two-axis tie at 112: the larger square wins -> 502 x 602 e. The read
    # recorded no confidence for its assumed resolution, which measures
    # nothing, so the estimate carries 0.0 (Source: docs/SPEC.md section 6.3,
    # "a read that recorded none gets 0.0"; section 8, a size estimated from
    # the photo is low confidence).
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
    # squares were read at confidence 0.3, so the estimate is a read's: 0.0
    # (Source: docs/SPEC.md section 6.3, only authored provenance with every
    # recorded confidence at 1.0 is hand-authored).
    data = json.loads(dumps(_read_shaped(9, 23)))
    data["center"]["cell_confidence"] = [[0.3] * 45 for _ in range(55)]
    del data["provenance"]
    result = size_pattern(loads(json.dumps(data)), SizeRequest(source="default"))
    assert result.model.size_basis.confidence == 0.0


@pytest.mark.parametrize(
    ("model", "confidence"),
    [
        (_snowball_grid(), 1.0),
        # authored provenance, but the grid stage was read at 0.5
        (_snowball_grid(stages={"grid": 0.5}), 0.0),
        # authored provenance, but the corner unit was read at 0.8
        (_snowball_grid(unit_confidence=0.8), 0.0),
    ],
    ids=["every-confidence-1", "a-stage-below-1", "a-unit-below-1"],
)
def test_only_a_model_with_every_confidence_at_1_is_hand_authored(model, confidence):
    # The snowball grid's own size: 4 x 12 + 2 x 16 = 80 e square. On its
    # list (6, 12, ..., 30), 12 e meets it exactly: border
    # 2 x round_div(16 x 12, 24) = 2 x (204 // 24) = 16, 48 + 32 = 80.
    result = size_pattern(model, SizeRequest(source="default"))
    assert (result.basis.achieved_width, result.basis.achieved_height) == (80, 80)
    assert result.model.size_basis.confidence == confidence


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
        # 86 x 67.5 in: 502 x 602, worked in test_the_sample_at_86_by_67_5
        (SizeRequest(source="typed", width=688, height=540), (502, 602)),
        # Queen 90 x 108 in = 720 x 864 e:
        #   12 e: 600 x 720, 120 + 144 = 264
        #   14 e: 45 x 14 + 2 x 36 = 702 x 842, 18 + 22 = 40
        #   16 e: 800 x 960, 80 + 96 = 176 -> 14 e, 702 x 842
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


def test_the_one_eighth_step_caps_borders():
    # 13 columns by 10 rows at 6 e with a 30 e border, asked 2000 e
    # (250 in) wide at the default step. The sprint 3 cell is
    # round_div(2000 x 6, 13 x 6 + 2 x 30) = round_div(12000, 138)
    # = (12000 + 69) // 138 = 87, clamped to 32. The border scales to
    # round_div(30 x 32, 6) = (960 + 3) // 6 = 160 e and stops at the
    # 112 e cap: 13 x 32 + 2 x 112 = 640 by 10 x 32 + 224 = 544.
    # Source: #132 criterion 3 and REBASELINE.md literal C3 (BAND_MAX 112 e).
    quilt = _grid_model(10, 13, 6, 30)
    updated, _requested, achieved = apply_finished_size(quilt, 2000, None)
    assert updated.center.cell_size == 32
    assert updated.borders[0].width == 112
    assert (achieved["width"], achieved["height"]) == (640, 544)
    assert (updated.finished_width, updated.finished_height) == (640, 544)


@pytest.mark.parametrize(
    ("step", "achieved"), [(1, (500, 600)), (2, (502, 602))], ids=["sprint-3", "pattern"]
)
def test_apply_finished_size_records_the_size_you_entered(step, achieved):
    # Sized to 75 x 90 in by a typed size, then entered again as 502 e wide.
    #   sprint 3: round_div(502 x 12, 45 x 12 + 2 x 30) = round_div(6024, 600)
    #     = 6324 // 600 = 10, border round_div(30 x 10, 12) = 306 // 12 = 25:
    #     45 x 10 + 50 = 500 by 55 x 10 + 50 = 600
    #   pattern: 10 e, border 2 x round_div(300, 24) = 2 x (312 // 24) = 26:
    #     45 x 10 + 52 = 502 by 55 x 10 + 52 = 602
    # Every caller of apply_finished_size passes a size you entered, so the
    # basis it writes is typed, at 1.0, with the step it applied, and the old
    # 600 x 720 basis is gone.
    typed = size_pattern(load(FIXTURE), _typed(600, 720)).model
    resized, _requested, _achieved = apply_finished_size(typed, 502, None, step=step)
    assert resized.center.cell_size == 10
    assert (resized.finished_width, resized.finished_height) == achieved
    assert resized.size_basis == FinishedSizeBasis(
        source="typed",
        requested_width=502,
        achieved_width=achieved[0],
        achieved_height=achieved[1],
        rounding_step=step,
        confidence=1.0,
    )


@pytest.mark.parametrize("width", [0, -8])
def test_apply_finished_size_refuses_a_size_below_one_eighth(width):
    with pytest.raises(ValueError, match="at least 1 e"):
        apply_finished_size(load(FIXTURE), width, None)
    error = _envelope_error(bridge.apply_finished_size(dumps(load(FIXTURE)), width, None))
    assert error["kind"] == "value"


def test_one_eighth_is_the_smallest_size_you_can_enter():
    # 1 e wide on the DIC: round_div(1 x 12, 45 x 12 + 60) = (12 + 300) // 600
    # = 0, clamped to 6 e; border round_div(30 x 6, 12) = (180 + 6) // 12 = 15:
    # 45 x 6 + 30 = 300 by 55 x 6 + 30 = 360, recorded as asked for 1 e.
    updated, _requested, achieved = apply_finished_size(load(FIXTURE), 1, None)
    assert (achieved["width"], achieved["height"]) == (300, 360)
    assert updated.size_basis.requested_width == 1


def test_a_size_typed_on_the_v1_paths_reaches_the_pattern_as_typed(tmp_path):
    # The crop screen's typed size (the pipeline, through bridge.reverse) and
    # the editor's size edit (bridge.apply_finished_size) both record a typed
    # basis whose achieved size is the model's own. On the DIC fixture the
    # edit reconciles 600 x 720 e to 12 e at the one-eighth step:
    # round_div(600 x 12, 45 x 12 + 60) = (7200 + 300) // 600 = 12, border
    # round_div(30 x 12, 12) = 30, so 600 x 720 exactly.
    png, _ = save_render(load(FIXTURE), tmp_path / "l0.png", level=0, seed=42)
    read = json.loads(
        bridge.reverse(str(png), json.dumps({"finished_width": 600, "finished_height": 720}))
    )["result"]["model"]
    edited = json.loads(bridge.apply_finished_size(dumps(load(FIXTURE)), 600, 720))["result"]
    assert edited["model"]["center"]["cell_size"] == 12
    assert (edited["achieved"]["width"], edited["achieved"]["height"]) == (600, 720)
    for model in (read, edited["model"]):
        basis = model["size_basis"]
        assert (basis["source"], basis["confidence"], basis["rounding_step"]) == ("typed", 1.0, 1)
        assert (basis["requested_width"], basis["requested_height"]) == (600, 720)
        quilt = loads(json.dumps(model))
        assert (basis["achieved_width"], basis["achieved_height"]) == (
            quilt.finished_width,
            quilt.finished_height,
        )
        # A later default request finds no photo estimate to label as one.
        with pytest.raises(ValueError, match="typed"):
            size_pattern(quilt, SizeRequest(source="default"))


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
    # the squares moved in steps of lcm(2, 3) = 6 e, and the basis says so
    assert result.model.size_basis.rounding_step == 6
    # the sized model loads again, corner legs and all
    assert loads(dumps(result.model)).center.cell_size == 18


def test_offered_squares_keep_every_corner_leg_whole():
    # A plain model offers the whole 1/4 in list.
    assert sizing.offered_squares(load(FIXTURE)) == sizing.square_sizes()
    # A 1/3 leg is whole on multiples of lcm(2, 3) = 6 e: 6, 12, 18, 24, 30.
    assert sizing.offered_squares(_snowball_grid()) == (6, 12, 18, 24, 30)
    # A 1/4 leg on a 12 e square (3 e) is whole on multiples of
    # lcm(2, 4) = 4 e: 8, 12, ..., 32 is (32 - 8) / 4 + 1 = 7 sizes.
    assert sizing.offered_squares(_snowball_grid(leg="1/4")) == (8, 12, 16, 20, 24, 28, 32)
    # At a 1/2 in step (4 e) a 1/3 leg needs multiples of lcm(4, 3) = 12 e.
    assert sizing.offered_squares(_snowball_grid(), 4) == (12, 24)


def test_a_corner_leg_no_offered_square_keeps_whole_is_refused():
    # A 1/17 leg on a 17 e square is 1 e. It stays whole only on multiples of
    # lcm(2, 17) = 34 e, past the 32 e clamp, so no square is offered.
    quilt = _snowball_grid(cell=17, leg="1/17")
    with pytest.raises(ValueError, match="corner leg"):
        sizing.offered_squares(quilt)
    with pytest.raises(ValueError, match="corner leg"):
        size_pattern(quilt, _typed(width=200))
    with pytest.raises(ValueError, match="corner leg"):
        size_pattern(quilt, SizeRequest(source="default"))


@pytest.mark.parametrize(
    ("model", "request_", "message"),
    [
        (_snowball_grid(cell=17, leg="1/17"), {"source": "typed", "width": 200}, "corner leg"),
        (load(FIXTURE), {"source": "preset", "preset": "Palace"}, "Palace"),
        (
            size_pattern(load(FIXTURE), _typed(600, 720)).model,
            {"source": "default"},
            "typed",
        ),
    ],
    ids=["no-square-keeps-the-leg", "unknown-preset", "default-on-a-typed-size"],
)
def test_the_bridge_refuses_a_size_it_cannot_apply_as_kind_value(model, request_, message):
    error = _envelope_error(bridge.size_pattern(dumps(model), json.dumps(request_)))
    assert error["kind"] == "value"
    assert message in error["message"]


def test_a_square_that_breaks_a_corner_leg_is_refused():
    # 16 e is on the 1/4 in list, but a 1/3 leg of it is 16/3 e
    with pytest.raises(ValueError, match="corner leg"):
        sizing.size_at(_snowball_grid(), 16)
    # The sprint 3 rule picks round_div(108 x 12, 4 x 12 + 2 x 16)
    # = round_div(1296, 80) = 1336 // 80 = 16 e: refused, never rounded.
    with pytest.raises(ValueError, match="corner leg"):
        apply_finished_size(_snowball_grid(), 108, None)
    # A width of 80 e reconciles to round_div(80 x 12, 80) = 12 e, which
    # keeps the leg at 4 e, so the one-eighth step sizes it.
    sized, _requested, achieved = apply_finished_size(_snowball_grid(), 80, None)
    assert (sized.center.cell_size, achieved["width"]) == (12, 80)


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
