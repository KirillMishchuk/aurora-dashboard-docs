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
KB_DIR="$(dirname "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")")/DOCS/aurora-dashboard-kb"
```

It holds `README.md` (index, pin, update log) and
`01`-`05` topic files. Everything is in English.

## Hard rules

- Never move the pinned commit before the affected KB files are updated.
- Verify claims against actual code (`git show`, read the files), not just
  commit messages — messages can overstate or drift.
- Fix outdated statements in place; don't append contradicting text next to
  stale text.
- Write everything in English — `01`-`05`, `README.md` and its update log,
  and any PR-report status you touch. Older PR reports under `prs/` were
  written in Russian and are kept as historical records; don't translate
  them, just update their status line (see step 2).

## Steps

1. **Range.** Read the pinned commit `<PIN>` from the KB `README.md` header.
   Run `git fetch origin` (skip if offline), then
   `git log --oneline <PIN>..origin/main`.
   Empty -> KB is current; tell the user and stop.
2. **Refresh PR-report statuses.** Extract PR numbers referenced in the
   commits from step 1 (the `(#NNNN)` in each commit subject). For each
   number that already has a row in
   `$KB_DIR/prs/README.md`, that PR just got merged —
   update the row's status in place (e.g. `2026-07-21 (open, not merged)`
   → `2026-07-21 → merged 2026-07-24`, using
   `git log -1 --format=%cs <sha>` on the merging commit for the merge date)
   and update the same PR's status line in its report file under `prs/` the
   same way — `**Status:**` in English reports, `**Статус:**` in older Russian
   ones (write the new value in English either way), and set the report's
   frontmatter `status:` property to `merged` (if the file has frontmatter;
   leave other properties alone). Don't touch reports for PR numbers outside this
   commit range, and don't re-run the full `review-and-comment-pr` review — this is a
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
6. **Update the affected files.** Keep each file's existing style and structure.
7. **Update README.** Move the pin to the new `origin/main` HEAD, update the
   date, prepend an entry to the update log (the `## Update log`
   section at the very bottom of the file — keep the full log, don't trim
   old entries):
   `<date> · <old pin> → <new pin> (N commits, PR #x–#y): substance; version bumps`
   (same format as the existing entries — `→`, an en dash in PR ranges).
   If nothing substantive changed, still move the pin and log
   "no substantive changes".
8. **Report.** Summarize to the user what landed on main, which KB files
   were updated, and which PR-report statuses were refreshed.
