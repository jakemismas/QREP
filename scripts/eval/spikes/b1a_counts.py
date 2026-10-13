"""B1a spike: count suggestions and the tap-one-square seed (issue #134, plan ticket B1a).

Measures five ways to suggest the square counts of a confirmed field on the v0 dev split:

- autocorr: the existing detector's autocorrelation period (a copy of qrep/vision/grid.py
  _find_pitch on the gray Sobel projection, as estimate_grid builds it), count = extent / pitch.
- seam: a seam-energy scorer, the mean edge energy on the N - 1 seams a count N implies. It is
  reconstructed from the public description of exp9 (plan section 1.2); the prototype's own
  code is not in the repo.
- fit: the exp2 fit score over candidate counts, reconstructed from plan sections 1.2 and B3:
  the seam-to-centre edge ratio times a chroma homogeneity gain (the within-square chroma mean
  absolute deviation of squares shifted by half a pitch over that of aligned squares, so the
  pitch size cancels out of the comparison between counts).
- tap: one tap on a square. The local window's nearest edges bound the square, and the
  window's autocorrelation gives the pitch, then the counts.

Each method ranks counts per axis; joint_ranking pairs the axes under the square-grid prior.
The photo is staged as plan section 2.1 stages it: cropped to the frame plus a margin, then
capped. The field corners move by each jitter radius of plan section 7.2 in random directions
before the warp. Only photos outside the holdout are read (corpus/README.md, holdout rule).

Run (from the worktree root, with the private cache of the main checkout):
  .venv/Scripts/python scripts/eval/spikes/b1a_counts.py --cache <main checkout>/corpus/private/cache
"""

import argparse
import csv
import datetime
import json
import math
import os
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
# The detector envelope: a pitch under 5 px is unresolvable (qrep/vision/grid.py MIN_PITCH_PX
# at 8480443, copied because B6b deletes grid.py).
MIN_PITCH_PX = 5
# estimate_grid searches pitches up to extent // 4, so at least 4 squares per axis; one or two
# seam samples make the scores of 2 and 3 noise, and no tier A quilt has fewer than 11.
MIN_COUNT = 4
# Plan section 7.2: until D10 measures the pin radius, report at 0, 2, 4, 6 and 8 px.
RADII = (0, 2, 4, 6, 8)
# Spike choice: 20 seeded trials per nonzero radius (exp1 used 60 on one photo; 11 photos here).
TRIALS = 20
# web/src/model/downscale.ts: CAP_PHONE and CAP_DESKTOP, the long-side caps of a staged photo.
CAPS = {"phone": 1400, "desktop": 2000}
# Spike choice: plan section 2.1 crops to the frame "plus a margin" without a number.
CROP_MARGIN = 0.05
# Plan section 5.B: L*0.5 is the default color distance.
L_WEIGHT = 0.5
# Spike choices for the edge profile: a light blur before the color gradient, and a profile
# smoothing that keeps a seam sample tolerant to a pixel of misregistration.
IMAGE_SIGMA = 1.0
PROFILE_SIGMA = 1.5
# Spike choices for the homogeneity samples: the inner 70 percent of a square, 5 samples per
# side, on 32 lines per axis for the per-axis ranking.
INNER = (0.15, 0.85)
SAMPLES = 5
LINES = 32
# Lab units added to both chroma deviations, so a flat synthetic square cannot divide by zero.
MAD_EPS = 0.5
# Spike choice: the square-grid prior. Tier A is one uniform square grid (corpus/README.md), so
# the two pitches of a pair agree up to perspective and piecing error; 15 percent is generous.
PITCH_PRIOR = 1.15
# Spike choices for the tap: the local window's half-size as a share of the shorter side; the
# L*0.5 color distance within which a pixel belongs to the tapped fabric; and the pitch search
# range as a share of the tapped region's size (it may be the square, a run of squares, or a
# print-split part of one).
TAP_WINDOW = 0.15
TAP_TOLERANCE = 10.0
TAP_RANGE = (0.5, 2.0)
# grid.py's fundamental rule: the smallest lag at least half as strong as the strongest.
FUNDAMENTAL_FACTOR = 0.5
# Fabric labels for the block period of a candidate: k-means over the squares' colors.
KMEANS_K = 3
# Issue #134 criterion 6: a method ships when its top-3 recall is at least 0.8.
BAR = 0.8
TOP_K = 3
PROVENANCES = ("verified-jake", "proposed-a", "proposed-b")


# --- Copies from modules B6b deletes ------------------------------------------------------
# B6b deletes qrep/vision/grid.py and qrep/vision/repeats.py (plan B6b), so the spike and its
# tests carry the few helpers its methods call, copied from commit 8480443 with their logic
# unchanged. The check that the copies are faithful is a rerun: the trials are seeded, so the
# rerun must reproduce the recorded run's JSON group for group.


def _autocorrelate(profile: np.ndarray) -> np.ndarray:
    """qrep/vision/grid.py _autocorrelate at 8480443."""
    centered = profile - profile.mean()
    corr = np.correlate(centered, centered, mode="full")[len(centered) - 1 :]
    if corr[0] <= 0:
        return np.zeros_like(corr)
    return corr / corr[0]


def _binarize(profile: np.ndarray) -> np.ndarray:
    """qrep/vision/grid.py _binarize at 8480443: an equal-weight spike train of edge locations,
    so the fundamental pitch peaks as strongly as its multiples."""
    threshold = profile.mean() + profile.std()
    spikes = np.zeros_like(profile)
    for i in range(1, len(profile) - 1):
        if profile[i] > threshold and profile[i] >= profile[i - 1] and profile[i] >= profile[i + 1]:
            spikes[i] = 1.0
    # Dilate by one pixel to absorb random half-pixel edge jitter.
    return np.minimum(spikes + np.roll(spikes, 1) + np.roll(spikes, -1), 1.0)


