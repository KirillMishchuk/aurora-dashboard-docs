# PR #1207 Code Review — Ceph Lifecycle Rules Management & Permission Controls

Repo: `cobaltcore-dev/aurora-dashboard`
Head SHA: `d01e15c4d7da21e0d0e73366ec2390f775da92ad`
Reviewed: 2026-08-28
Posted to PR: not posted — this run was requested as a local review only (see note at bottom)

Generated via the repo's `code-review` plugin methodology, replicated for this session: parallel Sonnet-equivalent reviewers (CLAUDE.md compliance, shallow bug scan, git-history context, code-comment compliance, prior-PR-feedback carryover) plus a dedicated security pass — using the repo's own `security-reviewer` persona — given this PR's stated purpose is permission controls. Every candidate finding was independently re-verified against the actual code before being kept; only findings that survived that verification and clear a high-confidence bar are reported below.

## This review supersedes the 2026-08-26 review at head `7edcce6754996071bed6f09f7789aa08a0ce78e4`

The PR moved on since then (`67b55149`, `3e6f9666` merges of `main`, plus `d01e15c4` "refactor(aurora): fixing AI issues"). Status of the two previously-posted findings:

- **"Create Lifecycle Rule" could silently delete unreadable rules"** (was Critical, confidence 100) — **FIXED.** `LifecycleRulesTab.tsx`'s Create button is now `disabled={mutationsBlocked}`, and a new warning `<Message>` explains why when it's blocked.
- **"Editing a lifecycle rule silently drops its object-size filter"** (was Critical, confidence 100) — still true in the codebase, but **out of scope for this PR**: `LifecycleRuleForm.tsx` no longer appears in PR #1207's diff against `main` at all (it's identical to `main` now — the file must have been touched by a different, already-merged PR, and this branch picked that state up by merging `main` in). This PR doesn't touch that file, so it can't be reviewed as part of it. Worth a separate fix, just not blocking this PR.

## Findings (confidence ≥ 80)

**1. This PR's own new documentation overstates the protection its permission checks provide — the underlying Ceph mutations have no matching server-side authorization** (confidence 80)
`packages/aurora/src/server/Storage/routers/permissionRouter.ts:23-24` (new doc comment, added by this PR)

The PR adds this comment to `permissionRouter.ts`:
> "These checks are UX-only: Ceph independently enforces access via EC2 credentials and bucket policy, so this gating never substitutes for real authorization."

