"""Browser decode path tests for the eval (plan D4b).

Expected values are worked by hand in the comments from the app's targetSize
(web/src/model/downscale.ts: the longest side down to the cap, the other side
Math.round), canvas drawImage's stretch of the whole bitmap onto the whole canvas
(so a point maps by x * W'/W and y * H'/H), and the G9 rule (plan 7.2: native and
browser reads match on every square above the confidence threshold), never copied
from a run.
"""

import csv
import dataclasses
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

import run_eval
from qrep.contract import Counts
from qrep_eval import corpus, decode, harness, readers

VERSION = "140.0.7339.16"


def _job(tmp_path, *, canvas, cap, name="q", data=b"source bytes") -> decode.Job:
    source = tmp_path / f"{name}.jpg"
    source.write_bytes(data)
    return decode.Job(key=decode.job_key(name, "r"), source=str(source),
                      sha256=hashlib.sha256(data).hexdigest(), cap=cap, canvas=canvas)


def _decoded(tmp_path, job, size, *, as_browser="chromium", **override):
    """A PNG of size and the sidecar the browser driver writes for it."""
    png, side = decode.decoded_paths(tmp_path / "decoded", as_browser, job.key)
    png.parent.mkdir(parents=True, exist_ok=True)
    assert cv2.imwrite(str(png), np.full((size[1], size[0], 3), 90, dtype=np.uint8))
    longest = max(job.canvas)
    sidecar = {
        "version": decode.SIDECAR_VERSION, "key": job.key, "browser": as_browser, "browser_version": VERSION,
        "playwright_version": "1.61.1", "source_sha256": job.sha256, "cap": job.cap,
        "source_size": list(job.canvas), "decoded_size": list(size),
        "scale": job.cap / longest if job.cap is not None and longest > job.cap else 1.0,
        "factors": [size[0] / job.canvas[0], size[1] / job.canvas[1]],
        "steps": decode.STEPS, "png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
        "decoded_at": "2026-10-13T18:00:00Z", **override,
    }
    side.write_text(json.dumps(sidecar), encoding="utf-8")
    return png, sidecar


def test_corners_scale_by_the_recorded_factors_at_the_phone_cap():
    # targetSize(3000, 2000) at cap 1400: factor 1400 / 3000, width 1400, height
    # Math.round(2000 * 1400 / 3000) = Math.round(933.33) = 933. drawImage stretches the
    # whole bitmap onto 1400 x 933, so the factors are 1400 / 3000 = 0.46667 across and
    # 933 / 2000 = 0.4665 down, not the one cap factor on both axes.
    assert corpus.cap_size(3000, 2000, 1400) == (1400, 933)
    factors = decode.factors((3000, 2000), (1400, 933))
    assert factors == pytest.approx((1400 / 3000, 0.4665), abs=1e-12)
    # (1500, 1000): 1500 * 1400 / 3000 = 700.0 and 1000 * 0.4665 = 466.5. The far corner
    # (3000, 2000) lands on the canvas corner (1400, 933), and the origin stays put.
    scaled = decode.scale_points([(1500.0, 1000.0), (0.0, 0.0), (3000.0, 2000.0)], factors)
    assert scaled == [pytest.approx((700.0, 466.5), abs=1e-9), (0.0, 0.0),
                      pytest.approx((1400.0, 933.0), abs=1e-9)]


def test_corners_scale_on_a_portrait_photo_at_the_desktop_cap():
    # targetSize(2000, 3000) at cap 2000: factor 2000 / 3000, width Math.round(1333.33) =
    # 1333, height 2000. Factors 1333 / 2000 = 0.6665 across and 2000 / 3000 down.
    # (1000, 1500) -> (1000 * 0.6665, 1500 * 2000 / 3000) = (666.5, 1000.0); a
    # fractional corner (10.5, 20.25) -> (6.998250, 13.5).
    assert corpus.cap_size(2000, 3000, 2000) == (1333, 2000)
    factors = decode.factors((2000, 3000), (1333, 2000))
    assert decode.scale_points([(1000.0, 1500.0), (10.5, 20.25)], factors) == [
        pytest.approx((666.5, 1000.0), abs=1e-9), pytest.approx((6.99825, 13.5), abs=1e-9)]


