# Prompt for the agent on the remote machine

Start Claude Code in the repo root with access to DOCS, then paste the
prompt below (fill in the two lines in angle brackets, or delete them):

```bash
git -C ../DOCS pull
claude --add-dir ../DOCS
```

```text
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
