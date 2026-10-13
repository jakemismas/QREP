"""Simulation, corpus, degradation and harness tests for the eval (plan D4a).

Expected values are worked by hand in the comments from the plan's text, the
app's resolution caps (web/src/model/downscale.ts) and each degradation's
stated parameters, never copied from a run.
"""

import csv
import hashlib
import json
import math
import random
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

import run_eval
from qrep.contract import Counts
from qrep_eval import annotation as an
from qrep_eval import corpus, degrade, harness, readers, report, simulate

SQUARE = [(100.0, 100.0), (300.0, 100.0), (300.0, 200.0), (100.0, 200.0)]


def test_jitter_moves_every_corner_by_exactly_the_radius_and_repeats_under_a_seed():
    # Each corner moves r px in its own random direction: |delta| = r for r = 4.
    moved = simulate.jitter(SQUARE, 4.0, random.Random("seed-1"), bounds=(1000, 1000))
    for (x0, y0), (x1, y1) in zip(SQUARE, moved):
        assert math.hypot(x1 - x0, y1 - y0) == pytest.approx(4.0)
    # Each corner draws its own direction, so the four displacement vectors are not one
    # shared shift: at least two differ.
    vectors = {(round(x1 - x0, 9), round(y1 - y0, 9)) for (x0, y0), (x1, y1) in zip(SQUARE, moved)}
    assert len(vectors) >= 2
    # The same seed gives the same corners; another seed gives others.
    assert simulate.jitter(SQUARE, 4.0, random.Random("seed-1"), bounds=(1000, 1000)) == moved
    assert simulate.jitter(SQUARE, 4.0, random.Random("seed-2"), bounds=(1000, 1000)) != moved
    # r = 0 is the annotation itself.
    assert simulate.jitter(SQUARE, 0.0, random.Random("seed-1"), bounds=(1000, 1000)) == SQUARE


def test_jitter_keeps_corners_on_the_image():
    # A tap cannot land off the photo: a corner at (0, 0) moved 8 px stays in [0, w] x [0, h].
    edge = [(0.0, 0.0), (50.0, 0.0), (50.0, 40.0), (0.0, 40.0)]
    for seed in range(20):
        moved = simulate.jitter(edge, 8.0, random.Random(seed), bounds=(50, 40))
        assert all(0.0 <= x <= 50.0 and 0.0 <= y <= 40.0 for x, y in moved)


def test_corner_trials_record_the_displacement_after_clamping():
    # Corner 0 sits at (0, 0): clamping can shorten its 8 px move to anything in [0, 8].
    # Corners 1 to 3 are at least 20 px from every edge of the 200 x 200 image, more than
    # 8, so no clamp touches them: exactly 8.
    corners = [(0.0, 0.0), (100.0, 20.0), (100.0, 80.0), (20.0, 80.0)]
    trials = simulate.corner_trials(corners, (0, 8), 10, "k", bounds=(200, 200))
    assert trials[0].moved_px == (0.0, 0.0, 0.0, 0.0)
    for trial in trials[1:]:
        assert 0.0 <= trial.moved_px[0] <= 8.0 + 1e-9
        assert trial.moved_px[1:] == pytest.approx((8.0, 8.0, 8.0))


def test_corner_trials_run_one_trial_at_zero_and_n_per_other_radius():
    # Radii 0, 2, 4, 6, 8 with 3 trials: 1 + 4 x 3 = 13 trials.
    trials = simulate.corner_trials(SQUARE, simulate.RADII_PX, 3, "photo|full", bounds=(1000, 1000))
    assert len(trials) == 13
    assert [t.radius_px for t in trials].count(0) == 1
    assert all(t.picker == "Works with these" for t in trials)


def test_square_pitch_and_jitter_as_a_fraction_of_a_square():
    # Outer edge 240 x 180 px; 2 blocks x 5 squares across = 10 columns, 1 block x 7
    # squares down = 7 rows; one band 1 square wide on every side.
    # Across: 10 + 2 x 1 = 12 squares in 240 px -> 20 px. Down: 7 + 2 = 9 in 180 -> 20 px.
    # Pitch = mean(20, 20) = 20 px; a 4 px jitter is 4 / 20 = 0.2 of a square.
    edge = [(0.0, 0.0), (240.0, 0.0), (240.0, 180.0), (0.0, 180.0)]
    counts = Counts(blocks_across=2, blocks_down=1, squares_per_block_across=5, squares_per_block_down=7)
    pitch = simulate.square_pitch(edge, counts, [1.0])
    assert pitch == pytest.approx(20.0)
    assert simulate.radius_in_squares(4.0, pitch) == pytest.approx(0.2)
    # Unequal axes, so an across/down swap would show: the same counts on a 240 x 270 px
    # edge. Across: 240 / 12 = 20 px. Down: 270 / 9 = 30 px. Pitch = (20 + 30) / 2 = 25 px;
    # 4 px is 4 / 25 = 0.16 of a square. Swapped, it would be (240 / 9 + 270 / 12) / 2
    # = (26.667 + 22.5) / 2 = 24.583.
    tall = [(0.0, 0.0), (240.0, 0.0), (240.0, 270.0), (0.0, 270.0)]
    pitch = simulate.square_pitch(tall, counts, [1.0])
    assert pitch == pytest.approx(25.0)
    assert simulate.radius_in_squares(4.0, pitch) == pytest.approx(0.16)


