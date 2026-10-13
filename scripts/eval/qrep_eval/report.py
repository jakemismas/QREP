"""Report-only scorecards: per-tier metrics with n and Wilson intervals (plan 7.2).

Gate rows use gate truth only; rows built on proposals are provisional and
never count toward a gate. Nothing here freezes a number: D5 measures the new
read and Jake freezes the gate.
"""

import subprocess
from collections import Counter, defaultdict
from statistics import median

from qrep_eval import corpus, stats

BLOCKED = ("held", "refused")
TIER_NAMES = {"A": "museum tier A (in scope)", "B": "museum tier B (stress)", "R": "refusal tier"}
# The section 7.2 metrics that wait on another ticket's merge, and the branch prefix
# that marks it in this tree's history.
PENDING = {"G3": ("B3", "slice/s5-b3-"), "G6": ("A3", "slice/s5-a3")}


def merged_in_tree(prefix: str) -> bool | None:
    """Whether a merge of a branch starting with prefix is in HEAD's history; None
    when git cannot answer (as under Pyodide)."""
    try:
        log = subprocess.run(["git", "log", "--merges", "--oneline", "HEAD"], capture_output=True,
                             text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None
    return prefix in log


def _valid(rows):
    return [r for r in rows if r["outcome"] != "error"]


def _blocked_rate(rows):
    rows = _valid(rows)
    return stats.rate(sum(r["outcome"] in BLOCKED for r in rows), len(rows))


def _flag_rate(rows, key):
    rows = [r for r in _valid(rows) if key in r]
    return stats.rate(sum(bool(r[key]) for r in rows), len(rows))


def _summary(rows) -> dict:
    valid = _valid(rows)
    in_scope = rows and rows[0]["tier"] != "R"
    out = {
        "n_rows": len(rows),
        "n_photos": len({r["photo"] for r in rows}),
        "errors": len(rows) - len(valid),
        "outcomes": dict(Counter(r["outcome"] for r in valid)),
        "verdicts": dict(Counter(r.get("verdict") for r in valid if r.get("verdict"))),
    }
    if in_scope:
        out["false_warning"] = _blocked_rate(rows)
        out["count_top1"] = _flag_rate(rows, "dims_exact")
        out["harmonic"] = _flag_rate(rows, "harmonic")
        out["fabric_count_exact"] = _flag_rate(rows, "k_exact")
        radii = [r["radius_squares"] for r in valid if r.get("radius_squares") is not None]
        out["mean_radius_squares"] = sum(radii) / len(radii) if radii else None
    else:
        out["refusal_recall"] = _blocked_rate(rows)
    return out


def _group(rows, *keys):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(k) for k in keys)].append(row)
    return {k: groups[k] for k in sorted(groups, key=lambda k: tuple(str(v) for v in k))}


def _gate_metrics(rows) -> list[dict]:
    """G1 to G6 per reader and resolution, gate truth and provisional side by side."""
    corpus_rows = [r for r in rows if r["group"] == "corpus"]
    out = []
    for (reader, resolution), group in _group(corpus_rows, "reader", "resolution").items():
        for label in ("gate", "provisional"):
            part = [r for r in group if r["truth"] == label]
            in_scope = [r for r in part if r["tier"] == "A"]
            gold = [r for r in in_scope if "fully_correct" in r and r.get("radius_px") in (None, 0)]
            squares = sum(r["squares"] for r in gold)
            wrong = sum(r["confident_wrong"] for r in gold)
            true_corners = [r for r in in_scope if r.get("radius_px") in (None, 0)]
            entry = {
                "reader": reader, "resolution": resolution, "truth": label,
                "G1": stats.rate(sum(r["fully_correct"] for r in gold), len(gold)),
                "G2": {"k": wrong, "n": squares, "rate": wrong / squares if squares else None},
                "G4": _blocked_rate([r for r in part if r["tier"] == "R"]),
                "G5": _blocked_rate(true_corners),
            }
            out.append(entry)
    return out


