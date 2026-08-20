---

description: "Task list template for feature implementation"
---

# Tasks: Ceph Bucket Lifecycle Rules

**Input**: Design documents from `/specs/001-bucket-lifecycle-rules/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/lifecycle-trpc-contract.md, quickstart.md

**Tests**: Included — Constitution Principle III (Test & CI Parity) and `plan.md`'s Testing section explicitly
require colocated `*.test.ts(x)` for the new router and client components, mirroring
`bucketPolicyRouter.test.ts` / `BucketPolicyModal.test.tsx`.

**Organization**: Tasks are grouped by user story (US1 = View, US2 = Create, US3 = Edit/Delete) to enable
independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths are exact, relative to repository root

## Path Conventions

Single package (`packages/aurora`), per `plan.md`'s Project Structure:
- Server: `packages/aurora/src/server/Storage/`
- Client: `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm conventions from the closest analogues before writing new code — no new tooling/deps
needed (`@aws-sdk/client-s3` and all client libs are already present per `plan.md`).

- [ ] T001 Read `packages/aurora/src/server/Storage/routers/ceph/bucketPolicyRouter.ts`,
      `versioningRouter.ts`, and `packages/aurora/src/server/Storage/types/versioning.ts` to confirm the
      exact `cephProtectedProcedure` / `mapS3ErrorToTRPCError` / `ctx.getCephClient()` call shape to mirror
      (research.md §1, §2)
- [ ] T002 Read `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketPolicyModal.tsx`,
      `DeleteBucketPolicyModal.tsx`, `BucketHeaderActions.tsx`, `BucketModals.tsx`, and
      `Ceph/Objects/ObjectVersionHistoryModal.tsx` to confirm the modal-dispatch, `DataGrid` list, and
      `@tanstack/react-form` patterns to mirror (research.md §6)

**Checkpoint**: Patterns confirmed — proceed to Foundational phase.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared Zod schemas, server-side SDK mapping helpers, and the tRPC sub-router shell that every
user story's procedures and UI depend on. No user story can be implemented until this phase is complete.

**⚠️ CRITICAL**: All three user stories call `lifecycle.get`/`lifecycle.set`/`lifecycle.delete` — none of
those procedures can exist without this phase.

- [ ] T003 Create `packages/aurora/src/server/Storage/types/lifecycle.ts` with `transitionActionSchema`,
      `dayCountActionSchema`, `lifecycleRuleSchema` (with the "at least one action" `.refine`),
      `getLifecycleInputSchema`, `setLifecycleInputSchema`, `deleteLifecycleInputSchema`, and the
      `LifecycleRule`/`LifecycleConfiguration` TS types, per `data-model.md`'s Zod schema sketch
- [ ] T004 [P] Add `toSdkLifecycleRule` (app `LifecycleRule` → SDK `LifecycleRule`, preserving
      `unsupportedFilter` passthrough per FR-013) and `fromSdkLifecycleRule` (inverse mapping) helper
      functions, colocated in `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts` (created
      in T005), per `research.md` §2 and `data-model.md`
- [ ] T005 Create `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts` exporting an empty
      `lifecycleRouter` shell (procedures added per-story below), built with `cephProtectedProcedure`,
      mirroring `bucketPolicyRouter.ts`'s file structure and imports (depends on T003, T004)
- [ ] T006 Export the new router from `packages/aurora/src/server/Storage/routers/ceph/index.ts`
      (`export { lifecycleRouter } from "./lifecycleRouter"`) (depends on T005)
- [ ] T007 Mount `lifecycle: auroraRouter({...lifecycleRouter})` under `storage.ceph` in
      `packages/aurora/src/server/Storage/routers/index.ts` (`buildObjectStorageRouters`), alongside the
      existing `bucketPolicy`/`versioning` mounts (depends on T006)
- [ ] T008 [P] Add the storage-class configuration read (research.md §4: server-configured list, e.g.
      `CEPH_LIFECYCLE_STORAGE_CLASSES` env var) surfaced as a field on `lifecycle.get`'s output or a small
      dedicated config-read value consumed by the router, wired into `lifecycleRouter.ts` (depends on T005)

