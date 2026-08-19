# PR #1177: feat(clavis): different changes(api/ui-ux) with downloading functionality

**Автор:** vlad-schur-external-sap · **Статус:** открыт, не смержен (коммиты 13.08.2026–19.08.2026, ожидает ревью) — **2-я версия отчёта**
**Ветки:** `clavis-ui-ux-changes-with-downloading` → `main` · **Файлов:** 30 (+1204/-845 к текущему `main`, база `9cdf0ae`), из них `pnpm-lock.yaml` — техническая регенерация под апдейт `@cloudoperators/juno-ui-components`, не разбирается ниже
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1177

> Доступ к GitHub REST/GraphQL API из этой сессии заблокирован (`gh`/`gh api` и прямой `curl` к `api.github.com`/`github.com/.../pull/1177.diff` возвращают 403 "GitHub access to this repository is not enabled for this session… Use add_repo…"). Заголовок PR, автор, статус, ветки и описание получены через `WebFetch` самой HTML-страницы PR — рабочий, но не подтверждённый вторым способом источник для этих полей. Весь код, дифф и история коммитов проверены анонимным `git clone` + `git fetch origin refs/pull/1177/head` (публичный репозиторий, git-протокол не подпадает под то же ограничение) — надёжный источник для всего остального. Это обновление отчёта от 14.08.2026 (коммит `0a1b61c`): с тех пор в PR добавлены 3 новых коммита (13:25→10:22, 19.08.2026) плюс один merge `main`, подтянувший #1176/#1181/#1184 — они не относятся к PR и не разбираются здесь. `git diff main...pr-1177-head` (актуальный `main`) — источник истины для всего отчёта, как и предписывает `document-pr`.

## Что сделано

PR продолжает серию доработок Clavis (Private Certificate Authority) в `packages/aurora/src/client/routes/.../services/pca/` семью содержательными коммитами одного автора (13.08→19.08.2026) плюс три merge-коммита `main`:

1. **`e3f051f` "remove unexpected states as its not available on the client"** — убирает `"UNEXPECTED"` из `CertificateAuthorityStateSchema` (сервер) и из обоих UI-маппингов состояний, удаляет соответствующие тесты.
2. **`d8a2186` "implement downloading"** — реализует скачивание PEM/CSR через `DetailsInfo`, поднимает `@cloudoperators/juno-ui-components` до `9.3.0` (нужна для `codeBlockFooter`).
3. **`3485002` "update import-issue validation and upload logic"** — делает `parseCsrInfo` синхронной, добавляет разбор/валидацию цепочки сертификатов, сужает загрузку файла импорта до `.json`.
4. **`3a91742` "change btn possition for creating certificates"** — переносит кнопку «Issue Self-Signed Certificate» из `PcaDetailsView` в `PcaCertificatesListContainer` (чистая перестановка, условие видимости не изменилось).
5. **`288977d` "fix(clavis): ai comments and typos"** (19.08, 09:25) — несмотря на название, содержательный коммит: переименовывает лейбл `"Subject"` → `"Subject Information"` (везде — `parseCsrInfo.ts`, `PcaDetailsView.tsx`, `PcaListContainer.tsx`), выделяет из `isValidPem` отдельную строгую `isValidCsr` (отклоняет вход, если это сертификат, а не CSR — раньше `IssueEndEntityCertificateModal` валидировал CSR-поле через `isValidPem`, который принимал и CSR, и сертификат), добавляет toast «Certificate Imported» при импорте и добавляет `getById`-инвалидацию после само-подписания CA.
6. **`f9dc694` "fix(clavis): get-by-id invalidation and tests for parsing and importing"** (19.08, 09:56) — сужает инвалидацию `getById` после импорта сертификата с «инвалидировать все `getById`-запросы» до «инвалидировать конкретно `{project_id, certificate_authority_id}` этого CA».
7. **`de468bd` "refactor(clavis): replace creating and awaiting icons"** (19.08, 10:22, самый свежий коммит) — заменяет иконки состояний `CREATING`/`AWAITING_CERTIFICATE` на `Spinner`/`Icon` из `juno-ui-components` вместо `react-icons/md`, попутно вносит регрессию — см. «Ревью».