def test_full_size_and_an_image_under_the_cap_keep_their_corners():
    # A 1200 x 800 photo under either cap, and any photo at full size, is drawn at its
    # own size: factors (1.0, 1.0), every corner unchanged.
    assert corpus.cap_size(1200, 800, 1400) == (1200, 800)
    for size in ((1200, 800), (5038, 7721)):
        factors = decode.factors(size, size)
        assert factors == (1.0, 1.0)
        assert decode.scale_points([(12.25, 700.5)], factors) == [(12.25, 700.5)]


def test_a_valid_sidecar_loads_and_yields_its_factors(tmp_path):
    job = _job(tmp_path, canvas=(3000, 2000), cap=1400)
    png, sidecar = _decoded(tmp_path, job, (1400, 933))
    loaded = decode.load_decoded(tmp_path / "decoded", "chromium", job)
    assert loaded.png == png and loaded.error is None
    assert loaded.size == (1400, 933)
    assert loaded.factors == pytest.approx((1400 / 3000, 933 / 2000), abs=1e-12)
    assert loaded.browser_version == VERSION


@pytest.mark.parametrize("override, message", [
    ({"source_sha256": "0" * 64}, "sha256"),
    ({"browser": "webkit"}, "browser"),
    ({"cap": 2000}, "cap"),
    # The browser saw another shape than the annotation's canvas, as an EXIF rotation would.
    ({"source_size": [2000, 3000]}, "source size"),
    # 934 is not Math.round(933.33); the PNG on disk is 933 tall too, so the size check speaks first.
    ({"decoded_size": [1400, 934]}, "targetSize"),
    ({"factors": [0.5, 0.5]}, "factors"),
    ({"png_sha256": "f" * 64}, "png"),
    ({"version": 0}, "version"),
    ({"key": "other__phone-1400"}, "answers job"),
    ({"steps": "createImageBitmap(blob); crop; drawImage"}, "decode steps"),
    # The cap's scale is 1400 / 3000 = 0.46667; 0.5 is another cap's.
    ({"scale": 0.5}, "scale"),
])
def test_a_sidecar_that_does_not_match_its_job_is_refused(tmp_path, override, message):
    job = _job(tmp_path, canvas=(3000, 2000), cap=1400)
    _decoded(tmp_path, job, (1400, 933), **override)
    with pytest.raises(ValueError, match=message):
        decode.load_decoded(tmp_path / "decoded", "chromium", job)


def test_a_png_of_another_size_than_its_sidecar_is_refused(tmp_path):
    # The sidecar claims 1400 x 933 (Math.round(933.33)), the PNG holds 1400 x 932.
    job = _job(tmp_path, canvas=(3000, 2000), cap=1400)
    png, sidecar = _decoded(tmp_path, job, (1400, 932), decoded_size=[1400, 933],
                            factors=[1400 / 3000, 933 / 2000])
    with pytest.raises(ValueError, match="PNG"):
        decode.load_decoded(tmp_path / "decoded", "chromium", job)


def test_a_missing_decode_stops_and_a_browser_failure_is_carried(tmp_path):
    job = _job(tmp_path, canvas=(3000, 2000), cap=1400)
    with pytest.raises(decode.DecodeMissing, match="run_decode"):
        decode.load_decoded(tmp_path / "decoded", "chromium", job)
    png, side = decode.decoded_paths(tmp_path / "decoded", "chromium", job.key)
    side.parent.mkdir(parents=True)
    side.write_text(json.dumps({"version": decode.SIDECAR_VERSION, "key": job.key, "browser": "chromium",
                                "browser_version": VERSION, "source_sha256": job.sha256, "cap": 1400,
                                "error": "canvas too large"}), encoding="utf-8")
    loaded = decode.load_decoded(tmp_path / "decoded", "chromium", job)
    assert loaded.error == "canvas too large" and loaded.png is None


