# QREP sprint 5 overnight report

<!--
Template, committed. The orchestrator copies it to docs/sprint-5/OVERNIGHT-REPORT.md at the start
of the run (that live copy stays local: #105 gitignores it), fills it after every merge, BLOCKED
item, rotation and new scorecard number, and posts the final copy on #104
(docs/sprint-5/ORCHESTRATOR.md, section 16). Delete this comment in the live copy.

Filling rules:
- Every number cites its source: a command, a CI run id, a PR, or a report file. Write
  "not measured" rather than an estimate, and never print a guess as a fact.
- "Before" measures the start SHA and "after" measures the end SHA, with the same harness.
- The #104 copy follows ORCHESTRATOR.md section 4: aggregate numbers only for the reference
  patterns and the private corpus tiers, no private screenshots, no private paths.
- Keep this structure. Fill or mark "not measured"; do not drop a section.
-->

Last updated: <local time> by <orchestrator name>

## Headline

- Run: <start time> to <end time, or "still running">. Start SHA <sha>; end SHA <sha>.
- Stop reason: <all launchable work merged, BLOCKED or waiting on Jake | failure stop: what and
  where | still running at the last update>.
- Merged: <n> PRs, each verified on origin/main with green main CI: <#..., #...>.
- Closed: <n> issues: <#..., #...>.
- Open work: building <tickets>; in review <PRs>; queued <tickets>.
- BLOCKED: <n> items need you (see "Needs you").
- Release readiness: <not ready: main reasons | ready for your freeze>. Release PR <#n | not yet
  prepared>; not tagged.
- Orchestrators: <name (generation, from to)>; rotations: <n>.

## Needs you

BLOCKED items and decisions, oldest first.

| # | Since | Ticket or mechanism | What blocked it | Evidence | What you decide |
| --- | --- | --- | --- | --- | --- |
| 1 | <time> | <ticket> | <failed check or open question> | <link> | <the decision> |

## Jake's morning checklist

- [ ] Confirm or correct the region-tool interpretation that `docs/SPEC.md` section 5 records: on
      Your pattern you drag or expand a square selection over a wrong region, from a few squares up
      to the whole quilt, and QREP re-reads only that region and shows a before and after to
      accept. It is a re-read, not paint editing. Reply on #104.
- [ ] Verify the corpus counts on the dev page: <URL or commands, verified by the orchestrator at
      <time>>. Confirm or correct the corners, counts and border bands of each photo the gate
      counts: <n> photos, about <minutes> by D3's estimate.
- [ ] Do a phone pass on a local preview: <commands, verified by the orchestrator at <time>>. Walk
      the whole flow on your phone and note what you find on #104.
- [ ] Revert the VS Code permission setting if you want: `claudeCode.initialPermissionMode`
      (and `claudeCode.allowDangerouslySkipPermissions`) in your VS Code user settings apply to
      every VS Code workspace on this machine, not only QREP.
- [ ] Restore your power settings if you want: sleep, screen off and lock.
- [ ] Freeze the gate: post the frozen numbers on #104 (proposals and measurements are under
      "Release readiness").
- [ ] Approve the release PR <#n> that E4 prepared. Merging it and tagging the release stay yours.

Optional:

- [ ] Read "Approvals used, retirements and blesses" against `docs/sprint-5/REBASELINE.md` and
      section 3 of the plan.
- [ ] Close the probe tabs from 2026-10-06 (qrep-11, qrep-40, qrep-ff, qrep-3d, qrep-2a and one
      dormant resumed tab). Tonight's worker tabs are listed under "Worker tabs".
- [ ] If you get your mother's exact backing case (quilt size, QREP's number, the calculator and
      its number), post it on #104; it becomes a failing hand-computed test. If she becomes
      available, send her the release-candidate PDF.
- [ ] To make aiguard require your exact author on local commits, set `aiguard.author` in your
      own terminal (see the aiguard README).
- [ ] Answer the open items under "Jake queue".

## What landed

| Ticket | Issue | PR | Merge SHA | Verified on main | Main CI run | Review rounds (core?) | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <id> | #<n> | #<n> | <sha> | <time> | <run id> | <n> (<yes/no>) | <one line> |

## Scorecards, before and after

Before: start SHA <sha>. After: end SHA <sha>. Same harness for both columns.

### Corpus (before: D4 baseline of the current read; after: D5)

| Tier | n | Fully correct interior rate | Confident-wrong squares rate | Refusal recall | False-warning rate | Source |
| --- | --- | --- | --- | --- | --- | --- |
| Museum CC0 | <n> | <before> / <after> | <before> / <after> | not applicable | <before> / <after> | <report, SHA> |
| Private shop screenshots (aggregate) | <n> | <before> / <after> | <before> / <after> | not applicable | <before> / <after> | <report, SHA> |
| Real phone captures | <n, or "not supplied yet"> | <before> / <after> | <before> / <after> | not applicable | <before> / <after> | <report, SHA> |
| Refusal set | <n> | not applicable | not applicable | <before> / <after> | <before> / <after> | <report, SHA> |

### Calculators (before: D2 baseline; after: D7)

