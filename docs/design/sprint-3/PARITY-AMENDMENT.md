# UI parity annex, sprint 3 amendment (binding skeleton)

Status: SKELETON written in S0 (issue #66), BINDING from S0 onward;
finalized in S8 (the sections marked "finalized in S8" gain their exact
strings and table rows there). Amends docs/design/sprint-2/PARITY.md for
sprint 3 scope only; everything in the sprint 2 annex not amended here
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

Sprint 2 tiers stand for successful reads: >= 92 very sure, >= 84 solid,
>= 78 good - check the flags, else needs your eye. New failure tier per
UI-SPEC section 4. Exact table rows and copy strings land here in S8,
matched by the copy-audit test.

## Panel visibility rules (finalized in S8)

Disclosure and banner semantics per UI-SPEC sections 3.1 and 3.2 (failure
never hides evidence; approximations are labeled). Exact visibility matrix
lands here in S8.

## Chip component (finalized in S8)

PRESET chips reuse the design system chip primitive; single source of
truth is the engine PRESETS table exported through the bridge (S6). Exact
states (default, suggested, selected, disabled) land here in S7/S8.