def _unit(source, *, canvas, cap, resolution, condition="clean", corners=None, photo="q"):
    counts = Counts(blocks_across=1, blocks_down=1, squares_per_block_across=6, squares_per_block_down=6)
    truth = corpus.TruthView(corners=corners, bands=[], counts=counts if corners else None, fabric_count=2,
                             construction="squares", provenance={"fabrics": "hand-authored"})
    return harness.Unit(photo=photo, group="corpus" if condition == "clean" else "stress", tier="A",
                        split="dev", license="CC0-1.0", device_class="museum scan", resolution=resolution,
                        cap=cap, condition=condition, source=str(source), canvas=canvas, truth=truth,
                        truth_label="provisional", readers=("auto", "auto-corners"), radii=(0,), trials=1,
                        seed="d4b")


def test_jobs_cover_each_staged_image_once_and_skip_units_over_the_budget(tmp_path):
    source = tmp_path / "big.jpg"
    source.write_bytes(b"big")
    # 10000 x 6000 = 60 MP, over the 50 MP as-fetched budget: the clean full unit is never
    # staged, so it needs no decode. low_res_jpeg hands the read 600 x 360 px (longest
    # side 600), under the budget, so the full-size decode is still needed for it. The
    # phone-cap clean and glare units share one decode: degradations apply after it.
    units = [_unit(source, canvas=(10000, 6000), cap=None, resolution="full"),
             _unit(source, canvas=(10000, 6000), cap=None, resolution="full", condition="low_res_jpeg"),
             _unit(source, canvas=(10000, 6000), cap=1400, resolution="phone-1400"),
             _unit(source, canvas=(10000, 6000), cap=1400, resolution="phone-1400", condition="glare")]
    jobs = decode.jobs_for(units)
    assert [(j.key, j.cap) for j in jobs] == [(decode.job_key("q", "full"), None),
                                             (decode.job_key("q", "phone-1400"), 1400)]
    assert {j.sha256 for j in jobs} == {hashlib.sha256(b"big").hexdigest()}
    # Only clean units, the first over the budget: one job, the phone cap's.
    assert [j.key for j in decode.jobs_for([units[0], units[2]])] == [decode.job_key("q", "phone-1400")]


def test_browser_units_read_the_png_with_scaled_corners(tmp_path):
    source = tmp_path / "q.jpg"
    source.write_bytes(b"photo")
    # Canvas 3000 x 2000 at the phone cap: 1400 x 933 (first test). Corners (300, 200),
    # (2700, 200), (2700, 1800), (300, 1800) scale by 1400 / 3000 and 933 / 2000:
    # 300 -> 140.0, 2700 -> 1260.0, 200 -> 93.3, 1800 -> 839.7.
    corners = [(300.0, 200.0), (2700.0, 200.0), (2700.0, 1800.0), (300.0, 1800.0)]
    clean = _unit(source, canvas=(3000, 2000), cap=1400, resolution="phone-1400", corners=corners)
    stress = dataclasses.replace(clean, group="stress", condition="glare")
    job = decode.jobs_for([clean])[0]
    png, _ = _decoded(tmp_path, job, (1400, 933))
    # A full-size unit over the 50 MP budget (10000 x 6000 = 60 MP) is never staged, so it
    # passes through unchanged and needs no decode; dropping it would shrink n.
    over = _unit(source, canvas=(10000, 6000), cap=None, resolution="full", corners=corners, photo="big")
    units, errors, versions = decode.browser_units([clean, stress, over], tmp_path / "decoded", "chromium")
    assert errors == [] and versions == {VERSION}
    assert units[2] is over
    units = units[:2]
    for unit, original in zip(units, (clean, stress)):
        assert unit.source == str(png) and unit.canvas == (1400, 933) and unit.cap is None
        assert unit.condition == original.condition and unit.resolution == "phone-1400"
        assert unit.truth.corners == [pytest.approx(p, abs=1e-9) for p in
                                      [(140.0, 93.3), (1260.0, 93.3), (1260.0, 839.7), (140.0, 839.7)]]
        assert unit.truth.counts == original.truth.counts
    # The original unit keeps its own corners: the swap copies.
    assert clean.truth.corners == corners


