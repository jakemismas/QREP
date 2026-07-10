"""Rectification: find the quilt-background quad and warp it upright.

Sprint 3 S1 (issue #67): detection is TIERED so the pipeline finds quilts
on photos QREP did not render, without disturbing its own renders:

- Tier 0, legacy: border-strip pooled median within epsilon of the
  renderer's #404040 runs the EXACT pre-sprint-3 path (BACKGROUND_BGR,
  distance > 40) verbatim; byte-identity with the S0 pinned regression is
  claimed for this branch only.
- Tier 1, border-sample: all four border strips uniform (small MAD, high
  inlier fraction) and mutually agreeing -> background model from their
  pooled median, tolerance from the inlier spread; contour candidates
  ranked by area x aspect-squareness so a full-width chrome bar cannot win
  on area alone.
- Tier 2, GrabCut: strips disagree or are not uniform -> cv2.grabCut with
  GC_INIT_WITH_MASK seeded from whichever strips passed uniformity, on a
  ~600 px downscale, quad scaled back. Near-axis-aligned quads get an
  outward edge refinement against the GrabCut background color model (a
  quilt border close to the page color reads as background to the GMM;
  the refinement recovers it).
- Tier 3, last resort: the full-image quad at fixed LOW confidence - the
  crop screen makes it visible and fixable, so it is honest.

Tiers 1 and 2 accept only quads whose interior is mostly NOT
background-colored: when the quilt runs edge to edge, the strips ARE its
border fabric, tiers 1-2 can only find the interior field, and the honest
answer is tier 3's full frame.

When the detected quad deviates from an axis-aligned rectangle by less
than 1 percent of image size we skip warping entirely (identity path);
the L0 test exercises that path.
"""

import cv2
import numpy as np
from pydantic import BaseModel

BACKGROUND_BGR = np.array([0x40, 0x40, 0x40], dtype=np.float32)
IDENTITY_THRESHOLD = 0.01  # fraction of max image dimension

# tiered-detection constants (S1 implementation values; the contractual
# literals live in the tests and the plan, not here)
STRIP_FRACTION = 0.04
LEGACY_EPSILON = 8.0
UNIFORM_MAD_MAX = 12.0
UNIFORM_INLIER_MIN = 0.90
INLIER_RADIUS_FLOOR = 15.0
INLIER_RADIUS_MADS = 4.0
AGREE_MAX = 20.0
BG_TOL_FLOOR = 25.0
BG_TOL_MADS = 6.0
MIN_CONTOUR_AREA_FRACTION = 0.02
MIN_QUAD_AREA_FRACTION = 0.05
INSIDE_BG_MAX = 0.35
GRABCUT_LONGEST = 600
GRABCUT_ITERS = 5
FG_FRACTION_MIN = 0.10
FG_FRACTION_MAX = 0.90
REFINE_MAX_EXPAND_FRACTION = 0.20
REFINE_LINE_QUILT_MIN = 0.5
TIER3_CONFIDENCE = 0.2
BG_SAMPLE = 20_000


