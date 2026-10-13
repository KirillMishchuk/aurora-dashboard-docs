---
type: pr-report
date: 2026-08-13
status: merged
pr: [1172]
author: KirylSAP
branch: kiryl-ceph-cors-review-findings
---
# PR #1172: fix(aurora): apply design review fixes to bucket CORS rules UI

**Author:** KirylSAP · **Status:** merged 2026-08-14 (commit `0bfd055`; opened 2026-08-12)
**Branches:** `kiryl-ceph-cors-review-findings` → `main` · **Files:** 32 (+145/-390, of which 4 locale files: +26/-100)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1172

## What was done

The PR is the third round of polishing the CORS UI for Ceph/S3 buckets, which grew out of #1092 (adding the "CORS Rules" tab, merged 2026-08-12, 0 findings ≥80 in the final version of the report). Three commits:

1. `7ebafdc` — "design review fixes": renaming the create-rule action (`Add CORS Rule` → `Create CORS Rule`, everywhere — trigger, modal title, submit button), demoting the `Add` buttons in `TagInput` (they were `variant="primary"`, now `variant="default"`, so that the modal has a single primary button), completely removing the modal for deleting the bucket's entire CORS configuration (`DeleteCorsModal` + the "Delete CORS Rules" menu item in the bucket header), and switching `CorsRulesTable` to the default `DataGrid` column layout instead of an explicit `gridColumnTemplate`.
2. `cf8ec61` — aligning the CORS Rules tab toolbar spacing with the `FloatingIpsList` pattern (`Divider spacing="0"`, `pb-2` on zone 1).
3. `46e061e` — **goes beyond the stated topic**: renames generic action labels ("Delete", "Empty", "Upload") to object-specific ones ("Delete Object"/"Delete Folder"/"Delete Bucket"/"Delete Version(s)"/"Delete Objects"/"Delete All Versions", "Empty Bucket"/"Empty Buckets", "Upload Object") not only in the CORS components but in all Ceph Buckets and Objects components: `BucketTableView`, `DeleteObjectModal`, `DeleteObjectsModal`, `DeleteVersionModal`, `ObjectsTableView`, `UploadObjectModal`, `EmptyBucketsModal`. Along the way, `DeleteObjectsModal`/`DeleteVersionModal` gained singular/plural logic for the confirmation label (see "How it is implemented").