def test_browser_units_turn_a_browser_failure_into_error_rows(tmp_path):
    source = tmp_path / "q.jpg"
    source.write_bytes(b"photo")
    corners = [(300.0, 200.0), (2700.0, 200.0), (2700.0, 1800.0), (300.0, 1800.0)]
    unit = _unit(source, canvas=(3000, 2000), cap=1400, resolution="phone-1400", corners=corners)
    job = decode.jobs_for([unit])[0]
    _, side = decode.decoded_paths(tmp_path / "decoded", "webkit", job.key)
    side.parent.mkdir(parents=True)
    side.write_text(json.dumps({"version": decode.SIDECAR_VERSION, "key": job.key, "browser": "webkit",
                                "browser_version": "26.0", "source_sha256": job.sha256, "cap": 1400,
                                "error": "Target crashed"}), encoding="utf-8")
    units, errors, _ = decode.browser_units([unit], tmp_path / "decoded", "webkit")
    # No unit is left to read; auto's read and auto-corners' 0 px trial each get an error
    # row, as a stage error would give them (harness._unread_rows): 2 rows.
    assert units == []
    assert [(r["reader"], r["outcome"]) for r in errors] == [("auto", "error"), ("auto-corners", "error")]
    assert all("webkit could not decode" in r["error"] and "Target crashed" in r["error"] for r in errors)


def test_pixel_diff_counts_pixels_and_the_largest_channel_difference():
    # Two 2 x 2 BGR images. Pixel (0, 0) differs by 3 in one channel; pixel (1, 1) by 7
    # and 2 in two channels; pixel (0, 1) by 245 = |5 - 250|, where uint8 a - b would wrap
    # to (5 - 250) mod 256 = 11. Differing pixels: 3 of 4; largest channel difference: 245.
    a = np.zeros((2, 2, 3), dtype=np.uint8)
    b = a.copy()
    b[0, 0, 1] = 3
    b[1, 1, 0], b[1, 1, 2] = 7, 2
    a[0, 1, 2], b[0, 1, 2] = 5, 250
    assert decode.pixel_diff(a, b) == {"pixels": 4, "differing": 3, "largest": 245}
    assert decode.pixel_diff(a, a) == {"pixels": 4, "differing": 0, "largest": 0}
    with pytest.raises(ValueError, match="shape"):
        decode.pixel_diff(a, np.zeros((2, 3, 3), dtype=np.uint8))


def test_pixel_diff_bands_give_the_same_counts_as_one_pass():
    # 1030 rows cross the 512-row bands twice. Rows 0, 511, 512 and 1029 get one pixel
    # off by 2, 9, 1 and 4: 4 differing pixels, largest 9, which sits in the first band so
    # a later band cannot overwrite it.
    a = np.full((1030, 3, 3), 100, dtype=np.uint8)
    b = a.copy()
    for value, row in zip((2, 9, 1, 4), (0, 511, 512, 1029)):
        b[row, 1, 0] = 100 + value
    assert decode.pixel_diff(a, b) == {"pixels": 3090, "differing": 4, "largest": 9}


