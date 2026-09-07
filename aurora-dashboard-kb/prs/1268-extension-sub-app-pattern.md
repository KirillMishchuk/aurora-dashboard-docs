# PR #1268: feat(aurora): replace route-injection with standalone extension sub-app pattern

**Автор:** taymoor89 · **Статус:** 03.09.2026 (открыт, не смержен; approved andypf 04.09.2026)
**Ветки:** `1253-change-additional-services-integration` → `main` · **Файлов:** 18 (+305/-87)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1268

## Что сделано

Смена модели интеграции сторонних (SCI) сервисов в Aurora. Было: потребитель отдавал в OSS готовые TanStack-роуты, и они **вклеивались в дерево роутов OSS** (`AdditionalProjectService.routes: AnyRoute` + экспортируемый `servicesRoute` как parent + общий `ProjectId`-контекст). Стало: потребитель регистрирует **самодостаточный React-компонент**, который OSS монтирует под `/projects/$projectId/services/$serviceType/**`; компонент поднимает **свой собственный** `RouterProvider` с `basepath` и получает данные хоста через расширяемый объект `context`, а не через общий React-контекст.

Заодно унифицирован словарь: всё, что называлось «additional project service», стало «service extension» (`AdditionalProjectService` → `ServiceExtension`, проп `additionalProjectServices` → `serviceExtensions`).

