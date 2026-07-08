# QREP Web Design Doc (Sprint 2)

## What this is

Design decisions for QREP Web, the sprint 2 build. This document is binding
alongside qrep-design-doc.md; where the two conflict, this one wins for
everything the Amendments section names, and the v1 doc wins elsewhere. Work
is tracked as GitHub Issues: parent #39, ordered slices S0-S7 (#40-#47). The
architecture was pressure-tested by a four-lens adversarial council on
2026-07-08; the decision record is the first comment on #39, and every major
finding is folded into the slice acceptance criteria.

## Core thesis

Sprint 1 proved the engine: a tested Python library whose golden files,
integer-eighths math, and CV round-trip harness are the project's core asset.
Sprint 2 changes the product surface, not the engine. The same wheel that
passes the test suite in CI runs unchanged in the user's browser through
Pyodide; the web UI is a client of the library, never a reimplementation of
it. Users get a link instead of a pip install. There is no backend: with no
accounts and no server-side storage, a server would have nothing to do.

## Architecture

- Static site on GitHub Pages, built from `web/` (Vite + React + TypeScript).
- The qrep wheel plus a vendored, pinned Pyodide runtime and the exact wheel
  closure (numpy, opencv-python from the Pyodide distribution, Pillow,
  pydantic, pydantic_core, reportlab 5.x pure-Python, svgwrite) ship inside
  the Pages artifact. No floating CDN references anywhere; opencv has been
  dropped from and re-added to the Pyodide distribution before, and a
  self-hosted pin is immune to that. S0 records the exact Pyodide version and
  every wheel filename in this section when it lands.

  S0 record (2026-07-08, issue #40; machine-readable copy with sha256 digests
  in web/vendor.lock.json, enforced by web/scripts/vendor.mjs at build time):
  - Pyodide 0.28.3 (Python 3.13.2, abi_version 2025_0, platform
    emscripten_4_0_9). Core files from npm pyodide@0.28.3: pyodide.mjs,
    pyodide.js, pyodide.asm.js, pyodide.asm.wasm, python_stdlib.zip,
    pyodide-lock.json.
  - Distribution wheels (Pyodide 0.28.3 CDN, vendored next to
    pyodide-lock.json): numpy-2.2.5-cp313-cp313-pyodide_2025_0_wasm32.whl,
    opencv_python-4.11.0.86-cp313-cp313-pyodide_2025_0_wasm32.whl,
    pillow-11.3.0-cp313-cp313-pyodide_2025_0_wasm32.whl,
    pydantic-2.10.6-py3-none-any.whl,
    pydantic_core-2.27.2-cp313-cp313-pyodide_2025_0_wasm32.whl,
    typing_extensions-4.14.1-py3-none-any.whl,
    annotated_types-0.7.0-py3-none-any.whl,
    charset_normalizer-3.4.2-py3-none-any.whl (reportlab 5.x dependency),
    micropip-0.10.1-py3-none-any.whl.
  - PyPI pure-Python wheels (vendored under wheels/):
    reportlab-5.0.0-py3-none-any.whl, svgwrite-1.4.3-py3-none-any.whl.
  - qrep-0.1.0-py3-none-any.whl built from the repo at site build time,
    installed with micropip deps=False.
  - Versioning note: Pyodide moved to CPython-tracking version numbers after
    0.29.x (0.28.3 -> 0.29.4 -> 314.x). 0.28.3 is the last release of the
    measured 0.28 line and matches the native 3.13 CI matrix; upgrades stay
    deliberate, tested acts per the risk register.
- Pyodide runs in a Web Worker. A typed RPC layer (request id, method, JSON
  payload, transferables for bytes) is the only path between UI and engine.
  The worker is disposable: every bridge call is stateless (the model JSON
  travels with the call), so terminating a stuck worker and re-booting is
  always safe. GitHub Pages cannot set COOP/COEP headers, so there is no
  SharedArrayBuffer and no Python interrupt; cancel = terminate + re-boot,
  and the UI treats it that way.