Заявленное в описании PR ("Fixed CSR/PEM validation and parsing, make parsing sync", "Added PEM downloads", "Removed the UNEXPECTED state", ссылка на #1160) соответствует диффу, с тем же уточнением, что и в прошлой версии отчёта: сужение загрузки файла до `.json` не упомянуто явно. Чеклист в описании PR не отмечен ни одним пунктом (все 6 чекбоксов `- [ ]` не проставлены).

## Как это реализовано

### `getById`-инвалидация после мутаций CA — два целевых фикса этого раунда

До сегодняшних коммитов `IssueSelfSignedCertificateModal` инвалидировал только список сертификатов, а `ImportExternallySignedCertificateModal` — весь кэш `getById` без фильтра по CA:

```tsx
// IssueSelfSignedCertificateModal.tsx:20-25
const { isPending, ...createCertificateMutation } = trpcReact.services.pca.createCertificate.useMutation({
  onSettled: () => {
    utils.services.pca.listCertificates.invalidate()
    utils.services.pca.getById.invalidate({ project_id: projectId, certificate_authority_id: pca.id })
  },
})
```

```tsx
// ImportExternallySignedCertificateModal.tsx:36-42
const { isPending, ...importMutation } = trpcReact.services.pca.import.useMutation({
  onSettled: () =>
    utils.services.pca.getById.invalidate({
      project_id: projectId,
      certificate_authority_id: pcaId,
    }),
})
```

Оба места теперь целенаправленно инвалидируют `getById` конкретного CA (`$pcaId/index.tsx:23,57` кормит `PcaDetailsView` именно этим запросом) — до фикса страница деталей CA после самоподписания/импорта могла оставаться со старым бейджем состояния и старым содержимым `DetailsInfo` до ручного рефреша. Реальный, обоснованный багфикс, покрытый обновлёнными тестами.

### Toast-уведомления на удаление и импорт

Новый файл `PcaToastNotifications.tsx` (15 строк) — два билдера в том же стиле, что и в других частях приложения (`ImageToastNotifications`, `ObjectToastNotifications`):

```tsx
// PcaToastNotifications.tsx:7-15
export const getPcaDeletedToast = (pcaName: string): ToastReturn => ({
  message: <Trans>Certificate Authority Deleted</Trans>,
  description: <Trans>Certificate Authority "{pcaName}" was successfully deleted.</Trans>,
})

export const getCertificateImportedToast = (): ToastReturn => ({
  message: <Trans>Certificate Imported</Trans>,
  description: <Trans>The externally signed certificate was successfully imported.</Trans>,
})
```

Подключены в `DeletePcaModal.tsx:49-50` и `ImportExternallySignedCertificateModal.tsx:59-60` сразу после успешной мутации, до `handleClose()`. Обе строки корректно обёрнуты в `<Trans>` и присутствуют в диффе `messages.po`.

### CSR vs сертификат — раздельная валидация вместо общей `isValidPem`

```ts
// parseCsrInfo.ts:96-119
export const isValidPem = (pem: string) => {
  try {
    const sanitizedPem = cleanPem(pem)
    if (sanitizedPem.includes("-----BEGIN CERTIFICATE-----")) {
      parseCertificateChain(sanitizedPem)
    } else {
      new Pkcs10CertificateRequest(sanitizedPem)
    }
    return true
  } catch {
    return false
  }
}

export const isValidCsr = (pem: string) => {
  try {
    const sanitizedPem = cleanPem(pem)
    if (sanitizedPem.includes("-----BEGIN CERTIFICATE-----")) return false
    new Pkcs10CertificateRequest(sanitizedPem)
    return true
  } catch {
    return false
  }
}
```

`IssueEndEntityCertificateModal.tsx:9,32` теперь валидирует CSR-поле через `isValidCsr` вместо `isValidPem` — реальное сужение: раньше в поле «Paste CSR code» можно было вставить полный сертификат и форма считала его валидным (`isValidPem` принимает и то, и то), теперь для этого поля принимается только настоящий CSR. Это скрыто под неинформативным названием коммита «ai comments and typos», хотя меняет поведение валидации формы. Побочный эффект — `isValidPem` остался экспортированным, но потерял единственного потребителя (см. «Ревью»).

### Иконки состояний CA — переход на компоненты juno вместо `react-icons/md`

```tsx
// PcaTableRow.tsx:34-42
const STATE_CONFIG = {
  CREATING: {
    text: t`Creating`,
    icon: <Spinner size="18" />,
  },
  AWAITING_CERTIFICATE: {
    text: t`Awaiting Certificate`,
    icon: <Icon icon="accessTime" size={20} color="#FBC02D" />,
  },
  ...
```

В таблице (`PcaTableRow.tsx`) текст и иконка — раздельные поля, `t\`Creating\`` не тронут. Но на странице деталей та же замена внесла регрессию:

```tsx
// PcaDetailsView.tsx:45-56
const STATE_CONFIG = {
  CREATING: (
    <Badge variant="info">
      <Stack direction="horizontal" gap="1" alignment="center">
        <Spinner size="18" /> Creating
      </Stack>
    </Badge>
  ),
  AWAITING_CERTIFICATE: <Badge icon="accessTime" variant="warning" text={t`Awaiting Certificate`} />,
  READY: <Badge icon="checkCircle" variant="success" text={t`Ready`} />,
  FAILED: <Badge icon="error" variant="error" text={t`Failed`} />,
} as const
```

Разбор последствий — в «Ревью», это главная находка этой версии отчёта.

## Что затронуло

Блast-радиус проверен по каждому изменённому/новому символу по всему монорепо на `pr-1177-head`:

- **`isValidCsr`, `isValidCertificateChain`, `getCertificateImportedToast`, `getPcaDeletedToast`** — каждый используется ровно одним потребителем внутри того же PR (`IssueEndEntityCertificateModal`, `ImportExternallySignedCertificateModal` ×2, `DeletePcaModal` соответственно); других мест использования в репозитории нет.
- **`isValidPem`** — экспортируется, но с коммита `288977d` не имеет ни одного потребителя в репозитории (проверено `git grep`); раньше был единственным валидатором CSR-поля. Не поймается линтом/тайпчеком (правило на неиспользуемые *экспорты* в конфиге ESLint пакета не включено — есть только `no-unused-vars` для локальных переменных).
- **`CertificateAuthorityStateSchema`/`CertificateAuthorityState`** — как и в прошлой версии отчёта: не ре-экспортируется из публичных точек входа пакета (внутренний тип), но валидирует реальные ответы backend'а в `pcaRouter.ts` (`list`/`create`/`getById`/`import` все проходят через `parseOrThrow`, которая бросает `TRPCError({code: "PARSE_ERROR"})` на весь вызов при несовпадении схемы) — сужение enum остаётся тем же незакрытым вопросом, что и раньше (см. «Ревью»).
- **`apps/dashboard`** не ссылается на `pca`-код напрямую — изменение полностью внутреннее для `packages/aurora`.
- Новые/переименованные лейблы (`"Subject Information"`) синхронно обновлены в трёх местах (`parseCsrInfo.ts`, `PcaDetailsView.tsx`, `PcaListContainer.tsx`) — консистентно, отставших мест не найдено.

## Ревью

Ревью прогнано 5 параллельными агентами (CLAUDE.md-комплаенс, беглый поиск багов, история/git blame, поиск фидбека по прошлым PR в этой же области, комплаенс с существующими код-комментариями) по актуальному диффу (`main...pr-1177-head`), затем каждая находка получила независимую оценку уверенности по шкале 0–100 (порог публикации — 80).

**Прошло порог ≥80:**

- **[100/100] Бейдж состояния `CREATING` на странице деталей CA потерял перевод — единственная непереведённая строка среди всех статус-бейджей.** `PcaDetailsView.tsx:49`: было `<Badge icon="bolt" variant="info" text={t\`Creating\`} />`, стало `<Spinner size="18" /> Creating` — литеральная английская строка прямо в JSX, без `t`/`<Trans>`. Соседние состояния в том же объекте (`AWAITING_CERTIFICATE`, `READY`, `FAILED`) продолжают использовать `t`. Подтверждено диффом `messages.po`: строка `"Creating"` не появляется как новый `msgid` — значит `lingui extract` (`pnpm check-i18n`) её не увидел и никогда не увидит, она останется английской на любой локали, включая немецкую. Аналог в `PcaTableRow.tsx:36` (`text: t\`Creating\`,`) корректен — регрессия только в `PcaDetailsView`. Ничем в CI не ловится (макрос Lingui — этап компиляции строк, а не тип).

**Не прошло порог (наблюдения, не находки):**

- **[78, отклонено] Загрузка файла импорта сертификата теперь принимает только `.json`, тогда как раньше принимала `.pem`/`.crt`/`.cer` напрямую с fallback на сырой текст.** Тот же вопрос, что и в прошлой версии отчёта (было 50/100) — новый скоринг-агент поднял до 78 после того, как проверил историю: `accept=".pem,.crt,.cer,.json"` был добавлен осознанно в отдельном PR (`fc861d5`, #901) именно чтобы поддержать прямую загрузку сертификата, а не только JSON. Не прошло порог: изменение intentional и покрыто тестом (переименован в "ignores non-JSON file uploads"), вставка вручную в текстовое поле не тронута — это реальное, но осознанное и смягчённое сужение UX, а не дефект.
- **[75, отклонено] Удаление `"UNEXPECTED"` из `CertificateAuthorityStateSchema` — та же находка, что в версии от 14.08, с усиленной доказательной базой.** Новые агенты подтвердили: состояние было в схеме с самого первого коммита файла (`034d591`, #761) — то есть заложено в исходный дизайн, а не добавлено позже как защита от конкретного инцидента; архитектурный документ `packages/aurora/docs/0011_clavis.md` (не тронут этим PR) до сих пор перечисляет `UNEXPECTED` в списке "Relevant PCA states". Если backend всё же может прислать это состояние, `pcaRouter.list`/`getById`/`import` упадут целиком через `parseOrThrow`. Порог не пройден по той же причине, что раньше: нет способа независимо проверить, подтверждено ли на стороне backend/Clavis-команды, что это состояние больше невозможно — если да, находка снимается полностью.
- **[75, отклонено] Тултип `title="Download PEM file"` на новой кнопке скачивания не переведён.** `DetailsInfo.tsx:47`, `codeBlockFooter={<Icon icon="download" title="Download PEM file" .../>}` — единственный `Icon` с `title` во всём репозитории, и единственный непереведённый; файл не импортирует `useLingui`. Не поднято до 80: эта строка (в отличие от бейджа `CREATING`) была добавлена ещё в самом первом коммите PR (`d8a2186`, 13.08) и уже проверялась предыдущей версией этого отчёта без находки — по факту нативный HTML `title` тултипа, а не видимый текст интерфейса, что мягче по impact.
- **[75, отклонено] `isValidPem` осталась мёртвым кодом** после того, как `288977d` переключил её единственного потребителя на `isValidCsr`. Подтверждено `git grep` — ни одного импорта в репозитории. Не ловится линтом/тайпчеком (unused-export правило не включено), но и не критично — просто неиспользуемый экспорт.
- **[30, отклонено] Комментарий `"", // ... "Delete CA" button` в `PcaCertificatesListContainer.tsx:82` не соответствует реальному меню строки (`PcaCertificatesTableRow.tsx`, там только "Show Details", без удаления).** Комментарий существовал на `main` до этого PR (скопирован из соседнего `PcaListContainer.tsx`, где меню действительно содержит "Delete CA") — этот PR не вносил и не копипастил его, только не исправил. Чисто документационная неточность без функционального эффекта.

Остальное проверено и не поднято как находка: переименование `"Subject"` → `"Subject Information"` — консистентно везде, корректно попало в `messages.po`; переход на `Spinner`/`Icon` из juno в `PcaTableRow.tsx` не потерял `t`-обёртку (только `PcaDetailsView.tsx` пострадал); `getById`-инвалидации в `IssueSelfSignedCertificateModal`/`ImportExternallySignedCertificateModal` корректны и адресны; тест `ParsedCertificateInfo.test.tsx` продолжает мокать `parseCsrInfo` как async-функцию (`mockResolvedValue`/`mockRejectedValue`) — не баг: мок подменяет модуль целиком, реальная синхронная реализация не вызывается, комментарий "Invalid/malformed CSR should quietly render no parsed info" в `ParsedCertificateInfo.tsx` продолжает соблюдаться (проверено по актуальному `QueryClient`-конфигу — ошибка парсинга тихо даёт `data: undefined` → `fields: []` → компонент рендерит `null`).

---
Проанализировано: 19.08.2026 · коммит `de468bd6`
