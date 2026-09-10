# Plan: Security Groups Go-Live fixes (#1138, #1165 + ID→path hardening)

**Date:** 2026-09-07 · **Status:** implemented 2026-09-07..08 (#1138 + #1165 + hardening ID→path; сверх плана добавлен фильтр Stateful — фильтруется на стороне BFF, т.к. поддержка `?stateful=` Neutron'ом не подтверждена; #1165 08.09 сначала откатывали как невоспроизводимый, затем вернули: баг виден только когда строка выше одной линии — в колонке Shared появляется вторая строка `Owner: …`; тесты по решению пользователя 2026-09-08 убраны — Testing Plan не реализован, изменения покрыты только существующими тестами репозитория; НЕ закоммичено — лежит локальными изменениями в рабочем дереве на ветке `kiryl-security-groups-go-live`, 19 файлов; typecheck/lint/224 test files 5549 tests зелёные; security-проверка без Critical/High, Medium по error.message оставлен осознанно; Риск 1 «сортировка в отфильтрованной ветке list» без автотестов — нужна ручная проверка на живом OpenStack)

# 📋 IMPLEMENTATION PLAN: Security Groups Go-Live fixes (#1138, #1165 + hardening ID→path)

## Overview

Три независимых блока в рамках эпика #1137: (1) починить фильтрацию/загрузку/поиск в списке Security Groups (#1138), (2) выровнять kebab-меню по вертикали в трёх таблицах Security Groups (#1165), (3) закрыть тот же класс уязвимости, что PR #1153, для `ruleId` и `policyId` (интерполяция непроверенного ID в путь запроса к Neutron). Все три — `fix`-изменения без нового публичного API; серверная часть делается первой и уезжает отдельным PR.

---

## Architecture Analysis

### Текущее состояние (проверено по коду на `8f993b8e`)

**Клиент, список SG**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/-components/SecurityGroupsList.tsx` — вся логика тулбара: локальный `sortSettings`/`filterSettings`/`searchTerm`, `useSearch({strict:false})` (роут без `validateSearch`), синхронизация URL→state через `useEffect`, запрос `network.securityGroup.list.useQuery` со спредом `buildFilterParams(...)`.
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/urlHelpers.ts` — `parseFiltersFromUrl` / `buildFilterParams(): Record<string, string>` / `applyFilterSelection` / `buildUrlSearchParams`. Файл — почти побайтовая копия `../floatingips/urlHelpers.ts` (diff = только имя типа и имя фильтра).
- `SecurityGroupListContainer.tsx` — таблица; early-return `Status progress` при `isLoading` и `Status error` при `isError` (то есть шапка колонок исчезает), пустое состояние — строка `colSpan` внутри `DataGrid` (пришло с #1256). Сейчас родитель передаёт `isLoading={false} isError={false} error={null}` — эти пропсы фактически мертвы.
- Общий тулбар `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/components/ListToolbar/`: `Filter.values: string[]` — **пары label/value не поддерживаются**; `FiltersInput` рендерит `<ComboBoxOption value={value} label={value}>`; `SelectedFilters` рендерит `Pill pillKey={filter.name} pillValue={filter.value}` и не знает про определения фильтров. Типы ListToolbar **не экспортируются** из `client/index.ts` → внутренний API.

**Эталонный паттерн в репозитории — Floating IPs** (`.../network/floatingips/-components/FloatingIpsList.tsx`): нет early-return по `isLoading`; `ContentHeader` и тулбар рендерятся всегда; `useQuery(..., { placeholderData: (prev) => prev })`; поиск с debounce 500 мс через `useRef`-таймер (`localSearchTerm` для инпута + `searchParams.search` как единственный источник для запроса); при ошибке с непустыми данными — неблокирующий `Message variant="error"`. Ровно тот же debounce-паттерн уже используется внутри самих Security Groups: `SecurityGroupRulesTable.tsx:186-206` и `SecurityGroupRBACPolicies.tsx:160-176`. Есть ещё `components/ListToolbar/index.tsx` со встроенным debounce 500 мс, но этот композитный компонент **никем не используется** — переводить список на него = отдельный рефакторинг, не делаем.
- «Загрузка не убивает шапку таблицы» уже реализовано в `Ceph/Objects/ObjectsTableView.tsx` (`isLoading`-проп, пустое состояние только при `!isLoading && rows.length === 0`) и в `compute/images/-components/ImageListView.tsx` (строка `colSpan` с `Status progress` + оверлей при `isFetching`).
- Мёртвая утилита `client/utils/buildFilterParams.ts` (+ тест) умеет `"true"→true`, но нигде не подключена и типизирована как `Record<string, string | boolean>` → компилятором ничего не ловит. Не трогаем (см. Follow-up).

**Сервер**
- `listSecurityGroupsInputSchema.shared` — `z.boolean()` (`server/Network/types/securityGroup.ts`). Для сравнения: у images аналогичный фильтр объявлен как `protected: z.string().optional()` — поэтому там баг не проявляется.
- `securityGroupRouter.list`: при `shared !== undefined` идёт **одиночный** запрос к Neutron с `sort_key`/`sort_dir` (сортирует Neutron), а `project_id` из этой ветки выброшен деструктуризацией; при `shared === undefined` — два запроса + дедуп + сортировка в памяти. Ветка с `shared` из UI **никогда не выполнялась** (запрос всегда падал в BAD_REQUEST) — после фикса она станет живой впервые.
- Конвенция валидации ID: `validateAndEncodeResourceId()` вызывается **на уровне роутера, инлайном, внутри `withErrorHandling`** — `securityGroupRouter` (3 места), `floatingIpRouter` (3 места); `wrapError` в `server/helpers/errorHandling.ts` мапит `SignalOpenstackError` → `TRPCError{code:"BAD_REQUEST"}`. Вариант с try/catch и своим сообщением (`flavorRouter`) и вариант «вернуть null» (`projectRouter`) — исключения под конкретную семантику. `openstackErrorMiddleware` тут не участвует: он обрабатывает только `SignalOpenstackApiError` (ответы OpenStack), а не ошибки валидации.
- `securityGroupRuleRouter.ts` (нет файла тестов вообще) и `rbacPolicyRouter.ts` (`rbacPolicyRouter.test.ts` есть, но URL-ассертов нет) — оба интерполируют ID без валидации.

**Juno 9.4.0 (проверено на теге `@cloudoperators/juno-ui-components@9.4.0`)**
- `DataGrid`: `cellVerticalAlignment = "center"` по умолчанию → `DataGridCell` получает `jn:justify-center jn:flex jn:flex-col`. Значит `justify-end` в `className` ячейки — это вертикальная ось (меню уезжает вниз), а `items-end` — горизонтальная (нужен). `CellVerticalAlignmentType = "center" | "top"`; у `DataGridCell` есть проп `verticalAlignment` для переопределения — он нам не нужен, правильный фикс — убрать `justify-end`.
- Варианты kebab-ячейки в репозитории: `items-end justify-end pr-0` (3 файла SG — сломано), `items-end pr-0` (`FloatingIpTableRow.tsx:43` — корректно), `justify-end pr-0` + внутренний `<div className="flex h-full items-center justify-end">` (Ceph `CorsRulesTable.tsx:165`, `LifecycleRulesTable.tsx:207` — визуально корректно, т.к. обёртка занимает всю высоту, но стилистически лишнее).

### Предлагаемые изменения (высокоуровнево)

1. **Сервер (безопасность):** `validateAndEncodeResourceId(ruleId, "Security group rule")` и `validateAndEncodeResourceId(policyId, "RBAC policy")` инлайном по конвенции `securityGroupRouter`/`floatingIpRouter`.
2. **Клиент, типизированные параметры фильтра:** новый локальный модуль `filterConfig.ts` в папке securitygroups, где имена и **типы** параметров фильтра выводятся из серверной Zod-схемы (`Pick<ListSecurityGroupsInput, "shared">`), а билдер возвращает типизированный объект — тогда рассинхронизация ловится `tsc`, потому что спред типизированного объекта (в отличие от `Record<string,string>`) проверяется против входного типа процедуры.
3. **Клиент, лейблы:** аддитивное расширение общего типа `Filter` полем `valueLabels?: Record<string,string>` + опциональный проп `filters` у `SelectedFilters`. Обратная совместимость полная: списки, которые проп не передают (Images, Floating IPs), не меняются вообще.
4. **Клиент, загрузка/ошибка:** убрать оба early-return из `SecurityGroupsList`, прокинуть реальные `isLoading`/`isError` в контейнер, в контейнере рисовать `Status` строкой `colSpan` **внутри** `DataGrid` (шапка колонок остаётся), пустое состояние — только при `!isLoading`; добавить `placeholderData: (prev) => prev`, чтобы при смене фильтра/поиска не мигало пустое состояние.
5. **Клиент, поиск:** debounce 500 мс по паттерну `FloatingIpsList`/`SecurityGroupRulesTable`.
6. **CSS:** `items-end justify-end pr-0` → `items-end pr-0` в трёх файлах SG.

Почему так, а не иначе: каждое решение — уже существующий в репозитории паттерн (Floating IPs / Ceph ObjectsTableView / `securityGroupRouter`), новых абстракций не вводим; единственное расширение общего кода — два опциональных поля в неэкспортируемых типах тулбара.

---

## Potential Problems & Mitigations

| Риск | Severity | Митигация |
| --- | --- | --- |
| 🔴 Ветка `shared !== undefined` в `securityGroupRouter.list` после фикса выполняется впервые: там сортировка отдаётся Neutron (`sort_key`/`sort_dir`), а не делается в памяти. `sort_key=project_id` может быть не поддержан Neutron → 400 при комбинации «фильтр Shared + сортировка Project id» | High | Обязательная ручная проверка всех 4 комбинаций (shared=Yes/No × sortBy=name/project_id). Если Neutron отвечает 400 — не передавать `sort_key`/`sort_dir` в `fetchSecurityGroupsWithParams` в этой ветке и сортировать через уже существующий `sortSecurityGroups(...)` (`server/Network/helpers/securityGroupHelpers.ts`), как в merged-ветке. Это правка ~4 строк, держать её в запасе в том же PR |
| ⚠️ Цикл/потеря символов: debounce пишет URL (`replace: true`), а `useEffect` по `searchParams.search` пишет URL обратно в `localSearchTerm` | Medium | Синхронизировать локальный state из URL только когда debounce-таймер не «в полёте» (guard по `debounceTimer.current`), либо сравнивать с последним запушенным значением через `useRef`. Плюс тест «быстрый ввод → один navigate с финальным значением» |
| ⚠️ `parseFiltersFromUrl` пропускает любое значение из URL (`?shared=banana`) → бессмысленный pill и мусор в запросе | Medium | Валидировать значение против списка известных опций и в `parseFiltersFromUrl`, и в билдере параметров; неизвестное — игнорировать (без pill, без параметра). Юнит-тест |
| 🔴 Убирая early-return по ошибке, легко «уронить» текущее поведение FORBIDDEN-сообщения | Medium | Сохранить существующий текст `You do not have permission to view security groups` для `error.data.code === "FORBIDDEN"`, остальное — `error.message` с fallback `Failed to load security groups`; проверять по существующим тестам контейнера |
| ⚠️ Расширение общего `Filter`/`SelectedFilters` затрагивает Images/Floating IPs/Rules-таблицу | Low | Оба поля опциональны и label-резолв включается только при переданном `filters`; ни один существующий вызов не меняет поведение. Запустить `pnpm --filter @cobaltcore-dev/aurora test src/client/components/ListToolbar` |
| ⚠️ `placeholderData: (prev) => prev` показывает устаревшие строки во время смены фильтра — при неуспешном refetch пользователь видит старые данные | Low | Как в `FloatingIpsList`: неблокирующий `Message variant="error"` при `isError && securityGroups.length > 0` |
| 🔒 Фикс валидации ID меняет код ответа для «странных» ID с 500/произвольного на 400 | Low | `wrapError` уже мапит в `BAD_REQUEST`; ни один клиентский путь легитимных UUID не затрагивается. Тесты на happy-path URL обязательны, чтобы не сломать нормальное удаление |
| ⚠️ Husky `pre-commit` заканчивается `git add -u` и застейджит все грязные tracked-файлы | Low | Коммитить по одному логическому блоку, держать рабочее дерево чистым между коммитами |
| ⚠️ Дрейф каталогов Lingui (CI-джоба `check-i18n` падает) | Medium | После UI-правок обязательно `pnpm check-i18n` в корне и коммит `packages/aurora/src/locales/{en,de}/messages.{po,ts}` |
| ⚠️ Дубликат `urlHelpers.ts` между securitygroups и floatingips: правки в одном не доезжают во второй | Low | Осознанно оставляем (скоуп issue), фиксируем как follow-up |

---

## Prerequisites

- [ ] Ветка от актуального `origin/main` (сейчас `8f993b8e`), рабочее дерево чистое.
- [ ] Доступ к живому OpenStack (Keystone `IDENTITY_ENDPOINT` в `apps/dashboard/.env`) с проектом, где есть **и** собственные, **и** shared security groups — иначе ветку `shared=true/false` не проверить.
- [ ] Решение по стратегии PR (см. «Delivery» ниже) — по умолчанию два PR.
- [ ] Уточнить у мейнтейнера, ожидается ли фикс #1165 только для Security Groups (рекомендация) или унификация kebab-ячеек по всему приложению.

---

## Implementation Steps

Порядок: сервер → клиент, чтобы каждая часть была самостоятельным ревьюабельным коммитом.

---

### Step 1: Валидировать `ruleId` перед интерполяцией в путь (security)

**Файлы:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/routers/securityGroupRuleRouter.ts` — добавить валидацию в `delete`.

**Что сделать:**
1. Добавить импорт: `import { validateAndEncodeResourceId } from "@cobaltcore-dev/signal-openstack"` (ровно как в `securityGroupRouter.ts:21`).
2. В процедуре `delete`, внутри `withErrorHandling`, между `getNetworkService(ctx)` и вызовом `network.del`, вставить:
   `const encodedRuleId = validateAndEncodeResourceId(ruleId, "Security group rule")`
3. Заменить путь на `network.del(`${SECURITY_GROUP_RULES_BASE_URL}/${encodedRuleId}`)`.
4. В `SecurityGroupRuleErrorHandlers.delete(response, ruleId)` оставить **сырой** `ruleId` (это только текст ошибки, как в `securityGroupRouter`, где в хендлеры тоже передаётся неэнкоженный ID).
5. Ничего не менять в `create`: там `security_group_id` уходит в тело запроса, а не в путь.

**Ожидаемый результат:** `ruleId` вида `../../v2.0/ports/<id>` или `x?admin=1` даёт `TRPCError` `BAD_REQUEST` до сетевого вызова; легитимные UUID работают как раньше.

**Верификация:** `pnpm --filter @cobaltcore-dev/aurora typecheck` + тесты из Step 3.

---

### Step 2: Валидировать `policyId` в `rbacPolicyRouter` (security)

**Файлы:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/routers/rbacPolicyRouter.ts` — процедуры `update` и `delete`.

**Что сделать:**
1. Добавить тот же импорт `validateAndEncodeResourceId`.
2. В `update`: `const encodedPolicyId = validateAndEncodeResourceId(policyId, "RBAC policy")` перед `network.put(...)`, путь → `` `${RBAC_POLICIES_BASE_URL}/${encodedPolicyId}` ``.
3. В `delete`: то же перед `network.del(...)`.
4. `RBACPolicyErrorHandlers.update/delete(response, policyId)` оставить с сырым `policyId`.
5. `list` не трогать: `securityGroupId` там уходит через `new URLSearchParams` в query, а не в путь (инъекции параметров нет — `URLSearchParams` энкодит).
6. Схемы в `server/Network/types/rbacPolicy.ts` и `securityGroup.ts` **не менять** — конвенция домена Network держит валидацию пути на уровне роутера (не в Zod), см. `securityGroupRouter`/`floatingIpRouter`.

**Ожидаемый результат:** оба мутирующих RBAC-эндпоинта не могут обратиться к произвольному пути Neutron.

---

### Step 3: Тесты на валидацию ID (server)

**Файлы:**
- **NEW** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/routers/securityGroupRuleRouter.test.ts`
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/server/Network/routers/rbacPolicyRouter.test.ts` — добавить describe-блок.

**Что сделать:**
1. Новый файл собрать по образцу `securityGroupRouter.test.ts` (локальный `createMockContext` с `vi.fn()`-based `validateSession`/`rescopeSession`/`openstack.service("network")`) + вызов через `createCallerFactory(auroraRouter({ securityGroupRule: securityGroupRuleRouter }))`; моки `del`/`post` вынести в наружу как в `floatingIpRouter.test.ts` (`__networkDelMock`), чтобы ассертить URL.
2. Кейсы для `securityGroupRule.delete`:
   - happy path: `ruleId: "rule-123"` → `del` вызван ровно с `"v2.0/security-group-rules/rule-123"`.
   - `ruleId: "../../v2.0/ports/port-1"` → `TRPCError` с `code === "BAD_REQUEST"`, **и** `__networkDelMock` не вызван (`expect(...).not.toHaveBeenCalled()`).
   - `ruleId: "x?admin=1"` → `BAD_REQUEST`, `del` не вызван.
   - `ruleId: "."` и `ruleId: ""` → `BAD_REQUEST` (пустая строка проходит Zod `z.string()`, но отбивается хелпером — важный кейс).
   - `ruleId: "rule 1"` → `del` вызван с `"v2.0/security-group-rules/rule%201"` (энкодинг не ломает легитимные значения).
   - happy path `create` (регресс-гард: тело запроса и URL без ID).
3. Кейсы для `rbacPolicy.update` и `rbacPolicy.delete` — те же пять пунктов, плюс happy-path ассерты URL `"v2.0/rbac-policies/rbac-policy-1"` на `put`/`del` (в текущем `rbacPolicyRouter.test.ts` URL-ассертов нет, их надо добавить, экспортировав моки из `createMockContext` по образцу `floatingIpRouter.test.ts:234-244`).

**Верификация:**
```
pnpm --filter @cobaltcore-dev/aurora test src/server/Network/routers/securityGroupRuleRouter.test.ts src/server/Network/routers/rbacPolicyRouter.test.ts
```

**Коммит:** `fix(aurora): validate resource IDs before path interpolation in network routers`
(альтернатива по конвенции #1153 — `fix(core): ...`; `network` тоже разрешён `commitlint.config.mjs`. Рекомендую `aurora` — так оформлены все свежие коммиты в `git log`.)

---

### Step 4: Типизированная конфигурация фильтров Security Groups (#1138a)

**Файлы:**
- **NEW** `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/filterConfig.ts`
- **NEW** `.../securitygroups/filterConfig.test.ts`

**Что сделать:**
1. Единственный источник истины по именам и типам — серверная схема:
   ```ts
   import type { ListSecurityGroupsInput } from "@/server/Network/types/securityGroup"

   /** Filter params this list may send to network.securityGroup.list. Names AND types come from the tRPC input schema. */
   export type SecurityGroupFilterParams = Partial<Pick<ListSecurityGroupsInput, "shared">>
   export type SecurityGroupFilterName = keyof SecurityGroupFilterParams
   ```
2. Описать значения фильтра `shared` так, чтобы тип параметра сверялся компилятором:
   ```ts
   const SHARED_VALUES = ["true", "false"] as const
   type SharedValue = (typeof SHARED_VALUES)[number]
   const SHARED_PARAM: Record<SharedValue, NonNullable<SecurityGroupFilterParams["shared"]>> = {
     true: true,
     false: false,
   }
   ```
   Если серверная схема когда-нибудь сменит `shared` на строковый enum — `tsc` упадёт здесь.
3. Экспортировать фабрику определений (лейблы через Lingui считаются на рендере, поэтому именно функция от `t`):
   ```ts
   export const buildSecurityGroupFilters = (labels: { shared: string; yes: string; no: string }): Filter[] => [
     {
       displayName: labels.shared,
       filterName: "shared" satisfies SecurityGroupFilterName,
       values: [...SHARED_VALUES],
       valueLabels: { true: labels.yes, false: labels.no },
       supportsMultiValue: false,
     },
   ]
   ```
   (принимаем готовые строки, а не сам `t`, чтобы модуль остался чистым и тестируемым без `I18nProvider`).
4. Экспортировать типизированный билдер, заменяющий `buildFilterParams` для этого списка:
   ```ts
   export const buildSecurityGroupFilterParams = (selectedFilters: SelectedFilter[]): SecurityGroupFilterParams
   ```
   Логика: отфильтровать `inactive`, взять последнее значение для `shared` (фильтр single-value), проверить, что значение входит в `SHARED_VALUES`; неизвестное значение — **пропустить** (вернуть `{}`), не бросать.
5. Экспортировать хелпер валидации значения для URL-парсинга: `export const isKnownSecurityGroupFilter = (name: string, value: string): boolean`.
6. Тесты (`filterConfig.test.ts`): `{}` при пустом списке; `{ shared: true }` для `value: "true"`; `{ shared: false }` для `"false"` (важно: не `Boolean("false") === true`); `{}` для `?shared=banana`; `{}` когда все выбранные фильтры `inactive`; типовой smoke — `expectTypeOf`-стиль не обязателен, достаточно `expect(typeof result.shared).toBe("boolean")`.

**Ожидаемый результат:** билдер возвращает `{ shared?: boolean }`; спред его результата во вход `useQuery` проверяется компилятором.

**Верификация:** временно вернуть в билдере `{ shared: "true" as unknown as boolean }` — `pnpm --filter @cobaltcore-dev/aurora typecheck` должен упасть на `SecurityGroupsList.tsx`; вернуть обратно.

---

### Step 5: Поддержать пары label/value в общем ListToolbar (#1138b)

**Файлы:**
- `/Users/kirylmishchuk/projects/SAP/aurora-dashboard/packages/aurora/src/client/components/ListToolbar/types.ts`
- `.../ListToolbar/FiltersInput.tsx`
- `.../ListToolbar/SelectedFilters.tsx`
- `.../ListToolbar/index.tsx` (передать новый проп, чтобы композитный компонент не отстал)
- тесты: `FiltersInput.test.tsx`, `SelectedFilters.test.tsx`

**Что сделать:**
1. В `types.ts` добавить в тип `Filter` **опциональное** поле с TSDoc в стиле файла:
   ```ts
   /**
    * Optional human-readable labels for raw filter values, keyed by value.
    * Use when the wire/URL value differs from what the table shows (e.g. `shared: "true"` → "Yes").
    * Values without an entry fall back to the raw value.
    */
   valueLabels?: Record<string, string>
   ```
2. В `FiltersInput.tsx`: вместо `filterValues` вычислять `const selectedFilterDef = filters.find((f) => f.filterName === selectedFilterName)`, из него брать `values` и `valueLabels`; в `<ComboBoxOption value={value} label={selectedFilterDef?.valueLabels?.[value] ?? value} key={value} data-testid={value} />`. `value` (то, что уходит в `onChange`) не меняется — URL и запрос остаются на «true»/«false».
3. В `SelectedFilters.tsx`: добавить опциональный проп `filters?: Filter[]` (с TSDoc: «filter definitions used to resolve human-readable labels for pills; when omitted, raw name/value are shown»), и внутри:
   ```ts
   const def = filters?.find((f) => f.filterName === filter.name)
   <Pill pillKey={def?.displayName ?? filter.name} pillValue={def?.valueLabels?.[filter.value] ?? filter.value} ... />
   ```
   ⚠️ `key` остаётся `` `${filter.name}:${filter.value}` `` (на сырых значениях), `onDelete(filter)` тоже отдаёт исходный объект — иначе поломается удаление pill.
4. В `ListToolbar/index.tsx` прокинуть `filters={filterSettings.filters}` в `<SelectedFilters …>`.
5. Не менять вызовы `SelectedFilters` в Images (`compute/images/-components/List.tsx`), Floating IPs (`FloatingIpsList.tsx`) и `SecurityGroupRulesTable.tsx` — они проп не передают, поведение не меняется (осознанное решение: скоуп issue = Security Groups).
6. Тесты: в `FiltersInput.test.tsx` — кейс «рендерит `valueLabels` как label опции, но отдаёт сырое value в `onChange`»; в `SelectedFilters.test.tsx` — «без `filters` рендерит сырые name/value (регресс-гард)» и «с `filters` рендерит displayName/label, а `onDelete` получает сырой фильтр».

**Ожидаемый результат:** общий тулбар умеет человекочитаемые лейблы значений, ничего не ломая у существующих потребителей.

---

### Step 6: Подключить типизированные параметры и лейблы в `SecurityGroupsList` (#1138a+b)

**Файлы:**
- `.../securitygroups/-components/SecurityGroupsList.tsx`
- `.../securitygroups/urlHelpers.ts`

**Что сделать:**
1. В `urlHelpers.ts` в `parseFiltersFromUrl` добавить отсечение неизвестных значений: пушить фильтр только если `isKnownSecurityGroupFilter("shared", searchParams.shared)`. Импорт из `./filterConfig`.
2. Из `SecurityGroupsList.tsx` убрать импорт `buildFilterParams` из `../urlHelpers`; импортировать `buildSecurityGroupFilterParams` и `buildSecurityGroupFilters` из `../filterConfig`.
3. Инициализацию `filterSettings.filters` заменить на
   `buildSecurityGroupFilters({ shared: t`Shared`, yes: t`Yes`, no: t`No` })`
   — msgid `Shared`, `Yes`, `No` **уже есть** в обоих каталогах (`Yes`→`Ja`, `No`→`Nein` в `de/messages.po`), новых строк не появляется.
4. Во входе `useQuery` заменить `...buildFilterParams(urlFilters, filterSettings.filters)` на `...buildSecurityGroupFilterParams(urlFilters)`.
5. В блок `<SelectedFilters …>` добавить `filters={filterSettings.filters}`.
6. `buildUrlSearchParams` в `handleFilterChange` не менять — в URL по-прежнему уходит `?shared=true|false`.

**Ожидаемый результат:** выбор фильтра «Shared: Yes» отправляет `{ shared: true }`, список грузится; в дропдауне и в pill написано Shared / Yes-No, ровно как в колонке таблицы (`SecurityGroupTableRow.BooleanValue`); URL остаётся `?shared=true`.

**Верификация:** `pnpm --filter @cobaltcore-dev/aurora typecheck`, затем ручная проверка в dev с открытой Network-панелью браузера.

---

### Step 7: Сохранить header и тулбар во время загрузки и ошибки (#1138c)

**Файлы:**
- `.../securitygroups/-components/SecurityGroupsList.tsx`
- `.../securitygroups/-components/SecurityGroupListContainer.tsx`

**Что сделать (родитель):**
1. Удалить блок `if (isLoading) return <Status status="progress" title={t`Loading Security Groups...`} />` (строки 246-248). Строка `Loading Security Groups...` больше нигде не используется → уйдёт из каталогов при `extract --clean` (учтено в Step 10).
2. Удалить блок `if (isError && !securityGroups.length) return <Stack …>…</Stack>` (строки 250-256) — вместе с ним уходит последний в этом файле «сырой» текстовый layout ошибки (репозиторий с #1222/#1256 использует `Status`).
3. Переписать вычисление сообщения об ошибке:
   ```ts
   const listError = isError
     ? error?.data?.code === "FORBIDDEN"
       ? t`You do not have permission to view security groups`
       : (error.message || t`Failed to load security groups`)
     : null
   ```
4. Добавить в `useQuery` опцию `placeholderData: (prev) => prev` (рядом с существующей `refetchOnWindowFocus: false`) — как в `FloatingIpsList`. Взять из хука ещё и `isFetching`.
5. Обернуть содержимое после `ContentHeader` в `<div className="relative">…</div>` и сразу под ним, до тулбара, добавить неблокирующий баннер:
   ```tsx
   {isError && securityGroups.length > 0 && (
     <Message variant="error" className="mb-4">{listError}</Message>
   )}
   ```
   (импорт `Message` из `@cloudoperators/juno-ui-components`; паттерн 1:1 из `FloatingIpsList.tsx`).
6. Передать в `SecurityGroupListContainer` реальные значения вместо хардкода:
   `isLoading={isLoading}`, `isError={isError && securityGroups.length === 0}`, `error={listError ? { message: listError } : null}`.

**Что сделать (контейнер):**
7. Удалить early-return'ы `if (isLoading)` (строки 117-120) и `if (isError)` (122-125).
8. Внутри `<DataGrid>`, сразу после строки заголовков, заменить нынешний тернарник на трёхветочный рендер (порядок важен):
   - `isLoading` → `<DataGridRow><DataGridCell colSpan={columnCount}><Status status="progress" title={t`Loading...`} /></DataGridCell></DataGridRow>`
   - `isError` → тот же `colSpan`-контейнер с `<Status status="error" title={error?.message ?? t`Failed to load security groups`} />`
   - иначе `securityGroups.length > 0` → строки; `else` → существующий `status="empty"` блок (не менять текст).
   Вынести `const columnCount = hasAnyBulkAction ? 6 : 5` в переменную и использовать её и в `columns`, и во всех `colSpan` (сейчас число дублируется).
   Ключевой инвариант: пустое состояние рендерится **только** при `!isLoading && !isError`.

**Ожидаемый результат:** при первой загрузке и при ошибке видны `ContentHeader`, кнопка Create, сортировка, фильтры, поиск и шапка колонок; крутилка/ошибка — только в области строк. При смене фильтра/поиска старые строки остаются на месте (placeholderData), «No security groups found» во время загрузки не мигает. При провалившемся refetch с уже загруженными данными — красный баннер сверху, а фильтр можно откатить (сейчас при BAD_REQUEST тулбар исчезал, и пользователь оказывался в тупике).

**Верификация:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/network/securitygroups`

---

### Step 8: Debounce поиска (#1138d)

**Файлы:**
- `.../securitygroups/-components/SecurityGroupsList.tsx`

**Что сделать:**
1. Ввести локальную константу файла `const SEARCH_DEBOUNCE_MS = 500` (то же значение, что в `SecurityGroupRulesTable`, `SecurityGroupRBACPolicies`, `FloatingIpsList`, `ListToolbar`).
2. Добавить `const debounceTimer = useRef<number | undefined>(undefined)` и `useEffect(() => () => clearTimeout(debounceTimer.current), [])` (паттерн `FloatingIpsList.tsx:41-43`).
3. Переименовать локальный state поиска в `localSearchTerm` (инпут), а входом запроса оставить `urlSearchTerm` из URL — так уже сделано, дополнительного состояния не нужно.
4. `onInput`:
   ```tsx
   const v = e.currentTarget.value
   setLocalSearchTerm(v)
   clearTimeout(debounceTimer.current)
   debounceTimer.current = window.setTimeout(() => handleSearchChange(v), SEARCH_DEBOUNCE_MS)
   ```
5. `onSearch` (Enter/кнопка) и `onClear`: сначала `clearTimeout(debounceTimer.current)`, затем немедленный `handleSearchChange(...)` — чтобы отложенный таймер не перезаписал явное действие.
6. `handleSearchChange` оставить с `replace: true` (сохранение истории браузера при каждом символе не нужно; это же значение уже стоит в файле).
7. ⚠️ Защитить `useEffect`-синхронизацию URL→state от гонки: не вызывать `setLocalSearchTerm(searchParams.search || "")`, если `debounceTimer.current !== undefined` (то есть пока ввод «в полёте»); таймер обнулять внутри колбэка (`debounceTimer.current = undefined`) и в `onSearch`/`onClear`. Это устраняет случай «URL применился, пользователь продолжил печатать, эффект откатил инпут».
8. Область применения — **только** список Security Groups: в `SecurityGroupRulesTable`, `SecurityGroupRBACPolicies` и `FloatingIpsList` debounce уже есть; Images/Flavors живут на другой (Suspense/promise) механике и в скоуп #1138 не входят.

**Ожидаемый результат:** ввод в поиск сам запускает запрос через 500 мс после последнего символа; Enter работает мгновенно; крест очищает мгновенно; за «быстрый ввод 5 символов» уходит один запрос.

**Верификация:** ручная — в Network-панели один запрос `securityGroup.list` на серию символов; тесты из Step 11.

---

### Step 9: Выровнять kebab-меню по строке (#1165)

**Файлы:**
- `.../securitygroups/-components/SecurityGroupTableRow.tsx:85`
- `.../securitygroups/$securityGroupId/-components/-details/RBACPolicyRow.tsx:24`
- `.../securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.tsx:248`

**Что сделать:**
1. В каждом из трёх мест заменить `className="items-end justify-end pr-0"` на `className="items-end pr-0"` — ровно как в `FloatingIpTableRow.tsx:43`.
2. Ничего больше не менять: `onClick={(e) => e.stopPropagation()}` остаётся, `verticalAlignment` у ячейки не задаём (наследуем `center` от `DataGrid`), `minContentColumns` не трогаем.
3. Скоуп: Ceph `CorsRulesTable.tsx:165` / `LifecycleRulesTable.tsx:207` **не трогаем** — там `justify-end` нейтрализован обёрткой `flex h-full items-center`, визуального дефекта нет; унификация трёх стилей оформления kebab-ячейки по всему приложению — отдельный `refactor`-PR (см. Follow-up), чтобы не мешать go-live-фикс с косметикой в чужом домене.

**Ожидаемый результат:** kebab-меню по центру строки по вертикали и у правого края по горизонтали — в списке SG (строки двухстрочные из-за «Owner: …»), в таблице правил и в таблице RBAC-политик.

**Верификация:** визуально + тесты из Step 11 (ассерты на className ячейки).

---

### Step 10: i18n-каталоги

**Файлы:** `packages/aurora/src/locales/en/messages.{po,ts}`, `packages/aurora/src/locales/de/messages.{po,ts}`

**Что сделать:**
1. Все новые/изменённые тексты уже идут через Lingui-макросы (`t` из `useLingui()` в компонентах, обычные строки в `filterConfig.ts` приходят снаружи) — новых механизмов не вводим.
2. Новых msgid **не появляется**: `Shared`, `Yes`, `No`, `Loading...`, `Failed to load security groups`, `No security groups found` уже в каталогах.
3. Удаляется один msgid — `Loading Security Groups...` (единственное употребление уходит в Step 7). После правок запустить в корне:
   ```
   pnpm check-i18n
   ```
   (это `lingui extract --clean && lingui compile --typescript` для aurora — та же команда, что в CI-джобе `check-i18n`).
4. Закоммитить изменённые `messages.po` и `messages.ts` для **обоих** локалей (en, de). Немецкий перевод вручную добавлять не нужно — новых строк нет; в `de` только удалится запись `Sicherheitsgruppen werden geladen…`-типа.

**Верификация:** `pnpm check-i18n` дважды подряд — второй прогон не должен давать диффа (`git status` чистый).

---

### Step 11: Клиентские тесты

**Файлы:**
- `.../securitygroups/-components/SecurityGroupsList.test.tsx`
- `.../securitygroups/-components/SecurityGroupListContainer.test.tsx`
- `.../securitygroups/-components/SecurityGroupTableRow.test.tsx`
- `.../securitygroups/$securityGroupId/-components/-details/SecurityGroupRBACPolicies.test.tsx` (покрывает `RBACPolicyRow`, своего файла у него нет)
- `.../securitygroups/$securityGroupId/-components/-details/SecurityGroupRulesTable.test.tsx`
- **NEW** `.../securitygroups/filterConfig.test.ts` (описан в Step 4)
- `.../components/ListToolbar/FiltersInput.test.tsx`, `SelectedFilters.test.tsx` (описаны в Step 5)

**`SecurityGroupsList.test.tsx` — сначала подготовка мока (сейчас `useQuery` возвращает жёсткий объект):**
1. Вынести в `vi.hoisted` два спая: `mockUseQuery` (чтобы менять возвращаемое значение по кейсам и ассертить аргументы) и `mockNavigate` (сейчас `useNavigate: () => vi.fn()` — новый мок на каждый вызов, ассертить нечего). Мок роутера: `useNavigate: () => mockNavigate`.
2. Кейсы:
   - **фильтр → boolean:** выбрать в `select-filterValue` значение `shared`, затем в `combobox-filterValue` опцию с лейблом `Yes` → `mockNavigate` вызван с `search`-функцией, дающей `{ shared: "true" }`; при рендере с `useSearch: () => ({ shared: "true" })` — `mockUseQuery` получил вход, где `shared === true` (именно `toBe(true)`, не `"true"`).
   - **лейблы фильтра:** в дропдаунe значений есть `Yes`/`No` и нет `true`/`false`; pill при `?shared=true` показывает `Shared` / `Yes`.
   - **неизвестное значение в URL:** `useSearch: () => ({ shared: "banana" })` → pill не отрисован, вход `useQuery` без ключа `shared`.
   - **загрузка не сносит страницу:** `isLoading: true, data: undefined` → в DOM есть заголовок `Security Groups`, `searchbar`, `select-filterValue` и кнопка `Create Security Group` (и `progressbar`, приходящий из контейнера — контейнер в этом файле замокан, так что достаточно проверить, что `isLoading` прокинут в мок-контейнер пропсом).
   - **ошибка не сносит тулбар:** `isError: true, error: { message: "boom", data: { code: "BAD_REQUEST" } }, data: []` → `searchbar` и заголовок в DOM, контейнер получил `isError=true` и `error.message === "boom"`; для `code: "FORBIDDEN"` — `error.message` равен `You do not have permission to view security groups`.
   - **debounce:** `await user.type(searchbar, "web")`, затем `await new Promise((r) => setTimeout(r, 600))` (паттерн `SecurityGroupRulesTable.test.tsx:313`) → `mockNavigate` вызван **один** раз, финальное значение `search: "web"`.
   - **Enter — мгновенно:** `user.type(searchbar, "web{Enter}")` → `mockNavigate` вызван сразу, без ожидания 600 мс.
   - **очистка — мгновенно и без отложенного перезаписывания:** клик по clear → `search: undefined`, и после 600 мс дополнительных вызовов `mockNavigate` нет.
3. Для мок-контейнера в этом файле расширить фейковый компонент, чтобы он рендерил переданные `isLoading`/`isError`/`error.message` в `data-testid`-атрибуты — иначе прокидывание пропсов не проверить.

**`SecurityGroupListContainer.test.tsx`:**
4. Обновить существующий кейс `renders loading spinner`: помимо `progressbar` и текста `Loading...` проверить, что заголовки колонок (`Name`, `Description`, `Shared`, `Stateful`) **тоже** в DOM.
5. Аналогично в `renders error message` / `renders default error message` — заголовки колонок на месте.
6. Новый кейс: `isLoading={true}` и `securityGroups={[]}` → текста `No security groups found` в DOM **нет** (гард от мигания пустым состоянием).
7. Существующий `renders empty state` не меняется.

**Kebab-выравнивание (#1165):**
8. `SecurityGroupTableRow.test.tsx`: новый кейс — найти ячейку с меню (например, `container.querySelectorAll('[role="gridcell"]')` последняя, или по `closest('[role="gridcell"]')` от кнопки меню) и проверить `expect(cell.className).toContain("items-end")` + `expect(cell.className).not.toContain("justify-end")`. Мотивация в комментарии теста: на `flex-col` от `DataGrid` `justify-end` = вертикальная ось, поэтому меню уезжало вниз (#1165).
9. То же в `SecurityGroupRBACPolicies.test.tsx` (для строки политики) и в `SecurityGroupRulesTable.test.tsx` (для ячейки действий правила).
10. Проверить, что существующие тесты не полагались на выравнивание — проверено: единственное упоминание className в этих трёх файлах — `SecurityGroupRulesTable.test.tsx:344` (`pill-value`), к ячейке действий не относится; снапшот-тестов в репозитории нет.

**Верификация:**
```
pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/network/securitygroups src/client/components/ListToolbar
```

---

### Step 12: Changeset(ы)

**Файлы:** `.changeset/<generated-name>.md` (по одному на PR)

**Что сделать:**
1. Создавать через `pnpm changeset` (интерактивно) либо вручную по образцу существующих файлов (`.changeset/single-primary-action.md`).
2. **Пакет — только `@cobaltcore-dev/aurora`, bump — `patch`.** Обоснование:
   - все изменения имеют тип `fix`, а по таблице в `CONTRIBUTING.md` `fix`/`perf` → patch;
   - публичный API пакета не меняется: `packages/aurora/src/client/index.ts` не экспортирует ни типы `ListToolbar`, ни `SelectedFilters`, ни роутеры Network — расширения `Filter.valueLabels` и `SelectedFilters.filters` внутренние и **опциональные**;
   - `packages/signal-openstack` **не включаем** — его код не меняется, мы лишь вызываем уже существующий `validateAndEncodeResourceId` (в отличие от #1153, где хелпер вводился и changeset справедливо включал оба пакета);
   - `apps/dashboard` (`@cobaltcore-dev/dashboard`) не указываем — changesets сам бампит internal deps как patch (`.changeset/config.json`);
   - **не** ставить `minor`: в истории репозитория уже был ряд несоответствий changeset/семвер (#1173/#1176/#1189, релиз 1.2.0), плодить ещё один не нужно. И наоборот — не оставлять PR совсем без changeset (кейс #1256/#1262, а также удалённый changeset в #1276): тогда фикс не попадёт в CHANGELOG публикуемого пакета.
3. Текст changeset'а для security-PR — по стилю #1153, без рецепта эксплуатации:
   > Security group rule and RBAC policy IDs are now validated and encoded before being interpolated into OpenStack request paths, matching the protection already applied to security group, floating IP and flavor IDs.
4. Текст для UI-PR:
   > Security Groups list: the Shared filter now sends a correctly typed value (filtering no longer fails), filter options and pills show the same Yes/No labels as the table, the page header and toolbar stay visible while the list loads, and the search box triggers a debounced search instead of requiring Enter. Kebab menus in the security group, rule and RBAC policy tables are vertically centred in their row again.

---

## Testing Plan

**Unit (vitest, колокейшн):**
- [ ] `filterConfig.test.ts`: `"true"→{shared:true}`, `"false"→{shared:false}`, `banana→{}`, пустой список→`{}`, `inactive`-фильтры игнорируются
- [ ] `securityGroupRuleRouter.test.ts` (новый): happy-path URL + `..`, `?`, `.`, `""` → `BAD_REQUEST` и `del` не вызван; `"rule 1"` → `%20`
- [ ] `rbacPolicyRouter.test.ts`: те же кейсы для `update` (`put`) и `delete` (`del`) + happy-path URL-ассерты
- [ ] `FiltersInput.test.tsx`: label из `valueLabels`, `onChange` с сырым value
- [ ] `SelectedFilters.test.tsx`: с `filters` и без (регресс-гард)
- [ ] `SecurityGroupsList.test.tsx`: boolean во входе запроса, лейблы Yes/No, header+toolbar при loading/error, FORBIDDEN-сообщение, debounce (один navigate), Enter и clear — мгновенные
- [ ] `SecurityGroupListContainer.test.tsx`: заголовки колонок при loading/error, отсутствие пустого состояния при `isLoading`
- [ ] `SecurityGroupTableRow.test.tsx` / `SecurityGroupRBACPolicies.test.tsx` / `SecurityGroupRulesTable.test.tsx`: className ячейки действий содержит `items-end` и не содержит `justify-end`

**Интеграционные (router-level, через `createCallerFactory`):**
- [ ] `securityGroup.list` с `{ shared: true }` и `{ shared: false }` проходит валидацию входа и формирует ожидаемый query к Neutron (`?shared=true`, key-map не задет)
- [ ] `securityGroup.list` с `{ shared: "true" }` отклоняется схемой (документируем контракт — тест в `server/Network/types/securityGroup.test.ts`)

**Ручная проверка (dev, `pnpm dev` → http://localhost:4005):**
1. Проект с собственными и shared группами → открыть Security Groups.
2. Фильтр «Filter by: Shared» → в списке значений видно **Yes / No** (не true/false). Выбрать Yes: список грузится (не BAD_REQUEST), pill показывает `Shared: Yes`, URL `?shared=true`.
3. Прогнать все четыре комбинации: Shared=Yes/No × Sort by Name/Project id. ⚠️ Отдельно смотреть, не отвечает ли Neutron 400 на `sort_key=project_id` в отфильтрованной ветке (см. риск #1) — если да, применить митигацию (сортировка в памяти).
4. Перезагрузить страницу с `?shared=true` — фильтр восстановлен, pill корректен; вручную подставить `?shared=banana` — pill не появляется, список грузится.
5. Во время загрузки (throttling «Slow 3G» в DevTools): `ContentHeader`, Create-кнопка, сортировка, фильтры, поиск и шапка колонок остаются; крутилка — в области строк.
6. Сменить фильтр на загруженном списке: старые строки остаются до прихода новых, «No security groups found» не мигает.
7. Ввести в поиск `web` быстро → в Network-панели один запрос `securityGroup.list` спустя ~0.5 с. Затем Enter — запрос сразу. Затем крест — сразу и без «догоняющего» запроса.
8. Сломать запрос (например, отключить сеть) → красный баннер сверху, тулбар доступен, фильтр можно снять.
9. Kebab-меню: список SG (в т.ч. строка shared-группы с подписью Owner), таб Rules, таб RBAC — иконка по центру высоты строки, у правого края.
10. Удаление правила и удаление/изменение RBAC-политики работают как раньше (регресс security-фикса).

---

## Acceptance Criteria

**Issue #1138 (Filtering fails)**
- [ ] Выбор фильтра `Shared` не приводит к ошибке запроса; `network.securityGroup.list` получает `shared` типа `boolean`
- [ ] Попытка передать в `shared` строку ловится `pnpm typecheck` (проверено намеренной регрессией в билдере)
- [ ] Имена и типы параметров фильтра выводятся из `listSecurityGroupsInputSchema` (`Pick<ListSecurityGroupsInput, …>`), а не дублируются строками
- [ ] Значения фильтра в дропдауне и в pill'ах — `Yes`/`No`, идентичны колонке `Shared` в таблице; в URL и в запрос уходит `true`/`false`
- [ ] Неизвестное значение фильтра в URL игнорируется (нет pill, нет параметра в запросе)
- [ ] Во время загрузки и при ошибке видны `ContentHeader`, кнопка Create, `SortInput`, `FiltersInput`, `SearchInput` и шапка колонок таблицы; индикатор — только в области строк
- [ ] Пустое состояние не показывается, пока `isLoading`; при смене фильтра/поиска предыдущие строки остаются до прихода новых
- [ ] Поиск запускается автоматически через 500 мс после последнего символа; Enter и очистка срабатывают мгновенно; серия из N символов даёт один запрос
- [ ] Ошибка refetch'а при непустом списке показывается неблокирующим `Message`, тулбар остаётся управляемым

**Issue #1165 (Kebab menu not aligned)**
- [ ] `SecurityGroupTableRow`, `RBACPolicyRow`, `SecurityGroupRulesTable` используют `className="items-end pr-0"` (как `FloatingIpTableRow`)
- [ ] Юнит-тесты фиксируют отсутствие `justify-end` в ячейке действий во всех трёх компонентах
- [ ] Меню визуально по центру строки по вертикали, включая двухстрочные строки (shared-группа с подписью Owner)

**Security fix**
- [ ] `securityGroupRule.delete`, `rbacPolicy.update`, `rbacPolicy.delete` пропускают ID через `validateAndEncodeResourceId` до интерполяции
- [ ] ID с `..`, `/`, `?`, `#`, одиночная точка и пустая строка → `TRPCError BAD_REQUEST`, сетевой вызов не выполняется (ассерт `not.toHaveBeenCalled`)
- [ ] Легитимные ID работают без изменений; URL в happy-path зафиксирован тестом
- [ ] Ни одна Zod-схема не ослаблена (валидация остаётся на уровне роутера, по конвенции домена Network)

**Общее**
- [ ] Нет регрессий в Images / Floating IPs / Rules-таблице (потребители общего `ListToolbar`)
- [ ] `pnpm check-i18n` идемпотентен, каталоги `en`/`de` закоммичены
- [ ] Changeset присутствует в каждом PR: `@cobaltcore-dev/aurora: patch`
- [ ] `pnpm --filter @cobaltcore-dev/aurora typecheck`, `... lint`, `... test` зелёные; `pnpm lint`/`pnpm typecheck` в корне зелёные

---

## Delivery: коммиты и PR

**Рекомендация — два PR.**

**PR 1 (сервер, безопасность):** Steps 1-3 + changeset.
Заголовок: `fix(aurora): validate resource IDs before path interpolation in network routers`
Один коммит достаточен (диф ~20 строк кода + тесты), при желании разделить: `fix(aurora): validate ruleId …` / `fix(aurora): validate policyId …` / `test(aurora): cover path validation in network routers`.
Почему отдельно: серверный, без пользовательских изменений, ревьюится security-глазами и мержится независимо; не должен ждать итераций по UI-скриншотам. Прямое продолжение уже смерженного #1153 — ревьюеру достаточно этого контекста.

**PR 2 (UI, #1138 + #1165):** Steps 4-11 + changeset, коммитами:
1. `fix(aurora): send typed filter params in security groups list` (Steps 4, 6 частично + `filterConfig.test.ts`)
2. `feat(ui): support human-readable filter value labels in list toolbar` (Step 5 + тесты) — тип `feat`, т.к. добавляется опциональная возможность общего компонента; если мейнтейнеры предпочтут не смешивать типы в fix-PR, оформить как `refactor(ui): …`
3. `fix(aurora): match security groups filter labels with table values` (остаток Step 6)
4. `fix(aurora): keep header and toolbar visible while security groups load` (Step 7 + тесты контейнера)
5. `fix(aurora): debounce security groups search input` (Step 8 + тесты)
6. `fix(aurora): center kebab menu in security groups tables` (Step 9 + тесты)
7. `chore(aurora): update i18n catalogs` (Step 10) + changeset (можно приложить к первому коммиту)

Заголовок PR: `fix(aurora): fix security groups filtering, loading state, search and kebab alignment (#1138) (#1165)` — формат «(#issue) (#issue)» соответствует истории (`… (#1237) (#1274)`).

**Альтернатива — три PR** (#1138 / #1165 / security): даёт трассируемость «один issue = один PR», ценой третьего цикла CI и ревью для трёхстрочного CSS-фикса. Разумно только если мейнтейнеры закрывают issue строго по PR-ссылке. #1165 при этом дешевле приложить к #1138: те же файлы, тот же эпик, один прогон визуальной проверки.

---

## Follow-ups (вне скоупа, зафиксировать как issues)

1. 🔒 **`imageRouter.memberId`** — тот же незакрытый класс: `packages/aurora/src/server/Compute/routers/imageRouter.ts`, ~строки 757/807/832 (интерполяция `memberId` в путь Glance без `validateAndEncodeResourceId`). Вне эпика Security Groups; отдельный issue/PR по образцу PR 1 этого плана.
2. **Дубликат `urlHelpers.ts`** между `network/securitygroups/` и `network/floatingips/` (файлы отличаются только именем типа и именем фильтра) — свести в один общий модуль, желательно сразу с типизированным билдером параметров из Step 4 в обобщённом виде.
3. **Мёртвый код:** `client/utils/buildFilterParams.ts` + `buildFilterParams.test.ts` и композитный `client/components/ListToolbar/index.tsx` (+ его тест) не используются ни одним списком — либо перевести списки на `ListToolbar`, либо удалить.
4. **Унификация kebab-ячеек:** привести Ceph `CorsRulesTable`/`LifecycleRulesTable` (обёртка `flex h-full items-center justify-end` внутри ячейки с `justify-end pr-0`) к общему `items-end pr-0`; заодно рассмотреть общий `<RowActionsCell>`-компонент, чтобы класс не расползался копипастой.
5. **Лейблы значений в других списках:** Floating IPs (`ACTIVE`/`DOWN`/`ERROR`) и Images (`protected: true/false`) имеют ту же проблему «значение фильтра ≠ значение в таблице»; инфраструктура (`valueLabels`) после Step 5 уже есть.
6. **`sort_key` в отфильтрованной ветке `securityGroupRouter.list`**: если ручная проверка (Step п.3) покажет расхождение поведения сортировки между ветками `shared !== undefined` и `shared === undefined`, выровнять на in-memory `sortSecurityGroups` в обеих.
7. **`validateSearch` для роута** `/_auth/projects/$projectId/network/securitygroups/`: сейчас search-параметры не типизированы (`useSearch({ strict: false })` + приведение типа), из-за чего дефекты вроде `?shared=banana` приходится ловить вручную.

---

## Open Questions

Инструмента для интерактивного вопроса в этой сессии нет, поэтому ниже — решения, принятые по умолчанию; отменяемы одним словом.

1. **Расширять общий `ListToolbar` или решать локально?** Принято: расширять (два опциональных поля, потребители не ломаются, переиспользуемо для Floating IPs/Images). Локальная альтернатива — свой `FiltersInput`/pills в папке securitygroups — дала бы четвёртую копию тулбара; не рекомендуется.
2. **Скоуп #1165.** Принято: только три файла Security Groups; унификация Ceph-вариантов — follow-up. Если мейнтейнер хочет единообразие сразу — добавить 7-й коммит `refactor(ui): unify row action cell alignment` в PR 2.
3. **Один PR или два.** Принято: два (security отдельно).
4. **Показывать ли оверлей при refetch** (как `ImageListView` с `bg-theme-background-lvl-0/50 … backdrop-blur-sm`) поверх «просто остающихся строк»? Принято: без оверлея (паттерн Floating IPs), чтобы поиск с debounce не мигал блюром на каждый запрос. Если UX захочет явный сигнал — добавить оверлей под условием `isFetching && !isLoading` в `SecurityGroupsList`.
5. **Тип коммита для расширения `ListToolbar`** — `feat(ui)` (моя рекомендация) или `refactor(ui)`: влияет только на CHANGELOG-группировку, changeset всё равно `patch`.
