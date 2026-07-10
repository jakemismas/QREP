"""The reverse pipeline: image path in, recovered Quilt plus diagnostics out.

Stage order note: borders are detected before the repeat search runs, and the
repeat search sees only the interior grid, because the border strips ARE the
periodicity break (2.5 pitches on the fixture by design); running the repeat
on the full grid would dilute the exact axis periods the contract pins.

Absolute scale is unknowable from a single photo; cell size is emitted as a
low-confidence guess assuming ASSUMED_PPI pixels per inch, and the user
corrects finished size with one JSON edit or the sizing viewer.
"""

from pathlib import Path

import cv2
from pydantic import BaseModel

from qrep.model.schema import (
    STAGES,
    Binding,
    BorderBand,
    Fabric,
    GridRegion,
    Palette,
    Provenance,
    Quilt,
    QuiltMetadata,
)
from qrep.model.finished_size import apply_finished_size
from qrep.vision.borders import detect_borders
from qrep.vision.cells import assign_cells
from qrep.vision.grid import estimate_grid
from qrep.vision.palette import extract_palette
from qrep.vision.rectify import rectify
from qrep.vision.repeats import (
    coherence_with_sublattice,
    detect_repeat,
    image_periodicity,
    vote_cells,
)
from qrep.vision.verdict import INTEGER_RATIO_EPSILON, T2, decide_verdict

ASSUMED_PPI = 10  # matches the renderer default; a guess for real photos


class ReverseResult(BaseModel):
    quilt: Quilt
    diagnostics: dict


def _fallback_result(
    image: "cv2.typing.MatLike",
    reason: str,
    rect=None,
    palette=None,
) -> ReverseResult:
    """S3 (issue #69): unreadable input is a typed zero-confidence result,
    never an exception. The minimal 2x2 fallback quilt keeps every consumer
    model-safe; grid_diagnosis carries the structured reason."""
    height, width = image.shape[:2]
    if palette is not None:
        fabric_ids = [f"f{i}" for i in range(palette.k)]
        fabrics_out = [
            Fabric(id=fid, name=f"Fabric {i + 1}", color=palette.colors_hex[i])
            for i, fid in enumerate(fabric_ids)
        ]
    else:
        fabric_ids = ["f0"]
        fabrics_out = [Fabric(id="f0", name="Fabric 1", color="#808080")]
    stage_confidence = {
        "rectify": round(rect.confidence, 6) if rect is not None else 0.0,
        "palette": round(palette.confidence, 6) if palette is not None else 0.0,
        "grid": 0.0,
        "cells": 0.0,
        "repeat": 0.0,
        "border": 0.0,
    }
    assert set(stage_confidence) == set(STAGES)
    quilt = Quilt(
        metadata=QuiltMetadata(
            name="Recovered quilt",
            notes=(
                "QREP could not read a square grid in this photo "
                f"(reason: {reason}). This placeholder is not a recovered design."
            ),
        ),
        palette=Palette(fabrics=fabrics_out),
        center=GridRegion(
            rows=2,
            cols=2,
            cell_size=12,
            cells=[[fabric_ids[0], fabric_ids[0]], [fabric_ids[0], fabric_ids[0]]],
            cell_confidence=[[0.0, 0.0], [0.0, 0.0]],
        ),
        borders=[],
        binding=Binding(fabric_id=fabric_ids[0]),
        provenance=Provenance(source="cv", stage_confidence=stage_confidence),
    )
    diagnostics = {
        "identity": rect.identity if rect is not None else True,
        "detection_tier": rect.tier if rect is not None else None,
        "grid_diagnosis": reason,
        "verdict": "no_grid",
        "detected_corners": rect.corners
        if rect is not None
        else [(0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height))],
        "rectified_size": [rect.image.shape[1], rect.image.shape[0]]
        if rect is not None
        else [width, height],
        "pitch_px": [0.0, 0.0],
        "border_strips": {"left": 0, "right": 0, "top": 0, "bottom": 0},
        "border_widths_px": {"left": 0.0, "right": 0.0, "top": 0.0, "bottom": 0.0},
        "repeat_period": [0, 0],
        "palette_k": palette.k if palette is not None else 0,
        "interior_dims": [2, 2],
        "periodicity": {"period_px": [0, 0], "score_x": 0.0, "score_y": 0.0, "score": 0.0},
        "coherence": 0.0,
        "integer_ratio": {"x": 0.0, "y": 0.0, "passed": False},
        "block_period_cells": None,
        "repeat_vote": {"applied": False, "cells_changed": 0},
        "size_source": "guess",
        "size_is_guess": True,
        "size_requested": None,
        "size_achieved": None,
    }
    return ReverseResult(quilt=quilt, diagnostics=diagnostics)


