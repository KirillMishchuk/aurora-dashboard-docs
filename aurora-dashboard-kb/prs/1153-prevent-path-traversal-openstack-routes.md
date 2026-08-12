# PR #1153: fix(core): prevent path traversal in OpenStack API routes

**Автор:** TilmanHaupt · **Статус:** смержен 12.08.2026 (коммит `9645ac6`; открыт 07.08.2026)
**Ветки:** `til-sec-3` → `main` · **Файлов:** 11 (+311/-28)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1153

## Что сделано

PR закрывает security-находку CWE-22 (path traversal) в BFF-слое: часть роутеров подставляла ID ресурса (полученный от клиента через tRPC-инпут) прямо в URL запроса к OpenStack без какой-либо проверки. Строка вида `"../admin"` в качестве `flavorId`/`floatingip_id`/`securityGroupId` могла увести запрос за пределы ожидаемого эндпоинта. По описанию PR затронуто 6 роутеров / 22 операции; по факту в диффе изменены 5 роутеров/хелперов плюс общий error-mapping.

Изменения естественно делятся на три группы:

**Новый security-хелпер (`packages/signal-openstack`)** — единая точка валидации и кодирования сегмента пути. `encodeOpenstackPathSegment` отвергает `.`, `..`, `./`, слэши и `?`/`#`, остальное кодирует через `encodeURIComponent`; `validateAndEncodeResourceId` — обёртка над ней специально для ID ресурсов (UUID или произвольная строка типа `m1.small` — UUID не требуется). Обе функции и сам класс `SignalOpenstackError` (раньше экспортировался только как тип, теперь и как значение — иначе `instanceof`-проверки ниже не скомпилировались бы) выведены из пакета.

**Проводка валидации в потребителей** — `flavorHelpers.ts`/`flavorRouter.ts` (Compute), `floatingIpRouter.ts`/`securityGroupRouter.ts` (Network), `projectRouter.ts` (Project), `pcaRouter.ts` (Services): каждый вызов, который раньше подставлял raw ID в URL, теперь сначала прогоняет его через `validateAndEncodeResourceId` и использует закодированный результат.

**Общий error-mapping** — `errorHandling.ts`: `wrapError` (используется всеми, кто оборачивает хендлер в `withErrorHandling`) теперь превращает `SignalOpenstackError` в `TRPCError({code: "BAD_REQUEST"})` вместо того, чтобы уронить его в generic `INTERNAL_SERVER_ERROR`.

Показательна собственная история branch'а (`git log main..pr-1153-head`): первый коммит (`a2152ca9`) добавил валидацию, но не единообразно её обрабатывал; второй (`aebd0cba`) добавил маппинг в `wrapError` и обработку в `projectRouter`; третий (`71c85454`) убрал добавленный и тут же оказавшийся ненужным `validateUUID`; финальный, `cee23177` (текущий `HEAD`, он же `headRefOid`), — донёс проверку одиночной точки (`segment === "."`, изначально не отлавливалась) и добавил недостающие try/catch в 8 функциях `flavorHelpers.ts`, где `SignalOpenstackError` до этого проваливался в generic `INTERNAL_SERVER_ERROR` вместо `BAD_REQUEST`. То есть PR уже самостоятельно исправил ровно те два класса дефектов («точку не отловили», «код ошибки не тот»), которые характерны для двух предыдущих security-PR того же автора (#1144, #1148) — см. раздел «Что затронуло».

## Как это реализовано

Ядро — новый файл `packages/signal-openstack/src/pathHelpers.ts`:

```ts
// packages/signal-openstack/src/pathHelpers.ts:16-37
export function encodeOpenstackPathSegment(segment: string, label = "Path segment"): string {
  if (!segment || typeof segment !== "string") {
    throw new SignalOpenstackError(`${label} must be a non-empty string`)
  }

  // Reject path traversal attempts
  if (segment === "." || segment.includes("..") || segment.includes("./")) {
    throw new SignalOpenstackError(`${label} contains path traversal characters`)
  }

  // Reject explicit path separators
  if (segment.includes("/")) {
    throw new SignalOpenstackError(`${label} must not contain slashes`)
  }

  // Reject URL special characters that could break path parsing
  if (segment.match(/[?#]/)) {
    throw new SignalOpenstackError(`${label} contains URL special characters`)
  }

  return encodeURIComponent(segment)
}
```

`validateAndEncodeResourceId` (`pathHelpers.ts:56-58`) — тонкая обёртка для ID ресурсов, без требования формата UUID (важно: часть ID в проекте не UUID, например `m1.small` для flavor — см. ниже).

