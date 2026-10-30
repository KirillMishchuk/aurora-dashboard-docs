# Prompt for the agent on the remote machine

Start Claude Code in the repo root with access to DOCS, then paste the
prompt below (fill in the two lines in angle brackets, or delete them):

```bash
git -C ../DOCS pull
claude --add-dir ../DOCS
```

```text
⚠️ **STOP if this session just completed a review run.** This audit MUST run
in a separate session from the review being audited. If you just finished
`/review-and-comment-pr` in this session, tell the user to close this
session first, then start a new one for the audit. The review session's log
must be complete and closed before analysis.

Read ../DOCS/ToolDocs/claude-config/cost-audit/README.md in full and follow it:
audit the cost of my earlier run of `/review-and-comment-pr 1383` in this
project. It cost about €10; the baseline on my main machine is $2.60
(../DOCS/ToolDocs/claude-config/cost-audit/baseline-1383.txt).

<Billing: Anthropic API / Bedrock / Vertex / Claude subscription — currency>
</cost output of that session, if I still have it>

This is a diagnosis only: don't change the skill, agents, settings or the
repo, don't commit or push, don't delete anything, and don't put logs into
DOCS. Ask me before reading under ~/.claude if a prompt appears, and if
several session logs fit, show me the list and let me pick.

Work step by step and reply in Russian, briefly. At the end write
~/review-cost-audit.md as the README says and show it to me.
```


## Follow-up: detailed audit (after the first report)

```text
⚠️ **STOP if this session just completed a review run.** This audit MUST run
in a separate session from the review being audited. If you just finished
`/review-and-comment-pr` in this session, tell the user to close this
session first, then start a new one for the audit. The review session's log
must be complete and closed before analysis.

Pull DOCS (git -C ../DOCS pull) and read
../DOCS/ToolDocs/claude-config/cost-audit/README.md again — the script and
the checks were extended. Your first report is
../DOCS/ToolDocs/claude-config/cost-audit/audit-1383-2026-10-23.md.

1. Confirm which session log is the review run. If the log you used also
   holds the audit work (the script's sanity check says so), find the
   review run on its own and use that.
2. Re-run the script on it (overview), then --agent for "finder d",
   "finder c", "describer", "fact-check" and "main", and compare each with
   the baseline files.
3. Answer with numbers: (a) which rate the bill matches — cost-state vs
   the list-price recount, and my real bill of about €10; (b) what the
   agents do in their extra requests (calls per request, repeated
   commands, errors); (c) whether effort xhigh reached the agents and
   how many thinking tokens it added; (d) anything else the data shows.
   Drop causes the data doesn't support.
4. DOCS now holds a newer skill version than the one installed here
   (Reviewed line, Precedent tag, Must-fix verdict, no merge-tree checks).
   A diff in check 2 is expected — don't count it as a cause and don't
   reinstall.

Diagnosis only, same rules as before; reply in Russian, briefly. Write
the result to ~/review-cost-audit-2.md and show it to me.
```
