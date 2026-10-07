"""The CI guards in scripts/: golden_guard (every commit that edits
tests/golden is a [bless] commit, and a merge leaves no golden content that
no commit wrote) and corpus_guard (no private-tier paths and no unlicensed
corpus files, in the index, in a range's merge result, or in any file version
the range wrote), plus the shape of the workflow that runs them.

Expected outcomes come from the rules the scripts enforce (CLAUDE.md's bless
protocol and the documented corpus contract), never from observed output.
The git-backed cases build throwaway repositories under tmp_path, copy the
scripts into them (each script checks the checkout it lives in), and skip
under Pyodide, which cannot spawn git.
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
import re
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
    # Not a private tier; it needs a row only because notes other than
    # corpus/README.md and corpus/ATTRIBUTION.md are content like any file.
    problems = corpus_guard.violations(["corpus/notes/private.md"], None)
    assert problems == ["corpus/notes/private.md: corpus/manifest.csv is missing"]


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


@pytest.mark.parametrize(
    "path",
    [
        "corpus/patterns/rk_kona_cubic.txt",
        "corpus/truth/IMG_4461.json",
        "corpus/eval/results.csv",
        "corpus/notes/settings.yaml",
    ],
)
def test_text_files_outside_the_annotation_folder_need_a_row(path):
    # A commercial pattern's text or a private truth file is still content.
    assert corpus_guard.violations([path], None) == [f"{path}: corpus/manifest.csv is missing"]


def test_qrep_authored_corpus_files_the_plan_names_need_no_row():
    # The sprint plan's D3a and D3b own these; none is a corpus image.
    tracked = [
        "corpus/manifest.csv",
        "corpus/README.md",
        "corpus/ATTRIBUTION.md",
        "corpus/schema/annotation.schema.json",
        "corpus/annotations/truth/met-1.json",
        "corpus/annotations/met-1.proposed-a.json",
        "corpus/gold/met-1.json",
        "corpus/holdout.json",
        "corpus/images/.gitkeep",
    ]
    assert corpus_guard.violations(tracked, "file,license\n") == []


@pytest.mark.parametrize(
    "path",
    [
        "corpus/annotations/IMG_4461_corners_overlay.png",
        "corpus/annotations/truth/IMG_4462.jpg",
        "corpus/Annotations/shop/screenshot.jpeg",
        "corpus/annotations/notes.txt",
        "corpus/annotations/met-1.md",
        "corpus/patterns/rk_kona_cubic.md",
        "corpus/museum/README.md",
        "corpus/schema/annotation.schema.yaml",
        "corpus/gold/met-1.png",
        "corpus/holdout.csv",
    ],
)
def test_only_qrep_json_and_the_named_notes_skip_the_row(path):
    # An overlay saved beside its sidecar, or a pattern transcribed into a
    # note, is content: the folder or the extension alone does not exempt it.
    problems = corpus_guard.violations(["corpus/manifest.csv", path], "file,license\n")
    assert problems == [f"{path}: no row in corpus/manifest.csv"]


def test_files_that_skip_the_row_must_be_text():
    tracked = ["corpus/annotations/met-1.json", "corpus/README.md", "corpus/images/.gitkeep"]
    binary = {"corpus/annotations/met-1.json"}
    problems = corpus_guard.violations(tracked, None, is_text=lambda key: key not in binary)
    assert problems == [f"corpus/annotations/met-1.json: {corpus_guard.BINARY}"]


def test_rows_for_one_file_that_disagree_fail():
    manifest = "file,license\nimages/a.jpg,not cleared\nimages/a.jpg,CC0-1.0\n"
    problems = corpus_guard.violations(["corpus/images/a.jpg"], manifest)
    assert len(problems) == 1
    assert problems[0].startswith("corpus/images/a.jpg: 2 manifest rows")
    assert "disagree" in problems[0]


def test_identical_duplicate_rows_pass():
    manifest = "file,license\nimages/a.jpg,CC0-1.0\nimages/a.jpg,CC0-1.0\n"
    assert corpus_guard.violations(["corpus/images/a.jpg"], manifest) == []


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


CONTENT = {"corpus/jake/IMG_1234.jpg": "jake's cc0 photo", "corpus/mom/IMG_1234.jpg": "mom's"}


def _digest(path: str) -> str | None:
    return _sha(CONTENT[path]) if path in CONTENT else None


JAKE_SHA = _sha(CONTENT["corpus/jake/IMG_1234.jpg"])
JAKE_ROW = f"file,license,sha256\nIMG_1234.jpg,CC0-1.0,{JAKE_SHA}\n"


def test_a_bare_name_row_licenses_only_the_content_its_sha256_names():
    manifest = JAKE_ROW
    assert corpus_guard.violations(["corpus/jake/IMG_1234.jpg"], manifest, digest=_digest) == []
    problems = corpus_guard.violations(["corpus/mom/IMG_1234.jpg"], manifest, digest=_digest)
    assert len(problems) == 1
    assert problems[0].startswith("corpus/mom/IMG_1234.jpg: manifest row 'IMG_1234.jpg'")
    assert "another file" in problems[0]


def test_a_sha256_row_needs_no_unique_name():
    # Content, not the name, says which file the row means.
    problems = corpus_guard.violations(sorted(CONTENT), JAKE_ROW, digest=_digest)
    assert len(problems) == 1
    assert problems[0].startswith("corpus/mom/IMG_1234.jpg")


def test_a_path_row_whose_sha256_differs_from_the_file_fails():
    manifest = f"file,license,sha256\nmom/IMG_1234.jpg,CC0-1.0,{_sha('other bytes')}\n"
    problems = corpus_guard.violations(["corpus/mom/IMG_1234.jpg"], manifest, digest=_digest)
    assert len(problems) == 1
    assert "not the file that row licenses" in problems[0]
    # sha256 is the source image's hash; the guard must never advise
    # overwriting it with the hash of whatever bytes were committed.
    assert "file_sha256" in problems[0]
    assert "update the row" not in problems[0]


SOURCE_SHA = _sha("full-size source bytes")
DOWNSIZED = {"corpus/images/met-1.jpg": "downsized 800 px bytes"}


def test_file_sha256_licenses_a_downsized_copy_while_sha256_stays_the_source():
    manifest = (
        "file,license,sha256,file_sha256\n"
        f"images/met-1.jpg,CC0-1.0,{SOURCE_SHA},{_sha('downsized 800 px bytes')}\n"
    )
    problems = corpus_guard.violations(
        ["corpus/images/met-1.jpg"], manifest, digest=lambda p: _sha(DOWNSIZED[p])
    )
    assert problems == []


def test_a_downsized_copy_without_file_sha256_fails_and_says_how_to_record_it():
    manifest = f"file,license,sha256\nimages/met-1.jpg,CC0-1.0,{SOURCE_SHA}\n"
    problems = corpus_guard.violations(
        ["corpus/images/met-1.jpg"], manifest, digest=lambda p: _sha(DOWNSIZED[p])
    )
    assert len(problems) == 1
    assert "keeps sha256 and records its own hash in a file_sha256 column" in problems[0]


def test_a_file_sha256_that_differs_from_the_file_fails():
    manifest = (
        "file,license,sha256,file_sha256\n"
        f"images/met-1.jpg,CC0-1.0,{SOURCE_SHA},{_sha('another copy')}\n"
    )
    problems = corpus_guard.violations(
        ["corpus/images/met-1.jpg"], manifest, digest=lambda p: _sha(DOWNSIZED[p])
    )
    assert len(problems) == 1
    assert "records file_sha256" in problems[0]
    assert "not the copy that row licenses" in problems[0]


def test_a_malformed_sha256_fails():
    manifest = "file,license,sha256\nmom/IMG_1234.jpg,CC0-1.0,abc123\n"
    problems = corpus_guard.violations(["corpus/mom/IMG_1234.jpg"], manifest, digest=_digest)
    assert len(problems) == 1
    assert "malformed sha256" in problems[0]


def test_an_empty_sha256_cell_keeps_the_name_rule():
    manifest = "file,license,sha256\na.jpg,CC0-1.0,\n"
    assert corpus_guard.violations(["corpus/images/a.jpg"], manifest) == []


def test_a_removed_file_licensed_by_an_earlier_manifest_passes():
    tracked = ["corpus/manifest.csv"]
    history = ["file,license\n", "file,license\nmuseum/a.jpg,CC0-1.0\n"]
    problems = corpus_guard.violations(
        tracked, "file,license\n", added=["corpus/museum/a.jpg"], history=history
    )
    assert problems == []


def test_a_removed_file_is_judged_by_its_newest_row():
    # Newest first: the license was withdrawn before the file was dropped.
    history = ["file,license\nmuseum/a.jpg,not cleared\n", "file,license\nmuseum/a.jpg,CC0-1.0\n"]
    problems = corpus_guard.violations(
        ["corpus/manifest.csv"], "file,license\n", added=["corpus/museum/a.jpg"], history=history
    )
    assert len(problems) == 1
    assert "not cleared" in problems[0]
    assert "then removed" in problems[0]


def test_a_removed_file_that_no_manifest_named_fails():
    history = ["file,license\n", None]
    problems = corpus_guard.violations(
        ["corpus/manifest.csv"], "file,license\n", added=["corpus/museum/a.jpg"], history=history
    )
    assert len(problems) == 1
    assert "no row in corpus/manifest.csv" in problems[0]


def test_a_moved_file_keeps_its_bare_name_row():
    # The removed old path holds the same bytes as the tracked new path, so it
    # is the licensed file, moved; the shared name makes nothing ambiguous.
    tracked = ["corpus/manifest.csv", "corpus/museum/a.jpg"]
    manifest = "file,license\na.jpg,CC0-1.0\n"
    problems = corpus_guard.violations(
        tracked, manifest, added=["corpus/incoming/a.jpg"], digest=lambda path: _sha("a")
    )
    assert problems == []


Version = corpus_guard.Version


def test_a_removed_file_cannot_borrow_a_tracked_namesakes_bare_name_row():
    # Phone names repeat: a shop capture added and removed in the range must
    # not pass on the row of Jake's tracked photo with the same name.
    tracked = {"corpus/manifest.csv": "m", "corpus/jake/IMG_1234.jpg": "jake"}
    manifest = "file,license\nIMG_1234.jpg,CC0-1.0\n"
    added = [Version("corpus/shop/IMG_1234.jpg", "shop", "c1")]
    digest = {"jake": _sha("jake's photo"), "shop": _sha("shop capture")}.get
    problems = corpus_guard.violations(tracked, manifest, added, digest=digest)
    assert len(problems) == 1
    assert problems[0].startswith("corpus/shop/IMG_1234.jpg (committed in this range")
    assert "ambiguous" in problems[0]


def test_an_earlier_version_with_other_bytes_at_a_licensed_path_fails():
    # A fix-forward commit restored the licensed bytes, but the version before
    # it stays in history: every version the range wrote must be licensed.
    tracked = {"corpus/manifest.csv": "m", "corpus/museum/met_1.jpg": "licensed"}
    manifest = f"file,license,sha256\nmuseum/met_1.jpg,CC0-1.0,{_sha('museum bytes')}\n"
    added = [
        Version("corpus/museum/met_1.jpg", "licensed", "c2" * 20),
        Version("corpus/museum/met_1.jpg", "private", "c1" * 20),
    ]
    digest = {"licensed": _sha("museum bytes"), "private": _sha("private photo")}.get
    problems = corpus_guard.violations(tracked, manifest, added, digest=digest)
    assert len(problems) == 1
    assert problems[0].startswith(
        "corpus/museum/met_1.jpg (committed in this range, then removed or replaced; "
        "commit c1c1c1c1c1c1)"
    )
    assert "not the file that row licenses" in problems[0]


def test_an_earlier_version_with_a_licensed_files_bytes_passes():
    # Renamed before its row was written: the bytes are the licensed file's.
    tracked = {"corpus/manifest.csv": "m", "corpus/museum/met-1.jpg": "b1"}
    manifest = "file,license\nmuseum/met-1.jpg,CC0-1.0\n"
    added = [Version("corpus/incoming/download.jpg", "b1", "c1")]
    digest = {"b1": _sha("met one")}.get
    assert corpus_guard.violations(tracked, manifest, added, digest=digest) == []


def test_a_removed_file_skips_rows_that_record_other_content():
    # A later commit re-encoded the file (a new sha256 row) and then dropped
    # it; the version that was added matches the older row.
    content = {"corpus/m/a.jpg": "first encoding"}
    history = [
        f"file,license,sha256\nm/a.jpg,CC0-1.0,{_sha('second encoding')}\n",
        f"file,license,sha256\nm/a.jpg,CC0-1.0,{_sha('first encoding')}\n",
    ]
    problems = corpus_guard.violations(
        ["corpus/manifest.csv"],
        "file,license,sha256\n",
        added=["corpus/m/a.jpg"],
        history=history,
        digest=lambda path: _sha(content[path]),
    )
    assert problems == []


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


@pytest.mark.parametrize(
    ("message", "blessed"),
    [
        ("Re-render top diagram\n\n[bless]\n", True),
        ("Re-render top diagram\n\nApproved in #91.\n  [bless]  \n", True),
        ("Re-render top diagram\n\n[bless] approved by Jake\n", True),
        # CLAUDE.md, #105 and plan A6 word the rule as "a commit whose message
        # contains [bless]", and only commits that edit tests/golden/ are judged.
        (
            "A6: consolidated golden refresh at the new defaults\n\n"
            "This is the one consolidated [bless] that REBASELINE.md names:\n"
            "tests/golden/top.svg\n",
            True,
        ),
        ("Re-render top diagram\r\n\r\nApproved in #91 as a [bless].\r\n", True),
        ("Re-render top diagram\n\nNo marker here.\n", False),
        ('Revert "Re-render top diagram [bless]"\n\nThis reverts commit 0123abcd.\n', False),
    ],
)
def test_a_marker_anywhere_in_the_commits_own_message_marks_a_bless(message, blessed):
    subject = message.splitlines()[0]
    commit = golden_guard.GoldenCommit("0" * 40, subject, (TOP,), message)
    assert golden_guard.is_bless(commit) is blessed
    assert golden_guard.verdict([TOP], [commit])[0] is blessed


BLESSED_BLOB = "100644 " + "a" * 40
MERGED_BLOB = "100644 " + "b" * 40


def test_merged_golden_content_that_no_commit_wrote_fails():
    commit = golden_guard.GoldenCommit(
        "0" * 40, "Re-render top diagram [bless]", (TOP,), wrote={TOP: BLESSED_BLOB}
    )
    ok, message = golden_guard.verdict([TOP], [commit], final={TOP: MERGED_BLOB})
    assert not ok
    assert "merge commit" in message


def test_merged_golden_content_that_a_bless_commit_wrote_passes():
    commit = golden_guard.GoldenCommit(
        "0" * 40, "Re-render top diagram [bless]", (TOP,), wrote={TOP: BLESSED_BLOB}
    )
    assert golden_guard.verdict([TOP], [commit], final={TOP: BLESSED_BLOB})[0]


def test_a_golden_deletion_by_a_bless_commit_passes():
    commit = golden_guard.GoldenCommit(
        "0" * 40, "Retire cut list [bless]", (CUT,), wrote={CUT: None}
    )
    assert golden_guard.verdict([CUT], [commit], final={CUT: None})[0]


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


def _commit(repo: Path, message: str, files: dict[str, str | bytes] | None = None) -> str:
    # bytes are written exactly, so a test can know the committed blob's sha256
    # (text mode on Windows would write CRLF line ends).
    for rel, content in (files or {}).items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
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
def test_golden_guard_script_ignores_a_marker_in_another_commits_body(repo):
    # Only the commit that edits tests/golden/ can bless its own edit.
    base = _start_branch(repo)
    _commit(repo, "Re-render cut list", {CUT: "z\n"})
    head = _commit(repo, "Tidy notes\n\nOutput is unchanged, so this needs no [bless] commit.")
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "without [bless] in its own message" in result.stdout


@needs_git
def test_golden_guard_script_accepts_a_marker_in_the_editing_commits_body(repo):
    # Plan A6's one consolidated bless, worded the way CLAUDE.md states the rule.
    base = _start_branch(repo)
    message = (
        "A6: consolidated golden refresh at the new defaults\n\n"
        f"This is the one consolidated [bless] that REBASELINE.md names:\n{CUT}"
    )
    head = _commit(repo, message, {CUT: "a,b,c\n"})
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


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
def test_golden_guard_script_accepts_a_marker_line_in_the_body(repo):
    base = _start_branch(repo)
    head = _commit(repo, "Re-render cut list\n\n[bless]", {CUT: "a,b,c\n"})
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


def _bless_then_start_merging_other_work(repo: Path) -> str:
    """work blesses the cut list, main gains unrelated work, and work starts
    merging main without committing. Returns main's tip, the base."""
    _start_branch(repo)
    _commit(repo, "Re-render cut list [bless]", {CUT: "blessed\n"})
    _git(repo, "checkout", "-q", "main")
    base = _commit(repo, "Other work", {"other.txt": "o\n"})
    _git(repo, "checkout", "-q", "work")
    _git(repo, "merge", "-q", "--no-ff", "--no-commit", "main")
    return base


