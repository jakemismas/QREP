# D1: Quilter-voice research

| Item | Value |
| --- | --- |
| Date | 2026-10-10 |
| Ticket | D1, issue #161 (parent #104) |
| Command | None that runs QREP. Web research with WebSearch and WebFetch, plus one headless Chromium session (Playwright from `web/node_modules`) for the Reddit and X attempts and the Webster 1915 text |
| qrep imported from | `C:\Users\Jake Mismas\qrep-wt\d1\qrep\__init__.py` (not called; no QREP number is measured here) |
| git HEAD | 9030fdede146b1c23fea8dc15cb68f1a3fc0173b |
| Inputs | The query log, source list and claim ledger in [D1-sources.json](D1-sources.json): 132 queries, 148 fetched pages (125 ok, 23 failed), 159 claims (1 excluded) |
| Companion | [D1-review-rubric.md](D1-review-rubric.md), the rubric the D8 panel scores a PDF against |

Cited quilter voices stand in for the review and the discrepancy case that Jake's mother cannot
give (plan J16). Every bracketed id such as [S-A03] is a source in D1-sources.json, fetched on
2026-10-10, with its URL there. Everything below is paraphrased; no page is quoted and no
individual poster is named. Calculator and quilter figures are recorded cross-checks, never the
source of an assertion (MATH.md rule 3), and this report changes no MATH.md vector and no
PATTERN-SPEC check.

## 1. Findings

1. Quilters' published charts disagree with each other more than with MATH.md. For the same quilt
   they assume 40, 42 or 44 in fabric, 2 to 8 in of overhang per side, 1/8 yd, 1/4 yd or half-yard
   rounding, and +10 to +20 in of binding extra (section 3).
2. The most-cited shop guide for backing divides by 40 in and prices one seam direction [S-A03].
   It reproduces QREP's current backing numbers (crib 3 1/2 yd, throw 50 x 65 4 1/4 yd, full
   8 1/4 yd), so a quilter checking QREP's new numbers against it will see QREP lower (DIS-01,
   DIS-02).
3. No fetched source shows a quilter complaining that a calculator or pattern over-estimated
   backing. Six sources show why the numbers run high: stacked buffers, and quilters who would
   rather be half a yard over than two inches short (section 5, category 1). The reported
   over-estimate (MATH.md Q1) stays unconfirmed by outside voices.
4. Running short is the louder complaint (8 sources), and some published charts under-buy. By
   hand arithmetic at their own stated widths and overhangs, four rows of one backing chart and
   one row of another cannot cover the quilt they name (DIS-03), two charts offer 108 in wide
   backing for a king it cannot span (DIS-04), and two binding figures buy 1/2 in less fabric than
   their own strip count uses (DIS-06). These support MATH.md's seam-aware panel count (F9), its omission of a 108 in line
   for a king (F11, V-WIDE-05) and its strips-times-width binding line (F7).
5. Wrong cut sizes are the most common printed pattern error: about 40 percent of one magazine's
   corrections from 2005 to 2023 [S-B03]. Quilters respond by checking the arithmetic, making a test
   block and looking for corrections pages (sections 5 and 7).
6. The most-made traditional squares and triangle quilts in the evidence are the nine patch, the
   Irish chain, half-square triangle quilts, flying geese and the four patch; log cabin ties with
   the last three but has no quilter's method in 0.4.0. A straight-set Double Irish Chain is the strongest
   release-demo candidate (section 6).
7. Reddit and X could not be read. Both refused every automated request, so the quilter voice here
   comes from forums (QuiltingBoard and The Quilt Show), designer and shop blogs, publishers and
   calculator sites (section 2).

## 2. Method and coverage

Four research passes ran in one session, one per topic (A finishing numbers, B complaints, C
most-made quilts and name sources, D pattern trust and clarity), each fetching one page at a time,
with no login, posting, sign-up or contact, and no API, JSON, sitemap or listing pages. Fourteen
sources that later sections rely on were fetched a second time to check the claims drawn from them
(D1-sources.json, `spot_checks`); one survey percentage and one name list were corrected that way,
and one claim from a knitting source was excluded.

Result count is the number of result blocks the search tool returned for a query, not the engine's
total hit count.

