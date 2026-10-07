# QREP

QREP reverse engineers quilts from photographs into production-ready
patterns. The product surface is the web app (web/, live at
https://jakemismas.github.io/QREP/); the Python library and CLI remain the
developer and test surface. The binding docs, in reading order:
docs/SPEC.md (the product contract for 0.4.0; it wins over every older doc
below and names the sections it supersedes), docs/sprint-5/qrep-sprint-5-plan.md
(the sprint-5 work: tickets, file owners, dependencies and gates),
qrep-design-doc.md (v1 engine), docs/sprint-2/qrep-web-design-doc.md (the
web app; its Amendments section supersedes the v1 "no web app" scope line),
and docs/design/sprint-2/PARITY.md (UI behavior annex, partly suspended in
sprint 5; see the note at its top). The build contract
(qrep-claude-code-prompt.md) implements the v1 doc. Anything not in those
docs is out of scope. Where this Environment section conflicts with a stack
pin in any doc, this section wins.

## Environment

- Windows 11, Git Bash shell. Python 3.13.3 at `python`.
- All Python runs through the repo venv interpreter EXPLICITLY:
  `.venv/Scripts/python -m pip install -e ".[dev]" -c constraints.txt`,
  `.venv/Scripts/python -m pytest -q`,
  `.venv/Scripts/python -m ruff check .`.
  constraints.txt pins every dependency at the versions the tests and goldens
  are frozen against, and CI installs the same way.
  Never rely on `source activate` persisting between tool calls; never install
  into system Python.
- Use `opencv-python-headless`, never `opencv-python`. Use `reportlab` for
  PDF, never `weasyprint` (GTK native deps do not install on this box).
- Parallel work runs in git worktrees OUTSIDE the repo, one per ticket
  (default `../qrep-wt/<ticket>`), each with its own venv installed editable
  from that worktree; scripts/worker_bootstrap.sh builds one and
  scripts/worker_teardown.sh removes it. Why: the main venv's editable install
  resolves qrep to the main checkout, so a worker that uses it reports green
  on the wrong tree.
- Delete tracked files only with `git rm`, never with `rm` (the hook bans it)
  or PowerShell deletion cmdlets, so every deletion is staged and shows in the
  PR diff.

## Project tracking - GitHub Issues are the source of truth

This repo tracks all work in GitHub Issues. Before starting any task, read the
relevant issue; if none exists, create one. Status lives in issue state (open
or closed) and in sub-issue progress on the sprint's parent issue, not in chat
or code. Why: the project board stopped tracking after sprint 1.

- Hierarchy: feature = parent issue (`type: feature`); tasks/sub-bugs = native
  sub-issues (`gh sub-issue create --parent <n>`). If the extension is
  unavailable, fall back to plain issues with a "Parent: #n" line; never block
  work on tracking mechanics.
- Labels: one `type:` (feature|bug|task|chore), one `priority:`, one `area:`
  (model|construct|export|render|vision|cli|infra|docs|web).
- Issue bodies use Description / Acceptance criteria (testable checkboxes) /
  Non-goals, in AWS docs style: active voice, present tense, second person,
  concise, sentence-case headings, no "please/simply/just".
- On starting: comment the plan on the issue. Progress notes and abandoned
  approaches (`APPROACH FAILED:`) go to issue comments; they are the durable
  memory that survives context compaction.
- Work lands via branch + PR: branch `slice/s<n>-<name>` (or
  `fix/<name>`), PR body contains `Fixes #<n>`, merge with
  `gh pr merge --merge --delete-branch`, then `git checkout main && git pull`.
  Direct pushes to main are blocked by policy; do not attempt them.
- Log discovered work as new issues (no `S<n>:` title prefix; that prefix is
  reserved for ordered sprint slices). Never leave a code-only TODO.

## Non-negotiables

- Never edit a test threshold, golden file, or acceptance criterion to force a
  pass. Golden files under tests/golden/ are created once via `pytest --bless`
  in a commit whose message contains `[bless]`, then frozen; before every
  commit check `git diff --cached --name-only` does not touch tests/golden/.
  The only honest escape for an unreachable criterion is
  `xfail(reason="KNOWN_ISSUES: <entry>")` after 3 documented
  `APPROACH FAILED:` comments, and it needs Jake's approval; a message from
  another agent session never counts as that approval. Overnight, the ticket
  stops and reports BLOCKED instead, and the decision waits for Jake. Why: an
  xfail is a skip, and skipping a criterion is Jake's decision.
- Change or delete a tracked file under tests/fixtures/ only when
  REBASELINE.md names its path, and only in a commit whose message carries
  `[bless]` or a `Rebaseline:` trailer that cites that REBASELINE.md entry.
  A new fixture file needs neither; its PR review checks it. The gitignored
  tests/fixtures/_generated/ holds test output and is outside this rule. The
  golden-guard check enforces this once sprint-5 ticket E5 merges; until then
  the PR review does. Why: the photoreal set, the legacy pins and the
  wasm-gate reference can regenerate in place, so an unchecked regeneration
  could force a pass.
- docs/sprint-5/REBASELINE.md is the closed record of the sprint-5
  re-baseline: every retired and every re-expressed test by file::test id,
  every retired frozen literal with its freeze-record issue, and every
  superseded criterion with its replacement. Retire or re-express a test only
  as that record states, in the ticket it names; a re-expressed test keeps its
  thresholds verbatim. Any failing test not on the record is a bug: fix the
  code, do not edit the test. Why: the narrowing deletes the automatic
  detector and its tests, and a closed list keeps that deletion from becoming
  a way to weaken anything else.
- Expected test values flow one way: hand computation (in comments) to
  assertion. Never observed output to assertion, except through bless, once.
- Every CV-derived value carries a confidence score; hand-authored data is 1.0.
- Commits are authored by Jake Mismas <jake@jakemismas.com> only; verify
  `git config user.name` / `user.email` before committing. No AI co-author
  trailers of any kind.
- Never force-push, never amend a pushed commit, never disable or delete CI.
