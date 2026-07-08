# QREP: Overnight Build Prompt

## Mission

Build QREP, an open-source Python system that reverse engineers quilts from photographs into production-ready patterns. Tonight's run builds v1 per the design doc (qrep-design-doc.md, in repo root, read it first and treat it as binding). v1 proves the architecture on grid-based quilts with the Double Irish Chain as the benchmark.

This is not a one-off script. Build a reusable library with a CLI.

## Ground rules

1. Build back-to-front. The quilt model, construction engine, and exports come first because they need no computer vision and are fully testable. The CV pipeline comes last and is validated against synthetic renders.
2. Each phase gates on green tests. Do not start a phase until the previous phase passes.
3. No thrashing. If a component fails after 3 genuinely distinct approaches, write the failure up in KNOWN_ISSUES.md (what you tried, why it failed, best partial result) and move on.
4. No GUI, no web app, no manual editing tools. Editing is JSON or the Python API.
5. Never present inferred data as certain. Every CV-derived attribute carries a confidence score. Hand-authored data is confidence 1.0.
6. Commit at the end of each phase with a message summarizing what passed.
7. Stack per design doc: Python 3.12, pydantic, numpy, OpenCV, scikit-image, Pillow, svgwrite, weasyprint or reportlab, typer, pytest, ruff.

## Phase 1: Quilt model and benchmark fixture

Build the model package.

- Pydantic schema: Quilt with metadata, palette (named fabrics, hex colors), regions (center Grid of rows x cols x finished cell size x fabric ids, border bands, binding), quilting layer (motif regions, authored only), settings (seam allowance, WOF, binding width, all defaulted per design doc).
- Confidence wrapper on inferable attributes.
- JSON serialize and deserialize with schema_version.
- Author the benchmark fixture from pattern knowledge: a two-fabric Double Irish Chain, light blue chain on cream. Standard structure: 5x5 pieced Block A alternating with a mostly-plain Block B carrying corner squares, laid out so chains connect diagonally across block boundaries. Verify connectivity yourself before accepting the fixture. Roughly 75 x 90 inches finished with a plain border. Fidelity to the exact Tori Jones antique is not required, structural correctness of the pattern is.

Acceptance:
- JSON round trip test passes (model -> JSON -> model, equal)
- Fixture validates against the schema
- A test asserts chain continuity across at least one Block A to Block B boundary

## Phase 2: Construction engine

Strategy interface: pure function, Model in, ConstructionPlan out. ConstructionPlan holds cut list, strip sets with subcuts, assembly steps, metrics (piece count, cut count, seam count, strip sets, waste estimate, bias percent, difficulty heuristic, rough time heuristic).

Implement three strategies:
1. historical: literal patch-by-patch
2. strip: detect repeated row or column fabric sequences, emit strip sets and subcut instructions
3. modern: merge same-fabric adjacent cells into larger cut pieces where no seam is visually required

Stub fpp, epp, hand, longarm behind the interface, raising NotImplementedError with a message.

Acceptance:
- Yardage unit test on a known simple grid with hand-computed expected values written in the test comments
- For the benchmark fixture: strip plan total cuts < historical plan total cuts
- For the benchmark fixture: modern plan piece count < historical plan piece count
- All three plans agree on total fabric area within 5 percent (waste may differ, patch area may not)

## Phase 3: Exports

- Cut list (markdown and CSV): per fabric, per piece size, quantities, strip cutting chart
- Yardage report per fabric including binding and backing
- SVG: full quilt top diagram, per-block diagrams, strip set diagrams, numbered assembly diagram
- PDF pattern booklet assembling the above into sections: intro, fabric list, cutting, strip sets, assembly, borders, binding, finishing. The booklet composes existing exports, it is not a layout engine.
- CLI: qrep validate, qrep plan --strategy, qrep export

Acceptance:
- Golden file tests for the fixture's SVG top diagram and cut list
- PDF generates without error and contains every section
- Cut list quantities reconcile with the plan's piece counts (tested)

## Phase 4: Synthetic renderer

Model to PNG at difficulty levels per design doc: L0 clean orthographic, L1 texture noise and color variance, L2 perspective warp and lighting gradient, L3 fold shading, clutter, partial occlusion. CLI: qrep render --level.

Acceptance:
- Fixture renders at all four levels
- Pixel tests on L0: image dimensions match model aspect, sampled cell centers match palette colors

## Phase 5: CV pipeline against synthetic images

Pipeline stages per design doc: rectify (corners detected or supplied), palette via k-means in Lab, grid via edge projections and autocorrelation, cell fabric assignment, repeat detection via 2D autocorrelation, border detection, emit model with per-stage confidence. CLI: qrep reverse image.png -o recovered.json.

Round-trip test harness: author model, render, reverse, compare to ground truth.

Acceptance thresholds:
- L0: exact grid dimensions, 100 percent cell assignment accuracy
- L1: exact grid dimensions, >= 98 percent cell accuracy
- L2: grid spacing within 2 percent, >= 90 percent cell accuracy
- Confidence populated for every stage, and confidence must be lower on L2 than L0

If a threshold is unreachable after real effort, record actual numbers in KNOWN_ISSUES.md and continue. Do not silently lower thresholds in the tests.

## Phase 6 (stretch): real photos

Check reference/ for photos. If any exist, run the pipeline on them, save recovered models and rendered diffs, and document per-stage confidence and failure modes. If reference/ is empty, spend the time on L3 robustness instead and report results the same way.

## Final deliverables

- Repo per the design doc layout, all gated tests green
- README.md: what QREP is, install, CLI walkthrough using the benchmark fixture end to end
- KNOWN_ISSUES.md: honest failures and dead ends
- REPORT.md: per-phase status, per-CV-stage confidence and accuracy numbers, the three construction plans' metrics for the benchmark side by side, and a prioritized next-steps list

Quality bar: a quilter with the generated PDF and no other context could cut and assemble the benchmark quilt. Everything upstream serves that.
