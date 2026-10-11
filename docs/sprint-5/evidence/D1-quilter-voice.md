# D1: Quilter-voice research

| Item | Value |
| --- | --- |
| Date | 2026-10-10 (research); 2026-10-11 (review fixes, with no new fetch) |
| Ticket | D1, issue #161 (parent #104) |
| Command | None that runs QREP. Web search and page fetches, plus headless Chromium (Playwright from `web/node_modules`) launched four times, one browser at a time: once for each of the three Reddit and X search pages, and once for the two Webster 1915 pages |
| Research base | 9030fdede146b1c23fea8dc15cb68f1a3fc0173b (origin/main when the research ran; no QREP number is measured here) |
| Inputs | The query log, source list and claim ledger in [D1-sources.json](D1-sources.json): 132 queries (123 searches run, 6 refused by the search tool, 3 page loads), 148 sources requested (125 fetched ok, covering 113 distinct pages; 23 failed), 25 spot checks, 164 claims (2 excluded) |
| Companion | [D1-review-rubric.md](D1-review-rubric.md), the rubric the D8 panel scores a PDF against |

Cited quilter voices stand in for the review and the discrepancy case that Jake's mother cannot
give (plan J16). Every bracketed id such as [S-A03] is a source in D1-sources.json, fetched on
2026-10-10, with its URL there. Everything below is paraphrased, quotes are limited to a few
words, and no individual poster is named. Calculator and quilter figures are recorded cross-checks, never the
source of an assertion (MATH.md rule 3), and this report changes no MATH.md vector and no
PATTERN-SPEC check. Arithmetic on a source's figures is this report's analysis, not something the
source says, and is marked as such.

## 1. Findings

1. Quilters' published charts disagree with each other more than with MATH.md. For the same quilt
   they assume 40, 42 or 44 in fabric, 2 to 8 in of overhang per side, 1/8 yd, 1/4 yd or half-yard
   rounding, and +10 to +20 in of binding extra (section 3).
2. A shop backing guide that MATH.md F8 also cites divides by 40 in and prices one seam direction [S-A03].
   It reproduces QREP's current backing numbers (crib 3 1/2 yd, throw 50 x 65 4 1/4 yd, full
   8 1/4 yd), so a quilter checking QREP's new numbers against it will see QREP lower (DIS-01,
   DIS-02).
3. No fetched source shows a quilter complaining that a calculator or pattern over-estimated
   backing. Six sources show why the numbers run high: stacked buffers, and quilters who would
   rather be half a yard over than two inches short (section 5, category 1). The reported
   over-estimate (MATH.md Q1) stays unconfirmed by outside voices.
4. Running short is reported in five sources: a shop's account and a forum thread [S-B04, S-B12],
   and three errata pages that correct yardage upward [S-B02, S-B03, S-B39]; three more describe a
   related difficulty (section 5, category 2). By this report's arithmetic, some published charts
   also under-buy at their own stated widths and allowances. In one backing chart, one row cannot
   cover its quilt, two more fall short at the low end of their range, and two more fall short under
   its longarm formula but not under every reading of the page. In another, five of six rows fall
   short if each figure is the row's total, which that chart does not settle (DIS-03). Three charts
   list 108 in wide backing that cannot span the backing they state (DIS-04), and two binding
   figures buy 1/2 in less fabric than their own strip count uses (DIS-06). These support MATH.md's
   seam-aware panel count (F9), its omission of a 108 in line for a king (F11, V-WIDE-05) and its
   strips-times-width binding line (F7).
5. Wrong cut sizes appear often in one magazine's corrections record from 2005 to 2023, and three
   fetch summaries of it rank them first; the page states no share, and its entries were not hand
   counted [S-B03]. Quilters respond by checking the arithmetic, making a test block and looking
   for corrections pages (sections 5 and 7).
6. By the evidence found (lists, recommendations and one reader survey, not counts of finished
   quilts), the most-made traditional squares and triangle quilts are the nine patch (5 sites),
   then half-square triangle quilts, flying geese and the four patch (4 sites each, in survey
   order), then the Irish chain and log cabin (4 sites each, no survey share); log cabin has no
   quilter's method in 0.4.0. The ranking favors a nine patch for the release demo, with a
   straight-set Double Irish Chain as the alternative that the repo fixture already exercises
   (section 6).
7. Reddit and X could not be read. Every automated request to them was refused or blocked, so the
   quilter voice here comes from forums (QuiltingBoard and The Quilt Show), designer and shop blogs,
   publishers and calculator sites (section 2).

## 2. Method and coverage

The research ran as four topic passes (A finishing numbers, B complaints, C most-made quilts and
name sources, D pattern trust and clarity), each fetching one page at a time, with no login,
posting, sign-up or contact, and no API, JSON or sitemap requests. The only search listing pages
requested were the Reddit and X pages listed under "Reddit and X" below. Sixteen sources that later
sections rely on were fetched a second time to check the claims drawn from them, six of them twice
(D1-sources.json, `spot_checks`). The checks corrected one survey percentage and dropped a
percentage share that a fetch summary had attached to a corrections list; the Webster name list was
rewritten from the book's full text [S-M02], and one claim from a knitting source was excluded. The
review of the first draft found five figures that fetches had returned but no claim recorded; they
are now claims C-M01 to C-M05, and C-A12 is corrected to its page's table. Page fetches return a
summary of a page, not its text, so a ranking such as "most frequent" is the summary's reading
unless the report says it was counted.

Result count is the number of results the web search returned for a query, not the engine's total
hit count; three searches returned two result sets, and both count. Every search that ran returned
at least one result. "Nothing used" counts searches none of whose results became a source that
backs a claim.

