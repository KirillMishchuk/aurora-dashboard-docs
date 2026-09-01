# PR #1209: fix(aurora): improve multi-tab auth error handling (#1128)

**Автор:** andypf · **Статус:** создан 26.08.2026, обновлён 27.08.2026, смержен 27.08.2026 (коммит `9796a71b`)
**Ветки:** `andypf/fix-multi-tab-auth-error-1128` → `main` · **Файлов:** 18 (+434/-521)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1209

> 2-я версия отчёта. Автор запушил фикс-коммиты в ответ на находки 1-й версии (все они также независимо всплыли в автоматическом ревью Copilot/CodeRabbit на этом же PR). Головной коммит сменился `c44278f3` → `6c2fedef`; база (`main`) не изменилась. Сравнение ниже — именно между этими двумя версиями PR, не PR целиком.

## Что изменилось со времени первой версии

Все 4 находки уровня ≥80 из 1-й версии отчёта закрыты точечными фикс-коммитами; проверено построчно по факту, не со слов PR-описания (которое осталось нетронутым и всё ещё показывает старый текст "Session Changed" в разделе "User Experience" — устарело).

1. **`sessionRouter.ts` — добавлена проверка на `null`.** Ветки `domain`/`project` в `setCurrentScope` теперь кидают `TRPCError({ code: "NOT_FOUND" })`, если `token?.tokenData.domain`/`token?.tokenData.project` не установлены после rescope:
   ```ts
   // packages/aurora/src/server/Authentication/routers/sessionRouter.ts:36-43
   if (!token?.tokenData.project) {
     throw new TRPCError({ code: "NOT_FOUND", message: "Failed to rescope to the requested project." })
   }
   ```
   `sessionRouter.test.ts` обновлён в этом же коммите — тест "should handle null session from rescopeSession" теперь проверяет `rejects.toThrow(TRPCError)` вместо прежнего `expect(result).toEqual({project: undefined, ...})`. Закрывает находку №1 (было 95/100).

2. **`context.ts` — `pendingRescopes` теперь хранит исходный (реджектящийся) промис, а не safe-обёртку.** Вместо `rescopeTokenPromise.catch(() => null).finally(...)`, положенного в карту, теперь:
   ```ts
   // packages/aurora/src/server/context.ts:370-393
   const cleanupPromise = rescopeTokenPromise.finally(() => { /* очистка pendingRescopes/sessionRescopes, без изменений */ })
   pendingRescopes.set(scopeKey, rescopeTokenPromise)     // ← исходный промис, не .catch(() => null)
   cleanupPromise.catch(() => {})                          // ← unhandled rejection гасится на ОТДЕЛЬНОМ производном промисе
   ```
   Проверено: ветка дедупликации конкурентных запросов (`await cachedTokenPromise`, чуть выше в этой же функции) по-прежнему не оборачивает `await` в try/catch — то есть при ошибке она теперь честно реджектится и пробрасывает `SignalOpenstackApiError` дальше в `openstackErrorMiddleware`, как и вызов-инициатор. Комментарий "Prevent unhandled rejection on the cleanup promise" теперь корректно описывает, что именно он гасит (в 1-й версии комментарий указывал не на тот промис). Закрывает находку №2 (было 90/100).

3. **`$projectId.tsx` — сообщение для `UNAUTHORIZED` переписано, чтобы не подразумевать неверное восстановление.** Вместо «Session Changed... Please select a project from your current domain» (с кнопкой «Go to Projects») теперь:
   ```tsx
   // packages/aurora/src/client/routes/_auth/projects/$projectId.tsx:106-119
   title={t`Session Expired`}
   body={t`Your session has expired. Please log in again. This may have occurred because you logged out or switched domains in another browser tab.`}
   action={<Button variant="primary" onClick={() => navigate({ to: "/" })}><Trans>Log In</Trans></Button>}
   ```
   Сервер по-прежнему не различает "сессия правда истекла" и "невалидна из-за смены домена в другом табе" (оба случая — 401 → один и тот же `UNAUTHORIZED`), но теперь единственное действие, которое предлагается ("Log In" → `/`), одинаково корректно работает для обоих сценариев — в отличие от прежнего "выберите проект", которое было бесполезно при реально истёкшей сессии. Закрывает находку №3 (было 85/100).

4. **`trpc.ts` — 400 выделен в отдельную ветку `BAD_REQUEST`, больше не смешивается с 404/`NOT_FOUND`.**
   ```ts
   // packages/aurora/src/server/trpc.ts:34-43
   if (cause.statusCode === 400) {
     return { ...result, error: new TRPCError({ code: "BAD_REQUEST", message: "The OpenStack request was invalid.", cause }) }
   }
   if (cause.statusCode === 404) {
     return { ...result, error: new TRPCError({ code: "NOT_FOUND", message: "Resource not found or not accessible. This can happen if you switched domains in another tab.", cause }) }
   }
   ```
   Закрывает находку №4 (было 82/100).