def test_miscount_variants_by_hand():
    # Plan 7.2, G3: one square and one block off on either axis, half and double.
    # True counts: 2 blocks across, 3 down, 4 x 4 squares per block.
    true = Counts(blocks_across=2, blocks_down=3, squares_per_block_across=4, squares_per_block_down=4)
    variants, skipped = simulate.miscount_variants(true)
    got = {kind: (c.blocks_across, c.blocks_down, c.squares_per_block_across, c.squares_per_block_down)
           for kind, c in variants}
    assert got == {
        "square +1 across": (2, 3, 5, 4),
        "square -1 across": (2, 3, 3, 4),
        "square +1 down": (2, 3, 4, 5),
        "square -1 down": (2, 3, 4, 3),
        "block +1 across": (3, 3, 4, 4),
        "block -1 across": (1, 3, 4, 4),
        "block +1 down": (2, 4, 4, 4),
        "block -1 down": (2, 2, 4, 4),
        # Half: 4 squares per block is even on both axes, so 4 / 2 = 2 each way.
        "half": (2, 3, 2, 2),
        # Double: 4 x 2 = 8 squares per block each way.
        "double": (2, 3, 8, 8),
    }
    assert skipped == []


def test_miscount_variants_skip_what_no_count_can_express():
    # One block of 13 x 11 squares: a block less leaves 0 blocks (skipped on both axes);
    # 13 and 11 are odd and 1 block is odd, so no whole half exists (skipped).
    true = Counts(blocks_across=1, blocks_down=1, squares_per_block_across=13, squares_per_block_down=11)
    variants, skipped = simulate.miscount_variants(true)
    assert {kind for kind, _ in skipped} == {"block -1 across", "block -1 down", "half"}
    assert len(variants) == 10 - 3
    # Half falls back to the blocks when the squares per block are odd: 2 x 2 blocks of
    # 5 x 4 squares -> across 5 is odd, 2 blocks halve to 1; down 4 halves to 2.
    variants, _ = simulate.miscount_variants(
        Counts(blocks_across=2, blocks_down=2, squares_per_block_across=5, squares_per_block_down=4))
    half = dict(variants)["half"]
    assert (half.blocks_across, half.squares_per_block_across) == (1, 5)
    assert (half.blocks_down, half.squares_per_block_down) == (2, 2)


@pytest.mark.parametrize(
    ("size", "cap", "expected"),
    [
        # web/src/model/downscale.test.ts: 4000 x 3000 -> 2000 x 1500 (3000 * 2000 / 4000).
        ((4000, 3000), 2000, (2000, 1500)),
        # 4000 x 3000 -> 1400 x 1050 (3000 * 1400 / 4000).
        ((4000, 3000), 1400, (1400, 1050)),
        ((3000, 4000), 1400, (1050, 1400)),
        # Within the cap: unchanged, never upscaled.
        ((1400, 900), 1400, (1400, 900)),
        # 2999 * 1400 / 3999 = 4198600 / 3999 = 1049.91 -> 1050.
        ((3999, 2999), 1400, (1400, 1050)),
        # JavaScript's Math.round rounds a half up: 1001 * 2000 / 4000 = 500.5 -> 501.
        ((4000, 1001), 2000, (2000, 501)),
        # As fetched: no cap.
        ((4000, 3000), None, (4000, 3000)),
    ],
)
def test_cap_size_matches_the_apps_target_size(size, cap, expected):
    assert corpus.cap_size(*size, cap) == expected


def test_split_follows_the_holdout_rule():
    # corpus/README.md: first 8 hex digits as an integer, divisible by 3 -> holdout.
    # 0x00000003 = 3, 3 % 3 = 0 -> holdout; 0x00000001 = 1 -> dev.
    assert corpus.split_of("00000003" + "0" * 56) == "holdout"
    assert corpus.split_of("00000001" + "0" * 56) == "dev"


