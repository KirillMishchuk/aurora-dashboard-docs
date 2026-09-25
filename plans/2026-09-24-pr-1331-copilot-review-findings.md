# Plan: PR #1331 — Copilot review findings

**Date:** 2026-09-24 · **Status:** implemented 2026-09-24 — все 8 шагов + правки по triple-review, 21 файл, не закоммичено (ветка `kiryl-s3-version-pagination`, HEAD `1602891d`). Все 7 CI-джоб зелёные (aurora 5712 тестов, signal-openstack 177, policy-engine 320 + 1 skipped). Каждый из фиксов 1–4 подтверждён регрессионной проверкой: с откаченной правкой новый тест краснеет. Security-review — Critical/High нет, два Low (см. «Security review» ниже). Triple-review 2026-09-24 (security + performance + architecture) — 14 находок, Critical/High нет; шесть закрыты правками в этой же ветке, остальные вынесены в «Follow-ups» (см. раздел «Triple-review» ниже). Ручная проверка тоста в живом UI и публикация ответов Copilot'у — за пользователем.

## Security review 2026-09-24 — Critical/High нет

Проверены auth/билдеры процедур, валидация входа, раскрытие данных и направление fail-closed логики.

**Чисто:** все три процедуры остались на `cephProtectedProcedure`, билдер не менялся; input-схемы не трогали; все три серверные правки только расширяют множество «не ручаюсь» — `isBucketEmptyWithVersions` (форс удаления версий без чекбокса в `EmptyBucketModal.tsx:117`) срабатывает **реже**, `cannotDelete` в `DeleteBucketModal` блокирует **чаще**; отмена по abort-сигналу не сломана (удаление после разрыва не продолжается); XSS нет — `detail` и `bucketName` рендерятся текстовыми узлами внутри `<Trans>`.

**Low-1 — `onPartial` опционален, частичный результат может потеряться.** `DeleteVersionsModal.tsx:17` объявляет `onPartial?`, тогда как раньше эта ветка уходила в `onError`, который передают все. Модалка реэкспортируется наружу из `Buckets/index.tsx:43`; будущий call-site, передавший `onError` без `onPartial`, получит полностью тихий исход — коллбек no-op, `onSettled` всё равно закроет модалку, и незавершённое удаление версий будет выглядеть как успешное. Сейчас латентно: единственный call-site (`BucketModals.tsx:222-226`) `onPartial` передаёт. Фикс: сделать проп обязательным (стоимость нулевая — call-site один) либо фолбэк `(onPartial ?? onError)?.(...)`.

**Low-2 — постоянный тост несёт сырые сообщения S3/SDK.** `detail` собирается из `formatBulkDeleteErrors`; в degrade-ветке `bulkDeleteItems` (`objectRouter.ts:199-204`) `message` — сырое `error.message` из AWS SDK, на транспортных сбоях содержащее внутренний хост/IP Ceph RGW. До `MAX_REPORTED_DELETE_ERRORS = 100` записей, и живёт в тосте с `duration: Infinity` до ручного закрытия. Поверхность **не новая** — тот же `formatBulkDeleteErrors` уже рендерят `Objects/DeleteVersionModal.tsx:64` и `RestoreVersionModal.tsx:65`; правка её расширяет, но не создаёт. Фикс чинит всех троих разом: в degrade-ветке ставить фиксированный текст, оригинал — только в `console.error` на сервере.

**Не находка:** `duration: Infinity` UI не блокирует (тосты sonner неблокирующие, показываются только после явного подтверждения с вводом имени бакета). Отличие от прецедента `objectDownloadStore.ts:50` — там задан фиксированный `id` и тосты дедуплицируются; здесь `id` нет, поэтому повторные запуски копят стопку. UX-мелочь, при желании — стабильный `id` вида `versions-partial-${bucketName}`.

# 📋 IMPLEMENTATION PLAN: PR #1331 — Copilot review round

All six findings were re-verified against the working tree at `1602891d` (`kiryl-s3-version-pagination`). Two things in the briefing turned out to need correction — flagged inline (Step 2 consumer impact, Step 5 helper signature). Everything else held up.

---

## Overview

Close the Copilot review on PR #1331: three server pagination loops that conflate "scan finished" with "scan stopped without a continuation marker" (findings 2, 3, 5), one client toast that is both mislabelled and auto-dismissed too fast to act on (finding 4), one UI-copy voice violation the PR itself introduced (finding 6), and one false positive that gets a regression test plus a reasoned rejection instead of a code change (finding 1).

Findings 2, 3 and 5 are **one bug in three copies of the same loop**. `objectRouter.ts:1001` already handles it correctly (`if (response.IsTruncated) isPartial = true`) — this is an unfinished propagation of the branch's own pattern. The plan brings all three to one shape.

---

## Architecture Analysis

**Current state**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts` — `containers.getState`, bounded `ListObjectVersions` scan, loop exit at `:300-302`, verdict assembled at `:313-320`.
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/versioningRouter.ts` — `checkDeletedContent`, same scan shape, exit at `:470-473`, page-ceiling branch at `:475-478`, abort branches at `:406` and `:424`.
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts` — `deleteNonCurrentVersions` loop exit at `:1000-1003`; `bulkDeleteItems` at `:148-214` (breaks silently on abort at `:159` and `:190-192`).
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/versionScan.ts` — `isFolderCovered(folderPrefix, stoppedAtKey)`: `stoppedAtKey === undefined` means "fully scanned"; `""` means "nothing is covered".
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/clients/s3Client.ts` — `requestHandler: { connectionTimeout: S3_CONNECTION_TIMEOUT_MS }` (5000, `Storage/constants.ts:33`).
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteVersionsModal.tsx` — closes unconditionally on `onSettled` (`:33-36`), reports via `onSuccess`/`onError` callbacks.
- `.../Ceph/Buckets/BucketModals.tsx` `:205-221` — wires those callbacks to `toast.success` / `toast.error`.
- `.../Ceph/Buckets/BucketToastNotifications.tsx` — `ToastReturnType = { message: ReactNode } & NotificationOptions`; `NotificationOptions.duration?: number` is part of the Juno public type (verified in `@cloudoperators/juno-ui-components@9.4.0` `NotificationManager.types.d.ts`), so `duration: Infinity` is legal inside a helper, not just at the call site.
- `.../Ceph/Buckets/EmptyBucketModal.tsx` `:163, :213, :243` — the three "Please try again." strings.

**Existing patterns to follow**

- Conservative-stop-point pattern: `versioningRouter.ts:406` / `:424` already set `stoppedAtKey = keyMarker ?? ""` on abort. Finding 5's fix reuses that exact sentinel — no change to `versionScan.ts` is needed (verified: `isFolderCovered(p, "")` returns `false` for any non-empty `p`, because `p < ""` is false; and with a non-empty `keyMarker`, folders closed out by earlier pages stay covered).
- Persistent-toast pattern: `.../Ceph/Objects/stores/objectDownloadStore.ts:49-50` — `toast(message, { ...options, id, duration: Infinity })` with the comment "this toast is dismissed explicitly, not on a timer". `<NotificationManager>` in `client/App.tsx:99` leaves `dismissible` at its default `true` and `Toast` renders a close button, so an `Infinity` toast is user-dismissible — no risk of unkillable clutter.
- Toast helper arity: every error helper in `BucketToastNotifications.tsx` is `(bucketName, errorMessage)` and lets the caller compose the detail sentence.

**Proposed changes**

Server: split the conflated exit in three places into "clean end" vs "truncated but no marker". Client: one new toast helper + one new modal prop; three copy strings. Plus one regression test with no production change (finding 1).

---

## Potential Problems & Mitigations

