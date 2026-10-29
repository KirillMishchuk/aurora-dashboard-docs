---
type: registry
---
# Follow-ups — single list

All deferred tasks for `aurora-dashboard` in one place: things recognized as valid during
review/analysis but deliberately not done in the PR where they came up.

**Maintenance rules**

- A new follow-up is created **here**. A plan, PR description, or reply to a reviewer keeps only a
  link of the form `FOLLOW-UPS.md` → item N — not a copy of the text.
- Numbering is continuous and permanent. An ID is never reused; a closed item is not deleted but gets
  the status `done` with a link to the PR.
- Items 1–11 came from the review of [PR #1331](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1331)
  and kept their numbers — the plan files for rounds 1–4 refer to them.

**Statuses:** `open` · `in progress` · `done` · `rejected`

## Summary

| # | Topic | Area | Status |
| --- | --- | --- | --- |
| 3 | Shared `ListObjectVersions` pagination helper | Version scans | open |
| 4 | Resume marker for `deleteNonCurrentVersions` | Version scans | open |
| 8 | Truncated page without `NextKeyMarker` deletes an incomplete group | Version scans | open |
| 9 | `deleteNonCurrentVersions` loses the report on a systemic failure | Version scans | open |
| 13 | Key order: UTF-16 instead of UTF-8 | Version scans | open |
| 18 | Move the page→key-group logic into a helper | Version scans | open |
| 20 | `nextContinuationToken` mixed up with `NextKeyMarker` | Version scans | open |
| 24 | `deleteNonCurrentVersions` has no page ceiling | Version scans | open |
| 11 | Empty Bucket without `storage:object_versions:delete` | Permissions | open |
| 12 | Destructive Ceph mutations are not authorized on the server | Permissions | open |
| 1 | Deleted tab ignores `isPartialScan` | Client | open |
| 6 | Memoization of lists in `ObjectBrowserView` | Client | open |
| 10 | Deleted tab should fail closed | Client | open |
| 15 | Pagination accumulator duplicates rows | Client | open |
| 16 | Six modals mounted with no way to open them | Client | open |
| 22 | `DeleteVersionModal` is titled "Delete Version" for a delete marker | Client | open |
| 23 | `GetBucketVersioning` called twice per bucket page load | Client | open |
| 28 | All tab hides live folders that have no placeholder object | Client | open |
| 5 | Raw `error.message` from the SDK reaches the UI | Contracts | open |
| 7 | `checkDeletedContentInputSchema.bucket` outside the shared schema | Contracts | open |
| 17 | `checkDeletedContent` does not limit response size | Contracts | open |
| 19 | `console.error` logs the entire SDK error object | Contracts | open |
| 29 | EC2 credential secrets leak into `signal-openstack` debug logs | Contracts | open |
| 30 | `if (!response.ok)` branches are unreachable, tests mask it | Contracts | open |
| 31 | `createPermissionRouter` catches the `policy-engine` error by message text | Contracts | open |
| 32 | Duplicate `GET /v3/credentials` when opening the credentials modal | Contracts | open |
| 40 | Bucket error screens are chosen by a substring of the server message | Contracts | open |
| 41 | S3 key metadata (`created_at`, `label`) in the EC2 credential blob | Contracts | open |
| 33 | Secret auto-reveal orchestration lives in the component, not in a hook | Client | open |
| 34 | `CephBuckets` rebuilt into a `let content: ReactNode` ladder | Client | open |
| 14 | `S3Client` and keep-alive agent created on every call | Transport | open |
| 21 | No `requestTimeout` and no `maxAttempts` tuning | Transport | open |
| 26 | `set` tests depend on the shared rate limit | Bucket policies | open |
| 27 | `Deny s3:*` is rejected even with a `Condition` | Bucket policies | open |
| 25 | Search query is not trimmed in client-side filters | Search | open |
| 35 | DataGrid header does not follow the Juno pattern in other lists | Lists | open |
| 47 | Search term is not trimmed in other client-side filters and pickers | Search | open |
| 2 | "Please" in the rest of the client | UI copy | open |
| 52 | Sentence-case and trailing-period empty-state titles elsewhere | UI copy | open |
| 36 | 409 on SG sharing is always shown as "already shared", including when the quota is exhausted | RBAC (SG) | open |
| 37 | Sharing a security group with several projects at once | RBAC (SG) | open |
| 38 | SG rules table has no Remote column | Client (SG) | done ([PR #1368](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1368), 2026-10-06) |
| 39 | Add Rule validation messages are not translated | Client (SG) | open |
| 42 | `TabNavigation` tabs: `tabStyle="content"` and controlled `activeItem` everywhere | Juno | open |
| 53 | Remaining `TabNavigation` users → `TabBar`/`TabBarItem` | Juno | open |
| 43 | SG details page state (tab, search, sorting, rule filters) in the URL | Client (SG) | open |
| 51 | SG Rules tab has no separate "no search/filter results" state | Client (SG) | open |
| 44 | Stale package READMEs (config, policy-engine, signal-openstack, e2e) | Documentation | open |
| 45 | `packages/aurora/README.md` + `.env.example`: removed `crossDomainCookie`, missing `cookieDomain`/`debug` | Documentation | open |
| 46 | Root `README.md`, `CONTRIBUTING.md`, release docs: stale prerequisites, port, Semantic Release | Documentation | open |
| 48 | Extend attached (`in-use`) volumes (Cinder 3.42) | Volumes | open |
| 49 | "Attached Volumes" section on Instance Details | Volumes | open |
| 50 | Availability-zone selection when creating a volume | Volumes | open |
| 54 | Ports/Routers docs say `danger` Badge for DOWN/ERROR; code uses `error` | Ports/Routers | open |
| 55 | Status is a Badge in Ports/Routers lists but plain text in details views | Ports/Routers | open |
| 56 | Router details answers 403 with an error page, not an info Message | Ports/Routers | open |
| 57 | Port details does not use the shared `TwoColumnDescriptionList` | Ports/Routers | open |
| 58 | Inconsistent empty-field placeholder (em dash vs en dash) in Ports views | Ports/Routers | open |
| 59 | Ports list layout differs from the maintainer's requested layout | Ports/Routers | open |
| 60 | Routers doc contradicts itself on 403 handling in the details view | Ports/Routers | open |
| 61 | 401 redirect can loop when only the OpenStack call is unauthorized | Ports/Routers | open |
| 62 | Ports/Routers by-ID procedures don't check the resource's `project_id` | Ports/Routers | open |
| 63 | `terminateUserSession` before the 401 redirect has no `.catch` | Ports/Routers | open |
| 64 | Container search sends `name` filter to Barbican, but Barbican ignores it | Key Manager | open |
| 65 | CreateContainerModal and DeleteContainerModal missing `disableCloseButton` | Key Manager | open |
| 66 | PR description claims "add/remove secret refs" but no such procedures exist | Key Manager | open |
| 67 | Server-side policy enforcement not mentioned in PR description | Key Manager | open |
| 68 | Navigation inconsistency: Key Manager detail views rely on breadcrumbs alone | Key Manager | open |
| 69 | Server-side policy enforcement is unique to Key Manager | Key Manager | open |
| 70 | CRUD acceptance partly met — Update UI missing, Container Edit scope dropped | Key Manager | open |
| 71 | Permission gating acceptance partly met — Update UI unreachable | Key Manager | open |
| 72 | Error handling acceptance partly met — Barbican error details dropped | Key Manager | open |

---

## A. Version scans and pagination (server)

### 3. Move the `ListObjectVersions` pagination loop into a shared helper

**Where:** `containerRouter.getState`, `versioningRouter.checkDeletedContent`,
`objectRouter.deleteNonCurrentVersions`, `deleteAll`, `deleteVersionsBulk` — six nearly identical
`while (true)` loops in the Ceph routers.

**What to do:** an async generator `scanObjectVersions(s3, { bucket, prefix, signal, maxPages })` in
`Storage/helpers/versionScan.ts` that yields pages and a single
`stopReason: "complete" | "aborted" | "page-ceiling" | "no-continuation-marker"`; the routers map
`stopReason` to their own flag. This also collapses three wordings of the comment and settles a shared vocabulary
(`isPartial` vs `isPartialScan`). The `MAX_SAME_MARKER` guard currently exists only in `objectRouter` — once
extracted, everyone gets it.

**Why deferred:** five of the six loops predate #1331. Extracting means rewriting `deleteAll` —
shipped code that permanently deletes objects — in the same diff as the new version-deletion
procedure. A reviewer would not be able to tell one from the other. It deserves its own PR and its own review pass.

**Source:** #1331 round 1 (the main tech debt according to the architecture review); again —
[`issues/issue-1004-comments.md`](issues/issue-1004-comments.md) (comment 3).

**Status:** open.

### 4. Resume marker for `deleteNonCurrentVersions`

**What to do:** return the stopping point and accept it as an optional input — then a retry costs
O(remainder) rather than O(entire history). Progress is monotonic: each deletion addresses a specific
`VersionId` and creates no new markers.

**Why deferred:** the partial-outcome message asks the user to run the action again, and the re-run
rescans the bucket from the first key. This is a feature, not a response to a review comment.

**Source:** #1331 round 1.

**Status:** open.

### 8. Do not delete an incomplete key group when a truncated page arrives without `NextKeyMarker`

**Where:** `objectRouter.ts:929`.

**What to do:** process the last group only if its current entry is a regular version; if
current is a delete marker, skip it, adding an entry to `errors` + `isPartial`. Mandatory condition:
the existing test `objectRouter.test.ts:1469` stays green — it covers the opposite risk
(silently dropping versions). A new test for the delete-marker case is needed.

**Why it matters:** otherwise an older version remains beyond the page boundary, it becomes current, and
the deleted object comes back to life. Probability is very low (requires an RGW response violating the S3 spec),
no data is lost — the version was already in the history.

**Source:** #1331 round 4, finding 3.

**Status:** open.

### 9. `deleteNonCurrentVersions` loses the report on previous pages on a systemic failure

**Where:** `objectRouter.ts:989` + `:196`.

**What to do:** wrap the per-page call in try/catch; when `deletedCount > 0`, return `isPartial`
+ an entry in `errors` instead of rejecting. Do not touch the `bulkDeleteItems` signature — the two other
call sites call it once and their behavior is correct.

**Why:** `bulkDeleteItems` judges a systemic failure by its local arrays, but is called
per page — a failure on the second page rejects the mutation, and neither the `deletedCount` of previous pages nor
"run it again" reaches the user.

**Source:** #1331 round 4, finding 4.

**Status:** open.

### 13. Key order is compared in UTF-16, while the API is ordered by UTF-8

**What to do:** a comparator based on `Buffer.compare`, shared by the group-deferral fallback branch and the folder
coverage check.

**Why:** `<` in JS compares UTF-16 code units, S3 orders keys by raw UTF-8 bytes.
They diverge on astral-plane characters versus U+E000–U+FFFF — emoji and CJK Ext-B in key names.

**Why deferred:** it touches the most delicate part of the new deletion path; it must not be mixed with the data-loss
fix — a failure would become ambiguous.

**Source:** issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

### 18. Move the page→key-group logic out of `deleteNonCurrentVersions` into a helper

**What to do:** page merging, byte-order sorting, grouping by key, merging the
carried-over group, and the keep/delete decision — pure functions of a single `ListObjectVersionsOutput` plus
carry, without the S3 client and `ctx`.

**Why:** the branch has already established where such code belongs — `Storage/helpers/` (it holds `folderPrefixOf`,
`isFolderCovered`, `longestCommonPrefix`). The cost of inaction is visible: most of the new tests in
`objectRouter.test.ts` build `mockSend` sequences for decisions that do not need S3
at all. Unlike item 3, it touches nothing that `deleteAll` relies on — it lands
independently.

**Source:** issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

### 20. `nextContinuationToken` mixed up with `NextKeyMarker`

**Where:** `objectRouter.ts`, the `showVersions` branch.

**What:** the `nextContinuationToken` field is assigned `response.NextKeyMarker`, and the same value goes
into `nextKeyMarker`. Related: when `delimiter` is set, versions are filtered on the client **after**
S3 has already cut the page at `MaxKeys` — a page may come back visually empty with
`isTruncated: true`.

**Why deferred:** none of the current call sites is affected (all use `delimiter: ""`), and the object
browser's per-tab branching remains consistent.

**Source:** issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

### 24. `deleteNonCurrentVersions` has no page ceiling

**What:** correctness does not need a ceiling (deleting by `VersionId` creates no new markers, there is no
rescan), and the per-key buffer + `isPartial` already bound what was dangerous: server memory and reporting
an incomplete cleanup as complete. What remains is wall-clock time: on a bucket with hundreds of thousands of non-current versions
the mutation runs for minutes inside a single request and may hit the proxy timeout.

**Why deferred:** `deleteAll` has exactly the same property, and it is already in production. Giving a ceiling only to the new
procedure would make it the only one able to stop halfway. Decide this together, and at the same time
decide whether this class of operations belongs behind the existing progress-subscription pattern.

**Source:** issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

---

## B. Permissions and authorization

### 11. Empty Bucket must not trigger version deletion without `storage:object_versions:delete`

**What to do:** pass `canDeleteVersion` into `EmptyBucketModal` and use it to gate both the automatic
`isBucketEmptyWithVersions` branch (`:77`, `:121`) and the checkbox (`:298-303`).

**Context:** this fixes `main`, not a change from #1331 — the same gate exists at `BucketTableView.tsx:255`.
This is aligning UI affordances, not a security boundary: there is no server-side permission check on Ceph procedures
at all (`cephProcedure.ts:107`), see item 12.

**Source:** #1331 round 4, finding 1.

**Status:** open.

### 12. Destructive Ceph mutations are not authorized on the server

**What:** `storage:object_version_delete` maps to `rule:storage_admin`, but this rule is read
only by the client — to decide what to render. `canUser` has not a single call site under `server/Storage`.
A project member without the admin role gets a hidden menu item and can still call the procedure
directly; `deleteAll`, `deleteVersionsBulk` and `containers.delete` are in the same position. The actual
protection rests entirely on the Keystone role mapping in RGW, which is a coarser gate than the policy
file describes.

**What to decide (one of two, both covering the entire Ceph surface):** either RGW is declared the authorization
boundary and oslo.policy is UI metadata, and this is written down once on
`cephProtectedProcedure` so it stops coming up in every review; or the domain needs a
`requirePermission` middleware applied to all destructive mutations at once.

**Source:** issue #1004, `comment-3-out-of-scope.md` (raised by review). Worth filing an issue.

**Status:** open.

---

## C. Client: object browser and modals

### 1. The "Deleted" tab ignores `isPartialScan`

**Where:** `ObjectBrowserView.tsx:361` — filters the tab only by `hasDeletedContent`. After the #1331 fix the
server honestly reports that the scan did not run to completion, but the tab does not read the flag: a folder with
unverified contents is simply not shown, and the user never learns that the answer is incomplete.

After item 28 the "All" branch no longer has its own check — it is fully decoupled from `checkDeletedContent`
(no request is sent there, `enabled: tab === "deleted"`) and does not read any `isPartialScan`. This makes this item
**the only remaining client-side consumer of the flag**
`checkDeletedContent.isPartialScan`: the contract and the server tests keep the field solely for its sake.

**What to decide:** whether to show partially scanned folders in the "Deleted" tab, and with what marker
("unconfirmed" / icon / tooltip). A product and design decision: the tab exists
precisely to show deleted content, and such folders mean "we don't know whether there is deleted content there".

**Do as a single task with item 10** and with finding 1 of round 3 (visible UI for scan state).

**Source:** #1331 round 1, decided on 2026-09-24 not to pull into the PR.

**Status:** open.

### 6. Memoization of lists in `ObjectBrowserView`

**Where:** `filteredObjects` (`:273`), `filteredFolders` (`:370`) and three sort expressions (`:374`,
`:411`, `:434`) — plain expressions, not memoized, over lists of up to 1000 items without virtualization.
They are recomputed on every render, including every keystroke in the search (the debounce delays the
request, but not the re-render). Pre-existing.

**Source:** #1331 round 1 (performance review).

**Status:** open.

### 10. The Deleted tab should fail closed

**Where:** `ObjectBrowserView.tsx:358`.

**What to do:** return `[]` in the Deleted branch instead of the neutral `allFolders` (fail-open remains
only there, since item 28 already moved the All branch to `return allFolders` for an entirely different reason —
the listing there is self-sufficient and the filter is not needed at all; the branches no longer share a common rationale).
Separately, in the same task: the mismatch between the query's `enabled` (`:167`, only `Enabled`) and the condition for showing the
tab (`:673`, `!== "Unversioned"`) — on a Suspended bucket the Deleted tab always shows all folders.
A falsely shown folder has no destructive actions (`ObjectsTableView.tsx:580-581`, `:481`) —
this is cosmetic.

An error from the `checkDeletedContent` query itself is also swallowed on the Deleted tab — not by the server (in
`versioningRouter.ts` #1331 removed the per-folder try/catch, a scan error is propagated outward via
`mapS3ErrorToTRPCError`), but by the **client**: only `data` is destructured from the hook (`ObjectBrowserView.tsx:157`),
the `error` field is not read, so a failed scan looks like "there is no deleted content".

**Do together with item 1.**

**Source:** #1331 round 4, finding 6.

**Status:** open.

### 15. The object browser's pagination accumulator can duplicate rows

**What:** after several pages have been loaded, invalidating `objects.list` refetches only the page that
the current token points to, and the accumulating effect appends it once more. Structural sharing
hides this until a mutation actually changes the data.

**The real fix:** `useInfiniteQuery` instead of the hand-rolled accumulator — i.e. rewriting the
data flow of this component.

**Source:** issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

### 16. Six modals are mounted in `ObjectBrowserView` with no way to open them

**What:** besides `DeleteVersionsModal`, six more modals hang there that nothing opens —
the live instances are owned by the bucket header. #1331 removed only the one it touched, not all seven.

**Source:** issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

### 22. `DeleteVersionModal` is always titled "Delete Version", including for a delete marker

**What:** the menu item that opens it does everything correctly —
`ObjectVersionHistoryModal` renders ``label={isDeleteMarker ? t`Delete Marker` : t`Delete Version`}``,
— and the modal receives `isDeleteMarker`, hiding the Date and Size rows based on it. But it is not
read at all for the text: the title, the confirm button and the body branch only on `isDeletingAllVersions`.
Clicking "Delete Marker" opens a dialog offering to delete a nonexistent "version".

**Estimate:** ten minutes (the same ternary in three more places) + `pnpm check-i18n` for the new strings.
Pre-existing at `dc918d47`.

**Source:** manual verification of issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

### 23. `GetBucketVersioning` runs twice per bucket page load

**What:** `containers.getState` needs the response to decide whether there is history worth scanning;
`ObjectBrowserView` separately queries `versioning.getStatus` to decide whether to enable
`checkDeletedContent`. The round 3 cleanup collapsed this for the bucket header and the empty-bucket modal — both
go through `useBucketInfo` — while the object browser keeps its own `useQuery` and was left untouched.
`getState` already returns a three-valued `status`, so the substitution is the same.

**Source:** manual verification of issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

### 28. The All tab hides live folders that lack a placeholder object

**Where:** `ObjectBrowserView.tsx`, `deletedFoldersList`, the `tab !== "deleted"` branch (on the #1331 branch —
lines 343-356, key line 352); the `checkDeletedContent` query — `:147-167`, `enabled` — `:164`.

**What:** a bug reported in feedback from a real user (eu-de-1): in a versioned bucket
a folder's contents are shown for a split second and then replaced with "No objects found.", and folders are visible only
in the Deleted tab. On top of the `ListObjectsV2` response, the All tab performs a second filtering of folders by
`checkDeletedContent` and drops any folder that has no zero-byte placeholder object `folder/`
(`folderMarkerVersionId === undefined`). The placeholder is created only by the "Create folder" button in Aurora
(`objectRouter.ts:806`), so every bucket populated by a third-party S3 client is affected —
Elektra, `s3cmd`, `rclone`, any SDK. The same condition hides a folder whose placeholder has a delete marker
even though a live object sits inside it. As a side effect, the header and the table disagree: `totalItemCount`
(`:409-410`) is computed from the unfiltered `allFolders`, so the counter shows the real number
above an empty table.

**What to do:** filtering on the All tab is redundant in principle — `ListObjectsV2` returns only
current versions, so a returned `CommonPrefix` already means live content, and a fully
deleted folder does not appear in the listing at all. The `tab !== "deleted"` branch reduces to `return allFolders`;
the `checkDeletedContent` query gets the condition `tab === "deleted"` in `enabled`. The change is purely
client-side; the server does not change.

**Follows [PR #1331](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1331):** both changes
land exactly on the lines that #1331 rewrites (`deletedFoldersList` → `useMemo` +
`statusByPrefix`, the `checkDeletedContent` input from `folders` → `prefix`, and the line it also added,
`if (status.isPartialScan) return true` inside the All filter), so a separate PR is branched off `main`
only after #1331 is merged. On the #1331 base the change does not get more complex — the entire All branch is removed.

**Implementation status:** the change is **implemented** but not yet committed. It was done locally on the branch
`kiryl-s3-version-pagination` (at the user's explicit instruction, without a separate branch off `main`);
after #1331 was merged into `main` on 2026-09-28 (`2feab20d`), the changes carried over onto `main` without conflicts and
sit there in the working tree. The base matched exactly: the `Ceph/Objects/` files in `main` are identical to the version of the branch
the plan was written against, so the line numbers in the plan remain correct. Re-verified on `main`
on 2026-09-28: the package's 5749 tests are green, `ObjectBrowserView.test.tsx` 43/43, typecheck/lint/format:check/
check-i18n clean. The item remains `open` because the PR has not been created yet — the blocker is lifted, and the branch can
be cut from `main` right now. Changes: `ObjectBrowserView.tsx` (the `tab !== "deleted"` branch
→ `return allFolders`; `enabled` of `checkDeletedContent` got `tab === "deleted"`),
`ObjectBrowserView.test.tsx` (test `:649-706` rewritten, #1331's test `:815-849` inverted while
keeping its test data, test `:778-813` re-commented, three new tests added),
changeset `.changeset/ceph-all-tab-folders-visible.md` (`patch`).

**Plan:** [`plans/2026-09-25-ceph-all-tab-folders-vanish.md`](./plans/2026-09-25-ceph-all-tab-folders-vanish.md)
— version 2, #1331 base, 6 steps, written **against the code of the #1331 branch** (`5b25aad0`), with line numbers from it;
it was implemented against exactly that branch. (The first revision of the same file was written against `main` line numbers and fully
rewritten on 2026-09-25, when it became clear that the change would land on the #1331 branch — section 0 of the file lists
which conclusions of the `main`-based revision no longer hold on the new base.) All consumers of
`folderDeletedStatus`/`statusByPrefix` were reviewed; Swift is not affected. Two existing tests failed intentionally and were
fixed: `:649-706` pinned the broken behavior and was rewritten; `:815-849`, added by #1331 itself,
was inverted while keeping its test data, rather than deleted.

**Related items:** neither item 1 nor item 10 is closed — both concern the Deleted branch, which the change does not
touch. But item 1 becomes more important (after the change `checkDeletedContent.isPartialScan` has no
client-side readers left — do not remove the field), and item 17 loses its main objection to the cheap
fix. The texts of items 1, 10, 17 were updated in this same registry edit.

**Source:** user feedback on Ceph, analysis on 2026-09-25; regression from `f66da80a` (PR #1121,
2026-08-07).

**Status:** open.

---

### 33. Secret auto-reveal orchestration lives in the component, not in a hook

**What:** in `ManageCredentialsModal.tsx` the secret-loading mechanics consist of two refs
(`isOpenRef`, `requestedSecretIds`), two state maps (`revealedSecrets`, `failedSecretIds`),
an effect that fires N parallel `mutateAsync` calls, manual cleanup in `handleClose`, and a write from
`createMutation.onSuccess`. This is the only non-trivial logic in the file and the only logic that
cannot be tested separately from rendering.

**Compared to:** in Ceph such logic lives in `Ceph/hooks/` — `useBucketInfo`,
`useCephPermissions`, `invalidateBucketQueries`, `invalidateVersioningStatusQueries`,
`invalidateCredentialQueries`.

**Side smell:** N parallel calls are funneled through a single `useMutation` handle, so
`revealMutation.isPending` / `.error` / `.reset()` reflect only the last call.
`revealMutation.reset()` in `handleClose` is effectively a no-op — late writes are guarded by
`isOpenRef` — but the handle stays in scope and looks meaningful.

**How to fix:** extract `useCredentialSecrets({ isOpen, projectId, credentials })`, returning
`{ secrets, failedIds, put(id, secret), clear() }`; the modal keeps the rendering and the two
user-facing mutations.

**Source:** triple review of the "S3 credentials management (Ceph)" task, second run, 2026-09-30,
architecture finding 5.

**Status:** open.

---

### 34. `CephBuckets` restructured into a `let content: ReactNode` ladder

**What:** `Ceph/Buckets/index.tsx` (458 lines) no longer uses early `return`s for the three
error branches — instead it assigns to `let content: ReactNode`, and the whole happy path moved into an
`else` one level deeper.

**Why it was done this way:** the credentials modal must survive the page switching to the
`NO_CEPH_CREDENTIALS` branch when the last key is deleted from within the modal itself. With early `return`s it
would be unmounted mid-operation.

**What's wrong:** the motivation is right, but the technique is not. `let content: ReactNode` appears nowhere else
in `packages/aurora/src/client`, and it is precisely the extra indentation level that produces most of the
noise in the diff.

**Options:** extract the three error branches into `Buckets/BucketsErrorState.tsx`, taking an
`onManageCredentials` callback (early `return`s come back, the file slims down); or lift
`credentialsModalOpen` and `<ManageCredentialsModal />` into
`storage/$provider/$storageType/index.tsx`, which already decides whether to render `<CephBuckets />`.

**Source:** triple review of the "S3 credentials management (Ceph)" task, second run, 2026-09-30,
architecture finding 6.

**Status:** open.

---

## D. Procedure contracts, schemas, logs

### 5. Do not pass the raw `error.message` from the AWS SDK through to the UI

**Where:** the degrade branch of `bulkDeleteItems` (`objectRouter.ts:199-204`) — `errors[].message` receives
the SDK message, which on transport failures contains the internal Ceph RGW host/IP.

**What to do:** keep the original in the server-side `console.error`, return a fixed text to the outside.
This fixes three consumers at once (`DeleteVersionsModal`, `Objects/DeleteVersionModal.tsx:64`,
`RestoreVersionModal.tsx:65`). In #1331 this was mitigated by limiting the list to three entries; the source was
left untouched.

The shared `s3ErrorMapper.ts:75-107` has the same source: for codes without special handling it returns the raw
`s3Error.message`. Via `containers.list` it reaches the "Failed to Load Buckets" screen
(`Ceph/Buckets/index.tsx`, `Status` body). Fix it in the same place as `bulkDeleteItems`: write the original message
to the log, return a fixed text to the client.

**Source:** #1331 round 1 (security review, Low); buckets screen — triple-review of the #1362 changes, 2026-10-07.

**Status:** open.

### 7. Align `checkDeletedContentInputSchema.bucket`

**Where:** `types/versioning.ts:143` — a bare `z.string().min(1)`, whereas the neighboring procedures
use `existingBucketNameSchema` with a length limit.

**Assessment:** not exploitable — bucket names go to the SDK as a command parameter and are escaped in the
path-style URL. Remove on the next edit of the file.

**Source:** #1331 round 1.

**Status:** open.

### 17. `checkDeletedContent` limits the request, but not the response

**What:** the input has a cap (`folders` — 1000), but the `prefix` mode — now the only one the
client uses — returns one entry for every direct-child folder found by the scan, up to the
~20,000 entries that the page cap allows. The client only looks at the prefixes it has actually
loaded; the rest is wasted payload. It is the same "cost grows with the bucket, not with the question" shape
that #1331 fixed on the scan side, but on the other side of the same procedure.

**Caution (was — lifted by item 28):** the obvious cheap fix — not returning entries in the fully
default state — was rejected during the analysis before item 28: a missing entry made the All tab
*show* the folder, while a present entry without `folderMarkerVersionId` made it *hide* it, and folders in exactly
that state did occur (a lone non-latest delete marker and no folder-marker object).
After item 28 this objection is lifted entirely: the All tab does not read the `checkDeletedContent` response at all
(the request is not sent there), and in the Deleted tab a missing entry and an entry in the default
state yield the same result — `hasDeletedContent` is falsy, the folder is not shown
(`ObjectBrowserView.tsx:361`). The cheap fix became acceptable, but was not pulled into item 28 — it is a separate
change to the procedure contract (the response schema itself, server tests, its own changeset), not a client-side
edit. An explicit response cap with an explicit "unknown" for the cut-off part remains an alternative if they decide not
to take the cheap option.

**Source:** issue #1004, `comment-3-out-of-scope.md`; clarification — plan [`plans/2026-09-25-ceph-all-tab-folders-vanish.md`](plans/2026-09-25-ceph-all-tab-folders-vanish.md), section "Answers", item 6.

**Status:** open.

### 19. `console.error` logs the entire AWS SDK error object

**What:** the new calls write the whole caught error object rather than a selected set of fields. Server
only, it does not reach the client, and what does reach it is sanitized by `mapS3ErrorToTRPCError` — but this is yet
another instance of a pattern that already exists in half a dozen places under `server/Storage`. They all need to be changed
at once.

**Source:** issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

### 29. EC2 credential secrets end up in `signal-openstack` debug logs in plain text

**What:** with debug logging enabled, the bodies of requests to and responses from Keystone are written to the log
verbatim, along with EC2 credential secrets. Redaction does not save them: `redactSensitiveData`
(`packages/signal-openstack/src/logger.ts:54-95`) matches only **key names** and never looks inside
a string value. `body` (`client.ts:124-132`) and `bodyPreview`
(`client.ts:155-192`) are plain strings, they do not match the `password|token|secret|key|authorization` patterns,
and go to the log as is. The Keystone `blob` is also a string, containing
`{"access":…,"secret":…}`; the credential JSON is shorter than the 500-character limit, so the secret ends up in the log
in full.

**When enabled:** `packages/aurora/src/server/context.ts:105` —
`debug: config.debug ?? process.env.NODE_ENV !== "production"`. That is, **by default everywhere
except strict `NODE_ENV=production`**: dev and most staging/QA deployments.

**Who is affected:** anyone with access to the BFF process logs or to the log aggregator
obtains live S3 keys with read and write permissions on the project's buckets.

**Where it came from:** the root cause is pre-existing, `packages/signal-openstack` was not changed. But the credential
management UI widens the channel: `reveal` is a new path that the user triggers themselves, as many
times as they like, each time pulling the secret through `bodyPreview`; and the limit pre-check in
`create` now requests the blobs of **all** of the user's existing credentials just to
count them — previously `create` did not read other blobs at all.

**How to fix:** in `redactSensitiveData`, try to parse string values as JSON and
redact the nested content (reassembling afterwards), plus add `/blob/i` to `SENSITIVE_PATTERNS`.
This covers `body`, `bodyPreview`, and future cases in all domains. Separately, reconsider
the `debug` default in `context.ts:105`: enabling verbose logging with request bodies everywhere
except strict production is risky in itself.

**Why it was not done right away:** the change goes beyond the `aurora` package and changes the shape of the debug logs
of all of `signal-openstack`; the decision to postpone was made deliberately during the triple-review analysis
(2026-09-29).

**Source:** triple-review of the plan [`plans/2026-09-29-ceph-s3-credentials-management-ui.md`](plans/2026-09-29-ceph-s3-credentials-management-ui.md),
a High-severity finding by the security reviewer; the mechanism was re-verified against the code.

**Status:** open.

### 30. `if (!response.ok)` branches are unreachable across the whole repository, and the tests mask it

**What:** `request()` in `packages/signal-openstack/src/client.ts:194-207` throws `SignalOpenstackApiError`
on any non-2xx and never returns `{ ok: false }`. So every check of the form
`if (!response.ok) { ... }` in the routers is dead code: control never reaches it. The codes are actually
mapped by `openstackErrorMiddleware` (`server/trpc.ts:15-60`), and correctly so: 401 →
`UNAUTHORIZED`, 403 → `FORBIDDEN`, 404 → `NOT_FOUND`, 400 → `BAD_REQUEST`. So the behavior is
correct; only the message text differs — the local branch would have written its own, while the client
receives the middleware's wording.

**Why it persists:** the unit tests mock the identity/S3 service with objects that **resolve** with
`{ ok: false, status: N }` instead of throwing. With such a mock the dead branch executes, and
the test is green — that is, the tests confirm a contract that does not exist in production. This also masks the
reverse: code that relies on the local branch behaves differently in production than in tests.

**Where it surfaced:** `ec2CredentialRouter.fetchOwnedCredential` — there, because of this, the declared
idempotency of `delete` did not work (deleting an already deleted credential returned `NOT_FOUND` instead of
`{ success: true }`). Fixed locally in the S3 credentials management task: the 404 is now caught
where it arrives. The remaining occurrences — including `list` and `create` in the same file — were left
as is, because they all need to be fixed at once together with the mocks.

**Also:** `createPermissionRouter` (after narrowing the `catch` by message) swallows not only
a missing top-level rule, but also a nested undefined rule — `policyEngine.ts`
throws the same text for those — as well as a typo in the `rule` field inside `mappings`. Both
degrade to "`false` forever" with a single `console.error`. Validation of rule names at startup
was deliberately not done: `policyDir` is set by the consumer, and a startup crash for an operator with an
older policy file would be worse than a hidden button. A reasonable option is a warning in the log when
the router is created, but that is a separate pass over the shared factory.

**Source:** code review of the "S3 credentials management (Ceph)" task, 2026-09-29, findings 3, 4 and 7;
the mechanism was re-verified against `client.ts` and `trpc.ts`.

**Status:** open.

---

### 31. `createPermissionRouter` recognizes a `policy-engine` error with a regex on the text

**What:** `server/policies/createPermissionRouter.ts:13` holds
`const MISSING_RULE_MESSAGE = /not found and no _default rule available/` and matches
`error.message` against it. The string comes from `packages/policy-engine/src/policyEngine.ts` (three places:
155, 272, 398).

**Why this is not "oh well":** the docblock justifies the technique by saying the engine throws a plain
`Error` and offers no way to ask whether a rule exists. That is true, but `policy-engine` is not a third-party
dependency; it is a sibling package in this same monorepo, fully under the team's control. It should be fixed on
that side of the boundary.

**What it risks:** a change of wording in `policy-engine` or a new throw site with different text
will silently bring back the failure of the whole `canUser` batch — exactly the regression the change
was made to eliminate. The test in `packages/aurora` will not catch this: it mocks the engine and hardcodes the same string.

**How to fix:** export a `RuleNotFoundError` subclass from `@cobaltcore-dev/policy-engine`
(or a `hasRule(name): boolean` predicate) and check via `instanceof`. The behavior and the already
written docblocks stay as they are. The change touches two packages, so it is a separate pass.

**Source:** triple-review of the "S3 credentials management (Ceph)" task, second run, 2026-09-30,
architecture finding 3.

**Status:** open.

---

### 32. Opening the credentials modal costs two nearly identical `GET /v3/credentials`

**What:** `ManageCredentialsModal` starts two requests at once: `ec2Credentials.list` and
`containers.status`. The first goes to Keystone for `credentials?user_id=…&type=ec2`
(`ec2CredentialRouter.ts`). The second is built on `cephProcedure`, whose `cephCredentialMiddleware`
(`Storage/cephProcedure.ts:72-94`) unconditionally calls `resolveEC2Credential`
(`Storage/middleware/resolveEC2Credential.ts:44-47`) — the very same request — and the result
is thrown away, except for `.length > 0` for the boolean `hasCredentials`.

**Why it turned out this way:** the modal needed `containers.status` only for `endpoint`/`region`,
and those come from `resolveS3Config`, which does not depend on credentials at all. But the procedure sits on
`cephProcedure`, and the middleware runs in full.

**How to fix:** split `cephProcedure` so that a request that needs only
`resolveS3Config` does not pull in `resolveEC2Credential`. Or move `endpoint`/`region` out of the
credential-resolving procedure altogether — they are deployment constants from `AuroraServerConfig`, and
delivering them through such a channel is heavy.

**Nearby:** `resolveEC2Credential` makes this uncached request on **every** ceph request and
filters by project only in-process, so the response carries the user's credentials across all of their
projects. The limit of 2 keys per project doubles that volume. Small in itself, but if
credential resolution ever calls for a request-scoped cache — start here.

**Source:** triple-review of the "S3 credentials management (Ceph)" task, second run, 2026-09-30,
performance finding 1 and architecture finding 7 (the `cephProcedure` part).

**Status:** open.

### 40. Bucket error screens are selected by a substring of the server message

**Where:** `Ceph/Buckets/index.tsx`, the `containers.list` error branch. The "Access Denied" and "S3
Authentication Failed" screens are selected via `errorMessage.includes("Access denied")` and
`includes("Invalid access key")`. These are texts from `s3ErrorMapper.ts:80-89`. If the wording on the
server changes, both screens will silently fall through to the generic "Failed to Load Buckets".

**What to do:** distinguish by `error.data?.code`. The mapper (`s3ErrorMapper.ts:26-31`) already sets
`FORBIDDEN` for `AccessDenied`/`AllAccessDisabled` and `UNAUTHORIZED` for `InvalidAccessKeyId`,
`SignatureDoesNotMatch`, `TokenRefreshRequired` and `RequestTimeTooSkewed`. These are exactly the groups that
are currently caught by substring.
While at it, remove "may be expired" from the text at `s3ErrorMapper.ts:89`: EC2 credentials have no expiration.

**Why not done right away:** it was like this before #1362; the PR changed only the look of the screens, not how they are selected.

**Source:** triple-review of the changes addressing #1362 feedback (security and architecture, Low), 2026-10-07.

**Status:** open.

### 41. S3 key metadata (`created_at`, `label`) in the EC2 credential blob

**What:** an EC2 credential in Keystone has neither a name nor a creation date: only `id`, `user_id`, `project_id`,
`type`, `blob`. So in Manage Credentials keys can be told apart only by access key, and "newest first"
works only within a single opening of the modal (the `createdIds` state in `ManageCredentialsModal.tsx`).

**How:** put the metadata into the blob that `ec2CredentialRouter.create` builds:
`{ access, secret, created_at, label }`. `list` returns them without the secret, the UI sorts by `created_at`
and shows the name; renaming is `PATCH /v3/credentials/{id}` with the same `access`. Keys created
outside Aurora (CLI, `OS-EC2` — 32 hex) don't have these fields, and the UI must show "unknown".

**Not like this:** do not embed data into the access/secret themselves. The secret is an HMAC key; anything embedded in it reduces
its strength. The access key is public: it goes into the `Authorization` header of every S3 request and is written to RGW logs;
it can be forged by creating a credential in "our format" via the Keystone API; and the embedded data cannot be changed, because
the credential id is sha256(access).

**Verify on a test environment first:** that Keystone (`POST`/`PATCH /v3/credentials`, EC2 authentication
via `s3tokens`) and RGW don't break with extra fields in the blob. As far as is known, Keystone reads from
the blob only `access`, `secret` and the optional `trust_id`/`app_cred_id`, but on a real deployment
this has not been verified (also recorded in the out of scope section of issue #1358).

**Why not done right away:** new functionality (key names are explicitly out of scope in #1358), requires
verification on a test environment.

**Source:** discussion of the feedback on #1362 (ordering of new keys, key format), 2026-10-07.

**Status:** open.

---

## E. S3 client and transport

### 14. New `S3Client` and keep-alive agent on every procedure call

**What:** `getCephClient()` constructs a client on every call, and nothing ever destroys it —
there is no connection reuse between requests, and idle sockets pile up. A small cache keyed
by credentials is needed.

**Coupling:** do it together with any change to SDK timeouts (item 21) — a shared agent changes what
`connectionTimeout` can actually affect.

**Source:** issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

### 21. No `requestTimeout` and no `maxAttempts` tuning on the shared S3 client

**What:** `s3Client.ts` does not set `requestTimeout` and leaves `maxAttempts` at the default (3), multiplying
each listing loop by up to three. `connectionTimeout: 5000` was added in #1331 precisely because it
only bounds TCP connection establishment and is safe for streams.

**Why not done:** `requestTimeout` in `@smithy/node-http-handler` is a socket inactivity timeout, and
the same client is shared with the streaming upload/download paths. Narrowing `maxAttempts` globally would reduce
the resilience of object transfers. Both require their own investigation against the installed SDK version.

**Source:** issue #1004, `comment-3-out-of-scope.md`.

**Status:** open.

---

## F. Bucket policies

### 26. `set` tests in `bucketPolicyRouter.test.ts` depend on the shared rate limit

**What:** `checkPolicySetRateLimit` is module-level, keyed by `${projectId}:${bucketName}`, with a limit of 10 per 5 minutes,
and it fires **before** any policy validation: even a call that will later be rejected by validation
consumes the budget. The existing `set` block sits at exactly 10 calls on `my-test-bucket`, so every
new test there silently pushes the tests further down the file into `TOO_MANY_REQUESTS`.

**Current workaround:** new tests use their own bucket names (documented in the code and in the
PR description).

**What to do:** reset the rate-limit key between tests. Keep in mind the related vitest gotcha:
`vi.clearAllMocks()` does not clear the `mockResolvedValueOnce`/`mockRejectedValueOnce` queue, and
an unconsumed `once` value leaks into the next test.

**Source:** PR ceph-bucket-policy-tenant-principals,
[`pr-descriptions/pr-1337-description.md`](pr-descriptions/pr-1337-description.md).

**Status:** open.

### 27. `validatePolicySemantics` rejects `Deny s3:*` even when narrowed by a `Condition`

**Where:** `bucketPolicyRouter.ts:101-113` — any `Deny` with `Action` `*` or `s3:*` is rejected
unconditionally.

**What:** this is a legitimate and common pattern when the deny is narrowed by a `Condition` (for example, "deny
everything except requests from a specific VPC/IP"). Currently such a policy can be neither created nor, worse,
saved after editing — even though RGW accepts it.

**Why deferred:** the multi-tenant principals fix was about something else; changing a rule that protects against
the bucket owner locking themselves out must be done separately and with tests for both outcomes.

**Source:** PR ceph-bucket-policy-tenant-principals.

**Status:** open.

---

## G. Lists and search

### 25. Search query is not trimmed in the Ceph and Swift client-side filters

**Where:** `Ceph/Buckets/index.tsx:200` and `Swift/Containers/index.tsx:223`:

```ts
const filteredBuckets = (buckets || []).filter((bucket) =>
  bucket.name.toLowerCase().includes(searchParam.toLowerCase())
)
```

**What:** nearby, the counter is enabled based on `searchParam.trim()` (`:384`), and the server-side
`filterBySearchParams` (`server/helpers/filterBySearchParams.ts:20-23`) **does** trim. As a result,
searching for `"bucket-1 "` (a trailing space is common when pasting) finds nothing, and a query consisting only of
spaces shows a "3 buckets" header with zero rows in the table. The space reaches the URL untrimmed:
`handleSearchChange` commits `value || undefined`, and `" "` is truthy.

**What to do:** trim the term in both predicates. At the same time, fix the misleading comment
in `Ceph/Buckets/index.test.tsx` — `// Plural 'one' form: "1 of 3 bucket" (singular)`: what renders is
"1 of 3 buckets", and that is correct; the test's regex simply isn't anchored.

**Context:** not a regression of PR #1335 — the code was restored by the revert byte for byte as it was before
#1320. But relative to `main` with server-side search it is a step back, which is why it is recorded.

**Source:** Copilot on [PR #1335](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1335),
finding 1 (finding 2 about `Plural` was rejected — the suggested change would have produced "1 of 3 bucket").

**Status:** open.

---

### 35. DataGrid header does not follow the Juno pattern in the other lists

**Where:** `network/floatingips/-components/FloatingIpsList.tsx` — `<div className="relative">`, header zones
are not wrapped in `Stack` (exactly as it was in Security Groups before #1323); `storage/-components/Ceph/Buckets/index.tsx`,
`Ceph/Objects/ObjectBrowserView.tsx`, `Swift/Objects/index.tsx` — `<div className="relative">` and a single
`Stack direction="vertical"` without separation into an outer Stack and a header Stack. While at it, also check
`Swift/Containers/index.tsx`, `compute/images/-components/List.tsx`, `compute/flavors/-components/List.tsx` —
they also have `div.relative`.

**What:** bring them to the structure from #1323: `Stack direction="vertical" className="juno-pattern-datagrid-outer"` →
`Stack direction="vertical" className="juno-pattern-datagrid-header"` (zones 1–3) + `DataGrid` as a direct sibling;
remove `div.relative` if nothing inside is positioned relative to it (in Juno 9.4.0 `Modal`, `PopupMenu`,
`Select`, `ComboBox` are portaled, and `SearchInput` is itself `relative`). The marker classes exist only in Juno `main` stories,
there is no CSS behind them — safe as of 9.4.0.

**Why not done right away:** per the #1323 decision, it was limited to Security Groups; the other lists go in a separate PR,
so as not to bloat the diff of epic #1327 and to verify each list separately.

**Source:** plan for epic #1327 (task #1323), 2026-09-30.

**Status:** open.

---

### 47. Search term is not trimmed in the other client-side filters and pickers

**Where:** under `packages/aurora/src/client/routes/_auth/projects/$projectId/`:
- `storage/-components/Ceph/Buckets/CorsRulesTab.tsx:193-196`, `Ceph/Buckets/LifecycleRulesTab.tsx:193-195`
- `network/securitygroups/$securityGroupId/-hooks/useSecurityGroupDetails.ts:81-82`, `-components/-details/SecurityGroupRBACPolicies.tsx:100-104`
- pickers: `storage/-components/Ceph/Objects/hooks/useBucketSearch.ts:45-47`, `Swift/Objects/CopyObjectModal.tsx:138`, `Swift/Objects/MoveRenameObjectModal.tsx:142`, `Swift/Containers/EditContainerMetadataModal.tsx:107`

(line numbers as of `main` @ `6a8dad69`)

**What:** the same defect as item 25, on other screens: these filters match the raw search string, so a trailing space finds nothing and a term of only spaces hides every row. The pickers check `debouncedSearch.trim()` to decide whether to filter, but the predicate itself uses the untrimmed string.

**How to fix:** use `term.toLowerCase().trim()` in each predicate, as `filterBySearchParams` and the Objects pages do, and add whitespace tests per component. Trim in the predicate, not where the term is committed (see the Decisions of the source plan: trimming at commit eats spaces while typing).

**Why not done right away:** item 25's plan is limited to the Ceph Buckets and Swift Containers list pages; these are different screens and components.

**Source:** planning of follow-up 25, 2026-10-12.

**Status:** open.

---

## H. UI copy

### 2. "Please" in the rest of the client

**What:** ~70 occurrences violating the repository's own rule
`.github/copilot-instructions.md:559`, mostly `client/utils/useErrorTranslation.ts`
(Compute/flavors) and `client/components/Errors/RouteError.tsx`.

**How to do it:** a separate `style(portal):` PR. Reason for splitting it out: every edit changes the msgid, and
`pnpm check-i18n` bloats the `.po` diff.

**Source:** #1331 round 1, finding 6 (three strings in `EmptyBucketModal` that the PR itself rewrote
were fixed there).

**Status:** open.

---

### 52. Sentence-case and trailing-period empty-state titles elsewhere in the client

**Where:** for example `storage/-components/Ceph/Objects/ObjectsTableView.tsx:389` (`No objects found.` with the generic
`There are no items to display.`), `storage/-components/Ceph/Objects/ObjectVersionHistoryModal.tsx:133`
(`No Versions Found for This Object.`), and `CorsRulesTable.tsx:127` / `LifecycleRulesTable.tsx:137` (trailing periods).

**What:** these `Status` titles break the title-case convention that the Juno `Status` prop docs ask for, or repeat the
generic default body.

**How to fix:** audit the `Status` titles in `packages/aurora/src/client`, change them to "No X Found" title case with
specific bodies, and run `pnpm check-i18n`. Each msgid change bloats the `.po` diff, so this should be a separate PR
(as in item 2).

**Why not done right away:** these are in other domains (storage), outside #1388 and epic #1327.

**Source:** plan [2026-10-27-security-group-empty-state-copy.md](./plans/2026-10-27-security-group-empty-state-copy.md) (issue #1388)

**Status:** open.

---

## I. Security Groups: sharing (RBAC)

### 36. A 409 when sharing an SG is always shown as "already shared", including when the quota is exhausted

**Where:** `packages/aurora/src/server/Network/helpers/rbacPolicyHelpers.ts:62-66`, `RBACPolicyErrorHandlers.create`.

**What:** any 409 response from `POST /v2.0/rbac-policies` is turned into "This security group is already
shared with the specified project". As far as is known about Neutron, a quota overrun (`OverQuota`)
is also returned as 409 Conflict. The `rbac_policy` quota defaults to 10 and is shared per project: across all
RBAC rules for groups, networks and QoS combined. So when the quota is exhausted, the user sees the wrong
reason. Not verified on DevStack.

**How to fix:** first verify on DevStack: set the `rbac_policy` quota = 1 and share a group
with two different projects. If confirmed, distinguish the cause of the 409 by the Neutron response body
(`NeutronError.type`: `OverQuota` vs. conflict/duplicate) and show a separate message about
the quota. Add tests for both branches. Also check `update` while at it: it has the same 409.

**Why not done right away:** outside epic #1327. It surfaced while analyzing sharing limitations and has nothing to do
with the list filter.

**Source:** analysis of RBAC sharing limitations in the session on epic #1327, 2026-10-01.

**Status:** open.

### 37. Sharing a security group with several projects at once

**Where:** `Network/routers/rbacPolicyRouter.ts` (`create` accepts a single `targetTenant`),
`securitygroups/$securityGroupId/-modals/AddRBACPolicyModal.tsx` (a single "Target Project ID" field).

**What:** in Neutron, one RBAC rule is one "object → one project" pair. Sharing with N projects
means N rules. As far as is known, there is no bulk creation for `rbac-policies` (not verified).
Currently the user repeats the modal N times. Feature: accept a list of project IDs and create the rules
in a batch. Options: on the client (N `create` calls) or via a `createMany` procedure in the BFF with a result for
each project.

**Constraints to take into account:** the operation is not atomic, partial success is needed ("7 shared,
3 failed: quota/duplicate"). The `rbac_policy` quota is shared per project (see item 36); without item 36, hitting
the quota will look like "already shared". Permissions are the same as for single sharing
(`network:rbac_policies:create` → `create_rbac_policy`, role `network_admin`). ID validation is
the same as in the modal (`isValidProjectID`), per element.

**Why not done right away:** this is a new feature, not a bug of epic #1327. First a product answer is needed
on whether it is wanted. Do it after item 36.

**Source:** analysis of RBAC sharing limitations in the session on epic #1327, 2026-10-01.

**Status:** open.

---

## J. Security Groups: rules

### 38. The SG rules table has no Remote column

**Where:** `securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx:234-238`
(columns Direction, Description, Ethertype, Protocol, Range); remote is visible only in
`$securityGroupId/-modals/DeleteRuleDialog.tsx:112-114`, and a group as a bare ID.

**What:** the user cannot see whom a rule is open to: "TCP 22 for `0.0.0.0/0`" and "TCP 22 for
`10.0.0.5/32`" are indistinguishable in the table. From a rule with a remote group you cannot navigate to that group: there is no
link and no name (the delete dialog shows a bare ID), the rule row is not clickable, and there is no rule
details page. The column has been missing since the first version of the table (`97590495`, #586);
the comment in `SecurityGroupRulesTable.test.tsx` (`"Remote Source" column was removed in linter
updates`) is not supported by the history. Elektra has the column (`security_group_rules/list.jsx:141`,
`item.jsx:49-54`): CIDR as `IP: <cidr>`, a group by name with a link to its rules.

**How:** a Remote column: `remote_ip_prefix`, or the remote group's name (resolved from the project's list of groups,
falling back to the ID; for the group itself — a "this group" label) with a link to its details; a rule
without a remote — "Any". Apply the same name resolution in `DeleteRuleDialog`. Mind the table width
(already 5 columns + actions).

**Why not done right away:** a separate table change, not part of the PR on form help hints
(the "Show validation information… on form inputs" remark).

**Source:** analysis of Remote / the current-group filter in the Add Rule modal, 2026-10-06.

**Status:** done 2026-10-06 in [PR #1368](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1368) (SG form help hints, branch `kiryl-security-groups-form-hints`):
Remote column (CIDR, group name as text, without a link — per the PR author's decision; `(this group)`, ID for groups not in the list, address group,
`Any`), Description moved to the end; in `DeleteRuleDialog` a single `Remote` row with the same value;
rule search matches both by CIDR and by remote group name. Helper — `$securityGroupId/-components/ruleRemote.ts`.

### 39. Add Rule validation messages are not translated

**What:** field errors in the Add Rule modal are English strings in the zod schema
(`AddRuleModal/validation/formSchema.ts`) and in `validationHelpers.ts`, about 27 messages. Lingui does
not extract them, so in the German locale they remain English. It was like this before the help hints PR too; it
added three strings in the same style.

**How:** make the schema a factory taking `t` (like `securityGroupValidation.ts` with `msg`) and fix
the 8 section tests that import `createRuleFormSchema`.

**Why not done right away:** a separate schema refactoring, unrelated to the hints.

**Source:** /code-review of branch `kiryl-security-groups-form-hints`, 2026-10-06.

**Status:** open.

### 43. SG details page state (tab, search, sorting, rule filters) in the URL

**Where:**
- `securitygroups/$securityGroupId/-components/SecurityGroupDetailsView.tsx:58`: `activeTab` in `useState`;
- `securitygroups/$securityGroupId/index.tsx:87-100`: rule search, sorting and filters via
  `useListWithFiltering` (`client/utils/useListWithFiltering.ts:97-119`, also `useState`);
- the `$securityGroupId/index.tsx` route has no `validateSearch`.

**What:** rule B.9 in `.github/copilot-instructions.md` requires keeping such state in search
params (`tab`, `search`, `sortBy`/`sortDirection`). Currently a reload or a link to the page always
opens Rules with no search and with default sorting.

**How:**
1. `validateSearch` on the route: `tab: z.enum(["rules", "rbac"]).optional().default("rules")` plus
   search and sorting parameters. Reference — `storage/$provider/$storageType/$containerName/objects/index.tsx:44`.
2. Pass `tab` and `navigate` to `SecurityGroupDetailsView` instead of the local `activeTab`.
3. If RBAC is unavailable but the URL has `tab=rbac`, replace it with `rules` (`navigate` with `replace`). Currently
   `currentTab` (`SecurityGroupDetailsView.tsx:63-64`) only masks the value, and when permissions are restored
   RBAC will open again.
4. Rule search and sorting will need a URL variant of `useListWithFiltering` or passing search
   params through, as on the list pages.

**Why not done right away:** `activeTab` and the rule state lived in `useState` before PR #1375 too. Moving
them to the URL is a separate routing task, while PR #1375 is about layout and Juno components.

**Source:** Copilot remark in PR #1375 (`SecurityGroupDetailsView.tsx:64`), 2026-10-07.

**Status:** open.

---

### 51. SG Rules tab has no separate "no search/filter results" state

**Where:** `securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx:242-247`; it receives
already-filtered `rules` from `SecurityGroupDetailsView.tsx:78-83`.

**What:** when the group has rules but the search or filters hide all of them, the table still says
"No Rules Found / There are no Rule items to display for this Security Group." (copy from #1388). That is misleading:
rule B.6 in `.github/copilot-instructions.md` asks for the two cases to be told apart.

**How to fix:** pass a total-rule count or an `isFiltered` flag from `SecurityGroupDetailsView`. When the table is filtered,
render `<Status status="no-matches">` with a title-case title and a body that suggests adjusting the search or filters,
mirroring the RBAC tab after #1388.

**Why not done right away:** it needs new data flow between the parent and the table plus new copy, while #1388 is a
copy-only change.

**Source:** plan [2026-10-27-security-group-empty-state-copy.md](./plans/2026-10-27-security-group-empty-state-copy.md) (issue #1388)

**Status:** open.

---

## K. Juno: component consistency

### 42. `TabNavigation` tabs: `tabStyle="content"` and a controlled `activeItem` everywhere

**Where:** all five `TabNavigation` instances in `packages/aurora/src/client`: `components/ListToolbar/index.tsx:163`,
`compute/images/-components/List.tsx:247`, `storage/-components/Ceph/Buckets/BucketDetailTabs.tsx:21`,
`storage/-components/Ceph/Objects/ObjectBrowserView.tsx:655`,
`network/securitygroups/$securityGroupId/-components/-details/SecurityGroupTabs.tsx`.

**What, in two parts:**

1. **`tabStyle`.** It is not set anywhere, so `main` is used by default everywhere. According to the Juno 9.4.0 docs
   (`TabNavigation.component.tsx:77`), `main` is for the first child of AppShell; tabs inside a
   page need `content` (inactive tabs get a dark bottom border). All five sit
   inside a page.
2. **Semi-controlled tabs.** `BucketDetailTabs` and `ObjectBrowserView` pass only `active` +
   `onClick`. In Juno 9.4.0, after the first click `Navigation` keeps the active item in its own state, and
   `NavigationItem` then ignores `active`: if the tab is switched by something other than a click, the highlight stays
   on the old one. The item key in this case is the translated `label`. `ListToolbar`, `images/List.tsx` and
   `SecurityGroupTabs` are already controlled.

**How:**
1. `tabStyle="content"` in all five places at once, not one page at a time, and check the look in the browser.
2. In `BucketDetailTabs` and `ObjectBrowserView`, do it as in `SecurityGroupTabs.tsx`: a stable
   `value` on the items, `activeItem` + `onActiveItemChange` on `TabNavigation`, keep `active` for
   the first render. Test: click, then change the active tab from the parent via `rerender`, check
   `aria-selected`.

**Why not done right away:** it touches other people's pages (Ceph, Images, lists). Changing `tabStyle`
only for Security Groups would introduce a new inconsistency.

**Source:** /triple-review of the PR for the SG details page (branch `kiryl-security-groups-detail-page`),
2026-10-07.

**Status:** open.

---

### 53. Migrate the remaining `TabNavigation` users to `TabBar`/`TabBarItem`

**Where:** `packages/aurora/src/client`:
- `components/ListToolbar/index.tsx:7-8,163-167`;
- `routes/_auth/projects/$projectId/network/routers/-components/RouterDetailsView.tsx:10-11,113-120`;
- `routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketDetailTabs.tsx:2,21-58`;
- `routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.tsx:11-12,655-686`;
- `routes/_auth/projects/$projectId/compute/images/-components/List.tsx:20-21,228-232`.

**What:** these still use Juno's deprecated `TabNavigation`/`TabNavigationItem`. In 9.7.1 they are
`withDeprecationWarning` wrappers around `TabBar`/`TabBarItem`, so each mount logs a `console.warn`, and they will
break when Juno drops them. After issue #1387 the Copilot rule (`.github/copilot-instructions.md` B.1) names
`TabBar`, so these files contradict it.

**How:** a one-for-one rename — the props are identical in 9.7.1, and the default `appearance="tabs"` looks the
same as the wrapper's `"main"`. Add `ariaLabel` where a page has more than one nav landmark. Combine with
item 42 (`appearance="content"`
everywhere and controlled `activeItem` in `BucketDetailTabs`/`ObjectBrowserView`) — same files, one pass.

**Why not done right away:** issue #1387 covers Security Groups only; it says the other scopes "will be updated
at some point soon".

**Source:** plan [2026-10-27-security-groups-tabbar.md](./plans/2026-10-27-security-groups-tabbar.md)

**Status:** open.

---

## L. Documentation

### 44. Stale package READMEs: config, policy-engine, signal-openstack, e2e

**Where:** `packages/config/README.md`, `packages/policy-engine/README.md:108`,
`packages/signal-openstack/README.md` (examples from line 21, image link at the end),
`apps/dashboard/e2e/README.md:27,48-49,58,347`.

**What:** the package READMEs no longer match the code.
- `config` still describes the Juno package it was copied from in `696af89a`: it names the package
  `@cloudoperators/juno-config` (real: `@cobaltcore-dev/aurora-config`, private), shows
  `typescript/base.json` as the base (packages extend `typescript/tsconfig.lib.json`; there is also
  `tsconfig.react.json`) and `eslint/juno.mjs` / `juno-typescript.mjs` (the only config is
  `eslint/index.mjs`). The example mentions files that don't exist here (`test/__mocks__/svgLib.js`,
  `setupTests.js`), and the "package-a" tree block was mangled by prettier.
- `policy-engine` imports from `"openstack-policy-engine"`; the package is `@cobaltcore-dev/policy-engine`.
- `signal-openstack`: `SignalOpenstackSession` is `async` (`src/session.ts:23`), but every example uses
  it without `await` and chains `.service()` on the Promise. The architecture image points at
  `docs/SignalOpenstackArch.svg`; the file is `docs/AuroraSignalArch.svg`. The API list omits
  `rescope`, `hasService` and `isValid`, and lists `put` without its `values` argument.
- `e2e`: says the app runs on `localhost:3000` — that is only the `playwright.config.ts` fallback; the
  dev server defaults to 4005 and `.env.example` sets 4001. Line 27 refers to
  `/workspace/aurora-dashboard-OS/...`.

**How to fix:** one `docs:` PR. Rewrite `config/README.md` (~25 lines: real name, the three tsconfig
files and when to use each, the one ESLint config, examples taken from `signal-openstack`). Fix the
import name, the `await`s, the image path and the API list; replace port 3000 with the configured
port and drop the `/workspace` path.

**Why not done right away:** these are tracked upstream files; changing them as a side effect of
another task would mix unrelated docs edits into that PR.

**Source:** workspace documentation audit, 2026-10-11.

**Status:** open.

### 45. `packages/aurora/README.md` and `.env.example` document the removed `crossDomainCookie`

**Where:** `packages/aurora/README.md:57-69` (the `createServer(config)` table) and `:19`,
`README.md:24` (root, "two entry points"), `apps/dashboard/.env.example:22-23`,
`packages/aurora/src/types/index.ts` (`policyDir` doc comment).

**What:** the consumer-facing docs describe a cookie option that no longer exists.
- The `createServer` table lists `crossDomainCookie: boolean`, default `true`, "Share cookie across
  subdomains". It was removed in `e070437c` (#998, aurora 0.12.0, 2026-06-30; marked breaking in
  `CHANGELOG.md`) and replaced by `cookieDomain?: string` — unset by default, i.e. cookies are
  host-specific, the opposite of what the table says. A consumer following the README passes a field
  that is silently ignored and gets no cross-subdomain cookie.
- `debug?: boolean` (OpenStack session HTTP logging; default `false` in production, `true` in dev)
  is in `AuroraServerConfig` but not in the table.
- `policyDir` is described as a directory of policy **YAML** files (the type's doc comment says
  `compute.yaml`); the permission routers load `compute.json`, `image.json`, `networking.json`,
  `storage.json`.
- `identityEndpoint` is marked required; the type has `identityEndpoint?: string` and
  `server.ts` falls back to `""`.
- Both READMEs say the package has two entry points; `package.json` exports three
  (`./server`, `./client`, `./types` — the last one types only).
- `apps/dashboard/.env.example` still offers `# ENABLE_CROSS_DASHBOARD_COOKIE=true` ("default: true"),
  which nothing reads; `COOKIE_DOMAIN`, which `apps/dashboard/src/server/server.ts` does read, is
  missing.

**How to fix:** one `docs:` PR (can be merged with #44 — same kind of change). Replace the
`crossDomainCookie` row with `cookieDomain` (`string`, default unset → host-specific cookies,
example `".example.com"`), add a `debug` row, change YAML → JSON for `policyDir` (README and doc
comment), mark `identityEndpoint` as optional or make the type match, mention the `./types` entry
point. In `.env.example` replace the two lines with
`# Share the session cookie across subdomains (default: unset — host-specific)` /
`# COOKIE_DOMAIN=".example.com"`.

**Why not done right away:** tracked upstream files; found during a workspace audit, not as part of
a change to this code.

**Source:** workspace documentation audit, 2026-10-12.

**Status:** open.

### 46. Root `README.md`, `CONTRIBUTING.md` and release docs: stale setup facts

**Where:** `README.md:53-56` (Prerequisites), `:65-84` (Configure environment, Run in development),
`:112-116` (Release Management); `CONTRIBUTING.md:20-21,33`; `docs/semantic_release.md`;
`docs/aurora_architecture_overview.md:242-251`.

**What:** the getting-started and release sections contradict the repo.
- Prerequisites say Node.js `>= 18` and pnpm `>= 10`; the repo requires Node 24 (`.nvmrc`
  `24.15.0`, `engines` `>=24.15.0`) and pnpm 11 (`packageManager` `pnpm@11.20.0`).
  `CONTRIBUTING.md` says Node `>= 24` but pnpm `>= 9`, and copies `.env` from the old
  `apps/aurora-portal/` path.
- "Configure environment" lists only `IDENTITY_ENDPOINT` and `VITE_BFF_ENDPOINT`. Without
  `CEPH_REGION` every Ceph procedure throws "Ceph region not configured"
  (`Storage/cephProcedure.ts:49`).
- "The dashboard starts at `http://localhost:4005` by default" — true only when `PORT` is unset;
  `.env.example`, which the README tells you to copy, sets `PORT="4001"`.
- "Release Management" says the project uses Semantic Release and links `docs/semantic_release.md`.
  Releases are done with Changesets: `.github/workflows/release.yaml` runs on push to `main`,
  `changesets/action` opens a version PR, merging it bumps versions, updates changelogs and
  publishes to npm. `docs/aurora_architecture_overview.md` ("Release Process – Semantic Release")
  says the same outdated thing.

**How to fix:** one `docs:` PR. A draft of the `README.md` part already existed (uncommitted on
`main`, reverted 2026-10-12 so it doesn't sit in the working tree); its wording, verified against the
code:
- Prerequisites: "Node.js 24 (exact version in `.nvmrc`)", "pnpm 11 (exact version pinned in
  `packageManager` in `package.json`)".
- After the `.env` block: "To use Ceph object storage (S3), also set `CEPH_REGION` to your Ceph RGW
  region; without it, Ceph operations fail with a configuration error. The other variables in
  `.env.example` are optional."
- Run in development: "The dashboard starts on the port set by `PORT` in `.env` —
  `http://localhost:4001` with the values from `.env.example`, or `http://localhost:4005` if `PORT`
  is not set."
- Release Management: Changesets — `pnpm changeset` in the PR; "On every push to `main`, the release
  workflow collects pending changesets into a version PR; merging that PR bumps the versions,
  updates the changelogs and publishes the packages to npm."
In the same PR: fix the pnpm version and the `apps/aurora-portal` path in `CONTRIBUTING.md`, and
delete `docs/semantic_release.md` (or mark it as obsolete) and rewrite the release section of
`docs/aurora_architecture_overview.md`.

**Why not done right away:** tracked upstream files; the README draft was sitting uncommitted on
`main` with no PR, where it would end up in an unrelated change.

**Source:** workspace documentation audit, 2026-10-12.

**Status:** open.

---

## M. Block Storage volumes

### 48. Extend attached (`in-use`) volumes (Cinder microversion 3.42)

**Where:** `packages/aurora/src/server/Compute/routers/volumeRouter.ts` (`extend`),
`.../compute/volumes/-components/-modals/ExtendVolumeModal.tsx`,
`packages/aurora/src/server/Compute/helpers/volumeStatus.ts` (`isExtendable`),
`apps/dashboard/src/policies/volume.json`.

**What:** extend is limited to `available` volumes. Cinder supports `in-use` extend from 3.42, subject to
the `volume:extend_attached_volume` policy and backend/compute driver support
(https://docs.openstack.org/cinder/latest/contributor/api_microversion_history.html).

**How to fix:** detect Cinder's max version and send `OpenStack-API-Version: volume 3.42` for `in-use`
volumes. Add key `compute:volumes:extend_attached` → `volume:extend_attached_volume`. Warn that the guest
may need a rescan.

**Why not done right away:** user decision D5 in the plan; the behaviour depends on the driver and needs
live verification.

**Source:** plan [2026-10-13-cinder-volumes-compute-page.md](./plans/2026-10-13-cinder-volumes-compute-page.md)

**Status:** open.

### 49. "Attached Volumes" section on Instance Details

**Where:** no Instances UI exists yet. `client/routes/_auth/projects/$projectId/compute/index.tsx` only
redirects, and `server/Compute/routers/serverRouter.ts` only has the legacy `getServersByProjectId`.

**What:** epic #1024 wants attach/detach reflected in Instance Details.

**How to fix:** once an Instances details page exists, add an "Attached Volumes" table from Nova
`GET servers/{id}/os-volume_attachments`, and reuse `AttachVolumeModal`/`DetachVolumeModal` with the
server preselected.

**Why not done right away:** depends on the Instances epic.

**Source:** plan [2026-10-13-cinder-volumes-compute-page.md](./plans/2026-10-13-cinder-volumes-compute-page.md)

**Status:** open.

### 50. Availability-zone selection when creating a volume

**Where:** `.../compute/volumes/-components/-modals/CreateVolumeModal.tsx`,
`packages/aurora/src/server/Compute/routers/volumeRouter.ts`.

**What:** volumes are created in Cinder's default AZ. With `cross_az_attach=False`, a new volume may not be
attachable to a server in another AZ.

**How to fix:** add `listAvailabilityZones` (Cinder `GET os-availability-zone`) and an optional
"Availability Zone" `Select` that sends `availability_zone`.

**Why not done right away:** not in the epic's field list, and the regions' AZ setup needs confirming
first.

**Source:** plan [2026-10-13-cinder-volumes-compute-page.md](./plans/2026-10-13-cinder-volumes-compute-page.md)

**Status:** open.

---

## N. Ports and Routers (PR #1377)

### 54. Ports and Routers docs name the wrong Badge variant for DOWN/ERROR

**Where:** `packages/aurora/docs/0017_ports_bff.md:405`, `packages/aurora/docs/0010_routers_bff.md:606`.

**What:** the docs say the status Badge is "danger for DOWN/ERROR", but `PortTableRow.tsx` and `RouterTableRow.tsx` return `"error"`. The code is right (B.4: `error` = system/operation failure, distinct from `danger`). No runtime effect.

**How:** change "danger" to "error" in both docs — or drop the paragraph if item 59 turns the status into plain text.

**Why not done right away:** an Improvement (Low) in the review, not a merge blocker.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `25282829`, 2026-10-28 — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open.

### 55. Status looks different in the list and the details view (Ports, Routers)

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortDetailsView.tsx:70`, `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/-components/RouterDetailsView.tsx:72`.

**What:** the list rows render status as a `Badge`, the details views as plain text, so the same status looks different on the two pages (B.1 names Badge for status).

**How:** once item 59 is settled, use the same rendering in both places (e.g. Badge as in `storage/-components/Ceph/Buckets/BucketHeader.tsx:47`, or plain text everywhere).

**Why not done right away:** an Improvement (Low) in the review, not a merge blocker.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `25282829`, 2026-10-28 — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open.

### 56. Router details answers 403 with an error page instead of an info Message

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/$routerId.tsx:88`.

**What:** `case "FORBIDDEN"` goes through `RouteIdLevelDefaultError`; B.6 asks for a page-level info Message on 403, and Ports details (`ports/$portId.tsx`) in the same PR uses one. `0010_routers_bff.md` records the difference on purpose.

**How:** render the 403 as in `ports/$portId.tsx` (`` <Message variant="info" title={t`Insufficient Permissions`}> ``) and drop the "the two differ here" note from the routers doc; then fix item 60 accordingly.

**Why not done right away:** an Improvement (Low) in the review, not a merge blocker.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `25282829`, 2026-10-28 — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open; still open at head `1d4d4c3c` (I14 in the 2026-10-28 Update).

### 57. Port details does not use the shared `TwoColumnDescriptionList`

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortDetailsView.tsx:17`.

**What:** renders Juno `<DescriptionList alignTerms="right">` instead of `packages/aurora/src/client/components/TwoColumnDescriptionList.tsx`, so it misses the two-column layout. Asked for by TilmanHaupt in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#pullrequestreview-5670107878.

**How:** build `PortDetailsView` from `TwoColumnDescriptionList`.

**Why not done right away:** an Improvement (Low) in the review, not a merge blocker.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `25282829`, 2026-10-28 — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open.

### 58. Inconsistent empty-field placeholder in the Ports views

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortDetailsView.tsx:60-81`, `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:63,81,86,88`.

**What:** details use `—` (em dash), the list `–` (en dash). TilmanHaupt asked for the guideline placeholder in both (same review). Merged code mixes both, and the repo does not document the character.

**How:** confirm the character with the maintainer, then use one shared constant in both files.

**Why not done right away:** an Improvement (Low) in the review, not a merge blocker.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `25282829`, 2026-10-28 — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open.

### 59. Ports list layout differs from the maintainer's requested layout

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:61`, `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:58-63`, `PortDetailsView.tsx:53`.

**What:** status is a Badge in the 2nd column, ID sits under the name, fixed IPs carry `IPv4`/`IPv6` labels. TilmanHaupt asked for plain-text status in the first column, no IP-version labels, ID maybe last (same review). The Badge came from the earlier report's I10 (B.1).

**How:** follow the maintainer's layout, or reply on the review explaining the B.1 Badge choice. Decides items 54 and 55.

**Why not done right away:** an Improvement (Low) in the review, not a merge blocker.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `25282829`, 2026-10-28 — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open.

### 60. Routers doc contradicts itself on 403 in the details view

**Where:** `packages/aurora/docs/0010_routers_bff.md:613` vs the Implementation Status line ("403 info message on both the list and details views").

**What:** line 613 (fixed after Copilot's https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#discussion_r4389368754) says details shows an error page; the status list still says info message on both. Code follows line 613.

**How:** align the Implementation Status line with line 613 — or, if item 56 is done, update line 613 instead.

**Why not done right away:** an Improvement (Low) in the review, not a merge blocker.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `25282829`, 2026-10-28 — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open.

### 61. 401 redirect can loop when only the OpenStack call is unauthorized

**Where:** `.../network/ports/-components/PortsList.tsx` and `.../network/routers/-components/RoutersList.tsx` (`UnauthorizedRedirect`), `.../network/ports/$portId.tsx`, `.../network/routers/$routerId.tsx`.

**What:** on a 401 the page reloads to `/?redirect=<current page>` without ending the session. `getCurrentUserSession` returns the stored token without asking Keystone, so with a revoked token or a failed rescope the landing route sends the user straight back, the query 401s again, and the page reloads in a loop.

**How:** end the session first (`trpcClient.auth.terminateUserSession`, as the expiry handler in `AuthProvider.tsx` does) or stop after one redirect and show "Session Expired"; one shared helper for the four places.

**Why not done right away:** a Required Change (Moderate) in the review; tracked here until the PR fixes it.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `25282829`, 2026-10-28 (CR5) — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open.

### 62. Ports and Routers by-ID procedures don't check the resource's `project_id`

**Where:** `packages/aurora/src/server/Network/routers/portsRouter.ts:107` (`getById`), and `update` / `delete` in the same file; the same pattern in `routersRouter.ts`.

**What:** `getById`, `update` and `delete` call Neutron by `port_id` only and never compare the port's `project_id` with `input.project_id` (`list` does filter by project). A token with cross-project Neutron admin rights, scoped to project A, can read, change or delete project B's port through project A's endpoint. Normal project-scoped users are not affected, since Neutron policy rejects them. Copilot raised it in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#discussion_r4389368122; the author called it valid defence-in-depth and deferred it in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#discussion_r4389970447.

**How:** after the fetch, compare `port.project_id` with `input.project_id` in all three procedures and answer `NOT_FOUND` on a mismatch; do the same for Routers.

**Why not done right away:** deferred by the author to one follow-up for Ports and Routers; a team call (Moderate, Security) in the review.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `1d4d4c3c`, 2026-10-28 (CR6) — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open.

### 63. `terminateUserSession` before the 401 redirect has no `.catch`

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:121`, `.../network/ports/$portId.tsx:75`, `.../network/routers/-components/RoutersList.tsx:75`, `.../network/routers/$routerId.tsx:77`.

**What:** `trpcClient.auth.terminateUserSession.mutate().finally(...)` has no `.catch`. `terminateUserSession` is a `protectedProcedure`, so when the session is already gone (the usual reason for a 401) it rejects with `UNAUTHORIZED`, and every expired-session redirect logs an unhandled promise rejection. The redirect itself still runs. `AuthProvider.tsx:66` wraps the same call in `try/catch/finally`.

**How:** `.mutate().catch(() => {}).finally(() => window.location.replace(...))`, or one shared helper for the four places.

**Why not done right away:** an Improvement (Low) in the review, not a merge blocker.

**Source:** review-and-comment-pr Update of [PR #1377](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377) at head `1d4d4c3c`, 2026-10-28 (I19) — report `aurora-dashboard-kb/prs/1377-neutron-ports-bff-read-only-ports-page.md`

**Status:** open.

---
Updated: 2026-10-28

## L. Key Manager (Barbican) plugin

### 64. Container search sends `name` filter to Barbican, but Barbican ignores it

**Where:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:223`, `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainersList.tsx:43`.

**What:** The Containers list shows a search box with placeholder "Search by name or ID". When the user types, the client sends `name` to the server, which forwards it to Barbican as a query parameter. However, Barbican's GET /v1/containers only supports `offset` and `limit` — no name-based filtering. The search appears to work but returns all containers regardless of input, misleading users.

**How:** Either remove the search box from the Containers list (Barbican can't filter), or implement client-side filtering on the fetched results. The Secrets list's search works because Barbican's GET /v1/secrets does support a `name` filter.

**Why not done right away:** Bug discovered during review — requires design decision on approach.

**Source:** review-and-comment-pr Update of [PR #1393](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393) at head `cfba5b42`, 2026-10-29 (CR12) — report `aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md`

**Status:** open.

### 65. CreateContainerModal and DeleteContainerModal missing `disableCloseButton` during async operations

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:132` (Create), `:297` (Delete).

**What:** Both modals disable the Cancel button while a mutation is pending (`disableCancelButton={createMutation.isPending}`), but they don't set `disableCloseButton`, so users can still close via the X button. This bypasses the "wait for the request" pattern and can leave the UI in an inconsistent state if the user closes mid-flight and the mutation completes.

**How:** Add `disableCloseButton={createMutation.isPending}` to CreateContainerModal and `disableCloseButton={deleteMutation.isPending}` to DeleteContainerModal. See `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/DeleteFlavorModal.tsx:119` for the pattern.

**Why not done right away:** Quick Reject Checklist violation with existing precedent — convention-level fix.

**Source:** review-and-comment-pr Update of [PR #1393](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393) at head `cfba5b42`, 2026-10-29 (CR13) — report `aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md`

**Status:** open.

### 66. PR description claims "add/remove secret refs" for containers, but no such procedures exist

**Where:** PR #1393 body.

**What:** The description states containers support "add/remove secret refs" as operations, but the keyManagerRouter only has listContainers, getContainer, createContainer, and deleteContainer. There are no addContainerSecret or removeContainerSecret procedures. The createContainer procedure accepts secret_refs in its input, but that's creation-time only, not add/remove operations on existing containers.

**How:** Update the description to say 'containers (list/get/create/delete)' without mentioning add/remove, or note that secret_refs are specified only at creation time.

**Why not done right away:** Process item — description/code mismatch.

**Source:** review-and-comment-pr Update of [PR #1393](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393) at head `cfba5b42`, 2026-10-29 (P2) — report `aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md`

**Status:** open.

### 67. Server-side policy enforcement not mentioned in PR description

**Where:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:64`.

**What:** The update added a `buildKeyManagerResourceRouter` factory that wraps each procedure with an `enforce()` call, checking the loaded policy engine before allowing any operation. This is a significant security feature where Aurora's policy becomes authoritative, preventing operations the policy denies even when Barbican would permit them. The description mentions the permission router and policy mappings for client-side gating, but not this server-side enforcement.

**How:** Add a bullet noting that all Key Manager operations are now enforced server-side via the loaded policy engine, making Aurora policy authoritative.

**Why not done right away:** Process item — significant feature not documented in PR description.

**Source:** review-and-comment-pr Update of [PR #1393](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393) at head `cfba5b42`, 2026-10-29 (P3) — report `aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md`

**Status:** open.

### 68. Navigation inconsistency: Key Manager detail views rely on breadcrumbs alone

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:71`.

**What:** Key Manager detail views removed the "Back to Secrets/Containers/Orders" button, relying on the breadcrumb for navigation. However, Flavors, Images, Floating IPs, Routers, Security Groups and other services still show both a Back button in the ContentHeader and the breadcrumb. Users navigating across services encounter inconsistent navigation patterns.

**How:** Either restore the Back button to Key Manager detail views for consistency with Flavors/Images/etc., or open a follow-up to remove Back buttons from the other services.

**Why not done right away:** UX consistency issue with existing precedent elsewhere — not a functional break.

**Source:** review-and-comment-pr Update of [PR #1393](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393) at head `cfba5b42`, 2026-10-29 (I25) — report `aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md`

**Status:** open.

### 69. Server-side policy enforcement is unique to Key Manager

**Where:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:71`.

**What:** This update introduces `buildKeyManagerResourceRouter(policyDir)`, which loads the policy engine once and wraps every procedure with an `enforce(ctx, rule)` call. This makes Aurora authoritative. However, Compute, Network and Storage routers still rely solely on client-side `canUser` checks — their procedures remain callable without policy enforcement when the advisory check is bypassed.

**How:** Document the server-side enforcement pattern in the KB or ADR. Consider a follow-up to apply it to Compute/Network/Storage routers.

**Why not done right away:** Architectural divergence, not a blocker — the new pattern is better and other services could adopt it incrementally.

**Source:** review-and-comment-pr Update of [PR #1393](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393) at head `cfba5b42`, 2026-10-29 (I26) — report `aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md`

**Status:** open.

### 70. CRUD acceptance partly met — Update UI missing, Container Edit scope dropped

**Where:** PR files.

**What:** Server procedures exist for all CRUD operations, and the client UI covers list, view, create and delete. However, `updateSecret` has no client caller (users cannot update secrets through the UI), and Container Edit scope (managing secret associations on existing containers, per issue #1133) was dropped with no scope note.

**How:** Either implement the Update UI, or add a scope note to the PR body clarifying that update is out of scope for this phase.

**Why not done right away:** Partial delivery of stated scope — follow-up work.

**Source:** review-and-comment-pr Update of [PR #1393](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393) at head `cfba5b42`, 2026-10-29 (I27) — report `aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md`

**Status:** open.

### 71. Permission gating acceptance partly met — Update UI unreachable

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:50`.

**What:** This update adds comprehensive server-side policy enforcement and client-side gating via `useKeyManagerPermissions`. However, the acceptance criterion asks for all action-triggering UI elements to be gated. The `updateSecret` procedure exists and is enforced server-side, but has no client caller — users cannot exercise it, so its permission gating cannot be verified end-to-end.

**How:** Once the Update UI is added, wire its button to `canUser('key-manager:secrets:update')` and test the full flow.

**Why not done right away:** Blocked by missing Update UI.

**Source:** review-and-comment-pr Update of [PR #1393](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393) at head `cfba5b42`, 2026-10-29 (I28) — report `aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md`

**Status:** open.

### 72. Error handling acceptance partly met — Barbican error details dropped

**Where:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:126`.

**What:** Mutations do surface errors in modals, so users see something went wrong. However, `mapKmError` (keyManagerRouter.ts:52) replaces the Barbican error body with a generic "Key Manager … failed" message. Users lose the specific diagnostics Barbican returns — e.g. why a secret name is invalid, why a container type is unsupported, or what's wrong with the payload format.

**How:** Enhance `mapKmError` to preserve or summarize Barbican's error body when present, so users see actionable diagnostics.

**Why not done right away:** Functional but not "comprehensive" as the criterion requires — UX improvement.

**Source:** review-and-comment-pr Update of [PR #1393](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393) at head `cfba5b42`, 2026-10-29 (I29) — report `aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md`

**Status:** open.

---
Updated: 2026-10-29
