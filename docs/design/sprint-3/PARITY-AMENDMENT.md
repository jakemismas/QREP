# UI parity annex, sprint 3 amendment (binding)

Status: SKELETON written in S0 (issue #66), BINDING from S0 onward;
FINALIZED in S8 (issue #74) - the exact strings and table rows below are
matched by web/src/model/verdictStory.test.ts and
web/src/copy-audit-verdicts.test.ts. Amends docs/design/sprint-2/PARITY.md
for sprint 3 scope only; everything in the sprint 2 annex not amended here
stands unchanged.

Design authority: no sprint 3 mocks exist ("UI from Claude Design.zip"
verified as a byte-identical duplicate of the committed sprint 2 mocks and
removed, approval record 2026-07-09). docs/design/sprint-3/UI-SPEC.md is
the binding look-and-behavior reference for the three new surfaces. Where
UI-SPEC conflicts with engine math, the engine wins and this file records
the deviation, exactly as the sprint 2 annex does.

## New surface-to-slice map

| Surface | Authority | Slice |
|---|---|---|
| Crop screen (pins, cold-start contract, flow rules) | UI-SPEC section 1 | S2 |
| Size block (chips, W x H inputs, in/cm toggle, suggestion rules) | UI-SPEC section 2 | S7 |
| Results size story (tappable size line, inline editor) | UI-SPEC section 2.4 | S7 |
| Verdict panels (no_grid, non_square_repeat, readable variants) | UI-SPEC section 3 | S8 |
| Overall pill failure tier | UI-SPEC section 4 | S8 |
| Progress-row failure states | UI-SPEC section 5 | S8 |
| Entry copy (dropzone sub-copy, start-screen lede) | UI-SPEC section 3 / plan S8 | S8 |

## Vocabulary additions (binding from S0)

- Period phrasing: periods are stated in squares or as "repeats about N
  times across its width" until a user-entered size exists; inches only
  with size_source="user". ASSUMED_PPI never converts a period.
- Honest failure copy: failure text names what QREP could not do and why
  it might have happened; it never blames the user, never shows a
  percentage next to a failure statement, and never calls an approximation
  a result.
- "Could not read this photo" is the failure pill's full text (accent
  tone, no number).

## Retired surface

- The post-results corners screen (sprint 2 map row "corner pins") is
  RETIRED in S2. Its behavior moves to the crop screen; "Adjust the crop"
  from results returns there seeded with the confirmed quad. The sprint 2
  PARITY row stays as history; this row supersedes it.

## Amended pill tier table (finalized in S8)

The pill is selected by VERDICT first, then by the sprint 2 mean-of-stages
percentage. "read as squares" is banned from all pill copy
(copy-audit-verdicts enforces).

| Verdict | Pill text | Tone | Number |
|---|---|---|---|
| no_grid | Could not read this photo | accent | NONE (dropped) |
| non_square_repeat | blocks repeat - squares uncertain (N%) | sprint 2 tier tone | kept, in parentheses |
| readable, readable_no_repeat, >= 92 | Overall confidence N% - very sure | sage | kept |
| readable, readable_no_repeat, 84-91 | Overall confidence N% - solid | sage | kept |
| readable, readable_no_repeat, 78-83 | Overall confidence N% - good - check the flags | amber | kept |
| readable, readable_no_repeat, < 78 | Overall confidence N% - needs your eye | accent | kept |

## Panel visibility matrix (finalized in S8)

Rendered 1:1 from verdictStory (web/src/model/verdictStory.ts); the
recovered-quilt PANEL is never removed, its content collapses.

| Verdict | Failure panel | Info panel | Quilt canvas | Caption | Disclosure label / banner |
|---|---|---|---|---|---|
| no_grid | yes (title + reason + actions) | no | behind disclosure | none | Show what we saw anyway / This reading is wrong - shown only to help you see what went wrong. |
| non_square_repeat | no | yes (title + period + size invite) | behind disclosure | none | Show the squares approximation / This is an approximation - the real blocks are not squares. |
| readable_no_repeat | no | no | visible | sampler caption | none |
| readable | no | no | visible | period caption when a repeat is confirmed, else none | none |

Side-stack rule (deviation recorded per the annex convention): on no_grid
the side stack's "Open in the editor" button is HIDDEN - opening the
wrong model beside "Could not read this photo" would contradict the
verdict; the failure panel's "Start in the editor" (blank-grid escape) is
the editor entry. "Adjust the crop" STAYS in the side stack on every
verdict: UI-SPEC section 1 pins that "Adjust the crop" from results,
success or failure, returns to the crop screen (the frozen S2 traversal
exercises this on a failure verdict). The lightbox link and the timing
line stay (UI-SPEC 3.1 keeps the side-by-side lightbox available).
Failure-panel action order (UI-SPEC 3.1): primary "Adjust the crop",
disclosure "Photo tips", secondary "Start in the editor".

Progress rows (UI-SPEC section 5): on verdict=no_grid the stage rows at
and after the failure point render a neutral dash (data-dashed), derived
from grid_diagnosis - no_quilt_found dashes all six rows; every other
diagnosis keeps the straighten and colors meters and dashes grid onward.
Other verdicts dash nothing.

## Verdict copy strings (finalized in S8)

Pinned by verdictStory.test.ts; hyphen-minus dashes throughout, no
percentage in any failure string.

- Failure pill: "Could not read this photo"
- Non-square pill label: "blocks repeat - squares uncertain"
- Failure panel title: "We could not find a square grid in this photo"
- Failure reasons, by grid_diagnosis:
  - no_quilt_found: "We could not tell the quilt apart from the background."
  - no_periodicity: "We did not find any repeating structure to read."
  - profile_too_short: "The photo is too small to read squares from."
  - anisotropic_pitch: "The rows and columns disagree - the photo may show the quilt at a steep angle."
  - implausible_dims: "The grid we found is not a plausible quilt."
  - weak_periodicity: "The square pattern is too faint to read confidently."
  - fallback (unknown diagnosis): "The pattern did not read as a grid of squares."
- Photo tips (failure panel disclosure): "Fill the frame with the quilt." /
  "Shoot square-on, not at an angle." / "Even light beats a bright window
  behind the quilt."
- Non-square info title: "This quilt's blocks repeat, but they may use
  shapes QREP cannot read yet (triangles and curves)" - "may use" softens
  UI-SPEC 3.2's "they use" per the plan (edge energy cannot fully
  distinguish piecing from busy prints); deviation recorded here.
