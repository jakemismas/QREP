"""Photoreal fixture determinism contract (sprint 3 S0, issue #66).

Fixtures are GENERATED ONCE and COMMITTED as PNGs under
tests/fixtures/photoreal/; these tests regenerate the pixel arrays in
memory and compare against the decoded committed files. Committed pixels
are canonical: a mismatch is a generator or environment drift bug, never a
reason to regenerate.

The one exception, per the plan's determinism spec: render_perspective_jpeg
passes through libjpeg, whose output is not stable across the three CI
OpenCV/Pillow builds. Its committed PNG is compared against the regenerated
NUMPY (pre-JPEG) stage within bounds that only JPEG quantization noise can
satisfy, plus an in-process encode determinism check.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

PHOTOREAL_DIR = Path(__file__).parent / "fixtures" / "photoreal"


def _load_generator():
    spec = importlib.util.spec_from_file_location(
        "photoreal_generator", PHOTOREAL_DIR / "generator.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GEN = _load_generator()

# the fifteen sprint 3 fixtures plus the seven sprint 4 S0 additions (three
# field-class composites and the four-fixture degraded tier)
PLAN_NAMES = [
    "render_on_white",
    "render_on_wood",
    "render_perspective_jpeg",
    "screenshot_composite",
    "tall_chrome",
    "edge_to_edge",
    "white_border_on_white",
    "lighting_gradient",
    "fabric_print",
    "seam_shadows",
    "hst_star",
    "drunkards_path",
    "busy_print_squares",
    "low_contrast_hst",
    "solid_fabric",
    # sprint 4 S0 (issue #92) field-class composites
    "antique_wash_chain",
    "quarter_circle_fine",
    "two_color_garbage",
    # sprint 4 S0 degraded tier (JPEG stage)
    "degraded_render_on_white",
    "degraded_drunkards_path",
    "degraded_hst_star",
    "degraded_busy_print",
]

BYTE_COMPARED = [n for n in PLAN_NAMES if n not in GEN.JPEG_FIXTURES]
ALL_CASES = [(n, cap) for n in PLAN_NAMES for cap in GEN.CAPS]


def test_registry_covers_every_plan_fixture():
    # the generator registry and the plan's named list must agree exactly
    assert sorted(GEN.FIXTURES) == sorted(PLAN_NAMES)
    assert GEN.CAPS == (1400, 2000)


@pytest.mark.parametrize("name,cap", ALL_CASES, ids=[f"{n}-{c}" for n, c in ALL_CASES])
def test_fixture_and_sidecar_committed(name, cap):
    assert GEN.fixture_path(name, cap).exists(), (
        f"{name}_{cap}.png is missing: run `python tests/fixtures/photoreal/generator.py write`"
        " once and commit the result"
    )
    assert GEN.sidecar_path(name, cap).exists()


@pytest.mark.parametrize(
    "name,cap",
    [(n, c) for n in BYTE_COMPARED for c in GEN.CAPS],
    ids=[f"{n}-{c}" for n in BYTE_COMPARED for c in GEN.CAPS],
)
def test_regenerated_pixels_match_committed(name, cap):
    image, side = GEN.generate(name, cap)
    committed = np.asarray(Image.open(GEN.fixture_path(name, cap)).convert("RGB"))
    assert committed.shape == image.shape
    assert np.array_equal(committed, image), (
        f"{name}_{cap}.png pixel drift: regenerated array differs from the committed file"
    )
    committed_side = json.loads(GEN.sidecar_path(name, cap).read_text(encoding="utf-8"))
    assert committed_side == json.loads(json.dumps(side))


JPEG_CASES = [(n, c) for n in sorted(GEN.JPEG_FIXTURES) for c in GEN.CAPS]


@pytest.mark.parametrize("name,cap", JPEG_CASES, ids=[f"{n}-{c}" for n, c in JPEG_CASES])
def test_jpeg_fixture_matches_prejpeg_within_quantization_bounds(name, cap):
    # bounds rationale (hand-chosen once, structural sanity only, NOT a
    # pipeline threshold): JPEG q55-82 with 4:2:0 subsampling perturbs smooth
    # regions by a few counts and block edges by tens (measured max 59 on the
    # sprint 4 degraded tier at q55); a regenerated scene that diverged for a
    # REAL reason (different rng stream, different geometry) would miss by
    # whole cell widths, not by quantization noise. One bound covers every
    # JPEG fixture, the sprint 3 perspective render and the sprint 4 tier.
    pre, side = GEN.prejpeg(name, cap)
    committed = np.asarray(Image.open(GEN.fixture_path(name, cap)).convert("RGB"))
    assert committed.shape == pre.shape
    diff = np.abs(committed.astype(np.int64) - pre.astype(np.int64))
    assert float(diff.mean()) < 3.0
    assert int(diff.max()) <= 96
    committed_side = json.loads(GEN.sidecar_path(name, cap).read_text(encoding="utf-8"))
    assert committed_side == json.loads(json.dumps(side))


@pytest.mark.parametrize("name", sorted(GEN.JPEG_FIXTURES))
def test_jpeg_encode_is_deterministic_in_process(name):
    # same-process re-encode yields identical pixels; cross-build variance
    # is the only exemption the determinism spec grants
    a, _ = GEN.generate(name, 1400)
    b, _ = GEN.generate(name, 1400)
    assert np.array_equal(a, b)


@pytest.mark.parametrize("name,cap", ALL_CASES, ids=[f"{n}-{c}" for n, c in ALL_CASES])
def test_sidecar_quad_inside_canvas_and_cap_respected(name, cap):
    side = json.loads(GEN.sidecar_path(name, cap).read_text(encoding="utf-8"))
    w, h = side["canvas"]
    assert max(w, h) == cap, "longest side must sit exactly at the staged cap"
    for x, y in side["quad"]:
        assert 0.0 <= x <= w and 0.0 <= y <= h
