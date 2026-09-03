# PR #1254: feat(aurora): refactor breadcrumb generation

**Автор:** taymoor89 · **Статус:** open (не смержен), создан 02.09.2026
**Ветки:** `1252-refactor-breadcrumbs` → `main` · **Файлов:** 35 (+1129/-727)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1254

## Что сделано

Закрывает issue #1252. PR заменяет монолитный, захардкоженный на конкретный роутер способ построения хлебных крошек (`ProjectInfoBox`, `packages/aurora/src/client/components/ProjectView/ProjectInfoBox.tsx`, удалён этим PR) на набор генерик-примитивов, публикуемых из пакета — с явной целью дать встраиваемым под-приложениям (SCI-сервисы со своим `RouterProvider`) возможность участвовать в общей цепочке крошек OSS-хоста.

Раньше вся логика построения breadcrumb-цепочки жила в одном компоненте `ProjectInfoBox`, который вручную ходил по `useMatches()`, искал самый глубокий матч под `/_auth/projects/$projectId`, и собирал 1–3 крошки из специального мини-DSL в `staticData` каждого роута (`labelKey`/`label`/`useParamAsLabel`/`sectionCrumb`/`intermediateCrumb`/`isDetail`/`useParentTitleAsLabel` — семь разных полей на одну схему). Компонент был жёстко завязан на конкретный `useMatches()`/`useParams()` от OSS-роутера и принимал `projectInfo` пропом снаружи — использовать его вне `$projectId.tsx` было невозможно.

Новая модель — два независимых источника крошек на каждый матч роута:

- **Статические** — `staticData.crumb: { text, to?, icon? }` (typed via `satisfies RouteInfo`), для меток, известных на этапе сборки;
- **Динамические** — `useSetBreadcrumb(routeId, text, { to? })`, вызываемый из компонента роута, для меток, известных только в рантайме (имя ресурса из API) — регистрирует крошку в `DynamicBreadcrumbContext` и снимает её при анмаунте.

Оба источника читает единый `useBreadcrumbs()` — генерик-хук, не завязанный на конкретный инстанс роутера, поэтому пригодный и для встроенных под-приложений. `usePushBreadcrumbs(items)` — обратный канал: под-приложение публикует свой список крошек в `BreadcrumbExtensionContext`, а OSS-компонент `Breadcrumbs` (переименованный `ProjectInfoBox`, перенесён в `components/Breadcrumbs.tsx`) дописывает их после собственной цепочки.

Старый мини-DSL в `routeInfo.ts` (`CRUMB_LABEL_KEYS`/`labelKey`/`useParamAsLabel`/`sectionCrumb`/`intermediateCrumb`/`isDetail`/`useParentTitleAsLabel`) полностью выпилен; вместо enum-меток теперь используются Lingui `msg` message descriptors (`text: MessageDescriptor | string`), резолвящиеся в `useBreadcrumbs()` через `useLingui()`.

~18 роут-файлов под `compute/flavors*`, `compute/images*`, `network/floatingips*`, `network/securitygroups*`, `storage/**` переведены на новую схему — большинство мест мехонично: `sectionCrumb`/`crumb: { labelKey }` → `crumb: { text: msg\`...\` }` в статичных роутах, `useSetBreadcrumb(Route.id, ...)` в компонентах детальных страниц.

## Как это реализовано

**Ядро — `useBreadcrumbs()`** (`packages/aurora/src/client/hooks/useBreadcrumbs.ts:25-77`) читает `useMatches()`, фильтрует матчи, у которых либо `staticData.crumb` задан, либо есть запись в `DynamicBreadcrumbContext` по `routeId`:

```ts
const crumbMatches = matches.filter(
  (m) => (isRouteInfo(m.staticData) && (m.staticData as RouteInfo).crumb) || dynamicCrumbs.has(m.routeId)
)
```
(`useBreadcrumbs.ts:42-44`), и для каждого матча резолвит текст/иконку/`to` с приоритетом «динамическая крошка важнее статической» (`useBreadcrumbs.ts:50-56`), последняя крошка помечается `active: true` без `onClick`, все остальные получают `onClick: () => navigate({ to: crumbTo ?? match.pathname, ... })` (`useBreadcrumbs.ts:57-65`) — если явный `to` не задан, используется `match.pathname`, накопленный TanStack Router для этого матча (см. ниже про хвост `$projectId`/`$storageType`, где `to` сознательно не передаётся).

Дополнительно хук умеет пристроить «служебную» крошку под серверный расширяющий сервис (SCI), если текущий URL матчит `serviceType`-параметр и он найден в `additionalProjectServices` из route-контекста (`useBreadcrumbs.ts:68-74`) — этот пункт помечается `active: true` без своего `onClick`; довести его до кликабельного состояния (когда есть расширения) — задача вызывающей стороны.

**`useSetBreadcrumb`** (`hooks/useSetBreadcrumb.ts:12-23`) регистрирует/снимает крошку в `useLayoutEffect` с cleanup:

```ts
useLayoutEffect(() => {
  if (text) {
    setCrumb(routeId, { text, to })
  } else {
    setCrumb(routeId, null)
  }
  return () => setCrumb(routeId, null)
}, [routeId, text, to, setCrumb])
```

