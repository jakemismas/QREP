"""Construction engine tests. Every expected literal is hand-computed in the
comments next to it; expectations flow one way, hand computation -> assertion."""

import pytest
from pydantic import ValidationError

from qrep.construct import (
    STRATEGIES,
    compute_purchase_lines,
    get_strategy,
    infer_block_structure,
    plan_historical,
    plan_modern,
    plan_strip,
)
from qrep.construct.finishing import backing_plan
from qrep.model import (
    Binding,
    BorderBand,
    Fabric,
    GridRegion,
    Palette,
    Quilt,
    QuiltMetadata,
    Settings,
)
from qrep.model.fixtures import make_double_irish_chain


def with_settings(quilt: Quilt, **changes: int) -> Quilt:
    settings = quilt.settings.model_copy(update=changes)
    return quilt.model_copy(update={"settings": settings})


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
    report = compute_purchase_lines(quilt, plan_historical(quilt))
    lines = {(line.fabric_id, line.purpose): line for line in report.lines}
    # MATH.md V-TOP-04 at the defaults: U = 40 in (320 e), top margin 10
    # percent, increment 1/4 yd (72 e). Binding is its own line (F5).
    assert list(lines) == [("r", "top"), ("w", "top"), ("r", "binding"), (None, "backing")]

    # red top: 2 squares cut 2 1/2 in (20 e); per strip = 320 // 20 = 16;
    #   strips = ceil(2 / 16) = 1; length = 1 x 20 = 20 e;
    #   purchase = ceil(20 x 110 / 100) = 22 e; qy = ceil(22 / 72) = 1 -> 1/4 yd
    red = lines[("r", "top")]
    assert red.length_needed == 20
    assert red.purchase == 22
    assert red.increments == 1
    assert red.quarter_yards == 1
    assert red.yards == 0.25

    # white top: 2 squares -> 1 strip (20 e), plus the border (V-BORD-04):
    #   cut strip 8 + 4 = 12 e; sides 32 + 4 = 36 e, per = 320 // 36 = 8 ->
    #   ceil(2 / 8) = 1 strip; top and bottom 32 + 16 + 4 = 52 e,
    #   per = 320 // 52 = 6 -> 1 strip; 2 strips x 12 = 24 e.
    #   length = 20 + 24 = 44 e; purchase = ceil(44 x 110 / 100) = ceil(48.4)
    #   = 49 e; qy = ceil(49 / 72) = 1
    white = lines[("w", "top")]
    assert white.length_needed == 44
    assert white.purchase == 49
    assert white.increments == 1
    assert white.quarter_yards == 1

    # binding: T = 2 (48 + 48) + 80 = 272 e; strips = ceil(272 / (320 - 20))
    #   = 1; length = 1 x 20 = 20 e, no allowance; qy = ceil(20 / 72) = 1
    binding = lines[("r", "binding")]
    assert binding.length_needed == 20
    assert binding.purchase == 20
    assert binding.increments == 1
    assert binding.quarter_yards == 1

    # wide back: not shown (one panel)
    assert report.wide_back is None

    # backing (MATH.md V-TOP-04): Wb = Lb = 6 + 8 = 14 in (112 e) <= 42 -> one
    # piece either way; tie -> vertical; total = 112 + 36 = 148 e (the 4 1/2 in
    # one-piece allowance); qy = ceil(148/72) = ceil(2.06) = 3 -> 0.75 yd.
    # Dedicated line, id None.
    backing = lines[(None, "backing")]
    assert backing.length_needed == 112
    assert backing_plan(48, 48, quilt.settings).purchase == 148
    assert backing.quarter_yards == 3
    assert backing.yards == 0.75
    # every value is a whole number of quarter yards by construction
    assert all(line.yards * 4 == line.quarter_yards for line in report.lines)


def test_subcut_counts_hand_computed_on_checker_quilt():
    # Pinned to the old 42 in usable width; the 40 in default has its own test.
    quilt = with_settings(checker_quilt(), wof=336)
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


