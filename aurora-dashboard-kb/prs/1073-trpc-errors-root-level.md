# PR #1073: fix(aurora): trpc errors not used at root level errors

**Автор:** vlad-schur-external-sap · **Статус:** смержен 22.07.2026 (`8944e742`; создан 15.07.2026)
**Ветки:** `vlad-fix-default-msgs-at-global-error-route` → `main` · **Файлов:** 6 (+22/-23)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1073

> PR ещё не готов к мержу: описание — незаполненный шаблон (CodeRabbit явно пометил это как fail в pre-merge проверке), и на самом PR висят 4 неразрешённых комментария Copilot, три из которых указывают на ту же проблему, что независимо нашёл ревью ниже (см. секцию "Ревью"). Этот отчёт документирует PR как есть на момент анализа — не как готовое к мержу решение.

## Что сделано

PR чинит конкретный баг: несколько `errorComponent`-компонентов в клиентском роутере рендерили `<RouteError error={error} />` **без** пропа `safeErrorMessage`, из-за чего `RouteError` (см. `packages/aurora/src/client/components/Error/RouteError.tsx:19-30`) намеренно скрывал реальный текст ошибки и показывал безопасный дефолт ("Unable to Load Content" / "An unexpected error occurred") — даже когда сервер тRPC вернул осмысленное, специально сформированное сообщение (например, "Access denied — your credentials are valid but lack permissions for this operation" из `s3ErrorMapper.ts`).

Исправление точечное — везде, где создаётся `errorComponent`, теперь явно передаётся `safeErrorMessage={error instanceof TRPCClientError ? error.message : undefined}`, так что тRPC-ошибки показываются пользователю как есть, а не-тRPC ошибки (не `instanceof TRPCClientError`) по-прежнему скрываются за дефолтным текстом.

Заодно PR убирает два **недостижимых** `errorComponent` (мёртвый код, оставшийся после более ранних рефакторингов — см. "Что затронуло") и один неиспользуемый экспорт `invalidateCsrfToken`.

## Как это реализовано

**Корневой error boundary** — `packages/aurora/src/client/routes/__root.tsx:63-68` — это `errorComponent` для *всего* приложения (ловит любую ошибку, не пойманную более специфичным boundary ниже по дереву роутов):