| Risk | Severity | Mitigation |
| --- | --- | --- |
| ⚠️ Finding 5's fix is **not** user-visible on the "Deleted" tab. `ObjectBrowserView.tsx:354-355` filters that tab on `hasDeletedContent` alone and never reads `isPartialScan` (only the "All" branch at `:346` does). So an honest `isPartialScan: true` changes nothing in that view today. The briefing's stated consumer impact is one step optimistic. | Medium | Fix the server contract anyway — `checkDeletedContent` is a **published tRPC procedure** of `@cobaltcore-dev/aurora`, and `isPartialScan: false` currently means "this answer is reliable" when it isn't. Do **not** widen the Deleted-tab filter in this PR: showing folders with no known deleted content would add clutter and is a UX decision. Record as Open Question / follow-up. |
| Finding 5's fix makes more folders report `isPartialScan: true`; the "All" tab then shows deleted folders it used to hide (`:346` `if (status.isPartialScan) return true`). | Low | This is exactly the documented neutral-under-uncertainty behaviour the page-ceiling branch already produces. Only folders at or after the stop point flip; folders closed out by earlier pages stay covered. Assert both halves in the new test. |
| 🔴 Finding 4 changes `DeleteVersionsModal`'s prop surface (`onPartial?`). | Low | Optional prop, additive. The modal is internal to `-components/`, not part of `AuroraApp`'s public slot contract — `packages/aurora/README.md` needs no change. |
| Finding 4's `duration: Infinity` leaves a toast on screen indefinitely if the user ignores it. | Low | `dismissible` defaults true; `visibleToasts` default is 3, so it cannot bury the stack. Same trade-off already accepted in `objectDownloadStore`. |
| Finding 3's `ctx.req.signal?.aborted` check can set `isPartial: true` on a run that actually finished (abort landed after the last delete). | Low | `isPartial` means "not vouching for completeness". A false positive costs the user one extra re-run; a false negative costs silently surviving versions. Document the asymmetry in the code comment. |
| `pnpm check-i18n` rewrites `locales/{en,de}/messages.po` wholesale and can pull in unrelated drift. | Medium | Run it and inspect `git diff` on the two `.po` files before accepting; if it touches msgids unrelated to the three edited strings, that drift predates this PR — decide explicitly whether to keep it (see Step 7). |
| 🔒 None of these changes touch auth, scoping or policy. | — | No permission-key or policy work needed. |

---

## Prerequisites

- [x] Branch `kiryl-s3-version-pagination` at `1602891d`, tree clean — confirmed.
- [x] `@aws-sdk/client-s3@3.1100.0` / `@smithy/node-http-handler@4.9.13` installed — confirmed.
- [x] Open Questions решены пользователем 2026-09-24 (Deleted-tab → follow-up; чистка "Please" — только три строки этого PR; сигнатура тост-хелпера → `(bucketName, detail)`).

---

## Implementation Steps

Order: server first (Steps 1–3 are independent of each other and of the rest), then the no-op regression test (Step 4), then client (Steps 5–6), then release/docs artefacts (Step 7), then the CI gate (Step 8). Steps 1–6 can be done in any order; Steps 7–8 must come last.

---

### Step 1 — Split the conflated loop exit in `containers.getState` (finding 2)

**Files to modify**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts` — loop exit at `:300-302`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/containerRouter.test.ts` — new case

**What to do**

1. Replace `:300-302`:

```ts
      if (!response.IsTruncated) {
        break
      }

      // Truncated, but S3 handed back no continuation marker. Stopping is mandatory —
      // resuming from the same marker would loop on the same page forever — but it is a
      // stop, not a completed scan: the history past this page stays unread. Collapsing
      // the two left hasOnlyDeleteMarkers below asserted off a single page.
      if (!response.NextKeyMarker) {
        isPartialScan = true
        break
      }

      if (pages >= S3_MAX_SCAN_PAGES) {
        isPartialScan = true
        break
      }
```

2. Leave the early exit at `:296` (`hasOldVersionOrDeleteMarker && hasRealVersion`) untouched — both flags are final there, so `isPartialScan: false` is correct.
3. Add a test next to `"does not claim a bucket holds only delete markers when the scan was cut short"` (`containerRouter.test.ts:468`), which uses `IsTruncated: true` **with** a `NextKeyMarker` and therefore misses this hole:

```ts
  it("treats a truncated page with no continuation marker as a partial scan", async () => {
    // IsTruncated with no NextKeyMarker is an edge/malformed S3 response. Stopping is the
    // only safe move, but it is not a finished scan — the two used to share one exit, so
    // hasOnlyDeleteMarkers got asserted from a single page and EmptyBucketModal would then
    // force the delete-versions branch over history it had never read.
    mockOpeningCalls({ status: "Enabled", isEmpty: true })
    mockSend.mockResolvedValueOnce({
      Versions: [],
      DeleteMarkers: [{ Key: "k-1", VersionId: "dm", IsLatest: true }],
      IsTruncated: true,
      NextKeyMarker: undefined,
      $metadata: { httpStatusCode: 200 },
    })

    const ctx = createMockContext()
    const caller = createCaller(ctx)

    const result = await caller.storage.ceph.containers.getState({
      project_id: TEST_PROJECT_ID,
      bucketName: TEST_BUCKET_NAME,
    })

    expect(result.isPartialScan).toBe(true)
    expect(result.hasOnlyDeleteMarkers).toBe(false)
    // The one thing the page did prove stays true.
    expect(result.hasOldVersionsOrDeleteMarkers).toBe(true)
    // isEmpty has its own exact source (ListObjectsV2 MaxKeys:1) and is unaffected.
    expect(result.isEmpty).toBe(true)
  })
```

`mockOpeningCalls` (defined at `containerRouter.test.ts:320`) queues the `GetBucketVersioning` and `ListObjectsV2` responses via `mockResolvedValueOnce`; the third `mockResolvedValueOnce` is the version-scan page.

**Expected outcome** — `hasOnlyDeleteMarkers` can no longer be `true` off an unfinished scan, so `EmptyBucketModal.tsx:75` (`isBucketEmptyWithVersions`) can no longer force `shouldDeleteVersions` (`:117`) over version history that was never read.

**Verification** — `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/containerRouter.test.ts`; revert the production change and confirm the new test fails.

---

### Step 2 — Split the conflated loop exit in `checkDeletedContent` (finding 5)

**Files to modify**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/versioningRouter.ts` — loop exit at `:470-473`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/versioningRouter.test.ts` — new case

**What to do**

1. Replace `:470-473`:

```ts
        if (!response.IsTruncated) {
          stoppedAtKey = undefined
          break
        }

        // Truncated with no continuation marker: stop, but report the stop point the same
        // way the two abort branches above do. Reporting `undefined` here claimed the scan
        // had run to the end, so every folder came back isPartialScan: false — including
        // folders whose nested delete markers were on a page that was never fetched.
        if (!response.NextKeyMarker) {
          stoppedAtKey = keyMarker ?? ""
          break
        }

        if (pages >= S3_MAX_SCAN_PAGES) {
          stoppedAtKey = response.NextKeyMarker
          break
        }
```