**Checkpoint**: Schemas, router shell, and mount point exist — user story implementation can now begin.

---

## Phase 3: User Story 1 - View a bucket's lifecycle rules (Priority: P1) 🎯 MVP

**Goal**: A user opens a bucket's lifecycle view and sees all configured rules (including externally-created
ones) accurately, or a clear empty state if none exist.

**Independent Test**: Open a bucket with a lifecycle configuration set via an external tool and confirm every
rule and its details display correctly; open a bucket with none and confirm the empty state.

### Tests for User Story 1

- [ ] T009 [P] [US1] Server test in
      `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.test.ts`: `lifecycle.get` returns
      mapped rules from a mocked `GetBucketLifecycleConfigurationCommand` response (multi-action rule,
      `unsupportedFilter` passthrough fields preserved), and returns `{ rules: [] }` (not an error) when the
      mocked SDK call throws `NoSuchLifecycleConfiguration` — reuse `routers/ceph/mockContext.ts` and
      `createCallerFactory`, mirroring `bucketPolicyRouter.test.ts` structure (FR-001, FR-002, FR-003)
- [ ] T010 [P] [US1] Client test in
      `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/LifecycleRulesModal.test.tsx`:
      renders rule list (name, status, prefix, actions) from a mocked `trpcReact.storage.ceph.lifecycle.get`
      query, and renders the empty state when the mocked query returns `{ rules: [] }` — mirror
      `BucketPolicyModal.test.tsx` mocking approach, wrapped in `I18nProvider`/`PortalProvider`

### Implementation for User Story 1

- [ ] T011 [US1] Implement `lifecycle.get` query procedure in
      `packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.ts`: `getLifecycleInputSchema` input,
      `storage:containers:read` permission, calls `GetBucketLifecycleConfigurationCommand` via
      `ctx.getCephClient()`, maps `NoSuchLifecycleConfiguration` to `{ rules: [] }`, maps other errors via
      `mapS3ErrorToTRPCError`, uses `fromSdkLifecycleRule` from T004 (depends on T005; makes T009 pass)
- [ ] T012 [US1] Create `LifecycleRulesModal.tsx` in
      `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/`:
      calls `trpcReact.storage.ceph.lifecycle.get.useQuery(...)`, renders a `DataGrid` of rules (name,
      status, prefix/scope, actions summary) with a per-row `PopupMenu` (Edit/Delete stubs wired in US2/US3),
      and an empty state when `rules` is `[]`, modeled on `ObjectVersionHistoryModal.tsx`'s table (depends
      on T011; makes T010 pass)
- [ ] T013 [US1] Add a "Lifecycle Rules" entry to `BucketHeaderActions.tsx`'s action menu (existing file,
      edited) that sets `activeModal: "lifecycle"`
- [ ] T014 [US1] Add `"lifecycle"` to the `ModalType` union and mount `LifecycleRulesModal` in
      `BucketModals.tsx` (existing file, edited), same dispatch pattern as `"policy"`/`"enableVersioning"`
      (depends on T012, T013)

**Checkpoint**: User Story 1 fully functional — users can view lifecycle rules (own and externally-created)
and see the empty state. Independently testable and demoable.

---

## Phase 4: User Story 2 - Create a lifecycle rule (Priority: P2)

**Goal**: A user adds a new rule (prefix scope, one or more actions) and it's saved and appears in the list.

**Independent Test**: Create a rule with an expiration action on a test bucket, save it, and confirm it
appears correctly in the rule list (US1) and is applied by the storage backend.

### Tests for User Story 2

- [ ] T015 [P] [US2] Server test in `lifecycleRouter.test.ts`: `lifecycle.set` maps a full rule array
      (expiration, transition, noncurrent-version actions, multipart-abort) to the SDK shape and calls
      `PutBucketLifecycleConfigurationCommand`; rejects (schema-level) a rule with zero actions and a rule
      with a non-positive day count; propagates S3 rejection (e.g. simulated rule-count-limit error) via
      `mapS3ErrorToTRPCError` without treating it as success (FR-005–FR-010, FR-015, Edge Cases)
