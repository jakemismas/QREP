# Mock implementation notes (derived 2026-07-09 from the committed .dc.html mocks)

Derived reference for building web/. The mocks + PARITY.md remain binding; where these notes and the mock disagree, the mock wins. Where the mock lacks a state the slice contract requires (e.g. the engine chip failed state), the contract wins and the design extends the DS idiom.


---

## SECTION: DESIGN SYSTEM

# QREP Design System — implementation notes (source: `C:\Users\Jake Mismas\QREP\docs\design\sprint-2\QREP Design System.dc.html`)

Supplemented where noted with `QREP.dc.html` (main app mock, same dir) for states the DS page does not show. `support.js` is the dc-runtime React shim only — it defines **no** design tokens (its two hex values, `#f0eee6`/`#2e2c26`, are the runtime's own preview-canvas backgrounds, not QREP tokens).

Theming mechanism in the mock: `[data-skin="light"]` / `[data-skin="dark"]` attribute selectors set all custom properties. Light is called **Daylight**, dark **Evening**.

---

## 1. Design tokens

### 1a. Color tokens (CSS variables, exact hex)

Named rows are documented in the mock's own token table (`colorRows`); rows below the rule exist in the skin CSS but are undocumented in the table — still required.

| CSS var | Name / use | Light (Daylight) | Dark (Evening) |
|---|---|---|---|
| `--bg` | Desk · app background | `#f2ebdc` | `#211a10` |
| `--card` | Card · panels, sheets | `#fffdf7` | `#2e2517` |
| `--card2` | Card sunken · wells, toolbars | `#faf5e8` | `#382e1d` |
| `--ink` | Ink · primary text | `#453a2a` | `#f0e6d0` |
| `--mut` | Muted ink · labels, captions | `#8a7a61` | `#b3a184` |
| `--line` | Seam line · borders, dividers | `#e7dcc4` | `#453a26` |
| `--accent` | Terracotta · primary action, low confidence | `#a5502f` | `#d98a5e` |
| `--sage` | Sage · success, high confidence | `#4c7a5a` | `#9cc2a1` |
| `--amber` | Goldenrod · busy, mid confidence | `#a8781f` | `#d9ae55` |
| `--denim` | Denim · engine, downloads | `#53718b` | `#93b3cf` |
| `--stage` | Cutting mat · canvas stage | `#e9dfc9` | `#181208` |
| `--card3` | deeper sunken well (progress container, meter track, toggle-off track) | `#f8f1df` | `#3f3421` |
| `--ink2` | secondary text (button labels, values) | `#5d4f39` | `#ddcfb0` |
| `--faint` | faintest text (units, stage labels, fine print) | `#a3937a` | `#93826a` |
| `--line2` | stronger border (input/button borders) | `#d9c8a8` | `#5b4b2e` |
| `--accentB` | terracotta hover | `#8c3f22` | `#e3a077` |
| `--accentInk` | text on terracotta | `#fdf6e9` | `#2a1305` |
| `--sageBg` | sage tint background | `#eef2e2` | `#2b3722` |
| `--sageLn` | sage tint border | `#d4dcba` | `#48593a` |
| `--pill` | chip/pill background | `#fbf7ec` | `#382e1d` |
| `--pillLn` | chip/pill border | `#ddcfb2` | `#5b4b2e` |
| `--shadow` | button shadow color | `rgba(96,66,28,.12)` | `rgba(0,0,0,.45)` |

**Fixed colors that never theme** (identical in both skins):
- Fabric/swatch colors are the user's data and never theme. Demo fabrics: `#a9c7dc` (Light Blue Chain), `#f7f1e0` (Cream Background).
- Uncertain-cell overlay: fill `rgba(196,90,40,0.32)`, stroke `#d06a35`.
- Toggle knob: `#fffdf7`.
- Toast success bg `#43372a` / text `#fbf4e4`; toast error bg `#8c3f22` / text `#fdf6e9`.
- Tooltip bg `#2b2115` / text `#f6ecd9` ("dark in both themes").
- Modal backdrop `rgba(18,12,6,0.6)`.
- Mini-quilt demo stage `#f7f1e0` with border `#cbb894`.
- Logo four-square: `#a9c7dc` + `#a5502f`, rects `rx:2.5`.
- DS doc chrome (not app surface): page bg `#efe8d8`, links `#a5502f` hover `#8c3f22`, heading ink `#3f3423`, section headings `#53718b` (denim).

### 1b. Typography

Font stacks (defined on `body`):
- `--serif: 'Bookman Old Style','URW Bookman',Bookman,'Iowan Old Style',Palatino,serif` — headings **and measurements**.
- `--sans: Seravek,'Gill Sans','Trebuchet MS',Verdana,sans-serif` — everything else.

Stated rules: "Body is 17px — quilters read glasses-off. Minimum 13px, and only for footnotes." (App shell in the mock uses 16.5px base.)

Type scale (from `typeRows`, with exact sample strings):

| Role | Spec | Sample copy |
|---|---|---|
| Display | 700 38px serif, `#3f3423` | "What are we making today?" |
| Screen title | 27–30px / 700 serif (sample 28px), `#3f3423` | "Here's what we found" |
| Panel title | 700 21px serif, `#3f3423` | "Sizing" |
| Measurement | 700 22px serif, terracotta `#a5502f` | "82½″ × 90″ finished" |
| Body | 16.5px/1.55 sans, `#5d4f39` (`--ink2`) | "Cut squares at 2″ — ¼″ seams included." |
| Caption | 13.5px sans, `#a3937a` (`--faint`) | "Rounded up to the next ¼ yard · estimate" |

Other observed sizes: section h2 700 26px serif; component h3 700 19px serif; skin badge 10.5px uppercase letter-spacing .12em `--faint`; stat labels 11px uppercase letter-spacing .08em; stage labels 11.5px; fine hints 12.5px.

Quilters' arithmetic rule: mixed fractions everywhere — "2½″, never 2.5". Finished sizes labeled as such; seam allowances spelled out.

### 1c. Radii

Stated: **cards 16 · panels & inputs 10 · segmented controls 11 outside, 8 inside · pills 999.** "Nothing sharp."
Observed per-element: demo card containers 14; primary button 11; secondary buttons/inputs/select/steppers 10; selected-option card 13; swatch row card 12; progress container 11; table swatch chip 6; fabric swatch 9; modal 18; modal close button 9; tooltip 8; toast/chips/meters/pills 999; dropzone 14.

### 1d. Spacing

- Base **4px scale**. Card padding **18–20**; rows **12**; section gaps **14–16**.
- Hit targets **≥ 44px** on touch; steppers **36–44px** wide.
- Dashed dividers (`1px dashed var(--line)` in components) mark section seams "like basting stitches".
- Layout: desktop = canvas + one **376px** side panel with tabs; tablet same with narrower panel; iPhone = bottom tab bar (**Quilt · Fabrics · Sizing · Pattern**), panels become full-width pages.

### 1e. Shadows

| Use | Value |
|---|---|
| Primary button | `0 4px 12px var(--shadow)` |
| Modal panel | `0 24px 60px rgba(0,0,0,0.35)` |
| Toast | `0 10px 26px rgba(30,18,6,0.4)` |
| Tooltip | `0 6px 18px rgba(0,0,0,0.3)` |
| Toggle knob | `0 1px 4px rgba(0,0,0,0.3)` |
| Fabric swatch (inner) | `inset 0 -2px 5px rgba(0,0,0,0.07)` |
| Selected-card radio dot ring | `inset 0 0 0 3px var(--card)` |
| Input focus ring | `0 0 0 3px rgba(165,80,47,0.16)` + `border-color: var(--accent)` |

### 1f. Borders

Default hairline `1px solid var(--line)`; interactive controls `1.5px solid var(--line2)`; selected card `2px solid var(--accent)`; dropzone `2.5px dashed var(--line2)`; progress container `1px dashed var(--line2)`; row dividers `1px dashed var(--line)`.

### 1g. Animations (keyframes)

```css
@keyframes qSpin  { to { transform: rotate(360deg); } }
@keyframes qPulse { 0%,100% { opacity:1; } 50% { opacity:.35; } }
@keyframes qToast { from { opacity:0; transform:translate(-50%,10px); }
                    to   { opacity:1; transform:translate(-50%,0); } }
```
Usage: button spinner `qSpin .8s linear infinite`; engine-chip spinner `qSpin .9s linear infinite`; busy/saving dots `qPulse 1s ease infinite`; toast entry `qToast .28s ease`. Transitions: toggle track/knob `.15s`; progress fill `width .12s`.

---

## 2. Component specs

### Buttons
- **Primary**: bg `var(--accent)`, text `var(--accentInk)`, no border, radius 11, padding `13px 20px`, font `600 15.5px sans`, shadow `0 4px 12px var(--shadow)`. Hover: bg `var(--accentB)`. Copy: "Start from a photo".
- **Secondary**: bg `var(--card)`, border `1.5px solid var(--line2)`, radius 10, padding `11px 16px`, font `500 14.5px sans`, color `var(--ink2)`. Hover: bg `var(--card2)`. Copy: "Open".
- **Link/text button**: no bg/border, padding `4px 0`, 14.5px, color `var(--accent)`, underlined, `text-underline-offset: 3px`. Copy: "Compare full size".
- **Disabled**: secondary style + `opacity: .45`, `cursor: not-allowed`. Copy: "Disabled".
- **Busy**: secondary style (font 600), `opacity: .75`, `cursor: wait`, flex gap 8; 14×14 SVG spinner (circle r 5.5, stroke `currentColor` width 2.4, `stroke-dasharray: 24 12`) spinning `qSpin .8s linear infinite`. Copy: "Making it…" (idle demo label: "Export — tap me"; demo busy duration 1600 ms).
- **Small secondary** (utility row): padding `10px 14px`, font `600 13.5px`.
- **Stepper** (−/+): 38w × 48h, font-size 20, color `var(--ink2)`, bg `var(--card2)`, border `1.5px var(--line2)`, radius 10, hover bg `var(--card3)`, `line-height: 1`. Glyphs `−` / `+`.

### Engine status chip
Pill: flex, gap 8, padding `8px 13px`, border `1px solid var(--pillLn)`, radius 999, bg `var(--pill)`, 13px, color `var(--ink2)`.
- **Booting/warming**: 13×13 SVG spinner (circle r 5, stroke `var(--denim)` width 2.4, `stroke-dasharray: 22 10`), `qSpin .9s linear infinite`. Text: **"engine warming up"**.
- **Ready**: 9px round dot, bg `var(--sage)`. Text: **"engine ready"**.
- **Busy** (from `QREP.dc.html` line 47): 9px round dot, bg `var(--amber)`, `animation: qPulse 1s ease infinite`. Text: **"engine busy"**.
- **Failed**: **NOT DESIGNED** — no failed state exists in either mock (verified by grep of both files). Implementation must invent it or raise it; the obvious pattern by system logic would be a terracotta dot + error copy, but that is extrapolation, not mock.
- Main-mock behaviors: text label shown on desktop only (icon-only on mobile); chip carries a tooltip: "The Python engine runs in your browser — it boots in a few seconds on first load."

### Autosave dot
9px round dot + label, gap 7px, 13px text color `var(--mut)`.
- **Saved**: dot `var(--sage)`, static. Text: **"Autosaved"**.
- **Saving** (from `QREP.dc.html` lines 1581–1582): dot `var(--amber)` + `qPulse 1s ease infinite`. Text: **"Saving…"**.

### Fraction input (with steppers)
- Field label: 14px `var(--mut)`, margin-bottom 6; copy "Square size" with unit suffix "· in" in `var(--faint)`.
- Row: flex gap 5, max-width 220px; stepper buttons (spec above) flanking the input.
- Input: width 100% center-aligned, font `600 17px serif`, color `var(--ink)`, bg `var(--card)`, border `1.5px solid var(--line2)`, radius 10, padding `6px 2px`. Focus: `border-color: var(--accent); box-shadow: 0 0 0 3px rgba(165,80,47,0.16); outline: none`.
- Helper text below: 12.5px `var(--faint)`, margin-top 5: "Accepts "2 1/2", "2½" or "2.5" — always shows mixed fractions."
- Behavior (from the mock's logic): parse accepts `N M/D` (space or hyphen separator), `M/D`, plain decimal; strips `″` and `"`. Commit on blur (Enter blurs): clamp to **[0.25, 20]**, round to nearest **1/8**, reformat as mixed eighth fraction (`1/8 1/4 3/8 1/2 5/8 3/4 7/8`). Invalid input reverts to previous value and fires error toast **"Mixed fractions like 2 1/2"**. Steppers ±0.25, floor 0.25.

### Dropdown (native select)
Label "Standard size" (14px `var(--mut)`), block max-width 280. Select: width 100%, padding `11px 12px`, 15.5px sans, color `var(--ink)`, bg `var(--card)`, border `1.5px solid var(--line2)`, radius 10, cursor pointer. Options (values crib/throw/twin/queen, default twin):
- "Crib — 36 × 52" · "Throw — 50 × 65" · "Twin — 70 × 90" · "Queen — 90 × 108"

### Toggle
Wrapper is a borderless button, flex gap 11. Track: 46×27, radius 999, `transition: background .15s`. On: bg + border `var(--sage)` (border 1.5px). Off: bg `var(--card3)`, border `1.5px solid var(--line2)`. Knob: absolute top 2, 20×20 circle, bg fixed `#fffdf7`, shadow `0 1px 4px rgba(0,0,0,0.3)`, `transition: left .15s`; left **22px** on / **3px** off. Label: 14.5px `var(--ink2)`: "Highlight uncertain squares".

### Proportion lock
44×44 button, radius 10, flex-centered padlock icon (SVG stroke-width 2.2, body rect 13×9.5 rx 2.5 filled `currentColor`; locked icon 19×21 closed shackle, unlocked 21×21 open shackle).
- **Locked**: bg `#f6e7da`, border `1.5px solid #cf9a7f`, icon color `var(--accent)`. Label: "Locked — scale together".
- **Unlocked**: bg `var(--card2)`, border `1.5px solid var(--line2)`, icon color `var(--mut)`. Label: "Unlocked — whole blocks".
- Label beside button: 14.5px `var(--ink2)`, gap 11.
- CAUTION: the locked-state bg/border (`#f6e7da`/`#cf9a7f`) are hard-coded light-tint values, not vars — they will look wrong in Evening unless mapped to a token (they play the role of an "accent tint"; no `--accentBg` token exists).

### Confidence meter (row)
Row: flex gap 10, padding `7px 0`, border-bottom `1px dashed var(--line)`.
- Label: flex 1, 14.5px `var(--ink2)`.
- Meter: 92×10, bg `var(--card3)`, border `1px solid var(--line)`, radius 999, overflow hidden; fill block `width: {pct}%`, bg color-mapped, radius 999.
- Percent: 38px right-aligned, 13px 700, `var(--ink2)`.
- Word: 70px right-aligned, 12.5px 700, same color as fill.
- **Color/word mapping (normative)**: `var(--sage)` **≥ 85%**, `var(--amber)` (goldenrod) **80–84%**, `var(--accent)` (terracotta) **below 80%**. Demo rows: Straighten 98% "Very sure" (sage); Repeats 84% "Good" (amber); Squares 71% "Check it" (terracotta).

### Staged progress bar
Container: bg `var(--card3)`, border `1px dashed var(--line2)`, radius 11, padding `12px 14px`.
- Header row: space-between, 13.5px `var(--ink2)`; left = status text, right = bold percent ("{n}%").
- Track: height 11, bg `var(--card)`, border `1px solid var(--line)`, radius 999, overflow hidden. Fill: block, `width: {pct}%`, bg `var(--denim)`, radius 999, `transition: width .12s`.
- Stage labels under track: space-between, 11.5px `var(--faint)`, margin-top 7, wrap allowed. Stages in order: **straighten · colors · grid · cells · repeats · borders**.
- Status copy: in progress "Loading the vision engine — first time only"; complete "Vision engine ready". (PARITY.md bans "download" language.) DS demo also has a link-style "Replay loading" control: `600 13px var(--accent)` underlined.

### Low-confidence cell treatment ("hatch")
Despite the name, both mocks render it as a **translucent terracotta overlay square with an outline**, per uncertain cell (verified in `QREP.dc.html` — the `hatchD` path is full-cell rects, `M x y h w v w h -w z`):
- fill `rgba(196,90,40,0.32)`, stroke `#d06a35`, stroke-width 1 (DS demo uses 1.2). Fixed colors, both themes.
- Drawn on top of the cell's fabric color. Toggled by "Highlight uncertain squares".
- Explanatory copy: "Squares the vision engine isn't sure about hatch in terracotta. Painting one by hand clears the doubt — hand edits are certain."
- Main-mock caption pattern when active: "{W}″ × {H}″ finished — {n} uncertain squares hatched".
- Threshold (from PARITY.md): uncertain = per-cell confidence < 0.90 from the engine.

### Cards
- **Demo/panel card container**: bg `var(--bg)` (in DS demos) or `var(--card)`, border `1px solid var(--line)`, radius 14, padding 18. Corner skin badge: absolute top 10 right 14, 10.5px uppercase, letter-spacing .12em, `var(--faint)`.
- **Selectable option card (selected state)**, e.g. strategy picker: bg `var(--card3)`, border `2px solid var(--accent)`, radius 13, padding `12px 14px`. Radio dot: 14px circle, bg `var(--accent)`, `box-shadow: inset 0 0 0 3px var(--card)`, border `1px solid var(--accent)`, gap 9 to title. Title `700 15.5px sans var(--ink)` "Strip piecing". Description 13px `var(--mut)`: "Sew long strips first, then crosscut whole rows at once." Stats: 3-col grid gap 6; stat label 11px uppercase `.08em` `var(--faint)` ("Pieces", "Cuts", "Sewing ⓘ"); stat value `700 15px serif var(--ink2)` ("1,331", "95", "~5½ h").

### Table (fabric/yardage)
`width:100%; border-collapse:collapse`; rows divided by `border-bottom: 1px dashed var(--line)` (last row none). Cell padding `9px 6px` (outer cells drop the outer 6px).
- Col 1: 22×22 swatch chip (radius 6, border `1px solid var(--line2)`, fabric color) + name `600 14px var(--ink)` nowrap ("Light Blue Chain").
- Col 2: 12.5px `var(--mut)` detail ("1,313 squares · cut 2″"; "1,162 squares + borders").
- Col 3 (right-aligned): value `700 14.5px serif var(--ink)` ("4¼ yd", "5½ yd") over 11px italic `var(--faint)` "estimate".

### Fabric swatch row (editor)
Flex gap 12, bg `var(--card)`, border `1px solid var(--line)`, radius 12, padding `10px 12px`.
- Swatch: 40×40, radius 9, fabric color, border `1px solid var(--line2)`, `inset 0 -2px 5px rgba(0,0,0,0.07)`.
- Name: `600 15px sans var(--ink)` "Light Blue Chain ✎" (pencil marks renamable); sub-line 13px `var(--mut)` "#A9C7DC · 1,313 squares" (uppercase hex).
- Hint pill (right, flex none): 11.5px `var(--faint)`, border `1px solid var(--pillLn)`, bg `var(--pill)`, radius 999, padding `3px 9px`: "tap swatch to recolor".

### Dropzone
Border `2.5px dashed var(--line2)`, radius 14, bg `var(--card2)`, padding `22px 16px`, centered column, gap 7, cursor pointer. Hover: `border-color: var(--accent); background: var(--card)`.
- Icon: 40×34 camera outline SVG, stroke `currentColor` at `var(--mut)`, stroke-width 2.2.
- Title: `700 17px serif var(--ink)`: "Drop your quilt photo here".
- Sub: 13px `var(--mut)`: "JPG or PNG — or tap to browse".

### Toast
`position: fixed; left: 50%; bottom: 26px; transform: translateX(-50%)`; flex gap 10; padding `13px 24px`; radius 999; 15.5px; z-index 80; shadow `0 10px 26px rgba(30,18,6,0.4)`; entry `qToast .28s ease`. Auto-dismiss after **3200 ms**. **Never stack** — a new toast replaces the current one. Colors fixed in both themes.
- **Success**: bg `#43372a`, text `#fbf4e4`, glyph `✓`. Example: "Saved — check your downloads folder."
- **Error**: bg `#8c3f22` (terracotta-dark), text `#fdf6e9`, glyph `⚠`. Example: "That file isn't a QREP project — nothing was changed." Rule: errors "always say what *didn't* happen".

### Modal
Overlay `fixed inset:0; z-index:60`; backdrop `rgba(18,12,6,0.6)` ("warm backdrop at 60%"), click closes. Panel: centered `translate(-50%,-50%)`, `width: min(420px, calc(100vw - 32px))`, radius 18, padding 24, shadow `0 24px 60px rgba(0,0,0,0.35)`; bg/border shown hard-coded light (`#fffdf7` / `1px #e7dcc4`) — map to `var(--card)`/`var(--line)` for theming (the DS modal demo sits outside any `data-skin` wrapper).
- Header: title `700 22px serif` denim `#53718b`, flex 1; close button 38×38, bg `#faf5e8` (→`--card2`), border `1px #e7dcc4` (→`--line`), radius 9, glyph `✕`, 16px, color `#5d4f39` (→`--ink2`).
- Body: 14.5px/1.55, `#8a7a61` (→`--mut`).
- Footer: flex gap 10; **primary action sits LEFT** ("Got it": terracotta primary, radius 10, padding `12px 18px`, `600 15px`), then "Cancel" (secondary, `1.5px #d9c8a8` border).
- Close paths: **Escape, ✕, and backdrop** all close it.

### Tooltip
`position: fixed`, centered above target: `transform: translate(-50%,-100%)`, anchored at target-center x, target-top − 9px. bg `#2b2115`, text `#f6ecd9` (dark in BOTH themes), padding `7px 12px`, radius 8, `13px sans`, `z-index: 90`, `pointer-events: none`, `white-space: nowrap`, shadow `0 6px 18px rgba(0,0,0,0.3)`. Rules: hover only; one short sentence; **never hide required information in a tooltip**. Demo copy: "Tooltips are one short sentence, dark in both themes".

---

## 3. Exact copy strings (complete inventory from the DS mock)

- Buttons: "Start from a photo" · "Open" · "Compare full size" · "Disabled" · "Export — tap me" · "Making it…" · "Show success toast" · "Show error toast" · "Open modal" · "Hover for tooltip" · "Got it" · "Cancel" · "Replay loading"
- Engine chip: "engine ready" · "engine warming up" · (main mock) "engine busy"; chip tooltip (main mock): "The Python engine runs in your browser — it boots in a few seconds on first load."
- Autosave: "Autosaved" · (main mock) "Saving…"
- Fraction input: label "Square size" + "· in"; helper "Accepts "2 1/2", "2½" or "2.5" — always shows mixed fractions."; error toast "Mixed fractions like 2 1/2"
- Dropdown: label "Standard size"; options "Crib — 36 × 52" / "Throw — 50 × 65" / "Twin — 70 × 90" / "Queen — 90 × 108"
- Toggle: "Highlight uncertain squares"
- Lock: "Locked — scale together" / "Unlocked — whole blocks"
- Progress: "Loading the vision engine — first time only" / "Vision engine ready"; stages "straighten colors grid cells repeats borders"
- Confidence words: "Very sure" (≥85) / "Good" (80–84) / "Check it" (<80); demo labels "Straighten" "Repeats" "Squares"
- Uncertainty caption: "Squares the vision engine isn't sure about hatch in terracotta. Painting one by hand clears the doubt — hand edits are certain."
- Strategy card: "Strip piecing" · "Sew long strips first, then crosscut whole rows at once." · stats "Pieces 1,331" "Cuts 95" "Sewing ⓘ ~5½ h"
- Table: "Light Blue Chain" · "1,313 squares · cut 2″" · "4¼ yd" · "estimate" · "Cream Background" · "1,162 squares + borders" · "5½ yd"
- Swatch row: "Light Blue Chain ✎" · "#A9C7DC · 1,313 squares" · "tap swatch to recolor"
- Dropzone: "Drop your quilt photo here" · "JPG or PNG — or tap to browse"
- Toasts: "Saved — check your downloads folder." · "That file isn't a QREP project — nothing was changed."
- Tooltip demo: "Tooltips are one short sentence, dark in both themes"
- Type samples: "What are we making today?" · "Here's what we found" · "Sizing" · "82½″ × 90″ finished" · "Cut squares at 2″ — ¼″ seams included." · "Rounded up to the next ¼ yard · estimate"
- Normative footnote: "Confidence words map to fills: sage ≥ 85%, goldenrod 80–84%, terracotta below 80%. Toasts sit bottom-center and never stack; errors are terracotta and always say what didn't happen. Tooltips appear on hover only — never hide required information in them."

## 4. Gaps and implementation cautions

1. **Engine "failed" state is not designed anywhere** (grepped both mocks; states are `boot`/`ready`/`busy` only). It needs a design decision.
2. **Proportion-lock locked state uses hard-coded light tints** (`#f6e7da` bg / `#cf9a7f` border) with no dark equivalents — needs an accent-tint token pair for Evening.
3. **Modal demo bypasses theming** (hard-coded light values outside a `data-skin` scope) — map to `--card`/`--line`/`--card2`/`--ink2`/`--mut` as annotated above.
4. **"Hatch" is not a hatch pattern** — it is a per-cell translucent overlay rect (`rgba(196,90,40,0.32)` fill + `#d06a35` 1px stroke) in both mocks; do not implement diagonal lines.
5. `--sageBg`/`--sageLn` are defined in both skins but unused on the DS page (used elsewhere in the main mock); include them in the token set.
6. Per PARITY.md, "download" wording is banned in loading copy — the progress bar copy above ("Loading the vision engine") is already the corrected form.

Source files: `C:\Users\Jake Mismas\QREP\docs\design\sprint-2\QREP Design System.dc.html` (primary), `C:\Users\Jake Mismas\QREP\docs\design\sprint-2\QREP.dc.html` (busy chip, saving dot, hatch geometry, engine tooltip), `C:\Users\Jake Mismas\QREP\docs\design\sprint-2\PARITY.md` (0.90 uncertainty threshold, copy corrections).


---

## SECTION: SHELL, START SCREEN, OPEN MODAL

# QREP mock notes: shell/header, start screen, open-project modal

Source: `C:\Users\Jake Mismas\QREP\docs\design\sprint-2\QREP.dc.html` (2043 lines). Markup: header lines 28-54, start screen 58-92, open modal 634-655, toast 657-662, tooltip 664-666. All logic is inline in the `text/x-dc` script (lines 669-2067). `support.js` in the same directory is only the template/DSL runtime (React-based `DCLogic`), not app logic.

## 0. Global/framework facts needed by all three areas

- **Breakpoint:** `isDesk = viewportWidth >= 720`. Below 720px the header hides: tagline, project-name input, autosave text (dot stays), engine chip text (status dot stays). Tooltips are fully suppressed below 720px.
- **Theme:** CSS custom properties on `body` (light) and `body[data-theme="dark"]` (dark). Toggle sets `document.body.setAttribute('data-theme', t)` and persists `localStorage['qrep-theme'] = 'light'|'dark'`. Read back on boot (only `'dark'` is honored; anything else means light).
- **Screens** (state `screen`): `home | drop | progress | results | corners | editor`. `main` max-width 1420px, centered, padding `20px 22px 44px` desktop / `16px 14px 44px` mobile (editor-on-phone: `12px 12px 96px`).
- **Fonts/tokens:** serif `Bookman Old Style...` for headings, sans `Seravek/Gill Sans...` for UI. Key colors (light): `--bg #f2ebdc`, `--card #fffdf7`, `--accent #a5502f`, `--accentB #8c3f22` (hover), `--accentInk #fdf6e9`, `--sage #4c7a5a`, `--amber #a8781f`, `--denim #53718b`, `--mut #8a7a61`, `--faint #a3937a`, `--line #e7dcc4`, `--line2 #d9c8a8`, `--pill #fbf7ec`, `--pillLn #ddcfb2`.
- **Keyframes used here:** `qSpin` (rotate 360, engine boot spinner .9s linear infinite), `qPulse` (opacity 1 to .35, 1s, autosave "saving" dot and engine "busy" dot), `qToast` (toast entry, .28s), `qFade` (screen entry, translateY 8px + fade, .35-.4s).

## 1. App shell / header

### Layout (line 28)
Sticky (`position:sticky; top:0; z-index:30`), background `var(--card)`, `border-bottom:1px solid var(--line)`, padding `9px 16px`, flex row gap 12px, `box-shadow:0 2px 10px var(--shadow)`. Hidden when printing (`data-noprint`). Child order:

1. **Logo/home button** — borderless button, flex row gap 9px. Contents: 26x26 SVG four-patch (rounded 11x11 rects rx=2 at (1,1)/(14,1)/(1,14)/(14,14); TL+BR `#a9c7dc` light blue, TR+BL `var(--accent)`), then wordmark `QREP` (serif 700 20px, letter-spacing .05em), then desktop-only tagline `quilt reverse-engineering` (italic serif 13px, `--mut`). Tooltip: `Back to the start screen`. Click = `goHome` which ONLY sets `screen:'home'` (model, projName, undo stacks are untouched — returning home does not discard work).
2. **Project name input** (desktop only) — `<input value={projName}>`, `flex:0 1 240px; min-width:120px`, transparent 1.5px border, radius 9px, padding 8px 10px, font 600 15.5px sans, color `--ink2`. Hover: `border-color:var(--line2)`. Focus: `border-color:var(--accent); outline:none; background:var(--card2)`. Tooltip: `Project name — click to rename`. onChange per keystroke: `setState({projName}); _touch()` (i.e. every keystroke marks dirty and debounce-autosaves). No Enter/blur handling; no explicit commit step. Initial value: resume name from autosave if present, else `My quilt project`.
3. **Spacer** `flex:1`.
4. **Autosave indicator** — flex row gap 7px, 13.5px, `--mut`. Tooltip: `Changes save to this device automatically`. Dot: 9px circle; `saved` state = `background:var(--sage)` steady; `saving` = `background:var(--amber)` with `qPulse 1s ease infinite`. Text (desktop only): `Autosaved` when saved, `Saving…` when saving. **Autosave mechanics** (`_touch`, lines 1008-1016): on any mutation set `saveState:'saving'` immediately, debounce 700ms, then write `{name: projName, model}` to `localStorage['qrep-autosave']` and set `saveState:'saved'`. Every model mutation, project rename, editor open, and analysis completion calls `_touch()`.
5. **Open button** — text `Open`. Style: `background:var(--card); border:1.5px solid var(--line2); radius 9px; padding 9px 14px; font 500 14.5px; color:--ink2`; hover `background:var(--card2)`. Click: `setState({jsonOpen:true})` (opens the open-project modal; available on every screen).
6. **Save button** — text `Save`, identical style to Open. Click (`saveJson`, lines 1585-1589): slug = `projName` lowercased, `[^a-z0-9]+` runs replaced with `-`; downloads `<slug>.qrep.json` containing `JSON.stringify({app:'QREP', version:1, name: projName, model}, null, 1)` MIME `application/json` via a Blob + temporary `<a download>` click (`_download`, lines 1342-1351). Toast on success: `Project saved as <slug>.qrep.json` (ok); on failure: `Save didn’t work — try again?` (err). Works from any screen; no disabled state.
7. **Engine status chip** — pill: `padding 8px 13px; border 1px solid var(--pillLn); border-radius 999px; background:var(--pill); font-size 13px; color:--ink2`, flex gap 8px. Tooltip (all states): `The Python engine runs in your browser — it boots in a few seconds on first load.` Three exclusive states driven by state `engine`:
   - `boot` (initial): 13px SVG spinner circle, stroke `var(--denim)`, `stroke-dasharray 22 10`, `qSpin 0.9s linear infinite`. Text `engine warming up`.
   - `ready`: 9px solid `var(--sage)` dot. Text `engine ready`.
   - `busy`: 9px `var(--amber)` dot with `qPulse 1s ease infinite`. Text `engine busy`.
   Text is desktop-only; the dot/spinner always shows. **Transitions:** boot -> ready via 1500ms timer after mount; ready -> busy when photo analysis starts (`_startAnalysis`) and during any export download (`_startDl`, ~620ms); busy -> ready when analysis finishes, is cancelled, or the export completes. Separately, a 6000ms idle timer sets `visionDL:true` (vision model "prefetched in the background") — this does NOT change the chip, it only changes the progress screen's later behavior (cached notice instead of download bar).
8. **Theme toggle** — 40x40 button, same bordered-card styling as Open/Save, icon-only: sun SVG (circle r4 + 8 rays, currentColor) when light, moon (crescent path) when dark. Tooltip: light -> `Switch to evening mode`; dark -> `Switch to daylight mode`. Click toggles theme, stamps `body[data-theme]`, persists to localStorage.

## 2. Start / first-run screen (`screen === 'home'`)

Container: `max-width:880px; margin:30px auto 0; animation:qFade .4s ease`.

### Copy block (top)
- Eyebrow: `QREP · quilt reverse-engineering` — 12.5px, letter-spacing .18em, uppercase, `--denim`, weight 700.
- H1: `Turn a quilt photo into a pattern.` — serif 700 40px, `--denim`, line-height 1.12.
- Subhead: `QREP finds the grid, matches the fabrics, and does the sizing and yardage math. Everything runs right here in your browser.` — 17.5px, `--mut`, max-width 56ch.

### Resume banner (conditional, between subhead and action row)
- Shown when `localStorage['qrep-autosave']` JSON-parses and has `model.cols`, `model.cells`, `model.fabrics` (checked once at construction; `hasResume` also requires `screen === 'home'`).
- Button: flex row gap 10px, `background:var(--sageBg); border:1.5px solid var(--sageLn); radius 12px; padding 13px 18px; font 600 15.5px; color:var(--sage); margin-bottom 20px`; hover `border-color:var(--sage)`. 15px circular-arrow (resume/history) SVG.
- Copy: `Continue where you left off — {resumeName}` where `resumeName = autosave.name || 'your quilt'`.
- Click (`resumeSession`): opens the editor with the CURRENT in-memory model (which was initialized from the autosave at construction) — `_openEditor(null, null)`; does not change `projName` (already initialized from autosave).

### Action row (flex wrap, gap 44px, align center)
**Left: photo card** (clickable, click = same as "Start from a photo"):
- Polaroid treatment: `transform:rotate(-2deg)`, background `#fffdf7`, border `1px solid #e7dcc4`, radius 4px, padding `13px 13px 9px`, `box-shadow:0 18px 38px var(--shadow)`; hover `rotate(0) scale(1.02)`.
- Content: procedurally rendered SVG of the Double Irish Chain sample "photo" (rendered with quilting texture + warm `#d99a4e` 10% overlay to look like a photo).
- Caption row: left `IMG_2847.jpeg` (italic serif 14px `#8a7a61`), right `sample photo` (12.5px `#b3a488`).

**Right column** (`flex:1 1 300px; max-width:430px`, column gap 13px, left-aligned):
- Paragraph: `Lay the quilt flat, take one straight-on shot, and drop it in. You get back a quilt you can repaint, resize and re-plan — with the fabric math done for you.` (16.5px, `--ink2`).
- Primary CTA: `Start from a photo` — `background:var(--accent); color:var(--accentInk); radius 12px; padding 16px 26px; font 600 18px; box-shadow 0 4px 12px`; hover `background:var(--accentB)`. Click: `setState({screen:'drop'})`.
- Secondary: `Open the demo quilt instead` — card-style bordered button (`1.5px solid var(--line2)`, radius 11, padding 12px 18px, font 600 15.5px). Click (`startDemo`): `_openEditor(_mkChain(false), 'Double Irish Chain')` — demo model: 45x55 grid, 1.5in cell, block 5, one 3.75in border, fabrics `Cream Background #f7f1e0` + `Light Blue Chain #a9c7dc`, source `'demo'`, no uncertainty flags.
- Tertiary link-button: `No photo handy? Start from a blank grid` — borderless, 14.5px, `--denim`, underline with `text-underline-offset:3px`. Click (`startBlank`): `_openEditor(_mkBlank(), 'My new quilt')` — blank model: 18x24 grid all fabric 0, 2.5in cell, one 2.5in border, fabrics `Cream Background #f7f1e0` + `Denim Blue #8ba8bf`, source `'blank'`, `photo:false`.
- Engine-size note: `Everything runs in your browser — the vision engine loads itself the first time, about 12 MB.` — 12.5px, `--faint`. (PARITY note context: loading copy must never say "download".)

`_openEditor(m, name)` (lines 1564-1570): if m given, install it, clear undo/redo stacks; if name given set projName; set `screen:'editor'`, `tab: vw<720 ? 'canvas' : 'fabrics'`, `zoom:'fit'`; refresh drafts; `_touch()` (so entering the editor immediately autosaves and flips the header dot through saving -> saved).

## 3. Open-project modal (`jsonOpen === true`)

Opened by header `Open` button from any screen. Markup lines 634-655.

### Structure
- Fixed full-viewport wrapper `z-index:60`; scrim `rgba(18,12,6,0.6)` — **click on scrim closes** (`jsonClose` = `setState({jsonOpen:false})`).
- Dialog: absolutely centered (`left/top 50%, translate(-50%,-50%)`), `width:min(460px, calc(100vw - 32px))`, `background:var(--card); border 1px solid var(--line); radius 18px; box-shadow 0 24px 60px rgba(0,0,0,.35); padding 24px`.
- Title row: H2 `Open a project` (serif 700 23px, `--denim`, flex:1) + close button `✕` (38x38, `--card2` bg, `--line` border, radius 9px, 16px text) = `jsonClose`.
- Body copy: `QREP projects are plain .json files — easy to email, back up, or share with a friend.` (14.5px, `--mut`).
- **Drop zone**: a `<label>` (column flex, centered, gap 8px) with `border:2.5px dashed var(--line2); radius 14px; background:var(--card2); padding 26px 16px; position:relative`; hover `border-color:var(--accent)`. Contents: 34x30 upload-arrow-into-tray SVG (`--mut`); line 1 `Drop a .json project here` (600 16.5px, `--ink2`); line 2 `or tap to browse` (13.5px, `--faint`); then an **invisible file input** `<input type="file" accept=".json,application/json">` absolutely covering the whole label (`inset:0; opacity:0; cursor:pointer`). So both click-anywhere-to-browse and native drag-drop-onto-input work through the one input; there are no separate onDrop/onDragOver handlers on this modal (unlike the photo dropzone screen). After each selection the handler sets `e.target.value = ''` so the same file can be re-chosen.
- Footer row (flex gap 10px, wrap, margin-top 14px), two equal-width (`flex:1`) buttons:
  - `Load the sample project` — solid card-bordered button (1.5px `--line2`, radius 10, padding 12px, 600 15px).
  - `Try a broken file` — dashed-bordered ghost button (`1.5px dashed var(--line2)`, `--mut` text); hover turns text+border `--accent`. Tooltip: `Shows the error toast`. (Mock-only affordance to demo the error path.)

### Behaviors (lines 2028-2053)
- **fileOpen** (file input change): read file as text with FileReader.
  - Parse JSON; require `obj.model` with truthy `cols`, `rows`, `cells`, `fabrics`, `bands`; else throw.
  - Success: close modal, `_openEditor(model, obj.name || 'Opened project')`, ok toast `Project opened — welcome back.`
  - Parse/validation failure: error toast, **exact copy**: `That file isn’t a QREP project — try the sample instead.` Modal stays open; nothing else changes.
  - FileReader onerror: error toast `Couldn’t read that file.`
- **loadSample**: close modal, `_openEditor(_mkChain(false), 'Sample project')`, ok toast `Sample project loaded.`
- **brokenDemo**: error toast only, **exact copy**: `That file isn’t a QREP project — it’s missing its grid. Nothing was changed.` Modal stays open.
- **Keyboard**: global keydown — `Escape` closes the modal (and the lightbox if open) (line 745). No focus trap, no autofocus, no Tab cycling in the mock.

## 4. Toast system (shared; required for modal errors and Save)

Single toast slot (state `toast = {msg, kind}`); each `_toast(msg, kind='ok')` replaces the current one and resets a 3600ms auto-dismiss timer. Render (lines 657-662, 2054-2056):
- Fixed `left:50%; bottom:26px; translateX(-50%)`, pill `border-radius:999px`, `padding 13px 24px`, 15.5px, `z-index:80`, `white-space:nowrap; max-width:92vw; overflow:hidden; text-overflow:ellipsis`, shadow `0 10px 26px rgba(30,18,6,.4)`, entry `qToast .28s ease`.
- Kind `ok`: glyph `✓`, `background:#43372a; color:#fbf4e4`. Kind `err`: glyph `⚠`, `background:#8c3f22; color:#fdf6e9`. Same colors in both themes (hardcoded).

## 5. Tooltip system (shared)

Elements carry `data-tip` + mouseenter/leave -> `tipOn/tipOff`. Suppressed when `vw < 720`. Rendered as fixed dark pill (`#2b2115` bg, `#f6ecd9` text, 13px, radius 8, padding 7px 12px, `z-index:90`, pointer-events none, nowrap, max-width 320px) positioned above the element's horizontal center (`x = rect center`, `y = rect.top - 9`, `translate(-50%,-100%)`).

## 6. State-transition summary (scoped areas)

- `screen`: `home` --Start from a photo / photo card--> `drop`; `home` --demo/blank/resume--> `editor`; any --logo click--> `home` (state preserved); modal `fileOpen` success or `loadSample` --> `editor`.
- `jsonOpen`: false --header Open--> true; true --scrim click / ✕ / Escape / successful file open / loadSample--> false. Error paths leave it true.
- `engine`: `boot` --1.5s after mount--> `ready`; `ready` --start analysis or export--> `busy`; `busy` --finish/cancel/export done--> `ready`. Chip text: `engine warming up` / `engine ready` / `engine busy`.
- `saveState`: `saved` --any mutation (`_touch`)--> `saving` --700ms debounce, localStorage write--> `saved`. Header dot sage/steady vs amber/pulsing; text `Autosaved` vs `Saving…`.
- `theme`: `light` <-> `dark` via toggle; persisted `qrep-theme`; body attribute drives all tokens.
- `visionDL`: false --6s idle timer OR completing the simulated fetch during analysis--> true (affects only the progress screen: shows `Vision engine ready — it loaded in the background.` instead of the first-time loading bar).

## 7. Exact copy inventory (scoped areas)

Header: `QREP` · `quilt reverse-engineering` · `My quilt project` (default name) · `Autosaved` · `Saving…` · `Open` · `Save` · `engine warming up` · `engine ready` · `engine busy`. Tooltips: `Back to the start screen` · `Project name — click to rename` · `Changes save to this device automatically` · `The Python engine runs in your browser — it boots in a few seconds on first load.` · `Switch to evening mode` · `Switch to daylight mode`.

Start screen: `QREP · quilt reverse-engineering` · `Turn a quilt photo into a pattern.` · `QREP finds the grid, matches the fabrics, and does the sizing and yardage math. Everything runs right here in your browser.` · `Continue where you left off — {name}` · `IMG_2847.jpeg` · `sample photo` · `Lay the quilt flat, take one straight-on shot, and drop it in. You get back a quilt you can repaint, resize and re-plan — with the fabric math done for you.` · `Start from a photo` · `Open the demo quilt instead` · `No photo handy? Start from a blank grid` · `Everything runs in your browser — the vision engine loads itself the first time, about 12 MB.`

Open modal: `Open a project` · `QREP projects are plain .json files — easy to email, back up, or share with a friend.` · `Drop a .json project here` · `or tap to browse` · `Load the sample project` · `Try a broken file` (tooltip `Shows the error toast`). Toasts: `Project opened — welcome back.` · `Sample project loaded.` · invalid file: `That file isn’t a QREP project — try the sample instead.` · broken-demo variant: `That file isn’t a QREP project — it’s missing its grid. Nothing was changed.` · unreadable file: `Couldn’t read that file.` Save toasts: `Project saved as {slug}.qrep.json` · `Save didn’t work — try again?`

Note: all dashes above are em dashes and the apostrophes are typographic (U+2019) in the source; preserve them verbatim, including the `…` ellipsis character in `Saving…`.


---

## SECTION: CANVAS VIEWER, RULERS, FABRIC PANEL

# QREP mock — Editor canvas area, extracted spec

Source: `C:\Users\Jake Mismas\QREP\docs\design\sprint-2\QREP.dc.html` (markup lines 240–514; logic in the inline `data-dc-script`, notably `_svgOut` ~line 877, `_ticks` ~line 962, pointer handlers ~1060–1257, `_rvEditor` ~1710–1786, `_rvPanels` ~1788+, `_rvShell` ~1571).

## 1. Core scale math (true-to-scale rendering)

- **1 inch = 96 CSS px at zoom 1.0.** Everywhere: `ppi = 96 * zoom` (line 1716). `zoom === 1` is labeled "actual size on most screens".
- **Zoom state** is either the string `'fit'` (default) or a number. Editor always opens with `zoom: 'fit'` (`_openEditor`, line 1567).
- **Fit formula** (line 1715): `ppi = max(0.7, min((cvW - 2*pad - 8) / W, (cvH - 2*pad - 8) / H))` where `pad = 16` (px padding around the quilt inside the scroll content), `W`/`H` are finished quilt inches, and `cvW`/`cvH` are the measured scroll-viewport size. Fit ppi floor is 0.7 px/in.
- **Quilt geometry in inches:** `W = cols*cell + 2*sum(band widths)`, `H = rows*cell + 2*sum(band widths)`. Demo model (Double Irish Chain): 45 × 55 cells at 1.5″, one 3.75″ border → **75″ × 90″ finished**.
- **SVG output** (`_svgOut`): svg width = `ceil(W*ppi + 2*x0)`, height = `ceil(H*ppi + 2*y0)` with `x0 = y0 = pad = 16`. All coords rounded to 2 decimals. Cells of the majority fabric are painted as one background rect; minority fabrics are compact path strings per fabric, each cell `M x y h w v w h -w z` with `w = cellPx + 0.3` (0.3px overdraw kills hairline seams). SVG results cached by `modelVersion|ppi|x0|y0|seamMode|flags`, cache capped at 24 entries.

## 2. Zoom controls

- **Toolbar**: `−` button (38×38, font-size 20, glyph `−`), a zoom label (`min-width:46px`, 14px 600, color `var(--mut)`, text `'Fit'` or `Math.round(zoom*100) + '%'`), `+` button (38×38, glyph `+`), and a **Fit** button (`height:38px; padding 0 12px`, label `Fit`). Tooltips: "Zoom out" / "Zoom in".
- **Button step ladder** (line 1727): `steps = [0.08, 0.12, 0.18, 0.25, 0.35, 0.5, 0.75, 1]` where `cur = ppi/96`.
  - zoomIn: first step `> cur*1.01`, else stays at max step (1.0 = 100%). **Buttons never exceed 100%.**
  - zoomOut: largest step `< cur*0.99`; if none below, sets `zoom:'fit'`.
  - zoomFit: `zoom = 'fit'`.
- **Pinch zoom** (two pointers, `_qDown/_qMove/_qUp`, lines 1169–1257):
  - Second finger cancels any in-progress paint/seam stroke (`_cancelStroke`) and starts pan/pinch. "Fingers from a pan/pinch never paint, seam or split."
  - Live: scales the content div with `transform: scale(f)` (transform-origin 0 0) and stretches its width/height by `f`; keeps midpoint anchored by adjusting `scrollLeft/Top` (`sc.scrollLeft = cx*f - (midX - boxL)`).
  - `f` clamped so final zoom stays in `[0.03, 2.2]`; min gesture distance 20px.
  - On release: if `|f - 1| > 0.02`, commit `zoom = clamp(zoom0 * f, 0.03, 2.2)` rounded to 3 decimals; restore scroll offsets after 60ms. **Pinch range (0.03–2.2, i.e. 3%–220%) exceeds the button ladder.**
- **Auto zoom-to on tap** (`_zoomTo`, line 1090): in paint/seam mode, if `ppi * cell < 14` px the tap zooms instead of painting: `zoom = clamp(22 / (96*cell), 0.1, 1)` (targets ~22px cells), rounded to 2 decimals; then centers scroll on the tapped point (60ms later). Toast copy: `Zoomed in — the squares were too small to touch. Tap again to edit; pan with two fingers.`
- **No wheel-zoom handler exists.** Mouse wheel just scrolls the native `overflow:auto` container.

## 3. Pan behavior

- Three canvas modes: **Paint / Move / Seams** (`mode`: `paint | pan | seam`). Cursor per mode (line 1746): paint → `crosshair`, seam → `cell`, pan → `grab`.
- **Move tool**: pointer drag sets `scrollLeft = startSL - dx`, `scrollTop = startST - dy` on the scroll container.
- **Two-finger pan** works in every mode (see pinch above; pure pan is pinch with f≈1).
- Scroll container: `position:absolute; left:41px; top:27px; right:0; bottom:0; overflow:auto`. Inside it a content div sized exactly `mq.w × mq.h` px (`contentStyle`, line 1775) holding the quilt SVG (`display:block; touch-action:none; user-select:none`).
- **Ruler sync on scroll** (line 1768): `onScroll` sets `topRuler.style.transform = translateX(-scrollLeft)` and `leftRuler.style.transform = translateY(-scrollTop)` directly on the ruler `<svg>` elements (no re-render).

## 4. Rulers (inch rulers, x and y)

Chrome geometry (markup lines 272–303):
- **Corner box**: absolute left 0/top 0, **41px wide × 27px tall**, bg `var(--card2)`, `border-right`/`border-bottom` 1px `var(--line)`, z-index 2, content: italic 12px serif `in`, color `var(--mut)`.
- **Top ruler**: absolute `left:41px; right:0; top:0; height:27px`, bg `var(--card2)`, border-bottom 1px `var(--line)`, `overflow:hidden`, z-index 1. Contains an SVG of width `mq.w` (full content width) × 27.
- **Left ruler**: absolute `left:0; top:27px; bottom:0; width:41px`, bg `var(--card2)`, border-right 1px `var(--line)`. SVG 41 × `mq.h`.

Tick generation (`_ticks(len, ppi, off, axis)`, lines 962–977; `off = pad = 16`):
- One tick per whole inch, `i = 0 .. floor(len)` at `p = off + i*ppi`.
- **Minor tick** (i not divisible by 5): x-axis path `M{p} 27v-6` (6px up from bottom edge); y-axis `M41 {p}h-6`.
- **Major tick** (every 5 inches, including 0): x-axis `M{p} 27v-11` (11px); y-axis `M41 {p}h-11`.
- **Numeric labels** on majors only (`0, 5, 10, …`), suppressed near the far end so they don't collide with the accent end label: label rendered only if `i === 0` or `(len - i)*ppi >= 26` (x-axis) / `>= 20` (y-axis).
- An extra major tick is always appended at the exact end position `off + len*ppi` (handles fractional widths like 82½).
- Label styling: x-axis `<text>` at `y=12`, `font:11.5px var(--sans)`, `fill:var(--mut)`, `text-anchor:middle`; y-axis at `x=27`, `y = p + 4`, `text-anchor:end`, same font/fill.
- **Accent end labels** (finished dimensions): x-axis text at `x = end, y = 12`, `font:700 12px var(--sans)`, `fill:var(--accent)`, anchor middle, text = `fmt(W)`; y-axis at `x=27, y = end+4`, anchor end, text = `fmt(H)`. `fmt` renders eighths as unicode fractions (⅛¼⅜½⅝¾⅞), e.g. `82½`. Demo shows `75` and `90`.
- Tick stroke colors: minor `stroke:var(--mut); stroke-width:1`; major `stroke:var(--ink2); stroke-width:1.6`. (Print sheet uses fixed hexes instead: minor `#8d7c60`, major `#5f5038`, labels `#6d5f49`, end labels `#a5502f`.)

## 5. Stage / canvas chrome

- Stage wrapper: `position:relative; background:var(--stage); border-radius:12px; box-shadow:inset 0 1px 8px var(--shadow); overflow:hidden; height:{{stageH}}`.
- **stageH** (line 1745): phone `max(360px, calc(100dvh - 340px))`; desktop `clamp(430px, calc(100vh - 330px), 860px)`.
- Quilt SVG group has `filter: drop-shadow(0 4px 12px var(--shadow))`.
- Binding outline: rect inset 1px, `stroke-width:2.5`, stroke = `_shade(fabrics[1].color, 0.72)` (fabric 2 darkened to 72%), fallback `#8c6f4e`.
- Seam overlay (`seamStyle`, line 1774): seam mode → `stroke:rgba(110,80,45,0.4); stroke-width:1.5`; otherwise `stroke:rgba(110,80,45,0.13); stroke-width:1`. Seams draw only when `cellPx >= 4.5`.
- Uncertain-cell hatch: path `fill:rgba(196,90,40,0.32); stroke:#d06a35; stroke-width:1` (shown when `showUnc` toggled; painting a cell deletes its `unc` flag).
- Canvas card (section wrapper): `flex:1 1 560px; min-width:0; background:var(--card); border:1px solid var(--line); border-radius:16px; box-shadow:0 2px 10px var(--shadow); padding:12px; display:flex; flex-direction:column; gap:10px`.

Theme tokens used by the canvas chrome (light / dark, body CSS vars lines 13–14):
- `--stage: #e9dfc9 / #181208` (canvas bed behind the quilt)
- `--card2: #faf5e8 / #382e1d` (ruler background)
- `--line: #e7dcc4 / #453a26` (ruler borders, dashed separators)
- `--mut: #8a7a61 / #b3a184` (minor ticks, labels, scale line pairs with `--faint`)
- `--ink2: #5d4f39 / #ddcfb0` (major ticks)
- `--accent: #a5502f / #d98a5e` (end labels, active states)
- `--faint: #a3937a / #93826a` (scale line text)
- `--card: #fffdf7 / #2e2517`, `--shadow: rgba(96,66,28,.12) / rgba(0,0,0,.45)`.

## 6. Copy under the canvas (exact strings)

Row: `display:flex; align-items:baseline; justify-content:space-between; padding:0 4px`.
- **Scale line** (left, 13.5px, `var(--faint)`), `scaleText` (line 1777):
  - Seam mode overrides: `Seams: drag to sew squares into one piece · tap a piece to split it · two fingers to pan`
  - Fit: `Fit — about 1:{N} of real size` with `N = max(1, round(96/ppi))`
  - Zoom exactly 1: `100% — actual size on most screens`
  - Other zooms: `{NN}% — about 1:{N} of real size`
- **Finished-size line** (right): `sizeText = fmt(W) + '″ × ' + fmt(H) + '″'` in `font:600 19px var(--serif); color:var(--ink)`, followed by ` finished` in `font:400 13.5px var(--sans); color:var(--faint)`. Demo: `75″ × 90″ finished`.

## 7. Toolbar (canvas header row)

Order, left to right: mode group (Paint / Move / Seams pill group in a `var(--card2)` container), divider, **fabric swatch buttons** (34×34, radius 9, `background:{color}`, inset shadow; active gets ring `0 0 0 2.5px var(--card), 0 0 0 5px var(--accent)`; clicking picks the fabric AND switches to paint mode; tooltip `{name} — paint with this`), divider, **Undo/Redo** (38×38 icon buttons, disabled = `opacity:0.35;cursor:default`; Ctrl/Cmd+Z, Ctrl+Y / Ctrl+Shift+Z; 60-entry undo stack), divider, zoom controls (section 2), flex spacer, optional **`▨ {N} uncertain`** pill toggle (only when `model.photo && uncCount > 0`; active = accent bg; tooltip `Squares the photo analysis wasn't sure about — painting one clears it`), optional polaroid **photo-compare** button (tooltip `Compare with your photo`, opens side-by-side lightbox; only when `model.photo`).
Mode button tooltips: Paint `Paint squares with the selected fabric`; Move `Drag to move around the quilt`; Seams `Drag to sew squares into one piece · tap a piece to split it`. Selecting Seams also toasts: `Seams: drag to sew squares together, tap a piece to split it.`

## 8. Fabrics side panel — read-only aspects

Per fabric row (markup 327–342, viewmodel `fabRows` line 1817):
- **Swatch**: 46×46, `border-radius:10px`, `background:{color}`, 1px `var(--line2)` border, `box-shadow:inset 0 -2px 5px rgba(0,0,0,0.07)` (hides an invisible `<input type=color>`; tooltip "Tap to recolor").
- **Name**: `font:600 16.5px var(--sans); color:var(--ink)`, rendered as `{name} ✎` (rename affordance).
- **Meta line**: `font-size:14px; color:var(--mut)`, text = `{HEX} · {countText}` where HEX = `color.toUpperCase()` and `countText = num(count) + ' squares' + (usedInBorders ? ' + borders' : '')`; counts use `toLocaleString('en-US')` (e.g. `#A9C7DC · 1,342 squares`). Border usage derived from `model.bands[].fid`.
- Rows separated by `border-bottom:1px dashed var(--line)`, padding `12px 2px`.
- Header: `Fabrics` (700 21px serif, `var(--denim)`), dashed rule spacer, pill badge `tap a swatch to recolor` (12.5px, `var(--pill)` bg, `var(--pillLn)` border, radius 999).
- Footer note: `Recoloring updates the quilt, yardage and pattern instantly. Pick a fabric here, then paint squares on the quilt.`
- (Editing affordances also present: `＋ Add a fabric` dashed button; add-fabric palette `['#c9b6d6','#b9c9a8','#dcb8ae','#d9b05e','#b98f7a','#8ba8bf']`; toast `New fabric added — it's now your paintbrush.`)
- Demo fabrics: `Cream Background` `#f7f1e0` (also the border fabric → "+ borders"), `Light Blue Chain` `#a9c7dc`.

## 9. Desktop layout and resizing

- Breakpoint: **`isDesk / !isPhone = vw >= 720`**.
- `<main>` (line 1578): `max-width:1420px; margin:0 auto`; padding desktop `20px 22px 44px`, phone-editor `12px 12px 96px` (room for bottom nav), other phone `16px 14px 44px`.
- Editor layout (line 1738): desktop `display:flex; gap:20px; align-items:flex-start` + fade-in; phone `display:block`.
  - Canvas section: `flex:1 1 560px; min-width:0`.
  - Side panel: `flex:0 0 376px; max-width:376px; display:flex; flex-direction:column; gap:14px`.
- **Desktop tabs** (side panel only, 3 tabs): `Fabrics`, `Sizing`, `Pattern` — segmented control in `var(--card2)` container, radius 12, padding 5px; active tab: `background:var(--card); border:1px solid var(--line2); color:var(--accent); box-shadow:0 2px 6px var(--shadow)`; inactive: transparent, `color:var(--mut)`. Canvas is always visible on desktop; if state tab is `canvas` on desktop it falls back to `fabrics` (line 1722).
- **Phone**: fixed bottom nav with 4 tabs — `Quilt` (canvas), `Fabrics`, `Sizing`, `Pattern` — only one region visible at a time. Active phone tab: `background:var(--card3); color:var(--accent)`.
- Default tab on entering editor: phone → `canvas`, desktop → `fabrics` (line 1567).
- **Canvas resize plumbing** (`_measure`, lines 734–743): on window `resize` (and 30/200ms after tab switches, 40/260ms after opening the editor) the scroll container's `getBoundingClientRect()` is stored as `cvW/cvH` state (only if > 60px each); fit zoom recomputes from those, so 'fit' tracks the live viewport. Initial state `cvW:900, cvH:560`.

## 10. Misc behaviors worth carrying over

- Paint drag interpolates between events with a Bresenham-ish `_walk` so fast strokes don't skip cells; painting batches repaints through a single `requestAnimationFrame`.
- Undo semantics: a stroke pushes one undo snapshot at pointer-down; if nothing changed, the snapshot is popped. Snapshots are deep JSON clones, capped at 60. Repeated same-tag mutations within 1200ms coalesce.
- Escape closes lightbox/modals; autosave to `localStorage['qrep-autosave']` debounced 700ms with `Autosaved` / `Saving…` header states.
- Seam-plan interplay: the seam overlay mode derives from the selected Pattern strategy — `{hist:'grid', strip:'strip', opt:'rect'}` (line 1718) — plus user `seamFix` overrides from the Seams tool.


---

## SECTION: PHONE LAYOUT, TOAST, TOOLTIP, THEME, KEYS

# QREP mock extraction notes

Source: `C:\Users\Jake Mismas\QREP\docs\design\sprint-2\QREP.dc.html` (2043 lines, ~154 KB). Line numbers below refer to that file. There is no CSS `@media (max-width: 720px)`; responsiveness is JS-driven off `state.vw` (window resize listener, `_measure`, line 734). The only media query is `@media print` (line 22). All copy strings below are verbatim from the file, including punctuation.

## (a) Phone layout (vw < 720)

### Breakpoint mechanics
- `isDesk = s.vw >= 720` (line 1572); `isPhone = s.vw < 720` (line 1711). Recomputed on every `resize` via `_measure` (lines 721, 734-743). Initial `vw: window.innerWidth || 1200` (line 694).
- `edPhone = screen === 'editor' && !isDesk` (line 1573). Main padding: phone editor `12px 12px 96px` (96px bottom clearance for the tab bar), desktop `20px 22px 44px`, phone non-editor `16px 14px 44px` (line 1578). Max-width 1420px, centered.

### Bottom tab bar (phone editor only)
- Rendered only when `phoneBar` is true, i.e. `screen === 'editor' && vw < 720` (lines 505-514, 1779).
- Container (line 506): `position:fixed; left:0; right:0; bottom:0; z-index:35; background:var(--card); border-top:1px solid var(--line); display:flex; padding:6px 6px calc(6px + env(safe-area-inset-bottom)); box-shadow:0 -4px 14px var(--shadow);` marked `data-noprint`.
- Four tabs, keys and labels (lines 1780-1783): `canvas` -> label **"Quilt"**, `fabrics` -> **"Fabrics"**, `sizing` -> **"Sizing"**, `pattern` -> **"Pattern"** (label is key capitalized except canvas).
- Each tab button: `flex:1; flex-direction:column; align-items:center; gap:3px; padding:8px 4px; border:none; border-radius:11px;` 22x22 SVG stroke icon (`stroke:currentColor; stroke-width:1.8; fill:none`) above an 11.5px/600 label (lines 508-511).
- Active state: `background:var(--card3); color:var(--accent)`. Inactive: transparent background, `color:var(--mut)` (line 1782). Active is keyed off raw `s.tab === k`.
- Icon path data (lines 1731-1736):
  - canvas: `M3.5 3.5h15v15h-15zM3.5 9h15M3.5 14h15M9 3.5v15M14 3.5v15` (grid)
  - fabrics: `M3.5 3.5h9v9h-9zM9.5 9.5h9v9h-9z` (two overlapping squares)
  - sizing: `M2.5 7.5h17v7h-17zM6 7.5v3.5M9.5 7.5v3.5M13 7.5v3.5M16.5 7.5v3.5` (ruler)
  - pattern: `M4.5 3h10l4 4v12h-14zM8 9.5h7M8 13h7M8 16.5h5` (document)
- Tap handler `setPhTab` calls `setTab(key)` which sets `s.tab` and re-measures at 30ms and 200ms (lines 1730, 1784).

### Full-width panels / what changes vs desktop
- Phone editor shows exactly one region at a time (lines 1722-1723, 1738-1742):
  - `showCanvas = !isPhone || s.tab === 'canvas'` -> canvas visible only on the Quilt tab.
  - `showSide = !isPhone || s.tab !== 'canvas'` -> on phone the side panel replaces the canvas for the other three tabs.
  - Editor layout: phone `display:block` (panels full width); desktop `display:flex; gap:20px` with side panel `flex:0 0 376px; max-width:376px`.
  - `deskTabs = !isPhone`: the in-panel segmented control (buttons "Fabrics" / "Sizing" / "Pattern", lines 313-318) renders on desktop only; on phone the bottom bar is the only tab UI.
  - Desktop has no "canvas" tab: `effTab = (!isPhone && tab === 'canvas') ? 'fabrics' : tab` (line 1722) coerces it, since desktop always shows the canvas alongside.
- Entering the editor picks the initial tab by width: `tab: vw < 720 ? 'canvas' : 'fabrics'`, `zoom: 'fit'` (`_openEditor`, line 1567). Default state is `tab: 'sizing'` (line 697) but `_openEditor` overrides it.
- Canvas stage height: phone `max(360px, calc(100dvh - 340px))` (note `dvh`); desktop `clamp(430px, calc(100vh - 330px), 860px)` (line 1745).
- Header condensation on phone (all via `sc-if isDesk`): hides the "quilt reverse-engineering" tagline (line 32), hides the project-name input entirely (lines 34-36), hides the "Autosaved"/"Saving…" text leaving only the colored dot (line 40), hides the engine pill text ("engine warming up" / "engine ready" / "engine busy") leaving only the spinner/dot (line 48). Open/Save buttons and theme toggle remain.
- Toolbar mode buttons Paint / Move / Seams show icon+label on desktop, icon-only on phone (`<sc-if isDesk><span>Paint</span></sc-if>`, lines 246-248).
- Tooltips are disabled on phone (see section c).

### Pinch zoom (two-finger, pointer events)
- The quilt SVG has `touch-action:none; user-select:none; -webkit-touch-callout:none` and onPointerDown/Move/Up/Cancel handlers (line 292). Not phone-gated; works wherever two pointers land.
- `_qDown` (lines 1169-1199): tracks pointers in a Map with pointer capture. When a **second finger** lands: cancels any in-progress paint/seam stroke (`_cancelStroke`, which also pops the speculative undo snapshot if nothing changed), and starts a combined two-finger pan + pinch, recording start distance `d0` (min 20px), `zoom0 = ppi/96`, the scroll-content anchor under the midpoint, and content element base size; sets `transformOrigin:'0 0'`.
- `_qMove` (lines 1200-1227): live pinch applies a CSS `scale(f)` transform plus width/height scaling to the content wrapper (cheap preview, no re-render), keeping the pinch midpoint stationary via scrollLeft/scrollTop. Scale factor clamped so the resulting zoom stays in **[0.03, 2.2]** (`f` clamped to `0.03/zoom0 .. 2.2/zoom0`).
- `_qUp` (lines 1228-1246): when fingers drop below 2, clears the CSS transform and, if scale changed by more than 2%, commits `zoom = round(zoom0 * f, 3)` (clamped 0.03-2.2) as real state, then restores scroll position after 60ms. Comment at line 1246: "fingers from a pan/pinch never paint, seam or split".
- One-finger behavior by mode: paint mode paints (with Bresenham-ish `_walk` fill between move samples), seam mode sews/splits, pan mode ("Move") drags scroll. Cursor: crosshair / cell / grab (line 1746).
- Button zoom steps (toolbar - / % / + / Fit): `[0.08, 0.12, 0.18, 0.25, 0.35, 0.5, 0.75, 1]`; zooming out below the lowest step returns to `'fit'` (lines 1727, 1758-1760). Zoom label: `'Fit'` or `'NN%'`.

### Auto-zoom-to-paint and its toast
- Trigger (line 1192, in `_qDown`): single pointer down while `mode === 'paint' || mode === 'seam'` and the on-screen cell size `geom.ppi * model.cell < 14` px. The tap does NOT paint; instead `_zoomTo(e)` runs and returns.
- `_zoomTo` (lines 1090-1105): computes target zoom `z = min(1, max(0.1, 22 / (96 * model.cell)))` (aims for ~22px cells, clamped 10%-100%), sets it, then after 60ms centers the scroll viewport on the tapped fraction of the quilt.
- Toast (line 1097, kind ok): **"Zoomed in — the squares were too small to touch. Tap again to edit; pan with two fingers."**
- Not phone-exclusive (no vw check) but in practice fires on small screens / fit zoom. Related status-bar copy under the canvas in seam mode (line 1777): **"Seams: drag to sew squares into one piece · tap a piece to split it · two fingers to pan"**.

## (b) Toast primitive

- Singleton. `_toast(msg, kind)` (lines 1335-1339): sets `state.toast = {msg, kind: kind || 'ok'}`, clears the previous timer, auto-dismisses after **3600 ms**. A new toast replaces the current one and resets the timer. No manual dismiss, no action button, no exit animation, no queue.
- Render (lines 657-661, 2054-2056): fixed, **bottom-center**: `position:fixed; left:50%; bottom:26px; transform:translateX(-50%)`. Pill: `border-radius:999px; padding:13px 24px; font-size:15.5px; display:flex; align-items:center; gap:10px; z-index:80; white-space:nowrap; max-width:92vw; overflow:hidden; text-overflow:ellipsis; box-shadow:0 10px 26px rgba(30,18,6,0.4)`. Marked `data-noprint`.
- Enter animation: `qToast .28s ease` = fade in + rise 10px (`from{opacity:0; transform:translate(-50%,10px)}`, line 18).
- Variants (2 only):
  - **ok** (default): background `#43372a`, text `#fbf4e4`, leading glyph `✓`.
  - **err**: background `#8c3f22`, text `#fdf6e9`, leading glyph `⚠`.
  - Colors are hardcoded, identical in light and dark themes. Glyph is a flex-none span before the message (lines 659-660, 2055).
- Complete toast copy catalog (verbatim, with trigger and kind):
  | Copy | Kind | Trigger | Line |
  |---|---|---|---|
  | "Zoomed in — the squares were too small to touch. Tap again to edit; pan with two fingers." | ok | auto-zoom-to-paint | 1097 |
  | "Copied! Paste it into notes, email, anywhere." | ok | Copy my settings success | 1488 |
  | "Could not copy — sorry!" | err | clipboard fallback failure | 1499 |
  | "Print dialog opened — your one-page plan is ready." | ok | Print export | 1512 |
  | "Saved — check your downloads folder." | ok | any file export success | 1518 |
  | "That export didn’t work — try again?" | err | file export failure | 1519 |
  | "Project saved as {base}.qrep.json" | ok | header Save success | 1588 |
  | "Save didn’t work — try again?" | err | header Save failure | 1588 |
  | "Seams: drag to sew squares together, tap a piece to split it." | ok | selecting Seams mode | 1749 |
  | "New fabric added — it’s now your paintbrush." | ok | Add a fabric | 1839 |
  | "Try inches like 75 or 75 1/2" | err | bad width input | 1866 |
  | "Try inches like 90 or 90 1/2" | err | bad height input | 1871 |
  | "Try a size like 1 1/2 or 2" | err | bad square-size input | 1876 |
  | "Locked — width and height scale together." | ok | lock toggled on | 1893 |
  | "Unlocked — each side moves by whole blocks." | ok | lock toggled off | 1893 |
  | "Try a width like 3 3/4" | err | bad border-width input | 1919 |
  | "New border added inside the others." | ok | add a border | 1925 |
  | "Seam tweaks reset for the new plan." | ok | changing strategy with manual seam fixes present | 1957 |
  | "Project opened — welcome back." | ok | valid .qrep.json opened | 2039 |
  | "That file isn’t a QREP project — try the sample instead." | err | invalid JSON file | 2041 |
  | "Couldn’t read that file." | err | FileReader error | 2044 |
  | "Sample project loaded." | ok | Load the sample project | 2051 |
  | "That file isn’t a QREP project — it’s missing its grid. Nothing was changed." | err | "Try a broken file" demo button | 2053 |
- Related non-toast confirmation: the "Copy my settings" button itself flips to **"Copied ✓"** on sage background for 2600 ms (lines 497, 1490, 1974-1976). Undo/redo produce no toast; their buttons dim to opacity 0.35 when their stack is empty (line 1726).

## (c) Tooltip primitive

- Trigger: any element carrying `data-tip="..."` plus `onMouseEnter={tipOn}` / `onMouseLeave={tipOff}`. Hover-only; no focus or touch trigger.
- **No delay**: `tipOn` shows immediately (lines 1602-1607). `tipOff` hides immediately (line 1607).
- **Desktop-only**: `tipOn` returns early when `this.state.vw < 720` (line 1603). Nothing else gates it, so tooltips simply never appear on phone widths.
- Positioning: fixed at `x = round(rect.left + rect.width/2)`, `y = round(rect.top - 9)` with `transform:translate(-50%,-100%)` -> centered above the trigger with a 9px gap. No arrow, no flip/collision logic (line 2059).
- Style (line 2059): `background:#2b2115; color:#f6ecd9; padding:7px 12px; border-radius:8px; font:13px var(--sans); z-index:90; pointer-events:none; white-space:nowrap; max-width:320px; box-shadow:0 6px 18px rgba(0,0,0,0.3)`. Hardcoded colors, same in both themes. No animation.
- Tooltip copy inventory (verbatim): "Back to the start screen" (logo), "Project name — click to rename", "Changes save to this device automatically" (autosave dot), engine pill: "The Python engine runs in your browser — it boots in a few seconds on first load." (line 1592), theme toggle: see (d), "Paint squares with the selected fabric", "Drag to move around the quilt", "Drag to sew squares into one piece · tap a piece to split it", fabric chips: "{name} — paint with this" (line 1751), "Undo", "Redo", "Zoom out", "Zoom in", "Squares the photo analysis wasn’t sure about — painting one clears it", "Compare with your photo", "Tap to enlarge" (results photo), "Tap to recolor" (fabric swatch), "Click to rename" (fabric name), "Shows the error toast" (broken-file demo), lock button tip is dynamic (`lockTitle`).
- Note: a handful of stepper buttons use native `title=` instead ("A quarter inch smaller/bigger/narrower/wider", "Remove this border", lines 370-425).

## (d) Theme toggle

- Header button, 40x40, `border-radius:9px`, `border:1.5px solid var(--line2)`, `background:var(--card)` (line 50).
- Icon (18x18, currentColor): **light theme shows a sun** (filled r=4 circle + 8 ray strokes, line 51); **dark theme shows a crescent moon** (filled path `M15 11.5A7 7 0 0 1 6.5 3 7 7 0 1 0 15 11.5z`, line 52). I.e., icon reflects the CURRENT theme, not the target.
- Tooltip copy (line 1594): light -> **"Switch to evening mode"**; dark -> **"Switch to daylight mode"**.
- Behavior (`toggleTheme`, lines 1595-1600): flips `state.theme`, sets `document.body.setAttribute('data-theme', t)` (all theming is CSS vars keyed off `body[data-theme]`), persists `localStorage.setItem('qrep-theme', t)` inside try/catch.
- Persistence/init (lines 685-686, 720): default `'light'`; on construct, reads `localStorage.getItem('qrep-theme')` and only the exact value `'dark'` switches the default; `componentDidMount` stamps `data-theme` on body. No `prefers-color-scheme` detection anywhere in the file.
- Separately persisted in localStorage: `qrep-autosave` (project autosave; validated shape `r.model.cols/cells/fabrics` before offering resume, lines 687-690, 1013).

## (e) Keyboard shortcuts

- Global `keydown` listener on window, bound for the app's lifetime (lines 722, 744-751). Full handler:
  - **Escape**: closes the photo lightbox (`lb: null`) and the Open-project modal (`jsonOpen: false`), then returns. Works on every screen. No guard against focused inputs.
  - **Ctrl+Z / Cmd+Z** (no shift): `preventDefault()` then `_undo()` — only when `state.screen === 'editor'`.
  - **Ctrl+Y / Cmd+Y** or **Ctrl+Shift+Z / Cmd+Shift+Z**: `preventDefault()` then `_redo()` — editor only.
  - Key match is `e.key.toLowerCase()`; both `ctrlKey` and `metaKey` accepted.
- Undo/redo semantics (lines 981-990): snapshot stacks `_undoS`/`_redoS`; `_undo`/`_redo` no-op silently when empty (no toast). Paint and seam strokes push one undo snapshot per stroke on pointer-down; a stroke that changes nothing pops it back off. Undo stacks reset on new analysis/open (lines 1053, 1565). Applying a snapshot refreshes drafts and touches autosave (line 991).
- Also keyboard-adjacent: `enterKey` handler blurs the field on Enter to commit sizing/name inputs (line 1608). No other shortcuts exist (no key for tabs, zoom, or modes).

## Misc cross-cutting constants worth keeping
- Breakpoint: single, **720px**, JS-evaluated (no CSS media query for layout).
- Z-index ladder: header 30, phone tab bar 35, toast 80, tooltip 90 (lightbox/modals sit between).
- Animations: `qToast .28s ease` (toast in), `qFade` (screen transitions .3-.4s), `qPulse` (saving dot / busy dot), `qSpin` (engine boot spinner).
- Autosave indicator: dot sage when `saveState === 'saved'` ("Autosaved"), amber pulsing when saving ("Saving…") (lines 1581-1582); text hidden on phone.
