---
type: pr-report
date: 2026-09-08
status: merged
pr: [1263]
author: vlad-schur-external-sap
branch: vlad-floatingips-issues-before-go-live
---
# PR #1263: fix(network): issues to fix before Floating IPs Go-Live

**Author:** vlad-schur-external-sap · **Status:** merged 2026-09-08 (created 2026-09-03)
**Branches:** `vlad-floatingips-issues-before-go-live` → `main` · **Files:** 27 (+395/-282)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1263

## What was done

The PR closes a list of small but release-blocking issues in the Floating IPs feature (Epic #1201) before go-live. The changes do not add new functionality but fix the UX/behavior of existing screens: the floating IP details page, the allocate/attach/detach/release/edit modals and the floating IP list.

Three substantive behavior changes stand out against the rest of the (mostly cosmetic) edits:

1. **Shared error state between modals.** All four floating IP modals (edit, attach/associate, detach, release) use the same shared `useFloatingIpMutations()` hook with two mutations (`update`, `delete`). Previously, an error from one mutation could "leak" into another modal if the user closed one and opened another before the state was reset. Now `FloatingIpActionModals` wraps each `toggle*Modal` in a `toggle*ModalWithReset`, which resets `updateError`/`deleteError` right before opening/closing the modal.
2. **Creating a floating IP now leads to the details page instead of a toast notification.** After a successful creation, `AllocateFloatingIpModal` calls `navigate()` to the details route of the new resource instead of showing a toast — the corresponding helper `getFloatingIpAllocatedToast` is removed completely.
3. **Attach is now the only primary action** on the floating IP details page; the other actions (Edit Description, Detach, Release) are moved into a kebab dropdown menu.

Other edits: long descriptions are truncated via CSS `truncate` (in the table and in `TwoColumnDescriptionList`), the loading/error/not-found states are switched to the Juno `Status` component instead of home-made Stack+Spinner markup, toast notifications are added for all CRUD operations (except create — see item 2), the "Preview" action is renamed to "Show Details", the sort field in the list is reduced to a single option "Status" (instead of eight), and the Cancel/Close buttons are disabled while a mutation is pending.

## How it is implemented

### Details page: Attach as the primary action + Status for loading/error

`FloatingIpDetailsView.tsx:60-77` — instead of a `ButtonRow` with four equal buttons, there is now a `PopupMenu` with three items plus a separate primary Attach button:

```tsx
<Stack gap="0.5" alignment="center">
  <PopupMenu className="flex items-center">
    <PopupMenuToggle as="div">
      <Button icon="moreVert" title={t`Floating IP actions`} />
    </PopupMenuToggle>
    <PopupMenuOptions>
      <PopupMenuItem label={t`Edit Description`} onClick={toggleEditModal} />
      <PopupMenuItem label={t`Detach`} onClick={toggleDetachModal} />
      <PopupMenuItem label={t`Release`} onClick={toggleReleaseModal} />
    </PopupMenuOptions>
  </PopupMenu>
  <Button variant="primary" className="whitespace-nowrap" onClick={toggleAttachModal}>
    {t`Attach`}
  </Button>
</Stack>
```

`$floatingIpId/index.tsx:84-98` merges the previously separate `isError` and `!floatingIp` branches into one, using Juno `Status`:

```tsx
if (isError || !floatingIp) {
  const errorMessage = error?.message || t`Error loading floating IP`
  return (
    <Status
      status="error"
      title={isError ? errorMessage : t`Floating IP not found`}
      action={<Button onClick={handleBack} variant="primary"><Trans>Back to Floating IPs</Trans></Button>}
    />
  )
}
```

### Shared error reset between modals + navigation after Release

`FloatingIpActionModals.tsx:42-71` — the `useFloatingIpMutations` hook now also returns `resetUpdateError`/`resetDeleteError`, wrapped into four `toggle*WithReset` functions:

```tsx
const toggleEditModalWithReset = () => {
  resetUpdateError()
  toggleEditModal()
}
// ...likewise toggleAttachModalWithReset, toggleDetachModalWithReset (resetUpdateError)
// and toggleReleaseModalWithReset (resetDeleteError)
```

`useFloatingIpMutations.ts:74-75` simply passes the react-query mutation's own `.reset` through:

```ts
resetUpdateError: updateMutation.reset,
resetDeleteError: deleteMutation.reset,
```

Additionally, `FloatingIpActionModals.tsx:93-108` (`handleReleaseWithToast`) now checks via `useMatches()` whether the user is on the details page of the deleted floating IP, and if so, redirects to the list:

```tsx
const isOnDetailsPage = matches.some(
  (route) => route.routeId === "/_auth/projects/$projectId/network/floatingips/$floatingIpId/"
)
if (isOnDetailsPage) {
  navigate({ to: "/projects/$projectId/network/floatingips", params: { projectId } })
}
```

### Allocate: redirect instead of toast

`AllocateFloatingIpModal.tsx:108-113`:

```tsx
handleClose()
navigate({
  to: "/projects/$projectId/network/floatingips/$floatingIpId",
  params: { projectId, floatingIpId: created.id },
})
```

Previously `toast.success(...)` was called here via `getFloatingIpAllocatedToast` — the helper is removed entirely along with its tests; verified with `git grep` across the whole monorepo — no dangling references remain.

### Disabling Cancel/Close during pending mutations

Added uniformly in `AllocateFloatingIpModal.tsx:144-145`, `AssociateFloatingIpModal.tsx:82-83`, `EditFloatingIpModal.tsx:79-80`:

```tsx
disableCancelButton={isPending /* or isLoading */}
disableCloseButton={isPending /* or isLoading */}
```

### Truncating long values

`TwoColumnDescriptionList.tsx:24-28,33-39` — each value is now wrapped in `<div className="truncate">`:

```tsx
<DescriptionDefinition>
  <div className="truncate">{value}</div>
</DescriptionDefinition>
```

`FloatingIpTableRow.tsx:42-44` — the same for the Description column in the table:

```tsx
<DataGridCell>
  <div className="truncate">{floatingIp.description || "—"}</div>
</DataGridCell>
```

### Renaming Preview → Show Details

`FloatingIpTableRow.tsx:50` and the comment updated in sync in `constants.tsx:32`:
`"", // empty column for item-actions with context menu containing "Show Details", "Edit Description", "Attach", "Detach" and "Release"`.

### Sorting reduced to Status

`FloatingIpsList.tsx:18,47`:

```ts
const DEFAULT_SORT_KEY = "status"
// ...
options: [{ label: t`Status`, value: "status" }],
```

Previously there were 8 options (`fixed_ip_address`, `floating_ip_address`, `floating_network_id`, `id`, `router_id`, `status`, `tenant_id`, `project_id`) with `fixed_ip_address` as the default.

### Locales

`packages/aurora/src/locales/{de,en}/messages.po` and `messages.ts` — a purely mechanical regeneration by the lingui extractor, matching the string changes in the `.tsx` files 1:1 (checked against `git log` — the pattern matches how these files are usually touched in the repository history).

## What it affects

- **`TwoColumnDescriptionList` is a shared component**, used not only in floating IPs but also in `FlavorDetailsView.tsx`, `ImageDetailsView.tsx` and `SecurityGroupBasicInfo.tsx`. Adding `<div className="truncate">` around each `value` affects all three screens. In most cases `value` is a plain string, where `truncate` is harmless and even helpful. But in `FlavorDetailsView.tsx:16` and `ImageDetailsView.tsx:106,142` the `ID` field is passed as `<ClipboardText text={...} />` — a component with `inline-flex` markup (text + copy icon). Wrapping such a component in `overflow-hidden; white-space-nowrap` may clip the copy icon for long IDs on these (non-floating-IP) screens. There are no tests for this scenario (long ID + ClipboardText inside `TwoColumnDescriptionList`) in the diff.
- **`getFloatingIpAllocatedToast`** is removed completely — `git grep` across the whole monorepo at `150fe4ecbeed745c5a553ca710a65e11672f6d98` confirms there are no dangling references.
- **`useFloatingIpMutations`, `FloatingIpActionModals`, `FloatingIpActionModalTriggers`** — used only inside the `floatingips/` directory, no external consumers (verified with `git grep` across the monorepo).
- The PR branch is an un-squashed history of five commits (`7716e0e → 312cb6d → 55d2c2a → 54fc687 → 150fe4e`). In particular, commit `54fc687` ("fix(network): ai comments and missed changeset") already, within this same branch, changed `TwoColumnDescriptionList` from `<span className="truncate">` to `<div className="truncate">` — `truncate` does not work on an inline `span` without `display:block`. The final diff the reviewer sees on GitHub already contains the corrected version.

## Review

**Race on Release from the details page — risk of a brief/persistent "Floating IP not found" before the redirect** (confidence 80/100)

- `useFloatingIpMutations.ts:51-52`: the `onSettled` of `deleteMutation` calls `utils.network.floatingIp.getById.invalidate(...)` for the just-deleted id — unconditionally, without checking the current route.
- `FloatingIpActionModals.tsx:93-108`: `handleReleaseWithToast` calls `navigate()` away from the details page only *after* `await handleDelete(...)` (i.e. after `onSettled` has already run) and after showing the toast.

Since the details page (`$floatingIpId/index.tsx`) is still mounted at the moment `invalidate()` is called (navigation hasn't happened yet), react-query considers the `getById` query active and refetches it immediately — for a resource that no longer exists. This typically results in `isError=true` and rendering `Status status="error"` / "Floating IP not found" (`$floatingIpId/index.tsx:85-98`) before the asynchronous `navigate()` manages to unmount the component. The path is deterministic — it is the main "Release from the details page" scenario, not a rare edge case, so the user will see the effect (a flicker, and on a slow network a noticeable delay) on every release from this page.

A possible fix direction (not tested in practice): call `navigate()` right after a successful `handleDelete`, before/without invalidating `getById` for the deleted id; or use `removeQueries`/an explicit `setData(undefined)` instead of `invalidate` for this specific id; or explicitly skip the `getById` invalidation when the id being deleted matches the id of the currently open details route.

No other issues with confidence ≥80 were found. Separately checked and deemed correct: the `toggle*ModalWithReset` logic (an error reset never happens over an error the user still needs to see, since Cancel/Close are disabled while pending); the comment in `constants.tsx:32` matches the actual contents of the kebab menu; consistency with existing codebase conventions (the switch to `Status`, the "redirect instead of toast after create" pattern was already applied in `SecurityGroupsList.tsx`, the `disableCancelButton`/`disableCloseButton` pair is used in 15+ other modals); the change history of `TwoColumnDescriptionList` (the `truncate` edit is a deliberate fix within this same branch, not a regression of an earlier fix). In the repository at the current point (`150fe4ecbeed745c5a553ca710a65e11672f6d98`) no tracked file [`CLAUDE.md`](../../CLAUDE.md) was found, even though the workspace note (`SAP/CLAUDE.md`) refers to `aurora-dashboard/CLAUDE.md` — it's worth checking with the user whether the file was accidentally deleted or renamed.

---
Analyzed: 2026-09-08 · commit `150fe4e`
