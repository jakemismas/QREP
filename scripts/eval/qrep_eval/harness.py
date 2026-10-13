"""One unit of eval work: stage one image at one resolution and condition, run every
reader trial on it, and score each reading into a report row.

Decode path: native. cv2.imread decodes the source, cv2.resize with INTER_AREA
brings it to the app's cap (corpus.cap_size), a degradation applies on top, and
the staged pixels go to the reader as a lossless PNG (the untouched source when
nothing changed). D4b adds the browser decode path.
"""

import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import cv2

from qrep.contract import BorderBand, Corners, OuterEdgeFrame, Point, ReadRequest
from qrep_eval import annotation as an
from qrep_eval import corpus, degrade, readers, scoring, simulate

DECODE_PATH = ("native: cv2.imread (IMREAD_COLOR), cv2.resize INTER_AREA to the cap with the app's "
               "targetSize rounding, staged to the reader as a lossless PNG")
HARMONICS = (2.0, 3.0, 0.5, 1 / 3)


@dataclass
class Unit:
    """One staged image and everything needed to read and score it."""

    photo: str
    group: str  # "corpus", "stress" or "named"
    tier: str
    split: str
    license: str
    device_class: str
    resolution: str
    cap: int | None
    condition: str
    source: str
    canvas: tuple[int, int]
    truth: corpus.TruthView
    truth_label: str
    readers: tuple[str, ...]
    radii: tuple[float, ...]
    trials: int
    seed: str
    annotation: an.Annotation | None = None
    truth_cells: list[list[int]] | None = None
    truth_colors: list[str] | None = None
    extra: dict = field(default_factory=dict)


def _field_box(corners: list[tuple[float, float]]) -> tuple[float, float, float, float]:
    xs, ys = [x for x, _ in corners], [y for _, y in corners]
    return min(xs), min(ys), max(xs), max(ys)


def stage(unit: Unit, workdir: Path) -> tuple[str, tuple[int, int]]:
    """The image the reader reads, and its (width, height)."""
    image = cv2.imread(unit.source, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"cv2 could not decode {unit.source}")
    height, width = image.shape[:2]
    if (width, height) != tuple(unit.canvas):
        raise ValueError(f"decoded {width} x {height}, the canvas is {unit.canvas[0]} x {unit.canvas[1]}")
    size = corpus.cap_size(width, height, unit.cap)
    if size != (width, height):
        image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    if unit.condition == "clean":
        if size == (width, height):
            return unit.source, size
    else:
        corners = scale_corners(unit.truth.corners, unit.canvas, size)
        image, _ = degrade.apply(unit.condition, image, _field_box(corners))
        size = (image.shape[1], image.shape[0])
    path = workdir / f"{unit.photo}-{unit.resolution}-{unit.condition}.png"
    if not cv2.imwrite(str(path), image):
        raise RuntimeError(f"could not write {path}")
    return str(path), size


def scale_corners(corners, canvas: tuple[int, int], size: tuple[int, int]) -> list[tuple[float, float]]:
    """Canvas pixels to staged pixels, refusing a staged image of another shape (the
    same 1 percent rule as annotation.to_read_request)."""
    if abs(size[0] / size[1] - canvas[0] / canvas[1]) / (canvas[0] / canvas[1]) > 0.01:
        raise ValueError(f"staged {size} is not the shape of the canvas {canvas}")
    sx, sy = size[0] / canvas[0], size[1] / canvas[1]
    return [(x * sx, y * sy) for x, y in corners]


def _truth_dims(truth: corpus.TruthView) -> tuple[int, int] | None:
    c = truth.counts
    if c is None:
        return None
    return c.blocks_down * c.squares_per_block_down, c.blocks_across * c.squares_per_block_across


def _harmonic(read: tuple[int, int], true: tuple[int, int]) -> bool:
    if read == true or 0 in read:
        return False
    return any(r != t and any(abs(r / t - h) < 1e-9 for h in HARMONICS) for r, t in zip(read, true))


def score(unit: Unit, reading: readers.Reading) -> dict:
    """The row's scores: outcome, dims and fabric count against truth, and the square
    scores when the unit has cell truth."""
    out: dict = {"outcome": reading.outcome, "verdict": reading.verdict,
                 "read_dims": [reading.rows, reading.cols], "k_read": reading.k}
    true_dims = _truth_dims(unit.truth)
    shown = reading.outcome != "refused"
    if true_dims is not None:
        out["truth_dims"] = list(true_dims)
        out["dims_exact"] = shown and (reading.rows, reading.cols) == true_dims
        out["harmonic"] = shown and _harmonic((reading.rows, reading.cols), true_dims)
        counts = unit.truth.counts
        out["periodic"] = counts.blocks_across * counts.blocks_down > 1
    if unit.truth.fabric_count is not None:
        out["k_truth"] = unit.truth.fabric_count
        out["k_exact"] = shown and reading.k == unit.truth.fabric_count
    if unit.truth_cells is not None:
        out.update(_score_cells(unit, reading))
    return out


