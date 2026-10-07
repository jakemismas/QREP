# QREP sprint 5 code review: verified findings

**What this is.** The verified code review Jake asked for on 2026-10-06 (HANDOFF section 1, item 2),
taken at commit 834d8be. Nine read-only recon reports produced 306 findings. An independent verifier
re-checked every finding while trying to refute it, and a second verifier re-checked every critical
and major finding that survived. This file publishes each finding by id with its verdict, severity,
fate and disposition. The sprint-5 plan (docs/sprint-5/qrep-sprint-5-plan.md) and its tickets cite
these ids; this file is where they resolve.

## Rules for using this review

- Finding ids are stable. Never renumber, reuse or delete one. Why: the plan, the ticket issues and
  the overnight report cite them, and a moved id breaks every citation.
- The disposition says who acts. Why: plan section 0 makes this file the bridge from verified
  findings to ticket acceptance criteria, and sends findings in deleted code to the deletion ticket
  instead of new issues (Critique: CR-sequencing-28).
  - `ticket:X`: ticket X's acceptance criteria fix the finding, or carry its lesson into the code
    that replaces it.
  - `new:X`: the plan added ticket X for this finding.
  - `deletion-note:X`: ticket X deletes the code, and the finding closes with the deletion.
  - `protocol:ORCHESTRATOR` or `protocol:WORKER`: docs/sprint-5/ORCHESTRATOR.md or WORKER.md handles
    it.
  - `no-action`: nothing to build, for the stated reason.
  - `UNMAPPED`: no disposition was recorded. All 11 such findings are refuted or unverifiable
    (section 5).
- The numbers below are what the verifiers observed at 834d8be. MATH.md owns every formula and
  corrected value, and PATTERN-SPEC.md owns every pattern-document rule; this file never overrides
  them. Why: one home per number.
- Ticket E3 is the only ticket that owns this file during the sprint, and it only appends its round
  2 section (section 6). Why: the record of what the review found must stay stable while the code
  changes.
- Private evidence stays private. The verifier scripts, screenshots and the three field screenshots
  live in a private folder outside the repo; this file describes what they showed and cites repo
  files by path and line. Why: the field photos are rights-unclean shop images (.gitignore:28-30),
  and HANDOFF forbids copying the evidence folder into the repo.

## What the review found, in brief

- The automatic read fails on real photos and labels many wrong reads "readable" (vision-01,
  docs-01, data-16). The plan replaces it with a confirmed read, in which the user confirms the
  corners and counts, and then deletes it (B2a, B2b, B6b).
- The pattern is not sewable as printed: the strip PDF lists squares the strip sets already make,
  the backing and yardage math is wrong, long borders are never joined, and the PDF has no figures
  (engine-01, engine-13, engine-02, engine-06, engine-03). Track A fixes the math first.
- The web app gives a different quilt at a different screen width, shows wrong reads as success, and
  keeps every download inside the editor that sprint 5 removes (ux-06, web-05, docs-06). Track C
  builds Your pattern before the editor goes.
- The green suite cannot see any of this: no test scores a read against truth, and the repo holds no
  real photo with truth (tests-01, tests-02, vision-03). Track D builds the corpus and the eval.
- main is unprotected and ruff is unpinned (tests-09, tests-05). Setup fixes both before the
  overnight run.

## 1. What was reviewed and how

**Scope.** Nine read-only recon reports covered the code and its surroundings at 834d8be: vision,
engine, web, tests, docs, ux, data, approaches and orchestration (the table below names each). No
report changed the repo.

**Pass 1: every finding, refute-framed.** An independent verifier tried to disprove each finding. It
read the cited file and lines and re-ran the claim with its own scripts: engine runs from scratch
copies, its own scorers against the fixtures' truth, the live site driven in headless Chromium (the
deployed bundle matched a build of 834d8be), and fresh copies of the cited web pages. It recorded a
verdict: CONFIRMED (holds as stated), PARTIAL (the core holds, and part of the claim is corrected or
refuted), REFUTED, or UNVERIFIABLE (cannot be settled read-only). It also set a severity (critical,
major, minor or nit) and a fate.

**Pass 2: critical and major findings, again.** A second verifier re-ran the 90 critical and major
findings that survived pass 1 with its own scripts and recorded its own verdict and severity. The 4
major findings that pass 1 refuted were not re-checked. Pass 2 also re-ran one sub-bug of ux-16 to
settle its severity, so 91 findings have a pass-2 entry. Where pass 2 ran, its verdict and severity
are final.

**Fate.** Jake narrowed sprint 5: a confirmed read replaces the automatic read, which is then
deleted, and editing is removed (HANDOFF section 2, items 3 and 4). Each finding carries a fate
against that narrowing:

- survives (76): the code stays, and a ticket fixes it.
- product (38): a product or scope finding; it informs a ticket or is recorded as context.
- deleted-code (55): the code is scheduled for deletion by B6b, C6b, C6a or A7.
- process (137): tests and CI, tracking, docs, data licensing, or the overnight protocol.

**Results by report.** C, P, R and U are CONFIRMED, PARTIAL, REFUTED and UNVERIFIABLE.

