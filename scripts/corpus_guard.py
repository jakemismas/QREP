"""Keep private and unlicensed files out of this public repository.

The repo is public and force-push is banned, so one commit of a rights-unclean
photo, a commercial pattern or a private truth file stays public for good.
This check fails when:
  - a tracked path sits in a private tier: any `local-photos/` folder, or any
    folder named `private` under `corpus/` (for example `corpus/private/`);
  - a tracked file under `corpus/` has no row in `corpus/manifest.csv`, or its
    row's license is not one this repo accepts (ALLOWED_LICENSES). The rule
    denies by default, so a .txt, .json, .pdf, .dng or extensionless file
    needs a row just like a .jpg. Only the manifest itself, Markdown notes
    (.md), .gitkeep files and anything under `corpus/annotations/` (the folder
    for QREP's own hand-authored annotations) need none.
Rows name a file by its path relative to `corpus/` in the `file` column; a
bare file name also matches a file in a subfolder while no other checked file
shares the name. When the manifest has a `sha256` column, a row that fills it
licenses only a file with exactly that content, so a bare name cannot license
a different photo that happens to share it (phone names such as IMG_1234.jpg
repeat). Rows for one file that disagree fail too. Folder names compare
without case: on Windows checkouts Corpus/ and corpus/ are one folder. It
passes trivially while nothing under `corpus/` is tracked.

Usage (from any folder; the script checks the checkout it lives in):
    python scripts/corpus_guard.py                        # the index: stage first
    python scripts/corpus_guard.py --range <base> <head>  # CI and before a PR
With --range it checks the tree of <head> instead of the index (CI judges a
pull request it never checks out), plus every file that a commit in
<base>..<head> added, merge commits included, even if a later commit removed
it again: a merge keeps those commits in main's history, so a removal commit
does not undo a leak. Such a removed file passes when its newest row in the
range (in <head>'s manifest, then each earlier manifest of the range, then
<base>'s) licenses it, so a licensed image may still be moved or dropped.
Exit codes: 0 pass, 1 violations, 2 usage or git error.
"""

from __future__ import annotations

import csv
import hashlib
import io
import posixpath
import re
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

CORPUS_DIR = "corpus"
MANIFEST = "corpus/manifest.csv"
ANNOTATION_DIR = "annotations"
REQUIRED_COLUMNS = ("file", "license")
# The public licenses the corpus plan admits (museum open-access images).
# Anything else, including notes such as "UNVERIFIED" or "not cleared",
# marks a file that belongs in a private tier.
ALLOWED_LICENSES = ("CC0-1.0", "PDM-1.0")
NOTE_SUFFIXES = frozenset({".md"})
EXEMPT_NAMES = frozenset({".gitkeep"})
SHA256_HEX = re.compile(r"[0-9a-f]{64}")
HINT = (
    "Private photos and truth files stay local (corpus/private/, local-photos/); "
    f"only files licensed {' or '.join(ALLOWED_LICENSES)} in {MANIFEST} are committed. "
    "A file that reached a commit stays in history even after a removal commit, so "
    "do not merge such a branch: recreate it from origin/main without the file and "
    "report the leak."
)
REMOVED = " (committed in this range, then removed)"


@dataclass(frozen=True)
class Row:
    license: str
    sha256: str  # lowercase hex, or "" when the row records none


Rows = dict[str, list[Row]]


@dataclass(frozen=True)
class Lookup:
    row: Row | None = None  # the row that licenses the file
    problem: str | None = None  # why a row that names the file cannot license it
    other_content: bool = False  # the row's sha256 belongs to different content


def _folders(path: str) -> list[str]:
    return [part.lower() for part in path.split("/")[:-1]]


def is_private(path: str) -> bool:
    folders = _folders(path)
    if "local-photos" in folders:
        return True
    return bool(folders) and folders[0] == CORPUS_DIR and "private" in folders[1:]


def needs_license_row(path: str) -> bool:
    folders = _folders(path)
    if not folders or folders[0] != CORPUS_DIR or is_private(path):
        return False
    if path.lower() == MANIFEST or folders[1:2] == [ANNOTATION_DIR]:
        return False
    name = posixpath.basename(path).lower()
    return name not in EXEMPT_NAMES and posixpath.splitext(name)[1] not in NOTE_SUFFIXES


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
            license_id = (cells.get("license") or "").strip()
            sha256 = (cells.get("sha256") or "").strip().lower()
            rows.setdefault(name, []).append(Row(license_id, sha256))
    return rows


