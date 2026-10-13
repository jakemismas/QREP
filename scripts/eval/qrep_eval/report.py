"""Report-only scorecards: per-tier metrics with n and Wilson intervals (plan 7.2).

Gate rows use gate truth only; rows built on proposals are provisional and
never count toward a gate. The unit of n is the photo: the tier, device and
gate tables take one row per photo, reader, resolution and condition, at true
corners and true counts. Nothing here freezes a number: D5 measures the new
read and Jake freezes the gate.
"""

import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from qrep_eval import corpus, stats

REPO = Path(__file__).resolve().parents[3]
BLOCKED = ("held", "refused")
OUTCOMES = ("read", "warned", "held", "refused")
# Rows that never enter a rate's n; every rate carries their counts instead.
UNSCORED = ("error", "skipped")
TIER_NAMES = {"A": "museum tier A (in scope)", "B": "museum tier B (stress)", "R": "refusal tier"}
TRUTH_LABELS = ("gate", "provisional", "conflict")
# The device column of the G5 entry pooled over every device class.
POOLED = "all in scope"
# Why the corner-taking readers score no refusal photo on the v0 corpus.
G4_CORNERS = "no frame or counts on the v0 refusal photos (#243)"
# The section 7.2 metrics that wait on another ticket's merge, and the branch prefix
# that marks it in this tree's history.
PENDING = {"G3": ("B3", "slice/s5-b3-"), "G6": ("A3b", "slice/s5-a3b-")}


def merged_in_tree(prefix: str, runner=subprocess.run) -> bool | None:
    """Whether a merge of a branch starting with prefix is in HEAD's history; None
    when git cannot answer (as under Pyodide)."""
    try:
        done = runner(["git", "log", "--merges", "--oneline", "HEAD"], capture_output=True, text=True,
                      cwd=REPO)
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return prefix in done.stdout


def _scored(rows):
    return [r for r in rows if r["outcome"] not in UNSCORED]


def _with_unscored(rate: dict, rows) -> dict:
    out = {**rate, "errors": sum(r["outcome"] == "error" for r in rows),
           "skipped": sum(r["outcome"] == "skipped" for r in rows)}
    over = sum(r["outcome"] == "skipped" and r.get("skip_kind") == corpus.OVER_BUDGET for r in rows)
    if over:
        out["over_budget"] = over
    return out


def _blocked_rate(rows):
    scored = _scored(rows)
    return _with_unscored(stats.rate(sum(r["outcome"] in BLOCKED for r in scored), len(scored)), rows)


def _flag_rate(rows, key):
    keyed = [r for r in _scored(rows) if key in r]
    return _with_unscored(stats.rate(sum(bool(r[key]) for r in keyed), len(keyed)), rows)


def _trial_count(rows, key=None) -> dict:
    """k of n trials and the photos behind them, with no interval: the trials of one
    photo are not independent draws."""
    scored = _scored(rows)
    counted = scored if key is None else [r for r in scored if key in r]
    hits = sum((r["outcome"] in BLOCKED) if key is None else bool(r[key]) for r in counted)
    return _with_unscored({"k": hits, "n": len(counted), "photos": len({r["photo"] for r in counted})},
                          rows)


def _summary(rows) -> dict:
    scored = _scored(rows)
    in_scope = rows and rows[0]["tier"] != "R"
    out = {
        "n_rows": len(rows),
        "n_photos": len({r["photo"] for r in rows}),
        "errors": sum(r["outcome"] == "error" for r in rows),
        "skipped": sum(r["outcome"] == "skipped" for r in rows),
        "outcomes": dict(Counter(r["outcome"] for r in scored)),
        "verdicts": dict(Counter(r.get("verdict") for r in scored if r.get("verdict"))),
        # Tier and device rates pool every truth label; the mix behind the rate's n.
        "truth_rows": {label: sum(r["truth"] == label for r in scored) for label in TRUTH_LABELS},
    }
    if in_scope:
        out["false_warning"] = _blocked_rate(rows)
        out["count_top1"] = _flag_rate(rows, "dims_exact")
        out["harmonic"] = _flag_rate(rows, "harmonic")
        out["fabric_count_exact"] = _flag_rate(rows, "k_exact")
    else:
        out["refusal_recall"] = _blocked_rate(rows)
    return out


def _mean(rows, key):
    values = [r[key] for r in _scored(rows) if r.get(key) is not None]
    return sum(values) / len(values) if values else None