- `qrep/bridge.py` is the engine-side seam: pure functions, JSON strings and
  bytes in and out, no typer import. Surface: validate, plan, export_cutlist_md,
  export_cutlist_csv, export_yardage, export_svg, export_pdf, render, reverse,
  compare, resize_locked, resize_unlocked. Every function returns a typed
  envelope: `{"ok": true, "result": ...}` or `{"ok": false, "error": {"kind":
  "schema|validation|value|internal|not_implemented", "message": ...}}`. No
  stringified tracebacks reach the UI.
- Uploaded images are downscaled in JS (canvas, longest side capped at
  2000 px) before bytes are staged onto Emscripten MEMFS for the pipeline. A
  12MP original would peak at 400-600 MB of float32 intermediates; the cap
  removes the tablet OOM risk.
- Photo reverse is reachable through exactly one async contract: image bytes
  in, model JSON with confidences out. That seam is the designed escape
  hatch: if wasm CV proves unusable on target devices, a serverless endpoint
  swaps in behind it as a one-function change. Build nothing server-side now.

## Payload and loading contract

Measured against the live Pyodide CDN (Brotli transfer sizes, 0.28.x):
core runtime ~5.3 MB, engine wheels (numpy, pydantic, pydantic_core,
svgwrite) ~4.9 MB, export extras (reportlab, Pillow) ~3.1 MB, opencv
~11.7 MB. Staged loading is a product rule:

- App shell (pure JS) is interactive immediately; the engine boots in the
  worker behind a status chip (booting with progress, ready, busy, failed
  with retry). Expect ~10-13 MB and a few seconds to Python-ready.
- The vision wheel (~12 MB) loads only on first photo use, behind a staged
  progress UI ("first time only"), with retry on failure. Editor-and-export
  users never pay for it. Cumulative with vision: ~25 MB, browser-cached
  afterward.
- No per-gesture Python calls, ever. Painting, hover, and slider previews
  are pure JS; Python runs on discrete actions (load, validate, replan,
  resize commit, export, reverse). A full replan lands in the 100 ms - 1 s
  band in wasm and gets an explicit action with a busy state.
- Site assets and the qrep wheel carry versioned/hashed filenames so a
  cached shell can never install a mismatched wheel.

## Determinism and goldens on the web

- Byte-parity between wasm and native is asserted for integer-domain exports
  only: cut list (md, csv), yardage, SVG (its floats pass through one
  formatter on integer-eighths inputs). The e2e proof is a byte-compare of
  browser-generated bytes against the canonical frozen files under
  tests/golden/, read at test runtime. No copies of goldens under web/.
- CV output gets no cross-runtime byte promises: cv2.kmeans float
  accumulation order may differ between wasm and native SIMD. CV results are
  asserted semantically (dims, accuracy, palette mapping, confidence
  presence), exactly as the S7 (sprint 1) thresholds already do.
- Playwright snapshot APIs (toMatchSnapshot, toHaveScreenshot) are banned
  for golden assertions: they auto-write on first run, which is an implicit
  bless. The v1 bless protocol stands unchanged.
- CI runs the full existing pytest suite under the pinned Pyodide runtime
  (Node headless) in addition to native 3.12/3.13. A wasm-only failure is a
  real cross-runtime divergence and takes the KNOWN_ISSUES/xfail path after
  3 documented attempts; thresholds and goldens are never edited to pass.

## Persistence policy (file-first)

Safari ITP deletes ALL script-writable storage (localStorage, IndexedDB,
Cache Storage, service worker registrations) after 7 days without visiting
the site. The audience is iPad-heavy and quilting is episodic, so browser
storage is structurally untrustworthy here:

- The durable save is the downloaded project JSON. The UI treats it that
  way: prominent save action, beforeunload guard when edits are newer than
  the last file save.
- localStorage is a convenience autosave only, offered back on return
  ("resume last session", with age shown). UI copy never promises browser
  storage is permanent. An "Add to Home Screen" tip for iPad users is
  allowed (home-screen web apps get a separate eviction counter).
