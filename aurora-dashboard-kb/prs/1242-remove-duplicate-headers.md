# PR #1242: refactor(dashboard): remove duplicate breadcrumbs and old headers

**Автор:** vlad-schur-external-sap · **Статус:** смержен 01.09.2026 (создан 01.09.2026)
**Ветки:** `vlad-1134-issue` → `main` · **Файлов:** 16 (+151/-186)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1242

> Closes #1134.
>
> **Исправление 01.09.2026:** первая версия этого отчёта ошибочно поднимала до confidence 85 находку о том, что страница деталей Security Group теряет навигацию "назад к списку" после удаления page-local `<Breadcrumb>`. Это неверно — автор (Kiryl) указал на реальный постоянный breadcrumb вверху страницы, отчёт был перепроверен и находка снята (см. "Что сделано" ниже, где теперь описан механизм `ProjectInfoBox`, который был упущен в первом проходе). Отчёт ниже — исправленная версия; общий вывод по PR (2 находки → осталась 1) изменился.

## Что сделано

Issue #1134 просил унифицировать шапки страниц Floating IPs и Security Groups под уже существующий общий компонент `ContentHeader` (`packages/aurora/src/client/components/ContentHeader/ContentHeader.tsx` — не новый, не тронут этим PR; введён ещё в PR #999/#1006/#1009 для остальных сервисных страниц). До этого PR обе страницы использовали устаревший паттерн: голый `ContentHeading` на уровне route-файла плюс (для Security Groups) отдельный компонент `SecurityGroupHeader` с собственным заголовком и **ещё одним, page-local `<Breadcrumb>`** внутри `SecurityGroupDetailsView`/`$securityGroupId/index.tsx`.

Важный контекст, упущенный в первой версии этого отчёта: в приложении уже существует отдельный, постоянный (persistent) breadcrumb — компонент `ProjectInfoBox` (`packages/aurora/src/client/components/ProjectView/ProjectInfoBox.tsx`), смонтированный один раз в layout-файле `packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:193` прямо над `<Outlet />`, то есть присутствующий на **каждой** странице проекта, включая обе страницы, которые трогает этот PR. Он строит цепочку "Home → Project → Network → Security Groups → <имя группы>" (с кликабельными элементами) из полей `crumb`/`sectionCrumb`/`isDetail`/`intermediateCrumb` в `staticData` активного route-а (`RouteInfo`, `routeInfo.ts`) — эти поля уже были объявлены в `$securityGroupId/index.tsx:17-26` (`crumb: { labelKey: "Security Groups", to: "/projects/$projectId/network/securitygroups" }`) и этим PR не менялись. То есть page-local `<Breadcrumb>`, которую PR убирает из `SecurityGroupDetailsView`, была **дублирующей** — второй, отдельной breadcrumb-строкой поверх уже работающей глобальной. Именно это, судя по всему, и имеет в виду заголовок PR под "duplicate breadcrumbs".

С учётом этого, PR вводит новый общий `<ContentHeader title=... projectId=... description=... actions=...? />` на самом верхнем уровне четырёх страниц вместо двух параллельных, частично дублирующих друг друга паттернов (`ContentHeading` на уровне route + локальные `Breadcrumb`/`SecurityGroupHeader` на уровне деталей):
- **Floating IPs, список** (`floatingips/index.tsx` → `FloatingIpsList.tsx`): `ContentHeading` убран из route-файла, `ContentHeader` теперь рендерится самим `FloatingIpsList`.
- **Floating IP, детали** (`$floatingIpId/index.tsx` → `FloatingIpDetailsView.tsx`): аналогично — `ContentHeading` в route-файле удалён, `ContentHeader` теперь в `FloatingIpDetailsView`, туда же перенесён весь `actions`-блок (Edit/Attach/Detach/Release).
- **Security Groups, список** (`securitygroups/index.tsx` → `SecurityGroupsList.tsx`): та же схема.
- **Security Group, детали** (`$securityGroupId/index.tsx`): `ContentHeading` + page-local `Breadcrumb`/`BreadcrumbItem` заменены на `ContentHeader`; отдельный компонент `SecurityGroupHeader.tsx` удалён целиком (был единственным потребителем `ContentHeading` внутри `SecurityGroupDetailsView`). Глобальный breadcrumb от `ProjectInfoBox` при этом остаётся нетронутым и продолжает работать как раньше.

