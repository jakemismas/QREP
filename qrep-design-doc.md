# QREP Design and Tech Doc

## What this is

Design decisions for the Quilt Reverse Engineering Platform v1. The companion Claude Code prompt implements this doc. Anything not in here is out of scope for the overnight run.

## Core thesis

The system splits cleanly in half. The back half (quilt model, construction strategies, pattern outputs) needs zero computer vision and is fully testable with hand-authored data. The front half (photo to model) is research-grade risky. Build back-to-front so the run produces a working pattern generator even if seam inference stalls. Validate CV with synthetic round-trip testing: render images from the model, run them through the pipeline, confirm the model is recovered.

## Stack

- Python 3.12, library plus CLI (typer). No GUI in v1. Editing means editing JSON or using the Python API.
- pydantic for the model and JSON serialization
- numpy, OpenCV, scikit-image for vision
- Pillow for the synthetic renderer
- svgwrite for diagrams, weasyprint or reportlab for the PDF booklet (agent's choice)
- pytest, ruff

## Quilt model

Quilt contains: metadata, palette, regions, quilting layer, settings.

- Regions: center field, zero or more border bands, binding. v1 implements one region type, a rectilinear Grid (rows, cols, cell finished size, cell fabric ids). The region abstraction is the extension point for non-grid quilts later.
- Palette: named fabrics with hex color. Fabric assignment is by id so recoloring is one edit.
- Every inferred attribute is wrapped as value plus confidence (0 to 1). Hand-authored data gets 1.0. The CV pipeline populates real confidences.
- Quilting layer exists in the schema (motif regions, density) but there is no stitch detection in v1. It can be authored manually and it renders on diagrams.
- JSON is the one project format, versioned with a schema_version field. No separate DXF or "project format" in v1.

## Construction engine

A strategy is a pure function: Model in, ConstructionPlan out. Deterministic, no state, trivially testable.

ConstructionPlan contains: cut list, strip sets with subcut instructions, assembly steps, metrics.

v1 ships three strategies:

1. Historical: patch by patch, replicates the grid literally.
2. Strip piecing: detect rows or columns whose fabric sequence repeats across the quilt, emit strip sets and subcuts. The Irish Chain is the canonical showcase for this.
3. Modern optimized: merge same-fabric adjacent cells into larger cut pieces where no seam is visually required (for example the mostly-plain alternate block in an Irish Chain becomes a few large pieces instead of 25 squares).

FPP, EPP, hand piecing, and longarm strategies are stubbed behind the same interface, not implemented.

Metrics per plan: piece count, cut count, seam count, strip set count, estimated fabric waste, bias percentage, difficulty score, rough time estimate. Difficulty and time are labeled heuristics, never presented as precise.

## Math defaults (all overridable in settings)

- Seam allowance 1/4 inch, cut size = finished size + 1/2 inch
- Usable width of fabric 42 inches
- Binding: 2.5 inch strips, length = perimeter + 10 inches
- Backing: quilt dimensions + 4 inches per side
- Yardage rounds up to the nearest 1/4 yard per fabric

## Synthetic renderer

Model to PNG at four difficulty levels. This is the test oracle for the CV pipeline.

- L0: clean orthographic, flat colors
- L1: fabric texture noise, per-patch color variance
- L2: perspective homography, lighting gradient
- L3: mild fold shading, background clutter, partial occlusion

## CV pipeline (v1, single image)

1. Rectification: detected or user-supplied corners, homography to orthographic
2. Palette extraction: k-means in Lab color space
3. Grid estimation: edge projections plus autocorrelation for spacing and offset
4. Cell fabric assignment: median cell color to nearest palette entry
5. Repeat detection: 2D autocorrelation on the fabric-id grid to find block size
6. Border detection: margin rows and columns that break grid periodicity
7. Emit model with per-stage confidence

Explicitly out of scope for v1: multi-image fusion, folded or partial quilts, quilting stitch detection, applique, non-grid piecing.

## Testing strategy

- Unit tests on construction math with hand-computed expected values in comments (yardage for a known grid, subcut counts, strip set detection on a synthetic fabric grid)
- Round-trip tests: author model, render at L0 through L2, run pipeline, compare recovered grid dimensions, palette, and cell assignments against ground truth with per-level pass thresholds
- Golden files for the SVG and cut list outputs of the benchmark fixture
- Benchmark fixture: a two-fabric Double Irish Chain (light blue chain on cream) hand-authored from pattern knowledge. The Tori Jones quilt photo is not required for v1. If a photo is available it drops into reference/ and activates the stretch phase.

## Build order

1. P1 model, JSON round trip, benchmark fixture
2. P2 construction strategies and metrics
3. P3 exports (cut list, yardage, SVG diagrams, PDF booklet)
4. P4 synthetic renderer
5. P5 CV pipeline validated against synthetic images
6. P6 stretch: real photo hardening if a photo exists, otherwise L3 robustness

Each phase gates on green tests before the next begins.

## Repo layout

```
qrep/
  model/        # schema, serialization, fixtures API
  construct/    # strategy interface, three strategies, metrics
  export/       # cutlist, yardage, svg, pdf booklet
  render/       # synthetic renderer, difficulty levels
  vision/       # rectify, palette, grid, repeats, borders
  cli.py        # validate, plan, export, render, reverse
tests/
  fixtures/     # authored quilts, rendered images, golden files
reference/      # optional real photos (gitignored if large)
docs/
```

## Known risks

- Seam inference on low-contrast solids is genuinely hard. Mitigation: palette-first grid approach, honest confidence reporting, and the rule that the agent documents a failing approach and moves on instead of thrashing.
- The PDF booklet invites scope creep. It assembles the existing exports into sections. It is not a layout engine.
- Grid-only v1 cannot represent the long tail of quilts. The region abstraction is the promise that it can later. Do not build non-grid support now.