def _reading(cells, confidence, *, colors=("#ff0000", "#0000ff"), outcome="read", threshold=0.9):
    return readers.Reading(outcome=outcome, verdict=None, rows=len(cells) if cells else 0,
                           cols=len(cells[0]) if cells else 0, colors=list(colors), cells=cells,
                           confidence=confidence, cell_size_eighths=16, band_eighths=[],
                           low_confidence_below=threshold, flagged_regions=[], seconds=0.0, received={})


def test_label_diff_maps_the_palettes_before_comparing():
    # The browser read lists the same two fabrics in the other order, so its labels are
    # swapped: mapped through the palettes (red to red, blue to blue) every square agrees.
    native = _reading([[0, 1], [1, 0]], [[1.0, 1.0], [1.0, 1.0]])
    browser = _reading([[1, 0], [0, 1]], [[1.0, 1.0], [1.0, 1.0]], colors=("#0000ff", "#ff0000"))
    out = decode.label_diff(native, browser)
    assert (out["squares"], out["differing"], out["differing_confident"], out["g9"]) == (4, 0, 0, True)
    # A three-fabric cycle tells the mapping's direction apart (a two-fabric swap is its
    # own inverse). Native red 0, blue 1, green 2; browser blue 0, green 1, red 2. Browser
    # cells [2, 0, 1] are red, blue, green, so mapped browser to native they read [0, 1, 2],
    # the native cells: 0 differing. Mapped the other way they would read [1, 2, 0]: 3.
    cycle = decode.label_diff(_reading([[0, 1, 2]], [[1.0] * 3], colors=("#ff0000", "#0000ff", "#00ff00")),
                              _reading([[2, 0, 1]], [[1.0] * 3], colors=("#0000ff", "#00ff00", "#ff0000")))
    assert (cycle["differing"], cycle["g9"]) == (0, True)
    # The browser read finds two fabrics where native found three (k 2 against 3): browser
    # red 0, blue 1 map to native 0, 1; the native green square (0, 2) is read red, so 1 differs.
    fewer = decode.label_diff(_reading([[0, 1, 2]], [[1.0] * 3], colors=("#ff0000", "#0000ff", "#00ff00")),
                              _reading([[0, 1, 0]], [[1.0] * 3]))
    assert (fewer["differing"], fewer["g9"], fewer["k"]) == (1, False, [3, 2])
    # Two close blues, each a shade off in the browser (as a colour-profile conversion
    # leaves them). By colour alone browser #3d5d89 sits nearer native #3e5e88 and
    # #3b5b8b nearer #3a5a8c, which would cross the pair and make all 6 squares differ.
    # The cells are identical, so browser fabric 0 shares 3 squares with native 0 and
    # none with native 1, and likewise 1 with 1: paired by shared squares, 0 differ.
    cells = [[0, 1, 0], [1, 0, 1]]
    close = decode.label_diff(_reading(cells, [[1.0] * 3] * 2, colors=("#3a5a8c", "#3e5e88")),
                              _reading(cells, [[1.0] * 3] * 2, colors=("#3d5d89", "#3b5b8b")))
    assert (close["differing"], close["g9"]) == (0, True)
    assert decode.pair_fabrics(cells, cells, ["#3a5a8c", "#3e5e88"], ["#3d5d89", "#3b5b8b"]) == [0, 1]


