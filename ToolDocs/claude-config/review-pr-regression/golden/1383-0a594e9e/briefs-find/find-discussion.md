# find-discussion — review discussion — review-and-comment-pr, aurora-dashboard PR #1383

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `0a594e9eaf3055cb1c9a102f1aceae43420e7870`
- baseRefOid: `a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd...0a594e9eaf3055cb1c9a102f1aceae43420e7870 -- <path>`.

## Your role: find-discussion — review discussion

Go through `discussion.json`: top-level comments, reviews and inline threads (replies nested). This skill's own earlier reports are marked `own_report` and their bodies omitted — skip them. For each remaining comment, check at headRefOid whether it was addressed, still applies, or was wrong in the first place. In `discussion`, name who first raised the point and give the comment's url — a review's own body has one too (`…#pullrequestreview-<id>` in `discussion.json`). A comment that confirms, disputes or reports fixing a finding of this skill's earlier review (CR2, I4 …) is not where that finding was raised — write it as "CR2 of the earlier review; <author> confirmed it in <url> and listed it as fixed in <url>". One that still applies becomes a candidate like any other — a bot comment is a lead to verify, not evidence; put who raised it, where and what happened in `discussion`.

Earlier PRs, kept short: at most one search — `gh pr list --state merged --search '<a changed path or the feature name>' --limit 5 --json number,title` — and the review comments of at most two hits that look related (`gh api --method GET repos/{owner}/{repo}/pulls/<n>/comments`, one call for both). A comment there that still applies to this PR's code is a candidate. Nothing related → stop and save. Whether a maintainer accepted the same pattern elsewhere is the scorer's question (`precedent`), not yours.

## Result shape

```json
{
  "candidates": [
    {
      "claim": "One or two sentences: what is wrong and what the user or the system gets from it — a concrete case, and when it happens (and when not).",
      "location": "packages/…/file.ts:42",
      "evidence": "What you checked: the code (path:line), commands with their output, doc quotes with URLs, the rule quoted. For a review-standard rule also `example: <path:line>` (see below).",
      "precedent": "Optional: sibling code or an earlier PR doing the same.",
      "discussion": "Optional: who raised it in the review discussion, where, what happened."
    }
  ]
}
```

- `location`: a full repo-relative `path:line`, or `path | <text on that line>` when you know the text but not the number, or one of `PR body`, `PR state`, `PR files`, `CI`.
- Finders report, they don't judge: a violation stays a violation when sibling code does the same or a maintainer accepted it on another PR — report it and put the precedent in `precedent`. Dropping or downgrading candidates is the scorer's job.
- A candidate built on a review-standard rule (its evidence cites `B.<n>` or the Quick Reject list) names the code to copy: `example: <path:line>` in `evidence` — merged code outside this PR's changed files that follows the rule (e.g. `example: packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/FlavorToastNotifications.tsx:1`). If no merged code follows it, write `example: none` — and that is a precedent, so say so in `precedent`. `save.py` refuses a standards candidate without an `example:`.
- Report only problems. A check that passed ("checked, consistent") is not a candidate — leave it out.
- No candidates: `{"candidates": []}`.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as find-discussion <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

