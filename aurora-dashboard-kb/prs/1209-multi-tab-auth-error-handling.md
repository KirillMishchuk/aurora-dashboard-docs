# PR #1209: fix(aurora): improve multi-tab auth error handling (#1128)

**Автор:** andypf · **Статус:** open (не смержен; создан 26.08.2026)
**Ветки:** `andypf/fix-multi-tab-auth-error-1128` → `main` · **Файлов:** 17 (+388/-502)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1209

> PR открыт и активно ревьюится (CodeRabbit + Copilot уже оставили 7 комментариев на момент анализа, часть — на более раннем коммите `e1374ba5` и с тех пор устарела/исправлена). Этот отчёт документирует PR по состоянию головного коммита `c44278f3`.

## Что сделано

Закрывает #1128: если пользователь открывает второй таб с другим доменом/проектом, первый таб продолжает работать со старой session-cookie, которая при следующем запросе больше не соответствует текущему scope на бэкенде. Раньше это приводило к нераспознанной ошибке rescope'а и общему краху UI ("Unable to load content"). PR делает две связанные вещи: на сервере — централизует превращение ошибок OpenStack API в осмысленные tRPC-коды; на клиенте — ловит эти коды в роуте `$projectId` и показывает дружелюбный экран через компонент `Status` из Juno вместо самодельного `StatusError`.

Заодно PR полностью выпиливает два внутренних куска инфраструктуры, которые раньше решали смежные задачи: `resolveProjectScope` (сверял результат rescope с фактическим проектом) и `StatusError` (кастомный компонент экрана ошибки, замененный на `Status` из `@cloudoperators/juno-ui-components@9.4.0`).

## Как это реализовано

### Серверная сторона — `openstackErrorMiddleware`

Новое центральное middleware в `packages/aurora/src/server/trpc.ts:15-64`, подключенное ко всем процедурам через `publicProcedure`:

```ts
export const publicProcedure = t.procedure.use(openstackErrorMiddleware)
```

поскольку `protectedProcedure`/`projectScopedProcedure`/`domainScopedProcedure` в этом же файле все построены поверх `publicProcedure`, middleware действует **на весь API repo-wide**, а не только на поток rescope. Механика (tRPC v11): `next()` не бросает исключение, а возвращает `{ ok: boolean, error?: TRPCError }`; middleware читает `result.error.cause`, и если это `SignalOpenstackApiError`, подменяет `TRPCError` на статически заданное безопасное сообщение по коду:

```ts
// packages/aurora/src/server/trpc.ts:23-44
if (cause instanceof SignalOpenstackApiError) {
  if (cause.statusCode === 401) { code: "UNAUTHORIZED", message: "Session expired or invalid..." }
  if (cause.statusCode === 404 || cause.statusCode === 400) { code: "NOT_FOUND", message: "Resource not found or not accessible. This can happen if you switched domains in another tab." }
  if (cause.statusCode === 403) { code: "FORBIDDEN", message: "Access denied..." }
  // иначе INTERNAL_SERVER_ERROR, "An unexpected OpenStack error occurred"
}
```

Чтобы `cause instanceof SignalOpenstackApiError` вообще работало снаружи пакета `signal-openstack`, PR меняет `packages/signal-openstack/src/index.ts:2,8` — раньше тип экспортировался только как `export type { SignalOpenstackApiError }`, теперь и как значение: `export { SignalOpenstackError, SignalOpenstackApiError } from "./error"`. До этой правки `instanceof`-проверка в новом middleware физически не могла бы скомпилироваться/сработать.

### Серверная сторона — `context.ts`: убран try/catch вокруг rescope

`packages/aurora/src/server/context.ts:326-396` (кэширование rescope-промисов, `pendingRescopes`/`sessionRescopes`) раньше оборачивал вызов `openstackSession.rescope(...)` в try/catch, логировал ошибку и возвращал `null`, чтобы вызывающая сторона (`projectScopedProcedure`/`domainScopedProcedure`) кидала общий `UNAUTHORIZED`. Теперь try/catch снят — ошибка `rescope()` пробрасывается наружу как есть, чтобы её мог поймать и типизировать `openstackErrorMiddleware`. Чтобы не потерять поведение для **конкурентных** запросов (несколько вызовов, дедуплицируемых через `pendingRescopes` по одному и тому же scope-ключу), в карту кладётся не сам промис, а его safe-обёртка:

```ts
pendingRescopes.set(
  scopeKey,
  rescopeTokenPromise
    .catch(() => null) // чтобы конкурентные читатели получали null, а не unhandled rejection
    .finally(() => { /* очистка pendingRescopes/sessionRescopes */ })
)
// ...
const newAuthToken = await rescopeTokenPromise   // ⚠️ исходный, необёрнутый промис
```

Это два разных промиса. Инициирующий запрос ждёт `rescopeTokenPromise` напрямую — он реджектится и долетает до `openstackErrorMiddleware` с полным кодом ошибки. Конкурентные запросы читают из `pendingRescopes` обёрнутую версию, которая при ошибке всегда резолвится в `null` — см. "Ревью" ниже, для них `openstackErrorMiddleware` эту ошибку никогда не увидит.

### Клиентская сторона — `$projectId.tsx`

Раньше (`packages/aurora/src/client/routes/_auth/projects/$projectId.tsx`) loader ловил только `TRPCClientError` с кодом `NOT_FOUND` из `setCurrentScope.mutate(...)`, а после успешного вызова сверял результат через `resolveProjectScope` (сравнение `scopeData.project.id` с `params.projectId` и отдельно зафетченным `project`), кидая `"scope_failed"`/404 при расхождении.

Теперь loader ловит **любой** `TRPCClientError` из `setCurrentScope.mutate(...)`, дополнительно пытается зафетчить `auth.getCurrentScope.query()`, чтобы показать имя текущего домена в сообщении, и возвращает ошибку как **данные** (`scopeError`), а не бросает исключение:

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:33-70
} catch (error) {
  if (error instanceof TRPCClientError) {
    let currentDomain
    try {
      const currentScope = await context.trpcClient?.auth.getCurrentScope.query()
      if (currentScope?.domain?.id && currentScope?.domain?.name) currentDomain = { ... }
    } catch { /* игнорируется */ }
    scopeError = { type: "scope_error", code: error.data?.code || "UNKNOWN", message: error.message, currentDomain }
  } else {
    throw error
  }
}
```

`RouteComponent` рендерит по `scopeError.code` три сценария через `Status` (`UNAUTHORIZED` → «Session Changed», `NOT_FOUND` → «Project Not Accessible», `FORBIDDEN` → «Access Denied»), с fallback на общий `RouteError` для всего остального (в т.ч. буквально для `"UNKNOWN"` — значения по умолчанию, если `error.data?.code` не задан).

### Клиентская сторона — унификация вокруг `Status`

`__root.tsx` (`PageNotFound`), `$projectId.tsx` (`ProjectErrorComponent`, 404-ветка) и `$projectId/compute/flavors/$flavorId.tsx` мигрируют с самодельного `StatusError` (`packages/aurora/src/client/components/Error/StatusError.tsx`, удалён вместе с тестами) на `Status` из Juno — тот же визуальный язык, но через библиотечный компонент вместо форкнутого. Ради `Status` поднят `@cloudoperators/juno-ui-components` 9.3.0 → 9.4.0 (`packages/aurora/package.json:86`, `pnpm-lock.yaml`). Добавленные строки локализованы (`en`/`de` `messages.po`/`.ts`) — механическая правка, замечаний нет.

## Что затронуло

**`openstackErrorMiddleware` — самое широкое изменение в PR.** Он навешан на `publicProcedure`, то есть действует на *весь* API поверхности (`Authentication`, `Compute`, `Network`, `Project`, `Services`, `Storage`), а не только на поток rescope из #1128 — любая необработанная `SignalOpenstackApiError` из любой процедуры теперь получает эти четыре сообщения. Проверено, что это не приводит к двойной обработке ошибок изображений/Swift: `imageHelpers.ts`/`swiftHelpers.ts`'s собственные `mapErrorResponseToTRPCError` (уже маппят 400/403/404/409/413/415 в свои специфичные `TRPCError` с точными сообщениями) **не** проставляют `cause` при конструировании `TRPCError`, так что `cause instanceof SignalOpenstackApiError` для них ложно — middleware их не перезаписывает. Но любой другой роутер, который раньше отдавал `SignalOpenstackApiError` наружу необработанной (а таких в кодовой базе, судя по `git grep`, немало за пределами Compute/Storage), теперь молча получает 400→404-ремаппинг миддлвари — см. находку №4 в "Ревью".

**`SignalOpenstackApiError` теперь экспортируется как значение, не только тип.** Проверено `git grep` по всему репозиторию на головном коммите: единственное место, где `instanceof SignalOpenstackApiError` используется через публичный импорт пакета — новый `trpc.ts`. Остальные потребители (`imageHelpers.ts`, `imageRouter.ts`, `swiftHelpers.ts`) используют его только как тип аннотации, так что смена типа экспорта на value-экспорт им ничем не грозит.

**`resolveProjectScope`/`StatusError` — удалены без остатка.** `git grep` по головному коммиту не находит ни одной ссылки ни на то, ни на другое имя — устаревших потребителей не осталось. Но `resolveProjectScope` не был случайным легаси: он был добавлен целенаправленно в PR #1035 ("improve project not found error handling") и доработан в PR #1061 ("avoid fetching all projects on project detail page") — то есть решал реальные прошлые баги. Его удаление без прямой замены разбирается в "Ревью" (находка №1).

## Ревью

**Найдено (confidence ≥ 80):**

1. **`sessionRouter.ts:41` `setCurrentScope` — нет проверки на `null`; вместе с удалением `resolveProjectScope` неудачный rescope молча репортится как успех.** (confidence 95)
   Все три ветки (`domain`/`project`/`unscoped`) в `setCurrentScope` делают `const session = await ctx.rescopeSession(...)` и сразу используют `session?.getToken()` через опциональную цепочку — нет `if (!session) throw`. `rescopeSession` **может** резолвиться в `null` без исключения (не залогиненный пользователь, а с находкой №2 ниже — ещё и конкурентный запрос с проваленным rescope). Раньше это ловилось за счёт `resolveProjectScope`, сравнивавшего `scopeData.project.id` с запрошенным `projectId` уже *после* успешного (не кинувшего исключение) `mutate()`; теперь эта проверка удалена без замены. Итог: `setCurrentScope.mutate(...)` в loader'е `$projectId.tsx` резолвится успешно с `{project: undefined, domain: undefined}`, `scopeError` не выставляется, и роут рендерится дальше как обычно — тот самый "friendly error UI", который PR добавляет, в этом случае не покажется вообще, хотя scope фактически не установлен. Подтверждено независимо: тот же вывод сделал автоматический ревью Copilot на этом PR на этой же строке (комментарий от 27.08, на головном коммите `c44278f3`).
   Файл: `packages/aurora/src/server/Authentication/routers/sessionRouter.ts:28-52`.

2. **`context.ts:373-390` — конкурентные (дедуплицированные) запросы теряют статус ошибки rescope: `openstackErrorMiddleware` их не видит.** (confidence 90)
   Как описано в "Как это реализовано", в `pendingRescopes` кладётся `rescopeTokenPromise.catch(() => null).finally(...)` — промис, который **никогда не реджектится**. Инициирующий запрос ждёт исходный `rescopeTokenPromise` и корректно долетает до middleware с `SignalOpenstackApiError` в `cause`. Но конкурентный запрос (другой таб/запрос с тем же scope-ключом, попавший в ветку дедупликации раньше в этой же функции) дожидается именно обёрнутой версии из карты — при ошибке получает голый `null`, что приводит к generic `throw new TRPCError({ code: "UNAUTHORIZED", message: "Failed to scope session..." })` двумя строками ниже в `trpc.ts` (`projectScopedProcedure`/`domainScopedProcedure`), а не к точной 401/403/404-специфичной ошибке из middleware. Учитывая, что PR называется "multi-tab auth error handling" — это ровно тот сценарий с несколькими конкурентными запросами, который он должен покрывать. Подтверждено независимо тем же выводом в комментарии Copilot на этом PR (`context.ts:377`, головной коммит).
   Файлы: `packages/aurora/src/server/context.ts:355-396`, `packages/aurora/src/server/trpc.ts:151-165, 263-277`.

3. **`$projectId.tsx` — ветка `UNAUTHORIZED` всегда показывает нарратив "сессия сменилась из-за другого таба", даже если сессия истекла по-настоящему.** (confidence 85)
   `openstackErrorMiddleware` мапит **любой** 401 от OpenStack (и просроченный/невалидный токен, и токен, ставший невалидным из-за смены scope в другом табе) в один и тот же код `UNAUTHORIZED` со статическим сообщением "Session expired or invalid. Please log in again." Клиент же, поймав `code === "UNAUTHORIZED"`, безусловно рендерит «Session Changed» / «Your session context has changed, possibly because you switched domains in another browser tab... Please select a project from your current domain to continue» — с кнопкой «Go to Projects», а не предложением перелогиниться. Для пользователя с реально истёкшей сессией (сервер восстановить которую не может в принципе) это вводящая в заблуждение инструкция — выбор проекта её не починит, нужен повторный логин. Сервер и клиент вместе не различают эти два принципиально разных случая, хотя оба возможны под одним и тем же кодом ошибки.
   Файлы: `packages/aurora/src/server/trpc.ts:27-33` (маппинг 401), `packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:111-127` (безусловный рендер "Session Changed" для любого `UNAUTHORIZED`).

4. **`trpc.ts:33` — статус 400 от OpenStack бланково маппится в `NOT_FOUND` для *всех* процедур репозитория, не только для потока rescope.** (confidence 82)
   `if (cause.statusCode === 404 || cause.statusCode === 400) { code: "NOT_FOUND", message: "...This can happen if you switched domains in another tab." }` — сообщение сформулировано специально под сценарий #1128, но применяется middleware'ом ко всем `publicProcedure`-процедурам без разбора. 400 от OpenStack в общем случае означает невалидный payload (например, при создании/обновлении ресурса), а не "не найдено" — для любой такой процедуры, не имеющей собственного явного перехвата `SignalOpenstackApiError` (что подтверждено верно для Compute-image/Swift, но не проверялось для всей остальной поверхности API), пользователь теперь увидит вводящее в заблуждение "not found... possibly switched domains" вместо ошибки валидации. Подтверждено независимо тем же выводом в комментарии Copilot на этом PR (`trpc.ts:43`, головной коммит).
   Файл: `packages/aurora/src/server/trpc.ts:33-41`.

**Проверено и отклонено как false positive:** комментарий CodeRabbit на этом PR (`trpc.ts:61`, "raw OpenStack error text reaches the UI... middleware fallback copies the upstream cause.message into the client-visible TRPCError") не подтверждается кодом на головном коммите — все четыре ветки `openstackErrorMiddleware` используют статически заданные безопасные сообщения (например, `"An unexpected OpenStack error occurred"` для fallback-ветки, `trpc.ts:60`), нигде не подставляя `cause.message`. Кастомного `errorFormatter` в `initTRPC.create()` нет, так что `TRPCError.cause` в принципе не сериализуется клиенту напрямую (см. прецедент в отчёте по PR #1073, где эта же тема разбиралась для `s3ErrorMapper.ts` — там утечка была реальной именно потому, что raw-текст попадал в `.message`, а не в `.cause`; здесь такого нет).

**Также замечено (confidence 50-79, не набрало полной уверенности):**
- **[70]** Copilot-комментарий на `$projectId.tsx:63` указывает, что TanStack Router выполняет loader'ы дочерних роутов параллельно с родительским, а не последовательно — то есть возврат `scopeError` как данных (вместо throw) в `$projectId.tsx` не останавливает дочерние scoped-запросы (например, во вложенных роутах `compute`/`network`/`storage`), которые могут упасть сами и показать грубый error boundary поверх дружелюбного экрана. Правдоподобно и согласуется с общей архитектурой TanStack Router, но не проверено пошагово по фактическому дереву роутов в рамках этого разбора.
- **[55]** `PageNotFound` (`__root.tsx`) и 404-ветка `ProjectErrorComponent` (`$projectId.tsx`) при миграции со `StatusError` на `Status` потеряли кнопку "Back" (`router.history.back()`, вместе с неиспользуемым теперь импортом `useRouter`) — остался только "Go to Home"/"Go to Projects". При этом соседняя миграция в `$flavorId.tsx` в том же PR кнопку "Back" сохранила — несогласованность наводит на мысль, что это недосмотр, а не осознанное решение. Небольшая, легко обратимая UX-регрессия.

---
Проанализировано: 27.08.2026 · коммит `c44278f3`
