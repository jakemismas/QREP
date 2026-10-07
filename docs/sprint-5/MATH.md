# QREP sprint 5: pattern math

Status: binding once the sprint-5 plan PR (issue #107) merges. Written 2026-10-07 against main at
834d8be; every file:line reference in this file is at that commit. The plan
([qrep-sprint-5-plan.md](qrep-sprint-5-plan.md), section 0) makes this file and
[PATTERN-SPEC.md](PATTERN-SPEC.md) the only homes for pattern numbers, so tickets cite the ids
here (F formulas, D defects, V vectors, Q questions) and never restate a value.

## Rules

1. Implement the formulas in section 2 and test them against the vectors in section 4. Why: each
   formula here is sourced and backed by hand-computed vectors, and math that is not here is out
   of scope (CLAUDE.md).
2. Write the tests before the code, with the vector id and its steps in a comment. Why: expected
   values flow one way, from hand computation to assertion (CLAUDE.md), and A1 and A2 write their
   tests from these vectors first.
3. Never take an expected value from running QREP or from a calculator. Calculator values
   (section 5) are recorded cross-checks, and a disagreement is investigated against the hand
   arithmetic. Why: the fix needs a source of truth that is not another tool's output.
4. Compute in integer eighths with integer ceil and floor, never with a decimal factor such as 1.1
   (section 1.2). Why: floating point can round a margin up one eighth too far (V-UNIT-02).
5. When Jake answers a section 6 question against its default, change the affected vectors here
   first, with new hand-worked steps, and only then the tests. Why: tests take expected values
   only from this file.
6. Identify quilts by plain size only, name no commercial pattern and reproduce no cutting chart;
   compare with the private reference patterns only in aggregate (section 5.3). Why: this
   repository is public and those patterns are copyrighted.

## Tickets that use this file

| Ticket | What it takes from this file |
| --- | --- |
| A1 Finishing math | Binding, backing, wide-back and batting: F6 to F12, with V-UNIT-01, V-UNIT-03 and V-UNIT-06 and the vectors in sections 4.3 to 4.7 |
| A2 Cutting yields and yardage | Cut sizes, strip yields, strip sets, borders and top-fabric purchase lines: F1 to F5 and the F14 yield rule, with V-UNIT-01, V-UNIT-02, V-UNIT-04 and V-UNIT-05, the vectors in section 4.2, and V-TRI-08 and V-TRI-09 |
| A3 Construction method, A4 Pattern document | Unit cut sizes from F14 (V-TRI-01 to V-TRI-07), the display rules in F13 and the assumption sentences in section 1.5; PATTERN-SPEC decides how each is used |
| D2 Calculator baseline, D7 Calculator re-run | The calculators, how to drive them and the size matrix in section 5.2, and the recorded values in section 5.1. D2 measures today's math; D7 re-runs after A1, A2 and A4 merge |
| D1 Quilter-voice research | Cross-checks the section 4 values against the numbers quilters expect for standard sizes, and stands in for the reported case (Q1) until Jake has it |
| A6 Consolidated bless | The fixture regeneration at U = 40 and B = 42 (section 1.3), and the fixture pins and goldens that move with it (section 3.2) |

## Inputs and changes from the planning audit

Inputs: the sprint-5 math audit and calculator research (private planning inputs; the public
sources they rely on are cited where used, with URLs), Jake's decisions J7, J9, J13 and J16 in the
plan (section 3.1), and the code at 834d8be. Section 7 says how the numbers were verified.

Changes from the audit's recommendations:
1. Backing uses its own width setting, B = 42 in (Jake's decision J13). The audit computed
   backing at 40 in. Every backing vector is recomputed at 42 in. The audit's 40 in results that
   differ at 42 in stay as configured-width vectors (V-BACK-18 to V-BACK-20); its 42 x 52, 28 x 28,
   68 x 68 and 76 x 85 results come out the same at 42 in.
2. Border strips: two pieces short enough to share one strip now share it. The audit's rule gave
   every piece its own strip, which over-buys on small quilts. The audit's cut list also joined
   all of a band's strips before cutting the four pieces; a per-piece count needs per-piece
   wording (F4, Q6). Every audit border vector is unchanged.
3. Backing orientation is chosen on the purchase total including its allowance, not on the raw
   length. This keeps a one-piece backing when it is cheaper (V-BACK-14).
4. The audit named commercial patterns and quoted their cut lists. This file does neither
   (rule 6).
5. Triangle and stitch-and-flip unit cut sizes (F14) are new. The audit did not cover them; they
   come from the published tutorials cited in F14, read on 2026-10-07.

## 1. Scope and conventions

### 1.1 Scope

This file covers per-strip cutting yields, strip sets, borders, quilt-top fabric yardage, binding,
pieced and wide backing, batting, rounding, and the assumption sentences the pattern prints.

It also gives cut sizes and yields for the triangle and stitch-and-flip units in 0.4.0 scope
(F14). It does not cover the following: the choice of technique per unit type and mirror
warnings (PATTERN-SPEC; Q9), fat quarter recipes, directional prints (Q10), borders cut on the
lengthwise grain and mitered borders (F4), bias binding, and prewash shrinkage beyond the stated
allowances.

### 1.2 Units and arithmetic

- All lengths are integer eighths of an inch, as today (`qrep/model/units.py:3-5`):
  1 in = 8, 1/4 in = 2, 1 yd = 288, 1/4 yd = 72, 1/8 yd = 36. Section 4 writes eighths with an
  `e` suffix.
- The math uses integers only. For positive integers, ceil(a / b) is `(a + b - 1) // b`. A percent
  margin is ceil(e x (100 + p) / 100). Never use a decimal factor such as 1.1: in binary floating
  point ceil(200 x 1.1) evaluates to 221, while the integer form gives 220.
- W is the finished quilt width (side to side) and L the finished length (top to bottom). Both
  include borders and exclude binding.
- Vertical seams run top to bottom: the backing panels sit side by side and each panel is
  Lb = L + 2o long. Horizontal seams run side to side: the panels are stacked and each panel is
  Wb = W + 2o long (F8).

### 1.3 Settings the formulas read

| Symbol | Meaning | Default | Code today |
| --- | --- | --- | --- |
| a | Seam allowance | 1/4 in (2 e). Cut = finished + 1/2 in | `Settings.seam_allowance`, `qrep/model/schema.py:134` |
| U | Usable width for strip cutting (WOF) | 40 in (320 e) | `Settings.wof`, default 336 e (42 in) at `schema.py:135`; A2b changes the default to 320, and the fixture keeps 336 until A6 (migration note below) |
| B | Backing fabric width, selvages trimmed | 42 in (336 e) | New setting (A1). Backing reads `Settings.wof` today |
| BW | Wide-back width | 108 in (864 e); 118 in is the other common width | New setting (A1) |
| 2o | Backing and batting overhang per axis (o per side) | 8 in (64 e), so o = 4 in. Domestic option: 2 in per side (32 e per axis) | `Settings.backing_margin`, `schema.py:138` |
| s | Backing seam loss | 1 in (8 e) per seam: a 1/2 in seam allowance on each panel | New constant (A1) |
| w | Binding cut strip width | 2 1/2 in (20 e) | `Binding.strip_width`, `schema.py:111`, the only source. `Settings.binding_strip_width` (`schema.py:136`) is never read; A7 removes it (D-09) |
| t | Binding extra length | 10 in (80 e) | `Settings.binding_extra`, `schema.py:137` |
| j | Straight-join loss for border strips | 1/2 in (4 e) per join | New constant (A2) |
| p | Quilt-top margin | 10 percent | New setting (A2) |
| Mp | Pieced-backing allowance | 9 in (72 e), which is 1/4 yd | New setting (A1) |
| M1 | One-piece backing allowance (one panel, or wide-back) | 4 1/2 in (36 e), which is 1/8 yd | New setting (A1) |
| r | Purchase increment | 1/4 yd (72 e) | `QUARTER_YARD`, `qrep/construct/yardage.py:14` |

Migration note: the committed fixture file stores its settings explicitly with `"wof": 336`
(`tests/fixtures/double_irish_chain.json`; `web/scripts/vendor.mjs:91-95` copies it to
`web/public/fixtures/`, which `web/.gitignore:29` keeps out of git), and
`tests/test_fixture.py:16-20` compares that file with the model that `make_double_irish_chain()`
builds, whose settings come from the `Settings` defaults (`qrep/model/schema.py:178`). Changing
the default does not move a stored file to 40 in, and the fixture keeps its stored 42 in until A6
(plan section 5.A, rule 3; [REBASELINE.md](REBASELINE.md), [bless] policy item 4). Why: the
cut-list goldens are generated from the fixture, and only A6 may change goldens.

- When A2b moves the `wof` default to 320, it pins `make_double_irish_chain()` to an explicit
  `wof` of 336.
- A1, A2b and A9 regenerate the file with no value change when they add their model fields. Plan
  section 5.A, rule 3 and [bless] policy item 4 name the other tickets that regenerate it.
- Until A6, the fixture's existing pins keep their 42 in values: binding V-BIND-09 (9 strips,
  180 e) and 21 segments per set (25 sets). Its backing moves to V-BACK-09 in A1, because backing
  reads B, which the fixture takes at its 42 in default.
- A6 regenerates the fixture at the new defaults (U = 40, B = 42) and moves those pins to the
  fixture's U = 40 vectors, such as V-SET-01, V-BIND-01 and V-BORD-01 (section 3.2).
- Vector tests set their widths explicitly (plan, A1), so A1 tests V-BIND-01 at U = 40 on night 1
  while the fixture's pin stays at V-BIND-09.

Saved user projects that store `wof: 336` also keep it, unless Jake decides they move to 40 in on
load (section 6, Q7).

### 1.4 Rounding and allowances

- Every purchase line rounds up, line by line, to the next 1/4 yd:
  qy = ceil(purchase_length / 72 e).
- Allowances by line type, added before rounding:
  - Quilt-top fabrics, including their border strips and strip-set strips: +10 percent of the
    strip-plan length.
  - Binding: nothing beyond the 10 in extra length and the join-aware strip count.
  - Pieced backing (two or more panels): +9 in (1/4 yd).
  - One-piece backing (one panel, or the wide-back line): +4 1/2 in (1/8 yd).
  - Batting: sold by package, so there is no rounded yardage line. A roll length may appear only
    with its roll width printed beside it (F12).
- Each line reports `length_needed` (the plan length before any allowance, in eighths) and the
  purchase in increments. Tests assert both.
- The 1/4 yd increment and both backing allowances are open decisions (section 6, Q2 and Q3).
  Section 4.4 precomputes the backing alternatives. A 1/8 yd increment also changes every other
  purchase line (top fabrics, binding, wide-back). Those are not precomputed, but each is
  ceil(purchase / 36 e) eighths of a yard from a purchase length that section 4 already gives.

### 1.5 Assumptions as the pattern states them

The PDF prints these in its "Before you begin" block and in the requirements footnote. The wording
is QREP's own. Every number comes from the settings, so a changed setting changes the sentence;
none is hard-coded.

1. All piecing seams are 1/4 in, and every cut size includes them.
2. WOF means width of fabric. Cutting yields assume 40 in of usable width per strip, a safe
   planning figure. Wider fabric leaves extra.
3. Fabric amounts are rounded up to the next 1/4 yd. Quilt-top fabrics include 10 percent extra
   for straightening edges and the occasional miscut.
4. Binding: (N) 2 1/2 in x WOF strips joined with diagonal seams. The length includes 10 in for the
   corners and the final join.
5. Backing extends 4 in beyond the quilt on every side. It assumes 42 in wide fabric with the
   selvages trimmed, joined with 1/2 in seams pressed open, plus 1/4 yd (1/8 yd for a one-piece
   backing) for squaring the ends. The layout shown uses the least fabric.
6. Wide backing: one piece of 108 in wide fabric, with no seams. (Printed only with the
   wide-back line, which F11 shows only when the pieced backing needs two or more panels and one
   backing dimension fits within the wide width.)
7. Batting is the size of the backing: the quilt plus 4 in on every side.
8. Borders are cut across the WOF. A border longer than one strip is made from strips joined end to
   end with straight 1/4 in seams.

## 2. Formulas

Each formula gives a plain statement, the formula, its edge cases, and its sources. Source URLs were
recorded during the sprint-5 calculator research, and the live calculators were re-checked on
2026-10-07 (section 5.2).

### F1. Cut size

- Statement: a square or rectangle is cut 1/2 in larger than its finished size in each direction.
- Formula: cut = finished + 2a = finished + 4 e.
- Edge cases: triangle and stitch-and-flip units use other additions (F14).
- Source: the standard 1/4 in seam convention. The code already does this at
  `schema.py:140-143`.

### F2. Strip yield for one cut line

- Statement: a cut line of q pieces, cut d1 x d2, comes from WOF strips U long. The strip width is
  one side of the piece, and the other side is cut off repeatedly along the strip. Try both
  orientations and keep the one that uses less fabric. (d1 and d2 are the two cut sides; the symbol
  a stays the seam allowance of section 1.3.)
- Formula:
  - Orientation 1 (strip width d1, subcut d2), valid when d2 <= U:
    per1 = floor(U / d2), strips1 = ceil(q / per1), len1 = strips1 x d1.
  - Orientation 2 (strip width d2, subcut d1), valid when d1 <= U:
    per2 = floor(U / d1), strips2 = ceil(q / per2), len2 = strips2 x d2.
  - Keep the smaller length. On a tie, keep the narrower strip, so the first printed number is the
    strip width (short side first).
  - Pieces from the last strip = q - (strips - 1) x per. The cutting section prints it when the
    last strip is partly used.
  - A square has one orientation.
- Edge cases:
  - Lines are not pooled. Each cut line gets its own strips, and leftover strip ends are not
    credited to another line. This is conservative and matches how a pattern prints one strip count
    per subcut.
  - The best orientation can flip when U changes (V-YIELD-02).
  - A piece whose longer side d2 exceeds U: the one-method scope should never produce one, because
    merged runs are capped at U (Q8). If one reaches this code anyway, cut it like a border piece:
    k = ceil((d2 - j) / (U - j)) strips of width d1 joined per piece, so strips = q x k (V-YIELD-03).
    The joined cut takes the place of orientation 1, which is invalid when d2 > U. Orientation 2
    (strips d2 wide, so each piece's long side runs along the lengthwise grain) stays valid when
    d1 <= U and still competes; the smaller length wins. For 2 1/2 x 60 1/2 in pieces at U = 40 the
    joined cut (5q in) wins for q <= 12 and one 60 1/2 in strip wins for q = 13 to 16, but the lead
    then alternates (joined again for q = 17 to 24 and 33 to 36; 60 1/2 in strips for q = 25 to 32
    and from q = 37 on), so compare both lengths for every q and never code a fixed threshold.
  - A piece longer than U in both directions cannot come from WOF strips. Raise an error.
- Sources: Quilter's Paradise piece count and pieces-to-yardage calculators (both orientations,
  floor(width / piece), https://www.quiltersparadiseesc.com/Calculators/Piece%20Count%20Calculator.php);
  Linda's Electric Quilters yardage guide (40 in usable; 40 / 5 = 8 pieces across,
  https://lindas.com/blogs/education/how-to-calculate-fabric-yardage). No surveyed calculator uses
  an area estimate.

### F3. Strip sets

- Statement: a strip set is one WOF strip of each fabric in its sequence, sewn lengthwise and
  crosscut into segments.
- Formula: per_set = floor(U / segment_cut_width); sets = ceil(segments_needed / per_set). Each
  fabric uses sets x (its count in the sequence) strips of strip_cut_width.
- Edge cases: when a row signature and its reverse share one set (a PATTERN-SPEC choice), only
  segments_needed changes; the formula does not.
- Sources: Linda's per-strip yield and the Quilter's Paradise piece count (URLs above). This
  replaces `wof // segment_width` at `qrep/construct/strategies.py:376`.

### F4. Borders

- Statement: each border band adds two side pieces, sewn first, then a top piece and a bottom piece.
  Pieces come from crosswise strips b + 1/2 in wide. A piece longer than one strip is made from
  strips joined end to end with straight 1/4 in seams. Two pieces that fit in one strip share it.
- Formula, for band i with finished width b and inner size Wi x Li (the center plus earlier bands):
  - Cut strip width = b + 1/2 in.
  - Side length Ls = Li + 1/2 in (2 pieces). Top and bottom length Lt = Wi + 2b + 1/2 in (2 pieces).
  - Strips for a pair of identical pieces of length Lp:
    - if Lp <= U: per = floor(U / Lp), strips = ceil(2 / per). That is 1 strip when 2 Lp <= U,
      otherwise 2.
    - if Lp > U: k = ceil((Lp - j) / (U - j)) strips per piece, so strips = 2k.
  - Band strips = strips(Ls) + strips(Lt). Band length = band strips x (b + 1/2 in).
  - The band length joins the border fabric's top line (F5) before the margin.
  - The cut list prints, per band: Cut (N) strips (b + 1/2 in) x WOF. For each side border, join
    k strips end to end and trim to Ls; do the same for the top and bottom borders at Lt. A piece
    with Lp <= U needs no join: cut it from one strip, and cut both pieces of the pair from one
    strip when 2 Lp <= U (the 1-strip case above, V-BORD-04).
- Edge cases:
  - Join thresholds at U = 40: one strip up to 40 in, two up to 79 1/2 in (2 x 40 - 1/2), three up
    to 119 in (3 x 40 - 1).
  - Do not pair these counts with "join all the strips, then cut four borders". Pooling every strip
    into one long strip adds joins and can come up short by up to 1 1/2 in when every piece has
    zero slack. Pooled counting is a valid alternative only with its own count (Q6).
  - The inner size grows by 2b with each band.
  - Only identical pieces share a strip, so V-BORD-04 buys 2 strips although all four of its
    pieces (22 in) fit in one.
  - Lengthwise-grain and mitered borders are out of scope.
- Sources: Quilter's Paradise border calculator (strips cut b + 1/2 in, 1/2 in lost per straight
  join, https://www.quiltersparadiseesc.com/Calculators/Border%20Calculator.php); GE Designs
  (measure through the center, 40 in usable; it adds 1 in to each length and sews the top and
  bottom first, https://gequiltdesigns.com/blogs/the-quilters-toolkit/all-about-quilt-borders).
  Quilter's Paradise pools all strips; per-piece counting is QREP's choice because it is never
  short. The +1/2 in lengths and the sides-first order match the code today
  (`strategies.py:86-126`) and one reference's printed cut lengths (section 5.3).

### F5. Quilt-top fabric length and purchase

- Statement: a fabric's length is the sum of its strip plans. The purchase adds 10 percent and
  rounds up to 1/4 yd. It is never an area estimate.
- Formula: length_needed = the sum of F2 lengths over the fabric's cut lines + its F4 band lengths
  + its F3 strip-set strips x strip width. purchase = ceil(length_needed x 110 / 100);
  qy = ceil(purchase / 72).
- Edge cases:
  - Binding stays a separate line even when the binding fabric is also in the top, as today
    (`yardage.py:86-92`).
  - A fabric used only in borders gets the margin too.
  - When length_needed is an exact multiple of 9 in, a purchase without margin leaves 0 in to spare
    (V-TOP-01). The margin prevents that.
- Sources: Linda's yardage guide (+10 percent; always round up; URL above); Quilter's Paradise
  pieces-to-yardage (URL above). The margin value is Q4.

### F6. Binding length

- Statement: the binding goes around the quilt, plus 10 in for the corners and the final join.
- Formula: T = 2 (W + L) + t, with t = 10 in.
- Edge cases: t is configurable. Sources range from +10 to +20 in.
- Sources: Quilter's Paradise binding calculator (+10,
  https://www.quiltersparadiseesc.com/Calculators/Binding%20Calculator.php); QuiltSocial (+10,
  https://quiltsocial.com/the-formula-for-calculating-the-necessary-yardage-for-binding-your-quilt/);
  Nebraska Quilt Company no-stress guide (+10 to 12,
  https://www.nebraskaquiltcompany.com/blogs/welcome-to-nqc/the-no-stress-quilt-math-guide-how-to-use-our-backing-amp-binding-calculator);
  Missouri Star Quilt Co. (MSQC) binding blog (+20,
  https://www.missouriquiltco.com/blogs/missouri-star-blog/how-to-figure-yardage-for-quilt-binding).

### F7. Binding strips and yardage (join-aware)

- Statement: binding strips are cut across the WOF and joined with diagonal seams. Each diagonal
  join, including the one that closes the binding on the quilt, uses one strip width of length.
- Why one strip width per join: the end of strip A overlaps the end of strip B in a w x w square,
  and the seam runs corner to corner across that square. Along the strip's center line the seam
  sits w/2 from each strip's end, so the joined strip is LA + LB - w long. A loop of n strips has n
  joins (n - 1 to make the strip and 1 to close it), so it supplies n x (U - w).
- Formula: strips = ceil(T / (U - w)); length_needed = strips x w; purchase = length_needed;
  qy = ceil(length_needed / 72). Loop check: strips x (U - w) >= T.
- Edge cases: w changes the yardage and can change the count (V-BIND-08: the fixture keeps 10
  strips at 2 1/4 in, while 94 x 108 drops from 12 to 11). One shared helper replaces the
  three copies at `strategies.py:133`, `strategies.py:243` and `qrep/export/pdf.py:211`.
  The closing join is budgeted twice on purpose: t names the final join (F6), and the loop
  count takes w for it again. That adds at most one strip, because w < U - w, and it matches
  Quilter's Paradise, which uses the same T and the same divisor. Binding has no margin by design,
  so a line can have 0 in to spare: king 110 x 108 at w = 2 1/4 in (12 strips) buys exactly
  27 in = 3/4 yd.
- Sources: Quilter's Paradise binding calculator (strips = ceil(T / (fabric width - strip width)),
  URL above). Strip width 2 1/2 in: MSQC, QuiltSocial and Nebraska; 2 1/4 in: National Quilters
  Circle (https://nationalquilterscircle.com/post/how-to-calculate-binding).

### F8. Backing size

- Statement: the backing extends o beyond the quilt on every side.
- Formula: Wb = W + 2o; Lb = L + 2o. The default 2o is 8 in.
- Edge cases: the domestic option uses o = 2 in (V-BACK-21, V-BACK-22).
- Sources, 4 in per side unless noted: MSQC backing blog
  (https://www.missouriquiltco.com/blogs/missouri-star-blog/how-to-figure-yardage-for-quilt-backing);
  Quilted Joy (https://quiltedjoy.com/blogs/blog/how-much-backing-fabric-do-i-need); My Favorite
  Quilt Store (4 in longarm, 2 in domestic, https://myfavoritequiltstore.com/toolbox/backing-calculator);
  Nebraska Quilt Company February 2026 guide (+8 in per dimension longarm, +4 in domestic,
  https://www.nebraskaquiltcompany.com/blogs/welcome-to-nqc/the-no-stress-quilt-math-guide-how-to-use-our-backing-amp-binding-calculator);
  Stitched in Color (4 to 5 in per side,
  https://www.stitchedincolor.com/blog/2018/1/25/how-to-enlarge-a-backing-for-longarm-quilting);
  The Crafty Quilter (3 to 4 in longarm, 2 to 3 in domestic,
  https://thecraftyquilter.com/2025/05/how-to-determine-quilt-batting-and-backing-size/). Nebraska
  Quilt Company's longarm guide asks for 5 in per side. That is not the top of the range: Linda's
  backing guide asks for 12 in more than the top in each direction for longarm quilting (6 in per
  side), and Linda's 108 in guide says some longarm frames need 6 to 8 in per side (URLs in section
  5.2 and F11). The 4 in default is the consensus figure, not the largest request.

### F9. Backing panel count (seam-aware)

- Statement: n panels of width B joined with 1/2 in seams cover n x B - (n - 1) in.
- Formula: n(D) = 1 if D <= B, otherwise ceil((D - s) / (B - s)) with s = 1 in.
- Thresholds: at B = 42, 1 panel covers up to 42 in, 2 up to 83 in, 3 up to 124 in and 4 up to
  165 in. At B = 40 the limits are 40, 79, 118 and 157 in.
- Edge cases: a backing dimension wider than two seamed widths needs three panels (from 83 1/8 in
  to 124 in at B = 42; V-BACK-08, and V-BACK-10 at 84 in, 1 in past the two-panel limit).
  Requested sizes clamp to 20 to 140 in (160 to 1120 e, `qrep/bridge.py:413-416`, mirrored at
  `web/src/model/sizing.ts:22-23`); 140 in gives 148 in and four panels (V-BACK-15). That is not
  a ceiling: a cell-size resize is clamped only by the 4 in cell limit (`qrep/bridge.py:471`), so
  a finished side can pass 140 in and n(D) must have no upper limit.
- Sources: Quilter's Paradise backing calculator (1 in per seam,
  https://www.quiltersparadiseesc.com/Calculators/Backing%20and%20Batting%20Calculator.php);
  Nebraska Quilt Company longarm guide (1/2 in backing seams pressed open,
  https://www.nebraskaquiltcompany.com/blogs/welcome-to-nqc/how-to-calculate-longarm-backing-fabric-6-step-guide-2026).

### F10. Backing orientation and purchase

- Statement: compute both layouts and buy the one with the smaller total.
- Formula:
  - Vertical seams: nv = n(Wb) panels, each Lb long; length_v = nv x Lb.
  - Horizontal seams: nh = n(Lb) panels, each Wb long; length_h = nh x Wb.
  - allowance(n) = 9 in when n >= 2, else 4 1/2 in.
  - total_v = length_v + allowance(nv); total_h = length_h + allowance(nh).
  - Keep the smaller total; on a tie keep vertical seams. length_needed is the kept raw length,
    purchase is the kept total, and qy = ceil(total / 72).
  - The pattern prints the yards, the panel count, the panel cut length and the seam direction.
- Edge cases:
  - Comparing totals, not raw lengths, keeps a one-piece backing when it costs less (V-BACK-14).
  - Zero slack is acceptable: n x B - (n - 1) = D exactly leaves exactly the 4 in overhang
    (V-BACK-09).
  - That zero slack holds only for panels sewn side by side. A backing that splits one panel to
    avoid a center seam adds a seam and covers 1 in less (82 in from two 42 in widths).
  - Directional backing prints are out of scope. The cheaper layout may turn a directional print
    sideways (Q10).
  - B is configurable. Setting it to 40 in brings back the over-estimate on some sizes (V-BACK-18),
    which is why backing does not share the strip-cutting width.
- Sources: C&T Publishing (both orientations, +9 in pieced, +4 1/2 in unpieced,
  https://ctpub.com/blogs/blog-c-t-publishing/quilting-tips-calculating-yardage-for-quilt-backing);
  Quilter's Paradise and My Favorite Quilt Store (least-fabric direction, URLs above); MSQC
  (turning the backing saves fabric; 1/4 yd rounding, URL above); Nebraska Quilt Company longarm
  guide (+1/4 yd for shrinkage and trimming, URL above).

### F11. Wide-back alternative

- Statement: when one backing dimension fits within the wide-back width, the backing can be one
  piece of wide fabric.
- Formula: if Wb <= BW and Lb <= BW, length = min(Wb, Lb); else if Wb <= BW, length = Lb; else if
  Lb <= BW, length = Wb; else there is no wide-back line. purchase = length + 4 1/2 in;
  qy = ceil(purchase / 72).
- Shown only when the pieced layout (F10) needs two or more panels. When it is not shown, the line
  is omitted, not printed as zero.
- Edge cases: there is no 108 in line for a quilt whose backing is wider than 108 in both ways (the
  110 x 108 king, V-WIDE-05). The 118 in width is configurable. Two wide panels are out of scope.
  Whether all 108 in of wide goods is usable after the selvages was not verified; the formula
  assumes it is.
- Sources: MSQC (wide backs from twin size up, URL above); Quilted Joy chart (URL above); Linda's
  108 in guide (https://lindas.com/blogs/tips-and-tricks/108-inch-wide-fabric-for-quilt-backing);
  Nebraska Quilt Company (108 and 118 in widths,
  https://www.nebraskaquiltcompany.com/blogs/welcome-to-nqc/the-no-stress-quilt-math-guide-how-to-use-our-backing-amp-binding-calculator).

### F12. Batting

- Statement: batting is the backing's size. The pattern names the smallest standard package that
  covers it.
- Formula: size = (W + 2o) x (L + 2o), with the same o as the backing (one source; drop the
  separate constant at `pdf.py:39`). The package is the first of crib 45 x 60, twin 72 x 90, full
  90 x 96, queen 90 x 108 and king 124 x 120 that covers the size in either orientation. If none
  does, print "larger than a king package (124 x 120 in)".
- Print the size and the package class with its dimensions. Do not print a brand. Do not print roll
  yardage unless the roll width is stated with it.
- Sources: The Crafty Quilter and Quilted Joy (URLs above); Linda's Warm and Natural package guide,
  which supplies the package sizes
  (https://lindas.com/blogs/product-guides/warm-natural-needled-cotton-batting-package-guide).
  Package sizes vary by brand; only these were verified.

### F13. Display

- Inches as mixed fractions in eighths (`format_inches`), never decimals.
- Yards as mixed fractions of the purchase increment (`format_yards`).
- Counts in parentheses: Cut (10) 2 1/2 in x WOF strips.

### F14. Triangle and stitch-and-flip units

These are new in 0.4.0 scope (Jake's decision J9) and were not in the audit. The cut sizes below
come from the published tutorials cited in the table, read on 2026-10-07. PATTERN-SPEC picks one
technique per unit type and owns the steps, checkpoints and mirror warnings; this section owns the
numbers. F is the finished unit size from the read's unit map (for a one-cell unit, F is the cell
size). All additions are whole eighths, so the integer-eighths rule holds.

| Unit and technique | Cut pieces | Units per set | Trim to | Source |
| --- | --- | --- | --- | --- |
| Half-square triangle, two at a time, exact | 1 square of each fabric at F + 7/8 in (F + 7 e) | 2 | none | USU Extension (https://extension.usu.edu/sewing/research/half-square-triangles-broken-dishes-block-pinwheel-block); National Quilters Circle (https://nationalquilterscircle.com/post/the-half-square-triangle-a-versatile-quilt-block); Quilting Daily (https://www.quiltingdaily.com/how-to-make-half-square-triangles-hst-from-squares) |
| Half-square triangle, two at a time, oversize and trim | 1 square of each fabric at F + 1 in (F + 8 e) | 2 | F + 1/2 in | QuiltSocial (2 1/2 in squares trimmed to 2 in units, https://quiltsocial.com/trimming-makes-accurate-half-square-triangle-units/amp/) |
| Half-square triangle, eight at a time | 1 square of each fabric at 2 x (F + 7/8 in) (2F + 14 e) | 8 | none | National Quilters Circle (URL above; its example: 3 in finished from 7 3/4 in squares) |
| Quarter-square triangle (two-fabric hourglass), exact | 1 square of each fabric at F + 1 1/4 in (F + 10 e) | 2 | none | Linda's QST tutorial (https://lindas.com/blogs/tips-and-tricks/quarter-square-triangle-tutorial); OLFA (https://olfa.com/blogs/craft/how-to-make-and-trim-quarter-square-triangles) |
| Quarter-square triangle (two-fabric hourglass), oversize and trim | 1 square of each fabric at F + 1 1/2 in (F + 12 e) | 2 | F + 1/2 in | Same two sources |
| Flying geese H x 2H (finished H tall and 2H wide), stitch and flip, one at a time | 1 goose rectangle (H + 1/2) x (2H + 1/2); 2 sky squares H + 1/2 | 1 | none | The Crafty Quilter chart (2 x 4 finished from a 2 1/2 x 4 1/2 rectangle and two 2 1/2 in squares, https://thecraftyquilter.com/?p=1279) |
| Flying geese H x 2H, four at a time (no waste) | 1 goose square 2H + 1 1/4 in; 4 sky squares H + 7/8 in | 4 | none | Connie Kresin (2 x 4 finished from one 5 1/4 in and four 2 7/8 in squares, https://conniekresin.com/flying-geese-four-at-a-time/) |
| Stitch-and-flip corner (snowball) on a base of finished size F with corner leg c | 1 base square F + 1/2 in; 1 corner square c + 1/2 in per corner | 1 | none | OLFA (https://olfa.com/blogs/craft/how-to-make-snowball-corners; its examples use c = F / 3) |

- Yield into yardage: each technique turns a unit count into cut lines, which then go through F2.
  For a two-at-a-time unit, squares per fabric = ceil(units / 2); for eight at a time,
  ceil(units / 8); for four-at-a-time geese, goose squares = ceil(geese / 4) and sky squares
  = 4 x goose squares; for one-at-a-time geese, one rectangle and two squares per goose.
- Edge cases: an odd unit count leaves spare units (V-TRI-09). Hourglass units from three or four
  fabrics pair squares differently; their counts and mirror behavior are not covered here.
  Stitch-and-flip trims off triangles; the trimmed fabric is waste and is already inside the cut
  sizes above.

## 3. Current QREP behavior and defects

All file:line references are at 834d8be. "Today" values below come from hand arithmetic on the
current formulas, not from running QREP.

### 3.1 Defects

| ID | Where | What it does | Defect and example |
| --- | --- | --- | --- |
| D-01 | `qrep/construct/yardage.py:36-47` (formula at :39-40) | panels = ceil((W + 8) / wof); length = panels x (L + 8). Vertical seams only | Over on wide or long quilts. The 92 1/2 x 115 queen gets 3 x 123 = 369 in = 10 1/4 yd; the cheaper horizontal layout is 301 1/2 in, or 8 3/4 yd with the allowance (V-BACK-01). The 90 x 108 queen gets 9 3/4 yd instead of 8 1/2 (V-BACK-07) |
| D-02 | `yardage.py:39` | The panel count ignores seam allowance | Under. A 76 x 85 quilt gets 2 panels (186 in, 5 1/4 yd), but two 42 in panels give 83 in after a 1/2 in seam against the 84 in needed (V-BACK-10: 3 panels, 7 1/4 yd). The 75 x 90 fixture has 0 in to spare |
| D-03 | `yardage.py:46` | Rounds the raw length up to 1/4 yd with no allowance | The fixture needs 196 in and buys 198 in, leaving 2 in to square two panel ends. A 28 x 28 quilt needs 36 in and buys 36 in |
| D-04 | `yardage.py:3`, `:16`; `qrep/export/pdf.py:241-242` | Hard-codes "42-inch" in the backing name and PDF text | A quilt whose `settings.wof` changes still prints 42-inch |
| D-05 | `qrep/model/schema.py:135` | One width (`wof`, 42 in) serves strip cutting and backing | Strip yields assume 2 in more than the 40 in consensus (21 instead of 20 two-inch segments). Backing needs its own 42 in setting (V-BACK-18) |
| D-06 | `yardage.py:36-47`; `pdf.py:241-242` | No wide-back alternative | The 90 x 108 queen: 9 3/4 yd pieced today, against 3 1/2 yd of 108 in (V-WIDE-04) |
| D-07 | `web/src/shell/PatternPanel.tsx:294` | Labels the pieced 42 in backing line "wide backing fabric, seamed to fit" | A reader may buy 9 3/4 yd of 108 in fabric for the 90 x 108 queen, which needs 3 1/2 yd |
| D-08 | `qrep/construct/strategies.py:133` (copies at `:243` and `pdf.py:211`) | strips = ceil((perimeter + 10) / wof); ignores the strip width each diagonal join uses | Under. The 90 x 108 queen gets 10 strips, which joined give 10 x (42 - 2 1/2) = 395 in, less than its 396 in perimeter (V-BIND-16 needs 11). Also short of the bare perimeter: twin 70 x 90 (316 vs 320 in), king 110 x 108 (434 1/2 vs 436), 76 x 85 (316 vs 322), 53 1/2 x 67 (237 vs 241) |
| D-09 | `schema.py:136` | `Settings.binding_strip_width` is never read; `Binding.strip_width` (`schema.py:111`, used at `strategies.py:134`) drives the math | Setting 2 1/4 in in Settings changes nothing |
| D-10 | `yardage.py:50-58` (:51) and `:114-137` (:127) | Top and binding lines use length = ceil(cut area / wof), which assumes pieces nest with no strip remainder; no margin | Under. Fixture cream (historical) buys 4 1/4 yd (153 in) against a 166 1/2 in strip plan (V-TOP-02) |
| D-11 | `strategies.py:86-126` (cut lengths at :101 and :116); `yardage.py:74-75` | Each border side is one piece at full length (83 in and 75 1/2 in on the fixture) with no joining step; border yardage is pooled by area | The cut list asks for 83 in pieces from 42 in fabric. A border-only fabric would buy 1 yd by area (32 1/8 in) while the joined-strip plan needs 42 1/2 in at 40 in usable (V-BORD-01) |
| D-12 | `strategies.py:376` (stored at :401-402) | Segments per set = wof // segment width = 21 | SS5 needs 147 segments; 7 sets x 21 = 147 leaves 0 spare, and on 40 in usable fabric 7 sets give 140 (V-SET-01: 8 sets) |
| D-13 | `pdf.py:37-39`, `:227-228`, `:243-244` vs `qrep/bridge.py:143-144` | PDF batting uses a fixed 64 e constant; web batting reads `settings.backing_margin` | Changing `backing_margin` changes web batting but not PDF batting |
| D-14 | `pdf.py:226` | A second copy of the vertical-only panel formula | Fixing `yardage.py` alone leaves the PDF panel count wrong |
| D-15 | `web/src/state/patternText.ts:57-58`; `PatternPanel.tsx:322`, `:327` | Batting yards = ceil(batting length / 9 in) "of a wide roll" with no roll width; "quilt plus 4 in on every side" is hard-coded | The yardage holds only for a roll at least as wide as the batting's other side (83 in for the fixture). The 4 in text ignores `backing_margin` |
| D-16 | `PatternPanel.tsx:334-337` | The footer states one usable width for every line, then says to buy a little extra | It must name both widths and the stated allowances instead |
| D-17 | `qrep/bridge.py:145` | The summary exposes one `usable_width` (= wof) | The web cannot show the separate backing width. The bridge v2 contract (E1) needs both |
| D-18 | `strategies.py:279-285` | The waste metric divides by purchased quarter yards from the area method | The metric changes when yardage changes. Not a purchase defect |

Documents that freeze today's math and need amendments in the governance PR (#106) or in A1 and
A2: `qrep-design-doc.md:74` (floor(42/2) = 21) and `:96-99` (42 in usable, vertical-only backing,
1/4 yd rounding); `docs/design/sprint-2/PARITY.md:83-89` (item 8 kept the engine's 42 in and its
backing formula over the mock's 40 in, orientation-optimized backing at `docs/viewer-mock.html:465-469`);
`docs/sprint-4/DECISIONS.md:67-73` (D4 keeps 42 in).

### 3.2 Tests and fixtures that pin today's math

[REBASELINE.md](REBASELINE.md) names the ticket that changes each row; this table gives the old
and new values. The fixture keeps its stored 42 in until A6 (section 1.3): A1, A2b and A9
regenerate it with no value change, and every fixture value that depends on U (strip sets, cut
counts, binding strips, `usable_width`, the view config `wof` and the goldens) changes only in A6.
Fixture values that read only B, such as the backing (V-BACK-09), change in A1. Rows that build
their own quilt change with the ticket that changes their math. Goldens change only in A6, the
one consolidated [bless] commit.

| Location | Pins today | New value |
| --- | --- | --- |
| `tests/test_construct.py:67-95` | Tiny quilt: area-based lengths, 1 binding strip, backing 112 e at 2 qy. It calls the aggregate `compute_yardage`, which folds the binding into the red line | V-TOP-04, written against the purchase lines once one yardage path remains |
| `tests/test_construct.py:115-126` | Checker quilt: 28 segments per set (336 // 12); binding 1 strip; cut count 13 | 26 per set (320 // 12); binding still 1 strip (ceil(208 / 300)); cut count still 13 |
| `tests/test_construct.py:129-145` | Fixture strip sets: 21 per set, SS5 7 sets, 25 sets | V-SET-01: 20, 8, 26 |
| `tests/test_construct.py:148-157` | Cut counts: historical 2488 (2475 squares + 4 border pieces + 9 binding strips); strip 633 (25 sets x 5 strips + 495 crosscuts + 4 border pieces + 9 binding strips) | Both totals change: binding 10 strips (V-BIND-01) and 26 sets x 5 = 130 strips (V-SET-01). The border term depends on how the cut list counts joined border strips (A2 and A4; 4 pieces today; 10 strips at 40 in, V-BORD-01) |
| `tests/test_construct.py:202-210` | Fixture backing 1568 e, 22 qy | V-BACK-09: 1568 e, 23 qy |
| `tests/test_exports.py:51-69` | Binding 180 e (9 strips); backing 5 1/2 yd; the "backing, any 42-inch WOF fabric" name | In A1: V-BACK-09, 5 3/4 yd, and a name built from B, while the binding stays at V-BIND-09 (180 e, 9 strips). In A6: V-BIND-01, 200 e (10 strips) |
| `tests/test_bridge.py:140-153`, `:191-197` | `usable_width` 336; `strip_set_count` 25; batting 664 x 784 | 320 (plus a new backing width field of 336); 26; batting unchanged |
| `tests/test_viewer.py:114` | View config `wof` 336 | 320 |
| `web/e2e/exports.spec.ts:95-102` (assertion at :99) | Strip strategy card shows 25 strip sets | 26 (V-SET-01) |
| `web/e2e/exports.spec.ts:104-128` (assertions at :113-114 and :120) | Backing row 22 quarter yards and "5 1/2"; the usable-width copy shows 42" | In A1: V-BACK-09, 23 quarter yards and "5 3/4", while the copy still shows the fixture's 42". Once the copy names both widths (D-16): 42 in for backing, and for cutting the fixture's 42 in until A6, then 40 in |
| `tests/test_fixture.py:16-20` | Committed fixture JSON equals the regenerated model (settings included) | Unchanged values when A1, A2b and A9 regenerate it; U = 40 and B = 42 when A6 regenerates it (section 1.3 migration note) |
| `tests/golden/cutlist_strip.md:8`, `cutlist_strip.csv:6` | 9 binding strips, cut 2 1/2 x 42 | 10 strips, printed as 2 1/2 in x WOF |
| `tests/golden/cutlist_strip.md:15-16`, `cutlist_strip.csv:4-5` | One 83 in and one 75 1/2 in border piece per side | Joined strips per V-BORD-01 |
| `tests/golden/cutlist_strip.md:22-26` | 21 segments per set, SS5 7 sets | 20 per set, SS5 8 sets |

## 4. Hand-computed test vectors

Defaults unless a vector says otherwise: U = 40 in (320 e), B = 42 in (336 e), BW = 108 in (864 e),
o = 4 in per side (2o = 64 e), w = 2 1/2 in (20 e), t = 10 in (80 e), j = 1/2 in (4 e),
s = 1 in (8 e), top margin 10 percent, pieced allowance 9 in (72 e), one-piece allowance
4 1/2 in (36 e), increment 1/4 yd (72 e). "qy" means quarter yards. "Today" values are hand
arithmetic on the current formulas.

### 4.1 Unit checks

```
V-UNIT-01  quarter-yard rounding, qy = ceil(e / 72)
  0 e -> 0 qy (no line printed)
  1 e -> ceil(1 / 72) = 1 qy
  72 e -> 1 qy; 73 e -> 2 qy
  1008 e (126 in) -> 1008 / 72 = 14 exactly -> 14 qy = 3 1/2 yd

V-UNIT-02  10 percent margin in integers, purchase = ceil(e x 110 / 100)
  1008 -> 110880 / 100 = 1108.8 -> 1109
  1200 -> 132000 / 100 = 1320 exactly -> 1320
  20   -> 2200 / 100 = 22 exactly -> 22
  288  -> 31680 / 100 = 316.8 -> 317
  200  -> 22000 / 100 = 220 exactly -> 220   (a floating-point ceil(200 x 1.1) gives 221; the four
          values above all pass under floating point, so this one is the check that catches it)

V-UNIT-03  backing panel thresholds, n(D) = 1 if D <= B else ceil((D - 8) / (B - 8))
  B = 42 (336 e), B - 8 = 328:
    n(336) = 1                                 (42 in)
    n(337) = ceil(329 / 328) = 2
    n(664) = ceil(656 / 328) = 2 exactly       (83 in = 2 x 42 - 1)
    n(665) = ceil(657 / 328) = 3
    n(992) = ceil(984 / 328) = 3 exactly       (124 in = 3 x 42 - 2)
    n(993) = ceil(985 / 328) = 4
  B = 40 (320 e), B - 8 = 312:
    n(320) = 1; n(321) = 2; n(632) = ceil(624 / 312) = 2 (79 in); n(633) = 3;
    n(944) = ceil(936 / 312) = 3 (118 in); n(945) = 4

V-UNIT-04  border join count, k(Lp) = 1 if Lp <= 320 else ceil((Lp - 4) / 316)
  k(320) = 1                                   (40 in)
  k(321) = ceil(317 / 316) = 2
  k(636) = ceil(632 / 316) = 2 exactly         (79 1/2 in = 2 x 40 - 1/2)
  k(637) = ceil(633 / 316) = 3

V-UNIT-05  pieces per strip, floor(U / cut)
  2 in cut (16 e):     U 40: 320 // 16 = 20    U 42: 336 // 16 = 21
  2 1/2 in cut (20 e): U 40: 320 // 20 = 16    U 42: 336 // 20 = 16
  3 1/2 in cut (28 e): U 40: 320 // 28 = 11    U 42: 336 // 28 = 12

V-UNIT-06  panel rule against a calculator's published example (B = 43 in = 344 e, no overhang)
  n(52 in = 416 e) = ceil((416 - 8) / (344 - 8)) = ceil(408 / 336) = ceil(1.214) = 2
  n(96 in = 768 e) = ceil(760 / 336) = ceil(2.262) = 3
  (Quilter's Paradise shows the same 2 and 3 panels. This checks the panel rule only; that
  calculator adds no allowance, and although its page says it rounds to 1/8 yd, it shows these two
  results as thirds, 5 1/3 and 4 1/3 yd.)
```

### 4.2 Strip yields, strip sets, borders and top fabrics

```
V-YIELD-01  200 squares cut 2 1/2 in, U = 40
  per = floor(40 / 2.5) = 16                   (320 // 20 = 16)
  strips = ceil(200 / 16) = ceil(12.5) = 13
  length = 13 x 2.5 = 32.5 in (260 e)
  last strip = 200 - 12 x 16 = 8 pieces

V-YIELD-02  160 rectangles cut 2 1/2 x 4 1/2 in (orientation tie at 42, flip at 40)
  U = 42 (336 e):
    2 1/2 in strips, subcut 4 1/2: per = floor(42 / 4.5) = 9 (336 // 36);
      strips = ceil(160 / 9) = ceil(17.78) = 18; length = 18 x 2.5 = 45 in (360 e)
    4 1/2 in strips, subcut 2 1/2: per = floor(42 / 2.5) = 16 (336 // 20);
      strips = ceil(160 / 16) = 10; length = 10 x 4.5 = 45 in (360 e)
    tie at 45 in -> keep the narrower strip: (18) 2 1/2 in strips, 9 per strip
    last strip = 160 - 17 x 9 = 7 pieces
  U = 40 (320 e):
    2 1/2 in strips: per = floor(40 / 4.5) = 8; strips = ceil(160 / 8) = 20; length = 50 in (400 e)
    4 1/2 in strips: per = floor(40 / 2.5) = 16; strips = 10; length = 45 in (360 e)
    keep 4 1/2 in strips: (10) strips, 16 per strip, 45 in; last strip = 160 - 9 x 16 = 16 (full)

V-YIELD-03  piece longer than U (fallback rule): 4 pieces cut 2 1/2 x 60 1/2 in, U = 40
  60.5 > 40, so cut 2 1/2 in strips and join them per piece:
  k = ceil((60.5 - 0.5) / (40 - 0.5)) = ceil(60 / 39.5) = ceil(1.519) = 2
    (eighths: ceil((484 - 4) / 316) = ceil(480 / 316) = 2)
  strips = 4 x 2 = 8; length = 8 x 2.5 = 20 in (160 e)
  orientation 2 (60 1/2 in strips, subcut 2 1/2): per = floor(40 / 2.5) = 16 (320 // 20);
    strips = ceil(4 / 16) = 1; length = 60.5 in (484 e)
  keep the joined cut (20 in < 60.5 in): (8) 2 1/2 in strips, 2 joined per piece

V-SET-01  fixture strip sets, U = 40, segments cut 2 in (1 1/2 in cell + 1/2 in)
  per_set = floor(40 / 2) = 20                 (320 // 16)
  needed (from the fixture's 50 A and 49 B blocks): SS1 bbcbb 100, SS2 bbbbb 100,
    SS3 cbbbc 50, SS4 bcccb 98, SS5 ccccc 147
  SS1 ceil(100 / 20) = 5; SS2 ceil(100 / 20) = 5; SS3 ceil(50 / 20) = ceil(2.5) = 3;
  SS4 ceil(98 / 20) = ceil(4.9) = 5; SS5 ceil(147 / 20) = ceil(7.35) = 8
  total sets = 5 + 5 + 3 + 5 + 8 = 26          (today 25: 21 per set, SS5 7)

V-SET-02  fixture strip-set fabric strips, U = 40 (sets from V-SET-01)
  blue:  SS1 4 x 5 = 20; SS2 5 x 5 = 25; SS3 3 x 3 = 9; SS4 2 x 5 = 10; SS5 0
         = 64 strips x 2 in = 128 in (1024 e)
  cream: SS1 1 x 5 = 5; SS2 0; SS3 2 x 3 = 6; SS4 3 x 5 = 15; SS5 5 x 8 = 40
         = 66 strips x 2 in = 132 in (1056 e)

V-BORD-01  fixture border: center 67 1/2 x 82 1/2, b = 3 3/4
  cut strip width = 3.75 + 0.5 = 4.25 in (34 e)
  sides Ls = 82.5 + 0.5 = 83 in (664 e); top and bottom Lt = 67.5 + 7.5 + 0.5 = 75.5 in (604 e)
  U = 40:
    sides: 83 > 40, k = ceil((83 - 0.5) / 39.5) = ceil(82.5 / 39.5) = ceil(2.089) = 3 -> 6 strips
      (eighths: ceil(660 / 316) = 3)
    top/bottom: 75.5 > 40, k = ceil(75 / 39.5) = ceil(1.899) = 2 -> 4 strips
      (eighths: ceil(600 / 316) = 2)
    total 10 strips; length = 10 x 4.25 = 42.5 in (340 e)
  U = 42 (configured):
    sides k = ceil(82.5 / 41.5) = ceil(1.988) = 2 -> 4; top/bottom k = ceil(75 / 41.5) = ceil(1.807) = 2 -> 4
    total 8 strips; length = 8 x 4.25 = 34 in (272 e)

V-BORD-02  crib: center 32 x 48, b = 2 (finished 36 x 52), U = 40
  cut width 2.5 in (20 e); Ls = 48 + 0.5 = 48.5 in (388 e); Lt = 32 + 4 + 0.5 = 36.5 in (292 e)
  sides: 48.5 > 40, k = ceil(48 / 39.5) = ceil(1.215) = 2 -> 4 strips
  top/bottom: 36.5 <= 40, per = floor(40 / 36.5) = 1 -> ceil(2 / 1) = 2 strips
  total 6 strips; length = 6 x 2.5 = 15 in (120 e)

V-BORD-03  two bands: center 60 x 72, band 1 b = 2, band 2 b = 5, U = 40
  band 1: cut 2.5 in (20 e); Ls = 72.5 in (580 e): k = ceil(72 / 39.5) = ceil(1.823) = 2 -> 4;
          Lt = 60 + 4 + 0.5 = 64.5 in (516 e): k = ceil(64 / 39.5) = ceil(1.620) = 2 -> 4;
          8 strips; 8 x 2.5 = 20 in (160 e)
  inner size for band 2 = 64 x 76
  band 2: cut 5.5 in (44 e); Ls = 76.5 in (612 e): k = ceil(76 / 39.5) = ceil(1.924) = 2 -> 4;
          Lt = 64 + 10 + 0.5 = 74.5 in (596 e): k = ceil(74 / 39.5) = ceil(1.873) = 2 -> 4;
          8 strips; 8 x 5.5 = 44 in (352 e)
  finished quilt 74 x 86

V-BORD-04  short pieces share a strip (the existing tiny test quilt): center 4 x 4, b = 1, U = 40
  cut width 1.5 in (12 e)
  Ls = 4.5 in (36 e): per = floor(40 / 4.5) = 8 -> ceil(2 / 8) = 1 strip
  Lt = 4 + 2 + 0.5 = 6.5 in (52 e): per = floor(40 / 6.5) = 6 -> ceil(2 / 6) = 1 strip
  total 2 strips; length = 2 x 1.5 = 3 in (24 e)

V-TOP-01  fixture historical, blue: 1246 squares cut 2 in, U = 40
  per = 20; strips = ceil(1246 / 20) = ceil(62.3) = 63; last strip = 1246 - 62 x 20 = 6
  length_needed = 63 x 2 = 126 in (1008 e)
  purchase = ceil(1008 x 110 / 100) = ceil(1108.8) = 1109 e
  qy = ceil(1109 / 72) = ceil(15.40) = 16 -> 4 yd
  without margin: 1008 / 72 = 14 exactly -> 3 1/2 yd with 0 in to spare
  today: area 1246 x 16 x 16 = 318976 e^2; 318976 / 336 = 949.3 -> 950 e (118 3/4 in) -> 14 qy = 3 1/2 yd

V-TOP-02  fixture historical, cream: 1229 squares cut 2 in, plus the V-BORD-01 band, U = 40
  per = 20; strips = ceil(1229 / 20) = ceil(61.45) = 62; last strip = 1229 - 61 x 20 = 9
  squares 62 x 2 = 124 in (992 e) + border 42.5 in (340 e) = 166.5 in (1332 e) = length_needed
  purchase = ceil(1332 x 110 / 100) = ceil(1465.2) = 1466 e
  qy = ceil(1466 / 72) = ceil(20.36) = 21 -> 5 1/4 yd
  without margin: 1332 / 72 = 18.5 -> 19 qy = 4 3/4 yd
  today: area = 1229 x 256 + 2 x 34 x 664 + 2 x 604 x 34 = 314624 + 45152 + 41072 = 400848 e^2;
         400848 / 336 = 1193 e (149 1/8 in) -> ceil(1193 / 72) = 17 qy = 4 1/4 yd = 153 in,
         13 1/2 in less than the strip plan

V-TOP-03  fixture strip strategy, U = 40 (strips from V-SET-02, border from V-BORD-01)
  blue:  length_needed = 1024 e (128 in); purchase = ceil(1024 x 110 / 100) = ceil(1126.4) = 1127 e;
         qy = ceil(1127 / 72) = ceil(15.65) = 16 -> 4 yd   (without margin ceil(1024 / 72) = 15 -> 3 3/4 yd)
  cream: length_needed = 1056 + 340 = 1396 e (174 1/2 in); purchase = ceil(1396 x 110 / 100) = ceil(1535.6) = 1536 e;
         qy = ceil(1536 / 72) = ceil(21.33) = 22 -> 5 1/2 yd   (without margin ceil(1396 / 72) = 20 -> 5 yd)
  today: blue 64 x 16 x 336 / 336 = 1024 e -> 15 qy = 3 3/4 yd;
         cream (61 strips at 21 per set + border area) 414160 / 336 -> 1233 e (154 1/8 in) -> 18 qy = 4 1/2 yd

V-TOP-04  the tiny test quilt, every line: 2 x 2 cells of 2 in (cut 2 1/2), red and white on the
          diagonals, 1 in white border, red binding; finished 6 x 6 in
  red top:   2 squares, per 16 -> 1 strip -> 2.5 in (20 e); purchase ceil(20 x 110 / 100) = 22 e -> qy 1 -> 1/4 yd
  white top: 2 squares -> 1 strip (20 e) + border V-BORD-04 (24 e) = 44 e (5.5 in);
             purchase ceil(44 x 110 / 100) = ceil(48.4) = 49 e -> qy 1 -> 1/4 yd
  binding:   T = 2 (6 + 6) + 10 = 34 in (272 e); strips = ceil(272 / 300) = 1; length 20 e -> qy 1 -> 1/4 yd
  backing:   Wb = Lb = 6 + 8 = 14 in (112 e) <= 42 -> one piece either way; tie -> vertical;
             total = 112 + 36 = 148 e; qy = ceil(148 / 72) = ceil(2.06) = 3 -> 3/4 yd
             (today 112 e -> 2 qy = 1/2 yd, with no allowance)
  wide-back: not shown (one panel)
  batting:   14 x 14 -> crib package
```

### 4.3 Binding

U - w = 40 - 2.5 = 37.5 in (300 e) unless stated. "Today" uses ceil(T / 42) strips; the "joined"
figure is today's strips x (42 - 2 1/2), which is what those strips supply once joined.

```
V-BIND-01  fixture 75 x 90
  T = 2 (75 + 90) + 10 = 340 in (2720 e)
  strips = ceil(340 / 37.5) = ceil(9.067) = 10   (eighths: ceil(2720 / 300) = 10)
  length = 10 x 2.5 = 25 in (200 e); qy = ceil(200 / 72) = ceil(2.78) = 3 -> 3/4 yd
  loop check: 10 x 37.5 = 375 >= 340
  today: ceil(340 / 42) = 9 strips, 22 1/2 in (180 e), 3/4 yd; joined 9 x 39.5 = 355.5 >= 340

V-BIND-02  76 x 85
  T = 2 (76 + 85) + 10 = 332 in (2656 e); strips = ceil(332 / 37.5) = ceil(8.853) = 9
  length = 22.5 in (180 e); qy = ceil(180 / 72) = ceil(2.5) = 3 -> 3/4 yd; loop 337.5 >= 332
  today: 8 strips; joined 8 x 39.5 = 316 < perimeter 322

V-BIND-03  53 1/2 x 67
  T = 2 (53.5 + 67) + 10 = 251 in (2008 e); strips = ceil(251 / 37.5) = ceil(6.693) = 7
  length = 17.5 in (140 e); qy = ceil(140 / 72) = ceil(1.94) = 2 -> 1/2 yd; loop 262.5 >= 251
  today: 6 strips; joined 6 x 39.5 = 237 < perimeter 241

V-BIND-04  70 x 88
  T = 2 (70 + 88) + 10 = 326 in (2608 e); strips = ceil(326 / 37.5) = ceil(8.693) = 9
  length = 22.5 in (180 e); qy = 3 -> 3/4 yd; loop 337.5 >= 326
  today: 8 strips; joined 8 x 39.5 = 316 = perimeter 316 exactly, nothing left for corners or the final join

V-BIND-05  queen 92 1/2 x 115
  T = 2 (92.5 + 115) + 10 = 425 in (3400 e); strips = ceil(425 / 37.5) = ceil(11.333) = 12
  length = 30 in (240 e); qy = ceil(240 / 72) = ceil(3.33) = 4 -> 1 yd; loop 450 >= 425
  today: 11 strips, 27 1/2 in, 1 yd; joined 11 x 39.5 = 434.5 >= 425

V-BIND-06  102 1/2 x 120
  T = 2 (102.5 + 120) + 10 = 455 in (3640 e); strips = ceil(455 / 37.5) = ceil(12.133) = 13
  length = 32.5 in (260 e); qy = ceil(260 / 72) = ceil(3.61) = 4 -> 1 yd; loop 487.5 >= 455
  today: 11 strips; joined 434.5 < perimeter 445

V-BIND-07  68 x 68
  T = 4 x 68 + 10 = 282 in (2256 e); strips = ceil(282 / 37.5) = ceil(7.52) = 8
  length = 20 in (160 e); qy = ceil(160 / 72) = ceil(2.22) = 3 -> 3/4 yd; loop 300 >= 282
  today: 7 strips; joined 7 x 39.5 = 276.5, which covers the 272 in perimeter but leaves 4.5 of the 10 in extra

V-BIND-08  binding strip width w = 2 1/4 in (18 e): (a) moves only the length; (b) moves the count and the purchase
  (a) fixture 75 x 90: U - w = 40 - 2.25 = 37.75 in (302 e); strips = ceil(340 / 37.75) = ceil(9.007) = 10
      length = 10 x 2.25 = 22.5 in (180 e); qy = 3 -> 3/4 yd
      (V-BIND-01 at w = 2 1/2 is also 10 strips and 3 qy, so only length_needed changes: 200 e -> 180 e)
  (b) 94 x 108: T = 2 (94 + 108) + 10 = 414 in (3312 e)
      w = 2 1/2: strips = ceil(414 / 37.5) = ceil(11.04) = 12; length = 12 x 2.5 = 30 in (240 e);
                 qy = ceil(240 / 72) = ceil(3.33) = 4 -> 1 yd; loop 12 x 37.5 = 450 >= 414
      w = 2 1/4: strips = ceil(414 / 37.75) = ceil(10.967) = 11; length = 11 x 2.25 = 24.75 in (198 e)
                 qy = ceil(198 / 72) = ceil(2.75) = 3 -> 3/4 yd; loop 11 x 37.75 = 415.25 >= 414

V-BIND-09  fixture at U = 42 (configured)
  U - w = 39.5 in (316 e); strips = ceil(340 / 39.5) = ceil(8.608) = 9
  length = 22.5 in (180 e); qy = 3 -> 3/4 yd

V-BIND-10  42 x 52
  T = 2 (42 + 52) + 10 = 198 in (1584 e); strips = ceil(198 / 37.5) = ceil(5.28) = 6
  length = 15 in (120 e); qy = ceil(120 / 72) = ceil(1.67) = 2 -> 1/2 yd; loop 225 >= 198
  today: 5 strips; joined 5 x 39.5 = 197.5 < 198

V-BIND-11  crib 36 x 52
  T = 2 (36 + 52) + 10 = 186 in (1488 e); strips = ceil(186 / 37.5) = ceil(4.96) = 5
  length = 12.5 in (100 e); qy = ceil(100 / 72) = ceil(1.39) = 2 -> 1/2 yd; loop 187.5 >= 186
  today: 5 strips, 1/2 yd (same)

V-BIND-12  throw 50 x 65
  T = 2 (50 + 65) + 10 = 240 in (1920 e); strips = ceil(240 / 37.5) = ceil(6.4) = 7
  length = 17.5 in (140 e); qy = 2 -> 1/2 yd; loop 262.5 >= 240
  today: 6 strips; joined 6 x 39.5 = 237 < 240

V-BIND-13  throw 60 x 72
  T = 2 (60 + 72) + 10 = 274 in (2192 e); strips = ceil(274 / 37.5) = ceil(7.307) = 8
  length = 20 in (160 e); qy = 3 -> 3/4 yd; loop 300 >= 274
  today: 7 strips, 1/2 yd; joined 7 x 39.5 = 276.5 >= 274 at 42 in, but 7 x 37.5 = 262.5 < 274 on 40 in usable fabric

V-BIND-14  twin 70 x 90
  T = 2 (70 + 90) + 10 = 330 in (2640 e); strips = ceil(330 / 37.5) = ceil(8.8) = 9
  length = 22.5 in (180 e); qy = 3 -> 3/4 yd; loop 337.5 >= 330
  today: 8 strips; joined 316 < perimeter 320

V-BIND-15  full 84 x 90
  T = 2 (84 + 90) + 10 = 358 in (2864 e); strips = ceil(358 / 37.5) = ceil(9.547) = 10
  length = 25 in (200 e); qy = 3 -> 3/4 yd; loop 375 >= 358
  today: 9 strips; joined 355.5 < 358 (covers the 348 in perimeter, short of the extra)

V-BIND-16  queen 90 x 108
  T = 2 (90 + 108) + 10 = 406 in (3248 e); strips = ceil(406 / 37.5) = ceil(10.827) = 11
  length = 27.5 in (220 e); qy = ceil(220 / 72) = ceil(3.06) = 4 -> 1 yd; loop 412.5 >= 406
  today: 10 strips, 25 in, 3/4 yd; joined 395 < perimeter 396

V-BIND-17  king 110 x 108
  T = 2 (110 + 108) + 10 = 446 in (3568 e); strips = ceil(446 / 37.5) = ceil(11.893) = 12
  length = 30 in (240 e); qy = 4 -> 1 yd; loop 450 >= 446
  today: 11 strips; joined 434.5 < perimeter 436

V-BIND-18  58 x 66
  T = 2 (58 + 66) + 10 = 258 in (2064 e); strips = ceil(258 / 37.5) = ceil(6.88) = 7
  length = 17.5 in (140 e); qy = 2 -> 1/2 yd; loop 262.5 >= 258
```

### 4.4 Backing, pieced (B = 42)

n(D) = 1 if D <= 42, else ceil((D - 1) / 41). The allowance is +9 in for two or more panels and
+4 1/2 in for one. Each vector shows both layouts.

V-BACK-01 and V-BACK-02 are the two planning cases: over-estimate examples recorded when this work
was planned (see J7 in the plan), each with a calculator figure whose calculator was not recorded.
They show the kind of error a quilter reported; the reported case itself is Q1.

```
V-BACK-01  queen 92 1/2 x 115 (planning case: today 10 1/4 yd; a calculator gave 8 3/8 yd)
  Wb = 92.5 + 8 = 100.5 in (804 e); Lb = 115 + 8 = 123 in (984 e)
  vertical:   n(100.5) = ceil(99.5 / 41) = ceil(2.427) = 3; 3 x 123 = 369; + 9 = 378
  horizontal: n(123) = ceil(122 / 41) = ceil(2.976) = 3; 3 x 100.5 = 301.5 in (2412 e); + 9 = 310.5 in (2484 e)
  keep horizontal (310.5 < 378): (3) panels cut 100 1/2 in, seams across the quilt
  check: 3 x 42 - 2 = 124 >= 123 (1 in to spare)
  qy = ceil(2484 / 72) = ceil(34.5) = 35 -> 8 3/4 yd
  today: ceil(804 / 336) = 3 panels x 123 = 369 in (2952 e) -> 41 qy = 10 1/4 yd
  new is 1 1/2 yd less than today and 3/8 yd more than the calculator (see the policy table below)

V-BACK-02  throw 60 x 72 (planning case: today 4 1/2 yd; a calculator gave 3 7/8 yd)
  Wb = 68 in (544 e); Lb = 80 in (640 e)
  vertical:   n(68) = ceil(67 / 41) = ceil(1.634) = 2; 2 x 80 = 160; + 9 = 169
  horizontal: n(80) = ceil(79 / 41) = ceil(1.927) = 2; 2 x 68 = 136 in (1088 e); + 9 = 145 in (1160 e)
  keep horizontal: (2) panels cut 68 in; check 2 x 42 - 1 = 83 >= 80
  qy = ceil(1160 / 72) = ceil(16.11) = 17 -> 4 1/4 yd
  today: 2 panels x 80 = 160 in -> 18 qy = 4 1/2 yd

V-BACK-03  crib 36 x 52
  Wb = 44 in (352 e); Lb = 60 in (480 e)
  vertical:   n(44) = ceil(43 / 41) = ceil(1.049) = 2; 2 x 60 = 120; + 9 = 129
  horizontal: n(60) = ceil(59 / 41) = ceil(1.439) = 2; 2 x 44 = 88 in (704 e); + 9 = 97 in (776 e)
  keep horizontal; qy = ceil(776 / 72) = ceil(10.78) = 11 -> 2 3/4 yd
  today: 2 x 60 = 120 in -> 14 qy = 3 1/2 yd

V-BACK-04  throw 50 x 65
  Wb = 58 in (464 e); Lb = 73 in (584 e)
  vertical:   n(58) = ceil(57 / 41) = ceil(1.390) = 2; 2 x 73 = 146; + 9 = 155
  horizontal: n(73) = ceil(72 / 41) = ceil(1.756) = 2; 2 x 58 = 116 in (928 e); + 9 = 125 in (1000 e)
  keep horizontal; qy = ceil(1000 / 72) = ceil(13.89) = 14 -> 3 1/2 yd
  today: 2 x 73 = 146 in -> 17 qy = 4 1/4 yd

V-BACK-05  twin 70 x 90
  Wb = 78 in (624 e); Lb = 98 in (784 e)
  vertical:   n(78) = ceil(77 / 41) = ceil(1.878) = 2; 2 x 98 = 196 in (1568 e); + 9 = 205 in (1640 e)
  horizontal: n(98) = ceil(97 / 41) = ceil(2.366) = 3; 3 x 78 = 234; + 9 = 243
  keep vertical; check 2 x 42 - 1 = 83 >= 78; qy = ceil(1640 / 72) = ceil(22.78) = 23 -> 5 3/4 yd
  today: 2 x 98 = 196 in -> 22 qy = 5 1/2 yd (the extra 1/4 yd is the new allowance)

V-BACK-06  full 84 x 90
  Wb = 92 in (736 e); Lb = 98 in (784 e)
  vertical:   n(92) = ceil(91 / 41) = ceil(2.220) = 3; 3 x 98 = 294; + 9 = 303
  horizontal: n(98) = 3; 3 x 92 = 276 in (2208 e); + 9 = 285 in (2280 e)
  keep horizontal; check 3 x 42 - 2 = 124 >= 98; qy = ceil(2280 / 72) = ceil(31.67) = 32 -> 8 yd
  today: 3 x 98 = 294 in -> 33 qy = 8 1/4 yd

V-BACK-07  queen 90 x 108
  Wb = 98 in (784 e); Lb = 116 in (928 e)
  vertical:   n(98) = 3; 3 x 116 = 348; + 9 = 357
  horizontal: n(116) = ceil(115 / 41) = ceil(2.805) = 3; 3 x 98 = 294 in (2352 e); + 9 = 303 in (2424 e)
  keep horizontal; check 124 >= 116; qy = ceil(2424 / 72) = ceil(33.67) = 34 -> 8 1/2 yd
  today: 3 x 116 = 348 in -> 39 qy = 9 3/4 yd

V-BACK-08  king 110 x 108 (three panels across)
  Wb = 118 in (944 e); Lb = 116 in (928 e)
  vertical:   n(118) = ceil(117 / 41) = ceil(2.854) = 3; 3 x 116 = 348 in (2784 e); + 9 = 357 in (2856 e)
  horizontal: n(116) = 3; 3 x 118 = 354; + 9 = 363
  keep vertical; check 124 >= 118; qy = ceil(2856 / 72) = ceil(39.67) = 40 -> 10 yd
  today: 3 x 116 = 348 in -> 39 qy = 9 3/4 yd (the extra 1/4 yd is the new allowance)

V-BACK-09  fixture 75 x 90 (zero slack)
  Wb = 83 in (664 e); Lb = 98 in (784 e)
  vertical:   n(83) = ceil(82 / 41) = 2 exactly; 2 x 98 = 196 in (1568 e); + 9 = 205 in (1640 e)
  horizontal: n(98) = 3; 3 x 83 = 249; + 9 = 258
  keep vertical; check 2 x 42 - 1 = 83 = 83 (0 in slack: exactly the 4 in overhang)
  length_needed = 1568 e (same as today); qy = ceil(1640 / 72) = 23 -> 5 3/4 yd (today 22 qy = 5 1/2 yd)

V-BACK-10  76 x 85 (the seam allowance forces three panels)
  Wb = 84 in (672 e); Lb = 93 in (744 e)
  vertical:   n(84) = ceil(83 / 41) = ceil(2.024) = 3 (2 x 42 - 1 = 83 < 84); 3 x 93 = 279; + 9 = 288
  horizontal: n(93) = ceil(92 / 41) = ceil(2.244) = 3; 3 x 84 = 252 in (2016 e); + 9 = 261 in (2088 e)
  keep horizontal; qy = 2088 / 72 = 29 exactly -> 7 1/4 yd
  today: ceil(672 / 336) = 2 panels x 93 = 186 in -> 21 qy = 5 1/4 yd; after a 1/2 in seam the two
         panels give 83 in against 84 in needed (3 1/2 in overhang instead of 4)

V-BACK-11  42 x 52
  Wb = 50 in (400 e); Lb = 60 in (480 e)
  vertical:   n(50) = ceil(49 / 41) = ceil(1.195) = 2; 2 x 60 = 120; + 9 = 129
  horizontal: n(60) = 2; 2 x 50 = 100 in (800 e); + 9 = 109 in (872 e)
  keep horizontal; qy = ceil(872 / 72) = ceil(12.11) = 13 -> 3 1/4 yd
  today: 2 x 60 = 120 in -> 14 qy = 3 1/2 yd

V-BACK-12  28 x 28 (one piece)
  Wb = Lb = 36 in (288 e) <= 42 -> n = 1 both ways; length 36; + 4.5 = 40.5 in (324 e) both ways
  tie -> vertical (one piece, no seam); qy = ceil(324 / 72) = ceil(4.5) = 5 -> 1 1/4 yd
  today: 36 in -> 4 qy = 1 yd, with 0 in to spare

V-BACK-13  68 x 68 (tie)
  Wb = Lb = 76 in (608 e); n(76) = ceil(75 / 41) = ceil(1.829) = 2 both ways
  2 x 76 = 152 in (1216 e) both ways; + 9 = 161 in (1288 e) both ways; tie -> vertical
  qy = ceil(1288 / 72) = ceil(17.89) = 18 -> 4 1/2 yd
  today: 152 in -> 17 qy = 4 1/4 yd

V-BACK-14  24 x 58 (a one-piece backing beats two panels on the total)
  Wb = 32 in (256 e); Lb = 66 in (528 e)
  vertical:   n(32) = 1 (32 <= 42); length 66 in (528 e); + 4.5 = 70.5 in (564 e)
  horizontal: n(66) = ceil(65 / 41) = ceil(1.585) = 2; 2 x 32 = 64 in (512 e); + 9 = 73 in (584 e)
  keep vertical (70.5 < 73), although the horizontal raw length is shorter (64 < 66)
  qy = ceil(564 / 72) = ceil(7.83) = 8 -> 2 yd
  a raw-length comparison would keep two panels and buy ceil(584 / 72) = 9 qy = 2 1/4 yd
  today: 1 panel x 66 in (528 e) -> 8 qy = 2 yd (same purchase, but no allowance)

V-BACK-15  140 x 140 (the largest requested size; four panels)
  Wb = Lb = 148 in (1184 e); n(148) = ceil(147 / 41) = ceil(3.585) = 4 both ways
  4 x 148 = 592 in (4736 e); + 9 = 601 in (4808 e); tie -> vertical; check 4 x 42 - 3 = 165 >= 148
  qy = ceil(4808 / 72) = ceil(66.78) = 67 -> 16 3/4 yd
  today: 4 x 148 = 592 in -> ceil(4736 / 72) = 66 qy = 16 1/2 yd

V-BACK-16  102 1/2 x 120
  Wb = 110.5 in (884 e); Lb = 128 in (1024 e)
  vertical:   n(110.5) = ceil(109.5 / 41) = ceil(2.671) = 3; 3 x 128 = 384 in (3072 e); + 9 = 393 in (3144 e)
  horizontal: n(128) = ceil(127 / 41) = ceil(3.098) = 4; 4 x 110.5 = 442; + 9 = 451
  keep vertical; qy = ceil(3144 / 72) = ceil(43.67) = 44 -> 11 yd
  today: 3 x 128 = 384 in -> 43 qy = 10 3/4 yd

V-BACK-17  53 1/2 x 67
  Wb = 61.5 in (492 e); Lb = 75 in (600 e)
  vertical:   n(61.5) = ceil(60.5 / 41) = ceil(1.476) = 2; 2 x 75 = 150; + 9 = 159
  horizontal: n(75) = ceil(74 / 41) = ceil(1.805) = 2; 2 x 61.5 = 123 in (984 e); + 9 = 132 in (1056 e)
  keep horizontal; qy = ceil(1056 / 72) = ceil(14.67) = 15 -> 3 3/4 yd
  today: 2 x 75 = 150 in -> 17 qy = 4 1/4 yd

V-BACK-18  queen 92 1/2 x 115 at B = 40 (configured; n = ceil((D - 1) / 39))
  vertical:   n(100.5) = ceil(99.5 / 39) = ceil(2.551) = 3; 3 x 123 = 369 in (2952 e); + 9 = 378 in (3024 e)
  horizontal: n(123) = ceil(122 / 39) = ceil(3.128) = 4 (3 x 40 - 2 = 118 < 123); 4 x 100.5 = 402; + 9 = 411
  keep vertical; qy = 3024 / 72 = 42 -> 10 1/2 yd
  (using the 40 in strip-cutting width for backing would put this case above today's 10 1/4 yd)

V-BACK-19  throw 60 x 72 at B = 40 (configured)
  vertical:   n(68) = ceil(67 / 39) = ceil(1.718) = 2; 2 x 80 = 160 in (1280 e); + 9 = 169 in (1352 e)
  horizontal: n(80) = ceil(79 / 39) = ceil(2.026) = 3 (2 x 40 - 1 = 79 < 80); 3 x 68 = 204; + 9 = 213
  keep vertical; qy = ceil(1352 / 72) = ceil(18.78) = 19 -> 4 3/4 yd

V-BACK-20  fixture 75 x 90 at B = 40 (configured)
  vertical:   n(83) = ceil(82 / 39) = ceil(2.103) = 3; 3 x 98 = 294; + 9 = 303
  horizontal: n(98) = ceil(97 / 39) = ceil(2.487) = 3; 3 x 83 = 249 in (1992 e); + 9 = 258 in (2064 e)
  keep horizontal; qy = ceil(2064 / 72) = ceil(28.67) = 29 -> 7 1/4 yd

V-BACK-21  queen 92 1/2 x 115, domestic overhang (2 in per side, 2o = 4 in = 32 e)
  Wb = 96.5 in (772 e); Lb = 119 in (952 e)
  vertical:   n(96.5) = ceil(95.5 / 41) = ceil(2.329) = 3; 3 x 119 = 357; + 9 = 366
  horizontal: n(119) = ceil(118 / 41) = ceil(2.878) = 3; 3 x 96.5 = 289.5 in (2316 e); + 9 = 298.5 in (2388 e)
  keep horizontal; qy = ceil(2388 / 72) = ceil(33.17) = 34 -> 8 1/2 yd

V-BACK-22  throw 60 x 72, domestic overhang
  Wb = 64 in (512 e); Lb = 76 in (608 e)
  vertical:   n(64) = ceil(63 / 41) = ceil(1.537) = 2; 2 x 76 = 152; + 9 = 161
  horizontal: n(76) = ceil(75 / 41) = ceil(1.829) = 2; 2 x 64 = 128 in (1024 e); + 9 = 137 in (1096 e)
  keep horizontal; qy = ceil(1096 / 72) = ceil(15.22) = 16 -> 4 yd

V-BACK-23  58 x 66
  Wb = 66 in (528 e); Lb = 74 in (592 e)
  vertical:   n(66) = ceil(65 / 41) = ceil(1.585) = 2; 2 x 74 = 148; + 9 = 157
  horizontal: n(74) = ceil(73 / 41) = ceil(1.780) = 2; 2 x 66 = 132 in (1056 e); + 9 = 141 in (1128 e)
  keep horizontal; qy = ceil(1128 / 72) = ceil(15.67) = 16 -> 4 yd
```

Policy alternatives for the backing allowance and increment (section 6, Q2 and Q3). Columns: A is
the default (+9 in / +4 1/2 in, 1/4 yd). B keeps the allowance and rounds to 1/8 yd (36 e).
C drops the allowance and rounds to 1/4 yd. D drops the allowance and rounds to 1/8 yd. Layouts
do not change across columns for these sizes, because both layouts have two or more panels.
Arithmetic: A = ceil(total / 72), B = ceil(total / 36) eighths of a yard, C = ceil(length / 72),
D = ceil(length / 36). Example for V-BACK-01: B = ceil(2484 / 36) = 69 eighths = 8 5/8;
C = ceil(2412 / 72) = ceil(33.5) = 34 qy = 8 1/2; D = 2412 / 36 = 67 eighths = 8 3/8.

| Vector | Size | Raw length / total | A (default) | B | C | D | Today |
| --- | --- | --- | --- | --- | --- | --- | --- |
| V-BACK-03 | crib 36 x 52 | 88 / 97 in | 2 3/4 | 2 3/4 | 2 1/2 | 2 1/2 | 3 1/2 |
| V-BACK-04 | throw 50 x 65 | 116 / 125 | 3 1/2 | 3 1/2 | 3 1/4 | 3 1/4 | 4 1/4 |
| V-BACK-02 | throw 60 x 72 | 136 / 145 | 4 1/4 | 4 1/8 | 4 | 3 7/8 | 4 1/2 |
| V-BACK-05 | twin 70 x 90 | 196 / 205 | 5 3/4 | 5 3/4 | 5 1/2 | 5 1/2 | 5 1/2 |
| V-BACK-06 | full 84 x 90 | 276 / 285 | 8 | 8 | 7 3/4 | 7 3/4 | 8 1/4 |
| V-BACK-07 | queen 90 x 108 | 294 / 303 | 8 1/2 | 8 1/2 | 8 1/4 | 8 1/4 | 9 3/4 |
| V-BACK-01 | queen 92 1/2 x 115 | 301 1/2 / 310 1/2 | 8 3/4 | 8 5/8 | 8 1/2 | 8 3/8 | 10 1/4 |
| V-BACK-08 | king 110 x 108 | 348 / 357 | 10 | 10 | 9 3/4 | 9 3/4 | 9 3/4 |
| V-BACK-09 | fixture 75 x 90 | 196 / 205 | 5 3/4 | 5 3/4 | 5 1/2 | 5 1/2 | 5 1/2 |
| V-BACK-10 | 76 x 85 | 252 / 261 | 7 1/4 | 7 1/4 | 7 | 7 | 5 1/4 (short) |

Column D reproduces both planning-case calculator figures exactly (8 3/8 and 3 7/8 yd). Column A
lands 3/8 yd above them and 1 1/2 yd (queen) and 1/4 yd (throw) below today.

### 4.5 Wide-back (BW = 108 in = 864 e; +4 1/2 in)

```
V-WIDE-01  queen 92 1/2 x 115
  Wb 100.5 <= 108, Lb 123 > 108 -> length = Lb = 123 in (984 e); + 4.5 = 127.5 in (1020 e)
  qy = ceil(1020 / 72) = ceil(14.17) = 15 -> 3 3/4 yd

V-WIDE-02  throw 60 x 72
  both fit -> length = min(68, 80) = 68 in (544 e), with the 80 in side across the 108 in width
  + 4.5 = 72.5 in (580 e); qy = ceil(580 / 72) = ceil(8.06) = 9 -> 2 1/4 yd

V-WIDE-03  76 x 85
  both fit -> min(84, 93) = 84 in (672 e); + 4.5 = 88.5 in (708 e); qy = ceil(708 / 72) = ceil(9.83) = 10 -> 2 1/2 yd

V-WIDE-04  queen 90 x 108
  Wb 98 fits, Lb 116 > 108 -> length 116 in (928 e); + 4.5 = 120.5 in (964 e)
  qy = ceil(964 / 72) = ceil(13.39) = 14 -> 3 1/2 yd

V-WIDE-05  king 110 x 108
  Wb 118 > 108 and Lb 116 > 108 -> no 108 in line
  at BW = 118 (944 e, configured): both fit -> min(118, 116) = 116 in (928 e); + 4.5 -> 964 e -> 14 qy -> 3 1/2 yd

V-WIDE-06  102 1/2 x 120
  Wb 110.5 > 108 and Lb 128 > 108 -> no 108 in line
  at BW = 118: Wb 110.5 fits, Lb 128 > 118 -> length 128 in (1024 e); + 4.5 = 132.5 in (1060 e);
  qy = ceil(1060 / 72) = ceil(14.72) = 15 -> 3 3/4 yd

V-WIDE-07  28 x 28 and the tiny quilt: the pieced layout is one panel -> no wide-back line

V-WIDE-08  fixture 75 x 90
  both fit -> min(83, 98) = 83 in (664 e); + 4.5 = 87.5 in (700 e); qy = ceil(700 / 72) = ceil(9.72) = 10 -> 2 1/2 yd

V-WIDE-09  42 x 52
  both fit -> min(50, 60) = 50 in (400 e); + 4.5 = 54.5 in (436 e); qy = ceil(436 / 72) = ceil(6.06) = 7 -> 1 3/4 yd

V-WIDE-10  standard sizes (both dimensions fit, so length = the smaller dimension)
  crib 36 x 52:   min(44, 60) = 44 -> 48.5 in (388 e) -> ceil(5.39) = 6 qy -> 1 1/2 yd
  throw 50 x 65:  min(58, 73) = 58 -> 62.5 in (500 e) -> ceil(6.94) = 7 qy -> 1 3/4 yd
  twin 70 x 90:   min(78, 98) = 78 -> 82.5 in (660 e) -> ceil(9.17) = 10 qy -> 2 1/2 yd
  full 84 x 90:   min(92, 98) = 92 -> 96.5 in (772 e) -> ceil(10.72) = 11 qy -> 2 3/4 yd
```

### 4.6 Batting (o = 4 in per side)

A package fits when (bw <= pw and bh <= ph) or (bw <= ph and bh <= pw). Packages are tried in the
order crib 45 x 60, twin 72 x 90, full 90 x 96, queen 90 x 108, king 124 x 120.

```
V-BATT-01  fixture 75 x 90 -> 83 x 98
  crib: 83 > 60 both ways, no. twin: 83 > 72, and turned 98 > 72, no.
  full: 98 > 96, and turned 98 > 90, no. queen: 83 <= 90 and 98 <= 108 -> queen
V-BATT-02  crib 36 x 52 -> 44 x 60: crib (44 <= 45, 60 <= 60)
V-BATT-03  throw 60 x 72 -> 68 x 80: crib no (68 > 60); twin 68 <= 72, 80 <= 90 -> twin
V-BATT-04  throw 50 x 65 -> 58 x 73: crib no (58 > 45; turned 73 > 45); twin 58 <= 72, 73 <= 90 -> twin
V-BATT-05  twin 70 x 90 -> 78 x 98: twin no (78 > 72; turned 98 > 72); full no (98 > 96; turned 98 > 90);
           queen 78 <= 90, 98 <= 108 -> queen
V-BATT-06  full 84 x 90 -> 92 x 98: full no (92 > 90; turned 98 > 90); queen no (92 > 90; turned 98 > 90);
           king -> king
V-BATT-07  queen 90 x 108 -> 98 x 116: queen no (98 > 90; turned 116 > 90); king 98 <= 124, 116 <= 120 -> king
V-BATT-08  queen 92 1/2 x 115 -> 100 1/2 x 123: king upright no (123 > 120); turned 100.5 <= 120 and 123 <= 124 -> king (turned)
V-BATT-09  king 110 x 108 -> 118 x 116: king (118 <= 124, 116 <= 120)
V-BATT-10  102 1/2 x 120 -> 110 1/2 x 128: king no (128 > 120; turned 128 > 124) -> none:
           print "larger than a king package (124 x 120 in)"
V-BATT-11  68 x 68 -> 76 x 76: twin no (76 > 72 both ways); full 76 <= 90, 76 <= 96 -> full
V-BATT-12  tiny 6 x 6 -> 14 x 14: crib
V-BATT-13  42 x 52 -> 50 x 60: crib no (50 > 45; turned 60 > 45); twin 50 <= 72, 60 <= 90 -> twin
```

The batting dimensions already match today (`bridge.py:143-144`). The package line is new.

### 4.7 Standard sizes summary (defaults)

| Size | Backing (layout) | Today | Wide 108 | Binding | Today | Batting |
| --- | --- | --- | --- | --- | --- | --- |
| Crib 36 x 52 | 2 3/4 yd (2 x 44 in, horizontal) | 3 1/2 | 1 1/2 | (5) strips, 1/2 yd | 5, 1/2 | 44 x 60, crib |
| Throw 50 x 65 | 3 1/2 (2 x 58, horizontal) | 4 1/4 | 1 3/4 | (7), 1/2 | 6, 1/2 | 58 x 73, twin |
| Throw 60 x 72 | 4 1/4 (2 x 68, horizontal) | 4 1/2 | 2 1/4 | (8), 3/4 | 7, 1/2 | 68 x 80, twin |
| Twin 70 x 90 | 5 3/4 (2 x 98, vertical) | 5 1/2 | 2 1/2 | (9), 3/4 | 8, 3/4 | 78 x 98, queen |
| Full 84 x 90 | 8 (3 x 92, horizontal) | 8 1/4 | 2 3/4 | (10), 3/4 | 9, 3/4 | 92 x 98, king |
| Queen 90 x 108 | 8 1/2 (3 x 98, horizontal) | 9 3/4 | 3 1/2 | (11), 1 | 10, 3/4 | 98 x 116, king |
| Queen 92 1/2 x 115 | 8 3/4 (3 x 100 1/2, horizontal) | 10 1/4 | 3 3/4 | (12), 1 | 11, 1 | 100 1/2 x 123, king |
| King 110 x 108 | 10 (3 x 116, vertical) | 9 3/4 | none (3 1/2 at 118 in) | (12), 1 | 11, 1 | 118 x 116, king |

The crib, throw 50 x 65, twin, full, queen 90 x 108 and king 110 x 108 rows are QREP's presets
(`qrep/viewer/sizing.py:15-22`). The 60 x 72 throw and 92 1/2 x 115 queen are the two planning
cases (section 4.4).

### 4.8 Triangle and stitch-and-flip units

```
V-TRI-01  half-square triangle, exact, F = 2 in (16 e)
  square = 2 + 7/8 = 2 7/8 in (16 + 7 = 23 e), one of each fabric; 2 units per pair

V-TRI-02  half-square triangle, oversize and trim, F = 2 in
  square = 2 + 1 = 3 in (24 e); trim each unit to 2 + 1/2 = 2 1/2 in (20 e)

V-TRI-03  half-square triangle, eight at a time, F = 3 in (24 e)
  square = 2 x (3 + 7/8) = 2 x 3.875 = 7.75 in = 7 3/4 in (2 x 24 + 14 = 62 e); 8 units per pair

V-TRI-04  quarter-square triangle (two-fabric hourglass), F = 3 in
  exact: square = 3 + 1 1/4 = 4 1/4 in (24 + 10 = 34 e); 2 units per pair
  trim:  square = 3 + 1 1/2 = 4 1/2 in (36 e); trim each unit to 3 1/2 in (28 e)

V-TRI-05  flying geese, stitch and flip, finished 2 x 4 in
  goose rectangle = (2 + 1/2) x (4 + 1/2) = 2 1/2 x 4 1/2 in (20 x 36 e)
  sky squares = 2 at 2 + 1/2 = 2 1/2 in (20 e)

V-TRI-06  flying geese, four at a time, finished 2 x 4 in
  goose square = 4 + 1 1/4 = 5 1/4 in (32 + 10 = 42 e)
  sky squares = 4 at 2 + 7/8 = 2 7/8 in (16 + 7 = 23 e); 4 geese per set

V-TRI-07  snowball, F = 6 in, corner leg c = 2 in
  base square = 6 + 1/2 = 6 1/2 in (52 e); corner squares = 4 at 2 + 1/2 = 2 1/2 in (20 e)

V-TRI-08  yield into yardage: 48 half-square triangles, F = 2 in, exact, U = 40
  squares per fabric = ceil(48 / 2) = 24, cut 2 7/8 in (23 e)
  per strip = floor(40 / 2.875) = 13 (320 // 23 = 13, because 13 x 23 = 299 <= 320 < 322 = 14 x 23)
  strips = ceil(24 / 13) = ceil(1.846) = 2; length = 2 x 2 7/8 = 5 3/4 in (46 e)
  last strip = 24 - 1 x 13 = 11 squares

V-TRI-09  odd count: 7 half-square triangles, two at a time
  squares per fabric = ceil(7 / 2) = 4, which make 8 units (1 spare)
```

## 5. Cross-checks

### 5.1 Recorded calculator values

They come from the sprint-5 calculator research and the planning cases (section 4.4). They are
context for reviewers, never the source of an assertion; D2 and D7 measure the live calculators
(section 5.2).

| Vector | QREP new (default) | Recorded values | Note |
| --- | --- | --- | --- |
| V-BACK-02 throw 60 x 72 | 4 1/4 yd (136 in + 9) | Planning case: 3 7/8 yd (calculator not named). Seam-blind at 40 in (MSQC, C&T method): 136 in = 3 7/8 (1/8 rounding) or 4 (1/4). Quilter's Paradise seam-aware at 40 in: 160 in = 4 1/2. At 42 in: 136 in = 3 7/8 or 4; C&T +9 in: 4 1/8 or 4 1/4 | Equals C&T at 42 in with 1/4 rounding. Policy D reproduces 3 7/8 |
| V-BACK-01 queen 92 1/2 x 115 | 8 3/4 yd (301 1/2 + 9) | Planning case: 8 3/8 yd. Its calculator was not recorded | Inference, not a recorded value: 301 1/2 in is exactly 8 3/8 yd, which fits a seam-aware calculator at 42 or 43 in with 4 in per side, no allowance and 1/8 yd rounding (for example Quilter's Paradise with its 43 in default and 4 in overage). Hand arithmetic with MSQC's seam-blind method at 40 in gives 369 in = 10 1/4 yd, today's value. Policy D reproduces 8 3/8 |
| V-BACK-07 queen 90 x 108 | 8 1/2 | 294 in = 8 1/4 at 40 and 42 in; C&T +9 in: 303 in = 8 1/2; Linda's 108 in article cites 9 3/4 or 8 1/4 yd (second hand) | Equals C&T |
| V-BACK-09 fixture | 5 3/4 | At 42 in: 196 in = 5 1/2; C&T: 205 in = 5 3/4. At 40 in: 249 in = 7; C&T: 258 in = 7 1/4 | Equals C&T at 42 in |
| V-BACK-11 42 x 52 | 3 1/4 | 100 in = 2 7/8 or 3; C&T: 109 in = 3 1/8 or 3 1/4 | Equals C&T at 1/4 |
| V-BACK-23 58 x 66 | 4 | MSQC worked example: 4 1/4 (vertical, 148 in) or 3 3/4 turned (132 in) | MSQC turned plus the 1/4 yd allowance |
| V-UNIT-06 | 2 and 3 panels | Quilter's Paradise published 52 x 96 on 43 in: 2 and 3 panels (5 1/3 and 4 1/3 yd) | Panel rule matches |
| V-WIDE-02 60 x 72 | 2 1/4 | 80 in = 2 1/4; rotated 68 in = 2 (no allowance) | The allowance takes 68 in past 2 yd |
| V-WIDE-04 queen 90 x 108 | 3 1/2 | 116 in = 3 1/4 (Linda's: about 3.25) | The allowance crosses a 1/4 yd step |
| V-WIDE-08 fixture | 2 1/2 | 98 in = 2 3/4; rotated 83 in = 2 3/8 or 2 1/2 | Rotated match at 1/4 |
| V-WIDE-09 42 x 52 | 1 3/4 | 60 in = 1 3/4; rotated 50 in = 1 1/2 | The allowance crosses a 1/4 yd step |
| V-BIND-01 fixture | (10), 3/4 | Plain +10 / 40: 9 strips, 5/8 or 3/4; Quilter's Paradise at 40 in: 10 strips, 3/4; Nebraska Quilt Company: 7/8 | Quilter's Paradise strip count matches |
| V-BIND-13 60 x 72 | (8), 3/4 | QuiltSocial worked example: 274 in, 7 strips, 1/2 yd (no join loss); Quilter's Paradise at 40 in: 8 strips, 5/8; MSQC +20 in: 8 strips | Quilter's Paradise strip count matches |
| V-BIND-16 queen 90 x 108 | (11), 1 | 11 strips at 40 in, 7/8 or 1; at 42 in plain 10, Quilter's Paradise 11 | Matches at 1/4 |
| V-BIND-10 42 x 52 | (6), 1/2 | Plain +10 / 40: 5 strips; Quilter's Paradise: 6 strips, 1/2 yd | Quilter's Paradise matches |
| V-BIND-18 58 x 66 | (7), 1/2 | MSQC worked example: 268 / 40 = 6.7 -> 7 strips, 1/2 yd | Matches |
| V-BORD-01 fixture | 10 strips at 40 in (42 1/2 in); 8 at 42 in | Quilter's Paradise pooled (finished lengths): 8 strips, 34 in, 1 yd at 40 and 42 in; lengthwise: 83 in = 2 3/8 or 2 1/2 yd | Per-piece costs 2 more strips at 40 in (Q6) |
| V-TOP-01, V-TOP-02 fixture | blue 126 in; cream 166 1/2 in | Strip-yield at 40 in: blue 126 in = 3 1/2 yd; cream 158 in (pooled 34 in border) = 4 1/2 yd | Same square strips. The border differs by the pooled vs per-piece rule. QREP adds 10 percent |
| V-SET-01 | 20 per set; 5, 5, 3, 5, 8 | Same | Matches |
| V-UNIT-05 | 20/21, 16/16, 11/12 | Same | Matches |
| V-BATT-01, -03, -07, -13 | queen; twin; king; twin | Same packages | Matches |

### 5.2 Live calculators for calculator conformance (D2 and D7)

D2 drives these calculators with Playwright to record a baseline of today's math, and D7 repeats
the run after A1, A2 and A4 merge. All five were opened on 2026-10-07. Four fetched pages showed
their form inputs. The Quilter's Paradise border page describes its inputs, but the fetched HTML
did not show the form fields, so D2 confirms it in a real browser first. The five come from three
vendors; two web searches for more vendor calculators returned only spam pages, so D2 may add one
if it finds a genuine page.

| Calculator | URL | Inputs and behavior | How to drive it |
| --- | --- | --- | --- |
| Quilter's Paradise Backing and Batting | https://www.quiltersparadiseesc.com/Calculators/Backing%20and%20Batting%20Calculator.php | Bolt width (default 43 in), quilt width and length, overage per side (default 0); adds 1 in per seam; tries both orientations; rounds up to 1/8 yd (its rounding also has 1/3 steps) | Bolt 42 (also 40), overage 4. It shows both orientations: compare QREP's kept layout with its result for the same orientation and expect the same panel count. Expect yards equal to ceil(length_needed / 36 e) eighths of a yard, except where its 1/3 steps apply: when the length in yards (length_needed / 288 e) has a fractional part in (1/4, 1/3] or (5/8, 2/3] it may show a third. At 42 in that covers full 84 x 90 (276 in, 7 2/3), 102 1/2 x 120 (384 in, 10 2/3) and 58 x 66 (132 in, 3 2/3); record those as rounding differences. King 110 x 108 (348 in) is also exactly 9 2/3 yd, but the calculator's floating-point fraction lands just above 2/3, so it shows 9 3/4, the same as the eighths rule (its rounding script, read and simulated 2026-10-07). On 24 x 58 its smaller raw length is the two-panel layout, while F10 keeps one panel on the total (V-BACK-14). Known difference: QREP adds the allowance and rounds to 1/4 yd |
| Quilter's Paradise Binding | https://www.quiltersparadiseesc.com/Calculators/Binding%20Calculator.php | Fabric width (default 43 in), quilt width and length, strip width (1 1/2 to 4 in); outputs strips and yards, plus bias binding | Width 40, strip 2 1/2. Expect the same strip count as F7 (same formula); yards differ only by the increment |
| Quilter's Paradise Border | https://www.quiltersparadiseesc.com/Calculators/Border%20Calculator.php | Fabric width (default 43 in), quilt size, up to 5 borders, end-to-end or diagonal joins, mitered option; adds 1/2 in to border widths; rounds up to 1/8 yd; pools all strips | Width 40, end to end, not mitered. Record its count; it is at or below QREP's per-piece count (fixture: 8 vs 10) |
| My Favorite Quilt Store Backing and Batting | https://myfavoritequiltstore.com/toolbox/backing-calculator | Quilt length and width, overage per side, backing fabric width, batting type (shrinkage); least-fabric direction; internals undocumented | Width 42, overage 4. Record only |
| Nebraska Quilt Company Backing and Binding | https://www.nebraskaquiltcompany.com/pages/backing-binding-calculator | Quilt width and length; backing width 40, 60, 80, 90, 108 or 118 in (no 42); assumes +8 in overage and 1/2 in loss per seam; rounds up to 1/4 yd; shows vertical and horizontal layouts; binding from 2 1/2 in strips at 40 in | Width 40 (compare with QREP at B = 40, configured), then 108 and 118. Known differences: 1/2 in seam loss (QREP 1 in) and no allowance |

Not usable: Linda's backing fabric yardage guide (https://lindas.com/pages/backing-fabric-yardage-calculator-guide)
is a static chart with no inputs (checked 2026-10-07). The Quilter's Paradise piece count page (F2)
was recorded during the calculator research but not re-opened on 2026-10-07; D2 uses it for
strip-yield spot checks if it loads.

Size matrix: the eight rows of section 4.7, plus the fixture 75 x 90, 42 x 52, 76 x 85, 68 x 68,
102 1/2 x 120, 58 x 66 and 24 x 58. D2 runs it once as a baseline before the math lands, and D7
runs it again after. Each records its results with URL and date in its report, and the numbers
fill the calculator scorecard of the overnight report. A disagreement is investigated against the
hand arithmetic and is never resolved by copying the calculator.

### 5.3 Private reference comparison (aggregate only)

These aggregates come from the planning audit's comparison with the private reference patterns.
Per-pattern details stay private and are never committed; D6 runs the full reference-pattern
comparison and reports aggregates only.
- Backing: of the five printed or derived backing figures that work on the fabric each reference
  states (three references; one figure is derived from a partial page), the default rule matches
  two exactly (one pieced, one wide-back) and lands 1/4 yd below a third. The other two assume
  about 2 in of overhang; the rule with the 2 in domestic setting lands within 1/4 yd of both. Two
  more printed figures cannot back their quilts on the stated fabric and were not used.
- Binding: four of four printed yardages for one reference match. One printed strip count is one
  strip below the join-aware count; it closes the loop but leaves less than half of the 10 in
  extra. One reference uses a different binding method (scrappy pieces joined with straight
  seams) and is not counted; its one-print alternative figure is 1/8 yd above the rule.
- Top fabric: the strip-yield rule reproduces one reference's printed strip count exactly at 42 in,
  and with the 10 percent margin lands 0.2 in above another reference's printed yardage. Today's
  area method falls short of both.
- Borders: cut lengths match one reference exactly, and the per-piece strip count matches
  another's printed border strip count.

## 6. Open questions for Jake

Q2, Q3, Q4, Q6 and Q7 change expected values when answered against the default, so decide them
before A1 and A2 start. If there is no answer, the defaults in this file stand.

- Q1. Jake's mother's exact case, the reported over-estimate: quilt size, QREP's backing number,
  which calculator, and its number. It becomes V-MOM-01, a failing hand-computed test written
  before the fix. She is not available (J16 in the plan), so D1 quilter-voice research stands in
  until Jake has the case.
- Q2. Backing allowance. Keep +1/4 yd for a pieced backing and +1/8 yd for a one-piece backing
  (default; 8 3/4 and 4 1/4 yd for the two planning cases), or drop it (8 1/2 and 4 yd at 1/4 yd
  rounding)? The default sits 3/8 yd above the planning cases' calculator figures. See the policy
  table in section 4.4.
- Q3. Purchase increment: 1/4 yd (the audit's recommendation and the default) or 1/8 yd (the
  increment Quilter's Paradise rounds to; PATTERN-SPEC X-03 and L-02 record the same choice)? With
  1/8 yd and no allowance, both planning cases reproduce the calculator figures exactly (8 3/8 and
  3 7/8 yd). Changing the increment renames the `quarter_yards` field and changes every expected
  purchase value.
- Q4. Quilt-top margin of 10 percent (default)? On the fixture, cream is 5 1/4 yd with it and
  4 3/4 yd without it. A floor of at least 4 in per fabric is also proposed (PATTERN-SPEC X-06 and
  L-01): purchase = max(ceil(length x 110 / 100), length + 32 e). The default has no floor. A floor
  changes only small lines: V-TOP-04 white becomes max(49, 44 + 32) = 76 e -> 2 qy = 1/2 yd instead
  of 1/4 yd.
- Q5. Overhang: 4 in per side (longarm, default). Should the UI offer the 2 in domestic option? It
  gives 8 1/2 and 4 yd for the two planning cases (V-BACK-21, V-BACK-22). If Jake's mother quilts
  on a home machine, 4 in may be part of why the backing looked too big.
- Q6. Borders: per-piece joins (default; never short; at most three more strips per band than
  pooled, for example 8 against 5 for a 37 3/4 x 39 3/4 in center with a 1 in border, where all four
  pieces are 40 1/4 in) or pooled "join all, then cut four borders" (fixture: 9 strips instead of 10
  at 40 in)? This file picks per-piece for both the count and the wording, and PATTERN-SPEC words
  borders per piece too (S4 and X-05); Quilter's Paradise pools (F4). If Jake picks pooled, F4
  switches to the pooled count N = ceil((sum of piece lengths - 1/2) / (U - 1/2)) and the
  PATTERN-SPEC wording switches with it. Mixing the two is unsafe.
- Q7. Does "42 in backing" mean 42 in after trimming selvages? Two cases sit on that edge: the
  75 x 90 fixture has 0 in slack at 42 in, and 76 x 85 needs three panels at 42 in but two at 43 in.
  Also decide whether saved projects that store `wof: 336` migrate to 40 in on load. The printed
  sentences follow the answer: section 1.5 item 5 states the backing width, and item 2 calls the
  40 in strip width a planning figure, so it holds either way (PATTERN-SPEC S3 rule 5 words it
  the same way, with no tie to trimmed selvages).
- Q8. Confirm that the construction method caps merged runs at U, so no center piece is longer than
  one strip (PATTERN-SPEC owns this in M-04; F2 has a fallback).
- Q9. Triangle units: F14 gives both an exact and an oversize-and-trim cut for half-square and
  quarter-square triangles. PATTERN-SPEC picks one per unit type; the trim versions are more
  forgiving and cost 1/8 in to 1/4 in more per square. Hourglass units from three or four fabrics
  are not covered yet.
- Q10. Smaller choices with defaults: vertical seams win ties (Nebraska prefers horizontal seams on
  a longarm); the wide-back line appears only when the pieced backing needs two or more panels;
  118 in wide-back is a setting, not a second printed line; directional backing prints are out of
  scope. A tie can pair different panel counts: an 82 x 52 quilt needs three 60 in panels with
  vertical seams or two 90 in panels with horizontal seams, 180 in either way, and the default
  keeps the layout with one more seam. Should fewer panels win a tie before seam direction? No
  vector in section 4 changes either way.
- Q11. Batting: print the package class with its dimensions and no brand (default)?

## 7. Verification

- Expected values come from hand computation. Every value in section 4 was worked by hand, from the
  section 2 formulas or, for "today" values, from the current code's formulas, and its steps are
  written beside it so a test can carry them in a comment. No expected value comes from running
  QREP, and no calculator value is the source of an assertion (section 5).
- Four independent recomputation rounds checked this file on 2026-10-07. In each round a newly
  written scratch script that does not import qrep recomputed the section 4 values in integer
  eighths: all 92 vector ids, the policy table in section 4.4 and the summary table in section 4.7.
  The scripts for rounds 2 to 4 were written without reading the earlier ones. Every round found
  0 value mismatches.
- The rounds also checked the written steps (ceil, floor, products, sums and unit conversions;
  about 700 steps per round in rounds 2 to 4) and compared the formulas and the section 5 values
  with the recorded calculator research and the planning audit. Rounds 2 to 4 re-read the code
  behind the "today" values at 834d8be, and the last round confirmed that every repository path in
  backticks exists at that commit.
- The section 5.2 statements about Quilter's Paradise rounding come from reading the calculator's
  script and simulating its display in IEEE double arithmetic over the size matrix.
- No round changed a section 4 value. The rounds corrected wording, worked steps,
  cross-references and a few claims outside section 4 (for example the F2 crossover ranges and the
  Q6 bound), and strengthened two vectors: V-UNIT-02 gained the 200 e case that catches a
  floating-point margin, and V-BIND-08 gained part (b), where the strip width changes the strip
  count. The fourth round corrected wording only.
