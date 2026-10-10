# D1: Quilter review rubric for the D8 panel

Date 2026-10-10. Built from the research in [D1-quilter-voice.md](D1-quilter-voice.md); every
bracketed id such as [S-D07] is a source in [D1-sources.json](D1-sources.json), fetched on
2026-10-10. Each item states what quilters say makes a pattern trustworthy or clear, how a reviewer
checks it on a QREP PDF, and the PATTERN-SPEC section 6 check (PS-01 to PS-44) it matches. Items
with no matching check are listed in section 4 as gaps for the A4 and A5 owners. This rubric changes
no PS check and no MATH.md vector.

## 1. How D8 uses it

- Each of the three reviewers takes one persona from D1-quilter-voice.md section 7 (P1 confident
  beginner, P2 experienced traditional piecer, P3 finisher), reads the PDF in the order that persona
  checks first, and scores every item below on every candidate PDF.
- Score each item **pass**, **fail** or **n/a** (for example, no triangle units in the quilt). A
  fail cites the page, the PDF text or figure, and the item id; a finding without that evidence is
  dropped (plan D8).
- Severity of a fail:
  - **critical**: a quilter following the PDF buys too little fabric, cuts a wrong size, or sews a
    wrong-size result (any number that disagrees with the MATH.md vector or the reviewer's hand
    recomputation);
  - **major**: a missing or ambiguous instruction that forces the quilter to guess, or an
    assumption the numbers depend on that the PDF does not state;
  - **minor**: friction a careful quilter works around.
- Every reviewer recomputes by hand, from the MATH.md formulas, the backing (R-03), the binding
  (R-06 and R-07) and one cutting yield (R-02), as plan D8 requires.
- Items marked with a persona weigh more for that reviewer; all items apply to all reviewers.
- A finding that asks for something PATTERN-SPEC rules out (R-30) is recorded for Jake, not filed
  as a defect (PATTERN-SPEC section 6).

## 2. Items

### Numbers you can trust

