# Cost audit of a review-and-comment-pr run

Handover for a Claude Code agent on the machine where the run happened.
The prompt to start it with is in `PROMPT.md`.
Goal: find out why a run cost far more than the baseline (e.g. #1383 at
about €10 instead of about $2.6) and report the causes to the user. This
is a diagnosis only.

## Rules

- Don't change the skill, agents, settings or the repo; don't commit or
  push anything; don't delete files. Propose fixes to the user instead.
- Session logs contain code and environment data: don't copy them into
  `DOCS` (a public repo) and don't print secrets (keys, tokens) — if a
  check shows one, say "present" instead of the value.
- Start Claude Code in `aurora-dashboard` with `claude --add-dir ../DOCS`;
  the logs are under `~/.claude/projects/` — ask the user before reading
  there if a prompt appears.

## 1. Find the session log

```bash
P=$(ls -d ~/.claude/projects/*aurora-dashboard* | head -1)
ls -lt "$P"/*.jsonl | head        # pick the review run by time
L=<chosen .jsonl>; S="${L%.jsonl}"  # its subagent logs are in "$S/subagents/"
```

The current session is also a `.jsonl` there — don't confuse it with the
run you audit.

## 2. Run the audit script

```bash
python3 ../DOCS/ToolDocs/claude-config/cost-audit/audit_session.py "$L" "$S" > ~/review-cost-audit.txt
```

It prints: the totals from the log's `cost-state` (cost per model), one
row per agent (model, requests, largest context, estimated share of the
cost, tokens), the orchestrator's context per request, its tool calls and
tool errors. Read the whole output. Ask the user for the `/cost` output of
that session too, and in which currency/provider they were billed.

## 3. Compare with the baseline

Baseline: #1383 on the main machine, 2026-10-23 (same skill version as
the setup in `../review-and-comment-pr-remote-setup.md`), Claude Code
2.1.309, effort medium:

| | Baseline |
| --- | --- |
| Total | $2.60, 8.9 min wall |
| Orchestrator | Opus, $0.90, 22 requests, context 34k → 77k |
| Agents | 14, all Sonnet, $1.70: describer, finders a–g (7), 4 scorers, fact-check |
| Per agent | 4–10 requests, context ≤ 64k, $0.04–0.28 |
| Orchestrator tool calls | Bash 14, Agent 13, AskUserQuestion 2, Read 1 (compose.md), Write 1 (texts.json), Edit 1 |
| Tool errors | none |

Agents run in the foreground (`bg=False`), launched in one message per
step, with no `model` override (they use `model: sonnet` from
`.claude/agents/*.md`).

The full script output of that run is in `baseline-1383.txt` next to this
file: per-agent rows, the orchestrator's context per request, its tool
calls, each agent's tool calls and errors. Compare your output with it
section by section — same agents, request counts, context growth, tool
calls — and explain every difference that costs money. (The baseline
itself has small deviations from the runbook, e.g. `cat compose.md`
instead of Read and ad-hoc `python3 -c` checks; they are cheap there.)

## 4. What to check

For each, say what you found and how much of the cost it explains.

1. **Models and provider.** Which model ran the orchestrator and which ran
   each agent (`model` column). Agents on Opus, or the orchestrator on an
   older/pricier model, multiplies the cost. Check `.claude/agents/*.md`
   frontmatter (`model: sonnet`), the `model` in `Agent` calls, and env
   variables that override models or route to another provider
   (`ANTHROPIC_MODEL`, `ANTHROPIC_DEFAULT_*_MODEL`, `CLAUDE_CODE_SUBAGENT_MODEL`,
   `CLAUDE_CODE_USE_BEDROCK` / `_VERTEX`) — names and values, keys hidden.
   Note the provider's prices if not the Anthropic API.
2. **Skill version and settings.** `diff -rq .claude/skills/review-and-comment-pr
   ../DOCS/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr`;
   the three agents present; `settings.local.json` has
   `"CLAUDE_CODE_FORK_SUBAGENT": "0"`, `"disableWorkflows": true`, the two
   hooks and the script permissions from the setup doc.
3. **Orchestrator turns.** Number of requests vs 22 and how fast the
   context grows. Look for: agents launched in the background or one per
   message (each wake-up re-reads the whole context), large `Read`s or
   `cat` of run-folder files (`context.json`, `pr.diff`, `out/*.json`),
   `gh pr view` / `git` work the scripts already did, an old report read.
4. **Retries and errors.** Tool errors; a script run several times
   (`save.py`, `assemble.py`, `render.py` exit 1); an agent launched twice;
   permission prompts that stalled or were denied; `curl` failures in
   finder f.
5. **Agent sizes.** Any agent far above 10 requests or 64k context — open
   its log in `$S/subagents/` and say what it was doing (e.g. reading the
   whole diff file by file, looping on a failing command).
6. **Number of agents.** More scorers than usual (candidates count from
   `briefs.py score` output), duplicate fact-checks, a second run in the
   same session.
7. **Effort / thinking.** `effort` in the log (baseline `medium`) and
   thinking tokens; a higher effort level raises output and cost.

## 5. Report

Write `~/review-cost-audit.md` (outside `DOCS`): the totals vs baseline,
a table of where the money went (orchestrator / each agent group), the
causes found with their share, and proposed fixes (skill, settings,
environment) — clearly marked as proposals. Show it to the user; they
will bring it to the main machine.