| Source group | Queries | Results returned | Queries with 0 results | Pages fetched ok |
| --- | --- | --- | --- | --- |
| r/quilting and related subreddits | 27 | 174 | 8 | 0 |
| X | 8 | 64 | 1 | 0 |
| Forums | 20 | 184 | 0 | 13 (QuiltingBoard 12, The Quilt Show 1) |
| Designer, shop and publisher blogs | 62 | 583 | 0 | 88 (designer 27, shop 43, publisher 18) |
| Calculator sites | 14 | 147 | 0 | 12 |
| Public-domain books | 1 | 10 | 0 | 5 (one work) |
| Other pages (extension office, magazines, newsletters), from the queries above | | | | 7 |

All 125 ok pages come from 56 distinct sites. The search tool refuses reddit.com as a domain
filter, and the Reddit-group queries without the filter returned only non-Reddit pages. WebFetch
refuses reddit.com. One headless Chromium session got a network-security block page from both
www.reddit.com and old.reddit.com, and HTTP 403 from x.com search, which needs a login (Q-M01 to
Q-M03). The `site:x.com` searches returned no x.com pages. No workaround was tried, so Reddit and X
contribute no claim. Four forum fetches (Quilt in a Day and a Tapatalk group) returned HTTP 403.

## 3. Standard sizes: what quilters and calculator sites state

The MATH.md column copies section 4.7 at its defaults: 42 in backing width, 4 in overhang per
side, 1 in per backing seam, +9 in (pieced) or +4 1/2 in (one piece) allowance, 1/4 yd rounding;
binding 2 1/2 in strips at 40 in usable width, +10 in, join-aware. "Today" is QREP's current value
from the same table. Each stated figure carries the source's own size and assumptions; "exact"
means the source uses the same dimensions. No source states a figure for the 92 1/2 x 115 queen.

### 3.1 Backing, pieced

| Size | MATH.md (today) | Stated figures |
| --- | --- | --- |
| Crib 36 x 52 | 2 3/4 yd, 2 x 44 in horizontal (3 1/2) | Exact: 3 1/2 yd, 2 widths, 40 in usable, 4 in per side, 1/4 yd, one seam direction [S-A03]. Exact: 2 3/4 yd, 2 strips, 42 in, 4 in per side [S-A38]. Exact: 1 5/8 yd, 1 panel, 42 to 44 in, 6 to 8 in total [S-A02]. 40 x 50: 2 1/2 to 3 yd, 44 in [S-A08]. 45 x 60: 4 yd, 44 in [S-A15] |
| Throw 50 x 65 | 3 1/2, 2 x 58 horizontal (4 1/4) | Exact: 4 1/4 yd, 2 widths, 40 in, 4 in per side [S-A03]. 50 x 60: 2 1/4 yd, 1 panel [S-A02] |
| Throw 60 x 72 | 4 1/4, 2 x 68 horizontal (4 1/2) | Exact: 4 to 4 1/2 yd, 44 in [S-A08]. 60 x 70: 4 3/4 yd, 44 in [S-A15] |
| Twin 70 x 90 | 5 3/4, 2 x 98 vertical (5 1/2) | Exact: 6 yd, 44 in [S-A15]. Exact: 5 yd, 2 panels [S-A02]. 68 x 86: 5 1/4 yd [S-A03]. 60 x 80: 5 yd, 44 in [S-A08]; 5 yd, 2 widths of 90 in, 40 to 42 in usable, 5 in per side, +1/4 yd [S-A16] |
| Full 84 x 90 | 8, 3 x 92 horizontal (8 1/4) | Exact: 8 1/4 yd, 3 widths, 40 in [S-A03]. 85 x 108: 6 yd, 2 panels [S-A02]. 72 x 90: 5 1/2 yd, 44 in [S-A08] |
| Queen 90 x 108 | 8 1/2, 3 x 98 horizontal (9 3/4) | Exact: 8 3/8 yd, 3 strips of 98 in, 42 in [S-A38]. Exact: 6 yd, 2 panels [S-A02]. Exact: 6 to 6 1/2 yd, 44 in [S-A08]. Exact: pieced "not recommended", 44 in [S-A15]. 90 x 95: 8 3/4 yd [S-A03]. 90 x 90: 8 to 9 yd [S-A10] |
| Queen 92 1/2 x 115 | 8 3/4, 3 x 100 1/2 horizontal (10 1/4) | Not found |
| King 110 x 108 | 10, 3 x 116 vertical (9 3/4) | 108 x 108: 9 7/8 yd, 42 in [S-A38]; 9 yd, 3 panels [S-A02]; 9 1/2 to 10 yd, 44 in [S-A08]. 110 x 110: pieced "not recommended" [S-A15]. 108 x 95: 8 3/4 yd [S-A03] |