That's an accurate description of the *client* side (the new `storage:*` checks only drive what buttons render), but the claimed backstop doesn't hold up under inspection. Every Ceph mutation router (`bucketPolicyRouter.ts`, `corsRouter.ts`, `lifecycleRouter.ts`, `versioningRouter.ts`, `ec2CredentialRouter.ts`, and the object router's `generatePresignedUrl`) is gated server-side only by `cephProtectedProcedure`, which checks *"does this user have some valid EC2 credential for this project"* — not the viewer/admin distinction the new permission map implies. Grepped every file under `Storage/routers/ceph/` and `Storage/cephProcedure.ts` for any policy/permission check inside a mutation handler: zero matches.

The comment's fallback — "bucket policy" — is opt-in and per-bucket. A bucket has no restricting policy by default, and this very PR is what makes bucket-policy and lifecycle management self-service in the UI. So for the common case (no custom bucket policy configured), there is no real enforcement distinguishing `storage_viewer` from `storage_admin` for: setting/deleting a bucket policy, setting/deleting CORS rules, setting/deleting lifecycle rules, toggling bucket versioning, or deleting/restoring an object version. Any authenticated user who can obtain an EC2 credential — itself gated at viewer tier, by design, per this same PR's doc comment — can call these tRPC mutations directly (devtools/curl with a valid session) and bypass every admin-only gate the UI now shows.

*Scope note:* the underlying routers and the `cephProtectedProcedure`-only gate predate this PR (they're not part of its diff) — this isn't a new hole introduced by the diff's own lines. What *is* new is the PR's own doc comment asserting an equivalence to real authorization that doesn't hold, for exactly the operations this PR's stated purpose is to protect ("permission controls"). Worth an explicit decision from the team: either the comment should be corrected to say plainly "no server-side enforcement exists yet for these operations," or (better, given the PR's own goal) the higher-blast-radius mutations added here — bucket policy, CORS, lifecycle, versioning, permanent version delete/restore — should get an actual `canUser`/policy check in the router, not just a client-side hint.

## Findings raised but filtered out (score < 80)

| Finding | File | Score | Why filtered |
| --- | --- | --- | --- |
| New doc comment claims read/list/view actions are "deliberately never gated anywhere in this file" / "the app" — contradicted by `SecurityGroupDetailsView.tsx` (`canViewRBAC`) and the flavors route (`canListSpecs`), which do gate view-only UI today | `PERMISSION_KEY_PATTERN.md`, `useCephPermissions.ts`, `permissionRouter.ts` | 50 | Real doc/code mismatch, but comment-only — doesn't change any actual gating behavior in this PR |
| No client-side mirror of server-side value bounds (tag Key ≤128/Value ≤256 chars, `Expiration.Days` ≤3650) — a rejected save surfaces a raw Zod error instead of inline validation | `lifecycleUtils.ts` | 30 | Already flagged by CodeRabbit on this PR as "Minor"; UX nitpick, not a correctness or security issue |
| `sortRules`/`rulesWithOriginalIndices`/`filteredRulesWithIndices` still computed inline every render, no `useMemo` | `LifecycleRulesTab.tsx:167-193` | 25 | Carryover from the #1178 review (tracked, "not started"); this PR rewrote parts of this file without addressing it, but the inefficiency itself predates this PR |
| "Download Object and View Versions are never gated" comment is slightly imprecise — View Versions is also conditioned on `versioningEnabled`, a feature-availability check, not a permission gate | `ObjectsTableView.tsx:159-160` | 25 | Accurate in the context it's written (a permissions docblock); minor wording nuance, not misleading in practice |
| `hasAnyBulkAction = permissions.canEmptyBucket` only (not `canDeleteBucket`) looked at first glance like it could hide bulk delete for admins who can delete but not empty | `Buckets/index.tsx:59` | 0 (false positive — verified and ruled out) | The bulk-actions menu this flag gates contains only "Empty Bucket(s)" — there is no bulk delete action anywhere in this menu. Per-row delete is gated independently on `canDeleteBucket` and unaffected. Confirmed by reading `BucketTableView.tsx` directly. |
| `storage:objects:create` and `storage:objects:update` both map to the same underlying `storage:object_update` policy rule | `permissionRouter.ts` | 0 | Pre-existing on `main`, unrelated to this PR's changes |

## Reviewers with no findings

- **CLAUDE.md compliance**: clean. Permission router stays inside the `createPermissionRouter` factory, no ad-hoc policy code; `apps/dashboard` only gained data (a `storage.json` policy entry), no logic; server domain folder structure untouched; all new user-facing strings go through `t`/`<Trans>` and are extracted into `en`/`de` locale files; every touched component has a colocated test file.
- **Shallow bug scan**: all 21 `PERMISSION_MAP` entries in `useCephPermissions.ts` cross-checked against `STORAGE_MAPPINGS` (`permissionRouter.ts`) and `storage.json` — no typos, no silent fallthrough. Every `canX` prop traced from hook to JSX gate across all ~12 touched components — no copy-paste mix-ups (e.g. a delete button gated on a create/update flag). `ObjectsTableView.tsx`'s 256-line refactor and the `lifecycleRouter.ts` rate-limit boundary fix (`>` → `>=`) both verified correct.
- **Git-history context**: no reverted fixes, no regressions against recent Ceph commits (`16a5a52d`, `0bfd055c`, prior #1178 fix batch). The new `useCephPermissions` hook actually improves on the only prior permission-hook pattern in the codebase (`useSecurityGroupPermissions`) by deriving the request/response arrays from one source-of-truth map instead of two independently-ordered lists.
- **Code-comment compliance**: this PR is unusually well-commented, and every checked claim (the `PERMISSION_MAP` "single source of truth" claim, the rate-limiter's "O(1), no full-map scan" claim, the "viewer-tier" rationale comments, the various "menu hidden when nothing is available" invariants) matches the code exactly — aside from finding #1 above and the minor doc-overclaim noted in the filtered table.

---

*Note: this review was generated in a local/Cowork session at the user's request ("put the result of review into pr-reviews folder") and, unlike the 2026-08-26 review, has not been posted as a PR comment. Let the user know if they'd like it posted to GitHub.*

*Analyzed: 2026-08-28 · commit `d01e15c4d7da21e0d0e73366ec2390f775da92ad`*
