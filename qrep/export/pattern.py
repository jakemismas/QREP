"""Interim pattern export (E1b): today's booklet behind the v2 pattern contract.

bridge.export_pattern loads build_pattern from here lazily. A4a turns this
module into the qrep/export/pattern/ package and A4d switches build_pattern
to the new document; until then it renders the sprint 1 booklet for the
engine's own choice of method (strip when the grid has a repeating block,
historical otherwise) and fills the summary from the same purchase lines and
batting plan the booklet prints, so the screen and the PDF agree (PS-40).
"""

import base64
import tempfile
from pathlib import Path

from qrep.construct import compute_purchase_lines, get_strategy, infer_block_structure
from qrep.construct.finishing import batting_plan
from qrep.construct.plan import ConstructionPlan
from qrep.construct.yardage import YardageReport
from qrep.contract import BattingSize, FabricLine, PatternResult, PatternSummary, PurchaseLine
from qrep.export.pdf import render_booklet
from qrep.model.schema import Quilt

# A square read below this confidence counts as uncertain: the mark the web
# already draws (web/src/state/project.tsx:63), so the summary's count and
# the squares marked on screen agree.
UNCERTAIN_BELOW = 0.9


def build_pattern(quilt: Quilt) -> PatternResult:
    method, reason = _method(quilt)
    plan = get_strategy(method)(quilt)
    purchase = compute_purchase_lines(quilt, plan)
    return PatternResult(
        outcome="pattern_ready",
        pdf_b64=base64.b64encode(_booklet_bytes(quilt, plan)).decode("ascii"),
        summary=_summary(quilt, method, reason, purchase),
    )


def _method(quilt: Quilt) -> tuple[str, str]:
    # plan_strip needs a block period and raises without one. A period is not
    # enough: infer_block_structure also returns a period whose few blocks are
    # all different (up to its 8 types, the whole grid at worst), and strip
    # piecing that buys strip sets for every distinct block. So strip only
    # when some block type appears at least twice.
    structure = infer_block_structure(quilt.center.cells)
    if structure is None or max(structure.counts) < 2:
        return "historical", "No repeating block was found, so each square is cut and sewn on its own."
    size = structure.size
    return "strip", f"Blocks of {size} x {size} squares repeat across the quilt, so it is strip pieced."


def _booklet_bytes(quilt: Quilt, plan: ConstructionPlan) -> bytes:
    # reportlab embeds timestamps unless invariant mode is on; pinning it makes
    # the PDF byte-identical for identical inputs, natively and in the browser.
    from reportlab import rl_config

    previous = rl_config.invariant
    try:
        rl_config.invariant = 1
        with tempfile.TemporaryDirectory(prefix="qrep-pattern-") as scratch:
            path = Path(scratch) / "pattern.pdf"
            render_booklet(quilt, plan, path)
            return path.read_bytes()
    finally:
        rl_config.invariant = previous


def _summary(quilt: Quilt, method: str, reason: str, purchase: YardageReport) -> PatternSummary:
    top = {line.fabric_id: line.yards for line in purchase.lines if line.purpose == "top"}
    backing = next(line for line in purchase.lines if line.purpose == "backing")
    wide = purchase.wide_back
    batting = batting_plan(quilt.finished_width, quilt.finished_height, quilt.settings)
    uncertain = sum(
        value < UNCERTAIN_BELOW
        for row in quilt.center.effective_cell_confidence()
        for value in row
    )
    return PatternSummary(
        finished_width=quilt.finished_width,
        finished_height=quilt.finished_height,
        # The model records no size basis until A9 adds the field.
        size_basis=None,
        method=method,
        method_reason=reason,
        # The booklet labels each fabric by its model id (its fabric table's
        # ID column, beside the name, and every strip-set sequence), so the
        # screen shows the same label; the new document (A4b) prints letters.
        fabrics=[
            FabricLine(
                letter=fabric.id,
                fabric_id=fabric.id,
                name=fabric.name,
                yards=top.get(fabric.id, 0.0),
            )
            for fabric in quilt.palette.fabrics
        ],
        binding=[
            PurchaseLine(fabric_id=line.fabric_id, name=line.name, yards=line.yards)
            for line in purchase.lines
            if line.purpose == "binding"
        ],
        backing=PurchaseLine(fabric_id=None, name=backing.name, yards=backing.yards),
        # Null when MATH.md F11 offers no wide back for this size.
        wide_back=(
            PurchaseLine(fabric_id=None, name=wide.name, yards=wide.yards) if wide else None
        ),
        batting=BattingSize(width=batting.width, height=batting.height),
        strip_width=quilt.settings.wof,
        backing_width=quilt.settings.backing_width,
        uncertain_squares=uncertain,
    )
