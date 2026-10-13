"""Simulation, corpus, degradation and harness tests for the eval (plan D4a).

Expected values are worked by hand in the comments from the plan's text, the
app's resolution caps (web/src/model/downscale.ts) and each degradation's
stated parameters, never copied from a run.
"""

import csv
import dataclasses
import hashlib
import json
import math
import random
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
    # A direction stays on the image from (0, 0) only within the quarter turn [0, pi/2],
    # chance 1/4 per draw; all 10 draws doing so has chance (1/4)^10 < 1e-6. So the clamp
    # shortens the move in at least one of these 10 seeded trials.
    assert any(trial.moved_px[0] < 8.0 - 1e-9 for trial in trials[1:])


def test_each_radius_draws_its_own_directions():
    # The seed is key, radius and trial: radius 2 and radius 4 at trial 0 draw different
    # angles, so the corners' unit displacement vectors differ.
    r2, r4 = simulate.corner_trials(SQUARE, (2, 4), 1, "k", bounds=(1000, 1000))
    units = [[((x1 - x0) / t.radius_px, (y1 - y0) / t.radius_px) for (x0, y0), (x1, y1) in zip(SQUARE, t.corners)]
             for t in (r2, r4)]
    assert any(math.dist(a, b) > 1e-6 for a, b in zip(*units))


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


def _frame_claim(code: str, inset: float, bands=()) -> dict:
    a, b, c = inset, 400.0 - inset, 300.0 - inset
    return {"provenance": code, "value": {"outer_edge": {
        "kind": "outer_edge", "bands": [{"width_squares": w} for w in bands],
        "corners": {"top_left": {"x": a, "y": a}, "top_right": {"x": b, "y": a},
                    "bottom_right": {"x": b, "y": c}, "bottom_left": {"x": a, "y": c}}}}}


def _annotation(provenance: str, *, frame=True, fabrics=(), refusal=None, built=None, klass=None,
                bands=(), capture=None, other_frame=None) -> an.Annotation:
    """fabrics is (provenance, count) pairs; refusal and built name the provenance of a
    refusal class and of the construction class when it differs from provenance, klass
    the class value; capture is a (provenance, value) claim; other_frame a second
    frame's provenance, its corners 20 px in where the first frame's are 10 px in."""
    claim = {"provenance": provenance}
    doc = {
        "schema_version": 1,
        "photo": "private/cache/x.jpg",
        "sha256": "1" * 64,
        "canvas": [400, 300],
        "construction_class": [{"provenance": built or provenance,
                                "value": klass or ("out_of_scope" if refusal else "squares")}],
    }
    if fabrics:
        doc["fabrics"] = [{"provenance": code, "value": {"count": n}} for code, n in fabrics]
    if refusal:
        codes = (refusal,) if isinstance(refusal, str) else refusal
        doc["refusal_class"] = [{"provenance": code, "value": "on_point"} for code in codes]
    if capture:
        doc["capture"] = [{"provenance": capture[0], "value": capture[1]}]
    if frame:
        # The second frame goes first, so a pick by list order would take it.
        doc["frame"] = ([_frame_claim(other_frame, 20.0)] if other_frame else []) + [
            _frame_claim(provenance, 10.0, bands)]
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


def test_a_proposed_fabric_count_never_grades_a_gate_row():
    # Plan 8.2 verifies frame, bands, counts and class, never the fabric count, so the count
    # plays no part in the label. Verified frame, counts and class with only a proposed-a
    # count: gate, and the count is withheld (a user who skips it), so no k is graded.
    view = corpus.truth_view(_annotation("verified-jake", fabrics=[("proposed-a", 3)]))
    assert view.provenance["fabrics"] == "proposed-a"
    assert view.label_for("A") == "gate" and view.label == "gate"
    assert view.fabrics_for("gate") is None and harness.given_fabrics(view, "gate") is None
    # The same truth on a provisional row gives the proposal to the reader: 3.
    assert harness.given_fabrics(view, "provisional") == 3
    # A hand-authored count is square truth (an.TRUTH): it wins over the proposal, and the
    # gate row gives and scores it: 4.
    view = corpus.truth_view(_annotation("verified-jake", fabrics=[("proposed-a", 3), ("hand-authored", 4)]))
    assert (view.fabric_count, view.provenance["fabrics"]) == (4, "hand-authored")
    assert view.label_for("A") == "gate" and view.fabrics_for("gate") == 4
    # A provisional row rests on proposals anyway, so it gives the proposed 3.
    view = corpus.truth_view(_annotation("proposed-a", fabrics=[("proposed-a", 3)]))
    assert view.label_for("A") == "provisional" and view.fabrics_for("provisional") == 3


def test_a_gate_row_without_a_true_count_records_no_k(tmp_path):
    # Score side of the same rule: a gate unit whose only count is proposed records
    # neither k_truth nor k_exact; a provisional one records both.
    view = corpus.truth_view(_annotation("verified-jake", fabrics=[("proposed-a", 2)]))
    reading = _fake_reading(received={"fabrics": None})
    unit = _plain_unit(tmp_path / "unused.png", canvas=(400, 300), corners=view.corners, counts=view.counts,
                       readers_=("auto",))
    gate = harness.score(dataclasses.replace(unit, truth=view, truth_label="gate"), reading)
    assert "k_truth" not in gate and "k_exact" not in gate
    prov = harness.score(dataclasses.replace(unit, truth=view, truth_label="provisional"), reading)
    # The fake read has 2 colors and the proposal says 2: exact.
    assert (prov["k_truth"], prov["k_exact"]) == (2, True)


def test_a_refusal_photo_is_gated_on_its_class():
    # Tier R: a verified-jake refusal class is gate truth even with a proposed
    # construction class and no frame. On tier A the same verified call says out of
    # scope, which contradicts the tier: conflict.
    view = corpus.truth_view(_annotation("proposed-a", frame=False, refusal="verified-jake"))
    assert view.provenance["refusal_class"] == "verified-jake"
    assert view.label_for("R") == "gate"
    assert view.label_for("A") == "conflict"
    # Both classes proposed: provisional.
    view = corpus.truth_view(_annotation("proposed-a", frame=False, refusal="proposed-b"))
    assert view.label_for("R") == "provisional"
    # A proposed refusal class listed before a verified one: the verified claim is taken.
    view = corpus.truth_view(_annotation("proposed-a", frame=False, refusal=("proposed-b", "verified-jake")))
    assert view.provenance["refusal_class"] == "verified-jake" and view.label_for("R") == "gate"
    # A verified out_of_scope construction class alone also gates a refusal photo.
    view = corpus.truth_view(_annotation("verified-jake", frame=False, klass="out_of_scope"))
    assert "refusal_class" not in view.provenance
    assert view.label_for("R") == "gate"


