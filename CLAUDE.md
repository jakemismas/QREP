# QREP

QREP reverse engineers quilts from photographs into production-ready
patterns. The product surface is the web app (web/, live at
https://jakemismas.github.io/QREP/); the Python library and CLI remain the
developer and test surface. The binding docs, in reading order:
qrep-design-doc.md (v1 engine), docs/sprint-2/qrep-web-design-doc.md (the
web app; its Amendments section supersedes the v1 "no web app" scope line),
and docs/design/sprint-2/PARITY.md (UI behavior annex). The build contract
(qrep-claude-code-prompt.md) implements the v1 doc. Anything not in those
docs is out of scope. Where this Environment section conflicts with a stack
pin in any doc, this section wins.

## Environment

- Windows 11, Git Bash shell. Python 3.13.3 at `python`.
- All Python runs through the repo venv interpreter EXPLICITLY:
  `.venv/Scripts/python -m pip install -e ".[dev]"`,
  `.venv/Scripts/python -m pytest -q`,
  `.venv/Scripts/python -m ruff check .`.
  Never rely on `source activate` persisting between tool calls; never install
  into system Python.
- Use `opencv-python-headless`, never `opencv-python`. Use `reportlab` for
  PDF, never `weasyprint` (GTK native deps do not install on this box).

## Project tracking — GitHub Issues are the source of truth

This repo tracks all work in GitHub Issues. Before starting any task, read the
relevant issue; if none exists, create one. Status lives on the project board,
not in chat or code.

- Hierarchy: feature = parent issue (`type: feature`); tasks/sub-bugs = native
  sub-issues (`gh sub-issue create --parent <n>`). If the extension is
  unavailable, fall back to plain issues with a "Parent: #n" line; never block
  work on tracking mechanics.
- Labels: one `type:` (feature|bug|task|chore), one `priority:`, one `area:`
  (model|construct|export|render|vision|cli|infra|docs).
- Issue bodies use Description / Acceptance criteria (testable checkboxes) /
  Non-goals, in AWS docs style: active voice, present tense, second person,
  concise, sentence-case headings, no "please/simply/just".
- On starting: comment the plan on the issue. Progress notes and abandoned
  approaches (`APPROACH FAILED:`) go to issue comments — they are the durable
  memory that survives context compaction.
- Work lands via branch + PR: branch `slice/s<n>-<name>` (or
  `fix/<name>`), PR body contains `Fixes #<n>`, merge with
  `gh pr merge --merge --delete-branch`, then `git checkout main && git pull`.
  Direct pushes to main are blocked by policy — do not attempt them.
- Log discovered work as new issues (no `S<n>:` title prefix — that prefix is
  reserved for ordered sprint slices). Never leave a code-only TODO.

## Non-negotiables

- Never edit a test threshold, golden file, or acceptance criterion to force a
  pass. Golden files under tests/golden/ are created once via `pytest --bless`
  in a commit whose message contains `[bless]`, then frozen; before every
  commit check `git diff --cached --name-only` does not touch tests/golden/.
  The only honest escape for an unreachable criterion is
  `xfail(reason="KNOWN_ISSUES: <entry>")` after 3 documented
  `APPROACH FAILED:` comments.
- Expected test values flow one way: hand computation (in comments) to
  assertion. Never observed output to assertion, except through bless, once.
- Every CV-derived value carries a confidence score; hand-authored data is 1.0.
- Commits are authored by Jake Mismas <jake@jakemismas.com> only — verify
  `git config user.name` / `user.email` before committing. No AI co-author
  trailers of any kind.
- Never force-push, never amend a pushed commit, never disable or delete CI.
