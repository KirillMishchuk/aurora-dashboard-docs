---
type: pr-report
date: 2026-09-02
status: merged
pr: [1247]
author: andypf
branch: andypf/refactor-edit-spec-modal
---
# PR #1247: feat(aurora): refactor EditSpecModal to match EditImageMetadataModal design

**Author:** andypf · **Status:** created 2026-09-01 → merged 2026-09-02
**Branches:** `andypf/refactor-edit-spec-modal` → `main` · **Files:** 11 (+980/-868)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1247

## What was done

The PR reworks two modals on the Flavor detail page — `EditSpecModal` (editing a flavor's extra specs) and `ManageAccessModal` (access of private flavors to projects) — to match the design already adopted in `EditImageMetadataModal` (Images). Previously `EditSpecModal` was built on `use()`+`Suspense`+`ErrorBoundary`, with separate `SpecFormRow`/`SpecRow` components and per-item mutations (each spec add/delete was its own immediate API call with a "successfully added/deleted" toast); `ManageAccessModal` was built similarly, with separate `TenantAccessFormRow`/`TenantAccessRow` and delete confirmation via click-and-wait-3-seconds in `TenantAccessRow`. Both components are fully rewritten to a "local draft + batch save" pattern: all edits (adding/renaming/changing a value/deleting rows) accumulate in local state, the actual tRPC mutations are sent in one go only when the `Save Changes` button in the `Modal` footer is pressed, and `Cancel`/the X button discard the draft. `TenantAccessFormRow.tsx` and `TenantAccessRow.tsx` are deleted as files in the process — their role was absorbed by `ManageAccessModal.tsx` directly. An accompanying changeset (`patch`) and en/de localization edits (new and removed strings for the new "Property"/"Project" wording instead of "Metadata"/"Tenant").

## How it is implemented

**Batch data model** — each modal has its own parallel set of state: a draft list (`specs`/`access`), an `isNew` flag for rows not yet saved on the backend, and `originalKey`/`originalValue`/`originalProjectId` to track what exactly changed relative to `initialSpecs`/`initialAccess` (`EditSpecModal.tsx:27-45`, `ManageAccessModal.tsx:26-43`).

**`EditSpecModal` batch save** (`EditSpecModal.tsx:192-243`) — on `handleSubmit`, the diff between `specs` and `initialSpecs` yields the keys to delete (deleted rows plus the old keys of renamed ones) and an object to create/update, after which the bracketing calls are executed sequentially:

```tsx
// EditSpecModal.tsx:219-235
// Delete removed/renamed specs
for (const key of new Set(keysToDelete)) {
  await client.compute.deleteExtraSpec.mutate({
    project_id: project,
    flavorId: flavor.id,
    key,
  })
}

// Create/update specs
if (Object.keys(specsToSave).length > 0) {
  await client.compute.createExtraSpecs.mutate({
    project_id: project,
    flavorId: flavor.id,
    extra_specs: specsToSave,
  })
}
```

Deleting a specific row in the UI is instant, without any confirmation (`EditSpecModal.tsx:165-168`):

```tsx
// EditSpecModal.tsx:165-168
const handleDelete = (index: number) => {
  setSpecs(specs.filter((_, i) => i !== index))
  setErrors({})
}
```

**`ManageAccessModal` batch save** mirrors the same scheme without renames — only add/remove (`ManageAccessModal.tsx:135-176`):

```tsx
// ManageAccessModal.tsx:152-168
// Remove projects
for (const targetProjectId of projectsToRemove) {
  await client.compute.removeTenantAccess.mutate({ project_id: project, flavorId: flavor.id, targetProjectId })
}

// Add projects
for (const targetProjectId of projectsToAdd) {
  await client.compute.addTenantAccess.mutate({ project_id: project, flavorId: flavor.id, targetProjectId })
}
```

**The Save Changes button is disabled** while there are no changes/a row is being edited/added — `disableConfirmButton={isSubmitDisabled}` in both modals, where `isSubmitDisabled` accounts for `isAddingNew` and (only in `EditSpecModal`) `specs.some(e => e.isEditing)` (`EditSpecModal.tsx:96`, `ManageAccessModal.tsx:98`) — this genuinely prevents losing an unsaved inline edit by silently closing via the confirm button.

**The DescriptionList layout** reproduces `EditImageMetadataModal`: column headers `Property Key`/`Value` (`EditSpecModal.tsx:295-297`); in `ManageAccessModal` — a fixed `Project` label with an editable `TextInput` only for the new row, while existing entries are plain `<span>` with no inline editing (`ManageAccessModal.tsx:283-308`), which matches the PR description's "editable Project ID value" as "adding" rather than "editing existing ones".

## What it affects

`EditSpecModal`/`ManageAccessModal` (Flavors) are used in exactly two places, both part of the same Flavor page:

- `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/$flavorId.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/FlavorListContainer.tsx`

Both consumers pass the same set of props as before (`client`, `isOpen`, `onClose`, `project`, `flavor`, `canEdit` for `EditSpecModal`) — the component contract has not changed, and the `patch` changeset is justified. `TenantAccessFormRow`/`TenantAccessRow` had no consumers outside the deleted `ManageAccessModal.tsx`. The `ManageAccessModal`/`manageAccessModal` matches in `ImageListView.tsx` and `ContainerTableView.test.tsx` are local identifiers of an unrelated Swift/Images modal, not imports of the deleted/changed component; there is no real external use outside the Flavor page.

## Review

Checked compliance with CLAUDE.md (tests colocated as `*.test.tsx`, the `-components` convention is not violated, a changeset is added and labeled correctly), matched the `en`/`de` locale diffs against the `` t`...` `` strings actually used in the code (all new strings are in place; removed strings come from logic that was removed entirely together with the per-item toasts; no "orphaned" keys found), checked the `git log --follow` history for both files and the delta relative to the version on `origin/main`. Separately cross-checked against the review comments already posted on this PR by the Copilot bot (`api.github.com/repos/.../pulls/1247/comments`) — some of them (JSON.stringify in a React key, missing `translateError` for `loadError`, missing `errortext` on the value field during inline editing, duplicates in `keysToDelete`) were **not confirmed** on direct inspection of the current head — the corresponding code already uses `key={flavor.id}`, `translateError(loadError)`, `errortext={errors[...]}` on both fields and deduplicates `keysToDelete` via `new Set(...)` before the delete loop — i.e. these comments are outdated (they relate to an earlier push to this same PR) and are not included in the report. Two findings are independently confirmed both by the Copilot bot on this same PR and by direct inspection of the code/history:

1. **The "confirm-delete pattern with 3-second timeout" for `EditSpecModal` announced in the PR body and changeset is absent from the code** (confidence 95) — `EditSpecModal.tsx:165-168`. Both the PR description ("Add confirm-delete pattern with 3-second timeout") and the changeset itself `.changeset/refactor-flavor-modals.md:9` literally promise this pattern for `EditSpecModal`. In fact `handleDelete` removes the row from local state with a single click, without any confirmation and without `setTimeout`/`confirm` state — neither in `EditSpecModal.tsx` nor in `EditSpecModal.test.tsx` (checked with grep for `timeout|confirm|3000|setTimeout` — no matches in a deletion context, only `Modal` props). Checking the history showed that this pattern (`useState` + `setTimeout(..., 3000)` + a two-phase button) did actually exist in this PR — but in the **deleted** `TenantAccessRow.tsx` (`origin/main`, `TenantAccessRow.tsx:19-59`), which belonged to `ManageAccessModal`, not `EditSpecModal`; and it was legitimately removed there according to another item of the same changeset ("Remove confirm-delete pattern \[from ManageAccessModal\] (unnecessary with batch save)"). Apparently, when writing the description/changeset, the wording for `ManageAccessModal` was mistakenly duplicated as an "addition" for `EditSpecModal`, even though that modal had no such pattern either before or after the PR (the pre-PR version of `EditSpecModal.tsx` on `origin/main` also has no mention of `timeout`/`confirm`). Independently confirmed by the same Copilot comment on this PR (path `EditSpecModal.tsx`, line 414: "The PR description / changeset claims a confirm-delete pattern with a 3-second timeout for EditSpecModal, but spec deletion here happens immediately"), still relevant for the current head.
2. **The batch save in both modals first deletes/revokes, then creates/adds — a failure in the second step after the first succeeds leads to real data loss, not just an error in the UI** (confidence 85) — `EditSpecModal.tsx:219-235` (the `deleteExtraSpec` delete loop before the `createExtraSpecs` create call) and symmetrically `ManageAccessModal.tsx:152-168` (the `removeTenantAccess` remove loop before the `addTenantAccess` add loop). If after a successful delete/revoke some calls go through and the subsequent create/add fails (network failure, key conflict, server limit — e.g. for extra specs this same codebase already has a localization string "Metadata size exceeds the 2KB limit..." for exactly this scenario of exceeding the limit during a batch edit), the `catch` in `handleSubmit` merely shows `saveError` and keeps the modal open — but the keys/access entries deleted on the backend are already gone, and the new/replacement ones were never created: meanwhile `specs`/`access` in local state are not rolled back to their pre-submit form and do not match the actual server state. Moreover, clicking "Save Changes" again recomputes the diff from the same stale `initialSpecs`/`initialAccess` (data is not refetched after the error), i.e. it will try to delete/revoke a key/access entry that no longer exists on the server a second time. For `ManageAccessModal` this means the user can unintentionally **revoke flavor access from some projects** without ever granting it to the new one, while the modal looks as if "nothing was committed". Independently confirmed by the Copilot bot on this same PR with separate comments for each file (`EditSpecModal.tsx:235` — "users can lose metadata even though the modal stays open with an error"; `ManageAccessModal.tsx:168` — "the user can end up unintentionally revoking access (partial update)"), still relevant for the current head.

Below the threshold (not reported): the hypothesis that edits are lost when the modal is closed via the X button/`Cancel` while `handleSubmit` is in progress (both modals do not pass `disableCancelButton`/`disableCloseButton` during `isSaving`, unlike 14+ delete modals in this same repository, which do) — direct inspection of the reference `EditImageMetadataModal`, which this PR is explicitly meant to copy design-wise, revealed that the reference itself **also** does not block Cancel/the X button during saving; i.e. this is not a deviation from the pattern this PR was meant to copy, but a property of the copied pattern itself — scored 40/100, not reported.

---
Analyzed: 2026-09-02 · commit `6d7db860` (head, PR open/unmerged)
