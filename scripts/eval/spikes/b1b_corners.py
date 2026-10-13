"""B1b spike: outer-edge corner suggestion (issue #135, plan ticket B1b).

Measures whether QREP can suggest the four outer-edge corners of a quilt well enough to
pre-place the confirm screen's pins (plan section 2.1, screen 2), on the v0 dev split:

- backdrop_hull: backdrop segmentation. A color model of the image's border ring (L*0.5 Lab),
  the backdrop-colored region connected to the image border, the largest remaining component,
  then its convex hull simplified to four corners.
- backdrop_lines: the same segmentation, with a robust line fit to each of the four sides of
  the outline, intersected, so a rounded or folded corner does not pull its pin inward.
- tiered: the reference, tiers 0 to 2 of the old detector (a copy of qrep/vision/rectify.py
  _detect_tiered). Its tier 3, the full frame, is recorded as no suggestion.

Each method runs on the whole photo (no corners are known yet), capped at each long side the
app stages at, and each corner's error is its distance from the proposed outer-edge corner in
squares. A band proposal set comes from a 1D change-point search on the color profiles inward
from each side of the warped proposed outer edge. Only photos outside the holdout are read
(corpus/README.md, holdout rule).

Run (from the worktree root, with the private cache of the main checkout):
  .venv/Scripts/python scripts/eval/spikes/b1b_corners.py --cache <main checkout>/corpus/private/cache
"""

import argparse
import csv
import datetime
import json
import math
import subprocess
import sys
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[3]
CORPUS = REPO / "corpus"

# --- Knobs, each with its source ----------------------------------------------------------
# web/src/model/downscale.ts: CAP_PHONE and CAP_DESKTOP. The suggestion runs before any corner
# is known, so on the whole photo with its long side capped at each.
CAPS = {"phone": 1400, "desktop": 2000}
# Issue #135 criterion 5: go when the 90th-percentile corner error is at most 0.22 of a square
# on both tiers, the largest radius at which exp1's voted read stayed at 1.00 (4 px at about
# 18 px per square).
BAR = 0.22
TIERS = ("museum", "screenshot")
PROVENANCES = ("verified-jake", "proposed-a", "proposed-b")
# Plan section 5.B: L*0.5 is the default color distance.
L_WEIGHT = 0.5
# Spike choice: a light blur before the color model, as B1a's field image used.
IMAGE_SIGMA = 1.0
# Spike choices for the backdrop model. The border ring is 2 percent of the shorter side (at
# least 3 px). A ring side is uniform when its distances to its median color have a MAD of
# at most 4 units and at least 90 percent of them lie within its tolerance, max(6, 4 MADs);
# at least two uniform sides make a backdrop.
RING = 0.02
RING_MAD_MAX = 4.0
RING_INLIER_MIN = 0.9
TOL_FLOOR = 6.0
TOL_MADS = 4.0
MIN_UNIFORM_SIDES = 2
# Spike choices for the quilt component: an opening of 0.5 percent of the shorter side (at least
# 3 px) cuts thin attachments; the component covers 5 to 98 percent of the photo; it touches at
# most 2 percent of any image side (more means its edge runs out of the photo); and the quad
# keeps an intersection over union of at least 0.9 with it.
OPEN_FRACTION = 0.005
AREA_RANGE = (0.05, 0.98)
TOUCH_MAX = 0.02
FIT_MIN = 0.9
# Spike choice for the line fit: the outer 10 percent of each side, near a corner, is left out.
CORNER_SKIP = 0.1
# Spike choices for the band search: profiles over the middle 60 percent of each side, down to
# a quarter of the shorter side, a two-window difference with windows of 1 percent of the
# shorter side (at least 3 px), a floor of 2 color units, and at most 4 proposals per side.
BAND_SPAN = (0.2, 0.8)
BAND_DEPTH = 0.25
BAND_WINDOW = 0.01
BAND_FLOOR = 2.0
BAND_K = 4
SIDES = ("top", "right", "bottom", "left")


# --- Copies from modules B6b deletes ------------------------------------------------------
# B6b deletes qrep/vision/rectify.py (plan B6b), so the spike carries the old detector's tiers 0
# to 2, copied from commit c8e4f8a (the last commit that touched it) with their logic and
# constants unchanged. The run checks the copy against the module before B6b lands (the
# report's Method section records how).

BACKGROUND_BGR = np.array([0x40, 0x40, 0x40], dtype=np.float32)
IDENTITY_THRESHOLD = 0.01  # fraction of max image dimension
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
BG_SAMPLE = 20_000


def _order_corners(points: np.ndarray) -> np.ndarray:
    """qrep/vision/rectify.py _order_corners at c8e4f8a: TL, TR, BR, BL by sums and differences."""
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
    """qrep/vision/rectify.py _quad_from_contour at c8e4f8a: the convex hull approximated to 4
    corners, plus the residual normalized by the perimeter."""
    hull = cv2.convexHull(contour)
    peri = cv2.arcLength(hull, True)
    for epsilon_frac in (0.01, 0.02, 0.03, 0.05):
        approx = cv2.approxPolyDP(hull, epsilon_frac * peri, True)
        if len(approx) == 4:
            break
    else:
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
    """qrep/vision/rectify.py _detect_quad at c8e4f8a (tier 0, the renderer's #404040)."""
    distance = np.linalg.norm(image.astype(np.float32) - BACKGROUND_BGR, axis=2)
    mask = (distance > 40).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError("no quilt found: image is entirely background-colored")
    contour = max(contours, key=cv2.contourArea)
    return _quad_from_contour(contour)


