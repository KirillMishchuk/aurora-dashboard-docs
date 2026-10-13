---
type: pr-report
date: 2026-08-28
status: merged
pr: [1221]
author: vlad-schur-external-sap
branch: vlad-missing-toasts-for-secgroups-and-storages
---
# PR #1221: feat(dashboard): add missing toasts for object-storage and security-groups

**Author:** vlad-schur-external-sap · **Status:** merged 2026-08-31 (created 2026-08-28)
**Branches:** `vlad-missing-toasts-for-secgroups-and-storages` → `main` · **Files:** 19 (+1068/-101)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1221

## What was done

Part of issue #1136 — it completes toast notification coverage (`NotificationManager`/Sonner-based `toast.success/error()`, the same pattern already used by Ceph/Swift/Images, see the report on #1132) for two features where some operations silently went through without feedback: Security Groups (the group itself + rules + RBAC policies for sharing with another project) and Ceph Bucket Policy (saving a bucket policy — previously only deletion had it).

**Security Groups.** Before the PR, the separate group details page (`useSecurityGroupDetails.ts`) showed no toasts at all for any of its three mutations (group update, rule create/delete) — only an error state in the form. The group list (`SecurityGroupsList.tsx`) already showed an inline error via `Message`, but not a toast, and did not show success in any way. RBAC policies (sharing a group with another project) were in the same state. The PR adds a toast to all six operations at once, using a single new builders file:

```tsx
// SecurityGroupToastNotifications.tsx:5-27
type ToastReturnType = { message: ReactNode } & NotificationOptions

export const getSecurityGroupDeletedToast = (name: string): ToastReturnType => ({
  message: <Trans>Security Group Deleted</Trans>,
  description: <Trans>Security group "{name}" was successfully deleted.</Trans>,
})
// ... symmetric Update/RuleCreated/RuleDeleted/RBACPolicyAdded/RBACPolicyDeleted builders
```

On the call side, for example `useSecurityGroupDetails.ts:99-113`, the toast for a successful rename takes the name from the submitted `variables`, falling back to the cached data if the field did not change (for example, when only a rule is added):

```tsx
// useSecurityGroupDetails.ts:99-113
const updateMutation = trpcReact.network.securityGroup.update.useMutation({
  onSuccess: (_, variables) => {
    utils.network.securityGroup.getById.invalidate({ project_id: projectId, securityGroupId })
    utils.network.securityGroup.list.invalidate()
    const { message, ...options } = getSecurityGroupUpdatedToast(
      variables.name || securityGroupQuery.data?.name || securityGroupId
    )
    toast.success(message, options)
    setEditModalOpen(false)
  },
  onError: (error) => {
    const { message, ...options } = getSecurityGroupUpdateErrorToast(error.message)
    toast.error(message, options)
  },
})
```

In `SecurityGroupsList.tsx` (the group list), success is now handled either via `.mutateAsync` + `try/catch` (update, create) or via a callback passed directly to `.mutate()` (delete) — two different styles for neighboring operations in the same file, but without a functional problem (see "Review"):

```tsx
// SecurityGroupsList.tsx:170-197
const handleDeleteSecurityGroup = (securityGroupId: string) => {
  setDeleteError(null)
  const sgName = securityGroups.find((sg) => sg.id === securityGroupId)?.name || securityGroupId
  deleteSecurityGroupMutation.mutate(
    { project_id: projectId, securityGroupId },
    { onSuccess: () => {
      const { message, ...options } = getSecurityGroupDeletedToast(sgName)
      toast.success(message, options)
    } }
  )
}

const handleUpdateSecurityGroup = async (securityGroupId, data) => {
  setUpdateError(null)
  const sgName = data.name || securityGroups.find((sg) => sg.id === securityGroupId)?.name || securityGroupId
  try {
    await updateSecurityGroupMutation.mutateAsync({ project_id: projectId, securityGroupId, ...data })
    const { message, ...options } = getSecurityGroupUpdatedToast(sgName)
    toast.success(message, options)
  } catch {
    // onError handles error state and UI feedback
  }
}
```

