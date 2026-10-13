"""Fabrics for the confirmed read: cluster the samples into fabrics, fit one
label-aware shading correction, and label every square and band strip.

Distances are taken in float CIELAB with L* scaled by the L weight, d =
sqrt((w dL)^2 + da^2 + db^2), because shading moves lightness most (plan
B2b, vision-06). The correction is one light surface, quadratic in
position, that every fabric's color is scaled by, so each fabric's color is
a quadratic in position. The read fits the palette and assigns the squares
with the same correction, which the old detrend did not (vision-07).

numpy only and no random draws: the same code runs under Pyodide (numpy
2.2) and natively, and gives the same fabrics on both.
"""

from dataclasses import dataclass
from typing import Literal, get_args

import numpy as np

from qrep.vision.read.knobs import (
    K_MAX,
    K_MIN,
    KMEANS_ITERATIONS,
    KMEANS_SEEDINGS,
    L_WEIGHT,
    LIGHT_CONFIDENCE_POWER,
    LIGHT_MAX_RATIO,
    SHADING_MIN_SQUARES,
    SHADING_ROUNDS,
    SILHOUETTE_SAMPLES,
)
from qrep.vision.read.sample import _EPSILON, _TO_XYZ, Squares

Code = Literal["bad_fabric_count", "too_many_fabrics"]
CODES: tuple[str, ...] = get_args(Code)

# The seedings replace k-means++'s random draws with the golden-ratio
# sequence, which spreads its draws evenly over [0, 1) without a generator.
_GOLDEN = 0.6180339887498949
# Light scales L* + 16, not L*, so the light model works on this offset.
_OFFSET = np.array([16.0, 0.0, 0.0])


@dataclass(frozen=True)
class Refusal:
    """A typed outcome that stops the read. Callers branch on code, never on
    message text, as for a Diagnosis."""

    code: Code
    message: str

    def __post_init__(self):
        if self.code not in CODES:
            raise ValueError(f"unknown refusal code {self.code!r}, expected one of {CODES}")


@dataclass(frozen=True, eq=False)
class Clusters:
    """One fabric count's clustering of n samples.

    centers has shape (k, 3): each fabric's float CIELAB in the light at the
    field center, fitted from its own samples (_palette). labels and
    confidence have shape (n,); a sample's confidence is (d2 - d1) / d2 over
    its distances to the colors, in the light at its own position, of the
    fabrics that hold samples, and 0.0 when fewer than two do. silhouette is the weighted mean
    silhouette at k, None when undefined, which includes a fabric that holds
    no sample.
    """

    k: int
    centers: np.ndarray
    center_confidence: np.ndarray
    labels: np.ndarray
    confidence: np.ndarray
    silhouette: float | None


@dataclass(frozen=True, eq=False)
class Fabrics:
    """The read's fabrics, darkest first (center L* ascending, ties by a* then
    b*), and every square's and band strip's label.

    labels and confidence have shape (rows, cols); strip_labels and
    strip_confidence follow squares.strips. k_confidence is 1.0 when the
    request set k, as a user fact. palette_confidence is the silhouette
    clipped to [0, 1], 0.0 when the silhouette is undefined: a palette with no
    evidence of separation never reads as certain.
    """

    k: int
    k_source: Literal["user", "suggestion"]
    k_confidence: float
    palette_confidence: float
    centers: np.ndarray
    center_confidence: np.ndarray
    labels: np.ndarray
    confidence: np.ndarray
    strip_labels: tuple[int, ...]
    strip_confidence: tuple[float, ...]