def _jitter(rows) -> dict:
    return {
        "n_rows": len(rows),
        "mean_radius_squares": _mean(rows, "radius_squares"),
        # Clamping at the photo's edge leaves the realized move short of the radius.
        "mean_moved_squares": _mean(rows, "moved_squares"),
        "false_warning": _trial_count(rows),
        "count_top1": _trial_count(rows, "dims_exact"),
    }


def _group(rows, *keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(k) for k in keys)].append(row)
    return {k: groups[k] for k in sorted(groups, key=lambda k: tuple(str(v) for v in k))}


def _at_true_corners(rows):
    """One row per photo, reader, resolution and condition: the read with no corners
    or at 0 px, with the true counts."""
    return [r for r in rows if r.get("radius_px") in (None, 0) and r.get("variant", "true") == "true"]


def _gate_metrics(rows) -> list[dict]:
    """G1, G2, G4 and G5 per reader, device class and resolution over photo rows, gate
    truth and provisional side by side, then G5 pooled over the device classes. A
    conflict row counts toward neither; the provisional entry carries their count."""
    out = []
    for (reader, device, resolution), group in _group(rows, "reader", "device_class", "resolution").items():
        for label in ("gate", "provisional"):
            part = [r for r in group if r["truth"] == label]
            in_scope = [r for r in part if r["tier"] == "A"]
            gold_rows = [r for r in in_scope if r.get("cell_truth")]
            gold = _scored(gold_rows)
            squares = sum(r["squares"] for r in gold)
            wrong = sum(r["confident_wrong"] for r in gold)
            entry = {
                "reader": reader, "device_class": device, "resolution": resolution, "truth": label,
                "G1": _with_unscored(stats.rate(sum(bool(r["fully_correct"]) for r in gold), len(gold)),
                                     gold_rows),
                # Squares cluster by photo, so the photo count travels with the rate.
                "G2": {**_with_unscored(stats.rate(wrong, squares), gold_rows), "photos": len(gold)},
                "G4": _blocked_rate([r for r in part if r["tier"] == "R"]),
                "G5": _blocked_rate(in_scope),
            }
            if label == "provisional":
                entry["conflict_rows"] = sum(r["truth"] == "conflict" for r in group)
            out.append(entry)
    for (reader, resolution), group in _group(rows, "reader", "resolution").items():
        in_scope = [r for r in group if r["tier"] == "A"]
        for label in ("gate", "provisional"):
            entry = {"reader": reader, "device_class": POOLED, "resolution": resolution, "truth": label,
                     "G1": None, "G2": None, "G4": None,
                     "G5": _blocked_rate([r for r in in_scope if r["truth"] == label])}
            if label == "provisional":
                entry["conflict_rows"] = sum(r["truth"] == "conflict" for r in in_scope)
            out.append(entry)
    return out


def _pending(runner=subprocess.run) -> dict:
    out = {}
    for metric, (ticket, prefix) in PENDING.items():
        merged = merged_in_tree(prefix, runner)
        if merged:
            out[metric] = f"n/a: {ticket} is merged in this tree, and wiring {metric} is D5's"
        else:
            out[metric] = f"n/a until {ticket} merges" + ("" if merged is False else " (git unavailable)")
    out["G3"] += ("; the automatic read takes no counts, so a miscount cannot be simulated for it; "
                  "#237 tracks wiring G3")
    return out


