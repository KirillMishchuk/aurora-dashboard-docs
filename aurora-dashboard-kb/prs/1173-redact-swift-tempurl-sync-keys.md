# PR #1173: fix(core): redact Swift TempURL and sync keys from metadata responses

**Автор:** TilmanHaupt · **Статус:** смержен 14.08.2026 (коммит `2c7bd0e`; открыт 12.08.2026)
**Ветки:** `til-sec-4` → `main` · **Файлов:** 10 (+224/-47)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1173

> Сеть до GitHub API из этой сессии заблокирована (тот же 403, что и раньше), `gh` недоступен на устройстве пользователя (нет сети у `device_bash`). PR склонирован анонимно по `git` в облачном контейнере (`refs/pull/1173/head`, публичный репозиторий, аутентификация не нужна) — весь код, диффы и история проверены по этому клону, а не по HTML-странице PR. Метаданные, которые нельзя достать через `git` (автор, статус, даты создания/обновления, ревью-боты), взяты через рендер страницы PR; там же попалась и явная галлюцинация (см. ниже) — не всё оттуда взято на веру.

## Что сделано

Свежая цепочка security-фиксов в `packages/aurora/src/server/Storage` (SSRF в Swift #1148, SSRF в пагинации Glance #1144, path traversal в OpenStack-роутах #1153 — все за последнюю неделю) продолжается этим PR: `getAccountMetadata`/`getContainerMetadata` в Swift-роутере до сих пор отдавали клиенту сырые секреты — `X-Account-Meta-Temp-URL-Key(-2)` и `X-Container-Meta-Temp-URL-Key(-2)`/`X-Container-Sync-Key` — прямо в теле ответа как обычные строковые поля `tempUrlKey`/`tempUrlKey2`/`syncKey`. Оба секрета дают реальный доступ без аутентификации: TempURL-ключ подписывает временные ссылки на объекты, sync-ключ разрешает межаккаунтную синхронизацию контейнера. Эти поля появились в `swiftHelpers.ts`/`swift.ts` 29.06.2026 (коммит `c67430d`, когда Swift-модуль добрался в репозиторий целиком) и с тех пор ни разу не трогались — PR исправляет утечку, просуществовавшую примерно 6.5 недель.

Решение — заменить сырые значения на булевы флаги присутствия (`hasTempUrlKey`, `hasSyncKey`), вычисляемые новым модулем `secretHelpers.ts`, и убрать секретные строковые поля из Zod-схем ответа. **Реализация закрывает утечку только частично** — см. «Ревью»: ключ аккаунта всё равно протекает через общий `metadata`-словарь, потому что `parseAccountInfo` (в отличие от `parseContainerInfo`) не фильтрует `temp-url-*` из generic-цикла по `x-account-meta-*`.

## Как это реализовано

### Новый модуль `secretHelpers.ts` — детектор и редактор секретных заголовков

`packages/aurora/src/server/helpers/secretHelpers.ts` (53 строки, новый файл) — три экспорта:

```ts
// secretHelpers.ts:5-14
const REDACTED_HEADERS = [
  "x-auth-token",
  "x-subject-token",
  "x-container-sync-key",
  "x-container-meta-temp-url-key",
  "x-container-meta-temp-url-key-2",
  "x-account-meta-temp-url-key",
  "x-account-meta-temp-url-key-2",
  "authorization",
] as const
```

`isSecretHeader()` (`secretHelpers.ts:19-21`) сверяет имя заголовка (в нижнем регистре) с этим списком — но нигде не вызывается за пределами собственного теста (см. «Ревью», не самостоятельная находка, просто контекст). Фактическую работу делают `redactAccountSecrets`/`redactContainerSecrets` (`secretHelpers.ts:30-53`) — каждая просто проверяет **присутствие** нужных заголовков через `Headers.has()`:

```ts
// secretHelpers.ts:30-36
export function redactAccountSecrets(headers: Headers): {
  hasTempUrlKey: boolean
} {
  return {
    hasTempUrlKey: headers.has("x-account-meta-temp-url-key") || headers.has("x-account-meta-temp-url-key-2"),
  }
}
```

### `swiftHelpers.ts` — секретные поля убраны из верхнего уровня ответа

`parseAccountInfo`/`parseContainerInfo` (`swiftHelpers.ts:97-211`) раньше явно копировали `tempUrlKey`/`tempUrlKey2`/`syncKey` из заголовков в возвращаемый объект по truthy-проверке значения; теперь на их месте — вызов нового редактора:

```ts
// swiftHelpers.ts:123-129 (parseAccountInfo)
// Security: Redact secret keys, return only presence flags
const secrets = redactAccountSecrets(headers)

return {
  ...accountInfo,
  ...secrets,
} as AccountInfo
```

Симметрично для контейнера (`swiftHelpers.ts:204-210`, `redactContainerSecrets`). На этом уровне (верхнеуровневые поля `tempUrlKey`/`tempUrlKey2`/`syncKey`) секрет действительно перестаёт возвращаться — подтверждено и по коду, и по новым тестам (`swiftHelpers.test.ts`: `expect(result).not.toHaveProperty("tempUrlKey")`).

### `types/swift.ts` — схемы ответа ужесточены

`accountInfoSchema`/`containerInfoSchema` (`swift.ts:136-143`, `189-205`) лишились опциональных строковых полей секретов и получили **обязательные** (не `.optional()`) булевы флаги:

```ts
// swift.ts:199-205 (containerInfoSchema)
  syncTo: z.string().optional(),
  // Security: Return only presence flags, not secret values
  hasTempUrlKey: z.boolean(),
  hasSyncKey: z.boolean(),
})
```

Остальные Zod-схемы, где `tempUrlKey`/`tempUrlKey2` встречаются (`updateAccountMetadataInputSchema:169-170`, `createContainerInputSchema:240-241`, `updateContainerMetadataInputSchema:256-257`), не тронуты — это **input**-схемы (клиент передаёт значение, чтобы *установить* ключ через `updateAccountMetadata`/`updateContainerMetadata`), а не response-схемы; они не являются частью утечки и правомерно не меняются этим PR.

### Тесты — обновлены фикстуры, но не разоблачили дырку в account-metadata

`swiftHelpers.test.ts`, `swift.test.ts`, `swiftRouter.test.ts` и два клиентских `*.test.tsx` (только фикстуры, без изменений в самих компонентах — `ContainerLimitsTooltip.tsx`/`EditContainerMetadataModal.tsx` этот PR не трогает, их тесты обновлены исключительно потому, что `hasTempUrlKey`/`hasSyncKey` стали обязательными полями типа) добавляют проверки вида `expect(result).not.toHaveProperty("tempUrlKey")` и `expect(result.hasTempUrlKey).toBe(true)`. Ни один новый тест не проверяет **содержимое `result.metadata`** при выставленных temp-url-заголовках — именно это и позволило утечке через `metadata` остаться незамеченной (см. «Ревью», находка №1).

## Что затронуло

Изменение локализовано внутри `packages/aurora/src/server/Storage` + новый `packages/aurora/src/server/helpers/secretHelpers.ts`; блast-radius проверен по каждому изменённому публичному имени по всему монорепо (`packages/*`, `apps/*`):

- `AccountInfo`/`ContainerInfo` (типы) — единственные производители — сами `parseAccountInfo`/`parseContainerInfo` (по одному вызову каждой в `swiftRouter.ts:197` и `:372`), которые теперь всегда проставляют `hasTempUrlKey`/`hasSyncKey`. Единственные потребители полного (не `Partial<>`) типа как литерала — 4 тестовых файла, и все 4 обновлены этим PR (`ContainerLimitsTooltip.test.tsx`, `EditContainerMetadataModal.test.tsx`, `swiftRouter.test.ts`, `swift.test.ts`). `ManageContainerAccessModal.test.tsx` тоже импортирует `ContainerInfo`, но только как `Partial<ContainerInfo>` — новые обязательные поля ему не нужны, ничего не ломает.
- Клиентский код (`packages/aurora/src/client/**`, `apps/dashboard/**`) — ни один некод-тестовый файл не читает `tempUrlKey`/`tempUrlKey2`/`syncKey`/`hasTempUrlKey`/`hasSyncKey` напрямую; UI не показывал и не показывает эти секреты, так что для конечного экрана поведение не меняется, только контракт API под ним.
- `isSecretHeader` — экспортирована, но не используется никем, кроме собственного теста; мёртвый код, не влияет на поведение.
- `.changeset/fix-swift-secret-exposure.md` — задаёт `"@cobaltcore-dev/aurora": minor`. Реальный релизный механизм — Changesets (`.github/workflows/release.yaml` → `changesets/action`, читает версию строго из frontmatter файла changeset'а), а не conventional-commits/semantic-release, на который ссылается `docs/semantic_release.md` (тот файл описывает механизм, которого в `.github/workflows` физически нет — устаревшая документация, отдельный вопрос вне этого PR). Значит формулировка "BREAKING CHANGE" в теле PR **не долетает** до фактического changelog/version bump — его читает только changeset-файл, а тот говорит "minor" (см. «Ревью», находка №2).

## Ревью

**Две находки набрали ≥80 confidence.**

- **[100/100] Секрет всё равно утекает через `metadata` в ответе аккаунта — редакция не полная.** `parseAccountInfo` (`swiftHelpers.ts:104-111`) собирает `metadata` общим циклом по всем заголовкам с префиксом `x-account-meta-`, без каких-либо исключений:
  ```ts
  // swiftHelpers.ts:104-111
  const metadata: Record<string, string> = {}
  headers.forEach((value, key) => {
    if (key.toLowerCase().startsWith("x-account-meta-")) {
      const metaKey = key.substring(15) // Remove "x-account-meta-" prefix
      metadata[metaKey] = value
    }
  })
  ```
  `x-account-meta-temp-url-key`/`-key-2` подходят под этот префикс — они окажутся в `metadata["temp-url-key"]`/`metadata["temp-url-key-2"]` **с настоящим секретным значением**, несмотря на то, что верхнеуровневое поле `tempUrlKey` теперь корректно убрано. `accountMetadataSchema` — свободный `z.record(string, string)`, ничего не отфильтрует. `getAccountMetadata` (`swiftRouter.ts:197`) возвращает этот объект клиенту без изменений. Это ровно та же категория утечки, которую PR заявляет закрытой — просто через другое поле. Для сравнения, `parseContainerInfo` (тот же файл, `swiftHelpers.ts:148`) делает такую фильтрацию правильно и давно (код не тронут этим PR): `if (!metaKey.startsWith("quota-") && !metaKey.startsWith("temp-url-") && !metaKey.startsWith("access-control-"))`. Account-версия такого исключения никогда не имела — этот PR был шансом добавить его туда же, но не добавил. Ни один новый тест не проверяет `result.metadata` при выставленных temp-url-заголовках (все новые ассершены проверяют только верхнеуровневые `tempUrlKey`/`hasTempUrlKey`), поэтому CI это не поймает. 100/100 — не гипотеза, а прямое чтение кода: для любого аккаунта с настроенным TempURL-ключом секрет придёт в каждом ответе `getAccountMetadata`, только по другому пути.
- **[85/100] Changeset помечен как `minor`, хотя сам PR называет изменение breaking.** Описание PR прямо говорит: `"BREAKING CHANGE: accountInfoSchema and containerInfoSchema response structure changed - removed tempUrlKey, tempUrlKey2, syncKey fields, added hasTempUrlKey and hasSyncKey boolean flags"` — и это действительно так: `hasTempUrlKey`/`hasSyncKey` в обеих схемах объявлены обязательными (`z.boolean()`, не `.optional()`), а не аддитивным расширением. При этом `.changeset/fix-swift-secret-exposure.md` объявляет бамп `minor`. Релиз идёт через Changesets, который читает версию только из frontmatter changeset-файла (`release.yaml` → `changesets/action`) — текст "BREAKING CHANGE" в теле PR никак не попадает в итоговый CHANGELOG или версию пакета. Потребитель `@cobaltcore-dev/aurora` с диапазоном `^0.23.1` получит это как обычный "безопасный" minor-апдейт: TS-код, обращавшийся к `.tempUrlKey`/`.tempUrlKey2`/`.syncKey` на response-типах, перестанет собираться без предупреждения о breaking-релизе, а слабо типизированный потребитель тихо получит `undefined` в этих местах во время выполнения. `CLAUDE.md` отдельно подчёркивает, что "commit type/scope directly affects the next version bump, so get it right" — тот же принцип применим к severity changeset'а. Не 100, потому что "правильный" bump для чисто внутреннего response-контракта библиотеки — вопрос конвенции проекта, а не жёстко проверяемый факт, но риск для потребителей пакета реален и легко исправим (сменить `minor` → `major` в changeset).

Ниже — то, что проверено и не набрало порог:

- **[50/100, отклонено как nitpick] `redactAccountSecrets`/`redactContainerSecrets` проверяют присутствие заголовка (`Headers.has()`), а не истинность значения — было наоборот.** До PR код делал `const tempUrlKey = headers.get(...); if (tempUrlKey) {...}` — falsy-проверка значения, пустая строка не считалась ключом. Новый код (`secretHelpers.ts:34`, `:50-51`) использует `.has()`, который вернёт `true` даже для заголовка с пустым значением. Если Swift когда-либо отдаёт этот заголовок пустым (а не просто не отдаёт его, что для OpenStack Swift обычное поведение при отсутствии/удалении ключа), `hasTempUrlKey`/`hasSyncKey` соврут клиенту, что ключ настроен. Реальность такого ответа от Swift не подтверждена — отклонено как маловероятный edge case, а не подтверждённый баг.
- **[25/100, отклонено] `isSecretHeader` экспортирована, но не используется нигде за пределами собственного теста.** Похоже на недостроенный generic-путь санитизации, который не подключили ни к одному реальному месту, где заголовки уходят в лог или в ответ — проверено: логирования сырых Swift-заголовков или объектов `AccountInfo`/`ContainerInfo` в `packages/aurora/src/server` не найдено. Мёртвый код, не самостоятельная угроза; отклонено как general code-quality опасение, не требуемое `CLAUDE.md` явно.
- **[0/100, отклонено] Ceph/S3-паритет.** Проверено: EC2-креды Ceph (`ec2CredentialRouter.ts`) уже возвращают secret только один раз при создании (`list` использует бессекретную схему, с явным комментарием в коде), presigned URL — производный, время-ограниченный артефакт, не персистентный секрет. Паритетного разрыва с этим PR нет, дополнительный фикс на стороне Ceph не требуется.

---
Проанализировано: 13.08.2026 · коммит `a278e3f`
