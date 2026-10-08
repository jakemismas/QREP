"""QREP's own numbers for the calculator matrix, read from the engine under test.

Values come from qrep.bridge.plan, the entry point the web app calls, so the
baseline records what a user saw rather than a re-derivation of the formulas.
The engine must be the start SHA's: D2 measures today's math, and D7 re-runs
the same harness after A1 and A2 change it (plan section 4.4).
"""

from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
BACKING_MARGIN = 64  # Settings.backing_margin default, eighths per axis


def engine_provenance(start_sha: str) -> dict:
    """Fail closed unless qrep/ in this checkout, working tree included, equals
    qrep/ at start_sha, and the imported qrep is this checkout's."""
    import qrep

    qrep_file = Path(qrep.__file__).resolve()
    if REPO.resolve() not in qrep_file.parents:
        raise RuntimeError(f"qrep imports from {qrep_file}, outside {REPO}")
    diff = subprocess.run(
        ["git", "-C", str(REPO), "diff", "--quiet", start_sha, "--", "qrep/"],
        check=False,
    )
    if diff.returncode != 0:
        raise RuntimeError(f"qrep/ differs from {start_sha}; measure on the start SHA only")

    def git(*args: str) -> str:
        out = subprocess.run(
            ["git", "-C", str(REPO), *args], check=True, capture_output=True, text=True
        )
        return out.stdout.strip()

    return {
        "qrep_file": str(qrep_file),
        "head": git("rev-parse", "HEAD"),
        "start_sha": git("rev-parse", start_sha),
        "qrep_tree": git("rev-parse", f"{start_sha}:qrep"),
    }


def _model(center_w: int, center_l: int, bands: list[int], wof: int | None) -> dict:
    # One cell size that tiles the center exactly; the backing, binding and
    # batting lines read only the finished size, so the grid content is moot.
    cell = math.gcd(center_w, center_l)
    fabrics = [{"id": "c", "name": "center", "color": "#888888"}]
    fabrics += [
        {"id": f"b{i}", "name": f"border {i}", "color": "#444444"}
        for i in range(1, len(bands) + 1)
    ]
    # A binding-only fabric keeps the binding on its own purchase line.
    fabrics.append({"id": "bind", "name": "binding", "color": "#222222"})
    model = {
        "schema_version": "1",
        "metadata": {"name": "calculator matrix row"},
        "palette": {"fabrics": fabrics},
        "center": {
            "rows": center_l // cell,
            "cols": center_w // cell,
            "cell_size": cell,
            "cells": [["c"] * (center_w // cell) for _ in range(center_l // cell)],
        },
        "borders": [{"fabric_id": f"b{i}", "width": b} for i, b in enumerate(bands, 1)],
        "binding": {"fabric_id": "bind"},
    }
    if wof is not None:
        model["settings"] = {"wof": wof}
    return model


def qrep_values(center_w: int, center_l: int, bands: list[int], wof: int | None = None) -> dict:
    """All lengths in eighths. wof None keeps the engine default (42 in today)."""
    from qrep import bridge

    reply = json.loads(bridge.plan(json.dumps(_model(center_w, center_l, bands, wof)), "historical"))
    if not reply["ok"]:
        raise RuntimeError(f"bridge.plan failed: {reply['error']}")
    result = reply["result"]
    summary = result["summary"]
    lines = result["yardage"]["lines"]
    pieces = result["plan"]["cut_pieces"]
    backing = next(line for line in lines if line["purpose"] == "backing")
    binding = next(line for line in lines if line["purpose"] == "binding")
    finished_l = summary["finished_height"]
    out = {
        "wof": summary["usable_width"],
        "finished_width": summary["finished_width"],
        "finished_height": finished_l,
        "backing": {
            "length_needed": backing["length_needed"],
            "quarter_yards": backing["quarter_yards"],
            # Today's backing is panels x (L + margin), so the count is exact.
            "panels": backing["length_needed"] // (finished_l + BACKING_MARGIN),
            "layout": "vertical",
        },
        "binding": {
            "strips": sum(p["quantity"] for p in pieces if p["component"] == "binding"),
            "length_needed": binding["length_needed"],
            "quarter_yards": binding["quarter_yards"],
        },
        "batting": {"width": summary["batting_width"], "height": summary["batting_height"]},
        "wide_back": None,
        "borders": [],
    }
    for i in range(1, len(bands) + 1):
        line = next(x for x in lines if x["fabric_id"] == f"b{i}" and x["purpose"] == "top")
        cuts = [p for p in pieces if p["component"] == "border" and p["fabric_id"] == f"b{i}"]
        out["borders"].append(
            {
                "length_needed": line["length_needed"],
                "quarter_yards": line["quarter_yards"],
                "pieces": sum(p["quantity"] for p in cuts),
                "cut_lengths": sorted({max(p["cut_width"], p["cut_height"]) for p in cuts}),
            }
        )
    return out
