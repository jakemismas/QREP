"""Run the corpus eval: simulated confirmations, readers, per-tier scorecards (plan D4a).

    python scripts/eval/run_eval.py --cache <main checkout>/corpus/private/cache --out <stem>

Runs the v0 dev split with the auto and auto-corners readers by default and
writes <stem>.json and <stem>.md; --holdout runs the holdout instead and writes
<stem>-holdout.json and .md. Only licensed museum scans run unless --private,
which writes only where git ignores the report. Report only: it freezes nothing.
"""

import argparse
import datetime
import json
import os
import shlex
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

EVAL = Path(__file__).resolve().parent
REPO = EVAL.parents[1]
if str(EVAL) not in sys.path:
    sys.path.insert(0, str(EVAL))

from qrep.contract import Counts  # noqa: E402
from qrep_eval import annotation as an  # noqa: E402
from qrep_eval import corpus, degrade, harness, readers, report, simulate  # noqa: E402

READERS = ("auto", "auto-corners", "confirmed")
PHOTOREAL = ("busy_print_squares", "low_contrast_hst")
PHOTOREAL_CAPS = (1400, 2000)
STRESS_RESOLUTION = "desktop-2000"
DEFAULT_SEED = "d4a"
# What the header says when git cannot answer, as under Pyodide.
GIT_UNAVAILABLE = "unknown (git unavailable)"


def _parse(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reader", action="append", choices=READERS,
                   help="a reader to score; repeat for more (default: auto and auto-corners)")
    p.add_argument("--holdout", action="store_true", help="run the sealed holdout, in its own report")
    p.add_argument("--corpus", type=Path, default=REPO / "corpus")
    p.add_argument("--cache", type=Path, help="the fetched source images (default: <corpus>/private/cache)")
    p.add_argument("--out", required=True, type=Path, help="report path without its suffix")
    p.add_argument("--title", default=None)
    p.add_argument("--radii", default=",".join(str(r) for r in simulate.RADII_PX),
                   help="corner jitter radii in px, comma separated")
    p.add_argument("--trials", type=int, default=3, help="jitter draws per nonzero radius")
    p.add_argument("--seed", default=DEFAULT_SEED)
    p.add_argument("--resolutions", default=",".join(corpus.RESOLUTIONS))
    p.add_argument("--no-degradations", action="store_true")
    p.add_argument("--no-photoreal", action="store_true")
    p.add_argument("--start-sha", help="refuse to run unless qrep/vision/ outside read/ equals this SHA's")
    p.add_argument("--workers", type=int, default=1, help="processes for the reads")
    p.add_argument("--private", action="store_true",
                   help="admit photos that are not licensed museum scans; the report must be git-ignored")
    return p.parse_args(argv)


def _git(runner, *args) -> str | None:
    try:
        done = runner(["git", *args], capture_output=True, text=True, cwd=REPO)
    except OSError:
        return None
    return done.stdout if done.returncode == 0 else None


def _start_sha_check(sha: str, runner) -> str:
    """Plan 4.4: the automatic read must still be the start SHA's before a baseline,
    both committed and in the working tree the run imports, and the run must import
    this tree's qrep."""
    import qrep

    results = []
    for where, revisions in (("HEAD", [sha, "HEAD"]), ("working tree", [sha])):
        command = ["git", "diff", "--quiet", *revisions, "--", "qrep/vision/", ":(exclude)qrep/vision/read/"]
        try:
            code = runner(command, cwd=REPO).returncode
        except OSError as error:
            raise SystemExit(f"start-SHA check could not run: {error}") from error
        if code != 0:
            raise SystemExit(f"start-SHA check failed (exit {code}): qrep/vision/ in the {where} "
                             f"differs from {sha}")
        results.append(f"{shlex.join(command)} exited 0")
    location = Path(qrep.__file__).resolve()
    if not location.is_relative_to(REPO.resolve()):
        raise SystemExit(f"start-SHA check failed: qrep imports from {location}, outside {REPO}")
    results.append(f"qrep imports from {location}, inside the repo")
    return "; ".join(results)


def report_paths(out: Path, split: str) -> tuple[Path, Path]:
    """The report's JSON and Markdown paths, built on the whole name: with_suffix would
    cut a stem such as v0.4-eval at its dot."""
    name = out.name + ("-holdout" if split == "holdout" else "")
    return out.with_name(name + ".json"), out.with_name(name + ".md")