| Id | Item | What quilters say | Check on the PDF | PS check | Persona |
| --- | --- | --- | --- | --- | --- |
| R-01 | Every assumption behind the numbers is printed | Calculators and publishers assume different widths, overhangs, seam losses and rounding, and some hide them, so quilters cannot tell why numbers differ [S-B15, S-B16, S-B17, S-B18, S-B35]; a publisher states its 40 in width and its extra for crooked cuts [S-D32] | The fabric requirements footnote and Before you begin state: the strip-cutting width used, the backing width used, the overhang per side, the rounding increment, the top-fabric margin and the backing allowance | PS-14, PS-15 (the overhang is not named by either; gap G-1) | P3 |
| R-02 | Buying exactly what is printed never runs short | Running short is the most reported fabric complaint, from wrong pattern yardage and from patterns written for wider fabric [S-B02, S-B04, S-B03, S-B39, S-B12] | Pick one cutting line: strips x per-strip yield covers the pieces, and the fabric's yards cover the sum of its strip widths plus the margin. Recompute one yield by hand (MATH.md F2) | PS-16, PS-20 | P1, P2 |
| R-03 | The backing covers the quilt with the stated overhang | Charts exist whose stated yardage cannot cover the quilt at their own width [S-A02, S-A08]; turning the backing can save fabric [S-D10, S-A03] | Recompute F8 to F10: n panels x width minus (n - 1) in reaches the backing side; the printed N lengths of L in, the seam direction and the yards equal the MATH.md vector | PS-12 | P3 |
| R-04 | Backing preparation is stated | Longarm quilters ask for a square backing, selvages removed, seams pressed open, and say uneven seams and selvages in seams cause sag and puckers [S-B05, S-B23, S-D35, S-B38, S-A14] | Finishing says to trim the selvages and press the 1/2 in backing seams open | None (PATTERN-SPEC S9 item 1 states it; gap G-2) | P3 |
| R-05 | The wide-back option is shown when it helps, and its absence is explained | Shops recommend 108 in wide backing from twin size up [S-A03, S-A26, S-A07]; two charts offer it for kings it cannot span [S-A15, S-A08] | The 108 in line appears exactly when MATH.md F11 shows one. When the pieced backing needs two or more panels and no 108 in line appears, a sentence says why | PS-12 (presence); the sentence is gap G-3 | P3 |
| R-06 | The binding is fully specified and counted once | Guides differ on extra length (+10 to +20 in), strip width (2 1/4 or 2 1/2 in) and usable width, so the count changes [S-B20, S-B34, S-A40, S-A43, S-A29]; finishers want width, count, join and corner method stated [S-D31, S-D21] | Strip width, strip count, diagonal joins, mitered corners and the extra length appear; the count equals ceil((2 (W + L) + 10) / (40 - 2 1/2)) and is the same in Fabric requirements, Cutting and Finishing | PS-11, PS-15, PS-30 | P3 |
| R-07 | The binding yardage covers its own strips | Two published figures price 11 strips of 2 1/2 in (27 1/2 in) at 3/4 yd (27 in) [S-A04, S-A40] | Binding yards x 36 in is at least strips x strip width | PS-20 | P3 |
| R-08 | Batting size and package are stated | Batting is cut to the top plus about 4 in per side [S-A24, S-A17, S-A25]; one chart pairs package names with same-named quilts and leaves no overhang [S-A23]; the overhang assumption should be stated [S-D16] | Batting = top plus the stated overhang per side, and the package named (with its dimensions) covers it, as MATH.md F12 picks | PS-13 | P3 |
| R-09 | Home-machine and longarm overhangs are both served | Longarm quilters ask for 4 to 8 in per side; home quilting needs 2 to 4 [S-A25, S-D20, S-D35, S-A17, S-A14] | The PDF states which overhang it uses and that it suits longarm quilting | PS-12, PS-13 (the overhang value only); a 2 in option waits on MATH.md Q5 (gap G-4) | P3 |
| R-10 | Finishing is complete and in sewing order | Patterns often assume the buyer knows layering, quilting and binding [S-B11]; a complete pattern covers backing, binding and quilting, not only the top [S-D15] | Finishing runs backing, layering and basting, quilting, binding | PS-29, PS-02 | P1, P3 |

### Sizes and cutting

| Id | Item | What quilters say | Check on the PDF | PS check | Persona |
| --- | --- | --- | --- | --- | --- |
| R-11 | The seam allowance is stated once and built into every cut size | Some patterns include the 1/4 in in cut sizes and some do not, a frequent source of mistakes [S-D02]; the 1/4 in seam must be accurate for anything to line up [S-D18, S-D29] | Before you begin says piecing seams are 1/4 in and every cut size includes them | PS-15 | P1 |
| R-12 | Finished, unfinished and cut sizes are kept apart | A "4 in square" without saying finished or cut makes beginners cut too small [S-D11]; an 8 in finished block measures 8 1/2 in before assembly [S-D29]; readers confuse unfinished and finished sizes [S-B13]; a pattern should state the finished quilt size [S-D03] | Page 1 gives the finished quilt size; cutting lists carry cut sizes only; checkpoints carry unfinished sizes; the terms are defined once | PS-07, PS-15, PS-25 | P1 |
| R-13 | A size checkpoint follows every unit, block and the quilt center | Wrong block size comes from seam, pressing and cutting error, fixed by checking and squaring at each stage [S-D34]; trim-to sizes are checkpoints [S-D23] | Each unit and block step ends with its unfinished size, and the quilt center has one; each equals the sum of its parts' finished sizes plus 1/2 in | PS-22, PS-25, PS-26, PS-27 | P1, P2 |
| R-14 | Cutting reads strips first, then subcuts, with nothing ambiguous | Wrong cut sizes are the most frequent printed error [S-B03]; quilters check a pattern's arithmetic before cutting [S-D03]; a beginner cut a rectangle where a square was meant [S-D22] | Each cutting step reads Cut (N) W in x WOF strips with indented subcuts giving label, count, size, per-strip yield and total; rectangles are written short side first | PS-16, PS-06 | P2 |
| R-15 | Piece labels match everywhere | Mislabeled diagrams and wrong patch placement show up on errata lists [S-D13, S-B02] | Every label defined in Cutting is used later and every label used later is defined; labels on figures match the text | PS-18, PS-36, PS-43 | P2 |
| R-16 | Piece counts add up | Errata pages correct wrong piece counts [S-B03, S-B24, S-B39] | For each label, the total cut equals pieces per unit times make counts, plus any stated spare | PS-19 | P2 |
| R-17 | Triangle units are cut oversized and trimmed, with the trim-to size | Oversizing and trimming half-square triangles is a standard accuracy method [S-D23]; a pattern was revised to cut triangle pieces large and trim [S-B28] | Each HST and QST unit gives the oversize cut and the trim-to size from MATH.md F14 | PS-23 (PATTERN-SPEC L-06) | P2 |
| R-18 | Abbreviations are defined before they are used | WOF, RST and HST overwhelm newcomers, who expect a glossary [S-D18, S-D33] | Before you begin defines every abbreviation used anywhere in the PDF | PS-15 | P1 |