class RectifyResult(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    image: np.ndarray  # rectified BGR quilt-only image
    mask: np.ndarray  # uint8, 255 inside the quilt quad (output coordinates)
    corners: list[tuple[float, float]]  # detected quad in source px, TL TR BR BL
    identity: bool
    confidence: float
    tier: int | None = None  # 0..3 for detected quads; None for user corners
    warp_magnitude: float = 0.0  # mean corner pull / max_dim (identity: 0.0)


def _order_corners(points: np.ndarray) -> np.ndarray:
    """Order 4 points TL, TR, BR, BL by their sums and differences."""
    sums = points.sum(axis=1)
    diffs = points[:, 0] - points[:, 1]
    return np.array(
        [
            points[np.argmin(sums)],
            points[np.argmax(diffs)],
            points[np.argmax(sums)],
            points[np.argmin(diffs)],
        ],
        dtype=np.float64,
    )


def _quad_from_contour(contour: np.ndarray) -> tuple[np.ndarray, float]:
    """Convex hull approximated to 4 corners plus the normalized residual.

    This is the EXACT quad-fitting used by the legacy path since sprint 1;
    tiers 1 and 2 reuse it on their own masks."""
    hull = cv2.convexHull(contour)
    peri = cv2.arcLength(hull, True)
    for epsilon_frac in (0.01, 0.02, 0.03, 0.05):
        approx = cv2.approxPolyDP(hull, epsilon_frac * peri, True)
        if len(approx) == 4:
            break
    else:
        # fall back to the minimum-area rectangle when simplification refuses
        approx = cv2.boxPoints(cv2.minAreaRect(contour)).reshape(-1, 1, 2)
    corners = _order_corners(approx.reshape(-1, 2).astype(np.float64))
    poly = corners.astype(np.float32)
    residuals = [
        abs(cv2.pointPolygonTest(poly.reshape(-1, 1, 2), (float(p[0][0]), float(p[0][1])), True))
        for p in hull
    ]
    residual_norm = float(np.mean(residuals)) / max(peri, 1.0)
    return corners, residual_norm


def _detect_quad(image: np.ndarray) -> tuple[np.ndarray, float]:
    """Largest non-background contour approximated to 4 corners (tier 0,
    the verbatim legacy path: renderer #404040 background, distance > 40).

    Returns (corners TL TR BR BL, fit residual normalized by perimeter)."""
    distance = np.linalg.norm(image.astype(np.float32) - BACKGROUND_BGR, axis=2)
    mask = (distance > 40).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("no quilt found: image is entirely background-colored")
    contour = max(contours, key=cv2.contourArea)
    return _quad_from_contour(contour)


# ---------------------------------------------------------------------------
# border-strip statistics
# ---------------------------------------------------------------------------


def _strip_pixels(image: np.ndarray) -> list[np.ndarray]:
    """Top, bottom, left, right border strips as flat float32 pixel lists."""
    h, w = image.shape[:2]
    t = max(4, int(round(STRIP_FRACTION * min(h, w))))
    return [
        image[:t, :].reshape(-1, 3).astype(np.float32),
        image[h - t :, :].reshape(-1, 3).astype(np.float32),
        image[:, :t].reshape(-1, 3).astype(np.float32),
        image[:, w - t :].reshape(-1, 3).astype(np.float32),
    ]


def _strip_stats(pixels: np.ndarray) -> tuple[np.ndarray, float, float]:
    """(median BGR, MAD of distances to it, inlier fraction)."""
    median = np.median(pixels, axis=0)
    distances = np.linalg.norm(pixels - median, axis=1)
    mad = float(np.median(distances))
    radius = max(INLIER_RADIUS_FLOOR, INLIER_RADIUS_MADS * mad)
    inlier_fraction = float(np.mean(distances <= radius))
    return median, mad, inlier_fraction


def _inside_bg_fraction(
    image: np.ndarray, quad: np.ndarray, bg: np.ndarray, tolerance: float
) -> float:
    """Fraction of pixels inside the quad that match the background model.

    A legitimate detection contains the quilt: mostly NOT background."""
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mask, quad.astype(np.int32), 255)
    inside = mask > 0
    if not inside.any():
        return 1.0
    distance = np.linalg.norm(image.astype(np.float32) - bg.astype(np.float32), axis=2)
    return float(np.mean(distance[inside] <= tolerance))


def _strip_surface_models(image: np.ndarray) -> list[tuple[np.ndarray, float]]:
    """The four strips' dominant-surface color models: (median, radius)."""
    models = []
    for pixels in _strip_pixels(image):
        median, mad, _inlier = _strip_stats(pixels)
        models.append((median, max(INLIER_RADIUS_FLOOR, INLIER_RADIUS_MADS * mad)))
    return models


def _inside_surface_fraction(
    image: np.ndarray, quad: np.ndarray, models: list[tuple[np.ndarray, float]]
) -> float:
    """Fraction of quad-interior pixels matching ANY strip surface model.

    The strips are the known background samples; a detection whose interior
    is largely strip-colored found a background region, not the quilt."""
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mask, quad.astype(np.int32), 255)
    inside = mask > 0
    if not inside.any():
        return 1.0
    pixels = image[inside].astype(np.float32)
    matches = np.zeros(pixels.shape[0], dtype=bool)
    for median, radius in models:
        matches |= np.linalg.norm(pixels - median, axis=1) <= radius
    return float(np.mean(matches))


