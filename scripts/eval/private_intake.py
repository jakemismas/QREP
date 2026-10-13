"""Private tiers: ingest shop screenshots and real phone captures without letting them reach git.

These photos show other people's designs and possibly people, so they live only in the main
checkout's gitignored corpus/private/ (plan sections 5.D and 8). For each photo the intake:

- refuses a root that git does not ignore, that sits in a linked worktree, or where git cannot
  answer, so nothing it writes can be staged or left behind for a worktree's teardown, and puts
  a `.gitignore` of `*` in the root so even an old checkout without the ignore rules skips it;
- stores a copy whose metadata is rebuilt from an allowlist: make, model and orientation
  survive, and everything else (the GPS IFD, the Exif sub-IFD, IFD1 and its thumbnail, XMP,
  IPTC, comments, PNG text chunks, JFIF thumbnails and the secondary images an iPhone JPEG
  carries after its primary image) is dropped without re-encoding a pixel. The copy is then
  re-read and refused if any metadata beyond the allowlist, or other pixels, come back;
- binds everything to that stored copy: the corpus never keeps the received file, so the
  manifest's sha256, the annotation's sha256, the D3a holdout rule and the dev annotate page
  all read the stored copy's hash, and received_sha256 only catches a file that arrives twice;
- records the capture, so a screenshot never counts as a phone capture: the private tier comes
  from it, and a capture that contradicts the file's own metadata needs the operator's word;
- appends a row to corpus/private/manifest.csv and writes a D3a annotation sidecar,
  corpus/private/annotations/<stem>.json, for the proposals and the dev annotate page.

The report subcommand writes docs/sprint-5/evidence/D3c-private-tiers.md, which holds counts per
private tier, tier and split and nothing else; tests/eval/test_private_intake.py parses it back.

Run from any checkout; both commands use the main checkout's corpus/private/, found through git,
and take no other root, so a private photo cannot be written anywhere else from the command line:
  python scripts/eval/private_intake.py ingest PHOTO --source S --capture C --ownership O \\
      --tier T --class K [--device-class D] [--capture-confirmed] [--claims F] [--regression F]
  python scripts/eval/private_intake.py report
"""

import argparse
import csv
import datetime
import hashlib
import io
import json
import math
import os
import re
import subprocess
import sys
import zlib
from dataclasses import dataclass
from pathlib import Path

from PIL import Image
from pydantic import ValidationError

from corpus_fetch import CLASSES_BY_TIER
from qrep_eval import annotation as an

COLUMNS = (
    "file", "license", "source", "source_name", "sha256", "received_sha256", "px_w", "px_h",
    "orientation", "capture", "capture_evidence", "device_make", "device_model", "device_class",
    "ownership", "private_tier", "tier", "class", "split", "ingested",
)
# Not a license corpus-guard admits, so a private row can never license a committed file.
LICENSE = "private"
PRIVATE_TIERS = {
    "camera": "phone_capture",
    "direct_screenshot": "screenshot",
    "nested_screenshot": "screenshot",
}
PRIVATE_TIER_NAMES = ("phone_capture", "screenshot")
STEM_PREFIX = {"phone_capture": "cap", "screenshot": "shot"}
TIERS = tuple(CLASSES_BY_TIER)
SPLITS = ("dev", "holdout")
# The intake records proposals and copies of a source's record; truth comes only from Jake on
# the dev annotate page and from D3b's gold layouts (plan section 8.2). It sets the capture and
# device class itself as screened: the intake is the screen for a private photo, and both come
# from how the photo was acquired (with the file's metadata as evidence when it has any, in the
# capture_evidence column), as a museum photo's come from its source.
CLAIM_PROVENANCES = ("proposed-a", "proposed-b", "source-record")
OWN_CLAIMS = ("capture", "device_class")

