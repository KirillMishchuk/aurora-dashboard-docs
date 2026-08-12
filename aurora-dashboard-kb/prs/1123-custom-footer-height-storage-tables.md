# PR #1123: fix(portal): account for custom footer height when sizing storage tables

**Автор:** mark-karnaukh-extern-sap · **Статус:** создан 30.07.2026, смержен 06.08.2026 (коммит `9e817d02`)
**Ветки:** `mark-object-storage-fix-table-view-height-it-2` → `main` · **Файлов:** 5 (+186/-77)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1123

## Что сделано

Прямое продолжение [PR #1090](./1090-viewport-height-storage-tables.md): тот PR заменил захардкоженные оффсеты вьюпорта в четырёх списочных вьюхах object storage (Ceph Buckets/Objects, Swift Containers/Objects) на хук `useAvailableViewportHeight`, который меряет фактическую позицию таблицы сверху, но снизу по-прежнему вычитал фиксированную константу `bottomGap` (52px) — оценку "сколько места занимает футер шелла". Пока футер стандартный, это работало; как только хост-приложение подставляет в слот `pageFooter` свой футер произвольной высоты (через `slots.pageFooter` в `AuroraApp`), оценка расходится с реальностью: более высокий кастомный футер перекрывает последние строки таблицы, более низкий — оставляет пустой зазор снизу.

Этот PR убирает саму необходимость оценивать снизу что-либо: вместо константы хук теперь меряет реальную позицию футера в DOM (`getBoundingClientRect()` на элементе `.app-page-footer`) и берёт её как нижнюю границу доступного пространства. Константа `DEFAULT_BOTTOM_GAP` (52px, значение не изменилось) осталась только как фолбэк на случай, если футера в DOM вообще нет (embedded-режим без слота `pageFooter`). Заодно из хука и его обёртки `useVirtualizedTableBody` убран параметр `bottomGap` — он был нужен только для старой константной логики и ни один из четырёх вызывающих компонентов его не использовал (проверено `git grep` — см. «Что затронуло»), так что удаление чисто внутреннее. Отдельно снижен `MIN_HEIGHT` (пол, ниже которого высота не клэмпится) с 200 до 150px — по комментарию в коде это по-прежнему "пара строк таблицы", просто более щедрый порог для случая мало доступного места.

## Как это реализовано

Раньше нижняя граница была константой; теперь это функция `findBottomBoundary()`, которая ищет DOM-элемент по селектору `.app-page-footer` и, если он есть, возвращает его верхнюю границу (минус небольшой визуальный зазор `GAP = 8px`); если футера нет — старое поведение (низ вьюпорта минус `DEFAULT_BOTTOM_GAP`):

```ts
// packages/aurora/src/client/hooks/useAvailableViewportHeight.ts:46-52
function findBottomBoundary(): number {
  const footer = document.querySelector<HTMLElement>(FOOTER_SELECTOR)
  if (footer) {
    return footer.getBoundingClientRect().top + window.scrollY - GAP
  }
  return window.scrollY + window.innerHeight - DEFAULT_BOTTOM_GAP
}
```

`measure()` теперь читает обе границы явно (верх — от самого элемента, низ — от `findBottomBoundary()`), вместо прежнего "вьюпорт минус верх минус константа":

```ts
// packages/aurora/src/client/hooks/useAvailableViewportHeight.ts:99-112
const measure = () => {
  // Document coordinates for both edges (getBoundingClientRect is
  // viewport-relative, so add scrollY): the element's top and the top of
  // whatever bounds it from below (the page footer, or the viewport). Using
  // document coordinates keeps the difference stable regardless of scroll.
  const top = element.getBoundingClientRect().top + window.scrollY
  const bottom = findBottomBoundary()
  const available = Math.floor(bottom - top)
  // Clamping here can leave the element taller than the space available,
  // which lets the page scroll. That is the intended trade-off — see above.
  const next = Math.max(MIN_HEIGHT, available)
  // Ignore sub-pixel churn so a re-layout cannot toggle the value forever.
  setHeight((previous) => (previous !== undefined && Math.abs(previous - next) < 1 ? previous : next))
}
```

И верх, и низ приводятся к "документным" координатам (`+ window.scrollY`) — оба `getBoundingClientRect()` вызываются синхронно в одном тике `measure()`, так что расхождения из-за скролла между двумя чтениями не возникает; это та же техника, что #1090 уже использовал для верхней границы, теперь применённая и к нижней.

Поскольку футер — не предок измеряемого элемента (это сосед по layout-дереву), а не часть уже отслеживаемой цепочки родителей, изменение его высоты не поймать существующим обходом `element.parentElement`. Поэтому футер отдельно регистрируется в `ResizeObserver`:

```ts
// packages/aurora/src/client/hooks/useAvailableViewportHeight.ts:139-143
// The footer bounds the element from below; a change in its height (custom
// footer content) must trigger a re-measure even though it is not an
// ancestor of the element.
const footer = document.querySelector(FOOTER_SELECTOR)
if (footer) observer.observe(footer)
```

Сам селектор `.app-page-footer` — это обёртка, которую владеет приложение (не библиотечный класс juno-ui-components), чтобы измерение не завязывалось на внутреннюю разметку шелла. Обёртка добавляется в корневом layout вокруг слота `pageFooter`, только когда слот заполнен:

```tsx
// packages/aurora/src/client/routes/__root.tsx:46-55
pageFooter={
  // Wrapped in an app-owned element so the table-height measurement can
  // anchor its bottom edge to the footer without depending on the
  // shell's internal markup. See useAvailableViewportHeight.
  slots?.pageFooter ? (
    <div className="app-page-footer">
      <Slot component={slots.pageFooter} useShadowDOM={false} />
    </div>
  ) : undefined
}
```

Публичная сигнатура хука упростилась — параметр `bottomGap` убран целиком, а не просто перестал использоваться:

```ts
// packages/aurora/src/client/hooks/useAvailableViewportHeight.ts:82 (было: (bottomGap: number = DEFAULT_BOTTOM_GAP))
export function useAvailableViewportHeight<T extends HTMLElement>() {
```

Тесты (`useAvailableViewportHeight.test.tsx`) переписаны под новую механику: вместо одного `vi.spyOn(...).mockReturnValue(...)` на `getBoundingClientRect` (одно и то же значение для любого элемента) теперь один спай на `beforeAll`, читающий из мутируемой мапы `currentRects` по `data-testid` — это позволяет стабить разные `top` для тела таблицы и для футера одновременно, что и требуется для проверки новой логики. Добавлены сценарии: футер выше/ниже (высота таблицы соответственно уменьшается/растёт), отсутствие футера (фолбэк на старую константу), независимость результата от текущего скролла страницы.

## Что затронуло

`useAvailableViewportHeight` и `useVirtualizedTableBody` — внутренние хуки пакета `@cobaltcore-dev/aurora`, используются только четырьмя вьюхами object storage (те же, что после #1090): `BucketTableView.tsx`, `Ceph/Objects/ObjectsTableView.tsx`, `Swift/Containers/ContainerTableView.tsx`, `Swift/Objects/ObjectsTableView.tsx`. `git grep` по всему монорепо на оба имени хука не находит других потребителей — изменение полностью внутреннее.

Удаление параметра `bottomGap` безопасно: ни на момент merge-base, ни сейчас ни один из четырёх вызовов `useVirtualizedTableBody({...})` в этих вьюхах его не передавал (проверено на обеих версиях кода) — параметр был мёртвым с точки зрения реальных вызовов ещё до этого PR, PR просто убрал его из сигнатуры.

Слот `pageFooter` — часть публичного контракта `AuroraApp` (`packages/aurora/README.md`, секция Slots). Сама форма слота (какой компонент туда передаётся и как рендерится через `<Slot>`) не изменилась — PR добавляет только внутреннюю обёртку `<div className="app-page-footer">` вокруг уже существующего рендеринга слота, поэтому `packages/aurora/README.md` не требует обновления и не было тронуто. `apps/dashboard` (эталонное приложение-потребитель) слот `pageFooter` вообще не использует — проверено `git grep`, так что для него это изменение не наблюдаемо.

## Ревью

Через диф прогнаны параллельно: CLAUDE.md/AGENTS.md-комплаенс, bug-scan, historical context (`git log`/`git blame`), prior-feedback (KB-отчёт по #1090 плюс индекс других отчётов) и comment-compliance. Одна методологическая деталь: `AGENTS.md`, на который обычно ориентируется комплаенс-проверка, в апстриме (`origin/main`, откуда взят этот PR) не существует — апстрим ещё не содержит такого гайда. Комплаенс-проверка вместо этого сверялась с реальными документами апстрима: `CONTRIBUTING.md`, `docs/aurora_architecture_overview.md`, `packages/aurora/README.md` — нарушений не найдено (границы `-components/`/route-файлов соблюдены, контракт слота `pageFooter` не менялся, changeset по форме совпадает с другими реальными changeset'ами репозитория, тестовый файл соответствует конвенциям colocated-vitest-jsdom).

**Проблем с уверенностью ≥80 не найдено.**

Кандидаты, не прошедшие порог (для полноты — на будущее, чтобы не искать заново):

- Гипотеза, что `ResizeObserver` подписывается на футер только в момент первого запуска эффекта (`useAvailableViewportHeight.ts:142-143`, зависимость `[element]`), и если элемент `.app-page-footer` появится в DOM позже — на него никогда не подпишутся, а `measure()` продолжит использовать константный фолбэк. При перепроверке: `measure()` всё равно каждый раз заново делает `document.querySelector`, так что расчёт не "залипает" на устаревшем значении, если пересчёт вообще случится; а пересчёт в реальности почти наверняка случится — вставка/удаление футера меняет layout flex-колонки шелла, что задевает уже отслеживаемых предков элемента (`element.parentElement`-цепочка), которые и так под наблюдением. Сценарий "футер появляется уже после первого рендера таблицы" к тому же не соответствует единственному реальному месту использования — слот `pageFooter` определяется на уровне корневого layout при инициализации `AuroraApp`, а не переключается динамически после монтирования вложенных таблиц. Итоговая оценка независимого агента: 45/100 — архитектурно кейс возможен, но маловероятен на практике и смягчён побочным эффектом от отслеживания предков.
- Гипотеза, что `document.querySelector(FOOTER_SELECTOR)` — глобальный, не заскоупленный к конкретному инстансу селектор, и при встраивании `AuroraApp` дважды на одной странице обе таблицы найдут один и тот же (первый по document order) футер. При перепроверке: весь хук и так завязан на постранично-глобальные API (`window.innerHeight`, `window.scrollY`, `window.addEventListener("resize", ...)`, `document.body` как корень наблюдения) — мульти-инстансное встраивание `AuroraApp` на одной странице уже не поддерживалось бы этим кодом (и архитектурой `AuroraApp` в целом — свой роутер, свой QueryClient, своя i18n-обёртка на инстанс) независимо от этого PR. Не новая проблема, вносимая этим PR, а существующее допущение, с которым PR просто консистентен. Оценка: 0/100.

---
Проанализировано: 06.08.2026 · коммит `5564e487a4adedbea72cbcdc0592c9e837288e21`
