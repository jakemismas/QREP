# QREP Sprint 3 plan: real photos, honest answers, real sizes

Status: v3, APPROVED 2026-07-09. v1 was pressure-tested by a 10-lens
adversarial council plus judge (2026-07-09); verdict "plan-needs-revisions";
the 24 code-verified defects were folded into v2. Jake's approval answers
are folded into v3: inches PLUS cm entry, PRESETS reused verbatim, UI-SPEC
written in S0, and #33 pulled fully into the sprint (new slice S5). This
doc is the sprint contract; the parent issue and `S0:`-`S9:` sub-issues are
created from the slice sections below, and docs/sprint-3/ORCHESTRATOR.md is
generated on the sprint 2 skeleton. Read
together with qrep-design-doc.md and docs/sprint-2/qrep-web-design-doc.md;
where they conflict, this doc wins for sprint 3 scope only.

## Why this sprint

Sprint 2 shipped the web app, but the reverse pipeline still silently assumes
its own renderer's output. Three real-world failures drove this plan (all
reproduced from actual usage, 2026-07-09):

1. A screenshot or shop product photo of a quilt produces garbage. Root
   cause: qrep/vision/rectify.py pins the background to the renderer's
   #404040 (`BACKGROUND_BGR`). On a white product photo everything is
   "quilt", the crop swallows browser chrome, and downstream stages read
   noise. There is no crop step before analysis; corner pins exist only as a
   post-failure retry.
2. Real repeating quilts (Double Irish Chain product photo, star quilt with
   half-square triangles, Old Mill Wheel with quarter circles) come back as
   nonsense grids (13 x 43 from a square quilt). Root causes: repeat
   detection (qrep/vision/repeats.py) demands a 99.9% exact label match,
   satisfiable only by synthetic renders; grid estimation has no
   plausibility guards, so a harmonic or noise peak on one axis wins
   unchallenged; and nothing ever tells the user "this did not work" - the
   pipeline always emits a quilt, however absurd.
3. Finished size is a hardcoded guess (`ASSUMED_PPI = 10`,
   qrep/vision/pipeline.py). The user often KNOWS the size (standing in
   front of the quilt, or reading it off a listing: "86 x 67.5"). There is
   nowhere to enter it until the editor, and the predicted size shown on the
   results screen is fiction presented at low confidence rather than a
   prompt for the one fact the user can supply.

Sprint theme: make the photo path trustworthy on photos QREP did not render,
and make the pipeline say "I can't read this" instead of hallucinating.

## Research summary

### Auto-crop / quilt boundary detection

- The current largest-non-background-contour approach generalizes: estimate
  the background from the image's own border strips instead of assuming
  #404040. Council-hardened spec: per-strip median plus inlier fraction via
  MAD (raw variance mis-routes the L3 clutter renders), a cross-strip
  agreement gate (four individually-uniform strips that disagree, the
  chrome-barred screenshot case, route to GrabCut), and contour candidates
  ranked by area x squareness so a full-width chrome bar cannot win on area
  alone.