### Steps and figures

| Id | Item | What quilters say | Check on the PDF | PS check | Persona |
| --- | --- | --- | --- | --- | --- |
| R-19 | One technique per unit, numbered steps, a labeled figure per step | Illustrations of how pieces fit and how seams are pressed work with the written steps, and beginners expect a labeled diagram for each step [S-D05, S-D15] | Each unit has one technique, steps numbered from 1, a figure per step on the same page, and Make N | PS-22, PS-36, PS-44 | P1 |
| R-20 | Pressing is stated or drawn, and planned so seams nest | Pressing direction and nesting confuse quilters [S-B01]; explicit pressing removes doubt when the press-to-dark rule does not apply [S-D12, S-D29] | Before you begin states the pressing plan with its reason; each unit step states or draws its pressing | PS-15, PS-22 | P1, P2 |
| R-21 | The layout shows every block's position and orientation | Common mistakes include rotating blocks wrongly and sewing a row upside down [S-D25, S-D22]; layout charts and numbered labels keep pieces in order [S-D19] | The layout chart has row and column numbers and a letter in every cell; the assembly figure shows block orientation | PS-31, PS-27 | P1 |
| R-22 | Borders are measured through the center and added sides first | Measure through the center (averaging three readings), not along the edges, or the borders wave [S-D08, S-A18]; sides first, then top and bottom [S-D28]; some quilters join border strips on the diagonal [S-A20] | Borders: sides first, then top and bottom, a measure-and-trim instruction, and the join type stated | PS-28 | P2 |
| R-23 | A coloring page is offered | Coloring pages help quilters plan fabrics [S-D19] | When enabled, the coloring page is the layout as an unfilled outline | PS-32 | P1 |
| R-24 | A fat quarter option appears where it fits | Precut bundles such as fat quarters make choosing materials easier for beginners [S-D15] | When "or N fat quarters" is printed, the to-scale diagram fits every piece | PS-21 | P1 |

### Print and format

| Id | Item | What quilters say | Check on the PDF | PS check | Persona |
| --- | --- | --- | --- | --- | --- |
| R-25 | Print at 100 percent, with a test square to measure | Fit-to-page is the most common printing mistake; quilters are told to print at 100 percent and measure the test box [S-D07, S-B21, S-B13] | A print note sits beside a test square that measures 1 in on paper at 100 percent | PS-38 | P1 |
| R-26 | The page size suits a home printer | Confirm Letter paper before printing so nothing is rescaled [S-D07] | Every page is US Letter with side margins of at least 1/2 in | PS-01, PS-38 | P1 |
| R-27 | Pages are numbered and the version is printed | Corrections pages cite the pattern, the page and the printing or revision [S-D14, S-D37] | Every footer has the name, page N of M and the QREP version | PS-03 | P2 |

### Process and honesty

