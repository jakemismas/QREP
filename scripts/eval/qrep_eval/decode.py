"""The browser decode path for eval inputs (plan D4b).

The app never hands the read a photo's own bytes: its stage step
(web/src/state/photo.tsx) decodes the file with createImageBitmap, draws the whole
bitmap onto a canvas at targetSize (web/src/model/downscale.ts) and encodes that
canvas as PNG, and decoders differ between runtimes (approaches-31). The browser
driver (scripts/eval/decode/browser_decode.mjs, run by run_decode.py) repeats those
steps in Chromium and WebKit and caches each PNG under <cache>/decoded/<browser>/
with a JSON sidecar. This module checks a sidecar against the job it answers, swaps
a harness unit onto the decoded PNG with its corners scaled by the recorded
factors, and compares native and browser decodes and reads.
"""

import dataclasses
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from qrep_eval import corpus, harness, scoring

BROWSERS = ("chromium", "webkit")
SIDECAR_VERSION = 1
STEPS = ("createImageBitmap(blob); canvas at targetSize(width, height, cap); "
         "drawImage(bitmap, 0, 0, width, height); canvas.toBlob(image/png)")
# drawImage maps the whole bitmap onto the whole canvas, so a recorded factor is a
# ratio of two integers and repeats exactly; this only absorbs JSON float printing.
FACTOR_SLACK = 1e-12
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Rows per band when comparing images, so a 117 MP comparison never holds a widened
# copy of the whole image.
BAND_ROWS = 512


class DecodeMissing(RuntimeError):
    """A unit needs a decoded image that run_decode.py never wrote."""


@dataclass(frozen=True)
class Job:
    """One image for the browser to decode: a source at one cap."""

    key: str
    source: str
    sha256: str
    cap: int | None
    canvas: tuple[int, int]

    def as_json(self) -> dict:
        return {"key": self.key, "source": self.source, "sha256": self.sha256, "cap": self.cap,
                "canvas": list(self.canvas)}


@dataclass(frozen=True)
class Decoded:
    """A checked sidecar: the PNG and its recorded size and factors, or the error the
    browser gave instead."""

    png: Path | None
    size: tuple[int, int] | None
    factors: tuple[float, float] | None
    browser_version: str
    error: str | None
    sidecar: dict


def job_key(photo: str, resolution: str) -> str:
    return f"{photo}__{resolution}"


def decoded_paths(decoded_dir: Path, browser: str, key: str) -> tuple[Path, Path]:
    folder = Path(decoded_dir) / browser
    return folder / f"{key}.png", folder / f"{key}.json"


_SHA_MEMO: dict[tuple[str, int, int], str] = {}


