"""D3c private tiers: the intake that keeps shop screenshots and phone captures out of the repo.

Every photo here is synthetic and made in a temporary directory, so no private file is read and
nothing is written outside tmp_path. Expected values are hand-computed in the comments beside
each assertion, or come from an oracle independent of the intake (hashlib over the source bytes,
Pillow's own decoder and EXIF reader); none is pasted from intake output.
"""

import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import private_intake as pi
from qrep_eval import annotation as an

# The same gate as tests/eval/test_corpus_manifest.py: Pyodide has no git and no subprocesses.
# The intake proves its root cannot be staged with git, so every ingest needs git; the pure
# byte-level and report tests run under Pyodide too.
needs_git = pytest.mark.skipif(
    sys.platform == "emscripten" or shutil.which("git") is None,
    reason="needs a git executable and subprocesses",
)

REPO = Path(__file__).resolve().parents[2]
REPORT = REPO / "docs" / "sprint-5" / "evidence" / "D3c-private-tiers.md"

MAKE, MODEL, ORIENTATION = 0x010F, 0x0110, 0x0112
EXIF_IFD, GPS_IFD = 0x8769, 0x8825
EXPOSURE_TIME, F_NUMBER, USER_COMMENT = 0x829A, 0x829D, 0x9286

# Fake coordinates; each needle below is planted once and must not survive the intake.
GPS = {0: b"\x02\x02\x00\x00", 1: "N", 2: (40.0, 26.0, 46.0), 3: "W", 4: (79.0, 58.0, 56.0)}
XMP = (
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
    'xmlns:exif="http://ns.adobe.com/exif/1.0/" exif:GPSLatitude="40,26.766N" '
    'exif:GPSLongitude="79,58.933W"/></rdf:RDF></x:xmpmeta>'
)
COMMENT = "Testhamlet 40.4461N 79.9822W"
IPTC_CITY = b"Testville"
ICC = b"QREP-test-icc-profile"
NEEDLES = (b"GPSLatitude", b"40,26.766N", b"Testhamlet", IPTC_CITY, b"SecondaryModel")


def picture(size=(64, 48)) -> Image.Image:
    # A gradient, so the JPEG carries real detail and a re-encode would change its pixels.
    w, h = size
    img = Image.new("RGB", size)
    img.putdata([((x * 4) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
                 for y in range(h) for x in range(w)])
    return img


def exif(make="FakePhoneCo", model="iPhone 99", orientation=1, *, exposure=True, gps=True,
         screenshot=False) -> Image.Exif:
    ex = Image.Exif()
    if make:
        ex[MAKE] = make
    if model:
        ex[MODEL] = model
    ex[ORIENTATION] = orientation
    ex[0x0132] = "2026:10:13 12:00:00"  # DateTime, which the allowlist drops
    sub = {}
    if exposure:
        sub[EXPOSURE_TIME] = 0.008
        sub[F_NUMBER] = 1.8
    if screenshot:
        sub[USER_COMMENT] = b"ASCII\x00\x00\x00Screenshot"
    if sub:
        ex[EXIF_IFD] = sub
    if gps:
        ex[GPS_IFD] = GPS
    return ex


def segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def jpeg(size=(64, 48), ex: Image.Exif | None = None, *, extras=True) -> bytes:
    buf = io.BytesIO()
    picture(size).save(buf, "JPEG", quality=90, exif=(ex or exif()).tobytes(), icc_profile=ICC)
    data = buf.getvalue()
    if not extras:
        return data
    iptc = b"\x1c\x02\x5a" + len(IPTC_CITY).to_bytes(2, "big") + IPTC_CITY
    planted = (
        segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + XMP.encode())
        + segment(0xED, b"Photoshop 3.0\x008BIM\x04\x04\x00\x00"
                  + len(iptc).to_bytes(4, "big") + iptc)
        + segment(0xFE, COMMENT.encode())
    )
    # An iPhone JPEG carries secondary images after the primary's end-of-image marker.
    secondary = io.BytesIO()
    picture((8, 8)).save(secondary, "JPEG", exif=exif(model="SecondaryModel").tobytes())
    return data[:2] + planted + data[2:] + secondary.getvalue()


