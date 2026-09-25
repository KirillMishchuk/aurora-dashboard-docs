# Plan: PR #1331 — Copilot review findings, round 4

**Date:** 2026-09-25 · **Status:** not implemented — все находки вынесены в follow-up по решению пользователя 2026-09-25

> Это не план работ по #1331, а запись разбора. Четвёртый раунд Copilot на том же PR: 7 замечаний, **ни одно не чинится в #1331**. Три валидных уходят в follow-up (п. 8–10 сводного списка в файле раунда 1), одно — частично валидное и чинящее `main`, а не этот PR (п. 11), два — ложные срабатывания, одно — решение, принятое и задокументированное во втором раунде.
>
> Ветка `kiryl-s3-version-pagination`, HEAD `03144db3`, дерево чистое. Все семь находок перепроверены по живому коду в этой сессии; номера строк актуальны на `03144db3`. Ревью Copilot от 2026-09-25 07:15.
>
> Решение вынести всё в follow-up принято после оценки критичности: **ни одна из находок не ведёт к потере данных, утечке или повреждению состояния**. Худший исход (п. 3) — удалённый объект возвращается в All со старым содержимым; версия при этом не теряется, она и так лежала в истории.

---

## Сводка

| Copilot | Файл:строка | Вердикт | Куда |
| --- | --- | --- | --- |
| 1 | `BucketHeaderActions.tsx:80` | частично валидно — не регрессия PR, чинит `main` | follow-up 11 |
| 2 | `containerRouter.ts:296` | **ложное срабатывание** | ответ ревьюверу |
| 3 | `objectRouter.ts:934` | валидно | follow-up 8 |
| 4 | `objectRouter.ts:995` | валидно, низкая severity | follow-up 9 |
| 5 | `versioningRouter.ts:470` | **ложное срабатывание** | ответ ревьюверу |
| 6 | `ObjectBrowserView.tsx:361` | валидно, косметика | follow-up 10 (сливается с follow-up 1 раунда 1) |
| 7 | `invalidateBucketQueries.ts:69` | решение принято в раунде 2, задокументировано в коде | ответ ревьюверу |

---

## Разбор

### Находка 1 — `BucketHeaderActions.tsx:80`: Empty Bucket в обход `canDeleteVersions`

**Частично валидно. Механика верна, атрибуция — нет.**

Механика подтверждена: бакет из одних delete-маркеров → `EmptyBucketModal.tsx:77` (`isBucketEmptyWithVersions`) → `:121` (`shouldDeleteVersions`) → `:127` (`includeVersionsAndDeleteMarkers: true`), и попасть туда можно, имея только `storage:containers:empty`.

Неверно утверждение «whereas the dedicated action was gated by that permission». Тот же модал открывается из строки таблицы бакетов — `BucketTableView.tsx:255` (на `main` — `:257`), и там гейт **тоже только `canEmptyBucket`**; PR этот файл почти не трогал (−3 строки, гейт не менялся). Чекбокс «Also delete all versions and all delete markers» в обычной ветке модала (`EmptyBucketModal.tsx:298-303`) — тоже с `main` и тоже за одним `canEmptyBucket`. Путь был открыт до PR; изменение добавило вторую точку входа, убрав `!isBucketEmpty` из гейта меню в шапке.

Это не эскалация привилегий в строгом смысле: `cephProtectedProcedure` (`cephProcedure.ts:107`) проверяет только наличие Ceph-кредов. Серверного `canUser` на процедурах Ceph нет вообще — реально решает S3 ACL пользователя, а флаги `useCephPermissions` управляют только видимостью аффордансов.

**Severity: низкая.** → follow-up 11.

### Находка 2 — `containerRouter.ts:296`: abort-гонка в `getState`

**Ложное срабатывание.**

Ветка, на которую указывает Copilot, — `containerRouter.ts:300` (`if (!response.IsTruncated) break`). Если последняя страница доехала и она не truncated, скан дошёл до конца бакета: данные полные, `isPartialScan: false` — правда. Abort мог помешать только *следующему* запросу, а его нет. Ранний выход (`:296`, `hasOldVersionOrDeleteMarker && hasRealVersion`) тем более: оба флага доказаны положительными наблюдениями, недосмотренный хвост их не отменяет.

