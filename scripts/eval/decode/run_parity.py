"""Native against browser decode on the v0 dev split (plan D4b).

    python scripts/eval/decode/run_parity.py --cache <main checkout>/corpus/private/cache \\
        --out docs/sprint-5/evidence/D4b-decode-parity

Needs run_decode.py's PNGs for both browsers. For every image the eval stages, at
full size and at the 2000 and 1400 caps: the pixels that differ between the native
staged image (harness.stage) and each browser's PNG, and the largest channel
difference. At the read resolutions (default: the two caps the app uses, and the
photoreal fixtures): the auto and auto-corners reads of each decode at true corners,
and their label differences under the G9 rule (decode.label_diff). Reads are cached
under <cache>/decoded/parity-work/, keyed by the qrep tree's git hash and the image's
sha256, so a stopped run resumes. Public rows only, dev split only. Report only.
"""

import argparse
import datetime
import hashlib
import json
import shlex
import statistics
import subprocess
import sys
import tempfile
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import replace
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
REPO = EVAL.parents[1]
for folder in (EVAL, HERE):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import run_decode  # noqa: E402
from qrep_eval import corpus, decode, harness, readers, simulate, stats  # noqa: E402

READERS = ("auto", "auto-corners")
DECODES = ("native", *decode.BROWSERS)
# The eval code a read depends on besides qrep/: staging, the reader wrapper and the
# corner trial. A change to any of them makes every cached read stale.
READ_PATH = ("harness.py", "readers.py", "simulate.py", "corpus.py")
# Exit code for a stop on free memory, which a rerun resumes; any other failure is 1.
MEMORY_STOP = 3
KEEP = ("outcome", "verdict", "rows", "cols", "colors", "cells", "confidence", "low_confidence_below", "seconds")


