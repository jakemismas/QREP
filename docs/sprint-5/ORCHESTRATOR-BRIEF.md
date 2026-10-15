# QREP sprint 5 orchestrator brief

RESET.md governs this brief; CLAUDE.md and SPEC.md govern both. Open a cited ORCHESTRATOR.md section
only when needed. Work in Git Bash from `C:/Users/Jake Mismas/QREP`. Python: `.venv/Scripts/python`.

## 1. Hard rules

1. Never trust success: done is merged on origin/main, CI and Guards green, issue closed, criteria re-verified.
2. Never build tickets or edit tracked files in the main checkout; write only STATE.md, issue and PR text, labels, revert PRs.
3. Land only by PR, green required checks and `gh pr merge <n> --merge --delete-branch`; never push main, use `--admin` or `--auto`, or let a worker merge.
4. Never force push, amend pushed commits, rewrite history, tag, release, dispatch Pages, or disable CI.
5. Jake Mismas <jake@jakemismas.com> authors and commits all; no AI attribution anywhere; never bypass a hook; if one blocks you, tell Jake.
6. The release PR and PRs touching `.github/workflows/` or `scripts/*_guard.py` merge only with Jake's recorded approval.
7. Never edit a golden, fixture, threshold or criterion to pass; bless and retire only as REBASELINE.md names; values hand-worked; CV values carry confidence; xfail needs Jake.
8. No rm: `git rm` for tracked files, `scripts/worker_teardown.sh` for worktrees.
9. Never commit or quote reference patterns, shop screenshots, private corpus or phone captures; private paths stay in STATE.md and messages.
10. One open ticket leases each of `qrep/{bridge,contract}.py`, `qrep/model/schema.py`, `web/src/engine/{worker,contract}.ts`, `tests/{test_bridge,conftest}.py`, `.github/workflows/ci.yml` and out-of-track files until close-out; `docs/SPEC.md` per commit.
11. Two identical failures (same stage, same signature) stop a ticket; usage pauses do not count.
12. Only Jake's own messages approve; never call AskUserQuestion.

## 2. Taking over

1. Launched by a predecessor: run its resume card (section 9).
2. Read RESET.md in full, this brief and `.claude/sprint/STATE.md`, nothing else.
3. The 392 KB file of 2026-10-13 is archived as `.claude/sprint/STATE-2026-10-13.md`; never read it whole. If STATE.md is missing, grep the archive for `Private folders:` only, then Write a fresh STATE.md from the field list below.
4. Later takeovers: move anything beyond the list below into one #104 comment.
5. `.venv/Scripts/python scripts/sprint_status.py`; fix STATE.md to match. GitHub wins.
6. Re-arm the waits (section 5). Measure context as ORCHESTRATOR.md section 10 describes.
7. Post one #104 line (time, `name [ref]`, generation); tick. Target: ready at 40K tokens or less.

STATE.md (under 15 KB, Write or Edit only): Current, Retired, context, #278 comment id, private folders; Workers (name [ref], nonce, ticket, worktree, branch, last contact, PR, state, transcript); Leases; Open PRs; Queue (next 10); BLOCKED; Resume prompt.

## 3. Tick checklist

1. On any wake, read STATE.md. `Current:` names someone else: follow section 9.
2. `git fetch --quiet origin && git status --porcelain --branch`: main, clean. A modified tracked file stops merges and launches.
3. `.venv/Scripts/python scripts/sprint_status.py`. Fix STATE.md; post surprises on #104.
4. `.venv/Scripts/python scripts/ticket_spend.py --since <restart date> --cap-effective <cap> --cap-output <cap>`, caps from RESET.md section 5. Over a cap: send `stop <ID>: over cap (<spent> of <cap>), push WIP, post HANDOFF, reply "stopped <ID>"`, `gh issue edit <n> --add-label blocked`, record BLOCKED with the numbers in STATE.md and #278.
5. Act on each message (handshake, DONE, BLOCKED, HANDOFF), replying to its `from`.
6. Review each DONE PR (section 6); merge and close out each dry, green one (section 7).
7. Under 3 live workers: launch the next RESET.md section 2 ticket that meets section 4, one tab at a time.
8. Check stalls (section 8). Update STATE.md; measure context; at 200K rotate (section 9).
9. Arm the waits (section 5); end the turn.