def _pending() -> dict:
    out = {}
    for metric, (ticket, prefix) in PENDING.items():
        merged = merged_in_tree(prefix)
        if merged:
            out[metric] = f"n/a: {ticket} is merged in this tree, and wiring {metric} is D5's"
        else:
            out[metric] = f"n/a until {ticket} merges" + ("" if merged is False else " (git unavailable)")
    out["G3"] += "; the automatic read takes no counts, so a miscount cannot be simulated for it"
    return out


def aggregate(rows: list[dict]) -> dict:
    true_rows = [r for r in rows if r.get("variant", "true") == "true"]
    corpus_rows = [r for r in true_rows if r["group"] == "corpus"]
    tier_a = [r for r in corpus_rows if r["tier"] == "A"]
    by_tier = {" | ".join(map(str, k)): _summary(g) for k, g in _group(
        corpus_rows, "reader", "tier", "resolution").items()}
    by_device = {}
    for (reader, device, resolution), group in _group(corpus_rows, "reader", "device_class", "resolution").items():
        by_device[f"{reader} | {device} | {resolution}"] = {
            "in_scope": _summary([r for r in group if r["tier"] != "R"]) if any(
                r["tier"] != "R" for r in group) else None,
            "refusal": _summary([r for r in group if r["tier"] == "R"]) if any(
                r["tier"] == "R" for r in group) else None,
        }
    jitter = {" | ".join(map(str, k)): _summary(g) for k, g in _group(
        [r for r in tier_a if r.get("radius_px") is not None], "reader", "resolution", "radius_px").items()}
    stress = {" | ".join(map(str, k)): _summary(g) for k, g in _group(
        [r for r in true_rows if r["group"] == "stress"], "reader", "condition").items()}
    auto_a = [r for r in tier_a if r["reader"] == "auto"]
    seconds = [r["seconds"] for r in _valid(true_rows) if "seconds" in r]
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
        "gate_metrics": _gate_metrics(true_rows),
        "pending": _pending(),
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


def _fmt(rate: dict | None) -> str:
    if not rate or rate.get("n", 0) == 0 or rate.get("rate") is None:
        return "n = 0"
    text = f"{rate['k']}/{rate['n']} = {rate['rate']:.3f}"
    if rate.get("wilson95"):
        lo, hi = rate["wilson95"]
        text += f" [{lo:.3f}, {hi:.3f}]"
    if rate.get("rule_of_three") is not None:
        text += f", 3/n = {rate['rule_of_three']:.3f}"
    return text


def _outcomes(summary: dict) -> str:
    o = summary["outcomes"]
    return f"{o.get('read', 0)} / {o.get('held', 0)} / {o.get('refused', 0)}"


def _verdicts(summary: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(summary["verdicts"].items())) or "none"


