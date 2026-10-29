# find-standards — conventions — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: find-standards — conventions compliance

Audit the PR against the review standards. `copilot-instructions.md` (in the run folder, the version at headRefOid) is an explicit review checklist, and its "What NOT to Review" scope applies here too. Root `CLAUDE.md` (`<REPO>/CLAUDE.md`, on disk only) is guidance for writing code, so not every line of it applies to review; it may be newer than the PR — a mismatch is context, not a violation.

Start with the "Quick Reject Checklist", then every "**Reject**" line in Part B — most B sections end with one, and several name rules the checklist doesn't (a 401/403 handled inline in B.6, a dismissible `Message` without `onDismiss`, a form without validation). Take the items one by one, check each against every changed file — UI strings included (casing, punctuation, wording) — and record one line per item: violated or not violated. A Reject clause that repeats a checklist item can point to it ("see checklist item n"). A general read of the standards misses items; the per-item pass doesn't. Then go through the rules in Part A (architecture & code quality) that apply to the changed files — e.g. data the route loader already fetched is not fetched again in the component — and record them the same way.

Every violation is also a candidate, with the item quoted in `evidence`.

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

For this finder the result has one more key, next to `candidates`:

```json
"checklist": [ { "item": "the item, quoted", "result": "violated | not violated", "where": "path:line, or empty" } ]
```

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as find-standards <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