Три файла (`compute/flavors.tsx`, `compute/images.tsx`, `network/floatingips/index.tsx`) попутно мигрируют search-schema с устаревшего `z.object(...).passthrough()` на `z.looseObject(...)` — эквивалентная замена (zod v4), но `flavors.tsx`/`images.tsx` при этом вообще не участвуют в самой задаче шапок (см. "Ревью"). Один незначительный побочный фикс: `.changeset/optimize-datagrid-action-columns.md` (ожидающий релиза changeset от уже смerженного #1216) поправлен с несуществующего имени пакета `@cloudoperators/aurora` на реальное `@cobaltcore-dev/aurora` — без этого фикса changeset был бы формально «пустым» для инструмента Changesets.

## Как это реализовано

### Глобальный breadcrumb (`ProjectInfoBox`) не тронут и продолжает давать навигацию назад

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:189-201 (не тронут этим PR)
<div className="min-w-0 flex-1">
  <ProjectInfoBox projectInfo={{ id: projectId, name: crumbProject?.name || projectId, domain: crumbProject?.domain }} />
  <Outlet />
</div>
```
```tsx
// packages/aurora/src/client/components/ProjectView/ProjectInfoBox.tsx:73-109 (не тронут этим PR)
if (info.crumb) {
  const { labelKey, label, to, useParamAsLabel } = info.crumb
  ...
  if (info.isDetail) {
    items.push({ label: resolvedLabel, onClick: () => navigate({ to: to as never, params }) })
    ...
    const title = deepest.meta?.find((m) => m != null && "title" in m)?.title as string | undefined
    if (title) items.push({ label: title, active: true })
  }
}
```
```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/$securityGroupId/index.tsx:17-26 (не тронуто этим PR)
staticData: {
  ...
  isDetail: true,
  sectionCrumb: { labelKey: "Network" },
  crumb: { labelKey: "Security Groups", to: "/projects/$projectId/network/securitygroups" },
} satisfies RouteInfo,
```
Эти три куска (layout-компонент, глобальный breadcrumb-компонент и route `staticData`) не изменены этим диффом ни на строку — они уже работали до PR и продолжают работать после. Итоговая цепочка на странице деталей security group: Home → Project → Network → **Security Groups** (кликабельно, ведёт на список) → название группы (активный элемент). Ровно то же самое предоставляла удалённая page-local `<Breadcrumb>` — только дублируя её.

### `FloatingIpDetailsView` — адрес Floating IP теперь показан дважды

```tsx
// FloatingIpDetailsView.tsx:27-28 (не тронуто диффом)
const networkRoutingItems: DetailListItem[] = [
  { label: t`Floating IP Address`, value: floatingIp.floating_ip_address || `—` },
  ...
]
...
// FloatingIpDetailsView.tsx:49-52 (новое)
<ContentHeader
  title={floatingIp.floating_ip_address ?? floatingIp.id}
  ...
```
До PR заголовок `<ContentHeading>{floatingIp.floating_ip_address}</ContentHeading>` рендерился в родительском route-файле (`$floatingIpId/index.tsx`), а не внутри `FloatingIpDetailsView` — то есть в изолированном юнит-тесте `FloatingIpDetailsView.test.tsx` адрес встречался один раз (только в `networkRoutingItems`). Теперь заголовок переехал внутрь того же компонента, и адрес отображается дважды на одной странице. Сам PR это подтверждает — 3 ассершна в `FloatingIpDetailsView.test.tsx` переведены с `getByText(...)` (падает при >1 совпадении) на `getAllByText(...).length > 0`, вместо удаления строки `Floating IP Address` из `networkRoutingItems` как избыточной. См. "Ревью", находка №1. (Для Security Groups аналогичного эффекта нет: `SecurityGroupBasicInfo` показывает Name/ID в таблице так же, как показывал и раньше, независимо от заголовка — эта пара дублировалась и до PR, PR её не меняет.)

## Что затронуло

Все четыре страницы — листовые route-компоненты с ровно одним потребителем (`FloatingIpsList`, `FloatingIpDetailsView`, `SecurityGroups`/`SecurityGroupsList`, `SecurityGroupDetailsView` нигде больше не импортируются). `ContentHeader` — переиспользуемый компонент, использовался и раньше на других страницах; этот PR не меняет сам компонент, только добавляет ему двух новых потребителей и убирает старый параллельный паттерн (голый `ContentHeading` + для Security Groups ещё и дублирующий page-local `Breadcrumb` рядом с уже работающим глобальным `ProjectInfoBox`). Удалённый `SecurityGroupHeader.tsx` не имел других потребителей (только `SecurityGroupDetailsView`, обновлён в этом же PR) — безопасное удаление, барrel-экспорт (`-details/index.ts`) поправлен соответствующе.

Оба списковых компонента (`FloatingIpsList`, `SecurityGroupsList`) теперь используют `useRouteContext`/`useMatches`/`useParams` (через `ContentHeader`) — оба юнит-теста получили нужные моки (`FloatingIpsList.test.tsx` мокает сам `ContentHeader` целиком; `SecurityGroupsList.test.tsx` мокает три хука `@tanstack/react-router` напрямую). Других потребителей этих списков, которым бы такой мок тоже понадобился, в кодовой базе нет (единственные совпадения на `SecurityGroups`/`FloatingIpsList` вне их собственных файлов — сами route-файлы, уже обновлённые в этом PR).

## Ревью

**Найдено (confidence ≥ 80):**

1. **`FloatingIpDetailsView` теперь показывает адрес Floating IP дважды на одной странице.** (confidence 80)
   Заголовок страницы (`ContentHeader title={floatingIp.floating_ip_address ?? floatingIp.id}`, строка 50) и поле `Floating IP Address` в таблице "Network & Routing" (`networkRoutingItems`, строка 28, не тронуто этим диффом) показывают одно и то же значение. До PR это не проявлялось как дублирование на уровне компонента, потому что заголовок рендерился в родительском route-файле, а не внутри `FloatingIpDetailsView` — перенос заголовка внутрь того же компонента, который уже показывал это же поле в таблице, и создал дублирование. PR это заметил (иначе не пришлось бы чинить тесты), но исправил тесты под новое поведение (`getByText` → `getAllByText(...).length > 0`, 3 места в `FloatingIpDetailsView.test.tsx`), а не убрал избыточную строку из таблицы — то есть тесты теперь документируют дублирование как ожидаемое, а не как временный артефакт. Частично противоречит заявленной в заголовке PR цели "remove duplicate ... headers" (хотя для breadcrumbs эта цель как раз выполнена корректно — см. "Что сделано").
   Файлы: `FloatingIpDetailsView.tsx:28,50`, `FloatingIpDetailsView.test.tsx` (4 применённых `getAllByText`).

**Также замечено (confidence 50-79, не набрало полной уверенности):**
- **[70]** `compute/flavors.tsx` и `compute/images.tsx` получили изменение `z.object(...).passthrough()` → `z.looseObject(...)` (эквивалентная замена под zod v4), при этом ни один из этих двух файлов не имеет отношения к заявленной теме PR (breadcrumbs/headers) — в обоих файлах это вообще единственная строка диффа. Ни описание PR, ни существующий changeset этого PR не упоминают миграцию на `z.looseObject`. Само изменение безвредно и, судя по всему, полностью завершено в рамках клиентских route-схем (других `.passthrough()` в `packages/aurora/src/client/routes/**` на головном коммите не осталось), но для читателя истории PR остаётся неочевидным, зачем два файла без единой другой правки попали в диф про шапки страниц.
- **[55]** `.changeset/optimize-datagrid-action-columns.md` (ожидающий релиза changeset уже смerженного #1216) поправлен с несуществующего имени пакета `@cloudoperators/aurora` на настоящее `@cobaltcore-dev/aurora` — легитимный и нужный фикс (без него changeset не привязался бы ни к одному реальному пакету в Changesets), но тоже никак не связан с темой этого PR и нигде не упомянут в его описании.

---
Проанализировано: 01.09.2026 · коммит `e80ea3ea` · исправлено 01.09.2026 (снята ошибочная находка о потере breadcrumb-навигации после проверки автором)