def test_a_verified_class_that_contradicts_the_tier_is_a_conflict():
    # Verified squares (in scope) on a refusal photo: conflict.
    assert corpus.truth_view(_annotation("verified-jake")).label_for("R") == "conflict"
    # Verified out_of_scope on a tier A photo, frame and counts verified too: conflict.
    view = corpus.truth_view(_annotation("verified-jake", klass="out_of_scope"))
    assert view.label_for("A") == "conflict" and view.label == "conflict"
    # Verified frame and counts with a proposed class: nothing verified says the photo is
    # in scope, so provisional, on either tier.
    view = corpus.truth_view(_annotation("verified-jake", built="proposed-a"))
    assert (view.label_for("A"), view.label_for("R")) == ("provisional", "provisional")


def test_the_verified_frame_wins_over_a_proposal_listed_first():
    # A proposed-a frame (corners 20 px in) listed before the verified-jake frame (10 px
    # in): the truth takes the verified claim, its provenance and its corners.
    view = corpus.truth_view(_annotation("verified-jake", other_frame="proposed-a"))
    assert view.provenance["frame"] == "verified-jake"
    assert view.corners == [(10.0, 10.0), (390.0, 10.0), (390.0, 290.0), (10.0, 290.0)]
    assert view.label_for("A") == "gate"


def test_truth_bands_come_from_the_frame():
    # The outer edge's bands, outside in, in squares: 1.5 then 0.5.
    assert corpus.truth_view(_annotation("verified-jake", bands=[1.5, 0.5])).bands == [1.5, 0.5]
    assert corpus.truth_view(_annotation("verified-jake")).bands == []


def test_the_device_class_takes_a_verified_or_screened_capture_claim_first():
    row = {"file": "private/cache/x.jpg", "capture": "museum_scan", "tier": "A", "sha256": "1" * 64}

    def device(capture):
        return corpus.Photo("x", row, _annotation("verified-jake", capture=capture), Path("x.jpg")).device_class

    # No claim: the manifest row's museum_scan.
    assert device(None) == "museum scan"
    # A verified-jake or screened claim wins over the row.
    assert device(("verified-jake", "camera")) == "phone camera"
    assert device(("screened", "nested_screenshot")) == "screenshot"
    # A proposal is no capture truth: the row's museum_scan stands.
    assert device(("proposed-a", "camera")) == "museum scan"


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


def test_blur_sigma_is_2_to_six_places_on_a_float_image():
    # On a float image OpenCV sizes the kernel as 2 x round(4 x 2) + 1 = 17 taps, i = -8..8,
    # weights exp(-i^2 / 8): the 13 above (sum 5.00812249 to 8 places) plus i = 7:
    # exp(-6.125) = 0.00218749 and i = 8: exp(-8) = 0.00033546 on both sides:
    # 5.00812249 + 2 x (0.00218749 + 0.00033546) = 5.00812249 + 0.00504590 = 5.01316839.
    # Centre 1 / 5.01316839 = 0.19947465, squared 0.03979014 of a pixel of 1.0. Float math
    # leaves no rounding, so a sigma of 2.1 (centre near 1 / (2 pi 2.1^2) = 0.0361) fails.
    image = np.zeros((41, 41, 3), dtype=np.float32)
    image[20, 20] = 1.0
    out = degrade.gaussian_blur(image)
    assert float(out[20, 20, 0]) == pytest.approx(0.0397901, abs=1e-5)


def test_low_res_jpeg_encodes_at_quality_40(monkeypatch):
    seen = []
    encode = cv2.imencode

    def spy(ext, image, params=None):
        seen.append((ext, list(params or [])))
        return encode(ext, image, params)

    monkeypatch.setattr(degrade.cv2, "imencode", spy)
    degrade.low_res_jpeg(np.full((10, 10, 3), 128, dtype=np.uint8))
    assert seen == [(".jpg", [cv2.IMWRITE_JPEG_QUALITY, 40])]


def test_low_res_jpeg_downsamples_by_area():
    # 1800 x 1800 -> 600 x 600, a factor of 3. Each 3 x 3 block holds one 255 at its
    # centre (row and column 1 mod 3) and 8 zeros. INTER_AREA averages the block:
    # 255 / 9 = 28.33 -> 28, on every output pixel. Bilinear and bicubic sample the
    # source at 3 x d + 1, the bright centre (255); nearest samples 3 x d, a zero (0).
    # A flat 28 survives the JPEG within 2 levels: its 8 x 8 blocks carry only a DC term,
    # 8 x (pixel - 128), and at quality 40 the luma DC step is (16 x 125 + 50) / 100 = 20
    # in integer division, so the DC error is at most 20 / 2 = 10, or 10 / 8 = 1.25
    # levels per pixel.
    rows = np.arange(1800) % 3 == 1
    image = np.zeros((1800, 1800, 3), dtype=np.uint8)
    image[np.ix_(rows, rows)] = 255
    out, scale = degrade.low_res_jpeg(image)
    assert out.shape[:2] == (600, 600) and scale == pytest.approx(1 / 3)
    assert int(np.abs(out.astype(int) - 28).max()) <= 2


def test_glare_sigma_follows_the_shorter_side():
    # Field box x 0..200, y 0..100: centre (0.35 x 200, 0.35 x 100) = (70, 35), sigma
    # = 0.15 x min(200, 100) = 15. At (x 85, y 35): d^2 = 15^2 = 225,
    # alpha = 0.85 x exp(-225 / (2 x 225)) = 0.85 x 0.6065307 = 0.5155511, so
    # 200 + (255 - 200) x 0.5155511 = 200 + 28.3553 = 228.355 -> 228. With the longer
    # side (sigma 30): 0.85 x exp(-225 / 1800) = 0.7501224 -> 241.26 -> 241.
    out = degrade.glare(np.full((100, 200, 3), 200, dtype=np.uint8), (0, 0, 200, 100))
    assert out[35, 85, 0] == 228
    # The peak sits at (70, 35): 200 x 0.15 + 255 x 0.85 = 246.75 -> 247.
    assert out[35, 70, 0] == 247