@needs_git
def test_golden_guard_script_fails_a_merge_that_rewrites_a_blessed_golden(repo):
    base = _bless_then_start_merging_other_work(repo)
    head = _commit(repo, "Merge main into work", {CUT: "rewritten inside the merge\n"})
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "merge commit" in result.stdout


@needs_git
def test_golden_guard_script_passes_a_merge_that_keeps_the_blessed_golden(repo):
    base = _bless_then_start_merging_other_work(repo)
    head = _commit(repo, "Merge main into work")
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


@needs_git
def test_golden_guard_script_fails_two_blesses_merged_as_text(repo):
    lines = [f"l{i}" for i in range(1, 9)]
    _commit(repo, "Bless eight lines [bless]", {TOP: "\n".join(lines) + "\n"})
    _start_branch(repo)
    _commit(repo, "Branch re-render [bless]", {TOP: "\n".join(["L1", *lines[1:]]) + "\n"})
    _git(repo, "checkout", "-q", "main")
    base = _commit(repo, "Upstream re-render [bless]", {TOP: "\n".join([*lines[:-1], "L8"]) + "\n"})
    _git(repo, "checkout", "-q", "work")
    _git(repo, "merge", "-q", "--no-ff", "-m", "Merge main into work", "main")
    head = _git(repo, "rev-parse", "HEAD")
    # The clean textual merge holds both edits: a file that neither bless wrote.
    assert (repo / TOP).read_text(encoding="utf-8").splitlines()[::7] == ["L1", "L8"]
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 1, result.stdout + result.stderr