def to_hex(lab) -> str:
    """The #rrggbb sRGB color of one float CIELAB value: the inverse of
    sample.to_lab with its D65 constants, so a fabric's center shows as the
    color its squares were sampled from. A center outside the sRGB gamut
    clips to it."""
    lightness, a, b = (float(v) for v in np.asarray(lab, dtype=float).reshape(3))
    eps = float(_EPSILON)
    y = ((lightness + 16) / 116) ** 3 if lightness > 903.3 * eps else lightness / 903.3
    fy = (lightness + 16) / 116 if y > eps else 7.787 * y + 16 / 116

    def inverse(f: float) -> float:
        return f**3 if f**3 > eps else (f - 16 / 116) / 7.787

    linear = np.linalg.solve(
        _TO_XYZ.astype(float), [inverse(fy + a / 500), y, inverse(fy - b / 200)]
    )
    linear = np.clip(linear, 0.0, 1.0)
    codes = np.where(linear <= 0.0031308, 12.92 * linear, 1.055 * linear ** (1 / 2.4) - 0.055)
    return "#" + "".join(f"{int(np.floor(v * 255 + 0.5)):02x}" for v in np.clip(codes, 0.0, 1.0))


def _scale(lab: np.ndarray, l_weight: float) -> np.ndarray:
    return lab * np.array([l_weight, 1.0, 1.0])


def _squared(lab: np.ndarray, colors: np.ndarray, l_weight: float) -> np.ndarray:
    """Squared L-weighted distances, shape (n, k), from lab (n, 3) to colors:
    k centers (k, 3), or each label's color at each sample (n, k, 3)."""
    return (_scale(lab[:, None, :] - colors, l_weight) ** 2).sum(axis=2)


def _draw(mass: np.ndarray, u: float) -> int:
    """The sample at the inverse CDF of mass at u in [0, 1). A sample with no
    mass spans an empty run of the CDF, so it is never drawn."""
    cumulative = np.cumsum(mass)
    index = int(np.searchsorted(cumulative, u * cumulative[-1], side="right"))
    # u * total rounds to the total only for u within an ulp of 1.
    return index if index < len(mass) else int(np.flatnonzero(mass > 0)[-1])


def _seed(lab: np.ndarray, weights: np.ndarray, k: int, seeding: int, l_weight: float):
    """k-means++ seeding number seeding, its draws from the golden-ratio
    sequence that starts at frac((seeding + 1) x 0.618...)."""
    u = (seeding + 1) * _GOLDEN % 1.0
    chosen = [_draw(weights, u)]
    nearest = _squared(lab, lab[chosen], l_weight)[:, 0]
    while len(chosen) < k:
        mass = weights * nearest
        if not mass.sum() > 0:
            # Every sample sits on a chosen center: fewer distinct colors
            # than k, so the surplus centers repeat the last and stay empty.
            chosen += [chosen[-1]] * (k - len(chosen))
            break
        u = (u + _GOLDEN) % 1.0
        chosen.append(_draw(mass, u))
        nearest = np.minimum(nearest, _squared(lab, lab[chosen[-1:]], l_weight)[:, 0])
    return lab[chosen].copy()


def _means(lab, weights, labels, centers) -> np.ndarray:
    """Each label's weighted mean color; an empty label keeps its center."""
    k = len(centers)
    totals = np.bincount(labels, weights=weights, minlength=k)
    sums = np.stack(
        [np.bincount(labels, weights=weights * lab[:, c], minlength=k) for c in range(3)],
        axis=1,
    )
    filled = totals > 0
    out = centers.copy()
    out[filled] = sums[filled] / totals[filled, None]
    return out


def _kmeans(lab: np.ndarray, weights: np.ndarray, k: int, l_weight: float):
    """Weighted Lloyd from each seeding, keeping the lowest weighted inertia
    (ties to the earlier seeding). argmin breaks distance ties to the lower
    index, which keeps a repeated center empty. Centers stay in plain Lab,
    since a weighted mean commutes with the L scaling, so an L weight of 0
    still keeps each center's lightness."""
    best = None
    for seeding in range(KMEANS_SEEDINGS):
        centers = _seed(lab, weights, k, seeding, l_weight)
        labels = np.argmin(_squared(lab, centers, l_weight), axis=1)
        for _ in range(KMEANS_ITERATIONS):
            centers = _means(lab, weights, labels, centers)
            again = np.argmin(_squared(lab, centers, l_weight), axis=1)
            if np.array_equal(again, labels):
                break
            labels = again
        inertia = float(weights @ _squared(lab, centers, l_weight)[np.arange(len(lab)), labels])
        if best is None or inertia < best[0]:
            best = (inertia, centers, labels)
    return best[1], best[2]


