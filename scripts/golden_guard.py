"""Fail a change range whose tests/golden/ edits do not come from [bless] commits.

Golden files are frozen output: CLAUDE.md lets them change only through
`pytest --bless` in a commit whose message carries [bless]. CI runs this on
every pull request (.github/workflows/guards.yml) so the rule holds even when
nobody is watching.

Usage (from any folder; the script checks the checkout it lives in, so a run
of another worktree's copy checks that worktree):
    python scripts/golden_guard.py <base> <head>
    python scripts/golden_guard.py origin/main HEAD   # before opening a PR

The changed golden files are those that merging <head> into <base> changes.
git merge-tree computes that merge, so the answer never depends on which of
several merge bases a three-dot diff happens to pick. The check is then per
commit, so one bless cannot excuse another commit's edit:
  - every non-merge commit in <base>..<head> that touches tests/golden/ must
    be a bless commit: its own message contains [bless], in the subject or
    anywhere in the body, as CLAUDE.md and #105 word the rule. Only commits
    that touch tests/golden/ are judged, so a body elsewhere in the branch
    that mentions the marker in passing excuses nothing. git's
    'Revert "... [bless]"' and 'Reapply "... [bless]"' subjects do not count
    by their quoted part, and neither does the reference that
    `git revert --reference` (or revert.reference=true) writes, 'This reverts
    commit <sha> (... [bless], <date>)', in the subject or the body: undoing a
    bless is not a bless;
  - every golden file the merge changes must end with the content (blob and
    mode) that one of those commits wrote. A merge commit therefore cannot
    leave golden content that no commit in the range produced: a hand-resolved
    conflict, an edit made inside the merge, a criss-cross merge that restores
    an old version, or two blessed versions merged as text.
A range whose golden edits cancel out passes: nothing frozen changes.
Exit codes: 0 pass, 1 unblessed golden change, 2 usage or git error (for
example a shallow clone that lacks <base>, git older than 2.38, or a <head>
that conflicts with <base>, which leaves no merge result to judge).
"""

from __future__ import annotations

import io
import re
import subprocess
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

GUARDED_PATHS = ("tests/golden/",)
BLESS_MARKER = "[bless]"
# git's own subjects for undoing or redoing a commit quote the original one.
REWRAP_PREFIXES = ('Revert "', 'Reapply "')
# git revert --reference names the undone commit as "<short sha> (<subject>,
# <date>)", always with a short date, and a merge revert names the mainline
# parent the same way after ", reversing changes made to". Without --edit the
# reference is in the body; with --edit and an untouched message, cleanup drops
# git's '#' title and the reference becomes the subject. The match runs to the
# last such date in its paragraph, so it takes an undone subject that holds its
# own parentheses and a merge revert's second reference, and it stops at git's
# closing date, so a marker the revert adds after it still counts.
REVERT_REFERENCE = re.compile(
    r"This\s+reverts\s+commit\s+[0-9a-f]{4,}\s+\(.*,\s+\d{4}-\d{2}-\d{2}\)"
)


@dataclass(frozen=True)
class GoldenCommit:
    sha: str
    subject: str
    files: tuple[str, ...]
    message: str = ""
    # What the commit left at each guarded path it touched, as "<mode> <blob>",
    # or None where it deleted the file. Without it, touching a path counts as
    # writing whatever the path ends with.
    wrote: Mapping[str, str | None] | None = None


def is_bless_subject(subject: str) -> bool:
    text = subject.strip()
    if text.startswith(REWRAP_PREFIXES):
        # The quoted part names the commit being undone or redone; only a
        # marker outside the quotes makes this commit a bless.
        opening, closing = text.find('"'), text.rfind('"')
        text = text[closing + 1 :] if closing > opening else ""
    return BLESS_MARKER in without_revert_references(text)


def without_revert_references(text: str) -> str:
    """The text with git's revert references cut out, one paragraph at a time.

    An editor may wrap a reference across lines (git's %s rejoins a wrapped
    subject the same way), so each paragraph's lines are joined first. A space
    stands in for each reference, so the text around it cannot join into a marker.
    """
    paragraphs = text.replace("\r\n", "\n").split("\n\n")
    return "\n\n".join(REVERT_REFERENCE.sub(" ", " ".join(p.split("\n"))) for p in paragraphs)


def message_body(message: str) -> str:
    """The message after its subject paragraph (git's %B is subject, blank line, body)."""
    _subject, blank, body = message.replace("\r\n", "\n").partition("\n\n")
    return body if blank else ""


def is_bless(commit: GoldenCommit) -> bool:
    body = without_revert_references(message_body(commit.message))
    return is_bless_subject(commit.subject) or BLESS_MARKER in body


def _wrote_final(commit: GoldenCommit, path: str, final: Mapping[str, str | None] | None) -> bool:
    if path not in commit.files:
        return False
    if final is None or commit.wrote is None:
        return True
    return commit.wrote.get(path) == final.get(path)