# ---------------------------------------------------------------------------
# tier 1: border-sample background model
# ---------------------------------------------------------------------------


def _best_quad_from_bg_model(
    image: np.ndarray, bg_bgr, tolerance: float
) -> tuple[np.ndarray, float] | None:
    """Best quad among non-background contours, ranked by area x
    aspect-squareness (min side / max side of the min-area rect): a
    full-width chrome bar has aspect ~0.15 and must lose to a plausible
    quilt quad even with more raw area."""
    bg = np.asarray(bg_bgr, dtype=np.float32)
    distance = np.linalg.norm(image.astype(np.float32) - bg, axis=2)
    mask = (distance > tolerance).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    image_area = image.shape[0] * image.shape[1]
    best_score, best_contour = 0.0, None
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_CONTOUR_AREA_FRACTION * image_area:
            continue
        (_cx, _cy), (rw, rh), _angle = cv2.minAreaRect(contour)
        if rw <= 0 or rh <= 0:
            continue
        aspect = min(rw, rh) / max(rw, rh)
        score = area * aspect
        if score > best_score:
            best_score, best_contour = score, contour
    if best_contour is None:
        return None
    return _quad_from_contour(best_contour)


def _tier1_detect(image: np.ndarray) -> tuple[np.ndarray | None, float, bool]:
    """Border-sample detection. Returns (quad, residual, accepted)."""
    strips = _strip_pixels(image)
    stats = [_strip_stats(s) for s in strips]
    uniform = [
        mad <= UNIFORM_MAD_MAX and inlier >= UNIFORM_INLIER_MIN for _m, mad, inlier in stats
    ]
    if not all(uniform):
        return None, 0.0, False
    medians = [m for m, _mad, _inlier in stats]
    for i in range(4):
        for j in range(i + 1, 4):
            if float(np.linalg.norm(medians[i] - medians[j])) > AGREE_MAX:
                return None, 0.0, False
    pooled = np.concatenate(strips, axis=0)
    bg, pooled_mad, _ = _strip_stats(pooled)
    tolerance = max(BG_TOL_FLOOR, BG_TOL_MADS * pooled_mad)
    found = _best_quad_from_bg_model(image, bg, tolerance)
    if found is None:
        return None, 0.0, False
    quad, residual = found
    image_area = image.shape[0] * image.shape[1]
    quad_area = cv2.contourArea(quad.astype(np.float32))
    if quad_area < MIN_QUAD_AREA_FRACTION * image_area:
        return None, 0.0, False
    if _inside_bg_fraction(image, quad, bg, tolerance) > INSIDE_BG_MAX:
        return None, 0.0, False
    return quad, residual, True


# ---------------------------------------------------------------------------
# tier 2: GrabCut
# ---------------------------------------------------------------------------


def _grabcut_confidence(compactness: float, residual: float) -> float:
    """GrabCut-tier confidence: mask compactness x quad fit quality."""
    return compactness * (1.0 - min(residual * 10.0, 1.0))


