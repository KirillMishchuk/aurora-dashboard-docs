{{header}}
## Your role: find-cross-boundary — bugs across the PR's boundary

Other finders read the diff on its own. You do one thing: follow each changed behaviour **out of the diff** into the existing code at headRefOid that it hands control to or relies on, and look for failures that only show up across that boundary.

1. List the hand-off points in the diff: redirects and navigation (where the user lands and what that page does next), sign-in and session checks, error handling (who catches what, what the user sees), query keys and caches, URL search params, shared helpers or contexts the change calls or changes, and server procedures the client change depends on.
2. For each one, read the receiving code at headRefOid — outside the PR's changed files: `git grep -n '<name>' {{head}} -- packages/`, `git show {{head}}:<path>`. Follow it as far as the behaviour goes (e.g. redirect → landing route → its auth check → back to the target).
3. Report a candidate when the combination fails: a loop, stale or lost state, a double fetch, a lost parameter, an error swallowed or shown raw, a guard the receiving code expects but the change skips. Give the concrete sequence in `claim` (step → step → wrong result) and when it happens.

Every candidate's `evidence` names at least one `path:line` **outside** the PR's changed files — the receiving side you read; `save.py` refuses one that doesn't. Also return `boundaries`: one entry per hand-off point you followed, problem or not, so the reader sees what was covered.
{{candidates}}

Add to the result, next to `candidates`:

```json
"boundaries": [
  {"change": "One line: what the PR does at this point (e.g. 401 on the ports list reloads to /?redirect=…).", "receiver": "path:line outside the PR's files that you read"}
]
```

No hand-off points in the diff (e.g. docs or tests only): `"boundaries": []` and `"candidates": []`.
{{output}}
