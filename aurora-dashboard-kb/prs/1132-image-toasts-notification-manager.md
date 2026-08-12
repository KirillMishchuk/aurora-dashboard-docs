# PR #1132: refactor(portal): migrate image toasts from legacy Toast to NotificationManager

**Автор:** mark-karnaukh-extern-sap · **Статус:** создан 04.08.2026, смержен 06.08.2026 (коммит `46256e98`)
**Ветки:** `mark-images-notifications` → `main` · **Файлов:** 12 (+980/-813)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1132

## Что сделано

Третий (после Ceph — коммит `32223ac`, и Swift — коммит `df25d7c`) и последний перевод legacy `<Toast>`-паттерна на общеприложенческий `NotificationManager` (Sonner-based `toast.success/error/warning/info()`) — на этот раз для фичи Glance images. До этого PR каждый экран (`ImageListView`, `ImageTableRow`, деталка `$imageId`) держал собственное состояние `toastData`, рендерил `<Toast {...toastData} />` фиксированным блоком и прокидывал `onDismiss`-колбэк через `ToastConfig` в каждый из 24 билдеров в `ImageToastNotifications.tsx`. PR убирает это состояние целиком: билдеры теперь возвращают простой объект `{ message, description }` (без `variant`, без JSX-рендеринга через компонент `NotificationText`), а вызывающий код сам решает северность и диспатчит её императивно:

```tsx
// ImageToastNotifications.tsx:5-11
// Builder helpers for the NotificationManager (Sonner-based) `toast` API.
// Each returns `{ message, ...options }`; the caller destructures and dispatches
// the appropriate severity, e.g.
//   const { message, ...options } = getImageUpdatedToast(name)
//   toast.success(message, options)
// Severity lives at the call site (toast.success / error / warning / info),
// mirroring the Swift/Ceph notification helpers.
```

Конкретный пример на месте вызова (один из 22 в `ImageListView.tsx`):

```tsx
// ImageListView.tsx:480-485
if (failedCount === 0) {
  const { message, ...options } = getBulkDeleteSuccessToast(successCount, totalCount)
  toast.success(message, options)
} else if (successCount === 0) {
  const { message, ...options } = getBulkDeleteErrorToast(failedCount, totalCount)
  toast.error(message, options)
```

Помимо самого рефакторинга, PR попутно исправил типизацию сообщений об ошибках: раньше `const { message } = error as TRPCClientError<...>` неявно трактовал потенциально `undefined` как `string`; теперь на большинстве мест добавлен явный фолбэк `?? ""` перед передачей в билдер. Обновлены английский и немецкий каталоги переводов под новые именованные плейсхолдеры (`errorMessage` вместо `message` в нескольких местах) — оба каталога синхронны, пустых `msgstr ""` не осталось.

## Как это реализовано

Каждый из 24 билдеров в `ImageToastNotifications.tsx` теперь возвращает данные, а не JSX-разметку компонента (компонент `NotificationText`, который раньше собирал `title`/`description` в вертикальный `<Stack>`, из билдеров убран целиком):

```tsx
// ImageToastNotifications.tsx:15-30
export const getImageUpdatedToast = (imageName: string): { message: ReactNode } & NotificationOptions => ({
  message: <Trans>Image Instance</Trans>,
  description: <Trans>Image instance "{imageName}" has been updated</Trans>,
})

export const getImageUpdateErrorToast = (
  imageName: string,
  errorMessage: string
): { message: ReactNode } & NotificationOptions => ({
  message: <Trans>Unable to Update Image</Trans>,
  description: (
    <Trans>
      The image "{imageName}" could not be updated: {errorMessage}
    </Trans>
  ),
})
```

Вызывающая сторона (`ImageListView.tsx`, `ImageTableRow.tsx`, `$imageId.tsx`) везде следует одному и тому же паттерну — деструктурировать `message`/`options` и вызвать нужный метод `toast`, без исключений (проверено построчно по всем 26 местам вызова): `*ErrorToast` → `toast.error`, простые/`*SuccessToast` → `toast.success`, `*PartialToast` → `toast.warning`, `getImageAccessStatusUpdatedToast` → `toast.info`. Пример из `ImageTableRow.tsx`:

```tsx
// ImageTableRow.tsx:90-96
const { message, ...options } = getImageAccessStatusUpdatedToast(newStatus)
toast.info(message, options)
onMemberStatusChanged?.()
} catch (error) {
  const errorMessage = (error as TRPCClientError<InferrableClientTypes>)?.message
  const { message, ...options } = getImageAccessStatusErrorToast(errorMessage)
  toast.error(message, options)
}
```

Тесты (`ImageToastNotifications.test.tsx`) переписаны под новую форму данных (`{ message, description }` вместо проверки отрендеренного `<Toast>`); добавлены два новых файла — `ImageTableRow.test.tsx` и `$imageId.test.tsx` — с рендерингом через реальные Juno-компоненты и реальный `NotificationManager`, а не моки, плюс проверки permission-gated экшенов и member-status флоу.

## Что затронуло

`ImageToastNotifications.tsx`, `NotificationText.tsx` и связанное состояние — всё локально для фичи Images (`compute/-components/Images/-components/`), потребителей за пределами изменённых файлов не найдено (`git grep` по монорепо на все 24 имени билдеров чист). Изменение не выходит за пределы этой фичи: паблик-контракт `AuroraApp` (слоты, пропсы) не тронут, `packages/aurora/README.md` обновления не требует.

