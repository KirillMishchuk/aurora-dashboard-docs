# PR #1221: feat(dashboard): add missing toasts for object-storage and security-groups

**Автор:** vlad-schur-external-sap · **Статус:** смержен 31.08.2026 (создан 28.08.2026)
**Ветки:** `vlad-missing-toasts-for-secgroups-and-storages` → `main` · **Файлов:** 19 (+1068/-101)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1221

## Что сделано

Часть issue #1136 — добивает покрытие toast-уведомлениями (`NotificationManager`/Sonner-based `toast.success/error()`, тот же паттерн, что уже стоит у Ceph/Swift/Images, см. отчёт по #1132) для двух фич, где часть операций молча проходила без обратной связи: Security Groups (сама группа + правила + RBAC-политики шаринга на другой проект) и Ceph Bucket Policy (сохранение политики бакета — до этого была только у удаления).

**Security Groups.** До PR отдельная страница деталей группы (`useSecurityGroupDetails.ts`) вообще не показывала тостов ни на один из трёх мутейшенов (update группы, create/delete правила) — только error-состояние в форме. Список групп (`SecurityGroupsList.tsx`) уже показывал inline-ошибку через `Message`, но не toast, и не показывал успех никак. RBAC-политики (шаринг группы на другой проект) были в таком же состоянии. PR добавляет toast на все шесть операций разом, используя единый новый файл билдеров:

```tsx
// SecurityGroupToastNotifications.tsx:5-27
type ToastReturnType = { message: ReactNode } & NotificationOptions

export const getSecurityGroupDeletedToast = (name: string): ToastReturnType => ({
  message: <Trans>Security Group Deleted</Trans>,
  description: <Trans>Security group "{name}" was successfully deleted.</Trans>,
})
// ... симметричные Update/RuleCreated/RuleDeleted/RBACPolicyAdded/RBACPolicyDeleted билдеры
```

На стороне вызова, например `useSecurityGroupDetails.ts:99-113`, тост для успешного переименования берёт имя из отправленных `variables`, с фолбэком на закэшированные данные, если поле не менялось (например, при чистом добавлении правила):

```tsx
// useSecurityGroupDetails.ts:99-113
const updateMutation = trpcReact.network.securityGroup.update.useMutation({
  onSuccess: (_, variables) => {
    utils.network.securityGroup.getById.invalidate({ project_id: projectId, securityGroupId })
    utils.network.securityGroup.list.invalidate()
    const { message, ...options } = getSecurityGroupUpdatedToast(
      variables.name || securityGroupQuery.data?.name || securityGroupId
    )
    toast.success(message, options)
    setEditModalOpen(false)
  },
  onError: (error) => {
    const { message, ...options } = getSecurityGroupUpdateErrorToast(error.message)
    toast.error(message, options)
  },
})
```

В `SecurityGroupsList.tsx` (список групп) успех теперь идёт либо через `.mutateAsync` + `try/catch` (update, create), либо через колбэк, переданный прямо в `.mutate()` (delete) — два разных стиля для соседних операций в одном файле, но без функциональной проблемы (см. «Ревью»):

```tsx
// SecurityGroupsList.tsx:170-197
const handleDeleteSecurityGroup = (securityGroupId: string) => {
  setDeleteError(null)
  const sgName = securityGroups.find((sg) => sg.id === securityGroupId)?.name || securityGroupId
  deleteSecurityGroupMutation.mutate(
    { project_id: projectId, securityGroupId },
    { onSuccess: () => {
      const { message, ...options } = getSecurityGroupDeletedToast(sgName)
      toast.success(message, options)
    } }
  )
}

const handleUpdateSecurityGroup = async (securityGroupId, data) => {
  setUpdateError(null)
  const sgName = data.name || securityGroups.find((sg) => sg.id === securityGroupId)?.name || securityGroupId
  try {
    await updateSecurityGroupMutation.mutateAsync({ project_id: projectId, securityGroupId, ...data })
    const { message, ...options } = getSecurityGroupUpdatedToast(sgName)
    toast.success(message, options)
  } catch {
    // onError handles error state and UI feedback
  }
}
```

