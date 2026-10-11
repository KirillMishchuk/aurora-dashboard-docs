---
type: tool-notes
---
# Claude Code plugins

A catalog of official Anthropic plugins available in the `claude-plugins-official` marketplace — the same one that provides `skill-creator` (see [`claude-code-skills.md`](claude-code-skills.md)). This is not the same as the list of connected skills: a plugin must be explicitly enabled (`/plugin`, `enabledPlugins` in `~/.claude/settings.json`) before its commands/skills/agents become available in a session. Currently only one is actually enabled in this environment — `skill-creator`.

The marketplace as a whole contains several hundred entries, but the vast majority are third-party integrations (Adobe, Airtable, Atlassian, AWS services, etc.) pulled from external repositories at install time. Below are only the ~53 first-party Anthropic plugins that physically reside in the local clone of the marketplace (`~/.claude/plugins/marketplaces/claude-plugins-official/`) without reaching out to third-party repos: they can be enabled instantly. The third-party catalog is not included here — it is too large and goes stale too quickly to be useful as a reference.

> List checked on 2026-09-24 against `.claude-plugin/marketplace.json` in the https://github.com/anthropics/claude-plugins-official repository (52 plugins with a local source — all of them are here; after 2026-07-24 only third-party plugins were added to the catalog). The statement "only `skill-creator` is enabled" was not rechecked. To check the state: `cat ~/.claude/settings.json` (what is actually enabled) and `~/.claude/plugins/marketplaces/claude-plugins-official/.claude-plugin/marketplace.json` (the full catalog).

## Development and code

| Plugin | Description |
| --- | --- |
| `feature-dev` | A comprehensive feature development workflow: specialized agents for codebase exploration, architecture design, and quality review. |
| `agent-sdk-dev` | A toolkit for developing with the Claude Agent SDK. |
| `mcp-server-dev` | Skills for designing and building MCP servers — deployment models (remote HTTP, MCPB, local), tool patterns, auth, interactive MCP apps. |
| `mcp-tunnels` | Connecting Claude to a private MCP server via an Anthropic MCP tunnel; the `/create-docker-mcp-tunnel` command deploys a complete Docker Compose quickstart (certificates, proxy, cloudflared). |
| `plugin-dev` | A toolkit for developing Claude Code plugins themselves: 7 expert skills on hooks, MCP integration, commands, agents. |
| `code-modernization` | Modernizing legacy code (COBOL, old Java/C++, monolithic web apps) through a structured pipeline preflight → assess → map → extract-rules → transform → harden. |
| `frontend-design` | Creating high-quality, distinctive frontend interfaces — generates polished code while avoiding generic "AI design". |
| `playground` | Generating interactive HTML playgrounds — self-contained explorers with visual controls and live preview. |
| `ralph-loop` | Iterative development through repeated self-referential loops (Ralph Wiggum technique) — Claude works on a single task, seeing its previous work, until it is done. |
| `skill-creator` | Creating and improving skills, evals, benchmarks. Already enabled in this environment — details in `claude-code-skills.md`. |

## PRs, commits, and code review

| Plugin | Description |
| --- | --- |
| `code-review` | Automated PR review by several specialized agents with confidence scoring to filter out false positives. |
| `pr-review-toolkit` | PR review agents by area: comments, tests, error handling, type design, code quality and simplification. |
| `code-simplifier` | An agent that simplifies and tidies recently changed code for clarity and maintainability while preserving behavior. |
| `commit-commands` | Commands for the git workflow — commit, push, PR creation. |

## Security

| Plugin | Description |
| --- | --- |
| `claude-security` | Deep vulnerability scanning of your own code right in the Claude Code session, with a selectable effort level; each finding is re-verified before being reported. |
| `security-guidance` | Security review of Claude-generated code: pattern-based warnings on edits, LLM review of the diff on the Stop hook, an agentic commit reviewer (injections, XSS, SSRF, hardcoded secrets, etc.). |

## Meta: configuring and maintaining Claude Code

