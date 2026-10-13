# B1a: count suggestions and the tap-one-square seed

Spike for issue #134 (plan ticket B1a). It measures whether QREP can suggest the square counts
of a confirmed field well enough for B7 to build, and records the go or no-go.

The run header, the exact command, the resolved qrep path, the git SHA and the cv2 version are
in the generated section at the end of this file and in `B1a-count-suggestions.json`, which
holds every number below with its n.

## Decision

No count method and no tap seed ships in B7. 0.4.0 ships typed counts, steppers and the fit
check, and scope does not change (plan section 10, risk 2).

The rule (issue #134, criterion 6): a method ships when its top-3 recall on the in-scope dev
photos is at least 0.8 and the exp2 fit score rejects every wrong top-1 it produced.

- No method clears both parts at any radius (0 to 8 px), on either staging cap (phone 1400 px,
  desktop 2000 px), against either proposal pass (proposed-a, proposed-b).
- Only the two fit methods reach a top-3 recall of 0.8: at 0 px (9 of 11) and 2 px on both
  caps and both passes (best: fit, phone, proposed-a, 182 of 220, 0.827), and at 4 px on the
  desktop cap only (0.809 and 0.814). Every one of those rows fails the fit rule. At 2 px the fit method's 73 wrong top-1s score up to 14.01,
  while the true counts score as low as 1.40 on the same trials, so no single threshold passes
  every truth and rejects every wrong top-1. Even the per-trial reading fails: 13 of the 73
  wrong top-1s score below their own trial's truth. A fit-ranked suggestion is by construction
  the candidate the fit likes best, so the fit check cannot catch it.
- The tap seed reaches a top-3 recall of at most 0.27 (3 of 11, at 0 px).
- Truth is proposals only. The two passes agree on the counts of all 11 photos; neither is
  verified-jake yet (D3b). The decision is provisional on that, but the margins are wide:
  the closest method misses the fit rule by an order of magnitude, not by a borderline.

Functions from the modules B6b deletes that a shipping method needs: none, because no method
ships. For reference, the functions each measured method calls are listed under
`b6b_functions` in the JSON: the autocorrelation and tap methods use
`qrep.vision.grid._find_pitch`, `_autocorrelate`, `_binarize` and `MIN_PITCH_PX`, and the
quilter units use `qrep.vision.repeats.detect_repeat` and its `_axis_period`.

## Results (phone cap, proposed-a frames, joint top-3 recall)

Each nonzero radius has 20 trials on each of the 11 photos (n = 220), and 0 px has one (n = 11).
Trials within a photo are correlated, so the effective n is closer to 11. Wilson 95 percent
intervals and the desktop and proposed-b rows are in the generated tables.

| Method | 0 px | 2 px | 4 px | 6 px | 8 px |
|---|---|---|---|---|---|
| autocorr | 0.45 (5/11) | 0.56 (124/220) | 0.55 (121/220) | 0.55 (121/220) | 0.56 (124/220) |
| seam | 0.73 (8/11) | 0.70 (155/220) | 0.61 (134/220) | 0.52 (114/220) | 0.48 (106/220) |
| fit | 0.818 (9/11) | 0.827 (182/220) | 0.795 (175/220) | 0.71 (157/220) | 0.68 (149/220) |
| fit_interior | 0.818 (9/11) | 0.818 (180/220) | 0.791 (174/220) | 0.68 (150/220) | 0.66 (145/220) |
| tap | 0.27 (3/11) | 0.18 (40/220) | 0.16 (35/220) | 0.15 (34/220) | 0.13 (28/220) |

Periodic against non-periodic quilts at 2 px (top-1 and top-3, then harmonic top-1s). A quilt
is periodic when its proposed counts have more than one block on an axis: 6 photos (n = 120)
against 5 (n = 100).

| Method | Periodic top-1 | Periodic top-3 | Periodic harmonic | Non-periodic top-1 | Non-periodic top-3 | Non-periodic harmonic |
|---|---|---|---|---|---|---|
| autocorr | 34/120 | 44/120 | 19/120 | 60/100 | 80/100 | 0/100 |
| seam | 0/120 | 65/120 | 115/120 | 85/100 | 90/100 | 0/100 |
| fit | 47/120 | 82/120 | 70/120 | 100/100 | 100/100 | 0/100 |
| fit_interior | 43/120 | 80/120 | 70/120 | 100/100 | 100/100 | 0/100 |
| tap | 8/120 | 13/120 | 13/120 | 11/100 | 27/100 | 0/100 |

What the numbers say:

- The failure is the block period. On the 5 non-periodic quilts the fit ranks the true count
  first in 100 of 100 trials at 2 px; on the 6 periodic quilts 70 of its 73 wrong top-1s are
  harmonics, chiefly block counts (lacma-54904 reads 10 x 10 blocks for 50 x 50 squares; smithsonian-saam-2017-24-5 reads
  5 x 6 for 45 x 54). Block seams are the strongest edges, and with an odd number of squares per
  block a block's centre lands inside a flat square, which every centre-based score rewards.
- The seam-energy scorer almost never ranks the true count first on a periodic quilt: 0 of 120
  at every radius on the phone cap, and at most 2 of 120 on the desktop cap. That reproduces
  exp9 (0 of 37 on image0) on museum photos.
- Tier B: n = 0. Its 28 dev photos carry no count proposals yet, and its 12 holdout photos are
  never read.
- Harmonic alternates as chips: at 0 px the fit's 4 wrong top-1s include the truth among the
  listed alternates (divisors, double and triple) on 2 photos (lacma-63229, 11 for 22;
  smithsonian-saam-2017-24-27, 7 for 21). The other 2 need a multiple by the squares per block
  (x5, x9), which the alternates do not list.
- Quilter units: where a method's top-1 is right at 0 px, the units from the block period
  match the proposal's blocks x squares on 5 of 7 (fit), 4 of 5 (autocorr) and 5 of 5 (seam).
  A mismatch is an equally valid split, such as an Irish chain's 10-square repeat against the
  proposal's 5-square blocks.

## For other tickets

- B3 (grid-fit check): on these museum photos the exp2 reconstruction scores wrong block-count
  harmonics (divisors by 3, 5 and 9 as well as by 2) above many true counts, so G3's simulated
  miscounts (one off, half and double) miss the most common real error. B3 may want divisors by
  the squares per block in its ROC. This is a reconstruction of exp2, not its code.
- C3 and B7: no suggestion ships, so nothing to build. The non-periodic result suggests a later
  design where the user types blocks per axis and the engine suggests squares per block; that
  is an observation for Jake, not a scope change.

## Method

Inputs: `corpus/manifest.csv` rows of tiers A and B, minus the holdout (the corpus README's
rule, applied through `qrep_eval.annotation.in_holdout` before any image is read). Only tier A
carries count proposals: 11 dev photos, all museum scans, decoded with cv2 from the main
checkout's private cache.

For each photo and each proposal pass (proposed-a, proposed-b), using that pass's own field
corners and counts:

1. Stage the photo as plan section 2.1 does: crop to the outer frame plus a 5 percent margin at
   full resolution, then cap the long side at 1400 px (phone) or 2000 px (desktop), the caps in
   `web/src/model/downscale.ts`.
2. Move each field corner by the radius (0, 2, 4, 6 or 8 px, plan section 7.2) in its own
   random direction, seeded per photo, pass, cap and radius.
3. Warp the field to a rectangle whose sides are the means of opposite edges.
4. Rank candidate square counts per axis (4 up to extent / 5 px) with each method, then pair
   the axes by rank sum under a square-grid prior (the two pitches within 15 percent; the 11
   photos' proposed-a pitches agree within 7.8 percent). Score the top 3 pairs against the
   proposed counts.

The methods:

- autocorr: the existing detector's period (`qrep.vision.grid._find_pitch` on the gray Sobel
  projection, as `estimate_grid` builds it); count = extent / pitch, then other counts by the
  autocorrelation at their pitch.
- seam: the mean color edge energy (L*0.5, a, b) on the N - 1 seams a count N implies. A
  reconstruction of exp9 from its public description; the prototype's code is not in the repo.
- fit: exp2's score reconstructed from plan sections 1.2 and B3: the seam-to-centre edge ratio
  times a chroma homogeneity gain, the within-square chroma mean absolute deviation of squares
  shifted half a pitch over that of aligned squares (so the pitch size cancels).
- fit_interior: fit with each square's whole inner 70 percent standing in for its centre
  point. Added after run 1, to test whether block counts win because one centre sample misses
  the seams inside a block; it changes little.
- tap: one tap at a random square's proposed centre, moved by the same radius. The 4-connected
  region of the tapped fabric bounds the pitch (half to twice its size), the local window's
  autocorrelation sets it (sub-pixel, averaged over harmonics), and the counts are the nearest
  integer and its two neighbours.
- The fit rule uses the whole-field exp2 reconstruction of each pair (`fit_2d`), with its two
  raw parts (seam-to-centre ratio, median within-square chroma deviation) kept in the JSON.

Every knob is a named constant with its source at the top of `scripts/eval/spikes/b1a_counts.py`.
The scoring helpers and the methods have hand-worked tests in `tests/eval/test_b1a_scoring.py`.

## Run history

- Run 1 at 0717fe6: same photos, radii and caps. autocorr, seam and fit gave exactly the numbers
  above (the trials are seeded). The tap then bracketed the square by the nearest edge peaks,
  and print texture inside squares made those brackets too narrow: top-3 recall on the phone
  cap with proposed-a frames was 3/11, 52/220, 44/220, 53/220 and 45/220 at 0 to 8 px. Neither
  tap version comes near the bar.
- Run 2 at the SHA in the header: the region-bounded tap and fit_interior added, as committed
  in 6db8573.

## Limits

- n = 11 photos, all museum scans; no phone capture and no screenshot. Trials within a photo
  are correlated.
- Truth is proposed, not verified (D3b).
- exp2 and exp9 are reconstructions from their public descriptions.
- The crop margin, the candidate floor of 4, the 15 percent prior and the tap's tolerance are
  spike choices, named in the script.

<!-- Generated by scripts/eval/spikes/b1a_counts.py below this line. -->