def _annotation(provenance: str, *, frame=True, fabrics=(), refusal=None, built=None) -> an.Annotation:
    """fabrics is (provenance, count) pairs; refusal and built name the provenance of a
    refusal class and of the construction class when it differs from provenance."""
    claim = {"provenance": provenance}
    doc = {
        "schema_version": 1,
        "photo": "private/cache/x.jpg",
        "sha256": "1" * 64,
        "canvas": [400, 300],
        "construction_class": [{"provenance": built or provenance, "value": "squares"}],
    }
    if fabrics:
        doc["fabrics"] = [{"provenance": code, "value": {"count": n}} for code, n in fabrics]
    if refusal:
        doc["construction_class"] = [{"provenance": built or provenance, "value": "out_of_scope"}]
        doc["refusal_class"] = [{"provenance": refusal, "value": "on_point"}]
    if frame:
        doc["frame"] = [{**claim, "value": {"outer_edge": {
            "kind": "outer_edge", "bands": [],
            "corners": {"top_left": {"x": 10.0, "y": 10.0}, "top_right": {"x": 390.0, "y": 10.0},
                        "bottom_right": {"x": 390.0, "y": 290.0}, "bottom_left": {"x": 10.0, "y": 290.0}}}}}]
        doc["counts"] = [{**claim, "value": {"blocks_across": 1, "blocks_down": 1,
                                             "squares_per_block_across": 4, "squares_per_block_down": 3}}]
    # JSON mode, as annotation.load reads the page's output.
    return an.Annotation.model_validate_json(json.dumps(doc))


def test_only_gate_truth_makes_a_gate_row():
    # Plan 5.D: corners, counts and bands count as truth only when verified-jake.
    assert corpus.truth_view(_annotation("verified-jake")).label == "gate"
    for code in ("proposed-a", "proposed-b", "adjudicated", "hand-authored"):
        view = corpus.truth_view(_annotation(code))
        assert view.label == "provisional", code
    # A proposal is used when no truth exists, and says which code it came from.
    view = corpus.truth_view(_annotation("proposed-b"))
    assert view.provenance["frame"] == "proposed-b"
    # No frame at all: nothing to confirm, so no corners and no counts.
    bare = corpus.truth_view(_annotation("proposed-a", frame=False))
    assert bare.corners is None and bare.counts is None


def test_a_proposed_fabric_count_keeps_a_photo_provisional():
    # Plan 5.D: verified frame, counts and class, but the fabric count only proposed-a:
    # a proposal would grade k, so the row is provisional.
    view = corpus.truth_view(_annotation("verified-jake", fabrics=[("proposed-a", 3)]))
    assert view.provenance["fabrics"] == "proposed-a"
    assert view.label_for("A") == "provisional" and view.label == "provisional"
    # A hand-authored count is square truth (an.TRUTH), and it wins over the proposal.
    view = corpus.truth_view(_annotation("verified-jake", fabrics=[("proposed-a", 3), ("hand-authored", 4)]))
    assert (view.fabric_count, view.provenance["fabrics"]) == (4, "hand-authored")
    assert view.label_for("A") == "gate"


def test_a_refusal_photo_is_gated_on_its_class():
    # Tier R: a verified-jake refusal class is gate truth even with a proposed
    # construction class and no frame; tier A on the same annotation is provisional.
    view = corpus.truth_view(_annotation("proposed-a", frame=False, refusal="verified-jake"))
    assert view.provenance["refusal_class"] == "verified-jake"
    assert view.label_for("R") == "gate"
    assert view.label_for("A") == "provisional"
    # Both classes proposed: provisional.
    view = corpus.truth_view(_annotation("proposed-a", frame=False, refusal="proposed-b"))
    assert view.label_for("R") == "provisional"


def test_device_class_comes_from_the_capture():
    assert corpus.DEVICE_CLASS["museum_scan"] == "museum scan"
    assert corpus.DEVICE_CLASS["direct_screenshot"] == "screenshot"
    # A nested screenshot never counts as a phone capture (approaches-25).
    assert corpus.DEVICE_CLASS["nested_screenshot"] == "screenshot"
    assert corpus.DEVICE_CLASS["camera"] == "phone camera"


def test_grayscale_keeps_only_value():
    # BGR (10, 100, 200): Y = 0.299 x 200 + 0.587 x 100 + 0.114 x 10 = 59.8 + 58.7 + 1.14
    # = 119.64 -> 120 on all three channels (within 1 of 119.64).
    image = np.full((4, 4, 3), (10, 100, 200), dtype=np.uint8)
    out = degrade.grayscale(image)
    assert out.shape == image.shape
    assert (out[..., 0] == out[..., 1]).all() and (out[..., 1] == out[..., 2]).all()
    assert abs(int(out[0, 0, 0]) - 119.64) <= 1


def test_lighting_gradient_dims_left_to_right():
    # Factor 1.0 at column 0 falling linearly to 0.55 at the last column (width 11):
    # column 0 -> 200; column 10 -> 200 x 0.55 = 110; column 5 -> 1 - 0.45 x 5/10 = 0.775
    # -> 155.
    out = degrade.lighting_gradient(np.full((3, 11, 3), 200, dtype=np.uint8))
    assert out[1, 0, 0] == 200 and out[1, 10, 0] == 110 and out[1, 5, 0] == 155