- Autosaves and uploads carry schema_version "1"; anything else is rejected
  with a clear message, never silently dropped.
- Photos and designs never leave the device; that privacy line is part of
  the product's identity and appears in the README and UI copy.

## UI reference (binding)

The Claude Design mockups are committed at docs/design/sprint-2/
(QREP.dc.html for screens and behavior, QREP Design System.dc.html for
tokens and components). They are the look-and-behavior reference for every
UI slice. docs/design/sprint-2/PARITY.md is the binding annex mapping each
mock screen to its slice and recording every deliberate deviation; the two
load-bearing ones: all numbers come from the engine even where the mock
computes them in JS, and the Seams tool is a preview layer whose overrides
live in the project-file wrapper, never in the engine model, and never
change exports in this sprint. The project file is a wrapper
(`{app, version, name, model, ui}`) around the canonical engine model JSON;
Open also accepts a bare engine model. The mock's phone layout (<720px,
bottom tabs) is in scope for layout; phone CV performance stays best-effort.

## Test-driven protocol (binding)

Every slice works red-first: for each acceptance criterion, the test exists
and fails before the implementing code lands, and both land in the same PR.
Expected values flow one way, hand computation (in comments or fixtures) to
assertion, per the repo non-negotiables; never observed output to assertion.
Layers: pytest for bridge and engine behavior (including the new resize
semantics with hand-computed literals); vitest for UI logic (fraction
parsing/formatting parity fixtures shared with Python, undo history, dirty
tracking, RPC correlation, seam-override edge maps); Playwright for user
flows against the built site. UI parity items test the behavior contract in
PARITY.md, not pixel styling. PRs state which tests were written first; a
criterion without a test is not done.

## Sizing math ownership

Sprint 1 already documented a Python-vs-JS divergence in the sizing math
(round-half-to-even vs Math.round, see qrep/viewer/sizing.py). The rule for
sprint 2: Python is authoritative. The bridge exposes resize_locked and
resize_unlocked; every UI commit adopts the bridge's returned model. Per the
mock (PARITY.md item 4), locked resize also scales border-band widths by
the cell factor (eighth-rounded, quarter-inch floor) with the mock's clamps;
these are NEW bridge functions with fresh hand-computed tests, and sprint
1's sizing helper and its tests stay untouched. A JS preview mirror for live slider feedback is permitted only with a
parity test asserting the exact literals of the Python sizing unit tests; if
parity cannot be held, the mirror is dropped in favor of a debounced Python
call.

## Packaging changes

- pyproject: `opencv-python-headless; sys_platform != 'emscripten'` (the
  Pyodide distribution supplies opencv-python in the browser; naive micropip
  resolution of the headless pin fails, found independently by two council
  lenses). The browser install flow uses deps=False plus explicit loads.
- scikit-image is removed from dependencies: nothing in qrep/ or tests/
  imports it (grep-verified 2026-07-08). This supersedes the v1 stack line
  that named it; if a future vision slice genuinely needs it, it returns as
  a normal dependency change with its wasm cost (it drags scipy, roughly
  20-30 MB) weighed explicitly.
- typer and click remain dependencies (pure Python, harmless in the browser
  payload); the bridge simply never imports them.

## Testing strategy

- The native pytest suite is untouched and still gates every slice; ruff
  likewise. No golden file, threshold, or assertion is weakened anywhere in
  the sprint (v1 non-negotiables apply unchanged).
- pytest-under-pinned-Pyodide CI job from S1 onward: the drift-proof check
  that the shipped engine is the tested engine.
- vitest for frontend logic (RPC correlation, undo/redo history, dirty
  tracking, fraction formatting parity fixtures).
- One Playwright e2e job in CI: boot the deployed-artifact site headlessly,
  load the demo fixture, and per slice: validate rendering and rulers (S2),
  edit and persistence round trips (S3), resize parity (S4), export
  byte-compares against canonical goldens (S5), and the L0 reverse round
  trip (S6). PDF bytes are structure-checked native-side with pypdf, never
  byte-compared.