def _score_cells(unit: Unit, reading: readers.Reading) -> dict:
    squares = sum(len(row) for row in unit.truth_cells)
    k_truth = len(unit.truth_colors)
    if reading.outcome != "read" or reading.cells is None:
        # A refusal or a hold ships no PDF: no confident-wrong square, no correct interior.
        return {"squares": squares, "accuracy_many_to_one": None, "accuracy_one_to_one": None,
                "fully_correct": False, "confident_wrong": 0, "k_mismatch": None}
    confidence = reading.confidence or [[1.0] * len(row) for row in reading.cells]
    many = scoring.map_many_to_one(reading.colors, unit.truth_colors)
    one = scoring.map_one_to_one(reading.colors, unit.truth_colors)
    kwargs = {"low_confidence_below": reading.low_confidence_below,
              "flagged_regions": reading.flagged_regions}
    m2o = scoring.score_squares(unit.truth_cells, reading.cells, many, confidence, **kwargs)
    o2o = scoring.score_squares(unit.truth_cells, reading.cells, one, confidence, **kwargs)
    truth_bands = scoring.truth_band_inches(unit.truth.bands, reading.cell_size_eighths)
    bands_ok = scoring.bands_match(truth_bands, scoring.read_band_inches(reading.band_eighths))
    return {
        "squares": squares,
        "accuracy_many_to_one": m2o.accuracy,
        "accuracy_one_to_one": o2o.accuracy,
        "fully_correct": scoring.fully_correct_interior(m2o, k_truth=k_truth, k_read=reading.k,
                                                        bands_ok=bands_ok),
        "confident_wrong": m2o.confident_wrong,
        "k_mismatch": scoring.k_mismatch(k_read=reading.k, k_truth=k_truth),
        "bands_ok": bands_ok,
    }


def _base_row(unit: Unit) -> dict:
    return {
        "photo": unit.photo, "group": unit.group, "tier": unit.tier, "split": unit.split,
        "license": unit.license, "device_class": unit.device_class, "resolution": unit.resolution,
        "condition": unit.condition, "truth": unit.truth_label, "provenance": unit.truth.provenance,
        "picker": simulate.PICKER_ANSWER, **unit.extra,
    }


def _confirmed_request(unit: Unit, token: str, size: tuple[int, int], corners) -> ReadRequest:
    if unit.annotation is not None:
        request = an.to_read_request(unit.annotation, token, size,
                                     prefer=an.FRAME_TRUTH + corpus.PROPOSALS)
    else:
        request = ReadRequest(
            token=token,
            frame=OuterEdgeFrame(kind="outer_edge", corners=Corners(**{
                n: Point(x=0.0, y=0.0) for n in ("top_left", "top_right", "bottom_right", "bottom_left")}),
                bands=[BorderBand(width_squares=w) for w in unit.truth.bands]),
            crop_offset=Point(x=0.0, y=0.0), counts=unit.truth.counts,
            fabric_count=unit.truth.fabric_count)
    names = ("top_left", "top_right", "bottom_right", "bottom_left")
    frame = request.frame.model_copy(update={"corners": Corners(**{
        n: Point(x=x, y=y) for n, (x, y) in zip(names, corners)})})
    return request.model_copy(update={"frame": frame})


def run_unit(unit: Unit) -> list[dict]:
    """Every reader trial on one staged image, each as a report row. An error becomes a
    row with outcome error, so the report counts it instead of shrinking n silently."""
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="qrep-eval-") as tmp:
        try:
            path, size = stage(unit, Path(tmp))
        except Exception as error:  # noqa: BLE001 - recorded on the row, never swallowed
            return [{**_base_row(unit), "reader": r, "outcome": "error", "error": repr(error)}
                    for r in unit.readers]
        corners = (scale_corners(unit.truth.corners, unit.canvas, size)
                   if unit.truth.corners is not None else None)
        pitch = (simulate.square_pitch(corners, unit.truth.counts, unit.truth.bands)
                 if corners is not None and unit.truth.counts is not None else None)
        fabrics = unit.truth.fabric_count
        if fabrics is not None and not 2 <= fabrics <= 12:
            fabrics = None
        for name in unit.readers:
            jobs: list[tuple[dict, object]] = []
            if name == "auto":
                jobs.append(({"radius_px": None}, lambda: readers.read_auto(path, size)))
            elif corners is not None and unit.truth.counts is not None:
                key = f"{unit.seed}|{unit.photo}|{unit.resolution}|{unit.condition}"
                for trial in simulate.corner_trials(corners, unit.radii, unit.trials, key, bounds=size):
                    meta = {"radius_px": trial.radius_px, "trial": trial.trial,
                            "radius_squares": simulate.radius_in_squares(trial.radius_px, pitch)
                            if pitch else None, "variant": "true"}
                    if name == "auto-corners":
                        jobs.append((meta, lambda c=trial.corners: readers.read_auto(path, size, c, fabrics)))
                    else:
                        request = _confirmed_request(unit, path, size, trial.corners)
                        jobs.append((meta, lambda q=request: readers.read_confirmed(q, size)))
                        if trial.radius_px == 0:
                            variants, _ = simulate.miscount_variants(unit.truth.counts)
                            for kind, counts in variants:
                                miscount = request.model_copy(update={"counts": counts})
                                jobs.append(({**meta, "variant": kind},
                                             lambda q=miscount: readers.read_confirmed(q, size)))
            for meta, call in jobs:
                row = {**_base_row(unit), "reader": name, **meta}
                try:
                    reading = call()
                except readers.ReaderUnavailable:
                    raise
                except Exception as error:  # noqa: BLE001 - recorded on the row, never swallowed
                    rows.append({**row, "outcome": "error", "error": repr(error),
                                 "received": {"staged_size": list(size)}})
                    continue
                rows.append({**row, **score(unit, reading), "seconds": round(reading.seconds, 3),
                             "received": reading.received, "diagnostics": reading.diagnostics})
    return json.loads(json.dumps(rows))