def test_label_diff_applies_the_g9_rule_to_squares_above_the_threshold():
    # One square, (0, 1), changes from blue (1) to red (0). Threshold 0.9: a square is
    # above it at 0.9 or more in either read, since either read would show it unflagged.
    native = _reading([[0, 1], [1, 0]], [[1.0, 0.95], [1.0, 1.0]])
    browser = _reading([[0, 0], [1, 0]], [[1.0, 0.95], [1.0, 1.0]])
    out = decode.label_diff(native, browser)
    # 0.95 >= 0.9 in both: 1 differing square, confident, G9 fails.
    assert (out["differing"], out["differing_confident"], out["g9"]) == (1, 1, False)
    # At 0.5 in both reads the square is flagged in both: reported, outside G9.
    low = [[1.0, 0.5], [1.0, 1.0]]
    out = decode.label_diff(_reading(native.cells, low), _reading(browser.cells, low))
    assert (out["differing"], out["differing_confident"], out["g9"]) == (1, 0, True)
    # Flagged in the browser read only (0.5) but 0.95 natively: above the threshold in one
    # read, so it counts and G9 fails.
    out = decode.label_diff(_reading(native.cells, [[1.0, 0.95], [1.0, 1.0]]), _reading(browser.cells, low))
    assert (out["differing_confident"], out["differing_confident_both"], out["g9"]) == (1, 0, False)
    # Exactly 0.9 in both reads is at the threshold, not below it: the app flags only
    # below (web/src/state/photo.tsx, value < UNCERTAIN_THRESHOLD), so it counts.
    edge = [[1.0, 0.9], [1.0, 1.0]]
    out = decode.label_diff(_reading(native.cells, edge), _reading(browser.cells, edge))
    assert (out["differing_confident"], out["g9"]) == (1, False)
    # A read with no confidences flags nothing, so every square is above the threshold.
    out = decode.label_diff(_reading(native.cells, None), _reading(browser.cells, low))
    assert (out["differing_confident"], out["g9"]) == (1, False)


def test_label_diff_fails_g9_on_another_outcome_or_grid_and_passes_two_refusals():
    shipped = _reading([[0, 1], [1, 0]], [[1.0] * 2] * 2)
    refused = _reading(None, None, outcome="refused")
    out = decode.label_diff(shipped, refused)
    assert (out["match"], out["g9"]) == ("outcome", False)
    # Neither read shows a pattern: no square to compare, nothing differs.
    out = decode.label_diff(refused, refused)
    assert (out["match"], out["g9"], out["squares"]) == ("nothing shown", True, 0)
    # A 2 x 3 grid against a 2 x 2 grid locates no square of the other.
    wider = _reading([[0, 1, 0], [1, 0, 1]], [[1.0] * 3] * 2)
    out = decode.label_diff(shipped, wider)
    assert (out["match"], out["g9"]) == ("dims", False)
    # A browser fabric with no native partner (k 3 against 2) maps to none, so its square differs.
    three = _reading([[0, 1], [1, 2]], [[1.0] * 2] * 2, colors=("#ff0000", "#0000ff", "#00ff00"))
    out = decode.label_diff(shipped, three)
    assert (out["differing"], out["g9"], out["k"]) == (1, False, [2, 3])


def _split_png(width, height, split="dev"):
    """A flat image whose sha256 lands in split."""
    for value in range(256):
        ok, data = cv2.imencode(".png", np.full((height, width, 3), value, dtype=np.uint8))
        if corpus.split_of(hashlib.sha256(data.tobytes()).hexdigest()) == split:
            return data.tobytes()
    raise AssertionError(f"no flat image landed in the {split} split")