| Size (in) | Item | QREP before | QREP after | Calculators (name: value) | Spread | Verdict | Source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| <w x h> | backing | <yd> | <yd> | <name: yd; ...> | <min to max> | <within / outside> | <report, date> |
| <w x h> | binding | <yd> | <yd> | <name: yd; ...> | <min to max> | <within / outside> | <report, date> |
| <w x h> | batting | <size> | <size> | <name: size; ...> | <min to max> | <within / outside> | <report, date> |
| <w x h> | yardage | <yd> | <yd> | <name: yd; ...> | <min to max> | <within / outside> | <report, date> |

Parity summary: <n of m line items within the calculator spread before, n of m after>.

### Reference patterns (D6, aggregate numbers only)

| Measure (as D6 defines it) | Before (start SHA) | After (end SHA) | Patterns compared | Source |
| --- | --- | --- | --- | --- |
| <for example, finished size matches> | <value> | <value> | <n> | <report> |
| <for example, cutting within D6's tolerance> | <value> | <value> | <n> | <report> |
| <for example, yardage within D6's tolerance> | <value> | <value> | <n> | <report> |
| <for example, sections that follow PATTERN-SPEC.md> | <value> | <value> | <n> | <report> |

### Test suites

| Suite | Before (start SHA, CI run) | After (end SHA, CI run) | Retired per REBASELINE.md | Re-expressed | New |
| --- | --- | --- | --- | --- | --- |
| pytest, Python 3.12 and 3.13 | <passed, failed, skipped> | <passed, failed, skipped> | <n> | <n> | <n> |
| Pyodide pytest | <passed, failed, skipped> | <passed, failed, skipped> | <n> | <n> | <n> |
| vitest | <passed, failed, skipped> | <passed, failed, skipped> | <n> | <n> | <n> |
| Playwright e2e | <passed, failed, skipped> | <passed, failed, skipped> | <n> | <n> | <n> |
| Lint and guards (ruff, oxlint, golden-guard, corpus-guard) | <state> | <state> | not applicable | not applicable | not applicable |

### Review

- Per-PR reviews: <n> PRs, <n> rounds. Findings raised (critical, major, minor, nit):
  <n, n, n, n>; fixed: <n, n, n, n>; deferred: <n>, to <tickets or follow-up issues>.
- Verified code review (`docs/sprint-5/REVIEW.md`): <n> findings mapped to tickets; <n> closed by
  merged tickets; <n> still open.
- E3 full adversarial review: <rounds, result, open findings, or "not run yet">.
- D8 virtual quilter panel on the release-candidate PDF: <verdict and rubric score per persona,
  or "not run yet">.

### UX walkthrough (D9)

- Before: the screenshots in the private evidence folder under `recon/ux/` (<n>).
- After: <private folder> (<n>), taken at <SHA> at desktop and phone sizes.
- Findings: fixed <n> (<list>); open <n> (<list>). The #104 copy lists findings only.

## Release readiness against the gate

The gate lives in the plan (`docs/SPEC.md` section 11 summarizes it). Its thresholds are proposals
until you freeze them; they are frozen only after the new read is measured.

| Criterion | Proposed threshold | Measured | n | Status | Source |
| --- | --- | --- | --- | --- | --- |
| Fully correct interior rate, per tier | <from the plan> | <value per tier> | <n per tier> | <pass, fail, not measured> | <D5 report> |
| Confident-wrong squares rate, per tier | <from the plan> | <value per tier> | <n per tier> | <pass, fail, not measured> | <D5 report> |
| Refusal recall, with the false-warning cap | <from the plan> | <recall; false-warning rate> | <n> | <pass, fail, not measured> | <D5 report> |
| Calculator parity after the math | <from the plan> | <summary> | <line items> | <pass, fail, not measured> | <D7 report> |
| Virtual quilter panel on the release-candidate PDF | <from the plan> | <verdict> | 3 reviewers | <pass, fail, not measured> | <D8 report> |
| Every sprint sub-issue closed, or labeled backlog with your OK | all | <open count> | <total> | <pass, fail> | `gh sub-issue list 104` |
| Release PR prepared by E4, not tagged | prepared | <#n or none> | not applicable | <ready, not ready> | <PR link> |

## Approvals used, retirements and blesses

| Time | Plan section 3 item | Ticket | PR | What it did |
| --- | --- | --- | --- | --- |
| <time> | <item> | <id> | #<n> | <one line> |

- Tests retired or re-expressed tonight: <n>, each matched to its `REBASELINE.md` entry
  (<list or link>). Any mismatch is an incident.
- Blesses: <the one consolidated [bless] commit and the goldens it names, or "none yet">.

## Incident log

Kinds: failed check, flake rerun, dead tab, stall, usage-limit pause, rotation, revert, launch
stop, hook block, other.

| Time | Kind | Ticket or mechanism | What happened | Action | Link |
| --- | --- | --- | --- | --- | --- |
| <time> | <kind> | <id> | <one line> | <one line> | <link> |

## Worker tabs

The tabs stay open so you can read them.

| Tab | Ticket | Role | Outcome | PR | Notes |
| --- | --- | --- | --- | --- | --- |
| <qrep-xx> | <id> | <build, test, spike, orchestrator> | <merged, BLOCKED, in review, ...> | #<n> | <one line> |

## Jake queue

| Question or input | What it blocks | Asked (time, where) |
| --- | --- | --- |
| <question> | <tickets> | <time, #104 comment link> |
