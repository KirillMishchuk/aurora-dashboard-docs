---
type: tool-notes
---
# Built-in Claude Code commands

Slash commands provided by Claude Code (the CLI) itself. Unlike skills ([`claude-code-skills.md`](claude-code-skills.md)) and plugins ([`claude-code-plugins.md`](claude-code-plugins.md)), these are not pluggable modules but part of the core: managing the session, context, configuration, plugins, and account. Some commands are marked in the documentation as **Skill** or **Workflow**: they ship with Claude Code but are implemented as built-in skills. Such commands are marked here with *(skill)* and are described in more detail in `claude-code-skills.md`.

> List checked on 2026-09-24 against the official page https://code.claude.com/docs/en/commands (versions mentioned up to v2.1.269). Enterprise- and provider-specific commands (`/setup-bedrock`, `/setup-vertex`, `/remote-env`, `/passes`) and purely entertainment ones (`/radio`) are omitted. To check whether it is up to date: `/help` in a conversation or the same documentation page.

## Session and context

| Command | Description |
| --- | --- |
| `/clear [name]` | New conversation with an empty context; the name labels the previous one in the `/resume` picker. Aliases: `/reset`, `/new`. |
| `/compact [instructions]` | Frees up context by compressing the conversation into a summary; you can specify what the summary should focus on. |
| `/autocompact [auto\|<tokens>]` | Autocompact threshold: how full the context window gets before automatic compression. |
| `/resume [session]` | Resumes a conversation by ID/name or opens the session picker (background ones are marked `bg`). |
| `/rename [name]` | Renames the session (without a name, generates one from the history). |
| `/context [all]` | Context usage as a colored grid + hints about heavy tools and bloated memory. |
| `/rewind` | Rolls back the conversation and/or code to a checkpoint, or summarizes from the selected message. Alias: `/checkpoint`. |
| `/diff` | Changes in the working tree, including Claude's edits. |
| `/export [filename]` | Exports the conversation as plain text, to a file or via a dialog to the clipboard. |
| `/copy [N]` | Copies the last (or N-th from the end) response to the clipboard. |
| `/branch [name]` | Branches the conversation from the current point to try a different direction. |
| `/fork [prompt]` | Copies the conversation into a new background session while you continue here. |
| `/subtask <task>` | Forked background sub-agent with the full context; the result comes back here. |
| `/background [prompt]` | Detaches the current session into a background agent and frees the terminal. Alias: `/bg`. |
| `/stop` | Stops a background session (only when you are attached to it). |
| `/tasks` | Background work of the current session, including finished sub-agents. Alias: `/bashes`. |
| `/list-agents` | Sub-agents, teammates, and other sessions Claude can message. Alias: `/peers`. |
| `/goal [condition\|clear]` | A goal Claude works toward over several consecutive turns until the condition is met. |
| `/focus` | Focus view: only the last prompt, a one-line tool summary, and the final answer. |
| `/btw [question]` | A side question about the session without adding it to the conversation. |
| `/plan [description]` | Enters plan mode (with a description, starts on that task right away). |
| `/recap` | One-line recap of the session on demand. |
| `/exit` | Exits the CLI (in a background session, detaches). Alias: `/quit`. |

## Help, status, diagnostics

| Command | Description |
| --- | --- |
| `/help` | Help and a list of available commands. |
| `/status` | Settings on the Status tab: version, model, account, connectivity. |
| `/usage` | Session cost, plan limits, activity statistics. Aliases: `/cost`, `/stats`. |
| `/doctor` | *(skill)* Checks the installation, with the option to fix what it finds. Alias: `/checkup`. |
| `/debug [description]` | *(skill)* Enables the session debug log and analyzes the problem using it. |
| `/heapdump` | JS heap snapshot and memory breakdown for diagnostics. |
| `/skills` | List of skills with filtering and sorting by token cost. |
| `/skill-doctor` | How much each skill costs in context and how often it is used. |
| `/insights` | HTML report on recent sessions on this machine. |
| `/release-notes` | Changelog with version selection. |
| `/powerup` | Interactive lessons on Claude Code features. |
| `/bug [report]` | Bug report / conversation sharing (with a consent screen). Alias: `/share`. |
| `/feedback [report]` | Product feedback (the same dialog as `/bug`). |

## Model and working modes

| Command | Description |
| --- | --- |
| `/model [model]` | Switches the model, **saving it as the default** for new sessions; arrow keys set the effort level. |
| `/effort [level\|auto\|status]` | Effort level: low…xhigh, max, ultracode, auto. |
| `/fast [on\|off]` | Fast mode. |
| `/advisor [model\|off]` | Advisor tool: consults a second model at key points of the task. |
| `/output-style [style]` | Lists output styles or switches to one. |

