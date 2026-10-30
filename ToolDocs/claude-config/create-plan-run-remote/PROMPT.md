# Prompt for the agent on the other machine

Start Claude Code in `<parent>/aurora-dashboard` with `claude --add-dir ../DOCS`, then paste
(replace `<task>`: an issue number, `follow-up <n>`, or a link):

```
Read ../DOCS/ToolDocs/claude-config/create-plan-run-remote/README.md in full, then
../DOCS/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/create-plan/SKILL.md and the two
agents (dev-planner.md, plan-reviewer.md in ../aurora-dashboard-config/.claude/agents/).
You run and analyse a test run of the create-plan skill on <task> on this machine.

1. Step 0 of the README: pull DOCS, run sync_install.py (dry run) and show me what differs in the
   skill, the two agents, CLAUDE.md and settings.local.json. Apply only after my "yes". Then the
   regression check. Tell me: DOCS up to date? install in sync? regression OK? which branch is the
   repo on and how far behind origin/main? Then stop — I start the run myself with
   run_plan.py <task> in a terminal, in the normal permission mode.
2. When I say the run is done (folder <parent>/plan-runs/<task>-v<N>): steps 2–6 — checks, cost,
   orchestrator and agents, the plan against the code, the questions of section 6, ANALYSIS.md, its
   copy into DOCS (analyses/), the pack.
Rules: answer in Russian, briefly; never commit, push, or change the skill, agents or settings beyond
sync_install.py --apply; no follow-ups filed on this machine; logs never into DOCS; ask before
anything that costs money (no extra agents or runs unless I agree to the estimate). If unsure whether
something is an agent's error, say so and show the evidence.
```