- [ ] T016 [P] [US2] Client test in `LifecycleRuleFormModal.test.tsx` (new file, same directory as T012):
      form renders name/prefix/status/action fields; submit blocked with an explanatory message when no
      action is selected (FR-009); duplicate rule name (against the currently-loaded rule list) is rejected
      client-side before any mutation call (FR-004, research.md §3); non-positive day-count input is
      rejected (FR-010); transition action is disabled with "unavailable" messaging when the configured
      storage-class list is empty (FR-006, Acceptance Scenario 2.4)

### Implementation for User Story 2

- [ ] T017 [US2] Implement `lifecycle.set` mutation procedure in `lifecycleRouter.ts`:
      `setLifecycleInputSchema` input, `storage:containers:update` permission, maps each rule via
      `toSdkLifecycleRule`, hard-cap re-validation (e.g. 1000 rules) as defense-in-depth per contract, calls
      `PutBucketLifecycleConfigurationCommand`, maps errors via `mapS3ErrorToTRPCError` (depends on T005;
      makes T015 pass)
- [ ] T018 [US2] Create `LifecycleRuleFormModal.tsx` in the `Buckets/` client folder: single component for
      add (no `existingRule` prop) driven by `@tanstack/react-form` + a Zod `formSchema` — fields for name,
      status, prefix, expiration (days), transition (days + storage class dropdown, disabled when no classes
      configured), noncurrent-version expiration/transition, multipart-abort (days); client-side "at least
      one action" and duplicate-name validation against the `lifecycle.get` cache; modeled on
      `BucketPolicyModal.tsx`'s form usage (depends on T017; makes T016 pass)
- [ ] T019 [US2] On successful `lifecycle.set` submit in `LifecycleRuleFormModal.tsx`: compute the full
      desired `rules` array (existing rules from the `lifecycle.get` cache plus the new rule), call
      `lifecycle.set`, invalidate `utils.storage.ceph.lifecycle.get`, and surface a success/error toast via
      `BucketToastNotifications.tsx` helpers, per the contract's "Client consumption contract" (depends on
      T018)
- [ ] T020 [US2] Wire an "Add rule" trigger button in `LifecycleRulesModal.tsx` (from US1) that opens
      `LifecycleRuleFormModal` in create mode (depends on T012, T018)
- [ ] T021 [US2] Add all new UI strings via `<Trans>`/`t` macro (`@lingui/react/macro`) in
      `LifecycleRuleFormModal.tsx` and `LifecycleRulesModal.tsx`'s add-trigger, and run `pnpm check-i18n` to
      confirm extraction (depends on T018, T020)

**Checkpoint**: User Stories 1 AND 2 both work independently — users can view and create lifecycle rules.

---

## Phase 5: User Story 3 - Edit and delete existing lifecycle rules (Priority: P3)

**Goal**: A user edits an existing rule's status/scope/actions or deletes a rule (with confirmation), without
corrupting fields the UI doesn't render controls for (e.g. externally-set tag filters).

**Independent Test**: Edit a previously created rule's expiration period and confirm the change is reflected;
separately, delete a rule and confirm it's removed from the list (and confirmation is required first).

### Tests for User Story 3

- [ ] T022 [P] [US3] Server test in `lifecycleRouter.test.ts`: `lifecycle.delete` calls
      `DeleteBucketLifecycleCommand` and treats a mocked `NoSuchLifecycleConfiguration` response as success,
      not an error, mirroring `bucketPolicy.delete`'s idempotency (contract's `lifecycle.delete` section)
- [ ] T023 [P] [US3] Client test in `LifecycleRuleFormModal.test.tsx`: passing an `existingRule` prop
      pre-populates the form for edit, and a rule field the form doesn't render a control for
      (`unsupportedFilter`, e.g. a tag filter) round-trips unchanged in the computed `rules` array passed to
      `lifecycle.set` after an unrelated field edit (FR-013, Acceptance Scenario 3.4)
