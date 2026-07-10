"""S3 grid plausibility guards and raise-to-verdict (sprint 3, issue #69).

CONTRACT LITERALS (frozen, never edited): T1 = 0.60 (the verdict grid floor,
frozen on #65); pitch recovery within 2% on the #33 AC1 alternation fixture;
solid-fabric returns grid_diagnosis="no_periodicity" at grid confidence 0.

Guard (a) tolerance, hand-derived (documented in the plan comment on #69):
TOL(m) = 0.06 + 3.0 * m, where m is rectify's warp_magnitude. The warp
target preserves image-plane edge lengths; a corner pull of m*max_dim moves
opposite edge lengths apart by up to 2*m*max_dim, and max_dim/extent <= 1.5
across our aspect range, so the pitch-ratio skew a legitimate perspective
can introduce is bounded by ~3m; 0.06 covers frontal rounding jitter.

Every fixture below is built in-test from hand-chosen geometry; expected
values are computed by hand in the comments, never observed output.
"""

import tempfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from PIL import Image

from qrep.vision import reverse
from qrep.vision.grid import estimate_grid
from qrep.vision.verdict import T1

PHOTOREAL = Path(__file__).parent / "fixtures" / "photoreal"

LIGHT = (200, 200, 200)
DARK = (60, 60, 60)


def _checker(
    col_widths: list[int], row_heights: list[int], strong=DARK, weak=LIGHT
) -> np.ndarray:
    """Checkerboard BGR array from explicit column/row extents."""
    width, height = sum(col_widths), sum(row_heights)
    image = np.zeros((height, width, 3), dtype=np.uint8)
    y = 0
    for r, rh in enumerate(row_heights):
        x = 0
        for c, cw in enumerate(col_widths):
            color = strong if (r + c) % 2 == 0 else weak
            image[y : y + rh, x : x + cw] = color
            x += cw
        y += rh
    return image


# ---------------------------------------------------------------------------
# raise-to-result conversion
# ---------------------------------------------------------------------------


def test_solid_fabric_returns_no_periodicity_at_zero_confidence():
    # the contract's pinned outcome: a no-pattern image is a typed no-grid
    # result, not a 7x7 smear at 0.5 confidence and not an exception
    result = reverse(PHOTOREAL / "solid_fabric_1400.png")
    assert result.diagnostics["grid_diagnosis"] == "no_periodicity"
    assert result.quilt.provenance.stage_confidence["grid"] == 0.0
    assert result.quilt.provenance.stage_confidence["cells"] == 0.0


def test_all_background_image_is_a_typed_result_not_a_raise(tmp_path):
    # rectify's "no quilt found" ValueError becomes a typed result
    path = tmp_path / "flat.png"
    Image.fromarray(np.full((300, 400, 3), 0x40, dtype=np.uint8)).save(path)
    result = reverse(path)
    assert result.diagnostics["grid_diagnosis"] == "no_quilt_found"
    assert result.quilt.provenance.stage_confidence["grid"] == 0.0
    assert result.quilt.provenance.stage_confidence["rectify"] == 0.0


def test_tiny_image_profile_too_short_is_typed(tmp_path):
    # a 23 px canvas guarantees the too-short path in EVERY runtime: even a
    # full-frame crop gives max_pitch = 23 // 4 = 5 <= MIN_PITCH_PX, so the
    # extent check fires before any edge-energy consideration; it must
    # convert to a typed result, not raise. (The 15 px quilt keeps enough
    # pixels after mask erosion for the palette stage upstream.)
    quilt = _checker([7, 8], [7, 8])
    canvas = np.full((23, 23, 3), 0x40, dtype=np.uint8)
    canvas[4:19, 4:19] = quilt
    path = tmp_path / "tiny.png"
    Image.fromarray(canvas[:, :, ::-1]).save(path)  # builder is BGR; save RGB
    result = reverse(path)
    assert result.diagnostics["grid_diagnosis"] == "profile_too_short"
    assert result.quilt.provenance.stage_confidence["grid"] == 0.0