2. **Do not touch `helpers/versionScan.ts`.** Verified: `isFolderCovered(p, "")` → `p < ""` is `false` → `false` (partial) for every non-empty prefix; with a non-empty `keyMarker`, `p < keyMarker && !keyMarker.startsWith(p)` keeps folders closed out by earlier pages covered. That is exactly the conservative semantics the abort branches already rely on.
3. Add a test in the `describe("checkDeletedContent")` block (note: the suite's `caller` is created in `beforeEach` over the bare router, so the call is `caller.checkDeletedContent(...)`, not `caller.storage.ceph.versioning...`). All eight existing `IsTruncated: true` fixtures (`:157, :409, :437, :526, :599`) carry a `NextKeyMarker`, so none of them reach this branch:

```ts
    it("treats a truncated page with no continuation marker as a partial scan", async () => {
      // The folder's own marker sorts before its contents ("p/foo/" < "p/foo/x"), so it can be
      // read on a page whose successors never arrive. That used to come back as
      // hasDeletedContent: false with isPartialScan: false — confidently wrong rather than
      // merely unknown.
      mockSend.mockResolvedValueOnce({
        Versions: [{ Key: "p/foo/", VersionId: "fv1", IsLatest: true, LastModified: TEST_DATE }],
        DeleteMarkers: [],
        IsTruncated: true,
        NextKeyMarker: undefined,
      })

      const result = await caller.checkDeletedContent({
        project_id: TEST_PROJECT_ID,
        bucket: TEST_BUCKET_NAME,
        prefix: "p/",
        folders: ["p/foo/"],
      })

      expect(mockSend).toHaveBeenCalledTimes(1)
      expect(result[0].isPartialScan).toBe(true)
      expect(result[0].hasDeletedContent).toBe(false)
      // The marker really was read, so this stays resolved.
      expect(result[0].folderMarkerVersionId).toBe("fv1")
    })
```

4. Optionally add a second assertion proving the fix is not a blanket "everything is partial": with a non-empty `keyMarker` on page 2, a folder sorting strictly before it must still report `isPartialScan: false`. Model it on `"stops at the page ceiling and marks folders past the stop point as partially scanned"` (`versioningRouter.test.ts:521`).

**Expected outcome** — `isPartialScan` becomes honest for every consumer of the published `checkDeletedContent` procedure.

⚠️ **Scope note:** as recorded under Risks, this does **not** change the "Deleted" tab rendering today, because `ObjectBrowserView.tsx:354-355` never reads the flag. Do not extend that filter here.

**Verification** — `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/versioningRouter.test.ts`.

---

### Step 3 — Honour the abort signal at `deleteNonCurrentVersions`'s last-page exit (finding 3)

**Files to modify**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts` — `:1000-1003`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.test.ts` — one new case, one amended case

**What to do**

1. Replace `:1000-1003`:

```ts
        if (!response.IsTruncated || !response.NextKeyMarker) {
          // Truncated without a usable continuation marker, or aborted while this page's
          // deletes were in flight. bulkDeleteItems breaks out silently on abort — no
          // deletion recorded, no error recorded — so this is the last place that can say
          // the run did not cover the bucket. A false positive is harmless: isPartial means
          // "not vouching for completeness", and the cost is one re-run.
          if (response.IsTruncated || ctx.req.signal?.aborted) isPartial = true
          break
        }
```

2. New test, next to `"stops without throwing when the request is aborted mid-scan"` (`objectRouter.test.ts:1600`):

```ts
  it("reports a partial run when the client aborts while the last page is being deleted", async () => {
    const controller = new AbortController()
    // Last page: nothing more to list.
    mockSend.mockImplementationOnce(() =>
      Promise.resolve({
        Versions: [
          { Key: "a.txt", VersionId: "v2", IsLatest: true },
          { Key: "a.txt", VersionId: "v1", IsLatest: false },
        ],
        DeleteMarkers: [],
        IsTruncated: false,
      })
    )
    // The disconnect lands on the DeleteObjects call. bulkDeleteItems returns
    // {deletedCount: 0, errors: []} — indistinguishable from a clean no-op.
    mockSend.mockImplementationOnce(() => {
      controller.abort()
      return Promise.resolve({ Deleted: [], Errors: [] })
    })

    const ctx = createMockContext({ abortSignal: controller.signal })
    const caller = createCaller(ctx)

    const result = await caller.storage.ceph.objects.deleteNonCurrentVersions({
      project_id: TEST_PROJECT_ID,
      containerName: TEST_BUCKET_NAME,
    })

    expect(result.isPartial).toBe(true)
    expect(result.errorCount).toBe(0)
  })
```

`createMockContext({ abortSignal })` is already supported (`routers/ceph/mockContext.ts:24, :42, :44`).

3. Amend the existing test at `:1600` — it currently asserts only `deletedCount`, `errorCount` and the call count. Add:

```ts
    expect(result.isPartial).toBe(true)
```

**Severity note for the PR reply** — user-facing impact is nil: `ctx.req.signal` fires only on a broken HTTP connection (`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/context.ts:131-152` — `res.raw "close"` when `!writableEnded`, `req.raw "close"` when `!complete`, `req.raw "error"` on `ECONNRESET`/`ECONNABORTED`). Abort therefore implies nobody is left to read the response. This is fixed for internal consistency with the invariant the same function already states two branches above (`:859-862`, `:876-879`), not for a user-visible defect. Say so in the reply rather than accepting Copilot's "High".

**Verification** — `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/objectRouter.test.ts`.

---

### Step 4 — Pin the S3 `connectionTimeout` behaviour with a regression test (finding 1, rejected)

**Files to modify**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/clients/s3Client.test.ts` — one new case. **No production change.**

**Why no production change** — verified three ways:
- `@aws-sdk/client-s3@3.1100.0`, `dist-cjs/index.js:4819`: `requestHandler: NodeHttpHandler.create(config?.requestHandler ?? defaultConfigProvider)`.
- `@smithy/node-http-handler@4.9.13:217-222`: `static create(instanceOrOptions) { if (typeof instanceOrOptions?.handle === "function") return instanceOrOptions; return new NodeHttpHandler(instanceOrOptions) }`.
- `S3Client.d.ts:144` types it `HttpHandlerUserInput` = `HttpHandler | NodeHttpHandlerOptions | FetchHttpHandlerOptions | Record<string, unknown>`, documented as "provide the constructor arguments as an object".

**Empirically confirmed on this branch**: the resolved handler is a `NodeHttpHandler` and `httpHandlerConfigs().connectionTimeout === 5000`. Note `httpHandlerConfigs()` returns `{}` until the handler's lazily-resolved config is materialised, which happens on the first `handle()` call — so the test has to force that. An already-aborted signal does it without opening a socket (`handle()` awaits the config provider *before* the abort check).

**Add this test** (I wrote it into the suite, ran `vitest` and `tsc --noEmit` against it, both green, then removed it — the snippet below is the verified version):

```ts
    it("applies the Ceph connection timeout to the underlying HTTP handler", async () => {
      // The SDK accepts requestHandler as either an HttpHandler instance or the
      // NodeHttpHandler constructor options (NodeHttpHandler.create branches on
      // `typeof x.handle === "function"`), and this file passes the options object.
      // Pin the resulting behaviour so an SDK upgrade that narrowed that contract
      // would fail here rather than silently drop the timeout.
      const client = createS3Client(TEST_ACCESS, TEST_SECRET, TEST_ENDPOINT, TEST_REGION)

      const handler = (await client.config.requestHandler) as unknown as {
        handle: (request: unknown, options: { abortSignal: AbortSignal }) => Promise<unknown>
        httpHandlerConfigs: () => { connectionTimeout?: number }
      }

      // NodeHttpHandler resolves its config lazily, on the first handle() call, and
      // httpHandlerConfigs() reports {} until then. An already-aborted signal forces
      // that resolution and rejects before any socket is opened.
      const controller = new AbortController()
      controller.abort()
      await expect(
        handler.handle(
          {
            protocol: "https:",
            hostname: "test-ceph.example.com",
            port: 443,
            method: "GET",
            path: "/",
            headers: {},
            query: {},
          },
          { abortSignal: controller.signal }
        )
      ).rejects.toThrow()

      expect(handler.httpHandlerConfigs().connectionTimeout).toBe(S3_CONNECTION_TIMEOUT_MS)
    })
```

Place it inside `describe("successful client creation")` (after the `forcePathStyle` case at `:26`) and add the import:

```ts
import { S3_CONNECTION_TIMEOUT_MS } from "../constants"
```

The `as unknown as {...}` cast is needed because `NodeHttpHandler`'s d.ts types `handle`'s first parameter as the `HttpRequest` class, and `@smithy/*` is not a direct dependency of `packages/aurora` (only `@aws-sdk/client-s3` is) — importing from it would create a phantom dependency and would not survive `licenses:check`'s dependency model.

**Expected outcome** — the suite goes from 20 to 21 cases; the file gains its first assertion about `requestHandler`.

**Verification** — `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/clients/s3Client.test.ts`; then temporarily delete the `requestHandler` key from `s3Client.ts` and confirm the new test fails (`connectionTimeout` becomes `undefined`).

---

### Step 5 — Relabel and persist the partial-delete report (finding 4)

Copilot's premise is right, its remedy is not. Verified: both `DeleteVersionsModal.tsx:76-84` (`errorCount > 0`) and `:88-95` (`isPartial`) route to `onError` → `BucketModals.tsx:216-220` → `getVersionsDeleteErrorToast` → `toast.error` with no options; `App.tsx:99` renders `<NotificationManager position="top-right" />` with no `duration`, and Juno 9.4.0's documented default is `4000` ms. Two sentences of actionable copy get four seconds.

Copilot's proposed fix — a persistent `<Message>` inside the modal — is rejected: the modal closes unconditionally on `onSettled` (`:33-36`), so an in-modal result banner would require a second "form → result" phase and would break the convention every one of the seven modals in `BucketModals.tsx` follows (close, then report by toast).

**Deviation from the briefing's sketch (deliberate):** the briefing proposed `getVersionsPartiallyDeletedToast(bucketName, deletedCount)`. I recommend `(bucketName: string, detail: string)` instead, matching the arity of every error helper in the file. Reason: the count is not the only thing the partial branches carry — the `errorCount > 0 && deletedCount > 0` case (item **c** below) also needs `formatBulkDeleteErrors(...)` in the description, and the modal already owns that composition. A count-only signature forces either a second near-duplicate helper or conditional interpolation inside a `<Trans>`, both worse. One helper, one caller-composed sentence.

**Files to modify**

- `.../Ceph/Buckets/BucketToastNotifications.tsx`
- `.../Ceph/Buckets/DeleteVersionsModal.tsx`
- `.../Ceph/Buckets/BucketModals.tsx`
- `.../Ceph/Buckets/BucketToastNotifications.test.tsx`
- `.../Ceph/Buckets/DeleteVersionsModal.test.tsx`

(all under `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/`)

**What to do**

1. **New helper** in `BucketToastNotifications.tsx`, immediately after `getVersionsDeleteErrorToast` (`:165-172`):

```tsx
export const getVersionsPartiallyDeletedToast = (bucketName: string, detail: string): ToastReturnType => ({
  message: <Trans>Versions Partially Deleted</Trans>,
  description: (
    <Trans>
      Bucket "{bucketName}" was not fully processed: {detail}
    </Trans>
  ),
  // duration: Infinity — this toast asks the user to run the action again. The 4s default
  // is not enough to read it, let alone act on it. Dismissed by the user, not by a timer
  // (same reasoning as the object-download toast in Objects/stores/objectDownloadStore.ts).
  duration: Infinity,
})
```

`duration` is a declared member of Juno's `NotificationOptions`, which `ToastReturnType` intersects, so this typechecks without a cast.

2. **New optional prop** on `DeleteVersionsModal` (`:11-17`):

```ts
  onPartial?: (bucketName: string, detail: string) => void
```

and add it to the destructure at `:19`.

3. **Rewrite the `onSuccess` handler** (`:72-97`) so the three outcomes are labelled correctly — this is item **(c)**, the defect Copilot missed and the one that matters more than the timer. Today a run that deleted 12 of 13 versions is announced as **"Failed to Delete Versions"** with a description that opens "Deleted 12 version(s), but…" — the title contradicts its own body.

```ts
        onSuccess: (result) => {
          const { deletedCount, errorCount } = result
          // S3's DeleteObjects can fail some keys while succeeding on others inside one
          // HTTP 200 (see deleteObjectsBulkOutputSchema).
          if (errorCount > 0) {
            const detail =
              result.errors.length > 0
                ? formatBulkDeleteErrors(result.errors)
                : t`${errorCount} item(s) could not be deleted`
            // Nothing got through: a plain failure. Anything else really did delete
            // versions, which is a partial result, not a failed one.
            if (deletedCount === 0) {
              onError?.(bucketName, detail)
            } else {
              onPartial?.(bucketName, t`Deleted ${deletedCount} version(s); ${detail}`)
            }
            return
          }
          // The scan stopped before the end of the bucket (aborted, a key it could not read,
          // or a truncated page with no continuation marker), so versions may survive.
          // Reporting the count alone would read as a completed wipe.
          if (result.isPartial) {
            onPartial?.(
              bucketName,
              t`Deleted ${deletedCount} version(s), but the scan did not reach the end of the bucket. Non-current versions may remain — run Delete Versions again.`
            )
            return
          }
          onSuccess?.(bucketName, deletedCount)
        },
```

`onError` stays wired to the mutation's own `onError` (`:98-100`) and to the `errorCount > 0 && deletedCount === 0` case — both are genuine failures.

4. **Wire it up** in `BucketModals.tsx`, alongside the existing `onSuccess`/`onError` at `:210-220`:

```tsx
        onPartial={(bucketName, detail) => {
          const { message, ...options } = getVersionsPartiallyDeletedToast(bucketName, detail)
          toast.warning(message, options)
          onClose()
        }}
```

`toast.warning` is the established channel for "it happened, but not the way you asked" — 8 existing call sites (e.g. `Ceph/Objects/ObjectBrowserView.tsx:564`, `Swift/Containers/index.tsx:94`). `options` carries `duration: Infinity` through the spread, mirroring `objectDownloadStore.ts:50`.

Add `getVersionsPartiallyDeletedToast` to the import list at the top of `BucketModals.tsx`.

5. **Tests**
   - `BucketToastNotifications.test.tsx`: add the helper to the `notifications` array in `"all helpers return a message and description as ReactNodes"` (`:258-286`) and add a `describe("getVersionsPartiallyDeletedToast")` block asserting the title renders as `"Versions Partially Deleted"`, the description contains the bucket name and the detail, and `toast.duration === Infinity`.
   - `DeleteVersionsModal.test.tsx`: rename/retarget the existing case `"warns instead of reporting success when the wipe did not reach the end of the bucket"` (currently asserts `onError` was called with a string containing `"not processed completely"`) so it asserts `onPartial` instead, and that `onError` was **not** called. Retarget `"reports an error instead of success when the mutation resolves with errorCount > 0"` to the new split: with `deletedCount: 1, errorCount: 1` it must call `onPartial`, not `onError`. Add a new case with `deletedCount: 0, errorCount: 1` asserting `onError` (and not `onPartial`).

6. **Boundary check — verified, nothing else to fix.** I checked the sibling modals for the same "Failed at partial success" mislabel:
   - `EmptyBucketModal.tsx` — `onSuccess` receives a bare `deletedCount` and has no `errorCount`/`isPartial` branch; nothing to mislabel.
   - `EmptyBucketsModal.tsx` — no `errorCount` handling at all.
   - `Objects/DeleteObjectsModal.tsx` — already handles partials correctly and differently: on `errorCount > 0` it keeps the modal open and renders an in-place `{deletedCount} deleted, {errorCount} failed` result panel (`:56-60`, `:140-145`) rather than firing an error toast.

   So the defect is unique to `DeleteVersionsModal`, and it is a string this PR introduced. No follow-up needed here.

**Expected outcome** — a partial delete-versions run produces a persistent warning toast titled "Versions Partially Deleted"; only a genuine total failure still says "Failed to Delete Versions".

**Verification** — `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/` (quote the `$`).

---

### Step 6 — Remove "Please" from the three EmptyBucketModal strings (finding 6)

**Files to modify**

- `.../Ceph/Buckets/EmptyBucketModal.tsx` — `:163`, `:213`, `:243`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/locales/en/messages.po`, `.../de/messages.po` — regenerated, not hand-edited

**What to do**

1. Replace all three with:

```tsx
<Trans>Unable to verify bucket versioning status and contents. Try again.</Trans>
```

2. Run `pnpm check-i18n` (lingui extract + compile, `packages/aurora` only) and inspect `git diff -- packages/aurora/src/locales`. Expect the old msgid at `:3968` to be replaced in both files. The German `msgstr` for it is currently empty, so no translation is lost.

**The claim is specific to this PR, not a pre-existing nit**: `git diff main...HEAD` shows the PR itself rewrote all three strings (collapsing separate "versioning status" / "contents" / combined variants into one wording) and carried "Please" forward into the new text. The rule is stated three times in `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.github/copilot-instructions.md` — the checklist at `:57`, the voice rule at `:559` ("Voice: active and impersonal. No 'We', 'Us', 'Please', 'Thanks'"), and the Reject list at `:566`.

🚧 **Boundary — do not widen.** "Please" appears ~70 more times in the client, concentrated in `client/utils/useErrorTranslation.ts` (Compute/flavors) and `client/components/Errors/RouteError.tsx`. None of it is touched by this PR's diff. Leave it; propose a standalone copy-cleanup PR (see Open Questions).

**Verification** — `grep -rn "Please" packages/aurora/src/client/routes/_auth/projects/\$projectId/storage/` returns nothing; `pnpm check-i18n` exits 0.

---

### Step 7 — Update the changeset and the PR description

**Files to modify**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.changeset/ceph-bounded-version-scans-and-delete-versions.md`
- `/Users/kirylmishchuk/projects/SAP/DOCS/descriptions/pr-1331-description.md` (plus the same edit pasted into the PR body on GitHub — the file is currently byte-identical to what is published)

**Changeset — recommendation: amend the existing file, do not add a new one.** Rationale:
- It is `minor`, unreleased, and describes exactly the code these fixes touch (`containers.getState`, `checkDeletedContent`, `deleteNonCurrentVersions`, `s3Client`). A separate `patch` changeset would emit a CHANGELOG entry describing a fix to behaviour that never shipped, which reads as noise to consumers and inflates the release notes.
- A `patch` alongside a `minor` on the same package does not change the bump anyway — `minor` wins.
- The existing text already makes claims that the fixes make *true*: "Each of those, and an aborted run, sets `isPartial: true`" (Step 3 closes the last hole in that sentence) and "A new per-folder `isPartialScan` flag reports an incomplete scan instead of guessing" (Step 2). Leaving them unamended would ship a changeset that overstates the code.

Concrete edits to the changeset text:
- In the `deleteNonCurrentVersions` bullet, keep "and an aborted run, sets `isPartial: true`" — now accurate for every exit path including the last page.
- In the `checkDeletedContent` paragraph, after "caps the scan at 20 pages", add that a truncated page without a continuation marker is also reported as partial rather than as a completed scan.
- In the `containers.getState` bullet, same addition for `isPartialScan`.
- Add one sentence about the delete-versions modal now distinguishing a partial result from a failure.

**PR description — sections affected** (headings verified against the file):
- `### New storage.ceph.containers.getState` (line 21) — the `isPartialScan` bullet currently reads "set when the ceiling was reached"; extend to "…or when a truncated page carried no continuation marker".
- `### Updated storage.ceph.versioning.checkDeletedContent` (line 30) — same addition to "Returns a per-folder `isPartialScan` instead of guessing completeness".
- `## Core Infrastructure` (line 38) — the `clients/s3Client.ts` bullet: optionally note the timeout is now covered by a regression test (this is where the finding-1 rejection is documented in-repo).
- `## Component Updates` (line 47) — the `DeleteVersionsModal` bullet: replace "reports partial per-key failures as errors" with the corrected three-way split (failure / partial / success) and the persistent warning toast; the `EmptyBucketModal` bullet needs no change (copy edit only).
- `## Tests` (line 61) — add the new cases: the marker-less truncated page in all three routers, the abort-on-last-page case, the `requestHandler` timeout case.
- `# Behaviour and Contract Changes` (line 65) — worth one line that `isPartialScan` / `isPartial` now cover the marker-less-truncation and late-abort cases, since external consumers of the published procedures will see `true` in situations that previously reported `false`.

Sections **not** affected: `# Summary`, `### New storage.ceph.objects.deleteNonCurrentVersions` (its contract is unchanged), `## Types`, `# Related Issues`, `# Testing Instructions`, `# Checklist`.

**Verification** — `git diff .changeset/` reads as a description of the shipped code with no remaining overstatement; the two description files (local + GitHub body) stay in sync.

---

### Step 8 — Run the CI gate locally

Run from `/Users/kirylmishchuk/projects/SAP/aurora-dashboard`, in the order CI runs them (`.github/workflows/ci-checks.yaml`):

```bash
pnpm licenses:check
pnpm lint
pnpm check-i18n
pnpm typecheck
pnpm format:check
pnpm test
pnpm build
```

Scope the fast inner loop with `--filter @cobaltcore-dev/aurora` (`test`, `typecheck`, `lint`), but run the unscoped set once before handing the PR back — `format:check` and `build` cover the whole workspace.

Note `pnpm check-i18n` is a *mutating* job (it rewrites the `.po` files). Run it before `format:check`, and re-run `pnpm format` if it leaves unformatted output.

**Verification** — all seven exit 0; `git status` shows only the files this plan names.

---

## Testing Plan

**Unit tests (new)**
- [ ] `containerRouter.test.ts` — `IsTruncated: true` + `NextKeyMarker: undefined` → `isPartialScan === true`, `hasOnlyDeleteMarkers === false`, `hasOldVersionsOrDeleteMarkers === true`, `isEmpty === true`.
- [ ] `versioningRouter.test.ts` — same shape → `isPartialScan === true` with `hasDeletedContent === false` and the folder marker still resolved.
- [ ] `versioningRouter.test.ts` (optional) — non-empty `keyMarker` stop point → folders sorting before it stay `isPartialScan === false`.
- [ ] `objectRouter.test.ts` — abort during the last page's `DeleteObjects` → `isPartial === true`, `errorCount === 0`.
- [ ] `s3Client.test.ts` — resolved handler reports `connectionTimeout === S3_CONNECTION_TIMEOUT_MS`.
- [ ] `BucketToastNotifications.test.tsx` — `getVersionsPartiallyDeletedToast` renders title/description and carries `duration: Infinity`.
- [ ] `DeleteVersionsModal.test.tsx` — `deletedCount > 0 && errorCount > 0` → `onPartial`; `deletedCount === 0 && errorCount > 0` → `onError`; `isPartial` → `onPartial`; clean run → `onSuccess`.

**Unit tests (amended)**
- [ ] `objectRouter.test.ts:1600` — add `expect(result.isPartial).toBe(true)`.
- [ ] `DeleteVersionsModal.test.tsx` — the two existing `onError` expectations retargeted to `onPartial`.
- [ ] `BucketToastNotifications.test.tsx:258-286` — new helper added to the exhaustiveness array.

**Regression guard (do this per step, not at the end)** — for each of Steps 1–4, revert the production edit, confirm the new test goes red, restore. Findings 2/3/5 are all "the wrong flag on a path no existing fixture exercises"; a test that passes both with and without the fix is worthless here.

**Manual verification**
1. Copy edit: open a Ceph bucket → Empty Bucket, in each of the three states (loading/query error, empty-with-versions, normal) confirm the sentence ends "Try again." and no "Please" appears.
2. Partial delete: with `S3_MAX_SCAN_PAGES` temporarily lowered (or a stubbed router), run Delete Versions on a bucket large enough to trip `isPartial`. Confirm the toast is a **warning** titled "Versions Partially Deleted", that it does not self-dismiss after ~4 s, and that it can be dismissed by clicking its close button.
3. Total failure: force `errorCount > 0, deletedCount === 0` — confirm the toast is still an **error** titled "Failed to Delete Versions".
4. Confirm the modal still closes immediately in all three cases (the `onSettled` behaviour is unchanged).

---

## Acceptance Criteria

- [ ] All three scan loops distinguish "reached the end" from "stopped without a continuation marker"; none of them can return a clean-scan verdict off an unfinished scan.
- [ ] `deleteNonCurrentVersions` sets `isPartial` on every abort path, including the last page.
- [ ] `s3Client.ts` is unchanged, and a test now fails if the `connectionTimeout` stops reaching the handler.
- [ ] A partial delete-versions run is reported as a persistent warning, not as a 4-second "Failed"; a total failure is still reported as an error.
- [ ] The three EmptyBucketModal strings comply with the repo voice rule; `locales/{en,de}/messages.po` are regenerated by `pnpm check-i18n`, not hand-edited.
- [ ] No "Please" cleanup outside the files this PR already touches.
- [ ] The existing changeset is amended (no new changeset file) and no longer overstates what the code does.
- [ ] `/Users/kirylmishchuk/projects/SAP/DOCS/descriptions/pr-1331-description.md` and the published PR body are updated in the six sections listed in Step 7 and remain byte-identical to each other.
- [ ] No regressions: `pnpm licenses:check`, `lint`, `check-i18n`, `typecheck`, `format:check`, `test`, `build` all pass.
- [ ] Six reply comments posted on PR #1331 (texts below) — posting is manual, by the user.

---

## Open Questions

Все три закрыты пользователем 2026-09-24 — блокеров для начала работ нет.

1. ✅ **РЕШЕНО 2026-09-24 — вариант (a): завести follow-up, в этот PR не тащим.** Шаг 2 чинит серверный контракт (`isPartialScan` перестаёт врать), поведение вкладки «Deleted» не меняется. Расширение её фильтра — отдельная задача с продуктовым решением, см. раздел «Follow-ups» ниже.
   <details><summary>исходная формулировка вопроса</summary>

   **Deleted-tab visibility (blocks nothing, but decides a follow-up).** `ObjectBrowserView.tsx:354-355` filters the "Deleted" tab on `hasDeletedContent` alone and ignores `isPartialScan`; only the "All" branch (`:346`) treats the flag neutrally. Step 2 makes the server flag honest but changes nothing in that tab. Options: (a) leave as is and open a follow-up issue — my recommendation, since surfacing folders with *no known* deleted content in a tab whose whole purpose is showing deleted content is a product decision; (b) show partially-scanned folders there with an "unverified" affordance, which needs design input. Which?
   </details>
2. ✅ **РЕШЕНО 2026-09-24 — чиним только три строки в `EmptyBucketModal`, которые переписал сам PR.** Остальные ~70 вхождений (`client/utils/useErrorTranslation.ts`, `client/components/Errors/RouteError.tsx` и прочие) остаются вне #1331 и уходят отдельным `style(portal):` PR — см. «Follow-ups» п. 2. Причины: PR про S3-сканы, 70 правок текстов Compute утопили бы в диффе сам фикс; каждая правка меняет msgid, и `pnpm check-i18n` раздул бы дифф `.po` с двух строк до семидесяти с лишним.
3. ✅ **РЕШЕНО 2026-09-24 — принят вариант планировщика: `getVersionsPartiallyDeletedToast(bucketName: string, detail: string)`.** Строку составляет модалка и передаёт готовой, как это уже делает соседняя `getVersionsDeleteErrorToast(bucketName, errorMessage)`. Счётчиковая сигнатура `(bucketName, deletedCount)` из брифа отклонена: ветка `errorCount > 0 && deletedCount > 0` должна нести ещё и `formatBulkDeleteErrors(result.errors)`, которую собирает модалка, — числом это не передать, пришлось бы заводить второй почти идентичный хелпер либо ставить условную логику внутрь `<Trans>` (ломает извлечение строк для переводчиков). Шаг 5 расписан уже под эту сигнатуру, менять его не нужно.

---

## Triple-review 2026-09-24 — 14 находок, Critical/High нет

Три ревьюера по одному диффу. Вердикты: security — «поверхность только сужается, Critical/High/Medium = 0»; performance — «round-trip'ов к S3 не добавилось, ранние выходы и потолок целы»; architecture — «изменение архитектурно здоровое, конвенции соблюдены».

**Закрыто правками в этой ветке (+3 файла: `helpers/versionScan.ts`, его тест, `types/ceph.ts`):**

1. **Классификация исхода теряла `isPartial`** (architecture, главная находка). Ветка `errorCount > 0` в `DeleteVersionsModal` завершалась `return` до проверки `isPartial`, а сервер ставит `isPartial = true` в тех же трёх местах, где вызывает `recordErrors` (`NoCurrentVersion`, `MissingVersionId`, `TooManyVersions`) — то есть самый обычный частичный прогон терял именно фразу «run Delete Versions again». Оба измерения теперь считаются независимо. Дефект внесён этим же планом (шаг 5).
2. **`stoppedAtKey` отбрасывал целую прочитанную страницу** (performance). Заменено на `greatestKeyOnPage(...)` — новый чистый хелпер в `helpers/versionScan.ts`. Аргумент ревьюера про «до 1000 лишних строк» завышен (ветка требует ответа, нарушающего спеку S3), но решает другое: соседняя ветка потолка страниц уже использует точную границу, и держать рядом две разные точности без причины — ровно та несогласованность, из-за которой случился весь раунд.
3. **Неограниченный `detail` в невечно-гаснущем тосте** (performance). Спеллится не более трёх записей, остальные сворачиваются в счётчик.
4. **Тост без стабильного `id`** (performance/architecture). Добавлен `versions-partial-${bucketName}` — повторный запуск заменяет отчёт, а не вешает второй вечный тост.
5. **`detail` склеивался из двух отдельно переводимых предложений** (architecture). Хелпер принимает структуру `{deletedCount, errorCount, errors, incomplete}` и владеет всем текстом; каждое предложение переводится целиком, `version(s)` ушло в `<Plural>`. Прецедент — `getBucketsEmptyCompleteToast`.
6. **`onPartial` был опционален** (security Low-1, architecture). Проверено: `DeleteVersionsModal` не экспортируется из `client/index.ts`, а бочка `Buckets/index.tsx:43` не имеет ни одного импортёра — «ломать внешний контракт» нечего, проп сделан обязательным.

Плюс JSDoc обеих Zod-схем (`isPartialScan`, `isPartial`) догнал changeset — третья причина остановки и независимость `isPartial` от `errorCount` теперь описаны там, где их читает потребитель библиотеки.

**Новые тесты:** комбинация `errorCount > 0 && deletedCount > 0 && isPartial: true`; `deletedCount === 0` с незавершённым сканом (partial, а не error); первая страница, усечённая без маркера, кредитует прочитанные ключи; `greatestKeyOnPage` (4 кейса, включая то, что папка с граничным ключом остаётся непокрытой); ограничение списка ошибок и стабильный id тоста. Обе ключевые правки подтверждены регрессией — с откаченным фиксом новые тесты краснеют (2 из 14 в модалке, 1 из 41 в роутере).

**CI после правок:** `licenses:check`, `lint`, `check-i18n`, `typecheck`, `format:check`, `build` — зелёные; `test` — aurora 235 файлов / 5725 тестов, signal-openstack 177, policy-engine 320 + 1 skipped. Дифф `.po` — восемь msgid, все наши.

---

## Follow-ups (вне этого PR)

1. **Вкладка «Deleted» игнорирует `isPartialScan`.** `ObjectBrowserView.tsx:354-355` фильтрует её только по `hasDeletedContent`. После шага 2 сервер честно сообщает, что скан не дошёл до конца, но эта вкладка флаг не читает — папка с непроверенным содержимым просто не показывается, и пользователь не узнаёт, что ответ неполон. Ветка «All» (`:346`) такой случай уже обрабатывает нейтрально (`if (status.isPartialScan) return true`).
   Что решить: показывать ли частично отсканированные папки во вкладке «Deleted» и с какой пометкой («не подтверждено» / иконка / подсказка). Это продуктовое и дизайнерское решение: вкладка существует ровно для показа удалённого содержимого, а такие папки — «мы не знаем, есть ли там удалённое».
   Решено 2026-09-24: в PR #1331 не тащим, оформить отдельной задачей.

2. **«Please» в остальном клиенте.** ~70 вхождений против правила `.github/copilot-instructions.md:559`, преимущественно `client/utils/useErrorTranslation.ts` (Compute/flavors) и `client/components/Errors/RouteError.tsx`. Отдельный `style(portal):` PR — см. Open Question 2.


3. **Вынести цикл пагинации `ListObjectVersions` в общий хелпер.** Главный техдолг участка по оценке architecture-ревью: три почти идентичных `while (true)` в `containerRouter.getState`, `versioningRouter.checkDeletedContent` и `objectRouter.deleteNonCurrentVersions` — проверка abort на входе и в `catch`, счётчик страниц, потолок `S3_MAX_SCAN_PAGES`, разбор `IsTruncated`/`NextKeyMarker`, продвижение маркеров. Этот PR чинил один дефект трижды. Предложение: async-генератор `scanObjectVersions(s3, {bucket, prefix, signal, maxPages})` в `helpers/versionScan.ts`, отдающий страницы и единый `stopReason: "complete" | "aborted" | "page-ceiling" | "no-continuation-marker"`; роутеры мапят `stopReason` в свой флаг. Заодно схлопнутся три разных формулировки комментария и закрепится общий словарь (`isPartial` vs `isPartialScan`, `stopReason` как первичное понятие). Защита `MAX_SAME_MARKER` сейчас есть только в `objectRouter` — при выносе достанется всем.

4. **Маркер возобновления для `deleteNonCurrentVersions`.** Сообщение о частичном исходе просит запустить действие ещё раз, а повторный запуск пересканирует бакет с первого ключа. Возвращать точку останова и принимать её опциональным входом — тогда повтор стоит O(остатка), а не O(всей истории). Прогресс монотонен: каждое удаление адресует конкретный `VersionId` и не создаёт новых маркеров. Это фича, а не ответ на замечание ревью, поэтому вне #1331.

5. **Не пробрасывать сырое `error.message` из AWS SDK в UI.** В degrade-ветке `bulkDeleteItems` (`objectRouter.ts:199-204`) в `errors[].message` попадает сообщение SDK, на транспортных сбоях содержащее внутренний хост/IP Ceph RGW. Оригинал должен оставаться в серверном `console.error`, наружу — фиксированный текст. Чинит трёх потребителей разом (`DeleteVersionsModal`, `Objects/DeleteVersionModal.tsx:64`, `RestoreVersionModal.tsx:65`). В #1331 смягчено ограничением списка тремя записями, но источник не тронут.

6. **Мемоизация списков в `ObjectBrowserView`.** `filteredObjects` (`:273`), `filteredFolders` (`:370`) и три выражения сортировки (`:374`, `:411`, `:434`) — обычные выражения, не мемо, над списками до 1000 элементов без виртуализации, пересчитываются на каждый рендер, включая каждое нажатие клавиши в поиске (дебаунс откладывает запрос, но не ре-рендер). Pre-existing, к #1331 отношения не имеет.

7. **Выровнять `checkDeletedContentInputSchema.bucket`.** Сейчас голый `z.string().min(1)` (`types/versioning.ts:143`), тогда как соседние процедуры используют `existingBucketNameSchema` с ограничением длины. Не эксплуатируется — имена бакетов уходят в SDK параметром команды и экранируются в path-style URL, — но расхождение стоит убрать при следующей правке файла.

8. **Не удалять неполную группу ключей, когда truncated-страница пришла без `NextKeyMarker`** (`objectRouter.ts:929`). Обрабатывать последнюю группу только если её current-запись — обычная версия; если current — delete-маркер, пропускать с записью в `errors` + `isPartial` (иначе за границей страницы остаётся более старая версия, она становится current, и удалённый объект воскресает живым). Существующий тест `objectRouter.test.ts:1469` обязан остаться зелёным — он закрывает противоположный риск. Заведено раундом 4, подробности: [2026-09-25-pr-1331-copilot-review-round-4.md](./2026-09-25-pr-1331-copilot-review-round-4.md).

9. **`deleteNonCurrentVersions` теряет отчёт о прошлых страницах при systemic-сбое** (`objectRouter.ts:989` + `:196`). `bulkDeleteItems` судит о systemic-сбое по своим локальным массивам, а зовётся постранично — падение на второй странице реджектит мутацию, и ни `deletedCount` прошлых страниц, ни `isPartial` («запустите ещё раз») до пользователя не доходят. Обернуть постраничный вызов в try/catch; сигнатуру хелпера не трогать. Заведено раундом 4.

10. **Вкладка Deleted должна fail-closed** (`ObjectBrowserView.tsx:358`). Возвращать `[]` в ветке Deleted, нейтральный `allFolders` оставить только для All. **Делать одной задачей с п. 1** (видимость `isPartialScan`) и находкой 1 раунда 3 (видимый UI состояния скана). Туда же: рассинхрон `enabled` запроса (`:164`, только `Enabled`) с условием показа вкладки (`:654`, `!== "Unversioned"`) — на Suspended-бакете вкладка Deleted показывает все папки всегда. Разрушающих действий у ложно показанной папки нет (`ObjectsTableView.tsx:580-581`, `:481`) — это косметика. Заведено раундом 4.

11. **Empty Bucket не должен запускать удаление версий без `storage:object_versions:delete`.** Прокинуть `canDeleteVersion` в `EmptyBucketModal` и закрыть им и авто-ветку `isBucketEmptyWithVersions` (`:77`, `:121`), и чекбокс (`:298-303`). Чинит `main`, а не изменение #1331: те же ворота стоят на `BucketTableView.tsx:255`. Серверной проверки прав на Ceph-процедурах нет вовсе (`cephProcedure.ts:107`) — это выравнивание аффордансов UI, не граница безопасности. Заведено раундом 4.
---

# Copilot reply texts (English, for manual posting)

### Finding 1 — `s3Client.ts:34` (Copilot: High) — declining

> Not a defect — the SDK accepts both forms here.
>
> `S3Client`'s constructor runs `requestHandler` through `NodeHttpHandler.create()` (`@aws-sdk/client-s3@3.1100.0`, `dist-cjs/index.js:4819`), and `create()` branches on whether the argument is already a handler:
>
> ```js
> // @smithy/node-http-handler@4.9.13:217-222
> static create(instanceOrOptions) {
>   if (typeof instanceOrOptions?.handle === "function") return instanceOrOptions
>   return new NodeHttpHandler(instanceOrOptions)
> }
> ```
>
> A plain object with no `handle` method takes the second branch and becomes the constructor arguments. That is the documented contract: `requestHandler` is typed `HttpHandlerUserInput` (`S3Client.d.ts:144`) = `HttpHandler | NodeHttpHandlerOptions | FetchHttpHandlerOptions | Record<string, unknown>`, with the doc comment "provide the constructor arguments as an object".
>
> Verified at runtime on this branch: the resolved handler is a `NodeHttpHandler` and `httpHandlerConfigs().connectionTimeout` is `5000`. The timeout is applied.
>
> Fair point that nothing was pinning this, though — a future SDK release could narrow the accepted shapes and the timeout would go missing silently. I've added a regression test in `s3Client.test.ts` that resolves the handler and asserts `connectionTimeout === S3_CONNECTION_TIMEOUT_MS`. Leaving the production code as is.

### Finding 2 — `containerRouter.ts:300-302` (High) — accepted

> Good catch, fixed.
>
> `!response.IsTruncated || !response.NextKeyMarker` merged two different outcomes. `IsTruncated: true` with no `NextKeyMarker` *must* break (resuming from the same marker would loop forever), but it isn't a completed scan — and it was leaving `isPartialScan` at `false`, so `hasOnlyDeleteMarkers` at `:317` got asserted from a single page.
>
> That propagates: `EmptyBucketModal` reads `hasOnlyDeleteMarkers` as `isBucketEmptyWithVersions` and then forces `shouldDeleteVersions` with no checkbox. `isEmpty` is honest (it has its own exact `ListObjectsV2 MaxKeys:1` probe), so the current-object count really is zero — but a key with a delete marker can still hold real, restorable versions on a page that was never fetched, and those would have been wiped as "just leftover markers".
>
> Split into two branches; the marker-less case now sets `isPartialScan = true` before breaking. The page-ceiling check follows unchanged, and the early exit at `:296` is untouched (both flags are final there). New test covers `IsTruncated: true` / `NextKeyMarker: undefined` — the existing "scan was cut short" case used a truncated page *with* a marker and never reached this path.

### Finding 3 — `objectRouter.ts:1000-1003` (High) — accepted, lower severity

> Accepted, fixed — though I'd rate it Low rather than High, for a reason worth recording.
>
> The inconsistency is real: two branches above (`:859-862`, `:876-879`) set `isPartial = true` on abort, and this exit didn't check the signal. `bulkDeleteItems` breaks out silently on abort (`:159`, `:190-192` — "stop processing without recording errors"), so on the last page an aborted run returned `{ isPartial: false, errorCount: 0 }` with versions left undeleted.
>
> What keeps the impact at zero in practice: `ctx.req.signal` is wired strictly to the HTTP connection dropping (`server/context.ts:131-152` — `res.raw "close"` when `!writableEnded`, `req.raw "close"` when `!complete`, `req.raw "error"` on `ECONNRESET`/`ECONNABORTED`). An abort therefore means the client is already gone and nobody reads the response. So this is a broken internal invariant, not a user-visible bug.
>
> Fixed anyway — `if (response.IsTruncated || ctx.req.signal?.aborted) isPartial = true`. A false positive is harmless: `isPartial` means "not vouching for completeness". New test covers an abort landing during the last page's `DeleteObjects`, and the existing mid-scan abort test now asserts `isPartial` too.

### Finding 4 — `DeleteVersionsModal.tsx:88-95` (Medium) — accepted, different remedy

> The premise is right and I've fixed it, but not with an in-modal `<Message>`.
>
> Confirmed: both the `isPartial` branch (`:88-95`) and the `errorCount > 0` branch (`:76-84`) call `onError`, which `BucketModals.tsx:216-220` turns into `toast.error` with no options; `App.tsx:99` renders `<NotificationManager position="top-right" />` with no `duration`, so Juno 9.4.0's sonner default of 4000 ms applies. Two sentences of actionable copy for four seconds — not enough.
>
> A persistent `<Message>` inside the modal doesn't fit here: this modal closes unconditionally in `onSettled` (`:33-36`), so an in-modal result panel needs a second "form → result" phase, and every one of the seven modals in `BucketModals.tsx` follows the same convention (close, then report by toast). Introducing an exception for one of them costs more consistency than it buys.
>
> What I did instead:
> - New `getVersionsPartiallyDeletedToast` helper with `duration: Infinity`, dispatched via `toast.warning`. The toast stays until dismissed. Same pattern already in the repo at `Objects/stores/objectDownloadStore.ts:49-50`.
> - New `onPartial` prop on the modal so the partial path stops borrowing `onError`.
> - **And a labelling bug that the timer was hiding**: both branches were titled "Failed to Delete Versions" over a description reading "Deleted 12 version(s), but…" — the title contradicting its own body. A run that deleted 12 of 13 versions is a partial result, not a failure. `errorCount > 0` now routes to the partial toast when anything was deleted, and stays an error only when `deletedCount === 0` (or the mutation itself rejects).
>
> I checked the sibling modals for the same mislabel: `EmptyBucketModal` and `EmptyBucketsModal` have no `errorCount` branch at all, and `DeleteObjectsModal` already handles partials correctly by keeping itself open with an in-place result panel. The defect was unique to this modal, and this PR introduced it.

### Finding 5 — `versioningRouter.ts:470-473` (Medium) — accepted

> Same bug as #2, fixed the same way.
>
> `stoppedAtKey = undefined` is the sentinel `isFolderCovered` (`helpers/versionScan.ts:31-33`) reads as "the scan covered everything", so a marker-less truncated page was reporting `isPartialScan: false` for *every* folder. Concretely: a folder's own marker sorts before its contents (`"foo/" < "foo/x"`), so it can land on a page whose successors never arrive — the accumulator entry exists, `folderMarkerVersionId` is set, and nested delete markers on the unread page produce `hasDeletedContent: false` under `isPartialScan: false`. Confidently wrong rather than merely unknown.
>
> The page-ceiling branch right below (`:475-478`) already did the right thing, which made the gap easy to miss.
>
> Fix: split the condition; the marker-less case sets `stoppedAtKey = keyMarker ?? ""` — the same sentinel the two abort branches use (`:406`, `:424`). `isFolderCovered(prefix, "")` is `false` for any non-empty prefix, and with a non-empty `keyMarker` the folders closed out by earlier pages stay honestly covered. No change needed in `versionScan.ts`. New test added; all eight existing truncated fixtures carried a `NextKeyMarker`, so none of them reached this path.
>
> Worth noting for scope: `ObjectBrowserView.tsx:354-355` filters the "Deleted" tab on `hasDeletedContent` alone and never reads `isPartialScan` (only the "All" branch at `:346` treats it neutrally), so this fix restores the contract rather than changing that view's rendering today. Whether the Deleted tab should surface partially-scanned folders is a product question I'd rather not settle inside this PR.

### Finding 6 — `EmptyBucketModal.tsx:163, 213, 243` (Low) — accepted

> Correct, and it's on this PR — `git diff main...HEAD` shows these three strings were rewritten here (three different wordings collapsed into one) with "Please" carried forward.
>
> Changed all three to `"Unable to verify bucket versioning status and contents. Try again."` and re-ran `pnpm check-i18n`. The German `msgstr` for the old msgid was empty, so no translation is lost.
>
> The rule is `.github/copilot-instructions.md:559` ("Voice: active and impersonal. No 'We', 'Us', 'Please', 'Thanks'"), repeated in the checklist at `:57` and the Reject list at `:566`.
>
> Scoping note: "Please" appears ~70 more times in the client, mostly in `utils/useErrorTranslation.ts` and `components/Errors/RouteError.tsx`. That's all pre-existing and untouched by this diff, so I'm leaving it out of this PR and will do it as a standalone copy cleanup.

---

## Files this plan touches

**Server (production)**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/versioningRouter.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts`

**Server (tests)**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/containerRouter.test.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/versioningRouter.test.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.test.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/clients/s3Client.test.ts`

**Client** (all under `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/`)
- `BucketToastNotifications.tsx`, `BucketToastNotifications.test.tsx`
- `DeleteVersionsModal.tsx`, `DeleteVersionsModal.test.tsx`
- `BucketModals.tsx`
- `EmptyBucketModal.tsx`

**i18n (regenerated, not hand-edited)**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/locales/en/messages.po`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/locales/de/messages.po`

**Release / docs**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.changeset/ceph-bounded-version-scans-and-delete-versions.md` (amend, no new file)
- `/Users/kirylmishchuk/projects/SAP/DOCS/descriptions/pr-1331-description.md`

**Read-only references consulted**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/versionScan.ts` (confirmed: no change needed)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/context.ts:131-152` (abort-signal semantics)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.tsx:340-370`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/stores/objectDownloadStore.ts:44-56`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.github/copilot-instructions.md:57, :559, :566`

Nothing was implemented, committed, pushed or posted.