## Permission modes (auto, manual, plan…)

There is **no** separate slash command for changing the mode. The mode is switched with a keyboard shortcut, a launch flag, or a setting. Checked against https://code.claude.com/docs/en/permission-modes (2026-09-24).

| Mode | Value in config / flag | What it does |
| --- | --- | --- |
| Manual | `default` (the flag also accepts `manual`) | Asks before most edits, shell commands, and network actions. |
| Accept edits | `acceptEdits` | Applies file edits and simple file commands (`mkdir`, `touch`, `rm`, `mv`, `cp`, `sed`…) without asking. |
| Plan | `plan` | Only research and planning, no changes. |
| Auto | `auto` | Actions are checked by a classifier model instead of you. On Pro/Max/Team, the default starting mode. |
| Bypass | `bypassPermissions` | No checks (deny rules still apply). |
| Don't ask | `dontAsk` | For CI: runs only what is explicitly allowed (`--allowedTools`) and rejects everything else. |

**Switching during a session (CLI, JetBrains):**

- **`Shift+Tab`** cycles `default` → `acceptEdits` → `plan` → `default`. From `auto`, the first press goes to `default`.
- Optional modes join the cycle after `plan`, with `bypassPermissions` before `auto`:
  - `auto` only when auto mode is available to the plan and organization;
  - `bypassPermissions` only if the session was started with `--permission-mode bypassPermissions`, `--dangerously-skip-permissions`, `--allow-dangerously-skip-permissions`, or with `defaultMode: "bypassPermissions"` in user or managed settings;
  - `dontAsk` never joins the cycle.
- `/plan …` enters plan mode directly with a prompt. `Shift+Tab` exits plan mode without approving the plan; `Ctrl+G` opens the proposed plan in the editor.
- The permission prompt for a Bash command in Manual and `acceptEdits` modes has a **"Yes, and switch to auto mode"** option.

**Mode at startup:**

- a single session: `claude --permission-mode <mode>` (also works with `-p`);
- default: `permissions.defaultMode` in `~/.claude/settings.json`, the project `.claude/settings.json`, or managed settings. `auto` and `bypassPermissions` are ignored in project `.claude/settings.json` / `.claude/settings.local.json`.

```json
{ "permissions": { "defaultMode": "default" } }
```

**Other interfaces:**

- VS Code: mode indicator.
- Desktop, Code tab: a selector next to the send button. The choice is remembered per folder, except for Plan.
- Cloud sessions: Accept edits / Plan / Auto.
- The **Cowork** tab does not use these modes: it has its own permission modes.

Allow/ask/deny rules on top of the mode: `/permissions`.

## Configuration and environment

| Command | Description |
| --- | --- |
| `/config [key=value ...]` | Settings; values can be set directly. Alias: `/settings`. |
| `/permissions` | Allow/ask/deny rules for tools. Alias: `/allowed-tools`. The mode (auto/manual/plan) is changed not here but with `Shift+Tab`; see "Permission modes". |
| `/update-config [request]` | *(skill)* You describe a settings change (hook, env, permission) and Claude edits the right settings file. |
| `/fewer-permission-prompts` | *(skill)* Allowlist of frequent read-only calls in `.claude/settings.json`. |
| `/auto-mode-setup` | Draft of `autoMode.environment` based on the project and recent sessions. |
| `/sandbox` | Sandbox mode (on supported platforms). |
| `/memory` | Edit [`CLAUDE.md`](../../CLAUDE.md), toggle auto memory on/off, view its entries. |
| `/init` | Creates a `CLAUDE.md` for the project. |
| `/hooks` | Hook configuration for tool events. |
| `/import [codex\|gemini\|cursor]` | Migrates configuration from Codex, Gemini CLI, Cursor. |
| `/add-dir <path>` | Additional working directory for tools. |
| `/cd <path>` | Moves the session to another directory, keeping the conversation. |
| `/ide` | IDE integrations and their status. |
| `/theme` | Color theme (including auto and colorblind variants). |
| `/color [color\|default]` | Prompt line color for the session. |
| `/statusline` | Status line setup. |
| `/keybindings` | Keybindings file. |
| `/terminal-setup` | Shift+Enter for newlines in VS Code, Cursor, Alacritty, Zed, etc. |
| `/tui [default\|fullscreen]` | Terminal UI renderer (fullscreen is flicker-free). |
| `/scroll-speed` | Mouse wheel scroll speed. |
| `/voice [hold\|tap\|off]` | Voice dictation. |
| `/privacy-settings` | Privacy settings (Pro/Max). |

## Plugins, MCP, skills

