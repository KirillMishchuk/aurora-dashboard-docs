---
type: pr-report
date: 2026-08-13
status: merged
pr: [1176]
author: TilmanHaupt
branch: til-sec-5
---
# PR #1176: fix: cap TempURL lifetime and restrict to read-only by default

**Author:** TilmanHaupt · **Status:** merged 2026-08-17 (commit `d00f84a`; opened and updated 2026-08-13, all 4 commits within a single day)
**Branches:** `til-sec-5` → `main` · **Files:** 2 (+16/-2)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1176

> GitHub API access from this session is blocked (the same 403 with the `add_repo` message as in previous reports); `gh` is unavailable both over the network from the cloud container (`gh` itself is installed, but the `github.com`/`api.github.com` API/web endpoints are closed by this session's proxy) and on the user's device (`device_bash` has no network). The PR was cloned anonymously via `git` (`refs/pull/1176/head` and `refs/pull/1176/merge`, public repository, no authentication needed) — all code, diffs and **the full history of all 4 commits** were checked against this clone, not against the PR's HTML page. The PR title, branches and status were derived from the commit history/changeset and `git ls-remote`/`merge-base` (reliable); what cannot be obtained without the API — the exact PR title as shown on GitHub (if the author edited it separately from the commits), draft/ready status, exact `createdAt`/`updatedAt`, review bots — is not confirmed. It was precisely the line-by-line walk through the entire commit history (rather than just `git diff base..head`) that uncovered finding #1 below — it is completely invisible in the final diff.

## What was done

The PR continues the recent series of Swift-related security fixes in `packages/aurora/src/server/Storage` — SSRF in the Swift account (#1148), SSRF in Glance pagination (#1144), redaction of TempURL/sync keys from metadata responses (#1173, still open) — and closes the next finding in the same series: `generateTempUrl` allowed issuing not only `GET` but also `PUT`/`POST`/`DELETE`-signed temporary links with an unlimited lifetime (`expiresIn: z.number().min(1)`, no upper bound).

The history within the PR itself is not linear:

1. **`20613f1` (12:06)** — introduces `MAX_TEMP_URL_LIFETIME = 3600` (1 hour), `DEFAULT_TEMP_URL_LIFETIME = 900` (15 minutes), narrows `method` to `z.enum(["GET"])` and adds audit logging (`console.info` with `userId`/`projectId`/`container`/`object`/`method`/`expiresIn`) in `swiftRouter.ts`. The commit message itself labels the change as `Breaking changes: TempURL method restricted to GET only ... expiresIn now capped at 3600s maximum`.
2. **`bcdf367` (12:36)** — raises the limit from 1 hour to 7 days (`604800`) and the default from 15 minutes to 24 hours (`86400`), to match the already existing UI presets (1h/24h/7d). The same commit puts two large files into the repository root — see finding #1.
3. **`794f8e4` (12:41, 5 minutes later)** — deletes both files from step 2 entirely.
4. **`6f24f56` (14:26, PR head)** — removes the `console.info` logging added in step 1, with the comment "not suitable for production".

The final diff against `main` (`4c34ce8`) is just 2 files: a new changeset and `swift.ts`. The audit logging in `swiftRouter.ts` was added and removed within a single PR — the resulting file is byte-for-byte identical to `main`.

## How it is implemented

### `types/swift.ts` — the only substantive change

```ts
// swift.ts:395-398
// TempURL lifetime constraints for security
// GET-only URLs can have longer lifetime for file sharing with colleagues
export const MAX_TEMP_URL_LIFETIME = 604800 // 7 days (in seconds)
export const DEFAULT_TEMP_URL_LIFETIME = 86400 // 24 hours
```

```ts
// swift.ts:401-409
export const generateTempUrlInputSchema = baseObjectInputSchema.extend({
  method: z.enum(["GET"]), // Read-only for security
  expiresIn: z
    .number()
    .min(60) // Minimum 1 minute
    .max(MAX_TEMP_URL_LIFETIME) // Maximum 7 days
    .default(DEFAULT_TEMP_URL_LIFETIME),
  filename: z.string().optional(), // Optional Content-Disposition filename
})
```

Before: `method: z.enum(["GET", "PUT", "POST", "DELETE"])`, `expiresIn: z.number().min(1)` — no upper bound and no method restriction.

### `swiftRouter.ts` — the consumer is unchanged, but re-checked

`generateTempUrl` (`swiftRouter.ts:1210-1211`) builds its input via `projectScopedInputSchema.extend(generateTempUrlInputSchema.shape)`, so the new constraints are picked up automatically, without changing the procedure's code. The only place where `method` is used further on is when it is passed into the HMAC signature:

```ts
// swiftRouter.ts:1287
const signature = await generateTempUrlSignature(tempUrlKey, method, expiresAt, objectPath)
```

Previously `"PUT"`/`"POST"`/`"DELETE"` could arrive here — now only `"GET"`. There was and is no logic in the file that branches on the value of `method` — narrowing the type is safe for this function.

## What it affects

The blast radius was checked for every changed name (`generateTempUrlInputSchema`, `MAX_TEMP_URL_LIFETIME`, `DEFAULT_TEMP_URL_LIFETIME`) across the whole monorepo:

- **The only server consumer** — `generateTempUrl` in `swiftRouter.ts` (see above), with no code changes.
- **Client** — `GenerateTempUrlModal.tsx` (not touched by this PR) already sends only `method: "GET"` (hardcoded on the client) and offers exactly three presets — 1 hour / 24 hours / 7 days (`3600`/`86400`/`604800` seconds) — which after this PR match the new `min`/`max`/`default` **exactly**. That is, the UI had been aligned with these limits in advance (or simultaneously, in another PR) — none of the already working UI paths break. The "Custom duration (minutes)" field has no upper bound on the client, but that is pre-existing behavior not touched by this PR (see the rejected finding below).
- **The package's public contract** — `generateTempUrlInputSchema`/`GenerateTempUrlInput` are part of the `@cobaltcore-dev/aurora` Zod schemas that define the input type of the `generateTempUrl` tRPC procedure for any external consumer of the package (not just `apps/dashboard`). Narrowing `method` and adding upper/lower bounds on `expiresIn` is a contract change: a call with `method: "PUT"` or with `expiresIn` outside `[60, 604800]`, which used to pass, will now get a Zod validation error. See finding #2.
- **Overlap with #1173** (open, not merged, same author, neighboring files) — no code overlap: #1173 fixes the leak of secret keys via `swiftHelpers.ts`/`parseAccountInfo`/`parseContainerInfo` (the metadata read path), this PR fixes the `generateTempUrl` input schema (the link generation path). There is no shared code, but there is a shared cause — both PRs successively close items from the same internal security audit (see finding #1: that is the audit in question).

## Review

**Two findings scored 100/100 confidence.**

- **[100/100] An internal security audit of the entire application (16 findings, including exploit descriptions and a 6-week remediation plan) was committed to the public repository and remains recoverable from the PR history even after deletion.** Commit `bcdf367` added `SECURITY_ANALYSIS.md` (1427 lines) and `SECURITY_IMPLEMENTATION_PLAN.md` (1841 lines) to the repository root — this is not a template but a real, code-verified report ("Security Review Analysis & Prioritization — Aurora Dashboard", dated 2026-08-05, tied to the specific commit `890f453`) with 16 numbered findings (2 High, 12 Medium, 2 Low), including "Finding #5: Overbroad Swift TempURL Generation" — literally what this PR fixes, "Finding #7: Raw OpenStack Token Exposure via API" (the raw Keystone token is handed to the browser), "Finding #9: EC2 Credential Deletion IDOR", etc., plus CWE/OWASP/SOC2/PCI-DSS mapping and an implementation plan with a draft customer incident notification. Five minutes later, commit `794f8e4` deleted both files ("Remove private security analysis documents that should not be in public repo") — but the final `git diff base..head` does not show this at all: the files appear and disappear within the PR history, not in the net diff. That does not help: both commits have already been pushed to the public `cobaltcore-dev/aurora-dashboard` on GitHub, and `git show bcdf3670:SECURITY_ANALYSIS.md` retrieves the full text for anyone who has the PR URL — including after the merge (the PR's "Commits" page keeps referencing these SHAs regardless of the merge method). Checked for real secrets/credentials inside — none found (examples like `super-secret-sync-key-123` are obviously illustrative), but the map of the application's weak spots and what has not been fixed yet is exactly the sensitive part that leaked. Possible steps: `git filter-repo`/a forced rewrite of the branch history before merging, plus rotation/reindexing of the repository if third parties have already seen it.
- **[100/100] The changeset is marked `minor`, even though the PR's own commits explicitly call the change breaking — the same pattern already noted in #1173 (85/100).** `.changeset/tempurl-restrictions.md` declares `"@cobaltcore-dev/aurora": minor`. Commit `20613f1` contains a `Breaking changes:` section in its full message — "TempURL method restricted to GET only (PUT, POST, DELETE no longer allowed)", "expiresIn now capped at 3600s maximum" (the limit was later raised to 7 days, but the breaking nature itself — narrowing the enum and adding an upper bound that did not exist before — did not change). Releases go through Changesets (`release.yaml` → `changesets/action`), which reads the version strictly from the changeset file's frontmatter — prose in the commit message has no effect on the final bump. A consumer of `@cobaltcore-dev/aurora` with a `^0.x` range will receive this as an ordinary "safe" minor update: TS code that called `generateTempUrl` with `method: "PUT"/"POST"/"DELETE"` or with `expiresIn` outside `[60, 604800]` will stop compiling/start failing at runtime with no breaking-release warning in the CHANGELOG. [`CLAUDE.md`](../../CLAUDE.md) separately stresses: "commit type/scope directly affects the next version bump, so get it right" — the same principle applies to changeset severity.

Below is what was checked and did not reach the ≥80 threshold:

- **[75/100, rejected — threshold not met] The changeset text was not updated after the limit was raised from 1 hour to 7 days.** Commit `20613f1` wrote the changeset for the "1 hour" limit; the next commit `bcdf367` raised it to 7 days (168×), but the changeset text ("Cap Swift TempURL lifetime and restrict to read-only by default") stayed generic, with no specific number. Not formally a lie, but the CHANGELOG for package consumers does not reflect the behavior that actually shipped. Closest to the threshold, but did not reach 80 — left as an observation, not a formal finding.
- **[25/100, rejected] None of the PR's 4 commits contain a `(scope)` in the `<type>(<scope>): <subject>` format documented in CLAUDE.md.** Checking `commitlint.config.mjs` showed that the `scope-empty` rule is not enabled — CI will not catch this; the final PR/squash commit title (which is what the linter actually checks) is not confirmed without API access. Rejected as unlikely/unconfirmed, not as a clear violation.
- **[0/100, rejected] The "Custom duration (minutes)" field in `GenerateTempUrlModal.tsx` has no upper bound on the client, so a user can now get a server-side 400 error for a value above 7 days.** A real gap, but it lives entirely in a file this PR did not touch (the bug is pre-existing — previously the server did not cap `expiresIn` from above either, so before this PR there was no mismatch at all; the mismatch is created by the new server-side bound, but the gap itself is in lines not changed by this PR).
- **[0/100, rejected] The PR adds no tests verifying the new schema bounds (`method: "PUT"` is now rejected, `expiresIn` outside `[60, 604800]` is now rejected).** A general test coverage remark, explicitly excluded by the false-positive rules (CLAUDE.md does not require tests for Zod schema bounds).

---
Analyzed: 2026-08-13 · commit `6f24f56`
