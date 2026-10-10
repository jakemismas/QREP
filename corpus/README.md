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
| Smithsonian Open Access (api.si.edu) | `media.usage.access=CC0` | CC0-1.0 | https://www.si.edu/openaccess |
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
| Modern designer quilts | A specific quilt's layout together with its colors can be protected (Boisson v. Banian, 2d Cir. 2001; data-55), and a museum's rights flag clears the photo, not the design. No photo or cell model of one is committed or cached: the fetch skips any object whose record dates it 1930 or later before fetching its image. |

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
- **Blocked on 2026-10-10:** two image hosts refused scripted downloads, so v0 holds Met and
  LACMA images only, and the AIC and Smithsonian candidates wait in the cache's candidate list.
  The Smithsonian image host, ids.si.edu, served a certificate that expired on 2026-10-09
  (`SEC_E_CERT_EXPIRED`); the fetch never turns certificate checks off. AIC's image server,
  www.artic.edu/iiif, answered every request, info.json included, with a Cloudflare challenge
  (HTTP 403, `Cf-Mitigated: challenge`); the fetch does not work around bot protection. Rerun
  `download --source smithsonian` or `--source aic` when the hosts serve scripted clients again,
  then screen the new images.
- **The recheck** re-reads every row's live record and fails when its rights flag no longer
  clears, the record is gone, or a policy page answers 404 or 410. The policy pages answered
  scripted reads with 403 or 429 on 2026-10-10, so a blocked page is left to the release's human
  check.

## v0 counts (2026-10-10)

Records searched: Met 184 (116 kept with `isPublicDomain` true and a primary image), AIC 114
(all kept; images blocked), Smithsonian 382 CC0 image records (149 kept: quilts made before
1930; images blocked), LACMA 25 hand-picked from 115 public-domain search results. Screened from
the image: 141 photos, Met 116 and LACMA 25.

| Tier | Photos | Share of the 141 | By source | Classes | In the holdout |
|---|---|---|---|---|---|
| A | 5 | 3.5 percent | LACMA 5 | squares 3, hst 1, snowball 1 | 0 |
| B | 14 | 9.9 percent | Met 10, LACMA 4 | squares 7, qst 3, flying_geese 3, snowball 1 | 4 |
| R | 117 | 83.0 percent | Met 102, LACMA 15 | other 52, applique 24, on_point 12, diamond_star 10, medallion 9, curve 6, hexagon 4 | 41 |
| X | 5 | 3.5 percent | Met 4, LACMA 1 | partial_view 4, unreadable 1 | 3 |

In scope (tiers A and B): 19 of 141, 13.5 percent. The setup screen expected about 15 tier A
photos across all four sources; with the AIC and Smithsonian images blocked, v0 finds 5, all
LACMA. Of the 52 `other` refusals, most are whole-cloth quilts, which look nothing like an
in-scope quilt.

**The v0 eval set** is the annotated subset: every tier A photo (5) and 44 refusals, weighted
toward look-alikes of in-scope quilts: all 12 on point, all 10 diamond stars, all 6 curves,
all 4 hexagons, the 6 in-scope designs refused for a pieced border or a mixed set (met-13885,
met-13894, met-13910, lacma-54874, lacma-54905, lacma-60154), and 3 each of medallion and
applique (the first three stems in sort order). The other 73 refusals stay in the manifest's
refusal pool, unannotated. Committed copies (`images/`): the 5 tier A photos, one tier B
(met-854571) and two on-point refusals (met-13905, lacma-58735), for the examples and the smoke
tests.

## Tiers and classes

Screening looks at each photo at a size where the piecing shows (700 px screen tiles) and
records a tier and a class:

| Tier | Meaning | Classes |
|---|---|---|
| A | Clean and in scope: the whole quilt, frontal and flat, pieced on a straight square grid from squares (merged runs included), half-square or quarter-square triangles, snowball corners or flying geese, with plain border bands | squares, hst, qst, snowball, flying_geese |
| B | In scope but a stress case: scrappy, log cabin or Trip Around the World, or photo problems (tilt, folds, drape, low resolution, slide scans with accession labels, which a mask covers) | as tier A |
| R | Refusal: a look-alike that QREP must refuse | on_point, curve, applique, medallion, hexagon, diamond_star, other |
| X | Excluded from every eval set | partial_view, duplicate, not_a_quilt, unreadable |

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
`px_h` are the source image's size, which is the annotations' canvas. Text from the museums
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
source-image pixels, so a read request built from an annotation has a zero crop offset; a
consumer that reads a downsized or decoded copy scales by its own factors.

Each annotated field (frame, counts, construction_class, refusal_class, fabrics,
finished_size, capture, device_class, masks, gold_layout) is a list of claims, each a value
with a provenance code:

| Code | Meaning | Gate truth |
|---|---|---|
| proposed-a, proposed-b | Two independent agent proposals, made in passes that never saw each other or any QREP output | Never |
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

Two passes, proposed-a and proposed-b, each read every eval-set photo (2026-10-10). Each pass
saw only the cached photos and the format, through `scripts/eval/corpus_screen.py` views whose
grid labels are source pixels; neither saw the other's answers, the screen's tiers, or any QREP
output. Each tier A photo got the outer edge, the bands, the field corners where visible, the
counts, the class and a fabric count; each refusal got its class. Nothing here is truth until
D3b verifies it.

The five tier A photos agree on counts and class in both passes; their outer corners lie within
1 percent of the image diagonal of each other and their bands within 0.25 squares. Two need a
closer look in D3b: lacma-54904's border is about 6 squares deep at the top and bottom but about
3 at the sides, which one band width cannot express (both passes recorded an average), and
lacma-60126's stair-step bricks have no repeating block, so both passes count it as one block of
21 by 26 squares.

Classes that disagree, between the passes or with the screen (`manifest.csv` class):

| Photo | Screen | proposed-a | proposed-b |
|---|---|---|---|
| lacma-54874 | R other | qst | qst |
| lacma-59557 | R on_point | on_point | hst |
| met-13870 | R medallion | applique | medallion |
| met-13885 | R other | on_point | other |
| met-13915 | R on_point | applique | on_point |
| met-854567 | R curve | applique | diamond_star |

lacma-54874 matters most: both passes read it as an in-scope quarter-square-triangle quilt that
the screen refused for its octagonal rings, so D3b decides whether it moves to tier A.
