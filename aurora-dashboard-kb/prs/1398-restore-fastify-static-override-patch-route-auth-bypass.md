---
type: pr-report
date: 2026-10-29
status: open
pr: [1398]
issue: [152, 153]
author: andypf
branch: fix/restore-fastify-static-override
---

# PR #1398: fix(deps): restore @fastify/static override to patch route/auth bypass

**Author:** andypf · **Status:** open · **Base:** `main` ← `fix/restore-fastify-static-override`
**Size:** 3 files, +12 / −19 · **Created:** 2026-10-27 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1398)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

_Reviewed at head [`8e6df7b2`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1398/commits/8e6df7b25542a860334dc773b70252c00482b461) · base `main` at `8cd09bfa` · 2026-10-29 13:25 UTC_

### ⚖️ &nbsp; Verdict

Recommendation: **🟡 Approve with process to-dos** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **High**

- **Process:** P1, P2

This PR correctly restores a critical security override for @fastify/static that was mistakenly removed in PR #1396, closing two path traversal vulnerabilities (route guard bypass and authorization bypass). The change only affects dependency resolution—no runtime impact, no API changes—and all CI checks pass. Acceptance grading: only one criterion (Security and Compliance) applies and is met. The PR description incorrectly references issues #152 and #153 as Dependabot alert numbers when they are unrelated GitHub issues.

### 🔧 &nbsp; Required Changes

