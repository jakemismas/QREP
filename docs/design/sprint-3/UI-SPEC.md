# Sprint 3 UI specification (binding)

Status: BINDING from S0 (issue #66). No sprint 3 mocks exist: the
"UI from Claude Design.zip" at the repo root was verified as a
byte-identical duplicate of the committed sprint 2 mocks (cmp on all three
files, 2026-07-09) and removed per the approval record. This document is
therefore the design authority for the three new sprint 3 surfaces, per the
plan's DESIGN REFERENCE BEFORE UI rule. Styling comes from the committed
sprint 2 design system (docs/design/sprint-2/QREP Design System.dc.html);
this spec pins layout, behavior, and copy. Read together with
docs/design/sprint-2/PARITY.md and docs/design/sprint-3/PARITY-AMENDMENT.md.

Vocabulary rules apply throughout: squares not cells, loading not
downloading, mixed fractions everywhere. Sprint 3 additions: period
phrasing uses squares or "repeats about N times across its width" until a
user-entered size exists; failure copy is honest and specific, never
blaming, never fake-precise.

## 1. Crop screen (S2)

Placement: a new PhotoScreen state `crop` between the dropzone (idle) and
the analysis progress screen. The post-results corners screen is retired;
"Adjust the crop" from results (success or failure) returns HERE seeded
with the confirmed quad. One pin surface, one behavior, reachable from
both ends.

Layout, desktop (>= 720 px):
- Card centered in the content area, max width 720 px.
- Header row: title "Check the crop", subtitle "Drag the pins so they sit
  on the quilt's corners."
- Photo viewport: the staged photo letterboxed to fit, max height 60vh,
  rounded per the design system card radius, on the recessed surface
  token. The quad overlay draws on top.
- Below the photo: the size block (section 2, lands in S7; S2 renders the
  screen without it).
- Footer buttons, right-aligned: secondary "Back", secondary
  "Reset to auto", primary "Analyze".

Layout, phone (< 720 px):
- Full-width sheet; photo viewport max height 48vh so the pins, the size
  block, and the button row stay reachable; buttons full-width stacked,
  primary last (thumb-nearest).
- With the soft keyboard up (size inputs focused), the photo viewport
  collapses to a 96 px thumbnail strip so the inputs and the Analyze
  button remain visible; collapsing and restoring animate at the design
  system's fast transition token.

Quad overlay and pins:
- Four draggable corner pins, 44 px minimum hit target, rendered as the
  design system's accent-filled handles with a 2 px surface-contrast ring.
- The quad edges connect the pins as 2 px accent lines; the region outside
  the quad is scrimmed at 40 percent surface-dark so the kept region reads
  as "kept".
- Pins clamp to the photo bounds; edges may not cross (dragging past an
  opposite edge clamps at 8 px separation).
- Pin drag never waits on the engine; the overlay is pure JS.

Cold-start contract (binding, from the plan):
- The photo and DEFAULT pins (inset 4 percent from each photo edge) render
  immediately on entry, draggable with no engine present.
- While detect_quad resolves, a quiet inline affordance sits under the
  photo: small spinner plus "Finding your quilt..." in the muted text
  token. It never blocks interaction.
- When detect_quad resolves, the detected quad SNAPS IN with a 150 ms
  ease, UNLESS the user has already moved any pin (user wins, silently).
- If detect_quad fails or the worker is cold, the affordance disappears
  and the default pins simply remain: the screen is fully usable.
- "Reset to auto" restores the detected quad when one exists, else the
  default inset pins; it is disabled until pins differ from that target.
- Vision prefetch fires on photo-flow ENTRY (not on drop).

Flow rules:
- Analyze proceeds with the current quad (normalized coordinates) into the
  existing staged progress screen. Corners ride along to the engine ONLY
  when the user moved a pin; untouched pins (default, detected, or seeded)
  pass nothing and the pipeline re-detects deterministically.
- Back returns to the dropzone and discards the staged photo.
- Cancel from progress returns to the DROPZONE (sprint 2 PARITY item 14,
  frozen by the sprint 2 e2e suite; corrected in S2 - this section
  originally said crop screen, which contradicted the frozen contract).
- A second photo (including after cancel) starts from ITS OWN detection,
  never the previous photo's corners.
- The sample photo bypasses this screen entirely (auto-confirmed
  full-frame quad).

## 2. Size block (S7)

Sits on the crop screen below the photo, and reappears as the inline size
editor on the results screen (section 2.4). Optional: analysis never
requires it.

2.1 Structure:
- Heading: "How big is it?" with muted sub-line "Skip this if you're not
  sure - you can set it any time."
- One row of PRESET chips, from the shipped PRESETS table verbatim
  (Crib 36x52, Throw 50x65, Twin 70x90, Full 84x90, Queen 90x108,
  King 110x108), rendered as design system chips labeled
  "Crib", "Throw", "Twin", "Full", "Queen", "King" with the dimensions in
  the chip tooltip (desktop) and under the label at small size (phone).
  Chips wrap to two rows under 400 px.
- Below the chips: "W x H" inputs (shared fraction-input component) with
  an "in / cm" toggle at the row end. Placeholder text shows the active
  unit ("width in", "height in" / "width cm", "height cm").

2.2 Entry and units:
- Inputs accept decimal ("67.5") AND mixed ("67 1/2") entry, plus the
  sprint 2 fraction-input forms (unicode fractions, trailing quote or
  "in"); display normalizes to mixed fractions.
- cm entry converts at entry via the pinned rule
  eighths = round(cm * 8 / 2.54); the size line thereafter shows the cm
  equivalent in parentheses when the user entered cm. The MODEL stays
  integer eighths everywhere; rulers, the editor, and exports stay inches
  (scope pin; full metric display is a logged follow-up issue).

2.3 Suggestion and provenance (binding, from the plan):
- The nearest-preset prediction renders as a HIGHLIGHTED CHIP (accent
  outline plus "looks about right?" microcopy), only when exactly ONE
  preset matches the detected aspect within the frozen
  orientation-normalized tolerance; otherwise no suggestion renders.
- Numbers NEVER silently prefill from a suggestion; prefill happens only
  under that same single-match rule AND only into empty inputs, marked
  visually as suggested (muted) until touched.
- Provenance user (size_source="user") attaches only on an explicit
  gesture: a chip tap or an edited input. An untouched suggestion ships as
  guess.
- Asked-vs-got: when the achieved dimensions differ from the entry, the
  confirm moment shows the sprint 2 sizing panel's asked-for-vs-you-get
  line ("You asked for 86 x 67 1/2 - the squares work out to ...").

2.4 Results-screen size story:
- The size line on results is tappable in BOTH states: entered
  ("86 x 67 1/2 finished", tap to edit) and guessed ("our guess - tap to
  set the real size").
- Tapping opens an INLINE W x H editor (this same block, chips included)
  in place; applying calls apply_finished_size with no navigation and no
  re-analysis. A typo is never a one-way door.

## 3. Verdict panels (S8)

One results surface keyed off the verdict field (readable,
readable_no_repeat, non_square_repeat, no_grid). Copy strings below are
binding skeletons; S8 finalizes exact strings in the PARITY amendment and
the copy-audit test.

3.1 no_grid (failure panel):
- Panel replaces the recovered-quilt panel position. Title: "We could not
  find a square grid in this photo". Body lists the structured reason from
  grid_diagnosis in plain language (e.g. "The photo may show the quilt at
  a steep angle, or the pattern may not be made of squares.").
- Actions, in order: primary "Adjust the crop" (returns to the crop screen
  seeded with the confirmed quad), secondary "Photo tips" (disclosure with
  retake tips: fill the frame, square-on, even light), secondary "Start in
  the editor".
- The recovered-quilt panel is NOT hidden: it collapses behind a
  disclosure labeled "Show what we saw anyway". Expanding shows a
  persistent this-is-wrong banner ("This reading is wrong - shown only to
  help you see what went wrong.") above the quilt, and keeps the
  side-by-side lightbox available.
- Editor entry from here: if palette-stage confidence clears the frozen
  threshold and the S0 palette-fidelity bar, "Start in the editor" enters
  via startBlankWithPalette (blank grid, recovered fabric colors);
  otherwise a plain blank grid.

3.2 non_square_repeat:
- Informational panel above the recovered quilt: "This quilt's blocks
  repeat, but they use shapes QREP cannot read yet (triangles and
  curves)." Period phrasing: sized "repeats every N in" when a
  user-entered size exists, otherwise "repeats about N times across its
  width", plus an invitation: "Know the size? Add it for a better
  answer."
- The squares approximation is available behind the same labeled
  disclosure pattern as 3.1 ("Show the squares approximation") with the
  banner softened ("This is an approximation - the real blocks are not
  squares.").

3.3 readable_no_repeat (NORMAL result, no failure framing):
- Standard results panel; the caption gains one line: "No repeating block
  found - common for samplers and medallion quilts."

3.4 readable with a confirmed repeat:
- Standard results panel; positive caption line: "repeats every N in"
  (sized) or "repeats N times across the width".

## 4. Overall pill: failure tier (S8)

The sprint 2 pill tiers stand for successful reads (>= 92 percent very
sure, >= 84 solid, >= 78 good - check the flags, else needs your eye). NEW
bottom tier, replacing the percentage entirely on failure verdicts
(no_grid): pill text "Could not read this photo" in the accent tone, no
number (a mean-of-stages percentage next to a failure statement is a
contradiction). non_square_repeat keeps a number but relabels: "read as
squares - N percent" is banned; use "blocks repeat - squares uncertain".
The PARITY tier table is amended accordingly (finalized in S8).

## 5. Progress-row failure states (S8)

The analysis progress screen's six stage rows currently fill green as
stages complete. When a run ends in a failure verdict: rows for stages AT
and AFTER the failure point render a neutral dash (design system muted
token) instead of a green check and meter; rows before the failure keep
their real meters. Six green checks before a failure panel contradict the
verdict and are banned. The failure point is derived from grid_diagnosis
(e.g. rectify ok, grid failed: rectify and palette keep meters; grid,
squares, repeats, borders show the dash).