def png(size=(64, 48), ex: Image.Exif | None = None) -> bytes:
    info = PngInfo()
    info.add_itxt("XML:com.adobe.xmp", XMP)
    info.add_text("Comment", COMMENT)
    buf = io.BytesIO()
    picture(size).save(buf, "PNG", pnginfo=info, exif=(ex or exif()).tobytes(), icc_profile=ICC)
    return buf.getvalue()


def decoded(data: bytes) -> tuple[str, tuple[int, int], bytes]:
    with Image.open(io.BytesIO(data)) as im:
        return im.mode, im.size, im.tobytes()


def assert_location_free(data: bytes) -> None:
    # Pillow is the oracle: it reads EXIF, XMP, IPTC and comments on its own.
    with Image.open(io.BytesIO(data)) as im:
        ex = im.getexif()
        assert GPS_IFD not in ex and not ex.get_ifd(GPS_IFD)
        assert EXIF_IFD not in ex
        assert not {"xmp", "XML:com.adobe.xmp", "photoshop", "comment", "Comment"} & set(im.info)
    for needle in NEEDLES:
        assert needle not in data, needle


def intake(**changes) -> pi.Intake:
    fields = dict(source="test-phone", capture="camera", ownership="owned by the tester",
                  tier="A", klass="squares")
    return pi.Intake(**(fields | changes))


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout


# ---------------------------------------------------------------------------------------------
# Rules that need no file
# ---------------------------------------------------------------------------------------------


def test_split_follows_the_d3a_holdout_rule():
    # Source: corpus/README.md, Holdout rule: int(sha256[:8], 16) % 3 == 0 means holdout.
    # 0x00000003 = 3, 3 % 3 = 0: holdout. 0x00000004 = 4, 4 % 3 = 1: dev.
    # 0x00000005 = 5, 5 % 3 = 2: dev. 0xffffffff = 4294967295 = 3 x 1431655765: holdout.
    tail = "0" * 56
    assert pi.split_of("00000003" + tail) == "holdout"
    assert pi.split_of("00000004" + tail) == "dev"
    assert pi.split_of("00000005" + tail) == "dev"
    assert pi.split_of("ffffffff" + tail) == "holdout"


def test_private_tier_follows_the_capture_so_a_screenshot_is_never_a_phone_capture():
    # Source: plan section 8.2 and D3c criterion 3: a camera capture is the phone tier, and a
    # direct or nested screenshot never counts as a phone capture.
    assert pi.private_tier("camera") == "phone_capture"
    assert pi.private_tier("direct_screenshot") == "screenshot"
    assert pi.private_tier("nested_screenshot") == "screenshot"
    # A private photo is never a museum scan, and the capture is never left out.
    for capture in ("museum_scan", "", "photo"):
        with pytest.raises(pi.IntakeError):
            pi.private_tier(capture)


def test_only_jpeg_and_png_are_accepted():
    assert pi.detect_format(b"\xff\xd8\xff\xe0rest") == "JPEG"
    assert pi.detect_format(b"\x89PNG\r\n\x1a\nrest") == "PNG"
    # GIF, and the ISO box a HEIC photo starts with: Pillow cannot read HEIC without a new
    # dependency, so the capture instructions ask for JPEG.
    for data in (b"GIF89a\x01\x00", b"\x00\x00\x00\x18ftypheic\x00\x00"):
        with pytest.raises(pi.IntakeError):
            pi.detect_format(data)


# ---------------------------------------------------------------------------------------------
# The stored copy: location gone, pixels and color untouched
# ---------------------------------------------------------------------------------------------


def test_clean_jpeg_has_no_location_and_the_same_pixels():
    source = jpeg(ex=exif(orientation=6))
    # The planted metadata is really there before the clean, so the checks below are not
    # vacuous: Pillow reads the GPS IFD, and every needle sits in the source bytes.
    with Image.open(io.BytesIO(source)) as im:
        assert im.getexif().get_ifd(GPS_IFD)[2] == (40.0, 26.0, 46.0)
    assert all(needle in source for needle in NEEDLES)

    stored = pi.clean_copy(source)

    assert_location_free(stored)
    assert pi.location_traces(stored) == []
    assert pi.location_traces(source) != []
    # No re-encode: Pillow decodes the same mode, size and bytes from both.
    assert decoded(stored) == decoded(source)
    with Image.open(io.BytesIO(stored)) as im:
        ex = im.getexif()
        # The allowlist keeps exactly make, model and orientation.
        assert dict(ex) == {MAKE: "FakePhoneCo", MODEL: "iPhone 99", ORIENTATION: 6}
        assert im.info["icc_profile"] == ICC


