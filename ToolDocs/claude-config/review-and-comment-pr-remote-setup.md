# review-and-comment-pr — setup on another machine

Handover for a Claude Code agent on a machine that has `DOCS` but not the
local `aurora-dashboard/.claude/` (it is git-ignored in the repo, so the
only versioned copy is the backup in this folder). Last synced: 2026-10-28.

## What the skill is

Documentation (not part of the skill folder): `review-and-comment-pr-docs/SPEC.md` (English: principles, roles and their contracts, invariants, decision log) and `review-and-comment-pr-docs/README.md` (Russian, detailed walkthrough). Copy only `aurora-dashboard-config/.claude/` into the app repo.

`/review-and-comment-pr <pr>` reviews an open aurora-dashboard PR, writes a
report to `DOCS/aurora-dashboard-kb/prs/<n>-<slug>.md` (+ index row), and
posts it as a PR comment only after an explicit "yes". Scripts do the
mechanical work (collect, briefs, checks, render); the orchestrator (Opus)
launches the Sonnet agents the scripts list and writes the wording.
Answer "no" at the posting step and nothing reaches GitHub.

## Requirements

- Claude Code; orchestrator model Opus (Sonnet does not hold the runbook well).
- `gh` signed in with read access to `cobaltcore-dev/aurora-dashboard`
  (and comment rights, if you will post).
- `python3` 3.9+, `git`, `curl`; network to `raw.githubusercontent.com`,
  `docs.ceph.com`, `docs.aws.amazon.com`; `npm` only for release PRs.
- Layout — the folder must be named `DOCS` and sit next to the repo
  (`collect.py` and the Markdown hook rely on it):

  ```
  <parent>/aurora-dashboard   # clone of cobaltcore-dev/aurora-dashboard
  <parent>/DOCS               # clone of KirillMishchuk/aurora-dashboard-docs
  ```

## Install

Start Claude Code in the repo root and give it access to DOCS:
`cd <parent>/aurora-dashboard && claude --add-dir ../DOCS`.
All commands below run from there; DOCS is `../DOCS`.

1. Update DOCS: `git -C <parent>/DOCS pull`.
2. From the root of `aurora-dashboard`:

   ```bash
   SRC=../DOCS/ToolDocs/claude-config/aurora-dashboard-config/.claude
   mkdir -p .claude/agents .claude/hooks .claude/skills
   cp $SRC/agents/pr-reviewer.md $SRC/agents/external-api-checker.md \
      $SRC/agents/security-reviewer.md .claude/agents/
   cp $SRC/hooks/check_report_md.py .claude/hooks/
   rsync -a --delete $SRC/skills/review-and-comment-pr/ .claude/skills/review-and-comment-pr/
   ```

3. `document-pr` was retired on 2026-10-23 (this skill covers it). If
   `.claude/skills/document-pr/` exists, ask the user before removing it.
4. Do **not** copy `settings.local.json` whole: its absolute paths point
   to the main machine. Merge the keys below into this machine's
   `.claude/settings.local.json` (append to existing lists, keep what is
   already there). Replace `<parent>` with this machine's absolute path
   to the folder that holds `aurora-dashboard` and `DOCS` (`Read` paths
   start with `//`, e.g. `Read(//home/me/projects/**)`). If you take any
   other entry from the backup's `settings.local.json`, rewrite its
   absolute paths to this machine's the same way, and drop entries for
   tools or folders that don't exist here.

   ```json
   {
     "permissions": {
       "allow": [
         "Bash(python3 .claude/skills/review-and-comment-pr/scripts/collect.py)",
         "Bash(python3 .claude/skills/review-and-comment-pr/scripts/collect.py *)",
         "Bash(python3 .claude/skills/review-and-comment-pr/scripts/briefs.py *)",
         "Bash(python3 .claude/skills/review-and-comment-pr/scripts/save.py *)",
         "Bash(python3 .claude/skills/review-and-comment-pr/scripts/assemble.py *)",
         "Bash(python3 .claude/skills/review-and-comment-pr/scripts/render.py *)",
         "Bash(python3 .claude/skills/review-and-comment-pr/scripts/quotes.py *)",
         "Bash(python3 .claude/skills/review-and-comment-pr/scripts/prepare_comment.py *)",
         "Bash(git show *)", "Bash(git grep *)", "Bash(git blame *)",
         "Bash(git fetch *)", "Bash(git rev-parse *)",
         "Bash(gh pr view *)", "Bash(gh pr diff *)", "Bash(gh pr checks *)",
         "Bash(gh pr list *)", "Bash(gh issue view *)", "Bash(gh api --method GET *)",
         "Bash(gh pr comment *)",
         "Bash(npm view *)", "Edit(//tmp/pr-*-comment.md)",
         "Bash(curl -s https://raw.githubusercontent.com/openstack/*)", "Bash(grep *)",
         "WebFetch(domain:docs.openstack.org)", "WebFetch(domain:docs.ceph.com)",
         "WebFetch(domain:docs.aws.amazon.com)",
         "Read(/<parent>/**)"
       ],
       "deny": ["SendFeedback", "ScheduleWakeup", "ShareOnboardingGuide"]
     },
     "enableArtifact": false,
     "disableWorkflows": true,
     "disableClaudeAiConnectors": true,
     "env": { "CLAUDE_CODE_FORK_SUBAGENT": "0" },
     "hooks": {
       "PostToolUse": [{ "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check_report_md.py" }] }],
       "PreToolUse":  [{ "matcher": "Bash",       "hooks": [{ "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check_report_md.py" }] }]
     }
   }
   ```

   On macOS `/tmp` resolves to `/private/tmp`: add
   `"Edit(//private/tmp/pr-*-comment.md)"` as well. Posting needs no extra
   permission prompt: the user's "yes" in the chat (Step 8) is the approval. Show the user the merged file before saving it.

## Check

1. `claude` in `aurora-dashboard` → `/agents` lists `pr-reviewer`,
   `external-api-checker`, `security-reviewer`; `/hooks` lists two hooks.
2. Trial run: `/review-and-comment-pr <pr>` → answer **no** at the posting
   step → `/cost`. Expected: report in `DOCS/aurora-dashboard-kb/prs/`,
   index row in `prs/README.md`, run folder
   `aurora-dashboard/.claude/runs/review-and-comment-pr/<pr>-<sha8>/`
   (git-ignored). Typical cost ~$2.6–3, 7–10 min.

## Rules for the agent on that machine

- Never commit or push `DOCS` or the repo; never check out the PR branch.
  Committing the new report in `DOCS` is the user's call.
- Post to the PR only on the user's explicit "yes" at Step 8.
- Don't edit the skill there. It is developed on the main machine; to
  update, `git pull` DOCS and repeat Install step 2. If a fix is needed,
  describe it to the user instead.
- Known untested paths (report anything odd): Update mode (PR with an
  existing report and new commits), release PRs.
