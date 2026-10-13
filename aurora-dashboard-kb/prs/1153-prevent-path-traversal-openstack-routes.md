---
type: pr-report
date: 2026-08-12
status: merged
pr: [1153]
author: TilmanHaupt
branch: til-sec-3
---
# PR #1153: fix(core): prevent path traversal in OpenStack API routes

**Author:** TilmanHaupt · **Status:** merged 2026-08-12 (commit `9645ac6`; opened 2026-08-07)
**Branches:** `til-sec-3` → `main` · **Files:** 11 (+311/-28)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1153

## What was done

The PR closes a CWE-22 (path traversal) security finding in the BFF layer: some routers substituted a resource ID (received from the client via tRPC input) directly into the URL of the request to OpenStack without any check. A string like `"../admin"` as `flavorId`/`floatingip_id`/`securityGroupId` could take the request outside the expected endpoint. According to the PR description, 6 routers / 22 operations are affected; in fact, the diff changes 5 routers/helpers plus the shared error mapping.

The changes naturally fall into three groups:

**New security helper (`packages/signal-openstack`)** — a single point for validating and encoding a path segment. `encodeOpenstackPathSegment` rejects `.`, `..`, `./`, slashes and `?`/`#`, and encodes everything else via `encodeURIComponent`; `validateAndEncodeResourceId` is a wrapper over it specifically for resource IDs (a UUID or an arbitrary string like `m1.small` — a UUID is not required). Both functions and the `SignalOpenstackError` class itself (previously exported only as a type, now also as a value — otherwise the `instanceof` checks below wouldn't compile) are exported from the package.

**Wiring validation into consumers** — `flavorHelpers.ts`/`flavorRouter.ts` (Compute), `floatingIpRouter.ts`/`securityGroupRouter.ts` (Network), `projectRouter.ts` (Project), `pcaRouter.ts` (Services): every call that previously substituted a raw ID into the URL now first runs it through `validateAndEncodeResourceId` and uses the encoded result.

**Shared error mapping** — `errorHandling.ts`: `wrapError` (used by everyone who wraps a handler in `withErrorHandling`) now turns `SignalOpenstackError` into `TRPCError({code: "BAD_REQUEST"})` instead of letting it fall into a generic `INTERNAL_SERVER_ERROR`.

The branch's own history is telling (`git log main..pr-1153-head`): the first commit (`a2152ca9`) added validation but did not handle it uniformly; the second (`aebd0cba`) added the mapping in `wrapError` and handling in `projectRouter`; the third (`71c85454`) removed `validateUUID`, which had been added and immediately turned out to be unnecessary; the final one, `cee23177` (the current `HEAD`, also `headRefOid`), added the single-dot check (`segment === "."`, not caught originally) and added the missing try/catch in 8 functions of `flavorHelpers.ts`, where `SignalOpenstackError` had previously fallen through into a generic `INTERNAL_SERVER_ERROR` instead of `BAD_REQUEST`. That is, the PR has already fixed on its own exactly the two classes of defects ("the dot wasn't caught", "wrong error code") that are characteristic of the same author's two previous security PRs (#1144, #1148) — see the "What it affects" section.

## How it is implemented

The core is the new file `packages/signal-openstack/src/pathHelpers.ts`:

```ts
// packages/signal-openstack/src/pathHelpers.ts:16-37
export function encodeOpenstackPathSegment(segment: string, label = "Path segment"): string {
  if (!segment || typeof segment !== "string") {
    throw new SignalOpenstackError(`${label} must be a non-empty string`)
  }

  // Reject path traversal attempts
  if (segment === "." || segment.includes("..") || segment.includes("./")) {
    throw new SignalOpenstackError(`${label} contains path traversal characters`)
  }

  // Reject explicit path separators
  if (segment.includes("/")) {
    throw new SignalOpenstackError(`${label} must not contain slashes`)
  }

  // Reject URL special characters that could break path parsing
  if (segment.match(/[?#]/)) {
    throw new SignalOpenstackError(`${label} contains URL special characters`)
  }

  return encodeURIComponent(segment)
}
```

`validateAndEncodeResourceId` (`pathHelpers.ts:56-58`) is a thin wrapper for resource IDs, without requiring the UUID format (important: some IDs in the project are not UUIDs, e.g. `m1.small` for a flavor — see below).

In `packages/signal-openstack/src/index.ts:1-11` the export is added, and `SignalOpenstackError` is moved from a type-only to a value export (line 2 vs the old line 9) — without this, `error instanceof SignalOpenstackError` would not work in consumers.

Two different wiring styles in consumers:

*Explicit try/catch with its own `ERROR_CODES`* — `flavorHelpers.ts` and `flavorRouter.ts` (Compute). Example, `getFlavorById` (`flavorHelpers.ts:197-217`):

```ts
// packages/aurora/src/server/Compute/helpers/flavorHelpers.ts:205-217
let encodedId
try {
  encodedId = validateAndEncodeResourceId(flavorId, "Flavor")
} catch (error) {
  if (error instanceof SignalOpenstackError) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: ERROR_CODES.GET_FLAVOR_DETAILS_INVALID_ID,
      cause: error,
    })
  }
  throw error
}
```

The same pattern is repeated in 7 more functions of `flavorHelpers.ts` (`deleteFlavor`, `createExtraSpecs`, `getExtraSpecs`, `deleteExtraSpec`, `getFlavorAccess`, `addTenantAccess`, `removeTenantAccess`) and once in `flavorRouter.ts` (`getFlavorAccess`, lines 329-341). The difference between the first two (`getFlavorById`/`deleteFlavor`) and the remaining six is which `ERROR_CODES` constant labels the validation error: the first two use dedicated `*_INVALID_ID` codes, the other six use the same code that already labels the generic catch-all in the same function (example — `flavorRouter.ts:329-341`, `getFlavorAccess`):

```ts
// packages/aurora/src/server/Compute/routers/flavorRouter.ts:329-341
let encodedId
try {
  encodedId = validateAndEncodeResourceId(flavorId, "Flavor")
} catch (error) {
  if (error instanceof SignalOpenstackError) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: ERROR_CODES.GET_FLAVOR_ACCESS_FAILED,   // ← the same code already labels this function's generic catch
      cause: error,
    })
  }
  throw error
}
```

*No local try/catch, via the shared `withErrorHandling`* — `floatingIpRouter.ts`, `securityGroupRouter.ts`, `pcaRouter.ts` (all three domains already wrapped their procedures in `withErrorHandling`, so the wiring here is a one-liner):

```ts
// packages/aurora/src/server/Network/routers/floatingIpRouter.ts:108-113
return withErrorHandling(async () => {
  const { floatingip_id } = input
  const network = getNetworkService(ctx)

  const encodedId = validateAndEncodeResourceId(floatingip_id, "Floating IP")
  const response = await network.get(`${FLOATING_IPS_BASE_URL}/${encodedId}`)
```

A `SignalOpenstackError` thrown here reaches `wrapError` (`errorHandling.ts:19-26`) and is correctly turned into `BAD_REQUEST` — the chain was checked across all three files, no gaps found.

A special case is `projectRouter.ts:205-214` (`getProject`): instead of a `throw` on an invalid ID, the procedure silently returns `null`:

```ts
// packages/aurora/src/server/Project/routers/projectRouter.ts:205-214
let encodedId: string
try {
  encodedId = validateAndEncodeResourceId(input.projectId, "Project")
} catch {
  return null
}

const response = await callIdentityAPI(ctx.identityEndpoint, token.authToken, `projects/${encodedId}`).catch(
  () => null
)
```

At first glance this diverges from the "BAD_REQUEST everywhere" pattern, but according to the commit history (`aebd0cba`) and the rest of the function body, it matches the contract that already existed in this procedure, "any failure (network, parsing, HTTP error) → `null`" — i.e. not a new inconsistency but preservation of the old behavior.

`pcaRouter.ts` (Services) — the same one-line wiring via `withErrorHandling`, applied in 6 places (`getById`, `delete`, `importCertificate`, `listCertificates`, `createCertificate`, `getCertificate` — the last one with two IDs, authority and certificate, both validated separately).

Finally, `errorHandling.ts:19-26` — the mapping itself:

```ts
// packages/aurora/src/server/helpers/errorHandling.ts:19-26
// Map SignalOpenstackError (validation failures) to BAD_REQUEST
if (error instanceof SignalOpenstackError) {
  return new TRPCError({
    code: "BAD_REQUEST",
    message: error.message,
    cause: error,
  })
}
```

The docstring above `wrapError` (line 8) is updated in sync with the code — the stated behavior matches the implementation.

Tests: only `packages/signal-openstack/src/pathHelpers.test.ts` is added (unit tests of the helper — happy path, path traversal, URL special characters). None of the six existing colocated test files of the routers/helpers (`flavorHelpers.test.ts`, `flavorRouter.test.ts`, `floatingIpRouter.test.ts`, `securityGroupRouter.test.ts`, `projectRouter.test.ts`, `pcaRouter.test.ts`) is updated — the new behavior (BAD_REQUEST on an invalid ID) is tested only at the helper level, not through the tRPC procedures themselves.

## What it affects

`validateAndEncodeResourceId`/`encodeOpenstackPathSegment` are new exports; there are no external consumers outside this PR's files yet (verified with `git grep` across the whole monorepo at `pr-1153-head`).

More important is what the PR does **not** cover, even though the vulnerability pattern is the same (a raw ID in a URL template string, the input schema is just `z.string()` without constraints):

- **`packages/aurora/src/server/Compute/routers/imageRouter.ts`** — `memberId` (`types/image.ts:134`, `z.string()` without constraints) is substituted without validation into `v2/images/${imageId}/members/${memberId}` (`imageRouter.ts:746`, `:796` and several other places). `imageId` there is protected by `z.string().uuid()`, `memberId` is not.
- **`packages/aurora/src/server/Network/routers/rbacPolicyRouter.ts`** — `policyId` without validation in `${RBAC_POLICIES_BASE_URL}/${policyId}` (lines 99, 116).
- **`packages/aurora/src/server/Network/routers/securityGroupRuleRouter.ts`** — `ruleId` without validation in `${SECURITY_GROUP_RULES_BASE_URL}/${ruleId}` (line 31).

This is not a regression of this PR — it simply has, per its own description, a defined perimeter (6 routers/22 operations), and the three places above did not fall within it. Given that the same author fixed neighboring SSRF/path-related findings in the same series of PRs (#1144 — absolute URLs in image pagination, #1148 — Swift account SSRF), this looks like closing pentest findings one at a time rather than a systematic pass — it's worth explicitly asking the author/reviewers whether these three places are part of the next iteration.

Separately: the repository now has two security helpers with non-overlapping responsibilities and no cross-references — `packages/aurora/src/server/helpers/urlValidation.ts` (added by the same author two PRs earlier, to protect against SSRF via absolute URLs) and the new `packages/signal-openstack/src/pathHelpers.ts` (for path traversal via path segments). Different layers and different vulnerabilities, no conflict, but someone without context searching for "where in the project do we validate unsafe user input for OpenStack requests" will find only one of the two.

## Review

No issues with confidence ≥80 were found.

Closest to the threshold is the reuse of the same `ERROR_CODES.*_FAILED` code for two different failure reasons (ID validation and a regular network/backend failure) in six functions of `flavorHelpers.ts` and once in `flavorRouter.getFlavorAccess` (see the quotes above in "How it is implemented"): an independent check confirmed that at the `TRPCError.code` level (`BAD_REQUEST` vs `INTERNAL_SERVER_ERROR`) the distinction is preserved, but the client-side `useErrorTranslation` switches on the `ERROR_CODES` string, not on `code`, so in both cases the user will see the same "...Please try again" message — including for an invalid ID, for which retrying the request is pointless. The independent check's score is 75/100 ("will surface in practice on every request with an invalid ID", but not 100, since it does not break the protective mechanism itself; only diagnostics/UX suffer). The ≥80 threshold was not met, but the reviewer should keep it in mind — all the more so since in this same PR the author used a more precise pattern for `getFlavorById`/`deleteFlavor` (dedicated `*_INVALID_ID` codes), so the fix is simply to bring the other six functions to the same form.

Separately checked and rejected as not a bug: returning `null` instead of `BAD_REQUEST` in `projectRouter.getProject` on an invalid ID (consistent with the "any failure → null" behavior that already existed in this procedure); repeated validation of the same `flavorId` in `flavorRouter.getFlavorAccess` (first in the procedure itself, then again inside the called helper) — redundant but not incorrect; the hypothesis about bypassing the check via `%2e%2e` — does not work, `encodeURIComponent` escapes the `%` character itself before the string reaches the URL.

---
Analyzed: 2026-08-12 · commit `cee23177`
