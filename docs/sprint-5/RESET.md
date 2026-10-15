# Sprint 5 reset: how the work runs from 2026-10-15

Status: binding from the merge of its PR. Jake approved the decisions on #278 in his own chat on
2026-10-15, except decision 4: the region re-read tool (B5, C5) and E6 stay in 0.4.0. Where this
file conflicts with the sprint-5 plan, ORCHESTRATOR.md or WORKER.md, this file wins. CLAUDE.md
and docs/SPEC.md still win over this file.

Why this file exists: in 7 days sprint 5 spent about 238 million input tokens per merged PR. 35
percent of all tokens went to review subagents, and 30 percent to writing and critiquing process
documents. 62 percent of all turns ran above 150K of context, and reviews filed 78 follow-up
issues. The rules below keep what prevented real failures and drop the rest. The evidence is on
#278.

## 1. The goal

A quilter with no technical background opens the site on a phone or a computer and picks a photo
of a quilt pieced on a square grid. She confirms where the quilt is and how many squares it has,
and downloads one PDF pattern she can sew from, with math she can trust. If QREP cannot make that
quilt, it says so in plain words before she does any work.

Test every ticket, criterion and review finding against that goal. Work that does not move a
quilter closer to a correct PDF, or keep her from a wrong one, waits on #277.

## 2. What remains, in order

| Step | Tickets | Notes |
|---|---|---|
| 1 | B2b #137 | Decision 1: weigh uncertain squares by confidence, so the vote fixes them. |
| 2 | C2b #148, then C3b #101 | C3b builds the phone Confirm as four steps (SPEC.md section 2). |
| 3 | B3 #138, then B4a #139, then B4b #140 | Ship squares only if triangles fail on real photos. |
| 4 | C3c #150, then C4 #151 | The photo flow uses the confirmed read. |
| 5 | B5 #141, then C5 #152 | The region re-read stays in 0.4.0, as Jake confirmed in SPEC.md section 5: counts never change, a new fabric is allowed, and phones get "Look again here" buttons. |
| 6 | A3b #121, A3c #122, A4b #123, A4c #124 (includes A4d), A5a #126, A5b #127 | Can run beside steps 2 to 5. |
| 7 | C6a #153, C6b #154, B6a #142, B6b #143 (includes B7) | Removal, after its replacement is live. |
| 8 | A6 #128, A7 #129 | A6 applies MATH.md Q2, Q3 and Q7 as answered. |
| 9 | C8a #155 (includes C8b), C11 #160, C7 #97, C8c #157, C9 #158, E6 #179 | Polish. C8c owns the friendliness criteria; C9 ships two examples Jake verifies. |
| 10 | D7 #170, D5 #168 | The release photo check (SPEC.md section 11). |
| 11 | E2 #176, E3 #177 (one round), E4 #98 (includes D8's single panel run) | Docs, one final review, release. Jake does the phone pass and tags. |

Closed by decision 3: D3b #164, D4b #167, D6 #169, D9 #172 and D10 #173. Their branches stay on
the remote.

## 3. How a worker runs a ticket

This section replaces WORKER.md for workers. WORKER.md stays as a reference only, for its gate
table (section 4.1).

**Read, and nothing else, before you write code:**

1. Your brief, `.claude/sprint/briefs/<ID>.md`. The orchestrator writes it before your launch
   with `python scripts/ticket_brief.py <ID>`, and your role prompt names it. It holds:
   - the issue body;
   - the comments that carry criteria, Jake's decisions and the latest resume note;
   - your plan section, and the plan sections of any ticket folded into yours;
   - every MATH.md and PATTERN-SPEC.md entry the text cites.

   If it is missing, run that command yourself.
2. This file's sections 3, 4 and 6.
3. The code you will change.

Do not read ORCHESTRATOR.md, STATE.md, OVERNIGHT-REPORT.md, REVIEW.md, the plan outside your
ticket, or #104's comments. Why: a worker read a median 133K tokens before its first code edit,
and most of it was other people's instructions.

**Rules.** CLAUDE.md's non-negotiables apply in full. In short:

- Work in your own worktree (`scripts/worker_bootstrap.sh <ticket> <branch>`), on your branch, in
  the files your ticket owns.
- Write tests first, with expected values worked by hand in comments.
- Never edit a golden, a fixture, a threshold or an acceptance criterion to pass.
- Delete tracked files only with `git rm`.
- Commit as Jake Mismas, with no AI attribution anywhere.
- Every CV-derived value carries a confidence.
- Two identical failures of the same approach: stop, comment `APPROACH FAILED:` on the issue, and
  try something different or report BLOCKED.

**Gates before you push.**

- Always run lint (G1), native tests (G2), the golden guard (G3), the corpus guard (G4), identity
  (G5) and the dash check (G6), as WORKER.md 4.1 lists them.
