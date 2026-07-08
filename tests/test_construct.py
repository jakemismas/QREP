"""Construction engine tests. Every expected literal is hand-computed in the
comments next to it; expectations flow one way, hand computation -> assertion."""

import pytest

from qrep.construct import (
    STRATEGIES,
    compute_yardage,
    get_strategy,
    infer_block_structure,
    plan_historical,
    plan_modern,
    plan_strip,
)
from qrep.model import (
    Binding,
    BorderBand,
    Fabric,
    GridRegion,
    Palette,
    Quilt,
    QuiltMetadata,
)
from qrep.model.fixtures import make_double_irish_chain


def tiny_quilt() -> Quilt:
    """2x2 grid of 2-inch cells (16 eighths), 1-inch white border, red binding."""
    return Quilt(
        metadata=QuiltMetadata(name="tiny"),
        palette=Palette(
            fabrics=[
                Fabric(id="r", name="Red", color="#cc3333"),
                Fabric(id="w", name="White", color="#ffffff"),
            ]
        ),
        center=GridRegion(rows=2, cols=2, cell_size=16, cells=[["r", "w"], ["w", "r"]]),
        borders=[BorderBand(fabric_id="w", width=8)],
        binding=Binding(fabric_id="r"),
    )


def checker_quilt() -> Quilt:
    """4x4 grid of 1-inch cells: 2x2 blocks A=[rw/wr], B=[wr/rw], alternating.

    Rows written out: A row + B row, then B row + A row.
    """
    cells = [
        ["r", "w", "w", "r"],
        ["w", "r", "r", "w"],
        ["w", "r", "r", "w"],
        ["r", "w", "w", "r"],
    ]
    return Quilt(
        metadata=QuiltMetadata(name="checker"),
        palette=Palette(
            fabrics=[
                Fabric(id="r", name="Red", color="#cc3333"),
                Fabric(id="w", name="White", color="#ffffff"),
            ]
        ),
        center=GridRegion(rows=4, cols=4, cell_size=8, cells=cells),
        binding=Binding(fabric_id="r"),
    )


def test_yardage_hand_computed_on_tiny_quilt():
    quilt = tiny_quilt()
    report = compute_yardage(quilt, plan_historical(quilt))
    lines = {line.fabric_id: line for line in report.lines}

    # red cut area: 2 center squares cut 20x20 = 800, plus binding:
    #   finished top = 2x16 + 2x8 = 48 square; perimeter = 4x48 = 192;
    #   binding length = 192 + 80 = 272; strips = ceil(272/336) = 1 WOF strip
    #   at 20 x 336 = 6720. Total red = 800 + 6720 = 7520.
    # length = ceil(7520/336) = 23 eighths; quarter yards = ceil(23/72) = 1.
    assert lines["r"].length_needed == 23
    assert lines["r"].quarter_yards == 1
    assert lines["r"].yards == 0.25

    # white cut area: 2 center squares cut 20x20 = 800; border sides
    #   2 x (12 x 36) = 864; border top/bottom 2 x (52 x 12) = 1248.
    #   Total white = 800 + 864 + 1248 = 2912.
    # length = ceil(2912/336) = 9; quarter yards = ceil(9/72) = 1.
    assert lines["w"].length_needed == 9
    assert lines["w"].quarter_yards == 1

    # backing: panels = ceil((48+64)/336) = 1; length = 48 + 64 = 112;
    # quarter yards = ceil(112/72) = 2 -> 0.5 yd. Dedicated line, id None.
    backing = lines[None]
    assert backing.length_needed == 112
    assert backing.quarter_yards == 2
    assert backing.yards == 0.5
    # every value is a whole number of quarter yards by construction
    assert all(line.yards * 4 == line.quarter_yards for line in report.lines)


def test_subcut_counts_hand_computed_on_checker_quilt():
    quilt = checker_quilt()
    plan = plan_strip(quilt)

    # block structure: p=2, types A and B, 2 instances each
    structure = infer_block_structure(quilt.center.cells)
    assert structure is not None and structure.size == 2
    assert structure.counts == [2, 2]

    # distinct signatures: (r,w) from A row 0 and (w,r) from A row 1; B rows
    # reuse them. needed(r,w) = A row0 x2 + B row1 x2 = 4; needed(w,r) = 4.
    assert len(plan.strip_sets) == 2
    by_id = {s.id: s for s in plan.strip_sets}
    assert by_id["SS1"].sequence == ["r", "w"]
    assert by_id["SS2"].sequence == ["w", "r"]
    assert by_id["SS1"].segments_needed == 4
    assert by_id["SS2"].segments_needed == 4

    # segment cut width = cell 8 + seam 4 = 12; per set = floor(336/12) = 28;
    # sets needed = ceil(4/28) = 1 per signature
    assert by_id["SS1"].segment_cut_width == 12
    assert by_id["SS1"].segments_per_set == 28
    assert by_id["SS1"].sets_needed == 1
    assert by_id["SS2"].sets_needed == 1

    # cut ops: WOF strips 2 sets x 2 strips = 4; crosscuts 4 + 4 = 8;
    # binding: perimeter 2x(32+32) = 128, +80 = 208, ceil(208/336) = 1 strip.
    # total = 4 + 8 + 1 = 13
    assert plan.metrics.cut_count == 13