- S6 additionally records one manual iPad Safari smoke run of the photo flow
  (device model and timings in the issue), since no published Pyodide
  benchmarks exist for mid-tier iPads.

## Slices (one slice = one GitHub issue, strictly in order)

- S0 (#40) feasibility spike + scaffold + CI + Pages deploy. THE GATE: full
  closure installs in wasm; cut-list CSV byte-equal to the frozen golden
  in-browser; the booklet PDF renders and passes pypdf checks; reverse()
  completes on an L0 render with dims recovered and timing recorded. Failure
  after 3 documented APPROACH FAILED attempts halts the sprint and re-opens
  the decision toward the hybrid fallback.
- S1 (#41) qrep/bridge.py + error envelopes + resize entry points +
  packaging changes + pytest-under-Pyodide CI job.
- S2 (#42) app shell, worker RPC, engine status chip, first-run screen,
  read-only true-to-scale viewer with rulers, fabric summary.
- S3 (#43) editing core: cell paint, palette CRUD, undo/redo, file-first
  persistence, autosave, schema_version guard.
- S4 (#44) sizing + borders, Python-authoritative, presets, proportion
  lock, achieved-vs-requested; the app replaces the standalone viewer as
  the product surface (qrep view and its tests stay).
- S5 (#45) strategy cards + metrics, yardage table, all export downloads,
  golden byte-compares in e2e.
- S6 (#46) photo reverse flow: downscale, staged vision load, confidence
  UI, corner escape hatch, round-trip demo panel, iPad smoke, timing
  numbers.
- S7 (#47) web-first README, REPORT.md sprint 2 numbers, KNOWN_ISSUES
  sweep, CLAUDE.md governing-docs update, Pages root serves the app,
  release v0.2.0, close #22.

Each slice gates on green: ruff, native pytest, pytest-under-Pyodide (from
S1), vitest + Playwright e2e (from S2), CI green on main for the previous
slice. Slices land as branch + PR with Fixes #N per repo policy.

## Amendments to the v1 design doc

This section is the exhaustive list of v1 statements sprint 2 supersedes.

1. "Interfaces in v1" / build-contract rule 4 ("No web app, no server"):
   superseded. The web app is the product surface. The one-file sizing
   viewer stops being the only GUI; it remains shipped and tested.
2. Stack list: scikit-image removed (unused). Added for the web build:
   vendored pinned Pyodide runtime, Vite + React + TypeScript in web/.
   The opencv dependency gains an Emscripten environment marker.
3. CLI signatures: unchanged and still pinned. The CLI is demoted from
   product to developer/test surface; nothing about it is deleted or
   weakened, and test_cli.py / test_viewer.py stay as-is.
4. Determinism rules: extended, not changed, by the web goldens policy
   above (integer-domain byte parity only; CV semantic assertions; snapshot
   APIs banned).
5. Repo layout: adds web/ (frontend) and qrep/bridge.py. The two governing
   docs at root are joined by this one under docs/sprint-2/.

Everything else in qrep-design-doc.md (units, model, fixture geometry,
construction engine, math defaults, renderer, CV formulas, diagram
conventions) stands unchanged and binding.

## Known risks

- reportlab under Pyodide has no public end-to-end demonstration. S0 retires
  this first; the fallback if it genuinely fails is a serverless PDF
  endpoint behind the same bridge seam (and only then).
- cv2.kmeans wasm-vs-native divergence could surface as a wasm-only test
  failure in the pytest-under-Pyodide job. That is information, not an
  emergency: KNOWN_ISSUES protocol, never threshold edits.
- Older iPads are the memory floor. Downscaling plus the S6 device smoke
  keeps this measured instead of assumed; the hybrid seam is the designed
  exit if measurement says no.
- Pyodide version churn (their lockfile ecosystem has broken pydantic
  before). The vendored pin plus the Pyodide CI job make upgrades a
  deliberate, tested act.
- The editor invites scope creep harder than the viewer did. The slice
  non-goals are the fence: no block-level tools, no quilting-layer editing,
  no fabric libraries, no sharing in this sprint.