def _lookup(
    path: str,
    rows: Rows,
    name_is_unique: bool,
    digest: Callable[[str], str | None] | None,
) -> Lookup:
    relative, name = _corpus_relative(path), posixpath.basename(path)
    key = relative if relative in rows else name
    if key not in rows:
        return Lookup()
    candidates = list(dict.fromkeys(rows[key]))
    if len(candidates) > 1:
        listed = "; ".join(f"license '{r.license}', sha256 '{r.sha256}'" for r in candidates)
        return Lookup(problem=f"{len(rows[key])} manifest rows for '{key}' disagree ({listed})")
    row = candidates[0]
    by_name = key != relative
    if row.sha256:
        if not SHA256_HEX.fullmatch(row.sha256):
            return Lookup(problem=f"manifest row '{key}' has a malformed sha256 '{row.sha256}'")
        actual = digest(path) if digest else None
        if actual is None:
            return Lookup(problem=f"cannot read the file to check the sha256 in row '{key}'")
        if actual != row.sha256:
            fix = "the row describes another file" if by_name else "update the row"
            return Lookup(
                problem=(
                    f"manifest row '{key}' records sha256 {row.sha256[:12]}..., but this "
                    f"file's is {actual[:12]}...; {fix}"
                ),
                other_content=True,
            )
        return Lookup(row=row)
    if by_name and not name_is_unique:
        return Lookup(problem=f"manifest row '{name}' is ambiguous; name the file as {relative}")
    return Lookup(row=row)


def _license_problem(path: str, where: str, license_id: str) -> str | None:
    if not license_id:
        return f"{path}{where}: manifest row has an empty license"
    if license_id.lower() not in {lic.lower() for lic in ALLOWED_LICENSES}:
        return f"{path}{where}: license '{license_id}' is not one of {', '.join(ALLOWED_LICENSES)}"
    return None


def _unique_names(paths: list[str]) -> dict[str, bool]:
    counts: dict[str, int] = {}
    for path in paths:
        name = posixpath.basename(path)
        counts[name] = counts.get(name, 0) + 1
    return {name: count == 1 for name, count in counts.items()}


def violations(
    tracked: Iterable[str],
    manifest_text: str | None,
    added: Iterable[str] = (),
    *,
    history: Sequence[str | None] = (),
    digest: Callable[[str], str | None] | None = None,
) -> list[str]:
    """Problems with a tree and, for a change range, with the files it added.

    tracked: the files of the checked tree; manifest_text: that tree's
    manifest, or None. added: files that commits in the range added, tracked
    or not. history: earlier manifest texts of the range, newest first, read
    only for added files that are gone again. digest: the sha256 of a file's
    committed content (the tree's version, or the added version of a removed
    file), read only where a row records a sha256.
    """
    tracked = list(tracked)
    tracked_set = set(tracked)
    removed = [path for path in dict.fromkeys(added) if path not in tracked_set]
    problems = [f"{path}: private-tier path is tracked" for path in tracked if is_private(path)]
    problems += [
        f"{path}: private-tier path was committed in this range and stays in its history"
        for path in removed
        if is_private(path)
    ]
    files = [path for path in tracked if needs_license_row(path)]
    gone = [path for path in removed if needs_license_row(path)]
    if not files and not gone:
        return problems

    current: Rows | None = None
    if manifest_text is not None:
        missing = missing_columns(manifest_text)
        if missing:
            return problems + [f"{MANIFEST}: missing required column(s) {', '.join(missing)}"]
        current = parse_manifest(manifest_text)

    unique = _unique_names(files)
    for path in files:
        if current is None:
            problems.append(f"{path}: {MANIFEST} is missing")
            continue
        found = _lookup(path, current, unique[posixpath.basename(path)], digest)
        if found.problem:
            problems.append(f"{path}: {found.problem}")
        elif found.row is None:
            problems.append(f"{path}: no row in {MANIFEST}")
        else:
            problem = _license_problem(path, "", found.row.license)
            if problem:
                problems.append(problem)

    # Names are counted per group: a removed file never makes a tracked file's
    # bare-name row ambiguous, so a moved file keeps its row.
    unique_gone = _unique_names(gone)
    versions = [current] if current is not None else []
    versions += [rows for rows in (parse_manifest(t) for t in history if t is not None) if rows]
    for path in gone:
        problem = _removed_problem(path, versions, unique_gone[posixpath.basename(path)], digest)
        if problem:
            problems.append(problem)
    return problems


def _removed_problem(
    path: str,
    versions: list[Rows],
    name_is_unique: bool,
    digest: Callable[[str], str | None] | None,
) -> str | None:
    # The newest manifest whose rows name the file decides. A row whose sha256
    # belongs to other content (say the version a later commit re-encoded)
    # defers to older manifests.
    mismatch = None
    for rows in versions:
        found = _lookup(path, rows, name_is_unique, digest)
        if found.row is not None:
            return _license_problem(path, REMOVED, found.row.license)
        if found.other_content:
            mismatch = mismatch or found.problem
        elif found.problem:
            return f"{path}{REMOVED}: {found.problem}"
    if mismatch:
        return f"{path}{REMOVED}: {mismatch}"
    where = "at any point in the range" if versions else "(the range has no manifest)"
    return f"{path}{REMOVED}: no row in {MANIFEST} {where}"


