---
type: pr-report
date: 2026-08-06
status: merged
pr: [1132]
author: mark-karnaukh-extern-sap
branch: mark-images-notifications
---
# PR #1132: refactor(portal): migrate image toasts from legacy Toast to NotificationManager

**Author:** mark-karnaukh-extern-sap · **Status:** created 2026-08-04, merged 2026-08-06 (commit `46256e98`)
**Branches:** `mark-images-notifications` → `main` · **Files:** 12 (+980/-813)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1132

## What was done

The third (after Ceph — commit `32223ac`, and Swift — commit `df25d7c`) and final migration of the legacy `<Toast>` pattern to the app-wide `NotificationManager` (Sonner-based `toast.success/error/warning/info()`) — this time for the Glance images feature. Before this PR, each screen (`ImageListView`, `ImageTableRow`, the `$imageId` details page) kept its own `toastData` state, rendered `<Toast {...toastData} />` as a fixed block and passed an `onDismiss` callback through `ToastConfig` into each of the 24 builders in `ImageToastNotifications.tsx`. The PR removes this state entirely: the builders now return a plain `{ message, description }` object (no `variant`, no JSX rendering via the `NotificationText` component), and the calling code decides the severity itself and dispatches it imperatively:

```tsx
// ImageToastNotifications.tsx:5-11
// Builder helpers for the NotificationManager (Sonner-based) `toast` API.
// Each returns `{ message, ...options }`; the caller destructures and dispatches
// the appropriate severity, e.g.
//   const { message, ...options } = getImageUpdatedToast(name)
//   toast.success(message, options)
// Severity lives at the call site (toast.success / error / warning / info),
// mirroring the Swift/Ceph notification helpers.
```

A concrete example at a call site (one of 22 in `ImageListView.tsx`):

```tsx
// ImageListView.tsx:480-485
if (failedCount === 0) {
  const { message, ...options } = getBulkDeleteSuccessToast(successCount, totalCount)
  toast.success(message, options)
} else if (successCount === 0) {
  const { message, ...options } = getBulkDeleteErrorToast(failedCount, totalCount)
  toast.error(message, options)
```

Besides the refactoring itself, the PR also fixed the typing of error messages: previously `const { message } = error as TRPCClientError<...>` implicitly treated a potentially `undefined` value as `string`; now an explicit `?? ""` fallback is added in most places before passing it to the builder. The English and German translation catalogs were updated for the new named placeholders (`errorMessage` instead of `message` in several places) — both catalogs are in sync, and no empty `msgstr ""` remain.

## How it is implemented

Each of the 24 builders in `ImageToastNotifications.tsx` now returns data rather than a component's JSX markup (the `NotificationText` component, which previously assembled `title`/`description` into a vertical `<Stack>`, was removed from the builders entirely):

```tsx
// ImageToastNotifications.tsx:15-30
export const getImageUpdatedToast = (imageName: string): { message: ReactNode } & NotificationOptions => ({
  message: <Trans>Image Instance</Trans>,
  description: <Trans>Image instance "{imageName}" has been updated</Trans>,
})

export const getImageUpdateErrorToast = (
  imageName: string,
  errorMessage: string
): { message: ReactNode } & NotificationOptions => ({
  message: <Trans>Unable to Update Image</Trans>,
  description: (
    <Trans>
      The image "{imageName}" could not be updated: {errorMessage}
    </Trans>
  ),
})
```

The calling side (`ImageListView.tsx`, `ImageTableRow.tsx`, `$imageId.tsx`) follows the same pattern everywhere — destructure `message`/`options` and call the appropriate `toast` method, without exception (checked line by line across all 26 call sites): `*ErrorToast` → `toast.error`, plain/`*SuccessToast` → `toast.success`, `*PartialToast` → `toast.warning`, `getImageAccessStatusUpdatedToast` → `toast.info`. An example from `ImageTableRow.tsx`:

```tsx
// ImageTableRow.tsx:90-96
const { message, ...options } = getImageAccessStatusUpdatedToast(newStatus)
toast.info(message, options)
onMemberStatusChanged?.()
} catch (error) {
  const errorMessage = (error as TRPCClientError<InferrableClientTypes>)?.message
  const { message, ...options } = getImageAccessStatusErrorToast(errorMessage)
  toast.error(message, options)
}
```

The tests (`ImageToastNotifications.test.tsx`) were rewritten for the new data shape (`{ message, description }` instead of checking a rendered `<Toast>`); two new files were added — `ImageTableRow.test.tsx` and `$imageId.test.tsx` — rendering through real Juno components and the real `NotificationManager` rather than mocks, plus checks of permission-gated actions and the member-status flow.

## What it affects

