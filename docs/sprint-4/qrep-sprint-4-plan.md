# QREP Sprint 4 plan: read real quilts, ship one real pattern, work on the phone

Status: v1, APPROVED 2026-07-10 (Jake, conditional on full coverage of the
reported bugs and requests; coverage cross-check recorded on parent #91).
Produced from docs/sprint-4/RESEARCH.md (10-agent fleet + 4 local spikes)
and a 3-proposer design council with judge (angles: simplest-that-ships,
most-robust-on-invariants, most-faithful-to-docs; judge synthesis is the
corroborated-grid contract below). This doc is the sprint contract; the
parent issue (#91) and the S0-S6 sub-issues (#92-#98) are created from the
slice sections below, and docs/sprint-4/ORCHESTRATOR.md carries the run
loop. Read together with qrep-design-doc.md,
docs/sprint-2/qrep-web-design-doc.md, and the sprint 2/3 PARITY docs; where
they conflict, this doc wins for sprint 4 scope only.

## Why this sprint

Three real failures from Jake's live phone walkthrough (2026-07-10), each
reproduced and diagnosed with instrumentation this week:

1. Real quilts read as no_grid even when the pipeline has the answer. The
   Irish chain field photo yields the CORRECT pitch (18.2, 17.7 px) and a
   visually correct 49x49 cell recovery (mean cell confidence 0.770), then
   refuses at grid confidence 0.472 < T1 = 0.60. The Old Mill Wheel
   (quarter circles) and star quilt (triangles) fail earlier: 1D projection
   pitch detection locks garbage (anisotropic 32.3/13.4; 7 px texture) and
   the anisotropy message wrongly blames a "steep angle". A measured
   peak-contrast 2D statistic certifies the true lattice on all three
   (SNR 2.16-5.44 vs 0.05/0.00 negatives) - the signal exists; the
   detector's 1D front end and single confidence leg lose it.
2. Results offer five separate downloads (PDF booklet, cutlist CSV, cutlist
   MD, yardage report, SVG). Market evidence (8 pattern PDFs read
   page-by-page across 5 publishers; designer-canon sources) says quilters
   expect ONE consolidated pattern document: cover-only page 1 with photo,
   name, and size; materials page 2; assumptions block; cutting chart;
   assembly with inline figures; layout diagram; finishing; and (near
   universal in modern listings) a coloring page. QREP's five files match
   no shipped pattern's shape.
3. The results lightbox's side-by-side compare is broken on iOS (issue
   #90): fixed-overlay + centered-flex + 78vh sizing meets iOS toolbar
   dynamics (and the unresolved iOS 26 fixed-position regression, WebKit
   297779); on any phone the two 84vw panels wrap unlabeled. Sprint 3's
   e2e ran desktop-only, which is why this shipped.

Sprint theme: the honest pipeline sprint 3 built starts SAYING YES to real
quilts it can actually read, and its output becomes a document a quilter
recognizes, on the device they actually use.

## Research and spike summary

Full detail in docs/sprint-4/RESEARCH.md (verdict table is the scope
authority; its Adopt-now rows map to slices below, with one council
override noted). Spike headlines the plan relies on:

- Peak-contrast lattice evidence (2D FFT autocorr, best Lab channel,
  harmonics k=1..3, min over axes, peak SNR over local background):
  field photos + passing fixtures 2.16-5.44; solid 0.05; noise 0.00.
- Phone 1400 px cap: Irish chain 3.13 and star 6.10 (stronger); mill
  wheel collapses to 0.00 under the FIXED detrend sigma - the statistic
  must sweep detrend scale (frozen sigma ladder).
- busy_print INVERSION: texture 22 px SNR 3.49 > true 92 px lattice 0.95.
  SNR certifies lattice PRESENCE; it cannot select nested lattices. #82
  stays open; every gate below is designed so this inversion cannot leak.
- THE DECISIVE NEGATIVE: at the corroborated Irish-chain pitch, BOTH
  existing confidence metrics miss the floor (binarized 0.472/0.496; raw
  _lattice_prominence 0.461/0.454 vs T1 = 0.60). Any design claiming
  "feedback adopts the pitch and prominence then clears T1" is refuted by
  measurement. The council's two prominence-recompute routes died on this
  fact; the surviving contract adds a new corroboration leg instead of
  bending a frozen one.
- Council override of one research verdict: crop-aware downscale
  (downscale after crop) is DEFERRED this sprint; the sigma ladder is the
  phone-cap fix. If S0's phone-cap re-measurement shows the ladder cannot
  hold the mill wheel above the proposed T4, crop-aware downscale is the
  named contingency and rides as a fast-follow issue, not scope creep.

## The corroborated-grid contract (single definition, owned by S1 + S2)

Judge-synthesized; verified against grid.py/verdict.py/pipeline.py/cells.py
mechanics before adoption.

- New detector `block_lattice_snr(image_bgr)` in qrep/vision/repeats.py:
  normalized 2D autocorrelation of the high-passed best Lab channel over a
  FROZEN scale-swept sigma ladder (max SNR across sigmas); per axis, the
  fundamental's peak SNR over its local non-peak background, averaged over
  harmonics k=1..3; statistic = min over axes; returns (period_x,
  period_y, snr). Runs ONLY when the 1D read is failing (min-axis
  binarized prominence < T1) - structurally inert on every passing
  fixture, including busy_print (its 1D read passes at the 92 px block).
- Pitch adoption: the block period feeds the EXISTING
  `_apply_period_feedback` via period_hint, admitted per axis inside
  estimate_grid only if (axis 1D prominence < T1) AND (snr >= T4) AND
  (block_period >= 1D pitch). The healthy-photo hint path
  (image_periodicity score >= T2) is byte-untouched and takes precedence.
- Corroboration branch, ADDITIVE inside decide_verdict's no_grid arm: new
  keyword-only parameter `corroboration=None`; when None the function is
  byte-identical (absence-identity property test). Grid stage confidence
  is NEVER inflated - 0.472 stays recorded; the branch adds new evidence
  inputs rather than editing any metric under a frozen threshold. Two
  exits:
  (a) Readable rescue: min-axis snr >= T4, AND per-axis integer lock of
      block period to the adopted pitch within the frozen
      INTEGER_RATIO_EPSILON = 0.15 (Irish chain locks at k = 2:
      37/18.2 = 2.03, 36/17.7 = 2.03), AND mean cell confidence >= T5.
      On pass, evaluation falls through the REMAINING frozen tree (T2/T3
      branches decide readable vs readable_no_repeat vs
      non_square_repeat) - one tree shape, no parallel logic.
  (b) Block-structure rescue: min-axis snr >= T4 AND intra-cell coherence
      measured ON THE SNR-DERIVED BLOCK LATTICE > T3 ->
      non_square_repeat. No T5 - this exit claims repeat structure, not
      cell readability.
  Neither exit -> no_grid unchanged.
- Diagnosis and copy: new grid_diagnosis string `non_square_content`
  emitted when a coarse block lattice exists but the read stays failed or
  routes via exit (b); the anisotropic "steep angle" copy fires only on
  genuine skew (no coarse block found). VERDICTS enum unchanged; the four
  verdicts stand.
- Negative controls, each pinned forever: solid (SNR 0.05) and noise
  (0.00) die at T4; busy_print never enters (1D passes); a degraded
  busy_print variant must additionally fail block_period >= pitch, the
  integer lock, or T5; a synthetic 2-color garbage image is the T5
  make-or-break control - if S0 cannot separate it from the Irish chain
  on mean cell confidence, exit (a) DOES NOT SHIP and the Irish chain
  honestly stays no_grid this sprint (consequence stated: the motivating
  squares quilt stays unreadable; the sprint still ships exit (b), the
  message fix, the document, and the phone fix).
- Property tests locking the branch: absence-identity (corroboration=None
  byte-identical across a threshold-straddling sweep + L0-L2 pins);
  end-to-end inertness (every currently-passing fixture produces
  corroboration=None); backdoor-lock (exit (b) reaches only
  {no_grid, non_square_repeat}; each exit-(a) gate independently negated
  returns no_grid); negative-control verdict pins; wasm parity gate for
  the new op (lags exact, SNR abs-tol, wall-time and memory at both caps).

Expected field outcomes, stated with their conditions: Irish chain ->
readable via exit (a) if T5 freezes; mill wheel -> non_square_repeat via
exit (b) IF its block-lattice coherence measures > T3, else no_grid with
truthful non_square_content copy; star -> non_square_repeat via exit (b)
under the same condition. All SNR populations are RE-MEASURED under the
frozen ladder at both caps in S0 before T4/T5 are proposed; the spike
numbers above are evidence the approach works, not the freeze values.

## Scope

In scope: the slices below - detector evidence + corroborated verdicts,
the consolidated pattern document (with generated name, cover, photo
comparison page, coloring page, print conventions), the iOS lightbox
rebuild with mobile WebKit e2e (closes #90), and release 0.4.0.

Out of scope, recorded so the plan never argues with them again:
- Non-grid piecing in the model (curved/triangle templates): stays #17.
  Sprint 4 detects, reports, and approximates behind the existing
  disclosure; it does not represent.
- Busy-print nested-lattice pitch selection: stays #82 (the spike proves
  SNR alone inverts on it; needs a cell-coherence selection mechanism).
- Crop-aware downscale: deferred per council; named contingency in S0.
- Overlay slider compare on phones; A4 document variant; fabric
  labels/tags page: fast-follow candidates, not this sprint.
- Reference-object absolute scale (#19), multi-image fusion (#21),
  stitch detection (#16): unchanged.

## Hard rules (carried forward, plus sprint 4 additions)

All sprint 2/3 rules stand: TDD with hand-computed expectations, frozen
goldens ([bless]-only), PR-per-slice with Fixes #N, no AI attribution,
engine-authoritative numbers, PARITY vocabulary, honest failure is a
feature, rights-clean committed fixtures, hands-off manual smoke policy
(local-photos smoke posted in PROGRESS comments; findings become new
issues, never reopened slices), six-stage confidence schema gains no new
stages (new CV sub-scores live in diagnostics), Pyodide parity spikes for
any new cv2 surface.

Sprint 4 additions, each traceable to a sprint 3 failure or a council
finding:

- NEW-LITERAL RITE, EXTENDED. T4 (block-lattice SNR floor, proposed 1.5),
  T5 (mean-cell-confidence floor, proposed ~0.70), and the sigma ladder
  are proposed by S0's baseline report with measured populations over
  passing fixtures, the degraded corpus, the field photos (desktop AND
  phone cap), and every negative control, then frozen by Jake via
  parent-issue checkbox BEFORE S1 starts. After freeze they are as
  immutable as T1-T3. One freeze comment on the parent issue; any
  pre-freeze change supersedes by a comment naming the prior one
  (sprint 3's 0.62 wobble is the lesson).
- FROZEN-FILE AMENDMENT BLESSING. decide_verdict's additive keyword-only
  parameter edits a function whose docstring declares the tree frozen.
  The approval checkbox below explicitly blesses this ONE additive edit,
  bounded by the absence-identity property test. No other edit to
  verdict.py semantics is authorized.
- METRIC-UNDER-THRESHOLD VIGILANCE (from the council's decisive fact):
  any PR whose behavior depends on a confidence value near a frozen
  threshold must cite the S0-measured population in its body. A reviewer
  treats an unmeasured "this will clear the floor" claim as a major
  finding. Traceable to two council proposals refuted by measurement.
- MOBILE-WEBKIT LENS (from #90 shipping with desktop-only e2e): every UI
  slice runs its Playwright specs additionally on an iPhone-class WebKit
  emulation profile; a mobile-only failure is a major finding. The
  emulation profile is the automated gate; the physical-device pass
  stays a hands-off smoke ask.
- RETIREMENT RULE. A slice that supersedes a surface removes or migrates
  every registration of the old one. S4 retires the five per-artifact
  download buttons when the document ships (engine exporters remain as
  CLI/developer surface; the plan says so to keep test_exports intact).
- COUNCIL-PIN RULE. The four property tests of the corroboration contract
  are acceptance-criteria checkboxes on S1/S2 issues, not optional tests.

## Slices

Orders restart at 0; ids unique across the sprint; each slice is one PR,
landable by one chat.

| Slice | Issue | Theme |
| ----- | ----- | ----- |
| S0 | #92 | degraded corpus, evidence baseline, freeze rite, design bundle |
| S1 | #93 | block-lattice evidence detector |
| S2 | #94 | corroborated verdicts and honest curved-quilt messaging |
| S3 | #95 | pattern document engine: sections, cover, name |
| S4 | #96 | one download in the web app |
| S5 | #97 | mobile lightbox and compare (fixes #90) |
| S6 | #98 | release 0.4.0 |

### Slice 0: S0 degraded corpus, evidence baseline, freeze rite, design bundle

Goal: an evidence base measured on photo-degraded inputs and the frozen
literals the detector slices build against, plus the binding design
sections for the two new UI surfaces.

Ships:
- tests/fixtures/photoreal/ gains a DEGRADED tier (deterministic, seeded,
  generated once and committed as PNGs per the sprint 3 determinism
  spec): screenshot-degradation pipeline (JPEG quality sweep, downscale,
  re-upscale, mild gamma/contrast wash) applied to render_on_white, the
  drunkards_path and hst_star composites, and busy_print; plus a
  low-contrast antique-wash squares composite (the Irish chain class), a
  quarter-circle composite at ~20 px block pitch (the phone-cap mill
  wheel class), and a 2-color garbage control (random 2-tone blobs, no
  lattice). Both caps (1400/2000).
- scripts/local_photo_smoke.py extended to print block_lattice_snr,
  integer-ratio, mean cell confidence, and block-lattice coherence per
  photo (native only, hands-off policy unchanged).
- Baseline report as a parent-issue comment: the FULL population table
  (SNR under the frozen-candidate ladder, ratio locks, cell confidences,
  block coherences) over passing fixtures, degraded tier, field photos at
  both caps, and negative controls; proposes T4, T5, and the ladder with
  margins shown; names the 2-color-garbage separation verdict for exit
  (a); names the phone-cap mill wheel verdict for the crop-aware
  contingency.
- Wasm gate: Lab conversion + ladder autocorr op under Pyodide on
  committed fixtures, native-parity tolerances (lags exact, SNR abs-tol),
  wall-time and peak-memory acceptance at both caps.
- Design bundle: UI-SPEC sprint-4 sections + PARITY sprint-4 amendment
  skeleton for (1) the pattern-document panel (one download), (2) the
  mobile lightbox/compare, (3) non_square_content verdict copy, (4) the
  quilt-name display; committed before any UI slice starts.
- DECISIONS.md entries: council verdict (corroboration branch over
  metric swap; crop-aware deferral), WOF decision (below), retirement of
  the five downloads.

Gate rule: if the wasm gate cannot meet wall-time/memory after 3
documented APPROACH FAILED attempts, stop the sprint for a fallback
decision (named fallback: single-sigma detrend + crop-aware downscale
promoted from contingency to scope, with the phone-cap mill wheel
criterion moving to a follow-up issue).

Tests: degraded-tier regeneration matches committed pixels; metric
helpers on hand-built arrays; ladder op parity.
Manual smoke: none (headless).

### Slice 1: S1 block-lattice evidence detector

Goal: the peak-contrast statistic exists, is wasm-clean, and feeds the
existing pitch feedback only on failing axes.

Ships: block_lattice_snr in qrep/vision/repeats.py (frozen ladder,
best-Lab-channel, k=1..3, min-over-axes, per the contract); estimate_grid
gains the per-axis admissibility hint (prominence < T1 AND snr >= T4 AND
block_period >= pitch) feeding _apply_period_feedback unchanged;
diagnostics gains lattice_snr {period_px, snr, channel, sigma}; pipeline
wiring (compute beside image_periodicity, only when the 1D read is
failing).

Modules: qrep/vision/repeats.py, qrep/vision/grid.py (hint admissibility
only), qrep/vision/pipeline.py.
Tests: hand-computed SNR on tiny arrays; ladder recovers a 10 px-period
lattice at phone cap where a single sigma reads 0; inertness property
test (every passing fixture: hint never admitted, model byte-unchanged,
L0-L2 pins green); degraded-tier assertions per the S0 baseline; T4
imported, never inlined.
Manual smoke: local-photos smoke numbers posted in PROGRESS (native).

### Slice 2: S2 corroborated verdicts and honest curved-quilt messaging

Goal: the frozen tree accepts corroboration evidence additively; real
quilts land on the verdicts the baseline predicts; the steep-angle lie
stops.

Ships: CorroborationEvidence (pydantic) + decide_verdict's keyword-only
corroboration parameter with exits (a) and (b) exactly per the contract;
pipeline assembles the evidence (integer locks, mean cell confidence,
block-lattice coherence via coherence_with_sublattice on the SNR-derived
boundaries); grid_diagnosis non_square_content emitted per the contract;
web verdictStory copy for non_square_content ("The blocks repeat, but the
shapes inside are not squares...") + steep-angle copy now conditioned on
genuine skew; copy-audit and verdictStory tests updated red-first.

Modules: qrep/vision/verdict.py (the ONE blessed additive edit),
qrep/vision/pipeline.py, qrep/vision/repeats.py (block-lattice coherence
entry), web/src/model/verdictStory.ts + tests.
Tests: absence-identity sweep + L0-L2 pins; backdoor-lock property tests;
negative-control verdict pins (solid, noise, 2-color garbage, busy_print
and its degraded variant); degraded-tier end-to-end verdicts
(low-contrast squares -> readable when T5 shipped; quarter-circle ->
non_square_repeat or pinned honest fallback per S0's measured coherence);
decide_verdict hand-computed re-pins.
Manual smoke: the three shop photos' verdict lines posted in PROGRESS
(native); optional phone ask rides with S5.

### Slice 3: S3 pattern document engine: sections, cover, name

Goal: one build_document produces every section a quilter expects, with
the recovered quilt on the cover under a generated name.

Ships:
- qrep/export/naming.py: deterministic name generator - structure word
  from detected features (repeat/block vocabulary; Irish-chain/checker/
  patch classes from repeat period and cell stats) + mood word from
  palette Lab (word lists committed), seeded by a stable content hash of
  (cells, palette); collision-suffix hook for the web save layer. Name
  lands in QuiltMetadata.name (model default "Recovered quilt" replaced
  at reverse time; user-editable in the editor as today).
- qrep/export/pdf.py build_sections extended to the market-canon order:
  Cover (full-page recovered-quilt render, generated name, finished size,
  honest technique line "straight seams, squares only", QREP byline) /
  Your quilt vs the pattern (original photo beside the recovered render,
  verdict line, per-stage confidence table) / Fabrics (existing, plus
  swatch chips) / Assumptions block (seam allowance 1/4 in, WOF
  assumption AS DECIDED by the approval checkbox, finished-vs-cut note,
  abbreviations WOF/HST/RST) / Cutting (existing chart) / Strip sets /
  Assembly (existing steps + per-step block figures rendered from the
  model) / Borders / Binding / Finishing / Coloring page (blank line-art
  grid of the recovered quilt) / footer on every page: name, page number,
  "made with QREP from your photo", generation date; 1-inch calibration
  square + "print at 100%, US Letter" note on page 1.
- Figures: raster mini-renders from the model (render() and cell-paint
  helpers; reportlab Image flowables; no new deps, no svglib).
- bridge.export_document(model_json, strategy, photo_png_b64 or None,
  original_verdict_json or None) returning the PDF bytes envelope; CLI
  `qrep export --document` embedding the source photo when the reverse
  input path is available.
Modules: qrep/export/naming.py (new), qrep/export/pdf.py, qrep/bridge.py,
qrep/cli.py, qrep/render/renderer.py (helper reuse only).
Tests: name generator hand-computed on fixed inputs (same quilt -> same
name; palette shift -> mood word shift); build_sections content
assertions per section (structure, not PDF bytes) including cover fields,
assumptions literals, calibration-square presence; export_document
envelope; determinism (same inputs -> identical section models).
Manual smoke: open the generated PDF locally; eyeball cover, side-by-side
page, coloring page.

### Slice 4: S4 one download in the web app

Goal: the results/pattern surface offers exactly one document download,
carrying the user's photo into it, and the five per-artifact buttons
retire.

Ships: PatternPanel offers "Pattern document (PDF)" (plus print and
copy-my-settings, unchanged); the engine worker/rpc pass the session
photo bitmap (downscaled per the existing caps) and verdict diagnostics
into export_document; the five download buttons removed per the
retirement rule (engine exporters and their tests stay; PARITY amendment
records the surface change); download filename = generated name, kebab
case. Session-only photo contract holds: the photo goes into a PDF the
user explicitly downloads, never into storage.
Modules: web/src/shell/PatternPanel.tsx, web/src/engine/worker.ts,
web/src/shell/photoApi.ts, web/src/state/project.tsx (name plumbing),
PARITY sprint-4 amendment.
Tests: vitest panel tests red-first (one download control, testid
download-document); e2e photo flow through document download on desktop
AND the mobile WebKit profile; copy-audit for new strings; assert absence
of the retired testids.
Manual smoke: download on desktop + phone; open the PDF on the phone.

### Slice 5: S5 mobile lightbox and compare (fixes #90)

Goal: the compare surface works on an iPhone.

Ships: lightbox rebuilt per UI-SPEC sprint-4: dvh-based sizing with vh
fallback, top-anchored scrollable overlay (no centered-flex clipping),
body scroll lock while open, safe-area insets, labeled stacked compare
(Photo / Recovered quilt) on narrow viewports and true side-by-side when
both fit, tab bar always reachable; iOS 26 fixed-position mitigation
(anchor to the visual viewport; re-measure on visualViewport events).
Modules: web/src/shell/PhotoFlow.tsx (Lightbox + styles), UI-SPEC
sprint-4 section, e2e specs.
Tests: Playwright lightbox spec on desktop AND iPhone-class WebKit
emulation (open, switch all three tabs, scroll the stage, close via
scrim and via button, stacked labels present at phone width); vitest for
scroll-lock hook; existing desktop assertions unchanged.
Manual smoke (the #90 closer): on the physical iPhone against live
Pages - open compare from a real photo result, both panels visible and
scrollable, close works; record the observed pre-fix symptom on #90 for
the record.

### Slice 6: S6 release 0.4.0

Goal: the sprint lands as a coherent release with honest reporting.

Ships: CHANGELOG (one entry per slice, per-issue attribution), README
(document + phone story), docs/sprint-4/REPORT.md (fresh numbers: full
fixture + degraded-tier verdict sweep, the three field photos' verdicts
at both caps, T4/T5 freeze record), version 0.4.0 across pyproject,
qrep.__version__, web/package.json (version-sync test), Pages deploy
green, release tag with wheel + sdist.
Gate: kickoff requires every other sub-issue closed and the recorded
human smoke pass for S5 on the parent issue (a parent never closes over
open children).
Tests: full native + wasm suites green; e2e 48+ green including mobile
profile; version-sync.
Manual smoke: none beyond the S5 recorded pass.

## Universal Definition of Done (per slice)

- Native pytest green (including the new property/pin tests), ruff clean,
  web vitest + Playwright green where touched, pyodide-tests job green
  (zero wasm-only divergence tolerated without a KNOWN_ISSUES entry per
  the sprint 3 precedent).
- Hand-computed expectations only; no golden edits outside [bless] (none
  anticipated except the S0 degraded-tier bless and, only if the WOF
  checkbox flips to 40, the yardage goldens in their own [bless] commit).
- Adversarial review dry: no critical/major finding, all issue AC boxes
  ticked; UI slices screenshot-compared against the UI-SPEC sections on
  desktop AND the mobile profile.
- CHANGELOG updated; ARCHITECTURE/DECISIONS touched only via their
  disciplines; PR per slice, Fixes #N, author/committer Jake Mismas
  <jake@jakemismas.com>, no AI attribution; slice trailer per the
  sprint 3 convention.
- Sacred constraints re-asserted on any slice touching them: T1/T2/T3
  literals, the four-verdict enum, six-stage confidence schema, L0-L2
  byte-pins, session-only photo, PR-only landing.

## Approval checklist (Jake, before kickoff)

- [ ] Scope: the seven slices above are the sprint.
- [ ] Corroborated-grid contract approved, including the ONE blessed
      additive decide_verdict edit (absence-identity-bounded).
- [ ] T4/T5/sigma-ladder freeze procedure approved (S0 proposes with the
      population table; you freeze via checkbox before S1; exit (a) does
      not ship if the 2-color garbage control cannot be separated).
- [ ] Crop-aware downscale deferred, named as S0's contingency: approved.
- [ ] WOF decision: KEEP 42 in the math and STATE it in the document's
      assumptions block (default; zero golden churn), or SWITCH usable
      width to 40 (market convention; touches yardage goldens via a
      dedicated [bless] commit in S3). Default stands unless you check
      the switch.
- [ ] Downloads: the five per-artifact buttons retire in S4 (engine
      exporters and CLI stay): approved.
- [ ] Document conventions: US Letter only this sprint (A4 deferred),
      coloring page in, calibration square + print-at-100% note in,
      generated-name cover in: approved.

## Review upgrades in force this sprint

1. Mobile-WebKit lens on every UI slice (from #90 shipping with
   desktop-only e2e).
2. Degraded-reality corpus assertions on every pipeline slice (from the
   sprint 3 fixture corpus missing all three field failures).
3. Metric-under-threshold vigilance: population numbers or it did not
   happen (from two council proposals refuted by the 0.461 measurement).
4. Council property-pins as acceptance boxes, not optional tests (from
   the S4-sprint-3 precedent of the council catching a one-pixel artifact
   and this council catching the prominence gap).
5. Single-comment freeze discipline on the parent issue (from the
   sprint 3 T1 0.62 wobble).