General statements: 4 in per side is the most common overhang (8 sources, claim C-A43); longarm
requests run from 3 to 8 in per side, home machines 2 to 4 [S-A07, S-A17, S-A16, S-A31, S-A26,
S-A32, S-A14, S-A25]. Backing seams are 1/2 in and pressed open [S-A03, S-A14, S-A16, S-A35,
S-A37]. Usable width: 40 in is the most conservative and most-cited planning figure, 42 in is
common in calculators, and one uses 43 1/2 in [S-A03, S-A27, S-A35, S-A16, S-A37, S-A38, S-A36].
Allowances: C&T adds 9 in for a pieced backing [S-A27]; others add 1/8 to 1/4 yd or 5 to 15
percent for shrinkage and squaring [S-A16, S-A36, S-A38, S-A10].

### 3.2 Backing, wide (108 in)

| Size | MATH.md | Stated figures |
| --- | --- | --- |
| Crib 36 x 52 | 1 1/2 yd | Exact: 1 3/4 yd, not turned [S-A03]. 40 x 50: 1 1/2 yd [S-A08]. 45 x 60: 2 yd [S-A15] |
| Throw 50 x 65 | 1 3/4 | Exact: 2 1/4 yd, not turned [S-A03] |
| Throw 60 x 72 | 2 1/4 | Exact: 2 1/2 yd [S-A08]. 60 x 70: 2 1/2 yd [S-A15]. Throw: 2 1/4 yd [S-A07, S-A26] |
| Twin 70 x 90 | 2 1/2 | Exact: 3 yd [S-A15]. 68 x 86: 2 3/4 yd [S-A03]. 60 x 80: 2 3/4 yd [S-A08]. Twin: 2 1/2 yd [S-A07, S-A26] |
| Full 84 x 90 | 2 3/4 | Exact: 2 3/4 yd [S-A03]. 72 x 90: 3 yd [S-A08]. Full: 3 yd [S-A07]; 2 3/4 yd [S-A26] |
| Queen 90 x 108 | 3 1/2 | Exact: 3 1/2 yd [S-A15, S-A08]. Exact: 2 7/8 yd, one 100 in strip [S-A38]. 90 x 95: 3 yd [S-A03]. 90 x 90: 3 yd [S-A10]. 92 x 96: 3 yd [S-A07] |
| Queen 92 1/2 x 115 | 3 3/4 | Not found |
| King 110 x 108 | None at 108 in (3 1/2 at 118 in) | 110 x 110: 3 1/2 yd [S-A15]. 108 x 108: 3 1/2 yd [S-A08]. 108 x 95: 3 1/4 yd [S-A03]. 100 x 100: 3 yd [S-A07]. King, size not stated: 3 to 3 1/2 yd [S-A12, S-A13] |

One calculator offers 118 in wide backing [S-A35] and one guide mentions it [S-A26]; neither gives a
yardage (C-A25).

### 3.3 Binding

| Size | MATH.md (today) | Stated figures |
| --- | --- | --- |
| Crib 36 x 52 | (5) strips, 1/2 yd (5, 1/2) | 45 x 45: 5 strips, 3/8 yd, 42 in, +10 in [S-A04]. Exact: 1/2 yd [S-A05] |
| Throw 50 x 65 | (7), 1/2 (6, 1/2) | Throw: 1/2 yd, +20 in [S-A30] |
| Throw 60 x 72 | (8), 3/4 (7, 1/2) | Exact: 7 strips, 1/2 yd, 42 in, +10 in [S-A04]. Exact: 8 strips, 5/8 yd, 40 in, +20 in [S-A29]. 60 x 70: 6.8, so 7 strips, 40 in, +12 in [S-A15] |
| Twin 70 x 90 | (9), 3/4 (8, 3/4) | 67 x 99: 9 strips, 5/8 yd [S-A04]. Exact: 1 1/4 yd [S-A05]. Twin: 2/3 yd [S-A30] |
| Full 84 x 90 | (10), 3/4 (9, 3/4) | 82 x 96: 9 strips, 5/8 yd [S-A04] |
| Queen 90 x 108 | (11), 1 (10, 3/4) | Exact: 11 strips, about 3/4 yd, 40 in, +12 in [S-A40]. 88 x 104: 10 strips, 3/4 yd [S-A04]. 90 x 90: 3/4 yd, +15 to 20 in [S-A10]. Queen: 3/4 yd [S-A30] |
| Queen 92 1/2 x 115 | (12), 1 (11, 1) | Not found |
| King 110 x 108 | (12), 1 (11, 1) | 106 x 108: 11 strips, 3/4 yd [S-A04]. King: 7/8 yd [S-A30] |

