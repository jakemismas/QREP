# S8 stretch notes: L3 robustness (report-only)

Branch taken: **L3 robustness**. `reference/` contains no images (README.md
only), so the harness ran at L3 (fold shading, background clutter, one corner
occlusion) with seeds 42, 7, 99. Renders produced in-session by the S6
renderer; the pipeline received the image path alone. No gating thresholds
apply to any number below; honest measurement is the deliverable.

## Baseline measurements (pipeline as landed by S7)

| Seed | Recovered dims | Cell accuracy | k | Identity | Pitch px | Repeat | Border strips (L/R/T/B) |
| ---- | -------------- | ------------- | - | -------- | -------- | ------ | ----------------------- |
| 42 | 58x48 (want 55x45) | 0.3180 | 3 | yes | 15.02 / 15.00 | 10x10 | 3/0/0/3 |
| 7 | 58x48 | 0.1903 | 3 | yes | 15.03 / 15.00 | 10x10 | 0/3/0/3 |
| 99 | 143x80 | 0.0283 | 4 | no (spurious warp) | 10.22 / 6.53 | 1x1 | 0/0/0/0 |

Per-stage confidence (baseline):

| Seed | rectify | palette | grid | cells | repeat | border |
| ---- | ------- | ------- | ---- | ----- | ------ | ------ |
| 42 | 1.000 | 0.869 | 0.755 | 0.879 | 0.951 | 1.000 |
| 7 | 1.000 | 0.888 | 0.711 | 0.901 | 0.951 | 1.000 |
| 99 | 0.931 | 0.879 | 0.316 | 0.883 | 0.821 | 1.000 |

Confidence honesty check: grid confidence correctly collapses on the seed-99
wreck (0.32) and the repeat confidence drops with it; border confidence is
overconfident everywhere (reports 1.0 while missing half the strips), which
is itself a finding (mode 4).

## Failure modes and hypotheses

1. **Corner occlusion breaks border-strip uniformity.** Seeds 42/7 found
   border strips on only two of four sides, so interior exclusion was wrong
   (58x48) and every downstream comparison misaligned. Hypothesis: the
   occluder rectangle sits on the outermost strips of its two sides and
   drags their modal-fabric fraction below the 0.93 uniformity bar.
2. **Background clutter merges into the quilt silhouette.** Seed 99 detected
   a quad spanning quilt plus clutter, warped the wrong region, and the grid
   collapsed (pitch 10.2/6.5, repeat 1x1, accuracy 0.03). Hypothesis: the
   largest-contour selection plus morphological close bridges clutter
   rectangles that touch the quilt boundary in the margin ring.
3. **Occluder color steals a palette cluster.** k=3 (seeds 42/7) or 4
   (seed 99): silhouette legitimately prefers separating the occluder color,
   and the bijective greedy mapping then wastes a fabric slot. Hypothesis:
   palette masking excludes background but nothing excludes ON-quilt
   foreign objects.
4. **Greedy mapping order is fragile at k>2.** With the occluder cluster
   darkest, greedy (recovered order, nearest unused truth fabric) lets the
   occluder claim blue's slot; real blue then maps to cream and accuracy
   inverts. Hypothesis: greedy is fine for k=2 (its design premise) but k>2
   needs a global minimum-cost assignment over the k! permutations.
5. (Positive finding) **Fold shading is benign.** Pitch 15.0 and repeat
   10x10 survive folds at seeds 42/7; the Lab median per cell absorbs the
   0.8-1.0 luminance bands.

## The one improvement attempt (timeboxed, per contract)

Target: mode 1, the dominant structural failure. Change: the border scan's
uniformity became a TRIMMED modal fraction (up to 15 percent of a strip may
be occluded or noisy). All 129 earlier tests stay green; the L0/L1 border
criteria of S7 are unaffected (their strips are fully uniform; the fixture's
worst interior row/col reaches only 0.71 trimmed vs the 0.93 bar).

| Seed | Dims after | Accuracy after | What changed |
| ---- | ---------- | -------------- | ------------ |
| 42 | 55x45 (exact) | 0.0028 | border exclusion fixed; mode 4 now dominates |
| 7 | 55x45 (exact) | 0.0028 | same |
| 99 | 143x78 | 0.0182 | unchanged in kind (mode 2 dominates) |

Honest reading: the attempt FIXED the targeted mode (interior dims now exact
on occluded renders) and thereby unmasked mode 4, whose inverted mapping
costs more accuracy than the misalignment did. Per the one-attempt rule the
change stays (it is structurally correct and diagnostically strictly
better), the numbers stand as measured, and mode 4 is the top v2 lead:
with dims already exact, a k-permutation minimum-cost palette mapping alone
should recover most of the lost accuracy. Recorded on issue #33.

## Reproduction

```
.venv/Scripts/python -m pytest tests/test_l3.py -q
```

renders L3 seed 42 fresh, runs the pipeline, and records accuracy to
`tests/fixtures/_generated/l3_accuracy.txt` (no threshold, run-to-completion
only). The three-seed tables above were produced the same way with seeds
42/7/99.