def test_glare_and_gradient_in_bands_equal_their_whole_image_formulas(monkeypatch):
    # Bands bound the float64 copies on a 117 MP scan; they must not move a pixel. The
    # reference is each docstring's formula over the whole image at once, the form the
    # hand-computed tests above check: alpha = 0.85 x exp(-d^2 / (2 sigma^2)) blended
    # toward 255, and brightness times 1 - (1 - 0.55) x column / (width - 1). The ramp
    # keeps the form 1 - 0.55: in binary that is 0.44999999999999996, not 0.45, and a
    # pixel on a half level rounds by it. Bands of 7 rows over 100 rows cross 14 band
    # edges, and the last band holds 2 rows.
    image = (np.arange(100 * 120 * 3) % 251).astype(np.uint8).reshape(100, 120, 3)
    box = (10.0, 5.0, 110.0, 95.0)
    cx, cy, sigma = 10.0 + 0.35 * 100.0, 5.0 + 0.35 * 90.0, 0.15 * 90.0
    ys, xs = np.mgrid[0:100, 0:120]
    alpha = (0.85 * np.exp(-((xs - cx) ** 2 + (ys - cy) ** 2) / (2 * sigma * sigma)))[..., None]
    glare = np.clip(np.rint(image.astype(np.float64) * (1 - alpha) + 255.0 * alpha), 0, 255).astype(np.uint8)
    ramp = 1.0 - (1.0 - 0.55) * np.arange(120) / 119
    gradient = np.clip(np.rint(image.astype(np.float64) * ramp[None, :, None]), 0, 255).astype(np.uint8)
    seen = []
    to_uint8 = degrade._to_uint8

    def spy(values):
        seen.append(values.shape[0])
        return to_uint8(values)

    monkeypatch.setattr(degrade, "BAND_ROWS", 7)
    monkeypatch.setattr(degrade, "_to_uint8", spy)
    assert np.array_equal(degrade.glare(image, box), glare)
    assert np.array_equal(degrade.lighting_gradient(image), gradient)
    # No float copy holds more than one band: 14 bands of 7 rows and one of 2, twice.
    assert seen == ([7] * 14 + [2]) * 2


def test_apply_dispatches_each_degradation_by_name():
    image = (np.arange(60 * 80 * 3) % 251).astype(np.uint8).reshape(60, 80, 3)
    box = (10.0, 5.0, 70.0, 55.0)
    direct = {
        "grayscale": (degrade.grayscale(image), 1.0),
        "lighting_gradient": (degrade.lighting_gradient(image), 1.0),
        "low_res_jpeg": degrade.low_res_jpeg(image),
        "gaussian_blur": (degrade.gaussian_blur(image), 1.0),
        "glare": (degrade.glare(image, box), 1.0),
        "occlusion": (degrade.occlusion(image, box), 1.0),
    }
    assert set(direct) == {d.name for d in degrade.DEGRADATIONS}
    for name, (expected, scale) in direct.items():
        got, got_scale = degrade.apply(name, image, box)
        assert np.array_equal(got, expected), name
        assert got_scale == scale, name
    with pytest.raises(ValueError):
        degrade.apply("perspective", image, box)


def _no_git(args, **kwargs):
    raise OSError("no git in this test")


class _Done:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


NOT_A_REPO = "fatal: not a git repository (or any of the parent directories): .git"


def _outside_git(args, **kwargs):
    # git answering as it does in a folder outside every work tree.
    return _Done(128, "", NOT_A_REPO)


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
    assert line.split("|")[7].strip() == "n = 0, 1 skipped; no frame or counts on the v0 refusal photos (#243)"


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
    assert request.fabric_count == 4 == harness.given_fabrics(truth, "gate")
    # 13 is outside the read's 2 to 12, so neither reader receives a count.
    annotation = _annotation("verified-jake", fabrics=[("hand-authored", 13)])
    truth = corpus.truth_view(annotation)
    request = harness._confirmed_request(unit(truth, annotation), "x.png", (400, 300), truth.corners)
    assert request.fabric_count is None and harness.given_fabrics(truth, "gate") is None


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


def test_load_photos_gates_on_the_license_not_the_capture(tmp_path):
    # Plan 8.1 commits CC0 phone captures with manifest rows: a CC0-1.0 camera row loads.
    root, cache = _write_corpus(tmp_path / "cc0", overrides={"a-dev": {"capture": "camera"}})
    assert [p.stem for p in corpus.load_photos(root, cache, split="dev")] == ["a-dev", "r-dev"]
    # The same capture under a license corpus-guard does not admit is refused.
    root, cache = _write_corpus(tmp_path / "private", overrides={
        "a-dev": {"capture": "camera", "license": "LicenseRef-private"}})
    with pytest.raises(ValueError, match="a-dev"):
        corpus.load_photos(root, cache, split="dev")


def test_load_photos_stops_on_a_changed_or_missing_source(tmp_path):
    root, cache = _write_corpus(tmp_path)
    # Bytes that are not the photo the manifest row binds: its sha256 differs.
    (cache / "a-dev.png").write_bytes(b"not the photo")
    with pytest.raises(ValueError, match="sha256"):
        corpus.load_photos(root, cache, split="dev")
    # A cache without the photo at all.
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="not in the cache"):
        corpus.load_photos(root, empty, split="dev")


def test_load_photos_reads_only_the_eval_set_in_manifest_order(tmp_path):
    root, cache = _write_corpus(tmp_path, overrides={"r-dev": {"eval_set": "v1"}})
    assert [p.stem for p in corpus.load_photos(root, cache, split="dev")] == ["a-dev"]
    assert [p.stem for p in corpus.load_photos(root, cache, eval_set="v1")] == ["r-dev"]
    # No split: both splits, in manifest order (a-dev, a-hold).
    assert [p.stem for p in corpus.load_photos(root, cache)] == ["a-dev", "a-hold"]


def test_load_photos_picks_the_split_before_opening_anything(tmp_path):
    # The holdout photo's annotation and source image do not exist: a dev load never
    # opens them, while a holdout load stops on the missing annotation.
    root, cache = _write_corpus(tmp_path, holdout_files=False)
    assert [p.stem for p in corpus.load_photos(root, cache, split="dev")] == ["a-dev", "r-dev"]
    with pytest.raises(FileNotFoundError):
        corpus.load_photos(root, cache, split="holdout")


FAKE_SHA = "0123456789abcdef0123456789abcdef01234567"


def _fake_git(args, **kwargs):
    # A clean checkout at FAKE_SHA with no merges in its history.
    return _Done(0, FAKE_SHA + "\n") if args[1:] == ["rev-parse", "HEAD"] else _Done(0, "")