def _corpus(tmp_path, width=2800, height=1400, stem="a-dev", split="dev"):
    root, cache = tmp_path / "corpus", tmp_path / "cache"
    (root / "annotations").mkdir(parents=True)
    cache.mkdir()
    data = _split_png(width, height, split)
    sha = hashlib.sha256(data).hexdigest()
    (cache / f"{stem}.png").write_bytes(data)
    claim = {"provenance": "proposed-a"}
    doc = {"schema_version": 1, "photo": f"private/cache/{stem}.png", "sha256": sha, "canvas": [width, height],
           "capture": [{"provenance": "screened", "value": "museum_scan"}],
           "construction_class": [{**claim, "value": "squares"}],
           "frame": [{**claim, "value": {"outer_edge": {"kind": "outer_edge", "bands": [], "corners": {
               "top_left": {"x": 400.0, "y": 200.0}, "top_right": {"x": 2400.0, "y": 200.0},
               "bottom_right": {"x": 2400.0, "y": 1200.0}, "bottom_left": {"x": 400.0, "y": 1200.0}}}}}],
           "counts": [{**claim, "value": {"blocks_across": 1, "blocks_down": 1,
                                          "squares_per_block_across": 6, "squares_per_block_down": 6}}],
           "fabrics": [{**claim, "value": {"count": 2}}]}
    (root / "annotations" / f"{stem}.json").write_text(json.dumps(doc), encoding="utf-8")
    with (root / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "license", "sha256", "file_sha256", "px_w", "px_h",
                                                    "tier", "class", "capture", "eval_set"])
        writer.writeheader()
        writer.writerow({"file": f"private/cache/{stem}.png", "license": "CC0-1.0", "sha256": sha, "file_sha256": "",
                         "px_w": str(width), "px_h": str(height), "tier": "A", "class": "squares",
                         "capture": "museum_scan", "eval_set": "v0"})
    return root, cache


class _Done:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def _outside_git(args, **kwargs):
    return _Done(128, "", "fatal: not a git repository (or any of the parent directories): .git")


def test_run_eval_decode_reads_the_browser_pngs_with_scaled_corners(monkeypatch, tmp_path):
    root, cache = _corpus(tmp_path)
    # Canvas 2800 x 1400. Phone cap: factor 1400 / 2800 = 0.5, 1400 x 700, corners
    # (400, 200)..(2400, 1200) -> (200, 100)..(1200, 600). Desktop cap: factor 2000 /
    # 2800, width 2000, height Math.round(1400 * 2000 / 2800) = Math.round(1000.0) = 1000;
    # 400 -> 400 * 2000 / 2800 = 285.714, 2400 -> 1714.286, 200 -> 200 * 1000 / 1400 =
    # 142.857, 1200 -> 857.143.
    sizes = {"phone-1400": (1400, 700), "desktop-2000": (2000, 1000)}
    units = [u for u in run_eval._corpus_units(
        run_eval._parse(["--out", "x", "--no-degradations", "--resolutions", "phone-1400,desktop-2000"]),
        corpus.load_photos(root, cache, split="dev"), ("auto", "auto-corners"), (0,))]
    for job in decode.jobs_for(units):
        _decoded(cache, job, sizes[job.key.split("__")[1]])
    calls = []

    def fake_auto(path, size, corners=None, fabrics=None):
        calls.append((Path(path).parent.name, tuple(size), corners and [tuple(p) for p in corners]))
        return readers.Reading(outcome="refused", verdict="no_grid", rows=0, cols=0, colors=[], cells=None,
                               confidence=None, cell_size_eighths=None, band_eighths=[],
                               low_confidence_below=0.9, flagged_regions=[], seconds=0.0, received={})

    monkeypatch.setattr(readers, "read_auto", fake_auto)
    out = tmp_path / "out" / "r"
    argv = ["--corpus", str(root), "--cache", str(cache), "--out", str(out), "--radii", "0", "--trials", "1",
            "--resolutions", "phone-1400,desktop-2000", "--no-degradations", "--no-photoreal",
            "--decode", "chromium"]
    assert run_eval.main(argv, runner=_outside_git) == 0
    # Each clean unit is the decoded PNG itself, read as its own file in the chromium folder.
    # Ordered by size, then the corner-free auto read before auto-corners.
    order = lambda call: (call[1], call[2] is not None)  # noqa: E731
    assert sorted(calls, key=order) == sorted([
        ("chromium", (1400, 700), None),
        ("chromium", (1400, 700), [(200.0, 100.0), (1200.0, 100.0), (1200.0, 600.0), (200.0, 600.0)]),
        ("chromium", (2000, 1000), None),
        ("chromium", (2000, 1000), [pytest.approx(p, abs=1e-9) for p in
                                    [(2000 / 7, 1000 / 7), (12000 / 7, 1000 / 7),
                                     (12000 / 7, 6000 / 7), (2000 / 7, 6000 / 7)]]),
    ], key=order)
    header = json.loads(out.with_name("r.json").read_text(encoding="utf-8"))["header"]
    assert header["decode_path"].startswith(f"browser: chromium {VERSION}")
    # Native stays the default, and its header keeps the native text.
    calls.clear()
    assert run_eval.main([*argv[:-2], "--out", str(out) + "-native"], runner=_outside_git) == 0
    assert len(calls) == 4 and "chromium" not in {c[0] for c in calls}
    native = json.loads(out.with_name("r-native.json").read_text(encoding="utf-8"))["header"]
    assert native["decode_path"] == harness.DECODE_PATH