def _refine_axis_aligned_quad(
    image: np.ndarray, quad: np.ndarray, bg: np.ndarray, tolerance: float
) -> np.ndarray:
    """Expand a near-axis-aligned quad outward while the adjacent line is
    mostly NOT background-colored: recovers a quilt border whose color the
    GrabCut GMM absorbed into the page background."""
    h, w = image.shape[:2]
    x0 = int(np.floor(quad[:, 0].min()))
    x1 = int(np.ceil(quad[:, 0].max()))
    y0 = int(np.floor(quad[:, 1].min()))
    y1 = int(np.ceil(quad[:, 1].max()))
    deviation = float(
        np.abs(
            quad
            - np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64)
        ).max()
    )
    if deviation > IDENTITY_THRESHOLD * 2 * max(h, w):
        return quad  # tilted quad: refinement is bbox-based, skip
    distance = np.linalg.norm(image.astype(np.float32) - bg.astype(np.float32), axis=2)
    quiltish = distance > tolerance
    cap_x = int(REFINE_MAX_EXPAND_FRACTION * w)
    cap_y = int(REFINE_MAX_EXPAND_FRACTION * h)

    def frac(line: np.ndarray) -> float:
        return float(np.mean(line)) if line.size else 0.0

    steps = 0
    while x0 > 0 and steps < cap_x and frac(quiltish[y0:y1, x0 - 1]) >= REFINE_LINE_QUILT_MIN:
        x0 -= 1
        steps += 1
    steps = 0
    while x1 < w and steps < cap_x and frac(quiltish[y0:y1, x1]) >= REFINE_LINE_QUILT_MIN:
        x1 += 1
        steps += 1
    steps = 0
    while y0 > 0 and steps < cap_y and frac(quiltish[y0 - 1, x0:x1]) >= REFINE_LINE_QUILT_MIN:
        y0 -= 1
        steps += 1
    steps = 0
    while y1 < h and steps < cap_y and frac(quiltish[y1, x0:x1]) >= REFINE_LINE_QUILT_MIN:
        y1 += 1
        steps += 1
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64)


