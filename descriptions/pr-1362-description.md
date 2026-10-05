# Summary

Ceph/S3 users had no way to see or manage their own access keys. Reported from the bucket list of a project that already had a working key:

> I have no option to see or manage my credentials.

The only credentials UI was `CredentialPrompt`, rendered on exactly one condition — the bucket listing failing with `NO_CEPH_CREDENTIALS` — so a user who had a key could never reach it again. It created a key, ignored the `secret` in the response and reloaded the page, so the key worked inside Aurora and nowhere else: nothing to configure `aws s3`, s3cmd or a backup job with, and no way to rotate. The endpoint and region were known only to the server.

This adds a **Manage Credentials** modal: the keys the user holds in this project, a secret revealed per key on request, create, delete, and the S3 endpoint and region beside them.

**The secret was recoverable all along.** Keystone's EC2 credentials are not Application Credentials — the blob is stored encrypted and decrypted on every read, and the owner may read their own. The BFF already performs that read on every Ceph request to sign the S3 call (`middleware/resolveEC2Credential.ts`), so nothing new is exposed.

**A secret is fetched only when its Reveal is clicked.** `type="password"` changes how an input paints a value it already holds; it is not a boundary. Filling every field on open would put every key into the DOM for a user who most likely came for the endpoint. Until then the field holds filler of the same length, and Hide, delete and close discard the value rather than paint over it — the component's own state is the only thing that ever holds it.

# Changes Made

## Server

- **`ec2CredentialRouter.ts`** — new `reveal` mutation, the only procedure that returns a secret. A mutation and not a query so the result never lands in the TanStack Query cache; the client calls it through the vanilla tRPC client, which holds no cache of its own either.
- **`ec2CredentialRouter.ts`** — `create` no longer returns the secret and imposes no limit on how many keys a user holds; `delete` is deliberately not idempotent, answering `NOT_FOUND` for a credential that is already gone rather than reporting a deletion that did not happen.
- **`ec2CredentialRouter.ts`** — `fetchOwnedCredential`, shared by `reveal` and `delete`: the status the identity service answered with is the status the caller gets. The one refusal of its own is a credential belonging to another user or project, which is never parsed and never returned.
- **`helpers/ec2CredentialMapper.ts`** — new; replaces the parse-and-validate block that stood three times in the router, and rejects JSON that parses but has no fields to read.
- **`containerRouter.ts`** — `containers.status` returns `endpoint` and `region` alongside `hasCredentials`, on `cephProcedure` so it renders for a user with no key yet.
- **`policies/createPermissionRouter.ts`** — a missing policy rule now denies its own permission key instead of throwing and failing the whole batch, which used to hide every Ceph action at once. Adding `storage:credentials:delete` would have hit this on any forked policy file.

## Client

- **`Ceph/Credentials/ManageCredentialsModal.tsx`** — new. Keys in a `DataGrid`: access key ID, secret, delete. Both values sit in read-only `TextInput`s, which is also how they are copied. The secret's field is an `InputGroup` with its own Reveal/Hide button. Connection Details carries the endpoint and region.
- **`reveal` is called through the vanilla tRPC client**, not `useMutation`: a mutation's answer sits in TanStack's `MutationCache` until `gcTime` elapses after `reset()`, which would outlive Hide, delete and close by minutes. The vanilla client caches nothing. A secret that arrives after its own key has been deleted is dropped rather than written back into a row that is gone and no Hide can reach, and a delete that comes back `NOT_FOUND` — the key was already removed elsewhere — discards that row's secret the same way a successful one does. Every other delete failure leaves the key on screen, and its secret with it.
- **`Ceph/Credentials/DeleteCredentialModal.tsx`** — new. Confirmation dialog stacked inside the parent modal's subtree, the way `ObjectVersionHistoryModal` stacks its own. Names the key, and says one thing more when it is the last one: without a key S3 Object Storage is out of reach in the dashboard too, though the buckets survive and a new key reaches them.
- **`Ceph/hooks/invalidateCredentialQueries.ts`** — new. Refetches the key table on every mutation and takes its decision from the list that comes back rather than from the cache afterwards: a refresh that fails leaves the pre-mutation list in place, which counts perfectly well and would strand the page behind the modal on "Setup Required" over a project that now has a key. The pending request is cancelled before that refetch, because `fetch` otherwise joins a request already in flight and answers with a snapshot that may predate the mutation — `staleTime: 0` refuses a cached answer, not a shared one. The bucket listing is re-scanned only on the 0 ↔ 1 transition, since that query is the expensive one on the screen; a listing that is currently showing an error is refreshed on every credential change regardless, because "S3 Credentials No Longer Valid" is reached with a key already in Keystone, so creating a replacement (1 → 2) and deleting the broken key (2 → 1) are not transitions by that rule and would leave the page on its cached error.
- **`Ceph/Buckets/index.tsx`** — three entry points into the same modal: the overflow menu beside "Create Bucket", the rewritten empty state, and the "S3 Credentials No Longer Valid" screen.
- **`Ceph/Credentials/CredentialPrompt.tsx`** — moved from `Ceph/Buckets/`, rebuilt on Juno's `Status`, and opens the modal instead of creating a key and reloading.
- **Permissions** — Create and the row's delete button render only for a user who may use them, with one `Message` naming what is missing and pointing at an administrator. Only a definite no hides a control: while the check is in flight, or if it failed, both stay disabled. Reading one's own keys is not gated.
- **In-flight state** — a create or delete disables everything in the modal, Escape included. A reveal does not: it belongs to one row.
- **Error banners** carry `role="alert"` and `aria-live="assertive"`, as `CreateBucketModal`'s does: both appear after an asynchronous failure rather than at render time.

