{{header}}
## Your role: the earlier findings

This is an Update: the report it extends already raised the findings below, at an older head. You do one thing — for each of them, check the code at headRefOid (the code as it is now, not only the diff) and say whether it still holds:

- `fixed` — the code no longer does what the finding says;
- `partly` — part of it is fixed and part still holds; the note says which part is left;
- `open` — it still holds as written;
- `dropped` — only for a finding about merge conflicts (with `main` or with other open PRs): this review no longer covers them, GitHub shows them. Don't check it; the note is "Merge conflicts are no longer part of this review; GitHub shows them."

Line numbers in the list are from the older head and may have moved: find the code by what the finding describes, not by the number. Process items: draft and changeset against `context.json` (`pr.is_draft`, `changeset`), claims about the PR description against `pr-body.md`.

{{earlier_list}}

## Result shape

```json
{
  "earlier": {
    "CR1": {"status": "fixed", "note": "One line: what changed, or what is left.", "evidence": "The command you ran and the lines of its output that show it."}
  }
}
```

- Every finding listed above exactly once — `save.py` refuses a result with one left out or one that isn't listed.
- `note` is one line for the report's reader. Name other earlier findings by their number (`CR2`); don't make up numbers.
{{output}}
