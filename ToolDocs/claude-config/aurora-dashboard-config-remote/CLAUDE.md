# CLAUDE.md

Guidance for Claude Code working in this repository.

## Knowledge base

A maintained, verified knowledge base for this project lives at `../DOCS/aurora-dashboard-kb/` (one level above the repo root):

- `01-overview.md` — what the project is, tech stack, monorepo layout, gotchas
- `02-architecture.md` — BFF/tRPC patterns, routing, auth & token scoping, permissions/policy
- `03-packages.md` — per-package API surface and build setup
- `04-development-workflow.md` — commands, commit/PR conventions, CI/CD, releases, testing
- `05-domain-map.md` — feature → router/route/design-doc map, new-feature checklist

Do NOT inline these files here. Read the relevant file on demand before planning non-trivial work. The KB is pinned to a specific commit (noted in its README) — if it lags far behind current HEAD, mention to the user that the knowledge base may need updating.

## Project overview

Aurora Dashboard is a web dashboard for managing OpenStack-based cloud infrastructure (compute, storage, networking, identity). It follows a Backend-for-Frontend (BFF) architecture: a Fastify + tRPC server abstracts OpenStack's REST APIs, and a React client consumes them through a fully typed tRPC client.

It's a **pnpm monorepo** orchestrated by **Turborepo**:

```
apps/
  dashboard/            # Reference consumer app — wires env vars into createServer(), owns nothing else
packages/
  aurora/                # Published npm library (@cobaltcore-dev/aurora) — the server + client, two entry points
  signal-openstack/      # Typed OpenStack HTTP client (built on undici) — auth, service catalog, sessions
  policy-engine/         # Evaluator for OpenStack's oslo.policy rule format
  config/                # Shared tsconfig and ESLint config
```

`packages/aurora` is where nearly all product code lives. `apps/dashboard` only reads env vars, calls `createServer()`/renders `<AuroraApp />`, and persists the theme.

## Commands

Run from the repo root unless noted. Turborepo fans these out to every package.

```bash
pnpm install                     # install deps (Node >= 24, pnpm >= 10 — see .nvmrc / packageManager)
pnpm dev                         # start apps/dashboard dev server (tsx watch), http://localhost:4001 by default
pnpm build                       # build all packages (turbo build, respects dependency graph)
pnpm test                        # run all vitest suites across packages
pnpm typecheck                   # tsc --noEmit across all packages
pnpm lint                        # eslint across all packages
pnpm format                      # prettier --write
pnpm format:check                # prettier --check (what CI runs)
pnpm check-i18n                  # lingui extract + compile (packages/aurora only)
```

Scope any of these to one package with `--filter`, e.g.:

```bash
pnpm --filter @cobaltcore-dev/aurora test              # vitest run, packages/aurora only
pnpm --filter @cobaltcore-dev/aurora test:watch         # vitest --watch
pnpm --filter @cobaltcore-dev/aurora test src/server/policies/createPermissionRouter.test.ts   # single file
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/signal-openstack test
pnpm --filter @cobaltcore-dev/policy-engine test
```

Test files are colocated with source as `*.test.ts(x)` (vitest, jsdom environment for `packages/aurora`, node elsewhere) — there's no separate `__tests__` tree.

E2E (Playwright, `apps/dashboard` only, requires a running dashboard + real/test OpenStack credentials in `.env`):

```bash
pnpm test:e2e            # playwright test
pnpm test:e2e:ui
pnpm test:e2e:headed
pnpm test:e2e:debug
pnpm test:e2e:report
```

Other:

```bash
pnpm commit               # commitizen-driven Conventional Commit prompt
pnpm licenses:check        # verify all prod dependency licenses are allow-listed
```

CI (`.github/workflows/ci-checks.yaml`) runs `licenses:check`, `lint`, `check-i18n`, `typecheck`, `format:check`, `test`, and `build` as separate jobs — match these locally before pushing.

## Server architecture (`packages/aurora/src/server`)

Fastify server exposing OpenStack functionality via **tRPC**. Domain code is grouped into PascalCase folders — `Authentication`, `Compute`, `Network`, `Project`, `Services`, `Storage` — each internally split into `routers/`, `types/` (Zod schemas), and `helpers/`. `routers.ts` merges each domain's router tree into the app router (`buildAppRouter`), which is exported via `packages/aurora/src/server/index.ts` along with `createServer`.

**Procedure builders** (`trpc.ts`) are the key abstraction — always build routers from these, not raw `initTRPC`:

