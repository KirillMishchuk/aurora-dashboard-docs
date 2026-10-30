# create-plan — setup on another machine

Handover for a Claude Code agent on a machine that has `DOCS` but not the local
`aurora-dashboard/.claude/` (it is git-ignored in the repo, so the only versioned copy is the
backup in this folder). Last synced: 2026-10-30.

## What the skill is

`/create-plan <issue | PR | follow-up N | link>` analyses aurora-dashboard for a task and writes
an implementation plan to `DOCS/plans/` (+ index row in `plans/README.md`), without touching the
code. Two modes: **A** — a new plan (issue, follow-up item, task in words, someone else's PR);
**B** — a round of fixes for the user's own PR from its review, appended to
`plans/<date>-pr-<n>-fixes.md`.

The script `scripts/plan.py` does the mechanical work: `collect` (task, images, git lag, mode,
review sources), `save` (the planner hands in its plan; structure, paths and tail are checked),
`write` (plan file, header, index, `update-related.py`), `followups` (files approved items in
`FOLLOW-UPS.md`). The orchestrator (Opus) launches `dev-planner` (Opus), relays its decisions to
the user, optionally launches `plan-reviewer` (Opus), and writes a few lines of wording.
Regression check of the script: `create-plan-regression/` (no agents, no network).

## Requirements

- Claude Code; Opus for the orchestrator and both agents (`model: opus` in the agents).
- `gh` signed in with read access to `cobaltcore-dev/aurora-dashboard`. Without `gh` the script
  falls back to unauthenticated `curl` (60 requests/hour) and can't tell whose PR it is — it then
  asks (exit 3).
- `python3` 3.9+, `git`, `curl`; network to `api.github.com`, `github.com` (issue images),
  `docs.openstack.org`, `docs.ceph.com`, `docs.aws.amazon.com`.
- Layout — the folder must be named `DOCS` and sit next to the repo:

  ```
  <parent>/aurora-dashboard   # clone of cobaltcore-dev/aurora-dashboard
  <parent>/DOCS               # clone of KirillMishchuk/aurora-dashboard-docs
  ```

  `<parent>/local-mock-backend` exists only on the main machine. Without it the planner can't
  ground the "manual check on the local mock" part of the Testing Plan in the mock's fixtures —
  expected, not an error.
- `aurora-dashboard/CLAUDE.md` (git-ignored in the repo): copy it from
  `aurora-dashboard-config/CLAUDE.md` if this machine has none; the planner reads it first.

## Install

Shortcut for steps 2 and 4 (and for every later update):
`python3 ../DOCS/ToolDocs/claude-config/create-plan-run-remote/sync_install.py` shows what differs
(skill, the two agents, `CLAUDE.md`, the settings below) and `--apply` copies and merges with
backups. The manual steps follow.

Start Claude Code in the repo root with access to DOCS:
`cd <parent>/aurora-dashboard && claude --add-dir ../DOCS`.

1. Update DOCS: `git -C <parent>/DOCS pull`.
2. From the root of `aurora-dashboard`:

   ```bash
   SRC=../DOCS/ToolDocs/claude-config/aurora-dashboard-config
   mkdir -p .claude/agents .claude/skills
   cp $SRC/.claude/agents/dev-planner.md $SRC/.claude/agents/plan-reviewer.md .claude/agents/
   rsync -a --delete $SRC/.claude/skills/create-plan/ .claude/skills/create-plan/
   [ -f CLAUDE.md ] || cp $SRC/CLAUDE.md CLAUDE.md
   ```

3. Nothing else from the main machine's `.claude/` is needed for this skill.
4. Do **not** copy `settings.local.json` whole: its absolute paths point to the main machine.
   Merge the keys below into this machine's `.claude/settings.local.json` (append to existing
   lists, keep what is there; `<parent>` = the absolute path of the folder holding both clones):

   ```json
   {
     "permissions": {
       "allow": [
         "Bash(python3 .claude/skills/create-plan/scripts/plan.py *)",
         "Bash(python3 /<parent>/aurora-dashboard/.claude/skills/create-plan/scripts/plan.py *)",
         "Bash(git show *)", "Bash(git grep *)", "Bash(git blame *)",
         "Bash(git log *)", "Bash(git diff *)", "Bash(git ls-tree *)", "Bash(git ls-files *)",
         "Bash(git merge-base *)", "Bash(git rev-list *)", "Bash(git rev-parse *)",
         "Bash(git status *)", "Bash(git --no-pager *)",
         "Bash(ls *)", "Bash(grep *)",
         "WebSearch",
         "WebFetch(domain:docs.openstack.org)", "WebFetch(domain:docs.ceph.com)",
         "WebFetch(domain:docs.aws.amazon.com)",
         "Read(/<parent>/**)"
       ],
       "deny": ["SendFeedback", "ScheduleWakeup", "ShareOnboardingGuide"]
     },
     "enableArtifact": false,
     "disableWorkflows": true,
     "disableClaudeAiConnectors": true,
     "env": { "CLAUDE_CODE_FORK_SUBAGENT": "0" }
   }
   ```

   The second `plan.py` line is the one the planner uses: its save command has the script's
   absolute path. Show the user the merged file before saving it.

## Check

1. `claude` in `aurora-dashboard` → `/agents` lists `dev-planner` and `plan-reviewer`.
2. `python3 -B ../DOCS/ToolDocs/claude-config/create-plan-regression/run.py --skill .claude/skills/create-plan`
   → every fixture `OK` (the script behaves as on the main machine).
3. Trial run: `/create-plan <issue>` → answer the questions → `/cost`. Expected: plan in
   `DOCS/plans/`, row in `plans/README.md`, run folder
   `aurora-dashboard/.claude/runs/create-plan/<label>/` (git-ignored). Typical cost $1.8–3.5,
   10–13 min; the orchestrator alone ~$0.4.

## Rules for the agent on that machine

- Never commit or push `DOCS` or the repo; never switch branches in the repo unless the user asks.
- Don't file follow-ups on this machine: at step 6 answer **none** (`--skip` for every
  candidate). `FOLLOW-UPS.md` numbers are permanent and the main machine files them too — two
  machines filing would collide.
- Don't edit the skill here. It is developed on the main machine; to update, `git pull` DOCS and
  repeat Install step 2. If a fix is needed, describe it to the user instead.
- Known untested paths (report anything odd): mode B on a real PR of the user's; the `gh`
  branches for PRs (`gh api user`, `closingIssuesReferences`); the allow rule for `plan.py save`
  outside `auto` permission mode; `followups` with real filing (not on this machine).
- Test run with log collection and analysis: `create-plan-run-remote/README.md`
  (`run_plan.py` starts the skill and collects logs outside `DOCS`).
