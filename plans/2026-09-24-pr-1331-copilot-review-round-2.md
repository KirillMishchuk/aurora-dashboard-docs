# Plan: PR #1331 — Copilot review findings, round 2

**Date:** 2026-09-24 · **Status:** implemented 2026-09-24

> **Реализовано 2026-09-24.** Все 6 шагов выполнены, 13 файлов в репо + `DOCS/descriptions/pr-1331-description.md`, ничего не закоммичено. Семь CI-джоб зелёные (aurora 5728 тестов, signal-openstack 177, policy-engine 320 + 1 skipped), `.po` без диффа. Регрессия подтверждена по всем фиксам, включая инверсную проверку шага 3 (с применённым лекарством Copilot новый тест краснеет, существующий `objectRouter.test.ts:1538` — нет).
>
> **Два отклонения по ходу**, оба пойманы существующими гейтами и починены точечно: `check-i18n` дал дифф в `.po`, потому что первая версия тела error-исхода использовала параметр `detail` вместо `errorMessage` (msgid сменился — переименовано обратно); `lint` выдал `lingui/no-expression-in-message` на `{bucket.name}`/`{outcome.detail}` внутри `<Trans>` — вынесено в компонент с плоскими пропсами без изменения msgid.
>
> **Одна правка сверх плана — по итогам security-прохода (Low).** Пункт 4.6 в исполненном виде оказался неполным: `disableCancelButton`/`disableCloseButton` гасят только отрисованные контролы, а Esc-обработчик juno `Modal` привязан к `closeable && closeOnEsc` и этих пропсов не смотрит вовсе — то есть одним нажатием Esc отчёт о частичном/неуспешном прогоне всё ещё можно было выбросить, ровно тот сценарий, ради которого пункт 4.6 и добавлялся. Проверено по исходнику на теге `@cloudoperators/juno-ui-components@9.4.0` (`handleEsc` → `if (isCloseable && isCloseableOnEsc)`), не по `juno/main`. Добавлен `closeOnEsc={!isPending}` плюс два теста (Esc игнорируется при `isPending`, Esc закрывает при обычном состоянии — второй нужен, чтобы первый не проверял заведомо мёртвый путь). `closeable={false}` отвергнут: он не дизейблит, а размонтирует футер и иконку закрытия вместе с кнопкой подтверждения.
>
> **Triple-review, два прохода (2026-09-24).** Первый проход по 13 файлам: security 0, performance 2 (одна ложная — `refetchOnWindowFocus` уже выключен глобально в `App.tsx:56`; одна отклонена — поднятие `staleTime` вернуло бы окно для внешних изменений), architecture 8. Закрыты: расползание паттерна (`EmptyBucketModal` приведён к модели `DeleteVersionsModal`, `DeleteBucketModal` сознательно оставлен на тостах), гарды закрытия во всех трёх модалках, развязка `S3_MAX_BUFFERED_VERSIONS_PER_KEY` от `S3_MAX_SCAN_PAGES`, неточность changeset, мелочи.
>
> Второй проход по 22 файлам: security 0, performance 1 High, architecture 6. **Главная находка — дефект, внесённый правкой первого прохода**, найден performance и architecture независимо и подтверждён по коду: `onSettled` у `EmptyBucketModal` инвалидирует `containers.getState`, на который сама модалка подписана активным обозревателем, поэтому рефетч стартует сразу после `setMutationError`; `isLoading`, включающий `isFetching`, подменял отчёт спиннером, а после разрешения рефетча частично удавшийся отказ мог перевести бакет в ветку `isTrulyEmpty`, которая отчёта не рендерила вовсе — сообщение пропадало безвозвратно. Ровно то, ради чего затевался inline-отчёт. Починено тремя частями: `isLoading = isLoadingBucketState || (isFetchingBucketState && !mutationError)`, общий `EmptyBucketErrorMessage` во всех трёх ветках, заголовок по ветке (`Failed to Delete Versions` там, где кнопка называется так же). Плюс закрыты: необоснованная асимметрия `DeleteBucketModal` (комментарий в коде + changeset + описание PR), недоделанный B.10 в `ObjectBrowserView` (три оставшихся inline-тоста переведены на хелперы, минус 4 msgid), причина блокировки закрытия в changeset разделена по модалкам.
>
> Итог: 22 файла, 7/7 CI-джоб зелёные (aurora 5728 тестов), каждая правка подтверждена откатом. Осталось за пользователем: перезалить тело PR — оно отстало от `DOCS/descriptions/pr-1331-description.md` на 8 блоков (сверено после нормализации CRLF).
>
> Критических и High-находок в security-проходе нет. Утечки сырого `error.message` из SDK не прибавилось — тот же текст, что рендерил удалённый тост, просто в другом месте (остаётся follow-up первого раунда).

# 📋 IMPLEMENTATION PLAN: PR #1331 — Copilot review, round 2

**Ветка:** `kiryl-s3-version-pagination`, HEAD `0f992593`, дерево чистое. Первый раунд (`/Users/kirylmishchuk/projects/SAP/DOCS/plans/2026-09-24-pr-1331-copilot-review-findings.md`, статус implemented) прочитан — раунд 2 частично **откатывает** его Шаг 5.

Все пять находок перепроверены по живому коду в этой сессии. Строки/факты ниже актуальны на `0f992593`. Пять уточнений к брифу помечены **[уточнение]** — ни одно не меняет решений, но два меняют содержание шагов (Шаг 3: в `deleteNonCurrentVersions` **нет** потолка страниц; Шаг 4: `Message.title` — это `string`, не `ReactNode`).

---

## Overview

Закрываем второй раунд Copilot на PR #1331 (файл-описание: `/Users/kirylmishchuk/projects/SAP/DOCS/descriptions/pr-1331-description.md`):

1. Две деструктивные модалки (`DeleteBucketModal`, `EmptyBucketModal`) рендерят решение по **закэшированному** ответу `containers.getState`, хотя обе в комментариях объявляют себя live-проверкой. Один общий однострочный фикс (`isFetching`) закрывает обе находки (1, 2).
2. `EmptyBucketModal` показывает три самодельных error-баннера без `role="alert"`/`aria-live="assertive"` — меняем на `<Message>` по форме, уже устоявшейся в соседних модалках (находка 5).
3. `objectRouter.deleteNonCurrentVersions` — лекарство Copilot отклоняем (оно превратило бы переполненный ключ в вечно нечистимый), но док константы действительно врёт: правим док + комментарий + добавляем недостающий тест (находка 3). Поведение кода не меняется.
4. `DeleteVersionsModal` — переносим отчёт о неуспехе из тоста во внутримодальный `<Message variant="error">`, модалка остаётся открытой при неуспехе. Это **признанный откат** решения раунда 1, принятого на неверном основании (находка 4).

---

## Architecture Analysis

### Current state (проверено)

**Клиент** — всё под `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/`:

- `Buckets/DeleteBucketModal.tsx:34-41` — `getState.useQuery(..., { enabled: isOpen && bucket !== null, staleTime: 0 })`, берёт только `data/isLoading/error`. `isLoading` = `isPending && isFetching`; при прогретом кэше `isPending === false`. Гейты: `cannotDelete` (`:113-116`), `disableConfirmButton` (`:144-146` — уже содержит `isLoading`), выбор ветки (`:153`).
- `Buckets/EmptyBucketModal.tsx:49-64` — тот же запрос, те же три поля. Флаги веток `:74-79`, решение мутации `:117` (`shouldDeleteVersions = isBucketEmptyWithVersions || deleteVersionsAndMarkers`), `isLoading = isLoadingBucketState` (`:143`), ветки `:147` / `:192` / `:225`. `disableConfirmButton` обычной ветки (`:235`) — **без** `isLoading`.
- `hooks/useBucketInfo.ts:93-101` — **тот же** `containers.getState` с тем же входом и `staleTime: 30 * 1000`, живёт в шапке бакета всё время. Собственный комментарий: «the modals that need emptiness query `getState` themselves and hit the same cache entry». ⇒ кэш почти всегда прогрет, `isLoading === true` реально только при первом открытии.
- `client/App.tsx:52-56` — `staleTime: 60_000`, **`refetchOnWindowFocus: false`** (важно: спонтанных рефетчей от переключения окна не будет).
- `Buckets/DeleteVersionsModal.tsx` — `onSettled` (`:42-46`) безусловно `invalidateBucketQueries(utils)` + `handleClose()`; классификация исходов в `mutate.onSuccess` (`:81-102`) с большим комментарием про независимость `errorCount` и `isPartial`; `onPartial` — обязательный проп (`:18`).
- `Buckets/BucketToastNotifications.tsx` — `getVersionsDeletedToast` (`:151`), `getVersionsDeleteErrorToast` (`:167`), `PartialVersionDeleteOutcome` (`:185-192`), `MAX_LISTED_DELETE_ERRORS = 3` (`:195`), `getVersionsPartiallyDeletedToast` (`:197-250`, `id: versions-partial-${bucketName}`, `duration: Infinity`).
- `Buckets/BucketModals.tsx:204-228` — три колбэка → `toast.success` / `toast.error` / `toast.warning`; импорты `:22-24`.
- **Поверхность экспорта** (проверено grep’ом): `DeleteVersionsModal` реэкспортируется только из `Buckets/index.tsx:43`, и **никто** не импортирует его из этой бочки (импортёры бочки берут только `CephBuckets`, `CephCorsRules`, `CephLifecycleRules`). В `client/index.ts` его нет. ⇒ менять пропсы безопасно, `packages/aurora/README.md` не трогаем.