def _tier2_grabcut(
    image: np.ndarray,
) -> tuple[np.ndarray | None, float, float, bool]:
    """GrabCut detection at the ~600 px downscale.

    Returns (quad in FULL-image coordinates, residual, confidence,
    accepted)."""
    h, w = image.shape[:2]
    scale = GRABCUT_LONGEST / max(h, w)
    if scale < 1.0:
        small = cv2.resize(
            image, (int(round(w * scale)), int(round(h * scale))), interpolation=cv2.INTER_AREA
        )
    else:
        small = image.copy()
    sh, sw = small.shape[:2]
    t = max(2, int(round(STRIP_FRACTION * min(sh, sw))))

    mask = np.full((sh, sw), cv2.GC_PR_BGD, np.uint8)
    inset_y, inset_x = int(round(0.25 * sh)), int(round(0.25 * sw))
    mask[inset_y : sh - inset_y, inset_x : sw - inset_x] = cv2.GC_PR_FGD
    # sure-background seeding from the strips: a strip that passes
    # uniformity contributes essentially all its pixels; a MIXED strip (the
    # chrome-barred screenshot's page+chrome sides) contributes its
    # dominant-surface inliers, leaving the minority probable. Without the
    # page pixels in the sure-background set, the GMM has only chrome as
    # definite background and sometimes flips the whole page to foreground.
    strip_slices = [
        (slice(0, t), slice(0, sw)),
        (slice(sh - t, sh), slice(0, sw)),
        (slice(0, sh), slice(0, t)),
        (slice(0, sh), slice(sw - t, sw)),
    ]
    for ys, xs in strip_slices:
        region = small[ys, xs].astype(np.float32)
        median, mad, _inlier = _strip_stats(region.reshape(-1, 3))
        radius = max(INLIER_RADIUS_FLOOR, INLIER_RADIUS_MADS * mad)
        distance = np.linalg.norm(region - median, axis=2)
        sub = mask[ys, xs]
        sub[distance <= radius] = cv2.GC_BGD
        mask[ys, xs] = sub

    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.setRNGSeed(42)
    try:
        cv2.grabCut(small, mask, None, bgd, fgd, GRABCUT_ITERS, cv2.GC_INIT_WITH_MASK)
    except cv2.error:
        return None, 0.0, 0.0, False
    fg = np.isin(mask, (cv2.GC_FGD, cv2.GC_PR_FGD))
    fg_fraction = float(fg.mean())
    if not (FG_FRACTION_MIN <= fg_fraction <= FG_FRACTION_MAX):
        return None, 0.0, 0.0, False

    fg_mask = (fg * 255).astype(np.uint8)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    small_area = sh * sw
    best_score, best_contour = 0.0, None
    for contour in contours:
        area = cv2.contourArea(contour)
        if area < MIN_CONTOUR_AREA_FRACTION * small_area:
            continue
        (_cx, _cy), (rw, rh), _angle = cv2.minAreaRect(contour)
        if rw <= 0 or rh <= 0:
            continue
        aspect = min(rw, rh) / max(rw, rh)
        score = area * aspect
        if score > best_score:
            best_score, best_contour = score, contour
    if best_contour is None:
        return None, 0.0, 0.0, False
    quad, residual = _quad_from_contour(best_contour)

    contour_area = cv2.contourArea(best_contour)
    hull_area = cv2.contourArea(cv2.convexHull(best_contour))
    compactness = float(contour_area / hull_area) if hull_area > 0 else 0.0
    confidence = _grabcut_confidence(compactness, residual)

    # background color model from the GrabCut background region
    bg_pixels = small[~fg].reshape(-1, 3).astype(np.float32)
    if bg_pixels.shape[0] == 0:
        return None, 0.0, 0.0, False
    if bg_pixels.shape[0] > BG_SAMPLE:
        idx = np.random.default_rng(42).choice(bg_pixels.shape[0], BG_SAMPLE, replace=False)
        bg_pixels = bg_pixels[np.sort(idx)]
    bg, bg_mad, _ = _strip_stats(bg_pixels)
    tolerance = max(BG_TOL_FLOOR, BG_TOL_MADS * bg_mad)

    quad = _refine_axis_aligned_quad(small, quad, bg, tolerance)
    quad_area = cv2.contourArea(quad.astype(np.float32))
    if quad_area < MIN_QUAD_AREA_FRACTION * small_area:
        return None, 0.0, 0.0, False

    # acceptance: the interior must not look like the strip surfaces. When
    # it does, GrabCut found a background REGION (the page band between
    # chrome bars around a small quilt): re-run the border-sample detector
    # INSIDE the coarse region, where that surface is the local uniform
    # background. Quilts whose inner crop has no uniform border (edge-to-
    # edge piecing, checker interiors) fail the inner detector and fall
    # through to tier 3 - which is the honest answer for them.
    surfaces = _strip_surface_models(small)
    if _inside_surface_fraction(small, quad, surfaces) > INSIDE_BG_MAX:
        bx0 = max(0, int(np.floor(quad[:, 0].min())))
        bx1 = min(sw, int(np.ceil(quad[:, 0].max())))
        by0 = max(0, int(np.floor(quad[:, 1].min())))
        by1 = min(sh, int(np.ceil(quad[:, 1].max())))
        # shave a sliver so bbox rounding cannot drag foreign pixels (a
        # chrome edge) into the inner detector's border strips
        pad_x = max(2, int(round(0.02 * (bx1 - bx0))))
        pad_y = max(2, int(round(0.02 * (by1 - by0))))
        bx0, bx1 = bx0 + pad_x, bx1 - pad_x
        by0, by1 = by0 + pad_y, by1 - pad_y
        if bx1 - bx0 < 40 or by1 - by0 < 40:
            return None, 0.0, 0.0, False
        inner_quad, inner_residual, inner_ok = _tier1_detect(small[by0:by1, bx0:bx1])
        if not inner_ok:
            return None, 0.0, 0.0, False
        quad = inner_quad + np.array([bx0, by0], dtype=np.float64)
        residual = inner_residual
        confidence = _grabcut_confidence(compactness, residual)
        if _inside_surface_fraction(small, quad, surfaces) > INSIDE_BG_MAX:
            return None, 0.0, 0.0, False

    quad_full = quad * np.array([w / sw, h / sh], dtype=np.float64)
    quad_full[:, 0] = np.clip(quad_full[:, 0], 0, w)
    quad_full[:, 1] = np.clip(quad_full[:, 1], 0, h)
    return quad_full, residual, confidence, True


# ---------------------------------------------------------------------------
# the cascade
# ---------------------------------------------------------------------------