def reverse(
    image_path: str | Path,
    corners: list[tuple[float, float]] | None = None,
    fabrics: int | None = None,
    *,
    finished_width: int | None = None,
    finished_height: int | None = None,
) -> ReverseResult:
    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"could not read image: {image_path}")

    try:
        rect = rectify(image, corners)
    except ValueError:
        # rectify's "no quilt found": typed result, never a raise (S3)
        return _fallback_result(image, "no_quilt_found")
    # S5: lighting normalization only on trusted crops - detection tiers
    # 0-2 or user-confirmed corners; a tier-3 full frame would feed the
    # detrend content structure instead of lighting (see palette.py)
    trusted_crop = corners is not None or rect.tier in (0, 1, 2)
    palette = extract_palette(
        rect.image, fabrics, mask=rect.mask, lighting_detrend=trusted_crop
    )
    # S4: image-level periodicity runs BEFORE the grid so a trustworthy
    # period (score at or above T2, per axis) can feed the pitch back
    periodicity = image_periodicity(rect.image)
    hint = (
        float(periodicity.period_x) if periodicity.score_x >= T2 else 0.0,
        float(periodicity.period_y) if periodicity.score_y >= T2 else 0.0,
    )
    try:
        grid = estimate_grid(
            rect.image,
            mask=rect.mask,
            warp_magnitude=rect.warp_magnitude,
            period_hint=hint if hint != (0.0, 0.0) else None,
        )
    except ValueError as error:
        reason = "profile_too_short" if "too short" in str(error) else "no_periodicity"
        return _fallback_result(image, reason, rect=rect, palette=palette)
    cells = assign_cells(rect.image, grid.x.boundaries, grid.y.boundaries, palette.centers_lab)
    borders = detect_borders(cells.assignments, grid.x.boundaries, grid.y.boundaries)

    left, right = borders.strips["left"], borders.strips["right"]
    top, bottom = borders.strips["top"], borders.strips["bottom"]
    total_rows = len(cells.assignments)
    total_cols = len(cells.assignments[0])
    interior = [
        row[left : total_cols - right] for row in cells.assignments[top : total_rows - bottom]
    ]
    interior_conf = [
        row[left : total_cols - right] for row in cells.cell_confidence[top : total_rows - bottom]
    ]
    repeat = detect_repeat(interior)

    # S4: integer-ratio cross-check (period_px / pitch_px within the frozen
    # epsilon of an integer confirms the pitch), coherence, voting, verdict
    def _ratio_ok(period: float, pitch: float) -> tuple[float, bool]:
        if period <= 0 or pitch <= 0:
            return 0.0, False
        ratio = period / pitch
        return ratio, round(ratio) >= 1 and abs(ratio - round(ratio)) <= INTEGER_RATIO_EPSILON

    ratio_x, ok_x = _ratio_ok(float(periodicity.period_x), grid.x.pitch)
    ratio_y, ok_y = _ratio_ok(float(periodicity.period_y), grid.y.pitch)
    ratio_passed = ok_x and ok_y

    vote_changed = 0
    vote_applied = False
    if ratio_passed and interior and repeat.period_rows > 0 and repeat.period_cols > 0:
        voted, vote_changed, vote_applied = vote_cells(
            interior, interior_conf, repeat.period_rows, repeat.period_cols
        )
        if vote_changed > 0:
            interior = voted

    coherence = coherence_with_sublattice(rect.image, grid.x.boundaries, grid.y.boundaries)

    fabric_ids = [f"f{i}" for i in range(palette.k)]
    cell_size = max(1, round(grid.x.pitch * 8 / ASSUMED_PPI))
    border_bands = []
    if any(borders.strips.values()) and borders.fabric_index is not None:
        mean_border_px = sum(borders.widths_px.values()) / 4
        border_bands.append(
            BorderBand(
                fabric_id=fabric_ids[borders.fabric_index],
                width=max(1, round(mean_border_px * 8 / ASSUMED_PPI)),
            )
        )
    binding_fabric = (
        fabric_ids[borders.fabric_index] if borders.fabric_index is not None else fabric_ids[0]
    )
    stage_confidence = {
        "rectify": round(rect.confidence, 6),
        "palette": round(palette.confidence, 6),
        "grid": round(grid.confidence, 6),
        "cells": round(cells.confidence, 6),
        "repeat": round(repeat.confidence, 6),
        "border": round(borders.confidence, 6),
    }
    assert set(stage_confidence) == set(STAGES)

    quilt = Quilt(
        metadata=QuiltMetadata(
            name="Recovered quilt",
            notes=(
                "Recovered by the QREP CV pipeline. Cell size is a low-confidence "
                f"guess assuming {ASSUMED_PPI} px per inch; correct the finished "
                "size with one edit and all downstream math recomputes."
            ),
        ),
        palette=Palette(
            fabrics=[
                Fabric(id=fid, name=f"Fabric {i + 1}", color=palette.colors_hex[i])
                for i, fid in enumerate(fabric_ids)
            ]
        ),
        center=GridRegion(
            rows=len(interior),
            cols=len(interior[0]) if interior else 0,
            cell_size=cell_size,
            cells=[[fabric_ids[idx] for idx in row] for row in interior],
            cell_confidence=[[round(v, 4) for v in row] for row in interior_conf],
        ),
        borders=border_bands,
        binding=Binding(fabric_id=binding_fabric),
        provenance=Provenance(source="cv", stage_confidence=stage_confidence),
    )
    # S6 (issue #72): user-entered finished size reconciles onto the grid;
    # ASSUMED_PPI survives only as the size_source="guess" fallback
    size_requested = None
    size_achieved = None
    if finished_width is not None or finished_height is not None:
        quilt, size_requested, size_achieved = apply_finished_size(
            quilt, finished_width, finished_height
        )
        quilt.metadata.notes = (
            "Recovered by the QREP CV pipeline. Finished size provided by "
            "you; squares and borders were fitted to it."
        )

    verdict = decide_verdict(
        stage_confidence["grid"],
        periodicity.score,
        coherence,
        repeat.period_rows > 0 and repeat.period_cols > 0,
    )
    block_period_cells = (
        [int(round(ratio_x)), int(round(ratio_y))] if ratio_passed else None
    )
    diagnostics = {
        "identity": rect.identity,
        "detection_tier": rect.tier,
        "grid_diagnosis": grid.diagnosis,
        "verdict": verdict,
        "detected_corners": rect.corners,
        "rectified_size": [rect.image.shape[1], rect.image.shape[0]],
        "pitch_px": [grid.x.pitch, grid.y.pitch],
        "border_strips": borders.strips,
        "border_widths_px": borders.widths_px,
        "repeat_period": [repeat.period_rows, repeat.period_cols],
        "palette_k": palette.k,
        "interior_dims": [len(interior), len(interior[0]) if interior else 0],
        "periodicity": {
            "period_px": [periodicity.period_x, periodicity.period_y],
            "score_x": periodicity.score_x,
            "score_y": periodicity.score_y,
            "score": periodicity.score,
        },
        "coherence": coherence,
        "integer_ratio": {"x": ratio_x, "y": ratio_y, "passed": ratio_passed},
        "block_period_cells": block_period_cells,
        "repeat_vote": {"applied": vote_applied, "cells_changed": vote_changed},
        "size_source": "user" if size_achieved is not None else "guess",
        "size_is_guess": size_achieved is None,
        "size_requested": size_requested,
        "size_achieved": size_achieved,
    }
    return ReverseResult(quilt=quilt, diagnostics=diagnostics)
