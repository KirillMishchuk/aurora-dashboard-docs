---
type: tool-notes
---
# Claude Code skills

Skills (`/commands`) available in Claude Code in this working environment. **Built-in** ones ship with Claude Code itself and work in any project. **Plugin** ones appear only after the plugin is enabled. **Project** ones are specific to `aurora-dashboard` and live in the repository's `.claude/skills/`. They are invoked via `/skill-name` or trigger automatically based on the task description.

> Built-in skills checked on 2026-09-24 against https://code.claude.com/docs/en/commands (rows marked Skill/Workflow). Project skills checked against `aurora-dashboard/.claude/skills/` on the same date. The catalog of official plugins is in [`claude-code-plugins.md`](claude-code-plugins.md); the remaining slash commands are in [`claude-code-commands.md`](claude-code-commands.md).

## Built-in skills

| Skill | Description |
| --- | --- |
| `code-review` | Reviews the current diff, **or** a PR (number), branch, or path — for correctness bugs. Effort levels `low`/`medium`/`high`/`xhigh`/`max`/`ultra` (`ultra` is a cloud review, like `/ultrareview`). `--comment` posts findings inline on the PR, `--fix` applies the fixes right away. `/review` is just its alias. |
| `simplify` | Reviews changed code for reuse, simplification, and efficiency (4 parallel agents) and applies the edits right away. Code quality only, it does not look for bugs — use `code-review` for that. |
| `verify` | Checks that a change actually works: builds, runs the app, and looks at the result, not just tests and the typecheck. |
| `run` | Starts and exercises the project's app to see the change in action. |
| `run-skill-generator` | Writes a project skill that teaches `run`/`verify` to build, start, and drive the app from a clean environment. |
| `debug` | Enables the session debug log and investigates the problem using it. |
| `doctor` | Checks the Claude Code installation (duplicates, PATH, etc.) with the option to fix it. |
| `batch` | Large-scale changes across the codebase: splits the work into 5–30 independent parts and executes them in parallel. |
| `loop` | Runs a prompt/command periodically while the session is open (e.g., `/loop 5m /foo`); without an interval the model picks the pace itself. |
| `fewer-permission-prompts` | Scans transcripts for frequent read-only Bash/MCP calls and adds an allowlist to `.claude/settings.json`. |
| `update-config` | You describe a settings change (a hook "every time X", a permission, env) — Claude edits the appropriate settings file. |
| `claude-api` | A reference for the Claude API and Managed Agents for the project's language; subcommands `migrate`, `upgrade`, `prompt-audit`, `cost-optimize`, `build-eval`, and others. |
| `dataviz` | A design guide for charts, graphs, and dashboards: chart form, color by role, palette validation. |
| `design` / `design-sync` | Mockups, flows, and landing pages as a Design artifact; `design-sync` exports the repo's React design system to Claude Design. |
| `workflow-authoring` | A reference for writing workflow scripts (API, resume, patterns). |
| `deep-research` | *(workflow)* Fan-out web search, cross-checking of sources, a report with links. |

Related commands that are **not** marked as skills in the documentation: `/security-review` (security analysis of the branch diff against the origin main branch), `/ultrareview`, `/schedule` (scheduled routines in the cloud), `/init` (creating [`CLAUDE.md`](../../CLAUDE.md)), `/keybindings`. There is no `keybindings-help` skill in the current documentation.

## Skills from plugins and the environment

| Skill | Source | Description |
| --- | --- | --- |
| `skill-creator` | the `skill-creator` plugin | Creating and improving skills: interview, SKILL.md draft, evals, baseline/with-skill comparison, description optimization. |
| `artifact-design`, `artifact-capabilities`, `claude-in-chrome` | environment (Cowork / cloud sessions) | Guides for Artifacts and browser control. They were available as of 2026-07-24 but are not listed in the CLI documentation — they depend on the runtime environment. |

## aurora-dashboard project skills

They live in `aurora-dashboard/.claude/skills/` (19 of them) and work only in the context of this repository.

### Planning, implementation, review

