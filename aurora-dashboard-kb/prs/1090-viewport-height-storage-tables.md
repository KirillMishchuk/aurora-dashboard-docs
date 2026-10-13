---
type: pr-report
date: 2026-07-24
status: merged
pr: [1090]
author: mark-karnaukh-extern-sap
branch: mark-object-storage-fix-table-view-scroll-issue
---
# PR #1090: fix(portal): size storage tables to the available viewport height

**Author:** mark-karnaukh-extern-sap · **Status:** merged 2026-07-24 (`fa875c73`)
**Branches:** `mark-object-storage-fix-table-view-scroll-issue` → `main` · **Files:** 13 (+577/-77)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1090

Closes #1091, part of epic #1027.

## What was done

All four object storage list views (Ceph Buckets, Ceph Objects, Swift Containers, Swift Objects) computed the height of the virtualized table body via a hardcoded viewport offset — `calc(100vh - 490px)`, `470px`, `490px` and `500px` respectively, each an estimate of "how much is rendered above the table". As soon as that estimate diverged from reality (a banner in the `serviceBanner`/`projectOverviewBanner` slot, the toolbar or breadcrumbs wrapping onto a second line, a narrow window), the document became taller than the viewport and a second scrollbar appeared next to the table's own scrollbar.

This is not a hypothetical risk in hindsight: `git log` on these four files shows that the magic number really did "drift" through iterations of eyeball tuning over the entire history of the project — for example, the Ceph Buckets offset went through `400→425→545→520→545→510→490px`, Swift Objects through `485→550→490→470px`, and not a single commit explains "490 because X". PR #863, which originally introduced this pattern, had already received a remark from CodeRabbit about its fragility with explicit advice to make the offset dynamic — i.e. exactly what this PR does.

Instead of an offset "from the top" (what is rendered above the table — the thing that keeps changing), the PR measures the space actually remaining below the table's current position in the document, rather than guessing it in advance.

## How it is implemented

The new hook `useAvailableViewportHeight` (`packages/aurora/src/client/hooks/useAvailableViewportHeight.ts:43-107`) measures the element's position via `getBoundingClientRect()` and computes:

```ts
// useAvailableViewportHeight.ts:60-68
const measure = () => {
  const topInDocument = element.getBoundingClientRect().top + window.scrollY
  const available = Math.floor(window.innerHeight - topInDocument - bottomGap)
  const next = Math.max(MIN_HEIGHT, available)
  setHeight((previous) => (previous !== undefined && Math.abs(previous - next) < 1 ? previous : next))
}
```

`topInDocument` is not needless complexity: `getBoundingClientRect().top` returns the element's position relative to the **current** viewport, which changes as the page scrolls; adding `window.scrollY` gives a position that is invariant to the current scroll (`rect.top` and `scrollY` change in opposite directions by the same amount on a pure scroll, so their sum is constant). This matters: without this term, if the user scrolled the page down while the `MIN_HEIGHT` fallback was in effect, the next recalculation (on resize/`ResizeObserver`) would see the table "closer to the top" of the current viewport and would keep growing its height without bound on every scroll — the sum with `scrollY` prevents this by returning the same structural value regardless of where the window is currently scrolled. (Verified manually and by an independent review agent — details in the "Review" section.)

Four implementation details, each a fix for a specific case found during development (listed in the PR description and confirmed by the code):

- **Callback ref, not a ref object** (`ref` is built via `useCallback`, `useAvailableViewportHeight.ts:50-53`) — the empty/loading state of the table has no scroll container at all; a ref object would be read once as `null` and never checked again, leaving the table unmeasured forever.
- **`height`, not `max-height`** — with `max-height` the container's size follows its content, closing a loop with the virtualizer (measured rows → container size → virtualizer recalculates the range → measures again).
- **The virtualizer stays silent while the height is unknown** — `useVirtualizedTableBody.ts:47,57-59` returns `virtualItems: []`/`totalSize: 0` while `height === undefined`; otherwise the unmeasured container is sized by its content height and the virtualizer renders the whole list at once on the first commit.
- **`ResizeObserver` is optional** (`useAvailableViewportHeight.ts:87`) — measurement works off the window `resize` anyway; where `ResizeObserver` is missing (jsdom), the table used to stay completely empty.

