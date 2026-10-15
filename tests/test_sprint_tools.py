"""Tests for the sprint tooling: ticket_spend.py and ticket_brief.py (#281).

Expected values are worked by hand from the synthetic inputs built here.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


spend = _load("ticket_spend")
brief = _load("ticket_brief")
status = _load("sprint_status")


def _user(text: str) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": text}})


def _assistant(mid: str, i: int, cw: int, cr: int, o: int) -> str:
    usage = {"input_tokens": i, "cache_creation_input_tokens": cw,
             "cache_read_input_tokens": cr, "output_tokens": o}
    return json.dumps({"type": "assistant", "message": {"id": mid, "usage": usage}})


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _projects(tmp_path: Path) -> Path:
    role = "QREP sprint 5 worker. Follow this prompt.\n\nRole:   build\nTicket:            C3b \n"
    _write(tmp_path / "w1.jsonl", [
        _user(role),
        _assistant("m1", 10, 100, 1000, 5),
        _assistant("m1", 10, 100, 1000, 5),  # the same message streamed twice counts once
        _assistant("m2", 1, 0, 2000, 7),
    ])
    _write(tmp_path / "w1" / "subagents" / "agent-x.jsonl", [_assistant("s1", 2, 20, 200, 3)])
    _write(tmp_path / "o1.jsonl", [
        _user("QREP sprint 5 orchestrator handover"),
        _assistant("o", 5, 5, 5, 5),
    ])
    return tmp_path


def test_spend_counts_each_message_once_and_adds_subagents(tmp_path):
    totals = spend.collect(_projects(tmp_path))
    c3b = totals["C3b"]
    # m1 once + m2 + s1: input 10+1+2 = 13, writes 100+0+20 = 120,
    # reads 1000+2000+200 = 3200, output 5+7+3 = 15; effective 13+120+3200 = 3333.
    assert (c3b["input_tokens"], c3b["cache_creation_input_tokens"]) == (13, 120)
    assert (c3b["cache_read_input_tokens"], c3b["output_tokens"]) == (3200, 15)
    assert c3b["effective"] == 3333
    assert c3b["sessions"] == 1
    # The orchestrator session is its own bucket: 5+5+5 = 15 effective.
    assert totals["orchestrator"]["effective"] == 15


def test_spend_exits_one_only_when_a_ticket_is_over_its_cap(tmp_path, capsys):
    projects = _projects(tmp_path)
    assert spend.main(["--projects-dir", str(projects), "--cap-effective", "3332"]) == 1
    assert "OVER CAP" in capsys.readouterr().out
    assert spend.main(["--projects-dir", str(projects), "--cap-effective", "3333"]) == 0
    # C3b's output is 15: a cap of 15 holds, 14 trips.
    assert spend.main(["--projects-dir", str(projects), "--cap-output", "15"]) == 0
    assert spend.main(["--projects-dir", str(projects), "--cap-output", "14"]) == 1
    # The orchestrator bucket (15 effective) never trips a ticket cap, even a cap of 1.
    assert spend.main(["--projects-dir", str(projects), "--ticket", "orchestrator",
                       "--cap-effective", "1"]) == 0


def test_spend_names_the_ticket_from_older_role_prompts():
    assert spend.classify(["QREP sprint 5 worker role prompt for B2b (relaunch)"]) == ("worker", "B2b")
    assert spend.classify(["QREP sprint 5 worker A10 role prompt"]) == ("worker", "A10")
    assert spend.classify(["QREP sprint 5 worker, branch slice/s5-d4a-eval"]) == ("worker", "D4a")
    assert spend.classify(["Looking at Github issues"]) == ("other", None)


PLAN = """### 5.C Web

#### C3b: Confirm screen

Uses F3 and PS-09, and F3 again.

#### C3c: Read with confirmed corners

Not part of C3b.
"""

MATH = """### F3. Strip sets

Strips cut at width plus 1/2 in.

### F4. Borders

