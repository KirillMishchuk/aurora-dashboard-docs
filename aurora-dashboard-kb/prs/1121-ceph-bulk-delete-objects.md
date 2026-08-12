# PR #1121: feat(aurora): add bulk delete for Ceph objects with performance and UX improvements

**Автор:** KirylSAP · **Статус:** смержен 07.08.2026
**Ветки:** `kiryl-ceph-bulk-objects-delete` → `main` · **Файлов:** 24 (+2937/-289)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1121

## Что сделано

До этого PR объекты в Ceph-бакетах можно было удалять только по одному — через `objects.delete` в строке таблицы. PR добавляет полноценный **bulk delete**: чекбоксы в таблице, «select all», панель действий при непустом выборе, и модалку с двухшаговым флоу (подтверждение → результаты с детализацией по каждому объекту). Работает как для текущих объектов (вкладка «All»), так и для конкретных версий в режиме восстановления (вкладка «Deleted») — включая полное перманентное удаление всех версий файла или папки.

Помимо основной фичи, PR попутно чинит два независимых бэкенд-бага в существующей пагинации `checkDeletedContent` (риск бесконечного цикла и пропуск данных на поздних страницах — см. ниже), устраняет ~140 строк дублирования между новыми `deleteBulk`/`deleteVersionsBulk` через общий хелпер, и приводит к единому стилю все три модалки удаления/восстановления объектов (текст предупреждения — под заголовком, а не в `helptext` поля; подтверждение — строчными `delete`, а не капсом `DELETE`).

## Как это реализовано

### Бэкенд: `bulkDeleteItems` — общая логика чанкинга и агрегации

Новая схема входа (`packages/aurora/src/server/Storage/types/ceph.ts:210-227`) явно запрещает передавать ключи папок (оканчивающиеся на `/`) — `DeleteObjects` удалил бы только нулевой маркер, оставив содержимое папки осиротевшим:

```ts
// types/ceph.ts:210-219
export const deleteObjectsBulkInputSchema = projectScopedInputSchema.extend({
  containerName: z.string().min(1),
  objectKeys: z
    .array(z.string().min(1).max(1024)) // 1024 = S3 max key length
    .min(1)
    .max(10000)
    .refine((keys) => keys.every((key) => !key.endsWith("/")), {
      message: 'Folder keys (ending with "/") cannot be bulk-deleted. Use objects.delete, which deletes recursively.',
    }),
})
```

Схема вывода (`deleteObjectsBulkOutputSchema`, `types/ceph.ts:263-268`) отражает ключевую особенность S3 API: `DeleteObjectsCommand` возвращает *смешанный* результат в единственном HTTP 200 — часть ключей в `Deleted[]`, часть в `Errors[]`, без единого флага успеха. Вся серверная логика построена вокруг этого факта.

Общий хелпер `bulkDeleteItems` (`objectRouter.ts:143-208`) переиспользуется обеими новыми процедурами — устраняет дублирование, которое PR явно называет в описании (~140 строк):

```ts
// objectRouter.ts:187-201
} catch (error) {
  // If aborted, stop processing without recording errors
  if (abortSignal?.aborted) {
    break
  }
  // Nothing deleted yet → the failure is systemic (bad bucket, denied
  // credentials). Surface it as a normal tRPC error rather than as 1000
  // identical per-key errors.
  if (deleted.length === 0 && errors.length === 0) {
    throw mapS3ErrorToTRPCError(error, { operation, bucket: containerName })
  }
  // Otherwise degrade: earlier chunks really were deleted, so keep the
  // partial result and report this chunk's items as failures.
  const message = error instanceof Error ? error.message : String(error)
  for (const item of chunk) {
    errors.push({ key: item.key, versionId: item.versionId, code: "RequestFailed", message })
  }
}
```

Логика различает два принципиально разных сценария отказа: если ничего ещё не удалено и ошибок ещё не было — это, скорее всего, системная проблема (несуществующий бакет, отказ в доступе), и она пробрасывается как обычная tRPC-ошибка. Если же часть чанков уже успешно прошла — предыдущий результат сохраняется, а упавший чанк деградирует в набор per-key ошибок вместо потери уже сделанной работы. `deleteBulk` (`objectRouter.ts:702-714`) и `deleteVersionsBulk` (`objectRouter.ts:736-746`) — тонкие обёртки над этим хелпером, каждая со своей де-дупликацией (по ключу для объектов, по паре ключ+versionId для версий) перед вызовом.