Осталось не до конца прибрано: **`NotificationText.tsx` и его тест `NotificationText.test.tsx` остались в дереве, но стали мёртвым кодом.** До PR все 24 билдера рендерили контент через `<NotificationText title=... description=... />`; после рефакторинга билдеры больше не рендерят JSX вообще, `NotificationText` нигде не используется (кроме собственного теста) — `git grep -n NotificationText` по всему репозиторию на head-коммите подтверждает: только сам файл и его тест. Это расходится с тем, как тот же самый рефакторинг был сделан раньше в этом же репозитории: у Ceph Buckets (`32223ac`) и Swift Containers (`df25d7c`) аналогичный локальный компонент удалялся тем же коммитом, что менял форму билдеров — там уборка была полной. Изменение реестра трансляций (locale-файлы) соответствует изменениям в билдерах один в один, без расхождений.

## Ревью

Через диф прогнаны параллельно: CLAUDE.md/AGENTS.md-комплаенс (та же оговорка, что и для #1123 — апстрим не содержит `AGENTS.md`/`CLAUDE.md`, сверка велась по `CONTRIBUTING.md`/`docs/aurora_architecture_overview.md`/`packages/aurora/README.md`), bug-scan, historical context (`git log`/`git blame`, сравнение с более ранними миграциями Ceph/Swift на тот же паттерн), prior-feedback (в этом PR на GitHub уже есть автоматические ревью от CodeRabbit и Copilot — их замечания перепроверены по коду, а не приняты на веру) и comment-compliance.

**Проблем с уверенностью ≥80 не найдено.** Ближе всего к порогу — оставленный мёртвый код `NotificationText` (75/100), не дотянул на 5 пунктов.

Кандидаты, не прошедшие порог (для полноты — на будущее, чтобы не искать заново):

- **Оставленный мёртвый код `NotificationText.tsx`/`NotificationText.test.tsx`** (см. «Что затронуло» выше) — 75/100. Реальная и подтверждённая находка (нулевые потребители, несогласованность с тем, как аналогичную уборку сделали более ранние PR по Ceph/Swift), но не дотягивает до порога отчёта — некритично (мёртвый файл, не баг в поведении), удаляется одной правкой при следующей правке этой области.
- **Северность bulk-операций решается на месте вызова, а не в билдере** (`ImageListView.tsx:470-560`, три хендлера `handleBulkDelete`/`handleBulkActivate`/`handleBulkDeactivate`, каждый напрямую воспроизводит `if (failedCount === 0) ... else if (successCount === 0) ... else ...` и диспатчит один из 9 отдельных билдеров) — 65/100. Описание PR заявляет паттерн «как у Swift и Ceph», но это в точности паттерн Ceph; более новый паттерн Swift (коммит `df25d7c`, билдер сам возвращает `{ message, severity, ...options }`, чтобы сообщение и северность не могли разойтись) сюда не перенесён. Риск реален, но смягчён тем, что ветки `if/else if/else` лежат рядом в одном блоке — разъехаться на практике сложно.
- **Дублирование jsdom-полифиллов между двумя новыми тестовыми файлами** (`ImageTableRow.test.tsx`, `$imageId.test.tsx` — оба заново стабят `scrollIntoView`/`matchMedia` в собственном `beforeAll`) — 65/100. В репозитории уже есть централизованный `vitest.setup.ts` с `ResizeObserver`/другими полифиллами, куда логично было бы добавить и эти два — но ни один из 22 остальных тестовых файлов с `beforeAll` не следует такому паттерну по-другому, эффект на практике смягчён defensive-guard'ами в самом коде полифиллов.
- **Повтор инлайн-типа `{ message: ReactNode } & NotificationOptions` в каждом из 24 билдеров** (вместо общего type alias) — 0/100. Формально новое в этом файле (раньше был общий `ToastConfig`), но ровно тот же паттерн уже используется во всех соседних файлах уведомлений (`BucketToastNotifications.tsx`, `ObjectToastNotifications.tsx`, `ContainerToastNotifications.tsx`) — это существующая конвенция репозитория, а не отклонение этого PR.
- Замечания CodeRabbit, уже оставленные прямо на этом PR, перепроверены по коду и отклонены как относящиеся не к этому PR: debug `console.log` в bulk-хендлерах (`ImageListView.tsx`, строки ~475/507/540) — тот же вызов существовал до PR, изменилось только имя переменной; импорт `@cloudoperators/juno-ui-components/index` вместо корня пакета в `$imageId.tsx` — путь импорта не тронут этим диффом; `errorMessage || <Trans>...</Trans>` в `getImageAccessStatusErrorToast` (`ImageToastNotifications.tsx:231-234`) без обёртки в `<Trans>` на truthy-ветке — идентичный паттерн уже был в JSX-версии билдера до PR (`ImageTableRow.tsx:94-96`, `$imageId.tsx` аналогично, вызывающий код тоже не менялся). Замечание CodeRabbit про `getByRole("button")` в новых тестах — на практике не неоднозначно: единственная другая интерактивная роль в той же строке — `checkbox`, не `button`.

---
Проанализировано: 06.08.2026 · коммит `8ca4c450e145e98188b2d02ac18c671ea50f89d9`
