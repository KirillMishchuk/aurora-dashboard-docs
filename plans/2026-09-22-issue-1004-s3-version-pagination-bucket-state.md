# Plan: Issue #1004 — S3 version pagination & bucket-state detection

**Date:** 2026-09-22 · **Status:** implemented 2026-09-22 на ветке `kiryl-issue-1004-s3-version-pagination` (не закоммичено — коммитит пользователь). 14 из 15 шагов; шаг 4 не применим при выбранном Варианте B.

> **Отклонения:** (1) исправлен баг самого плана — `stoppedAtKey = keyMarker` при abort до первой страницы даёт `undefined`, что `isFolderCovered` трактует как полное покрытие; заменено на `keyMarker ?? ""`, закреплено тестом. (2) тест на abort переписан с одной папки на две (с одной папкой он был бы зелёным по неверной причине). (3) зафиксирована тестом граница обратной совместимости: старый вход `{folders:['folder1/']}` без `prefix` вырождается — LCP равен самой папке, вложенное не атрибутируется, возвращается `hasDeletedContent: false`. (4) сверх плана добавлена i18n-строка и третья причина блокировки в `DeleteBucketModal` (fail-closed при `isPartialScan`).
>
> **Гейты:** licenses:check / lint / check-i18n / typecheck / format:check / test (235 файлов, 5669 тестов) / build — все зелёные локально.
>
> **Security-ревью:** Critical/High нет. Одна **Medium** — `BucketHeaderActions.tsx:59` `canShowDeleteVersions = (hasOldVersionsOrDeleteMarkers || isPartialScan) && canDeleteVersions` fail-open'ит пункт «Delete Versions», который через неизменённую `objects.deleteAll({includeVersionsAndDeleteMarkers:true})` безвозвратно стирает ВСЕ объекты, а не только старые версии. Достижимый сценарий: версионированный бакет >20 000 объектов без перезаписей ⇒ `hasOldVersionsOrDeleteMarkers:false` + `isPartialScan:true`; раньше пункт был скрыт. **РЕШЕНО 2026-09-22:** возвращён fail-closed — `canShowDeleteVersions = hasOldVersionsOrDeleteMarkers && canDeleteVersions`. Тупика не создаёт: «Empty Bucket» теперь видно всегда, а его чекбокс «Also delete all versions» запускает ту же мутацию под честным названием. Проп `isPartialScan` стал неиспользуемым и удалён из `BucketHeaderActions` и `BucketHeader`; тест на fail-open заменён на fail-closed. Повторные гейты после правки: lint / typecheck / format:check / test (235 файлов, 5668 тестов) / build — зелёные.
>
> **РАСШИРЕНИЕ СКОУПА 2026-09-22 (решение пользователя):** баг с «Delete Versions» **исправлен в этой же ветке**, а не вынесен в отдельный тикет. Новая процедура `objects.deleteNonCurrentVersions` (правило: удалять всё, кроме `Version` с `IsLatest === true`), `deleteAll` не тронута. При ревью реализации найдены и исправлены два дефекта: (а) группа откладывалась по «последней в массиве» после пересортировки `localeCompare`, которая расходится с байтовым порядком S3 (`A` < `a`) — теперь отложенная группа определяется по `NextKeyMarker`, сортировка переведена в байтовый порядок; (б) запись без `VersionId` отправлялась в `DeleteObjects`, что на версионированном бакете создаёт новый delete-маркер вместо удаления — теперь пропускается с логом. Оба закрыты регрессионными тестами, каждый проверен на падение против наивной реализации. Попутно удалена мёртвая проводка модалки в `ObjectBrowserView` и исправлен врущий комментарий в `BucketModals`. Отдельный changeset `keep-current-version-on-delete-versions` (позже слит с `bound-s3-version-scan-and-bucket-state` в один `ceph-bounded-version-scans-and-delete-versions`). Итоговые гейты: все 7 джоб зелёные, 5683 теста.

> **TRIPLE-REVIEW 2026-09-22 (security + performance + architecture, параллельно по 28 файлам):** 16 находок, ни одной Critical/High по безопасности (auth, валидация входа, утечки — чисто; новая деструктивная процедура построена на `cephProtectedProcedure`, тот же уровень, что и заменяемая `deleteAll`). Исправлены четыре, каждая перепроверена по коду до правки:
> 1. **`helpers/bucketState.ts` — мёртвый код** (нашли perf и arch независимо). `calculateBucketState` не импортировался нигде, кроме собственного теста; `getState` считает состояние инлайном. Файл и его тест удалены, ссылка из JSDoc `containerRouter.ts` убрана — иначе два расходящихся определения состояния бакета и 5 тестов, дающих ложную уверенность.
> 2. **Ранний выход `getState` не срабатывал на невersioned-бакетах.** Условие требовало `hasOldVersionOrDeleteMarker`, который на бакете без версионирования не выставляется никогда → полные 20 последовательных `ListObjectVersions` вместо одного, и `isPartialScan: true` на большом простом бакете, блокирующий «Delete Bucket» без причины. Регрессия по латентности ровно на тех бакетах, ради которых делался PR. Выход переписан как «все флаги, которые процедура отдаёт, устоялись».
> 3. **Ни одна из 10 объектных модалок не инвалидировала `containers.getState`.** Раньше `useBucketInfo` выводил состояние из `objects.list`, который они инвалидируют; после переноса на сервер меню бакета до 30 с показывало состояние до мутации. Инвалидация добавлена во все 10; в пяти тест-файлах пришлось дополнить моки `utils`, в `EmptyBucketsModal.test.tsx` — развести счётчик отдельным `mockInvalidateContainerState`, чтобы проверки остались осмысленными.
> 4. **Отложенная группа терялась при `IsTruncated: true` без `NextKeyMarker`** в `deleteNonCurrentVersions`: цикл выходил с непустым `pendingItems`, версии не удалялись, в `errors` не попадали, мутация рапортовала успех. Условие отсрочки приведено к точному совпадению с условием выхода из цикла.
>
> Два новых регрессионных теста (2, 4) проверены на падение против исходного кода. `currentObjectCount` задокументирован в `bucketStateOutputSchema` как нижняя граница, а не точный счётчик (ранний выход обрывает его по построению). В changeset дописаны две недокументированные для потребителей библиотеки вещи: деградация старого пути `checkDeletedContent` (только `folders` → один скан по общему префиксу, возможен `isPartialScan: true`) и `connectionTimeout: 5000`, влияющий на все Ceph-запросы.
>
> **Отложено в follow-up к #1004** (обосновано, но вне скоупа ветки): четыре почти одинаковых цикла пагинации `ListObjectVersions` с разными потолками и обработкой аборта — просится `scanObjectVersions` в `versionScan.ts`; отсутствие потолка страниц в `deleteNonCurrentVersions`; `currentObjectCount` → `hasCurrentObjects`; `connectionTimeout` в `constants.ts`; схемы `checkDeletedContent` инлайном вместо `types/versioning.ts`; `useMemo`/`Map` вместо `O(n×m)` `.find()` в `ObjectBrowserView`; извлечение `invalidateBucketQueries(utils)` вместо копипасты в 10 файлах.
>
> **Долг закрыт 2026-09-22 (после уточняющего вопроса пользователя «мы можем это всё исправить, чтобы не иметь долга?»):**
> - **`currentObjectCount` убран из контракта целиком.** Здесь была моя ошибка в оценке: я сказал «переименование ломает публичный контракт библиотеки», но `containers.getState` в `main` отсутствует — процедура новая, потребителей нет, менять её контракт бесплатно ровно до релиза. При этом переименовывать не понадобилось: рядом уже есть `isEmpty`, по определению равный `currentObjectCount === 0`, то есть поле было избыточным. Единственный прод-потребитель `DeleteBucketModal.tsx` переведён на `!isEmpty`.
> - **`connectionTimeout` → `S3_CONNECTION_TIMEOUT_MS`** в `constants.ts`, к остальным настройкам домена.
> - **Схемы `checkDeletedContent` перенесены в `types/versioning.ts`** (`checkDeletedContentInputSchema` / `checkDeletedContentOutputSchema`, на `projectScopedInputSchema` вместо ручного `project_id: z.string()`). Признак того, что место было неверным: после переноса из `versioningRouter.ts` исчез импорт `zod` — инлайновая схема была там единственной.
> - **`invalidateBucketQueries(utils, options)`** в `Ceph/hooks/`, 13 мест вызова вместо копипасты. Флаги `deletedContent` / `objectVersions` не косметика: `checkDeletedContent` — это тот самый ограниченный многостраничный скан, и безусловная инвалидация вернула бы его стоимость на каждую загрузку файла. Попутно `UploadObjectModal` и `EditMetadataModal` получили недостающий `containers.list` (аплоад меняет `bytes`/`last_modified`, показываемые на странице бакетов) — осознанное изменение поведения, не побочный эффект. Контракт хелпера закреплён 5 тестами.
>
> **Осознанно НЕ сделано — отдельным PR:** общий `scanObjectVersions`. Посчитано: в `main` циклов сканирования было **пять** (3 в `objectRouter`, 2 в `versioningRouter`), сейчас шесть — ветка добавила один и переписала один. Дублирование на 80% досталось по наследству, включая `deleteAll` — отгруженную деструктивную процедуру. Смешивать её переписывание с новой логикой удаления версий в одном PR значит лишить ревьюера возможности отделить одно от другого.
>
> Итоговые гейты: все 7 джоб зелёные, **5685 тестов**, 44 файла (+2235/−573).
>
> **Исходная формулировка follow-up (устарела, оставлена для истории):** `DeleteVersionsModal` называется «Delete Versions», но всегда зовёт `objects.deleteAll({includeVersionsAndDeleteMarkers: true})`, а та ветка в `objectRouter.ts:435-462` собирает `[...Versions, ...DeleteMarkers]` **без фильтра по `isLatest`** — то есть безвозвратно стирает и живые объекты. Поведение предсуществующее, шире скоупа #1004. Завести вместе с переписыванием issue #1004.**

# 📋 IMPLEMENTATION PLAN: issue #1004 — S3 version pagination & bucket-state detection

Все факты из брифа перепроверены построчно по HEAD `dc918d47`. **Все 27 пунктов подтвердились.** Три уточнения по фактам — в конце отчёта (раздел «Поправки к брифу»).

Я — субагент, `AskUserQuestion` мне недоступен, поэтому все развилки, требующие решения пользователя, вынесены в раздел **«Решения, требующие подтверждения»** с явной рекомендацией по каждой. Шаги 1–15 написаны под рекомендованные варианты; если пользователь выберет иначе, затронуты шаги 2–4 (бэкенд) и 8–11 (фронт).

---

## Overview

Две независимые проблемы под одним issue:

- **(A) Бэкенд.** `storage.ceph.versioning.checkDeletedContent` делает неограниченный по числу страниц S3-скан на каждую из до 100 папок параллельно, страницами по 100 ключей, без abort-signal, с пустым `catch`. Early-exit в нём при этом **никогда не срабатывает для живой папки** — то есть полный скан префикса это не край, а норма.
- **(B) Фронтенд.** Состояние бакета (`isBucketEmpty`, `hasOldVersionsOrDeleteMarkers`) вычисляется по первым 100 версиям из трёх независимых дублирующих пробников, два из которых не смотрят на `isTruncated`. Следствие — пропадающие пункты меню «Empty Bucket»/«Delete Versions» и неполный чек-лист причин в `DeleteBucketModal` (замкнутый круг: бакет не удалить и непонятно почему).

Цель: сделать обе проверки ограниченными по стоимости, отменяемыми, честными в условиях неполных данных (`isPartialScan` вместо угадывания) и покрыть их тестами, которых сейчас нет вообще.

---

## Architecture Analysis

### Current state (ключевые файлы, все пути абсолютные)