MAKE, MODEL, ORIENTATION = 0x010F, 0x0110, 0x0112
KEPT_TAGS = (MAKE, MODEL, ORIENTATION)
EXIF_IFD = 0x8769
EXPOSURE_TAGS = (0x829A, 0x829D)  # ExposureTime, FNumber: every camera writes them
USER_COMMENT = 0x9286
METADATA_KEYS = ("xmp", "XML:com.adobe.xmp", "photoshop", "comment", "Comment", "mp", "mpinfo",
                 "flashpix")

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Image data and color only, the chunks a decoder needs to show the same pixels, each with the
# payload length its definition allows (None: any), so no kept chunk can carry extra bytes.
PNG_KEEP = {b"IHDR": (13,), b"PLTE": None, b"IDAT": None, b"IEND": (0,), b"tRNS": None,
            b"cHRM": (32,), b"gAMA": (4,), b"iCCP": None, b"sBIT": (1, 2, 3, 4), b"sRGB": (1,),
            b"pHYs": (9,), b"cICP": (4,), b"mDCV": (24,), b"cLLI": (8,)}
SOI, EOI, SOS = 0xD8, 0xD9, 0xDA
STANDALONE = frozenset(range(0xD0, 0xD8)) | {0x01}
# JFIF's APP0 up to its density fields (identifier, version, units, two densities), and Adobe's
# APP14 through its color transform byte; the bytes past them are a thumbnail or padding.
JFIF_HEAD, ADOBE_LENGTH = 12, 12

REPORT = Path("docs/sprint-5/evidence/D3c-private-tiers.md")
MAIN_ROOT = "<main checkout>/corpus/private"
OTHER_ROOT = "<root>"
# The checkout folder the report names: the main checkout, or a worktree named for its ticket.
QREP_SHOWN = re.compile(r"(QREP|[a-z][a-z0-9]{0,7})/qrep/__init__\.py")


class IntakeError(Exception):
    """The intake refused a photo or a root; nothing was written."""


@dataclass(frozen=True)
class Intake:
    source: str
    capture: str
    ownership: str
    tier: str
    klass: str
    device_class: str = ""
    capture_confirmed: bool = False


def split_of(sha256: str) -> str:
    return "holdout" if an.in_holdout(sha256) else "dev"


def private_tier(capture: str) -> str:
    if capture not in PRIVATE_TIERS:
        raise IntakeError(
            f"capture {capture!r} is not one of {', '.join(PRIVATE_TIERS)}; a private photo "
            "records how it was captured, and is never a museum scan")
    return PRIVATE_TIERS[capture]


