"""Confidence and provenance of the confirmed read (B2b, criterion S7-6).

Every value the read derives from the photo carries a confidence in [0, 1],
every input you confirmed is recorded at 1.0, and every knob the read turns
is provisional, with its source, until D5 measures it (plan section 5.B),
except the three literals REBASELINE.md keeps frozen.
"""

import json
from pathlib import Path

import cv2
import pytest

from qrep import bridge
from qrep.model import STAGES, load
from qrep.render import save_render
from qrep.vision.read import knobs


def test_every_knob_is_provisional_with_a_source():
    # Plan B2b: the L weight, P, the inset, the k range and the vote threshold
    # sit in knobs.py with their sources, and this ticket freezes none of
    # them. The three literals REBASELINE.md keeps stay frozen: B5
    # (VOTE_MIN_COPIES), B8 (SQUARE_MIN) and B9 (SQUARE_MAX); every other
    # knob is provisional.
    named = {"L_WEIGHT", "P", "INSET", "K_MIN", "K_MAX", "VOTE_THRESHOLD"}
    kept = {"VOTE_MIN_COPIES", "SQUARE_MIN", "SQUARE_MAX"}
    assert named <= set(knobs.KNOBS)
    frozen = {name for name, knob in knobs.KNOBS.items() if knob.status == "frozen"}
    assert frozen == kept
    for name, knob in knobs.KNOBS.items():
        if name not in kept:
            assert knob.status == "provisional", name
        assert knob.source.strip(), name
        assert getattr(knobs, name) == knob.value, name
    for name, literal in (("VOTE_MIN_COPIES", "B5"), ("SQUARE_MIN", "B8"), ("SQUARE_MAX", "B9")):
        assert f"literal {literal}" in knobs.KNOBS[name].source, name


def test_knob_values_match_their_sources():
    # Source: plan sections 2.1 (L*0.5, Jake's default) and 5.B; B2a's P = 32
    # and inset 0.2 (plan B2a); the 2 to 12 fabric range (SPEC.md section
    # 12.1); REBASELINE.md literal B5 keeps 3 copies; the 3/4 in and 4 in
    # square bounds are literals B8 and B9 (6 and 32 eighths). The vote's
    # threshold 0.8 is the old vote's VOTE_HIGH_MARGIN (qrep/vision/repeats.py),
    # and 0.8, 0.75 and 0.5 are the values the hand computations in
    # tests/test_read_vote.py use. The light cap 2.0 is the ruling in #137
    # comment 6149208104, and 10 shading rounds the count at which the 6-band
    # ramp's light passes that cap on every seed (knobs.SHADING_ROUNDS).
    expected = {
        "L_WEIGHT": 0.5,
        "P": 32,
        "INSET": 0.2,
        "K_MIN": 2,
        "K_MAX": 12,
        "VOTE_MIN_COPIES": 3,
        "SQUARE_MIN": 6,
        "SQUARE_MAX": 32,
        "SIZE_STEP": 2,
        "VOTE_THRESHOLD": 0.8,
        "TYPE_AGREEMENT": 0.75,
        "ATTACH_AGREEMENT": 0.5,
        "LIGHT_MAX_RATIO": 2.0,
        "SHADING_ROUNDS": 10,
    }
    assert {name: knobs.KNOBS[name].value for name in expected} == expected


# The read's result: the L0 to L2 renders of the fixture read through the
# bridge with their sidecar outer edge, one cream band of 30 / 12 = 2.5
# squares and the fixture's 9 x 5 by 11 x 5 counts (tests/test_bridge.py).
FIXTURE = Path(__file__).parent / "fixtures" / "double_irish_chain.json"
CORNER_NAMES = ("top_left", "top_right", "bottom_right", "bottom_left")
COUNTS = {
    "blocks_across": 9,
    "blocks_down": 11,
    "squares_per_block_across": 5,
    "squares_per_block_down": 5,
}
# Darkest first: chain blue #9db8d9 sorts before cream #f2e8d5.
TO_FIXTURE = {"f0": "b", "f1": "c"}
CV_STAGES = ("palette", "cells", "repeat")
USER_STAGES = ("rectify", "grid", "border")


