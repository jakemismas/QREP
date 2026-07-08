# QREP Design and Tech Doc

## What this is

Design decisions for the Quilt Reverse Engineering Platform v1. The companion build prompt (qrep-claude-code-prompt.md) implements this doc. Anything not in here is out of scope for the overnight run. Work is tracked as GitHub Issues in jakemismas/QREP; the slice issues are the operational contract and derive from these two docs. Where CLAUDE.md's Environment section conflicts with a stack pin here, CLAUDE.md wins.

## Core thesis

The system splits cleanly in half. The back half (quilt model, construction strategies, pattern outputs) needs zero computer vision and is fully testable with hand-authored data. The front half (photo to model) is research-grade risky. Build back-to-front so the run produces a working pattern generator even if seam inference stalls. Validate CV with synthetic round-trip testing: render images from the model, run them through the pipeline, confirm the model is recovered.

## Stack (decided, not optional)

- Python >= 3.12 (the build machine runs 3.13.3; use it; CI matrix tests 3.12 and 3.13). Library plus CLI (typer).
- pydantic >= 2.9 for the model and JSON serialization
- numpy, opencv-python-headless, scikit-image for vision. Never opencv-python: the headless wheel avoids GUI deps.
- Pillow for the synthetic renderer
- svgwrite for diagrams (archived but stable; mitigate with the determinism rules below); reportlab for the PDF booklet. weasyprint is banned: it needs GTK native libs that do not install on this Windows box.
- pytest, ruff, pypdf (dev, for PDF structure tests)
- Packaging: pyproject.toml, hatchling backend, flat layout (packages = ["qrep"]), requires-python >= 3.12, console script qrep = "qrep.cli:app", [dev] extra. MIT license. GitHub Actions CI on ubuntu-latest, matrix 3.12/3.13: pip install -e .[dev], ruff check ., pytest.
- All work through the repo venv interpreter explicitly: `.venv/Scripts/python -m pip ...`, `.venv/Scripts/python -m pytest`, `.venv/Scripts/python -m ruff check .`. Never rely on shell activation persisting between tool calls; never install into system Python.

## Units (load-bearing)

