# Sprint 4 decisions

Decision log for sprint 4, written in S0 (issue #92). Each entry records a
decision, its rationale, and the evidence behind it, so later slices and
sprints do not relitigate them. The binding contract is
docs/sprint-4/qrep-sprint-4-plan.md; this file records the council verdicts
and the S0 measurements that support them.

## D1. Corroboration branch over metric swap (council verdict)

Decision: the block-lattice evidence is admitted through a NEW additive
corroboration leg (a keyword-only `corroboration` parameter on
`decide_verdict`, and a per-axis `period_hint` admissibility gate in
`estimate_grid`), NOT by recomputing or bending any frozen confidence metric
under a frozen threshold.

Rationale: the council's two prominence-recompute proposals were refuted by
measurement — at the corroborated Irish-chain pitch, BOTH existing confidence
metrics still miss the T1 = 0.60 floor (binarized prominence ~0.47, raw
`_lattice_prominence` ~0.46). Any design that "adopts the pitch and prominence
then clears T1" is false. The additive leg adds new evidence inputs rather
than editing a metric under a frozen threshold, and is bounded by the
absence-identity property test (`corroboration=None` is byte-identical to
today).

Consequence: T1/T2/T3 and the L0-L2 byte-pins stay frozen. The single blessed
edit to verdict.py is the additive keyword-only parameter.

## D2. Crop-aware downscale deferred (contingency, not scope)

Decision: crop-aware downscale (crop to the quilt, then downscale, so a small
quilt region keeps its pixels) is DEFERRED this sprint. The frozen sigma
ladder is the phone-cap fix in scope.

Rationale: the ladder's fine rung recovers a ~20 px block that a single fixed
detrend sigma collapses (S0 `quarter_circle_fine` composite: block SNR ~5.0 at
both caps). The named contingency trigger is: if S0's phone-cap re-measurement
shows the ladder cannot hold the mill wheel above the proposed T4, crop-aware
is promoted to a fast-follow issue.

S0 finding (see the #91 baseline report): the three FIELD screenshots read at
tier-3 full frame (rectify does not isolate the quilt from the chrome), so
their block SNR on the full frame is weak (Irish 2.44, star 2.72, mill wheel
3.05) — at or below any T4 that cleanly separates the composite populations.
The corroboration MECHANISM is validated on the well-cropped composites; the
field screenshots need crop-aware to benefit. This is the crop-aware
contingency evidence; the promotion call is Jake's at freeze.

## D3. Mean cell confidence does not reject the 2-color garbage (S0 measurement)

Decision: exit (a)'s garbage rejection rests on the block-lattice SNR floor
(T4) AND the integer-lock's "block period >= 1D pitch" requirement, NOT on
mean cell confidence. T5 is a rescue-QUALITY floor, not the garbage
discriminator.

Rationale: measured, the median-based cell operator assigns HIGH confidence to
any locally-uniform two-tone content, so the 2-color garbage control reads
mean cell confidence ~0.997 — higher than the Irish chain (composite ~0.92,
field ~0.77). Mean cell confidence therefore cannot separate garbage from
squares. The garbage IS separated decisively by T4 (garbage SNR <= 2.69 vs
squares-rescue >= 3.85) and by the integer-lock (garbage block period ~7 px <
its 1D pitch ~20 px, so "block >= pitch" fails). Per the literal S0 gate,
"cannot separate on mean cell confidence" means exit (a) does not ship; the
baseline report presents this to Jake with the SNR/lock separation and a
recommendation. The exit-(a) ship decision is Jake's at freeze.

## D4. WOF assumption (default)

Decision: KEEP usable fabric width at 42 in in the yardage math and STATE it
in the document's assumptions block (default; zero golden churn). The switch
to 40 in (market convention) touches the yardage goldens and, if Jake flips
the #91 WOF checkbox, lands as a dedicated `[bless]` yardage-golden commit in
S3.

## D5. Five downloads retire; engine exporters stay (RETIREMENT RULE)

Decision: the five per-artifact download buttons in the web `PatternPanel`
(PDF booklet, cutlist CSV, cutlist MD, yardage, SVG) retire in S4, replaced by
one "Pattern document · PDF". The engine exporters (`qrep/export/*`), the CLI
surface, and `test_exports` stay as the developer surface.

Rationale: market evidence (8 pattern PDFs across 5 publishers, plus
designer-canon sources) converges on ONE consolidated pattern document;
QREP's five separate files match no shipped pattern's shape.

## D6. Document conventions (this sprint)

US Letter only (A4 deferred); coloring page in; 1-inch calibration square +
print-at-100% note on the cover; generated-name cover in. A4 variant and a
fabric-labels page are recorded fast-follow candidates, not this sprint.