@needs_git
def test_golden_guard_script_fails_a_criss_cross_merge_that_restores_an_old_golden(repo):
    root = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "w1")
    _commit(repo, "w1 work", {"a.txt": "a\n"})
    _git(repo, "checkout", "-q", "-b", "w2", root)
    _commit(repo, "Bless the cut list [bless]", {CUT: "blessed\n"})
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "Merge w1", "w1")
    _git(repo, "merge", "-q", "--no-ff", "-m", "Merge w2", "w2")
    base = _git(repo, "rev-parse", "HEAD")
    # h starts from w1 and merges w2 but keeps the old cut list, so h and main
    # have two merge bases and merging h would undo the bless.
    _git(repo, "checkout", "-q", "-b", "h", "w1")
    _git(repo, "merge", "-q", "--no-ff", "--no-commit", "w2")
    _git(repo, "checkout", root, "--", CUT)
    _commit(repo, "Merge w2 into h")
    head = _commit(repo, "h work", {"h.txt": "h\n"})
    assert len(_git(repo, "merge-base", "--all", base, head).split()) == 2
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 1, result.stdout + result.stderr


@needs_git
def test_golden_guard_script_judges_a_stacked_branch_by_its_merge_result(repo):
    _git(repo, "checkout", "-q", "-b", "w1")
    _commit(repo, "w1 work", {"w1.txt": "w\n"})
    _git(repo, "checkout", "-q", "-b", "h")
    _commit(repo, "h work", {"h.txt": "h\n"})
    _git(repo, "checkout", "-q", "main")
    _commit(repo, "Bless the cut list [bless]", {CUT: "blessed\n"})
    _git(repo, "checkout", "-q", "h")
    _git(repo, "merge", "-q", "--no-ff", "-m", "Merge main into h", "main")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "Merge w1", "w1")
    base = _git(repo, "rev-parse", "HEAD")
    head = _git(repo, "rev-parse", "h")
    assert len(_git(repo, "merge-base", "--all", base, head).split()) == 2
    # Merging h now adds only h.txt; the bless is already on main.
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


