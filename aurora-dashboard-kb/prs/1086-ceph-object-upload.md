# PR #1086: feat(portal): add object upload for Ceph (S3) buckets

**Автор:** mark-karnaukh-extern-sap · **Статус:** смержен 24.07.2026 (`1e9ba790`)
**Ветки:** `mark-ceph-object-upload-setup` → `main` · **Файлов:** 12 (+1691/-10)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1086

Закрывает #1087.

## Что сделано

До этого PR в Ceph (S3) бакетах можно было браузить, скачивать и управлять объектами, но не загружать новые — пользователям приходилось идти во внешние S3-тулы. PR добавляет upload с паритетом уже существующего Swift-аплоада: кнопка в тулбаре объект-браузера, модалка с drag-and-drop/file-picker, live-прогресс, отмена, тосты успеха/отмены/ошибки.

Реализация буквально **порт** существующего Swift-аплоада на S3: серверная и клиентская части почти построчно копируют структуру `swiftRouter.uploadObject`/`watchUploadProgress` и клиентский `Swift/Objects/UploadObjectModal.tsx`, с заменой Swift-специфики (`x-upload-account` заголовок, которого у Ceph нет — это явно проверено отдельным тестом) на S3 (`PutObjectCommand`). Ключевая архитектурная деталь, вынесшая логику в отдельную процедуру: `octetInputParser` (для приёма файла как raw-потока) нельзя присоединить к `cephProtectedProcedure`, потому что та построена на `projectScopedProcedure`, которая уже несёт объектный `project_id` инпут — а tRPC отказывается сливать объектный инпут с raw-stream инпутом ("All input parsers did not resolve to an object"). Поэтому метаданные (project id, бакет, ключ объекта, тип, размер, id для прогресса) едут заголовками `x-upload-*`, а не tRPC-инпутом — тот же приём, что уже использует Swift-аплоад.

## Как это реализовано

Новая `cephUploadProcedure` (`packages/aurora/src/server/Storage/cephProcedure.ts:135-178`) строится на базовой `protectedProcedure` (не `cephProtectedProcedure`) и вручную рескоупит OpenStack-сессию из заголовка `x-upload-project-id`:

```ts
// cephProcedure.ts:135-144
export const cephUploadProcedure = protectedProcedure.use(async function resolveCephForUpload(opts) {
  const { ctx, next } = opts
  const uploadProjectId = (ctx.req.headers["x-upload-project-id"] as string | undefined)?.trim()
  if (!uploadProjectId) {
    throw new TRPCError({ code: "BAD_REQUEST", message: "x-upload-project-id header is required for uploads" })
  }
```

Далее рескоупленная сессия (`scopedCtx`, не исходный `ctx`) идёт и в резолв EC2-credentials, и в возвращаемый контекст (`cephProcedure.ts:165-177`) — в самой ветке PR это изначально было упущено (spread шёл от `ctx`, а не `scopedCtx`), баг поймал Copilot-ревьюер на самом PR и это было исправлено отдельным коммитом `38bcf24` ("scope upload session to the rescoped project") ещё до текущего head — на актуальном коде всё верно.

`uploadObject` (`objectRouter.ts:1092-1216`) читает метаданные из заголовков, валидирует их как непустые строки после `trim()` (то же самое, не более строгое, что и Zod-схемы `containerName`/`objectKey` для остальных Ceph-процедур в `types/ceph.ts` — не ослабление, а совпадение с конвенцией), затем гоняет файл через `Transform`-поток, который считает байты и эмитит прогресс, прежде чем передать `PutObjectCommand`:

```ts
// objectRouter.ts:1099-1117
const projectId = (headers["x-upload-project-id"] as string | undefined)?.trim()
const bucket = (headers["x-upload-container"] as string | undefined)?.trim()
const objectKey = (headers["x-upload-object"] as string | undefined)?.trim()
...
if (!projectId) { throw new TRPCError({ code: "BAD_REQUEST", message: "x-upload-project-id header is required" }) }
if (!bucket) { throw new TRPCError({ code: "BAD_REQUEST", message: "x-upload-container header is required" }) }
if (!objectKey) { throw new TRPCError({ code: "BAD_REQUEST", message: "x-upload-object header is required" }) }
```

