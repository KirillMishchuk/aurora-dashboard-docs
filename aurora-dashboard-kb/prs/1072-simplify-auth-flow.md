# PR #1072: refactor(aurora): simplify auth flow and improve session handling

**Автор:** andypf · **Статус:** merged 15.07.2026
**Ветки:** `andypf/auth` → `main` · **Файлов:** 14 (+575/-727)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1072

## Что сделано

Полный рефакторинг клиентского auth-флоу в пакете `aurora`: логика авторизации переехала из роута `/` (файлового роута `routes/index.tsx`, где раньше жил и `beforeLoad`-гвард, и вся форма логина инлайном) в `AuthProvider` и новый выделенный компонент `LoginForm`. Цель — меньше состояния, меньше повторного рендера, использовать преимущества React 19 (отказ от `useCallback`, т.к. он больше не нужен для мемоизации).

Изменения группируются в четыре связанных куска:

1. **`AuthProvider` стал источником истины по сессии.** Раньше `login`/`logout` были просто сеттерами локального состояния, а сами tRPC-вызовы (`createUserSession`, `terminateUserSession`, `getCurrentUserSession`) были размазаны по компонентам (`routes/index.tsx`, `UserMenu.tsx`). Теперь все три вызова инкапсулированы внутри `AuthProvider`, а наружу торчит простой контракт: `login(credentials) → {success}`, `logout()`, `isLoading`, `error`.
2. **Восстановление сессии на маунте.** Новый `useEffect` в `AuthProvider` дергает `getCurrentUserSession` при монтировании и восстанавливает `user`/`expiresAt`, если сессия жива — это заменяет прежнюю проверку, которая делалась в роутерном `beforeLoad`.
3. **Таймер истечения сессии.** Отдельный `useEffect` считает `timeUntilExpiry` и по истечении сам чистит локальное состояние и редиректит на `/`, сохраняя текущий URL в `sessionStorage` (`redirect=...`), чтобы после повторного логина вернуть пользователя туда, где он был.
4. **Новая `LoginForm`.** Неконтролируемая форма на `FormData` (без `onChange`-стейта на каждое поле) — минус лишние ре-рендеры на каждый набранный символ.

## Как это реализовано

**`AuthProvider` — контракт и восстановление сессии** (`packages/aurora/src/client/store/AuthProvider.tsx:19-116`):

```ts
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [expiresAt, setExpiresAt] = useState<string | null>(null)

  useEffect(() => {
    trpcClient.auth.getCurrentUserSession
      .query()
      .then((session) => {
        if (session) {
          setUser(session.user)
          setExpiresAt(session.expires_at)
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Could not load session")
      })
      .finally(() => setIsLoading(false))
  }, [])
```

`getCurrentUserSession` — это `publicProcedure`, которая резолвится с `null`, если сессии нет (`packages/aurora/src/server/Authentication/routers/sessionRouter.ts:12-15`); она не реджектится в обычном случае "гость зашёл в первый раз". Реджект здесь — это именно отказ инфраструктуры (сеть, CSRF), не нормальное "не залогинен".

`AuthProvider` больше не принимает `router` пропом (раньше — `{ children, router }: { ...; router: RouterNavigation }`) — редиректы теперь идут через `window.location.href`, а не через `router.navigate()`/`router.invalidate()` (`AuthProvider.tsx:23-30`, функция `redirectToLogin`). Соответственно в `App.tsx:93` вызов упростился с `<AuthProvider router={router}>` до `<AuthProvider>`.

**`LandingPage`** (новое имя компонента роута `/`, `packages/aurora/src/client/routes/index.tsx:18-49`) стал тонким: гейтит рендер по `isLoading` (спиннер), затем либо рендерит `<LoginForm />`, либо (если уже авторизован) ничего не рендерит и уходит через `useEffect`-редирект:

```tsx
function LandingPage() {
  const { isLoading, isAuthenticated } = useAuth()
  const { redirect: searchRedirect } = Route.useSearch()
  const navigate = useNavigate()

  useEffect(() => {
    if (isAuthenticated && !isLoading) {
      const target = isSafeRedirect(searchRedirect) ? searchRedirect : "/projects"
      navigate({ to: target, replace: true })
    }
  }, [isAuthenticated, isLoading, navigate, searchRedirect])

  if (isLoading) {
    return (<Stack className="fixed inset-0" distribution="center" alignment="center">...<Spinner .../></Stack>)
  }
  if (!isAuthenticated) {
    return <LoginForm />
  }
  return null // Redirecting...
}
```

Раньше эта же логика (редирект уже авторизованных пользователей) жила в роутерном `beforeLoad` — она отрабатывала до рендера компонента, на уровне роутера, а не после маунта. Теперь `isLoading` изначально `true` (дефолт стейта в `AuthProvider`), поэтому "мелькания" формы логина для уже авторизованных пользователей не происходит — просто спиннер вместо мгновенного редиректа роутером.

**Новая `LoginForm`** (`packages/aurora/src/client/components/Auth/LoginForm.tsx:1-55`) — неконтролируемая форма на `FormData`:

```tsx
<form onSubmit={(e) => {
  e.preventDefault()
  const formData = new FormData(e.currentTarget)
  login({
    domain: String(formData.get("domain") ?? ""),
    user: String(formData.get("user") ?? ""),
    password: String(formData.get("password") ?? ""),
  })
}}>
```

**`UserMenu`** (`packages/aurora/src/client/components/navigation/UserMenu.tsx`) лишился собственного `handleLogout`-обёртки (была: вызов `trpcClient.auth.terminateUserSession.mutate()` напрямую + try/catch + свой `isLoading`-стейт) — теперь просто `onClick={logout}`, а `isLoading`/`isAuthenticated`/`user`/`expiresAt` идут напрямую из `useAuth()`.