- For busy backgrounds (wood floor, bed, lawn), `cv2.grabCut` seeded with
  GC_INIT_WITH_MASK from the uniformity-passing strips is the classical
  escape hatch. Availability evidence: the vendored Pyodide wheel
  web/public/pyodide/opencv_python-4.11.0.86-*-wasm32.whl carries the cv2
  imgproc surface including grabCut (verified by symbol inspection during
  council review); the S0 spike proves it executes and performs. GrabCut
  runs on a detection-sized downscale (about 600 px longest edge) with the
  quad scaled back, and cv2.setRNGSeed precedes every call (its GMM init
  draws from the process-global RNG). Sources:
  [OpenCV GrabCut tutorial](https://docs.opencv.org/4.x/d8/d83/tutorial_grabcut.html),
  [PyImageSearch GrabCut guide](https://pyimagesearch.com/2020/07/27/opencv-grabcut-foreground-segmentation-and-extraction/).
- Document-scanner practice (detect a quad, let the user adjust corners,
  then warp) is the standard UX shape; classical detection is acceptable for
  a v1 crop proposal because the user confirms it. Sources:
  [LearnOpenCV document scanner](https://learnopencv.com/automatic-document-scanner-using-opencv/),
  [Scanbot edge-detection notes](https://scanbot.io/techblog/document-edge-detection-with-opencv/).
- Decision: tiered detection - legacy exact path, border-sample path,
  GrabCut fallback, full-image quad last resort - always shown as an
  adjustable crop BEFORE analysis.

### Repeat detection and non-square patterns

- Literature standard for near-regular textures: autocorrelation of the
  IMAGE (normalized cross-correlation, FFT-accelerated), peaks give the
  lattice; label-grid matching like ours is a special case that only works
  noise-free. Sources:
  [Detection of repetitive patterns in near regular texture images](https://www.researchgate.net/publication/252024928_Detection_of_repetitive_patterns_in_near_regular_texture_images),
  [minimal repeated pattern detection in printed fabric images](https://www.sciencedirect.com/science/article/abs/pii/S0950705124007913).
- Key insight for the failing examples: the star quilt (half-square
  triangles) and Old Mill Wheel (quarter circles) are STRONGLY periodic at
  the block level even though their content is not solid squares.
  Image-level autocorrelation finds that block pitch where cell-label
  matching cannot. So QREP can honestly report the repeat even when it
  cannot recover the cell contents. Council correction: the image-level
  period is NOT independent of the grid pitch when converted via cells; the
  honest cross-check is whether period_px / pitch_px lands within epsilon of
  an integer (confirms the pitch) - a non-integer ratio is itself evidence
  the pitch is wrong and feeds back as a pitch candidate.
- Once a repeat is confirmed on a squares-compatible quilt,
  confidence-weighted plurality voting per cell across its periodic copies
  (NOT a median - palette indices are categorical) is a cheap accuracy win,
  guarded so it can never make things worse (see S4).
- Non-square PIECING (triangles, curves) stays out of the model this sprint:
  qrep-design-doc.md pins non-grid piecing out of scope for v1, and changing
  the cell model ripples through construct, export, render, and the frozen
  goldens. Sprint 3 ships honest detection and messaging; full shape support
  remains issue #17.

### Physical size

- Absolute scale from a single photo is unknowable (already stated in the
  pipeline docstring; reference-object recovery stays ceded to #19). The
  honest source is the user, who usually knows.
- Council correction to v1: the repo ALREADY ships a standard-size table,
  the PRESETS tuple in qrep/viewer/sizing.py and web/src/model/sizing.ts
  (Crib 36x52, Throw 50x65, Twin 70x90, Full 84x90, Queen 90x108,
  King 110x108), test-pinned in both languages. Sprint 3 reuses PRESETS
  verbatim for the size chips; no second table.
- Council correction to v1: adjacent presets are indistinguishable by aspect
  ratio (Full and Queen differ by under half a percent), so aspect-based
  prediction can only ever SUGGEST (highlight a chip), never silently
  prefill numbers, and only when exactly one preset matches within a stated
  orientation-normalized tolerance.
- Whiteboard-rectification aspect recovery (focal-aware) remains a stretch
  upgrade, not core. Source:
  [Zhang, Whiteboard scanning and image enhancement](https://www.microsoft.com/en-us/research/wp-content/uploads/2004/05/2004-zhang-icassp.pdf).
- Council correction to v1 (the biggest sizing defect): arbitrary user
  dimensions are often UNREPRESENTABLE in the model. Cells are square with
  one integer-eighths cell_size and borders add identically to both axes, so
  finished W - H = (cols - rows) * cell_size exactly; the plan's own 86 x
  67.5 example has no integer solution over a 13-column grid. S6 therefore
  ships an explicit reconcile rule with asked-vs-got presentation, the same
  contract the sprint 2 sizing panel already established.

## Scope

In scope: everything under "Slices" below, including ALL of open issue #33
(vision robustness off the synthetic oracle), pulled into the sprint at
approval: S3 covers its pitch criterion (AC1) with a recovery test, and the
dedicated slice S5 covers palette-under-lighting (AC2) and
border-width-at-scale (AC3) and closes #33.

Out of scope, unchanged from v1/v2 decisions:
- Non-grid piecing in the model (triangles, curves, applique): #17. Sprint 3
  detects and reports; it does not represent.
- Absolute scale from reference objects: #19.
- Multi-image fusion (#21), partial-view recovery (#54), stitch detection
  (#16).
- Any editor or export changes beyond consuming a correctly sized model and
  the two named additions (startBlankWithPalette entry, apply_finished_size
  bridge call).

## Hard rules (carried forward, plus sprint 3 additions)

All sprint 2 rules stand: TDD with hand-computed expectations, frozen
goldens, PR-per-slice, no AI attribution, engine-authoritative numbers,
PARITY vocabulary (squares not cells; loading not downloading; mixed
fractions).

Sprint 3 additions and amendments (each traceable to a council finding):

- HONEST FAILURE IS A FEATURE. A structured "could not read this" result
  with a reason is a PASS when the fixture is designed to be unreadable;
  emitting a quilt with absurd dimensions is the bug.
- E2E TRAVERSAL AMENDMENT. "Sprint 1 and 2 suites pass untouched" is
  amended for exactly one mechanical case: Playwright photo-flow TRAVERSAL
  helpers (uploadPhoto and equivalents in web/e2e/photo.spec.ts) may be
  updated in S2 to click through the new crop screen, because inserting a
  crop state makes the old traversal fail by definition. Every existing
  ASSERTION on results content stays byte-for-byte unchanged; the S2 PR
  body lists each traversal edit. All other suites remain untouchable.
- THRESHOLD LITERALS ARE CONTRACTUAL. Every numeric pass/fail literal in
  this plan (IoU bounds, pitch-agreement tolerance, cell-count bounds, the
  integer-ratio epsilon, the 5% border and 2% pitch recovery bounds) is
  frozen into the slice issue bodies at approval time, before any pipeline
  code runs on the fixtures, under sprint 1's "never edited to force a
  pass" declaration (precedent: tests/test_roundtrip.py header). Exactly
  three literals cannot be honestly chosen before the fixtures exist: the
  verdict thresholds T1, T2, T3. Those are PROPOSED with measured evidence
  in S0's baseline report, frozen by a parent-issue checkbox BEFORE S1
  starts, and from then on are as immutable as the rest. No other literal
  gets this deferral.
- DESIGN REFERENCE BEFORE UI. The three new UI surfaces (crop screen, size
  block, verdict panels) get a committed design reference (mocks or a
  binding UI-SPEC section) plus a PARITY sprint-3 amendment BEFORE the crop
  screen slice starts. The untracked "UI from Claude Design.zip" at the
  repo root is resolved in S0: inspected, and either committed as the
  sprint 3 design bundle or discarded with a note. If no mock exists for a
  surface, S0 writes the binding UI-SPEC section instead and PARITY records
  it as the authority.
- MANUAL SMOKE ASSIGNMENT. Manual-smoke checkboxes that require Jake or a
  real device are assigned to Jake, non-blocking for slice merge, tracked
  on the parent issue (sprint 2 #46 precedent). Smoke steps live on the
  slice that makes them OBSERVABLE (a pipeline change is smoked on the
  slice that renders it).
- Every new pipeline behavior is exercised against the S0 photo-reality
  fixture set, not only against renderer output.
- New CV sub-scores live in diagnostics; the six-stage confidence schema
  (rectify, palette, grid, cells, repeat, border) is validator-frozen
  (qrep/model/schema.py STAGES) and gains NO new stages. User-entered facts
  are recorded via diagnostics size_source, not a fake stage confidence.
- Committed fixtures must be rights-clean: composites we generate ourselves.
  Jake's saved shop photos are used only in the manual smoke pass, never
  committed.
- Pyodide parity: any new cv2 surface must be spike-verified in the wasm
  build in S0, with wall-time and memory acceptance, not just "it runs".

## The verdict contract (single definition, owned by S4)

One field, `verdict`, lives in ReverseResult.diagnostics and in the bridge
envelope. Enum: `readable` (grid recovered, squares content),
`readable_no_repeat` (grid recovered, no periodic block - NORMAL result,
common for samplers and medallions, not a failure),
`non_square_repeat` (periodic at block level, content not solid squares),
`no_grid` (no plausible grid; subsumes S3 plausibility failures and
detection failures). S3 emits a `grid_diagnosis` diagnostics field (its
guards' structured reasons); S4 folds it into the verdict. Decision tree
with pinned thresholds (frozen at approval per the hard rule): grid
confidence < T1 -> no_grid; else periodicity score < T2 -> readable or
readable_no_repeat by repeat score; else intra-cell coherence > T3 ->
non_square_repeat. The pipeline NEVER raises for unreadable input:
estimate_grid's ValueErrors ("profile too short", "no periodicity found")
and rectify's "no quilt found" become zero-confidence typed results (S3).
bridge.reverse's envelope grows from {"model"} to {"model", "verdict",
"diagnostics"} (S4); rpc.ts and PhotoResult carry them (S4 types, S8
renders).

## Slices

Orders restart at 0; ids are unique across the sprint. Each slice is one
PR, landable by one chat.

### Slice 0: S0 photo-reality fixtures, metrics, design bundle, wasm gate

Goal: an evidence base hard enough that green means the field failures are
actually fixed, plus proof the new cv2 surfaces work under Pyodide, plus
the binding design reference for the new UI.

Ships:
- tests/fixtures/photoreal/ generator (deterministic, seeded) producing, at
  the staged resolution caps (1400 px phone / 2000 px desktop) so native
  and wasm test the same operating point: render-on-white, render-on-wood,
  render-with-perspective-and-jpeg, screenshot-composite (quilt on a light
  page between dark chrome-like bars), tall-chrome variant (small quilt,
  large bars), edge-to-edge crop (quilt touches image edges),
  white-bordered-quilt-on-white, strong-lighting-gradient (beyond the
  renderer's deliberately mild 0.88 floor), fabric-print texture over
  cells, seam/quilting shadow overlay, HST star-block composite,
  quarter-circle drunkard's-path composite (the Old Mill Wheel failure
  class), busy-print squares composite and low-contrast HST (the two
  confusion directions of the S4 coherence classifier), and a solid-fabric
  no-pattern image.
- Determinism spec: fixtures are GENERATED ONCE and COMMITTED as PNGs;
  tests compare regenerated decoded PIXEL arrays against the committed
  files (JPEG container bytes are not stable across the three CI OpenCV
  builds; only numpy-generated stages are byte-compared).
- Metric helpers: quad IoU vs known placement, grid-dims exact match, cell
  accuracy vs source model, palette fidelity (max Lab distance of matched
  palette entries) - hand-computed expectations on tiny hand-built arrays.
- Pinned legacy-regression fixture: current detected corners and full
  recovered-model JSON captured on the L0-L2 seed-42 renders (there are no
  reverse goldens today; test_roundtrip.py pins thresholds only). This is
  the byte-stability contract S1 is held to.
- Baseline report as an issue comment: current-pipeline numbers on every
  fixture, red cases named. Red baselines are recorded, not asserted; the
  slices that fix them write the red tests.
- Design bundle: resolve "UI from Claude Design.zip" (commit as
  docs/design/sprint-3/ or discard with a note); write the PARITY sprint-3
  amendment skeleton and, for any new surface without a mock, the binding
  UI-SPEC section (crop screen, size block, verdict panels, new pill tier,
  progress-row failure states).
- Wasm gate, extending the sprint 2 spike: cv2.grabCut and cv2.dft (or
  matchTemplate) run under Pyodide on the committed fixtures and agree with
  native within an IoU/score tolerance (not exact equality), with
  cv2.setRNGSeed before every grabCut call and a same-process
  repeat-determinism check; wall-time and peak-memory acceptance at both
  staged caps, grabCut measured at the ~600 px detection downscale.

Gate rule (same shape as sprint 2 S0): if grabCut or the DFT path cannot
meet the gate after 3 documented APPROACH FAILED attempts, stop the sprint
for a fallback decision. Named fallbacks: pure-numpy FFT autocorrelation
for DFT; border-model-only detection for grabCut - and if the grabCut
fallback is taken, the wood-texture fixture's IoU criterion moves from S1
to a follow-up issue (border sampling alone cannot meet it; the plan says
so rather than letting the criterion silently rot).

Tests: fixture regeneration matches committed pixels; metric helpers on
hand-built arrays; spike parity checks.
Manual smoke: none (headless slice).

### Slice 1: S1 background-agnostic quilt detection

Goal: rectify finds the quilt on photos QREP did not render, without
disturbing what it does on its own renders.

Ships, as a tiered detector in qrep/vision/rectify.py:
- Tier 0, legacy: if the border-strip median is within epsilon of #404040,
  run the EXACT current path (BACKGROUND_BGR, distance > 40) verbatim.
  Byte-identity with the S0 pinned regression fixture is claimed for THIS
  branch only. L3 renders (clutter rectangles sit inside the border strips
  by construction, renderer.py:226-243) are pinned to whatever tier the
  implementation routes them to, stated in the issue body, with their
  regression captured in S0's baseline.
- Tier 1, border-sample: per-strip median + MAD inlier fraction; all four
  strips uniform AND mutually agreeing -> background model from their
  pooled median with tolerance derived from the inlier spread; largest
  contour ranked by area x squareness (a full-width chrome bar must lose to
  a plausible quilt quad).
- Tier 2, GrabCut: strips disagree or none uniform -> cv2.grabCut with
  GC_INIT_WITH_MASK seeded from whichever strips passed uniformity, on the
  ~600 px downscale, quad scaled back; acceptance gated on foreground area
  fraction (reject near-empty and near-full masks, fall through).
- Tier 3, last resort: full-image quad at low confidence (the crop screen
  makes this visible and fixable, so it is honest).
- Confidence: the existing formula, (1 - min(residual*10, 1)) *
  (1 - warp_magnitude) (v1's "fill-ratio" description was wrong - no such
  symbol exists); the GrabCut tier gets its own mapping (mask compactness x
  quad fit residual), pinned with hand-computed cases.
- One test asserting the GENERALIZED tier-1 path handles an
  exact-#404040-bordered fixture (so tier 1 is exercised on the renderer
  case too, not just the legacy special-case).

Tests: per-fixture detected-quad IoU >= 0.95 vs known placement for
render-on-white, wood (unless the S0 gate took the grabCut fallback, per
S0's rule), screenshot, tall-chrome, edge-to-edge; legacy branch
byte-identical to the S0 pinned fixture; white-on-white and
lighting-gradient fixtures produce either a correct quad or a
LOW-confidence quad (never a confident wrong one - hand-pick the bound).
Manual smoke: deferred to S2 (the crop screen makes detection observable);
noted on the parent issue.

### Slice 2: S2 crop screen before analysis

Goal: the user sees and can fix the crop before any analysis runs, on a
cold cache and on a phone.

Ships:
- Engine/bridge: `detect_quad` bridge method - detection tiers only, no
  full reverse. S2 owns its FULL return contract: quad (normalized), tier,
  confidence, and predicted_size (nearest-PRESET suggestion + aspect data;
  the FIELD is defined here, S7 populates the UI). Registered in worker.ts
  BRIDGE_METHODS/VISION_METHODS; staged image files are unlinked from MEMFS
  after each call (today's uploads are never cleaned up; the crop flow
  stages the photo once and reuses the staged token, invalidated on worker
  restart).
- State layer (project.tsx): `start()` splits into `stage()` (file in,
  photoUrl + detect_quad kicked off) and `analyze(corners)`; new
  `detectedQuad` state distinct from user-adjusted corners so "Reset to
  auto" has something to reset TO; a second photo (including after cancel)
  starts from ITS detection, never the previous photo's corners. PhotoScreen
  type gains `crop`.
- UI: crop screen between idle and progress. The pin/quad overlay is
  extracted from the private CornerEditor into a shared component. Cold-
  start contract: the photo and default inset pins render IMMEDIATELY and
  are draggable with no engine; a "finding your quilt..." affordance shows
  while detect_quad resolves; the detected quad snaps in on resolve UNLESS
  the user already moved a pin (user wins). Vision prefetch fires on
  photo-flow ENTRY (not on drop). Buttons: Analyze / Reset to auto / Back.
- The post-results corners screen is RETIRED: "Adjust the crop" from
  results (success or failure) returns to this same crop screen seeded with
  the confirmed quad; the `corners` PhotoScreen state is removed and its
  tests migrate. One pin surface, one behavior, reachable from both ends.
- Sample photo bypasses the crop screen (auto-confirmed full-frame quad).
- E2E traversal edits per the hard-rule amendment, listed in the PR body.

Tests: vitest transition matrix (idle -> crop -> progress -> results;
cancel from crop and from progress; second-photo reset; sample bypass;
user-pin-wins race); Playwright: drop the screenshot fixture, crop screen
appears with pins immediately, quad snaps in, adjust a pin, analyze, reach
results; results "Adjust the crop" returns to crop with the quad seeded.
Manual smoke (Jake, non-blocking, on parent issue): phone-width crop
interaction, cold first visit on a throttled connection, his three shop
photos detect a sane quad.

### Slice 3: S3 grid plausibility guards and raise-to-verdict

Goal: the grid stage refuses nonsense instead of shipping it, and refusal
is a typed result, not an exception.

Ships, in qrep/vision/grid.py and pipeline.py:
- Raise-to-result conversion: estimate_grid's ValueErrors and rectify's
  "no quilt found" become zero-confidence typed results carrying a
  `grid_diagnosis` (structured reason) in diagnostics; pipeline.reverse
  completes and emits a model-less-safe result path (red test: the S0
  solid-fabric fixture currently raises; after S3 it returns
  grid_diagnosis="no_periodicity", confidence 0).
- Guard (a), pitch isotropy: pitch_x vs pitch_y agreement with a tolerance
  CONDITIONED on rectify's warp_magnitude (already computed,
  rectify.py:118) via a hand-derived foreshortening bound, because the warp
  target preserves image-plane edge lengths, not physical aspect;
  disagreement triggers a joint harmonic re-search (2x, 3x, 1/2x, 1/3x
  candidates scored against both axes together).
- Guard (b), cell-count bounds derived from the detector's real envelope
  (MIN_PITCH_PX=5 against the staged caps gives the honest upper bound;
  the lower bound is 2). Stated as a new product decision in the issue
  body, NOT attributed to the design doc (v1 fabricated that citation).
- v1's guard (c), grid-aspect vs image-aspect, is DROPPED: boundaries span
  [0, extent] by construction, so the check compares the image aspect to
  itself (council-verified tautology). Its intent returns in S6: when the
  user has entered a size, grid-implied aspect vs entered aspect is a real,
  independent check.
- Violations lower grid confidence below the honest-failure threshold T1
  (frozen at approval) and set grid_diagnosis; nothing raises.
- Fixtures from #33's AC1 (systematic 14/16 pitch alternation) join the
  suite with a RECOVERY assertion (pitch within 2%), plus the two guard
  boundary fixtures: a frontal composite with a planted one-axis harmonic
  where the guard must fire, and a ~35-degree tilted composite with
  hand-computed post-warp pitch ratio where it must stay silent.

Posts a progress comment on #33 (AC1 addressed here with a recovery test;
AC2/AC3 land in S5, which closes #33).

Tests: hand-built profiles where the harmonic wins today and must not
after; the 13x43 class reproduced on the perspective+mis-crop fixture and
caught (grid_diagnosis set, confidence < T1); both guard boundary fixtures;
existing grid tests byte-stable.
Manual smoke: none (headless; observable behavior smoked in S8).

### Slice 4: S4 image-level repeat detection, voting, and the verdict

Goal: "does this quilt repeat, and at what period" answered from the image,
exploited when yes, and folded into the single verdict contract.

Ships, in qrep/vision/repeats.py, pipeline.py, bridge.py, rpc.ts:
- Image-level periodicity: FFT-accelerated normalized autocorrelation of
  the detrended (high-pass) rectified grayscale over a FIXED-FRACTION
  central inset (not the detected-border interior, which is garbage exactly
  when we need this most). Fundamental selection mirrors grid.py's rule
  (smallest lattice vector comparably strong to the strongest, threshold
  frozen), with a max-lag cap.
- Pitch cross-check, replacing v1's false "independent detector" claim: the
  label-based detector shares the grid pitch, so the real test is
  period_px / pitch_px within epsilon of an integer (confirms pitch); a
  non-integer ratio feeds back to S3's harmonic re-search as a pitch
  candidate. The label-based detector's MATCH_THRESHOLD drops to a soft
  best-score vote that PRESERVES minimal-period selection (diagnostics
  repeat_period stays [10, 10] on the Irish chain fixture, not a multiple).
- Intra-cell coherence score (edge energy inside cells vs on boundaries)
  feeding the non_square_repeat arm, with BOTH confusion directions pinned
  by fixtures: busy-print squares must stay readable; low-contrast HST must
  still read non_square_repeat. Raw sub-scores go in diagnostics; stage
  confidences stay within the frozen six (folded into repeat and grid).
- Repeat voting: confidence-weighted plurality over per-cell margins (NOT
  median - labels are categorical), gated on the integer-ratio test
  passing, minimum 3 periodic copies on the voted axis, and a post-vote
  invariant: agreement with high-margin pre-vote cells must not drop.
  Contractual identity test: on the L0 seed-42 render the vote is
  element-wise identity (cell_accuracy 1.0 over all 2475 cells,
  test_roundtrip.py's pin).
- The verdict contract lands here (see "The verdict contract" above): enum,
  thresholds, grid_diagnosis fold-in, and the bridge envelope change
  ({"model"} -> {"model", "verdict", "diagnostics"}) with rpc.ts and
  PhotoResult types updated. Existing bridge tests that assert the envelope
  gain the new keys in the same PR (additive; no existing assertion
  weakened).
- Period is reported in CELLS (and repeats-across-width). Inches appear
  only when a user-entered size exists (S6+); ASSUMED_PPI never converts a
  period.

Tests: hand-computed autocorrelation on tiny synthetic arrays; HST and
drunkard's-path composites yield non_square_repeat with the correct block
period; busy-print squares stay readable; solid-fabric yields no_grid;
voting flips a hand-planted minority of corrupted cells on the noisy Irish
chain fixture and is identity on L0; integer-ratio feedback corrects a
planted harmonic pitch.
Manual smoke: deferred to S8 (verdicts are invisible until rendered);
noted on the parent issue.

### Slice 5: S5 palette and border robustness (closes #33)

Goal: the remaining #33 criteria, so the vision pipeline is robust off the
synthetic oracle in ALL three of that issue's probes, not just pitch.

Ships, in qrep/vision/palette.py and borders.py:
- Palette lighting normalization (#33 AC2): flatten large-scale luminance
  variation (Lab L-channel detrend or an equivalent illumination-invariant
  step) before k selection and kmeans, so the symmetric-pinch-plus-lighting
  probe resolves k == 2 instead of splitting one fabric into light and dark
  phantoms. The S0 strong-lighting-gradient fixture doubles as the
  regression case; the L0-L2 legacy regression (S0 pinned fixture) must
  stay byte-stable, so normalization is applied in a way that is identity
  on flat-lit renders, or the tier is gated on measured gradient magnitude
  (decided in-slice with the reasoning in the issue).
- Border-width recovery at non-default scales (#33 AC3): border strip
  widths within 5% of truth at render scales 8 and 12 (sub-strip
  refinement of widths_px rather than whole-cell counting).
- Recovery assertions per #33's pinned criteria: AC2 k == 2 on the probe;
  AC3 width error <= 5% at both scales. AC1's 2% pitch recovery lives in
  S3 and is referenced.
- PR carries Fixes #33.

Tests: the #33 probe fixtures with recovery assertions; palette fidelity
metric (S0) improves or holds on every photoreal fixture; legacy pinned
regression byte-stable.
Manual smoke: none (headless).

### Slice 6: S6 size engine - reconcile math, presets, provenance

Goal: user-entered size flows through the model honestly, including when it
is unrepresentable.

Ships (engine + bridge only; UI is S7):
- reverse() accepts optional finished width/height as OPTIONS_JSON keys
  (keyword-only through the bridge; no positional signature change - the
  worker rewrites reverse_photo positionally today).
- Reconcile rule (the model cannot represent arbitrary W x H: square
  integer-eighths cells, borders add equally to both axes, so W - H =
  (cols - rows) * cell_size exactly): derive the cell candidate per axis,
  take the min that satisfies the editor's clamps, recompute achieved
  dimensions, and store ONLY achieved dims in the model; the response
  carries {requested, achieved} so the UI reuses the sprint 2 sizing
  panel's asked-for-vs-you-get presentation. Hand-computed contract test:
  86 x 67.5 over a 13 x 10 grid pins rows, cell, bands, and achieved dims
  end to end. A non-representable-entry test is mandatory.
- Clamp decision (frozen at approval): photo-derived models honor the
  editor's CELL_MIN/CELL_MAX clamps; an entry whose derived cell falls
  outside them returns achieved-at-clamp with the delta reported, never an
  error.
- Size trust lives in diagnostics: size_source ("user" | "guess"),
  size_is_guess. NO new confidence stage (schema-frozen). Provenance 1.0
  semantics attach only to size_source="user".
- PRESETS reused verbatim: exported through the bridge (single source of
  truth; no second table). Nearest-preset suggestion logic: orientation-
  normalized aspect match, returned only when exactly ONE preset falls
  within the frozen tolerance; otherwise no suggestion.
- `apply_finished_size` bridge call: re-derives cell/borders on an existing
  model without re-running vision (powers late size edits from results).
- ASSUMED_PPI survives only as the size_source="guess" fallback;
  the metadata note text updates accordingly.

Tests: pytest only - reconcile math (hand-computed), clamp edges, preset
suggestion uniqueness, apply_finished_size equivalence with a fresh
reverse at the same size, options_json round-trip through the bridge.
Manual smoke: none (headless; S7 makes it observable).

### Slice 7: S7 size UI - chips, inputs, units, the size story

Goal: the user can state the real size at crop time or any time after,
and always sees an honest size story.

Ships:
- Crop screen size block ("How big is it?", optional): PRESET chips plus
  W x H inputs accepting decimal ("67.5") AND mixed ("67 1/2") entry,
  normalized to mixed-fraction display (the shopper's listing says 67.5).
- Units (approval decision): an in / cm toggle on the size block and the
  inline results editor. The MODEL stays integer eighths everywhere; cm
  entry converts at entry via a pinned rule (eighths = round(cm * 8 /
  2.54)), with hand-computed vitest cases, and the size line shows the cm
  equivalent in parentheses when the user entered cm. Rulers, the editor,
  and every export stay inches (scope pin; full metric display is logged
  as a follow-up issue, not silently promised).
  The nearest-preset prediction renders as a HIGHLIGHTED CHIP suggestion;
  numbers prefill only on the single-match-within-tolerance rule (an
  anchored-wrong prefill is worse than empty). Provenance user only on an
  explicit gesture (chip tap or edited input); an untouched suggestion
  ships as guess. Asked-vs-got line appears at confirm time when achieved
  differs from entered. Layout specified for <720 px with the soft
  keyboard up (per the S0 design reference).
- Results screen size story: the size line is tappable in BOTH states -
  entered ("86 x 67 1/2 finished", tap to edit) and guessed ("our guess -
  tap to set the real size") - opening an INLINE W x H editor that applies
  via apply_finished_size (no navigation, no re-analysis; a typo is never
  a one-way door). Sizes flow to the editor so it opens at real
  dimensions.
- Editor entry consumes achieved dims and the asked-vs-got context.

Tests: vitest for chip/input/prefill/gesture-provenance rules and both
entry formats; Playwright: enter 86 x 67.5 on the crop screen, results
shows the achieved size with the asked-vs-got line, editor opens at it;
edit size from results inline and see it stick without a re-run.
Manual smoke (Jake, non-blocking): standing-in-front-of-quilt flow on the
phone - type a size mid-flow, see it stick through to the editor rulers.

### Slice 8: S8 honest results messaging

Goal: when QREP cannot read a quilt, the app says so, says why, and offers
a real next step; when it can, new positive signals join the story.

Ships, keyed off the verdict (which S4 already delivers to PhotoResult):
- `no_grid`: failure panel "We could not find a square grid in this photo"
  with reasons and actions: Adjust the crop (returns to the S2 crop
  screen), retake tips, or Start in the editor. The recovered-quilt panel
  is NOT hidden: it collapses behind a disclosure ("Show what we saw
  anyway") that expands with a persistent this-is-wrong banner and keeps
  the side-by-side lightbox available - the 13x43 smear is the user's best
  diagnostic for what went wrong.
- `non_square_repeat`: "This quilt's blocks repeat, but they use shapes
  QREP cannot read yet (triangles and curves)" - period stated in inches
  when user-sized, otherwise "repeats about N times across its width",
  with an invitation to add the size. Squares approximation available
  behind the same labeled disclosure. Copy softens the shape claim (edge
  energy cannot fully distinguish piecing from busy prints).
- `readable_no_repeat`: a NORMAL result; caption gains "No repeating block
  found - common for samplers and medallion quilts." No failure framing.
- `readable` with a confirmed repeat: positive caption line "repeats every
  N in" (sized) or "repeats N times across the width".
- Overall pill: on failure verdicts the percentage is DROPPED - "Could not
  read this photo" in accent tone (a mean-of-stages percentage next to a
  failure statement is a contradiction; PARITY tier table amended).
- Progress screen: stage rows at and after the failure point render a
  neutral dash, not green checks (six green checks before a failure panel
  contradict the verdict).
- Blank-grid escape: `startBlankWithPalette` project entry (neither
  existing entry accepts a palette), gated on palette-stage confidence
  above a frozen threshold and the S0 palette-fidelity metric; below it,
  plain blank grid (prefilling chrome-gray junk fabrics would undermine
  the honesty theme).
- Entry copy: dropzone sub-copy gains "A photo, a screenshot, or a shop
  listing picture all work"; start-screen lede reflects the honest size
  position. copy-audit test extended to the new strings and to
  verdict/pill consistency.
- PARITY sprint-3 amendment finalized (pill tier, panel visibility rules,
  verdict copy strings, chip component), matching the S0 design reference.

Tests: vitest rendering of every verdict variant from fixed PhotoResult
fixtures (including disclosure and banner state); Playwright: solid-fabric
fixture upload lands on the failure panel with the disclosure collapsed,
expand shows the banner, editor-with-palette action works; copy-audit.
Manual smoke (Jake, non-blocking): star quilt and mill wheel photos show
the non-square message with sane period counts; the Irish chain product
photo reads correctly end to end - the sprint's three field failures,
re-run for real.

### Slice 9: S9 release 0.3.0

Goal: sprint lands as a coherent release.

Ships: CHANGELOG, README photo-flow section refresh, docs/sprint-3/
REPORT.md, version 0.3.0 everywhere (pyproject, web), Pages deploy verified
live, demo flow re-checked, the metric-display follow-up issue filed (from
S7's scope pin), parent-issue checklist ticked and closed.

Tests: existing suites green on CI including the Pyodide and e2e jobs;
version consistency check.
Manual smoke (Jake, gate for the release): full phone walkthrough of the
new photo flow on live Pages with a real shop photo - crop, size, verdict,
editor.

## Universal Definition of Done (sprint 2's, plus the amendments above)

Per slice: tests written first and red, then green (pytest + ruff native;
vitest + Playwright where web changes); sprint 1 and 2 suites pass
untouched EXCEPT the named S2 e2e traversal amendment; no golden touched
outside a justified [bless] commit (none expected); threshold literals
never edited; acceptance boxes ticked with evidence, manual-smoke boxes
assigned to Jake are non-blocking and tracked on the parent issue; one PR
per slice with Fixes #N; author Jake Mismas, no AI trailers; branch
hygiene; KNOWN_ISSUES + xfail escape only after 3 documented APPROACH
FAILED attempts.

## Issue plan (created on approval)

CREATED 2026-07-09. Parent: #65 "Sprint 3: real-photo robustness
(auto-crop, honest verdicts, real sizes)". Sub-issues: S0 #66, S1 #67,
S2 #68, S3 #69, S4 #70, S5 #71, S6 #72, S7 #73, S8 #74, S9 #75 - each body
carries its slice section verbatim plus acceptance-criteria checkboxes
(T1-T3 deferred per the hard rule; frozen via the parent checkbox before
S1). S5 (#71) carries Fixes #33; #17 and #19 named as explicit non-goals.
docs/sprint-3/ORCHESTRATOR.md is the sprint 2 skeleton with: issues
#66-#75, S0 gate items updated (grabCut/DFT wasm parity with perf
acceptance, T1-T3 proposal duty), the e2e traversal amendment quoted,
completion criteria v0.3.0.

## Approval record (2026-07-09)

1. Size units: inches PLUS cm entry. Encoded in S7: entry-side conversion
   with a pinned rounding rule; model stays integer eighths; full metric
   display is a logged follow-up, not in scope.
2. Size chips: the shipped PRESETS table reused verbatim (single source of
   truth exported through the bridge). No migration.
3. Design reference: no sprint 3 mocks exist ("UI from Claude Design.zip"
   at the repo root verified as a byte-size-identical duplicate of the
   committed sprint 2 mocks; S0 deletes it). S0 writes binding UI-SPEC
   sections for the crop screen, size block, and verdict panels.
4. #33: pulled fully into the sprint. S3 covers AC1; new slice S5 covers
   AC2 and AC3 and closes #33.
