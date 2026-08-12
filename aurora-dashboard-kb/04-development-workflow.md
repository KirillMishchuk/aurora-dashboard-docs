# 04 — Development Workflow

## Local setup

```bash
# Node 24 (.nvmrc), pnpm 11.20.0 (packageManager field; corepack enable)
pnpm install
cp apps/dashboard/.env.example apps/dashboard/.env
# set at minimum: IDENTITY_ENDPOINT (Keystone v3 URL), VITE_BFF_ENDPOINT="/polaris-bff"
pnpm dev            # dashboard on http://localhost:4005 (README) / PORT from .env
```

Dev mode runs `tsx watch` on `apps/dashboard/src/server/server.ts` with `@fastify/vite`; the aurora client package is aliased to source, so library edits hot-reload without a rebuild. Since #1085, `tsx watch` also passes `--tsconfig tsconfig.server.json --watch-kill-signal=SIGKILL` and explicit `--include` globs for `packages/aurora/src/{server,types}`, `packages/policy-engine/src`, `packages/signal-openstack/src` (excluding `*.test.ts`), so server-side workspace-package edits restart the dev server directly from source too — `turbo.json`'s `dev` task no longer depends on `@cobaltcore-dev/aurora#build` first.

## Commands (root, turbo-orchestrated)

| Command | Notes |
| --- | --- |
| `pnpm dev` | dev server (filter: dashboard app) |
| `pnpm build` | all packages; aurora = tsup (server) + vite (client) |
| `pnpm preview` | production build + `NODE_ENV=production tsx` run |
| `pnpm test` | vitest across packages (`--filter @cobaltcore-dev/aurora` etc. to narrow; add path for one file) |
| `pnpm test:e2e` / `:ui` / `:headed` / `:debug` / `:report` | Playwright in apps/dashboard |
| `pnpm lint` / `pnpm typecheck` / `pnpm format` / `format:check` | quality gates |
| `pnpm check-i18n` | Lingui extract `--clean` + compile — CI fails if catalogs drift |
| `pnpm commit` | commitizen interactive helper (cz-customizable) |
| `pnpm changeset` | create a changeset for release-worthy changes |
| `pnpm licenses:check` | allowlist check (Apache/MIT/BSD…), runs in CI |
| `pnpm clean` / `clean:cache` | remove dist/node_modules / turbo cache |
| `pnpm generate:package` | scaffold a new package from the template |

## Commits & PRs

- **Conventional Commits enforced** by commitlint (husky `commit-msg` hook) and by CI on PR titles.
- Format: `type(scope): subject` — types: `feat` (minor), `fix`/`perf` (patch), `refactor`, `docs`, `test`, `build`, `ci`, `chore`, `revert`, `style`. Breaking: `!` or `BREAKING CHANGE:` footer.
- Allowed scopes (`.cz-config.js`, `allowCustomScopes: false`): `build`, `config`, `ci`, `core`, `dashboard`, `app-gardener`, `app-template`, `aurora-portal`, `portal`, `aurora-sdk`, `signal-openstack`, `polaris`, `bff`, `docs`, `deps`, `infra`, `npm`, `template`, `ui`, `version`, `identity`. **`commitlint.config.mjs` is the actual source of truth and differs**: `build`, `config`, `ci`, `clavis`, `core`, `dashboard`, `gardener` (not `app-gardener`), `network`, `template`, `aurora`, `portal`, `aurora-sdk`, `signal-openstack`, `polaris`, `bff`, `docs`, `deps`, `infra`, `npm`, `ui`, `version`, `identity`, `playwright`, `metrics`, plus an `ISSUE-<number>` regex pattern — no `app-template`/`aurora-portal`.
- Subject limit 100 chars, imperative tense.
- **Husky hooks:** `pre-commit` (runs checks and ends with `git add -u` — beware: it stages *all* dirty tracked files), `commit-msg` (commitlint), `prepare-commit-msg`.
- **PR flow:** contribution via issue-first (open/claim issue → fork/branch → PR). PR titles lint-checked; CI must pass; DCO sign-off automatic on first PR. Draft PRs via the `create-pr` Claude skill (see below).

## CI/CD (GitHub Actions)