- `publicProcedure` — no auth
- `protectedProcedure` — requires a valid session
- `projectScopedProcedure` — requires `project_id` (via `projectScopedInputSchema`), transparently rescopes the OpenStack session/token to that project via Keystone before the handler runs, and passes the rescoped session as `ctx.openstack`
- `domainScopedProcedure` — same idea for `domain_id`, additionally checks the user actually has access to the requested domain (lazy-loaded via `/v3/auth/domains`) before rescoping

Consumers extending the server pass extra routers via `createServer({ routers: [...] })`; those routers **must** be built with the exported `auroraRouter` (== `t.router`) so their context type matches — a different `initTRPC` instance breaks `ctx.openstack`/`ctx.validateSession` at runtime.

**Permissions**: `packages/policy-engine` evaluates OpenStack `oslo.policy` YAML rule files (checked out of `apps/dashboard/src/policies/*`). Each domain exposes a `canUser` query built with the generic factory `createPermissionRouter` (`policies/createPermissionRouter.ts`) — you give it `{ policyDir, engines: { <engine>: { fileName } }, mappings }` and it handles engine loading, single/bulk permission checks, and Zod validation. See `PERMISSION_ROUTER_IMPLEMENTATION.md` for the factory contract and `PERMISSION_KEY_PATTERN.md` for the permission-key naming convention.

Permission keys follow `scope:resource:action` (e.g. `storage:containers:create`, `network:routers:attach_interface`) — scope and resource are UI/domain vocabulary, never the OpenStack service name (`storage`, not `swift`/`ceph`; `network`, not `neutron`). Resources are plural snake_case; actions are consistent verbs (`read`, `list`, `create`, `update`, `delete`, plus specific ones like `attach`/`associate`/`empty`/`copy`).

## Client architecture (`packages/aurora/src/client`)

React 19 + **TanStack Router** (file-based routing) + **TanStack Query** + a typed **tRPC client** (`trpcClient.ts`), styled with Tailwind v4, i18n via **Lingui**.

Routing conventions under `client/routes/`:

- Dynamic segments use a `$` prefix (`$projectId.tsx`)
- Folders prefixed with `-` (e.g. `-components/`) hold non-route files (components, tests, helpers) and are excluded from route generation
- `_auth.tsx` is the shared authenticated layout; its `beforeLoad` hydrates/validates the session and redirects to login if absent — no child route renders without a scoped session
- Project/domain-scoped tRPC calls (token rescoping) happen in route `loader`s, not inside components — components receive already-scoped data
- `routeTree.gen.ts` is generated; don't hand-edit it

`AuroraApp` (the package's public client export, `client/AuroraApp.tsx` / `App.tsx`) accepts `slots` — named extension points (`logo`, `sideNavBanner`, `pageFooter`, `login`, `serviceBadge`, `servicePageActions`, `projectsBanner`, `projectOverviewBanner`) letting host apps inject components without forking, and `enabledServices` to whitelist which OpenStack services show in the nav. See `packages/aurora/README.md` for the full consumer-facing contract (props, slots, analytics via `onTrackEvent`) — treat that file as the source of truth when changing any of `AuroraApp`'s public props.

## Commit conventions

Conventional Commits are enforced by commitlint (`commitlint.config.mjs`) and checked in CI on PR titles too. Format: `<type>(<scope>): <subject>`.

- `type` must be one of the values in `commitlint.config.mjs` (`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`, `revert`, `publish`)
- `scope` must be one of the allow-listed scopes in the same file (kebab-case), or an `ISSUE-<number>` pattern
- Breaking changes: `!` after the type or a `BREAKING CHANGE:` footer
- Releases are automated via Changesets/Semantic Release from commit history (see `docs/semantic_release.md`) — commit type/scope directly affects the next version bump, so get it right.

**Signing commits:**
All commits must include a `Signed-off-by` line. **IMPORTANT**: Git hooks do NOT work reliably with the `-m` flag — Git skips `prepare-commit-msg` and `commit-msg` hooks when a message is provided via `-m` or `--amend -m`. **Always use the `--signoff` (or `-s`) flag explicitly**:

```bash
git add <files>
# CORRECT - always use --signoff flag:
git commit --signoff -m "fix(aurora): improve bulk delete selection performance"
# Short form:
git commit -s -m "fix(aurora): improve bulk delete selection performance"

# For amending commits:
git commit --amend --signoff --no-edit

# INCORRECT - will NOT add Signed-off-by:
git commit -m "fix(aurora): message"  # ❌ Missing --signoff flag
```