def test_subcut_counts_at_the_40_in_default():
    quilt = checker_quilt()
    plan = plan_strip(quilt)
    # MATH.md 3.2: segment cut width = cell 8 + seam 4 = 12;
    # per set = floor(320 / 12) = 26; sets needed = ceil(4 / 26) = 1 each
    for strip_set in plan.strip_sets:
        assert strip_set.segment_cut_width == 12
        assert strip_set.segments_per_set == 26
        assert strip_set.sets_needed == 1
    # cut ops: WOF strips 2 sets x 2 strips = 4; crosscuts 4 + 4 = 8;
    # binding: 2 x (32 + 32) + 80 = 208, ceil(208 / (320 - 20)) = 1 strip.
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
    report = compute_purchase_lines(quilt, plan_historical(quilt))
    backing = next(line for line in report.lines if line.fabric_id is None)
    # MATH.md V-BACK-09: Wb = 83 in (664 e), Lb = 98 in (784 e)
    # vertical: n(83) = ceil(82/41) = 2 exactly; 2 x 98 = 196 in (1568 e); + 9 = 205 in (1640 e)
    # horizontal: n(98) = 3; 3 x 83 = 249; + 9 = 258 -> keep vertical
    # length_needed = 1568 e; quarter yards = ceil(1640/72) = 23 -> 5.75 yd
    assert backing.length_needed == 1568
    assert backing.quarter_yards == 23
    assert backing.yards == 5.75


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


def fixture_at_40_in() -> Quilt:
    """The benchmark fixture at the 40 in usable width it moves to in A6."""
    return with_settings(make_double_irish_chain(), wof=320)


def test_fixture_historical_purchase_lines_at_40_in():
    quilt = fixture_at_40_in()
    report = compute_purchase_lines(quilt, plan_historical(quilt))
    lines = {(line.fabric_id, line.purpose): line for line in report.lines}
    # V-TOP-01 blue: 1246 squares cut 2 in (16 e); per = 320 // 16 = 20;
    #   strips = ceil(1246 / 20) = 63; length = 63 x 16 = 1008 e;
    #   purchase = ceil(1008 x 110 / 100) = ceil(1108.8) = 1109 e;
    #   qy = ceil(1109 / 72) = 16 -> 4 yd
    blue = lines[("b", "top")]
    assert (blue.length_needed, blue.purchase, blue.increments) == (1008, 1109, 16)
    # V-TOP-02 cream: 1229 squares -> ceil(1229 / 20) = 62 strips x 16 = 992 e,
    #   plus the V-BORD-01 band at U = 40: 10 strips x 34 e = 340 e;
    #   length = 1332 e; purchase = ceil(1332 x 110 / 100) = ceil(1465.2) = 1466 e;
    #   qy = ceil(1466 / 72) = 21 -> 5 1/4 yd
    cream = lines[("c", "top")]
    assert (cream.length_needed, cream.purchase, cream.increments) == (1332, 1466, 21)
    # V-BIND-01: 10 strips x 20 e = 200 e, no allowance; qy = ceil(200 / 72) = 3
    binding = lines[("b", "binding")]
    assert (binding.length_needed, binding.purchase, binding.increments) == (200, 200, 3)


def test_fixture_strip_purchase_lines_at_40_in():
    quilt = fixture_at_40_in()
    report = compute_purchase_lines(quilt, plan_strip(quilt))
    top = {line.fabric_id: line for line in report.lines if line.purpose == "top"}
    # V-TOP-03 blue: V-SET-02 64 strips x 16 e = 1024 e;
    #   purchase = ceil(1024 x 110 / 100) = ceil(1126.4) = 1127 e; qy = ceil(1127 / 72) = 16
    assert (top["b"].length_needed, top["b"].purchase, top["b"].increments) == (1024, 1127, 16)
    # V-TOP-03 cream: V-SET-02 66 strips x 16 e = 1056 e + V-BORD-01 340 e = 1396 e;
    #   purchase = ceil(1396 x 110 / 100) = ceil(1535.6) = 1536 e; qy = ceil(1536 / 72) = 22
    assert (top["c"].length_needed, top["c"].purchase, top["c"].increments) == (1396, 1536, 22)