**Сервер:**

- `packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:929-952` — проверка `deferredGroup.items.length > S3_MAX_BUFFERED_VERSIONS_PER_KEY` внутри `if (response.IsTruncated && response.NextKeyMarker && pageGroups.length > 0)`; `pendingItems` присваивается в `else`.
- `packages/aurora/src/server/Storage/constants.ts:35-45` — док + `S3_MAX_BUFFERED_VERSIONS_PER_KEY = S3_MAX_SCAN_PAGES * S3_MAX_KEYS_PER_REQUEST` (20 × 1000 = 20 000). Константа **не** экспортируется из `server/index.ts` — публичного контракта на ней нет.
- **[уточнение 1, важно]** цикл `deleteNonCurrentVersions` (`:857-1025`) **не имеет** потолка `S3_MAX_SCAN_PAGES` (в отличие от `containers.getState` и `checkDeletedContent`): он сканирует до конца бакета, а единственная защита от разрастания — буфер на ключ и `MAX_SAME_MARKER = 5`. Значит тест из шага 3 на 21 страницу не упрётся в потолок — сценарий воспроизводим.
- **[уточнение 2]** точная граница поведения: проверка применяется только к **отложенной** группе. Ключ обрабатывается, если к моменту, когда он перестал быть отложенным (последняя страница, либо `NextKeyMarker` указал на другой ключ), накопилось ≤ 20 000 + вклад текущей страницы ≤ 1000. Ключ отбрасывается, если, оставаясь отложенным, он перевалил 20 000 (т.е. на 21-й подряд странице одного ключа). Пик — ровно 21 000 записей, константа.

**Правила репо** (`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.github/copilot-instructions.md`, прочитаны):

- B.11 `:415-416` — «On success: … (modal) close and show a confirming toast»; «Distinguish failures: validation errors stay inline and keep the form open; server-side errors show a `Message` at form top (or inside the modal)…». Это и есть предписанный паттерн находки 4.
- B.5 `:245` — «No redundant confirmation `Message` inside a modal… **Operation/validation errors are still allowed and should use `variant="error"`**».
- B.14 `:455`, Reject `:295`, чек-лист `:51` — error-элемент обязан нести `role="alert"` + `aria-live="assertive"`.
- B.16 `:497` (CRUD-подтверждение → toast), `:504` («Error that requires user attention/action → `<Message variant="error">` (not a toast)»), `:506` (title только для заметных/многопредложенных), `:507` (вариант `Message` в модалке должен совпадать с primary-кнопкой), Reject `:509`.
- Reject `:41` — «Modal without `disableCancelButton`/`disableCloseButton` during async operations» (см. Шаг 4.6).

**[уточнение 3]** `MessageProps extends HTMLAttributes<HTMLDivElement>` и сигнатура `({title, variant, dismissible, autoDismiss, autoDismissTimeout, onDismiss, className, ...props})` — подтверждено по `@cloudoperators/juno-ui-components@9.4.0/build/components/Message/Message.component.d.ts`: `role`/`aria-live`/`data-testid` проходят через `...props`, сам компонент их не ставит. **`title?: string`** — не `ReactNode`: заголовок надо передавать как `` t`…` ``, не `<Trans>`.

**[уточнение 4]** `packages/aurora/lingui.config.ts` использует `formatter({ origins: false })` — в `.po` нет ссылок `file:line`. ⇒ сдвиг строк ничего не ломает, диффа `.po` от шагов 1–3 не будет вообще; от шага 4 — только если изменится сам текст (см. Шаг 4.7).

### Proposed changes (высокоуровнево)

- Клиент: один флаг (`isFetching`) в двух модалках; три `div` → `<Message>`; перенос отчёта о неуспехе `DeleteVersionsModal` из тоста в `<Message>` + удаление двух тост-хелперов и типа.
- Сервер: только док-комментарии + один тест. Ни одной строки исполняемого кода.

---

## Potential Problems & Mitigations

| Риск | Severity | Митигация |
| --- | --- | --- |
| ⚡ **Принятая цена шагов 1–2:** каждое открытие обеих модалок теперь ждёт живой `getState` (GetBucketVersioning + ListObjectsV2 MaxKeys:1 + до 20 страниц истории — секунды на большой истории) вместо мгновенного рендера по кэшу. | Medium | Это **принятое решение, а не побочный эффект**: оба файла уже декларируют live-проверку в комментариях (`DeleteBucketModal.tsx:30-33`, `EmptyBucketModal.tsx:60-61`), код просто не выполнял декларацию. Для деструктивного pre-check спиннер строго лучше устаревшего решения. Зафиксировать формулировкой в ответе Copilot и в PR-описании. |
| ⚠️ Фоновый рефетч того же ключа (например, после `invalidateBucketQueries`) при открытой модалке переключит `isFetching` → модалка мигнёт в прогресс-ветку. | Low | `refetchOnWindowFocus: false` (App.tsx:56) убирает главный источник «случайных» рефетчей. В `EmptyBucketModal` инвалидация приходит в `onSettled` мутации, которая тут же закрывает модалку; в `DeleteBucketModal` `getState` не инвалидируется вовсе. Остаточный случай (действие из шапки бакета при открытой модалке) — безопасное направление: спиннер, а не устаревшее решение. |
| 🔴 Шаг 4 меняет пропсы `DeleteVersionsModal` (убираются `onError`, `onPartial`). | Low | Проверено grep’ом: единственный потребитель — `BucketModals.tsx`; реэкспорт из `Buckets/index.tsx:43` ни разу не импортируется; в `client/index.ts` компонента нет. Публичный контракт `AuroraApp` не затронут, `packages/aurora/README.md` не меняется. |
| ⚠️ Шаг 4: модалка остаётся открытой во время in-flight мутации, и её сейчас **можно закрыть** — отчёт будет потерян молча (раньше это было безвредно: модалка всё равно закрывалась). | Medium | Добавить `disableCancelButton={isPending}` + `disableCloseButton={isPending}` (Шаг 4.6). Это Reject-пункт `:41` и B.5; замечание Copilot его не называет, поэтому шаг помечен как «найдено при планировании» — при желании выносится в follow-up (Open Question 2). |
| ⚠️ Тест-моки `useQuery` в обеих модалках не отдают `isFetching` (`DeleteBucketModal.test.tsx:99-108`, `EmptyBucketModal.test.tsx:119-127`). | Low | `undefined` → falsy, существующие кейсы не поедут. Моки всё равно расширяем управляемым полем, иначе новые кейсы не написать. |
| ⚠️ Тест шага 3 создаёт 21 страницу × 1000 записей (≈21 000 объектов) и ~21 вызов DeleteObjects. | Low | Прецедент уже в репо: `objectRouter.test.ts:1538` делает ровно это. Использовать `mockSend.mockImplementation` с ветвлением по `command.input.Delete` и эхом `Deleted: command.input.Delete.Objects`, а не цепочку `mockResolvedValueOnce`. |
| ⚠️ B.5 формально запрещает лишний `Message` в деструктивной модалке. | Low | Оговорка `:245` разрешает operation/validation errors с `variant="error"`; primary — `primary-danger`, конфликта вариантов по `:507` нет, потому что единственный допустимый вариант здесь — `error`. |
| ⚠️ `toast.warning` для частичного исхода **нельзя** просто переложить в `Message variant="warning"`. | Medium | B.16 `:507`: вариант `Message` обязан совпадать с вариантом primary-кнопки, и единственное исключение — `error`. Оба неуспешных исхода внутри модалки идут `variant="error"` и различаются **заголовком и текстом**, а не цветом. Иначе будет третий раунд. |
| ⚠️ Changeset содержит утверждение про «warning notification that stays on screen until dismissed», которое шаг 4 делает ложным. | Medium | Шаг 5: правим существующий файл (рекомендация ниже). |
| 🔒 Ни одна правка не трогает auth, скоупинг токена, policy-ключи или input-схемы. | — | Permission-работ нет. |
| ⚠️ Аналитика: после неуспешного прогона `markSubmitted()` уже вызван, поэтому ручное закрытие модалки не даст события `.close`. | Low | Семантически корректно (пользователь действительно сабмитил); тест `"does not track .close event on successful submit"` остаётся валидным. Зафиксировать в плане, чтобы не приняли за баг. |

