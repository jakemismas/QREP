"""The frozen verdict thresholds (sprint 3; proposed by S0's baseline report
on issue #66, frozen by Jake via the parent-issue checkbox on #65).

IMMUTABLE per the sprint contract: these literals are never edited to force
a pass. The decision tree that consumes them lands in S4:
    grid confidence < T1            -> no_grid
    else periodicity score < T2     -> readable / readable_no_repeat
    else intra-cell coherence > T3  -> non_square_repeat
S3 uses T1 as the honest-failure floor its guards push violators below.
"""

T1 = 0.60  # grid-confidence floor
T2 = 0.45  # image-level periodicity floor
T3 = 1.05  # intra-cell coherence ceiling for squares content

VERDICTS = ("readable", "readable_no_repeat", "non_square_repeat", "no_grid")

# S4 integer-ratio cross-check epsilon, frozen at test-write time (rationale
# in tests/test_repeats_verdict.py: absorbs a 2% pitch error at periods up
# to ~7 cells; half-integer aliases sit 0.5 away at every k).
INTEGER_RATIO_EPSILON = 0.15


def decide_verdict(
    grid_confidence: float,
    periodicity_score: float,
    coherence: float,
    label_repeat_found: bool,
) -> str:
    """The frozen decision tree (S4, issue #70).

    grid confidence < T1            -> no_grid
    else periodicity score < T2     -> readable / readable_no_repeat by the
                                       label detector's repeat
    else intra-cell coherence > T3  -> non_square_repeat
    else                            -> readable
    Boundary semantics are the contract's own: exactly-at-threshold values
    are NOT below/above.
    """
    if grid_confidence < T1:
        return "no_grid"
    if periodicity_score < T2:
        return "readable" if label_repeat_found else "readable_no_repeat"
    if coherence > T3:
        return "non_square_repeat"
    return "readable"
