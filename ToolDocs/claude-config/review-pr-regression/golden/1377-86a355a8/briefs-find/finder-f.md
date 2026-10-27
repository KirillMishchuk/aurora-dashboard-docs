# Finder f — external API contract — review-and-comment-pr, aurora-dashboard PR #1377

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1380.md` (issue #1380 — acceptance criteria), `issue-1381.md` (issue #1381 — acceptance criteria), `issue-1382.md` (issue #1382 — acceptance criteria), `issue-816.md` (issue #816 — acceptance criteria), `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `86a355a8d6da94478e77c0869d9720efe6823e2a`
- baseRefOid: `af14a6a0d76d4a3019d8b49308d503e7247bc338`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `512f01b1bd79771fbf6b959225231e777c2c7c42..86a355a8d6da94478e77c0869d9720efe6823e2a` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff af14a6a0d76d4a3019d8b49308d503e7247bc338...86a355a8d6da94478e77c0869d9720efe6823e2a -- <path>`.

## Your role: finder f — external API contract

The PR changes server code that talks to OpenStack or Ceph RGW. These changed files are in scope:

- `packages/aurora/src/server/Network/helpers/lookupHelpers.ts`
- `packages/aurora/src/server/Network/helpers/portHelpers.ts`
- `packages/aurora/src/server/Network/helpers/requestHelpers.ts`
- `packages/aurora/src/server/Network/helpers/routerHelpers.ts`
- `packages/aurora/src/server/Network/routers/index.ts`
- `packages/aurora/src/server/Network/routers/portsRouter.ts`
- `packages/aurora/src/server/Network/routers/routersRouter.ts`
- `packages/aurora/src/server/Network/types/index.ts`
- `packages/aurora/src/server/Network/types/port.ts`
- `packages/aurora/src/server/Network/types/router.ts`

Check every changed call to OpenStack (`service("<name>")…`) or to Ceph RGW through the S3 client (`Storage/clients`, `Storage/routers/ceph`) in them, and every changed Zod schema describing an API response, against the official references — read them verbatim as your agent instructions describe, never from memory. Put each doc quote with its URL in `evidence`: that is what lets the scorer verify a candidate instead of guessing.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as finder-f <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