deps-массив содержит только примитивы (`routeId`, `text`, извлечённый `to`, стабильный `setCrumb` из `useCallback`) — вызывающий код может передавать `{ to: "..." }` инлайн-объектом на каждый рендер без риска бесконечного цикла (сам `options` в deps не участвует).

**`usePushBreadcrumbs`** (`hooks/usePushBreadcrumbs.ts:13-23`) сериализует список в строковый ключ (`label:icon:active` через запятую) и обновляет контекст только когда ключ меняется; отдельным эффектом с пустыми deps чистит контекст при анмаунте хоста.

**Контексты.** `DynamicBreadcrumbContext`/`DynamicBreadcrumbProvider` (`context/DynamicBreadcrumbContext.tsx:5-26`) — `Map<routeId, Crumb>`, монтируется в `routes/_auth.tsx:28-30` (обёртывает `<Outlet/>` на уровне всего аутентифицированного дерева — именно там, где требует комментарий в `useSetBreadcrumb.ts:9`). `BreadcrumbExtensionContext`/`BreadcrumbExtensionProvider` (`context/BreadcrumbExtensionContext.tsx:5-17`) — монтируется на уровень ниже, в `routes/_auth/projects/$projectId.tsx:199-202`, ровно там, где требует комментарий `usePushBreadcrumbs.ts:10`.

**`Breadcrumbs`** (`components/Breadcrumbs.tsx:8-53`, бывший `ProjectInfoBox`) сводит два потока: берёт `useBreadcrumbs()` и, если есть непустой `extensionCrumbs` из `BreadcrumbExtensionContext`, деактивирует последнюю OSS-крошку (сервисный лейбл), выдаёт ей `onClick` для возврата на корень сервиса, и дописывает `extensionCrumbs` следом (`Breadcrumbs.tsx:15-39`). В отличие от старого `ProjectInfoBox`, новый `Breadcrumbs` не принимает пропов — данные о проекте приходят через `useSetBreadcrumb(Route.id, projectLabel)`, вызванный прямо в `$projectId.tsx:105-107` (та же логика "domain/project", что раньше собиралась внутри `ProjectInfoBox`, просто переехала к вызывающей стороне).

**Публичные экспорты** (`packages/aurora/src/client/index.ts:25-28`, добавлено этим PR):

```ts
export { usePushBreadcrumbs } from "./hooks/usePushBreadcrumbs"
export { useSetBreadcrumb } from "./hooks/useSetBreadcrumb"
export { useBreadcrumbs, type BreadcrumbItem } from "./hooks/useBreadcrumbs"
export { DynamicBreadcrumbContext, DynamicBreadcrumbProvider } from "./context/DynamicBreadcrumbContext"
```

Сам компонент `Breadcrumbs` (UI-виджет OSS) в барреле не экспортируется — и это осмысленно: контракт для под-приложений — это `useBreadcrumbs`/`useSetBreadcrumb`/`DynamicBreadcrumbProvider`/`usePushBreadcrumbs`, рендерит крошки всегда сам OSS.

**Репрезентативные примеры конвертации роутов.** Статический (`compute/flavors.tsx:18-26`): `sectionCrumb: { labelKey: "Compute" }, crumb: { labelKey: "Flavors" }` → просто `crumb: { text: msg\`Flavors\` }`. Динамический (`compute/images/$imageId.tsx:43-50` + `:112`): `staticData` больше не содержит `crumb` вообще (`isDetail`/`sectionCrumb`/старый `crumb` с `useParamAsLabel` выпилены), а `RouteComponent` вызывает `useSetBreadcrumb(Route.id, image?.name as string | undefined)` после того как имя образа приходит из tRPC-запроса.

Одно место потребовало структурного, не механического изменения: `storage/$provider/$storageType.tsx` — новый файл (layout-роут, `21` строка), добавленный именно для того, чтобы у "Object Storage (Swift/Ceph)" появился свой матч с собственной динамической крошкой (`useSetBreadcrumb` внутри `StorageTypeLayout`, `$storageType.tsx:12-20`), а список бакетов переехал в `$storageType/index.tsx`. Из-за этого сдвига импорт `Route` в `storage/-components/Ceph/Buckets/index.tsx` (и его тесте) поменялся с `.../$storageType` на `.../$storageType/index` — оба места в диффе синхронно обновлены, несостыковок нет.

`routeTree.gen.ts` перегенерирован автоматически (не ревьюился построчно) — состав новых/переименованных роутов в нём (в частности новый layout-роут `$storageType`) соответствует ручным правкам, расхождений с hand-written роутами не найдено.

## Что затронуло

**Новая публичная поверхность и потребители.** `client/index.ts` добавляет 6 новых публичных символов: `useBreadcrumbs`, `type BreadcrumbItem`, `useSetBreadcrumb`, `usePushBreadcrumbs`, `DynamicBreadcrumbContext`, `DynamicBreadcrumbProvider`. `git grep` по каждому имени на `origin/main` (за пределами файлов, которые сам этот PR меняет) не находит ни одного упоминания — это подтверждает то, что и заявлено в PR/changeset: символы полностью новые, потребителей вне пакета (в частности, в `apps/dashboard`) пока нет, ломать нечего.

