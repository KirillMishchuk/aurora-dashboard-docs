# PR #1120: feat(portal): generate pre-signed URLs for objects

**Автор:** mark-karnaukh-extern-sap · **Статус:** смержен 05.08.2026 (коммит `502a1e92`)
**Ветки:** `mark-ceph-object-pre-signed-urls` → `main` · **Файлов:** 16 (+1323/-11)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1120

## Что сделано

У Swift-объектов давно есть временные HMAC-подписанные ссылки (`GenerateTempUrlModal`, PR #705), у Ceph (S3) — не было. PR закрывает этот разрыв: добавляет **pre-signed URL** для объектов Ceph — новую процедуру `storage.ceph.objects.generatePresignedUrl` в BFF и модалку `GeneratePresignedUrlModal` на клиенте, вызываемую через новый пункт «Share URL» в меню действий строки объекта в `ObjectsTableView`.

В отличие от Swift, здесь нет ключа, который нужно предварительно сконфигурировать: подпись выводится из уже существующих EC2-credentials запроса (тех же, что используются остальными Ceph-процедурами через `getCephClient()`), поэтому реализация проще Swift-аналога — не нужен путь «ключ не настроен», нет параметра account.

Ограничение: **только GET**. Presigned `PUT` (upload-by-link) явно вне скоупа — загрузка по-прежнему идёт через существующий `uploadObject` (стриминг через BFF, см. PR #1086 в этом же ключе документации).

## Как это реализовано

**Схема входа** (`packages/aurora/src/server/Storage/types/ceph.ts:271-281`) вводит константу максимального времени жизни ссылки и Zod-схему, использующую её как верхнюю границу:

```ts
// ceph.ts:271-281
export const S3_PRESIGN_MAX_EXPIRY_SECONDS = 604800

export const generatePresignedUrlInputSchema = projectScopedInputSchema.extend({
  containerName: z.string().min(1),
  objectKey: z.string().min(1),
  expiresIn: z.number().int().positive().max(S3_PRESIGN_MAX_EXPIRY_SECONDS),
})
```

604800 секунд (7 дней) — это жёсткий максимум самого протокола AWS SigV4 (подписчик `@aws-sdk/s3-request-presigner` сам отклонит бо́льшее значение); вынося проверку в Zod-схему, PR превращает выход-за-границу в понятный `BAD_REQUEST` ещё до похода к сайнеру, вместо непрозрачной ошибки подписи. Константа экспортируется специально, чтобы фронтенд не держал собственное магическое число 604800 и не мог разойтись со схемой (см. использование в модалке ниже).

**Процедура** (`packages/aurora/src/server/Storage/routers/ceph/objectRouter.ts:305-323`) построена на `cephProtectedProcedure` — том же билдере, что и все остальные Ceph-object-процедуры в этом файле (`list`, `getDetails`, `deleteAll`, `copy`, ...), так что она автоматически наследует существующий контракт аутентификации/рескоупинга, ничего нового здесь не вводится:

```ts
// objectRouter.ts:305-323
generatePresignedUrl: cephProtectedProcedure
  .input(generatePresignedUrlInputSchema)
  .mutation(async ({ ctx, input }): Promise<{ url: string; expiresAt: number }> => {
    const s3 = ctx.getCephClient!()
    const { containerName, objectKey, expiresIn } = input

    try {
      const url = await getSignedUrl(s3, new GetObjectCommand({ Bucket: containerName, Key: objectKey }), {
        expiresIn,
      })
      const expiresAt = Math.floor(Date.now() / 1000) + expiresIn
      return { url, expiresAt }
    } catch (error) {
      throw mapS3ErrorToTRPCError(error, {
        operation: "generate presigned URL",
        bucket: containerName,
        key: objectKey,
      })
    }
  }),
```

Ключевая деталь, которую стоит понимать при чтении этого кода: подпись — чисто локальная криптографическая операция (`getSignedUrl` не делает сетевого похода к Ceph), поэтому вызов быстрый и **не проверяет, что объект вообще существует** — сам PR это явно документирует как компромисс (см. ниже, docs). `expiresAt` вычисляется на сервере как абсолютный unix-timestamp (`now + expiresIn`), а не просто возвращает длительность — так фронтенду не нужно доверять собственным часам для отображения времени истечения.

**Фронтенд** — `GeneratePresignedUrlModal.tsx` (новый файл, 352 строки), Ceph-аналог `Swift/Objects/GenerateTempUrlModal.tsx`, но заметно проще: нет полей account/method, нет ветки «ключ не настроен» (у Swift она есть, потому что там нужен предварительно сконфигурированный HMAC-ключ — у Ceph такого шага нет в принципе). Импортирует общий лимит из серверного модуля тем же путём, что и остальной клиентский код в этом файле (`S3Object`/`S3FolderPrefix` из `@/server/Storage/types/ceph` в `ObjectsTableView.tsx` — существующая конвенция, не новая для этого PR):

```ts
// GeneratePresignedUrlModal.tsx:6,19-21
import { S3_PRESIGN_MAX_EXPIRY_SECONDS } from "@/server/Storage/types/ceph"
...
const MAX_EXPIRY_SECONDS = S3_PRESIGN_MAX_EXPIRY_SECONDS
const MAX_EXPIRY_MINUTES = MAX_EXPIRY_SECONDS / 60
```

Пресеты — 1 час / 24 часа / 7 дней плюс произвольная длительность в минутах; при custom-вводе модалка сама валидирует границу (`> MAX_EXPIRY_MINUTES` → инлайн-ошибка), не давая уйти в round-trip за гарантированным 400 от бэкенда.

Защита от протухших ответов реализована через инкрементный `requestIdRef` (`GeneratePresignedUrlModal.tsx:76,156,166,170`): каждый вызов `handleGenerate` захватывает текущее значение счётчика, и `onSuccess`/`onError` игнорируют результат, если счётчик успел измениться (второй клик «Generate», смена пресета, либо закрытие модалки — см. `useEffect` на `isOpen`, инкрементирующий счётчик при закрытии). Копирование в буфер (`handleCopy`, `GeneratePresignedUrlModal.tsx:177`) отдельно отслеживает состояние ошибки копирования (`copyError`) от состояния ошибки генерации (`generalError`) — они не затирают друг друга.

**Подключение в таблицу** (`ObjectsTableView.tsx:186,531,622-630`) — новый пункт меню строки, задизейбленный для не-объектных строк (папок), и сама модалка, тост об успешном копировании поднимается прямо здесь же, не требуя изменений в `ObjectBrowserView`:

```tsx
// ObjectsTableView.tsx:622-630
<GeneratePresignedUrlModal
  bucketName={bucketName}
  objectKey={presignedUrlTarget?.key ?? null}
  isOpen={presignedUrlTarget !== null}
  onClose={() => setPresignedUrlTarget(null)}
  onCopySuccess={(objectKey) => {
    const { message, ...options } = getPresignedUrlCopiedToast(objectKey)
    toast.success(message, options)
  }}
/>
```

Новый тост `getPresignedUrlCopiedToast` (`ObjectToastNotifications.tsx:127-134`) выводит basename ключа объекта тем же способом (`split("/").filter(Boolean).pop()`), что и остальные тосты этого файла — консистентно с существующим паттерном.

**Документация** (`packages/aurora/docs/009_ceph_s3_bff.md:181,1095-1141`) обновлена по месту: добавлена запись в дерево процедур, отдельный раздел `#### generatePresignedUrl` с input/output/примером, и явно проговорена асимметрия с `downloadObject` (та стримит через BFF, эта выдаёт прямую ссылку) и с Swift (там HMAC + обязательная настройка ключа, здесь — ничего конфигурировать не нужно). В разделе limitations прежняя строка «No presigned URL generation» заменена на «Presigned URLs are GET-only» — документация обновлена консистентно с кодом, а не оставлена стухшей.

## Что затронуло

Проверка по всему монорепо (`git grep` на `generatePresignedUrl`, `S3_PRESIGN_MAX_EXPIRY_SECONDS`, `getPresignedUrlCopiedToast`, `GeneratePresignedUrlModal` на head-коммите) не нашла ни одного потребителя за пределами файлов, изменённых самим PR. Это чисто аддитивная фича:

- `generatePresignedUrl` — новая процедура, ничего не переиспользует и не переиспользуется другими роутерами; корректно экспортируется через `objectRouter` → `routers/ceph/index.ts` → общий `AuroraRouter`, так что `trpcClient.storage.ceph.objects.generatePresignedUrl` реально доступен с клиента.
- `S3_PRESIGN_MAX_EXPIRY_SECONDS` используется только в двух местах: сама схема (`ceph.ts`) и модалка (`GeneratePresignedUrlModal.tsx`) — ровно как и задумано (единый источник границы).
- `GeneratePresignedUrlModal` подключена только в `ObjectsTableView.tsx` (Ceph), в Swift-версии таблицы (`Swift/Objects/ObjectsTableView.tsx`) не тронута и не должна быть — это разные бэкенды с разными сценариями (HMAC vs SigV4).

Контрактных изменений (публичные пропсы `AuroraApp`, существующие процедуры, экспортируемые типы) нет — новая процедура и новый компонент добавлены, ничего существующего не изменено по сигнатуре.

## Ревью

Через диф, историю и комментарии прогнаны параллельно CLAUDE.md-compliance, bug-scan, historical-context, prior-feedback и comment-compliance.

CLAUDE.md-compliance ничего не нашёл: процедура построена на правильном билдере (`cephProtectedProcedure`, не raw `initTRPC`), схема наследует `projectScopedInputSchema`, модалка лежит в `-components/`-директории, коммиты соответствуют conventional commits. Historical и prior-feedback агенты не нашли релевантной истории проблем в затронутых файлах и открытых замечаний из прошлых PR, которые бы всё ещё применялись.

Comment-compliance нашёл один нюанс словесной неточности (не функциональный баг): комментарий у `requestIdRef` (`GeneratePresignedUrlModal.tsx:76-81`) утверждает, что счётчик инкрементируется «on every generate call and on modal close/reopen» — по факту `useEffect` инкрементирует его только в ветке `!isOpen` (то есть при закрытии), отдельного пути на реоткрытие нет. Гарантия защиты от протухших ответов при этом не нарушается (инкремент при закрытии уже покрывает любой запрос, оставшийся от предыдущего открытия), так что это неточность формулировки, а не баг — не набрало уверенности ≥80.

**Проблем с уверенностью ≥80 не найдено.**

---
Проанализировано: 03.08.2026 · коммит `66a33b5f`