def test_low_resolution_jpeg_shrinks_to_600_px():
    # 1200 x 900 -> longest side 600: 600 x 450, a scale of 600 / 1200 = 0.5.
    out, scale = degrade.low_res_jpeg(np.full((900, 1200, 3), 128, dtype=np.uint8))
    assert out.shape[:2] == (450, 600)
    assert scale == pytest.approx(0.5)
    # A 1 px checkerboard of 0 and 255, 64 x 64: within 600 px, so no resize (scale 1),
    # and only the JPEG at quality 40 acts. Its 8 x 8 blocks hold the highest frequency
    # there is, which quality 40 quantizes coarsely: the pixels come back changed.
    board = np.indices((64, 64)).sum(axis=0) % 2 * 255
    board = np.repeat(board[..., None], 3, axis=2).astype(np.uint8)
    out, scale = degrade.low_res_jpeg(board)
    assert scale == 1.0 and out.shape == board.shape
    assert (out != board).any()


def test_blur_leaves_a_flat_image_flat():
    # A Gaussian blur of a constant image is the constant: 77 everywhere.
    out = degrade.gaussian_blur(np.full((20, 20, 3), 77, dtype=np.uint8))
    assert (out == 77).all()


def test_blur_spreads_a_bright_pixel_by_the_gaussian_weight():
    # One pixel of 255 at the centre of a 31 x 31 black image, blurred with sigma 2.
    # OpenCV sizes the kernel for sigma 2 on uint8 as 2 x round(3 x 2) + 1 = 13 taps,
    # i = -6..6, weights exp(-i^2 / (2 x 2^2)) = exp(-i^2 / 8):
    # i = 0: 1; 1: 0.8824969; 2: 0.6065307; 3: 0.3246525; 4: 0.1353353; 5: 0.0439369;
    # 6: 0.0111090. Sum = 1 + 2 x (0.8824969 + 0.6065307 + 0.3246525 + 0.1353353
    # + 0.0439369 + 0.0111090) = 1 + 2 x 2.0040613 = 5.0081226.
    # Normalized centre weight 1 / 5.0081226 = 0.1996756; the 2D kernel is separable,
    # so the centre gets 0.1996756^2 = 0.0398704 of the pixel: 255 x 0.0398704 = 10.167
    # -> 10, within 1 grey level for OpenCV's fixed-point rounding. The pixel sits 15 px
    # from every edge, beyond the 6 px reach, so no border rule enters.
    image = np.zeros((31, 31, 3), dtype=np.uint8)
    image[15, 15] = 255
    out = degrade.gaussian_blur(image)
    assert abs(int(out[15, 15, 0]) - 10) <= 1


def test_glare_whitens_a_spot_in_the_field():
    # Field box x 0..100, y 0..100; centre at 0.35 of each side = (35, 35); sigma
    # = 0.15 x 100 = 15. At the centre alpha = 0.85: 200 x 0.15 + 255 x 0.85 = 30 + 216.75
    # = 246.75 -> 247. At (99, 99): d^2 = 64^2 + 64^2 = 8192, alpha = 0.85 x
    # exp(-8192 / 450) = 0.85 x 1.2e-8, so the pixel stays 200.
    out = degrade.glare(np.full((100, 100, 3), 200, dtype=np.uint8), (0, 0, 100, 100))
    assert out[35, 35, 0] == 247 and out[99, 99, 0] == 200


def test_occlusion_covers_a_quarter_by_a_quarter_of_the_field():
    # Field box 100 x 100; patch 0.25 x 100 = 25 px square centred at 0.6 x 100 = 60:
    # left/top = floor(60 - 12.5 + 0.5) = 48, so rows and columns 48..72 are gray 128
    # and 47 and 73 are not. Area 25 x 25 / (100 x 100) = 6.25 percent of the field box.
    out = degrade.occlusion(np.full((100, 100, 3), 200, dtype=np.uint8), (0, 0, 100, 100))
    assert out[48, 48, 0] == 128 and out[72, 72, 0] == 128
    assert out[47, 47, 0] == 200 and out[73, 73, 0] == 200
    assert int((out[..., 0] == 128).sum()) == 25 * 25


def test_every_degradation_states_its_parameters():
    # Six stress rows, each named with its parameters; no homography variant (exp6).
    assert [d.name for d in degrade.DEGRADATIONS] == [
        "grayscale", "lighting_gradient", "low_res_jpeg", "gaussian_blur", "glare", "occlusion"]
    assert all(d.params for d in degrade.DEGRADATIONS if d.name != "grayscale")
    assert not any("homograph" in d.name or "perspective" in d.name for d in degrade.DEGRADATIONS)


def _no_git(args, **kwargs):
    raise OSError("no git in this test")


class _Done:
    def __init__(self, returncode: int, stdout: str = ""):
        self.returncode, self.stdout = returncode, stdout


def _no_read(*args, **kwargs):
    raise AssertionError("the run loaded or read a photo")