| Workflow | Trigger | What it does |
| --- | --- | --- |
| `ci-checks.yaml` | PRs, push to `changeset-release/main` | jobs: licenses, lint, check-i18n, typecheck, prettier, test, build (Node 24 → `24.15.0` since #1149; pnpm version auto-detected from `packageManager` field, no longer hardcoded — since #1122; #1124 briefly re-pinned `version: 11.18.0` in `.github/actions/setup-pnpm`, #1131 removed it again, so the `packageManager` pin is the single source; audit temporarily disabled) |
| `ci-title-lint-check.yaml` | PRs | conventional-commit PR title check |
| `release.yaml` | push to `main` | changesets action: opens/updates a "publish(npm)" version PR, or publishes to npm (OIDC trusted publishing) when the version PR merges; commit msg `chore(version): update versions with Changesets` |
| `build-push-aurora-pr-preview.yaml` | PR labels | label `pr-build` → build & push Docker preview image to GHCR; auto-adds `pr-preview` → ArgoCD deploys preview env; cleanup on close (see `docs/0012_aurora-pr-preview-workflow.md`) |
| `pr-preview.yml` | PR opened/reopened/synchronize/closed | second, newer PR-preview path (#1146): self-hosted runner + Traefik, `docker-compose.yml` (port 3000) → `https://pr-<NUMBER>.aurora-previews.d.c.eu-nl-1.cloud.sap`; `continue-on-error` so a down runner doesn't block merges, paired with a separate always-green `preview-check` job for branch protection (#1152) — coexists with `build-push-aurora-pr-preview.yaml` above; no design doc yet |
| `codeql.yml`, `reuse.yaml`, `stale.yaml` | scheduled/push | security scanning, license compliance, stale issues |

**Release model:** Changesets (`.changeset/`), `baseBranch: main`, public access, internal deps bumped as patch. Add a changeset in the same PR as the change. (`docs/semantic_release.md` describes an older semantic-release flow — treat changesets as current.)

**Docker:** `docker/Dockerfile` — node:24-alpine, full monorepo build, runs `pnpm preview` from `apps/dashboard` with `.env` from example (override with `-e`).

## Testing

- **Unit/integration:** vitest, colocated `*.test.ts(x)`; all three packages configure `environment: "jsdom"` in `vitest.config.ts` — meaningful in `packages/aurora` (React Testing Library + Lingui `I18nProvider` wrapper pattern), but `signal-openstack`/`policy-engine` tests never touch `document`/`window`, so jsdom there looks inherited (from the `generate:package` scaffolding template) rather than required. `test` task depends on `^build` in turbo.
- **E2E:** Playwright in `apps/dashboard/e2e/` — smoke (unauthenticated: landing/about/login/redirects; authenticated: projects, compute/network/storage UIs load without JS errors) and `ui/` specs (projects overview, navigation, detail). Needs `TEST_DOMAIN`, `TEST_MEMBER_USER/PASSWORD`, optional `TEST_ADMIN_*`, `TEST_PROJECT`, `PLAYWRIGHT_BASE_URL`, and a running app (`pnpm dev`). Design doc: `packages/aurora/docs/009_playwright_e2e_testing.md`.

## Claude Code assets in the repo (`.claude/`)

`.claude/` and the repo-root `CLAUDE.md` are **not** in `origin/main`, so nothing here ships upstream.

- **Agents:** `dev-planner` (opus — plan with architecture analysis and risk identification), `dev-executor` (sonnet — execute a plan step by step), and three read-only reviewers: `architecture-reviewer` (opus), `security-reviewer` (sonnet, auth/authz/data protection), `performance-reviewer` (sonnet, frontend + backend).
- **Skills — project workflow:** `create-plan` (analyze the architecture for a task → written plan in `../DOCS/plans/`), `implement-plan` (build an existing plan), `create-pr` (sync with main → guided conflict resolution, never resolves non-locale conflicts itself → PR description from template → draft PR via `gh`; never force-push/no-verify), `rework-commits` (split a branch into small semantic commits, backup branch first, before/after diff validation), `document-pr` (fetch a PR and write the report under `../DOCS/aurora-dashboard-kb/prs/`), `update-kb` (this knowledge base's update procedure), `triple-review` (review working changes from three angles), `quick-security-check` (focused audit of one file/component).
- **Skills — spec-kit:** `speckit-constitution`, `-specify`, `-clarify`, `-plan`, `-tasks`, `-taskstoissues`, `-analyze`, `-checklist`, `-implement`, `-converge` — the spec-driven workflow, alongside the `.specify/` and `specs/` directories.
- **`.claude/docs/`** holds one-off analyses (`ERROR-I18N-ANALYSIS.md`, `ISSUE-1055-ANALYSIS.md`).
- **`CLAUDE.md` exists** at the repo root (guidance for Claude Code, points at this knowledge base); the workspace-level `SAP/CLAUDE.md` one directory up covers the whole workspace folder.