@needs_git
def test_golden_guard_script_reports_a_head_that_conflicts_with_the_base_as_exit_2(repo):
    _start_branch(repo)
    head = _commit(repo, "Re-render cut list [bless]", {CUT: "branch\n"})
    _git(repo, "checkout", "-q", "main")
    base = _commit(repo, "Upstream re-render [bless]", {CUT: "upstream\n"})
    result = _run(repo, "golden_guard.py", base, head)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "does not merge cleanly" in result.stderr


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


@needs_git
def test_corpus_guard_range_catches_a_private_file_added_inside_a_merge(repo):
    _start_branch(repo)
    _commit(repo, "Work", {"w.txt": "w\n"})
    _git(repo, "checkout", "-q", "main")
    base = _commit(repo, "Other work", {"other.txt": "o\n"})
    _git(repo, "checkout", "-q", "work")
    _git(repo, "merge", "-q", "--no-ff", "--no-commit", "main")
    _commit(repo, "Merge main into work", {"local-photos/IMG_4461.png": "not really a png\n"})
    _git(repo, "rm", "-q", "local-photos/IMG_4461.png")
    head = _commit(repo, "Remove the stray photo")
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "local-photos/IMG_4461.png" in result.stdout


@needs_git
def test_corpus_guard_range_passes_licensed_images_that_were_moved_or_dropped(repo):
    base = _start_branch(repo)
    _commit(
        repo,
        "Add two museum images (CC0)",
        {
            "corpus/manifest.csv": "file,license\nmet-1.jpg,CC0-1.0\nmet-2.jpg,CC0-1.0\n",
            "corpus/met-1.jpg": "one\n",
            "corpus/met-2.jpg": "two\n",
        },
    )
    (repo / "corpus" / "museum").mkdir()
    _git(repo, "mv", "corpus/met-1.jpg", "corpus/museum/met-1.jpg")
    _git(repo, "rm", "-q", "corpus/met-2.jpg")
    head = _commit(
        repo,
        "Move met-1 into the museum tier; drop met-2 and its row",
        {"corpus/manifest.csv": "file,license\nmet-1.jpg,CC0-1.0\n"},
    )
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