def test_a_run_reports_its_provenance_and_keeps_the_holdout_apart(tmp_path):
    root, cache = _write_corpus(tmp_path)
    # A stem with a dot keeps its whole name in the report's file names.
    out = tmp_path / "out" / "v0.4-eval"
    args = ["--corpus", str(root), "--cache", str(cache), "--out", str(out), "--radii", "0,4",
            "--trials", "1", "--resolutions", "full", "--no-photoreal", "--workers", "1"]
    assert run_eval.main(args, runner=_fake_git) == 0
    payload = json.loads((out.parent / "v0.4-eval.json").read_text(encoding="utf-8"))
    header = payload["header"]
    for key in ("date", "command", "qrep_path", "git_sha", "git_status", "cv2_version", "decode_path",
                "split", "masks"):
        assert header[key], key
    assert header["split"] == "dev"
    # The header carries the injected git's answers.
    assert header["git_sha"] == FAKE_SHA
    assert header["git_status"] == "git status --porcelain -- qrep/ scripts/eval/: clean"
    # The manifest and annotations sit in tmp_path, outside the repo, so the header does
    # not print their paths.
    assert header["inputs"].startswith("a manifest outside the repo")
    assert "annotations from an annotations directory outside the repo" in header["inputs"]
    assert "#243" in header["masks"]
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
    assert run_eval.main([*args, "--holdout"], runner=_fake_git) == 0
    held = json.loads((out.parent / "v0.4-eval-holdout.json").read_text(encoding="utf-8"))
    assert held["header"]["split"] == "holdout"
    assert {row["photo"] for row in held["rows"]} == {"a-hold"}
    assert (out.parent / "v0.4-eval-holdout.md").exists()


class _Loaded(Exception):
    pass


def _loaded(*args, **kwargs):
    raise _Loaded(kwargs)


def _private_git(ignore_code, *, inside=None):
    """git for --private: every folder in a work tree (or inside's answer), and
    check-ignore exiting ignore_code(path)."""
    seen = []

    def runner(args, **kwargs):
        seen.append(args)
        if args[1] == "rev-parse":
            return inside or _Done(0, "true\n")
        if args[1] == "check-ignore":
            return _Done(ignore_code(args[-1]))
        return _Done(128, "", "fatal: unexpected")

    runner.seen = seen
    return runner