---

## Prerequisites

- [x] Ветка `kiryl-s3-version-pagination` на `0f992593`, дерево чистое.
- [x] Первый раунд прочитан; откатываемое решение локализовано (Шаг 5 прошлого плана).
- [ ] Решить Open Question 1 (changeset: дополнить vs новый) и Open Question 2 (`disableCancelButton` — в PR или follow-up) — обе с рекомендацией по умолчанию, работы не блокируют.

---

## Implementation Steps

Порядок: Шаг 1 → Шаг 2 (оба в одном файле `EmptyBucketModal.tsx`, поэтому подряд) → Шаг 3 (независим) → Шаг 4 (самый крупный) → Шаг 5 (артефакты релиза/описания, только после 1–4) → Шаг 6 (CI-гейт, последним). Шаг 3 можно делать параллельно с 1/2/4 — пересечений по файлам нет.

---

### Шаг 1 — Считать фоновый рефетч загрузкой в обеих pre-check модалках (находки 1 + 2)

**Файлы:**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/DeleteBucketModal.tsx`
- `.../Ceph/Buckets/EmptyBucketModal.tsx`
- `.../Ceph/Buckets/DeleteBucketModal.test.tsx`
- `.../Ceph/Buckets/EmptyBucketModal.test.tsx`

**Что сделать:**

1. `DeleteBucketModal.tsx:34-41` — добавить `isFetching: isFetchingBucketState` в деструктуризацию `useQuery`. На `:118` заменить `const isLoading = isLoadingBucketState` на:

   ```ts
   // `isLoading` alone is `isPending && isFetching`, and `isPending` is false whenever the
   // cache already holds an entry — which it almost always does here, because the bucket
   // header's `useBucketInfo` keeps the very same `getState` query warm with a 30s staleTime.
   // Rendering the verdict off that entry defeats the point of `staleTime: 0`: this modal is
   // a live pre-delete check, so a refetch in flight means "not known yet", not "known".
   const isLoading = isLoadingBucketState || isFetchingBucketState
   ```

2. `EmptyBucketModal.tsx:49-64` — то же самое; на `:143` заменить `const isLoading = isLoadingBucketState` на `isLoadingBucketState || isFetchingBucketState` с аналогичным (более коротким) комментарием, дополнительно называющим причину: «здесь нет страховки со стороны S3 — ветка `isBucketEmptyWithVersions` форсит `includeVersionsAndDeleteMarkers: true` без чекбокса (`:117`, `:147`)».
3. `EmptyBucketModal.tsx:235` — в `disableConfirmButton` обычной деструктивной ветки добавить `|| isLoading`:

   ```ts
   disableConfirmButton={emptyBucketMutation.isPending || isLoading || confirmName.trim() !== bucket.name || hasQueryError}
   ```

   Сейчас эта ветка спасается только косвенно (пока `isLoading`, `TextInput` не отрендерен, `confirmName` пуст) — делаем гарантию явной, как уже сделано в `DeleteBucketModal.tsx:145`.
4. `DeleteBucketModal.tsx` — ничего больше не менять: `disableConfirmButton` (`:144-146`) уже читает `isLoading`, ветка `:153` тоже.

**Почему одним шагом:** это один и тот же дефект в двух копиях, фикс идентичен, и находка 1 чинится «за компанию» ради консистентности — самостоятельного ущерба там нет (`cannotDelete` — предварительный UX-гейт, непустой бакет всё равно отобьётся S3 с `BucketNotEmpty`).

**Тесты:**

- `DeleteBucketModal.test.tsx`: расширить `mockState` полем `isFetchingBucketState` (дефолт `false`, сбрасывать в `beforeEach` рядом с `:170`) и вернуть его из мока `useQuery` (`:99-108`). Новый кейс:
  «shows the progress state while a background refetch of the bucket state is in flight» — `{ data: <непустое состояние>, isLoading: false, isFetching: true }` → в документе есть `Checking Bucket Contents...`, confirm-кнопка задизейблена, список причин `cannotDelete` не отрендерен.
- `EmptyBucketModal.test.tsx`: то же для `mockBucketStateQuery` (`:119-127`, сброс рядом с `:202`). Новый кейс:
  «does not render the delete-versions branch off a stale cache entry» — `{ data: { isEmpty: true, hasOnlyDeleteMarkers: true, hasOldVersionsOrDeleteMarkers: true, isPartialScan: false, status: "Enabled" }, isLoading: false, isFetching: true }` → рендерится прогресс-ветка (`Checking Bucket Contents...`), заголовка `Delete Versions` **нет**, confirm задизейблен.

**Expected outcome:** ни одна из двух модалок больше не может принять решение (и уж тем более форсировать полный wipe) по данным, которые в этот момент перепроверяются.

**Verification:**
`pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/DeleteBucketModal.test.tsx src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/EmptyBucketModal.test.tsx`
**Регрессия:** временно вернуть `const isLoading = isLoadingBucketState` в каждом файле по отдельности и убедиться, что краснеет ровно соответствующий новый кейс.

---

### Шаг 2 — Три error-баннера `EmptyBucketModal` → `<Message>` (находка 5)

**Файлы:** `.../Ceph/Buckets/EmptyBucketModal.tsx` (строки `:161-165`, `:209-214`, `:241-245` — после шага 1 сдвинутся), при необходимости `EmptyBucketModal.test.tsx`.

**Что сделать:**

1. Добавить `Message` в импорт из `@cloudoperators/juno-ui-components` (`:4-13`).
2. Заменить каждый из трёх блоков вида
   `<div className="bg-theme-danger-10 text-theme-danger rounded p-4"><Trans>…</Trans></div>`
   на:

   ```tsx
   <Message variant="error" role="alert" aria-live="assertive" data-testid="empty-bucket-state-error">
     <Trans>Unable to verify bucket versioning status and contents. Try again.</Trans>
   </Message>
   ```

   Во втором вхождении (ветка `isTrulyEmpty`) сохранить существующий JSX-комментарий «One query now answers both…» внутри `<Message>`.
3. Строго соблюсти три ограничения (все три — Reject-пункты, если нарушить):
   - `role`/`aria-live` передаём **явно** — juno `Message` их не ставит (подтверждено по d.ts и бандлу 9.4.0);
   - **без** `dismissible` — баннер отражает живое состояние запроса, сбрасывать нечем; `dismissible` без `onDismiss` — отдельный Reject (B.16 `:509`);
   - **без** `title` — B.16 `:506`, сообщение односложное.
4. Класс `bg-theme-danger-10 text-theme-danger rounded p-4` после этого во всём клиенте не остаётся (он встречался только в этих трёх местах) — проверить `grep -rn "bg-theme-danger-10" packages/aurora/src/client`.

**Образцы в репо** (следовать им буквально): `.../Ceph/Buckets/CreateBucketModal.tsx:176-185`, `.../Ceph/Objects/CreateFolderModal.tsx:123-132`, `.../Swift/Objects/CreateFolderModal.tsx:137-146`, `.../Swift/Containers/CreateContainerModal.tsx:137-146`.

**Границы (не расширять):** `DeleteBucketModal.tsx:149-151` рендерит ошибку как `<Status status="error" title={t`Failed to Check Bucket Contents`}>` тоже без `role` — проверено `git diff main...HEAD`: блок пришёл из `main`, PR его не трогал, а `Status` — санкционированный B.16 компонент для секционных ошибок. Оставить, вынести в follow-up.

**i18n:** текст строки не меняется, `msgid` тот же; `origins: false` в `lingui.config.ts` ⇒ `pnpm check-i18n` по этому шагу — чистый no-op, `.po` не должны измениться ни на строку.

**Тесты:** отдельный кейс не обязателен (текущая сюита баннер не проверяет), но дешевле всего добавить один: `mockBucketStateQuery.error = { message: "boom" }` → `screen.getAllByTestId("empty-bucket-state-error")[0]` имеет `role="alert"` и `aria-live="assertive"`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test …/EmptyBucketModal.test.tsx`; `git diff -- packages/aurora/src/locales` пуст.

