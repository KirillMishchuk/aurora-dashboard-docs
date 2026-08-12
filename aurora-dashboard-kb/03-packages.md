# 03 — Packages & Apps

## packages/aurora — `@cobaltcore-dev/aurora` (the product)

Published npm library (v0.23.x, public). Peer deps: `react`, `react-dom`, `fastify`, `@headlessui/react`, `@lingui/core`, `@lingui/react`, `@tanstack/react-form`, `@tanstack/react-query`, `@tanstack/react-router`, `@tanstack/react-virtual`, `@trpc/react-query`, `focus-trap-react`, `react-error-boundary`, `react-icons` — anything that renders React components or uses hooks/context must be a peer, not a private dependency, to avoid duplicate-React issues in consumers (#1085; classification rules in `docs/0014_dependency_classification.md`).

**Entry points** (package.json `exports`):

| Export | Contents |
| --- | --- |
| `@cobaltcore-dev/aurora/server` | `createServer(config)`, `auroraRouter`, procedure builders (`publicProcedure`, `protectedProcedure`, `projectScopedProcedure`, `domainScopedProcedure`), scoped input schemas |
| `@cobaltcore-dev/aurora/client` | `<AuroraApp />`, `SlotProps`, `TrackEventPayload`, tRPC client hooks |
| `@cobaltcore-dev/aurora/types` | shared types |

**Build:** two-step — `tsup` for the server (CJS, node18 target, dts; bundles `policy-engine` + `signal-openstack` via `noExternal`, path alias `@` → `./src`) and `vite build` for the client. i18n via Lingui (`extract`/`compile`, checked in CI with `check-i18n`).

**Source layout:**

```
src/
├── server/          # BFF: domain folders (Authentication, Project, Compute, Network, Storage, Services),
│                    # policies/ (permission router factory), aurora-fastify-plugins/, trpc.ts, routers.ts
├── client/          # AuroraApp, routes/ (file-based), components/, hooks/ (e.g. useAvailableViewportHeight,
│                    #   useVirtualizedTableBody — see 02-architecture "Cross-cutting mechanisms"), trpcClient
├── types/           # shared types
├── locales/en, de   # Lingui PO catalogs
└── docs/ → ../docs/ # design docs 001–0013 (see 05-domain-map.md)
```

**Testing:** vitest, jsdom environment, colocated `*.test.ts(x)`. Run a single package: `pnpm --filter @cobaltcore-dev/aurora test [path]`.

## packages/signal-openstack — `@cobaltcore-dev/signal-openstack`

Typed OpenStack HTTP client on undici. "Swiss Army knife" for OpenStack APIs.

- **Session:** `SignalOpenstackSession(identityEndpoint, authConfig, options)` — auth methods `password`, `token`, `application_credentials`; scoping/rescoping via `scope` in authConfig; `getToken()`, `terminate()`, `service(name, options)`.
- **Token:** `authToken`, `tokenData`, `availableRegions`, `isExpired()`, `hasService()`, `hasRole()`, `serviceEndpoint(type, {region, interfaceName})`.
- **Service:** `get/head/del/post/put/patch(path, {queryParams, headers, region, interfaceName, signal…})` → native `Response`; `getEndpoint()` (e.g. to hand the S3 endpoint to AWS SDK); `availableEndpoints()`.
- Options cascade session → service → request. Structured colorized debug logging with automatic secret redaction (`logger`, `redactSensitiveData`). Proxy support for mitmproxy debugging (TLS validation auto-disabled; dev only).
- Source: flat `src/` — `session.ts`, `token.ts`, `service.ts`, `client.ts`, `auth-config.ts`, `error.ts`, `responseErrorHandler.ts`, `logger.ts`; every module has a colocated test.

## packages/policy-engine — `@cobaltcore-dev/policy-engine`

TypeScript implementation of OpenStack's oslo.policy evaluator; works in browser and Node.

- Pipeline: `policyFileLoader` (JSON/YAML) → `lexer` → `parser` (AST, operator precedence) → compiled rules map → `evaluator`; `debugTrace` for step-by-step traces.
- API: `createPolicyEngine(config)` / `createPolicyEngineFromFile(path)` → `engine.policy(keystoneTokenPayload, {debug?})` → `userPolicy.check(ruleName, params)`.
- Syntax support: `@`/`!`, `role:x`, `rule:x` (nested), `user_id:%(target.user.id)s` parameter substitution, `and/or/not` + parentheses, `is_admin:true`, `is_admin_project:true`, `system_scope:all`.
- Includes `keystone_policy.test.ts` and `integration.test.ts` against realistic policies.
- Private/unpublished, like `signal-openstack`: since #1085 its `package.json` has no `exports` field (that field forced Node to resolve the compiled `dist/` regardless of tsconfig path mappings). Node now falls back to `main`, so tsx's tsconfig paths route straight to TS source in dev — no rebuild needed to see workspace edits.

## packages/config — `@cobaltcore-dev/aurora-config`

Shared base configs: `typescript/base.json`, `tsconfig.react.json`, `tsconfig.lib.json`, `eslint/index.mjs`. (README still calls it `@cloudoperators/juno-config` — outdated; the workspace name used in deps is `@cobaltcore-dev/aurora-config`.)

## apps/dashboard — `@cobaltcore-dev/dashboard` (private reference consumer)

Owns only:

- `src/server/server.ts` — validates `PORT` (default 4005 per README; `.env.example` uses 4001), maps env vars → `createServer()` config, resolves `policyDir` (src in dev, dist in prod), `listen`s.
- `src/client/App.tsx` — `<AuroraApp bffEndpoint={import.meta.env.VITE_BFF_ENDPOINT} theme=… />` with theme persisted to localStorage.
- `src/policies/*.json` — compute, networking, image, storage policy files (copied to dist on build).
- `vite.config.mjs` — dev alias of `@cobaltcore-dev/aurora/client` to package source (instant HMR into the library), `@fastify/vite` integration, static copy of policies.
- `e2e/` — Playwright suite (see 04-development-workflow.md).

**Env vars** (`.env.example`): `IDENTITY_ENDPOINT` (required), `VITE_BFF_ENDPOINT` (`/polaris-bff`), `PORT`, `DEFAULT_ENDPOINT_INTERFACE`, `VITE_APP_TITLE`, `VITE_ENABLED_SERVICES`, `CEPH_REGION`, `IMAGE_METADATA_EXCLUDED_PROPERTIES`, `DASHBOARD_COOKIE_NAME`, `COOKIE_DOMAIN`, `INSECURE_COOKIES`, `GLOBAL_AGENT_HTTP_PROXY` (mitmproxy, dev only), plus `TEST_*`/`PLAYWRIGHT_BASE_URL` for e2e.

## Dependency graph

```
apps/dashboard ──► @cobaltcore-dev/aurora ──► @cobaltcore-dev/signal-openstack   (bundled into aurora dist)
                                        └──► @cobaltcore-dev/policy-engine       (bundled into aurora dist)
all packages ──► @cobaltcore-dev/aurora-config (dev-time tsconfig/eslint)
```