| Skill | Description |
| --- | --- |
| `create-plan` | Studies the architecture relevant to the task and drafts a detailed plan (risks, steps, testing, definition of done) via `dev-planner`; it does **not** write code. The plan is saved to `../DOCS/plans/` and the index is updated. |
| `implement-plan` | Implements an existing plan (from `create-plan`, from a previous session, or a manual one) via `dev-executor`, followed by a targeted security pass. If there is no plan, run `create-plan` first. |
| `triple-review` | Reviews changes from three angles in parallel (security, performance, architecture) with three subagents, plus a summary. Takes uncommitted changes, or, if there are none, the whole branch (`main...HEAD`). Saves the report to `../DOCS/pr-reviews/pr-<n>-review.md` (or `<branch>-review.md` while there is no PR) and updates the index in `pr-reviews/README.md`; a rerun overwrites the file. It does not create a fix plan and publishes nothing to GitHub. |
| `quick-security-check` | A quick security audit of a single file or component via `security-reviewer`. |

### Git and PRs

| Skill | Description |
| --- | --- |
| `create-pr` | Syncs the branch with main, walks through conflicts and the merge commit, generates a description from `.github/pull_request_template.md`, and opens a draft PR via `gh`. |
| `rework-commits` | Splits the branch's **last commit** into a series of small semantic commits (schema/DB → backend → frontend) with a rollback point and a before/after diff comparison. |
| `document-pr` | Fetches a PR (number/URL/current branch) via `gh` and produces a breakdown in Russian — what was done, how, and what it affected in the monorepo (code with file:line) — plus a review with confidence scoring (5 agents + a ≥80 filter). The report goes to `../DOCS/aurora-dashboard-kb/prs/` and the index is updated. |
| `temp-sync` | A snapshot of git-staged files into `../DOCS/transfer/temp-files` (the files themselves with their hierarchy) and `../DOCS/transfer/patch` (a single `git diff --cached --binary` patch for transfer to another machine); both subfolders are cleared on every run. It also writes a PR description for the same set of changes to `../DOCS/pr-descriptions/` (a cumulative folder, not cleared). It commits and publishes nothing. |

### Knowledge base

| Skill | Description |
| --- | --- |
| `update-kb` | Updates `../DOCS/aurora-dashboard-kb/` after new commits on main: diff from the pinned commit, editing the affected files, moving the pin, an entry in the log. |

### Spec Kit (spec-driven development)

The `speckit-*` set drives a feature through the artifacts `spec.md` → `plan.md` → `tasks.md`. **It requires a `.specify/` directory at the repository root** (templates, scripts, `memory/constitution.md`) — `aurora-dashboard` currently does not have one, so the skills do not work until Spec Kit is initialized. The only surviving output of a previous run is `../claude-config/aurora-dashboard-config/specs/001-bucket-lifecycle-rules/`.

| Skill | Description |
| --- | --- |
| `speckit-constitution` | Creates or updates the project's "constitution" — its core principles. |
| `speckit-specify` | Creates or updates a feature specification from a natural-language description. |
| `speckit-clarify` | Finds underspecified areas of the spec: up to 5 targeted questions, with the answers written back into the spec. |
| `speckit-plan` | A template-based planning workflow — design artifacts. |
| `speckit-tasks` | A dependency-ordered `tasks.md` from the design artifacts. |
| `speckit-analyze` | A non-destructive consistency and quality check of spec/plan/tasks after task generation. |
| `speckit-checklist` | A custom checklist for the current feature based on the user's requirements. |
| `speckit-implement` | Executes the plan, working through all tasks in `tasks.md`. |
| `speckit-converge` | Reconciles the code with spec/plan/tasks and adds unfinished work as new tasks in `tasks.md`. |
| `speckit-taskstoissues` | Turns tasks into ordered GitHub issues. |

### How the project skills are structured

`create-plan`/`implement-plan`/`triple-review`/`quick-security-check` do not contain the review logic themselves but delegate it to five subagents from `.claude/agents/` (`dev-planner`, `dev-executor`, `security-reviewer`, `performance-reviewer`, `architecture-reviewer`). These agents know the specifics of the aurora-dashboard stack: tRPC procedures, oslo.policy, the absence of SQL/JWT/GraphQL/CORS, etc. A skill describes the workflow (whom to call, in what order, what to do with the result), while the project knowledge lives in the agent files. That is why the skills pick up agent improvements automatically, without changes to the skills themselves.

Next to it is `.claude/workflows/` with the same scenarios in workflow format (descriptions in Russian):

- `create-plan` — a plan with architecture analysis, without implementation;
- `plan-and-implement` — the full cycle: plan → implementation → review;
- `quick-security-check` — a quick check of a single file;
- `triple-review` — parallel review by three agents.