| Plugin | Description |
| --- | --- |
| `claude-code-setup` | Analyzes the codebase and recommends Claude Code automations tailored to it — hooks, skills, MCP servers, subagents. |
| `claude-md-management` | Maintaining and improving CLAUDE.md files — quality audits, capturing session learnings, keeping project memory up to date. |
| `hookify` | Creating custom hooks to prevent unwanted behavior — based on conversation patterns or explicit instructions, with rules in markdown. |
| `session-report` | An HTML report on Claude Code session usage — tokens, cache efficiency, subagents, skills, the most expensive prompts. |
| `receipts` | A personal report on the impact of your Claude Code usage — what was done, which projects it went into — for justifying it to a manager or for self-review. |
| `project-artifact` | Generating and publishing a live project status page (overview, success criteria, work plan) as a shareable claude.ai artifact. |

## Language servers (LSP)

They give Claude code understanding and refactoring tools for a specific language via the language server protocol. For aurora-dashboard (a TypeScript/React monorepo) `typescript-lsp` is relevant; the rest are for projects in other languages.

| Plugin | Language |
| --- | --- |
| `typescript-lsp` | TypeScript / JavaScript |
| `pyright-lsp` | Python |
| `gopls-lsp` | Go |
| `rust-analyzer-lsp` | Rust |
| `jdtls-lsp` | Java (Eclipse JDT.LS) |
| `kotlin-lsp` | Kotlin |
| `csharp-lsp` | C# |
| `clangd-lsp` | C / C++ |
| `ruby-lsp` | Ruby |
| `php-lsp` | PHP (Intelephense) |
| `swift-lsp` | Swift (SourceKit-LSP) |
| `lua-lsp` | Lua |

## Learning and output style

| Plugin | Description |
| --- | --- |
| `explanatory-output-style` | Adds educational explanations of architectural decisions and codebase patterns (an equivalent of the retired Explanatory output style). |
| `learning-output-style` | An interactive learning mode — asks the user for meaningful contributions at key decision points. |

## Miscellaneous

| Plugin | Description |
| --- | --- |
| `math-olympiad` | Solving olympiad math (IMO, Putnam, USAMO) with adversarial proof checking by "fresh" verifiers. |
| `cwc-makers` | One-command setup of the Code-with-Claude Makers Cardputer — firmware flashing, installing Claude Buddy. |

## External MCP integrations

Ready-made MCP servers for external services, packaged as plugins (`external_plugins/` in the marketplace). Potentially useful for aurora-dashboard: `github` (repository, PRs, issues — an alternative to the direct `gh` CLI already used by `create-pr`/`document-pr`), `context7` (up-to-date library documentation), and `playwright` (browser E2E testing).

| Plugin | Description |
| --- | --- |
| `github` | The official GitHub MCP server — issues, PRs, code review, repository search, full access to the GitHub API. |
| `gitlab` | The GitLab DevOps platform — repositories, merge requests, CI/CD pipelines, issues, wiki. |
| `context7` | The Upstash Context7 MCP server — up-to-date, versioned documentation and code examples right in the context. |
| `playwright` | Browser automation and E2E testing from Microsoft — page navigation, screenshots, form filling, clicks. |
| `serena` | Semantic code analysis — codebase understanding, refactoring, navigation via the language server protocol. |
| `terraform` | The Terraform MCP server — automation and integration for Infrastructure as Code. |
| `firebase` | Google Firebase — Firestore, authentication, cloud functions, hosting, storage. |
| `laravel-boost` | A toolkit for Laravel — Artisan commands, Eloquent queries, routing, migrations, code generation. |
| `linear` | Linear issue tracking — issues, projects, statuses, search across workspaces. |
| `asana` | Asana project management — tasks, projects, assignments, progress. |
| `discord` | A Discord messaging bridge with access control (pairing, allowlist). |
| `telegram` | A Telegram messaging bridge with access control. |
| `imessage` | An iMessage messaging bridge (reading `chat.db`, sending via AppleScript) with access control. |
| `fakechat` | A local web chat for testing the notification channel — no tokens or external services. |

Third-party plugins (pulled from external repositories, not included in the local clone) are intentionally not listed here. Related to this topic: `greptile` — AI-powered natural-language search and understanding of a codebase (source: `greptileai/claude-plugin`).