@needs_git
def test_corpus_guard_range_reads_rows_from_the_range_history(repo):
    base = _start_branch(repo)
    manifest = "corpus/manifest.csv"
    _commit(repo, "Add a, row next", {manifest: "file,license\n", "corpus/museum/a.jpg": "a\n"})
    _commit(repo, "Record a's license", {manifest: "file,license\nmuseum/a.jpg,CC0-1.0\n"})
    _git(repo, "rm", "-q", "corpus/museum/a.jpg")
    head = _commit(repo, "Drop a and its row", {manifest: "file,license\n"})
    passed = _run(repo, "corpus_guard.py", "--range", base, head)
    assert passed.returncode == 0, passed.stdout + passed.stderr

    b_row = "file,license\nmuseum/b.jpg,CC0-1.0\n"
    _commit(repo, "Add b (CC0)", {manifest: b_row, "corpus/museum/b.jpg": "b\n"})
    _commit(repo, "Rights unclear after all", {manifest: b_row.replace("CC0-1.0", "not cleared")})
    _git(repo, "rm", "-q", "corpus/museum/b.jpg")
    head = _commit(repo, "Drop b and its row", {manifest: "file,license\n"})
    failed = _run(repo, "corpus_guard.py", "--range", base, head)
    assert failed.returncode == 1, failed.stdout + failed.stderr
    assert "corpus/museum/b.jpg" in failed.stdout
    assert "not cleared" in failed.stdout