def _bridge_answers(monkeypatch, error: dict) -> None:
    from qrep import bridge

    envelope = json.dumps({"ok": False, "error": error})
    monkeypatch.setattr(bridge, "read_confirmed", lambda request_json: envelope)


def test_the_confirmed_reader_fails_closed_on_a_not_implemented_bridge(monkeypatch, capsys, tmp_path):
    # The stub's envelope, whatever qrep.bridge holds today: the run stops with exit 2
    # before it loads a photo, and says B2b is what it waits for.
    _bridge_answers(monkeypatch, {"kind": "not_implemented", "message": "stub"})
    monkeypatch.setattr(corpus, "load_photos", _no_read)
    reason = readers.confirmed_unavailable()
    assert reason is not None and "B2b" in reason
    with pytest.raises(SystemExit) as stop:
        run_eval.main(["--reader", "confirmed", "--out", str(tmp_path / "unused")], runner=_no_git)
    assert stop.value.code == 2
    assert "B2b" in capsys.readouterr().err


def test_a_value_error_means_the_confirmed_reader_can_run(monkeypatch):
    # B2b's read fails the probe's missing photo as a value error: the read exists.
    _bridge_answers(monkeypatch, {"kind": "value", "message": "no such file"})
    assert readers.confirmed_unavailable() is None


def test_the_auto_outcomes_cover_every_verdict():
    # no_grid is a refusal. non_square_repeat is a warning: the old app sets no failure
    # panel for it (web/src/model/verdictStory.ts:105), so it still offers "Open in the
    # editor" and a PDF (web/src/shell/photo/ResultsScreen.tsx:240). The two readable
    # verdicts are a read.
    from qrep.vision.verdict import VERDICTS

    assert set(readers.AUTO_OUTCOMES) == set(VERDICTS)
    assert readers.AUTO_OUTCOMES["no_grid"] == "refused"
    assert readers.AUTO_OUTCOMES["non_square_repeat"] == "warned"
    assert readers.AUTO_OUTCOMES["readable"] == readers.AUTO_OUTCOMES["readable_no_repeat"] == "read"
    # A warning blocks nothing: false warning and refusal recall count holds and refusals.
    assert report.BLOCKED == ("held", "refused")


def test_a_photo_with_nothing_to_confirm_is_one_skipped_row(tmp_path):
    # A refusal-tier photo with no frame or counts: auto-corners has nothing to confirm,
    # so it gets one skipped row at radius 0 and no read.
    source = tmp_path / "r.png"
    assert cv2.imwrite(str(source), np.full((30, 40, 3), 128, dtype=np.uint8))
    truth = corpus.TruthView(corners=None, bands=[], counts=None, fabric_count=None,
                             construction="out_of_scope", provenance={"refusal_class": "verified-jake"})
    unit = harness.Unit(photo="r1", group="corpus", tier="R", split="dev", license="CC0-1.0",
                        device_class="museum scan", resolution="full", cap=None, condition="clean",
                        source=str(source), canvas=(40, 30), truth=truth, truth_label=truth.label_for("R"),
                        readers=("auto-corners",), radii=(0, 4), trials=1, seed="t")
    rows = harness.run_unit(unit)
    assert len(rows) == 1
    row = rows[0]
    assert (row["reader"], row["outcome"], row["radius_px"], row["truth"]) == (
        "auto-corners", "skipped", 0, "gate")
    assert row["reason"] == "no frame or counts in the annotation to confirm"
    agg = report.aggregate(rows, runner=_no_git)
    g4 = next(e for e in agg["gate_metrics"] if e["truth"] == "gate")["G4"]
    # A skipped row never enters n: 0 rows scored, 1 skipped beside it.
    assert (g4["k"], g4["n"], g4["skipped"]) == (0, 0, 1)
    text = report.markdown({"header": {"title": "t"}, "aggregate": agg})
    line = next(r for r in text.splitlines() if r.startswith("| auto-corners | museum scan | full | gate |"))
    # Columns: reader, device, resolution, truth, G1, G2, G4, G5.
    assert line.split("|")[7].strip() == "n = 0, 1 skipped"


def test_the_confirmed_request_gets_the_count_auto_corners_gets():
    # to_read_request prefers verified-jake, then the proposals, so alone it would send
    # the proposed-a count 3. The truth view takes the hand-authored 4 first, and both
    # readers receive that one: 4.
    annotation = _annotation("verified-jake", fabrics=[("proposed-a", 3), ("hand-authored", 4)])
    truth = corpus.truth_view(annotation)

    def unit(truth, annotation):
        return harness.Unit(photo="x", group="corpus", tier="A", split="dev", license="CC0-1.0",
                            device_class="museum scan", resolution="full", cap=None, condition="clean",
                            source="unused.png", canvas=(400, 300), truth=truth, truth_label="gate",
                            readers=("confirmed",), radii=(0,), trials=1, seed="t", annotation=annotation)

    request = harness._confirmed_request(unit(truth, annotation), "x.png", (400, 300), truth.corners)
    assert request.fabric_count == 4 == harness.given_fabrics(truth)
    # 13 is outside the read's 2 to 12, so neither reader receives a count.
    annotation = _annotation("verified-jake", fabrics=[("hand-authored", 13)])
    truth = corpus.truth_view(annotation)
    request = harness._confirmed_request(unit(truth, annotation), "x.png", (400, 300), truth.corners)
    assert request.fabric_count is None and harness.given_fabrics(truth) is None


