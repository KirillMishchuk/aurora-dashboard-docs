# PR #1247: feat(aurora): refactor EditSpecModal to match EditImageMetadataModal design

**Автор:** andypf · **Статус:** open (не смержен), создан 01.09.2026
**Ветки:** `andypf/refactor-edit-spec-modal` → `main` · **Файлов:** 11 (+980/-868)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1247

## Что сделано

PR переделывает две модалки Flavor-детальной страницы — `EditSpecModal` (редактирование extra specs флейвора) и `ManageAccessModal` (доступ приватных флейворов к проектам) — под дизайн, уже принятый в `EditImageMetadataModal` (Images). Раньше `EditSpecModal` был устроен на `use()`+`Suspense`+`ErrorBoundary`, с отдельными компонентами `SpecFormRow`/`SpecRow` и точечными мутациями (каждое добавление/удаление spec — свой немедленный API-вызов с тостом "успешно добавлено/удалено"); `ManageAccessModal` был устроен аналогично, с отдельными `TenantAccessFormRow`/`TenantAccessRow` и подтверждением удаления через клик-и-подожди-3-секунды в `TenantAccessRow`. Оба компонента полностью переписаны на паттерн "локальный черновик + пакетное сохранение": все правки (добавление/переименование/изменение значения/удаление строк) копятся в локальном state, реальные tRPC-мутации отправляются одним махом только по кнопке `Save Changes` в футере `Modal`, а `Cancel`/крестик отбрасывают черновик. `TenantAccessFormRow.tsx` и `TenantAccessRow.tsx` при этом удалены как файлы — их роль поглотил `ManageAccessModal.tsx` напрямую. Сопутствующий changeset (`patch`) и правки локализации en/de (новые и удалённые строки под новую формулировку "Property"/"Project" вместо "Metadata"/"Tenant").

## Как это реализовано

**Батч-модель данных** — у каждой модалки свой параллельный набор состояний: черновой список (`specs`/`access`), флаг `isNew` для ещё не сохранённых на бэкенде строк и `originalKey`/`originalValue`/`originalProjectId` для отслеживания, что именно изменилось относительно `initialSpecs`/`initialAccess` (`EditSpecModal.tsx:27-45`, `ManageAccessModal.tsx:26-43`).

**Пакетное сохранение `EditSpecModal`** (`EditSpecModal.tsx:192-243`) — на `handleSubmit` из diff'а между `specs` и `initialSpecs` собираются ключи на удаление (удалённые строки плюс старые ключи переименованных) и объект на создание/обновление, затем bracketing-вызовы выполняются последовательно:

```tsx
// EditSpecModal.tsx:219-235
// Delete removed/renamed specs
for (const key of new Set(keysToDelete)) {
  await client.compute.deleteExtraSpec.mutate({
    project_id: project,
    flavorId: flavor.id,
    key,
  })
}

// Create/update specs
if (Object.keys(specsToSave).length > 0) {
  await client.compute.createExtraSpecs.mutate({
    project_id: project,
    flavorId: flavor.id,
    extra_specs: specsToSave,
  })
}
```

Удаление конкретной строки в UI — мгновенное, без какого-либо подтверждения (`EditSpecModal.tsx:165-168`):

```tsx
// EditSpecModal.tsx:165-168
const handleDelete = (index: number) => {
  setSpecs(specs.filter((_, i) => i !== index))
  setErrors({})
}
```

**Пакетное сохранение `ManageAccessModal`** зеркалит ту же схему без переименований — только add/remove (`ManageAccessModal.tsx:135-176`):

```tsx
// ManageAccessModal.tsx:152-168
// Remove projects
for (const targetProjectId of projectsToRemove) {
  await client.compute.removeTenantAccess.mutate({ project_id: project, flavorId: flavor.id, targetProjectId })
}

// Add projects
for (const targetProjectId of projectsToAdd) {
  await client.compute.addTenantAccess.mutate({ project_id: project, flavorId: flavor.id, targetProjectId })
}
```

