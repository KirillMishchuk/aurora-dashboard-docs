{{header}}
## Your role: the earlier findings

This is an Update: the report it extends already raised the findings below, at an older head. You do one thing — for each of them, check the code at headRefOid (the code as it is now, not only the diff) and the replies to it in the review discussion (`discussion.json`: comments, reviews and threads after the report that name it — "I14", the finding's subject), and say whether it still holds:

- `fixed` — the code no longer does what the finding says;
- `partly` — part of it is fixed and part still holds; the note says which part is left;
- `open` — it still holds as written;
- `dropped` — only in three cases: a finding about merge conflicts (with `main` or with other open PRs) or about the PR being a draft — this review no longer covers them; don't check it, the note is "Merge conflicts are no longer part of this review; GitHub shows them." or "Draft state is no longer part of this review; a draft can't be merged anyway." — or a finding a maintainer (a reviewer other than the PR's author, not a bot) asked to do differently in the review discussion (`discussion.json`): the note is "Reversed by <login> in <url>." with the comment's or review's url — or an Improvement (`I…`) or Process item (`P…`) that the author or a maintainer explicitly kept as is in the discussion, with a reason (intentional, documented, out of scope, follow-up): the note is "Kept as is by <login>: <their reason in a few words> (<url>)." A Required Change (`CR…`) is not closed by the author's word: it stays `open` (or `partly`), and the note may add the author's position with the url.

Line numbers in the list are from the older head and may have moved: find the code by what the finding describes, not by the number. Process items: changeset against `context.json` (`changeset`), claims about the PR description against `pr-body.md`.

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