**Бэкенд**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/versioningRouter.ts:359-488` — `checkDeletedContent`, `cephProtectedProcedure`. Цикл `do{...}while(true)` :397-457; `MaxKeys: 100` :402; `Promise.all` по `input.folders` :384; пустой `catch` :469-475; внешний `mapS3ErrorToTRPCError` :481-486 (мёртвый для пофолдерных ошибок).
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/constants.ts:10` — `S3_MAX_KEYS_PER_REQUEST = 1000` (импортируется как `"../../constants"`, см. `objectRouter.ts:46`).
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts:60-126` — эталон `CONCURRENCY_LIMIT = 5` (батчи через `for` + `Promise.all`).
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:145-211` — эталон работы с `abortSignal` (проверка `abortSignal?.aborted` в начале итерации + проброс `{ abortSignal }` вторым аргументом `s3.send`); :219-306 — `list`, ветка `showVersions`; :237-245 проброс `keyMarker`/`versionIdMarker`; :297-305 возврат `isTruncated`/`nextKeyMarker`/`nextVersionIdMarker`; :298 `objects: []` при `showVersions`; :301 `nextContinuationToken = response.NextKeyMarker`.
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/clients/s3Client.ts:23-31` — `new S3Client({region, endpoint, credentials, forcePathStyle:true})`, без таймаутов и `maxAttempts`. Клиент создаётся заново на каждый вызов (`cephProcedure.ts:81-89`), общий для всех Ceph-роутеров, включая стриминговые download/upload.
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.ts:164-180` — `listObjectsInputSchema` (`maxKeys` `.min(1).max(1000).default(1000)`), `listObjectsOutputSchema`.
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/context.ts:150-152` — `Object.defineProperty(opts.req, "signal", …)`; `:423` — `ctx.signal`. **Оба доступны**, Storage-роутеры используют `ctx.req.signal`.
- В Ceph-роутерах **нет** серверного enforcement политик (проверено grep'ом) — `canUser` используется только для гейтинга UI.

**Фронтенд**
- `…/storage/-components/Ceph/hooks/useBucketInfo.ts` — 6 запросов; `containers.list` без `includeMetadata` (:50-58) → `bucketObjectCount` всегда `0`; `objects.list {maxKeys:100, delimiter:"", showVersions:true}` (:123-135) без чтения `isTruncated`; мёртвое поле `isBucketEmptyWithVersions` (:148, :155).
- `…/Ceph/hooks/bucketStateHelpers.ts:11-48` — `calculateBucketState`, без параметра усечения.
- `…/Ceph/Buckets/BucketHeader.tsx:33` → `BucketHeaderActions.tsx:52-53` — `canShowEmptyBucket = !isBucketEmpty && canEmptyBucket`, `canShowDeleteVersions = hasOldVersionsOrDeleteMarkers && canDeleteVersions`; :63-65 `return null` при отсутствии действий.
- `…/Ceph/Buckets/DeleteBucketModal.tsx:46-53` (свой пробник, `isTruncated` не читается), :121-134 (`currentObjectCount = objects?.objects?.length ?? 0` — всегда 0), :146-160, :173-190.
- `…/Ceph/Buckets/EmptyBucketModal.tsx:64-102` — единственное место с защитой `isVersionDataComplete = !versionCheckData?.isTruncated` (:97); :142/:148 `shouldDeleteVersions`.
- `…/Ceph/Objects/ObjectBrowserView.tsx:146-156` — вызов `checkDeletedContent` с `folders: allFolders.map(f => f.prefix)`; :317-354 — два разных способа использования результата (All прячет / Deleted показывает); :175-262 — рабочий прецедент полной клиентской пагинации.
- `…/Ceph/Buckets/index.tsx:153-161` — список бакетов зовёт `containers.list({project_id, includeMetadata: true})`.

**Тесты**
- `versioningRouter.test.ts` — 6 кейсов на `checkDeletedContent` (:355, :380, :405, :435, :452, :474), во всех `IsTruncated: false`.
- `mockContext.ts:114-127` — `req: { headers: {} }`, `signal` лежит **на верхнем уровне ctx, не в `req`** → `ctx.req.signal` в тестах `undefined`. Это придётся править (шаг 6).
- `ObjectBrowserView.test.tsx:159-160` и `:855-856` — мёртвая ветка/комментарий про `maxKeys === 1`.

### Proposed changes (высокоуровнево)

1. **`checkDeletedContent` переписывается с N пофолдерных сканов на один пагинируемый скан родительского префикса** без делимитера, с атрибуцией ключей по первому сегменту пути. Запросов ~в N раз меньше, один цикл вместо ста, ограничивать нужно одно место. Добавляется пожолдерный флаг `isPartialScan`.
2. **Состояние бакета переносится на сервер** новой процедурой `storage.ceph.containers.getState`, схлопывающей три клиентских пробника в один запрос с серверным early-exit и потолком страниц. `calculateBucketState` переезжает на сервер как чистая функция.
3. Клиент везде рендерит неполные данные нейтрально (fail-open), а не угадывает.

---

## Решения, требующие подтверждения пользователя

> ### ✅ ПРИНЯТО 2026-09-22 (подтверждено пользователем)
>
> - **Решение 1 (бэкенд): Вариант B** — один пагинируемый скан родительского префикса. Шаг 4 (ограничитель параллелизма для fan-out) **не выполняется**.
> - **Решение 2 (фронт): Вариант B** — серверная процедура `storage.ceph.containers.getState`. Шаги 8–11 исполняются как написаны.
> - **Решение 3: без изменений** — только `connectionTimeout: 5000` (шаг 7). `requestTimeout`/`maxAttempts` — отдельным тикетом.
> - **Решение 4 (доставка): серия коммитов в одной ветке**, решение про один/два PR принимается в конце, когда будет виден объём диффа. Коммиты и пуш — за пользователем; агент не коммитит и не пушит.
>
> Шаги 1–3, 5–15 стоят в силе без изменений.


Прежде чем исполнять, нужно подтвердить 4 пункта. Рекомендация дана по каждому; шаги плана написаны под рекомендации.

### Решение 1 (бэкенд): пофолдерный fan-out vs один скан префикса

| | **Вариант A — ужесточить существующий fan-out** | **Вариант B — один скан префикса ⭐ рекомендуется** |
|---|---|---|
| Запросов, типичный случай (20 папок × ~10 объектов) | 20 (минимум 1 на папку) | **1** |
| Запросов, 100 папок | 100 | **1–2** |
| Запросов, худший случай | 100 × потолок_страниц | **потолок_страниц** |
| Гарантия «каждая папка получила хотя бы страницу 1» | **есть** | нет — папки за высокой водой не покрыты |
| Изменение контракта процедуры | нет | `prefix?` во вход (аддитивно), `folders` → optional |
| Объём | ~0.5 дня + тесты | ~1 день + тесты |
| Что чинит пункт 10 (>100 папок) | нужен `slice(0,100)` на клиенте | **отпадает** — `folders` больше не отправляется |
| Что чинит пункт 11 (перезапуск на «Load more») | не чинит (ключ всё равно меняется) | **чинит** — ключ `{project_id, bucket, prefix}` стабилен |

**Эквивалентность данных проверена по коду.** Скан `Prefix=P` без делимитера возвращает ровно объединение того, что вернули бы сканы `Prefix=P+"foo/"` по всем папкам, плюс «свободные» объекты уровня `P` (у них в остатке после префикса нет `/` → атрибутируются в `undefined` и игнорируются). Атрибуция ключа `K` в папку: `P + K.slice(P.length).split("/")[0] + "/"`. Маркер самой папки `"P/foo/"` даёт остаток `"foo/"` → атрибутируется в `"P/foo/"` ✓. Ключ `"P/foobar"` не попадает в `"P/foo/"` ни там, ни там ✓. Все три вычисляемых флага (`folderMarkerVersionId`, `isFolderDeleted`, `hasDeletedNestedObjects`) считаются из тех же множеств.

**Где вариант B ломается — честно:**
- Под потолком страниц папки, лексикографически идущие последними, могут вообще не попасть в скан. При пофолдерном сканировании каждая папка гарантированно получала страницу 1, а значит (по п.8) корректный `folderMarkerVersionId`/`isFolderDeleted`. Митигация: **пофолдерный** `isPartialScan` + fail-open рендер (см. ниже) — непокрытая папка показывается в All как обычная, а не исчезает. Ложноположительных «есть мусор» не появляется.
- Определить покрытие можно точно: S3 отдаёт ключи лексикографически, поэтому при остановке на `NextKeyMarker = X` папка `F` полна ⟺ `F < X && !X.startsWith(F)`.
- Если внешний вызывающий передаст `folders`, не являющиеся детьми одного префикса, и не передаст `prefix`, серверный fallback (longest common prefix) может дать `""` → скан всего бакета. Документируется; клиент всегда передаёт `prefix`.
- В корне бакета с большим числом «свободных» файлов часть бюджета страниц уходит на них.

**Рекомендация: B.** Вариант A оставляет стоимость линейной по числу папок и не чинит пункты 10 и 11; B при этом строго дешевле A и в типичном, и в худшем случае.

### Решение 2 (фронт): клиентская пагинация vs серверная процедура `bucketState`

| | **Вариант A — ограниченная пагинация в `useBucketInfo`** | **Вариант B — серверная процедура ⭐ рекомендуется** |
|---|---|---|
| Что делает | цикл `objects.list` по `keyMarker` на клиенте до `!isTruncated` или потолка | одна процедура возвращает готовые флаги |
| Сколько мест надо чинить | **3** (`useBucketInfo`, `DeleteBucketModal`, `EmptyBucketModal` — у каждого свой пробник) | **1** (три пробника схлопываются в один вызов) |
| Round-trip'ов, типичный бакет | 1–N на каждый из 3 пробников | **1** (сервер выходит из цикла на 1-й странице) |
| Трафик | все версии едут на клиент | едут 6 булевых полей |
| Early-exit | невозможен (клиент не знает, что уже хватит) | **есть**: как только виден ≥1 current object и ≥1 old version/delete marker, ответ определён |
| `bucketObjectCount`/`includeMetadata` (п.15) | требует отдельного решения | **отпадает** — `containers.list` из `useBucketInfo` удаляется целиком |
| Тестируемость | цикл в React-хуке, mock по `keyMarker`, jsdom | чистая серверная функция + `mockSend` |
| Публичный контракт | без изменений | новая процедура (аддитивно, `minor`) |
| Permission-keys | не нужны | **не нужны** — проверено: в Ceph-роутерах нет серверного enforcement, а UI-гейты уже есть (`storage:containers:empty`, `storage:object_versions:delete`, `storage:objects:list`). По `PERMISSION_KEY_PATTERN.md` новая запись не требуется: это тот же ресурс и то же действие чтения |
| `AuroraApp` контракт (`packages/aurora/README.md`) | не затронут | **не затронут** — проверено grep'ом: ни `useBucketInfo`, ни `calculateBucketState`, ни `checkDeletedContent` в README не упоминаются |
| Объём | ~1 день + переписывание моков в 3 test-файлах | ~1–1.5 дня + переписывание моков в 3 test-файлах |

**Рекомендация: B.** Вариант A лишь поднимает потолок (со 100 до, скажем, 5000 версий) и оставляет тот же класс бага для больших бакетов, при этом требует поддержки цикла в трёх местах. B убирает класс бага целиком и попутно закрывает п.15 и п.19.

### Решение 3: таймауты/ретраи на `createS3Client`

`createS3Client` — общий для **всех** Ceph-процедур, включая стриминговые `downloadObject` (`objectRouter.ts:1071-1119`) и `uploadObject`. Blast radius глобального изменения — весь Ceph.

- `connectionTimeout` (фаза установления соединения) — **безопасно**, стриминга не касается. Рекомендую `5000`.
- `requestTimeout` в `@smithy/node-http-handler` реализован через `socket.setTimeout(...)`, то есть это таймаут **бездействия сокета**, а не общей длительности. Теоретически стриминг не рвёт. Но это надо **проверить против фактически установленной версии** (`@aws-sdk/client-s3: ^3.1100.0`) прежде чем включать глобально. Рекомендую **не трогать глобально** в этом фиксе; отмена длинного цикла обеспечивается `ctx.req.signal` + потолком страниц, которые мы и так добавляем.
- `maxAttempts` (сейчас дефолт 3, standard retry mode) умножает число запросов на 3. Сужать глобально до 2 — значит сделать менее устойчивыми загрузки/выгрузки объектов. Рекомендую **не трогать**; вместо этого при необходимости передавать `maxAttempts` per-command только для листингов через второй аргумент `s3.send`.

**Рекомендация: в рамках этого фикса — только `connectionTimeout: 5000`, остальное вынести отдельным тикетом.** Шаг 7 написан под это.

### Решение 4: доставка

Как оформляем — один PR, два PR (бэкенд / фронт) или серия коммитов в одной ветке? План разбит так, что шаги 1–7 (+ тесты 12) самодостаточны и отделимы от шагов 8–11 (+ тесты 13). Решение за пользователем; я никаких коммитов не предписываю.

---

## Potential Problems & Mitigations

| Риск | Severity | Митигация |
|---|---|---|
| 🔴 Любое ограничение цикла, оставляющее `folderMarkerVersionId === undefined`, **удалит живые папки** из вкладки All (`ObjectBrowserView.tsx:329`) | High | Пофолдерный `isPartialScan`; клиент в All-табе показывает папку при `!status \|\| status.isPartialScan`. Покрыто тестом (шаг 12, кейс 7 + шаг 13). |
| 🔴 «Консервативный fallback `hasDeletedContent = true`» из текста issue пометит здоровые крупные папки как «есть мусор» во вкладке Deleted | High | **Не реализуем.** `hasDeletedContent` остаётся строго фактическим; неопределённость едет отдельным полем. Зафиксировано в тексте переписанного тикета. |
| ⚠️ При варианте B (бэкенд) папки за высокой водой теряют индикатор «есть удалённое» | Medium | Fail-open: в All показываем, в Deleted не прячем истинные срабатывания (положительные результаты остаются достоверными — неполнота может только *пропустить*, но не выдумать). Потолок 20 страниц × 1000 = 20 000 версий на префикс — для реальных папок покрытие практически полное. |
| 🔴 Смена формы input `checkDeletedContent` сломает внешних потребителей BFF | Medium | `prefix` добавляем как optional, `folders` делаем optional и расширяем `.max(100)` → `.max(1000)`. Обратная совместимость сохраняется: старый вызов `{project_id,bucket,folders}` продолжает работать через LCP-fallback. Changeset `minor`. |
| ⚠️ Новая процедура `containers.getState` дублирует логику `calculateBucketState`, пока клиент не мигрирован | Medium | Мигрировать все три потребителя в рамках одного шага (шаг 10), клиентский `bucketStateHelpers.ts` удалять **последним** (шаг 11) после того, как на него не осталось импортов. |
| ⚠️ `mockContext` не отдаёт `ctx.req.signal` → тесты на abort «зелёные» ложно | Medium | Шаг 6: положить тот же signal в `req` и дать опцию `abortSignal` в `MockContextOptions`. |
| 🔒 Пустой `catch` глушит `AccessDenied` и отдаёт «мусора нет» — пользователь видит чистую папку вместо ошибки доступа | Medium | Ошибки цикла больше не глотаются: `console.error` + проброс через `mapS3ErrorToTRPCError`. ⚠️ Это **смена поведения**: раньше при частичном отказе доступа страница рисовалась, теперь запрос упадёт. Так как скан теперь один на префикс, «частичного» отказа больше нет — либо есть доступ к листингу версий бакета, либо нет. Для случая, когда `versioning.getStatus === "Enabled"`, но `ListObjectVersions` запрещён политикой бакета, клиент должен рендерить папки без индикаторов, а не ронять страницу → `ObjectBrowserView` уже устойчив (`if (!folderDeletedStatus …) return allFolders`, :321/:335), нужно только не пробрасывать ошибку в `errorComponent`. |
| ⚠️ `AbortError` из AWS SDK не должен превращаться в 500 | Low | По образцу `objectRouter.ts:187-189` / `:1119`: если `ctx.req.signal?.aborted` — не записывать ошибку, выйти из цикла и вернуть то, что уже накоплено, с `isPartialScan: true`. |
| ⚠️ Пункт 21: `objectRouter.ts:301` кладёт `NextKeyMarker` в `nextContinuationToken` | Low | Мы этих полей в новом коде не используем. **Не трогать** — в `ObjectBrowserView.tsx:252-259` логика ветвится по табу и сейчас консистентна; правка — отдельный тикет. Зафиксировать в тексте нового issue как «замеченное, вне скоупа». |
| ⚠️ После миграции на `getState` три test-файла перестанут компилироваться (их моки ветвятся по `objects.list` params) | Medium | Шаги 13 — переписывание моков идёт в том же шаге, что и миграция компонента. |
| ⚠️ Убрать `containers.list` из `useBucketInfo` — не сломает ли что-то ещё | Low | Проверено: `bucketsData` используется только для `bucketObjectCount` (`useBucketInfo.ts:61-62`). Других потребителей нет. |

---

## Prerequisites

- [x] Подтверждены Решения 1–4 (см. выше, блок «ПРИНЯТО 2026-09-22»): 1→B, 2→B, 3→только `connectionTimeout`, 4→серия коммитов в одной ветке.
- [ ] `pnpm install` отработал, `pnpm --filter @cobaltcore-dev/aurora test` зелёный на `dc918d47` (базовая линия).
- [ ] Ветка от `main` (ветку/имя выбирает пользователь).
- [ ] Не требуется: новые permission-keys, изменения `packages/aurora/README.md`, изменения policy-файлов в `apps/dashboard/src/policies/`.

---

## Implementation Steps

### ЧАСТЬ A — БЭКЕНД (приоритет 1, стабильность)

---

#### Шаг 1: Добавить константы потолка скана

**Зависимости:** нет.

**Файлы:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/constants.ts`

