# PR #1076: refactor(aurora): migrate AuthProvider to tRPC React Query hooks

**Автор:** andypf · **Статус:** open, draft (не смержен)
**Ветки:** `andypf/refactor-auth-provider-to-trpc-react` → `main` · **Файлов:** 6 значимых (+~230/-~380, без учёта шума changesets/CHANGELOG/локалей, см. ниже)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1076

> ⚠️ PR открыт как **draft** и не смержен. `baseRefOid`, который отдаёт `gh`, указывает на коммит `3e8f1bf` (#1074), который с тех пор ушёл вперёд по `main` (сейчас `main` на `28cc3ff`, включая #1079/#1080). `gh pr diff` из-за этого подмешивает шумовые реверты `CHANGELOG.md`/`package.json`/локалей — отчёт ниже построен на `git diff <baseRefOid>..<headRefOid>`, что даёт чистый диф только по файлам, которые реально тронул этот PR.

## Что сделано

PR продолжает рефакторинг auth-флоу, начатый в PR #1072 (см. [1072-simplify-auth-flow.md](./1072-simplify-auth-flow.md)): `AuthProvider` переводится с вызовов vanilla `trpcClient` + ручного `useState`/`useEffect` на хуки `trpcReact` (`useQuery`/`useMutation`), то есть на тот же паттерн, что уже используется в остальном клиентском коде пакета. Помимо самого `AuthProvider`, PR правит два небольших layout-фикса (центрирование `LoginForm` и спиннера на `/projects`) и синхронно переписывает три тестовых файла под новый паттерн моков.

## Как это реализовано

**Сессия как React Query-запрос** (`packages/aurora/src/client/store/AuthProvider.tsx:19-32`):

```tsx
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const trpcUtils = trpcReact.useUtils()

  const sessionQuery = trpcReact.auth.getCurrentUserSession.useQuery(undefined, {
    staleTime: Infinity, // Session only changes via login/logout
    retry: false,
  })

  const user = sessionQuery.data?.user ?? null
  const expiresAt = sessionQuery.data?.expires_at
  const isInitialLoading = sessionQuery.isLoading
  const isRefetching = sessionQuery.isRefetching
  const error = sessionQuery.error?.message ?? null
```

Раньше сессия жила в четырёх `useState` и грузилась вручную в `useEffect` (см. #1072). Теперь источник истины — кэш React Query; `staleTime: Infinity` осознанно отключает фоновые рефетчи по времени (сессия меняется только явным `login`/`logout`), `retry: false` сохраняет прежнее поведение "не ретраить".

**Login/logout — мутации, кэш обновляется вручную** (`AuthProvider.tsx:68-93`):

```tsx
const loginMutation = trpcReact.auth.createUserSession.useMutation()

const login = async ({ domain, user, password }: { domain: string; user: string; password: string }) => {
  try {
    const tokenData = await loginMutation.mutateAsync({ domainName: domain, user, password })
    trpcUtils.auth.getCurrentUserSession.setData(undefined, tokenData)
    return { success: true }
  } catch {
    return { success: false }
  }
}

const logoutMutation = trpcReact.auth.terminateUserSession.useMutation()

const logout = async () => {
  try {
    await logoutMutation.mutateAsync()
  } catch {
    // Server-side termination failed, but we still clear local state
  }
  redirectToLogin(false)
}
```

После успешного логина кэш `getCurrentUserSession` заполняется напрямую результатом мутации (`trpcUtils...setData`), без повторного похода на сервер — экономит один round-trip по сравнению с инвалидацией+рефетчем. `logout` намеренно всегда чистит локальное состояние и редиректит, даже если серверный `terminateUserSession` упал — это то же поведение, что было и до PR (см. #1072), просто перенесённое на мутацию.

**`redirectToLogin` больше не проверяет путь до построения `returnUrl`** (`AuthProvider.tsx:34-47`):

```tsx
const redirectToLogin = (saveReturnUrl: boolean = false) => {
  const returnUrl = saveReturnUrl
    ? `/?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`
    : "/"

  if (window.location.pathname === "/") {
    // Already on login page - just clear session query, no redirect needed
    trpcUtils.auth.getCurrentUserSession.setData(undefined, undefined)
  } else {
    // Redirect triggers page reload which clears cache
    window.location.href = returnUrl
  }
}
```

Если уже на `/`, вместо `window.location.href` (что раньше не делало вообще ничего) теперь явно чистится кэш сессии через `setData(undefined, undefined)` — иначе, при `staleTime: Infinity`, устаревшие `user`/`expiresAt` продолжали бы висеть в кэше без полной перезагрузки страницы.

**Комбинированный `isLoading`, который не учитывает logout** (`AuthProvider.tsx:95-96`, разобрано подробно в разделе "Ревью"):

```tsx
// Combined loading state (initial load, during login, or refetching after login)
const combinedLoading = isInitialLoading || loginMutation.isPending || isRefetching
```

**Layout-фиксы**: `LoginForm.tsx:9` — контейнер сменил `<div className="mt-8 flex justify-center">` на `<Stack className="fixed inset-0 overflow-auto px-4 py-8" distribution="center" alignment="center">` (форма теперь центрируется по всему вьюпорту, а не только горизонтально от верха страницы); `routes/_auth/projects/index.tsx:85` — то же самое для спиннера Suspense-фолбэка на странице списка проектов.

**Тесты** (`AuthProvider.test.tsx`, `LoginForm.test.tsx`, `MainNavigation.test.tsx`) переписаны с моков `trpcClient.auth.X.query/mutate` на моки `trpcReact.auth.X.useQuery/useMutation` + обёртку `QueryClientProvider`. По пути часть поведенческих проверок ослаблена или убрана (например, тест логина больше не проверяет `result.current.isAuthenticated`/`user` после успешного `login()` — при статическом моке `useQuery` вызов `trpcUtils.setData` не отражается на возвращаемых данных хука, так что раньше эта проверка либо не работала бы, либо её вообще убрали как несовместимую с новым способом мокать). Это не тянет на самостоятельную находку по правилам ревью (общее качество тестового покрытия — не баг), но объясняет, почему регрессия из раздела "Ревью" ниже осталась незамеченной юнит-тестами.

## Что затронуло

`AuthProvider`/`useAuth` — часть публичного API пакета (экспортируются из `packages/aurora/src/client/index.ts`, см. #1072). Контракт `AuthContext` (`isAuthenticated`, `isLoading`, `error`, `user`, `expiresAt`, `login`, `logout`) не меняется по форме — меняется только то, что стоит за `isLoading` внутри. Проверка потребителей `useAuth()` на головном коммите (`git grep -n "useAuth()" 15f8590`) показала тот же список, что и в #1072:

- **`UserMenu.tsx:14`** — читает `isLoading`, чтобы показать `"Signing out…"` и задизейблить кнопку логаута на время выхода. Это единственный потребитель, для которого смена реализации `isLoading` реально меняет поведение (см. находку ниже) — остальные читают `isLoading` только для гейта первого рендера (`LoginForm.tsx`, `routes/index.tsx`) или не читают его вовсе (`useDomainId.ts`, `useScope.ts`, `routes/_auth.tsx`, `routes/_auth/aurora.tsx`).
- `App.tsx:130` подключает `AuthProvider` внутри уже существующего `<QueryClientProvider>` (добавлен в #1072) — новый `useQuery`/`useMutation` внутри `AuthProvider` не требует изменений в дереве провайдеров приложения, крash-риска на рантайме нет.
- В `apps/dashboard` прямых обращений к `useAuth`/`AuthProvider` нет — потребители получают auth-функциональность через смонтированный `<App>`, так что для них рефактор прозрачен на уровне API.
- `UserMenu.tsx` не имеет собственного тестового файла (`git grep -l "UserMenu" -- '*.test.tsx'` — пусто) — регрессия ниже не покрыта тестами ни до, ни после PR.

## Ревью

Пайплайн (5 параллельных агентов: CLAUDE.md-соответствие, беглый поиск багов, исторический контекст git blame/log, прежние PR-комментарии CodeRabbit/Copilot на этот PR, соответствие кодовым комментариям) плюс независимый confidence-scoring дал одну находку с уверенностью ≥80:

1. **Индикатор логаута в `UserMenu` перестал показываться** (confidence 90) — `AuthProvider.tsx:96`, `UserMenu.tsx:33-38`. Комбинированный `isLoading` теперь считается как `isInitialLoading || loginMutation.isPending || isRefetching` — `logoutMutation.isPending` в формулу не входит. `UserMenu` завязан именно на `isLoading`, чтобы во время выхода показать `label={isLoading ? "Signing out…" : "Log Out"}` и задизейблить кнопку (`disabled={isLoading}`). После этого PR кнопка "Log Out" во время реального сетевого запроса `terminateUserSession` остаётся активной и не меняет текст — пользователь может кликнуть повторно, пока запрос ещё летит. Комментарий над строкой (`// Combined loading state (initial load, during login, or refetching after login)`) сам не упоминает logout — это похоже на непреднамеренный пропуск при переносе состояния из ручных `useState` (в старой версии `logout()` явно делал `setIsLoading(true)` на всё время вызова, см. историю в #1072). Функциональность "Signing out…" была осознанно добавлена в этом же файле в PR #1072 буквально накануне ([`0021456`](https://github.com/cobaltcore-dev/aurora-dashboard/commit/0021456)) — то есть это тихая регрессия недавно добавленного, специально протестированного вручную UX-поведения. Юнит-тестами не покрыто (у `UserMenu.tsx` вообще нет тестового файла), так что регрессия не всплывёт ни в одном существующем прогоне.

Ещё одна находка подтверждена независимо (историческим контекстом — уже была поднята CodeRabbit на этом самом PR и не устранена к финальному коммиту `15f8590`, который является головным на момент анализа), но по вероятности реального срабатывания в проде тянет только на "также замечено":

- **Переполнение `setTimeout` для долгоживущих сессий** (confidence 55) — `AuthProvider.tsx:50-66`. `setTimeout(handleExpiry, timeUntilExpiry)` использует `timeUntilExpiry` без ограничения сверху; `setTimeout` в JS хранит задержку как 32-битное целое (лимит ≈ 24.8 дня, 2 147 483 647 мс) — если `expiresAt` дальше в будущем, таймер переполняется и синхронно стреляет `handleExpiry` (то есть мгновенный логаут) сразу после логина. CodeRabbit поднимал это на диапазоне коммитов `9297de8..15f8590` (том самом, что вошёл в финальный `head`) с готовым фиксом (рекурсивный `setTimeout` с капом на `MAX_TIMEOUT`) — фикс в код не попал. Понижаю с потенциальных 75+ до 55, потому что реальный TTL токенов Keystone в этом проекте типично измеряется часами, а не неделями — баг реален и подтверждён построчно, но шанс, что срок жизни сессии в проде когда-либо превысит ~25 дней, невысок.

Также проверено и отклонено как false positive/намеренное поведение: два более поздних комментария CodeRabbit на финальном коммите (`setData(undefined, undefined)` вместо `null` при логауте на `/`, и предложение не редиректить при неудачном `terminateUserSession`) — оба воспроизводят уже существовавшее до этого PR поведение (см. #1072: "локальный стейт чистится, даже если серверный вызов упал") и явно протестированы новым тестом `"should clear session immediately if already expired"` (`AuthProvider.test.tsx:479-551`), то есть это осознанный дизайн, а не побочный эффект рефакторинга (confidence 20).

**Что сделано хорошо:** заполнение кэша `getCurrentUserSession` результатом мутации логина вместо инвалидации+рефетча (`trpcUtils.auth.getCurrentUserSession.setData(undefined, tokenData)`) убирает лишний round-trip к серверу сразу после успешного входа — раньше в первой версии рефакторинга (до этого PR) такого оптимизма не было.

---
Проанализировано: 20.07.2026 · коммит `15f8590`
