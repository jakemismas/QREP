"""Keep private and unlicensed files out of this public repository.

The repo is public and force-push is banned, so one commit of a rights-unclean
photo, a commercial pattern or a private truth file stays public for good.
This check fails when:
  - a tracked path sits in a private tier: any `local-photos/` folder, or any
    folder named `private` under `corpus/` (for example `corpus/private/`);
  - a tracked file under `corpus/` has no row in `corpus/manifest.csv`, its
    row's license is not one this repo accepts (ALLOWED_LICENSES), or its row
    does not bind the file's bytes (below). The rule denies by default: any
    file type in any folder needs a row, an image under corpus/annotations/
    and a Markdown file under corpus/patterns/ included. Only these need
    none: the manifest itself, corpus/README.md, corpus/ATTRIBUTION.md,
    .gitkeep files, and QREP's own structured data (.json files under
    corpus/annotations/, corpus/schema/ or corpus/gold/, and
    corpus/holdout.json). All of them but the manifest must be UTF-8 text
    without NUL bytes, so an image cannot pass under such a name.
Rows name a file by its path relative to `corpus/` in the `file` column, or
by its bare file name. A row licenses only the bytes it binds. Its `sha256`
is the source image's hash (fetch verification and the holdout rule read it)
and every row that licenses a committed file needs one; the committed bytes
must match the row's `file_sha256` when the row fills it, else its `sha256`.
A downsized or re-encoded copy therefore keeps the source's sha256 and
records its own hash in file_sha256. A row without a sha256 licenses nothing:
a license that names only a path would cover whatever bytes sit there,
including a swapped-in photo and one that a later commit swapped out again,
and a bare name would cover a different photo that happens to share it
(phone names such as IMG_1234.jpg repeat). Rows for one file that disagree
fail too. Folder names compare without case: on Windows checkouts Corpus/
and corpus/ are one folder. It passes trivially while nothing under
`corpus/` is tracked.

Usage (from any folder; the script checks the checkout it lives in):
    python scripts/corpus_guard.py                             # the index: stage first
    python scripts/corpus_guard.py --range origin/main HEAD    # before every push; CI
With --range <base> <head> it checks the tree that merging <head> into <base>
produces (git merge-tree, as golden_guard does), so a branch that is behind
<base> is judged together with the files <base> gained, and nothing needs a
checkout. It also checks every version of every file that a commit in
<base>..<head> wrote, merge commits included, even when a later commit
replaced or removed it: merging keeps those commits in main's history, so a
fix-forward commit does not undo a leak. Such an earlier version passes when
its bytes equal a licensed file of the merge result (a move or a copy), or
when the newest manifest row that names it licenses it (the merge result's
manifest, then each earlier manifest of the range, then <base>'s; a row that
binds other bytes defers to older manifests), so a licensed image may still
be moved, re-encoded or dropped while each of its versions had a row that
bound its bytes.
Exit codes: 0 pass, 1 violations, 2 usage or git error (for example git older
than 2.38, or a <head> that conflicts with <base>, which leaves no merge
result to judge).
"""

from __future__ import annotations

import csv
import hashlib
import io
import posixpath
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

