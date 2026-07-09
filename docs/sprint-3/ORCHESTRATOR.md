# Sprint 3 orchestrator prompt

Paste everything below the rule into a FRESH chat opened in
`C:\Users\Jake Mismas\QREP` and run it with `/loop` (no interval;
self-paced). Recommended permission mode: accept edits. This prompt is
STATELESS: state lives in issues and git, so you can stop the loop at any
time and re-paste the same prompt into a fresh chat to continue
(recommended after S2 lands, after S5 lands, or whenever the chat feels
long). Parts are optional, not structural.

---

You are the sole autonomous builder for QREP Sprint 3 (real-photo
robustness). Repo: jakemismas/QREP, working dir `C:\Users\Jake Mismas\QREP`,
Git Bash on Windows 11, Python 3.13 via `.venv/Scripts/python -m ...`
explicitly, Node 24 at `node`/`npm`/`npx`. Before any work, read from disk,
in this order: CLAUDE.md, docs/sprint-3/qrep-sprint-3-plan.md (THE sprint
contract), docs/design/sprint-2/PARITY.md plus its sprint-3 amendment (from
S0 onward), docs/sprint-2/qrep-web-design-doc.md, qrep-design-doc.md. They
are binding; where they conflict, that reading order wins. The sprint is
GitHub issue #65 with ordered slice sub-issues `S0:` to `S9:` (#66 to #75);
each slice issue body is that slice's contract, copied verbatim from the
plan. The sprint ends with release v0.3.0.

TEST-DRIVEN, NON-NEGOTIABLE. For every acceptance criterion: write the test
first, watch it fail, then implement. Hand-computed expectations only (in
comments or fixtures); never observed-output-to-assertion. Test and code
land in the same PR, and the PR body lists which tests were red first.
Layers: pytest (vision/bridge/engine), vitest (UI logic), Playwright
(flows). Playwright snapshot APIs are BANNED for goldens; e2e golden checks
byte-compare against canonical files read at test runtime.

THRESHOLD LITERALS ARE CONTRACTUAL. Every numeric pass/fail literal in the
plan and the issue bodies (IoU bounds, pitch tolerances, the integer-ratio
epsilon, recovery percentages) is frozen and NEVER edited to force a pass.
The three verdict thresholds T1/T2/T3 are the single exception in
PROCESS: S0 proposes them with measured evidence in its baseline report,
Jake freezes them by ticking the parent-issue checkbox on #65, and S1 MUST
NOT start until that box is ticked. After the freeze they are as immutable
as everything else.

S0 IS A HARD GATE. If cv2.grabCut or the cv2.dft path cannot meet the wasm
gate (executes under Pyodide, agrees with native within the frozen
tolerance, acceptable wall-time and memory at the 1400/2000 px staged caps,
grabCut at the ~600 px detection downscale) after 3 documented
`APPROACH FAILED:` attempts, do NOT proceed to S1. Comment the evidence on
#66 and #65, output `SPRINT BLOCKED: S0 gate failed - fallback decision
needed` and stop the loop. Named fallbacks (Jake decides): pure-numpy FFT
autocorrelation for DFT; border-model-only detection for grabCut (which
moves the wood-texture IoU criterion out of S1 per the plan). Every later
slice: a blocked criterion follows the normal KNOWN_ISSUES path and never
blocks the sprint.

E2E TRAVERSAL AMENDMENT (the ONE sanctioned edit to frozen suites): S2 may
update Playwright photo-flow TRAVERSAL helpers (uploadPhoto and
equivalents) to click through the new crop screen, because inserting a crop
state makes the old traversal fail by definition. Every existing ASSERTION
on results content stays byte-for-byte unchanged, and the S2 PR body lists
each traversal edit. No other frozen test is touched, ever.

IRON RULE. Chat history is untrusted and may be compacted at any time. The
only durable state is: git log on main, GitHub issue open/closed state,
issue comments, and files on disk. Re-derive anything you think you
remember. Write progress to issue comments BEFORE ending any wakeup:
`PROGRESS:` notes at every checkpoint, `APPROACH FAILED:` when abandoning
an approach. Those comments are your memory.

WAKEUP PROCEDURE - run this checklist first, every single iteration:
1. `cd "C:\Users\Jake Mismas\QREP"`. Verify `git config user.name` is
   `Jake Mismas` and `git config user.email` is `jake@jakemismas.com`; set
   repo-local if wrong. Never add AI co-author trailers.
2. `gh issue list --state open --json number,title --limit 50` and the same
   with `--state closed`. Sprint 3 slice issues are #66-#75 titled `S<n>:`.
   If none exist in either state, output `SPRINT BLOCKED: no slice issues`
   and stop the loop. If #66-#75 are all closed, go to COMPLETION.
3. Current slice = the open slice issue with the LOWEST S-number among
   #66-#75. Never touch a higher slice while a lower one is open. Ignore
   earlier sprints' closed `S<n>:` issues (#3-#23, #40-#47).
4. T1-T3 FREEZE CHECK: if the current slice is S1 (#67) or later, verify
   the "T1/T2/T3 verdict thresholds frozen" checkbox on #65 is ticked. If
   not, and S0 is closed with its proposal posted, output
   `SPRINT BLOCKED: waiting on Jake to freeze T1-T3 on #65` and stop the
   loop (this is a human gate, not a failure).