---

### Шаг 3 — `S3_MAX_BUFFERED_VERSIONS_PER_KEY`: чиним документ и покрытие, не поведение (находка 3)

Лекарство Copilot (безусловная проверка сразу после слияния + отбрасывание ключа) **отклоняем**. Кода не меняем.

**Файлы:**

- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/constants.ts:35-45`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:929-935`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.test.ts`

**(а) Переписать док константы** так, чтобы он описывал настоящую гарантию. Должен содержать все четыре утверждения:

- предел ограничивает буфер, **переносимый между страницами** (`pendingItems`), а не пиковую занятость;
- фактический пик — `S3_MAX_BUFFERED_VERSIONS_PER_KEY + S3_MAX_KEYS_PER_REQUEST` (21 000 записей), константа: она не растёт ни с размером бакета, ни с числом страниц, потому что вклад страницы нельзя оценить, не прочитав её — записи уже в куче к моменту любой проверки;
- группа, дочитанная до конца, обрабатывается независимо от размера: все записи ключа в руках, решение корректно, удаление безопасно;
- отказ от такой группы был бы **невосстановимым** отказом в обслуживании: ключ на 20 001+ версий перестал бы чиститься навсегда — каждый повторный запуск упирался бы в тот же предел и возвращал `TooManyVersions`. А это ровно профиль ключа, ради которого константа заведена (её же текст: «a CI artifact, a rolling log»).

Фразу «Past this many records the group is abandoned rather than buffered» заменить на точную: группа отбрасывается тогда и только тогда, когда, **оставаясь отложенной**, превышает предел.

**(б) Добавить тест**, закрепляющий намерение — сейчас этот путь не покрыт, именно поэтому находка выглядит убедительно. Рядом с `objectRouter.test.ts:1538` («abandons a key whose versions overflow the buffer»):

- имя: `"processes a key that overflows the buffer only on its final page"`;
- форма: 20 усечённых страниц по `S3_MAX_KEYS_PER_REQUEST` записей одного ключа (`IsTruncated: true`, `NextKeyMarker: "hot-key"`) → перенос ровно 20 000, предел не превышен; 21-я страница — `IsTruncated: false` с ещё 1000 записями того же ключа ⇒ слитая группа 21 000 обрабатывается, потому что ветка проверки на последней странице вообще не исполняется;
- одна запись группы должна нести `IsLatest: true` и **не** быть delete-маркером, иначе группа уйдёт в `NoCurrentVersion`;
- мок: `mockSend.mockImplementation((command) => command.input?.Delete ? Promise.resolve({ Deleted: command.input.Delete.Objects, Errors: [] }) : <страница>)` — цепочка `mockResolvedValueOnce` здесь не годится, DeleteObjects вызовется ~21 раз;
- утверждения: `result.deletedCount > 0` (точнее — `20_999`), `result.errors.some(e => e.code === "TooManyVersions") === false`, `result.isPartial === false`;
- комментарий в теле теста: «дочитанная группа обрабатывается по размеру ключа, а не по размеру буфера; предел стережёт перенос между страницами».

**[уточнение 1 напоминанием]:** в `deleteNonCurrentVersions` нет `S3_MAX_SCAN_PAGES`-потолка, поэтому 21 страница не срезается раньше; `MAX_SAME_MARKER = 5` тоже не мешает — `NextVersionIdMarker` меняется на каждой странице.

**(в) Короткий комментарий** на `objectRouter.ts:929-935`, почему проверка живёт именно в truncated-ветке: проверяется то, что переносится; присваивание `pendingItems` живёт в `else` этой же проверки, чем и держится инвариант `pendingItems.length ≤ S3_MAX_BUFFERED_VERSIONS_PER_KEY`; на последней странице группа уже полна, и отбросить её значило бы навсегда отказать в обслуживании самому нуждающемуся ключу.

**Текущее поведение, которое надо зафиксировать в PR-ответе:** ключ обрабатывается корректно, пока он перестаёт быть отложенным, не перевалив 20 000 перенесённых (практически — до ~21 000 записей); ключ, который остаётся отложенным на 21-й подряд странице, отбрасывается с `TooManyVersions` + `isPartial: true`. Существующий тест `:1538` пинит именно вторую половину.

**Expected outcome:** документ перестаёт обещать недостижимое, намерение закреплено тестом, поведение байт-в-байт прежнее.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/objectRouter.test.ts`. **Регрессия для этого шага особая** (кода мы не меняли): временно применить лекарство Copilot — вынести проверку `> S3_MAX_BUFFERED_VERSIONS_PER_KEY` из truncated-ветки и применять её к слитой группе безусловно — и убедиться, что новый тест краснеет (`TooManyVersions`, `deletedCount === 0`), а старый `:1538` остаётся зелёным. Это и есть доказательство, что тест пинит именно спорное место. После — откатить.

---

### Шаг 4 — `DeleteVersionsModal`: отчёт о неуспехе внутрь модалки (находка 4, откат решения раунда 1)

Здесь мы **признаём, что первый раунд закрыл находку неправильно**. Аргумент раунда 1 («модалка безусловно закрывается в `onSettled`, а „закрылась → отчиталась тостом“ — конвенция всех семи модалок в `BucketModals`») не выдерживает: конвенция нигде не записана, а противоположное записано прямо — B.11 `:415-416` предписывает «успех → закрыть + тост, отказ → остаться открытым + `Message`». Второе возражение раунда 1 («`Message` в деструктивной модалке запрещён B.5») снимается оговоркой `:245`.

**Файлы** (все под `.../Ceph/Buckets/`):
`DeleteVersionsModal.tsx`, `BucketToastNotifications.tsx`, `BucketModals.tsx`, `DeleteVersionsModal.test.tsx`, `BucketToastNotifications.test.tsx`.

**4.1 — `onSettled` перестаёт закрывать безусловно.**

```ts
const deleteVersionsMutation = trpcReact.storage.ceph.objects.deleteNonCurrentVersions.useMutation({
  // Invalidation belongs here (it must happen on every outcome — a partial run moved data too),
  // but closing does not: a failed or partial run has to stay open to report itself (B.11).
  onSettled: () => {
    invalidateBucketQueries(utils)
  },
})
```

Закрытие (`handleClose()`) вызывается только в ветке чистого успеха внутри `mutate`-колбэка `onSuccess`.

**4.2 — Локальное состояние исхода.** В `DeleteVersionsModal.tsx`:

```ts
type DeleteVersionsOutcome =
  | { kind: "error"; detail: string }
  | { kind: "partial"; deletedCount: number; errorCount: number; errors: DeleteObjectError[]; incomplete: boolean }

const [outcome, setOutcome] = useState<DeleteVersionsOutcome | null>(null)
```

Два варианта — ровно 1:1 с двумя удаляемыми тостами, поэтому перенос копирайта механический.
Сброс: в начале `handleSubmit` (перед `mutate`), в `handleConfirmNameChange`, в `handleClose`.

**4.3 — Классификация исходов переезжает целиком, меняется только транспорт.** Сохранить как есть структуру `mutate.onSuccess` (`:81-102`) **вместе с большим комментарием** про независимость `errorCount` и `isPartial` — она правильная:

- `deletedCount === 0 && errorCount > 0 && !isPartial` → `setOutcome({ kind: "error", detail })`, где `detail = errors.length > 0 ? formatBulkDeleteErrors(errors.slice(0, MAX_LISTED_DELETE_ERRORS)) : t`${errorCount} item(s) could not be deleted``;
- `errorCount > 0 || isPartial` → `setOutcome({ kind: "partial", deletedCount, errorCount, errors, incomplete: isPartial })`;
- иначе → `onSuccess?.(bucketName, deletedCount)` **и** `handleClose()`.

`mutate.onError` (транспортный/tRPC-отказ) → `setOutcome({ kind: "error", detail: error.message })`, модалка остаётся открытой (B.11: server-side errors → `Message` внутри модалки).

Константу `MAX_LISTED_DELETE_ERRORS = 3` перенести сюда из `BucketToastNotifications.tsx:195` вместе с комментарием.

**4.4 — Рендер `Message` первым элементом `<Stack>`** (B.16 `:506`: «Place a `Message` as close as possible to the content it relates to»):

```tsx
{outcome && (
  <Message
    variant="error"
    title={outcome.kind === "error" ? t`Failed to Delete Versions` : t`Versions Partially Deleted`}
    role="alert"
    aria-live="assertive"
    className="mb-4"
    data-testid="delete-versions-outcome"
  >
    {/* structured body — see below */}
  </Message>
)}
```

