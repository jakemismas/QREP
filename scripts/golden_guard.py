"""Fail a change range that edits tests/golden/ without a [bless] commit.

Golden files are frozen output: CLAUDE.md lets them change only through
`pytest --bless` in a commit whose message contains [bless]. CI runs this on
every pull request so the rule holds even when nobody is watching.

Usage (from anywhere inside the checkout):
    python scripts/golden_guard.py <base> <head>
    python scripts/golden_guard.py origin/main HEAD   # before opening a PR

The diff is three-dot (what <head> changed since it forked from <base>), and
any commit in <base>..<head> whose message contains [bless] satisfies it.
Exit codes: 0 pass, 1 unblessed golden change, 2 git error (for example a
shallow clone that lacks <base>).
"""

from __future__ import annotations

import subprocess
import sys

GUARDED_PATHS = ("tests/golden/",)
BLESS_MARKER = "[bless]"


def verdict(changed: list[str], messages: list[str]) -> tuple[bool, str]:
    if not changed:
        return True, "no changes under " + ", ".join(GUARDED_PATHS)
    blessed = [m for m in messages if BLESS_MARKER in m]
    listing = "\n".join(f"  {path}" for path in changed)
    if blessed:
        subjects = "\n".join(f"  {m.strip().splitlines()[0]}" for m in blessed)
        return True, (
            f"{len(changed)} golden file(s) changed, with {len(blessed)} "
            f"{BLESS_MARKER} commit(s):\n{listing}\n{subjects}"
        )
    return False, (
        f"{len(changed)} golden file(s) changed and no commit in the range has "
        f"{BLESS_MARKER} in its message:\n{listing}\n"
        "Golden files change only through `pytest --bless` in a commit whose "
        f"message contains {BLESS_MARKER}. Drop the golden edit, or bless it in "
        "its own commit if the change is approved."
    )


def _git(*args: str) -> str:
    result = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def changed_guarded_files(base: str, head: str) -> list[str]:
    out = _git("diff", "--name-only", f"{base}...{head}", "--", *GUARDED_PATHS)
    return [line for line in out.splitlines() if line]


def commit_messages(base: str, head: str) -> list[str]:
    out = _git("log", "--format=%B%x00", f"{base}..{head}")
    return [m.strip() for m in out.split("\x00") if m.strip()]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    base, head = argv
    try:
        ok, message = verdict(changed_guarded_files(base, head), commit_messages(base, head))
    except RuntimeError as err:
        print(f"golden_guard: {err}", file=sys.stderr)
        return 2
    print(f"golden_guard ({base}...{head}): {'PASS' if ok else 'FAIL'}: {message}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
