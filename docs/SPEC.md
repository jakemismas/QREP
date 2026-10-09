# QREP product specification (0.4.0)

Status: written 2026-10-07 for issue #106; binding once that PR merges. This file is the product
contract for QREP 0.4.0: it says what 0.4.0 does, not what main does today. Main reaches it ticket
by ticket under the sprint-5 plan, and the ticket sub-issues under #104 record what has landed. A
section describes main only once the tickets that build it have merged; until then main keeps its
0.3.0 behavior there. Why: every ticket builds toward one fixed target, and progress lives in the
issues, not here. Where an older document disagrees with this file, this file wins, and section 10
names every older section it replaces.

One home per topic:

- [docs/sprint-5/qrep-sprint-5-plan.md](sprint-5/qrep-sprint-5-plan.md): the work (tickets, file
  owners, dependencies, gates).
- [docs/sprint-5/MATH.md](sprint-5/MATH.md): formulas, sources and hand-computed test vectors.
- [docs/sprint-5/PATTERN-SPEC.md](sprint-5/PATTERN-SPEC.md): the pattern document's contents, order
  and wording, and how a reviewer checks it.
- [docs/sprint-5/REBASELINE.md](sprint-5/REBASELINE.md): the closed record of retired and
  re-expressed tests, retired frozen literals and superseded criteria.

**How this file changes.** There are two kinds of change, with different authority.

- Ticket updates, pre-approved. A sprint-5 ticket whose Files owned line names a section of this
  file updates that section, and no other, in the same PR as the behavior (plan section 4.3). The
  update records only what the PR makes true on main within its ticket's text: a link to where a
  value this file leaves to that ticket is kept, such as B2's provisional pixel floor or B3's fit
  thresholds, instead of a restated number; a detail the ticket's text specifies that the section
  does not state yet; or a correction where the section misstates what a merged ticket built (E2's
  drift check). When the section already says what the PR builds, it stays unchanged and the PR
  body says so. These updates need no further decision: Jake approved the plan that assigns them
  and the overnight run that executes its tickets (plan section 3.2, items 5 and 15). Why: the
  contract has to stay true as main changes, and an unattended run cannot stop for Jake at every
  PR.
- Contract changes, Jake only. Every other change lands through a PR whose issue records Jake's
  decision. This includes any change to a binding rule (section 1), the screens or their order
  (section 2), the scope, a refusal or the fabric cap (section 3), the region re-read
  interpretation (section 5), the one-pattern rule (section 6), a default Jake set (the L* weight
  of 0.5 in section 4; the strip and backing widths in section 7), freezing a provisional read
  constant (plan section 5.B), what 0.4.0 removes (section 9) and the release gate (section 11).
  Why: only the product owner changes the contract. A ticket that would need such a change, or
  whose text disagrees with this file, stops and records BLOCKED instead of choosing (plan
  section 3.3; the precedence rule atop docs/sprint-5/WORKER.md).

**Where each topic lives.** The plan's Files owned lines name a section of this file by topic, and
plan section 6.5 lists the tickets that own each topic.

| Topic in the plan | Section here |
|---|---|
| web | 2 |
| read | 4 and 5 |
| construction | 6.1 |
| pattern document | 6.2 |
| sizing | 6.3 |
| math defaults | 7 |
| model | 8 |
| removed surfaces | 9 |
| bridge | 12.1 |
| CLI | 12.2 |
| all sections | every section |

## 1. Binding rules

1. The user confirms the geometry; the engine reads the fabrics. QREP never decides corners or
   counts on its own. Why: the automatic read returned no readable result on any of 3 field
   screenshots or 16 public-domain museum photos, and 12 of the 25 synthetic fixture reads it
   called readable were wrong (docs/sprint-5/REVIEW.md).
2. One pattern outcome: one construction method, one document, one download. Why: Jake's decision
   of 2026-10-06; published patterns are one document (docs/sprint-4/DECISIONS.md, D5), and a menu
   of strategies hands the engine's decision to the quilter.
