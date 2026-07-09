"""S1 tiered background-agnostic detection (sprint 3, issue #67).

CONTRACT LITERALS (frozen in the plan and issue body, never edited):
- Detected-quad IoU >= 0.95 vs the sidecar ground truth on render_on_white,
  render_on_wood, screenshot_composite, tall_chrome, edge_to_edge.
- white_border_on_white and lighting_gradient: correct quad (IoU >= 0.95)
  OR a LOW-confidence quad; the low bound is hand-picked ONCE here, before
  implementation: confidence <= 0.5. Never a confident wrong answer.

Byte-identity of the legacy tier with the S0 pin is proven separately by
test_legacy_regression.py; this file proves routing and the generalized
tiers. Ground truth comes from the committed photoreal sidecars; nothing
here reads pipeline output into an expectation.
"""

import json
import tempfile
from pathlib import Path

import cv2
import pytest

from qrep.vision.metrics import quad_iou
from qrep.vision.rectify import rectify

PHOTOREAL = Path(__file__).parent / "fixtures" / "photoreal"

IOU_MIN = 0.95  # frozen contract literal (plan S1)
LOW_CONFIDENCE_BOUND = 0.5  # frozen at write time for the never-confident-wrong pair

IOU_FIXTURES = [
    "render_on_white",
    "render_on_wood",
    "screenshot_composite",
    "tall_chrome",
    "edge_to_edge",
]
NEVER_CONFIDENT_WRONG = ["white_border_on_white", "lighting_gradient"]
CAPS = (1400, 2000)


def _load(name: str, cap: int):
    image = cv2.imread(str(PHOTOREAL / f"{name}_{cap}.png"))
    assert image is not None
    side = json.loads((PHOTOREAL / f"{name}_{cap}.json").read_text(encoding="utf-8"))
    return image, [tuple(p) for p in side["quad"]]


@pytest.mark.parametrize(
    "name,cap",
    [(n, c) for n in IOU_FIXTURES for c in CAPS],
    ids=[f"{n}-{c}" for n in IOU_FIXTURES for c in CAPS],
)
def test_detected_quad_iou(name, cap):
    image, truth = _load(name, cap)
    result = rectify(image)
    iou = quad_iou([tuple(p) for p in result.corners], truth)
    assert iou >= IOU_MIN, f"{name}_{cap}: detected-quad IoU {iou:.3f} < {IOU_MIN}"


@pytest.mark.parametrize(
    "name,cap",
    [(n, c) for n in NEVER_CONFIDENT_WRONG for c in CAPS],
    ids=[f"{n}-{c}" for n in NEVER_CONFIDENT_WRONG for c in CAPS],
)
def test_never_a_confident_wrong_quad(name, cap):
    image, truth = _load(name, cap)
    result = rectify(image)
    iou = quad_iou([tuple(p) for p in result.corners], truth)
    assert iou >= IOU_MIN or result.confidence <= LOW_CONFIDENCE_BOUND, (
        f"{name}_{cap}: wrong quad (IoU {iou:.3f}) at confidence "
        f"{result.confidence:.3f} > {LOW_CONFIDENCE_BOUND}"
    )


# ---------------------------------------------------------------------------
# routing
# ---------------------------------------------------------------------------


def _seed42_render(level: int, tmp: str) -> Path:
    from qrep.model import load
    from qrep.render import save_render

    truth = load(Path(__file__).parent / "fixtures" / "double_irish_chain.json")
    png, _ = save_render(truth, Path(tmp) / f"l{level}.png", level=level, seed=42)
    return png


@pytest.mark.parametrize("level", [0, 1, 2])
def test_legacy_tier_routes_renderer_backgrounds(level):
    # exact #404040 margins must take tier 0, the byte-stable legacy branch
    with tempfile.TemporaryDirectory() as tmp:
        image = cv2.imread(str(_seed42_render(level, tmp)))
        result = rectify(image)
    assert result.tier == 0


def test_l3_routing_pinned():
    # L3 clutter rectangles sit inside the border strips by construction;
    # the pooled strip MEDIAN stays #404040 (clutter covers a minority of
    # strip pixels), so L3 routes to tier 0 - pinned here per the contract,
    # stated in the issue body. Detection quality itself is pinned by the
    # S0 baseline (IoU 0.999); assert it survives the tiering unharmed.
    with tempfile.TemporaryDirectory() as tmp:
        png = _seed42_render(3, tmp)
        sidecar = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
        image = cv2.imread(str(png))
        result = rectify(image)
    assert result.tier == 0
    truth = [tuple(p) for p in sidecar["corners"]]
    assert quad_iou([tuple(p) for p in result.corners], truth) >= 0.99


def test_user_corners_bypass_detection():
    # supplying corners is the escape hatch: no tier is assigned
    image, truth = _load("render_on_white", 1400)
    result = rectify(image, corners=truth)
    assert result.tier is None
    assert quad_iou([tuple(p) for p in result.corners], truth) >= 0.99


# ---------------------------------------------------------------------------
# generalized tier internals
# ---------------------------------------------------------------------------


def _rectify_module():
    import qrep.vision.rectify as module

    return module


def test_generalized_tier1_handles_renderer_background():
    # the GENERALIZED border-sample path must handle an exact-#404040
    # bordered fixture on its own merits, not via the legacy special case
    module = _rectify_module()
    image, truth = _load("fabric_print", 1400)
    quad, _residual, accepted = module._tier1_detect(image)
    assert accepted
    assert quad_iou([tuple(map(float, p)) for p in quad], truth) >= IOU_MIN


def test_chrome_bar_loses_area_squareness_ranking():
    # rank the non-background contours of the screenshot fixture against a
    # page-white background model: the full-width chrome bars have huge
    # area but aspect-squareness ~0.15, so the quilt quad must win
    module = _rectify_module()
    image, truth = _load("screenshot_composite", 1400)
    quad = module._best_quad_from_bg_model(
        image, bg_bgr=(250.0, 250.0, 250.0), tolerance=25.0
    )
    assert quad is not None
    assert quad_iou([tuple(map(float, p)) for p in quad[0]], truth) >= 0.90


def test_grabcut_confidence_hand_computed_cases():
    # confidence = compactness * (1 - min(residual * 10, 1)), by hand:
    #   compactness 1.0, residual 0.00 -> 1.0 * (1 - 0.0) = 1.0
    #   compactness 0.5, residual 0.00 -> 0.5 * (1 - 0.0) = 0.5
    #   compactness 1.0, residual 0.05 -> 1.0 * (1 - 0.5) = 0.5
    #   compactness 0.8, residual 0.20 -> min(2.0, 1) = 1 -> 0.8 * 0 = 0.0
    module = _rectify_module()
    assert module._grabcut_confidence(1.0, 0.00) == pytest.approx(1.0)
    assert module._grabcut_confidence(0.5, 0.00) == pytest.approx(0.5)
    assert module._grabcut_confidence(1.0, 0.05) == pytest.approx(0.5)
    assert module._grabcut_confidence(0.8, 0.20) == pytest.approx(0.0)


def test_edge_to_edge_takes_tier3_full_frame():
    # cascade analysis (issue comment): on edge_to_edge the border strips
    # ARE the quilt's cream border, so tiers 1-2 can only find the interior
    # field and the inside-quad background gate rejects them; the honest
    # answer is tier 3's full-frame quad at fixed low confidence
    image, _truth = _load("edge_to_edge", 1400)
    result = rectify(image)
    assert result.tier == 3
    assert result.confidence == pytest.approx(0.2)
