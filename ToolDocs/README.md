---
type: index
---
# ToolDocs

A folder of notes on the tools Kiryl uses at work (part of the single `DOCS` Obsidian vault, not a vault of its own) — a reference not tied to any particular project (unlike `../aurora-dashboard-kb`, which is entirely about aurora-dashboard).

## Contents

| Folder | What's inside |
| --- | --- |
| [`ClaudeDocs/`](./ClaudeDocs/) | Notes on Claude Code: [claude-code-commands.md](./ClaudeDocs/claude-code-commands.md) (slash commands), [claude-code-plugins.md](./ClaudeDocs/claude-code-plugins.md) (plugins), [claude-code-skills.md](./ClaudeDocs/claude-code-skills.md) (skills) |
| [`claude-config/`](./claude-config/) | Backup copies of the `aurora-dashboard` Claude Code config ([`CLAUDE.md`](./claude-config/aurora-dashboard-config/CLAUDE.md) + `.claude/`): [`aurora-dashboard-config/`](./claude-config/aurora-dashboard-config/) — from the local machine, [`aurora-dashboard-config-remote/`](./claude-config/aurora-dashboard-config-remote/) — from the remote one. In the repository itself these files are excluded by `.gitignore` and not versioned, so this is the only copy with history, in case something gets deleted. Synced by hand (later — by the workspace audit skill). Besides the config, the copies contain: `docs/` — a copy of the upstream `aurora-dashboard/docs/` folder (already versioned in the repository itself); `specs/001-bucket-lifecycle-rules/` (local copy only) — Spec Kit artifacts (spec, plan, tasks, research, contracts), the only copy. [`archive/workflows/`](./claude-config/archive/workflows/) — retired Claude Code workflows (`create-plan`, `plan-and-implement`, `triple-review`, `quick-security-check`, Sep 2026), removed from `aurora-dashboard/.claude/` on 2026-10-11 as superseded by the skills of the same names; kept as a record, not used |
| [`GitDocs/`](./GitDocs/) | A practical git command reference: [git-commands.md](./GitDocs/git-commands.md) (setup, everyday work, branches, rebase, syncing with a remote + HTTPS/PAT authentication, history, undoing changes, stash, tags, diagnosing conflicts) |

When notes on another tool appear — add a new subfolder at the top level of `ToolDocs/` and a row in the table above.