def _find_pitch(profile: np.ndarray, max_pitch: int) -> tuple[float, float]:
    """qrep/vision/grid.py _find_pitch at 8480443: the fundamental repeat distance and its
    normalized peak prominence."""
    corr = _autocorrelate(_binarize(profile))
    lo, hi = MIN_PITCH_PX, min(max_pitch, len(corr) - 1)
    window = corr[lo:hi]
    if window.size == 0:
        raise ValueError("profile too short for grid detection")
    # Local maxima only, so a slow downward ramp does not win.
    peaks = [
        i
        for i in range(1, window.size - 1)
        if window[i] >= window[i - 1] and window[i] >= window[i + 1] and window[i] > 0
    ]
    if not peaks:
        raise ValueError("no periodicity found in edge profile")
    strongest = max(window[i] for i in peaks)
    # The smallest comparably strong lag is the fundamental, not a harmonic.
    fundamental = next(i for i in peaks if window[i] >= 0.5 * strongest)
    pitch = float(lo + fundamental)
    i = lo + fundamental
    if 1 <= i < len(corr) - 1:
        denom = corr[i - 1] - 2 * corr[i] + corr[i + 1]
        if abs(denom) > 1e-9:
            shift = 0.5 * (corr[i - 1] - corr[i + 1]) / denom
            pitch += float(np.clip(shift, -0.5, 0.5))
    # A systematic pitch alternation plateaus the fundamental peak; the harmonic average
    # replaces the parabolic estimate only when the two disagree by more than 1 percent.
    base = lo + fundamental
    harmonic_estimates: list[float] = []
    for k in range(2, 7):
        center = k * base
        if center + 2 >= len(corr):
            break
        lo_k, hi_k = center - 2, center + 3
        segment = corr[lo_k:hi_k]
        peak_at = lo_k + int(np.argmax(segment))
        if corr[peak_at] > 0:
            harmonic_estimates.append(peak_at / k)
    if harmonic_estimates:
        harmonic = float(np.mean(harmonic_estimates))
        if abs(harmonic - pitch) / max(harmonic, 1e-9) > 0.01:
            pitch = harmonic
    prominence = float(max(0.0, min(1.0, corr[i])))
    return pitch, prominence


# qrep/vision/repeats.py MATCH_THRESHOLD and SOFT_FACTOR at 8480443: an exact repeat tolerates
# a stray cell, and the soft vote takes the smallest period within 5 percent of the best.
MATCH_THRESHOLD = 0.999
SOFT_FACTOR = 0.95


class RepeatResult(NamedTuple):
    """qrep/vision/repeats.py RepeatResult at 8480443, a NamedTuple here instead of a pydantic
    model; the fields and their values are the same."""

    period_rows: int  # 0 when no repeat found
    period_cols: int
    confidence: float