## Tests

- **`ManageCredentialsModal.test.tsx`** — 37 tests over the modal: concealment and the filler, one `reveal` per Reveal, Hide discarding rather than masking, the per-row error message, create and delete including the confirmation dialog, the permission states, and what each mutation does to the bucket listing behind the modal. Four of them are about a secret outliving what asked for it: one arriving after the modal was closed, one after it was closed and reopened, one after its own key was deleted, and one whose delete came back `NOT_FOUND`. The last pair's counterpart is there too — an ordinary failed delete keeps the key on screen, so it keeps the secret.
- **`invalidateCredentialQueries.test.ts`** — 12 tests: the key table is refreshed on every mutation, the pending request is cancelled before it, the refetch asks the server rather than accepting a merely fresh list, the decision is taken from what came back, a failed refresh still refreshes the bucket listing, and the narrow error-only refresh matches a failed listing while skipping a loaded one.
- **`ec2CredentialRouter.test.ts`** and **`ec2CredentialMapper.test.ts`** — ownership from the rescoped token, the identity service's status passed through unchanged in both shapes a refusal arrives in, non-`ec2` credentials treated as absent, and a blob that parses into something with no fields to read.
- Full suite: **240 files / 5835 tests**, all passing. `pnpm typecheck`, `pnpm lint`, `pnpm format:check` and `pnpm check-i18n` are green, with no `.po` churn.

## Docs

- **`packages/aurora/docs/009_ceph_s3_bff.md`** — the EC2-credential section brought in line with the procedures it documents.

# Related Issues

Fixes #1358

# Testing Instructions

1. `pnpm i`
2. `pnpm run test`
3. Open a project with Ceph object storage, `/projects/<id>/storage/ceph/containers`.
4. **With no keys:** the empty state's button opens the modal instead of creating a key and reloading. Create one — the row appears concealed and a toast says where to find it again.
5. **With a key:** "More Actions" → "Manage Credentials". Watch the network tab: no `reveal` call on open. Press Reveal — one call, for that key only. Press Hide, then Reveal again: the value is refetched.
6. Check a key works: `AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… aws --endpoint-url <endpoint> --region <region> s3 ls`.
7. Create a second and a third key — nothing claims a maximum, and each creation is a single request.
8. Delete one: the confirmation names the key, Cancel leaves it alone, confirming removes the row and toasts. Delete the same key from two tabs — the second reports `Credential not found` instead of claiming success, and if that tab had revealed the key's secret, the secret goes with the row rather than staying in state with no Hide left to clear it. Deleting the last key says the storage goes out of reach, and the page behind falls back to the empty state while the modal stays open.
9. Press Escape during a create or delete: nothing in the modal responds until the request settles.
10. Operators with a forked `storage.json`: add `"storage:credential_delete": "rule:storage_viewer"`. Without it the Delete action stays hidden and the rest of the Ceph permissions are unaffected.

# Behaviour and Contract Changes

- New procedure `storage.ceph.ec2Credentials.reveal`.
- `storage.ceph.ec2Credentials.create` no longer returns `secret`; the response is `{ id, access, user_id, project_id }`. A narrowed contract, so worth a reviewer's eye — nothing in this package consumed the field.
- `storage.ceph.ec2Credentials.delete` answers `NOT_FOUND` for a credential that is already gone, where it previously answered `{ success: true }`.
- `storage.ceph.containers.status` returns two additional fields. Purely additive.
- New permission key `storage:credentials:delete`; see step 10 for operators running their own policy files.
- `Ceph/Buckets/CredentialPrompt.*` moved to `Ceph/Credentials/`. Nothing outside the package imported them.

# Checklist

- [x] I have performed a self-review of my code.
- [x] I have commented my code, particularly in hard-to-understand areas.
- [x] I have added tests that prove my fix is effective or that my feature works.
- [x] New and existing unit tests pass locally with my changes.
- [x] I have made corresponding changes to the documentation (if applicable).
- [x] My changes generate no new warnings or errors.