def _basis(positions: np.ndarray) -> np.ndarray:
    """The quadratic terms of the light surface about the field center, from
    [x', y', x'^2, x'y', y'^2], keeping only the terms the positions can fit:
    a slope along an axis needs two distinct positions on it, a square term
    three, and x'y' both slopes. A term left in without that is collinear
    with the fabric intercepts or with another term (on a one-row field y' is
    fixed, so x'y' copies x'), and a least squares fit would split one slope
    between them. No constant term, so the surface is 1 at the center."""
    x, y = positions[:, 0] - 0.5, positions[:, 1] - 0.5
    nx, ny = len(np.unique(x)), len(np.unique(y))
    terms = [(x, nx >= 2), (y, ny >= 2), (x * x, nx >= 3), (x * y, nx >= 2 and ny >= 2)]
    terms.append((y * y, ny >= 3))
    kept = [term for term, fits in terms if fits]
    return np.stack(kept, axis=1) if kept else np.zeros((len(x), 0))


def _light(basis, lab, weights, labels) -> np.ndarray:
    """The light at each sample, a factor shared by every fabric: g =
    exp(basis @ beta), fitted with each fabric's own level by weighted least
    squares on log(L* + 16) = u[label] + basis @ beta.

    Uneven light scales a sample's XYZ by some t, which scales L* + 16, a*
    and b* alike by t^(1/3) wherever Y > 0.008856, so one surface serves
    every fabric. It is fitted over every sample at once, so it holds where
    any fabric has squares; a surface per fabric, fitted only where that
    fabric lies, swings outside its rows and takes other fabrics' squares.
    The weight (L* + 16)^2 makes a log residual count as its error in L*.
    """
    held = np.unique(labels)
    level = (labels[:, None] == held[None, :]).astype(float)
    design = np.concatenate([level, basis], axis=1)
    offset = lab[:, 0] + 16.0
    root = np.sqrt(weights) * offset
    solution = np.linalg.lstsq(root[:, None] * design, root * np.log(offset), rcond=None)[0]
    return np.exp(basis @ solution[len(held) :])


def _palette(lab, weights, labels, light, centers) -> np.ndarray:
    """Each fabric's color in the light at the field center, from its own
    samples alone: the weighted least squares c in (L* + 16, a*, b*) =
    g c over its members, c = sum(w g x) / sum(w g^2). An empty fabric
    keeps its center."""
    k = len(centers)
    shifted = lab + _OFFSET
    totals = np.bincount(labels, weights=weights * light * light, minlength=k)
    sums = np.stack(
        [
            np.bincount(labels, weights=weights * light * shifted[:, c], minlength=k)
            for c in range(3)
        ],
        axis=1,
    )
    filled = totals > 0
    out = centers.copy()
    out[filled] = sums[filled] / totals[filled, None] - _OFFSET
    return out


def _lit(centers: np.ndarray, light: np.ndarray) -> np.ndarray:
    """Each fabric's color in the light at each sample, shape (n, k, 3)."""
    return light[:, None, None] * (centers + _OFFSET)[None, :, :] - _OFFSET


def _margins(lab, colors, labels, k: int, l_weight: float) -> np.ndarray:
    """Each sample's (d2 - d1) / d2 over its distances to colors (n, k, 3) of
    the fabrics that hold samples, in [0, 1].

    An empty fabric (k above the distinct colors) repeats a held center, so
    counting it would put d2 at 0 for every square of its twin. With fewer
    than two held fabrics there is no other fabric to tell a square from, so
    no margin, never certainty."""
    held = np.bincount(labels, minlength=k) > 0
    if held.sum() < 2:
        return np.zeros(len(lab))
    nearest = np.sort(np.sqrt(_squared(lab, colors, l_weight))[:, held], axis=1)
    d1, d2 = nearest[:, 0], nearest[:, 1]
    return np.where(d2 > 0, (d2 - d1) / np.where(d2 > 0, d2, 1.0), 0.0)