def _axis_period(grid: np.ndarray, axis: int) -> tuple[int, float]:
    """qrep/vision/repeats.py _axis_period at 8480443."""
    n = grid.shape[axis]
    scores: list[tuple[int, float]] = []
    for shift in range(1, n // 2 + 1):
        if axis == 0:
            a, b = grid[:-shift, :], grid[shift:, :]
        else:
            a, b = grid[:, :-shift], grid[:, shift:]
        score = float(np.mean(a == b))
        if score >= MATCH_THRESHOLD:
            return shift, score
        scores.append((shift, score))
    if not scores:
        return 0, 0.0
    best_score = max(score for _shift, score in scores)
    if best_score <= 0:
        return 0, 0.0
    for shift, score in scores:
        if score >= SOFT_FACTOR * best_score:
            return shift, score
    return 0, 0.0


def detect_repeat(assignments: list[list[int]]) -> RepeatResult:
    """qrep/vision/repeats.py detect_repeat at 8480443."""
    grid = np.array(assignments)
    period_rows, score_rows = _axis_period(grid, 0)
    period_cols, score_cols = _axis_period(grid, 1)
    return RepeatResult(
        period_rows=period_rows,
        period_cols=period_cols,
        confidence=float(min(score_rows, score_cols)),
    )


# --- Scoring helpers ----------------------------------------------------------------------


class Outcome(NamedTuple):
    top1: bool
    top3: bool
    harmonic: bool


def _axis_harmonic(candidate: int, truth: int) -> bool:
    return candidate > 0 and candidate != truth and (truth % candidate == 0 or candidate % truth == 0)


def score_ranking(ranking: Sequence, truth) -> Outcome:
    """Top-1 hit, top-3 hit and harmonic top-1 of a ranking of counts or of (x, y) pairs.

    A pair's top-1 is harmonic when it is wrong and each wrong axis divides, or is a multiple
    of, that axis's truth."""
    ranking = list(ranking)
    if not ranking:
        return Outcome(False, False, False)
    first = ranking[0]
    top1 = first == truth
    top3 = truth in ranking[:TOP_K]
    if isinstance(truth, tuple):
        harmonic = not top1 and all(c == t or _axis_harmonic(c, t) for c, t in zip(first, truth))
    else:
        harmonic = _axis_harmonic(first, truth)
    return Outcome(top1, top3, harmonic)


def quilter_units(count: int, period: int) -> tuple[int, int]:
    """(blocks, squares per block) of an axis with count squares and a block period in squares."""
    # A repeat of two alternating blocks (10 squares) in 55 squares means blocks of
    # gcd(10, 55) = 5, so the block is the common divisor, not the repeat.
    block = math.gcd(period, count)
    if 1 < block < count:
        return count // block, block
    return 1, count


def harmonic_alternates(count: int, lo: int, hi: int) -> list[int]:
    """The divisors of count other than 1 and itself, and its double and triple, in [lo, hi]."""
    divisors = [count // k for k in range(2, count + 1) if count % k == 0 and count // k > 1]
    multiples = [count * k for k in (2, 3)]
    return sorted(n for n in set(divisors + multiples) if lo <= n <= hi and n != count)


def is_periodic(blocks_across: int, blocks_down: int) -> bool:
    return blocks_across > 1 or blocks_down > 1


def joint_ranking(
    ranking_x: Sequence[int], ranking_y: Sequence[int], width: float, height: float,
    k: int = TOP_K, prior: float = PITCH_PRIOR, depth: int = 10,
) -> list[tuple[int, int]]:
    """Pairs from the first depth counts of each axis whose pitches agree within prior, by
    rank sum, then the larger rank, then the x rank."""
    pairs = []
    for rx, nx in enumerate(ranking_x[:depth]):
        for ry, ny in enumerate(ranking_y[:depth]):
            px, py = width / nx, height / ny
            if max(px, py) / min(px, py) <= prior:
                pairs.append(((rx + ry, max(rx, ry), rx), (nx, ny)))
    pairs.sort()
    return [pair for _key, pair in pairs[:k]]


def summarize(outcomes: Sequence[Outcome]) -> dict:
    n = len(outcomes)
    counts = {key: sum(getattr(o, key) for o in outcomes) for key in ("top1", "top3", "harmonic")}
    summary: dict = {"n": n, **counts}
    for key, value in counts.items():
        summary[f"{key}_rate"] = value / n if n else None
    return summary


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval of k successes in n trials (plan section 7.2 asks for it)."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def pair(fit: dict[str, float]) -> tuple[float, float]:
    return fit["edge_ratio"], fit["mad"]


def two_part_rejects(wrong: tuple[float, float], truths: Sequence[tuple[float, float]]) -> bool:
    """exp2's check as plan B3 states it, two scores with one threshold each, set where every
    truth passes: a (seam-to-centre ratio, within-square chroma MAD) pair is rejected when its
    ratio is below every truth's or its MAD is above every truth's."""
    return wrong[0] < min(t[0] for t in truths) or wrong[1] > max(t[1] for t in truths)


def decide_two_part(top3_recall: float | None, rejected: Sequence[bool]) -> bool:
    """Issue #134 criterion 6 as the Go column records it: top-3 recall at least BAR, and the
    two-part fit rule rejects every wrong top-1. rejected holds one flag per wrong top-1, so a
    method with no wrong top-1 has nothing to reject; a group with no trials has no recall
    (summarize gives None) and never ships."""
    return top3_recall is not None and top3_recall >= BAR and all(rejected)


def decide(top3_recall: float, wrong_fits: Sequence[float], truth_fits: Sequence[float]) -> bool:
    """The product reading of criterion 6 (go_product in the JSON): one threshold on the
    product fit passes every true count and rejects every wrong top-1 (each wrong top-1 fits
    worse than the worst truth)."""
    if top3_recall < BAR:
        return False
    return not wrong_fits or max(wrong_fits) < min(truth_fits)


# --- Geometry -----------------------------------------------------------------------------


def jitter_corners(corners: np.ndarray, radius: float, rng: np.random.Generator) -> np.ndarray:
    """Each corner moved radius px in its own uniformly random direction."""
    theta = rng.uniform(0.0, 2.0 * math.pi, size=len(corners))
    if radius == 0:
        return corners.copy()
    return corners + radius * np.stack([np.cos(theta), np.sin(theta)], axis=1)


def field_size(corners: np.ndarray) -> tuple[int, int]:
    """Warp size: the mean of the top and bottom edges by the mean of the left and right."""
    tl, tr, br, bl = corners
    width = (np.linalg.norm(tr - tl) + np.linalg.norm(br - bl)) / 2
    height = (np.linalg.norm(bl - tl) + np.linalg.norm(br - tr)) / 2
    return int(round(width)), int(round(height))


def _homography(corners: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    width, height = size
    target = np.array([[0, 0], [width, 0], [width, height], [0, height]], np.float32)
    return cv2.getPerspectiveTransform(corners.astype(np.float32), target)


def _map_point(matrix: np.ndarray, point: Sequence[float]) -> np.ndarray:
    return cv2.perspectiveTransform(np.array([[point]], np.float32), matrix)[0, 0].astype(float)


def _smooth(profile: np.ndarray, sigma: float) -> np.ndarray:
    radius = int(math.ceil(3 * sigma))
    kernel = cv2.getGaussianKernel(2 * radius + 1, sigma).ravel()
    return np.convolve(np.pad(profile, radius, mode="edge"), kernel, mode="valid")


def _sample(profile: np.ndarray, positions: np.ndarray) -> np.ndarray:
    return np.interp(positions, np.arange(len(profile)), profile)


@dataclass
class FieldImage:
    """A field warped to a rectangle, with the profiles the methods read.

    Coordinates are pixel edges: pixel i covers [i, i + 1), so the seam between squares k and
    k + 1 of N across width W sits at x = (k + 1) W / N, and edge[x] is the color step there."""

    bgr: np.ndarray
    lab: np.ndarray  # L scaled by L_WEIGHT, then a and b
    edge_x: np.ndarray  # length W + 1, smoothed mean color step at each column edge
    edge_y: np.ndarray
    sobel_x: np.ndarray  # |Sobel| of gray, as estimate_grid computes it
    sobel_y: np.ndarray
    matrix: np.ndarray  # staged image to field

    @property
    def width(self) -> int:
        return self.bgr.shape[1]

    @property
    def height(self) -> int:
        return self.bgr.shape[0]

    @classmethod
    def from_bgr(cls, image_bgr: np.ndarray, corners: np.ndarray) -> "FieldImage":
        size = field_size(corners)
        matrix = _homography(corners, size)
        bgr = cv2.warpPerspective(image_bgr, matrix, size, flags=cv2.INTER_LINEAR,
                                  borderMode=cv2.BORDER_REPLICATE)
        blurred = cv2.GaussianBlur(bgr.astype(np.float32) / 255.0, (0, 0), IMAGE_SIGMA)
        lab = cv2.cvtColor(blurred, cv2.COLOR_BGR2Lab)
        lab[..., 0] *= L_WEIGHT
        width, height = size
        step_x = np.linalg.norm(lab[:, 1:] - lab[:, :-1], axis=2).mean(axis=0)
        step_y = np.linalg.norm(lab[1:] - lab[:-1], axis=2).mean(axis=1)
        edge_x = np.zeros(width + 1)
        edge_y = np.zeros(height + 1)
        edge_x[1:width] = step_x
        edge_y[1:height] = step_y
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        return cls(
            bgr=bgr, lab=lab,
            edge_x=_smooth(edge_x, PROFILE_SIGMA), edge_y=_smooth(edge_y, PROFILE_SIGMA),
            sobel_x=np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)),
            sobel_y=np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)),
            matrix=matrix,
        )

    def axis(self, axis: int) -> tuple[int, np.ndarray]:
        return (self.width, self.edge_x) if axis == 0 else (self.height, self.edge_y)

    def lines(self, axis: int) -> np.ndarray:
        """LINES evenly spaced lines of (a, b) across the axis: (LINES, extent, 2)."""
        ab = self.lab[..., 1:]
        if axis == 0:
            rows = ((np.arange(LINES) + 0.5) * self.height / LINES).astype(int)
            return ab[rows]
        cols = ((np.arange(LINES) + 0.5) * self.width / LINES).astype(int)
        return ab[:, cols].transpose(1, 0, 2)