| Source group | Queries | Searches run | Refused by the search tool | Page loads | Results returned | Searches with nothing used | Pages fetched ok |
| --- | --- | --- | --- | --- | --- | --- | --- |
| r/quilting and related subreddits | 27 | 19 | 6 | 2 | 173 | 11 | 0 |
| X | 8 | 7 | 0 | 1 | 64 | 4 | 0 |
| Forums | 20 | 20 | 0 | 0 | 184 | 8 | 13 (QuiltingBoard 12, The Quilt Show 1) |
| Designer, shop and publisher blogs | 62 | 62 | 0 | 0 | 580 | 18 | 88 (designer 27, shop 43, publisher 18) |
| Calculator sites | 14 | 14 | 0 | 0 | 147 | 7 | 12 |
| Public-domain books | 1 | 1 | 0 | 0 | 10 | 0 | 5 (one work) |
| Other pages (extension office, magazines, newsletters), from the queries above | | | | | | | 7 |

The 125 ok fetches cover 113 distinct pages on 55 sites: ten pages were fetched two or three times
and carry two or three ids (`same_page_as` in D1-sources.json; one C&T Publishing article was
fetched at two URLs), and any list here that counts sources cites one id per page. Nine distinct ok
pages back no claim: two off-topic pages (one about crochet; one about knitting, whose one claim is
excluded), two copies of the Webster book that its full text [S-M02] replaced, and five quilting
pages the passes did not draw on. Five forum fetches (four Quilt in a Day threads and one Tapatalk
group) returned HTTP 403.

**Reddit and X.** Every automated request to Reddit or X was refused or blocked, so they contribute
no claim. In time order on 2026-10-10 (UTC, when each request started):

- 10:09:54. The page fetch tool refused an r/quilting search listing page before sending any
  request (S-C03).
- 10:09:56 to 10:14:13. The web search refused reddit.com as a domain filter six times, so those
  searches never ran (Q-C06, Q-B10, Q-A09, Q-A10, Q-D30, Q-D31).
- 10:14:17 and 10:14:18. The page fetch tool refused one r/quilting thread on www.reddit.com
  (S-D26), then the same thread on old.reddit.com (S-D27), a second host tried after the first
  refusal. The thread came from a Reddit mirror site in a search result (Q-D22); the mirror was not
  requested.
- 10:19:18 to 10:19:40. After both tools had refused Reddit, headless Chromium loaded three search
  listing pages, one after another: the r/quilting search on www.reddit.com, which returned a
  network-security block page (Q-M01); the same search on old.reddit.com, a retry on another host
  after that block, which returned HTTP 403 and the same block page (Q-M02); and X search, which
  returned HTTP 403 and an empty page (Q-M03).

The other Reddit and X group searches, `site:` searches included, ran and returned no reddit.com or
x.com page. No request went to Reddit or X after Q-M03. Some of these steps followed an earlier
refusal or block: S-D27 and Q-M02 tried a second Reddit host, and Q-M01 to Q-M03 used a browser
after the search and page fetch tools had refused Reddit. Retrying after a refusal or block is not
using a site the way a person would (ORCHESTRATOR.md section 15); all of these are recorded here as
they happened.

## 3. Standard sizes: what quilters and calculator sites state

The MATH.md column copies section 4.7 at its defaults: 42 in backing width, 4 in overhang per
side, 1 in per backing seam, +9 in (pieced) or +4 1/2 in (one piece) allowance, 1/4 yd rounding;
binding 2 1/2 in strips at 40 in usable width, +10 in, join-aware. "Today" is QREP's current value
from the same table. Each stated figure gives the source's own quilt size; the width, overhang and
rounding behind it are in the source table below, which marks what a source does not state.
"Exact" means the source uses the same dimensions. No source states a figure for the
92 1/2 x 115 queen.

| Source | What it is | Fabric width | Overhang or extra length | Rounding and other |
| --- | --- | --- | --- | --- |
| [S-A02] | Designer backing chart | 42 to 44 in | 6 to 8 in added to each dimension | Up to 1/4 yd per panel in its worked example; its panel column says only whether to piece, not how many panels (C-M03) |
| [S-A03] | Shop backing chart | 40 in usable from a 42 in bolt; 108 in | 4 in per side | Up to 1/4 yd; 1/2 in seams; seams run lengthwise |
| [S-A04] | Shop binding chart | 42 in | +10 in | Strips rounded up; yardage rounding not stated; 2 1/2 in strips |
| [S-A05] | Shop binding table | 42 in | About 1/4 yd buffer | Strips rounded up; yardage rounding not stated; 2 1/2 in strips |
| [S-A07] | Shop guide, 108 in backing | 108 in | 4 in per side (longarm) | Not stated |
| [S-A08] | Shop calculator guide | 44 in; 108 in | Width + 8 in; length + 8 in (home) or + 12 in (longarm). A note also gives 6 to 8 in for longarm without saying per side or total (C-M04) | Round up by half a yard when unsure |
| [S-A10] | Shop article, 90 x 90 queen | 44 to 45 in fabric, 42 in usable | 4 to 5 in per side; binding +15 to 20 in | Not stated; 10 to 15 percent extra for shrinkage; 2 1/2 in binding strips |
| [S-A12] | Forum thread | 108 in | 4 to 5 in per side (6 in for some longarm quilters) | Not stated |
| [S-A13] | Forum thread | 108 in | Not stated | Not stated |
| [S-A15] | Shop calculator article | 44 in (pieced); 108 in; 40 in for binding | Its backing column is the top + 8 in each way; binding +10 to 12 in | Not stated; 2 1/2 in binding strips |
| [S-A16] | Longarm guide | 40 to 42 in usable | 5 in per side | Not stated; +1/4 yd for shrinkage and squaring; 1/2 in seams |
| [S-A26] | Shop guide, 108 in backing | 108 in | 4 in per side (machine), 6 to 8 in per side (longarm) | Not stated |
| [S-A29] | Shop binding tutorial | 40 in | +20 in | Not stated; 2 1/2 in strips, diagonal joins |
| [S-A30] | Designer binding guide | Not stated | +20 in | Not stated; 2 1/2 in strips |
| [S-A38] | Calculator | 42 in; 108 in | 4 in per side | No rule stated, figures in eighths of a yard; suggests 10 percent extra |
| [S-A40] | Shop binding guide | 40 in | +12 in | Strips rounded up; yardage rounding not stated; 2 1/2 in strips |