Вторая, независимая причина: `ctx.req.signal` — сигнал отменённого HTTP-запроса. Результат такого прогона не доставляется никому, Fastify его выбрасывает. Посылки «callers trust a result from an aborted run» не существует: вызывающего нет.

Предложенное лекарство сделало бы ответ **менее** точным — помечало бы заведомо полный скан как частичный.

### Находка 3 — `objectRouter.ts:929`: truncated без `NextKeyMarker` удаляет неполную группу

**Валидно.** Единственная находка раунда на разрушающем пути.

`objectRouter.ts:929` — `if (response.IsTruncated && response.NextKeyMarker && pageGroups.length > 0)`. При `IsTruncated: true` без `NextKeyMarker` отсрочка не срабатывает, последняя группа страницы попадает в `groupsToProcess` и удаляется на месте (`:954`, `:989`), хотя её хвост остался за границей страницы. `isPartial = true` ставится на `:1000` — уже после удаления.

**Уточнение к формулировке Copilot: опасен только один из двух случаев.**

- current-запись группы — обычная версия: удаляются только более старые версии, воскрешать нечего. Безопасно. S3 отдаёт записи ключа от новых к старым, поэтому `IsLatest` всегда в начале группы, т.е. на этой странице.
- current-запись — delete-маркер: удаляются маркер и видимые версии, за границей страницы остаётся более старая версия, она становится current — **объект воскресает живым со старым содержимым**.

**Ограничение на правку.** На текущее поведение есть намеренный тест — `objectRouter.test.ts:1469` «still deletes the last key's old versions when a truncated page carries no NextKeyMarker», с обоснованием «отсрочка уронила бы эти версии молча: ни удалены, ни в `errors`, а мутация всё равно резолвится успехом». Требования совместимы, и правка обязана сохранить оба: обрабатывать последнюю группу, как сейчас, когда current — обычная версия; пропускать её с записью в `errors` + `isPartial`, когда current — delete-маркер. Существующий тест при этом остаётся зелёным (в нём current — `v2`, обычная версия).

**Вероятность: очень низкая.** Требуется ответ RGW с `IsTruncated: true` без `NextKeyMarker` (нарушение спеки S3 — ветка чисто оборонительная, «Ceph RGW is not AWS»), **и** delete-маркер как current в последней группе страницы, **и** разрез этой группы границей страницы.

**Severity: средняя по последствию, очень низкая по вероятности.** Данные не теряются: воскресшая версия уже лежала в истории; лечится повторным удалением. → follow-up 8.

### Находка 4 — `objectRouter.ts:989`: `bulkDeleteItems` теряет прогресс прошлых страниц

**Валидно, низкая severity.** Описано точно.

`bulkDeleteItems` (`objectRouter.ts:196`) классифицирует сбой как systemic по своим **локальным** `deleted`/`errors` и бросает. `deleteNonCurrentVersions` зовёт её заново на каждой странице листинга (`:989`). Страница 1 удалила 500 версий → на странице 2 первый `DeleteObjects` падает систематически → хелпер видит пустые локальные массивы и бросает → мутация реджектится, клиент попадает в `onError` (`DeleteVersionsModal.tsx:104`), и ни `deletedCount: 500`, ни `isPartial: true` («запустите ещё раз») до пользователя не доходят. Ровно тот отчёт, ради которого раунды 1–3 и переписывали эту модалку.

Два других вызова хелпера (`:752` `deleteAll`, `:784` `deleteVersions`) зовут её однократно — там поведение корректно.

**Форма правки:** локально, в `deleteNonCurrentVersions` — обернуть вызов на `:989` в try/catch и при `deletedCount > 0` конвертировать бросок в `isPartial` + запись в `errors`; на первой странице по-прежнему бросать. Сигнатуру хелпера и два других call site'а трогать не нужно.

**Severity: низкая.** Данные не портятся, бакет приходит в то же состояние, инвалидация через `onSettled` отрабатывает, повторный запуск дочищает. → follow-up 9.

### Находка 5 — `versioningRouter.ts:470`: abort-гонка в `checkDeletedContent`

**Ложное срабатывание, ровно по логике находки 2.**