В `packages/signal-openstack/src/index.ts:1-11` экспорт добавлен, а `SignalOpenstackError` перенесён из type-only в value-экспорт (строка 2 vs старая строка 9) — без этого `error instanceof SignalOpenstackError` в потребителях не работал бы.

Два разных стиля проводки в потребителях:

*Явный try/catch с собственным `ERROR_CODES`* — `flavorHelpers.ts` и `flavorRouter.ts` (Compute). Пример, `getFlavorById` (`flavorHelpers.ts:197-217`):

```ts
// packages/aurora/src/server/Compute/helpers/flavorHelpers.ts:205-217
let encodedId
try {
  encodedId = validateAndEncodeResourceId(flavorId, "Flavor")
} catch (error) {
  if (error instanceof SignalOpenstackError) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: ERROR_CODES.GET_FLAVOR_DETAILS_INVALID_ID,
      cause: error,
    })
  }
  throw error
}
```

Этот же паттерн повторён ещё в 7 функциях `flavorHelpers.ts` (`deleteFlavor`, `createExtraSpecs`, `getExtraSpecs`, `deleteExtraSpec`, `getFlavorAccess`, `addTenantAccess`, `removeTenantAccess`) и один раз в `flavorRouter.ts` (`getFlavorAccess`, строки 329-341). Разница между первыми двумя (`getFlavorById`/`deleteFlavor`) и остальными шестью — в том, какой `ERROR_CODES`-константой помечена ошибка валидации: у первых двух это выделенные `*_INVALID_ID`-коды, у остальных шести — тот же код, которым в той же функции уже помечен generic catch-all (пример — `flavorRouter.ts:329-341`, `getFlavorAccess`):

```ts
// packages/aurora/src/server/Compute/routers/flavorRouter.ts:329-341
let encodedId
try {
  encodedId = validateAndEncodeResourceId(flavorId, "Flavor")
} catch (error) {
  if (error instanceof SignalOpenstackError) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: ERROR_CODES.GET_FLAVOR_ACCESS_FAILED,   // ← тем же кодом уже помечен generic catch этой функции
      cause: error,
    })
  }
  throw error
}
```

*Без локального try/catch, через общий `withErrorHandling`* — `floatingIpRouter.ts`, `securityGroupRouter.ts`, `pcaRouter.ts` (все три домена уже оборачивали процедуры в `withErrorHandling`, поэтому проводка тут — однострочник):

```ts
// packages/aurora/src/server/Network/routers/floatingIpRouter.ts:108-113
return withErrorHandling(async () => {
  const { floatingip_id } = input
  const network = getNetworkService(ctx)

  const encodedId = validateAndEncodeResourceId(floatingip_id, "Floating IP")
  const response = await network.get(`${FLOATING_IPS_BASE_URL}/${encodedId}`)
```

Брошенный здесь `SignalOpenstackError` долетает до `wrapError` (`errorHandling.ts:19-26`) и корректно превращается в `BAD_REQUEST` — цепочка проверена по всем трём файлам, разрывов не нашлось.

Особый случай — `projectRouter.ts:205-214` (`getProject`): вместо `throw` при невалидном ID процедура тихо возвращает `null`:

```ts
// packages/aurora/src/server/Project/routers/projectRouter.ts:205-214
let encodedId: string
try {
  encodedId = validateAndEncodeResourceId(input.projectId, "Project")
} catch {
  return null
}

const response = await callIdentityAPI(ctx.identityEndpoint, token.authToken, `projects/${encodedId}`).catch(
  () => null
)
```

На первый взгляд это расходится с паттерном «BAD_REQUEST везде», но по истории коммита (`aebd0cba`) и по остальному телу функции это соответствует уже существовавшему в этой процедуре контракту «любая неудача (сетевая, парсинг, HTTP-ошибка) → `null`» — то есть не новая непоследовательность, а сохранение старого поведения.

`pcaRouter.ts` (Services) — та же однострочная проводка через `withErrorHandling`, применена в 6 местах (`getById`, `delete`, `importCertificate`, `listCertificates`, `createCertificate`, `getCertificate` — последний с двумя ID, authority и certificate, оба валидируются отдельно).

Наконец, `errorHandling.ts:19-26` — сам маппинг:

```ts
// packages/aurora/src/server/helpers/errorHandling.ts:19-26
// Map SignalOpenstackError (validation failures) to BAD_REQUEST
if (error instanceof SignalOpenstackError) {
  return new TRPCError({
    code: "BAD_REQUEST",
    message: error.message,
    cause: error,
  })
}
```

Docstring над `wrapError` (строка 8) обновлён синхронно с кодом — заявленное поведение соответствует реализации.

