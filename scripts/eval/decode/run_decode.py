"""Decode the eval's dev-split images in Chromium and WebKit (plan D4b).

    python scripts/eval/decode/run_decode.py --cache <main checkout>/corpus/private/cache

Builds the same units run_eval.py builds, one job per photo and resolution that a
unit stages (full size and the 2000 and 1400 caps, and the photoreal fixtures at
their own size), and runs browser_decode.mjs once per browser. PNGs and sidecars
land in <cache>/decoded/<browser>/, which git ignores. A self-check first decodes
two generated PNGs: at full size the browser must return every pixel unchanged, and
at the phone cap the size must be corpus.cap_size's (the eval's copy of the app's
targetSize rounding, which the driver repeats in the page); the generated PNGs are the same
bytes on every run, so a rerun rechecks the decodes that browser version made. Every
sidecar is then checked
(decode.load_decoded). The dev split by default; --holdout decodes the sealed holdout
instead, for the gate measurement alone (plan 8.2), so no development run opens it. A rerun skips
images already decoded by the same browser version.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
EVAL = HERE.parent
REPO = EVAL.parents[1]
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))

import run_eval  # noqa: E402
from qrep_eval import corpus, decode  # noqa: E402

DRIVER = HERE / "browser_decode.mjs"
SELF_CHECK = (("selfcheck__full", (257, 129), None), ("selfcheck__phone-1400", (3001, 1999), 1400))


def _parse(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", type=Path, default=REPO / "corpus")
    p.add_argument("--cache", type=Path, help="the fetched source images (default: <corpus>/private/cache)")
    p.add_argument("--browser", action="append", choices=decode.BROWSERS, help="default: both")
    p.add_argument("--resolutions", default=",".join(corpus.RESOLUTIONS))
    p.add_argument("--no-degradations", action="store_true",
                   help="skip the full-size decodes only a degradation needs")
    p.add_argument("--no-photoreal", action="store_true")
    p.add_argument("--private", action="store_true", help="admit rows under other licenses")
    p.add_argument("--holdout", action="store_true",
                   help="decode the sealed holdout instead of the dev split; only the gate measurement runs it")
    p.add_argument("--port", type=int, default=int(os.environ.get("QREP_E2E_PORT") or 0) or None,
                   help="the loopback port for the driver (default: QREP_E2E_PORT)")
    p.add_argument("--min-free-gb", type=float, default=4.0)
    args = p.parse_args(argv)
    if not args.port:
        p.error("--port is required when QREP_E2E_PORT is unset")
    return args


def units_for(args, cache: Path):
    """run_eval's units for the dev split with these options, so every image a
    --decode run stages has a job."""
    argv = ["--out", "unused", "--corpus", str(args.corpus), "--cache", str(cache), "--resolutions",
            args.resolutions, "--radii", "0", "--trials", "1"]
    argv += ["--no-degradations"] * args.no_degradations + ["--private"] * args.private
    eval_args = run_eval._parse(argv)
    holdout = getattr(args, "holdout", False)
    photos = corpus.load_photos(args.corpus, cache, split="holdout" if holdout else "dev",
                                allow_private=args.private)
    units = run_eval._corpus_units(eval_args, photos, ("auto",), (0,))
    # run_eval reads the photoreal fixtures on the dev split only.
    if not args.no_photoreal and not holdout:
        units += run_eval._photoreal_units(eval_args, ("auto",))
    return units


def _drive(jobs, decoded_dir: Path, browser: str, args, name: str) -> dict:
    jobs_file = decoded_dir / f"jobs-{name}-{browser}.json"
    jobs_file.write_text(json.dumps([job.as_json() for job in jobs]), encoding="utf-8")
    command = ["node", str(DRIVER), "--jobs", str(jobs_file), "--out", str(decoded_dir / browser),
               "--browser", browser, "--port", str(args.port), "--min-free-gb", str(args.min_free_gb)]
    done = subprocess.run(command, capture_output=True, text=True)
    sys.stderr.write(done.stderr)
    if done.returncode not in (0, 3):
        raise SystemExit(f"run_decode: the {browser} driver failed (exit {done.returncode})")
    summary = json.loads(done.stdout.strip().splitlines()[-1])
    if summary["stopped"]:
        raise SystemExit(f"run_decode: {browser} stopped: {summary['stopped']}; rerun to resume")
    return summary


def self_check_inputs(folder: Path) -> tuple[list[decode.Job], dict]:
    """The generated PNGs and their jobs; the same bytes on every run."""
    folder.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(4)
    jobs, images = [], {}
    for key, (width, height), cap in SELF_CHECK:
        image = rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
        source = folder / f"{key}.png"
        if not cv2.imwrite(str(source), image):
            raise SystemExit(f"run_decode: could not write {source}")
        images[key] = image
        jobs.append(decode.Job(key=key, source=str(source), sha256=corpus.sha256_of(source), cap=cap,
                               canvas=(width, height)))
    return jobs, images


def self_check_result(folder: Path, browser: str, jobs, images) -> str:
    """What came back: every pixel of the full-size PNG unchanged, and the capped one at
    targetSize's size (load_decoded checks the size)."""
    full = decode.load_decoded(folder, browser, jobs[0])
    capped = decode.load_decoded(folder, browser, jobs[1])
    if full.error or capped.error:
        raise SystemExit(f"run_decode: {browser} self-check failed: {full.error or capped.error}")
    back = cv2.imread(str(full.png), cv2.IMREAD_COLOR)
    diff = decode.pixel_diff(images[jobs[0].key], back)
    if diff["differing"]:
        raise SystemExit(f"run_decode: {browser} changed {diff['differing']} pixels of a PNG drawn at its own size")
    return (f"{browser} {full.browser_version}: a {jobs[0].canvas[0]} x {jobs[0].canvas[1]} random PNG at full "
            f"size came back with 0 of {diff['pixels']} pixels changed; a {jobs[1].canvas[0]} x "
            f"{jobs[1].canvas[1]} PNG at the {jobs[1].cap} cap came back {capped.size[0]} x {capped.size[1]}, "
            "the size corpus.cap_size gives")


def self_check(decoded_dir: Path, browser: str, args) -> str:
    """Decode two generated PNGs and check what came back, before any corpus image."""
    folder = decoded_dir / "selfcheck"
    jobs, images = self_check_inputs(folder)
    _drive(jobs, folder, browser, args, "selfcheck")
    return self_check_result(folder, browser, jobs, images)


def main(argv=None) -> int:
    args = _parse(list(sys.argv[1:] if argv is None else argv))
    cache = args.cache or args.corpus / "private" / "cache"
    decoded_dir = cache / "decoded"
    decoded_dir.mkdir(parents=True, exist_ok=True)
    # Smallest decode first, so a stop on free memory leaves every smaller image done.
    jobs = sorted(decode.jobs_for(units_for(args, cache)),
                  key=lambda job: (job.canvas[0] * job.canvas[1], job.cap is None))
    for browser in args.browser or decode.BROWSERS:
        print(f"self-check: {self_check(decoded_dir, browser, args)}")
        summary = _drive(jobs, decoded_dir, browser, args, "eval")
        checked = [decode.load_decoded(decoded_dir, browser, job) for job in jobs]
        failed = [job.key for job, d in zip(jobs, checked) if d.error is not None]
        print(f"{browser} {summary['browser_version']}: {len(jobs)} jobs, {summary['decoded']} decoded now, "
              f"{summary['skipped']} already decoded, {len(jobs) - len(failed)} sidecars checked, "
              f"{len(failed)} browser failures{': ' + ', '.join(failed) if failed else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
