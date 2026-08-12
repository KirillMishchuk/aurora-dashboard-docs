# Plan: Ceph bucket list — gate the row-level "Empty" action + align row action naming (Issues #1107, #1109)

**Date:** 2026-08-12 · **Status:** not implemented

## 📋 IMPLEMENTATION PLAN: Ceph Bucket List Row Actions — Empty-state Gating & Naming Consistency

### Overview

Two linked bugs in the Ceph bucket **list** page's per-row action menu (`BucketTableView.tsx`):

- **#1107** — the row menu's "Empty" item is shown even when the bucket is already empty, unlike the bucket **detail** page, which hides its equivalent "Empty Bucket" item when the bucket has no current content.
- **#1109** — the row menu's items read "Empty" / "Delete" (no object noun), while the bulk-actions toolbar on the same page ("Empty Bucket" / "Empty Buckets") and the detail page's header menu ("Empty Bucket" / "Delete Bucket") always include the noun. Per user decision, this plan fixes **both** row labels ("Empty" → "Empty Bucket", "Delete" → "Delete Bucket"), not just "Empty".

Both fixes touch the same three `PopupMenuItem`s in the same file and are implemented together in one pass.

### Architecture Analysis

**Current state:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketTableView.tsx` (list page, per-row `PopupMenu`, ~line 233–252): renders `Show Details` / `Empty` / `Delete` unconditionally for every row, using `PopupMenuItem label={t\`Empty\`}` and `label={t\`Delete\`}`. No emptiness check exists here at all today.
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.tsx` (detail page header menu, ~line 44): already does the right thing — `{!isBucketEmpty && <PopupMenuItem label={t\`Empty Bucket\`} .../>}`. `isBucketEmpty` there comes from `useBucketInfo` → `calculateBucketState` (`bucketStateHelpers.ts`), which cross-references `bucket.count` **and** a live, version-aware `objects.list` call (`showVersions: true`) plus `versioning.getStatus` — 3 extra queries, deliberately paid for on the single-bucket detail page.
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeader.tsx` / `index.tsx` (bulk toolbar, "Zone 3"): already uses full-noun, pluralized labels ("Empty Bucket" / "Empty Buckets") via `i18n._(plural(...))`. Not part of this fix — used only as the naming reference.
- `EmptyBucketModal.tsx` (opened by the row's "Empty" click) does its **own** accurate, real-time emptiness/versioning check (`versioning.getStatus` + `objects.list` + `calculateBucketState`) every time it opens, regardless of what gated its visibility. This means the row-menu gate is a pure UI affordance/menu-declutter decision, **not** a correctness-critical safety gate — the mutation path is already protected independently of this change.
- Server-side, `bucket.count`/`bucket.bytes` (consumed by the list page) come from `containerRouter.ts`'s `list` procedure with `includeMetadata: true`: a direct `ListObjectsV2Command` (not version-aware) per bucket, `count = KeyCount`. Per S3/RGW semantics, a plain `ListObjectsV2` already excludes keys whose current version is a delete marker, so for a versioned bucket with only delete markers/old versions, `count` correctly reads 0 — same as `isBucketEmpty` would conclude on the detail page (that "has old versions/delete markers but no current objects" case is exposed there via a *separate* "Delete Versions" menu item, which the row menu doesn't have and isn't in scope here). The only documented caveat in the code is the 1000-key cap for very large buckets (undercounts, doesn't produce a false zero).
- The list page's `containers.list` query (`index.tsx`) has no explicit `staleTime`, so it refetches on mount/focus — further shrinking the already-small race window (an object uploaded a moment before the row renders).

**Proposed changes:**

- Add a lightweight, no-extra-query emptiness check local to `BucketTableView.tsx`: a bucket row has no content when `bucket.count === 0 && bucket.bytes === 0` (using metadata already fetched for the table — no new tRPC calls, no per-row `useBucketInfo`). Use it to conditionally render the row's "Empty Bucket" item, mirroring the detail page's `{!isBucketEmpty && ...}` pattern.
- Rename the row's `Empty`/`Delete` labels to `Empty Bucket`/`Delete Bucket`. Both message IDs already exist in `packages/aurora/src/locales/{en,de}/messages.po` (used today by `BucketHeaderActions.tsx`), so this reuses existing i18n keys — no new strings to translate, and no existing usage of the bare `Empty`/`Delete` keys goes orphaned (both remain heavily used elsewhere: `Swift/Containers/ContainerTableView.tsx`, `Ceph/Objects/ObjectsTableView.tsx`, `SecurityGroupTableRow.tsx`, several compute/image components, etc.).
- Keep `data-testid` values (`empty-action-${bucket.name}`, `delete-action-${bucket.name}`) unchanged — no consumer (tests, e2e) should need id updates.

### Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Race: bucket just gained content but `count`/`bytes` in the cached list response haven't caught up yet, so "Empty Bucket" is hidden for a moment on a non-empty bucket | Low | List query has no `staleTime` (refetches on mount/focus); `EmptyBucketModal` isn't a safety gate anyway — user can still act from the bucket detail page, which does the full accurate check; add a short code comment documenting the trade-off (mirrors the existing caveat comment in `bucketStateHelpers.ts`) |
| Renaming `Empty`→`Empty Bucket` / `Delete`→`Delete Bucket` looks like new copy needing translation | Low | Confirmed both `msgid`s already exist in `en`/`de` `messages.po` (reused from `BucketHeaderActions.tsx`); `pnpm check-i18n` should produce no new/removed entries — run it as a sanity check, not because new strings are expected |
| Existing tests assert on the old labels/behavior and break | Medium | Grepped `BucketTableView.test.tsx`: no existing test asserts the literal text "Empty"/"Delete" or exercises the row popup's contents (current test only checks rows exist, explicitly noting "PopupMenu items are hidden until menu is opened"); no e2e specs under `apps/dashboard/e2e` reference `empty-action`/`delete-action` or the bare strings. Add new coverage per the Testing Plan below rather than relying on absence of breakage |
| Scope creep vs. issue text | Low | User explicitly confirmed extending #1109's fix to "Delete" → "Delete Bucket" in addition to "Empty" → "Empty Bucket", to fully match the noun rule the issue argues for |

**Informational, out of scope:** the identical "Empty"/"Delete" (no-noun) pattern exists in the analogous Swift container list row menu (`Swift/Containers/ContainerTableView.tsx`, ~line 274/279). Both filed issues are explicitly labeled `[Bug](ceph)`/`(Ceph)`, so this plan does not touch Swift. Worth a follow-up issue if the same consistency is wanted there — flagged in Open Questions.

### Prerequisites

- [ ] None — no schema/API changes, no new dependencies. Pure client-side UI change in one file (plus its test file).

### Implementation Steps

#### Step 1: Gate the row-level "Empty Bucket" action on emptiness, and rename both row labels

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketTableView.tsx` — the per-row `PopupMenu` block inside the virtualized row map (currently ~lines 233–252)

**What to do:**

1. Inside the `virtualItems.map((virtualRow) => { ... })` callback, right after `const bucket = buckets[virtualRow.index]`, add:
   ```ts
   // Row-level "Empty Bucket" affordance is hidden once the bucket has no content,
   // mirroring the detail page's `!isBucketEmpty` gate (BucketHeaderActions.tsx).
   // Deliberately uses the lightweight list metadata already fetched for this table
   // (no extra per-row query) rather than the detail page's full version-aware
   // useBucketInfo/calculateBucketState check — EmptyBucketModal re-validates
   // emptiness/versioning accurately itself when opened, so this is a menu-declutter
   // decision, not a safety gate. See bucketStateHelpers.ts for the fuller check.
   const bucketHasNoContent = bucket.count === 0 && bucket.bytes === 0
   ```
2. Change the "Empty" `PopupMenuItem` to:
   ```tsx
   {!bucketHasNoContent && (
     <PopupMenuItem
       label={t`Empty Bucket`}
       onClick={() => setEmptyModalBucket(bucket)}
       data-testid={`empty-action-${bucket.name}`}
     />
   )}
   ```
3. Change the "Delete" `PopupMenuItem` label only (no gating change — deleting an already-empty bucket is intentionally always allowed):
   ```tsx
   <PopupMenuItem
     label={t`Delete Bucket`}
     onClick={() => setDeleteModalBucket(bucket)}
     data-testid={`delete-action-${bucket.name}`}
   />
   ```
4. Leave `Show Details` untouched.

**Expected outcome:**

- A bucket with `count === 0` and `bytes === 0` shows only "Show Details" and "Delete Bucket" in its row menu.
- A bucket with any content shows "Show Details", "Empty Bucket", and "Delete Bucket".
- Labels read "Empty Bucket" / "Delete Bucket" everywhere in this menu, matching the detail page and the bulk-actions toolbar.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora typecheck` and `pnpm --filter @cobaltcore-dev/aurora lint` pass.
- Manually load the Ceph buckets list with a mix of empty and non-empty buckets; open each row's `⋮` menu and confirm the item is present/absent and reads correctly.

---

#### Step 2: Add/extend test coverage in `BucketTableView.test.tsx`

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketTableView.test.tsx`

**What to do:**

1. To open a row's popup menu in tests, follow the established pattern used for this exact kind of bare `<PopupMenu>` (no explicit `PopupMenuToggle`) elsewhere in the repo — e.g. `SecurityGroupTableRow.test.tsx`: `within(row).getByRole("button", { name: /more/i })`, then `await user.click(...)`. `row` is `screen.getByTestId(\`bucket-row-${name}\`)` (already used in this file).
2. Add a test: given a bucket with `count: 0, bytes: 0`, open its row menu → `queryByTestId(\`empty-action-${name}\`)` is `null` (not rendered), `getByTestId(\`delete-action-${name}\`)` is present.
3. Add a test: given a bucket with `count: 5` (or `bytes > 0`), open its row menu → both `empty-action-${name}` and `delete-action-${name}` are present.
4. Add a test (or extend an existing one) asserting the visible label text is exactly `"Empty Bucket"` and `"Delete Bucket"` (not the old `"Empty"`/`"Delete"`) when opened.
5. Double-check the existing "renders PopupMenu for each bucket" test (~line 285) still passes unchanged (it only checks row existence, not menu contents) — no update expected there.

**Expected outcome:**

- Both bug fixes are covered by assertions that would fail on the old code.

**Verification:**

- `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/BucketTableView.test.tsx`

---

#### Step 3: i18n sanity check

**Files to modify:** none expected; this step only runs a generator and inspects the diff.

**What to do:**

1. Run `pnpm check-i18n` from the repo root.
2. Diff `packages/aurora/src/locales/en/messages.po` and `.../de/messages.po`. Expect **no** new or removed `msgid`s for `"Empty Bucket"` / `"Delete Bucket"` (already present) and no change to the still-used `"Empty"` / `"Delete"` entries (still referenced by Swift/Objects/SecurityGroups/etc.).

**Expected outcome:**

- Clean/empty diff on the locale files (or only unrelated pre-existing churn, if any).

**Verification:**

- `git diff --stat packages/aurora/src/locales` shows no unexpected changes before committing.

### Testing Plan

**Unit tests:**

- [ ] Row menu hides "Empty Bucket" when `count === 0 && bytes === 0`
- [ ] Row menu shows "Empty Bucket" when the bucket has any objects or bytes
- [ ] Row menu always shows "Delete Bucket" regardless of emptiness
- [ ] Row menu label text reads "Empty Bucket" / "Delete Bucket", not "Empty" / "Delete"
- [ ] `data-testid` values unchanged (`empty-action-${name}`, `delete-action-${name}`)

**Integration tests:**

- [ ] No existing `BucketTableView.test.tsx` or `index.test.tsx` test regresses (`pnpm --filter @cobaltcore-dev/aurora test`)

**Manual verification:**

1. Open the Ceph buckets list for a project with at least one empty and one non-empty bucket.
2. Open the `⋮` menu on the empty bucket's row → confirm only "Show Details" and "Delete Bucket" appear.
3. Open the `⋮` menu on the non-empty bucket's row → confirm "Show Details", "Empty Bucket", and "Delete Bucket" all appear.
4. Click "Empty Bucket" on the non-empty bucket → confirm `EmptyBucketModal` still opens and behaves as before (this flow is unchanged, only the trigger's visibility/label changed).
5. Compare wording against the detail page's `⋮` menu and the list page's bulk "Actions" menu — all three should now agree on "Empty Bucket"/"Delete Bucket" phrasing.

### Acceptance Criteria

- [ ] #1107: the row-level "Empty Bucket" action is not shown for a bucket with `count === 0 && bytes === 0`, matching detail-page behavior
- [ ] #1109: the row-level actions read "Empty Bucket" and "Delete Bucket", matching the bulk-actions toolbar and detail-page header menu
- [ ] No regressions to `EmptyBucketModal`/`DeleteBucketModal` behavior — only the row-menu trigger's visibility/label changed, not the modals themselves
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `pnpm --filter @cobaltcore-dev/aurora lint`, and `pnpm --filter @cobaltcore-dev/aurora test` pass
- [ ] `pnpm check-i18n` produces no unexpected locale-file diff

### Open Questions

- The same no-noun "Empty"/"Delete" pattern exists in the Swift container list row menu (`Swift/Containers/ContainerTableView.tsx`). Both GitHub issues are Ceph-specific — should a follow-up issue be filed for Swift, or is that intentionally out of scope for now?
- Confirmed with the user: extend #1109's fix to "Delete" → "Delete Bucket" as well as "Empty" → "Empty Bucket" (not a strictly-literal, Empty-only fix). Confirmed with the user: use the lightweight `bucket.count === 0 && bucket.bytes === 0` check for #1107 rather than reusing the detail page's full per-bucket `useBucketInfo` check, given `EmptyBucketModal` already re-validates accurately on open regardless of the row gate.