def _spread(n: int, m: int) -> np.ndarray:
    """m distinct indices of range(n), m < n, sorted: the distinct values of
    floor(frac((j + 1) x 0.618...) x n) for j = 0, 1, .., the first m to
    appear. The sequence runs past j = m only when picks repeat, and it
    reaches every index in the end, so the loop stops."""
    count = m
    while True:
        u = np.arange(1, count + 1) * _GOLDEN % 1.0
        # u x n rounds up to n only for u within an ulp of 1.
        picks = np.minimum(np.floor(u * n), n - 1).astype(np.intp)
        values, first = np.unique(picks, return_index=True)
        if len(values) >= m:
            return np.sort(picks[np.sort(first)[:m]])
        count *= 2


def _subset(positions: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The silhouette's points and weights: every sample outside the field
    (the band strips, few and heavy) and a golden-ratio pick of the squares
    (_spread), at most SILHOUETTE_SAMPLES in all. A stride would line up with
    the grid whenever it shares a factor with the column count: stride 2 on
    48 columns keeps the even columns alone, and a fabric on odd columns
    drops out of the silhouette. The golden-ratio sequence has no period, so
    it cannot line up. Each kept square stands for n / kept squares, so its
    weight scales up and the squares keep their share of the weight against
    the strips."""
    inside = np.all((positions >= 0) & (positions <= 1), axis=1)
    squares, strips = np.flatnonzero(inside), np.flatnonzero(~inside)
    budget = max(SILHOUETTE_SAMPLES - len(strips), 0)
    kept = squares
    if len(squares) > budget:
        kept = squares[_spread(len(squares), budget)]
    index = np.concatenate([kept, strips])
    w = weights[index].copy()
    if len(kept):
        w[: len(kept)] *= len(squares) / len(kept)
    return index, w


def _silhouette(points: np.ndarray, weights: np.ndarray, labels: np.ndarray, k: int):
    """The weighted mean silhouette and each label's weighted mean, or
    (None, None) when undefined: fewer than two labels present, or no more
    points than labels present."""
    present = np.unique(labels)
    if len(present) < 2 or len(points) <= len(present):
        return None, None
    squared = np.zeros((len(points), len(points)))
    for c in range(3):
        diff = points[:, None, c] - points[None, :, c]
        squared += diff * diff
    member = (labels[:, None] == np.arange(k)[None, :]) * weights[:, None]
    sums = np.sqrt(squared) @ member
    totals = member.sum(axis=0)
    counts = np.bincount(labels, minlength=k)
    rows = np.arange(len(points))
    alone = counts[labels] == 1
    others = np.where(alone, 1.0, totals[labels] - weights)
    a = np.where(alone, 0.0, sums[rows, labels] / others)
    away = np.where(totals > 0, sums / np.where(totals > 0, totals, 1.0), np.inf)
    away[rows, labels] = np.inf
    b = away.min(axis=1)
    top = np.maximum(a, b)
    s = np.where(alone | (top == 0), 0.0, (b - a) / np.where(top == 0, 1.0, top))
    per_label = np.bincount(labels, weights=weights * s, minlength=k)
    mass = np.bincount(labels, weights=weights, minlength=k)
    per_label = np.where(mass > 0, per_label / np.where(mass > 0, mass, 1.0), np.nan)
    return float(weights @ s / weights.sum()), per_label


def cluster(
    samples,
    weights,
    positions,
    k: int,
    *,
    l_weight: float = L_WEIGHT,
    shading_rounds: int = SHADING_ROUNDS,
) -> Clusters:
    """Clusters samples (n, 3) float CIELAB, with positive weights (n,) and
    positions (n, 2) as (x, y) in field units, into k fabrics.

    Weighted k-means seeds the labels; then up to shading_rounds rounds fit
    the light shared by every fabric (_light) and each fabric's color under
    it (_palette), and move every sample to the fabric whose color in the
    light at its position is nearest, until the labels repeat. The light is
    fitted only from SHADING_MIN_SQUARES samples up, and a light that varies
    more than LIGHT_MAX_RATIO in luminance drops the correction and keeps the
    k-means read. Samples outside the
    field [0, 1] x [0, 1] are the band strips, which the silhouette always
    keeps; the light holds the field edge's value across them.
    """
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")
    lab = np.asarray(samples, dtype=float).reshape(-1, 3)
    weights = np.asarray(weights, dtype=float).reshape(-1)
    positions = np.asarray(positions, dtype=float).reshape(-1, 2)

    plain = _kmeans(lab, weights, k, l_weight)
    centers, labels = plain
    basis = _basis(np.clip(positions, 0.0, 1.0))
    light = np.ones(len(lab))
    if len(lab) >= SHADING_MIN_SQUARES and basis.shape[1]:
        for _ in range(shading_rounds):
            # A misread square sits near the midpoint between two fabrics, at
            # a small margin, and on bands of rising lightness every misread
            # tilts the light the same way; weighting by the margin keeps
            # those squares from feeding the light that moved them.
            margin = _margins(lab, _lit(centers, light), labels, k, l_weight)
            light = _light(basis, lab, weights * margin**LIGHT_CONFIDENCE_POWER, labels)
            if (light.max() / light.min()) ** 3 > LIGHT_MAX_RATIO:
                # Light that varies more than any photo's is the fit taking a
                # change between fabrics for shading, so the read keeps none.
                light = np.ones(len(lab))
                centers, labels = plain
                break
            centers = _palette(lab, weights, labels, light, centers)
            again = np.argmin(_squared(lab, _lit(centers, light), l_weight), axis=1)
            if np.array_equal(again, labels):
                break
            labels = again

    confidence = _margins(lab, _lit(centers, light), labels, k, l_weight)
    held = np.bincount(labels, minlength=k) > 0

    corrected = _scale((lab + _OFFSET) / light[:, None] - _OFFSET, l_weight)
    index, w = _subset(positions, weights)
    silhouette, per_label = _silhouette(corrected[index], w, labels[index], k)
    if not held.all():
        # A fabric with no sample has no evidence of separation, so the
        # palette has none at this k; the held fabrics keep their own scores.
        silhouette = None
    if per_label is None:
        center_confidence = np.zeros(k)
    else:
        center_confidence = np.clip(np.nan_to_num(per_label, nan=0.0), 0.0, 1.0)
    return Clusters(
        k=k,
        centers=centers,
        center_confidence=center_confidence,
        labels=labels,
        confidence=confidence,
        silhouette=silhouette,
    )


def suggest(
    samples,
    weights,
    positions,
    *,
    l_weight: float = L_WEIGHT,
    shading_rounds: int = SHADING_ROUNDS,
) -> Clusters | Refusal:
    """The clustering at the fabric count with the highest silhouette over
    K_MIN..K_MAX (ties to the smaller count), or too_many_fabrics when the
    silhouette peaks at K_MAX, still rising there: a quilt of more fabrics
    than the cap is refused, never merged silently.

    Past the true count the silhouette runs flat with noise, so a rise from
    K_MAX - 1 to K_MAX alone says nothing: on 3-fabric grids with Gaussian
    noise it held in 10 of 12, each peaking at 3 near 0.94 and ending near
    0.33. Only a peak at the cap is evidence of more fabrics.
    """
    lab = np.asarray(samples, dtype=float).reshape(-1, 3)
    distinct = len(np.unique(lab, axis=0))
    first = best = None
    for k in range(K_MIN, min(K_MAX, distinct) + 1):
        result = cluster(
            lab, weights, positions, k, l_weight=l_weight, shading_rounds=shading_rounds
        )
        first = first or result
        if result.silhouette is not None and (best is None or result.silhouette > best.silhouette):
            best = result
    if best is not None and best.k == K_MAX:
        return Refusal(
            code="too_many_fabrics",
            message=f"the fabrics separate best at {K_MAX}, the most the read tells apart, "
            "so the quilt may hold more",
        )
    if best is not None:
        return best
    if first is not None:
        return first
    # One distinct color: the least count the read offers, its second fabric
    # empty, so the palette carries no confidence.
    return cluster(lab, weights, positions, K_MIN, l_weight=l_weight, shading_rounds=shading_rounds)


def _samples(squares: Squares) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Every square in raster order at weight 1, then every band strip in
    squares.strips order at its area in squares, with positions in field
    units. A border fabric that never appears in the field still gets its own
    fabric this way, instead of being forced onto the nearest field fabric.
    """
    geometry = squares.geometry
    rows, cols = geometry.rows, geometry.cols
    r, c = np.divmod(np.arange(rows * cols), cols)
    lab = [np.asarray(squares.lab, dtype=float).reshape(-1, 3)]
    weights = [np.ones(rows * cols)]
    positions = [np.stack([(c + 0.5) / cols, (r + 0.5) / rows], axis=1)]
    total = sum(band.width_squares for band in geometry.bands)
    for strip in squares.strips:
        band = geometry.bands[strip.band]
        side = band.side(strip.side)
        # The strip's center across the band, in field-plane squares: the
        # field spans 0..cols and 0..rows, and the outer edge sits T out.
        across = band.inset_squares + band.width_squares / 2 - total
        u, v = {
            "top": (cols / 2, across),
            "bottom": (cols / 2, rows - across),
            "left": (across, rows / 2),
            "right": (cols - across, rows / 2),
        }[strip.side]
        lab.append(np.asarray(strip.lab, dtype=float).reshape(1, 3))
        weights.append(np.array([side.length_squares * side.width_squares]))
        positions.append(np.array([[u / cols, v / rows]]))
    return np.concatenate(lab), np.concatenate(weights), np.concatenate(positions)


def read_fabrics(
    squares: Squares,
    k: int | None = None,
    *,
    l_weight: float = L_WEIGHT,
    shading_rounds: int = SHADING_ROUNDS,
) -> Fabrics | Refusal:
    """The fabrics of a read's samples and every square's and strip's label,
    at the requested count k or, when k is None, the suggested one; or the
    refusal that stops the read: bad_fabric_count or too_many_fabrics."""
    if k is not None:
        if isinstance(k, bool) or not isinstance(k, (int, np.integer)) or k < K_MIN:
            return Refusal(
                code="bad_fabric_count",
                message=f"the fabric count must be a whole number from {K_MIN} to {K_MAX}, "
                f"got {k!r}",
            )
        if k > K_MAX:
            return Refusal(
                code="too_many_fabrics",
                message=f"the read tells apart at most {K_MAX} fabrics, got {k}",
            )
    lab, weights, positions = _samples(squares)
    if k is None:
        result = suggest(lab, weights, positions, l_weight=l_weight, shading_rounds=shading_rounds)
        if isinstance(result, Refusal):
            return result
    else:
        result = cluster(
            lab, weights, positions, int(k), l_weight=l_weight, shading_rounds=shading_rounds
        )

    centers = result.centers
    # A light fit leaves float noise in a center, so colors equal in L*
    # would order by that noise instead of by a* and b*; rounding keeps the
    # tie.
    key = np.round(centers, 6)
    order = np.lexsort((key[:, 2], key[:, 1], key[:, 0]))
    rank = np.empty(result.k, dtype=int)
    rank[order] = np.arange(result.k)
    labels = rank[result.labels]
    rows, cols = squares.geometry.rows, squares.geometry.cols
    field = rows * cols
    score = 0.0 if result.silhouette is None else float(np.clip(result.silhouette, 0.0, 1.0))
    return Fabrics(
        k=result.k,
        k_source="suggestion" if k is None else "user",
        k_confidence=score if k is None else 1.0,
        palette_confidence=score,
        centers=centers[order],
        center_confidence=result.center_confidence[order],
        labels=labels[:field].reshape(rows, cols),
        confidence=result.confidence[:field].reshape(rows, cols),
        strip_labels=tuple(int(v) for v in labels[field:]),
        strip_confidence=tuple(float(v) for v in result.confidence[field:]),
    )
