"""Total each sprint ticket's token use from the Claude Code session transcripts.

No ticket had a spending limit, and B2b ran five worker sessions at 360K to
435K tokens of context each (#278). The orchestrator runs this on every tick
and stops a ticket over its cap as BLOCKED (docs/sprint-5/RESET.md section 5).

A worker session is one whose first messages carry the worker role prompt
("QREP sprint 5 worker ... Ticket: C3b"); its subagents count toward the same
ticket. Orchestrator sessions are totalled on their own line. Usage repeats on
streamed message blocks, so each message id counts once.

Usage:
    python scripts/ticket_spend.py [--since 2026-10-15 (session start date)] [--ticket C3b]
        [--cap-effective N] [--cap-output N] [--json] [--projects-dir DIR]

Effective input is input plus cache writes plus cache reads: the context each
turn re-reads. Exit status 1 means at least one ticket is over a cap.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

DEFAULT_PROJECTS = Path.home() / ".claude" / "projects" / "c--Users-Jake-Mismas-QREP"
HEAD_BYTES = 400_000
USER_MESSAGES_SCANNED = 5
FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
TICKET = re.compile(r"Ticket:\s+([A-E]\d{1,2}[a-z]?)\b")
NAMED = (
    re.compile(r"worker role prompt for ([A-E]\d{1,2}[a-z]?)\b"),
    re.compile(r"worker ([A-E]\d{1,2}[a-z]?) role prompt"),
)
BRANCH = re.compile(r"slice/s5-([a-e]\d{1,2}[a-z]?)-")


def _user_texts(path: Path) -> list[str]:
    with path.open("rb") as fh:
        head = fh.read(HEAD_BYTES)
    texts: list[str] = []
    for raw in head.splitlines():
        if b'"user"' not in raw:
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if rec.get("type") != "user":
            continue
        content = (rec.get("message") or {}).get("content")
        if isinstance(content, list):
            content = "".join(b.get("text", "") for b in content if isinstance(b, dict))
        if isinstance(content, str) and content:
            texts.append(content)
        if len(texts) >= USER_MESSAGES_SCANNED:
            break
    return texts


def started(path: Path) -> dt.date | None:
    """The date of a session's first timestamped line (UTC), or None."""
    with path.open("rb") as fh:
        for raw in fh:
            m = re.search(rb'"timestamp":\s*"(\d{4}-\d{2}-\d{2})', raw[:2000])
            if m:
                return dt.date.fromisoformat(m.group(1).decode())
    return None


def classify(texts: list[str]) -> tuple[str, str | None]:
    """Return ("worker", ticket), ("orchestrator", None) or ("other", None)."""
    for text in texts:
        if "QREP sprint 5 orchestrator" in text:
            return "orchestrator", None
        if "QREP sprint 5 worker" in text:
            for pattern in (TICKET, *NAMED):
                m = pattern.search(text)
                if m:
                    return "worker", m.group(1)
            m = BRANCH.search(text)
            if m:
                ident = m.group(1)
                return "worker", ident[0].upper() + ident[1:]
            return "worker", "unknown"
    return "other", None


def usage(path: Path) -> dict[str, int]:
    seen: dict[str, dict] = {}
    with path.open("rb") as fh:
        for raw in fh:
            if b'"usage"' not in raw:
                continue
            try:
                rec = json.loads(raw)
            except ValueError:
                continue
            msg = rec.get("message") or {}
            if rec.get("type") != "assistant" or not isinstance(msg.get("usage"), dict):
                continue
            seen[msg.get("id") or rec.get("uuid") or str(len(seen))] = msg["usage"]
    totals = dict.fromkeys(FIELDS, 0)
    for u in seen.values():
        for field in FIELDS:
            totals[field] += int(u.get(field) or 0)
    return totals


def effective(t: dict[str, int]) -> int:
    return t["input_tokens"] + t["cache_creation_input_tokens"] + t["cache_read_input_tokens"]


def collect(projects: Path, since: dt.date | None = None) -> dict[str, dict]:
    """Totals per ticket, plus "orchestrator" and "other" buckets."""
    out: dict[str, dict] = {}
    for session in sorted(projects.glob("*.jsonl")):
        if since and (started(session) or dt.date.min) < since:
            continue
        kind, ticket = classify(_user_texts(session))
        key = ticket if kind == "worker" else kind
        bucket = out.setdefault(key, {"sessions": 0, **dict.fromkeys(FIELDS, 0)})
        bucket["sessions"] += 1
        files = [session, *sorted((projects / session.stem / "subagents").glob("*.jsonl"))]
        for f in files:
            for field, n in usage(f).items():
                bucket[field] += n
    for bucket in out.values():
        bucket["effective"] = effective(bucket)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--projects-dir", type=Path, default=DEFAULT_PROJECTS)
    ap.add_argument("--since", type=dt.date.fromisoformat)
    ap.add_argument("--ticket")
    ap.add_argument("--cap-effective", type=int)
    ap.add_argument("--cap-output", type=int)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    totals = collect(args.projects_dir, args.since)
    if args.ticket:
        totals = {k: v for k, v in totals.items() if k.lower() == args.ticket.lower()}
    over = sorted(
        k for k, v in totals.items()
        if k not in ("orchestrator", "other")
        and ((args.cap_effective and v["effective"] > args.cap_effective)
             or (args.cap_output and v["output_tokens"] > args.cap_output))
    )
    if args.json:
        print(json.dumps({"totals": totals, "over_cap": over}, indent=1, sort_keys=True))
    else:
        print(f"{'ticket':<14}{'sessions':>9}{'output':>12}{'effective':>14}")
        for k, v in sorted(totals.items(), key=lambda kv: -kv[1]["effective"]):
            flag = "  OVER CAP" if k in over else ""
            print(f"{k:<14}{v['sessions']:>9}{v['output_tokens']:>12,}{v['effective']:>14,}{flag}")
    return 1 if over else 0


if __name__ == "__main__":
    sys.exit(main())
