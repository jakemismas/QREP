"""The CI guards in scripts/: golden_guard (tests/golden changes need a
[bless] commit) and corpus_guard (no tracked private-tier paths; every
committed corpus image has a licensed row in corpus/manifest.csv).

Expected outcomes come from the rules the scripts enforce (CLAUDE.md's bless
protocol and the documented corpus contract), never from observed output.
The git-backed cases build throwaway repositories under tmp_path and skip
under Pyodide, which cannot spawn git.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


golden_guard = _load("golden_guard")
corpus_guard = _load("corpus_guard")

needs_git = pytest.mark.skipif(
    sys.platform == "emscripten" or shutil.which("git") is None,
    reason="needs a git executable and subprocesses",
)

LICENSED = "file,source,license\nimages/a.jpg,met,CC0-1.0\n"


# corpus_guard rules


def test_corpus_guard_passes_without_a_corpus():
    assert corpus_guard.violations(["README.md", "qrep/__init__.py"], None) == []


def test_tracked_local_photos_fail():
    problems = corpus_guard.violations(["local-photos/IMG_4461.png"], None)
    assert len(problems) == 1
    assert "local-photos/IMG_4461.png" in problems[0]


def test_private_folders_under_corpus_fail_at_any_depth():
    tracked = ["corpus/private/shop.jpg", "corpus/truth/private/shop.json"]
    problems = corpus_guard.violations(tracked, None)
    assert len(problems) == 2
    assert all("private-tier" in p for p in problems)


def test_a_file_merely_named_private_is_not_a_tier():
    assert corpus_guard.violations(["corpus/notes/private.md"], None) == []


def test_licensed_corpus_image_passes():
    tracked = ["corpus/manifest.csv", "corpus/images/a.jpg"]
    assert corpus_guard.violations(tracked, LICENSED) == []


def test_corpus_image_without_a_row_fails():
    tracked = ["corpus/manifest.csv", "corpus/images/a.jpg", "corpus/images/b.png"]
    problems = corpus_guard.violations(tracked, LICENSED)
    assert problems == ["corpus/images/b.png: no row in corpus/manifest.csv"]


def test_uppercase_extension_still_counts_as_an_image():
    tracked = ["corpus/manifest.csv", "corpus/images/a.jpg", "corpus/images/C.JPG"]
    assert len(corpus_guard.violations(tracked, LICENSED)) == 1


def test_empty_license_fails():
    manifest = "file,license\nimages/a.jpg,   \n"
    problems = corpus_guard.violations(["corpus/manifest.csv", "corpus/images/a.jpg"], manifest)
    assert problems == ["corpus/images/a.jpg: manifest row has an empty license"]


def test_missing_manifest_fails_every_image():
    problems = corpus_guard.violations(["corpus/images/a.jpg", "corpus/images/b.jpg"], None)
    assert len(problems) == 2
    assert all("corpus/manifest.csv is missing" in p for p in problems)


def test_manifest_without_license_column_fails():
    problems = corpus_guard.violations(
        ["corpus/manifest.csv", "corpus/images/a.jpg"], "file,source\nimages/a.jpg,met\n"
    )
    assert problems == ["corpus/manifest.csv: missing required column(s) license"]


def test_bare_file_name_matches_while_unique():
    manifest = "file,license\na.jpg,CC0-1.0\n"
    assert corpus_guard.violations(["corpus/images/a.jpg"], manifest) == []


def test_bare_file_name_shared_by_two_images_is_ambiguous():
    manifest = "file,license\na.jpg,CC0-1.0\n"
    problems = corpus_guard.violations(["corpus/sq/a.jpg", "corpus/neg/a.jpg"], manifest)
    assert len(problems) == 2
    assert all("ambiguous" in p for p in problems)


def test_row_paths_tolerate_backslashes_and_a_corpus_prefix():
    manifest = "file,license\ncorpus\\images\\a.jpg,CC0-1.0\n"
    assert corpus_guard.violations(["corpus/images/a.jpg"], manifest) == []


def test_non_image_corpus_files_need_no_row():
    assert corpus_guard.violations(["corpus/annotations/a.json", "corpus/README.md"], None) == []


# golden_guard rules


def test_no_golden_change_passes_without_bless():
    ok, _ = golden_guard.verdict([], ["refactor exporter"])
    assert ok


def test_golden_change_without_bless_fails():
    ok, message = golden_guard.verdict(["tests/golden/top.svg"], ["tweak exporter"])
    assert not ok
    assert "tests/golden/top.svg" in message


def test_golden_change_with_a_bless_commit_passes():
    ok, _ = golden_guard.verdict(
        ["tests/golden/top.svg"], ["tweak exporter", "Re-render top diagram [bless]"]
    )
    assert ok


def test_bless_marker_in_the_message_body_counts():
    ok, _ = golden_guard.verdict(["tests/golden/top.svg"], ["Re-render\n\n[bless] approved on #1"])
    assert ok


# git-backed runs of the real scripts


def _git_env() -> dict[str, str]:
    env = dict(os.environ)
    configured = subprocess.run(["git", "config", "user.email"], capture_output=True, text=True)
    if not configured.stdout.strip():
        env.update(
            GIT_AUTHOR_NAME="qrep tests",
            GIT_AUTHOR_EMAIL="tests@qrep.invalid",
            GIT_COMMITTER_NAME="qrep tests",
            GIT_COMMITTER_EMAIL="tests@qrep.invalid",
        )
    return env


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, env=_git_env(), capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str, files: dict[str, str]) -> str:
    for rel, text in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        _git(repo, "add", rel)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _run(repo: Path, script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        cwd=repo,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _commit(tmp_path, "base", {"tests/golden/cut.csv": "a,b\n", "README.md": "x\n"})
    return tmp_path


@needs_git
def test_golden_guard_script_blocks_an_unblessed_edit_until_a_bless_commit(repo):
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "work")
    head = _commit(repo, "edit exporter", {"tests/golden/cut.csv": "a,b,c\n"})
    blocked = _run(repo, "golden_guard.py", base, head)
    assert blocked.returncode == 1, blocked.stdout + blocked.stderr

    head = _commit(repo, "Bless the new cut list [bless]", {"notes.txt": "approved\n"})
    assert _run(repo, "golden_guard.py", base, head).returncode == 0


@needs_git
def test_golden_guard_script_ignores_golden_changes_that_landed_on_the_base(repo):
    fork = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "work")
    head = _commit(repo, "docs only", {"README.md": "y\n"})
    _git(repo, "checkout", "-q", "main")
    base = _commit(repo, "Bless upstream [bless]", {"tests/golden/cut.csv": "z\n"})
    assert fork != base
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


@needs_git
def test_golden_guard_script_reports_git_errors_as_exit_2(repo):
    assert _run(repo, "golden_guard.py", "no-such-ref", "HEAD").returncode == 2


@needs_git
def test_corpus_guard_script_fails_on_a_tracked_private_tier(repo):
    assert _run(repo, "corpus_guard.py").returncode == 0
    _commit(repo, "oops", {"corpus/private/shop.jpg": "not really a jpeg\n"})
    result = _run(repo, "corpus_guard.py")
    assert result.returncode == 1
    assert "corpus/private/shop.jpg" in result.stdout
