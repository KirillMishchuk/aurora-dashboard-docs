{{header}}
## Your role: finder a — conventions compliance

Audit the PR against the review standards. `copilot-instructions.md` (in the run folder, the version at headRefOid) is an explicit review checklist, and its "What NOT to Review" scope applies here too. Root `CLAUDE.md` (`{{claude_md}}`, on disk only) is guidance for writing code, so not every line of it applies to review; it may be newer than the PR — a mismatch is context, not a violation.

Start with the "Quick Reject Checklist", then every "**Reject**" line in Part B — most B sections end with one, and several name rules the checklist doesn't (a 401/403 handled inline in B.6, a dismissible `Message` without `onDismiss`, a form without validation). Take the items one by one, check each against every changed file — UI strings included (casing, punctuation, wording) — and record one line per item: violated or not violated. A Reject clause that repeats a checklist item can point to it ("see checklist item n"). A general read of the standards misses items; the per-item pass doesn't. Then go through the rules in Part A (architecture & code quality) that apply to the changed files — e.g. data the route loader already fetched is not fetched again in the component — and record them the same way.

Every violation is also a candidate, with the item quoted in `evidence`.
{{candidates}}
For this finder the result has one more key, next to `candidates`:

```json
"checklist": [ { "item": "the item, quoted", "result": "violated | not violated", "where": "path:line, or empty" } ]
```
{{output}}
