# PATTERN-SPEC: the QREP pattern document

Status: binding for sprint 5 once the plan PR (#107) merges; until then a proposal. It replaces
the eight-section booklet contract for the PDF (qrep-claude-code-prompt.md:68 and :74;
qrep-design-doc.md:159 and :202), a supersession that docs/SPEC.md section 10 and
docs/sprint-5/REBASELINE.md record. The literals L-01 to L-14 stay proposals until Jake freezes or
accepts them (plan section 9, item 3). Ids are never renumbered or reused; a change to what an id
means lands through a PR that names the id.

What this file owns: the content of QREP's one pattern document (the PDF), its order, its words and
numbers, its figures, and the checks a reviewer applies to a generated PDF. MATH.md owns how each
number is computed: this file names the number, says where it is printed and says which engine data
it comes from. docs/SPEC.md owns the product contract, and the plan
(docs/sprint-5/qrep-sprint-5-plan.md) owns tickets, order and gates.

How to cite: sections S0 to S11; page rules G-01 to G-13; decisions D-01 to D-10; literals L-01 to
L-14; conflicts X-01 to X-11; method rules M-01 to M-14; conventions C-01 to C-14; gaps GAP-01 to
GAP-27; acceptance checks PS-01 to PS-44. Outside this file, prefix the decision ids ("PATTERN-SPEC
D-04"), because MATH.md uses D-01 to D-18 for defects and the track D tickets are D1 to D9. A
ticket's acceptance criterion names the check and its input, for example:
"- [ ] Pass PS-16 to PS-20 on the PDF generated from the DIC fixture."

## Binding rules

1. One document, one method. The PDF describes one construction method that the engine picks and
   explains in one plain sentence; it never offers alternates or a strategy choice (D-05, section
   3, PS-33). Why: Jake asked for one pattern outcome (plan J6), and a menu of strategies hands the
   engine's decision to the quilter (docs/SPEC.md binding rule 2).
2. Fixed section order: cover, fabric requirements, before you begin, cutting, units, blocks, quilt
   assembly, borders, finishing, layout chart, optional coloring page (section 2, PS-02). Why: it is
   the order a quilter works in (buy, cut, sew, finish), and published patterns put a cover alone on
   page 1 and materials on page 2 in 8 of 8 PDFs read in sprint 4 (docs/sprint-4/RESEARCH.md:54).
3. One source for every number. Fabric requirements, cutting, steps and figure labels all come from
   one cutting layout computed with the MATH.md formulas (M-10). Why: today's booklet computes the
   same quantities in several places, and they disagree (engine-14).
4. Two widths, both printed. Strips are cut at the WOF setting (default 40" usable); backing uses its
   own width setting (default 42", with a 108" wide-back option); the document states both (D-03,
   D-04, S2, S3). Why: Jake's decision J13; computing backing at 40" brings back the over-estimate a
   quilter reported (MATH.md F10, V-BACK-18).
5. Names that cannot collide. Fabrics get letters, pieces get the fabric letter plus a number, and
   blocks get numbers (C-02, C-05, C-06). Why: the quilter matches labels across cutting, steps and
   figures, and today's booklet prints internal ids next to display names (engine-07).
6. Never print a guess as a fact. The cover states how the size was set, and a photo read counts its
   uncertain squares and marks them on the layout chart (S1, S3 rule 10, S10). Why: a quilter
   follows a pattern literally (docs/SPEC.md binding rule 5).
7. Refuse, never approximate. A square that is none of the four unit types, or a layout that needs a
   partial or set-in seam, produces a refusal, never a PDF (M-13, M-14, PS-35). Why: a wrong pattern
   wastes fabric; an honest "not yet" does not (docs/SPEC.md binding rule 4).
8. QREP's own words and figures. The references inform structure and conventions only, and examples
   come from QREP's own or public-domain quilts (Rights and references, PS-39). Why: the references
   are commercial and copyrighted, the repo is public, and its history cannot be rewritten (plan
   section 8).
9. Nothing that misleads. No difficulty rating, time estimate, piece total, internal strategy name,
   internal id or hex code appears (PS-05). Why: today's difficulty and time numbers have no scale
   and rank the methods wrongly (engine-15), and ids and engineering terms confuse quilters
   (engine-07, ux-11).
10. Deterministic bytes. The same model, settings and photo give byte-identical PDFs on the command
    line and in the browser (G-11, PS-04). Why: tests and the browser-versus-native parity check can
    then compare outputs exactly (plan gate G9; CR-process-17).

## Ticket map

The plan's ticket entries set each ticket's acceptance criteria. This table says which part of this
file each ticket builds and which checks cover that part, so a ticket can find its checks.

| Ticket | Builds | Checks |
|---|---|---|
| A1 Finishing math | The backing, binding and batting numbers that S2, S3 and S9 print (MATH.md F6 to F12) | PS-11, PS-12, PS-13 |
| A2 Cutting yields and yardage | The cutting layout behind S2 and S4: strip groups, per-strip yields, partial last strips, border strips joined per piece, top-fabric purchase lines (M-10, M-11) | PS-16, PS-20, PS-28 |
| A3 Construction method selection | Section 3 (M-01 to M-14), the one technique per unit type in S5 with its MATH.md F14 cut sizes, strip sets (S5.5) and the rows method (S7) | PS-17, PS-19, PS-23, PS-24, PS-33, PS-34, PS-35 |
| A4 Pattern document structure (rescopes #95) | Section 2 text and tables (G-01 to G-04, G-09 to G-13; S1 to S9, swatches included) and the section 4 conventions | PS-01 to PS-20 (text), PS-22 (steps), PS-24 to PS-30 (text), PS-38, PS-40 to PS-42 |
| A5 Pattern figures | G-05 to G-08 and every figure: cover render, symbol legend, fat quarter diagrams, unit and block figures, exploded layout, backing and binding corner figures, layout chart (S10), coloring page (S11) | PS-07 (render), PS-21, PS-22 (figures), PS-25, PS-27, PS-30 (figure), PS-31, PS-32, PS-36, PS-37, PS-43, PS-44 |
| B2 Confirmed read | Per-square confidence for S3 rule 10 and the S10 dots; the confirmed block period that M-03 uses | Prerequisite for PS-09, PS-15 and PS-31 on photo reads |
| B4 Triangle units | The unit map that S5 reads: unit type, squares spanned, fabric per part, orientation, confidence (GAP-13) | Prerequisite for PS-22 to PS-24 on triangle units |
| E1 Bridge v2 contract | A PDF entry point that takes no strategy (GAP-26) | PS-04 in the browser |
| C2 Your pattern screen (rescopes #96) | The one Download pattern (PDF) button (D-09) and census names that match S2 (C-03) | PS-40 |
| C4 Colors step and scope picker | The early refusal of out-of-scope quilts (D-08) | PS-35, screen side |
| A6 Consolidated bless | The cut-list goldens that follow the new layout (GAP-27) | None of its own |
| D1 Quilter-voice research | The review rubric that D8 uses (D-10) | None of its own |
| D6 Reference-pattern comparison | An aggregate measure of how closely QREP's PDF follows the conventions observed in R1 to R4 (section 2, "Layout conventions observed"; section 4) | PS-39, run locally |
| D8 Virtual quilter panel | A review of every release-candidate PDF with the D1 rubric and section 6 (D-10) | Every [V] and [M] check, plus a review of the [S] results |

## Rights and references

Plan section 8 governs all reference material, and this file follows it: no reference sentence or
close paraphrase, figure, page design, table, cutting chart or block-specific number appears here
or in any QREP output. What is specific to this file:

- The structure and conventions in sections 2 and 4 were observed in four commercial patterns
  curated as models of a well-made pattern (plan J6). They are cited by title only, as sources of
  conventions:
  - R1: Fireworks (pattern #155). Three photographed pages: basic instructions and cutting, block
    assembly, and quilt assembly with finishing. One quilt of a single repeated block built from
    stitch-and-flip and flying geese units. Its cover and requirements page were not photographed.
  - R2: Colorwash Irish Chain. One photographed page: the title and fabric requirements of a
    squares quilt in four sizes.
  - R3: Applesauce Quilt, with its Apple Block and Left and Right Apple Core Block chapters, from the
    book Scrappiness is Happiness. Block recipes plus the whole-quilt pages; stitch-and-flip units;
    every piece is lettered.
  - R4: Blossom Block, from the same book. A two-page recipe for one block made with
    stitch-and-flip units.
- Statements such as "R1 does X" summarize private page extractions that stay off the repo (plan
  Appendix B says where they live); D6 can check each one locally. Reference figures are named only
  by kind (row diagram, before and after pair, two-panel corner figure).
- Examples, fixtures, test vectors and demo quilts come from QREP's own models or from public-domain
  quilts, never from R1 to R4, and no test names, cites or reproduces a reference.
- The generated pattern name never uses a reference title or a designer's name (C-01, PS-08), and
  no QREP output says it is in the style of a designer.

Evidence used in this file:
- QREP code: file:line at commit 834d8be.
- The current PDF: renders of the repo's Double Irish Chain fixture (the DIC:
  tests/fixtures/double_irish_chain.json, built by qrep/model/fixtures.py; 99 blocks of 1 1/2"
  squares, 75" x 90" finished). Appendix B gives the steps.
- Techniques the references do not show: web pages fetched on 2026-10-07 (Appendix C, W1 to W6).
- Planning sources: Jake's decisions J1 to J17 (plan section 3.1), docs/SPEC.md, the review findings
  in docs/sprint-5/REVIEW.md (engine-01 and so on), and the critique items that the plan's
  Appendix A dispositions (CR-product-24 and so on). "HANDOFF section N" is the private planning
  handoff (plan Appendix B). "The planning draft" is an unpublished sprint 5 draft of this spec that
  covered squares only; this file supersedes it, and X-01 to X-11 record where the two disagreed.
- Anything not checked is marked UNVERIFIED.

## S0. Decisions, literals and conflicts this spec depends on

### Decisions

| ID | Decision | Source |
|----|----------|--------|
| D-01 | One pattern document, formatted like the curated references in structure and conventions only; never their text or diagram art. | plan J6 |
| D-02 | Scope: squares, half-square triangles, quarter-square triangles (hourglass, star points), and stitch-and-flip corners (snowball corners, flying geese). | plan J9; docs/SPEC.md section 3 |
| D-03 | WOF for strip cutting is configurable, default 40" usable. | plan J13; docs/SPEC.md section 7 |
| D-04 | Backing uses its own width setting, default 42" (configurable), with a 108" wide-back option. The pattern states both width assumptions. | plan J13; docs/SPEC.md section 7 |
| D-05 | ONE method per quilt, chosen by the engine with a one-sentence reason, units first; merge same-fabric runs; strip sets only where rows repeat; recognized HST, QST and stitch-and-flip methods; a straight-seam sewing order. | HANDOFF section 5; plan section 2.5; docs/SPEC.md section 6 |
| D-06 | Math comes from MATH.md, with hand-computed vectors written before implementation. Calculators and published patterns are recorded cross-checks, never the source of an assertion. | docs/SPEC.md binding rule 3; plan section 0 |
| D-07 | Section order: title and finished size, fabric requirements, basic instructions, cutting with per-strip yields and lettered pieces, unit and block steps with figures and pressing, quilt assembly diagram, borders, finishing in sewing order, coloring page optional. | HANDOFF section 5; plan J6 |
| D-08 | Out of scope and refused before any pattern is made: curves, applique, on-point settings, medallions. | docs/SPEC.md section 3; plan section 2.3 |
| D-09 | The Your pattern screen offers one Download pattern (PDF) button. | docs/SPEC.md section 6; plan section 2.1 |
| D-10 | The D8 virtual quilter panel reviews every release-candidate PDF with the D1 rubric, in place of a review by Jake's mother, who is not available; her review stays optional. | plan J16 and gate G8; docs/SPEC.md section 11 |

### Literals and choices that need Jake's freeze

| ID | Literal or choice | Proposal | Basis |
|----|-------------------|----------|-------|
| L-01 | Yardage allowance on top fabrics | 10 percent of the strip-plan length, added before rounding; no floor by default (a floor of 4" per fabric is open, X-06) | MATH.md section 1.4, F5 and Q4 |
| L-02 | Purchase rounding increment | One increment for every purchase line, backing included: 1/4 yd by default, or 1/8 yd. OPEN (X-03). | MATH.md section 1.4 and Q3 |
| L-03 | Half-set threshold for strip sets | A row signature must fill at least half a strip set | Planning draft. Why: below half a set, more than half of the segments a set yields go unused. |
| L-04 | Fat quarter usable area | Shelf packing inside 17 1/2" x 20" of an 18" x 21" fat quarter | Planning draft. Why: the margin leaves room to straighten the edges. |
| L-05 | Uncertain-square threshold for the layout chart dot | No value yet; measured on the new read first | plan section 7.2: numbers freeze only after the new read is measured |
| L-06 | HST and QST cut mode | Oversize and trim (HST: finished + 1", trimmed to finished + 1/2"; QST: finished + 1 1/2", trimmed to finished + 1/2"). The exact alternative is HST + 7/8" and QST + 1 1/4". | MATH.md F14 and Q9; Appendix C, W1 to W3. Why: trimming forgives small cutting and sewing errors at 1/8" to 1/4" more fabric per square (MATH.md Q9). |
| L-07 | Pressing plan rule | Open plan when HST or QST points meet at seams; nest plan otherwise | This spec (M-08) |
| L-08 | Coloring page default | Included, with a setting to leave it out | docs/sprint-4/RESEARCH.md:59 |
| L-09 | Layout chart | Always included | Required for the rows method and for photo reads with uncertain squares (S10) |
| L-10 | Minimum type and figure sizes | Body text 10 pt, table text 9 pt, figure labels 7 pt, smallest labeled patch 1/4" on paper | This spec; today's table text is 8 pt (GAP-25) |
| L-11 | Designer-respect line on the cover | Include one plain line (S1) | CR-product-24 |
| L-12 | Problem-report line in the footer or on page 2 | Optional; a link to the QREP site | This spec |
| L-13 | Block gate parameters | At most 8 block types; every type used at least twice except at most one; types at most one quarter of the block count | Planning draft (the qualitative rule); the numbers are this spec's |
| L-14 | User photo beside the cover render | For photo reads, include the photo, labeled as the source photo, downscaled to its printed size, built in the session and never stored | docs/sprint-4/RESEARCH.md:56 records the side-by-side as Jake's requirement. Embedding a raster photo in the browser (Pyodide) build is UNVERIFIED, so A5 probes it first. |

### Conflicts between earlier proposals, and how this spec resolves them

The planning draft, the math audit that MATH.md now carries, and HANDOFF section 5 disagreed in
eleven places. Each resolution below is binding; changing one goes through Jake.

- X-01 Section order. The planning draft put the before-you-begin rules before the fabric
  requirements; HANDOFF section 5 puts fabric requirements first. Resolved: fabric requirements
  first, as published patterns do (materials on page 2 in 8 of 8 PDFs read in sprint 4,
  docs/sprint-4/RESEARCH.md:54).
- X-02 Where the binding method goes. HANDOFF section 5 lists the binding method among the basic
  instructions; the planning draft describes binding only in finishing. R1 names its binding method
  among its basic rules and refers back to it from finishing. Resolved: Before you begin names the
  method and its parameters in one sentence; the step-by-step procedure appears exactly once, in
  Finishing (PS-30).
- X-03 Yardage rounding. The planning draft rounds top fabrics up to 1/8 yd; the math audit keeps
  1/4 yd. MATH.md applies one increment to every purchase line, backing included, with 1/4 yd as the
  default, and leaves the choice to Jake (MATH.md Q3; L-02). Under the default the yards formatter
  keeps quarters; it needs eighths only if Jake picks 1/8 yd (GAP-06).
- X-04 Backing width in the math. The math audit and the planning draft computed backing at 40"
  usable. Jake's decision gives backing its own width, default 42" (plan J13), because 40" would
  worsen the over-estimate a quilter reported. Resolved: MATH.md computes every backing vector at
  42" and keeps 40" results only as configured-width vectors (MATH.md F10, V-BACK-18 to V-BACK-20).
  Its backing width is the width after the selvages are trimmed (MATH.md section 1.3), so S9's
  instruction to trim the selvages matches it; Jake confirms that meaning as MATH.md Q7.
- X-05 Border strip count and wording. The planning draft joins all of a band's strips end to end
  and then cuts the two sides and the top and bottom from the long strip. That pooled count is 9
  strips for the DIC border: the 4 pieces total 317", and 9 x 40" less 8 joins of 1/2" = 356",
  while 8 strips give only 316 1/2". MATH.md counts strips per border piece instead (F4,
  V-BORD-01): 10 strips (3 + 3 + 2 + 2). Neither count may be printed with the other's wording
  (MATH.md F4 and Q6). Join-all wording on a per-piece count adds joins and can run short by up to
  1 1/2" when every piece has zero slack, although on the DIC it happens to leave a spare strip;
  per-piece wording on the pooled count runs short. Resolved: per-piece count with per-piece
  wording, MATH.md's default (S4, PS-28). If Jake picks pooled counting (MATH.md Q6), the count and
  the S4 wording switch together. Joins are straight 1/4" seams, each taking 1/2" of length
  (MATH.md F4).
- X-06 Allowance floor. The planning draft proposes 10 percent with at least 4" per fabric; MATH.md
  proposes 10 percent with no floor (MATH.md section 1.4). Open for Jake as MATH.md Q4 (L-01).
- X-07 Letter namespaces. The planning draft letters fabrics A, B, C and also names blocks Block A.
  Resolved: blocks are numbered (C-06).
- X-08 Test square placement. The planning draft puts the 1" test square on the first page with
  diagrams, which under S1 is the cover, since the cover carries the render. Resolved: page 2
  (G-09), so page 1 stays a cover alone, as in 8 of 8 published PDFs read in sprint 4
  (docs/sprint-4/RESEARCH.md:54).
- X-09 Scope line. The planning draft covers squares on a grid with 2 to 8 fabrics and plain
  borders. Jake's scope adds triangle units (plan J9), and the fabric cap is about 12 (docs/SPEC.md
  section 3). Resolved: the wider scope and the cap (D-02, C-02). Borders stay plain bands, so
  pieced borders are outside this spec (section 1).
- X-10 Crosscut line style. The planning draft draws strip-set crosscut lines dashed. G-07 gives
  each line style one meaning: dashed means sew, dotted means cut. Resolved: crosscut lines are
  dotted (S5.5).
- X-11 Strip sharing between cut lines. The planning draft lets pieces of the same width share
  strips, filling the last strip's remainder first, a common tech-editing practice. MATH.md F2
  gives every cut line its own strips and credits no leftover to another line. Resolved: MATH.md F2
  (M-11, S4), because the printed strip counts and yards must equal its vectors (M-10); R1 also
  cuts separate strips for each size. Sharing can return only through a MATH.md change with its own
  vectors.

## 1. Purpose and audience

Purpose. The PDF is QREP's only product output. A quilter holding only this PDF can buy fabric,
cut, sew and finish the quilt QREP recovered from a photo or from a model. Every number in it comes
from one engine computation, so the requirements, cutting, steps and figures cannot disagree. It is
honest about what QREP does not know: how the size was set and which squares were read with low
confidence.

Audience.
- Primary: a confident beginner to intermediate quilter who owns a rotary cutter, mat, ruler and
  sewing machine and can sew a 1/4" seam. The references assume this level: the book references
  (R3, R4) never define the seam allowance and rely on checkpoints instead. QREP defines its terms
  once and gives one technique per unit, with steps and figures.
- Secondary: an experienced quilter who wants to check the math fast. Every assumption (widths,
  allowance, seam, margins) is printed where it is used.
- Reviewers: people and agents applying section 6, including the D8 virtual quilter panel.

Format. One US Letter portrait PDF that prints at 100 percent on Letter or A4 and reads in
grayscale.

Not in this document: alternate methods, difficulty ratings, time estimates, internal strategy
names (the build line and the reason sentence describe the one method in plain words instead),
metric measurements (except echoing a size the user typed in centimeters), an A4 layout variant
(adopt later per docs/sprint-4/RESEARCH.md:63), size variants (R2 prints four sizes; QREP recovers
one quilt at one size), pieced borders (X-09; backlog #15), quilting motif design, and any
construction outside D-02 (curves, applique, on-point settings, medallions, partial or set-in seams,
paper piecing, templates).

## 2. Document structure

Each section lists its required content, the engine data it comes from (existing code with
file:line, or NEW where nothing exists), its figures, and the layout conventions observed across
the references, described generically. Examples with numbers are illustrative unless they cite the
DIC fixture or a MATH.md vector. A4 builds the text and tables, and A5 builds the figures (ticket
map).

### 2.0 Rules for every page (G)

- G-01 Paper: US Letter portrait, 612 x 792 pt on every page. Side margins at least 1/2" so an A4
  printer at 100 percent clips nothing (today 54 pt = 3/4": qrep/export/pdf.py:312-318).
- G-02 Footer on every page: the pattern name, "page N of M", and a version line such as "QREP
  0.4.0" (version source: qrep/__init__.py:3). No date, so identical inputs give identical bytes.
  No running header, title band, logo or copyright notice. Title bands are reference page design
  (G-06). QREP cannot know who owns a layout recovered from a photo, so this spec proposes no
  copyright notice; the cover's L-11 line covers designer respect, and L-12 takes the place of a
  corrections link.
- G-03 Type: one sans-serif family (built-in Helvetica is fine and needs no embedding). Minimum
  sizes per L-10. Headings in plain words; sentence case.
- G-04 Steps: numbered, restarting at 1 under each subheading. One or two imperative sentences per
  step. A step and its figure stay on the same page; a table row never splits across pages.
- G-05 Figures: numbered Fig. 1, Fig. 2 and so on through the document; a step cites every figure.
  Published patterns use inline numbered figures in 8 of 8 PDFs read in sprint 4
  (docs/sprint-4/RESEARCH.md:54).
- G-06 Figure style: QREP's own flat style, drawn from the user's model: palette fills, thin dark
  outlines, a label in every patch large enough to read (L-10), pressing symbols where pressing
  applies. Sizes stay in the text, except on the cover render, the fat quarter diagram and the
  backing figure. Never imitate a reference's art, page design, title bands, callout cards or type
  treatment (Rights and references).
- G-07 Symbols, defined once in Before you begin: a single-headed arrow means press toward the
  arrow; a double-headed mark across a seam means press open (R3 uses such a mark without defining
  it); a dashed line means sew here (in stitch-and-flip the marked diagonal is sewn on, so it is
  dashed); a dotted line means cut here (in HSTs the marked diagonal is cut on, so it is dotted,
  between two dashed sewing lines).
- G-08 Grayscale: color is never the only carrier of identity. Every fabric patch in every figure
  carries its label or letter, and swatches have an outline so light fabrics show.
- G-09 Print scale: page 2 carries a 1" test square and a print-at-100-percent note
  (docs/sprint-4/RESEARCH.md:58; page placement per X-08).
- G-10 Text is real text, not images, so it can be searched, extracted and read aloud.
- G-11 Determinism: the same model, settings and photo give byte-identical PDFs in the browser and
  on the command line (PS-04). Today only the bridge pins this (qrep/bridge.py:206-216).
- G-12 Voice: neutral and imperative. No first person, no exclamations, no emojis, no designer
  persona. One term per concept (C-14).
- G-13 Callouts: no boxed tips, recipe cards or designer notes (G-06, G-12). Content that the
  references put in callouts appears as plain text only where a quilter needs it: the per-block
  tally (S4), the reason for the pressing plan in one clause (S3 rule 7), and short technique notes
  inside a step (S5.1). Scrap-basket sourcing, fabric SKUs and shop pairings are left out, because
  QREP knows the palette it read, not where the fabrics came from. A separate tip on keeping each
  block's pieces together is left out, because the per-block piece lists (S6) already group them.

### S1. Cover: title and finished size (page 1, alone)

Required content:
- Pattern name: the model's own name when it has one (hand-authored models and fixtures);
  otherwise the deterministic generated name of docs/design/sprint-4/UI-SPEC.md section 4 (a
  structure word plus a mood word, seeded by a content hash; docs/sprint-4/RESEARCH.md:57), checked
  against a denylist that covers the reference titles and other known commercial pattern names. The
  name never claims a traditional or commercial identity: naming a quilt by
  matching it against a block catalog is not in this sprint (plan section 11). Never "in the style
  of" a designer. The download file name follows the same name (UI-SPEC section 4).
- Finished size of the bound quilt, width first, for example 75" x 90".
- One build line in plain words that states the structure and the method, for example: "99
  blocks, 7 1/2" finished, set 9 x 11, strip pieced"; "40 x 52 grid of 2" finished squares, sewn
  in rows"; "20 blocks, 12" finished, set 4 x 5, from half-square triangle units and squares".
- Number of fabrics, for example "3 fabrics, plus backing".
- Size basis line, one of: the size the user asked for beside the achieved size, with the
  rotary-friendly finished square size QREP picked (echoing centimeters if the user typed them);
  or, when the user set no size, a line saying the size is estimated from the photo and naming the
  square size assumed. A guessed size is never printed as a measured fact (docs/SPEC.md section 6;
  plan section 2.1).
- For photo reads with uncertain squares: one line pointing to the count in Before you begin and
  the dots on the layout chart.
- Designer-respect line (L-11), in QREP's words, for example: "QREP recovers the layout of a
  pictured quilt. If this quilt comes from a designer's published pattern, buy that pattern to
  support the designer."
- For photo reads (L-14): the user's photo beside the render, labeled as the source photo.
- Leave out: skill level, difficulty, time estimate, piece totals, internal strategy names,
  internal ids, hex codes. The build line names the method in plain words only.

Engine data:
- Name: Quilt.metadata.name (qrep/model/schema.py:165-167). NEW: the name generator and the
  denylist; neither exists at 834d8be (Appendix B, C7).
- Finished size: Quilt.finished_width and finished_height, borders included (schema.py:201-207).
- Build line: block counts and finished block size. Today inferred by infer_block_structure
  (qrep/construct/strategies.py:47-71). NEW: the confirmed block period from the read
  (docs/SPEC.md section 4), the block gate (M-03) and the chosen method (section 3).
- Fabric count: Palette.fabrics (schema.py:38-55).
- Size basis: NEW stored record of the requested and achieved size. apply_finished_size already
  returns both (qrep/model/finished_size.py:45-81), but nothing stores or prints them; the
  photo-read caveat lives only in free text in the model notes (qrep/vision/pipeline.py:262-266).
- Render: NEW. render_top_svg draws square cells and border bands with rulers
  (qrep/export/svg.py:37-158); it draws no binding, no triangle units and no dimension lines.

Figures: one full-color render of the whole top with borders and binding, triangle units drawn as
triangles, a dimension line under it for the width and one beside it for the height.

Layout conventions observed: the name appears in all four references, set as a display title at
the top; a finished size is printed in 2 of 4 (R2 on its title sheet, as sizes before borders; R3
as dimension lines on a photo of the made quilt); a photo of the made quilt or block appears in 2
of 4; no reference page shows a skill rating or time estimate. Prior research found a cover-only
first page in 8 of 8 published PDFs (docs/sprint-4/RESEARCH.md:54).

### S2. Fabric requirements (page 2)

Required content:
- A table with one row per top fabric, in letter order (C-02): swatch, letter, plain name, yards to
  buy. Yards come from the cutting layout (S4) plus the stated allowance, rounded up per L-02. Add
  "or N fat quarters" when every piece of that fabric fits fat quarters (M-12).
- Binding row: the binding fabric's swatch and letter, yards for binding alone, and the strip count
  written "(N) 2 1/2" x WOF strips". When the binding fabric is also a top fabric, its two rows sit
  together and the note says to buy the sum.
- Backing row (no letter): yards of backing fabric at the backing width setting, written as "N
  lengths of L"" with the seam direction ("seams run across the quilt" or "along the quilt"), for
  whichever orientation needs less fabric (MATH.md F10 computes both and breaks ties), plus the
  alternative "or Y yd of 108" wide backing" only when the pieced backing needs two or more panels
  and one backing dimension fits within 108"; otherwise the wide-back line is left out, not printed
  as zero (MATH.md F11).
- Batting row (no letter): W" x H", the top plus the margin on every side (4" default), and the
  smallest standard batting package that covers it, named by class with its dimensions and no brand
  (MATH.md F12; the default for MATH.md Q11).
- A footnote stating the rounding and allowances (L-01, L-02) and both width assumptions (D-03,
  D-04). MATH.md section 1.5 owns the content of every assumption sentence in S2 and S3, with
  numbers taken from the settings: this footnote carries its items 3 and 6 to 8, and S3 rules 2, 5,
  6 and 9 carry items 1, 2, 5 and 4.
- One supplies line: rotary cutter and mat, 6" x 24" ruler, neutral thread; when triangle units are
  present, add a marking tool for diagonal lines and a square ruler with a 45 degree line for
  trimming. Stitch-and-flip needs a marked diagonal (R3); trimming HSTs aligns the ruler's 45
  degree line with the seam (Appendix C, W2).
- The 1" test square and print note (G-09).

Engine data:
- Purchase lines: NEW purchase function fed by the cutting layout (M-10). Today length is
  ceil(cut area / WOF) with quarter-yard rounding and no allowance (qrep/construct/yardage.py:14,
  50-58, 61-94); duplicate math sits at yardage.py:97-143 and strategies.py:279-285.
- Yards format: format_yards prints quarters only (qrep/export/yardage_report.py:8-13).
- Backing: NEW backing plan per MATH.md (both orientations, seam allowance, separate width setting,
  wide-back option). Today: vertical seams only, with 42" hard-coded in the line name and text
  (yardage.py:16, 36-47; pdf.py:241-242); Settings has one wof field (schema.py:131-143).
- Binding: NEW join-aware count per MATH.md F7. Today ceil(binding_length / wof) is computed in
  three places (strategies.py:133, strategies.py:243, pdf.py:211); the strip width is
  Binding.strip_width (schema.py:111), while Settings.binding_strip_width is never read
  (schema.py:136).
- Batting: margin from settings.backing_margin (schema.py:138); today the PDF uses a duplicate
  constant (pdf.py:37-39, 227-228). NEW: the package lookup (MATH.md F12).
- Letters, names and swatch colors: NEW letter mapping and color naming; Fabric holds only id, name
  and color (schema.py:24-35).
- Fat quarters: NEW packing (M-12); no fat quarter code exists (Appendix B, C7).

Figures: swatches only: a small square filled with the fabric's display color, with a thin dark
outline (R1 draws its white fabric as an outlined empty square).

Layout conventions observed: one entry per fabric, background first; single fabrics in yards;
binding and backing on their own lines. One reference (R3) offers both a standard-width and a 108"
wide backing; another prints backing yardage with no width at all. Yardage appears in shop
increments. A supplies list appears in 1 of 4 (R2). QREP rules: no thirds of a yard, no raw inch
lengths, no cell counts, no hex codes. No scrappy groups: each letter is one fabric with its own
yards, so R3's piece-count-only lines, per-print counts and one-print alternatives have no QREP
counterpart.

### S3. Before you begin (basic instructions)

Required content: nine short numbered rules in QREP's words, in this order, plus a tenth for photo
reads. The planning draft proposed 6 to 8; rules 6 and 9 are added because D-04 requires the
backing width to be stated and HANDOFF section 5 puts the binding method in the basic instructions
(X-02).
1. Read the whole pattern before cutting.
2. Every piecing seam is 1/4", and every cut size already includes seam allowances ("piecing",
   because rule 6's backing seams are 1/2"; MATH.md section 1.5 item 1).
3. Should-measure sizes are unfinished: they include the 1/4" allowance on every edge.
4. RST means right sides together.
5. WOF means width of fabric. Strips are cut across the full width; yields assume N" of usable
   width per strip (N is the strip-cutting setting, default 40), a safe planning figure; wider
   fabric gives extra pieces. The rule has no tie to trimmed selvages, so it holds whatever Jake
   answers to MATH.md Q7 (MATH.md section 1.5 item 2).
6. Backing yardage assumes N"-wide backing fabric with the selvages trimmed (backing setting,
   default 42), joined with 1/2" seams pressed open, extending past the quilt on every side by the
   margin setting (default 4"), plus the backing allowance, in the layout that uses less fabric
   (MATH.md section 1.5 item 5). The 108" alternative is stated with the backing row and its
   footnote (S2).
7. This quilt's pressing plan (M-08) with its reason in one clause, and the symbol legend (G-07).
8. How labels work: fabric letters and swatches, piece labels such as A1, and the warning used for
   mirror-image units.
9. The binding method in one sentence: double-fold binding from 2 1/2" strips joined with diagonal
   seams, machine sewn to the front, mitered at the corners, finished by hand on the back, with
   extra length for the corners and the final join (binding-extra setting, default 10"; MATH.md
   section 1.5 item 4); the steps are in Finishing (X-02).
10. Photo reads only: how many squares were read with low confidence; each carries a dot on the
    layout chart; check them against the photo before cutting.

Every abbreviation used anywhere in the document is defined here (C-08).

Engine data: Settings.seam_allowance (schema.py:134); Settings.wof (schema.py:135, 42" today; D-03
requires 40"); NEW backing width setting; Binding.strip_width (schema.py:111); NEW pressing plan;
GridRegion.cell_confidence (schema.py:69, 89-93) and threshold L-05. Today none of these values is
printed, and nothing in qrep/export or qrep/construct reads confidence (Appendix B, C7; engine-09).

Figures: the symbol legend (one small drawing per symbol).

Layout conventions observed: 2 of 4 references carry a basic-instructions block. R1 uses a
numbered list of basic rules that covers reading first, RST, the seam allowance, the binding
method, its WOF assumption and where corrections are posted, and it states the usable width its
yields assume. R2 gives one sentence on fiber, width and prewashing. The book references (R3, R4)
state no general rules on the photographed pages; their trim and checkpoint arithmetic implies
1/4" seams.

### S4. Cutting

Required content:
- One block per fabric, in letter order, headed by swatch, letter and name.
- Numbered steps inside each fabric block, restarting at 1. Each step cuts one group of WOF strips,
  "Cut (N) W" x WOF strips.", with the subcuts indented beneath: label, count, size (short side
  first), shape word, per-strip yield and total. Example: "A2: subcut (6) strips into (120) 2"
  squares, 20 per strip."
- Partial last strip: when the last strip of a group is only partly used, say how many pieces come
  from it. Each subcut gets its own strips; no strip is shared between two subcuts, because MATH.md
  F2 counts them that way (X-11).
- Strip-set fabric is cut only as strips: "Set aside (N) W" x WOF strips (A1) for strip set 1."
  Pieces that come out of strip sets are never listed as cut pieces.
- Border strips, one entry per border band, worded per piece the way MATH.md F4 counts them (X-05):
  "Cut (N) W" x WOF strips. For each side border, join (k) strips end to end with straight seams and
  trim to L1". For the top and bottom borders, join (k) strips each and trim to L2"." A border piece
  no longer than the usable width is cut from one strip with no join, and both pieces of a pair come
  from one strip when they fit in it (MATH.md F4, V-BORD-04). Joins are straight 1/4" seams, each
  taking 1/2" of length. The pooled form, joining every strip and then cutting four borders, is
  printed only if Jake picks pooled counting (MATH.md Q6).
- Binding strips under the binding fabric: "(N) 2 1/2" x WOF strips for binding."
- Triangle-unit pieces at the technique's cut size (S5), naming the unit they feed, for example
  "B3: (24) 4" squares for HST unit 1" for 3" finished HSTs under L-06's proposed oversize-and-trim
  mode (the exact mode would print 3 7/8"; MATH.md F14).
- Order within a fabric (M-11): border strips, binding strips, strip-set strips, then the remaining
  pieces from the widest strip to the narrowest.
- Per-block tally when blocks repeat: one line per block type giving how many of each label one
  block takes and how many WOF strips that is, so a quilter can change the block count.
- Cut sizes only: no finished sizes, no component column.

Engine data: NEW cutting layout (M-10, M-11): per fabric, strip groups (width, count), subcuts
(label, size, quantity, yield, last-strip remainder), strip-set strips, border strips with joins
and subcut lengths, binding strips, per-block tallies, fat quarter recipes. Today: one line per
fabric and size with a total (strategies.py:149-176); labels such as `1 1/2" square, cut 2" x 2"`
(strategies.py:77-83); a per-strip yield exists only for strip-set segments (strategies.py:376);
squares inside strip sets are listed as cut lines (strategies.py:407-409); borders are one piece
per side (strategies.py:86-126); binding strips (strategies.py:129-146); the PDF table has Fabric,
Piece, Component, Quantity, Cut size and Finished size columns (pdf.py:130-148).

Figures: only when fat quarters are offered: one to-scale fat quarter cutting diagram per distinct
recipe, an 18" x 21" outline with both edges labeled, every piece labeled with its label and cut
size, leftover visible, scale stated.

Layout conventions observed: cutting is grouped by fabric, and each line gives count, cut size and
shape, with cut sizes only. R1 cuts full WOF strips first, then subcuts each group, stating how
many pieces one strip gives and how many are needed in all; it also reserves strips for the border
and tallies one block's pieces so the quilter can make more or fewer blocks. R1 gives one fat
quarter diagram that every fat quarter follows. R3 and R4 letter every piece and reuse the letter
in text and figures. R3 lists borders and binding as strips or rectangles in the same list. R1
indents subcuts under their strip step and puts counts in parentheses inside sentences.

### S5. Making the units

This section exists when the quilt has triangle units, strip sets or plain sub-units. It opens with
the one-sentence method reason (M-09) and the sewing order in one line. If the quilt has no units,
both lines open S6 instead.

Required for every unit:
- One subheading per unit: type plus number, for example "HST unit 1" or "Flying geese unit 2". A
  mirror-image unit gets its own subheading and a warning not to mix the two.
- A piece list keyed by label to the cutting steps, with swatches.
- Numbered steps, each one or two imperative sentences with its figure.
- A checkpoint: "Trim to S" square." for oversize-and-trim techniques, or "Unit should measure W" x
  H"." for exact ones; always unfinished.
- "Make N." with digits.
- Pressing stated in the step and drawn on the figure, following the quilt's pressing plan.
- Exactly one technique per unit type. No alternates.

Engine data for all of S5: NEW unit map from the read (unit type, squares spanned, fabrics,
orientation, confidence; B4); NEW technique table from MATH.md F14 (cut sizes, yields, trim sizes)
with this spec's mirror rules; NEW checkpoints; NEW pressing plan. The model has only square cells
of one fabric each (schema.py:58-101). No construct or export code handles triangles; in qrep/,
triangle terms appear only in vision comments (qrep/vision/repeats.py:328; qrep/vision/grid.py:21,
289). StripSet exists (qrep/construct/plan.py:44-53) but is built from raw cell rows without
merging, including single-fabric sets (strategies.py:378-405; engine-05).

Layout conventions observed: units come first, then blocks. R1 opens block assembly with a
per-block piece list keyed to the cutting steps, each line ending in a swatch. Steps are short
imperatives, one action each, with a figure per step. A checkpoint and a make count follow each
unit. Mirror-image units are named and counted separately, and R1 warns that its two differ. Every
reference gives one technique per unit with no alternatives. Pressing appears as arrows on figures
or as one stated rule. R1 letters its step figures; R3 and R4 pair a before view with an after
view.

#### S5.1 Half-square triangle (HST) units

- Technique: two at a time from two squares.
- Cut size (MATH.md F14 owns the numbers): finished + 7/8" exact, or finished + 1" and trimmed to
  finished + 1/2" (L-06; Appendix C, W1 and W2).
- Steps: pair one square of each fabric RST, lighter on top; draw a corner-to-corner line on the
  back of the lighter square; sew 1/4" from the line on both sides; cut on the line; press per the
  plan; trim with the ruler's 45 degree line on the seam.
- Yield: 2 identical units per pair of squares (W1).
- Figures: the marked pair with the dotted cutting line on the diagonal and a dashed sewing line on
  each side of it; the two pressed units with pressing symbols; optionally the trim.
- Note: the bias edge is cut only after sewing, so the unit is stable until then (W1); a short tip
  says to press without pulling.
- Orientation: an HST and its mirror image are the same unit turned, so HSTs with the same two
  fabrics are one unit type.

#### S5.2 Quarter-square triangle (QST) units: hourglass and star points

- Technique: two HSTs made from two squares, then joined and cut again.
- Cut size: finished + 1 1/4" exact, or finished + 1 1/2" and trimmed to finished + 1/2" (MATH.md
  F14; L-06; W3, W4).
- Steps: make two HSTs from the pair without trimming; place them RST with contrasting fabrics
  facing and the seams nested; mark the diagonal that crosses the seam; sew 1/4" from it on both
  sides; cut; press; trim with the ruler's diagonals on both seams.
- Yield: 2 units per pair of starting squares (W5).
- Mirror pairs: the two units come out as mirror images of each other unless the unit is
  mirror-symmetric (two-fabric hourglass, or three fabrics with the repeated fabric on opposite
  sides). Appendix A derives this. Cutting counts and make counts must account for it, and mirror
  units get separate names (C-06).
- Three-fabric star points: the same method, starting from two different HSTs.
- Counts: MATH.md F14 gives cut sizes and yields for two-fabric hourglass units only. Cut counts per
  fabric for three- and four-fabric units are not in MATH.md yet (F14 edge cases, Q9); they must be
  added there, with hand-computed vectors and the mirror pairs above, before PS-23 and PS-24 can
  pass for such units.
- Figures: the HST pair with the crossing diagonal drawn dotted and a dashed sewing line on each
  side; the resulting units with pressing symbols, mirror pairs side by side and labeled.

#### S5.3 Stitch-and-flip corners (snowball units)

- Technique: a corner square sewn on its diagonal onto a base piece, then trimmed and pressed.
- Cut sizes (MATH.md F14): base piece finished + 1/2" each way; corner square equal to the finished
  leg of the corner triangle plus 1/2". R4's checkpoint arithmetic is consistent with this rule,
  and R3 sizes each flip square to match the edge it is sewn onto. No reference piece size is
  restated here.
- QREP validity rule: corner legs along one side may total at most that side's finished length (at
  exactly the length, the two points meet on the seam line, as in R4).
- Steps: draw a corner-to-corner line on the back of every corner square at the first step that
  uses that label; lay it RST on the corner; stitch along the line; cut away the excess, leaving
  1/4" past the stitching; press per the plan (toward the corner in the nest plan; R3 presses this
  way).
- Yield: 1 unit per base piece.
- Figures: one before and after pair per stage of corners (the pairing R3 and R4 use).

#### S5.4 Flying geese units

- Technique: stitch-and-flip, one goose at a time, from one rectangle and two squares, the
  construction R1 uses.
- Cut sizes (MATH.md F14): rectangle (finished height + 1/2") x (finished width + 1/2"); two squares
  at finished height + 1/2". A goose finishes twice as wide as it is tall (W6).
- Steps: draw the line on both squares; stitch the first square to one end along its line, cut the
  excess to 1/4", press; repeat at the other end with the line mirrored; the point must sit 1/4"
  inside the top raw edge (W6).
- Yield: 1 unit per rectangle.
- Identity: geese pointing different ways are one unit turned; geese with the goose and sky fabrics
  swapped are different units (R1 makes both kinds).
- Figures: two before and after pairs (first corner, second corner).

#### S5.5 Strip sets and segments

- When: only under method (a) of M-07.
- One figure per strip set: strips in sewing order with labels, a pressing symbol across the seams,
  and dotted crosscut lines (G-07, X-10) across the full height of the set.
- Text: sew the strips lengthwise in this order, press, make N sets, then crosscut (M) S" segments,
  K per set. A row signature and its reverse share one set: turn the segment end for end.
- A row that is a single piece after merging is cut as a rectangle, never as a strip set.
- Provenance: none of the references uses strip sets; these rules follow standard Irish chain
  practice in the same step format (sentence, figure, checkpoint, make count).

#### S5.6 Plain sub-units (optional)

When a block splits into repeated 2 x 2 or 3 x 3 sub-units (turning allowed), make the sub-units
first, each with its own checkpoint (M-06). R1 builds its block from repeated sub-units this way.

### S6. Making the blocks

Required content:
- One subheading per block type, "Block 1", "Block 2", numbered by first appearance in reading
  order.
- A piece and unit list keyed by label.
- An exploded block figure: units, segments and pieces drawn apart in their rows, then the joined
  block; every patch labeled; pressing symbols chosen so that meeting seams nest (nest plan) or
  press-open marks (open plan).
- Steps: lay out, sew each row, press, join the rows, press.
- Checkpoint: "Block 1 should measure S" square." (finished + 1/2").
- "Make N.", equal to the count in the quilt layout.
- A block that appears turned in the layout is the same block, made the same way and turned when
  placed. A mirror-image block is a separate type.

Engine data: block types and counts (BlockStructure: strategies.py:31-45); NEW block recipe (rows of
units, segments and pieces) and checkpoint (AssemblyStep has no size field: plan.py:56-60). Today
block steps are text substeps listing fabric ids (strategies.py:316-331) or segment stacks
(strategies.py:441-451). Block SVGs draw cells only, without labels, exploded rows or arrows
(svg.py:164-207), and only the command line reaches them: the bridge exports only the top SVG
(qrep/bridge.py:191-193).

Figures: one exploded block figure plus the assembled view per block type.

Layout conventions observed: R1 sews its sub-units in rows, joins the rows, then gives the
unfinished block checkpoint and make count, with a row diagram and a finished block diagram. R3
draws exploded rows beside the assembled view, with pressing arrows. R4 joins its units in pairs,
then joins the pairs.

### S7. Quilt assembly

Required content:
- Two or three sentences: the layout (for example "11 rows of 9 blocks, alternating Block 1 and
  Block 2"), the pressing (rows in opposite directions, or open), joining the rows, and the
  quilt-center checkpoint ("The quilt center should measure W" x H"."). No numbered step per row.
- Rows method: a figure draws the first two rows apart with every merged piece labeled, so both
  pressing directions show; the remaining rows are sewn from the layout chart (S10); the text says
  which way to press each row; very large quilts are split into labeled sections.
- Sashing and cornerstones, when present in the layout, are named here and joined with the rows,
  with straight seams.

Engine data: the block layout (BlockStructure.layout: strategies.py:37) or the cell grid
(schema.py:58-68); center finished size (schema.py:95-101); NEW center checkpoint. Today: one
numbered step per block row (strategies.py:193-217; the DIC PDF prints 11 of them); the assembly
SVG draws block outlines with letters, not exploded and without borders (svg.py:274-348); its
no-block fallback is a title line with no drawing (svg.py:278-291; engine-18).

Figures: one exploded layout: rows drawn apart with row numbers and block numbers (or the cell grid
for the rows method), borders drawn as separate strips, pressing symbols on the row seams.

Layout conventions observed: one or two sentences and one large exploded diagram; the row
structure stated in words; no numbered step per row. R3 adds the quilt-center checkpoint and arrows
on the row seams. R1 draws the border strips apart from the blocks.

### S8. Borders

Required content:
- One short step per border band, inner to outer: sew the side borders first, then the top and
  bottom borders; press toward the border.
- Lengths come from S4 (each border joined from its own strips, then trimmed to length). Before
  sewing, measure the quilt through its center and trim the border to match if needed.
- Each band is named by position (inner, outer) and fabric letter.

Engine data: Quilt.borders (schema.py:104-107, 175); cut lengths today, one piece per side (sides =
running height + 1/2"; top and bottom = widened width + 1/2": strategies.py:86-126); NEW strip
count with joins (MATH.md F4, X-05). Today the only pressing text in the booklet is here
(strategies.py:236-237), and the PDF section prints one sentence per band (pdf.py:199-207).

Figures: share the S7 layout, or draw the center with side borders attached and the top and bottom
borders apart.

Layout conventions observed: sides first, then top and bottom. R3 cuts exact lengths from joined
WOF strips and presses toward the border. R1 measures the quilt and cuts set-aside strips to match,
printing no lengths.

### S9. Finishing, in sewing order

Required content:
1. Backing: cut N lengths of L", trim the selvages, sew along the long edges with 1/2" seams and
   press the seams open; or, when S2 offers the wide-back line, cut one piece of 108" wide backing
   to L". Figure: the quilt outline over the backing panels, showing the seam direction and the
   overhang on every side.
2. Layer and baste: backing right side down, then batting, then the top right side up; smooth and
   baste.
3. Quilt as desired, with one plain suggestion that suits the quilt, for example an allover design
   or straight lines.
4. Binding: join the strips with diagonal seams and press them open; press the long strip in half
   lengthwise; sew it to the front with raw edges together, leaving a tail; stop 1/4" from each
   corner and fold to miter; join the two ends; turn to the back and stitch by hand. A two-panel
   corner figure in QREP's style. The binding steps appear only here.

Engine data: NEW backing plan (MATH.md F8 to F11) and Settings.backing_margin (schema.py:138);
batting (pdf.py:37-39, 243-244 today); binding count (MATH.md F7). Today binding steps 22 and 23
come before any layering or quilting (strategies.py:243-266; engine-08), binding is described a
second time in a separate Binding section (pdf.py:210-220), the quilting text talks about authored
motifs (pdf.py:229-237), and the backing text gives a panel count and total length only
(pdf.py:241-242).

Figures: the backing layout figure and the two-panel binding corner figure.

Layout conventions observed: quilting is always left to the maker. R1 pieces its backing from two
lengths with the selvages removed, layers backing, batting and top, and illustrates the binding
corner in two panels. R3 joins its binding pieces end to end; its photographed page does not settle
whether those seams are straight or diagonal. No reference gives a batting size.

### S10. Layout chart

Required per L-09. Content: the full grid with row numbers on the left and column numbers on top;
the fabric letter in every cell; triangle-unit cells drawn split, with a letter in each part;
uncertain cells marked with a dot; large grids split across pages, each part labeled with its row
and column range and sharing one row or column of overlap with its neighbor. No cell is printed
smaller than the L-10 minimum.

Engine data: GridRegion.cells and cell_confidence (schema.py:58-69); NEW unit map (B4); L-05. None
exists in the PDF today.

Layout conventions observed: none of the photographed reference pages has a lettered layout chart;
the references rely on block diagrams and one exploded quilt diagram, which suits block quilts but
not a quilt sewn square by square. The chart is QREP's addition for the rows method and for
photo-read uncertainty.

### S11. Coloring page (optional)

Per L-08: the same outline with every seam line (diagonals included) and no fill, so a quilter can
try colors. Bundled coloring pages are near-universal in modern pattern listings
(docs/sprint-4/RESEARCH.md:59). None exists today, and none of the photographed reference pages
includes one.

## 3. Method selection

A3 implements this section; A4 prints its outputs (the build line, the reason sentence and the
steps).

- M-01 One method per quilt, picked by the engine. The document never offers alternates, and the
  product drops the strategy choice. Today the strategy is a bridge argument
  (qrep/bridge.py:156-159, 197-205) chosen on strategy cards (web/src/shell/PatternPanel.tsx:20-38)
  with strip as the default (web/src/state/project.tsx:47-48).
- M-02 Units first. Every triangle unit, plain sub-unit and strip-set segment is made before any
  block, in the S5 order: HST, QST, snowball, flying geese, strip sets, plain sub-units. Each unit
  type has exactly one recognized technique (S5): HSTs two at a time from squares, QSTs from two
  HSTs, snowball corners and flying geese by stitch-and-flip.
- M-03 Block structure. For photo reads, blocks come from the counts the user confirmed in quilter
  units (blocks across x squares per block) and the block-consistent vote (docs/SPEC.md section 4;
  plan section 2.2), so a few misread squares cannot change the method. For models without
  confirmed counts (fixtures, hand-authored models), treat the grid as blocks only when all of these
  hold: a period divides the grid; there are at most 8 block types; most types are used at least
  twice; there are far fewer types than blocks (L-13 gives numbers). Today any period with 8 or
  fewer types passes (strategies.py:47-71). On three random 40 x 40 two-fabric grids it returned
  20 x 20 "blocks" with 4 types used once each, every time (Appendix B, C5; engine-11).
- M-04 Merge same-fabric runs, plain cells only. Within a row of a block, consecutive cells of one
  fabric become one piece, cut (run x cell) + 1/2" long. Within a block, consecutive rows that are
  one fabric across the full width become one rectangle. A merge never includes a unit cell. Both
  merges keep every seam straight. No merged piece is cut longer than the strip-cutting usable width
  U (defined in M-05): a longer run splits at a cell boundary into the fewest pieces that fit,
  joined by straight seams, so every piece comes from one WOF strip. This answers MATH.md Q8;
  MATH.md F2 keeps a fallback for any piece that still exceeds U.
- M-05 Strip sets (method a). Allowed when blocks pass M-03 and plain multi-piece row signatures
  repeat. A signature is the row's sequence of merged pieces; after merging it must have 2 to 7
  strips and fill at least half a set (L-03). Segments per set = floor(U / segment cut width), where
  U is the strip-cutting usable width (default 40", D-03; MATH.md F3). A signature and its reverse
  share one set. Single-piece rows are rectangles. Rows that contain units are never strip pieced;
  they are sewn from units and cut pieces in the block steps.
- M-06 Optional plain sub-unit layer, as in S5.6.
- M-07 Pick one: (a) strip sets per M-05; (b) blocks from units and cut pieces, one recipe per block
  type sewn row by row; (c) rows, when there are no blocks: a lettered layout chart, each row sewn
  from units, squares and merged rectangles (columns instead of rows if that needs fewer pieces
  after merging), pressing alternating by row. Tie-break when more than one qualifies: the lower
  effort count, where effort = pieces cut + crosscuts + seams sewn, counting a strip-set seam once
  per set, plus a penalty for unused segments. Triangle-unit work is the same under every method, so
  it never decides the tie.
- M-08 Pressing plan, one per quilt (L-07). Nest plan: every seam pressed to one side, chosen so
  seams meet in opposite directions; strip sets toward the darker strip; rows alternate;
  stitch-and-flip seams toward the corner. Open plan: every seam pressed open. In both plans border
  seams are pressed toward the border. The plan is stated once (S3) and drawn on every figure. Today
  only borders get pressing text (strategies.py:236-237).
- M-09 Reason sentence. One sentence in plain words naming the deciding fact: what repeats, or that
  nothing repeats. Examples: "Two blocks repeat across the quilt, so you sew long strips together
  and cut them into segments instead of cutting every square." "No block repeats, so you sew the
  quilt row by row from the layout chart." No strategy names and no effort numbers.
- M-10 One source for every number. Strip counts, subcuts, yardage, make counts, step text and
  figure labels all come from one cutting layout computed at the strip-cutting WOF, so they cannot
  disagree.
- M-11 Cutting. Give each piece the strip width that needs less fabric: compute both orientations
  and keep the shorter total, ties going to the narrower strip (MATH.md F2). That is usually the
  short side, but not always: six 6" x 7" pieces take one 7" strip (6 per strip at U = 40") rather
  than two 6" strips (5 per strip). Yield per strip = floor(U / other side); strips = ceil(quantity
  / yield). Each cut line gets its own strips, and no leftover strip end counts toward another line
  (MATH.md F2, X-11). Strip-set, border and binding strips are listed as strips. A top fabric's
  yardage = the sum of its strip widths, border and strip-set strips included, plus the allowance
  (L-01), rounded per L-02 (MATH.md F5); binding strips are their own purchase line with no
  allowance (MATH.md F7).
- M-12 Fat quarters and precuts. Offer "or N fat quarters" for a fabric when every piece is at most
  about 17 1/2" long and the pieces pack into one or two fat quarters within L-04. Strip-set, border
  and binding fabrics stay yardage only, because 21" strips halve the segments per set. Name a
  precut only when a cut size matches it exactly (2 1/2" strips, 5" or 10" squares).
- M-13 Straight-seam sewing order. Every join is a straight seam across the full edge of both parts,
  in the order units, block rows, blocks, quilt rows, quilt center, borders, finishing. No partial
  or set-in seams; none of the photographed reference steps uses one (R1 to R4). A layout that
  cannot be sewn this way is refused, not approximated (engine-10 shows today's modern strategy
  producing such layouts).
- M-14 Scope guard. A cell that is neither a plain square nor one of the four unit types produces
  the out-of-scope refusal (D-08), never a PDF with approximations.

Worked example (DIC fixture, qrep/model/fixtures.py:7-16, 34-37; 50 of the fixture's Block A and 49
of its Block B, which the new document calls Block 1 and Block 2 (C-06); 1 1/2" finished cells;
re-derived by hand):
- Block A rows: b b c b b, b b b b b, c b b b c, b b b b b, b b c b b. Merged, row 1 is blue 3 1/2",
  cream 2", blue 3 1/2" (strip set 1); row 3 is cream 2", blue 5", cream 2" (strip set 2); the two
  all-blue rows are not adjacent, so each is one 2" x 8" rectangle.
- Block B rows: b c c c b, then three all-cream rows, then b c c c b. Merged, the end rows are blue
  2", cream 5", blue 2" (strip set 3), and the three cream rows become one 5" x 8" rectangle.
- Segments are 2" wide, so a set yields floor(40 / 2) = 20. Strip set 1: 2 per Block A x 50 = 100
  segments, 5 sets. Strip set 2: 50 segments, 3 sets. Strip set 3: 2 per Block B x 49 = 98
  segments, 5 sets. Total 13 three-strip sets, 26 long seams, plus 100 blue 2" x 8" and 49 cream
  5" x 8" rectangles.
- Cream for the strip sets: (5 + 3 x 2) = (11) 2" strips and (5) 5" strips. Cream rectangles: 5"
  strips, floor(40 / 8) = 5 per strip, ceil(49 / 5) = (10) strips.
- Cream border, 3 3/4" finished and cut 4 1/4" wide: (10) strips, 3 joined for each 83" side
  border and 2 for each 75 1/2" top and bottom border (MATH.md V-BORD-01); the pooled wording would
  print (9) (X-05).
- Today's plan instead sews 25 five-strip sets (SS1 5, SS2 5, SS3 3, SS4 5, SS5 7; 100 long seams),
  two of which are single-fabric (SS2 all blue, SS5 all cream), and 74 of the 100 long seams join a
  fabric to itself (hand count in Appendix B, C3).

## 4. Conventions

A4 applies these to every line of text; A5 applies C-04 to C-06 and C-09 to C-10 to figure labels.

| ID | Topic | Rule | Example | Basis |
|----|-------|------|---------|-------|
| C-01 | Pattern name | The model's own name if it has one, else the generated name checked against the denylist (S1); never "in the style of" anyone | (generated) | docs/design/sprint-4/UI-SPEC.md section 4; docs/sprint-4/RESEARCH.md:57; Rights and references |
| C-02 | Fabric letters | A, B, C in order of area in the top; a fabric used only for binding comes last; skip I and O so piece labels never look like numbers; cap of about 12 fabrics (A to M without I) | A, B, C | Planning draft; docs/SPEC.md section 3; plan section 2.1 (the stepper stops at 12) |
| C-03 | Fabric names | A plain color word, unique within the pattern; fabric A (most area) is named Background when it is light, and otherwise gets a color word like the rest; value words (light, medium, dark) separate similar colors; authored names are kept; the web fabric census uses the same names | Background, Navy, Light blue | Planning draft; R2; plan section 2.1 (census) |
| C-04 | Swatches | Filled square of the fabric's display color with a thin dark outline, wherever a letter appears in a table or heading | (graphic) | R1 |
| C-05 | Piece labels | Fabric letter plus a number in cutting order; the same label in cutting, piece lists, steps and figures; each label is unique across the whole pattern (R3 restarts its letters in every block, so one letter names different pieces) | A1, A2, B1 | R3, R4 |
| C-06 | Other names | HST unit 1, QST unit 1, Snowball unit 1, Flying geese unit 1 (mirror units named separately, with "mirror image of unit 1"); Block 1; Strip set 1; Row 1 at the top; inner and outer border; side borders, top and bottom borders; Fig. 1 | Block 2 | R1, R3; X-07 |
| C-07 | Units of measure | Inches and yards only; a straight double quote as the inch mark; "yd" for yards; no metric except echoing a centimeter size the user typed | 2 1/2", 3 1/2 yd | Planning draft; backlog #86 (full metric display) |
| C-08 | Abbreviations | Only WOF, RST, HST, QST and yd, each defined once in Before you begin; "fat quarter" spelled out; no other shortened words | WOF | R1, R2 |
| C-09 | Fractions | Mixed fractions in eighths, ASCII slash, one space after the whole number; never decimals, hyphenated fractions or fraction glyphs (they break text search) | 1 1/2", 3/4", 5 7/8" | qrep/model/units.py:13-26; planning draft |
| C-10 | Dimensions | Lowercase x with spaces; rectangles short side first; the strip width is the number stated in the strip step, usually the short side (M-11); squares as "S" square"; only the quilt and the quilt center are width x height, matching the cover's dimension lines | 2" x 8" rectangle; 4" square; 75" x 90" | R3, R4; MATH.md F2 |
| C-11 | Counts | Counts in parentheses inside sentences; digits always; yields as "N per strip"; "Make N." after every unit and block; mirror pairs as "Make 8 (4 of each)" | Cut (12) 2" x WOF strips. | R1; planning draft |
| C-12 | Sizes by kind | Cutting lists carry cut sizes only; checkpoints carry unfinished sizes; finished sizes appear only for the quilt, blocks and cells in the build line and reason text | Block 1 should measure 8" square. | Planning draft |
| C-13 | Rounding | Cut sizes exact to 1/8" and never rounded; yields floor; strip and panel counts ceil; yards rounded up line by line to the one purchase increment (L-02), backing included; allowances added before rounding; batting printed as an exact size plus a package, never as rounded yards | 49 / 5 per strip = 10 strips | MATH.md section 1.4, F2 and F12 |
| C-14 | Wording | One term per concept: unit, block, row, strip set, segment, border, binding, backing, batting, selvage (one spelling; R1 mixes two); imperative voice; no first person | Sew the rows together. | R1 |

## 5. Gap list versus the current QREP PDF

Observed by rendering the DIC fixture with each of the three strategies (Appendix B, C1 and C2) and
reading the code at 834d8be. In short: today's PDF has 3 pages and 0 figures; it prints internal
ids, hex codes, difficulty and time; it lists 2,475 squares that the strip sets already contain; it
binds before layering; and 3 test files pin its old structure. The Review column gives the
docs/sprint-5/REVIEW.md finding that covers the same defect.

What exists and can be kept:
- The two-layer design: build_sections makes structured Section objects and render_booklet lays
  them out, so tests assert on content without parsing PDF bytes (pdf.py:1-10, 53-87).
- Integer eighths everywhere and one length formatter that already prints C-09 style fractions
  (qrep/model/units.py:1-26); seam allowance and cut add in Settings (schema.py:131-143).
- Border piece lengths and the sides-first order (strategies.py:86-126, 229-242), the binding
  length as perimeter plus 10" (schema.py:137, 209-215), and the 4" per side backing and batting
  overhang (schema.py:138); MATH.md keeps all of these (F4, F6, F8).
- Byte-stable rendering through reportlab invariant mode, today only in the bridge
  (bridge.py:206-216), and fixed PDF metadata (pdf.py:319-320).
- Per-cell confidence (schema.py:69, 89-93), requested and achieved size (finished_size.py:45-81),
  the StripSet model (plan.py:44-53), and SVG drawing code that can seed figure geometry
  (svg.py:37-348).

| ID | Spec needs | Today (file:line) | Review | Checks |
|----|-----------|-------------------|--------|--------|
| GAP-01 | Eleven-section structure in the D-07 order | Eight sections (pdf.py:41-50, 65-87); a title-only cover reading "QREP pattern booklet" (pdf.py:322-327). Pinned by tests/test_pdf.py:47-50, tests/test_bridge.py:28 and 281-294, and tests/test_wasm_artifacts.py:23 and 41-56; by the contract lines qrep-claude-code-prompt.md:68 and :74 and qrep-design-doc.md:159; and by the "not a layout engine" line, qrep-design-doc.md:202. REBASELINE.md decides each pinned test; no ticket changes one outside that record. | engine-03 | PS-01, PS-02 |
| GAP-02 | Footer, page N of M, version, test square, print note | None: the story has no page callback (pdf.py:312-337); the version is available at qrep/__init__.py:3 | - | PS-03, PS-38 |
| GAP-03 | Byte-identical output everywhere | Command-line renders differ run to run (C4); only the bridge pins invariant mode (bridge.py:206-216); the design doc says the PDF is never byte-tested (qrep-design-doc.md:106) | engine-20 | PS-04 |
| GAP-04 | No strategy names, difficulty, time or piece totals | The intro prints the strategy, 2479 pieces, difficulty 16 and 3968 minutes for the DIC (pdf.py:90-104; metrics at plan.py:63-77 and strategies.py:269-297); the web shows difficulty and time (PatternPanel.tsx:217-223) | engine-15, ux-11, ux-21 | PS-05 |
| GAP-05 | Fabric letters, swatches and plain names | The fabrics table prints name, internal id, hex and cell count (pdf.py:107-114); steps print ids such as "b b c b b" (strategies.py:319, 420-422); photo reads name fabrics "Fabric N" with ids f0 and up (qrep/vision/pipeline.py:72-75, 270-272) | engine-07 | PS-10, PS-36 |
| GAP-06 | Yardage from the strip layout plus allowance, in the L-02 increment (eighths only if Jake picks 1/8 yd) | Area / WOF with quarter-yard rounding and no allowance (yardage.py:14, 50-58, 61-94); raw inches printed next to yards (pdf.py:116-122); a quarters-only formatter (yardage_report.py:8-13); duplicates (yardage.py:97-143; strategies.py:279-285). Pinned by tests/test_construct.py:67-96 (area-over-WOF lengths and a 42" backing on a tiny quilt) and tests/test_exports.py:72-78 (quarters-only format); MATH.md section 3.2 lists every test that pins today's math with its new value, and REBASELINE.md lists them | engine-02, engine-14 | PS-10, PS-20 |
| GAP-07 | Backing: both orientations, seam-aware, own width setting, 108" option, N lengths of L" | Vertical only, no seam allowance, 42" in the name and text (yardage.py:16, 36-47; pdf.py:224-226, 241-242); one wof setting (schema.py:131-143); no wide-back line. Pinned by tests/test_construct.py:202-210 and tests/test_exports.py:62-69 (5 1/2 yd and the 42-inch label for the DIC), whose new values come from hand computation (MATH.md section 3.2, V-BACK-09) | engine-13 | PS-12 |
| GAP-08 | A join-aware binding count from one helper; binding described once | ceil(binding_length / wof) three times (strategies.py:133, 243; pdf.py:211); Settings.binding_strip_width unread (schema.py:136); binding in steps 22 and 23 and again in its own section (strategies.py:243-263; pdf.py:210-220); the 9-strip count at 42" is pinned by tests/test_exports.py:57-61 | engine-14, engine-23 | PS-11, PS-29, PS-30 |
| GAP-09 | Batting margin from the backing margin setting, and the batting package (MATH.md F12) | A duplicate constant (pdf.py:37-39 versus schema.py:138); no package line | engine-14 | PS-13 |
| GAP-10 | Before you begin | Seam allowance (schema.py:134) and WOF (schema.py:135) are never printed; no RST or WOF definitions, pressing plan or legend | - | PS-15 |
| GAP-11 | Strips then subcuts, labels, cut sizes only | One line per size with a total (pdf.py:130-148; strategies.py:149-176); a yield only for strip-set segments (strategies.py:376); squares inside strip sets listed as cut lines (strategies.py:407-409): the DIC PDF lists 1,246 blue and 1,229 cream 2" squares beside the strip sets (C2); Finished size and Component columns (pdf.py:135-144); size-text labels (strategies.py:77-83) | engine-01 | PS-16 to PS-19 |
| GAP-12 | Border strips joined per piece, then trimmed to length (X-05) | One piece per side at full length (strategies.py:86-126): the DIC PDF asks for 4 1/4" x 83" sides, longer than any WOF strip (C2); one sentence per band (pdf.py:199-207) | engine-06 | PS-28 |
| GAP-13 | Triangle units in the model and read | Square cells of one fabric only (schema.py:58-101); no construct or export code for triangles (Appendix B, C7); sprint 4 ceded triangles in the model (docs/sprint-4/RESEARCH.md:70). B4 adds the unit map. | - | PS-22 to PS-24 |
| GAP-14 | One engine-chosen method with a gate, merging and a reason | A user-chosen strategy through the bridge (bridge.py:156-159, 197-205); three strategies plus four stubs (strategies.py:596-604); strip raises on grids without blocks (strategies.py:366-370); the gate is missing (strategies.py:47-71; C5); single-fabric strip sets (strategies.py:394-405); greedy merging without a straight-seam check (strategies.py:473-513); the modern strategy groups cut lines by orientation, so a rectangle and its quarter turn print as two lines (strategies.py:149-176, 516-579), which C-10 and M-11 rule out | engine-04, engine-05, engine-10, engine-11, engine-19 | PS-33, PS-34, PS-35 |
| GAP-15 | Checkpoints and make counts after every unit and block | AssemblyStep has no size field (plan.py:56-60); make counts only inside step titles (strategies.py:325, 418, 446) | - | PS-22, PS-25 to PS-27 |
| GAP-16 | One pressing plan, drawn | Borders only (strategies.py:236-237) | engine-08 | PS-22, PS-36 |
| GAP-17 | Two-sentence quilt assembly, no per-row steps, no plan-data tables | One step per block row (strategies.py:193-217); a strip-set table with Sets, Segments per set and Segments needed columns (pdf.py:151-184) | - | PS-27 |
| GAP-18 | Figures in the PDF | 3 pages and 0 images for all three strategies on the DIC (C1); SVGs exist (svg.py:37-348), but only the top SVG reaches the web (bridge.py:191-193); block SVGs are unlabeled (svg.py:164-207); crosscut marks stop 18 px short of the set bottom (svg.py:241-266); the assembly SVG is not exploded (svg.py:274-348); the no-block fallback has no drawing (svg.py:278-291). reportlab 5.0.0 is installed and svglib is not (C6), so figures can be drawn with reportlab graphics without a new dependency; whether that runs unchanged in Pyodide is UNVERIFIED | engine-03, engine-18, ux-03 | PS-07, PS-36 |
| GAP-19 | Cover with render, build line, size basis, generated name | A title plus a fixed subtitle (pdf.py:322-327); no name generator or denylist (C7); requested and achieved size computed but not kept (finished_size.py:45-81); the size caveat only in notes (pipeline.py:262-266) | engine-03, engine-09 | PS-07, PS-08, PS-09 |
| GAP-20 | Uncertain squares counted and dotted | cell_confidence exists (schema.py:69, 89-93); no export reads it (C7) | engine-09 | PS-15, PS-31 |
| GAP-21 | Finishing in sewing order with layering | No layering or basting step; quilting text about authored motifs (pdf.py:229-237); the backing gives panels and a total only (pdf.py:241-242) | engine-08 | PS-29 |
| GAP-22 | Layout chart and coloring page | None | - | PS-31, PS-32 |
| GAP-23 | Fat quarters and precuts | None (C7) | - | PS-21 |
| GAP-24 | One download whose numbers match the screen | Five downloads (PatternPanel.tsx:40-46); the web recomputes batting yards itself (web/src/state/patternText.ts:57-58). C2 and C6 own the screen side. | - | PS-40 |
| GAP-25 | Type sizes | Table text 8 pt (pdf.py:301-309), below L-10 | - | PS-42 |
| GAP-26 | A PDF entry point that takes no strategy | bridge.export_pdf(model_json, strategy) (bridge.py:197); E1 owns the change | - | PS-33 |
| GAP-27 | Cut-list goldens follow the new layout | tests/golden/cutlist_strip.md and .csv encode today's cut lines (MATH.md section 3.2); they change only in A6's one consolidated [bless] commit, after the math and document bytes settle (plan section 3.4) | - | PS-20 |

## 6. Acceptance checks

Inputs a reviewer needs: the generated PDF, the model JSON, settings and photo it came from, and the
MATH.md vectors. Text checks extract text with pypdf after collapsing whitespace and dropping
straight double quotes, the same normalization the current tests use because pypdf can drop inch
marks (tests/test_pdf.py:36-40). Tags: [S] scriptable from text or PDF structure, [V] visual, [M]
needs the model or MATH.md.

Who applies them: the ticket that builds a part turns its [S] checks into tests (ticket map); D8
applies the [V] and [M] checks to every release-candidate PDF and reviews the [S] results (plan gate
G8); PS-39 runs only locally, because its inputs are private, and D6 runs it on every
release-candidate PDF. A panel finding that asks for something this file rules out is recorded for
Jake, not built, because acceptance criteria change only with his approval (plan section 3.3).

Whole document (A4; PS-04 also E1)
- PS-01 [S] Exactly one PDF; every page is 612 x 792 pt portrait.
- PS-02 [S] Section headings appear in this order: cover (page 1 alone), Fabric requirements,
  Before you begin, Cutting, Making the units (if any units), Making the blocks (if any blocks),
  Quilt assembly, Borders (if any borders), Finishing, Layout chart, Coloring page (if enabled).
- PS-03 [S] Every page footer has the pattern name, "page N of M" with the right N and M, and the
  QREP version; no page shows a date.
- PS-04 [S] Two generations from the same model, settings and photo give identical bytes, on the
  command line and in the browser; the browser and native PDFs extract to the same text.
- PS-05 [S] None of these appear anywhere: strategy names (historical, modern, "strip strategy"),
  "difficulty", "minutes", "heuristic", a piece total, internal fabric ids (regex `\bf\d+\b`, and
  the model's own ids as standalone tokens in steps), hex colors (`#[0-9a-fA-F]{6}`), decimal sizes
  (`\d+\.\d+"`), hyphenated fractions (`\d+-\d+/\d+`), fraction glyphs.
- PS-06 [S] Every length is a mixed fraction in eighths with an inch mark (C-09); every dimension
  pair uses " x "; every rectangle in a cutting line is short side first.

Cover (A4; render A5)
- PS-07 [S][M][V] Page 1 has the name, the finished size W" x H" equal to the model's finished width
  and height, a build line, the fabric count, a size basis line, and one render with width and
  height dimension lines that match the printed size.
- PS-08 [S] The name is not on the denylist, and no page says "in the style of".
- PS-09 [S][M] When the user set no size, the size basis line says the size is estimated from the
  photo and names the square size assumed; a size the user set is echoed beside the achieved size.

Fabric requirements (A4; values A1 and A2)
- PS-10 [S][M] One row per top fabric in letter order, each with swatch, letter, name and yards;
  letters follow area order (C-02); names are unique.
- PS-11 [S][M] The binding strip count is the same in Fabric requirements, Cutting and Finishing and
  equals the MATH.md vector for the quilt's perimeter.
- PS-12 [S][M] The backing row gives N lengths of L" at the backing width setting with the seam
  direction of the orientation that needs less fabric; the 108" alternative appears exactly when
  MATH.md F11 shows one and is absent otherwise; the values equal the MATH.md vectors.
- PS-13 [S][M] Batting = finished top plus the configured margin on every side, and the package
  named is the one MATH.md F12 picks (or its larger-than-king statement).
- PS-14 [S] The footnote states the rounding, the allowances and both width assumptions, and the
  supplies line is present; the supplies add a marking tool and a square ruler when triangle units
  exist.

Before you begin (A4)
- PS-15 [S][M] Numbered rules cover 1/4" piecing seams, cut sizes including seams, unfinished
  checkpoints, RST, the WOF value actually used (with no claim that it is measured after trimming
  selvages), the backing width actually used, the pressing plan with its reason, the symbol legend,
  labels, and the one-sentence binding method; photo reads add the uncertain-square count. Every
  abbreviation is defined here before its first use elsewhere.

Cutting (A4; values A2; fat quarter diagrams A5)
- PS-16 [S] Every cutting step reads "Cut (N) W" x WOF strips" with indented subcuts that give
  label, count, size, per-strip yield and total; for each subcut group, strips x yield >= total and
  (strips - 1) x yield < total; a partial last strip is stated.
- PS-17 [S][M] No piece is listed both as a cut piece and inside a strip set; strip-set fabric
  appears only as strips.
- PS-18 [S] The set of piece labels is closed: every label defined in Cutting is used later, and
  every label used later is defined in Cutting.
- PS-19 [S][M] For each label, the total cut equals the sum over units and blocks of pieces per unit
  times make count, plus any spare that the text states.
- PS-20 [S][M] Each top fabric's yards equal the engine's purchase line, which equals the sum of its
  strip widths (cut-piece, border and strip-set strips) plus the allowance, rounded per L-02
  (MATH.md F5); the binding line equals the binding strips alone, with no allowance (MATH.md F7); no
  strip is counted for two cut lines (X-11).
- PS-21 [S][V][M] When "or N fat quarters" is printed, a to-scale diagram with an 18" x 21" outline
  shows every piece of that fabric inside the usable area, and N matches the diagrams.

Units and blocks (A3 and A4; figures A5; triangle units need B4)
- PS-22 [S][V] Each unit has exactly one technique, steps numbered from 1, a figure per step, a
  checkpoint and "Make N."; pressing is stated or drawn.
- PS-23 [S][M] Unit cut sizes match the MATH.md F14 technique table for HST, QST, snowball and flying
  geese units, recomputed from the finished sizes.
- PS-24 [S][M] Mirror-image units are named and counted separately with a warning; QST make counts
  account for mirror pairs (Appendix A).
- PS-25 [S][M] Each block type has an exploded figure, a checkpoint equal to its finished size plus
  1/2", and a make count equal to its count in the layout.
- PS-26 [S][M] Every checkpoint (unit, block, quilt center) equals the sum of its parts' finished
  sizes plus 1/2".

Assembly, borders, finishing (A4; figures A5; values A1 and A2)
- PS-27 [S][V] Quilt assembly has two or three sentences (layout, pressing, joining) plus the
  quilt-center checkpoint and one exploded layout figure with row numbers; no numbered step per row.
  For the rows method, a figure also draws the first two rows apart with every merged piece labeled
  (S7).
- PS-28 [S][M] Borders: sides first, then top and bottom; press toward the border; cut lengths,
  strip counts and the stated join type equal MATH.md and come from the same computation as the
  cutting text, which is worded per piece unless Jake picked pooled counting (X-05); a
  measure-and-trim instruction is present.
- PS-29 [S] Finishing runs backing, layering and basting, quilting, binding, in that order.
- PS-30 [S][V] The binding procedure (diagonal joins, fold, sew, miter, join the ends, hand finish)
  appears only in Finishing, with a corner figure; Before you begin has exactly one sentence about
  binding.

Layout chart and coloring page (A5; uncertainty needs B2)
- PS-31 [S][V][M] The layout chart has row and column numbers and a letter in every cell; the number
  of dotted cells equals the uncertain count in Before you begin; split pages are labeled with their
  ranges and overlap.
- PS-32 [V] When enabled, the coloring page is the same layout as an unfilled outline.

Method (A3)
- PS-33 [S][M] The document describes one method, with the one-sentence reason at the start of
  construction; no alternates; no single-fabric strip set; strip sets only for repeated plain
  signatures; a signature and its reverse share one set; no merged piece is cut longer than the
  strip-cutting width (M-04).
- PS-34 [V][M] Every join joins two parts along a full straight edge; no partial or set-in seam.
- PS-35 [M] A model with an unsupported cell (curve, applique, on-point, medallion) or a layout that
  needs a partial seam produces a refusal, never a PDF.

Figures, print and rights (A5 and A4; PS-39 D6; PS-40 C2)
- PS-36 [V] Figures come from the model (fills match the swatches; every patch labeled); sizes
  appear only on the cover render, fat quarter and backing figures; a step cites every figure as
  Fig. N; the symbol legend matches the symbols used.
- PS-37 [V] Printed in grayscale, every fabric in every figure is still identifiable by its label.
- PS-38 [S][V] The test square measures 72 x 72 pt in the PDF and 1" on paper at 100 percent; the
  print note sits beside it; side margins are at least 36 pt.
- PS-39 [S] No run of 10 or more consecutive words matches the private reference extractions (run
  locally, never in CI); no reference title or designer name appears.
- PS-40 [S][M] The Your pattern screen shows the same finished size, fabric names and yards as the
  PDF for the same model.
- PS-41 [S] All instruction text and numbers extract as text.
- PS-42 [S] No text is smaller than the L-10 minimums (body 10 pt, tables 9 pt, figure labels 7 pt),
  read from the PDF font sizes.
- PS-43 [S][M] Every number printed in a figure label equals the same number in the text.
- PS-44 [V] Each step sits on the same page as its figure, and no table row splits across a page
  break.

## Appendix A. Mirror pairs from two-at-a-time QSTs (hand derivation)

Derived by hand; none of the pages in Appendix C states it. MATH.md leaves mirror behavior to this
spec (MATH.md section 1.1 and F14 edge cases), so A3, which implements S5.2, confirms the derivation
with a sewn sample or a cited source before PS-24 relies on it. A second, independent derivation
reflected the second HST's quarters across the cutting diagonal and got the same result.

Name the four quarter triangles of a square T (top), R (right), B (bottom), L (left). An HST seamed
on the diagonal from the top right corner to the bottom left corner has one fabric in T and L and
the other in R and B. Lay HST 1 face up (X1 in T and L, Y1 in R and B). Lay HST 2 face down on it
with its seam on the same diagonal, so that through the stack its fabrics sit X2 over T and L and
Y2 over R and B. Sew on both sides of the other diagonal (top left to bottom right) and cut on it.
The top-right piece of the stack holds HST 1's T and R quarters and HST 2's T and R quarters. When
it is opened, HST 2's half turns over the seam line, so its T quarter lands in L and its R quarter
lands in B. Unit 1 reads, clockwise from the top: X1, Y1, Y2, X2. The same steps for the
bottom-left piece give unit 2: X2, Y2, Y1, X1 clockwise from the top. Starting unit 2 at X1 and
reading it counterclockwise gives X1, Y1, Y2, X2, which is unit 1. So unit 2 is unit 1's mirror
image. The two coincide only when the unit is mirror-symmetric: X1 = Y2 or Y1 = X2 (two-fabric
hourglasses and three-fabric units with the repeated fabric on opposite sides). The only other
symmetric case, X1 = X2 with Y1 = Y2, stacks like fabrics on each other and gives back a plain HST
look, so it never occurs in a real QST. With four different fabrics, or with the repeated fabric on
adjacent sides, the method yields one unit of each hand.

## Appendix B. How the current-PDF observations were made

Every observation below was made against commit 834d8be with the repo venv and
PYTHONDONTWRITEBYTECODE=1, writing output to a temporary folder outside the repo, and was re-run on
2026-10-07 with the same results. Anyone with the repo can repeat it.
- C1. Load tests/fixtures/double_irish_chain.json with qrep.model.io.loads. For each of the strip,
  historical and modern strategies, build the plan with qrep.construct.get_strategy(name)(quilt)
  and render it with qrep.export.pdf.render_booklet(quilt, plan, path). Read each PDF with pypdf:
  each has 3 pages of 612 x 792 pt and 0 images; the sizes are 5873, 5336 and 5705 bytes; the plans
  have 23, 17 and 17 assembly steps.
- C2. Extract the strip PDF's text. Page 1 holds only the name and "QREP pattern booklet". The other
  pages hold: the strip strategy sentence, 2479 pieces, difficulty 16 and 3968 minutes; a fabrics
  table with ids b and c and their hex colors; purchase rows 128" (3 3/4 yd) blue, 154 1/8" (4 1/2
  yd) cream, 22 1/2" (3/4 yd) binding and 196" (5 1/2 yd) "backing, any 42-inch WOF fabric";
  cutting rows of 1246 blue and 1229 cream 2" x 2" squares; borders cut 4 1/4" x 83" and 75 1/2" x
  4 1/4"; 9 binding strips cut 2 1/2" x 42"; strip sets SS1 "b b c b b" (5 sets), SS2 "b b b b b"
  (5), SS3 "c b b b c" (3), SS4 "b c c c b" (5) and SS5 "c c c c c" (7) at 21 segments per set;
  steps 9 to 19 join block rows 1 to 11; steps 22 and 23 prepare and attach the binding; Finishing:
  2 panels for 196" of 42-inch fabric, batting 83" by 98".
- C3. Hand count of self-joins in C2's strip sets: SS1 2 of 4 seams x 5 sets = 10; SS2 4 x 5 = 20;
  SS3 2 x 3 = 6; SS4 2 x 5 = 10; SS5 4 x 7 = 28; total 74 of 100 long seams.
- C4. Render the strip PDF twice through render_booklet, without the bridge's invariant mode, about
  1 s apart: the bytes differ.
- C5. Run qrep.construct.strategies.infer_block_structure on 40 x 40 grids whose cells are drawn
  from two fabrics by random.Random(seed), seeds 1, 2 and 3: each time p = 20, 4 types, a 2 x 2
  layout and counts [1, 1, 1, 1].
- C6. pip list in the venv: reportlab 5.0.0, svgwrite 1.4.3, pypdf 6.14.2, pillow 12.3.0; no
  svglib.
- C7. git grep at 834d8be over qrep/ and web/src: no name generator, denylist, fat quarter, test
  square or color-name code; no confidence or provenance use in qrep/export or qrep/construct. In
  qrep/, triangle terms appear only in vision comments (qrep/vision/repeats.py:328;
  qrep/vision/grid.py:21, 289); in web/src, only in the verdict copy that refuses triangles today
  (web/src/model/verdictStory.ts:51-55, 114).

## Appendix C. Web sources for techniques the references do not show (fetched 2026-10-07)

Paraphrased; no text copied. MATH.md F14 owns the unit cut sizes and yields and cites its own
sources; W1 to W6 remain the evidence for the technique steps in S5.
- W1 sewcanshe.com, easy half-square triangles (2015): HSTs two at a time; cut finished + 7/8" for
  exact units, or + 1" and trim; the bias edge is cut after sewing.
  https://sewcanshe.com/2015-5-27-quilting-unplugged-easy-half-square-triangles-hsts/
- W2 lindas.com, half-square triangle guide: two-at-a-time cut at finished + 7/8", 2 units per
  pair, trim to finished + 1/2" with the ruler's 45 degree line on the seam.
  https://lindas.com/pages/half-square-triangle-guide-all-methods
- W3 lindas.com, quarter-square triangle tutorial: finished + 1 1/4" exact or + 1 1/2" to trim;
  HSTs first, then paired, sewn on both sides of the second diagonal, cut, pressed and trimmed.
  https://lindas.com/blogs/tips-and-tricks/quarter-square-triangle-tutorial
- W4 createwhimsy.com, quarter-square triangle block: add 1 1/4" to the finished size.
  https://createwhimsy.com/projects/how-to-make-a-quarter-square-triangle-quilt-block/
- W5 patchworkposse.com, hourglass block: two hourglass units from each pair of squares; trim all
  units to one size. https://www.patchworkposse.com/hour-glass-quilt-block-pattern/
- W6 lindas.com, flying geese tutorial: the stitch-and-flip rectangle is finished + 1/2" both ways
  with squares at finished height + 1/2"; geese are 2:1; keep 1/4" between the point and the raw
  edge. https://lindas.com/blogs/tips-and-tricks/flying-geese-quilt-block-tutorial

Limits: the fetched summaries of W3 and W4 disagreed on the QST yield (one said one unit per pair,
the other four from its example); W5 states two per pair, which matches the hand derivation in
Appendix A (two squares make two HSTs, which make two QSTs). The yield in S5.2 rests on W5 plus that
derivation.

## Verification

What was checked for this version on 2026-10-07, and how:
- Copying. A script compared this file with the private page extractions of R1 to R4: every
  maximal run of 6 or more shared words, every phrase the extractions quote from the pages, and a
  sentence-level similarity screen (difflib, threshold 0.5). No shared run is longer than 7 words;
  the 7-word runs are trade phrases (the fat quarter size, folding the binding strip, a list of
  cutting tools), and the 6-word runs are trade phrases or the reference titles. Two quoted page
  phrases occur, both generic. The screen flagged 28 of 1,120 sentences; each was read and shares
  only trade terms, numbers or a title. No reference table or figure is described in enough detail
  to redraw it.
- Repo citations. All 124 distinct file:line citations resolve to existing lines at 834d8be
  (checked with git show). The draft was written from full reads of the PDF, construct and model
  modules, and a sample of the cited ranges (pdf.py, schema.py, bridge.py, plan.py,
  strategies.py, svg.py, PatternPanel.tsx, project.tsx, patternText.ts, tests/test_pdf.py,
  tests/test_bridge.py and docs/sprint-4/RESEARCH.md) was read again and matches.
- Current PDF. Appendix B's C1, C2 and C4 to C7 were re-run against 834d8be and reproduced. C3, the
  X-05 border arithmetic and the section 3 worked example were recomputed by hand; the per-piece
  border count agrees with MATH.md V-BORD-01.
- MATH.md. Every F, V and Q id and every MATH.md section this file cites exists in MATH.md as
  written on 2026-10-07.
- Coverage. Two earlier refute passes checked that every element of the planning draft is carried
  here or excluded with a reason, and checked each reference observation against the extractions.
  This version removed the private pointers, cites the references by title, and words the
  observations in S3, S5.6, S6, S8 and S9 more generally, so they describe conventions without
  design detail.

Not checked: the Appendix C pages were not fetched again. Whether reportlab graphics run unchanged
in Pyodide (GAP-18) and whether a raster photo embeds in the browser build (L-14) are UNVERIFIED.
Appendix A awaits A3's confirmation.