def test_fallback_result_is_model_safe():
    # the fallback quilt validates and carries zeroed cell confidence
    result = reverse(PHOTOREAL / "solid_fabric_1400.png")
    quilt = result.quilt
    assert quilt.center.rows >= 1 and quilt.center.cols >= 1
    assert all(v == 0.0 for row in quilt.center.cell_confidence for v in row)
    assert quilt.provenance.source == "cv"


# ---------------------------------------------------------------------------
# guard (a): pitch isotropy + joint harmonic re-search
# ---------------------------------------------------------------------------


def test_planted_harmonic_must_not_win():
    # 20 columns of pitch 20 whose base gray cycles [60, 200, 175, 35]:
    # vertical boundary contrasts by hand are |60-200| = 140 (strong),
    # |200-175| = 25 (weak), |175-35| = 140, |35-60| = 25 ... so STRONG
    # vertical boundaries repeat every 40 px while the true pitch is 20.
    # Rows add a +/-30 brightness offset alternating every 20 px, so every
    # horizontal boundary has contrast 60 and pitch_y is a clean 20. The
    # weak x-boundaries fall under the binarize threshold today, the spike
    # train peaks at lag 40, and pitch_x reads as the 2x harmonic; the
    # joint re-search must recover the isotropic (20, 20) pair.
    col_cycle = [60, 200, 175, 35]
    image = np.zeros((400, 400, 3), dtype=np.uint8)
    for c in range(20):
        base = col_cycle[c % 4]
        for r in range(20):
            value = np.clip(base + (30 if r % 2 == 0 else -30), 0, 255)
            image[r * 20 : (r + 1) * 20, c * 20 : (c + 1) * 20] = value
    grid = estimate_grid(image)
    # true pitch is 20 on both axes (hand geometry above)
    assert grid.x.pitch == pytest.approx(20.0, rel=0.02)
    assert grid.y.pitch == pytest.approx(20.0, rel=0.02)


def test_tilted_35_degree_guard_stays_silent():
    # Hand-computed post-warp geometry. Content: 20x20 cells of pitch 20
    # (400 x 400). Chosen quad (a ~35-degree tilt about the vertical axis):
    #   TL (20, 20), TR (380, 80), BR (380, 320), BL (20, 380)
    # Edge lengths: left = 380 - 20 = 360; right = 320 - 80 = 240;
    # top = bottom = sqrt(360^2 + 60^2) = 364.97.
    # rectify's warp target: W = mean(top, bottom) = 364.97 -> pitch_x =
    # 364.97 / 20 = 18.25; H = mean(left, right) = 300 -> pitch_y = 15.
    # Ratio = 18.25 / 15 = 1.217, so |1 - r| = 0.217.
    # warp_magnitude m = mean corner distance from the bounding rect
    # ((20,20),(380,20),(380,380),(20,380)): TL 0, TR 60, BR 60, BL 0 ->
    # mean 30; max_dim 420 -> m = 30 / 420 = 0.0714.
    # TOL(m) = 0.06 + 3.0 * 0.0714 = 0.274 > 0.217: the guard stays silent
    # and the recovered dims are the true 20 x 20.
    content = _checker([20] * 20, [20] * 20)
    canvas = np.full((420, 420, 3), 255, dtype=np.uint8)
    quad = np.array([[20, 20], [380, 80], [380, 320], [20, 380]], dtype=np.float32)
    src = np.array([[0, 0], [400, 0], [400, 400], [0, 400]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, quad)
    warped = cv2.warpPerspective(
        content, matrix, (420, 420), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255)
    )
    mask = cv2.warpPerspective(
        np.full((400, 400), 255, dtype=np.uint8), matrix, (420, 420), flags=cv2.INTER_NEAREST
    )
    canvas[mask > 0] = warped[mask > 0]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "tilted.png"
        Image.fromarray(canvas[:, :, ::-1]).save(path)
        result = reverse(path)
    assert result.diagnostics.get("grid_diagnosis") is None
    assert result.diagnostics["interior_dims"] == [20, 20]
    assert result.quilt.provenance.stage_confidence["grid"] >= T1