**[уточнение 3, критично]:** `title` типизирован как `string` — передавать `` t`…` ``, не `<Trans>`. Заголовки берём дословно из удаляемых тостов, чтобы `msgid` уцелели.

Тело для `kind: "partial"` — тот же структурный состав, что сейчас в `getVersionsPartiallyDeletedToast` (`BucketToastNotifications.tsx:208-241`), перенести как есть:
«Deleted N version(s) from bucket "X".» → «M item(s) could not be deleted: …» (до `MAX_LISTED_DELETE_ERRORS` записей) → «K further failure(s) are not listed here.» → «The scan did not reach the end of the bucket, so non-current versions may remain. Run Delete Versions again.» Плюрализация через `<Plural>` сохраняется, каждое предложение переводится целиком.
Тело для `kind: "error"` — `<Trans>Could not delete versions from bucket "{bucketName}": {detail}</Trans>` (msgid совпадает с телом удаляемого `getVersionsDeleteErrorToast`).

**Почему оба исхода — `variant="error"`, а не `warning` для частичного:** B.16 `:507` требует совпадения варианта `Message` с вариантом primary-кнопки (`primary-danger` → `danger`), и единственное разрешённое исключение — `variant="error"` для operation-ошибок (B.5 `:245`). `warning` внутри этой модалки недопустим. Исходы различаются **заголовком и текстом**.

**4.5 — Поверхность для повтора получается бесплатно.** После неудачного прогона `confirmName` уже заполнен, `disableConfirmButton={isPending || confirmName.trim() !== bucket.name}` не срабатывает ⇒ кнопка «Delete Versions» активна, повтор прямо здесь. Отдельная кнопка Retry не нужна (и была бы вторым primary — нарушение B.5). Повтор безопасен: для `isPartial` это продолжение скана, для пер-ключевых отказов — идемпотентное удаление по `VersionId`.

**4.6 — Закрыть новую дыру: блокировка закрытия во время мутации.** ⚠️ *Найдено при планировании, Copilot этого не называл.* Раньше закрытие модалки во время in-flight мутации было безвредно (она всё равно закрывалась по `onSettled`); теперь оно молча уносит единственную поверхность отчёта. Добавить на `<Modal>`:

```tsx
disableCancelButton={deleteVersionsMutation.isPending}
disableCloseButton={deleteVersionsMutation.isPending}
```

Основание: Reject-чеклист `:41` и B.5 («`disableCloseButton` sync»). Если решено не расширять диффа — см. Open Question 2.

**4.7 — Чистка `BucketToastNotifications.tsx`.** Удалить `getVersionsPartiallyDeletedToast` (`:197-250`), `getVersionsDeleteErrorToast` (`:167-174`), тип `PartialVersionDeleteOutcome` (`:176-192`), константу `MAX_LISTED_DELETE_ERRORS` (`:195`) и ставшие ненужными импорты (`DeleteObjectError`, `formatBulkDeleteErrors` — проверить, не нужны ли они другим хелперам файла; на `0f992593` больше нигде не используются). **Оставить** `getVersionsDeletedToast` (`:151-165`) — подтверждение CRUD остаётся тостом (B.16 `:497`).
Проверено grep’ом: у удаляемых символов нет импортёров, кроме `BucketModals.tsx`, `DeleteVersionsModal.tsx` и собственных тестов.