`versioningRouter.ts:470-471` — `if (!response.IsTruncated) { stoppedAtKey = undefined }`. Последняя страница префикса пришла, покрытие полное, `isPartialScan` по всем папкам корректно false. Abort снова мог помешать только несуществующему следующему запросу, а ответ отменённого запроса никому не уходит.

### Находка 6 — `ObjectBrowserView.tsx:358`: вкладка Deleted fail-open

**Валидно, косметика. Плюс более грубый случай, которого у Copilot нет.**

`ObjectBrowserView.tsx:358` — в ветке `tab === "deleted"` фолбэк `return allFolders`. При ошибке запроса (и пока он грузится) вкладка Deleted рисует **все** папки бакета, как будто в каждой есть удалённое: `isDeleted` не проставлен, versionId'ов для restore нет.

Само fail-open поведение — с `main`; PR повысил его достижимость, убрав серверный per-folder `catch` (на `main` — `versioningRouter.ts` ~478, молча возвращал `hasDeletedContent: false`) в пользу `throw mapS3ErrorToTRPCError`. Это уже зафиксировано как находка 1 раунда 3 и выведено в follow-up тогда же.

**Новое (найдено при разборе, Copilot не называл):** запрос `enabled` только при `versioningStatus?.status === "Enabled"` (`:164`), а вкладка Deleted рендерится при `status !== "Unversioned"` (`:654`). То есть **на Suspended-бакете вкладка Deleted показывает все папки всегда**, безо всякой ошибки и без рефетча. Тоже pre-existing.

**Почему косметика, а не опасность (проверено):** у ложно показанной папки нет разрушающих действий. Row-меню папки во вкладке Deleted гейтится `row.isDeleted` (`ObjectsTableView.tsx:580-581`), а в этом фолбэке `deletedFoldersList` возвращает `allFolders` немаппленными, поэтому `isDeleted === undefined` и меню не рендерится вовсе. Bulk-выделение тоже мимо: `selectableKeys` во вкладке Deleted берётся только из файлов (`:481`). Максимум — папка отрисована в списке и в неё можно провалиться.

**Severity: низкая.** → follow-up 10, сливается с follow-up 1 раунда 1 (видимость `isPartialScan` во вкладке Deleted) и находкой 1 раунда 3: один пробел, один дизайн, одна задача.

### Находка 7 — `invalidateBucketQueries.ts:69`: избыточная инвалидация

**Отклонить. Это принятое во втором раунде решение, задокументированное в самом коде.**

`invalidateBucketQueries.ts:26-30` объясняет отказ от per-call-site флага: единственный существовавший флаг в первый же день был проставлен неверно на четырёх из тринадцати call site'ов, причём дважды — для одной и той же мутации, вызываемой из двух модалок. `:55-68` разбирает конкретно `checkDeletedContent` и прямо называет `updateMetadata` единственным из тринадцати, который не способен его сдвинуть.

Довод Copilot'а про `EditMetadataModal` при этом бьёт мимо второй половины: `updateMetadata` — это `CopyObjectCommand`, и на версионированном бакете он пишет новую версию, то есть `containers.getState` (`hasOldVersionsOrDeleteMarkers`) сдвигает по-настоящему. Не инвалидировать его — вернуть ровно ту протухшесть, ради которой хелпер и заведён.

Фактическая поправка: инвалидация сама по себе запросов не шлёт — рефетч происходит только при активном обозревателе, а `checkDeletedContent` ограничен одним префиксом (в отличие от `getState`, который сканирует бакет).

---

## Follow-ups, заведённые этим раундом

Продолжают сквозную нумерацию списка «Follow-ups (вне этого PR)» в `2026-09-24-pr-1331-copilot-review-findings.md`.

**8. Не удалять неполную группу ключей, когда truncated-страница пришла без `NextKeyMarker`** (`objectRouter.ts:929`). Обрабатывать последнюю группу только если её current-запись — обычная версия; если current — delete-маркер, пропускать с записью в `errors` + `isPartial`. Обязательное условие: существующий тест `objectRouter.test.ts:1469` должен остаться зелёным — он закрывает противоположный риск (молча уронить версии). Нужен новый тест на delete-маркерный случай.

**9. `deleteNonCurrentVersions` теряет отчёт о прошлых страницах при systemic-сбое** (`objectRouter.ts:989` + `:196`). Обернуть постраничный вызов в try/catch, при `deletedCount > 0` отдавать `isPartial` + запись в `errors` вместо реджекта. Сигнатуру `bulkDeleteItems` не трогать — у двух других call site'ов вызов однократный и поведение корректно.

