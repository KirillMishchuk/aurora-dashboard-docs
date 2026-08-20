# 01 — Project Overview

## What Aurora Dashboard is

Aurora Dashboard is an alternative **OpenStack user dashboard**, inspired by SAP Cloud Infrastructure's legacy Elektra dashboard and intended to replace it. It gives operators and end users one web UI for compute, storage, networking, identity and related services across projects and regions. Design goals: fine-grained self-service, usability with vanilla OpenStack, extensibility for custom use cases (including non-OpenStack services like Gardener and Clavis/PCA).

The core architectural idea is a **Backend-for-Frontend (BFF)**: a Fastify server proxies and abstracts OpenStack APIs, exposing them to the React UI as fully typed tRPC procedures. The UI never talks to OpenStack directly.

- Upstream repo: https://github.com/cobaltcore-dev/aurora-dashboard
- License: Apache-2.0 (REUSE-compliant; license check is part of CI)
- Copyright: SAP SE / cobaltcore-dev contributors

## Tech stack

| Area | Tooling |
| --- | --- |
| UI | React 19, juno-ui-components (`@cloudoperators/juno-ui-components`), Headless UI |
| Styling | Tailwind CSS v4, class-variance-authority, tailwind-merge |
| Routing | TanStack Router v1 (file-based) + TanStack Query / Form / Virtual |
| API layer | tRPC 11 + Zod 4 |
| Server | Fastify 5 (+ cookie, csrf-protection, helmet, multipart, static; rate-limit removed in #1075) |
| OpenStack client | `@cobaltcore-dev/signal-openstack` (undici-based, in-repo) |
| Policy | `@cobaltcore-dev/policy-engine` (oslo.policy evaluator, in-repo) |
| S3 / Ceph | AWS SDK v3 (`client-s3`, `lib-storage`, `s3-request-presigner`) |
| i18n | Lingui 5 (en / de locales, PO format) |
| Build / dev | Vite 8, tsup (server build), tsx (dev runner), pnpm 11, Turborepo 2 |
| Tests | Vitest 4 (unit, colocated `*.test.ts(x)`), Playwright (e2e) |
| Quality | ESLint 10, Prettier, Husky, commitlint + commitizen (Conventional Commits) |
| Node | v24 (`.nvmrc`; CI uses Node 24, packages declare `>=18`) |

## Monorepo layout

pnpm workspace (`apps/*`, `packages/*`, excluding `apps/dev`) orchestrated by Turborepo.

```
aurora-dashboard/
├── apps/
│   └── dashboard/            # @cobaltcore-dev/dashboard — thin reference consumer app (private)
│       ├── src/server/server.ts   # reads env, calls createServer()
│       ├── src/client/App.tsx     # renders <AuroraApp/>, persists theme in localStorage
│       ├── src/policies/*.json    # policy files passed to the BFF (compute/networking/image/storage)
│       └── e2e/                   # Playwright tests
├── packages/
│   ├── aurora/                # @cobaltcore-dev/aurora v0.23.x — THE library (server + client), published to npm
│   ├── signal-openstack/      # @cobaltcore-dev/signal-openstack — typed OpenStack HTTP client
│   ├── policy-engine/         # @cobaltcore-dev/policy-engine — oslo.policy evaluator (TS)
│   └── config/                # shared tsconfig + eslint config
├── docs/                      # architecture overview, semantic release docs
├── docker/                    # Dockerfile (node:24-alpine, runs pnpm preview)
├── .claude/                   # personal, NOT in origin/main — agents (dev-planner, dev-executor, architecture/security/performance reviewers) + skills (create-plan, implement-plan, create-pr, document-pr, update-kb, triple-review, quick-security-check, rework-commits, speckit-*); see 04-development-workflow.md
├── .github/workflows/         # ci-checks, release (changesets), PR preview, codeql, reuse, stale
├── PERMISSION_KEY_PATTERN.md          # scope:resource:action permission key convention
└── PERMISSION_ROUTER_IMPLEMENTATION.md # permission router factory reference
```

## Key facts & gotchas

- `packages/aurora` is the product; `apps/dashboard` deliberately owns almost nothing (env parsing, theme persistence, Vite config, policy JSON files).
- In dev, `apps/dashboard` aliases `@cobaltcore-dev/aurora/client` to aurora's **source** (`vite.config.mjs`), so edits to the package hot-reload without rebuild; the dashboard compiles Tailwind/SVGR/Lingui itself in dev. In production the pre-built dist is used.
- The server build (tsup) **bundles** `policy-engine` and `signal-openstack` into aurora's dist so consumers don't install them separately; everything else stays external.
- Versioning/publishing is done with **Changesets** (see `docs/semantic_release.md` for the older semantic-release description — the active pipeline is the changesets GitHub action in `.github/workflows/release.yaml`).
- Historical naming in docs: `apps/aurora-portal`, `aurora-sdk`, `polaris` — older names still appearing in design docs and commit scopes. Today's app is `apps/dashboard`; the BFF endpoint default is still `/polaris-bff`.
- Some docs disagree on prerequisites (README: Node ≥18/pnpm ≥10; CONTRIBUTING: Node ≥24/pnpm ≥9; CONTRIBUTING also references the old `apps/aurora-portal` path). Trust `.nvmrc` (24), `packageManager` (pnpm 11.20.0), and the README paths.
- **pnpm version comes from `packageManager` alone (#1131).** The root `package.json` briefly also listed `pnpm` in `dependencies` (`^11.16.0`); corepack installed that instead of the `packageManager` pin, and Docker builds then failed because workspace packages enforce the pinned version via `devEngines.packageManager`. The dependency entry was removed — don't reintroduce it. The same PR also dropped the hardcoded `version:` input from `.github/actions/setup-pnpm`, so CI reads the pin too.
- Repo root `pnpm-workspace.yaml` sets `minimumReleaseAge: 10080` (dependencies must be ≥7 days old, npm supply-chain guard), excluding `tmp` and juno-ui-components.
- **`@cloudoperators/juno-ui-components` is a real npm dependency, not a pnpm-workspace link.** There is no local build-time coupling to the sibling `../juno` clone that lives in this SAP workspace folder (`cloudoperators/juno`, the design system's own monorepo) — that clone is purely a reference copy for reading actual component source/props when the published package's types/docs aren't enough. It tracks `origin/main`, which normally runs ahead of the version pinned here (e.g. `9.1.0` on this branch vs `9.3.0` on `juno`'s `main` as of 20.08.2026, per #1177) — check out the git tag matching the pinned version (`@cloudoperators/juno-ui-components@<version>`) in `juno/` before trusting its source as authoritative for currently-running behavior.
- Since #1062 (Ceph) and #1155 (Swift, merged 2026-08-13, same pattern), object downloads run in an inline (`blob:`) Web Worker, which needs `worker-src 'self' blob:` in CSP — `createServer()` sets this in production automatically, but a consumer app running its own CSP (rather than Aurora's server) must add the directive itself or downloads silently fail. See 02-architecture "Cross-cutting mechanisms".
- **Peer-dependency rule (#1085):** any package that renders React components or uses React hooks/context must be a `peerDependency` of `packages/aurora`, not a `dependency` — otherwise a consuming app can resolve two copies of it (duplicate React instances → "Invalid hook call", disconnected context). Classification checklist in `packages/aurora/docs/0014_dependency_classification.md`. Same PR also dropped the `exports` field from `policy-engine`/`signal-openstack` `package.json` (both private, never published) and reworked the dashboard's `dev` script so workspace source-file changes are picked up without a rebuild — see 04-development-workflow.md.
- **`PERMISSION_KEY_PATTERN.md`/`PERMISSION_ROUTER_IMPLEMENTATION.md` are back in `origin/main`.** PR #1146 accidentally deleted both inside an unrelated squashed commit ("chore: remove documentation files"); PR #1158 (`docs: restore permission documentation files`, merged 10.08.2026) restored them verbatim. Present again as of the current pin — the files 02/04/05 in this KB reference are safe to rely on.