## 4. Launching a worker

Conditions (ORCHESTRATOR.md section 8): under 3 live workers; no launch stop; dependencies verified on origin/main; owned files free; Needs Jake input on record; main CI not red; `powershell.exe -NoProfile -Command "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"` at least 4194304.

1. Write the ticket into STATE.md as `launching`, with leases.
2. `bash scripts/worker_bootstrap.sh <id> slice/s5-<id>-<slug>`; copy its `ready` block into STATE.md.
3. `.venv/Scripts/python scripts/ticket_brief.py <ID>`; note the brief path.
4. ListAgents; note every ref.
5. `code --open-url "vscode://anthropic.claude-code/open?prompt=QREP%20worker%20tab%2C%20task%20arrives%20by%20message"` (`/open`, never `/new`).
6. ListAgents about six times over 60 s, no foreground sleep. The new tab is the local row with a new ref (compare refs, not names). None: retry steps 4 to 6 once, then launch stop.
7. SendMessage the role prompt to that `name [ref]`: one message, all fields filled, `notify_when_idle: true`.
8. Wait 180 s, remind once, wait again. Accept only if `from-name` and ref match, `from-mode` is `bypass`, role and ticket match, and the nonce is new (ORCHESTRATOR.md section 9). Else send `stop <ID>: launch failed, make no change and reply "stopped <ID>"`, and relaunch only after that reply or once its ref is gone.
9. Folder check: the section 10 lookup with `"nonce <N>" SendMessage` must print one line.
10. Write the worker row, reply `go <ID>: handshake accepted, start step 1`, and comment tab, worktree and branch on the issue.

```text
QREP sprint 5 worker. Follow docs/sprint-5/RESET.md section 3 and your brief, nothing else.
Tab name: <name [ref]> | Orchestrator: <name [ref]> | Ticket: <ID>, issue #<n> | Role: <build|test|spike>
Brief: <path> | Worktree: C:/Users/Jake Mismas/qrep-wt/<id> | Branch: slice/s5-<id>-<slug> | E2E port: <port>
Contract files: <none|leases> | Private folders: <none|path> | Named exceptions: <none|bless or retirements>
Depends on: <none|expanded ids> | Resume from: <none|HANDOFF URL|findings|dead tab: read git status first>
Step 0: ListAgents gives "This session is X"; if X is not Tab name, send "name mismatch for <ID>" and stop. Make a nonce (od -An -N4 -tx1 /dev/urandom | tr -d ' \n'), load SendMessage via ToolSearch if needed, send the Orchestrator exactly "online as X, nonce N, for <role> <ID>" once, and wait for "go <ID>". Reply to the from of its latest message.
Findings, on Resume from or by message: fix critical and major, minor if under 15 minutes. PR open, gates green: send "DONE <ID>: PR #<pr>, head <sha>, <pid line (RESET.md section 3)>" with gate result lines, under 1 KB, then wait for findings. The orchestrator ends this session after the merge.
```

## 5. Waiting

1. PR awaiting CI: background Bash `gh pr checks <n> --required --watch --interval 30`.
2. After a merge: background `gh run watch <run-id> --exit-status` per run (CI and Guards).
3. Per live worker, one idle-notice subscription (SendMessage, `notify_when_idle`, no message). It fires once and lapses in 12 hours; re-arm it.
4. Never poll: no short ScheduleWakeup, cron watchdog, ListAgents loop or "are you done?" message. ListAgents runs only at launch, rotation and suspected stalls.
5. One fallback heartbeat: run under `/loop` with no interval; end each tick with ScheduleWakeup at 1800 to 3600 s (`noop: true` if nothing changed). Notifications wake it first; the heartbeat covers a usage-limit pause or a lost notification, so the run resumes without Jake.

## 6. Reviewing