**Что сделать:**
1. Добавить экспорт `export const S3_MAX_SCAN_PAGES = 20` с TSDoc: «Hard ceiling on pages for the version-scan loops in `versioningRouter.checkDeletedContent` and `containerRouter.getState`. 20 × `S3_MAX_KEYS_PER_REQUEST` = 20 000 versions per request. Reaching it is reported as `isPartialScan`, never as a guessed value.»
2. Добавить `export const S3_SCAN_CONCURRENCY_LIMIT = 5` с TSDoc и ссылкой «matches `CONCURRENCY_LIMIT` in `containerRouter.list`». (Нужно, только если выбран Вариант A Решения 1; при Варианте B fan-out исчезает — тогда константу **не добавлять**, а вместо неё в шаге 3 переиспользовать существующий локальный `CONCURRENCY_LIMIT` там, где он уже есть.)

**Expected outcome:** константы доступны для импорта как `"../../constants"`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

**Acceptance criteria шага:**
- [ ] `S3_MAX_SCAN_PAGES` экспортируется, имеет TSDoc, значение 20.
- [ ] Никаких магических чисел `100`/`20` не остаётся в роутерах после шагов 2–3.

---

#### Шаг 2: Вынести чистую логику скана в отдельный helper-модуль

**Зависимости:** шаг 1.

**Файлы (создать):**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/versionScan.ts`

**Что сделать:**
1. Экспортировать чистую функцию атрибуции:
   ```ts
   /** Returns the direct-child folder prefix that `key` belongs to under `prefix`,
    *  or undefined for loose objects at the current level.
    *  "p/foo/"      -> "p/foo/"   (the folder marker itself)
    *  "p/foo/a/b"   -> "p/foo/"
    *  "p/foobar"    -> undefined
    */
   export function folderPrefixOf(key: string, prefix: string): string | undefined
   ```
   Реализация: `if (!key.startsWith(prefix)) return undefined; const rest = key.slice(prefix.length); const i = rest.indexOf("/"); return i === -1 ? undefined : prefix + rest.slice(0, i + 1)`.
2. Экспортировать чистую функцию определения покрытия:
   ```ts
   /** With S3's lexicographic key order, a folder is fully scanned iff the scan
    *  finished, or it ended at a key strictly after the folder's whole range. */
   export function isFolderCovered(folderPrefix: string, stoppedAtKey: string | undefined): boolean
   ```
   Реализация: `stoppedAtKey === undefined ? true : folderPrefix < stoppedAtKey && !stoppedAtKey.startsWith(folderPrefix)`.
3. Экспортировать `export function longestCommonPrefix(folders: string[]): string` — fallback для случая, когда `prefix` не передан (обрезать до последнего `/` включительно; при пустом массиве вернуть `""`).

**Expected outcome:** три чистые функции, тестируемые без моков S3.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

**Acceptance criteria шага:**
- [ ] `folderPrefixOf("p/foo/", "p/")` === `"p/foo/"`.
- [ ] `folderPrefixOf("p/foobar", "p/")` === `undefined`.
- [ ] `folderPrefixOf("p/foo/a/b.txt", "p/")` === `"p/foo/"`.
- [ ] `isFolderCovered("a/", undefined)` === `true`; `isFolderCovered("z/", "m/x")` === `false`; `isFolderCovered("m/", "m/x")` === `false`; `isFolderCovered("a/", "m/x")` === `true`.

---

#### Шаг 3: Переписать `checkDeletedContent` на один пагинируемый скан префикса

**Зависимости:** шаги 1, 2. **Это центральный шаг части A.**

**Файлы:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/versioningRouter.ts:359-488`

**Что сделать:**
1. Расширить input-схему (обратно совместимо):
   ```ts
   z.object({
     project_id: z.string(),
     bucket: z.string().min(1),
     prefix: z.string().optional(),               // NEW: parent prefix the folders live under
     folders: z.array(z.string()).max(1000).optional(),  // now optional; filters the output
   })
   ```
2. Расширить output-тип: к существующим пяти полям добавить `isPartialScan: boolean`.
3. Заменить `Promise.all` по папкам **одним** циклом:
   - `const scanPrefix = input.prefix ?? longestCommonPrefix(input.folders ?? [])`
   - аккумулятор `Map<string, { hasDeletedNested: boolean; isFolderDeleted: boolean; folderDeleteMarkerVersionId?: string; folderMarkerVersionId?: string; folderMarkerLastModified?: number }>`
   - на каждой итерации:
     - `if (ctx.req.signal?.aborted) { stoppedAtKey = keyMarker; break }`
     - `await s3.send(new ListObjectVersionsCommand({ Bucket: input.bucket, Prefix: scanPrefix || undefined, MaxKeys: S3_MAX_KEYS_PER_REQUEST, KeyMarker: keyMarker, VersionIdMarker: versionIdMarker }), { abortSignal: ctx.req.signal })`
     - для каждой `Version v`: `const f = folderPrefixOf(v.Key ?? "", scanPrefix); if (!f) continue;` — если `v.Key === f`, обновить `folderMarkerVersionId` **по максимуму `LastModified`, накапливая между страницами** (не «только первая страница», как сейчас — это попутно чинит скрытый баг при разрыве версий маркера по границе страницы).
     - для каждого `DeleteMarker dm`: `const f = folderPrefixOf(dm.Key ?? "", scanPrefix); if (!f) continue;` — если `dm.Key === f && dm.IsLatest` → `isFolderDeleted = true`, запомнить `VersionId`; иначе если `dm.IsLatest === true` → `hasDeletedNested = true`.
     - `pages++`
     - `if (!response.IsTruncated || !response.NextKeyMarker) break` (скан завершён, `stoppedAtKey` остаётся `undefined`)
     - `if (pages >= S3_MAX_SCAN_PAGES) { stoppedAtKey = response.NextKeyMarker; break }`
     - сдвинуть маркеры.
4. Сборка результата: список папок = `input.folders ?? [...acc.keys()]`. Для каждой папки `F`:
   ```ts
   const a = acc.get(F)
   return {
     prefix: F,
     hasDeletedContent: (a?.isFolderDeleted ?? false) || (a?.hasDeletedNested ?? false),
     isFolderDeleted: a?.isFolderDeleted ?? false,
     folderDeleteMarkerVersionId: a?.folderDeleteMarkerVersionId,
     folderMarkerVersionId: a?.folderMarkerVersionId,
     isPartialScan: !isFolderCovered(F, stoppedAtKey),
   }
   ```
5. Обработка ошибок: **убрать пустой пофолдерный `catch` целиком**. Внешний `try/catch` остаётся, но перед `throw` добавить `console.error("checkDeletedContent scan failed", { bucket: input.bucket, prefix: scanPrefix, pages, error })` (формат сообщения — по образцу `containerRouter.ts:115`). Исключение: если `ctx.req.signal?.aborted` — не бросать, а выйти из цикла и вернуть накопленное с `isPartialScan` (по образцу `objectRouter.ts:187-189`).
6. Обновить TSDoc процедуры (:346-358): убрать «N S3 requests for N folders», описать новую стоимость, потолок, семантику `isPartialScan` и **явно написать**, что `hasDeletedContent: false` при `isPartialScan: true` означает «не проверено», а не «чисто».

**Expected outcome:** один пагинируемый скан; ≤ `S3_MAX_SCAN_PAGES` запросов на вызов независимо от числа папок; отменяемый; ошибки S3 больше не глотаются.

**Verification:** шаг 12 (тесты). Промежуточно — `pnpm --filter @cobaltcore-dev/aurora typecheck`.

**Acceptance criteria шага:**
- [ ] В файле нет `MaxKeys: 100`, нет `Promise.all`, нет пустого `catch {}`.
- [ ] `MaxKeys` = `S3_MAX_KEYS_PER_REQUEST`.
- [ ] Цикл не может выполниться больше `S3_MAX_SCAN_PAGES` раз ни при каком ответе S3.
- [ ] `ctx.req.signal` проверяется в начале каждой итерации и пробрасывается в `s3.send`.
- [ ] `hasDeletedContent` нигде не выставляется в `true` «на всякий случай».
- [ ] Старый вызов `{project_id, bucket, folders}` (без `prefix`) продолжает работать.

---

#### Шаг 4 (только если выбран Вариант A Решения 1): ограничитель параллелизма

**Зависимости:** шаг 1. **Пропустить, если выбран Вариант B (рекомендованный).**

**Файлы:** `versioningRouter.ts`.

