# QREP Sprint 4 research

Status: synthesized 2026-07-10 from a 10-agent research fleet (5 web, 5
social-leaning; Reddit and X were tool-inaccessible, so "social" coverage
leans on quilting forums, designer blogs, and errata pages - flagged per
finding in the fleet transcripts) plus four local detector spikes run
against the three sprint 3 field photos and the photoreal fixture corpus.
This doc is the planning input for docs/sprint-4/qrep-sprint-4-plan.md;
anything not in the verdict table does not enter the plan.

## The spike evidence (local, reproducible, ours)

Peak-contrast lattice evidence: normalized 2D FFT autocorrelation of the
high-passed best Lab channel; at each axis fundamental p, SNR of the
autocorr peak over its local non-peak background (median/std), averaged
over harmonics k=1..3, min over axes. Measured:

| Case | SNR | period found | note |
| ---- | --- | ------------ | ---- |
| Irish chain field photo | 2.16 | (37,36) | true 2-cell block; 1D pitch (18.2,17.7) is CORRECT today at prominence 0.472 < T1 |
| Old Mill Wheel field photo | 2.19 | (21,21) | isotropic block lattice where 1D reads garbage (32.3,13.4) |
| Star quilt field photo | 5.44 | (135,136) | true motif where 1D locks 7 px texture |
| render_on_white fixture | 2.89 | (144,144) | passing fixture stays strong |
| drunkards_path fixture | 2.91 | (173,172) | curved fixture stays strong |
| hst_star fixture | 3.08 | (173,172) | |
| solid_fabric fixture | 0.05 | - | negative control |
| gaussian noise | 0.00 | - | negative control |

At the phone 1400 px cap: Irish chain 3.13, star 6.10 (both STRONGER),
mill wheel 0.00 because the fixed detrend sigma (5% of inset) approaches
its shrunken ~10 px period - the evidence stage must sweep detrend scale.
End-to-end: painting the Irish chain's assigned cells at today's rejected
grid visually reproduces the quilt (49x49, mean cell confidence 0.77) -
the pipeline already recovers it and refuses to show it.

Two honest negatives, carried into scope decisions below: (1) busy_print
INVERTS (texture 22 px SNR 3.49 > true 92 px lattice 0.95), so peak
contrast certifies lattice PRESENCE but cannot select between nested
lattices - the #82 class needs a different mechanism and stays open.
(2) No literature source directly tests 1D projections on curved quilt
seams; that failure mode is our own measurement plus a document-skew
analogy (fleet agent flagged the gap explicitly).

## Verdict table

