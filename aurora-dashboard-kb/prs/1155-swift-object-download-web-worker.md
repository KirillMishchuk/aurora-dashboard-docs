# PR #1155: feat(portal): offload Swift object downloads to a Web Worker

**Автор:** mark-karnaukh-extern-sap · **Статус:** создан 09.08.2026 → смержен 13.08.2026
**Ветки:** `mark-swift-download-improvements` → `main` · **Файлов:** 15 (+1271/-548)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1155

> **Повторная проверка 13.08.2026:** голова PR на GitHub не сдвинулась — тот же коммит `97430ad`, что был проанализирован 11.08.2026, новых коммитов нет. Изменилось только обсуждение: CodeRabbit оставил автоматическое ревью, запрошено (но не выполнено) ревью Copilot, живых approve пока нет; GitHub также показывает предупреждения "Out of Scope Changes" (это про уже учтённую ниже находку про changeset) и "Docstring Coverage 75% < 80%". Пункты CodeRabbit сверены с кодом на `97430ad`: один подтверждён независимо и добавлен в «Ревью» первым пунктом; один (`rel="noopener,noreferrer"` через запятую) оказался pre-existing кодом, унаследованным от Ceph, и отклонён; остальные — стилистические nitpick'и ниже порога (см. конец раздела «Ревью»).

## Что сделано

Переносит архитектуру скачивания объектов из Web Worker'а, ранее реализованную только для Ceph (PR #1062), на Swift-объекты. Заявленный багфикс: `swift.downloadObject` никогда не проверял отмену запроса, поэтому отменённая на клиенте загрузка продолжала читать поток до конца и накапливать байты в памяти воркера — на большом файле это забивало память рендерера ("STATUS_BREAKPOINT"-краш, упомянутый в описании PR). Решение — то же, что уже работает у Ceph: декодирование base64→Blob уходит в отдельный Web Worker (не блокирует основной поток), состояние активных загрузок живёт в модульном хранилище вне React (переживает размонтирование таблицы при навигации по папкам), а на сервере `downloadObject` теперь проверяет `ctx.req.signal.aborted` в цикле чтения и не эмитит `:complete` для прерванной загрузки.

По ходу реализации PR сам себя поправил: коммит `7ece064` ("keep Swift and Ceph download worker/store in parity") добавил в уже существующий Ceph-воркер два guard'а на `abortController.signal.aborted`, которых там не было — то есть Swift-версия изначально написана строже, чем Ceph-оригинал, и это несоответствие устранено обратным пуском в Ceph.

## Как это реализовано

### Web Worker + module-scope store (новое для Swift)

`.../Swift/Objects/workers/objectDownload.worker.ts` (129 строк, `?worker&inline`) — почти точная копия Ceph-воркера, декодирует base64-чанки в `Uint8Array` вне основного потока и собирает `Blob` в конце:

```ts
// objectDownload.worker.ts:21-25
// Cancellation: a "cancel" message aborts the AbortController passed to the tRPC
// mutation, which aborts the underlying fetch. The BFF sees the client disconnect
// and stops reading the Swift stream on its next chunk (see swiftRouter's
// downloadObject). The store drops the transfer from its state right away, so the
// UI doesn't wait on this unwinding.
```

`.../Swift/Objects/stores/objectDownloadStore.ts` (246 строк) держит `Map<transferKey, ActiveTransfer>` вне React через `useSyncExternalStore(subscribeTransfers, getTransfersSnapshot)` — причина в комментарии к файлу:

```ts
// objectDownloadStore.ts:3-9
// Why this lives outside React: ObjectBrowserView swaps ObjectsTableView out for
// a <Spinner> whenever objects.list is loading (i.e. entering an uncached
// folder). That unmounts the table — and if the table owned the workers, its
// cleanup would abort them mid-stream ("stream closed prematurely") and lose the
// progress state. Owning transfers here means a download survives folder
// navigation, spinner swaps, and even leaving the container entirely...
```

