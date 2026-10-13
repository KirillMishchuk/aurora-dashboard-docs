---
type: pr-report
date: 2026-07-23
status: merged
pr: [1085]
author: taymoor89 (Taimoor Aslam)
branch: 1084-move-dependencies
---
# PR #1085: fix(core): move react dependent packages to peerDeps and resolve workspace sources in dev

**Author:** taymoor89 (Taimoor Aslam) · **Status:** merged 2026-07-24 (`8b44234f`; created 2026-07-21)
**Branches:** `1084-move-dependencies` → `main` · **Files:** 11 (+180/-61)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1085

## What was done

The PR implements issue #1084 and solves two related monorepo configuration problems:

**Duplicate React due to incorrect dependency classification.** `packages/aurora/package.json` kept packages that use React context/hooks (`@lingui/react`, `@tanstack/react-query`, `@tanstack/react-router`, `@headlessui/react`, `focus-trap-react`, `react-error-boundary`, `react-icons`, `@trpc/react-query`, `@tanstack/react-form`, `@tanstack/react-virtual`) in regular `dependencies`. pnpm installed a private copy of them inside the `aurora` package's `node_modules`, which left the consumer (`apps/dashboard`) with two instances of React/contexts at once — hence "Invalid hook call" and silently broken Providers. The PR moves all such packages to `peerDependencies` and explicitly declares them as direct `dependencies` in `apps/dashboard/package.json` (i.e. the host application is now required to supply them itself).

**No hot reload for server-side workspace packages in dev mode.** `packages/policy-engine` and `packages/signal-openstack` are private and never published, but had an `exports` field that forced Node to always resolve them from the built `dist/`, ignoring the tsconfig path mapping. The PR removes `exports` from both (keeping `main`/`module`/`types` at the top level), adds `apps/dashboard/tsconfig.server.json` with path aliases to the sources of these packages and to `packages/aurora/src/server`, and replaces the previous `dev` command (`tsx watch --env-file=.env src/server/server.ts`) with a new `apps/dashboard/scripts/dev.sh`, which explicitly puts these paths on `--include` for `tsx watch`. Along the way, `apps/dashboard/turbo.json`'s `dev` task lost `dependsOn: ["@cobaltcore-dev/aurora#build"]` — a build before dev is no longer needed, everything is resolved from sources.

`packages/aurora/docs/0014_dependency_classification.md` was added — it documents the classification rule (peer if the package holds React context/hook state or singleton state; dependency if it is a pure utility or server-only) and greps for checking a new package for React usage. Plus a minor thing: `packages/aurora/eslint.config.mjs` added `src/locales/**` to the ignores (generated Lingui locales).

## How it is implemented

**Classification change** — `packages/aurora/package.json:52-68`:
```json
"peerDependencies": {
  "@headlessui/react": "^2.0.0",
  "@lingui/core": "^5.0.0",
  ...
  "fastify": "^5.0.0",
  "focus-trap-react": "^12.0.0",
  "react": "^19.0.0",
  "react-dom": "^19.0.0",
  "react-error-boundary": "^6.0.0",
  "react-icons": "^5.0.0"
},
```
Symmetrically, in `apps/dashboard/package.json:21-33` the same packages appear as regular `dependencies` (mostly without a caret, pinned to an exact version).

**New dev script** — `apps/dashboard/scripts/dev.sh:15-24`:
```sh
exec node_modules/.bin/tsx watch \
  --env-file=.env \
  --tsconfig tsconfig.server.json \
  --watch-kill-signal=SIGKILL \
  --include ../../packages/aurora/src/server \
  --include ../../packages/aurora/src/types \
  --include ../../packages/policy-engine/src \
  --include ../../packages/signal-openstack/src \
  --exclude '**/*.test.ts' \
  --exclude '**/dist/**' \
  src/server/server.ts
```
The reason for a shell script rather than a line in `package.json` — a comment in the file explains that Turbo mangles multi-flag commands when running them through its task runner. `--include` lists exactly the directories that the new path aliases in `apps/dashboard/tsconfig.server.json:9-12` point to — the two files are consistent with each other.

**Removed `exports`** — `packages/policy-engine/package.json:11-17` and `packages/signal-openstack/package.json:9-15` lose the `exports` block (mapping to `dist/{cjs,esm,types}`), keeping only `main`/`module`/`types` at the package's top level — this is enough for resolution, since both packages are `"private": true` and never published.

## What it affects

The change affects **only the dev workflow and package metadata** — runtime code and the public API of `AuroraApp`/tRPC routers are untouched. A `git grep` check at the PR's head commit (`132d5fa356af4299ff9594247bf1f5a99cef7565`) for other consumers of `policy-engine`/`signal-openstack`/the moved React packages outside the changed files found nothing extraneous — the only consumers are `packages/aurora` and `apps/dashboard`, which the PR updates consistently.

The production build (`vite build`, `tsup`) is not changed by this PR — it already resolves `packages/aurora/client` from sources via an alias in `vite.config.mjs`, and the server bundles `policy-engine`/`signal-openstack` via `tsup` with `noExternal`, where resolution goes by `main` regardless of `exports` (esbuild with `platform: "node"` uses `mainFields: ["main", "module"]`). So removing `exports` does not change the behaviour of the prod build — the effect is only in dev mode (`tsx watch`), which is what it is intended for.

The only point the build potentially doesn't cover — if another server-side workspace package (`packages/config`, a new one) appears in the future, one will have to remember to add it both to `--include` in `dev.sh` and to `paths` in `tsconfig.server.json`; right now this is manual synchronization of two files, nothing automatically checks them for drift, but with 11 files and 2 packages in the PR this is not a problem — just not absolute protection against future drift.

## Review

**Found (confidence ≥ 80):** no problems with this level of confidence were found.

**Also noted (confidence 50-79, confirmed but below the threshold):**

1. **The comment about `--watch-kill-signal=SIGKILL` describes non-existent behaviour.** (confidence 75)
   `apps/dashboard/scripts/dev.sh:17-18` explains: the flag "kills the old process immediately on restart... avoids 'address already in use' errors". In reality `--watch-kill-signal` is a flag of native `node --watch`, not of `tsx watch`; `tsx watch --help` (version `4.21.0`, pinned in `package.json`) recognizes only `--clear-screen, --exclude, --ignore, --include, --no-cache, --tsconfig`. `tsx` uses its own restart logic: it always sends `SIGTERM` and waits a fixed 5 seconds before `SIGKILL`, regardless of this flag — the flag is silently ignored (no CLI error, behaviour unchanged). The goal stated in the comment (avoiding "address already in use") is not achieved by this line. It does not affect whether the script works — it's just a dead line with a misleading comment.
   File: `apps/dashboard/scripts/dev.sh:17-18, 23`.

Additionally, the CodeRabbit review on the PR itself independently noted two minor inaccuracies in `packages/aurora/docs/0014_dependency_classification.md` (an example using `useState` instead of `useContext`/`createContext` as a sign of "context access"; and a heuristic based on `grep "Provider"`, which catches arbitrary text rather than specifically React imports/hooks) — both purely about wording in the new doc file, not about code behaviour.

---
Analyzed: 2026-07-23 · commit `132d5fa356af4299ff9594247bf1f5a99cef7565`