def aggregate(rows: list[dict], *, runner=subprocess.run) -> dict:
    true_rows = [r for r in rows if r.get("variant", "true") == "true"]
    corpus_rows = [r for r in true_rows if r["group"] == "corpus"]
    photo_rows = _at_true_corners(corpus_rows)
    tier_a = [r for r in corpus_rows if r["tier"] == "A"]
    by_tier = {" | ".join(map(str, k)): _summary(g) for k, g in _group(
        photo_rows, "reader", "tier", "resolution").items()}
    by_device = {" | ".join(map(str, k)): _summary(g) for k, g in _group(
        photo_rows, "reader", "tier", "device_class", "resolution").items()}
    jitter = {" | ".join(map(str, k)): _jitter(g) for k, g in _group(
        [r for r in tier_a if r.get("radius_px") is not None], "reader", "resolution", "radius_px").items()}
    stress = {" | ".join(map(str, k)): _summary(g) for k, g in _group(
        _at_true_corners([r for r in true_rows if r["group"] == "stress"]),
        "reader", "condition", "device_class", "resolution").items()}
    auto_a = [r for r in photo_rows if r["tier"] == "A" and r["reader"] == "auto"]
    seconds = [r["seconds"] for r in _scored(true_rows) if "seconds" in r]
    r1 = {}
    for resolution, group in _group(auto_a, "resolution").items():
        r1[resolution[0]] = {
            "count_top1_periodic": _flag_rate([r for r in group if r.get("periodic")], "dims_exact"),
            "count_top1_non_periodic": _flag_rate([r for r in group if r.get("periodic") is False], "dims_exact"),
            "count_top3": "n/a: the automatic read offers one grid, not ranked suggestions (B7)",
            "harmonic_error": _flag_rate(group, "harmonic"),
            "fabric_count_suggestion_exact": _flag_rate(group, "k_exact"),
        }
    miscounts = [r for r in rows if r.get("variant", "true") != "true"]
    return {
        "gate_metrics": _gate_metrics(photo_rows),
        "pending": _pending(runner),
        "by_tier": by_tier,
        "by_device_class": by_device,
        "device_classes_without_photos": sorted(
            set(corpus.DEVICE_CLASS.values()) - {r["device_class"] for r in corpus_rows}),
        "jitter": jitter,
        "stress": stress,
        "named": [r for r in true_rows if r["group"] == "named"],
        "r1": {
            "by_resolution": r1,
            "latency": {"browser": "n/a: confirm-flow latency in the browser needs D4b and C3",
                        "native_median_seconds_per_read": median(seconds) if seconds else None,
                        "n_reads": len(seconds)},
            "triangle_counts": "n/a until B4 classifies triangle units",
        },
        "miscount_trials": len(miscounts),
        "errors": [{k: r.get(k) for k in ("photo", "reader", "resolution", "condition", "error")}
                   for r in rows if r["outcome"] == "error"],
    }


def _unscored(rate: dict) -> str:
    text = f", {rate['errors']} errors" if rate.get("errors") else ""
    if rate.get("skipped"):
        text += f", {rate['skipped']} skipped"
        if rate.get("over_budget"):
            text += f" ({rate['over_budget']} over the as-fetched budget)"
    return text


def _fmt(rate: dict | None, what: str = "", digits: int = 3) -> str:
    if not rate:
        return "n = 0"
    if rate.get("n", 0) == 0 or rate.get("rate") is None:
        return "n = 0" + _unscored(rate)
    text = f"{rate['k']}/{rate['n']}{' ' + what if what else ''} = {rate['rate']:.{digits}f}"
    if rate.get("wilson95"):
        lo, hi = rate["wilson95"]
        text += f" [{lo:.{digits}f}, {hi:.{digits}f}]"
    if rate.get("rule_of_three") is not None:
        text += f", 3/n = {rate['rule_of_three']:.{digits}f}"
    return text + _unscored(rate)


def _fmt_trials(count: dict) -> str:
    if count["n"] == 0:
        return "n = 0" + _unscored(count)
    return f"{count['k']}/{count['n']} trials, {count['photos']} photos" + _unscored(count)


def _outcomes(summary: dict) -> str:
    o = summary["outcomes"]
    return " / ".join(str(o.get(name, 0)) for name in OUTCOMES)


def _truth_rows(summary: dict) -> str:
    return " / ".join(str(summary["truth_rows"][label]) for label in TRUTH_LABELS)


def _verdicts(summary: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(summary["verdicts"].items())) or "none"


