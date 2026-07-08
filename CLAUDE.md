# QREP

QREP is an open-source Python library and CLI that reverse engineers quilts
from photographs into production-ready patterns. The design doc
(qrep-design-doc.md) is binding; the build prompt (qrep-claude-code-prompt.md)
implements it. Anything not in those docs is out of scope for v1.

## Environment

- Windows 11, Git Bash shell. Python 3.13 at `python`.
- Work inside the repo venv: `python -m venv .venv` then
  `source .venv/Scripts/activate` (Git Bash path). Install with
  `pip install -e ".[dev]"`.
- Use `opencv-python-headless`, not `opencv-python`. Use `reportlab` for PDF,
  not `weasyprint` (GTK native deps do not install cleanly on Windows).
- Run tests with `python -m pytest`, lint with `python -m ruff check .`.

## Project tracking — GitHub Issues are the source of truth

This repo tracks all work in GitHub Issues. Before starting any task, read the
relevant issue; if none exists, create one. Status lives on the project board,
not in chat or code.

- Hierarchy: feature = parent issue (`type: feature`); tasks/sub-bugs = native
  sub-issues (`gh sub-issue create --parent <n>` via the gh-sub-issue
  extension).
- Labels: one `type:` (feature|bug|task|chore), one `priority:`, one `area:`
  (model|construct|export|render|vision|cli|infra|docs).
- Issue bodies use Description / Acceptance criteria (testable checkboxes) /
  Non-goals, written in AWS docs style: active voice, present tense, second
  person, concise, sentence-case headings, no "please/simply/just".
- On starting: comment the plan on the issue. On finishing: comment
  implementation notes (approach, files, test evidence) and commit with
  `Fixes #<n>` in the message so the merge to main closes the issue.
- Log discovered work as new issues. Never leave a code-only TODO.

## Non-negotiables

- Never edit a test threshold, golden file, or acceptance criterion to force a
  pass. Golden files are generated once via the bless step, reviewed, then
  frozen; regenerating one requires a stated reason in the commit message.
- Every CV-derived value carries a confidence score; hand-authored data is 1.0.
- Commits are authored by Jake Mismas <jake@jakemismas.com> only. No AI
  co-author trailers.