3. Every number comes from a stated formula with hand-computed test vectors (MATH.md). Calculators
   and published patterns are recorded cross-checks, never the source of an assertion; reference
   patterns set structure and conventions, never numbers. Why: today's backing formula over-buys on
   wide and long quilts (MATH.md, section 3), a quilter reported it as far too much, and the fix
   needs a source of truth that is not another tool's output.
4. Refuse what QREP cannot represent, early and in plain words; never ship an approximation as a
   pattern. Why: a wrong pattern wastes fabric; an honest "not yet" does not.
5. Never print a guess as a fact. Every CV-derived value carries a confidence; user-confirmed values
   are user facts (section 8). Why: a quilter follows a pattern literally.
6. Expand, then contract: old code goes only after its replacement is live, and main always offers a
   pattern download. Why: main stays shippable through the narrowing.

## 2. The web app flow

A photo moves through these steps in order: Photo, the scope picker, Confirm, Reading, Colors and
Your pattern. Plan section 2.1 holds the screen-level rules and copy.

- **Photo.** The user picks or drops a photo or screenshot of a quilt that lies flat and faces the
  camera. Try an example opens a committed CC0 or public-domain museum quilt on Confirm, with its
  verified corners, counts and bands pre-filled; the examples replace the synthetic sample photo
  (C9). See a sample pattern opens the hand-authored demo quilt on Your pattern without a read
  (plan section 5.C, decision 2).
- **Scope picker.** Right after the photo, QREP-drawn diagrams show quilts QREP works with and
  quilts it does not work with yet (section 3). A Not yet pick ends at the refusal screen, so an
  out-of-scope quilt is turned away before the user confirms anything. The pick travels with the
  read as its scope.
- **Confirm.** One screen with a live grid overlay for the frame and the counts (section 4).
- **Reading.** One progress line while the engine reads fabrics and units and checks the grid fit
  (sections 4 and 5). A failed fit returns to Confirm with the pins and counts kept, and too few
  pixels per square returns there with advice for a closer photo (sections 3 and 5).
- **Colors.** A fabric-count stepper starts at the read's suggestion and runs from 2 to 12. Each
  change re-reads the fabrics at that count, without refitting the grid, and updates the recovered
  preview. Why here: the suggestion comes from the read, and the fabric count feeds the
  block-consistent vote and the method choice, so it is settled before Your pattern (plan
  section 2.1).
- **Your pattern.** The recovered quilt beside the photo, a fabric census with letters, swatches
  and color names that match the PDF, the finished size (section 6.3), the method with its
  one-sentence reason, flagged regions with the region re-read tool (section 5), a way back to
  Confirm that keeps the corners, counts and bands, and one Download pattern (PDF) button.

Unchanged rules that carry forward: photos never leave the device
(docs/sprint-2/qrep-web-design-doc.md, Persistence policy); the photo is session-only
(docs/design/sprint-2/PARITY.md, decision 7); every number on screen comes from the engine
(PARITY.md, decision 1); the phone layout is in scope (PARITY.md, decision 10); squares not cells,
loading not downloading, mixed fractions (docs/design/sprint-3/UI-SPEC.md, vocabulary).

## 3. Scope and refusals

In scope: quilts pieced on a square grid, with plain border bands and up to about 12 fabrics, built
from plain squares, half-square triangles (HST), quarter-square triangles (QST: hourglass, star
points) and stitch-and-flip corners (snowball corners, flying geese).

- Refused at the scope picker, before any confirming: curves, applique, on-point settings and
  medallions (until supported), shown as QREP-drawn diagrams under Not yet these. Why diagrams, not
  a yes-or-no question: an owner may call an on-point Double Irish Chain "only squares" (plan
  section 2.3).
- Refused by the engine, whatever the pick: more fabrics than the cap (scrappy quilts), squares the
  classifier cannot resolve as one of the four unit types once their share passes a measured
  threshold (ticket B4), and a layout that cannot be sewn with straight seams. Each ends at the
  refusal screen, never in an approximated PDF (PATTERN-SPEC.md, method selection).
- Every refusal screen says what QREP reads today and offers next steps: another photo or an
  example (plan section 2.3).
- Held: with too few pixels per square, QREP returns to Confirm and asks for a closer photo, or for
  a screenshot taken zoomed in on the quilt. The floor is measured, never guessed: B2 sets a
  provisional one, and D5 and D10 measure the final one. A grid that does not fit withholds the
  download (section 5).
