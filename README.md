# QREP

[![CI](https://github.com/jakemismas/QREP/actions/workflows/ci.yml/badge.svg)](https://github.com/jakemismas/QREP/actions/workflows/ci.yml)

QREP (Quilt Reverse Engineering Platform) is an open-source Python library and
CLI that reverse engineers quilts from photographs into production-ready
patterns: cut lists, yardage, strip-piecing plans, SVG diagrams, a PDF pattern
booklet, and an interactive sizing viewer.

All lengths live as integer eighths of an inch, so pattern math is exact and
every export is deterministic. Computer-vision results carry per-stage and
per-cell confidence scores; hand-authored data is always 1.0. The benchmark
quilt is a two-fabric Double Irish Chain (75" x 90").

## Install

```
git clone https://github.com/jakemismas/QREP.git
cd QREP
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

Python 3.12+ (3.12 and 3.13 are tested in CI). On macOS/Linux the venv paths
are `.venv/bin/...`. The commands below assume the venv is on PATH.

## Walkthrough: the benchmark quilt end to end

Every command below was executed verbatim against this repo during Sprint 1
(see issue #12 for the run log). The benchmark model is committed at
`tests/fixtures/double_irish_chain.json`.

Validate the model:

```
qrep validate tests/fixtures/double_irish_chain.json
```

```
OK: Double Irish Chain 75x90 is valid (55x45 cells, 2 fabrics)
```

Plan construction with any of the three strategies (`historical`, `strip`,
`modern`) and compare their metrics:

```
qrep plan tests/fixtures/double_irish_chain.json --strategy strip
qrep plan tests/fixtures/double_irish_chain.json --strategy strip -o plan.json
```

```
strategy: strip
pieces in top: 2479
cut operations: 633
seams: 607
strip sets: 25 physical (5 distinct)
waste: 3.3%
bias edges: 0.0%
difficulty: 16 (rough heuristic)
time estimate: 3968 min (rough heuristic)
yardage - Chain blue (b): 4.25 yd
yardage - Background cream (c): 4.5 yd
yardage - backing, any 42-inch WOF fabric: 5.5 yd
```

Export the full pattern set (cut list markdown + CSV, yardage report, SVG
diagrams with inch rulers, PDF booklet):

```
qrep export tests/fixtures/double_irish_chain.json --strategy strip --out dist/
```

Emit the sizing viewer, a single self-contained HTML file quilters can open
from disk, resize with live rulers (proportion lock on or off), and copy the
adjusted settings back out of:

```
qrep view tests/fixtures/double_irish_chain.json -o viewer.html
```

Render a synthetic photo of the quilt and reverse it back into a model. The
recovered JSON carries real confidence scores; `qrep compare` shows the
round trip side by side:

```
qrep render tests/fixtures/double_irish_chain.json --level 0 --seed 42 -o render_l0.png
qrep reverse render_l0.png -o recovered.json
qrep compare tests/fixtures/double_irish_chain.json recovered.json
```

```
grid dims: truth 55x45 vs recovered 55x45 (MATCH)
cell accuracy: 1.0000 over 2475 cells
palette mapping: f0 -> b, f1 -> c
stage confidence (truth | recovered):
  rectify: 1.0000 | 1.0000
  palette: 1.0000 | 1.0000
  grid: 1.0000 | 0.9647
  cells: 1.0000 | 1.0000
  repeat: 1.0000 | 1.0000
  border: 1.0000 | 1.0000
```

Difficulty levels 0-3 add texture noise, perspective + lighting, and
folds/clutter/occlusion; see [REPORT.md](REPORT.md) for measured accuracy per
level. Absolute scale is unknowable from a single photo, so the recovered
cell size is a labeled low-confidence guess you correct with one edit (or the
viewer).

## Project shape

- `qrep/model` pydantic schema, integer-eighths units, benchmark fixture
- `qrep/construct` three construction strategies plus metrics and yardage
- `qrep/export` cut list, yardage, SVG diagrams, PDF booklet
- `qrep/viewer` the static sizing viewer emitter
- `qrep/render` seeded synthetic renderer (the CV test oracle), levels L0-L3
- `qrep/vision` rectify, palette, grid, cells, repeats, borders, compare

Design decisions live in [qrep-design-doc.md](qrep-design-doc.md); sprint
status and measured numbers in [REPORT.md](REPORT.md); known limitations in
[KNOWN_ISSUES.md](KNOWN_ISSUES.md) and issue
[#33](https://github.com/jakemismas/QREP/issues/33). MIT license.