`watchUploadProgress` (`objectRouter.ts:1227-...`) — async-generator subscription, отдаёт снапшот текущего прогресса сразу при подписке, затем слушает `EventEmitter` до completion/error или до 30-секундного bounded wait (на случай, если аплоад уже завершился до того, как клиент успел подписаться).

Клиент — `UploadObjectModal.tsx` (новый файл, 309 строк) — почти дословная копия `Swift/Objects/UploadObjectModal.tsx` с заменой `container`/`account` на `bucketName` (без account — у Ceph нет этого понятия), и вызовом `trpcClient.storage.ceph.objects.uploadObject.mutate` вместо `storage.swift.uploadObject`. Подключается в `ObjectBrowserView.tsx:612-631` новой кнопкой тулбара «Upload Object».

## Что затронуло

`uploadObject`/`watchUploadProgress` корректно вписаны в экспортируемый `objectRouter` (`routers/ceph/index.ts` → `routers/index.ts`) — новые процедуры реально доступны через `AuroraRouter`, ничего не забыто. `cephUploadProcedure` используется только этим router — внешних потребителей нет. `UploadObjectModal` (Ceph) — самостоятельный компонент, не переиспользуется нигде за пределами `ObjectBrowserView.tsx`; одноимённый Swift-компонент (`Swift/Objects/UploadObjectModal.tsx`) — отдельный, не конфликтует (разные директории, разный tRPC-путь).

Инвалидация списка после аплоада (`utils.storage.ceph.objects.list.invalidate()`, без аргументов — то есть широко, все варианты списка, не только текущий бакет) — не решение этого PR: ровно тот же паттерн используют все существующие Ceph-модалки объектов (`CreateFolderModal`, `DeleteObjectModal`, `MoveObjectModal`, `EditMetadataModal` и т.д.) — консистентно, не регрессия.

Права доступа: в этом домене (Storage/Ceph+Swift) ни одна процедура-мутация объектов не делает серверный `canUser`-чек внутри себя — `canUser` (`routers/permissionRouter.ts`) существует только как отдельный query для UI-гейтинга кнопок; реальная авторизация полностью делегирована Keystone-scoped S3/Swift credentials на уровне Ceph RGW. `uploadObject` в этом смысле ничем не отличается от `deleteObject`/`moveObject`/etc. — не новый пробел, существующая архитектура домена.

## Ревью

Через диф и историю прогнаны параллельно bug-scan, comment-compliance, historical-context (сравнение построчно со Swift-оригиналом, который этот PR явно заявляет как копируемый) и prior-feedback (issue/PR-комментарии). На самом PR уже были найдены и закрыты в рамках этой же ветки: баг с нерескоупленным `ctx` (Copilot, фикс `38bcf24`), слишком узкая инвалидация списка (Copilot, фикс `2171b5e3`), утечка таймера в тесте (Copilot, фикс `b3bad147`), `setTimeout`→`setImmediate` (CodeRabbit, фикс `4ed90c3`), и позиция кнопки (человек-ревьюер, фикс `4e80607d`, дальше approve). Дальше — то, что этот цикл не поймал.

**Найдено 2 проблемы с уверенностью ≥80:**

