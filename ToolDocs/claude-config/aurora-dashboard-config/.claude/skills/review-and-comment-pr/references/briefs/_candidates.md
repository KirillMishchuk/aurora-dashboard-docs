
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
