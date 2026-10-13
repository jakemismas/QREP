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

import cv2
import numpy as np
import pytest

import run_eval
from qrep.contract import Counts
from qrep_eval import annotation as an
from qrep_eval import corpus, degrade, readers, simulate

SQUARE = [(100.0, 100.0), (300.0, 100.0), (300.0, 200.0), (100.0, 200.0)]


def test_jitter_moves_every_corner_by_exactly_the_radius_and_repeats_under_a_seed():
    # Each corner moves r px in its own random direction: |delta| = r for r = 4.
    moved = simulate.jitter(SQUARE, 4.0, random.Random("seed-1"), bounds=(1000, 1000))
    for (x0, y0), (x1, y1) in zip(SQUARE, moved):
        assert math.hypot(x1 - x0, y1 - y0) == pytest.approx(4.0)
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
        # 2999 * 1400 / 3999 = 1049.86 -> 1050.
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


def _annotation(provenance: str, *, frame=True) -> an.Annotation:
    claim = {"provenance": provenance}
    doc = {
        "schema_version": 1,
        "photo": "private/cache/x.jpg",
        "sha256": "1" * 64,
        "canvas": [400, 300],
        "construction_class": [{**claim, "value": "squares"}],
    }
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


def test_blur_leaves_a_flat_image_flat():
    # A Gaussian blur of a constant image is the constant: 77 everywhere.
    out = degrade.gaussian_blur(np.full((20, 20, 3), 77, dtype=np.uint8))
    assert (out == 77).all()


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


def test_the_confirmed_reader_fails_closed_while_the_bridge_is_a_stub():
    # bridge.read_confirmed is a stub until B2b: the harness refuses to run it.
    reason = readers.confirmed_unavailable()
    assert reason is not None and "B2b" in reason
    with pytest.raises(SystemExit) as stop:
        run_eval.main(["--reader", "confirmed", "--out", "unused"])
    assert stop.value.code == 2


def test_the_auto_outcomes_cover_every_verdict():
    # no_grid is a refusal, non_square_repeat a hold (the old app's "squares uncertain"
    # warning), the two readable verdicts a read.
    from qrep.vision.verdict import VERDICTS

    assert set(readers.AUTO_OUTCOMES) == set(VERDICTS)
    assert readers.AUTO_OUTCOMES["no_grid"] == "refused"
    assert readers.AUTO_OUTCOMES["non_square_repeat"] == "held"


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


def _write_corpus(tmp_path):
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
        (cache / f"{stem}.png").write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        rows.append({"file": f"private/cache/{stem}.png", "license": "CC0-1.0", "sha256": sha,
                     "file_sha256": "", "px_w": "160", "px_h": "160", "tier": tier,
                     "class": "squares" if tier == "A" else "on_point", "capture": "museum_scan",
                     "eval_set": "v0"})
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


def test_a_run_reports_its_provenance_and_keeps_the_holdout_apart(tmp_path):
    root, cache = _write_corpus(tmp_path)
    out = tmp_path / "out" / "report"
    args = ["--corpus", str(root), "--cache", str(cache), "--out", str(out), "--radii", "0,4",
            "--trials", "1", "--resolutions", "full", "--no-degradations", "--no-photoreal",
            "--workers", "1"]
    assert run_eval.main(args) == 0
    report = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    header = report["header"]
    for key in ("date", "command", "qrep_path", "git_sha", "cv2_version", "decode_path", "split"):
        assert header[key], key
    assert header["split"] == "dev"
    # The dev split holds a-dev and r-dev; the holdout photo never appears.
    assert {row["photo"] for row in report["rows"]} == {"a-dev", "r-dev"}
    # Proposals only: every row is provisional and no row counts toward a gate.
    assert {row["truth"] for row in report["rows"]} == {"provisional"}
    # auto reads both photos; auto-corners reads only the photo with a frame, at 0 and 4 px.
    auto = [row for row in report["rows"] if row["reader"] == "auto"]
    corners = [row for row in report["rows"] if row["reader"] == "auto-corners"]
    assert len(auto) == 2 and {row["radius_px"] for row in corners} == {0, 4}
    # Every row records what the reader received (vision-13).
    assert all(row["received"]["staged_size"] == [160, 160] for row in report["rows"])
    assert out.with_suffix(".md").exists()
    # --holdout writes its own report holding only the holdout photo.
    assert run_eval.main([*args, "--holdout"]) == 0
    held = json.loads((out.parent / "report-holdout.json").read_text(encoding="utf-8"))
    assert held["header"]["split"] == "holdout"
    assert {row["photo"] for row in held["rows"]} == {"a-hold"}