`ImageToastNotifications.tsx`, `NotificationText.tsx` and the related state are all local to the Images feature (`compute/-components/Images/-components/`); no consumers were found outside the changed files (a `git grep` across the monorepo for all 24 builder names is clean). The change does not go beyond this feature: the public contract of `AuroraApp` (slots, props) is untouched, and `packages/aurora/README.md` needs no update.

Something was left not fully cleaned up: **`NotificationText.tsx` and its test `NotificationText.test.tsx` remained in the tree but became dead code.** Before the PR, all 24 builders rendered their content via `<NotificationText title=... description=... />`; after the refactoring the builders no longer render any JSX at all, and `NotificationText` is not used anywhere (except in its own test) — `git grep -n NotificationText` across the whole repository at the head commit confirms it: only the file itself and its test. This diverges from how the very same refactoring was done earlier in this same repository: for Ceph Buckets (`32223ac`) and Swift Containers (`df25d7c`) the analogous local component was deleted in the same commit that changed the shape of the builders — there the cleanup was complete. The changes to the translation registry (locale files) match the changes in the builders one to one, with no discrepancies.

## Review

The following were run in parallel over the diff: CLAUDE.md/AGENTS.md compliance (with the same caveat as for #1123 — upstream does not contain `AGENTS.md`/[`CLAUDE.md`](../../CLAUDE.md), so the check was done against `CONTRIBUTING.md`/`docs/aurora_architecture_overview.md`/`packages/aurora/README.md`), bug-scan, historical context (`git log`/`git blame`, comparison with the earlier Ceph/Swift migrations to the same pattern), prior-feedback (this PR on GitHub already has automated reviews from CodeRabbit and Copilot — their remarks were re-checked against the code rather than taken on trust) and comment-compliance.

**No issues found with confidence ≥80.** The closest to the threshold is the leftover dead code `NotificationText` (75/100), which fell 5 points short.

Candidates that did not pass the threshold (for completeness — for the future, so they do not have to be searched for again):

- **Leftover dead code `NotificationText.tsx`/`NotificationText.test.tsx`** (see "What it affects" above) — 75/100. A real and confirmed finding (zero consumers, inconsistent with how the earlier Ceph/Swift PRs did the analogous cleanup), but it does not reach the reporting threshold — non-critical (a dead file, not a behavioral bug), removable with a single edit the next time this area is touched.
- **The severity of bulk operations is decided at the call site, not in the builder** (`ImageListView.tsx:470-560`, three handlers `handleBulkDelete`/`handleBulkActivate`/`handleBulkDeactivate`, each directly reproducing `if (failedCount === 0) ... else if (successCount === 0) ... else ...` and dispatching one of 9 separate builders) — 65/100. The PR description claims the pattern is "like Swift and Ceph", but this is exactly the Ceph pattern; the newer Swift pattern (commit `df25d7c`, where the builder itself returns `{ message, severity, ...options }` so that the message and the severity cannot diverge) was not carried over here. The risk is real, but mitigated by the fact that the `if/else if/else` branches sit next to each other in the same block — in practice they are hard to get out of sync.
- **Duplication of jsdom polyfills between the two new test files** (`ImageTableRow.test.tsx`, `$imageId.test.tsx` — both re-stub `scrollIntoView`/`matchMedia` in their own `beforeAll`) — 65/100. The repository already has a centralized `vitest.setup.ts` with `ResizeObserver`/other polyfills, where it would be logical to add these two as well — but none of the other 22 test files with `beforeAll` follows that pattern differently, and in practice the effect is mitigated by defensive guards in the polyfill code itself.
- **Repetition of the inline type `{ message: ReactNode } & NotificationOptions` in each of the 24 builders** (instead of a shared type alias) — 0/100. Formally new in this file (previously there was a shared `ToastConfig`), but exactly the same pattern is already used in all neighboring notification files (`BucketToastNotifications.tsx`, `ObjectToastNotifications.tsx`, `ContainerToastNotifications.tsx`) — this is an existing repository convention, not a deviation by this PR.
- The CodeRabbit remarks already left directly on this PR were re-checked against the code and rejected as not belonging to this PR: debug `console.log` in the bulk handlers (`ImageListView.tsx`, lines ~475/507/540) — the same call existed before the PR, only the variable name changed; the import of `@cloudoperators/juno-ui-components/index` instead of the package root in `$imageId.tsx` — the import path is not touched by this diff; `errorMessage || <Trans>...</Trans>` in `getImageAccessStatusErrorToast` (`ImageToastNotifications.tsx:231-234`) without a `<Trans>` wrapper on the truthy branch — an identical pattern already existed in the JSX version of the builder before the PR (`ImageTableRow.tsx:94-96`, `$imageId.tsx` likewise; the calling code did not change either). CodeRabbit's remark about `getByRole("button")` in the new tests is not ambiguous in practice: the only other interactive role in the same row is `checkbox`, not `button`.

---
Analyzed: 2026-08-06 · commit `8ca4c450e145e98188b2d02ac18c671ea50f89d9`
