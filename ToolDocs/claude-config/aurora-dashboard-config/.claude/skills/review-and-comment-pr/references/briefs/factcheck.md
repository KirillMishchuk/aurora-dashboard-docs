{{header}}
## Your role: the fact-checker

Nothing else re-reads the report's walkthrough — the review agents looked at the code, not at what was written about it. Read `{{target}}` and check only its descriptive sections — the three "Solution Overview" folds (What was done / How it is implemented / What it affects) and the "QA Test Plan"{{update_note}} — not the Review:

- every claim about behaviour ("X now calls Y", "the cache is keyed by …") matches the code at headRefOid;
- every consumer claim ("no consumers outside the PR", "all callers were updated") holds on your own `git grep` at headRefOid;
- every place the report contrasts the PR description (`pr-body.md`) with the code is right.

Code excerpts and line citations are already checked by a script — skip them.

## Result shape

Report only the claims that are wrong. For each, point at the source text it was rendered from{{source_note}}, with an exact piece of it to replace:

```json
{
  "wrong": [
    {
      "claim": "the wrong sentence, quoted from the report",
      "field": "{{field_example}}",
      "old": "an exact piece of that field's text, as it appears in the source file (placeholders like [[code:…]] included)",
      "new": "the corrected text",
      "evidence": "commands with their output that show what the code does"
    }
  ]
}
```

Everything holds: `{"wrong": []}`.
{{output}}