Ключевой момент по истории: заменяемый паттерн прожил **11 дней** — route-injection ввёл тот же автор в `a9c257a1` (#1189, 24.08.2026), и его changeset прямо продавал механику «pass your service definitions via the `additionalProjectServices` prop… to plug in client-side routes». Триггером разворота стал комментарий в issue #1102 («Reopening this task and converting this to an epic in order to change the approach how we handle breadcrumbs and additional services integration»), из которого вырос #1253. Это не внешнее требование, а быстрый внутренний пересмотр только что выпущенного дизайна — при чтении базы знаний полезно помнить, что раздел про route-injection устарел через полторы недели после появления.

## Как это реализовано

**Контракт регистрации** (`packages/aurora/src/client/AuroraApp.tsx:61-100`). Три новых типа вместо одного: `ServiceExtensionContext` (сейчас `{ projectId }`, но расширяемый — смысл именно в том, чтобы будущие поля вроде `domainId`/`scope` не меняли сигнатуру компонента), `ServiceExtensionProps = { basePath, context }` и сам `ServiceExtension`, где вместо `routes` теперь `component`:

```ts
export type ServiceExtension = {
  /** OpenStack catalog service type, e.g. `"pca"`. */
  serviceType: string
  /** OpenStack catalog service name, e.g. `"clavis"`. */
  serviceName: string
  /** Nav item and service card label. */
  label: string
  /**
   * The React component to render at `/projects/$projectId/services/$serviceType/**`.
   * Receives `basePath` (the URL prefix) and `context` (host data). Create your own RouterProvider
   * inside this component using `basePath` as the `basepath` prop and `context` as the router context.
   *
   * Note: this is a self-contained sub-app. Host slots (see `Slots`) are not injected into it, so the
   * extension owns its own header/actions (e.g. via the re-exported `PageContentHeader` `actions` prop).
   */
  component: FC<ServiceExtensionProps>
}
```
— `AuroraApp.tsx:84-100`

Заявленное «host slots в под-приложение не инжектятся» — не просто декларация в доке: в `ServiceExtensionContext` поля `slots` нет, и монтирующий компонент передаёт наружу только `{ projectId }`, так что структурно пути к слотам у расширения нет.

**Монтирование.** Вся развязка — в одном компоненте на 23 строки:

```tsx
export function ServiceExtensionMount() {
  const { projectId, serviceType } = useParams({ strict: false }) as { projectId: string; serviceType: string }
  const { serviceExtensions } = useRouteContext({ strict: false })
  const extension = serviceExtensions?.find((s) => s.serviceType === serviceType)

  // Memoize so the object reference stays stable across renders and the extension's own
  // createRouter (seeded with this context) is not recreated on every render.
  const context = useMemo<ServiceExtensionContext>(() => ({ projectId }), [projectId])

  if (!extension?.component) return null

  const basePath = `/projects/${projectId}/services/${serviceType}`
  const ServiceComponent = extension.component
  return <ServiceComponent basePath={basePath} context={context} />
}
```
— `.../services/$serviceType/-components/ServiceExtensionMount.tsx:9-23`

**Три новых роута с разделением ролей.** Монтирование живёт на **layout**-роуте, а `index` и splat существуют только для матчинга URL — это осознанное решение, и оно задокументировано в коде:

```tsx
// Render the extension mount at the layout level so it stays mounted across all
// /services/$serviceType/** navigation. The index and splat child routes exist only to
// match the URL (so deep links don't 404); if the mount rendered in those children instead,
// navigating between them would tear down and rebuild the extension's own RouterProvider,
// losing its state, scroll position, and in-flight fetches.
export const Route = createFileRoute("/_auth/projects/$projectId/services/$serviceType")({
  staticData: { section: "services" },
  component: ServiceExtensionMount,
})
```
— `.../services/$serviceType.tsx:4-12` (оба ребёнка — `component: () => null`: `$serviceType/index.tsx:6`, `$serviceType/$.tsx:7`)

Проверено отдельно (против `@tanstack/react-router@1.168.22`): опасение «расширение A остаётся смонтированным, пока URL уже указывает на B» не реализуется — `ServiceExtensionMount` при смене `serviceType` не размонтируется, но подставляет другую функцию-компонент, и React корректно размонтирует старое поддерево по различию типа элемента.

**Публичная поверхность** (`packages/aurora/src/client/index.ts`). Убрано: `AdditionalProjectService`, `useProjectId`, `servicesRoute`. Добавлено: `ServiceExtension`, `ServiceExtensionProps`, `ServiceExtensionContext` и `PageContentHeader` (переименованный ре-экспорт `ContentHeader`, чтобы расширение могло отрисовать хедер в стиле OSS со своими экшенами). Переименование при экспорте — уже принятая в репо практика (ср. `ObjectBrowserView as CephObjects`).

**Навигация.** `buildNavSections` больше не может навигировать по `module.routes.fullPath` (роутов-то нет) и переходит на статический путь с параметрами; подсветка активного пункта получила фолбэк на URL-параметр, потому что у mount-роута нет статического `service`:

```ts
const activeService = activeRouteInfo?.service ?? serviceType ?? null
```
— `.../projects/-components/SideNavBar.tsx:38`

**Хлебные крошки.** На `/services/$serviceType/**` OSS не показывает секционную крошку (как и в compute/network/storage), а всё ниже уровня сервиса расширение публикует само через `usePushBreadcrumbs`. Это прямое применение механики, построенной за два дня до этого в #1254 (`0cadedd9`), а не конфликт с ней: `useBreadcrumbs.ts` уже тогда документировался как пригодный для встроенных под-приложений, а `Breadcrumbs.tsx` — как мерджящий `BreadcrumbExtensionContext`.

**Мелкая закалка.** `EMPTY_SERVICE_EXTENSIONS` объявлен на уровне модуля (`App.tsx:39`) и подставляется, когда проп не передан (`App.tsx:108`), чтобы не ломать мемоизацию `buildNavSections` новым `[]` на каждый рендер. Проверено: константа действительно на уровне модуля, а нижестоящая мемоизация зависит от самой ссылки `serviceExtensions`, а не от оборачивающего объекта контекста, так что закалка работает.

## Что затронуло

**Внутри монорепо ломать нечего — и это проверено.** `additionalProjectServices`, `AdditionalProjectService` и `ProjectIdContext` на `4df9ccea` не встречаются ни в одном файле; `apps/dashboard` этих API не использовал вообще, а зависимость у него `workspace:*` (`apps/dashboard/package.json:20`), то есть тип бампа для него безразличен. `useProjectId` остаётся живым и активно используемым **внутри** пакета (117 файлов) — из публичного индекса он убран, но не удалён, так что внутренние потребители не затронуты.

**Реальный риск — только у внешних потребителей.** Пакет публикуемый (`publishConfig.access: "public"`, версия 1.1.0), и это классическая breaking-смена контракта: SCI-дашборд должен переехать в lockstep. Координация этого переезда **нигде не отслеживается** — единственное упоминание в PR это шаг «Rebuild and install OSS into the SCI dashboard» в инструкции по тестированию; ни линкованного issue, ни чеклиста.

**Тип бампа — `minor` при шести задокументированных breaking changes — соответствует практике проекта, а не нарушает её.** Это стоит зафиксировать, потому что выглядит как ошибка, но ей не является: в `packages/aurora/CHANGELOG.md:6-9` удаление публичного `getAuthToken` с миграционной заметкой вышло как minor (коммит `8e99f074` в своём сообщении прямо пишет «Upgraded to minor version due to breaking API change»); `.changeset/tempurl-restrictions.md` — minor при breaking-ограничении TempURL; `.changeset/brave-weeks-warn.md` — вообще `patch` при секции «Breaking change for API consumers». Единственный major в истории (1.0.0, `2c7bd0e7`) был осознанным исключением. `docs/semantic_release.md`, где написано про major по `BREAKING CHANGE:`, — мёртвый документ: ни `.releaserc.js`, ни semantic-release workflow в репо нет, релиз идёт через changesets-экшен.

**Тесты не переписаны под новое поведение — они механически переименованы.** `buildNavSections.test.ts` (+4/-5): только `AdditionalProjectService`→`ServiceExtension` и `routes: {} as unknown as AnyRoute`→`component: () => null`, сами ассерты не тронуты. `useBreadcrumbs.test.tsx` (+1/-1): переименование поля в моке `useRouteContext`, который сам хук вообще не вызывает (он работает через `useMatches`/`DynamicBreadcrumbContext`) — мёртвая заглушка, доставшаяся от #1254. То есть нового поведения (монтирование, splat, фолбэк подсветки, поведение при незарегистрированном типе) не покрывает ни один тест.

## Ревью

Пять параллельных агентов (конвенции/версионирование, скан багов, история, прошлый фидбек, соответствие докам и комментариям) плюс confidence-scoring. Порог ≥80 прошла одна находка; три набрали 75 и вынесены отдельным блоком, потому что по существу они полезнее, чем их балл.

### [100] Changeset публикует три несуществующих breaking change

`.changeset/extension-sub-app-pattern.md` — это не описание PR, а потребительские release notes: релизный экшен копирует текст changeset'а дословно в `packages/aurora/CHANGELOG.md`. Три из шести заявленных breaking changes не соответствуют действительности:

| Заявка в changeset | Факт |
| --- | --- |
| «`ProjectIdContext` export removed» (стр. 11) | Ни экспорта, ни типа, ни файла с таким именем в истории репозитория **никогда не было**: `git log --all -S'ProjectIdContext'` не даёт ни одного коммита, кроме ветки самого PR |
| «`AuroraAppProps.router` prop removed» (стр. 13) | У `AuroraAppProps` поля `router` не было ни в одном коммите, включая базу `273aebbe` (там только `theme`, `bffEndpoint`, `onThemeChange`, `slots`, `appName`, `onTrackEvent`, `enabledServices`, `additionalProjectServices`) |
| `usePushBreadcrumbs` в разделе «New exports» (стр. 19) | Уже экспортировался до этого PR — `git show 273aebbe:packages/aurora/src/client/index.ts:25`, добавлен в #1254 |

Плюс более мягкая формулировочная неточность: «`ServiceExtensionProps` reshaped from `{ basePath, projectId }` to `{ basePath, context }`» (стр. 10) — типа с таким именем до этого PR не существовало вовсе, он вводится здесь же, так что «reshaped» вводит в заблуждение.

Практический вред: внешний потребитель, читая CHANGELOG, будет искать в своём коде `ProjectIdContext` и проп `router`, которых у него нет и быть не могло, и при этом получит неверное представление о том, что нового появилось. Подтверждено двумя агентами независимо и перепроверено вручную по `git log --all -S` и блобам базы. Правится до мержа — правкой файла changeset'а.

### Ниже порога [75], но именно это стоит поправить в коде

- **Пустая страница вместо 404 при неизвестном `serviceType`.** `$serviceType` + splat `$` вместе матчат **любой** URL под `/services/**`, а `ServiceExtensionMount.tsx:18` на промахе поиска возвращает `null`. Итог: устаревшая ссылка, опечатка или тип сервиса, который есть в каталоге OpenStack, но не зарегистрирован как расширение, дают полностью пустую контентную область внутри обычной оболочки проекта — без ошибки, без редиректа, без `notFoundComponent: PageNotFound` (`routes/__root.tsx:29`), который до этого PR как раз и срабатывал, потому что незарегистрированного роута в дереве просто не было. Ср. аналогичный динамический сегмент в storage: `storage/$provider/$storageType/index.tsx` валидирует его через `checkServiceAvailability` и всегда бросает `redirect()` на осмысленный фолбэк. **Это же замечание оставил Copilot на самом PR и оно осталось без ответа и без правки** — при этом соседнее его замечание (про дубликаты `serviceType`) автор отклонил осознанно и с объяснением («OSS `aurora` shouldn't second-guess consumers intent»), так что молчание здесь выглядит именно пропуском, а не решением. Approve от andypf («Looks good to me, no regressions so far») этот пункт не снимает.
- **«No user-visible change» в описании PR противоречит его же changeset'у.** Утверждение «N/A (no user-visible change; projectId resolves identically inside mounted extensions)» верно про `projectId`, но changeset тут же документирует, что на `/services/**` пропадает секционная крошка, а крошки роутов внутри собственного роутера расширения больше не видны `useMatches()`-основанной крошечной панели OSS, пока расширение не вызовет `usePushBreadcrumbs` на каждом уровне. Крошка, которая раньше рисовалась, а теперь нет, — видимое изменение.
- **Мёртвый `servicesRoute` остался в исходниках.** Публичный ре-экспорт убран, route-injection удалён, но сам файл всё ещё отдаёт алиас: `.../services.tsx:7` → `export { Route as servicesRoute }`. Артефакт ровно того механизма, который PR заменяет.

### Ниже порога [50], как контекст

- `$serviceType.tsx:10` пишет `staticData: { section: "services" }` без `satisfies RouteInfo`, тогда как сопоставимые роуты в репо это утверждение ставят стабильно (`_auth.tsx:8-10`, `storage/$provider/$storageType.tsx:7-10`). Типизацию не ломает.
- Новый публичный экспорт `PageContentHeader` в `packages/aurora/README.md` не упомянут ни разу, хотя PR переписывает в этом README раздел «Service extensions», а экспорт добавлен именно для авторов расширений. Остальная часть раздела при этом сверена с кодом на `4df9ccea` и совпадает точно — имена, пропы, формы типов и оба примера с `createRouter({ routeTree, context })`/`useRouteContext`.
- Выход за рамки issue #1253: issue просит лишь «render consumer supplied project services as isolated components», удаления `useProjectId`/`servicesRoute` из публичного API там нет. Как следствие нового паттерна это защитимо, но формально это расширение объёма, и ревьюеры его не обсуждали.

---
Проанализировано: 04.09.2026 · коммит `4df9ccea`
