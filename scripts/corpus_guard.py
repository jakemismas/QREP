"""Keep private and unlicensed files out of this public repository.

The repo is public and force-push is banned, so one commit of a rights-unclean
photo, a commercial pattern or a private truth file stays public for good.
This check fails when:
  - a tracked path sits in a private tier: any `local-photos/` folder, or any
    folder named `private` under `corpus/` (for example `corpus/private/`);
  - a tracked file under `corpus/` that is not an annotation (.csv, .json,
    .md, .txt, .yaml, .yml) has no row in `corpus/manifest.csv`, or its row's
    license is not one this repo accepts (ALLOWED_LICENSES). The rule denies
    by default, so a .jfif, .dng, .pdf or extensionless file needs a row just
    like a .jpg. Rows name the file by its path relative to `corpus/` in the
    `file` column; a bare file name also matches while it is unique.
Folder names compare without case: on Windows checkouts Corpus/ and corpus/
are one folder. It passes trivially while nothing under `corpus/` is tracked.

Usage (from any folder; the script checks the checkout it lives in):
    python scripts/corpus_guard.py                        # the index: stage first
    python scripts/corpus_guard.py --range <base> <head>  # CI: plus every commit
With --range it also checks every file that a non-merge commit in
<base>..<head> added, even if a later commit removed it again: a merge keeps
those commits in main's history, so a removal commit does not undo a leak.
Exit codes: 0 pass, 1 violations, 2 usage or git error.
"""

from __future__ import annotations

import csv
import io
import posixpath
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

CORPUS_DIR = "corpus"
MANIFEST = "corpus/manifest.csv"
REQUIRED_COLUMNS = ("file", "license")
# The public licenses the corpus plan admits (museum open-access images).
# Anything else, including notes such as "UNVERIFIED" or "not cleared",
# marks a file that belongs in a private tier.
ALLOWED_LICENSES = ("CC0-1.0", "PDM-1.0")
ANNOTATION_SUFFIXES = frozenset({".csv", ".json", ".md", ".txt", ".yaml", ".yml"})
EXEMPT_NAMES = frozenset({".gitkeep"})
HINT = (
    "Private photos and truth files stay local (corpus/private/, local-photos/); "
    f"only files licensed {' or '.join(ALLOWED_LICENSES)} in {MANIFEST} are committed. "
    "A file that reached a commit stays in history even after a removal commit, so "
    "do not merge such a branch: recreate it from origin/main without the file and "
    "report the leak."
)


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
    name = posixpath.basename(path).lower()
    return name not in EXEMPT_NAMES and posixpath.splitext(name)[1] not in ANNOTATION_SUFFIXES


def _corpus_relative(path: str) -> str:
    return path.split("/", 1)[1]


def _normalize_row_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    first, sep, rest = value.partition("/")
    return rest if sep and first.lower() == CORPUS_DIR else value


def violations(
    tracked: Iterable[str], manifest_text: str | None, added: Iterable[str] = ()
) -> list[str]:
    tracked = list(tracked)
    tracked_set = set(tracked)
    removed = [path for path in dict.fromkeys(added) if path not in tracked_set]
    problems = [f"{path}: private-tier path is tracked" for path in tracked if is_private(path)]
    problems += [
        f"{path}: private-tier path was committed in this range and stays in its history"
        for path in removed
        if is_private(path)
    ]
    files = [path for path in [*tracked, *removed] if needs_license_row(path)]
    if not files:
        return problems
    if manifest_text is None:
        return problems + [f"{path}: {MANIFEST} is missing" for path in files]

    reader = csv.DictReader(io.StringIO(manifest_text))
    columns = [(name or "").strip().lower() for name in reader.fieldnames or []]
    missing = [col for col in REQUIRED_COLUMNS if col not in columns]
    if missing:
        return problems + [f"{MANIFEST}: missing required column(s) {', '.join(missing)}"]

    licenses: dict[str, str] = {}
    for row in reader:
        cells = {(k or "").strip().lower(): (v or "") for k, v in row.items()}
        licenses[_normalize_row_path(cells["file"])] = cells["license"].strip()

    basenames: dict[str, int] = {}
    for path in files:
        name = posixpath.basename(path)
        basenames[name] = basenames.get(name, 0) + 1

    allowed = {lic.lower() for lic in ALLOWED_LICENSES}
    for path in files:
        where = "" if path in tracked_set else " (committed in this range, then removed)"
        relative = _corpus_relative(path)
        name = posixpath.basename(path)
        if relative in licenses:
            license_id = licenses[relative]
        elif name in licenses and basenames[name] == 1:
            license_id = licenses[name]
        elif name in licenses:
            problems.append(
                f"{path}{where}: manifest row '{name}' is ambiguous; name the file as {relative}"
            )
            continue
        else:
            problems.append(f"{path}{where}: no row in {MANIFEST}")
            continue
        if not license_id:
            problems.append(f"{path}{where}: manifest row has an empty license")
        elif license_id.lower() not in allowed:
            problems.append(
                f"{path}{where}: license '{license_id}' is not one of {', '.join(ALLOWED_LICENSES)}"
            )
    return problems


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


def added_paths(repo: Path, base: str, head: str) -> list[str]:
    # No pathspec, so git simplifies no history away; --no-renames turns a
    # rename into an addition of the new path.
    return _nul_split(
        _git(
            repo,
            "-c",
            "log.showSignature=false",
            "log",
            "--no-merges",
            "--no-renames",
            "--diff-filter=A",
            "--name-only",
            "--format=",
            "-z",
            f"{base}..{head}",
        )
    )


def staged_text(repo: Path, path: str) -> str:
    return _git(repo, "show", f":{path}").decode("utf-8-sig", "replace")


def main(argv: list[str]) -> int:
    if isinstance(sys.stdout, io.TextIOWrapper):
        # Paths may hold characters the console code page cannot print.
        sys.stdout.reconfigure(errors="backslashreplace")
    if argv and (len(argv) != 3 or argv[0] != "--range"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        repo = repo_root()
        tracked = tracked_paths(repo)
        added = added_paths(repo, argv[1], argv[2]) if argv else []
        manifests = [path for path in tracked if path.lower() == MANIFEST]
        manifest = staged_text(repo, manifests[0]) if len(manifests) == 1 else None
    except RuntimeError as err:
        print(f"corpus_guard: {err}", file=sys.stderr)
        return 2
    problems = violations(tracked, manifest, added)
    if len(manifests) > 1:
        problems.append(f"{', '.join(manifests)}: more than one manifest; keep only {MANIFEST}")
    scope = f"index of {repo}" + (f" and commits {argv[1]}..{argv[2]}" if argv else "")
    if problems:
        print(f"corpus_guard ({scope}): FAIL ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  {problem}")
        print(HINT)
        return 1
    licensed = sum(1 for path in tracked if needs_license_row(path))
    print(
        f"corpus_guard ({scope}): PASS (no private-tier paths; {licensed} corpus file(s) "
        f"licensed; {len(added)} added path(s) checked)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