def markdown(report: dict) -> str:
    h, a = report["header"], report["aggregate"]
    lines = [f"# {h['title']}", ""]
    lines += [f"- {k.replace('_', ' ').capitalize()}: {v}" for k, v in h.items() if k != "title"]
    lines += ["", "Rates read k/n = rate [Wilson 95 percent interval]; a zero count adds its 3/n bound. "
              "Outcomes read read / held / refused. Provisional rows rest on proposals, never on gate "
              "truth, and count toward no gate. Nothing here is frozen (plan 7.2).", ""]
    lines += ["## Section 7.2 metrics", "",
              "| Reader | Resolution | Truth | G1 fully correct interior | G2 confident-wrong squares "
              "| G4 refusal recall | G5 false warning (true corners) |", "|---|---|---|---|---|---|---|"]
    for e in a["gate_metrics"]:
        g2 = e["G2"]
        g2_text = f"{g2['k']}/{g2['n']} squares = {g2['rate']:.4f}" if g2["n"] else "n = 0"
        lines.append(f"| {e['reader']} | {e['resolution']} | {e['truth']} | {_fmt(e['G1'])} | {g2_text} "
                     f"| {_fmt(e['G4'])} | {_fmt(e['G5'])} |")
    lines += ["", "- G5 for auto counts its read with no corners, since the automatic read takes none; "
              "auto-corners and confirmed count their 0 px trials."]
    lines += [f"- {k}: {v}" for k, v in a["pending"].items()]
    lines += ["- G1 and G2 need D3b's gold layouts; until a corpus photo has one, they read n = 0 on "
              "the corpus. The named rows below carry synthetic cell truth.", ""]
    lines += ["## Per tier and resolution", "",
              "| Reader | Tier | Resolution | Photos | Rows | Errors | Outcomes | Rate | Count top-1 "
              "| Fabric count exact | Verdicts |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for key, s in a["by_tier"].items():
        reader, tier, resolution = key.split(" | ")
        rate = s.get("false_warning") or s.get("refusal_recall")
        label = "false warning " if "false_warning" in s else "refusal recall "
        lines.append(f"| {reader} | {TIER_NAMES.get(tier, tier)} | {resolution} | {s['n_photos']} "
                     f"| {s['n_rows']} | {s['errors']} | {_outcomes(s)} | {label}{_fmt(rate)} "
                     f"| {_fmt(s.get('count_top1'))} | {_fmt(s.get('fabric_count_exact'))} "
                     f"| {_verdicts(s)} |")
    lines += ["", "## Per device class", "",
              "| Reader | Device class | Resolution | In scope: false warning | Refusal tier: recall |",
              "|---|---|---|---|---|"]
    for key, d in a["by_device_class"].items():
        reader, device, resolution = key.split(" | ")
        fw = _fmt(d["in_scope"]["false_warning"]) if d["in_scope"] else "n = 0"
        rr = _fmt(d["refusal"]["refusal_recall"]) if d["refusal"] else "n = 0"
        lines.append(f"| {reader} | {device} | {resolution} | {fw} | {rr} |")
    for device in a["device_classes_without_photos"]:
        lines.append(f"| every reader | {device} | every resolution | n = 0 | n = 0 |")
    lines += ["", "## Corner jitter (museum tier A)", "",
              "| Reader | Resolution | Radius px | Mean radius in squares | Rows | False warning "
              "| Count top-1 |", "|---|---|---|---|---|---|---|"]
    for key, s in a["jitter"].items():
        reader, resolution, radius = key.split(" | ")
        mean = s.get("mean_radius_squares")
        lines.append(f"| {reader} | {resolution} | {radius} | {mean:.3f} | {s['n_rows']} "
                     f"| {_fmt(s['false_warning'])} | {_fmt(s['count_top1'])} |" if mean is not None else
                     f"| {reader} | {resolution} | {radius} | n/a | {s['n_rows']} "
                     f"| {_fmt(s['false_warning'])} | {_fmt(s['count_top1'])} |")
    lines += ["", "## Stress: degradations", "", "Parameters: " + h.get("degradations", "none") + ".", "",
              "| Reader | Degradation | Photos | Outcomes | False warning | Count top-1 | Verdicts |",
              "|---|---|---|---|---|---|---|"]
    for key, s in a["stress"].items():
        reader, condition = key.split(" | ")
        lines.append(f"| {reader} | {condition} | {s['n_photos']} | {_outcomes(s)} "
                     f"| {_fmt(s['false_warning'])} | {_fmt(s['count_top1'])} | {_verdicts(s)} |")
    lines += ["", "## Named rows: photoreal fixtures (#82)", "",
              "Read with their sidecar corners and counts (auto-corners) and without (auto). Cell truth "
              "is the fixture generator's, so these rows are synthetic, not a gate tier.", "",
              "| Fixture | Cap | Reader | Verdict | Read dims | Truth dims | k read / truth "
              "| Accuracy many-to-one | Accuracy one-to-one | Fully correct | Confident-wrong |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in a["named"]:
        acc = r.get("accuracy_many_to_one")
        one = r.get("accuracy_one_to_one")
        lines.append(
            f"| {r['photo']} | {r['resolution']} | {r['reader']} | {r.get('verdict')} "
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
    picked = [r for r in rows if r["group"] == "corpus" and r["tier"] == "A"
              and r.get("radius_px") in (None, 0) and r.get("variant", "true") == "true"]
    out = []
    for (photo, resolution, reader), group in _group(picked, "photo", "resolution", "reader").items():
        r = group[0]
        out.append({"photo": photo, "resolution": resolution, "reader": reader, "truth": r["truth"],
                    "verdicts": ", ".join(str(g.get("verdict") or g["outcome"]) for g in group),
                    "read_dims": r.get("read_dims"), "truth_dims": r.get("truth_dims")})
    return out