def test_purchase_lines_round_to_the_configured_increment():
    quilt = with_settings(tiny_quilt(), purchase_increment=36)
    report = compute_purchase_lines(quilt, plan_historical(quilt))
    # MATH.md 1.4 at a 1/8 yd increment (36 e), from the V-TOP-04 purchases:
    #   red 22 e -> ceil(22 / 36) = 1; white 49 e -> ceil(49 / 36) = 2;
    #   binding 20 e -> 1; backing 148 e -> ceil(148 / 36) = 5
    assert [line.increments for line in report.lines] == [1, 2, 1, 5]
    assert report.increment == 36


def test_purchase_lines_use_the_top_margin_setting():
    quilt = with_settings(tiny_quilt(), top_margin=0)
    report = compute_purchase_lines(quilt, plan_historical(quilt))
    # F5 with p = 0: purchase = ceil(44 x 100 / 100) = 44 e for the V-TOP-04 white top
    white = next(line for line in report.lines if line.fabric_id == "w")
    assert (white.length_needed, white.purchase) == (44, 44)
    assert report.top_margin == 0


def test_waste_metric_reads_the_purchase_lines():
    quilt = tiny_quilt()
    plan = plan_historical(quilt)
    # purchased = (red top 1 + white top 1 + binding 1) increments x 72 e x U 320 e
    #           = 3 x 72 x 320 = 69120 e^2
    # cut area: red squares 2 x 20 x 20 = 800; binding 1 x 20 x 320 = 6400;
    #   white squares 800; border sides 2 x 12 x 36 = 864; top and bottom
    #   2 x 52 x 12 = 1248; total = 10112 e^2
    # waste = (69120 - 10112) / 69120 = 59008 / 69120
    assert plan.metrics.waste == pytest.approx(59008 / 69120)


def quarter_turn_quilt() -> Quilt:
    """3x3 cells of 1 in: a 2 x 1 red piece on top and a 1 x 2 red piece on the right."""
    cells = [["r", "r", "w"], ["w", "w", "r"], ["w", "w", "r"]]
    return Quilt(
        metadata=QuiltMetadata(name="turns"),
        palette=Palette(
            fabrics=[
                Fabric(id="r", name="Red", color="#cc3333"),
                Fabric(id="w", name="White", color="#ffffff"),
            ]
        ),
        center=GridRegion(rows=3, cols=3, cell_size=8, cells=cells),
        binding=Binding(fabric_id="r"),
    )


def test_rectangle_and_its_quarter_turn_share_one_cut_line():
    plan = plan_modern(quarter_turn_quilt())
    red = [p for p in plan.cut_pieces if p.component == "center" and p.fabric_id == "r"]
    # PATTERN-SPEC C-10: the 16 x 8 and 8 x 16 e pieces are one line of 2,
    # short side first: finished 8 x 16 e (1 x 2 in), cut 12 x 20 e (1 1/2 x 2 1/2 in)
    assert len(red) == 1
    assert red[0].quantity == 2
    assert (red[0].finished_width, red[0].finished_height) == (8, 16)
    assert (red[0].cut_width, red[0].cut_height) == (12, 20)
    assert red[0].label == '1" x 2", cut 1 1/2" x 2 1/2"'


def test_settings_default_to_40_in_strips_and_the_fixture_keeps_42():
    # D-05: U = 40 in = 320 e; MATH.md 1.3: p = 10 percent
    assert Settings().wof == 320
    assert Settings().top_margin == 10
    # bless policy item 4: the fixture keeps 42 in = 336 e until A6
    assert make_double_irish_chain().settings.wof == 336


def test_binding_strip_at_or_above_the_usable_width_fails_validation():
    data = tiny_quilt().model_dump()
    # F7 needs w < U: 320 e strips on 320 e fabric leave no length per strip
    data["binding"]["strip_width"] = 320
    with pytest.raises(ValidationError, match="binding strip width"):
        Quilt.model_validate(data)
    data["binding"]["strip_width"] = 319
    assert Quilt.model_validate(data).binding.strip_width == 319


def test_wide_back_must_be_wider_than_the_backing():
    with pytest.raises(ValidationError, match="wide_back_width"):
        Settings(backing_width=336, wide_back_width=336)
    assert Settings(backing_width=336, wide_back_width=337).wide_back_width == 337