def test_clean_png_has_no_location_and_the_same_pixels():
    source = png(ex=exif(model="iPad Test", exposure=False))
    with Image.open(io.BytesIO(source)) as im:
        assert im.getexif().get_ifd(GPS_IFD)[1] == "N"
        assert "XML:com.adobe.xmp" in im.info
    stored = pi.clean_copy(source)
    assert_location_free(stored)
    assert pi.location_traces(stored) == []
    assert decoded(stored) == decoded(source)
    with Image.open(io.BytesIO(stored)) as im:
        assert dict(im.getexif()) == {MAKE: "FakePhoneCo", MODEL: "iPad Test", ORIENTATION: 1}
        assert im.info["icc_profile"] == ICC
        assert not getattr(im, "text", {})


def test_clean_copy_without_any_exif_writes_none():
    buf = io.BytesIO()
    picture().save(buf, "PNG")
    stored = pi.clean_copy(buf.getvalue())
    with Image.open(io.BytesIO(stored)) as im:
        assert dict(im.getexif()) == {}
    assert decoded(stored) == decoded(buf.getvalue())


# ---------------------------------------------------------------------------------------------
# Ingest: the D3c criterion 4 test, then the capture, device and root rules
# ---------------------------------------------------------------------------------------------


@needs_git
def test_intake_stores_a_copy_without_location_and_a_complete_manifest_row(tmp_path):
    # Source: D3c criterion 4: a synthetic JPEG with fake GPS EXIF, run in a temporary
    # directory; the stored copy has no location tags and the manifest row is complete.
    photo = write(tmp_path / "in" / "IMG_0001.JPG", jpeg(size=(64, 48), ex=exif(orientation=6)))
    root = tmp_path / "corpus" / "private"
    row = pi.ingest(photo, intake(ownership="owned by the tester; traditional nine patch"),
                    root, today="2026-10-13")

    sha = hashlib.sha256(photo.read_bytes()).hexdigest()
    # Stem rule: "cap-" for a camera capture, then the first 12 hex digits of the source sha256.
    stem = "cap-" + sha[:12]
    stored = root / "photos" / f"{stem}.jpg"
    assert stored.is_file()
    assert_location_free(stored.read_bytes())

    assert list(row) == list(pi.COLUMNS)
    assert all(row[column] for column in pi.COLUMNS)
    assert row == {
        "file": f"private/photos/{stem}.jpg",
        "license": "private",
        "source": "test-phone",
        "source_name": "IMG_0001.JPG",
        "sha256": sha,
        "file_sha256": hashlib.sha256(stored.read_bytes()).hexdigest(),
        # Orientation 6 turns the stored 64 x 48 image a quarter turn, so it shows 48 x 64.
        "px_w": "48",
        "px_h": "64",
        "orientation": "6",
        "capture": "camera",
        "capture_evidence": "exif",
        "device_make": "FakePhoneCo",
        "device_model": "iPhone 99",
        # A model that starts with iPhone is a phone.
        "device_class": "phone",
        "ownership": "owned by the tester; traditional nine patch",
        "private_tier": "phone_capture",
        "tier": "A",
        "class": "squares",
        # The D3a holdout rule, computed here from hashlib's digest, not from the intake.
        "split": "holdout" if int(sha[:8], 16) % 3 == 0 else "dev",
        "ingested": "2026-10-13",
    }
    assert pi.read_manifest(root) == [row]
    # The source is untouched.
    assert hashlib.sha256(photo.read_bytes()).hexdigest() == sha


