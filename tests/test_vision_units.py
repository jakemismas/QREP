"""Unit regressions from the S7 adversarial council.

Finding B: the identity-path bounding-box crop used to feed background
wedge pixels into palette extraction (spec: quad pixels only), letting a
third cluster hijack k-selection. Finding A follow-on: the spike-train
dilation absorbs RANDOM one-pixel jitter (and only claims that much).
"""

import cv2
import numpy as np

from qrep.vision.grid import _find_pitch
from qrep.vision.palette import extract_palette
from qrep.vision.rectify import rectify

BACKGROUND = (0x40, 0x40, 0x40)


def _pinched_quilt_image() -> np.ndarray:
    """A two-color quilt whose quad is pinched ~0.6 percent: inside the
    identity threshold, so rectify crops the bounding box and must mask the
    background wedges that ride along."""
    img = np.full((600, 600, 3), BACKGROUND, dtype=np.uint8)
    quad = np.array([[103, 100], [497, 103], [494, 500], [100, 497]], dtype=np.int32)
    cv2.fillConvexPoly(img, quad, (60, 90, 200))
    # checkered second color so k-means has two real fabric clusters
    for y in range(100, 500, 50):
        for x in range(100, 500, 50):
            if (x + y) // 50 % 2 == 0:
                cv2.rectangle(img, (x + 4, y + 4), (x + 46, y + 46), (220, 230, 240), -1)
    return img


def test_identity_crop_masks_background_wedges():
    result = rectify(_pinched_quilt_image())
    assert result.identity is True
    # pixels the mask keeps must contain no background color at all
    kept = result.image[result.mask > 0]
    background_hits = np.all(kept == np.array(BACKGROUND, dtype=np.uint8), axis=-1).sum()
    assert background_hits == 0
    # while the raw bounding-box crop DOES contain wedges (the bug's vector)
    raw_hits = np.all(
        result.image.reshape(-1, 3) == np.array(BACKGROUND, dtype=np.uint8), axis=-1
    ).sum()
    assert raw_hits > 0


def test_masked_palette_ignores_wedges():
    result = rectify(_pinched_quilt_image())
    palette = extract_palette(result.image, mask=result.mask)
    # two fabric clusters, not three: the gray wedge cannot form a cluster
    assert palette.k == 2
    grays = [c for c in palette.colors_bgr if max(c) - min(c) < 12 and abs(c[0] - 0x40) < 24]
    assert not grays


def test_pitch_survives_random_one_pixel_jitter():
    # spikes every 15 px with seeded random +-1 px jitter: the documented
    # case the dilation absorbs (systematic 14/16 alternation is a genuine
    # 2-cell period and is out of scope by design)
    rng = np.random.default_rng(7)
    profile = np.zeros(760)
    for k in range(1, 50):
        profile[15 * k + rng.integers(-1, 2)] = 100.0
    pitch, prominence = _find_pitch(profile, max_pitch=180)
    assert abs(pitch - 15.0) <= 0.6
    assert prominence > 0.5