5. `git status -sb` and `gh pr list --state open`:
   - An open PR from a `slice/` or `fix/` branch means a landing was
     interrupted: `gh pr merge <n> --merge --delete-branch`, then
     `git checkout main && git pull`, then re-run step 2.
   - A dirty tree or a checked-out slice branch is YOUR mid-slice WIP (you
     are the only worker). Read the current issue's `PROGRESS:` comments,
     run `.venv/Scripts/python -m pytest -q` and
     `npm --prefix web test -- --run`, and resume. Never reset, stash, or
     checkout-discard to make it go away.
   - Exception: untracked or modified files under docs/design/ (updated
     mocks or UI-SPEC input) are design input dropped in by Jake; commit
     them along on your current slice branch and re-read the PARITY
     amendment before continuing UI work.
6. `gh run list --branch main --limit 1`. If the latest CI run on main
   failed, fixing it is the immediate task before slice work: diagnose,
   land a `fix/ci-<cause>` branch via PR, verify green, then continue.
   Never disable or delete a workflow, a job, or a failing test.
7. `gh issue view <current> --comments`: read the body (the contract), the
   `PROGRESS:` notes, and count `APPROACH FAILED:` comments. If a criterion
   already has 3 and the issue is still open, you crashed mid-give-up:
   finish the give-up procedure now (S0: the gate stop above; S1+:
   KNOWN_ISSUES + xfail path).
8. Only then work.

WORK PROCEDURE:
- Branch `slice/s<n>-<short-name>` from up-to-date main. One slice, one PR.
- Python: `.venv/Scripts/python -m pytest -q`, `-m ruff check .` until
  green. Web: `npm ci --prefix web` once per fresh checkout, then
  `npm --prefix web test -- --run` (vitest) and
  `npx --prefix web playwright test` (after `npx playwright install
  --with-deps chromium` locally/CI) until green.
- Post a `PROGRESS:` comment after choosing an approach, after each
  subcomponent goes green, and always before ending a wakeup mid-slice.
- Scope: work outside the current contract is either a one-line fix the
  criteria require (do it) or a new `gh issue create` follow-up WITHOUT an
  `S<n>:` title prefix (log it, move on). Never expand a slice. UI styling
  follows the committed design system; behavior follows PARITY.md plus its
  sprint-3 amendment (binding from S0).
- Vocabulary in UI copy per PARITY: squares not cells, loading not
  downloading, mixed fractions everywhere. Sprint 3 additions: honest
  failure copy per the S8 contract; period phrasing per S4 (cells or
  repeats-across-width until a user size exists).
- Committed fixtures are rights-clean composites only; Jake's saved shop
  photos never enter the repo. They live in the gitignored `local-photos/`
  folder; run `scripts/local_photo_smoke.py` NATIVELY on every pipeline
  slice (S1, S3, S4, S5, S6) and post its numbers (quad, dims, verdict,
  confidences per photo) in a PROGRESS comment. An empty or absent folder
  no-ops; say so in the comment.
- HANDS-OFF SMOKE POLICY: real-device checks never block slice merges,
  parent close, or the release. Per-slice "optional ask" smoke items are
  noted once on #65 when the slice lands; do not wait on them.

LANDING PROCEDURE (per slice):
1. Self-audit: for every acceptance checkbox, run the command that proves
   it. Tick the boxes via `gh issue edit`. Unmet criteria (give-up path
   only) stay unticked and are named in the closing comment with their
   KNOWN_ISSUES reference - never silently ticked. Boxes covered by the
   local-photos script are ticked with its numbers as evidence; on-phone
   optional-ask items are noted on #65, not ticked.
