# Implementation Plan: Ceph Bucket Lifecycle Rules

**Branch**: `001-bucket-lifecycle-rules` | **Date**: 2026-08-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-bucket-lifecycle-rules/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Add lifecycle-rule management for Ceph (RGW/S3) buckets: a `storage.ceph.lifecycle` tRPC router
(`get`/`set`/`delete`, mirroring the existing `bucketPolicy` and `versioning` routers) backed by the
`@aws-sdk/client-s3` `GetBucketLifecycleConfigurationCommand` / `PutBucketLifecycleConfigurationCommand` /
`DeleteBucketLifecycleCommand`, plus a client-side rule list (add/edit/delete) rendered as a modal/panel on
the bucket detail view, following the same header-action → modal-dispatcher pattern already used for bucket
policy and versioning.

## Technical Context

**Language/Version**: TypeScript 5, Node >= 24 (per repo `.nvmrc`/`packageManager`)

**Primary Dependencies**: Fastify + tRPC (server), `@aws-sdk/client-s3` `^3.1042.0` (already a dependency,
exposes `GetBucketLifecycleConfigurationCommand`/`PutBucketLifecycleConfigurationCommand`/
`DeleteBucketLifecycleCommand`), Zod (input/output validation), React 19 + TanStack Router/Query,
`@tanstack/react-form`, Lingui (`@lingui/react/macro`), `@cloudoperators/juno-ui-components` (Modal, DataGrid)

**Storage**: N/A (feature reads/writes lifecycle config directly on the Ceph RGW bucket via the S3 API; no
BFF-side persistence)

**Testing**: Vitest (colocated `*.test.ts(x)`) — server: `createCallerFactory` + mocked `S3Client.send` via
`vi.mock("../../clients/s3Client")`, reusing `routers/ceph/mockContext.ts`; client: React Testing Library +
`userEvent`, `trpcReact` namespace mocked directly, wrapped in `I18nProvider`/`PortalProvider`

**Target Platform**: Web (Aurora Dashboard, browser client + Node BFF)

**Project Type**: Web application (existing `packages/aurora` monorepo package — server + client in one
package, per Constitution Principle V)

**Performance Goals**: No new performance target beyond existing bucket-config operations (single S3 API
round trip per get/set/delete, same as bucket policy/versioning)

**Constraints**: Ceph RGW's S3-compatible API has no endpoint to enumerate available storage classes (this
is normally an RGW Admin Ops / zonegroup concept, out of scope for this feature); no live "max rules per
bucket" or "available storage classes" discovery is possible via `@aws-sdk/client-s3` alone (see
`research.md`)

**Scale/Scope**: 3 new tRPC procedures (`getLifecycle`/`setLifecycle`/`deleteLifecycle`), 1 new Zod schema
module, ~5-7 new client components (rule list + add/edit modal + delete-confirm modal + header action wiring)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. BFF Boundary Discipline** — PASS. New `lifecycleRouter.ts` is built with `cephProtectedProcedure`
  (itself built on the exported `projectScopedProcedure`/`protectedProcedure` chain from `trpc.ts`), added
  as a sibling under `storage.ceph.*` in `routers/index.ts`, exactly like `bucketPolicyRouter`/
  `versioningRouter`. No new `initTRPC` instance. No project/domain-scoped calls inside client components —
  the client only calls the already-scoped `trpcReact.storage.ceph.lifecycle.*` procedures from within
  modal components mounted on an already-loaded bucket route (consistent with existing bucket-config
  modals, which are not route loaders themselves but operate on data the route already scoped).
- **II. Policy-Driven Authorization** — PASS. Reuses the existing `storage:containers:read` /
  `storage:containers:update` permission keys (already in `STORAGE_MAPPINGS`) rather than inventing new
  ones — this matches the established convention that bucket policy and versioning, which are also
  bucket-configuration actions, do not have dedicated permission keys either. No `storage.json` policy
  changes needed. See `research.md` for the explicit decision.
- **III. Test & CI Parity** — PASS (planned). New server router test (`lifecycleRouter.test.ts`) and new
  client component tests colocated as `*.test.tsx`, following the exact patterns of
  `bucketPolicyRouter.test.ts` / `BucketPolicyModal.test.tsx`. `pnpm lint`, `pnpm typecheck`, `pnpm test`,
  `pnpm check-i18n`, `pnpm format:check`, `pnpm build` will be run before pushing.
- **IV. Conventional Commits** — PASS (planned). Commits will use `feat(storage): ...` /
  `test(storage): ...` scopes (an existing allow-listed scope — verify against `commitlint.config.mjs`
  during implementation).
- **V. Monorepo Package Boundaries** — PASS. All new code lives in `packages/aurora` (server routers/types
  under `Storage/`, client components under the existing `Buckets/` component folder). `apps/dashboard` is
  untouched.

No violations; Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-bucket-lifecycle-rules/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
packages/aurora/src/server/Storage/
├── routers/
│   ├── index.ts                         # buildObjectStorageRouters — add `lifecycle: auroraRouter({...lifecycleRouter})`
│   └── ceph/
│       ├── index.ts                     # add `export { lifecycleRouter } from "./lifecycleRouter"`
│       ├── lifecycleRouter.ts           # NEW — get/set/delete procedures (mirrors bucketPolicyRouter.ts)
│       └── lifecycleRouter.test.ts      # NEW — vitest, mocked S3Client.send, reuses mockContext.ts
└── types/
    └── lifecycle.ts                     # NEW — Zod schemas (mirrors types/versioning.ts)

packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/
├── BucketHeaderActions.tsx              # add "lifecycle" trigger (existing file, edited)
├── BucketModals.tsx                     # add "lifecycle" to ModalType union + mount (existing file, edited)
├── LifecycleRulesModal.tsx              # NEW — rule list (DataGrid), Add button, per-row Edit/Delete actions
├── LifecycleRulesModal.test.tsx         # NEW
├── LifecycleRuleFormModal.tsx           # NEW — shared add/edit form (name, prefix, status, actions)
├── LifecycleRuleFormModal.test.tsx      # NEW
├── DeleteLifecycleRuleModal.tsx         # NEW — confirm-delete (mirrors DeleteBucketPolicyModal.tsx)
└── DeleteLifecycleRuleModal.test.tsx    # NEW
```

**Structure Decision**: Single-package web application (`packages/aurora` holds both the tRPC server and
the React client per Constitution Principle V; `apps/dashboard` is an unmodified consumer). The feature adds
one new domain sub-router (`storage.ceph.lifecycle`) alongside the existing `bucketPolicy`/`versioning`
sub-routers, and new client components inside the existing `Buckets/` folder alongside
`BucketPolicyModal.tsx`/`EnableVersioningModal.tsx`, reusing their exact modal-dispatch and
list-with-row-actions patterns (the latter modeled on `ObjectVersionHistoryModal.tsx`). No new top-level
route is introduced — lifecycle rules are managed via a modal launched from the existing bucket view, same
as bucket policy and versioning.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

No violations — table not applicable.