Composition: `useVirtualizedTableBody` (`packages/aurora/src/client/hooks/useVirtualizedTableBody.ts:32-63`) combines the measurement with `@tanstack/react-virtual`, keeping `rowHeight`/`overscan` the same for all four views. Each view (e.g. `BucketTableView.tsx:59-68,152-168`) shrank from three separate blocks (height hook + virtualizer config + gating) to a single call:

```tsx
// BucketTableView.tsx:61-68
const {
  ref: tableBodyRef,
  elementRef: parentRef,
  height: bodyHeight,
  virtualItems,
  totalSize,
  measureElement,
} = useVirtualizedTableBody({ count: buckets.length })
```

```tsx
// BucketTableView.tsx:155-158
<div
  ref={tableBodyRef}
  className="overflow-auto"
  style={{ height: `${bodyHeight ?? 0}px` }}
  data-testid="buckets-table-body"
>
```

`MIN_HEIGHT = 200` (`useAvailableViewportHeight.ts:16`) is a documented, deliberate trade-off: if there is less space, the table is clamped to the minimum and the page gets a scrollbar, rather than a table one and a half rows tall. This is not a forgotten edge case but explicitly described behavior (see the hook's JSDoc, lines 37-41) — a separate (last, separate from this PR) `docs` commit on the same branch documents this specifically.

## What it affects

Both new hooks are used only by these four views — `git grep` across the whole monorepo for `useAvailableViewportHeight`/`useVirtualizedTableBody` finds no other consumers. The change is entirely internal and does not leak outward (to other packages/apps of the monorepo).

Within storage itself there are four more independent places with `useVirtualizer` — `Ceph/Objects/CopyObjectModal.tsx`, `Ceph/Objects/MoveObjectModal.tsx`, `Swift/Objects/CopyObjectModal.tsx`, `Swift/Objects/MoveRenameObjectModal.tsx` (the folder browser inside the copy/move object modals). They are not touched by this PR, and that is correct: their scroll container is `max-h-56` (a fixed ~224px), independent of the viewport and not subject to the banner bug — i.e. this is not the same bug left half-fixed, but a structurally different, unrelated pattern.

## Review

The diff and history were run in parallel through: bug-scan, comment-compliance (checking comments against the code), historical context (`git log`/`git blame`) and prior-feedback (issues/old PRs/comments already left on the PR itself). One candidate finding required manual re-verification — there is a separate explanation for it below.

**No issues with confidence ≥80 found.**

Candidates that did not pass the threshold (for completeness — for the future, so there is no need to search again):

- The hypothesis of mixed coordinate systems in the `measure()` formula (`useAvailableViewportHeight.ts:62-63`) — at first glance it looks like a bug (viewport-relative `rect.top` + `window.scrollY`, subtracted from viewport-relative `innerHeight`). A manual algebraic check (and, independently, the comment-compliance agent) confirmed that `rect.top + scrollY` is mathematically invariant to scrolling (this is fixed by the very contract of `getBoundingClientRect()`), and the resulting formula indeed does not drift on scroll — the code comment ("Relative to the document, so the value does not drift while scrolling") is correct. A false positive, rejected after re-verification.
- `Math.abs(previous - next) < 1` (`useAvailableViewportHeight.ts:68`) is technically redundant and does not do what the comment claims (`next`/`previous` are always integers after `Math.floor`, so the comparison is equivalent to `===`, which React's `setState` bailout already gives for free) — but this is an inaccuracy in the comment with no runtime side effects, not a bug.
- An already open Copilot comment on the PR itself saying that the `MIN_HEIGHT` clamp may bring back the very scrollbar the hook is supposed to remove — in effect it restates the already documented (JSDoc, lines 37-41) deliberate trade-off, merely nitpicking the wording of the function's one-line summary, which does not contain the caveat placed just below it.
- A CodeRabbit remark on this PR about "duplicated gating logic across all four views" — checked with `git grep` for `isMeasured`/`getVirtualItems`/`getTotalSize` in the view files at the head commit: no matches; all of this logic lives exclusively in `useVirtualizedTableBody`. The comment appears to be stale (it refers to an earlier version of the diff, before extraction into the shared hook) and does not point at the current code — worth keeping in mind in case someone wants to "fix" non-existent duplication.

---
Analyzed: 2026-07-24 · commit `038012bb1bb`