def detect_format(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "JPEG"
    if data.startswith(PNG_SIGNATURE):
        return "PNG"
    raise IntakeError("only JPEG and PNG photos are accepted (export a HEIC photo as JPEG)")


# ---------------------------------------------------------------------------------------------
# The stored copy
# ---------------------------------------------------------------------------------------------


def _split_jpeg(data: bytes) -> tuple[list[tuple[int | None, bytes]], bytes]:
    """The primary image as (marker, bytes) parts in file order, scan data as (None, bytes),
    ending with the end-of-image marker, and whatever follows it."""
    if not data.startswith(b"\xff\xd8"):
        raise IntakeError("not a JPEG: no start-of-image marker")
    parts: list[tuple[int | None, bytes]] = []
    i, in_scan = 2, False
    while True:
        if in_scan:
            j = i
            while True:
                k = data.find(b"\xff", j)
                if k < 0 or k + 1 >= len(data):
                    raise IntakeError("the JPEG has no end-of-image marker")
                following = data[k + 1]
                if following == 0x00 or following in STANDALONE:
                    j = k + 2  # a stuffed 0xff or a restart marker belongs to the scan
                elif following == 0xFF:
                    j = k + 1
                else:
                    break
            if k > i:
                parts.append((None, data[i:k]))
            i = k
        if i + 1 >= len(data) or data[i] != 0xFF:
            raise IntakeError("the JPEG is malformed: a marker was expected")
        while i + 2 < len(data) and data[i + 1] == 0xFF:
            i += 1
        marker = data[i + 1]
        if marker == EOI:
            parts.append((EOI, data[i:i + 2]))
            return parts, data[i + 2:]
        if marker in STANDALONE:
            parts.append((marker, data[i:i + 2]))
            i += 2
            continue
        length = int.from_bytes(data[i + 2:i + 4], "big")
        if length < 2 or i + 2 + length > len(data):
            raise IntakeError("the JPEG is malformed: a segment runs past the end of the file")
        parts.append((marker, data[i:i + 2 + length]))
        i += 2 + length
        in_scan = in_scan or marker == SOS


def _segment(marker: int, payload: bytes) -> bytes:
    return bytes([0xFF, marker]) + (len(payload) + 2).to_bytes(2, "big") + payload


def _jpeg_kept(marker: int | None, part: bytes) -> bytes | None:
    """The part as the stored copy carries it, or None when it is dropped."""
    if marker is None or marker in (SOS, EOI) or marker in STANDALONE:
        return part
    if 0xC0 <= marker <= 0xCF and marker != 0xC8:  # frame headers, Huffman and arithmetic tables
        return part
    if marker in (0xDB, 0xDD):  # quantization tables, restart interval
        return part
    payload = part[4:]
    if marker == 0xE0 and payload.startswith(b"JFIF\x00") and len(payload) >= JFIF_HEAD + 2:
        # The density fields stay; the thumbnail goes, and its size bytes read 0 x 0.
        return _segment(0xE0, payload[:JFIF_HEAD] + b"\x00\x00")
    if marker == 0xE2 and payload.startswith(b"ICC_PROFILE\x00"):
        return part  # color data a decoder applies; phones write a standard profile here
    if marker == 0xEE and payload.startswith(b"Adobe") and len(payload) >= ADOBE_LENGTH:
        return _segment(0xEE, payload[:ADOBE_LENGTH])  # its color transform, which decoding needs
    return None


def _split_png(data: bytes) -> tuple[list[tuple[bytes, bytes]], bytes]:
    if not data.startswith(PNG_SIGNATURE):
        raise IntakeError("not a PNG: no signature")
    chunks, i = [], len(PNG_SIGNATURE)
    while True:
        if i + 12 > len(data):
            raise IntakeError("the PNG has no IEND chunk")
        length = int.from_bytes(data[i:i + 4], "big")
        kind, end = data[i + 4:i + 8], i + 12 + length
        if end > len(data):
            raise IntakeError("the PNG is malformed: a chunk runs past the end of the file")
        chunks.append((kind, data[i:end]))
        i = end
        if kind == b"IEND":
            return chunks, data[i:]


def _png_keeps(kind: bytes, chunk: bytes) -> bool:
    if kind not in PNG_KEEP:
        return False
    lengths = PNG_KEEP[kind]
    return lengths is None or len(chunk) - 12 in lengths


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    crc = zlib.crc32(kind + payload).to_bytes(4, "big")
    return len(payload).to_bytes(4, "big") + kind + payload + crc


def _raw_exif(im: Image.Image) -> Image.Exif:
    """The file's own EXIF block. Image.getexif() also copies an XMP orientation into its
    answer, which would promote an orientation no viewer applies into the stored copy."""
    exif = Image.Exif()
    raw = im.info.get("exif")
    if raw:
        exif.load(raw)
    return exif


def _allowlisted(source: Image.Exif) -> bytes | None:
    """Make, model and orientation as a fresh EXIF block ("Exif\\0\\0" first), or None when
    the source has none of them."""
    kept = Image.Exif()
    for tag in KEPT_TAGS:
        if tag in source:
            kept[tag] = source[tag]
    return kept.tobytes() if len(kept) else None


def clean_copy(data: bytes) -> bytes:
    """The photo with its metadata rebuilt from the allowlist and its image data byte for byte."""
    fmt = detect_format(data)
    with Image.open(io.BytesIO(data)) as im:
        exif = _allowlisted(_raw_exif(im))
    if fmt == "JPEG":
        parts, _after_end = _split_jpeg(data)
        kept = [(marker, _jpeg_kept(marker, part)) for marker, part in parts]
        # JFIF wants its APP0 first, and EXIF its APP1 next.
        app0 = b"".join(part for marker, part in kept if marker == 0xE0 and part)
        rest = b"".join(part for marker, part in kept if marker != 0xE0 and part)
        app1 = b"" if exif is None else _segment(0xE1, exif)
        return b"\xff\xd8" + app0 + app1 + rest
    chunks, _after_end = _split_png(data)
    out, placed = [PNG_SIGNATURE], exif is None
    for kind, chunk in chunks:
        if kind == b"IDAT" and not placed:
            out.append(_png_chunk(b"eXIf", exif[len(b"Exif\x00\x00"):]))
            placed = True
        if _png_keeps(kind, chunk):
            out.append(chunk)
    return b"".join(out)


def location_traces(data: bytes) -> list[str]:
    """What a photo carries beyond the allowlist, in any block; [] when nothing."""
    fmt = detect_format(data)
    traces = []
    with Image.open(io.BytesIO(data)) as im:
        exif = _raw_exif(im)
        extra = sorted(set(exif) - set(KEPT_TAGS))
        if extra:
            traces.append("EXIF tags " + ", ".join(f"0x{tag:04x}" for tag in extra))
        raw = im.info.get("exif")
        # Byte for byte the block the allowlist builds from those tags, so nothing hides in a
        # sub-IFD, IFD1, its thumbnail or the gaps between them.
        if raw and raw != _allowlisted(exif) and not extra:
            traces.append("an EXIF block with more than make, model and orientation")
        traces += [f"{key} metadata" for key in METADATA_KEYS if key in im.info]
        if fmt == "PNG" and im.text:
            traces.append("PNG text chunks")
    if fmt == "JPEG":
        parts, after_end = _split_jpeg(data)
        app1 = [part for marker, part in parts if marker == 0xE1]
        changed = [marker for marker, part in parts
                   if marker != 0xE1 and _jpeg_kept(marker, part) != part]
        if changed:
            traces.append("JPEG segments " + ", ".join(f"0xff{m:02x}" for m in changed))
        if len(app1) > 1 or any(not part[4:].startswith(b"Exif\x00\x00") for part in app1):
            traces.append("an APP1 segment other than one EXIF block")
    else:
        chunks, after_end = _split_png(data)
        dropped = sorted({kind.decode("latin-1") for kind, chunk in chunks
                          if kind != b"eXIf" and not _png_keeps(kind, chunk)})
        if dropped:
            traces.append("PNG chunks " + ", ".join(dropped))
    if after_end:
        traces.append(f"{len(after_end)} bytes after the image's end")
    return traces


def _pixels(data: bytes) -> tuple[str, tuple[int, int], bytes]:
    with Image.open(io.BytesIO(data)) as im:
        return im.mode, im.size, im.tobytes()


# ---------------------------------------------------------------------------------------------
# The root
# ---------------------------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    except OSError as err:
        raise IntakeError(f"git is needed to prove the root cannot be staged: {err}") from err


def default_root() -> Path:
    """The main checkout's corpus/private/, from any checkout of this repository."""
    found = _git(Path(__file__).resolve().parent, "rev-parse", "--path-format=absolute",
                 "--git-common-dir")
    if found.returncode:
        raise IntakeError(f"cannot find the main checkout: {found.stderr.strip()}")
    return Path(found.stdout.strip()).resolve().parent / "corpus" / "private"


def check_root(root: Path) -> Path:
    """root made absolute, or IntakeError when git could stage what is written there."""
    root = Path(os.path.abspath(root))
    probe = root
    while not probe.exists():
        if probe.parent == probe:
            raise IntakeError(f"no folder of {root} exists, not even its drive")
        probe = probe.parent
    top = _git(probe, "rev-parse", "--show-toplevel")
    if top.returncode:
        # Only git's own answer that no repository holds the folder clears it; any other
        # failure (dubious ownership, a broken config) could hide a checkout, so it refuses.
        if "not a git repository" not in top.stderr:
            raise IntakeError(f"git cannot tell whether {root} is in a checkout: "
                              f"{top.stderr.strip()}")
        return root
    toplevel = Path(top.stdout.strip()).resolve()
    common = _git(probe, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if common.returncode or Path(common.stdout.strip()).resolve().parent != toplevel:
        raise IntakeError(
            f"{root} is inside a linked worktree; private photos live only in the main "
            "checkout's corpus/private/, which no worktree teardown touches")
    relative = Path(os.path.relpath(root.resolve(), toplevel)).as_posix()
    if _git(toplevel, "check-ignore", "-q", f"{relative}/probe").returncode:
        raise IntakeError(
            f"git does not ignore {relative}/ in {toplevel}, so a photo written there could be "
            "staged; use the main checkout's corpus/private/")
    return root


# ---------------------------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------------------------


def read_manifest(root: Path) -> list[dict[str, str]]:
    path = Path(root) / "manifest.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise IntakeError(f"{path} does not have the private manifest's columns")
        return list(reader)


def _write_manifest(root: Path, rows: list[dict[str, str]]) -> None:
    path = root / "manifest.csv"
    part = path.with_suffix(".csv.part")
    with part.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(part, path)


def _write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    part.write_bytes(data)
    os.replace(part, path)


def _text(value) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return str(value).strip("\x00 \t\r\n") if value is not None else ""


def _check_intake(intake: Intake) -> str:
    tier = private_tier(intake.capture)
    if intake.tier not in CLASSES_BY_TIER:
        raise IntakeError(f"tier {intake.tier!r} is not one of {', '.join(TIERS)}")
    if intake.klass not in CLASSES_BY_TIER[intake.tier]:
        raise IntakeError(f"class {intake.klass!r} is not a tier {intake.tier} class: "
                          f"{', '.join(CLASSES_BY_TIER[intake.tier])}")
    for name in ("source", "ownership"):
        if not getattr(intake, name).strip():
            raise IntakeError(f"{name} must not be blank")
    return tier


def _capture_evidence(intake: Intake, exif_ifd: dict, xmp: bytes) -> str:
    exposure = any(tag in exif_ifd for tag in EXPOSURE_TAGS)
    comment = exif_ifd.get(USER_COMMENT, b"")
    comment = comment if isinstance(comment, bytes) else str(comment).encode()
    # iOS marks a screenshot in the EXIF user comment, and in a PNG's XMP.
    marked = b"screenshot" in comment.lower() or b"screenshot" in xmp.lower()
    if intake.capture == "camera":
        if marked:
            raise IntakeError("the file's metadata marks it a screenshot, and a screenshot "
                              "never counts as a phone capture")
        if not exposure and not intake.capture_confirmed:
            raise IntakeError("a camera capture without camera exposure data (ExposureTime or "
                              "FNumber), which messaging apps strip; send the original, or pass "
                              "--capture-confirmed if you took this photo with a camera")
        return "exif" if exposure else "operator"
    if exposure and not intake.capture_confirmed:
        raise IntakeError("a screenshot that carries camera exposure data; check the capture, "
                          "or pass --capture-confirmed")
    return "exif" if marked else "operator"


def _device_class(intake: Intake, model: str) -> str:
    derived = ("phone" if model.startswith("iPhone")
               else "tablet" if model.startswith("iPad") else "")
    if intake.device_class and derived and intake.device_class != derived:
        raise IntakeError(f"the EXIF model {model!r} is a {derived}, not a "
                          f"{intake.device_class}; check the device class")
    device = intake.device_class or derived
    if not device:
        raise IntakeError("the EXIF names no device this script knows; pass --device-class")
    if device not in an.DEVICE_CLASSES or device == "museum":
        raise IntakeError(f"device class {device!r} is not one of "
                          f"{', '.join(d for d in an.DEVICE_CLASSES if d != 'museum')}")
    return device


def _check_claims(claims) -> dict:
    if not isinstance(claims, dict):
        raise IntakeError("claims must be a JSON object of claim lists")
    for field, entries in claims.items():
        if field not in an.CLAIM_FIELDS or field in OWN_CLAIMS:
            raise IntakeError(f"{field!r} is not a claim field the intake accepts")
        if not isinstance(entries, list):
            raise IntakeError(f"{field} must be a list of claims")
        for entry in entries:
            code = entry.get("provenance") if isinstance(entry, dict) else None
            if code in an.TRUTH:
                raise IntakeError(f"{field} claims {code}, which is gate truth: truth comes only "
                                  "from the dev annotate page and D3b's gold layouts")
            if code not in CLAIM_PROVENANCES:
                raise IntakeError(f"{field} claims provenance {code!r}; the intake accepts "
                                  f"{', '.join(CLAIM_PROVENANCES)}")
    return claims


def _check_pins(pins) -> list:
    def number(value) -> bool:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(
            value)

    if not isinstance(pins, list) or not pins:
        raise IntakeError("regression pins must be a non-empty list")
    for pin in pins:
        space = pin.get("space") if isinstance(pin, dict) else None
        corners = pin.get("corners") if isinstance(pin, dict) else None
        if not (isinstance(pin, dict) and isinstance(pin.get("note"), str) and pin["note"].strip()
                and isinstance(space, list) and len(space) == 2 and all(number(n) for n in space)
                and isinstance(corners, list) and len(corners) == 4
                and all(isinstance(c, list) and len(c) == 2 and all(number(n) for n in c)
                        for c in corners)):
            raise IntakeError("each regression pin set needs a note, a [width, height] space and "
                              "four [x, y] corners")
    return pins


def ingest(photo: Path, intake: Intake, root: Path, *, today: str | None = None,
           claims: dict | None = None, regression: list | None = None) -> dict[str, str]:
    """Store one private photo and its sidecars, and return its new manifest row.

    Every check runs before the first write, so a refused photo leaves the root as it was."""
    tier = _check_intake(intake)
    claims = _check_claims({} if claims is None else claims)
    if regression is not None:
        _check_pins(regression)
    root = check_root(root)
    photo = Path(photo)
    data = photo.read_bytes()
    fmt = detect_format(data)
    received = hashlib.sha256(data).hexdigest()
    try:
        with Image.open(io.BytesIO(data)) as im:
            exif = _raw_exif(im)
            exif_ifd = dict(exif.get_ifd(EXIF_IFD))
            xmp = im.info.get("xmp", im.info.get("XML:com.adobe.xmp", b""))
            width, height = im.size
        stored = clean_copy(data)
        traces = location_traces(stored)
        same_pixels = _pixels(stored) == _pixels(data)
    except (OSError, SyntaxError, ValueError) as err:
        raise IntakeError(f"Pillow cannot read this photo whole: {err}") from err
    if traces:
        raise IntakeError(f"metadata survived the clean ({'; '.join(traces)}); nothing stored")
    if not same_pixels:
        raise IntakeError("the stored copy decodes to other pixels; nothing stored")
    sha = hashlib.sha256(stored).hexdigest()
    rows = read_manifest(root)
    for row in rows:
        if received in (row["received_sha256"], row["sha256"]) or sha == row["sha256"]:
            raise IntakeError(f"this photo is already ingested as {row['file']}")

    xmp = xmp if isinstance(xmp, bytes) else str(xmp).encode()
    evidence = _capture_evidence(intake, exif_ifd, xmp)
    make, model = _text(exif.get(MAKE)), _text(exif.get(MODEL))
    device = _device_class(intake, model)
    orientation = exif.get(ORIENTATION, 1)
    orientation = orientation if orientation in range(1, 9) else 1

    stem = f"{STEM_PREFIX[tier]}-{sha[:12]}"
    file = f"private/photos/{stem}{'.jpg' if fmt == 'JPEG' else '.png'}"
    # The canvas is the stored pixels, which annotations index whatever the orientation says
    # (corpus/README.md, Annotations; the dev page's orientation.ts); the row keeps the tag.
    doc = {
        "schema_version": an.SCHEMA_VERSION,
        "photo": file,
        "sha256": sha,
        "canvas": [width, height],
        "capture": [{"provenance": "screened", "value": intake.capture}],
        "device_class": [{"provenance": "screened", "value": device}],
    } | claims
    try:
        an.Annotation.model_validate_json(json.dumps(doc))
    except ValidationError as err:
        raise IntakeError(f"the sidecar is not a valid annotation: {err}") from err

    row = {
        "file": file,
        "license": LICENSE,
        "source": intake.source.strip(),
        "source_name": photo.name,
        "sha256": sha,
        "received_sha256": received,
        "px_w": str(width),
        "px_h": str(height),
        "orientation": str(orientation),
        "capture": intake.capture,
        "capture_evidence": evidence,
        "device_make": make or "unknown",
        "device_model": model or "unknown",
        "device_class": device,
        "ownership": intake.ownership.strip(),
        "private_tier": tier,
        "tier": intake.tier,
        "class": intake.klass,
        "split": split_of(sha),
        "ingested": today or datetime.date.today().isoformat(),
    }
    # The manifest row goes last, so a run that dies midway leaves no row for a missing file,
    # and running it again rewrites the same files.
    if not (root / ".gitignore").exists():
        _write(root / ".gitignore", b"*\n")
    _write(root / "photos" / Path(file).name, stored)
    _write(root / "annotations" / f"{stem}.json",
           (json.dumps(doc, indent=2) + "\n").encode("utf-8"))
    if regression is not None:
        kept = {"photo": file, "sha256": sha, "pins": regression}
        _write(root / "regression" / f"{stem}.json",
               (json.dumps(kept, indent=2) + "\n").encode("utf-8"))
    _write_manifest(root, rows + [row])
    return row


# ---------------------------------------------------------------------------------------------
# The report: counts only
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportHeader:
    date: str
    root: str
    qrep: str
    sha: str
    clean: bool


def tally(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], int]:
    table = {(p, t, s): 0 for p in PRIVATE_TIER_NAMES for t in TIERS for s in SPLITS}
    for row in rows:
        key = (row["private_tier"], row["tier"], row["split"])
        if key not in table:
            raise IntakeError(f"a manifest row has an unknown private tier, tier or split: {key}")
        table[key] += 1
    return table


INTRO = """\
Private-tier counts for issue #165 (plan ticket D3c). The private tiers hold shop screenshots and
real phone captures, which stay out of the repo because they show other people's designs and
possibly people (plan section 8). This report counts them and names no image, file, shop or
person: `tests/eval/test_private_intake.py` parses it back to its counts and re-renders it byte
for byte, so it can hold nothing else.

- The private tier comes from the capture recorded for every photo: a camera capture is
  `phone_capture`, and a direct or nested screenshot is `screenshot`, so a screenshot never
  counts as a phone capture.
- The tier is D3a's (A clean in scope, B in-scope stress, R refusal, X excluded), and the split
  is D3a's holdout rule (corpus/README.md) applied to the stored copy's sha256. The run reads
  the private manifest only.
- Targets (plan section 9, item 5): at least 20 in-scope phone captures and at least 10
  in-scope shop screenshots. The phone tier reads unmeasured below 10 photos, and the release
  holds until it has 10 (plan section 7.2).
"""


def _command(root: str) -> str:
    return (f".venv/Scripts/python scripts/eval/private_intake.py report --root {root} "
            f"--out {REPORT.as_posix()}")


def render_report(header: ReportHeader, table: dict[tuple[str, str, str], int]) -> str:
    total = sum(table.values())
    lines = [
        "# D3c: private tiers",
        "",
        f"- Date: {header.date}",
        f"- Command: `{_command(header.root)}`",
        f"- qrep: `{header.qrep}`",
        f"- Git SHA: `{header.sha}`, {'clean tree' if header.clean else 'uncommitted changes'}",
        f"- Inputs: the private manifest `{header.root}/manifest.csv` (gitignored, never "
        f"committed), {total} {'row' if total == 1 else 'rows'}",
        "<!-- Run header above, generated by scripts/eval/private_intake.py report. -->",
        "",
        INTRO.rstrip("\n"),
        "",
        "| Private tier | Tier | Dev | Holdout | Total |",
        "|---|---|---|---|---|",
    ]

    def cells(label_a: str, label_b: str, dev: int, holdout: int) -> str:
        return f"| {label_a} | {label_b} | {dev} | {holdout} | {dev + holdout} |"

    for p in PRIVATE_TIER_NAMES:
        for t in TIERS:
            lines.append(cells(p, t, table[(p, t, "dev")], table[(p, t, "holdout")]))
    for p in PRIVATE_TIER_NAMES:
        lines.append(cells(p, "in scope (A and B)",
                           *(sum(table[(p, t, s)] for t in ("A", "B")) for s in SPLITS)))
    lines.append(cells("all", "all", *(sum(table[(p, t, s)] for p in PRIVATE_TIER_NAMES
                                           for t in TIERS) for s in SPLITS)))
    return "\n".join(lines) + "\n"


def parse_report(text: str) -> tuple[ReportHeader, dict[tuple[str, str, str], int]]:
    """The header and counts a rendered report holds; render_report(*parse_report(t)) is t
    exactly when t holds nothing else. Every header field is a fixed vocabulary or pattern."""

    def field(pattern: str) -> re.Match:
        found = re.search(pattern, text, re.MULTILINE)
        if not found:
            raise IntakeError(f"the report has no line matching {pattern!r}")
        return found

    roots = "|".join(re.escape(r) for r in (MAIN_ROOT, OTHER_ROOT))
    root = field(rf"^- Command: `.* --root ({roots}) --out ").group(1)
    sha = field(r"^- Git SHA: `([0-9a-f]{40})`, (clean tree|uncommitted changes)$")
    header = ReportHeader(
        date=field(r"^- Date: (\d{4}-\d{2}-\d{2})$").group(1),
        root=root,
        qrep=field(rf"^- qrep: `({QREP_SHOWN.pattern})`$").group(1),
        sha=sha.group(1),
        clean=sha.group(2) == "clean tree",
    )
    table = {}
    for p in PRIVATE_TIER_NAMES:
        for t in TIERS:
            row = field(rf"^\| {p} \| {t} \| (\d+) \| (\d+) \| \d+ \|$")
            table[(p, t, "dev")], table[(p, t, "holdout")] = int(row.group(1)), int(row.group(2))
    return header, table


def run_header(root: Path) -> ReportHeader:
    import qrep

    checkout = Path(__file__).resolve().parents[2]
    head = _git(checkout, "rev-parse", "HEAD")
    status = _git(checkout, "status", "--porcelain")
    if head.returncode or status.returncode:
        raise IntakeError("cannot read the checkout's git state")
    qrep_path = Path(qrep.__file__).resolve()
    try:
        shown = qrep_path.relative_to(checkout.parent).as_posix()
    except ValueError:
        shown = ""
    if not QREP_SHOWN.fullmatch(shown):
        raise IntakeError(f"qrep resolves to {qrep_path}, not this checkout's qrep/")
    main = Path(root).resolve() == default_root().resolve()
    return ReportHeader(date=datetime.date.today().isoformat(),
                        root=MAIN_ROOT if main else OTHER_ROOT, qrep=shown,
                        sha=head.stdout.strip(), clean=not status.stdout.strip())


# ---------------------------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------------------------


def _json_file(path: str | None):
    if path is None:
        return None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        raise IntakeError(f"cannot read {path} as JSON: {err}") from err


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("ingest", help="store one private photo with its manifest row")
    add.add_argument("photo", type=Path)
    add.add_argument("--source", required=True, help="where the photo came from")
    add.add_argument("--capture", required=True, choices=tuple(PRIVATE_TIERS))
    add.add_argument("--ownership", required=True,
                     help="who owns the quilt, and whether its design is traditional")
    add.add_argument("--tier", required=True, choices=TIERS)
    add.add_argument("--class", dest="klass", required=True)
    add.add_argument("--device-class", default="")
    add.add_argument("--capture-confirmed", action="store_true",
                     help="the capture is right although the file's metadata cannot show it")
    add.add_argument("--claims", help="a JSON file of annotation claims (proposals only)")
    add.add_argument("--regression", help="a JSON list of earlier runs' pins to keep")
    rep = sub.add_parser("report", help="write the counts-only report")
    rep.add_argument("--out", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    try:
        root = default_root()
        if args.command == "ingest":
            row = ingest(args.photo, Intake(args.source, args.capture, args.ownership, args.tier,
                                            args.klass, args.device_class,
                                            args.capture_confirmed),
                         root, claims=_json_file(args.claims),
                         regression=_json_file(args.regression))
            print(f"ingested as {row['file']}: {row['private_tier']}, tier {row['tier']}, "
                  f"{row['class']}, split {row['split']}")
        else:
            root = check_root(root)
            text = render_report(run_header(root), tally(read_manifest(root)))
            args.out.write_text(text, encoding="utf-8", newline="\n")
            print(args.out)
    except IntakeError as err:
        print(f"refused: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
