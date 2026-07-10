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
