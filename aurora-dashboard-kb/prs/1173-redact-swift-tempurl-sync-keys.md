---
type: pr-report
date: 2026-08-13
status: merged
pr: [1173]
author: TilmanHaupt
branch: til-sec-4
---
# PR #1173: fix(core): redact Swift TempURL and sync keys from metadata responses

**Author:** TilmanHaupt · **Status:** merged 2026-08-14 (commit `2c7bd0e`; opened 2026-08-12)
**Branches:** `til-sec-4` → `main` · **Files:** 10 (+224/-47)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1173

> Network access to the GitHub API from this session is blocked (the same 403 as before), and `gh` is unavailable on the user's device (`device_bash` has no network). The PR was cloned anonymously via `git` in the cloud container (`refs/pull/1173/head`, a public repository, no authentication needed) — all code, diffs and history were checked against that clone, not against the PR's HTML page. Metadata that cannot be obtained via `git` (author, status, creation/update dates, review bots) was taken from a render of the PR page; an outright hallucination also turned up there (see below) — not everything from it was taken on faith.

## What was done

The recent chain of security fixes in `packages/aurora/src/server/Storage` (SSRF in Swift #1148, SSRF in Glance pagination #1144, path traversal in OpenStack routes #1153 — all within the last week) continues with this PR: `getAccountMetadata`/`getContainerMetadata` in the Swift router were still returning raw secrets to the client — `X-Account-Meta-Temp-URL-Key(-2)` and `X-Container-Meta-Temp-URL-Key(-2)`/`X-Container-Sync-Key` — right in the response body as ordinary string fields `tempUrlKey`/`tempUrlKey2`/`syncKey`. Both secrets grant real access without authentication: the TempURL key signs temporary links to objects, and the sync key permits cross-account container synchronization. These fields appeared in `swiftHelpers.ts`/`swift.ts` on 2026-06-29 (commit `c67430d`, when the Swift module landed in the repository in full) and have not been touched since — the PR fixes a leak that existed for roughly 6.5 weeks.

The solution is to replace the raw values with boolean presence flags (`hasTempUrlKey`, `hasSyncKey`), computed by a new module `secretHelpers.ts`, and to remove the secret string fields from the response Zod schemas. **The implementation closes the leak only partially** — see "Review": the account key still leaks through the generic `metadata` dictionary, because `parseAccountInfo` (unlike `parseContainerInfo`) does not filter `temp-url-*` out of the generic loop over `x-account-meta-*`.

## How it is implemented

### New module `secretHelpers.ts` — detector and redactor of secret headers

`packages/aurora/src/server/helpers/secretHelpers.ts` (53 lines, new file) — three exports:

```ts
// secretHelpers.ts:5-14
const REDACTED_HEADERS = [
  "x-auth-token",
  "x-subject-token",
  "x-container-sync-key",
  "x-container-meta-temp-url-key",
  "x-container-meta-temp-url-key-2",
  "x-account-meta-temp-url-key",
  "x-account-meta-temp-url-key-2",
  "authorization",
] as const
```

`isSecretHeader()` (`secretHelpers.ts:19-21`) matches the header name (lowercased) against this list — but it is not called anywhere outside its own test (see "Review"; not a standalone finding, just context). The actual work is done by `redactAccountSecrets`/`redactContainerSecrets` (`secretHelpers.ts:30-53`) — each simply checks for the **presence** of the relevant headers via `Headers.has()`:

```ts
// secretHelpers.ts:30-36
export function redactAccountSecrets(headers: Headers): {
  hasTempUrlKey: boolean
} {
  return {
    hasTempUrlKey: headers.has("x-account-meta-temp-url-key") || headers.has("x-account-meta-temp-url-key-2"),
  }
}
```

### `swiftHelpers.ts` — secret fields removed from the top level of the response

`parseAccountInfo`/`parseContainerInfo` (`swiftHelpers.ts:97-211`) used to explicitly copy `tempUrlKey`/`tempUrlKey2`/`syncKey` from the headers into the returned object based on a truthy check of the value; now a call to the new redactor takes their place:

```ts
// swiftHelpers.ts:123-129 (parseAccountInfo)
// Security: Redact secret keys, return only presence flags
const secrets = redactAccountSecrets(headers)

return {
  ...accountInfo,
  ...secrets,
} as AccountInfo
```

Symmetrically for the container (`swiftHelpers.ts:204-210`, `redactContainerSecrets`). At this level (the top-level fields `tempUrlKey`/`tempUrlKey2`/`syncKey`) the secret really is no longer returned — confirmed both by the code and by the new tests (`swiftHelpers.test.ts`: `expect(result).not.toHaveProperty("tempUrlKey")`).

### `types/swift.ts` — response schemas tightened

`accountInfoSchema`/`containerInfoSchema` (`swift.ts:136-143`, `189-205`) lost their optional secret string fields and gained **required** (not `.optional()`) boolean flags:

```ts
// swift.ts:199-205 (containerInfoSchema)
  syncTo: z.string().optional(),
  // Security: Return only presence flags, not secret values
  hasTempUrlKey: z.boolean(),
  hasSyncKey: z.boolean(),
})
```

The other Zod schemas where `tempUrlKey`/`tempUrlKey2` appear (`updateAccountMetadataInputSchema:169-170`, `createContainerInputSchema:240-241`, `updateContainerMetadataInputSchema:256-257`) are untouched — these are **input** schemas (the client passes a value to *set* the key via `updateAccountMetadata`/`updateContainerMetadata`), not response schemas; they are not part of the leak and are rightly left unchanged by this PR.

### Tests — fixtures updated, but they did not expose the hole in account metadata

`swiftHelpers.test.ts`, `swift.test.ts`, `swiftRouter.test.ts` and two client `*.test.tsx` files (fixtures only, with no changes to the components themselves — this PR does not touch `ContainerLimitsTooltip.tsx`/`EditContainerMetadataModal.tsx`; their tests were updated solely because `hasTempUrlKey`/`hasSyncKey` became required fields of the type) add checks like `expect(result).not.toHaveProperty("tempUrlKey")` and `expect(result.hasTempUrlKey).toBe(true)`. Not a single new test checks **the contents of `result.metadata`** when temp-url headers are set — which is exactly what allowed the leak through `metadata` to go unnoticed (see "Review", finding #1).

## What it affects

The change is localized within `packages/aurora/src/server/Storage` + the new `packages/aurora/src/server/helpers/secretHelpers.ts`; the blast radius was checked for every changed public name across the entire monorepo (`packages/*`, `apps/*`):

- `AccountInfo`/`ContainerInfo` (types) — the only producers are `parseAccountInfo`/`parseContainerInfo` themselves (one call of each in `swiftRouter.ts:197` and `:372`), which now always set `hasTempUrlKey`/`hasSyncKey`. The only consumers of the full (non-`Partial<>`) type as a literal are 4 test files, and all 4 are updated by this PR (`ContainerLimitsTooltip.test.tsx`, `EditContainerMetadataModal.test.tsx`, `swiftRouter.test.ts`, `swift.test.ts`). `ManageContainerAccessModal.test.tsx` also imports `ContainerInfo`, but only as `Partial<ContainerInfo>` — it does not need the new required fields; nothing breaks.
- Client code (`packages/aurora/src/client/**`, `apps/dashboard/**`) — not a single non-test file reads `tempUrlKey`/`tempUrlKey2`/`syncKey`/`hasTempUrlKey`/`hasSyncKey` directly; the UI did not and does not display these secrets, so the behavior on the end screen does not change, only the API contract underneath it.
- `isSecretHeader` — exported, but not used by anyone except its own test; dead code, does not affect behavior.
- `.changeset/fix-swift-secret-exposure.md` — specifies `"@cobaltcore-dev/aurora": minor`. The actual release mechanism is Changesets (`.github/workflows/release.yaml` → `changesets/action`, which reads the version strictly from the changeset file's frontmatter), not the conventional-commits/semantic-release that `docs/semantic_release.md` refers to (that file describes a mechanism that physically does not exist in `.github/workflows` — outdated documentation, a separate issue outside this PR). So the "BREAKING CHANGE" wording in the PR body **does not reach** the actual changelog/version bump — only the changeset file is read for that, and it says "minor" (see "Review", finding #2).

## Review

**Two findings scored ≥80 confidence.**

- **[100/100] The secret still leaks through `metadata` in the account response — the redaction is incomplete.** `parseAccountInfo` (`swiftHelpers.ts:104-111`) builds `metadata` with a generic loop over all headers with the `x-account-meta-` prefix, without any exclusions:
  ```ts
  // swiftHelpers.ts:104-111
  const metadata: Record<string, string> = {}
  headers.forEach((value, key) => {
    if (key.toLowerCase().startsWith("x-account-meta-")) {
      const metaKey = key.substring(15) // Remove "x-account-meta-" prefix
      metadata[metaKey] = value
    }
  })
  ```
  `x-account-meta-temp-url-key`/`-key-2` match this prefix — they will end up in `metadata["temp-url-key"]`/`metadata["temp-url-key-2"]` **with the real secret value**, even though the top-level `tempUrlKey` field is now correctly removed. `accountMetadataSchema` is a loose `z.record(string, string)` and will not filter anything. `getAccountMetadata` (`swiftRouter.ts:197`) returns this object to the client unchanged. This is exactly the same category of leak that the PR claims to have closed — just through a different field. For comparison, `parseContainerInfo` (same file, `swiftHelpers.ts:148`) has done this filtering correctly for a long time (code untouched by this PR): `if (!metaKey.startsWith("quota-") && !metaKey.startsWith("temp-url-") && !metaKey.startsWith("access-control-"))`. The account version never had such an exclusion — this PR was a chance to add it there as well, but it did not. Not a single new test checks `result.metadata` with temp-url headers set (all new assertions check only the top-level `tempUrlKey`/`hasTempUrlKey`), so CI will not catch this. 100/100 — not a hypothesis but a direct reading of the code: for any account with a TempURL key configured, the secret will arrive in every `getAccountMetadata` response, just by a different path.
- **[85/100] The changeset is marked `minor`, even though the PR itself calls the change breaking.** The PR description says outright: `"BREAKING CHANGE: accountInfoSchema and containerInfoSchema response structure changed - removed tempUrlKey, tempUrlKey2, syncKey fields, added hasTempUrlKey and hasSyncKey boolean flags"` — and this is indeed the case: `hasTempUrlKey`/`hasSyncKey` are declared required in both schemas (`z.boolean()`, not `.optional()`), not as an additive extension. Meanwhile `.changeset/fix-swift-secret-exposure.md` declares a `minor` bump. The release goes through Changesets, which reads the version only from the changeset file's frontmatter (`release.yaml` → `changesets/action`) — the "BREAKING CHANGE" text in the PR body in no way makes it into the final CHANGELOG or package version. A consumer of `@cobaltcore-dev/aurora` with a `^0.23.1` range will receive this as an ordinary "safe" minor update: TS code that accessed `.tempUrlKey`/`.tempUrlKey2`/`.syncKey` on the response types will stop compiling without any warning of a breaking release, and a loosely typed consumer will silently get `undefined` in those places at runtime. [`CLAUDE.md`](../../CLAUDE.md) specifically stresses that "commit type/scope directly affects the next version bump, so get it right" — the same principle applies to the changeset's severity. Not 100, because the "correct" bump for a purely internal response contract of a library is a matter of project convention rather than a strictly verifiable fact, but the risk for the package's consumers is real and easy to fix (change `minor` → `major` in the changeset).

Below is what was checked and did not reach the threshold:

- **[50/100, rejected as a nitpick] `redactAccountSecrets`/`redactContainerSecrets` check for the header's presence (`Headers.has()`), not the truthiness of its value — it used to be the other way round.** Before the PR the code did `const tempUrlKey = headers.get(...); if (tempUrlKey) {...}` — a falsy check of the value; an empty string was not considered a key. The new code (`secretHelpers.ts:34`, `:50-51`) uses `.has()`, which returns `true` even for a header with an empty value. If Swift ever returns this header empty (rather than simply not returning it, which is the usual OpenStack Swift behavior when a key is absent/deleted), `hasTempUrlKey`/`hasSyncKey` will lie to the client that a key is configured. That Swift actually produces such a response is not confirmed — rejected as an unlikely edge case rather than a confirmed bug.
- **[25/100, rejected] `isSecretHeader` is exported but not used anywhere outside its own test.** It looks like an unfinished generic sanitization path that was never wired into any real place where headers go to a log or a response — checked: no logging of raw Swift headers or of `AccountInfo`/`ContainerInfo` objects was found in `packages/aurora/src/server`. Dead code, not a standalone threat; rejected as a general code-quality concern not explicitly required by `CLAUDE.md`.
- **[0/100, rejected] Ceph/S3 parity.** Checked: Ceph EC2 credentials (`ec2CredentialRouter.ts`) already return the secret only once, at creation (`list` uses a secret-free schema, with an explicit comment in the code); a presigned URL is a derived, time-limited artifact, not a persistent secret. There is no parity gap with this PR; no additional fix on the Ceph side is needed.

---
Analyzed: 2026-08-13 · commit `a278e3f`
