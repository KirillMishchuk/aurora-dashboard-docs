---
name: update-kb
description: >-
  Update the project knowledge base in ../DOCS/aurora-dashboard-kb/ after new
  commits land on main. Diffs the repo against the KB's pinned commit, updates
  the affected KB files, moves the pin, and appends the update log. Use when
  the user asks to update/refresh the knowledge base, or after pulling main
  when the KB pin lags behind HEAD.
---

# Update knowledge base

The knowledge base lives OUTSIDE the repo at `../DOCS/aurora-dashboard-kb/`
— relative to the **repo root**, so resolve it explicitly rather than from
wherever the shell happens to be:

```bash
KB_DIR="$(dirname "$(git rev-parse --show-toplevel)")/DOCS/aurora-dashboard-kb"
```

It holds `README.md` (Russian — index, pin, update log, this procedure
duplicated) and `01`-`05` topic files (English).

## Hard rules

- Never move the pinned commit before the affected KB files are updated.
- Verify claims against actual code (`git show`, read the files), not just
  commit messages — messages can overstate or drift.
- Fix outdated statements in place; don't append contradicting text next to
  stale text.
- Keep each file's language: `01`-`05` English, `README.md` Russian.

## Steps

1. **Range.** Read the pinned commit `<PIN>` from the KB `README.md` header.
   Run `git fetch origin` (skip if offline), then
   `git log --oneline <PIN>..origin/main`.
   Empty -> KB is current; tell the user and stop.
2. **Refresh PR-report statuses.** Extract PR numbers referenced in the
   commits from step 1 (the `(#NNNN)` in each commit subject). For each
   number that already has a row in
   `$KB_DIR/prs/README.md`, that PR just got merged —
   update the row's status in place (e.g. `21.07.2026 (открыт, не смержен)`
   -> `21.07.2026 -> смержен 24.07.2026`, using
   `git log -1 --format=%cs <sha>` on the merging commit for the merge date)
   and update the same PR's `**Статус:**` line in its report file under
   `prs/` the same way. Don't touch reports for PR numbers outside this
   commit range, and don't re-run the full `document-pr` review — this is a
   status-only fix.
3. **Filter noise.** Skip `chore(version): update versions with Changesets`
   commits and lockfile-only changes — extract only new package versions
   from them.
4. **Analyze substantive commits.** `git show --stat <sha>`, then read diffs
   of significant files.
5. **Route changes to KB files.**
   - stack, monorepo layout, versions, gotchas -> `01-overview.md`
   - architecture, auth, permissions, server/client patterns -> `02-architecture.md`
   - package APIs, build setup -> `03-packages.md`
   - commands, CI/CD, conventions, releases, testing -> `04-development-workflow.md`
   - new routers, routes, design docs, feature map -> `05-domain-map.md`
6. **Update the affected files.**
7. **Update README.** Move the pin to the new `origin/main` HEAD, update the
   date, prepend an entry to the update log (the `## Журнал обновлений`
   section at the very bottom of the file — keep the full log, don't trim
   old entries):
   `<date> · <old pin> -> <new pin> (N commits, PRs #x-#y): substance; version bumps`.
   If nothing substantive changed, still move the pin and log
   "без существенных изменений".
8. **Report.** Summarize to the user what landed on main, which KB files
   were updated, and which PR-report statuses were refreshed.
