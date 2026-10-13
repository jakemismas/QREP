"""D3c private tiers: the intake that keeps shop screenshots and phone captures out of the repo.

Every photo here is synthetic and made in a temporary directory, so no private file is read and
nothing is written outside tmp_path. Expected values are hand-computed in the comments beside
each assertion, or come from an oracle independent of the intake (hashlib over the source bytes,
Pillow's own decoder and EXIF reader); none is pasted from intake output.
"""

import hashlib
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import zlib
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

# Fake coordinates a second of arc off 0 degrees north and east, in the sea, and a processing
# method (GPS tag 27) that puts a byte needle inside the GPS IFD itself; each needle below is
# planted once and must not survive the intake.
GPS = {0: b"\x02\x02\x00\x00", 1: "N", 2: (0.0, 0.0, 1.0), 3: "E", 4: (0.0, 0.0, 1.0),
       27: b"ASCII\x00\x00\x00GPSNEEDLE"}
XMP = (
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
    'xmlns:exif="http://ns.adobe.com/exif/1.0/" exif:GPSLatitude="0,0.017N" '
    'exif:GPSLongitude="0,0.017E"/></rdf:RDF></x:xmpmeta>'
)
SCREENSHOT_XMP = (
    '<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
    'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
    'xmlns:exif="http://ns.adobe.com/exif/1.0/" exif:UserComment="Screenshot"/>'
    '</rdf:RDF></x:xmpmeta>'
)
COMMENT = "Testhamlet 0.0003N 0.0003E"
IPTC_CITY = b"Testville"
NEEDLES = (b"GPSLatitude", b"0,0.017N", b"GPSNEEDLE", b"Testhamlet", IPTC_CITY,
           b"SecondaryModel")


def icc_profile() -> bytes:
    # The smallest well-formed ICC profile: a 128-byte header whose first 4 bytes give the
    # profile's size (132) and whose bytes 36 to 39 read "acsp", then a tag count of 0.
    # 4 + 32 + 4 + 88 = 128 header bytes, + 4 = 132.
    return (132).to_bytes(4, "big") + bytes(32) + b"acsp" + bytes(88) + (0).to_bytes(4, "big")


ICC = icc_profile()


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


def chunk(kind: bytes, payload: bytes) -> bytes:
    return (len(payload).to_bytes(4, "big") + kind + payload
            + zlib.crc32(kind + payload).to_bytes(4, "big"))


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


def plain_jpeg() -> bytes:
    buf = io.BytesIO()
    picture().save(buf, "JPEG", quality=90)
    return buf.getvalue()


def plain_png() -> bytes:
    buf = io.BytesIO()
    picture().save(buf, "PNG")
    return buf.getvalue()


def png_with(before=(), after=()) -> bytes:
    """plain_png() with chunks added before its image data and after it, before IEND."""
    data = plain_png()
    # IHDR follows the 8-byte signature as 4 + 4 + 13 + 4 = 25 bytes, so it ends at byte 33.
    # IEND is the last 12 bytes: a length of 0, its type and its CRC.
    return (data[:33] + b"".join(before) + data[33:-12] + b"".join(after) + data[-12:])


def exif_payload(ex: Image.Exif) -> bytes:
    # An eXIf chunk holds the TIFF data without the "Exif\0\0" that tobytes() puts first.
    return ex.tobytes()[len(b"Exif\x00\x00"):]


def xmp_chunk(xmp: str) -> bytes:
    # iTXt: keyword, NUL, compression flag 0, method 0, empty language and translated keyword.
    return chunk(b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + xmp.encode())


def decoded(data: bytes) -> tuple[str, tuple[int, int], bytes]:
    with Image.open(io.BytesIO(data)) as im:
        return im.mode, im.size, im.tobytes()


def assert_location_free(data: bytes) -> None:
    # Pillow is the oracle: it reads EXIF, XMP, IPTC and comments on its own.
    with Image.open(io.BytesIO(data)) as im:
        im.load()
        ex = im.getexif()
        assert GPS_IFD not in ex and not ex.get_ifd(GPS_IFD)
        assert EXIF_IFD not in ex
        assert not {"xmp", "XML:com.adobe.xmp", "photoshop", "comment", "Comment"} & set(im.info)
    for needle in NEEDLES:
        assert needle not in data, needle
    # Pillow reads only one EXIF block, so the bytes are counted too: at most one JPEG EXIF
    # header and at most one PNG eXIf chunk type.
    assert data.count(b"Exif\x00\x00") <= 1
    assert data.count(b"eXIf") <= 1


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def side(sha256: str) -> str:
    # Source: corpus/README.md, Holdout rule: int(sha256[:8], 16) % 3 == 0 means holdout.
    return "holdout" if int(sha256[:8], 16) % 3 == 0 else "dev"


