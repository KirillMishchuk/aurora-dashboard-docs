---
type: pr-report
date: 2026-08-24
status: merged
pr: [1198]
author: TilmanHaupt
branch: til-del-mod
---
# PR #1198: refactor(portal): equalize delete modals

**Author:** TilmanHaupt · **Status:** merged 2026-08-24 (commit `1513d972`; created 2026-08-21)
**Branches:** `til-del-mod` → `main` · **Files:** 13 (+453/-362)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1198

## What was done

The PR brings three "delete" modals of the Compute section (Flavors, single/bulk Images) and one Storage modal (Swift `DeleteContainerModal`) to a single pattern already adopted in Ceph (`DeleteObjectsModal` etc.): instead of a home-made `ModalFooter`/`ButtonRow`/`Button` — the built-in `Modal` props (`confirmButtonLabel`, `confirmButtonVariant`, `onConfirm`, `disableConfirmButton`/`disableCancelButton`/`disableCloseButton`). For irreversible deletions (Flavor, single Image, bulk Images) a typed confirmation is added — a `TextInput` with the placeholder `delete`; the confirm button is disabled until the entered text matches the word `delete`. Along the way, `DeleteFlavorModal` is switched from `TwoColumnDescriptionList` to a single-column `DescriptionList` (for consistency with Images/Storage), and `DeleteImagesModal` from a flat list of IDs to the declared two-step flow "confirmation → results screen with errors". There is an accompanying changeset (`patch`) and localization edits (en/de).

## How it is implemented

**Shared confirmation pattern** (`DeleteFlavorModal.tsx:193-194`, `DeleteImageModal.tsx:430-431`, `DeleteImagesModal.tsx` similarly):

```tsx
const isConfirmValid = confirmText === "delete"
const confirmLabel = isLoading ? t`Deleting...` : t`Delete Flavor`
...
disableConfirmButton={!isConfirmValid || isLoading}
```

`DeleteFlavorModal` (`DeleteFlavorModal.tsx:52-73`) now calls `client.compute.deleteFlavor.mutate(...)` itself, catches the error, shows it inline (`role="alert"`) and stays open on failure — previously `flavor.swap` was shown in the `TwoColumnDescriptionList` only if it was truthy; now the `Swap` row is always rendered:

```tsx
// DeleteFlavorModal.tsx:127
{flavor.swap === 0 || flavor.swap === "" ? <Trans>None</Trans> : `${Number(flavor.swap)} MiB`}
```

**`DeleteImagesModal`** (the only modal where the two-step flow is actually implemented) keeps `result` in local state and switches the modal's view based on it (`DeleteImagesModal.tsx:14-33`):

```tsx
interface DeleteResult {
  deletedCount: number
  errorCount: number
  errors: Array<{ imageId: string; message: string }>
}
...
const [result, setResult] = useState<DeleteResult | null>(null)
```

`handleConfirm` (`DeleteImagesModal.tsx:44-51`):

```tsx
const handleConfirm = () => {
  if (result === null) {
    // Step A: Confirm
    onDelete(deletableImages)
    // Note: Parent component should call setResult after getting backend response
  } else {
    // Step B: Close results view
    handleClose()
  }
}
```

`DeleteContainerModal` (Swift) is switched to the built-in props also for the "container has objects" branch — previously a separate `Close` button via `modalFooter`/`data-testid="delete-has-objects-close-button"`, now simply `confirmButtonLabel={hasObjects ? t\`Close\` : t\`Delete\`}` (`DeleteContainerModal.tsx:129-131`).

## What it affects

All four modals are internal-only, each with exactly one consumer:

- `DeleteFlavorModal` ← `FlavorListContainer.tsx`, `compute/flavors/$flavorId.tsx`
- `DeleteImageModal` ← `ImageListView.tsx`, `compute/images/$imageId.tsx`
- `DeleteImagesModal` ← `ImageListView.tsx` (the only one, `ImageListView.tsx:777-784`)
- `DeleteContainerModal` ← `ContainerTableView.tsx`

The props of these components (except `DeleteImagesModal`, see review) did not change — there are no outward contract changes; the changeset is correctly marked `patch`.

## Review