def _strip_pixels(image: np.ndarray) -> list[np.ndarray]:
    """qrep/vision/rectify.py _strip_pixels at c8e4f8a."""
    h, w = image.shape[:2]
    t = max(4, int(round(STRIP_FRACTION * min(h, w))))
    return [
        image[:t, :].reshape(-1, 3).astype(np.float32),
        image[h - t :, :].reshape(-1, 3).astype(np.float32),
        image[:, :t].reshape(-1, 3).astype(np.float32),
        image[:, w - t :].reshape(-1, 3).astype(np.float32),
    ]


def _strip_stats(pixels: np.ndarray) -> tuple[np.ndarray, float, float]:
    """qrep/vision/rectify.py _strip_stats at c8e4f8a: (median BGR, MAD, inlier fraction)."""
    median = np.median(pixels, axis=0)
    distances = np.linalg.norm(pixels - median, axis=1)
    mad = float(np.median(distances))
    radius = max(INLIER_RADIUS_FLOOR, INLIER_RADIUS_MADS * mad)
    inlier_fraction = float(np.mean(distances <= radius))
    return median, mad, inlier_fraction


def _inside_bg_fraction(image: np.ndarray, quad: np.ndarray, bg: np.ndarray, tolerance: float) -> float:
    """qrep/vision/rectify.py _inside_bg_fraction at c8e4f8a."""
    mask = np.zeros(image.shape[:2], dtype=np.uint8)
    cv2.fillConvexPoly(mask, quad.astype(np.int32), 255)
    inside = mask > 0
    if not inside.any():
        return 1.0
    distance = np.linalg.norm(image.astype(np.float32) - bg.astype(np.float32), axis=2)
    return float(np.mean(distance[inside] <= tolerance))


def _strip_surface_models(image: np.ndarray) -> list[tuple[np.ndarray, float]]:
    """qrep/vision/rectify.py _strip_surface_models at c8e4f8a."""
    models = []
    for pixels in _strip_pixels(image):
        median, mad, _inlier = _strip_stats(pixels)
        models.append((median, max(INLIER_RADIUS_FLOOR, INLIER_RADIUS_MADS * mad)))
    return models


def _inside_surface_fraction(image: np.ndarray, quad: np.ndarray,
                             models: list[tuple[np.ndarray, float]]) -> float:
    """qrep/vision/rectify.py _inside_surface_fraction at c8e4f8a."""
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


def _best_quad_from_bg_model(image: np.ndarray, bg_bgr, tolerance: float) -> tuple[np.ndarray, float] | None:
    """qrep/vision/rectify.py _best_quad_from_bg_model at c8e4f8a."""
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
    """qrep/vision/rectify.py _tier1_detect at c8e4f8a: (quad, residual, accepted)."""
    strips = _strip_pixels(image)
    stats = [_strip_stats(s) for s in strips]
    uniform = [mad <= UNIFORM_MAD_MAX and inlier >= UNIFORM_INLIER_MIN for _m, mad, inlier in stats]
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


def _grabcut_confidence(compactness: float, residual: float) -> float:
    """qrep/vision/rectify.py _grabcut_confidence at c8e4f8a."""
    return compactness * (1.0 - min(residual * 10.0, 1.0))


def _refine_axis_aligned_quad(image: np.ndarray, quad: np.ndarray, bg: np.ndarray,
                              tolerance: float) -> np.ndarray:
    """qrep/vision/rectify.py _refine_axis_aligned_quad at c8e4f8a."""
    h, w = image.shape[:2]
    x0 = int(np.floor(quad[:, 0].min()))
    x1 = int(np.ceil(quad[:, 0].max()))
    y0 = int(np.floor(quad[:, 1].min()))
    y1 = int(np.ceil(quad[:, 1].max()))
    deviation = float(
        np.abs(quad - np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=np.float64)).max()
    )
    if deviation > IDENTITY_THRESHOLD * 2 * max(h, w):
        return quad
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


def _tier2_grabcut(image: np.ndarray) -> tuple[np.ndarray | None, float, float, bool]:
    """qrep/vision/rectify.py _tier2_grabcut at c8e4f8a: (quad in full-image coordinates,
    residual, confidence, accepted)."""
    h, w = image.shape[:2]
    scale = GRABCUT_LONGEST / max(h, w)
    if scale < 1.0:
        small = cv2.resize(image, (int(round(w * scale)), int(round(h * scale))),
                           interpolation=cv2.INTER_AREA)
    else:
        small = image.copy()
    sh, sw = small.shape[:2]
    t = max(2, int(round(STRIP_FRACTION * min(sh, sw))))

    mask = np.full((sh, sw), cv2.GC_PR_BGD, np.uint8)
    inset_y, inset_x = int(round(0.25 * sh)), int(round(0.25 * sw))
    mask[inset_y : sh - inset_y, inset_x : sw - inset_x] = cv2.GC_PR_FGD
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

    surfaces = _strip_surface_models(small)
    if _inside_surface_fraction(small, quad, surfaces) > INSIDE_BG_MAX:
        bx0 = max(0, int(np.floor(quad[:, 0].min())))
        bx1 = min(sw, int(np.ceil(quad[:, 0].max())))
        by0 = max(0, int(np.floor(quad[:, 1].min())))
        by1 = min(sh, int(np.ceil(quad[:, 1].max())))
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