One shop guide's binding yardages run well above every other source (1 1/4 yd for a twin, 2 yd for
a king) [S-A05]; it is recorded but not counted as typical. General statements: +10 in [S-A04,
S-A43], +12 in [S-A40, S-A15], +15 to 20 in [S-A10] and +20 in [S-A21, S-A29, S-A30]; usable width
40 in for binding in most sources; 2 1/2 in strips in shop guides and 2 1/4 in in a forum thread and
an extension guide [S-A40, S-A30, S-A41, S-A43, S-A29]; strips joined on the diagonal [S-A29,
S-A43].

### 3.4 Batting

| Size | MATH.md (F12) | Stated figures |
| --- | --- | --- |
| Crib 36 x 52 | 44 x 60, crib | Crib package 45 x 60 [S-A25, S-A23, S-A06] |
| Throw 50 x 65 | 58 x 73, twin | Twin package 72 x 90 [S-A25, S-A23, S-A06] |
| Throw 60 x 72 | 68 x 80, twin | As above |
| Twin 70 x 90 | 78 x 98, queen | One chart pairs a 70 x 90 top with the 72 x 90 twin package, leaving 1 in or less of overhang, against its own 3 to 4 in rule [S-A23] |
| Full 84 x 90 | 92 x 98, king | Full package 90 x 96 [S-A23, S-A06] or 81 x 96 [S-A25]; neither covers 92 x 98 |
| Queen 90 x 108 | 98 x 116, king | The same chart pairs the 90 x 108 queen package with a 90 x 108 top [S-A23] |
| Queen 92 1/2 x 115 | 100 1/2 x 123, king (turned) | Not found. The king package is 124 x 120 for one brand [S-A06] and 120 x 120 in two package lists [S-A25, S-A23]; the second does not cover 100 1/2 x 123 |
| King 110 x 108 | 118 x 116, king | King package 120 x 120 or 124 x 120 [S-A25, S-A23, S-A06] |

General statements: batting is cut to the backing's size, the top plus about 4 in per side, or 6 to
8 in in total [S-A24, S-A17, S-A32, S-A25, S-A33]; one calculator gives 4 in per side for longarm
and 2 in for home quilting, and lists cotton batting shrinkage of about 4 percent [S-A25].

### 3.5 Borders

MATH.md section 4.7 has no border column; F4 vectors exist for the crib (V-BORD-02), the
two-band 60 x 72 case (V-BORD-03) and the fixture (V-BORD-01). No source gives a border figure for
any 4.7 size, because borders depend on the design. The conventions quilters state, against F4:

| Convention | Sources | F4 |
| --- | --- | --- |
| Cut strip width is the finished width plus 1/2 in | [S-A18] | Same |
| Strips cut crosswise, planned at 40 in usable | [S-A18] | Same (U = 40) |
| Measure through the center, averaging three measurements, not along the edges | [S-A18, S-D08, S-D28] | Lengths from the inner size; PS-28 asks for a measure-and-trim instruction |
| Sides first, then top and bottom | [S-A18, S-D28] | Same |
| Add 1 in to each border length before trimming | [S-A19] | No extra beyond the 1/2 in seam allowance |
| Join border strips with diagonal seams | [S-A20] | Straight 1/4 in joins, 1/2 in per join (j) |
| Border width about a third to a half of the block size | [S-A19] | Not a math question (design) |

## 4. Disagreements for the A1 and A2 owners

A1, A2a and A2b have merged, so these go to their owners and to D7 as context. None changes a
vector; each names the MATH.md item it bears on.

