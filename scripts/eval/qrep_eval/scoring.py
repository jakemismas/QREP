"""Square-level scoring against gold roles (plan 7.2, G1 and G2; vision-11).

Two fabric mappings, both by CIE 1976 color distance from each read fabric to
each gold role: many-to-one (each read fabric takes its nearest role, so a
phantom extra fabric that splits a role costs nothing here and shows up in the
k mismatch instead) and minimum-cost one-to-one (the assignment with the least
total distance, so an extra fabric has no role and its squares count wrong).
qrep/vision/compare.py's greedy darkest-first bijection stays as it is: it
defines test_roundtrip's frozen thresholds (plan D4a).
"""

from dataclasses import dataclass

# sRGB to XYZ (IEC 61966-2-1), linear RGB rows. The white point is each row's sum, so
# #ffffff maps to L* 100, a* = b* = 0 exactly.
_M = (
    (0.4124564, 0.3575761, 0.1804375),
    (0.2126729, 0.7151522, 0.0721750),
    (0.0193339, 0.1191920, 0.9503041),
)
_WHITE = tuple(sum(row) for row in _M)
_EPS = (6 / 29) ** 3
# Any band difference within this of 1/4 in counts as within it (eighths are exact in
# binary, so only an inch value computed another way could land a hair over).
_BAND_SLACK = 1e-9


def _linear(channel: int) -> float:
    v = channel / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _f(t: float) -> float:
    return t ** (1 / 3) if t > _EPS else t * (841 / 108) + 4 / 29


def srgb_to_lab(hex_color: str) -> tuple[float, float, float]:
    """#rrggbb to CIE 1976 L*a*b* under the sRGB matrix's D65 white."""
    text = hex_color.lstrip("#")
    if len(text) != 6:
        raise ValueError(f"not a #rrggbb color: {hex_color!r}")
    rgb = [_linear(int(text[i : i + 2], 16)) for i in (0, 2, 4)]
    fx, fy, fz = (_f(sum(m * c for m, c in zip(row, rgb)) / white) for row, white in zip(_M, _WHITE))
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    """CIE 1976 color difference: Euclidean distance in L*a*b*."""
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def _costs(read_colors: list[str], gold_colors: list[str]) -> list[list[float]]:
    gold = [srgb_to_lab(c) for c in gold_colors]
    return [[delta_e(srgb_to_lab(c), g) for g in gold] for c in read_colors]


def map_many_to_one(read_colors: list[str], gold_colors: list[str]) -> list[int]:
    """Each read fabric's nearest gold role (the lower index on a tie)."""
    if not gold_colors:
        raise ValueError("no gold roles to map to")
    return [min(range(len(row)), key=lambda j: (row[j], j)) for row in _costs(read_colors, gold_colors)]


def map_one_to_one(read_colors: list[str], gold_colors: list[str]) -> list[int | None]:
    """The one-to-one pairing of read fabrics with gold roles that pairs as many as
    possible at the least total distance; a read fabric left over maps to None."""
    m, n = len(read_colors), len(gold_colors)
    if m == 0 or n == 0:
        return [None] * m
    cost = _costs(read_colors, gold_colors)
    # Exact search over subsets of the smaller side, taking the larger side's items in
    # turn: k is at most 12 in a read (qrep/contract.py FABRICS_MAX), so 2^k states stay
    # small, and an exact optimum keeps the score free of greedy-order effects.
    swap = m > n
    small, large = (n, m) if swap else (m, n)
    if small > 16:
        raise ValueError(f"{small} fabrics on the smaller side is beyond the exact search")

    def pair_cost(s: int, b: int) -> float:
        return cost[b][s] if swap else cost[s][b]

    states: dict[int, tuple[float, tuple]] = {0: (0.0, ())}
    for b in range(large):
        nxt = dict(states)
        for mask, (total, pairs) in states.items():
            for s in range(small):
                if mask & (1 << s):
                    continue
                key = mask | (1 << s)
                candidate = (total + pair_cost(s, b), pairs + ((s, b),))
                if key not in nxt or candidate < nxt[key]:
                    nxt[key] = candidate
        states = nxt
    mapping: list[int | None] = [None] * m
    for s, b in states[(1 << small) - 1][1]:
        read, gold = (b, s) if swap else (s, b)
        mapping[read] = gold
    return mapping


@dataclass(frozen=True)
class SquareScore:
    squares: int
    correct: int
    wrong: int
    confident_wrong: int
    dims_match: bool

    @property
    def accuracy(self) -> float:
        return self.correct / self.squares if self.squares else 0.0


def score_squares(
    truth: list[list[int]],
    read: list[list[int]],
    mapping: list[int | None],
    confidence: list[list[float]],
    *,
    low_confidence_below: float | None = None,
    flagged_regions: list[tuple[int, int, int, int]] = (),
) -> SquareScore:
    """Score a read's interior squares against the truth's roles.

    truth holds a gold role per square, read a read-fabric index per square, and
    mapping each read fabric's role (None: no role). A wrong square is confident-wrong
    (G2) unless its confidence is below low_confidence_below (None: no square is
    flagged by confidence) or it lies in a flagged region, given as (row0, col0,
    row1, col1), half-open. A read whose grid differs from the truth's locates no
    truth square, so every square counts wrong and confident-wrong.
    """
    squares = sum(len(row) for row in truth)
    dims_match = len(read) == len(truth) and all(len(a) == len(b) for a, b in zip(read, truth))
    if not dims_match:
        return SquareScore(squares, 0, squares, squares, False)
    correct = confident_wrong = 0
    for r, (truth_row, read_row) in enumerate(zip(truth, read)):
        for c, (role, fabric) in enumerate(zip(truth_row, read_row)):
            mapped = mapping[fabric] if 0 <= fabric < len(mapping) else None
            if mapped == role:
                correct += 1
                continue
            low = low_confidence_below is not None and confidence[r][c] < low_confidence_below
            in_region = any(r0 <= r < r1 and c0 <= c < c1 for r0, c0, r1, c1 in flagged_regions)
            if not (low or in_region):
                confident_wrong += 1
    return SquareScore(squares, correct, squares - correct, confident_wrong, True)


def k_mismatch(*, k_read: int, k_truth: int) -> int:
    """Read fabrics minus gold roles: positive is a phantom fabric, negative a merge."""
    return k_read - k_truth


def bands_match(truth_inches: list[float], read_inches: list[float], tolerance: float = 0.25) -> bool:
    """G1's band rule: the same number of bands, each within 1/4 in of the truth."""
    return len(truth_inches) == len(read_inches) and all(
        abs(t - r) <= tolerance + _BAND_SLACK for t, r in zip(truth_inches, read_inches)
    )


def truth_band_inches(width_squares: list[float], cell_size_eighths: int) -> list[float]:
    """Truth bands in squares, in inches at the read's own square size, so a scale the
    read guessed cancels out of the comparison."""
    return [w * cell_size_eighths / 8 for w in width_squares]


def read_band_inches(width_eighths: list[int]) -> list[float]:
    return [w / 8 for w in width_eighths]


def fully_correct_interior(score: SquareScore, *, k_truth: int, k_read: int, bands_ok: bool) -> bool:
    """G1: every interior square right, the fabric count exact and the bands matching."""
    return score.dims_match and score.wrong == 0 and k_read == k_truth and bands_ok
