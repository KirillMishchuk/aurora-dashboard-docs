# PR #1398: fix(deps): restore @fastify/static override to patch route/auth bypass

Author: andypf · State: open · https://github.com/cobaltcore-dev/aurora-dashboard/pull/1398
Code: `origin/pr/1398` (head `8e6df7b2`) — read it with `git show origin/pr/1398:<path>` and `git diff origin/main...origin/pr/1398`, not from the working tree.

## Description

## Summary

Restores the `@fastify/static@<10.1.2` pnpm override that was dropped as "redundant" in #1396. It was **not** redundant: `@fastify/vite` pulls in `@fastify/static@9.3.0`, which is affected by two advisories. Dropping the override reopened Dependabot alerts **#152** and **#153**.

| Alert | Advisory | Affected | Fix |
|---|---|---|---|
| #152 (high) | route guard bypass via non-leading `..` / `%2E%2E` | `<=10.1.0` | `10.1.2` |
| #153 (moderate) | authorization bypass via non-canonical URL paths | `<=10.1.1` | `10.1.2` |

`@fastify/static@9.3.0` falls under both ranges. These are **dev-dependency** (`@fastify/vite`) vulnerabilities, which is why `pnpm audit --prod` did not surface them.

## Changes
- `pnpm-workspace.yaml`: re-add `@fastify/static@<10.1.2: ^10.1.2` override.
- `pnpm-lock.yaml`: `@fastify/static` now resolves to `10.1.2` only (the vulnerable `9.3.0` is gone).
- Added changeset (`@cobaltcore-dev/aurora`: patch).

## Verification
- `pnpm audit --prod` -> No known vulnerabilities found
- No `@fastify/static@9.x` left in the lockfile
- `pnpm typecheck` + `pnpm test` pass
- Note: `@fastify/static@10.1.2` (published 2026-07-22) is well outside the 7-day `minimumReleaseAge` window, so no exclude entry is needed.

## Conversation

### github-actions[bot] · 2026-10-27

🚀 **Preview deployed!**
👉 [PR #1398](https://pr-1398.aurora-previews.d.c.eu-nl-1.cloud.sap)

Commit: `8e6df7b25542a860334dc773b70252c00482b461`

### github-actions[bot] · 2026-10-27

🚀 **Preview deployed!**
👉 [PR #1398](https://pr-1398.aurora-previews.d.c.eu-nl-1.cloud.sap)

Commit: `8e6df7b25542a860334dc773b70252c00482b461`