RBAC-политики получили тост на добавление (`AddRBACPolicyModal.tsx:41-53`, тост зависит от `variables.targetTenant`, т.е. реально отправленного значения) и на удаление (`SecurityGroupRBACPolicies.tsx:58-84`) — на удалении успех и ошибка обрабатываются в разных местах: `onError` тостит из конфига мутейшена (:64-67), а `onSuccess`-тост передан инлайн в `.mutate()` (:76-84), а не в конфиг — асимметрично, но обе ветки реально срабатывают.

**Ceph Bucket Policy.** До PR `BucketPolicyModal` (общая модалка просмотра/редактирования/удаления политики бакета) принимала `onSuccess?: (bucketName: string) => void` / `onError?: (...) => void`, не различая, была ли операция сохранением или удалением политики. Единственный потребитель, который реально передавал эти колбэки (`BucketModals.tsx`), поэтому не мог показать разный текст тоста для save/delete — и фактически не показывал тост на save вообще, только на delete (через отдельный `getBucketPolicyDeletedToast`). PR расширяет сигнатуру третьим параметром `action: "saved" | "deleted"`:

```tsx
// BucketPolicyModal.tsx:11-17, 119-140
interface BucketPolicyModalProps {
  isOpen: boolean
  bucketName: string
  onClose: () => void
  onSuccess?: (bucketName: string, action: "saved" | "deleted") => void
  onError?: (bucketName: string, errorMessage: string, action: "saved" | "deleted") => void
}
...
const setMutation = trpcReact.storage.ceph.bucketPolicy.set.useMutation({
  onSuccess: () => { utils.storage.ceph.bucketPolicy.get.invalidate(); onSuccess?.(bucketName, "saved"); handleClose() },
  onError: (error) => { onError?.(bucketName, error.message, "saved") },
})
const deleteMutation = trpcReact.storage.ceph.bucketPolicy.delete.useMutation({
  onSuccess: () => { utils.storage.ceph.bucketPolicy.get.invalidate(); onSuccess?.(bucketName, "deleted"); handleClose() },
  onError: (error) => { onError?.(bucketName, error.message, "deleted") },
})
```

и `BucketModals.tsx:113-129` branches on `action` to pick the right pair of toast builders (new `getBucketPolicySavedToast`/`getBucketPolicySaveErrorToast`, added to `BucketToastNotifications.tsx` alongside the existing `getBucketPolicyDeletedToast`/`getBucketPolicyDeleteErrorToast`). Попутно `BucketToastNotifications.tsx` вынес повторяющийся инлайн-тип `{ message: ReactNode } & NotificationOptions` во всех ~24 билдерах в общий `type ToastReturnType` (чисто рефакторинг, поведение не меняет).

Locale-файлы (`packages/aurora/src/locales/{de,en}/messages.{po,ts}`) — стандартная `lingui extract`-регенерация под новые строки `<Trans>`, оба каталога синхронны, пустых `msgstr ""` нет.

## Как это реализовано

См. фрагменты выше — вся работа сводится к (1) новому файлу `SecurityGroupToastNotifications.tsx` с шестью билдерами по образцу уже существующих `BucketToastNotifications.tsx`/`ImageToastNotifications.tsx`/`ObjectToastNotifications.tsx`, (2) добавлению `onSuccess`/`onError` в существующие `useMutation`-конфиги пяти security-group компонентов и (3) добавлению третьего параметра `action` в контракт `BucketPolicyModal`, чтобы единая модалка могла сообщить, какая из двух её мутаций сработала. Ни один новый tRPC-вызов не добавлен — PR только навешивает UI-обратную связь на уже существующие мутации.

Тесты добавлены/расширены под каждый новый тост: два новых тестовых файла (`useSecurityGroupDetails.test.ts`, `SecurityGroupToastNotifications.test.tsx`, `AddRBACPolicyModal.test.tsx`, `SecurityGroupsList.test.tsx` — фактически все новые), плюс расширения существующих (`SecurityGroupRBACPolicies.test.tsx`, `BucketPolicyModal.test.tsx`, `BucketToastNotifications.test.tsx`). `BucketPolicyModal.test.tsx` явно проверяет ветвление по `action` (`reports whether a policy was saved or deleted`, :277-286).

## Что затронуло

