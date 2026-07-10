# UI parity annex, sprint 4 amendment (binding)

Status: SKELETON written in S0 (issue #92), BINDING from S0 onward; FINALIZED
per surface in its slice (S2 copy, S4 document panel, S5 lightbox) — the exact
strings and table rows below are matched by the web copy-audit and
verdictStory tests when those slices land. Amends docs/design/sprint-2/PARITY.md
and docs/design/sprint-3/PARITY-AMENDMENT.md for sprint 4 scope only;
everything not amended here stands unchanged.

Design authority: no sprint 4 mocks exist. docs/design/sprint-4/UI-SPEC.md is
the binding look-and-behavior reference for the four sprint 4 surfaces. Where
UI-SPEC conflicts with engine math, the engine wins and this file records the
deviation, exactly as the sprint 2/3 annexes do.

## New/changed surface-to-slice map

| Surface | Authority | Slice |
|---|---|---|
| Pattern document panel (one download) | UI-SPEC section 1 | S4 |
| Mobile lightbox + labeled stacked compare | UI-SPEC section 2 | S5 |
| non_square_content verdict copy | UI-SPEC section 3 | S2 |
| Quilt-name display + editable title | UI-SPEC section 4 | S3/S4 |

## Retired surface (RETIREMENT RULE)

- The five per-artifact download buttons in `PatternPanel` (`download-pdf`,
  `download-cutlist-csv`, `download-cutlist-md`, `download-yardage`,
  `download-svg`) RETIRE in S4, replaced by one `download-document`. The
  engine exporters (`qrep/export/*`) and their CLI and `test_exports`
  coverage STAY as the developer surface. The sprint 2/3 rows for those
  buttons stay as history; this row supersedes them.

## Vocabulary additions (binding from S0)

- Generated-name vocabulary: the recovered quilt gets a deterministic name
  (structure word + mood word). The document and the results title show it;
  "Recovered quilt" remains only the pre-name model default.
- non_square_content copy: when a coarse block lattice is found under a failed
  square read, the honest line is "The blocks repeat, but the shapes inside
  are not squares," NOT the steep-angle line. "Steep angle" is reserved for
  genuine skew with no coarse block (recorded so S2 does not regress it).
- Document vocabulary: US Letter only this sprint; the document states the WOF
  assumption verbatim (42 in unless the #91 WOF checkbox flips to 40), seam
  allowance 1/4 in, finished-vs-cut, and abbreviations (WOF, HST, RST). The
  cover states honest technique ("straight seams, squares only"), never a
  numeric skill rating.

## Amended verdict copy strings (finalized in S2)

Pinned by `verdictStory.test.ts` and the copy-audit; hyphen-minus dashes
throughout, no percentage in any failure string.

- non_square_content info title: "The blocks repeat, but the shapes inside are
  not squares."
- non_square_content body: "QREP reads quilts made of squares. This one looks
  like it is pieced from curves or triangles, so the squares below are an
  approximation of the block layout, not the real shapes."
- anisotropic_pitch (genuine skew only): unchanged sprint-3 string, now
  conditioned on the ABSENCE of a coarse block lattice.
- Squares-approximation disclosure: unchanged sprint-3 pattern.

## Document section order (finalized in S3)

Rendered by `qrep/export/pdf.py` `build_sections`; content assertions (not PDF
bytes) pin each section:

1. Cover — full-page recovered-quilt render, generated name, finished size,
   honest technique line, QREP byline, 1-inch calibration square + "print at
   100%, US Letter" note.
2. Your quilt vs the pattern — original photo beside the recovered render,
   verdict line, per-stage confidence table.
3. Fabrics — existing yardage plus swatch chips.
4. Assumptions — seam allowance 1/4 in, WOF assumption (as the #91 checkbox
   decides), finished-vs-cut note, abbreviations.
5. Cutting — existing chart.
6. Strip sets.
7. Assembly — existing steps plus per-step block figures rendered from the
   model.
8. Borders. 9. Binding. 10. Finishing.
11. Coloring page — blank line-art grid of the recovered quilt.
- Footer on every page: name, page number, "made with QREP from your photo",
  generation date.

## Mobile lightbox parity (finalized in S5)

- `.pf-lb-stage` moves off `max-height: 78vh` to `dvh`-based sizing with a
  `vh` fallback; top-anchored scroll column, not centered flex.
- Compare stacks with visible labels below 640 px; side by side above when
  both fit. No unlabeled wrap at any width (the #90 defect).
- Body scroll lock while open; safe-area insets; visual-viewport anchoring for
  the iOS 26 fixed-position regression.
- MOBILE-WEBKIT LENS: every touched UI slice runs its Playwright specs on an
  iPhone-class WebKit emulation profile in addition to desktop; a mobile-only
  failure is a major review finding.

## Pill / panel matrices

The sprint-3 pill-tier and panel-visibility matrices stand. non_square_content
routes through the existing `non_square_repeat` panel (info panel + squares
approximation behind the disclosure); only the copy strings change, per the
section above.