def test_private_refuses_staging_that_git_would_track(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(corpus, "load_photos", _no_read)
    cache = tmp_path / "corpus" / "private" / "cache"
    argv = ["--private", "--cache", str(cache), "--out", str(tmp_path / "out" / "r")]
    # The reports are ignored, the staging root (the cache's parent) is not: exit 2
    # before any photo loads.
    git = _private_git(lambda path: 1 if "qrep-eval-staging" in path else 0)
    with pytest.raises(SystemExit) as stop:
        run_eval.main(argv, runner=git)
    assert stop.value.code == 2
    # Each path is asked from its nearest existing folder, tmp_path: both reports, then a
    # path inside the staging root, which git matches against a directory ignore rule.
    asked = [Path(args[-1]) for args in git.seen if args[1] == "check-ignore"]
    assert asked == [Path("out/r.json"), Path("out/r.md"), Path("corpus/private/qrep-eval-staging/staged.png")]
    assert "staged.png" in capsys.readouterr().err
    # Everything ignored: the run goes on to load, with private rows allowed.
    monkeypatch.setattr(corpus, "load_photos", _loaded)
    with pytest.raises(_Loaded) as hit:
        run_eval.main(argv, runner=_private_git(lambda path: 0))
    assert hit.value.args[0]["allow_private"] is True


def test_private_fails_closed_when_git_cannot_say(monkeypatch, tmp_path):
    monkeypatch.setattr(corpus, "load_photos", _no_read)
    argv = ["--private", "--out", str(tmp_path / "out" / "r")]

    def missing(args, **kwargs):
        raise OSError("git is not installed")

    # No git at all, check-ignore failing with 128 (an error, not an answer), and a
    # rev-parse failure other than "not a git repository" all stop the run with exit 2.
    for runner in (missing, _private_git(lambda path: 128),
                   _private_git(lambda path: 0, inside=_Done(128, "", "fatal: detected dubious ownership"))):
        with pytest.raises(SystemExit) as stop:
            run_eval.main(argv, runner=runner)
        assert stop.value.code == 2


def test_private_passes_outside_every_work_tree(monkeypatch, tmp_path):
    # git's own "not a git repository" for every path: nothing can commit the outputs.
    monkeypatch.setattr(corpus, "load_photos", _loaded)
    with pytest.raises(_Loaded):
        run_eval.main(["--private", "--out", str(tmp_path / "out" / "r")], runner=_outside_git)


def _fake_reading(*, rows=6, cols=6, received=None):
    return readers.Reading(outcome="read", verdict=None, rows=rows, cols=cols, colors=["#ff0000", "#0000ff"],
                           cells=None, confidence=None, cell_size_eighths=16, band_eighths=[],
                           low_confidence_below=None, flagged_regions=[], seconds=0.0, received=received or {})


def _plain_unit(source, *, canvas, corners, counts, readers_, cap=None, radii=(0,), condition="clean"):
    truth = corpus.TruthView(corners=corners, bands=[], counts=counts, fabric_count=2, construction="squares",
                             provenance={"fabrics": "hand-authored"})
    return harness.Unit(photo="q", group="corpus", tier="A", split="dev", license="CC0-1.0",
                        device_class="museum scan", resolution="full" if cap is None else f"cap-{cap}",
                        cap=cap, condition=condition, source=str(source), canvas=canvas, truth=truth,
                        truth_label="gate", readers=readers_, radii=radii, trials=1, seed="t")


def test_miscounts_no_count_can_express_are_skipped_rows(monkeypatch, tmp_path):
    source = tmp_path / "q.png"
    assert cv2.imwrite(str(source), np.full((100, 100, 3), 128, dtype=np.uint8))
    monkeypatch.setattr(readers, "read_confirmed",
                        lambda request, size: _fake_reading(received={"request": json.loads(request.model_dump_json())}))
    # One block of 13 across x 11 down: of the 10 miscount kinds, block -1 across and
    # block -1 down leave 0 blocks, and half finds 13 and 11 odd with 1 block, so 3 are
    # skipped and 7 read, beside the true-count read: 1 + 7 + 3 = 11 rows.
    counts = Counts(blocks_across=1, blocks_down=1, squares_per_block_across=13, squares_per_block_down=11)
    unit = _plain_unit(source, canvas=(100, 100), corners=[(10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)],
                       counts=counts, readers_=("confirmed",))
    rows = harness.run_unit(unit)
    assert len(rows) == 11
    skipped = {r["variant"]: r["reason"] for r in rows if r["outcome"] == "skipped"}
    assert skipped == {"block -1 across": "blocks_across would be 0", "block -1 down": "blocks_down would be 0",
                       "half": "no whole half across: 1 x 13 squares"}
    assert all(r["radius_px"] == 0 and r["reader"] == "confirmed" for r in rows)
    # Every confirmed request carries the fabric count auto-corners gets: 2.
    assert {r["received"]["request"]["fabric_count"] for r in rows if r["outcome"] == "read"} == {2}
    # The 10 miscount rows (7 read, 3 skipped) are the miscount trials; none is a photo row.
    agg = report.aggregate(rows, runner=_no_git)
    assert agg["miscount_trials"] == 10
    assert agg["by_tier"]["confirmed | A | full"]["n_rows"] == 1


def test_a_stage_error_is_each_readers_true_corner_row(tmp_path):
    # No such source: cv2 cannot decode it, so every reader gets an error row where its
    # true-corner read would be (no corners for auto, 0 px for the others), and the
    # confirmed reader one per miscount variant. Counts 1 block of 4 x 4: square +1 and
    # -1 on each axis (4), block +1 on each axis (2), half (4 / 2 = 2 each way) and
    # double: 8 variants, error rows; block -1 on each axis leaves 0 blocks: 2 skipped.
    unit = _plain_unit(tmp_path / "missing.png", canvas=(100, 100),
                       corners=[(10.0, 10.0), (90.0, 10.0), (90.0, 90.0), (10.0, 90.0)],
                       counts=Counts(blocks_across=1, blocks_down=1, squares_per_block_across=4,
                                     squares_per_block_down=4),
                       readers_=("auto", "auto-corners", "confirmed"))
    rows = harness.run_unit(unit)
    assert [(r["reader"], r["radius_px"], r["variant"], r["outcome"]) for r in rows[:3]] == [
        ("auto", None, "true", "error"), ("auto-corners", 0, "true", "error"), ("confirmed", 0, "true", "error")]
    variants = {r["variant"]: r["outcome"] for r in rows[3:]}
    assert all(r["reader"] == "confirmed" and r["radius_px"] == 0 for r in rows[3:])
    assert variants == {**{f"square {s} {axis}": "error" for s in ("+1", "-1") for axis in ("across", "down")},
                        "block +1 across": "error", "block +1 down": "error", "half": "error", "double": "error",
                        "block -1 across": "skipped", "block -1 down": "skipped"}
    agg = report.aggregate(rows, runner=_no_git)
    # 8 error and 2 skipped miscount rows: 10 miscount trials.
    assert agg["miscount_trials"] == 10
    assert agg["by_tier"]["auto | A | full"]["errors"] == 1
    assert agg["jitter"]["auto-corners | full | 0"]["false_warning"]["errors"] == 1


def test_stage_caps_the_image_then_degrades_the_scaled_field(tmp_path):
    # A 400 x 200 canvas of 200 capped at 100: factor 100 / 400 = 0.25, staged 100 x 50
    # (INTER_AREA keeps a flat 200). The truth corners (40, 20) .. (360, 180) scale by 0.25
    # to (10, 5) .. (90, 45): field box x 10..90, y 5..45. Occlusion: patch
    # floor(0.25 x 80 + 0.5) = 20 wide, floor(0.25 x 40 + 0.5) = 10 tall,
    # left floor(10 + 0.6 x 80 - 10 + 0.5) = 48, top floor(5 + 0.6 x 40 - 5 + 0.5) = 24:
    # rows 24..33, columns 48..67, 20 x 10 = 200 pixels of 128. Unscaled corners would put
    # the patch at column 192, off the image.
    source = tmp_path / "wide.png"
    assert cv2.imwrite(str(source), np.full((200, 400, 3), 200, dtype=np.uint8))
    unit = _plain_unit(source, canvas=(400, 200), cap=100, condition="occlusion",
                       corners=[(40.0, 20.0), (360.0, 20.0), (360.0, 180.0), (40.0, 180.0)], counts=None,
                       readers_=("auto",))
    workdir = tmp_path / "stage"
    workdir.mkdir()
    path, size = harness.stage(unit, workdir)
    assert size == (100, 50) and Path(path).parent == workdir
    out = cv2.imread(path, cv2.IMREAD_COLOR)
    assert out.shape[:2] == (50, 100)
    gray = out[..., 0] == 128
    assert int(gray.sum()) == 200
    assert gray[24, 48] and gray[33, 67] and not gray[23, 48] and not gray[34, 48]
    assert not gray[24, 47] and not gray[24, 68]


def test_corner_reads_get_the_staged_corners_and_pitch(monkeypatch, tmp_path):
    # Canvas 320 x 320 capped at 160: staged 160 x 160, factor 0.5. Truth corners
    # (40, 40) .. (280, 280) become (20, 20) .. (140, 140): edges 120 px over 6 squares,
    # pitch 120 / 6 = 20 px, so 4 px is 4 / 20 = 0.2 of a square (the canvas pitch, 40 px,
    # would give 0.1).
    source = tmp_path / "q.png"
    assert cv2.imwrite(str(source), np.full((320, 320, 3), 200, dtype=np.uint8))
    calls = []

    def fake_auto(path, size, corners=None, fabrics=None):
        calls.append((tuple(size), corners, fabrics))
        return _fake_reading(received={"fabrics": fabrics})

    monkeypatch.setattr(readers, "read_auto", fake_auto)
    counts = Counts(blocks_across=1, blocks_down=1, squares_per_block_across=6, squares_per_block_down=6)
    unit = _plain_unit(source, canvas=(320, 320), cap=160, radii=(0, 4), counts=counts,
                       corners=[(40.0, 40.0), (280.0, 40.0), (280.0, 280.0), (40.0, 280.0)],
                       readers_=("auto-corners",))
    rows = harness.run_unit(unit)
    assert calls[0] == ((160, 160), [(20.0, 20.0), (140.0, 20.0), (140.0, 140.0), (20.0, 140.0)], 2)
    assert {r["radius_px"]: r["radius_squares"] for r in rows} == {0: 0.0, 4: pytest.approx(0.2)}
    # The staged corners lie 20 px from every edge, more than 4, so each moves the full
    # 4 px: realized 4 / 20 = 0.2 squares, and 0 at radius 0.
    assert {r["radius_px"]: r["moved_squares"] for r in rows} == {0: 0.0, 4: pytest.approx(0.2)}


def _capture_units(monkeypatch, argv, runner=_outside_git):
    """main's units, with no read: _run records them and returns no rows."""
    units = []

    def record(us, workers):
        units.extend(us)
        return []

    monkeypatch.setattr(run_eval, "_run", record)
    assert run_eval.main(argv, runner=runner) == 0
    return units


def _corpus_argv(root, cache, tmp_path, *extra):
    return ["--corpus", str(root), "--cache", str(cache), "--out", str(tmp_path / "out" / "r"), *extra]


def test_private_staging_goes_beside_the_cache(monkeypatch, tmp_path):
    root, cache = _write_corpus(tmp_path)
    units = _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path, "--no-photoreal", "--private"))
    assert units and {u.workdir_root for u in units} == {str(cache.resolve().parent)}
    units = _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path, "--no-photoreal"))
    assert {u.workdir_root for u in units} == {None}