def test_the_start_sha_check_stops_the_run_before_any_read(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus, "load_photos", _no_read)
    monkeypatch.setattr(readers, "read_auto", _no_read)
    scope = ["--", "qrep/vision/", ":(exclude)qrep/vision/read/"]
    calls = []

    def head_matches(args, **kwargs):
        calls.append(args)
        return _Done(0 if "HEAD" in args else 1)

    # HEAD matches the start SHA but the working tree differs: the second diff fails.
    with pytest.raises(SystemExit) as stop:
        run_eval.main(["--start-sha", "abc123", "--out", str(tmp_path / "r")], runner=head_matches)
    assert "working tree" in str(stop.value.code)
    assert calls == [["git", "diff", "--quiet", "abc123", "HEAD", *scope],
                     ["git", "diff", "--quiet", "abc123", *scope]]
    # HEAD itself differs: the first diff fails and the second never runs.
    calls.clear()

    def differs(args, **kwargs):
        calls.append(args)
        return _Done(1)

    with pytest.raises(SystemExit) as stop:
        run_eval.main(["--start-sha", "abc123", "--out", str(tmp_path / "r")], runner=differs)
    assert "HEAD" in str(stop.value.code) and len(calls) == 1


def test_report_paths_keep_a_dotted_stem():
    # with_suffix would cut "v0.4-eval" to "v0.json"; the whole name is kept.
    base = Path("reports") / "v0.4-eval"
    assert run_eval.report_paths(base, "dev") == (Path("reports/v0.4-eval.json"), Path("reports/v0.4-eval.md"))
    assert run_eval.report_paths(base, "holdout") == (
        Path("reports/v0.4-eval-holdout.json"), Path("reports/v0.4-eval-holdout.md"))


def test_private_refuses_a_report_that_git_would_track(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus, "load_photos", _no_read)
    seen = []

    def tracked(args, **kwargs):
        seen.append(args[1])
        # Inside a work tree, and check-ignore exits 1: not ignored.
        return _Done(0, "true\n") if args[1] == "rev-parse" else _Done(1)

    with pytest.raises(SystemExit) as stop:
        run_eval.main(["--private", "--out", str(tmp_path / "out" / "r")], runner=tracked)
    assert stop.value.code == 2
    assert seen == ["rev-parse", "check-ignore"]

    class Loaded(Exception):
        pass

    def loaded(*args, **kwargs):
        raise Loaded(kwargs)

    # Ignored by git (every answer exit 0): the run goes on and loads with private rows
    # allowed.
    monkeypatch.setattr(corpus, "load_photos", loaded)
    with pytest.raises(Loaded) as hit:
        run_eval.main(["--private", "--out", str(tmp_path / "out" / "r")],
                      runner=lambda args, **kwargs: _Done(0, "true\n"))
    assert hit.value.args[0]["allow_private"] is True


def test_photoreal_units_are_built_from_their_sidecars():
    units = run_eval._photoreal_units(SimpleNamespace(seed="t"), ("auto", "auto-corners"))
    # 2 fixtures x 2 caps (1400 and 2000) = 4 units, fixture by fixture.
    assert [(u.photo, u.resolution) for u in units] == [
        ("busy_print_squares", "fixture-1400"), ("busy_print_squares", "fixture-2000"),
        ("low_contrast_hst", "fixture-1400"), ("low_contrast_hst", "fixture-2000")]
    assert all(u.group == "named" and u.truth_label == "synthetic" and u.cap is None for u in units)
    busy, busy_2000, hst, hst_2000 = units
    # busy_print_squares_1400.json: grid 13 rows x 11 cols, repeat_cells null, so the field
    # is one block: 11 // 11 = 1 across and 13 // 13 = 1 down, of 11 x 13 squares.
    c = busy.truth.counts
    assert (c.blocks_across, c.blocks_down, c.squares_per_block_across, c.squares_per_block_down) == (
        1, 1, 11, 13)
    # Cell truth: 13 rows of 11; palette_hex 2 colors, so fabric count 2.
    assert len(busy.truth_cells) == 13 and {len(row) for row in busy.truth_cells} == {11}
    assert busy.truth_colors == ["#8f3b3b", "#28345e"] and busy.truth.fabric_count == 2
    # canvas 1214 x 1400, quad 96..1117 by 96..1303, border_pitches 0.0: no band.
    assert busy.canvas == (1214, 1400)
    assert busy.truth.corners == [(96.0, 96.0), (1117.0, 96.0), (1117.0, 1303.0), (96.0, 1303.0)]
    assert busy.truth.bands == []
    # low_contrast_hst_1400.json: grid 28 rows x 24 cols, repeat_cells [4, 4]: 24 // 4 = 6
    # blocks across and 28 // 4 = 7 down, of 4 x 4 squares; no cells key, so no cell truth.
    c = hst.truth.counts
    assert (c.blocks_across, c.blocks_down, c.squares_per_block_across, c.squares_per_block_down) == (
        6, 7, 4, 4)
    assert hst.truth_cells is None and hst.truth_colors is None
    # The 2000 px renders' canvases: 1735 x 2000 and 1754 x 2000.
    assert busy_2000.canvas == (1735, 2000) and hst_2000.canvas == (1754, 2000)