The pipeline (CLAUDE.md compliance, quick bug scan, historical context from git blame/log, earlier CodeRabbit/Copilot PR comments on this PR, compliance with code comments) plus independent confidence scoring yielded two findings with confidence ≥80:

1. **The `DeleteImagesModal` results screen is unreachable — `result` is never set** (confidence 100) — `DeleteImagesModal.tsx:44-51`, consumer `ImageListView.tsx:470-471,777-784`. When `result === null`, `handleConfirm` calls `onDelete(deletableImages)` and relies on the comment "Parent component should call setResult after getting backend response" — but `result`/`setResult` are the component's private state; `DeleteImagesModalProps` contains neither a callback nor a prop for passing the result back. The only consumer, `ImageListView.handleBulkDelete` (`ImageListView.tsx:470-496`), in its very first line does `setDeleteAllModalOpen(false)` — i.e. it closes the modal (`isOpen` becomes `false`) before the mutation has even run — and reports the outcome via the already existing toasts (`toast.success`/`error`/`warning`), not via the modal. As a result, `result` stays `null` forever, and all the "Step B: Results view" code (lines `DeleteImagesModal.tsx:56-120`, including handling of `errors`/`hiddenErrorCount`) is dead; the user will never see the results screen, which the PR description declares as the main feature ("two-step flow: confirmation input → results view with error reporting"). Independently confirmed by two bots on this same PR (CodeRabbit, severity "Major": "`result` remains `null` and the results view is unreachable after every bulk deletion"; Copilot: the same, with a proposed fix — either `onDelete` returns a `Promise<DeleteResult>` and `handleConfirm` `await`s it, or the result is passed to the modal via a new prop, analogous to Ceph `DeleteObjectsModal`) — these comments still point to the current head (`a613b137`), i.e. they are not outdated and were not resolved by subsequent commits.
2. **The `Swap` display in `DeleteFlavorModal` produces `NaN MiB`/`0 MiB` instead of `None` for real API values** (confidence 90) — `DeleteFlavorModal.tsx:127`, the type of `flavor.swap` is `packages/aurora/src/server/Compute/types/flavor.ts:8-19` (`swap: z.union([z.string(), z.number()]).optional()`). The check `flavor.swap === 0 || flavor.swap === ""` catches only numeric `0` and the empty string. It does not catch: (a) `flavor.swap === undefined` — the Zod schema makes the field `optional()`, and in this case `${Number(flavor.swap)} MiB"` yields `${Number(undefined)}` = `"NaN MiB"`; (b) the string `"0"` — judging by the fixtures `flavorHelpers.test.ts:47,58,69` (`swap: "0"`), this is a typical value that Nova actually returns for flavors without swap on some OpenStack versions, and `Number("0")` yields `0`, so the `None` branch does not fire — `"0 MiB"` is rendered, which is exactly the behavior this PR's changeset claims to have fixed ("fix swap display to show "None" instead of "0 MiB""). Before the PR the `Swap` row was simply not shown in this case (`...(flavor?.swap ? [...] : [])` — the falsy check skipped `0`, `"0"` and `undefined` alike), so for these two realistic cases this is a pure display regression, not just an incomplete fix. A neighboring component of the same domain, `FlavorListContainer.tsx:180`, uses the common technique `flavor.swap || "–"`, which confirms that falsy `swap` values (including `"0"`) are an expected rather than an edge case in this codebase.

Below the threshold (not reported): in `DeleteContainerModal.test.tsx` the test "renders Close button instead of Delete" checks `screen.getAllByRole("button", { name: /^Close$/i }).length).toBeGreaterThan(0)` — according to the Juno clone (`Modal.test.tsx:211`), the modal's own X button has `aria-label="close"`, which also matches this case-insensitive pattern, so the test would pass even if the new `Close` confirm button were not rendered at all; a purely test-side insufficiency that does not affect production behavior (confidence 50). The missing German translations for the new strings (`de/messages.po`, flagged by CodeRabbit) are not reported separately — in this repository an empty `msgstr` for new strings at the time of a PR is normal practice (translations are added in a separate pass), not a blocking defect.

---
Analyzed: 2026-08-24 · commit `a613b137`