def intake(**changes) -> pi.Intake:
    fields = dict(source="test-phone", capture="camera", ownership="owned by the tester",
                  tier="A", klass="squares")
    return pi.Intake(**(fields | changes))


def write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def files_under(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout


PINS = [{"note": "an earlier run's outer edge, by eye", "space": [64, 48],
         "corners": [[1, 2], [60, 2], [61, 45], [2, 46]]}]


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
        assert im.getexif().get_ifd(GPS_IFD)[2] == (0.0, 0.0, 1.0)
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
        # The color profile is the stated exception: kept byte for byte.
        assert im.info["icc_profile"] == ICC


def test_clean_png_has_no_location_and_the_same_pixels():
    source = png(ex=exif(model="iPad Test", exposure=False))
    with Image.open(io.BytesIO(source)) as im:
        assert im.getexif().get_ifd(GPS_IFD)[1] == "N"
        assert "XML:com.adobe.xmp" in im.info
    assert b"GPSNEEDLE" in source
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


def test_every_png_exif_block_is_read_wherever_it_sits():
    # Pillow reads a PNG's chunks after the image data only on load, and keeps one eXIf, so a
    # GPS eXIf after IDAT, or a second eXIf, would hide from a check that asked Pillow alone.
    gps_only = exif(make="", model="", exposure=False)
    clean_first = Image.Exif()
    clean_first[MAKE] = "FakePhoneCo"
    after_only = png_with(after=[chunk(b"eXIf", exif_payload(gps_only))])
    second = png_with(before=[chunk(b"eXIf", exif_payload(clean_first))],
                      after=[chunk(b"eXIf", exif_payload(gps_only))])
    for source in (after_only, second):
        assert b"GPSNEEDLE" in source
        assert any("EXIF" in trace for trace in pi.location_traces(source))
        stored = pi.clean_copy(source)
        assert_location_free(stored)
        assert pi.location_traces(stored) == []
        assert decoded(stored) == decoded(source)
    # The first block in file order is the one the allowlist builds from: the make in the
    # second photo, and in the first only the orientation of 1 that exif() always sets.
    with Image.open(io.BytesIO(pi.clean_copy(second))) as im:
        assert dict(im.getexif()) == {MAKE: "FakePhoneCo"}
    with Image.open(io.BytesIO(pi.clean_copy(after_only))) as im:
        assert dict(im.getexif()) == {ORIENTATION: 1}


def test_thumbnail_inside_the_jfif_segment_is_dropped():
    data = plain_jpeg()
    assert data[2:4] == b"\xff\xe0"
    end = 4 + int.from_bytes(data[4:6], "big")
    # JFIF 1.01, no units, density 1 x 1, then a 4 x 1 thumbnail: 4 x 1 x 3 = 12 RGB bytes.
    app0 = b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01" + bytes([4, 1]) + b"THUMBNEEDLE!"
    source = data[:2] + segment(0xE0, app0) + data[end:]
    assert b"THUMBNEEDLE!" in source
    assert any("JPEG segments" in trace for trace in pi.location_traces(source))

    stored = pi.clean_copy(source)
    assert b"THUMBNEEDLE!" not in stored
    # The APP0 keeps its first 12 bytes (identifier, version, units, densities) and reads its
    # thumbnail size as 0 x 0: a 14-byte payload, so a length field of 16.
    assert stored[2:6] == b"\xff\xe0\x00\x10"
    assert stored[6:20] == b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    assert pi.location_traces(stored) == []
    assert decoded(stored) == decoded(source)


def test_adobe_padding_is_dropped_and_its_color_transform_kept():
    data = plain_jpeg()
    end = 4 + int.from_bytes(data[4:6], "big")
    # Without a JFIF APP0, a 3-component JPEG's color space comes from Adobe's transform byte:
    # 0 reads the scans as RGB, while a decoder with no APP14 reads them as YCbCr. So the
    # transform byte changes the decoded pixels, and dropping the segment would show.
    bare = data[:2] + data[end:]
    # Adobe APP14: version 100, flags 0 and 0, transform 0 (RGB), then 11 bytes of padding.
    app14 = b"Adobe\x00\x64\x00\x00\x00\x00\x00" + b"ADOBENEEDLE"
    source = bare[:2] + segment(0xEE, app14) + bare[2:]
    assert decoded(source) != decoded(bare)
    assert any("JPEG segments" in trace for trace in pi.location_traces(source))

    stored = pi.clean_copy(source)
    assert b"ADOBENEEDLE" not in stored
    # Its first 12 payload bytes stay, through the transform byte: a length field of 14.
    assert stored[2:6] == b"\xff\xee\x00\x0e"
    assert pi.location_traces(stored) == []
    assert decoded(stored) == decoded(source)


def test_png_chunk_longer_than_its_definition_is_dropped():
    data = plain_png()
    # pHYs is defined as 9 bytes; this one carries 10 more. IHDR ends at byte 33 (png_with).
    phys = chunk(b"pHYs", (1).to_bytes(4, "big") * 2 + b"\x00" + b"PHYSNEEDLE")
    source = data[:33] + phys + data[33:]
    assert "PNG chunks pHYs" in pi.location_traces(source)
    stored = pi.clean_copy(source)
    assert b"PHYSNEEDLE" not in stored
    assert pi.location_traces(stored) == []
    assert decoded(stored) == decoded(source)


def test_jpeg_table_segment_longer_than_its_definition_is_flagged():
    data = plain_jpeg()
    end = 4 + int.from_bytes(data[4:6], "big")
    # A restart interval's payload is 2 bytes (here 4 MCUs), so its length field reads 4;
    # this one carries 9 bytes more.
    valid = data[:end] + segment(0xDD, b"\x00\x04") + data[end:]
    padded = data[:end] + segment(0xDD, b"\x00\x04" + b"DRINEEDLE") + data[end:]
    assert pi.location_traces(valid) == []
    assert any("0xffdd" in trace for trace in pi.location_traces(padded))
    assert b"DRINEEDLE" not in pi.clean_copy(padded)


def test_png_image_data_with_bytes_past_its_stream_is_flagged():
    data = plain_png()
    start = data.index(b"IDAT") - 4
    length = int.from_bytes(data[start:start + 4], "big")
    payload = data[start + 8:start + 8 + length]
    # The decoder stops at the zlib stream's end, so bytes after it ride along unseen.
    source = data[:start] + chunk(b"IDAT", payload + b"IDATNEEDLE") + data[start + 12 + length:]
    assert any("IDAT" in trace for trace in pi.location_traces(source))
    assert pi.location_traces(data) == []


def test_icc_profile_that_is_not_a_profile_is_flagged():
    buf = io.BytesIO()
    picture().save(buf, "JPEG", quality=90, icc_profile=b"ICCNEEDLE, not a profile")
    assert any("ICC" in trace for trace in pi.location_traces(buf.getvalue()))
    good = io.BytesIO()
    picture().save(good, "JPEG", quality=90, icc_profile=ICC)
    assert pi.location_traces(good.getvalue()) == []


def test_an_orientation_only_in_xmp_is_not_promoted_into_the_stored_exif():
    xmp = ('<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
           'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
           'xmlns:tiff="http://ns.adobe.com/tiff/1.0/" tiff:Orientation="6"/></rdf:RDF>'
           '</x:xmpmeta>')
    data = plain_jpeg()
    source = data[:2] + segment(0xE1, b"http://ns.adobe.com/xap/1.0/\x00" + xmp.encode()) + data[2:]
    with Image.open(io.BytesIO(source)) as im:
        # Pillow's getexif() reports the XMP orientation, though the file has no EXIF block.
        assert im.getexif().get(ORIENTATION) == 6
        assert "exif" not in im.info
    stored = pi.clean_copy(source)
    with Image.open(io.BytesIO(stored)) as im:
        assert dict(im.getexif()) == {}


# ---------------------------------------------------------------------------------------------
# Ingest: the D3c criterion 4 test, then the split, capture, device and root rules
# ---------------------------------------------------------------------------------------------


@needs_git
def test_intake_stores_a_copy_without_location_and_a_complete_manifest_row(tmp_path):
    # Source: D3c criterion 4: a synthetic JPEG with fake GPS EXIF, run in a temporary
    # directory; the stored copy has no location tags and the manifest row is complete.
    photo = write(tmp_path / "in" / "IMG_0001.JPG", jpeg(size=(64, 48), ex=exif(orientation=6)))
    # Hashed before the ingest, so the unchanged-source check below compares two moments.
    received = sha(photo.read_bytes())
    root = tmp_path / "corpus" / "private"
    row = pi.ingest(photo, intake(ownership="owned by the tester; traditional nine patch"),
                    root, today="2026-10-13")

    (stored,) = (root / "photos").iterdir()
    assert_location_free(stored.read_bytes())
    stored_sha = sha(stored.read_bytes())
    assert stored_sha != received
    # Stem rule: "cap-" for a camera capture, then the first 12 hex digits of the stored
    # copy's sha256, the file the stem names.
    stem = "cap-" + stored_sha[:12]
    assert stored.name == f"{stem}.jpg"

    assert list(row) == list(pi.COLUMNS)
    assert all(row[column] for column in pi.COLUMNS)
    assert row == {
        "file": f"private/photos/{stem}.jpg",
        "license": "private",
        "source": "test-phone",
        "source_name": "IMG_0001.JPG",
        # corpus/README.md, Manifest columns: sha256 is the source image's hash as received,
        # and file_sha256 a copy's own hash.
        "sha256": received,
        "file_sha256": stored_sha,
        # The stored pixels, 64 x 48, which annotations index whatever the orientation tag
        # says (corpus/README.md, Annotations); the tag, 6, is kept beside them.
        "px_w": "64",
        "px_h": "48",
        "orientation": "6",
        "capture": "camera",
        # The source carries ExposureTime and FNumber, which only a camera writes.
        "capture_evidence": "exif",
        "device_make": "FakePhoneCo",
        "device_model": "iPhone 99",
        # A model that starts with iPhone is a phone.
        "device_class": "phone",
        "ownership": "owned by the tester; traditional nine patch",
        "private_tier": "phone_capture",
        "tier": "A",
        "class": "squares",
        # The D3a holdout rule on hashlib's digest of the source as received.
        "split": side(received),
        "ingested": "2026-10-13",
    }
    assert pi.read_manifest(root) == [row]
    assert sha(photo.read_bytes()) == received
    # Nothing beside the source, and exactly the four files in the root: no copy, no .part.
    assert files_under(photo.parent) == ["IMG_0001.JPG"]
    assert files_under(root) == sorted([".gitignore", "manifest.csv", f"photos/{stem}.jpg",
                                        f"annotations/{stem}.json"])
    # A .gitignore of * keeps the folder out of git even in a checkout without the ignore rules.
    assert (root / ".gitignore").read_text() == "*\n"


def with_comment(data: bytes, text: bytes) -> bytes:
    return data[:2] + segment(0xFE, text) + data[2:]


def discriminating_photos() -> dict[str, bytes]:
    """Two JPEGs whose received hash and stored-copy hash fall on opposite sides of the holdout
    rule, keyed by the received hash's side. The clean drops a comment segment, so varying the
    comment moves the received hash while the stored copy stays the same."""
    found: dict[str, bytes] = {}
    for size in range(32, 64):
        base = jpeg(size=(size, size), ex=exif(gps=False), extras=False)
        stored_side = side(sha(pi.clean_copy(base)))
        for n in range(32):
            source = with_comment(base, b"note %d" % n)
            if side(sha(source)) != stored_side:
                found.setdefault(side(sha(source)), source)
                break
        if len(found) == 2:
            return found
    raise AssertionError("no discriminating pair in the search range")


@needs_git
def test_split_follows_the_received_hash_not_the_stored_copy(tmp_path):
    # Source: corpus/README.md, Manifest columns and Holdout rule (the source image's sha256
    # as fetched), as ruled on PR #262: the split follows the received file, the sidecars bind
    # the stored copy so the dev annotate page loads it.
    root = tmp_path / "private"
    for received_side, source in discriminating_photos().items():
        photo = write(tmp_path / f"{received_side}.jpg", source)
        received = sha(source)
        row = pi.ingest(photo, intake(), root, regression=PINS)
        stem = Path(row["file"]).stem
        stored_sha = sha((root / "photos" / Path(row["file"]).name).read_bytes())
        # The case discriminates: the two hashes fall on opposite sides of the rule.
        assert side(received) == received_side != side(stored_sha)
        assert (row["sha256"], row["file_sha256"]) == (received, stored_sha)
        assert row["split"] == received_side
        assert an.load(root / "annotations" / f"{stem}.json").sha256 == stored_sha
        kept = json.loads((root / "regression" / f"{stem}.json").read_text())
        assert kept["sha256"] == stored_sha
    # One received in each split, so the tally puts one camera capture of tier A in each.
    table = pi.tally(pi.read_manifest(root))
    assert table[("phone_capture", "A", "dev")] == 1
    assert table[("phone_capture", "A", "holdout")] == 1
    assert sum(table.values()) == 2


@needs_git
def test_two_photos_in_one_root_keep_both_rows_and_sidecars(tmp_path):
    root = tmp_path / "private"
    camera = write(tmp_path / "a.jpg", jpeg(extras=False))
    shot = write(tmp_path / "b.png", png(ex=exif(make="", model="", exposure=False)))
    first = pi.ingest(camera, intake(), root, today="2026-10-13", regression=PINS)
    second = pi.ingest(shot, intake(capture="nested_screenshot", device_class="phone", tier="R",
                                    klass="curve"), root, today="2026-10-13")
    # The second ingest appends: the first row is kept as it was, in file order.
    assert pi.read_manifest(root) == [first, second]
    assert (first["sha256"], second["sha256"]) == (sha(camera.read_bytes()),
                                                  sha(shot.read_bytes()))
    for row in (first, second):
        stem = Path(row["file"]).stem
        assert (root / "photos" / Path(row["file"]).name).is_file()
        doc = an.load(root / "annotations" / f"{stem}.json")
        assert (doc.photo, doc.sha256) == (row["file"], row["file_sha256"])
    # Only the first was given regression pins.
    assert files_under(root / "regression") == [f"{Path(first['file']).stem}.json"]
    table = pi.tally(pi.read_manifest(root))
    # By hand: the camera capture is phone_capture, tier A, in its received hash's split; the
    # screenshot is screenshot, tier R, in its own; the other 14 cells are 0.
    assert table[("phone_capture", "A", side(first["sha256"]))] == 1
    assert table[("screenshot", "R", side(second["sha256"]))] == 1
    assert sum(table.values()) == 2
    text = pi.render_report(header(), table)
    # In scope is tiers A and B: the camera capture counts there, the refusal does not.
    a_dev, a_hold = (1, 0) if side(first["sha256"]) == "dev" else (0, 1)
    assert f"| phone_capture | in scope (A and B) | {a_dev} | {a_hold} | 1 |" in text
    assert "| screenshot | in scope (A and B) | 0 | 0 | 0 |" in text
    assert "2 rows" in text


@needs_git
def test_sidecar_is_a_valid_annotation_with_the_screened_capture(tmp_path):
    photo = write(tmp_path / "shot.png", png(ex=exif(make="", model="", exposure=False)))
    root = tmp_path / "private"
    row = pi.ingest(photo, intake(capture="nested_screenshot", device_class="phone", tier="R",
                                  klass="curve"), root, today="2026-10-13")
    stem = Path(row["file"]).stem
    # Stem rule: "shot-" for a screenshot.
    assert stem == "shot-" + row["file_sha256"][:12]
    doc = an.load(root / "annotations" / f"{stem}.json")
    assert doc.photo == row["file"]
    # The sidecar binds the stored copy, the file the dev annotate page loads.
    assert doc.sha256 == row["file_sha256"]
    # png() saves picture((64, 48)), and the canvas is the stored width and height.
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
    row = pi.ingest(photo, intake(capture="direct_screenshot", device_class="phone"), root,
                    regression=PINS)
    kept = json.loads((root / "regression" / f"{Path(row['file']).stem}.json").read_text())
    assert kept == {"photo": row["file"], "sha256": row["file_sha256"], "pins": PINS}
    with pytest.raises(pi.IntakeError):
        pi.ingest(write(tmp_path / "b.png", png(size=(10, 10),
                                                ex=exif(make="", model="", exposure=False))),
                  intake(capture="direct_screenshot", device_class="phone"), root,
                  regression=[{"note": "three corners", "space": [10, 10],
                               "corners": [[0, 0], [1, 0], [1, 1]]}])


@needs_git
def test_files_without_a_manifest_row_are_moved_aside_not_overwritten(tmp_path):
    photo = write(tmp_path / "a.png", png(ex=exif(make="", model="", exposure=False)))
    root = tmp_path / "private"
    shot = intake(capture="direct_screenshot", device_class="phone")
    row = pi.ingest(photo, shot, root, regression=PINS)
    stem = Path(row["file"]).stem
    sidecar = root / "annotations" / f"{stem}.json"
    # A restored manifest without the row (or a run that died before writing it), and a
    # sidecar edited by hand since.
    os.replace(root / "manifest.csv", tmp_path / "manifest.old")
    sidecar.write_text('{"edited": "verified claims"}\n')

    again = pi.ingest(photo, shot, root, regression=PINS)

    assert again["file"] == row["file"]
    (aside,) = (root / "superseded").iterdir()
    # The three files the ingest writes per photo were moved aside, the edit intact.
    assert files_under(aside) == sorted([f"annotations/{stem}.json", f"photos/{stem}.png",
                                         f"regression/{stem}.json"])
    assert (aside / "annotations" / f"{stem}.json").read_text() == (
        '{"edited": "verified claims"}\n')
    assert an.load(sidecar).sha256 == row["file_sha256"]
    assert pi.read_manifest(root) == [again]


@needs_git
def test_a_screenshot_marked_in_exif_is_never_ingested_as_a_camera_capture(tmp_path):
    photo = write(tmp_path / "s.png", png(ex=exif(exposure=False, screenshot=True)))
    for confirmed in (False, True):
        with pytest.raises(pi.IntakeError, match="screenshot"):
            pi.ingest(photo, intake(capture_confirmed=confirmed), tmp_path / "private")
    row = pi.ingest(photo, intake(capture="direct_screenshot"), tmp_path / "private")
    assert (row["private_tier"], row["capture_evidence"]) == ("screenshot", "exif")


@needs_git
def test_a_screenshot_marked_in_xmp_is_never_a_camera_capture(tmp_path):
    info = PngInfo()
    info.add_itxt("XML:com.adobe.xmp", SCREENSHOT_XMP)
    buf = io.BytesIO()
    picture().save(buf, "PNG", pnginfo=info, exif=exif(exposure=False, gps=False).tobytes())
    photo = write(tmp_path / "s.png", buf.getvalue())
    with pytest.raises(pi.IntakeError, match="screenshot"):
        pi.ingest(photo, intake(capture_confirmed=True), tmp_path / "private")
    row = pi.ingest(photo, intake(capture="direct_screenshot"), tmp_path / "private")
    # The XMP marker is the file's own evidence of a screenshot.
    assert (row["private_tier"], row["capture_evidence"]) == ("screenshot", "exif")


@needs_git
def test_a_screenshot_marker_after_the_png_image_data_is_read(tmp_path):
    # Pillow reads chunks after IDAT only on load, so these markers sit where a pre-load read
    # never looks.
    marked = exif(make="", model="", exposure=False, gps=False, screenshot=True)
    root = tmp_path / "private"
    by_exif = write(tmp_path / "e.png", png_with(after=[chunk(b"eXIf", exif_payload(marked))]))
    by_xmp = write(tmp_path / "x.png", png_with(after=[xmp_chunk(SCREENSHOT_XMP)]))
    for photo in (by_exif, by_xmp):
        with pytest.raises(pi.IntakeError, match="screenshot"):
            pi.ingest(photo, intake(capture_confirmed=True, device_class="phone"), root)
    assert not root.exists()
    for photo in (by_exif, by_xmp):
        row = pi.ingest(photo, intake(capture="direct_screenshot", device_class="phone"), root)
        assert (row["private_tier"], row["capture_evidence"]) == ("screenshot", "exif")


@needs_git
def test_capture_must_match_the_exposure_data_unless_the_operator_confirms_it(tmp_path):
    root = tmp_path / "private"
    no_exposure = write(tmp_path / "n.jpg", jpeg(ex=exif(exposure=False), extras=False))
    with pytest.raises(pi.IntakeError, match="exposure"):
        pi.ingest(no_exposure, intake(), root)
    row = pi.ingest(no_exposure, intake(capture_confirmed=True), root)
    # No exposure data, so the camera capture rests on the operator's word.
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
    # Rule: a model that starts with iPad is a tablet.
    assert pi.ingest(tablet, intake(), root)["device_class"] == "tablet"
    unnamed = write(tmp_path / "u.jpg", jpeg(size=(40, 40), ex=exif(make="", model=""),
                                             extras=False))
    with pytest.raises(pi.IntakeError, match="device-class"):
        pi.ingest(unnamed, intake(), root)
    conflict = write(tmp_path / "c.jpg", jpeg(size=(41, 41), extras=False))
    with pytest.raises(pi.IntakeError, match="device"):
        pi.ingest(conflict, intake(device_class="tablet"), root)
    # With no model to conflict with, the museum class is refused on its own: a private photo
    # is never a museum's.
    with pytest.raises(pi.IntakeError, match="device class 'museum'"):
        pi.ingest(unnamed, intake(device_class="museum"), root)


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
def test_the_same_pixels_received_twice_are_one_photo(tmp_path):
    root = tmp_path / "private"
    # The same picture encoded twice at one quality gives the same image data; only the GPS
    # differs, and the clean drops it, so both stored copies are byte for byte the same.
    first = write(tmp_path / "a.jpg", jpeg(ex=exif(gps=True), extras=False))
    second = write(tmp_path / "b.jpg", jpeg(ex=exif(gps=False), extras=False))
    assert first.read_bytes() != second.read_bytes()
    pi.ingest(first, intake(), root)
    with pytest.raises(pi.IntakeError, match="already"):
        pi.ingest(second, intake(), root)
    assert len(pi.read_manifest(root)) == 1


@needs_git
def test_a_photo_over_the_decompression_bomb_limit_is_refused(monkeypatch, tmp_path):
    photo = write(tmp_path / "p.jpg", jpeg(extras=False))
    # 64 x 48 = 3072 pixels. Pillow warns above MAX_IMAGE_PIXELS and raises above twice it:
    # a limit of 2000 warns (3072 > 2000, 3072 <= 4000), a limit of 1000 raises (3072 > 2000).
    for limit in (2000, 1000):
        monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", limit)
        with pytest.raises(pi.IntakeError, match="pixels"):
            pi.ingest(photo, intake(), tmp_path / "private")
    assert not (tmp_path / "private").exists()


@needs_git
def test_an_icc_segment_that_is_not_a_profile_is_refused(tmp_path):
    buf = io.BytesIO()
    picture().save(buf, "JPEG", quality=90, exif=exif(gps=False).tobytes(),
                   icc_profile=b"ICCNEEDLE, not a profile")
    photo = write(tmp_path / "p.jpg", buf.getvalue())
    with pytest.raises(pi.IntakeError, match="ICC"):
        pi.ingest(photo, intake(), tmp_path / "private")
    assert not (tmp_path / "private").exists()


@needs_git
def test_ingest_refuses_a_clean_that_keeps_metadata_or_changes_pixels(monkeypatch, tmp_path):
    photo = write(tmp_path / "p.jpg", jpeg())
    root = tmp_path / "private"
    monkeypatch.setattr(pi, "clean_copy", lambda data: data)
    with pytest.raises(pi.IntakeError, match="metadata survived"):
        pi.ingest(photo, intake(), root)

    def reencoded(data: bytes) -> bytes:
        buf = io.BytesIO()
        with Image.open(io.BytesIO(data)) as im:
            # From the bare pixels, so no metadata of the source comes along.
            Image.frombytes(im.mode, im.size, im.tobytes()).save(buf, "JPEG", quality=50)
        return buf.getvalue()

    monkeypatch.setattr(pi, "clean_copy", reencoded)
    with pytest.raises(pi.IntakeError, match="other pixels"):
        pi.ingest(photo, intake(), root)
    assert not root.exists()


@needs_git
def test_ingest_refuses_a_clean_that_changes_the_orientation(monkeypatch, tmp_path):
    # The same picture at one quality encodes to the same image data, so these two differ only
    # in the orientation tag, 6 against 1: the same pixels, shown turned a quarter.
    source = write(tmp_path / "p.jpg", jpeg(ex=exif(orientation=6), extras=False))
    upright = jpeg(ex=exif(orientation=1), extras=False)
    real = pi.clean_copy
    monkeypatch.setattr(pi, "clean_copy", lambda data: real(upright))
    with pytest.raises(pi.IntakeError, match="orientation"):
        pi.ingest(source, intake(), tmp_path / "private")
    assert not (tmp_path / "private").exists()


@needs_git
def test_unreadable_photo_and_malformed_claims_are_refused(tmp_path):
    data = plain_png()
    start = data.index(b"IDAT") - 4
    end = start + 12 + int.from_bytes(data[start:start + 4], "big")
    broken = write(tmp_path / "b.png", data[:start] + chunk(b"IDAT", b"not zlib data") + data[end:])
    with pytest.raises(pi.IntakeError, match="cannot read"):
        pi.ingest(broken, intake(capture="direct_screenshot", device_class="phone"),
                  tmp_path / "private")
    with pytest.raises(pi.IntakeError, match="JSON object"):
        pi.ingest(write(tmp_path / "p.jpg", jpeg(extras=False)), intake(), tmp_path / "private",
                  claims=[{"provenance": "proposed-a"}])
    assert not (tmp_path / "private").exists()


# ---------------------------------------------------------------------------------------------
# The root
# ---------------------------------------------------------------------------------------------


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
def test_root_must_sit_in_the_private_tier(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    write(repo / ".gitignore", b"build/\nlocal-photos/\ncorpus/private/\n")
    photo = write(tmp_path / "p.jpg", jpeg(extras=False))
    # build/ is ignored but outside corpus-guard's private tier; local-photos/ is the inbox
    # the photos come from, never where the intake writes.
    for root in (repo / "build" / "private", repo / "local-photos" / "private"):
        with pytest.raises(pi.IntakeError, match="private tier"):
            pi.ingest(photo, intake(), root)
    # Outside any checkout git cannot stage a file, but the folder still names what it holds.
    with pytest.raises(pi.IntakeError, match="named private"):
        pi.ingest(photo, intake(), tmp_path / "elsewhere")
    assert not (repo / "build").exists() and not (repo / "local-photos").exists()
    assert not (tmp_path / "elsewhere").exists()
    pi.ingest(photo, intake(), repo / "corpus" / "private")


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


def test_root_where_git_cannot_answer_is_refused(monkeypatch, tmp_path):
    def broken(cwd, *args):
        # git's answer for a repository another account owns, which hides whether the folder
        # is in a checkout.
        return subprocess.CompletedProcess(["git", *args], 128, "",
                                           "fatal: detected dubious ownership in repository\n")

    monkeypatch.setattr(pi, "_git", broken)
    with pytest.raises(pi.IntakeError, match="cannot tell"):
        pi.check_root(tmp_path / "corpus" / "private")


def test_root_with_no_existing_folder_is_refused(monkeypatch):
    # A drive that is not there: no folder up to its root exists, so the search for one ends.
    monkeypatch.setattr(pi.Path, "exists", lambda self: False)
    with pytest.raises(pi.IntakeError, match="not even its drive"):
        pi.check_root(Path("Z:/corpus/private"))


# ---------------------------------------------------------------------------------------------
# The report: counts per private tier, tier and split, and nothing else
# ---------------------------------------------------------------------------------------------

# Hand-picked digests on each side of the holdout rule: 0x00000003 = 3, 3 % 3 = 0, holdout;
# 0x00000004 = 4, 4 % 3 = 1, dev.
HOLDOUT_SHA = "00000003" + "0" * 56
DEV_SHA = "00000004" + "0" * 56


def manifest_row(**changes) -> dict[str, str]:
    row = dict.fromkeys(pi.COLUMNS, "x")
    row |= {"private_tier": "phone_capture", "tier": "A", "split": "dev", "class": "squares"}
    row |= changes
    if "sha256" not in changes:
        row["sha256"] = HOLDOUT_SHA if row["split"] == "holdout" else DEV_SHA
    return row


def header(out: str = "docs/sprint-5/evidence/D3c-private-tiers.md") -> pi.ReportHeader:
    return pi.ReportHeader(date="2026-10-13", root="<main checkout>/corpus/private", out=out,
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


def test_tally_refuses_a_split_that_disagrees_with_the_received_hash():
    # DEV_SHA reads dev under the rule (4 % 3 = 1), so a row that says holdout is refused,
    # whatever wrote it.
    with pytest.raises(pi.IntakeError, match="split"):
        pi.tally([manifest_row(split="holdout", sha256=DEV_SHA)])


def test_report_holds_aggregates_only():
    secrets = {
        "file": "private/photos/shot-a1b2c3d4e5f6.png",
        "source": "Testshop listing",
        "source_name": "IMG_9876.JPG",
        # Since 16 = 1 (mod 3), a hex number's remainder mod 3 is its digits' sum mod 3:
        # a1b2c3d4 sums to 10 + 1 + 11 + 2 + 12 + 3 + 13 + 4 = 56, and 56 % 3 = 2: dev, the
        # row's split.
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
    assert head.out == "docs/sprint-5/evidence/D3c-private-tiers.md"
    # Nothing that names a photo, a hash of one, or a pixel size.
    assert not re.search(r"[0-9a-f]{64}", text)
    assert not re.search(r"\.(jpe?g|png|heic|heif|webp|gif|tiff?)\b", text, re.IGNORECASE)
    assert not re.search(r"IMG_|image0|local-photos|shot-|cap-", text)
    assert not re.search(r"\b\d{3,5} ?x ?\d{3,5}\b", text)


def recorded_command(text: str) -> list[str]:
    command = re.search(r"^- Command: `(.*)`$", text, re.MULTILINE).group(1)
    words = shlex.split(command)
    assert words[:2] == [".venv/Scripts/python", "scripts/eval/private_intake.py"]
    return words[2:]


def test_the_recorded_command_parses_with_the_cli_parser():
    # The report records the command that wrote it, so the CLI must accept it as written:
    # the default report path, another path shown as <out>, and the committed report's line.
    for text in (pi.render_report(header(), pi.tally([])),
                 pi.render_report(header(out="<out>"), pi.tally([])),
                 REPORT.read_text(encoding="utf-8")):
        args = pi.build_parser().parse_args(recorded_command(text))
        assert args.command == "report"


@needs_git
def test_report_runs_through_main(monkeypatch, tmp_path):
    root = tmp_path / "private"
    monkeypatch.setattr(pi, "default_root", lambda: root)
    out = tmp_path / "report.md"
    assert pi.main(["report", "--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    head, table = pi.parse_report(text)
    # No manifest yet, so all 16 cells read 0; the root is the CLI's own, and a report written
    # anywhere but the committed path shows its path as <out>.
    assert len(table) == 16 and sum(table.values()) == 0
    assert (head.root, head.out) == ("<main checkout>/corpus/private", "<out>")
    assert pi.render_report(head, table) == text
    assert pi.build_parser().parse_args(recorded_command(text)).out == Path("<out>")


@needs_git
def test_ingest_runs_through_main(monkeypatch, tmp_path, capsys):
    root = tmp_path / "private"
    monkeypatch.setattr(pi, "default_root", lambda: root)
    photo = write(tmp_path / "in" / "p.jpg", jpeg(extras=False))
    argv = ["ingest", str(photo), "--source", "test-phone", "--capture", "camera",
            "--ownership", "owned by the tester", "--tier", "A", "--class", "squares"]
    assert pi.main(argv) == 0
    (row,) = pi.read_manifest(root)
    assert row["sha256"] == sha(photo.read_bytes())
    assert pi.main(argv) == 1
    assert "refused: this photo is already ingested" in capsys.readouterr().err


def test_report_with_free_text_in_its_header_does_not_parse():
    text = pi.render_report(header(), pi.tally([]))
    assert pi.parse_report(text)[0] == header()
    for leaked in (text.replace("d3c/qrep/", "Testshop.Aunt-Testperson/qrep/"),
                   text.replace("--out docs/sprint-5/evidence/D3c-private-tiers.md",
                                "--out Testshop/listing.md")):
        with pytest.raises(pi.IntakeError):
            pi.parse_report(leaked)
