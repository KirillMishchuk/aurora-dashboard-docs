# PR #1176: fix: cap TempURL lifetime and restrict to read-only by default

**Автор:** TilmanHaupt · **Статус:** открыт, не смержен (создан и обновлён 13.08.2026, все 4 коммита в течение одного дня)
**Ветки:** `til-sec-5` → `main` · **Файлов:** 2 (+16/-2)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1176

> Доступ к GitHub API из этой сессии заблокирован (тот же 403 с сообщением про `add_repo`, что и в прошлых отчётах), `gh` недоступен ни по сети из облачного контейнера (сам `gh` установлен, но API/веб-эндпоинты `github.com`/`api.github.com` закрыты прокси этой сессии), ни на устройстве пользователя (`device_bash` без сети). PR склонирован анонимно по `git` (`refs/pull/1176/head` и `refs/pull/1176/merge`, публичный репозиторий, аутентификация не нужна) — весь код, диффы и **полная история всех 4 коммитов** проверены по этому клону, а не по HTML-странице PR. Заголовок PR, ветки и статус выведены из истории коммитов/changeset'а и `git ls-remote`/`merge-base` (надёжно); то, что нельзя получить без API — точный заголовок PR как он показан на GitHub (если автор его редактировал отдельно от коммитов), статус draft/ready, точные `createdAt`/`updatedAt`, ревью-боты — не подтверждено. Именно построчный обход всей истории коммитов (а не просто `git diff base..head`) вскрыл находку №1 ниже — она полностью не видна в итоговом диффе.

## Что сделано

