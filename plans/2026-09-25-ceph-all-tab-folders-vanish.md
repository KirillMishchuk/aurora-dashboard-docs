# Plan: Ceph — папки исчезают во вкладке «All» в версионированном бакете

**Date:** 2026-09-25 · **Status:** implemented 2026-09-25; [PR #1331](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1331) влит в `main` 2026-09-28 — правка теперь лежит некоммиченной прямо на `main` и перепроверена на нём (см. ниже), осталось отвести ветку и открыть PR; см. [`FOLLOW-UPS.md`](../FOLLOW-UPS.md) п. 28 — пункт остаётся `открыт` до открытия PR

> **Версия 2, базис #1331.** Первая редакция плана была написана по `main` и переписана целиком
> 25.09.2026, когда стало ясно, что правка пойдёт отдельным PR следом за #1331. Раздел 0 перечисляет,
> какие выводы первой редакции на новом базисе оказались неверны.

# 📋 ПЛАН ИСПРАВЛЕНИЯ (базис #1331): папки исчезают во вкладке «All» в версионированном Ceph-бакете

> Базис: ветка `kiryl-s3-version-pagination`, HEAD `5b25aad0`, дерево чистое. Все номера строк ниже — **по этой ветке**. Прочитаны: `aurora-dashboard/CLAUDE.md`, `DOCS/aurora-dashboard-kb/README.md`, `DOCS/FOLLOW-UPS.md` (п. 1, 10, 17, 28), предыдущий план `DOCS/plans/2026-09-25-ceph-all-tab-folders-vanish.md`. Все шесть пунктов установленной причины перепроверены по коду ветки — расхождений нет. Baseline прогон `ObjectBrowserView.test.tsx` на ветке: **40 тестов, все зелёные**.

---

## 0. Что изменилось относительно плана по `main` (главное)

**Подтвердилось без изменений:**
- Причина бага цела: `ObjectBrowserView.tsx:352` — `return !status.isFolderDeleted && status.folderMarkerVersionId !== undefined`; `folderMarkerVersionId` сервер заполняет только при `key === folder` (`versioningRouter.ts:443-450`); пустышку пишет только `objectRouter.createFolder` (`objectRouter.ts:1047-1075`, `PutObjectCommand` с `Body: Buffer.from("")`, `IfNoneMatch: "*"` — строка сместилась с 806 на 1047).
- Вкладка All берёт папки из `ListObjectsV2` → `CommonPrefixes` (`objectRouter.ts:311-343`).
- Расхождение счётчика и таблицы: `totalItemCount` (`ObjectBrowserView.tsx:409-410`) на All считается по нефильтрованному `allFolders`.
- `folderDeletedStatus` по-прежнему читается **только** внутри `deletedFoldersList`; остальные вхождения `checkDeletedContent` в клиенте — только `invalidate` (`invalidateBucketQueries.ts:69` — новый хелпер #1331, заменивший россыпь инвалидаций в модалках).
- Swift не затронут: в `-components/Swift/` ноль вхождений `checkDeletedContent` / вкладок All-Deleted.
- Changeset нужен, тип — `patch` для `@cobaltcore-dev/aurora`.
- Правка чисто клиентская.

**Больше не верно (выводы старого плана, которые надо отбросить):**

1. 🔴 **«Мок `ObjectsTableView` не показывает, какие папки пришли, поэтому существующие тесты баг поймать не могли»** — на ветке это уже не так. #1331 дополнил мок (`ObjectBrowserView.test.tsx:47-51`) рендером `data-testid={folder-<prefix>}` на каждую папку. **Шаг «перенести `data-folders`/`data-objects` из repro-файла» из старого плана отменяется целиком**, вместе с самим repro-блоком: скрипты не нужны, ассерты пишутся через `screen.queryByTestId("folder-<prefix>/")`. Файл `/private/tmp/.../scratchpad/repro-folders-vanish.test.tsx` для этой работы больше не нужен ни идеей, ни строками.
2. 🔴 **«Тест `hides folders with no versions…` ничего не проверяет (единственный assert — наличие таблицы)»** — на ветке он проверяет ровно сломанное поведение и **упадёт после правки**: `ObjectBrowserView.test.tsx:703-705` ассертит, что `folder-deleted-folder/` и `folder-soft-deleted-folder/` отсутствуют. Прогноз «падений не ожидается ни одного» из старого плана **неверен на этом базисе**.
3. 🔴 **Появился второй падающий тест, которого на `main` не было:** `:815-849` «All tab: still hides a folder that is confirmed deleted by a complete scan» — добавлен самим #1331, ассертит отсутствие `folder-confirmed-deleted/`. После правки папка показывается → тест красный. Его надо **инвертировать**, а не удалять (см. Шаг 3).
4. 🔴 **Ссылка на fail-open `catch` в `versioningRouter.ts:470-475`** (старый план, вопрос 4 и Open Question 3) — **этого кода на ветке нет**. #1331 убрал per-folder try/catch вместе с фан-аутом: теперь один скан, ошибка которого проксируется наружу через `mapS3ErrorToTRPCError` (`versioningRouter.ts:422-437`). Значит, тезис «правка снимает All-tab-последствие swallow-а» больше не применим — снимать нечего. Вместо него актуален другой: ошибка запроса на вкладке Deleted по-прежнему проглатывается **клиентом** (из хука деструктурируется только `data`, `:154`), что и есть follow-up 10.
5. ⚠️ **Аргумент о производительности сильно ослаб.** Старый план обещал «исчезают N пагинируемых `ListObjectVersions`-сканов (до 100 на страницу)». На ветке скан **один** и ограничен: `S3_MAX_SCAN_PAGES = 20` × `S3_MAX_KEYS_PER_REQUEST = 1000` = до 20 000 версий, до 20 HTTP-запросов к Ceph, раз в `staleTime: 30s` на префикс. Выигрыш реальный, но это «один ограниченный многостраничный скан вместо нуля», а не «сто сканов вместо нуля». **Рекомендация: в changeset и в комментарии к коду формулировать сдержанно** («до 20 постраничных `ListObjectVersions`-запросов на просмотр каталога»), не повторяя формулировку старого плана — иначе ревьювер #1331 справедливо укажет на устаревшую оценку.

**Добавилось нового (учтено в плане):**
- `statusByPrefix` (`:291-294`) — после правки остаётся живым, его читает только ветка Deleted (`:361`, `:363`). Не удалять.
- `if (status.isPartialScan) return true` (`:351`) — уходит вместе с веткой.
- Новых потребителей `folderDeletedStatus` не появилось. `isPartialScan` вне `checkDeletedContent` читают `DeleteBucketModal.tsx:116` и `EmptyBucketModal.tsx:76`, но у **другой** процедуры — `containers.getState`. Их правка не касается.
- 🔴 **После правки у `checkDeletedContent.isPartialScan` не остаётся ни одного клиентского читателя** (ветка Deleted его игнорирует — это и есть follow-up 1). Поле не удалять: контракт и серверные тесты корректны, потребитель появится при закрытии follow-up 1. Явно записать это в реестр — иначе следующий ревьювер предложит выпилить поле.
- Новый факт для follow-up 17 (см. раздел «Ответы», п. 6) — правка снимает его главное возражение.

---

## Overview

Во вкладке «All» объектного браузера Ceph клиент поверх ответа `ListObjectsV2` делает вторую, избыточную фильтрацию папок по данным `versioning.checkDeletedContent`. Условие требует у папки zero-byte объекта-пустышки `folder/`, который создаёт только кнопка «Create folder» в Aurora, — поэтому папки, залитые любым другим S3-клиентом, после ответа `checkDeletedContent` исчезают, и рисуется «No objects found.». Правка клиентская: ветка All в `deletedFoldersList` сводится к `return allFolders`, а сам запрос перестаёт выполняться вне вкладки Deleted.

---

## Architecture Analysis

### Current state

**Файлы, которые меняются**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.tsx`
  - `:147-167` — запрос `checkDeletedContent`; вход `prefix: currentPrefix` (`:161`), `enabled` на `:164`;
  - `:282-294` — `statusByPrefix`;
  - `:338-373` — `deletedFoldersList` (`useMemo`); ветка All — `:343-356`, ключевая строка `:352`, fail-open `:346`, `isPartialScan` `:351`; ветка Deleted — `:358-372`;
  - `:409-410` — `totalItemCount`.
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.test.tsx` — 1229 строк; блок `describe("ObjectBrowserView - Folder filtering with versioning")` на `:620-945`.
- `.changeset/<новый файл>.md`
- `/Users/kirylmishchuk/projects/SAP/DOCS/FOLLOW-UPS.md` (вне репозитория).

**Только чтение (контекст):** `versioningRouter.ts:350-504`, `types/versioning.ts:130-186`, `objectRouter.ts:311-343` и `:1047-1075`, `ObjectsTableView.tsx:288-336, 570-645`.

**Почему фильтрация на All избыточна в принципе (главный аргумент правки, перепроверен)**

`ListObjectsV2` возвращает только актуальные версии; `CommonPrefixes` строится исключительно из ключей текущей выборки. Следовательно: (а) если все ключи под префиксом перекрыты delete-маркерами, `CommonPrefix` не придёт — папки не будет в `allFolders`, скрывать нечего; (б) если `CommonPrefix` пришёл — под ним есть хотя бы один живой ключ; (в) пустая папка, созданная Aurora, представлена одним ключом `folder/`, который при `Delimiter: "/"` тоже сворачивается в `CommonPrefix`, и исчезает из листинга сама после удаления. Ответ сервера уже является точной истиной для вкладки All; надстройка над ним может только ошибиться.

### Proposed changes

Направление из запроса подтверждено и принимается, с двумя уточнениями по тестам (Шаг 3):

1. Ветка `tab !== "deleted"` → `return allFolders` (вместе со строкой `isPartialScan`).
2. `enabled` получает `tab === "deleted"`.
3. Тест `:649-706` переписывается; тест `:815-849` **инвертируется** (не удаляется); тест `:778-813` переименовывается/перекомментируется; добавляются три новых кейса.
4. Changeset `patch`; обновление follow-up-ов 28/1/10/17.

Сервер не меняется: контракт `checkDeletedContent` нужен вкладке Deleted (оттуда берутся `hasDeletedContent`, `isFolderDeleted`, `folderDeleteMarkerVersionId`, `folderMarkerVersionId` — `ObjectBrowserView.tsx:361-368` → `ObjectsTableView.tsx:298/321/630-633/803`).

---

## Ответы на вопросы, которые план должен закрыть

**1. Не ломает ли отключение `checkDeletedContent` на вкладке All что-то ещё?**
Нет. Полный поиск по `packages/aurora/src` + `apps` (исключая `dist`, `routeTree.gen.ts`): `folderDeletedStatus` — только `ObjectBrowserView.tsx:154, 292, 346, 358, 373`; `statusByPrefix` — только `:291, 349, 361, 363`. Прочие вхождения `checkDeletedContent` в клиенте — `invalidate` в `invalidateBucketQueries.ts:69` (и его тест) плюс моки в 7 тестовых файлах. Инвалидация неактивного запроса — no-op; при переходе на Deleted запрос выполнится заново.
Поведенческие следствия, принимаемые осознанно: (а) на вкладке All у папки не может появиться бейдж «Deleted» — но и раньше не могло, такие папки просто пропадали; (б) переключение All → Deleted больше не попадает в прогретый кэш, первый рендер Deleted будет с задержкой скана (при переключении вкладок префикс и так сбрасывается в корень, `:666`/`:681`, так что прогрев и раньше попадал редко).

**2. Правка чисто клиентская или нужен и сервер?**
Чисто клиентская. Сервер после #1331 корректен для своей задачи; проблема в интерпретации ответа.

**3. Не затрагивает ли аналогичная логика Swift?**
Нет. `grep` по `-components/Swift/` — ноль вхождений `checkDeletedContent` и `tab === "deleted"`; у Swift нет версионирования и вкладок All/Deleted.

**4. Как соотносится с follow-up 1 и 10?**
Ни один не закрывается — обе про ветку Deleted, которую мы не трогаем.
- **Follow-up 1** («вкладка Deleted игнорирует `isPartialScan`») остаётся открытым и становится **важнее**: после правки у `checkDeletedContent.isPartialScan` не остаётся клиентских читателей вообще. В тексте п. 1 надо (а) поправить ссылки на строки, (б) убрать фразу «Ветка All (`:346`) такой случай уже обрабатывает нейтрально» — ветки All больше нет, вместо неё записать «вкладка All отвязана от этого запроса, поэтому п. 1 — единственный оставшийся потребитель флага».
- **Follow-up 10** («Deleted должна fail-closed») остаётся открытым; наша правка реализует только его вторую половину («нейтральный `allFolders` оставить только для All»). Из текста п. 10 эту фразу убрать, оставив требование `return []` в ветке Deleted (`:358` после правки — пересчитать), и актуализировать ссылки `:164` (`enabled`) и `:654` (`TabNavigationItem`). Рассинхрон `enabled`/`!== "Unversioned"` мы **не трогаем**.
- Из п. 10 и п. 28 надо **удалить упоминание fail-open `catch` в `versioningRouter.ts:470-475`** — на ветке его нет (см. раздел 0, пункт 4).

**5. Какие тесты на ветке могут упасть?**

| Файл / тест | Завязка | Прогноз |
| --- | --- | --- |
| `ObjectBrowserView.test.tsx:649-706` «hides folders with no versions…» | ассертит отсутствие 2 папок на All | 🔴 **Упадёт** → переписать (Шаг 3.1) |
| `ObjectBrowserView.test.tsx:815-849` «All tab: still hides a folder that is confirmed deleted…» (добавлен #1331) | ассертит отсутствие папки на All | 🔴 **Упадёт** → инвертировать (Шаг 3.2) |
| `ObjectBrowserView.test.tsx:778-813` «All tab: shows a folder whose scan is partial…» | ассертит наличие папки | Пройдёт, но станет вакуумным → переименовать/перекомментировать (Шаг 3.3) |
| `ObjectBrowserView.test.tsx:708-730` «asks for the bucket root as an explicit empty prefix» | читает `mock.calls[0][0]` | Пройдёт: `enabled` не влияет на то, что хук вызывается и вход вычисляется |
| `ObjectBrowserView.test.tsx:732-776`, `:851-887` (Deleted) | ветка Deleted | Не затронуты |
| `ObjectBrowserView.test.tsx:889-921`, `:923-944` | форма входа `checkDeletedContent` | Пройдут |
| `ObjectBrowserView.test.tsx:1153-1228` («a folder that isn't there»), `:947-1060` (permissions), `:1062-1151` (state across folder change) | не читают `checkDeletedContent` | Не затронуты |
| `versioningRouter.test.ts:355-860` | сервер | Не затронуты (сервер не меняем) |
| `invalidateBucketQueries.test.ts`, `invalidateVersioningStatusQueries.test.ts` | `invalidate` | Не затронуты |
| `DeleteVersionModal.test.tsx:288, 332-338`, `ObjectsTableView.test.tsx`, `EmptyBucketModal.test.tsx`, `DeleteBucketModal.test.tsx` | `folderMarkerVersionId` как проп / `isPartialScan` у `containers.getState` | Не затронуты |

**6. Побочный эффект для follow-up 17 (новое, в старом плане не было).**
П. 17 («`checkDeletedContent` ограничивает запрос, но не ответ») содержит предупреждение: дешёвый фикс «не отдавать записи в полностью дефолтном состоянии» **отвергнут**, потому что «отсутствующая запись заставляет вкладку All папку *показать*, а присутствующая запись без `folderMarkerVersionId` — *скрыть*». После нашей правки это возражение **исчезает полностью**: вкладка All ответ не читает, а во вкладке Deleted отсутствующая запись и дефолтная запись дают один и тот же результат (`hasDeletedContent` falsy → папка не показана, `:361`). Это надо дописать в п. 17 как разблокировку — но **в этот PR не тащить** (отдельное изменение контракта процедуры, серверные тесты, свой changeset).

**7. Нужен ли changeset и какой bump?**
Да, `patch` для `@cobaltcore-dev/aurora`: багфикс без изменения публичного API (`AuroraApp`-пропы, слоты, серверные экспорты не меняются). Ориентир по стилю и объёму — `.changeset/fix-session-scope-error-detection.md` (тоже `patch`, один связный абзац). Заголовок PR: `fix(aurora): ...` (тип и скоуп есть в `commitlint.config.mjs`).

**8. Не выглядит ли правка как частичный откат #1331? (важно для ревьювера)**
Формально да — удаляются две строки, которые #1331 только что добавил (`:351` + `if` вокруг неё) и разворачивается один его тест. По существу — нет, и это надо явно сказать в описании PR:
- Что #1331 сделал в этой зоне и **остаётся нетронутым**: единый постраничный скан вместо фан-аута, вход `prefix` вместо `folders`, ограничение `S3_MAX_SCAN_PAGES`, честный `isPartialScan` в контракте, `statusByPrefix`, мемоизация списков, отказ от swallow-а ошибок, `containers.getState`.
- Что уходит: **только** двухстрочная защита `isPartialScan` внутри All-фильтра. Она была митигацией того же класса проблемы (не прятать папку, про которую ответ ненадёжен); наша правка убирает саму причину — весь фильтр, — и тем самым **включает** эту митигацию в предельном виде: на All не прячется ни одна папка, ни при каком ответе.
- Текст changeset-а #1331 при этом **не становится ложным**: фраза «the object browser shows such folders normally rather than hiding them» (`.changeset/ceph-bounded-version-scans-and-delete-versions.md`, абзац 3) после нашей правки остаётся верной — папки с неполным сканом на All по-прежнему показываются, просто по более общей причине. Противоречия в CHANGELOG не возникнет.
- Тестовые данные #1331 (`confirmed-deleted/` с `dm-1`/`v-1`) сохраняются — меняется только ассерт и название. Ревьювер видит не «удалили мой тест», а «тот же сценарий, переосмысленный».

---

## Potential Problems & Mitigations

| Риск | Severity | Митигация |
| --- | --- | --- |
| ⚠️ Ревьювер #1331 прочтёт правку как откат его работы | Medium | Явный абзац в описании PR по схеме из п. 8; данные тестов #1331 сохранены, изменены только ассерт и название; ссылка на follow-up 28 |
| ⚠️ «А теперь на All покажется удалённая папка» | Low | Невозможно: `ListObjectsV2` не отдаёт `CommonPrefix` для префикса, где все ключи перекрыты delete-маркерами. Закрепить тестом (Шаг 3.4) |
| ⚠️ Папка с delete-маркером на пустышке теперь видна на All и предлагает «Delete Folder» | Low | Новой деструктивной поверхности нет: на All папки не несут `isDeleted`, поэтому `ObjectsTableView` (`:573`, `:597-645`) рисует обычную ветку «Regular folder → Delete Folder», гейтингованную `canDeleteFolder`, как у любой другой папки |
| ⚠️ Первое открытие вкладки Deleted стало «холодным» | Low | Осознанный размен: на All мы экономим до 20 `ListObjectVersions`-запросов на каждый просмотр каталога; при переключении вкладок префикс и так сбрасывается, прогрев кэша почти никогда не попадал |
| `isPartialScan` у `checkDeletedContent` остаётся без клиентских читателей | Low | Не удалять поле; зафиксировать в follow-up 1 (Шаг 5), иначе следующий ревьювер предложит выпилить контракт |
| 🔴 Расхождение счётчика и таблицы (текущий баг) | — | После правки оба источника — `allFolders`; вносим в acceptance criteria |
| ⚠️ Мок-стейт течёт между тестами | Medium | В `vitest.config.ts` нет `clearMocks`/`mockReset`/`restoreMocks`, а `vi.clearAllMocks()` в `beforeEach` (`:621-647`) чистит только `mock.calls`, **не** реализации: `mockReturnValue` предыдущего теста доживает до следующего. Каждый новый тест обязан явно мокать `versioning.getStatus`, `objects.list` **и** `checkDeletedContent` |
| Вкладка Deleted остаётся fail-open | Low | Вне скоупа → follow-up 10 (Шаг 5) |

---

## Prerequisites

- [ ] **PR #1331 смержен в `main`**; рабочая ветка отведена от обновлённого `main`.
- [ ] ⚠️ Номера строк даны по `kiryl-s3-version-pagination@5b25aad0`. Если #1331 уедет в `main` сквошем с дополнительными правками по ревью, строки сместятся — **искать по идентификаторам** (`deletedFoldersList`, `statusByPrefix`, `checkDeletedContent.useQuery`), а не по номерам.
- [x] Repro-скаффолдинг не нужен: мок таблицы уже рендерит папки, а сломанное поведение уже закреплено тестом `:649-706` — он и есть repro.
- [x] Решений от пользователя не требуется.

---

## Implementation Steps

### Шаг 1 — Убрать избыточную фильтрацию папок на вкладке All

**Файл:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.tsx`

**Что делать:**
1. В `deletedFoldersList` (`:338-373`) заменить всё тело ветки `if (tab !== "deleted") { ... }` (`:343-356`) на единственный `return allFolders`. Удаляются: fail-open `:346`, локальный `filtered` `:348-353`, строка `if (status.isPartialScan) return true` `:351`, ключевая строка `:352`.
2. Заменить комментарий над `useMemo` (`:338-339`, «Filter folders based on deleted content check from BFF / Also add isDeleted flag…») и перенести объяснение внутрь, к новому `return`. Комментарий должен отвечать **почему фильтрации нет**, а не констатировать её отсутствие. Обязательный смысл:
   - вкладка All рисует то, что вернул `ListObjectsV2`; этот листинг видит только актуальные версии, поэтому пришедший `CommonPrefix` уже означает живое содержимое, а полностью удалённая папка в листинг не попадает вовсе;
   - прежняя проверка требовала zero-byte пустышку `folder/`, которую пишет только `objects.createFolder` (кнопка «Create folder» в Aurora), и потому прятала любую папку, залитую сторонним S3-клиентом.
3. Тип-аннотацию `deletedFoldersList` (`:340-342`) **оставить** — она нужна ветке Deleted; `S3FolderPrefix[]` присваивается ей корректно (опциональные поля).
4. Массив зависимостей (`:373`) оставить как есть: `[tab, allFolders, folderDeletedStatus, statusByPrefix]` — ветка Deleted читает оба.
5. Ветку `tab === "deleted"` (`:358-372`) и `statusByPrefix` (`:291-294`) **не трогать**.

**Expected outcome:** на вкладке All в таблицу уходит ровно то, что вернул сервер.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`; тесты `:649-706` и `:815-849` краснеют — это ожидаемо и правильно, они чинятся на Шаге 3.

---

### Шаг 2 — Не запрашивать `checkDeletedContent` на вкладке All

**Файл:** тот же.

**Что делать:**
1. В `enabled` (`:164`) добавить `tab === "deleted"`:
   ```ts
   enabled: !!projectId && tab === "deleted" && versioningStatus?.status === "Enabled" && allFolders.length > 0,
   ```
   Порядок важен для читаемости, но и для значения: выражение остаётся строго булевым `false` на All.
2. Переписать комментарий `:147-148` («Need this in both tabs: "deleted" to show deleted folders, "all" to hide deleted folders») — он теперь неверен. Новый должен сказать: запрос — источник данных исключительно для вкладки Deleted; на All он не нужен, потому что листинг уже точен, а стоит он до `S3_MAX_SCAN_PAGES` (20) постраничных `ListObjectVersions`-запросов по всему префиксу на каждый просмотр каталога.
3. Абзац `:149-153` (про `prefix` вместо `folders`, от #1331) и комментарий `:158-160` (про пустую строку как корень) **сохранить дословно** — они описывают вход, который мы не меняем.
4. `staleTime: 30 * 1000` не менять. `versioningStatus?.status === "Enabled"` **не трогать** (follow-up 10).

**Expected outcome:** при обычном просмотре бакета скан версий не выполняется; на Deleted поведение прежнее.

**Verification:** тесты Шага 3.5/3.6; вручную — DevTools Network (см. Testing Plan).

---

### Шаг 3 — Привести в порядок тесты блока `ObjectBrowserView - Folder filtering with versioning`

**Файл:** `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.test.tsx`

Во всех новых/правленых тестах: `versioning.getStatus` → `{ status: "Enabled" }`, `objects.list` и `checkDeletedContent` задаются явно (см. риск про утечку моков), ассерты через `screen.getByTestId("folder-<prefix>")` / `queryByTestId`. `beforeEach` блока (`:621-647`) не трогать.

**3.1. Переписать тест `:649-706`** «hides folders with no versions (permanently deleted) from All tab».
Новое название по смыслу: *«All tab: shows every folder the listing returned, including folders with no folder-marker object»*. Данные оставить прежними (три папки `active-folder/`, `deleted-folder/`, `soft-deleted-folder/` и их статусы `:672-695`) — ассерты инвертировать: все три `getByTestId` присутствуют. В комментарии зафиксировать репорт: eu-de-1, версионированный бакет, объекты залиты не через Aurora, поэтому у папок нет zero-byte пустышки и `folderMarkerVersionId` отсутствует; раньше такие папки мигали и сменялись на «No objects found.».

**3.2. Инвертировать тест `:815-849`** «All tab: still hides a folder that is confirmed deleted by a complete scan» (добавлен #1331).
Данные (`confirmed-deleted/`, `hasDeletedContent: true`, `isFolderDeleted: true`, `folderDeleteMarkerVersionId: "dm-1"`, `folderMarkerVersionId: "v-1"`, `isPartialScan: false`) **сохранить**. Изменить: название → *«All tab: shows a folder whose marker object is deleted while live content remains»*; ассерт `queryByTestId(...).not.toBeInTheDocument()` → `getByTestId(...).toBeInTheDocument()`. Комментарий обязан объяснить, почему прежний ассерт был неверен: удалён только служебный маркер папки, а раз `ListObjectsV2` вернул `CommonPrefix` — под префиксом есть живой ключ, и прятать папку нельзя. Это второй случай из репорта.

**3.3. Переименовать/перекомментировать тест `:778-813`** «All tab: shows a folder whose scan is partial rather than hiding it (fail-open, high risk)».
Ассерт не меняется (папка показана). Новое название: *«All tab: an unresolved (partial) scan does not affect the listing either»*. Комментарий: вкладка All больше не читает ответ вовсе, поэтому ни `isPartialScan`, ни отсутствующий `folderMarkerVersionId` не могут её изменить; тест остаётся как страховка от того, что логику «неполного скана» из follow-up 1 когда-нибудь скопируют обратно в ветку All.

**3.4. Новый тест — полностью удалённая папка не показывается, потому что её нет в листинге.**
`objects.list` → `{ objects: [], folders: [], isTruncated: false }` в **корне бакета** (`resetMockSearch()` по умолчанию, `prefix: undefined`) — при непустом префиксе сработал бы `folderIsMissing` (`:624-646`) и таблица не отрендерилась бы. `checkDeletedContent` → `[{ prefix: "gone/", hasDeletedContent: true, isFolderDeleted: true, folderDeleteMarkerVersionId: "dm-9", isPartialScan: false }]`. Ассерты: `queryByTestId("folder-gone/")` отсутствует, `getByTestId("objects-table")` присутствует. Смысл в комментарии: скрытие удалённых папок на All обеспечивает сервер (`ListObjectsV2`), а не клиентский фильтр — правка ничего не ослабила.

**3.5. Новый тест — запрос не выполняется на вкладке All.**
Проверять второй аргумент последнего вызова: `vi.mocked(trpcReact.storage.ceph.versioning.checkDeletedContent.useQuery).mock.calls`, `(calls.at(-1)![1] as { enabled?: boolean }).enabled` === `false`. Условия: `getStatus` → `Enabled`, `objects.list` с непустым `folders` — то есть единственная причина `false` именно вкладка. Мок хука объявлен как `vi.fn(() => ({...}))` без параметров (`:288-295`), аргументы всё равно пишутся в `mock.calls` — менять мок не нужно.

**3.6. Новый тест — запрос выполняется на вкладке Deleted.**
`resetMockSearch({ tab: "deleted" })`, `objects.list` → `{ objects: [], folders: [{ prefix: "d/" }], versions: [], isTruncated: false }`, `getStatus` → `Enabled`. Ассерт: `enabled` последнего вызова === `true`. Важно брать **последний** вызов: на первом рендере `allFolders` ещё пуст и `enabled` там `false` — он заполняется эффектом `:204-238`.

**3.7. (Дёшево, по желанию)** Усилить тест `:732-776` «shows folders with delete markers in Deleted tab» — он уже ассертит `getByTestId("folder-deleted-folder/")`, дополнительных изменений не требует. Ничего не делать.

**Expected outcome:** файл зелёный; 3.1 и 3.2 краснеют при откате Шага 1, 3.5/3.6 — при откате Шага 2.

**Verification:**
```bash
pnpm --filter @cobaltcore-dev/aurora test 'src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.test.tsx'
```
(baseline до правок — 40 passed). Затем временно вернуть строку `:352` и убедиться, что 3.1 и 3.2 краснеют.

---

### Шаг 4 — Changeset

**Файл:** `.changeset/ceph-all-tab-folders-visible.md` (создать).

1. Frontmatter:
   ```
   ---
   "@cobaltcore-dev/aurora": patch
   ---
   ```
2. Текст на английском, стиль и объём — как `.changeset/fix-session-scope-error-detection.md` (связный абзац-два, не булеты). Содержание:
   - симптом: в версионированном Ceph-бакете содержимое каталога мелькало и сменялось на «No objects found.», счётчик в шапке при этом показывал реальное число элементов, а папки были видны только во вкладке Deleted;
   - причина: вкладка All отбрасывала любую папку без zero-byte объекта-пустышки `folder/`, который создаёт только «Create folder» в Aurora, — страдал каждый бакет, наполнявшийся сторонним клиентом (Elektra, `s3cmd`, `rclone`, SDK); тем же условием пряталась папка, у которой delete-маркер стоит на пустышке, хотя внутри есть живой объект;
   - почему проверка не нужна: `ListObjectsV2` отдаёт только актуальные версии, поэтому пришедший `CommonPrefix` сам по себе означает живое содержимое, а полностью удалённая папка в листинг не попадает;
   - побочный эффект: `versioning.checkDeletedContent` больше не выполняется на вкладке All — при обычном просмотре каталога экономится до `S3_MAX_SCAN_PAGES` (20) постраничных `ListObjectVersions`-запросов. **Формулировать именно так**, без «N сканов на папку» (см. раздел 0, пункт 5).

**Verification:** `pnpm format:check` не ругается на новый файл.

---

### Шаг 5 — Обновить реестр follow-up-ов

**Файл:** `/Users/kirylmishchuk/projects/SAP/DOCS/FOLLOW-UPS.md` (**вне репозитория**, в upstream-PR не попадает).

1. **П. 28** (`:282-321`) — перевести в статус «сделан» (и строку сводки `:38`), сослаться на этот PR. Из тела убрать блок «Отложено до мержа #1331» и абзац про fail-open `catch` в `versioningRouter.ts:470-475` (кода нет на новом базисе). Ссылку на старый план (`plans/2026-09-25-…md`) сохранить, пометив, что номера строк там по `main`, а фактическая правка сделана по базису #1331.
2. **П. 1** (`:203-216`) — статус `открыт`. Обновить ссылку на строки ветки Deleted; удалить фразу «Ветка „All“ (`:346`) такой случай уже обрабатывает нейтрально»; дописать, что после правки п. 28 у `checkDeletedContent.isPartialScan` не осталось клиентских читателей, и п. 1 — единственный оставшийся.
3. **П. 10** (`:227-239`) — статус `открыт`. Убрать «нейтральный `allFolders` оставить только для All» (сделано), оставить требование `return []` в ветке Deleted; пересчитать ссылки на `:358`, `:164`, `:654`; убрать упоминание fail-open `catch` в `versioningRouter.ts`, заменив его на точную формулировку: ошибку запроса проглатывает **клиент** — из хука (`ObjectBrowserView.tsx:154`) деструктурируется только `data`, поэтому упавший скан на Deleted выглядит как «удалённого содержимого нет».
4. **П. 17** (`:347-361`) — статус `открыт`, дописать разблокировку: возражение «отсутствующая запись заставляет All показать, а дефолтная — скрыть» снято, так как вкладка All больше не читает ответ; во вкладке Deleted отсутствующая и дефолтная записи эквивалентны. Пометить, что дешёвый фикс стал допустимым, но требует отдельного PR (изменение контракта процедуры + серверные тесты + свой changeset).

**Verification:** номера строк в пп. 1, 10 совпадают с кодом после Шагов 1-2.

---

### Шаг 6 — Финальная проверка пакета

```bash
pnpm --filter @cobaltcore-dev/aurora typecheck
pnpm --filter @cobaltcore-dev/aurora lint
pnpm --filter @cobaltcore-dev/aurora test
pnpm format:check
```
Локализация не затрагивается (новых `t\`\``/`<Trans>` нет), но `pnpm check-i18n` входит в CI и должен остаться зелёным — диффа в `.po` быть не должно.

---

## Testing Plan

**Unit / component (`ObjectBrowserView.test.tsx`):**
- [ ] All: три папки, у всех `folderMarkerVersionId === undefined` → все три в таблице (3.1)
- [ ] All: папка с `isFolderDeleted: true` + `folderDeleteMarkerVersionId`, пришедшая в листинге → показана (3.2)
- [ ] All: папка с `isPartialScan: true` → показана (3.3)
- [ ] All: `folders: []` при статусе с `hasDeletedContent: true` → в таблице ничего, таблица отрендерена (3.4)
- [ ] All: `enabled` у `checkDeletedContent.useQuery` === `false` (3.5)
- [ ] Deleted: `enabled` === `true` (3.6)
- [ ] Не сломаны: `:708-730` (вход `prefix: ""`), `:732-776` и `:851-887` (Deleted), `:889-944` (форма входа), `:947-1060` (permissions), `:1062-1151`, `:1153-1228`

**Integration:** отдельные не нужны — сервер не меняется; `versioningRouter.test.ts:355-860` остаются актуальным контрактом для вкладки Deleted.

**Ручная проверка** (нужен версионированный бакет, наполненный **не** через Aurora; при недоступности eu-de-1 — `local-mock-backend/` или любой S3-клиент):
1. Открыть такой бакет → папки видны и остаются видны, мигания нет, счётчик в шапке совпадает с числом строк.
2. Зайти внутрь папки → объекты видны, поведение прежнее.
3. DevTools Network: при открытии вкладки All вызова `versioning.checkDeletedContent` нет (искать по имени процедуры в URL tRPC-батча); при переключении на Deleted — появляется.
4. Deleted: удалённые файлы и папки видны, бейдж «Deleted», Restore и Delete permanently работают как раньше.
5. Создать папку через «Create folder», положить файл, удалить файл → папка на All ведёт себя ожидаемо (пропадает, когда живого содержимого не остаётся, потому что `CommonPrefix` перестаёт приходить).
6. Бакет без версионирования: вкладок нет, регрессий нет.

---

## Acceptance Criteria

- [ ] В версионированном бакете, наполненном сторонним S3-клиентом, папки во вкладке All отображаются стабильно, без мигания и без «No objects found.»
- [ ] Папка, у которой delete-маркер стоит на пустышке при живом содержимом внутри, во вкладке All показана
- [ ] Счётчик в шапке (`objects-info-block`) совпадает с числом строк таблицы на вкладке All
- [ ] Папка, чьё содержимое целиком перекрыто delete-маркерами, во вкладке All не показывается (обеспечивается `ListObjectsV2`, закреплено тестом)
- [ ] `versioning.checkDeletedContent` не выполняется на вкладке All и выполняется на Deleted
- [ ] Вкладка Deleted не изменилась: список удалённых файлов и папок, бейджи, restore, permanent delete
- [ ] Тест, закреплявший сломанное поведение (`:649-706`), переписан; тест #1331 `:815-849` инвертирован с сохранением данных
- [ ] Сервер и контракт `checkDeletedContent` не изменены; поле `isPartialScan` сохранено
- [ ] Changeset `patch` для `@cobaltcore-dev/aurora` добавлен
- [ ] `DOCS/FOLLOW-UPS.md`: п. 28 закрыт, пп. 1, 10, 17 актуализированы
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck && lint && test` и `pnpm format:check` зелёные
- [ ] Регрессий в Swift-части storage нет (код не затронут)

---

## Open Questions

Блокирующих нет. Четыре решения приняты осознанно:
1. **`versioningStatus?.status === "Enabled"` в `enabled` не меняем** на `!== "Unversioned"` — на Suspended-бакете вкладка Deleted по-прежнему показывает все папки. Вторая половина follow-up 10, помеченного «делать вместе с п. 1».
2. **Ветка Deleted остаётся fail-open** (`return allFolders` при пустом `folderDeletedStatus`) — первая половина follow-up 10.
3. **`isPartialScan` в контракте `checkDeletedContent` сохраняем**, несмотря на отсутствие клиентских читателей после правки — потребитель появится при закрытии follow-up 1.
4. **Дешёвый фикс follow-up 17 не делаем**, хотя правка его разблокировала — это изменение контракта процедуры, отдельный PR.

Если решите взять пп. 1-2 в этот же PR — это ~10 строк в `ObjectBrowserView.tsx` плюс 2-3 теста, и follow-up 10 закрывается целиком; но изменение перестаёт быть чистым багфиксом по репорту пользователя, а bump, возможно, придётся поднять.

---

## Ключевые файлы (абсолютные пути)

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.tsx` — Шаги 1, 2
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Objects/ObjectBrowserView.test.tsx` — Шаг 3
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.changeset/ceph-all-tab-folders-visible.md` — Шаг 4 (создать)
- `/Users/kirylmishchuk/projects/SAP/DOCS/FOLLOW-UPS.md` — Шаг 5
- Только чтение: `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/versioningRouter.ts` (`:350-504`), `.../ceph/objectRouter.ts` (`:311-343`, `:1047-1075`), `.../Storage/types/versioning.ts` (`:130-186`), `.../Ceph/Objects/ObjectsTableView.tsx` (`:288-336`, `:570-645`), `.../Storage/constants.ts` (`S3_MAX_SCAN_PAGES`), `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.changeset/ceph-bounded-version-scans-and-delete-versions.md` (changeset #1331 — для абзаца «это не откат» в описании PR)
- Устарел, больше не нужен: `/private/tmp/claude-501/-Users-kirylmishchuk-projects-SAP-aurora-dashboard/d442ce68-3c50-4c36-9ff7-257d4069bf3b/scratchpad/repro-folders-vanish.test.tsx`

Коммитов, `git add`, push, PR и комментариев в GitHub не выполнялось и планом не предусмотрено. Рабочее дерево не изменялось: единственная выполненная команда с побочными эффектами — прогон тестов для baseline.
