# PR #1250: fix(aurora): incorrect DataGrid usage in virtualized tables (Swift, Ceph) (#1223)

**Автор:** mark-karnaukh-extern-sap · **Статус:** создан 01.09.2026 → смержен 02.09.2026
**Ветки:** `mark-fix-datagrid-virtualized-tables` → `main` · **Файлов:** 9 (+79/-27)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1250

> Closes #1223.

## Что сделано

Фикс некорректного использования Juno `DataGrid` в виртуализированном теле четырёх таблиц Storage: Ceph `BucketTableView`/`ObjectsTableView` и Swift `ContainerTableView`/`ObjectsTableView`. До PR каждая строка виртуализированного тела оборачивалась в `<div className="juno-datagrid" ...>` — то есть по факту на список из N строк рендерилось N отдельных grid-контейнеров вместо одного. PR заменяет это на единственный `<DataGrid>`-враппер тела с дочерними `<DataGridRow>` на каждую строку — ровно та структура, которую ожидает issue #1223. Заголовок таблиц (`<DataGrid>`/`<DataGridHeadCell>`) не тронут — проблема была только в теле.

Побочный, осознанный эффект: строки получают `role="row"` (через `<DataGridRow>`) вместо прежнего `role="link"`; клик по строке и навигация с клавиатуры (Enter/Space) не изменились — обработчики и `tabIndex={0}` остались на строке.

## Как это реализовано

Паттерн идентичен во всех четырёх файлах. На примере `Ceph/Buckets/BucketTableView.tsx`:

```tsx
// packages/aurora/src/client/routes/.../storage/-components/Ceph/Buckets/BucketTableView.tsx:166-206
<DataGrid
  style={{
    height: `${totalSize}px`,
    width: "100%",
    position: "relative",
  }}
>
  {virtualItems.map((virtualRow) => {
    ...
    return (
      <DataGridRow
        key={bucket.name}
        data-index={virtualRow.index}
        ref={measureElement}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          transform: `translateY(${virtualRow.start}px)`,
          display: "grid",
          gridTemplateColumns: gridColumnTemplate,
          alignItems: "stretch",
        }}
        data-testid={`bucket-row-${bucket.name}`}
        tabIndex={0}
        onClick={handleRowNavigate}
        onKeyDown={...}
      >
```

Раньше на месте `<DataGrid>`/`<DataGridRow>` были обычные `<div>` с ручными классами `juno-datagrid` (враппер тела) и `juno-datagrid group hover:bg-theme-background-lvl-1 cursor-pointer` (строка, только для Buckets/Containers — у Objects-таблиц класс был просто `juno-datagrid`, без hover/cursor). Позиционирование виртуализатора (`position: absolute`, `transform: translateY(...)`) и собственная grid-раскладка строки (`display: "grid"`, `gridTemplateColumns: gridColumnTemplate`) остались как inline `style` — без изменений, один в один.

Важная деталь для правильности этого рефакторинга: у Juno `DataGridRow` (`packages/ui-components/src/components/DataGridRow/DataGridRow.component.tsx` @ juno-ui-components 9.4.0) CSS-класс `.datagrid-row { display: contents }` — сам элемент не создаёт бокса. Строчный inline-`style` каждой строки в PR явно задаёт `display: "grid"`, что как инлайн-стиль перебивает `display: contents` из внешнего CSS-класса — поэтому `position: absolute`/`transform` продолжают работать так же, как и раньше. Проверено для всех 4 файлов — паттерн стиля идентичен (см. `CephObjectsTableView.tsx:470-479`, `SwiftContainerTableView.tsx:215-224`, `SwiftObjectsTableView.tsx:317-326`).

Тестовые изменения зеркальны в 4 файлах — новый регрессионный тест на "один grid, много row":

```tsx
// packages/aurora/src/client/routes/.../Ceph/Buckets/BucketTableView.test.tsx:185-195
// #1223: the virtualized body must be a single grid wrapper with the rows as
// role="row" children — previously each row carried the grid itself (one grid
// per row), causing extra re-renders and broken grid semantics.
test("renders one grid wrapper with row children, not a grid per row", () => {
  renderTableView()
  const body = screen.getByTestId("buckets-table-body")
  const grids = within(body).getAllByRole("grid")
  expect(grids).toHaveLength(1)
  const rows = within(grids[0]).getAllByRole("row")
  expect(rows.length).toBeGreaterThan(1)
})
```

Плюс точечное обновление уже существующей ассерции роли строки в Swift `ContainerTableView.test.tsx` (единственное место в диффе, где раньше проверялся `role="link"`):

```tsx
// packages/aurora/src/client/routes/.../Swift/Containers/ContainerTableView.test.tsx:383-392
test("container rows have tabIndex 0 and role row", () => {
  renderView()
  mockContainers.forEach((c) => {
    const row = screen.getByTestId(`container-row-${c.name}`)
    expect(row).toHaveAttribute("tabindex", "0")
    // Rows now render via Juno's <DataGridRow>, which sets role="row"
    // (previously the row div used role="link"). Row-click / keyboard
    // navigation is unchanged — see the navigation tests above.
    expect(row).toHaveAttribute("role", "row")
  })
})
```