## Что затронуло

`useAuth`/`AuthProvider` экспортируются из паблик-точки входа пакета (`packages/aurora/src/client/index.ts:19`), так что это часть публичного API `@cobaltcore-dev/aurora`, а не только внутренняя деталь. Проверка потребителей по всему монорепо на коммите `710e506` (`git grep -n "useAuth\|AuthProvider"`) показала:

- Внутри `aurora` на `useAuth()` завязаны: `App.tsx`, `LoginForm.tsx`, `UserMenu.tsx`, `hooks/useDomainId.ts`, `hooks/useScope.ts`, `routes/_auth.tsx`, `routes/_auth/aurora.tsx`, `routes/index.tsx` — все они используют только `isAuthenticated`/`user`/`isLoading`/`logout`, ни один не звал `login()` со старой сигнатурой `(user, expires_at)`, так что смена сигнатуры `login` на `(credentials) => {success}` не оставила сломанных вызовов.
- `routes/_auth.tsx` (гвард приватных роутов) читает только `context.auth?.isAuthenticated` — контракта не касается.
- В `apps/` (приложения-потребители пакета) прямых обращений к `useAuth`/`AuthProvider`/`login(` не найдено — они получают auth-функциональность целиком через смонтированный `<App>` из пакета, так что рефактор для них прозрачен на уровне API.
- Тесты (`AuthProvider.test.tsx`, `MainNavigation.test.tsx`, `useScope.test.ts`, новый `LoginForm.test.tsx`) обновлены консистентно с новой формой `AuthContext` (добавлены `isLoading`/`error` в моки).

Более серьёзный побочный эффект — этот PR тихо убрал точку кастомизации `slots.login` (см. раздел "Ревью" ниже): проверка `git grep -n "slots.*login" 710e506` по всему репозиторию на головном коммите PR ничего не находит — слот объявлен в типе `Slots` (`AuroraApp.tsx`), но нигде не читается. Это уже задокументировано в основном журнале базы знаний: слот был восстановлен в PR #1079 (см. [1079-slot-support-login.md](./1079-slot-support-login.md), если создан, либо запись в корневом README).

## Ревью

Пайплайн (5 параллельных агентов: CLAUDE.md-соответствие, беглый поиск багов, исторический контекст по git blame/log, прежние PR-комментарии на эти файлы, соответствие кодовым комментариям) плюс независимый confidence-scoring каждой находки дали одну находку с уверенностью ≥80:

1. **Точка кастомизации `slots.login` тихо удалена** (confidence 90) — `packages/aurora/src/client/routes/index.tsx`. Старый код рендерил кастомный компонент логина через `<Slot component={slots.login} .../>`, если консьюмер пакета его сконфигурировал (добавлено осознанно в PR #970 — специально для OIDC-окружений, где пароль-форма не нужна). Новый `LandingPage` вообще не читает `Route.useRouteContext().slots` и всегда рендерит захардкоженную `<LoginForm />`. Проп `Slots.login` остался в типе, но стал мёртвым. PR-описание не упоминает это удаление — похоже на не намеренный побочный эффект переписывания файла, а не осознанное решение. Уже исправлено в PR #1079.

Ещё две находки подтверждены независимо несколькими агентами и историей git (PR, которые исходно вносили это поведение), но набрали 75 — чуть ниже порога включения ≥80, привожу как "также замечено", раз это документация, а не гейт мержа:

- **Потеряна локализация ошибки логина** (confidence 75) — `AuthProvider.login()` теперь делает `setError(err.message)` с сырым текстом ошибки от tRPC, без проверки `isTRPCUnauthorized()` и без перевода через `useErrorTranslation`/`t`. Утилита `isTRPCUnauthorized` (`packages/aurora/src/client/utils/trpcErrors.ts:4`) осталась в кодовой базе, но не используется. Это то же самое поведение, которое было явно добавлено в PR #972 после ревью-комментария CodeRabbit о том, что немецкие пользователи видят сырой английский текст ошибки при неверных данных для входа.
- **Невалидные `autoComplete`-токены в `LoginForm`** (confidence 75) — новая форма использует `autoComplete="domain"`, `autoComplete="user"`, `autoComplete="password"`, ни один из которых не является валидным токеном спецификации WHATWG (валидные — `"username"`, `"current-password"`). Старая форма использовала `autoComplete="username"` / `autoComplete="current-password"`, добавленные осознанно в PR #1032 ради автозаполнения из менеджеров паролей — теперь это не работает.

Также проверено и отклонено как false positive/намеренное решение: смена редиректа на логауте с `router.navigate()`/`router.invalidate()` на `window.location.href` (confidence 30 — укладывается в заявленную цель PR "проще и надёжнее", полная перезагрузка при логауте — обычная практика для BFF-приложений); гипотеза о "мелькании" формы логина у авторизованных пользователей из-за удаления роутерного `beforeLoad`-гварда (confidence 20 — не подтвердилось: `isLoading` гейтит рендер спиннером раньше проверки `isAuthenticated`).

**Что сделано хорошо:** `SessionExpirationTimer` стал чистым компонентом отображения без побочного эффекта логаута — это устраняет race, на который раньше указывали в ревью PR #1046 (двойной вызов инвалидации сессии от независимых таймеров). Тесты переписаны консистентно с новым контрактом `AuthContext`, а не просто патчены точечно.

---
Проанализировано: 17.07.2026 · коммит `710e506`
