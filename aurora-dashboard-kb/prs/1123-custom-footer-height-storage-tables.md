---
type: pr-report
date: 2026-08-06
status: merged
pr: [1123]
author: mark-karnaukh-extern-sap
branch: mark-object-storage-fix-table-view-height-it-2
---
# PR #1123: fix(portal): account for custom footer height when sizing storage tables

**Author:** mark-karnaukh-extern-sap · **Status:** created 2026-07-30, merged 2026-08-06 (commit `9e817d02`)
**Branches:** `mark-object-storage-fix-table-view-height-it-2` → `main` · **Files:** 5 (+186/-77)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1123

## What was done

A direct continuation of [PR #1090](./1090-viewport-height-storage-tables.md): that PR replaced the hardcoded viewport offsets in the four object storage list views (Ceph Buckets/Objects, Swift Containers/Objects) with the `useAvailableViewportHeight` hook, which measures the table's actual position from the top, but at the bottom it still subtracted a fixed constant `bottomGap` (52px) — an estimate of "how much space the shell footer takes". As long as the footer is the standard one, this worked; as soon as the host application puts its own footer of arbitrary height into the `pageFooter` slot (via `slots.pageFooter` in `AuroraApp`), the estimate diverges from reality: a taller custom footer covers the last rows of the table, a shorter one leaves an empty gap at the bottom.

This PR removes the very need to estimate anything at the bottom: instead of a constant, the hook now measures the footer's actual position in the DOM (`getBoundingClientRect()` on the `.app-page-footer` element) and takes it as the lower bound of the available space. The constant `DEFAULT_BOTTOM_GAP` (52px, value unchanged) remains only as a fallback for when there is no footer in the DOM at all (embedded mode without a `pageFooter` slot). Along the way, the `bottomGap` parameter was removed from the hook and its wrapper `useVirtualizedTableBody` — it was needed only for the old constant logic, and none of the four calling components used it (checked with `git grep` — see "What it affects"), so the removal is purely internal. Separately, `MIN_HEIGHT` (the floor below which the height is not clamped) was lowered from 200 to 150px — according to the code comment it is still "a couple of table rows", just a more generous threshold for the case where little space is available.

## How it is implemented

Previously the lower bound was a constant; now it is a function `findBottomBoundary()` that looks up a DOM element by the `.app-page-footer` selector and, if it exists, returns its top edge (minus a small visual gap `GAP = 8px`); if there is no footer, the old behavior applies (the bottom of the viewport minus `DEFAULT_BOTTOM_GAP`):

```ts
// packages/aurora/src/client/hooks/useAvailableViewportHeight.ts:46-52
function findBottomBoundary(): number {
  const footer = document.querySelector<HTMLElement>(FOOTER_SELECTOR)
  if (footer) {
    return footer.getBoundingClientRect().top + window.scrollY - GAP
  }
  return window.scrollY + window.innerHeight - DEFAULT_BOTTOM_GAP
}
```

`measure()` now reads both bounds explicitly (top from the element itself, bottom from `findBottomBoundary()`), instead of the previous "viewport minus top minus constant":

```ts
// packages/aurora/src/client/hooks/useAvailableViewportHeight.ts:99-112
const measure = () => {
  // Document coordinates for both edges (getBoundingClientRect is
  // viewport-relative, so add scrollY): the element's top and the top of
  // whatever bounds it from below (the page footer, or the viewport). Using
  // document coordinates keeps the difference stable regardless of scroll.
  const top = element.getBoundingClientRect().top + window.scrollY
  const bottom = findBottomBoundary()
  const available = Math.floor(bottom - top)
  // Clamping here can leave the element taller than the space available,
  // which lets the page scroll. That is the intended trade-off — see above.
  const next = Math.max(MIN_HEIGHT, available)
  // Ignore sub-pixel churn so a re-layout cannot toggle the value forever.
  setHeight((previous) => (previous !== undefined && Math.abs(previous - next) < 1 ? previous : next))
}
```

Both top and bottom are converted to "document" coordinates (`+ window.scrollY`) — both `getBoundingClientRect()` calls are made synchronously within the same `measure()` tick, so there is no discrepancy due to scrolling between the two reads; this is the same technique #1090 already used for the top bound, now applied to the bottom one as well.

Since the footer is not an ancestor of the measured element (it is a sibling in the layout tree) rather than part of the already tracked parent chain, a change in its height cannot be caught by the existing `element.parentElement` traversal. So the footer is registered with the `ResizeObserver` separately:

```ts
// packages/aurora/src/client/hooks/useAvailableViewportHeight.ts:139-143
// The footer bounds the element from below; a change in its height (custom
// footer content) must trigger a re-measure even though it is not an
// ancestor of the element.
const footer = document.querySelector(FOOTER_SELECTOR)
if (footer) observer.observe(footer)
```

The `.app-page-footer` selector itself is a wrapper owned by the application (not a juno-ui-components library class), so that the measurement does not depend on the shell's internal markup. The wrapper is added in the root layout around the `pageFooter` slot, only when the slot is filled:

```tsx
// packages/aurora/src/client/routes/__root.tsx:46-55
pageFooter={
  // Wrapped in an app-owned element so the table-height measurement can
  // anchor its bottom edge to the footer without depending on the
  // shell's internal markup. See useAvailableViewportHeight.
  slots?.pageFooter ? (
    <div className="app-page-footer">
      <Slot component={slots.pageFooter} useShadowDOM={false} />
    </div>
  ) : undefined
}
```

The hook's public signature became simpler — the `bottomGap` parameter was removed entirely, not just left unused:

```ts
// packages/aurora/src/client/hooks/useAvailableViewportHeight.ts:82 (was: (bottomGap: number = DEFAULT_BOTTOM_GAP))
export function useAvailableViewportHeight<T extends HTMLElement>() {
```

The tests (`useAvailableViewportHeight.test.tsx`) were rewritten for the new mechanics: instead of a single `vi.spyOn(...).mockReturnValue(...)` on `getBoundingClientRect` (the same value for any element), there is now one spy in `beforeAll` that reads from a mutable map `currentRects` by `data-testid` — this makes it possible to stub different `top` values for the table body and for the footer at the same time, which is exactly what is needed to test the new logic. Scenarios were added: a taller/shorter footer (the table height decreases/grows accordingly), no footer (fallback to the old constant), and the result being independent of the current page scroll.

## What it affects

`useAvailableViewportHeight` and `useVirtualizedTableBody` are internal hooks of the `@cobaltcore-dev/aurora` package, used only by the four object storage views (the same ones as after #1090): `BucketTableView.tsx`, `Ceph/Objects/ObjectsTableView.tsx`, `Swift/Containers/ContainerTableView.tsx`, `Swift/Objects/ObjectsTableView.tsx`. A `git grep` across the whole monorepo for both hook names finds no other consumers — the change is entirely internal.

Removing the `bottomGap` parameter is safe: neither at the merge-base nor now did any of the four `useVirtualizedTableBody({...})` calls in these views pass it (checked on both versions of the code) — the parameter was dead from the point of view of actual calls even before this PR; the PR simply removed it from the signature.

The `pageFooter` slot is part of the public contract of `AuroraApp` (`packages/aurora/README.md`, Slots section). The shape of the slot itself (which component is passed in and how it is rendered via `<Slot>`) has not changed — the PR only adds an internal `<div className="app-page-footer">` wrapper around the already existing slot rendering, so `packages/aurora/README.md` needs no update and was not touched. `apps/dashboard` (the reference consumer application) does not use the `pageFooter` slot at all — checked with `git grep` — so for it this change is not observable.

## Review

The following were run in parallel over the diff: CLAUDE.md/AGENTS.md compliance, bug-scan, historical context (`git log`/`git blame`), prior-feedback (the KB report on #1090 plus the index of other reports) and comment-compliance. One methodological detail: `AGENTS.md`, which the compliance check usually relies on, does not exist upstream (`origin/main`, which this PR targets) — upstream does not yet contain such a guide. The compliance check was instead done against the actual upstream documents: `CONTRIBUTING.md`, `docs/aurora_architecture_overview.md`, `packages/aurora/README.md` — no violations found (the `-components/`/route-file boundaries are respected, the `pageFooter` slot contract has not changed, the changeset matches the form of other real changesets in the repository, and the test file follows the colocated-vitest-jsdom conventions).

**No issues found with confidence ≥80.**

Candidates that did not pass the threshold (for completeness — for the future, so they do not have to be searched for again):

- The hypothesis that `ResizeObserver` subscribes to the footer only when the effect first runs (`useAvailableViewportHeight.ts:142-143`, dependency `[element]`), and if the `.app-page-footer` element appears in the DOM later, it will never be subscribed to, and `measure()` will keep using the constant fallback. On re-checking: `measure()` re-runs `document.querySelector` every time anyway, so the calculation does not "stick" to a stale value if a recalculation happens at all; and in reality a recalculation will almost certainly happen — inserting/removing the footer changes the layout of the shell's flex column, which affects the element's already tracked ancestors (the `element.parentElement` chain), which are being observed anyway. Moreover, the "footer appears after the table's first render" scenario does not match the only real usage site — the `pageFooter` slot is defined at the root layout level when `AuroraApp` is initialized, not toggled dynamically after the nested tables mount. The independent agent's final score: 45/100 — architecturally the case is possible, but unlikely in practice and mitigated by the side effect of tracking ancestors.
- The hypothesis that `document.querySelector(FOOTER_SELECTOR)` is a global selector not scoped to a specific instance, and if `AuroraApp` is embedded twice on the same page, both tables will find the same footer (the first in document order). On re-checking: the whole hook is already tied to page-global APIs (`window.innerHeight`, `window.scrollY`, `window.addEventListener("resize", ...)`, `document.body` as the observation root) — multi-instance embedding of `AuroraApp` on a single page would not be supported by this code anyway (nor by the `AuroraApp` architecture as a whole — its own router, its own QueryClient, its own i18n wrapper per instance), regardless of this PR. Not a new problem introduced by this PR, but an existing assumption that the PR is simply consistent with. Score: 0/100.

---
Analyzed: 2026-08-06 · commit `5564e487a4adedbea72cbcdc0592c9e837288e21`