def test_stress_units_need_a_cc0_tier_a_photo_and_run_at_each_resolution(monkeypatch, tmp_path):
    root, cache = _write_corpus(tmp_path / "cc0")
    units = _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path, "--no-photoreal",
                                                     "--resolutions", "full,phone-1400"))
    stress = [u for u in units if u.group == "stress"]
    # a-dev is CC0-1.0 tier A with corners: one unit per degradation (6) at each of the 2
    # requested resolutions (caps None and 1400), true corners only: 12. r-dev is tier R:
    # none.
    names = [d.name for d in degrade.DEGRADATIONS]
    assert [(u.resolution, u.condition) for u in stress] == [("full", n) for n in names] + [
        ("phone-1400", n) for n in names]
    assert {(u.photo, u.cap, u.radii) for u in stress} == {("a-dev", None, (0,)), ("a-dev", 1400, (0,))}
    # The same photo licensed PDM-1.0 gets no stress unit, nor as a tier B photo (still
    # CC0-1.0, still framed), nor with --no-degradations.
    root, cache = _write_corpus(tmp_path / "pdm", overrides={"a-dev": {"license": "PDM-1.0"}})
    units = _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path, "--no-photoreal"))
    assert not [u for u in units if u.group == "stress"]
    root, cache = _write_corpus(tmp_path / "tier-b", overrides={"a-dev": {"tier": "B"}})
    units = _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path, "--no-photoreal"))
    assert {u.photo for u in units} == {"a-dev", "r-dev"} and not [u for u in units if u.group == "stress"]
    root, cache = _write_corpus(tmp_path / "off")
    units = _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path, "--no-photoreal", "--no-degradations"))
    assert not [u for u in units if u.group == "stress"]


def test_units_follow_the_resolutions_radii_and_readers(monkeypatch, tmp_path):
    root, cache = _write_corpus(tmp_path)
    units = _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path, "--no-photoreal", "--no-degradations",
                                                     "--resolutions", "full,phone-1400", "--radii", "0,2.5,4"))
    # 2 dev photos x 2 resolutions, caps None and 1400 (corpus.RESOLUTIONS).
    assert [(u.photo, u.resolution, u.cap) for u in units] == [
        ("a-dev", "full", None), ("a-dev", "phone-1400", 1400), ("r-dev", "full", None), ("r-dev", "phone-1400", 1400)]
    # Radii as given, whole numbers as int and 2.5 as float; default readers auto and auto-corners.
    assert units[0].radii == (0, 2.5, 4) and [type(r) for r in units[0].radii] == [int, float, int]
    assert units[0].readers == ("auto", "auto-corners")
    # The truth label follows each photo's tier: proposals only, so provisional.
    assert {u.truth_label for u in units} == {"provisional"}
    # An unknown resolution stops the run before anything loads.
    with pytest.raises(SystemExit):
        run_eval.main(_corpus_argv(root, cache, tmp_path, "--resolutions", "full,tablet"), runner=_outside_git)


def test_photoreal_units_join_the_dev_split_only(monkeypatch, tmp_path):
    root, cache = _write_corpus(tmp_path)
    named = [u for u in _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path)) if u.group == "named"]
    # 2 fixtures x 2 caps = 4 named units in a dev run.
    assert len(named) == 4
    assert not [u for u in _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path, "--holdout"))
                if u.group == "named"]
    assert not [u for u in _capture_units(monkeypatch, _corpus_argv(root, cache, tmp_path, "--no-photoreal"))
                if u.group == "named"]


def test_the_start_sha_check_requires_this_trees_qrep(monkeypatch, tmp_path):
    import qrep

    def clean(args, **kwargs):
        return _Done(0)

    # qrep imported from outside REPO: refused.
    monkeypatch.setattr(run_eval, "REPO", tmp_path)
    with pytest.raises(SystemExit) as stop:
        run_eval._start_sha_check("abc123", clean)
    assert "outside" in str(stop.value.code)
    # REPO set to the folder that holds the imported qrep: both diffs and the location pass.
    monkeypatch.setattr(run_eval, "REPO", Path(qrep.__file__).resolve().parents[1])
    text = run_eval._start_sha_check("abc123", clean)
    assert text.count("exited 0") == 2 and text.endswith("inside the repo")


def _proposals(counts_a, counts_b, class_a="squares", class_b="squares", *, both=True):
    def counts(n):
        return {"blocks_across": 1, "blocks_down": 1, "squares_per_block_across": n, "squares_per_block_down": n}

    doc = {"schema_version": 1, "photo": "private/cache/x.jpg", "sha256": "1" * 64, "canvas": [400, 300],
           "counts": [{"provenance": "proposed-a", "value": counts(counts_a)}],
           "construction_class": [{"provenance": "proposed-a", "value": class_a}]}
    if both:
        doc["counts"].append({"provenance": "proposed-b", "value": counts(counts_b)})
        doc["construction_class"].append({"provenance": "proposed-b", "value": class_b})
    return an.Annotation.model_validate_json(json.dumps(doc))


def test_proposals_agree_compares_the_two_proposals_field_by_field():
    assert run_eval._proposals_agree(_proposals(4, 4)) == {"counts": True, "construction_class": True}
    assert run_eval._proposals_agree(_proposals(4, 5, "squares", "hst")) == {
        "counts": False, "construction_class": False}
    # One proposal alone has nothing to agree with.
    assert run_eval._proposals_agree(_proposals(4, 4, both=False)) == {}


def test_run_unit_stages_under_its_workdir_root(monkeypatch, tmp_path):
    # A capped image must be written: the PNG lands in a qrep-eval-* folder under
    # workdir_root, never in the shared temp.
    source = tmp_path / "q.png"
    assert cv2.imwrite(str(source), np.full((320, 320, 3), 200, dtype=np.uint8))
    root = tmp_path / "staging-root"
    root.mkdir()
    written = []
    imwrite = cv2.imwrite

    def spy(path, image, *args):
        written.append(Path(path))
        return imwrite(path, image, *args)

    monkeypatch.setattr(harness.cv2, "imwrite", spy)
    monkeypatch.setattr(readers, "read_auto", lambda path, size, corners=None, fabrics=None: _fake_reading())
    unit = dataclasses.replace(_plain_unit(source, canvas=(320, 320), cap=160, counts=None, corners=None,
                                           readers_=("auto",)), workdir_root=str(root))
    harness.run_unit(unit)
    assert len(written) == 1
    assert written[0].parent.parent == root and written[0].parent.name.startswith("qrep-eval-")
    assert written[0].name == "q-cap-160-clean.png"