1. **Отсутствует обработчик `error` на `progressTracker` — необработанное исключение валит весь процесс BFF, а не только текущий запрос.**
   `packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:1167-1172`. Слушатель ошибок повешен только на `fileStream`:
   ```ts
   fileStream.on("error", (err) => {
     if (isAbortLike(err)) return
     progressTracker.destroy(err as Error)
   })
   const trackedStream = fileStream.pipe(progressTracker)
   ```
   `progressTracker.destroy(err)` эмиттит `'error'` на самом `progressTracker` — а на нём слушателя нет. `trackedStream` (`=== progressTracker`) передаётся напрямую в `PutObjectCommand({ Body: trackedStream })`; `@smithy/node-http-handler`'s `write-request-body.js` только делает `body.pipe(httpRequest)`, слушателя ошибок туда не добавляет. `.pipe()` в Node НЕ защищает источник от собственного необработанного `'error'`. Комментарий в коде утверждает: "Non-abort errors are re-emitted so they surface through PutObject and the catch block" — неверно: при *не*-abort ошибке на `fileStream` (например `EPIPE`/`ETIMEDOUT`/обрыв соединения на большом файле — вполне реалистично для гигабайтных аплоадов) необработанное исключение крашит весь Node-процесс, а не всплывает через `catch`. В `packages/aurora/src/server` нет глобального `uncaughtException`-хендлера — значит, это реальный краш процесса, обрывающий текущие запросы всех пользователей, а не просто неудачный аплоад. Live-репродукция этой ровно этой цепочки (fileStream→Transform→pipe, ошибка без abort-кода) подтверждает падение.
   Именно этот слушатель присутствует в Swift-оригинале, который PR заявляет как копируемый (`packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts:1426-1429`):
   ```ts
   progressTracker.on("error", (err) => {
     if (isAbortLike(err)) return
     trackedStream.destroy(err as Error)
   })
   ```
   В Ceph-порте этот блок просто не перенесён.

2. **`watchUploadProgress` не реагирует на `ctx.req.signal` (обрыв соединения клиента) — подписка висит до 30 секунд вместо немедленного завершения, в отличие от Swift.**
   `packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:1227-1309`. У Swift-аплоада ровно эта проблема была реальным багом, исправленным отдельным коммитом `665957d` ("cancellable file upload with AbortSignal propagation to Swift", #776) — до фикса генератор так же зависал на 30-секундном таймауте при обрыве клиента; после фикса Swift-версия (`swiftRouter.ts:1557-1563,1597-1599`) регистрирует `ctx.req.signal.addEventListener("abort", onAbort)` и завершается немедленно. Ceph-порт этот кусок не унаследовал — `ctx.req` доступен в контексте (используется рядом же, в `uploadObject`), просто не подключён к `watchUploadProgress`. PR явно заявляет "same abort-signal wiring" как у Swift — по факту не так. (То же самое отсутствует и у соседнего, уже существующего `watchDownloadProgress` — то есть это не новый, специфичный для этого PR изъян, а системный пробел Ceph-модуля, который этот PR унаследовал вместо того, чтобы исправить по пути.)

**Рассмотрено, но не прошло порог ≥80** (для полноты, чтобы не искать заново):
- Безусловный `await setImmediate` на каждый чанк (`objectRouter.ts:1148-1151`) — реальные, но небольшие накладные расходы на планирование (~900мс на GB в изолированном бенчмарке), растущие с числом параллельных аплоадов; не катастрофично на фоне реального времени сетевой передачи гигабайтного файла.
- Гонка между `finally`-удалением записи из `uploadProgressMap` (`objectRouter.ts:1213-1215`) и снапшотом в `watchUploadProgress` для очень быстрых/маленьких аплоадов — реальна, но безвредна: `UploadObjectModal.tsx` завязан на резолв самого `mutate()`, а не на подписку; максимум — прогресс-бар не покажет процент для короткоживущего аплоада.
- `err.name === "AbortError"` в `UploadObjectModal.tsx:150-161` — мёртвый код (`TRPCClientError` всегда имеет `name === "TRPCClientError"`), но реальная детекция отмены сейчас работает через соседний фоллбэк по подстроке `"aborted"` в сообщении, которая эмпирически ловит настоящий abort. Не сломано сейчас, но хрупко (держится на тексте сообщения, а не на структуре ошибки).
- Валидация `x-upload-size`: `Number.isFinite(fileSize) && fileSize >= 0` пропускает дробные значения (`"1024.5"`), тогда как Swift использует `Number.isInteger`. Низкое влияние.

---
Проанализировано: 24.07.2026 · коммит `4e80607dacd`