def markdown(report: dict) -> str:
    h, a = report["header"], report["aggregate"]
    lines = [f"# {h['title']}", ""]
    lines += [f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in h.items() if k != "title"]
    lines += ["", "Rates read k/n = rate [Wilson 95 percent interval]; a zero count adds its 3/n bound. "
              "Error and skipped rows never enter n; a rate lists them after it. n counts photos: one "
              "row per photo, reader, resolution and condition, read at true corners and true counts. "
              "Outcomes read read / warned / held / refused. False warning, refusal recall and G4 and "
              "G5 count holds and refusals only: a warned read still offers the editor and its PDF. "
              "Provisional rows rest on proposals, never on gate truth, and conflict rows carry a "
              "verified class that contradicts their tier; neither counts toward a gate. Nothing here "
              "is frozen (plan 7.2).", ""]
    lines += ["## Section 7.2 metrics", "",
              "| Reader | Device class | Resolution | Truth | G1 fully correct interior "
              "| G2 confident-wrong squares | G4 refusal recall | G5 false warning (true corners) |",
              "|---|---|---|---|---|---|---|---|"]
    for e in a["gate_metrics"]:
        g2 = e["G2"]
        truth = e["truth"] + (f" ({e['conflict_rows']} conflict rows)" if e.get("conflict_rows") else "")
        g4 = "n/a" if e["G4"] is None else _fmt(e["G4"]) + (
            f"; {G4_CORNERS}" if e["G4"].get("skipped", 0) > e["G4"].get("over_budget", 0) else "")
        g1 = "n/a" if e["G1"] is None else _fmt(e["G1"])
        g2_text = "n/a" if g2 is None else f"{g2['photos']} photos: {_fmt(g2, 'squares', 4)}"
        lines.append(f"| {e['reader']} | {e['device_class']} | {e['resolution']} | {truth} "
                     f"| {g1} | {g2_text} | {g4} | {_fmt(e['G5'])} |")
    lines += ["", "- G5 for auto counts its read with no corners, since the automatic read takes none; "
              "auto-corners and confirmed count their 0 px trials. The " + POOLED + " rows pool G5 over "
              "every device class.",
              "- A G4 cell with skipped refusal photos: auto-corners and confirmed take a frame and counts, "
              "and the v0 annotations give the refusal photos neither, so those photos are skipped, not "
              "scored (#243).",
              "- G2 counts squares, which cluster by photo; its interval treats them as independent, so "
              "it is too narrow. The photo count says how many gold photos stand behind it."]
    lines += [f"- {k}: {v}" for k, v in a["pending"].items()]
    lines += ["- G1 and G2 need gold layouts, and the harness has no gold-layout loader yet (D3b defines "
              "corpus/gold/; #237 tracks loading it), so they read n = 0 on the corpus. The named rows "
              "below carry synthetic cell truth.", ""]
    lines += ["## Per tier and resolution", "",
              "| Reader | Tier | Resolution | Photos | Rows | Errors | Skipped | Outcomes | Rate "
              "| Gate / provisional / conflict rows | Count top-1 | Fabric count exact | Verdicts |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, s in a["by_tier"].items():
        reader, tier, resolution = key.split(" | ")
        rate = s.get("false_warning") or s.get("refusal_recall")
        label = "false warning " if "false_warning" in s else "refusal recall "
        lines.append(f"| {reader} | {TIER_NAMES.get(tier, tier)} | {resolution} | {s['n_photos']} "
                     f"| {s['n_rows']} | {s['errors']} | {s['skipped']} | {_outcomes(s)} | {label}{_fmt(rate)} "
                     f"| {_truth_rows(s)} | {_fmt(s.get('count_top1'))} | {_fmt(s.get('fabric_count_exact'))} "
                     f"| {_verdicts(s)} |")
    lines += ["", "## Per device class", "",
              "| Reader | Tier | Device class | Resolution | Photos | Outcomes | Rate "
              "| Gate / provisional / conflict rows |", "|---|---|---|---|---|---|---|---|"]
    for key, s in a["by_device_class"].items():
        reader, tier, device, resolution = key.split(" | ")
        rate = (f"false warning {_fmt(s['false_warning'])}" if "false_warning" in s
                else f"refusal recall {_fmt(s['refusal_recall'])}")
        lines.append(f"| {reader} | {TIER_NAMES.get(tier, tier)} | {device} | {resolution} | {s['n_photos']} "
                     f"| {_outcomes(s)} | {rate} | {_truth_rows(s)} |")
    for device in a["device_classes_without_photos"]:
        lines.append(f"| every reader | every tier | {device} | every resolution | 0 | none | n = 0 | 0 / 0 / 0 |")
    lines += ["", "## Corner jitter (museum tier A)", "",
              "Trials of one photo are not independent, so these rows give k/n trials and the photo "
              "count, with no interval and no 3/n bound.", "",
              "| Reader | Resolution | Radius px | Mean radius in squares | Mean moved in squares | Rows "
              "| False warning | Count top-1 |", "|---|---|---|---|---|---|---|---|"]
    for key, s in a["jitter"].items():
        reader, resolution, radius = key.split(" | ")
        mean, moved = s.get("mean_radius_squares"), s.get("mean_moved_squares")
        lines.append(f"| {reader} | {resolution} | {radius} | {'n/a' if mean is None else f'{mean:.3f}'} "
                     f"| {'n/a' if moved is None else f'{moved:.3f}'} | {s['n_rows']} "
                     f"| {_fmt_trials(s['false_warning'])} | {_fmt_trials(s['count_top1'])} |")
    lines += ["", "## Stress: degradations", "", "Parameters: " + h.get("degradations", "none") + ".", "",
              "| Reader | Degradation | Device class | Resolution | Photos | Outcomes | False warning "
              "| Count top-1 | Verdicts |", "|---|---|---|---|---|---|---|---|---|"]
    for key, s in a["stress"].items():
        reader, condition, device, resolution = key.split(" | ")
        lines.append(f"| {reader} | {condition} | {device} | {resolution} | {s['n_photos']} | {_outcomes(s)} "
                     f"| {_fmt(s['false_warning'])} | {_fmt(s['count_top1'])} | {_verdicts(s)} |")
    lines += ["", "## Named rows: photoreal fixtures (#82)", "",
              "auto-corners reads each fixture with its sidecar corners and fabric count, auto with "
              "neither; the automatic read takes no counts, so the sidecar counts reach only the "
              "confirmed reader. Cell truth is the fixture generator's, so these rows are synthetic, "
              "not a gate tier.", "",
              "| Fixture | Cap | Reader | Verdict | Read dims | Truth dims | k read / truth "
              "| Accuracy many-to-one | Accuracy one-to-one | Fully correct | Confident-wrong |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in a["named"]:
        acc = r.get("accuracy_many_to_one")
        one = r.get("accuracy_one_to_one")
        lines.append(
            f"| {r['photo']} | {r['resolution']} | {r['reader']} | {r.get('verdict') or r['outcome']} "
            f"| {r.get('read_dims')} | {r.get('truth_dims')} | {r.get('k_read')} / {r.get('k_truth')} "
            f"| {'n/a' if acc is None else f'{acc:.4f}'} | {'n/a' if one is None else f'{one:.4f}'} "
            f"| {r.get('fully_correct', 'n/a')} | {r.get('confident_wrong', 'n/a')} |")
    lines += ["", "## R1, reported and not gated (automatic read, museum tier A)", ""]
    for resolution, r in a["r1"]["by_resolution"].items():
        lines += [f"- {resolution}: count top-1 periodic {_fmt(r['count_top1_periodic'])}; non-periodic "
                  f"{_fmt(r['count_top1_non_periodic'])}; harmonic error {_fmt(r['harmonic_error'])}; "
                  f"fabric-count suggestion exact {_fmt(r['fabric_count_suggestion_exact'])}; "
                  f"top-3 {r['count_top3']}"]
    latency = a["r1"]["latency"]
    native = latency["native_median_seconds_per_read"]
    lines += [f"- Latency: {latency['browser']}; native median "
              f"{'n/a' if native is None else f'{native:.2f} s'} per read over {latency['n_reads']} reads",
              f"- Triangle counts: {a['r1']['triangle_counts']}", ""]
    lines += ["## Errors", ""] + ([f"- {e}" for e in a["errors"]] or ["- none"])
    if report.get("photos"):
        lines += ["", "## Per photo (museum tier A)", "",
                  "| Photo | Resolution | Reader | Truth | Verdicts | Read dims | Truth dims |",
                  "|---|---|---|---|---|---|---|"]
        lines += [f"| {p['photo']} | {p['resolution']} | {p['reader']} | {p['truth']} | {p['verdicts']} "
                  f"| {p['read_dims']} | {p['truth_dims']} |" for p in report["photos"]]
    return "\n".join(lines) + "\n"


def per_photo(rows: list[dict]) -> list[dict]:
    """Museum tier A at true corners (radius 0, or no corners): one line per photo,
    resolution and reader."""
    picked = [r for r in _at_true_corners(rows) if r["group"] == "corpus" and r["tier"] == "A"]
    out = []
    for (photo, resolution, reader), group in _group(picked, "photo", "resolution", "reader").items():
        r = group[0]
        out.append({"photo": photo, "resolution": resolution, "reader": reader, "truth": r["truth"],
                    "verdicts": ", ".join(str(g.get("verdict") or g["outcome"]) for g in group),
                    "read_dims": r.get("read_dims"), "truth_dims": r.get("truth_dims")})
    return out