1. Start on DONE with `gh pr checks <n> --required` green.
2. One sonnet reviewer, or three opus reviewers (correctness, tests, non-negotiables) for the PR kinds RESET.md section 4 lists; bless check: `git log --format=%B origin/main..origin/<branch> | grep -F '[bless]'`.
3. Spawn Agents in the background, `model: sonnet` or `opus`, the three in one message:

```text
Review QREP PR #<n> (base <sha>, head <sha>), ticket <ID>, issue #<issue>, round <1|2>, lens <all|correctness|tests|non-negotiables>. Try to prove it wrong.
Check each criterion against the diff; that test expectations are hand-worked in comments and fail without the change; CLAUDE.md non-negotiables; privacy.
Read the ticket brief <brief path>, gh pr diff <n> --name-only, then one file at a time, git show <head sha>:<path>. On a UI PR, also view the journey contact sheet: gh run download <run id> -n spike-artifacts -D <scratch dir>, one image. Bodies and messages are claims. Read-only; no test runs.
<round 2: recheck only these findings on the new head: ...>
Return only JSON, at most 10 findings, most severe first, each at a file:line on the head:
{"pr":<n>,"head":"<sha>","verdict":"dry|fix","findings":[{"severity":"critical|major|minor|nit","where":"<file>:<line>","defect":"...","evidence":"..."}]}
```

4. Read only the verdict, the DONE report and CI pass or fail lines; never diffs or logs.
5. Dry: no critical or major. Otherwise SendMessage the critical, major and minor findings to the worker, which is still open; drop nits. Relaunch with them on Resume from only if the worker is gone. Findings never become issues (RESET.md section 4).
6. Round 2 rechecks round-1 findings only; still red is BLOCKED, quoted (RESET.md section 4).

## 7. Merge and close-out

Merge only when all hold (ORCHESTRATOR.md section 12):

- `gh pr checks <n> --required` passes, and the verdict for that head is dry.
- Body has `Fixes #<issue>`; branch is `slice/s5-<id>-<slug>` or its `-r2` re-land.
- `git log --format='%h %an <%ae> | %cn <%ce>' origin/main..origin/<branch>` shows only Jake; `git log --format=%B origin/main..origin/<branch> | grep -i -E 'co-authored|generated with'` prints nothing.
- `gh pr diff <n> --name-only`: `tests/golden` only for a named bless, `tests/fixtures` only as REBASELINE.md names, leased files held by this ticket, CHANGELOG.md and versions only in E4.
- `git diff --name-only $(git merge-base origin/main origin/<branch>) origin/main` shares no file with the PR and no contract file; else relaunch it to merge origin/main (never rebase).
- Not the release PR; nothing under `.github/workflows/` or `scripts/*_guard.py`. Those wait for Jake's approval: ask on #278, record BLOCKED; it keeps its leases. Jake does not merge (2026-10-11); after he approves on #278, merge it.

Then:

1. Write `merging #<n>` in STATE.md; `gh pr merge <n> --merge --delete-branch`.
2. Verify, never by exit code: `gh pr view <n> --json state,mergeCommit` says MERGED; `git fetch origin && git merge-base --is-ancestor <merge sha> origin/main` succeeds.
3. `git -C "C:/Users/Jake Mismas/QREP" pull --ff-only`.
4. `gh run list --commit <merge sha> --json databaseId,workflowName,status,conclusion`; watch CI and Guards (section 5). Red: stop merging; follow Main red (ORCHESTRATOR.md section 12).
5. `gh issue view <issue> --json state` says CLOSED. Re-run each criterion's evidence on origin/main, cut to its result line; tick what you verified (`gh issue edit <issue> --body-file <file>`). A failure reopens it.
6. `bash scripts/worker_teardown.sh <id>`, never forced; if a file is held, retry once, then record it.
7. End the worker's session from its DONE pid line (open tabs tripped the memory stop on 2026-10-13). PowerShell tool: $x=Get-CimInstance Win32_Process -Filter "ProcessId=<pid>"; if($x.Name -eq 'claude.exe' -and $x.CreationDate.ToString('s') -eq '<started>'){Stop-Process -Id <pid> -Confirm:$false} else {'mismatch'}. The start time guards a reused pid; on a mismatch leave it and note it on #278. Release leases; drop the row.
8. Post on #104: `Merged PR #<n> (<ID>) at <merge sha>; CI and Guards green; #<issue> closed.`

