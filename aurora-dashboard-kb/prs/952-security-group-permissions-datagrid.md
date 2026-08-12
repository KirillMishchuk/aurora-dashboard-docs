# PR #952: feat(aurora): security group data grid, permissions

**Автор:** KirylSAP · **Статус:** смержен 23.07.2026 (`cb548a4a`)
**Ветки:** `kiryl-security-group-refactor` → `main` · **Файлов:** 25 (+939/-756)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/952

> `baseRefOid` PR (`fd1a2ba`) сильно отстал от текущего `main` (более 70 коммитов) — отчёт построен на `git diff <baseRefOid>..<headRefOid>`, что даёт именно те 25 файлов, которые правит сам PR.

## Что сделано

PR закрывает два связанных бага в UI Security Groups (issue #835 "Edit на DataGrid и деталях" и issue #836 "сообщение об ошибке остаётся висеть при переоткрытии модалки") и попутно переносит список security groups на общий паттерн DataGrid-тулбара, уже используемый в Images/Flavors (issue #888). Три независимых куска:

1. **Реальные permissions вместо заглушки.** До PR `permissions` в `SecurityGroupsList.tsx` был захардкожен `TODO`-объектом `{ canCreate: true, canUpdate: true, canDelete: true, canManageAccess: true }` — то есть Edit/Delete в меню строки и так уже были формально "гейтнуты" пропом `permissions.canUpdate`/`canDelete` (эта проверка существовала и до PR), но сам проп всегда был `true`, так что гейт был декоративным. Это и есть источник бага #835. PR заменяет заглушку хуком `useSecurityGroupPermissions`, который реально ходит в `network.canUser` (bulk-запрос из 9 permission-ключей) и раскладывает результат по позициям массива.
2. **DataGrid-тулбар в три зоны** для списка security groups (сортировка+Create, фильтр+поиск+чипы, задел под bulk actions) и почти идентичный тулбар для таблицы правил (`SecurityGroupRulesTable`) и RBAC-политик (`SecurityGroupRBACPolicies`) — с URL-персистентностью через новый `urlHelpers.ts` (тот же паттерн, что уже есть у Images/Swift).
3. **Попытка исправить #836** (ошибка модалки не сбрасывается) — добавлен `handleClose`/`onClearUpdateError` в паре мест. Как показано в разделе "Ревью", это исправлено только частично.

## Как это реализовано

**Permission hook — позиционная распаковка bulk-ответа `canUser`** (`-hooks/useSecurityGroupPermissions.ts:29-66`):

```ts
} = trpcReact.network.canUser.useQuery(
  {
    project_id: projectId || "",
    permission: [
      "network:security_groups:read", "network:security_groups:create",
      "network:security_groups:update", "network:security_groups:delete",
      "network:security_group_rules:create", "network:security_group_rules:delete",
      "network:rbac_policies:create", "network:rbac_policies:delete", "network:rbac_policies:read",
    ],
  },
  {
    enabled: Boolean(projectId),
    select: ([canView, canCreate, canUpdate, canDelete, canCreateRule, canDeleteRule,
               canCreateRBAC, canDeleteRBAC, canViewRBAC]) => ({
      canView, canCreate, canUpdate, canDelete, canCreateRule, canDeleteRule,
      canManageAccess: canCreateRBAC && canDeleteRBAC,
      canViewRBAC,
    }),
    staleTime: Infinity,
    gcTime: Infinity,
  }
)
```

Порядок позиционной распаковки я сверил построчно с массивом `permission` и с `createPermissionRouter.ts:157-163` (`permissions.map(...)` сохраняет порядок входного массива, не сортирует и не группирует по engine) — совпадение 1:1, здесь всё корректно. Дефолт при `data === undefined` (первый рендер и ошибка запроса) — объект из одних `false` (`useSecurityGroupPermissions.ts:24-32`), то есть при ошибке или до загрузки UI фейлится в сторону "ничего нельзя", а не в сторону старой заглушки "можно всё" — это прямое исправление именно той дыры, которую описывает issue #835.

**Реальная проверка permissions в строке таблицы уже существовала** (`SecurityGroupTableRow.tsx:90-91`, не менялось этим PR):

```tsx
{permissions.canUpdate && !isReadOnly && <PopupMenuItem label={t`Edit`} onClick={() => onEdit(sg)} />}
{permissions.canDelete && !isReadOnly && <PopupMenuItem label={t`Delete`} onClick={() => onDelete(sg)} />}
```

т.е. баг #835 был не в отсутствии проверки, а в том, что проверяемое значение было захардкожено `true` на уровень выше — это стоит знать, если кто-то будет искать регрессию в этом компоненте в будущем: сам компонент никогда не был "виноват".

**`canManageAccess` — AND, а не раздельные права** (`useSecurityGroupPermissions.ts:63`) — см. "Ревью".

**Zone-тулбар и URL-состояние** (`SecurityGroupsList.tsx:39-90`, `urlHelpers.ts`): `sortSettings`/`filterSettings`/`searchTerm` — локальный `useState`, инициализированный один раз из `useSearch({strict:false})`; сам же tRPC-запрос (`SecurityGroupsList.tsx:74-90`) берёт значения не из этого state, а заново из `searchParams` через `urlFilters`/`urlSortBy`/`urlSortDirection`/`urlSearchTerm` (строки 69-72) — то есть данные всегда соответствуют URL, а вот отображаемое состояние контролов (что подсвечено в `SortInput`, какие чипы показаны в `SelectedFilters`, что в поле поиска) может разойтись с URL при навигации назад/вперёд в браузере, см. "Ревью".

## Что затронуло

`useSecurityGroupPermissions`/`SecurityGroupPermissions` не экспортируются за пределы `network/securitygroups/` — `git grep` по всему монорепо на `<headRefOid>` не находит потребителей вне самой фичи (`grep -n "useSecurityGroupPermissions\|SecurityGroupPermissions"` вне `securitygroups/` — пусто). Серверные файлы (`network.canUser`, `permissionRouter.ts`) этим PR не тронуты вообще — весь diff клиентский. Так что blast radius ограничен экраном Security Groups, никаких внешних контрактов не меняется.

Внутри фичи: `SecurityGroupsList.test.tsx` (439 строк) **удалён без замены** — файл `SecurityGroupsList.tsx` (сам компонент верхнего уровня со списком, тулбаром, Create-модалкой и permission-гейтингом Create-кнопки) остался вообще без собственных тестов после PR. Это прямо объясняет, почему обе находки ниже (незакрытая ошибка Create-модалки и рассинхронизация UI-контролов с URL) не были пойманы: единственный код, который их мог бы поймать, был удалён, а взамен ничего не добавлено.

## Ревью

Пайплайн (5 параллельных агентов: CLAUDE.md-соответствие, беглый поиск багов, исторический контекст git blame/log, прежние PR-комментарии CodeRabbit на этот же PR, соответствие кодовым комментариям) плюс независимый confidence-scoring дал одну находку с уверенностью ≥80, дополнительно подтверждённую (обе части) ранее оставленным и неисправленным комментарием CodeRabbit на этом же PR:

1. **Bug #836 не исправлен так, как заявлено в описании PR** (confidence 90) — `SecurityGroupsList.tsx:290-312`, `SecurityGroupListContainer.tsx:58-65`. Описание PR утверждает: *"CreateSecurityGroupModal: Now resets error state in `handleClose()` to prevent error persistence"* и то же самое для `EditSecurityGroupModal`. По факту:
   - **Create-модалка вообще не подключена к состоянию мутации.** `isLoading={false}` (`SecurityGroupsList.tsx:310`) — захардкожено, спиннер "создаётся..." никогда не покажется, хотя `createSecurityGroupMutation.isPending` существует и используется для других мутаций рядом. `onClose={() => setCreateModalOpen(false)}` (строка 308) не сбрасывает `createError` — `handleClose()` внутри `CreateSecurityGroupModal.tsx:97-101` чистит только локальные `properties`/`errors` (валидация формы), не проп `error`. При повторном открытии модалки после неудачного создания старое сообщение об ошибке будет видно сразу, до какого-либо ввода — именно то поведение, которое описывает issue #836.
   - **Edit-модалка исправлена лишь частично.** `handleEdit` в `SecurityGroupListContainer.tsx:58-65` вызывает `onClearUpdateError` только при переключении на **другую** security group (`selectedSecurityGroup.id !== sg.id`). Если переоткрыть Edit для той же самой группы после неудачного обновления — `updateError` (стейт, поднятый в `SecurityGroupsList.tsx`) не очищается нигде, старая ошибка показывается снова.
   
   Оба факта независимо подтверждены комментарием CodeRabbit на этом же PR (коммит диапазона до финального `head`, актуальность не менялась): *"The CreateSecurityGroupModal usage in SecurityGroupsList is not wired to the mutation state and leaves stale errors behind... make the close handler clear createError... matching the behavior used for the Edit modal"* — то есть замечание описывает ровно эту находку и на момент анализа (`head` = `0377fe6`) не устранено.

Ещё две находки подтверждены самостоятельно и (частично) тем же ревью CodeRabbit на этом PR, но по вероятности/серьёзности — на уровне "также замечено":

- **Локальные UI-контролы (сортировка/фильтры/поиск) могут разойтись с URL** (confidence 60) — `SecurityGroupsList.tsx:40-61`. `sortSettings`/`filterSettings`/`searchTerm` — это `useState`, инициализированный один раз значением `searchParams` на момент первого рендера, без эффекта, ресинхронизирующего их при последующих изменениях `searchParams` (навигация назад/вперёд, программный переход по ссылке с другими query-параметрами). Сам список данных при этом не ломается — сетевой запрос строится напрямую из `searchParams`, а не из этого state (см. "Как это реализовано"), но отображаемые в `SortInput`/`SelectedFilters`/`SearchInput` значения могут временно показывать не то, что реально применено. Тот же паттерн повторяется в `localSearchTerm` (`SecurityGroupRulesTable.tsx:72`, инициализация из пропа `searchTerm` без ресинхронизации). Отмечено тем же комментарием CodeRabbit на PR.
- **`canManageAccess` требует ОБА права (`create` И `delete`) одной AND-связкой** (confidence 55) — `useSecurityGroupPermissions.ts:63`: `canManageAccess: canCreateRBAC && canDeleteRBAC`. У пользователя, которому назначено только `network:rbac_policies:delete` (без `:create`, или наоборот), `canManageAccess` окажется `false` — он не увидит ни кнопку "Share Security Group" (ожидаемо, это create), ни возможность удалить существующую RBAC-политику в `RBACPolicyRow` (`canDelete={canManageAccess}` в `SecurityGroupRBACPolicies.tsx:191`) — хотя формально у него есть отдельное право на delete. В OpenStack Neutron это действительно разные policy-правила; объединение их в один флаг воспроизводит ровно тот класс бага (видимость действий не по правам пользователя), который PR призван устранить для остальных полей.
- **Задел под bulk actions полностью нерабочий** (confidence 50) — `SecurityGroupsList.tsx:302` передаёт `hasAnyBulkAction={false}` жёстко захардкоженным (единственный call site `SecurityGroupListContainer`, `git grep` подтверждает). Чекбоксы выбора строк, колонка выбора и вся ветка "Zone 3: Bulk actions toolbar", упомянутая в описании PR, технически existance в коде (`SecurityGroupTableRow.tsx:63-67`, пропы `showSelectColumn`/`isSelected`/`onSelect`), но недостижима ни при каком состоянии приложения — весь этот путь мёртвый код на момент PR.
- **Удаление поля Stateful из Edit-модалки не имеет видимого объяснения в UI** (confidence 45, ниже порога включения, но упомяну как контекст) — старое инфо-сообщение про ограничение `stateful` удалено полностью и заменено JSX-комментарием (`EditSecurityGroupModal.tsx:187`), который никогда не рендерится. Технически безопасно (поле реально требует cloud-admin роль), но пользователь теперь не видит объяснения, почему чекбокс исчез. Отмечено тем же CodeRabbit-ревью как trivial nitpick.

**Что сделано хорошо:** дефолт permissions-хука на случай ошибки/загрузки — объект из одних `false`, а не старая заглушка "всё можно" — это правильная сторона отказа для UI, завязанного на permissions; RBAC-таб (`SecurityGroupDetailsView.tsx:60`) корректно учитывает и `isOwner`, и `canViewRBAC` одновременно, а не только одно из двух.

---
Проанализировано: 21.07.2026 · коммит `0377fe6`
