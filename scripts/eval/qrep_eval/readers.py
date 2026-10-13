"""The readers the harness scores, behind one Reading shape.

auto is the automatic read (qrep.vision.reverse with no corners) and
auto-corners the same read given the simulated corners and the true fabric
count; main keeps both until B6b deletes them. confirmed is the new read
(qrep.bridge.read_confirmed), which refuses to run while the bridge is B2b's
stub. Each Reading records what the reader received, so a report measures what
the pipeline used (vision-13).
"""

import json
import time
from dataclasses import dataclass, field

from qrep.contract import ReadRequest

# The automatic read has no refusal outcome. no_grid shows "Could not read this
# photo" (a refusal). non_square_repeat shows "squares uncertain" but sets no failure
# panel (web/src/model/verdictStory.ts:105), and without one the old app still offers
# "Open in the editor" and so a PDF (web/src/shell/photo/ResultsScreen.tsx:240): a
# warning, not a hold. The readable verdicts show the read.
AUTO_OUTCOMES = {
    "readable": "read",
    "readable_no_repeat": "read",
    "non_square_repeat": "warned",
    "no_grid": "refused",
}
# The old app outlines a square as uncertain below this confidence
# (web/src/state/photo.tsx:36, UNCERTAIN_THRESHOLD), so that is what it flagged.
AUTO_LOW_CONFIDENCE_BELOW = 0.9


@dataclass
class Reading:
    outcome: str
    verdict: str | None
    rows: int
    cols: int
    colors: list[str]
    cells: list[list[int]] | None
    confidence: list[list[float]] | None
    cell_size_eighths: int | None
    band_eighths: list[int]
    low_confidence_below: float | None
    flagged_regions: list[tuple[int, int, int, int]]
    seconds: float
    received: dict
    diagnostics: dict = field(default_factory=dict)

    @property
    def k(self) -> int:
        return len(self.colors)


def _from_quilt(quilt: dict) -> tuple[list[str], list[list[int]], list[list[float]] | None, int, list[int]]:
    fabrics = quilt["palette"]["fabrics"]
    index = {fabric["id"]: i for i, fabric in enumerate(fabrics)}
    center = quilt["center"]
    cells = [[index[fabric_id] for fabric_id in row] for row in center["cells"]]
    return ([f["color"].lower() for f in fabrics], cells, center.get("cell_confidence"),
            center["cell_size"], [band["width"] for band in quilt.get("borders", [])])


def read_auto(path: str, staged_size: tuple[int, int], corners=None, fabrics: int | None = None) -> Reading:
    from qrep.vision import reverse

    start = time.perf_counter()
    result = reverse(path, corners=corners, fabrics=fabrics)
    seconds = time.perf_counter() - start
    d = result.diagnostics
    colors, cells, confidence, cell_size, bands = _from_quilt(result.quilt.model_dump(mode="json"))
    rows, cols = (int(n) for n in d["interior_dims"])
    tier = d.get("detection_tier")
    return Reading(
        outcome=AUTO_OUTCOMES[d["verdict"]],
        verdict=d["verdict"],
        rows=rows,
        cols=cols,
        colors=colors,
        cells=cells,
        confidence=confidence,
        cell_size_eighths=cell_size,
        band_eighths=bands,
        low_confidence_below=AUTO_LOW_CONFIDENCE_BELOW,
        flagged_regions=[],
        seconds=seconds,
        received={"staged_size": list(staged_size),
                  "corners": [list(map(float, p)) for p in corners] if corners else None,
                  "fabrics": fabrics},
        diagnostics={
            "grid_diagnosis": d.get("grid_diagnosis"),
            "detection_tier": int(tier) if tier is not None else None,
            "detected_corners": [list(map(float, p)) for p in d.get("detected_corners", [])],
            "pitch_px": [float(v) for v in d.get("pitch_px", [])],
            "border_strips": {side: int(n) for side, n in (d.get("border_strips") or {}).items()},
            "palette_k": int(d["palette_k"]) if d.get("palette_k") is not None else None,
        },
    )


class ReaderUnavailable(RuntimeError):
    pass


def _probe_request() -> str:
    corners = {"top_left": {"x": 1.0, "y": 1.0}, "top_right": {"x": 9.0, "y": 1.0},
               "bottom_right": {"x": 9.0, "y": 9.0}, "bottom_left": {"x": 1.0, "y": 9.0}}
    return json.dumps({
        "token": "eval-probe-no-such-file.png",
        "frame": {"kind": "field", "corners": corners},
        "crop_offset": {"x": 0.0, "y": 0.0},
        "counts": {"blocks_across": 1, "blocks_down": 1,
                   "squares_per_block_across": 2, "squares_per_block_down": 2},
    })


def confirmed_unavailable() -> str | None:
    """Why the confirmed reader cannot run, or None when it can. A valid request for a
    photo that does not exist reaches the read: B2b's read fails it as a value error,
    while the stub answers not_implemented."""
    from qrep import bridge

    envelope = json.loads(bridge.read_confirmed(_probe_request()))
    error = envelope.get("error") or {}
    if error.get("kind") == "not_implemented":
        return ("the confirmed reader needs B2b: qrep.bridge.read_confirmed is still the stub "
                f"({error.get('message')})")
    return None


def read_confirmed(request: ReadRequest, staged_size: tuple[int, int]) -> Reading:
    from qrep import bridge

    start = time.perf_counter()
    envelope = json.loads(bridge.read_confirmed(request.model_dump_json()))
    seconds = time.perf_counter() - start
    if not envelope.get("ok"):
        error = envelope.get("error") or {}
        if error.get("kind") == "not_implemented":
            raise ReaderUnavailable(error.get("message"))
        raise RuntimeError(f"read_confirmed failed: {error}")
    result = envelope["result"]
    received = {"staged_size": list(staged_size), "request": json.loads(request.model_dump_json())}
    if result["outcome"] != "read":
        return Reading(result["outcome"], None, 0, 0, [], None, None, None, [], None, [],
                       seconds, received, {"reason": result.get("reason")})
    colors, cells, confidence, cell_size, bands = _from_quilt(result["model"])
    return Reading(
        outcome="read",
        verdict=None,
        rows=len(cells),
        cols=len(cells[0]) if cells else 0,
        colors=colors,
        cells=cells,
        confidence=confidence,
        cell_size_eighths=cell_size,
        band_eighths=bands,
        # B2b and B3 define the new read's flags; until a result carries them,
        # no square counts as flagged (#237).
        low_confidence_below=None,
        flagged_regions=[],
        seconds=seconds,
        received=received,
    )
