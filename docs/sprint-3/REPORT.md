# QREP Sprint 3 report - real-photo robustness

Generated 2026-07-10 during slice S9 from fresh runs on the release commit;
no number below is quoted from memory. Sprint 3 made the photo flow honest:
it recovers quilts from real photos, and where it cannot, it says so instead
of presenting a confident wrong answer. Slices S0-S9 landed as issues
#66-#75 via PRs #78-#88.

## Slice status

| Slice | Issue | Landed | Theme |
| ----- | ----- | ------ | ----- |
| S0 photoreal foundations, UI-SPEC, thresholds proposed | #66 | PR #78 | fixtures + wasm gate + T1/T2/T3 |
| S1 tiered detection | #67 | PR #79 | four-tier quilt-region cascade |
| S2 crop screen | #68 | PR #80 | pins before analysis, cold-start contract |
| S3 grid guards | #69 | PR #81 | honest-failure floors below T1 |
| S4 image repeats, voting, verdict contract | #70 | PR #83 | the verdict tree (council-repaired) |
| S5 palette lighting, border robustness | #71 | PR #84 | closes sprint 1's #33 |
| S6 size engine | #72 | PR #85 | reconcile math, presets, provenance |
| S7 size UI | #73 | PR #87 | chips, in/cm entry, the size story |
| S8 honest results messaging | #74 | PR #88 | failure panels, verdict copy |
| S9 release 0.3.0 | #75 | this slice | CHANGELOG, README, REPORT, version |

Frozen thresholds (proposed by S0, frozen by Jake on the parent issue before
S1, never edited to force a pass): T1 = 0.60 grid-confidence floor,
T2 = 0.45 image-level periodicity floor, T3 = 1.05 intra-cell coherence
ceiling. INTEGER_RATIO_EPSILON = 0.15, cm rule eighths = round(cm*8/2.54).

## Test status (fresh, release commit)

- Native pytest: 411 passed, 1 skipped (subprocess test unavailable under
  the harness), ruff clean. The sprint 1 L0-L2 legacy regression pins are
  byte-intact.
- Web vitest: 249 passed across 15 files (verdictStory 9 red-first, verdict
  copy-audit 39, plus the release version-sync check that now covers
  pyproject, qrep.__version__, and web/package.json together).
- Playwright e2e: 48 passed against the rebuilt 0.3.0 bundle, including the
  new solid-fabric failure-flow spec.
- Cross-runtime: the full native suite runs under the pinned Pyodide 0.28.3
  runtime in the CI pyodide-tests job on every push; sprint 3 added no
  wasm-only divergence and no KNOWN_ISSUES entry. The authoritative
  cross-runtime count for this release is the pyodide-tests job on the S9
  merge to main.

## Honest verdicts over the photoreal corpus (fresh sweep, 1400px fixtures)

Each fixture run through the real pipeline; grid is the grid-stage
confidence, compared against T1 = 0.60.

| Fixture | Verdict | Diagnosis | grid |
| ------- | ------- | --------- | ---- |
| render_on_wood | readable | - | 0.963 |
| tall_chrome | readable | - | 0.904 |
| white_border_on_white | readable | - | 0.904 |
| edge_to_edge | readable | - | 0.867 |
| render_on_white | readable | - | 0.847 |
| screenshot_composite | readable | - | 0.831 |
| fabric_print | readable | - | 0.820 |
| low_contrast_hst | non_square_repeat | - | 0.751 |
| drunkards_path | non_square_repeat | - | 0.733 |
| seam_shadows | readable | - | 0.731 |
| lighting_gradient | readable | - | 0.680 |
| hst_star | non_square_repeat | - | 0.657 |
| render_perspective_jpeg | no_grid | anisotropic_pitch | 0.500 |
| busy_print_squares | no_grid | weak_periodicity | 0.295 |
| solid_fabric | no_grid | no_periodicity | 0.000 |

The three failure classes each land on a structured diagnosis rather than a
false read: a steep-angle photo (anisotropic_pitch), a busy print with no
readable square lattice (weak_periodicity), and a plain solid rectangle with
no quilt at all (no_periodicity). The three non-square quilts (half-square
triangles, drunkard's path curves) are flagged as blocks-that-repeat with a
squares approximation offered behind a disclosure, not silently mis-read.

## Field photos (real shop photos, local-photo smoke, gitignored corpus)

The three rights-unclean field photos that motivated the sprint, re-run for
real on the release commit. All three now answer honestly:

| Photo | Verdict | Diagnosis | grid | palette |
| ----- | ------- | --------- | ---- | ------- |
| image0.jpg | no_grid | anisotropic_pitch | 0.190 | k=2 @ 0.879 |
| IMG_4461.png | no_grid | anisotropic_pitch | 0.240 | k=2 @ 0.900 |
| IMG_4462.png | no_grid | anisotropic_pitch | 0.175 | k=2 @ 0.934 |

Each lands on the S8 failure panel with the steep-angle reason. Their k=2
palettes clear the frozen trust gate (confidence >= 0.80, 2 <= k <= 6), so
"Start in the editor" keeps the recovered fabrics on a blank grid - the
designed use of the escape.

## Known issues added in sprint 3

None promoted to xfail (guarded by tests/test_known_issues_audit.py). Two
discovered-work issues are logged for future sprints, neither a regression:
- #82: verdict coverage gaps at specific operating points (from the S4
  council sweep).
- #86: full metric (cm) display for rulers, the editor, and exports (S7
  scoped cm to entry only; the model and outputs stay inches).

## Sprint mechanics of note

- The S4 verdict wall was resolved by an adversarial council: the measurement
  lens proved the hst_star failure was a one-pixel lag-rounding artifact, not
  a true ceiling, overturning an incorrect self-diagnosis before a threshold
  was touched.
- Every threshold literal named above is frozen; git history confirms no
  golden file changed outside a [bless] commit (none were needed this sprint).
