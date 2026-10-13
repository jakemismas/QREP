# D4 baseline: the automatic read on the v0 dev split

- Date: 2026-10-13 15:57 UTC
- Command: python scripts/eval/run_eval.py --cache 'C:/Users/Jake Mismas/QREP/corpus/private/cache' --out docs/sprint-5/evidence/D4-baseline --title 'D4 baseline: the automatic read on the v0 dev split' --start-sha 3fa671e --workers 2
- Qrep path: C:\Users\Jake Mismas\qrep-wt\d4a\qrep\__init__.py
- Git sha: 6e6d98f8975861408b7b81074f1cb714dfb413f3
- Start sha check: git diff --quiet 3fa671e HEAD -- qrep/vision/ ':(exclude)qrep/vision/read/' exited 0; git diff --quiet 3fa671e -- qrep/vision/ ':(exclude)qrep/vision/read/' exited 0; qrep imports from C:\Users\Jake Mismas\qrep-wt\d4a\qrep\__init__.py, inside the repo
- Git status: git status --porcelain -- qrep/ scripts/eval/: clean
- Cv2 version: 5.0.0
- Decode path: native: an untouched full-resolution clean image is passed as its source file, which the reader decodes with the same cv2.imread flags (IMREAD_COLOR), so its pixels are identical; every other image is decoded by cv2.imread (IMREAD_COLOR), resized with INTER_AREA to the cap with the app's targetSize rounding, degraded where its condition says, and staged as a lossless PNG
- Split: dev
- Inputs: corpus/manifest.csv, eval_set v0 (sha256 800e36c13104facc9c27d7e217aced9249707b11765bb6966f41bb45dd77e17a), 66 photos in the dev split by tier {'A': 11, 'R': 55}, annotations from corpus/annotations, source images checked against the manifest sha256
- Masks: annotation masks are not applied: the reader sees the whole photo and no score excludes them (#243)
- Readers: auto, auto-corners
- Simulation: corners from the annotation's outer edge (gate truth, else proposed-a, else proposed-b), jitter radii [0, 2, 4, 6, 8] px, 3 draws per nonzero radius, seed 'd4a'; auto-corners receives those corners and a fabric count when 2 to 12 (a square-truth claim, or the proposal on a row that is not gate; a gate row with only a proposed count gives none); the automatic read takes no counts, so the true counts reach only the confirmed reader, with the same corners and fabric count; picker answer 'Works with these' for every photo
- Resolutions: full,desktop-2000,phone-1400
- Full resolution budget: 50 MP per as-fetched unit (corpus.FULL_BUDGET_MP; #166 comments 6145839899 and 6146139041), on every split: a unit whose reader would be handed an uncapped image above it, judged after any degradation that shrinks the image, is never read; its rows stand where its reads would be (auto's read, each corner trial, the confirmed reader's miscounts) and carry skip_kind over_budget, except a corner reader with no frame to confirm, which keeps its no-frame row; they are listed beside every rate, never counted as a read, refusal, success or failure; a capped unit is never over it, and the named fixture rows are outside this tally. In this run: clean units 66 as fetched, 2 skipped; stress units 36 as fetched, 5 skipped; photos skipped: smithsonian-chndm-1972-28-1, smithsonian-chndm-1973-45-1; the largest image read as fetched: 5038 x 7721 px (smithsonian-chndm-1986-27-1). Why: measured 2026-10-13 on dev photos, each step alone in a fresh process, as peak working set / peak commit (#166 comments 6145827537, 6146146558 and 6146429860): at 78e92e3 the automatic read took 0.50 / 1.20 GB at 8.9 MP, 1.18 / 1.88 GB at 15.4 MP and 1.00 / 1.70 GB at 38.9 MP, and under a 5 GB per-process commit cap both the automatic read (a 456 MiB float32 power spectrum in the padded block autocorrelation, qrep/vision/repeats.py) and the glare degradation failed on the 117.5 MP scan; banded in 419388c, glare takes 0.89 / 1.61 GB and the lighting gradient 0.87 / 1.59 GB on that scan, while the read still fails as fetched and is not the eval's to change; the scan's low_res_jpeg unit, which hands the read 541 x 600 px, takes 0.70 / 1.41 GB as fetched
- Degradations: grayscale {}; lighting_gradient {'factor_left': 1.0, 'factor_right': 0.55}; low_res_jpeg {'longest_px': 600, 'jpeg_quality': 40}; gaussian_blur {'sigma_px': 2.0}; glare {'center_of_field': [0.35, 0.35], 'sigma_of_short_side': 0.15, 'peak_blend_to_white': 0.85}; occlusion {'center_of_field': [0.6, 0.6], 'side_of_field': 0.25, 'gray': 128}, applied at every requested resolution, at true corners, to museum tier A photos licensed CC0-1.0
- Truth: 0 gate rows, 1008 provisional rows, 0 conflict rows, 8 synthetic rows
- Proposal disagreements: 0 of 11 tier A photos have proposed-a and proposed-b counts or classes that differ: none
- Low confidence flag: auto readers flag squares below 0.9 (the old app's UNCERTAIN_THRESHOLD); the confirmed reader flags none until its result carries flags (#237); a read with no confidences flags none and its row says confidence_missing

Rates read k/n = rate [Wilson 95 percent interval]; a zero count adds its 3/n bound. Error and skipped rows never enter n; a rate lists them after it. n counts photos: one row per photo, reader, resolution and condition, read at true corners and true counts. Outcomes read read / warned / held / refused. False warning, refusal recall and G4 and G5 count holds and refusals only: a warned read still offers the editor and its PDF. Provisional rows rest on proposals, never on gate truth, and conflict rows carry a verified class that contradicts their tier; neither counts toward a gate. Nothing here is frozen (plan 7.2).

## Section 7.2 metrics

| Reader | Device class | Resolution | Truth | G1 fully correct interior | G2 confident-wrong squares | G4 refusal recall | G5 false warning (true corners) |
|---|---|---|---|---|---|---|---|
| auto | museum scan | desktop-2000 | gate | n = 0 | 0 photos: n = 0 | n = 0 | n = 0 |
| auto | museum scan | desktop-2000 | provisional | n = 0 | 0 photos: n = 0 | 49/55 = 0.891 [0.782, 0.949] | 11/11 = 1.000 [0.741, 1.000] |
| auto | museum scan | full | gate | n = 0 | 0 photos: n = 0 | n = 0 | n = 0 |
| auto | museum scan | full | provisional | n = 0 | 0 photos: n = 0 | 45/54 = 0.833 [0.713, 0.910], 1 skipped (1 over the as-fetched budget) | 9/10 = 0.900 [0.596, 0.982], 1 skipped (1 over the as-fetched budget) |
| auto | museum scan | phone-1400 | gate | n = 0 | 0 photos: n = 0 | n = 0 | n = 0 |
| auto | museum scan | phone-1400 | provisional | n = 0 | 0 photos: n = 0 | 50/55 = 0.909 [0.804, 0.961] | 11/11 = 1.000 [0.741, 1.000] |
| auto-corners | museum scan | desktop-2000 | gate | n = 0 | 0 photos: n = 0 | n = 0 | n = 0 |
| auto-corners | museum scan | desktop-2000 | provisional | n = 0 | 0 photos: n = 0 | n = 0, 55 skipped; no frame or counts on the v0 refusal photos (#243) | 11/11 = 1.000 [0.741, 1.000] |
| auto-corners | museum scan | full | gate | n = 0 | 0 photos: n = 0 | n = 0 | n = 0 |
| auto-corners | museum scan | full | provisional | n = 0 | 0 photos: n = 0 | n = 0, 55 skipped; no frame or counts on the v0 refusal photos (#243) | 9/10 = 0.900 [0.596, 0.982], 1 skipped (1 over the as-fetched budget) |
| auto-corners | museum scan | phone-1400 | gate | n = 0 | 0 photos: n = 0 | n = 0 | n = 0 |
| auto-corners | museum scan | phone-1400 | provisional | n = 0 | 0 photos: n = 0 | n = 0, 55 skipped; no frame or counts on the v0 refusal photos (#243) | 11/11 = 1.000 [0.741, 1.000] |
| auto | all in scope | desktop-2000 | gate | n/a | n/a | n/a | n = 0 |
| auto | all in scope | desktop-2000 | provisional | n/a | n/a | n/a | 11/11 = 1.000 [0.741, 1.000] |
| auto | all in scope | full | gate | n/a | n/a | n/a | n = 0 |
| auto | all in scope | full | provisional | n/a | n/a | n/a | 9/10 = 0.900 [0.596, 0.982], 1 skipped (1 over the as-fetched budget) |
| auto | all in scope | phone-1400 | gate | n/a | n/a | n/a | n = 0 |
| auto | all in scope | phone-1400 | provisional | n/a | n/a | n/a | 11/11 = 1.000 [0.741, 1.000] |
| auto-corners | all in scope | desktop-2000 | gate | n/a | n/a | n/a | n = 0 |
| auto-corners | all in scope | desktop-2000 | provisional | n/a | n/a | n/a | 11/11 = 1.000 [0.741, 1.000] |
| auto-corners | all in scope | full | gate | n/a | n/a | n/a | n = 0 |
| auto-corners | all in scope | full | provisional | n/a | n/a | n/a | 9/10 = 0.900 [0.596, 0.982], 1 skipped (1 over the as-fetched budget) |
| auto-corners | all in scope | phone-1400 | gate | n/a | n/a | n/a | n = 0 |
| auto-corners | all in scope | phone-1400 | provisional | n/a | n/a | n/a | 11/11 = 1.000 [0.741, 1.000] |

- G5 for auto counts its read with no corners, since the automatic read takes none; auto-corners and confirmed count their 0 px trials. The all in scope rows pool G5 over every device class.
- A G4 cell with skipped refusal photos: auto-corners and confirmed take a frame and counts, and the v0 annotations give the refusal photos neither, so those photos are skipped, not scored (#243).
- G2 counts squares, which cluster by photo; its interval treats them as independent, so it is too narrow. The photo count says how many gold photos stand behind it.
- G3: n/a until B3 merges; the automatic read takes no counts, so a miscount cannot be simulated for it; #237 tracks wiring G3
- G6: n/a until A3b merges
- G1 and G2 need gold layouts, and the harness has no gold-layout loader yet (D3b defines corpus/gold/; #237 tracks loading it), so they read n = 0 on the corpus. The named rows below carry synthetic cell truth.

## Per tier and resolution

| Reader | Tier | Resolution | Photos | Rows | Errors | Skipped | Outcomes | Rate | Gate / provisional / conflict rows | Count top-1 | Fabric count exact | Verdicts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| auto | museum tier A (in scope) | desktop-2000 | 11 | 11 | 0 | 0 | 0 / 0 / 0 / 11 | false warning 11/11 = 1.000 [0.741, 1.000] | 0 / 11 / 0 | 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273 | 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273 | no_grid 11 |
| auto | museum tier A (in scope) | full | 11 | 11 | 0 | 1 | 1 / 0 / 0 / 9 | false warning 9/10 = 0.900 [0.596, 0.982], 1 skipped (1 over the as-fetched budget) | 0 / 10 / 0 | 0/10 = 0.000 [0.000, 0.278], 3/n = 0.300, 1 skipped (1 over the as-fetched budget) | 1/10 = 0.100 [0.018, 0.404], 1 skipped (1 over the as-fetched budget) | no_grid 9, readable 1 |
| auto | museum tier A (in scope) | phone-1400 | 11 | 11 | 0 | 0 | 0 / 0 / 0 / 11 | false warning 11/11 = 1.000 [0.741, 1.000] | 0 / 11 / 0 | 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273 | 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273 | no_grid 11 |
| auto | refusal tier | desktop-2000 | 55 | 55 | 0 | 0 | 6 / 0 / 0 / 49 | refusal recall 49/55 = 0.891 [0.782, 0.949] | 0 / 55 / 0 | n = 0 | n = 0 | no_grid 49, readable 6 |
| auto | refusal tier | full | 55 | 55 | 0 | 1 | 9 / 0 / 0 / 45 | refusal recall 45/54 = 0.833 [0.713, 0.910], 1 skipped (1 over the as-fetched budget) | 0 / 54 / 0 | n = 0 | n = 0 | no_grid 45, readable 9 |
| auto | refusal tier | phone-1400 | 55 | 55 | 0 | 0 | 5 / 0 / 0 / 50 | refusal recall 50/55 = 0.909 [0.804, 0.961] | 0 / 55 / 0 | n = 0 | n = 0 | no_grid 50, readable 5 |
| auto-corners | museum tier A (in scope) | desktop-2000 | 11 | 11 | 0 | 0 | 0 / 0 / 0 / 11 | false warning 11/11 = 1.000 [0.741, 1.000] | 0 / 11 / 0 | 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273 | n = 0 | no_grid 11 |
| auto-corners | museum tier A (in scope) | full | 11 | 11 | 0 | 1 | 1 / 0 / 0 / 9 | false warning 9/10 = 0.900 [0.596, 0.982], 1 skipped (1 over the as-fetched budget) | 0 / 10 / 0 | 0/10 = 0.000 [0.000, 0.278], 3/n = 0.300, 1 skipped (1 over the as-fetched budget) | n = 0, 1 skipped (1 over the as-fetched budget) | no_grid 9, readable 1 |
| auto-corners | museum tier A (in scope) | phone-1400 | 11 | 11 | 0 | 0 | 0 / 0 / 0 / 11 | false warning 11/11 = 1.000 [0.741, 1.000] | 0 / 11 / 0 | 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273 | n = 0 | no_grid 11 |
| auto-corners | refusal tier | desktop-2000 | 55 | 55 | 0 | 55 | 0 / 0 / 0 / 0 | refusal recall n = 0, 55 skipped | 0 / 0 / 0 | n = 0 | n = 0 | none |
| auto-corners | refusal tier | full | 55 | 55 | 0 | 55 | 0 / 0 / 0 / 0 | refusal recall n = 0, 55 skipped | 0 / 0 / 0 | n = 0 | n = 0 | none |
| auto-corners | refusal tier | phone-1400 | 55 | 55 | 0 | 55 | 0 / 0 / 0 / 0 | refusal recall n = 0, 55 skipped | 0 / 0 / 0 | n = 0 | n = 0 | none |

## Per device class

| Reader | Tier | Device class | Resolution | Photos | Outcomes | Rate | Gate / provisional / conflict rows |
|---|---|---|---|---|---|---|---|
| auto | museum tier A (in scope) | museum scan | desktop-2000 | 11 | 0 / 0 / 0 / 11 | false warning 11/11 = 1.000 [0.741, 1.000] | 0 / 11 / 0 |
| auto | museum tier A (in scope) | museum scan | full | 11 | 1 / 0 / 0 / 9 | false warning 9/10 = 0.900 [0.596, 0.982], 1 skipped (1 over the as-fetched budget) | 0 / 10 / 0 |
| auto | museum tier A (in scope) | museum scan | phone-1400 | 11 | 0 / 0 / 0 / 11 | false warning 11/11 = 1.000 [0.741, 1.000] | 0 / 11 / 0 |
| auto | refusal tier | museum scan | desktop-2000 | 55 | 6 / 0 / 0 / 49 | refusal recall 49/55 = 0.891 [0.782, 0.949] | 0 / 55 / 0 |
| auto | refusal tier | museum scan | full | 55 | 9 / 0 / 0 / 45 | refusal recall 45/54 = 0.833 [0.713, 0.910], 1 skipped (1 over the as-fetched budget) | 0 / 54 / 0 |
| auto | refusal tier | museum scan | phone-1400 | 55 | 5 / 0 / 0 / 50 | refusal recall 50/55 = 0.909 [0.804, 0.961] | 0 / 55 / 0 |
| auto-corners | museum tier A (in scope) | museum scan | desktop-2000 | 11 | 0 / 0 / 0 / 11 | false warning 11/11 = 1.000 [0.741, 1.000] | 0 / 11 / 0 |
| auto-corners | museum tier A (in scope) | museum scan | full | 11 | 1 / 0 / 0 / 9 | false warning 9/10 = 0.900 [0.596, 0.982], 1 skipped (1 over the as-fetched budget) | 0 / 10 / 0 |
| auto-corners | museum tier A (in scope) | museum scan | phone-1400 | 11 | 0 / 0 / 0 / 11 | false warning 11/11 = 1.000 [0.741, 1.000] | 0 / 11 / 0 |
| auto-corners | refusal tier | museum scan | desktop-2000 | 55 | 0 / 0 / 0 / 0 | refusal recall n = 0, 55 skipped | 0 / 0 / 0 |
| auto-corners | refusal tier | museum scan | full | 55 | 0 / 0 / 0 / 0 | refusal recall n = 0, 55 skipped | 0 / 0 / 0 |
| auto-corners | refusal tier | museum scan | phone-1400 | 55 | 0 / 0 / 0 / 0 | refusal recall n = 0, 55 skipped | 0 / 0 / 0 |
| every reader | every tier | phone camera | every resolution | 0 | none | n = 0 | 0 / 0 / 0 |
| every reader | every tier | screenshot | every resolution | 0 | none | n = 0 | 0 / 0 / 0 |

## Corner jitter (museum tier A)

Trials of one photo are not independent, so these rows give k/n trials and the photo count, with no interval and no 3/n bound.

| Reader | Resolution | Radius px | Mean radius in squares | Mean moved in squares | Rows | False warning | Count top-1 |
|---|---|---|---|---|---|---|---|
| auto-corners | desktop-2000 | 0 | 0.000 | 0.000 | 11 | 11/11 trials, 11 photos | 0/11 trials, 11 photos |
| auto-corners | desktop-2000 | 2 | 0.041 | 0.041 | 33 | 33/33 trials, 11 photos | 0/33 trials, 11 photos |
| auto-corners | desktop-2000 | 4 | 0.081 | 0.081 | 33 | 33/33 trials, 11 photos | 0/33 trials, 11 photos |
| auto-corners | desktop-2000 | 6 | 0.122 | 0.122 | 33 | 33/33 trials, 11 photos | 0/33 trials, 11 photos |
| auto-corners | desktop-2000 | 8 | 0.162 | 0.162 | 33 | 33/33 trials, 11 photos | 0/33 trials, 11 photos |
| auto-corners | full | 0 | 0.000 | 0.000 | 11 | 9/10 trials, 10 photos, 1 skipped (1 over the as-fetched budget) | 0/10 trials, 10 photos, 1 skipped (1 over the as-fetched budget) |
| auto-corners | full | 2 | 0.023 | 0.023 | 33 | 27/30 trials, 10 photos, 3 skipped (3 over the as-fetched budget) | 0/30 trials, 10 photos, 3 skipped (3 over the as-fetched budget) |
| auto-corners | full | 4 | 0.046 | 0.046 | 33 | 25/30 trials, 10 photos, 3 skipped (3 over the as-fetched budget) | 0/30 trials, 10 photos, 3 skipped (3 over the as-fetched budget) |
| auto-corners | full | 6 | 0.069 | 0.069 | 33 | 27/30 trials, 10 photos, 3 skipped (3 over the as-fetched budget) | 0/30 trials, 10 photos, 3 skipped (3 over the as-fetched budget) |
| auto-corners | full | 8 | 0.093 | 0.093 | 33 | 26/30 trials, 10 photos, 3 skipped (3 over the as-fetched budget) | 0/30 trials, 10 photos, 3 skipped (3 over the as-fetched budget) |
| auto-corners | phone-1400 | 0 | 0.000 | 0.000 | 11 | 11/11 trials, 11 photos | 0/11 trials, 11 photos |
| auto-corners | phone-1400 | 2 | 0.058 | 0.058 | 33 | 33/33 trials, 11 photos | 0/33 trials, 11 photos |
| auto-corners | phone-1400 | 4 | 0.116 | 0.116 | 33 | 33/33 trials, 11 photos | 0/33 trials, 11 photos |
| auto-corners | phone-1400 | 6 | 0.174 | 0.174 | 33 | 32/33 trials, 11 photos | 0/33 trials, 11 photos |
| auto-corners | phone-1400 | 8 | 0.232 | 0.231 | 33 | 31/33 trials, 11 photos | 0/33 trials, 11 photos |

## Stress: degradations

Parameters: grayscale {}; lighting_gradient {'factor_left': 1.0, 'factor_right': 0.55}; low_res_jpeg {'longest_px': 600, 'jpeg_quality': 40}; gaussian_blur {'sigma_px': 2.0}; glare {'center_of_field': [0.35, 0.35], 'sigma_of_short_side': 0.15, 'peak_blend_to_white': 0.85}; occlusion {'center_of_field': [0.6, 0.6], 'side_of_field': 0.25, 'gray': 128}, applied at every requested resolution, at true corners, to museum tier A photos licensed CC0-1.0.

| Reader | Degradation | Device class | Resolution | Photos | Outcomes | False warning | Count top-1 | Verdicts |
|---|---|---|---|---|---|---|---|---|
| auto | gaussian_blur | museum scan | desktop-2000 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto | gaussian_blur | museum scan | full | 6 | 0 / 0 / 0 / 5 | 5/5 = 1.000 [0.566, 1.000], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 5 |
| auto | gaussian_blur | museum scan | phone-1400 | 6 | 1 / 0 / 0 / 5 | 5/6 = 0.833 [0.436, 0.970] | 1/6 = 0.167 [0.030, 0.564] | no_grid 5, readable 1 |
| auto | glare | museum scan | desktop-2000 | 6 | 2 / 0 / 0 / 4 | 4/6 = 0.667 [0.300, 0.903] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 4, readable 2 |
| auto | glare | museum scan | full | 6 | 1 / 0 / 0 / 4 | 4/5 = 0.800 [0.376, 0.964], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 4, readable 1 |
| auto | glare | museum scan | phone-1400 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto | grayscale | museum scan | desktop-2000 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto | grayscale | museum scan | full | 6 | 0 / 0 / 0 / 5 | 5/5 = 1.000 [0.566, 1.000], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 5 |
| auto | grayscale | museum scan | phone-1400 | 6 | 1 / 0 / 0 / 5 | 5/6 = 0.833 [0.436, 0.970] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 5, readable 1 |
| auto | lighting_gradient | museum scan | desktop-2000 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto | lighting_gradient | museum scan | full | 6 | 0 / 0 / 0 / 5 | 5/5 = 1.000 [0.566, 1.000], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 5 |
| auto | lighting_gradient | museum scan | phone-1400 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto | low_res_jpeg | museum scan | desktop-2000 | 6 | 1 / 0 / 0 / 5 | 5/6 = 0.833 [0.436, 0.970] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 5, readable 1 |
| auto | low_res_jpeg | museum scan | full | 6 | 1 / 0 / 0 / 5 | 5/6 = 0.833 [0.436, 0.970] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 5, readable 1 |
| auto | low_res_jpeg | museum scan | phone-1400 | 6 | 1 / 0 / 0 / 5 | 5/6 = 0.833 [0.436, 0.970] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 5, readable 1 |
| auto | occlusion | museum scan | desktop-2000 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto | occlusion | museum scan | full | 6 | 1 / 0 / 0 / 4 | 4/5 = 0.800 [0.376, 0.964], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 4, readable 1 |
| auto | occlusion | museum scan | phone-1400 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto-corners | gaussian_blur | museum scan | desktop-2000 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto-corners | gaussian_blur | museum scan | full | 6 | 0 / 0 / 0 / 5 | 5/5 = 1.000 [0.566, 1.000], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 5 |
| auto-corners | gaussian_blur | museum scan | phone-1400 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto-corners | glare | museum scan | desktop-2000 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto-corners | glare | museum scan | full | 6 | 1 / 0 / 0 / 4 | 4/5 = 0.800 [0.376, 0.964], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 4, readable 1 |
| auto-corners | glare | museum scan | phone-1400 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto-corners | grayscale | museum scan | desktop-2000 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto-corners | grayscale | museum scan | full | 6 | 0 / 0 / 0 / 5 | 5/5 = 1.000 [0.566, 1.000], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 5 |
| auto-corners | grayscale | museum scan | phone-1400 | 6 | 1 / 0 / 0 / 5 | 5/6 = 0.833 [0.436, 0.970] | 1/6 = 0.167 [0.030, 0.564] | no_grid 5, readable 1 |
| auto-corners | lighting_gradient | museum scan | desktop-2000 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto-corners | lighting_gradient | museum scan | full | 6 | 0 / 0 / 0 / 5 | 5/5 = 1.000 [0.566, 1.000], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 5 |
| auto-corners | lighting_gradient | museum scan | phone-1400 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto-corners | low_res_jpeg | museum scan | desktop-2000 | 6 | 2 / 1 / 0 / 3 | 3/6 = 0.500 [0.188, 0.812] | 2/6 = 0.333 [0.097, 0.700] | no_grid 3, non_square_repeat 1, readable 2 |
| auto-corners | low_res_jpeg | museum scan | full | 6 | 2 / 1 / 0 / 3 | 3/6 = 0.500 [0.188, 0.812] | 2/6 = 0.333 [0.097, 0.700] | no_grid 3, non_square_repeat 1, readable 2 |
| auto-corners | low_res_jpeg | museum scan | phone-1400 | 6 | 2 / 0 / 0 / 4 | 4/6 = 0.667 [0.300, 0.903] | 1/6 = 0.167 [0.030, 0.564] | no_grid 4, readable 2 |
| auto-corners | occlusion | museum scan | desktop-2000 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |
| auto-corners | occlusion | museum scan | full | 6 | 1 / 0 / 0 / 4 | 4/5 = 0.800 [0.376, 0.964], 1 skipped (1 over the as-fetched budget) | 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget) | no_grid 4, readable 1 |
| auto-corners | occlusion | museum scan | phone-1400 | 6 | 0 / 0 / 0 / 6 | 6/6 = 1.000 [0.610, 1.000] | 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500 | no_grid 6 |

## Named rows: photoreal fixtures (#82)

auto-corners reads each fixture with its sidecar corners and fabric count, auto with neither; the automatic read takes no counts, so the sidecar counts reach only the confirmed reader. Cell truth is the fixture generator's, so these rows are synthetic, not a gate tier.

| Fixture | Cap | Reader | Verdict | Read dims | Truth dims | k read / truth | Accuracy many-to-one | Accuracy one-to-one | Fully correct | Confident-wrong |
|---|---|---|---|---|---|---|---|---|---|---|
| busy_print_squares | fixture-1400 | auto | no_grid | [221, 186] | [13, 11] | 4 / 2 | n/a | n/a | False | 0 |
| busy_print_squares | fixture-1400 | auto-corners | readable | [53, 45] | [13, 11] | 2 / 2 | 0.0000 | 0.0000 | False | 143 |
| busy_print_squares | fixture-2000 | auto | no_grid | [332, 282] | [13, 11] | 4 / 2 | n/a | n/a | False | 0 |
| busy_print_squares | fixture-2000 | auto-corners | readable | [53, 45] | [13, 11] | 2 / 2 | 0.0000 | 0.0000 | False | 0 |
| low_contrast_hst | fixture-1400 | auto | non_square_repeat | [26, 24] | [28, 24] | 2 / 2 | n/a | n/a | n/a | n/a |
| low_contrast_hst | fixture-1400 | auto-corners | non_square_repeat | [26, 24] | [28, 24] | 2 / 2 | n/a | n/a | n/a | n/a |
| low_contrast_hst | fixture-2000 | auto | non_square_repeat | [27, 23] | [28, 24] | 2 / 2 | n/a | n/a | n/a | n/a |
| low_contrast_hst | fixture-2000 | auto-corners | non_square_repeat | [27, 23] | [28, 24] | 2 / 2 | n/a | n/a | n/a | n/a |

## R1, reported and not gated (automatic read, museum tier A)

- desktop-2000: count top-1 periodic 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500; non-periodic 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600; harmonic error 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273; fabric-count suggestion exact 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273; top-3 n/a: the automatic read offers one grid, not ranked suggestions (B7)
- full: count top-1 periodic 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600, 1 skipped (1 over the as-fetched budget); non-periodic 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600; harmonic error 0/10 = 0.000 [0.000, 0.278], 3/n = 0.300, 1 skipped (1 over the as-fetched budget); fabric-count suggestion exact 1/10 = 0.100 [0.018, 0.404], 1 skipped (1 over the as-fetched budget); top-3 n/a: the automatic read offers one grid, not ranked suggestions (B7)
- phone-1400: count top-1 periodic 0/6 = 0.000 [0.000, 0.390], 3/n = 0.500; non-periodic 0/5 = 0.000 [0.000, 0.434], 3/n = 0.600; harmonic error 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273; fabric-count suggestion exact 0/11 = 0.000 [0.000, 0.259], 3/n = 0.273; top-3 n/a: the automatic read offers one grid, not ranked suggestions (B7)
- Latency: n/a: confirm-flow latency in the browser needs D4b and C3; native median 2.73 s per read over 826 reads
- Triangle counts: n/a until B4 classifies triangle units

## Errors

- none

## Per photo (museum tier A)

| Photo | Resolution | Reader | Truth | Verdicts | Read dims | Truth dims |
|---|---|---|---|---|---|---|
| lacma-54871 | desktop-2000 | auto | provisional | no_grid | [10, 10] | [50, 50] |
| lacma-54871 | desktop-2000 | auto-corners | provisional | no_grid | [10, 11] | [50, 50] |
| lacma-54871 | full | auto | provisional | no_grid | [10, 95] | [50, 50] |
| lacma-54871 | full | auto-corners | provisional | no_grid | [31, 31] | [50, 50] |
| lacma-54871 | phone-1400 | auto | provisional | no_grid | [25, 10] | [50, 50] |
| lacma-54871 | phone-1400 | auto-corners | provisional | no_grid | [11, 11] | [50, 50] |
| lacma-54904 | desktop-2000 | auto | provisional | no_grid | [6, 4] | [50, 50] |
| lacma-54904 | desktop-2000 | auto-corners | provisional | no_grid | [14, 12] | [50, 50] |
| lacma-54904 | full | auto | provisional | no_grid | [253, 13] | [50, 50] |
| lacma-54904 | full | auto-corners | provisional | no_grid | [14, 12] | [50, 50] |
| lacma-54904 | phone-1400 | auto | provisional | no_grid | [6, 4] | [50, 50] |
| lacma-54904 | phone-1400 | auto-corners | provisional | no_grid | [14, 12] | [50, 50] |
| lacma-60126 | desktop-2000 | auto | provisional | no_grid | [26, 21] | [26, 21] |
| lacma-60126 | desktop-2000 | auto-corners | provisional | no_grid | [26, 21] | [26, 21] |
| lacma-60126 | full | auto | provisional | no_grid | [26, 21] | [26, 21] |
| lacma-60126 | full | auto-corners | provisional | no_grid | [26, 21] | [26, 21] |
| lacma-60126 | phone-1400 | auto | provisional | no_grid | [26, 21] | [26, 21] |
| lacma-60126 | phone-1400 | auto-corners | provisional | no_grid | [26, 21] | [26, 21] |
| lacma-63229 | desktop-2000 | auto | provisional | no_grid | [178, 161] | [22, 22] |
| lacma-63229 | desktop-2000 | auto-corners | provisional | no_grid | [339, 313] | [22, 22] |
| lacma-63229 | full | auto | provisional | no_grid | [536, 480] | [22, 22] |
| lacma-63229 | full | auto-corners | provisional | readable | [677, 623] | [22, 22] |
| lacma-63229 | phone-1400 | auto | provisional | no_grid | [12, 11] | [22, 22] |
| lacma-63229 | phone-1400 | auto-corners | provisional | no_grid | [211, 97] | [22, 22] |
| lacma-63267 | desktop-2000 | auto | provisional | no_grid | [12, 229] | [23, 19] |
| lacma-63267 | desktop-2000 | auto-corners | provisional | no_grid | [12, 139] | [23, 19] |
| lacma-63267 | full | auto | provisional | readable | [639, 545] | [23, 19] |
| lacma-63267 | full | auto-corners | provisional | no_grid | [597, 544] | [23, 19] |
| lacma-63267 | phone-1400 | auto | provisional | no_grid | [11, 19] | [23, 19] |
| lacma-63267 | phone-1400 | auto-corners | provisional | no_grid | [23, 17] | [23, 19] |
| smithsonian-chndm-1973-45-1 | desktop-2000 | auto | provisional | no_grid | [12, 55] | [60, 55] |
| smithsonian-chndm-1973-45-1 | desktop-2000 | auto-corners | provisional | no_grid | [12, 11] | [60, 55] |
| smithsonian-chndm-1973-45-1 | full | auto | provisional | skipped | None | [60, 55] |
| smithsonian-chndm-1973-45-1 | full | auto-corners | provisional | skipped | None | [60, 55] |
| smithsonian-chndm-1973-45-1 | phone-1400 | auto | provisional | no_grid | [12, 12] | [60, 55] |
| smithsonian-chndm-1973-45-1 | phone-1400 | auto-corners | provisional | no_grid | [67, 11] | [60, 55] |
| smithsonian-saam-1998-149-21 | desktop-2000 | auto | provisional | no_grid | [23, 23] | [21, 22] |
| smithsonian-saam-1998-149-21 | desktop-2000 | auto-corners | provisional | no_grid | [22, 24] | [21, 22] |
| smithsonian-saam-1998-149-21 | full | auto | provisional | no_grid | [23, 24] | [21, 22] |
| smithsonian-saam-1998-149-21 | full | auto-corners | provisional | no_grid | [74, 25] | [21, 22] |
| smithsonian-saam-1998-149-21 | phone-1400 | auto | provisional | no_grid | [23, 24] | [21, 22] |
| smithsonian-saam-1998-149-21 | phone-1400 | auto-corners | provisional | no_grid | [21, 23] | [21, 22] |
| smithsonian-saam-2013-67-17 | desktop-2000 | auto | provisional | no_grid | [22, 19] | [22, 19] |
| smithsonian-saam-2013-67-17 | desktop-2000 | auto-corners | provisional | no_grid | [22, 250] | [22, 19] |
| smithsonian-saam-2013-67-17 | full | auto | provisional | no_grid | [22, 263] | [22, 19] |
| smithsonian-saam-2013-67-17 | full | auto-corners | provisional | no_grid | [22, 292] | [22, 19] |
| smithsonian-saam-2013-67-17 | phone-1400 | auto | provisional | no_grid | [22, 19] | [22, 19] |
| smithsonian-saam-2013-67-17 | phone-1400 | auto-corners | provisional | no_grid | [22, 19] | [22, 19] |
| smithsonian-saam-2013-67-9 | desktop-2000 | auto | provisional | no_grid | [175, 174] | [11, 14] |
| smithsonian-saam-2013-67-9 | desktop-2000 | auto-corners | provisional | no_grid | [93, 210] | [11, 14] |
| smithsonian-saam-2013-67-9 | full | auto | provisional | no_grid | [265, 147] | [11, 14] |
| smithsonian-saam-2013-67-9 | full | auto-corners | provisional | no_grid | [316, 568] | [11, 14] |
| smithsonian-saam-2013-67-9 | phone-1400 | auto | provisional | no_grid | [185, 206] | [11, 14] |
| smithsonian-saam-2013-67-9 | phone-1400 | auto-corners | provisional | no_grid | [51, 52] | [11, 14] |
| smithsonian-saam-2017-24-27 | desktop-2000 | auto | provisional | no_grid | [23, 21] | [21, 21] |
| smithsonian-saam-2017-24-27 | desktop-2000 | auto-corners | provisional | no_grid | [21, 374] | [21, 21] |
| smithsonian-saam-2017-24-27 | full | auto | provisional | no_grid | [21, 21] | [21, 21] |
| smithsonian-saam-2017-24-27 | full | auto-corners | provisional | no_grid | [21, 27] | [21, 21] |
| smithsonian-saam-2017-24-27 | phone-1400 | auto | provisional | no_grid | [21, 21] | [21, 21] |
| smithsonian-saam-2017-24-27 | phone-1400 | auto-corners | provisional | no_grid | [21, 27] | [21, 21] |
| smithsonian-saam-2017-24-5 | desktop-2000 | auto | provisional | no_grid | [55, 45] | [54, 45] |
| smithsonian-saam-2017-24-5 | desktop-2000 | auto-corners | provisional | no_grid | [54, 46] | [54, 45] |
| smithsonian-saam-2017-24-5 | full | auto | provisional | no_grid | [55, 45] | [54, 45] |
| smithsonian-saam-2017-24-5 | full | auto-corners | provisional | no_grid | [54, 46] | [54, 45] |
| smithsonian-saam-2017-24-5 | phone-1400 | auto | provisional | no_grid | [56, 46] | [54, 45] |
| smithsonian-saam-2017-24-5 | phone-1400 | auto-corners | provisional | no_grid | [54, 46] | [54, 45] |