RBAC policies got a toast on add (`AddRBACPolicyModal.tsx:41-53`; the toast depends on `variables.targetTenant`, i.e. the value actually submitted) and on delete (`SecurityGroupRBACPolicies.tsx:58-84`) — on delete, success and error are handled in different places: `onError` toasts from the mutation config (:64-67), while the `onSuccess` toast is passed inline to `.mutate()` (:76-84) rather than in the config — asymmetric, but both branches actually fire.

**Ceph Bucket Policy.** Before the PR, `BucketPolicyModal` (the shared modal for viewing/editing/deleting a bucket policy) accepted `onSuccess?: (bucketName: string) => void` / `onError?: (...) => void`, without distinguishing whether the operation was saving or deleting the policy. The only consumer that actually passed these callbacks (`BucketModals.tsx`) therefore could not show different toast text for save/delete — and in practice did not show a toast on save at all, only on delete (via a separate `getBucketPolicyDeletedToast`). The PR extends the signature with a third parameter `action: "saved" | "deleted"`:

```tsx
// BucketPolicyModal.tsx:11-17, 119-140
interface BucketPolicyModalProps {
  isOpen: boolean
  bucketName: string
  onClose: () => void
  onSuccess?: (bucketName: string, action: "saved" | "deleted") => void
  onError?: (bucketName: string, errorMessage: string, action: "saved" | "deleted") => void
}
...
const setMutation = trpcReact.storage.ceph.bucketPolicy.set.useMutation({
  onSuccess: () => { utils.storage.ceph.bucketPolicy.get.invalidate(); onSuccess?.(bucketName, "saved"); handleClose() },
  onError: (error) => { onError?.(bucketName, error.message, "saved") },
})
const deleteMutation = trpcReact.storage.ceph.bucketPolicy.delete.useMutation({
  onSuccess: () => { utils.storage.ceph.bucketPolicy.get.invalidate(); onSuccess?.(bucketName, "deleted"); handleClose() },
  onError: (error) => { onError?.(bucketName, error.message, "deleted") },
})
```

and `BucketModals.tsx:113-129` branches on `action` to pick the right pair of toast builders (new `getBucketPolicySavedToast`/`getBucketPolicySaveErrorToast`, added to `BucketToastNotifications.tsx` alongside the existing `getBucketPolicyDeletedToast`/`getBucketPolicyDeleteErrorToast`). Along the way, `BucketToastNotifications.tsx` extracted the repeated inline type `{ message: ReactNode } & NotificationOptions` in all ~24 builders into a shared `type ToastReturnType` (pure refactoring, no behavior change).

The locale files (`packages/aurora/src/locales/{de,en}/messages.{po,ts}`) are a standard `lingui extract` regeneration for the new `<Trans>` strings; both catalogs are in sync, and there are no empty `msgstr ""`.

## How it is implemented

See the snippets above — all the work comes down to (1) a new file `SecurityGroupToastNotifications.tsx` with six builders modeled on the existing `BucketToastNotifications.tsx`/`ImageToastNotifications.tsx`/`ObjectToastNotifications.tsx`, (2) adding `onSuccess`/`onError` to the existing `useMutation` configs of five security-group components, and (3) adding a third parameter `action` to the `BucketPolicyModal` contract so that the single modal can report which of its two mutations fired. No new tRPC call was added — the PR only attaches UI feedback to already existing mutations.

Tests were added/extended for each new toast: two new test files (`useSecurityGroupDetails.test.ts`, `SecurityGroupToastNotifications.test.tsx`, `AddRBACPolicyModal.test.tsx`, `SecurityGroupsList.test.tsx` — in fact all of them are new), plus extensions of existing ones (`SecurityGroupRBACPolicies.test.tsx`, `BucketPolicyModal.test.tsx`, `BucketToastNotifications.test.tsx`). `BucketPolicyModal.test.tsx` explicitly checks the branching on `action` (`reports whether a policy was saved or deleted`, :277-286).

## What it affects