**Не тронуто с 1-й версии** (те же файлы, тот же код): `__root.tsx`, `$flavorId.tsx`, `packages/signal-openstack/src/index.ts` — байт в байт совпадают с коммитом `c44278f3`.

## Что сделано (актуально для v2, без изменений в сути)

Закрывает #1128: если пользователь открывает второй таб с другим доменом/проектом, первый таб продолжает работать со старой session-cookie, которая при следующем запросе больше не соответствует текущему scope на бэкенде. PR централизует превращение ошибок OpenStack API в осмысленные tRPC-коды на сервере (`openstackErrorMiddleware` в `trpc.ts`, действует на `publicProcedure` и, транзитивно, на весь API) и показывает дружелюбный экран через `Status` из Juno на клиенте (`$projectId.tsx`) вместо краха. Заодно удаляет `resolveProjectScope.ts` (сверял результат rescope с фактическим проектом) и `StatusError.tsx` (кастомный компонент экрана ошибки, заменён на `Status` из `@cloudoperators/juno-ui-components@9.4.0`).

## Что затронуло

Актуально по-прежнему: `openstackErrorMiddleware` действует на весь API repo-wide через `publicProcedure`, а не только на поток rescope. Подтверждено (см. v1 отчёта), что это не приводит к двойной обработке ошибок в `imageHelpers.ts`/`swiftHelpers.ts` — их `mapErrorResponseToTRPCError` не проставляет `cause`, так что `cause instanceof SignalOpenstackApiError` для них ложно. `SignalOpenstackApiError`-value-экспорт и удаление `resolveProjectScope`/`StatusError` — без изменений, детали см. в v1 (сохранён в истории файла).

## Ревью

**Найдено в 1-й версии (confidence ≥ 80) — все 4 закрыты в этой версии:**

1. ~~`sessionRouter.ts:41` — нет проверки на `null`, неудачный rescope молча репортится как успех~~ (было 95/100) — **закрыто**, см. "Что изменилось" п.1.
2. ~~`context.ts` — конкурентные запросы теряют статус ошибки rescope~~ (было 90/100) — **закрыто**, см. п.2.
3. ~~`$projectId.tsx` — `UNAUTHORIZED` всегда показывает нарратив про смену домена, даже при реальном истечении сессии~~ (было 85/100) — **закрыто**, см. п.3.
4. ~~`trpc.ts` — 400 бланково маппится в `NOT_FOUND`~~ (было 82/100) — **закрыто**, см. п.4.

**Новое в этой версии (confidence ≥ 80): не найдено.**

**Также замечено (confidence 50-79, ниже порога включения):**
- **[65]** `sessionRouter.ts` case `"unscoped"` (строки 76-81) остаётся без проверки результата: `await ctx.rescopeSession({})` вызывается, но возвращаемое значение никуда не сохраняется и не проверяется — мутация безусловно возвращает `{project: null, domain: null}` независимо от того, удался rescope или нет. Та же категория проблемы, что и закрытая находка №1, но для ветки `unscoped`. Confidence снижен относительно найденного ранее для `domain`/`project`, потому что `git grep` по головному коммиту не находит ни одного клиентского вызова `setCurrentScope` с `type: "unscoped"` — путь существует в роутере, но сейчас не достижим ни из одного известного UI-сценария, так что реального пользовательского impact на сегодня нет.
- **[70]** Copilot-комментарий на `$projectId.tsx:63` про параллельное выполнение loader'ов дочерних роутов в TanStack Router (friendly-экран родителя не останавливает дочерние scoped-запросы) — без изменений с 1-й версии, не адресовано в этом обновлении.
- **[55]** Отсутствие кнопки "Back" в `PageNotFound` (`__root.tsx`) и 404-ветке `ProjectErrorComponent` (`$projectId.tsx`) при миграции на `Status`, при том что `$flavorId.tsx` в том же PR кнопку сохранил — без изменений с 1-й версии, не адресовано.
- **[15, отклонено]** Комментарий CodeRabbit на `trpc.ts:71` (текущий головной коммит `6c2fedef`), повторяющий claim из 1-й версии про "raw cause.message reaches the UI" — перепроверено против актуального кода: fallback-ветка `INTERNAL_SERVER_ERROR` (`trpc.ts:64-71`) по-прежнему использует статическую строку `"An unexpected OpenStack error occurred"`, `cause.message` нигде не используется как значение `message`. Похоже, это залипший/неточный шаблонный комментарий бота, не привязанный к фактическому содержимому строки — тот же вывод, что и в 1-й версии.

## Что сделано хорошо

Все 4 находки были устранены точечными, минимальными коммитами (не переписыванием заново), с обновлением сопутствующего теста там, где было нужно (`sessionRouter.test.ts`). Комментарий в `context.ts` про "Prevent unhandled rejection" при этом стал более точным, а не просто был удалён — фикс не просто убрал внешние симптомы, а действительно исправил семантику двух разных промисов.

---
Проанализировано: 27.08.2026 (v1: коммит `c44278f3`, v2: коммит `6c2fedef`)