- Not in 0.4.0 (backlog): pieced borders (#15), quilting detection (#16), applique and non-grid
  regions (#17), colorways (#18), machine formats (#20), multi-image fusion (#21), partial views
  (#54), full metric display (#86).

## 4. The confirmed read

The user confirms, and QREP records each value as a user fact at confidence 1.0:

- geometry: the four corners of the pieced field, or the outer quilt edge plus border bands set
  inward (in real photos the field corners are often hidden by borders or binding);
- counts in quilter units: blocks across and down, times squares per block, typed or with steppers;
  the confirmed block period follows from them;
- the fabric count, which the user settles on Colors after the first read; until then the read
  uses its own suggestion (section 2).

The confirm screen has 44 px pins, a loupe and the live overlay. It may suggest counts with harmonic
alternates and offer a tap-one-square fallback (QREP proposes counts from one tapped square). A
suggestion is shown, never applied silently, and ships only if its measured accuracy earns it
(spike B1).

From the confirmed frame and counts, the engine:

- reads a crop around the confirmed frame that the web cuts at full resolution before the
  resolution cap (#101), area-downsamples it before the perspective warp when it holds more pixels
  than the read needs (B2a), and samples square interiors inset from the seams;
- clusters fabrics in Lab with L* weighted 0.5 by default, with value-aware handling: fabrics that
  differ only in lightness stay apart, and a label-aware shading correction applies to both the
  palette and the assignment;
- classifies each square as plain, HST, QST or stitch-and-flip corner, with a fabric per part (B4);
- votes within the confirmed block period, so a few misread squares cannot flip the method. Every
  square the vote changes is flagged on Your pattern, so a deliberate variation is never lost
  silently (B2 and A3 set the tolerance).

The bridge carries these inputs and outputs (section 12.1).

## 5. Grid-fit check and region re-read

After every read the engine measures how well the confirmed grid fits the photo: seam alignment on
the grid lines plus color homogeneity inside each square, for the whole quilt and per region. It
catches miscounts (including off-by-one and harmonic counts), drift and waviness. Its thresholds are
measured on the corpus (ticket B3), not guessed.

- Global failure: QREP withholds the download, names the failed check in plain words and returns to
  the confirm screen with the corners and counts kept. Why: a miscounted grid makes every square
  confidently wrong.
- Regional suspects: Your pattern outlines them, the download stays available, and the PDF marks
  uncertain squares on its layout chart (PATTERN-SPEC.md, layout chart).

Region re-read, the working interpretation of Jake's decision of 2026-10-06, pending his
confirmation in the sprint-5 morning report: on Your pattern the user drags or expands a square
selection over a wrong region, from a few squares up to the whole quilt. QREP re-reads only that
region (local grid refit, recount if needed, fabric re-assignment) and shows before and after to
accept or discard. It is a re-read, not paint editing.

## 6. The pattern

One pattern outcome: one method, one document, one download (binding rule 2).

### 6.1 Construction method

One method per quilt, chosen by the engine and explained in one plain sentence (PATTERN-SPEC.md,
method selection): units first, same-fabric runs merged, strip sets only where rows repeat, HST,
QST and stitch-and-flip techniques quilters recognize, and a straight-seam sewing order. The user
never picks a strategy, and the document offers no alternates.

### 6.2 The pattern document

- One document, structured by PATTERN-SPEC.md section 2, from the cover to the optional coloring
  page, in QREP's own words. Commercial reference patterns inform structure and conventions only;
  they stay private and are never copied or committed.
- One output action on Your pattern: Download pattern (PDF). The engine exporters stay on the CLI as
  the developer surface (section 12.2).

### 6.3 Finished size

From the size the user sets, QREP picks a rotary-friendly finished square size and shows the
achieved size beside the asked-for size; with no size set, it prints an estimate labeled "estimated
from your photo". The pattern never prints a guess as a measured fact (PATTERN-SPEC.md, cover).

## 7. Math defaults and conventions

MATH.md holds the formulas and vectors. This contract fixes:

- Lengths are integer eighths of an inch (qrep-design-doc.md, Units). Seam allowance 1/4 in: cut
  size is finished size plus 1/2 in.
- Strip cutting assumes 40 in usable width of fabric (WOF), configurable: Jake's decision on #91
  (2026-07-10), kept as the safe default for yields. `Settings.wof` defaults to 320 e; the
  benchmark fixture stores 336 e (42 in) until A6 regenerates it (MATH.md section 1.3).
- Backing has its own width setting, default 42 in, configurable, with a 108 in wide-back option.
  Why: applying 40 in to backing brings back the over-estimate a quilter reported (MATH.md). The
  pattern prints both width assumptions from the settings.
- Backing is computed in both seam orientations with seam allowance and overage; the cheaper layout
  wins. Binding is 2 1/2 in strips, perimeter plus 10 in, counted with its diagonal joins.
- The finishing defaults, each a setting in eighths (qrep/model/schema.py, Settings): backing width
  42 in (`backing_width`), wide-back width 108 in (`wide_back_width`), 4 in of backing and batting
  overhang per side (`backing_margin`, 8 in per axis), 1 in lost per backing seam, a 9 in squaring
  allowance for a backing of two or more panels (`backing_pieced_allowance`) and 4 1/2 in for a
  one-piece or wide backing (`backing_one_piece_allowance`), and a 1/4 yd purchase increment
  (`purchase_increment`). A tie between the two layouts keeps vertical seams. The wide-back line
  appears only when the pieced backing needs two or more panels and one backing side fits within
  the wide width. Batting is the backing's size, and the pattern names the smallest of the five
  MATH.md packages that covers it (F12). One module holds this math
  (qrep/construct/finishing.py), so the cut list, the purchase lines and the pattern print the
  same numbers.
- Yardage comes from strip yields plus a stated margin, never from area alone. A top fabric's
  length is the sum of its cut-line yields (F2), strip-set strips (F3) and joined border strips
  (F4); its purchase adds a 10 percent margin (`top_margin`, in percent). Binding adds nothing
  beyond its extra length, and the backing adds its squaring allowance. Each line rounds up on
  its own to `purchase_increment`, and yards print as mixed fractions of that increment (F13).
  One purchase-line function (`compute_purchase_lines`) serves the CLI, the waste metric and the
  exports, and the yardage report prints each line's length needed and purchase length.
- These defaults stand until Jake changes one, and each is a setting, so a change moves a default,
  not a formula (MATH.md, section 6 lists the questions). A reported discrepancy becomes a failing
  hand-computed test before the fix.

## 8. The quilt model: confidence and provenance

The quilt model records every value with its source:

| Value | Source | Recorded as |
|---|---|---|
| Corners or outer edge, border bands, counts, fabric count, typed finished size | User | User fact, confidence 1.0 |
| Count, corner and fabric-count suggestions; palette colors | CV | Confidence in [0, 1] |
| Fabric per square, unit class, fabric per part | CV | Confidence in [0, 1] per square |
| Grid fit, global and per region | CV | Confidence in [0, 1] |
| Finished size estimated from the photo | CV guess | Low confidence; printed only as an estimate |
| Hand-authored models and fixtures | Author | Confidence 1.0 |

A test asserts that every CV-derived field carries a confidence in [0, 1]. The method and its reason
follow deterministically from the read and carry no confidence of their own.

## 9. Removed surfaces

The editor is archived at tag `archive/editor-v0.3` (commit 834d8be), and 0.4.0 removes from the
web app: paint, palette editing, the seams tool, the Sizing tab, undo and redo, autosave and resume,
project save and open, the blank-grid start, the failure screen's "Start in the editor", the
round-trip panel and the spike page. The strategy cards, five per-artifact downloads, print sheet
and Copy my settings give way to the one download. Restoring editing is a re-port from the tag, not
a revert; Jake accepted that.

0.4.0 removes from the engine: the automatic detection stack (rectify tiers 0 to 3 and GrabCut,
grid estimation, periodicity, block-lattice SNR, the verdict tree and corroboration, the border
scan, the palette detrend, the wasm gate) with its frozen literals (T1 to T5, RESCUE_MIN_PITCH_PX,
the sigma ladder, INTEGER_RATIO_EPSILON, FEEDBACK_REFINE) and the verdict UI; and dead code
(resize_locked, resize_unlocked, the sprint-1 viewer and `qrep view`, stub strategies, dead fields).

Order: Your pattern and its download land before the editor goes (ticket C2 before C6), and the new
read and confirm screen go live before the automatic stack goes (B2, B3 and C3 before B6). Tests and
literals retire only as REBASELINE.md names them.

## 10. Older sections this replaces

Lines are at commit 834d8be. "Design doc" is qrep-design-doc.md; "web doc" is
docs/sprint-2/qrep-web-design-doc.md.

| Section | Status |
|---|---|
| Design doc, Interfaces in v1 and CLI signatures (26-41); Repo layout, `viewer/` (186-187) | Superseded in part: the web app is the only GUI, and section 12.2 sets the CLI; a signature it does not change stands until a ticket changes it and records the change there. |
| Design doc, Quilt model, confidence and scale bullets (49-50) | Superseded by sections 6 and 8. |
| Design doc, Construction engine: strategies, stubs and assembly steps (73-79) | Superseded by section 6; the pure, deterministic plan (69-71) and Metrics (81-91) stand, but the PDF prints no difficulty or time. |
| Design doc, Math defaults (93-99) | Superseded by section 7 and MATH.md. |
| Design doc, CV pipeline through Round-trip accuracy definitions (121-147) | Superseded by sections 3 to 5 and 8; the round-trip accuracy thresholds stay, with corners and counts supplied (REBASELINE.md). |
| Design doc, Testing strategy, PDF line (159); Known risks (202, 204) | Superseded by PATTERN-SPEC.md; the grid-only risk narrows to section 3. |
| Design doc, all other sections | Stand; the plan extends the model and SVG for triangle units. |
| Web doc, bridge surface (65-71) and photo reverse contract (76-79) | Superseded by the bridge v2 contract (section 12.1); the serverless escape seam stays. |
| Web doc, e2e byte-compare (104-108) | Narrowed: the pyodide-tests CI job proves integer-domain byte parity; e2e checks the PDF's structure. |
| Web doc, Persistence policy (121-136) | Suspended: no project files or autosave. "Photos never leave the device" (137-138) stands. |
| Web doc, UI reference (140-153) | Partly suspended, per the notes atop PARITY.md and each UI-SPEC; design-system tokens stay. |
| Web doc, Sizing math ownership (169-181) | Superseded: size math lives only in the Python model package. |
| Web doc, e2e per slice (206-211) | Superseded: e2e covers a confirmed L0 read, Your pattern and the download. |
| Web doc, Amendments (246-267); editor risk (283-285) | Viewer clauses of amendments 1 and 3 superseded; "everything else stands" narrows to this table; editor risk obsolete. |
| qrep-claude-code-prompt.md | REBASELINE.md lists each superseded criterion with its replacement. |
| PARITY.md, both UI-SPEC.md and both PARITY-AMENDMENT.md files | Partly suspended or superseded, per the notes atop PARITY.md and each UI-SPEC. |
| Sprint-3 and sprint-4 plans; docs/sprint-4/DECISIONS.md | Bound only their sprints; frozen thresholds retire through REBASELINE.md; D4 (WOF 42), flipped on #91, yields to section 7. |

## 11. Release readiness

0.4.0 is ready when the plan's gate passes: the read per corpus tier with n stated (fully correct
interior rate, confident-wrong squares rate, refusal recall with a false-warning cap; ticket D5);
calculator parity after the math lands (D7); and a release-candidate PDF review by a virtual quilter
panel of three refute-framed reviewers with distinct quilter personas, using a rubric built from
cited quilter sources (D1, D8). Jake's mother's review stays optional if she becomes available.
Gate numbers are frozen only after the new read is measured. No release is tagged or published
without Jake, and during sprint 5 Pages deploys only on a release tag or manual dispatch.

## 12. Engine surfaces

### 12.1 The bridge

The web app calls the Python engine, which runs in the browser under Pyodide, only through the
bridge (qrep/bridge.py), so the screen and the PDF cannot disagree (section 2). The bridge v2
contract (tickets E1a and E1b) keeps these rules:

- It carries the confirmed read (sections 4, 5 and 8), the sizing call (section 6.3) and the
  pattern export.
- The read request takes the staged photo; the frame, given either as the four corners of the
  pieced field or as the four outer-edge corners plus a list of border bands from the outside in,
  each with one width in squares that need not be whole; the corners in staged-image pixels with
  the crop offset (#101); counts in quilter units (blocks across and down, and squares per block on
  each axis); and an optional fabric count from 2 to 12. Given an outer edge, the engine derives
  the field from it and the bands (B2a); the web converts a dragged band line or a typed inch width
  to squares before it sends the request (C3a). Why: field corners are often hidden by borders or
  binding, so the user can pin the outer edge instead (section 4; plan section 2.1).
- The scope pick (section 2) is not part of E1b's request. It joins the request later, under the
  contract lease (plan section 5.C, Interfaces with other tracks): B4a's triangle classifier skips
  a squares-only pick, and C4's picker sends the pick. Until C4 lands, the read uses the default
  scope, every in-scope unit type (C3c).
- The pattern export takes no strategy. It returns the PDF with the summary Your pattern shows: the
  finished size and its basis, the method and its reason, the fabric letters, names and yards, the
  binding, backing, wide-back and batting lines, both width assumptions and the uncertain-square
  count.
- The web, the eval harness and the corpus annotations use the same field names and units: D3a's
  annotation format reuses E1b's frame, band and count models.
- Every v2 result states an explicit outcome, such as pattern-ready or a refusal with its code. A
  missing or unknown outcome is an error, never a success. Why: today a missing verdict renders as
  readable (web/src/model/verdictStory.ts:82), which breaks binding rule 5.
- A CONTRACT_VERSION, kept equal in qrep/contract.py and web/src/engine/contract.ts, is checked by
  the web worker at boot: it calls bridge.contract_version() after it imports the bridge and before
  it reports boot-done. A mismatch, or an engine that reports no version, stops the app with a
  message that names the app's version and the engine's (or says the engine reports none) and
  tells you to reload. tests/test_bridge.py fails when the two literals differ, and when the
  worker's method allowlist differs from the bridge's envelope functions. E1a and E1b together
  define version 2, and the plan sets which later changes bump it (plan sections 4.2 and 5.A,
  rule 6). Why: a cached wheel from another release must not serve the page.
- Every call returns a typed envelope whose error kind tells your input errors from engine bugs:
  validation for a model that fails validation, a call with the wrong number of arguments, or an
  argument with the wrong type or structure, naming the field (a whole-number argument must be
  exact: 20.9, true and "600" are wrong types); value for an input the engine cannot use, naming
  it (an unknown strategy, a preset object without both a width and a height, a level, seed,
  scale or fabric count out of range, a missing or unreadable image); schema for malformed JSON
  or an unknown schema_version; not_implemented for a stub; and internal for anything else,
  including a KeyError, TypeError or AttributeError raised inside the engine. No traceback
  reaches the app. The worker passes a JavaScript null argument as Python None, because Pyodide
  would otherwise hand the bridge a jsnull.
- render() takes a scale from 1 to 20 pixels per inch (RENDER_SCALE_MAX in qrep/bridge.py, which
  records the arithmetic) and returns kind value outside that range. The bound caps the scale, not
  the image, which also grows with the quilt (#187).

The request and response shapes live in qrep/contract.py and web/src/engine/contract.ts, which E1a
created; E1b adds the request and response models.

### 12.2 The CLI

The qrep CLI stays the developer and test surface; the web app is the product (CLAUDE.md). In
0.4.0:

- `qrep reverse` runs the confirmed read and takes the corners and the counts in quilter units as
  required options (ticket B6a).
- `qrep plan` prints the one method the engine chooses and its reason, and `qrep export` writes the
  pattern PDF and its cut-list text from the one-method pipeline (A6). Fabric amounts come from the
  one purchase-line function (section 7).
- `qrep view` and the sprint-1 viewer go (A7; section 9).
- Signatures this section does not change stay as qrep-design-doc.md lists them (CLI signatures,
  lines 33-41) until a ticket changes one and records the change here.
