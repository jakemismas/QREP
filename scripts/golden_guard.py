"""Fail a change range whose tests/golden/ edits do not come from [bless] commits.

Golden files are frozen output: CLAUDE.md lets them change only through
`pytest --bless` in a commit whose message contains [bless]. CI runs this on
every pull request so the rule holds even when nobody is watching.

Usage (from any folder; the script checks the checkout it lives in, so a run
of another worktree's copy checks that worktree):
    python scripts/golden_guard.py <base> <head>
    python scripts/golden_guard.py origin/main HEAD   # before opening a PR

The check is per commit, so one bless cannot excuse another commit's edit:
  - every non-merge commit in <base>..<head> that touches tests/golden/ needs
    [bless] in its own subject line. Every bless commit in this repo carries
    it there, while bodies often mention the marker in passing ("the golden
    lands in the next [bless] commit"), so a body never counts. Neither does
    git's 'Revert "... [bless]"' subject: undoing a bless is not a bless;
  - every golden file the range changes (three-dot diff: what <head> changed
    since it forked from <base>) must be touched by one of those commits, so
    an edit made inside a merge commit fails too.
A range whose golden edits cancel out passes: nothing frozen changes.
Exit codes: 0 pass, 1 unblessed golden change, 2 usage or git error (for
example a shallow clone that lacks <base>).
"""

from __future__ import annotations

import io
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

GUARDED_PATHS = ("tests/golden/",)
BLESS_MARKER = "[bless]"
# git's own subjects for undoing or redoing a commit quote the original one.
REWRAP_PREFIXES = ('Revert "', 'Reapply "')


@dataclass(frozen=True)
class GoldenCommit:
    sha: str
    subject: str
    files: tuple[str, ...]


def is_bless_subject(subject: str) -> bool:
    text = subject.strip()
    if text.startswith(REWRAP_PREFIXES):
        # The quoted part names the commit being undone or redone; only a
        # marker outside the quotes makes this commit a bless.
        opening, closing = text.find('"'), text.rfind('"')
        text = text[closing + 1 :] if closing > opening else ""
    return BLESS_MARKER in text


def verdict(changed: list[str], commits: list[GoldenCommit]) -> tuple[bool, str]:
    if not changed:
        return True, "no changes under " + ", ".join(GUARDED_PATHS)
    listing = "\n".join(f"  {path}" for path in changed)
    unblessed = [c for c in commits if not is_bless_subject(c.subject)]
    touched = {path for c in commits for path in c.files}
    unexplained = [path for path in changed if path not in touched]
    if not unblessed and not unexplained:
        blesses = "\n".join(f"  {c.sha[:12]} {c.subject}" for c in commits)
        return True, (
            f"{len(changed)} golden file(s) changed, all through {BLESS_MARKER} commits:\n"
            f"{listing}\n{blesses}"
        )
    problems = [
        f"  {c.sha[:12]} '{c.subject}' edits {', '.join(c.files)} without "
        f"{BLESS_MARKER} in its subject line"
        for c in unblessed
    ] + [
        f"  {path} changes inside a merge commit, outside any {BLESS_MARKER} commit"
        for path in unexplained
    ]
    return False, (
        f"{len(changed)} golden file(s) changed:\n{listing}\nnot through a bless:\n"
        + "\n".join(problems)
        + "\nGolden files change only through `pytest --bless`, in a commit with "
        f"{BLESS_MARKER} in its subject line. If the edit is not approved, revert it "
        "in a new commit. History cannot be rewritten (force-push is banned), so an "
        "approved edit that landed in an unblessed commit needs a new branch from "
        "origin/main with the bless redone in its own commit."
    )


def repo_root() -> Path:
    """The top of the checkout this script file lives in, wherever it runs from."""
    here = Path(__file__).resolve().parent
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=here, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"{here} is not inside a git checkout: {result.stderr.strip()}")
    return Path(result.stdout.strip())


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def changed_guarded_files(repo: Path, base: str, head: str) -> list[str]:
    out = _git(
        repo, "diff", "--no-renames", "--name-only", "-z", f"{base}...{head}", "--", *GUARDED_PATHS
    )
    return [path for path in out.split("\x00") if path]


def golden_commits(repo: Path, base: str, head: str) -> list[GoldenCommit]:
    # rev-list is plumbing, so no log.* setting can change its output. Its
    # default history simplification skips side-branch commits whose golden
    # edits a merge then discarded; those never reach the result.
    out = _git(
        repo,
        "rev-list",
        "--no-merges",
        "--no-commit-header",
        "--format=%H%x00%s",
        f"{base}..{head}",
        "--",
        *GUARDED_PATHS,
    )
    commits = []
    for line in out.splitlines():
        sha, _, subject = line.partition("\x00")
        files = _git(
            repo,
            "diff-tree",
            "--no-commit-id",
            "--name-only",
            "-r",
            "--root",
            "-z",
            sha,
            "--",
            *GUARDED_PATHS,
        )
        commits.append(GoldenCommit(sha, subject, tuple(p for p in files.split("\x00") if p)))
    return commits


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        # Commit subjects may hold characters the console code page cannot print.
        sys.stdout.reconfigure(errors="backslashreplace")
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    base, head = argv
    try:
        repo = repo_root()
        changed = changed_guarded_files(repo, base, head)
        commits = golden_commits(repo, base, head) if changed else []
        ok, message = verdict(changed, commits)
    except RuntimeError as err:
        print(f"golden_guard: {err}", file=sys.stderr)
        return 2
    print(f"golden_guard ({base}...{head} in {repo}): {'PASS' if ok else 'FAIL'}: {message}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
