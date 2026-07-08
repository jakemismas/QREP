# UI parity annex (binding)

Maps the Claude Design mockups (QREP.dc.html, QREP Design System.dc.html,
committed in this directory) onto the sprint 2 slices, and records every
deliberate deviation. The mock is the look-and-behavior reference; where the
mock's internal math conflicts with the engine, the engine wins and this file
says so explicitly. Read together with docs/sprint-2/qrep-web-design-doc.md.

## Screen-to-slice map

| Mock screen / feature | Slice |
|---|---|
| App shell: logo/home, project rename, Open/Save, autosave dot, engine chip, theme toggle | S2 |
| Start screen: photo card, "Start from a photo", demo quilt, blank grid, resume banner, engine-size note | S2 (shell) + S3 (blank grid, resume) + S6 (photo entry) |
| Open-project modal: drop .json, browse, load sample, error toast | S2 |
| Editor canvas: rulers with accent end-labels, zoom in/out/fit/pinch, Paint / Move / Seams modes, fabric quick swatches, undo/redo, scale line, finished-size line | S2 (canvas, rulers, zoom, pan) + S3 (paint, undo) + S5 (seams) |
| Fabrics panel: recolor via color input, inline rename, counts, add fabric | S3 |
| Sizing panel: presets incl. Custom, W/H/cell fraction inputs + steppers, proportion lock, asked-for vs you-get, border rows (fabric select, width, add/remove), equation box, blocks line | S4 |
| Pattern panel: three strategy cards with metrics and blurbs, hand-tweaked badge, yardage table (fabrics, binding, backing, batting), five downloads, copy-my-settings | S5 |
| Photo flow: dropzone, staged progress (download bar, cached notice, six stages, cancel), results (confidence rows and words, overall pill, uncertain toggle, side-by-side), corner pins (drag, quad overlay, reset, re-run), lightbox (photo / side by side / quilt) | S6 |
| Print sheet (one-page plan via browser print) | S5 |
| Phone layout: bottom tab bar (Quilt / Fabrics / Sizing / Pattern), tooltips desktop-only | S2 layout rule, applies to all later slices |
| Toast + tooltip primitives, keyboard (Ctrl+Z/Y, Escape) | S2 (primitives) + S3 (keys) |

## Vocabulary (engine term -> UI term, from the mock)

cell -> square; stage names rectify/palette/grid/cells/repeat/border ->
Straighten / Fabric colors / Grid / Squares / Repeats / Borders (1:1 with
provenance.stage_confidence keys); strategies historical/strip/modern ->
Historical / Strip piecing / Modern optimized. UI copy never says "cell",
"palette extraction", or "homography".

## Binding functional decisions (deviations and reconciliations)

1. Engine-authoritative numbers. The mock computes metrics, yardage, and cut
   rows in JS; the app must not. Strategy-card metrics, yardage, and every
   download come from bridge calls. Testable rule: with no seam tweaks, card
   numbers equal bridge plan output field-for-field.
