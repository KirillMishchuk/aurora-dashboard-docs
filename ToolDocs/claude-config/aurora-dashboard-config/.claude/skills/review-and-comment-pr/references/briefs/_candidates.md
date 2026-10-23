
## Result shape

```json
{
  "candidates": [
    {
      "claim": "One or two sentences: what is wrong and what it leads to.",
      "location": "packages/…/file.ts:42",
      "evidence": "What you checked: commands with their output, doc quotes with URLs, the rule quoted.",
      "precedent": "Optional: sibling code or an earlier PR doing the same.",
      "discussion": "Optional: who raised it in the review discussion, where, what happened."
    }
  ]
}
```

- `location`: a full repo-relative `path:line`, or `path | <text on that line>` when you know the text but not the number, or one of `PR body`, `PR state`, `PR files`, `CI`.
- Finders report, they don't judge: a violation stays a violation when sibling code does the same or a maintainer accepted it on another PR — report it and put the precedent in `precedent`. Dropping or downgrading candidates is the scorer's job.
- Report only problems. A check that passed ("checked, consistent") is not a candidate — leave it out.
- No candidates: `{"candidates": []}`.
