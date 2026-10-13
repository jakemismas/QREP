# QREP web app

The QREP web app turns a quilt photo into a pattern in the browser. It is a
React and TypeScript app built with Vite. The qrep Python engine runs in a web
worker on Pyodide, from a wheel built out of this repo's `qrep/` sources, so
the photo never leaves the device. The live site is
https://jakemismas.github.io/QREP/.

## Set up

You need Node 24 and Python 3.13 (the versions CI uses), and the repo venv
from the root README (`.venv/Scripts/python -m pip install -e ".[dev]" -c constraints.txt`).
Run these from `web/`:

```bash
npm ci
node scripts/vendor.mjs   # the pinned Pyodide runtime and its wheels, into public/
node scripts/wheel.mjs    # the qrep wheel, into public/wheels/
npx playwright install chromium   # the browser the end-to-end specs drive
```

`vendor.mjs` downloads and checks the files `vendor.lock.json` pins; rerun it
when that file changes. `wheel.mjs` uses the repo venv's
`.venv/Scripts/python.exe` when it exists and plain `python` otherwise; set
`QREP_PYTHON` to pick another interpreter. Rerun it after every change under
`qrep/` or to `pyproject.toml`.

## Build and run

```bash
npm run dev       # dev server with hot reload
npm run build     # type check and production build into dist/
npm run preview   # serve dist/
```

The wheel carries a stamp of the sources it was built from
(`public/wheels/qrep-source-hash.json`). `npm run build` runs
`scripts/wheel-hash.mjs` first, as its prebuild step, and refuses to build
when the stamp no longer matches `qrep/` and `pyproject.toml`, so a stale
engine never ships. The Pyodide test run checks the same stamp, and the
Playwright run checks the copy in `dist/wheels/` that the preview serves. When
a check fails, rerun `node scripts/wheel.mjs`, then `npm run build` before
Playwright.

## Test

```bash
npx tsc -b                     # types, unit tests and e2e specs included
npm run lint                   # oxlint; errors fail
npm run build                  # before vitest: compose-site.test.ts reads dist/
npm test -- --run              # vitest
npx playwright test            # end to end, against a preview of dist/
node scripts/pytest-pyodide.mjs   # the whole pytest suite under Pyodide
```

Playwright starts its own preview server. A sprint worktree gets its own port:
`scripts/worker_bootstrap.sh` writes `QREP_E2E_PORT` to `.qrep-worker.env` at
the repo root, and `playwright.config.ts` reads it from there (an exported
`QREP_E2E_PORT` wins). With a worker port, Playwright never reuses a server
that is already listening, because that server may be serving another
checkout's build. Without one, it takes port 4173 and fails if something
already holds it; set `QREP_E2E_REUSE=1` to reuse a server you started
yourself (never in CI). `SPIKE_BASE_URL` points the specs at a deployed site
instead.

Playwright runs headless. Specs that check layout or touch carry the `@phone`
tag. A screen a change adds or visibly changes passes
`expectNoHorizontalOverflow` (`e2e/helpers/layout.ts`) at 390 x 844 and
1440 x 900 in that change's own specs; a change that only moves code keeps
`e2e/layout.spec.ts` green. The editor is checked at 1440 x 900 only until
C6a removes it, because its header overflows at 390 px (web-02).

## CSS convention

- Each component imports its own stylesheet, a `.css` file next to its
  `.tsx`. Never inject a style string from a component: an injected sheet
  styles its classes only while its component is mounted (web-03).
- A class has one home. A component's own rules live in its stylesheet; rules
  that several files in a folder share live in that folder's shared sheet,
  as `src/shell/photo/shared.css` does for the photo flow. Each component
  imports the shared sheet before its own, so a component rule wins a tie
  with a shared one. To adjust a shared class in one component, lead the
  selector with that component's own class (`.pf-rt .pf-btn--secondary`).
  `src/css-collisions.test.ts` fails when two component stylesheets, or a
  component stylesheet and `index.css` or `ui/tokens.css`, lead a selector
  with the same class.
- New rules take colors, fonts and shadows from the `var(--*)` tokens in
  `src/ui/tokens.css`, which theme light and dark. A few `rgba()` tints in
  the photo-flow sheets predate this rule and moved unchanged.
- `.btn`, `.btn--primary`, `.btn--secondary` and `.btn--link` in
  `src/index.css` are the one button set. New UI uses them instead of a
  component-specific button class.