**Что сделать:** заменить `Promise.all(input.folders.map(...))` на батчевый цикл по образцу `containerRouter.ts:63-126` с `S3_SCAN_CONCURRENCY_LIMIT`; внутри каждой папки — потолок `S3_MAX_SCAN_PAGES`, проверка `ctx.req.signal`, `MaxKeys: S3_MAX_KEYS_PER_REQUEST`; early-exit исправить на `if (hasDeletedNestedObjects && folderMarkerResolvedOnFirstPage) break` (убрать требование `isFolderMarkerDeleted`).

**Acceptance criteria шага:** одновременно в полёте не более 5 S3-запросов; общее число запросов ≤ `folders.length × S3_MAX_SCAN_PAGES`.

---

#### Шаг 5: Клиентская часть под новый бэкенд — `ObjectBrowserView`

**Зависимости:** шаг 3.

**Файлы:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.tsx`

**Что сделать:**
1. `:146-156` — заменить input запроса на стабильный:
   ```ts
   { project_id: projectId ?? "", bucket: bucketName, prefix: currentPrefix || undefined }
   ```
   `folders` **не передавать**. `enabled` оставить как есть (`versioningStatus?.status === "Enabled" && allFolders.length > 0`), `staleTime: 30_000` оставить. Добавить комментарий: ключ запроса теперь не зависит от накопленного `allFolders`, поэтому «Load more» не перезапускает скан (регрессия п.11).
2. `:323-330` (вкладка All) — заменить условие фильтра на:
   ```ts
   const status = folderDeletedStatus.find((s) => s.prefix === folder.prefix)
   if (!status) return true                 // неизвестно → показываем
   if (status.isPartialScan) return true     // скан неполон → не прячем живую папку
   return !status.isFolderDeleted && status.folderMarkerVersionId !== undefined
   ```
3. `:338-342` (вкладка Deleted) — **оставить как есть**: `status?.hasDeletedContent ?? false`. Положительные результаты остаются достоверными даже при `isPartialScan`, а неполнота может только пропустить папку, а не выдумать её. Добавить поясняющий комментарий, чтобы это не «починили» обратно.
4. Никаких новых пользовательских строк (см. Open Questions по опциональному баннеру).

**Expected outcome:** живые папки не исчезают при неполном скане; «Load more» не перезапускает fan-out; ограничение в 100 папок больше не действует.

**Verification:** шаг 13 + ручная проверка (Testing Plan).

**Acceptance criteria шага:**
- [ ] В input `checkDeletedContent` нет поля `folders`.
- [ ] При двух последовательных «Load more» `checkDeletedContent.useQuery` вызывается с идентичным объектом входа.
- [ ] Папка с `isPartialScan: true` отображается во вкладке All.
- [ ] Папка с `isFolderDeleted: true, isPartialScan: false` по-прежнему скрыта во вкладке All.

---

#### Шаг 6: Починить `mockContext` под тесты на abort

**Зависимости:** нет (можно делать параллельно шагам 1–3).

**Файлы:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/mockContext.ts:114-127`

**Что сделать:**
1. Добавить в `MockContextOptions` поле `abortSignal?: AbortSignal`.
2. Создать один сигнал: `const signal = options.abortSignal ?? new AbortController().signal`.
3. Положить его **и** в `req`, и на верхний уровень: `req: { headers: {}, signal }`, `signal`.
4. Комментарий: «Prod exposes the abort signal both as `ctx.signal` and on the Fastify request (`context.ts:150`); Storage routers read `ctx.req.signal`, so the mock must carry both.»

**Expected outcome:** тесты могут передать предварительно прерванный сигнал и проверить, что цикл не делает запросов.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/versioningRouter.test.ts` (существующие кейсы должны остаться зелёными).

**Acceptance criteria шага:**
- [ ] `createMockContext().req.signal` определён.
- [ ] `createMockContext({ abortSignal: preAborted }).req.signal.aborted === true`.
- [ ] Все ранее существовавшие тесты Ceph остались зелёными.

---

#### Шаг 7: `connectionTimeout` на S3-клиенте

**Зависимости:** нет.

**Файлы:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/clients/s3Client.ts:23-31`

**Что сделать:**
1. Добавить в конфиг `requestHandler: { connectionTimeout: 5000 }` (через `NodeHttpHandler` или объектную форму `requestHandler`, в зависимости от того, что поддерживает установленная версия `@aws-sdk/client-s3 ^3.1100.0` — проверить по типам).
2. Добавить комментарий: почему **не** ставим `requestTimeout` (общий клиент используется стриминговыми download/upload, `objectRouter.ts:1071`, `:1386`) и почему не трогаем `maxAttempts` (глобальное сужение ударит по загрузкам).
3. **Ничего больше в этом файле не менять.**

**Expected outcome:** зависший TCP-connect к RGW отваливается за 5 с, а не висит до `keepAliveTimeout`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck` + существующие тесты Ceph (`s3Client` замокан в тестах роутеров, так что регрессий быть не должно) + ручная проверка: скачивание объекта >100 МБ по-прежнему проходит.

**Acceptance criteria шага:**
- [ ] `requestTimeout` и `maxAttempts` в файле **не** заданы.
- [ ] `connectionTimeout` задан и прокомментирован.
- [ ] `pnpm --filter @cobaltcore-dev/aurora test` зелёный.

---

### ЧАСТЬ B — ФРОНТЕНД/СОСТОЯНИЕ БАКЕТА (приоритет 2, корректность)

---

#### Шаг 8: Перенести `calculateBucketState` на сервер как чистую функцию

**Зависимости:** нет.

**Файлы (создать):**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/bucketState.ts`

**Что сделать:**
1. Перенести тело `calculateBucketState` из `…/Ceph/hooks/bucketStateHelpers.ts:11-48`, изменив сигнатуру так, чтобы **усечение нельзя было проигнорировать**:
   ```ts
   export interface BucketStateInput {
     versions: S3ObjectVersion[]
     isVersioningEnabled: boolean
     /** true when the scan hit the page ceiling — the caller MUST treat every
      *  "false"/"empty" answer below as "unknown", not as "confirmed". */
     isPartialScan: boolean
   }
   export interface BucketStateResult {
     currentObjectCount: number
     isEmpty: boolean
     hasOnlyDeleteMarkers: boolean
     hasOldVersionsOrDeleteMarkers: boolean
     isPartialScan: boolean
   }
   export function calculateBucketState(input: BucketStateInput): BucketStateResult
   ```
   Объектный аргумент вместо позиционного — чтобы добавление `isPartialScan` было ломающим на уровне типов и ни один вызов нельзя было забыть обновить.
2. Формулы сохранить 1-в-1 (строки :17, :20, :23, :27-28, :40 исходника), но:
   - параметр `bucketObjectCount` **убрать** — он всегда был `0` из-за п.15, а теперь `versions` полны (или помечены `isPartialScan`). `currentObjectCount` считается как `versions.filter(v => v.isLatest && !v.isDeleteMarker).length` для версионированного бакета и `versions.filter(v => !v.isDeleteMarker).length` для неверсионированного.
   - при `isPartialScan === true` **не** менять значения флагов (никаких подмен), только пробросить флаг.
3. TSDoc с явной таблицей «какие ответы надёжны при `isPartialScan`»: `true`-ответы (`hasOldVersionsOrDeleteMarkers: true`, `currentObjectCount > 0`) достоверны всегда; `false`/`isEmpty: true` — только при `isPartialScan === false`.

**Expected outcome:** чистая тестируемая функция без React и без S3.

**Verification:** шаг 12 (unit-тесты).

**Acceptance criteria шага:**
- [ ] Функция не импортирует ничего из `@/client`.
- [ ] Сигнатура объектная, `isPartialScan` обязателен.
- [ ] Параметра `bucketObjectCount` больше нет.

---

#### Шаг 9: Новая процедура `storage.ceph.containers.getState`

**Зависимости:** шаги 1, 8.

**Файлы:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts` (добавить процедуру)
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/types/ceph.ts` (Zod-схемы входа/выхода)

**Что сделать:**
1. В `types/ceph.ts` добавить:
   ```ts
   export const bucketStateInputSchema = projectScopedInputSchema.extend({
     containerName: z.string().min(1),
   })
   export const bucketStateOutputSchema = z.object({
     isVersioningEnabled: z.boolean(),
     currentObjectCount: z.number(),
     isEmpty: z.boolean(),
     hasOnlyDeleteMarkers: z.boolean(),
     hasOldVersionsOrDeleteMarkers: z.boolean(),
     isPartialScan: z.boolean(),
   })
   ```
2. В `containerRouter.ts` добавить `getState: cephProtectedProcedure.input(bucketStateInputSchema).query(...)`:
   - `GetBucketVersioningCommand` → `isVersioningEnabled = Status === "Enabled" || Status === "Suspended"`. Брать статус на сервере, а не из клиентского входа — иначе ответ можно посчитать против устаревшего статуса.
   - цикл `ListObjectVersionsCommand({Bucket, MaxKeys: S3_MAX_KEYS_PER_REQUEST, KeyMarker, VersionIdMarker})` **без `Prefix` и без `Delimiter`** (важно: делимитер отсутствует — тогда клиентская фильтрация из `objectRouter.ts:274-280` не применима и страница не может прийти визуально пустой, п.21).
   - накапливать не сами версии целиком, а только счётчики/флаги (память): `currentObjectCount`, `hasOldVersionOrDeleteMarker`, `hasRealVersion`, `anyVersionSeen`.
   - **early-exit**: как только `currentObjectCount > 0 && hasOldVersionOrDeleteMarker === true` — дальнейшие страницы не могут изменить ни один флаг → `break` с `isPartialScan = false`. Это честный early-exit (в отличие от сломанного в `checkDeletedContent`), и в типичном непустом версионированном бакете он срабатывает на первой странице.
   - `ctx.req.signal` в начале итерации + `{ abortSignal }` в `s3.send`.
   - потолок `S3_MAX_SCAN_PAGES` → `isPartialScan = true`.
   - ошибки: `console.error` + `mapS3ErrorToTRPCError(error, { operation: "get bucket state", bucket: input.containerName })`.
   - итог собрать через `calculateBucketState` из шага 8 либо посчитать инкрементально теми же формулами (предпочтительно инкрементально, чтобы не держать 20 000 объектов в памяти; тогда `calculateBucketState` остаётся для юнит-тестов формул и для случая, когда версии уже собраны).
   - распарсить через `bucketStateOutputSchema.parse(...)` (конвенция роутера).
3. TSDoc: стоимость (1 запрос в типичном случае, ≤20 в худшем), смысл `isPartialScan`, явное «`isEmpty: true` при `isPartialScan: true` НЕ значит, что бакет пуст».

**Expected outcome:** один авторитетный источник состояния бакета.

**Verification:** шаг 12.

**Acceptance criteria шага:**
- [ ] Процедура зарегистрирована и доступна как `storage.ceph.containers.getState` (проверить по `routers.ts`/сборке `cephRouter`).
- [ ] В типичном сценарии (первая страница содержит и current object, и delete marker) делается ровно 2 `s3.send` (versioning + 1 страница).
- [ ] Цикл ограничен `S3_MAX_SCAN_PAGES`.
- [ ] Новых permission-keys не добавлено (сверено с `permissionRouter.ts` и `PERMISSION_KEY_PATTERN.md`).

---

#### Шаг 10: Мигрировать трёх потребителей на `getState`

**Зависимости:** шаг 9.

**Файлы:**
- `…/Ceph/hooks/useBucketInfo.ts`
- `…/Ceph/Buckets/DeleteBucketModal.tsx`
- `…/Ceph/Buckets/EmptyBucketModal.tsx`
- `…/Ceph/Buckets/BucketHeaderActions.tsx`

