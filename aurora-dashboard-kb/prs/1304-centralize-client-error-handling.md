# PR #1304: feat(dashboard): centralize client error handling

**Автор:** vlad-schur-external-sap · **Статус:** смержен 17.09.2026 (создан 15.09.2026)
**Ветки:** `vlad-centralized-error-handling` → `main` · **Файлов:** 94 (+837/-527)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1304

## Что сделано

Крупный (94 файла) рефакторинг клиентской обработки ошибок вокруг Epic #1055, без изменений на сервере. Три слоя, по PR description: **global** (просроченный токен и т.п. — уже существовало), **service-level** (несуществующий роут типа `netrowk/floatingips`) и **$id-level** (несуществующий конкретный ресурс: flavor/image/floating IP/security group/storage container).

**1. Новые общие компоненты** (`client/components/Errors/`, переименовано из `Error/`, единственного числа):
- `RouteError` (переименован, без функциональных изменений, только добавлен doc-комментарий) — полноэкранная ошибка вне layout (протухшая сессия и т.п.), уже существовала.
- `RouteIdLevelDefaultError` (новый) — ошибка ресурса **внутри** layout (сайдбар/хедер остаются), обёртка над `<Status code={404} status="error">`, с дефолтным заголовком/текстом/кнопкой "Go to Project Home", переопределяемыми пропами.
- `ServiceLevelDefaultError` (новый) — аналог для несуществующего роута целиком, зарегистрирован как `defaultNotFoundComponent` роутера (`router.ts:14`).

**2. Пять роутов получили собственный `errorComponent`** (не было раньше): `compute/flavors/$flavorId.tsx`, `compute/images/$imageId.tsx`, `network/floatingips.tsx`, `network/securitygroups.tsx`, `storage/$provider/$storageType/$containerName/objects/index.tsx` (тут же и `notFoundComponent`, было `<p>Storage container not found</p>`). Все пять — обёртки, рендерящие `RouteIdLevelDefaultError` с кнопкой "Назад к <раздел>". `images/$imageId.tsx` также вручную использует `RouteIdLevelDefaultError`/свой `ImageErrorComponent` в собственных ветках `status === "error"` / `!image` компонента (данные из `useQuery`, отдельно от роутерного `errorComponent`).

**3. Механическая замена `Spinner`/`Message` на `<Status/>`** в ~50 модалках (Delete/Empty/Move/Copy/Edit — Ceph Buckets/Objects, Swift Containers/Objects, Flavors, Images, Security Groups): `<Spinner/>` + текст → `<Status status="progress" title=.../>`, `<Message variant="error">` → `<Status status="error" title=... body=.../>`, `variant="warning"` → `status="empty"`. Везде сохранена семантика 1:1, попутно поправлена пара мест, где спиннер и текст ошибки могли отрендериться одновременно (см. "Как реализовано").

**4.** Локали `en`/`de` `messages.po` синхронизированы (91/90 строк изменено — новые заголовки Status, убранные inline-тексты спиннеров).

## Как это реализовано

### Новые примитивы (`client/components/Errors/`)

`RouteIdLevelDefaultError.tsx` (новый файл, 44 строки):

```tsx
export const RouteIdLevelDefaultError = ({ errorTitle, errorDescription, action }: RouteIdLevelDefaultErrorProps) => {
  const { t } = useLingui()
  const navigate = useNavigate()
  const { projectId } = useParams({ strict: false })
  ...
  return (
    <Status
      code={404}
      status="error"
      title={errorTitle || t`Resource Not Found`}
      body={errorDescription || t`The Resource you are looking for does not exist or is not accessible.`}
      action={action ?? (<Button variant="primary" onClick={navigateToProjectId}>{t`Go to Project Home`}</Button>)}
    />
  )
}
```

`code={404}` и оба текста — жёстко закодированные дефолты, снимаемые только явно переданными `errorTitle`/`errorDescription`/`action`. Это важно для "Что затронуло" ниже: везде, где эту обёртку регистрируют как `errorComponent:` роута без передачи этих пропов, компонент показывает статичный 404, независимо от реальной причины сбоя.

### Пять новых `errorComponent`