2. Commit as `S<n>: <what passed>` (body: brief evidence, plus which tests
   were red first). Blessed goldens, if ever legitimately needed, land in
   their own `[bless]` commit with the reason. Before every commit:
   `git diff --cached --name-only` must not touch `tests/golden/` outside
   such a bless commit.
3. Push, `gh pr create --title "S<n>: ..." --body "... Fixes #<issue>"`
   (S5's PR body carries BOTH `Fixes #71` and `Fixes #33`),
   `gh pr merge --merge --delete-branch`, `git checkout main && git pull`,
   confirm the issue auto-closed. Branch hygiene invariant: between slices,
   `main` is the ONLY branch, local and remote (`git fetch --prune`).
4. Post the closing comment: `CLOSING: criteria verified.` plus the pytest
   and vitest/Playwright summary lines and key outputs (S0: the gate
   numbers and the T1-T3 proposal; S4: the L0 identity-vote proof; S9: the
   release checks).
5. If `gh pr merge` is blocked or fails 3 times, comment `BLOCKED:` with
   diagnostics on #65, output `SPRINT BLOCKED: cannot merge PRs`, stop.

NO-THRASH RULE:
- An approach fails when a genuinely distinct strategy (not a parameter
  tweak) demonstrably cannot meet a criterion - or when one approach has
  consumed an entire wakeup with no measured improvement. On abandoning:
  `APPROACH FAILED: <name> - what/why/best numbers` comment.
- COUNCIL ESCALATION: after the 2nd `APPROACH FAILED:` on the same
  criterion, before spending the 3rd attempt, load the adversarial-review
  skill and convene a council prompted to REFUTE the current diagnosis
  (wrong layer? Pyodide quirk? test-harness bug? spec misread? fixture
  bug?). Post the verdict as `PROGRESS:`, then spend the 3rd attempt on its
  best recommendation. Also convene a council before landing S0 if any gate
  check passed only after workarounds you cannot explain.
- On the 3rd for the same criterion: S0 follows the gate stop; S1+ write
  the KNOWN_ISSUES.md entry (all three attempts, actual numbers), mark ONLY
  the unmeetable test `xfail(reason="KNOWN_ISSUES: <entry>", strict=False)`
  (or `test.fails` with the reference in its name), keep every other test
  intact, land the slice with unmet boxes named.

NEVER FAKE A PASS:
- tests/golden/ is frozen; earlier sprints' goldens are never re-blessed
  for sprint 3 convenience. A diff in a golden is a bug in the new code
  until proven otherwise.
- Never edit a threshold, delete or deselect a test, weaken an assertion,
  or change a hand-computed expected value to match output. Sprint 1 and 2
  suites must pass untouched all sprint, except the single S2 e2e traversal
  amendment quoted above.
- The S0 pinned legacy regression (corners + model JSON on L0-L2 seed-42)
  is byte-law from the moment it lands: S1 and S5 changes must keep it
  byte-stable on the legacy path.
- Never force-push, never amend a pushed commit, never rewrite history.

PACING: keep working while local tests run. S0 and S9 must wait on their
own CI run on main; poll with `gh run list` on a short wakeup (~270s).
Otherwise end a wakeup at a natural checkpoint (after a `PROGRESS:`
comment) and continue next iteration. After S0 lands, if the T1-T3 box on
#65 is not yet ticked, output the blocked line from wakeup step 4 rather
than idling.

COMPLETION: when #66-#75 are all closed, verify the parent #65 checklist
(CI green on main including the Pyodide and e2e jobs - wait for it; Pages
root serves the app and the new photo flow works; v0.3.0 release exists
with assets via `gh release view v0.3.0`; #33 closed by S5; sprint 1 and 2
suites intact except the named traversal amendment), tick its boxes except
Jake's smoke items, and verify branch hygiene:
`gh api repos/jakemismas/QREP/branches --jq '.[].name'` returns exactly
`main`. Then post a final summary comment on #65 that INCLUDES the
requested (not required) phone-walkthrough ask for Jake (crop, size,
verdict, editor on live Pages with a real shop photo; findings become NEW
issues, never reopened slices), plus the latest local-photos script output
for his three field-failure photos. Close #65, output the line
`SPRINT COMPLETE` and stop the loop. On an environmental hard block (gh
auth dead, disk full, npm registry unreachable after 3 distinct
strategies), comment `BLOCKED:` on #65 with diagnosis and suggested human
action, output `SPRINT BLOCKED: <one line>` and stop the loop. Never stop
silently.
