#!/usr/bin/env python3
"""Generate and check the tables of the sprint 5 re-baseline record.

The record, docs/sprint-5/REBASELINE.md, classifies every test at the recorded commit as
KEEP, RETIRE or REEXPRESS and names the ticket that executes each retirement and
re-expression. This script derives those tables mechanically:

1. Python: `python -m pytest --collect-only -q -p no:cacheprovider` (with
   PYTHONDONTWRITEBYTECODE=1) lists every node id. Each test function is analysed with `ast`
   for the qrep symbols it reaches: imports, attribute chains, module helpers, pytest
   fixtures, CLI commands, the corners or no-corners call shape of reverse() and rectify(),
   asserted diagnostics keys, fixture-loader modules and qrep source files read as text.
2. Web: every vitest file (web/src/**/*.test.ts) and Playwright spec (web/e2e/*.spec.ts) is
   parsed statically for test(), it() and describe() calls. Titles built in loops come from
   declared expanders that mirror the loop sources.
3. Every symbol, scanned web file and e2e surface is looked up in the declared fate maps.
   A fixed rule turns the fates into a class. Declared per-test overrides, each with its
   reason, settle what the rule cannot. Every RETIRE and REEXPRESS row resolves to a ticket.
4. The tables are rendered into the marked blocks of the record.

Run it from the repo root with the repo venv:
    .venv/Scripts/python scripts/rebaseline_inventory.py --check       # exit 0: record matches
    .venv/Scripts/python scripts/rebaseline_inventory.py --write       # rewrite the blocks
    .venv/Scripts/python scripts/rebaseline_inventory.py --list RETIRE # ids, one per line

Inputs must be the recorded commit's. The script refuses (exit 2) when pyproject.toml,
qrep/, tests/, web/src/ or web/e2e/ in --repo differ from that commit. Once sprint-5 tickets
change those paths, verify against a separate checkout of the recorded commit:
    git worktree add --detach ../qrep-rebaseline 834d8be60cbf6f11354c4b5e6fbac5ffd90f6641
    .venv/Scripts/python scripts/rebaseline_inventory.py --check --repo ../qrep-rebaseline

Writes: --write rewrites only the generated blocks of the output file. --check and --list
write nothing; the collection runs with bytecode writing and the pytest cache disabled.
Exit codes: 0 match (or written), 1 the record differs from a fresh generation, 2 the
record cannot be generated at the recorded commit.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

GENERATOR_VERSION = "2.2"
RECORDED_COMMIT = "834d8be60cbf6f11354c4b5e6fbac5ffd90f6641"
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "sprint-5" / "REBASELINE.md"
INPUT_PATHS = ("pyproject.toml", "qrep", "tests", "web/src", "web/e2e")
COLLECT_COMMAND = ("python -m pytest --collect-only -q -p no:cacheprovider "
                   "(PYTHONDONTWRITEBYTECODE=1)")
# Test counts observed at the recorded commit: pytest 569 passed + 1 skipped (setup handoff,
# section 4); vitest 252 and Playwright 48 passed (read-only tests recon).
EXPECTED_COUNTS = {"pytest": 570, "vitest": 252, "playwright": 48}
BLOCKS = ("provenance", "totals", "closing", "py-retired", "py-reexpressed", "py-kept",
          "web-retired", "web-reexpressed", "web-kept", "support")

KEEP, RETIRE, REEXPRESS, UNSURE, MIXED = "KEEP", "RETIRE", "REEXPRESS", "UNSURE", "MIXED"
CLASSES = (KEEP, RETIRE, REEXPRESS)
SUITES = ("pytest", "vitest", "playwright")

# ---------------------------------------------------------------------------
# Tickets that execute retirements and re-expressions, by their exact ids in the sprint-5
# plan: a split ticket is named by its part (B6a or B6b), never by its base id, because each
# part has its own worker. Scope lives in the plan; the titles only label the tables, in the
# plan's order. C8b is absent on purpose: the idle vision prefetch stays (plan section 5.C,
# decision 4), so C8b executes no entry, and a row that names it is refused as unknown.
# ---------------------------------------------------------------------------
TICKETS = {
    "A1": "Backing, binding and batting math",
    "A2b": "Purchase lines from the cutting layout and the 40 in default",
    "A6": "Fixture at the new defaults and the one consolidated [bless]",
    "A7": "Engine cleanup (contract)",
    "A8": "Convert the legacy byte pins to semantic checks",
    "A10": "Rotary-friendly finished sizing in one model module",
    "B6a": "Re-express the read tests, add the parity check, move native OpenCV to 4.11",
    "B6b": "Delete the automatic detection stack",
    "C2a": "Your pattern screen with one Download pattern (PDF) button",
    "C2b": "Fabric widths, finished size and shopping lines on Your pattern",
    "C3b": "Confirm screen in the photo flow, with crop-aware staging",
    "C3c": "Read with confirmed corners and counts: suggestions, one progress line and the fit "
           "check",
    "C6a": "Remove the editor (archived at archive/editor-v0.3)",
    "C6b": "Remove the old photo-flow screens and the web verdict surface",
}
RETIRE_TICKET_BY_GROUP = {"detector": "B6b", "dead-code": "A7"}

# ---------------------------------------------------------------------------
# Deletion schedule (HANDOFF 2.3, 2.4 and 5; expand, then contract)
# ---------------------------------------------------------------------------
SCHEDULE = [
    ("detector", "B6b", "automatic detection stack: rectify tiers 0 to 3 and GrabCut, grid "
     "estimation, periodicity, block-lattice SNR, the verdict tree, corroboration, the border "
     "scan, the palette detrend, the wasm gate and their frozen literals, after B6a has moved "
     "the read tests onto the confirmed read"),
    ("editor", "C6a", "web editor: paint, palette editing, the seams tool, the Sizing tab, undo "
     "and redo, autosave and resume, save and open project files, the blank-grid start, the "
     "failure-screen 'Start in the editor', the Pattern tab, the round-trip panel and the spike "
     "page (archived at tag archive/editor-v0.3)"),
    ("photo-flow", "C6b", "old photo-flow screens: the progress and results screens with their "
     "stage meters and verdict pill, the web verdict story, the crop machine's detection paths "
     "and the synthetic sample-photo path"),
    ("dead-code", "A7", "engine dead code: resize_locked and resize_unlocked, the sprint-1 "
     "viewer package and `qrep view`, stub strategies, dead fields, after A10 has moved PRESETS "
     "and round_div into qrep/model/sizing.py"),
]

# ---------------------------------------------------------------------------
# Python symbol fate map. Ordered: first matching glob wins.
# Fates: DELETE, REBUILD (kept, rewritten), KEEP, MOVE (relocates), INPUT (the call survives
# with confirmed corners and counts), HARNESS (test oracle or fixture plumbing; does not
# decide the class). The draft inventory left bridge.presets, detect_repeat, diag:identity
# and diag:repeat_period open; this record closes them.
# ---------------------------------------------------------------------------
HOW_INPUT = ("feed confirmed corners and counts (render sidecar corners or the photoreal "
             "sidecar quad; fixture or sidecar rows and cols) instead of automatic "
             "detection; assertions and thresholds unchanged")
HOW_MOVE = ("import the symbol from qrep/model/sizing.py, where A10 moves it; A7 repoints the "
            "import when it deletes qrep/viewer/; hand-computed values unchanged")

PY_FATE_RULES: list[tuple[str, str, str, str]] = [
    ("qrep.vision.pipeline.reverse[auto]", "INPUT", "read",
     "automatic read; the confirmed read takes user corners and counts"),
    ("qrep.vision.pipeline.reverse[corners]", "REBUILD", "read",
     "corner-supplied read becomes the confirmed read"),
    ("qrep.bridge.reverse[auto]", "INPUT", "read",
     "bridge read without corners; the v2 read takes corners and counts"),
    ("qrep.bridge.reverse[corners]", "REBUILD", "bridge-v2", "bridge v2 read"),
    ("qrep.cli:reverse[auto]", "INPUT", "read", "CLI reverse without --corners"),
    ("qrep.cli:reverse[corners]", "REBUILD", "cli", "CLI reverse with corners"),
    ("qrep.cli:view", "DELETE", "dead-code", "`qrep view` (sprint-1 viewer)"),
    ("qrep.cli:*", "KEEP", "cli", "developer CLI surface"),
    ("qrep.cli*", "KEEP", "cli", "developer CLI surface"),
    ("qrep.bridge.detect_quad*", "DELETE", "detector",
     "bridge.detect_quad wraps rectify tiers 0 to 3 and GrabCut"),
    ("qrep.bridge.resize_locked*", "DELETE", "dead-code", "editing-only resize_locked"),
    ("qrep.bridge.resize_unlocked*", "DELETE", "dead-code", "editing-only resize_unlocked"),
    ("qrep.bridge.presets*", "REBUILD", "bridge-v2",
     "bridge.presets is not on the deletion list and stays"),
    ("qrep.bridge*", "REBUILD", "bridge-v2", "bridge v2 contract, expand then contract"),
    ("qrep.vision.rectify.rectify[auto]", "DELETE", "detector",
     "tiered quad detection (tiers 0 to 3, GrabCut)"),
    ("qrep.vision.rectify.rectify[corners]", "REBUILD", "read",
     "corner warp path; the confirmed read warps by user corners"),
    ("qrep.vision.rectify._*", "DELETE", "detector", "rectify tier internals"),
    ("qrep.vision.rectify.TIER3_CONFIDENCE", "DELETE", "detector", "tier-3 literal"),
    ("qrep.vision.rectify*", "REBUILD", "read", "rectify module (corner warp survives at most)"),
    ("qrep.vision.grid*", "DELETE", "detector",
     "grid estimation, guards, integer-ratio feedback (FEEDBACK_REFINE)"),
    ("qrep.vision.verdict*", "DELETE", "detector",
     "verdict tree, corroboration, T1 to T5, RESCUE_MIN_PITCH_PX, INTEGER_RATIO_EPSILON"),
    ("qrep.vision.borders*", "DELETE", "detector", "border scan"),
    ("qrep.vision.repeats.vote_cells", "REBUILD", "read",
     "repeat vote driven by the confirmed block period (HANDOFF 5)"),
    ("qrep.vision.repeats.detect_repeat", "REBUILD", "read",
     "label repeat search over the confirmed blocks; not on the deletion list"),
    ("qrep.vision.repeats*", "DELETE", "detector",
     "image periodicity, coherence probe, block-lattice SNR, sigma ladder"),
    ("qrep.vision.palette._fit_illumination", "DELETE", "detector", "palette detrend"),
    ("qrep.vision.palette.GRADIENT_*", "DELETE", "detector", "palette detrend literals"),
    ("qrep.vision.palette*", "REBUILD", "read", "palette clustering (engine reads fabrics)"),
    ("qrep.vision.cells*", "REBUILD", "read", "cell assignment (engine reads fabrics)"),
    ("qrep.vision.compare*", "HARNESS", "harness", "truth-vs-recovered oracle"),
    ("qrep.vision.metrics*", "HARNESS", "harness", "evaluation metrics"),
    ("qrep.vision.pipeline*", "REBUILD", "read", "read pipeline module"),
    ("qrep.vision", "REBUILD", "read", "vision package survives with the confirmed read"),
    ("qrep.viewer.sizing.PRESETS", "MOVE", "dead-code",
     "PRESETS moves into qrep.model before the viewer is deleted"),
    ("qrep.viewer.sizing.round_div", "MOVE", "dead-code",
     "round_div moves into qrep.model before the viewer is deleted"),
    ("qrep.viewer*", "DELETE", "dead-code",
     "sprint-1 viewer package (emit, template, locked/unlocked resize, build_view_config)"),
    ("qrep.construct.strategies:stub", "DELETE", "dead-code",
     "stub strategies fpp, epp, hand, longarm"),
    ("qrep.construct*", "REBUILD", "math", "kept and rebuilt (math rewrite, MATH.md)"),
    ("qrep.export*", "REBUILD", "math", "kept and rebuilt (pattern document, PATTERN-SPEC)"),
    ("qrep.model.finished_size*", "KEEP", "model", "finished-size reconcile and presets"),
    ("qrep.model*", "HARNESS", "harness", "model schema, io, units, fixtures"),
    ("qrep.render*", "HARNESS", "harness", "synthetic renderer (test oracle)"),
    ("qrep", "HARNESS", "harness", "package root"),
    ("fixture:wasm_gate*", "DELETE", "detector", "wasm gate ops, capture and reference"),
    ("fixture:legacy_regression*", "DELETE", "detector",
     "legacy byte pins (observed output of the tier-0 path)"),
    ("fixture:photoreal*", "HARNESS", "harness", "photoreal fixture generator"),
    ("conftest:*", "HARNESS", "harness", "golden-file protocol fixtures"),
    ("diag:identity", "DELETE", "detector",
     "tier-0 identity shortcut, deleted with the rectify tiers"),
    ("diag:repeat_period", "REBUILD", "read",
     "label repeat period, still reported by the confirmed read"),
    ("diag:repeat_vote", "REBUILD", "read", "repeat vote"),
    ("diag:detection_tier", "DELETE", "detector", "detection tier"),
    ("diag:grid_diagnosis", "DELETE", "detector", "grid guard diagnosis"),
    ("diag:verdict", "DELETE", "detector", "verdict tree output"),
    ("diag:pitch_px", "DELETE", "detector", "estimated grid pitch"),
    ("diag:border_strips", "DELETE", "detector", "border scan output"),
    ("diag:border_widths_px", "DELETE", "detector", "border scan output"),
    ("diag:periodicity", "DELETE", "detector", "image periodicity output"),
    ("diag:coherence", "DELETE", "detector", "coherence probe output"),
    ("diag:integer_ratio", "DELETE", "detector", "integer-ratio check output"),
    ("diag:block_period_cells", "DELETE", "detector", "integer-ratio block period"),
    ("diag:lattice_snr", "DELETE", "detector", "block-lattice SNR output"),
    ("diag:*", "REBUILD", "read", "read outputs that survive (dims, corners, palette, size)"),
]

DIAG_KEYS = {
    "identity", "detection_tier", "grid_diagnosis", "verdict", "detected_corners",
    "rectified_size", "pitch_px", "border_strips", "border_widths_px", "repeat_period",
    "palette_k", "interior_dims", "periodicity", "coherence", "integer_ratio",
    "block_period_cells", "lattice_snr", "repeat_vote", "size_source", "size_is_guess",
    "size_requested", "size_achieved",
}
CONFTEST_FIXTURES = {"golden", "bless_mode"}
STUB_STRATEGIES = {"fpp", "epp", "hand", "longarm"}
# Module-level names bound to importlib-loaded fixture modules (each verified to exist).
FIXTURE_LOADERS = {
    ("tests/test_legacy_regression.py", "CAP"): "fixture:legacy_regression/capture.py",
    ("tests/test_wasm_gate.py", "OPS"): "fixture:wasm_gate/ops.py",
    ("tests/test_wasm_gate.py", "CAPTURE"): "fixture:wasm_gate/capture.py",
    ("tests/test_block_lattice_s1.py", "OPS"): "fixture:wasm_gate/ops.py",
    ("tests/test_photoreal_fixtures.py", "GEN"): "fixture:photoreal/generator.py",
}

# ---------------------------------------------------------------------------
# Python overrides. Key: node id, file::function (all params), or file. cls changes the
# class; otherwise the mechanical class stands and the entry refines detail, ticket or tags.
# Every entry carries a reason (module for RETIRE, how for REEXPRESS, reason for KEEP).
# ---------------------------------------------------------------------------
PY_OVERRIDES: list[dict] = [
    # --- math pins, re-expressed by the ticket that changes the value (MATH.md section 3.2).
    #     The benchmark fixture keeps its v1 settings until A6 (see the [bless] policy).
    dict(match="tests/test_bridge.py::test_validate_happy_summary", cls=REEXPRESS, ticket="A6",
         how="when A6 regenerates the benchmark fixture at the new defaults, restate "
         "usable_width from 336 to 320 (U = 40 in, MATH.md section 3.2); keep the name, dims, "
         "census and batting 664 x 784 assertions (batting is unchanged, V-BATT-01)",
         tags=["math", "bridge-v2"]),
    dict(match="tests/test_bridge.py::test_plan_strip_carries_plan_summary_and_yardage",
         cls=REEXPRESS, ticket="A6",
         how="restate strip_set_count from 25 to 26 (V-SET-01) and usable_width from 336 to 320 "
         "when A6 regenerates the fixture; keep the batting and purpose taxonomy assertions",
         tags=["math", "bridge-v2"]),
    dict(match="tests/test_cli.py::test_plan_prints_metrics_and_writes_json", cls=REEXPRESS,
         ticket="A6",
         how="restate the 'cut operations' and 'strip sets' lines by hand for the regenerated "
         "fixture and the new cut layout (V-SET-01, V-SET-02, V-BIND-01, V-BORD-01; MATH.md "
         "section 3.2); keep 'pieces in top: 2479' (a joined border is one piece in the top) "
         "and the JSON write", tags=["math"]),
    dict(match="tests/test_construct.py::test_yardage_hand_computed_on_tiny_quilt", cls=REEXPRESS,
         ticket="A1, A2b",
         how="A1 restates the backing line to V-TOP-04 (the one-piece allowance changes its "
         "quarter yards); A2b rewrites the fabric and binding lines against the purchase lines "
         "built from strip yields plus the stated margin (V-TOP-04)", tags=["math"]),
    dict(match="tests/test_construct.py::test_subcut_counts_hand_computed_on_checker_quilt",
         cls=REEXPRESS, ticket="A2b",
         how="when A2b changes the WOF default, pin this test to an explicit wof of 336 and add a "
         "new test at the default with segments_per_set = floor(320/12) = 26, or restate it from "
         "floor(336/12) = 28 to 26 (MATH.md section 3.2); the binding strip and the cut count of "
         "13 hold", tags=["math"]),
    dict(match="tests/test_construct.py::test_fixture_strip_sets_match_design_doc", cls=REEXPRESS,
         ticket="A6",
         how="restate the counts to V-SET-01 (20 segments per set, 8 sets of SS5, 26 sets in all) "
         "and the strip sequences to merged same-fabric runs (HANDOFF 5), both by hand, when A6 "
         "moves the fixture and the exporters to the new layout", tags=["math"]),
    dict(match="tests/test_construct.py::test_fixture_strip_cut_ops_below_historical",
         cls=REEXPRESS, ticket="A6",
         how="restate both totals by hand from V-SET-01, V-SET-02, V-BIND-01 and V-BORD-01 for "
         "the new cut layout; keep 'strip below historical'", tags=["math"]),
    dict(match="tests/test_construct.py::test_fixture_backing_line", cls=REEXPRESS, ticket="A1",
         how="restate to V-BACK-09: length_needed 1568 e (unchanged), 23 quarter yards, 5 3/4 yd "
         "(the 9 in pieced-backing allowance)", tags=["math"]),
    dict(match="tests/test_exports.py::test_yardage_report_has_binding_and_backing_lines",
         cls=REEXPRESS, ticket="A1, A6",
         how="A1 restates the backing to V-BACK-09 (5 3/4 yd) and the backing name to one built "
         "from the backing width setting; A6 restates the binding to V-BIND-01 (10 strips, "
         "200 e) when it regenerates the fixture at U = 40; the purpose and quarter-yard "
         "assertions stay", tags=["math"]),
    dict(match="tests/test_svg.py::test_strip_sets_svg", cls=REEXPRESS, ticket="A6",
         how="restate the strip rectangle count by hand from the merged same-fabric runs of the "
         "new layout (HANDOFF 5; MATH.md F3) when A6 moves the exporters", tags=["math"]),
    dict(match="tests/test_exports.py::test_csv_reconciles_piece_count", cls=REEXPRESS,
         ticket="A6",
         how="when A6 moves the cut list to strips then subcuts and joined border strips "
         "(PATTERN-SPEC GAP-11, GAP-12), restate the reconciliation by hand: the CSV quantities "
         "match the plan's cut counts from V-SET-01, V-SET-02 and V-BORD-01"),
    dict(match="tests/test_construct.py::test_assembly_is_hierarchical_block_level",
         cls=REEXPRESS, ticket="A6",
         how="the historical and strip planners keep these step counts until their assembly "
         "steps change; if A6's move to the one-method pipeline changes them (binding described "
         "once and after layering, no per-row quilt assembly steps: PATTERN-SPEC GAP-08, GAP-17, "
         "GAP-21), A6 restates the 17 and 23 step counts by hand; the consecutive numbering "
         "assertion stays"),
    # --- v1 booklet structure (PATTERN-SPEC GAP-01 names these pins)
    dict(match="tests/test_pdf.py::test_sections_are_the_eight_titles_in_order", cls=REEXPRESS,
         ticket="A6",
         how="assert the PATTERN-SPEC section list in order (S1 to S11, the coloring page "
         "optional) instead of the eight v1 titles (PATTERN-SPEC GAP-01)"),
    dict(match="tests/test_pdf.py::test_cutting_rows_cover_both_fabrics_with_positive_quantities",
         cls=REEXPRESS, ticket="A6",
         how="read the cutting table under its PATTERN-SPEC title and columns (strips, then "
         "subcuts: GAP-11); keep 'both fabrics appear and every quantity is positive'"),
    dict(match="tests/test_pdf.py::test_strip_sets_table_has_at_least_five_rows", cls=REEXPRESS,
         ticket="A6",
         how="find the strip sets in the PATTERN-SPEC units section (S5.5); keep 'at least five "
         "strip sets' for the fixture while its method is strip piecing"),
    dict(match="tests/test_pdf.py::test_assembly_has_at_least_ten_numbered_steps", cls=REEXPRESS,
         ticket="A6",
         how="count numbered steps across the PATTERN-SPEC unit, block, quilt assembly, border "
         "and finishing sections; keep 'at least ten'"),
    dict(match="tests/test_pdf.py::test_fabrics_purchase_table_lists_binding_and_backing",
         cls=REEXPRESS, ticket="A6",
         how="read the purchase table in the PATTERN-SPEC fabric requirements section (S2); keep "
         "the binding and backing lines"),
    dict(match="tests/test_pdf.py::test_pdf_contains_titles_fabric_names_and_every_cut_size",
         cls=REEXPRESS, ticket="A6",
         how="check the PATTERN-SPEC headings and every cut size of the cut layout the PDF "
         "prints; keep the fabric-name check"),
    dict(match="tests/test_bridge.py::test_export_pdf_passes_pypdf_section_checks",
         cls=REEXPRESS, ticket="A6",
         how="check the PATTERN-SPEC headings through the bridge's pattern export "
         "(export_pattern, E1b) instead of the v1 export_pdf, whose eight v1 sections "
         "PATTERN-SPEC replaces (GAP-01); keep the %PDF- and fabric-name checks",
         tags=["bridge-v2"]),
    dict(match="tests/test_wasm_artifacts.py::test_wasm_booklet_passes_native_structure_checks",
         cls=REEXPRESS, ticket="A6",
         how="run the same checks as the re-expressed "
         "test_pdf_contains_titles_fabric_names_and_every_cut_size on the browser booklet; A6 "
         "runs after C6a, when the Download pattern booklet (C2a) is the only one CI checks"),
    # --- stub strategies (a string literal reaches a stub through a kept entry point)
    dict(match="tests/test_bridge.py::test_plan_stub_strategy_is_not_implemented_kind",
         cls=RETIRE, ticket="A7", module="stub strategies (fpp) via bridge.plan; engine dead code",
         reason="asserts only the not_implemented envelope of a stub strategy"),
    dict(match="tests/test_cli.py::test_plan_stub_strategy_reports_not_implemented",
         cls=RETIRE, ticket="A7", module="stub strategies (fpp) via `qrep plan`; engine dead code",
         reason="asserts only the stub's 'not implemented in v1' message"),
    dict(match="tests/test_construct.py::test_stubs_raise_not_implemented", cls=RETIRE,
         ticket="A7", module="stub strategies fpp, epp, hand, longarm (strategies.py:586-604)",
         reason="parametrized over the four stubs; asserts only NotImplementedError"),
    # --- bridge read error paths: no read happens
    dict(match="tests/test_bridge.py::test_reverse_missing_file_is_value_kind", cls=KEEP,
         reason="error path: a missing staged file is a value error before any read; holds for "
         "the v2 read", tags=["bridge-v2"]),
    dict(match="tests/test_bridge.py::test_reverse_bad_options_is_schema_kind", cls=KEEP,
         reason="error path: malformed options JSON is a schema error before any read; holds for "
         "the v2 read", tags=["bridge-v2"]),
    dict(match="tests/test_bridge.py::test_reverse_recovers_fixture_dims", ticket="B6b",
         how="when B6b removes the v1 automatic reverse, pass the L0 render sidecar corners (the "
         "outer edge), the 2.5-square border band and the fixture counts in the v2 read request "
         "(E1b defines it); keep rows 55, cols 45, non-authored provenance and the stage keys",
         reason="automatic read used to check recovered dims"),
    # --- detector tests the rule cannot settle alone
    dict(match="tests/test_corroboration_s2.py::"
         "test_t5_and_rescue_floor_not_inlined_in_pipeline_source", cls=RETIRE, ticket="B6b",
         module="corroboration gate (RESCUE_MIN_PITCH_PX, T5) in qrep/vision/pipeline.py",
         reason="reads pipeline.py as text to pin the corroboration gate literals"),
    dict(match="tests/test_grid_guards.py::test_fallback_result_is_model_safe", cls=RETIRE,
         ticket="B6b",
         module="no-grid fallback result (pipeline._fallback_result) reached through the grid "
         "estimator's no_periodicity path",
         reason="asserts the placeholder quilt that exists only for detector failures"),
    dict(match="tests/test_grid_guards.py::test_tilted_35_degree_guard_stays_silent",
         cls=RETIRE, ticket="B6b", module="grid guard (a) isotropy tolerance and T1",
         reason="interior_dims is asserted only to show the guard stayed silent"),
    dict(match="tests/test_grid_guards.py::"
         "test_perspective_mis_crop_13x43_class_is_caught_below_t1", cls=RETIRE, ticket="B6b",
         module="grid guards and T1 (grid_diagnosis, grid confidence < T1)",
         reason="user corners are only the input; the asserted catch is the grid guard. Its "
         "intent (a mis-crop is flagged) moves to the grid-fit check (B3), which brings its own "
         "tests"),
    dict(match="tests/test_repeats_verdict.py::test_l0_render_verdict_readable_with_repeat",
         cls=RETIRE, ticket="B6b", module="verdict tree (verdict == readable)",
         reason="primary assertion is the verdict; repeat_period and the vote stay pinned by "
         "tests/test_roundtrip.py and the vote unit tests"),
    dict(match="tests/test_repeats_verdict.py::"
         "test_bridge_reverse_envelope_gains_verdict_and_diagnostics", cls=RETIRE, ticket="B6b",
         module="verdict field of the bridge reverse envelope (S4 contract)",
         reason="pins the verdict-bearing envelope that the v2 read contract replaces"),
    dict(match="tests/test_repeats_verdict.py::test_label_detector_soft_vote_minimal_period",
         reason="detect_repeat is not on the deletion list, and the block-consistent vote needs "
         "the label period over the confirmed blocks: the fixture alternates two 5 x 5 block "
         "types, so its label period is 10 x 10 (qrep/model/fixtures.py:37-42)"),
    dict(match="tests/test_viewer.py::test_build_view_config_fixture", cls=RETIRE, ticket="A7",
         module="qrep.viewer.sizing.build_view_config (sprint-1 viewer)",
         reason="config for the viewer template only; the preset table it also pins stays "
         "covered by tests/test_size_engine.py::test_presets_bridge_export_verbatim. A7 "
         "retires it before A6 regenerates the fixture at the new defaults, so its stored "
         "wof of 336 never needs a restatement"),
    # --- legacy byte pins (HANDOFF 2.3) and the round-trip harness
    dict(match="tests/test_legacy_regression.py::test_legacy_path_byte_stable", cls=REEXPRESS,
         ticket="A8, B6a",
         how="A8 replaces the byte compare against the captured pins with semantic checks on the "
         "seed-42 L0 to L2 renders read with their sidecar corners: interior dims 45 x 55, 2 "
         "fabrics, and cell accuracy 1.0 at L0, at least 0.98 at L1 and at least 0.90 at L2 "
         "(criteria S7-1 to S7-3), every expected value from the hand-authored fixture and the "
         "sidecars, never re-captured (HANDOFF 2.3). The checks read neither the pins nor "
         "capture.py, so B6b can delete them. A8 lands first on night 1, because the pins store "
         "the full recovered model, settings included, which A1's new Settings fields, A2b's "
         "40 in default and B6a's native opencv 4.11 would each break. B6a then feeds the "
         "fixture counts to the confirmed read before B6b deletes the old corner path; "
         "assertions unchanged",
         reason="HANDOFF 2.3: legacy byte pins become semantic checks"),
    dict(match="tests/test_legacy_regression.py::test_pin_committed", ticket="B6b",
         module="legacy byte pin files (observed output of the tier-0 path)",
         reason="after A8 the semantic checks no longer read the pins; B6b deletes the pin files "
         "and capture.py with these tests"),
    dict(match="tests/test_roundtrip.py",
         how="feed the L0, L1 or L2 render sidecar corners and the fixture counts (9 blocks "
         "across by 11 down, 5 squares per block, one 3 3/4 in border band) to the confirmed "
         "read instead of the image path alone; keep the verbatim issue #10 thresholds",
         reason="HANDOFF 2.3: test_roundtrip keeps its L0, L1 and L2 accuracy thresholds, "
         "re-expressed with corners and counts from the hand-authored fixture"),
    dict(match="tests/test_roundtrip.py::test_l0_identity_homography_path", cls=RETIRE,
         ticket="B6b",
         module="tier-0 identity shortcut (diagnostics identity, rectify confidence 1.0 from the "
         "identity path)",
         reason="not an accuracy threshold; issue #10's identity-path clause is superseded "
         "(criterion S7-1), and L0 accuracy stays gated by "
         "test_l0_exact_dims_and_perfect_accuracy"),
    dict(match="tests/test_roundtrip.py::test_l2_spacing_accuracy_and_nonidentity",
         cls=REEXPRESS, ticket="B6a",
         how="feed the L2 sidecar corners and fixture counts; keep accuracy >= 0.90 (HANDOFF "
         "2.3); drop the self-found non-identity and the 2 percent spacing checks, because "
         "confirmed corners and counts make the warp and the pitch inputs (criterion S7-3)",
         reason="HANDOFF 2.3 keeps the L2 accuracy threshold"),
    dict(match="tests/test_roundtrip.py::test_repeat_period_exact",
         how="read L0 and L1 with sidecar corners and fixture counts; keep repeat_period == "
         "[10, 10], the label repeat of the two alternating 5 x 5 block types, which the read "
         "reports so the vote never merges different block types (criterion S7-5b)",
         reason="issue #10 contract number, kept"),
    dict(match="tests/test_roundtrip.py::test_fabric_count_recovered",
         how="read L0 and L1 with sidecar corners and fixture counts and leave the fabric count "
         "to the engine's suggestion, so the test still checks that 2 fabrics are found "
         "(criterion S7-5a)", reason="issue #10 contract number, kept"),
    dict(match="tests/test_roundtrip.py::test_border_width_within_five_percent", ticket="B6b",
         reason="border widths come only from the border scan; in the confirmed read the user "
         "pins the outer edge and sets border bands (HANDOFF 5), so the issue #10 border "
         "criterion is superseded (criterion S7-5c)"),
    dict(match="tests/test_roundtrip.py::test_l2_diagnostic_with_ground_truth_corners",
         how="becomes the report-only corner-jitter diagnostic (criterion S7-4): the L2 read with "
         "sidecar corners moved by a few pixels plus fixture counts records accuracy without "
         "gating", reason="escape-hatch diagnostic"),
    dict(match="tests/test_roundtrip.py::test_every_stage_populated_and_l2_strictly_lower",
         how="read with sidecar corners and fixture counts; STAGES keeps its six names, with "
         "user-confirmed stages recorded at 1.0; keep 'every stage in (0, 1]' and 'L2 minimum "
         "strictly below L0' (criterion S7-6)", reason="confidence on every stage"),
    dict(match="tests/test_roundtrip.py::test_reverse_cli_writes_recovered_model",
         how="pass --corners from the L0 sidecar and the counts through the new CLI options; "
         "keep rows 55, cols 45, provenance cv and the confidence output line",
         reason="CLI reverse without corners"),
    dict(match="tests/test_roundtrip.py::test_compare_cli_reconciles_with_harness",
         how="the l0 read is re-expressed (confirmed corners and counts); `qrep compare` and its "
         "reconciliation assertions are unchanged", reason="uses the re-expressed l0 read"),
    dict(match="tests/test_l3.py::test_l3_runs_to_completion_and_records_accuracy",
         how="read the L3 render with sidecar corners and fixture counts; run-to-completion "
         "assertions unchanged; stays report-only (no threshold by contract, criterion S8-2)",
         reason="same harness as test_roundtrip (HANDOFF 2.3)"),
    dict(match="tests/test_rectify_tiers.py::test_user_corners_bypass_detection",
         cls=REEXPRESS, ticket="B6a",
         how="keep IoU >= 0.99 between supplied and returned corners; drop `result.tier is None` "
         "because the tier field leaves with the tiers",
         reason="corner path survives; the asserted tier field does not"),
    dict(match="tests/test_vision_units.py::test_identity_crop_masks_background_wedges",
         cls=REEXPRESS, ticket="B6a",
         how="pass the pinched quad as confirmed corners instead of tier-0 detection; keep 'no "
         "background pixel survives the mask', or, if the new read always warps, 'no background "
         "pixel enters the warped field'",
         reason="quad-pixels-only rule (design doc) survives; the detection input does not"),
    dict(match="tests/test_vision_units.py::test_masked_palette_ignores_wedges", cls=REEXPRESS,
         ticket="B6a",
         how="pass the pinched quad as confirmed corners and leave the fabric count to the "
         "engine; keep k == 2 and the no-gray-cluster assertion",
         reason="palette must ignore background wedges; detection input goes"),
    # --- robustness (#33, #71)
    dict(match="tests/test_robustness_33.py::test_ac2_probe_identity_path_and_k2",
         cls=REEXPRESS, ticket="B6a",
         how="read the probe with its pinched quad as confirmed corners and the fixture counts, "
         "and leave the fabric count to the engine; keep #33 AC2: the engine suggests 2 fabrics "
         "(the value the Colors step starts from) and the read returns 2; drop the identity and "
         "detection_tier premise checks, which leave with the rectify tiers",
         reason="#33 AC2 is a hand-set contract number"),
    dict(match="tests/test_robustness_33.py::test_ac2_probe_palette_centers_survive_the_gradient",
         cls=RETIRE, ticket="B6b",
         module="palette detrend: its 15 Lab bound was raised from the hand-set 10 after "
         "measuring the flat-field correction (recorded on #71)",
         reason="an observed-output calibration of deleted code (verified review finding "
         "tests-11); the new read's colour accuracy is measured on labeled truth (D4, D5)"),
    dict(match="tests/test_robustness_33.py::test_lighting_fixture_fidelity_improves",
         cls=REEXPRESS, ticket="B6a",
         how="add the sidecar grid rows and cols as confirmed counts (and, where the read takes "
         "one, the sidecar's fabric count) to the sidecar corners it already passes; keep "
         "fidelity <= 10 Lab, which the new read's label-aware shading correction must meet "
         "(HANDOFF 5)", reason="hand-set S5 contract bound"),
    dict(match="tests/test_robustness_33.py::test_palette_fidelity_holds_or_improves",
         cls=RETIRE, ticket="B6b",
         module="automatic read and palette detrend: PRE_S5_FIDELITY ceilings captured once from "
         "pipeline output on pre-S5 main",
         reason="observed-output ceilings, against the one-way rule for expected values "
         "(verified review finding tests-11); the confirmed read's palette accuracy is gated on "
         "labeled truth by the corpus eval (D4, D5)"),
    dict(match="tests/test_robustness_33.py::test_ac3_border_width_within_five_percent",
         ticket="B6b",
         reason="#33 AC3 border widths come only from the border scan; bands become user-set "
         "(HANDOFF 5), so AC3 is superseded"),
    # --- size engine and viewer moves
    dict(match="tests/test_size_engine.py::test_presets_bridge_export_verbatim", ticket="A7",
         how="import PRESETS from qrep/model/sizing.py, where A10 moves it; A7 repoints this "
         "import when it deletes the qrep.viewer shim; bridge.presets() is not on the deletion "
         "list and keeps returning the table verbatim", tags=["bridge-v2"]),
    dict(match="tests/test_size_engine.py::test_reverse_options_thread_size_and_provenance",
         how="read the L0 render with sidecar corners and fixture counts; the size threading, "
         "provenance and note assertions are unchanged", reason="size options threading"),
    dict(match="tests/test_size_engine.py::test_bridge_reverse_options_json_round_trip",
         how="add sidecar corners and fixture counts to the options JSON in the v2 request shape "
         "(E1); keep the requested and achieved round trip", reason="size options threading"),
    dict(match="tests/test_size_engine.py::test_apply_finished_size_bridge_equivalence",
         how="both reads take sidecar corners and fixture counts; keep apply-equals-fresh",
         reason="apply_finished_size equivalence"),
    dict(match="tests/test_size_engine.py::test_no_new_confidence_stage",
         how="read with sidecar corners and fixture counts; keep the six-stage set (STAGES keeps "
         "its names; criterion S7-6)", reason="schema freeze guard"),
    dict(match="tests/test_viewer.py::test_round_div_half_up", ticket="A10, A7",
         how="A10 copies the test, unchanged, into tests/test_sizing.py against round_div's new "
         "home, qrep/model/sizing.py; A7 deletes tests/test_viewer.py with the original, and "
         "moves the test itself if A10 did not; its hand-computed values hold",
         reason="round_div survives the viewer"),
]

# Conditions on tests that stay (KEEP) or tags on re-expressed ones. Key: node id or
# file::function. Each names the ticket the condition binds, or "-" for none.
PY_DECLARED_TAGS: list[tuple[str, str, str, str]] = [
    ("tests/test_bridge.py::test_plan_historical_piece_count", "math", "A6",
     "2479 counts each joined border as one piece in the top; joined border strips count in cut "
     "operations, not in pieces"),
    ("tests/test_exports.py::test_csv_reconciles_piece_count", "math", "A6",
     "2479 counts 4 border pieces today"),
    ("tests/test_construct.py::test_fixture_modern_piece_count_below_historical", "math", "A6",
     "2479 counts each joined border as one piece in the top"),
    ("tests/test_construct.py::test_assembly_is_hierarchical_block_level", "math", "A6",
     "17 and 23 steps include two binding steps before layering"),
    ("tests/test_pdf.py::test_strip_sets_table_has_at_least_five_rows", "math", "A3a",
     "merged runs keep the fixture's five distinct strip sets"),
    ("tests/test_size_engine.py::test_reconcile_happy_path_hand_math", "math", "A10",
     "the reconcile math keeps its hand-computed values when A10 builds the one sizing module: "
     "apply_finished_size's new step parameter defaults to one eighth, and the 1/4 in steps of "
     "Your pattern (A10, C2b) do not change it"),
    ("tests/test_size_engine.py::test_reconcile_plan_contract_86_by_67_5_clamps", "math", "A10",
     "same as the happy-path reconcile test"),
    ("tests/test_size_engine.py::test_reconcile_with_band_hand_math", "math", "A10",
     "band 21 eighths (2 5/8 in); same as the happy-path reconcile test"),
    ("tests/test_size_engine.py::test_reconcile_lower_clamp", "math", "A10",
     "CELL_MIN stays frozen in qrep.model.finished_size, which A10 edits"),
    ("tests/test_size_engine.py::test_reconcile_width_only", "math", "A10",
     "same as the happy-path reconcile test"),
    ("tests/test_exports.py::test_format_yards", "math", "-",
     "quarter-yard formatting; MATH.md leaves the 1/4 yd increment open for Jake, and a 1/8 yd "
     "decision needs an amendment of this record"),
    ("tests/test_construct.py::test_finished_area_reconciles_exactly", "dead-fields", "A7",
     "uses ConstructionPlan.top_finished_area, test-only per the engine review; move the helper "
     "into the test if A7 removes it"),
    ("tests/test_fixture.py::test_fixture_confidences_all_default_to_one", "dead-fields", "A7",
     "uses GridRegion.effective_cell_confidence, test-only per the engine review; the rule it "
     "checks (hand-authored data is 1.0) is a CLAUDE.md non-negotiable"),
    ("tests/test_render.py::test_l0_every_cell_center_matches_palette_exactly", "dead-fields",
     "A7", "uses RenderResult.base_cell_center, test-only per the engine review"),
    ("tests/test_render.py::test_l2_sidecar_corners_consistent_with_homography", "dead-fields",
     "A7", "uses RenderResult.base_cell_center, test-only per the engine review"),
    ("tests/test_construct.py::test_metrics_carry_heuristic_label_and_zero_bias", "dead-fields",
     "A7", "the heuristic label stays on the metrics even though the PDF stops printing "
     "difficulty and time (PATTERN-SPEC GAP-04)"),
    ("tests/test_bridge.py::test_reverse_missing_file_is_value_kind", "bridge-v2", "B6b",
     "if B6b removes the v1 bridge.reverse, retarget the call to the v2 read; assertions "
     "unchanged"),
    ("tests/test_bridge.py::test_reverse_bad_options_is_schema_kind", "bridge-v2", "B6b",
     "if B6b removes the v1 bridge.reverse, retarget the call to the v2 read; assertions "
     "unchanged"),
]

# ---------------------------------------------------------------------------
# Web fate maps
# ---------------------------------------------------------------------------
# web/src files (relative to web/src): fate, note, ticket. Unlisted files: KEEP. The draft
# inventory left model/sizing.ts and shell/PalettePanel.tsx open; the plan's C6a deletes both,
# with PatternPanel.tsx and patternText.ts, after C2a and C2b replace what they rendered.
WEB_FILE_FATE: dict[str, tuple[str, str, str]] = {
    "model/seams.ts": ("DELETE", "seams tool", "C6a"),
    "model/verdictStory.ts": ("DELETE", "verdict surface, the UI of the verdict tree", "C6b"),
    "state/editor.ts": ("DELETE", "editor store: paint, undo and redo, palette edits, autosave, "
                        "project file, blank grid", "C6a"),
    "shell/SizingPanel.tsx": ("DELETE", "Sizing tab", "C6a"),
    "shell/OpenModal.tsx": ("DELETE", "open project files", "C6a"),
    "shell/PatternPanel.tsx": ("DELETE", "Pattern tab: strategy cards, yardage table, the five "
                               "downloads, copy my settings and the print sheet", "C6a"),
    "shell/PalettePanel.tsx": ("DELETE", "palette editing panel; C2a renders the census in "
                               "viewer/FabricsPanel.tsx", "C6a"),
    "state/patternText.ts": ("DELETE", "Pattern-tab value helpers and the copy-my-settings "
                             "summary", "C6a"),
    "model/sizing.ts": ("DELETE", "Sizing-tab resize mirrors and a PRESETS copy, which C2b "
                        "replaces with the bridge's presets()", "C6a"),
    "viewer/EditorToolbar.tsx": ("DELETE", "paint, seams and undo toolbar", "C6a"),
    "viewer/paintGeometry.ts": ("DELETE", "paint and seam-drag geometry", "C6a"),
    "spike/SpikePage.tsx": ("DELETE", "spike page", "C6a"),
    "spike/main.tsx": ("DELETE", "spike page", "C6a"),
    "spike/spikeWorker.ts": ("DELETE", "spike page", "C6a"),
}

# vitest files: default class, ticket and module or reason for every test in the file.
WEB_VITEST_FILE_RULES: dict[str, dict] = {
    "web/src/compose-site.test.ts": dict(cls=KEEP, reason="Pages composition and version sync"),
    "web/src/copy-audit.test.ts": dict(per_file=True, cls=KEEP,
                                       reason="loading-copy ban on UI strings"),
    "web/src/copy-audit-verdicts.test.ts": dict(per_file=True, cls=KEEP,
                                                reason="S8 entry copy pinned verbatim"),
    "web/src/golden-discipline.test.ts": dict(cls=KEEP, reason="golden discipline guards"),
    "web/src/engine/rpc.test.ts": dict(cls=KEEP, reason="engine RPC client (web shell)",
                                       tags=["bridge-v2"], tag_ticket="E1a",
                                       tag_note="boot handshake scripted here; E1a adds a "
                                       "CONTRACT_VERSION check in the worker at boot; a changed "
                                       "handshake message changes the script, not the "
                                       "assertions"),
    "web/src/model/downscale.test.ts": dict(cls=KEEP, reason="photo downscale caps (#101 may "
                                            "move the cap to the crop)"),
    "web/src/model/fraction.test.ts": dict(cls=KEEP, reason="fraction input grammar used by "
                                           "the size entry"),
    "web/src/model/seams.test.ts": dict(cls=RETIRE, ticket="C6a",
                                        module="seams tool (web/src/model/seams.ts; its strategy "
                                        "merges re-implement the engine's)"),
    "web/src/model/sizeEntry.test.ts": dict(cls=KEEP, reason="finished-size entry state "
                                            "(HANDOFF 5 keeps finished size)"),
    "web/src/model/sizing.test.ts": dict(cls=RETIRE, ticket="C6a",
                                         module="Sizing-tab resize mirrors (roundDiv, "
                                         "lockedResize, unlockedResize, previewLocked in "
                                         "web/src/model/sizing.ts)"),
    "web/src/model/units.test.ts": dict(cls=KEEP, reason="fraction display parity with "
                                        "qrep.model.units"),
    "web/src/model/verdictStory.test.ts": dict(cls=RETIRE, ticket="C6b",
                                               module="verdict surface (verdictStory; "
                                               "paletteGate for the failure-screen 'Start in "
                                               "the editor')"),
    "web/src/state/editor.test.ts": dict(cls=RETIRE, ticket="C6a",
                                         module="editor store (web/src/state/editor.ts)"),
    "web/src/state/photoFlow.test.ts": dict(cls=KEEP, reason="photo flow state machine"),
    "web/src/viewer/paintGeometry.test.ts": dict(cls=RETIRE, ticket="C6a",
                                                 module="paint and seam-drag geometry "
                                                 "(web/src/viewer/paintGeometry.ts)"),
}

# Identifiers in a photoFlow test body that exist only to consume detect_quad.
PHOTOFLOW_DETECT_HOOKS = {"detectionResolved", "detectionFailed", "resetToAuto",
                          "detectPending", "detectedQuad", "bypassToProgress"}

WEB_OVERRIDES: list[dict] = [
    dict(match="web/src/compose-site.test.ts::composed Pages artifact > keeps the legacy docs "
         "URLs alive (viewer.html, demo artifacts)", cls=KEEP,
         reason="A7 replaces docs/viewer.html with a redirect stub to the app root; the test "
         "asserts only that viewer.html and demo/booklet.pdf exist in the composed site "
         "(compose-site.test.ts:38-41), so it passes unchanged and the legacy link keeps "
         "working"),
    dict(match="web/src/compose-site.test.ts::composed Pages artifact > ships the runtime, "
         "wheels, and .nojekyll", cls=REEXPRESS, ticket="C6a",
         how="drop the spike.html assertion when the spike page is deleted; keep "
         "pyodide-lock.json, wheels/manifest.json and .nojekyll"),
    dict(match="web/src/copy-audit-verdicts.test.ts::verdict/pill consistency invariants",
         cls=RETIRE, ticket="C6b", module="verdict surface (web/src/model/verdictStory.ts)",
         reason="pure tests of verdictStory pill and panel rules"),
    dict(match="web/src/copy-audit-verdicts.test.ts::S8 entry copy present verbatim > "
         "start-screen lede honest size line", cls=REEXPRESS, ticket="C2b",
         how="C2b rewrites the start-screen lede (you confirm the corners and counts, and the "
         "pattern prints a size you chose or one labeled as a default) and restates the pinned "
         "sentence to that copy; the verbatim check stays (criterion A3-11; HANDOFF 5)"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > stage enters crop with "
         "default inset pins and detection pending", cls=REEXPRESS, ticket="C6b",
         how="drop the detectPending assertion; keep the crop state, the default pins, "
         "quadSource 'default' and sequence 1"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > detection snap-in: "
         "untouched pins adopt the detected quad", cls=RETIRE, ticket="C6b",
         module="detect_quad snap-in (no automatic corner detection on the confirm screen, "
         "criterion U3-4)"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > user wins the race: a moved "
         "pin is never overwritten by detection", cls=RETIRE, ticket="C6b",
         module="race against detect_quad (no automatic corner detection, criterion U3-4)",
         reason="if spike B1 earns a measured suggestion, C3c tests the suggestion chips on "
         "their own"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > analyze passes corners ONLY "
         "when the user moved a pin", cls=RETIRE, ticket="C6b",
         module="automatic-detection path of the crop flow (untouched pins send no corners)",
         reason="the confirmed read always sends confirmed corners (criterion U3-5); C3b sends "
         "them from confirmFlow.ts and leaves this machine path to C6b"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > results then Adjust-the-crop "
         "seeds the confirmed quad", cls=REEXPRESS, ticket="C6b",
         how="seed by moving pins instead of a detection; keep 'returns to the screen seeded with "
         "the confirmed quad'; the last step asserts that analyze re-sends the seeded quad, "
         "because confirmed corners always ride along (criterion U3-5)"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > cancel from progress returns "
         "to idle and clears the session", cls=KEEP,
         reason="cancel and clear-session behavior survives; the detectedQuad null check becomes "
         "vacuous without detection"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > a second photo starts from "
         "ITS detection, never the previous corners", cls=REEXPRESS, ticket="C6b",
         how="keep the no-leak assertions (the second photo starts from the default pins, "
         "quadSource 'default', the next sequence number); drop the detection steps (criterion "
         "U3-8)"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > Reset to auto restores the "
         "detected quad after a user move", cls=RETIRE, ticket="C6b",
         module="Reset to auto with a detected quad (no detection, criterion U3-4)",
         reason="reset to the default pins stays covered by 'Reset to auto without a detection "
         "restores the default pins'"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > Reset to auto without a "
         "detection restores the default pins", cls=KEEP,
         reason="reset to default pins survives on the confirm screen"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > sample bypass: straight to "
         "progress, no crop, default pins untouched", cls=RETIRE, ticket="C6b",
         module="sample bypass of the crop screen",
         reason="C6b removes the synthetic sample-photo path (plan 5.C decision 2); C9's "
         "committed examples go through the confirm screen like every photo (criterion U3-9)"),
    dict(match="web/src/state/photoFlow.test.ts::PhotoFlowMachine > detection failure just clears "
         "the pending flag; pins stay usable", cls=RETIRE, ticket="C6b",
         module="detect_quad failure handling (no detection, criterion U3-4)"),
]

# Playwright: e2e surfaces (test ids and markers) and their fates, first match wins. The
# draft inventory left the demo, sample, ruler, download, strategy, yardage, copy and print
# surfaces open; this record closes them.
E2E_SURFACE_RULES: list[tuple[str, str, str]] = [
    ("engine-chip", "HARNESS", "readiness wait"),
    ("toast", "HARNESS", "generic toast"),
    ("engine-retry", "KEEP", "web shell"),
    ("theme-toggle", "KEEP", "web shell"),
    ("url:spike.html", "DELETE", "spike page"),
    ("editor", "DELETE", "editor view container"),
    ("mode-paint", "DELETE", "paint"), ("mode-move", "DELETE", "paint"),
    ("mode-seams", "DELETE", "seams tool"), ("hand-tweaked", "DELETE", "seams tool"),
    ("swatch-*", "DELETE", "paint"), ("undo", "DELETE", "undo and redo"),
    ("redo", "DELETE", "undo and redo"), ("key:undo-redo", "DELETE", "undo and redo"),
    ("fabric-rename-*", "DELETE", "palette editing"),
    ("fabric-color-*", "DELETE", "palette editing"),
    ("delete-fabric-*", "DELETE", "palette editing"), ("add-fabric", "DELETE", "palette editing"),
    ("fabric-row-*", "DELETE", "palette editing rows"),
    ("save-project", "DELETE", "save project files"),
    ("open-project", "DELETE", "open project files"),
    ("open-modal", "DELETE", "open project files"),
    ("open-file-input", "DELETE", "open project files"),
    ("start-blank", "DELETE", "blank-grid start"),
    ("resume-banner", "DELETE", "autosave and resume"),
    ("resume-accept", "DELETE", "autosave and resume"),
    ("autosave-error", "DELETE", "autosave and resume"),
    ("roundtrip-*", "DELETE", "round-trip panel"),
    ("failure-start-editor", "DELETE", "failure-screen 'Start in the editor'"),
    ("open-in-editor", "DELETE", "editor entry from results"),
    ("tab:Sizing", "DELETE", "Sizing tab"), ("equation-box", "DELETE", "Sizing tab"),
    ("sizing-panel", "DELETE", "Sizing tab"), ("size-cell*", "DELETE", "Sizing tab"),
    ("size-preset", "DELETE", "Sizing tab"), ("proportion-lock", "DELETE", "Sizing tab"),
    ("border-*", "DELETE", "Sizing tab"), ("blocks-line", "DELETE", "Sizing tab"),
    ("size-asked", "DELETE", "Sizing tab"), ("size-got", "DELETE", "Sizing tab"),
    ("crop-detecting", "DELETE", "detect_quad snap-in"),
    ("attr:data-verdict", "DELETE", "verdict surface"),
    ("failure-panel", "DELETE", "verdict surface"),
    ("failure-adjust-crop", "DELETE", "verdict surface"),
    ("verdict-disclosure*", "DELETE", "verdict surface"),
    ("wrong-banner", "DELETE", "verdict surface"),
    ("overall-pill", "DELETE", "verdict surface"),
    ("confidence-*", "DELETE", "automatic stage meters"),
    ("crop-analyze", "INPUT", "analyze from the crop screen (untouched pins = automatic "
     "detection); the confirm screen sends corners and counts"),
    ("open-demo", "DELETE", "demo entry into the editor, removed with it"),
    ("photo-sample", "DELETE", "sample bypass; examples replace the sample (C9)"),
    ("ruler-*", "REBUILD", "canvas rulers stay wherever Your pattern shows the quilt"),
    ("download-pdf", "REBUILD", "single pattern download"),
    ("download-*", "DELETE", "per-format downloads leave with the Pattern tab"),
    ("strategy-card-*", "DELETE", "strategy picker (one method, HANDOFF 5)"),
    ("yardage-*", "DELETE", "UI yardage table (yardage lives in the PDF)"),
    ("copy-settings", "DELETE", "copy my settings (not on Your pattern)"),
    ("print-*", "DELETE", "print sheet (one PDF download)"),
    ("tab:Pattern", "REBUILD", "pattern exports"), ("pattern-panel", "REBUILD", "pattern exports"),
    ("quilt-canvas", "REBUILD", "quilt render"), ("fabric-count-*", "REBUILD", "fabric census"),
    ("open-lightbox", "REBUILD", "photo compare (#97)"),
    ("uncertain-toggle", "REBUILD", "uncertain squares"),
    ("*", "REBUILD", "photo flow, size entry (confirmed-read UI)"),
]

# Every Playwright test is decided explicitly (48 rows): class, ticket and detail. A row that
# names C3b covers only how the test reaches the read on the confirm screen (pins and counts);
# C3c lands the read on Your pattern. The idle vision prefetch stays (PARITY item 17; plan
# section 5.C, decision 4), so C8b executes no entry here.
E2E_DECISIONS: dict[tuple[str, str], dict] = {
    ("web/e2e/app.spec.ts", "demo quilt renders true to scale with correct rulers"): dict(
        cls=REEXPRESS, ticket="C2a",
        how="open the hand-authored fixture from See a sample pattern and reach the quilt canvas "
        "on Your pattern instead of open-demo and the editor; keep the title, the 600 x 720 "
        "finished-size attributes and the 75 in and 90 in ruler ends (rulers stay binding "
        "wherever Your pattern shows the quilt)"),
    ("web/e2e/app.spec.ts", "engine chip reaches ready on a healthy load"): dict(
        cls=KEEP, reason="web shell engine chip"),
    ("web/e2e/app.spec.ts", "killing the network surfaces retry and recovery works"): dict(
        cls=KEEP, reason="web shell boot failure and retry"),
    ("web/e2e/app.spec.ts", "uploading a valid project JSON renders it"): dict(
        cls=RETIRE, ticket="C6a", module="open project files (open-project, OpenModal)"),
    ("web/e2e/app.spec.ts", "corrupted JSON shows the error envelope message, not a "
     "traceback"): dict(
        cls=RETIRE, ticket="C6a", module="open project files (open-project, OpenModal)",
        reason="the no-traceback property stays covered engine-side by the tests/test_bridge.py "
        "error envelope helper (test_bridge.py:54-60), which every bridge error test calls"),
    ("web/e2e/app.spec.ts", "fabric summary counts match the fixture census via bridge "
     "data"): dict(
        cls=REEXPRESS, ticket="C2a",
        how="reach the fabric census on Your pattern from See a sample pattern instead of "
        "open-demo and the editor; keep the 1246 and 1229 literals"),
    ("web/e2e/app.spec.ts", "the editor is interactive before the engine finishes booting"):
        dict(cls=REEXPRESS, ticket="C6a",
             how="when C6a deletes the editor and the old demo entry, stall the Pyodide wasm "
             "as the test does and show that the start screen and its photo entry render and "
             "respond while the chip says booting, instead of opening the demo into the "
             "editor; keep the booting-chip and no download or install wording checks "
             "(criterion W7: the shell is interactive at once)"),
    ("web/e2e/app.spec.ts", "theme toggle persists across reload"): dict(
        cls=KEEP, reason="web shell theme toggle"),
    ("web/e2e/crop.spec.ts", "crop screen: pins immediately, quad snaps in, analyze reaches "
     "results, adjust returns seeded"): dict(
        cls=REEXPRESS, ticket="C3b, C3c",
        how="C3b drops the detect_quad snap-in step (crop-detecting and the pin-top check after "
        "detection) and places the four pins by hand on the screenshot fixture's sidecar quad; "
        "C3c lands the read on Your pattern and returns through its Adjust corners and counts; "
        "keep 'pins render immediately' and 'adjust returns seeded with the confirmed quad'"),
    ("web/e2e/crop.spec.ts", "sample photo bypasses the crop screen entirely"): dict(
        cls=RETIRE, ticket="C6b", module="sample bypass of the crop screen",
        reason="C6b removes the synthetic sample-photo path (plan 5.C decision 2); C9's "
        "committed examples go through the confirm screen like every photo (criterion U3-9) and "
        "bring their own tests"),
    ("web/e2e/editing.spec.ts", "paint with census verification, drag line walk, undo and "
     "redo"): dict(cls=RETIRE, ticket="C6a", module="paint and undo/redo"),
    ("web/e2e/editing.spec.ts", "undo depth of at least 50"): dict(
        cls=RETIRE, ticket="C6a", module="undo and redo"),
    ("web/e2e/editing.spec.ts", "palette add, rename, recolor; deleting an in-use fabric is "
     "blocked"): dict(cls=RETIRE, ticket="C6a", module="palette editing"),
    ("web/e2e/editing.spec.ts", "save-to-file round trip is byte-identical on the canonical "
     "model"): dict(cls=RETIRE, ticket="C6a", module="save and open project files"),
    ("web/e2e/editing.spec.ts", "autosave restores after reload with its age shown"): dict(
        cls=RETIRE, ticket="C6a", module="autosave and resume"),
    ("web/e2e/editing.spec.ts", "beforeunload guards only when edits are newer than the last "
     "save"): dict(cls=RETIRE, ticket="C6a", module="dirty tracking for save and autosave"),
    ("web/e2e/editing.spec.ts", "a foreign schema_version autosave is rejected with a clear "
     "message"): dict(cls=RETIRE, ticket="C6a", module="autosave and resume"),
    ("web/e2e/editing.spec.ts", "start from a blank grid (PARITY item 15)"): dict(
        cls=RETIRE, ticket="C6a", module="blank-grid start"),
    ("web/e2e/exports.spec.ts", "strip cut-list CSV and MD downloads byte-equal the canonical "
     "goldens"): dict(
        cls=RETIRE, ticket="C6a", module="per-format downloads on the Pattern tab",
        reason="one Download pattern (PDF) button replaces them (HANDOFF 5); golden byte checks "
        "stay in tests/test_exports.py and tests/test_bridge.py, and the pyodide-tests job "
        "proves browser byte parity (criterion W11)"),
    ("web/e2e/exports.spec.ts", "SVG downloads byte-equal the frozen golden and parse "
     "sanely"): dict(
        cls=RETIRE, ticket="C6a", module="per-format SVG download on the Pattern tab",
        reason="tests/test_svg.py and tests/test_bridge.py keep the golden byte checks; the "
        "pyodide-tests job proves browser byte parity (criterion W11)"),
    ("web/e2e/exports.spec.ts", "exports are deterministic within a session; PDF saved for "
     "pypdf"): dict(
        cls=REEXPRESS, ticket="C2a",
        how="open See a sample pattern and download the pattern PDF twice with Your pattern's "
        "Download pattern (PDF) button: identical bytes that start with %PDF-; save "
        "web/test-results/downloads/booklet.pdf for the CI pypdf step (ci.yml:89-92 at the "
        "recorded commit); the CSV, SVG and yardage-report parts leave with those downloads, "
        "whose bytes the golden tests keep pinned"),
    ("web/e2e/exports.spec.ts", "strategy cards show bridge metrics field-for-field"): dict(
        cls=RETIRE, ticket="C6a", module="strategy cards on the Pattern tab",
        reason="one method chosen by the engine, with its reason on Your pattern (HANDOFF 5); "
        "its 25 strip sets change only in A6, which lands after C6a", tags=["math"]),
    ("web/e2e/exports.spec.ts", "yardage table: binding, backing 5 1/2 yd, batting row, engine "
     "usable width"): dict(
        cls=REEXPRESS, ticket="A1, C2b",
        how="A1 restates the backing row to V-BACK-09 (23 quarter yards, 5 3/4). C2b moves the "
        "test onto Your pattern's shopping lines, all from the engine summary: the binding line "
        "as the summary gives it ((9) strips while the fixture stores 42 in, V-BIND-09; (10) "
        "after A6, V-BIND-01), backing 5 3/4 yd (V-BACK-09), batting 83 x 98 in (V-BATT-01), "
        "both widths named, 40 in for cutting and 42 in for backing (MATH.md D-16), and a "
        "positive amount on every fabric line", tags=["math"]),
    ("web/e2e/exports.spec.ts", "seams: tweak shows badge and estimates; strategy switch "
     "resets; exports unaffected"): dict(
        cls=RETIRE, ticket="C6a", module="seams tool (mode-seams, hand-tweaked badge)"),
    ("web/e2e/exports.spec.ts", "copy-my-settings writes the clipboard summary"): dict(
        cls=RETIRE, ticket="C6a", module="copy my settings on the Pattern tab",
        reason="not on the Your pattern screen (HANDOFF 5: one Download pattern button)"),
    ("web/e2e/exports.spec.ts", "print one-page plan populates the print sheet and calls "
     "print"): dict(
        cls=RETIRE, ticket="C6a", module="print sheet on the Pattern tab",
        reason="one Download pattern (PDF) action and no print sheet (HANDOFF 5)"),
    ("web/e2e/photo.spec.ts", "L0 photo reverses in-browser to 45x55 with the palette mapped"):
        dict(cls=REEXPRESS, ticket="C3b, C3c",
             how="C3b places the pins on the L0 sidecar corners instead of clicking through with "
             "untouched pins; C3c confirms the outer edge, the 2.5-square band and counts of "
             "9 x 5 across by 11 x 5 down, and asserts 45 x 55 squares and the census 1246 and "
             "1229 on Your pattern (criterion W30); the stage-meter, overall-pill and "
             "open-in-editor steps leave with the automatic stages and the editor"),
    ("web/e2e/photo.spec.ts", "editor and export flows never need opencv"): dict(
        cls=REEXPRESS, ticket="C2a",
        how="abort every OpenCV fetch, open See a sample pattern, and check the census (1246) "
        "and the pattern PDF download on Your pattern with no error toast, instead of the "
        "editor, the Pattern tab and the CSV download (criterion W8)"),
    ("web/e2e/photo.spec.ts", "idle prefetch: post-prefetch reverse shows no loading bar "
     "(PARITY 17)"): dict(
        cls=REEXPRESS, ticket="C3b, C3c",
        how="traverse the confirm screen with corners and counts (C3b) and land on Your pattern "
        "(C3c) instead of clicking through the crop screen to the results screen; keep the "
        "wait for the idle prefetch and the no-loading-bar assertion (criterion P24)"),
    ("web/e2e/photo.spec.ts", "pre-prefetch reverse shows the staged loading bar with the "
     "measured size"): dict(
        cls=REEXPRESS, ticket="C3b, C3c",
        how="traverse the confirm screen (C3b) and land on Your pattern (C3c); keep the "
        "loading-bar and retry assertions for a read that starts before the prefetch "
        "finishes (criterion P24)"),
    ("web/e2e/photo.spec.ts", "vision loading copy is loading, sized, and cached on repeat"):
        dict(cls=REEXPRESS, ticket="C3b, C3c",
             how="traverse the confirm screen (C3b) and land on Your pattern (C3c), reading the "
             "copy on C3c's progress line instead of the old progress screen; keep the "
             "'Loading the vision engine' copy, the measured size and the no-download wording"),
    ("web/e2e/photo.spec.ts", "cancel returns to the dropzone and the engine reboots safely"):
        dict(cls=REEXPRESS, ticket="C3b, C3c",
             how="traverse the confirm screen (C3b) and cancel from C3c's one progress line; keep "
             "cancel-to-dropzone and the engine reboot (criterion U3-7)"),
    ("web/e2e/photo.spec.ts", "corner adjust re-runs reverse with user corners"): dict(
        cls=REEXPRESS, ticket="C3b, C3c",
        how="C3b keeps adjust, the pin nudge and the re-run on the confirm screen; C3c reopens "
        "Confirm from Your pattern's Adjust corners and counts and checks that Your pattern "
        "updates after the new read, which replaces the confidence-grid stage meter (criterion "
        "U3-1)"),
    ("web/e2e/photo.spec.ts", "round-trip demo panel renders, reverses, and compares"): dict(
        cls=RETIRE, ticket="C6a", module="round-trip panel (RoundTripPanel)"),
    ("web/e2e/photo.spec.ts", "the photo bitmap is session-only (PARITY 7)"): dict(
        cls=RETIRE, ticket="C6a", module="autosave and resume (resume-accept) plus the editor "
        "entry (open-in-editor)", reason="proves the photo is not restored by autosave resume; "
        "with autosave deleted nothing persists across a reload, and C2a re-asserts the "
        "property with a network and storage check (criterion P19)",
        prior="C3c starts it from the synthetic sample photo, which still reaches the old "
        "results screen and its Open in the editor action until C6a, because C3c sends every "
        "other photo read to Your pattern; assertions unchanged"),
    ("web/e2e/size.spec.ts", "86 x 67.5 entered at crop flows to achieved size, asked-vs-got, "
     "and the editor"): dict(
        cls=REEXPRESS, ticket="C2b",
        how="enter 86 x 67.5 as a target size on Your pattern's size control for the sample "
        "pattern instead of at the crop screen, and restate the achieved size by hand in a "
        "comment from A10's square-size list and tie rule (it was 56 3/8 x 67 5/8 at the "
        "one-eighth step); keep the asked-vs-got assertions; the editor Sizing-tab tail "
        "(equation-box) leaves, because C6a deletes the Sizing tab", tags=["math"],
        tag_ticket="A10", tag_note="the achieved size follows A10's square-size rule"),
    ("web/e2e/size.spec.ts", "inline size edit from results sticks without a re-run"): dict(
        cls=REEXPRESS, ticket="C2b",
        how="edit the size on Your pattern for the sample pattern instead of the results screen; "
        "keep 'applies with no re-read and no progress screen' (criterion U3-15); the 'our "
        "guess' wording follows HANDOFF 5 (never a guess printed as fact)"),
    ("web/e2e/size.spec.ts", "size block renders usable at phone width"): dict(
        cls=REEXPRESS, ticket="C2b",
        how="assert that Your pattern's size control is usable at 400 px"),
    ("web/e2e/sizing.spec.ts", "locked preset commit adopts bridge numbers exactly"): dict(
        cls=RETIRE, ticket="C6a", module="Sizing tab (resize_locked)"),
    ("web/e2e/sizing.spec.ts", "locked typed width commit: asked 75 1/2, got 75"): dict(
        cls=RETIRE, ticket="C6a", module="Sizing tab (resize_locked)"),
    ("web/e2e/sizing.spec.ts", "unlocked resize moves whole blocks with asked-vs-got shown"):
        dict(cls=RETIRE, ticket="C6a", module="Sizing tab (resize_unlocked)"),
    ("web/e2e/sizing.spec.ts", "border width change re-renders extents from the bridge "
     "model"): dict(cls=RETIRE, ticket="C6a", module="Sizing tab border editing"),
    ("web/e2e/sizing.spec.ts", "border add inserts innermost at 2in default; remove restores"):
        dict(cls=RETIRE, ticket="C6a", module="Sizing tab border editing"),
    ("web/e2e/sizing.spec.ts", "cell stepper moves 1/4in locked and commits through the "
     "bridge"): dict(cls=RETIRE, ticket="C6a", module="Sizing tab (resize_locked)"),
    ("web/e2e/sizing.spec.ts", "invalid fraction input restores the prior value with a toast"):
        dict(cls=RETIRE, ticket="C6a", module="Sizing tab inputs"),
    ("web/e2e/sizing.spec.ts", "equation box and blocks line render engine numbers"): dict(
        cls=RETIRE, ticket="C6a", module="Sizing tab"),
    ("web/e2e/spike.spec.ts", "S0 spike: closure, cut-list golden, booklet PDF, reverse, MEMFS "
     "staging"): dict(
        cls=RETIRE, ticket="C6a", module="spike page (web/spike.html, web/src/spike/)",
        reason="its booklet feeds the CI pypdf steps at ci.yml:85-88 and :184-187; C6a drops "
        "the first and points the second at the Download pattern booklet, and the downloads "
        "booklet step (ci.yml:89-92) stays"),
    ("web/e2e/verdicts.spec.ts", "no_grid: failure panel, collapsed disclosure, banner on "
     "expand, plain blank escape"): dict(
        cls=RETIRE, ticket="C3c", module="verdict surface (failure panel, disclosure, wrong "
        "banner) and the failure-screen 'Start in the editor'",
        reason="C3c sends every photo read to Your pattern and no v2 read returns a verdict, so "
        "after C3c no read reaches the failure panel; C6b deletes the verdict UI code",
        prior="C3b moves its traversal onto the confirm screen (the default pins and counts for "
        "the solid photo) where its screen changes the path; assertions unchanged"),
}

# Former UNSURE rows and other rows whose class changed when the record closed. Key: node id
# or file::function; value: the class the draft inventory gave it.
CLOSED_FROM: dict[str, str] = {
    "tests/test_bridge.py::test_validate_happy_summary": UNSURE,
    "tests/test_bridge.py::test_plan_strip_carries_plan_summary_and_yardage": UNSURE,
    "tests/test_cli.py::test_plan_prints_metrics_and_writes_json": UNSURE,
    "tests/test_construct.py::test_yardage_hand_computed_on_tiny_quilt": UNSURE,
    "tests/test_construct.py::test_subcut_counts_hand_computed_on_checker_quilt": UNSURE,
    "tests/test_construct.py::test_fixture_strip_sets_match_design_doc": UNSURE,
    "tests/test_construct.py::test_fixture_strip_cut_ops_below_historical": UNSURE,
    "tests/test_construct.py::test_fixture_backing_line": UNSURE,
    "tests/test_exports.py::test_yardage_report_has_binding_and_backing_lines": UNSURE,
    "tests/test_repeats_verdict.py::test_label_detector_soft_vote_minimal_period": UNSURE,
    "tests/test_robustness_33.py::test_ac2_probe_identity_path_and_k2": UNSURE,
    "tests/test_robustness_33.py::test_ac2_probe_palette_centers_survive_the_gradient": UNSURE,
    "tests/test_robustness_33.py::test_lighting_fixture_fidelity_improves": UNSURE,
    "tests/test_roundtrip.py::test_l0_identity_homography_path": UNSURE,
    "tests/test_roundtrip.py::test_repeat_period_exact": UNSURE,
    "tests/test_size_engine.py::test_presets_bridge_export_verbatim": UNSURE,
    "tests/test_svg.py::test_strip_sets_svg": UNSURE,
    "web/src/compose-site.test.ts::composed Pages artifact > keeps the legacy docs URLs alive "
    "(viewer.html, demo artifacts)": UNSURE,
    "web/src/copy-audit-verdicts.test.ts::verdict-copy audit: banned phrasing > model/sizing.ts":
        UNSURE,
    "web/src/copy-audit-verdicts.test.ts::verdict-copy audit: banned phrasing > "
    "shell/PalettePanel.tsx": UNSURE,
    "web/src/copy-audit-verdicts.test.ts::S8 entry copy present verbatim > start-screen lede "
    "honest size line": UNSURE,
    "web/src/copy-audit.test.ts::loading-copy audit > model/sizing.ts": UNSURE,
    "web/src/copy-audit.test.ts::loading-copy audit > shell/PalettePanel.tsx": UNSURE,
    "web/src/state/photoFlow.test.ts::PhotoFlowMachine > stage enters crop with default inset "
    "pins and detection pending": UNSURE,
    "web/src/state/photoFlow.test.ts::PhotoFlowMachine > detection snap-in: untouched pins "
    "adopt the detected quad": UNSURE,
    "web/src/state/photoFlow.test.ts::PhotoFlowMachine > user wins the race: a moved pin is "
    "never overwritten by detection": UNSURE,
    "web/src/state/photoFlow.test.ts::PhotoFlowMachine > results then Adjust-the-crop seeds the "
    "confirmed quad": UNSURE,
    "web/src/state/photoFlow.test.ts::PhotoFlowMachine > a second photo starts from ITS "
    "detection, never the previous corners": UNSURE,
    "web/src/state/photoFlow.test.ts::PhotoFlowMachine > Reset to auto restores the detected "
    "quad after a user move": UNSURE,
    "web/src/state/photoFlow.test.ts::PhotoFlowMachine > sample bypass: straight to progress, "
    "no crop, default pins untouched": UNSURE,
    "web/src/state/photoFlow.test.ts::PhotoFlowMachine > detection failure just clears the "
    "pending flag; pins stay usable": UNSURE,
    "web/e2e/app.spec.ts::demo quilt renders true to scale with correct rulers": UNSURE,
    "web/e2e/app.spec.ts::the editor is interactive before the engine finishes booting": UNSURE,
    "web/e2e/crop.spec.ts::sample photo bypasses the crop screen entirely": UNSURE,
    "web/e2e/exports.spec.ts::strip cut-list CSV and MD downloads byte-equal the canonical "
    "goldens": UNSURE,
    "web/e2e/exports.spec.ts::SVG downloads byte-equal the frozen golden and parse sanely":
        UNSURE,
    "web/e2e/exports.spec.ts::strategy cards show bridge metrics field-for-field": UNSURE,
    "web/e2e/exports.spec.ts::yardage table: binding, backing 5 1/2 yd, batting row, engine "
    "usable width": UNSURE,
    "web/e2e/exports.spec.ts::copy-my-settings writes the clipboard summary": UNSURE,
    "web/e2e/exports.spec.ts::print one-page plan populates the print sheet and calls print":
        UNSURE,
    "web/e2e/photo.spec.ts::editor and export flows never need opencv": UNSURE,
    # reclassified from the draft inventory on review
    "tests/test_robustness_33.py::test_palette_fidelity_holds_or_improves": REEXPRESS,
    "tests/test_pdf.py::test_sections_are_the_eight_titles_in_order": KEEP,
    "tests/test_pdf.py::test_cutting_rows_cover_both_fabrics_with_positive_quantities": KEEP,
    "tests/test_pdf.py::test_strip_sets_table_has_at_least_five_rows": KEEP,
    "tests/test_pdf.py::test_assembly_has_at_least_ten_numbered_steps": KEEP,
    "tests/test_pdf.py::test_fabrics_purchase_table_lists_binding_and_backing": KEEP,
    "tests/test_pdf.py::test_pdf_contains_titles_fabric_names_and_every_cut_size": KEEP,
    "tests/test_bridge.py::test_export_pdf_passes_pypdf_section_checks": KEEP,
    "tests/test_wasm_artifacts.py::test_wasm_booklet_passes_native_structure_checks": KEEP,
    "tests/test_construct.py::test_assembly_is_hierarchical_block_level": KEEP,
    "tests/test_exports.py::test_csv_reconciles_piece_count": KEEP,
}

# ---------------------------------------------------------------------------
# Support files and CI steps tied to retired tests (not test nodes)
# ---------------------------------------------------------------------------
SUPPORT_FILES = [
    ("tests/fixtures/legacy_regression/capture.py", "legacy pin capture script", "B6b"),
    ("tests/fixtures/legacy_regression/l0_seed42.json", "legacy byte pin (observed output)",
     "B6b"),
    ("tests/fixtures/legacy_regression/l1_seed42.json", "legacy byte pin (observed output)",
     "B6b"),
    ("tests/fixtures/legacy_regression/l2_seed42.json", "legacy byte pin (observed output)",
     "B6b"),
    ("tests/fixtures/wasm_gate/capture.py", "wasm gate reference capture", "B6b"),
    ("tests/fixtures/wasm_gate/ops.py", "wasm gate ops (a copy of the block-lattice SNR)", "B6b"),
    ("tests/fixtures/wasm_gate/reference.json", "wasm gate native reference", "B6b"),
    ("tests/fixtures/wasm_gate/render_on_wood_1400_fg.png", "wasm gate GrabCut mask", "B6b"),
    ("tests/fixtures/wasm_gate/render_on_wood_2000_fg.png", "wasm gate GrabCut mask", "B6b"),
    ("tests/fixtures/wasm_gate/screenshot_composite_1400_fg.png", "wasm gate GrabCut mask",
     "B6b"),
    ("web/scripts/wasm-gate-perf.mjs", "wasm gate perf script (not a test)", "B6b"),
    ("scripts/local_photo_smoke.py", "detector smoke run on gitignored local photos (not a "
     "test)", "B6b"),
    ("scripts/photoreal_baseline.py", "detector baseline script (not a test)", "B6b"),
    ("scripts/sprint4_baseline.py", "detector baseline script (not a test)", "B6b"),
    ("web/spike.html", "spike page entry", "C6a"),
    ("web/src/spike/spike_check.py", "Python check run inside the spike page (not collected)",
     "C6a"),
    ("docs/viewer.html", "sprint-1 viewer page; A7 replaces it with a redirect stub to the app "
     "root, so the published URL keeps working", "A7"),
]
CI_NOTES = [
    ("ci.yml:85-88 runs tests/test_wasm_artifacts.py on web/test-results/spike/booklet.pdf "
     "(from spike.spec.ts); C6a drops it with the spike page", "C6a"),
    ("ci.yml:184-187 (the live-spike job, in pages.yml once #105 lands) reads the same spike "
     "booklet; C6a points its pypdf check at web/test-results/downloads/booklet.pdf", "C6a"),
    ("ci.yml:89-92 runs tests/test_wasm_artifacts.py on web/test-results/downloads/booklet.pdf "
     "(from exports.spec.ts); it stays and reads the Download pattern booklet that C2a's "
     "re-expressed spec saves", "C2a"),
    ("web/vite.config.ts:15-20 builds spike.html as a second page; it goes with the spike page",
     "C6a"),
    ("web/scripts/pytest-pyodide.mjs:62-67 runs pytest on the same tests/ directory under "
     "Pyodide, so it has no separate node ids; platform skips: test_legacy_regression.py:33-36 "
     "and test_bridge.py:112-116 skip on emscripten, test_wasm_artifacts.py:28-31 skips "
     "without QREP_WASM_PDF. A8 drops the test_legacy_regression.py skip unless its semantic "
     "checks fail under Pyodide (criterion W14)", "A8"),
]

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


class Refusal(Exception):
    """The record cannot be generated at the recorded commit (exit 2)."""


def run(cmd: list[str], cwd: Path, env: dict | None = None) -> str:
    out = subprocess.run(cmd, cwd=str(cwd), env=env, capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise Refusal(f"command failed ({out.returncode}): {' '.join(cmd)}\n{out.stderr}")
    return out.stdout


def tree_files(repo: Path, *paths: str) -> list[str]:
    """Files under paths at the recorded commit (independent of the index)."""
    text = run(["git", "ls-tree", "-r", "--name-only", RECORDED_COMMIT, "--", *paths], repo)
    return sorted(line.strip() for line in text.splitlines() if line.strip())


def verify_inputs(repo: Path) -> None:
    run(["git", "cat-file", "-e", RECORDED_COMMIT + "^{commit}"], repo)
    diff = subprocess.run(["git", "diff", "--quiet", RECORDED_COMMIT, "--", *INPUT_PATHS],
                          cwd=str(repo), capture_output=True)
    untracked = run(["git", "ls-files", "--others", "--exclude-standard", "--", *INPUT_PATHS],
                    repo).strip()
    if diff.returncode != 0 or untracked:
        raise Refusal(
            f"{repo} differs from the recorded commit {RECORDED_COMMIT[:7]} in "
            f"{', '.join(INPUT_PATHS)}; the record describes that commit only. Check it out "
            f"elsewhere and pass it with --repo:\n"
            f"  git worktree add --detach ../qrep-rebaseline {RECORDED_COMMIT}\n"
            f"  python scripts/rebaseline_inventory.py --check --repo ../qrep-rebaseline")


def glob_match(sym: str, pattern: str) -> bool:
    """Only '*' is special (brackets in patterns such as reverse[auto] are literal)."""
    regex = "^" + re.escape(pattern).replace(r"\*", ".*") + "$"
    return re.match(regex, sym) is not None


def fate_lookup(sym: str, rules) -> tuple:
    for rule in rules:
        if glob_match(sym, rule[0]):
            return rule
    return (sym, "KEEP", "unmapped", "not in the fate map")


def mechanical_class(fates: list[str]) -> str:
    subject = [f for f in fates if f != "HARNESS"]
    if not subject:
        return KEEP
    kinds = set(subject)
    if kinds == {"DELETE"}:
        return RETIRE
    if "DELETE" in kinds and kinds - {"DELETE"} <= {"INPUT"}:
        return RETIRE  # automatic read used only to reach detector outputs
    if "DELETE" in kinds or "OPEN" in kinds:
        return MIXED
    if "INPUT" in kinds or "MOVE" in kinds:
        return REEXPRESS
    return KEEP


def split_tickets(ticket: str) -> list[str]:
    return [t.strip() for t in ticket.split(",") if t.strip() and t.strip() != "-"]


def md_escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def code(text: str) -> str:
    """Inline code for a test id; table() escapes pipes afterwards."""
    return f"`` {text} ``" if "`" in text else f"`{text}`"


DETAIL_KEYS = {KEEP: ("reason",), RETIRE: ("module", "reason", "prior"),
               REEXPRESS: ("how", "reason")}


def filter_detail(cls: str, detail: dict) -> dict:
    return {k: v for k, v in detail.items() if k in DETAIL_KEYS[cls]}


# ---------------------------------------------------------------------------
# Python analysis
# ---------------------------------------------------------------------------


def module_name_for(rel: str) -> str:
    parts = list(Path(rel).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def build_qrep_index(repo: Path) -> tuple[dict[str, set[str]], dict[str, str]]:
    """Top-level names per qrep module, and re-export map from package __init__ files."""
    names: dict[str, set[str]] = {}
    reexports: dict[str, str] = {}
    for rel in tree_files(repo, "qrep"):
        if not rel.endswith(".py"):
            continue
        mod = module_name_for(rel)
        tree = ast.parse((repo / rel).read_text(encoding="utf-8"))
        top: set[str] = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                top.add(node.name)
            elif isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        top.add(t.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                top.add(node.target.id)
            elif isinstance(node, ast.ImportFrom) and node.module and rel.endswith("__init__.py"):
                for a in node.names:
                    reexports[f"{mod}.{a.asname or a.name}"] = f"{node.module}.{a.name}"
        names[mod] = top
    return names, reexports


def canonical(sym: str, reexports: dict[str, str]) -> str:
    seen = set()
    while True:
        base, marker = sym, ""
        m = re.match(r"^(.*?)(\[.*\])?$", sym)
        if m:
            base, marker = m.group(1), m.group(2) or ""
        hit = None
        parts = base.split(".")
        for k in range(len(parts), 0, -1):
            prefix = ".".join(parts[:k])
            if prefix in reexports:
                hit = reexports[prefix] + ("." + ".".join(parts[k:]) if k < len(parts) else "")
                break
        if hit is None or hit + marker in seen:
            return sym
        seen.add(hit + marker)
        sym = hit + marker


def collect_imports(nodes) -> dict[str, str]:
    table: dict[str, str] = {}
    for node in nodes:
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.asname:
                    table[a.asname] = a.name
                else:
                    table[a.name.split(".")[0]] = a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for a in node.names:
                table[a.asname or a.name] = f"{node.module}.{a.name}"
    return table


def dotted(node, table) -> str | None:
    if isinstance(node, ast.Name):
        return table.get(node.id)
    if isinstance(node, ast.Attribute):
        base = dotted(node.value, table)
        if base is not None:
            return f"{base}.{node.attr}"
    return None


class PyFile:
    def __init__(self, repo: Path, rel: str):
        self.rel = rel
        self.src = (repo / rel).read_text(encoding="utf-8")
        self.tree = ast.parse(self.src)
        self.imports = collect_imports(self.tree.body)
        self.functions: dict[str, ast.FunctionDef] = {}
        self.fixtures: set[str] = set()
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node
                for dec in node.decorator_list:
                    target = dec.func if isinstance(dec, ast.Call) else dec
                    if ast.unparse(target) in ("pytest.fixture", "fixture"):
                        self.fixtures.add(node.name)
        self.loader_aliases = {name: fx for (f, name), fx in FIXTURE_LOADERS.items() if f == rel}
        for name in self.loader_aliases:
            if not any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name
                                                         for t in n.targets)
                       for n in self.tree.body):
                raise Refusal(f"declared fixture loader {rel}:{name} not found")


def analyze_function(pf: PyFile, fn, index, reexports, golden_names, visited=None):
    visited = visited if visited is not None else set()
    visited.add(fn.name)
    syms: set[str] = set()
    evidence_strings: list[str] = []
    local = collect_imports(n for n in ast.walk(fn) if isinstance(n, (ast.Import, ast.ImportFrom)))
    table = {**pf.imports, **local}
    golden_hits: set[str] = set()

    def add(sym: str | None):
        if sym and (sym.startswith("qrep") or sym.startswith(("fixture:", "conftest:", "diag:"))):
            syms.add(canonical(sym, reexports))

    for arg in fn.args.args:
        if arg.arg in pf.fixtures and arg.arg not in visited:
            sub = analyze_function(pf, pf.functions[arg.arg], index, reexports, golden_names,
                                   visited)
            syms |= sub["symbols"]
            golden_hits |= sub["golden"]
        elif arg.arg in CONFTEST_FIXTURES:
            syms.add(f"conftest:{arg.arg}")

    special_calls: set[int] = set()
    private_attrs: set[str] = set()
    constants: list[tuple[int, int, str]] = []
    # a golden file name counts only when the golden protocol is in play (the conftest
    # fixture or a GOLDEN_DIR constant); "top.svg" alone can be an export file name
    golden_ref = "conftest:golden" in syms
    for node in ast.walk(fn):
        if isinstance(node, ast.Name) and "GOLDEN" in node.id:
            golden_ref = True
        if isinstance(node, ast.Call):
            callee = canonical(dotted(node.func, table) or "", reexports)
            kws = {k.arg for k in node.keywords}
            if callee == "qrep.vision.pipeline.reverse":
                corners = "corners" in kws or len(node.args) >= 2
                syms.add(callee + ("[corners]" if corners else "[auto]"))
                special_calls.add(id(node.func))
            elif callee == "qrep.vision.rectify.rectify":
                corners = "corners" in kws or len(node.args) >= 2
                syms.add(callee + ("[corners]" if corners else "[auto]"))
                special_calls.add(id(node.func))
            elif callee == "qrep.bridge.reverse":
                corners = False
                if len(node.args) >= 2:
                    opt = node.args[1]
                    if isinstance(opt, ast.Constant) and isinstance(opt.value, str):
                        corners = '"corners"' in opt.value
                    elif isinstance(opt, ast.Call) and isinstance(opt.args[0] if opt.args else None,
                                                                  ast.Dict):
                        corners = any(isinstance(k, ast.Constant) and k.value == "corners"
                                      for k in opt.args[0].keys)
                syms.add(callee + ("[corners]" if corners else "[auto]"))
                special_calls.add(id(node.func))
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "invoke" and node.args:
                app = canonical(dotted(node.args[0], table) or "", reexports)
                if app == "qrep.cli.app" and len(node.args) > 1 and isinstance(node.args[1], ast.List):
                    elts = [e.value for e in node.args[1].elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)]
                    if elts:
                        cmd = elts[0]
                        marker = ""
                        if cmd == "reverse":
                            marker = "[corners]" if "--corners" in elts else "[auto]"
                        syms.add(f"qrep.cli:{cmd}{marker}")
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "get" and node.args:
                a0 = node.args[0]
                if isinstance(a0, ast.Constant) and a0.value in DIAG_KEYS:
                    syms.add(f"diag:{a0.value}")
        if isinstance(node, ast.Subscript):
            sl = node.slice
            if isinstance(sl, ast.Constant) and isinstance(sl.value, str) and sl.value in DIAG_KEYS:
                syms.add(f"diag:{sl.value}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            constants.append((node.lineno, node.col_offset, node.value))
            if node.value in STUB_STRATEGIES:
                syms.add("qrep.construct.strategies:stub")
            if node.value in golden_names:
                golden_hits.add(node.value)
            if node.value in pf.fixtures and node.value not in visited:
                sub = analyze_function(pf, pf.functions[node.value], index, reexports,
                                       golden_names, visited)
                syms |= sub["symbols"]
                golden_hits |= sub["golden"]
        if isinstance(node, ast.Attribute):
            if id(node) in special_calls:
                continue
            d = dotted(node, table)
            if d:
                add(d)
            elif node.attr.startswith("_") and not node.attr.startswith("__"):
                private_attrs.add(node.attr)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if id(node) in special_calls:
                continue
            if node.id in pf.loader_aliases:
                syms.add(pf.loader_aliases[node.id])
            elif node.id in table:
                add(table[node.id])
            elif node.id in pf.functions and node.id not in visited and not node.id.startswith("test"):
                sub = analyze_function(pf, pf.functions[node.id], index, reexports, golden_names,
                                       visited)
                syms |= sub["symbols"]
                golden_hits |= sub["golden"]
    # special call names were added above with a marker; drop their bare duplicates
    for base in ("qrep.vision.pipeline.reverse", "qrep.vision.rectify.rectify", "qrep.bridge.reverse"):
        if any(s.startswith(base + "[") for s in syms):
            syms.discard(base)
    # the CLI app object is plumbing once a command is known
    if any(s.startswith("qrep.cli:") for s in syms):
        syms.discard("qrep.cli.app")
    # private attributes on local variables: resolve against referenced qrep modules
    modules = {s for s in syms if s in index}
    for attr in sorted(private_attrs):
        for mod in sorted(modules):
            if attr in index[mod]:
                syms.add(f"{mod}.{attr}")
    # qrep source files read as text: "qrep", "vision", "grid.py" in source order
    constants.sort()
    values = [c[2] for c in constants]
    for i, v in enumerate(values):
        if v == "qrep":
            parts = []
            for w in values[i + 1:i + 4]:
                parts.append(w)
                if w.endswith(".py"):
                    mod = "qrep." + ".".join(p[:-3] if p.endswith(".py") else p for p in parts)
                    syms.add(mod)
                    evidence_strings.append("src:qrep/" + "/".join(parts))
                    break
    # drop a bare module when a more specific symbol under it is present
    for s in sorted(syms):
        if any(o != s and (o.startswith(s + ".") or o.startswith(s + "[") or o.startswith(s + ":"))
               for o in syms):
            syms.discard(s)
    if not (golden_ref or "conftest:golden" in syms):
        golden_hits = set()
    return {"symbols": syms, "golden": golden_hits, "evidence": evidence_strings}


def toplevel_flag_symbols(pf: PyFile, reexports) -> set[str]:
    return {canonical(v, reexports) for v in pf.imports.values() if v.startswith("qrep")}


def py_param_symbols(param: str | None) -> set[str]:
    out = set()
    if param and re.fullmatch(r"qrep(\.[a-z_]+)*", param):
        out.add(param)
    if param in STUB_STRATEGIES:
        out.add("qrep.construct.strategies:stub")
    return out


def override_for(node_id: str, overrides: list[dict]) -> list[dict]:
    func = node_id.split("[", 1)[0]
    file = node_id.split("::", 1)[0]
    hits = [o for o in overrides if o["match"] in (node_id, func, file)]
    rank = {node_id: 0, func: 1, file: 2}
    return sorted(hits, key=lambda o: rank[o["match"]])


def resolve_py_ticket(nid: str, cls: str, looked, explicit: str | None) -> str:
    if cls == KEEP:
        return "-"
    if explicit:
        return explicit
    if cls == RETIRE:
        groups = sorted({r[2] for _, r in looked if r[1] == "DELETE"})
        tickets = sorted({RETIRE_TICKET_BY_GROUP[g] for g in groups if g in RETIRE_TICKET_BY_GROUP})
        if len(tickets) == 1:
            return tickets[0]
    if cls == REEXPRESS:
        kinds = {r[1] for _, r in looked}
        if "INPUT" in kinds:
            return "B6a"
        if "MOVE" in kinds:
            return "A7"
    raise Refusal(f"{nid}: {cls} needs an explicit ticket")


def analyze_python(repo: Path, collect_text: str):
    index, reexports = build_qrep_index(repo)
    golden_names = {Path(p).name for p in tree_files(repo, "tests/golden")}
    node_ids = [ln.strip() for ln in collect_text.splitlines() if "::" in ln]
    summary = [m.group(0) for ln in collect_text.splitlines()
               for m in [re.search(r"\d+ tests? collected", ln)] if m]
    files: dict[str, PyFile] = {}
    rows = []
    used_overrides: set[int] = set()
    used_tags: set[int] = set()
    for nid in node_ids:
        rel, rest = nid.split("::", 1)
        func, param = (rest.split("[", 1) + [None])[:2]
        param = param[:-1] if param else None
        pf = files.setdefault(rel, PyFile(repo, rel))
        fn = pf.functions.get(func)
        if fn is None:
            raise Refusal(f"collected test {nid} has no module-level function {func}")
        res = analyze_function(pf, fn, index, reexports, golden_names)
        syms = set(res["symbols"]) | py_param_symbols(param)
        looked = sorted((s, fate_lookup(s, PY_FATE_RULES)) for s in syms)
        fates = [r[1] for _, r in looked]
        mech = mechanical_class(fates)
        row = dict(id=nid, suite="pytest", file=rel, name=func, params=param, line=fn.lineno,
                   mechanical=mech, symbols=[f"{s} ({r[1]}: {r[3]})" for s, r in looked],
                   tags=set(), notes=[], golden=sorted(res["golden"]))
        if res["evidence"]:
            row["notes"].append(("-", "reads " + ", ".join(res["evidence"]) + " as text"))
        if res["golden"]:
            row["tags"].add("golden")
        cls, basis = mech, "map"
        detail: dict[str, str] = {}
        ticket = None
        for ov in override_for(nid, PY_OVERRIDES):
            used_overrides.add(id(ov))
            if "cls" in ov and cls == mech:
                cls, basis = ov["cls"], "override"
            for k in ("how", "module", "reason", "prior"):
                if k in ov and k not in detail:
                    detail[k] = ov[k]
            if "ticket" in ov and ticket is None:
                ticket = ov["ticket"]
            row["tags"] |= set(ov.get("tags", []))
        if cls in (MIXED, UNSURE):
            raise Refusal(f"{nid}: {cls} with no closing override; symbols {sorted(syms)}")
        if basis == "override" and cls == mech:
            basis = "map"
        for decl in PY_DECLARED_TAGS:
            key, tag, tag_ticket, note = decl
            if key in (nid, nid.split("[", 1)[0]):
                used_tags.add(id(decl))
                row["tags"].add(tag)
                row["notes"].append((tag_ticket, f"{tag}: {note}"))
        delete_notes = sorted({r[3] for _, r in looked if r[1] == "DELETE"})
        if cls == RETIRE and "module" not in detail:
            detail["module"] = "; ".join(delete_notes) or "see symbols"
        if cls == REEXPRESS and "how" not in detail:
            kinds = set(fates)
            detail["how"] = HOW_MOVE if "MOVE" in kinds and "INPUT" not in kinds else HOW_INPUT
        if cls == KEEP and "reason" not in detail:
            groups = sorted({r[2] for _, r in looked if r[1] not in ("HARNESS",)})
            detail["reason"] = ("unaffected; subjects kept or rebuilt: " + ", ".join(groups)) \
                if groups else "unaffected; test harness or self-contained"
        if cls != RETIRE and any(s.startswith("qrep.bridge") for s in syms):
            row["tags"].add("bridge-v2")
        row.update(cls=cls, basis=basis, ticket=resolve_py_ticket(nid, cls, looked, ticket),
                   **filter_detail(cls, detail))
        rows.append(row)
    # file-level import repoints: the deleting ticket repoints the imports of rows that stay
    repoints = []
    for rel, pf in sorted(files.items()):
        bad = sorted(s for s in toplevel_flag_symbols(pf, reexports)
                     if fate_lookup(s, PY_FATE_RULES)[1] in ("DELETE", "MOVE"))
        staying = [r for r in rows if r["file"] == rel and r["cls"] != RETIRE]
        if not bad or not staying:
            continue
        groups = sorted({fate_lookup(s, PY_FATE_RULES)[2] for s in bad})
        tickets = ", ".join(sorted({RETIRE_TICKET_BY_GROUP.get(g, "-") for g in groups}))
        repoints.append((rel, bad, tickets))
        for row in staying:
            row["tags"].add("import-repoint")
    stale = [o["match"] for o in PY_OVERRIDES if id(o) not in used_overrides]
    if stale:
        raise Refusal(f"stale Python overrides: {stale}")
    stale_tags = [t[0] for t in PY_DECLARED_TAGS if id(t) not in used_tags]
    if stale_tags:
        raise Refusal(f"stale declared tags: {stale_tags}")
    for row in rows:
        row["tags"] = sorted(row["tags"])
    return rows, summary, repoints


# ---------------------------------------------------------------------------
# TypeScript scanning (comments, strings, templates, regex literals)
# ---------------------------------------------------------------------------
REGEX_PREV_PUNCT = set("(,=:[!&|?{};+-*%<>~^")
REGEX_PREV_WORDS = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete",
                    "void", "throw", "yield", "await"}


def js_unescape(body: str) -> str:
    out, i = [], 0
    simple = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        nxt = body[i + 1] if i + 1 < len(body) else ""
        if nxt in simple:
            out.append(simple[nxt])
            i += 2
        elif nxt == "u" and body[i + 2:i + 3] == "{":
            j = body.index("}", i)
            out.append(chr(int(body[i + 3:j], 16)))
            i = j + 1
        elif nxt == "u":
            out.append(chr(int(body[i + 2:i + 6], 16)))
            i += 6
        elif nxt == "x":
            out.append(chr(int(body[i + 2:i + 4], 16)))
            i += 4
        elif nxt == "\n":
            i += 2
        else:
            out.append(nxt)
            i += 2
    return "".join(out)


def ts_tokens(src: str) -> list[dict]:
    toks: list[dict] = []
    i, n = 0, len(src)

    def prev_allows_regex() -> bool:
        if not toks:
            return True
        t = toks[-1]
        if t["kind"] == "punct":
            return t["value"] in REGEX_PREV_PUNCT
        if t["kind"] == "id":
            return t["value"] in REGEX_PREV_WORDS
        return False

    while i < n:
        c = src[i]
        if c in " \t\r\n":
            i += 1
            continue
        if src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if src.startswith("/*", i):
            j = src.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            toks.append(dict(kind="str", value=js_unescape(src[i + 1:j]), start=i, end=j + 1))
            i = j + 1
            continue
        if c == "`":
            j, depth, has_expr = i + 1, 0, False
            while j < n:
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if depth == 0 and ch == "`":
                    break
                if src.startswith("${", j) and depth == 0:
                    has_expr = True
                    depth = 1
                    j += 2
                    continue
                if depth > 0:
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                    elif ch in "\"'`":
                        q = ch
                        j += 1
                        while j < n and src[j] != q:
                            j += 2 if src[j] == "\\" else 1
                j += 1
            raw = src[i + 1:j]
            toks.append(dict(kind="tmpl", value=raw, has_expr=has_expr, start=i, end=j + 1))
            i = j + 1
            continue
        if c == "/" and prev_allows_regex():
            j, in_class = i + 1, False
            while j < n:
                ch = src[j]
                if ch == "\\":
                    j += 2
                    continue
                if ch == "[":
                    in_class = True
                elif ch == "]":
                    in_class = False
                elif ch == "/" and not in_class:
                    break
                elif ch == "\n":
                    break
                j += 1
            j += 1
            while j < n and (src[j].isalnum()):
                j += 1
            toks.append(dict(kind="regex", value=src[i:j], start=i, end=j))
            i = j
            continue
        if c.isalpha() or c in "_$":
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            toks.append(dict(kind="id", value=src[i:j], start=i, end=j))
            i = j
            continue
        if c.isdigit():
            j = i + 1
            while j < n and (src[j].isalnum() or src[j] in "._"):
                j += 1
            toks.append(dict(kind="num", value=src[i:j], start=i, end=j))
            i = j
            continue
        toks.append(dict(kind="punct", value=c, start=i, end=i + 1))
        i += 1
    return toks


def match_brackets(toks: list[dict]) -> dict[int, int]:
    pairs, stack = {}, []
    opening = {"(": ")", "[": "]", "{": "}"}
    for k, t in enumerate(toks):
        if t["kind"] != "punct":
            continue
        if t["value"] in opening:
            stack.append(k)
        elif t["value"] in ")]}":
            if stack:
                pairs[stack.pop()] = k
    return pairs


TEST_CALLEES = {"test", "it", "test.only", "test.skip", "test.fixme", "test.fail", "it.only",
                "it.skip", "test.fails", "it.fails"}
DESCRIBE_CALLEES = {"describe", "test.describe", "describe.only", "describe.skip",
                    "test.describe.only", "test.describe.skip", "test.describe.serial"}


def is_punct(tok: dict, value: str) -> bool:
    return tok["kind"] == "punct" and tok["value"] == value


def ts_calls(src: str):
    toks = ts_tokens(src)
    pairs = match_brackets(toks)
    calls = []
    k = 0
    while k < len(toks):
        t = toks[k]
        if t["kind"] == "id" and t["value"] in ("test", "it", "describe") and not (
                k > 0 and is_punct(toks[k - 1], ".")):
            j, chain = k, [t["value"]]
            while (j + 2 < len(toks) and is_punct(toks[j + 1], ".") and
                   toks[j + 2]["kind"] == "id"):
                chain.append(toks[j + 2]["value"])
                j += 2
            callee = ".".join(chain)
            p = j + 1
            if p < len(toks) and is_punct(toks[p], "(") and (callee in TEST_CALLEES or
                                                            callee in DESCRIBE_CALLEES):
                q = pairs.get(p)
                depth, a = 0, p + 1
                while a < q:
                    v = toks[a]["value"] if toks[a]["kind"] == "punct" else None
                    if v in ("(", "[", "{"):
                        depth += 1
                    elif v in (")", "]", "}"):
                        depth -= 1
                    elif v == "," and depth == 0:
                        break
                    a += 1
                first = toks[p + 1:a]
                if len(first) == 1 and first[0]["kind"] == "str":
                    title, dynamic = first[0]["value"], None
                elif len(first) == 1 and first[0]["kind"] == "tmpl" and not first[0]["has_expr"]:
                    title, dynamic = js_unescape(first[0]["value"]), None
                else:
                    title = None
                    dynamic = src[first[0]["start"]:first[-1]["end"]] if first else ""
                calls.append(dict(kind="describe" if callee in DESCRIBE_CALLEES else "test",
                                  callee=callee, title=title, dynamic=dynamic, tok=k, open=p,
                                  close=q, start=toks[p]["start"], end=toks[q]["end"],
                                  line=src.count("\n", 0, t["start"]) + 1))
                k = p
        k += 1
    return toks, pairs, calls


def ts_function_spans(src: str, toks: list[dict], pairs: dict[int, int]) -> dict[str, tuple]:
    spans = {}
    for k, t in enumerate(toks):
        if t["kind"] == "id" and t["value"] == "function" and k + 1 < len(toks) and \
                toks[k + 1]["kind"] == "id":
            name = toks[k + 1]["value"]
            b = k + 2
            while b < len(toks) and toks[b]["value"] != "{":
                b += 1
            if b in pairs:
                spans[name] = (toks[b]["start"], toks[pairs[b]]["end"])
    return spans


TESTID_RE = re.compile(r"getByTestId\(\s*([\"'`])(.*?)\1")
TESTID_ATTR_RE = re.compile(r"data-testid\^?=\s*['\"]([^'\"]+)['\"]")
ATTR_RE = re.compile(r"toHaveAttribute\(\s*\"(data-[a-z-]+)\"")
TAB_RE = re.compile(r"getByRole\(\s*\"tab\",\s*\{\s*name:\s*\"(\w+)\"")


def e2e_surfaces(text: str) -> set[str]:
    out = set()
    for _q, tid in TESTID_RE.findall(text):
        out.add(re.sub(r"\$\{[^}]*\}.*$", "*", tid))
    for tid in TESTID_ATTR_RE.findall(text):
        out.add(tid.rstrip("-") + "-*" if tid.endswith("-") else tid)
    for attr in ATTR_RE.findall(text):
        if attr in ("data-verdict", "data-vision-state"):
            out.add(f"attr:{attr}")
    for tab in TAB_RE.findall(text):
        out.add(f"tab:{tab}")
    if "spike.html" in text:
        out.add("url:spike.html")
    if "ControlOrMeta+z" in text or "Control+y" in text:
        out.add("key:undo-redo")
    return out


# ---------------------------------------------------------------------------
# web expanders (mirror the loop sources exactly)
# ---------------------------------------------------------------------------


def web_src_files(repo: Path) -> list[str]:
    out = []
    for rel in tree_files(repo, "web/src"):
        name = rel.split("/")[-1]
        if re.search(r"\.(ts|tsx|css)$", name) and not re.search(r"\.test\.tsx?$", name):
            out.append(rel[len("web/src/"):])
    return sorted(out)


def ts_array_literal(src: str, const_name: str) -> list[dict]:
    toks = ts_tokens(src)
    pairs = match_brackets(toks)
    for k, t in enumerate(toks):
        if t["kind"] == "id" and t["value"] == const_name:
            j = k
            while j < len(toks) and not is_punct(toks[j], "="):
                j += 1
            j += 1
            if j < len(toks) and is_punct(toks[j], "["):
                return toks[j + 1:pairs[j]]
    raise Refusal(f"array literal {const_name} not found")


IMPORT_RE = re.compile(r"import\s+(type\s+)?\{([^}]*)\}\s*from\s*\"(\.{1,2}/[^\"]+)\"")


def ts_value_imports(src: str, rel: str, repo: Path) -> list[tuple[str, list[str]]]:
    """(web/src-relative module, imported value names) for relative named imports."""
    out = []
    for type_only, names, spec in IMPORT_RE.findall(src):
        if type_only:
            continue
        values = []
        for part in names.split(","):
            part = part.strip()
            if not part or part.startswith("type "):
                continue
            values.append(part.split(" as ")[-1].strip())
        target = os.path.normpath(os.path.join(os.path.dirname(rel), spec)).replace("\\", "/")
        for ext in (".ts", ".tsx"):
            if (repo / (target + ext)).exists():
                out.append(((target + ext)[len("web/src/"):], values))
                break
    return out


def expand_dynamic(repo: Path, rel: str, src: str, dynamic: str) -> list[str]:
    compact = re.sub(r"\s+", "", dynamic)
    if rel in ("web/src/copy-audit.test.ts", "web/src/copy-audit-verdicts.test.ts") and \
            compact == "path.relative(srcRoot,file)":
        return web_src_files(repo)
    if rel == "web/src/model/units.test.ts" and compact == "`${eighths}->${display}`":
        cases = json.loads((repo / "tests/fixtures/fraction_display.json")
                           .read_text(encoding="utf-8"))["cases"]
        return [f"{c['eighths']} -> {c['display']}" for c in cases]
    if rel == "web/src/model/fraction.test.ts":
        if compact == "`accepts${JSON.stringify(text)}as${eighths}eighths`":
            items = [t for t in ts_array_literal(src, "ACCEPTED") if t["kind"] in ("str", "num")]
            pairs = list(zip(items[0::2], items[1::2]))
            return [f"accepts {json.dumps(s['value'], ensure_ascii=False)} as {num['value']} "
                    "eighths" for s, num in pairs]
        if compact == "`rejects${JSON.stringify(text)}`":
            items = [t for t in ts_array_literal(src, "REJECTED") if t["kind"] == "str"]
            return [f"rejects {json.dumps(s['value'], ensure_ascii=False)}" for s in items]
    raise Refusal(f"no expander for dynamic title in {rel}: {dynamic}")


# ---------------------------------------------------------------------------
# web analysis
# ---------------------------------------------------------------------------


def analyze_web(repo: Path):
    rows = []
    used_overrides: set[int] = set()
    used_decisions: set[tuple] = set()
    files = [f for f in tree_files(repo, "web/e2e", "web/src")
             if re.search(r"\.spec\.ts$", f) or re.search(r"\.test\.tsx?$", f)]
    for rel in files:
        src = (repo / rel).read_text(encoding="utf-8")
        toks, pairs, calls = ts_calls(src)
        helpers = ts_function_spans(src, toks, pairs)
        suite = "playwright" if rel.startswith("web/e2e/") else "vitest"
        describes = [c for c in calls if c["kind"] == "describe"]
        value_imports = ts_value_imports(src, rel, repo)
        for c in calls:
            if c["kind"] != "test":
                continue
            chain = [d["title"] for d in describes if d["start"] < c["start"] and d["end"] >= c["end"]]
            if any(t is None for t in chain):
                raise Refusal(f"dynamic describe title in {rel}")
            titles = [c["title"]] if c["title"] is not None else \
                expand_dynamic(repo, rel, src, c["dynamic"])
            body = src[c["start"]:c["end"]]
            seen_helpers, stack = set(), [body]
            while stack:
                text = stack.pop()
                for name, (a, b) in helpers.items():
                    if name not in seen_helpers and re.search(rf"\b{name}\(", text):
                        seen_helpers.add(name)
                        stack.append(src[a:b])
            full_text = body + "".join(src[helpers[h][0]:helpers[h][1]] for h in sorted(seen_helpers))
            for title in titles:
                full = " > ".join(chain + [title])
                nid = f"{rel}::{full}"
                row = dict(id=nid, suite=suite, file=rel, name=full, params=None, line=c["line"],
                           tags=set(), notes=[], golden=[])
                detail: dict[str, str] = {}
                ticket = "-"
                if suite == "playwright":
                    surfaces = sorted(e2e_surfaces(full_text))
                    looked = [(s, fate_lookup(s, E2E_SURFACE_RULES)) for s in surfaces]
                    mech = mechanical_class([r[1] for _, r in looked])
                    row["symbols"] = [f"{s} ({r[1]}: {r[2]})" for s, r in looked]
                    dec = E2E_DECISIONS.get((rel, title))
                    if dec is None:
                        raise Refusal(f"no e2e decision for {nid}")
                    used_decisions.add((rel, title))
                    cls = dec["cls"]
                    ticket = dec.get("ticket", "-")
                    for k in ("how", "module", "reason", "prior"):
                        if k in dec:
                            detail[k] = dec[k]
                    row["tags"] |= set(dec.get("tags", []))
                    if dec.get("tag_note"):
                        row["notes"].append((dec.get("tag_ticket", "-"), dec["tag_note"]))
                    if re.search(r"golden(Dir|CsvPath)|cutlist_strip|top\.svg", full_text):
                        row["tags"].add("golden")
                else:
                    rule = WEB_VITEST_FILE_RULES.get(rel)
                    if rule is None:
                        raise Refusal(f"no vitest file rule for {rel}")
                    syms = []
                    if rule.get("per_file") and c["dynamic"] is not None:
                        fate, note, file_ticket = WEB_FILE_FATE.get(
                            title, ("KEEP", "not scheduled for deletion", "-"))
                        syms.append(f"scans web/src/{title} ({fate}: {note})")
                        mech = cls = RETIRE if fate == "DELETE" else KEEP
                        if fate == "DELETE":
                            ticket = file_ticket
                            detail["module"] = f"web/src/{title} ({note}); the per-file scan id " \
                                "leaves with the file"
                        elif title in WEB_FILE_FATE:
                            detail["reason"] = f"scans web/src/{title}: {note}"
                        else:
                            detail["reason"] = f"scans web/src/{title}, which is not scheduled " \
                                "for deletion"
                    else:
                        fates = []
                        for sub, names in value_imports:
                            used = [nm for nm in names if re.search(rf"\b{re.escape(nm)}\b",
                                                                    full_text)]
                            if used:
                                fate, note, _t = WEB_FILE_FATE.get(sub, ("KEEP", "not scheduled",
                                                                         "-"))
                                fates.append(fate)
                                syms.append(f"uses {', '.join(used)} from web/src/{sub} "
                                            f"({fate}: {note})")
                        for marker, fate, note in (("spike.html", "DELETE", "spike page"),
                                                   ("viewer.html", "OPEN", "sprint-1 viewer "
                                                    "docs page")):
                            if marker in body:
                                fates.append(fate)
                                syms.append(f"asserts {marker} ({fate}: {note})")
                        if rel == "web/src/state/photoFlow.test.ts":
                            hooks = sorted(h for h in PHOTOFLOW_DETECT_HOOKS
                                           if re.search(rf"\b{h}\b", body))
                            if hooks:
                                fates.append("OPEN")
                                syms.append("detect_quad hooks " + ", ".join(hooks) +
                                            " (OPEN: exist only to consume detect_quad)")
                        mech = mechanical_class(fates) if fates else KEEP
                        cls = rule["cls"]
                        if cls == RETIRE:
                            detail["module"] = rule["module"]
                            ticket = rule["ticket"]
                        elif "reason" in rule:
                            detail["reason"] = rule["reason"]
                    row["symbols"] = syms
                    row["tags"] |= set(rule.get("tags", []))
                    if rule.get("tag_note"):
                        row["notes"].append((rule.get("tag_ticket", "-"), rule["tag_note"]))
                    for ov in WEB_OVERRIDES:
                        m = ov["match"]
                        if nid == m or nid.startswith(m + " > "):
                            used_overrides.add(id(ov))
                            cls = ov["cls"]
                            ticket = ov.get("ticket", "-")
                            detail = {k: ov[k] for k in ("how", "module", "reason", "prior")
                                      if k in ov}
                    if rel == "web/src/copy-audit-verdicts.test.ts" and cls != RETIRE:
                        row["tags"].add("import-repoint")
                basis = "map" if cls == mech else "override"
                row["mechanical"] = mech
                if cls == RETIRE and "module" not in detail:
                    raise Refusal(f"{nid}: RETIRE without module")
                if cls == REEXPRESS and "how" not in detail:
                    raise Refusal(f"{nid}: REEXPRESS without how")
                if cls not in CLASSES:
                    raise Refusal(f"{nid}: class {cls} is not closed")
                if cls == KEEP:
                    ticket = "-"
                    detail.setdefault("reason", "unaffected")
                elif ticket == "-":
                    raise Refusal(f"{nid}: {cls} needs a ticket")
                row.update(cls=cls, basis=basis, ticket=ticket, **filter_detail(cls, detail))
                row["tags"] = sorted(row["tags"])
                rows.append(row)
    stale = [o["match"] for o in WEB_OVERRIDES if id(o) not in used_overrides]
    if stale:
        raise Refusal(f"stale web overrides: {stale}")
    missing = sorted(set(E2E_DECISIONS) - used_decisions)
    if missing:
        raise Refusal(f"stale e2e decisions: {missing}")
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise Refusal("duplicate web test ids")
    return rows


# ---------------------------------------------------------------------------
# rendering
# ---------------------------------------------------------------------------


def counts(rows) -> dict[str, dict[str, int]]:
    out = {s: {c: 0 for c in CLASSES} for s in SUITES}
    for r in rows:
        out[r["suite"]][r["cls"]] += 1
    return out


def closing_key(row_id: str) -> str | None:
    if row_id in CLOSED_FROM:
        return row_id
    func = row_id.split("[", 1)[0]
    return func if func in CLOSED_FROM else None


def sentence(text: str) -> str:
    """Capitalize a detail that starts with a plain word (never a path or identifier)."""
    first = text.split(" ", 1)[0]
    if text[:1].islower() and not any(ch in first for ch in "/._(`["):
        return text[0].upper() + text[1:]
    return text


def row_detail(r: dict) -> str:
    if r["cls"] == RETIRE:
        text = sentence(r["module"])
        if r.get("reason"):
            text += ". " + sentence(r["reason"])
        if r.get("prior"):
            text += ". Before then, " + r["prior"]
        return text
    if r["cls"] == REEXPRESS:
        return sentence(r["how"])
    return sentence(r.get("reason", ""))


def base_id(row_id: str) -> str:
    return row_id.split("[", 1)[0] if row_id.endswith("]") else row_id


def collapse(entries: list[tuple[str, str, str]]) -> list[list[str]]:
    """(id, text, ticket) rows; parametrized ids with the same text share one row."""
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for row_id, text, ticket in entries:
        grouped.setdefault((base_id(row_id), text, ticket), []).append(row_id)
    out = []
    for (base, text, ticket), ids in grouped.items():
        label = code(ids[0]) if len(ids) == 1 else f"{code(base + '[...]')} ({len(ids)} ids)"
        out.append([label, text, ticket])
    return out


def table(header: list[str], body: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(md_escape(cell) for cell in row) + " |" for row in body]
    return lines


def render_provenance(meta) -> str:
    lines = [
        f"- Recorded commit: `{RECORDED_COMMIT}`.",
        f"- Generator: scripts/rebaseline_inventory.py, version {GENERATOR_VERSION}.",
        f"- Python collection: `{COLLECT_COMMAND}` ({meta['collect_summary']}).",
        "- Web titles: parsed statically from web/src/**/*.test.ts and web/e2e/*.spec.ts at the "
        "recorded commit.",
        "- Cross-checks: " + "; ".join(meta["checks"]) + ".",
        "",
        "Scheduled for deletion (expand, then contract):",
        "",
    ]
    for group, ticket, text in SCHEDULE:
        lines.append(f"- {group} ({ticket}): {text}.")
    return "\n".join(lines)


def render_totals(rows) -> str:
    c = counts(rows)
    body = []
    for suite in SUITES:
        n = c[suite]
        body.append([suite] + [str(n[k]) for k in CLASSES] + ["0", str(sum(n.values()))])
    web = {k: c["vitest"][k] + c["playwright"][k] for k in CLASSES}
    body.append(["web (vitest + playwright)"] + [str(web[k]) for k in CLASSES] +
                ["0", str(sum(web.values()))])
    allc = {k: sum(c[s][k] for s in SUITES) for k in CLASSES}
    body.append(["all"] + [str(allc[k]) for k in CLASSES] + ["0", str(sum(allc.values()))])
    lines = table(["Suite", "KEEP", "RETIRE", "REEXPRESS", "UNSURE", "Total"], body)
    lines += ["", "Entries by executing ticket (an entry that names two tickets counts under "
              "both):", ""]
    per: dict[str, dict[str, int]] = {t: {RETIRE: 0, REEXPRESS: 0} for t in TICKETS}
    for r in rows:
        for t in split_tickets(r["ticket"]):
            per[t][r["cls"]] += 1
    tbody = [[t, TICKETS[t], str(per[t][RETIRE]), str(per[t][REEXPRESS])]
             for t in TICKETS if per[t][RETIRE] or per[t][REEXPRESS]]
    lines += table(["Ticket", "Title in the plan (the plan owns the scope)", "RETIRE",
                    "REEXPRESS"], tbody)
    return "\n".join(lines)


def render_closing(rows) -> str:
    grouped: dict[str, list[dict]] = {}
    for r in rows:
        key = closing_key(r["id"])
        if key is not None:
            grouped.setdefault(key, []).append(r)
    body = []
    for key, mine in grouped.items():
        first = mine[0]
        label = code(first["id"]) if len(mine) == 1 else f"{code(key + '[...]')} ({len(mine)} ids)"
        body.append([label, CLOSED_FROM[key], first["cls"], first["ticket"], row_detail(first)])
    return "\n".join(table(["Test id", "Was", "Now", "Ticket", "Reason"], body))


def file_order(rows) -> list[str]:
    seen: list[str] = []
    for r in rows:
        if r["file"] not in seen:
            seen.append(r["file"])
    return seen


def render_class(rows, cls: str, detail_header: str) -> str:
    chosen = [r for r in rows if r["cls"] == cls]
    lines: list[str] = []
    for f in file_order(chosen):
        mine = [r for r in chosen if r["file"] == f]
        total = sum(1 for r in rows if r["file"] == f)
        tickets = sorted({t for r in mine for t in split_tickets(r["ticket"])})
        lines += [f"#### {f} ({len(mine)} of {total}; {', '.join(tickets)})", ""]
        lines += table(["Test id", detail_header, "Ticket", "By"],
                       [[code(r["id"]), row_detail(r), r["ticket"], r["basis"]] for r in mine])
        lines.append("")
    if not lines:
        return "None."
    return "\n".join(lines).rstrip("\n")


def render_kept(rows, repoints, web: bool) -> str:
    kept = [r for r in rows if r["cls"] == KEEP]
    body = []
    for f in file_order(rows):
        n = sum(1 for r in kept if r["file"] == f)
        total = sum(1 for r in rows if r["file"] == f)
        if n:
            body.append([f, str(n), str(total)])
    lines = table(["File", "Kept", "Tests in file"], body)
    entries: list[tuple[str, str, str]] = []
    for r in kept:
        for g in r.get("golden", []):
            entries.append((r["id"], f"Byte-compares tests/golden/{g}; only A6 re-blesses it",
                            "A6"))
        for ticket, note in r["notes"]:
            if ticket == "-" and note.startswith("reads "):
                continue
            entries.append((r["id"], sentence(note), ticket))
    # a condition carried by every kept test of a file is stated once for the file
    per_file: dict[tuple[str, str, str], list[str]] = {}
    for row_id, text, ticket in entries:
        per_file.setdefault((row_id.split("::", 1)[0], text, ticket), []).append(row_id)
    whole: list[list[str]] = []
    rest: list[tuple[str, str, str]] = []
    for (f, text, ticket), ids in per_file.items():
        kept_in_file = [r["id"] for r in kept if r["file"] == f]
        if len(ids) > 1 and sorted(ids) == sorted(kept_in_file):
            whole.append([f"{f} (all {len(ids)} kept tests)", text, ticket])
        else:
            rest += [(i, text, ticket) for i in ids]
    cond = collapse(rest) + whole
    lines += ["", "Kept tests with conditions:", ""]
    lines += table(["Test or file", "Condition", "Ticket"], cond) if cond else ["None."]
    imports = [[rel, "Imports " + ", ".join(bad) + " at top level", ticket]
               for rel, bad, ticket in repoints]
    if web:
        imports.append(["web/src/copy-audit-verdicts.test.ts",
                        "Imports ./model/verdictStory at top level", "C6b"])
    if imports:
        lines += ["", "Top-level imports that the deleting ticket repoints or removes in the same "
                  "PR, assertions unchanged (files with tests that stay or are re-expressed):", ""]
        lines += table(["File", "Import", "Ticket"], imports)
    return "\n".join(lines)


def render_support(repo: Path) -> str:
    present = set(tree_files(repo, *[f for f, _n, _t in SUPPORT_FILES]))
    body = [[f, note, ticket] for f, note, ticket in SUPPORT_FILES if f in present]
    lines = table(["Path at the recorded commit", "What it is", "Ticket"], body)
    lines += ["", "CI steps at the recorded commit:", ""]
    lines += table(["Step", "Ticket"], [[note, ticket] for note, ticket in CI_NOTES])
    return "\n".join(lines)


def render_blocks(repo: Path, meta, py_rows, web_rows, repoints) -> dict[str, str]:
    all_rows = py_rows + web_rows
    return {
        "provenance": render_provenance(meta),
        "totals": render_totals(all_rows),
        "closing": render_closing(all_rows),
        "py-retired": render_class(py_rows, RETIRE, "Retires with"),
        "py-reexpressed": render_class(py_rows, REEXPRESS, "What changes"),
        "py-kept": render_kept(py_rows, repoints, web=False),
        "web-retired": render_class(web_rows, RETIRE, "Retires with"),
        "web-reexpressed": render_class(web_rows, REEXPRESS, "What changes"),
        "web-kept": render_kept(web_rows, [], web=True),
        "support": render_support(repo),
    }


# ---------------------------------------------------------------------------
# blocks in the record
# ---------------------------------------------------------------------------


def block_pattern(name: str) -> re.Pattern:
    return re.compile(rf"(<!-- rebaseline:begin {re.escape(name)} -->\n)(.*?)"
                      rf"(<!-- rebaseline:end {re.escape(name)} -->)", re.S)


def read_blocks(text: str) -> dict[str, str]:
    out = {}
    for name in BLOCKS:
        found = block_pattern(name).findall(text)
        if len(found) != 1:
            raise Refusal(f"the record must hold exactly one '{name}' block (found {len(found)})")
        out[name] = found[0][1]
    return out


def write_blocks(text: str, blocks: dict[str, str]) -> str:
    for name in BLOCKS:
        body = blocks[name].rstrip("\n") + "\n"
        text = block_pattern(name).sub(lambda m, b=body: m.group(1) + b + m.group(3), text)
    return text


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def generate(repo: Path, collect_file: Path | None):
    verify_inputs(repo)
    if collect_file:
        collect_text = collect_file.read_text(encoding="utf-8")
    else:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        collect_text = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p",
                            "no:cacheprovider"], repo, env)
    py_rows, summary, repoints = analyze_python(repo, collect_text)
    web_rows = analyze_web(repo)
    order = {"vitest": 0, "playwright": 1}
    web_rows.sort(key=lambda r: (order[r["suite"]], r["file"], r["line"], r["id"]))
    found = re.search(r"(\d+) tests? collected", " ".join(summary))
    collected = int(found.group(1)) if found else -1
    c = counts(py_rows + web_rows)
    got = {s: sum(c[s].values()) for s in SUITES}
    if collected != got["pytest"]:
        raise Refusal(f"collected {collected} but classified {got['pytest']}")
    for suite, expected in EXPECTED_COUNTS.items():
        if got[suite] != expected:
            raise Refusal(f"{suite}: {got[suite]} tests, expected {expected} at the recorded "
                          "commit")
    used = {t for r in py_rows + web_rows for t in split_tickets(r["ticket"])}
    unknown = sorted(used - set(TICKETS))
    if unknown:
        raise Refusal(f"unknown tickets: {unknown}")
    stale = sorted(k for k in CLOSED_FROM
                   if not any(closing_key(r["id"]) == k for r in py_rows + web_rows))
    if stale:
        raise Refusal(f"stale closing entries: {stale}")
    checks = [f"pytest {got['pytest']} classified of {collected} collected",
              f"vitest {got['vitest']} titles", f"Playwright {got['playwright']} titles",
              "the counts equal those observed at the recorded commit (pytest 569 passed and "
              "1 skipped; vitest 252 and Playwright 48 passed)"]
    meta = dict(collect_summary="; ".join(summary), checks=checks)
    return render_blocks(repo, meta, py_rows, web_rows, repoints), py_rows + web_rows


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true",
                      help="exit 1 if the record's tables differ from a fresh generation")
    mode.add_argument("--write", action="store_true",
                      help="rewrite the generated blocks of the record")
    mode.add_argument("--list", choices=CLASSES, help="print the ids of one class")
    ap.add_argument("--repo", type=Path, default=REPO_ROOT,
                    help="checkout to read at the recorded commit (default: this repo)")
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                    help="the record (default: docs/sprint-5/REBASELINE.md in this repo)")
    ap.add_argument("--collect-file", type=Path, default=None,
                    help="saved `pytest --collect-only -q` output from the recorded commit")
    args = ap.parse_args()
    try:
        blocks, rows = generate(args.repo.resolve(), args.collect_file)
        if args.list:
            for r in rows:
                if r["cls"] == args.list:
                    print(r["id"])
            return 0
        text = args.output.read_text(encoding="utf-8")
        current = read_blocks(text)
        if args.write:
            new = write_blocks(text, blocks)
            if new != text:
                args.output.write_text(new, encoding="utf-8", newline="\n")
            print(f"wrote the generated blocks of {args.output}")
            return 0
        differs = [n for n in BLOCKS if current[n] != blocks[n].rstrip("\n") + "\n"]
        if differs:
            for name in differs:
                diff = difflib.unified_diff(current[name].splitlines(),
                                            (blocks[name].rstrip("\n") + "\n").splitlines(),
                                            f"{name} (record)", f"{name} (fresh)", lineterm="")
                print("\n".join(list(diff)[:60]))
            print(f"FAIL: {len(differs)} block(s) differ from a fresh generation at "
                  f"{RECORDED_COMMIT[:7]}: {', '.join(differs)}")
            return 1
        c = counts(rows)
        summary = ", ".join(f"{s} " + "/".join(str(c[s][k]) for k in CLASSES) for s in SUITES)
        print(f"OK: the record matches a fresh generation at {RECORDED_COMMIT[:7]} "
              f"(KEEP/RETIRE/REEXPRESS: {summary}; UNSURE 0)")
        return 0
    except Refusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