### 3.1 Backing, pieced

| Size | MATH.md (today) | Stated figures |
| --- | --- | --- |
| Crib 36 x 52 | 2 3/4 yd, 2 x 44 in horizontal (3 1/2) | Exact: 3 1/2 yd, 2 widths [S-A03]; 2 3/4 yd, 2 strips [S-A38]; 1 5/8 yd [S-A02]. 40 x 50: 2 1/2 to 3 yd [S-A08]. 45 x 60: 4 yd [S-A15] |
| Throw 50 x 65 | 3 1/2, 2 x 58 horizontal (4 1/4) | Exact: 4 1/4 yd, 2 widths [S-A03]; 3 7/8 yd, 2 strips [S-A38]. 50 x 60: 2 1/4 yd [S-A02] |
| Throw 60 x 72 | 4 1/4, 2 x 68 horizontal (4 1/2) | Exact: 4 to 4 1/2 yd [S-A08]. 60 x 70: 4 3/4 yd [S-A15] |
| Twin 70 x 90 | 5 3/4, 2 x 98 vertical (5 1/2) | Exact: 6 yd [S-A15]; 5 yd [S-A02]. 68 x 86: 5 1/4 yd, 2 widths [S-A03]. 60 x 80: 5 yd [S-A08]; 5 yd, 2 widths of 90 in [S-A16] |
| Full 84 x 90 | 8, 3 x 92 horizontal (8 1/4) | Exact: 8 1/4 yd, 3 widths [S-A03]. 85 x 108: 6 yd [S-A02]. 72 x 90: 5 1/2 yd [S-A08] |
| Queen 90 x 108 | 8 1/2, 3 x 98 horizontal (9 3/4) | Exact: 8 3/8 yd, 3 strips cut 98 in long [S-A38]; 6 yd [S-A02]; 6 to 6 1/2 yd [S-A08]; pieced "not recommended" [S-A15]. 90 x 95: 8 3/4 yd, 3 widths [S-A03]. 90 x 90: 8 to 9 yd [S-A10] |
| Queen 92 1/2 x 115 | 8 3/4, 3 x 100 1/2 horizontal (10 1/4) | Not found |
| King 110 x 108 | 10, 3 x 116 vertical (9 3/4) | 108 x 108: 9 7/8 yd, 3 strips [S-A38]; 9 yd [S-A02]; 9 1/2 to 10 yd [S-A08]. 110 x 110: pieced "not recommended" [S-A15]. 108 x 95: 8 3/4 yd, 3 widths [S-A03] |

General statements: eight sources give 4 in per side for at least one kind of quilting [S-A03,
S-A07, S-A08, S-A25, S-A26, S-A36, S-A37, S-A38]; others give 3 to 4 in [S-A17, S-A14], 5 in
[S-A16], or 6 to 8 in per side for longarm quilting [S-A26], and one guide gives 6 to 8 in for
longarm without saying per side or total [S-A08]; home quilting runs 2 to 4 in [S-A25, S-A17,
S-A14]. Backing seams are 1/2 in and pressed open [S-A03, S-A14, S-A16, S-A35, S-A37]. Usable
width: 40 in is the most conservative planning figure [S-A03, S-A27, S-A35, S-A16]; calculators
also use 42 in [S-A37, S-A38] and 43 1/2 in [S-A36]. Allowances: C&T adds 9 in for a seamed
backing and 1/8 to 1/4 yd for crooked cuts, and buys the cheaper of the two seam directions
[S-A27]; others add 1/4 yd [S-A16] or 5 to 15 percent [S-A36, S-A38, S-A10] for shrinkage and
squaring.

### 3.2 Backing, wide (108 in)

| Size | MATH.md | Stated figures |
| --- | --- | --- |
| Crib 36 x 52 | 1 1/2 yd | Exact: 1 3/4 yd [S-A03]. 40 x 50: 1 1/2 yd [S-A08]. 45 x 60: 2 yd [S-A15] |
| Throw 50 x 65 | 1 3/4 | Exact: 2 1/4 yd [S-A03] |
| Throw 60 x 72 | 2 1/4 | Exact: 2 1/2 yd [S-A08]. 60 x 70: 2 1/2 yd [S-A15]; 2 1/4 yd [S-A07, S-A26] |
| Twin 70 x 90 | 2 1/2 | Exact: 3 yd [S-A15]. 68 x 86: 2 3/4 yd [S-A03]. 60 x 80: 2 3/4 yd [S-A08]. 72 x 92: 2 1/2 yd [S-A07, S-A26] |
| Full 84 x 90 | 2 3/4 | Exact: 2 3/4 yd [S-A03]. 72 x 90: 3 yd [S-A08]. 86 x 92: 3 yd [S-A07]; 2 3/4 yd [S-A26] |
| Queen 90 x 108 | 3 1/2 | Exact: 3 1/2 yd [S-A15, S-A08]; 2 7/8 yd, one strip cut 100 in long [S-A38], which by this report's arithmetic cannot cover its own 98 x 116 backing (DIS-04). 90 x 95: 3 yd [S-A03]. 90 x 90: 3 yd [S-A10]. 92 x 96: 3 yd [S-A07] |
| Queen 92 1/2 x 115 | 3 3/4 | Not found |
| King 110 x 108 | None at 108 in (3 1/2 at 118 in) | 110 x 110: 3 1/2 yd [S-A15]. 108 x 108: 3 1/2 yd [S-A08]. 108 x 95: 3 1/4 yd [S-A03]. 100 x 100: 3 yd [S-A07]; 3 to 3 1/2 yd [S-A12]. King, size not stated: 3 to 3 1/2 yd [S-A13] |

