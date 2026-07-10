# QREP Sprint 4 orchestrator

Generated on the sprint 2/3 skeleton. Drives the sprint 4 build in the house
style (sprint 1-3 conventions; this repo does not run the advanced sprint
suite). The contract is docs/sprint-4/qrep-sprint-4-plan.md; the evidence is
docs/sprint-4/RESEARCH.md.

## Issues

Parent: #91. Discovered bug folded in: #90 (iOS compare), closed by S5.

| Slice | Issue | Theme |
| ----- | ----- | ----- |
| S0 | #92 | degraded corpus, evidence baseline, freeze rite, design bundle |
| S1 | #93 | block-lattice evidence detector |
| S2 | #94 | corroborated verdicts and honest curved-quilt messaging |
| S3 | #95 | pattern document engine: sections, cover, name |
| S4 | #96 | one download in the web app |
| S5 | #97 | mobile lightbox and compare (fixes #90) |
| S6 | #98 | release 0.4.0 |

## Run loop (per slice, in slice order)

1. Comment the slice plan on its issue.
2. Branch `slice/s<n>-<name>` off fresh main.
3. Build to the slice's acceptance criteria and the plan's Definition of
   Done. Run `.venv/Scripts/python -m pytest -q` and `ruff`, plus web
   vitest/playwright where touched.
4. Post PROGRESS and `APPROACH FAILED:` notes on the issue as you go.
5. Open a PR with `Fixes #<issue>` (S5 also `Fixes #90`). Verify the commit
   author and committer are Jake Mismas <jake@jakemismas.com>, no AI
   attribution.
6. Merge with `gh pr merge --merge --delete-branch`; then
   `git checkout main && git pull`. Tick the issue's AC boxes.

## Gates

- After S0's baseline-report comment on #91, STOP. Jake freezes T4, T5, and
  the sigma ladder via the #91 checkbox. Do not start S1 until frozen.
- If S0 cannot separate the 2-color-garbage control from the Irish chain on
  mean cell confidence, exit (a) does not ship: the Irish chain stays
  no_grid honestly. Continue with exit (b) plus the messaging fix.
- The only blessed edit to decide_verdict is the additive keyword-only
  corroboration parameter, bounded by the absence-identity property test.
  T1/T2/T3 stay frozen.
- WOF (#91 checkbox): default keeps 42 and states it in the document; the
  flip switches to 40 with a dedicated [bless] yardage-golden commit in S3.
- S6 kickoff requires every other sub-issue closed and the recorded S5
  phone smoke pass on #91.

## Kickoff prompt (paste into the build chat, run on Opus)

```
QREP Sprint 4 build chat. Execute the sprint; do not replan.

Read first, in order:
- docs/sprint-4/qrep-sprint-4-plan.md   (the contract)
- docs/sprint-4/RESEARCH.md             (evidence)
- docs/sprint-4/ORCHESTRATOR.md         (issue map + run loop + gates)
- CLAUDE.md                             (non-negotiables)

House style, not the advanced sprint suite. Sprint issues exist:
parent #91, slices S0-S6 = #92-#98; S5 also closes #90.

- Work slices in order S0 -> S6. One branch slice/s<n>-<name> + PR per
  slice, "Fixes #<issue>", merged with gh pr merge --merge --delete-branch,
  then git checkout main && git pull. Direct push to main is blocked.
- Comment the plan on each issue before starting; post PROGRESS and
  "APPROACH FAILED:" notes as issue comments.
- Verify git author/committer = Jake Mismas <jake@jakemismas.com> before
  every commit. No AI attribution or co-author trailers.
- Run via the venv interpreter explicitly: .venv/Scripts/python -m pytest -q ;
  .venv/Scripts/python -m ruff check . ; web vitest/playwright where touched.

Gates:
- S0 (#92) ends with a baseline-report comment on #91 proposing T4, T5, and
  the sigma ladder with measured population tables. Then STOP and wait for
  Jake to freeze them via the #91 checkbox before S1.
- If S0 cannot separate the 2-color-garbage control from the Irish chain on
  mean cell confidence, exit (a) does not ship (Irish chain stays no_grid);
  continue with exit (b) plus the messaging fix.
- The only blessed decide_verdict edit is the additive keyword-only
  corroboration parameter, bounded by the absence-identity property test.
  T1/T2/T3 and the L0-L2 byte-pins stay frozen. Never edit a golden or
  threshold to force a pass.
- WOF: keep 42 and state it (default), unless Jake flips the #91 checkbox to
  40 (dedicated [bless] yardage-golden commit in S3).

Start with S0 (#92).
```