### Бэкенд: фикс бага пагинации в `checkDeletedContent`

Отдельно от bulk-delete, PR переписывает цикл пагинации в `versioningRouter.checkDeletedContent` (`versioningRouter.ts:397-457`). Раньше цикл был `while (!hasDeleteMarkers)` — то есть останавливался на **первом же** delete-маркере на любой странице, даже если папка была лишь частично просканирована и маркер самой папки (`folderMarkerVersionId`) на этой странице ещё не был найден. Теперь — `do...while(true)` с явными условиями выхода:

```ts
// versioningRouter.ts:445-457
// Early exit optimization: stop if we have all the information we need
if (hasDeletedNestedObjects && isFolderMarkerDeleted && folderMarkerVersionId) {
  break
}

// Continue to next page if truncated and has next marker
if (!response.IsTruncated || !response.NextKeyMarker) {
  break
}

keyMarker = response.NextKeyMarker
versionIdMarker = response.NextVersionIdMarker
} while (true) // eslint-disable-line no-constant-condition
```

Выход теперь корректно завершает цикл либо когда собраны все три нужных факта (есть удалённые вложенные объекты, папка-маркер удалена, известен её versionId), либо когда страницы закончились (`!response.IsTruncated`) — с дополнительной защитой от бесконечного цикла на случай, если S3 сообщит `IsTruncated: true`, но не пришлёт `NextKeyMarker`. Результат также расширен двумя новыми полями (`folderDeleteMarkerVersionId`, `folderMarkerVersionId`), которые нужны фронтенду для восстановления и перманентного удаления папок.

### Фронтенд: состояние выбора в `ObjectBrowserView`

`selectedItems: { key: string; versionId?: string }[]` — источник истины для выбора, живёт в `ObjectBrowserView`, а не в таблице. Очищается при смене вкладки, навигации по префиксу, смене бакета и после самого bulk-delete:

```ts
// ObjectBrowserView.tsx:522-535
const handleBulkDeleted = (deletedKeys: string[], errorCount: number) => {
  // The list accumulates pages; a plain invalidate would refetch only the last
  // page and append it. Drop the accumulator so the refetch rebuilds page 1.
  resetAccumulatedObjects()

  // In Deleted tab, clear all selection after bulk delete (list is being refetched anyway)
  // In All tab, only clear successfully deleted items
  if (tab === "deleted") {
    setSelectedItems([])
  } else {
    setSelectedItems((prev) => prev.filter((item) => !deletedKeys.includes(item.key)))
  }
  ...
```

Есть содержательная асимметрия между вкладками: во вкладке «All» после частичного отказа успешно удалённые ключи убираются из выбора, а неудалённые остаются выбранными (можно сразу повторить попытку); во вкладке «Deleted» выбор сбрасывается целиком независимо от результата, потому что список версий всё равно перезапрашивается заново.

Проверки O(1) вместо O(n)/O(m), которые PR заявляет как перформанс-фикс, реализованы через `useMemo`-мапы (`ObjectBrowserView.tsx:443,449`):

```ts
// ObjectBrowserView.tsx:443-451
const versionIdByKey = useMemo(() => {
  if (tab !== "deleted") return new Map<string, string>()
  return new Map(filteredDeletedFiles.map((v) => [v.key, v.versionId]))
}, [tab, filteredDeletedFiles])

const selectedItemsSet = useMemo(() => {
  return new Set(selectedItems.map((item) => makeItemKey(item.key, item.versionId)))
}, [selectedItems])
```

Разрешение на массовые действия пока захардкожено:

```ts
// ObjectBrowserView.tsx:96-98
// TODO(perms): wire to storage.canUser({ permission: "storage:objects:delete" })
// instead of hardcoding — mirrors the Swift objects list.
const hasAnyBulkAction = true
```