```tsx
import { TRPCClientError } from "@trpc/client"
// ...
function RootErrorComponent({ error }: { error: Error }) {
  return (
    <AuroraLayout>
      <RouteError error={error} safeErrorMessage={error instanceof TRPCClientError ? error.message : undefined} />
    </AuroraLayout>
  )
}
```
До этого PR здесь было просто `<RouteError error={error} />` — с момента появления этого компонента (PR #850, "move aurora-portal to aurora package") тRPC-ошибки на корневом уровне никогда не показывали свой реальный текст.

**Роут деталей проекта** — `packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:136` — та же правка, тот же паттерн:
```tsx
return <RouteError error={error} safeErrorMessage={error instanceof TRPCClientError ? error.message : undefined} />
```
Этот `ProjectErrorComponent` был добавлен PR #1035 ("improve project not found error handling") и с тех пор имел тот же пробел.

**Удаление мёртвого кода**: `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images.tsx` лишился собственного `errorComponent: ({ error }) => <RouteError error={error} />` — у этого роута нет ни `loader`, ни другой точки, где могла бы выброситься ошибка до рендера, так что этот boundary был недостижим с момента его добавления (PR #900). Ошибки теперь корректно всплывают к `$projectId.tsx`'s `ProjectErrorComponent` (проверено: соседние роуты `compute/index.tsx` и `compute/flavors.tsx` уже полагались на тот же паттерн без собственного `errorComponent`).

**Удаление неиспользуемого экспорта** — `packages/aurora/src/client/trpcClient.ts:58-63`:
```ts
-/**
- * Invalidate the cached CSRF token.
- * Call this when receiving a 403 response to trigger a fresh token fetch on the next request.
- */
-export const invalidateCsrfToken = () => csrfCache.invalidate()
```
Экспорт не имел ни одной точки вызова в кодовой базе ни до, ни после удаления — но см. "Ревью", это не совсем однозначная чистка.

## Что затронуло

**Блэст-радиус самого фикса широкий**: `__root.tsx`'s `errorComponent` — это error boundary верхнего уровня, он ловит любую необработанную ошибку из любого роута приложения. До этого PR тРPC-сообщения глушились везде, где не было более специфичного boundary с собственным `safeErrorMessage` — теперь показываются.

**Прямая связь с PR #1067** (смержен на день раньше, переписал `projects/index.tsx` на `Suspense`/`useSuspenseQuery`): та переработка оставила `ProjectsOverviewNavBar` **вне** `ErrorBoundary`, который сама же добавила, и превратила route-level `errorComponent` этого файла в недостижимый мёртвый код (данные теперь грузятся в компоненте, а не в `loader`, так что router-level `errorComponent` никогда не срабатывает). PR #1073 исправляет ровно это — переносит `ProjectsOverviewNavBar` внутрь `ErrorBoundary`:
```tsx
// packages/aurora/src/client/routes/_auth/projects/index.tsx:76-93 (после PR)
<ErrorBoundary
  fallbackRender={({ error }) => (
    <RouteError error={error} safeErrorMessage={error instanceof TRPCClientError ? error.message : undefined} />
  )}
>
  <ProjectsOverviewNavBar searchTerm={search} onSearch={handleSearch} />
  <div className="pt-5">
    <Suspense fallback={...}><ProjectsContent search={search} /></Suspense>
  </div>
</ErrorBoundary>
```
и удаляет мёртвый `errorComponent` из конфига роута. Побочный эффект этого переноса (не баг, но заметное поведенческое изменение): строка поиска (`ProjectsOverviewNavBar`) теперь тоже пропадает при ошибке загрузки карточек проектов, а раньше оставалась видимой — консистентность важнее, но это стоит знать.

**Проверка потребителей**: `git grep` по `safeErrorMessage`/`TRPCClientError` на головном коммите PR показывает, что после этого фикса ВСЕ боевые (не тестовые) `errorComponent`/`RouteError`-точки в клиенте либо передают `safeErrorMessage`, либо были удалены как недостижимые — расхождений не осталось. Тестовый файл `RouteError.test.tsx` по-прежнему вызывает `<RouteError error={error} />` без пропа в нескольких кейсах — это намеренно (тестирует именно дефолтное поведение сокрытия), не пропущенный call site.

## Ревью

**Найдено (confidence ≥ 80):**

1. **`error instanceof TRPCClientError` — недостаточное условие безопасности; сырые сообщения от сервера могут утечь через корневой error boundary.** (confidence 85)
   `RouteError.tsx:19-24` документирует инвариант: "Do not expose raw Error.message by default as it may contain sensitive information" — показывать можно только явно проверенные безопасные сообщения. Но серверный роутер (`packages/aurora/src/server/trpc.ts:5`, `initTRPC.context<AuroraPortalContext>().create()`) не задаёт кастомный `errorFormatter`, так что тRPC по умолчанию пробрасывает `error.message` как есть. Конкретно `packages/aurora/src/server/Storage/helpers/s3ErrorMapper.ts:80-81` для немаппленных кодов ошибок S3/Ceph делает `parts.push(s3Error.message)` — сырой текст ошибки AWS/Ceph SDK попадает прямиком в `TRPCError.message` → `TRPCClientError.message` → теперь показывается пользователю через корневой boundary (который ловит ошибки *любого* роута, не только storage). Это ровно тот сценарий, от которого предостерегает комментарий в `RouteError.tsx`.
   Это не домысел ревью — на самом PR #1073 уже висят **3 неразрешённых комментария Copilot** (на `__root.tsx`, `$projectId.tsx` и `projects/index.tsx`), дословно рекомендующих: "Consider filtering out INTERNAL_SERVER_ERROR (or otherwise ensuring messages are sanitized)". Ни один не адресован на момент анализа.
   Файлы: `packages/aurora/src/client/routes/__root.tsx:66`, `packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:136`, `packages/aurora/src/client/routes/_auth/projects/index.tsx:75` (последний — паттерн уже существовал до PR #1073, туда просто добавились ещё 2 таких же места).

**Также замечено (confidence 50-79, подтверждено, но не набрало полной уверенности):** — по этой находке кандидатов не набралось; единственный второй кандидат (удаление `invalidateCsrfToken` без замены механизма восстановления после ротации CSRF-токена, тоже отмеченное Copilot-комментарием на PR) получило confidence 35 — реальный архитектурный пробел, но экспорт был мёртвым кодом без единой точки вызова и до PR, так что ничего рабочего это не ломает; ниже порога включения.

## Что сделано хорошо

Удаление недостижимых `errorComponent` (в `images.tsx` и `projects/index.tsx`) — не косметика, а корректная реакция на то, что архитектура роутинга изменилась в PR #1067 (data-fetching переехал из `loader` в компонент), и старые route-level boundary перестали иметь смысл. Автор PR проверил это, а не просто патчил на месте.

---
Проанализировано: 17.07.2026 · коммит `0263a780e`