All lengths are stored internally and in JSON as integer eighths of an inch. 1.5" = 12, 0.25" = 2, 3.75" = 30. One shared formatter renders mixed fractions (`2 1/2"`) for every human-facing export. This makes JSON round-trip equality exact and golden files byte-stable; float inch arithmetic is forbidden in the model and exports.

## Interfaces in v1

- CLI and JSON editing are the primary interfaces. No manual editing tools.
- One bounded exception to the no-GUI rule: the sizing viewer, a single static HTML file (vanilla JS, no framework, no server, no build step) that loads a quilt JSON, renders the quilt top with inch rulers on the x and y axes, and re-renders live when the user changes finished width, height, or cell size inputs. View plus sizing only: no cell editing, no fabric picking, no persistence beyond copying adjusted values back into the JSON. Anything beyond that is future UI and out of scope.

### CLI signatures (pinned; the README walkthrough is written against these)

```
qrep validate quilt.json
qrep plan quilt.json --strategy historical|strip|modern -o plan.json
qrep export quilt.json --strategy strip --out dist/ [--formats cutlist,yardage,svg,pdf]   # default all
qrep render quilt.json --level 0..3 --seed 42 --scale 10 -o out.png
qrep reverse img.png -o recovered.json [--corners x1,y1,...,x4,y4] [--fabrics N]
qrep view quilt.json -o viewer.html
```

## Quilt model

Quilt contains: metadata, palette, regions, quilting layer, settings, provenance.

- Regions: center field, zero or more border bands, binding. v1 implements one region type, a rectilinear Grid (rows, cols, cell finished size, cell fabric ids). The region abstraction is the extension point for non-grid quilts later.
- Palette: named fabrics with hex color. Fabric assignment is by id so recoloring is one edit.
- Confidence lives in two places, not a schema-wide generic wrapper: (a) `provenance.stage_confidence`, a per-stage dict (rectify, palette, grid, cells, repeat, border), and (b) a per-cell confidence array alongside the cell fabric ids. Hand-authored models omit both (defaults 1.0). The CV pipeline populates real values using the formulas in the CV section.
- Absolute scale is unknowable from a single photo. The reverse pipeline recovers grid structure and proportions and emits cell size as a low-confidence guess; the user corrects finished size with one JSON edit (or the sizing viewer) and all downstream math recomputes.
- Quilting layer exists in the schema (motif regions, density), authored only, renders on diagrams. No stitch detection in v1.
- JSON is the one project format. `schema_version` is the string "1"; the loader raises a clear error on missing or unknown major version. No DXF in v1. The JSON model plus true-to-scale SVG exports are the future integration surface (DXF/longarm, cutter formats, EQ8); do not build those now.

## Benchmark fixture (exact geometry; do not re-derive)

Two-fabric Double Irish Chain, light blue chain (b) on cream (c). The traditional pattern uses three fabrics; this collapses dark and medium into blue, which is legitimate — say so in the fixture docstring so nobody researches variants mid-run.

- Finished cell 1.5" (cut 2.0"). Block = 5x5 cells = 7.5".
- Center field: 9 x 11 blocks (both odd, Block A on all four corners) = 45 x 55 cells = 67.5" x 82.5".
- One plain cream border, 3.75" finished, all four sides. Finished top: exactly 75" x 90". Binding: blue, 2.5" strips, length = perimeter 330" + 10" = 340".
- Block A rows, top to bottom: `bbcbb / bbbbb / cbbbc / bbbbb / bbcbb` (21 blue, 4 cream). NOT a plain checkerboard — a checkerboard has no diagonal blue adjacency into Block B and the continuity test would fail.
- Block B: cream with a blue corner square in each corner: `bcccb / ccccc / ccccc / ccccc / bcccb` (4 blue, 21 cream).
- Cell census (50 A + 49 B blocks): 1246 blue, 1229 cream, total 2475 center cells. Border and backing cream-side; binding blue.
- Connectivity: for a horizontally adjacent A|B pair, A local cell (3,4) is blue, B local cell (4,0) is blue, diagonally adjacent (likewise (1,4) and (0,0)). The continuity test asserts a diagonal blue-blue pair across every A-to-B boundary and that a main diagonal of blue cells is 8-connected end to end.
- The fixture is generated by `qrep.model.fixtures.make_double_irish_chain(...)` (2475 ids are not hand-typed), serialized once to `tests/fixtures/double_irish_chain.json`, committed; a test regenerates and compares. The fixture module docstring carries an ASCII rendering of one A/B pair and the continuity test asserts the same coordinates the ASCII shows.

## Construction engine

A strategy is a pure function: Model in, ConstructionPlan out. Deterministic, no state. Running the same strategy on the same model twice yields equal serialized plans.

ConstructionPlan contains: cut list, strip sets with subcut instructions, assembly steps, metrics.

1. Historical: patch by patch, replicates the grid literally.
2. Strip piecing: strip sets are built from width-of-fabric (WOF) strips at BLOCK granularity, never full quilt rows (a 45-cell row would need a 90" strip; WOF is 42"). Detect the distinct 5-cell row sequences per block type: Block A has {bbcbb, bbbbb, cbbbc} (rows 0=4, 1=3), Block B has {bcccb, ccccc}, so five distinct strip sets exist. Each strip set = 5 WOF strips (2.0" cut) sewn in sequence, crosscut at 2.0" yielding floor(42/2) = 21 segments per set; sets needed = ceil(required_segments / 21). A row-signature approach is sufficient; do not build a general sequence miner.
3. Modern optimized: merge same-fabric adjacent cells into larger cut pieces where no seam is visually required (Block B's cream interior becomes a few large pieces instead of 21 squares).

FPP, EPP, hand piecing, and longarm are stubbed behind the same interface, raising NotImplementedError with a human-readable message.

Assembly steps are hierarchical: piece blocks, join blocks into rows (11), join rows, add border, bind — roughly 25 block-level numbered steps, never per-cell steps.

### Metrics (defined, so the comparison tests mean something)

- piece count: pieces in the finished top
- cut count: rotary-cut operations (WOF strips + crosscut segments for strip plans; one per piece for historical/modern)
- seam count: seams sewn
- strip set count
- waste = (purchased area - cut piece area) / purchased area
- bias percent = fraction of cut edges not parallel to grain; 0.0 for all v1 rectilinear strategies (hardcoded with a comment)
- difficulty = round(log10(piece count) + seams per square foot); time = pieces x 1.5 min + strip-set ops x 10 min. Both carry the label "rough heuristic" in the data model and every output.

Plans agree on FINISHED area: the sum of finished piece areas in every plan equals the quilt-top area exactly (integer eighths make this exact). Cut areas legitimately differ across strategies and are reported in metrics, never asserted equal.

## Math defaults (all overridable in settings)

- Seam allowance 1/4", cut size = finished size + 1/2"
- Usable width of fabric 42"
- Binding: 2.5" strips, length = perimeter + 10"
- Backing: a dedicated yardage line item ("backing, any 42-inch WOF fabric"), never taken from the palette fabrics: panels = ceil((width + 8) / 42), yards = panels x (height + 8) / 36, rounded up to the next 1/4 yard. Fixture: ceil(83/42) = 2 panels x 98" = 196" ≈ 5.5 yd.
- Yardage rounds up to the nearest 1/4 yard per fabric.

## Determinism and the golden-file protocol

- Every stochastic effect draws from numpy.random.default_rng(seed) with an explicit seed (default 42). Call cv2.setRNGSeed(42) immediately before cv2.kmeans. Same seed, same bytes.
- Exports are deterministic: sorted iteration, fixed float formatting for SVG coordinates ({:.3f}), \n newlines, no timestamps, no random ids. Exporting twice yields byte-identical files.
- Golden tests read tests/golden/. Running `pytest --bless` (a conftest flag) writes current output there; a missing golden without --bless FAILS the test with "run --bless". Bless protocol: generate once, verify independently (cut-list totals cross-checked against plan metrics; SVG parsed and cell count/colors asserted programmatically), commit in a commit whose message contains [bless], then frozen for the sprint. Never pass --bless again without a stated reason in the commit message.
- PDF is structure-tested via pypdf (section presence, content reconciliation), never byte-tested: reportlab embeds timestamps.
- .gitattributes forces `* text=auto eol=lf` plus explicit rules for *.svg, *.csv, *.md, *.json. Without this, Windows autocrlf silently breaks byte-compared goldens on Linux CI. Load-bearing.
- Rendered PNGs for tests are generated at test time into tests/fixtures/_generated/ (gitignored), never committed, never hand-edited.

## Synthetic renderer

Model to PNG, the test oracle for the CV pipeline. Seeded-deterministic; takes `seed` (default 42) and `scale` (default 10 px per finished inch; fixture quilt = 750x900 px plus margin, 15-px cells).

- Every level renders the quilt on a background margin of 8 percent of the long side, filled with constant #404040 (guaranteed absent from any palette). Corner detection therefore always has a boundary to find.
- L0: clean orthographic, flat colors, Pillow rectangle fills, no antialiasing
- L1: fabric texture noise, per-patch color variance (seeded)
- L2: perspective homography via Image.transform(PERSPECTIVE, resample=BILINEAR), corners pulled inward 3 to 6 percent of width (seeded, bounded), plus lighting gradient
- L3: mild fold shading, background clutter, partial occlusion
- The renderer exposes ground truth for the harness: a sidecar JSON with true corner coordinates, seed, and level. Sidecars are diagnostics for the harness comparison only; the pipeline under test never reads them.

## CV pipeline (v1, single image)

1. Rectification: detect the quilt-background quad. If the detected quad deviates from an axis-aligned rectangle by less than 1 percent of image size, skip warping (identity homography, confidence 1.0) — the identity path is exercised by the L0 test. User-supplied corners are a CLI escape hatch for real photos only; round-trip tests call the pipeline with the image path alone.
2. Palette extraction: k-means in Lab on pixels inside the rectified quilt quad only (background excluded). k chosen by scanning k in [2, 8] and maximizing mean silhouette in Lab (subsample <= 20k pixels). KMEANS_PP_CENTERS, attempts=10, RNG seeded.
3. Grid estimation: edge projections plus autocorrelation for spacing and offset.
4. Cell fabric assignment: median cell color in Lab to nearest palette entry.
5. Repeat detection: 2D autocorrelation on the fabric-id grid to find block size.
6. Border detection: margin rows and columns that break grid periodicity. Note the fixture border is 2.5 cell-pitches wide by design (non-integer) — that IS the periodicity break; do not "fix" it.
7. Emit model with per-stage confidence.

### Confidence formulas

- rectify = 1 - normalized corner-fit residual, scaled down by warp magnitude (identity = 1.0, so L2 < L0 is structural, not a tie risk)
- palette = mean silhouette score
- grid = autocorrelation peak prominence (normalized)
- cells = mean margin between nearest and second-nearest palette distance
- The L2-vs-L0 comparison test asserts min(stage_confidence.values()) is strictly lower on L2.

### Round-trip accuracy definitions

- Recovered palette entries map to ground-truth fabrics by nearest Lab distance (bijective; greedy is fine for k=2).
- Cell accuracy = correct cells / 2475 over the center-field grid only. "Grid dimensions" means the interior field (45x55) after excluding detected border margins.
- At L0/L1 a dimension mismatch fails the test outright. At L2, if dimensions mismatch, accuracy is computed over the overlapping top-left-aligned region and the deviation is reported.
- Grid spacing error = |recovered cell pitch - true pitch| / true pitch in the rectified image, both axes.
- The L2 test asserts rectification found a non-identity homography itself (no ground-truth corners fed in).

Explicitly out of scope for v1: multi-image fusion, folded or partial quilts, stitch detection, applique, non-grid piecing, absolute scale recovery from reference objects.

## Diagram conventions

- The full quilt top SVG carries inch rulers along the top (x) and left (y) edges: labeled major ticks every 5", minor ticks every 1", extents matching the model's computed finished dimensions. Rulers show finished dimensions only; cut dimensions live in the cut list.
- SVG diagrams are true to scale at a fixed px-per-inch factor.

## Testing strategy

- Unit tests on construction math with hand-computed expected values written step-by-step in comments. Expected values flow one way: hand computation to assertion, never observed output to assertion (except through the bless step, once).
- Round-trip tests: author model, render at L0 through L2 with fixed seeds inside the test session, reverse, compare per the accuracy definitions above with per-level thresholds.
- Golden files for the SVG top diagram and cut list, per the bless protocol.
- PDF booklet built from a list of section objects unit-tested pre-render (cutting lists both fabrics with nonzero quantities; strip-set section >= 5 sets; assembly >= 10 numbered steps; yardage includes binding and backing lines), plus a pypdf smoke test for section titles.

## Build order (one slice = one GitHub issue, strictly in order)

- S0 scaffolding: venv, pyproject, package skeleton, CI, .gitattributes, import-smoke test
- S1 model, JSON round trip, benchmark fixture
- S2 construction strategies and metrics
- S3 text exports (cut list, yardage) and CLI (validate, plan, export)
- S4 visual exports: SVG diagrams with rulers, PDF booklet
- S5 sizing viewer (static HTML, live rulers)
- S6 synthetic renderer, L0 through L3
- S7 CV pipeline validated against synthetic images, L0 through L2
- S8 stretch: real photos if reference/ has any, otherwise L3 robustness (report-only, no gating thresholds, timeboxed)
- S9 docs: README walkthrough, REPORT.md, KNOWN_ISSUES sweep, packaging honesty check

Each slice gates on green tests (pytest and ruff locally, CI green on main for the previous slice). A gate is satisfied when all tests pass OR each failing test is marked xfail(reason="KNOWN_ISSUES: <entry>", strict=False) with a matching KNOWN_ISSUES.md entry recording actual numbers, permitted only after 3 documented distinct attempts. Never delete or weaken an assertion. Each slice lands as a branch plus PR with Fixes #N; direct pushes to main are blocked by policy.

## Repo layout

```
qrep/
  model/        # schema, serialization, fixtures API
  construct/    # strategy interface, three strategies, metrics
  export/       # cutlist, yardage, svg, pdf booklet
  render/       # synthetic renderer, difficulty levels
  vision/       # rectify, palette, grid, repeats, borders
  viewer/       # static HTML sizing viewer template + emit logic
  cli.py        # validate, plan, export, render, reverse, view
tests/
  fixtures/     # authored quilts; _generated/ for test-time renders (gitignored)
  golden/       # blessed golden files (frozen after bless)
reference/      # optional real photos (gitignored); outputs to reference/out/ (gitignored)
docs/           # stretch notes, future design docs
.github/workflows/ci.yml
pyproject.toml
```

The two governing docs (this file and the build prompt) stay at repo root. REPORT.md and KNOWN_ISSUES.md live at root.

## Known risks

- Seam inference on low-contrast solids is genuinely hard. Mitigation: palette-first grid approach, honest confidence reporting, document-and-move-on instead of thrashing.
- The PDF booklet invites scope creep. It assembles the existing exports into sections. It is not a layout engine.
- The sizing viewer invites scope creep harder than the PDF does. It is one static file with three numeric inputs and rulers. It is not the future web app.
- Grid-only v1 cannot represent the long tail of quilts. The region abstraction is the promise that it can later. Do not build non-grid support now.
- Golden files authored on Windows and compared on Linux CI diverge on line endings, dict ordering, and float repr unless the determinism rules are followed exactly.
