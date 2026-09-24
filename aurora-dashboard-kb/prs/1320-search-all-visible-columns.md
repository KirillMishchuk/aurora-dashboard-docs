# PR #1320: feat(portal): expand search to all visible columns including numeric

**Автор:** TilmanHaupt · **Статус:** смержен 23.09.2026 (andypf; создан 23.09.2026). Отчёт писался, пока PR был open.
**Ветки:** `til-all-search` → `main` · **Файлов:** 20 (+195/-73)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1320
**Закрывает:** #1226 («Ensure search placeholder instructs user what to search by»)

## Что сделано

Issue #1226 предлагала два пути: либо искать по *всем* показанным полям, либо написать в placeholder, по каким полям идёт поиск. PR выбирает первый путь. Placeholder'ы не менялись (например, `Search...` в `ProjectOverviewNavBar.tsx:51`), и второй пункт issue (единый стиль placeholder'ов) не закрыт.

По областям:

1. **Общий хелпер `filterBySearchParams`** теперь ищет и по числовым полям: число приводится к строке и проверяется подстрокой. От этого зависят Ceph, Swift, Images, Projects и Floating IPs.
2. **Compute.** Flavors ищут ещё по `vcpus`/`ram`/`disk`/`swap` (у flavor'ов свой regex-хелпер, а не `filterBySearchParams`). Images ищут ещё по `id`/`owner`/`size`, но это только в двух из трёх процедур (см. ниже).
3. **Storage (Ceph + Swift): фильтрация по имени переехала с клиента на сервер.** В input-схемы `listContainersInputSchema` (обе) добавлен `searchTerm`. Роутеры фильтруют через `filterBySearchParams` по name/count/bytes/last_modified (у Ceph ещё creationDate). Клиент передаёт `searchParam` в `useQuery` и больше не фильтрует сам. Счётчик «X of Y buckets/containers» убран, осталось просто «N buckets». Поэтому из каталогов `en`/`de` удалены два msgid.
4. **Projects: новая процедура `project.listProjectsWithSearch`.** Страница `/projects` раньше грузила все проекты через `getAuthProjects` и фильтровала на клиенте по name/description. Теперь серверу уходит `searchTerm`, а поиск идёт по id/name/description/domain_name/domain_id.
5. **Network.** Floating IPs ищут ещё и по `id`. В PR description сказано «no changes», но изменение в диффе есть.
6. Changeset `minor` для `@cobaltcore-dev/aurora` и тесты: числовой поиск в `filterBySearchParams.test.ts`, моки tRPC в тестах Ceph/Swift теперь отдают уже отфильтрованный список.

Changeset расходится с кодом. В нём заявлено «Images: owner and size», а PR description добавляет «excluded filter arrays (status, visibility, disk_format)». В ветке shared images (`listSharedImagesByMemberStatus`) поиск по-прежнему идёт только по `id`/`name`.

## Как это реализовано

Код приведён по коммиту `e0737fe`.

### `filterBySearchParams`: числовая ветка

`packages/aurora/src/server/helpers/filterBySearchParams.ts:26-39`:

```ts
  return items.filter((item) =>
    searchFields.some((field) => {
      const value = item[field]
      // Handle strings
      if (typeof value === "string") {
        return value.toLowerCase().includes(searchLower)
      }
      // Handle numbers by converting to string
      if (typeof value === "number") {
        return value.toString().includes(searchLower)
      }
      return false
    })
  )
```

Это подстрочный поиск по *сырому* значению. Поиск `"512"` находит и `512`, и `5120`, а `"0"` находит почти всё. В UI Ceph и Swift `bytes` показывается в человекочитаемом виде, а даты форматируются. Поэтому «поиск по видимым колонкам» здесь на деле означает поиск по сырым данным: запрос «1.5 KB» или дата в формате UI ничего не найдут, а год из ISO-строки найдёт.

В тестах (`filterBySearchParams.test.ts`) ожидания посчитаны верно. Copilot в ревью писал, что кейс `"1"` должен падать, потому что `medium` (count=512) якобы не совпадает. Это ложное срабатывание: `"512"` содержит `"1"`.

### Flavors: отдельный regex-хелпер

`packages/aurora/src/server/Compute/helpers/flavorHelpers.ts:162-181`:

```ts
export function includesSearchTerm(flavor: Flavor, searchTerm: string): boolean {
  const regex = new RegExp(searchTerm, "i")

  // Search across all visible fields in the flavor list: id, name, description, vcpus, ram, disk, swap
  const searchableValues = [
    flavor.id,
    flavor.name,
    flavor.description,
    flavor.vcpus,
    flavor.ram,
    flavor.disk,
    flavor.swap,
  ]
```

Flavors не переведены на `filterBySearchParams`, хотя PR заявляет «unified search». `new RegExp(searchTerm)` без экранирования был и раньше: ввод `(` бросит исключение. PR эту строку не менял, но теперь через неё проходит больше полей.

### Images

`packages/aurora/src/server/Compute/routers/imageRouter.ts:128` (`listImagesWithSearch`) и `:244` (`listImagesWithPagination`):

```ts
          filteredImages = filterBySearchParams(filteredImages, queryInput.name, ["id", "name", "owner", "size"])
```

`imageRouter.ts:1006` (`listSharedImagesByMemberStatus`):

```ts
          filteredImages = filterBySearchParams(filteredImages, name, ["id", "name"])
```

### Ceph: серверная фильтрация после fan-out по метаданным

`packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts:130-136`:

```ts
      return filterBySearchParams(bucketsWithMetadata, searchTerm, [
        "name",
        "count",
        "bytes",
        "last_modified",
        "creationDate",
      ])
```

Фильтр стоит *после* цикла, который для каждого bucket'а делает `ListObjectsV2` батчами по 5 (`containerRouter.ts:62-128`). Поэтому каждый новый поисковый запрос повторяет весь S3 fan-out. Раньше поиск был чисто клиентским и к серверу не ходил. На быстром пути без метаданных (`:57`) фильтр идёт только по `name`.

Клиент, `Ceph/Buckets/index.tsx:153-163` и `:200-201`:

```tsx
  } = trpcReact.storage.ceph.containers.list.useQuery(
    {
      project_id: projectId,
      includeMetadata: true, // Fetch full metadata for table view with sorting
      searchTerm: searchParam, // Server-side filtering
    },
    {
      enabled: !!projectId,
      retry: false, // Don't retry on NO_CEPH_CREDENTIALS error
    }
  )
...
  // Buckets are already filtered server-side via searchTerm
  const filteredBuckets = buckets || []
```

`searchParam` попадает в URL через SearchInput с debounce 500 мс (`index.tsx:330`), значит, новый query key появляется после каждой паузы в наборе.

### Swift

`packages/aurora/src/server/Storage/routers/swift/swiftRouter.ts:134` достаёт `searchTerm` из input, чтобы он не ушёл в query string Swift API. На строке `:168` применяется фильтр:

```ts
        return filterBySearchParams(parsedData.data, searchTerm, ["name", "count", "bytes", "last_modified"])
```

Клиент (`Swift/Containers/index.tsx:169-173`) устроен так же, как у Ceph: передаёт `searchTerm: searchParam`.

### Projects

`packages/aurora/src/client/routes/_auth/projects/index.tsx:36-42`:

```tsx
function ProjectsContent({ searchTerm }: ProjectsContentProps) {
  const [projects] = trpcReact.project.listProjectsWithSearch.useSuspenseQuery({
    searchTerm: searchTerm.trim() || undefined,
  })

  return <ProjectCardView projects={projects} />
}
```

`packages/aurora/src/server/Project/routers/projectRouter.ts:195` задаёт `listProjectsWithSearch`. Тело процедуры построчно повторяет `getAuthProjects` (`:89-129`): те же проверки токена, тот же `Promise.all` на `auth/projects` и `auth/domains`, тот же `domainMap`, то же обогащение `domain_name` (сравните `:127` и `:239`). В конце добавлен фильтр (`:243`):

```ts
      return filterBySearchParams(projectsWithDomain, input.searchTerm, [
        "id",
        "name",
        "description",
        "domain_name",
        "domain_id",
      ])
```

## Что затронуло

- **`storage.ceph.containers.list`.** К input добавлено опциональное поле, так что контракт расширен обратно совместимо. Другие потребители (`Ceph/Objects/CopyObjectModal.tsx:72`, `MoveObjectModal.tsx:75`, `Ceph/hooks/useBucketInfo.ts:50`) `searchTerm` не передают и поведение не меняют. Все `invalidate()` в модалках (Create/Delete/Empty/DeleteVersions bucket, операции с объектами) вызываются без input и по-прежнему задевают все варианты ключа, включая ключи с `searchTerm`. Кэш списка bucket'ов и `useBucketInfo` и раньше жили под разными ключами (`includeMetadata: true` против отсутствия поля), тут ничего не изменилось.
- **`storage.swift.listContainers`.** Ситуация та же. `EditContainerMetadataModal.tsx:88`, `Swift/Objects/CopyObjectModal.tsx:97` и `MoveRenameObjectModal.tsx:106` не затронуты, инвалидации без input работают.
- **`project.getAuthProjects`.** После PR у процедуры не осталось ни одного клиентского потребителя (grep по монорепо находит только определение и `projectRouter.test.ts`). В роутере теперь три пересекающиеся процедуры загрузки проектов: `getAuthProjects`, `searchProjects` (без domain-обогащения, с сортировкой, тоже без клиентских потребителей) и новая `listProjectsWithSearch`. Copilot указал на это дублирование, в PR оно не устранено. Для новой процедуры нет router-тестов.
- **Внешние потребители `AuroraRouter`.** Новая процедура в `project.*` и новые поля input — это аддитивное расширение публичного типа роутера, ничего не ломается.
- **i18n.** Удалены два msgid («X of Y container(s)», «X of Y bucket(s)»), каталоги `messages.ts` перекомпилированы, `check-i18n` не должен падать.
- **UX-контракт выбора (bulk actions) в Storage** незаметно изменился, подробности в ревью.
- **Тесты клиента** теперь мокают уже отфильтрованный ответ сервера. Они проверяют рендер, но не то, что `searchTerm` действительно уходит в запрос.

## Ревью

Ревью выполнено в одном проходе по пяти направлениям из скилла (CLAUDE.md, баги, история, прошлые PR, комментарии в коде) с последующей оценкой уверенности. Ниже только находки с оценкой ≥80.

**1. Каждый новый поисковый запрос в Ceph Buckets и Swift Containers заменяет всю страницу, включая поле поиска, на спиннер загрузки (85/100).** *На 24.09.2026 не исправлено ни в `main`, ни в [#1330](./1330-search-architecture-consistency-ux.md).*
`searchTerm` входит в query key. Каждый debounced-коммит поиска создаёт ключ без кэша, и в TanStack Query v5 (`^5.0.0`) `isLoading` становится `true`. Компонент при этом делает ранний return: `Ceph/Buckets/index.tsx:231-233` (`if (isLoading) return <Status … Loading Buckets... />`) и `Swift/Containers/index.tsx:253-255`. Тулбар с `SearchInput` размонтируется посреди набора: теряется фокус, мигает весь интерфейс. `placeholderData`/`keepPreviousData` не заданы. У Ceph каждое такое переключение ещё и повторяет `ListObjectsV2` по всем bucket'ам (`containerRouter.ts:62-128`). Раньше поиск был мгновенным и клиентским. Copilot отметил стоимостную сторону проблемы, а размонтирование поля поиска — нет.

**2. После серверной фильтрации выбор, сделанный до поиска, перестаёт работать. Это прямо противоречит комментарию в коде (85/100).**
`Ceph/Buckets/index.tsx:269-272`:

```tsx
  // Resolve selected Bucket objects from the full unfiltered list so
  // the modal always operates on what was actually selected — not the filtered
  // subset currently visible in the table.
  const selectedBucketSummaries = (buckets || []).filter((c) => selectedBuckets.includes(c.name))
```

Теперь `buckets` — это уже отфильтрованный сервером список, а не «full unfiltered list». Если пользователь выбрал bucket A и затем ищет B, A остаётся в `selectedBuckets`, но пропадает из `selectedBucketSummaries`. `hasSelection` становится `false`, счётчик и bulk actions не видят выбора. Если очистить поиск, A снова окажется «выбранным». То же в `Swift/Containers/index.tsx:267-272`. Copilot флагнул это для обоих файлов.

> **Обновление 24.09.2026. Частично исправлено до мержа.** В смерженную версию (`6ce6aeac`) попал эффект, который очищает выбор при каждой смене `searchParam`: `Ceph/Buckets/index.tsx:79-84`, `Swift/Containers/index.tsx:80-85`. Массовые действия больше не ломаются, но выбор теперь просто сбрасывается при поиске, то есть поведение выбрано противоположное прежнему. Комментарий «from the full unfiltered list» над `selectedBucketSummaries` / `selectedContainerSummaries` остался и теперь неверен.

**3. Поиск на странице Projects теперь на каждый запрос показывает Suspense-fallback и делает два запроса к Keystone (80/100).** *На 24.09.2026 не исправлено ни в `main`, ни в #1330.*
`projects/index.tsx:37` вызывает `useSuspenseQuery` с `searchTerm` в ключе. `handleSearch` (`:50-52`) вызывает `navigate` без `startTransition`, поэтому каждый новый запрос (debounce 300 мс, `ProjectOverviewNavBar.tsx:32-35`) подвешивает `ProjectsContent`, и вместо карточек появляется «Loading...» (`:73`). Плюс уходят два вызова (`auth/projects` и `auth/domains`). Раньше фильтрация шла по уже загруженному списку без сетевых запросов. Строка поиска остаётся на месте (она вне Suspense), но список мигает при каждом вводе.

Ниже порога. В отчёт как ревью-замечания не входят, но стоит учитывать:

- `listSharedImagesByMemberStatus` ищет только по `id`/`name`, а changeset описывает Images шире, чем реализовано (70).
- `listProjectsWithSearch` дублирует `getAuthProjects`, а `getAuthProjects`/`searchProjects` остались без потребителей. Проще было бы добавить опциональный input в `getAuthProjects` (65).
- Числовой и датовый поиск идёт по сырым значениям, а не по тому, что отображается (50).
- Замечания Copilot про импорты через `../../` уже неактуальны: на head все новые импорты используют `@/`.

---
Проанализировано: 23.09.2026 · коммит `e0737fe` · статус проблем обновлён 24.09.2026 по смерженному `6ce6aeac`
