# PR #1189: feat(aurora): allow consumers to register custom srevices

**Автор:** taymoor89 (Taimoor Aslam) · **Статус:** открыт, не смержен (создан 20.08.2026)
**Ветки:** `1102-support-custom-services` → `main` · **Файлов:** 61 (+840/-7582)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1189

> Закрывает issue #1102. Коммит заголовка содержит опечатку — "srevices" вместо "services"; формат `<type>(<scope>): <subject>` для commitlint это не нарушает (проверяется только тип/скоуп, не орфография).

## Что сделано

PR вводит общий механизм расширения `AuroraApp` — новый проп `additionalProjectServices`, позволяющий консьюмеру зарегистрировать свой проект-скоуп-сервис (клиентские роуты + пункт навигации) без форка пакета — и одновременно, в том же PR, целиком удаляет из OSS-пакета встроенную реализацию PCA (Clavis): серверный роутер, Zod-схемы, весь клиентский UI и тесты под `services/pca/**`, i18n-строки. Формулировка из changeset'а: «This replaces the previously hardcoded PCA (Clavis) integration. PCA and any other consumer-specific service should now be registered this way rather than living inside the OSS package.»

Итог для консьюмера: вместо жёстко вшитого «PCA всегда есть» пакет теперь ничего специфичного не знает про PCA — если он нужен, приложение-консьюмер регистрирует его само через новый API, при этом получая тот же UX (пункт в нав-секции «Services», карточка на странице проекта), что раньше давал встроенный PCA.

## Как это реализовано

### Новый публичный API `AuroraApp`

`AdditionalProjectService` — новый экспортируемый тип (`packages/aurora/src/client/AuroraApp.tsx:64-78`):

```ts
export type AdditionalProjectService = {
  /** OpenStack catalog service type, e.g. `"pca"`. */
  serviceType: string
  /** OpenStack catalog service name, e.g. `"clavis"`. */
  serviceName: string
  /** Nav item and service card label. */
  label: string
  routes: AnyRoute
}
```

и новый проп на `AuroraAppProps` (`AuroraApp.tsx:115-116`): `additionalProjectServices?: AdditionalProjectService[]`. Активация сервиса завязана на то же условие, что раньше проверяла `canAccessClavisPca` для PCA — присутствие `serviceType`/`serviceName` в каталоге OpenStack проекта плюс (если задан) `enabledServices`.

### Вживление роутов в дерево TanStack Router

Самая нетривиальная часть — `createAuroraRouter` (`packages/aurora/src/client/router.ts:12-45`) теперь принимает третий параметр `additionalProjectServices` и до создания роутера вручную дописывает переданные роуты в дерево:

```ts
const parent = parentFn() as unknown as RouteWithChildren
const existing = parent.children ?? {}
parent._addFileChildren({ ...existing, [`_extra_${i}`]: route })
```

(`router.ts:26-28`). Каждый элемент `additionalProjectServices[].routes` обязан иметь `options.getParentRoute` (по конвенции — указывающий на новый `servicesRoute`), иначе бросается `Error` (`router.ts:23-24`). Новый файл-роут `services.tsx` (`packages/aurora/src/client/routes/_auth/projects/$projectId/services.tsx`, создан этим PR) — минимальный layout-роут, который и служит точкой подвеса:

```tsx
export const Route = createFileRoute("/_auth/projects/$projectId/services")({
  component: () => <Outlet />,
})
export { Route as servicesRoute }
```

`servicesRoute` экспортирован из публичного `packages/aurora/src/client/index.ts` вместе с `RouteInfo`/`Crumb`/`isRouteInfo` — консьюмеру нужно всё это, чтобы собрать свой под-роут и передать его в `additionalProjectServices`.

### Навигация и карточки на странице проекта

`buildNavSections.ts` (`packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts`) убрал хардкод `canAccessClavisPca`/`clavisServices` и завёл `Map` встроенных секций (compute/network/storage/services), в которую цикл (строки 117-128) домешивает разрешённые доп.сервисы:

```ts
for (const module of additionalProjectServices ?? []) {
  if (!serviceIndex[module.serviceType]?.[module.serviceName]) continue
  if (enabledServices && !enabledServices.includes(module.serviceType)) continue
  sectionMap.get("services")?.services.push({ ... navigate: (nav) => nav({ to: module.routes.fullPath as never, params: { projectId } as never }) })
}
```

Аналогичный цикл в `$projectId/index.tsx:102-114` рисует карточку сервиса на странице обзора проекта, но строит ссылку иначе — не через `nav({ to, params })`, а строковой подстановкой: `additionalService.routes.fullPath.replace("$projectId", projectId)` (`index.tsx:111`, подробнее в разделе «Ревью»).

### Серверные экспорты

`packages/aurora/src/server/index.ts` теперь дополнительно экспортирует `validateOpenstackService` (существовавший ранее внутренний хелпер, начиная с #850, впервые сделан публичным) и `parseOrThrow` (ранее — внутренний хелпер `Network/helpers`, использовался только `pcaRouter.ts`/floating-ip роутерами) — оба нужны консьюмеру, чтобы писать свой BFF-роутер в тех же конвенциях, что описывает `CLAUDE.md` («routers must be built with the exported `auroraRouter`»). `routers.ts` убрал `serviceRouters` (бывший `Services/routers` с единственным содержимым — PCA) из `buildBaseRouter` (`routers.ts:6,15`).

### Прочее

Из `packages/aurora/package.json` убраны зависимости `@peculiar/x509` и `reflect-metadata` (использовались только PCA-парсингом CSR/сертификатов) — `git grep` по `pr-1189-head` не находит больше ни одного импорта ни того, ни другого. `apps/dashboard/package.json` добавил `@tanstack/router-plugin` в devDependencies (нужен, по-видимому, для регенерации `routeTree.gen.ts`). Changeset `move-pca-to-sci-scope-modules.md` помечен `minor`.

## Что затронуло

**Собственный design-doc пакета устарел.** `packages/aurora/docs/0011_clavis.md` — design-doc, описывающий PCA/Clavis-интеграцию во всех деталях (роуты, компоненты, состояния) — этим PR не тронут вообще (`git diff` по файлу пуст), хотя описываемая функциональность полностью удалена. Он продолжает утверждать «The active UI entry point is the project service route at `/projects/$projectId/services/pca/`» и т.д. — то есть теперь описывает код, которого больше нет, без пометки «устарело» и без указателя на новый `additionalProjectServices`.

**Наша собственная KB на это тоже завязана.** `DOCS/aurora-dashboard-kb/05-domain-map.md` в этой базе знаний ссылается на `0011_clavis.md` как на «living doc, current scope» для строки Services — PCA/Clavis. Если этот PR смержится в текущем виде, наш domain-map тоже станет неточным (ссылается на design-doc, который описывает удалённую функциональность) — стоит учесть при следующем прогоне `update-kb` после мержа.

**Свежая работа по PCA удаляется день в день.** Merge-base этого PR (`35095b4f`) — это ровно голова `main` сразу после мержа PR #1177 (19.08.2026, «different changes(api/ui-ux) with downloading functionality» — скачивание/импорт сертификатов, рефакторинг `parseCsrInfo` и т.д.). PR #1189 удаляет весь этот код на следующий день (коммиты 20.08.2026). Ни commit-сообщения, ни changeset не упоминают #1177 или то, что только вчера смерженная функциональность выбрасывается целиком — стоит явно сверить с автором #1177 (или консьюмером PCA), что эта работа перенесена/учтена на стороне будущей внешней реализации, а не потеряна.

**Публичный контракт расширяется без раздувания серверного роутинга.** Grep по `pca`/`clavis` за пределами удаляемых файлов показывает, что упоминания остаются только в `CHANGELOG.md` (историческая запись, ожидаемо), `docs/0011_clavis.md` (см. выше) и — что важнее — в `README.md` дважды (см. «Ревью»). Никакой другой код/тест за пределами удаляемых файлов и правок этого PR не ссылается на `pca`/`Clavis`, `serviceRouters` или сам `pcaRouter` — то есть удаление серверной/клиентской части внутренне самодостаточно и ничего стороннего не роняет.

**Проверено и не является проблемой:** самостоятельная security-правка path traversal (#1153, `validateAndEncodeResourceId`) внутри `pcaRouter.ts` была самодостаточной — общий хелпер живёт в `signal-openstack` и продолжает использоваться остальными роутерами (`flavorRouter`, `floatingIpRouter`, `securityGroupRouter`, `projectRouter`), удаление `pcaRouter.ts` её не затрагивает.

## Ревью

**[100] `README.md` не обновлён под новый публичный проп `additionalProjectServices` — единственную содержательную фичу PR.** `CLAUDE.md` прямо называет `packages/aurora/README.md` источником истины при изменении публичных пропсов `AuroraApp`: «treat that file as the source of truth when changing any of `AuroraApp`'s public props». Таблица пропсов (`README.md:117-125`) заканчивается на `enabledServices` и не содержит ни строки, ни примера использования для `additionalProjectServices`/`AdditionalProjectService` — консьюмер, открывший README сегодня, не узнает о существовании этого механизма вообще.

**[100] `README.md` в двух местах продолжает называть `"pca"` действующим встроенным сервис-ключом, хотя этот же PR удаляет всю встроенную реализацию PCA.** `README.md:176` («**Service key reference:** ... `"pca"`») и `README.md:203` («**Available service keys:** ... `"pca"`») не тронуты этим PR — при этом после мержа `"pca"` не существует нигде во встроенном коде пакета. Консьюмер, следующий этой инструкции, будет ожидать рабочий сервис-ключ, которого не будет.

**[80] `createAuroraRouter` мутирует общий модуль-синглтон `routeTree`, не сбрасывая его между вызовами — роуты могут накапливаться при повторных вызовах фабрики.** `router.ts:26-28` берёт родительский роут через `parentFn()`, который возвращает объект из общего дерева `routeTree` (импортированного один раз из `./routeTree.gen`), и вызывает `parent._addFileChildren({...existing, [`_extra_${i}`]: route})`. Реализация `_addFileChildren` в `@tanstack/router-core` мутирует сам объект роута (`this.children = ...; return this`), а не клонирует его; ничего в `createAuroraRouter` не очищает `parent.children` перед примешиванием. Поскольку `AuroraApp` — публикуемая библиотека, встраиваемая внешними консьюмерами (а не единственная фиксированная страница, которую контролируют мейнтейнеры), повторный вызов этой фабрики в рамках одного загруженного экземпляра модуля — HMR-remount в dev-режиме, второй смонтированный `<AuroraApp/>` на той же странице, или просто future test-suite для `router.ts` (которого сейчас нет) — будет дописывать `_extra_i` поверх того, что уже приросло от предыдущих вызовов, без механизма удаления старых. Ни один тест на `router.ts` в PR не добавлен, так что CI это не поймает.

*Проверено и не подтвердилось (ниже порога ≥80, не репортится отдельно):* orphaned-файлы `PcaToastNotifications.tsx`/`.test.tsx` (не удалены вместе с остальным PCA-UI, но и ни на что не влияют — мёртвый код); `additionalService.routes.fullPath.replace("$projectId", projectId)` в `index.tsx:111` — работает при документированном ограничении «один `$projectId`-сегмент», но менее надёжно, чем соседний `nav({ to, params })`-подход в `buildNavSections.ts:125`; типизация `RouteWithChildren.children` как `Record<string, AnyRoute>` в `router.ts:9` не совпадает с реальной формой (массив) — расхождение только на уровне типов, на поведение не влияет.

---
Проанализировано: 20.08.2026 · коммит `c086aa4`
