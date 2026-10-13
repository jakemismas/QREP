"""Rates with their n, Wilson intervals and the rule of three (plan 7.2; data-44)."""

import math

# Two-sided 95 percent normal quantile.
Z95 = 1.959964


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float] | None:
    """The Wilson score interval for k successes in n trials, or None when n is 0."""
    if n == 0:
        return None
    if not 0 <= k <= n:
        raise ValueError(f"k = {k} is not within 0..{n}")
    p = k / n
    z2 = z * z
    denom = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def rule_of_three(n: int) -> float | None:
    """The 95 percent upper bound 3/n on a rate whose count is 0 in n trials, capped at
    1: below 3 trials 3/n exceeds any rate."""
    return min(1.0, 3 / n) if n else None


def rate(k: int, n: int) -> dict:
    """A rate as the report prints it: k, n, k/n and its interval; a zero count also
    carries its 3/n bound, and n = 0 reads not measured (rate None), never 0."""
    return {
        "k": k,
        "n": n,
        "rate": k / n if n else None,
        "wilson95": list(wilson(k, n)) if n else None,
        "rule_of_three": rule_of_three(n) if n and k == 0 else None,
    }