Паттерн одинаковый во всех пяти местах — например `compute/flavors/$flavorId.tsx:25-44`:

```tsx
function FlavorErrorComponent() {
  const { t } = useLingui()
  const navigate = useNavigate()
  const { projectId } = Route.useParams()

  return (
    <RouteIdLevelDefaultError
      action={
        <Button variant="primary" onClick={() => navigate({ to: "/projects/$projectId/compute/flavors", params: { projectId } })}>
          {t`Back to Flavors`}
        </Button>
      }
    />
  )
}
...
export const Route = createFileRoute(...)({
  ...
  errorComponent: FlavorErrorComponent,
})
```

Идентично в `compute/images/$imageId.tsx:41-60` (`ImageErrorComponent`), `network/floatingips.tsx:6-23` (`FloatingIpsErrorComponent`), `network/securitygroups.tsx:6-23` (`SecurityGroupsErrorComponent`), `storage/.../objects/index.tsx:12-30` (`ObjectStorageErrorComponent`, назначен и на `errorComponent`, и на `notFoundComponent`).

Во всех пяти случаях функция объявлена **без параметров** — ни одна не принимает `error`. Отдельно `images/$imageId.tsx:325-336` показывает верный паттерн для **другого** источника ошибки — собственного `useQuery`-состояния компонента (не роутерного `errorComponent`):

```tsx
if (status === "error") {
  const errorMessage = error?.message || t`Unknown error`
  return (
    <RouteIdLevelDefaultError
      errorTitle={t`Error loading image`}
      errorDescription={errorMessage}
      action={<Button onClick={handleBack} variant="primary"><Trans>Back to Images</Trans></Button>}
    />
  )
}
```

Здесь реальный текст ошибки передаётся явно — контраст с `errorComponent: ImageErrorComponent`, которая эту же обёртку вызывает без единого прокинутого прома. Тест на это расхождение не пишется — см. "Ревью".

### Спиннер/Message → Status (пример)

`storage/-components/Swift/Objects/DeleteObjectModal.tsx:134-152` — заодно устранён порядок, при котором ошибка загрузки метаданных могла отрендериться одновременно с состоянием `isLoading`/`isPending` (структура `if/else if metadataError` вместо отдельного блока `{metadataError && (...)}` перед основным деревом):

```tsx
{isPending ? (
  <Status status="progress" title={t`Deleting...`} className="mt-0" />
) : isLoading ? (
  <Status status="progress" title={t`Loading object info...`} className="mt-0" />
) : metadataError ? (
  <Status status="error" title={t`Failed to load object metadata`} body={metadataErrorMessage} className="mt-0" />
) : (
  ...
)}
```

Паттерн идентичен во всех ~50 затронутых модалках — механическая, консистентная замена, проверена выборочно (Ceph `DeleteBucketPolicyModal`, `DeleteCorsRuleModal`; Swift `DeleteObjectModal`, `CopyObjectModal`; Security Groups `AddRuleModal`, `CreateSecurityGroupModal`, `EditSecurityGroupModal`) — везде 1:1 перенос семантики, находок нет.

## Что затронуло

**`errorComponent` игнорирует переданный `error` во всех пяти новых местах — подтверждено типами.** `@tanstack/router-core@1.171.15` (пинована в проекте, `node_modules/.pnpm/@tanstack+router-core@1.171.15/.../route.d.ts:432`) типизирует пропы `errorComponent` как `ErrorComponentProps<TError = Error> = { error: TError; info?; reset: () => void }` — то есть роутер реально передаёт `error` в компонент. Ни `FlavorErrorComponent`, ни `ImageErrorComponent`, ни `FloatingIpsErrorComponent`, ни `SecurityGroupsErrorComponent`, ни `ObjectStorageErrorComponent` не объявляют параметров и не читают `error` — типы это разрешают (структурная совместимость по недостающим пропам), так что `typecheck`/CI это не поймает. См. "Ревью".