`.changeset/sunny-geckos-read.md` добавляет `patch`-changeset для `@cobaltcore-dev/aurora`, формулировка соответствует сути изменения (performance/layout/accessibility).

## Что затронуло

Изменение полностью внутреннее — публичный контракт компонентов не менялся, ни одна сигнатура пропсов не тронута:

- **Потребители четырёх `*TableView` компонентов.** Каждый импортируется только из своего родного `index.tsx` в той же папке (`Ceph/Buckets/index.tsx`, `Ceph/Objects/ObjectBrowserView.tsx` и `Ceph/Objects/index.tsx` (ре-экспорт), `Swift/Containers/index.tsx`, `Swift/Objects/index.tsx`) — других мест использования в `origin/main` не найдено (`git grep` по именам компонентов вне их собственных директорий). Их же `index.test.tsx`/`ObjectBrowserView.test.tsx` мокают `TableView` целиком (`vi.mock(".../TableView", ...)`), так что внутренняя DOM/role-структура для этих тестов не видна и диффом не задета.
- **Антипаттерн `juno-datagrid` на строку.** `git grep -n "juno-datagrid" origin/main` до PR находит ровно 4 совпадения — все они в четырёх файлах, которые PR и правит. То же для `useVirtualizedTableBody` — используется только этими четырьмя файлами. Значит PR закрывает проблему полностью, без пропущенных виртуализированных таблиц с тем же багом где-то ещё в монорепо.
- **Взаимодействие с недавним PR #1216** ("optimize DataGrid Action column width", `fb23589e`, 28.08.2026) — тот добавил `minContentColumns={[columnCount - 1]}` в **header**-`<DataGrid>` этих же файлов. #1250 header не трогает; body-`<DataGrid>` не получает `columns`/`gridColumnTemplate`-пропсов вовсе (раскладка колонок задаётся per-row через inline `gridTemplateColumns` на каждом `DataGridRow`, как и до PR) — пересечения/регрессии с #1216 нет.
- **Hover/cursor на строке.** У Buckets/Containers убран Tailwind-класс `group hover:bg-theme-background-lvl-1 cursor-pointer` без замены явным классом — но `DataGridRow` сам добавляет `datagrid-row-hoverable` при наличии `onClick` (что у этих строк есть), а CSS-правило `.datagrid-row-hoverable:hover > * { cursor: pointer; background-color: ... }` (juno-ui-components 9.4.0) даёт эквивалентную подсветку/курсор на дочерних ячейках. У Objects-таблиц (Ceph/Swift) `onClick` на строке как не было, так и нет — там и раньше не было hover-подсветки, поведение не изменилось. `group`-класс нигде в этих 4 файлах для `group-hover:` не использовался (проверено `grep`), так что его удаление не задело ничего.

## Ревью

Проблем с уверенностью ≥80 не найдено.

Отдельно проверены места, где такой рефакторинг обычно ломается:
- Конфликт `display: contents` (CSS-класс `DataGridRow`) с inline `position: absolute`/`transform`, нужными виртуализатору — не проблема: inline `style` каждой строки явно перебивает его на `display: "grid"` во всех 4 файлах.
- Потеря hover/cursor-стиля строки при удалении Tailwind-класса — компенсируется встроенным поведением `DataGridRow` (`datagrid-row-hoverable` при наличии `onClick`), различие между Buckets/Containers (есть `onClick`) и Objects (нет `onClick`, hover и раньше не было) сохранено корректно.
- Полнота обновления тестовых ассерций `role="link"` → `role="row"` — единственная такая ассерция во всей PR-диффе (в `ContainerTableView.test.tsx`) обновлена; в остальных трёх test-файлах подобной ассерции на конкретный `role` строки не было ни до, ни после.
- Пересечение с недавним PR #1216 (минимизация ширины Action-колонки через `minContentColumns` на header `DataGrid`) — не пересекается, header не тронут, body раскладка колонок как и раньше идёт per-row.
- Полнота охвата: `juno-datagrid`-антипаттерн и хук `useVirtualizedTableBody` в `origin/main` встречаются ровно в этих 4 файлах — других виртуализированных таблиц с тем же багом, оставленных без исправления, не найдено.
- Соответствие CLAUDE.md — правки локализованы в клиентских компонентах `packages/aurora/src/client`, тесты колоцированы как `*.test.tsx` (по конвенции), changeset добавлен; иных применимых пунктов CLAUDE.md (серверная архитектура, permission keys, роутинг) диф не касается.

---
Проанализировано: 02.09.2026 · коммит `12f54f1e` (head, PR open/unmerged)
