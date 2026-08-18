# 05 — Domain & Feature Map

Where each feature lives: server router (`packages/aurora/src/server/…`), client routes (`packages/aurora/src/client/routes/_auth/…`), and the design doc in `packages/aurora/docs/`.

## Domains

| Domain | Server routers | Client UI | Design doc |
| --- | --- | --- | --- |
| **Authentication** | `Authentication/routers/sessionRouter.ts` | `/auth/login`, `_auth.tsx` guard | — (see 02-architecture) |
| **Project** | `Project/routers/projectRouter.ts` | `/projects`, `/projects/$projectId` overview | — |
| **Compute — servers** | `Compute/routers/serverRouter.ts`, `serverGroupRouter.ts` | project compute section | — |
| **Compute — flavors** | `Compute/routers/flavorRouter.ts` | flavors list/detail (admin CRUD, metadata, access control) | `003_flavors_ui_requirements.md` |
| **Compute — images** | `Compute/routers/imageRouter.ts` | images UI (list/search/visibility/members/metadata; excluded props via env); notifications go through the app-wide `NotificationManager` `toast` API via `ImageToastNotifications` builders, not the legacy `<Toast>` (#1132) — see 02-architecture "Cross-cutting mechanisms" | `005_images_bff.md` (full BFF API reference, Glance v2) |
| **Compute — keypairs** | `Compute/routers/keypairRouter.ts` | — | example in `docs/aurora_architecture_overview.md` |
| **Network — security groups** | `Network/routers/securityGroupRouter.ts`, `securityGroupRuleRouter.ts`, `rbacPolicyRouter.ts` | `network/securitygroups`, `…/$securityGroupId` (+AddRuleModal); actions are permission-gated via `useSecurityGroupPermissions` (`network:security_groups:*`, `network:security_group_rules:*`, `network:rbac_policies:*` keys, one bulk `canUser` check), list toolbar (sort/filter/search) syncs to URL via `urlHelpers.ts` (#952) | `007_security_groups_bff.md` (Neutron v2, CRUD + rules + RBAC) |
| **Network — floating IPs** | `Network/routers/floatingIpRouter.ts` (`network.floatingIp.*`; `searchTerm` matches `description`, `floating_ip_address`, `fixed_ip_address`, `floating_network_id`) | `network/floatingips`, `…/$floatingIpId`; list header uses `DataGridToolbar` (`SortInput`/`FiltersInput`/`SelectedFilters` + 500ms-debounced `SearchInput`), `placeholderData` keeps the previous rows on screen during refetch so only the initial load blocks on a spinner (a non-blocking `Message` banner covers refetch errors when cached rows exist); "Allocate Floating IP" is gated by `network.canUser` (`network:floatingips:create`) instead of a hardcoded permission; bulk selection/action UI was removed as unused (#1099); filters/search/sort are persisted in URL search params via the route's `validateSearch` + route-local `urlHelpers.ts`, with per-field `safeParse` fallback and push-vs-replace history semantics (#1129) | `008_floating_ips.md` |
| **Storage — Swift** | `Storage/routers/swift/swiftRouter.ts` | `storage/$provider/$storageType/…/objects`; object downloads/previews run in a Web Worker off the main thread, at parity with Ceph (#1155, merged 2026-08-13), see 02-architecture "Cross-cutting mechanisms" and `prs/1155-…md` for findings shipped unfixed; account/container metadata redacts TempURL and sync secrets to presence flags, and TempURL generation is capped to read-only `GET` with a 60s–7d lifetime (#1173, #1176, merged 14.08/17.08.2026 — see 02-architecture "Secret redaction & TempURL hardening" and `prs/1173-…md`, `prs/1176-…md`) | `006_swift_object_storage_bff.md` (verified against Swift API; relative paths, SDK handles /v1/AUTH_) |
| **Storage — Ceph S3** | `Storage/routers/ceph/`: `containerRouter`, `objectRouter`, `bucketPolicyRouter`, `versioningRouter`, `ec2CredentialRouter` | Ceph buckets/objects components; object downloads/previews run in a Web Worker off the main thread (#1062); object upload via file picker/drag-and-drop with progress + cancel (#1086, `UploadObjectModal`), see 02-architecture "Cross-cutting mechanisms"; `objects.generatePresignedUrl` + `GeneratePresignedUrlModal` issue a time-limited shareable GET link (#1120); bulk delete of objects/versions via multi-select + `DeleteObjectsModal` (#1121, merged 2026-08-07) — chunked `DeleteObjects` (max 1000 keys/call); **known bug:** `RestoreVersionModal`/`DeleteVersionModal` swallow `errorCount` from `deleteVersionsBulk` and report success even on partial S3 failure (fix planned, not yet implemented — `DOCS/plans/2026-08-03-fix-deleteversionsbulk-partial-failure.md`) | `009_ceph_s3_bff.md` (EC2 creds via Keystone, AWS SDK v3, error mapping, upload/download streaming, presigned URLs) |
| **Services — PCA / Clavis** | `Services/routers/pcaRouter.ts` | `services/pca`, `…/$pcaId` (CA list/create/delete/import chain, certificates, lifecycle actions) | `0011_clavis.md` (living doc, current scope) |
| **Permissions** | `policies/createPermissionRouter.ts` + per-domain `permissionRouter.ts` (Compute, Network, Storage) | UI checks `scope:resource:action` keys | `PERMISSION_KEY_PATTERN.md`, `PERMISSION_ROUTER_IMPLEMENTATION.md` (repo root — accidentally deleted by PR #1146, restored by PR #1158, see 01-overview.md gotchas) |

## Design doc index (`packages/aurora/docs/`)

| Doc                                  | Topic                                                                                  | Status flavor          |
| ------------------------------------ | -------------------------------------------------------------------------------------- | ---------------------- |
| `001_extensions.md`                  | Aurora Extension model (client/server exports, registerRouter, aurora-sdk, tRPC rules) | concept                |
| `002_integration_approaches.md`      | Embedding Aurora in the legacy (Elektra) dashboard: iframe vs alternatives             | analysis               |
| `003_flavors_ui_requirements.md`     | Flavors control requirements (business + functional, admin-only CRUD)                  | requirements           |
| `004_proposal_subscriptions.md`      | SSE real-time updates architecture (single connection, invalidation events)            | proposal               |
| `005_images_bff.md`                  | Glance Images BFF API reference (endpoints, schemas, params)                           | implemented, reference |
| `006_swift_object_storage_bff.md`    | Swift BFF (accounts/containers/objects, versioning notes)                              | implemented, verified  |
| `007_security_groups_bff.md`         | Security Groups + Rules + RBAC BFF                                                     | implemented, verified  |
| `008_floating_ips.md`                | Floating IP BFF + mutations hook                                                       | implemented            |
| `009_ceph_s3_bff.md`                 | Ceph RGW S3 BFF (EC2 creds, S3 client, error mapping)                                  | implemented, reference |
| `009_playwright_e2e_testing.md`      | E2E smoke test plan (2 phases)                                                         | implemented            |
| `0010_abort_signal_propagation.md`   | AbortSignal propagation browser→OpenStack                                              | implemented, reference |
| `0011_clavis.md`                     | Clavis/PCA integration scope + UI                                                      | living doc             |
| `0012_aurora-pr-preview-workflow.md` | PR preview: labels `pr-build`/`pr-preview`, GHCR, ArgoCD                               | implemented            |
| `0013_analytics-tracking.md`         | Analytics: onTrackEvent, router auto-tracking, semantic actions                        | implemented, guide     |
| `0014_dependency_classification.md`  | `dependencies` vs. `peerDependencies` rule for React-using packages, detection checklist | guide                  |

Note: older docs (005–008) reference historical paths `apps/aurora-portal/...` — the code now lives in `packages/aurora/src/...`; the API descriptions remain accurate.

## Where to add a new feature (checklist)

1. **Types**: Zod schemas in `packages/aurora/src/server/<Domain>/types/`.
2. **Router**: tRPC router in `<Domain>/routers/`, built with `auroraRouter`/`protectedProcedure` (or scoped procedures); mount in `<Domain>/routers/index.ts` and the root router.
3. **Permissions**: add `scope:resource:action` keys via the permission router factory; policy rules in the consumer's policy files (`apps/dashboard/src/policies/*.json`).
4. **Client route**: file-based route under `routes/_auth/projects/$projectId/...`; loaders fetch + scope, `-components/`/`-hooks/`/`-modals/` for non-route code; add `staticData` (section/service) for analytics.
5. **i18n**: wrap strings with Lingui; run `pnpm check-i18n` (en + de catalogs).
6. **Tests**: colocated `*.test.ts(x)` (vitest); e2e spec in `apps/dashboard/e2e/` if user-facing.
7. **Changeset + conventional commit** (scope from allowed list), PR with template; label `pr-build` for a preview environment.
