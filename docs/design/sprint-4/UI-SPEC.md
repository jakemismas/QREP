# Sprint 4 UI specification (binding)

Status: SKELETON written in S0 (issue #92), BINDING from S0 onward; the
individual sections FINALIZE in their slices (S2 copy, S3/S4 document panel,
S5 lightbox). No sprint 4 mocks exist; this document is the design authority
for the four new/changed sprint 4 surfaces, per the plan's DESIGN REFERENCE
BEFORE UI rule. Styling comes from the committed sprint 2 design system
(docs/design/sprint-2/QREP Design System.dc.html). Read together with
docs/design/sprint-2/PARITY.md, docs/design/sprint-3/UI-SPEC.md, and
docs/design/sprint-4/PARITY-AMENDMENT.md. Where this spec conflicts with
engine math, the engine wins and the PARITY amendment records the deviation.

Vocabulary rules carry forward (squares not cells, loading not downloading,
mixed fractions everywhere; honest failure copy that never blames, never
shows a percentage next to a failure statement, never calls an approximation
a result). Sprint 4 additions are called out per section.

## 1. Pattern document panel — one download (S4, on the S3 engine)

Supersedes the sprint 2/3 PatternPanel download block
(web/src/shell/PatternPanel.tsx `DL_BTNS`), which offers five per-artifact
downloads (`download-pdf`, `download-cutlist-csv`, `download-cutlist-md`,
`download-yardage`, `download-svg`). Sprint 4 retires all five (RETIREMENT
RULE); the engine exporters and their CLI/`test_exports` surface stay.

Layout (Pattern tab, unchanged frame):
- The yardage table, strategy cards, and hand-tweaked badge stay exactly as
  today.
- The download block becomes ONE primary control: "Pattern document · PDF"
  (`data-testid="download-document"`, sub-line "everything in one file, ready
  to print"), plus the existing secondary "Print" (`print-plan`) and
  "Copy my settings" (`copy-settings`). No other download control renders.
- The generated quilt name (section 4) heads the panel as an editable title;
  the download filename is that name in kebab case plus `.pdf`.

Behavior:
- The control calls `bridge.export_document` through the worker with the
  model, the active seam strategy, the SESSION photo bitmap (downscaled per
  the existing caps; never persisted), and the verdict diagnostics. It builds
  the market-canon document (S3): cover, your-quilt-vs-the-pattern page,
  fabrics, assumptions, cutting, assembly with inline figures, layout,
  finishing, coloring page.
- Session-only photo contract holds: the photo enters a PDF the user
  explicitly downloads; it is never written to storage or the model.
- Loading affordance while the document builds reuses the sprint 2 button
  spinner; a build error surfaces the sprint 2 inline error, never a crash.

Absence assertions for the slice: the five retired testids
(`download-pdf`, `download-cutlist-csv`, `download-cutlist-md`,
`download-yardage`, `download-svg`) are gone from the panel.

## 2. Mobile lightbox and compare (S5, fixes #90)

Rebuilds the `Lightbox` in web/src/shell/PhotoFlow.tsx. Today it is
`position: fixed; inset: 0` with a centered-flex stage capped at
`max-height: 78vh` and photo panels at `max-width: 84vw` — two 84vw panels
cannot sit side by side on a phone (they wrap, unlabeled), and the fixed
overlay clips under the iOS toolbar (WebKit 297779, unresolved).

Requirements (binding; S5 finalizes the exact CSS):
- Sizing uses `dvh` with a `vh` fallback (`max-height: 92dvh`), never a fixed
  `78vh`; the stage is a TOP-ANCHORED scrollable column, not centered flex,
  so nothing clips when the visual viewport shrinks.
- Body scroll lock while the lightbox is open (a `useScrollLock` hook,
  vitest-covered); restore on close.
- Safe-area insets honored (`env(safe-area-inset-*)`), tab bar always within
  reach at the top of the overlay.
- Compare view: on narrow viewports (< 640 px) the two images STACK, each
  under a visible label ("Photo" / "Recovered quilt"); when both fit
  side by side (>= 640 px and aspect allows) they sit side by side, still
  labeled. No unlabeled wrap in any width.
- iOS 26 fixed-position mitigation: anchor the overlay to the visual viewport
  and re-measure on `visualViewport` resize/scroll events.
- The three tabs (Photo / Side by side / Quilt) and their testids
  (`lightbox`, `open-lightbox`, `lightbox-tab-*`) stay; desktop assertions
  unchanged.

Manual smoke (the #90 closer): a physical iPhone against live Pages — open
compare from a real photo result, both panels visible and scrollable, close
via scrim and via button. Record the observed pre-fix symptom on #90.

## 3. non_square_content verdict copy (S2)

A new `grid_diagnosis` value `non_square_content` is emitted when a coarse
block lattice exists but the square read stays failed or routes via
corroboration exit (b) (curves/triangles). The verdict remains
`non_square_repeat` (the four-verdict enum is unchanged); this diagnosis
selects honest copy in `web/src/model/verdictStory.ts`.

Copy skeleton (S2 finalizes exact strings + copy-audit test):
- Info-panel title: "The blocks repeat, but the shapes inside are not
  squares." Body: "QREP reads quilts made of squares. This one looks like it
  is pieced from curves or triangles, so the squares below are an
  approximation of the block layout, not the real shapes."
- The steep-angle copy (`anisotropic_pitch`: "The rows and columns disagree —
  the photo may show the quilt at a steep angle.") now fires ONLY on genuine
  skew (no coarse block lattice found). When a coarse block IS found, the
  `non_square_content` copy replaces it — the sprint-3 bug where a
  curved-quilt read was blamed on a "steep angle" is retired.
- The squares approximation stays available behind the sprint-3 disclosure
  pattern ("Show the squares approximation" / "This is an approximation — the
  real blocks are not squares.").

## 4. Quilt name display (S3 engine, surfaced S4)

A deterministic generated name (structure word + mood word, seeded by a
content hash of cells + palette; `qrep/export/naming.py`) replaces the model
default "Recovered quilt" at reverse time. It is user-editable in the editor
exactly as the name is today.

- Results/pattern surface: the name heads the Pattern panel as an editable
  title (`data-testid="quilt-name"`), reusing the sprint 2 inline-edit
  affordance for the model name.
- The document cover (S3) prints the name; the download filename is the name
  in kebab case.
- The web save layer appends a collision suffix within saved projects (the
  naming module exposes the hook); an untouched generated name ships as a
  guess, a user edit as authored — no provenance change to the model schema.
