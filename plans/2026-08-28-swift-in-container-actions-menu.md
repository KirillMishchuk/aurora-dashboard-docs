# Plan: Swift in-container actions menu (issue #1196)

**Date:** 2026-08-28 · **Status:** implemented 2026-08-28

## Overview

The Swift objects page (browsing *inside* a container) has no page-level header or actions menu, while the Ceph objects page (inside a bucket) has both. This adds a `ContentHeader` + overflow actions menu to the Swift in-container view, mirroring Ceph's `BucketHeader`/`BucketHeaderActions` position and shape, but containing only the four actions that actually exist for Swift: **Manage Access → Preview and Edit metadata → Empty → Delete**. All four modals already exist and are used by the Swift container *list* page; this change adds only wiring, no modal changes.

---

## Architecture Analysis

**Current state (verified against working tree at `70367891`):**

- Route file: `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/index.tsx`
  - Line 99: `const showContentHeader = provider === "ceph"` → line 103 renders `<BucketHeader bucketName={containerName} />` only for Ceph. Swift renders `<SwiftObjects .../>` with no header at all.
- Ceph pattern (to mirror):
  - `.../storage/-components/Ceph/Buckets/BucketHeader.tsx` — reads `useParams({ from: "/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/" })`, holds a single `activeModal` state of union type `ModalType`, renders `ContentHeader` (`title`, `projectId`, `badges`, `actions`), then `BucketDetailTabs` and `BucketModals`.
  - `.../Ceph/Buckets/BucketHeaderActions.tsx` — pure presentational: `PopupMenu` > `PopupMenuToggle as="div"` > `<Button icon="moreVert" title={t\`Bucket actions\`} />`, then `PopupMenuOptions` with `PopupMenuItem`s calling `onOpenModal(...)`.
  - `.../Ceph/Buckets/BucketModals.tsx` — separate file because it wires **7** modals + toast builders.