CORPUS_DIR = "corpus"
MANIFEST = "corpus/manifest.csv"
REQUIRED_COLUMNS = ("file", "license")
# The public licenses the corpus plan admits (museum open-access images).
# Anything else, including notes such as "UNVERIFIED" or "not cleared",
# marks a file that belongs in a private tier.
ALLOWED_LICENSES = ("CC0-1.0", "PDM-1.0")
# QREP's own files that need no row. Paths compare in lower case.
NOTES = frozenset({"corpus/readme.md", "corpus/attribution.md"})
PLACEHOLDERS = frozenset({".gitkeep"})
DATA_FOLDERS = frozenset({"annotations", "schema", "gold"})
DATA_FILES = frozenset({"corpus/holdout.json"})
DATA_SUFFIX = ".json"
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
BINARY = (
    "not UTF-8 text, but notes, .gitkeep files and QREP's .json data must be; an image or "
    "other binary file needs a licensed manifest row under a name of its own type"
)
POLICY = (
    "Private photos and truth files stay local (corpus/private/, local-photos/); only files "
    f"licensed {' or '.join(ALLOWED_LICENSES)} in {MANIFEST} are committed. If a listed file "
    "really is licensed that way and only its row is missing or wrong (no row, a license "
    "note, no sha256, a downsized copy without file_sha256), fix the row. When bytes do not "
    "match a row, never change the row's sha256 to theirs: sha256 is the source image's hash."
)
UNBOUND = (
    "records no sha256, so it licenses no particular bytes; a row needs its source image's "
    "sha256, and a downsized or re-encoded copy also needs its own hash in file_sha256"
)
INDEX_HINT = POLICY + (
    " Otherwise unstage the file (git restore --staged <path>) and keep it in a private tier. "
    "If a local commit already holds it, do not push: a pushed commit is public for good. "
    "Start a new branch from origin/main without the file and report to Jake."
)
RANGE_HINT = POLICY + (
    " Anything else listed here is a leak that no later commit can remove. If none of these "
    "commits is pushed, do not push: start a new branch from origin/main without the file. "
    "If one is pushed, its bytes are already public on the branch and on refs/pull/<n>/head, "
    "even after the branch is deleted or the pull request closes: stop pushing, do not open "
    "or update a pull request, and report to Jake with the commit SHAs (removal needs the "
    "branch deleted and GitHub Support to purge the pull request refs)."
)


@dataclass(frozen=True)
class Row:
    license: str
    sha256: str = ""  # the source image's hash, lowercase hex, or "" (licenses nothing)
    file_sha256: str = ""  # the committed copy's own hash when it differs, or ""

    def bound(self) -> tuple[str, str]:
        """The column, and the hash, that committed bytes must match."""
        return ("file_sha256", self.file_sha256) if self.file_sha256 else ("sha256", self.sha256)


Rows = dict[str, list[Row]]


@dataclass(frozen=True)
class Lookup:
    row: Row | None = None  # the row that licenses the file
    problem: str | None = None  # why a row that names the file cannot license it
    other_content: bool = False  # the row binds different content


@dataclass(frozen=True)
class Version:
    """One version of a file that a commit in the checked range wrote."""

    path: str
    key: str  # names the content for digest() and is_text(): a git object id
    commit: str = ""


def _folders(path: str) -> list[str]:
    return [part.lower() for part in path.split("/")[:-1]]


def is_private(path: str) -> bool:
    folders = _folders(path)
    if "local-photos" in folders:
        return True
    return bool(folders) and folders[0] == CORPUS_DIR and "private" in folders[1:]


def _exemption(path: str) -> str | None:
    """Why a corpus file needs no manifest row, or None when it needs one."""
    lowered = path.lower()
    if lowered == MANIFEST:
        return "manifest"
    if lowered in NOTES:
        return "note"
    if posixpath.basename(lowered) in PLACEHOLDERS:
        return "placeholder"
    folders = _folders(path)
    in_data_folder = len(folders) > 1 and folders[1] in DATA_FOLDERS
    if lowered in DATA_FILES or (in_data_folder and lowered.endswith(DATA_SUFFIX)):
        return "data"
    return None


def _in_corpus(path: str) -> bool:
    folders = _folders(path)
    return bool(folders) and folders[0] == CORPUS_DIR and not is_private(path)


def needs_license_row(path: str) -> bool:
    return _in_corpus(path) and _exemption(path) is None


def needs_text(path: str) -> bool:
    """Exempt files other than the manifest, which must be text to earn the exemption."""
    return _in_corpus(path) and _exemption(path) in {"note", "placeholder", "data"}


def is_text_bytes(data: bytes) -> bool:
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return False
    return True


def _corpus_relative(path: str) -> str:
    return path.split("/", 1)[1]