def _quilt_png(variant: int) -> bytes:
    # A 160 x 160 photo: a 6 x 6 checkerboard of 20 px squares (red and blue) on gray,
    # its outer edge at 20..140 px. variant changes one background pixel, so the bytes
    # (and so the holdout split) differ while the quilt stays the same.
    image = np.full((160, 160, 3), 128, dtype=np.uint8)
    for r in range(6):
        for c in range(6):
            color = (40, 40, 200) if (r + c) % 2 == 0 else (200, 60, 40)
            image[20 + r * 20:40 + r * 20, 20 + c * 20:40 + c * 20] = color
    image[0, 0] = (variant % 256, 0, 0)
    return cv2.imencode(".png", image)[1].tobytes()


def _png_in_split(split: str, start: int) -> tuple[bytes, int]:
    for variant in range(start, start + 60):
        data = _quilt_png(variant)
        if corpus.split_of(hashlib.sha256(data).hexdigest()) == split:
            return data, variant
    raise AssertionError("no variant landed in the split")


def _write_corpus(tmp_path, *, overrides=None, holdout_files=True):
    """overrides maps a stem to manifest fields to change; holdout_files False leaves the
    holdout photo's annotation and source image out."""
    root, cache = tmp_path / "corpus", tmp_path / "cache"
    (root / "annotations").mkdir(parents=True)
    cache.mkdir()
    columns = ["file", "license", "sha256", "file_sha256", "px_w", "px_h", "tier", "class",
               "capture", "eval_set"]
    rows = []
    plan = [("a-dev", "A", "dev"), ("a-hold", "A", "holdout"), ("r-dev", "R", "dev")]
    variant = 0
    for stem, tier, split in plan:
        data, variant = _png_in_split(split, variant + 1)
        sha = hashlib.sha256(data).hexdigest()
        rows.append({"file": f"private/cache/{stem}.png", "license": "CC0-1.0", "sha256": sha,
                     "file_sha256": "", "px_w": "160", "px_h": "160", "tier": tier,
                     "class": "squares" if tier == "A" else "on_point", "capture": "museum_scan",
                     "eval_set": "v0", **(overrides or {}).get(stem, {})})
        if split == "holdout" and not holdout_files:
            continue
        (cache / f"{stem}.png").write_bytes(data)
        claim = {"provenance": "proposed-a"}
        doc = {"schema_version": 1, "photo": f"private/cache/{stem}.png", "sha256": sha,
               "canvas": [160, 160],
               "capture": [{"provenance": "screened", "value": "museum_scan"}],
               "construction_class": [{**claim, "value": "squares" if tier == "A" else "out_of_scope"}]}
        if tier == "A":
            doc["frame"] = [{**claim, "value": {"outer_edge": {"kind": "outer_edge", "bands": [], "corners": {
                "top_left": {"x": 20.0, "y": 20.0}, "top_right": {"x": 140.0, "y": 20.0},
                "bottom_right": {"x": 140.0, "y": 140.0}, "bottom_left": {"x": 20.0, "y": 140.0}}}}}]
            doc["counts"] = [{**claim, "value": {"blocks_across": 1, "blocks_down": 1,
                                                 "squares_per_block_across": 6, "squares_per_block_down": 6}}]
            doc["fabrics"] = [{**claim, "value": {"count": 2}}]
        (root / "annotations" / f"{stem}.json").write_text(json.dumps(doc), encoding="utf-8")
    with (root / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return root, cache


def test_load_photos_refuses_a_private_row_unless_allowed(tmp_path):
    # Plan 8.2: a photo that is not a licensed museum scan stays private, so loading it
    # needs --private (allow_private).
    root, cache = _write_corpus(tmp_path, overrides={"r-dev": {"license": "LicenseRef-private"}})
    with pytest.raises(ValueError, match="r-dev"):
        corpus.load_photos(root, cache, split="dev")
    assert [p.stem for p in corpus.load_photos(root, cache, split="dev", allow_private=True)] == [
        "a-dev", "r-dev"]
    # The holdout split never holds r-dev, so it loads without allow_private.
    assert [p.stem for p in corpus.load_photos(root, cache, split="holdout")] == ["a-hold"]


def test_load_photos_refuses_a_phone_capture_unless_allowed(tmp_path):
    root, cache = _write_corpus(tmp_path / "camera", overrides={"a-dev": {"capture": "camera"}})
    with pytest.raises(ValueError, match="a-dev"):
        corpus.load_photos(root, cache, split="dev")


def test_load_photos_picks_the_split_before_opening_anything(tmp_path):
    # The holdout photo's annotation and source image do not exist: a dev load never
    # opens them, while a holdout load stops on the missing annotation.
    root, cache = _write_corpus(tmp_path, holdout_files=False)
    assert [p.stem for p in corpus.load_photos(root, cache, split="dev")] == ["a-dev", "r-dev"]
    with pytest.raises(FileNotFoundError):
        corpus.load_photos(root, cache, split="holdout")


def test_a_run_reports_its_provenance_and_keeps_the_holdout_apart(tmp_path):
    root, cache = _write_corpus(tmp_path)
    # A stem with a dot keeps its whole name in the report's file names.
    out = tmp_path / "out" / "v0.4-eval"
    args = ["--corpus", str(root), "--cache", str(cache), "--out", str(out), "--radii", "0,4",
            "--trials", "1", "--resolutions", "full", "--no-photoreal", "--workers", "1"]
    assert run_eval.main(args) == 0
    payload = json.loads((out.parent / "v0.4-eval.json").read_text(encoding="utf-8"))
    header = payload["header"]
    for key in ("date", "command", "qrep_path", "git_sha", "git_status", "cv2_version", "decode_path",
                "split"):
        assert header[key], key
    assert header["split"] == "dev"
    if sys.platform == "emscripten":
        assert header["git_sha"] == run_eval.GIT_UNAVAILABLE
    else:
        assert re.fullmatch(r"[0-9a-f]{40}", header["git_sha"]), header["git_sha"]
    # The manifest sits in tmp_path, outside the repo, so the header does not print its path.
    assert header["inputs"].startswith("a manifest outside the repo")
    rows = payload["rows"]
    assert payload["aggregate"]["errors"] == []
    assert {row["outcome"] for row in rows} <= {"read", "warned", "held", "refused", "skipped"}
    # The dev split holds a-dev and r-dev; the holdout photo never appears.
    assert {row["photo"] for row in rows} == {"a-dev", "r-dev"}
    # Proposals only: every row is provisional and no row counts toward a gate.
    assert {row["truth"] for row in rows} == {"provisional"}
    corpus_rows = [row for row in rows if row["group"] == "corpus"]
    # auto reads both photos once. auto-corners reads a-dev at 0 and 4 px and skips r-dev,
    # which has no frame to confirm.
    assert len([row for row in corpus_rows if row["reader"] == "auto"]) == 2
    corners = [row for row in corpus_rows if row["reader"] == "auto-corners"]
    assert sorted((row["photo"], row["radius_px"], row["outcome"] == "skipped") for row in corners) == [
        ("a-dev", 0, False), ("a-dev", 4, False), ("r-dev", 0, True)]
    # a-dev's corners lie 20 px inside its 160 px edges, more than 4, so no clamp: each
    # moves the full 4 px (mean 4.0), and 0 at radius 0.
    moved = {row["radius_px"]: row["moved_px_mean"] for row in corners if row["photo"] == "a-dev"}
    assert moved == {0: 0.0, 4: pytest.approx(4.0)}
    # Degradations on: a-dev is a CC0-1.0 museum tier A photo with corners, so each of the
    # 6 degradations stages it once for auto and once for auto-corners (radius 0 only):
    # 6 x 2 = 12 stress rows. r-dev is tier R and gets none.
    stress = [row for row in rows if row["group"] == "stress"]
    assert len(stress) == 12 and {row["photo"] for row in stress} == {"a-dev"}
    assert {row["condition"] for row in stress} == {d.name for d in degrade.DEGRADATIONS}
    # Every row records what the reader received (vision-13); no degradation resizes a
    # 160 px photo (low_res_jpeg stops at 600 px).
    assert all(row["received"]["staged_size"] == [160, 160] for row in rows)
    assert (out.parent / "v0.4-eval.md").exists()
    # --holdout writes its own report holding only the holdout photo.
    assert run_eval.main([*args, "--holdout"]) == 0
    held = json.loads((out.parent / "v0.4-eval-holdout.json").read_text(encoding="utf-8"))
    assert held["header"]["split"] == "holdout"
    assert {row["photo"] for row in held["rows"]} == {"a-hold"}
    assert (out.parent / "v0.4-eval-holdout.md").exists()
