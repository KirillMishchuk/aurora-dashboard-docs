# Fact-check — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7`
- baseRefOid: `cd8e674e2504b9de06d72e09ea4177f8f758bd8c`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `fd248f083f89fbe9caca6ad536106ffd08860159..64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff cd8e674e2504b9de06d72e09ea4177f8f758bd8c...64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7 -- <path>`.

## Your role: the fact-checker

Nothing else re-reads the report's walkthrough — the review agents looked at the code, not at what was written about it. Read `<RUN>/report.md` and check only its descriptive sections — the three "Solution Overview" folds (What was done / How it is implemented / What it affects) and the "QA Test Plan" — this is an Update block, so its "What changed" section (rendered from `overview`) — not the Review:

- every claim about behaviour ("X now calls Y", "the cache is keyed by …") matches the code at headRefOid;
- every consumer claim ("no consumers outside the PR", "all callers were updated") holds on your own `git grep` at headRefOid;
- every place the report contrasts the PR description (`pr-body.md`) with the code is right.

Code excerpts and line citations are already checked by a script — skip them.

## Result shape

Report only the claims that are wrong. For each, point at the source text it was rendered from — `<RUN>/findings.json`: `overview.what|how|affects`, `qa.core_path[i]`, `qa.edge_cases[i]` (0-based, in the order shown), or `findings.<id>.issue|title|explanation|fix`, with an exact piece of it to replace:

```json
{
  "wrong": [
    {
      "claim": "the wrong sentence, quoted from the report",
      "field": "overview.how | qa.edge_cases[3] | findings.<id>.explanation",
      "old": "an exact piece of that field's text, as it appears in the source file (placeholders like [[code:…]] included)",
      "new": "the corrected text",
      "evidence": "commands with their output that show what the code does"
    }
  ]
}
```

Everything holds: `{"wrong": []}`.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as factcheck <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

