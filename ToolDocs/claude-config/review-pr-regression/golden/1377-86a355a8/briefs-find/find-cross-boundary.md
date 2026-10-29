# find-cross-boundary — bugs across the PR's boundary — review-and-comment-pr, aurora-dashboard PR #1377

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1380.md` (issue #1380 — acceptance criteria), `issue-1381.md` (issue #1381 — acceptance criteria), `issue-1382.md` (issue #1382 — acceptance criteria), `issue-816.md` (issue #816 — acceptance criteria), `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `86a355a8d6da94478e77c0869d9720efe6823e2a`
- baseRefOid: `af14a6a0d76d4a3019d8b49308d503e7247bc338`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `512f01b1bd79771fbf6b959225231e777c2c7c42..86a355a8d6da94478e77c0869d9720efe6823e2a` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff af14a6a0d76d4a3019d8b49308d503e7247bc338...86a355a8d6da94478e77c0869d9720efe6823e2a -- <path>`.

## Your role: find-cross-boundary — bugs across the PR's boundary

Other finders read the diff on its own. You do one thing: follow each changed behaviour **out of the diff** into the existing code at headRefOid that it hands control to or relies on, and look for failures that only show up across that boundary.

1. List the hand-off points in the diff: redirects and navigation (where the user lands and what that page does next), sign-in and session checks, error handling (who catches what, what the user sees), query keys and caches, URL search params, shared helpers or contexts the change calls or changes, and server procedures the client change depends on.
2. For each one, read the receiving code at headRefOid — outside the PR's changed files: `git grep -n '<name>' 86a355a8d6da94478e77c0869d9720efe6823e2a -- packages/`, `git show 86a355a8d6da94478e77c0869d9720efe6823e2a:<path>`. Follow it as far as the behaviour goes (e.g. redirect → landing route → its auth check → back to the target).
3. Report a candidate when the combination fails: a loop, stale or lost state, a double fetch, a lost parameter, an error swallowed or shown raw, a guard the receiving code expects but the change skips. Give the concrete sequence in `claim` (step → step → wrong result) and when it happens.

Every candidate's `evidence` names at least one `path:line` **outside** the PR's changed files — the receiving side you read; `save.py` refuses one that doesn't. Also return `boundaries`: one entry per hand-off point you followed, problem or not, so the reader sees what was covered.

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

Add to the result, next to `candidates`:

```json
"boundaries": [
  {"change": "One line: what the PR does at this point (e.g. 401 on the ports list reloads to /?redirect=…).", "receiver": "path:line outside the PR's files that you read"}
]
```

No hand-off points in the diff (e.g. docs or tests only): `"boundaries": []` and `"candidates": []`.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as find-cross-boundary <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

