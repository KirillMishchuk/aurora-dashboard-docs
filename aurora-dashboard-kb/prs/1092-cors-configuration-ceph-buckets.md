# PR #1092: feat(aurora): add CORS configuration management for Ceph/S3 buckets

**Автор:** KirylSAP · **Статус:** смержен 12.08.2026 (коммит `b7576db`)
**Ветки:** `kiryl-ceph-cors` → `main` · **Файлов:** 35 (+4643/-45, после раунда 4)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1092

> Это четвёртая версия отчёта. Первая (25.07.2026, коммит `1f7a0d9`) описывала модалку-ориентированную реализацию (20 файлов, +2212/-6). Вторая (11.08.2026 утром, коммит `834f993`) зафиксировала полный редизайн в таб-based UI (34 файла, +4478/-45) и 3 находки ≥80. Третья (11.08.2026 днём, коммит `5d8fb2d`) зафиксировала первый раунд фиксов — 1 из 3 находок закрыта, 2 остались открытыми, плюс 2 новых кандидата на 75/70. Эта версия — по итогам четырёх целевых фикс-коммитов `4f16ad3`/`356618c`/`81598e1`/`8cbd4a5` (11.08.2026, 14:09), написанных по промптам для `dev-executor`, подготовленным по итогам предыдущего отчёта. Ветка синхронизирована с `main` (merge-base = текущий `origin/main`).

### Раунд 4 (коммиты `4f16ad3` → `8cbd4a5`, 13 файлов, +95/-49) — все 4 оставшиеся находки закрыты

Все четыре промпта выполнены и проверены построчно по коду (не по тексту коммитов):

