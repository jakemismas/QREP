"""The CI guards in scripts/: golden_guard (every commit that edits
tests/golden is a [bless] commit) and corpus_guard (no private-tier paths
and no unlicensed corpus files, in the tree or anywhere in a change range).

Expected outcomes come from the rules the scripts enforce (CLAUDE.md's bless
protocol and the documented corpus contract), never from observed output.
The git-backed cases build throwaway repositories under tmp_path, copy the
scripts into them (each script checks the checkout it lives in), and skip
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
GUARDS = ("golden_guard.py", "corpus_guard.py")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    # dataclasses resolve the module through sys.modules while the class body runs.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


golden_guard = _load("golden_guard")
corpus_guard = _load("corpus_guard")

needs_git = pytest.mark.skipif(
    sys.platform == "emscripten" or shutil.which("git") is None,
    reason="needs a git executable and subprocesses",
)

LICENSED = "file,source,license\nimages/a.jpg,met,CC0-1.0\n"
TOP = "tests/golden/top.svg"
CUT = "tests/golden/cut.csv"


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


@pytest.mark.parametrize(
    "license_text",
    [
        "not cleared",
        "UNVERIFIED",
        "private reference only - do not publish",
        "TODO",
        "-",
        "CC0-1.0 (image terms UNVERIFIED)",
    ],
)
def test_a_license_outside_the_allowlist_fails(license_text):
    manifest = f"file,license\nimages/a.jpg,{license_text}\n"
    problems = corpus_guard.violations(["corpus/manifest.csv", "corpus/images/a.jpg"], manifest)
    assert len(problems) == 1
    assert "corpus/images/a.jpg" in problems[0]
    assert "is not one of" in problems[0]


@pytest.mark.parametrize("license_text", ["CC0-1.0", "cc0-1.0", "PDM-1.0", " CC0-1.0 "])
def test_allowlisted_licenses_pass_in_any_case(license_text):
    manifest = f"file,license\nimages/a.jpg,{license_text}\n"
    assert corpus_guard.violations(["corpus/images/a.jpg"], manifest) == []


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


def test_a_gitkeep_needs_no_row():
    assert corpus_guard.violations(["corpus/images/.gitkeep"], None) == []


def test_a_capitalized_corpus_folder_is_still_the_corpus():
    # Windows checkouts treat Corpus/ and corpus/ as the same folder.
    problems = corpus_guard.violations(["Corpus/images/shop.jpg"], None)
    assert problems == ["Corpus/images/shop.jpg: corpus/manifest.csv is missing"]
    assert corpus_guard.violations(["Corpus/images/a.jpg"], LICENSED) == []


@pytest.mark.parametrize(
    "path",
    [
        "corpus/images/shop.jfif",
        "corpus/images/shop.jpe",
        "corpus/phone/IMG_0001.DNG",
        "corpus/patterns/storebought.pdf",
        "corpus/patterns/pattern.svg",
        "corpus/screens.zip",
        "corpus/images/no_extension",
    ],
)
def test_every_corpus_file_that_is_not_an_annotation_needs_a_row(path):
    problems = corpus_guard.violations([path], None)
    assert problems == [f"{path}: corpus/manifest.csv is missing"]


def test_a_private_path_committed_and_removed_in_the_range_fails():
    problems = corpus_guard.violations(["README.md"], None, added=["local-photos/IMG_4461.png"])
    assert len(problems) == 1
    assert "local-photos/IMG_4461.png" in problems[0]
    assert "history" in problems[0]


def test_an_unlicensed_file_committed_and_removed_in_the_range_fails():
    tracked = ["corpus/manifest.csv", "corpus/images/a.jpg"]
    problems = corpus_guard.violations(tracked, LICENSED, added=["corpus/images/b.png"])
    assert len(problems) == 1
    assert problems[0].startswith("corpus/images/b.png")
    assert "no row in corpus/manifest.csv" in problems[0]


def test_a_licensed_file_committed_and_removed_in_the_range_passes():
    tracked = ["corpus/manifest.csv"]
    assert corpus_guard.violations(tracked, LICENSED, added=["corpus/images/a.jpg"]) == []


def test_a_path_both_tracked_and_added_is_reported_once():
    path = "corpus/private/a.jpg"
    assert len(corpus_guard.violations([path], None, added=[path])) == 1


# golden_guard rules


def _commit_record(subject: str, *files: str) -> golden_guard.GoldenCommit:
    return golden_guard.GoldenCommit("0123456789ab" + "0" * 28, subject, files)


def test_no_golden_change_passes():
    ok, _ = golden_guard.verdict([], [])
    assert ok


def test_golden_change_without_bless_fails():
    ok, message = golden_guard.verdict([TOP], [_commit_record("Tweak exporter output", TOP)])
    assert not ok
    assert TOP in message


def test_golden_change_in_a_bless_commit_passes():
    ok, _ = golden_guard.verdict([TOP], [_commit_record("Re-render top diagram [bless]", TOP)])
    assert ok


def test_a_bless_commit_does_not_excuse_another_commits_golden_edit():
    commits = [
        _commit_record("Refactor exporter", CUT),
        _commit_record("Re-render top diagram [bless]", TOP),
    ]
    ok, message = golden_guard.verdict([CUT, TOP], commits)
    assert not ok
    assert "Refactor exporter" in message


def test_a_golden_change_no_commit_explains_fails():
    # Only a merge commit can change a file without a non-merge commit doing so.
    ok, message = golden_guard.verdict([TOP], [])
    assert not ok
    assert "merge commit" in message


@pytest.mark.parametrize(
    ("subject", "blessed"),
    [
        ("[bless] S4: bless top-diagram SVG golden", True),
        ("S0: [bless] degraded photoreal tier", True),
        ("Re-render top diagram", False),
        ('Revert "Re-render top diagram [bless]"', False),
        ('Reapply "Re-render top diagram [bless]"', False),
        ('Revert "Re-render top diagram [bless]" [bless]', True),
    ],
)
def test_only_a_subject_of_its_own_marks_a_bless(subject, blessed):
    assert golden_guard.is_bless_subject(subject) is blessed


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


def _commit(repo: Path, message: str, files: dict[str, str] | None = None) -> str:
    for rel, text in (files or {}).items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        _git(repo, "add", rel)
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _run(
    repo: Path, script: str, *args: str, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / script), *args],
        cwd=cwd or repo,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _commit(root, "base", {CUT: "a,b\n", "README.md": "x\n"})
    # Untracked copies: each guard checks the checkout its own file sits in.
    (root / "scripts").mkdir()
    for name in GUARDS:
        shutil.copy(SCRIPTS / name, root / "scripts" / name)
    return root


def _start_branch(repo: Path) -> str:
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "work")
    return base


@needs_git
def test_golden_guard_script_passes_a_golden_edit_made_in_a_bless_commit(repo):
    base = _start_branch(repo)
    head = _commit(repo, "Bless the new cut list [bless]", {CUT: "a,b,c\n"})
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


@needs_git
def test_golden_guard_script_fails_an_unblessed_edit_even_after_a_bless_commit(repo):
    base = _start_branch(repo)
    head = _commit(repo, "Edit exporter", {CUT: "a,b,c\n"})
    blocked = _run(repo, "golden_guard.py", base, head)
    assert blocked.returncode == 1, blocked.stdout + blocked.stderr

    # A [bless] commit that touches no golden file cannot excuse that edit.
    head = _commit(repo, "Bless the new cut list [bless]", {"notes.txt": "approved\n"})
    still_blocked = _run(repo, "golden_guard.py", base, head)
    assert still_blocked.returncode == 1, still_blocked.stdout + still_blocked.stderr
    assert "Edit exporter" in still_blocked.stdout


@needs_git
def test_golden_guard_script_ignores_a_marker_that_only_a_body_mentions(repo):
    base = _start_branch(repo)
    _commit(
        repo, "Re-render cut list\n\nThe golden lands in the next [bless] commit.", {CUT: "z\n"}
    )
    head = _commit(repo, "Tidy notes\n\nOutput is unchanged, so this needs no [bless] commit.")
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 1, result.stdout + result.stderr


@needs_git
def test_golden_guard_script_fails_a_revert_of_a_bless(repo):
    _commit(repo, "Re-render cut list [bless]", {CUT: "a,b,c\n"})
    base = _start_branch(repo)
    _git(repo, "revert", "--no-edit", "HEAD")
    head = _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "log", "-1", "--format=%s").startswith('Revert "')
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 1, result.stdout + result.stderr


@needs_git
def test_golden_guard_script_fails_a_golden_edit_made_inside_a_merge(repo):
    _start_branch(repo)
    _commit(repo, "Docs", {"README.md": "y\n"})
    _git(repo, "checkout", "-q", "main")
    base = _commit(repo, "Other work", {"other.txt": "o\n"})
    _git(repo, "checkout", "-q", "work")
    _git(repo, "merge", "-q", "--no-ff", "--no-commit", "main")
    (repo / CUT).write_text("edited in the merge\n", encoding="utf-8")
    _git(repo, "add", CUT)
    _git(repo, "commit", "-q", "-m", "Merge main [bless]")
    head = _git(repo, "rev-parse", "HEAD")
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "merge commit" in result.stdout


@needs_git
def test_golden_guard_script_ignores_golden_changes_that_landed_on_the_base(repo):
    fork = _start_branch(repo)
    head = _commit(repo, "docs only", {"README.md": "y\n"})
    _git(repo, "checkout", "-q", "main")
    base = _commit(repo, "Bless upstream [bless]", {CUT: "z\n"})
    assert fork != base
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


@needs_git
def test_golden_guard_script_checks_its_own_checkout_from_a_subfolder(repo):
    base = _start_branch(repo)
    head = _commit(repo, "Edit exporter", {CUT: "a,b,c\n"})
    subfolder = repo / "web"
    subfolder.mkdir()
    result = _run(repo, "golden_guard.py", base, head, cwd=subfolder)
    assert result.returncode == 1, result.stdout + result.stderr


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


@needs_git
def test_corpus_guard_range_catches_a_private_file_that_a_later_commit_removed(repo):
    base = _start_branch(repo)
    _commit(repo, "Add smoke photo", {"local-photos/IMG_4461.png": "not really a png\n"})
    _git(repo, "rm", "-q", "local-photos/IMG_4461.png")
    head = _commit(repo, "Remove the smoke photo again")
    # The final tree is clean, which is why CI also passes the PR range.
    assert _run(repo, "corpus_guard.py").returncode == 0
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "local-photos/IMG_4461.png" in result.stdout


@needs_git
def test_corpus_guard_script_checks_its_own_checkout_from_anywhere(repo, tmp_path):
    _commit(repo, "oops", {"corpus/private/shop.jpg": "not really a jpeg\n"})
    subfolder = repo / "web"
    subfolder.mkdir()
    assert _run(repo, "corpus_guard.py", cwd=subfolder).returncode == 1
    # A clean sibling worktree as the current folder, the way worker tabs run
    # from the main checkout, must not stand in for the script's checkout.
    sibling = tmp_path / "sibling"
    _git(repo, "worktree", "add", "-q", "-b", "clean", str(sibling), "HEAD~1")
    assert _run(repo, "corpus_guard.py", cwd=sibling).returncode == 1


@needs_git
def test_corpus_guard_script_rejects_unknown_arguments(repo):
    assert _run(repo, "corpus_guard.py", "--range", "HEAD").returncode == 2
