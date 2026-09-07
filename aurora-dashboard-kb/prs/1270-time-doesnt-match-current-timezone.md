# PR #1270: fix(aurora): time doesn't match current timezone (#1236)

**Автор:** mark-karnaukh-extern-sap · **Статус:** 03.09.2026 (открыт, не смержен)
**Ветки:** `mark-fix-parse-timestamps-as-utc` → `main` · **Файлов:** 8 (+159/-26)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1270

## Что сделано

Swift в JSON-листингах контейнеров и объектов отдаёт `last_modified` как ISO 8601 **без указания зоны** — `"2024-03-01T08:00:00.000000"` (баг Swift #1169287). По ISO 8601 date-time без зоны трактуется как **локальное** время, поэтому `new Date("...T08:00:00").toLocaleString()` не делал UTC→local конверсию и показывал время, сдвинутое на смещение зоны зрителя (issue #1236, репортер guoda-puidokaite).

PR вводит общий хелпер `@/client/utils/formatSwiftDate.ts` с двумя функциями — `parseSwiftDate` (нормализует зоно-безразмерный timestamp к UTC, дописывая `Z`) и `formatSwiftDate` (обёртка над `toLocaleString`, возвращающая `null` на невалидном входе, чтобы вызывающий сам выбирал fallback) — и переводит на него весь Swift-код, который трогает `last_modified`: две таблицы (контейнеры, объекты), два компаратора сортировки и модалку метаданных объекта. Добавлен зоно-независимый unit-тест и changeset (`patch` для `@cobaltcore-dev/aurora`). Ceph не затронут — он отдаёт timestamps с `Z`, и хелпер пропускает такие значения без изменений.

**Важно:** описание PR перечисляет в разделе «Changes» только хелпер, две таблицы и тест. Фактический диф шире — в него также входят оба компаратора сортировки (`Containers/index.tsx`, `Objects/index.tsx`) и `EditObjectMetadataModal.tsx`. Эти три места добавлены позже, в ответ на замечание Copilot'а, и именно в модалке живёт регрессия из раздела «Ревью». Читать диф, не описание.

## Как это реализовано

Ядро — эвристика «есть ли у строки зона» в `formatSwiftDate.ts`:

```ts
const HAS_ZONE = /(Z|[+-]\d{2}:?\d{2})$/

export const parseSwiftDate = (value: string | null | undefined): Date | null => {
  if (!value) return null
  const trimmed = value.trim()
  if (!trimmed) return null

  // Only a full date-time (has a "T") that lacks a zone needs normalizing to
  // UTC. A date-only string ("2024-03-01") is already parsed as UTC by the
  // engine, and appending "Z" to it would make it invalid.
  const needsUtc = trimmed.includes("T") && !HAS_ZONE.test(trimmed)
  const normalized = needsUtc ? `${trimmed}Z` : trimmed

  const date = new Date(normalized)
  return Number.isNaN(date.getTime()) ? null : date
}
```
— `packages/aurora/src/client/utils/formatSwiftDate.ts:21-40`

`formatSwiftDate` (там же, `:50-57`) — тонкая обёртка: `parseSwiftDate` плюс `date.toLocaleString(locales, options)`, возвращает `null` вместо строки-заглушки.

**Таблицы.** Обе таблицы имели свой локальный `formatDate`; оба удалены, вместо них — вызов хелпера с прежним fallback'ом каждого места:

```tsx
<DataGridCell>{formatSwiftDate(container.last_modified) ?? t`N/A`}</DataGridCell>
```
— `.../Swift/Containers/ContainerTableView.tsx:232` (аналогично `.../Swift/Objects/ObjectsTableView.tsx:409-410`, где fallback — литеральный `"—"`)

**Сортировка.** Оба компаратора раньше считали `new Date(a.last_modified).getTime() - new Date(b.last_modified).getTime()`, то есть сравнивали неверно распарсенные инстансы (на переходах DST это давало реально неверный порядок). Новая версия в контейнерах заодно чинит транзитивность на пропущенных значениях:

```ts
case "last_modified": {
  // Both missing → equal (keeps the comparator transitive); exactly one
  // missing → push it to the end.
  if (!a.last_modified && !b.last_modified) return 0
  if (!a.last_modified || !b.last_modified) {
    return a.last_modified ? -1 : 1
  }
  // #1236: Swift listing timestamps are UTC without a "Z" — parse them as
  // UTC so the ordering is correct (matters near DST boundaries). If a
  // (non-empty) value can't be parsed, treat the pair as equal so the
  // order is left untouched (matches the old NaN behaviour).
  const at = parseSwiftDate(a.last_modified)?.getTime()
  const bt = parseSwiftDate(b.last_modified)?.getTime()
  comparison = at == null || bt == null ? 0 : at - bt
  break
}
```
— `.../Swift/Containers/index.tsx:197-212` (то же в `.../Swift/Objects/index.tsx:354-366`)

Замечание в комментарии про «matches the old NaN behaviour» корректно по существу: старый код возвращал из компаратора `NaN`, а спецификация `Array.prototype.sort` приводит `NaN`-результат к `+0` — то есть к тому же «считать пару равной». Проверено прогоном на смешанных массивах: поведение сортировки идентично.

**Модалка метаданных.** `EditObjectMetadataModal` — единственное место, которое сознательно показывает время в UTC (у него и подписи полей — `Last modified (UTC)`, `Expires at (UTC)`), поэтому `timeZone: "UTC"` сохранён, а тело функции переписано на хелпер:

```tsx
const formatDate = (iso: string): string =>
  // #1236: Swift timestamps are UTC without a "Z"; parse them as UTC (via
  // formatSwiftDate) so the value is correct. This view intentionally displays
  // in UTC (timeZone: "UTC"), unlike the list tables which show local time.
  formatSwiftDate(iso, undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "UTC",
  }) ?? "—"
```
— `.../Swift/Objects/EditObjectMetadataModal.tsx:77-88`

История подтверждает, что этот UTC — старое осознанное решение (введён вместе с самой модалкой в `919f89e9`, переподтверждён в `0c4b2010` при унификации формата с редактируемым полем), а «локальность» таблиц никогда осознанно не выбиралась: там с момента создания (`4e369750`, `93413009`) стоял безаргументный `toLocaleString()`. То есть текущий микс «таблицы — локально, модалка — UTC» истории не противоречит.

**Тест.** `formatSwiftDate.test.ts` (62 строки) построен зоно-независимо: проверяет не отформатированную строку в зоне раннера, а сам инстант (`toISOString()`), а для формата — две явные зоны (`UTC` и `America/New_York`), что и доказывает факт конверсии. Удалённый `try/catch` из `ContainerTableView` был мёртвым кодом с самого первого коммита файла: `new Date()` не бросает, а возвращает `Invalid Date`.

## Что затронуло

**Пропущенных мест нет — это проверено, а не предположено.** `git grep` по `last_modified` на `d6d81280` показывает, что в Swift-компонентах не осталось ни одного места, где `last_modified` парсится напрямую: остальные `new Date(...)` в этой директории работают с unix-секундами (`GenerateTempUrlModal.tsx:249`, `formatUnixToTimestamp`) или со строкой формата поля `"YYYY-MM-DD HH:mm:ss"`, к которой `Z` дописывается явно (`EditObjectMetadataModal.tsx:53`, `:244`) — это отдельный контракт, хелпера не требует.

**Ceph намеренно не тронут и не нуждается в этом.** `Ceph/Buckets/index.tsx:196` и `Ceph/Objects/ObjectBrowserView.tsx:364,401` по-прежнему используют сырой `new Date(...)`, но Ceph возвращает timestamps с `Z`, так что парсинг там корректен. Отдельно проверено, что `ObjectBrowserView` — Ceph-only (экспортируется как `CephObjects`, в общем роуте `storage/$provider/$storageType/$containerName/objects` для Swift рендерится другой компонент), несмотря на то что его `SortKey` для совместимости принимает и Swift-ключ `last_modified`.

**Публичный API пакета не расширен.** Хелпер лежит в `client/utils/` и не экспортируется из `packages/aurora/src/client/index.ts` — внешних потребителей нет, все 5 импортов внутри самого PR. Для встраиваемых под-приложений (SCI) поверхность не изменилась, изменение внутреннее.

**Существующие тесты сигнала не дают.** `ContainerTableView.test.tsx:294` и `EditObjectMetadataModal.test.tsx:259` проверяют лишь наличие строки/подписи, а не конкретное значение времени, и используют зоно-безразмерные фикстуры. Ни один тест в затронутых компонентах не утверждает ни конкретную отформатированную дату, ни порядок сортировки по `last_modified` — это предсуществующий пробел, но именно он маскирует регрессию ниже.

## Ревью

Пять параллельных агентов (соответствие конвенциям, скан багов, история, прошлый фидбек, соответствие комментариям) плюс confidence-scoring. Порог ≥80 прошла одна находка. В репозитории на `d6d81280` нет отслеживаемого `CLAUDE.md`/`AGENTS.md` (`.gitignore` исключает `CLAUDE*`), поэтому проверка «против гайдлайна» опиралась на фактические конвенции соседнего кода.

### [100] Регрессия: `Last modified (UTC)` в модалке метаданных объекта теперь всегда показывает `—`

`needsUtc` определяет «это date-time» подстрочным поиском буквы `T` в любом месте строки:

```ts
const needsUtc = trimmed.includes("T") && !HAS_ZONE.test(trimmed)
```
— `packages/aurora/src/client/utils/formatSwiftDate.ts:35`

Проверки позиции нет, поэтому условие срабатывает и на букве `T` внутри слова **`GMT`**. А в модалку приходит не листинговый timestamp, а сырой HTTP-заголовок `Last-Modified` в формате RFC 1123 — он кладётся в метаданные без изменений на сервере:

```ts
const lastModified = headers.get("last-modified")
if (lastModified) {
  metadata.lastModified = lastModified
}
```
— `packages/aurora/src/server/Storage/helpers/swiftHelpers.ts:250-252`

и попадает в `formatDate` приоритетно, раньше листингового значения:

```tsx
{metadataRaw?.lastModified
  ? formatDate(metadataRaw.lastModified)
  : object.last_modified
    ? formatDate(object.last_modified)
    : "—"}
```
— `.../Swift/Objects/EditObjectMetadataModal.tsx:436-439`

Цепочка на реальном значении (проверено прогоном в node на том же V8):

| шаг | результат |
| --- | --- |
| вход | `"Wed, 01 Mar 2025 12:00:00 GMT"` |
| `trimmed.includes("T")` | `true` — из `GMT` |
| `HAS_ZONE.test` | `false` — `GMT` не матчит `Z` / `±hh:mm` в конце |
| `normalized` | `"Wed, 01 Mar 2025 12:00:00 GMTZ"` |
| `new Date(...)` | `Invalid Date` → `parseSwiftDate` вернёт `null` |
| отрисовано | `"—"` |
| **старый код** `new Date(iso)` | `2025-03-01T12:00:00.000Z` — парсил корректно |

То есть это **строгая регрессия на основном пути**: HEAD-запрос за метаданными объекта в норме успешен, заголовок `Last-Modified` есть практически у каждого объекта, и поле, которое раньше показывало настоящее время, теперь показывает прочерк при каждом открытии модалки. Тест PR это не ловит, потому что мокает `lastModified` как ISO-строку (`EditObjectMetadataModal.test.tsx:117,259`), а не как реальный HTTP-date.

Найдено независимо двумя агентами (скан багов и соответствие комментариям), подтверждено прямым прогоном парсинга и трассировкой источника данных до `swiftHelpers.ts`. Лечится привязкой проверки к позиции — например, тестом на ISO-форму (`/^\d{4}-\d{2}-\d{2}T/`) вместо `includes("T")`, либо явной ветвью для HTTP-date.

### Ниже порога (как контекст, не как задачи)

- **[25]** Комментарий `formatSwiftDate.ts:34` утверждает, что дописывание `Z` к date-only строке «would make it invalid» — фактически неверно (`new Date("2024-03-01Z")` парсится в тот же инстант). Безвредно: код дописывает `Z` только при наличии `T`, так что date-only в эту ветку не попадает. Неверное обоснование при верном поведении.
- **[50]** `formatSwiftDate.test.ts` использует `test(...)`, тогда как все пять существующих `client/utils/*.test.ts(x)` — исключительно `it(...)`. Чистая стилистика, ни линтер, ни гайдлайн-файл этого не требуют.
- **[25]** Замечание Copilot'а к `formatSwiftDate.ts:36` (что компараторы и `formatDate` всё ещё на сыром `new Date`) на `d6d81280` уже неактуально — все три места переведены на хелпер, тред просто не помечен resolved. Остальные его замечания (транзитивность компаратора, `?? 0` как epoch-1970) автор исправил и ответил в треде.

---
Проанализировано: 04.09.2026 · коммит `d6d81280`