| Id | Item | What quilters say | Check on the PDF | PS check | Persona |
| --- | --- | --- | --- | --- | --- |
| R-28 | The reader can find corrections or report a problem | Errata are routine for major publishers [S-D04]; quilters learn of corrections by searching or from a shop, and some never check [S-B10, S-B04]; a corrections page tells buyers whether already-cut pieces still work [S-D14] | A line names where to report a problem (PATTERN-SPEC L-12) | None (L-12 is optional; gap G-5) | P2 |
| R-29 | The pattern suggests a test block and a seam test before cutting everything | Read the whole pattern, do rough math and make a test block first [S-D03, S-D11, S-D33]; sew a seam test before assembly [S-D34] | Before you begin says to read the whole pattern first (S3 rule 1) and suggests one test block or a seam test | PS-15 covers the numbered rules, not this suggestion (gap G-6) | P1, P2 |
| R-30 | Skill level and time | Quilters use skill labels to choose a first pattern and are told to double time estimates [S-D15, S-D17]; testers judge whether both labels match their experience [S-D05] | The PDF prints neither, and the cover's build line names the method in plain words | PS-05 rules both out, PS-07 (build line). A panel finding that asks for them is recorded for Jake | P1 |

## 3. Persona weights

| Persona | Weighted items | Checks first |
| --- | --- | --- |
| P1 confident beginner | R-02, R-10, R-11, R-12, R-13, R-18 to R-21, R-23 to R-26, R-29, R-30 | Fabric requirements, then the first cutting step |
| P2 experienced traditional piecer | R-02, R-13 to R-17, R-20, R-22, R-27 to R-29 | Cut sizes against finished sizes, then piece counts against the layout |
| P3 finisher | R-01, R-03 to R-10 | The backing, binding and batting lines, then Finishing |

## 4. Gaps for the A4 and A5 owners

Quilter concerns that no PS check covers. Each is a proposal for the owners and for Jake (an
acceptance check changes only with his approval, plan section 3.3), not a defect in a PDF.

- **G-1 (A4; R-01).** No check names the overhang per side, although PATTERN-SPEC S3 rule 6 prints
  it and finishers check it first. Proposal: PS-14 or PS-15 also checks the overhang value.
- **G-2 (A4; R-04).** No check names trimming selvages, pressing backing seams open or squaring the
  backing, all of which PATTERN-SPEC S9 item 1 states and longarm quilters ask for.
- **G-3 (A4; R-05).** When the pieced backing needs two or more panels and no 108 in line appears
  (the 110 x 108 king, V-WIDE-05), the PDF says nothing. Finishers have seen charts offer 108 in
  backing for such kings, so one sentence (no backing dimension fits within 108 in) prevents a
  wrong purchase.
- **G-4 (A4; R-09).** The PDF prints one overhang. Home-machine quilters need 2 to 4 in per side;
  whether to print the domestic option is MATH.md Q5.
- **G-5 (A4; R-28).** The problem-report line (L-12) is optional and unchecked. Quilters treat a
  corrections channel as part of a trustworthy pattern.
- **G-6 (A4; R-29).** No rule suggests a test block or a seam test before cutting everything.
- **G-7 (A4).** Calculators warn that they ignore directional prints [S-B18, S-B15]; the backing
  layout that uses less fabric can turn a directional print sideways (MATH.md Q10). No sentence
  tells the reader the backing layout assumes a print with no direction.
- **G-8 (A4).** Quilters add fabric for prewashing and shrinkage [S-A16, S-B06, S-A25]; MATH.md
  includes no shrinkage beyond its allowances. No sentence tells the reader whether to prewash or
  that the amounts include no shrinkage allowance.
- **G-9 (A4).** Quilters trust patterns that were tested and technically edited [S-D05]. QREP's PDF
  has no human tester, so no check is proposed; the owners should make sure no page claims testing
  that did not happen.

No item needs a new figure check, so A5 has no gap of its own; R-03, R-06, R-13, R-15 and R-21 lean
on A5's figures through PS-36, PS-43 and PS-44.