def _detect_tiered(image: np.ndarray) -> tuple[np.ndarray, float, int, float | None]:
    """qrep/vision/rectify.py _detect_tiered at c8e4f8a: (quad, residual, tier, tier 2
    confidence or None)."""
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


# --- Scoring helpers ----------------------------------------------------------------------


def order_corners(points: np.ndarray) -> np.ndarray:
    return _order_corners(np.asarray(points, dtype=np.float64))


def field_size(corners: np.ndarray) -> tuple[float, float]:
    """The mean of the top and bottom edges by the mean of the left and right (TL, TR, BR, BL)."""
    tl, tr, br, bl = np.asarray(corners, dtype=np.float64)
    width = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    height = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    return float(width), float(height)


def square_size(outer: np.ndarray, field: np.ndarray | None, counts: tuple[int, int],
                bands: Sequence[float]) -> float:
    """Pixels per square: the field's mean edges over the counts; with no field corners, the
    outer edge's over the counts plus each band twice (the bands run all the way round)."""
    nx, ny = counts
    if field is not None:
        width, height = field_size(field)
    else:
        width, height = field_size(outer)
        nx, ny = nx + 2 * sum(bands), ny + 2 * sum(bands)
    return (width / nx + height / ny) / 2


def corner_errors(suggested: np.ndarray, truth: np.ndarray, square: float) -> np.ndarray:
    """Each corner's distance from its truth corner, in squares (TL, TR, BR, BL)."""
    return np.linalg.norm(np.asarray(suggested, float) - np.asarray(truth, float), axis=1) / square


def _percentile(values: Sequence[float], q: float) -> float | None:
    return float(np.percentile(values, q)) if len(values) else None


def summarize_tier(photos: Sequence[np.ndarray | None]) -> dict:
    """One tier's numbers from each photo's four corner errors (None for no suggestion): the
    median and 90th percentile over the suggested corners (linear interpolation), the photos
    with every corner within BAR (a photo with no suggestion is not within), and the photos
    with no suggestion."""
    n = len(photos)
    corners = [float(e) for errors in photos if errors is not None for e in errors]
    within = sum(errors is not None and float(np.max(errors)) <= BAR for errors in photos)
    none = sum(errors is None for errors in photos)
    return {
        "photos": n, "suggested": n - none, "corners": len(corners),
        "median": _percentile(corners, 50), "p90": _percentile(corners, 90),
        "within": within, "none": none,
        "within_rate": within / n if n else None, "none_rate": none / n if n else None,
    }


def decide(tiers: dict[str, dict]) -> bool:
    """Issue #135 criterion 5 as the Go column records it: every tier in TIERS has measured
    corners and a 90th-percentile corner error of at most BAR. A tier with no corners (n = 0)
    or no entry cannot show the bar is met, so it never ships."""
    return all(
        tier in tiers and tiers[tier]["corners"] > 0 and tiers[tier]["p90"] is not None
        and tiers[tier]["p90"] <= BAR
        for tier in TIERS
    )


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval of k successes in n trials (plan section 7.2 asks for it); the
    same formula as scripts/eval/spikes/b1a_counts.py wilson."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


# --- Lines and quads ----------------------------------------------------------------------


def _intersect(a: Sequence[float], b: Sequence[float]) -> np.ndarray | None:
    """Where line a meets line b, each (vx, vy, x0, y0); None when they are parallel."""
    va, pa = np.array(a[:2], float), np.array(a[2:], float)
    vb, pb = np.array(b[:2], float), np.array(b[2:], float)
    det = vb[0] * va[1] - va[0] * vb[1]
    if abs(det) <= 1e-9 * np.linalg.norm(va) * np.linalg.norm(vb):
        return None
    t, _s = np.linalg.solve(np.array([[va[0], -vb[0]], [va[1], -vb[1]]]), pb - pa)
    return pa + t * va


def quad_from_lines(lines: Sequence[Sequence[float]]) -> np.ndarray | None:
    """Corners TL, TR, BR, BL of the top, right, bottom and left lines."""
    top, right, bottom, left = lines
    corners = [_intersect(top, left), _intersect(top, right), _intersect(bottom, right),
               _intersect(bottom, left)]
    if any(c is None for c in corners):
        return None
    return np.array(corners)


def side_lines(points: np.ndarray, quad: np.ndarray) -> list[tuple[float, ...]] | None:
    """A robust (Huber) line through the outline points nearest each side of quad, leaving out
    the CORNER_SKIP share at each end; top, right, bottom, left."""
    starts = quad
    ends = np.roll(quad, -1, axis=0)
    distances, params = [], []
    for a, b in zip(starts, ends):
        seg = b - a
        t = np.clip(((points - a) @ seg) / max(float(seg @ seg), 1e-9), 0.0, 1.0)
        distances.append(np.linalg.norm(points - (a + t[:, None] * seg), axis=1))
        params.append(t)
    nearest = np.argmin(np.stack(distances, axis=1), axis=1)
    lines = []
    for k in range(4):
        chosen = points[(nearest == k) & (params[k] > CORNER_SKIP) & (params[k] < 1 - CORNER_SKIP)]
        if len(chosen) < 2:
            return None
        line = cv2.fitLine(chosen.astype(np.float32), cv2.DIST_HUBER, 0, 0.01, 0.01).ravel()
        lines.append(tuple(float(v) for v in line))
    return lines


# --- The outer-edge methods ---------------------------------------------------------------


class Suggestion(NamedTuple):
    corners: np.ndarray  # TL, TR, BR, BL in the pixels of the image the method was given
    confidence: float  # in [0, 1]; uncalibrated (the report says so)
    tier: int | None  # the old detector's tier, None for the backdrop methods