Тесты: добавлен только `packages/signal-openstack/src/pathHelpers.test.ts` (unit-тесты хелпера — happy path, path traversal, URL-спецсимволы). Ни один из шести существующих colocated test-файлов роутеров/хелперов (`flavorHelpers.test.ts`, `flavorRouter.test.ts`, `floatingIpRouter.test.ts`, `securityGroupRouter.test.ts`, `projectRouter.test.ts`, `pcaRouter.test.ts`) не обновлён — новое поведение (BAD_REQUEST на невалидный ID) проверено только на уровне хелпера, не через сами tRPC-процедуры.

## Что затронуло

`validateAndEncodeResourceId`/`encodeOpenstackPathSegment` — новый экспорт, внешних потребителей за пределами файлов этого PR пока нет (проверено `git grep` по всему монорепо на `pr-1153-head`).

Важнее — что PR **не** покрывает, хотя рисунок уязвимости тот же (raw ID в шаблонной строке URL, схема входа — просто `z.string()` без ограничений):

- **`packages/aurora/src/server/Compute/routers/imageRouter.ts`** — `memberId` (`types/image.ts:134`, `z.string()` без ограничений) подставляется без валидации в `v2/images/${imageId}/members/${memberId}` (`imageRouter.ts:746`, `:796` и ещё несколько мест). `imageId` там же защищён `z.string().uuid()`, `memberId` — нет.
- **`packages/aurora/src/server/Network/routers/rbacPolicyRouter.ts`** — `policyId` без валидации в `${RBAC_POLICIES_BASE_URL}/${policyId}` (строки 99, 116).
- **`packages/aurora/src/server/Network/routers/securityGroupRuleRouter.ts`** — `ruleId` без валидации в `${SECURITY_GROUP_RULES_BASE_URL}/${ruleId}` (строка 31).

Это не регрессия этого PR — просто у него, по собственному описанию, обозначенный периметр (6 роутеров/22 операции), и три вышеперечисленных места в этот периметр не попали. Учитывая, что тот же автор чинил соседние SSRF/path-related находки этой же серией PR (#1144 — абсолютные URL в пагинации изображений, #1148 — Swift account SSRF), похоже на точечное закрытие находок пентеста одна за другой, а не на системный проход — стоит явно спросить автора/ревьюеров, входят ли эти три места в следующую итерацию.

Отдельно: в репозитории теперь два security-хелпера с непересекающейся зоной ответственности и без взаимных ссылок — `packages/aurora/src/server/helpers/urlValidation.ts` (добавлен тем же автором двумя PR раньше, для защиты от SSRF через абсолютные URL) и новый `packages/signal-openstack/src/pathHelpers.ts` (для path traversal через сегменты пути). Разные слои и разные уязвимости, конфликта нет, но при поиске «где у нас в проекте валидация небезопасного пользовательского ввода для OpenStack-запросов» человек без контекста найдёт только один из двух.

## Ревью

Проблем с уверенностью ≥80 не найдено.

Ближе всего к порогу — переиспользование одного и того же кода `ERROR_CODES.*_FAILED` для двух разных причин отказа (валидация ID и обычный сетевой/backend-сбой) в шести функциях `flavorHelpers.ts` и один раз в `flavorRouter.getFlavorAccess` (см. цитаты выше в «Как это реализовано»): независимая проверка подтвердила, что на уровне `TRPCError.code` (`BAD_REQUEST` vs `INTERNAL_SERVER_ERROR`) различие сохраняется, но клиентский `useErrorTranslation` переключается по строке `ERROR_CODES`, а не по `code`, так что пользователь в обоих случаях увидит одно и то же сообщение «...Please try again» — включая невалидный ID, повторять запрос для которого бессмысленно. Оценка независимой проверки — 75/100 («выявится на практике при каждом обращении с невалидным ID», но не 100, так как сам защитный механизм это не ломает, страдает только диагностика/UX). Порог ≥80 не пройден, но стоит на заметке у ревьюера — тем более что в этом же PR для `getFlavorById`/`deleteFlavor` автор использовал более точный паттерн (выделенные `*_INVALID_ID`-коды), так что исправление — просто привести шесть остальных функций к тому же виду.

Отдельно проверено и отклонено как не баг: возврат `null` вместо `BAD_REQUEST` в `projectRouter.getProject` при невалидном ID (согласуется с уже существовавшим в этой процедуре поведением «любой сбой → null»); повторная валидация одного и того же `flavorId` в `flavorRouter.getFlavorAccess` (сначала в самой процедуре, затем ещё раз внутри вызываемого хелпера) — избыточно, но не некорректно; предположение про обход проверки через `%2e%2e` — не работает, `encodeURIComponent` экранирует сам символ `%` до того, как строка попадёт в URL.

---
Проанализировано: 12.08.2026 · коммит `cee23177`
