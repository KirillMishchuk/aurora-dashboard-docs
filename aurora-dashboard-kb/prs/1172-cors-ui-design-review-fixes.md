# PR #1172: fix(aurora): apply design review fixes to bucket CORS rules UI

**Автор:** KirylSAP · **Статус:** смержен 14.08.2026 (коммит `0bfd055`; открыт 12.08.2026)
**Ветки:** `kiryl-ceph-cors-review-findings` → `main` · **Файлов:** 32 (+145/-390, из них 4 locale-файла: +26/-100)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1172

## Что сделано

PR — третий раунд полировки CORS UI для Ceph/S3-бакетов, выросшего из #1092 (добавление таба «CORS Rules», смержен 12.08.2026, 0 находок ≥80 в финальной версии отчёта). Три коммита:

1. `7ebafdc` — «design review fixes»: переименование действия создания правила (`Add CORS Rule` → `Create CORS Rule`, везде — триггер, заголовок модалки, кнопка сабмита), понижение приоритета кнопок `Add` в `TagInput` (были `variant="primary"`, теперь `variant="default"`, чтобы у модалки была одна первичная кнопка), полное удаление модалки удаления всей CORS-конфигурации бакета (`DeleteCorsModal` + пункт меню «Delete CORS Rules» в шапке бакета), переход `CorsRulesTable` на дефолтную раскладку колонок `DataGrid` вместо явного `gridColumnTemplate`.
2. `cf8ec61` — выравнивание отступов тулбара таба CORS Rules по паттерну `FloatingIpsList` (`Divider spacing="0"`, `pb-2` на зоне 1).
3. `46e061e` — **выходит за рамки заявленной темы**: переименовывает обобщённые лейблы действий («Delete», «Empty», «Upload») в предметные («Delete Object»/«Delete Folder»/«Delete Bucket»/«Delete Version(s)»/«Delete Objects»/«Delete All Versions», «Empty Bucket»/«Empty Buckets», «Upload Object») не только в CORS-компонентах, а во всех Ceph Buckets- и Objects-компонентах: `BucketTableView`, `DeleteObjectModal`, `DeleteObjectsModal`, `DeleteVersionModal`, `ObjectsTableView`, `UploadObjectModal`, `EmptyBucketsModal`. Заодно у `DeleteObjectsModal`/`DeleteVersionModal` появилась логика единственного/множественного числа для лейбла подтверждения (см. «Как это реализовано»).

Плюс `useBucketInfo.ts`: CORS-запрос перестаёт быть источником данных для `BucketHeader` (поле `corsData` убрано из возвращаемого объекта хука) — теперь это чистый prefetch, прогревающий общий кэш React Query для потребителей, которые сами делают тот же запрос (`CorsRulesTab`, `CorsRuleModal`, `DeleteCorsRuleModal`). Естественное следствие удаления `DeleteCorsModal`: пункту меню шапки, который его открывал, больше не нужно знать, есть ли CORS-правила (`hasCors`), поэтому это поле и убрано у `useBucketInfo`/`BucketHeader`/`BucketHeaderActions` целиком.

## Как это реализовано

### Переименование действия создания правила

```tsx
// CorsRuleModal.tsx:150
title={editingRule ? t`Edit CORS Rule` : t`Create CORS Rule`}
```

Согласовано во всех трёх местах, где раньше было расхождение между "Add CORS Rule" (заголовок/триггер) и "Create Rule" (кнопка сабмита) — теперь везде `Create CORS Rule`.

### Удаление модалки удаления всей CORS-конфигурации

`DeleteCorsModal.tsx` удалён целиком (148 строк) вместе с пунктом меню, который его открывал, и связанными тост-хелперами:

```diff
// BucketHeaderActions.tsx:44-49 (было)
-          {hasCors && <PopupMenuItem label={t`Delete CORS Rules`} onClick={() => onOpenModal("deleteCors")} />}
```

Это закрывает историю, начатую в #1092: там уже было два экземпляра `DeleteCorsModal` — рабочий, из меню шапки (вариант "а" в отчёте #1092), и недостижимый мёртвый (вариант "б", внутри `CorsRulesTab`, `setIsDeleteModalOpen(true)` нигде не вызывался). Раунд 4 в #1092 убрал только мёртвый экземпляр. Этот PR идёт дальше и убирает сам рабочий путь целиком, оставляя удаление CORS только на уровне отдельных правил (`DeleteCorsRuleModal`) и выбранной группы (`DeleteCorsRulesModal`) — эти два переименованы в `Delete CORS Rule`/`Delete CORS Rules` для консистентности с новым `Create CORS Rule`, но не удалены и не потеряли функциональность:

```tsx
// DeleteCorsRuleModal.tsx:164
confirmButtonLabel={t`Delete CORS Rule`}
```

Changeset явно документирует это как намеренное решение: *«drop the redundant bucket-header "Delete CORS Rules" entry (per-rule and batch delete are unchanged)»* — соответствует коду.

### Именование действий по целевому объекту (commit `46e061e`)

Однотипный паттерн повторяется в шести файлах Buckets/Objects — лейбл кнопки/пункта меню и метка подтверждения раньше были общим словом («Delete», «Empty», «Upload»), теперь называют объект действия:

```tsx
// DeleteObjectsModal.tsx:202-211 (новое)
  const confirmLabel = isPending
    ? t`Deleting...`
    : isVersionMode
      ? count === 1
        ? t`Delete Version`
        : t`Delete Versions`
      : count === 1
        ? t`Delete Object`
        : t`Delete Objects`
```

```tsx
// ObjectsTableView.tsx:1001-1030 (три места, было везде t`Delete`)
  <PopupMenuItem label={t`Delete Folder`} .../>   // папка с delete-marker
  <PopupMenuItem label={t`Delete Folder`} .../>   // обычная папка
  <PopupMenuItem label={t`Delete Object`} .../>   // версия/объект
```

`DeleteVersionModal.tsx:126` уже имел ветвление `isDeletingAllVersions ? t\`Delete All Versions\` : ...` для заголовка модалки (унаследовано из существующего кода, не новое в этом PR) — коммит просто провёл ту же ветку и в `confirmButtonLabel`, который раньше был захардкожен как `t\`Delete\`` и не совпадал с заголовком:

```tsx
// DeleteVersionModal.tsx:126 (новое)
confirmButtonLabel={isDeletingAllVersions ? t`Delete All Versions` : t`Delete Version`}
```

`BucketTableView.tsx:130-137`, `EmptyBucketsModal.tsx:97` (`Empty` → `Empty Bucket`/`Empty Buckets` по количеству), `UploadObjectModal.tsx:194` (`Upload` → `Upload Object`) — тот же паттерн, без ветвления по числу там, где действие всегда единичное.

Побочный, но полезный фикс в этом же коммите — `TagInput.tsx:88-95`: кнопка `Add` раньше была захардкоженной строкой без Lingui-обёртки:

```diff
-        <Button variant="primary" onClick={...}>
-          Add
-        </Button>
+        <Button variant="default" onClick={...}>
+          <Trans>Add</Trans>
+        </Button>
```

Это закрывает наблюдение из отчёта #1092 (*«У компонента [TagInput] нет ни одной строки, пропущенной через Lingui (кнопка "Add"...)»*, зафиксировано на 75/100, порог не прошло) — теперь строка локализуется. `variant="default"` — та же правка, что описана в changeset («demote the tag-input "Add" buttons so the modal has a single primary action»).

### `useBucketInfo`: CORS-запрос становится чистым prefetch

```diff
// useBucketInfo.ts:88-95
-  // Query CORS configuration
-  const { data: corsData, isLoading: isLoadingCors } = trpcReact.storage.ceph.cors.get.useQuery(
+  // Prefetch only: warms the shared cors.get cache consumed by CorsRulesTab (5 min staleTime).
+  const { isLoading: isLoadingCors } = trpcReact.storage.ceph.cors.get.useQuery(
     {
       project_id: projectId ?? "",
       bucketName: bucketName,
     },
```

Параметры запроса (`project_id`, `bucketName`, `staleTime: 5 * 60 * 1000`, `retry: false`) не изменились — это тот же query key, что использует `CorsRulesTab`/`CorsRuleModal`/`DeleteCorsRuleModal` в своих собственных вызовах `cors.get.useQuery`, так что React Query продолжает шарить один кэш-энтри между хуком и вкладкой; поведение прогрева не поломано, изменился только факт, что `useBucketInfo` больше не *читает* эти данные для своих собственных нужд.

### `CorsRulesTable`: переход на дефолтную раскладку колонок