def repo_root() -> Path:
    """The top of the checkout this script file lives in, wherever it runs from."""
    here = Path(__file__).resolve().parent
    result = _git(here, "rev-parse", "--show-toplevel")
    return Path(result.decode("utf-8").strip())


def _git(cwd: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {detail}")
    return result.stdout


def _nul_split(raw: bytes) -> list[str]:
    return [p for p in raw.decode("utf-8", "surrogateescape").split("\x00") if p]


def tracked_paths(repo: Path) -> list[str]:
    return _nul_split(_git(repo, "ls-files", "-z"))


def tree_paths(repo: Path, rev: str) -> list[str]:
    return _nul_split(_git(repo, "ls-tree", "-r", "--full-tree", "--name-only", "-z", rev))


def resolve_commit(repo: Path, rev: str) -> str:
    return _git(repo, "rev-parse", "--verify", f"{rev}^{{commit}}").decode().strip()


def added_paths(repo: Path, base: str, head: str) -> dict[str, str]:
    """Each path a commit in base..head added, with the newest commit that added it.

    No pathspec, so git simplifies no history away; --no-renames turns a
    rename into an addition of the new path. A merge commit is diffed against
    all its parents at once (dense-combined), which lists exactly the files
    the merge itself introduced and none that it only took from a parent.
    """
    raw = _git(
        repo,
        "-c",
        "log.showSignature=false",
        "log",
        "--diff-merges=dense-combined",
        "--no-renames",
        "--diff-filter=A",
        "--name-only",
        "--format=%x01%H",
        "-z",
        f"{base}..{head}",
    )
    added: dict[str, str] = {}
    for record in raw.decode("utf-8", "surrogateescape").split("\x01")[1:]:
        sha, *names = record.split("\x00")
        for name in names:
            path = name.lstrip("\n")
            if path:
                added.setdefault(path, sha.strip())
    return added


def manifest_paths(paths: Iterable[str]) -> list[str]:
    return [path for path in paths if path.lower() == MANIFEST]


def blob_text(repo: Path, spec: str) -> str:
    return _git(repo, "cat-file", "blob", spec).decode("utf-8-sig", "replace")


def manifest_history(repo: Path, base: str, head: str) -> list[str | None]:
    """The range's earlier manifest texts, newest first: those of the commits that
    changed it (side branches included, <head> left out), then <base>'s."""
    changed = _git(
        repo, "rev-list", "--full-history", "--topo-order", f"{base}..{head}", "--",
        f":(icase){MANIFEST}",
    ).decode().split()
    texts: list[str | None] = []
    for rev in [sha for sha in changed if sha != head] + [base]:
        found = manifest_paths(tree_paths(repo, rev))
        texts.append(blob_text(repo, f"{rev}:{found[0]}") if len(found) == 1 else None)
    return texts


class Source:
    """Where the checked files' content lives: the index, or a range's commits."""

    def __init__(self, repo: Path, base: str | None = None, head: str | None = None):
        self.repo = repo
        self.head = head
        if base is not None and head is not None:
            self.tracked = tree_paths(repo, head)
            self.added = added_paths(repo, base, head)
            self.history = manifest_history(repo, base, head)
        else:
            self.tracked = tracked_paths(repo)
            self.added = {}
            self.history = []
        self._tracked_set = set(self.tracked)
        self._digests: dict[str, str | None] = {}

    def blob(self, path: str) -> str | None:
        if path in self._tracked_set:
            return f"{self.head}:{path}" if self.head else f":{path}"
        return f"{self.added[path]}:{path}" if path in self.added else None

    def digest(self, path: str) -> str | None:
        if path not in self._digests:
            spec = self.blob(path)
            data = _git(self.repo, "cat-file", "blob", spec) if spec else None
            self._digests[path] = hashlib.sha256(data).hexdigest() if data is not None else None
        return self._digests[path]


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
        manifest = blob_text(repo, source.blob(manifests[0])) if len(manifests) == 1 else None
        problems = violations(
            source.tracked, manifest, source.added, history=source.history, digest=source.digest
        )
    except RuntimeError as err:
        print(f"corpus_guard: {err}", file=sys.stderr)
        return 2
    if len(manifests) > 1:
        problems.append(f"{', '.join(manifests)}: more than one manifest; keep only {MANIFEST}")
    scope = (
        f"tree of {argv[2]} and commits {argv[1]}..{argv[2]} in {repo}"
        if argv
        else f"index of {repo}"
    )
    if problems:
        print(f"corpus_guard ({scope}): FAIL ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  {problem}")
        print(HINT)
        return 1
    licensed = sum(1 for path in source.tracked if needs_license_row(path))
    print(
        f"corpus_guard ({scope}): PASS (no private-tier paths; {licensed} corpus file(s) "
        f"licensed; {len(source.added)} added path(s) checked)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