def verdict(
    changed: list[str],
    commits: list[GoldenCommit],
    final: Mapping[str, str | None] | None = None,
) -> tuple[bool, str]:
    """Judge the changed golden paths; `final` maps each to its merged "<mode> <blob>"."""
    if not changed:
        return True, "no changes under " + ", ".join(GUARDED_PATHS)
    listing = "\n".join(f"  {path}" for path in changed)
    unblessed = [c for c in commits if not is_bless(c)]
    unexplained = [
        path for path in changed if not any(_wrote_final(c, path, final) for c in commits)
    ]
    if not unblessed and not unexplained:
        blesses = "\n".join(f"  {c.sha[:12]} {c.subject}" for c in commits)
        return True, (
            f"{len(changed)} golden file(s) changed, all through {BLESS_MARKER} commits:\n"
            f"{listing}\n{blesses}"
        )
    problems = [
        f"  {c.sha[:12]} '{c.subject}' edits {', '.join(c.files)} without "
        f"{BLESS_MARKER} in its own message"
        for c in unblessed
    ] + [
        f"  {path} ends with content that no commit in the range wrote: a merge commit "
        f"produced it, outside any {BLESS_MARKER} commit"
        for path in unexplained
    ]
    return False, (
        f"{len(changed)} golden file(s) changed:\n{listing}\nnot through a bless:\n"
        + "\n".join(problems)
        + "\nGolden files change only through `pytest --bless`, in a commit whose own "
        f"message contains {BLESS_MARKER}. If an edit is not approved, undo it in a new "
        "commit. Golden content that a merge produced (a "
        "hand-resolved conflict, or two blesses merged as text) needs the approved bless "
        "redone in a new commit after the merge. History cannot be rewritten (force-push "
        "is banned), so an approved edit that landed in an unblessed commit needs a new "
        "branch from origin/main with the bless redone in its own commit."
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


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _git(repo: Path, *args: str) -> str:
    result = _run_git(repo, *args)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def resolve_commit(repo: Path, rev: str) -> str:
    return _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").strip()


def merge_result(repo: Path, base: str, head: str) -> str:
    """The tree that merging head into base produces (git merge-tree, git 2.38+)."""
    result = _run_git(repo, "merge-tree", "--write-tree", "--no-messages", base, head)
    if result.returncode == 1:
        lines = result.stdout.splitlines()[1:]
        conflicted = sorted({line.split("\t", 1)[1] for line in lines if "\t" in line})
        raise RuntimeError(
            f"{head} does not merge cleanly into {base} (conflicts in "
            f"{', '.join(conflicted) or 'unlisted files'}), so there is no merge result to "
            "judge; merge the base into the branch, resolve the conflicts and push"
        )
    if result.returncode != 0:
        raise RuntimeError(
            f"git merge-tree --write-tree failed (it needs git 2.38 or later): "
            f"{result.stderr.strip()}"
        )
    return result.stdout.splitlines()[0].strip()


def changed_guarded_files(repo: Path, base: str, tree: str) -> list[str]:
    out = _git(
        repo, "diff-tree", "-r", "--no-renames", "--name-only", "-z", base, tree, "--",
        *GUARDED_PATHS,
    )
    return [path for path in out.split("\x00") if path]


def guarded_entries(repo: Path, tree: str) -> dict[str, str]:
    """Each guarded file in a tree, as "<mode> <blob>"."""
    out = _git(repo, "ls-tree", "-r", "--full-tree", "-z", tree, "--", *GUARDED_PATHS)
    entries = {}
    for record in out.split("\x00"):
        meta, tab, path = record.partition("\t")
        if tab:
            mode, _kind, blob = meta.split()
            entries[path] = f"{mode} {blob}"
    return entries


def _written(raw: str) -> dict[str, str | None]:
    """Parse `git diff-tree --raw -z` output into what each touched path ended as."""
    fields = raw.split("\x00")
    wrote: dict[str, str | None] = {}
    for meta, path in zip(fields[0::2], fields[1::2]):
        if not meta.startswith(":"):
            continue
        _old_mode, new_mode, _old_blob, new_blob, status = meta[1:].split()
        wrote[path] = None if status.startswith("D") else f"{new_mode} {new_blob}"
    return wrote


def golden_commits(repo: Path, base: str, head: str) -> list[GoldenCommit]:
    # rev-list is plumbing, so no log.* setting can change its output. Its
    # default history simplification skips side-branch commits whose golden
    # edits a merge then discarded; those never reach the result.
    out = _git(
        repo,
        "rev-list",
        "--no-merges",
        "--no-commit-header",
        "--format=%x01%H%x00%s%x00%B",
        f"{base}..{head}",
        "--",
        *GUARDED_PATHS,
    )
    commits = []
    for record in out.split("\x01")[1:]:
        sha, _, rest = record.partition("\x00")
        subject, _, message = rest.partition("\x00")
        raw = _git(
            repo,
            "diff-tree",
            "--no-commit-id",
            "-r",
            "--root",
            "--no-renames",
            "--raw",
            "--no-abbrev",
            "-z",
            sha,
            "--",
            *GUARDED_PATHS,
        )
        wrote = _written(raw)
        commits.append(GoldenCommit(sha, subject, tuple(wrote), message, wrote))
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
        base_sha, head_sha = resolve_commit(repo, base), resolve_commit(repo, head)
        tree = merge_result(repo, base_sha, head_sha)
        changed = changed_guarded_files(repo, base_sha, tree)
        final: dict[str, str | None] = {}
        commits: list[GoldenCommit] = []
        if changed:
            entries = guarded_entries(repo, tree)
            final = {path: entries.get(path) for path in changed}
            commits = golden_commits(repo, base_sha, head_sha)
        ok, message = verdict(changed, commits, final)
    except RuntimeError as err:
        print(f"golden_guard: {err}", file=sys.stderr)
        return 2
    scope = f"merging {head} into {base} in {repo}"
    print(f"golden_guard ({scope}): {'PASS' if ok else 'FAIL'}: {message}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
