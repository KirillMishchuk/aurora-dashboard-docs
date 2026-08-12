# Quickstart: Validating Ceph Bucket Lifecycle Rules

Prerequisites:
- `pnpm install` done at repo root (Node >= 24, pnpm >= 10).
- A running dashboard against a real or test OpenStack + Ceph RGW environment with EC2 credentials
  available for the target project (see `apps/dashboard/.env.example`), OR unit/integration tests using the
  mocked S3 client (no live cluster needed for automated checks below).
- A test bucket the user's project has `storage:containers:update` on.

## Automated checks

```bash
# Server: router unit tests (mocked S3Client, no live cluster)
pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/lifecycleRouter.test.ts

# Client: component tests
pnpm --filter @cobaltcore-dev/aurora test -- Buckets/LifecycleRules

# Full local gate before push (must match CI)
pnpm lint && pnpm check-i18n && pnpm typecheck && pnpm format:check && pnpm test && pnpm build
```

## Manual / E2E validation scenarios

Run `pnpm dev` (dashboard at the configured port, default `4001`/`4005` — see `CLAUDE.md`), sign in, and
navigate to a project's Storage → Ceph bucket list.

1. **Story 1 — View (FR-001, FR-002, FR-003)**
   - Open a bucket with no lifecycle configuration → "Lifecycle Rules" view shows the empty state.
   - Using an external tool (`aws s3api put-bucket-lifecycle-configuration` against the same RGW endpoint,
     or a pre-seeded test bucket) configure 1-2 rules, then open the same bucket in the dashboard → both
     rules appear with correct name, status, prefix, and actions (`lifecycle.get` contract).

2. **Story 2 — Create (FR-004–FR-010)**
   - Create a rule scoped to `logs/` that expires current objects after 30 days → appears in the list with
     correct prefix/expiration (Acceptance Scenario 2.1).
   - On a versioning-enabled bucket, add a noncurrent-version expiration action to the same or a new rule →
     both current- and noncurrent-version actions show distinctly (Acceptance Scenario 2.2).
   - Attempt to save a rule with zero actions selected → save is blocked with an explanatory message
     (Acceptance Scenario 2.3 / FR-009).
   - On a cluster with no configured transition storage classes (research.md §4), attempt to add a
     transition action → UI communicates transitions are unavailable rather than allowing the save
     (Acceptance Scenario 2.4 / FR-006).
   - Attempt to save a second rule reusing an existing rule's name → client-side rejection before any
     network call (Clarifications session 2026-08-04, FR-004).

3. **Story 3 — Edit/Delete (FR-011–FR-013)**
   - Disable an enabled rule → it stays listed, shown disabled (Acceptance Scenario 3.1).
   - Edit a rule's expiration period → list reflects the new value immediately (Acceptance Scenario 3.2).
   - Delete a rule → a confirmation prompt appears before removal (Acceptance Scenario 3.3 / FR-012 /
     SC-005).
   - Open for editing a rule created externally with an object-tag filter → the tag filter is not dropped
     or overwritten by an unrelated edit (Acceptance Scenario 3.4 / FR-013) — verify via
     `aws s3api get-bucket-lifecycle-configuration` after the edit that the `Filter.Tag`/`And` fragment is
     unchanged.
   - Delete the last remaining rule on a bucket → bucket returns to the empty state from Story 1 (Edge
     Cases; exercises the `lifecycle.delete` full-removal path from the contract).

4. **Backend rejection (Edge Cases, FR-015, SC-004)**
   - Attempt to exceed the storage backend's max-rules-per-bucket limit → save is blocked with the
     backend's error surfaced clearly; the rule list still reflects the last known-good state.

5. **Permissions (FR-014)**
   - As a user without `storage:containers:update` (but with `read`), confirm the rule list is visible but
     add/edit/delete controls are unavailable or rejected.

## Success criteria mapping

- SC-001 (≤2 clicks from bucket detail view) — verify the "Lifecycle Rules" action is reachable directly
  from the bucket's header actions/menu.
- SC-002 (<2 min to create a working rule) — time the Story 2 first scenario end-to-end.
- SC-003 (100% of externally-created rules displayed accurately, never silently lost) — Story 1's
  external-tool scenario plus Story 3's tag-filter edit scenario.
- SC-004 (<5% of save attempts rejected by the backend) — informal check that client-side validation
  (Story 2 scenarios) catches the documented invalid states before submission.
- SC-005 (zero accidental deletions) — Story 3's delete-confirmation scenario.