- Swift side (already exists, untouched by this task):
  - `.../Swift/Containers/ManageContainerAccessModal.tsx`, `EditContainerMetadataModal.tsx`, `EmptyContainerModal.tsx`, `DeleteContainerModal.tsx`. All take `{ isOpen, container: ContainerSummary | null, onClose, onSuccess?, onError? }`, all early-return `null` when `!isOpen || !container`, and all **self-close** (`mutation.onSettled → handleClose() → onClose()`). Parent `onSuccess` handlers therefore must only fire toasts — they must not call `onClose`.
  - Toast builders: `.../Swift/Containers/ContainerToastNotifications.tsx` (`getContainerAclUpdatedToast`, `getContainerUpdatedToast`, `getContainerEmptiedToast`, `getContainerDeletedToast` + their `…ErrorToast` counterparts). Dispatch idiom used everywhere: `const { message, ...options } = getX(...); toast.success(message, options)`.
  - Row menu precedent (labels/order/testids): `.../Swift/Containers/ContainerTableView.tsx` lines 260–285; it also renders its four modals inline with four `useState`s (no `…Modals.tsx` indirection on the Swift side).
  - `EditContainerMetadataModal` declares `onError` in its props interface but does **not** destructure it (deliberate, per #1191 — errors are shown inline). Passing it is harmless but pointless.

**Key constraint found while verifying (drives the design):** the Swift modals genuinely consume `container.count` / `container.bytes`, unlike Ceph's modals which tolerate a `{ count: 0, bytes: 0 }` placeholder:

- `EmptyContainerModal.tsx:106,110,203-206` — empty/consistency-delay detection and the "N of M objects" hint.
- `DeleteContainerModal.tsx:107` — `hasObjects = actualObjectCount > 0 || container.count > 0`; a fake `count: 0` would let a user delete a container whose listing lags (the exact case this guard exists for). Risk.
- `EditContainerMetadataModal.tsx:473,479` — displays object count and size read-only.

So a **real** `ContainerSummary` must be supplied; a placeholder is not acceptable.

**Proposed changes:**

1. New `ContainerHeaderActions.tsx` (pure, no data, no permission props) + new `ContainerHeader.tsx` (params, data, modal state, toasts), both under `.../Swift/Containers/`.
2. Modal state: one `activeModal` union state in `ContainerHeader.tsx`, modals rendered **inline in the same file** — no `ContainerModals.tsx`. Four modals ≈ 80 lines; the extra file only pays off at Ceph's scale, and `ContainerTableView.tsx` already sets the inline precedent on the Swift side.
3. `ContainerSummary` source: `storage.swift.getContainerMetadata` (one HEAD per container, returns `objectCount`/`bytesUsed`) rather than listing every container in the account — see Step 2. **Decided.**
4. Route file renders `<ContainerHeader containerName={containerName} />` for `swift`, `<BucketHeader .../>` for `ceph`.
5. **No permission gating** — Swift has no `canUser` wiring anywhere (`TODO(perms)` at `.../Swift/Containers/index.tsx:55`); adding gating here would invent a source of truth that doesn't exist.

---

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| Passing a placeholder `ContainerSummary` (Ceph's approach) would make `DeleteContainerModal` treat a non-empty container as empty and `EditContainerMetadataModal` show `0 objects / 0 B` | High | Always pass a real summary built from `getContainerMetadata`; render the actions menu only once that data resolved (`container !== null`) |
| Existing route test `.../objects/index.test.tsx` renders `ObjectsDashboard` for `provider: "swift"` with `@/client/trpcClient` unmocked — a real `ContainerHeader` would throw there | High | Add `vi.mock(".../-components/Swift/Containers/ContainerHeader", () => ({ ContainerHeader: () => null }))` alongside the existing `BucketHeader` mock (line 55) |
| One extra query per objects-page visit | Low | `getContainerMetadata` with input **exactly** `{ project_id, container }` — byte-identical to what `DeleteContainerModal`/`EditContainerMetadataModal`/`ManageContainerAccessModal` already request, so TanStack serves them from one cache entry. Do **not** add `xNewest`/`account` or the key diverges |
| Container inaccessible/deleted (#1142 flow): header query 404s | Medium | `retry: false`, ignore the error; `container` stays `null` → no menu; `SwiftObjects` already toasts + navigates back to the list |
| Delete succeeds while the user is inside the container → page would query a gone container | Medium | In `onSuccess` navigate to `/projects/$projectId/storage/$provider/$storageType` (params from `useParams`), mirroring `BucketModals.handleDeleteBucketSuccess` |
| Menu button flickers in after the metadata query resolves | Low | Accepted (Ceph behaves the same way while permissions/versioning load); alternative is a disabled toggle — call it in review |
| Swift's loading state is `<Stack className="absolute inset-0">` (`Swift/Objects/index.tsx:392-397`) and may overlay the new header while objects load | Low | Manual visual check; if it overlays, that is a follow-up styling fix in `Swift/Objects/index.tsx`, not in the new files |
| New i18n strings uncompiled → `check-i18n` job diff | Low | Run `pnpm --filter @cobaltcore-dev/aurora check-i18n` and include the regenerated `src/locales/{en,de}/messages.{po,ts}` |
| Breaking changes | None | Purely additive; no modal, router, schema or public `AuroraApp` prop changes |

---

## Prerequisites

- [x] ~~Working tree dirty / conflicted file on `kiryl-swift-overflow-menu`~~ — checked after the plan was generated: the working tree is actually clean (`git status` → "nothing to commit, working tree clean"), branch `kiryl-swift-overflow-menu` is up to date with its remote. The agent's observation was stale/transient; no action needed.
- [x] Branch/base: `kiryl-swift-overflow-menu`, in sync with its remote — confirmed.
- [x] All Open Questions resolved (see bottom of file) — `getContainerMetadata`, "Empty Container"/"Delete Container" wording, always-show Empty item, no changeset for now, no badge in this task.

---

## Implementation Steps

### Step 1: Create the presentational actions menu

**Files to create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/ContainerHeaderActions.tsx`

**What to do:**

1. Export the modal union from this file (it is the lowest-level module; defining it here avoids a circular import with `ContainerHeader`):
   ```ts
   export type ContainerModalType = "manageAccess" | "editMetadata" | "emptyContainer" | "deleteContainer"
   ```
2. Props: `{ onOpenModal: (modal: ContainerModalType) => void }` — nothing else. No `can*` props (Swift has no permission source), no versioning/policy props.
3. Structure, copied from `BucketHeaderActions.tsx` lines 67–89:
   - `<PopupMenu>` → `<PopupMenuToggle as="div"><Button icon="moreVert" title={t\`Container actions\`} /></PopupMenuToggle>` → `<PopupMenuOptions>`.
   - `const { t } = useLingui()` from `@lingui/react/macro`.
4. Items, in this exact order, each with a `data-testid` in the style of `ContainerTableView.tsx`:
   1. `label={t\`Manage Access\`}` → `onOpenModal("manageAccess")`, `data-testid="container-actions-manage-access"`
   2. `label={t\`Preview and Edit metadata\`}` → `onOpenModal("editMetadata")`, `data-testid="container-actions-edit-metadata"`
   3. `label={t\`Empty Container\`}` → `onOpenModal("emptyContainer")`, `data-testid="container-actions-empty"`
   4. `label={t\`Delete Container\`}` → `onOpenModal("deleteContainer")`, `data-testid="container-actions-delete"`
   (Wording of items 3–4 decided: Ceph-parity naming, "Empty Container" / "Delete Container", not the row-menu's bare "Empty"/"Delete".)
5. Add a short header comment explaining *why* this menu has no permission props (Swift has no `canUser` wiring; see `TODO(perms)` in `Swift/Containers/index.tsx`) and why nothing is conditionally hidden, so a later reviewer doesn't read it as an oversight.

**Expected outcome:** a self-contained, dependency-free component (no tRPC, no router) that can be unit-tested with just `I18nProvider` + `PortalProvider`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

---

### Step 2: Create the header container component

**Files to create:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/ContainerHeader.tsx`

**What to do:**

1. Props: `{ containerName: string }` (mirrors `BucketHeader`'s `{ bucketName }`).
2. Params — copy `BucketHeader.tsx` lines 26–28 verbatim, only the destructured names change:
   ```ts
   const { projectId, provider, storageType } = useParams({
     from: "/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/",
   })
   ```
   plus `const navigate = useNavigate()` from `@tanstack/react-router`.
3. State: `const [activeModal, setActiveModal] = useState<ContainerModalType | null>(null)`, `const closeModal = () => setActiveModal(null)`.
4. Container summary (recommended source):
   ```ts
   const { data: containerInfo } = trpcReact.storage.swift.getContainerMetadata.useQuery(
     { project_id: projectId, container: containerName },
     { enabled: !!projectId && !!containerName, retry: false }
   )
   const container: ContainerSummary | null = containerInfo
     ? { name: containerName, count: containerInfo.objectCount, bytes: containerInfo.bytesUsed }
     : null
   ```
   - `ContainerSummary` type from `@/server/Storage/types/swift`; `last_modified` is optional and unused by all four modals (verified).
   - Keep the input object exactly `{ project_id, container }` so it shares the cache entry with the modals.
   - Add a comment explaining why a real summary is needed (the `DeleteContainerModal.tsx:107` guard and the read-only count/size fields).
   - (Decided: `getContainerMetadata` is the source, not `listContainers` + find-by-name — no fallback needed.)
5. Render:
   ```tsx
   <ContentHeader
     title={containerName}
     projectId={projectId}
     actions={container ? <ContainerHeaderActions onOpenModal={setActiveModal} /> : null}
   />
   ```
   `ContentHeader` from `@/client/components/ContentHeader/ContentHeader`. **No `badges`** (Swift has no versioning/policy analog) and **no tabs block** (that `-mt-4 mb-8` div in `BucketHeader` exists only for `BucketDetailTabs`).
6. Below the header, render the four modals inline, each `isOpen={activeModal === "…"}`, `container={container}`, `onClose={closeModal}`:
   - `ManageContainerAccessModal` → `onSuccess` fires `getContainerAclUpdatedToast`, `onError` fires `getContainerAclUpdateErrorToast`
   - `EditContainerMetadataModal` → `onSuccess` fires `getContainerUpdatedToast` (skip `onError`; the modal ignores it and shows errors inline — add a one-line comment)
   - `EmptyContainerModal` → `getContainerEmptiedToast(name, deletedCount)` / `getContainerEmptyErrorToast`
   - `DeleteContainerModal` → `getContainerDeletedToast` **plus** navigation:
     ```ts
     const handleDeleteSuccess = (name: string) => {
       const { message, ...options } = getContainerDeletedToast(name)
       toast.success(message, options)
       navigate({
         to: "/projects/$projectId/storage/$provider/$storageType",
         params: { projectId, provider, storageType },
       })
     }
     ```
     and `getContainerDeleteErrorToast` for `onError`.
   - Toast dispatch idiom exactly as in `Swift/Containers/index.tsx:89-122`. **Do not call `closeModal()` from these handlers** — the modals close themselves in `onSettled`.
7. Import `toast` from `@cloudoperators/juno-ui-components`.

**Expected outcome:** `ContainerHeader` renders title + Project ID + divider + overflow menu, and opening any item shows the matching modal populated with real container data.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

---

### Step 3: Wire the header into the objects route

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/index.tsx`

**What to do:**

1. Add `import { ContainerHeader } from "../../../../-components/Swift/Containers/ContainerHeader"` next to the existing `BucketHeader` import (line 10).
2. Replace the `showContentHeader` boolean + line 103 with an explicit per-provider render, e.g.:
   ```tsx
   {provider === "ceph" && <BucketHeader bucketName={containerName} />}
   {provider === "swift" && <ContainerHeader containerName={containerName} />}
   ```
   Keep the `default:` branch of the inner switch untouched (unknown providers still get no header).
3. Update the stale comment at lines 97–98 ("For Swift containers, the component handles its own header") — it is no longer true.

**Expected outcome:** Swift objects pages show the header and menu; Ceph is byte-for-byte unchanged in behavior.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`; manual check per the Testing Plan.

---

### Step 4: Keep the existing route test green

**Files to modify:**

- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/index.test.tsx`

**What to do:**

1. Next to the existing `BucketHeader` mock (lines 55–57), add:
   ```ts
   vi.mock("../../../../-components/Swift/Containers/ContainerHeader", () => ({
     ContainerHeader: () => <div data-testid="swift-container-header" />,
   }))
   ```
   (Using a test id rather than `null` lets you assert the header renders.)
2. Extend the "Objects Route - View Parameter Handling" describe (line 309) with:
   - swift + any view → `swift-container-header` present, Ceph header absent;
   - ceph → the Ceph branch still renders (its `BucketHeader` mock returns `null`, so assert on `ceph-objects` as today plus `queryByTestId("swift-container-header")` being absent).

**Expected outcome:** existing suite passes; provider→header mapping is regression-guarded.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/\$provider/\$storageType/\$containerName/objects/index.test.tsx`

---

### Step 5: Unit-test the actions menu

**Files to create:**

- `.../Swift/Containers/ContainerHeaderActions.test.tsx`

**What to do:**

1. Copy the harness from `.../Ceph/Buckets/BucketHeaderActions.test.tsx` lines 1–40: `I18nProvider` + `PortalProvider` wrapper, `beforeAll(async () => act(() => i18n.activate("en")))`, an `openMenu()` helper clicking `screen.getByRole("button", { name: "Container actions" })`.
2. Tests:
   - toggle button renders with the accessible name "Container actions";
   - after opening, all four labels are present;
   - the four items appear in the agreed order (e.g. map over `screen.getAllByRole("menuitem")`/the rendered option nodes and assert the text sequence — verify which role Juno's `PopupMenuItem` exposes and assert on whatever it actually renders, falling back to the `data-testid`s from Step 1);
   - clicking each item calls `onOpenModal` once with `"manageAccess"` / `"editMetadata"` / `"emptyContainer"` / `"deleteContainer"` respectively.

**Expected outcome:** menu contents, order and payloads are pinned.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Swift/Containers/ContainerHeaderActions.test.tsx`

---

### Step 6: Test the header wiring

**Files to create:**

- `.../Swift/Containers/ContainerHeader.test.tsx`

**What to do:**

1. Mock `@tanstack/react-router` (`useParams` returning `{ projectId, provider: "swift", storageType: "containers" }`, `useNavigate` returning a spy) and `@/client/trpcClient` — copy the module-mock shape from `.../Swift/Containers/index.test.tsx` lines 66–160 (that file is the canonical example of the `trpcReact` mock in this area, including `useUtils`).
2. Mock the four modal modules with lightweight stubs that expose their `isOpen` and the `container` they received, e.g. `ManageContainerAccessModal: (p) => p.isOpen ? <div data-testid="manage-access-modal">{p.container?.name}</div> : null`. This keeps the test about wiring, not about modal internals (which have their own large suites).
3. Also mock `@/client/components/ContentHeader/ContentHeader` (it reads `useRouteContext`/`useMatches` slots) or provide the router mocks it needs — whichever is less brittle; a stub rendering `title` is enough.
4. Tests:
   - no actions menu while `getContainerMetadata` has no data (`data: undefined`);
   - menu renders once metadata resolves; container title shown;
   - clicking each menu item opens the corresponding modal stub, and the stub receives `count`/`bytes` derived from `objectCount`/`bytesUsed` (guards the placeholder regression called out above);
   - `DeleteContainerModal.onSuccess` → `toast.success` called **and** `navigate` called with `to: "/projects/$projectId/storage/$provider/$storageType"` and the three params (invoke the captured prop directly from the stub);
   - `EmptyContainerModal.onSuccess` → `toast.success`, and `navigate` **not** called.
5. Mock `toast` via the `importOriginal` pattern at the top of `Swift/Containers/index.test.tsx` (lines 16–22).

**Expected outcome:** modal routing, data shape and post-delete navigation are covered without duplicating modal tests.

---

### Step 7: i18n + full checks

**What to do:**

1. `pnpm --filter @cobaltcore-dev/aurora check-i18n` — new strings are "Container actions", "Empty Container", "Delete Container"; "Manage Access" and "Preview and Edit metadata" already exist from `ContainerTableView`. Include the regenerated `packages/aurora/src/locales/{en,de}/messages.po` and `messages.ts`.
2. `pnpm --filter @cobaltcore-dev/aurora typecheck && pnpm --filter @cobaltcore-dev/aurora lint && pnpm --filter @cobaltcore-dev/aurora test`, then `pnpm format:check` at the repo root.
3. No `.changeset` entry for now (decided) — revisit at PR time if the maintainers' process requires one.

---

## Testing Plan

**Unit tests:**

- [ ] `ContainerHeaderActions`: toggle has accessible name "Container actions"
- [ ] `ContainerHeaderActions`: all four items render, in the agreed order
- [ ] `ContainerHeaderActions`: each item invokes `onOpenModal` with its own `ContainerModalType`
- [ ] `ContainerHeader`: no menu until the container summary resolves
- [ ] `ContainerHeader`: each menu item opens exactly one modal
- [ ] `ContainerHeader`: modals receive a real `count`/`bytes` (not zeros)
- [ ] `ContainerHeader`: delete success → toast + navigate to the container list; empty success → toast, no navigation
- [ ] Route: swift renders `ContainerHeader`, ceph renders `BucketHeader`, neither leaks into the other

**Integration / manual verification** (dev server, real Swift project):

1. Open a Swift container with objects → header shows the container name, Project ID, and a `⋮` button in the same spot as on a Ceph bucket page.
2. Menu contents/order match: Manage Access, Preview and Edit metadata, Empty…, Delete…
3. Manage Access → change an ACL → save → success toast; reopening shows the new ACL.
4. Preview and Edit metadata → object count and size match the container's real values (**not** 0 / 0 B) → change a metadata key → success toast.
5. Empty → confirm by typing the container name → objects table refreshes to empty on the same page, success toast with the deleted count.
6. Delete on a non-empty container → modal explains it must be emptied first (Close). Empty it, then Delete → confirm with `delete` → redirected to the Swift container list with a success toast, and the container is gone from the list.
7. Ceph bucket page: header, badges, tabs and all seven actions unchanged.
8. Watch the initial page load: confirm the Swift loading spinner (`absolute inset-0`) does not sit on top of the new header; note it if it does.
9. Navigate away and back / switch projects → no stale container data in the header (query-key project isolation).

---

## Acceptance Criteria

- [ ] Swift in-container page renders a `ContentHeader` with the container name and an overflow actions menu positioned as on the Ceph bucket page
- [ ] Menu contains exactly Manage Access, Preview and Edit metadata, Empty, Delete — in that order — and nothing versioning/policy/CORS-related
- [ ] All four items open the existing modals with a real `ContainerSummary` (correct `count`/`bytes`)
- [ ] Successful delete navigates back to the Swift container list; successful empty stays and refreshes the object list
- [ ] Every action produces the same toast as the equivalent action on the container list page
- [ ] No changes to the four modal components, to any router/schema, or to Ceph behavior
- [ ] No permission props/gating introduced for Swift
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test`, `check-i18n` and root `pnpm format:check` all pass

---

## Open Questions — resolved 2026-08-28

1. **`ContainerSummary` source.** Decided: `getContainerMetadata` — one HEAD request per container instead of listing the whole account (which is capped at 10 000 containers — a container beyond that cap would silently yield no menu with the `listContainers` approach), fresher counts, and cache-shared with three of the four modals which already issue that exact query.
2. **Menu wording for items 3–4.** Decided: "Empty Container" / "Delete Container" — Ceph-position parity, accepting a small wording difference from the Swift row menu's bare "Empty"/"Delete".
3. **Conditional hiding.** Decided: always show all four items, matching the current Swift row-menu behavior (`EmptyContainerModal` already handles the already-empty case with its own messaging). No Ceph-style hide-when-`count === 0`.
4. **Changeset / delivery.** Decided: no `.changeset` entry for now — revisit at PR time if needed.
5. **Badges.** Decided: out of scope for this task. A "Public" badge (derived from the read ACL already fetched by `getContainerMetadata`) is a natural follow-up, tracked separately, not part of issue #1196's agreed scope.

---

## Post-implementation review — 2026-09-01

Verified branch `kiryl-swift-overflow-menu` (commits `2646cbc1` "feat(aurora): add swift overflow menu and other small fixes" + merge `862f655a`) against this plan.

**Core plan (Steps 1–3) implemented correctly.** `ContainerHeaderActions.tsx` and `ContainerHeader.tsx` match the plan closely: real `ContainerSummary` via `getContainerMetadata`, no placeholder zeros, correct toast wiring, delete-success navigation, modals self-close (parent never calls `closeModal` from `onSuccess`/`onError`), no permission gating. Route wiring in `objects/index.tsx` matches Step 3, plus an unplanned but harmless `pt-4` padding class on the content wrapper for Swift (spacing polish, not in the plan).

**Checks run 2026-09-01:** `typecheck` ✅, `lint` ✅, `check-i18n` ✅ (no diff), `format:check` ✅, `test` — initially ❌ (1 file / 3 tests failing in `DeleteObjectModal.test.tsx`: a stray backtick corrupting a `getByRole` regex at the old line 408, plus two assertions at old lines 205/213 still matching the pre-rename `/^Delete$/` label). **Fixed 2026-09-01** (test-only edit, not committed): backtick removed, both assertions updated to `/^Delete Object$/`. Full suite now green: 220/220 files, 5524/5524 tests.

**Undocumented scope creep — flagged, not reverted.** Commit `2646cbc1`'s "and other small fixes" renamed labels well outside this plan's scope, and this directly contradicts Open Question #2 above (which explicitly decided to *keep* the Swift row-menu's bare "Empty"/"Delete" wording):

- `DeleteContainerModal`: "Delete" → "Delete Container"
- `ContainerTableView` row menu: "Empty"/"Delete" → "Empty Container"/"Delete Container"
- `CopyObjectModal`: "Copy" → "Copy Object"
- `DeleteObjectModal`: "Delete" → "Delete Object"
- `DeleteObjectsModal`: "Delete" → "Delete Object"/"Delete Objects"
- `MoveRenameObjectModal`: "Move" → "Move/Rename Object"
- `ObjectsTableView` row menu: Download/Edit Metadata/Copy/Move-Rename/Share URL/Delete all gained an "Object" suffix
- `Swift/Objects/index.tsx` toolbar: "Create Folder" moved into a new `⋮` overflow menu; "Upload Object" became the primary button — a toolbar redesign never mentioned in this plan or its acceptance criteria

This is plausibly a reasonable consistency pass across the Swift storage UI, but it was undocumented, contradicts a decision this plan recorded, and is exactly what caused the test breakage above (renames without updating every assertion). **Recommendation for PR time:** either split this out of the Swift-overflow-menu commit into its own clearly-labeled commit/PR, or add an explicit note to the PR description explaining the expanded scope so reviewers aren't comparing it against issue #1196 alone.