def test_the_realized_move_is_the_clamped_displacement_over_the_pitch(monkeypatch, tmp_path):
    # Corners on the edges of a 160 x 160 photo: (0, 0), (120, 0), (120, 120), (0, 120).
    # Edges 120 px over 6 squares: pitch 120 / 6 = 20 px. Each corner touches at least one
    # edge, so a 4 px move pointing off the photo is clamped short; over 10 seeded trials
    # at least one is (each draw stays whole for corner (0, 0) with chance 1/4 only).
    # Every row's realized move in squares is its mean moved px over 20.
    source = tmp_path / "q.png"
    assert cv2.imwrite(str(source), np.full((160, 160, 3), 200, dtype=np.uint8))
    monkeypatch.setattr(readers, "read_auto", lambda path, size, corners=None, fabrics=None: _fake_reading())
    counts = Counts(blocks_across=1, blocks_down=1, squares_per_block_across=6, squares_per_block_down=6)
    unit = dataclasses.replace(
        _plain_unit(source, canvas=(160, 160), radii=(4,), counts=counts,
                    corners=[(0.0, 0.0), (120.0, 0.0), (120.0, 120.0), (0.0, 120.0)], readers_=("auto-corners",)),
        trials=10)
    rows = harness.run_unit(unit)
    assert len(rows) == 10
    assert all(r["moved_squares"] == pytest.approx(r["moved_px_mean"] / 20.0) for r in rows)
    assert all(r["radius_squares"] == pytest.approx(4 / 20) for r in rows)
    assert any(r["moved_px_mean"] < 4.0 - 1e-9 for r in rows)


def test_only_as_fetched_units_above_50_mp_are_over_the_budget():
    # The budget is 50 MP, 50,000,000 pixels, on the as-fetched canvas
    # (#166 comment 6145839899). 10292 x 11415 = 117,483,180 and 13376 x 13029 =
    # 174,275,904 are above it; 5038 x 7721 = 38,898,398 is within. 10000 x 5000 =
    # 50,000,000 exactly is within (over means above); 10000 x 5001 = 50,010,000 is over.
    assert corpus.FULL_BUDGET_MP == 50
    assert corpus.over_budget((10292, 11415), None)
    assert corpus.over_budget((13376, 13029), None)
    assert not corpus.over_budget((5038, 7721), None)
    assert not corpus.over_budget((10000, 5000), None)
    assert corpus.over_budget((10000, 5001), None)
    # A capped unit is read at most cap px on its longest side, 2000 x 2000 = 4 MP at
    # most, so the 117.5 MP scan at either cap is within the budget.
    assert not corpus.over_budget((10292, 11415), 2000)
    assert not corpus.over_budget((10292, 11415), 1400)


def test_the_budget_judges_low_res_jpeg_at_the_size_it_reads():
    # low_res_jpeg hands the reader a copy at most 600 px on its longest side. For a
    # 10292 x 11415 canvas: scale 600 / 11415 = 0.0525624, 10292 x 0.0525624 = 540.97,
    # floor(540.97 + 0.5) = 541, and 11415 x 0.0525624 = 600: 541 x 600 = 324,600 px,
    # within 50,000,000, so that unit runs. Clean or glared, the reader gets all
    # 117,483,180 px, over. A capped unit is never over.
    assert degrade.read_size("low_res_jpeg", (10292, 11415)) == (541, 600)
    assert degrade.read_size("glare", (10292, 11415)) == (10292, 11415)

    def unit(condition, cap=None):
        return _plain_unit("never-opened.png", canvas=(10292, 11415), corners=None, counts=None,
                           readers_=("auto",), cap=cap, condition=condition)

    assert not harness.over_budget(unit("low_res_jpeg"))
    assert harness.over_budget(unit("clean")) and harness.over_budget(unit("glare"))
    assert not harness.over_budget(unit("clean", cap=2000))


def test_an_over_budget_unit_stands_in_rows_wherever_its_reads_would_be(monkeypatch, tmp_path):
    # A 10292 x 11415 canvas as fetched is over the budget: no stage, no read. Its rows
    # stand where run_unit would put reads, so every table lists it: auto's one read;
    # auto-corners and confirmed at radius 0 (1 trial) and 4 (trials = 1); and at 0 px
    # the confirmed reader's miscounts. Counts 1 block of 4 x 4: square +1 and -1 on each
    # axis (4), block +1 on each axis (2), half and double: 8 variants skipped over the
    # budget; block -1 on each axis leaves 0 blocks: 2 skipped for that reason.
    # Rows: 1 + 2 + (1 + 10 + 1) = 15.
    monkeypatch.setattr(readers, "read_auto", _no_read)
    monkeypatch.setattr(readers, "read_confirmed", _no_read)
    monkeypatch.setattr(harness, "stage", _no_read)
    corners = [(100.0, 100.0), (10192.0, 100.0), (10192.0, 11315.0), (100.0, 11315.0)]
    unit = _plain_unit(tmp_path / "never-opened.png", canvas=(10292, 11415), corners=corners,
                       counts=Counts(blocks_across=1, blocks_down=1, squares_per_block_across=4,
                                     squares_per_block_down=4),
                       readers_=("auto", "auto-corners", "confirmed"), radii=(0, 4))
    rows = harness.run_unit(unit)
    assert len(rows) == 15
    true = [r for r in rows if r["variant"] == "true"]
    assert [(r["reader"], r["radius_px"], r.get("trial")) for r in true] == [
        ("auto", None, None), ("auto-corners", 0, 0), ("auto-corners", 4, 0), ("confirmed", 0, 0),
        ("confirmed", 4, 0)]
    assert all(r["outcome"] == "skipped" and r["skip_kind"] == corpus.OVER_BUDGET
               and r["reason"] == corpus.over_budget_reason() for r in true)
    kinds = {r["variant"]: r.get("skip_kind") or r["reason"] for r in rows if r["variant"] != "true"}
    assert all(r["reader"] == "confirmed" and r["radius_px"] == 0 for r in rows if r["variant"] != "true")
    assert kinds == {**{f"square {s} {axis}": corpus.OVER_BUDGET for s in ("+1", "-1") for axis in ("across", "down")},
                     "block +1 across": corpus.OVER_BUDGET, "block +1 down": corpus.OVER_BUDGET,
                     "half": corpus.OVER_BUDGET, "double": corpus.OVER_BUDGET,
                     "block -1 across": "blocks_across would be 0", "block -1 down": "blocks_down would be 0"}
    # Truth dims 1 x 4 = 4 by 1 x 4 = 4; 1 x 1 = 1 block is not periodic (more than 1 is).
    assert all(r["truth_dims"] == [4, 4] and r["periodic"] is False for r in rows)
    # A second photo of 2 x 2 blocks of 2 x 2 squares: 2 x 2 = 4 blocks, periodic.
    periodic = dataclasses.replace(unit, photo="p", truth=dataclasses.replace(
        unit.truth, counts=Counts(blocks_across=2, blocks_down=2, squares_per_block_across=2,
                                  squares_per_block_down=2)))
    rows += harness.run_unit(periodic)
    agg = report.aggregate(rows, runner=_no_git)
    # Both photos stay in their tier at full: 2 photos, 2 skipped, no outcome, n = 0.
    tier = agg["by_tier"]["auto | A | full"]
    assert (tier["n_photos"], tier["skipped"], tier["errors"], tier["outcomes"]) == (2, 2, 0, {})
    assert (tier["false_warning"]["n"], tier["false_warning"]["over_budget"]) == (0, 2)
    # The 4 px jitter row lists both photos as skipped instead of dropping them.
    four = agg["jitter"]["auto-corners | full | 4"]["false_warning"]
    assert (four["n"], four["skipped"], four["over_budget"]) == (0, 2, 2)
    # R1 at full: q in the non-periodic split, p in the periodic one, each listed.
    r1 = agg["r1"]["by_resolution"]["full"]
    assert (r1["count_top1_periodic"]["n"], r1["count_top1_periodic"]["over_budget"]) == (0, 1)
    assert (r1["count_top1_non_periodic"]["n"], r1["count_top1_non_periodic"]["over_budget"]) == (0, 1)
    assert agg["errors"] == []


