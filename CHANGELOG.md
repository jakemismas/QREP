# Changelog

All notable changes to QREP are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project uses
semantic-ish versioning where each minor release is a sprint.

## [0.3.0] - 2026-07-10 - Real-photo robustness

Sprint 3. The photo flow stops pretending. When QREP cannot read a quilt it
says so, says why, and offers a real next step; when it can, the recovered
model is honest about its own uncertainty and about size. Slices S0-S9
landed as issues #66-#75 via PRs #78-#88. The v1 engine's byte-frozen
legacy behavior is unchanged.

### Added

- Tiered quilt detection: a four-tier cascade (legacy #404040 verbatim,
  border-sample MAD, grabCut with dominant-inlier ring seeding, full-frame
  fallback) recovers the quilt region from real photos with chrome,
  backgrounds, and wood, not just clean synthetic renders.
- Crop screen: draggable corner pins render immediately on drop with no
  engine on the critical path; the detected quad snaps in unless you have
  already moved a pin. "Adjust the crop" from results returns here seeded
  with the confirmed quad.
- Honest verdicts: every result carries a verdict (readable,
  readable_no_repeat, non_square_repeat, no_grid) computed from grid
  confidence, image-level periodicity, and intra-cell coherence against
  frozen thresholds (T1=0.60, T2=0.45, T3=1.05). A no_grid failure shows
  what could not be read and why, drops the confidence percentage, and
  offers Adjust the crop / photo tips / a blank-grid start; the wrong
  reading stays available behind a labeled disclosure.
- Non-square piecing is flagged rather than silently mis-read as squares:
  triangles-and-curves quilts get an approximation behind a disclosure and
  an honest "blocks repeat - squares uncertain" label.
- Real sizes: an optional size block with preset chips (Crib through King),
  inch and centimeter entry (cm converts at entry via
  eighths = round(cm * 8 / 2.54); the model stays integer eighths), a
  single-match preset suggestion that never silently prefills as fact, and
  a tappable results size line with an inline editor.
- Image-level repeat detection, confidence-weighted plurality voting for
  ambiguous squares, and integer-ratio pitch feedback.
- Palette lighting normalization (multiplicative flat-fielding from a
  quadratic illumination fit on linear grayscale, trusted crops only) so a
  bright window no longer inflates the fabric count.
- Photoreal fixture corpus (15 rights-clean synthetic photos across
  chrome, wood, perspective, lighting, low contrast, non-square piecing,
  and solid fabric) with a metrics harness, plus a wasm-parity gate and a
  local-photo smoke script for rights-unclean field photos.

### Changed

- Finished-size reconcile derives cell size per axis from the entered
  finished dimensions and reports achieved-vs-requested instead of
  silently rounding; clamps never error.
- Overall pill is selected by verdict first, then the sprint 2
  mean-of-stages percentage; a failure verdict shows no number.

### Fixed

- Off-oracle robustness gaps from sprint 1's issue #33 (systematic pitch
  alternation, lighting-driven palette-k inflation, non-default-scale
  border widths); #33 closed by slice S5.

## [0.2.0] - 2026-07-09 - QREP Web

The engine that passed sprint 1's suite runs unchanged in the browser: photo
to editable pattern, fully client-side on a pinned, self-hosted Pyodide
0.28.3, with the browser's cut-list downloads byte-identical to the native
goldens. Slices landed as issues #40-#47.

## [0.1.0] - 2026-07-08 - Engine

First release. Reverse engineers grid quilts from photographs into
production-ready patterns (cut lists, yardage, strip-piecing plans, SVG
diagrams, PDF booklet) and proves the architecture on the benchmark Double
Irish Chain. Every CV-derived value carries a confidence score; all lengths
are exact integer eighths of an inch.

[0.3.0]: https://github.com/jakemismas/QREP/releases/tag/v0.3.0
[0.2.0]: https://github.com/jakemismas/QREP/releases/tag/v0.2.0
[0.1.0]: https://github.com/jakemismas/QREP/releases/tag/v0.1.0