def _normalize_row_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    first, sep, rest = value.partition("/")
    return rest if sep and first.lower() == CORPUS_DIR else value


def _columns(reader: csv.DictReader) -> list[str]:
    return [(name or "").strip().lower() for name in reader.fieldnames or []]


def missing_columns(text: str) -> list[str]:
    columns = _columns(csv.DictReader(io.StringIO(text)))
    return [col for col in REQUIRED_COLUMNS if col not in columns]


def parse_manifest(text: str) -> Rows | None:
    """Rows by corpus-relative file name, or None when a required column is missing."""
    if missing_columns(text):
        return None
    rows: Rows = {}
    for record in csv.DictReader(io.StringIO(text)):
        cells = {(k or "").strip().lower(): v for k, v in record.items()}
        name = _normalize_row_path(cells.get("file") or "")
        if name:
            rows.setdefault(name, []).append(
                Row(
                    (cells.get("license") or "").strip(),
                    (cells.get("sha256") or "").strip().lower(),
                    (cells.get("file_sha256") or "").strip().lower(),
                )
            )
    return rows


def _describe(row: Row) -> str:
    text = f"license '{row.license}', sha256 '{row.sha256}'"
    return text + (f", file_sha256 '{row.file_sha256}'" if row.file_sha256 else "")


def _mismatch(key: str, column: str, expected: str, actual: str, by_name: bool) -> str:
    stated = (
        f"manifest row '{key}' records {column} {expected[:12]}..., but these bytes hash to "
        f"{actual[:12]}..."
    )
    if by_name:
        return f"{stated}; the row describes another file"
    if column == "file_sha256":
        return f"{stated}; they are not the copy that row licenses"
    return (
        f"{stated}; they are not the file that row licenses. A downsized or re-encoded copy "
        "of the row's source image keeps sha256 and records its own hash in a file_sha256 "
        "column; other bytes are the wrong file"
    )


def _lookup(path: str, rows: Rows, content_sha: Callable[[], str | None]) -> Lookup:
    relative, name = _corpus_relative(path), posixpath.basename(path)
    key = relative if relative in rows else name
    if key not in rows:
        return Lookup()
    candidates = list(dict.fromkeys(rows[key]))
    if len(candidates) > 1:
        listed = "; ".join(_describe(r) for r in candidates)
        return Lookup(problem=f"{len(rows[key])} manifest rows for '{key}' disagree ({listed})")
    row = candidates[0]
    for column, value in (("sha256", row.sha256), ("file_sha256", row.file_sha256)):
        if value and not SHA256_HEX.fullmatch(value):
            return Lookup(problem=f"manifest row '{key}' has a malformed {column} '{value}'")
    if not row.sha256:
        return Lookup(problem=f"manifest row '{key}' {UNBOUND}")
    column, expected = row.bound()
    actual = content_sha()
    if actual is None:
        return Lookup(problem=f"cannot read the file to check the {column} in row '{key}'")
    if actual != expected:
        problem = _mismatch(key, column, expected, actual, key != relative)
        return Lookup(problem=problem, other_content=True)
    return Lookup(row=row)


def _license_problem(path: str, where: str, license_id: str) -> str | None:
    if not license_id:
        return f"{path}{where}: manifest row has an empty license"
    if license_id.lower() not in {lic.lower() for lic in ALLOWED_LICENSES}:
        return f"{path}{where}: license '{license_id}' is not one of {', '.join(ALLOWED_LICENSES)}"
    return None


def _commit_note(version: Version) -> str:
    return f"; commit {version.commit[:12]}" if version.commit else ""


def _label(version: Version) -> str:
    return f" (committed in this range, then removed or replaced{_commit_note(version)})"


