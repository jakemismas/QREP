"""Keep private and unlicensed images out of this public repository.

The repo is public and force-push is banned, so one commit of a rights-unclean
photo, a commercial pattern or a private truth file stays public for good.
This check fails when:
  - a tracked path sits in a private tier: any `local-photos/` folder, or any
    folder named `private` under `corpus/` (for example `corpus/private/`);
  - a committed image under `corpus/` has no row in `corpus/manifest.csv`, or
    its row has an empty license. Rows name the image by its path relative to
    `corpus/` in the `file` column; a bare file name also matches while it is
    unique among the committed corpus images.
It passes trivially while nothing under `corpus/` is tracked.

It reads the git index (what the next commit contains), so stage first:
    python scripts/corpus_guard.py
Exit codes: 0 pass, 1 violations, 2 git error.
"""

from __future__ import annotations

import csv
import io
import posixpath
import subprocess
import sys

CORPUS_DIR = "corpus/"
MANIFEST = "corpus/manifest.csv"
REQUIRED_COLUMNS = ("file", "license")
IMAGE_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".heic", ".heif", ".avif"}
)


def is_private(path: str) -> bool:
    folders = [part.lower() for part in path.split("/")[:-1]]
    if "local-photos" in folders:
        return True
    return bool(folders) and folders[0] == "corpus" and "private" in folders[1:]


def is_corpus_image(path: str) -> bool:
    return path.startswith(CORPUS_DIR) and posixpath.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def _normalize_row_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value.removeprefix(CORPUS_DIR)


def violations(tracked: list[str], manifest_text: str | None) -> list[str]:
    problems = [f"{path}: private-tier path is tracked" for path in tracked if is_private(path)]
    images = [path for path in tracked if is_corpus_image(path) and not is_private(path)]
    if not images:
        return problems
    if manifest_text is None:
        return problems + [f"{path}: {MANIFEST} is missing" for path in images]

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
    for path in images:
        name = posixpath.basename(path)
        basenames[name] = basenames.get(name, 0) + 1

    for path in images:
        relative = path.removeprefix(CORPUS_DIR)
        name = posixpath.basename(path)
        if relative in licenses:
            license_id = licenses[relative]
        elif name in licenses and basenames[name] == 1:
            license_id = licenses[name]
        elif name in licenses:
            problems.append(
                f"{path}: manifest row '{name}' is ambiguous; name the image as {relative}"
            )
            continue
        else:
            problems.append(f"{path}: no row in {MANIFEST}")
            continue
        if not license_id:
            problems.append(f"{path}: manifest row has an empty license")
    return problems


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], capture_output=True)


def tracked_paths() -> list[str]:
    result = _git("ls-files", "-z")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return [p for p in result.stdout.decode("utf-8").split("\x00") if p]


def staged_manifest() -> str | None:
    result = _git("show", f":{MANIFEST}")
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8-sig")


def main() -> int:
    try:
        tracked = tracked_paths()
    except RuntimeError as err:
        print(f"corpus_guard: git ls-files failed: {err}", file=sys.stderr)
        return 2
    manifest = staged_manifest() if MANIFEST in tracked else None
    problems = violations(tracked, manifest)
    if problems:
        print(f"corpus_guard: FAIL ({len(problems)} problem(s)):")
        for problem in problems:
            print(f"  {problem}")
        return 1
    images = sum(1 for path in tracked if is_corpus_image(path))
    print(f"corpus_guard: PASS (no private-tier paths; {images} corpus image(s) licensed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
