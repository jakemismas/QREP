"""S2 detect_quad bridge method (sprint 3, issue #68).

Detection tiers only, no full reverse. The return contract is owned by S2:
quad (normalized to [0,1] image coordinates), tier, confidence, and
predicted_size ({width_px, height_px, aspect, preset}); S6 populates the
preset suggestion, S7 renders it - the FIELD is defined here.

New file: the sprint 2 test_bridge.py suite is frozen and stays untouched.
"""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from qrep import bridge
from qrep.vision.metrics import quad_iou

PHOTOREAL = Path(__file__).parent / "fixtures" / "photoreal"


def _call(image_path) -> dict:
    envelope = json.loads(bridge.detect_quad(str(image_path)))
    assert envelope["ok"], envelope
    return envelope["result"]


def test_detect_quad_finds_the_white_background_quilt():
    result = _call(PHOTOREAL / "render_on_white_1400.png")
    side = json.loads((PHOTOREAL / "render_on_white_1400.json").read_text(encoding="utf-8"))
    w, h = side["canvas"]
    # normalized quad: scale back to pixels and compare against the sidecar
    quad_px = [(x * w, y * h) for x, y in result["quad"]]
    truth = [tuple(p) for p in side["quad"]]
    assert quad_iou(quad_px, truth) >= 0.95  # same frozen bound as the S1 contract
    assert result["tier"] == 1
    assert 0.0 < result["confidence"] <= 1.0
    for x, y in result["quad"]:
        assert 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0


def test_detect_quad_predicted_size_field_shape():
    result = _call(PHOTOREAL / "render_on_white_1400.png")
    predicted = result["predicted_size"]
    assert set(predicted) == {"width_px", "height_px", "aspect", "preset"}
    # S6 landed the suggestion this field was defined for (the S2-era
    # assertion "preset is None until S6" is superseded by contract): the
    # 60:50-pitch quad normalizes to aspect 1.2 = Queen (108/90) uniquely
    assert predicted["preset"] == "Queen"
    assert predicted["width_px"] > 0 and predicted["height_px"] > 0
    # aspect is defined as width_px / height_px of the detected quad
    assert predicted["aspect"] == pytest.approx(
        predicted["width_px"] / predicted["height_px"], abs=1e-9
    )
    # the irish chain quilt spans 50 x 60 pitches: taller than wide
    assert predicted["aspect"] < 1.0


def test_detect_quad_missing_file_is_a_value_error():
    envelope = json.loads(bridge.detect_quad("/nowhere/missing.png"))
    assert envelope["ok"] is False
    assert envelope["error"]["kind"] == "value"


def test_detect_quad_never_raises_on_all_background(tmp_path):
    # an entirely #404040 image makes the legacy tier raise "no quilt
    # found"; detect_quad must answer with the honest tier-3 full frame at
    # the fixed low confidence instead of an error (the crop screen makes
    # it visible and fixable)
    path = tmp_path / "flat.png"
    Image.fromarray(np.full((300, 400, 3), 0x40, dtype=np.uint8)).save(path)
    result = _call(path)
    assert result["tier"] == 3
    assert result["confidence"] == pytest.approx(0.2)
    assert result["quad"] == [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]