def test_fixture_strip_sets_match_design_doc():
    plan = plan_strip(make_double_irish_chain())
    # five distinct sets: A rows bbcbb, bbbbb, cbbbc; B rows bcccb, ccccc.
    # needed: 50 A blocks -> bbcbb x2 = 100, bbbbb x2 = 100, cbbbc x1 = 50;
    #         49 B blocks -> bcccb x2 = 98, ccccc x3 = 147.
    # per set = floor(336/16) = 21; sets = ceil(needed/21) = 5, 5, 3, 5, 7.
    assert len(plan.strip_sets) >= 2  # acceptance floor
    assert len(plan.strip_sets) == 5
    got = {tuple(s.sequence): (s.segments_needed, s.segments_per_set, s.sets_needed)
           for s in plan.strip_sets}
    assert got[("b", "b", "c", "b", "b")] == (100, 21, 5)
    assert got[("b", "b", "b", "b", "b")] == (100, 21, 5)
    assert got[("c", "b", "b", "b", "c")] == (50, 21, 3)
    assert got[("b", "c", "c", "c", "b")] == (98, 21, 5)
    assert got[("c", "c", "c", "c", "c")] == (147, 21, 7)
    # 25 physical sets total
    assert plan.metrics.strip_set_count == 25


def test_fixture_strip_cut_ops_below_historical():
    quilt = make_double_irish_chain()
    historical = plan_historical(quilt)
    strip = plan_strip(quilt)
    # historical: 2475 squares + 4 border pieces + 9 binding strips = 2488
    assert historical.metrics.cut_count == 2488
    # strip: 25 sets x 5 strips = 125, + 495 crosscuts (100+100+50+98+147),
    # + 4 border + 9 binding = 633
    assert strip.metrics.cut_count == 633
    assert strip.metrics.cut_count < historical.metrics.cut_count


def test_fixture_modern_piece_count_below_historical():
    quilt = make_double_irish_chain()
    historical = plan_historical(quilt)
    modern = plan_modern(quilt)
    # historical top pieces: 2475 cells + 4 border = 2479
    assert historical.metrics.piece_count == 2479
    assert modern.metrics.piece_count < historical.metrics.piece_count


@pytest.mark.parametrize("strategy", ["historical", "strip", "modern"])
def test_finished_area_reconciles_exactly(strategy):
    quilt = make_double_irish_chain()
    plan = STRATEGIES[strategy](quilt)
    # independent recomputation: center 45x55 cells x 12x12 = 356400;
    # border sides 2x(30x660) = 39600, top/bottom 2x(600x30) = 36000;
    # total = 432000 = 600 x 720 exactly
    center = 45 * 55 * 12 * 12
    border = 2 * (30 * 660) + 2 * (600 * 30)
    assert center + border == 432000
    assert quilt.finished_width * quilt.finished_height == 432000
    assert plan.top_finished_area() == 432000


@pytest.mark.parametrize("strategy", ["historical", "strip", "modern"])
def test_determinism_same_strategy_twice(strategy):
    quilt = make_double_irish_chain()
    first = STRATEGIES[strategy](quilt)
    second = STRATEGIES[strategy](quilt)
    assert first.model_dump_json() == second.model_dump_json()


@pytest.mark.parametrize("name", ["fpp", "epp", "hand", "longarm"])
def test_stubs_raise_not_implemented(name):
    with pytest.raises(NotImplementedError, match="not implemented in v1"):
        STRATEGIES[name](make_double_irish_chain())


def test_get_strategy_unknown_name():
    with pytest.raises(KeyError, match="unknown strategy"):
        get_strategy("quantum")


def test_fixture_backing_line():
    quilt = make_double_irish_chain()
    report = compute_yardage(quilt, plan_historical(quilt))
    backing = next(line for line in report.lines if line.fabric_id is None)
    # panels = ceil((600+64)/336) = 2; length = 2 x (720+64) = 1568 eighths
    # = 196 inches; quarter yards = ceil(1568/72) = 22 -> 5.5 yd
    assert backing.length_needed == 1568
    assert backing.quarter_yards == 22
    assert backing.yards == 5.5


def test_metrics_carry_heuristic_label_and_zero_bias():
    plan = plan_historical(make_double_irish_chain())
    assert plan.metrics.heuristic_label == "rough heuristic"
    assert plan.metrics.bias_percent == 0.0
    assert plan.metrics.strip_set_count == 0


def test_assembly_is_hierarchical_block_level():
    plan = plan_historical(make_double_irish_chain())
    # 2 block-piecing + 11 row joins + 1 join-rows + 1 border + 2 binding = 17
    assert len(plan.assembly) == 17
    numbers = [step.number for step in plan.assembly]
    assert numbers == list(range(1, len(numbers) + 1))
    strip_plan = plan_strip(make_double_irish_chain())
    # + 5 strip sets + 1 crosscut + 2 block-assembly replaces 2 block-piecing
    # = 5 + 1 + 2 + 11 + 1 + 1 + 2 = 23 (roughly 25 per the design doc)
    assert len(strip_plan.assembly) == 23