def test_perspective_mis_crop_13x43_class_is_caught_below_t1():
    # the 13x43 failure class on the contract's perspective + mis-crop
    # fixture: full-frame user corners on the perspective composite feed a
    # TILTED quilt plus margins into the grid stage. The read must carry a
    # structured grid_diagnosis and land below T1 = 0.60.
    corners = [(0.0, 0.0), (1400.0, 0.0), (1400.0, 1050.0), (0.0, 1050.0)]
    result = reverse(PHOTOREAL / "render_perspective_jpeg_1400.png", corners=corners)
    assert result.diagnostics["grid_diagnosis"] is not None
    assert result.quilt.provenance.stage_confidence["grid"] < T1


def test_anisotropic_garbage_is_caught_below_t1():
    # guard (a)'s standing-violation face, on a case NO harmonic pair can
    # rescue: a 20 x 33 px grating. Hand-check of every re-search pair
    # (factors 1, 2, 3, 1/2, 1/3): x candidates {20, 40, 60, 10, 6.7} vs
    # y candidates {33, 66, 99, 16.5, 11} - the closest ratios (10:11,
    # 60:66) are 1.10, all above TOL(0) = 1.06. The violation stands:
    # anisotropic_pitch, confidence capped below T1.
    # (This test originally pinned drunkards_path's interim S3 state; the
    # S4 contract supersedes that - its integer-ratio feedback now recovers
    # drunkards to non_square_repeat, pinned in test_repeats_verdict.py.)
    image = np.full((330, 400, 3), 200, dtype=np.uint8)
    for x in range(0, 400, 20):
        image[:, x : x + 2] = 60
    for y in range(0, 330, 33):
        image[y : y + 2, :] = 60
    grid = estimate_grid(image)
    assert grid.diagnosis == "anisotropic_pitch"
    assert grid.confidence < T1


# ---------------------------------------------------------------------------
# guard (b): cell-count bounds (product decision recorded on issue #69)
# ---------------------------------------------------------------------------


def test_cell_count_bounds_are_the_detector_envelope():
    from qrep.vision.grid import MIN_PITCH_PX, cell_count_bounds

    # bounds derive from the detector envelope: a 1-cell axis has no
    # interior line to detect (lower bound 2); a pitch below MIN_PITCH_PX
    # is unresolvable, so cells > extent / MIN_PITCH_PX is self-contradictory
    low, high = cell_count_bounds(1400)
    assert low == 2
    assert high == 1400 // MIN_PITCH_PX  # 280 by hand: 1400 / 5


# ---------------------------------------------------------------------------
# #33 AC1: systematic 14/16 alternation recovers the true mean pitch
# ---------------------------------------------------------------------------


def test_pitch_alternation_14_16_recovers_within_two_percent():
    # 20 columns alternating 14 and 16 px wide (mean pitch 15, the renderer
    # rounding artifact class from #33 AC1); rows constant 15. Recovery
    # contract, frozen by #33: mean pitch within 2% of truth on both axes.
    widths = [14 if i % 2 == 0 else 16 for i in range(20)]
    heights = [15] * 20
    image = _checker(widths, heights)
    grid = estimate_grid(image)
    assert grid.x.pitch == pytest.approx(15.0, rel=0.02)
    assert grid.y.pitch == pytest.approx(15.0, rel=0.02)


# ---------------------------------------------------------------------------
# byte-stability of the clean path
# ---------------------------------------------------------------------------


def test_clean_grid_results_carry_no_diagnosis():
    # a healthy read must not grow a diagnosis (guards silent = zero
    # mutation; the L0-L2 legacy pin proves byte-stability separately)
    result = reverse(PHOTOREAL / "edge_to_edge_1400.png")
    assert result.diagnostics.get("grid_diagnosis") is None