def _sha256(path: Path) -> str:
    stat = path.stat()
    memo = (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    if memo not in _SHA_MEMO:
        _SHA_MEMO[memo] = corpus.sha256_of(path)
    return _SHA_MEMO[memo]


def jobs_for(units) -> list[Job]:
    """One job per photo and resolution that some unit stages, in unit order. A unit
    over the as-fetched budget is never staged (harness.run_unit), so it needs none;
    degradations apply after the decode, so a photo's conditions share one job."""
    jobs: dict[str, Job] = {}
    for unit in units:
        key = job_key(unit.photo, unit.resolution)
        if key in jobs or harness.over_budget(unit):
            continue
        jobs[key] = Job(key=key, source=unit.source, sha256=_sha256(Path(unit.source)), cap=unit.cap,
                        canvas=tuple(unit.canvas))
    return list(jobs.values())


def factors(source_size: tuple[int, int], decoded_size: tuple[int, int]) -> tuple[float, float]:
    """drawImage stretches the whole bitmap onto the whole canvas, so each axis scales
    by its own ratio: x' = x * W'/W, y' = y * H'/H."""
    return decoded_size[0] / source_size[0], decoded_size[1] / source_size[1]


def scale_points(points, recorded: tuple[float, float]) -> list[tuple[float, float]]:
    sx, sy = recorded
    return [(x * sx, y * sy) for x, y in points]


def png_size(path: Path) -> tuple[int, int]:
    """(width, height) from the PNG's IHDR chunk."""
    with Path(path).open("rb") as handle:
        head = handle.read(24)
    if len(head) < 24 or head[:8] != PNG_SIGNATURE or head[12:16] != b"IHDR":
        raise ValueError(f"{path} is not a PNG")
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def _check(condition: bool, key: str, message: str) -> None:
    if not condition:
        raise ValueError(f"{key}: {message}")


def load_decoded(decoded_dir: Path, browser: str, job: Job) -> Decoded:
    """The sidecar for job, checked field by field against the job, the app's
    targetSize and the PNG on disk; any mismatch stops the caller, since a stale or
    foreign decode would score a read of another image."""
    png, side = decoded_paths(decoded_dir, browser, job.key)
    if not side.exists():
        raise DecodeMissing(f"no {browser} decode of {job.key}; run scripts/eval/decode/run_decode.py first")
    sidecar = json.loads(side.read_text(encoding="utf-8"))
    key = job.key
    _check(sidecar.get("version") == SIDECAR_VERSION, key,
           f"sidecar version {sidecar.get('version')!r}, expected {SIDECAR_VERSION}")
    _check(sidecar.get("browser") == browser, key, f"sidecar browser {sidecar.get('browser')!r}, expected {browser}")
    _check(sidecar.get("source_sha256") == job.sha256, key, "the sidecar's source_sha256 is not the source's")
    _check(sidecar.get("cap") == job.cap, key, f"sidecar cap {sidecar.get('cap')!r}, the job's is {job.cap!r}")
    _check(sidecar.get("key") == job.key, key, f"the sidecar answers job {sidecar.get('key')!r}")
    version = str(sidecar.get("browser_version"))
    if sidecar.get("error") is not None:
        return Decoded(None, None, None, version, str(sidecar["error"]), sidecar)
    # Another decode path (the crop-aware one of #101, say) writes other steps.
    _check(sidecar.get("steps") == STEPS, key, f"decode steps {sidecar.get('steps')!r} are not {STEPS!r}")
    source = tuple(sidecar.get("source_size") or ())
    _check(source == tuple(job.canvas), key,
           f"the browser decoded a source size of {source}, the canvas is {tuple(job.canvas)}")
    size = tuple(sidecar.get("decoded_size") or ())
    target = corpus.cap_size(*job.canvas, job.cap)
    _check(size == target, key, f"decoded size {size} is not targetSize {target}")
    longest = max(job.canvas)
    scale = job.cap / longest if job.cap is not None and longest > job.cap else 1.0
    _check(abs(float(sidecar.get("scale", -1)) - scale) <= FACTOR_SLACK, key,
           f"recorded scale {sidecar.get('scale')!r} is not the cap's {scale}")
    recorded = tuple(sidecar.get("factors") or ())
    expected = factors(job.canvas, size)
    _check(len(recorded) == 2 and all(abs(a - b) <= FACTOR_SLACK for a, b in zip(recorded, expected)), key,
           f"recorded factors {recorded} are not decoded / source size {expected}")
    _check(png.exists(), key, f"the sidecar names a PNG that is missing: {png.name}")
    on_disk = png_size(png)
    _check(on_disk == size, key, f"the PNG is {on_disk[0]} x {on_disk[1]}, its sidecar says {size}")
    _check(_sha256(png) == sidecar.get("png_sha256"), key, "png_sha256 does not match the PNG on disk")
    return Decoded(png, size, recorded, version, None, sidecar)


def browser_unit(unit: harness.Unit, decoded: Decoded) -> harness.Unit:
    """unit read from the browser's PNG: the canvas is the decoded size, nothing is
    left to cap, and the truth corners scale by the recorded factors, so a degradation
    and every simulated corner land where they would on the native staged image."""
    corners = unit.truth.corners
    truth = dataclasses.replace(unit.truth, corners=scale_points(corners, decoded.factors) if corners else corners)
    return dataclasses.replace(unit, source=str(decoded.png), canvas=decoded.size, cap=None, truth=truth)


def browser_units(units, decoded_dir: Path, browser: str):
    """(units to read, error rows, browser versions). A unit over the as-fetched budget
    passes through, since the harness skips it before staging. A unit whose image the
    browser failed to decode becomes error rows where its reads would be, as a stage
    error does (harness._unread_rows), so n keeps it."""
    jobs = {job.key: job for job in jobs_for(units)}
    kept, errors, versions = [], [], set()
    for unit in units:
        if harness.over_budget(unit):
            kept.append(unit)
            continue
        decoded = load_decoded(decoded_dir, browser, jobs[job_key(unit.photo, unit.resolution)])
        versions.add(decoded.browser_version)
        if decoded.error is not None:
            result = {"outcome": "error", "error": f"{browser} could not decode the image: {decoded.error}"}
            errors.extend(json.loads(json.dumps(harness._unread_rows(unit, result))))
            continue
        kept.append(browser_unit(unit, decoded))
    return kept, errors, versions


def steps_text() -> str:
    return (f"each image is decoded as the app's stage step does (web/src/state/photo.tsx), {STEPS}, through "
            "Playwright; at full size the canvas takes the image's own size. The reader reads that PNG with "
            "cv2.imread (lossless), degraded where its condition says, and the corners scale by the sidecar's "
            "per-axis factors (decoded / source size)")


def describe(browser: str, versions) -> str:
    return f"browser: {browser} {', '.join(sorted(versions)) or 'unknown'}: {steps_text()}"


def pixel_diff(a: np.ndarray, b: np.ndarray) -> dict:
    """Pixels that differ in any channel, of all pixels, and the largest absolute
    channel difference."""
    if a.shape != b.shape:
        raise ValueError(f"cannot compare images of shape {a.shape} and {b.shape}")
    differing = largest = 0
    for top in range(0, a.shape[0], BAND_ROWS):
        delta = np.abs(a[top:top + BAND_ROWS].astype(np.int16) - b[top:top + BAND_ROWS].astype(np.int16))
        if delta.ndim == 3:
            delta = delta.max(axis=2)
        differing += int(np.count_nonzero(delta))
        largest = max(largest, int(delta.max(initial=0)))
    return {"pixels": int(a.shape[0] * a.shape[1]), "differing": differing, "largest": largest}


def _flagged(reading, r: int, c: int) -> bool:
    """The app's flag: a square below the reader's threshold. A read without
    confidences, or without a threshold, flags nothing."""
    threshold = reading.low_confidence_below
    confidence = reading.confidence
    if threshold is None or not confidence or not all(confidence):
        return False
    return confidence[r][c] < threshold


def pair_fabrics(native_cells, browser_cells, native_colors, browser_colors) -> list[int | None]:
    """Each browser fabric's native partner, one to one, pairing the fabrics that share
    the most squares, then the least total colour distance on a tie. Fabric identity is
    which squares a fabric covers: the browser converts a photo's colour profile and cv2
    does not, so the same fabric can come back a shade off, and two close fabrics paired
    by colour alone could cross. A browser fabric left over maps to None."""
    m, n = len(browser_colors), len(native_colors)
    shared = [[0] * n for _ in range(m)]
    for native_row, browser_row in zip(native_cells, browser_cells):
        for fabric, other in zip(native_row, browser_row):
            if 0 <= other < m and 0 <= fabric < n:
                shared[other][fabric] += 1
    cost = [[scoring.delta_e(scoring.srgb_to_lab(b), scoring.srgb_to_lab(a)) for a in native_colors]
            for b in browser_colors]
    # Exact search over subsets of native fabrics (at most 12, qrep/contract.py
    # FABRICS_MAX), scoring (squares shared, -colour distance).
    states: dict[int, tuple[int, float, tuple]] = {0: (0, 0.0, ())}
    for b in range(m):
        nxt: dict[int, tuple[int, float, tuple]] = {}
        for mask, (agree, distance, pairs) in states.items():
            options = [(mask, (agree, distance, pairs + (None,)))]
            options += [(mask | 1 << a, (agree + shared[b][a], distance - cost[b][a], pairs + (a,)))
                        for a in range(n) if not mask & 1 << a]
            for key, value in options:
                if key not in nxt or value[:2] > nxt[key][:2]:
                    nxt[key] = value
        states = nxt
    return list(max(states.values(), key=lambda v: v[:2])[2]) if m else []


def label_diff(native, browser) -> dict:
    """The browser read against the native read under the G9 rule (plan 7.2): every
    square above the confidence threshold must carry the same fabric. A square counts
    when either read shows it unflagged. Fabrics pair by pair_fabrics, so a reordered
    or slightly shifted palette is no difference, and a browser fabric with no partner
    differs wherever it is used; palette_delta_e reports the largest colour distance
    between paired fabrics."""
    out = {"outcomes": [native.outcome, browser.outcome], "verdicts": [native.verdict, browser.verdict],
           "dims": [[native.rows, native.cols], [browser.rows, browser.cols]], "k": [native.k, browser.k],
           "squares": None, "differing": None, "differing_confident": None, "differing_confident_both": None}
    if native.outcome != browser.outcome:
        return {**out, "match": "outcome", "g9": False}
    if native.outcome not in harness.SHIPS:
        return {**out, "match": "nothing shown", "g9": True, "squares": 0, "differing": 0,
                "differing_confident": 0, "differing_confident_both": 0}
    if native.cells is None or browser.cells is None:
        return {**out, "match": "no cells", "g9": None}
    shape = [len(row) for row in native.cells]
    if shape != [len(row) for row in browser.cells]:
        return {**out, "match": "dims", "g9": False}
    mapping = pair_fabrics(native.cells, browser.cells, native.colors, browser.colors)
    paired = [scoring.delta_e(scoring.srgb_to_lab(browser.colors[b]), scoring.srgb_to_lab(native.colors[a]))
              for b, a in enumerate(mapping) if a is not None]
    differing = confident = both = 0
    for r, (native_row, browser_row) in enumerate(zip(native.cells, browser.cells)):
        for c, (fabric, other) in enumerate(zip(native_row, browser_row)):
            mapped = mapping[other] if 0 <= other < len(mapping) else None
            if mapped == fabric:
                continue
            differing += 1
            shown = (not _flagged(native, r, c), not _flagged(browser, r, c))
            confident += any(shown)
            both += all(shown)
    return {**out, "match": "compared", "g9": confident == 0, "squares": sum(shape), "differing": differing,
            "differing_confident": confident, "differing_confident_both": both,
            "palette_delta_e": round(max(paired, default=0.0), 2)}


def available_memory_gb() -> float:
    """Physical memory available to a new allocation, in GB (2^30 bytes): what the
    run stops on before it starves the machine."""
    if sys.platform == "win32":
        import ctypes

        class _Status(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

        status = _Status()
        status.dwLength = ctypes.sizeof(_Status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("GlobalMemoryStatusEx failed")
        return status.ullAvailPhys / 2**30
    return os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 2**30