def _lab(image_bgr: np.ndarray, sigma: float = IMAGE_SIGMA) -> np.ndarray:
    scaled = image_bgr.astype(np.float32) / 255.0
    blurred = cv2.GaussianBlur(scaled, (0, 0), sigma) if sigma > 0 else scaled
    lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2Lab)
    lab[..., 0] *= L_WEIGHT
    return lab


def ring_stats(lab: np.ndarray) -> list[tuple[np.ndarray, float, float, float]]:
    """(median color, MAD, tolerance, inlier share) of each side of the border ring: top,
    bottom, left, right."""
    h, w = lab.shape[:2]
    t = max(3, int(round(RING * min(h, w))))
    stats = []
    for strip in (lab[:t], lab[h - t:], lab[:, :t], lab[:, w - t:]):
        pixels = strip.reshape(-1, 3)
        median = np.median(pixels, axis=0)
        distances = np.linalg.norm(pixels - median, axis=1)
        mad = float(np.median(distances))
        tolerance = max(TOL_FLOOR, TOL_MADS * mad)
        stats.append((median, mad, tolerance, float(np.mean(distances <= tolerance))))
    return stats


def ring_models(lab: np.ndarray) -> list[tuple[np.ndarray, float]]:
    """(median color, tolerance) of each uniform side of the border ring."""
    return [(median, tolerance) for median, mad, tolerance, inliers in ring_stats(lab)
            if mad <= RING_MAD_MAX and inliers >= RING_INLIER_MIN]


def _segment(image_bgr: np.ndarray) -> tuple[tuple[np.ndarray, np.ndarray] | None, str]:
    """The quilt's filled mask (uint8, 255 inside) and its outline points, or None and the
    reason there is no suggestion."""
    lab = _lab(image_bgr)
    h, w = lab.shape[:2]
    models = ring_models(lab)
    if len(models) < MIN_UNIFORM_SIDES:
        return None, "no backdrop: under 2 uniform ring sides"
    near = np.zeros((h, w), bool)
    for median, tolerance in models:
        near |= np.linalg.norm(lab - median, axis=2) <= tolerance
    # The backdrop is the backdrop-colored region connected to the photo's border, so a fabric
    # inside the quilt that matches the backdrop stays quilt.
    _n, labels = cv2.connectedComponents(near.astype(np.uint8), connectivity=4)
    border = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    quilt = (~np.isin(labels, border[border > 0])).astype(np.uint8) * 255
    size = max(3, int(round(OPEN_FRACTION * min(h, w))))
    quilt = cv2.morphologyEx(quilt, cv2.MORPH_OPEN, np.ones((size, size), np.uint8))
    count, labels, stats, _c = cv2.connectedComponentsWithStats(quilt, connectivity=4)
    if count < 2:
        return None, "no component off the backdrop"
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    component = labels == largest
    if not AREA_RANGE[0] <= float(component.mean()) <= AREA_RANGE[1]:
        return None, "component area outside 5 to 98 percent"
    for edge in (component[0], component[-1], component[:, 0], component[:, -1]):
        if float(edge.mean()) > TOUCH_MAX:
            return None, "component touches the photo's border"
    contours, _ = cv2.findContours(component.astype(np.uint8) * 255, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_NONE)
    outline = max(contours, key=cv2.contourArea)
    mask = np.zeros((h, w), np.uint8)
    cv2.drawContours(mask, [outline], -1, 255, thickness=cv2.FILLED)
    return (mask, outline), "segmented"