@needs_git
def test_corpus_guard_range_judges_the_heads_tree_not_the_index(repo):
    # CI never checks out the pull request: the checkout stays on main, whose
    # manifest still licenses the image that the pull request un-licenses.
    manifest = "corpus/manifest.csv"
    _commit(repo, "Add a licensed image", {manifest: LICENSED, "corpus/images/a.jpg": "a\n"})
    base = _start_branch(repo)
    head = _commit(repo, "Rights unclear", {manifest: LICENSED.replace("CC0-1.0", "UNVERIFIED")})
    _git(repo, "checkout", "-q", "main")
    assert _run(repo, "corpus_guard.py").returncode == 0
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "UNVERIFIED" in result.stdout


def _bsha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


MANIFEST_PATH = "corpus/manifest.csv"
MET = "corpus/museum/met_1.jpg"
MUSEUM = b"MUSEUM-CC0-BYTES\n"
PRIVATE = b"PRIVATE-PHONE-PHOTO\n"
PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"


@needs_git
def test_corpus_guard_range_judges_the_merge_result(repo):
    # main starts relying on an existing row for m.jpg while a branch cut from
    # older main drops that row as a cleanup. Each tip passes on its own, but
    # the merge would land m.jpg without a row, so the branch fails now.
    rows = "file,license\nimages/a.jpg,CC0-1.0\nimages/k.jpg,CC0-1.0\nimages/m.jpg,CC0-1.0\n"
    images = {"corpus/images/a.jpg": "a\n", "corpus/images/k.jpg": "k\n"}
    _commit(repo, "Corpus", {MANIFEST_PATH: rows, **images})
    _start_branch(repo)
    without_m = rows.replace("images/m.jpg,CC0-1.0\n", "")
    head = _commit(repo, "Drop the unused m row", {MANIFEST_PATH: without_m})
    assert _run(repo, "corpus_guard.py").returncode == 0
    _git(repo, "checkout", "-q", "main")
    base = _commit(repo, "Add m", {"corpus/images/m.jpg": "m\n"})
    assert _run(repo, "corpus_guard.py").returncode == 0
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "corpus/images/m.jpg: no row in corpus/manifest.csv" in result.stdout