- **DIS-01 (A1; Q7).** The most-cited shop backing guide plans on 40 in usable width ("divide by
  40, not 42") [S-A03], as do forum quilters [S-B12]; B is 42 in (J13). At 40 in that guide
  reproduces QREP's current crib, 50 x 65 throw and full figures (3 1/2, 4 1/4, 8 1/4 yd).
  Calculators use 42 to 43 1/2 in [S-A38, S-A37, S-A36], and older charts use 44 in [S-A08,
  S-A15].
- **DIS-02 (A1; F10).** The same guide's chart prices one seam direction and its text notes that
  crosswise seams can save half a yard on small quilts [S-A03]. F10 keeps the cheaper total, so
  QREP's new crib and throw numbers sit 3/4 yd below that chart. PS-12's seam-direction line is
  what tells the reader why.
- **DIS-03 (A1; F9).** Published backing rows that cannot cover their own quilt at their own
  width and overhang (hand arithmetic, inches):
  - [S-A02], 42 to 44 in, 6 to 8 in added: lap 50 x 60 on one panel needs at least 56 in of width
    (66 in turned), more than 44; full 85 x 108 on two panels needs at least 91 in, but two panels
    give at most 88; queen 90 x 108 on two panels needs at least 96 in, more than 88; twin 70 x 90
    on two panels needs 2 x 96 = 192 in at 6 in added, but 5 yd is 180 in.
  - [S-A08], 44 in: queen 90 x 108 at 6 to 6 1/2 yd (at most 234 in). Its backing is 98 x 116,
    and two 44 in panels give at most 88 in, so it needs three panels: 3 x 98 = 294 in (8 1/6 yd)
    turned, or 3 x 116 = 348 in.
  These support the seam-aware panel count of F9 and the "running short" complaints (section 5).
- **DIS-04 (A1; F11, V-WIDE-05).** Two charts list 3 1/2 yd of 108 in fabric for a king whose
  stated backing is wider than 108 in both ways: 110 x 110 with a 118 x 118 backing [S-A15], and
  108 x 108 with 8 in added, 116 x 116 [S-A08]. F11 prints no 108 in line for the 110 x 108 king,
  which is correct; a finisher who expects one needs the footnote to say why (rubric R-07).
- **DIS-05 (A1; F6, F7).** Strip counts from charts that divide by 42 in with no join loss run
  one strip below F7 (60 x 72: 7 against 8) [S-A04]. Sources that divide by 40 in with +20 in
  match F7's count (60 x 72: 8) [S-A29]. Binding extra ranges from +10 to +20 in across 8 sources;
  t = 10 in is the low end, and the join-aware count adds the margin back.
- **DIS-06 (A1; F7).** Two binding figures buy less fabric than their own strip count uses:
  11 strips x 2 1/2 in = 27 1/2 in, priced at 3/4 yd = 27 in, in a 106 x 108 king row [S-A04]
  and a 90 x 108 queen example given as about 3/4 yd [S-A40]. F7 buys strips x w rounded up
  (1 yd at 1/4 yd rounding), so QREP's line is 1/4 yd higher on purpose.
- **DIS-07 (A1; Q3).** Rounding increments split: 1/4 yd [S-A03, S-A35, S-A21], 1/8 yd [S-A38,
  S-A36, S-A37, S-A04], and a half-yard tip [S-A08].
- **DIS-08 (A1; Q2).** Backing allowances: +9 in pieced [S-A27], +1/4 yd for shrinkage and
  squaring [S-A16], 5 to 15 percent [S-A36, S-A38, S-A10]. The default +9 in and +4 1/2 in sit at
  the low end of what quilters add.
- **DIS-09 (A1; F12, Q11).** The king batting package is 124 x 120 in one brand [S-A06] (F12's
  source) and 120 x 120 in two package lists [S-A25, S-A23]. Only V-BATT-08 (queen 92 1/2 x 115,
  100 1/2 x 123) depends on it: at 120 x 120 it is larger than a king. One chart pairs package
  names with same-named quilts and leaves no overhang [S-A23], while F12 picks a queen package for
  a 70 x 90 twin; PS-13 prints the package dimensions, which settles the naming for the reader.
- **DIS-10 (A1; Q5).** Overhang: 4 in per side is the consensus (8 sources); longarm requests run
  to 5 in [S-A16] and 6 to 8 in [S-A26], and home quilting to 2 to 4 in [S-A25, S-A14, S-A17].
  The default matches the consensus; the 2 in domestic option matches the home range.
- **DIS-11 (A2; F4).** Some quilters join border strips on the diagonal [S-A20], which uses about
  one strip width per join, not F4's 1/2 in; one guide adds 1 in to each border length [S-A19].
  F4's count holds only for straight joins, so the cut list must name the join type, as MATH.md
  section 1.5 item 8 and PS-28 require.
- **DIS-12 (A2; F2, F5).** No disagreement on U = 40: the 40 in planning width is the most common
  figure for strip cutting and binding [S-A03, S-B12, S-D32, S-A15, S-A40].

## 5. Complaint catalog

Counts are distinct fetched sources (pages or threads) per category; a page that two passes fetched
counts once. Each category names the MATH.md section 6 question or PATTERN-SPEC check it bears on.

| # | Category | Sources | What quilters say | Bears on |
| --- | --- | --- | --- | --- |
| 1 | Backing over-estimated | 6, all indirect | No direct complaint found. Calculators stack buffers (an extra 1/4 yd, about 1/2 yd when prewashing, shrinkage percents, 4 to 8 in of overhang) [S-B15, S-B16, S-B18, S-B35]; forum quilters say they would rather be half a yard over than two inches short [S-B36, S-B12] | Q1, Q2, Q5 |
| 2 | Running short | 8 | A published pattern listed backing and batting far below what the quilt needed [S-B02]; a monthly pattern was half a yard short on one fabric until the designer posted a corrected cutting sheet [S-B04]; errata pages correct yardage upward [S-B03, S-B39]; patterns written for 44 to 45 in fabric run short on today's 40 to 42 in, worst for newer quilters [S-B12]; a 79 in top could not get a one-piece backing at 40 in usable [S-B27, S-B26]; working out yardage after changing a pattern is hard [S-B01] | Q2, Q4, Q7, F9 |
| 3 | Width-of-fabric assumptions | 9 | Experienced quilters plan on 40 in even from fabric labeled 44 [S-B12, S-B36, S-B27]; calculators and publishers assume 40, 42 to 44 or a changeable 43 in [S-B15, S-B35, S-B16, S-B17, S-B18]; prewashing and trimming selvages take more [S-B06, S-B16, S-B18] | Q7, U = 40, B = 42 |
| 4 | Binding length and strip count | 4 | Strip count changes with strip width, and guides differ on the extra (+10 or +12 in) [S-B20, S-B34]; a calculator fixed at 2 1/2 in strips over 40 in gives a different count for another width [S-B15]; joining the ends is a step some need a video for [S-B01] | F6, F7 |
| 5 | Calculators disagree or hide assumptions | 5 | Overhang varies from 0 to 8 in, seams are handled differently, rounding goes to 1/8 yd in one and to 1/4 yd in another, and one tool says its results are only a starting point [S-B15, S-B16, S-B17, S-B18, S-B35] | Q2, Q3, Q5, Q7; PS-14 |
| 6 | Pattern errors and errata | 8 | Errata pages list wrong cut sizes, wrong counts, mislabeled diagrams and missing templates [S-B02, S-B03, S-B24, S-B39]; quilters find a wrong dimension after cutting everything [S-B10, S-B33]; they learn of corrections by searching or from a shop [S-B04, S-B10]; precut kit pieces 1/4 in off broke triangle units [S-B09] | PS-16, PS-19, PS-23 |
| 7 | Unclear instructions | 5 | Pressing direction, nesting and the scant 1/4 in confuse [S-B01]; patterns assume the buyer knows layering, quilting and binding [S-B11]; readers mistake unfinished for finished sizes [S-B13]; designers clarify assembly text and switch to cut-large-and-trim [S-B24, S-B28] | PS-15, PS-22, PS-29 |
| 8 | Cutting instructions | 3 | Wrong cut sizes are the most frequent correction in one magazine's record [S-B03]; cutting must be exact or nothing fits, and a pattern was revised to cut triangles oversized and trim [S-B01, S-B28] | PS-16, PS-23 (L-06) |
| 9 | Size mismatch | 4 | A finished size printed 20 in off [S-B28]; blocks finishing small from printer scaling, seam error or finished-versus-unfinished confusion [S-B13, S-B14]; kit pieces cut wrong [S-B09] | PS-07, PS-26, PS-38 |
| 10 | Format and print | 2 | Fit-to-page printing shrinks templates; print at 100 percent and measure the test box [S-B21, S-B13] | PS-38 |
| 11 | Longarm backing | 6 | Backing should be 8 to 10 in larger than the top [S-B05, S-B06, S-B23, S-B37, S-B38]; uneven or badly sewn seams and selvages in seams cause sag and puckers [S-B05, S-B06, S-B23]; seams pressed open; a short backing costs extra to extend [S-B38, S-B16] | Q5, F8, F9 |

Not found: complaints about tiny text, color-only diagrams, page counts or wasteful cutting layouts,
and any direct report of a binding that came out short.

## 6. Most-made traditional squares and triangle quilts

Ranked by the number of independent sites (fetched ok) that list the family as popular, a beginner
favorite or a classic (two pages from one site count once), then by its share in the trade-body
survey of over 1,000 quilters [S-C01]. The evidence is
lists, recommendations and one survey; no source counts finished quilts, and Reddit, where such
counts would come from, could not be read. Scope follows plan section 2.3.

| Rank | Family | Sites | Evidence | Units | 0.4.0 scope | Webster 1915 list |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Nine patch (and double nine patch) | 5 | Third favorite unit (32 percent) and the most common first block [S-C01]; common-block list [S-C02]; beginner list rank 2 [S-C11]; magazine top 10 [S-C17]; first-quilt workshop [S-C23] | Squares | In | Nine Patch |
| 2 | Irish chain (single, double) | 5 | Favorite [S-C14, S-C18]; finished, set on point [S-C15]; classic beginner quilt [S-C16]; magazine top 10 [S-C17]; throw tutorial [S-C26] | Squares, merged runs | In when set straight; on point is out | Double Irish Chain |
| 3 | Half-square triangle quilts (pinwheel, broken dishes, sawtooth) | 4 | Favorite unit, 53 percent [S-C01]; lists [S-C02, S-C11, S-C12] | Half-square triangles | In | Broken Dish, Pinwheel Square, Wind Mill, Sawtooth Patchwork, Bear's Paws |
| 4 | Flying geese | 4 | Second favorite unit, 33 percent [S-C01]; lists and tutorials [S-C02, S-C16, S-C27] | Stitch-and-flip corners (or HSTs) | In | Wild Goose Chase |
| 5 | Four patch | 4 | 18 percent [S-C01]; lists [S-C02, S-C11, S-C12] | Squares | In | New Four Patch |
| 6 | Log cabin | 4 | Popular write-in and second most common first block [S-C01]; lists [S-C02, S-C11, S-C12]; classic list on the same shop site as S-C11 [S-C16] | Log strips | Read, no quilter's method yet | Log Cabin |
| 7 | Rail fence | 3 | Rail unit 17 percent [S-C01]; first in two beginner lists [S-C11, S-C12] | Merged runs (bars) | In | Not listed |
| 8 | Simple squares, checkerboard, charm squares | 2 | Beginner lists [S-C11, S-C12] | Squares | In | Not listed |
| 9 | Bricks | 2 | Beginner lists [S-C11, S-C12] | Squares, merged runs | In | Brick Pile |
| 10 | Disappearing nine patch | 2 | Beginner list rank 3 [S-C11]; magazine top 10 [S-C17] | Squares, merged runs | In | Not listed |
| 11 | Hourglass and quarter-square triangle quilts | 2 | 11 percent [S-C01]; common-block list [S-C02] | Quarter-square triangles | In | Hour Glass |
| 12 | Ohio star | 1 | Stars won favorite block overall, Ohio star named most [S-C01] | Squares, QSTs | In | Not listed |
| 13 | Square in a square | 1 | 20 percent [S-C01] | Stitch-and-flip corners | In | Not listed |
| 14 | Churn dash | 1 | Classic list [S-C16] | Squares, HSTs | In | Churn Dash |
| 15 | Bow tie | 1 | Traditional roundup [S-C20] | Squares, stitch-and-flip corner | In | Not listed |
| 16 | Sampler | 1 | Historically as common as one-block quilts [S-C25] | Mixed | Case by case | Not applicable |

Not found as most-made: Trip Around the World, shoo fly, snowball and card trick (C-C24). Only the
Irish chain shows up often on point: one designer blog says single, double and triple chains all
work on point [S-C18], and one finished scrap quilt is on point [S-C15].

Candidates:
- **Corpus (D3a).** In-scope rows in rank order: straight-set Irish chains (single and double),
  nine patch and double nine patch, four patch and checkerboard, rail fence, bars and bricks, HST
  quilts (pinwheel, broken dishes, sawtooth, bear's paw), flying geese, hourglass and Ohio star,
  churn dash, and stitch-and-flip quilts (snowball, bow tie, square in a square) for the thin
  stitch-and-flip class. For the refusal tier, on-point Irish chains and on-point nine patches
  first, because they look like the top two in-scope families.
- **Examples gallery (C9).** A straight-set Double Irish Chain, a nine patch, a four patch or
  checkerboard, and one HST quilt (pinwheel or broken dishes), all families whose method plan
  section 2.3 lists as working. Not log cabin or Trip Around the World.
- **Release demo.** A straight-set Double Irish Chain: it ties for the top rank, it is a
  public-domain name [S-M02], and its method is the squares-and-merged-runs path that the repo
  fixture already exercises. If the demo shows triangle units too, add a pinwheel or broken dishes
  HST quilt. Whether a CC0 museum photo of either exists is D3a's call.

Name sources: the only name source cited is Marie D. Webster, Quilts: Their Story and How to Make
Them (1915). The Project Gutenberg ebook page states it is public domain in the USA [S-M01], and its
text carries a 1915 copyright line [S-M02]. Its alphabetical list was searched in full for the names
above. QUILT-1M, Hall and Kretsinger, the Quilt Index, the V&A and the International Quilt Study
Center were not used.

## 7. Quilter personas for D8

Three personas for the D8 panel, each built from the claims above. A reviewer playing one should
read the PDF in the order that persona checks first and score it with [D1-review-rubric.md](D1-review-rubric.md),
weighting the items marked for that persona.

### P1. Confident beginner

Has finished one or two quilts from beginner patterns such as rail fence, nine patch or four patch
[S-C11, S-C12]. Checks first: the fabric list, then the first cutting step.
- Mixes up finished, unfinished and cut sizes unless the pattern defines them once and uses them
  the same way throughout [S-D11, S-D29, S-B13].
- Needs the seam allowance stated, cut sizes that already include it, and a way to test the seam
  [S-D02, S-D34].
- Needs WOF, RST and HST defined before they appear [S-D18, S-D33].
- Expects a labeled drawing for each step and a stated pressing direction [S-D05, S-D15, S-B01,
  S-D29].
- Expects layering, quilting and binding to be included, not assumed [S-B11, S-D15].
- Follows yardage exactly, so runs short when a pattern assumes 44 in fabric [S-B12].
- Prints with the default fit-to-page setting unless told to print at 100 percent [S-D07, S-B21].
- Trusts skill and time labels and is told to double the time [S-D15, S-D17]; PS-05 leaves both
  out, so a panel finding that asks for them is recorded for Jake, not built.

### P2. Experienced traditional piecer

Has made many traditional quilts and has been burned by printed errors. Checks first: cut sizes
against finished sizes, then piece counts against the layout.
- Reads the whole pattern, does rough math, and makes a test block before cutting everything
  [S-D03, S-D11, S-D33].
- Knows wrong cut sizes are the most common printed error [S-B03] and has found one only after
  cutting [S-B10, S-B33].
- Wants strip-first cutting with per-strip yields, so the yardage can be checked by hand [S-D03].
- Prefers cutting triangle units oversized and trimming, with a stated trim-to size [S-D23,
  S-B28].
- Expects a size checkpoint after each unit, block and the quilt center, and squares up at each
  stage [S-D34].
- Expects a pressing plan that makes seams nest, and presses rather than irons [S-D12, S-D34].
- Expects diagram labels to match the cutting list exactly [S-D13].
- Wants to know which version they hold and where corrections are posted [S-D14, S-D37].

### P3. Finisher (backing, batting and binding)

Often sends quilts to a longarm quilter, or quilts at home on a domestic machine. Checks first: the
backing, binding and batting lines in the fabric list, then Finishing.
- Wants the overhang stated per side: 4 in is the norm, longarm quilters ask for 4 to 8 in, home
  quilting needs 2 to 4 [S-A03, S-D35, S-D20, S-A26, S-A25].
- Plans on 40 in usable width with selvages trimmed [S-A03, S-B12, S-B27].
- Wants a square backing with seams pressed open and selvages out of the seams [S-B05, S-B23,
  S-D35, S-B38].
- Wants the seam direction and the fabric saved by turning the backing [S-D10].
- Expects a wide-back option, and has seen charts offer one that cannot cover a king [S-A03,
  S-A26; DIS-04].
- Wants the binding strip width, strip count, join method, corner method and extra length stated
  [S-D31, S-A40, S-D21, S-A43].
- Wants the batting size with its overhang and the package that covers it [S-A25, S-D16].
- Would rather buy half a yard over than come up two inches short [S-B36, S-B12].

## 8. V-MOM-01

The slot stays open. Item O1 of the Jake queue comment on #104 (comment 6043683358) asks for the
quilt size, QREP's backing number, the calculator and its number; the orchestrator keeps that
comment, and this ticket does not edit it. No fetched source describes a matching over-estimate
case (section 5, category 1). When Jake supplies the case, A1 writes the failing hand-computed test
before any fix (MATH.md Q1).

## 9. Limits

- No Reddit or X content: both refused every automated request (section 2).
- Two sites supply several sources each (one shop blog with six pages, one publisher with six), so
  a few voices weigh more than their count suggests.
- The fetch tool summarizes pages. Fourteen sources were re-fetched and checked; the claims from
  the rest are as the research passes recorded them.
- The most-made ranking counts lists and recommendations, not finished quilts.
- Size figures rarely use MATH.md's exact dimensions; "nearest" rows are context, not
  like-for-like comparisons.