**10. Вкладка Deleted должна fail-closed** (`ObjectBrowserView.tsx:358`). Возвращать `[]` в ветке Deleted, нейтральный `allFolders` оставить только для All. Делать вместе с follow-up 1 (видимость `isPartialScan`) и находкой 1 раунда 3 (видимый UI состояния скана). Отдельно в ту же задачу: рассинхрон `enabled` запроса (`:164`, только `Enabled`) с условием показа вкладки (`:654`, `!== "Unversioned"`) — на Suspended-бакете вкладка Deleted показывает все папки всегда.

**11. Empty Bucket не должен запускать удаление версий без `storage:object_versions:delete`.** Прокинуть `canDeleteVersion` в `EmptyBucketModal` и закрыть им и авто-ветку `isBucketEmptyWithVersions` (`:77`, `:121`), и чекбокс (`:298-303`). Чинит `main`, а не изменение этого PR: те же ворота стоят на `BucketTableView.tsx:255`. Помнить, что серверной проверки прав на Ceph-процедурах нет вовсе (`cephProcedure.ts:107`) — это выравнивание аффордансов UI, не граница безопасности.

---

# Copilot reply texts (round 4, English, for manual posting)

**Thread `#discussion_r4102124712` — `BucketHeaderActions.tsx:80` (Empty Bucket / version-delete permission):**

> The mechanics are right, the attribution isn't, and it's tracked as a follow-up rather than fixed here.
>
> "whereas the dedicated action was gated by that permission" doesn't hold: the same modal opens from the bucket table row action at `BucketTableView.tsx:255` (`:257` on `main`), gated by `canEmptyBucket` alone, and this PR didn't change that gate. The "also delete all versions and delete markers" checkbox in the modal's ordinary branch is on `main` too, behind the same single permission. So the path was reachable before this PR; what changed here is a second entry point, because the header menu item lost its `!isBucketEmpty` condition.
>
> Worth stating explicitly: none of these flags are a security boundary. `cephProtectedProcedure` (`cephProcedure.ts:107`) only requires Ceph credentials — there is no server-side `canUser` check on any Ceph procedure, so what actually decides is the user's S3 ACL. `useCephPermissions` governs affordance visibility only.
>
> Tracked as a follow-up because the fix belongs to `main`'s gating, not to this change set: pass the version-delete permission into the modal and gate both the automatic `isBucketEmptyWithVersions` branch and the checkbox.

**Thread `#discussion_r4102124762` — `containerRouter.ts:296` (abort race in `getState`):**

> I don't think this one holds.
>
> The branch is `containerRouter.ts:300`, `if (!response.IsTruncated) break`. If that final page resolved and is not truncated, the scan did reach the end of the bucket — the data is complete and `isPartialScan: false` is accurate. An abort can only prevent a *subsequent* request, and there is none. The early exit at `:296` is safer still: both flags are set by positive observations, which an unread tail cannot retract.
>
> Independently of that: `ctx.req.signal` is the aborted HTTP request's signal. The result of such a run is delivered to nobody — Fastify discards it. There is no caller to be misled.
>
> Applying the suggested check would make the answer less accurate, by reporting a demonstrably complete scan as partial.

**Thread `#discussion_r4102124797` — `objectRouter.ts:934` (truncated page without `NextKeyMarker`):**

> Valid, and the sharpest finding of this round. Tracked as a follow-up.
>
> One refinement: only one of the two shapes is dangerous. S3 returns a key's records newest-first, so `IsLatest` is always at the head of the group, i.e. on this page. If the current record is an ordinary version, only older versions get deleted and nothing can be resurrected. The damage is confined to the case where the current record is a delete marker: the marker and the visible versions go, an older version beyond the page boundary survives and becomes current, and the object comes back live with stale content.
>
> The fix is constrained by an existing deliberate test, `objectRouter.test.ts:1469`, which pins the opposite risk — deferring that group would drop those versions silently, neither deleted nor reported in `errors`, with the mutation still resolving as success. Both requirements are satisfiable: process the last group as today when its current record is an ordinary version, skip it with an `errors` entry plus `isPartial` when the current record is a delete marker. That test stays green.
>
> Not fixed in this PR because it rewrites the condition that test is built around and needs a new test of its own, and the trigger is a spec-violating RGW response (`IsTruncated: true` with no `NextKeyMarker`) combined with a delete-marker-current group split across a page boundary. No data is lost when it does fire — the resurrected version was already in the history.

