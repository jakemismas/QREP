# QREP Sprint 1 report

Generated 2026-07-08 during slice S9 from fresh runs (commands in issue #12);
no number below is quoted from memory or an earlier log.

## Slice status

| Slice | Issue | Status | Landed |
| ----- | ----- | ------ | ------ |
| S0 scaffolding, packaging, CI | #3 | closed | PR #26 |
| S1 model, JSON round trip, fixture | #4 | closed | PR #27 |
| S2 construction engine | #5 | closed | PR #28 |
| S3 text exports + CLI | #6 | closed | PR #29 |
| S4 SVG diagrams + PDF booklet | #7 | closed | PR #30 |
| S5 sizing viewer | #8 | closed | PR #31 |
| S6 synthetic renderer L0-L3 | #9 | closed | PR #32 |
| S7 CV pipeline + harness | #10 | closed | PR #34 (adversarial council reviewed) |
| S8 stretch: L3 robustness | #11 | closed | PR #35 (report-only) |
| S9 docs, REPORT, sweep | #12 | this slice | |
| S10 release v0.1.0 | #23 | pending | |

Test suite at S9: 130 passed, 0 xfail, ruff clean. Goldens: blessed once per
artifact in [bless] commits (03fc779 cut list, 0365463 top SVG), frozen since;
git log confirms only [bless] commits touch tests/golden/.

## Construction strategies, benchmark fixture (fresh run)

| Metric | historical | strip | modern |
| ------ | ---------- | ----- | ------ |
| Pieces in top | 2479 | 2479 | 997 |
| Cut operations | 2488 | 633 | 1006 |
| Seams | 2487 | 607 | 1005 |
| Strip sets | 0 | 25 physical (5 distinct) | 0 |
| Waste | 2.3% | 3.3% | 3.0% |
| Bias edges | 0.0% | 0.0% | 0.0% |
| Difficulty (rough heuristic) | 56 | 16 | 24 |
| Time est. min (rough heuristic) | 3718 | 3968 | 1496 |
| Blue / cream / backing yardage | 4.0 / 4.25 / 5.5 yd | 4.25 / 4.5 / 5.5 yd | 3.5 / 3.5 / 5.5 yd |

All three plans reconcile to the identical finished-top area (432000
eighths^2 = exactly 75" x 90"), asserted in tests.

## CV round trip, benchmark fixture at seed 42 (fresh harness run)

Pipeline receives the image path alone; contractual thresholds in
parentheses.

| Level | Recovered dims | Cell accuracy | rectify | palette | grid | cells | repeat | border |
| ----- | -------------- | ------------- | ------- | ------- | ---- | ----- | ------ | ------ |
| L0 clean | 55x45 exact | 1.0000 (== 1.0) | 1.000 | 1.000 | 0.965 | 1.000 | 1.000 | 1.000 |
| L1 texture | 55x45 exact | 1.0000 (>= 0.98) | 1.000 | 0.923 | 0.766 | 0.943 | 1.000 | 1.000 |
| L2 perspective | 55x45 exact | 1.0000 (>= 0.90) | 0.989 | 0.897 | 0.812 | 0.918 | 1.000 | 1.000 |
| L3 folds/clutter/occlusion | 55x45 exact | 0.0028 (report-only) | 1.000 | 0.869 | 0.755 | 0.879 | 0.995 | 1.000 |

L2 also holds grid spacing error at 0.80% / 0.43% (<= 2% both axes) and finds
its non-identity homography unaided. Repeat detection recovers the 10x10
block period at L0-L2; fabric count is exactly 2 at L0/L1.

L3 is ungraded by contract. The interior dims are exact even under occlusion
(the S8 trimmed-uniformity border fix), and the accuracy collapse is a single
identified mechanism: with a third occluder color cluster, the greedy
bijective palette mapping lets the occluder claim blue's slot and the whole
assignment inverts. Full failure-mode analysis with hypotheses:
[docs/stretch/NOTES.md](docs/stretch/NOTES.md).

## Known issues

Zero xfail markers in the suite; KNOWN_ISSUES.md has no entries. Measured
limitations are tracked on issue #33 (off-oracle robustness: systematic pitch
alternation, lighting-driven k inflation, border widths at non-default render
scales, greedy mapping at k > 2).

## Prioritized next steps

1. Minimum-cost k-permutation palette mapping (#33): the single change the
   L3 evidence says buys the most accuracy, now that dims survive occlusion.
2. Host the sizing viewer + demo artifacts on GitHub Pages (#25) so testing
   needs only a link.
3. Vision robustness batch (#33): clutter-tolerant quad selection,
   lighting-normalized palette, scale-invariant border refinement.
4. Web UI editor on the same JSON contract (#22), then the backlog features
   (#15-#21): pieced borders, stitch detection, applique regions, colorway
   generator, reference-object absolute scale, machine formats, multi-image
   fusion.