def _parse(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", type=Path, default=REPO / "corpus")
    p.add_argument("--cache", type=Path, help="the fetched source images (default: <corpus>/private/cache)")
    p.add_argument("--out", required=True, type=Path, help="report path without its .md suffix")
    p.add_argument("--read-resolutions", default="desktop-2000,phone-1400")
    p.add_argument("--workers", type=int, default=1, choices=(1, 2))
    p.add_argument("--min-free-gb", type=float, default=4.0)
    return p.parse_args(argv)


def _git(*args) -> str | None:
    done = subprocess.run(["git", *args], capture_output=True, text=True, cwd=REPO)
    return done.stdout.strip() if done.returncode == 0 else None


def _staged(unit, decoded_dir: Path, name: str, tmp: Path):
    if name != "native":
        job = decode.jobs_for([unit])[0]
        decoded = decode.load_decoded(decoded_dir, name, job)
        if decoded.error is not None:
            raise RuntimeError(f"{name} could not decode the image: {decoded.error}")
        unit = decode.browser_unit(unit, decoded)
    path, size = harness.stage(unit, tmp)
    return unit, path, size


def read_task(task) -> list[dict]:
    """Every reader on one decode of one unit, as run_unit reads at 0 px: auto with no
    corners, auto-corners with the scaled true corners and the given fabric count."""
    unit, name, decoded_dir, workdir = task
    out = []
    with tempfile.TemporaryDirectory(prefix="qrep-eval-", dir=workdir) as tmp:
        try:
            staged, path, size = _staged(unit, decoded_dir, name, Path(tmp))
        except Exception as error:  # noqa: BLE001 - recorded, never swallowed
            return [{"reader": reader, "error": repr(error)} for reader in unit.readers]
        truth = staged.truth
        framed = truth.corners is not None and truth.counts is not None
        corners = None
        if framed:
            corners = harness.scale_corners(truth.corners, staged.canvas, size)
            key = f"{unit.seed}|{unit.photo}|{unit.resolution}|{unit.condition}"
            corners = simulate.corner_trials(corners, (0,), 1, key, bounds=size)[0].corners
        fabrics = harness.given_fabrics(truth, unit.truth_label)
        for reader in unit.readers:
            if reader == "auto-corners" and not framed:
                out.append({"reader": reader, "skipped": harness.SKIP_REASON})
                continue
            given = (corners, fabrics) if reader == "auto-corners" else (None, None)
            try:
                reading = readers.read_auto(path, size, *given)
            except Exception as error:  # noqa: BLE001 - recorded, never swallowed
                out.append({"reader": reader, "error": repr(error)})
                continue
            out.append({"reader": reader, **{k: getattr(reading, k) for k in KEEP}})
    return json.loads(json.dumps(out))


class MemoryStop(RuntimeError):
    pass


def _code_digest() -> str:
    """The qrep tree as committed plus the eval files a read runs through. A dirty
    qrep/ is refused, since its tree hash would not describe what ran."""
    if _git("status", "--porcelain", "--", "qrep/"):
        raise SystemExit("run_parity: qrep/ has uncommitted changes; commit them so cached reads stay keyed")
    import cv2 as cv

    digest = hashlib.sha256(f"{_git('rev-parse', 'HEAD:qrep') or 'unknown'}|cv2 {cv.__version__}".encode())
    for name in READ_PATH:
        digest.update((EVAL / "qrep_eval" / name).read_bytes())
    return digest.hexdigest()[:16]


def _inputs_digest(unit) -> str:
    """What the simulated user gives a read: corners, counts, fabric count, seed."""
    truth = unit.truth
    payload = [truth.corners, truth.counts.model_dump() if truth.counts else None,
               harness.given_fabrics(truth, unit.truth_label), unit.seed, list(unit.readers)]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def _reading(result: dict) -> readers.Reading:
    return readers.Reading(**{k: result[k] for k in KEEP}, cell_size_eighths=None, band_eighths=[],
                           flagged_regions=[], received={})


def _image_id(unit, name: str, jobs: dict, sidecars: dict) -> str:
    job = jobs[decode.job_key(unit.photo, unit.resolution)]
    if name == "native":
        return job.sha256 + f"|{job.cap}"
    sidecar = sidecars[(name, job.key)].sidecar
    # A failed decode has no PNG; read_task records its error as the read's.
    return sidecar.get("png_sha256") or f"error|{sidecar.get('error')}"


def run_reads(units, args, decoded_dir: Path, jobs: dict, sidecars: dict) -> dict:
    """{(photo, resolution, decode): results}, resuming from the work cache."""
    work = decoded_dir / "parity-work"
    work.mkdir(parents=True, exist_ok=True)
    cache_file = work / "reads.jsonl"
    code = _code_digest()
    done = {}
    if cache_file.exists():
        for line in cache_file.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue  # a line cut short by a killed run; its read runs again
            done[tuple(entry["key"])] = entry["results"]
    tasks, results = [], {}
    for unit in units:
        for name in DECODES:
            key = (unit.photo, unit.resolution, name, code, _inputs_digest(unit),
                   _image_id(unit, name, jobs, sidecars))
            if key in done:
                results[key[:3]] = done[key]
            else:
                tasks.append((key, (unit, name, decoded_dir, str(work))))
    print(f"reads: {len(results)} cached, {len(tasks)} to run", flush=True)

    def record(key, out):
        results[key[:3]] = out
        with cache_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"key": list(key), "results": out}) + "\n")

    def check_memory(before):
        free = decode.available_memory_gb()
        if free < args.min_free_gb:
            raise MemoryStop(f"free memory {free:.2f} GB is under {args.min_free_gb} GB before {before}; "
                             "rerun to resume")

    if args.workers == 1:
        for key, task in tasks:
            check_memory(key[:3])
            record(key, read_task(task))
        return results
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        pending, queue = {}, list(tasks)
        while queue or pending:
            while queue and len(pending) < args.workers:
                key, task = queue.pop(0)
                check_memory(key[:3])
                pending[pool.submit(read_task, task)] = key
            finished, _ = wait(pending, return_when=FIRST_COMPLETED)
            for future in finished:
                record(pending.pop(future), future.result())
    return results