def test_an_unframed_photo_over_the_budget_keeps_its_no_frame_row(monkeypatch, tmp_path):
    # A refusal-tier photo with no frame or counts, 13376 x 13029 as fetched: auto would
    # get 174,275,904 px, over the budget, so its row is a budget skip. auto-corners has
    # nothing to confirm at any size, so its row keeps the no-frame reason, as it does
    # at 2000 px, and the G4 cell keeps the #243 note for it alone.
    monkeypatch.setattr(readers, "read_auto", _no_read)
    monkeypatch.setattr(harness, "stage", _no_read)
    truth = corpus.TruthView(corners=None, bands=[], counts=None, fabric_count=None,
                             construction="out_of_scope", provenance={"refusal_class": "verified-jake"})
    unit = harness.Unit(photo="r1", group="corpus", tier="R", split="dev", license="CC0-1.0",
                        device_class="museum scan", resolution="full", cap=None, condition="clean",
                        source=str(tmp_path / "never-opened.png"), canvas=(13376, 13029), truth=truth,
                        truth_label=truth.label_for("R"), readers=("auto", "auto-corners"), radii=(0, 4),
                        trials=1, seed="t")
    rows = harness.run_unit(unit)
    assert [(r["reader"], r["radius_px"], r["outcome"], r.get("skip_kind"), r["reason"]) for r in rows] == [
        ("auto", None, "skipped", corpus.OVER_BUDGET, corpus.over_budget_reason()),
        ("auto-corners", 0, "skipped", None, harness.SKIP_REASON)]
    text = report.markdown({"header": {"title": "t"}, "aggregate": report.aggregate(rows, runner=_no_git)})
    cells = {line.split("|")[1].strip(): line.split("|")[7].strip() for line in text.splitlines()
             if line.startswith(("| auto | museum scan | full | gate |", "| auto-corners | museum scan | full | gate |"))}
    assert cells == {"auto": "n = 0, 1 skipped (1 over the as-fetched budget)",
                     "auto-corners": "n = 0, 1 skipped; no frame or counts on the v0 refusal photos (#243)"}


def test_a_run_states_the_budget_and_skips_only_as_fetched_units_over_it(monkeypatch, tmp_path):
    # a-dev and r-dev are 160 x 160 = 25,600 px = 0.0256 MP. With the budget lowered to
    # 0.02 MP both are over it as fetched; low_res_jpeg leaves 160 px as it is (under
    # 600), so it is over too. The 1400 px cap leaves 160 px unscaled, and a capped unit
    # is never over. As fetched: clean units a-dev and r-dev (2), stress units a-dev's 6
    # degradations (6), all skipped. Budget rows: a-dev clean, auto plus auto-corners at
    # 0 and 4 px (3); each stress unit, auto plus auto-corners at 0 px (6 x 2 = 12);
    # r-dev clean, auto (1), while its auto-corners row keeps the no-frame reason:
    # 3 + 12 + 1 = 16.
    root, cache = _write_corpus(tmp_path)
    monkeypatch.setattr(corpus, "FULL_BUDGET_MP", 0.02)
    out = tmp_path / "out" / "r"
    args = ["--corpus", str(root), "--cache", str(cache), "--out", str(out), "--radii", "0,4",
            "--trials", "1", "--resolutions", "full,phone-1400", "--no-photoreal", "--workers", "1"]
    assert run_eval.main(args, runner=_fake_git) == 0
    payload = json.loads((out.parent / "r.json").read_text(encoding="utf-8"))
    budget = payload["header"]["full_resolution_budget"]
    assert budget.startswith("0.02 MP per as-fetched unit (corpus.FULL_BUDGET_MP")
    assert ("In this run: clean units 2 as fetched, 2 skipped; stress units 6 as fetched, 6 skipped; "
            "photos skipped: a-dev, r-dev; the largest image read as fetched: none.") in budget
    assert "6145827537" in budget and "6146146558" in budget
    rows = payload["rows"]
    over = [r for r in rows if r.get("skip_kind") == corpus.OVER_BUDGET]
    assert len(over) == 16 and {r["resolution"] for r in over} == {"full"}
    assert all(r["outcome"] == "skipped" for r in rows if r["resolution"] == "full")
    assert [r["reason"] for r in rows if r["photo"] == "r-dev" and r["reader"] == "auto-corners"
            and r["resolution"] == "full"] == [harness.SKIP_REASON]
    capped = [r for r in rows if r["resolution"] == "phone-1400"]
    assert not any(r.get("skip_kind") for r in capped)
    # At 1400 px: a-dev clean read by auto and by auto-corners at 0 and 4 px (3 rows), its
    # 6 degradations by both readers (12), r-dev by auto (1) and skipped by auto-corners,
    # which has no frame to confirm (1): 17 rows, 16 of them reads.
    assert len(capped) == 17 and sum(r["outcome"] != "skipped" for r in capped) == 16
    assert "- Full resolution budget: 0.02 MP per as-fetched unit" in (out.parent / "r.md").read_text(
        encoding="utf-8")
    # Back at 50 MP nothing here is over it, and the header names the largest image read
    # as fetched: both photos are 160 x 160 px, and a tie goes to the later name, r-dev.
    monkeypatch.setattr(corpus, "FULL_BUDGET_MP", 50)
    assert run_eval.main([*args[:5], str(tmp_path / "out" / "r2"), "--radii", "0", "--resolutions", "full",
                          "--no-degradations", "--no-photoreal", "--workers", "1"], runner=_fake_git) == 0
    budget = json.loads((tmp_path / "out" / "r2.json").read_text(encoding="utf-8"))["header"]["full_resolution_budget"]
    assert ("In this run: clean units 2 as fetched, 0 skipped; photos skipped: none; the largest image read "
            "as fetched: 160 x 160 px (r-dev).") in budget