def violations(
    tracked: Iterable[str] | Mapping[str, str],
    manifest_text: str | None,
    added: Iterable[str | Version] = (),
    *,
    history: Sequence[str | None] = (),
    digest: Callable[[str], str | None] | None = None,
    is_text: Callable[[str], bool] | None = None,
) -> list[str]:
    """Problems with a tree and, for a change range, with every file version it wrote.

    tracked: the checked tree's files, as paths or as {path: content key};
    manifest_text: that tree's manifest, or None. added: the versions that
    commits in the range wrote (a bare path stands for the version under the
    path's own key). history: earlier manifest texts of the range, newest
    first, read only for versions the tree no longer holds. digest(key): the
    sha256 of that content, read where a row binds content or an earlier
    version may be a copy of a tracked file. is_text(key): whether that content
    is UTF-8 text without NUL bytes, read for files that need no row; None
    skips that check.
    """
    keys = dict(tracked) if isinstance(tracked, Mapping) else {path: path for path in tracked}
    earlier: list[Version] = []
    seen: set[tuple[str, str]] = set()
    for entry in added:
        version = entry if isinstance(entry, Version) else Version(entry, entry)
        # The tree's own version of a path is judged with the tree.
        if keys.get(version.path) == version.key or (version.path, version.key) in seen:
            continue
        seen.add((version.path, version.key))
        earlier.append(version)

    def sha(key: str) -> str | None:
        return digest(key) if digest else None

    problems = [f"{path}: private-tier path is tracked" for path in keys if is_private(path)]
    flagged = {path for path in keys if is_private(path)}
    for version in earlier:
        if is_private(version.path) and version.path not in flagged:
            flagged.add(version.path)
            problems.append(
                f"{version.path}: private-tier path was committed in this range"
                f"{_commit_note(version)} and stays in its history"
            )
    if is_text is not None:
        problems += [
            f"{path}: {BINARY}"
            for path, key in keys.items()
            if needs_text(path) and not is_text(key)
        ]
        problems += [
            f"{v.path}{_label(v)}: {BINARY}"
            for v in earlier
            if needs_text(v.path) and not is_text(v.key)
        ]

    files = [path for path in keys if needs_license_row(path)]
    gone = [version for version in earlier if needs_license_row(version.path)]
    if not files and not gone:
        return problems

    current: Rows | None = None
    if manifest_text is not None:
        missing = missing_columns(manifest_text)
        if missing:
            return problems + [f"{MANIFEST}: missing required column(s) {', '.join(missing)}"]
        current = parse_manifest(manifest_text)

    licensed: list[str] = []
    for path in files:
        if current is None:
            problems.append(f"{path}: {MANIFEST} is missing")
            continue
        found = _lookup(path, current, lambda key=keys[path]: sha(key))
        problem = found.problem
        if problem is None and found.row is None:
            problem = f"no row in {MANIFEST}"
        if problem:
            problems.append(f"{path}: {problem}")
            continue
        problem = _license_problem(path, "", found.row.license)
        if problem:
            problems.append(problem)
        else:
            licensed.append(path)

    row_sets = [current] if current is not None else []
    row_sets += [rows for rows in (parse_manifest(t) for t in history if t is not None) if rows]
    for version in gone:
        actual = sha(version.key)
        if actual is not None and any(sha(keys[path]) == actual for path in licensed):
            continue  # the same bytes as a licensed file of the tree: a move or a copy
        problem = _version_problem(version, row_sets, sha)
        if problem:
            problems.append(problem)
    return problems


def _version_problem(
    version: Version, row_sets: list[Rows], sha: Callable[[str], str | None]
) -> str | None:
    # row_sets runs newest first, and the newest manifest whose rows name the
    # file decides. A row that binds other content (say the version a later
    # commit re-encoded) defers to older manifests.
    label = _label(version)
    mismatch = None
    for rows in row_sets:
        found = _lookup(version.path, rows, lambda: sha(version.key))
        if found.row is not None:
            return _license_problem(version.path, label, found.row.license)
        if found.other_content:
            mismatch = mismatch or found.problem
        elif found.problem:
            return f"{version.path}{label}: {found.problem}"
    if mismatch:
        return f"{version.path}{label}: {mismatch}"
    where = "at any point in the range" if row_sets else "(the range has no manifest)"
    return f"{version.path}{label}: no row in {MANIFEST} {where}"