- [ ] T024 [P] [US3] Client test in `DeleteLifecycleRuleModal.test.tsx` (new file, same directory): renders a
      confirmation prompt before calling `lifecycle.set` (remaining rules) or `lifecycle.delete` (last rule),
      per the contract's single-rule-delete mapping; confirms delete is not fired without explicit
      confirmation (FR-012, SC-005)

### Implementation for User Story 3

- [ ] T025 [US3] Implement `lifecycle.delete` mutation procedure in `lifecycleRouter.ts`:
      `deleteLifecycleInputSchema` input, `storage:containers:update` permission, calls
      `DeleteBucketLifecycleCommand`, treats `NoSuchLifecycleConfiguration` as success, maps other errors via
      `mapS3ErrorToTRPCError` (depends on T005; makes T022 pass)
- [ ] T026 [US3] Extend `LifecycleRuleFormModal.tsx` to accept an optional `existingRule` prop: pre-populate
      form fields for edit, preserve `unsupportedFilter` verbatim in the computed rule object, and on submit
      compute the full `rules` array with the edited rule replacing the original by `id` (depends on T018;
      makes T023 pass)
- [ ] T027 [US3] Create `DeleteLifecycleRuleModal.tsx` in the `Buckets/` client folder: confirm-delete modal
      (`confirmButtonVariant="primary-danger"`) that on confirm computes `remainingRules` (current rules
      minus the target by `id`) and calls `lifecycle.set` if non-empty else `lifecycle.delete`, invalidates
      `utils.storage.ceph.lifecycle.get`, surfaces a toast, modeled on `DeleteBucketPolicyModal.tsx` (depends
      on T017, T025; makes T024 pass)
- [ ] T028 [US3] Wire per-row Edit and Delete actions in `LifecycleRulesModal.tsx`'s `PopupMenu` (stubbed in
      T012) to open `LifecycleRuleFormModal` (edit mode, `existingRule` set) and `DeleteLifecycleRuleModal`
      respectively (depends on T026, T027)
- [ ] T029 [US3] Add all new UI strings via `<Trans>`/`t` macro in `DeleteLifecycleRuleModal.tsx` and the
      edit-mode additions to `LifecycleRuleFormModal.tsx`, and run `pnpm check-i18n` to confirm extraction
      (depends on T026, T027)

**Checkpoint**: All three user stories independently functional — view, create, and edit/delete lifecycle
rules all work end-to-end.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Full-gate validation and manual verification per `quickstart.md`; no story-specific code left.

- [ ] T030 [P] Run `pnpm lint && pnpm check-i18n && pnpm typecheck && pnpm format:check && pnpm test && pnpm build`
      from repo root and fix any failures (Constitution Principle III; `quickstart.md`'s "Full local gate")
- [ ] T031 Verify commit messages use allow-listed `feat(storage): ...` / `test(storage): ...` scopes against
      `commitlint.config.mjs` (Constitution Principle IV; `plan.md`)
- [ ] T032 Walk through `quickstart.md`'s Manual / E2E validation scenarios 1–5 (view, create, edit/delete,
      backend rejection, permissions) against a running `pnpm dev` instance or test cluster, confirming each
      Success Criteria mapping (SC-001–SC-005)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001, T002 read the patterns Phase 2 mirrors) — BLOCKS all
  user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (T003–T008) completion — no dependency on other
  stories
- **User Story 2 (Phase 4)**: Depends on Foundational completion; `LifecycleRuleFormModal`'s "add" trigger
  (T020) is wired into `LifecycleRulesModal` from US1, but the form/mutation logic (T017–T019) has no
  runtime dependency on US1's list rendering — could be built and tested in isolation via T016 mocks
- **User Story 3 (Phase 5)**: Depends on Foundational completion; reuses `LifecycleRuleFormModal` (T018) and
  `lifecycle.set` (T017) from US2, and `LifecycleRulesModal`'s `PopupMenu` (T012) from US1 — genuinely
  builds on both prior stories' components (unlike US2, which only shares the router shell)