| Report | Findings | Pass 1 C / P / R / U | Re-checked | Pass 2 C / P / R | Final C / P / R / U | Final critical / major / minor / nit |
|---|---|---|---|---|---|---|
| vision (the automatic read) | 22 | 19 / 3 / 0 / 0 | 12 | 8 / 4 / 0 | 16 / 6 / 0 / 0 | 2 / 7 / 9 / 4 |
| engine (construction, math, export) | 25 | 24 / 1 / 0 / 0 | 13 | 12 / 1 / 0 | 24 / 1 / 0 / 0 | 1 / 11 / 11 / 2 |
| web (the app's code) | 25 | 22 / 3 / 0 / 0 | 9 | 8 / 1 / 0 | 22 / 3 / 0 / 0 | 1 / 7 / 14 / 3 |
| tests (suite and CI) | 24 | 22 / 2 / 0 / 0 | 7 | 6 / 1 / 0 | 22 / 2 / 0 / 0 | 1 / 6 / 12 / 5 |
| docs (docs and tracking) | 20 | 14 / 6 / 0 / 0 | 6 | 2 / 4 / 0 | 12 / 8 / 0 / 0 | 1 / 4 / 10 / 5 |
| ux (the live site in a browser) | 25 | 24 / 0 / 1 / 0 | 11 | 9 / 2 / 0 | 22 / 2 / 1 / 0 | 2 / 8 / 11 / 4 |
| data (corpus sources, licensing) | 63 | 47 / 11 / 0 / 5 | 17 | 10 / 7 / 0 | 44 / 14 / 0 / 5 | 0 / 10 / 35 / 18 |
| approaches (prior art, alternatives) | 58 | 43 / 11 / 1 / 3 | 7 | 5 / 1 / 1 | 42 / 11 / 2 / 3 | 0 / 6 / 14 / 38 |
| orchestration (overnight tooling) | 44 | 8 / 27 / 7 / 2 | 9 | 3 / 6 / 0 | 8 / 27 / 7 / 2 | 0 / 8 / 31 / 5 |
| **Total** | **306** | 223 / 64 / 9 / 10 | 91 | 63 / 27 / 1 | 212 / 74 / 10 / 10 | 8 / 67 / 147 / 84 |

The ux row's re-checked count includes the ux-16 severity check.

**What pass 2 changed.**

- Verdicts: 10 findings dropped from CONFIRMED to PARTIAL (vision-04, vision-12, vision-14, docs-03,
  docs-04, ux-03, ux-14, data-05, data-59, data-60), and 1 was refuted (approaches-33: the edge
  drift it described is a color failure; see section 5).
- Severity: 3 critical findings became major (vision-04, web-09, approaches-28); 20 major findings
  became minor (vision-08, vision-12, vision-14, engine-12, web-08, docs-04, ux-07, data-05,
  data-12, data-13, data-18, data-42, data-47, data-50, approaches-33, approaches-52,
  orchestration-03, orchestration-24, orchestration-25, orchestration-34); and the stale-bytes path
  inside ux-16 rose from minor to major.
- Final severity: 8 critical, 67 major, 147 minor and 84 nit. Every final critical finding has the
  same shape: wrong output presented as right on a primary path.

## 2. Top findings: critical and major, verified twice, in code that survives

These 33 findings are critical or major after both passes, survived both, and sit in code or product
scope that the narrowing keeps. Critical findings come first, then majors by the track that fixes
them. Findings that describe one defect share an entry. Each entry gives what the verifiers saw and
the ticket that fixes it; the ticket's acceptance criteria in plan section 5 are the binding fix.

### 2.1 Critical

#### engine-01: PDF cutting table tells strip-strategy quilters to cut every square individually

Critical. CONFIRMED in both passes.

- **Seen:** qrep/export/pdf.py:130-148 prints Fabric, Piece, Component, Quantity, Cut size and
  Finished size, and never CutPiece.source (qrep/construct/plan.py:27). The strip booklet for the
  benchmark fixture lists 1,246 blue and 1,229 cream squares, cut 2 x 2 in, as cuts, then strip sets
  SS1 to SS5 that make the same squares, and no text links the two. Strip is the web default
  (web/src/state/project.tsx:48), and the download's sub-label reads "multi-page, ready to sew"
  (web/src/shell/PatternPanel.tsx:42). Pass 2 nuance: the purchase covers the cutting table alone;
  the fabric runs out when the reader also cuts the strip-set strips that the assembly steps
  require.
- **Fixed by:** A4c, *Cutting instructions and the cut-list text*. Cutting prints strips, then
  subcuts, from one layout and never lists strip-set squares as cuts (PS-16, PS-17).

#### ux-06: Same photo, different quilt depending on screen width

Critical. CONFIRMED in both passes.

- **Seen:** stage() downscales the whole photo to a cap chosen by the window width
  (web/src/state/project.tsx:854; web/src/model/downscale.ts:8-20: 2000 px at 720 px and wider, 1400
  px below), and the size guess assumes 10 px per inch (qrep/vision/pipeline.py:53, :236). On the
  live site the same pins gave 59 7/8 x 61 1/4 in on a 1440 px desktop and 37 5/8 x 38 1/2 in at
  iPhone 13 size; in the engine, the same stored pins gave 41 x 40 squares at the 2000 cap and 43 x
  42 at 1400. The pins are also placed as fractions of the padded .pf-corner-box
  (web/src/shell/PhotoFlow.tsx:603-607, :636, :1183) and then multiplied by image pixels
  (project.tsx:897), so the engine reads 5 to 7 percent inside each corner the user set.
- **Fixed by:** C3b, *Confirm screen in the photo flow, with crop-aware staging (includes #101)*.
  Pins mapped from the image rect (C3a geometry), one viewport-independent staging crop, and an e2e
  that compares 1440 px with 390 px.

#### docs-01: No shipped path reads any of the three real field photos on the phone; even hand crops mostly fail

Critical. PARTIAL in both passes.

- **Seen:** scripts/local_photo_smoke.py returns no_grid at tier 3 (the full frame) for all three
  field screenshots. Pass 2 got no_grid in 33 of 33 automatic runs across resamplers, including the
  real Chromium canvas bytes, and the live site at phone width agrees. The refuted part makes the
  defect worse: with hand pins, the Irish chain screenshot does read at the phone cap, as "Overall
  confidence 84% - solid" at 42 x 43, while its field is 40 x 40. Of 110 hand-pin runs, 87 read
  "readable" with 19 different dims, and none was 40 x 40.
- **Fixed by:** B2a, *Confirmed read: geometry and sampling*. The confirmed read replaces automatic
  detection, and the release gate measures it per tier on real captures (plan section 7.2).

### 2.2 Major: math, construction and the pattern document

#### engine-13: Backing considers only vertical seams; WOF labels are hard-coded to 42 in

Major. CONFIRMED in both passes (raised from the report's minor in pass 1).

- **Seen:** backing_line sizes panels from the quilt width only (qrep/construct/yardage.py:36-47),
  and "42-inch" is hard-coded at yardage.py:16 and qrep/export/pdf.py:241-242. With no borders, a 92
  1/2 x 115 in quilt gets 369 in (10 1/4 yd) where horizontal seams need 301 1/2 in (8 1/2 yd) with
  the same margin and rounding; 90 x 108 gets 9 3/4 yd against 8 1/4; 60 x 72 gets 4 1/2 against 4.
  This matches the over-estimate Jake's mother reported (HANDOFF 1.7). The PDF prints only a total
  length, never panels times panel length.
- **Fixed by:** A1, *Backing, binding and batting math*. Both orientations with seam loss and
  allowance, a backing width of its own (default 42 in), a wide-back line, and labels built from the
  setting (MATH.md D-01).

#### engine-02: Yardage is area divided by WOF with no strip packing or margin and runs short under standard cutting

Major. CONFIRMED in both passes.

- **Seen:** `_line_from_area` buys ceil(area / wof) with only quarter-yard rounding
  (qrep/construct/yardage.py:50-58), and the default WOF is still 336 eighths, 42 in
  (qrep/model/schema.py:135), although #91 recorded 40 in. Cut from strips at 40 or 41 in usable
  width, the benchmark fixture's historical method needs 166 1/2 in of cream (158 in with
  continuously joined borders) against 153 in bought. Even at 42 in, strip set SS5 needs exactly 7
  sets of 21 segments, with nothing spare for squaring the ends.
- **Fixed by:** A2b, *Purchase lines from the cutting layout and the 40 in default*. Purchase lines
  come from the strip plan plus a stated margin, never from area; A2a writes the strip-yield
  functions (MATH.md F2 to F5).

#### engine-06: Borders longer than WOF have no piecing instructions

Major. CONFIRMED in both passes.

- **Seen:** border_pieces emits one piece per side (qrep/construct/strategies.py:86-126; its
  docstring calls this a v1 simplification), so the fixture's cut list asks for 4 1/4 x 83 in sides
  from 42 in fabric. No step mentions joining strips, and yardage.py:74-75 counts borders as plain
  area.
- **Fixed by:** A2b, *Purchase lines from the cutting layout and the 40 in default*. Borders are
  bought as joined per-piece strips (MATH.md F4); A4c prints the joins and the cut lengths.

#### docs-05: The WOF=40 decision is mis-scoped and collides with the frozen-test rules

Major. CONFIRMED in both passes.

- **Seen:** #91 records WOF 40 in, but schema.py:135 still defaults to 42 in, and the change was
  routed through a "yardage golden" that does not exist (tests/golden holds cutlist_strip.csv,
  cutlist_strip.md and top.svg). The real ripple reaches the cut-list goldens, hand-computed tests
  in test_construct.py, test_exports.py, test_bridge.py and test_viewer.py, the fixture's embedded
  width (tests/fixtures/double_irish_chain.json:2631, byte-compared by tests/test_fixture.py:16-20),
  and two hard-coded "42-inch" labels (yardage.py:16 and pdf.py:242). Applied to backing, one 40 in
  width raises the fixture's backing from 5 1/2 yd to 8 1/4 yd.
- **Fixed by:** A2b, *Purchase lines from the cutting layout and the 40 in default*. The 40 in
  default lands with every touched pin listed against REBASELINE.md; A1 builds the backing label
  from its own width.

#### engine-05: Strip sets never merge same-fabric runs

Major. PARTIAL in both passes, because the stated count was wrong in the defect's favor.

- **Seen:** every strip set uses one strip per square (qrep/construct/strategies.py:394-405), so SS2
  and SS5 sew five identical strips together. Of the fixture's 100 strip-set seams, 74 join a fabric
  to itself (the report said 48), which wastes 37 in of strip width across both fabrics.
- **Fixed by:** A3a, *Block structure, merged runs and strip-set signatures*. Same-fabric runs merge
  (M-04) before strip-set signatures are built.

#### engine-11: Block inference has no plausibility gate

Major. CONFIRMED in both passes.

- **Seen:** infer_block_structure takes the first period with at most 8 block types and never checks
  that the types repeat (qrep/construct/strategies.py:47-71). A random 40 x 40 two-fabric grid
  infers 20 x 20 blocks; its strip plan has 80 strip sets and buys about 44 to 46 yd of each fabric,
  against 2 1/4 and 3 yd for the historical method on the same quilt.
- **Fixed by:** A3a, *Block structure, merged runs and strip-set signatures*. Block structure comes
  from the confirmed counts, else from the M-03 gate with the L-13 numbers; a random grid gets none.

#### engine-04 and ux-02: The default strip method errors on photo reads, and the pattern never downloads

engine-04: major, CONFIRMED in both passes. ux-02: major, CONFIRMED in both passes.

- **Seen:** plan_strip raises ValueError with no fallback when it finds no block structure
  (qrep/construct/strategies.py:365-370), while the historical and modern planners handle that case
  (:332-342, :552-564). It fails on 4 of 12 "readable" photoreal reads, and 7 flipped squares in the
  fixture (0.28 percent) are enough to trigger it. On the live site, after a readable pinned read of
  the Irish chain screenshot, the Pattern tab preselects Strip (web/src/state/project.tsx:48,
  :187-192), shows the raw engine error as a toast, keeps "Working out the yardage..." forever, and
  the PDF button produces no file; picking Historical downloads it. No e2e goes from a photo to an
  export.
- **Fixed by:** A3b, *One method per quilt, its reason and the straight-seam check* for the engine
  (one method per quilt, a rows fallback with a reason instead of an error), and C2a, *Your pattern
  screen with one Download pattern (PDF) button (rescopes #96, part 1)* for the download path (no
  strategy argument, a plain error with Retry, and a photo-to-PDF e2e).

#### engine-10: Modern strategy gives no sewing order and silently produces layouts that need partial seams

Major. CONFIRMED in both passes.

- **Seen:** `_decompose` turns the block `[[a,a,b],[b,c,b],[b,a,a]]` into a pinwheel that no
  straight-seam order can sew, and 20 of 400 random blocks of 4 x 4 to 6 x 6 squares did the same.
  Substeps list piece positions with no order (qrep/construct/strategies.py:534-538), and the block
  figures are identical across strategies (qrep/export/svg.py:164-207). Modern is a selectable card
  in the web app (web/src/shell/PatternPanel.tsx:34).
- **Fixed by:** A3b, *One method per quilt, its reason and the straight-seam check*. A straight-seam
  check refuses layouts that need partial seams (M-13, PS-34, PS-35); A7 deletes the modern planner.

#### engine-03 and ux-03: The pattern PDF has no figures

engine-03: major, CONFIRMED in both passes. ux-03: major, PARTIAL in pass 2.

- **Seen:** render_booklet builds only Paragraph, Spacer, PageBreak and Table flowables
  (qrep/export/pdf.py:322-337). Each booklet is 3 pages with no image, and page 1 holds only the
  quilt name and "QREP pattern booklet". The block, strip-set and assembly figures exist only in the
  CLI exporter (`qrep/export/__init__.py:43-48`); the bridge returns only the top SVG
  (qrep/bridge.py:55, :192-193). The Historical booklet's only assembly step says to sew 42 rows of
  41 cells, with no row sequence or square map, and the print plan is text with a duplicated word
  and a blank second page (PatternPanel.tsx:393, :396). docs/sprint-4/RESEARCH.md:54 found inline
  figures in 8 of 8 published patterns. Refuted part of ux-03: the SVG download does draw every
  square in its color.
- **Fixed by:** A5a, *Figure toolkit and whole-quilt figures*, after a proof that the figures render
  under Pyodide, and A5b, *Unit, strip-set, block and binding figures*; A4b carries fabric
  requirements with batting and a legend.

#### engine-07: Photo-derived instructions print fabric IDs that collide with display names

Major. CONFIRMED in both passes.

- **Seen:** qrep/construct/strategies.py:319, :422 and :535-536, qrep/export/cutlist.py:48 and
  pdf.py:157 print raw fabric ids, while the read names f0 "Fabric 1" (qrep/vision/pipeline.py:235,
  :270). A read of the demo render produces "Row 1: sew f0 f0 f1 f0 f0 left to right." beside a
  cutting row that calls f0 "Fabric 1"; a reader who takes f1 for Fabric 1 swaps the fabrics in
  every row.
- **Fixed by:** A4b, *Cover, fabric requirements and Before you begin*. Fabric letters and color
  names everywhere, and no internal ids in any instruction (C-02, C-03, C-05).

#### engine-09: Exports ignore confidence and present guessed sizes as fact

Major. CONFIRMED in both passes.

- **Seen:** a grep for confidence, provenance, size_source and guess in qrep/construct and
  qrep/export finds nothing. A read of docs/demo/render_l2.png marks its square size as a
  low-confidence guess, yet the booklet states a 68 5/8 x 82 3/8 in quilt and 1 3/8 in squares as
  fact (qrep/export/pdf.py:90-104). Only the web results screen calls the size a guess
  (web/src/shell/PhotoFlow.tsx:767).
- **Fixed by:** A4b, *Cover, fabric requirements and Before you begin*. A size-basis line and an
  uncertain-square pointer on the cover (PS-09, PS-15); A9 stores the basis and A10 fills it.

#### engine-08: Numbered steps bind before layering and quilting; pressing is barely covered

Major. CONFIRMED in both passes.

- **Seen:** the numbered steps end with "Prepare the binding" and "Bind the quilt", with no layer,
  baste or quilt step (qrep/construct/strategies.py:229-266); backing, batting and "Quilt as
  desired" appear afterwards in a separate Finishing section (qrep/export/pdf.py:223-247). Only the
  borders and the binding fold get pressing directions (strategies.py:236-237).
- **Fixed by:** A4d, *Construction steps, borders and finishing*. Finishing in sewing order, with
  A3c's pressing plan on every pressing step.

### 2.3 Major: the read, the scorer and the model

#### vision-06: Euclidean 8-bit Lab is L-dominated, so shading and folds flip cell labels

Major. PARTIAL in both passes.

- **Seen:** qrep/vision/palette.py:150 and qrep/vision/cells.py:26-38 use Euclidean distance on
  OpenCV 8-bit Lab, where L is stretched 2.55 times against a and b. With the corners and 40 x 40
  counts supplied on the Irish chain screenshot, full Lab gets about 97.6 percent of squares right,
  L\*0.5 about 99.0 and ab-only about 99.9. On the pipeline's own field grid, 8-bit Lab misreads the
  5 leftmost field columns, which the border scan then strips; reassigning with ab-only leaves none
  stripped. Refuted parts: the misread squares are brighter, not shaded, and folds were not tested.
- **Fixed by:** B2b, *Confirmed read: fabrics and the block-consistent vote*. Float CIELAB with an L
  weight of 0.5 by default on inset samples; D5 reports the weight sweep.

#### vision-11: compare.map_palettes greedy bijective mapping collapses cell accuracy when k is over-estimated (known since sprint 1, unfixed)

Major. CONFIRMED in both passes.

- **Seen:** qrep/vision/compare.py:33-50 gives each recovered fabric, darkest first, the nearest
  unused truth fabric. The L3 render reads 55 x 45 with a third, phantom fabric and scores 0.0020
  against 0.9996 under a many-to-one mapping. docs/stretch/NOTES.md:47-51 recorded this failure in
  sprint 1, and compare.py has not changed since. The error only ever understates accuracy, but
  tests/test_roundtrip.py:40 uses this scorer and the release gate needs a truthful one.
- **Fixed by:** D4a, *Eval harness: simulated confirmations and per-tier metrics*. A many-to-one
  mapping with the fabric-count mismatch reported separately, plus a min-cost assignment, in
  compare.py and the harness.

#### data-23 and approaches-23: The model holds only solid square cells, so triangle quilts cannot be represented

data-23: major, CONFIRMED in both passes. approaches-23: major, CONFIRMED in both passes.

- **Seen:** qrep/model/schema.py:58-62 documents GridRegion as "the one region type v1 implements";
  kind is a plain string (:64), each grid has one cell_size (:67) and each cell one fabric id (:68),
  and Quilt.center is a single GridRegion (:174). No model or construct code represents a triangle.
  A one-fabric square cannot carry a diagonal or curved seam, yet Jake's 0.4.0 scope adds
  half-square and quarter-square triangles and stitch-and-flip corners (HANDOFF section 2, item 1).
  Two of the three field screenshots are a curved design and a triangle star.
- **Fixed by:** B8, *Unit map in the quilt model*, before B4a and A3. data-23 is mapped as new:B8,
  approaches-23 as ticket:B8.

### 2.4 Major: the web app

#### docs-03 and approaches-30: The phone resolution cap is applied to the whole frame before cropping

docs-03: major, PARTIAL in pass 2. approaches-30: major, CONFIRMED in both passes.

- **Seen:** stage() draws the whole bitmap onto a canvas capped by web/src/model/downscale.ts:8-9
  (1400 px below a 720 px viewport, 2000 px above) and maps the user's pins onto the capped image
  only later (web/src/state/project.tsx:853-864, :894-898). The Irish chain's square pitch falls
  from 18.2 px at full resolution to 9.1 px through the Chromium canvas at the 1400 cap, under
  RESCUE_MIN_PITCH_PX = 10 (qrep/vision/verdict.py:44); with hand pins, 50 of 50 runs read at 2000
  and 27 of 50 at 1400. Refuted part of docs-03: the report's own example fails at 1400 by another
  route (a harmonic pitch), and on the shipped Chromium path that crop reads. #101 tracks the fix.
- **Fixed by:** the C3 tickets (both findings are mapped as ticket:C3). C3b, *Confirm screen in the
  photo flow, with crop-aware staging (includes #101)* crops to the confirmed frame at full
  resolution, then applies the cap; B2a accepts the crop and its offset.

#### docs-06: Every export and the failure escape live inside the editor being removed

Major. PARTIAL in both passes.

- **Seen:** PatternPanel, which holds all five download buttons
  (web/src/shell/PatternPanel.tsx:41-47, :345-350), mounts only in the two editor views
  (web/src/App.tsx:171, :215), and PhotoFlow.tsx has no download control, so deleting the editor
  first would remove every pattern output. Refuted part: the failure panel leads with "Adjust the
  crop", so "Start in the editor" is not the only escape.
- **Fixed by:** C2a, *Your pattern screen with one Download pattern (PDF) button (rescopes #96, part
  1)* (mapped as ticket:C2). Your pattern, with the one download, lands before the editor is removed
  (C2 before C6).

#### web-09: Analyze is enabled before the photo is staged

Major (pass 2 lowered it from critical). CONFIRMED in both passes.

- **Seen:** the Analyze button has no disabled state (web/src/shell/PhotoFlow.tsx:821-828). stage()
  shows the crop screen before decoding finishes and sets stagedBytesRef only at
  web/src/state/project.tsx:863, and cancel() keeps the old bytes (:983-993). On the live site,
  Cancel, then a new photo, then a click within about 0.1 to 0.4 s read the previous photo:
  "readable, 65 x 64" next to the new image. Pass 2 lowered the severity because a person rarely
  clicks that fast.
- **Fixed by:** C3b, *Confirm screen in the photo flow, with crop-aware staging (includes #101)*.
  Staging clears the old bytes and token first, Continue stays disabled until the photo is staged,
  and each read is bound to a staging sequence, with a stale-photo e2e.

#### ux-16: Non-image and corrupt files are accepted until Analyze

Major for the stale-bytes path only (pass 2); the rest of the finding is minor. CONFIRMED in both
passes.

- **Seen:** a .txt file and a corrupt JPEG reach the crop screen, and the error appears only after
  Analyze (web/src/state/project.tsx:849-851, :875-879, :933-935); `accept="image/*"`
  (web/src/shell/PhotoFlow.tsx:137) contradicts the "JPG or PNG" copy (:132). Pass 2 ran the
  stale-bytes path live: Cancel, then a file the browser cannot decode, then Analyze showed the
  previous photo's read ("185 x 165 squares") next to the broken image, because cancel() and a
  failed decode both keep the old bytes (project.tsx:983-993, :852-880).
- **Fixed by:** C3b, *Confirm screen in the photo flow, with crop-aware staging (includes #101)*.
  Decode at drop with errors shown on the dropzone, an accept list that matches the copy, and the
  stale-bytes path closed with an e2e.

#### web-04: Results screen never offers the uncertain-squares toggle

Major. CONFIRMED in both passes.

- **Seen:** uncCount reads the editor model's count (web/src/shell/PhotoFlow.tsx:338;
  web/src/state/project.tsx:1154, :1739), which is 0 during the photo flow, so the toggle never
  renders. On the live site the results screen shows no toggle where the editor later reports 4,081,
  1,153 and 1,770 uncertain squares for three fixtures. web/e2e/photo.spec.ts:75-77 checks only the
  exact L0 render, so the e2e cannot catch it.
- **Fixed by:** C2a, *Your pattern screen with one Download pattern (PDF) button (rescopes #96, part
  1)*. The flagged-squares count on Your pattern comes from the read result; C3c switches it to the
  engine's fit flags.

#### web-01 and ux-09: Yardage amounts are cut off on desktop, and the Pattern tab inherits PalettePanel styles

web-01: major, CONFIRMED in both passes. ux-09: major, CONFIRMED in both passes.

- **Seen:** the nowrap name and amount columns (web/src/shell/PatternPanel.tsx:78, :81) make a 428
  px table inside the 376 px side panel (web/src/index.css:407-413). At 1280, 1366 and 1440 px the
  amounts run past the viewport edge (at 1440 the binding's "3/4 yd" shows as "3"), and hidden
  header tooltips that still take up space (web/src/ui/tokens.css:265-283) let every desktop page
  scroll 46 px sideways at 1440. Separately, PalettePanel stays mounted while hidden
  (web/src/App.tsx:165-167), and its global `.pp-*` rules restyle the Pattern panel.
- **Fixed by:** C2b, *Fabric widths, finished size and shopping lines on Your pattern (rescopes #96,
  part 2)*. The amounts stay inside their column at 1280, 1366, 1440 and 390 px; C6a deletes
  PalettePanel, and C10 fixes the tooltip overflow (ux-17).

#### ux-08: First visit silently downloads 25.4 MB; a cold phone user waits about 44 s on an uninformative spinner

Major. CONFIRMED in both passes.

- **Seen:** the live landing makes 23 requests totaling 25.4 MB with no user action, including the
  11.7 MB OpenCV wheel, which is prefetched once the engine is ready
  (web/src/state/project.tsx:733-746, as PARITY.md item 17 requires). On a phone throttled to 5
  Mbps, "Finding your quilt..." shows for about 45 s with no progress
  (web/src/shell/PhotoFlow.tsx:811-816), and the start screen's "about 12 MB"
  (web/src/shell/StartScreen.tsx:169-170) leaves out about 13.7 MB of base engine.
- **Fixed by:** C8b, *Vision loading and first-run weight*. C8b keeps the idle prefetch (plan
  section 4.5) and adds byte progress and the full first-run size to the loading copy.

#### web-07: Worker RPC has no timeouts, no error channel, and drops diagnostics

Major. CONFIRMED in both passes.

- **Seen:** WorkerLike exposes no onerror (web/src/engine/rpc.ts:46-50), call() has no timeout
  (:131-142), and web/src/engine/worker.ts:198-206 and qrep/bridge.py:106-107 replace errors with
  generic text while nothing logs. On the live site, after the worker was killed, the PDF button
  stayed on "Making it..." for 25 s with the engine chip busy and no Retry.
- **Fixed by:** C8a, *Engine calls: error channel, timeouts and plain errors*. An error channel,
  per-call timeouts with Retry, typed errors and bridge-side logging.

#### web-12: Vision failures are retried forever, classified by message text

Major. PARTIAL in both passes.

- **Seen:** web/src/state/project.tsx:748-749 classifies errors by /vision/i, and :767-801 loops
  with no cap. Refuted part: the loop never runs, because Pyodide's loadPackage logs a failed
  download without throwing, so web/src/engine/worker.ts:77-78 reports vision as ready. The real
  defect is worse for the user: after a failed download the app reports vision ready, blames the
  photo ("That photo didn't come through"), and never fetches the wheel again while the worker
  lives.
- **Fixed by:** C8b, *Vision loading and first-run weight*. Verify the cv2 import after loadPackage,
  raise a typed vision error, cap retries with backoff, and show an offline message.

#### web-03: Compare lightbox (in the editor) and round-trip panel render unstyled

Major. CONFIRMED in both passes.

- **Seen:** the `.pf-lb*` and `.pf-rt*` rules live only in PF_CSS
  (web/src/shell/PhotoFlow.tsx:1053-1217), which is injected only while PhotoFlow is mounted
  (web/src/App.tsx:254-255). In the editor the lightbox renders inline under the canvas, 1,698 px
  tall with default buttons, and widens the page; no e2e opens it.
- **Fixed by:** C1b, *One file per photo-flow screen, each with its own stylesheet*. The lightbox
  styles move into its own stylesheet, with an e2e that asserts position fixed; RoundTripPanel goes
  with C6a.

## 3. Findings in code scheduled for deletion

55 findings sit in code that sprint 5 deletes. Plan section 4.4 deletes code only after its
replacement is live (expand, then contract), so each finding closes in one of two ways: the deletion
removes the defect (`deletion-note`), or a replacement ticket carries the lesson forward so the new
code cannot repeat it (`ticket` or `new`). The groups follow the ticket that deletes the code. Where
an engine half and a web half go in different tickets, the entry names both.

### 3.1 B6b, *Delete the automatic detection stack* (41 findings)

Critical and major findings, with what was seen:

- **vision-01** (critical, CONFIRMED in both passes): on the 44 committed photoreal fixtures, 12 of
  25 "readable" verdicts are wrong (wrong dims, under 95 percent of squares right, or a curved quilt
  read as squares), and the 12 right ones are all the same Irish chain render on different
  backgrounds. No test asserts recovered dims or square accuracy. With the fixtures' own corners
  supplied, 10 of 29 "readable" verdicts are wrong. Closes by deletion; D4a and D5 score the new
  read against truth (plan section 7.2, G1 and G2).
- **vision-02** (critical, CONFIRMED in both passes): with hand corners, the Irish chain screenshot
  reads "readable" through the corroboration rescue (qrep/vision/verdict.py:88-96) as 44 x 41 with
  one border band where the photo has three; 30 of 30 jittered placements read "readable" and none
  gave the true 40 x 40. Carried forward by B2a (field corners or the outer edge, plus bands and
  counts); the photo stays a private regression case (D3c).
- **tests-01** (critical, PARTIAL in both passes): no test scores a read against the truth the
  repo's sidecars already hold, and 10 of 28 synthetic squares fixtures read "readable" but wrong
  (the report's 11 counted one fixture that only the greedy scorer of vision-11 marks wrong).
  Carried forward by D4a.
- **vision-04** (major, pass 2 lowered it from critical; PARTIAL): qrep/vision/verdict.py:95-96
  returns before coherence is consulted whenever periodicity is under T2, so the curves check is
  skipped on every real photo. The curved fixtures that read "readable" actually reach that check
  and slip past it, a miss already counted in vision-01. Closes by deletion; the C4 picker and the
  B4b signal refuse curves up front.
- **vision-05** (major, CONFIRMED in both passes): the border scan stops at the first non-uniform
  strip and eats misread field columns (qrep/vision/borders.py:41-59), and
  qrep/vision/pipeline.py:237-245 averages the four sides, zeros included, into one band of one
  fabric. Carried forward by B2a: borders come from geometry as a list of bands set inward.
- **vision-07** (major, CONFIRMED in both passes): the lighting detrend fits palette centers on a
  corrected copy but assigns squares on raw pixels (qrep/vision/palette.py:113-150,
  pipeline.py:197); 46 of 48 gated test layouts lost accuracy. It is latent on the three field
  photos, where the gate never fired. Carried forward by B2b: one label-aware shading correction for
  both the palette and the assignment.
- **vision-10** (major, CONFIRMED in both passes): tiered quad detection returns the full frame
  (tier 3) on all three field screenshots after 0.7 to 3 s, and runs again inside reverse() when the
  user leaves the pins untouched (qrep/vision/rectify.py:457-472; web/src/state/project.tsx:867,
  :896-897). Closes by deletion; C3 starts the pins at a neutral inset.
- **tests-03** (major, CONFIRMED in both passes): tests/test_corroboration_s2.py pins known-wrong
  outputs as expected (antique_wash_chain and a curved fixture as "readable" at :367-386, true
  squares quilts as no_grid at :272-294), so a fix for open issue #82 fails CI. Closes by deletion;
  #82 closes as superseded.
- **tests-06** (major, CONFIRMED in both passes): the highest grid confidence in the corpus, 0.979,
  belongs to a wrong read of a curved quilt, and every wrong "readable" squares read clears T1 =
  0.60 (qrep/vision/verdict.py:14). Carried forward by D4a: a confident-wrong squares rate per tier
  (G2).
- **ux-01** (major, CONFIRMED in both passes): on all three field screenshots the detected pins snap
  to the full frame, phone chrome included, and every default run ends in no_grid; only the
  synthetic sample reads (99 percent). Carried forward by C3b, and the dropzone stops promising that
  shop-listing screenshots work; the web half goes with C6b, and D3b and D5 gate real photos.
- **data-16** (major, CONFIRMED in both passes): the automatic read returns no grid on 16 of 16 CC0
  museum photos, including a straight-set Double Irish Chain that matches the benchmark fixture.
  Carried forward by D4a: the 834d8be run becomes the before scorecard.
- **data-20** (major, CONFIRMED in both passes): with corners read by eye and the true fabric count,
  that Double Irish Chain still gives no grid, because the estimator locks onto the 5-square block
  period (80 to 84 px against squares of about 16 px). Carried forward by B2a: confirmed counts
  replace the inferred pitch.
- **approaches-24** (major, CONFIRMED in both passes): reverse() with no corners gives tier 3 and
  no_grid on all three field screenshots, natively, through the Chromium canvas at both caps, and
  under Pyodide. Carried forward by D3c: the three screenshots join the private tier with their own
  truth.
- **approaches-28** (major, pass 2 lowered it from critical; PARTIAL): the curved Mill Wheel's
  "honest" refusal depends on pin placement; 7 of 153 jittered full-resolution placements read a
  false "readable" through the rescue, though none did at the web caps. Carried forward by D4a:
  refusal recall measured with the simulated picker answer (G4).
- **approaches-31** (major, CONFIRMED in both passes): the phone cap shrinks the pinned Irish chain
  to about 9.1 px squares, under the 10 px rescue floor, and the verdict flips with the resampling
  filter. Carried forward by D4b: eval inputs are decoded through the browser path at both caps.

Minor and nit findings, and the refuted one:

| Finding | Severity | Verdict | Title | Closes by |
|---|---|---|---|---|
| vision-08 | minor (was major) | CONFIRMED / CONFIRMED | block_period_cells comes from the image period, not the label repeat, so the UI repeat caption is wrong on the real photo | carried forward by B2b |
| vision-09 | minor | CONFIRMED | Period feedback adopts texture-scale pitches on real photos | deletion note on B6b |
| vision-12 | minor (was major) | CONFIRMED / PARTIAL | Real curved quilt gets the wrong failure reason; S2's non_square_content never fires on it | deletion note on B6b |
| vision-14 | minor (was major) | CONFIRMED / PARTIAL | Star photo trips the isotropy guard at 7.0 vs 7.5 px and the UI shows steep-angle copy for a frontal photo | deletion note on B6b |
| vision-17 | minor | PARTIAL | Wasted recompute and full-resolution 9-config SNR ladder on failing reads | deletion note on B6b |
| vision-18 | nit | CONFIRMED | Failure reason derived by matching the exception text | carried forward by B2a |
| vision-19 | nit | CONFIRMED | Dead code and a wrong annotation | carried forward by B2b |
| vision-20 | nit | CONFIRMED | Duplicated logic across modules and scripts | deletion note on B6b |
| tests-07 | minor | CONFIRMED | Sprint-4 S1/S2 tests are 63% of suite time and doubled CI, with no field-photo payoff | deletion note on B6b |
| tests-08 | minor | PARTIAL | 37% of suite wall is repeated reverse() on identical inputs | deletion note on B6b |
| tests-11 | minor | CONFIRMED | Observed-output thresholds and ratchets, against the repo's own rule | deletion note on B6b |
| tests-13 | minor | CONFIRMED | Negative-control coverage gap: degraded_busy_print_2000 is falsely 'readable' | deletion note on B6b |
| tests-14 | minor | CONFIRMED | Implementation-detail pins break on any refactor | carried forward by A8 (new) |
| tests-15 | minor | CONFIRMED | Block-lattice algorithm is implemented twice (production plus a test fixture copy) | deletion note on B6b |
| tests-20 | nit | CONFIRMED | Dead code in test_repeats_verdict | deletion note on B6b |
| docs-04 | minor (was major) | CONFIRMED / PARTIAL | The false 'steep angle' reason still fires on frontal screenshots | deletion note on B6b |
| data-17 | minor | PARTIAL | 11 of 16 photos fell to rectify tier 3 | deletion note on B6b |
| data-18 | minor (was major) | PARTIAL / PARTIAL | Square-cell quilts all no_grid, but 2 of the 7 are on-point | carried forward by D3a |
| data-19 | minor | CONFIRMED | Higher resolution (2000 px) does not help | carried forward by D4a |
| data-48 | minor | PARTIAL | Crop screen does not surface detection failure | carried forward by B2a; the web half goes with C6b |
| approaches-26 | minor | CONFIRMED | The field smoke test measured only the automatic full-frame path | carried forward by D4a |
| approaches-27 | minor | CONFIRMED | Pinned Double Irish Chain reads only through the S2 corroboration rescue | carried forward by D3c |
| approaches-37 | minor | CONFIRMED | On screenshots the proposed quad is the whole frame | carried forward by C3 (plan: C3b); the web half goes with C6b |
| approaches-38 | minor | PARTIAL | Per-stage confidence meters and a verdict taxonomy, unlike every analog | deletion note on B6b |
| approaches-39 | major | REFUTED | The existing non_square_content diagnosis cannot flag triangles and curves before the grid step | UNMAPPED (refuted; section 5) |
| approaches-58 | minor | PARTIAL | The planned removals and the fate of the frozen thresholds | handled by B6b's acceptance criteria |

### 3.2 C6b, *Remove the old photo-flow screens and the web verdict surface* (6 findings)

Critical and major findings, with what was seen:

- **web-05** (critical, CONFIRMED in both passes): a 65 x 64 read of a 45 x 55 fixture shows as a
  normal success, "Overall confidence 67% - needs your eye", with Open in the editor as the main
  button, and a 46 x 56 read shows "90% - solid". The readable branch has no warning layout
  (web/src/model/verdictStory.ts:138-147), and the pill is the mean of six stage confidences
  (web/src/shell/PhotoFlow.tsx:61-71). Carried forward by C2a: no averaged pill or stage meters,
  flags instead; C6b deletes the web surface and B6b the engine half.
- **ux-14** (critical, PARTIAL in pass 2): the "85% - solid" read of the Irish chain screenshot has
  one cream border where the photo shows blue, cream and blue bands, misreads the bottom two rows,
  and says the quilt repeats about 20 times across where the true 10-square repeat gives 4. Pass 2
  refuted the grey-colors sub-claim. Carried forward by C2a: the census shows the engine's fabric
  letters and color names, shared with the PDF; D3b and D5 score borders, edge rows and colors.
- **ux-05** (major, CONFIRMED in both passes): failure screens show "Very sure" stage meters under
  "Could not read this photo", and a readable read shows "85% - solid" while three of its stages say
  "Check it" (the pill is a mean; web/src/shell/PhotoFlow.tsx:54-71, :472-493). Carried forward by
  C2a; C6b deletes the meters.

Minor findings:

| Finding | Severity | Verdict | Title | Closes by |
|---|---|---|---|---|
| web-08 | minor (was major) | CONFIRMED / CONFIRMED | Progress screen shows six spinners that never fill (deviates from PARITY item 14) | carried forward by C3c |
| ux-07 | minor (was major) | CONFIRMED / CONFIRMED | Failure reasons name the wrong cause, and the tips omit the real fix | carried forward by C3c |
| ux-13 | minor | CONFIRMED | Progress screen never progresses stage by stage | carried forward by C3c |

### 3.3 C6a, *Remove the editor (archived at archive/editor-v0.3)* (5 findings)

Major findings, with what was seen:

- **web-02** (major, CONFIRMED in both passes): with a quilt open on a 390 px phone, Open and Save
  widen the header to 470 px (web/src/shell/Header.tsx:140-159), the layout viewport grows to 470
  px, and the fixed tab bar falls below the visible screen. Closes by deletion; C10's 390 px
  no-overflow guard keeps it from returning.
- **ux-04** (major, CONFIRMED in both passes): the same overflow seen from the phone editor: the tab
  bar, the only route to Pattern and the downloads, sits off-screen. Carried forward by C10 (new):
  the residual header overflow during boot is fixed and guarded by a no-overflow e2e.

Minor and nit findings, and the refuted one:

| Finding | Severity | Verdict | Title | Closes by |
|---|---|---|---|---|
| web-10 | minor | CONFIRMED | Resume banner goes stale after Home | deletion note on C6a |
| web-21 | minor | CONFIRMED | Editing-only bugs (moot after removal): Ctrl+Z hijacks text fields; blur commits a no-op resize | deletion note on C6a |
| ux-10 | nit | REFUTED | Tap-to-paint is ignored on touch; squares are 5.86 px at Fit on a phone | UNMAPPED (refuted; section 5) |

### 3.4 A7, *Engine cleanup (contract)* (3 findings)

No critical or major finding:

| Finding | Severity | Verdict | Title | Closes by |
|---|---|---|---|---|
| engine-12 | minor (was major) | CONFIRMED / CONFIRMED | Locked resize misses the requested size and disagrees with apply_finished_size (editing path) | deletion note on A7 |
| engine-23 | nit | CONFIRMED | Dead or misleading fields, helpers and stubs | handled by A7's acceptance criteria |
| engine-24 | nit | CONFIRMED | Viewer package is a superseded sprint-1 editor that is still tested and published | deletion note on A7 |

## 4. Process findings and where they went

137 findings concern how the work runs rather than what the product does: tests and CI, tracking,
docs, corpus sources and licensing, and the overnight tooling. They went to the corpus and eval
tickets, the docs pass, the overnight protocol documents, the setup PRs, or no action with a reason.

Critical and major findings (18 survive both passes; 3 were refuted, see section 5):

- **tests-09** (major): main is unprotected; the branch-protection API returns 404 and there are no
  rulesets, so green CI is advisory. Went to protocol:ORCHESTRATOR: setup step 5 protects main
  (required checks, non-strict, admins enforced) before the dry run, and E4 re-checks it.
- **tests-05** (major): ruff is unpinned (pyproject.toml:26-30), and ruff 0.16.10 reports 99 errors
  on main, so the next CI run fails Lint. No action beyond setup: the toolchain PR for #105 pins
  ruff 0.15.20 in constraints.txt, and every CI install uses that file.
- **tests-10** (major): the bless rule is honor-system and covers only tests/golden; the photoreal
  fixtures, the legacy pins and the wasm reference regenerate in place (tests/conftest.py:11-40 is a
  local switch, and ci.yml has no guard). Went to new:E5, *Guard frozen fixtures, not only goldens*.
- **vision-03, tests-02 and docs-02** (major): no real quilt photo with ground truth exists in the
  repo (44 of its 50 tracked images are generator.py output), and every threshold is calibrated on
  synthetic renders (qrep/vision/grid.py:18-23, qrep/vision/palette.py:17-24,
  qrep/vision/verdict.py:14-44). Went to ticket:D3b: human-verified truth and hand-authored gold
  layouts for every gated photo.
- **data-11** (major): the V&A terms rule out corpus use (non-commercial only, a 768 px cap, no
  caching past four weeks). Went to ticket:D3a, which rejects the source.
- **data-38 and data-41** (major): never copy modern block diagrams, instructions, cutting charts,
  designer patterns or a designer quilt's layout, and keep rights-unclean material out of the repo.
  Went to protocol:WORKER (the DO NOT COPY list); #105's corpus guard blocks private-tier paths.
- **data-39** (major): free fabric-company patterns are licensed for personal use only, so they
  serve only as private cross-checks. Went to ticket:D6, which publishes aggregate numbers only.
- **data-55** (major): Boisson v. Banian (2d Cir. 2001) protects a specific quilt's layout together
  with its colors. Went to ticket:D3a: no photo or cell model of a modern designer quilt is
  committed.
- **data-59** (major, PARTIAL in pass 2): the list of excluded sources. Pass 2 found that Mia's own
  open-access page allows reuse of its public-domain images, so that exclusion does not hold as
  stated. Went to ticket:D3a, which encodes the exclusions in the fetch allowlist and the license
  vocabulary; Mia images stay out until Mia confirms its terms in writing (data-05).
- **data-60** (major, PARTIAL in pass 2): the local shop screenshots stay private. Went to
  ticket:D3c, which keeps them in the gitignored private tier; the corpus guard blocks
  local-photos/.
- **orchestration-01, -07, -08, -17 and -31** (major): background sessions, worktree isolation,
  message delivery, per-session permissions, and the version floor for cross-session messaging on
  native Windows (2.1.234 or later; the command-line tool on PATH printed 2.1.204). Went to
  protocol:ORCHESTRATOR, whose sections 2, 8, 9, 11 and 13 encode each corrected mechanism.

All 137 process findings by destination:

| Destination | Count | Findings |
|---|---|---|
| protocol:ORCHESTRATOR | 35 | tests-09, tests-24, docs-11, docs-15, docs-16, orchestration-01, orchestration-03, orchestration-04, orchestration-05, orchestration-06, orchestration-07, orchestration-08, orchestration-09, orchestration-10, orchestration-12, orchestration-13, orchestration-14, orchestration-16, orchestration-17, orchestration-19, orchestration-20, orchestration-21, orchestration-23, orchestration-24, orchestration-27, orchestration-28, orchestration-29, orchestration-31, orchestration-32, orchestration-34, orchestration-36, orchestration-39, orchestration-42, orchestration-43, orchestration-44 |
| protocol:WORKER | 6 | data-29, data-30, data-38, data-41, orchestration-02, orchestration-15 |
| ticket:A7 | 1 | tests-18 |
| ticket:C3 (plan: C3b, which includes #101) | 1 | approaches-32 |
| ticket:C6a | 1 | web-25 |
| ticket:C7 | 1 | docs-10 |
| ticket:D1 | 4 | data-15, data-32, data-62, data-63 |
| ticket:D3a | 31 | tests-04, data-01, data-02, data-03, data-04, data-05, data-06, data-09, data-10, data-11, data-12, data-13, data-14, data-22, data-26, data-27, data-28, data-36, data-42, data-45, data-46, data-50, data-51, data-54, data-55, data-56, data-57, data-58, data-59, approaches-22, approaches-25 |
| ticket:D3b | 6 | vision-03, tests-02, docs-02, data-25, data-37, data-47 |
| ticket:D3c | 1 | data-60 |
| ticket:D4a | 4 | vision-13, vision-21, data-43, data-44 |
| ticket:D5 | 1 | data-49 |
| ticket:D6 | 1 | data-39 |
| ticket:E2 | 7 | tests-23, docs-07, docs-09, docs-12, docs-13, docs-14, docs-20 |
| ticket:E4 | 1 | docs-17 |
| new:C10 | 1 | web-20 |
| new:E5 | 1 | tests-10 |
| new:E6 | 3 | engine-25, tests-16, tests-17 |
| ticket:#105 | 1 | orchestration-30 |
| no-action (reasons in Appendix A) | 9 | data-07, data-21, data-31, data-33, data-34, data-35, approaches-54, approaches-55, approaches-56 |
| no-action: answered | 2 | orchestration-40, orchestration-41 |
| no-action: bypass | 1 | orchestration-11 |
| no-action: fixed by setup PR #105 | 4 | web-19, tests-05, docs-18, docs-19 |
| no-action: handled by governance PR #106 | 1 | docs-08 |
| no-action: informational | 3 | orchestration-22, orchestration-33, orchestration-35 |
| no-action: not used | 3 | orchestration-18, orchestration-37, orchestration-38 |
| no-action: speed only | 1 | tests-22 |
| no-action: superseded | 2 | orchestration-25, orchestration-26 |
| UNMAPPED | 4 | data-08, data-40, data-52, data-61 |

## 5. Refuted and unverifiable findings

10 findings are refuted and 10 are unverifiable. None drives a ticket; the dispositions of the
orchestration ones record how the protocol uses the corrected fact.

**Refuted (10)**

| Finding | Severity | Title | Why it fails | Disposition |
|---|---|---|---|---|
| ux-10 | nit | Tap-to-paint is ignored on touch; squares are 5.86 px at Fit on a phone | Below 14 px squares a touch tap zooms toward the tap by design (web/src/viewer/QuiltCanvas.tsx:22-27, :759-776); it is not ignored. Only the 5.86 px measurement holds, and the editor goes with C6a. | UNMAPPED |
| approaches-33 | minor (was major) | A single global grid drifts at the photo edges | The numbers reproduce, but the cause is color, not drift: all 51 disagreeing left-edge squares are blue read as white, reclassifying that region with an ab-only distance scores 0.996 to 1.000, and the grid lines sit 0.3 to 3 px from the color edges, not half a square. A local refit stays a hypothesis that B5 measures. | UNMAPPED |
| approaches-39 | major | The existing non_square_content diagnosis cannot flag triangles and curves before the grid step | The non_square_content diagnosis is set only after grid estimation and only when corroboration ran (qrep/vision/pipeline.py:305-342); it fired in 0 of 69 pinned Star runs and 41 of 130 pinned Mill Wheel runs, so it cannot refuse triangles and curves early. | UNMAPPED |
| orchestration-13 | major | Context rotation: auto-compaction | The tool compacts automatically as a session nears its limit (its context-window documentation); the 12 percent summary size is a constant in a simulation, not documented behavior. | protocol:ORCHESTRATOR |
| orchestration-22 | minor | Permissions: config precedence | Managed settings rank highest, above command-line flags; the report put them below user settings. | no-action: informational |
| orchestration-29 | minor | Recommended setup: context management | Workers do not clean up on exit: a worktree that holds work prompts before removal, and the background sweep waits for cleanupPeriodDays (3650 on this machine). | protocol:ORCHESTRATOR |
| orchestration-36 | major | Open question: VS Code tabs launched programmatically | The VS Code extension registers an /open URI handler that opens a tab with an optional pre-filled prompt (extension 2.1.289 and its documentation), so tabs can be opened programmatically. | protocol:ORCHESTRATOR |
| orchestration-39 | major | Open question: VS Code tab from a URI (/new path) | The handler accepts only /open and /install-plugin; a /new URI does nothing, and /open is the documented path. | protocol:ORCHESTRATOR |
| orchestration-40 | nit | Open question: --fork-session and MEMORY.md | Answerable from the documentation: memory is stored per project, so a forked session reads the same MEMORY.md. | no-action: answered |
| orchestration-41 | minor | Open question: approvals from background agents | Answerable from the documentation: on Windows an approval granted in a worktree stays with that worktree, and bypass mode raises no approvals. | no-action: answered |

**Unverifiable (10)**

| Finding | Severity | Title | Why it cannot be settled | Disposition |
|---|---|---|---|---|
| data-08 | nit | Other museums and aggregators: unverified | Brooklyn, Newfields, Yale, the American Folk Art Museum, Europeana and DPLA were never sampled, and no saved response exists to check. | UNMAPPED |
| data-40 | minor | Other fabric-company terms unverified | The Moda, Andover and Riley Blake terms pages returned 403 and 404; personal-use-only is a conservative default, not a verified fact. | UNMAPPED |
| data-52 | nit | Effort estimates | Effort estimates for fetching, annotation and gold matrices have no timing evidence; plan section 9 re-measures the rate with a 10-photo pilot. | UNMAPPED |
| data-53 | nit | Pattern-name matching against a hand-authored catalog | A proposal (match recovered blocks against a hand-authored catalog) with nothing to measure; pattern naming is outside 0.4.0. | UNMAPPED |
| data-61 | minor | Legal note 8: Jake's own quilt photos can be CC0 | A legal assessment (Jake's photos of quilts he owns can be dedicated CC0; non-traditional designs need the maker's written OK) that a verifier cannot confirm; plan section 8.1 adopts its conservative rule. | UNMAPPED |
| approaches-10 | nit | Liu, Hodgins, McCann NPAR 2017: whole-cloth quilting stitch paths | The cited NPAR 2017 page returned 403, and no copy exists in the evidence. | UNMAPPED |
| approaches-11 | nit | Gokhale (SPIE): crazy vs non-crazy quilt classification | The cited SPIE profile returned empty content, so the classifier and its 39 images cannot be checked. | UNMAPPED |
| approaches-53 | nit | A VLM cannot run inside Pyodide | Untested: the only observation is that the vendored wheels hold no ML runtime; whether any VLM could run under Pyodide was not tried. VLMs are outside 0.4.0. | UNMAPPED |
| orchestration-37 | nit | Open question: --remote-control from the Windows CLI | Testing --remote-control needs a live session tied to Jake's account, which a read-only check cannot start; sprint 5 does not use it. | no-action: not used |
| orchestration-38 | nit | Open question: hooks spawning background agents | Testing a hook that spawns background sessions needs a live hook, which a read-only check cannot install; sprint 5 does not use it. | no-action: not used |

## 6. Round 2: review of the narrowed codebase (E3)

Not started. Ticket E3 appends its round counts by severity and lens, with each finding's ticket,
below this paragraph, and leaves the sections above unchanged.

## Appendix A: every finding

Verdict shows pass 1, then pass 2 where it ran. Severity is final, with the pass-1 value when pass 2
changed it. A disposition of `ticket:C3` or `ticket:C2` names a ticket family that the plan split;
the note in parentheses gives the ticket that cites the finding.

| ID | Title | Verdict | Severity | Fate | Disposition |
|---|---|---|---|---|---|
| vision-01 | Verdict tree certifies wrong recoveries as readable (12 of 25 readable verdicts wrong on committed fixtures) | CONFIRMED / CONFIRMED | critical | deleted-code | deletion-note:B6b |
| vision-02 | Hand-cropped real Irish chain reads 'readable' with wrong dims and borders (the hand-crop claim is refuted) | CONFIRMED / CONFIRMED | critical | deleted-code | ticket:B2a |
| vision-03 | No real ground truth anywhere; every threshold is calibrated on synthetic renders | CONFIRMED / CONFIRMED | major | process | ticket:D3b |
| vision-04 | Frozen tree skips the squares-vs-curves check whenever periodicity < T2, so curved quilts read readable | CONFIRMED / PARTIAL | major (was critical) | deleted-code | deletion-note:B6b |
| vision-05 | Border scan deletes real field columns and misses wavy edges; multi-band borders collapse to one band | CONFIRMED / CONFIRMED | major | deleted-code | ticket:B2a |
| vision-06 | Euclidean 8-bit Lab is L-dominated, so shading and folds flip cell labels | PARTIAL / PARTIAL | major | survives | ticket:B2b |
| vision-07 | Lighting detrend fits palette centers on corrected pixels but cells are sampled from raw pixels | CONFIRMED / CONFIRMED | major | deleted-code | ticket:B2b |
| vision-08 | block_period_cells comes from the image period, not the label repeat, so the UI repeat caption is wrong on the real photo | CONFIRMED / CONFIRMED | minor (was major) | deleted-code | ticket:B2b |
| vision-09 | Period feedback adopts texture-scale pitches on real photos | CONFIRMED | minor | deleted-code | deletion-note:B6b |
| vision-10 | Auto quad detection fails on all three real screenshots, costs about 1 to 1.8 s, and runs twice per web photo | CONFIRMED / CONFIRMED | major | deleted-code | deletion-note:B6b |
| vision-11 | compare.map_palettes greedy bijective mapping collapses cell accuracy when k is over-estimated (known since sprint 1, unfixed) | CONFIRMED / CONFIRMED | major | survives | ticket:D4a |
| vision-12 | Real curved quilt gets the wrong failure reason; S2's non_square_content never fires on it | CONFIRMED / PARTIAL | minor (was major) | deleted-code | deletion-note:B6b |
| vision-13 | Smoke script's evidence line does not measure what the pipeline used | CONFIRMED | minor | process | ticket:D4a |
| vision-14 | Star photo trips the isotropy guard at 7.0 vs 7.5 px and the UI shows steep-angle copy for a frontal photo | CONFIRMED / PARTIAL | minor (was major) | deleted-code | deletion-note:B6b |
| vision-15 | User corners outside the frame slice with negative indices in the identity path | CONFIRMED | minor | survives | ticket:B2a |
| vision-16 | Unvalidated fabrics option: k=1 reports palette confidence 1.0, and 0 or a float gives an internal error | CONFIRMED | minor | survives | ticket:B2b |
| vision-17 | Wasted recompute and full-resolution 9-config SNR ladder on failing reads | PARTIAL | minor | deleted-code | deletion-note:B6b |
| vision-18 | Failure reason derived by matching the exception text | CONFIRMED | nit | deleted-code | ticket:B2a |
| vision-19 | Dead code and a wrong annotation | CONFIRMED | nit | deleted-code | ticket:B2b |
| vision-20 | Duplicated logic across modules and scripts | CONFIRMED | nit | deleted-code | deletion-note:B6b |
| vision-21 | Eval harness code ships in the production wheel | PARTIAL | nit | process | ticket:D4a |
| vision-22 | A period-1 'repeat' counts as a found repeat | CONFIRMED | minor | survives | ticket:B2b |
| engine-01 | PDF cutting table tells strip-strategy quilters to cut every square individually | CONFIRMED / CONFIRMED | critical | survives | ticket:A4c |
| engine-02 | Yardage is area divided by WOF with no strip packing or margin and runs short under standard cutting | CONFIRMED / CONFIRMED | major | survives | ticket:A2b |
| engine-03 | Pattern PDF has no figures and the web delivers only the top SVG | CONFIRMED / CONFIRMED | major | survives | ticket:A5a |
| engine-04 | The web's default strip strategy errors on a third of readable photo reads | CONFIRMED / CONFIRMED | major | survives | ticket:A3b |
| engine-05 | Strip sets never merge same-fabric runs | PARTIAL / PARTIAL | major | survives | ticket:A3a |
| engine-06 | Borders longer than WOF have no piecing instructions | CONFIRMED / CONFIRMED | major | survives | ticket:A2b |
| engine-07 | Photo-derived instructions print fabric IDs that collide with display names | CONFIRMED / CONFIRMED | major | survives | ticket:A4b |
| engine-08 | Numbered steps bind before layering and quilting; pressing is barely covered | CONFIRMED / CONFIRMED | major | survives | ticket:A4d |
| engine-09 | Exports ignore confidence and present guessed sizes as fact | CONFIRMED / CONFIRMED | major | survives | ticket:A4b |
| engine-10 | Modern strategy gives no sewing order and silently produces layouts that need partial seams | CONFIRMED / CONFIRMED | major | survives | ticket:A3b |
| engine-11 | Block inference has no plausibility gate | CONFIRMED / CONFIRMED | major | survives | ticket:A3a |
| engine-12 | Locked resize misses the requested size and disagrees with apply_finished_size (editing path) | CONFIRMED / CONFIRMED | minor (was major) | deleted-code | deletion-note:A7 |
| engine-13 | Backing considers only vertical seams; WOF labels are hard-coded to 42 in | CONFIRMED / CONFIRMED | major | survives | ticket:A1 |
| engine-14 | Yardage and related math are computed several ways that disagree | CONFIRMED | minor | survives | ticket:A2b |
| engine-15 | Difficulty and time metrics shown to users are misleading | CONFIRMED | minor | survives | ticket:A4a |
| engine-16 | Bridge boundary misclassifies bad input and can mask engine bugs | CONFIRMED | minor | survives | ticket:E1a |
| engine-17 | Modern greedy is super-linear and the web plans every strategy on every revision | CONFIRMED | minor | survives | ticket:A3b |
| engine-18 | Strip-set SVG crosscut marks stop short; fallback assembly SVG is malformed | CONFIRMED | minor | survives | ticket:A5b |
| engine-19 | Modern cut list lists rotated duplicates as separate lines | CONFIRMED | minor | survives | ticket:A2b |
| engine-20 | CLI-path PDF is not deterministic; python -m qrep.cli is a silent no-op | CONFIRMED | minor | survives | ticket:A4a |
| engine-21 | L3 renders skip L2 perspective; the sample demo is circular | CONFIRMED | minor | survives | ticket:C9 |
| engine-22 | Sizing math exists in four implementations with drifting clamps | CONFIRMED | minor | survives | new:A10 |
| engine-23 | Dead or misleading fields, helpers and stubs | CONFIRMED | nit | deleted-code | ticket:A7 |
| engine-24 | Viewer package is a superseded sprint-1 editor that is still tested and published | CONFIRMED | nit | deleted-code | deletion-note:A7 |
| engine-25 | Lint coverage and dependency hygiene are thin | CONFIRMED | minor | process | new:E6 |
| web-01 | Pattern tab inherits PalettePanel styles; yardage amounts clipped on desktop | CONFIRMED / CONFIRMED | major | survives | ticket:C2b |
| web-02 | Phone header overflows once a quilt is open (horizontal scroll, tab bar pushed below the screen) | CONFIRMED / CONFIRMED | major | deleted-code | deletion-note:C6a |
| web-03 | Compare lightbox (in the editor) and round-trip panel render unstyled | CONFIRMED / CONFIRMED | major | survives | ticket:C1b |
| web-04 | Results screen never offers the uncertain-squares toggle | CONFIRMED / CONFIRMED | major | survives | ticket:C2a |
| web-05 | A wrong read is shown as a normal success (cross-area with vision) | CONFIRMED / CONFIRMED | critical | deleted-code | ticket:C2a |
| web-06 | State layer is a 1749-line god context with editing tangled into exports and the photo flow | PARTIAL | minor | survives | ticket:C1a |
| web-07 | Worker RPC has no timeouts, no error channel, and drops diagnostics | CONFIRMED / CONFIRMED | major | survives | ticket:C8a |
| web-08 | Progress screen shows six spinners that never fill (deviates from PARITY item 14) | CONFIRMED / CONFIRMED | minor (was major) | deleted-code | ticket:C3c |
| web-09 | Analyze is enabled before the photo is staged | CONFIRMED / CONFIRMED | major (was critical) | survives | ticket:C3b |
| web-10 | Resume banner goes stale after Home | CONFIRMED | minor | deleted-code | deletion-note:C6a |
| web-11 | Vision 'ready' notice is driven by a localStorage flag, not the live state | PARTIAL | minor | survives | ticket:C8b |
| web-12 | Vision failures are retried forever, classified by message text | PARTIAL / PARTIAL | major | survives | ticket:C8b |
| web-13 | Home does not cancel a running analysis; crossing 720 px remounts the editor | CONFIRMED | minor | survives | new:C11 |
| web-14 | Ruler labels overlap at small scales | CONFIRMED | minor | survives | ticket:C8c |
| web-15 | Muted and faint text fail WCAG AA contrast | CONFIRMED | minor | survives | ticket:C8c |
| web-16 | Accessibility gaps in dialogs, inputs and controls | CONFIRMED | minor | survives | ticket:C8c |
| web-17 | Phone ergonomics: the canvas swallows scrolls and downloads sit two screens down | CONFIRMED | minor | survives | ticket:C2a |
| web-18 | Export busy state tracks only one export | CONFIRMED | minor | survives | ticket:C2a |
| web-19 | Local builds and e2e can silently test a stale engine | CONFIRMED | minor | process | no-action: fixed by setup PR #105 |
| web-20 | Tests and e2e specs are never type-checked; thin UI coverage | CONFIRMED | minor | process | new:C10 |
| web-21 | Editing-only bugs (moot after removal): Ctrl+Z hijacks text fields; blur commits a no-op resize | CONFIRMED | minor | deleted-code | deletion-note:C6a |
| web-22 | Dev StrictMode boots two workers | CONFIRMED | nit | survives | ticket:C8a |
| web-23 | Duplicate contracts and dead code | CONFIRMED | nit | survives | ticket:C1a |
| web-24 | Styling is seven injected template strings with global class names and three button systems | CONFIRMED | minor | survives | ticket:C1b |
| web-25 | Stale comments, test-only production code, and a spike page that still ships | CONFIRMED | nit | process | ticket:C6a |
| tests-01 | No test checks end-to-end correctness; 11 of 28 synthetic squares cases return a confident-wrong 'readable' | PARTIAL / PARTIAL | critical | deleted-code | ticket:D4a |
| tests-02 | No real-world photo or published pattern with ground truth anywhere in tests or metrics | CONFIRMED / CONFIRMED | major | process | ticket:D3b |
| tests-03 | S2 tests pin known-wrong outputs as expected, so fixing them breaks CI (conflicts with open #82) | CONFIRMED / CONFIRMED | major | deleted-code | deletion-note:B6b |
| tests-04 | All correct squares reads are the one benchmark quilt; the corpus is a monoculture | CONFIRMED | minor | process | ticket:D3a |
| tests-05 | Next CI run will fail Lint: ruff is unpinned and 0.16.10 reports 99 errors on main | CONFIRMED / CONFIRMED | major | process | no-action: fixed by setup PR #105 |
| tests-06 | Confidence is not calibrated against correctness and no test checks it | CONFIRMED / CONFIRMED | major | deleted-code | ticket:D4a |
| tests-07 | Sprint-4 S1/S2 tests are 63% of suite time and doubled CI, with no field-photo payoff | CONFIRMED | minor | deleted-code | deletion-note:B6b |
| tests-08 | 37% of suite wall is repeated reverse() on identical inputs | PARTIAL | minor | deleted-code | deletion-note:B6b |
| tests-09 | main is unprotected, so CI is only advisory | CONFIRMED / CONFIRMED | major | process | protocol:ORCHESTRATOR |
| tests-10 | The freeze/bless protocol is honor-system and covers only tests/golden | CONFIRMED / CONFIRMED | major | process | new:E5 |
| tests-11 | Observed-output thresholds and ratchets, against the repo's own rule | CONFIRMED | minor | deleted-code | deletion-note:B6b |
| tests-12 | Vacuous or conditional tests | CONFIRMED | minor | survives | ticket:B2a |
| tests-13 | Negative-control coverage gap: degraded_busy_print_2000 is falsely 'readable' | CONFIRMED | minor | deleted-code | deletion-note:B6b |
| tests-14 | Implementation-detail pins break on any refactor | CONFIRMED | minor | deleted-code | new:A8 |
| tests-15 | Block-lattice algorithm is implemented twice (production plus a test fixture copy) | CONFIRMED | minor | deleted-code | deletion-note:B6b |
| tests-16 | CI is slow and structured as post-deploy verification | CONFIRMED | minor | process | new:E6 |
| tests-17 | Unpinned runtime installs in the Pyodide job and Node-20-era actions | CONFIRMED | minor | process | new:E6 |
| tests-18 | Removing editing has a wider test blast radius than editing.spec.ts | CONFIRMED | minor | process | ticket:A7 |
| tests-19 | Fragile path and private pytest import | CONFIRMED | nit | survives | ticket:A1 |
| tests-20 | Dead code in test_repeats_verdict | CONFIRMED | nit | deleted-code | deletion-note:B6b |
| tests-21 | Redundant and divergent tests | CONFIRMED | nit | survives | no-action: harmless duplication |
| tests-22 | 24% of tests are fixture-integrity checks that regenerate PNGs on every run | CONFIRMED | nit | process | no-action: speed only |
| tests-23 | docs/demo duplicates the golden and Pages publishes internal docs | CONFIRMED | minor | process | ticket:E2 |
| tests-24 | Stale tracking and a stray directory | CONFIRMED | nit | process | protocol:ORCHESTRATOR |
| docs-01 | No shipped path reads any of the three real field photos on the phone; even hand crops mostly fail | PARTIAL / PARTIAL | critical | product | ticket:B2a |
| docs-02 | No ground-truth reference data exists to measure real-photo accuracy | CONFIRMED / CONFIRMED | major | process | ticket:D3b |
| docs-03 | Phone downscale before crop pushes real quilts under the rescue pitch floor | CONFIRMED / PARTIAL | major | survives | ticket:C3 (plan: C3b) |
| docs-04 | The false 'steep angle' reason still fires on frontal screenshots | CONFIRMED / PARTIAL | minor (was major) | deleted-code | deletion-note:B6b |
| docs-05 | The WOF=40 decision is mis-scoped and collides with the frozen-test rules | CONFIRMED / CONFIRMED | major | survives | ticket:A2b |
| docs-06 | Every export and the failure escape live inside the editor being removed | PARTIAL / PARTIAL | major | survives | ticket:C2 (plan: C2a) |
| docs-07 | No current spec exists; shipped behavior is governed by sprint-scoped docs CLAUDE.md does not list | PARTIAL | minor | process | ticket:E2 |
| docs-08 | The rules only let the vision read path grow, never shrink | PARTIAL | minor | process | no-action: handled by governance PR #106 |
| docs-09 | The project board stopped tracking after sprint 1 | CONFIRMED | minor | process | ticket:E2 |
| docs-10 | The mobile WebKit lens the plan requires is not configured | CONFIRMED | minor | process | ticket:C7 |
| docs-11 | Discovered work was never filed as issues | CONFIRMED | minor | process | protocol:ORCHESTRATOR |
| docs-12 | README and REPORT point at closed issues and work that never shipped | PARTIAL | minor | process | ticket:E2 |
| docs-13 | Sprint-4 plan premises refuted during the build were never amended, and DECISIONS.md is incomplete | CONFIRMED | minor | process | ticket:E2 |
| docs-14 | Area labels are wrong or missing on several issues | PARTIAL | nit | process | ticket:E2 |
| docs-15 | Some issues closed as completed with acceptance boxes unticked | CONFIRMED | nit | process | protocol:ORCHESTRATOR |
| docs-16 | Sub-issue links miss work folded into sprint 4 | CONFIRMED | nit | process | protocol:ORCHESTRATOR |
| docs-17 | The live site runs unreleased code | CONFIRMED | minor | process | ticket:E4 |
| docs-18 | Native dependencies are unpinned and CI has not run in three months | CONFIRMED | minor | process | no-action: fixed by setup PR #105 |
| docs-19 | Untracked .sf/ directory at the repo root | CONFIRMED | nit | process | no-action: fixed by setup PR #105 |
| docs-20 | Issue templates and bodies drift from the convention | CONFIRMED | nit | process | ticket:E2 |
| ux-01 | Auto-crop grabs the whole frame on every real photo; all three real photos fail by default | CONFIRMED / CONFIRMED | major | deleted-code | ticket:C3b |
| ux-02 | A photo-recovered quilt cannot be exported by default: Strip plan errors and booklet, cut list and yardage never download | CONFIRMED / CONFIRMED | major | survives | ticket:C2a |
| ux-03 | The pattern deliverables are not visual and not always sewable | CONFIRMED / PARTIAL | major | survives | ticket:A5a |
| ux-04 | Phone editor is wider than the screen; bottom tab bar (route to Pattern and downloads) falls off-screen | CONFIRMED / CONFIRMED | major | deleted-code | new:C10 |
| ux-05 | Confidence copy contradicts the verdict and itself | CONFIRMED / CONFIRMED | major | deleted-code | ticket:C2a |
| ux-06 | Same photo, different quilt depending on screen width | CONFIRMED / CONFIRMED | critical | survives | ticket:C3b |
| ux-07 | Failure reasons name the wrong cause, and the tips omit the real fix | CONFIRMED / CONFIRMED | minor (was major) | deleted-code | ticket:C3c |
| ux-08 | First visit silently downloads 25.4 MB; a cold phone user waits about 44 s on an uninformative spinner | CONFIRMED / CONFIRMED | major | survives | ticket:C8b |
| ux-09 | Yardage amounts are clipped at 1440x900, and the page scrolls sideways | CONFIRMED / CONFIRMED | major | survives | ticket:C2b |
| ux-10 | Tap-to-paint is ignored on touch; squares are 5.86 px at Fit on a phone | REFUTED | nit | deleted-code | UNMAPPED |
| ux-11 | Engineering language and developer tools leak into the product | CONFIRMED | minor | survives | ticket:C8a |
| ux-12 | Crop step friction: Analyze below the fold, tiny preview, no zoom, small pins | CONFIRMED | minor | survives | ticket:C3b |
| ux-13 | Progress screen never progresses stage by stage | CONFIRMED | minor | deleted-code | ticket:C3c |
| ux-14 | Visible reading errors in a 'solid' result | CONFIRMED / PARTIAL | critical | deleted-code | ticket:C2a |
| ux-15 | Browser Back exits the app and loses the session photo | CONFIRMED | minor | survives | new:C11 |
| ux-16 | Non-image and corrupt files are accepted until Analyze | CONFIRMED / CONFIRMED | major (stale-bytes path only; rest minor; was minor) | survives | ticket:C3b |
| ux-17 | Header tooltips render outside the viewport | CONFIRMED | minor | survives | new:C10 |
| ux-18 | Results preview layout and ruler label collisions | CONFIRMED | minor | survives | ticket:C8c |
| ux-19 | Duplicated and dead-looking controls | CONFIRMED | minor | survives | ticket:C8c |
| ux-20 | Phone results page buries the primary action | CONFIRMED | minor | survives | ticket:C2a |
| ux-21 | Strategy cards and sizing presets overload a first-time user | CONFIRMED | minor | survives | ticket:C2a |
| ux-22 | Scrolling the Pattern panel scrolls the quilt out of view | CONFIRMED | minor | product | ticket:C2a |
| ux-23 | 'Copy my settings' is the most prominent action on the Pattern tab | CONFIRMED | nit | survives | ticket:C2a |
| ux-24 | Unfinished site metadata and leftover dev artifacts are public | CONFIRMED | nit | survives | ticket:C8c |
| ux-25 | The landing 'sample photo' card sets a false expectation | CONFIRMED | nit | survives | ticket:C9 |
| data-01 | Met Open Access: adopt (116 public-domain quilt images) | CONFIRMED | minor | process | ticket:D3a |
| data-02 | Smithsonian Open Access: adopt (173 CC0 quilt records) | CONFIRMED | minor | process | ticket:D3a |
| data-03 | Art Institute of Chicago: adopt (114 public-domain quilt images) | CONFIRMED | minor | process | ticket:D3a |
| data-04 | LACMA: free public-domain images with a required citation | CONFIRMED | minor | process | ticket:D3a |
| data-05 | Mia: image license conflicts, keep private | CONFIRMED / PARTIAL | minor (was major) | process | ticket:D3a |
| data-06 | Wikimedia Commons: mixed licenses, maybe | CONFIRMED | minor | process | ticket:D3a |
| data-07 | NGA Index of American Design: optional render tier | CONFIRMED | nit | process | no-action: NGA render tier not adopted: the synthetic renders cover clean renders, and renders are never scored as photos |
| data-08 | Other museums and aggregators: unverified | UNVERIFIABLE | nit | process | UNMAPPED |
| data-09 | Cleveland Museum of Art: reject (too few bed quilts) | CONFIRMED | nit | process | ticket:D3a |
| data-10 | Rijksmuseum: reject (almost no pieced quilts) | CONFIRMED | nit | process | ticket:D3a |
| data-11 | V&A: reject (non-commercial, 768 px cap, 4-week cache ban) | CONFIRMED / CONFIRMED | major | process | ticket:D3a |
| data-12 | Quilt Index: reject for the corpus | CONFIRMED / CONFIRMED | minor (was major) | process | ticket:D3a |
| data-13 | International Quilt Museum: reject (copyrighted, fees) | CONFIRMED / CONFIRMED | minor (was major) | process | ticket:D3a |
| data-14 | Library of Congress quilt collection: reject (mixed rights, modern designs) | CONFIRMED | minor | process | ticket:D3a |
| data-15 | QUILT-1M is a histopathology dataset, not quilts | CONFIRMED | nit | process | ticket:D1 |
| data-16 | Engine produced no grid on all 16 real CC0 museum photos | CONFIRMED / CONFIRMED | major | deleted-code | ticket:D4a |
| data-17 | 11 of 16 photos fell to rectify tier 3 | PARTIAL | minor | deleted-code | deletion-note:B6b |
| data-18 | Square-cell quilts all no_grid, but 2 of the 7 are on-point | PARTIAL / PARTIAL | minor (was major) | deleted-code | ticket:D3a |
| data-19 | Higher resolution (2000 px) does not help | CONFIRMED | minor | deleted-code | ticket:D4a |
| data-20 | Supplied corners plus fabric count still give no grid | CONFIRMED / CONFIRMED | major | deleted-code | ticket:B2a |
| data-21 | Sample inventory and resolutions | CONFIRMED | nit | process | no-action: Inventory fact; the D3a manifest supersedes the 16-sample list |
| data-22 | 14 of 16 photos usable; NMAH slide scans marginal | CONFIRMED | minor | process | ticket:D3a |
| data-23 | The model is a rectilinear grid of solid square cells | CONFIRMED / CONFIRMED | major | survives | new:B8 |
| data-24 | Model scope share: 7 square of 16 is really 4 to 5 | PARTIAL | minor | product | ticket:D3a |
| data-25 | Annotation feasibility: block reads right, TATW count wrong | PARTIAL | minor | process | ticket:D3b |
| data-26 | Museum dimensions give finished-size ground truth | CONFIRMED | minor | process | ticket:D3a |
| data-27 | Pattern-name tallies from museum titles | CONFIRMED | minor | process | ticket:D3a |
| data-28 | Per-image license record template exists | CONFIRMED | minor | process | ticket:D3a |
| data-29 | Commercial pattern PDF kept private | CONFIRMED | minor | process | protocol:WORKER |
| data-30 | The recon run left the repo untouched | CONFIRMED | nit | process | protocol:WORKER |
| data-31 | Traditional blocks are not protected; presentations are | CONFIRMED | minor | process | no-action: PATTERN-SPEC.md (a setup document in the plan PR) carries the Compendium citation; no worker ticket |
| data-32 | Webster 1915 is public domain with a quilt-name list | CONFIRMED | nit | process | ticket:D1 |
| data-33 | Ladies Art Company catalogs are public domain but unscanned | CONFIRMED | nit | process | no-action: Name source only; pattern naming is out of 0.4.0 (section 11) |
| data-34 | McKim 1931 public domain by non-renewal (asserted) | CONFIRMED | nit | process | no-action: Not relied on; pattern naming is out of 0.4.0 |
| data-35 | Finley 1929 public domain since 2025 | CONFIRMED | nit | process | no-action: Not relied on; pattern naming is out of 0.4.0 |
| data-36 | Museum titles document name aliases | CONFIRMED | nit | process | ticket:D3a |
| data-37 | Block catalog tags are outdated for sprint 5 scope | PARTIAL | minor | process | ticket:D3b |
| data-38 | DO NOT COPY list for modern sources | CONFIRMED / CONFIRMED | major | process | protocol:WORKER |
| data-39 | Commercial patterns are private oracles only | CONFIRMED / CONFIRMED | major | process | ticket:D6 |
| data-40 | Other fabric-company terms unverified | UNVERIFIABLE | minor | process | UNMAPPED |
| data-41 | Conservative rules for rights-unclean material | CONFIRMED / CONFIRMED | major | process | protocol:WORKER |
| data-42 | Corpus tiers keyed to deleted verdicts and old scope | PARTIAL / PARTIAL | minor (was major) | process | ticket:D3a |
| data-43 | S0 degradation chain exists but differs from the description | PARTIAL | minor | process | ticket:D4a |
| data-44 | Confidence-interval arithmetic | CONFIRMED | nit | process | ticket:D4a |
| data-45 | Supply estimate is internally inconsistent | PARTIAL | minor | process | ticket:D3a |
| data-46 | Annotation sidecar can extend the photoreal schema | CONFIRMED | minor | process | ticket:D3a |
| data-47 | Gold-subset candidates include on-point and unlicensed images | PARTIAL / PARTIAL | minor (was major) | process | ticket:D3b |
| data-48 | Crop screen does not surface detection failure | PARTIAL | minor | deleted-code | ticket:B2a |
| data-49 | Report-only first, freeze later with the existing rite | CONFIRMED | nit | process | ticket:D5 |
| data-50 | Release-asset corpus plan conflicts with sprint rules | PARTIAL / PARTIAL | minor (was major) | process | ticket:D3a |
| data-51 | Fetch plan endpoints and rate limits | CONFIRMED | minor | process | ticket:D3a |
| data-52 | Effort estimates | UNVERIFIABLE | nit | process | UNMAPPED |
| data-53 | Pattern-name matching against a hand-authored catalog | UNVERIFIABLE | nit | product | UNMAPPED |
| data-54 | Legal note 1: traditional blocks unprotected | CONFIRMED | minor | process | ticket:D3a |
| data-55 | Legal note 2: Boisson v. Banian protects specific quilts | CONFIRMED / CONFIRMED | major | process | ticket:D3a |
| data-56 | Legal note 3: rely on per-object rights flags | CONFIRMED | minor | process | ticket:D3a |
| data-57 | Legal note 4: store flags and re-check before release | CONFIRMED | minor | process | ticket:D3a |
| data-58 | Legal note 5: CC0 is committable; LACMA needs a citation | CONFIRMED | minor | process | ticket:D3a |
| data-59 | Legal note 6: excluded sources | CONFIRMED / PARTIAL | major | process | ticket:D3a |
| data-60 | Legal note 7: local shop photos stay private | CONFIRMED / PARTIAL | major | process | ticket:D3c |
| data-61 | Legal note 8: Jake's own quilt photos can be CC0 | UNVERIFIABLE | minor | process | UNMAPPED |
| data-62 | Legal note 9: public-domain book status | CONFIRMED | nit | process | ticket:D1 |
| data-63 | Legal note 10: QUILT-1M is not quilt data | CONFIRMED | nit | process | ticket:D1 |
| approaches-01 | Hays 2006: automatic lattice discovery fails often | CONFIRMED | nit | product | ticket:B2a |
| approaches-02 | Park 2008/2009 deformed lattice: detection rates and the claimed fix for QREP drift | PARTIAL | nit | product | ticket:B5 |
| approaches-03 | Liu 2015 PatchMatch lattice detection: rates and the dropped fence subset | CONFIRMED | nit | product | ticket:B2a |
| approaches-04 | Liu, Collins, Tsin 2000: regions-of-dominance lattice, symmetry group and motif | CONFIRMED | nit | product | no-action: Background on lattice discovery; no decision depends on it |
| approaches-05 | Funk 2017 challenge: frieze detection in natural photos scores F=0.19-0.20 | CONFIRMED | nit | product | ticket:B2a |
| approaches-06 | Lettry 2017 CNN repeated-pattern detection and the no-browser-detector claim | PARTIAL | nit | product | no-action: No CNN or browser lattice detector adopted; the absence is stated as a search outcome |
| approaches-07 | Sookocheff and Mould 2005: one-click lattice extraction | CONFIRMED | nit | product | ticket:B1a |
| approaches-08 | Kaspar 2019 Neural Inverse Knitting: per-cell accuracy ceiling | CONFIRMED | nit | product | no-action: Background on per-cell accuracy ceilings |
| approaches-09 | Hazay, Lewenstein, Tsur 2005: two-dimensional parameterized matching | CONFIRMED | nit | product | no-action: Catalog matching deferred with pattern naming (section 11) |
| approaches-10 | Liu, Hodgins, McCann NPAR 2017: whole-cloth quilting stitch paths | UNVERIFIABLE | nit | product | UNMAPPED |
| approaches-11 | Gokhale (SPIE): crazy vs non-crazy quilt classification | UNVERIFIABLE | nit | product | UNMAPPED |
| approaches-12 | Electric Quilt 8 and BlockBase+: no photo recognition, large block library | CONFIRMED | nit | product | no-action: Competitive context only |
| approaches-13 | Brackman encyclopedia: 4,000+ blocks in 25 structural categories | CONFIRMED | nit | product | no-action: Context; the DO NOT COPY rule is carried by data-38 (WORKER.md) |
| approaches-14 | PreQuilt: design tools but no photo-to-pattern feature | PARTIAL | nit | product | no-action: Competitive context; the fabric-calculator detail is not used |
| approaches-15 | photoQuilt: forward-only photo to pixel quilt, last updated 2016 | CONFIRMED | nit | product | no-action: Competitive context only |
| approaches-16 | Generative quilt tools and Quilter's App do not make cut-ready patterns from photos | CONFIRMED | nit | product | no-action: Market context for section 1 |
| approaches-17 | Pixel Rehab: detectors vote on cell size and the user owns rows and columns | CONFIRMED | nit | product | ticket:B1a |
| approaches-18 | Photo-to-cross-stitch converters: user sets stitch count and maximum colours | CONFIRMED | nit | product | ticket:B2b |
| approaches-19 | Document scanners auto-propose corners and let the user drag them | PARTIAL | nit | product | ticket:B1b |
| approaches-20 | Sudoku solver: a known count turns cell finding into division | CONFIRMED | nit | product | ticket:B2a |
| approaches-21 | VLMs miscount simple grids (Vision language models are blind, ACCV 2024) | CONFIRMED | nit | product | ticket:D3b |
| approaches-22 | The Quilt Index as a local-only eval source | CONFIRMED | nit | process | ticket:D3a |
| approaches-23 | The model has one region type, so curved and triangle quilts cannot be represented | CONFIRMED / CONFIRMED | major | survives | ticket:B8 |
| approaches-24 | The automatic path fails at the crop on all three field screenshots | CONFIRMED / CONFIRMED | major | deleted-code | ticket:D3c |
| approaches-25 | Field photos described as phone screenshots of a shop page | PARTIAL | minor | process | ticket:D3a |
| approaches-26 | The field smoke test measured only the automatic full-frame path | CONFIRMED | minor | deleted-code | ticket:D4a |
| approaches-27 | Pinned Double Irish Chain reads only through the S2 corroboration rescue | CONFIRMED | minor | deleted-code | ticket:D3c |
| approaches-28 | Old Mill Wheel with pins: the 'honest no_grid / non_square_content' result depends on pin placement | PARTIAL / PARTIAL | major (was critical) | deleted-code | ticket:D4a |
| approaches-29 | Pinned Star reads no_grid at a 7 px pitch because the quilt is small in the frame | CONFIRMED | minor | product | ticket:B4a |
| approaches-30 | The phone resolution cap is applied to the whole frame before cropping | CONFIRMED / CONFIRMED | major | survives | ticket:C3 (plan: C3b) |
| approaches-31 | The phone cap pushes the pinned DIC below the rescue floor and the verdict flips on the filter | CONFIRMED / CONFIRMED | major | deleted-code | ticket:D4b |
| approaches-32 | Issue #101 tracks crop-aware downscale but lacked the phone-path measurement | CONFIRMED | minor | process | ticket:C3 (plan: C3b, which includes #101) |
| approaches-33 | A single global grid drifts at the photo edges | CONFIRMED / REFUTED | minor (was major) | product | UNMAPPED |
| approaches-34 | Catalog matching scores on the pinned Double Irish Chain | CONFIRMED | minor | product | ticket:B2b |
| approaches-35 | The repo Double Irish Chain fixture is a different colour variant from the field photo | CONFIRMED | minor | survives | ticket:D3c |
| approaches-36 | QREP already has a corner-pin crop screen | CONFIRMED | nit | survives | ticket:C3 (plan: C3b) |
| approaches-37 | On screenshots the proposed quad is the whole frame | CONFIRMED | minor | deleted-code | ticket:C3 (plan: C3b) |
| approaches-38 | Per-stage confidence meters and a verdict taxonomy, unlike every analog | PARTIAL | minor | deleted-code | deletion-note:B6b |
| approaches-39 | The existing non_square_content diagnosis cannot flag triangles and curves before the grid step | REFUTED | major | deleted-code | UNMAPPED |
| approaches-40 | Repeat detection and voting already exist | CONFIRMED | nit | survives | ticket:B2b |
| approaches-41 | A bring-your-own-key VLM would break the README privacy promise | CONFIRMED | minor | product | no-action: VLMs are out of 0.4.0 (section 11); the README privacy promise stands |
| approaches-42 | VLM cost per photo is under half a cent on Sonnet 5.5 | CONFIRMED | nit | product | no-action: VLM cost context; VLMs are out of scope |
| approaches-43 | The Anthropic API supports direct browser calls with the user's own key | CONFIRMED | nit | product | no-action: VLM access context; VLMs are out of scope |
| approaches-44 | Anthropic's vision guide lists counting as a limitation | CONFIRMED | nit | product | no-action: Supports human-verified counts (D3b); no separate action |
| approaches-45 | Chrome's Prompt API rules out the iPhone user | CONFIRMED | nit | product | no-action: Rules out an on-device browser model; no action |
| approaches-46 | An on-device VLM via Transformers.js and WebGPU is too heavy for the payload budget | PARTIAL | nit | product | no-action: An on-device VLM is too heavy; no action |
| approaches-47 | VLM block naming and scope checks are unmeasured | PARTIAL | nit | product | no-action: VLM naming is out of 0.4.0 |
| approaches-48 | Pyodide stack, wheel sizes and lazy vision loading | CONFIRMED | nit | survives | no-action: Payload context for C8; no change |
| approaches-49 | No SharedArrayBuffer on GitHub Pages: single-threaded engine, cancel by terminating | CONFIRMED | nit | survives | no-action: Single-thread engine already designed in; cancel means terminating the worker (C8) |
| approaches-50 | Pyodide speed ranges from near native to 3-5x slower | CONFIRMED | nit | product | no-action: Background; D9 measures real browser latency |
| approaches-51 | Native timings, and the wasm estimate that was not measured | CONFIRMED | nit | product | ticket:D9 |
| approaches-52 | OpenCV and numpy version skew between the dev venv and the browser | CONFIRMED / CONFIRMED | minor (was major) | survives | ticket:B6a |
| approaches-53 | A VLM cannot run inside Pyodide | UNVERIFIABLE | nit | product | UNMAPPED |
| approaches-54 | A reference/ folder for real quilt photos already exists | CONFIRMED | nit | process | no-action: Section 8.3 decides: the corpus lives in corpus/ and reference/ stays as it is |
| approaches-55 | Repo hygiene after the planning chat's runs | PARTIAL | nit | process | no-action: No hygiene change needed |
| approaches-56 | The flow and scope change needs an amendment to the binding web design doc | CONFIRMED | minor | process | no-action: The governance PR (#106) amends the binding docs before any flow change merges |
| approaches-57 | Hand-authored data carries confidence 1.0 | CONFIRMED | nit | survives | ticket:D3b |
| approaches-58 | The planned removals and the fate of the frozen thresholds | PARTIAL | minor | deleted-code | ticket:B6b |
| orchestration-01 | Mechanism: background agents with agent view | PARTIAL / PARTIAL | major | process | protocol:ORCHESTRATOR |
| orchestration-02 | Mechanism: worktree sessions | PARTIAL | minor | process | protocol:WORKER |
| orchestration-03 | Mechanism: VS Code extension parallel sessions | PARTIAL / PARTIAL | minor (was major) | process | protocol:ORCHESTRATOR |
| orchestration-04 | Mechanism: agent teams | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-05 | Mechanism: subagents | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-06 | Mechanism: cross-session messaging | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-07 | Coordination: parallel work isolation | PARTIAL / PARTIAL | major | process | protocol:ORCHESTRATOR |
| orchestration-08 | Coordination: message flow and delivery | PARTIAL / PARTIAL | major | process | protocol:ORCHESTRATOR |
| orchestration-09 | Coordination: status updates | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-10 | Coordination: orchestrator pattern and idle notices | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-11 | Coordination: shared config | PARTIAL | minor | process | no-action: bypass |
| orchestration-12 | Context rotation: checking fill | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-13 | Context rotation: auto-compaction | REFUTED | major | process | protocol:ORCHESTRATOR |
| orchestration-14 | Context rotation: handoff between sessions | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-15 | Context rotation: survival rules after compaction | CONFIRMED | minor | process | protocol:WORKER |
| orchestration-16 | Context rotation: session switching and shared memory | CONFIRMED | minor | process | protocol:ORCHESTRATOR |
| orchestration-17 | Permissions: per-session enforcement | CONFIRMED / CONFIRMED | major | process | protocol:ORCHESTRATOR |
| orchestration-18 | Permissions: hooks in spawned sessions | PARTIAL | minor | process | no-action: not used |
| orchestration-19 | Permissions: CLAUDE.md and skills scope | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-20 | Permissions: rule cascade and the --bg default mode | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-21 | Permissions: auto mode in workers | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-22 | Permissions: config precedence | REFUTED | minor | process | no-action: informational |
| orchestration-23 | Recommended setup: orchestrator launch | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-24 | Recommended setup: worker 1 via claude --bg | PARTIAL / PARTIAL | minor (was major) | process | protocol:ORCHESTRATOR |
| orchestration-25 | Recommended setup: worker 2 via --worktree in acceptEdits | PARTIAL / PARTIAL | minor (was major) | process | no-action: superseded |
| orchestration-26 | Recommended setup: worker 3 for slice builds | PARTIAL | minor | process | no-action: superseded |
| orchestration-27 | Recommended setup: orchestrator tasks | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-28 | Recommended setup: viewing tabs in VS Code | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-29 | Recommended setup: context management | REFUTED | minor | process | protocol:ORCHESTRATOR |
| orchestration-30 | Recommended setup: git setup for worktrees | PARTIAL | minor | process | ticket:#105 |
| orchestration-31 | Verified constraint: messaging needs v2.1.234+ on native Windows | CONFIRMED / CONFIRMED | major | process | protocol:ORCHESTRATOR |
| orchestration-32 | Verified constraint: agent view works on Windows | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-33 | Verified constraint: worktrees require a git repo | CONFIRMED | nit | process | no-action: informational |
| orchestration-34 | Verified constraint: permission modes are per session | CONFIRMED / CONFIRMED | minor (was major) | process | protocol:ORCHESTRATOR |
| orchestration-35 | Verified constraint: subagents are not background agents | CONFIRMED | nit | process | no-action: informational |
| orchestration-36 | Open question: VS Code tabs launched programmatically | REFUTED | major | process | protocol:ORCHESTRATOR |
| orchestration-37 | Open question: --remote-control from the Windows CLI | UNVERIFIABLE | nit | process | no-action: not used |
| orchestration-38 | Open question: hooks spawning background agents | UNVERIFIABLE | nit | process | no-action: not used |
| orchestration-39 | Open question: VS Code tab from a URI (/new path) | REFUTED | major | process | protocol:ORCHESTRATOR |
| orchestration-40 | Open question: --fork-session and MEMORY.md | REFUTED | nit | process | no-action: answered |
| orchestration-41 | Open question: approvals from background agents | REFUTED | minor | process | no-action: answered |
| orchestration-42 | Open question: /loop or /schedule for worker status | PARTIAL | minor | process | protocol:ORCHESTRATOR |
| orchestration-43 | Open question: message delivery latency | CONFIRMED | minor | process | protocol:ORCHESTRATOR |
| orchestration-44 | Citations | PARTIAL | minor | process | protocol:ORCHESTRATOR |

## Appendix B: findings by ticket

The inverse of Appendix A's disposition column, for a worker who wants every finding a ticket owns.
Deletion notes are marked (d), findings that a new ticket answers are marked (new), and findings
mapped to a ticket family that the plan split are listed under the ticket that cites them.

| Ticket | Findings |
|---|---|
| A1 | engine-13, tests-19 |
| A2b | engine-02, engine-06, engine-14, engine-19, docs-05 |
| A3a | engine-05, engine-11 |
| A3b | engine-04, engine-10, engine-17 |
| A4a | engine-15, engine-20 |
| A4b | engine-07, engine-09 |
| A4c | engine-01 |
| A4d | engine-08 |
| A5a | engine-03, ux-03 |
| A5b | engine-18 |
| A7 | engine-12 (d), engine-23, engine-24 (d), tests-18 |
| A8 | tests-14 (new) |
| A10 | engine-22 (new) |
| B1a | approaches-07, approaches-17 |
| B1b | approaches-19 |
| B2a | vision-02, vision-05, vision-15, vision-18, tests-12, docs-01, data-20, data-48, approaches-01, approaches-03, approaches-05, approaches-20 |
| B2b | vision-06, vision-07, vision-08, vision-16, vision-19, vision-22, approaches-18, approaches-34, approaches-40 |
| B4a | approaches-29 |
| B5 | approaches-02 |
| B6a | approaches-52 |
| B6b | vision-01 (d), vision-04 (d), vision-09 (d), vision-10 (d), vision-12 (d), vision-14 (d), vision-17 (d), vision-20 (d), tests-03 (d), tests-07 (d), tests-08 (d), tests-11 (d), tests-13 (d), tests-15 (d), tests-20 (d), docs-04 (d), data-17 (d), approaches-38 (d), approaches-58 |
| B8 | data-23 (new), approaches-23 |
| C1a | web-06, web-23 |
| C1b | web-03, web-24 |
| C2a | web-04, web-05, web-17, web-18, docs-06 (mapped as C2), ux-02, ux-05, ux-14, ux-20, ux-21, ux-22, ux-23 |
| C2b | web-01, ux-09 |
| C3b | web-09, docs-03 (mapped as C3), ux-01, ux-06, ux-12, ux-16, approaches-30 (mapped as C3), approaches-32 (mapped as C3), approaches-36 (mapped as C3), approaches-37 (mapped as C3) |
| C3c | web-08, ux-07, ux-13 |
| C6a | web-02 (d), web-10 (d), web-21 (d), web-25 |
| C7 | docs-10 |
| C8a | web-07, web-22, ux-11 |
| C8b | web-11, web-12, ux-08 |
| C8c | web-14, web-15, web-16, ux-18, ux-19, ux-24 |
| C9 | engine-21, ux-25 |
| C10 | web-20 (new), ux-04 (new), ux-17 (new) |
| C11 | web-13 (new), ux-15 (new) |
| D1 | data-15, data-32, data-62, data-63 |
| D3a | tests-04, data-01, data-02, data-03, data-04, data-05, data-06, data-09, data-10, data-11, data-12, data-13, data-14, data-18, data-22, data-24, data-26, data-27, data-28, data-36, data-42, data-45, data-46, data-50, data-51, data-54, data-55, data-56, data-57, data-58, data-59, approaches-22, approaches-25 |
| D3b | vision-03, tests-02, docs-02, data-25, data-37, data-47, approaches-21, approaches-57 |
| D3c | data-60, approaches-24, approaches-27, approaches-35 |
| D4a | vision-11, vision-13, vision-21, tests-01, tests-06, data-16, data-19, data-43, data-44, approaches-26, approaches-28 |
| D4b | approaches-31 |
| D5 | data-49 |
| D6 | data-39 |
| D9 | approaches-51 |
| E1a | engine-16 |
| E2 | tests-23, docs-07, docs-09, docs-12, docs-13, docs-14, docs-20 |
| E4 | docs-17 |
| E5 | tests-10 (new) |
| E6 | engine-25 (new), tests-16 (new), tests-17 (new) |
| protocol:ORCHESTRATOR | tests-09, tests-24, docs-11, docs-15, docs-16, orchestration-01, orchestration-03, orchestration-04, orchestration-05, orchestration-06, orchestration-07, orchestration-08, orchestration-09, orchestration-10, orchestration-12, orchestration-13, orchestration-14, orchestration-16, orchestration-17, orchestration-19, orchestration-20, orchestration-21, orchestration-23, orchestration-24, orchestration-27, orchestration-28, orchestration-29, orchestration-31, orchestration-32, orchestration-34, orchestration-36, orchestration-39, orchestration-42, orchestration-43, orchestration-44 |
| protocol:WORKER | data-29, data-30, data-38, data-41, orchestration-02, orchestration-15 |
| ticket:#105 | orchestration-30 |
| no-action | data-07, data-21, data-31, data-33, data-34, data-35, approaches-04, approaches-06, approaches-08, approaches-09, approaches-12, approaches-13, approaches-14, approaches-15, approaches-16, approaches-41, approaches-42, approaches-43, approaches-44, approaches-45, approaches-46, approaches-47, approaches-48, approaches-49, approaches-50, approaches-54, approaches-55, approaches-56 |
| no-action: answered | orchestration-40, orchestration-41 |
| no-action: bypass | orchestration-11 |
| no-action: fixed by setup PR #105 | web-19, tests-05, docs-18, docs-19 |
| no-action: handled by governance PR #106 | docs-08 |
| no-action: harmless duplication | tests-21 |
| no-action: informational | orchestration-22, orchestration-33, orchestration-35 |
| no-action: not used | orchestration-18, orchestration-37, orchestration-38 |
| no-action: speed only | tests-22 |
| no-action: superseded | orchestration-25, orchestration-26 |
| UNMAPPED | ux-10, data-08, data-40, data-52, data-53, data-61, approaches-10, approaches-11, approaches-33, approaches-39, approaches-53 |