@needs_git
def test_sidecar_is_a_valid_annotation_with_the_screened_capture(tmp_path):
    photo = write(tmp_path / "shot.png", png(ex=exif(make="", model="", exposure=False)))
    root = tmp_path / "private"
    row = pi.ingest(photo, intake(capture="nested_screenshot", device_class="phone", tier="R",
                                  klass="curve"), root, today="2026-10-13")
    stem = Path(row["file"]).stem
    # Stem rule: "shot-" for a screenshot.
    assert stem == "shot-" + row["sha256"][:12]
    doc = an.load(root / "annotations" / f"{stem}.json")
    assert doc.photo == row["file"]
    assert doc.sha256 == row["sha256"]
    assert list(doc.canvas) == [64, 48]
    assert [(c.provenance, c.value) for c in doc.capture] == [("screened", "nested_screenshot")]
    assert [(c.provenance, c.value) for c in doc.device_class] == [("screened", "phone")]
    # No EXIF make or model: the row says so rather than leaving the cells blank.
    assert (row["device_make"], row["device_model"]) == ("unknown", "unknown")
    assert row["private_tier"] == "screenshot"


@needs_git
def test_claims_join_the_sidecar_but_never_as_gate_truth(tmp_path):
    photo = write(tmp_path / "a.png", png(ex=exif(make="", model="", exposure=False)))
    root = tmp_path / "private"
    claims = {"construction_class": [{"provenance": "proposed-a", "value": "squares"}],
              "counts": [{"provenance": "proposed-a", "value": {
                  "blocks_across": 1, "blocks_down": 1,
                  "squares_per_block_across": 40, "squares_per_block_down": 40}}]}
    for code in an.TRUTH:
        bad = {"construction_class": [{"provenance": code, "value": "squares"}]}
        with pytest.raises(pi.IntakeError, match="truth"):
            pi.ingest(photo, intake(capture="direct_screenshot", device_class="phone"), root,
                      claims=bad)
    # Nothing was written by the refused attempts.
    assert not root.exists()
    row = pi.ingest(photo, intake(capture="direct_screenshot", device_class="phone"), root,
                    claims=claims)
    doc = an.load(root / "annotations" / f"{Path(row['file']).stem}.json")
    assert doc.counts[0].value.squares_per_block_across == 40
    assert doc.construction_class[0].provenance == "proposed-a"


@needs_git
def test_regression_pins_are_kept_bound_to_the_photo(tmp_path):
    photo = write(tmp_path / "a.png", png(ex=exif(make="", model="", exposure=False)))
    root = tmp_path / "private"
    pins = [{"note": "an earlier run's outer edge, by eye", "space": [64, 48],
             "corners": [[1, 2], [60, 2], [61, 45], [2, 46]]}]
    row = pi.ingest(photo, intake(capture="direct_screenshot", device_class="phone"), root,
                    regression=pins)
    kept = json.loads((root / "regression" / f"{Path(row['file']).stem}.json").read_text())
    assert kept == {"photo": row["file"], "sha256": row["sha256"], "pins": pins}
    with pytest.raises(pi.IntakeError):
        pi.ingest(write(tmp_path / "b.png", png(size=(10, 10),
                                                ex=exif(make="", model="", exposure=False))),
                  intake(capture="direct_screenshot", device_class="phone"), root,
                  regression=[{"note": "three corners", "space": [10, 10],
                               "corners": [[0, 0], [1, 0], [1, 1]]}])


@needs_git
def test_a_screenshot_marked_in_exif_is_never_ingested_as_a_camera_capture(tmp_path):
    photo = write(tmp_path / "s.png", png(ex=exif(exposure=False, screenshot=True)))
    for confirmed in (False, True):
        with pytest.raises(pi.IntakeError, match="screenshot"):
            pi.ingest(photo, intake(capture_confirmed=confirmed), tmp_path / "private")
    row = pi.ingest(photo, intake(capture="direct_screenshot"), tmp_path / "private")
    assert (row["private_tier"], row["capture_evidence"]) == ("screenshot", "exif")


@needs_git
def test_capture_must_match_the_exposure_data_unless_the_operator_confirms_it(tmp_path):
    root = tmp_path / "private"
    no_exposure = write(tmp_path / "n.jpg", jpeg(ex=exif(exposure=False), extras=False))
    with pytest.raises(pi.IntakeError, match="exposure"):
        pi.ingest(no_exposure, intake(), root)
    row = pi.ingest(no_exposure, intake(capture_confirmed=True), root)
    assert (row["capture"], row["capture_evidence"]) == ("camera", "operator")

    exposed = write(tmp_path / "e.jpg", jpeg(size=(32, 32), extras=False))
    with pytest.raises(pi.IntakeError, match="exposure"):
        pi.ingest(exposed, intake(capture="direct_screenshot"), root)
    with pytest.raises(pi.IntakeError):
        pi.ingest(exposed, intake(capture=""), root)