**4.8 — `BucketModals.tsx`.** Убрать пропсы `onError`/`onPartial` у `<DeleteVersionsModal>` (`:216-227`) и импорты `getVersionsDeleteErrorToast`/`getVersionsPartiallyDeletedToast` (`:23-24`). Оставить `onSuccess` → `toast.success(getVersionsDeletedToast(...))` + `onClose()` без изменений. В интерфейсе `DeleteVersionsModalProps` убрать `onError` и `onPartial`, а также импорт `type PartialVersionDeleteOutcome` (`:10`).
Комментарий на `:198-203` («it doesn't query anything itself») остаётся верным.

**4.9 — Тесты.**

- `DeleteVersionsModal.test.tsx` (14 кейсов, `test(...)`, не `it(...)`): переписать с «вызвал ли колбэк» на «что отрендерилось и осталась ли модалка открытой». Из `renderModal` убрать `onError`/`onPartial`; сделать `isPending` мока мутации управляемым (сейчас захардкожен `false` на `:59`), иначе не написать кейс 4.6. Целевые кейсы:
  - `:178` «some keys failed but others were deleted» → `getByTestId("delete-versions-outcome")`, заголовок `Versions Partially Deleted`, `onSuccess` не вызван, `onClose` не вызван, диалог в документе;
  - `:208` «nothing was deleted and keys failed» → заголовок `Failed to Delete Versions`, модалка открыта;
  - `:231` «errorCount === 0» → `onSuccess` вызван, `onClose` вызван, `Message` отсутствует;
  - `:252` «did not reach the end of the bucket» → частичный `Message`, текст содержит «Run Delete Versions again»;
  - `:283` «both the failures and the incomplete scan» → в теле присутствуют и перечень отказов, и фраза про незавершённый скан;
  - `:315` «nothing deleted but the scan stopped early» → частичный, не error-заголовок;
  - `:340` «refreshes the deleted-content indicators» → остаётся валиден (`onSettled` по-прежнему инвалидирует), но теперь дополнительно утверждаем, что `onSettled` **не** закрывает модалку;
  - **новые:** (a) кнопка «Delete Versions» остаётся активной после неуспешного прогона (поверхность повтора); (b) `Message` несёт `role="alert"`/`aria-live="assertive"`; (c) повторный сабмит очищает предыдущий `Message`; (d) при `isPending: true` Cancel/close задизейблены (если принят 4.6);
  - аналитические кейсы `:361-397` — не трогать, добавить комментарий, что после неуспеха ручное закрытие не даёт `.close`, так как `markSubmitted()` уже был вызван.
- `BucketToastNotifications.test.tsx`: удалить `describe("getVersionsDeleteErrorToast")` (`:413-419`) и `describe("getVersionsPartiallyDeletedToast")` (`:421-501`), убрать оба хелпера из массива в «Notification configuration» (`:259-300`, строки `:278-279`) и из импортов (`:22-23`). `describe("getVersionsDeletedToast")` (`:389`) остаётся.

**Expected outcome:** успех — закрытие + тост (как было); отказ и частичный исход — модалка остаётся открытой с `<Message variant="error">` наверху, с тем же структурным текстом и живой кнопкой повтора.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets/` (экранировать `$`).
**Регрессия:** временно вернуть `handleClose()` в `onSettled` и убедиться, что краснеют кейсы «модалка осталась открытой»; отдельно временно убрать `role`/`aria-live` и убедиться, что краснеет a11y-кейс.

---

### Шаг 5 — Changeset и описание PR

**Changeset — рекомендация: дополнять существующий файл**
`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.changeset/ceph-bounded-version-scans-and-delete-versions.md` (`minor`), **не** заводить новый. Основания:

- ветка не отрелижена, файл описывает ровно тот код, который правится; отдельный `patch` породил бы в CHANGELOG запись про фикс поведения, которое никогда не отгружалось;
- `patch` рядом с `minor` на том же пакете всё равно не меняет бамп;
- главное: абзац про `DeleteVersionsModal` сейчас утверждает «…reported as a partial result in a **warning notification that stays on screen until dismissed**» — шаг 4 делает это **ложным**. Оставить как есть нельзя: changeset уйдёт в публичный CHANGELOG.

Конкретные правки текста changeset’а:

1. Абзац 2 (`The modal now also distinguishes the three outcomes…`): заменить «warning notification that stays on screen until dismissed» на формулировку про inline-`Message` в модалке: успешный прогон закрывает модалку и подтверждается тостом; отказ и частичный исход оставляют модалку открытой и объясняются сообщением об ошибке внутри неё, откуда действие можно повторить сразу. Сохранить существующее уточнение про независимость `errorCount` и `isPartial` — оно осталось верным.
2. Добавить (в тот же абзац или отдельным буллетом в «Behaviour changes») одно предложение про шаг 1: «Delete Bucket» и «Empty Bucket» теперь ждут завершения живой проверки состояния бакета вместо рендера по закэшированному ответу — модалка, чьё решение необратимо, не принимает решения по данным, которые в этот момент перепроверяются.
3. Абзац про `deleteNonCurrentVersions` / `S3_MAX_BUFFERED_VERSIONS_PER_KEY`: если там есть формулировка про предел памяти, привести её в соответствие с новым доком константы (буфер, переносимый между страницами; пик = предел + размер страницы). Проверить фразу «A key with more versions than fit in the scan buffer is abandoned the same way instead of being accumulated in server memory» — она остаётся верной, но стоит уточнить, что отбрасывается ключ, **не дочитанный** до конца в пределах буфера.
4. Шаг 2 (a11y) и шаг 3 (док+тест) в changeset отдельной строкой не нуждаются — поведения не меняют.

**Описание PR** — `/Users/kirylmishchuk/projects/SAP/DOCS/descriptions/pr-1331-description.md` (опубликовано и совпадает с телом PR байт-в-байт; правки нужно внести и в файл, и в PR на GitHub — постит пользователь). Затрагиваемые разделы (заголовки проверены по файлу):

- `## Component Updates` → буллет **`DeleteVersionsModal`** (`:49`) — переписать вторую половину: вместо «reported through a new required `onPartial` callback as a "Versions Partially Deleted" warning notification that stays on screen until dismissed» — про inline-`Message` в открытой модалке, про повтор прямо оттуда и про то, что тостом остаётся только подтверждение успеха. Упоминание стабильного `id` тоста и `duration: Infinity` удалить — этих механизмов больше нет. Перечисление структурного тела («spells out the first few failures, counts the rest») сохранить, оно переехало в `Message`.
- `## Component Updates` → буллеты **`EmptyBucketModal`** (`:50`) и **`DeleteBucketModal`** (`:51`) — добавить, что обе ждут живой ответ `getState` (in-flight refetch трактуется как «ещё не знаем»), и что error-состояние `EmptyBucketModal` теперь `Message` с `role="alert"`/`aria-live="assertive"`.
- `## Core Infrastructure` → буллет **`constants.ts`** (`:44`) — одно предложение о том, что `S3_MAX_BUFFERED_VERSIONS_PER_KEY` ограничивает переносимый между страницами буфер, а пик равен предел + размер страницы.
- `## Tests` (`:61-65`) — добавить новые кейсы: refetch-in-flight в обеих модалках, обработка ключа, переполняющего буфер на последней странице, inline-отчёт `DeleteVersionsModal` вместо колбэков.
- `# Behaviour and Contract Changes` (`:67`) — правки контракта BFF нет; при желании одна строка, что «Delete Versions» больше не закрывается при неуспехе (изменение UX, не API).

**Не затрагиваются:** `# Summary`, `### New storage.ceph.objects.deleteNonCurrentVersions`, `### New storage.ceph.containers.getState`, `### Updated storage.ceph.versioning.checkDeletedContent`, `## Types`, `# Related Issues`, `# Testing Instructions`, `# Checklist`.

**Verification:** в changeset не остаётся утверждений, которых код не выполняет; локальный файл описания и тело PR остаются байт-в-байт идентичными.

---

### Шаг 6 — Прогон CI локально

Из `/Users/kirylmishchuk/projects/SAP/aurora-dashboard`, в порядке `.github/workflows/ci-checks.yaml`:

```bash
pnpm licenses:check
pnpm lint
pnpm check-i18n
pnpm typecheck
pnpm format:check
pnpm test
pnpm build
```

Быстрый внутренний цикл — с `--filter @cobaltcore-dev/aurora` (`test`, `typecheck`, `lint`), но полный нескоупленный набор прогнать один раз перед сдачей: `format:check` и `build` покрывают весь workspace.

`pnpm check-i18n` — **мутирующая** джоба (переписывает `.po`). Запускать до `format:check`; после — `git diff -- packages/aurora/src/locales`. Ожидание: диффа либо нет вовсе, либо он ограничен msgid’ами, реально исчезнувшими/появившимися на шаге 4. Если шаг 4 сохранил формулировки заголовков и тел дословно, диффа быть не должно — любой неожиданный msgid означает, что копирайт при переносе разъехался, и это надо чинить, а не принимать.

**Verification:** все семь — exit 0; `git status` показывает только файлы из раздела «Файлы, которые трогает план».

---

## Testing Plan

**Новые unit-тесты**

- [ ] `DeleteBucketModal.test.tsx` — `{isLoading:false, isFetching:true}` → прогресс-ветка + задизейбленный confirm.
- [ ] `EmptyBucketModal.test.tsx` — `{isLoading:false, isFetching:true, data:<empty + only delete markers>}` → прогресс-ветка, заголовка `Delete Versions` нет, confirm задизейблен.
- [ ] `EmptyBucketModal.test.tsx` — error-баннер несёт `role="alert"`/`aria-live="assertive"`.
- [ ] `objectRouter.test.ts` — ключ переполняет буфер **на последней** странице → `deletedCount > 0`, нет `TooManyVersions`, `isPartial === false`.
- [ ] `DeleteVersionsModal.test.tsx` — частичный исход: `Message` отрендерен, модалка открыта, `onSuccess`/`onClose` не вызваны.
- [ ] `DeleteVersionsModal.test.tsx` — полный отказ (в т.ч. отказ самой мутации): `Message` с заголовком `Failed to Delete Versions`, модалка открыта.
- [ ] `DeleteVersionsModal.test.tsx` — чистый успех: `onSuccess` + `onClose`, `Message` отсутствует.
- [ ] `DeleteVersionsModal.test.tsx` — кнопка повтора активна после неуспеха; повторный сабмит очищает предыдущий `Message`.
- [ ] `DeleteVersionsModal.test.tsx` — (если принят 4.6) Cancel/close задизейблены при `isPending`.

**Изменяемые тесты**

- [ ] Моки `useQuery` в обеих модалках получают управляемый `isFetching`.
- [ ] Шесть кейсов исходов в `DeleteVersionsModal.test.tsx` переводятся с колбэков на рендер; `renderModal` теряет `onError`/`onPartial`; мок мутации получает управляемый `isPending`.
- [ ] `BucketToastNotifications.test.tsx` — минус два `describe`, минус две записи в массиве «Notification configuration», минус два импорта.

**Регрессионная проверка (делать по шагам, не в конце)** — для каждого продуктового фикса откатить правку и убедиться, что новый тест краснеет:

1. Шаг 1: вернуть `isLoading = isLoadingBucketState` в каждом файле по отдельности.
2. Шаг 2: убрать `role`/`aria-live` с `Message`.
3. Шаг 3 (инверсия — кода не меняли): применить лекарство Copilot и убедиться, что новый тест краснеет, а существующий `:1538` — нет.
4. Шаг 4: вернуть `handleClose()` в `onSettled`.

**Ручная проверка**

1. Открыть бакет с историей версий, подождать загрузки шапки (кэш `useBucketInfo` прогрет), затем открыть «Delete Bucket» и «Empty Bucket» — обе показывают `Checking Bucket Contents...` до ответа, а не мгновенное решение.
2. Сценарий находки 2: в одной вкладке открыть пустой версионированный бакет с одними delete-маркерами, из другой вкладки/клиента залить объекты, затем открыть «Empty Bucket» — модалка обязана либо ждать, либо показать обычную деструктивную форму с чекбоксом, но **не** ветку «Delete Versions».
3. Обрыв связи/403 на `getState` в `EmptyBucketModal` — красный `Message`, скринридер зачитывает его появление.
4. Частичный «Delete Versions» (временно занизить `S3_MAX_KEYS_PER_REQUEST` или подменить ответ) — модалка **не** закрывается, показывает `Message` с перечнем отказов и фразой «Run Delete Versions again», кнопка «Delete Versions» активна, повтор работает из той же модалки.
5. Чистый «Delete Versions» — модалка закрывается, тост «Versions Deleted».

---

## Acceptance Criteria

- [ ] Ни `DeleteBucketModal`, ни `EmptyBucketModal` не выносят решение (и не форсируют `includeVersionsAndDeleteMarkers: true`) при `isFetching: true`; `disableConfirmButton` обычной ветки `EmptyBucketModal` явно содержит `isLoading`.
- [ ] В `EmptyBucketModal` нет самодельных error-`div`; все три состояния — `<Message variant="error" role="alert" aria-live="assertive">` без `dismissible` и без `title`; класс `bg-theme-danger-10` в клиенте больше не встречается.
- [ ] Поведение `objectRouter.deleteNonCurrentVersions` не изменилось ни на строку; док `S3_MAX_BUFFERED_VERSIONS_PER_KEY` описывает настоящую гарантию; путь «переполнение на последней странице» покрыт тестом.
- [ ] `DeleteVersionsModal` остаётся открытой при отказе и частичном исходе и рапортует inline-`Message` (`variant="error"` в обоих случаях, различие — заголовок и текст); успех закрывает модалку и подтверждается тостом.
- [ ] `getVersionsPartiallyDeletedToast`, `getVersionsDeleteErrorToast`, `PartialVersionDeleteOutcome` удалены; `getVersionsDeletedToast` сохранён; пропсы `onError`/`onPartial` у `DeleteVersionsModal` удалены; ни одного висячего импорта.
- [ ] Классификация трёх исходов (с комментарием про независимость `errorCount` и `isPartial`) сохранена дословно — поменялся только транспорт.
- [ ] Changeset больше не утверждает про «warning notification that stays on screen until dismissed»; описание PR обновлено в перечисленных разделах и остаётся байт-в-байт равным телу PR.
- [ ] Регрессия подтверждена по всем четырём пунктам выше.
- [ ] `pnpm licenses:check`, `lint`, `check-i18n`, `typecheck`, `format:check`, `test`, `build` — зелёные; `git diff` по `packages/aurora/src/locales` объясним построчно.
- [ ] Пять ответов Copilot’у опубликованы (вручную, пользователем).
- [ ] Ничего не закоммичено/не запушено/не опубликовано агентом.

---

## Open Questions

> **Решено пользователем 2026-09-24 — вопросы 1–3 закрыты, работу не блокируют.**
>
> 1. **Changeset — дополняем существующий** `.changeset/ceph-bounded-version-scans-and-delete-versions.md`. Новый файл не заводим.
> 2. **`disableCancelButton`/`disableCloseButton` при `isPending` (пункт 4.6) — делаем в этом PR**, вместе с тестом. Дыру создаёт сам шаг 4, и это отдельный пункт Reject-чеклиста `:41`.
> 3. **`S3_MAX_BUFFERED_VERSIONS_PER_KEY` не переименовываем.** Ограничиваемся доком; при желании — отдельный `refactor` позже.
>
> Вопрос 4 (follow-ups) решения не требует — это фиксация границ PR.


1. **Changeset: дополнить существующий или завести новый?** Рекомендация — **дополнить существующий** `ceph-bounded-version-scans-and-delete-versions.md` (ветка не отрелижена, файл описывает ровно этот код, и его текущий текст без правки станет ложным). Новый `patch`-файл не изменил бы бамп, зато добавил бы в CHANGELOG запись про фикс не отгружавшегося поведения. Решение нужно до шага 5.
2. **Пункт 4.6 (`disableCancelButton`/`disableCloseButton` при `isPending`) — в этот PR или в follow-up?** Рекомендация — **в этот PR**: дыру создаёт сам шаг 4 (раньше закрытие во время мутации было безвредно), и она прямо в Reject-чеклисте `:41`. Аргумент против — Copilot об этом не просил, диффа растёт на две строки + один тест.
3. **Переименовывать ли константу** `S3_MAX_BUFFERED_VERSIONS_PER_KEY` → например `S3_MAX_CARRIED_VERSIONS_PER_KEY`, раз её имя тоже намекает на пик, а не на перенос? Проверено: константа не экспортируется из `server/index.ts`, потребителей вне `objectRouter.ts` и его теста нет — переименование безопасно. Рекомендация — **не переименовывать** в этом PR (шум в диффе на ревью второго раунда), ограничиться доком; при желании отдельным `refactor`.
4. **Follow-ups, подтверждающие границы (в #1331 не тащим):** (а) `DeleteBucketModal.tsx:149-151` — `<Status status="error">` без `role`/`aria-live`, пришёл из `main`; (б) все follow-ups первого раунда остаются в силе, включая вынос общего цикла пагинации `ListObjectVersions` в хелпер и маркер возобновления для `deleteNonCurrentVersions` — последний как раз сильно улучшил бы новый inline-повтор из шага 4.

---

# Copilot reply texts (English, for manual posting)

### Finding 1 — `DeleteBucketModal.tsx:33-40` (Copilot: High) — accepted, lower severity

> Accepted and fixed, though I'd rate it Low rather than High.
>
> The mechanism is exactly as described: `staleTime: 0` governs staleness (and therefore triggers a refetch), not whether a cached entry is served. `isLoading` is `isPending && isFetching`, and `isPending` is false whenever the cache holds an entry — so the modal renders a verdict off the old state while `isFetching` is still true, and both `disableConfirmButton` and the branch selection only look at `isLoading`.
>
> One detail worth adding, because it makes the window much wider than it looks: the cache is warm essentially always. `hooks/useBucketInfo.ts` issues the *same* `containers.getState` query with the same key and `staleTime: 30s`, and that hook lives in the bucket header for the whole session — its own comment says so ("the modals that need emptiness query `getState` themselves and hit the same cache entry"). `isLoading === true` therefore only happens on the very first open.
>
> What keeps this Low rather than High: `cannotDelete` is a preliminary UX gate. A bucket that is not actually empty still refuses to delete on the S3 side with `BucketNotEmpty`, so a stale "looks deletable" costs an error message, not data.
>
> Fix: take `isFetching` from the query too and gate on `isLoadingBucketState || isFetchingBucketState`. Same one-line change as #2 below — it's one defect in two copies.

### Finding 2 — `EmptyBucketModal.tsx:49-63` (Copilot: High) — accepted

> Accepted as High, fixed.
>
> Same mechanism and the same warm cache as #1, but here there is no backstop on the S3 side. `isBucketEmptyWithVersions` is the one branch that forces `includeVersionsAndDeleteMarkers: true` with no checkbox (`shouldDeleteVersions` at the mutation call), and `objects.deleteAll` with that flag is a full wipe — the original bug this PR exists to fix.
>
> The dangerous direction is one-way: a stale entry saying `isEmpty: true, hasOnlyDeleteMarkers: true, isPartialScan: false` while objects have since been uploaded (another tab, another user, CI — the local `invalidateBucketQueries` cannot see any of those) opens the modal on the "Delete Versions" branch, whose copy promises to remove only versions and delete markers, and the confirm then wipes the fresh objects.
>
> The other directions are all fail-safe, which is worth recording so the fix isn't over-scoped: a stale "not empty" falls into the ordinary branch with the opt-in checkbox (`shouldDeleteVersions: false`); a stale `isTrulyEmpty` renders the info-only branch with no action at all; a stale `isPartialScan: true` disables both "smart" branches and falls back to the ordinary destructive form. Exposure is one round-trip wide (`getState` is GetBucketVersioning + a one-key ListObjectsV2 + a bounded history scan, seconds on a large history) — the High rating rests on the irreversibility of the outcome, not on the probability.
>
> Fix: `const isLoading = isLoadingBucketState || isFetchingBucketState`. That covers everything on its own, because `isLoading` already gates both smart branches and the body of the ordinary one. I also added `|| isLoading` to the ordinary branch's `disableConfirmButton`, which until now was only saved indirectly (while loading, the `TextInput` isn't rendered, so `confirmName` stays empty) — `DeleteBucketModal` already had it explicit.
>
> The cost is deliberate: every open of either modal now waits for the live check instead of painting instantly from cache. That is the right trade for a destructive pre-check, and both files already claim to do it ("live pre-delete check", "re-verifies live instead of serving cached data") — the code simply wasn't honouring the claim.

### Finding 3 — `objectRouter.ts:929-952` (Copilot: High) — declining the remedy, fixing the doc and the coverage

> The arithmetic is right, the conclusion isn't — and the doc comment that makes it look wrong is genuinely wrong, so I've fixed that instead.
>
> The check guards what is **carried across pages**: the assignment to `pendingItems` lives in the `else` of that very check, so the invariant `pendingItems.length ≤ S3_MAX_BUFFERED_VERSIONS_PER_KEY` always holds. The peak is reached right after the merge — carried (≤ 20 000) plus this page's contribution for the same key (≤ `S3_MAX_KEYS_PER_REQUEST` = 1 000) = **21 000 records, a constant**. It does not grow with the bucket or with the number of pages; it's a few MB per in-flight request.
>
> Why the proposed remedy is worse: a group that has been read to the end — every record of the key in hand, the decision provably correct, the deletion safe — would be discarded purely for its size. A key with 20 001 versions would stop being cleanable *forever*: every re-run would hit the same limit and return `TooManyVersions`. And that is precisely the profile the constant exists for — its own doc calls it "a CI artifact, a rolling log". A deterministic, permanent denial of service on the key that most needs the cleanup.
>
> What no implementation can achieve: the doc says the limit is "how many version records … will hold in memory for a single key" and that "past this many records the group is abandoned rather than buffered". That's unreachable by construction — to know a page's contribution you must first fetch and parse it, so the records are already on the heap before any check can run. A check after the merge doesn't lower the peak; it only decides what to do with it. So the "contradiction with the heap bound" is a defect in the wording, not in the code.
>
> Current behaviour, to state it exactly: a key is processed as long as it stops being the deferred group without having exceeded 20 000 carried records (in practice, up to ~21 000 records); a key that is still deferred on its 21st consecutive page is abandoned with `TooManyVersions` and `isPartial: true`. The existing test at `objectRouter.test.ts:1538` pins that second half.
>
> Changes made:
> - rewrote the `S3_MAX_BUFFERED_VERSIONS_PER_KEY` doc to state the real guarantee (bounds the cross-page carry; peak is limit + page size, because a page cannot be sized without reading it; a fully-read group is processed regardless of size, because dropping it would be an unrecoverable denial of service for that key);
> - added the test that was missing — and whose absence is exactly why this finding looks convincing: a key that overflows the buffer on its **final** page (`IsTruncated: false`) is deleted, with no `TooManyVersions` and `isPartial: false`;
> - added a short comment at the check explaining why it lives in the truncated branch.
>
> No behaviour change.

### Finding 4 — `BucketModals.tsx` / `DeleteVersionsModal.tsx` (Medium) — accepted in full; the previous round closed this incorrectly

> Accepted in full, and I owe a correction: I rejected this remedy in the previous review round and the reasoning I gave was wrong.
>
> What I argued then: the modal closes unconditionally in `onSettled`, and "close, then report by toast" is the convention all seven modals in `BucketModals` follow, so an in-modal result panel would be an exception. That convention is written down nowhere, and the opposite *is* written down. B.11 (`.github/copilot-instructions.md:415-416`): "On success: … (modal) close and show a confirming toast"; "Distinguish failures: validation errors stay inline and keep the form open; server-side errors show a `Message` at form top (or inside the modal) explaining what went wrong and whether retry helps." The success/failure split you're asking for *is* the prescribed pattern. My second objection — that B.5 forbids a `Message` inside a destructive modal — doesn't hold either: B.5 (`:245`) carves out "Operation/validation errors are still allowed and should use `variant="error"`". Add B.16 `:504` and the Reject item at `:509`.
>
> What changed:
> - `onSettled` no longer closes unconditionally. `invalidateBucketQueries(utils)` still runs on every outcome; `handleClose()` runs only on a clean success.
> - The modal keeps its own outcome state, cleared on re-submit, on editing the confirmation field, and on close.
> - Failure and partial outcomes render a `<Message variant="error" role="alert" aria-live="assertive">` at the top of the modal, carrying the same structured body the toast used to: "Deleted N versions", "M items could not be deleted: …" (first 3 spelled out), "…further failures are not listed here", "The scan did not reach the end of the bucket — run Delete Versions again."
> - Success is unchanged: close, then `toast.success` (B.16 `:497` — a confirmed CRUD action is a toast).
> - Both failing outcomes use `variant="error"` and differ by title and body, **not** by colour. A `warning` variant isn't available inside this modal: B.16 `:507` requires the `Message` variant to match the primary button (`primary-danger` → `danger`), and the only sanctioned exception is `error` for operation errors.
> - The retry surface comes for free: after a failed run `confirmName` is still filled, so `disableConfirmButton` doesn't trip and "Delete Versions" is live. No separate Retry button (it would be a second primary). Re-running is safe — for `isPartial` it continues the scan, and the per-key deletions are idempotent, addressed by `VersionId`.
> - Removed `getVersionsPartiallyDeletedToast`, `getVersionsDeleteErrorToast` and the `PartialVersionDeleteOutcome` type (no importers outside `BucketModals` and their own tests), along with the modal's `onError`/`onPartial` props. `getVersionsDeletedToast` stays.
> - Kept the three-way outcome classification untouched, including the comment explaining why `errorCount` and `isPartial` are independent dimensions rather than alternatives. Only the transport changed: local state instead of callbacks.
>
> I also disabled Cancel and the close button while the mutation is in flight. Previously closing mid-flight was harmless because the modal was closing anyway; now it would silently discard the only report of the outcome (Reject list `:41`), so the security pass on this change caught that the two props alone are not enough: juno's `Modal` gates its Esc handler on `closeable && closeOnEsc` and never consults `disableCancelButton`/`disableCloseButton` (checked against the source at the pinned `@cloudoperators/juno-ui-components@9.4.0` tag), so one keypress still discarded the report. `closeOnEsc={!isPending}` closes that path; `closeable={false}` would have closed it too, but it unmounts the footer and the close icon rather than disabling them, taking the confirm button with it.

### Finding 5 — `EmptyBucketModal.tsx:162, 210, 242` (Medium) — accepted

> Correct, and it's on this PR: `git diff main...HEAD` shows the `div`s as context but all three `<Trans>` strings as changed lines, so the PR rewrote the copy in each of them.
>
> All three were hand-rolled banners (`bg-theme-danger-10 text-theme-danger rounded p-4`) with no `role` and no `aria-live`, and they appear reactively on `bucketStateError` *after* the modal is already open — exactly the live-region case B.14 (`:455`) is about, repeated in the Reject list (`:295`) and the checklist (`:51`).
>
> Rather than bolting the attributes onto the `div`s, I replaced them with `<Message>`, which is the settled form in the same folder — `CreateBucketModal.tsx:176-185`, `Objects/CreateFolderModal.tsx:123-132` and several others. That class combination appeared in exactly these three places in the whole client, so it's now gone.
>
> Three details that aren't obvious:
> - `role`/`aria-live` have to be passed explicitly. Juno's `Message` doesn't set them (there's no `role: "alert"` anywhere in the 9.4.0 bundle), but `MessageProps extends HTMLAttributes<HTMLDivElement>` and the component spreads `...props`, so they land on the rendered element.
> - No `dismissible`: the banner reflects live query state, there's nothing to dismiss to, and `dismissible` without `onDismiss` is its own Reject item (B.16 `:509`).
> - No `title`: B.16 `:506` — titles are for prominent or multi-sentence messages.
>
> No conflict with B.5: the primary button is `primary-danger` and `variant="error"` is the sanctioned form for operation errors (`:245`).
>
> The message text is unchanged, so the msgid is the same and `check-i18n` is a no-op here (the catalogue is configured with `origins: false`, so no line references move either).
>
> Out of scope, flagged as a follow-up: `DeleteBucketModal` renders its equivalent error as `<Status status="error" title="Failed to Check Bucket Contents">`, also without `role`. That block came from `main` and isn't touched by this diff, and `Status` is the B.16-sanctioned component for section-level errors, so I'd rather not fold it in here.

---

## Файлы, которые трогает план

**Клиент (продакшн)** — все под `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/`:
`DeleteBucketModal.tsx`, `EmptyBucketModal.tsx`, `DeleteVersionsModal.tsx`, `BucketToastNotifications.tsx`, `BucketModals.tsx`

**Клиент (тесты)** — там же:
`DeleteBucketModal.test.tsx`, `EmptyBucketModal.test.tsx`, `DeleteVersionsModal.test.tsx`, `BucketToastNotifications.test.tsx`

**Сервер:**
`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/constants.ts` (только док)
`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts` (только комментарий)
`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Storage/routers/ceph/objectRouter.test.ts`

**i18n (регенерируются, руками не править):**
`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/locales/en/messages.po`, `.../de/messages.po` — ожидается отсутствие диффа; любой появившийся msgid требует объяснения.

**Релиз / документы:**
`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.changeset/ceph-bounded-version-scans-and-delete-versions.md` (дополнить)
`/Users/kirylmishchuk/projects/SAP/DOCS/descriptions/pr-1331-description.md` (+ то же в тело PR на GitHub, вручную)

**Читались только для справки:**
`/Users/kirylmishchuk/projects/SAP/aurora-dashboard/.github/copilot-instructions.md` (B.5 `:245`, B.11 `:415-416`, B.14 `:455`, B.16 `:492-509`, Reject `:41`, `:51`, `:295`, `:509`)
`.../Ceph/hooks/useBucketInfo.ts:93-101`, `.../Ceph/Objects/DeleteObjectsModal.tsx` (прецедент «остаться открытой с результатом»), `packages/aurora/src/client/App.tsx:52-60`, `packages/aurora/lingui.config.ts`, `@cloudoperators/juno-ui-components@9.4.0` `Message.component.d.ts`

---

**Режим соблюдён:** только план. Ничего не реализовано, не закоммичено, не запушено, ни один комментарий на GitHub не опубликован. Разбивка на коммиты в плане намеренно отсутствует.