Все шесть новых экспортов `SecurityGroupToastNotifications.tsx` потребляются только файлами, изменёнными в этом же PR (`git grep` по монорепо на head-коммите подтверждает — 4 потребителя, все в диффе). `BucketToastNotifications.tsx` уже имеет более широкий круг потребителей (`CorsRulesTab/Table`, `LifecycleRulesTab/Table`, `index.tsx` реэкспортирует всё через `export *`) — они не тронуты этим PR и не ссылаются на новые `getBucketPolicySavedToast`/`getBucketPolicySaveErrorToast`, так что расширение файла безопасно для них.

`BucketPolicyModal` — единственный компонент, чья публичная сигнатура (`onSuccess`/`onError`) реально меняется — имеет **двух** потребителей в монорепо, не одного: `BucketModals.tsx` (обновлён этим PR) и `ObjectBrowserView.tsx:918-922` (Ceph Object Browser, **не тронут этим PR**). Сигнатура расширяется, а не сужается (добавлен третий параметр), поэтому обратной совместимости на уровне TypeScript/рантайма ничего не угрожает — но стоит зафиксировать для истории: `ObjectBrowserView.tsx` вообще не передаёт `onSuccess`/`onError` в `BucketPolicyModal` (оба пропа опциональны), то есть сохранение/удаление политики бакета из Object Browser как не показывало тост до PR, так и не показывает после. Это никогда не было в объёме этого PR (заголовок и changeset говорят только про security-groups и object-storage списки/детали, не про Object Browser) и не регрессия этого PR — просто соседний пробел в том же покрытии, который стоит иметь в виду при следующей итерации issue #1136.

Аналогично в Security Groups: `createSecurityGroupMutation` (`SecurityGroupsList.tsx:117-133`) — единственная из четырёх мутаций группы, которая так и не получила success-тост (только `setCreateError`/inline `Message` на ошибку) — строки этого мутейшена PR не трогает вообще, значит это тоже не регрессия, а нетронутый остаток той же задачи.

## Ревью

Через диф и полные файлы на head-коммите (`e6332b18b`) прогнаны параллельно: CLAUDE.md-комплаенс, bug-scan, historical context (`git log -p`/`git blame` по всем 8 нетестовым источникам, сверка с тем, как аналогичный паттерн вводили #1092/#1132 CORS/Lifecycle/Images), prior-feedback (публичный REST API GitHub — `gh` в окружении недоступен без токена, поэтому вместо `gh pr list`/`gh api` использовался неаутентифицированный `curl` к `api.github.com`, лимит запросов ниже, но заняло меньше 60) и comment-compliance.

**Проблем с уверенностью ≥80 не найдено.**

Кандидаты, не прошедшие порог (для полноты, чтобы не искать заново):

- **Два идентичных комментария `// onError handles error state and UI feedback`** (`SecurityGroupsList.tsx:166` в `handleCreateSecurityGroup` и `:195` в `handleUpdateSecurityGroup`) на деле описывают разный уровень обратной связи: `onError` у create-мутации (:130-132) выставляет только inline-состояние `setCreateError`, тост на создание в этом PR не добавлен вовсе; `onError` у update-мутации (:154-158) выставляет inline-состояние **и** тостит. Формально комментарий не врёт («UI feedback» покрывает оба случая), поэтому не тянет на нарушение — 25/100.
- **Одновременный показ inline `Message`-баннера и `toast.error` на одну и ту же ошибку** (`SecurityGroupsList.tsx:141-144, 154-158`, аналогично `SecurityGroupRBACPolicies.tsx`) — это ровно то, что заявлено целью PR (добавить тосты поверх уже существующего inline-состояния, не заменяя его), не отклонение — 0/100.
- **Пропуск найден предыдущим прогоном по prior-feedback**: PR #1092 (CORS для бакетов) получил ревью-замечание «репортить удаление как удаление, а не как сохранение» для точно такого же паттерна общей save/delete-модалки — этот PR следует той же рекомендации на своём коде (`action: "saved" | "deleted"`), так что тут не пропуск, а подтверждение, что конвенция соблюдена — не репортится как находка, зафиксировано для истории.
- Не находки, а зафиксированные для истории out-of-scope пробелы (см. «Что затронуло»): `ObjectBrowserView.tsx`'s `BucketPolicyModal` без `onSuccess`/`onError` и `createSecurityGroupMutation` без success-тоста — оба на строках, которые этот PR не трогает, поэтому не репортятся как находки этого PR.

---
Проанализировано: 28.08.2026 · коммит `e6332b18becbef4b9934dbbe1b138b8cb7a81a35`
