{{header}}
## Your role: scorer {{batch}} of {{batches}}

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

{{groups}}
{{earlier}}
## Candidates

The evidence is as the finders reported it, unchanged.

{{candidates_md}}

## Result shape

```json
{
  "scores": [
    {
      "id": "C1",
      "score": 75,
      "severity": "Moderate",
      "category": "Performance",
      "location": "path:line, verified at headRefOid",
      "reason": "One or two sentences: what you checked and found (file:line, quote, behaviour) and why this score and severity.",
      "same_as": null,
      "precedent": null
    }
  ]
}
```

- One entry per candidate, every candidate exactly once.
- `score`: 0, 25, 50, 75 or 100. For 50 and up, `severity` (Critical, Major, Moderate, Low, Trivial), `category` (Bug, Security, Accessibility, UI/UX, Code Quality, Performance, Docs, Test coverage) and a `location` that exists at headRefOid (`path:line`, `path | text on that line`, or `PR body` / `PR state` / `PR files` / `CI`). Below 50, leave them out.
- `precedent`: required for 50 and up — the reader's tag, it never changes the score. `{"kind": "existing", "ref": "path:line"}` when merged code already has the same problem — `ref` is a line that itself breaks the same rule. Sibling code that does it right (e.g. a list that already debounces) is not a precedent: it's evidence for the finding, put it in `reason`. Find that line at baseRefOid (`git grep -n '<pattern>' <baseRefOid> -- <pathspec>`). `{"kind": "deferred", "ref": "<URL>"}` when a maintainer accepted or postponed the same point, on another PR or in `discussion.json`: open the thread, `ref` is the comment's GitHub URL. Both apply → `deferred`. Neither, or you couldn't confirm the candidate's `precedent` → `null`.
- `same_as`: required for a candidate in a group above — the id of the candidate in the same group that describes the same problem (score that one; this one is then dropped — `score` and `reason` may be left out for it), or `null` if it is a different problem. Elsewhere leave it out.
{{output}}