Not F3.
"""

SPEC = "| PS-09 | Cover | The size line echoes the request |\n| PS-10 | Other | x |\n"


def test_brief_takes_only_the_tickets_plan_section():
    section = brief.plan_section(PLAN, "C3b")
    assert section.startswith("#### C3b: Confirm screen")
    assert "C3c" not in section


def test_brief_lists_cited_ids_once_in_order():
    assert brief.cited_ids("F3 and PS-09, and F3 again; V-BACK-21") == ["F3", "PS-09", "V-BACK-21"]


def test_brief_extracts_a_heading_section_and_a_table_row():
    assert brief.definition(MATH, "F3", "MATH.md") == "### F3. Strip sets\n\nStrips cut at width plus 1/2 in."
    assert brief.definition(SPEC, "PS-09", "PATTERN-SPEC.md") == (
        "| PS-09 | Cover | The size line echoes the request |"
    )
    assert brief.definition(SPEC, "PS-44", "PATTERN-SPEC.md") is None


def test_brief_keeps_criteria_decisions_and_only_the_latest_resume_note():
    comments = [
        {"body": "HANDOFF one", "createdAt": "1"},
        {"body": "PROGRESS ran the tests", "createdAt": "2"},
        {"body": "Folded in.\n\n### From #125: A4d: Steps\n\n- [ ] Do the thing", "createdAt": "3"},
        {"body": "Jake's decision 9 on #278", "createdAt": "4"},
        {"body": "**HANDOFF** two", "createdAt": "5"},
    ]
    kept = [c["createdAt"] for c in brief.select_comments(comments)]
    assert kept == ["3", "4", "5"]
    assert brief.folded_tickets(comments) == ["A4d"]
    # With no HANDOFF, the latest PROGRESS is the resume note.
    assert [c["createdAt"] for c in brief.select_comments(comments[1:4])] == ["2", "3", "4"]


def test_brief_puts_the_pieces_in_one_file():
    issue = {"number": 101, "title": "C3b: Confirm screen", "body": "Body cites F3.", "comments": []}
    text = brief.build_brief("C3b", issue, PLAN, MATH, SPEC)
    assert text.startswith("# Brief for C3b (#101): C3b: Confirm screen")
    assert "## Plan section" in text and "#### C3b: Confirm screen" in text
    assert "### F3. Strip sets" in text and "| PS-09 | Cover |" in text


RESET_SAMPLE = """## 2. What remains, in order

| Step | Tickets | Notes |
|---|---|---|
| 1 | B2b #137 | Decision 1. |
| 2 | C2b #148, then C3b #101 | Two tickets. |

Closed by decision 3: D3b #164.

## 3. How a worker runs a ticket
"""


def test_status_reads_the_reset_table_in_order():
    # Table rows only: #164 sits below the table and is not a ticket to track.
    assert status.reset_order(RESET_SAMPLE) == [(1, 137), (2, 148), (2, 101)]


def test_status_counts_only_the_latest_run_of_each_check():
    # PR #251 on 2026-10-13: the first guard runs were cancelled by a newer push.
    rollup = [
        {"name": "corpus-guard", "status": "COMPLETED", "conclusion": "CANCELLED",
         "startedAt": "2026-10-13T17:07:53Z"},
        {"name": "corpus-guard", "status": "COMPLETED", "conclusion": "SUCCESS",
         "startedAt": "2026-10-13T17:09:30Z"},
        {"name": "web-spike", "status": "COMPLETED", "conclusion": "SUCCESS",
         "startedAt": "2026-10-13T17:07:54Z"},
    ]
    assert status.checks_summary(rollup) == "green"
    rollup.append({"name": "test (3.13)", "status": "COMPLETED", "conclusion": "FAILURE",
                   "startedAt": "2026-10-13T17:08:00Z"})
    assert status.checks_summary(rollup) == "red: test (3.13)"
    rollup.append({"name": "pyodide-tests", "status": "IN_PROGRESS", "conclusion": None,
                   "startedAt": "2026-10-13T17:08:00Z"})
    assert status.checks_summary(rollup) == "red: test (3.13)"
    assert status.checks_summary(rollup[:3] + rollup[4:]) == "running"


def test_status_names_the_latest_progress_note():
    comments = [
        {"body": "PLAN B2b", "createdAt": "2026-10-13T10:18:00Z"},
        {"body": "**BLOCKED** B2b: which rule?", "createdAt": "2026-10-13T17:43:00Z"},
        {"body": "Jake's decision 1 on #278", "createdAt": "2026-10-15T17:30:00Z"},
    ]
    assert status.latest_note(comments) == "BLOCKED 10-13"
