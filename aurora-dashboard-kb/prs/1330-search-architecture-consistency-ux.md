# PR #1330: refactor(portal): improve search architecture consistency and UX

**Автор:** TilmanHaupt · **Статус:** open, снят с draft; approve от vlad-schur-external-sap 24.09.2026 (создан 24.09.2026)
**Ветки:** `til-search-robustness` → `main` · **Файлов:** 15 (на head `b424b47`)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1330
**База:** `6ce6aeac`, то есть merge-коммит [#1320](./1320-search-all-visible-columns.md) (смержен 23.09.2026). Этот PR — продолжение #1320.

> **CI:** на первом head `2572b6f` job `test` падал в трёх тестах, хотя в PR description написано «All existing tests pass». Коммит `b424b47` (24.09.2026, «fix(aurora): resolve test failures from ARIA live regions») это исправил: все проверки CI зелёные. Подробности — в «Что затронуло».

## Что сделано

Это доработка после #1320. Сам PR называет себя ответом на ревью коммита `6ce6aeac`. Изменения четырёх видов:

1. **Сервер, Projects.** Удалена процедура `project.searchProjects` (без клиентских потребителей, свой inline-фильтр). `getAuthProjects` при этом **остаётся**: клиентских потребителей у неё нет, и она почти построчно дублирует `listProjectsWithSearch`. Поэтому таблица «After» в description («Projects — 1 endpoint with shared helper») не соответствует коду: процедур загрузки проектов по-прежнему две.
2. **Сервер, Flavors.** Свой regex-хелпер `includesSearchTerm` заменён общим `filterBySearchParams` с теми же семью полями. Шесть его тестов удалены.
3. **Клиент, Storage: доступность.** В тулбары Ceph Buckets и Swift Containers добавлен скрытый `aria-live="polite"` регион, который озвучивает «Found N buckets matching "…"» или «N buckets total».
4. **Клиент, Storage: пустые состояния.** `BucketTableView` и `ContainerTableView` получили проп `hasActiveSearch`. При активном поиске показывается «No … matching search / … match your search criteria», без поиска — «No … found / There are no … available in this project».

Плюс changeset `patch` и каталоги i18n. В `en` добавлены 8 msgid и переименованы 2. В `de` у всех 8 новых строк пустой `msgstr`, то есть немецкий UI покажет английский текст. Переведены только две переименованные строки про пустой проект.

## Как это реализовано

Код приведён по коммиту `2572b6f`.

### Flavors на общем хелпере

`packages/aurora/src/server/Compute/helpers/flavorHelpers.ts:163-193`:

```ts
export function filterAndSortFlavors(
  flavors: Flavor[],
  searchTerm: string,
  sortBy: keyof Flavor,
  sortDirection: string
): Flavor[] {
  // Use shared filterBySearchParams helper for consistent search behavior
  const filtered = filterBySearchParams(flavors, searchTerm, [
    "id",
    "name",
    "description",
    "vcpus",
    "ram",
    "disk",
    "swap",
  ])

  filtered.sort((a, b) => {
```

Description называет замену regex на подстроку «functionally equivalent». На деле поведение меняется, и в лучшую сторону:

- раньше `new RegExp(searchTerm, "i")` падал на вводе вроде `(` или `[`, и `.` совпадал с чем угодно;
- теперь поиск идёт буквальной подстрокой, а пробелы по краям обрезаются (`filterBySearchParams` делает `trim()`).

`swap` в схеме (`types/flavor.ts:17`) — `string | number`, и хелпер обрабатывает оба типа. `sort` по-прежнему мутирует массив на месте. Без поиска хелпер возвращает тот же массив, так что мутация входных данных осталась как была. Массив приходит свежим из API (`flavorRouter.ts:105`), поэтому это ни на что не влияет.

В `flavorHelpers.test.ts:74` блок `describe("fetchFlavors")` переименован в `describe("filterAndSortFlavors")`. В нём по-прежнему лежат HTTP-тесты `fetchFlavors`, и теперь в файле два describe с одинаковым именем (`:74` и `:212`). Поиск флейворов покрывают только тесты `:219` и `:255`. Числовые поля в них не проверяются.

### ARIA live region

`packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/index.tsx:389-403`:

```tsx
            <div className="text-theme-light flex items-center gap-1" data-testid="buckets-info-block">
              <Plural value={totalCount} one={`${totalCount} bucket`} other={`${totalCount} buckets`} />
            </div>
            {/* ARIA live region for screen readers */}
            <div className="sr-only" aria-live="polite" aria-atomic="true">
              {searchParam?.trim() ? (
                <Plural
                  value={totalCount}
                  one={`Found ${totalCount} bucket matching "${searchParam}"`}
                  other={`Found ${totalCount} buckets matching "${searchParam}"`}
                />
              ) : (
                <Plural value={totalCount} one={`${totalCount} bucket total`} other={`${totalCount} buckets total`} />
              )}
            </div>
```

В Swift аналог стоит в `Swift/Containers/index.tsx:406`. Регион находится внутри тулбара, а тулбар рендерится только после раннего return `if (isLoading)` (`Ceph/Buckets/index.tsx:238-240`, `Swift/Containers/index.tsx:260`). Этот return пришёл из #1320, после того как `searchTerm` стал частью query key.

### Пустые состояния

`Ceph/Buckets/BucketTableView.tsx:149-157`:

```tsx
                  <Status
                    status="empty"
                    title={hasActiveSearch ? t`No buckets matching search` : t`No buckets found`}
                    body={
                      hasActiveSearch
                        ? t`No buckets match your search criteria. Try adjusting your search term.`
                        : t`There are no buckets available in this project.`
                    }
                  />
```

Проп передаётся как `hasActiveSearch={!!searchParam}` (`Ceph/Buckets/index.tsx:423`, `Swift/Containers/index.tsx:444`), без `trim()`. Live region при этом проверяет `searchParam?.trim()`, так что при поиске из одних пробелов эти два признака расходятся. Сервер такой поиск игнорирует.

## Что затронуло

- **Три упавших теста на `2572b6f` (CI `test`, проверено по аннотациям check run); исправлены в `b424b47`.** Изначально тесты не были обновлены под новые строки:
  - `Swift/Containers/index.test.tsx:647` ждёт `/No containers found/i` при активном поиске, а теперь заголовок «No containers matching search»;
  - `Ceph/Buckets/index.test.tsx:374` и `:388`: `getByText(/3 buckets/i)` находит два элемента — видимый «3 buckets» и скрытый «3 buckets total» из live region.

  В `b424b47` Ceph-тесты ищут текст внутри `buckets-info-block` (`within(...)`), а Swift-тест ждёт `/No containers matching search/i`. Код компонентов этим коммитом не менялся.

  `ContainerTableView.test.tsx:216/221` проходят: там пропа `hasActiveSearch` нет, и по умолчанию показывается вариант без поиска. Для него отдельного теста с `hasActiveSearch` нет, есть только в `BucketTableView.test.tsx`.
- **`project.searchProjects` удалена.** Это контрактное изменение `AuroraRouter`. Внутри монорепо потребителей нет (grep по head), но внешнее приложение, которое импортирует тип роутера и вызывает эту процедуру, сломается при сборке. Changeset при этом `patch`.
- **`includesSearchTerm` удалена** из экспортов `flavorHelpers.ts`. Импортировал её только тестовый файл.
- **`BucketTableView` / `ContainerTableView`**: новый опциональный проп со значением по умолчанию `false`, так что остальные места использования не затронуты.
- **Замечания из отчёта #1320** (сверено на `b424b47`):

  | Проблема #1320 | Статус |
  | --- | --- |
  | Спиннер на всю страницу при каждом поиске (Ceph/Swift), повторный опрос S3 | Не решена: `searchTerm` в query key (`Ceph/Buckets/index.tsx:164`, `Swift/Containers/index.tsx:179`), ранний `if (isLoading)` (`:238`, `:260`), `placeholderData` нет. Теперь ещё и мешает новой фиче (см. ревью). |
  | Выбор пропадает при серверной фильтрации | Частично решена **ещё в #1320** до мержа: выбор очищается при смене поиска (`Ceph/Buckets/index.tsx:79-84`, `Swift/Containers/index.tsx:80-85`). Комментарий «from the full unfiltered list» (`:276`, `:274`) устарел. #1330 здесь ничего не меняет. |
  | Projects: Suspense и два запроса к Keystone на каждый поиск | Не решена: `useSuspenseQuery` с `searchTerm` (`projects/index.tsx:37`), `navigate` без `startTransition`. |

## Ревью

Ревью выполнено в одном проходе по пяти направлениям скилла с последующей оценкой уверенности. Находки, которые ловит CI (упавшие тесты), в ревью не включены по правилам скилла: они описаны выше.

**1. Live region не озвучивает главный сценарий — новый поисковый запрос (80/100).**
Регион рендерится внутри тулбара, а весь компонент уходит в ранний return `if (isLoading)` (`Ceph/Buckets/index.tsx:238-240`, `Swift/Containers/index.tsx:260`). Каждый новый поисковый запрос — это новый query key без кэша. `isLoading` становится `true`, и регион размонтируется, а после загрузки монтируется заново уже с готовым текстом. `aria-live` сообщает об *изменениях* содержимого региона, который уже есть в DOM. Регион, вставленный сразу с содержимым, скринридеры (NVDA, JAWS, VoiceOver) обычно не озвучивают. В итоге анонс сработает только при возврате к уже закэшированному запросу, а для нового поиска, ради которого фичу и добавляли, — нет. Чтобы исправить, регион нужно держать смонтированным вне ветки загрузки или убрать ранний return, например через `placeholderData: keepPreviousData`.

Ниже порога. В ревью не входят, но стоит учитывать:

- `getAuthProjects` остаётся мёртвым дубликатом `listProjectsWithSearch`, а description утверждает обратное (65).
- В `de` у 8 новых строк пустой `msgstr` (50).
- Два одинаковых `describe("filterAndSortFlavors")` в `flavorHelpers.test.ts` (40).
- `hasActiveSearch` без `trim()` расходится с условием live region (35).

---
**Ревью Copilot** (на первом коммите `a6b093a`; коммит `2572b6f` назван «apply Copilot code review suggestions»):

| Замечание Copilot | Статус на `b424b47` |
| --- | --- |
| Устаревший тест пустого состояния в `BucketTableView.test.tsx` | Исправлено |
| Live region озвучивает поиск из одних пробелов | Исправлено в live region (`searchParam?.trim()`), но `hasActiveSearch={!!searchParam}` остался без `trim()` |
| Немецкий перевод пустого состояния без поиска потерян | Исправлено для двух переименованных строк; у 8 новых строк `msgstr` в `de` по-прежнему пустой |
| `describe("fetchFlavors")` переименован по ошибке | Не исправлено |

Описание PR не обновлялось: в нём всё ещё «All existing tests pass» и «Projects — 1 endpoint».

---
Проанализировано: 24.09.2026 · коммит `2572b6f`, обновлено по `b424b47` (фикс тестов; код компонентов не менялся, находки ревью в силе)