def _detect_tiered(image: np.ndarray) -> tuple[np.ndarray, float, int, float | None]:
    """Returns (quad, residual, tier, tier2_confidence_or_None)."""
    h, w = image.shape[:2]
    pooled = np.concatenate(_strip_pixels(image), axis=0)
    pooled_median = np.median(pooled, axis=0)
    if float(np.linalg.norm(pooled_median - BACKGROUND_BGR)) <= LEGACY_EPSILON:
        quad, residual = _detect_quad(image)
        return quad, residual, 0, None
    quad, residual, accepted = _tier1_detect(image)
    if accepted:
        return quad, residual, 1, None
    quad, residual, confidence, accepted = _tier2_grabcut(image)
    if accepted:
        return quad, residual, 2, confidence
    full = np.array([[0, 0], [w, 0], [w, h], [0, h]], dtype=np.float64)
    return full, 0.0, 3, None


def rectify(image: np.ndarray, corners: list[tuple[float, float]] | None = None) -> RectifyResult:
    """Detect (or accept) the quilt quad and return the upright quilt image.

    User-supplied corners are the real-photo escape hatch; round-trip tests
    always call with the image alone.
    """
    max_dim = max(image.shape[0], image.shape[1])
    tier: int | None
    tier2_confidence: float | None = None
    if corners is not None:
        quad = _order_corners(np.array(corners, dtype=np.float64))
        residual_norm = 0.0
        tier = None
    else:
        quad, residual_norm, tier, tier2_confidence = _detect_tiered(image)

    # deviation of the quad from its own axis-aligned bounding rectangle
    x0, y0 = quad[:, 0].min(), quad[:, 1].min()
    x1, y1 = quad[:, 0].max(), quad[:, 1].max()
    rect = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64)
    deviation = float(np.abs(quad - rect).max()) / max_dim

    if deviation < IDENTITY_THRESHOLD:
        cx0, cy0 = int(round(x0)), int(round(y0))
        cropped = image[cy0 : int(round(y1)), cx0 : int(round(x1))]
        # the crop is the quad's bounding box; pixels between the quad and
        # the box are background wedges, and the design doc pins palette
        # extraction to pixels inside the QUAD only, so mask them out
        mask = np.zeros(cropped.shape[:2], dtype=np.uint8)
        local_quad = (quad - np.array([cx0, cy0])).astype(np.int32)
        cv2.fillConvexPoly(mask, local_quad, 255)
        if tier == 3:
            confidence = TIER3_CONFIDENCE
        elif tier == 2 and tier2_confidence is not None:
            confidence = min(tier2_confidence, 0.999)
        else:
            confidence = 1.0
        return RectifyResult(
            image=cropped,
            mask=mask,
            corners=[tuple(p) for p in rect],
            identity=True,
            confidence=confidence,
            tier=tier,
        )

    # output size from mean opposite edge lengths, so pitch survives the warp
    width = int(round((np.linalg.norm(quad[1] - quad[0]) + np.linalg.norm(quad[2] - quad[3])) / 2))
    height = int(round((np.linalg.norm(quad[3] - quad[0]) + np.linalg.norm(quad[2] - quad[1])) / 2))
    target = np.array([[0, 0], [width, 0], [width, height], [0, height]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad.astype(np.float32), target)
    warped = cv2.warpPerspective(image, matrix, (width, height), flags=cv2.INTER_LINEAR)

    # confidence: 1 - residual, scaled down by warp magnitude, so identity is
    # 1.0 and any real warp lands strictly below it (design doc formula)
    warp_magnitude = float(np.mean(np.linalg.norm(quad - rect, axis=1))) / max_dim
    confidence = max(0.0, (1.0 - min(residual_norm * 10, 1.0)) * (1.0 - warp_magnitude))
    if tier == 3:
        confidence = TIER3_CONFIDENCE
    elif tier == 2 and tier2_confidence is not None:
        confidence = min(tier2_confidence, 0.999)
    return RectifyResult(
        image=warped,
        # the whole warp target IS the quad interior
        mask=np.full((height, width), 255, dtype=np.uint8),
        corners=[tuple(p) for p in quad],
        identity=False,
        confidence=min(confidence, 0.999),
        tier=tier,
        warp_magnitude=warp_magnitude,
    )
