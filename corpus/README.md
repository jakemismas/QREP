# QREP corpus

Real quilt photos with proposed and, later, verified truth, for measuring the confirmed read
(plan section 8). Everything in this folder is public, and so is its history: a file that
reaches any commit stays public, because force pushes are banned.

## Layout

| Path | What it holds | Who writes it |
|---|---|---|
| `manifest.csv` | One row per fetched photo: its source, rights flag, hashes, size, tier and class | `scripts/eval/corpus_fetch.py` and the screening step (D3a) |
| `ATTRIBUTION.md` | Credits for every row, generated from the manifest | `corpus_fetch.py attribution` |
| `schema/annotation.schema.json` | The annotation format, exported from `scripts/eval/qrep_eval/annotation.py` | `python scripts/eval/qrep_eval/annotation.py` |
| `annotations/<photo stem>.json` | Proposed truth for tier A and refusal photos; D3b adds verified truth beside it | D3a proposals, D3b ingest, the dev annotate page (C3a) |
| `images/` | At most 10 downsized copies (800 px or less) for the examples and smoke tests | D3a |
| `private/` (main checkout only, gitignored) | The image cache and the private tiers; never committed | fetch scripts, D3c |

Every fetched image lives in the main checkout's `corpus/private/cache/` (WORKER.md R1, its
private-data exception), so every worktree reads one copy and no fetched image can be staged. A
manifest row names that copy by its path relative to `corpus/` (`private/cache/<name>.jpg`);
a row that licenses a committed copy names it as `images/<name>.jpg` instead, and its source
image still sits in the cache under the same name.

## Sources

Each object needs its institution's own per-object rights flag; a rights argument such as
PD-Art, or a bare Wikimedia Commons tag, never clears an image (data-56). `corpus_fetch.py`
refuses every host off its allowlist, redirects included.

Accepted:

| Source | Rights flag stored in each row | License recorded | Policy |
|---|---|---|---|
| The Metropolitan Museum of Art (collection API: search v1.1, object records v1) | `isPublicDomain=true` | CC0-1.0 (the Met dedicates its open-access images CC0) | https://www.metmuseum.org/about-the-met/policies-and-documents/image-resources |
| Smithsonian Open Access (api.si.edu; images from ids.si.edu and its own media bucket on registry.opendata.aws) | `media.usage.access=CC0` | CC0-1.0 | https://www.si.edu/openaccess |
| Art Institute of Chicago (api.artic.edu, with the AIC-User-Agent header) | `is_public_domain=true` | PDM-1.0 (AIC marks the work public domain) | https://www.artic.edu/image-licensing |
| LACMA (hand-picked after a screened sample) | `publicDomain=1` (its object page flag; restricted objects carry 0 and offer no download) | PDM-1.0, cited with www.lacma.org as LACMA asks | https://www.lacma.org/about/contact-us/terms-use |

Rejected, with the reason:

| Source | Why |
|---|---|
| V&A | Its terms allow non-commercial use only, cap images at 768 px and forbid caching beyond four weeks (data-11). Never stored anywhere. |
| Quilt Index | Rejected for the corpus by the sprint's rights review (data-12): it offers no per-object open-access flag to rely on. Never stored anywhere. |
| International Quilt Museum | Its images are copyrighted and licensed for fees (data-13). Never stored anywhere. |
| Library of Congress quilt contest images | Mixed rights and modern designs (data-14). Never stored anywhere. |
| Mia (Minneapolis Institute of Art) | Its image terms conflict (data-05, data-59). Not fetched; a Mia image may sit only in the private tier until Mia confirms its terms in writing. Its on-point Double Irish Chain variant (123326) belongs to the private refusal tier. |
| Wikimedia Commons | Mixed licenses (data-06); a CC BY or CC BY-SA file needs attribution terms this corpus does not carry, so none is kept in the repo or the cache. |
| Cleveland Museum of Art | Too few bed quilts to justify a fetcher (data-09). |
| Rijksmuseum | Almost no pieced quilts (data-10). |
| QUILT-1M | A histopathology dataset, not quilt data (data-15). |
| Fabric-company and designer patterns | Licensed for personal use; private cross-checks only (data-39). |
| Modern designer quilts | A specific quilt's layout together with its colors can be protected (Boisson v. Banian, 2d Cir. 2001; data-55), and a museum's rights flag clears the photo, not the design. No photo or cell model of one is committed or cached: the fetch skips any object whose record dates it 1930 or later, and any object it cannot date, before fetching its image; the manifest's `date_end` records the last year each record gives. |