- **Polish (Phase 6)**: Depends on all three user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundational only — fully independent
- **User Story 2 (P2)**: Foundational only for its core logic (T017–T019, T016); integrates its "Add"
  trigger into US1's `LifecycleRulesModal` (T020)
- **User Story 3 (P3)**: Foundational + reuses US2's `LifecycleRuleFormModal`/`lifecycle.set` and US1's
  `LifecycleRulesModal` row actions — not independently buildable before US1 and US2 exist, though its own
  server procedure (`lifecycle.delete`, T025) has no such dependency

### Within Each User Story

- Tests before implementation (T009/T010 before T011/T012; T015/T016 before T017/T018; T022–T024 before
  T025–T027)
- Server procedure before the client component that calls it (T011 before T012; T017 before T018; T025
  before T027)
- Story complete before moving to the next priority, per Implementation Strategy below

### Parallel Opportunities

- T001 and T002 (Setup) in parallel
- T004 and T008 (Foundational, different concerns within/around T005) in parallel once T003 lands
- T009 and T010 (US1 tests) in parallel
- T015 and T016 (US2 tests) in parallel
- T022, T023, T024 (US3 tests) in parallel
- Once Foundational (Phase 2) completes, US1's server track (T011) and client-test authoring (T010, though
  it needs T011's shape to mock realistically) can proceed alongside early US2/US3 test-writing (T015, T016,
  T022–T024) since those only need the schemas from T003, not the finished procedures

---

## Parallel Example: User Story 1

```bash
# Launch both US1 tests together:
Task: "Server test for lifecycle.get in packages/aurora/src/server/Storage/routers/ceph/lifecycleRouter.test.ts"
Task: "Client test for LifecycleRulesModal in packages/aurora/src/client/.../Buckets/LifecycleRulesModal.test.tsx"
```

## Parallel Example: User Story 3 tests

```bash
Task: "Server test for lifecycle.delete idempotency in lifecycleRouter.test.ts"
Task: "Client test for unsupportedFilter round-trip in LifecycleRuleFormModal.test.tsx"
Task: "Client test for confirm-before-delete in DeleteLifecycleRuleModal.test.tsx"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T002)
2. Complete Phase 2: Foundational (T003–T008) — CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T009–T014)
4. **STOP and VALIDATE**: Open a bucket with an externally-configured lifecycle policy and confirm it
   displays accurately (FR-003); open one with none and confirm the empty state (FR-002)
5. Demo: "Lifecycle Rules" is visible and readable from the bucket header action, reachable in ≤2 clicks
   (SC-001)

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. Add US1 (view) → test independently → demo (MVP)
3. Add US2 (create) → test independently (create + save + appears in US1's list) → demo
4. Add US3 (edit/delete) → test independently (edit reflected, delete requires confirmation, tag filters
   preserved) → demo
5. Phase 6 polish (full gate + quickstart walkthrough) → ship

### Parallel Team Strategy

1. Team completes Setup + Foundational together (T001–T008)
2. Once Foundational is done:
   - Developer A: User Story 1 (T009–T014)
   - Developer B: starts US2's server side (T015, T017) — can proceed without US1 merged, since it only
     needs the Foundational schemas/router shell
   - Developer C: prepares US3's server test/procedure (T022, T025) similarly
3. US2's client (T018–T021) and US3's client (T026–T029) wait on US1's `LifecycleRulesModal` (T012) and each
   other, per the User Story Dependencies above, and integrate once those land

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Verify tests fail before implementing (T009/T010, T015/T016, T022–T024 must fail against the Phase 2
  schemas alone, before T011/T012, T017/T018, T025/T027 respectively)
- Commit after each task or logical group, using `feat(storage): ...` / `test(storage): ...` scopes
- Stop at any checkpoint to validate story independently
- FR-013 (never silently drop unsupported filter fields) is the one correctness risk that spans US1 (must
  display), US2 (must not require dropping them to save a new rule), and US3 (must preserve them through an
  edit) — T004's `unsupportedFilter` passthrough mapping is what every story's correctness on this point
  relies on