def _refuse_unignored(paths, runner) -> None:
    """A private run's report names private photos, so it may land in a git work tree
    only where git ignores it; when git cannot answer, the run stops."""
    folder = paths[0].resolve().parent
    while not folder.exists():
        folder = folder.parent
    try:
        inside = runner(["git", "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True,
                        cwd=folder)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return
        for path in paths:
            relative = os.path.relpath(path.resolve(), folder)
            if runner(["git", "check-ignore", "-q", "--", relative], capture_output=True, text=True,
                      cwd=folder).returncode != 0:
                print(f"run_eval: --private would write {path} inside a git work tree where git does "
                      "not ignore it", file=sys.stderr)
                raise SystemExit(2)
    except OSError as error:
        print(f"run_eval: --private could not ask git whether {folder} is tracked: {error}", file=sys.stderr)
        raise SystemExit(2) from error


def _manifest_name(manifest: Path) -> str:
    try:
        return manifest.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return "a manifest outside the repo"


def _corpus_units(args, photos, readers_, radii, workdir_root=None) -> list[harness.Unit]:
    units = []
    for photo in photos:
        truth = corpus.truth_view(photo.annotation)
        common = dict(
            photo=photo.stem, tier=photo.tier, split=photo.split, license=photo.row["license"],
            device_class=photo.device_class, source=str(photo.source),
            canvas=tuple(photo.annotation.canvas), truth=truth, truth_label=truth.label_for(photo.tier),
            readers=readers_, trials=args.trials, seed=args.seed, annotation=photo.annotation,
            extra={"proposals_agree": _proposals_agree(photo.annotation)}, workdir_root=workdir_root,
        )
        for resolution in args.resolutions.split(","):
            units.append(harness.Unit(group="corpus", resolution=resolution,
                                      cap=corpus.RESOLUTIONS[resolution], condition="clean",
                                      radii=radii, **common))
        if (not args.no_degradations and photo.tier == "A" and photo.row["license"] == "CC0-1.0"
                and truth.corners is not None):
            for d in degrade.DEGRADATIONS:
                units.append(harness.Unit(group="stress", resolution=STRESS_RESOLUTION,
                                          cap=corpus.RESOLUTIONS[STRESS_RESOLUTION], condition=d.name,
                                          radii=(0,), **common))
    return units


def _proposals_agree(annotation: an.Annotation) -> dict:
    out = {}
    for name in ("counts", "construction_class"):
        values = {c.provenance: c.value for c in getattr(annotation, name)}
        if "proposed-a" in values and "proposed-b" in values:
            out[name] = values["proposed-a"] == values["proposed-b"]
    return out


def _photoreal_units(args, readers_) -> list[harness.Unit]:
    units = []
    folder = REPO / "tests" / "fixtures" / "photoreal"
    for name in PHOTOREAL:
        for cap in PHOTOREAL_CAPS:
            side = json.loads((folder / f"{name}_{cap}.json").read_text(encoding="utf-8"))
            rows, cols = side["grid"]["rows"], side["grid"]["cols"]
            down, across = side["repeat_cells"] or (rows, cols)
            counts = Counts(blocks_across=cols // across, blocks_down=rows // down,
                            squares_per_block_across=across, squares_per_block_down=down)
            border = side["grid"]["border_pitches"] or 0
            truth = corpus.TruthView(
                corners=[tuple(p) for p in side["quad"]], bands=[border] if border else [],
                counts=counts, fabric_count=len(side["palette_hex"]), construction=side["character"],
                provenance={"frame": "fixture sidecar", "counts": "fixture sidecar"})
            units.append(harness.Unit(
                photo=name, group="named", tier="named", split="dev", license="repo fixture",
                device_class="synthetic render", resolution=f"fixture-{cap}", cap=None,
                condition="clean", source=str(folder / f"{name}_{cap}.png"), canvas=tuple(side["canvas"]),
                truth=truth, truth_label="synthetic", readers=readers_, radii=(0,), trials=1,
                seed=args.seed, truth_cells=side.get("cells"),
                truth_colors=[c.lower() for c in side["palette_hex"]] if side.get("cells") else None))
    return units


def _run(units, workers):
    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            return [row for rows in pool.map(harness.run_unit, units) for row in rows]
    return [row for unit in units for row in harness.run_unit(unit)]


def main(argv=None, *, runner=subprocess.run) -> int:
    """runner stands in for subprocess.run on every git call, so a test can answer
    for git."""
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parse(argv)
    readers_ = tuple(args.reader or ("auto", "auto-corners"))
    if "confirmed" in readers_:
        reason = readers.confirmed_unavailable()
        if reason:
            print(f"run_eval: {reason}", file=sys.stderr)
            raise SystemExit(2)
    split = "holdout" if args.holdout else "dev"
    json_path, md_path = report_paths(args.out, split)
    if args.private:
        _refuse_unignored((json_path, md_path), runner)
    check = _start_sha_check(args.start_sha, runner) if args.start_sha else "not run (no --start-sha)"
    radii = tuple(float(r) if "." in r else int(r) for r in args.radii.split(","))
    for resolution in args.resolutions.split(","):
        if resolution not in corpus.RESOLUTIONS:
            raise SystemExit(f"unknown resolution {resolution!r}; choose from {list(corpus.RESOLUTIONS)}")
    cache = args.cache or args.corpus / "private" / "cache"
    photos = corpus.load_photos(args.corpus, cache, split=split, allow_private=args.private)
    # A private photo's staged copies stay beside its cache, never in the shared temp.
    workdir_root = str(cache.resolve().parent) if args.private else None
    units = _corpus_units(args, photos, readers_, radii, workdir_root)
    if not args.no_photoreal and split == "dev":
        units += _photoreal_units(args, readers_)
    try:
        rows = _run(units, args.workers)
    except readers.ReaderUnavailable as error:
        print(f"run_eval: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    import cv2
    import qrep

    manifest = args.corpus / "manifest.csv"
    status = _git(runner, "status", "--porcelain", "--", "qrep/", "scripts/eval/")
    sha = _git(runner, "rev-parse", "HEAD")
    tiers = {t: sum(p.tier == t for p in photos) for t in sorted({p.tier for p in photos})}
    disagree = [p.stem for p in photos
                if p.tier == "A" and not all(_proposals_agree(p.annotation).values())]
    header = {
        "title": args.title or f"Corpus eval, v0 {split} split",
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "command": "python scripts/eval/run_eval.py " + shlex.join(argv),
        "qrep_path": qrep.__file__,
        "git_sha": sha.strip() if sha else GIT_UNAVAILABLE,
        "start_sha_check": check,
        "git_status": "git status --porcelain -- qrep/ scripts/eval/: " + (
            GIT_UNAVAILABLE if status is None
            else "; ".join(line.strip() for line in status.splitlines()) or "clean"),
        "cv2_version": cv2.__version__,
        "decode_path": harness.DECODE_PATH,
        "split": split,
        "inputs": (f"{_manifest_name(manifest)}, eval_set v0 (sha256 {corpus.sha256_of(manifest)}), "
                   f"{len(photos)} photos in the {split} split by tier {tiers}, annotations from "
                   "corpus/annotations/, source images checked against the manifest sha256"),
        "readers": ", ".join(readers_),
        "simulation": (f"corners from the annotation's outer edge (gate truth, else proposed-a, else "
                       f"proposed-b), jitter radii {list(radii)} px, {args.trials} draws per nonzero "
                       f"radius, seed {args.seed!r}; auto-corners receives those corners and the fabric "
                       f"count when 2 to 12; the automatic read takes no counts, so the true counts reach "
                       f"only the confirmed reader, with the same corners and fabric count; picker answer "
                       f"{simulate.PICKER_ANSWER!r} for every photo"),
        "resolutions": args.resolutions,
        "degradations": "none" if args.no_degradations else "; ".join(
            f"{d.name} {d.params}" for d in degrade.DEGRADATIONS) + (
            f", applied at {STRESS_RESOLUTION} to museum tier A photos licensed CC0-1.0"),
        "truth": (f"{sum(r['truth'] == 'gate' for r in rows)} gate rows, "
                  f"{sum(r['truth'] == 'provisional' for r in rows)} provisional rows, "
                  f"{sum(r['truth'] == 'synthetic' for r in rows)} synthetic rows"),
        "proposal_disagreements": (f"{len(disagree)} of {tiers.get('A', 0)} tier A photos have "
                                   f"proposed-a and proposed-b counts or classes that differ: "
                                   f"{', '.join(disagree) or 'none'}"),
        "low_confidence_flag": (f"auto readers flag squares below {readers.AUTO_LOW_CONFIDENCE_BELOW} "
                                "(the old app's UNCERTAIN_THRESHOLD); the confirmed reader flags none "
                                "until its result carries flags (#237); a read with no confidences "
                                "flags none and its row says confidence_missing"),
    }
    payload = {"header": header, "aggregate": report.aggregate(rows, runner=runner),
               "photos": report.per_photo(rows),
               "rows": rows}
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8", newline="\n")
    md_path.write_text(report.markdown(payload), encoding="utf-8", newline="\n")
    print(md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