By this report's arithmetic, S-A03's crib and throw figures (63 and 81 in) cut the backing's
length (60 and 73 in) from the bolt; turning the piece so the 108 in width spans the length needs
only the backing's width (44 and 58 in) plus F11's 4 1/2 in allowance, which is how F11 reaches
1 1/2 and 1 3/4 yd. One calculator
offers 118 in wide backing [S-A35] and one guide mentions it [S-A26]; neither gives a yardage
(C-A25).

### 3.3 Binding

| Size | MATH.md (today) | Stated figures |
| --- | --- | --- |
| Crib 36 x 52 | (5) strips, 1/2 yd (5, 1/2) | 45 x 45: 5 strips, 3/8 yd [S-A04]. Exact: about 1/2 yd [S-A05] |
| Throw 50 x 65 | (7), 1/2 (6, 1/2) | 52 x 70: 1/2 yd [S-A30] |
| Throw 60 x 72 | (8), 3/4 (7, 1/2) | Exact: 7 strips, 1/2 yd [S-A04]; 8 strips, about 5/8 yd [S-A29]. 60 x 70: 6.8, so 7 strips, about 0.6 yd, at +12 in [S-A15] |
| Twin 70 x 90 | (9), 3/4 (8, 3/4) | 67 x 99: 9 strips, 5/8 yd [S-A04]. Exact: about 1 1/4 yd [S-A05]. 70 x 88: 2/3 yd [S-A30] |
| Full 84 x 90 | (10), 3/4 (9, 3/4) | 82 x 96: 9 strips, 5/8 yd [S-A04] |
| Queen 90 x 108 | (11), 1 (10, 3/4) | Exact: 11 strips, about 3/4 yd [S-A40]. 88 x 104: 10 strips, 3/4 yd [S-A04]. 90 x 90: 3/4 yd [S-A10]. 88 x 106: 3/4 yd [S-A30] |
| Queen 92 1/2 x 115 | (12), 1 (11, 1) | Not found |
| King 110 x 108 | (12), 1 (11, 1) | 106 x 108: 11 strips, 3/4 yd [S-A04]. 106 x 106: 7/8 yd [S-A30] |

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
| Full 84 x 90 | 92 x 98, king | Full package 90 x 96 [S-A23, S-A06] or 81 x 96 [S-A25, S-A33]; neither covers 92 x 98. One brand's queen package, 108 x 96, covers it turned [S-A22] |
| Queen 90 x 108 | 98 x 116, king | The same chart pairs the 90 x 108 queen package with a 90 x 108 top [S-A23] |
| Queen 92 1/2 x 115 | 100 1/2 x 123, king (turned) | Not found. The king package is 124 x 120 for one brand [S-A06] and 120 x 120 in four package lists [S-A25, S-A23, S-A33, S-A22]; the second does not cover 100 1/2 x 123 |
| King 110 x 108 | 118 x 116, king | King package 120 x 120 or 124 x 120 [S-A25, S-A23, S-A33, S-A22, S-A06] |

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
| Sides first, then top and bottom | [S-A18, S-D28]; one guide sews top and bottom first [S-A19] | Sides first |
| Add 1 in to each border length before trimming | [S-A19] | No extra beyond the 1/2 in seam allowance |
| Join border strips with diagonal seams | [S-A20] | Straight 1/4 in joins, 1/2 in per join (j) |
| Border width about a third to a half of the block size | [S-A19] | Not a math question (design) |

## 4. Disagreements for the A1 and A2 owners

A1, A2a and A2b have merged, so these go to their owners and to D7 as context. None changes a
vector; each names the MATH.md item it bears on. The arithmetic in DIS-03, DIS-04 and DIS-06 is
this report's, done by hand on the sources' stated figures; the sources do not say it.

