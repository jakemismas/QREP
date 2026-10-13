"""The confirmed read's knobs, each with its source and its status.

Every knob is provisional (plan section 5.B): D5 measures the new read on the
corpus, and only Jake freezes a value or changes the L weight (plan section
7.2). B2a's sampling knobs live beside the code that uses them, and the
fabric-count range beside the request that carries it (qrep/contract.py must
not import qrep.vision, which loads cv2), so this table records those by
reference and holds each value once.
"""

from dataclasses import dataclass

from qrep.contract import FABRICS_MAX, FABRICS_MIN
from qrep.model.finished_size import CELL_MAX, CELL_MIN
from qrep.vision.read.geometry import MIN_PX_PER_SQUARE
from qrep.vision.read.sample import INSET, P

PROVISIONAL = "provisional"

# Weight on L* in the color distance, so lightness, which shading moves most,
# counts half: Jake's default (plan section 2.1, screen 3).
L_WEIGHT = 0.5
# Fabric counts the read tries when the request sets none, and accepts.
K_MIN = FABRICS_MIN
K_MAX = FABRICS_MAX
# A square takes its block majority only below this confidence.
VOTE_THRESHOLD = 0.8
# A block type votes only with at least this many copies.
VOTE_MIN_COPIES = 3
# Two blocks are copies of one type when their confidence-weighted agreement
# reaches this share of squares.
TYPE_AGREEMENT = 0.75
# A label fits its own shading surface only with this many squares: three per
# coefficient of the six-term quadratic in position.
SHADING_MIN_SQUARES = 18
# Rounds of shading fit and reassignment for one fabric count.
SHADING_ROUNDS = 10
# Lloyd iterations per k-means run, and deterministic seedings per count.
KMEANS_ITERATIONS = 100
KMEANS_SEEDINGS = 4
# The silhouette compares every pair of samples, so it runs on at most this
# many: 2000 x 2000 float64 distances take 32 MB.
SILHOUETTE_SAMPLES = 2000
# Photo pixels per inch assumed for the default size estimate.
ASSUMED_PPI = 10
# The default square size snaps to this step within these bounds, in eighths.
SIZE_STEP = 2
SQUARE_MIN = CELL_MIN
SQUARE_MAX = CELL_MAX
# Confidence of the default size estimate.
SIZE_ESTIMATE_CONFIDENCE = 0.0


@dataclass(frozen=True)
class Knob:
    value: float
    source: str
    status: str = PROVISIONAL


KNOBS: dict[str, Knob] = {
    "L_WEIGHT": Knob(
        L_WEIGHT,
        "Jake's default color distance (plan sections 2.1 and 5.B); on image0 with exact corners "
        "full Lab read 97.6 percent, L*0.5 99.0 and a,b only 99.9 (vision-06), and a,b only "
        "fails on value-only fabrics (exp7); D5 reports a weight sweep",
    ),
    "P": Knob(P, "qrep/vision/read/sample.py, the confirmed-grid prototype's value (plan B2a)"),
    "INSET": Knob(INSET, "qrep/vision/read/sample.py, inner 60 percent of a square (plan B2a)"),
    "MIN_PX_PER_SQUARE": Knob(
        MIN_PX_PER_SQUARE,
        "qrep/vision/read/geometry.py: L*0.5 stayed at or above 0.98 down to 7 px after JPEG q70 "
        "with exact corners (exp3); D5 and D10 set the final floor",
    ),
    "K_MIN": Knob(K_MIN, "qrep/contract.py FABRICS_MIN: below 2 there is nothing to tell apart"),
    "K_MAX": Knob(
        K_MAX, "qrep/contract.py FABRICS_MAX: the fabric cap of about 12 (SPEC.md section 3)"
    ),
    "VOTE_THRESHOLD": Knob(
        VOTE_THRESHOLD,
        "the old vote's VOTE_HIGH_MARGIN (qrep/vision/repeats.py), above which it never changed "
        "a square; not measured on the corpus",
    ),
    "VOTE_MIN_COPIES": Knob(
        VOTE_MIN_COPIES,
        "REBASELINE.md literal B5, kept for the block-consistent vote (#70 body and comment 0)",
    ),
    "TYPE_AGREEMENT": Knob(
        TYPE_AGREEMENT,
        "not measured: two copies of one block, each with 10 percent misreads, agree on about "
        "1 - 2 x 0.1 = 0.8 of their squares, while the fixture's two Double Irish Chain blocks "
        "agree on 8 of 25 = 0.32",
    ),
    "SHADING_MIN_SQUARES": Knob(
        SHADING_MIN_SQUARES, "not measured: three squares per coefficient of a six-term quadratic"
    ),
    "SHADING_ROUNDS": Knob(SHADING_ROUNDS, "not measured: a compute bound"),
    "KMEANS_ITERATIONS": Knob(KMEANS_ITERATIONS, "not measured: a compute bound"),
    "KMEANS_SEEDINGS": Knob(KMEANS_SEEDINGS, "not measured: a compute bound"),
    "SILHOUETTE_SAMPLES": Knob(
        SILHOUETTE_SAMPLES, "a memory bound: 2000 x 2000 float64 distances take 32 MB"
    ),
    "ASSUMED_PPI": Knob(
        ASSUMED_PPI,
        "qrep/vision/pipeline.py ASSUMED_PPI, the renderer's default scale; a photo's real "
        "resolution is unknown (#207)",
    ),
    "SIZE_STEP": Knob(SIZE_STEP, "1/4 in square sizes (plan A10 and section 2.1, screen 4)"),
    "SQUARE_MIN": Knob(
        SQUARE_MIN, "qrep/model/finished_size.py CELL_MIN, 3/4 in (REBASELINE.md literal B8)"
    ),
    "SQUARE_MAX": Knob(
        SQUARE_MAX, "qrep/model/finished_size.py CELL_MAX, 4 in (REBASELINE.md literal B9)"
    ),
    "SIZE_ESTIMATE_CONFIDENCE": Knob(
        SIZE_ESTIMATE_CONFIDENCE,
        "an assumed resolution carries no evidence of the quilt's real size; #207 asks for a "
        "confidence below 1.0",
    ),
}
