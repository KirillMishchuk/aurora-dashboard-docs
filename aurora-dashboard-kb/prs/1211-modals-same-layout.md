# PR #1211: refactor(portal): refactor all modals to the same layout

**Автор:** TilmanHaupt · **Статус:** смержен 01.09.2026 (создан 27.08.2026)
**Ветки:** `til-modal` → `main` · **Файлов:** 51 (+1593/-1257)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1211

> Closes #1169, #1141, #1241.
>
> **Полный ре-анализ 01.09.2026:** головной коммит сменился с `0cb05e66` (версия, разобранная в предыдущей версии этого отчёта 27-28.08.2026 — 33 файла, +689/-763, общий хук `useDeleteConfirmation`) на `ce4e8a4c` (51 файл, +1593/-1257). Автор полностью отказался от подхода с общим хуком `useDeleteConfirmation` — этот файл (`packages/aurora/src/client/hooks/useDeleteConfirmation.ts`) в текущем коммите не существует — и переписал все модалки на **TanStack Form + Zod** напрямую, поверх уже существующего (не нового) хука `useModalTracking` (введён в PR #1007). Это фактически новая реализация того же PR: старые находки предыдущей версии отчёта (баг `ImageListView` со сравнением по количеству, недостижимая проверка `markSubmitted()` в `DeleteImageModal`, дублирующий чекбокс охвата в changeset) нужно проверять заново — часть из них не переносится 1:1 на новый код. Отчёт ниже написан с нуля по текущему коммиту.

## Что сделано

Issue #1141 просил визуальной консистентности у модалок удаления/действий, #1169 — убрать чекбоксы bulk-выбора из хедер-ячеек `DataGrid`. Вместо общего хука (как в промежуточной версии этого же PR и в PR #1198) автор теперь переводит ~15 модалок подтверждения на **TanStack Form** (`useForm`/`useStore` из `@tanstack/react-form`) с валидацией через **Zod**: каждая модалка независимо объявляет свою Zod-схему вида `z.object({ confirm: z.string().refine((v) => v === "delete", { message: ... }) })`, подключает её как `validators: { onSubmit: formSchema }`, и гейтит кнопку подтверждения через `useStore(form.store, (s) => s.isSubmitting || s.values.confirm !== "delete")`. Аналитика (`.open`/`.close` события) — через уже существующий `useModalTracking`, без изменений в самом хуке.

Затронуты: Compute (`DeleteFlavorModal`, `DeleteImageModal`, `DeleteImagesModal`, `DeactivateImageModal`, `DeactivateImagesModal`), Network (`DetachFloatingIpModal`, `ReleaseFloatingIpModal`, `DeleteRBACPolicyDialog`, `DeleteRuleDialog`, `DeleteSecurityGroupDialog`), Storage/Ceph (`DeleteObjectModal`, `EmptyBucketsModal`, плюс лёгкая правка imports/форматирования в `BucketPolicyModal`, `CreateBucketModal`, `DeleteBucketPolicyModal`, `DeleteCorsRuleModal`/`DeleteCorsRulesModal`, `DeleteLifecycleRuleModal`/`DeleteLifecycleRulesModal`, `DeleteVersionsModal`, `EmptyBucketModal`, `EnableVersioningModal`, `SuspendVersioningModal`, `LifecycleRuleForm`), Storage/Swift (`DeleteContainerModal`, `EmptyContainerModal`, `EmptyContainersModal`, `DeleteFolderModal`, `DeleteObjectModal`, `DeleteObjectsModal`). Попутно: `ImageListView.tsx` лишился чекбокса "выбрать всё" в хедере таблицы (см. "Ревью"); `EmptyContainerModal` — список объектов переведён с `DataGrid` на скроллящийся `Stack`, кнопка `Empty` → `Empty Container`, размер модалки `small` → `large`; локали `de`/`en` обновлены под новые/переименованные строки; `eslint.config.mjs` и `turbo.json` — чисто форматирование (перенос строк), без смысловых изменений. Changeset (`.changeset/swift-ceph-delete-modals.md`, `patch`) в этот раз точно описывает суть изменения (TanStack Form + `useModalTracking` вместо `useDeleteConfirmation`, Zod-схемы, консистентный трекинг) — в отличие от прошлых PR в этой базе знаний (#1172, #1198), здесь охват назван верно.

Ни один общий переиспользуемый хук в этот раз не вводится — каждая модалка независимо повторяет один и тот же блок из ~10 строк (схема + `useForm` + `useStore`), то есть PR меняет направление по сравнению со своей же предыдущей версией (которая как раз обобщала эту логику в `useDeleteConfirmation`) в сторону дублирования. Само по себе это не баг, но стоит знать, читая как единую историю: PR дважды поменял архитектурный подход к одной и той же задаче за несколько дней.

## Как это реализовано

### Канонический паттерн (пример — `DeleteFlavorModal.tsx`)

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Flavors/-components/DeleteFlavorModal.tsx:49-93
const formSchema = z.object({
  confirm: z.string().refine((value) => value === "delete", {
    message: t`Type "delete" to confirm`,
  }),
})

const form = useForm({
  defaultValues: { confirm: "" },
  validators: { onSubmit: formSchema },
  onSubmit: async () => { /* ... */ },
})

const canDelete = useStore(form.store, (state) => state.isSubmitting || state.values.confirm !== "delete")
```

Кнопка подтверждения гейтится строковым сравнением (`canDelete`), а не результатом валидации формы — Zod-схема формально существует, но кнопка уже заблокирована до того, как введённый текст совпадёт с ожидаемым словом. Это работает корректно как UX, но означает, что `onSubmit`-валидатор почти никогда не видит невалидное значение через обычный клик — см. находку про несогласованность `errortext` в "Ревью".

### Инконсистентность в отображении ошибок валидации

Из ~15 модалок с type-to-confirm гейтингом только 4 реально пробрасывают `field.state.meta.errors` в `TextInput`:

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Images/-components/DeleteImagesModal.tsx:231-239
<TextInput
  label={t`Type "delete" to confirm`}
  ...
  invalid={field.state.meta.errors.length > 0}
  errortext={...}
```

Остальные (`DeleteFlavorModal.tsx:161-176`, `DeleteImageModal.tsx`, `DetachFloatingIpModal.tsx`, `ReleaseFloatingIpModal.tsx`, `DeleteRBACPolicyDialog.tsx`, `DeleteRuleDialog.tsx`, `DeleteSecurityGroupDialog.tsx`, `EmptyBucketsModal.tsx`, `DeleteObjectModal.tsx` — Ceph и Swift, `EmptyContainersModal.tsx`) объявляют ту же Zod-схему, но никогда не читают `field.state.meta.errors` в разметке — сообщение `t\`Type "delete" to confirm\`` (или аналог) существует только в схеме и никогда не отображается пользователю. Подробнее — "Ревью", находка №4.

### `EmptyContainersModal.tsx` — двойной вызов трекинга закрытия

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/EmptyContainersModal.tsx:101-108, 123-126
const handleClose = () => {
  trackClose()
  emptyContainerMutation.reset()
  setProgress(null)
  form.reset()
  resetTracking()
  onClose()
}
...
<Modal
  ...
  onCancel={() => {
    trackClose()
    handleClose()
  }}
```

Во всех остальных модалках batch'а `trackClose()` перенесён внутрь `handleClose`, а `onCancel` упрощён до `onCancel={handleClose}` (например `EmptyBucketsModal.tsx`, `DeleteVersionsModal.tsx`, `EnableVersioningModal.tsx` и другие Ceph-модалки). `EmptyContainersModal.tsx` — единственный файл, где `trackClose()` добавили и туда, и туда: закрытие этой конкретной модалки (крестик/Cancel) отправляет аналитическое событие `.close` дважды. См. "Ревью", находка №1.

### `DeleteContainerModal.tsx` — задвоенная валидация одного и того же поля

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/DeleteContainerModal.tsx:29-33, 216-238
const formSchema = z.object({
  confirm: z.string().refine((value) => value === "delete", {
    message: t`The text must match "delete"`,
  }),
})
const form = useForm({ ..., validators: { onSubmit: formSchema }, ... })
...
<form.Field
  name="confirm"
  validators={{
    onSubmit: ({ value }) => (value !== "delete" ? t`The text must match "delete"` : undefined),
  }}
  children={(field) => (
    <TextInput
      ...
      errortext={field.state.meta.errors.map((e) => (typeof e === "string" ? e : e?.message)).join(", ") || undefined}
```

Единственная модалка в PR, где на одно и то же поле навешаны одновременно form-level Zod-схема и отдельный field-level `onSubmit`-валидатор с идентичной проверкой. См. "Ревью", находка №2.

## Что затронуло

Все затронутые компоненты — модалки с ровно одним потребителем в своём собственном route-файле (внутреннее использование, без внешнего контракта). `@tanstack/react-form` (`^1.0.0`) и `zod` (`^4.0.0`) уже были зависимостями `packages/aurora` до этого PR (использовались частично уже в предыдущей версии этого же PR/#1198) — `package.json` в диффе не тронут, новых зависимостей нет. `useModalTracking` — не новый и не изменён этим PR, только повторно используется. Единственное, что реально исчезает из кодовой базы — файл `useDeleteConfirmation.ts` и его тесты (введённые промежуточным коммитом этого же PR ранее, до текущего head) — но поскольку ни один смерженный коммит в `main` его не использовал, это не breaking change для внешних потребителей.

`ImageListView.tsx` — единственный файл, где это PR трогает поведение, выходящее за рамки самих модалок удаления (см. "Ревью", находка №3).

## Ревью

**Найдено (confidence ≥ 80):**

1. **`EmptyContainersModal.tsx` — двойной вызов `trackClose()` при отмене.** (confidence 95)
   `handleClose` (строки 101-108) вызывает `trackClose()`, но `onCancel` (строки 123-126) оборачивает `handleClose` в ещё один `trackClose()` перед вызовом. Во всех остальных модалках PR ровно тот же рефакторинг убрал именно такую обёртку (`onCancel={handleClose}` без дублирования). Пользователь, отменяющий это конкретное bulk-действие (крестик или кнопка Cancel), отправляет аналитическое событие закрытия дважды — искажает close/abandon-rate метрики именно для этой модалки.
   Файл: `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/EmptyContainersModal.tsx:101-108,123-126`.

2. **`DeleteContainerModal.tsx` — дублирующий field-level валидатор поверх Zod-схемы даёт задвоенное сообщение об ошибке.** (confidence 85)
   Строки 29-33/39-41 подключают Zod-схему на уровне формы; строки 216-225 добавляют для того же поля `confirm` ещё один `onSubmit`-валидатор с идентичной проверкой (`value !== "delete"`). `field.state.meta.errors` в TanStack Form агрегирует ошибки обоих уровней для одного и того же field path, а строка 234-238 склеивает их через `.join(", ")` — при срабатывании валидации (например, пользователь жмёт Enter в текстовом поле, не нажимая саму кнопку подтверждения — нативный submit формы не блокируется `disableConfirmButton`, в отличие от клика по кнопке) под полем отобразится `"The text must match "delete", The text must match "delete""` вместо одного сообщения. Во всех остальных модалках с `errortext` (`DeleteImagesModal`, `EmptyContainerModal`, `DeleteObjectsModal` — Swift) валидатор ровно один — Zod-схема.
   Файл: `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Swift/Containers/DeleteContainerModal.tsx:216-225`.

3. **Две немецкие строки потеряли перевод при неизменном исходном тексте.** (confidence 90)
   `packages/aurora/src/locales/de/messages.po:410-411` (`msgid "Already deactivated (will be skipped):"`) и `:2096-2097` (`msgid "Images to deactivate:"`) — оба `msgid` не менялись этим PR (в отличие от соседних строк в том же диффе, где `msgstr` тоже сбрасывается в `""`, но потому что сам `msgid` изменился, например `"Detach Floating IP {floating_ip_address}"` → `"Detach Floating IP \"{floating_ip_address}\""`), однако немецкий `msgstr` обнулился с `"Bereits deaktiviert (wird übersprungen):"` и `"Zu deaktivierende Images:"` на `""`. `pnpm check-i18n` это не поймает (пустой `msgstr` синтаксически валиден), так что потеря перевода уйдёт в прод молча. Тот же класс регрессии (обнуление `msgstr` при неизменном `msgid` из-за повторной генерации каталога инструментом lingui) уже отмечался в этой базе знаний для PR #1111 — повторяющийся паттерн в этом репозитории, стоит один раз проверить процесс `pnpm check-i18n`/экстракции, а не чинить точечно каждый раз.
   Файл: `packages/aurora/src/locales/de/messages.po:410-411,2096-2097`.

4. **Заявленный в PR паттерн "field-level errors" реально подключён только в 4 из ~15 мигрированных модалок — Zod-сообщение в остальных не отображается никогда.** (confidence 80)
   `DeleteImagesModal.tsx:231-239`, `DeleteContainerModal.tsx:234-238`, `EmptyContainerModal.tsx`, `DeleteObjectsModal.tsx` (Swift) читают `field.state.meta.errors`/`invalid`/`errortext`. `DeleteFlavorModal.tsx:161-176`, `DeleteImageModal.tsx`, `DetachFloatingIpModal.tsx`, `ReleaseFloatingIpModal.tsx`, `DeleteRBACPolicyDialog.tsx`, `DeleteRuleDialog.tsx`, `DeleteSecurityGroupDialog.tsx`, `EmptyBucketsModal.tsx`, `DeleteObjectModal.tsx` (Ceph и Swift), `EmptyContainersModal.tsx` — нет: `TextInput` там не получает ни `invalid`, ни `errortext`, хотя Zod-схема с кастомным `message` объявлена в каждом. Поскольку кнопка подтверждения в этих модалках гейтится отдельным строковым сравнением (см. "Как это реализовано"), функционально это не ломается — но описание PR прямо называет "field-level errors via `field.state.meta.errors`" одним из ключевых улучшений, и в большинстве файлов это мёртвый код. Не критично для функциональности, но стоит либо довести до конца, либо убрать неиспользуемые сообщения из схем.
   Файлы: перечислены выше.

**Также замечено (confidence 50-79, не набрало полной уверенности):**
- **[70]** `ImageListView.tsx:601-625` — чекбокс "выбрать всё" в хедере `DataGrid` убран полностью (`<DataGridHeadCell></DataGridHeadCell>` вместо `Checkbox` с обработчиком), а не исправлен. Это разрешает баг с кросс-страничным выбором, который разбирался в предыдущей версии этого же PR (сравнение по количеству вместо по id, было confidence 98 в отчёте от 27-28.08.2026) — но ценой полного удаления bulk-выбора "разом" из хедера; массовые действия (Deactivate/Delete Images) теперь требуют клика по каждой строке отдельно. Судя по тестам (`ImageListView.test.tsx` — тесты на select-all/deselect-all удалены, а не обновлены) и собственному пункту PR-описания "Removed unused Checkbox import from ImageListView" в разделе "Other Improvements", решение выглядит намеренным, а не забытым — поэтому не поднимаю выше порога, но стоит сверить с issue #1169 (которая как раз просила убрать этот чекбокс из хедера) — если это её прямое разрешение, а не побочный эффект, для читателя changelog это стоит явно назвать, а не прятать в "Other Improvements".
- **[75]** `DeleteFlavorModal.tsx:105,111` — `title={t\`Delete Flavor "${flavorName}"\`}` не защищён от `flavor === null` (проп `flavor: Flavor | null`), тело модалки такую защиту имеет (`{flavor && (...)}` на строке 128), заголовок — нет. Тот же самый паттерн (тот же файл, та же строка №) уже отмечался в предыдущей версии этого отчёта на 27.08.2026 с тем же confidence 75 и с той же оговоркой: воспроизводимость ограничена узким окном закрывающей анимации модалки, если `flavor` сбрасывается в родителе раньше, чем `isOpen` становится `false` (`FlavorListContainer.tsx` действительно сбрасывает оба в одном `closeDeleteModal()`, стр. 84-87 — проверено).
- **[55]** `DetachFloatingIpModal.test.tsx:158-163` и `ReleaseFloatingIpModal.test.tsx:157-162` — название теста `"shows loading state and hides input form when isLoading is true"` противоречит собственному assertion (`expect(screen.queryByPlaceholderText("detach"/"release")).toBeInTheDocument()` — то есть поле теперь видно, а не скрыто). Тест по-прежнему проходит и корректно проверяет актуальное поведение компонента (форма больше не скрывается во время загрузки) — только его название устарело и вводит в заблуждение.
- **[50]** `DeleteObjectsModal.tsx` (Swift, множественное число) — комментарий `// Type-to-confirm guard. Bulk deletion is irreversible...` остался на месте, но код, который он описывал (старый `useState`/`isConfirmed`), удалён; сейчас комментарий висит прямо над не связанным с ним объявлением `bulkDeleteMutation`. Сам механизм type-to-confirm переехал выше по файлу в новый блок Zod-схемы/`useForm` — смысл комментария не устарел, но его физическое расположение теперь вводит в заблуждение.

---
Проанализировано: 01.09.2026 · коммит `ce4e8a4c`
