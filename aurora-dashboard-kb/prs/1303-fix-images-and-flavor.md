# PR #1303: fix(portal): fix images and flavor

**Автор:** TilmanHaupt · **Статус:** смержен 16.09.2026 (создан 15.09.2026)
**Ветки:** `til-flav-edit-fix` → `main` · **Файлов:** 14 (+133/-152)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1303

## Что сделано

PR правит UX двух модалок метаданных (Images/Flavors) и попап-меню в Compute (Images, Flavors), плюс терминологию в форме sharing образов. Формально закрывает 6 issue: #1301, #1293, #1296, #1302, #1300, #1294.

**1. Метаданные-модалки** (`EditImageMetadataModal.tsx`, `EditSpecModal.tsx`) — три независимых изменения в одном месте:
- Одиночный клик на "Delete" теперь сразу убирает свойство из локального state — раньше был паттерн "первый клик показывает подтверждение, второй клик удаляет" с authotimeout сбросом через 3 секунды (`confirmDeleteIndex` + `useEffect`/`setTimeout`), полностью убран.
- Заголовок и Save-кнопка модалки стали зависеть от нового пропа `canEdit` (`EditImageMetadataModal`) / уже существовавшего `canEdit` (`EditSpecModal`, введён в #1247): `canEdit ? "Edit Metadata" : "Show Metadata"`, кнопка "Save Changes" рендерится только когда `canEdit`.
- Убрана шапка списка (`DescriptionTerm`/`DescriptionDefinition` "Property Key"/"Value"), вместо неё `<DescriptionList alignTerms="left">`; размер модалки `"large"` → `"xl"`.

**2. Терминология "Member ID" → "Project ID"** (image sharing, #1296): заголовок колонки, текст ошибки валидации, placeholder инпута — во всех местах, где именно они встречаются в UI образов.

**3. Реорганизация попап-меню** (#1302) — в трёх местах (список Flavors, список Images, страница деталей Image) действия отсортированы алфавитно, "Delete" перенесён в конец за `PopupMenuSectionSeparator`.

**4. "Manage Access" скрывается, а не дизейблится**, когда flavor публичный (#1294) — но только в `FlavorListContainer.tsx` (список), не в `$flavorId.tsx` (страница деталей самого flavor) — см. "Что затронуло".

**5.** Один changeset (`patch` на `@cobaltcore-dev/aurora`), локали `en`/`de` обновлены под новые/удалённые строки.

## Как это реализовано

### Одиночный delete в метаданных

`EditImageMetadataModalInner` (`packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/EditImageMetadataModal.tsx:52-166`, головной коммит `8c54ea84d`) раньше держал `confirmDeleteIndex` и таймер:

```tsx
const [confirmDeleteIndex, setConfirmDeleteIndex] = useState<number | null>(null)

useEffect(() => {
  if (confirmDeleteIndex !== null) {
    const timer = setTimeout(() => setConfirmDeleteIndex(null), 3000)
    return () => clearTimeout(timer)
  }
}, [confirmDeleteIndex])
```

Всё это (плюс сброс `confirmDeleteIndex` в `handleEdit`/`handleDelete`, ветвление кнопки "Delete"/"confirm-delete" в JSX) удалено; кнопка удаления теперь один `<Button onClick={() => handleDelete(index)} icon="deleteForever" aria-label={t\`Delete\`} data-testid={\`delete-${entry.key}\`} .../>` без второго шага. Тест `EditImageMetadata.test.tsx:98-115` синхронно упрощён: убран клик по `confirm-delete-${key}` и ожидание текста "Edit Image Metadata" заменено на "Edit Metadata" (заголовок модалки тоже переименован).

Тот же паттерн уже отсутствовал в `EditSpecModal` (Flavors) — там подтверждения удаления никогда не было; изменения в этом файле касаются только пунктов 2 ниже.

### `canEdit` → заголовок/кнопка Save

`EditImageMetadataModal.tsx:391-452` (внешний экспортируемый компонент) прокидывает новый проп `canEdit = true` дальше во `EditImageMetadataModalInner` и в заголовки состояний загрузки/ошибки:

```tsx
if (isLoadingExcluded) {
  return (
    <Modal open onCancel={onClose} size="xl" title={canEdit ? t`Edit Metadata` : t`Show Metadata`}>
```

Для `EditSpecModal` это уже существовавший (#1247) `canEdit`, но модалка резолвит его отдельно — сравните `EditSpecModal.tsx:493,503` (внешний loading/error early-return, использует пропс `canEdit` дословно) с финальным рендером `EditSpecModal.tsx:509-519`, который использует **другую** переменную:

```tsx
return (
  <EditSpecModalInner
    key={flavor.id}
    ...
    canEdit={resolvedCanEdit ?? false}
  />
)
```

`resolvedCanEdit` — состояние, которое заполняется асинхронно (`EditSpecModal.tsx:460-477`) либо из самого пропа `canEdit` (если он передан явно — `canEdit !== undefined ? Promise.resolve(...) : createPermissionsPromise(...)`), либо из `canUser`-запроса. См. "Ревью" — на практике оба вызывающих места передают `canEdit` явным булевым значением, так что расхождение title в loading/error веток не проявляется сегодня, но осталось потенциальной ловушкой.

### Убранная шапка списка / `alignTerms`

`EditSpecModal.tsx:301-304` и `EditImageMetadataModal.tsx` (аналогично):

```tsx
-            <DescriptionList className="mb-6">
-              <DescriptionTerm>{t`Property Key`}</DescriptionTerm>
-              <DescriptionDefinition>{t`Value`}</DescriptionDefinition>
-
+            <DescriptionList className="mb-6" alignTerms="left">
```

`alignTerms` и `PopupMenuSectionSeparator` (используется в реорганизации меню ниже) проверены напрямую в установленном пакете `@cloudoperators/juno-ui-components@9.4.0` (`packages/aurora/node_modules/.pnpm/.../build/components/DescriptionList/DescriptionList.component.d.ts`, `.../PopupMenu/PopupMenu.component.d.ts`) — оба реально существуют в пинованной версии, это не опечатка и не несуществующий проп.

### Терминология Member ID → Project ID

`ImageMemberFormRow.tsx:33`, `ImageMembersTable.tsx:83,201` — три места, все в блоке "поделиться образом":

```tsx
placeholder={t`Enter project ID`}   // было: t`Enter member ID`
...
newErrors.memberId = t`Project ID (project UUID) is required.`   // было: Member ID (...)
...
<DataGridHeadCell>{t`Project ID`}</DataGridHeadCell>   // было: Member ID
```

Локали (`en`/`de` `messages.po`) синхронно теряют старые `msgid` и получают новые; `de` для двух новых строк (`"Show Metadata"`, `"No custom metadata properties found."`) получил пустой `msgstr` — это ожидаемо для непереведённых строк, не блокирует `check-i18n` (только extract/compile).

### Реорганизация попап-меню

Общий паттерн во всех трёх местах: элементы отсортированы алфавитно по видимому лейблу, "Delete" перенесён в конец с `PopupMenuSectionSeparator`. Пример — `FlavorListContainer.tsx:150-176`:

```tsx
<PopupMenuOptions>
  {(canManageSpecs || canListSpecs) && (
    <PopupMenuItem label={canManageSpecs ? t`Edit Metadata` : t`Metadata`} onClick={() => openSpecModal(flavor)} />
  )}
  {canMangageAccess && flavor["os-flavor-access:is_public"] === false && (
    <PopupMenuItem label={t`Manage Access`} onClick={() => openAccessModal(flavor)} />
  )}
  <PopupMenuItem label={t`Show Details`} onClick={() => navigate(...)} />
  {canDeleteFlavor && (
    <>
      <PopupMenuSectionSeparator />
      <PopupMenuItem label={t`Delete Flavor`} onClick={() => openDeleteModal(flavor)} />
    </>
  )}
</PopupMenuOptions>
```

`canMangageAccess` (опечатка "Mangage") — существующее имя переменной, не тронуто этим PR, не относится к диффу.

Такой же паттерн (перестановка + separator) применён в `ImageTableRow.tsx:135-190` и `images/$imageId.tsx:358-403`.

## Что затронуло

**`alignTerms`/`PopupMenuSectionSeparator` — реальные API пинованной версии juno.** Проверено напрямую в установленном `@cloudoperators/juno-ui-components@9.4.0` (см. выше) — не риск.

**`EditImageMetadataModal`'s `canEdit` не используется НИ ОДНИМ вызывающим местом — read-only режим для Images недостижим.** Оба потребителя компонента —

```
packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/$imageId.tsx:451
packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ImageListView.tsx:718
```

— рендерят `<EditImageMetadataModal image=... isOpen=... onSave=... isLoading=... onClose=.../>` без пропа `canEdit`, так что он всегда падает на дефолт `true`. Это не случайность: в обоих местах модалка открывается только из пункта меню "Edit Metadata", который сам уже спрятан за `permissions.canUpdate` (`$imageId.tsx:361-374`, `ImageTableRow.tsx` через `onEditMetadata`, вызывается только внутри `!isExternalImage && permissions.canUpdate`). Т.е. для Images просто не существует сценария "открыть эту модалку без прав на редактирование" — весь новый read-only UI (заголовок "Show Metadata", скрытая кнопка Save) добавлен, но никогда не срабатывает. У Flavors, наоборот, `canEdit` реально прокидывается как `canManageSpecs` из пункта меню, доступного и при `canListSpecs` (без прав на изменение) — там read-only режим осмыслен и работает. PR-описание заявляет параллельную реализацию для "Images & Flavors" — на деле она рабочая только для одной из двух сущностей.

**`$flavorId.tsx` (страница деталей flavor) не обновлён — расходится с `FlavorListContainer.tsx` по обоим пунктам PR.** Тот же паттерн "Manage Access", что чинится в списке (`FlavorListContainer.tsx:158`, теперь скрывается через `flavor["os-flavor-access:is_public"] === false`), в файле `$flavorId.tsx:200` остаётся старым:

```tsx
<PopupMenuItem label={t`Manage Access`} onClick={toggleAccessModal} disabled={isPublicFlavor} />
```

— пункт меню всё ещё дизейблится, а не скрывается, для публичного flavor. Там же (`$flavorId.tsx:206-209`) кнопка метаданных использует старую терминологию, не тронутую этим PR:

```tsx
<Button variant="primary" onClick={toggleSpecModal}>
  {canManageSpecs ? <Trans>Edit Metadata</Trans> : <Trans>Metadata</Trans>}
</Button>
```

вместо новой пары `"Edit Metadata"/"Show Metadata"`, введённой в `EditSpecModal.tsx` этим же PR. `$flavorId.tsx` не входит в список изменённых файлов PR #1303 — обе несогласованности не затронуты диффом.

**Терминология "member ID" вне UI образов не тронута** (`server/Compute/helpers/imageHelpers.ts:360` — текст серверной ошибки) — вне скоупа заявленных issue (#1296 про интерфейс sharing), не репортится как находка.

## Ревью

**[90]** `$flavorId.tsx:200` — страница деталей flavor не мигрирована на паттерн "скрыть, а не дизейблить" пункт "Manage Access" для публичного flavor, хотя PR заявляет закрытие #1294 без оговорки "только в списке". Пользователь, открывший flavor напрямую (не из списка) и находящийся на публичном flavor, продолжает видеть ту же дизейбленную (не скрытую) кнопку, которую issue просил убрать. Верифицировано построчно, воспроизводится в 100% случаев на публичном flavor, независимая переменная `isPublicFlavor` в том же файле подтверждает, что паттерн просто не портирован.

**[80]** `EditImageMetadataModal.tsx` (весь файл) — новый read-only режим (`canEdit=false` → заголовок "Show Metadata", скрытая кнопка Save) недостижим в текущем дереве вызовов: оба потребителя (`$imageId.tsx:451`, `ImageListView.tsx:718`) не передают `canEdit`, а единственный путь открытия модалки уже гейтится на `permissions.canUpdate`. PR-описание прямо заявляет параллельную реализацию для "Metadata Modals (Images & Flavors)" — по факту для Images это мёртвый код на сегодняшний день, а не работающая фича. Не блокирующий бинарный баг (ничего не ломается — дефолт `true` всегда совпадает с реальным правом), поэтому не 90+, но само расхождение с описанием PR и потенциальная ловушка для будущего кода (кто-то один раз в будущем передаст `canEdit={false}` откуда-то не из-под `permissions.canUpdate` — заголовок отработает верно, но специально протестировано это не было) даёт уверенность выше порога.

Ниже порога (не репортится): расхождение title в loading/error ветках `EditSpecModal.tsx:493,503` (использует внешний проп `canEdit`, а финальный рендер — `resolvedCanEdit`) — оба текущих вызывающих места передают `canEdit` явным булевым значением, так что на практике title в loading-состоянии совпадает с итоговым; проявится только если будущий вызывающий код положится на асинхронное разрешение прав через `canUser`, сегодня такого нет (~40/100).

---
Проанализировано: 16.09.2026 · коммит `8c54ea84d`