**Что сделать:**
1. **`useBucketInfo.ts`:**
   - Удалить запрос `containers.list` (:50-58) и вычисление `bucket`/`bucketObjectCount` (:61-62) **целиком** — вместе с врущим комментарием на :39/:49 (это и есть ответ на вопрос про `includeMetadata` из п.15: не «чинить», а убрать; счётчик теперь приходит из `getState`, честный и без fan-out `ListObjectsV2` по всем бакетам). В TSDoc хука убрать строку «Uses bucket.count from metadata (same as Buckets page)».
   - Удалить запрос `objects.list` (:123-135).
   - Добавить `trpcReact.storage.ceph.containers.getState.useQuery({ project_id, containerName: bucketName }, { enabled: !!projectId && enabled, staleTime: 30 * 1000 })`.
   - Удалить импорт `calculateBucketState`.
   - Из возвращаемого интерфейса **удалить мёртвое** `isBucketEmptyWithVersions` (:23, :148, :155) — потребителей нет (проверено grep'ом по `packages/aurora/src/client`), а логика «bucket пуст, но есть только delete markers» живёт внутри `EmptyBucketModal`.
   - Добавить в возврат `isPartialScan`.
   - `hasVersionsOrDeleteMarkers` (:153) — сейчас `allVersions.length > 0`; заменить на `hasOldVersionsOrDeleteMarkers || currentObjectCount > 0` **только если** у него есть потребители (проверить grep'ом; если нет — удалить вместе с `isBucketEmptyWithVersions`).
   - `isLoading` пересобрать из оставшихся запросов.
2. **`DeleteBucketModal.tsx`:**
   - Удалить собственный `objects.list` (:46-53) и вычисление :121-127; перейти на `getState` (через `useBucketInfo` или прямой `useQuery` с `staleTime: 0` — модалка должна быть живой проверкой; выбрать прямой `useQuery` со `staleTime: 0`, по образцу `EmptyBucketModal.tsx:80`).
   - `hasCurrentObjects = currentObjectCount > 0`; `hasVersionsInVersionedBucket = hasOldVersionsOrDeleteMarkers`.
   - 🔴 **Добавить третью причину в чек-лист (:178-189)** — это и есть реальный дефект вместо выдуманного в issue: когда `isPartialScan === true`, кнопка удаления **не** включается, а в списке причин появляется пункт вида «Bucket contents could not be fully verified — refresh and try again» (новая i18n-строка). Без этого пользователь очищает бакет, снова упирается в блокировку и не понимает почему.
   - `cannotDelete = hasCurrentObjects || hasVersionsInVersionedBucket || isPartialScan`.
3. **`EmptyBucketModal.tsx`:**
   - Заменить `objects.list` (:68-82) на `getState` со `staleTime: 0`.
   - `isVersionDataComplete` (:97) заменить на `!state.isPartialScan` — смысл тот же, источник честнее.
   - `isBucketEmptyWithVersions` (:98) и `isTrulyEmpty` (:102) собрать из полей `getState`, семантику **не менять**.
   - Удалить комментарии :62-63, :84-86, :94-96, ставшие неверными.
4. **`BucketHeaderActions.tsx`:**
   - `:52` — привести к правилу пользователя (Empty-действие всегда видно, решает модалка): `const canShowEmptyBucket = canEmptyBucket`. Убрать зависимость от `isBucketEmpty`; проп `isBucketEmpty` удалить из интерфейса, если он больше не используется (сверить с `BucketHeader.tsx:33`). Обоснование: «Empty Bucket» — это ровно тот случай из памяти пользователя, где row-level гейтинг по кэшированным данным вреден, а `EmptyBucketModal` уже имеет ветку «This bucket is already empty» (:217).
   - `:53` — сделать fail-open: `const canShowDeleteVersions = (hasOldVersionsOrDeleteMarkers || isPartialScan) && canDeleteVersions`. Прокинуть `isPartialScan` пропом из `BucketHeader`. Это закрывает тупик из п.16 (без «Delete Versions» бакет невозможно удалить).

**Expected outcome:** три дублирующих пробника → один запрос; все гейты, которые **скрывают** действие, fail-open на неполных данных.

**Verification:** шаг 13 + ручная проверка.

**Acceptance criteria шага:**
- [ ] `grep -rn "objects.list.useQuery" …/Ceph/Buckets/` не находит ни `DeleteBucketModal`, ни `EmptyBucketModal`.
- [ ] `grep -rn "containers.list.useQuery" …/Ceph/hooks/useBucketInfo.ts` ничего не находит.
- [ ] `isBucketEmptyWithVersions` из `useBucketInfo` удалён.
- [ ] Ни один гейт, скрывающий действие, не срабатывает при `isPartialScan === true`.
- [ ] `pnpm check-i18n` прогнан после добавления новой строки в `DeleteBucketModal`.

---

#### Шаг 11: Удалить клиентский `bucketStateHelpers.ts`

**Зависимости:** шаг 10 (и только после него).

**Файлы:**
- удалить `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/hooks/bucketStateHelpers.ts`

**Что сделать:**
1. Убедиться grep'ом, что импортов `calculateBucketState` из клиента не осталось.
2. Удалить файл.

**Acceptance criteria шага:**
- [ ] `grep -rn "bucketStateHelpers" packages/aurora/src` ничего не находит.
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck` зелёный.

---

### ЧАСТЬ C — ТЕСТЫ

---

#### Шаг 12: Серверные тесты

**Зависимости:** шаги 2, 3, 6, 8, 9.

**Файлы:**
- создать `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/versionScan.test.ts`
- создать `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/helpers/bucketState.test.ts`
- дописать `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/versioningRouter.test.ts` (блок `describe("checkDeletedContent")`, :354-486)
- дописать `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/containerRouter.test.ts` (новый `describe("getState")`)

**Харнесс (уже существует, переиспользовать):** `vi.mock("../../clients/s3Client", () => ({ createS3Client: vi.fn(() => ({ send: mockSend })) }))` + `createMockContext` + `createCallerFactory(auroraRouter(...))`. msw в репозитории нет — не вводить.

**`versionScan.test.ts`:**
1. `folderPrefixOf` — маркер папки, вложенный объект, «свободный» объект уровня, ключ-похожий-но-не-в-папке (`p/foobar`), ключ вне префикса, пустой префикс.
2. `isFolderCovered` — завершённый скан, остановка до/после/внутри папки.
3. `longestCommonPrefix` — общий родитель, разные ветки → `""`, пустой массив.

**`bucketState.test.ts`:**
4. пустой бакет (`versions: []`) → `isEmpty: true`, `hasOnlyDeleteMarkers: false`.
5. неверсионированный бакет с 3 объектами → `currentObjectCount: 3`, `isEmpty: false`.
6. версионированный, только delete markers → `hasOnlyDeleteMarkers: true`, `isEmpty: true`, `hasOldVersionsOrDeleteMarkers: true`.
7. версионированный, current object + старая версия → `isEmpty: false`, `hasOldVersionsOrDeleteMarkers: true`.
8. `isPartialScan: true` пробрасывается в результат и **не меняет** остальные флаги.

**`versioningRouter.test.ts` — `checkDeletedContent` (существующие 6 кейсов переписать под новый вход + добавить):**
9. **Атрибуция:** одна страница, `Prefix: ""`, delete marker `folder1/a/b.txt` (IsLatest) → у `folder1/` `hasDeletedContent: true`, `isFolderDeleted: false`; у `folder2/` — `false`.
10. **Лексикографический порядок маркера папки (пункт 8 — обязательно закрепить):** ответ, где `Versions` содержит `folder1/` первым, а затем `folder1/z.txt` → `folderMarkerVersionId` определён; отдельный кейс: маркер `folder1/` приходит на странице 1, объекты — на странице 2 → `folderMarkerVersionId` сохраняется после второй страницы (регрессия на потерю значения между страницами).
11. **Маркер папки удалён:** `DeleteMarkers` с `Key: "folder1/", IsLatest: true` → `isFolderDeleted: true`, `folderDeleteMarkerVersionId` заполнен.
12. **Не-latest delete markers игнорируются** (восстановленный объект) → `hasDeletedContent: false`.
13. **Свободные объекты уровня** (`loose.txt` с delete marker) не заражают ни одну папку.
14. **Версии маркера папки разбиты по страницам:** две версии `folder1/` с разными `LastModified` на разных страницах → выбран максимум по времени (регрессия старого бага «только первая страница»).
15. **Потолок страниц:** `mockSend` бесконечно отдаёт `{IsTruncated: true, NextKeyMarker: "k<N>"}` → `expect(mockSend).toHaveBeenCalledTimes(S3_MAX_SCAN_PAGES)`, промис резолвится, тест не виснет (без `vi.useFakeTimers`). Папки до точки остановки → `isPartialScan: false`; папки после → `isPartialScan: true`, `hasDeletedContent: false`.
16. **`isPartialScan: false` у всех записей**, когда скан завершился (`IsTruncated: false`).
17. **`MaxKeys`:** `expect(mockSend.mock.calls[0][0].input.MaxKeys).toBe(1000)`.
18. **Abort:** `createMockContext({ abortSignal: AbortSignal.abort() })` → ≤1 вызова `mockSend`, результат возвращается с `isPartialScan: true`, ошибка не бросается.
19. **Abort в середине:** контроллер прерывается после первой страницы → цикл останавливается, накопленное отдаётся.
20. **AccessDenied:** `mockSend.mockRejectedValueOnce({ name: "AccessDenied", $metadata: { httpStatusCode: 403 } })` → бросается `TRPCError` с `code: "FORBIDDEN"` (**не** тихий `hasDeletedContent: false`), `console.error` вызван (spy).
21. **SlowDown/503:** `mockSend.mockRejectedValueOnce({ name: "SlowDown", $metadata: { httpStatusCode: 503 } })` → `TRPCError`, не проглатывание.
22. **`prefix` во входе** прокидывается в `ListObjectVersionsCommand.Prefix`; `folders` фильтрует выход.
23. **`folders` не передан** → в выходе записи по всем найденным папкам-детям.
24. **Обратная совместимость:** старый вход `{project_id, bucket, folders: ["folder1/"]}` без `prefix` работает (LCP → `"folder1/"` … проверить ожидаемую семантику и зафиксировать её тестом).
25. **FORBIDDEN без credentials** (сохранить существующий кейс :474).

**`containerRouter.test.ts` — `getState`:**
26. Версионированный бакет, страница 1 содержит current object + delete marker → early-exit: ровно 2 `mockSend` (versioning + 1 листинг), `isPartialScan: false`.
27. Бакет только с delete markers → `isEmpty: true`, `hasOnlyDeleteMarkers: true`.
28. Неверсионированный бакет (`GetBucketVersioning` → `{}`) → `isVersioningEnabled: false`, `currentObjectCount` = число объектов.
29. Потолок страниц без разрешения флагов → `isPartialScan: true`, ровно `S3_MAX_SCAN_PAGES` листинговых вызовов.
30. Abort, AccessDenied, FORBIDDEN без credentials.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage`.

**Acceptance criteria шага:**
- [ ] Все перечисленные кейсы 1–30 реализованы и зелёные.
- [ ] Ни один тест не завершается по таймауту (кейсы 15/29 доказывают отсутствие бесконечного цикла).
- [ ] Ни один тест не полагается на `IsTruncated: false` там, где проверяется усечение.

---

#### Шаг 13: Клиентские тесты

**Зависимости:** шаги 5, 10, 11.

**Файлы:**
- `…/Ceph/Objects/ObjectBrowserView.test.tsx`
- `…/Ceph/Buckets/DeleteBucketModal.test.tsx`
- `…/Ceph/Buckets/EmptyBucketModal.test.tsx`
- создать `…/Ceph/hooks/useBucketInfo.test.ts` (сейчас в `Ceph/hooks/` **нет ни одного** `*.test.ts`)

**Харнесс:** vitest + `@testing-library/react` + jsdom, `vi.mock("@/client/trpcClient")` с `mockUseQuery`, ветвящимся по входу. Образцы: `EmptyBucketModal.test.tsx`, `ObjectBrowserView.test.tsx`.

**`ObjectBrowserView.test.tsx`:**
1. 🧹 **Удалить мёртвую ветку** `if (params?.maxKeys === 1 && params?.showVersions === true)` (:159-167) и устаревший комментарий :158 — такого запроса в проде нет (`useBucketInfo` использовал `maxKeys: 100`, а после шага 10 не использует `objects.list` вовсе).
2. 🧹 Поправить устаревший комментарий на :856 («The component also runs a probe query with maxKeys: 1») — фильтр `maxKeys === 1000` оставить, комментарий переписать.
3. **Вкладка All:** папка со статусом `{isPartialScan: true, isFolderDeleted: false, folderMarkerVersionId: undefined}` **отображается** (главный регресс-тест против п.12а).
4. **Вкладка All:** папка со статусом `{isPartialScan: false, isFolderDeleted: true}` **скрыта** (сохранение существующего поведения).
5. **Вкладка All:** папка без записи в ответе отображается.
6. **Вкладка Deleted:** папка с `{hasDeletedContent: true, isPartialScan: true}` **отображается** (положительные результаты достоверны).
7. **Вкладка Deleted:** папка с `{hasDeletedContent: false, isPartialScan: true}` **не** отображается и **не** помечена как «есть мусор» (регресс-тест против вредного fallback из issue, п.12б).
8. **Стабильность query key (п.11):** отрендерить, выполнить «Load more», убедиться, что все вызовы `checkDeletedContent.useQuery` имели идентичный первый аргумент (`toEqual` по всем вызовам).
9. **>100 папок (п.10):** мок `objects.list` отдаёт 150 `folders`; `checkDeletedContent.useQuery` вызван, вход не содержит массива `folders`, никакого `BAD_REQUEST`.

**`useBucketInfo.test.ts` (новый):**
10. Возвращает поля из `getState` без трансформации.
11. `isPartialScan` пробрасывается.
12. `containers.list` и `objects.list` **не** вызываются (регресс-тест на удалённые запросы).
13. `isLoading` истинно, пока `getState` грузится.

**`DeleteBucketModal.test.tsx`:**
14. Переписать фикстуры (:282, :322, :337, :355, :373, :388) с `isTruncated: false` на новый ответ `getState`.
15. `currentObjectCount > 0` → в чек-листе есть «Empty the bucket», кнопки подтверждения нет.
16. `hasOldVersionsOrDeleteMarkers: true` → есть «Delete all versions and delete markers».
17. Обе причины одновременно → оба пункта в списке.
18. 🆕 `isPartialScan: true` при `isEmpty: true, hasOldVersionsOrDeleteMarkers: false` → **кнопка удаления не появляется**, показан третий пункт про непроверенное содержимое.
19. Полностью пустой бакет (`isEmpty: true, isPartialScan: false`) → форма подтверждения с вводом имени доступна.

**`EmptyBucketModal.test.tsx`:**
20. 🆕 Заменить мок (:60), который вообще не отдаёт признак усечения, на явные `isPartialScan: true/false`.
21. 🆕 **Покрыть защиту, которая сейчас не покрыта ни одним тестом:** `isPartialScan: true` + `isEmpty: true` + `hasOnlyDeleteMarkers: true` → показана обычная деструктивная форма, **не** ветка «Delete Versions» и **не** «already empty».
22. 🆕 **Покрыть непокрытую ветку `isBucketEmptyWithVersions`:** `isPartialScan: false, isEmpty: true, hasOnlyDeleteMarkers: true` → ветка «Delete Versions» (:172), и `deleteAll` вызван с `includeVersionsAndDeleteMarkers: true` (:148).
23. `isTrulyEmpty` → ветка «This bucket is already empty» (:217), мутация не вызывается.

**`BucketHeaderActions.test.tsx`:**
24. «Empty Bucket» присутствует при `canEmptyBucket` независимо от состояния бакета.
25. «Delete Versions» присутствует при `isPartialScan: true`, даже если `hasOldVersionsOrDeleteMarkers: false` (fail-open, п.16).
26. При отсутствии всех прав меню по-прежнему `null` (:63-65).

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage`.

**Acceptance criteria шага:**
- [ ] Кейсы 1–26 реализованы и зелёные.
- [ ] Мёртвая ветка `maxKeys === 1` и оба устаревших комментария удалены.
- [ ] В `Ceph/hooks/` появился хотя бы один `*.test.ts`.

---

### ЧАСТЬ D — ПРОЦЕСС

---

#### Шаг 14: Changeset

**Зависимости:** шаги 1–13.

**Файлы:** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.changeset/<kebab-name>.md`

**Что сделать:**
1. Добавить changeset(ы) в формате существующих (`.changeset/fix-session-scope-error-detection.md`):
   ```md
   ---
   "@cobaltcore-dev/aurora": minor
   ---

   Bound the S3 version scans behind folder and bucket state detection. `storage.ceph.versioning.checkDeletedContent` now performs a single paginated scan of the parent prefix (accepting a new optional `prefix` input) instead of one unbounded scan per folder, uses the standard 1000-key page size, honours the request abort signal, caps the scan at 20 pages, and no longer swallows S3 errors. A new per-folder `isPartialScan` flag reports an incomplete scan instead of guessing — the object browser shows such folders normally rather than hiding them. New `storage.ceph.containers.getState` procedure returns authoritative bucket emptiness/version flags in one request, replacing three truncation-prone client-side probes, which previously made "Empty Bucket" and "Delete Versions" disappear from the bucket menu on large buckets.
   ```
2. **Bump — `minor`**, потому что добавляются новая процедура и новые поля вход/выход опубликованного BFF-роутера (аддитивно, не breaking). ⚠️ В репозитории есть история несоответствий changeset↔semver (см. журнал KB: #1268/#1288) — не копировать её; если пользователь хочет консервативно, `patch` формально тоже пройдёт, но исказит контракт.
3. Если доставка двумя PR — два changeset'а (бэкенд `minor`, фронт `minor`).
4. **Тип/scope коммита** (по `commitlint.config.mjs`): `fix(aurora)` для обеих частей (тип `fix` в allow-list, scope `aurora` в allow-list; альтернативы — `ISSUE-1004` как scope, тоже валидна по regex `^ISSUE-\d+$`). Не `feat`, несмотря на новую процедуру: она заменяет существующее поведение, а не добавляет пользовательскую функциональность. **Оформление коммитов — на усмотрение пользователя, план коммиты не предписывает.**

**Acceptance criteria шага:**
- [ ] Changeset существует, валиден, package name точный (`@cobaltcore-dev/aurora`).
- [ ] Bump обоснован в описании PR.

---

#### Шаг 15: Локальный прогон всех CI-джоб

**Зависимости:** все предыдущие.

**Что сделать (из корня репо, в том же порядке, что `.github/workflows/ci-checks.yaml`):**
```bash
pnpm licenses:check
pnpm lint
pnpm check-i18n
pnpm typecheck
pnpm format:check
pnpm test
pnpm build
```
Сначала можно быстрее итерировать точечно:
```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora test
```

**Особое внимание:**
- `pnpm check-i18n` — обязателен, если в шаге 10 добавлена строка «Bucket contents could not be fully verified…» (`lingui extract + compile`, только `packages/aurora`). Если после extract изменились `.po`/`.ts` каталоги — они должны попасть в изменения.
- `pnpm format:check` — то, что реально запускает CI (не `pnpm format`).

**Acceptance criteria шага:**
- [ ] Все 7 команд проходят без ошибок.
- [ ] `git status` не показывает неучтённых изменений после `check-i18n` (каталоги переводов закоммичены вместе с кодом).

---

## Testing Plan

### Unit
- [ ] `versionScan.test.ts` — 3 чистые функции, включая границы лексикографического покрытия.
- [ ] `bucketState.test.ts` — 5 сценариев формул, включая «`isPartialScan` не меняет флаги».
- [ ] `useBucketInfo.test.ts` — новый файл, 4 кейса.

### Integration (tRPC caller + `mockSend`)
- [ ] `checkDeletedContent` — 17 кейсов (атрибуция, порядок маркера, потолок, abort, ошибки, обратная совместимость).
- [ ] `containers.getState` — 5 кейсов (early-exit, неверсионированный, потолок, abort, ошибки).

### Component (testing-library)
- [ ] `ObjectBrowserView` — обе вкладки × (`isPartialScan`, `isFolderDeleted`, отсутствие статуса) + стабильность query key + 150 папок.
- [ ] `DeleteBucketModal`, `EmptyBucketModal`, `BucketHeaderActions` — см. шаг 13.

### Ручная проверка
1. Запустить дашборд (`pnpm dev`; при недоступном бэкенде — мок из `/Users/kirylmishchuk/projects/SAP/local-mock-backend/run-all.sh`, но учесть, что он не эмулирует версионирование S3 в полном объёме — реальный Ceph предпочтительнее).
2. Бакет с включённым версионированием и ≥3 папками, в одной из которых удалённый файл:
   - вкладка All — все живые папки на месте, удалённая папка скрыта;
   - вкладка Deleted — только папка с удалённым содержимым;
   - DevTools → Network: **один** запрос `checkDeletedContent`, а не N.
3. Нажать «Load more» дважды на большом бакете → в Network **нет** повторного `checkDeletedContent` на каждое нажатие.
4. Бакет с >100 подпапок → индикаторы удалённого контента работают (раньше весь запрос падал в `BAD_REQUEST`).
5. Бакет с >20 000 версий → страница отвечает за секунды, живые папки видны, ошибки нет.
6. Бакет с 5000+ объектов, версионирование включено:
   - меню `⋮` содержит «Empty Bucket» и «Delete Versions» (раньше пункты исчезали);
   - `DeleteBucketModal` перечисляет **все** применимые причины блокировки; после очистки бакета и удаления версий кнопка «Delete Bucket» становится доступной (нет замкнутого круга).
7. Навигация прочь со страницы во время долгого скана → в логах сервера нет продолжающихся S3-запросов (проверка abort).
8. Скачивание объекта >100 МБ по-прежнему проходит (регресс-проверка шага 7).

---

## Acceptance Criteria (итоговые)

- [ ] В `packages/aurora/src/server/Storage` не осталось S3-циклов без потолка (единственный был в `checkDeletedContent`; остальные — `objectRouter.ts:445-551`, `:559-617`, `:657-698`, `:155-203`, `containerRouter.ts:63`, `swiftRouter.ts:521-591` — уже ограничены и не трогаются).
- [ ] `checkDeletedContent`: ≤ `S3_MAX_SCAN_PAGES` S3-запросов на вызов независимо от числа папок; `MaxKeys` = `S3_MAX_KEYS_PER_REQUEST`; `ctx.req.signal` соблюдается; ошибки S3 логируются и пробрасываются.
- [ ] Ни в одном месте неполный скан не подменяется значением `hasDeletedContent: true` или `isBucketEmpty: false` — неопределённость едет отдельным полем `isPartialScan`.
- [ ] Ни один гейт, **скрывающий** UI-действие, не срабатывает на неполных/неизвестных данных (fail-open).
- [ ] Живая папка не исчезает из вкладки All ни при каком значении `isPartialScan`.
- [ ] Состояние бакета вычисляется одним серверным запросом; клиентских пробников `objects.list` для этой цели не осталось.
- [ ] `bucketObjectCount`/`includeMetadata`-несоответствие устранено удалением запроса, врущий комментарий убран.
- [ ] Мёртвые `isBucketEmptyWithVersions` и `bucketStateHelpers.ts` удалены.
- [ ] Мёртвая ветка `maxKeys === 1` в `ObjectBrowserView.test.tsx` и оба устаревших комментария удалены.
- [ ] Нет регрессий: `EnableVersioning`/`SuspendVersioning`, restore/permanent delete версий, Swift-часть не затронуты.
- [ ] Changeset добавлен; `pnpm licenses:check`, `lint`, `check-i18n`, `typecheck`, `format:check`, `test`, `build` проходят.

---

## 📝 Оформление в GitHub

> **РЕШЕНО 2026-09-22 (пользователь):** новые тикеты НЕ заводим — issue #1004 остаётся единственным, к нему дописываются три комментария. Готовые тексты лежат в [`2026-09-22-issue-1004-comments/`](./2026-09-22-issue-1004-comments/): `comment-1-verification.md`, `comment-2-implementation.md`, `comment-3-out-of-scope.md`. Тело самого issue не правится — неверные места перекрываются комментарием ①. Постит пользователь сам. Заготовки тикетов ниже оставлены как черновой материал, из которого собраны комментарии.

Issue #1004 предлагалось закрыть как superseded и завести два тикета — **этот вариант отклонён**, см. выше. Ниже — исходный текст заготовок.

### Что убрать из исходного #1004
1. **AWS-ценники** («$4.00» / «$0.05» за 10 000 запросов) — это self-hosted Ceph RGW, за запросы никто не платит; к тому же две цифры в самом issue противоречат друг другу. Заменить на реальную метрику: число round-trip'ов и латентность.
2. **Тезис «разрешит удалить непустой бакет»** — недостижим: любая непустая первая страница даёт `true` хотя бы по одному из `hasCurrentObjects`/`hasVersionsInVersionedBucket` (`DeleteBucketModal.tsx:121-134`). Заменить на реальный дефект: неполный чек-лист причин → замкнутый круг.
3. **Цитаты несуществующего кода**: цикла `while (!hasDeleteMarkers)` в репозитории нет; номера строк не соответствуют `versioningRouter.ts`.
4. **Предложение «при достижении лимита ставить `hasDeletedContent = true`»** — вредно: пометит все крупные здоровые папки как «есть мусор» и вытащит их во вкладку Deleted, обесценив индикатор именно там, где он нужен.

### Что добавить (незамеченное в #1004)
- п.2 — сломанный early-exit (полный скан — норма, а не край);
- п.5 — пустой `catch`, глушащий AccessDenied/SlowDown;
- п.10 — `.max(100)` + отсутствие `slice` на клиенте → `BAD_REQUEST` и молчаливая потеря индикаторов при >100 папок;
- п.11 — нестабильный query key → перезапуск fan-out на каждое «Load more»;
- п.15 — `bucketObjectCount` всегда `0` из-за отсутствующего `includeMetadata`.

---

### 🎫 Тикет 1 (бэкенд)

**Title:** `Bound the S3 version scan in versioning.checkDeletedContent`

**Labels:** `bug`, `backend`, `storage`

**Body:**

> **Supersedes the backend half of #1004.** The original issue quoted code that does not exist in the repository (a `while (!hasDeleteMarkers)` loop, wrong line numbers) and priced the impact in AWS request fees — irrelevant for our self-hosted Ceph RGW. This is a re-write against the code at `dc918d47`.
>
> ### Problem
> `packages/aurora/src/server/Storage/routers/ceph/versioningRouter.ts:359-488` (`checkDeletedContent`) runs, for each of up to 100 folders **in parallel with no concurrency limit**, a `do {...} while (true)` pagination loop over `ListObjectVersions` with **no page limit, no time limit and no abort signal**.
>
> 1. **The early-exit never fires for a live folder.** The condition at `:446` requires `hasDeletedNestedObjects && isFolderMarkerDeleted && folderMarkerVersionId`. For any folder that has *not* been deleted, `isFolderMarkerDeleted` is permanently `false`, so the loop always runs to the end of the prefix. The "worst case" is the ordinary case. *(Not identified in #1004.)*
> 2. **Page size is 100** (`:402`) while `S3_MAX_KEYS_PER_REQUEST = 1000` (`Storage/constants.ts:10`) is used by every other paginating call in the package (`objectRouter.ts:155, :451, :563, :663`) — 10× more round-trips than necessary.
> 3. **No concurrency limit** on the `Promise.all` over up to 100 folders (`:384`), although `containerRouter.ts:60` already establishes `CONCURRENCY_LIMIT = 5`.
> 4. **`ctx.req.signal` is not used**, so navigating away does not stop the scan. Both `objectRouter.ts:156` and `:1727` do use it.
> 5. **The per-folder `catch` at `:469-475` is empty.** `AccessDenied`, `SlowDown`/503 and timeouts are all silently converted to `hasDeletedContent: false` with no logging, which makes the outer `mapS3ErrorToTRPCError` (`:481-486`) dead code for per-folder failures. A permissions problem renders as "this folder is clean". *(Not identified in #1004.)*
> 6. **Nothing downstream backstops this.** Fastify's `requestTimeout: 30000` (`server.ts:41`) bounds only request *receipt*, not handler execution; `s3Client.ts:23-31` sets no `requestTimeout`/`connectionTimeout` and leaves `maxAttempts` at the SDK default of 3 (multiplying every request by 3); there is no rate-limit plugin; a fresh `S3Client` (`maxSockets` 50) is created per call (`cephProcedure.ts:81-89`) with no global socket ceiling.
>
> ### Client-side consequences
> - `ObjectBrowserView.tsx:146-156` passes `folders: allFolders.map(f => f.prefix)` **without slicing**. Past 100 sub-folders the Zod `.max(100)` rejects the whole request with `BAD_REQUEST` and the deleted-content indicators silently stop working. *(Not identified in #1004.)*
> - The same `.map()` allocates a new array on every accumulation page (`:205`/`:219`), producing a new query key, so the entire fan-out restarts on every "Load more". *(Not identified in #1004.)*
>
> ### Why the fix must not guess
> `ObjectBrowserView.tsx:317-353` consumes the result two different ways:
> - the **All** tab *hides* a folder when `!isFolderDeleted && folderMarkerVersionId !== undefined` is false;
> - the **Deleted** tab *shows* a folder when `hasDeletedContent` is true.
>
> Therefore: (a) any bound that leaves `folderMarkerVersionId` undefined will **delete live folders from the main listing**; (b) the "conservative fallback: set `hasDeletedContent = true` when the limit is hit" suggested in #1004 would mark every large **healthy** folder as containing deleted content and pull it into the Deleted tab, destroying the indicator exactly where it matters. The absence of an entry is safer than a wrong entry — `:325` already shows the folder when no status is present.
>
> ### Proposed fix
> - Replace the N-scans-for-N-folders fan-out with **one paginated, delimiter-less scan of the parent prefix**, attributing each key to its direct-child folder. Same data (the union of the folders is a subset of the parent prefix), ~N× fewer requests, one loop to bound instead of a hundred. Add an optional `prefix` input; keep `folders` as an optional output filter for backward compatibility.
> - Hard page ceiling (20 × 1000 = 20 000 versions), reported through a new **per-folder `isPartialScan`** flag. Never substitute a guessed `hasDeletedContent`.
> - `MaxKeys` → `S3_MAX_KEYS_PER_REQUEST`.
> - Honour `ctx.req.signal` at the top of each iteration and pass `{ abortSignal }` to `s3.send`.
> - Stop swallowing errors: log and map through `mapS3ErrorToTRPCError`; distinguish "no deleted content" from "could not check".
> - Client: send `prefix` instead of the folder array (stable query key, no 100-folder cap); in the All tab treat `isPartialScan` as "unknown" and show the folder; in the Deleted tab keep trusting positive results (an incomplete scan can only miss, never invent).
>
> ### Known limitation of the single-scan approach
> Under the page ceiling, folders that sort lexicographically last may not be reached at all, whereas per-folder scanning guaranteed every folder its first page. This is reported honestly via `isPartialScan` and rendered neutrally, and it is still strictly cheaper than the current behaviour in both the typical and the worst case.
>
> ### Test gaps to close
> `versioningRouter.test.ts:354-486` has 6 cases for `checkDeletedContent` and **every one of them sets `IsTruncated: false`** — pagination, the early exit and the `catch` are entirely uncovered. Needed: page ceiling (an infinitely-truncating `mockSend` must terminate), abort, `AccessDenied`/`SlowDown`, the lexicographic guarantee that a folder's own marker arrives on page 1, key attribution, and >100 folders on the client.
>
> ### Out of scope (noted while investigating)
> `objectRouter.ts:301` puts `NextKeyMarker` into `nextContinuationToken` in the `showVersions` branch, and `:274-280` filters versions client-side *after* the `MaxKeys` cut when a delimiter is given, so a page can arrive visually empty with `isTruncated: true`. Neither is triggered by the call sites in this issue (they use `delimiter: ""`). Tracked separately.

---

### 🎫 Тикет 2 (фронт)

**Title:** `Bucket state is decided from the first 100 versions`

**Labels:** `bug`, `frontend`, `storage`

**Body:**

> **Supersedes the frontend half of #1004.** One claim in the original issue is wrong (see "Correction" below) and its line references are stale. Re-written against `dc918d47`.
>
> ### Problem
> Three independent client-side probes each read **only the first page** of `objects.list` and derive the bucket's state from it:
>
> | Location | Query | Truncation handled? |
> |---|---|---|
> | `hooks/useBucketInfo.ts:123-135` | `{maxKeys:100, delimiter:"", showVersions:true}` | ❌ `isTruncated`/`nextKeyMarker`/`nextVersionIdMarker` are never read |
> | `Buckets/DeleteBucketModal.tsx:49-52` | same | ❌ no check at all |
> | `Buckets/EmptyBucketModal.tsx:67-82` | same | ✅ only place — `isVersionDataComplete = !isTruncated` (`:96`, added in #1249) |
>
> `hooks/bucketStateHelpers.ts:11-48` (`calculateBucketState`) has no truncation parameter at all, so there is nothing stopping a caller from ignoring it.
>
> ### User-visible impact
> `BucketHeader.tsx:33` → `BucketHeaderActions.tsx:52-53`:
> - `canShowEmptyBucket = !isBucketEmpty && canEmptyBucket` — on a bucket whose first 100 entries are all delete markers, **"Empty Bucket" disappears from a non-empty bucket**.
> - `canShowDeleteVersions = hasOldVersionsOrDeleteMarkers && canDeleteVersions` — when the old versions sit past entry 100, **"Delete Versions" disappears**, so the versions can never be cleared and therefore the bucket can never be deleted. Dead end.
> - If no action qualifies, `:55-65` returns `null` and the whole `⋮` menu vanishes.
>
> `DeleteBucketModal.tsx:173-190` shows an **incomplete list of blocking reasons**: the user clears what is listed, hits the block again, and has no way to learn why.
>
> ### Correction to #1004
> #1004 claims this "may allow deleting a non-empty bucket". That is **not reachable**: `:121-134` computes `cannotDelete = hasCurrentObjects || hasVersionsInVersionedBucket`, and any non-empty first page sets at least one of them. The real defect is the incomplete reason list, not a bypassed guard.
>
> ### Additional defect not in #1004
> `useBucketInfo.ts:48-62` calls `containers.list` **without `includeMetadata`**; the schema default is `false` (`types/ceph.ts:56`) and the fast path returns a hard-coded `count: 0` (`containerRouter.ts:46-54`). So `bucketObjectCount` is **always 0**, contradicting the comment on `:49` ("to get accurate count (same as Buckets page)"), the `bucketObjectCount > 0` branch of `calculateBucketState` (`:33-37`) never executes, and `isBucketEmpty` rests entirely on the first page. There is no metadata safety net.
>
> Also dead: `useBucketInfo.ts:148` returns `isBucketEmptyWithVersions`, which no component reads.
>
> ### Proposed fix
> Move the computation to the BFF: a new `storage.ceph.containers.getState` returning `{ isVersioningEnabled, currentObjectCount, isEmpty, hasOnlyDeleteMarkers, hasOldVersionsOrDeleteMarkers, isPartialScan }`. It paginates server-side with a hard page ceiling and a **real** early exit (once at least one current object and at least one old version/delete marker have been seen, no further page can change the answer — typically one request), honours the abort signal, and reports incompleteness as `isPartialScan` rather than guessing.
>
> This collapses the three duplicate probes into one request, removes the `bucketObjectCount` lie together with the `containers.list` query, and makes the truncation parameter impossible to forget (`calculateBucketState` takes an object with a required `isPartialScan`).
>
> Client rules, split by what the action costs if the guess is wrong:
> - **Non-destructive gates fail open.** `Empty Bucket` becomes permission-gated only (its modal already has a live "already empty" branch, `EmptyBucketModal.tsx:217`), and a folder whose scan was incomplete stays visible in the object browser's All tab.
> - **Destructive gates fail closed.** `DeleteBucketModal` gains a third blocking reason for unverifiable contents and never enables deletion on incomplete data. `Delete Versions` stays gated on `hasOldVersionsOrDeleteMarkers` alone — an unconfirmed scan must not be what makes it appear, because the action behind it permanently deletes current objects too (see the follow-up ticket). This costs nothing: `Empty Bucket` is always visible and its "also delete all versions" checkbox reaches the same mutation under a label that matches what it does.
>
> No new `storage:*` permission key is required (the same read, already covered by `storage:objects:list`; Ceph routers carry no server-side policy enforcement). `AuroraApp`'s public contract in `packages/aurora/README.md` is unaffected.
>
> The server-side scan is a prerequisite bounded loop — see the backend ticket for the shared page-ceiling constant and abort-signal conventions.
>
> ### Test gaps to close
> - **No tests exist at all** for `bucketStateHelpers.ts` or `useBucketInfo.ts` (`Ceph/hooks/` contains 3 files, none of them a test).
> - `DeleteBucketModal.test.tsx`'s `describe("Versioning logic")` (`:316-395`) hard-codes `isTruncated: false` in every fixture (`:282, :322, :337, :355, :373, :388`).
> - `EmptyBucketModal.test.tsx`'s mock (`:60`) never returns `isTruncated`, so it is `undefined` and `isVersionDataComplete` is always `true` — **the one existing truncation guard in the codebase is covered by zero tests**; the `isBucketEmptyWithVersions` ("Delete Versions") branch is also uncovered.
> - `ObjectBrowserView.test.tsx:159-160` and `:855` branch on `maxKeys === 1`, a query that does not exist in production — dead branch plus stale comments, to be removed.

---

### 🎫 Тикет 3 (follow-up, обнаружено при работе над #1004)

**Title:** `"Delete Versions" permanently deletes current objects, not just old versions`

**Labels:** `bug`, `storage`, `data-loss`

**Body:**

> Found while fixing #1004. **Pre-existing behaviour, not introduced by that work** — filed separately because the fix belongs to the destructive-actions area, not to pagination.
>
> ### Problem
> `DeleteVersionsModal.tsx:66-71` unconditionally calls:
> ```ts
> // Always delete all versions and delete markers (includeVersionsAndDeleteMarkers: true)
> deleteVersionsMutation.mutate({ ..., includeVersionsAndDeleteMarkers: true })
> ```
> That branch of `objectRouter.ts:435-462` collects:
> ```ts
> const versions = listResponse.Versions ?? []
> const deleteMarkers = listResponse.DeleteMarkers ?? []
> const allItems = [...versions, ...deleteMarkers]   // no IsLatest filter
> ```
> `ListObjectVersions.Versions` includes current versions (`IsLatest: true`), so every object in the bucket is hard-deleted by explicit `VersionId`. **The action labelled "Delete Versions" empties the bucket, irreversibly.**
>
> It sits in the same `⋮` menu as "Empty Bucket", which invites the reading "clear the stale versions, keep my files". The modal copy (`:104-107`) — "This action will permanently delete all versions and delete markers" — is literally accurate but does not disclose that current object data is included.
>
> ### Guards that do exist
> Typed bucket-name confirmation and the `storage:object_versions:delete` permission. This is **not** an authorization bypass — it is a labelling/expectation defect on an unrecoverable operation.
>
> ### Already mitigated in the #1004 work
> The bucket-header menu item is now fail-closed: an unverified/partial bucket scan can no longer be what makes "Delete Versions" appear (`BucketHeaderActions.tsx`). That removes the reachable path where the option showed up on a large versioned bucket that had **no** old versions at all. It does not address the mislabelling itself.
>
> ### Options
> 1. **Make the action match its name** — delete only non-latest versions and delete markers. Needs either a new `deleteAll` mode or reuse of `objects.deleteVersionsBulk`. Preferred: the menu then means what it says, and "Empty Bucket" keeps owning the full wipe.
> 2. **Make the name match the action** — relabel and rewrite the copy to state plainly that current objects are deleted too.
>
> Option 1 is the better product answer; option 2 is the cheap stop-gap if 1 is out of budget.

---

## Open Questions

1. ~~**Доставка.**~~ **РЕШЕНО 2026-09-22:** серия коммитов в одной ветке; выбор один/два PR откладывается до конца работы.
2. **Значение потолка `S3_MAX_SCAN_PAGES`.** Предложено 20 (20 000 версий). Нужна ли другая цифра под реальные размеры бакетов в qa-de-1?
3. **Баннер о неполном скане в `ObjectBrowserView`.** Показывать ли пользователю нейтральное уведомление, когда хотя бы у одной папки `isPartialScan: true` (например: «Some folders could not be fully checked for deleted content»)? Это новая i18n-строка и дополнительный прогон `check-i18n`. По умолчанию в плане **не** добавляется — только нейтральный рендер.
4. **Имя новой процедуры.** `storage.ceph.containers.getState` vs `storage.ceph.objects.bucketState`. Выбрал `containers.getState` (это состояние контейнера, и рядом уже живут `containers.list`/`containers.head`), но конвенцию стоит подтвердить.
5. **`DeleteVersionsModal`.** Если «Delete Versions» станет fail-open, стоит ли дать модалке отдельную ветку «nothing to delete» по образцу `EmptyBucketModal.tsx:217`? В план **не** включено (расширение скоупа) — нужен отдельный тикет, если да.
6. **`objectRouter.ts:301`** (`nextContinuationToken = NextKeyMarker`) — заводить отдельный тикет или оставить как «замеченное» в теле issue #1?
7. **`requestTimeout`/`maxAttempts` на S3-клиенте** (Решение 3) — заводить отдельный тикет на исследование, или оставить как есть без записи?

---

## Поправки к брифу (три расхождения, найденные при верификации)

1. **п.3 — неверный путь к константе.** `S3_MAX_KEYS_PER_REQUEST` лежит в `packages/aurora/src/server/Storage/constants.ts:10`, а **не** в `routers/ceph/constants.ts` (такого файла нет). Импортируется как `from "../../constants"`.
2. **п.6 / п.27 — подвох в тестовом харнессе.** `ctx.req.signal` в проде есть (`context.ts:150-152`), но `createMockContext` (`mockContext.ts:114-127`) кладёт `signal` **только на верхний уровень** ctx, а `req` — это `{ headers: {} }`. То есть `ctx.req.signal` в тестах `undefined`, и тест «на abort» без правки `mockContext` будет зелёным ложно. Это учтено отдельным шагом 6.
3. **п.15 — дополнение, усиливающее аргумент.** Страница списка бакетов (`Buckets/index.tsx:153-161`) уже зовёт `containers.list({project_id, includeMetadata: true})`. Если бы `useBucketInfo` тоже передавал `includeMetadata: true`, он бы **разделил кэш** с этой страницей и переход «список → бакет» был бы бесплатным. То есть «починить» было бы дешевле, чем кажется. Тем не менее при рекомендованном Варианте B правильный ответ другой: запрос удаляется целиком, потому что счётчик приходит из `getState` — без `ListObjectsV2` по всем бакетам при глубоком заходе по прямой ссылке.

Всё остальное (пункты 1, 2, 4, 5, 7–14, 16–26) подтверждено построчно.

---

## TRIPLE-REVIEW, РАУНД 2 — 2026-09-23

Второй параллельный прогон security / performance / architecture по той же ветке, уже после
исправлений первого раунда. 36 находок, 13 уникальных значимых после дедупликации.
Critical — ноль; High: 2 security, 3 performance, 2 architecture.

### Исправлено (баги)

1. **`deleteNonCurrentVersions` удалял живой объект**, если в завершённой группе ключа нет записи
   с `IsLatest`. `current === undefined` читалось как «текущей версии нет» → в удаление уходила вся
   группа, по явным `VersionId`, то есть без delete marker и без возможности восстановления.
   Теперь группа пропускается целиком и попадает в `errors`. Проверено реверсией.
2. **Легаси-путь `checkDeletedContent`** (`folders` без `prefix`) отвечал уверенно и неправильно:
   `longestCommonPrefix` для одной папки возвращал саму папку. Теперь поднимается к родителю —
   но только когда самая мелкая папка и есть общий префикс.
3. **`getState` не мог выйти рано на версионированном бакете с чистой историей.** Недоделка
   первого раунда: ранний выход был починен только для неверсионированной ветки. `isEmpty` теперь
   берётся отдельным `ListObjectsV2({MaxKeys: 1})` параллельно с `GetBucketVersioning`, а
   неверсионированный бакет не сканируется вообще. Это закрыло и тупик «Delete Bucket»
   структурно: неподтверждённая история больше не делает бакет неудаляемым.
4. **O(n×m) в рендере `ObjectBrowserView`.** Паттерн был и раньше, но именно эта ветка сняла
   ограничитель `.max(100)`. `Map` + `useMemo`.

### Исправлено (долг)

`deleted[]` больше не копится (у мутации своя схема выдачи), буфер одного ключа ограничен,
два `.refine()` на вход, `hasOnlyDeleteMarkers` схлопывается в false при неполном скане,
`isPartial` в выдаче + предупреждение в модалке, changeset переведён в minor, `currentObjectCount`
убран из фикстур четырёх файлов, два непрочитанных поля убраны из `useBucketInfo`, строгая схема
имени бакета, четыре устаревших JSDoc.

### Отклонено с обоснованием

Предложение убрать `containers.getState` из безусловной инвалидации (якобы правка метаданных и
копирование не меняют состояние бакета). Проверка показала обратное: `updateMetadata` и
`copyObject` — это `CopyObjectCommand`, и на версионированном бакете копирование на существующий
ключ создаёт новую версию, переключая `hasOldVersionsOrDeleteMarkers`. Правка внесла бы ровно тот
баг рассогласования кэша, ради которого хелпер и писался. Причина записана рядом с вызовом.

### Регрессия, внесённая и пойманная в этом же раунде

`.refine()` требует `prefix` или `folders`, а `ObjectBrowserView` слал
`prefix: currentPrefix || undefined` — в корне бакета `""` falsy, значит уходило `undefined` без
`folders`, и запрос отклонялся бы. Индикаторы удалённого контента молча умерли бы на экране по
умолчанию. Ни серверные, ни клиентские тесты этого не ловили — дыра была ровно в стыке.
Починено, добавлены тесты с обеих сторон, клиентский проверен реверсией.

### Отложено (записано в комментарий ③)

Серверные проверки прав на деструктивные мутации (репозиторное решение: `deleteAll`,
`deleteVersionsBulk`, `containers.delete` в том же положении — `canUser` не вызывается нигде в
`server/Storage`), общий `scanObjectVersions`, потолок страниц для `deleteNonCurrentVersions`,
UTF-8-компаратор вместо UTF-16, `S3Client` на каждый вызов, дубли строк аккумулятора пагинации,
шесть мёртвых модалок в `ObjectBrowserView`.

### Итог

44 файла, +2655/−584. 7/7 джоб CI зелёные, 5695 тестов. Ничего не закоммичено.

---

## TRIPLE-REVIEW, РАУНД 3 — 2026-09-23

10 сырых находок от трёх ревьюеров → 9 уникальных (security 1, performance 3, architecture 6;
одна находка совпала у performance и architecture, найдена независимо). Critical и High по
безопасности нет. Каждая проверена отдельно перед действием.

### Исправлено (① ④ ⑤ ⑦ ⑧)

**① Флаг `deletedContent` в `invalidateBucketQueries` убран целиком.** Нашли performance и
architecture независимо: 4 из 13 мест проставляли его неверно, причём `objects.delete` вызывался
из двух модалок с двумя разными ответами. Собирался инвертировать флаг (`contentUnchanged` как
opt-out), но проверка посылки показала, что инвертировать нечего: `checkDeletedContent` считает
delete markers, которые *сейчас latest*, а запись в ключ с текущим delete marker делает его
не-latest — значит upload, copy и создание папки поверх удалённого ключа двигают эту метрику ровно
так же, как удаление. Из 13 мест не может сдвинуть только `updateMetadata` (работает лишь по
видимому ключу). Флаг ради одного места — ловушка, а не оптимизация. Плюс это более дешёвый из двух
сканов (один префикс против всего бакета), так что opt-in был выбран задом наперёд дважды.
Остался `objectVersions` — он честно узкий.

Косвенное подтверждение диагноза: три файла тестов вообще не мокали `versioning` в `useUtils` —
ровно те три, чьи вызовы флаг не проставляли.

**④** `bucketStateInputSchema`: `containerName` → `bucketName`. Остальные три схемы
`containers.*` (`create`/`delete`/`head`) используют `bucketName`; новая процедура затащила словарь
соседнего `objectRouter` в чужое пространство имён. Публичный тип `AppRouter` на пакете 2.0.0 —
сейчас бесплатно, позже breaking.

**⑤** `checkDeletedContentOutputSchema.parse(...)` на возврате. Ветка добавила три выходные схемы и
применяла две; третья существовала только под `z.infer`, хотя её докблок описывает контракт
`isPartialScan`.

**⑦** Только docstring. Performance заявил High: `hasRealVersion` ставится только из
`response.Versions`, поэтому бакет с одними delete markers (lifecycle `NoncurrentVersionExpiration`
выел реальные версии) не выходит рано и идёт до потолка. Механика верна, вывод — нет: доказать
`hasOnlyDeleteMarkers` в этом случае действительно можно только дойдя до конца, ровно как в уже
задокументированном «чистая история». Лишней работы нет — неполон был блок «Cost, honestly».
Понижено до Low, дописан четвёртый шейп.

**⑧** `status` добавлен в `bucketStateOutputSchema`; `versioning.getStatus` убран из
`useBucketInfo` и `EmptyBucketModal`. `getState` всё равно шлёт `GetBucketVersioning`, а сырая
трёхзначная строка нужна заголовку бакета, чтобы отличить Suspended от Unversioned. Минус один
round-trip на загрузку страницы и на каждое открытие модалки (там `staleTime: 0` — дубль был
гарантированный). В `EmptyBucketModal` схлопнулась трёхвариантная развилка ошибки: раздельного
отказа больше не бывает, два msgid ушли из каталогов.

### Проверено обращением

- `DeleteVersionsModal` без инвалидации `checkDeletedContent` → тест падает.
- `useBucketInfo` со вторым `getStatus` → тест падает.

### Отложено осознанно (записано в comment-3)

- **② Ответ `checkDeletedContent` не ограничен.** Вход ограничили, выход в `prefix`-режиме отдаёт
  запись на каждую дочернюю папку, до ~20 000. Предложенный architecture фикс («не отдавать
  дефолтные записи, клиент уже умеет обрабатывать отсутствие») **проверен и отвергнут**: в All-вкладке
  отсутствующая запись показывает папку, а дефолтная (`folderMarkerVersionId === undefined`) —
  прячет. Не эквивалентно. Нужен честный потолок плюс явный «unknown».
- **⑥ Вынести `planPageDeletions` в `helpers/`.** Это не отложенный общий пагинатор: группировка
  страницы и решение keep/delete — чистые функции, `deleteAll` не трогают. Отдельный PR.
- **⑨ Сырые SDK-ошибки в `console.error`** — существующий паттерн в полудюжине мест, менять всё
  сразу или не менять.

### Открытый вопрос к пользователю

**③ Changeset `minor` на ужесточение входного контракта в пакете 2.0.0.** Changeset сам честно
перечисляет: два входных шейпа, которые раньше принимались, теперь отвергаются; процедура, которая
молча деградировала, теперь бросает. По semver для post-1.0 пакета с публичным `AppRouter` это
breaking. Либо `major`, либо одна фраза о том, почему поверхность tRPC-процедур не считается
semver-обязательством. Решение команды, не агента. В публичные комментарии не вынесено.

### Итог раунда

44 файла, +2778/−641. 7/7 джоб CI зелёные, 5700 тестов. Ничего не закоммичено.