def run_pixels(units, decoded_dir: Path, args) -> dict:
    """{(photo, resolution): {browser: diff or error}} for every staged image."""
    out = {}
    with tempfile.TemporaryDirectory(prefix="qrep-eval-", dir=decoded_dir) as tmp:
        for unit in units:
            free = decode.available_memory_gb()
            if free < args.min_free_gb:
                raise MemoryStop(f"free memory {free:.2f} GB is under {args.min_free_gb} GB")
            path, _ = harness.stage(unit, Path(tmp))
            native = cv2.imread(path, cv2.IMREAD_COLOR)
            row = {}
            for browser in decode.BROWSERS:
                try:
                    _, png, _ = _staged(unit, decoded_dir, browser, Path(tmp))
                    row[browser] = decode.pixel_diff(native, cv2.imread(png, cv2.IMREAD_COLOR))
                except Exception as error:  # noqa: BLE001 - recorded, never swallowed
                    row[browser] = {"error": repr(error)}
            out[(unit.photo, unit.resolution)] = row
            del native
    return out


def _rate(k: int, n: int) -> str:
    if not n:
        return "n = 0"
    lo, hi = stats.wilson(k, n)
    bound = f", 3/n = {3 / n:.3f}" if k == 0 else ""
    return f"{k}/{n} = {k / n:.3f} [{lo:.3f}, {hi:.3f}]{bound}"


def _pixels_cell(diff: dict) -> str:
    if "error" in diff:
        return "error"
    return f"{diff['differing']} / {diff['pixels']} ({diff['differing'] / diff['pixels']:.4f})"


def compare(units, reads: dict) -> list[dict]:
    """One row per photo, resolution, reader and browser."""
    rows = []
    for unit in units:
        native = {r["reader"]: r for r in reads[(unit.photo, unit.resolution, "native")]}
        for browser in decode.BROWSERS:
            other = {r["reader"]: r for r in reads[(unit.photo, unit.resolution, browser)]}
            for reader in unit.readers:
                a, b = native[reader], other[reader]
                row = {"photo": unit.photo, "group": unit.group, "tier": unit.tier, "resolution": unit.resolution,
                       "reader": reader, "browser": browser}
                if "skipped" in a or "skipped" in b:
                    rows.append({**row, "status": "skipped"})
                elif "error" in a or "error" in b:
                    rows.append({**row, "status": "error", "error": a.get("error") or b.get("error")})
                else:
                    rows.append({**row, "status": "compared", **decode.label_diff(_reading(a), _reading(b))})
    return rows