2. Seams tool is a preview layer in v2. Strategy choice implies a seam
   preview (historical=grid, strip=row runs, modern=merged rectangles); drag
   merges same-fabric neighbors, tap splits a piece. Overrides live in the
   project-file wrapper (ui.seamFix edge map), NOT in the engine model, and
   do NOT change exports or plans in v2. A tweaked selected card shows the
   "hand-tweaked" badge and clearly-estimated adjusted numbers; switching
   strategy resets tweaks with a toast (as the mock does). Feeding tweaks
   into the construction engine is logged as future work (#49).
3. PDF split. The mock's "PDF booklet" button opens the browser print dialog
   on a one-page plan. The app ships BOTH: "Pattern booklet - PDF" downloads
   the engine's reportlab booklet (the sprint 1 flagship, S0-gated), and
   "Print one-page plan" opens the print sheet. Six actions total; ask
   Claude Design to relabel rather than dropping either.
4. Locked resize scales border bands. The mock scales band widths by the
   same factor as the cell (rounded to 1/8", floor 1/4"); sprint 1's helper
   scales cell size only. The bridge gains NEW band-scaling resize functions
   with fresh hand-computed tests; sprint 1's sizing tests stay untouched.
   Mock semantics to encode: locked typed-commit ratio = target/current on
   that axis; locked preset ratio = min(pw/W, ph/H); cell clamp [3/4", 4"],
   eighth-rounded; dims clamp [20", 140"], quarter-rounded; band clamp
   [1/4", 14"]; unlocked cols/rows = max(block, round((target - 2*offset) /
   (cell*block)) * block) with top-left regrid preservation; steppers move
   cell 1/8" (locked) or one block (unlocked); cell stepper 1/4".
5. Project file is a wrapper. Save writes
   `{app:"QREP", version:1, name, model, ui:{seamFix}}` as
   `<slug>.qrep.json`, where model is the CANONICAL engine schema JSON
   (schema_version "1"), not the mock's flat shape. Open accepts the wrapper
   or a bare engine model (CLI/fixture interchange). Autosave stores the
   wrapper. Validation of the model part is the engine's job via the bridge.
6. Uncertainty is derived, not stored. "Uncertain squares" = per-cell
   confidence < 0.90 from the engine's per-cell confidence array. Painting a
   square sets its confidence to 1.0 (the mock's unc-clearing behavior).
   The uncertain button appears only for photo-sourced models with a nonzero
   count. Threshold 0.90 is a UI constant, documented in copy as "squares
   the analysis wasn't sure about".
7. Photo bitmap is session-only. The compare lightbox and editor photo
   button show the uploaded photo from memory; it is never persisted to
   autosave or the project file. After reload, compare affordances hide.
8. Copy corrections against the mock (the engine value wins):
   - Usable fabric width: mock hardcodes 40"; the engine default is 42"
     (design doc). All copy reads the settings value.
   - Vision download size: mock says "about 60 MB"; use the measured wheel
     size (~12 MB opencv) formatted at build time.
   - Backing panel math in the mock (orientation-optimized) differs from the
     engine's formula; the engine's yardage is displayed as-is.
9. Batting row. The mock's yardage table ends with a Batting row showing
   size-needed (quilt + 4" per side). Surface it from bridge data (finished
   dims + 8") in the UI table; extend the engine yardage report with the
   same line only if the yardage export is not golden-frozen (check first;
   if frozen, UI-only and log follow-up).
10. Phone layout is in scope for layout only. The mock ships a <720px
    arrangement (bottom tabs, full-width panels, desktop-only tooltips,
    pinch zoom, auto-zoom-to-paint with toast when squares are under ~14px).
    Adopted. Phone CV performance remains best-effort (downscaling is the
    mitigation); the parent issue non-goal is amended accordingly.
11. Downloads and filenames. Five downloads plus print: booklet PDF, cut
    list CSV, cut list Markdown, yardage report, SVG diagram. Filenames are
    `<project-slug>-cut-list.csv`, `-cut-list.md`, `-yardage.txt`,
    `-diagram.svg`, and `<project-slug>.qrep.json` for saves. Every download
    shows the busy state and a success/failure toast; the engine chip goes
    busy during generation.
12. Copy-my-settings. Clipboard text summary (name, finished size, squares,
    borders, per-fabric yardage, binding, backing, batting) with copied
    state, toast, and execCommand fallback. Values from bridge data.
13. Fraction input contract (shared component): displays mixed fractions,
    accepts "75", "75 1/2", "75.5", unicode fractions, optional trailing
    quote or "in"; invalid input restores the previous value and shows the
    mock's error toast copy. Parity-tested against the Python formatter.
14. Analysis progress maps 1:1 to real pipeline stages; each stage row fills
    its meter with the real per-stage confidence as it completes. Confidence
    color words: >=95% Very sure (sage), >=85% Solid (sage), >=80% Good
    (amber), else Check it (accent); overall pill: >=92% very sure, >=84%
    solid, >=78% good - check the flags, else needs your eye. Cancel returns
    to the dropzone (worker terminate + reboot is acceptable). The corner
    re-run flows user corners through the bridge's corners option.
15. Blank grid start: 18x24 squares at 2 1/2", one 2 1/2" border, two
    fabrics (background + one accent), block size 1 (unlocked resize moves
    one row/column at a time; the "blocks" copy adapts, as in the mock).
16. Theme: light/dark toggle in the header, persisted to localStorage,
    default light; the design system's dark tokens apply app-wide.

## Design-system adoption

web/ styling implements the committed design-system tokens (color, type,
shape and spacing scales, light + dark) and the component set (buttons,
engine chip, autosave dot, fraction input, dropdown, toggle, proportion
lock, confidence meter, staged progress, low-confidence hatch, cards,
tables, swatches, dropzone, toast, modal, tooltip) as reusable components,
not per-screen one-offs.