def segment(image_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    return _segment(image_bgr)[0]


def _accept(mask: np.ndarray, quad: np.ndarray | None) -> tuple[Suggestion | None, str]:
    """A convex quad whose overlap with the mask (intersection over union) is at least FIT_MIN;
    the overlap is its confidence."""
    if quad is None or not np.all(np.isfinite(quad)):
        return None, "no quad from the outline"
    if not cv2.isContourConvex(np.round(quad).astype(np.int32).reshape(-1, 1, 2)):
        return None, "quad not convex"
    filled = np.zeros_like(mask)
    cv2.fillConvexPoly(filled, np.round(quad).astype(np.int32), 255)
    union = int(np.count_nonzero(filled | mask))
    overlap = int(np.count_nonzero(filled & mask)) / union if union else 0.0
    if overlap < FIT_MIN:
        return None, "quad overlap under 0.9"
    return Suggestion(np.asarray(quad, float), float(overlap), None), "suggested"


def _backdrop(image_bgr: np.ndarray, lines: bool) -> tuple[Suggestion | None, str]:
    found, reason = _segment(image_bgr)
    if found is None:
        return None, reason
    mask, outline = found
    quad, _residual = _quad_from_contour(outline)
    if lines:
        fitted = side_lines(outline.reshape(-1, 2).astype(np.float64), quad)
        quad = quad_from_lines(fitted) if fitted else None
    return _accept(mask, quad)


def backdrop_hull(image_bgr: np.ndarray) -> Suggestion | None:
    return _backdrop(image_bgr, lines=False)[0]


def backdrop_lines(image_bgr: np.ndarray) -> Suggestion | None:
    return _backdrop(image_bgr, lines=True)[0]


def tiered(image_bgr: np.ndarray) -> Suggestion | None:
    """The old detector's quad, with tier 3's full frame as no suggestion. Its confidence is
    rectify's residual term for tiers 0 and 1 and the GrabCut confidence for tier 2."""
    quad, residual, tier, grabcut = _detect_tiered(image_bgr)
    if tier == 3:
        return None
    confidence = grabcut if tier == 2 and grabcut is not None else 1.0 - min(residual * 10.0, 1.0)
    return Suggestion(np.asarray(quad, float), float(confidence), int(tier))


METHODS: dict[str, Callable[[np.ndarray], Suggestion | None]] = {
    "backdrop_hull": backdrop_hull,
    "backdrop_lines": backdrop_lines,
    "tiered": tiered,
}


def explain(method: str, image_bgr: np.ndarray) -> tuple[Suggestion | None, str]:
    """A method's suggestion and, when there is none, why."""
    if method == "tiered":
        found = tiered(image_bgr)
        return found, "suggested" if found is not None else "tier 3, the full frame"
    return _backdrop(image_bgr, lines=method == "backdrop_lines")


# --- Band proposals -----------------------------------------------------------------------


def outer_warp(outer: np.ndarray) -> tuple[tuple[int, int], np.ndarray]:
    """The size and homography that warp the outer edge to an upright rectangle, in pixel-edge
    coordinates: the quilt's edge is depth 0 on every side."""
    width, height = field_size(outer)
    size = (int(round(width)), int(round(height)))
    target = np.array([[0, 0], [size[0], 0], [size[0], size[1]], [0, size[1]]], np.float32)
    return size, cv2.getPerspectiveTransform(np.asarray(outer, np.float32), target)


def side_profiles(lab: np.ndarray) -> dict[str, np.ndarray]:
    """Each side's mean color across its middle BAND_SPAN at each depth from the edge inward."""
    h, w = lab.shape[:2]
    depth = int(BAND_DEPTH * min(h, w))
    x0, x1 = int(BAND_SPAN[0] * w), int(BAND_SPAN[1] * w)
    y0, y1 = int(BAND_SPAN[0] * h), int(BAND_SPAN[1] * h)
    return {
        "top": lab[:depth, x0:x1].mean(axis=1),
        "right": lab[y0:y1, ::-1][:, :depth].mean(axis=0),
        "bottom": lab[::-1][:depth, x0:x1].mean(axis=1),
        "left": lab[y0:y1, :depth].mean(axis=0),
    }


def change_points(profile: np.ndarray, window: int) -> list[int]:
    """Depths d (pixel edges) where the mean of the window after d differs most from the mean
    of the window before it: local peaks of at least BAND_FLOOR, kept strongest first at least
    a window apart, at most BAND_K, returned in depth order."""
    n = len(profile)
    strength = np.zeros(n + 1)
    for d in range(window, n - window + 1):
        strength[d] = float(np.linalg.norm(profile[d:d + window].mean(axis=0)
                                           - profile[d - window:d].mean(axis=0)))
    peaks = [d for d in range(window, n - window + 1)
             if strength[d] >= BAND_FLOOR and strength[d] > strength[d - 1]
             and strength[d] >= strength[d + 1]]
    kept: list[int] = []
    for d in sorted(peaks, key=lambda d: (-strength[d], d)):
        if all(abs(d - e) >= window for e in kept):
            kept.append(d)
        if len(kept) == BAND_K:
            break
    return sorted(kept)


def band_proposals(image_bgr: np.ndarray, outer: np.ndarray) -> dict[str, list[int]]:
    """Proposed band edges per side, as depths in pixels of the warped outer edge."""
    size, matrix = outer_warp(outer)
    warped = cv2.warpPerspective(image_bgr, matrix, size, flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_REPLICATE)
    # No blur: each profile point already averages hundreds of pixels, and a blur mixes two
    # fabrics in BGR, whose Lab is not the mean of their Labs, so a field's row means would
    # alternate with the parity of its square rows and fake a change point at every row.
    lab = _lab(warped, sigma=0.0)
    window = max(3, int(round(BAND_WINDOW * min(size))))
    return {side: change_points(profile, window) for side, profile in side_profiles(lab).items()}


def band_truth(outer: np.ndarray, field: np.ndarray | None, counts: tuple[int, int],
               bands: Sequence[float]) -> tuple[float, dict[str, list[float]]]:
    """Square size in the warped outer edge, and each side's true band edges in squares from the
    outer edge: the running sums of the band widths, with the innermost edge (the field's)
    taken from the field corners when they are known, because one width per band cannot say
    that a border is deeper on two sides."""
    size, matrix = outer_warp(outer)
    rect = np.array([[0, 0], [size[0], 0], [size[0], size[1]], [0, size[1]]], float)
    warped_field = (cv2.perspectiveTransform(np.asarray(field, np.float32)[None], matrix)[0]
                    if field is not None else None)
    square = square_size(rect, warped_field, counts, bands)
    edges = list(np.cumsum(bands)) if bands else []
    truth = {}
    for side in SIDES:
        side_edges = [float(e) for e in edges]
        if side_edges and warped_field is not None:
            tl, tr, br, bl = warped_field
            depth = {"top": (tl[1] + tr[1]) / 2, "right": size[0] - (tr[0] + br[0]) / 2,
                     "bottom": size[1] - (bl[1] + br[1]) / 2, "left": (tl[0] + bl[0]) / 2}[side]
            side_edges[-1] = float(depth / square)
        truth[side] = side_edges
    return square, truth


def band_errors(proposals: Sequence[int], truth_edges: Sequence[float], square: float) -> list[float | None]:
    """Each true band edge's distance in squares to its nearest proposal; None with no proposal."""
    if not proposals:
        return [None for _edge in truth_edges]
    depths = np.asarray(proposals, float) / square
    return [float(np.min(np.abs(depths - edge))) for edge in truth_edges]


# --- The corpus run -----------------------------------------------------------------------


@dataclass
class Photo:
    stem: str
    tier: str
    file: str
    sha256: str
    truth: dict[str, dict]  # provenance -> {"outer", "field", "bands", "counts"}


def _corners(frame) -> np.ndarray:
    c = frame.corners
    return np.array([[p.x, p.y] for p in (c.top_left, c.top_right, c.bottom_right, c.bottom_left)])


def dev_split_rows() -> list[dict]:
    """Manifest rows of the v0 eval set in tier A, the museum tier, the holdout still in:
    load_photos drops the holdout before any read. Refusal rows carry no frame to score."""
    with (CORPUS / "manifest.csv").open(encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if row["tier"] == "A" and row["eval_set"] == "v0"]


def load_photos() -> tuple[list[Photo], list[dict]]:
    """The museum dev split with every provenance that gives a frame and counts, and the rows
    skipped with the reason. The holdout is filtered before any read. The screenshot tier has
    no truth on this machine until D3c (#165) lands it, so it loads nothing."""
    sys.path.insert(0, str(REPO / "scripts" / "eval"))
    from qrep_eval import annotation as an

    photos, skipped = [], []
    for row in dev_split_rows():
        stem = Path(row["file"]).stem
        if an.in_holdout(row["sha256"]):
            # Counted, not named: the report never lists holdout photos.
            skipped.append({"stem": None, "tier": "museum", "reason": "holdout"})
            continue
        path = CORPUS / "annotations" / f"{stem}.json"
        doc = an.load(path) if path.exists() else None
        truth = {}
        for prov in PROVENANCES:
            frame = an.pick(doc.frame, (prov,)) if doc else None
            counts = an.pick(doc.counts, (prov,)) if doc else None
            if frame is None or counts is None:
                continue
            outer, field, v = frame.value.outer_edge, frame.value.field, counts.value
            truth[prov] = {
                "outer": _corners(outer),
                "field": _corners(field) if field is not None else None,
                "bands": [b.width_squares for b in outer.bands],
                "counts": (v.blocks_across * v.squares_per_block_across,
                           v.blocks_down * v.squares_per_block_down),
            }
        if truth:
            photos.append(Photo(stem, "museum", row["file"], row["sha256"], truth))
        else:
            skipped.append({"stem": stem, "tier": "museum", "reason": "no frame and counts claims"})
    return photos, skipped


def stage(image: np.ndarray, cap: int) -> tuple[np.ndarray, tuple[float, float]]:
    """The whole photo with its long side capped, and the (x, y) scale from source pixels."""
    h, w = image.shape[:2]
    scale = min(1.0, cap / max(h, w))
    size = (int(round(w * scale)), int(round(h * scale)))
    staged = cv2.resize(image, size, interpolation=cv2.INTER_AREA) if scale < 1 else image.copy()
    return staged, (size[0] / w, size[1] / h)


def _round(values) -> list:
    return [None if v is None else round(float(v), 4) for v in values]


def run_photo(job: tuple[Photo, str]) -> tuple[list[dict], list[dict]]:
    """Every suggestion and band proposal of one photo, scored against each provenance."""
    photo, cache = job
    image = cv2.imread(str(Path(cache) / Path(photo.file).name), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"{photo.stem}: not in the cache")
    corners, bands = [], []
    for cap_name, cap in CAPS.items():
        staged, (sx, sy) = stage(image, cap)
        for method in METHODS:
            found, reason = explain(method, staged)
            ring = ([[round(mad, 2), round(inliers, 3)] for _m, mad, _t, inliers in ring_stats(_lab(staged))]
                    if method != "tiered" else None)
            source = found.corners / [sx, sy] if found is not None else None
            for prov, truth in sorted(photo.truth.items()):
                square = square_size(truth["outer"], truth["field"], truth["counts"], truth["bands"])
                errors = corner_errors(source, truth["outer"], square) if source is not None else None
                corners.append({
                    "photo": photo.stem, "tier": photo.tier, "provenance": prov, "cap": cap_name,
                    "method": method, "square_px": round(square, 3),
                    "staged_px": [staged.shape[1], staged.shape[0]],
                    "suggested": source.round(1).tolist() if source is not None else None,
                    "confidence": round(found.confidence, 4) if found is not None else None,
                    "detector_tier": found.tier if found is not None else None,
                    "reason": reason,
                    "ring_mad_inliers": ring,
                    "errors": _round(errors) if errors is not None else None,
                })
        for prov, truth in sorted(photo.truth.items()):
            if not truth["bands"]:
                continue
            outer = truth["outer"] * [sx, sy]
            field = truth["field"] * [sx, sy] if truth["field"] is not None else None
            square, truth_edges = band_truth(outer, field, truth["counts"], truth["bands"])
            proposals = band_proposals(staged, outer)
            for side in SIDES:
                bands.append({
                    "photo": photo.stem, "tier": photo.tier, "provenance": prov, "cap": cap_name,
                    "side": side, "square_px": round(square, 3),
                    "proposals": _round(np.asarray(proposals[side], float) / square),
                    "truth": _round(truth_edges[side]),
                    "errors": _round(band_errors(proposals[side], truth_edges[side], square)),
                })
    return corners, bands


# --- Report -------------------------------------------------------------------------------


def _band_summary(records: list[dict]) -> dict:
    errors = [e for r in records for e in r["errors"] if e is not None]
    missing = sum(e is None for r in records for e in r["errors"])
    within = sum(e <= BAR for e in errors)
    return {
        "edges": len(errors) + missing, "missing": missing,
        "median": _percentile(errors, 50), "p90": _percentile(errors, 90),
        "within": within,
        "proposals_per_side": (sum(len(r["proposals"]) for r in records) / len(records)
                               if records else None),
        "photos": len({r["photo"] for r in records}),
    }


def build_report(corners: list[dict], bands: list[dict], photos: list[Photo], skipped: list[dict],
                 header: dict) -> dict:
    groups = []
    for prov in PROVENANCES:
        for cap in CAPS:
            for method in METHODS:
                base = [r for r in corners if r["provenance"] == prov and r["cap"] == cap
                        and r["method"] == method]
                if not base:
                    continue
                row: dict = {"provenance": prov, "cap": cap, "method": method}
                for tier in TIERS:
                    chosen = [r for r in base if r["tier"] == tier]
                    row[tier] = summarize_tier(
                        [np.array(r["errors"]) if r["errors"] is not None else None for r in chosen])
                row["go"] = decide({tier: row[tier] for tier in TIERS})
                groups.append(row)
    band_groups = []
    for prov in PROVENANCES:
        for cap in CAPS:
            chosen = [r for r in bands if r["provenance"] == prov and r["cap"] == cap]
            if chosen:
                band_groups.append({"provenance": prov, "cap": cap, **_band_summary(chosen)})
    return {
        "header": header,
        "photos": [{"stem": p.stem, "tier": p.tier, "provenances": sorted(p.truth)} for p in photos],
        "skipped": skipped,
        "screenshot_tier": "no truth on this machine: D3c (#165) has not landed it",
        "groups": groups,
        "band_groups": band_groups,
        "corner_records": corners,
        "band_records": bands,
    }


def _fmt(value: float | None) -> str:
    return f"{value:.3f}" if value is not None else "n/a"


def _share(k: int, n: int) -> str:
    if not n:
        return "n/a (n = 0)"
    lo, hi = wilson(k, n)
    return f"{k}/{n} ({lo:.3f} to {hi:.3f})"


HEADER_END = "<!-- Run header above, generated by scripts/eval/spikes/b1b_corners.py. -->"
GENERATED = "<!-- Generated by scripts/eval/spikes/b1b_corners.py below this line. -->"


def write_markdown(report: dict, path: Path) -> None:
    """Write the run header first and the generated tables last, keeping the hand-written
    reading an existing file holds between the HEADER_END and GENERATED markers. A file without
    both markers is refused, so a rerun never discards the reading."""
    h = report["header"]
    head = [
        "# B1b: outer-edge corner suggestion",
        "",
        f"- Date: {h['date']}",
        f"- Command: `{h['command']}`",
        f"- qrep: `{h['qrep']}`",
        f"- Git SHA: `{h['git_sha']}`"
        + (" with uncommitted changes to tracked files" if h["dirty"] else ", clean tree"),
        f"- cv2 {h['cv2']}, numpy {h['numpy']}, Python {h['python']}",
        f"- Inputs: {h['inputs']}",
        "",
    ]
    lines = [
        "## Decision table (corner error in squares, per tier)",
        "",
        "Percentiles run over the corners of photos with a suggestion. Within 0.22 counts photos "
        "whose every corner is within 0.22 of a square, over all photos (a photo with no "
        "suggestion is not within). Intervals are Wilson 95 percent.",
        "",
        "| Provenance | Cap | Method | Museum photos | No suggestion | Corners | Median | P90 "
        "| Every corner within 0.22 | Screenshot corners | Screenshot p90 | Go |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for g in report["groups"]:
        m, s = g["museum"], g["screenshot"]
        lines.append(
            f"| {g['provenance']} | {g['cap']} | {g['method']} | {m['photos']} "
            f"| {_share(m['none'], m['photos'])} | {m['corners']} | {_fmt(m['median'])} "
            f"| {_fmt(m['p90'])} | {_share(m['within'], m['photos'])} | {s['corners']} "
            f"| {_fmt(s['p90'])} | {'go' if g['go'] else 'no-go'} |")
    lines += [
        "",
        "## Each photo's largest corner error in squares",
        "",
        "none means no suggestion, with its reason; the tiered column names the old "
        "detector's tier.",
        "",
        "| Provenance | Cap | Photo | Square px | backdrop_hull | backdrop_lines | tiered |",
        "|---|---|---|---|---|---|---|",
    ]
    by_key: dict[tuple, dict] = {}
    for r in report["corner_records"]:
        by_key.setdefault((r["provenance"], r["cap"], r["photo"]), {})[r["method"]] = r
    for (prov, cap, stem), methods in by_key.items():
        cells = []
        for method in METHODS:
            r = methods.get(method)
            if r is None or r["errors"] is None:
                cells.append(f"none ({r['reason']})" if r else "none")
                continue
            cell = _fmt(max(r["errors"]))
            cells.append(cell + (f" (tier {r['detector_tier']})" if method == "tiered" else ""))
        square = next(iter(methods.values()))["square_px"]
        lines.append(f"| {prov} | {cap} | {stem} | {square:.1f} | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Band proposals (band-edge error in squares, on the proposed outer edge)",
        "",
        "| Provenance | Cap | Photos | Band edges | No proposal | Median | P90 | Within 0.22 "
        "| Proposals per side |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for g in report["band_groups"]:
        found = g["edges"] - g["missing"]
        lines.append(
            f"| {g['provenance']} | {g['cap']} | {g['photos']} | {g['edges']} | {g['missing']} "
            f"| {_fmt(g['median'])} | {_fmt(g['p90'])} | {_share(g['within'], found)} "
            f"| {_fmt(g['proposals_per_side'])} |")
    lines += [
        "",
        "## Each photo's band edges (desktop cap): truth and nearest proposal error, per side",
        "",
        "| Provenance | Photo | Side | True edges (squares) | Proposals (squares) | Errors |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["band_records"]:
        if r["cap"] != "desktop":
            continue
        lines.append(
            f"| {r['provenance']} | {r['photo']} | {r['side']} | {', '.join(_fmt(v) for v in r['truth'])} "
            f"| {', '.join(_fmt(v) for v in r['proposals']) or 'none'} "
            f"| {', '.join(_fmt(v) for v in r['errors'])} |")
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if existing and not (HEADER_END in existing and GENERATED in existing):
        raise SystemExit(f"{path}: no {HEADER_END!r} and {GENERATED!r} markers; refusing to "
                         "overwrite its hand-written reading")
    kept = existing.split(HEADER_END)[1].split(GENERATED)[0] if existing else "\n\n"
    text = "\n".join(head) + HEADER_END + kept + GENERATED + "\n\n" + "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _git_state() -> tuple[str, bool]:
    """HEAD and whether any tracked file differs from it: the SHA names the code that ran only
    on a clean tree."""
    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                              check=True).stdout.strip()

    return git("rev-parse", "HEAD"), bool(git("status", "--porcelain", "--untracked-files=no"))


def _header(command: str, photos: list[Photo], skipped: list[dict]) -> dict:
    import qrep

    sha, dirty = _git_state()
    rows = dev_split_rows()
    used = ", ".join(p.stem for p in photos)
    holdout = sum(s["reason"] == "holdout" for s in skipped)
    return {
        "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": command, "qrep": _qrep_path(qrep.__file__), "git_sha": sha, "dirty": dirty,
        "cv2": cv2.__version__, "numpy": np.__version__, "python": sys.version.split()[0],
        "inputs": (f"museum tier: corpus/manifest.csv rows of eval_set v0 in tier A, {len(rows)} "
                   f"rows; {holdout} holdout rows skipped before any read; read: {used}. "
                   "Screenshot tier: n = 0, no truth on this machine until D3c (#165)"),
        "caps": CAPS,
    }


def _qrep_path(module_file: str) -> str:
    """The resolved qrep module as <checkout folder>/<path inside it>: the folder's name shows
    which checkout's code ran, and no local folder above it is printed."""
    resolved = Path(module_file).resolve()
    if resolved.is_relative_to(REPO):
        return f"{REPO.name}/{resolved.relative_to(REPO).as_posix()}"
    return f"<outside this checkout>/{resolved.name}"


def _public_arg(arg: str, cache: str) -> str:
    """A command argument as the report prints it: no local path outside the repo."""
    if arg.startswith("--") and "=" in arg:
        key, value = arg.split("=", 1)
        return f"{key}={_public_arg(value, cache)}"
    if arg == cache:
        return "<main checkout>/corpus/private/cache"
    if "/" in arg or "\\" in arg:
        resolved = Path(arg).resolve()
        if resolved.is_relative_to(REPO):
            return resolved.relative_to(REPO).as_posix()
        return f"<local>/{resolved.name}"
    return arg


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", required=True, help="folder holding the cached source images")
    parser.add_argument("--json", default=str(REPO / "docs/sprint-5/evidence/B1b-corner-suggestions.json"))
    parser.add_argument("--md", default=None, help="write the generated tables here")
    # Two workers keep the run under the machine's shared memory budget; one dev photo is
    # about 117 megapixels.
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    exe = Path(sys.executable).resolve()
    python = exe.relative_to(REPO).as_posix() if exe.is_relative_to(REPO) else "python"
    command = f"{python} scripts/eval/spikes/b1b_corners.py " + " ".join(
        _public_arg(a, args.cache) for a in (argv if argv is not None else sys.argv[1:]))
    photos, skipped = load_photos()
    # The header records the checkout as the run starts; a commit, checkout or edit during the
    # run would make it name code that did not run, so the run then writes nothing.
    header = _header(command, photos, skipped)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(run_photo, [(p, args.cache) for p in photos]))
    if _git_state() != (header["git_sha"], header["dirty"]):
        raise SystemExit("the checkout's HEAD or tracked files changed during the run; nothing "
                         "written, because the header would not name the code that ran")
    corners = [r for chunk, _b in results for r in chunk]
    bands = [r for _c, chunk in results for r in chunk]
    report = build_report(corners, bands, photos, skipped, header)
    Path(args.json).write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    if args.md:
        write_markdown(report, Path(args.md))
    for g in report["groups"]:
        m = g["museum"]
        print(f"{g['provenance']:11} {g['cap']:7} {g['method']:14} n={m['photos']} "
              f"none={m['none']} p50={_fmt(m['median'])} p90={_fmt(m['p90'])} "
              f"within={m['within']} go={g['go']}")
    for g in report["band_groups"]:
        print(f"bands {g['provenance']:11} {g['cap']:7} edges={g['edges']} missing={g['missing']} "
              f"p50={_fmt(g['median'])} p90={_fmt(g['p90'])} within={g['within']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
