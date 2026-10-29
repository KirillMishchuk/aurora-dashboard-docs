# Test run of review-and-comment-pr on another machine — run, collect, analyse

Handover for a Claude Code agent on a machine that has only `DOCS`. The skill is developed on the
main machine; **here** we install the current version, run it on a real PR, collect everything the run
left behind, and **analyse it here**: check every agent and every finding against the code and write
`ANALYSIS.md` with proposed fixes. The analysis reaches the main machine through `DOCS` (step 5); fixes
are made there, never here. The prompt to start this agent with is in `PROMPT.md`.

Your job, in order: 0 install/refresh → (the user runs the skill) → 2 checks and cost → 3 every agent →
4 every finding against the code → 5 `ANALYSIS.md` + copy into `DOCS` → tell the user what to push.
Section 6 lists what this round of runs must answer.

Files here:

| File | What it is |
| --- | --- |
| `sync_install.py` | brings the install here (skill, 3 agents, hook, `settings.local.json`) up to the version in `DOCS`; dry run by default, `--apply` with backups |
| `run_review.py` | starts the skill in Claude Code and, when you quit, collects logs, run folder and DOCS changes into `<parent>/review-runs/<pr>-v<N>/`; `--save` collects a past session, `--pack` makes a `.tar.gz` |
| `check_run.py` | mechanical checks of a collected run → `checks.md` (protocol, agents' tool calls, `save.py` failures, statuses, text leaks) |
| `../cost-audit/audit_session.py` | cost and per-agent activity from the log (its own `README.md`) |
| `baselines/` | the same outputs for two good update runs on the main machine, and the main machine's handoff of 2026-10-28 (Russian: history of every past agent error and its fix) |

Background: `../review-and-comment-pr-docs/SPEC.md` (roles, contracts, invariants, decision log —
read §roles and the invariants before judging an agent) and `README.md` there (Russian, detailed).
The skill itself: `../aurora-dashboard-config/.claude/skills/review-and-comment-pr/` (`SKILL.md`,
`references/briefs/` — each agent's brief, `scripts/`).

## Rules

- Never commit or push `DOCS` or the app repo; never check out a branch there; delete nothing.
- The skill, agents, hook and settings change here only through `sync_install.py --apply` (after the
  user's "yes"). Don't edit them by hand, not even to test a fix: write proposed fixes into the analysis.
- Logs and run folders contain code and environment data: they stay in `<parent>/review-runs/`,
  **never in `DOCS`** (public repo). Don't print keys or tokens — write "present".
- Post to the PR only if the user says "yes" at the skill's Step 8. For a test run the default is **no**.
- One question at a time to the user; say what each run will cost before starting it.

## 0. Install / refresh — before **every** run

The skill alone is not enough: the run also needs the three agent types (`pr-reviewer`,
`external-api-checker`, `security-reviewer`), the hook `check_report_md.py` (also imported by
`render.py`/`prepare_comment.py`) and the permissions, flags, env and hook registration in
`aurora-dashboard/.claude/settings.local.json`. All of them change between versions.

1. `git -C <parent>/DOCS pull` — the user must have pushed the main machine's DOCS first; the KB
   report of the PR (`aurora-dashboard-kb/prs/<n>-*.md`) is what makes the run an **Update**.
2. `python3 sync_install.py` (dry run) — lists what differs: skill files, agents, hook, settings
   entries (template = the JSON block of `../review-and-comment-pr-remote-setup.md`, `<parent>` filled in).
   Show the user the list; on "yes": `python3 sync_install.py --apply` (backs up to
   `<parent>/review-runs/_install-backups/`, copies, merges settings without dropping this machine's
   own entries, checks again → `in sync`). First install on a new machine: the same command; read the
   setup doc's Requirements (`gh` signed in, Opus for the orchestrator) first.
3. Claude Code reads settings, agents and hooks at start — the run starts a new session anyway; in a
   session you keep open, check `/agents` (3 types listed) and `/hooks` (2 hooks).
4. `cd <parent>/aurora-dashboard && git fetch origin` (read-only for the working tree) so `collect.py`
   finds the PR's commits.
5. No other Claude Code session in `aurora-dashboard/` during the run: its log would be collected too.
   `run_review.py` records in `meta.json` whether the installed skill equals DOCS
   (`skill_synced_with_docs`: skill, agents, hook) — if it is not `true`, the run tested the wrong version.

## 1. Run

```bash
cd <parent>/DOCS/ToolDocs/claude-config/review-run-remote
python3 run_review.py <pr>                 # e.g. 1393; after `--`: flags for claude, e.g. -- --model opus
```

It opens a normal interactive Claude Code session in `aurora-dashboard` with `/review-and-comment-pr <pr>`
(DOCS added with `--add-dir`). The user answers the skill's questions (posting: **no** unless told
otherwise; FOLLOW-UPS: as the user decides), then runs `/cost`, **copies its output**, and quits.

**IMPORTANT:** Quit Claude Code immediately after the skill completes (after answering Step 8 posting
and Step 9 FOLLOW-UPS). **Do not perform any other work** (running `check_run.py`, copying files,
diagnostic commands) in the same session — that mixes the skill's log with unrelated tool calls,
inflates the cost audit, and can cause `check_run.py` to report false problems. Open a fresh Claude
Code session for analysis work.

The script then collects into `<parent>/review-runs/<pr>-v<N>/`:

```
session.jsonl, session/subagents/   orchestrator log, one log + .meta.json per agent
run/<pr>-<sha8>/                    context.json, delta.diff, pr.diff, discussion.json, briefs/, out/*.json,
                                    candidates.json, compose.md, texts.json, findings.json, report.md
docs-status.txt, docs.diff, docs-files/   what the run changed in DOCS (report, index, FOLLOW-UPS)
meta.json                           session ids, time span, claude version, git heads, skill in sync
```

Ran plain `claude` instead? `python3 run_review.py --save <pr>-v<N> [--last 2]` collects the last
session(s). Save the `/cost` text as `cost.txt` in the run's folder.

Cost to expect: an Update **$2.7–4** and 6–10 min on the main machine (list prices; this machine's
provider may bill differently — ask the user how). A full review ~$3–4.7.

## 2. Mechanical checks and cost

```bash
R=<parent>/review-runs/<pr>-v<N>
python3 check_run.py "$R" > "$R/checks.md"
python3 ../cost-audit/audit_session.py "$R/session.jsonl" "$R/session" > "$R/audit.txt"
```

Read both in full. Compare with `baselines/1377-v4-update-*` (agents with today's names) and
`baselines/1393-v3-update-audit.txt` (same PR, older role names: `finder a…g` = `find-standards`,
`find-diff-bugs`, `find-history`, `find-discussion`, `find-code-comments`, `find-api-contract`,
`find-security`; `scorer N` = `score-N`; no `find-cross-boundary` and `pr-description` then).

What is normal (1377-v4): orchestrator 14–18 requests, context ≤ 80k, tool calls = `collect.py`,
`briefs.py find`, all listed agents in one message, `briefs.py score`, scorers, `assemble.py`,
Read `compose.md` + `findings-format.md`, write `texts.json`, `assemble.py --texts && render.py`,
`briefs.py factcheck`, factcheck agent, `prepare_comment.py`, 2× AskUserQuestion, then Step 9
(FOLLOW-UPS). Agents: 4–14 requests, context ≤ 65k, $0.05–0.35 each; one `save.py` refusal per
agent that is then fixed is normal (the check worked).

Every `[!]` line in `checks.md` gets a verdict in the analysis: real problem / harmless / expected.
Step 3 tells you how to dig in. For one agent step by step:
`python3 ../cost-audit/audit_session.py "$R/session.jsonl" "$R/session" --agent "<role>"`
(role = the agent's description: `describer`, `find-diff-bugs`, `score-1`, `factcheck`, `main` …).

## 3. Agent by agent — did it do its job?

For each agent: read its brief (`run/…/briefs/<role>.md`), its result (`run/…/out/<role>.json`) and
its log (`--agent <role>`). Ask: did it follow the brief, stay in its role, read the code at the
head SHA (`context.json` → `pr.head`), and is what it saved true? Known failure patterns — check
each, they have all happened before (`baselines/handoff-2026-10-28.md` has the stories):

| Role | What has gone wrong before | How to see it |
| --- | --- | --- |
| orchestrator | did agents' or scripts' work itself (gh, git, reading `context.json`/`candidates.json`/`out/*.json`), changed or merged briefs, launched in background, edited `findings.json`/report by hand, skipped the fact-check or ignored its fixes | `checks.md` §2; `[!]` Bash/Read lines |
| `find-diff-bugs` | missed a real bug one run and found it the next (the 401 redirect loop in #1377) — finder variance | compare with the previous KB report and the user's notes; a bug only one finder saw |
| `find-cross-boundary` | must follow changed code into callers/receivers outside the PR's files | `out/find-cross-boundary.json` `boundaries[].receiver` = `path:line` outside the PR; read 1–2 receivers yourself |
| `find-api-contract` | with the current brief it should `curl -s https://raw.githubusercontent.com/openstack/…` (the API reference); not yet seen live. In `1393-v3` it used `api.github.com` instead (not in the allow-list) | `checks.md` §3 "network:" lines for that agent (`[!]` = not the allowed URL); claims about Barbican/Neutron fields must cite the reference |
| `find-discussion` | credited the wrong person; used our own earlier report as a source | `discussion` field: first person who raised it + URL |
| `pr-description` | "X unchanged" read across sections → false Process item (P3 in #1377) | each `not in code` quote: read the whole section of the PR body it comes from |
| `earlier-findings` | `fixed` where the maintainer asked for the opposite (should be `dropped` "Reversed by <login>"); calls the author "maintainer"; `Kept as is` used for a CR (only I/P may be kept); missed an author's reply in the discussion | `checks.md` §4 statuses; open the code at head for every `fixed` and `open` |
| scorers | a candidate from the discussion about a file the update didn't touch must be 0 "Outside this update's changes"; a maintainer's request beats an earlier finding (not 0); `same_as` chains | `out/score-*.json`, `findings.json` `dismissed` |
| describer / describer-update | wrote about things earlier findings already cover; wrong "What changed" | factcheck result; read "What changed" against `delta.diff` |
| factcheck | missed a wrong claim in the walkthrough | read Solution Overview / What changed against the code yourself, 3–5 claims |
| scripts | merged `main` changes counted as the author's (`delta.diff` should hold only the author's change); text cut mid-sentence; internal names (`find-*`, `context.json`, `headRefOid`) or `[[…]]` in the report | `checks.md` §1 and §5; `delta.diff` vs `git log <old>..<head>` |

## 4. Verify every finding against the code

The report is only as good as its findings. For each finding in `findings.json` and each earlier
finding marked `fixed` / `partly` / `open`:

```bash
cd <parent>/aurora-dashboard
H=<head sha>; git grep -n -A8 '<anchor text from location>' $H -- '<path>'   # or: git show $H:<path> | sed -n '<a>,<b>p'
```

Write per finding: **confirmed** / **wrong** (why, with `path:line`) / **can't tell**. Also look at the
dismissed list for anything that should have been a finding (a high-scored-by-one-agent bug dropped
by a scorer). If you find a real problem no agent reported, say which role should have caught it.

## 5. Write the analysis and hand it over

`$R/ANALYSIS.md`, in this order:

1. **Summary** — 3–5 lines: verdict of the run, is the report right, the main problems.
2. **Run** — PR, mode, heads, cost (`/cost` + audit totals) vs baseline, duration.
3. **Findings check** — table: id · claim · confirmed/wrong/can't tell · evidence.
4. **Agent problems** — per problem: role, what happened (log time or `out/` field), why (brief line,
   script check missing), how bad (changed the verdict? wrong text? cost?).
5. **Script/protocol problems** — same shape.
6. **Proposed fixes** — each: file, "was → becomes", and how to test it (regression fixture or live run).
   One fix = one narrow change; a new check belongs in code (`save.py`/`assemble.py`/`render.py`) or
   in a separate narrow agent, never added to the orchestrator or to another agent's brief (SPEC
   principle; attempts to do otherwise failed).
7. **Not checked** — what you couldn't verify and why.

Write it so the main machine can act without the logs: name files and fields, quote at most a few
lines of code or log per point, give log times (`14:27:08`) and `out/<role>.json` fields as pointers.

Hand-over:

1. Copy it into `DOCS`: `ToolDocs/claude-config/review-run-remote/analyses/<pr>-v<N>-<date>.md`. Before
   that, check the copy: no secrets or tokens, no home-directory paths (write `<parent>/…`), no log dumps.
   DOCS is public; the app code itself is public on GitHub, so short code quotes are fine.
2. `python3 run_review.py --pack <pr>-v<N>` → `.tar.gz` with the logs, for the main machine only if
   the user wants to look deeper (never into DOCS or anywhere public).
3. Tell the user, briefly: the verdict of the analysis, the 3–5 main problems, the path of the analysis
   in DOCS (to commit and push — the user does that), the `.tar.gz` path, and what the run itself
   changed in `DOCS` (`docs-status.txt`: the KB report, index, FOLLOW-UPS). Whether to keep, commit or
   revert those edits is the user's call: the main machine produces its own Update for the same head.

## 6. What this round of runs must answer

Besides the general checks, say for each point: **seen working / seen broken / not exercised**.

- `collect.py` stops an Update whose new commits only merge `main` (mode `none`, "change none of the
  PR's own lines"), no agents launched. On a real Update the delta keeps only the author's lines:
  `delta_base_changes_removed` lists files where merged `main` changes were subtracted (#1393 has two
  merges of `main` since `64c47a99`) — check `delta.diff` holds no hunk that is a `main` change.
- `find-api-contract` on server changes (#1393 `keyManagerRouter.ts`): did it `curl` the OpenStack API
  reference (`raw.githubusercontent.com/openstack/…`), and are its claims backed by it?
- `pr-description`: each item — true? read in its own section of the PR body?
- `find-cross-boundary`: real receivers outside the PR's files; any finding only it made — real?
- `earlier-findings` on a second PR: every earlier finding of the KB report has a status; `fixed`
  checked in code; `dropped` only for merge conflicts, draft, "Reversed by <maintainer>", or an I/P
  "Kept as is by <author/maintainer>" with the reply's link.
- Scorers: discussion points about files the update didn't touch → 0 "Outside this update's changes"
  and listed under "Review comments not taken up"; a maintainer's request is not scored 0 for
  contradicting an earlier finding.
- Report text: "not taken up" lines end in whole sentences; no internal names; links to reviews
  (`#pullrequestreview-…`) and comments resolve.
- Verdict: matches the rules (SPEC §7) given the findings and the earlier ones still open.

If the run stops early (collect exits 1/3, an agent fails twice, render keeps refusing), that is a
result too: collect what exists (`run_review.py --save`), and analyse why.