**`ProjectInfoBox` → `Breadcrumbs`: переименование безопасно.** На `origin/main` `ProjectInfoBox` не экспортировался из `client/index.ts` и использовался только в одном месте — `routes/_auth/projects/$projectId.tsx` (плюс его колоцированный тест). Оба места переведены на новый `Breadcrumbs` в этом же PR; внешних импортов по прямому пути (`@cobaltcore-dev/aurora/client/components/ProjectView/ProjectInfoBox` и т.п.) в остальной кодовой базе не найдено — переименование не является breaking change для консьюмеров пакета.

**README (пакета) не обновлён под новую публичную поверхность — см. «Ревью», единственная находка с уверенностью ≥80.**

**Не регрессия, а уборка мёртвого кода: пропажа секционной крошки "Compute"/"Network"/"Storage".** На первый взгляд PR убирает промежуточный уровень цепочки (было `Home > Compute > Flavors`, стало `Home > Flavors`) — ни один из 18 сконвертированных роутов не переносит секционную метку в новую схему. Но `git show origin/main:.../ProjectInfoBox.tsx` показывает, что старый код добавлял `sectionCrumb` в цепочку только по условию `if (info.sectionCrumb?.to)` (`ProjectInfoBox.tsx:67`) — а во всех 12 мест использования `sectionCrumb` в `origin/main` передавался только `{ labelKey: "Compute" }` и т.п., без `to`. То есть секционная крошка не рендерилась уже на `main` до этого PR — этот путь стал мёртвым ещё в `3e782219 feat(portal): simplify breadcrumb — omit section group label (#937)`, задолго до текущего PR. Рефакторинг просто убрал код, который и так никогда не исполнялся; поведение для пользователя не меняется.

**E2E-тесты breadcrumb (`apps/dashboard/e2e/ui/project-detail.spec.ts`), которые этот PR не трогает, по коду остаются справедливы.** Тест проверяет, что комбинированная крошка "Domain/Project" неактивна на overview и становится кликабельной на под-роутах, ведя обратно на overview. По новой реализации: `useSetBreadcrumb(Route.id, projectLabel)` в `$projectId.tsx:107` без `to` → на под-роуте `crumbTo ?? match.pathname` резолвится в `match.pathname` матча `$projectId`, что и есть путь `/projects/$projectId` — совпадает с ожиданием теста. Формат метки (`domain/project`) собирается той же логикой (`$projectId.tsx:105-106`), что раньше жила внутри `ProjectInfoBox`. Тест не проверялся запуском (E2E требует реального стенда), но по трассировке кода расхождений с его ожиданиями не найдено.

## Ревью

**[95] `packages/aurora/README.md` не документирует ни один из шести новых публичных экспортов, хотя PR прямо и единственно ради этого их и вводит.** `CLAUDE.md` называет `packages/aurora/README.md` источником истины для консьюмерского контракта пакета («treat that file as the source of truth when changing any of `AuroraApp`'s public props»), и changeset этого PR сам формулирует цель как «for use in embedded sub-apps and standalone consumers» — то есть аудитория именно внешние читатели README, не только maintainers. Диф PR не касается `README.md` вообще (`git grep README` по `/tmp/pr1254.diff` — пусто) ни в корне, ни в `packages/aurora/`. В README нет ни слова про `useBreadcrumbs`, `useSetBreadcrumb`, `usePushBreadcrumbs`, `DynamicBreadcrumbProvider`/`DynamicBreadcrumbContext`, ни примера, как под-приложению подключить эти примитивы к своему `RouterProvider`. Это ровно тот же паттерн, который уже был зафиксирован как находка [100] в ревью PR #1189 (`prs/1189-custom-project-services.md`) для `additionalProjectServices` — и на момент этого PR остаётся неисправленным для новой порции публичного API. Разработчик, открывший README сегодня, не узнает о существовании breadcrumb-примитивов вообще.

*Проверено и не подтвердилось (ниже порога ≥80, не репортится отдельно):* пропажа секционной крошки "Compute"/"Network"/"Storage" — не регрессия, см. «Что затронуло» (условие рендера было мёртвым с #937 задолго до этого PR); edge-case в `Breadcrumbs.tsx:15-39`, где при `hasExtensionTrail === true`, но не найденном в `additionalProjectServices` сервисе, последняя OSS-крошка ошибочно получила бы "кнопку назад к сервису" — ветка технически недостижима в штатном потоке (URL с `serviceType`-параметром существует только если сервис зарегистрирован и, значит, найдётся); типы/deps-массивы `useSetBreadcrumb`/`usePushBreadcrumbs` (mount-порядок провайдеров, cleanup при анмаунте, стабильность `setCrumb`/`setBreadcrumbs`) проверены построчно — логика корректна и соответствует комментариям в файлах.

---
Проанализировано: 02.09.2026 · коммит `b70f667c` (head, PR open/unmerged)
