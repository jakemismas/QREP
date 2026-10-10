"""Fail a change range whose tests/golden/ or tests/fixtures/ edits are not sanctioned.

Golden files are frozen output: CLAUDE.md lets them change only through
`pytest --bless` in a commit whose message carries [bless]. Tracked fixtures
are frozen too: CLAUDE.md lets one change or go only when REBASELINE.md names
its path, in a commit whose message carries [bless] or a `Rebaseline:` trailer
that cites that entry. CI runs this on every pull request
(.github/workflows/guards.yml) so the rules hold even when nobody is watching.

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

The fixture rule judges each tracked file under tests/fixtures/ that the merge
modifies or deletes; a file the merge adds passes, for the pull request review
to check, and the gitignored test output under tests/fixtures/_generated/ is
outside the rule, as CLAUDE.md states. For each judged file:
  - REBASELINE.md as the base commit holds it must name the file's whole path.
    The head's copy never counts, because a pull request could otherwise admit
    a path by listing it in its own diff; a new path needs an amendment Jake
    approves, merged first (REBASELINE.md, Amending this record);
  - every non-merge commit in <base>..<head> that touches the file, in the
    same history walk as the golden rule, must carry [bless] by the golden
    rule above, or a non-empty `Rebaseline:` trailer as git parses trailers:
    in the message's last paragraph, never the subject, the reading of
    `git interpret-trailers --parse --no-divider`;
  - the merge must leave the content (or the deletion) that one of those
    commits wrote, so a merge commit cannot regenerate a fixture on its own.
The guard checks that the record names the path and that the trailer is
there, not which entry the trailer cites or whether that entry allows this
kind of change (the support-file rows name paths that only leave): the pull
request review checks the citation.
Exit codes: 0 pass, 1 unsanctioned golden or fixture change, 2 usage or git error (for
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
FIXTURE_PATHS = ("tests/fixtures/",)
FIXTURE_OUTPUT = "tests/fixtures/_generated/"
RECORD = "docs/sprint-5/REBASELINE.md"
TRAILER_KEY = "Rebaseline"
BLESS_MARKER = "[bless]"
# git's own subjects for undoing or redoing a commit quote the original one.
REWRAP_PREFIXES = ('Revert "', 'Reapply "')
# git revert --reference names the undone commit as "<short sha> (<subject>,
# <date>)", always with a short date, and a merge revert names the mainline
# parent the same way after ", reversing changes made to". Without --edit the
# reference is in the body; with --edit and an untouched message, cleanup drops
# git's '#' title and the reference becomes the subject. A match runs to the
# last such date in its paragraph, so it takes an undone subject that holds its
# own parentheses and a merge revert's second reference; a marker after that
# date still counts, one before a later dated reference in the same paragraph
# does not. A reference that lost its closing date (cleanup drops a wrapped
# line that starts with '#') runs to the end of its paragraph instead, so the
# undone commit's marker never survives a cut.
REVERT_REFERENCE = re.compile(
    r"This\s+reverts\s+commit\s+[0-9a-f]{4,}\s+\((?:.*,\s+\d{4,}-\d{2}-\d{2}\)|.*)", re.ASCII
)
# git ends a paragraph at a line that holds only spaces or tabs, too.
PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")


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
    # The values of the message's Rebaseline: trailers, as git parses them.
    rebaseline: tuple[str, ...] = ()


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
    paragraphs = PARAGRAPH_BREAK.split(text.replace("\r\n", "\n"))
    return "\n\n".join(REVERT_REFERENCE.sub(" ", " ".join(p.split("\n"))) for p in paragraphs)


def message_body(message: str) -> str:
    """The message after its subject paragraph (git's %B is subject, blank line, body)."""
    _subject, blank, body = message.replace("\r\n", "\n").partition("\n\n")
    return body if blank else ""


def is_bless(commit: GoldenCommit) -> bool:
    body = without_revert_references(message_body(commit.message))
    return is_bless_subject(commit.subject) or BLESS_MARKER in body


def is_sanctioned_fixture_change(commit: GoldenCommit) -> bool:
    return is_bless(commit) or any(value.strip() for value in commit.rebaseline)


def names_path(record: str, path: str) -> bool:
    """Whether the record names the path whole, not inside a longer path or name.

    A sentence may end right after the path, so a period counts as the end
    only when no path character follows it.
    """
    pattern = rf"(?<![\w./-]){re.escape(path)}(?![\w/-]|\.[\w/-])"
    return re.search(pattern, record) is not None


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


def fixture_verdict(
    changed: list[str],
    commits: list[GoldenCommit],
    named: set[str],
    final: Mapping[str, str | None] | None = None,
) -> tuple[bool, str]:
    """Judge the tracked fixtures the merge modifies or deletes.

    `commits` are the range's non-merge commits that touch them, `named` the
    ones the base's record names, and `final` maps each to its merged
    "<mode> <blob>", or None where the merge deletes it.
    """
    if not changed:
        return True, "no tracked file under " + ", ".join(FIXTURE_PATHS) + " modified or deleted"
    listing = "\n".join(f"  {path}" for path in changed)
    unnamed = [path for path in changed if path not in named]
    unsanctioned = [c for c in commits if not is_sanctioned_fixture_change(c)]
    unexplained = [
        path for path in changed if not any(_wrote_final(c, path, final) for c in commits)
    ]
    if not unnamed and not unsanctioned and not unexplained:
        sanctioned = "\n".join(f"  {c.sha[:12]} {c.subject}" for c in commits)
        return True, (
            f"{len(changed)} tracked fixture(s) modified or deleted, each named in {RECORD} at "
            f"the base and changed only in {BLESS_MARKER} or {TRAILER_KEY}: commits:\n"
            f"{listing}\n{sanctioned}"
        )
    problems = (
        [f"  {path} is not named in {RECORD} at the base commit" for path in unnamed]
        + [
            f"  {c.sha[:12]} '{c.subject}' changes {', '.join(c.files)} without "
            f"{BLESS_MARKER} or a {TRAILER_KEY}: trailer in its own message"
            for c in unsanctioned
        ]
        + [
            f"  {path} ends with content that no commit in the range wrote: a merge commit "
            "produced it"
            for path in unexplained
        ]
    )
    return False, (
        f"{len(changed)} tracked fixture(s) modified or deleted:\n{listing}\n"
        "not through a sanctioned change:\n"
        + "\n".join(problems)
        + f"\nA tracked file under {FIXTURE_PATHS[0]} changes or goes only when {RECORD} on "
        "the base branch names its path, in a commit whose own message carries "
        f"{BLESS_MARKER} or ends with a `{TRAILER_KEY}: <entry>` trailer that cites that "
        "entry. A path the record does not name needs an amendment Jake approves, merged "
        "first (REBASELINE.md, Amending this record); listing it in this branch's copy does "
        "not count. If an edit is not approved, undo it in a new commit. Content that a merge "
        "produced needs a sanctioned commit behind it: resolve the merge with the base's copy "
        "of the file, or, once the merge is committed, commit the base's copy back with the "
        "trailer; then redo the change in a new commit with the trailer."
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


def changed_frozen_fixtures(repo: Path, base: str, tree: str) -> list[str]:
    """Tracked fixtures that exist at the base and that the merge modifies or deletes."""
    out = _git(
        repo, "diff-tree", "-r", "--no-renames", "--name-status", "-z", base, tree, "--",
        *FIXTURE_PATHS,
    )
    fields = out.split("\x00")
    return [
        path
        for status, path in zip(fields[0::2], fields[1::2])
        if status and status != "A" and not path.startswith(FIXTURE_OUTPUT)
    ]


def record_at(repo: Path, commit: str) -> str:
    """The commit's REBASELINE.md, or "" where it has none, which names nothing."""
    if not _git(repo, "ls-tree", "--full-tree", "-z", commit, "--", RECORD):
        return ""
    return _git(repo, "cat-file", "blob", f"{commit}:{RECORD}")


def guarded_entries(
    repo: Path, tree: str, paths: tuple[str, ...] = GUARDED_PATHS
) -> dict[str, str]:
    """Each guarded file in a tree, as "<mode> <blob>"."""
    out = _git(repo, "ls-tree", "-r", "--full-tree", "-z", tree, "--", *paths)
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


def golden_commits(
    repo: Path,
    base: str,
    head: str,
    paths: tuple[str, ...] = GUARDED_PATHS,
    only: set[str] | None = None,
) -> list[GoldenCommit]:
    """The range's non-merge commits that touch `paths`, narrowed to `only` when given."""
    # rev-list is plumbing, so no log.* setting can change its output. Its
    # default history simplification skips side-branch commits whose guarded
    # edits a merge then discarded; those never reach the result.
    shas = _git(repo, "rev-list", "--no-merges", f"{base}..{head}", "--", *paths).split()
    commits = []
    for sha in shas:
        # One field per call: a commit message may hold any byte git accepts,
        # so no separator inside one combined format can be trusted.
        subject = _commit_field(repo, sha, "%s")
        message = _commit_field(repo, sha, "%B")
        trailers = _commit_field(
            repo, sha, f"%(trailers:key={TRAILER_KEY},valueonly,separator=%x1f)"
        )
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
            *paths,
        )
        wrote = _written(raw)
        if only is not None:
            wrote = {path: entry for path, entry in wrote.items() if path in only}
            if not wrote:
                continue
        rebaseline = tuple(value for value in trailers.split("\x1f") if value)
        commits.append(GoldenCommit(sha, subject, tuple(wrote), message, wrote, rebaseline))
    return commits


def _commit_field(repo: Path, sha: str, placeholder: str) -> str:
    """One pretty-format placeholder for one commit, without the newline rev-list adds."""
    out = _git(repo, "rev-list", "-1", "--no-commit-header", f"--format={placeholder}", sha)
    return out[:-1] if out.endswith("\n") else out


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

        frozen = changed_frozen_fixtures(repo, base_sha, tree)
        fixture_final: dict[str, str | None] = {}
        fixture_commits: list[GoldenCommit] = []
        named: set[str] = set()
        if frozen:
            entries = guarded_entries(repo, tree, FIXTURE_PATHS)
            fixture_final = {path: entries.get(path) for path in frozen}
            fixture_commits = golden_commits(
                repo, base_sha, head_sha, FIXTURE_PATHS, only=set(frozen)
            )
            record = record_at(repo, base_sha)
            named = {path for path in frozen if names_path(record, path)}
        fixtures_ok, fixture_message = fixture_verdict(
            frozen, fixture_commits, named, fixture_final
        )
    except RuntimeError as err:
        print(f"golden_guard: {err}", file=sys.stderr)
        return 2
    scope = f"merging {head} into {base} in {repo}"
    ok = ok and fixtures_ok
    print(f"golden_guard ({scope}): {'PASS' if ok else 'FAIL'}: {message}\n{fixture_message}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