def candidate_counts(extent: int) -> range:
    return range(MIN_COUNT, max(MIN_COUNT, extent // MIN_PITCH_PX) + 1)


def _rank(scores: dict[int, float]) -> list[int]:
    return sorted(scores, key=lambda n: (-scores[n], n))


# --- Methods ------------------------------------------------------------------------------


def _seam_axis(field: FieldImage, axis: int) -> list[int]:
    extent, edge = field.axis(axis)
    return _rank({
        n: float(_sample(edge, extent * np.arange(1, n) / n).mean()) for n in candidate_counts(extent)
    })


def seam_energy(field: FieldImage) -> tuple[list[int], list[int]]:
    return _seam_axis(field, 0), _seam_axis(field, 1)


def _autocorr_axis(field: FieldImage, axis: int) -> list[int]:
    extent = field.width if axis == 0 else field.height
    profile = field.sobel_x.sum(axis=0) if axis == 0 else field.sobel_y.sum(axis=1)
    try:
        pitch, _prominence = _find_pitch(profile, max_pitch=extent // 4)
    except ValueError:
        return []
    corr = _autocorrelate(_binarize(profile))
    counts = candidate_counts(extent)
    first = min(max(int(round(extent / pitch)), counts.start), counts.stop - 1)
    scores = {n: float(_sample(corr, np.array([extent / n]))[0]) for n in counts if n != first}
    return [first] + _rank(scores)


def autocorr_period(field: FieldImage) -> tuple[list[int], list[int]]:
    return _autocorr_axis(field, 0), _autocorr_axis(field, 1)


def _segment_mad(lines: np.ndarray, positions: np.ndarray) -> float:
    """Median over lines and segments of the chroma mean absolute deviation inside a segment.

    positions is (segments, SAMPLES) in pixel-edge coordinates along the lines."""
    if positions.size == 0:
        return 0.0
    index = np.clip(np.floor(positions).astype(int), 0, lines.shape[1] - 1)
    values = lines[:, index]  # (lines, segments, SAMPLES, 2)
    deviation = np.linalg.norm(values - values.mean(axis=2, keepdims=True), axis=3)
    return float(np.median(deviation.mean(axis=2)))


def _offsets() -> np.ndarray:
    return INNER[0] + (INNER[1] - INNER[0]) * np.arange(SAMPLES) / (SAMPLES - 1)


def _edge_ratio(edge: np.ndarray, seams: np.ndarray, centres: np.ndarray) -> float:
    delta = 0.05 * float(edge.mean()) + 1e-6
    return (float(seams.mean()) + delta) / (float(centres.mean()) + delta)


def _fit_axis(field: FieldImage, axis: int, interior: bool = False) -> list[int]:
    extent, edge = field.axis(axis)
    lines = field.lines(axis)
    offsets = _offsets()
    scores = {}
    for n in candidate_counts(extent):
        pitch = extent / n
        seams = _sample(edge, pitch * np.arange(1, n))
        aligned = pitch * (np.arange(n)[:, None] + offsets[None, :])
        # exp2 samples each square's centre; the interior variant samples its inner 70 percent,
        # so a block-sized candidate whose centre lands inside a flat square still sees the
        # seams inside its blocks.
        centres = _sample(edge, aligned.ravel() if interior else pitch * (np.arange(n) + 0.5))
        shifted = pitch * (np.arange(n - 1)[:, None] + 0.5 + offsets[None, :])
        gain = (_segment_mad(lines, shifted) + MAD_EPS) / (_segment_mad(lines, aligned) + MAD_EPS)
        scores[n] = _edge_ratio(edge, seams, centres) * gain
    return _rank(scores)


def fit_score(field: FieldImage) -> tuple[list[int], list[int]]:
    return _fit_axis(field, 0), _fit_axis(field, 1)


def fit_interior(field: FieldImage) -> tuple[list[int], list[int]]:
    return _fit_axis(field, 0, interior=True), _fit_axis(field, 1, interior=True)


def _square_mad(ab: np.ndarray, xs: np.ndarray, ys: np.ndarray) -> float:
    """Median over squares of the chroma mean absolute deviation of SAMPLES x SAMPLES samples;
    xs is (columns, SAMPLES) and ys is (rows, SAMPLES) in pixel-edge coordinates."""
    if xs.size == 0 or ys.size == 0:
        return 0.0
    xi = np.clip(np.floor(xs).astype(int), 0, ab.shape[1] - 1)
    yi = np.clip(np.floor(ys).astype(int), 0, ab.shape[0] - 1)
    values = ab[yi[:, None, :, None], xi[None, :, None, :]]  # (rows, cols, S, S, 2)
    values = values.reshape(len(yi), len(xi), -1, 2)
    deviation = np.linalg.norm(values - values.mean(axis=2, keepdims=True), axis=3)
    return float(np.median(deviation.mean(axis=2)))


def fit_2d(field: FieldImage, nx: int, ny: int) -> dict[str, float]:
    """The whole-field fit of a pair: exp2's seam-to-centre ratio and median within-square
    chroma deviation, the shifted-square homogeneity gain, and their product (the fit)."""
    px, py = field.width / nx, field.height / ny
    seams = np.concatenate([_sample(field.edge_x, px * np.arange(1, nx)),
                            _sample(field.edge_y, py * np.arange(1, ny))])
    centres = np.concatenate([_sample(field.edge_x, px * (np.arange(nx) + 0.5)),
                              _sample(field.edge_y, py * (np.arange(ny) + 0.5))])
    edge = np.concatenate([field.edge_x, field.edge_y])
    ratio = _edge_ratio(edge, seams, centres)
    ab = field.lab[..., 1:]
    offsets = _offsets()
    mad = _square_mad(ab, px * (np.arange(nx)[:, None] + offsets), py * (np.arange(ny)[:, None] + offsets))
    shifted = _square_mad(ab, px * (np.arange(nx - 1)[:, None] + 0.5 + offsets),
                          py * (np.arange(ny - 1)[:, None] + 0.5 + offsets))
    gain = (shifted + MAD_EPS) / (mad + MAD_EPS)
    return {"edge_ratio": ratio, "mad": mad, "chroma_gain": gain, "fit": ratio * gain}


def _refine_lag(corr: np.ndarray, lag: int, harmonics: int = 8) -> float:
    """Sub-pixel pitch from the harmonics, after grid._find_pitch's harmonic average but not
    the same rule: a parabola through every harmonic's peak, each searched near k times the
    running estimate, and the mean of peak / k always replaces the integer lag."""
    estimates: list[float] = []
    estimate = float(lag)
    for k in range(1, harmonics + 1):
        centre = int(round(k * estimate))
        if centre + 3 >= len(corr):
            break
        lo = max(1, centre - 2)
        i = lo + int(np.argmax(corr[lo:centre + 3]))
        if corr[i] <= 0:
            break
        denom = corr[i - 1] - 2 * corr[i] + corr[i + 1]
        shift = 0.5 * (corr[i - 1] - corr[i + 1]) / denom if abs(denom) > 1e-9 else 0.0
        estimates.append((i + float(np.clip(shift, -0.5, 0.5))) / k)
        estimate = float(np.mean(estimates))
    return estimate


def tap_region(field: FieldImage, tap: Sequence[float]) -> tuple[float | None, float | None]:
    """Width and height of the 4-connected same-fabric region under the tap: the tapped square,
    a run of same-fabric squares, or a print-split part of one. An axis whose region spans half
    the field or more (a background fabric) gives None."""
    lab = cv2.GaussianBlur(field.lab, (0, 0), 2.0)
    x = int(np.clip(tap[0], 0, field.width - 1))
    y = int(np.clip(tap[1], 0, field.height - 1))
    seed = np.median(lab[max(0, y - 2):y + 3, max(0, x - 2):x + 3].reshape(-1, 3), axis=0)
    mask = (np.linalg.norm(lab - seed, axis=2) < TAP_TOLERANCE).astype(np.uint8)
    _n, labels, stats, _c = cv2.connectedComponentsWithStats(mask, connectivity=4)
    label = labels[y, x]
    if label == 0:
        return None, None
    width, height = float(stats[label, cv2.CC_STAT_WIDTH]), float(stats[label, cv2.CC_STAT_HEIGHT])
    return (width if width < field.width / 2 else None,
            height if height < field.height / 2 else None)


def _tap_axis(profile: np.ndarray, bracket: float | None, extent: int) -> list[int]:
    corr = _autocorrelate(_binarize(profile))
    lo, hi = (TAP_RANGE[0] * bracket, TAP_RANGE[1] * bracket) if bracket else (0, len(corr))
    lags = [i for i in range(max(MIN_PITCH_PX, int(math.ceil(lo))), len(corr) - 1)
            if i <= hi and corr[i] > 0 and corr[i] >= corr[i - 1] and corr[i] >= corr[i + 1]]
    if lags:
        strongest = max(corr[i] for i in lags)
        pitch = _refine_lag(corr, next(i for i in lags if corr[i] >= FUNDAMENTAL_FACTOR * strongest))
    elif bracket and bracket >= MIN_PITCH_PX:
        pitch = bracket
    else:
        return []
    estimate = extent / pitch
    nearest = int(round(estimate))
    second = nearest + 1 if estimate > nearest else nearest - 1
    third = 2 * nearest - second
    return [n for n in (nearest, second, third) if n >= MIN_COUNT]


def tap_seed(field: FieldImage, tap: Sequence[float]) -> tuple[list[int], list[int]]:
    """Counts from one tap at field coordinates tap = (x, y): the tapped region's size bounds
    the pitch, and the local window's autocorrelation sets it."""
    bracket_x, bracket_y = tap_region(field, tap)
    half = max(4 * MIN_PITCH_PX, int(round(TAP_WINDOW * min(field.width, field.height))),
               int(3 * max(bracket_x or 0, bracket_y or 0)))
    x0, x1 = max(0, int(tap[0]) - half), min(field.width, int(tap[0]) + half)
    y0, y1 = max(0, int(tap[1]) - half), min(field.height, int(tap[1]) + half)
    if x1 - x0 < 4 * MIN_PITCH_PX or y1 - y0 < 4 * MIN_PITCH_PX:
        return [], []
    local_x = field.sobel_x[y0:y1, x0:x1].sum(axis=0)
    local_y = field.sobel_y[y0:y1, x0:x1].sum(axis=1)
    return _tap_axis(local_x, bracket_x, field.width), _tap_axis(local_y, bracket_y, field.height)


METHODS: dict[str, Callable[[FieldImage], tuple[list[int], list[int]]]] = {
    "autocorr": autocorr_period,
    "seam": seam_energy,
    "fit": fit_score,
    "fit_interior": fit_interior,
}
# Functions of modules B6b deletes (plan B6b; REBASELINE.md "detector (B6b)") that each method
# uses, through the copies above: the list a shipping method would hand B7 (issue #134,
# criterion 7).
B6B_FUNCTIONS = {
    "autocorr": ["qrep.vision.grid._find_pitch", "qrep.vision.grid._autocorrelate",
                 "qrep.vision.grid._binarize", "qrep.vision.grid.MIN_PITCH_PX"],
    "seam": ["qrep.vision.grid.MIN_PITCH_PX"],
    "fit": ["qrep.vision.grid.MIN_PITCH_PX"],
    "fit_interior": ["qrep.vision.grid.MIN_PITCH_PX"],
    "tap": ["qrep.vision.grid._autocorrelate", "qrep.vision.grid._binarize",
            "qrep.vision.grid.MIN_PITCH_PX"],
    "quilter_units": ["qrep.vision.repeats.detect_repeat", "qrep.vision.repeats._axis_period"],
}


def block_periods(field: FieldImage, nx: int, ny: int) -> tuple[int, int]:
    """(columns, rows) block period in squares: detect_repeat (the copy above) on k-means
    labels of the squares' inner colors."""
    px, py = field.width / nx, field.height / ny
    offsets = _offsets()
    xi = np.clip(np.floor(px * (np.arange(nx)[:, None] + offsets)).astype(int), 0, field.width - 1)
    yi = np.clip(np.floor(py * (np.arange(ny)[:, None] + offsets)).astype(int), 0, field.height - 1)
    colors = field.lab[yi[:, None, :, None], xi[None, :, None, :]].reshape(ny, nx, -1, 3).mean(axis=2)
    k = min(KMEANS_K, nx * ny)
    cv2.setRNGSeed(0)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 50, 0.1)
    _c, labels, _centres = cv2.kmeans(colors.reshape(-1, 3).astype(np.float32), k, None, criteria,
                                      3, cv2.KMEANS_PP_CENTERS)
    result = detect_repeat(labels.reshape(ny, nx).tolist())
    return result.period_cols, result.period_rows


# --- The corpus run -----------------------------------------------------------------------


@dataclass
class Photo:
    stem: str
    tier: str
    file: str
    sha256: str
    truth: dict[str, dict]  # provenance -> {"counts": (bx, sx, by, sy), "field": 4x2, "outer": 4x2}


def _corners(frame) -> np.ndarray:
    c = frame.corners
    return np.array([[p.x, p.y] for p in (c.top_left, c.top_right, c.bottom_right, c.bottom_left)])


def dev_split_rows() -> list[dict]:
    """Manifest rows of the v0 eval set in tiers A and B, the holdout still in: the dev split is
    the v0 eval set outside the holdout (corpus/README.md), and load_photos drops the holdout
    before any read. A tier B row counts only when it is in v0."""
    with (CORPUS / "manifest.csv").open(encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle)
                if row["tier"] in ("A", "B") and row["eval_set"] == "v0"]


def load_photos() -> tuple[list[Photo], list[dict]]:
    """The dev split's photos, with every provenance that gives a field and counts; and the rows
    skipped, with the reason. The holdout is filtered before any read."""
    sys.path.insert(0, str(REPO / "scripts" / "eval"))
    from qrep_eval import annotation as an

    photos, skipped = [], []
    for row in dev_split_rows():
        stem = Path(row["file"]).stem
        if an.in_holdout(row["sha256"]):
            # Counted, not named: the report never lists holdout photos.
            skipped.append({"stem": None, "tier": row["tier"], "reason": "holdout"})
            continue
        path = CORPUS / "annotations" / f"{stem}.json"
        doc = an.load(path) if path.exists() else None
        truth = {}
        for prov in PROVENANCES:
            frame = an.pick(doc.frame, (prov,)) if doc else None
            counts = an.pick(doc.counts, (prov,)) if doc else None
            if frame is None or counts is None:
                continue
            outer = frame.value.outer_edge
            field = frame.value.field
            if field is None and outer.bands:
                skipped.append({"stem": stem, "tier": row["tier"], "reason": f"{prov}: no field corners"})
                continue
            v = counts.value
            truth[prov] = {
                "counts": (v.blocks_across, v.squares_per_block_across, v.blocks_down,
                           v.squares_per_block_down),
                "field": _corners(field if field is not None else outer),
                "outer": _corners(outer),
            }
        if truth:
            photos.append(Photo(stem, row["tier"], row["file"], row["sha256"], truth))
        else:
            skipped.append({"stem": stem, "tier": row["tier"], "reason": "no frame and counts claims"})
    return photos, skipped


def stage(image: np.ndarray, outer: np.ndarray, field: np.ndarray, cap: int) -> tuple[np.ndarray, np.ndarray]:
    """Crop to the outer frame plus a margin at full resolution, then cap the long side
    (plan section 2.1); returns the staged image and the field corners in its pixels."""
    x0, y0 = outer.min(axis=0)
    x1, y1 = outer.max(axis=0)
    margin = CROP_MARGIN * max(x1 - x0, y1 - y0)
    h, w = image.shape[:2]
    cx0, cy0 = int(max(0, x0 - margin)), int(max(0, y0 - margin))
    cx1, cy1 = int(min(w, x1 + margin)), int(min(h, y1 + margin))
    crop = image[cy0:cy1, cx0:cx1]
    scale = min(1.0, cap / max(crop.shape[:2]))
    size = (int(round(crop.shape[1] * scale)), int(round(crop.shape[0] * scale)))
    staged = cv2.resize(crop, size, interpolation=cv2.INTER_AREA) if scale < 1 else crop.copy()
    sx, sy = size[0] / crop.shape[1], size[1] / crop.shape[0]
    return staged, (field - [cx0, cy0]) * [sx, sy]


def _rankings(field: FieldImage, method: str, tap: Sequence[float] | None):
    return tap_seed(field, tap) if method == "tap" else METHODS[method](field)


def run_photo(job: tuple[Photo, str, str]) -> list[dict]:
    """Every trial of one photo, one provenance and the cache folder."""
    photo, prov, cache = job
    image = cv2.imread(str(Path(cache) / Path(photo.file).name), cv2.IMREAD_COLOR)
    if image is None:
        raise FileNotFoundError(f"{photo.stem}: not in the cache")
    truth = photo.truth[prov]
    bx, sx, by, sy = truth["counts"]
    nx, ny = bx * sx, by * sy
    records = []
    for cap_index, (cap_name, cap) in enumerate(CAPS.items()):
        staged, field_corners = stage(image, truth["outer"], truth["field"], cap)
        truth_matrix = _homography(field_corners, field_size(field_corners))
        truth_w, truth_h = field_size(field_corners)
        for radius in RADII:
            seed = [int(photo.sha256[:8], 16), PROVENANCES.index(prov), cap_index, radius]
            rng = np.random.default_rng(seed)
            for trial in range(1 if radius == 0 else TRIALS):
                corners = jitter_corners(field_corners, radius, rng)
                field = FieldImage.from_bgr(staged, corners)
                # The user taps a square's middle on the photo, so the tap error lives in staged
                # pixels with the same radius as a pin, not in the warped field.
                i, j = int(rng.integers(nx)), int(rng.integers(ny))
                centre = ((i + 0.5) * truth_w / nx, (j + 0.5) * truth_h / ny)
                tap_staged = _map_point(np.linalg.inv(truth_matrix), centre)
                tap_staged = jitter_corners(tap_staged[None, :], radius, rng)[0]
                tap = _map_point(field.matrix, tap_staged)
                truth_fit = fit_2d(field, nx, ny)
                for method in (*METHODS, "tap"):
                    rx, ry = _rankings(field, method, tap)
                    joint = joint_ranking(rx, ry, field.width, field.height)
                    top1_fit = fit_2d(field, *joint[0]) if joint else None
                    units = []
                    for cx, cy in joint:
                        pcols, prows = block_periods(field, cx, cy)
                        units.append([*quilter_units(cx, pcols), *quilter_units(cy, prows)])
                    records.append({
                        "photo": photo.stem, "tier": photo.tier, "provenance": prov, "cap": cap_name,
                        "radius": radius, "trial": trial, "method": method,
                        "periodic": is_periodic(bx, by), "truth": [nx, ny],
                        "truth_units": [bx, sx, by, sy], "field_px": [field.width, field.height],
                        "tap_square": [i, j] if method == "tap" else None,
                        "rank_x": rx[:TOP_K], "rank_y": ry[:TOP_K],
                        "joint": [list(p) for p in joint], "units": units,
                        "alternates": ([harmonic_alternates(n, MIN_COUNT, e // MIN_PITCH_PX)
                                        for n, e in zip(joint[0], (field.width, field.height))]
                                       if joint else None),
                        "outcome": score_ranking(joint, (nx, ny))._asdict(),
                        "outcome_x": score_ranking(rx, nx)._asdict(),
                        "outcome_y": score_ranking(ry, ny)._asdict(),
                        "fit_truth": truth_fit, "fit_top1": top1_fit,
                    })
    return records


# --- Report -------------------------------------------------------------------------------


def _outcomes(records: list[dict], key: str = "outcome") -> list[Outcome]:
    return [Outcome(**r[key]) for r in records]


def _rate_cell(summary: dict, key: str) -> str:
    if not summary["n"]:
        return "n/a"
    lo, hi = wilson(summary[key], summary["n"])
    # Three decimals: a rate of 0.795 must not print as 0.80 beside a bar of 0.8.
    return f"{summary[key + '_rate']:.3f} ({summary[key]}/{summary['n']}; {lo:.3f} to {hi:.3f})"


def build_report(records: list[dict], photos: list[Photo], skipped: list[dict], header: dict) -> dict:
    methods = (*METHODS, "tap")
    groups = []
    for prov in PROVENANCES:
        for cap in CAPS:
            for method in methods:
                for radius in RADII:
                    base = [r for r in records if r["provenance"] == prov and r["cap"] == cap
                            and r["method"] == method and r["radius"] == radius]
                    if not base:
                        continue
                    row = {"provenance": prov, "cap": cap, "method": method, "radius": radius}
                    for tier in ("A", "B"):
                        for label, subset in (("all", None), ("periodic", True), ("non_periodic", False)):
                            chosen = [r for r in base if r["tier"] == tier
                                      and (subset is None or r["periodic"] == subset)]
                            name = f"{tier}_{label}"
                            row[name] = summarize(_outcomes(chosen))
                            row[name]["photos"] = len({r["photo"] for r in chosen})
                            row[name + "_axis"] = summarize(_outcomes(chosen, "outcome_x")
                                                            + _outcomes(chosen, "outcome_y"))
                    in_scope = [r for r in base if r["tier"] in ("A", "B")]
                    wrong = [r["fit_top1"]["fit"] for r in in_scope
                             if r["fit_top1"] and not r["outcome"]["top1"]]
                    truths = [r["fit_truth"]["fit"] for r in in_scope]
                    per_trial = [r for r in in_scope if r["fit_top1"] and not r["outcome"]["top1"]]
                    row["wrong_top1"] = len(wrong)
                    row["max_wrong_fit"] = max(wrong) if wrong else None
                    row["min_truth_fit"] = min(truths) if truths else None
                    row["rejected_per_trial"] = sum(
                        r["fit_top1"]["fit"] < r["fit_truth"]["fit"] for r in per_trial)
                    row["no_suggestion"] = sum(not r["joint"] for r in in_scope)
                    # The decision reads exp2 as plan B3 states it: two scores, one threshold
                    # each, set where every truth passes. The product fit stays as a reading.
                    truth_pairs = [pair(r["fit_truth"]) for r in in_scope]
                    rejected = [two_part_rejects(pair(r["fit_top1"]), truth_pairs) for r in per_trial]
                    row["two_part"] = {
                        "min_truth_ratio": min((t[0] for t in truth_pairs), default=None),
                        "max_truth_mad": max((t[1] for t in truth_pairs), default=None),
                        "rejected": sum(rejected),
                        "rejected_per_trial": sum(
                            two_part_rejects(pair(r["fit_top1"]), [pair(r["fit_truth"])])
                            for r in per_trial),
                    }
                    summary = summarize(_outcomes(in_scope))
                    row["in_scope"] = summary
                    row["go_product"] = bool(summary["n"]) and decide(summary["top3_rate"], wrong, truths)
                    row["go"] = decide_two_part(summary["top3_rate"], rejected)
                    groups.append(row)
    zero = [r for r in records if r["radius"] == 0]
    # Every candidate of every trial in quilter units: how often each label was the top-1 and
    # how often it was among the top 3, with the harmonic alternates of each distinct top-1.
    histogram: dict[str, dict[str, dict]] = {}
    for r in records:
        key = f"{r['provenance']}|{r['cap']}|{r['method']}|{r['photo']}|r{r['radius']}"
        cell = histogram.setdefault(key, {})
        for rank, units in enumerate(r["units"]):
            label = "{}x{} by {}x{}".format(*units)
            entry = cell.setdefault(label, {"top1": 0, "top3": 0})
            entry["top3"] += 1
            if rank == 0:
                entry["top1"] += 1
                entry.setdefault("alternates", r["alternates"])
        if not r["joint"]:
            cell.setdefault("none", {"top1": 0, "top3": 0})["top1"] += 1
    return {
        "header": header,
        "photos": [{"stem": p.stem, "tier": p.tier, "provenances": sorted(p.truth),
                    "counts": {k: v["counts"] for k, v in p.truth.items()}} for p in photos],
        "skipped": skipped,
        "b6b_functions": B6B_FUNCTIONS,
        "groups": groups,
        "radius0_trials": zero,
        "candidate_units_histogram": histogram,
    }


def _fmt(value: float | None) -> str:
    return f"{value:.2f}" if value is not None else "n/a"


HEADER_END = "<!-- Run header above, generated by scripts/eval/spikes/b1a_counts.py. -->"
GENERATED = "<!-- Generated by scripts/eval/spikes/b1a_counts.py below this line. -->"


def write_markdown(report: dict, path: Path) -> None:
    """Write the run header first and the generated tables last, keeping the hand-written
    reading an existing file holds between the HEADER_END and GENERATED markers (WORKER.md
    step 4: a report opens with its run header). A file without both markers is refused, so a
    rerun never discards the reading."""
    h = report["header"]
    head = [
        "# B1a: count suggestions and the tap-one-square seed",
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
        "## Decision table (v0 dev photos, joint top-3 recall and the fit rule)",
        "",
        "Go uses the two-part fit rule (exp2's two scores, one threshold each, set by the worst "
        "truth). Intervals treat trials as independent; trials within a photo are correlated, so "
        "the real uncertainty is wider (effective n near the photo count).",
        "",
        "| Provenance | Cap | Method | Radius px | Top-1 | Top-3 | Harmonic top-1 | Wrong top-1 "
        "| Max wrong fit | Min truth fit | Product rejected per trial | Two-part rejected "
        "| Two-part rejected per trial | No suggestion | Go |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for g in report["groups"]:
        s = g["in_scope"]
        if not s["n"]:
            continue
        lines.append(
            f"| {g['provenance']} | {g['cap']} | {g['method']} | {g['radius']} "
            f"| {_rate_cell(s, 'top1')} | {_rate_cell(s, 'top3')} | {_rate_cell(s, 'harmonic')} "
            f"| {g['wrong_top1']} | {_fmt(g['max_wrong_fit'])} | {_fmt(g['min_truth_fit'])} "
            f"| {g['rejected_per_trial']}/{g['wrong_top1']} "
            f"| {g['two_part']['rejected']}/{g['wrong_top1']} "
            f"| {g['two_part']['rejected_per_trial']}/{g['wrong_top1']} "
            f"| {g['no_suggestion']} | {'go' if g['go'] else 'no-go'} |")
    lines += [
        "",
        "## Periodic and non-periodic quilts, per tier (joint, then per axis)",
        "",
        "| Provenance | Cap | Method | Radius px | Tier and class | Photos | Top-1 | Top-3 "
        "| Harmonic top-1 | Per-axis top-1 | Per-axis top-3 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for g in report["groups"]:
        for name in ("A_periodic", "A_non_periodic", "B_all"):
            s, axis = g[name], g[name + "_axis"]
            lines.append(
                f"| {g['provenance']} | {g['cap']} | {g['method']} | {g['radius']} | {name} "
                f"| {s['photos']} | {_rate_cell(s, 'top1')} | {_rate_cell(s, 'top3')} "
                f"| {_rate_cell(s, 'harmonic')} | {_rate_cell(axis, 'top1')} | {_rate_cell(axis, 'top3')} |")
    lines += [
        "",
        "## Radius 0: each photo's top-3 in quilter units, and the top-1's harmonic alternates",
        "",
        "Units read blocks x squares per block, across then down. Alternates are square counts.",
        "",
        "| Provenance | Cap | Method | Photo | Truth | Top-3 | Top-1 alternates (across; down) |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in report["radius0_trials"]:
        truth = "{}x{} by {}x{}".format(*r["truth_units"])
        top = "; ".join("{}x{} by {}x{}".format(*u) for u in r["units"]) or "none"
        alt = ("; ".join(", ".join(map(str, a)) for a in r["alternates"]) if r["alternates"] else "none")
        lines.append(f"| {r['provenance']} | {r['cap']} | {r['method']} | {r['photo']} | {truth} "
                     f"| {top} | {alt} |")
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
    used = ", ".join(f"{p.stem} ({p.tier})" for p in photos)
    holdout = sum(s["reason"] == "holdout" for s in skipped)
    tier_b = sum(row["tier"] == "B" for row in rows)
    return {
        "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": command, "qrep": _qrep_path(qrep.__file__), "git_sha": sha, "dirty": dirty,
        "cv2": cv2.__version__,
        "numpy": np.__version__, "python": sys.version.split()[0],
        "inputs": (f"corpus/manifest.csv rows of eval_set v0 in tiers A and B: {len(rows)} rows, "
                   f"{tier_b} of them tier B; {holdout} holdout rows skipped before any read; "
                   f"read: {used}"),
        "radii_px": list(RADII), "trials_per_radius": TRIALS, "caps": CAPS,
    }


def _qrep_path(module_file: str) -> str:
    """The resolved qrep module as <checkout folder>/<path inside it>: the folder's name shows
    which checkout's code ran, and no local folder above it is printed."""
    resolved = Path(module_file).resolve()
    if resolved.is_relative_to(REPO):
        return f"{REPO.name}/{resolved.relative_to(REPO).as_posix()}"
    return f"<outside this checkout>/{resolved.name}"


def _public_arg(arg: str, cache: str) -> str:
    """A command argument as the report prints it: no local path outside the repo, in either
    the --opt value or the --opt=value form, absolute or relative."""
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
    parser.add_argument("--json", default=str(REPO / "docs/sprint-5/evidence/B1a-count-suggestions.json"))
    parser.add_argument("--md", default=None, help="write the generated tables here")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    args = parser.parse_args(argv)
    # The cache is a local folder of the main checkout; the report names it, not its path.
    exe = Path(sys.executable).resolve()
    python = exe.relative_to(REPO).as_posix() if exe.is_relative_to(REPO) else "python"
    command = f"{python} scripts/eval/spikes/b1a_counts.py " + " ".join(
        _public_arg(a, args.cache) for a in (argv if argv is not None else sys.argv[1:]))
    photos, skipped = load_photos()
    # The header records the checkout as the run starts; a commit, checkout or edit during the
    # run would make it name code that did not run, so the run then writes nothing.
    header = _header(command, photos, skipped)
    jobs = [(p, prov, args.cache) for p in photos for prov in sorted(p.truth)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        records = [r for chunk in pool.map(run_photo, jobs) for r in chunk]
    if _git_state() != (header["git_sha"], header["dirty"]):
        raise SystemExit("the checkout's HEAD or tracked files changed during the run; nothing "
                         "written, because the header would not name the code that ran")
    report = build_report(records, photos, skipped, header)
    Path(args.json).write_text(json.dumps(report, indent=1, default=float) + "\n",
                               encoding="utf-8", newline="\n")
    if args.md:
        write_markdown(report, Path(args.md))
    for g in report["groups"]:
        s = g["in_scope"]
        print(f"{g['provenance']:11} {g['cap']:7} {g['method']:8} r={g['radius']} "
              f"top1={s['top1']}/{s['n']} top3={s['top3']}/{s['n']} harm={s['harmonic']} "
              f"wrong={g['wrong_top1']} go={g['go']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