def markdown(header: dict, self_checks: list[str], pixels: dict, units, rows: list[dict], over: list) -> str:
    lines = [f"# {header['title']}", ""]
    lines += [f"- {key.replace('_', ' ').capitalize()}: {value}" for key, value in header.items() if key != "title"]
    lines += ["", "## Self-check", ""] + [f"- {line}" for line in self_checks]
    lines += ["", "## Pixels: native against browser decode", "",
              "Each staged image as the reader receives it: native is harness.stage's (cv2.imread, then "
              "cv2.resize with INTER_AREA to the cap), browser is the browser's PNG. Differing counts pixels "
              "with any channel different; largest is the largest absolute channel difference (0 to 255).", "",
              "| Browser | Resolution | Images | Identical | Median differing fraction | Largest differing "
              "fraction | Median largest difference | Largest difference |",
              "|---|---|---|---|---|---|---|---|"]
    resolutions = list(dict.fromkeys(u.resolution for u in units))
    for browser in decode.BROWSERS:
        for resolution in resolutions:
            diffs = [row[browser] for (photo, res), row in pixels.items() if res == resolution]
            ok = [d for d in diffs if "error" not in d]
            if not diffs:
                continue
            fractions = sorted(d["differing"] / d["pixels"] for d in ok)
            largest = sorted(d["largest"] for d in ok)
            errors = len(diffs) - len(ok)
            lines.append(f"| {browser} | {resolution} | {len(diffs)}{f', {errors} errors' if errors else ''} | "
                         f"{_rate(sum(d['differing'] == 0 for d in ok), len(ok))} | "
                         f"{statistics.median(fractions):.4f} | {fractions[-1]:.4f} | {statistics.median(largest):g} | {largest[-1]} |"
                         if ok else f"| {browser} | {resolution} | {len(diffs)}, {errors} errors | n = 0 | | | | |")
    if over:
        lines += ["", f"Not compared at full size, over the eval's {corpus.FULL_BUDGET_MP} MP as-fetched budget and "
                  f"never read as fetched: {', '.join(sorted({u.photo for u in over}))} ({len(over)} images)."]
    lines += ["", "Per image (differing / pixels (fraction), largest):", "",
              "| Photo | Resolution | Size | Chromium differing | Chromium largest | WebKit differing | "
              "WebKit largest |", "|---|---|---|---|---|---|---|"]
    sizes = {(u.photo, u.resolution): corpus.cap_size(*u.canvas, u.cap) for u in units}
    for (photo, resolution), row in pixels.items():
        size = sizes[(photo, resolution)]
        cells = [part for b in decode.BROWSERS for part in (_pixels_cell(row[b]), str(row[b].get("largest", "")))]
        lines.append(f"| {photo} | {resolution} | {size[0]} x {size[1]} | " + " | ".join(cells) + " |")
    lines += ["", "## Reads: label differences under the G9 rule", "",
              "G9 holds for a pair when both reads have the same outcome and, if they show a pattern, the "
              "same grid and the same fabric on every square that either read shows unflagged (confidence "
              "at or above the reader's threshold; a read with no confidences flags nothing). Two refusals "
              "show nothing and hold. Fabrics pair one to one by the squares they share, then by colour "
              "(decode.pair_fabrics), before squares are compared. A pair is one photo at one resolution, "
              "read by one reader in native and in one browser.", "",
              "| Browser | Resolution | Reader | Pairs | Same outcome | Nothing shown | Both shown | Same grid | "
              "G9 holds | Squares differing above threshold / differing / compared | Largest paired-fabric "
              "Delta E | Errors | Skipped |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for browser in decode.BROWSERS:
        for resolution in dict.fromkeys(r["resolution"] for r in rows):
            for reader in READERS:
                group = [r for r in rows if (r["browser"], r["resolution"], r["reader"]) == (browser, resolution, reader)]
                if not group:
                    continue
                done = [r for r in group if r["status"] == "compared"]
                same = [r for r in done if r["match"] != "outcome"]
                shown = [r for r in same if r["match"] != "nothing shown"]
                grid = [r for r in shown if r["match"] == "compared"]
                lines.append(
                    f"| {browser} | {resolution} | {reader} | {len(done)} | {_rate(len(same), len(done))} | "
                    f"{len(same) - len(shown)} | {len(shown)} | {len(grid)}/{len(shown)} | "
                    f"{_rate(sum(r['g9'] is True for r in done), len(done))} | "
                    f"{sum(r['differing_confident'] for r in grid)} / {sum(r['differing'] for r in grid)} / "
                    f"{sum(r['squares'] for r in grid)} | "
                    f"{max((r['palette_delta_e'] for r in grid), default=0):g} | "
                    f"{sum(r['status'] == 'error' for r in group)} | {sum(r['status'] == 'skipped' for r in group)} |")
    lines += [""]
    for browser in decode.BROWSERS:
        pairs = [r for r in rows if r["browser"] == browser and r["status"] == "compared"]
        moves = Counter((r["resolution"], r["reader"], *r["outcomes"]) for r in pairs if r["match"] == "outcome")
        lines.append(f"- Outcome changes, native to {browser}, of {len(pairs)} compared pairs: " + (
            "; ".join(f"{res} {reader} {a} to {c}: {n}" for (res, reader, a, c), n in sorted(moves.items()))
            or "none") + ".")
    lines += ["", "Pairs where the reads differ, or both show a pattern:", "",
              "| Photo | Resolution | Reader | Browser | Native outcome, grid, k | Browser outcome, grid, k | "
              "Squares differing above threshold / differing / compared | G9 |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if r["status"] != "compared" or (r["match"] == "nothing shown"):
            continue
        (no, bo), (nd, bd), (nk, bk) = r["outcomes"], r["dims"], r["k"]
        squares = (f"{r['differing_confident']} / {r['differing']} / {r['squares']}" if r["differing"] is not None
                   else "n/a")
        lines.append(f"| {r['photo']} | {r['resolution']} | {r['reader']} | {r['browser']} | {no}, {nd[0]} x {nd[1]}, "
                     f"{nk} | {bo}, {bd[0]} x {bd[1]}, {bk} | {squares} | {'holds' if r['g9'] else 'fails'} |")
    errors = [r for r in rows if r["status"] == "error"]
    lines += ["", "## Errors", ""] + ([f"- {r['photo']} {r['resolution']} {r['reader']} {r['browser']}: "
                                         f"{r['error']}" for r in errors] or ["- none"])
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parse(argv)
    cache = args.cache or args.corpus / "private" / "cache"
    decoded_dir = cache / "decoded"
    options = argparse.Namespace(corpus=args.corpus, resolutions=",".join(corpus.RESOLUTIONS),
                                 no_degradations=True, no_photoreal=False, private=False)
    units = [replace(u, readers=READERS) for u in run_decode.units_for(options, cache)]
    over = [u for u in units if harness.over_budget(u)]
    units = [u for u in units if not harness.over_budget(u)]
    jobs = {job.key: job for job in decode.jobs_for(units)}
    try:
        sidecars = {(b, key): decode.load_decoded(decoded_dir, b, job) for b in decode.BROWSERS
                    for key, job in jobs.items()}
    except (decode.DecodeMissing, ValueError) as error:
        raise SystemExit(f"run_parity: {error}") from error
    folder = decoded_dir / "selfcheck"
    check_jobs, images = run_decode.self_check_inputs(folder)
    self_checks = [run_decode.self_check_result(folder, b, check_jobs, images) for b in decode.BROWSERS]
    wanted = set(args.read_resolutions.split(","))
    read_units = [u for u in units if u.resolution in wanted or u.group == "named"]
    try:
        pixels = run_pixels(units, decoded_dir, args)
        rows = compare(read_units, run_reads(read_units, args, decoded_dir, jobs, sidecars))
    except MemoryStop as stop:
        print(f"run_parity: {stop}", file=sys.stderr)
        return MEMORY_STOP

    import cv2 as cv
    import qrep

    photos = {u.photo: u.tier for u in units if u.group == "corpus"}
    tiers = dict(sorted(Counter(photos.values()).items()))
    manifest = args.corpus / "manifest.csv"
    versions = {b: sorted({s.browser_version for (name, _), s in sidecars.items() if name == b})
                for b in decode.BROWSERS}
    playwright = sorted({s.sidecar.get("playwright_version") for s in sidecars.values() if s.error is None})
    status = _git("status", "--porcelain", "--", "qrep/", "scripts/eval/")
    header = {
        "title": "D4b: native and browser decode parity on the v0 dev split",
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "command": "python scripts/eval/decode/run_parity.py " + shlex.join(argv),
        "qrep_path": qrep.__file__,
        "git_sha": _git("rev-parse", "HEAD") or "unknown (git unavailable)",
        "git_status": "git status --porcelain -- qrep/ scripts/eval/: " + (
            "unknown" if status is None else "; ".join(status.splitlines()) or "clean"),
        "cv2_version": cv.__version__,
        "browsers": "; ".join(f"{b} {', '.join(v)}" for b, v in versions.items()) +
                    f", driven headless by Playwright {', '.join(playwright)} (scripts/eval/decode/browser_decode.mjs)",
        "native_decode_path": harness.DECODE_PATH,
        "browser_decode_path": decode.steps_text(),
        "inputs": (f"corpus/manifest.csv, eval_set v0 (sha256 {corpus.sha256_of(manifest)}), {len(photos)} photos "
                   f"in the dev split by tier {tiers}, and the photoreal fixtures busy_print_squares and "
                   "low_contrast_hst at 1400 and 2000 px; source images checked against the manifest sha256; "
                   "the holdout is never opened"),
        "resolutions": (f"pixels at {', '.join(corpus.RESOLUTIONS)}; reads at {args.read_resolutions} and the "
                        "fixtures"),
        "readers": ("auto (no corners) and auto-corners (true corners from the annotation, scaled to the staged "
                    "image, and the fabric count run_eval gives), each at 0 px as run_eval reads them; the "
                    "confirmed reader needs B2b"),
        "limits": ("Playwright's WebKit on Windows is the WinCairo port, whose image decoders are not Apple's "
                   "ImageIO, so WebKit here stands for WebKit's canvas path, not for Safari on an iPhone; the "
                   "crop-aware path of #101 waits for C3b; reads at full size are not run, since the D4 "
                   "baseline's auto reads at full size took 9697 s against 919 s at the phone cap"),
    }
    md = markdown(header, self_checks, pixels, units, rows, [u for u in over if u.resolution == "full"])
    out = args.out.with_name(args.out.name + ".md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8", newline="\n")
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