| Feature | Verdict | Effort | Evidence |
| ------- | ------- | ------ | -------- |
| Peak-contrast 2D lattice evidence stage (Lab channel sweep, scale-swept detrend, SNR statistic) | Adopt-now | M | Spike table above; literature consensus is local/2D evidence over 1D projections (Park/Liu TPAMI 2009; PLOS ONE fabric survey 2026; Chen & Tokuda regional-vs-global) |
| Evidence period fused into the existing integer-ratio pitch feedback (rescue/lock the 1D read) | Adopt-now | S-M | Irish chain: period 36 / pitch 18.2 = 1.98, integer confirms; feedback path already exists in grid.py |
| New structured diagnosis + honest copy for block-lattice-only reads (replaces wrong "steep angle" message on curved quilts) | Adopt-now | S | Mill wheel measurement; sprint 3 verdict-copy system keys off structured diagnoses already |
| Crop-aware downscale (downscale AFTER crop so a small quilt region keeps its pixels) | Adopt-now | S | Phone-cap spike; Jake's real photos are screenshots where the quilt is a fraction of frame |
| New-literal governance: evidence thresholds proposed via S0-style baseline report, frozen by Jake before implementation slices | Adopt-now | S (process) | Sprint 3 threshold rite; avoids metric-swapped-under-frozen-threshold dishonesty |
| Rights-clean degraded fixture corpus (renders pushed through screenshot-like degradation: JPEG, downscale, recompress, low contrast) | Adopt-now | M | Sprint 3 fixture sweep missed all three field failures; field photos are rights-unclean and gitignored |
| Single consolidated pattern document replacing the five separate downloads | Adopt-now | M-L | Canonical section order converges across 5 independent pattern-writing sources AND an 8-PDF page-by-page structural read (5 publishers, 44 pages): cover-only page 1 in 8/8, materials as page 2 in 8/8, inline "fig N" diagrams in 8/8, dedicated layout diagram in 7/8; "all information in one document" precedent (Shannon Fraser Designs); EQ8 printout types and YouPatch's 17-page PDF as market anchors |
| Cover page: generated name, rendered quilt image, finished size, honest technique line | Adopt-now | S | Cover elements converge (phoebemoon, sherriquiltsalot, stringandstory); skill-level taxonomies are designer-specific so QREP states techniques, not a star rating |
| Original photo + recovered pattern side-by-side page inside the document | Adopt-now | S | Jake's requirement; fraud-advisory research shows a real photo is the trusted convention; photo bytes are already client-side (session-only contract holds) |
| Deterministic quilt-name generator (palette mood word + block/structure word, seeded by content hash; collision-suffix within saved projects) | Adopt-now | S | Documented designer method is exactly theme word + feature word (thecraftynomad); "no correct name" and duplicates are normal (Brackman); no prior-art name generator exists |
| Print conventions baked in: US Letter, print-at-100% note, 1-inch calibration square, name + page number in footer, ink-conscious layout | Adopt-now | S | Near-universal print-at-100%/test-square convention (quiltingdaily, quiltingdigest); EQ8 prints project name in footer; fit-to-page mis-scaling is the industry gotcha |
| Coloring page (blank line-art grid of the recovered quilt) | Adopt-now | S | Bundled coloring page is near-universal in modern listings (Suzy Quilts, Then Came June, Pen+Paper, multiple Etsy listings) |
| Stated yardage assumptions in the document (40 in usable WOF, seam allowance, finished-vs-cut sizes) | Adopt-now | S | 40 in convention (quiltweb, inklingo); top verified complaint classes are wrong cutting math, missing seam-allowance statement, yardage on wrong WOF |
| Mobile lightbox rebuild: dvh sizing, body scroll lock, top-anchored scrollable overlay, stacked compare with labels on narrow screens | Adopt-now | M | Code reading (78vh centered flex clips; two 84vw panels always wrap); iOS 26 fixed-position offset regression is current and unresolved (WebKit bug 297779, corroborated 4x) |
| Mobile-viewport WebKit e2e for the photo flow + lightbox (Playwright device emulation) | Adopt-now | S-M | Sprint 3 shipped the lightbox bug with desktop-only e2e; named review upgrade |
| A4 variant of the document | Adopt-later | S | Market ships Letter+A4 (modernquiltpatterns FAQ); Letter-first with 100%-scale note is the honest v1 |
| Fabric organization labels/tags page | Adopt-later | S | Market extra (Then Came June, Pen+Paper), not canon |
| Busy-print nested-lattice selection (issue #82) | Adopt-later | M | Spike proves SNR alone inverts on it; needs cell-coherence cross-check mechanism, separate from this sprint's evidence stage |
| Overlay slider compare on phones | Adopt-later | M | Compare-slider libraries carry iOS-specific drag caveats (touch-action; use-gesture #486); stacked-with-labels suffices for v1 |
| Per-row phase refinement for wavy fabric boundaries | Adopt-later | M | Line-snap exists; adopt only if the degraded corpus shows dim errors after fusion |
| Full deformed-lattice machinery (MSBP/TPS, PatchMatch lattice) | Cede | L | Research-grade; classical peak-contrast + fusion already certifies the three field photos (spike); revisit only if the corpus proves otherwise |
| Deep-learning lattice detection | Cede | - | Out of the OpenCV-wasm envelope; PLOS ONE survey notes no annotated datasets for this task |
| Non-grid piecing in the model (curves/triangles as templates) | Cede | - | Stays issue #17 per design doc; sprint 4 detects and reports honestly, does not represent |
| Reference-object absolute scale | Cede | - | Stays issue #19 |
| PDF layers / DRM / download caps / A0 copyshop format | Cede | - | Garment-market or store-policy mechanics, not document content |

## Recommended build sequencing

- Phase 1 (this sprint): evidence stage + fusion + new diagnosis/copy +
  crop-aware downscale + degraded corpus + threshold-freeze rite; the
  consolidated document with cover, name generator, side-by-side page,
  coloring page, print conventions; mobile lightbox rebuild + WebKit
  mobile e2e. Rationale: the three user-visible failures (photos read as
  no_grid, five confusing downloads, broken phone compare) each map to
  exactly one track.
- Phase 1.5 (fast follows, if sprint capacity allows): A4 variant,
  fabric tags page.
- Phase 2 (next sprint candidates): #82 nested-lattice selection, phone
  overlay slider compare, per-row phase refinement.
- Never (recorded so the plan does not argue with them again): DL
  detection, full deformed-lattice machinery, #17 model expansion, #19
  reference scale - see DECISIONS.md entries at plan approval.

## Ceded and impossible

- Perfect star-quilt CELL recovery this sprint: the motif is certified
  (SNR 5.44) but pale HST content classification remains risky; the plan
  scopes the star photo's acceptance at an honest verdict (trusted
  repeat, non-square or low-confidence read), not a perfect pattern.
- "Skill level" as a numeric rating: research shows no standardized
  system; QREP states its honest technique facts instead.
- Reddit/X as evidence sources: tool-blocked this cycle; forum/blog/
  errata substitutes carried the complaint taxonomy.

## Sources

Detector: pubmed.ncbi.nlm.nih.gov/19696451 (Park/Liu TPAMI 2009);
epubs.siam.org/doi/10.1137/18M1234400 (LISA); journals.plos.org/plosone
e0340797 (fabric repeat survey); arxiv.org/abs/cs/0005001 (regional vs
global); faculty.cc.gatech.edu/~hays (ECCV 2006); calebrob.com FFT demo;
docs.opencv.org CLAHE; pyimagesearch.com CLAHE guide.

Pattern content: quiltweb.com/how-to-tech-edit-a-quilt-pattern;
meadowmistdesigns.blogspot.com Pattern Writing 101 (2016);
aquiltinglife.com pattern-writing tips; stringandstory.com,
phoebemoon.com, alderwood-studio.com, thequiltedlab.com, mrsquilty.com
how-to-read guides; snugglesquilts.com abbreviations;
elizabethhartman.com (skill-level guide, errata, FAQ);
modernquiltpatterns.com/pages/faq; shannonfraserdesigns.ca single-PDF
filing; quiltingdaily.com + quiltingdigest.com print-at-100%;
guiltyquiltystudio.com (copyright placement, difficulty ratings,
diagram standalone rule); inklingo.com yardage math.

Market/listings: fatquartershop.com (Shine 19pp, Thrive 18pp, Maypole
10pp); thencamejune.com listings; penandpaperpatterns.com listings;
loandbeholdstitchery.com; etsy.com listing snippets (flagged
unfetched); homemadeemilyjane.com coloring pages; youpatch.com +
eastdakotaquilter review (17pp delivered PDF); support.electricquilt.com
(printout types, yardage-estimate caveats, 100% printing);
help.prequilt.com download types; quiltassistant.com; accuquilt.com.

Complaints/errata: quiltingboard.com threads (seam allowance t109217,
t192455; cutting error t248454; WOF t132183; template t25393; block size
t204687; kit t61170; finishing t247793; diagrams t131658);
elizabethhartman.com/pages/errata; missouriquiltco.com block-corrections;
busyhandsquilts.com/pages/errata; quiltylove.com pattern-corrections;
quiltingjetgirl.com pattern-testing comments.

Naming: barbarabrackman.blogspot.com (no-correct-name);
antiquequilthistory.com (20 names for Hole in the Barn Door);
thecraftynomad.co.uk naming method (2020); sherriquiltsalot.com
whats-in-a-name (2024); quiltersatfirst.com (2023); materialgirlfriends
Wallah collision; quiltingboard.com t293668.

iOS: bugs.webkit.org 297779 (iOS 26 fixed/sticky offset, unresolved),
195325 (canvas memory, fixed 2023), 261331 (WebGL context lost, iOS 17),
221530 (wasm memory unpredictability); pqina.nl canvas-area limit;
github.com/fabricjs/fabric.js/9585; github.com/godotengine/godot/70621
(wasm memory cap on iOS); caniuse.com (offscreencanvas,
createimagebitmap, viewport-unit-variants, aspect-ratio);
hazelduvall.dev 2024-09-14 aspect-ratio ordering bug;
github.com/pmndrs/use-gesture/486 (touch-action drag).

Delivery norms: modernquiltpatterns.com FAQ (ZIP with Letter+A4, 97.7%
shrink note); cestlasara.com printing guide; tintofmintpatterns.com
size explainer; elizabethhartman.com Show-and-Tell 61pp;
guiltyquiltystudio.com copyright essentials.

Directly-read pattern PDFs (page-by-page structural evidence, 8 files /
5 publishers / 44 pages): cloud9fabrics.com Sea-Glass-Quilt.pdf (2016,
8pp), Village-Life-Project-Sheet2.pdf (2015, 3pp), RIBBON-BOX (2023,
4pp, lettered A-H swatch+SKU+cut chart), JUST-DOTTY (2023, 3pp);
fatquartershop.com sample 10993 = AGF Evergreen (2020, 10pp, dedicated
binding section with diagrams B1-B3 + closing page + 1-inch test square
on templates), sample 12508 = Moda Peach Cobbler (2025, 4pp);
robertkaufman.com MilkyWay-Moonlight.pdf (2020, 6pp, "Notes Before You
Begin" assumptions box: seam allowance, pressing, WOF, RST);
suzyquilts.com DuvalStarPattern.pdf (2023, 6pp, TERMS glossary page,
two-size fabric table, dedicated finishing section, bundled coloring
page). Cross-cutting: cover-only page 1 (8/8), materials page 2 (8/8),
"fig N" inline diagrams (8/8), dedicated layout diagram (7/8),
difficulty label on cover (3/8), dedicated binding section (2/8, the
two most designer-branded patterns).
