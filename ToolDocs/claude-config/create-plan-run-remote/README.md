# Test run of create-plan on another machine — run, collect, analyse

Handover for a Claude Code agent on a machine that has only `DOCS`. The skill is developed on the
main machine; **here** we install the current version, run it on a real task, collect everything the
run left behind, and **analyse it here**: check the orchestrator, both agents and the plan itself
against the code, and write `ANALYSIS.md` with proposed fixes. The analysis reaches the main machine
through `DOCS` (step 5); fixes are made there, never here. The prompt to start this agent with is in
`PROMPT.md`.

Your job, in order: 0 install/refresh → (the user runs the skill) → 2 checks and cost → 3 orchestrator
and agents → 4 the plan against the code → 5 `ANALYSIS.md` + copy into `DOCS` → tell the user what to
push. Section 6 lists what this round of runs must answer.

Files here:

| File | What it is |
| --- | --- |
| `sync_install.py` | brings the install here (skill, `dev-planner`, `plan-reviewer`, the repo's `CLAUDE.md`, `settings.local.json`) up to the version in `DOCS`; dry run by default, `--apply` with backups |
| `run_plan.py` | starts the skill in Claude Code and, when you quit, collects logs, run folder and DOCS changes into `<parent>/plan-runs/<task>-v<N>/`; `--save` collects a past session, `--pack` makes a `.tar.gz` |
| `check_run.py` | mechanical checks of a collected run → `checks.md` (orchestrator's calls, agents' writes and network, `save` refusals, the plan re-checked by the skill's own checks, DOCS changes) |
| `../cost-audit/audit_session.py` | cost and per-agent activity from the log (its own `README.md`) |
| `../create-plan-regression/` | the script's regression check — no agents, no network |
| `baselines/` | audit and checks of a good run on the main machine (`1208-v1`), and the main machine's handoff (Russian: what each change was for, every known problem) |

Background: the skill itself is `../aurora-dashboard-config/.claude/skills/create-plan/` (`SKILL.md`,
`scripts/plan.py`), the agents `../aurora-dashboard-config/.claude/agents/dev-planner.md` and
`plan-reviewer.md`; setup: `../create-plan-remote-setup.md`.

## Rules

- Never commit or push `DOCS` or the app repo; delete nothing. Don't switch branches in the repo
  unless the user asks (a lag test needs a branch behind `main` — the user sets it up).
- The skill, agents, `CLAUDE.md` and settings change here only through `sync_install.py --apply`
  (after the user's "yes"). Don't edit them by hand, not even to test a fix: write proposed fixes into
  the analysis.
- **No follow-ups filed on this machine.** At the skill's step 6 the answer is "none" (`--skip` for
  every candidate): `FOLLOW-UPS.md` numbers are permanent and the main machine files them too.
- Logs and run folders contain code and environment data: they stay in `<parent>/plan-runs/`,
  **never in `DOCS`** (public repo). Don't print keys or tokens — write "present".
- One question at a time to the user; say what each run will cost before starting it.

## 0. Install / refresh — before **every** run

The run needs the skill (`SKILL.md` + `scripts/plan.py`), the two agent types (`dev-planner`,
`plan-reviewer`), the repo's `CLAUDE.md` (the planner reads it first; git-ignored, so only DOCS has it)
and the permissions in `aurora-dashboard/.claude/settings.local.json` — above all the allow rule for
`plan.py` with this machine's absolute path (the planner's save command uses it).

1. `git -C <parent>/DOCS pull` — the user must have pushed the main machine's DOCS first.
2. `python3 sync_install.py` (dry run) — lists what differs (template = the JSON block of
   `../create-plan-remote-setup.md`, `<parent>` filled in). Show the user the list; on "yes":
   `python3 sync_install.py --apply` (backs up to `<parent>/plan-runs/_install-backups/`, copies,
   merges settings without dropping this machine's own entries — the `review-and-comment-pr` ones
   stay — checks again → `in sync`).
3. `python3 -B ../create-plan-regression/run.py --skill <parent>/aurora-dashboard/.claude/skills/create-plan`
   → every fixture `OK`. A difference here means the installed script isn't the main machine's.
4. Claude Code reads settings and agents at start — the run starts a new session anyway; in a
   session you keep open, check `/agents` (both types listed).
5. `cd <parent>/aurora-dashboard && git fetch origin` (read-only for the working tree). Note the
   branch and how far it is behind `origin/main`: the skill asks about the lag (that's tested too).
6. No other Claude Code session in `aurora-dashboard/` during the run: its log would be collected too.
   `run_plan.py` records `skill_synced_with_docs` in `meta.json` — if it is not `true`, the run tested
   the wrong version.

## 1. Run

```bash
cd <parent>/DOCS/ToolDocs/claude-config/create-plan-run-remote
python3 run_plan.py <task>                 # 1208 · follow-up 42 · an issue/PR link; after `--`: flags for claude
```

It opens a normal interactive Claude Code session in `aurora-dashboard` with `/create-plan <task>`
(DOCS added with `--add-dir`). **Use the normal permission mode, not `auto`** — one thing to see is
whether the planner's `plan.py save` asks for permission (it must not). The user answers the
skill's questions (code lag, the planner's decisions, follow-ups: **none**), then runs `/cost`,
**copies its output**, and quits.

**Quit Claude Code right after the skill's report.** Don't do other work in the same session — it
mixes the skill's log with unrelated calls and spoils the checks and the cost audit.

The script then collects into `<parent>/plan-runs/<task>-v<N>/`:

```
session.jsonl, session/subagents/   orchestrator log, one log + .meta.json per agent
run/<label>/                        task.md, context.json, images/, github.md (mode B), plan.md, written.json
docs-status.txt, docs.diff, docs-files/   what the run changed in DOCS (plan, index, Related blocks)
meta.json                           session ids, time span, claude version, git heads + lag, skill in sync
```

A task in words (no issue): run plain `claude`, then `python3 run_plan.py --save <slug>-v1 [--last 2]`.
Save the `/cost` text as `cost.txt` in the run's folder.

Cost to expect (main machine, list prices; ask the user how this machine's provider bills):
$1.8–3.5 and 10–13 min. The orchestrator alone ~$0.4; the planner $0.9–2.4 depending on the task
(decisions, external docs); the plan review, when it runs, ~$0.7.

## 2. Mechanical checks and cost

```bash
R=<parent>/plan-runs/<task>-v<N>
python3 check_run.py "$R" > "$R/checks.md"
python3 ../cost-audit/audit_session.py "$R/session.jsonl" "$R/session" > "$R/audit.txt"
```

Read both in full and compare with `baselines/1208-v1-*`. Every `[!]` line in `checks.md` gets a
verdict in the analysis: real problem / harmless / expected. For one agent step by step:
`python3 ../cost-audit/audit_session.py "$R/session.jsonl" "$R/session" --agent "<description>"`.

What is normal (1208-v1, mode A, an issue with an image, branch 2 commits behind `main`):

- **Orchestrator** 10–14 requests, context ≤ 50k, ~$0.4. Tool calls, in order: `plan.py collect`,
  AskUserQuestion (code lag) → Agent `dev-planner` (foreground) → AskUserQuestion (the planner's
  decisions) → SendMessage to the **same** planner → [Agent `plan-reviewer` → SendMessage with its
  findings] → `plan.py write` → [AskUserQuestion + `plan.py followups`, only with candidates]. No
  `gh`, `git`, `curl`, no Read of `task.md`/`plan.md`/`github.md`, no Write/Edit.
- **dev-planner** reads `task.md` first, the images it lists, `CLAUDE.md` and the KB files it needs,
  then the code; returns `## Decisions needed` or saves with `plan.py save` and replies with the
  `saved …` line. Nothing downloaded, nothing written except through `save`.
- **plan-reviewer** reads `plan.md` by its path, checks claims against code and docs, returns
  `## Plan review`. Read-only.
- **Result**: plan in `DOCS/plans/<date>-<slug>.md` with frontmatter, `**Base:**` (lag included),
  `**Reviewed:**` if the review ran; no home-directory paths; nothing after the last section; one
  new row in `plans/README.md`.

Known findings in 1208-v1 (main machine; see the handoff, items C14–C17): the planner revised
`plan.md` through `/tmp` (no sanctioned way to patch a saved plan yet); the review ran for Ceph/S3
CLI behaviour though the rule names OpenStack; `.;` before the step count in the index row; the
allow rule for `save` unverified (that run was in `auto` mode).

## 3. Orchestrator and agents — did each do its job?

| Role | What has gone wrong before | How to see it |
| --- | --- | --- |
| orchestrator | read the task or plan itself; pasted the task into the planner's prompt; wrote the plan with `Write` (before C11); launched a new planner instead of `SendMessage`; asked the planner's decisions in its own words, dropping options or the recommendation | `checks.md` §2; compare the AskUserQuestion options with the planner's `## Decisions needed` |
| orchestrator | ran the plan review outside the rule (8+ steps, OpenStack behaviour, or the user asks) — or skipped it when the rule applied | step count in `checks.md` §4; the plan's external claims |
| `dev-planner` | downloaded images itself and read outside the repo (before C9/C12); left a file list after the last section and absolute paths (before C8 — `save` now refuses both); wrote to `/tmp` to patch its plan (C14); `grep -r` over `dist/`/`node_modules/` (C10) | `checks.md` §3 `[!]` lines |
| `dev-planner` | planned on a guess instead of returning a decision; folded out-of-scope work into the plan instead of `Proposed follow-ups`; steps not verifiable on their own | read the plan (step 4) |
| `plan-reviewer` | argued with a user decision instead of naming the defect and the decision it comes from; style remarks | its `## Plan review` in the log; findings marked "From a user decision" |
| scripts | `collect` missed the epic or an image, wrong mode; `write` header/index wrong | `run/<label>/task.md`, `context.json`, `checks.md` §1 and §4 |

## 4. The plan against the code

The plan is a contract for the implementer: every file, function, prop and line it names must exist
at the base it records, and every step must be doable as written. In `<parent>/aurora-dashboard`,
at the plan's base (`**Base:**` — the branch/SHA, not necessarily your HEAD):

```bash
B=<sha from Base>; git grep -n '<name>' $B -- '<path>'    # or: git show $B:<path> | sed -n '<a>,<b>p'
```

Check, and write per item **confirmed / wrong (why, path:line) / can't tell**:

1. **Claims the plan rests on** — 5–10 of the Architecture Analysis' "current state" lines and the
   files each step modifies: do they exist and say what the plan says?
2. **Decisions** — each `## Decisions` entry matches what the user answered (the AskUserQuestion
   result in the log), and the steps follow it.
3. **Consistency** — the risk table, the steps, the Testing Plan and the Acceptance Criteria agree
   (the reviewer's job when it ran; check 2–3 cross-references yourself either way).
4. **External claims** — every claim about an API or CLI behaviour carries a doc URL or is marked as
   an assumption / a live check.
5. **Scope** — nothing outside the task folded in; follow-up candidates really outside it.
6. **The task** — re-read `task.md`: does the plan answer what the issue asks (and not the epic)?
   If the issue had a screenshot, did the plan use it and check it against the code?

## 5. Write the analysis and hand it over

`$R/ANALYSIS.md`, in this order:

1. **Summary** — 3–5 lines: verdict of the run, is the plan sound, the main problems.
2. **Run** — task, mode, base and lag, cost (`/cost` + audit totals) vs baseline, duration.
3. **Plan check** — table: item · claim · confirmed/wrong/can't tell · evidence.
4. **Agent problems** — per problem: role, what happened (log time), why (which line of the agent's
   file or `SKILL.md`, or a missing script check), how bad (changed the plan? cost?).
5. **Script/protocol problems** — same shape.
6. **Proposed fixes** — each: file, "was → becomes", and how to test it (a regression fixture in
   `../create-plan-regression/` or a live run). One fix = one narrow change; a check belongs in
   `plan.py` (code) rather than in more instructions to the orchestrator.
7. **Section 6 answers.**
8. **Not checked** — what you couldn't verify and why.

Write it so the main machine can act without the logs: name files and fields, quote at most a few
lines per point, give log times (`15:11:14`) as pointers.

Hand-over:

1. Copy it into `DOCS`: `ToolDocs/claude-config/create-plan-run-remote/analyses/<task>-v<N>-<date>.md`.
   Before that, check the copy: no secrets or tokens, no home-directory paths (write `<parent>/…`),
   no log dumps. DOCS is public; the app code is public on GitHub, so short code quotes are fine.
2. `python3 run_plan.py --pack <task>-v<N>` → `.tar.gz` with the logs, for the main machine only if
   the user wants to look deeper (never into DOCS or anywhere public).
3. Tell the user, briefly: the verdict, the 3–5 main problems, the path of the analysis in DOCS (to
   commit and push — the user does that), the `.tar.gz` path, and what the run changed in `DOCS`
   (`docs-status.txt`: the plan, the index row). Whether to keep, commit or revert the plan is the
   user's call.

## 6. What this round of runs must answer

For each point: **seen working / seen broken / not exercised**.

- **C17 — permissions.** In the normal permission mode, did the planner's `plan.py save` (absolute
  path, heredoc) run without a permission prompt? Did anything else ask (which command)?
- **C14 — patching a saved plan.** After decisions or review findings, how did the planner revise
  the plan: whole plan again through `save`, or edits — and where did it write?
- **C15 — review trigger.** Did the plan review run, and was it the rule (8+ steps, OpenStack
  behaviour, the user asked)? If it ran on other grounds, what did it find?
- **C16** — the index row: no `.;` before the step count.
- **`collect` with `gh`** on this machine: issue + comments + epic, images downloaded (count in
  `checks.md` §1), the lag question when the branch is behind. For a PR: `gh api user` decides the
  mode; `closingIssuesReferences` give `issue:`.
- **No local mock here**: what did the planner do with the "manual check on the local mock" part —
  said it can't check fixtures, or invented them?
- **Mode B** (only if the user has an open PR of their own with a review): review sources listed,
  original plan found or asked, `*-pr-<n>-fixes.md` with `## Round 1`, one index row.

If the run stops early (`collect` exits 1/3, the planner can't save, `write` refuses), that is a
result too: collect what exists (`run_plan.py --save`), and analyse why.