- Size invite (unsized non-square only): "Know the size? Add it for a
  better answer."
- Sampler caption (readable_no_repeat): "No repeating block found - common
  for samplers and medallion quilts."
- Period phrasing (vocabulary rule upheld): sized (size_source="user")
  "It repeats every N in." with N a mixed fraction from
  block_period_cells x cell_size; unsized "It repeats about N times across
  its width." (floor(cols / period), only when N >= 2). ASSUMED_PPI never
  converts a period.
- Entry copy: dropzone sub-copy gains "A photo, a screenshot, or a shop
  listing picture all work."; start-screen lede gains "Size is optional:
  QREP guesses until you set the real one."

## Blank-grid escape gate (finalized in S8)

startBlankWithPalette (project.tsx startInEditorFromFailure): the blank
grid keeps the recovered palette ONLY when palette-stage confidence
>= 0.80 AND 2 <= k <= 6 (frozen in verdictStory.ts; calibration recorded
on #74: solid-fabric phantom palettes are killed by the k ceiling at k=8,
lighting-split palettes by the confidence floor at 0.64). Below the gate
the escape opens the plain sprint 2 blank grid (PARITY item 15).

## Chip component (finalized in S8)

PRESET chips reuse the design system chip primitive; single source of
truth is the engine PRESETS table exported through the bridge (S6).
States shipped in S7: default (line2 border, card surface), hover (accent
border), suggested (data-suggested: accent border, accent glow, and the
"looks about right?" hint line). A tapped chip commits the preset into
the W x H inputs (provenance user) rather than holding a selected state;
no disabled state exists. Dimensions render in the chip tooltip (desktop)
and under the label at small size (phone).
