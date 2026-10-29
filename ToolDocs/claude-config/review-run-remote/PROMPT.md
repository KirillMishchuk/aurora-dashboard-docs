# Prompt for the agent on the other machine

Start Claude Code in `<parent>/aurora-dashboard` with `claude --add-dir ../DOCS`, then paste
(replace `<pr>`; for this round: 1393):

```
Read ../DOCS/ToolDocs/claude-config/review-run-remote/README.md in full, then
../DOCS/ToolDocs/claude-config/review-and-comment-pr-docs/SPEC.md (principles, roles, invariants, verdict).
You run and analyse a test run of the review-and-comment-pr skill on PR <pr> on this machine.

1. Step 0 of the README: pull DOCS, run sync_install.py (dry run) and show me what differs in the
   skill, the three agents, the hook and settings.local.json. Apply only after my "yes".
   Tell me: DOCS up to date? install in sync? KB report of the PR present → Update expected?
   Then stop — I start the run myself with run_review.py <pr> in a terminal.
2. When I say the run is done (folder <parent>/review-runs/<pr>-v<N>): steps 2–6 — checks, cost,
   every agent against its brief, every finding and earlier status against the code at head,
   the questions of section 6, ANALYSIS.md, its copy into DOCS (analyses/), the pack.
Rules: answer in Russian, briefly; never commit, push, post to GitHub or change the skill, agents or
settings beyond sync_install.py --apply; logs never into DOCS; ask before anything that costs money
(no extra agents or runs unless I agree to the estimate). If unsure whether something is an agent's
error, say so and show the evidence.
```