@needs_git
def test_device_class_comes_from_the_model_or_the_operator(tmp_path):
    root = tmp_path / "private"
    tablet = write(tmp_path / "t.jpg", jpeg(ex=exif(model="iPad Air"), extras=False))
    assert pi.ingest(tablet, intake(), root)["device_class"] == "tablet"
    unnamed = write(tmp_path / "u.jpg", jpeg(size=(40, 40), ex=exif(make="", model=""),
                                             extras=False))
    with pytest.raises(pi.IntakeError, match="device-class"):
        pi.ingest(unnamed, intake(), root)
    conflict = write(tmp_path / "c.jpg", jpeg(size=(41, 41), extras=False))
    with pytest.raises(pi.IntakeError, match="device"):
        pi.ingest(conflict, intake(device_class="tablet"), root)
    with pytest.raises(pi.IntakeError):
        pi.ingest(conflict, intake(device_class="museum"), root)


@needs_git
def test_tier_and_class_use_the_d3a_vocabularies(tmp_path):
    photo = write(tmp_path / "p.jpg", jpeg(extras=False))
    for tier, klass in (("A", "curve"), ("R", "squares"), ("Q", "squares"), ("X", "hst")):
        with pytest.raises(pi.IntakeError):
            pi.ingest(photo, intake(tier=tier, klass=klass), tmp_path / "private")
    assert not (tmp_path / "private").exists()


@needs_git
def test_the_same_photo_is_ingested_once(tmp_path):
    photo = write(tmp_path / "p.jpg", jpeg(extras=False))
    root = tmp_path / "private"
    pi.ingest(photo, intake(), root)
    with pytest.raises(pi.IntakeError, match="already"):
        pi.ingest(write(tmp_path / "copy.jpg", photo.read_bytes()), intake(), root)
    assert len(pi.read_manifest(root)) == 1


