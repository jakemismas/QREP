"""Print one screen of sprint status for a check-in with the orchestrator.

The orchestrator used to answer "where are we" by re-reading a state file
that grew to 392 KB (#278). This asks GitHub twice (one GraphQL query for the
tickets, one PR list) and reads the spend meter, then prints one screen in
docs/sprint-5/RESET.md section 2 order:

    step  ticket  issue  state  PR and CI  latest note  spend

Usage:
    python scripts/sprint_status.py [--since 2026-10-15] [--no-spend]
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESET = ROOT / "docs" / "sprint-5" / "RESET.md"
REPO = ("jakemismas", "QREP")
NOTE_KINDS = ("APPROACH FAILED", "HANDOFF", "PROGRESS", "UNBLOCKED", "BLOCKED", "QUESTION",
              "PLAN", "MEASUREMENT", "DONE", "Launched", "Close-out")


def reset_order(text: str) -> list[tuple[int, int]]:
    """(step, issue) pairs from the RESET.md section 2 table, in table order."""
    body = text.split("## 2.", 1)[-1].split("\n## 3.", 1)[0]
    pairs: list[tuple[int, int]] = []
    for line in body.splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|([^|]*)\|", line)
        if m:
            pairs += [(int(m.group(1)), int(n)) for n in re.findall(r"#(\d+)", m.group(2))]
    return pairs


def checks_summary(rollup: list[dict]) -> str:
    """Summarize the latest run of each check; a newer push cancels older runs."""
    if not rollup:
        return "no checks"
    latest: dict[str, dict] = {}
    for c in rollup:
        name = c.get("name") or c.get("context") or "?"
        if name not in latest or (c.get("startedAt") or "") >= (latest[name].get("startedAt") or ""):
            latest[name] = c
    rollup = list(latest.values())
    failed = [c.get("name") or c.get("context") for c in rollup
              if (c.get("conclusion") or c.get("state")) in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT")]
    if failed:
        return "red: " + ", ".join(sorted(failed))
    if any(c.get("status") not in (None, "COMPLETED") for c in rollup):
        return "running"
    return "green"


def latest_note(comments: list[dict]) -> str:
    for c in reversed(comments):
        head = c["body"].lstrip("*# ")
        for kind in NOTE_KINDS:
            if head.startswith(kind):
                return f"{kind} {c['createdAt'][5:10]}"
    return ""


def _gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True,
                          encoding="utf-8").stdout


def fetch_issues(numbers: list[int]) -> dict[int, dict]:
    fields = ("number title state labels(first:10){nodes{name}} "
              "comments(last:15){nodes{body createdAt}}")
    aliases = " ".join(f"i{n}: issue(number:{n}){{{fields}}}" for n in numbers)
    query = f'query{{repository(owner:"{REPO[0]}",name:"{REPO[1]}"){{{aliases}}}}}'
    data = json.loads(_gh("api", "graphql", "-f", f"query={query}"))["data"]["repository"]
    return {v["number"]: v for v in data.values() if v}


def fetch_prs() -> list[dict]:
    return json.loads(_gh("pr", "list", "--state", "open", "--json",
                          "number,title,body,headRefName,statusCheckRollup"))


def _spend(since: dt.date) -> dict[str, dict]:
    spec = importlib.util.spec_from_file_location("ticket_spend", ROOT / "scripts" / "ticket_spend.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.collect(mod.DEFAULT_PROJECTS, since) if mod.DEFAULT_PROJECTS.exists() else {}


def _m(n: int) -> str:
    return f"{n / 1e6:.0f}M" if n >= 1e6 else f"{n / 1e3:.0f}K"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", type=dt.date.fromisoformat, default=dt.date(2026, 10, 15))
    ap.add_argument("--no-spend", action="store_true")
    args = ap.parse_args(argv)

    order = reset_order(RESET.read_text(encoding="utf-8"))
    issues = fetch_issues([n for _, n in order])
    prs = fetch_prs()
    pr_for = {}
    for pr in prs:
        for n in re.findall(r"(?i)(?:fixes|closes)\s+#(\d+)", pr.get("body") or ""):
            pr_for[int(n)] = pr
    spend = {} if args.no_spend else _spend(args.since)

    print(f"Sprint 5 status, {dt.datetime.now():%Y-%m-%d %H:%M}, RESET.md order, spend since {args.since}")
    print(f"{'step':<5}{'ticket':<7}{'issue':<7}{'state':<8}{'PR and CI':<22}{'latest note':<20}spend")
    blocked, ready, done = [], [], 0
    for step, n in order:
        issue = issues.get(n)
        if not issue:
            continue
        ticket = issue["title"].split(":", 1)[0]
        state = issue["state"].lower()
        done += state == "closed"
        pr = pr_for.get(n)
        pr_text = f"#{pr['number']} {checks_summary(pr['statusCheckRollup'])}" if pr else ""
        note = latest_note(issue["comments"]["nodes"])
        labels = {lab["name"] for lab in issue["labels"]["nodes"]}
        if state == "open" and ("blocked" in labels or note.startswith("BLOCKED")):
            blocked.append(f"{ticket} #{n}")
        elif state == "open" and not pr:
            ready.append(f"{ticket} #{n}")
        s = spend.get(ticket)
        spent = f"{_m(s['effective'])}/{_m(s['output_tokens'])}" if s else ""
        print(f"{step:<5}{ticket:<7}#{n:<6}{state:<8}{pr_text[:21]:<22}{note[:19]:<20}{spent}")
    print(f"\n{done} of {len(order)} tickets closed. Open PRs: {len(prs)}.")
    print("Blocked: " + (", ".join(blocked) or "none"))
    print("Next in order (check each Depends on line): " + (", ".join(ready[:5]) or "none"))
    loose = [f"#{p['number']} {p['title'][:50]}" for p in prs
             if not any(p is pr_for.get(n) for _, n in order)]
    if loose:
        print("Open PRs outside the ticket list: " + "; ".join(loose))
    return 0


if __name__ == "__main__":
    sys.exit(main())