def repo_root() -> Path:
    """The top of the checkout this script file lives in, wherever it runs from."""
    here = Path(__file__).resolve().parent
    result = _git(here, "rev-parse", "--show-toplevel")
    return Path(result.decode("utf-8").strip())


def _run_git(cwd: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True)


def _git(cwd: Path, *args: str) -> bytes:
    result = _run_git(cwd, *args)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {detail}")
    return result.stdout


def _records(raw: bytes) -> list[str]:
    return [p for p in raw.decode("utf-8", "surrogateescape").split("\x00") if p]


def index_entries(repo: Path) -> dict[str, str]:
    """Each file of the index, with the object id of its staged content."""
    entries = {}
    for record in _records(_git(repo, "ls-files", "--stage", "-z")):
        meta, _, path = record.partition("\t")
        entries[path] = meta.split()[1]
    return entries


def tree_entries(repo: Path, tree: str) -> dict[str, str]:
    """Each file of a tree or commit, with its object id."""
    entries = {}
    for record in _records(_git(repo, "ls-tree", "-r", "--full-tree", "-z", tree)):
        meta, _, path = record.partition("\t")
        entries[path] = meta.split()[2]
    return entries


def resolve_commit(repo: Path, rev: str) -> str:
    return _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").decode().strip()


def merge_result(repo: Path, base: str, head: str) -> str:
    """The tree that merging head into base produces (git merge-tree, git 2.38+).

    The same computation as golden_guard.merge_result; each guard stays a
    standalone script.
    """
    result = _run_git(repo, "merge-tree", "--write-tree", "--no-messages", base, head)
    out = result.stdout.decode("utf-8", "surrogateescape")
    if result.returncode == 1:
        lines = out.splitlines()[1:]
        conflicted = sorted({line.split("\t", 1)[1] for line in lines if "\t" in line})
        raise RuntimeError(
            f"{head} does not merge cleanly into {base} (conflicts in "
            f"{', '.join(conflicted) or 'unlisted files'}), so there is no merge result to "
            "judge; merge the base into the branch, resolve the conflicts and push"
        )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(
            f"git merge-tree --write-tree failed (it needs git 2.38 or later): {detail}"
        )
    return out.splitlines()[0].strip()


def _relevant(path: str) -> bool:
    folders = _folders(path)
    return (bool(folders) and folders[0] == CORPUS_DIR) or is_private(path)


def range_versions(repo: Path, base: str, head: str) -> list[Version]:
    """Every corpus or private-tier file version that a commit in base..head wrote.

    Newest commit first. No pathspec, so git simplifies no history away;
    --no-renames turns a rename into a new path, and --root lists what a root
    commit added even where log.showRoot is false (an unrelated history merged
    into the branch starts with one). A merge commit is diffed against all its
    parents at once (dense-combined), which lists exactly the versions the
    merge itself produced and none that it only took from a parent. Each raw
    entry is ":<modes> <object ids> <status>" with one colon per parent; the
    last object id is the version the commit left, all zeros where it deleted
    the file.
    """
    raw = _git(
        repo,
        "-c",
        "log.showSignature=false",
        "log",
        "--root",
        "--diff-merges=dense-combined",
        "--no-renames",
        "--raw",
        "--no-abbrev",
        "--format=%x01%H",
        "-z",
        f"{base}..{head}",
    )
    versions: list[Version] = []
    for record in raw.decode("utf-8", "surrogateescape").split("\x01")[1:]:
        commit, _, rest = record.partition("\x00")
        fields = rest.split("\x00")
        i = 0
        while i < len(fields):
            meta = fields[i].lstrip("\n")
            if not meta.startswith(":"):
                i += 1
                continue
            path = fields[i + 1] if i + 1 < len(fields) else ""
            i += 2
            parents = len(meta) - len(meta.lstrip(":"))
            parts = meta[parents:].split()
            if len(parts) < 2 * parents + 3:
                raise RuntimeError(f"unexpected git log --raw entry in {commit}: {meta!r}")
            blob = parts[2 * parents + 1]
            if path and blob.strip("0") and _relevant(path):
                versions.append(Version(path, blob, commit.strip()))
    return versions