All six new exports of `SecurityGroupToastNotifications.tsx` are consumed only by files changed in this same PR (`git grep` across the monorepo at the head commit confirms it — 4 consumers, all in the diff). `BucketToastNotifications.tsx` already has a wider set of consumers (`CorsRulesTab/Table`, `LifecycleRulesTab/Table`, `index.tsx` re-exports everything via `export *`) — they are not touched by this PR and do not reference the new `getBucketPolicySavedToast`/`getBucketPolicySaveErrorToast`, so extending the file is safe for them.

`BucketPolicyModal` — the only component whose public signature (`onSuccess`/`onError`) actually changes — has **two** consumers in the monorepo, not one: `BucketModals.tsx` (updated by this PR) and `ObjectBrowserView.tsx:918-922` (Ceph Object Browser, **not touched by this PR**). The signature is widened rather than narrowed (a third parameter is added), so backward compatibility at the TypeScript/runtime level is not at risk — but it is worth recording for history: `ObjectBrowserView.tsx` does not pass `onSuccess`/`onError` to `BucketPolicyModal` at all (both props are optional), meaning that saving/deleting a bucket policy from the Object Browser showed no toast before the PR and still shows none after. This was never in the scope of this PR (the title and changeset talk only about security groups and object-storage lists/details, not the Object Browser) and is not a regression of this PR — just an adjacent gap in the same coverage that is worth keeping in mind for the next iteration of issue #1136.

Similarly in Security Groups: `createSecurityGroupMutation` (`SecurityGroupsList.tsx:117-133`) is the only one of the four group mutations that never got a success toast (only `setCreateError`/inline `Message` on error) — the PR does not touch this mutation's lines at all, so this is not a regression either, but an untouched remainder of the same task.

## Review

The following were run in parallel over the diff and the full files at the head commit (`e6332b18b`): CLAUDE.md compliance, bug-scan, historical context (`git log -p`/`git blame` across all 8 non-test sources, compared with how the analogous pattern was introduced in #1092/#1132 CORS/Lifecycle/Images), prior-feedback (GitHub's public REST API — `gh` is unavailable in the environment without a token, so unauthenticated `curl` to `api.github.com` was used instead of `gh pr list`/`gh api`; the rate limit is lower, but it took fewer than 60 requests) and comment-compliance.

**No issues found with confidence ≥80.**

Candidates that did not pass the threshold (for completeness, so they do not have to be searched for again):

- **Two identical comments `// onError handles error state and UI feedback`** (`SecurityGroupsList.tsx:166` in `handleCreateSecurityGroup` and `:195` in `handleUpdateSecurityGroup`) actually describe different levels of feedback: `onError` of the create mutation (:130-132) sets only the inline `setCreateError` state, and no toast on create is added in this PR at all; `onError` of the update mutation (:154-158) sets the inline state **and** toasts. Formally the comment is not wrong ("UI feedback" covers both cases), so it does not qualify as a violation — 25/100.
- **Showing both an inline `Message` banner and `toast.error` for the same error at once** (`SecurityGroupsList.tsx:141-144, 154-158`, similarly `SecurityGroupRBACPolicies.tsx`) — this is exactly the stated goal of the PR (to add toasts on top of the existing inline state, not replace it), not a deviation — 0/100.
- **A gap found by the previous prior-feedback run**: PR #1092 (CORS for buckets) received a review comment "report deletion as deletion, not as saving" for exactly the same shared save/delete modal pattern — this PR follows the same recommendation in its own code (`action: "saved" | "deleted"`), so this is not a gap but confirmation that the convention is followed — not reported as a finding, recorded for history.
- Not findings but out-of-scope gaps recorded for history (see "What it affects"): `ObjectBrowserView.tsx`'s `BucketPolicyModal` without `onSuccess`/`onError` and `createSecurityGroupMutation` without a success toast — both on lines this PR does not touch, so they are not reported as findings of this PR.

---
Analyzed: 2026-08-28 · commit `e6332b18becbef4b9934dbbe1b138b8cb7a81a35`
