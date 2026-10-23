{{header}}
## Your role: finder c — historical context

Run `git log`/`git blame` on the modified files to catch bugs that only make sense in light of history.

Also check the PR against other open PRs. `context.json` → `overlapping_prs` already lists the open PRs that touch the same files, with `git merge-tree` run at both heads:

{{overlaps}}

A conflict only in generated files or catalogs (`conflicts_only_generated`) is not a candidate — they are regenerated. When the description claims the PR is compatible with another one ("doesn't conflict", "same commit as on branch X"), test it — `git fetch origin <their headRefOid>` (or `git fetch origin pull/<n>/head`, without a `:<ref>` part), then `git merge-tree --write-tree --name-only {{head}} <their headRefOid>` — always by SHA, never by a ref name you created. A conflict the description denies is a candidate; so is a real conflict with, or the same work duplicated in, another open PR.
{{candidates}}
{{output}}