def manifest_paths(paths: Iterable[str]) -> list[str]:
    return [path for path in paths if path.lower() == MANIFEST]


def blob_text(repo: Path, object_id: str) -> str:
    return _git(repo, "cat-file", "blob", object_id).decode("utf-8-sig", "replace")


def manifest_history(repo: Path, base: str, head: str) -> list[str | None]:
    """The range's manifest texts, newest first: those of the commits that
    changed it (side branches included), then <base>'s."""
    changed = _git(
        repo, "rev-list", "--full-history", "--topo-order", f"{base}..{head}", "--",
        f":(icase){MANIFEST}",
    ).decode().split()
    texts: list[str | None] = []
    for rev in [*changed, base]:
        entries = tree_entries(repo, rev)
        found = manifest_paths(entries)
        texts.append(blob_text(repo, entries[found[0]]) if len(found) == 1 else None)
    return texts


class Source:
    """The checked tree with its content, and for a range every version it wrote."""

    def __init__(self, repo: Path, base: str | None = None, head: str | None = None):
        self.repo = repo
        self.tracked: dict[str, str] = {}
        self.versions: list[Version] = []
        self.history: list[str | None] = []
        if base is not None and head is not None:
            self.tracked = tree_entries(repo, merge_result(repo, base, head))
            self.versions = range_versions(repo, base, head)
            self.history = manifest_history(repo, base, head)
        else:
            self.tracked = index_entries(repo)
        self._facts: dict[str, tuple[str, bool] | None] = {}

    def _read(self, key: str) -> tuple[str, bool] | None:
        if key not in self._facts:
            result = _run_git(self.repo, "cat-file", "blob", key)
            if result.returncode != 0:
                self._facts[key] = None  # not a blob (a submodule entry) or unreadable
            else:
                data = result.stdout
                self._facts[key] = (hashlib.sha256(data).hexdigest(), is_text_bytes(data))
        return self._facts[key]

    def digest(self, key: str) -> str | None:
        facts = self._read(key)
        return facts[0] if facts else None

    def is_text(self, key: str) -> bool:
        facts = self._read(key)
        return bool(facts and facts[1])


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        # Paths may hold characters the console code page cannot print.
        sys.stdout.reconfigure(errors="backslashreplace")
    if argv and (len(argv) != 3 or argv[0] != "--range"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        repo = repo_root()
        if argv:
            source = Source(repo, resolve_commit(repo, argv[1]), resolve_commit(repo, argv[2]))
        else:
            source = Source(repo)
        manifests = manifest_paths(source.tracked)
        manifest = blob_text(repo, source.tracked[manifests[0]]) if len(manifests) == 1 else None
        problems = violations(
            source.tracked,
            manifest,
            source.versions,
            history=source.history,
            digest=source.digest,
            is_text=source.is_text,
        )
    except RuntimeError as err:
        print(f"corpus_guard: {err}", file=sys.stderr)
        return 2
    if len(manifests) > 1:
        problems.append(f"{', '.join(manifests)}: more than one manifest; keep only {MANIFEST}")
    scope = (
        f"merging {argv[2]} into {argv[1]}, and commits {argv[1]}..{argv[2]}, in {repo}"
        if argv
        else f"index of {repo}"
    )
    if problems:
        print(f"corpus_guard ({scope}): FAIL ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  {problem}")
        print(RANGE_HINT if argv else INDEX_HINT)
        return 1
    licensed = sum(1 for path in source.tracked if needs_license_row(path))
    print(
        f"corpus_guard ({scope}): PASS (no private-tier paths; {licensed} corpus file(s) "
        f"licensed; {len(source.versions)} committed version(s) checked)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