- Run the web gates (G7 to G11) only when your diff touches web/ or the wheel.
- Run the Pyodide suite (G12) only when your diff touches qrep/.

CI runs everything on the PR, and CI is the gate that counts.

**The quilter journey.** `web/e2e/journey.spec.ts` (#280) drives the built site as a quilter
does, at phone and desktop sizes:

- It checks the outcome against hand-computed values.
- It runs the plain-language check (`web/e2e/helpers/grandma.ts`) on every screen.
- It writes one contact-sheet image.

A UI ticket extends the journey with its own steps and outcome checks, and its PR does not merge
unless the journey passes. Never add an entry to `web/e2e/grandma-allowlist.json`; it only
shrinks, as the tickets named in it fix their entries. Why: CI was green while a real photo
dead-ended, because no test checked what a quilter actually gets.

**Use a cheaper model for mechanical sub-work.** Your tab runs on Jake's default model, because
a link-launched tab cannot pick one (ORCHESTRATOR.md:39-40). Give each Agent call the model the
work needs:
- `model: "sonnet"`: bulk renames, deleting dead code and its tests, doc updates, and running a
  suite to summarize it.
- `model: "opus"`: reasoning about vision, math or the pattern.

**Keep output small.** Pipe long output through `tail -40` or `head -60`. Use
`git diff --stat` before any full diff, and read a full diff one file at a time. Never `cat` a
file over 40 KB; grep it, then read a range. Run pytest with `-q`, and re-run only the failing
tests until they pass. Why: in sprint 5, shell output alone was 85 MB, and every byte stayed in
context for the rest of the session.

**Hand off at 200K of context**, not 450K. Write a HANDOFF comment on the issue: branch, head SHA,
what is done, what is next, open questions. A fresh session reads only that comment and the issue
body. Why: a turn at 400K re-reads 400K, so a long session costs more per step than a restart
costs once.

**Your PR body** stays under 2 KB:

- `Fixes #N`.
- What changed, in 3 to 6 lines.
- The gates you ran, with their result lines.
- Anything skipped, with the reason.

**When you finish**, send the orchestrator "DONE <ID>: PR #<n>, head <sha>, <pid line>" with
your gate result lines, under 1 KB, then wait. Fix any review findings it sends on the same
branch, and send DONE again. The orchestrator ends your session after the merge, so finished
tabs never pile up. Get the pid line with the PowerShell tool:

```powershell
$p=$PID; while($p){$x=Get-CimInstance Win32_Process -Filter "ProcessId=$p"; if(!$x){break}; if($x.Name -eq 'claude.exe'){"pid $($x.ProcessId) started $($x.CreationDate.ToString('s'))"; break}; $p=$x.ParentProcessId}
```

## 4. Review

- The reviewer runs on `model: "sonnet"` for a standard PR, and the 3-lens panel on
  `model: "opus"`. It returns a JSON verdict: `{"verdict": "approve" | "changes", "findings":
  [{"severity", "file", "line", "summary"}]}`. On a UI PR it also views the journey's contact
  sheet, a single image.
- Each PR gets **one** independent reviewer subagent. It checks:
  - every acceptance criterion against the diff;
  - that the tests' expected values are hand-worked and fail without the change;
  - the non-negotiables.
- A **3-lens panel** (correctness, tests, non-negotiables) runs only on a PR that:
  - changes a contract file (qrep/contract.py, web/src/engine/contract.ts, qrep/bridge.py);
  - deletes code or tests;
  - carries a [bless] or a test retirement;
  - or is the release PR.
- **At most 2 rounds.** Round 2 rechecks only the round-1 findings on the new head. A critical or
  major finding still open after round 2 stops the ticket as BLOCKED, with the finding quoted.
- **Findings:**
  - Critical and major: fixed in the PR.
  - Minor: fixed in the PR if the fix takes under 15 minutes, otherwise dropped.
  - Nits: dropped.
- **Never open an issue for a review finding.** Why: reviews filed 47 issues in 6 days. A real
  defect a quilter would hit, in code outside the PR, goes as one criterion line on the open
  ticket that owns that code. If no ticket owns it, add one line to #277.
- The worker does not run its own review fan-out. The tests, the gates and the one reviewer cover
  it.

## 5. Orchestration

- One orchestrator runs at most 3 workers at once. A worker stays open after DONE to fix review
  findings. The orchestrator ends its session after the merge, by the pid in its DONE report
  (ORCHESTRATOR-BRIEF.md section 7). Why: about 50 open Claude processes tripped the memory
  launch stop on 2026-10-13.
- ORCHESTRATOR-BRIEF.md condenses the parts of ORCHESTRATOR.md that still apply: launching
  (section 8), the handshake (9), merge and close-out (12), stalls and pauses (13), rotation
  (14) and the failure protocol (17). ORCHESTRATOR.md stays as the full reference wherever the
  brief cites it. This file replaces its review (section 11), context (10) and morning report
  (16) rules, and suspends section 15.
- **The orchestrator's working document is ORCHESTRATOR-BRIEF.md** (15 KB or less), not the
  79 KB ORCHESTRATOR.md. Why: each takeover used to cost 140K to 150K tokens before the new
  orchestrator could act.
- **Each tick runs two commands.** `python scripts/sprint_status.py` prints the board.
  `python scripts/ticket_spend.py --since <restart date> --cap-effective 150000000
  --cap-output 1200000` checks spend.

  A ticket over a cap is told to write its HANDOFF and stop. It is then marked BLOCKED, with its
  numbers, in the daily question for Jake.

  These caps are provisional. In last week's transcripts the median ticket used about 90M
  effective input and 450K output, and the 75th percentile was about 150M. After the first 3
  tickets under this file, the orchestrator re-sets the caps from their actual spend and records
  the new numbers here.
- **Wait in the background, never by polling.** Use `gh pr checks <n> --watch` as a background
  command, and task notifications. Do not loop on ListAgents or short ScheduleWakeup calls. Why:
  last week had 569 wakes at about 292K of context each.

  The one exception is a heartbeat. The orchestrator runs under `/loop` and ends each tick with
  one ScheduleWakeup of 1800 to 3600 s, so a usage-limit pause or a lost notification still
  resumes without Jake.
- **Read only short results.** That means a worker's DONE report (1 KB or less), the reviewer's
  JSON verdict and CI pass or fail lines. Never read diffs, logs or test output; the reviewer and
  the worker do that.
- **Check-ins with Jake** are answered from `sprint_status.py`, in 10 lines or fewer.
- **Answered blockers.** When Jake answers a BLOCKED item, post a comment that starts with
  "UNBLOCKED" on its issue, so the board shows it.
- Rotate the orchestrator at 200K of context.
- **STATE.md stays under 15 KB.** It holds only:
  - the current orchestrator;
  - live workers;
  - leases;
  - open PRs;
  - the next 10 in the queue;
  - BLOCKED items;
  - a resume prompt of 2 KB or less.

  At each takeover, move anything older to one comment on #104, then delete it from the file.
  The 392 KB file of 2026-10-13 is archived as STATE-2026-10-13.md (untracked, kept as
  history). Nobody reads it during the sprint.
- **Questions for Jake go into one batched comment on #278 per day**, each with a recommended
  answer. A question that touches no non-negotiable and no SPEC "Jake only" item is not BLOCKED:
  take the option that makes the PDF correct and simpler, and record it in the PR body for his
  audit.
- The morning report is that one comment, under 3 KB. OVERNIGHT-REPORT.md is no longer updated.

## 6. Plain-language rules for every screen

These bind every C ticket and every change to web/src. Why: the app is for a quilter who has never
heard of an engine, a crop or a grid fit.

1. **No engine words on screen.** Banned: engine, Python, vision, read, re-read, region,
   confidence, census, scope, grid fit, pixels, HST, QST, stepper, MB, ms, analyze, reverse,
   crop, quad, approximation, and internal ids such as f0. Say photo, squares, blocks, fabrics,
   borders and pattern. The copy audit enforces this, including text written in JSX (#157).
2. **One primary button per screen.** It is at least 48 px tall, visible without scrolling at
   390 x 660, and named for what happens next.
3. **Every question comes pre-filled when QREP has an answer.** She changes only what is wrong.
4. **Readable and tappable.** Text is at least 16 px (paragraphs 17 to 18 px), contrast is at
   least 4.5:1, and tap targets are at least 44 x 44 px with 8 px gaps.
5. **Failures stay on the page.** They use quilter words and offer one next step. A toast alone
   is never enough.
6. **Never ask her to count from a tiny image.** Show one block zoomed for squares per block, and
   redraw the grid live, so she can see when it matches.
7. **Waits are stated in time, never in size.** No spinner appears without words.
8. **Download is the only file concept.** Say where the file went, offer Open and Share on phones,
   and keep project files out of the flow.

## 7. Records that are finished

Nobody reads these during a ticket. They stay in the repo as history:

- REVIEW.md (a one-time review at 834d8be; its findings now live on tickets).
- The plan's Appendix A (the critique table).
- OVERNIGHT-REPORT.md and its template.
- docs/sprint-5/evidence/.

REBASELINE.md stays binding until the tickets that carry out its rows merge (A7, B6a, B6b, C3c,
C6a, C6b). Its section "Amendments Jake approved on 2026-10-15" adds one standing rule: a PR that
deletes code may retire the tests that exercise only that code, naming them in its PR body.
