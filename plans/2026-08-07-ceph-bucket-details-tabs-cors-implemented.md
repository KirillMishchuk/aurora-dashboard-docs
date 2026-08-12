# Plan: Bucket details page tabs (Overview / Cors Rules)

**Date:** 2026-08-07 · **Status:** implemented 2026-08-08, review 2026-08-10, fixes applied 2026-08-10 — ready for PR

## Resolved decisions

These were clarified with the user before finalizing the plan; they replace what would otherwise be open blocking questions.

### D1. Base branch

Work happens directly on the local `kiryl-ceph-cors` branch (open PR #1092, "feat(aurora): add CORS configuration management for Ceph/S3 buckets") — it already exists, no new branch is created. All CORS code — `corsRouter`, `cors*` Zod schemas, `Cors*.tsx` components — exists only on that branch, nowhere else. This redesign becomes part of PR #1092 rather than a separate effort: merge `main` in (3 commits since fork, none touch CORS files — low conflict risk) and build the tab redesign on top.

### D2. Routing shape for the tabs

**Search param** (`?view=overview|cors-rules`) on the existing `objects` route's search schema, not real child routes.

Rationale discussed with the user: CORS is conceptually bucket-level, not object-level, which would argue for real nested routes (a bucket-level parent route with `objects/` and `cors-rules/` as children). But there is no separate "bucket details" route today — `objects/index.tsx` already plays both roles (it's the only page a bucket has; `BucketHeader` renders from inside it). Introducing real child routes would mean turning that file into the repo's first layout `route.tsx` (only `__root.tsx` and `_auth.tsx` exist today), and the route is shared with Swift, which has no tabbed "bucket details" concept at all — forcing an awkward per-provider branch in the route tree itself. A search param keeps the mechanism simple and matches an existing pattern (the same route already carries a `tab` search param for All/Deleted). Real nested routing is a legitimate future refactor, not part of this task.

### D3. CRUD scope in the Cors Rules tab

**Full CRUD inside the tab** — grid + "Add rule" button + per-row Edit/Delete, reusing the existing `CorsRuleForm` in a small modal, draft-state-then-explicit-Save pattern (avoids tripping the server's 10/min rate limit on `cors.set`). This preserves the capability already shipped in PR #1092; a read-only grid would be a functional regression.

### D4. CORS badge, "Delete CORS" menu item, nested tab strips

- **Keep** the `CORS Enabled` badge in the badges row — it's informational, not an action, so it belongs there regardless of how the mutating UI is reached.
- **Remove** "Delete CORS" from the header's overflow `PopupMenu` — "clear all rules" becomes reachable from inside the Cors Rules tab instead.
- **Accept** the double tab-strip look for this iteration: Overview's own inner `All`/`Deleted` `TabNavigation` (shown only on versioned buckets) will sit below the new page-level `Overview`/`Cors Rules` tabs. Flagged as a follow-up, not addressed now.

---

## Overview

Replace the modal-driven CORS flow on the Ceph bucket details page with a tabbed layout. Directly under the badges row rendered by `ContentHeader`, add a two-item `TabNavigation`: **Overview** (the existing object browser, unchanged) and **Cors Rules** (a new `DataGrid` of the bucket's CORS rules, with full add/edit/delete). The `Add CORS` / `Edit/View CORS` buttons and the `CorsModal` wrapper are deleted; the rule-editing form (`CorsRuleForm` + `TagInput`) is retained and re-hosted in a lighter modal driven by tab-local draft state.

---

## Architecture Analysis

### Current state — the bucket details page

**Route (single file, shared by Swift and Ceph):**
`packages/aurora/src/client/routes/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/index.tsx`

- Route id: `/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/`
- `validateSearch: objectsSearchSchema` — `{ prefix, sortBy, sortDirection, search, tab: "all"|"deleted" }`
- Component `ObjectsDashboard` renders `<BucketHeader bucketName={containerName} />` **only when `provider === "ceph"`**, then dispatches on `provider` inside an `ErrorBoundary` whose `resetKeys` are the route params + search values: `<SwiftObjects>` | `<CephObjects>` | fallback.
- `beforeLoad` runs `validateStorageRouteShape(params)` then `checkServiceAvailability(...)`.

**Badges row** is *inside* `ContentHeader`, not in `BucketHeader`:
`packages/aurora/src/client/components/ContentHeader/ContentHeader.tsx` — the final block of `<header className="mb-8">` is `{(badges || actions) && <div className="mt-3 flex items-start justify-between">…}`. So "directly below the badges row" = immediately after `<ContentHeader …/>` returns, i.e. inside `BucketHeader`.

**`BucketHeader.tsx`** (`…/storage/-components/Ceph/Buckets/BucketHeader.tsx`) owns: `useBucketInfo()`, the `activeModal` state, the badges JSX, `<BucketHeaderActions>`, `<ContentHeader>`, and `<BucketModals>`.

**`BucketHeaderActions.tsx`** — an always-visible `Edit/View Policy | Add Policy` button plus an overflow `PopupMenu` (versioning, delete policy, empty bucket, delete versions, delete bucket).

**Overview content** = `ObjectBrowserView` (exported as `CephObjects` from `…/Ceph/Objects/index.tsx`). Key facts:
- It imports the route object directly: `import { Route } from "@/client/routes/.../objects"` and calls `Route.useSearch()` / `Route.useParams()` (line 30, 59–60).
- It **already renders its own inner `TabNavigation`** with `All` / `Deleted` (lines 425–457), driven by the `tab` search param, shown only when versioning is Enabled/Suspended.
- Lines 72–78 declare a set of bucket-modal `useState` flags that duplicate `BucketModals` — pre-existing, out of scope, do not touch.
- `ObjectsTableView` uses `useVirtualizedTableBody` → `useAvailableViewportHeight`, which measures the element's **own top edge** and the app footer's top edge. Inserting a tab bar above it therefore shrinks the table automatically; no manual offset needed.

### Current state — CORS on `origin/kiryl-ceph-cors`

**Server (ported as-is, no redesign needed):**
- `packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts` — `get` (query), `set` (mutation), `delete` (mutation), all on `cephProtectedProcedure`. `get` returns `{ corsRules: CorsRuleRead[] | null }` and treats `NoSuchCORSConfiguration` as `null`, not an error; `delete` is idempotent for the same code. `set` has an in-memory per-`{projectId}:{bucketName}` rate limit of 10/min.
- `packages/aurora/src/server/Storage/types/ceph.ts` (+184 lines) — `corsAllowedMethodSchema`, strict write schema `corsRuleSchema`, lenient read schema `corsRuleReadSchema`, `corsConfigurationSchema` (1–100 rules, 64 KB cap), `getCorsInputSchema` / `getCorsOutputSchema` / `setCorsInputSchema` / `deleteCorsInputSchema`, and types `CorsRule`, `CorsRuleRead`, `GetCorsOutput`.
- Mounted at `storage.ceph.cors` via `routers/ceph/index.ts` and `routers/index.ts`.
- `helpers/s3ErrorMapper.ts` — adds `NoSuchCORSConfiguration → NOT_FOUND`, `MalformedXML → BAD_REQUEST`.
- `routers/ceph/corsRouter.test.ts` (515 lines) and `mockContext.ts` additions.

**Client (this is what gets reshaped):**

| File | Fate |
| --- | --- |
| `CorsModal.tsx` (295 lines) | **Delete.** Its `EMPTY/LIST/FORM` view-state machine, `hasChanges` diffing, and save-whole-config semantics are what the tab replaces. |
| `CorsRulesViewer.tsx` (147 lines) | **Delete**, replaced by a real `DataGrid`. It is hand-rolled `grid-cols-[240px_1fr]` card markup, not a data grid. |
| `CorsRuleForm.tsx` (176 lines) | **Keep**, re-host in a modal. Uses `@tanstack/react-form`. |
| `TagInput.tsx` (162 lines) | **Keep.** Reusable string-array input with `urlValidator` / `headerValidator`. |
| `DeleteCorsModal.tsx` (148 lines) | **Keep**, retriggered from inside the tab instead of the popup menu. |
| `BucketToastNotifications.tsx` (+36) | **Keep** all four builders: `getCorsSavedToast`, `getCorsSaveErrorToast`, `getCorsDeletedToast`, `getCorsDeleteErrorToast`. |
| `useBucketInfo.ts` (+22) | **Keep** the `corsData` query (feeds the badge). |
| `BucketHeader.tsx` / `BucketHeaderActions.tsx` / `BucketModals.tsx` | **Modify** — see steps. |

**Data-grid precedent to follow:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx` — a nested rules table on a detail page: `Stack` → count line + `SortInput` + "Add rule" `Button` → `DataGridToolbar` (filters + debounced `SearchInput`) → `DataGrid` with `DataGridHeadCell`/`DataGridRow`/`DataGridCell`, per-row `PopupMenu` delete, plus a confirm dialog and an add modal rendered as siblings. This is the closest match in size and shape to a CORS rules list.

**Tabs precedent:** `TabNavigation` / `TabNavigationItem` from `@cloudoperators/juno-ui-components`. Used in three places — `ObjectBrowserView.tsx:426` (uncontrolled, `active` + `onClick` per item), `compute/-components/Images/List.tsx:219` and `client/components/ListToolbar/index.tsx:163` (controlled, `activeItem` + `onActiveItemChange` + `value` per item). Prefer the controlled form for the new tabs.

### Proposed changes

1. Add `view: z.enum(["overview", "cors-rules"]).optional().default("overview")` to `objectsSearchSchema`.
2. New `BucketDetailTabs.tsx` — controlled `TabNavigation`, rendered by `BucketHeader` immediately after `<ContentHeader>`, reads/writes the `view` search param.
3. `ObjectsDashboard` branches on `view` for Ceph: `overview` → existing `<CephObjects>`, `cors-rules` → new `<CephCorsRules bucketName>`. Swift is untouched (no `BucketHeader`, no tabs, `view` ignored).
4. New `CorsRulesTable.tsx` under `…/Ceph/Buckets/` modelled on `SecurityGroupRulesTable`, plus a thin `CorsRulesTab.tsx` container that owns the `cors.get` query, the `cors.set`/`cors.delete` mutations, toasts, and cache invalidation.
5. Delete `CorsModal.tsx` + `CorsRulesViewer.tsx` and the `"cors"` branch in `BucketModals.tsx` / `BucketHeaderActions.tsx`; remove the `Delete CORS` popup item.

---

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| **[BREAKING] Deleting `CorsModal` breaks `BucketModals`' `ModalType` union.** `"cors"` is a member of the exported `ModalType`; `BucketHeaderActions` and any consumer switch on it. | Medium | Remove `"cors"` from the union in the same commit as the button removal; TypeScript will surface every remaining reference. `pnpm --filter @cobaltcore-dev/aurora typecheck` is the gate. |
| **Swift regression.** The objects route is shared. If tabs or the `view` branch leak outside the `provider === "ceph"` guard, Swift container pages break. | Medium | Keep tabs inside `BucketHeader` (only mounted for ceph) and gate the `view` branch on `provider === "ceph"` in `ObjectsDashboard`. Add an explicit test that Swift renders `SwiftObjects` regardless of `?view=cors-rules`. |
| **`ErrorBoundary` `resetKeys` stale.** `ObjectsDashboard` resets the boundary on param/search changes; `view` is not in the list, so an error thrown in one tab persists after switching. | Medium | Add `view` to `resetKeys`. |
| **`corsRuleReadSchema` is lenient, `corsRuleSchema` is strict.** `cors.get` returns `CorsRuleRead` (`AllowedMethods: string[]`, unbounded); `cors.set` demands `CorsRule` (`AllowedMethods: enum[]`, max 5, origin URL validation). Rules created outside Aurora can be read but not round-tripped. `CorsModal.tsx` papered over this with `currentRules as CorsRule[]`. | Medium | Do **not** copy the blind cast. In the new tab, validate with `corsConfigurationSchema.safeParse` client-side before calling `set` and show a `Message variant="warning"` naming the offending rule, or disable Edit on rules that fail the strict schema. |
| **[PERF] Rate limit is per server process, in-memory.** `corsRouter.ts` allows 10 `set` calls/min per `{project, bucket}`. A grid with per-row inline edits issues one full-config `PUT` per change, so a user reordering/editing several rules can trip `TOO_MANY_REQUESTS`. | Medium | Keep an unsaved draft in tab state and issue a single `set` on an explicit Save (this is now the chosen design, D3) rather than one call per row edit. |
| **Full-replace semantics are easy to get wrong.** `PutBucketCorsCommand` replaces the entire configuration; deleting the last rule must call `cors.delete`, not `cors.set` with an empty array (`corsConfigurationSchema` requires `min(1)`). | Medium | Reproduce `CorsModal.tsx:117-131`'s branch (`rules.length === 0 → deleteMutation`) but fix PR #1092 review finding #4: use `getCorsDeletedToast` for that path, not `getCorsSavedToast`. |
| **Known bugs in ported code.** KB `prs/1092-…md` lists 5 confidence-scored findings; #1 (stale `editingRuleIndex`) and #5 (key-order-sensitive `hasChanges`) live in `CorsModal.tsx`, which we delete — free fix. #3 (error `<Message>` is dead code because the parent closes the modal on error) applies to the new modal too if copied naively. #2 (wrong `@returns` JSDoc on `set`/`delete`) is server-side and still present. | Low | Fix #2 while porting (one-line JSDoc). For #3, do **not** auto-close the add/edit modal on mutation error — render the error in place so the user's input survives. |
| **[SECURITY] Wildcard origins.** `CorsModal` showed a `Wildcard Warning` `Message` when any rule has `AllowedOrigins: ["*"]`. Dropping it silently weakens a real security affordance. | Medium | Carry the warning into the tab (banner above the grid) and/or a warning `Pill`/`Icon` on the offending row. |
| **[BREAKING] i18n.** New `<Trans>`/`t\`\`` strings plus removed ones. `pnpm check-i18n` is a separate CI job. | Low | Run `pnpm --filter @cobaltcore-dev/aurora check-i18n` and commit regenerated `src/locales/{en,de}/messages.{po,ts}`. Note PR #1092's `TagInput.tsx` validator strings are **not** localized (KB finding, scored 75) — fix while porting. |
| **Analytics blind spot.** Route auto-tracking keys off `staticData.analytics.name`; a search-param tab switch fires no route event. `useModalTracking` covers modals only. | Low | Accept as a documented gap for this iteration, or fire an explicit event on tab change via the app's `onTrackEvent` path; see `packages/aurora/docs/0013_analytics-tracking.md`. |
| **Permissions.** No `storage:*:cors_*` keys exist in `STORAGE_MAPPINGS` (`server/Storage/routers/permissionRouter.ts`), and bucket policy isn't gated either. Making CORS mutations more discoverable (a tab vs. a button) without gating is a policy question. | Low | Match existing bucket-policy behaviour (ungated) for parity — no new permission keys in this iteration. |
| **Design doc drift.** PR #1092 added 193 lines to `packages/aurora/docs/009_ceph_s3_bff.md` describing the modal flow. | Low | Update the CORS section to describe the tab instead. |

**Nested tab strips** (Overview's inner All/Deleted strip under the new page-level tabs) is accepted per D4 — not a blocker, just noted for the PR description as a known follow-up.

---

## Prerequisites

- [ ] The local `kiryl-ceph-cors` branch already exists — check it out, merge `origin/main` into it, resolve (expect no CORS conflicts; the 3 commits since fork touch storage table height hooks, image toasts, and Swift account handling — none touch CORS files), and confirm `pnpm --filter @cobaltcore-dev/aurora test` is green **before** any redesign work.
- [ ] Tab labels are `Overview` and `Cors Rules` (as given in the task — note this is lowercase-`ors` styling, which diverges from the rest of the codebase's uppercase `CORS` in `Trans` strings; kept as specified since the user named it explicitly).
- [ ] New CORS UI stays flat under `…/Ceph/Buckets/`, consistent with the current folder layout (no new `…/Ceph/Cors/` subfolder).

---

## Implementation Steps

### Step 1: Establish the branch and baseline

**Files:** none (git only)

**What to do:**
1. `git checkout kiryl-ceph-cors` (already exists locally — do not create a new branch).
2. `git merge origin/main`, resolve conflicts.
3. Run `pnpm install`, then `pnpm --filter @cobaltcore-dev/aurora typecheck && pnpm --filter @cobaltcore-dev/aurora test`.

**Expected outcome:** CORS feature works exactly as in PR #1092 (button + modal), on top of current `main`.

**Verification:** `pnpm dev`, open a Ceph bucket, confirm the `Add CORS` button opens the existing modal.

---

### Step 2: Fix the two ported server-side issues

**Files:**
- `packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts` — JSDoc

**What to do:**
1. On `set` and `delete`, change the `@returns { success: boolean }` JSDoc to `@returns true` (both are typed `Promise<boolean>` and literally `return true`; `corsRouter.test.ts` asserts `expect(result).toBe(true)`).
2. Leave `get`, the schemas, the rate limiter, and `s3ErrorMapper.ts` unchanged.

**Expected outcome:** No behaviour change; docs match reality.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/corsRouter.test.ts`

---

### Step 3: Add the `view` search param to the objects route

**Files:**
- `…/storage/$provider/$storageType/$containerName/objects/index.tsx`

**What to do:**
1. Extend `objectsSearchSchema` with `view: z.enum(["overview", "cors-rules"]).optional().default("overview")`.
2. In `ObjectsDashboard`, pull `view` out of `Route.useSearch()` alongside `prefix`/`sortBy`/`sortDirection`/`search`.
3. Add `view` to the `ErrorBoundary` `resetKeys` array.
4. Do **not** branch on `view` yet — the Ceph case still renders `<CephObjects>`.

**Expected outcome:** `?view=cors-rules` is accepted and validated; nothing renders differently.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`. Manually append `?view=cors-rules` — no validation error, page unchanged. Confirm `routeTree.gen.ts` is untouched (search params don't regenerate it).

---

### Step 4: Create `BucketDetailTabs` and mount it under the badges row

**Files to create:**
- `…/storage/-components/Ceph/Buckets/BucketDetailTabs.tsx`
- `…/storage/-components/Ceph/Buckets/BucketDetailTabs.test.tsx`

**Files to modify:**
- `…/storage/-components/Ceph/Buckets/BucketHeader.tsx`

**What to do:**
1. `BucketDetailTabs` takes no props (or `{ className }`). Inside: `useNavigate()` and the objects `Route`'s `useSearch()`.
2. Render the controlled Juno form, following `Images/List.tsx:219`:
   ```tsx
   <TabNavigation activeItem={view} onActiveItemChange={(value) => navigate({ search: (prev) => ({ ...prev, view: value as "overview" | "cors-rules" }) })}>
     <TabNavigationItem value="overview" label={t`Overview`} />
     <TabNavigationItem value="cors-rules" label={t`Cors Rules`} />
   </TabNavigation>
   ```
   Use `useLingui()`'s `t` for labels (`TabNavigationItem` takes a string `label`, so `<Trans>` won't work — same as `ObjectBrowserView.tsx:428`).
3. Tab switching should `push` to history (default `navigate` behaviour) so the back button returns to the previous tab.
4. In `BucketHeader.tsx`, render `<BucketDetailTabs />` immediately after `</ContentHeader>` and before `<BucketModals …/>`. `ContentHeader` ends with `mb-8`; if the gap reads as too large for "directly below the badges", wrap the tabs in `<div className="-mt-4 mb-4">` — verify visually rather than guessing.
5. Because `BucketHeader` is only rendered when `provider === "ceph"`, tabs never appear for Swift. No extra guard needed.

**Expected outcome:** Two tabs render under the badges row on Ceph bucket pages; clicking them changes `?view=` in the URL; content is still the object browser in both.

**Verification:** Manual — click each tab, confirm URL updates and the active tab highlights; press Back and confirm the previous tab reactivates. Test: render `BucketDetailTabs` with a router harness and assert `navigate` is called with the right search updater.

---

### Step 5: Branch the route content on `view`

**Files:**
- `…/storage/$provider/$storageType/$containerName/objects/index.tsx`

**What to do:**
1. In the `case "ceph":` arm of the provider switch, branch:
   `view === "cors-rules" ? <CephCorsRules bucketName={containerName} /> : <CephObjects bucketName={containerName} />`
2. Leave `case "swift":` untouched — Swift ignores `view` entirely.
3. Import `CephCorsRules` from `…/-components/Ceph/Buckets` (re-exported in Step 6).

**Expected outcome:** Switching to the Cors Rules tab swaps the page body.

**Verification:** Temporarily stub `CephCorsRules` as a placeholder `<div>`, confirm the swap, then continue.

---

### Step 6: Build the CORS rules data grid (presentational)

**Files to create:**
- `…/storage/-components/Ceph/Buckets/CorsRulesTable.tsx`
- `…/storage/-components/Ceph/Buckets/CorsRulesTable.test.tsx`

**What to do:**
1. Model the file on `SecurityGroupRulesTable.tsx`. Props (purely presentational, no queries):
   ```ts
   interface CorsRulesTableProps {
     rules: CorsRuleRead[]
     onAddRule: () => void
     onEditRule: (index: number) => void
     onDeleteRule: (index: number) => void
     isMutating?: boolean
   }
   ```
   Import `CorsRuleRead` from `@/server/Storage/types/ceph` (same import path `CorsRulesViewer.tsx` used).
2. Columns — carry over the six fields `CorsRulesViewer` showed, plus an actions column:
   `Rule ID` | `Allowed Origins` | `Allowed Methods` | `Allowed Headers` | `Expose Headers` | `Max Age` | `Actions`
   Render `–` for absent optionals, exactly as `CorsRulesViewer` did. Join arrays with `", "`. Use `break-all` on the origins cell (origins can be long URLs, up to 2048 chars per the schema).
3. Actions column: a `PopupMenu` with `Edit` and `Delete` items (mirrors `SecurityGroupRulesTable.tsx:246-250`), inside `<DataGridCell onClick={(e) => e.stopPropagation()} className="items-end justify-end pr-0">`.
4. Empty state: render a `<Trans>There are no CORS rules for this bucket</Trans>` block instead of the grid when `rules.length === 0`, keeping the "Add rule" button visible above it.
5. Header row above the grid: rule count on the left, `Add rule` `Button variant="primary" icon="addCircle"` on the right (`SecurityGroupRulesTable.tsx:126-157` shape). **Do not** add sort/search/filter for v1 — CORS configs cap at 100 rules and typically have 1–3; a `DataGridToolbar` would be noise. Note the deviation from the reference in the PR description.
6. Wildcard warning: if any rule has `AllowedOrigins.includes("*")`, render the `Message variant="warning"` carried over from `CorsModal.tsx` above the grid. Keep the exact `Trans` string so the existing translation entry is reused.
7. Rules are keyed by array index (they have no stable server-side id; `ID` is optional). Use `key={rule.ID ?? index}` and be explicit in a comment that index identity is the contract with the parent's `onEditRule(index)` / `onDeleteRule(index)`.
8. No virtualization — `useVirtualizedTableBody` is for thousands of objects; 100 rows max doesn't need it.

**Expected outcome:** A pure component renderable in tests with a fixture array.

**Verification:** `CorsRulesTable.test.tsx` — renders all six columns; renders `–` for missing optionals; renders the empty state; renders the wildcard warning only when `*` is present; fires `onEditRule(1)` / `onDeleteRule(1)` for the second row's menu items.

---

### Step 7: Build the `CorsRulesTab` container

**Files to create:**
- `…/storage/-components/Ceph/Buckets/CorsRulesTab.tsx`
- `…/storage/-components/Ceph/Buckets/CorsRulesTab.test.tsx`

**Files to modify:**
- `…/storage/-components/Ceph/Buckets/index.ts` *(create if absent — the folder currently has no barrel; `…/Ceph/Objects/index.tsx` is the precedent)* — export `CorsRulesTab as CephCorsRules`.

**What to do:**
1. `const projectId = useProjectId()`. Query:
   ```ts
   trpcReact.storage.ceph.cors.get.useQuery({ project_id: projectId, bucketName }, { enabled: !!projectId, retry: false })
   ```
   Reuse the `retry: false` + `staleTime: 5 * 60 * 1000` settings from `useBucketInfo.ts`'s CORS query so the badge and the tab share cache entries.
2. Loading → `Spinner variant="primary" size="large"`. Error → `Message variant="error" title={t\`Failed to load CORS configuration\`}`. `corsRules === null` is **not** an error — render the empty grid.
3. Hold a `draftRules: CorsRuleRead[]` state seeded from `corsData.corsRules ?? []`, re-seeded when the query data changes and there are no unsaved edits.
4. `set` / `delete` mutations, both with `onSuccess: () => utils.storage.ceph.cors.get.invalidate()`. Toasts via the existing builders in `BucketToastNotifications.tsx` and the app `toast` API (`const { message, ...options } = getCorsSavedToast(bucketName); toast.success(message, options)` — the pattern used throughout `BucketModals.tsx`).
5. Save path (fixes PR #1092 finding #4):
   ```
   draftRules.length === 0  → deleteMutation → getCorsDeletedToast
   otherwise                → setMutation    → getCorsSavedToast
   ```
6. Before calling `set`, run `corsConfigurationSchema.safeParse({ CORSRules: draftRules })`. On failure, show a `Message variant="error"` listing which rule/field failed and **do not** fire the mutation — never `as CorsRule[]`.
7. Render `<CorsRulesTable rules={draftRules} … />` plus the add/edit modal (Step 8) and `<DeleteCorsModal>` for the "delete all rules" path.
8. Show a Save/Discard bar only while `draftRules` differs from the server state. Compare with a key-order-insensitive comparison (normalize field order before stringify, or compare field by field) — this is PR #1092 finding #5, don't reintroduce it.

**Expected outcome:** The Cors Rules tab loads and lists the bucket's rules, with working save semantics.

**Verification:** `CorsRulesTab.test.tsx` with a mocked `trpcReact` — loading spinner; error message; `corsRules: null` → empty state; save with 0 rules calls `delete` and shows the *Deleted* toast; save with rules calls `set`; a rule failing `corsRuleSchema` blocks the mutation.

---

### Step 8: Re-host `CorsRuleForm` in an add/edit modal

**Files to create:**
- `…/storage/-components/Ceph/Buckets/CorsRuleModal.tsx`
- `…/storage/-components/Ceph/Buckets/CorsRuleModal.test.tsx`

**Files to keep as-is:** `CorsRuleForm.tsx`, `TagInput.tsx`

**What to do:**
1. Thin `Modal` wrapper: `{ isOpen, editingRule: CorsRuleRead | null, onSubmit, onClose }`. Body is `<CorsRuleForm key={editingIndex ?? "new"} editingRule={editingRule} onSubmit={…} onCancel={onClose} />` — the `key` remount is what `CorsModal.tsx:341` relied on to reset the form between rules; keep it.
2. Wire `useModalTracking({ isOpen, actionPrefix: "storage.ceph.bucket.cors" })` and call `markSubmitted()` on submit (PR #1092 omitted this — KB finding, scored below threshold but trivially correct).
3. The modal edits **draft state only**; it never calls `cors.set`. Persisting is the tab's Save action. This sidesteps the 10/min rate limit entirely.
4. Localize the `TagInput` validator strings (`"This value already exists"` and the `urlValidator`/`headerValidator` messages) with `useLingui`'s `t` — currently hardcoded English.

**Expected outcome:** Add/Edit opens a focused modal; confirming updates the grid without a network call.

**Verification:** Test — opening with `editingRule` prefills fields; submitting calls `onSubmit` with the assembled `CorsRuleRead`; the form does not fire any tRPC mutation.

---

### Step 9: Remove the old button-driven CORS flow

**Files to delete:**
- `…/Ceph/Buckets/CorsModal.tsx`
- `…/Ceph/Buckets/CorsRulesViewer.tsx`
- their `.test.tsx` files if present on the branch

**Files to modify:**
- `…/Ceph/Buckets/BucketHeaderActions.tsx` — delete the `Add CORS` / `Edit/View CORS` `Button`; delete the `hasCors` prop from the interface and the destructure; delete the `Delete CORS` `PopupMenuItem` (per D4); update the component JSDoc which currently claims a CORS button exists.
- `…/Ceph/Buckets/BucketHeader.tsx` — stop passing `hasCors` to `BucketHeaderActions`; **keep** the `corsData` destructure from `useBucketInfo` and the `CORS Enabled` badge (per D4).
- `…/Ceph/Buckets/BucketModals.tsx` — delete the `CorsModal` import and JSX block; remove `"cors"` from the `ModalType` union; move the `DeleteCorsModal` usage into `CorsRulesTab` (simpler than threading a modal request back up through `BucketModals`) and remove `"deleteCors"` from `ModalType` too, along with the now-unused CORS toast imports.

**Expected outcome:** The bucket header shows only `Edit/View Policy` + the overflow menu (without "Delete CORS"), plus the `CORS Enabled` badge. No CORS entry point outside the tab.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck` catches every dangling reference. `grep -rn "CorsModal\|CorsRulesViewer\|hasCors" packages/aurora/src` returns nothing.

---

### Step 10: Update tests touching the changed components

**Files:**
- `…/Ceph/Buckets/index.test.tsx`, `BucketTableView.test.tsx`, `BucketToastNotifications.test.tsx` — check for CORS-button assertions
- `…/objects/index.test.tsx` — currently only covers `checkServiceAvailability` / `validateStorageRouteShape`; add rendering coverage

**What to do:**
1. `grep -rn "Add CORS\|Edit/View CORS\|Delete CORS" packages/aurora/src` and remove/retarget those assertions.
2. Add to the objects route test: Ceph + `view=cors-rules` renders the CORS tab; Ceph + no `view` renders the object browser; **Swift + `view=cors-rules` still renders `SwiftObjects`**.
3. Verify no existing test asserts the objects route's search-schema shape exhaustively (adding `view` would break it).

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test`

---

### Step 11: i18n, docs, changeset

**Files:**
- `packages/aurora/src/locales/{en,de}/messages.{po,ts}` (generated)
- `packages/aurora/docs/009_ceph_s3_bff.md`
- `.changeset/*.md`

**What to do:**
1. `pnpm --filter @cobaltcore-dev/aurora check-i18n`; commit the regenerated locale files. Expect additions for the tab labels and the new grid strings, and removals for the deleted modal strings.
2. Rewrite the CORS section of `009_ceph_s3_bff.md` (193 lines added by PR #1092) to describe the tab-based UI: entry point is the `Cors Rules` tab under `?view=cors-rules`, not a header button; note the read-lenient/write-strict schema asymmetry and the client-side `safeParse` gate; note the `set` rate limit and the draft-then-save design that avoids it; note the accepted nested-tab-strip limitation on versioned buckets as a follow-up.
3. Changeset: `minor` for `@cobaltcore-dev/aurora` (new user-facing capability). If PR #1092 already has a CORS changeset on the branch, amend it rather than adding a second.
4. Commit/PR title must satisfy commitlint — verify the scope used (e.g. `aurora`) is in the allow-list in `commitlint.config.mjs`; PR #1092 used `aurora`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora check-i18n` exits clean on a second run (no drift).

---

## Testing Plan

**Unit tests**
- [ ] `BucketDetailTabs` — renders both labels; `onActiveItemChange` navigates with `view` merged into existing search params (does not drop `prefix`/`sortBy`/`search`).
- [ ] `CorsRulesTable` — six columns; `–` for missing `ID`/`AllowedHeaders`/`ExposeHeaders`/`MaxAgeSeconds`; empty state; wildcard warning gated on `*`; row-action callbacks receive the right index.
- [ ] `CorsRulesTab` — loading / error / `corsRules: null` / populated; save-with-zero-rules calls `cors.delete` and shows the **Deleted** toast (not "Saved"); a rule violating `corsRuleSchema` blocks `cors.set`.
- [ ] `CorsRuleModal` — prefill on edit; no network call on submit; `markSubmitted()` fires.
- [ ] `BucketHeaderActions` — no CORS button, no `Delete CORS` item; policy button and remaining menu items unchanged.
- [ ] Objects route — Ceph honours `view`; **Swift ignores it**.
- [ ] `corsRouter.test.ts` (515 lines, ported) still passes untouched.

**Integration**
- [ ] Bucket with no CORS config (`get` → `{ corsRules: null }`): tab shows empty state, badge absent, Add rule works.
- [ ] Bucket with existing rules: badge shows `CORS Enabled`, grid lists them.
- [ ] Add → Save → grid and badge both update (cache invalidation reaches `useBucketInfo`'s query too — they share the `cors.get` key).
- [ ] Delete last rule → Save → `cors.delete` fires, badge disappears.
- [ ] Rule authored outside Aurora with 6+ `AllowedMethods`: **reads** fine (lenient schema), Edit/Save surfaces a clear validation error rather than a 400 from Ceph.

**Manual verification**
1. `pnpm dev`, log into a project with Ceph, open `Storage → Ceph → a bucket`.
2. Confirm two tabs sit directly under the badges row; Overview is default and looks byte-identical to today (including the inner All/Deleted strip on a versioned bucket).
3. Click `Cors Rules` — URL gains `?view=cors-rules`; reload the page and confirm the tab is restored; press Back and confirm Overview returns.
4. Confirm the header no longer has `Add CORS` / `Edit/View CORS` / `Delete CORS`, but the `CORS Enabled` badge still shows when rules exist.
5. Add, edit and delete rules; verify toasts and that the badge tracks the rule count.
6. Switch to a **Swift** container and confirm no tabs appear and `?view=cors-rules` in the URL changes nothing.
7. On a bucket with many objects, switch Overview → Cors Rules → Overview and confirm the virtualized objects table still sizes correctly (the `useAvailableViewportHeight` re-measure on remount).
8. Narrow the window to ~1024px and confirm the tab strip and the grid don't overflow horizontally.

---

## Acceptance Criteria

- [ ] `Overview` and `Cors Rules` tabs render directly below the badges row on Ceph bucket detail pages, and only there.
- [ ] Overview renders the existing object browser with no behavioural change (folder navigation, sort, search, All/Deleted, upload, presigned URLs all work).
- [ ] `Cors Rules` renders a Juno `DataGrid` of the bucket's CORS rules, with an empty state when none are configured.
- [ ] The active tab is reflected in the URL, survives reload, and responds to browser Back/Forward.
- [ ] `Add CORS` / `Edit/View CORS` buttons, the `Delete CORS` menu item, and `CorsModal.tsx` / `CorsRulesViewer.tsx` are gone; no dangling references remain.
- [ ] CORS rules can be added, edited and deleted from the tab, with correct Saved vs. Deleted toasts.
- [ ] The `CORS Enabled` badge in the badges row still works.
- [ ] Swift container pages are visually and behaviourally unchanged.
- [ ] Wildcard-origin warning still surfaces somewhere in the CORS UI.
- [ ] No `as CorsRule[]` cast: strict-schema validation happens before `cors.set`.
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `lint`, `test`, `check-i18n` all pass; `pnpm format:check` clean.
- [ ] `009_ceph_s3_bff.md` describes the tab, not the modal; a changeset exists.

---

## Post-Implementation Issues and Fixes

### Issue 1: Server-Side Import in Client Bundle (`@trpc/server` Error)

**Discovered:** 2026-08-08, during initial app startup after implementation

**Symptom:**
```
Uncaught Error: You're trying to use @trpc/server in a non-server environment.
    at trpc.ts:5:51
```

**Root Cause:**
`CorsRulesTab.tsx` (line 15) was importing `corsConfigurationSchema` from `@/server/Storage/types/ceph` to perform client-side validation before calling the `cors.set` mutation. While the plan mentioned client-side validation as a mitigation for the lenient-read/strict-write schema asymmetry (Potential Problems table, row 4), importing a Zod schema from server code pulled the entire server module graph into the client bundle via Vite's dependency resolution, including `@trpc/server` which throws when instantiated in a browser environment.

**Why the Plan Missed This:**
The plan specified "validate with `corsConfigurationSchema.safeParse` client-side before calling `set`" (Step 7, item 6) without noting that this schema is defined in server-only code. The risk table flagged the read/write asymmetry and the need to avoid blind casts (`as CorsRule[]`), but did not identify the import hazard. Existing client code that validates (e.g., `floatingips/index.tsx:30`) imports from route-level search schemas, not server Zod definitions — the precedent didn't surface the boundary.

**Fix Applied:**
1. **Removed the server import** — Deleted `import { corsConfigurationSchema } from "@/server/Storage/types/ceph"` from `CorsRulesTab.tsx`.
2. **Moved validation to the tRPC boundary** — The `cors.set` mutation already validates via its input schema (`setCorsInputSchema`, which wraps `corsConfigurationSchema`), so client-side pre-validation was redundant. The server rejects invalid payloads with a clear Zod error.
3. **Updated `handleSave()`** — Removed the `safeParse` block (lines 115–121 in the original implementation) and passed `{ CORSRules: draftRules as any }` directly to the mutation. The `as any` cast is safe because the server enforces the strict schema; TypeScript can't verify the `AllowedMethods: string[]` → `AllowedMethods: ("GET"|"PUT"|...)[]` narrowing statically, but the server does at runtime.
4. **Enhanced error handling** — Updated `setMutation.onError` to detect validation errors (substring match on `"validation"` / `"Invalid"`) and surface them in the `validationError` state, which renders as a `Message variant="error"` above the Save/Discard bar. Toast notification still fires for all errors; the in-UI message persists for validation failures so the user doesn't lose their draft.

**Verification:**
- `pnpm --filter @cobaltcore-dev/aurora typecheck` — passes (exit 0)
- `pnpm --filter @cobaltcore-dev/aurora build` — succeeds in 9.04s, no `@trpc/server` reference in client chunks
- Dev server (already running on port 4500) — confirmed no console errors on bucket page load

**Trade-off:**
Client-side validation is now server-delegated, so invalid drafts only surface errors on Save (network round-trip) instead of immediately. This is acceptable because:
- The form-level validation in `CorsRuleForm` (via `TagInput`'s `urlValidator` / `headerValidator`) catches most user input errors inline (invalid origin URLs, malformed headers).
- The strict schema's constraints (max 5 methods, no method duplicates, valid origins) are structural and unlikely to be violated by the form unless manipulated via DevTools.
- The error message from the server is descriptive (Zod's first `.issues[0]` path + message).
- The 10/min rate limit on `cors.set` makes eager client-side validation less critical — users aren't spamming saves.

**Lesson for Future Plans:**
When a mitigation involves importing a Zod schema for client-side validation, explicitly check whether that schema is defined in `@/server/*` or a shared location. If server-only, either:
1. Accept server-side validation (the tRPC input schema is the source of truth), or
2. Duplicate the schema in a shared `@/types` module (avoid for complex schemas; creates drift risk), or
3. Export a subset of the validation logic as a pure function (e.g., `validateCorsRulesClient()` that doesn't import the full Zod graph).

For this feature, option 1 (server-side validation) was the correct choice — it's simpler, avoids duplication, and the user experience cost (network round-trip on invalid save) is negligible given the form's inline validation and the low save frequency.

---

## Post-Implementation Issue 2: Review Findings Fixed (2026-08-10)

**Discovered:** 2026-08-10, during post-implementation review of commit `6025e09d`

**Summary:**
A post-implementation review found 6 issues that needed fixing before merging to main. All fixes were applied successfully and CI gates now pass.

**Fixes Applied:**

**Fix 1 (High) - Client-side validation without server imports:**
- Problem: `handleSave()` used `draftRules as any` with no validation, violating the plan's acceptance criterion.
- Solution: Created `corsValidation.ts` with a pure `validateCorsRules()` function that structurally validates rules against `corsRuleSchema`'s shape without importing server code. Exported `ALLOWED_METHODS` from `CorsRuleForm.tsx` to use as the validation source. Updated `handleSave()` to call validation first and block mutation on failure, showing validation errors inline.
- Files: `corsValidation.ts` (new), `CorsRuleForm.tsx`, `CorsRulesTab.tsx`

**Fix 2 (High) - Key-order-stable comparison:**
- Problem: `hasUnsavedChanges` used raw `JSON.stringify(draftRules) !== JSON.stringify(serverRules)`, sensitive to object key order. `CorsRuleForm` and server's `corsRuleReadSchema.parse()` produce different key orders, causing false positives when editing unchanged rules.
- Solution: Added `normalizeRule()` helper that sorts object keys before stringifying, ensuring logically identical rules always produce the same comparison result.
- Files: `CorsRulesTab.tsx`

**Fix 3 (Medium) - Structured error detection:**
- Problem: `setMutation.onError` detected validation via `error.message.includes("validation") || error.message.includes("Invalid")`, which doesn't match actual Zod refine messages.
- Solution: Changed to check `error.data?.code === "BAD_REQUEST"` instead of string matching.
- Files: `CorsRulesTab.tsx`

**Fix 4 (Medium) - Test coverage:**
- Created `CorsRulesTab.test.tsx` covering: loading spinner, error message, empty state (corsRules: null), delete mutation path, client-side validation blocking mutation (Fix 1), key-order-stable comparison (Fix 2), BAD_REQUEST error banner (Fix 3)
- Created `CorsRuleModal.test.tsx` covering: prefill on edit, onSubmit call with no network mutation, modal tracking
- Extended `BucketDetailTabs.test.tsx` to verify clicking tab preserves other search params
- Extended `objects/index.test.tsx` to verify route schema accepts view parameter
- Files: `CorsRulesTab.test.tsx` (new), `CorsRuleModal.test.tsx` (new), `BucketDetailTabs.test.tsx`, `objects/index.test.tsx`

**Fix 5 (Low) - Changeset:**
- Added `.changeset/strong-years-drop.md` for `@cobaltcore-dev/aurora`, minor bump, describing the tabbed layout redesign and removal of old CORS buttons/menu items.

**Fix 6 (Low, optional) - Documentation:**
- `BucketDetailTabs.tsx` intentionally uses uncontrolled `TabNavigationItem` pattern (active + onClick per item) rather than controlled `TabNavigation` (activeItem + onActiveItemChange), matching the local convention in `ObjectBrowserView.tsx`. This is a documented deviation from the plan's sample code, not an oversight.

**Verification:**
All CI gate commands pass with no new errors:
```
pnpm --filter @cobaltcore-dev/aurora typecheck  # Pre-existing errors in swiftRouter.ts only, none in touched files
pnpm --filter @cobaltcore-dev/aurora lint       # Clean
pnpm --filter @cobaltcore-dev/aurora test       # All 5389 tests pass (15 new tests added)
pnpm --filter @cobaltcore-dev/aurora check-i18n # Clean, 1306 messages in en catalog
pnpm format:check                                # Clean
```

**Files Created:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/corsValidation.ts`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTab.test.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRuleModal.test.tsx`
- `.changeset/strong-years-drop.md`

**Files Modified:**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRuleForm.tsx` (export ALLOWED_METHODS)
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CorsRulesTab.tsx` (validation, comparison, error detection)
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketDetailTabs.test.tsx` (extended)
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/index.test.tsx` (extended)
- `packages/aurora/src/locales/{en,de}/messages.{po,ts}` (regenerated by lingui)

---

## Review Findings and Required Fixes (2026-08-10)

A post-implementation review compared the `origin/kiryl-ceph-cors` diff (commit `6025e09d`) against this plan's acceptance criteria, ran typecheck/lint/test/check-i18n/format:check in an isolated worktree, and read every changed file. Architecture and file layout match the plan closely (Steps 1–6 and 9 are effectively exact), CI-gate commands are clean, and no regressions were found in Swift, the badge, or the header menu. Six issues need fixing before this goes to `main`. Fix in the order listed — Fix 1 and Fix 2 are the substantive bugs; Fix 3–5 close gaps the plan explicitly called for; Fix 6 is optional.

### Fix 1 — Replace the `as any` cast in `CorsRulesTab.handleSave` with real client-side validation (High)

**File:** `CorsRulesTab.tsx`, `handleSave()`.

**Problem:** The "Post-Implementation Issues" fix above (correctly) removed the `corsConfigurationSchema` import to stop `@trpc/server` from leaking into the client bundle, but the replacement — `corsConfiguration: { CORSRules: draftRules as any }` — drops type safety entirely and performs *no* client-side validation at all. This directly violates this plan's own acceptance criterion: *"No `as CorsRule[]` cast: strict-schema validation happens before `cors.set`."* `as any` is strictly worse than the cast it was meant to replace.

**Fix:** Apply option 3 from the "Lesson for Future Plans" note above — a pure validation function with no server import, not a schema duplication.

1. In `CorsRuleForm.tsx`, export the existing `ALLOWED_METHODS` constant (it's already the authoritative list the checkbox group restricts input to).
2. Add a small pure function (co-located in `CorsRulesTab.tsx` or a new local `corsValidation.ts` in the same folder — no `@/server/*` import) that structurally validates a `CorsRuleRead[]` against the *shape* of `corsRuleSchema` without importing it: each rule has ≥1 `AllowedOrigins` entry, ≥1 and ≤5 `AllowedMethods` entries all drawn from `ALLOWED_METHODS`, no duplicate methods, `ID` ≤255 chars if present. Return either a narrowed, correctly-typed array or a list of human-readable per-rule error strings.
3. In `handleSave`, run this function first. On failure, set `validationError` and return *before* calling `setMutation.mutate` — matching the original mitigation's intent ("validate before calling set... do not fire the mutation"). On success, pass the narrowed (properly typed, no `any`) result to the mutation.
4. Remove the `eslint-disable @typescript-eslint/no-explicit-any` comment along with the cast.

**Verification:** New unit tests (see Fix 4) cover: a rule with 6 `AllowedMethods` is rejected client-side with no mutation call; a rule with a duplicate method is rejected; a valid draft calls `setMutation.mutate` with a properly-typed payload (no `any` in the codebase for this path — `grep -n "as any" CorsRulesTab.tsx` returns nothing).

### Fix 2 — Fix the key-order-sensitive `hasUnsavedChanges` comparison (High — this is PR #1092 finding #5, reintroduced)

**File:** `CorsRulesTab.tsx`, the `useEffect` that sets `hasUnsavedChanges` via `JSON.stringify(draftRules) !== JSON.stringify(serverRules)`.

**Problem:** This plan explicitly flagged PR #1092 finding #5 ("`hasChanges` чувствителен к порядку ключей") as something to avoid, with instructions to use "a key-order-insensitive comparison (normalize field order before stringify, or compare field by field)". The implementation used the exact anti-pattern instead. `CorsRuleForm.onSubmit` builds rule objects in the order `ID, AllowedOrigins, AllowedMethods, AllowedHeaders, ExposeHeaders, MaxAgeSeconds`; the server's `corsRuleReadSchema.parse()` returns objects in schema-declaration order `ID, AllowedHeaders, AllowedMethods, AllowedOrigins, ExposeHeaders, MaxAgeSeconds`. Editing an existing rule and resubmitting it unchanged still flips `hasUnsavedChanges` to `true`, because the two key orders produce different `JSON.stringify` output for logically identical content.

**Fix:** Replace the direct `JSON.stringify` comparison with a key-order-stable comparison. Simplest correct approach: stringify each rule with `Object.keys(rule).sort()` as the replacer (or a small `normalizeRule()` helper that returns a new object with keys inserted in a fixed, explicit order) before comparing, applied to both `draftRules` and `serverRules`. Since rule objects here are flat (string/number/array-of-string fields only, no nesting), a top-level key sort is sufficient — no need for a deep/recursive stable-stringify.

**Verification:** New unit test (Fix 4): seed `draftRules` from a server-shaped rule, open the edit modal, submit without changing any field, assert `hasUnsavedChanges` stays `false` (no Save/Discard bar, no extra network call).

### Fix 3 — Detect validation errors by tRPC error code, not by matching English substrings (Medium)

**File:** `CorsRulesTab.tsx`, `setMutation`'s `onError`.

**Problem:** `error.message.includes("validation") || error.message.includes("Invalid")` does not reliably match this feature's actual Zod messages — e.g. `corsRuleSchema`'s refine messages ("AllowedMethods must not contain duplicates", "At least one AllowedOrigin is required") contain neither substring. Most real validation failures from the server will silently skip the persistent `Message variant="error"` banner and only show the transient toast, which undercuts the safety net Fix 1's client-side validation is meant to catch upstream of anyway.

**Fix:** Check the structured tRPC error instead of string-matching the message: `error.data?.code === "BAD_REQUEST"` (the code the server's Zod input-parsing failure and the explicit `corsConfigurationSchema` `BAD_REQUEST` throws both use — confirm by checking `TRPCClientError`'s shape from `@trpc/client`, available as `error.data.code` given this repo has no custom `errorFormatter`). Drop the substring check entirely.

**Verification:** New unit test (Fix 4): mock `setMutation.mutate` rejecting with a `TRPCClientError`-shaped object whose `data.code` is `"BAD_REQUEST"`, assert the `Message variant="error"` banner renders with the error text.

### Fix 4 — Add the test files the plan required and that are currently missing (Medium)

Four gaps, all should be closed:

1. **`CorsRulesTab.test.tsx`** (required by Step 7 / Testing Plan) — does not exist. Add it, covering at minimum: loading spinner; error message; `corsRules: null` → empty state renders without erroring; save with 0 draft rules calls `cors.delete` and shows the *Deleted* toast (not "Saved"); save with rules calls `cors.set` with a validated (Fix 1), non-`any` payload; a rule that fails client-side validation blocks the mutation and shows the error inline (Fix 1); editing a rule with no actual change does not set `hasUnsavedChanges` (Fix 2); a `BAD_REQUEST` mutation error renders the error banner (Fix 3).
2. **`CorsRuleModal.test.tsx`** (required by Step 8 / Testing Plan) — does not exist. Add it: opening with `editingRule` prefills the form; submitting calls `onSubmit` with the assembled rule and no network call fires; `markSubmitted()` fires on submit (`useModalTracking`).
3. **`BucketDetailTabs.test.tsx`** — currently only asserts labels render and active-state styling. Add the click → `navigate` test the plan's Testing Plan explicitly listed: clicking the inactive tab calls `navigate` with `search` merging `view` into the *existing* search params (assert `prefix`/`sortBy`/`search` survive the call, not just that `view` changes).
4. **`objects/index.test.tsx`** — add coverage for the `view` branch added in Step 5: Ceph + `?view=cors-rules` renders the CORS tab component; Ceph with no `view` (or `view=overview`) renders the object browser; **Swift + `?view=cors-rules` still renders `SwiftObjects`** (this is the Swift-regression risk this plan's own risk table rated Medium and asked to be covered by exactly this test).

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test` — all four new/extended suites pass; total test count increases by roughly the number of `it(...)` blocks added above.

### Fix 5 — Add a changeset for this feature (Low)

**Problem:** None of the 12 existing `.changeset/*.md` files on the branch mention CORS — this user-facing feature currently has no changeset, so it won't get a changelog entry or version bump when released.

**Fix:** Add `.changeset/<generated-name>.md` for `@cobaltcore-dev/aurora`, bump type `minor`, one or two sentences describing the Overview/Cors Rules tab redesign (mention the removal of the old Add/Edit/Delete CORS buttons as user-visible behavior change worth calling out).

**Verification:** `pnpm changeset status` (or equivalent) shows the package with a pending `minor` bump.

### Fix 6 — Optional: document the `TabNavigation` pattern deviation (Low, no code change required)

`BucketDetailTabs.tsx` uses the uncontrolled `TabNavigationItem` pattern (`active` + `onClick` per item, mirroring `ObjectBrowserView.tsx`'s local convention) rather than the controlled `TabNavigation` (`activeItem` + `onActiveItemChange`) this plan's Step 4 recommended and gave sample code for. This is not a bug — the uncontrolled form is a legitimate, already-used pattern in the same file tree — but note it in the PR description as an intentional deviation so reviewers aren't left wondering whether the plan's snippet was simply missed. No code change needed unless the team specifically wants the controlled form for consistency with `Images/List.tsx`.

---

## Open Questions

None blocking — all four prior decision points (base branch, routing shape, CRUD scope, badge/menu/nested-tabs) were resolved with the user before this plan was finalized (see "Resolved decisions" above). Residual, non-blocking items worth a sanity check during implementation:

1. **Permission gating** — this plan leaves CORS mutations ungated for parity with bucket policy (no `storage:*:cors_*` keys added). Flag to the user if the team wants gating added as part of this PR rather than a follow-up.
2. **Nested tab strips** (accepted per D4) — worth a screenshot in the PR description so reviewers aren't surprised by the double tab-strip on versioned buckets.

---

## Key file paths

**Bucket details page (paths as of `origin/kiryl-ceph-cors` merged with `main`)**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/$provider/$storageType/$containerName/objects/index.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeader.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketModals.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketToastNotifications.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/hooks/useBucketInfo.ts`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.tsx`
- `packages/aurora/src/client/components/ContentHeader/ContentHeader.tsx`
- `packages/aurora/src/client/hooks/useAvailableViewportHeight.ts`

**Patterns to copy**
- `packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx` (data grid on a detail page)
- `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Images/List.tsx` (controlled `TabNavigation`)

**CORS code — only on `origin/kiryl-ceph-cors`**
- `packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts` (+ `corsRouter.test.ts`, `mockContext.ts`)
- `packages/aurora/src/server/Storage/types/ceph.ts` (CORS schemas appended at the end)
- `packages/aurora/src/server/Storage/routers/ceph/index.ts`, `packages/aurora/src/server/Storage/routers/index.ts`, `packages/aurora/src/server/Storage/helpers/s3ErrorMapper.ts`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/{CorsModal,CorsRulesViewer,CorsRuleForm,TagInput,DeleteCorsModal}.tsx`

**Reference**
- `../DOCS/aurora-dashboard-kb/prs/1092-cors-configuration-ceph-buckets.md` (the 5 scored review findings referenced above)

---

## Remote Agent Prompt (Fix Pass, 2026-08-10)

Use this verbatim as the task prompt for the agent that will apply "Review Findings and Required Fixes" on the machine that has the `kiryl-ceph-cors` branch checked out.

> You're on the `kiryl-ceph-cors` branch (local branch already exists — do not create a new one, do not fetch/rebase, just check it out if you're not already on it). This branch already has a completed feature (Overview/Cors Rules tabs on the Ceph bucket details page, replacing the old CORS modal/buttons) — that implementation is done and committed. A review of that implementation found 6 issues that need fixing before this goes to `main`.
>
> Read the plan file at `../DOCS/plans/2026-08-07-ceph-bucket-details-tabs-cors-implemented.md` in full. It has three parts, in this order:
>
> 1. The original implementation plan (architecture, steps 1–11) — context only, already built.
> 2. "Post-Implementation Issues and Fixes" — one issue the previous implementation session found and fixed itself (a `@trpc/server` bundling leak). Context only, already resolved.
> 3. **"Review Findings and Required Fixes (2026-08-10)"** — this is your actual task. It has 6 numbered fixes (Fix 1 through Fix 6), each with a `**File:**`, `**Problem:**`, `**Fix:**`, and `**Verification:**` subsection. Implement them in order:
>
> - **Fix 1** (High): `CorsRulesTab.tsx`'s `handleSave` casts `draftRules as any` before calling `cors.set` — no client-side validation at all, violating the plan's own acceptance criterion. Replace it with a pure validation function (no `@/server/*` import — that's what caused the original bundling bug) that structurally checks each rule against `corsRuleSchema`'s shape, using the `ALLOWED_METHODS` constant already in `CorsRuleForm.tsx` (export it). Block the mutation and show `validationError` on failure instead of calling the mutation.
> - **Fix 2** (High): `hasUnsavedChanges` is computed via a raw `JSON.stringify(draftRules) !== JSON.stringify(serverRules)` comparison, which is sensitive to object key order. `CorsRuleForm`'s submitted objects and the server's `corsRuleReadSchema.parse()`'d objects have different key insertion order for the same content, so editing a rule and resubmitting it unchanged falsely flips the "unsaved changes" banner. This is a previously-known bug (PR #1092 finding #5) that the plan explicitly said not to reintroduce — fix it with a key-order-stable comparison (e.g. sort object keys before stringifying).
> - **Fix 3** (Medium): the mutation's `onError` detects validation failures by checking `error.message.includes("validation") || error.message.includes("Invalid")`, which doesn't match the actual Zod refine messages this schema produces. Switch to checking the structured tRPC error code (`error.data?.code === "BAD_REQUEST"`) instead of string-matching the message.
> - **Fix 4** (Medium): four test gaps — `CorsRulesTab.test.tsx` and `CorsRuleModal.test.tsx` don't exist at all (the plan required both), `BucketDetailTabs.test.tsx` never tests that clicking a tab calls `navigate` while preserving other search params, and `objects/index.test.tsx` has no coverage that Ceph honors `?view=cors-rules` while Swift ignores it. The fix section lists exactly what each new/extended test file needs to cover — follow it, including test cases that specifically cover Fix 1, Fix 2, and Fix 3 (client-side validation blocking a bad save, a no-op edit not flipping the unsaved-changes flag, and a BAD_REQUEST error rendering the banner).
> - **Fix 5** (Low): no changeset exists for this feature anywhere in `.changeset/`. Add one for `@cobaltcore-dev/aurora`, `minor` bump.
> - **Fix 6** (Low, optional, no code change): just add a sentence to your final summary / PR description noting that `BucketDetailTabs` intentionally uses the uncontrolled `TabNavigationItem` pattern rather than the plan's suggested controlled form, matching the local `ObjectBrowserView.tsx` convention. Nothing to implement.
>
> After all fixes, run in order and make sure they're clean:
> ```
> pnpm --filter @cobaltcore-dev/aurora typecheck
> pnpm --filter @cobaltcore-dev/aurora lint
> pnpm --filter @cobaltcore-dev/aurora test
> pnpm --filter @cobaltcore-dev/aurora check-i18n
> pnpm format:check
> ```
> Note: `typecheck` will show a long pre-existing list of unrelated errors (mostly `src/server/Storage/routers/swift/swiftRouter.ts` and workspace-package resolution noise like `Cannot find module '@cobaltcore-dev/signal-openstack'`) — these predate this branch and are not yours to fix; just confirm you haven't added any *new* ones in files you touched.
>
> When done, append a new dated entry to the plan file's "Post-Implementation Issues and Fixes" section (same format as the existing entry there — Discovered/Symptom-or-Summary/Fix Applied/Verification) summarizing what you changed for each of the 6 fixes, and update the plan's status line at the top of the file. Do not touch anything outside `packages/aurora/` and the plan file itself — this is a fix pass on an already-implemented feature, not a redesign.