**Thread `#discussion_r4102124827` — `objectRouter.ts:995` (`bulkDeleteItems` per-page systemic failure):**

> Accurate, and tracked as a follow-up.
>
> `bulkDeleteItems` (`objectRouter.ts:196`) classifies a failure as systemic from its own local `deleted`/`errors`, and this mutation calls it once per listing page, so a page-2 failure after a successful page 1 throws with empty local arrays. The mutation rejects, the modal takes `onError`, and neither the prior `deletedCount` nor `isPartial: true` — the "run it again" half — reaches the user. That is exactly the report the previous rounds rebuilt this modal around.
>
> The remedy stays local to `deleteNonCurrentVersions` rather than touching the helper's signature: wrap the per-page call, and when `deletedCount > 0` convert the throw into `isPartial` plus an `errors` entry, while a first-page systemic failure still throws. The helper's other two call sites (`deleteAll`, `deleteVersions`) invoke it once and are correct as they are.
>
> Deferred because it is a reporting defect, not a behavioural one: the bucket ends in the same state either way, `onSettled` still invalidates, and a re-run finishes the job.

**Thread `#discussion_r4102124859` — `versioningRouter.ts:470` (abort race in `checkDeletedContent`):**

> Same as the `getState` one — I don't think it holds.
>
> `versioningRouter.ts:470-471`, `if (!response.IsTruncated) { stoppedAtKey = undefined }`: the final page of the prefix arrived, so coverage is complete and `isPartialScan: false` is correct for every folder. The abort could only have prevented a next request that doesn't exist, and the response of an aborted request is never delivered to a caller.

**Thread `#discussion_r4102124911` — `ObjectBrowserView.tsx:361` (Deleted tab fail-open):**

> Valid, and already tracked — this is the same gap as finding 1 of the previous round, which was moved to a follow-up then.
>
> Two additions from re-checking it. First, a worse trigger than the error path: the query is `enabled` only when the status is `Enabled` (`:164`), while the Deleted tab renders whenever the status is not `Unversioned` (`:654`). On a Suspended bucket the tab therefore lists every folder unconditionally, with no error and no refetch involved.
>
> Second, the blast radius is smaller than it looks: a falsely listed folder carries no destructive affordance. Its row menu is gated on `row.isDeleted` (`ObjectsTableView.tsx:580-581`), and in this fallback `deletedFoldersList` returns `allFolders` unmapped, so `isDeleted` is `undefined` and no menu renders. Folders aren't bulk-selectable in that tab either (`:481` builds `selectableKeys` from files only). The result is visual and navigational confusion, not a destructive path.
>
> The follow-up covers all of it together: fail closed in the Deleted branch, keep the neutral fallback for All, surface scan failure and `isPartialScan` in the browser, and align the query's `enabled` condition with the tab's render condition.

**Thread `#discussion_r4102124953` — `invalidateBucketQueries.ts:69` (unconditional invalidation):**

> This is a decision taken in round 2 and documented in the file itself.
>
> `invalidateBucketQueries.ts:26-30` records why the per-call-site flag was dropped: the one flag that existed was answered incorrectly at four of thirteen call sites on its first day, twice for the same mutation invoked from two different modals. `:55-68` addresses `checkDeletedContent` specifically and already names `updateMetadata` as the only one of the thirteen that cannot move it.
>
> The `EditMetadataModal` argument misses the other half, though: `updateMetadata` is a `CopyObjectCommand`, and on a versioned bucket it writes a new version, which flips `hasOldVersionsOrDeleteMarkers` — so it moves `containers.getState` for real. Skipping that invalidation would reintroduce exactly the staleness the helper exists to prevent.
>
> One factual correction: invalidation does not issue requests by itself — a refetch happens only where an observer is mounted. And `checkDeletedContent` is scoped to a single prefix, where `getState` scans the whole bucket, which is why making the cheaper, narrower query the opt-in one had it backwards.