- **DIS-01 (A1; Q7).** The shop backing guide of finding 2 plans on 40 in usable width ("divide by
  40, not 42") [S-A03], as do forum quilters [S-B12]; B is 42 in (J13). At 40 in that guide
  reproduces QREP's current crib, 50 x 65 throw and full figures (3 1/2, 4 1/4, 8 1/4 yd).
  Calculators use 42 to 43 1/2 in [S-A38, S-A37, S-A36], and two shop charts use 44 in [S-A08,
  S-A15].
- **DIS-02 (A1; F10).** The same guide's chart prices one seam direction and its text notes that
  crosswise seams can save half a yard on small quilts [S-A03]. A publisher's method computes both
  directions and buys the smaller [S-A27], as F10 does, so QREP's new crib and throw numbers sit
  3/4 yd below the first chart. PS-12's seam-direction line is what tells the reader why.
- **DIS-03 (A1; F9).** Published backing rows that cannot cover their own quilt at their own
  width and allowance, by this report's arithmetic. Each case takes the widest fabric the source
  allows, no seam loss, and the cheaper of panels across the width or across the length (inches);
  the reading of each source's allowance is stated with it:
  - [S-A02], 42 to 44 in, 6 to 8 in added to each dimension (6 in used). The page does not say
    whether a row's figure is the row's total or per panel: its worked example rounds a length up
    "per panel", and its panel column says only whether to piece, not how many panels (C-M03).
    Reading each figure as the row's total: lap 50 x 60 has a 56 x 66 backing; two panels are
    needed either way, the cheaper 2 x 56 = 112 in against 2 1/4 yd = 81 in. Twin 70 x 90,
    76 x 96: 2 x 96 = 192 in (or 3 x 76 = 228) against 5 yd = 180 in. Full 85 x 108, 91 x 114:
    3 x 91 = 273 in (or 3 x 114 = 342) against 6 yd = 216 in. Queen 90 x 108, 96 x 114:
    3 x 96 = 288 in (or 3 x 114 = 342) against 216 in. King 108 x 108, 114 x 114: 3 x 114 =
    342 in against 9 yd = 324 in. Only the baby row covers: its 42 x 58 backing fits one 44 in
    panel 58 in long, within 1 5/8 yd (58 1/2 in). If the figures are per panel, the rows cannot be
    checked, because the page gives no panel count.
  - [S-A08], 44 in. The page states its allowance two ways (C-M04): a formula, width + 8 in and
    length + 8 in (home) or + 12 in (longarm), and a note of 4 in on all sides for home quilting
    and 6 to 8 in for longarm quilting that does not say per side or total. For home quilting the
    two agree (+8 in each way). At that allowance, queen 90 x 108 at 6 to 6 1/2 yd (at most 234 in)
    has a 98 x 116 backing that needs three panels either way, because two give at most 88 in, so
    3 x 98 = 294 in (8 1/6 yd) turned or 3 x 116 = 348 in. At the low end of their ranges, crib
    40 x 50 (48 x 58) needs 2 x 48 = 96 in against 2 1/2 yd = 90 in, and king 108 x 108
    (116 x 116) needs 3 x 116 = 348 in against 9 1/2 yd = 342 in. Under the longarm formula, twin
    60 x 80 (68 x 92) needs 2 x 92 = 184 in against 5 yd = 180 in, and full 72 x 90 (80 x 102)
    needs 2 x 102 = 204 in against 5 1/2 yd = 198 in. These two also fall short under MATH.md F8's
    reading of the page (12 in more each way) and under 6 to 8 in per side, but not if the note's
    6 to 8 in is a total: the twin then needs at most 2 x 68 = 136 in turned, and the full at most
    2 x 98 = 196 in, both within the stated yardage.
  These support the seam-aware panel count of F9 and the "running short" reports (section 5).
- **DIS-04 (A1; F11, V-WIDE-05).** Three charts offer 108 in wide backing that cannot span the
  backing they state. Two list 3 1/2 yd for a king whose backing is wider than 108 in both ways:
  110 x 110 with a 118 x 118 backing [S-A15], and 108 x 108 with 8 in added, 116 x 116 [S-A08]. A
  calculator gives 2 7/8 yd, one strip cut 100 in long, for the 90 x 108 queen at 4 in per side
  [S-A38]; the backing is 98 x 116, so the 108 in width spans the 98 in side and the strip must be
  116 in long (3 1/4 yd before any allowance). F11 prints no 108 in line for the 110 x 108 king,
  which is correct; a finisher who expects one needs the footnote to say why (rubric R-05).
- **DIS-05 (A1; F6, F7).** Strip counts from charts that divide by 42 in with no join loss run
  one strip below F7 (60 x 72: 7 against 8) [S-A04]. Sources that divide by 40 in with +20 in
  match F7's count (60 x 72: 8) [S-A29]. Binding extra ranges from +10 to +20 in across 8 sources;
  t = 10 in is the low end, and the join-aware count adds the margin back.
- **DIS-06 (A1; F7).** Two binding figures buy less fabric than their own strip count uses:
  11 strips x 2 1/2 in = 27 1/2 in, priced at 3/4 yd = 27 in, in a 106 x 108 king row [S-A04];
  a 90 x 108 queen example gives about 3/4 yd for the same 11 strips [S-A40], which a reader buying
  exactly 3/4 yd would find 1/2 in short. F7 buys strips x w rounded up
  (1 yd at 1/4 yd rounding), so QREP's line is 1/4 yd higher on purpose.
- **DIS-07 (A1; Q3).** Rounding increments split: 1/4 yd [S-A03, S-A35, S-A21], 1/8 yd [S-A36,
  S-A37], figures in eighths with no stated rule [S-A38, S-A04], and a half-yard tip [S-A08].
- **DIS-08 (A1; Q2).** Backing allowances: +9 in per seamed backing and 1/8 to 1/4 yd for crooked
  cuts [S-A27], +1/4 yd for shrinkage and squaring [S-A16], 5 to 15 percent [S-A36, S-A38, S-A10].
  The default +9 in and +4 1/2 in sit at the low end of what quilters add.
- **DIS-09 (A1; F12, Q11).** Package sizes vary by brand. The king is 124 x 120 in one brand
  [S-A06] (F12's source) and 120 x 120 in four package lists [S-A25, S-A23, S-A33, S-A22]; at
  120 x 120, V-BATT-08 (queen 92 1/2 x 115, 100 1/2 x 123) is larger than a king. One brand's queen
  is 108 x 96 [S-A22], which covers V-BATT-06's 92 x 98 turned, so with that brand a full 84 x 90
  takes a queen package, not a king. One chart pairs package
  names with same-named quilts and leaves no overhang [S-A23], while F12 picks a queen package for
  a 70 x 90 twin; PS-13 prints the package dimensions, which settles the naming for the reader.
- **DIS-10 (A1; Q5).** Overhang: eight sources give 4 in per side for at least one kind of
  quilting (section 3.1); longarm requests run to 5 in [S-A16] and 6 to 8 in per side [S-A26], one
  guide gives 6 to 8 in for longarm without saying per side or total [S-A08], and home quilting
  runs 2 to 4 in [S-A25, S-A14, S-A17]. The default is the most frequent single value; the 2 in
  domestic option matches the home range.
- **DIS-11 (A2; F4).** Some quilters join border strips on the diagonal [S-A20], which uses about
  one strip width per join, not F4's 1/2 in; one guide adds 1 in to each border length [S-A19].
  F4's count holds only for straight joins, so the cut list must name the join type, as MATH.md
  section 1.5 item 8 and PS-28 require. One guide sews the top and bottom borders first [S-A19],
  against F4's sides first. No source found addresses per-piece versus pooled border counting
  (Q6).
- **DIS-12 (A2; F2, F5).** No disagreement on U = 40: the 40 in planning width is the most common
  figure for strip cutting and binding [S-A03, S-B12, S-D32, S-A15, S-A40].

## 5. Complaint catalog

Counts are distinct fetched sources (pages or threads) per category; a page that two passes fetched
counts once. Each count is split by kind of source. Quilter reports are forum threads, blog
comments and a shop's or longarm quilter's account of a problem met. Errata pages are a publisher's
or designer's own corrections. Calculator and guide pages state what a tool or guide assumes, so
they are indirect evidence of a complaint. A page is classed by the claim drawn from it in that
category, so one page can be a quilter report in one category and an indirect guide page in
another. Each category names the MATH.md section 6 question or PATTERN-SPEC check it bears on.

| # | Category | Sources | What the sources say | Bears on |
| --- | --- | --- | --- | --- |
| 1 | Backing over-estimated | 6, all indirect: 4 calculator and guide pages, 2 forum threads | No direct complaint found. Calculators stack buffers (an extra 1/4 yd, about 1/2 yd when prewashing, shrinkage percents, 4 to 8 in of overhang) [S-B15, S-B16, S-B18, S-B35]; forum quilters say they would rather be half a yard over than two inches short [S-B36, S-B12] | Q1, Q2, Q5 |
| 2 | Running short | 8: 5 report a shortfall (a shop's account and a forum thread, 3 errata pages); 3 describe a related difficulty | Shortfall: a published pattern listed backing and batting far below what the quilt needed, corrected on the publisher's errata page [S-B02]; a monthly pattern was half a yard short on one fabric until the designer posted a corrected cutting sheet [S-B04]; errata pages correct yardage upward [S-B03, S-B39]; patterns written for 44 to 45 in fabric run short on today's 40 to 42 in, worst for newer quilters [S-B12]. Related difficulty: a 79 in top could not get a one-piece backing at 40 in usable [S-B27], quilters whose top is just wider than the backing fabric look for ways to widen it [S-B26], and working out yardage after changing a pattern is hard [S-B01] | Q2, Q4, Q7, F9 |
| 3 | Width-of-fabric assumptions | 9: 3 quilter reports (forum threads); 6 calculator and guide pages, indirect | Experienced quilters plan on 40 in even from fabric labeled 44 [S-B12, S-B36, S-B27]. Indirect: calculators and a publisher assume 40, 42 to 44 or a changeable 43 in [S-B15, S-B35, S-B16, S-B17, S-B18]; prewashing and trimming selvages take more [S-B06, S-B16, S-B18] | Q7, U = 40, B = 42 |
| 4 | Binding length and strip count | 4: 1 quilter report (blog comments); 3 calculator and guide pages, indirect | Joining the ends is a step some need a video for [S-B01]. Indirect: strip count changes with strip width, and guides differ on the extra (+10 or +12 in) [S-B20, S-B34]; a calculator fixed at 2 1/2 in strips over 40 in gives a different count for another width [S-B15] | F6, F7 |
| 5 | Calculators disagree | 5, all indirect: calculator and guide pages; no quilter report found | Overhang varies from 0 to 8 in per side; one adds 1 in per seam, one rounds up to 1/8 yd, one adds a buffer for crooked cuts; each page states its own assumptions, and one says its results are only a starting point [S-B15, S-B16, S-B17, S-B18, S-B35] | Q2, Q3, Q5, Q7; PS-14 |
| 6 | Pattern errors and errata | 8: 4 quilter reports (forum threads and a shop's account); 4 errata pages | Errata pages list wrong cut sizes, wrong counts, mislabeled diagrams and missing templates [S-B02, S-B03, S-B24, S-B39]; quilters find a wrong dimension after cutting everything [S-B10, S-B33]; they learn of corrections by searching or from a shop [S-B04, S-B10]; precut kit pieces 1/4 in off broke triangle units [S-B09] | PS-16, PS-19, PS-23 |
| 7 | Unclear instructions | 5: 3 quilter reports (blog comments, a forum thread); 2 errata or revision pages | Pressing direction, nesting and the scant 1/4 in confuse [S-B01]; patterns assume the buyer knows layering, quilting and binding [S-B11]; readers mistake unfinished for finished sizes [S-B13]; designers clarify assembly text and switch to cut-large-and-trim [S-B24, S-B28] | PS-15, PS-22, PS-29 |
| 8 | Cutting instructions | 3: 1 quilter report (blog comments); 2 errata or revision pages | Wrong cut sizes appear often in one magazine's corrections record, and three fetch summaries rank them first; the page states no share [S-B03]; cutting must be exact or nothing fits [S-B01]; a pattern was revised to cut triangles oversized and trim [S-B28] | PS-16, PS-23 (L-06) |
| 9 | Size mismatch | 4: 2 quilter reports (blog comments, a forum thread); 1 correction; 1 guide page, indirect | A finished size printed 20 in off [S-B28]; blocks finishing small from printer scaling, seam error or finished-versus-unfinished confusion [S-B13, S-B14]; kit pieces cut wrong [S-B09] | PS-07, PS-26, PS-38 |
| 10 | Format and print | 2, all indirect: guide pages | Fit-to-page printing shrinks templates; print at 100 percent and measure the test box [S-B21, S-B13] | PS-38 |
| 11 | Longarm backing | 6: 5 quilter reports (longarm quilters' accounts, in their guides and service checklists, of problems they meet with customers' backings); 1 calculator, indirect | Backing should be 8 to 10 in larger than the top [S-B05, S-B06, S-B23, S-B37, S-B38]; uneven or badly sewn seams and selvages in seams cause sag and puckers [S-B05, S-B06, S-B23]; seams pressed open; a short backing costs extra to extend [S-B38, S-B16] | Q5, F8, F9 |

Not found: complaints about tiny text, color-only diagrams, page counts or wasteful cutting layouts,
and any direct report of a binding that came out short.

## 6. Most-made traditional squares and triangle quilts

"Most-made" here means most often listed, recommended or chosen as a favorite: no source counts
finished quilts. Ranked by the number of independent sites (fetched ok) that list the family as
popular, a favorite or a classic, or recommend it for beginners (two pages from one site count
once; a post that only shows one finished quilt does not count), then by its share in a quilting
publisher's reader survey of over 1,000 quilters [S-C01]. Families tied on both share a rank and are listed alphabetically. The
evidence is lists, recommendations and one survey; no source counts finished quilts, and Reddit,
where such counts would come from, could not be read. Scope follows plan section 2.3.

| Rank | Family | Sites | Survey share [S-C01] | Evidence | Units | 0.4.0 scope | Webster 1915 list |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Nine patch (and double nine patch) | 5 | 32 percent | Third favorite unit and the most common first block [S-C01]; common-block list [S-C02]; beginner list rank 2 [S-C11]; magazine top 10 [S-C17]; first-quilt workshop [S-C23] | Squares | In | Nine Patch |
| 2 | Half-square triangle quilts (pinwheel, broken dishes, sawtooth) | 4 | 53 percent | Favorite unit [S-C01]; lists [S-C02, S-C11, S-C12] | Half-square triangles | In | Broken Dish, Pinwheel Square, Wind Mill, Sawtooth Patchwork, Bear's Paws |
| 3 | Flying geese | 4 | 33 percent | Second favorite unit [S-C01]; lists and tutorials [S-C02, S-C16, S-C27] | Stitch-and-flip corners (or HSTs) | In | Not under this name; Wild Goose Chase is listed |
| 4 | Four patch | 4 | 18 percent | Survey [S-C01]; lists [S-C02, S-C11, S-C12] | Squares | In | New Four Patch |
| 5= | Irish chain (single, double) | 4 | None | Favorite, set straight [S-C14], on the same site as a post that says chains can be set on point [S-C18]; classic beginner quilt, set straight [S-C16]; magazine top 10 [S-C17]; a designer's own throw pattern that recommends it for beginners with some experience, set straight [S-C26]. Straight-set examples at 3 sites. Without S-C26 it would have 3 sites and rank 8th, below rail fence | Squares, merged runs | In when set straight; on point is out | Double Irish Chain |
| 5= | Log cabin | 4 | None (a popular write-in and the second most common first block) | Survey [S-C01]; lists [S-C02, S-C11, S-C12]; classic list on the same shop site as S-C11 [S-C16] | Log strips | Read, no quilter's method yet | Log Cabin |
| 7 | Rail fence | 3 | 17 percent (rail unit) | Survey [S-C01]; first in two beginner lists [S-C11, S-C12] | Merged runs (bars) | In | Not listed |
| 8 | Hourglass and quarter-square triangle quilts | 2 | 11 percent | Survey [S-C01]; common-block list [S-C02] | Quarter-square triangles | In | Hour Glass |
| 9= | Bricks | 2 | None | Beginner lists [S-C11, S-C12] | Squares, merged runs | In | Brick Pile and Brickwork Quilt by name; designs not checked |
| 9= | Disappearing nine patch | 2 | None | Beginner list rank 3 [S-C11]; magazine top 10 [S-C17] | Squares, merged runs | In | Not listed |
| 9= | Simple squares, checkerboard, charm squares | 2 | None | Beginner lists [S-C11, S-C12] | Squares | In | Not listed |
| 12 | Square in a square | 1 | 20 percent | Survey [S-C01] | Stitch-and-flip corners | In | Not listed |
| 13= | Bow tie | 1 | None | Traditional roundup [S-C20] | Squares, stitch-and-flip corner | In | Not listed |
| 13= | Ohio star | 1 | None (stars won favorite block overall, Ohio star named most) | Survey [S-C01] | Squares, QSTs | In | Not listed |
| 13= | Sampler | 1 | None | Historically as common as one-block quilts; no block names given [S-C25] | Mixed | In when every block uses in-scope units (squares, HSTs, QSTs, stitch-and-flip corners) set straight; out when any block has curves, applique or an on-point setting (plan section 2.3) | Not applicable |

Not found as most-made: churn dash, Trip Around the World, shoo fly, snowball and card trick
(C-C24). The page first counted for churn dash names a snail trail or monkey wrench quilt and never
mentions churn dash [S-C16]; monkey wrench names more than one block, so the page is not counted
for churn dash (C-C18). Only the Irish chain shows up often on point: one designer blog says single,
double and triple chains all work on point [S-C18], and one finished scrap quilt is on point
[S-C15].

Candidates:
- **Corpus (D3a).** In-scope rows in rank order: nine patch and double nine patch, HST quilts
  (pinwheel, broken dishes, sawtooth, bear's paw), flying geese, four patch, straight-set Irish
  chains (single and double), rail fence, hourglass, bricks, disappearing nine patch, simple squares
  and checkerboard, square in a square, bow tie and Ohio star. For the thin stitch-and-flip class,
  snowball quilts may be added, though no source ranks them. For the refusal tier, on-point Irish
  chains and on-point nine patches first, because they look like in-scope families ranked 1 and 5=.
- **Examples gallery (C9).** The top five in-scope families: a nine patch, one HST quilt (pinwheel
  or broken dishes), a flying geese quilt, a four patch or checkerboard, and a straight-set Double
  Irish Chain, all families whose method plan section 2.3 lists as working. Not log cabin or Trip
  Around the World.
- **Release demo.** The ranking favors a nine patch quilt (rank 1). A straight-set Double Irish
  Chain is the alternative: it ranks 5=, below four families, and no fetched source is about the
  Double variant in particular, but it is built from the same squares and merged runs, its name is
  in Webster's list [S-M02], and the repo fixture is a Double Irish Chain, so its method is already
  exercised. If the demo shows triangle units too, add a pinwheel or broken dishes HST quilt
  (rank 2). Whether a CC0 museum photo of any of these exists is D3a's call.

Name sources: the only name source cited is Marie D. Webster, Quilts: Their Story and How to Make
Them (1915). The Project Gutenberg ebook page states it is public domain in the USA [S-M01], and its
text carries a 1915 copyright line [S-M02]. Its alphabetical list was searched in full for the names
above. QUILT-1M, Hall and Kretsinger, the Quilt Index, the V&A and the International Quilt Study
Center were not used.

## 7. Quilter personas for D8

Three personas for the D8 panel, each built from the claims above. A reviewer playing one should
read the PDF in the order that persona checks first and score it with [D1-review-rubric.md](D1-review-rubric.md),
weighting the items marked for that persona. A line marked "report's analysis" is this report's
reasoning about QREP's format or a source's arithmetic, not something a source says.

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
- Prints with the default fit-to-page setting unless told to print at 100 percent [S-D07].
- Trusts skill and time labels and is told to double the time [S-D15, S-D17]; PS-05 leaves both
  out, so a panel finding that asks for them is recorded for Jake, not built.

### P2. Experienced traditional piecer

Has made many traditional quilts and has been burned by printed errors. Checks first: cut sizes
against finished sizes, then piece counts against the layout.
- Reads the whole pattern, does rough math, and makes a test block before cutting everything
  [S-D03, S-D11, S-D33].
- Knows wrong cut sizes appear often in a magazine's corrections record [S-B03] and has found one
  only after cutting [S-B10, S-B33].
- Report's analysis: QREP's strip-first cutting with per-strip yields (PATTERN-SPEC PS-16) is what
  lets this persona do that rough math by hand; no source asks for that format by name.
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
- Checks the overhang per side against what longarm quilters ask: at least 4 in all round [S-D35],
  5 in [S-D20] or 6 to 8 in [S-A26]. Charts most often use 4 in [S-A03, S-A25], and home quilting
  needs 2 to 4 in [S-A25, S-A14, S-A17].
- Plans on 40 in usable width with selvages trimmed [S-A03, S-B12, S-B27].
- Wants a square backing with seams pressed open and selvages out of the seams [S-B05, S-B23,
  S-D35, S-B38].
- Is told crosswise backing seams can save half a yard on small quilts and lengthwise seams wear
  better on bed quilts [S-D10].
- Is offered 108 in wide backing by shop guides from crib size up, two of them through king
  [S-A03, S-A07] and one through queen [S-A26].
  Report's analysis: some charts list it for kings it cannot span (DIS-04), so a missing 108 in
  line needs a stated reason (rubric R-05).
- Wants the binding strip width, strip count, join method, corner method and extra length stated
  [S-D31, S-A40, S-D21, S-A43].
- Checks the batting size, the top plus about 4 in per side [S-A24, S-A25], and the package that
  covers it [S-A25].
- Would rather buy half a yard over than come up two inches short [S-B36, S-B12].

## 8. V-MOM-01

The slot stays open. Item O1 of the Jake queue comment on #104 (comment 6043683358) asks for the
quilt size, QREP's backing number, the calculator and its number; the orchestrator keeps that
comment, and this ticket does not edit it. No fetched source describes a matching over-estimate
case (section 5, category 1). When Jake supplies the case, A1 writes the failing hand-computed test
before any fix (MATH.md Q1).

## 9. Limits

- No Reddit or X content: every automated request to them was refused or blocked (section 2).
- Five sites supply six or more distinct pages each: QuiltingBoard 12 (threads, each with several
  posters), lindas.com 9, quiltingdaily.com 8, missouriquiltco.com 6 and mrsquilty.com 6. A few
  shops and one publisher weigh more than their count of sources suggests.
- Page fetches return a summary of each page, not its full text. Sixteen sources were fetched a
  second time and checked, six of them twice (D1-sources.json, `spot_checks`); the claims from the
  rest are as the research passes recorded them.
- The most-made ranking counts lists and recommendations, not finished quilts.
- Size figures rarely use MATH.md's exact dimensions; "nearest" rows are context, not
  like-for-like comparisons.