| Command | Description |
| --- | --- |
| `/plugin [subcommand]` | Plugin menu or `list`/`install`/`enable`/`disable`… Marketplaces are here too (there is no separate `/marketplace`). See `claude-code-plugins.md`. |
| `/reload-plugins [--force]` | Applies pending plugin changes without restarting. |
| `/reload-skills` | Rescans the skill and command directories. |
| `/mcp [reconnect\|enable\|disable]` | MCP servers and their OAuth. |
| `/agents` | No longer manages agents: prints a hint to ask Claude or edit `.claude/agents/` directly (since v2.1.198). |

## Account and limits

| Command | Description |
| --- | --- |
| `/login` / `/logout` | Log in to and out of an Anthropic account. |
| `/upgrade` | Plan upgrade page. |
| `/usage-credits` | Usage credits, or requesting them from an admin when you hit the limit. |
| `/rate-limit-options` | Options to keep working when you hit the claude.ai limit. |

## Git, review, PR

The nuances of how these commands differ are in `claude-code-skills.md`.

| Command | Description |
| --- | --- |
| `/code-review [low\|medium\|high\|xhigh\|max\|ultra] [--fix] [--comment] [pr#\|branch\|path]` | *(skill)* Reviews the current diff, PR, branch, or path for correctness bugs. `--fix` applies the fixes, `--comment` posts to the PR. |
| `/review` | **Alias of `/code-review`** (same arguments, e.g. `/review 1234`). |
| `/ultrareview [PR or branch]` | Deep multi-agent review in a cloud sandbox. |
| `/security-review` | Security analysis of the current branch's diff against the origin main branch. |
| `/simplify [target]` | *(skill)* Reviews changed code for cleanup (4 parallel agents) and applies the fixes. |
| `/autofix-pr [prompt]` | A cloud session watches the branch's PR and pushes fixes when CI fails or reviewers comment. |
| `/install-github-app` | Claude GitHub App for the repository (+ optionally GitHub Actions). |

## Running, verification, automation

| Command | Description |
| --- | --- |
| `/run` | *(skill)* Launches the project's app and shows the change in action. |
| `/verify` | *(skill)* Verifies a change by building, running, and observing the result, not just with tests. |
| `/run-skill-generator` | *(skill)* Writes a project skill that teaches `/run` and `/verify` how to build and launch the app. |
| `/loop [interval] [prompt]` | *(skill)* Repeats a prompt while the session is open; without an interval, picks its own pace. Alias: `/proactive`. |
| `/schedule [description]` | Routines: scheduled tasks in the cloud. |
| `/batch <instruction>` | *(skill)* Large-scale changes across the codebase in parallel (5–30 independent parts). |
| `/deep-research <question>` | *(workflow)* Fan-out web search, cross-checking of sources, a report with links. |
| `/workflows` | Workflow progress: view, pause, resume, save. |
| `/workflow-authoring` | *(skill)* Reference for writing workflow scripts. |

## Cloud, devices, integrations

| Command | Description |
| --- | --- |
| `/remote-control` | Makes the session available for Remote Control from claude.ai. |
| `/teleport` | Pulls a cloud session into the terminal. Alias: `/tp`. |
| `/desktop` | Continue the session in Claude Code Desktop. Alias: `/app`. |
| `/web-setup` | Connects a GitHub account for cloud sessions using local `gh` credentials. |
| `/mobile` | QR code for the mobile app. Aliases: `/ios`, `/android`. |
| `/chrome` | Claude in Chrome settings. |
| `/install-slack-app` | Claude app in Slack. |
| `/artifacts` | Your own and shared artifacts: attach to the session, open, copy link. |

## Miscellaneous

| Command | Description |
| --- | --- |
| `/claude-api [...]` | *(skill)* Reference for the Claude API and Managed Agents for the project's language. |
| `/dataviz [request]` | *(skill)* Guide to charts and dashboards. |
| `/design [brief]` | *(skill)* UI mockups, flows, landing pages, posters as a Design artifact. |
| `/design-sync [hint]` / `/design-login` | *(skill)* Uploads the repo's React design system to Claude Design (and authorization for that). |
| `/team-onboarding` | Team onboarding guide based on your usage history. |
| `/stickers` | Order Claude Code stickers. |

## Removed commands

| Command | Status |
| --- | --- |
| `/vim` | Removed in v2.1.92: editor mode is now in `/config` → Editor mode. |
| `/ultraplan` | Removed: use plan mode (`/plan`) instead. |
| `/pr-comments` | Removed in v2.1.91: just ask Claude to show the PR comments. |

## Notes

- The CLI (`claude <command>`, not a slash command in a conversation) separately provides `claude doctor`, `claude mcp`, `claude plugin`, `claude agents` (background agents), `claude update`, `claude auth`, `claude setup-token`: the same capabilities outside a conversation, before a session starts. This list was not re-checked on 2026-09-24.
