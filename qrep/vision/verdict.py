"""The frozen verdict thresholds (sprint 3; proposed by S0's baseline report
on issue #66, frozen by Jake via the parent-issue checkbox on #65).

IMMUTABLE per the sprint contract: these literals are never edited to force
a pass. The decision tree that consumes them lands in S4:
    grid confidence < T1            -> no_grid
    else periodicity score < T2     -> readable / readable_no_repeat
    else intra-cell coherence > T3  -> non_square_repeat
S3 uses T1 as the honest-failure floor its guards push violators below.
"""

from pydantic import BaseModel

T1 = 0.60  # grid-confidence floor
T2 = 0.45  # image-level periodicity floor
T3 = 1.05  # intra-cell coherence ceiling for squares content
# T4 (sprint 4; proposed by S0's baseline report on issue #92, frozen by Jake
# via the parent-issue checkbox on #91, 2026-07-10). IMMUTABLE from here, same
# standing as T1-T3: the block-lattice SNR floor below which the peak-contrast
# 2D evidence is noise. S1 (#93) admits the block period as a pitch hint only
# above this floor; S2 (#94) gates the corroboration exits on it.
T4 = 1.50  # block-lattice SNR floor
# T5 (sprint 4; proposed by S0's baseline report on issue #92, frozen by Jake
# on #91, 2026-07-10). IMMUTABLE, same standing as T1-T4: the mean-cell-
# confidence floor for exit (a)'s READABLE rescue - a rescue-quality gate, not
# the garbage discriminator (S0/D3: median snapping reads 2-color garbage at
# ~0.997, above the Irish chain's ~0.74; the integer-lock separates garbage).
T5 = 0.70  # mean-cell-confidence rescue floor

VERDICTS = ("readable", "readable_no_repeat", "non_square_repeat", "no_grid")

# S4 integer-ratio cross-check epsilon, frozen at test-write time (rationale
# in tests/test_repeats_verdict.py: absorbs a 2% pitch error at periods up
# to ~7 cells; half-integer aliases sit 0.5 away at every k).
INTEGER_RATIO_EPSILON = 0.15
# RESCUE_MIN_PITCH_PX (sprint 4, S2/#94; frozen by Jake on #94, 2026-07-10,
# same standing as T4/T5). The piecing-vs-texture floor: below this adopted
# cell pitch a "cell" is print texture, not a pieced square, so the pipeline
# refuses to build corroboration and the read stays no_grid. = 2 x
# grid.MIN_PITCH_PX (a rescued cell must span at least two detector-resolution
# units); measured margin - texture inversions sit at pitch <= 8, legit
# rescues at >= 14.3 (baseline population cited on #94). Consumed in the
# pipeline's plausibility precondition, never inside the frozen tree.
RESCUE_MIN_PITCH_PX = 10.0


class CorroborationEvidence(BaseModel):
    """Block-lattice corroboration for a failing 1D read (S2, issue #94). The
    pipeline builds this ONLY for quilt-plausible reads (see
    RESCUE_MIN_PITCH_PX); a texture-scale read passes corroboration=None and
    stays no_grid by absence-identity."""

    min_axis_snr: float  # block_lattice.snr, the min-over-axes SNR statistic
    integer_lock: bool  # per-axis block-period integer lock, block >= pitch
    mean_cell_confidence: float  # cells.confidence on the recovered grid
    block_coherence: float  # coherence on the SNR-derived block lattice


def decide_verdict(
    grid_confidence: float,
    periodicity_score: float,
    coherence: float,
    label_repeat_found: bool,
    *,
    corroboration: CorroborationEvidence | None = None,
) -> str:
    """The frozen decision tree (S4, issue #70) plus the S2 (#94) additive
    corroboration leg.

    grid confidence < T1            -> no_grid, UNLESS corroboration rescues:
        exit (a) snr>=T4 AND integer_lock AND mcc>=T5 -> fall through the
                 remaining frozen tree below (readable / readable_no_repeat /
                 non_square_repeat by T2/T3);
        exit (b) snr>=T4 AND block_coherence>T3       -> non_square_repeat.
    else periodicity score < T2     -> readable / readable_no_repeat by the
                                       label detector's repeat
    else intra-cell coherence > T3  -> non_square_repeat
    else                            -> readable

    With corroboration=None the function is byte-identical to the frozen tree
    (the absence-identity property test). The corroboration branch adds new
    evidence inputs; it NEVER edits grid_confidence or any T1-T4 literal.
    Boundary semantics are the contract's own: exactly-at-threshold values
    are NOT below/above.
    """
    if grid_confidence < T1:
        rescued = False
        if corroboration is not None and corroboration.min_axis_snr >= T4:
            if corroboration.integer_lock and corroboration.mean_cell_confidence >= T5:
                rescued = True  # exit (a): fall through the remaining frozen tree
            elif corroboration.block_coherence > T3:
                return "non_square_repeat"  # exit (b): block structure, not cells
        if not rescued:
            return "no_grid"
    if periodicity_score < T2:
        return "readable" if label_repeat_found else "readable_no_repeat"
    if coherence > T3:
        return "non_square_repeat"
    return "readable"