@needs_git
def test_root_inside_a_checkout_must_be_ignored_there(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    photo = write(tmp_path / "p.jpg", jpeg(extras=False))
    with pytest.raises(pi.IntakeError, match="ignore"):
        pi.ingest(photo, intake(), repo / "corpus" / "private")
    assert not (repo / "corpus").exists()


@needs_git
def test_ingest_into_an_ignored_root_leaves_nothing_to_stage(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo / ".gitignore", b"corpus/private/\n")
    photo = write(tmp_path / "p.jpg", jpeg())
    pi.ingest(photo, intake(), repo / "corpus" / "private")
    assert (repo / "corpus" / "private" / "manifest.csv").is_file()
    # Only the .gitignore this test wrote is visible to git, even to add -A.
    assert git(repo, "status", "--porcelain", "--untracked-files=all").splitlines() == [
        "?? .gitignore"]
    git(repo, "add", "-A")
    assert git(repo, "diff", "--cached", "--name-only").splitlines() == [".gitignore"]


@needs_git
def test_root_in_a_linked_worktree_is_refused(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo / ".gitignore", b"corpus/private/\n")
    git(repo, "add", ".gitignore")
    # The developer's own identity when git has one, as tests/test_repo_guards.py does; CI has
    # none.
    configured = subprocess.run(["git", "config", "user.email"], cwd=repo, capture_output=True,
                                text=True).stdout.strip()
    identity = [] if configured else [
        "-c", "user.name=qrep tests", "-c", "user.email=tests@qrep.invalid"]
    git(repo, *identity, "commit", "-q", "-m", "Add ignore rules")
    git(repo, "worktree", "add", "-q", "--detach", str(tmp_path / "wt"))
    photo = write(tmp_path / "p.jpg", jpeg(extras=False))
    with pytest.raises(pi.IntakeError, match="main checkout"):
        pi.ingest(photo, intake(), tmp_path / "wt" / "corpus" / "private")
    assert not (tmp_path / "wt" / "corpus").exists()
    # The main checkout of the same repository is accepted.
    pi.ingest(photo, intake(), repo / "corpus" / "private")


# ---------------------------------------------------------------------------------------------
# The report: counts per private tier, tier and split, and nothing else
# ---------------------------------------------------------------------------------------------


def manifest_row(**changes) -> dict[str, str]:
    row = dict.fromkeys(pi.COLUMNS, "x")
    row |= {"private_tier": "phone_capture", "tier": "A", "split": "dev", "class": "squares"}
    return row | changes


def header() -> pi.ReportHeader:
    return pi.ReportHeader(date="2026-10-13", root="<main checkout>/corpus/private",
                           # A SHA made of none of the planted values' digit runs.
                           qrep="d3c/qrep/__init__.py", sha="fedcba98" * 5,
                           clean=True)


def test_report_counts_by_private_tier_tier_and_split():
    rows = [
        manifest_row(),
        manifest_row(),
        manifest_row(tier="R", split="holdout", **{"class": "curve"}),
        manifest_row(private_tier="screenshot", tier="B", split="holdout"),
        manifest_row(private_tier="screenshot"),
    ]
    table = pi.tally(rows)
    # By hand: phone_capture A dev 2, phone_capture R holdout 1, screenshot B holdout 1,
    # screenshot A dev 1; the other 12 of the 16 cells (2 private tiers x 4 tiers x 2 splits)
    # are 0, and the cells sum to the 5 rows.
    assert table[("phone_capture", "A", "dev")] == 2
    assert table[("phone_capture", "R", "holdout")] == 1
    assert table[("screenshot", "B", "holdout")] == 1
    assert table[("screenshot", "A", "dev")] == 1
    assert len(table) == 16 and sum(table.values()) == 5
    text = pi.render_report(header(), table)
    # Row cells: dev, holdout, total. Phone A: 2, 0, 2. Screenshot B: 0, 1, 1.
    assert "| phone_capture | A | 2 | 0 | 2 |" in text
    assert "| screenshot | B | 0 | 1 | 1 |" in text
    # In scope is tiers A and B: phone 2 + 0 = 2; screenshot 1 + 1 = 2.
    assert "| phone_capture | in scope (A and B) | 2 | 0 | 2 |" in text
    assert "| screenshot | in scope (A and B) | 1 | 1 | 2 |" in text
    assert "5 rows" in text


def test_report_holds_aggregates_only():
    secrets = {
        "file": "private/photos/shot-a1b2c3d4e5f6.png",
        "source": "Testshop listing",
        "source_name": "IMG_9876.JPG",
        "sha256": "a1b2c3d4e5f6" + "7" * 52,
        "file_sha256": "b" * 64,
        "px_w": "1234",
        "px_h": "2345",
        "device_make": "Testmaker",
        "device_model": "Testphone 7",
        "ownership": "made by Aunt Testperson",
    }
    text = pi.render_report(header(), pi.tally([manifest_row(**secrets)]))
    for value in secrets.values():
        assert value not in text
    assert "shot-" not in text and "IMG_" not in text


def test_committed_report_holds_aggregates_only():
    # The committed report parses back to its header and its 16 counts and re-renders byte for
    # byte, so it can hold nothing but the template, the run header and integers.
    text = REPORT.read_text(encoding="utf-8")
    head, table = pi.parse_report(text)
    assert pi.render_report(head, table) == text
    assert len(table) == 16 and all(isinstance(n, int) and n >= 0 for n in table.values())
    assert re.fullmatch(r"[0-9a-f]{40}", head.sha)
    assert re.fullmatch(r"[A-Za-z0-9._-]+/qrep/__init__\.py", head.qrep)
    assert head.root == "<main checkout>/corpus/private"
    # Nothing that names a photo, a hash of one, or a pixel size.
    assert not re.search(r"[0-9a-f]{64}", text)
    assert not re.search(r"\.(jpe?g|png|heic|heif|webp|gif|tiff?)\b", text, re.IGNORECASE)
    assert not re.search(r"IMG_|image0|local-photos|shot-|cap-", text)
    assert not re.search(r"\b\d{3,5} ?x ?\d{3,5}\b", text)
