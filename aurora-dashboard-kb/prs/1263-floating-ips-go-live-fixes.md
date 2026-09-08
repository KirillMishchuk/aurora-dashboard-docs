# PR #1263: fix(network): issues to fix before Floating IPs Go-Live

**Автор:** vlad-schur-external-sap · **Статус:** open (создан 03.09.2026)
**Ветки:** `vlad-floatingips-issues-before-go-live` → `main` · **Файлов:** 27 (+395/-282)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1263

## Что сделано

PR закрывает список мелких, но блокирующих релиз проблем в фиче Floating IPs (Epic #1201) перед go-live. Изменения не добавляют новую функциональность, а исправляют UX/поведение уже существующих экранов: страницы деталей floating IP, модалок allocate/attach/detach/release/edit и списка floating IP.

Три содержательных изменения поведения выделяются на фоне остальных (в основном косметических) правок:

1. **Общее состояние ошибки между модалками.** Все четыре модалки floating IP (edit, attach/associate, detach, release) используют один и тот же общий `useFloatingIpMutations()` хук с двумя мутациями (`update`, `delete`). Раньше ошибка одной мутации могла "утекать" в другую модалку, если пользователь закрывал одну и открывал другую до сброса состояния. Теперь `FloatingIpActionModals` оборачивает каждый `toggle*Modal` в `toggle*ModalWithReset`, который сбрасывает `updateError`/`deleteError` непосредственно перед открытием/закрытием модалки.
2. **Создание floating IP теперь ведёт на страницу деталей вместо toast-уведомления.** `AllocateFloatingIpModal` после успешного создания вызывает `navigate()` на маршрут деталей нового ресурса вместо показа toast — соответствующий helper `getFloatingIpAllocatedToast` полностью удалён.
3. **Attach — теперь единственное основное действие** на странице деталей floating IP; остальные действия (Edit Description, Detach, Release) перенесены в выпадающее kebab-меню.

Остальные правки: длинные описания обрезаются через CSS `truncate` (в таблице и в `TwoColumnDescriptionList`), состояния loading/error/not-found переведены на компонент Juno `Status` вместо самодельной Stack+Spinner-разметки, добавлены toast-уведомления на все CRUD-операции (кроме create — см. пункт 2), действие "Preview" переименовано в "Show Details", поле сортировки в списке сведено к единственному варианту "Status" (вместо восьми), кнопки Cancel/Close блокируются на время pending-мутации.

## Как это реализовано

### Страница деталей: Attach как primary action + Status для loading/error

`FloatingIpDetailsView.tsx:60-77` — вместо `ButtonRow` с четырьмя равноправными кнопками теперь `PopupMenu` с тремя пунктами плюс отдельная primary-кнопка Attach:

```tsx
<Stack gap="0.5" alignment="center">
  <PopupMenu className="flex items-center">
    <PopupMenuToggle as="div">
      <Button icon="moreVert" title={t`Floating IP actions`} />
    </PopupMenuToggle>
    <PopupMenuOptions>
      <PopupMenuItem label={t`Edit Description`} onClick={toggleEditModal} />
      <PopupMenuItem label={t`Detach`} onClick={toggleDetachModal} />
      <PopupMenuItem label={t`Release`} onClick={toggleReleaseModal} />
    </PopupMenuOptions>
  </PopupMenu>
  <Button variant="primary" className="whitespace-nowrap" onClick={toggleAttachModal}>
    {t`Attach`}
  </Button>
</Stack>
```

`$floatingIpId/index.tsx:84-98` объединяет прежние отдельные ветки `isError` и `!floatingIp` в одну, используя Juno `Status`:

```tsx
if (isError || !floatingIp) {
  const errorMessage = error?.message || t`Error loading floating IP`
  return (
    <Status
      status="error"
      title={isError ? errorMessage : t`Floating IP not found`}
      action={<Button onClick={handleBack} variant="primary"><Trans>Back to Floating IPs</Trans></Button>}
    />
  )
}
```

### Общий сброс ошибок между модалками + навигация после Release

`FloatingIpActionModals.tsx:42-71` — хук `useFloatingIpMutations` теперь также отдаёт `resetUpdateError`/`resetDeleteError`, обёрнутые в четыре `toggle*WithReset`-функции:

```tsx
const toggleEditModalWithReset = () => {
  resetUpdateError()
  toggleEditModal()
}
// ...аналогично toggleAttachModalWithReset, toggleDetachModalWithReset (resetUpdateError)
// и toggleReleaseModalWithReset (resetDeleteError)
```

`useFloatingIpMutations.ts:74-75` просто пробрасывает `.reset` самой мутации react-query наружу:

```ts
resetUpdateError: updateMutation.reset,
resetDeleteError: deleteMutation.reset,
```

Дополнительно, `FloatingIpActionModals.tsx:93-108` (`handleReleaseWithToast`) теперь проверяет через `useMatches()`, находится ли пользователь на странице деталей удалённого floating IP, и если да — редиректит на список:

```tsx
const isOnDetailsPage = matches.some(
  (route) => route.routeId === "/_auth/projects/$projectId/network/floatingips/$floatingIpId/"
)
if (isOnDetailsPage) {
  navigate({ to: "/projects/$projectId/network/floatingips", params: { projectId } })
}
```

### Allocate: редирект вместо toast

`AllocateFloatingIpModal.tsx:108-113`:

```tsx
handleClose()
navigate({
  to: "/projects/$projectId/network/floatingips/$floatingIpId",
  params: { projectId, floatingIpId: created.id },
})
```

Раньше здесь вызывался `toast.success(...)` через `getFloatingIpAllocatedToast` — helper удалён целиком вместе с тестами на него; проверено `git grep` по всему монорепо — висячих ссылок не осталось.

### Блокировка Cancel/Close во время pending-мутаций

Единообразно добавлено в `AllocateFloatingIpModal.tsx:144-145`, `AssociateFloatingIpModal.tsx:82-83`, `EditFloatingIpModal.tsx:79-80`:

```tsx
disableCancelButton={isPending /* или isLoading */}
disableCloseButton={isPending /* или isLoading */}
```

### Обрезание длинных значений (truncate)

`TwoColumnDescriptionList.tsx:24-28,33-39` — каждое значение теперь обёрнуто в `<div className="truncate">`:

```tsx
<DescriptionDefinition>
  <div className="truncate">{value}</div>
</DescriptionDefinition>
```

`FloatingIpTableRow.tsx:42-44` — то же самое для колонки Description в таблице:

```tsx
<DataGridCell>
  <div className="truncate">{floatingIp.description || "—"}</div>
</DataGridCell>
```

### Переименование Preview → Show Details

`FloatingIpTableRow.tsx:50` и синхронно обновлённый комментарий в `constants.tsx:32`:
`"", // empty column for item-actions with context menu containing "Show Details", "Edit Description", "Attach", "Detach" and "Release"`.

### Сортировка сведена к Status

`FloatingIpsList.tsx:18,47`:

```ts
const DEFAULT_SORT_KEY = "status"
// ...
options: [{ label: t`Status`, value: "status" }],
```

Раньше было 8 вариантов (`fixed_ip_address`, `floating_ip_address`, `floating_network_id`, `id`, `router_id`, `status`, `tenant_id`, `project_id`) с дефолтом `fixed_ip_address`.

### Локали

`packages/aurora/src/locales/{de,en}/messages.po` и `messages.ts` — чисто механическая регенерация lingui-экстрактором, 1:1 соответствует строковым изменениям в `.tsx`-файлах (проверено по `git log` — паттерн совпадает с тем, как эти файлы обычно трогают в истории репозитория).

## Что затронуло

- **`TwoColumnDescriptionList` — общий компонент**, используется не только в floating IPs, но и в `FlavorDetailsView.tsx`, `ImageDetailsView.tsx` и `SecurityGroupBasicInfo.tsx`. Добавление `<div className="truncate">` вокруг каждого `value` затрагивает все три экрана. В большинстве случаев `value` — обычная строка, где `truncate` безобиден и даже полезен. Но в `FlavorDetailsView.tsx:16` и `ImageDetailsView.tsx:106,142` поле `ID` передаётся как `<ClipboardText text={...} />` — компонент с `inline-flex`-разметкой (текст + иконка копирования). Оборачивание такого компонента в `overflow-hidden; white-space-nowrap` может обрезать иконку копирования для длинных ID на этих (не относящихся к floating IPs) экранах. Тестов на этот сценарий (long ID + ClipboardText внутри `TwoColumnDescriptionList`) в диффе нет.
- **`getFloatingIpAllocatedToast`** удалён полностью — `git grep` по всему монорепо на `150fe4ecbeed745c5a553ca710a65e11672f6d98` подтверждает отсутствие висячих ссылок.
- **`useFloatingIpMutations`, `FloatingIpActionModals`, `FloatingIpActionModalTriggers`** — используются только внутри директории `floatingips/`, внешних потребителей нет (проверено `git grep` по монорепо).
- Ветка PR — сквош-незавершённая история из пяти коммитов (`7716e0e → 312cb6d → 55d2c2a → 54fc687 → 150fe4e`). В частности, коммит `54fc687` ("fix(network): ai comments and missed changeset") уже в рамках этой же ветки исправил `TwoColumnDescriptionList` с `<span className="truncate">` на `<div className="truncate">` — `truncate` не работает на инлайновом `span` без `display:block`. Итоговый дифф, который видит ревьюер на GitHub, уже содержит исправленную версию.

## Ревью

**Гонка при Release со страницы деталей — риск кратковременного/устойчивого "Floating IP not found" перед редиректом** (уверенность 80/100)

- `useFloatingIpMutations.ts:51-52`: `onSettled` у `deleteMutation` вызывает `utils.network.floatingIp.getById.invalidate(...)` для только что удалённого id — безусловно, без проверки текущего маршрута.
- `FloatingIpActionModals.tsx:93-108`: `handleReleaseWithToast` вызывает `navigate()` прочь со страницы деталей только *после* `await handleDelete(...)` (т.е. после того как `onSettled` уже отработал) и после показа toast.

Поскольку страница деталей (`$floatingIpId/index.tsx`) на момент вызова `invalidate()` всё ещё смонтирована (навигация ещё не произошла), react-query считает запрос `getById` активным и немедленно рефетчит его — для ресурса, которого уже не существует. Это типично приводит к `isError=true` и рендеру `Status status="error"` / "Floating IP not found" (`$floatingIpId/index.tsx:85-98`) до того, как асинхронный `navigate()` успевает размонтировать компонент. Путь детерминированный — это основной сценарий "Release со страницы деталей", а не редкий edge-case, поэтому пользователь будет видеть эффект (мигание, а в медленной сети — заметную задержку) при каждом релизе с этой страницы.

Возможное направление исправления (не проверялось на практике): вызывать `navigate()` сразу после успешного `handleDelete`, до/без инвалидации `getById` для удалённого id, либо использовать `removeQueries`/явный `setData(undefined)` вместо `invalidate` для этого конкретного id, либо явно пропускать `getById`-инвалидацию, когда удаляемый id совпадает с id текущего открытого маршрута деталей.

Прочих проблем с уверенностью ≥80 не найдено. Проверено отдельно и признано корректным: логика `toggle*ModalWithReset` (сброс ошибки никогда не происходит поверх ошибки, которую пользователь ещё должен увидеть, т.к. Cancel/Close заблокированы на время pending); соответствие комментария в `constants.tsx:32` фактическому содержимому kebab-меню; согласованность с существующими конвенциями кодовой базы (переход на `Status`, паттерн "redirect вместо toast после create" уже применялся в `SecurityGroupsList.tsx`, парность `disableCancelButton`/`disableCloseButton` используется в 15+ других модалках); история изменений `TwoColumnDescriptionList` (правка `truncate` — сознательный fix внутри этой же ветки, а не регресс более раннего исправления). В репозитории на текущий момент (`150fe4ecbeed745c5a553ca710a65e11672f6d98`) не найден трекаемый файл `CLAUDE.md`, несмотря на то что workspace-заметка (`SAP/CLAUDE.md`) ссылается на `aurora-dashboard/CLAUDE.md` — стоит проверить у пользователя, не был ли файл случайно удалён или переименован.

---
Проанализировано: 08.09.2026 · коммит `150fe4e`