Plus `useBucketInfo.ts`: the CORS query stops being a data source for `BucketHeader` (the `corsData` field was removed from the hook's returned object) — it is now a pure prefetch that warms the shared React Query cache for consumers that make the same query themselves (`CorsRulesTab`, `CorsRuleModal`, `DeleteCorsRuleModal`). A natural consequence of removing `DeleteCorsModal`: the header menu item that opened it no longer needs to know whether there are CORS rules (`hasCors`), so that field was removed from `useBucketInfo`/`BucketHeader`/`BucketHeaderActions` entirely.

## How it is implemented

### Renaming the create-rule action

```tsx
// CorsRuleModal.tsx:150
title={editingRule ? t`Edit CORS Rule` : t`Create CORS Rule`}
```

Made consistent in all three places where there used to be a mismatch between "Add CORS Rule" (title/trigger) and "Create Rule" (submit button) — now it is `Create CORS Rule` everywhere.

### Removing the modal for deleting the entire CORS configuration

`DeleteCorsModal.tsx` was removed entirely (148 lines), together with the menu item that opened it and the related toast helpers:

```diff
// BucketHeaderActions.tsx:44-49 (before)
-          {hasCors && <PopupMenuItem label={t`Delete CORS Rules`} onClick={() => onOpenModal("deleteCors")} />}
```

This closes the story that began in #1092: there were already two instances of `DeleteCorsModal` there — a working one, from the header menu (variant "a" in the #1092 report), and an unreachable dead one (variant "b", inside `CorsRulesTab`, where `setIsDeleteModalOpen(true)` was never called). Round 4 in #1092 removed only the dead instance. This PR goes further and removes the working path itself entirely, leaving CORS deletion only at the level of individual rules (`DeleteCorsRuleModal`) and a selected group (`DeleteCorsRulesModal`) — these two were renamed to `Delete CORS Rule`/`Delete CORS Rules` for consistency with the new `Create CORS Rule`, but were not removed and did not lose functionality:

```tsx
// DeleteCorsRuleModal.tsx:164
confirmButtonLabel={t`Delete CORS Rule`}
```

The changeset explicitly documents this as a deliberate decision: *"drop the redundant bucket-header "Delete CORS Rules" entry (per-rule and batch delete are unchanged)"* — it matches the code.

### Naming actions after their target object (commit `46e061e`)

The same pattern repeats across six Buckets/Objects files — the button/menu item label and the confirmation label used to be a generic word ("Delete", "Empty", "Upload"); now they name the object of the action:

```tsx
// DeleteObjectsModal.tsx:202-211 (new)
  const confirmLabel = isPending
    ? t`Deleting...`
    : isVersionMode
      ? count === 1
        ? t`Delete Version`
        : t`Delete Versions`
      : count === 1
        ? t`Delete Object`
        : t`Delete Objects`
```

```tsx
// ObjectsTableView.tsx:1001-1030 (three places, all were t`Delete`)
  <PopupMenuItem label={t`Delete Folder`} .../>   // folder with a delete marker
  <PopupMenuItem label={t`Delete Folder`} .../>   // regular folder
  <PopupMenuItem label={t`Delete Object`} .../>   // version/object
```

`DeleteVersionModal.tsx:126` already had the branch `isDeletingAllVersions ? t\`Delete All Versions\` : ...` for the modal title (inherited from existing code, not new in this PR) — the commit simply carried the same branch over to `confirmButtonLabel`, which was previously hardcoded as `t\`Delete\`` and did not match the title:

```tsx
// DeleteVersionModal.tsx:126 (new)
confirmButtonLabel={isDeletingAllVersions ? t`Delete All Versions` : t`Delete Version`}
```

`BucketTableView.tsx:130-137`, `EmptyBucketsModal.tsx:97` (`Empty` → `Empty Bucket`/`Empty Buckets` depending on the count), `UploadObjectModal.tsx:194` (`Upload` → `Upload Object`) — the same pattern, without branching on the count where the action is always singular.

A side but useful fix in the same commit — `TagInput.tsx:88-95`: the `Add` button used to be a hardcoded string without a Lingui wrapper:

```diff
-        <Button variant="primary" onClick={...}>
-          Add
-        </Button>
+        <Button variant="default" onClick={...}>
+          <Trans>Add</Trans>
+        </Button>
```

This closes an observation from the #1092 report (*"The [TagInput] component has not a single string passed through Lingui (the "Add" button...)"*, scored at 75/100, did not pass the threshold) — the string is now localized. `variant="default"` is the same change described in the changeset ("demote the tag-input "Add" buttons so the modal has a single primary action").

### `useBucketInfo`: the CORS query becomes a pure prefetch

```diff
// useBucketInfo.ts:88-95
-  // Query CORS configuration
-  const { data: corsData, isLoading: isLoadingCors } = trpcReact.storage.ceph.cors.get.useQuery(
+  // Prefetch only: warms the shared cors.get cache consumed by CorsRulesTab (5 min staleTime).
+  const { isLoading: isLoadingCors } = trpcReact.storage.ceph.cors.get.useQuery(
     {
       project_id: projectId ?? "",
       bucketName: bucketName,
     },
```

The query parameters (`project_id`, `bucketName`, `staleTime: 5 * 60 * 1000`, `retry: false`) did not change — it is the same query key that `CorsRulesTab`/`CorsRuleModal`/`DeleteCorsRuleModal` use in their own `cors.get.useQuery` calls, so React Query keeps sharing a single cache entry between the hook and the tab; the warming behavior is not broken, the only thing that changed is that `useBucketInfo` no longer *reads* this data for its own needs.

### `CorsRulesTable`: switching to the default column layout

```diff
-  const gridColumnTemplate =
-    "40px minmax(100px, 1fr) minmax(150px, 2fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(80px, 1fr) 60px"
-  ...
-  <DataGrid columns={8} gridColumnTemplate={gridColumnTemplate} className="cors-rules-table">
+  <DataGrid columns={8}>
```

This matches the changeset's explicitly stated goal ("use the default DataGrid column layout") — the visual comparison of the layouts itself cannot be verified from the code (it requires rendering the `juno-ui-components` component), but the change is intentional and documented, not an accidental loss of styling.

## What it affects

A search across the whole repository at the branch head (`git grep -n '<symbol>' pr-1172 -- '*.ts' '*.tsx'`) for each removed export:

- **`corsData`/`hasCors` (removed from the return value of `useBucketInfo`)** — the only remaining mentions of `corsData` in the repository are local variables in `CorsRuleModal.tsx`, `CorsRulesTab.tsx`, `DeleteCorsRuleModal.tsx`, each from its own `cors.get.useQuery` call, unrelated to the hook. `hasCors` does not appear at all. The cleanup is clean; no external consumers remain.
- **`DeleteCorsModal`, `getCorsDeletedToast`, `getCorsDeleteErrorToast`** — zero matches in the rest of the repository; the removal is complete, with no orphaned imports.
- **`gridColumnTemplate` in `CorsRulesTable`** — used in other tables (`BucketTableView`, `ObjectsTableView`, `EditMetadataModal`) with their own, unrelated values; the change to `CorsRulesTable` does not affect them.

The change is entirely within `packages/aurora`; no public contract exported from the package (types, tRPC procedures) is touched — it is purely the UI layer (labels, markup, local state). The changeset is correctly marked `patch`.

**An important discrepancy with the PR description.** The PR title and text (*"apply design review fixes to bucket CORS rules UI"*) and the changeset text describe the change as pertaining to the CORS UI. In fact, commit `46e061e` renames action labels in six files, of which only `BucketHeaderActions`/`CorsRulesTable` relate to CORS — the rest (`DeleteObjectModal`, `DeleteObjectsModal`, `DeleteVersionModal`, `ObjectsTableView`, `UploadObjectModal`, `EmptyBucketsModal`, `BucketTableView`) relate to ordinary Ceph buckets and objects and have nothing to do with CORS. The changeset (`.changeset/cors-design-fixes.md`) also does not mention this part of the change at all — it describes only the CORS-specific items. The change itself (naming actions after their target object instead of a generic "Delete"/"Empty"/"Upload") is clearly sensible and useful; the only question is the accuracy of the scope description. See "Review".

## Review

**1 finding ≥80:**

- **[85] The PR description and changeset do not reflect the actual scope of the change.** Both the PR title/body and `.changeset/cors-design-fixes.md` frame the change as CORS UI fixes ("CORS rules UI", "Ceph/S3 bucket CORS management"). Meanwhile, commit `46e061e` ("name ceph storage actions after their target object") renames action labels in `BucketTableView.tsx`, `DeleteObjectModal.tsx`, `DeleteObjectsModal.tsx`, `DeleteVersionModal.tsx`, `ObjectsTableView.tsx`, `UploadObjectModal.tsx`, `EmptyBucketsModal.tsx` — in all Ceph Buckets/Objects components, not just the CORS components. This is exactly the case where the PR description, as a source for understanding the scope of the change, is misleading: someone who reads only the title/changeset (for example, when preparing a release or assessing whether their own PR conflicts with this branch) will not learn that `Delete`/`Empty`/`Upload` are affected in all object and bucket modals. Verified directly against the diff and the changeset file — not a single line in `.changeset/cors-design-fixes.md` mentions objects/the Buckets table/file upload.

Did not reach the threshold (mentioned in the description above as an observation, not a finding): the visual correctness of switching `CorsRulesTable` to the default `DataGrid` column layout cannot be confirmed or refuted from the code alone — the change is explicitly stated in the changeset as intentional, and does not look like an accidental loss of styling.

---
Analyzed: 2026-08-13 · commit `127847c`