Ключ транзакции — `container:objectKey` (`objectDownloadStore.ts:74`), отдельный toast-id `"swift-object-download"` (`objectDownloadStore.ts:38`, специально отличается от Ceph-стора, чтобы постоянные toast'ы двух бэкендов не гасили друг друга).

Отмена — `cancelObjectDownload()` (`objectDownloadStore.ts:233-245`) удаляет запись из `Map` немедленно (UI очищается без ожидания воркера) и ставит защитный таймер:

```ts
// objectDownloadStore.ts:65-72
// How long a cancelled worker gets to report back before it is forced down.
//
// Normally it replies almost immediately — the abort rejects its `for await`,
// and the reply path terminates it. But that reply isn't guaranteed: if the
// abort ever fails to unwind the stream, the worker would keep downloading and
// buffering a file nobody wants, with no entry left in `transfers` to clean it
// up. This bounds that window.
const CANCEL_TERMINATE_GRACE_MS = 5000
```
```ts
// objectDownloadStore.ts:238-244
transfer.worker.postMessage({ type: "cancel" } satisfies DownloadWorkerRequest)
setTimeout(() => transfer.worker.terminate(), CANCEL_TERMINATE_GRACE_MS)
transfers.delete(key)
emit()
```

### ObjectsTableView.tsx — переход на per-row прогресс

Раньше был один общий флаг "что-то скачивается"; теперь `ObjectsTableView.tsx:140` подписывается на весь `Map` через `useSyncExternalStore`, и на каждую строку считается собственный `isStreaming` (`ObjectsTableView.tsx:307`), который управляет и disabled-состоянием action-кнопок построчно, и показом нового подкомпонента:

```tsx
// ObjectsTableView.tsx:51-56
function RowTransferProgress({ downloadId, isPreviewing }: { downloadId: string; isPreviewing: boolean }) {
  const { data: progress } = trpcReact.storage.swift.watchDownloadProgress.useSubscription(
    { downloadId },
    { enabled: !!downloadId }
  )
  const percent = progress?.percent
```

Список превьюируемых MIME-типов расширен — раньше был свой узкий список, теперь делегирует общей `isPreviewableContentType` (та же, что у Ceph: `image/*`/`video/*`/`audio/*` + `application/pdf`/`text/plain`) — поведенческое изменение в сторону паритета с Ceph, не regressions, но стоит знать, что набор превьюируемых типов у Swift расширился этим PR.

### ObjectToastNotifications.tsx — деривация имени файла переехала внутрь

`getObjectDownloadErrorToast`/`getObjectDownloadCancelledToast` раньше принимали уже готовое отображаемое имя, теперь принимают полный `objectKey` и сами режут basename:

```ts
// ObjectToastNotifications.tsx:88-92
export const getObjectDownloadErrorToast = (
  objectKey: string,
  errorMessage: string
): { message: ReactNode } & NotificationOptions => {
  const displayName = objectKey.split("/").filter(Boolean).pop() ?? objectKey
```

Проверено: единственный внешний вызывающий (`index.tsx:222-224`, не тронут этим PR) уже передаёт полный `objectKey` под именем параметра `objectName` — поведение на выходе не меняется, просто деривация имени переехала из вызывающего кода в саму функцию-тост.

### swiftRouter.ts — server-side abort-awareness

`downloadObject` (`swiftRouter.ts:1642-1741`) теперь проверяет сигнал на каждой итерации цикла чтения и не эмитит `:complete` для прерванного потока:

```ts
// swiftRouter.ts:1687-1695
// The download worker aborts its tRPC fetch on cancel, which surfaces
// here as ctx.req.signal. Check before each read so a cancelled transfer
// stops pulling from Swift promptly, instead of streaming the whole
// object into a worker the client has already discarded...
if (ctx.req?.signal?.aborted) {
  aborted = true
  break
}
```
```ts
// swiftRouter.ts:1721-1726
// Only signal completion for a stream that actually ran to the end — an
// aborted transfer stopped at a partial byte count, and emitting
// `complete` would make watchDownloadProgress report it as finished.
if (!aborted) {
  downloadProgressEmitter.emit(`progress:${scopedDownloadId}:complete`)
}
```

### Побочный фикс: Ceph-воркер получил такие же abort-guard'ы

Коммит `7ece064` меняет `.../Ceph/Objects/workers/objectDownload.worker.ts` — существующий файл из другого, уже смерженного PR (#1062), — добавляя ровно то, с чем Swift-воркер написан с самого начала:

```diff
 for await (const { chunk, contentType: ct, filename: fn } of iterable) {
+      if (abortController.signal.aborted) break
       if (ct) contentType = ct
```
```diff
+    if (abortController.signal.aborted) {
+      chunks.length = 0
+      self.postMessage({ ok: false, cancelled: true, message: "cancelled" } satisfies DownloadWorkerResponse)
+      return
+    }
+
     const blob = new Blob(chunks, { type: contentType })
```

Это реальный, пользователь-видимый фикс для Ceph (без него отменённая на грани готовности Ceph-загрузка могла всё равно собрать и сохранить Blob из частично буферизованных чанков) — но он не про Swift и не упомянут в changeset (см. «Ревью»).

## Что затронуло

Всё изменение — внутреннее для Swift/Objects (и, точечно, для одного файла в Ceph/Objects). Блast-radius проверен по каждому изменённому публичному имени:

- `cancelObjectDownload`/`subscribeTransfers`/`getTransfersSnapshot`/`startObjectDownload` из `objectDownloadStore.ts` — потребляются только внутри `Swift/Objects/ObjectsTableView.tsx` и тестов того же каталога. Аналогичные Ceph-экспорты (не тронутые этим PR) используются только внутри `Ceph/Objects`. Кросс-бэкендных потребителей нет.
- `storage.swift.downloadObject` — единственный клиентский вызывающий (`Swift/Objects` через воркер) и тесты `swiftRouter.test.ts`; отдельно зарегистрирован в `trpcClient.ts:125` как одна из двух `STREAMING_PROCEDURES` (наравне с `storage.ceph.objects.downloadObject`) — эта регистрация не менялась, процедура и до PR была потоковой.
- `getObjectDownloadErrorToast`/`getObjectDownloadCancelledToast` (изменённая сигнатура) — единственный вызывающий (`index.tsx:222-224`) не тронут PR, но передаёт совместимое значение (полный `objectKey`), так что вызов остаётся корректным без изменений на его стороне.
- Изменение в `Ceph/Objects/workers/objectDownload.worker.ts` — файл используется только `Ceph/Objects/stores/objectDownloadStore.ts`, экспортов у воркера нет (это `self.addEventListener` модуль), поэтому единственный эффект — поведенческий (описан выше), не затрагивает контракт.

Ни один из изменённых экспортов не выходит за пределы `packages/aurora` — нет изменений публичного API пакета, потребителей в `apps/dashboard` не найдено.

## Ревью

**Одна находка набрала ≥80 confidence.** Ниже она первая, затем — две находки, упёршиеся в порог (75/75), и отклонённые, для полноты картины.

- **[80/100] Чекбокс выбора объекта дизейблится на время его скачивания/предпросмотра — уже выбранный объект нельзя снять с выделения перед bulk-действием.** Этим PR в чекбокс строки добавлен `disabled={isStreaming}` (`ObjectsTableView.tsx:353`, рядом `checked={isSelected}` на `ObjectsTableView.tsx:352`) — раньше у этого чекбокса атрибута `disabled` не было вовсе. `selectedObjects` живёт в родителе (`Swift/Objects/index.tsx:170`) и передаётся в `DeleteObjectsModal` целиком, без фильтрации по `isStreaming` (`objectKeys={selectedObjects}`, `index.tsx:533`). Сценарий: пользователь отмечает объект чекбоксом для массового удаления, затем (до удаления) кликает по нему «Preview»/«Download» — строка переходит в `isStreaming`, чекбокс дизейблится, снять объект с выделения до конца передачи невозможно; массовое удаление, запущенное в этот момент, включит и скачиваемый объект. Симметрично: если скачивание уже идёт, а объект случайно попал в выделение (например, через «выбрать всё»), убрать его из выделения тоже нельзя, пока передача не закончится. Независимое подтверждение: тот же паттерн отметил CodeRabbit на самом PR ("disabled checkboxes prevent deselection during transfers, risking bulk actions on downloading objects") — сверено по коду, а не принято на слово.
- **[75/100] Незакрытое окно отмены до первого байта: `swift.get(url)` не получает `signal`.** В `swiftRouter.ts:1665` вызов `const response = await swift.get(url).catch(...)` не передаёт `{ signal: ctx.req.signal }`, хотя тот же файл делает это для `uploadObject` (`swiftRouter.ts:1471`: `signal: ctx.req.signal`), а Ceph-аналог передаёт `abortSignal: ctx.req.signal` в `GetObjectCommand` (`objectRouter.ts:1059-1071`) с прямым комментарием про клик на "Cancel". Добавленная этим PR проверка `ctx.req?.signal?.aborted` (`swiftRouter.ts:1687`) отрабатывает только между чтениями уже открытого потока — если клиент отменяет загрузку до того, как Swift-бэкенд ответит первым байтом (медленный backend, файл под нагрузкой), исходящий GET-запрос продолжит выполняться до завершения. Это прямо противоречит заявленной в PR цели — устранить именно эту категорию "аборт не долетает до Swift". Не дотянуло до 100 в независимой оценке из-за отсутствия прямого воспроизведения (проверка по коду, не по логам/трейсу реального race).
- **[75/100] Changeset не упоминает Ceph-side правку.** `.changeset/tough-things-mix.md` описывает только Swift-часть; правка в `Ceph/Objects/workers/objectDownload.worker.ts` (коммит `7ece064`, реальный пользователь-видимый фикс поведения при отмене — см. «Как это реализовано») в changeset не отражена. CodeRabbit на самом PR отметил эту правку как "out of scope" для PR, озаглавленного вокруг Swift.
- **[50/100, отклонено как nitpick] Abort-guard в Ceph-воркере (`7ece064`) не покрыт тестами.** Новые тесты (`swiftRouter.test.ts`, `objectDownloadStore.test.ts` +385 строк, `ObjectsTableView.test.tsx`, `ObjectToastNotifications.test.tsx`) мокают сам воркер (`vi.mock(".../objectDownload.worker?worker&inline", ...)`) и не проверяют его код напрямую — `objectDownload.worker.test.ts` не существует ни для Ceph, ни для Swift во всём репозитории. Commit-сообщение `test(portal): cover Swift object-download worker, store, and router abort` заявляет покрытие воркера, которого по факту нет. Отклонено по правилу skill'а — это claim про test coverage, не явное требование CLAUDE.md.
- **[0/100, отклонено] Нет watchdog на "тихо зависший" воркер вне явной отмены.** `CANCEL_TERMINATE_GRACE_MS` защищает только явную отмену пользователем; воркер, который перестал отвечать без явного cancel (зависшее чтение, краш без сообщения об ошибке), может остаться в `Map` бессрочно. Отклонено — паттерн идентично унаследован из Ceph-стора (этот PR явно приводит Swift к паритету с Ceph), то есть это pre-existing поведение, не новая проблема, введённая этим PR.
- **[0/100, отклонено] `rel="noopener,noreferrer"` через запятую вместо пробела в `openBlobInNewTab` (`objectDownloadStore.ts:97`).** CodeRabbit отметил это как проблему безопасности: браузер разбирает `rel` на пробел-разделённые токены, так что значение через запятую не распознаётся ни как `noopener`, ни как `noreferrer` — анкор с `target="_blank"` теряет защиту от `window.opener`. В коде PR это действительно так, но идентичная строка с той же запятой уже есть в Ceph-сторе (`Ceph/Objects/stores/objectDownloadStore.ts:101`) со времён смерженного #1062 — этот PR лишь скопировал существующий паттерн для паритета с Ceph, не ввёл его. Отклонено по правилу skill'а (pre-existing issue), хотя сама уязвимость реальна и стоит отдельного фикса сразу в обоих сторах.

Прочие nitpick-замечания CodeRabbit на этом PR (вынести повторяющуюся деривацию basename в общий хелпер, `key={activeTransfer.downloadId}` на `RowTransferProgress`, `role="progressbar"`/ARIA-атрибуты на прогресс-баре, расширить тест на error-путь воркера, переиспользовать реальный `isPreviewableContentType` в моках вместо дублирования allow-list) — стилистические, самостоятельной проверкой порог 80 не подтверждён, в отдельные пункты не выносим.

---
Проанализировано: 11.08.2026, повторно проверено 13.08.2026 (новых коммитов нет) · коммит `97430ad`