PR продолжает недавнюю серию security-фиксов вокруг Swift в `packages/aurora/src/server/Storage` — SSRF в Swift-аккаунте (#1148), SSRF в пагинации Glance (#1144), редакция TempURL/sync-ключей из ответов метадаты (#1173, всё ещё открыт) — и закрывает следующую находку из того же ряда: `generateTempUrl` позволял выпускать не только `GET`-, но и `PUT`/`POST`/`DELETE`-подписанные временные ссылки с неограниченным сроком жизни (`expiresIn: z.number().min(1)`, без верхней границы).

История внутри самого PR не линейна:

1. **`20613f1` (12:06)** — вводит `MAX_TEMP_URL_LIFETIME = 3600` (1 час), `DEFAULT_TEMP_URL_LIFETIME = 900` (15 минут), сужает `method` до `z.enum(["GET"])` и добавляет аудит-логирование (`console.info` с `userId`/`projectId`/`container`/`object`/`method`/`expiresIn`) в `swiftRouter.ts`. Сообщение коммита само помечает изменение как `Breaking changes: TempURL method restricted to GET only ... expiresIn now capped at 3600s maximum`.
2. **`bcdf367` (12:36)** — поднимает лимит с 1 часа до 7 дней (`604800`), дефолт с 15 минут до 24 часов (`86400`), чтобы совпасть с уже существующими UI-пресетами (1ч/24ч/7д). Этим же коммитом в корень репозитория попадают два больших файла — см. находку №1.
3. **`794f8e4` (12:41, 5 минут спустя)** — удаляет оба файла из шага 2 целиком.
4. **`6f24f56` (14:26, PR head)** — убирает `console.info`-логирование, добавленное в шаге 1, с комментарием «not suitable for production».

Итоговый диф к `main` (`4c34ce8`) — только 2 файла: новый changeset и `swift.ts`. Аудит-логирование в `swiftRouter.ts` добавлено и убрано в рамках одного PR — файл на выходе побайтово идентичен `main`.

## Как это реализовано

### `types/swift.ts` — единственное содержательное изменение

```ts
// swift.ts:395-398
// TempURL lifetime constraints for security
// GET-only URLs can have longer lifetime for file sharing with colleagues
export const MAX_TEMP_URL_LIFETIME = 604800 // 7 days (in seconds)
export const DEFAULT_TEMP_URL_LIFETIME = 86400 // 24 hours
```

```ts
// swift.ts:401-409
export const generateTempUrlInputSchema = baseObjectInputSchema.extend({
  method: z.enum(["GET"]), // Read-only for security
  expiresIn: z
    .number()
    .min(60) // Minimum 1 minute
    .max(MAX_TEMP_URL_LIFETIME) // Maximum 7 days
    .default(DEFAULT_TEMP_URL_LIFETIME),
  filename: z.string().optional(), // Optional Content-Disposition filename
})
```

Было: `method: z.enum(["GET", "PUT", "POST", "DELETE"])`, `expiresIn: z.number().min(1)` — без верхней границы и без ограничения метода.

### `swiftRouter.ts` — потребитель не изменился, но пересчитан

`generateTempUrl` (`swiftRouter.ts:1210-1211`) собирает вход через `projectScopedInputSchema.extend(generateTempUrlInputSchema.shape)`, то есть новые ограничения подключаются автоматически, без изменения кода процедуры. Единственное место, где `method` используется дальше — передача в HMAC-подпись:

```ts
// swiftRouter.ts:1287
const signature = await generateTempUrlSignature(tempUrlKey, method, expiresAt, objectPath)
```

Раньше сюда мог прийти `"PUT"`/`"POST"`/`"DELETE"` — теперь только `"GET"`. Логики, которая ветвилась по значению `method`, в файле не было и нет — сужение типа безопасно для этой функции.

## Что затронуло

Блаcт-радиус проверен по каждому изменённому имени (`generateTempUrlInputSchema`, `MAX_TEMP_URL_LIFETIME`, `DEFAULT_TEMP_URL_LIFETIME`) по всему монорепо:

- **Единственный сервер-потребитель** — `generateTempUrl` в `swiftRouter.ts` (см. выше), без изменений кода.
- **Клиент** — `GenerateTempUrlModal.tsx` (не тронут этим PR) уже отправляет только `method: "GET"` (захардкожено на клиенте) и предлагает ровно три пресета — 1 час / 24 часа / 7 дней (`3600`/`86400`/`604800` секунд) — которые после этого PR **точно** совпадают с новыми `min`/`max`/`default`. То есть UI был приведён в соответствие с этими лимитами заранее (или одновременно, в другом PR) — никакой из уже работающих путей UI не ломается. Поле «Custom duration (minutes)» не имеет верхней границы на клиенте, но это предсуществующее поведение, не тронутое этим PR (см. отклонённую находку ниже).
- **Публичный контракт пакета** — `generateTempUrlInputSchema`/`GenerateTempUrlInput` — часть Zod-схем `@cobaltcore-dev/aurora`, определяющих input-тип tRPC-процедуры `generateTempUrl` для любого внешнего потребителя пакета (не только `apps/dashboard`). Сужение `method` и появление верхней/нижней границы `expiresIn` — контрактное изменение: вызов с `method: "PUT"` или `expiresIn` вне `[60, 604800]`, который раньше проходил, теперь получит ошибку валидации Zod. См. находку №2.
- **Пересечение с #1173** (открыт, не смержен, тот же автор, тот же файл-соседи) — не пересекается по коду: #1173 правит утечку секретных ключей через `swiftHelpers.ts`/`parseAccountInfo`/`parseContainerInfo` (путь чтения метадаты), этот PR — входную схему `generateTempUrl` (путь генерации ссылки). Общего кода нет, но общая причина — оба PR последовательно закрывают пункты одного внутреннего security-аудита (см. находку №1: это и есть тот аудит).

## Ревью

**Две находки набрали 100/100 confidence.**

- **[100/100] Внутренний security-аудит всего приложения (16 находок, включая формулировки эксплойтов и 6-недельный план устранения) был закоммичен в публичный репозиторий и остаётся восстановимым из истории PR даже после удаления.** Коммит `bcdf367` добавил в корень репозитория `SECURITY_ANALYSIS.md` (1427 строк) и `SECURITY_IMPLEMENTATION_PLAN.md` (1841 строка) — это не шаблон, а реальный, проверенный по коду отчёт («Security Review Analysis & Prioritization — Aurora Dashboard», датирован 2026-08-05, привязан к конкретному коммиту `890f453`) с 16 пронумерованными находками (2 High, 12 Medium, 2 Low), включая «Finding #5: Overbroad Swift TempURL Generation» — буквально то, что чинит сам этот PR, «Finding #7: Raw OpenStack Token Exposure via API» (сырой Keystone-токен отдаётся в браузер), «Finding #9: EC2 Credential Deletion IDOR» и т.д., плюс CWE/OWASP/SOC2/PCI-DSS-маппинг и план внедрения с черновиком клиентского уведомления об инциденте. Пять минут позже коммит `794f8e4` удалил оба файла («Remove private security analysis documents that should not be in public repo») — но итоговый `git diff base..head` этого вообще не показывает: файлы появляются и исчезают внутри истории PR, не в net-диффе. Это не спасает: оба коммита уже запушены в публичный `cobaltcore-dev/aurora-dashboard` на GitHub, `git show bcdf3670:SECURITY_ANALYSIS.md` достаёт полный текст любому, у кого есть URL PR — включая после мержа (страница «Commits» PR продолжает ссылаться на эти SHA независимо от способа мержа). Проверено на наличие реальных секретов/учётных данных внутри — не найдено (примеры вида `super-secret-sync-key-123` — заведомо иллюстративные), но сама карта слабых мест приложения и то, что ещё не пофикшено — это и есть чувствительная часть, которая утекла. Возможные шаги: `git filter-repo`/принудительная перезапись истории ветки перед мержем плюс ротация/переиндексация репозитория, если это уже видели третьи лица.
- **[100/100] Changeset помечен `minor`, хотя сами коммиты PR прямо называют изменение breaking — тот же паттерн, что уже отмечался в #1173 (85/100).** `.changeset/tempurl-restrictions.md` объявляет `"@cobaltcore-dev/aurora": minor`. Коммит `20613f1` в своём полном сообщении содержит раздел `Breaking changes:` — «TempURL method restricted to GET only (PUT, POST, DELETE no longer allowed)», «expiresIn now capped at 3600s maximum» (лимит потом подняли до 7 дней, но сама breaking-природа — сужение enum и появление верхней границы, которой не было — не изменилась). Релиз идёт через Changesets (`release.yaml` → `changesets/action`), который читает версию строго из frontmatter файла changeset'а — проза в сообщении коммита никак не влияет на итоговый бамп. Потребитель `@cobaltcore-dev/aurora` с диапазоном `^0.x` получит это как обычный «безопасный» minor-апдейт: TS-код, вызывавший `generateTempUrl` с `method: "PUT"/"POST"/"DELETE"` или с `expiresIn` вне `[60, 604800]`, перестанет собираться/начнёт падать в рантайме без предупреждения о breaking-релизе в CHANGELOG. `CLAUDE.md` отдельно подчёркивает: «commit type/scope directly affects the next version bump, so get it right» — тот же принцип применим к severity changeset'а.

Ниже — то, что проверено и не набрало порог ≥80:

- **[75/100, отклонено — порог не пройден] Текст changeset'а не обновлён после того, как лимит поднялся с 1 часа до 7 дней.** Коммит `20613f1` написал changeset под лимит «1 час»; следующий коммит `bcdf367` поднял его до 7 дней (168×), но текст changeset'а («Cap Swift TempURL lifetime and restrict to read-only by default») так и остался общим, без конкретной цифры. Формально не ложь, но CHANGELOG для потребителей пакета не отражает фактически отправленное поведение. Ближе всего к порогу, но не набрал 80 — оставлено как наблюдение, не как формальная находка.
- **[25/100, отклонено] Все 4 коммита PR не содержат `(scope)` в формате `<type>(<scope>): <subject>`, документированном в CLAUDE.md.** Проверка `commitlint.config.mjs` показала, что правило `scope-empty` не включено — CI это не отловит; итоговый заголовок PR/squash-коммита (который реально проверяется линтером) не подтверждён без доступа к API. Отклонено как маловероятное/неподтверждённое, не как явное нарушение.
- **[0/100, отклонено] Поле «Custom duration (minutes)» в `GenerateTempUrlModal.tsx` не имеет верхней границы на клиенте, из-за чего пользователь теперь может получить серверную 400-ошибку при значении больше 7 дней.** Реальный гэп, но живёт целиком в файле, который этот PR не трогал (баг предсуществующий — раньше сервер тоже не ограничивал `expiresIn` сверху, так что до этого PR несоответствия не было вовсе; несоответствие создаёт новая серверная граница, но сам гэп — не изменённые этим PR строки).
- **[0/100, отклонено] PR не добавляет тестов, проверяющих новые границы схемы (`method: "PUT"` теперь отклоняется, `expiresIn` вне `[60, 604800]` теперь отклоняется).** Общее замечание о покрытии тестами, явно исключённое правилами false-positive (CLAUDE.md не требует тестов на границы Zod-схем).

---
Проанализировано: 13.08.2026 · коммит `6f24f56`