**Кнопка Save Changes задизейблена** пока нет изменений/идёт редактирование/добавление строки — `disableConfirmButton={isSubmitDisabled}` в обеих модалках, где `isSubmitDisabled` учитывает `isAddingNew` и (только в `EditSpecModal`) `specs.some(e => e.isEditing)` (`EditSpecModal.tsx:96`, `ManageAccessModal.tsx:98`) — это реально не даёт потерять недосохранённую inline-правку молчаливым закрытием кнопки подтверждения.

**DescriptionList-layout** воспроизводит `EditImageMetadataModal`: заголовок колонок `Property Key`/`Value` (`EditSpecModal.tsx:295-297`), у `ManageAccessModal` — фиксированный лейбл `Project` с редактируемым `TextInput` только для новой строки, существующие записи — просто `<span>` без возможности inline-редактирования (`ManageAccessModal.tsx:283-308`), что соответствует "editable Project ID value" из описания PR как "добавление", а не "правка существующих".

## Что затронуло

`EditSpecModal`/`ManageAccessModal` (Flavors) используются ровно в двух местах, оба — часть той же страницы Flavor:

- `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/$flavorId.tsx`
- `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/FlavorListContainer.tsx`

Оба потребителя передают тот же набор пропов, что и раньше (`client`, `isOpen`, `onClose`, `project`, `flavor`, `canEdit` для `EditSpecModal`) — контракт компонентов не изменился, changeset `patch` обоснован. `TenantAccessFormRow`/`TenantAccessRow` потребителей вне удалённого `ManageAccessModal.tsx` не имели. Совпадения `ManageAccessModal`/`manageAccessModal` в `ImageListView.tsx` и `ContainerTableView.test.tsx` — это локальные идентификаторы несвязанной Swift/Images-модалки, не импорт удаляемого/меняемого компонента; реального внешнего использования вне Flavor-страницы нет.

## Ревью

Проверено соответствие CLAUDE.md (тесты колоцированы как `*.test.tsx`, `-components` конвенция не нарушена, changeset добавлен и промаркирован верно), сопоставлены locale-диффы `en`/`de` с реально используемыми в коде `t\`...\`` строками (все новые строки на месте, удалённые строки — от логики, которая целиком убрана вместе с точечными тостами, "осиротевших" ключей не найдено), проверена история `git log --follow` по обоим файлам и дельта относительно версии на `origin/main`. Отдельно сверено с уже выставленными на этом PR review-комментариями бота Copilot (`api.github.com/repos/.../pulls/1247/comments`) — часть из них (JSON.stringify в React key, отсутствие `translateError` для `loadError`, отсутствие `errortext` на поле значения при inline-редактировании, дубли в `keysToDelete`) при прямой проверке текущего head **не подтвердились** — соответствующий код уже использует `key={flavor.id}`, `translateError(loadError)`, `errortext={errors[...]}` на обоих полях и дедуплицирует `keysToDelete` через `new Set(...)` перед циклом удаления — то есть эти комментарии устарели (относятся к более раннему пушу в этот же PR) и в отчёт не включены. Две находки независимо подтверждены и Copilot-ботом на этом же PR, и прямой проверкой кода/истории:

1. **Заявленный в PR body и changeset "confirm-delete pattern with 3-second timeout" для `EditSpecModal` в коде отсутствует** (confidence 95) — `EditSpecModal.tsx:165-168`. И PR description ("Add confirm-delete pattern with 3-second timeout"), и сам changeset `.changeset/refactor-flavor-modals.md:9` дословно обещают этот паттерн для `EditSpecModal`. По факту `handleDelete` удаляет строку из локального состояния одним кликом, без какого-либо подтверждения и без `setTimeout`/`confirm`-state — ни в `EditSpecModal.tsx`, ни в `EditSpecModal.test.tsx` (проверено grep по `timeout|confirm|3000|setTimeout` — совпадений в контексте удаления нет, есть только пропы `Modal`). Проверка истории показала, что этот паттерн (`useState` + `setTimeout(..., 3000)` + двухфазная кнопка) реально существовал в этом PR — но в **удалённом** `TenantAccessRow.tsx` (`origin/main`, `TenantAccessRow.tsx:19-59`), который относился к `ManageAccessModal`, а не к `EditSpecModal`; и был там законно убран согласно другому пункту того же changeset ("Remove confirm-delete pattern \[from ManageAccessModal\] (unnecessary with batch save)"). Судя по всему, при написании description/changeset формулировку для `ManageAccessModal` по ошибке продублировали как "добавление" для `EditSpecModal`, хотя там паттерна не было ни до, ни после PR (в версии на `origin/main` до PR в `EditSpecModal.tsx` тоже нет ни одного упоминания `timeout`/`confirm`). Независимо подтверждено тем же комментарием Copilot на этом PR (path `EditSpecModal.tsx`, line 414: "The PR description / changeset claims a confirm-delete pattern with a 3-second timeout for EditSpecModal, but spec deletion here happens immediately"), актуален для текущего head.
2. **Пакетное сохранение обеих модалок сначала удаляет/отзывает, потом создаёт/добавляет — сбой на втором шаге после успеха первого приводит к реальной потере данных, а не просто к ошибке в UI** (confidence 85) — `EditSpecModal.tsx:219-235` (delete-loop `deleteExtraSpec` до create-вызова `createExtraSpecs`) и симметрично `ManageAccessModal.tsx:152-168` (remove-loop `removeTenantAccess` до add-loop `addTenantAccess`). Если после успешного удаления/отзыва часть вызовов доходит, а последующий create/add падает (сетевой сбой, конфликт ключа, серверный лимит — например, для extra specs в этой же кодовой базе уже есть строка локализации "Metadata size exceeds the 2KB limit..." под ровно такой сценарий превышения лимита при пакетной правке), `catch` в `handleSubmit` лишь показывает `saveError` и держит модалку открытой — но удалённые на бэкенде ключи/доступы уже удалены, а новые/заменяющие так и не созданы: `specs`/`access` в локальном state при этом не откатываются к пред-сабмитному виду и не совпадают с реальным состоянием сервера. Более того, повторный клик "Save Changes" пересчитывает diff от того же устаревшего `initialSpecs`/`initialAccess` (данные не перезапрашиваются после ошибки), то есть попытается удалить/отозвать уже отсутствующий на сервере ключ/доступ повторно. Для `ManageAccessModal` это означает, что пользователь может непреднамеренно **отозвать доступ к флейвору у части проектов**, так и не выдав его новому, при том что модалка выглядит как "ничего не подтверждено". Независимо подтверждено Copilot-ботом на этом же PR отдельными комментариями для каждого файла (`EditSpecModal.tsx:235` — "users can lose metadata even though the modal stays open with an error"; `ManageAccessModal.tsx:168` — "the user can end up unintentionally revoking access (partial update)"), актуально для текущего head.

Ниже порога (не репортится): гипотеза о потере правок при закрытии модалки крестиком/`Cancel` во время идущего `handleSubmit` (обе модалки не передают `disableCancelButton`/`disableCloseButton` во время `isSaving`, в отличие от 14+ delete-модалок в этом же репозитории, которые это делают) — при прямой проверке референсного `EditImageMetadataModal`, который эта PR явно обязана copировать по дизайну, выяснилось, что сам референс **тоже** не блокирует Cancel/крестик во время сохранения; то есть это не отклонение от паттерна, который эта PR обязана была скопировать, а свойство самого скопированного паттерна — оценка 40/100, не репортится.

---
Проанализировано: 02.09.2026 · коммит `6d7db860` (head, PR open/unmerged)