def test_run_eval_decode_stops_when_a_png_was_never_decoded(tmp_path):
    root, cache = _corpus(tmp_path)
    argv = ["--corpus", str(root), "--cache", str(cache), "--out", str(tmp_path / "out" / "r"), "--radii", "0",
            "--resolutions", "phone-1400", "--no-degradations", "--no-photoreal", "--decode", "webkit"]
    with pytest.raises(SystemExit, match="run_decode"):
        run_eval.main(argv, runner=_outside_git)


def test_parity_pairs_route_skips_errors_and_reads(monkeypatch):
    # One unit read by auto and auto-corners. Native and chromium: auto refuses in both
    # (nothing shown, G9 holds); auto-corners has no frame in either (skipped). WebKit:
    # auto errors, so its pair is an error, not a comparison.
    monkeypatch.syspath_prepend(str(Path(run_eval.__file__).parent / "decode"))
    import run_parity

    unit = _unit(Path("q.jpg"), canvas=(100, 100), cap=None, resolution="phone-1400")
    refused = {"outcome": "refused", "verdict": "no_grid", "rows": 0, "cols": 0, "colors": [], "cells": None,
               "confidence": None, "low_confidence_below": 0.9, "seconds": 1.0}
    skip = {"reader": "auto-corners", "skipped": harness.SKIP_REASON}
    reads = {("q", "phone-1400", "native"): [{"reader": "auto", **refused}, skip],
             ("q", "phone-1400", "chromium"): [{"reader": "auto", **refused}, skip],
             ("q", "phone-1400", "webkit"): [{"reader": "auto", "error": "RuntimeError('x')"}, skip]}
    rows = run_parity.compare([unit], reads)
    got = [(r["browser"], r["reader"], r["status"], r.get("match"), r.get("g9")) for r in rows]
    assert got == [("chromium", "auto", "compared", "nothing shown", True),
                   ("chromium", "auto-corners", "skipped", None, None),
                   ("webkit", "auto", "error", None, None),
                   ("webkit", "auto-corners", "skipped", None, None)]


def test_run_decode_opens_the_holdout_only_when_asked(monkeypatch, tmp_path):
    # A corpus whose one photo lands in the holdout split. By default the job list is the
    # dev split's: no corpus photo, only the photoreal fixtures (2 fixtures at 2 sizes).
    # With --holdout it is that photo at the phone cap, and no fixture, as run_eval reads
    # fixtures on the dev split only.
    monkeypatch.syspath_prepend(str(Path(run_eval.__file__).parent / "decode"))
    import run_decode

    root, cache = _corpus(tmp_path, stem="a-hold", split="holdout")
    base = ["--corpus", str(root), "--cache", str(cache), "--port", "4999", "--resolutions", "phone-1400",
            "--no-degradations"]
    dev = run_decode.units_for(run_decode._parse(base), cache)
    assert sorted({u.photo for u in dev}) == ["busy_print_squares", "low_contrast_hst"]
    held = run_decode.units_for(run_decode._parse([*base, "--holdout"]), cache)
    assert [(u.photo, u.split, u.cap) for u in held] == [("a-hold", "holdout", 1400)]
