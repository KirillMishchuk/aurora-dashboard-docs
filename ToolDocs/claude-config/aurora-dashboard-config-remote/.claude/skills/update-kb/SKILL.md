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
(relative to the repo root): `README.md` (Russian — index, pin, update log,
this procedure duplicated) and `01`-`05` topic files (English).

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
2. **Filter noise.** Skip `chore(version): update versions with Changesets`
   commits and lockfile-only changes — extract only new package versions
   from them.
3. **Analyze substantive commits.** `git show --stat <sha>`, then read diffs
   of significant files.
4. **Route changes to KB files.**
   - stack, monorepo layout, versions, gotchas -> `01-overview.md`
   - architecture, auth, permissions, server/client patterns -> `02-architecture.md`
   - package APIs, build setup -> `03-packages.md`
   - commands, CI/CD, conventions, releases, testing -> `04-development-workflow.md`
   - new routers, routes, design docs, feature map -> `05-domain-map.md`
5. **Update the affected files.**
6. **Update README.** Move the pin to the new `origin/main` HEAD, update the
   date, prepend an entry to the update log (the `## Журнал обновлений`
   section at the very bottom of the file — keep the full log, don't trim
   old entries):
   `<date> · <old pin> -> <new pin> (N commits, PRs #x-#y): substance; version bumps`.
   If nothing substantive changed, still move the pin and log
   "без существенных изменений".
7. **Report.** Summarize to the user what landed on main and which KB files
   were updated.