**Переименование `Error/` → `Errors/` — само по себе чистое** (проверено: во всём дереве на головном коммите PR не осталось ссылок на `components/Error/` в единственном числе), **но прямо конфликтует с текущей незакоммиченной веткой пользователя** `kiryl-storage-type-404-1081`: там в рабочем дереве лежат новые файлы `packages/aurora/src/client/components/Error/RouteNotFound.tsx` и `RouteNotFound.test.tsx` — в **той же** директории, которую этот PR переименовывает. Если #1304 смержится первым, эта ветка при ребейзе/мерже получит несуществующую (переименованную) директорию под новыми файлами; если наоборот — придётся вручную повторить переименование для файлов из #1081.

**Тот же файл `storage/.../objects/index.tsx` одновременно переписывается в незакоммиченной ветке `kiryl-storage-type-404-1081`** (issue #1081) — по совершенно другой схеме: там `notFound({ data: { reason } })` с разными сообщениями на `provider-not-found`/`storage-type-mismatch` (см. план `DOCS/plans/2026-09-14-storage-type-404-issue-1081.md`), тогда как #1304 здесь просто ставит один и тот же `ObjectStorageErrorComponent` на оба (`notFoundComponent`/`errorComponent`) без различения причины. Оба PR трогают один и тот же роут с несовместимыми дизайнами — независимо от порядка мержа потребуется ручная сверка.

**Покрытие `errorComponent` неравномерно между Network и Compute.** Для Network (`floatingips.tsx`, `securitygroups.tsx`) новый `errorComponent` поставлен на **родительский layout-роут** раздела — значит, он перехватывает ошибки и из списка, и из страницы деталей (`floatingips/$floatingIpId/index.tsx`, `securitygroups/$securityGroupId/index.tsx` через `Outlet`). Для Compute аналогичные layout-роуты (`compute/flavors.tsx`, `compute/images.tsx`) не тронуты этим PR вообще — `errorComponent` есть только на самой странице деталей (`$flavorId.tsx`/`$imageId.tsx`), список (`flavors/index.tsx`/`images/index.tsx`) при ошибке загрузки по-прежнему всплывёт до полноэкранного `ProjectErrorComponent` на уровне `$projectId.tsx`. Не баг (то же поведение, что было везде до PR), но заявленное покрытие "Compute, Network and Object Storage" по факту неполное и несимметричное между разделами.

## Ревью

**[90]** Все пять новых `errorComponent` (`FlavorErrorComponent`, `ImageErrorComponent`, `FloatingIpsErrorComponent`, `SecurityGroupsErrorComponent`, `ObjectStorageErrorComponent`) отбрасывают реальный `error`, переданный роутером, и рендерят жёстко закодированный `RouteIdLevelDefaultError` без `errorTitle`/`errorDescription` — код 404 и текст "Resource Not Found / ...does not exist or is not accessible" показываются **для любой** брошенной ошибки, не только для реального "не найдено". Конкретный воспроизводимый случай: `compute/images/$imageId.tsx` `beforeLoad` (не изменён этим PR, но подпадает под новый `errorComponent: ImageErrorComponent`) вызывает `trpcClient?.auth.getAvailableServices.query()` без try/catch — сетевой сбой или ошибка BFF здесь выдаст пользователю "Resource Not Found" вместо реальной причины. Контраст в том же файле: собственная ручная ветка `status === "error"` (строки 325-336) правильно прокидывает `errorMessage` через `errorTitle`/`errorDescription` — то есть авторы знали о параметрах компонента, но забыли их прокинуть именно в роутерном `errorComponent`. Ни один из пяти wrapper-компонентов не покрыт тестом, который бросает ошибку через сам роут и проверяет отрендеренный текст — только примитивы `RouteIdLevelDefaultError`/`ServiceLevelDefaultError` протестированы напрямую, с руками заданными пропами; путь "реальная ошибка → `errorComponent` → экран" ни разу не воспроизведён в тестах этого PR. Прямо противоречит заявленной цели PR "Improved error messages".

Ниже порога (не репортится, но стоит держать в уме): неравномерное покрытие `errorComponent` между Network (список+детали) и Compute (только детали) — архитектурное решение, не регрессия, но заявлено как единая политика для всех трёх доменов (70/100).

---
Проанализировано: 16.09.2026 · коммит `aac6f9ed9`