| #   | Severity | Category | Precedent | Issue                                                        | Location |
| --- | -------- | -------- | --------- | ------------------------------------------------------------ | -------- |
| P1  | —        | Process  | —         | PR description references incorrect Dependabot alert numbers | PR body  |
| P2  | —        | Process  | —         | Security advisory table uses wrong issue numbers             | PR body  |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**P1 — The description claims what the code doesn't do** · Process · PR body
The PR body states 'Dropping the override reopened Dependabot alerts **#152** and **#153**', but these are actually GitHub issues about production deployment (#152 EPIC) and Gardener UI requirements (#153 Task), not security advisories. The security fixes are real—the referenced issue numbers are wrong.
_Fix:_ Update the PR description to use the actual Dependabot alert identifiers (e.g., GHSA-xxxx), or describe the advisories generically without specific numbers.

**P2 — The description claims what the code doesn't do** · Process · PR body
The table mapping alerts to vulnerabilities lists '#152 (high): route guard bypass' and '#153 (moderate): authorization bypass', but those GitHub issue numbers refer to unrelated project management issues, not security advisories.
_Fix:_ Replace the issue numbers in the table with correct Dependabot alert identifiers or use GHSA references for the advisories.

</details>

### 💡 &nbsp; Improvements

None.

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

This PR restores a pnpm dependency override for `@fastify/static` that was mistakenly removed in PR #1396. The override forces `@fastify/static@^10.1.2` (the patched version) and prevents the vulnerable `9.3.0` from being installed as a transitive dependency through `@fastify/vite`. Without this override, two Dependabot security advisories (high severity: route guard bypass; moderate severity: authorization bypass) are reopened. CI passes with 18 jobs successful, 4 skipped, and 0 failures.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**Dependency configuration** — The PR makes three focused changes:

```yaml
"@fastify/static@<10.1.2": "^10.1.2"
```

Adds the override back to `pnpm-workspace.yaml`, forcing any `@fastify/static` version below `10.1.2` to resolve to `^10.1.2`. This targets the transitive dependency chain: `@fastify/vite@8.4.1` depends on `@fastify/static@^9.3.0`, and without the override, pnpm installs the vulnerable 9.3.0 alongside the production dependency (10.1.2 in `packages/aurora/package.json`).

**Lockfile cleanup** — The diff shows `pnpm-lock.yaml` removing all references to `@fastify/static@9.3.0`:

```yaml
devDependencies:
  '@changesets/cli':
    specifier: ^2.31.1
```

The vulnerable package definition is deleted, and the snapshot for `@fastify/vite@8.4.1` now references `@fastify/static@10.1.2` `pnpm-lock.yaml:6436`. The obsolete `content-disposition@1.1.0` (a dependency of the removed 9.3.0) is also pruned.

**Changeset** — A patch-level changeset is added for `@cobaltcore-dev/aurora`:

```markdown
---
"@cobaltcore-dev/aurora": patch
---

Restore the `@fastify/static@<10.1.2` pnpm override. Without it, `@fastify/vite` pulls in `@fastify/static@9.3.0`, which is affected by two advisories:
- GHSA (route guard bypass via non-leading `..` / `%2E%2E` path segments, `<=10.1.0`)
- GHSA (authorization bypass via non-canonical URL paths, `<=10.1.1`)

The override forces the patched `10.1.2`. These are dev-dependency (`@fastify/vite`) vulnerabilities, so `pnpm audit --prod` did not surface them.
```

The changeset explains the security rationale: `@fastify/static@9.3.0` is affected by two advisories (route guard bypass via non-leading `..` / `%2E%2E` path segments in `<=10.1.0`, and authorization bypass via non-canonical URL paths in `<=10.1.1`), and the override ensures the patched `10.1.2` is used. It clarifies that these are dev-dependency vulnerabilities (via `@fastify/vite`), so `pnpm audit --prod` did not surface them.

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

**Production runtime impact**: None. `@fastify/static@^10.1.2` is already a direct dependency of `@cobaltcore-dev/aurora` `packages/aurora/package.json:75` and is used in production to serve static files (`packages/aurora/src/server/server.ts:199-203`). The vulnerable `9.3.0` was never imported by production code — it was only present in the lockfile for dev tooling (`@fastify/vite`).

**Development environment impact**: The override ensures developers don't have the vulnerable version installed when running `pnpm install`. Before this fix, `pnpm-lock.yaml` contained both versions (10.1.2 for production, 9.3.0 for dev), and the 9.3.0 instance could be exploited if a developer ran a local Fastify server with `@fastify/vite` in a non-standard configuration.

**Security posture**: Closes two Dependabot security advisories (high severity: route guard bypass; moderate severity: authorization bypass). The PR description notes that `@fastify/static@10.1.2` was published on 2026-07-22, well outside the 7-day `minimumReleaseAge` window in `pnpm-workspace.yaml`, so no `minimumReleaseAgeExclude` entry is needed.

**Consumers**: No code changes outside the three configuration files. The override is transparent to all consumers of `@cobaltcore-dev/aurora` — it's a build-time constraint, not a runtime API change. No package exports, tRPC procedure keys, React components, or public types are modified.

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Clone the repository and check out the PR branch (commit `8e6df7b2`)
2. Run `pnpm install` to rebuild the lockfile locally
3. Verify that `pnpm-lock.yaml` contains only `@fastify/static@10.1.2` (no `9.3.0` entry) by running `git diff HEAD pnpm-lock.yaml` and confirming the vulnerable version is absent
4. Run `pnpm audit --prod` and confirm "No known vulnerabilities found"
5. Run `pnpm audit` (without `--prod`) and confirm no `@fastify/static` advisories are reported
6. Run `pnpm typecheck` and `pnpm test` to verify the override doesn't break type checking or tests
7. Run `pnpm dev` and access the dashboard at `http://localhost:4001` (or the configured PORT) to confirm static file serving (logo, CSS, JS bundles) works correctly

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- If `@fastify/vite` is upgraded to a version that depends on `@fastify/static@^10`, the override becomes redundant but harmless — pnpm will resolve to the highest compatible version (10.1.2 or later) regardless of the override
- If a future advisory affects `@fastify/static@10.1.2` and requires a bump to (e.g.) `10.1.3`, the override range `^10.1.2` will automatically accept the patch, so only the direct dependency in `packages/aurora/package.json` needs updating

</details>

---

_Analyzed 2026-10-29 · commit `8e6df7b2` · read-only · skill: review-and-comment-pr_