def _request(png, corners, **overrides) -> str:
    request = {
        "token": str(png),
        "frame": {
            "kind": "outer_edge",
            "corners": {n: {"x": x, "y": y} for n, (x, y) in zip(CORNER_NAMES, corners)},
            "bands": [{"width_squares": 2.5}],
        },
        "crop_offset": {"x": 0, "y": 0},
        "counts": COUNTS,
    }
    return json.dumps({**request, **overrides})


def _read(png, corners, **overrides) -> dict:
    envelope = json.loads(bridge.read_confirmed(_request(png, corners, **overrides)))
    assert envelope["ok"] is True, envelope
    result = envelope["result"]
    assert result["outcome"] == "read"
    return result


@pytest.fixture(scope="module")
def renders(tmp_path_factory):
    folder = tmp_path_factory.mktemp("renders")
    out = {}
    for level in (0, 2):
        png, sidecar = save_render(load(FIXTURE), folder / f"l{level}.png", level=level, seed=42)
        out[level] = (png, json.loads(Path(sidecar).read_text(encoding="utf-8"))["corners"])
    return out


def _cv_confidences(result: dict) -> list[float]:
    """Every confidence the read attaches to a value it took from the photo."""
    model, details = result["model"], result["details"]
    stages = model["provenance"]["stage_confidence"]
    values = [stages[stage] for stage in CV_STAGES]
    values += [v for row in model["center"]["cell_confidence"] for v in row]
    values += [model["size_basis"]["confidence"]]
    values += [f["confidence"] for f in details["fabrics"]]
    values += [s["confidence"] for s in details["strips"]]
    values += [c["confidence"] for c in details["vote_changes"]]
    values += [b["confidence"] for b in details["repeat_breaks"]]
    if details["fabric_count"]["source"] == "suggestion":
        values.append(details["fabric_count"]["confidence"])
    return values


@pytest.mark.parametrize("level", [0, 2])
def test_every_cv_value_of_a_read_carries_a_confidence(renders, level):
    # Criterion S7-6 replacement: palette entries, square labels, strip
    # labels, vote changes and the suggested fabric count each carry a
    # confidence in [0, 1]. The fixture has 55 x 45 = 2475 squares, 2 fabrics
    # and one band of 4 sides, so the list cannot be short.
    result = _read(*renders[level])
    values = _cv_confidences(result)
    assert len(values) >= 3 + 2475 + 1 + 2 + 4 + 1
    assert all(0.0 <= v <= 1.0 for v in values)
    assert len(result["details"]["fabrics"]) == 2
    # The default size estimate is a guess, never certain (#207).
    assert result["model"]["size_basis"]["confidence"] < 1.0


@pytest.mark.parametrize("level", [0, 2])
def test_confirmed_inputs_are_recorded_at_one(renders, level):
    # Criterion S7-6 replacement: your corners, counts and border bands are
    # the rectify, grid and border stages at 1.0, and the confirmed block
    # structure records 1.0.
    result = _read(*renders[level])
    stages = result["model"]["provenance"]["stage_confidence"]
    assert {stage: stages[stage] for stage in USER_STAGES} == dict.fromkeys(USER_STAGES, 1.0)
    assert set(stages) == set(STAGES)
    assert result["model"]["confirmed_blocks"]["confidence"] == 1.0
    assert result["details"]["corners_source"] == "user"


def test_a_fabric_count_you_set_is_recorded_at_one(renders):
    # A count you set is a user fact (SPEC.md section 4): source user, 1.0.
    result = _read(*renders[0], fabric_count=2)
    assert result["details"]["fabric_count"] == {"value": 2, "source": "user", "confidence": 1.0}


def test_minimum_stage_confidence_is_lower_on_l2_than_l0(renders):
    # Criterion S7-6 replacement: every stage stays in (0, 1], and the
    # minimum is strictly lower on L2 (noise, blur, shading) than on L0.
    minimum = {}
    for level in (0, 2):
        stages = _read(*renders[level])["model"]["provenance"]["stage_confidence"]
        assert all(0.0 < v <= 1.0 for v in stages.values())
        minimum[level] = min(stages.values())
    assert minimum[2] < minimum[0]


