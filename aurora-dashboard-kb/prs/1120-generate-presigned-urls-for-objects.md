---
type: pr-report
date: 2026-08-03
status: merged
pr: [1120]
author: mark-karnaukh-extern-sap
branch: mark-ceph-object-pre-signed-urls
---
# PR #1120: feat(portal): generate pre-signed URLs for objects

**Author:** mark-karnaukh-extern-sap · **Status:** merged 2026-08-05 (commit `502a1e92`)
**Branches:** `mark-ceph-object-pre-signed-urls` → `main` · **Files:** 16 (+1323/-11)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1120

## What was done

Swift objects have long had temporary HMAC-signed links (`GenerateTempUrlModal`, PR #705), but Ceph (S3) did not. The PR closes this gap: it adds **pre-signed URLs** for Ceph objects — a new procedure `storage.ceph.objects.generatePresignedUrl` in the BFF and a `GeneratePresignedUrlModal` modal on the client, invoked via a new "Share URL" item in the row action menu in `ObjectsTableView`.

Unlike Swift, there is no key that needs to be configured beforehand: the signature is derived from the request's already existing EC2 credentials (the same ones used by the other Ceph procedures via `getCephClient()`), so the implementation is simpler than its Swift counterpart — no "key not configured" path is needed, and there is no account parameter.

Limitation: **GET only**. Presigned `PUT` (upload-by-link) is explicitly out of scope — uploads still go through the existing `uploadObject` (streaming via the BFF, see PR #1086 in this same documentation set).

## How it is implemented

**The input schema** (`packages/aurora/src/server/Storage/types/ceph.ts:271-281`) introduces a constant for the maximum link lifetime and a Zod schema that uses it as the upper bound:

```ts
// ceph.ts:271-281
export const S3_PRESIGN_MAX_EXPIRY_SECONDS = 604800

export const generatePresignedUrlInputSchema = projectScopedInputSchema.extend({
  containerName: z.string().min(1),
  objectKey: z.string().min(1),
  expiresIn: z.number().int().positive().max(S3_PRESIGN_MAX_EXPIRY_SECONDS),
})
```

604800 seconds (7 days) is the hard maximum of the AWS SigV4 protocol itself (the `@aws-sdk/s3-request-presigner` signer will reject a larger value on its own); by moving the check into the Zod schema, the PR turns an out-of-bounds value into a clear `BAD_REQUEST` before reaching the signer, instead of an opaque signing error. The constant is exported specifically so that the frontend doesn't keep its own magic number 604800 and can't drift from the schema (see its use in the modal below).

**The procedure** (`packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:305-323`) is built on `cephProtectedProcedure` — the same builder as all the other Ceph object procedures in this file (`list`, `getDetails`, `deleteAll`, `copy`, ...), so it automatically inherits the existing authentication/rescoping contract; nothing new is introduced here:

```ts
// objectRouter.ts:305-323
generatePresignedUrl: cephProtectedProcedure
  .input(generatePresignedUrlInputSchema)
  .mutation(async ({ ctx, input }): Promise<{ url: string; expiresAt: number }> => {
    const s3 = ctx.getCephClient!()
    const { containerName, objectKey, expiresIn } = input

    try {
      const url = await getSignedUrl(s3, new GetObjectCommand({ Bucket: containerName, Key: objectKey }), {
        expiresIn,
      })
      const expiresAt = Math.floor(Date.now() / 1000) + expiresIn
      return { url, expiresAt }
    } catch (error) {
      throw mapS3ErrorToTRPCError(error, {
        operation: "generate presigned URL",
        bucket: containerName,
        key: objectKey,
      })
    }
  }),
```

A key detail worth understanding when reading this code: signing is a purely local cryptographic operation (`getSignedUrl` makes no network round-trip to Ceph), so the call is fast and **does not check that the object exists at all** — the PR itself explicitly documents this as a trade-off (see below, docs). `expiresAt` is computed on the server as an absolute unix timestamp (`now + expiresIn`) rather than just returning a duration — this way the frontend doesn't need to trust its own clock to display the expiration time.

**Frontend** — `GeneratePresignedUrlModal.tsx` (new file, 352 lines), the Ceph counterpart of `Swift/Objects/GenerateTempUrlModal.tsx`, but noticeably simpler: no account/method fields, no "key not configured" branch (Swift has one because it requires a preconfigured HMAC key — Ceph has no such step at all). It imports the shared limit from the server module via the same path as the rest of the client code in this file (`S3Object`/`S3FolderPrefix` from `@/server/Storage/types/ceph` in `ObjectsTableView.tsx` — an existing convention, not new to this PR):

```ts
// GeneratePresignedUrlModal.tsx:6,19-21
import { S3_PRESIGN_MAX_EXPIRY_SECONDS } from "@/server/Storage/types/ceph"
...
const MAX_EXPIRY_SECONDS = S3_PRESIGN_MAX_EXPIRY_SECONDS
const MAX_EXPIRY_MINUTES = MAX_EXPIRY_SECONDS / 60
```

Presets are 1 hour / 24 hours / 7 days plus an arbitrary duration in minutes; for custom input the modal validates the bound itself (`> MAX_EXPIRY_MINUTES` → inline error), avoiding a round-trip for a guaranteed 400 from the backend.

Protection against stale responses is implemented via an incrementing `requestIdRef` (`GeneratePresignedUrlModal.tsx:76,156,166,170`): each `handleGenerate` call captures the current counter value, and `onSuccess`/`onError` ignore the result if the counter has changed in the meantime (a second "Generate" click, a preset change, or closing the modal — see the `useEffect` on `isOpen`, which increments the counter on close). Copying to the clipboard (`handleCopy`, `GeneratePresignedUrlModal.tsx:177`) tracks the copy error state (`copyError`) separately from the generation error state (`generalError`) — they don't overwrite each other.

**Wiring into the table** (`ObjectsTableView.tsx:186,531,622-630`) — a new row menu item, disabled for non-object rows (folders), and the modal itself; the successful-copy toast is raised right here, requiring no changes in `ObjectBrowserView`:

```tsx
// ObjectsTableView.tsx:622-630
<GeneratePresignedUrlModal
  bucketName={bucketName}
  objectKey={presignedUrlTarget?.key ?? null}
  isOpen={presignedUrlTarget !== null}
  onClose={() => setPresignedUrlTarget(null)}
  onCopySuccess={(objectKey) => {
    const { message, ...options } = getPresignedUrlCopiedToast(objectKey)
    toast.success(message, options)
  }}
/>
```

The new toast `getPresignedUrlCopiedToast` (`ObjectToastNotifications.tsx:127-134`) displays the basename of the object key in the same way (`split("/").filter(Boolean).pop()`) as the other toasts in this file — consistent with the existing pattern.

**Documentation** (`packages/aurora/docs/009_ceph_s3_bff.md:181,1095-1141`) is updated in place: an entry is added to the procedure tree, a separate `#### generatePresignedUrl` section with input/output/example, and the asymmetry is spelled out explicitly with `downloadObject` (which streams via the BFF, while this one returns a direct link) and with Swift (HMAC + mandatory key setup there, nothing to configure here). In the limitations section the former line "No presigned URL generation" is replaced with "Presigned URLs are GET-only" — the documentation is updated consistently with the code rather than left stale.

## What it affects

A check across the whole monorepo (`git grep` for `generatePresignedUrl`, `S3_PRESIGN_MAX_EXPIRY_SECONDS`, `getPresignedUrlCopiedToast`, `GeneratePresignedUrlModal` at the head commit) found no consumers outside the files changed by the PR itself. This is a purely additive feature:

- `generatePresignedUrl` is a new procedure; it reuses nothing and is not reused by other routers; it is correctly exported via `objectRouter` → `routers/ceph/index.ts` → the shared `AuroraRouter`, so `trpcClient.storage.ceph.objects.generatePresignedUrl` is actually reachable from the client.
- `S3_PRESIGN_MAX_EXPIRY_SECONDS` is used in only two places: the schema itself (`ceph.ts`) and the modal (`GeneratePresignedUrlModal.tsx`) — exactly as intended (a single source for the bound).
- `GeneratePresignedUrlModal` is wired only into `ObjectsTableView.tsx` (Ceph); the Swift version of the table (`Swift/Objects/ObjectsTableView.tsx`) is not touched and shouldn't be — these are different backends with different scenarios (HMAC vs SigV4).

There are no contract changes (public `AuroraApp` props, existing procedures, exported types) — a new procedure and a new component are added; nothing existing has its signature changed.

## Review

CLAUDE.md compliance, bug scan, historical context, prior feedback and comment compliance were run in parallel over the diff, history and comments.

CLAUDE.md compliance found nothing: the procedure is built on the right builder (`cephProtectedProcedure`, not raw `initTRPC`), the schema extends `projectScopedInputSchema`, the modal lives in a `-components/` directory, the commits follow conventional commits. The historical and prior-feedback agents found no relevant history of problems in the affected files and no open remarks from past PRs that would still apply.

Comment compliance found one nuance of wording inaccuracy (not a functional bug): the comment on `requestIdRef` (`GeneratePresignedUrlModal.tsx:76-81`) states that the counter is incremented "on every generate call and on modal close/reopen" — in fact the `useEffect` increments it only in the `!isOpen` branch (i.e. on close); there is no separate path on reopen. The stale-response protection guarantee is not violated by this (the increment on close already covers any request left over from a previous opening), so this is an inaccuracy of wording, not a bug — it did not reach confidence ≥80.

**No issues with confidence ≥80 were found.**

---
Analyzed: 2026-08-03 · commit `66a33b5f`
