---
type: pr-report
date: 2026-09-01
status: merged
pr: [1245]
author: andypf
branch: andypf/refactor-compute-components-1244
---
# PR #1245: refactor(aurora): move compute components to their feature directories

**Author:** andypf · **Status:** merged 2026-09-01 (created 2026-09-01)
**Branches:** `andypf/refactor-compute-components-1244` → `main` · **Files:** 80 (+37/-810)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1245

> Closes #1244.

## What was done

A purely structural refactoring with no behavior change: the `Flavors`/`Images` components move from the shared folder `compute/-components/` into subfolders of the feature routes themselves — `compute/flavors/-components/` and `compute/images/-components/` respectively (63 files; git correctly recognized them as renames with history preserved, similarity 98-100%). The motivation is colocation: the components now sit next to the route files that use them (`flavors/index.tsx`, `flavors/$flavorId.tsx`, `images/index.tsx`, `images/$imageId.tsx`), rather than in a separate tree one level up. Along the way, three completely unused directories were deleted: `compute/-components/Instances/`, `compute/-components/KeyPairs/`, `compute/-components/ServerGroups/` (9 files, a pure deletion, not a move) — see "Review" regarding whether this code was really dead.

Remaining in place (not Flavors/Images-specific): `compute/-components/ActivitySummary.tsx`, `compute/-components/Overview.tsx`.

## How it is implemented

The move was done consistently: all relative imports inside the moved files were recalculated for the new nesting depth. Example:

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ImageListView.tsx
// was (one level deeper): "../../../-constants/filters"
import { IMAGE_STATUSES } from "../../-constants/filters"
```
The old path `compute/-components/Images/-components/ImageListView.tsx` was 4 levels below `compute/`, the new `compute/images/-components/ImageListView.tsx` is 3; `../../../` → `../../` correctly points to the same `compute/-constants/filters` in both cases — checked for all files with a non-empty diff (not only for those renamed without changes).

The route files (`flavors/index.tsx`, `flavors/$flavorId.tsx`, `images/index.tsx`, `images/$imageId.tsx`) updated their imports from the package-absolute `../-components/Flavors/...`/`../-components/Images/...` to local `./-components/...` — also correct; the components are now literally in their own `-components/` subfolder (in line with the CLAUDE.md convention: the `-` prefix excludes a folder from route generation).

## What it affects

Internal use only — none of the moved/deleted files has consumers outside `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/`. Checked:
- No remaining references to the old paths (`compute/-components/Flavors`, `compute/-components/Images`) are left in the codebase at the head commit.
- `routeTree.gen.ts` is not part of the diff — as expected, since the route paths themselves (`/compute/flavors`, `/compute/images/$imageId` etc.) have not changed; only the `-` folders, which are excluded from route generation, were moved.
- The deleted `Instances`/`KeyPairs`/`ServerGroups` were already orphan code before this PR: neither in the base commit (before the PR) nor in the current one is there any `compute/instances`/`compute/keypairs`/`compute/servergroups` route file, and no other file imported their `List.tsx`/`-components/*` — these three directories have been unused since at least PR #1222 (the last commit to touch these files, three weeks ago); they simply had not been deleted until now.
- The strings removed from the `de`/`en` `messages.po` (57 in each: "CPU", "Fingerprint", "Group Name", "IPv4"/"IPv6", "Key Name", "Loading Instances...", "Members", "Policy", "Restart", "Server Name", "Type", "View Details", etc.) all belonged to the deleted components; for each one it was checked that after the PR no `` t`...` `` / `<Trans>` with exactly the same source text occurs anywhere else in the codebase, i.e. `pnpm check-i18n` worked correctly and did not touch anything that is still in use.

## Review

No issues found with confidence ≥80. The places where such a move usually breaks were checked separately:
- The arithmetic of relative imports (`../../../` → `../../` etc.) in all files with a non-empty diff — it matches the new nesting depth.
- Completeness of the import updates — no remaining references to the old paths `compute/-components/Flavors|Images` were found in the repository.
- The actual "deadness" of the deleted `Instances`/`KeyPairs`/`ServerGroups` — confirmed by the absence of consumers in both the base and the head commit (not merely "the PR deletes what it itself stops using").
- The i18n catalogs — the removed strings have no remaining consumers in the code.

---
Analyzed: 2026-09-01 · commit `26bd222e`
