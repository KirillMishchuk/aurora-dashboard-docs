---
type: pr-report
date: 2026-09-16
status: merged
pr: [1303]
author: TilmanHaupt
branch: til-flav-edit-fix
---
# PR #1303: fix(portal): fix images and flavor

**Author:** TilmanHaupt · **Status:** merged 2026-09-16 (created 2026-09-15)
**Branches:** `til-flav-edit-fix` → `main` · **Files:** 14 (+133/-152)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1303

## What was done

The PR fixes the UX of two metadata modals (Images/Flavors) and of the popup menus in Compute (Images, Flavors), plus the terminology in the image sharing form. Formally it closes 6 issues: #1301, #1293, #1296, #1302, #1300, #1294.

**1. Metadata modals** (`EditImageMetadataModal.tsx`, `EditSpecModal.tsx`) — three independent changes in one place:
- A single click on "Delete" now immediately removes the property from local state — previously there was a "first click shows a confirmation, second click deletes" pattern with an automatic timeout reset after 3 seconds (`confirmDeleteIndex` + `useEffect`/`setTimeout`); it has been removed entirely.
- The modal title and Save button now depend on a new `canEdit` prop (`EditImageMetadataModal`) / the already existing `canEdit` (`EditSpecModal`, introduced in #1247): `canEdit ? "Edit Metadata" : "Show Metadata"`, and the "Save Changes" button is rendered only when `canEdit`.
- The list header (`DescriptionTerm`/`DescriptionDefinition` "Property Key"/"Value") was removed and replaced with `<DescriptionList alignTerms="left">`; the modal size changed from `"large"` → `"xl"`.

**2. Terminology "Member ID" → "Project ID"** (image sharing, #1296): the column header, the validation error text, the input placeholder — in every place where they appear in the images UI.

**3. Popup menu reorganization** (#1302) — in three places (Flavors list, Images list, Image details page) the actions are sorted alphabetically, and "Delete" is moved to the end behind a `PopupMenuSectionSeparator`.

**4. "Manage Access" is hidden rather than disabled** when the flavor is public (#1294) — but only in `FlavorListContainer.tsx` (the list), not in `$flavorId.tsx` (the details page of the flavor itself) — see "What it affects".

**5.** One changeset (`patch` for `@cobaltcore-dev/aurora`); the `en`/`de` locales are updated for the new/removed strings.

## How it is implemented

### Single-click delete in metadata

`EditImageMetadataModalInner` (`packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/EditImageMetadataModal.tsx:52-166`, head commit `8c54ea84d`) used to hold `confirmDeleteIndex` and a timer:

```tsx
const [confirmDeleteIndex, setConfirmDeleteIndex] = useState<number | null>(null)

useEffect(() => {
  if (confirmDeleteIndex !== null) {
    const timer = setTimeout(() => setConfirmDeleteIndex(null), 3000)
    return () => clearTimeout(timer)
  }
}, [confirmDeleteIndex])
```

All of this (plus the reset of `confirmDeleteIndex` in `handleEdit`/`handleDelete`, and the "Delete"/"confirm-delete" button branching in JSX) was removed; the delete button is now a single `<Button onClick={() => handleDelete(index)} icon="deleteForever" aria-label={t\`Delete\`} data-testid={\`delete-${entry.key}\`} .../>` without a second step. The test `EditImageMetadata.test.tsx:98-115` was simplified in step: the click on `confirm-delete-${key}` was removed, and the wait for the text "Edit Image Metadata" was replaced with "Edit Metadata" (the modal title was renamed too).

The same pattern was already absent from `EditSpecModal` (Flavors) — there was never a delete confirmation there; the changes in that file concern only item 2 below.

### `canEdit` → title/Save button

`EditImageMetadataModal.tsx:391-452` (the outer exported component) passes the new prop `canEdit = true` down into `EditImageMetadataModalInner` and into the titles of the loading/error states:

```tsx
if (isLoadingExcluded) {
  return (
    <Modal open onCancel={onClose} size="xl" title={canEdit ? t`Edit Metadata` : t`Show Metadata`}>
```

For `EditSpecModal` this is the already existing (#1247) `canEdit`, but the modal resolves it separately — compare `EditSpecModal.tsx:493,503` (the outer loading/error early return, uses the `canEdit` prop verbatim) with the final render `EditSpecModal.tsx:509-519`, which uses a **different** variable:

```tsx
return (
  <EditSpecModalInner
    key={flavor.id}
    ...
    canEdit={resolvedCanEdit ?? false}
  />
)
```

`resolvedCanEdit` is state that is populated asynchronously (`EditSpecModal.tsx:460-477`) either from the `canEdit` prop itself (if it is passed explicitly — `canEdit !== undefined ? Promise.resolve(...) : createPermissionsPromise(...)`) or from a `canUser` query. See "Review" — in practice both call sites pass `canEdit` as an explicit boolean, so the title mismatch in the loading/error branches does not show up today, but it remains a potential trap.

### Removed list header / `alignTerms`

`EditSpecModal.tsx:301-304` and `EditImageMetadataModal.tsx` (similarly):

```tsx
-            <DescriptionList className="mb-6">
-              <DescriptionTerm>{t`Property Key`}</DescriptionTerm>
-              <DescriptionDefinition>{t`Value`}</DescriptionDefinition>
-
+            <DescriptionList className="mb-6" alignTerms="left">
```

`alignTerms` and `PopupMenuSectionSeparator` (used in the menu reorganization below) were checked directly in the installed package `@cloudoperators/juno-ui-components@9.4.0` (`packages/aurora/node_modules/.pnpm/.../build/components/DescriptionList/DescriptionList.component.d.ts`, `.../PopupMenu/PopupMenu.component.d.ts`) — both really exist in the pinned version; this is neither a typo nor a non-existent prop.

### Terminology Member ID → Project ID

`ImageMemberFormRow.tsx:33`, `ImageMembersTable.tsx:83,201` — three places, all in the "share image" block:

```tsx
placeholder={t`Enter project ID`}   // was: t`Enter member ID`
...
newErrors.memberId = t`Project ID (project UUID) is required.`   // was: Member ID (...)
...
<DataGridHeadCell>{t`Project ID`}</DataGridHeadCell>   // was: Member ID
```

The locales (`en`/`de` `messages.po`) correspondingly lose the old `msgid`s and gain new ones; `de` got an empty `msgstr` for two new strings (`"Show Metadata"`, `"No custom metadata properties found."`) — this is expected for untranslated strings and does not block `check-i18n` (extract/compile only).

### Popup menu reorganization

The common pattern in all three places: items are sorted alphabetically by visible label, and "Delete" is moved to the end with a `PopupMenuSectionSeparator`. Example — `FlavorListContainer.tsx:150-176`:

```tsx
<PopupMenuOptions>
  {(canManageSpecs || canListSpecs) && (
    <PopupMenuItem label={canManageSpecs ? t`Edit Metadata` : t`Metadata`} onClick={() => openSpecModal(flavor)} />
  )}
  {canMangageAccess && flavor["os-flavor-access:is_public"] === false && (
    <PopupMenuItem label={t`Manage Access`} onClick={() => openAccessModal(flavor)} />
  )}
  <PopupMenuItem label={t`Show Details`} onClick={() => navigate(...)} />
  {canDeleteFlavor && (
    <>
      <PopupMenuSectionSeparator />
      <PopupMenuItem label={t`Delete Flavor`} onClick={() => openDeleteModal(flavor)} />
    </>
  )}
</PopupMenuOptions>
```

`canMangageAccess` (typo "Mangage") is an existing variable name, not touched by this PR and not part of the diff.

The same pattern (reordering + separator) is applied in `ImageTableRow.tsx:135-190` and `images/$imageId.tsx:358-403`.

## What it affects

**`alignTerms`/`PopupMenuSectionSeparator` are real APIs of the pinned juno version.** Checked directly in the installed `@cloudoperators/juno-ui-components@9.4.0` (see above) — not a risk.

**`EditImageMetadataModal`'s `canEdit` is not used by ANY call site — the read-only mode for Images is unreachable.** Both consumers of the component —

```
packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/$imageId.tsx:451
packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ImageListView.tsx:718
```

— render `<EditImageMetadataModal image=... isOpen=... onSave=... isLoading=... onClose=.../>` without the `canEdit` prop, so it always falls back to the default `true`. This is not accidental: in both places the modal is opened only from the "Edit Metadata" menu item, which is itself already hidden behind `permissions.canUpdate` (`$imageId.tsx:361-374`, `ImageTableRow.tsx` via `onEditMetadata`, called only inside `!isExternalImage && permissions.canUpdate`). I.e. for Images there simply is no "open this modal without edit permissions" scenario — the whole new read-only UI (the "Show Metadata" title, the hidden Save button) was added but never fires. For Flavors, by contrast, `canEdit` really is passed as `canManageSpecs` from a menu item that is available with `canListSpecs` too (without modify permissions) — there the read-only mode makes sense and works. The PR description claims a parallel implementation for "Images & Flavors" — in reality it works for only one of the two entities.

**`$flavorId.tsx` (the flavor details page) was not updated — it diverges from `FlavorListContainer.tsx` on both points of the PR.** The same "Manage Access" pattern that is fixed in the list (`FlavorListContainer.tsx:158`, now hidden via `flavor["os-flavor-access:is_public"] === false`) remains old in `$flavorId.tsx:200`:

```tsx
<PopupMenuItem label={t`Manage Access`} onClick={toggleAccessModal} disabled={isPublicFlavor} />
```

— the menu item is still disabled rather than hidden for a public flavor. In the same file (`$flavorId.tsx:206-209`) the metadata button uses the old terminology, untouched by this PR:

```tsx
<Button variant="primary" onClick={toggleSpecModal}>
  {canManageSpecs ? <Trans>Edit Metadata</Trans> : <Trans>Metadata</Trans>}
</Button>
```

instead of the new `"Edit Metadata"/"Show Metadata"` pair introduced in `EditSpecModal.tsx` by this same PR. `$flavorId.tsx` is not in the list of files changed by PR #1303 — neither inconsistency is touched by the diff.

**The "member ID" terminology outside the images UI is untouched** (`server/Compute/helpers/imageHelpers.ts:360` — a server error text) — out of scope of the stated issues (#1296 is about the sharing interface), not reported as a finding.

## Review

**[90]** `$flavorId.tsx:200` — the flavor details page was not migrated to the "hide rather than disable" pattern for the "Manage Access" item on a public flavor, even though the PR claims to close #1294 without a "list only" caveat. A user who opens a flavor directly (not from the list) and is on a public flavor still sees the same disabled (not hidden) button that the issue asked to remove. Verified line by line, reproduces 100% of the time on a public flavor; the independent `isPublicFlavor` variable in the same file confirms that the pattern simply was not ported.

**[80]** `EditImageMetadataModal.tsx` (the whole file) — the new read-only mode (`canEdit=false` → "Show Metadata" title, hidden Save button) is unreachable in the current call tree: both consumers (`$imageId.tsx:451`, `ImageListView.tsx:718`) do not pass `canEdit`, and the only path to opening the modal is already gated on `permissions.canUpdate`. The PR description explicitly claims a parallel implementation for "Metadata Modals (Images & Flavors)" — in fact, for Images it is dead code as of today, not a working feature. Not a blocking binary bug (nothing breaks — the default `true` always matches the real permission), hence not 90+, but the divergence from the PR description itself and the potential trap for future code (someone at some point passes `canEdit={false}` from somewhere not under `permissions.canUpdate` — the title will work correctly, but this was never specifically tested) put the confidence above the threshold.

Below the threshold (not reported): the title mismatch in the loading/error branches of `EditSpecModal.tsx:493,503` (uses the outer `canEdit` prop, while the final render uses `resolvedCanEdit`) — both current call sites pass `canEdit` as an explicit boolean, so in practice the title in the loading state matches the final one; it would only show up if future calling code relied on asynchronous permission resolution via `canUser`, which doesn't exist today (~40/100).

---
Analyzed: 2026-09-16 · commit `8c54ea84d`