Комментарий сам называет это временным решением и явно ссылается на то, что так же (без серверной проверки прав) устроен и Swift-объектный список — то есть не новый пробел, а совпадение с существующей архитектурой домена (см. «Ревью» ниже).

### Фронтенд: `DeleteObjectsModal` — новый компонент, два шага

Новый файл (`DeleteObjectsModal.tsx`, 266 строк) реализует связку подтверждение → результаты в одном компоненте, переключаясь по `result !== null`:

```tsx
// DeleteObjectsModal.tsx:32-57 (handleConfirm)
const handleConfirm = () => {
  if (!projectId) return

  if (result === null) {
    // Step A: Confirm
    markSubmitted()
    if (isVersionMode) {
      deleteVersionsBulkMutation.mutate({ project_id: projectId, containerName: bucketName, versions })
    } else {
      deleteBulkMutation.mutate({ project_id: projectId, containerName: bucketName, objectKeys })
    }
  } else {
    // Step B: Close results view
    handleClose()
  }
}
```

При `errorCount === 0` модалка закрывается сама; при частичном отказе — переключается на экран результатов с усечённым списком ошибок (до 100 записей, `MAX_ERROR_VISIBLE`) и списком удаляемых объектов (до 20, `MAX_VISIBLE`), оба со счётчиком «и ещё N».

### Фронтенд: перманентное удаление всех версий/папки через `deleteVersionsBulk`

`DeleteVersionModal` (одиночное удаление версии из истории) и `RestoreVersionModal` (для папок, «восстановление» реализовано как удаление delete-маркера) были переведены с прежней процедуры `versioning.deleteVersion`/`versioning.restoreVersion`-путей на общий `objects.deleteVersionsBulk` — чтобы не дублировать логику удаления и единообразно обработать составной случай «удалить папку целиком» (delete-маркер + сам маркер-объект папки — два элемента одним вызовом):

```ts
// DeleteVersionModal.tsx:52-59
const deleteMutation = trpcReact.storage.ceph.objects.deleteVersionsBulk.useMutation({
  onSuccess: () => {
    utils.storage.ceph.versioning.listObjectVersions.invalidate()
    utils.storage.ceph.versioning.checkDeletedContent.invalidate()
    utils.storage.ceph.objects.list.invalidate()
    utils.storage.ceph.containers.list.invalidate()
    onSuccess?.(objectKey, versionId)
  },
  ...
```

### Тосты: единая фабрика вместо дублирования

`ObjectToastNotifications.tsx` получил `createBulkDeleteToasts(entityType)` (`ObjectToastNotifications.tsx:194-233`) — фабрику, параметризованную `"object" | "version"`, которая производит `success`/`partial`/`error` варианты с правильными формами множественного числа через Lingui `<Plural>`, вместо шести отдельных почти идентичных функций.

## Что затронуло

Обе новые процедуры (`deleteBulk`, `deleteVersionsBulk`), хелпер `bulkDeleteItems` и все новые Zod-схемы (`deleteObjectsBulkInputSchema`, `deleteVersionsBulkInputSchema`, `deleteObjectsBulkOutputSchema`, `deletedObjectSchema`, `deleteObjectErrorSchema`) используются только внутри файлов, изменённых самим PR — контрактных изменений наружу нет, чисто аддитивная фича на уровне `AuroraRouter`.

Однако есть заметный побочный эффект: **`versioning.deleteVersion`** (старая одиночная процедура удаления версии, `versioningRouter.ts:281`) осталась в роутере, но потеряла всех фронтенд-потребителей — `DeleteVersionModal` и `RestoreVersionModal` теперь используют `objects.deleteVersionsBulk` вместо неё. Единственные оставшиеся упоминания `.deleteVersion` — в собственном тесте `versioningRouter.test.ts:236,252`. Это не баг (процедура по-прежнему валидна и протестирована), но осиротевший эндпоинт — кандидат на удаление в отдельном PR, если он окончательно не нужен.

Имя `DeleteObjectsModal` уже занято — есть одноимённый, но не связанный компонент `Swift/Objects/DeleteObjectsModal.tsx` (другая директория, другой tRPC-путь, отдельная реализация bulk-delete для Swift). Конфликта нет (разные модули), но стоит иметь в виду при поиске по имени.