@needs_git
def test_corpus_guard_range_reports_a_head_that_conflicts_with_the_base_as_exit_2(repo):
    _start_branch(repo)
    head = _commit(repo, "Branch rows", {MANIFEST_PATH: "file,license\nimages/b.jpg,CC0-1.0\n"})
    _git(repo, "checkout", "-q", "main")
    base = _commit(repo, "Main rows", {MANIFEST_PATH: "file,license\nimages/c.jpg,CC0-1.0\n"})
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 2, result.stdout + result.stderr
    assert "does not merge cleanly" in result.stderr


def _license_met(repo: Path, *, committed: bool = True) -> str:
    """main licenses MUSEUM's bytes at MET by sha256. Returns main's tip, the base."""
    files: dict[str, str | bytes] = {
        MANIFEST_PATH: f"file,license,sha256\nmuseum/met_1.jpg,CC0-1.0,{_bsha(MUSEUM)}\n"
    }
    if committed:
        files[MET] = MUSEUM
    _commit(repo, "License met_1", files)
    return _start_branch(repo)


@needs_git
def test_corpus_guard_range_fails_other_bytes_that_a_later_commit_restored(repo):
    base = _license_met(repo)
    _commit(repo, "Re-encode met_1", {MET: PRIVATE})
    _git(repo, "checkout", base, "--", MET)
    head = _commit(repo, "Restore met_1")
    # The final tree is the licensed one; history still holds the other bytes.
    assert _run(repo, "corpus_guard.py").returncode == 0
    assert _git(repo, "show", f"{head}~1:{MET}") == PRIVATE.decode().strip()
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{MET} (committed in this range, then removed or replaced" in result.stdout


@needs_git
def test_corpus_guard_range_fails_other_bytes_dropped_with_their_row(repo):
    base = _license_met(repo)
    _commit(repo, "Swap in a better photo", {MET: PRIVATE})
    _git(repo, "rm", "-q", MET)
    head = _commit(repo, "Drop met_1", {MANIFEST_PATH: "file,license,sha256\n"})
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert MET in result.stdout


@needs_git
def test_corpus_guard_range_fails_wrong_bytes_removed_and_then_replaced(repo):
    base = _license_met(repo, committed=False)
    _commit(repo, "Add met_1", {MET: PRIVATE})
    _git(repo, "rm", "-q", MET)
    _commit(repo, "Wrong file")
    head = _commit(repo, "Add the right met_1", {MET: MUSEUM})
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 1, result.stdout + result.stderr


@needs_git
def test_corpus_guard_range_fails_a_fix_forward_and_never_advises_editing_the_row(repo):
    base = _license_met(repo, committed=False)
    head = _commit(repo, "Add met_1", {MET: PRIVATE})
    first = _run(repo, "corpus_guard.py", "--range", base, head)
    assert first.returncode == 1, first.stdout + first.stderr
    assert "not the file that row licenses" in first.stdout
    assert "update the row" not in first.stdout
    head = _commit(repo, "Use the licensed bytes", {MET: MUSEUM})
    second = _run(repo, "corpus_guard.py", "--range", base, head)
    assert second.returncode == 1, second.stdout + second.stderr
    # Once pushed, the bytes are public: the hint says to stop, not to fix forward.
    assert "stop pushing" in second.stdout
    assert "refs/pull/<n>/head" in second.stdout
    assert "do not merge such a branch" not in second.stdout


@needs_git
def test_corpus_guard_range_fails_a_removed_namesake_of_a_licensed_photo(repo):
    licensed = {
        MANIFEST_PATH: "file,license\nIMG_1234.jpg,CC0-1.0\n",
        "corpus/jake/IMG_1234.jpg": b"JAKE-CC0\n",
    }
    _commit(repo, "Jake's photo", licensed)
    base = _start_branch(repo)
    shop = "corpus/shop/IMG_1234.jpg"
    head = _commit(repo, "Add shop capture", {shop: b"SHOP-SCREENSHOT\n"})
    kept = _run(repo, "corpus_guard.py", "--range", base, head)
    assert kept.returncode == 1, kept.stdout + kept.stderr
    _git(repo, "rm", "-q", shop)
    head = _commit(repo, "Remove shop capture")
    removed = _run(repo, "corpus_guard.py", "--range", base, head)
    assert removed.returncode == 1, removed.stdout + removed.stderr
    assert f"{shop} (committed in this range" in removed.stdout
    assert "ambiguous" in removed.stdout


PLAN_FILES: dict[str, str | bytes] = {
    MANIFEST_PATH: "file,license\n",
    "corpus/README.md": "Accepted and rejected sources.\n",
    "corpus/ATTRIBUTION.md": "Credits generated from the manifest.\n",
    "corpus/schema/annotation.schema.json": '{"type": "object"}\n',
    "corpus/annotations/met-1.proposed-a.json": '{"corners": []}\n',
    "corpus/gold/met-1.json": '{"rows": 8}\n',
    "corpus/holdout.json": '{"holdout": []}\n',
}


@needs_git
def test_corpus_guard_passes_the_plans_qrep_authored_corpus_files(repo):
    base = _start_branch(repo)
    head = _commit(repo, "D3a and D3b files", PLAN_FILES)
    index = _run(repo, "corpus_guard.py")
    assert index.returncode == 0, index.stdout + index.stderr
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


@needs_git
def test_corpus_guard_fails_an_image_saved_beside_its_annotation(repo):
    base = _start_branch(repo)
    overlay = "corpus/annotations/IMG_4461_overlay.png"
    head = _commit(repo, "Annotation and overlay", {**PLAN_FILES, overlay: PNG})
    index = _run(repo, "corpus_guard.py")
    assert index.returncode == 1, index.stdout + index.stderr
    assert f"{overlay}: no row in corpus/manifest.csv" in index.stdout
    assert "git restore --staged" in index.stdout
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{overlay}: no row in corpus/manifest.csv" in result.stdout


@needs_git
def test_corpus_guard_range_fails_binary_bytes_under_a_json_name(repo):
    base = _start_branch(repo)
    disguised = "corpus/annotations/met-1.json"
    _commit(repo, "Annotation", {disguised: PNG})
    head = _commit(repo, "Real annotation", {disguised: '{"corners": []}\n'})
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "not UTF-8 text" in result.stdout


@needs_git
def test_corpus_guard_range_licenses_a_downsized_copy_through_file_sha256(repo):
    full, small = b"FULL-SIZE SOURCE IMAGE BYTES", b"DOWNSIZED 800PX COPY BYTES"
    header = "file,license,sha256,file_sha256\n"
    source_row = f"{header}images/met-1.jpg,CC0-1.0,{_bsha(full)},\n"
    _commit(repo, "Source row", {MANIFEST_PATH: source_row})
    base = _start_branch(repo)
    head = _commit(repo, "Commit the downsized example", {"corpus/images/met-1.jpg": small})
    refused = _run(repo, "corpus_guard.py", "--range", base, head)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "file_sha256" in refused.stdout
    assert "update the row" not in refused.stdout
    copy_row = f"{header}images/met-1.jpg,CC0-1.0,{_bsha(full)},{_bsha(small)}\n"
    head = _commit(repo, "Record the copy's own hash", {MANIFEST_PATH: copy_row})
    result = _run(repo, "corpus_guard.py", "--range", base, head)
    assert result.returncode == 0, result.stdout + result.stderr


# The guard workflow itself

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"


def _top_level_block(text: str, key: str) -> list[str]:
    lines = text.splitlines()
    start = lines.index(f"{key}:")
    block = []
    for line in lines[start + 1 :]:
        if line and not line.startswith((" ", "#")):
            break
        block.append(line)
    return block


def test_the_guards_run_main_copies_and_treat_the_pull_request_as_data():
    text = (WORKFLOWS / "guards.yml").read_text(encoding="utf-8")
    triggers = [line.strip() for line in _top_level_block(text, "on")]
    assert "pull_request_target:" in triggers
    # pull_request would run the PR's own workflow copy; a dispatch could run
    # a branch's copy and replace a failing check on that branch's tip.
    assert not any(t.startswith(("pull_request:", "workflow_dispatch")) for t in triggers)
    # Retargeting a pull request (a base change is an "edited" event) must
    # re-run the guards against the new base.
    types = next(t for t in triggers if t.startswith("types:"))
    assert {"opened", "synchronize", "reopened", "edited"} <= set(re.findall(r"\w+", types))
    # No checkout of the PR and nothing installed from it.
    assert not re.search(r"^\s*ref:", text, re.MULTILINE)
    assert not re.search(r"setup-python|setup-node|pip install|npm ", text)
    assert "python3 scripts/golden_guard.py" in text
    assert "python3 scripts/corpus_guard.py --range" in text
    # A required check matches by name, so no other workflow may reuse one.
    for path in WORKFLOWS.glob("*.yml"):
        if path.name != "guards.yml":
            other = path.read_text(encoding="utf-8")
            assert "golden-guard" not in other and "corpus-guard" not in other, path.name