- **[Было #1, 100] Changeset — ИСПРАВЛЕНО.** Текст переписан: больше не утверждает, что что-либо убрано из шапки, корректно описывает добавленный таб «CORS Rules» и добавленный пункт «Delete CORS Rules» в меню шапки.
- **[Было #2 (в 3-й версии), 95] Хелптекст Rule ID — ИСПРАВЛЕНО.** `placeholder`/`helptext` заменены на текст, релевантный CORS-правилу; строки `"Access to admin area"` и `"Confirm that the Project ID is accurate."` полностью ушли из `en/de messages.po` при `pnpm check-i18n` (значит, других легитимных использований этих строк в кодовой базе не было — предыдущее предположение, что первая строка используется для настоящего поля Project ID, не подтвердилось, но и не создало проблемы: чистое удаление).
- **[F, 50] `isMutating={false}` — ИСПРАВЛЕНО.** Реализовано ровно так, как описано в промпте: `onMutatingChange` проведён через `CorsRuleModal`, `DeleteCorsRulesModal`, `DeleteCorsRuleModal` (по образцу существующего `onValidationChange`), `CorsRulesTab` и `CorsRulesTable` агрегируют состояние в `effectiveIsMutating`, которое теперь реально дизейблит Edit/Delete в строках. Код проверен построчно — реализация корректна.
- **[A, 50] Мёртвый `DeleteCorsModal` в табе — ИСПРАВЛЕНО.** Стейт `isDeleteModalOpen`, рендер-блок, неиспользуемые импорты (`DeleteCorsModal`, `getCorsDeleteErrorToast`) и мок в тесте убраны полностью и аккуратно — рабочий путь удаления всей конфигурации через шапку (`BucketHeaderActions`/`BucketModals`) не тронут.

Два новых наблюдения от этого же раунда, оба **не прошли порог ≥80** (независимый confidence-scoring):
- **[75] Новый тест на `isMutating` не проверяет то, что заявляет.** Восстановленный тест `CorsRulesTable.test.tsx` называется «renders without errors when isMutating is true», но проверяет только отсутствие краша и наличие кнопки меню — не открывает меню и не проверяет, что Edit/Delete действительно `disabled`. Сама реализация (`effectiveIsMutating`) корректна и проверена мной по коду напрямую, но регрессию (например, случайно вернувшийся хардкод `isMutating={false}`) этот тест не поймает.
- **[70] Узкое «слепое окно» в `onMutatingChange` во время проверки свежести.** Во всех трёх модалках (`CorsRuleModal`, `DeleteCorsRuleModal`, `DeleteCorsRulesModal`) перед мутацией идёт `await ...cors.get.fetch(...)` (freshness check) — в этот момент `setMutation.isPending`/`deleteMutation.isPending` ещё `false`, поэтому `onMutatingChange` в этот короткий промежуток (один сетевой запрос) сообщает «не мутирует», хотя действие уже запущено. `DeleteCorsRuleModal`/`DeleteCorsRulesModal` завели локальный `isVerifying` и блокируют им свою собственную кнопку подтверждения, но не включили `isVerifying` в сам `onMutatingChange` — так что для СОСЕДНИХ строк таблицы защита на это окно не распространяется. `CorsRuleModal` такого локального флага для своей ветки редактирования не завёл вовсе. Узкое окно, требует одновременной работы двух пользователей с одним бакетом — по оценке обеих независимых проверок это реальный, но маловероятный на практике геп.

### Что изменилось с предыдущей версии отчёта (коммит `5d8fb2d`, 16 файлов, +250/-131)

Коммит `5d8fb2d` целенаправленно закрывает часть находок из предыдущего отчёта:

- **[Было #2, 100] Хардкод нелокализованных тостов при удалении CORS из шапки — ИСПРАВЛЕНО.** `BucketModals.tsx` теперь использует `getCorsDeletedToast`/`getCorsDeleteErrorToast` вместо шаблонных строк — ровно то, что было предложено.
- **Стейл-индекс `selectedIndices` после поштучного удаления (не набрал порог, 75) — ИСПРАВЛЕНО (грубо, но рабочим способом).** `CorsRulesTab` получил `handleDeleteRule`, который просто сбрасывает `selectedIndices` в `[]` при любом поштучном удалении — не хирургически (не сдвигает индексы), но полностью убирает риск стейл-индекса, ценой сброса всех остальных выборов пользователя.
- **`setState` во время рендера в `CorsRuleForm` (не набрал порог, 50) — ИСПРАВЛЕНО.** `onValidationChange` перенесён в `useEffect`.
- **`as any`-каст, вернувшийся после более раннего фикса (не набрал порог, 75) — ЧАСТИЧНО ИСПРАВЛЕНО.** Добавлен хелпер `toCorsRule()` в новом `utils/corsUtils.ts`, который инкапсулирует приведение типа `AllowedMethods` в одном явном, документированном месте вместо `as any` на весь объект с `eslint-disable` — не идеальная типобезопасность, но явно лучше и переиспользуется в трёх местах (`CorsRuleModal`, `DeleteCorsRuleModal`, `DeleteCorsRulesModal`).
- **Кросс-табовая гонка по индексу без проверки свежести (не набрал порог, 50) — ИСПРАВЛЕНО для edit/delete, НЕ для add** (см. новую находку в «Ревью» ниже). В `CorsRuleModal`, `DeleteCorsRuleModal`, `DeleteCorsRulesModal` перед мутацией теперь идёт повторный `fetch` + сравнение `JSON.stringify` конкретного правила с исходным снепшотом — если правило изменилось, показывается ошибка вместо тихой перезаписи.
- Плюс не связанные с прошлым отчётом фиксы: заглавие таба «Cors Rules» → «CORS Rules»; ключ строки в `CorsRulesTable` — всегда `originalIndex` (было `rule.ID ?? originalIndex`, что могло давать дублирующиеся React-ключи при отсутствующем/повторяющемся `ID`); в `DeleteCorsRulesModal` исправлена нумерация «Rule #N» в предпросмотре массового удаления — раньше use'ался индекс внутри обрезанного `visibleRules`, а не реальный индекс правила, из-за чего показывался неверный номер при выборе несмежных строк.

**Не закрыто:**

- **[Было #1, 100] Changeset утверждает, что пункт «Delete CORS Rules» убран из шапки — не тронут, утверждение всё ещё неверное.**
- **[Было #3, 95] Скопированный хелптекст «Confirm that the Project ID is accurate.» на поле Rule ID — не тронут.**
- **[F, 50] `isMutating={false}` всё ещё хардкодится** в `CorsRulesTab.tsx:298` при рендере `CorsRulesTable` — Edit/Delete в строках так и не блокируются во время мутации.
- **[A, 50] Второй недостижимый экземпляр `DeleteCorsModal` внутри `CorsRulesTab`** (гейт `isDeleteModalOpen`, `setIsDeleteModalOpen(true)` не вызывается нигде) — не тронут.

## Что сделано

PR закрывает **Section 12: CORS Configuration** эпика #608 для Ceph (S3) бакетов — backend (`corsRouter.ts`: `get`/`set`/`delete`) не менялся концептуально с июльской версии, но фронтенд полностью переизобретён: вместо модалки с двумя вкладками (просмотр/редактирование) теперь отдельная вкладка **«Cors Rules»** на странице деталей бакета, рядом с существующей вкладкой Overview — с полноценным CRUD: списком правил в `DataGrid`, поиском/сортировкой с состоянием в URL, поштучным и массовым удалением.

История веток (`git log`) показывает три волны: (1) `fc5cf77` (04.08) — первая реализация, модалка с двумя вкладками, как в июльской версии; (2) `bef794d` (10.08, "apply 6 critical fixes from code review") — фиксы по итогам самостоятельного ревью автора, включая замену `as any`-каста на честную клиентскую валидацию через отдельный файл `corsValidation.ts`; (3) `6025e09` (08.08) → серия коммитов до `834f993` (11.08) — полный редизайн на табы, при котором `corsValidation.ts` был удалён вместе с частью фиксов из (2) (см. «Ревью» и историческую находку ниже).

Три новых визуальных больших блока: сама вкладка (`CorsRulesTab`/`CorsRulesTable`), форма добавления/редактирования правила (`CorsRuleForm` в модалке `CorsRuleModal`), и **три** модалки удаления с разным охватом — удалить всю конфигурацию, одно правило или выбранную группу правил. Плюс новый переиспользуемый `TagInput` для полей-массивов строк (origins/headers).

## Как это реализовано

### Backend — `corsRouter.ts` не изменился по сути, но обзавёлся rate-limit'ом

Три процедуры под `cephProtectedProcedure`, смонтированные как `storage.ceph.cors.{get,set,delete}`:

```typescript
// packages/aurora/src/server/Storage/routers/index.ts:34-36
      cors: auroraRouter({
        ...corsRouter,
      }),
```

`get`/`delete` трактуют `NoSuchCORSConfiguration` как валидное «нет конфигурации» состояние, а не ошибку — тот же паттерн, что в июльской версии:

```typescript
// packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts:90-95
    } catch (error) {
      // NoSuchCORSConfiguration is not an error - it means no CORS config set
      const s3Error = error as { name?: string; Code?: string }
      if (s3Error.name === "NoSuchCORSConfiguration" || s3Error.Code === "NoSuchCORSConfiguration") {
        return { corsRules: null }
      }
```

Новое по сравнению с июльской версией — две схемы валидации вместо одной: строгая `corsRuleSchema` (для `set`, 1-5 `AllowedMethods` без дублей, ≥1 `AllowedOrigin` с проверкой wildcard-паттерна, `MaxAgeSeconds` только с `.min(0)` — верхней границы в схеме нет вообще) и лениентная `corsRuleReadSchema` (для `get`, принимает произвольные строки, чтобы не падать на правилах, созданных мимо Aurora):

```typescript
// packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts:85-89
      // Use lenient read schema to accept rules with values outside write-time constraints
      // (e.g., more than 5 AllowedMethods, though write schema now matches S3 limits)
      const corsRules = rawCorsRules.map((rule) => corsRuleReadSchema.parse(rule))
```

Также добавлен in-process rate limiter на `set` — не более 10 изменений в минуту на пару `projectId:bucketName`, состояние в module-level `Map`:

```typescript
// packages/aurora/src/server/Storage/routers/ceph/corsRouter.ts:8-38 (сокращённо)
const corsSetRateLimits = new Map<string, { count: number; resetAt: number }>()
function checkCorsSetRateLimit(bucketName: string, projectId: string): void {
  // ...
  if (limit.count >= 10) {
    throw new TRPCError({ code: "TOO_MANY_REQUESTS", ... })
  }
  limit.count++
}
```

Лимитер per-process (не распределённый) — при нескольких инстансах BFF за балансировщиком реальный порог масштабируется с числом реплик. В переписанный раздел дизайн-документа (`009_ceph_s3_bff.md`) этот лимитер не попал вообще — ни описания, ни оговорки про per-process поведение.

`s3ErrorMapper.ts` получил два новых кода (`NoSuchCORSConfiguration`, `MalformedXML`) — это общий файл для всех Ceph-роутеров, так что выигрывают все, не только CORS; впрочем `NoSuchCORSConfiguration` в мапере фактически недостижим, так как `corsRouter.ts` перехватывает эту ошибку раньше (см. «Ревью», отклонённая находка с оценкой 65).

`mockContext.ts` (общий тест-хелпер для всех Ceph-роутеров) расширен полями `res`/`signal` под реальную форму `AuroraPortalContext` — понадобилось для типизации нового `corsRouter.test.ts`, но заодно чинит мок для 6 других тестовых файлов Ceph-роутеров, которые его импортируют.

### Архитектура табов на странице бакета

Роут объектов (`.../$containerName/objects/index.tsx`) получил параметр URL `view: "overview" | "cors-rules"` (по умолчанию `"overview"`) и три CORS-специфичных параметра `corsSortBy`/`corsSortDirection`/`corsSearch`, независимых от параметров списка объектов:

```typescript
// objects/index.tsx:27-33
  view: z.enum(["overview", "cors-rules"]).optional().default("overview"),
  corsSortBy: z
    .enum(["ID", "AllowedOrigins", "AllowedMethods", "AllowedHeaders", "ExposeHeaders", "MaxAgeSeconds"])
    .optional()
    .default("ID"),
  corsSortDirection: z.enum(["asc", "desc"]).optional().default("asc"),
  corsSearch: z.string().optional(),
```

Ветвление по провайдеру и `view` — прямо в компоненте роута:

```typescript
// objects/index.tsx:108-124 (сокращённо)
              switch (provider) {
                case "swift":
                  return <SwiftObjects provider={provider} containerName={containerName} />
                case "ceph":
                  if (view === "cors-rules") {
                    return <CephCorsRules bucketName={containerName} />
                  }
                  return <CephObjects bucketName={containerName} />
```

Swift явно игнорирует `view` (закрыто регрессионным тестом `objects/index.test.tsx:344-360`). `CephCorsRules` — не новый компонент, а `CorsRulesTab`, реэкспортированный под этим именем из барреля `Ceph/Buckets/index.tsx:44`.

Сама полоска табов рендерится не в роуте, а в `BucketHeader` — над содержимым, которое выбирает роут:

```tsx
// .../Ceph/Buckets/BucketHeader.tsx:73-90 (сокращённо)
      <ContentHeader title={bucketName} projectId={projectId} badges={badges} actions={actions} />
      <div className="-mt-4 mb-8">
        <BucketDetailTabs />
        <Divider />
      </div>
      <BucketModals ... />
```

`BucketDetailTabs` — тонкая обёртка над `TabNavigation`, которая читает/пишет тот же параметр `view` через сгенерированный объект `Route` того же роута. То есть таб-переключатель и контент, который он переключает — два независимых читателя/писателя одного URL-параметра, синхронизированных только тем, что оба импортируют один `Route`. Работает, но структурно развязано (таб-компонент не оборачивает свой контент, а является параллельным потребителем состояния).

`useBucketInfo` расширен запросом `storage.ceph.cors.get`, результат используется в `BucketHeader` для `hasCors` (видимость бейджа/пункта меню).

### Вкладка CORS: контейнер, таблица, форма, TagInput

`CorsRulesTab` (353 строки) — контейнер: владеет запросом `cors.get`, состоянием сортировки/поиска (в URL-параметрах), состоянием выбора строк (`selectedIndices`) и оркестрирует три модалки (добавление/редактирование, удаление всей конфигурации, массовое удаление).

`CorsRulesTable` (190 строк) — презентационная таблица на 8 колонок, управляемая пропсами; при этом **сама владеет** состоянием для поштучного удаления (`deleteModalState` + собственный экземпляр `DeleteCorsRuleModal`) — это состояние не поднято в `CorsRulesTab`, в отличие от массового удаления. Строки идентифицируются по `rule.ID ?? originalIndex`, так как у правил нет стабильного серверного идентификатора.

`CorsRuleModal` оборачивает `CorsRuleForm` в `Modal`; на сабмите строит полный обновлённый массив правил и вызывает `cors.set` целиком (добавление — append, редактирование — замена по индексу):

```typescript
// CorsRuleModal.tsx:88-101
  const handleSubmit = (rule: CorsRuleRead) => {
    markSubmitted()
    const currentRules = corsData?.corsRules ?? []
    let updatedRules: CorsRuleRead[]
    if (editingIndex === null) {
      updatedRules = [...currentRules, rule]
    } else {
      updatedRules = [...currentRules]
      updatedRules[editingIndex] = rule
    }
```

Кнопка Save находится в футере модалки, а не в форме, и триггерит сабмит через `document.querySelector('#'+formId).requestSubmit()` — DOM-мост между футером и формой вместо `ref`.

`CorsRuleForm` использует `@tanstack/react-form`. Хелптекст поля Rule ID явно скопирован из другого поля и не отредактирован:

```tsx
// CorsRuleForm.tsx:65-73
          <form.Field name="ID">
            {(field) => (
              <TextInput
                label={t`Rule ID`}
                ...
                placeholder={t`Access to admin area`}
                helptext={t`Confirm that the Project ID is accurate.`}
```

Строка `"Confirm that the Project ID is accurate."` уже существует в `de/messages.po:636` для другого, не связанного с CORS поля Project ID — почти наверняка copy-paste. См. «Ревью», п. 3 (оценка 95).

`TagInput` (новый общий компонент, 165 строк) — поле для массива строк с валидаторами `urlValidator`/`headerValidator`. Эти валидаторы дублируют (другим кодом, те же правила) логику `.refine()` в серверной `corsRuleSchema` — клиент и сервер независимо переизобретают одну и ту же проверку wildcard-origin. У компонента нет ни одной строки, пропущенной через Lingui (кнопка "Add", тексты ошибок валидаторов) — все остальные новые компоненты этого PR корректно используют `t`/`Trans`.

### Три модалки удаления — разный охват, одна не подключена

1. **`DeleteCorsModal`** — удаляет **всю конфигурацию CORS** (`cors.delete`). Подключена дважды: (а) из меню действий заголовка бакета через `BucketHeaderActions.tsx:49` → `BucketModals.tsx:131-143` — этот путь реально работает; (б) отдельный экземпляр внутри `CorsRulesTab.tsx:296-309`, гейтящийся стейтом `isDeleteModalOpen` (объявлен на строке 78) — но `setIsDeleteModalOpen(true)` не вызывается нигде в файле или в репозитории (только `false` на строках 300/302). Этот второй экземпляр — недостижимый мёртвый код, судя по всему, остаток от рефакторинга, когда «Delete All» заменили на массовое удаление по выборке.
2. **`DeleteCorsRuleModal`** — удаляет одно правило по индексу, вызывается из строки таблицы (внутреннее состояние `CorsRulesTable`, не поднято в таб).
3. **`DeleteCorsRulesModal`** — массовое удаление по выбранным индексам, с превью первых `MAX_VISIBLE_RULES = 5` правил и строкой «…и ещё N».

Оба #2 и #3 живые и содержательно разные (одно правило vs выборка). #1 в варианте (а) — намеренный «глобальный» шорткат из шапки, но #1 в варианте (б) — мёртвый код, который стоит либо подключить к UI-триггеру, либо убрать вместе с `isDeleteModalOpen`.

Все три модалки удаления независимо друг от друга делают свой `cors.get.useQuery` вместо переиспользования уже загрученных данных из `CorsRulesTab`/`useBucketInfo`, полагаясь на кэш React Query.

### Локали, дизайн-документ, changeset

Changeset (`minor` для `@cobaltcore-dev/aurora`) утверждает: *«The Add CORS, Edit/View CORS buttons, and Delete CORS menu item have been removed in favor of full CRUD operations within the Cors Rules tab.»* Это **не соответствует действительности** — сравнение с базовым коммитом (`c65b027a`) показывает, что до этого PR в шапке бакета вообще не было ни кнопок CORS, ни пункта «Delete CORS Rules» — этот PR **добавляет** пункт «Delete CORS Rules» в меню шапки, а не убирает что-либо. См. «Ревью», п. 1 (оценка 100).

Дизайн-документ (`009_ceph_s3_bff.md`) получил полноценный раздел `### CORS Configuration (storage.ceph.cors)` — с описанием `get`/`set`/`delete`, примерами и заметкой про особенности тестирования CORS в Ceph RGW (RGW не добавляет CORS-заголовки к HEAD-запросам, только к GET/POST/PUT/DELETE/OPTIONS). В этой заметке — ссылка `DOCS/plans/2026-07-25-cors-manual-testing-scenarios.md`, которая указывает на личную (не входящую в репозиторий) папку заметок автора; для апстрим-читателей этого PR путь не будет существовать (см. «Ревью», отклонённая находка с оценкой 75). Также раздел про `MaxAgeSeconds` в документе (и один из комментариев в `types/ceph.ts:581`) утверждает верхнюю границу 86400, хотя в реальной Zod-схеме максимума нет (см. отклонённую находку с оценкой 75).

Локали `en`/`de` выросли с 1255 до 1330 строк `msgid` (+75 под новый CORS UI); все 75 новых немецких строк имеют пустой `msgstr ""` — перевода нет ни для одной, каталог только переэкстрагирован. Вероятно, это отдельный процесс перевода, а не недосмотр этого PR.

## Что затронуло

PR полностью самодостаточен внутри `packages/aurora` и не меняет ни один контракт, потребляемый `apps/dashboard` или другими пакетами монорепо (`policy-engine`, `signal-openstack`, `config`). Поиск по всему репозиторию на коммите головы (`git grep -n '<symbol>' HEAD`) для каждого нового экспорта/tRPC-ключа/типа показал:

- `storage.ceph.cors.{get,set,delete}` — потребитель вне `Ceph/Buckets/*` только один: `useBucketInfo.ts:95`, который сам является частью этой же фичи и обновлён этим же PR. В `apps/dashboard` и в `policies/storage.json` ссылок на CORS нет (как и у `bucketPolicy`/`versioning` — это не регрессия PR, а существующий паттерн: `permissionRouter.ts`'s `STORAGE_MAPPINGS` не покрывает ни одну из «продвинутых» bucket-level фич).
- Все новые React-компоненты/хуки (`BucketDetailTabs`, `CorsRuleForm`, `CorsRuleModal`, `CorsRulesTab`, `CorsRulesTable`, `TagInput`, три Delete-модалки) — без единого потребителя за пределами своей директории. `CephCorsRules` (реэкспорт `CorsRulesTab`) используется ровно один раз, в `objects/index.tsx`.
- Новые типы/схемы (`CorsRule`, `CorsRuleRead`, `CorsConfiguration`, `CorsAllowedMethod`, `GetCorsOutput`, Zod-схемы) — потребляются исключительно внутри `corsRouter.ts` и клиентского кода этой же фичи; `CorsConfiguration`/`CorsAllowedMethod` экспортированы, но пока нигде не используются (мёртвые, но безвредные экспорты).
- Единственная сквозная зависимость — `mockContext.ts`, общий для 7 тестовых файлов Ceph-роутеров; изменение обратно совместимое (добавлены опциональные поля под реальную форму контекста).

Старая модалка-реализация (июльская версия — `CorsModal.tsx`, `CorsRulesViewer.tsx`) удалена полностью и без следов: `git grep -n '\bCorsModal\b' HEAD` (с границей слова, за исключением совпадений `DeleteCorsModal`) и `git grep -n 'CorsRulesViewer' HEAD` дают **ноль совпадений** — ни в коде, ни в тестах, ни в доках не осталось ссылок на удалённые файлы. Единственный «остаток» переезда с модалки на таб — не мёртвая ссылка, а мёртвое состояние: второй недостижимый экземпляр `DeleteCorsModal` внутри `CorsRulesTab` (см. выше).

## Ревью

**Текущий статус: 0 подтверждённых (≥80) находок открыто.** Все 4 находки, дошедшие до этой стадии из предыдущих версий отчёта (changeset, хелптекст Rule ID, `isMutating`, мёртвый `DeleteCorsModal` в табе), закрыты коммитами `4f16ad3`/`356618c`/`81598e1`/`8cbd4a5` — каждая проверена построчно против текущего кода, не по тексту коммитов, подробности в блоке «Раунд 4» выше. Оставшиеся два наблюдения этого раунда (тест на `isMutating`, не проверяющий заявленное; узкое слепое окно в `onMutatingChange` во время freshness-check) получили 75 и 70 при независимом confidence-scoring — ниже порога, приведены в «Раунд 4» для полноты, не считаются подтверждёнными находками.

Также остаются не набравшими порог (без изменений с прошлой версии, код не трогали, не входили в объём последнего раунда): отсутствие freshness-check на ветке добавления нового правила в `CorsRuleModal` (75, «Что изменилось» выше), отсутствие Lingui-обёрток в `TagInput.tsx` (75), мёртвая ветка `NoSuchCORSConfiguration` в error-маппере (65) и ещё несколько пунктов 25-60 из второй версии отчёта — если у PR будет ещё один раунд ревью, стоит держать их в поле зрения, но сейчас поднимать их в отдельные фикс-промпты нет оснований (низкая практическая значимость по независимой оценке).

---
Проанализировано: 11.08.2026 · коммит `8cbd4a5` (предыдущие версии отчёта — коммиты `1f7a0d9`, `834f993`, `5d8fb2d`)