```diff
-  const gridColumnTemplate =
-    "40px minmax(100px, 1fr) minmax(150px, 2fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(120px, 1fr) minmax(80px, 1fr) 60px"
-  ...
-  <DataGrid columns={8} gridColumnTemplate={gridColumnTemplate} className="cors-rules-table">
+  <DataGrid columns={8}>
```

Соответствует явно заявленной цели changeset («use the default DataGrid column layout») — само визуальное сравнение раскладок не проверить по коду (нужен рендер компонента `juno-ui-components`), но изменение намеренное и задокументированное, а не случайная потеря стилизации.

## Что затронуло

Поиск по всему репозиторию на голове ветки (`git grep -n '<symbol>' pr-1172 -- '*.ts' '*.tsx'`) для каждого убранного экспорта:

- **`corsData`/`hasCors` (убраны из возврата `useBucketInfo`)** — единственные оставшиеся упоминания `corsData` в репозитории — это локальные переменные в `CorsRuleModal.tsx`, `CorsRulesTab.tsx`, `DeleteCorsRuleModal.tsx`, каждая из своего собственного вызова `cors.get.useQuery`, не связанного с хуком. `hasCors` не встречается вообще. Блокировка чистая, потребителей вовне не осталось.
- **`DeleteCorsModal`, `getCorsDeletedToast`, `getCorsDeleteErrorToast`** — ноль совпадений в остальном репозитории; удаление полное, без осиротевших импортов.
- **`gridColumnTemplate` у `CorsRulesTable`** — используется в других таблицах (`BucketTableView`, `ObjectsTableView`, `EditMetadataModal`) с собственными, не связанными значениями; изменение `CorsRulesTable` их не касается.

Изменение целиком внутри `packages/aurora`, ни один экспортируемый из пакета публичный контракт (типы, tRPC-процедуры) не тронут — это чисто UI-слой (лейблы, разметка, локальный state). Changeset корректно помечен `patch`.

**Важное расхождение с описанием PR.** Заголовок и текст PR (*«apply design review fixes to bucket CORS rules UI»*) и текст changeset описывают изменение как относящееся к CORS UI. Фактически коммит `46e061e` переименовывает лейблы действий в шести файлах, из которых только `BucketHeaderActions`/`CorsRulesTable` относятся к CORS — остальные (`DeleteObjectModal`, `DeleteObjectsModal`, `DeleteVersionModal`, `ObjectsTableView`, `UploadObjectModal`, `EmptyBucketsModal`, `BucketTableView`) относятся к обычным Ceph-бакетам и объектам и с CORS не связаны вообще. Changeset (`.changeset/cors-design-fixes.md`) тоже не упоминает эту часть изменения ни словом — описывает только CORS-специфичные пункты. Само изменение (называть действия по целевому объекту вместо общего "Delete"/"Empty"/"Upload") явно осмысленное и полезное, вопрос только к точности описания охвата. См. «Ревью».

## Ревью

**1 находка ≥80:**

- **[85] Описание PR и changeset не отражают реальный охват изменения.** И заголовок/тело PR, и `.changeset/cors-design-fixes.md` рамочно описывают изменение как правки CORS UI («CORS rules UI», «Ceph/S3 bucket CORS management»). Коммит `46e061e` («name ceph storage actions after their target object») при этом переименовывает лейблы действий в `BucketTableView.tsx`, `DeleteObjectModal.tsx`, `DeleteObjectsModal.tsx`, `DeleteVersionModal.tsx`, `ObjectsTableView.tsx`, `UploadObjectModal.tsx`, `EmptyBucketsModal.tsx` — во всех Ceph Buckets/Objects компонентах, а не только в CORS-компонентах. Это ровно тот случай, когда описание PR как источник для понимания охвата изменения обманчив: тот, кто читает только заголовок/changeset (например, при подготовке релиза или при оценке своей PR на конфликт с этой веткой), не узнает, что задеты `Delete`/`Empty`/`Upload` во всех модалках объектов и бакетов. Проверено напрямую по диффу и changeset-файлу — не найдено ни одной строки в `.changeset/cors-design-fixes.md`, упоминающей объекты/Buckets-таблицу/загрузку файлов.

Не набрало порог (упомянуто в описании выше как наблюдение, не находка): визуальную корректность перехода `CorsRulesTable` на дефолтную раскладку колонок `DataGrid` нельзя подтвердить или опровергнуть по одному коду — изменение прямо заявлено в changeset как намеренное, а не похоже на случайную потерю стилизации.

---
Проанализировано: 13.08.2026 · коммит `127847c`