def _paint(image, row: int, col: int, bgr) -> None:
    # Field square (row, col) of the L0 render: the outer edge starts 72 px in
    # and the band is 2.5 squares of 15 px, so the square's center is at
    # 72 + (2.5 + col + 0.5) x 15 = 117 + 15 col across and 117 + 15 row down.
    # 11 px about the center cover the sampled inner 60 percent (9 of 15 px).
    x, y = 117 + 15 * col, 117 + 15 * row
    image[y - 5 : y + 6, x - 5 : x + 6] = bgr


def test_vote_changes_and_repeat_breaks_carry_confidences(renders, tmp_path):
    # Two squares of block (0, 0), whose type (the checkerboard's even
    # blocks) has 50 copies (tests/test_read_vote.py), are painted with the
    # wrong fabric. (0, 0) gets a 70/30 sRGB blend of the wrong and the right
    # fabric, about 0.3 of the way from the wrong one, so it reads the wrong
    # fabric at a margin (d2 - d1) / d2 of about 0.6, well under the 0.8 vote
    # threshold: the vote changes it to the type majority. (1, 1) gets the
    # wrong fabric exactly, read at 1.0, so it keeps its read as a repeat
    # break.
    quilt = load(FIXTURE)
    colors = {f.id: f.color for f in quilt.palette.fabrics}

    def bgr(hex_color):
        return [int(hex_color[i : i + 2], 16) for i in (5, 3, 1)]

    png, corners = renders[0]
    image = cv2.imread(str(png), cv2.IMREAD_COLOR)
    wrong = {}
    for row, col in ((0, 0), (1, 1)):
        right = quilt.center.cells[row][col]
        wrong[row, col] = next(f for f in colors if f != right)
    blend = [
        round(0.7 * w + 0.3 * r)
        for w, r in zip(bgr(colors[wrong[0, 0]]), bgr(colors[quilt.center.cells[0][0]]))
    ]
    _paint(image, 0, 0, blend)
    _paint(image, 1, 1, bgr(colors[wrong[1, 1]]))
    painted = tmp_path / "painted.png"
    cv2.imwrite(str(painted), image)

    # Every square of a flat render is exact, so the lone blend is a cluster
    # of its own with no spread, and the suggestion would give it a third
    # fabric. You settle the count on Colors, so the read takes your 2.
    result = _read(painted, corners, fabric_count=2)
    to_read = {fixture: read for read, fixture in TO_FIXTURE.items()}
    details = result["details"]
    changes = [(c["row"], c["col"], c["read"], c["voted"]) for c in details["vote_changes"]]
    assert changes == [(0, 0, to_read[wrong[0, 0]], to_read[quilt.center.cells[0][0]])]
    # The vote's confidence is the majority's share: 49 agreeing copies at 1.0
    # over 49 + c, with the painted square's own c below 0.8, so it lies in
    # (49 / 49.8, 1] = (0.9839..., 1].
    assert 49 / 49.8 < details["vote_changes"][0]["confidence"] <= 1.0
    breaks = [(b["row"], b["col"], b["read"], b["majority"]) for b in details["repeat_breaks"]]
    assert breaks == [(1, 1, to_read[wrong[1, 1]], to_read[quilt.center.cells[1][1]])]
    assert details["repeat_breaks"][0]["confidence"] >= 0.8
    # The vote fixed (0, 0) and kept (1, 1), so the model differs from the
    # fixture at (1, 1) alone.
    read = [[TO_FIXTURE[f] for f in row] for row in result["model"]["center"]["cells"]]
    diff = [
        (r, c)
        for r, row in enumerate(read)
        for c, value in enumerate(row)
        if value != quilt.center.cells[r][c]
    ]
    assert diff == [(1, 1)]
    assert all(0.0 <= v <= 1.0 for v in _cv_confidences(result))