`checkDeletedContent` теперь также запрашивается на вкладке «All» (`enabled: !!projectId && versioningStatus?.status === "Enabled" && allFolders.length > 0`, было — только на вкладке «deleted»), чтобы скрывать удалённые папки из обычного списка — новый постоянный источник нагрузки на этот запрос, а не разовый для вкладки «Deleted».

## Ревью

Через диф, историю, комментарии и предыдущие ревью-фидбеки прогнаны параллельно CLAUDE.md-compliance, bug-scan, historical-context, prior-feedback и comment-compliance; кандидаты прошли отдельный confidence-scoring проход.

CLAUDE.md-compliance, comment-compliance и historical-context ничего не нашли: захардкоженный `hasAnyBulkAction = true` (см. выше) совпадает с существующим паттерном Swift-списка объектов, а не является новым пробелом; все проверенные комментарии в новом коде (`bulkDeleteItems`, схемы, `checkDeletedContent`, обработчики выбора в `ObjectBrowserView`) точно описывают то, что делает код; переписанный цикл пагинации в `checkDeletedContent` корректно устраняет баг из PR #1013 (см. «Что затронуло» — там же история его происхождения). Prior-feedback заметил один открытый, не относящийся к этому PR момент: `checkDeletedContent` по-прежнему не имеет жёсткого предела числа страниц пагинации — это отмечалось как Major ещё в ревью PR #992 и не устранено; PR #1121 не регрессирует это (сохраняет прежнее поведение), но и не чинит.

**Найдена 1 проблема с уверенностью ≥80** (изначально две смежные находки с одинаковой первопричиной прошли confidence-scoring раздельно — `RestoreVersionModal` получил 100, `DeleteVersionModal` с тем же кодовым паттерном — 75, ниже порога отчёта; ниже они объединены как один дефект, поскольку код идентичен и различается только тем, насколько легко он воспроизводится):

1. **Мутации на базе `deleteVersionsBulk` считают операцию успешной, даже если S3 не удалила ничего.** После перевода `RestoreVersionModal` и `DeleteVersionModal` с одиночных процедур на общий `objects.deleteVersionsBulk`, оба `onSuccess`-хендлера полагаются на сам факт резолва промиса и никогда не проверяют `res.errorCount`/`res.errors`. Хелпер `bulkDeleteItems` (`objectRouter.ts:143-209`) пробрасывает исключение только когда `catch` реально сработал (сетевая/системная ошибка) **и** ничего ещё не удалено; per-key отказ S3 (например, конфликт версионирования именно на этом ключе) возвращается внутри штатного HTTP 200 в `response.Errors` — исключения нет, промис резолвится нормально с `errorCount > 0`.

   Подтверждённый (уверенность 100) путь — `RestoreVersionModal.tsx:45-52,82-88`: восстановление папки удаляет её delete-маркер через `deleteVersionsBulk` с **ровно одним** элементом (`versions: [{ key: objectKey, versionId }]`). Раньше предполагалось, что для одного элемента `bulkDeleteItems` либо кидает исключение, либо гарантированно возвращает полный успех — это неверно: per-key отказ у единственного элемента тоже не бросает исключение. `handleRestoreSuccess` (`RestoreVersionModal.tsx:45-52`) вызывается безусловно и сообщает «папка восстановлена», хотя delete-маркер физически не удалён — путь гарантированно достижим при любом per-key отказе S3 на этом ключе.

   Тот же код-паттерн (уверенность 75, ниже порога как самостоятельная находка, но root cause идентичен) — `DeleteVersionModal.tsx:52-59`: при перманентном удалении всех версий файла (`allVersionIds`) или удалении папки (delete-маркер + folder-маркер, два элемента) `onSuccess` так же не смотрит на `errorCount`, но здесь для срабатывания нужен по-настоящему смешанный ответ S3 на несколько элементов в одном запросе — менее гарантированный, но реально достижимый сценарий.

---
Проанализировано: 03.08.2026 · коммит `3775ab00`