### Why traditional block layouts may be hand-authored as truth

The U.S. Copyright Office does not register common geometric shapes or familiar symbols and
designs, or mere variations of them (Compendium of U.S. Copyright Office Practices, Third
Edition, sections 906.1 and 906.2,
https://www.copyright.gov/comp3/chap900/ch900-visual-art.pdf). Traditional blocks such as the
nine patch, the Irish chain and the half-square triangle are such shapes in grid arrangements
(data-54), so D3b's gold layouts record a traditional block's geometry by hand, and the colors
come from the photo of a public-domain object.

## Fetching

```bash
python scripts/eval/corpus_fetch.py search            # records, rights flags and filters
python scripts/eval/corpus_fetch.py download          # images into the cache, sha256 checked
python scripts/eval/corpus_fetch.py verify            # re-hash every cached image
python scripts/eval/corpus_fetch.py attribution       # regenerate ATTRIBUTION.md
python scripts/eval/corpus_fetch.py --recheck         # E4, before a release
```

- **Rate:** at most one request per second across all hosts, which keeps AIC under its 60
  requests per minute; the User-Agent and AIC-User-Agent carry the project URL and no personal
  contact.
- **Smithsonian key:** no api.data.gov key is used. DEMO_KEY allows 30 requests per hour and 50
  per day per IP (api.data.gov developer manual), and api.si.edu reported `X-Ratelimit-Limit:
  10` on 2026-10-10. One search with `rows=1000` returns every CC0 quilt image record, so the
  fetch spends one DEMO_KEY request and `--recheck` one more. The answer is cached under
  `private/cache/raw/`, and screening reruns read the cache with no request.
- **Which records:** the Met's v1.1 title search for quilt with images, AIC's public-domain
  artworks whose title matches quilt, and Smithsonian CC0 image records titled quilt or typed as
  a quilt (many carry only a pattern name, such as Double Irish Chain, as their title). Titles
  set the order of screening; the tier comes from the image.
- **Image hosts on 2026-10-11:** the Smithsonian image host, ids.si.edu, served a certificate that
  expired on 2026-10-09 (`SEC_E_CERT_EXPIRED`) until it was renewed (valid from 2026-10-10). Its
  `ids/download` address redirects most images to Smithsonian Open Access's own media bucket,
  `smithsonian-open-access.s3-us-west-2.amazonaws.com`, which
  https://registry.opendata.aws/smithsonian-open-access documents as the program's CC0 media store;
  the allowlist admits that one bucket host and no other amazonaws.com host. 138 of the 140
  Smithsonian candidates are fetched; two Cooper Hewitt scans (chndm 1938-27-1 and 1938-57-1213,
  186 and 191 megapixels) exceed Pillow's decompression-bomb limit and are not cached, because the
  fetch does not lift that limit. AIC's image server, www.artic.edu/iiif, answers every request
  with a Cloudflare challenge (HTTP 403, `Cf-Mitigated: challenge`), and the fetch does not work
  around bot protection, so the AIC candidates wait in the cache's candidate list (#208).
- **The recheck** re-reads every row's live record and fails when the record cannot be read, when
  its rights flag differs from the row's own `rights_flag`, or when a policy page the rows cite
  does not answer HTTP 200 at its own URL. It fails closed: there is no manual escape. On
  2026-10-11 a scripted read got 429 from the Met's policy page, 403 from Smithsonian Open
  Access's and 200 from LACMA's, so the recheck fails on two policy pages until #219 is resolved.

## v0 counts (2026-10-11)

Records searched: Met 184 (116 kept with `isPublicDomain` true and a primary image), AIC 114
(113 kept, one undated; images blocked), Smithsonian 382 CC0 image records (140 kept: quilts
dated before 1930; 138 images fetched), LACMA 25 hand-picked from 115 public-domain search
results. Screened from the image: 279 photos, Met 116, Smithsonian 138 and LACMA 25.

| Tier | Photos | Share of the 279 | By source | Classes | In the holdout |
|---|---|---|---|---|---|
| A | 13 | 4.7 percent | LACMA 5, Smithsonian 8 | squares 8, hst 2, qst 2, snowball 1 | 2 |
| B | 31 | 11.1 percent | LACMA 6, Met 11, Smithsonian 14 | squares 14, flying_geese 6, hst 6, qst 4, snowball 1 | 8 |
| R | 131 | 47.0 percent | LACMA 12, Met 57, Smithsonian 62 | applique 39, on_point 32, medallion 20, curve 15, diamond_star 15, hexagon 10 | 42 |
| X | 104 | 37.3 percent | LACMA 2, Met 48, Smithsonian 54 | whole_cloth 53, outside_classes 30, partial_view 10, not_a_quilt 10, unreadable 1 | 38 |

In scope (tiers A and B): 44 of 279, 15.8 percent. The setup screen expected about 15 tier A
photos across all four sources; with the AIC images blocked, v0 finds 13. The Smithsonian Double
Irish Chain 2013.67.2 (`smithsonian-saam-2013-67-2`) is an on-point refusal. The NMAH slide
scans, color slides inside a black film surround (on a blue board, except 556592 on black
with a ruler), are
`smithsonian-nmah-556281` to `556284`, `556288` and `556592`; the three in-scope ones (556283,
556284 and 556288) are tier B, and neither proposal pass found an accession label inside them
to mask. The masks in v0 cover the labels, captions, rulers and color bars that the passes found
on nine refusal photos.

The first screen (2026-10-10) used a seventh refusal class, `other`, which plan D3a does not
list. The 52 photos it held were screened again from the image on 2026-10-11 with the six
classes only: 45 fit none of them and moved to tier X (whole_cloth 34, outside_classes 7,
not_a_quilt 4), 3 read as in scope with a stress and moved to tier B (lacma-54874, lacma-54905,
met-13894), and 4 took a refusal class (met-13596 curve, met-13885 medallion, met-13910
on_point, met-701310 applique). Whether the whole-cloth and other unclassed refusals belong back in
the refusal tier under a seventh class is a question for Jake on PR #214.

**The v0 eval set** is the rows whose `eval_set` column reads `v0`: every tier A photo (13) and
78 refusals, weighted toward look-alikes of in-scope quilts: every on_point (32), curve (15),
diamond_star (15) and hexagon (10) refusal, plus the first three medallion and the first three
applique stems in sort order (lacma-54813, lacma-54852, met-13865, met-13867, met-13870,
met-13874). The holdout takes 2 of the 13 tier A photos and 25 of the 78 refusals, so the
development side holds 11 and 53. Every tier A and refusal photo has an annotation, whether or
not it is in the eval set. Committed copies (`images/`): five tier A photos (all LACMA), one
tier B (met-854571) and two on-point refusals (met-13905, lacma-58735), for the examples and the
smoke tests.

## Tiers and classes

Screening looks at each photo at a size where the piecing shows (700 px screen tiles) and
records a tier and a class:

| Tier | Meaning | Classes |
|---|---|---|
| A | Clean and in scope: the whole quilt, frontal and flat, pieced on one straight uniform square grid from squares (merged runs included), half-square or quarter-square triangles, snowball corners or flying geese, with plain border bands; sashing and cornerstones count when they sit on that grid | squares, hst, qst, snowball, flying_geese |
| B | In scope but a stress case: scrappy, log cabin or Trip Around the World, or photo problems (tilt, folds, drape, low resolution), and the NMAH slide scans, whose labels a mask covers when one shows | as tier A |
| R | Refusal: a look-alike that QREP must refuse, in one of the six classes plan D3a lists | on_point, curve, applique, medallion, hexagon, diamond_star |
| X | Excluded from every eval set; whole_cloth has no piecing to read, and outside_classes is out of scope with none of the six refusal classes | partial_view, duplicate, not_a_quilt, unreadable, whole_cloth, outside_classes |

The class names the unit that sets the read's difficulty: `squares` when only squares are used,
otherwise the triangle or stitch-and-flip unit that covers more of the quilt. A museum photo's
capture is `museum_scan`. `commit_ok` is `yes` when the image may be committed (its row clears
it and it shows no person).

## Manifest columns

`file` and `license` are the columns corpus-guard requires. `sha256` is the source image's hash
as fetched; the fetch check and the holdout rule read it. `file_sha256` is filled only for a
committed copy, with that copy's own hash, because corpus-guard matches committed bytes against
`file_sha256` when it is filled and against `sha256` otherwise. `finished_in` is parsed from
`dimensions_text` as `~width x height` in inches and is approximate: an unlabeled museum pair
reads height by width, H. and W. labels win over order, and a depth is dropped. `px_w` and
`px_h` are the source image's size, which is the annotations' canvas. Museums disagree on
which number comes first, so `finished_in` is turned to match the photo: the quilt's longer side
is the photo's longer side. `date_end` is the last year the record's date gives (a range's end,
a century's last year, or a decade's last year). `eval_set` reads `v0` for a row in the v0
eval set and is empty otherwise. Text from the museums
keeps its words; en and em dashes become hyphens under the repo's text rule.

## Holdout rule

A photo belongs to the holdout when the integer value of the first 8 hex digits of its source
image's manifest `sha256` is divisible by 3: `int(sha256[:8], 16) % 3 == 0`, about a third of
each tier. Every spike and tuning script excludes those photos from the start; use
`qrep_eval.annotation.in_holdout(sha256)` rather than restating the rule. D3b commits the
holdout manifest, `corpus/holdout.json`, when the corpus freezes, and it stays frozen with the
gate (plan section 8.2).

## Annotations

One file per photo, `annotations/<photo stem>.json`, valid against
`schema/annotation.schema.json`. It names its photo by the manifest's `file` value and the
source image's `sha256`, and records `canvas` as that image's `[width, height]`. Coordinates are
source-image pixels, whichever file `photo` names, so
`qrep_eval.annotation.to_read_request` takes the pixel size of the image it stages and scales
the corners from the canvas to it, with a zero crop offset. Those identity fields are not
claims: they bind the file to its manifest row, and the licensed-photo check compares each one
with that row.

Each annotated field (frame, counts, construction_class, refusal_class, fabrics,
finished_size, capture, device_class, masks, gold_layout, and the photoreal sidecar's quad,
grid, repeat_cells and character) is a list of claims, each a value
with a provenance code:

| Code | Meaning | Gate truth |
|---|---|---|
| proposed-a, proposed-b | Two independent proposals (proposer A, proposer B), made in passes that never saw each other or any QREP output | Never |
| verified-jake | Jake confirmed it on the dev annotate page | Yes: corners, bands and counts |
| adjudicated | Jake decided a disputed square on zoom tiles | Yes, with hand-authored, for squares |
| hand-authored | A drafted gold layout (D3b) | Yes, with adjudicated |
| source-record | Copied from the institution's own record, such as the finished size from its dimensions text | Never |

The frame is the outer edge with its border bands from the outside in (each band's width in
finished squares; no border means no bands), plus the field corners when they can be seen;
counts are blocks across and down, with squares per block on each axis. These are
`qrep/contract.py`'s own models, so the annotation maps straight to a read request
(`qrep_eval.annotation.to_read_request`).

A committed annotation must name a photo with a CC0-1.0 or PDM-1.0 row whose `sha256` and size
match, under that photo's own stem (`tests/eval/test_corpus_manifest.py` checks it, the rule of
issue #113). Annotations of private photos stay under `corpus/private/`, because a cell model can
reveal a modern design (plan section 8.2).

## v0 proposals and the disagreements for D3b

Two passes, proposed-a and proposed-b, each read every tier A photo, every refusal and the three
tier B slide scans. Each pass saw only the cached photos and the format, through
`scripts/eval/corpus_screen.py` views whose grid labels are source pixels; neither saw the
other's answers or any QREP output. Each pass was told which photos to frame and count (the
screen's tier A) and which to classify only, so the split itself carries the screen's call; the
classes were the passes' own. Each tier A photo got the outer edge, the bands, the field corners
where visible, the counts, the class and a fabric count; every other photo got its class, and a
mask over any label, caption, ruler or color bar in frame. Nothing here is truth until D3b
verifies it.

The proposals come from two rounds. Round 1 (2026-10-10) classified 38 refusals that keep its
claims. Round 2 (2026-10-11) framed and counted all 13 tier A photos, the five LACMA ones again
with a brief that counts sashing and cornerstones on the grid as part of the field, and
classified 96 photos: 93 refusals and the three slide scans. In round 2 a helper script that
both classifying agents kept in one shared scratch folder was overwritten, so pass A's answers
for 38 photos were written into pass B's folder for a few minutes before pass B wrote its own.
Those 38 pass B files were set aside, and a fresh pass B, which never saw them, classified the
38 photos again; those are the proposed-b claims. The tier A frames and counts came from four
other agents, two per pass, each writing only its own pass's folder; none of their files is
identical to the other pass's, so their agreement on counts is the passes' own.

The 13 tier A photos agree on counts in both passes, and their outer corners lie within 0.25
percent of the image diagonal of each other. Points for D3b:

- lacma-63267 is 19 by 23 squares: sashing about one square wide runs between the blocks and
  down both sides, so equal blocks are impossible and both passes record one block per axis.
  The stair-step quilts (lacma-60126, smithsonian-saam-1998-149-21, smithsonian-saam-2013-67-17)
  and the sashed four-patch smithsonian-saam-2013-67-9 are recorded the same way.
- lacma-54904's border is about 6 squares deep at the top and bottom but about 3 at the sides,
  which one band width cannot express (both passes recorded an average).
- smithsonian-saam-2016-57-2 has a sawtooth row inside its border: pass A records it as a 0.9
  square band (three bands), pass B folds it into a 3.0 square band (two bands). A pieced row
  may also put the quilt out of tier A.
- Band widths differ by up to 0.1 square on six photos (proposed-a against proposed-b):
  lacma-54871 2.2/2.15 and 0.7/0.65, lacma-54904 0.5/0.4 and 4.7/4.8, lacma-63229 2.9/2.85,
  smithsonian-chndm-1973-45-1 0.25/0.3, 1.3/1.35 and 1.5/1.45, smithsonian-saam-1998-149-21
  1.4/1.5, and smithsonian-saam-2017-24-27 1.05/1.1; at a 4 inch square, 0.1 square is 0.4 inch,
  beyond G1's quarter inch, so D3b verifies each.
- Fabric counts differ on four photos: smithsonian-nmah-556322 (9 against 10),
  smithsonian-saam-2013-67-9 (8 against 7), smithsonian-saam-2016-57-2 (2 against 3) and
  smithsonian-saam-2017-24-27 (4 against 3).

Classes that disagree, between the passes or with the screen (`manifest.csv` class):

| Photo | Screen | proposed-a | proposed-b |
|---|---|---|---|
| lacma-59557 | R on_point | on_point | hst |
| lacma-63229 | A snowball | hst | hst |
| met-13870 | R medallion | applique | medallion |
| met-13873 | R applique | on_point | on_point |
| met-13915 | R on_point | applique | on_point |
| met-854567 | R curve | applique | diamond_star |
| met-855674 | R applique | medallion | applique |
| smithsonian-nmaahc-2013-215-4 | R applique | curve | curve |
| smithsonian-nmah-556469 | R medallion | medallion | applique |
| smithsonian-nmah-556492 | R applique | medallion | applique |
| smithsonian-nmah-556599 | R applique | medallion | applique |
| smithsonian-saam-1998-149-19 | R medallion | medallion | applique |
| smithsonian-saam-1998-149-2 | R medallion | medallion | applique |
| smithsonian-saam-1998-149-30 | R medallion | on_point | hst |
| smithsonian-saam-1998-149-32 | R medallion | applique | applique |
| smithsonian-saam-1998-149-5 | R medallion | medallion | applique |
| smithsonian-saam-2016-57-2 | A hst | squares | squares |
| smithsonian-saam-2016-57-7 | R on_point | on_point | qst |

Three refusals (lacma-59557, smithsonian-saam-1998-149-30, smithsonian-saam-2016-57-7) are read
in scope by one pass, so D3b decides whether each moves to tier A; they have no frame or count
proposals yet, because the passes classified them only.

The committed copies under `images/` are downsized; an annotation of one names that copy in
`photo` but keeps the source image's `sha256` and `canvas`, so `to_read_request` takes the size
of the image it stages and scales the corners from the canvas to it.