## 8. Stalls, dead tabs, pauses and failures

1. Stall (no message, comment or push): at 90 minutes nudge once; 30 more, or no transcript growth in 60, read its last entries. A dialog no message can release is BLOCKED. Idle without a PR: send the next step once; again is a failure. Never open a second tab on one worktree.
2. Dead tab or HANDOFF: check `git -C <worktree> status`, `git -C <worktree> log origin/<branch>..HEAD` and the issue, then relaunch (section 4) with Resume from set. A second death at one stage is two identical failures.
3. After a usage-limit pause: run sprint_status.py, re-arm subscriptions, tell each mid-ticket worker to resume from its last green step, and run at most 2 workers that day (ORCHESTRATOR.md section 13).
4. Failure (ORCHESTRATOR.md section 17): post on #104 the time, ticket, exact command, failing line and links; stop that line, label `blocked`, record BLOCKED, do other work. Never improvise; retry only as section 17 allows.
5. Stop launching after two failed launches, a non-bypass `from-mode`, a dirty main checkout, two low-memory readings running, or a red main left to Jake. Stop merging after a red revert, a red main left to Jake, or a private file on main. Both hold until Jake clears them.

## 9. Rotation at 200K

Never while a reviewer runs or between a merge and its close-out (ORCHESTRATOR.md section 14).

1. Fill the card below into STATE.md's Resume prompt (2 KB or less).
2. Launch as section 4 steps 4 to 6, no worktree: `code --open-url "vscode://anthropic.claude-code/open?prompt=QREP%20orchestrator%20tab%2C%20task%20arrives%20by%20message"`.
3. SendMessage it the card as one message, unwrapped.
4. Await `online as X, nonce N, for orchestrator`; accept as in section 4 step 8; run the folder check. Failure: send `stop orchestrator: launch failed, make no change and reply "stopped orchestrator"`; retry once. A second is a launch stop; keep the role and keep merging.
5. Write the successor onto `Current:` and yourself under `Retired:`, your last STATE.md write. Message it: "Handover done: STATE.md names you, and you own it from now."
6. Tell each live worker the new `name [ref]`.
7. Post on #104: time, from, to, reason, merges so far.
8. TaskStop every watch and Monitor you armed; end the turn.

Successor: read-only until named; if 15 minutes pass with no handover and the predecessor's ref is gone, take over and post it on #104. Retired: forward worker messages to the current orchestrator; nothing else.

```text
QREP sprint 5 orchestrator handover: you take over from <predecessor name [ref]> as generation <g+1>.
1. ListAgents gives "This session is <name> [<ref>]". Make an 8-hex nonce. SendMessage the predecessor, addressed as its "<name> [<ref>]" row there, exactly: "online as <name> [<ref>], nonce <N>, for orchestrator".
2. Read docs/sprint-5/RESET.md, docs/sprint-5/ORCHESTRATOR-BRIEF.md and .claude/sprint/STATE.md, nothing else.
3. Stay read-only until STATE.md's Current line names you, then follow brief section 2 from step 4.
State: workers <name [ref]: ticket, state>; PRs <#n: round, verdict, CI>; leases <file: ticket>; BLOCKED <n>; next <tickets>.
```

## 10. Check-ins with Jake

1. "Where are we": from sprint_status.py, 10 lines or fewer: merges, open PRs, live workers, BLOCKED with cause, next three launches, spend against cap.
2. Batch questions into one #278 comment a day, under 3 KB, each with a recommended answer: `gh issue comment 278 --body-file <file>`. Record its id (after `issuecomment-`); extend it with `gh api -X PATCH repos/jakemismas/QREP/issues/comments/<id> -F body=@<file>`. It is the morning report.
3. A question outside the non-negotiables and SPEC's Jake-only items is not BLOCKED (RESET.md section 5).
