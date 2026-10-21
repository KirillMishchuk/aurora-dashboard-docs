---
type: pr-report
date: 2026-09-01
status: merged
pr: [1211]
author: TilmanHaupt
branch: til-modal
---
# PR #1211: refactor(portal): refactor all modals to the same layout

**Author:** TilmanHaupt · **Status:** merged 2026-09-01 (created 2026-08-27)
**Branches:** `til-modal` → `main` · **Files:** 51 (+1593/-1257)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1211

> Closes #1169, #1141, #1241.
>
> **Full re-analysis on 2026-09-01:** the head commit changed from `0cb05e66` (the version analyzed in the previous version of this report on 2026-08-27–28 — 33 files, +689/-763, a shared `useDeleteConfirmation` hook) to `ce4e8a4c` (51 files, +1593/-1257). The author fully abandoned the shared `useDeleteConfirmation` hook approach — that file (`packages/aurora/src/client/hooks/useDeleteConfirmation.ts`) does not exist in the current commit — and rewrote all modals on **TanStack Form + Zod** directly, on top of the already existing (not new) `useModalTracking` hook (introduced in PR #1007). This is effectively a new implementation of the same PR: the old findings from the previous version of the report (the `ImageListView` bug comparing by count, the unreachable `markSubmitted()` check in `DeleteImageModal`, the duplicated scope checkbox in the changeset) need to be re-verified — some of them do not carry over 1:1 to the new code. The report below is written from scratch against the current commit.

## What was done

Issue #1141 asked for visual consistency across the delete/action modals, #1169 — to remove the bulk-selection checkboxes from `DataGrid` header cells. Instead of a shared hook (as in the intermediate version of this same PR and in PR #1198), the author now migrates ~15 confirmation modals to **TanStack Form** (`useForm`/`useStore` from `@tanstack/react-form`) with **Zod** validation: each modal independently declares its own Zod schema of the form `z.object({ confirm: z.string().refine((v) => v === "delete", { message: ... }) })`, wires it up as `validators: { onSubmit: formSchema }`, and gates the confirm button via `useStore(form.store, (s) => s.isSubmitting || s.values.confirm !== "delete")`. Analytics (`.open`/`.close` events) go through the already existing `useModalTracking`, with no changes to the hook itself.

Affected: Compute (`DeleteFlavorModal`, `DeleteImageModal`, `DeleteImagesModal`, `DeactivateImageModal`, `DeactivateImagesModal`), Network (`DetachFloatingIpModal`, `ReleaseFloatingIpModal`, `DeleteRBACPolicyDialog`, `DeleteRuleDialog`, `DeleteSecurityGroupDialog`), Storage/Ceph (`DeleteObjectModal`, `EmptyBucketsModal`, plus minor imports/formatting edits in `BucketPolicyModal`, `CreateBucketModal`, `DeleteBucketPolicyModal`, `DeleteCorsRuleModal`/`DeleteCorsRulesModal`, `DeleteLifecycleRuleModal`/`DeleteLifecycleRulesModal`, `DeleteVersionsModal`, `EmptyBucketModal`, `EnableVersioningModal`, `SuspendVersioningModal`, `LifecycleRuleForm`), Storage/Swift (`DeleteContainerModal`, `EmptyContainerModal`, `EmptyContainersModal`, `DeleteFolderModal`, `DeleteObjectModal`, `DeleteObjectsModal`). Along the way: `ImageListView.tsx` lost the "select all" checkbox in the table header (see "Review"); `EmptyContainerModal` — the object list moved from `DataGrid` to a scrolling `Stack`, the `Empty` button became `Empty Container`, the modal size went from `small` to `large`; the `de`/`en` locales were updated for new/renamed strings; `eslint.config.mjs` and `turbo.json` — formatting only (line wrapping), no semantic changes. The changeset (`.changeset/swift-ceph-delete-modals.md`, `patch`) this time accurately describes the essence of the change (TanStack Form + `useModalTracking` instead of `useDeleteConfirmation`, Zod schemas, consistent tracking) — unlike earlier PRs in this knowledge base (#1172, #1198), here the scope is named correctly.

No shared reusable hook is introduced this time — each modal independently repeats the same ~10-line block (schema + `useForm` + `useStore`), meaning the PR shifts direction compared with its own previous version (which precisely generalized this logic into `useDeleteConfirmation`) towards duplication. That is not a bug in itself, but it is worth knowing when reading this as a single story: the PR changed its architectural approach to the same task twice within a few days.

## How it is implemented

### Canonical pattern (example — `DeleteFlavorModal.tsx`)

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Flavors/-components/DeleteFlavorModal.tsx:49-93
const formSchema = z.object({
  confirm: z.string().refine((value) => value === "delete", {
    message: t`Type "delete" to confirm`,
  }),
})

const form = useForm({
  defaultValues: { confirm: "" },
  validators: { onSubmit: formSchema },
  onSubmit: async () => { /* ... */ },
})

const canDelete = useStore(form.store, (state) => state.isSubmitting || state.values.confirm !== "delete")
```

The confirm button is gated by a string comparison (`canDelete`), not by the form's validation result — the Zod schema formally exists, but the button is already disabled until the entered text matches the expected word. This works correctly as UX, but it means the `onSubmit` validator almost never sees an invalid value via a normal click — see the finding about inconsistent `errortext` in "Review".

### Inconsistency in displaying validation errors

Of the ~15 modals with type-to-confirm gating, only 4 actually pass `field.state.meta.errors` through to `TextInput`:

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Images/-components/DeleteImagesModal.tsx:231-239
<TextInput
  label={t`Type "delete" to confirm`}
  ...
  invalid={field.state.meta.errors.length > 0}
  errortext={...}
```

The rest (`DeleteFlavorModal.tsx:161-176`, `DeleteImageModal.tsx`, `DetachFloatingIpModal.tsx`, `ReleaseFloatingIpModal.tsx`, `DeleteRBACPolicyDialog.tsx`, `DeleteRuleDialog.tsx`, `DeleteSecurityGroupDialog.tsx`, `EmptyBucketsModal.tsx`, `DeleteObjectModal.tsx` — Ceph and Swift, `EmptyContainersModal.tsx`) declare the same Zod schema but never read `field.state.meta.errors` in the markup — the message `` t`Type "delete" to confirm` `` (or its equivalent) exists only in the schema and is never shown to the user. Details — "Review", finding #4.

### `EmptyContainersModal.tsx` — close tracking called twice

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/EmptyContainersModal.tsx:101-108, 123-126
const handleClose = () => {
  trackClose()
  emptyContainerMutation.reset()
  setProgress(null)
  form.reset()
  resetTracking()
  onClose()
}
...
<Modal
  ...
  onCancel={() => {
    trackClose()
    handleClose()
  }}
```

In all the other modals of the batch, `trackClose()` was moved inside `handleClose`, and `onCancel` was simplified to `onCancel={handleClose}` (e.g. `EmptyBucketsModal.tsx`, `DeleteVersionsModal.tsx`, `EnableVersioningModal.tsx` and other Ceph modals). `EmptyContainersModal.tsx` is the only file where `trackClose()` was added in both places: closing this particular modal (X button/Cancel) sends the `.close` analytics event twice. See "Review", finding #1.

### `DeleteContainerModal.tsx` — duplicated validation of the same field

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/DeleteContainerModal.tsx:29-33, 216-238
const formSchema = z.object({
  confirm: z.string().refine((value) => value === "delete", {
    message: t`The text must match "delete"`,
  }),
})
const form = useForm({ ..., validators: { onSubmit: formSchema }, ... })
...
<form.Field
  name="confirm"
  validators={{
    onSubmit: ({ value }) => (value !== "delete" ? t`The text must match "delete"` : undefined),
  }}
  children={(field) => (
    <TextInput
      ...
      errortext={field.state.meta.errors.map((e) => (typeof e === "string" ? e : e?.message)).join(", ") || undefined}
```

The only modal in the PR where the same field has both a form-level Zod schema and a separate field-level `onSubmit` validator with an identical check. See "Review", finding #2.

## What it affects

All affected components are modals with exactly one consumer in their own route file (internal use, no external contract). `@tanstack/react-form` (`^1.0.0`) and `zod` (`^4.0.0`) were already dependencies of `packages/aurora` before this PR (partly used already in the previous version of this same PR/#1198) — `package.json` is not touched in the diff, no new dependencies. `useModalTracking` is neither new nor changed by this PR, only reused. The only thing that actually disappears from the codebase is the `useDeleteConfirmation.ts` file and its tests (introduced by an intermediate commit of this same PR earlier, before the current head) — but since no merged commit in `main` used it, this is not a breaking change for external consumers.

`ImageListView.tsx` is the only file where this PR touches behavior beyond the delete modals themselves (see "Review", finding #3).

## Review

**Found (confidence ≥ 80):**

1. **`EmptyContainersModal.tsx` — `trackClose()` called twice on cancel.** (confidence 95)
   `handleClose` (lines 101-108) calls `trackClose()`, but `onCancel` (lines 123-126) wraps `handleClose` in yet another `trackClose()` before calling it. In all the other modals of the PR, exactly the same refactoring removed precisely this kind of wrapper (`onCancel={handleClose}` with no duplication). A user cancelling this particular bulk action (X button or Cancel button) sends the close analytics event twice — skewing close/abandon-rate metrics for this modal specifically.
   File: `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/EmptyContainersModal.tsx:101-108,123-126`.

2. **`DeleteContainerModal.tsx` — a duplicate field-level validator on top of the Zod schema produces a doubled error message.** (confidence 85)
   Lines 29-33/39-41 wire up the Zod schema at the form level; lines 216-225 add another `onSubmit` validator for the same `confirm` field with an identical check (`value !== "delete"`). In TanStack Form, `field.state.meta.errors` aggregates errors from both levels for the same field path, and lines 234-238 join them with `.join(", ")` — when validation fires (e.g. the user presses Enter in the text field without clicking the confirm button itself — the native form submit is not blocked by `disableConfirmButton`, unlike a button click), the field will show `"The text must match "delete", The text must match "delete""` instead of a single message. In all the other modals with `errortext` (`DeleteImagesModal`, `EmptyContainerModal`, `DeleteObjectsModal` — Swift) there is exactly one validator — the Zod schema.
   File: `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/DeleteContainerModal.tsx:216-225`.

3. **Two German strings lost their translation while the source text is unchanged.** (confidence 90)
   `packages/aurora/src/locales/de/messages.po:410-411` (`msgid "Already deactivated (will be skipped):"`) and `:2096-2097` (`msgid "Images to deactivate:"`) — neither `msgid` was changed by this PR (unlike neighboring strings in the same diff, where `msgstr` is also reset to `""`, but because the `msgid` itself changed, e.g. `"Detach Floating IP {floating_ip_address}"` → `"Detach Floating IP \"{floating_ip_address}\""`), yet the German `msgstr` was blanked from `"Bereits deaktiviert (wird übersprungen):"` and `"Zu deaktivierende Images:"` to `""`. `pnpm check-i18n` will not catch this (an empty `msgstr` is syntactically valid), so the lost translation will ship to production silently. The same class of regression (blanking `msgstr` with an unchanged `msgid` due to the lingui tool regenerating the catalog) was already noted in this knowledge base for PR #1111 — a recurring pattern in this repository; it is worth checking the `pnpm check-i18n`/extraction process once rather than fixing it point by point every time.
   File: `packages/aurora/src/locales/de/messages.po:410-411,2096-2097`.

4. **The "field-level errors" pattern announced in the PR is actually wired up in only 4 of ~15 migrated modals — the Zod message in the rest is never displayed.** (confidence 80)
   `DeleteImagesModal.tsx:231-239`, `DeleteContainerModal.tsx:234-238`, `EmptyContainerModal.tsx`, `DeleteObjectsModal.tsx` (Swift) read `field.state.meta.errors`/`invalid`/`errortext`. `DeleteFlavorModal.tsx:161-176`, `DeleteImageModal.tsx`, `DetachFloatingIpModal.tsx`, `ReleaseFloatingIpModal.tsx`, `DeleteRBACPolicyDialog.tsx`, `DeleteRuleDialog.tsx`, `DeleteSecurityGroupDialog.tsx`, `EmptyBucketsModal.tsx`, `DeleteObjectModal.tsx` (Ceph and Swift), `EmptyContainersModal.tsx` — do not: `TextInput` there receives neither `invalid` nor `errortext`, even though a Zod schema with a custom `message` is declared in each one. Since the confirm button in these modals is gated by a separate string comparison (see "How it is implemented"), nothing breaks functionally — but the PR description explicitly names "field-level errors via `field.state.meta.errors`" as one of the key improvements, and in most files this is dead code. Not critical for functionality, but it is worth either finishing it or removing the unused messages from the schemas.
   Files: listed above.

**Also noted (confidence 50-79, did not reach full confidence):**
- **[70]** `ImageListView.tsx:601-625` — the "select all" checkbox in the `DataGrid` header was removed entirely (`<DataGridHeadCell></DataGridHeadCell>` instead of a `Checkbox` with a handler), not fixed. This resolves the cross-page selection bug analyzed in the previous version of this same PR (comparison by count instead of by id, which was confidence 98 in the 2026-08-27–28 report) — but at the cost of completely removing "all at once" bulk selection from the header; bulk actions (Deactivate/Delete Images) now require clicking each row individually. Judging by the tests (`ImageListView.test.tsx` — the select-all/deselect-all tests were deleted, not updated) and the PR description's own item "Removed unused Checkbox import from ImageListView" under "Other Improvements", the decision looks intentional rather than forgotten — so I am not raising it above the threshold, but it is worth checking against issue #1169 (which asked precisely to remove this checkbox from the header) — if this is its direct resolution rather than a side effect, it should be named explicitly for changelog readers rather than hidden under "Other Improvements".
- **[75]** `DeleteFlavorModal.tsx:105,111` — `` title={t`Delete Flavor "${flavorName}"`} `` is not guarded against `flavor === null` (prop `flavor: Flavor | null`); the modal body has such a guard (`{flavor && (...)}` on line 128), the title does not. The very same pattern (same file, same line number) was already noted in the previous version of this report on 2026-08-27 with the same confidence 75 and the same caveat: reproducibility is limited to the narrow window of the modal's closing animation, if `flavor` is reset in the parent before `isOpen` becomes `false` (`FlavorListContainer.tsx` does indeed reset both in a single `closeDeleteModal()`, lines 84-87 — verified).
- **[55]** `DetachFloatingIpModal.test.tsx:158-163` and `ReleaseFloatingIpModal.test.tsx:157-162` — the test name `"shows loading state and hides input form when isLoading is true"` contradicts its own assertion (`expect(screen.queryByPlaceholderText("detach"/"release")).toBeInTheDocument()` — i.e. the field is now visible, not hidden). The test still passes and correctly checks the component's current behavior (the form is no longer hidden during loading) — only its name is outdated and misleading.
- **[50]** `DeleteObjectsModal.tsx` (Swift, plural) — the comment `// Type-to-confirm guard. Bulk deletion is irreversible...` stayed in place, but the code it described (the old `useState`/`isConfirmed`) was removed; the comment now sits directly above the unrelated `bulkDeleteMutation` declaration. The type-to-confirm mechanism itself moved further up the file into the new Zod schema/`useForm` block — the meaning of the comment is not outdated, but its physical location is now misleading.

---
Analyzed: 2026-09-01 · commit `ce4e8a4c`
