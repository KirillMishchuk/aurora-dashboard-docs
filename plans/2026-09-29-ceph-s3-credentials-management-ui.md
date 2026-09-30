# Plan: Управление S3-кредами (Ceph) в Aurora

**Date:** 2026-09-29 · **Status:** implemented 2026-09-29 (локальные правки в `main`, не закоммичено)

**Результат прогона.** Все 15 шагов выполнены. Проверки: typecheck чисто, 5778 тестов в 238 файлах (0 упавших), lint 4/4 пакета, `format:check` чисто, `check-i18n` прошёл, `build` собрал все 4 пакета, `licenses:check` прошёл. Ревью безопасности (auth/авторизация, валидация входа, раскрытие данных) — **ни одной находки Critical/High**; отдельно подтверждено, что `reveal` повторяет проверку владения из `delete` через общий `fetchOwnedCredential` и сохраняет `NOT_FOUND`-вместо-`FORBIDDEN` (анти-перебор из #1182), что пре-чек лимита fail-closed, и что новый `try/catch` в `createPermissionRouter` возвращает `false`. Follow-up'ов не заводилось.

**Тройное ревью (29.09.2026)** — security / performance / architecture параллельно по одному набору файлов. Итог: 1 High, 2 Medium, ~12 Low, 0 находок по производительности.

Исправлено в этом же заходе: оба Medium — удалены мёртвые ре-экспорты `CredentialPrompt`/`ManageCredentialsModal` из `Ceph/Buckets/index.tsx` (переезд в `Ceph/Credentials/` частично отменялся ими), и сужен `catch` в `createPermissionRouter` — теперь поглощается только «правило не найдено и нет `_default`», всё остальное пробрасывается; докблок переписан нейтрально к репозиторию (`policyDir` — потребительский параметр `createServer()`), поведение дописано в контракт `canUser` и в `PERMISSION_ROUTER_IMPLEMENTATION.md`. Плюс `storage:credentials:delete` внесён в `PERMISSION_KEY_PATTERN.md`, и починена идемпотентность `delete`: `request()` в signal-openstack бросает `SignalOpenstackApiError` на любой не-2xx вместо `{ok:false}`, поэтому 404 надо ловить, а не проверять — ветки `if (!response.ok)` были недостижимы, и удаление уже удалённого креда возвращало `NOT_FOUND` вместо `{success:true}`. Добавлено 5 тестов на реальную (бросающую) форму отказа.

Отложено осознанно: **High — секреты EC2-кред уходят в debug-логи `signal-openstack` открытым текстом** (`redactSensitiveData` сопоставляет только имена ключей и не заглядывает внутрь строк; `debug` включён по умолчанию везде, кроме строгого `NODE_ENV=production`). Корень пре-существующий, пакет `signal-openstack` этим изменением не трогался, но канал расширен: `reveal` даёт пользовательский повторяемый путь, а пре-чек лимита в `create` начал читать блобы существующих кред. Заведено как [FOLLOW-UPS.md](../FOLLOW-UPS.md) → пункт 29 по решению пользователя.

**Code-review (29.09.2026), отдельным проходом после правок triple-review.** Семь находок, одна не подтвердилась.

Исправлено: (№2) `ManageCredentialsModal` терял `isError` из `useCephPermissions` — при сбое запроса прав пользователю показывали «нет прав, обратитесь к администратору» вместо «попробуйте позже»; регрессия нашего диффа, у прежнего `CredentialPrompt` такая ветка была. (№1) `onSuccess` создания и `handleReveal` могли записать секрет в state уже после закрытия модалки — она смонтирована всегда, а `reset()` не отменяет летящий запрос; теперь запись под гардом по ref на `isOpen`. (№5) `fetchOwnedCredential` не проверял `type === "ec2"`, из-за чего `delete` мог удалить кред другого типа через эндпоинт управления S3-ключами. (№6) кнопка подтверждения удаления получила `disabled` — `progress` в Juno 9.4.0 только меняет иконку на спиннер. Добавлено 4 теста.

Не подтвердилась (№3): утверждение, что настоящие 401/403 от Keystone доходят до клиента как 500 с сырой строкой OpenStack. `openstackErrorMiddleware` (`trpc.ts:15-60`) отображает их корректно; отличается только текст сообщения.

Отложено: (№3, №4, №7) — ветки `if (!response.ok)` недостижимы по всему репозиторию, а тесты маскируют это моками, которые резолвятся вместо того, чтобы бросать; плюс сужённый по сообщению `catch` в `createPermissionRouter` поглощает и вложенное неопределённое правило, и опечатку в `mappings`. Валидацию правил на старте не делаем осознанно: `policyDir` задаёт потребитель, падение на старте у оператора со старым policy-файлом хуже скрытой кнопки. Заведено как [FOLLOW-UPS.md](../FOLLOW-UPS.md) → пункт 30.

**Правка по фидбэку после ревью (29.09.2026): CLI-сниппет удалён.** Блок `CodeBlock` с `AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… aws --endpoint-url … s3 ls`, который рендерился под таблицей для каждого раскрытого ключа (решение F, Step 13.4), убран из модалки по решению пользователя как лишний. Вместе с ним ушли импорт `CodeBlock`, строка каталога `AWS CLI`, тест «CLI snippet» и соответствующий буллет из чейнджсета. Endpoint и region остаются — они в панели Connection Details, каждое значение копируется отдельно. Тестов стало 5786.

**Правка по фидбэку (29.09.2026): модалка расширена до `xl`.** Ключи наезжали друг на друга: `size="large"` в Juno 9.4.0 — это всего `40rem` (640px), а на три равные колонки нужно место под 40-символьный access key, 56-символьный секрет и кнопки. Переведено на `size="xl"` (`76.75rem`, 1228px) — та же ширина, что у Compute → Flavors → Edit Metadata (`EditSpecModal.tsx:239`). Плюс `minContentColumns={[2]}` на `DataGrid`: колонка с действиями сжимается по содержимому, а освободившееся место уходит двум текстовым колонкам. Размеры проверены по установленному пакету (`build/index.js`, `tx()`): small 33.625rem · large 40rem · xl 76.75rem · 2xl 80% (min 85rem).

**Правка по фидбэку (29.09.2026): Show/Hide переехали в колонку действий.** Кнопка раскрытия стояла вплотную к самому секрету и мешала его читать/копировать; теперь колонка «Secret Access Key» содержит только значение (`ClipboardText` или маску `••••••••••••`), а `Show`/`Hide` стоит рядом с корзиной. На время подтверждения удаления в колонке остаются только `Delete`/`Cancel`. Добавлены `data-testid` `reveal-credential-<id>` и `hide-credential-<id>` по образцу `delete-credential-<id>`.

**Иконки «показать/скрыть» в проекте нет.** Проверено: `KnownIconsEnum` в Juno 9.4.0 — 61 иконка, ничего похожего на глаз/visibility (`build/components/Icon/Icon.component.d.ts`); `IconProps.icon` типизирован строго как `KnownIcons`, произвольную SVG туда не передать. Своих ассетов в репо тоже три штуки — `grid.svg`, `json.svg`, `logo.svg`. Поэтому переключатель остался текстовой кнопкой `Show`/`Hide` (`size="small" variant="subdued"`) рядом с иконочной корзиной. Если нужна именно иконка — придётся заводить свой SVG-ассет (в сборке есть `vite-plugin-svgr`) и рендерить его мимо `Icon`.

**Правка по фидбэку (29.09.2026): маскировка секрета снята полностью — решение D пересмотрено.** Кнопок `Show`/`Hide` больше нет, секрет виден сразу. Реализовано на клиенте: `useEffect` при открытии модалки дёргает `reveal` для каждого ключа из `list` (максимум 2 запроса), результат кладётся в `revealedSecrets`. Серверный контракт не тронут — `list` по-прежнему вырезает секрет, `reveal` остаётся мутацией, и секрет по-прежнему не попадает в кэш TanStack Query. Отклонён вариант «пусть `list` отдаёт секрет»: он дешевле на один-два запроса, но возвращает секрет в query-кэш и devtools, от чего уходило решение №2.

Детали: `requestedSecretIds` (ref) не даёт перезапрашивать ключ при каждом рендере и повторно читать секрет только что созданного ключа — `create` кладёт его в state сам; ошибка запроса пишется в `failedSecretIds` и показывается строкой «Could not load secret» в своей же ячейке, не роняя соседний ключ; `revealMutation.isPending` убран из `isBusy`, иначе фоновая подгрузка блокировала бы Close/Create/Delete. Тесты «Secret masking» переписаны в «Secret display» (5 тестов: автозагрузка, частичный отказ, поздний ответ после закрытия, перезапрос при повторном открытии, ошибка проверки прав). Тестов стало 5785.

**Риск принят осознанно.** Строка «🔒 Секрет в DOM/скриншотах/скринкастах» в таблице рисков выше описывает митигацию, которой больше нет: любой скриншот или шаринг экрана с открытой модалкой раскрывает оба секрета целиком, без единого клика. Пользователь выбрал этот вариант явно.

**Правка по фидбэку (29.09.2026): заголовки секций переведены на `FormSection`.** Было `ContentHeading` — это `<h1>` на 1.69rem (27px), компонент задуман как заголовок страницы внутри `ContentContainer`/`AppShell`, и он оказывался крупнее заголовка самой модалки (`<h4 class="juno-modal-title">`, 1.28rem). Дом-паттерн для секций внутри попапа — `FormSection` с пропом `title` (так сделан `CreateFlavorModal`): он рендерит `<h4 class="juno-formsection-heading mb-4">`, то есть ровно уровень заголовка модалки, и сам держит отступы между секциями (`mb-8 last:mb-0`). Внешний `Stack gap="6"` за ненадобностью убран. Размеры сверены по `build/juno-ui-components.css` пакета 9.4.0: h1 1.69rem · h4 1.28rem · h5 1.125rem.

**Правка по фидбэку (29.09.2026): баннеры в секции Access Keys убраны.** Постоянный `Message variant="warning"` про то, что удалённый ключ сразу перестаёт работать, и `Message variant="info"` про лимит (показывался при `atLimit`) заменены одним абзацем-описанием под заголовком секции — обычным `<p>` без классов цвета и размера — как вводный абзац в `DeactivateImageModal` (`<p className="mb-4">`, базовый цвет текста); отступ здесь даёт `Stack gap="2"`. Оба факта верны для экрана всегда, а как баннеры они конкурировали с настоящими сообщениями об ошибках ниже. `atLimit` остался — он по-прежнему дизейблит кнопку Create.

Побочно: текст ошибки `EC2_CREDENTIAL_LIMIT_REACHED` переписан («Could not create an access key: you already hold the maximum of 2. Delete one first.»), потому что раньше он дословно повторял текст инфо-баннера, а теперь этот текст стоит в описании постоянно — на экране выходило одно и то же предложение дважды.

**Правка по фидбэку (29.09.2026): Create Access Key переехал из футера в секцию.** Кнопка стоит над таблицей ключей, справа (`Stack direction="horizontal" className="justify-end"`), дефолтным вариантом — как «Add Property» в `EditSpecModal`. Создание — действие над секцией, а не над модалкой. В футере остался один Close, и он теперь primary: `ModalFooter` в Juno 9.4.0 рисует пару «subdued Cancel + primary Confirm» только если задан `confirmButtonLabel` или `onConfirm`; без них остаётся одна кнопка с `variant: confirmButtonVariant || "primary"` и подписью `cancelButtonLabel || "Close"`, вешающаяся на `onCancel`. Поэтому `onConfirm`, `confirmButtonLabel`, `confirmButtonVariant` и `disableConfirmButton` с `Modal` сняты, а условие дизейбла переехало на саму кнопку вместе с `progress={createMutation.isPending}`.

**Правка по фидбэку (29.09.2026): подтверждение удаления убрано совсем, таблице добавлен нижний отступ.** Сначала я скопировал двухшаговое подтверждение из `SpecRow` (иконка → `primary-danger` «Delete» с самосбросом через 3 с). Пользователь заметил, что во флейворах удаление идёт без подтверждения — и был прав: **`SpecRow` — мёртвый код**, его не импортирует ничего, кроме собственного теста. Живой `EditSpecModal` удаляет строку сразу (`handleDelete`, `EditSpecModal.tsx:392-400`). Ближайший по форме живой аналог — `Ceph/Objects/EditMetadataModal`: тот же `DataGrid` внутри модалки, построчные Edit/Delete, и корзина `variant="primary-danger"` удаляет по клику без подтверждения (`:505-512`).

Итог: корзина осталась дефолтного варианта (как во флейворах — `primary-danger` из `EditMetadataModal` пользователь отклонил) и удаляет сразу; пока летит запрос, на её месте `<Spinner variant="primary" size="small" />`; предупреждение об необратимости несёт постоянное описание секции. `pendingDeleteId` заменён на `deletingId` + `deletingIdRef` — колбэки мутации могут отработать в том же тике, что и клик, до перерисовки, поэтому id для тоста и очистки секрета читается из ref, а не из state. Тесты: «first click shows inline confirmation» и «disarms itself after three seconds» удалены, «confirming calls delete» превращён в «the trash button deletes on the click». Тестов стало 5783.

**Замечание, которое остаётся в силе:** удаление ключа необратимо (секрет не восстановить, любой настроенный на него клиент ломается мгновенно), в отличие от строки метаданных, которую можно добавить обратно. Пользователь выбрал единообразие с остальным дашбордом явно.

Отступ: `DataGrid` получил `className="mb-6"` — по образцу `DescriptionList className="mb-6"` в `EditSpecModal`. `FormSection` даёт `mb-8 last:mb-0`, то есть последняя секция своего отступа не имеет и таблица упиралась в футер.

**Второй triple-review (30.09.2026)** — после переработки модалки по фидбэку. Security: Critical/High нет, одна Low (права на create/delete гейтятся только на клиенте — сознательный паттерн всего ceph-домена, UX-only, реальный бэкстоп у Keystone). Performance: 2 находки. Architecture: 10 плюс неточность в чейнджсете.

Исправлено в этом же заходе:

- **Инвалидация запросов.** Заведён `Ceph/hooks/invalidateCredentialQueries.ts` (третий в семье после `invalidateBucketQueries` и `invalidateVersioningStatusQueries`). `containers.list` теперь инвалидируется только на переходе 0↔1 по числу ключей: страница читает его с `includeMetadata: true`, то есть `ListObjectsV2` на каждый бакет пачками по 5, а второй ключ не меняет ни одного бакета. `containers.status` не инвалидируется вовсе — его единственный читатель берёт оттуда `endpoint`/`region` под `staleTime: Infinity`, а `hasCredentials` на клиенте не читает никто; `invalidate()` же перезапрашивает независимо от `staleTime`, и каждый такой рефетч стоил ещё одного `GET /v3/credentials` через middleware `cephProcedure`.
- **Мёртвые схемы инпута.** `listEc2CredentialsInputSchema`, `createEc2CredentialInputSchema`, `deleteEc2CredentialInputSchema` имели ноль ссылок вне `types/ceph.ts`, при этом `delete` переобъявлял ту же схему инлайн, а `types/ceph.test.ts` тестировал неиспользуемую. Схлопнуто в один `ec2CredentialIdInputSchema`, используется в `delete` и `reveal`.
- **Парсинг блоба.** Троекратный `JSON.parse` → `safeParse` → `throw` вынесен в `Storage/helpers/ec2CredentialMapper.ts` (`toEc2Credential` / `toEc2CredentialWithSecret`, 10 тестов). Попутно закрыта дыра: `"null"`, `"42"` и `"[]"` парсились успешно и доходили до чтения полей — старый код ловил это случайно, потому что `try` охватывал и чтения. Сообщения об ошибке в `create` унифицированы с остальными (теперь называют id креда).
- **Уровень лога.** `console.error` → `console.warn` в `createPermissionRouter`: докблок сам называет состояние легитимным, а `useCephPermissions` просит ~20 ключей на загрузку страницы.
- **Чейнджсет.** Утверждение, что `S3Status`/`s3StatusSchema` экспортируются из пакета и консьюмерам нужно обновляться, неверно — ни одного из символов нет ни в `server/index.ts`, ни в `types/index.ts`. Переписано на фактическое: процедура стала отдавать два поля, для консьюмеров это чисто аддитивно.

Отложено в [FOLLOW-UPS.md](../FOLLOW-UPS.md): пункт 31 (регулярка по тексту ошибки `policy-engine` — правка в двух пакетах), 32 (двойной `GET /v3/credentials` — требует расщепления `cephProcedure`), 33 (хук `useCredentialSecrets`), 34 (`let content` в `CephBuckets`).

Не трогали сознательно: права только на клиенте (паттерн всего домена, KB «эти проверки — UX-only»); смешение `return null` и `throw` в `fetchOwnedCredential` (ревьювер сам пометил как judgement call, поведение корректно); асимметрия каналов обратной связи в `CredentialToastNotifications`.

После правок: typecheck чисто, lint 4/4, `format:check` чисто, `check-i18n` прошёл, 240 файлов / 5796 тестов, 0 упавших.

**Code-review (30.09.2026), третий проход.** Три находки, все подтвердились, все исправлены.

- **(Medium) Флаг `hasCredentialsChanged` считался по устаревшему списку.** Колбэк мутации видел `credentials` из последнего рендера, а после предыдущей мутации список ещё догружался. В сценарии ротации (удалить единственный ключ → сразу создать новый) `credentials.length` оставалась 1, флаг выходил `false`, `containers.list` не инвалидировался — а он сидел в ошибке `NO_CEPH_CREDENTIALS` с `retry: false` и сам не перезапрашивался, так что страница навсегда застревала на «Setup Required» до ручной перезагрузки. Хелпер переписан: он теперь `async`, сначала дожидается инвалидации `ec2Credentials.list`, затем читает счётчик из обновлённого кэша через `getData` и решает по нему (`create` → ровно 1 ключ значит первый, `delete` → ноль значит был последний). Счётчик неизвестен — инвалидируем, это безопасное направление. Сигнатура сменилась на `{ projectId, mutation }`.
- **(Low/Medium) Escape закрывал модалку посреди мутации.** Проверено по установленной сборке Juno 9.4.0: `escapeDeactivates: (e) => (B(e), !1)`, где `B` смотрит только на `closeable && closeOnEsc` и зовёт `onCancel`; `disableCancelButton`/`disableCloseButton` на Escape не влияют. Последствия: у create `handleClose` чистил `requestedSecretIds` раньше, чем `onSuccess` добавлял туда id нового ключа, и при следующем открытии эффект пропускал этот id как «уже запрошенный» — ячейка секрета висела на `Loading…` навсегда; у delete `deletingIdRef` обнулялся до чтения, и тост об удалении молча терялся. Добавлено `closeOnEsc={!isBusy}` плюс сброс `requestedSecretIds`/`deletingIdRef` при открытии модалки, а не только при закрытии — чтобы любое закрытие мимо `handleClose` (в том числе если родитель сам уронит `isOpen`) не оставляло мусора. Новый тест.
- **(Low) Докблок `fetchOwnedCredential` обещал больше, чем делает код.** Утверждение «чужой кред отдаётся как NOT_FOUND, не FORBIDDEN» верно только для кредов, которые Keystone вообще даёт прочитать. При дефолтной современной политике (`identity:get_credential = user_id:%target.credential.user_id%`) чужой существующий id даёт 403 → `FORBIDDEN`, несуществующий — 404 → `NOT_FOUND`, то есть различимы. Код не меняли: заворачивать 403 в NOT_FOUND бессмысленно (те же два ответа владелец токена получит от Keystone напрямую) и вредно — сломанное правило `identity:get_credential` выглядело бы как пустой аккаунт вместо проблемы с правами. Докблок переписан под фактическую, более узкую гарантию.

Деталь находки 3 не подтвердилась: ревьювер писал, что 403 на «бросающем» пути доходит как `INTERNAL_SERVER_ERROR`. `openstackErrorMiddleware` (`trpc.ts:15-60`) мапит 403 → `FORBIDDEN`; на сам вывод это не влияет.

После правок: typecheck чисто, lint 4/4, `format:check` чисто, `check-i18n` прошёл, 240 файлов / 5801 тест, 0 упавших.

**Отклонения от плана (5, все мелкие):** тест `createPermissionRouter` написан через реальный tRPC caller вместо приватной `checkSinglePermission` (по образцу `Compute/routers/permissionRouter.test.ts`); селектор в `index.test.tsx` уточнён до `/^Actions/` из-за новой кнопки «More Actions»; мок `create.mutate` в тесте модалки явно дописывает кред в стейт, симулируя refetch; в модалку добавлен `Loading…` для Connection Details, пока грузится `containers.status` (в псевдокоде плана этого не было, без него — краш на первом рендере); Step 15.3 выполнен частично — в `009_ceph_s3_bff.md` обновлены разделы `ec2Credentials` и `containers.status`, ~15 иллюстративных сниппетов дальше по файлу не тронуты (план помечал шаг как необязательный для CI).

**Не покрыто автотестами, проверить руками:** браузерный сценарий целиком (оба входа в модалку, копирование в буфер, реальный запрос AWS CLI выданными access/secret/endpoint/region, удаление последнего ключа, отсутствие секрета в React Query Devtools). Немецкий каталог получил пустые `msgstr` для новых строк — перевода не было, только extract.

# 📋 ПЛАН РЕАЛИЗАЦИИ: Управление S3-кредами (Ceph EC2 credentials) в Aurora

> Все пути — абсолютные от корня репо `/Users/kirylmishchuk/projects/SAP/aurora-dashboard`.
> Факты из задания перепроверены по живому коду на HEAD `bc9a5f96`; расхождения и уточнения отмечены в тексте.

---

## Принятые решения (разбор рисков с пользователем, 2026-09-29)

Этот раздел **имеет приоритет** над остальным текстом плана там, где они расходятся.

**Follow-up'ы не заводим — всё делается в рамках этой задачи.** Оба пункта, которые планировщик предлагал отложить (#29 `.find`, #30 `createPermissionRouter`), входят в скоуп.

1. **Permission-ключ на удаление — заводим отдельный** `storage:credentials:delete` → `"storage:credential_delete": "rule:storage_viewer"`. Переиспользование `storage:credentials:create` отклонено: в `storage.json` уже принято давать каждому действию свой ключ даже при одинаковом правиле (`container_policy_update`/`_delete`, `container_cors_update`/`_delete`, `container_lifecycle_update`/`_delete`), а один ключ навсегда лишил бы оператора возможности развести создание и удаление. **Вместе с ключом в этом же PR чинится `createPermissionRouter`** (см. Step 6) — иначе недостающее правило у консьюмера роняет весь bulk-`canUser`.
2. **`reveal` — mutation, не query.** Результат не попадает в query-кэш вообще и стирается `reset()`. Вариант «query с `gcTime: 0`» отклонён: корректность держалась бы на ручном `removeQueries` в каждой ветке закрытия. `list` секрет по-прежнему не отдаёт.
3. **endpoint/region — расширением `containers.status`**, отдельной процедуры не заводим. Проверено: `resolveS3Config` вызывается в `cephCredentialMiddleware` (`cephProcedure.ts:74`) безусловно для любой ceph-процедуры, поэтому 500 при отсутствии `ceph` в каталоге или пустом `CEPH_REGION` существует уже сегодня — новых режимов отказа не добавляется.
4. **Удаление ключа — с инлайновым подтверждением**, не в один клик. Операция необратима и мгновенно ломает внешних клиентов; вложенные модалки запрещены (B.5), поэтому подтверждение инлайновое.
5. **Модалка монтируется один раз** в общем хвосте `Ceph/Buckets/index.tsx` — ранние `return` заменяются вычислением `content`. Без этого удаление последнего ключа размонтирует модалку прямо во время операции.
6. **Лимит 2 — пре-чек в `create`, гонку принимаем.** Компенсирующее удаление не делаем: лишний ключ безвреден (все ключи пользователя в проекте — одна идентичность в RGW), а автоудаление на гонке хуже самой проблемы. Код ошибки — `CONFLICT`. Клиент дизейблит кнопку при двух ключах с объяснением.
7. **`.find` в `resolveEC2Credential` заменяется на детерминированный выбор** — сортировка по `id`, первый (см. Step 1). Проверено: у объекта credential в Keystone нет ни `expires_at`, ни `created_at` — только `id`, `type`, `user_id`, `project_id`, `blob`, поэтому «самый старый/новый» технически невозможен. Выбор остаётся произвольным, но становится воспроизводимым между запросами. Полноценная ротация с явным выбором активного ключа **не делается** — противоречит решению E.
8. **Step 13 включён в скоуп** (третья точка входа, ветка невалидных кредов). Заодно исправляется копирайт: слова «expired» там нет оснований — механизма истечения у EC2-кредов не существует, ветка срабатывает на `InvalidAccessKeyId` от RGW, что означает «ключ удалён либо сломалась расшифровка `blob`». Новый текст — безлично, без «Please», без «expired».
9. **Файлы кредов переезжают в новую папку `Ceph/Credentials/`** рядом с `Buckets/` и `Objects/`: в `Ceph/Buckets/` уже 52 файла, а креды — сущность уровня проекта, к бакетам отношения не имеющая. Переносятся `CredentialPrompt.tsx` и `CredentialPrompt.test.tsx`, туда же кладутся новые файлы. Импорты и баррель-реэкспорты правятся соответственно.
10. **CLI-сниппет — только AWS CLI**, плюс четыре значения (access key, secret, endpoint, region) отдельными полями с копированием у каждого. s3cmd не добавляем: он настраивается файлом `~/.s3cfg`, а не однострочником. Вкладку добавим, если придёт фидбэк.

**Дополнительно зафиксировано при разборе:** EC2-кред не привязан к сервису и не имеет поля для имени/метки — объект Keystone состоит из `id`, `type`, `user_id`, `project_id`, `blob`. Значит два ключа в списке визуально неразличимы, и единственная зацепка — access key ID: показывать его **целиком**, не обрезая. Предупреждение при удалении должно быть общим («любой клиент, использующий этот ключ, перестанет работать немедленно») — какой ключ где используется, мы не знаем и знать не можем.

---

## Overview

Пользователь Ceph/S3 сейчас не может ни увидеть свой access/secret, ни создать второй ключ, ни удалить старый: единственный экран про креды (`CredentialPrompt`) показывается только тогда, когда кредов нет вообще, и выбрасывает секрет, который сервер уже вернул. Добавляем одну модалку «Manage Credentials» — список всех EC2-кредов пользователя в проекте с раскрытием секрета по осознанному действию, созданием (лимит 2) и удалением, плюс endpoint/region и готовый CLI-сниппет. Две точки входа ведут в неё: оверфлоу-меню на списке бакетов и переписанный экран «Setup Required».

---

## Architecture Analysis

### Current state (проверено по коду)

**Сервер**

| Файл | Роль / что подтвердилось |
| --- | --- |
| `/packages/aurora/src/server/Storage/routers/ceph/ec2CredentialRouter.ts` | `list` (:46) — GET `credentials?user_id&type=ec2`, фильтр по `input.project_id`, **секрет вырезается** валидацией через `ec2CredentialSchema` (:72). `create` (:101) — BFF сам генерит `access`=`randomBytes(20).hex.toUpperCase()`, `secret`=`randomBytes(40).base64`, POST в Keystone, возвращает `Ec2CredentialWithSecret` (секрет уже доходит до браузера). `delete` (:164) — GET кред по id, 404 → идемпотентный `{success:true}`, сверка `credential.user_id !== userId \|\| credential.project_id !== projectId` (оба из токена) → `NOT_FOUND` (анти-энумерация, #1182), затем DELETE. |
| `/packages/aurora/src/server/Storage/middleware/resolveEC2Credential.ts` | Читает секрет на **каждом** Ceph-запросе: GET `credentials?user_id&type=ec2` → `.find(c => c.type==="ec2" && c.project_id===projectId)` → `JSON.parse(blob)` → `{credentialId, access, secret}`. Выбор ключа недетерминированный. |
| `/packages/aurora/src/server/Storage/cephProcedure.ts` | `resolveS3Config()` (:22) режет endpoint по `/swift/`, регион берёт из `ctx.cephRegion` (env `CEPH_REGION`, прокидывается в `server.ts:27` / `context.ts:425`). `cephCredentialMiddleware` (:71) кладёт в ctx `cephCredentials \| null`, `cephRegion`, `getCephClient`. **`endpoint` остаётся только в замыкании — в ctx его нет.** `cephProcedure` = этот middleware без требования кредов; `cephProtectedProcedure` добавляет FORBIDDEN/`NO_CEPH_CREDENTIALS`. |
| `/packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts:30` | `status: cephProcedure.input(projectScopedInputSchema).query(… => ({ hasCredentials: !!ctx.cephCredentials }))`. **Подтверждено: с клиента не вызывается нигде** (`grep containers.status` по `client/` — ноль попаданий), серверных тестов у неё тоже нет. |
| `/packages/aurora/src/server/Storage/types/ceph.ts:9-33, 181-189` | `ec2CredentialSchema{id,access,user_id,project_id}`, `ec2CredentialWithSecretSchema = .extend({secret})`, `s3StatusSchema = z.object({hasCredentials: z.boolean()})`. |
| `/packages/aurora/src/server/Storage/routers/permissionRouter.ts:86` | Единственный кредовый ключ `"storage:credentials:create" → "storage:credential_create"`. Докблок (:25-35) прямо фиксирует «read/list не гейтим» и «credential_create — viewer-tier, потому что это предусловие любого доступа к Ceph». |
| `/apps/dashboard/src/policies/storage.json` | `"storage:credential_create": "rule:storage_viewer"`. Правил на list/delete нет. **`_default` в файле отсутствует.** |
| `/packages/aurora/src/server/policies/createPermissionRouter.ts` | `canUser` — bulk-проверка; неизвестный ключ отбивается Zod'ом (`BAD_REQUEST`) до хендлера; `checkSinglePermission` вызывает `policy.check(rule)` **без try/catch**. |
| `/packages/aurora/src/server/Storage/constants.ts` | Место для `EC2_CREDENTIALS_MAX_PER_PROJECT` (уже есть прецедент импорта константы клиентом — `S3_PRESIGN_MAX_EXPIRY_SECONDS` тянется в `GeneratePresignedUrlModal.tsx`). |

**Клиент**

| Файл | Роль |
| --- | --- |
| `/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CredentialPrompt.tsx` | «S3 Object Storage: Setup Required», гейт по `permissions.canCreateCredential`, мутация `create` в `onSuccess` только `utils.storage.ceph.ec2Credentials.list.invalidate()` + `onSuccess()` — **возвращённый секрет выбрасывается**. |
| `.../Ceph/Buckets/index.tsx:230-236` | `if (error) { if (errorMessage === "NO_CEPH_CREDENTIALS") return <CredentialPrompt onSuccess={() => window.location.reload()} /> }`; ниже (:239-257) ветки Access denied / InvalidAccessKeyId — голый текст без действия. Zone 1 (:288-306): `SortInput` + `Button variant="primary" Create Bucket`, **оверфлоу-меню там нет**. |
| `.../Ceph/hooks/useCephPermissions.ts` | `PERMISSION_MAP` (21 ключ) `satisfies Record<keyof CephPermissions, string>`; один bulk-`canUser`, `staleTime/gcTime: Infinity`, fail-closed `DEFAULT_PERMISSIONS`. |
| `/packages/aurora/src/client/App.tsx:55` | Глобальный `staleTime: 60 * 1000` для всех запросов. |
| `/packages/aurora/src/client/components/ClipboardText.tsx` | `default`-экспорт, `{text, truncateAt, showTooltip}`, копирование через `navigator.clipboard`. |
| `/packages/aurora/src/client/hooks/useModalTracking.ts` | `{isOpen, actionPrefix}` → `{trackClose, markSubmitted, resetTracking}`. |

**Библиотека (juno-ui-components 9.4.0, `packages/aurora/node_modules/@cloudoperators/juno-ui-components`)**

- Есть `CodeBlock` (`{content \| children, wrap, size, copy=true, codeBlockFooter, lang, heading}`) — встроенная кнопка Copy. Ровно то, что нужно для CLI-сниппета (решение F).
- ⚠️ В `KnownIconsEnum` **нет** `visibility`/`visibilityOff`. Переключатель секрета делать текстовой кнопкой `Show`/`Hide`, не иконкой.
- Прецедент инлайн-удаления строки внутри модалки: `/packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/ManageAccessModal.tsx:283-291` (`Button size="small" icon="deleteForever" title progress disabled`).
- Прецедент «read-only операция как mutation, чтобы не кэшировалась»: `objectRouter.ts:400` `generatePresignedUrl: cephProtectedProcedure.…mutation(...)`.
- Прецедент оверфлоу-меню в Zone 1 рядом с primary-кнопкой: `.../Ceph/Objects/ObjectBrowserView.tsx:703-717` (`PopupMenu` → `PopupMenuToggle as="div"` → `Button icon="moreVert" title={t\`More Actions\`}` → `PopupMenuOptions`/`PopupMenuItem`), меню **слева** от primary-кнопки, обе внутри `Stack gap="0.5" alignment="center"`.
- Прецедент footer-only-Close: `.../Ceph/Buckets/EmptyBucketModal.tsx:213-221` (`modalFooter` + `Button variant="primary"` Close).

### Proposed changes (высокоуровнево)

1. **Сервер** — `reveal` (mutation, по `credentialId`, с той же проверкой владения, что у `delete`); лимит 2 в `create`; `containers.status` расширяется до `{hasCredentials, endpoint, region}`; `cephEndpoint` добавляется в ctx; новый permission-ключ `storage:credentials:delete`.
2. **Клиент** — новая `ManageCredentialsModal`, смонтированная **один раз** в `CephBuckets` вне всех ранних `return`; `CredentialPrompt` худеет до тонкого empty-state с кнопкой, открывающей ту же модалку; в Zone 1 появляется оверфлоу-меню с пунктом «Manage Credentials»; `window.location.reload()` уходит, вместо него точечные инвалидации.

**Почему так ложится в архитектуру.** Ничего нового в паттернах не изобретается: `reveal` повторяет структуру `delete`, `status` уже существует и лежит на `cephProcedure` (то есть работает, когда кредов ещё нет — критично, endpoint/region нужны и в пустом состоянии), модалка следует зонам/скелету из `.github/copilot-instructions.md`, вход через `moreVert` копирует `ObjectBrowserView`.

---

## Potential Problems & Mitigations

| Риск | Серьёзность | Митигация |
| --- | --- | --- |
| 🔴 **Новое правило в `storage.json` ломает Ceph-UI у консьюмера с форкнутой политикой.** policy-engine при отсутствии правила и отсутствии `_default` **бросает** (`policyEngine.ts:155`), а не возвращает `false`. `useCephPermissions` шлёт все ключи **одним** `canUser` → `canUser:163` прогоняет их через `.map` без `try/catch` → падает весь батч → `isError: true` + `DEFAULT_PERMISSIONS` → исчезают **все 21** Ceph-действие, а не только Delete. Докблок хука («covers operators whose storage.json is missing one of the newer Ceph rules») в этой части неверен. | ~~High~~ → **снят** | **Решение 1 разбора рисков: чиним `createPermissionRouter` в этом же PR** (Step 6, п.4–5) — `policy.check` в `try/catch` с `return false`, fail-closed становится по ключу. Правило всё равно добавляем в `apps/dashboard/src/policies/storage.json`, upgrade note в чейнджсете остаётся (без правила у оператора просто скроется кнопка Delete). Follow-up не заводим. |
| 🔒 **Секрет попадает в кэш TanStack Query и живёт там до конца сессии.** Глобальный `staleTime: 60s`, `gcTime` по умолчанию 5 мин; кэш виден в React Query Devtools и переживает закрытие модалки. | High | `reveal` оформляем **mutation**, а не query: результат мутации не попадает в query-кэш вообще и стирается `reset()`. Секреты держим в локальном `useState<Record<string,string>>`, чистим в `handleClose` вместе с `revealMutation.reset()`/`createMutation.reset()`. `list` **остаётся без секрета**. Ни `utils.….fetch()` (пишет в queryClient), ни расширение `list` не используем. |
| 🔴 **Изменение `s3StatusSchema` ломает существующие тесты и публичный тип.** `types/ceph.test.ts:322-332` утверждает `safeParse({hasCredentials:true}).success === true` — после добавления обязательных `endpoint`/`region` эти три ассерта упадут. `S3Status` экспортируется из публичного пакета. | Medium | Тесты обновляем в том же шаге. Для консьюмеров изменение аддитивное на чтение, ломающее на конструирование → `minor` в чейнджсете с явным упоминанием. |
| ⚠️ **TOCTOU на лимите 2.** Keystone не умеет атомарный constraint; два параллельных `create` пройдут пре-чек и дадут 3 ключа. | Low | Пре-чек + комментарий в коде о гонке. Компенсирующее удаление НЕ делаем: превышение на один ключ безвредно (нет квоты, нет расширения прав — все ключи одного пользователя в проекте мапятся в RGW на одну идентичность), а деструктивный откат на гонке добавляет режим отказа хуже самой проблемы. Клиент дизейблит кнопку при `length >= 2`. |
| ⚠️ **Удаление последнего/используемого ключа рвёт S3-сессию.** `resolveEC2Credential` на следующем запросе не найдёт ключ (или возьмёт другой) → `containers.list` упадёт в `NO_CEPH_CREDENTIALS`, пока модалка открыта. | Medium | После `delete` инвалидируем `containers.list` + `containers.status`; страница под модалкой перерисуется в `CredentialPrompt`, а модалка останется открытой — **это и есть причина, почему модалка монтируется вне ранних `return`**. В модалке — постоянный `Message variant="warning"` про то, что удаление немедленно ломает клиентов, использующих ключ. Удаление — двухшаговое инлайн-подтверждение (стековать модалки запрещено B.5). |
| ⚠️ **`CephBuckets` имеет три ранних `return`** (`isLoading`, `error`, и ветки внутри `error`), модалка не может быть смонтирована в одной из них без дублирования. | Medium | Рефактор `index.tsx`: ранние `return` заменяются на вычисление `content`, единый JSX-хвост рендерит `content` + модалку. Без этого при удалении последнего ключа модалка размонтируется прямо во время операции. |
| ⚠️ **`resolveS3Config` бросает обычный `Error`** при отсутствии `ceph` в каталоге сервисов или пустом `CEPH_REGION` → `containers.status` отдаёт 500 и модалка останется без endpoint/region. | Low | Не регрессия (так ведут себя все ceph-процедуры), но модалка должна деградировать: секция Connection Details при ошибке `status` показывает `Status status="error"` и **не блокирует** список ключей/создание/удаление. |
| ⚠️ **Пункт «Manage Credentials» не гейтится правами** (это чтение). Ревьювер может прочитать это как нарушение B.15 («create без permission-чека»). | Low | Пункт меню открывает модалку, а не мутирует; мутации внутри модалки гейтятся. Оформить комментарием в коде со ссылкой на докблок `useCephPermissions` («reads deliberately not gated»). |
| 🔒 **Секрет в DOM/скриншотах/скринкастах.** | Medium | Маскировка по умолчанию (`••••••••`), раскрытие только по явному `Show`, состояние не переживает закрытие модалки, CLI-сниппет с реальным секретом рендерится **только** для раскрытого ключа. |
| ⚠️ **`reveal` как mutation — семантический смелл** («мутация, которая ничего не мутирует»). | Low | Прецедент в том же домене: `objects.generatePresignedUrl` — тоже read-only mutation. Обосновать докблоком у процедуры. |
| ⚠️ **`.find` в `resolveEC2Credential` делает выбор ключа недетерминированным** — порядок ответа Keystone не гарантирован, а наша фича впервые делает возможным второй ключ. | ~~Known limitation~~ → **в скоупе** | **Решение 7 разбора рисков:** сортировка по `id`, берём первый (Step 1, п.5). Временных меток у credential нет (`RawCredential` — `id`/`type`/`project_id`/`blob`), поэтому «самый старый» невозможен; цель — воспроизводимость, а не «правильный» ключ. Метка «активный» по-прежнему не делается (решение E), полноценная ротация вне скоупа. |

---

## Prerequisites

- [ ] Ветка: работаем **локальными правками прямо в `main`** (HEAD `bc9a5f96`, дерево чистое, синхронизировано с `origin/main`). Новую ветку **не создавать**. Агент **не коммитит, не делает `git add`, не пушит, не создаёт PR** — коммит и пуш делает пользователь.
- [ ] `pnpm install` выполнен; Node ≥ 24, pnpm ≥ 10.
- [ ] Прочитать `.github/copilot-instructions.md` — ревью PR идёт по нему (в плане ниже помечены применимые правила B.x).
- [ ] **Follow-up'ы не заводим.** Оба отложенных пункта входят в скоуп: детерминированный выбор креда — в Step 1, починка `createPermissionRouter` — в Step 6.
- [ ] Не трогаем Swift — там EC2-креды не используются.

---

## Implementation Steps

### Step 1: Прокинуть endpoint в ctx, расширить `containers.status`, сделать выбор креда детерминированным

**Файлы:**
- `/packages/aurora/src/server/Storage/cephProcedure.ts`
- `/packages/aurora/src/server/Storage/middleware/resolveEC2Credential.ts`
- `/packages/aurora/src/server/Storage/types/ceph.ts`
- `/packages/aurora/src/server/Storage/routers/ceph/containerRouter.ts`

**Что сделать:**
1. В `cephCredentialMiddleware` (`cephProcedure.ts:71`) в объекте `next({ ctx: {...} })` добавить `cephEndpoint: endpoint` рядом с `cephRegion: region`. То же самое — в `cephUploadProcedure` (:174) для консистентности типа ctx.
2. Обновить докблоки обеих процедур (списки «Adds to context»): добавить строку `cephEndpoint: string — base S3 endpoint (Swift path suffix stripped)`.
3. В `types/ceph.ts:181` расширить схему:
   ```ts
   export const s3StatusSchema = z.object({
     hasCredentials: z.boolean(),
     /** Base S3 endpoint of the Ceph RGW for this region (Swift path suffix stripped). */
     endpoint: z.string(),
     /** Ceph-compatible region identifier the S3 client signs with. */
     region: z.string(),
   })
   ```
4. В `containerRouter.status` (`containerRouter.ts:30`) вернуть `{ hasCredentials: !!ctx.cephCredentials, endpoint: ctx.cephEndpoint, region: ctx.cephRegion }`. Добавить докблок: процедура умышленно на `cephProcedure` (не `cephProtectedProcedure`), потому что endpoint/region нужны UI и тогда, когда кредов ещё нет.

5. В `resolveEC2Credential.ts:53` заменить `.find` на детерминированный выбор — отфильтровать по `type === "ec2" && project_id === projectId`, отсортировать по `id` (`localeCompare`) и взять первый. Добавить комментарий: у credential в Keystone нет временных меток (`RawCredential` — только `id`, `type`, `project_id`, `blob`), поэтому «самый старый» невозможен; сортировка по `id` даёт не «правильный» ключ, а **один и тот же** между запросами — до этой фичи второй ключ создать было негде, и порядок ответа Keystone не имел значения.

**Expected outcome:** `storage.ceph.containers.status` отдаёт всё, что нужно модалке для Connection Details, без кредов; Aurora при двух ключах стабильно ходит одним и тем же.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

---

### Step 2: Константа лимита и маркер ошибки

**Файл:** `/packages/aurora/src/server/Storage/constants.ts`

**Что сделать:** дописать в конец файла (в стиле остальных констант — с содержательным докблоком, а не однострочником):
```ts
/**
 * Maximum number of EC2 (S3) credentials one user may hold in one project.
 *
 * Mirrors AWS's two-access-key limit: two is exactly enough to rotate without downtime
 * (create the new key, migrate clients, delete the old one) and not enough to accumulate
 * a zoo of forgotten keys nobody can attribute. Keystone and RGW impose no limit of their
 * own, so this is the only ceiling that exists.
 *
 * All of a user's keys in a project map to the SAME RGW identity — an extra key grants no
 * extra access, which is why exceeding the limit by one on a race is harmless (see
 * ec2CredentialRouter.create).
 */
export const EC2_CREDENTIALS_MAX_PER_PROJECT = 2

/**
 * Machine-readable marker thrown by `ec2Credentials.create` when the per-project key limit
 * is reached. Mirrors the NO_CEPH_CREDENTIALS convention in `cephProcedure.ts`: the client
 * branches on this constant instead of matching prose that i18n/refactors would break.
 */
export const EC2_CREDENTIAL_LIMIT_REACHED = "EC2_CREDENTIAL_LIMIT_REACHED" as const
```

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

---

### Step 3: Вынести проверку владения кредом в хелпер

**Файл:** `/packages/aurora/src/server/Storage/routers/ceph/ec2CredentialRouter.ts`

**Что сделать:**
1. Добавить в файл (между блоком internal-типов и роутером) функцию:
   ```ts
   /**
    * Fetches one credential and verifies it belongs to the caller.
    *
    * Both user_id and project_id come from the (already rescoped) token, never from input —
    * that is what makes the check an authorization check and not a filter the caller controls.
    * A credential owned by someone else is reported as NOT_FOUND, not FORBIDDEN, so the
    * response can't be used to confirm that a credential ID exists (IDOR hardening, #1182).
    *
    * Returns null when Keystone answers 404, letting the caller choose its own semantics:
    * `delete` treats it as idempotent success, `reveal` as NOT_FOUND.
    */
   async function fetchOwnedCredential(
     ctx: /* AuroraPortalContext-shaped ctx of projectScopedProcedure */,
     credentialId: string
   ): Promise<RawCredential | null>
   ```
   Тело — один в один текущие шаги 1–2 из `delete` (`ec2CredentialRouter.ts:182-213`): GET `credentials/${credentialId}`; 404 → `null`; 401 → `UNAUTHORIZED`; 403 → `FORBIDDEN`; иное `!ok` → `INTERNAL_SERVER_ERROR` «Failed to fetch credential for verification»; несовпадение `user_id`/`project_id` → `NOT_FOUND` «Credential not found».
   Тип `RawCredential` уже объявлен в файле (:16), но у одиночного GET ответ — `{ credential: RawCredential }`; типизировать соответственно.
2. Переписать `delete` на использование хелпера: `const credential = await fetchOwnedCredential(ctx, input.credentialId); if (!credential) return { success: true }` → далее DELETE как сейчас. **Поведение не меняется** (это важно для существующих тестов `delete` — они должны пройти без правок).

**Expected outcome:** одна реализация проверки владения на `delete` и будущий `reveal` — невозможно разойтись в семантике изоляции.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage/routers/ceph/ec2CredentialRouter.test.ts` — все существующие тесты зелёные без изменений.

---

### Step 4: Процедура `reveal`

**Файлы:**
- `/packages/aurora/src/server/Storage/types/ceph.ts`
- `/packages/aurora/src/server/Storage/routers/ceph/ec2CredentialRouter.ts`

**Что сделать:**
1. В `types/ceph.ts` рядом с `deleteEc2CredentialInputSchema` (:23) добавить:
   ```ts
   export const revealEc2CredentialInputSchema = projectScopedInputSchema.extend({
     credentialId: z.string().min(1),
   })
   ```
2. В `ec2CredentialRouter` добавить процедуру **между** `create` и `delete`:
   ```ts
   /**
    * Returns one credential including its secret key.
    *
    * EC2 credentials in Keystone are reversible by design: the blob is stored encrypted and
    * decrypted on every read, so `GET /v3/credentials/{id}` hands back {"access","secret"}.
    * This is NOT an Application Credential (whose secret is hashed and unrecoverable) — the
    * BFF already reads this exact secret on every single Ceph request
    * (`middleware/resolveEC2Credential.ts`), so exposing it to its own owner adds no new
    * disclosure surface.
    *
    * Modelled as a mutation rather than a query on purpose: a tRPC query result lands in the
    * TanStack Query cache, where the secret would survive the modal being closed and show up
    * in devtools. Mutation results never enter the query cache and are dropped by reset().
    * Same trick as `objects.generatePresignedUrl`.
    */
   reveal: projectScopedProcedure
     .input(revealEc2CredentialInputSchema)
     .mutation(async ({ ctx, input }): Promise<Ec2CredentialWithSecret> => { ... })
   ```
   Тело: `const credential = await fetchOwnedCredential(ctx, input.credentialId)`; `if (!credential) throw new TRPCError({ code: "NOT_FOUND", message: "Credential not found" })`; `JSON.parse(credential.blob)` в try/catch (по образцу `list`, :85-93, с `INTERNAL_SERVER_ERROR` на невалидном blob); валидация через `ec2CredentialWithSecretSchema.safeParse({id, access, secret, user_id, project_id})`; `!success` → `INTERNAL_SERVER_ERROR`.
   Импортировать `revealEc2CredentialInputSchema` из `../../types/ceph`.

**Expected outcome:** `storage.ceph.ec2Credentials.reveal` отдаёт секрет владельцу и `NOT_FOUND` всем остальным.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

---

### Step 5: Лимит 2 в `create`

**Файл:** `/packages/aurora/src/server/Storage/routers/ceph/ec2CredentialRouter.ts`

**Что сделать:**
1. Импортировать `EC2_CREDENTIALS_MAX_PER_PROJECT`, `EC2_CREDENTIAL_LIMIT_REACHED` из `../../constants`.
2. В `create`, **до** генерации ключей и POST (то есть сразу после проверки `userId`, ~:108), вставить пре-чек:
   ```ts
   const listResponse = await identityService.get("credentials", {
     queryParams: { user_id: userId, type: "ec2" },
   })
   if (!listResponse.ok) {
     throw new TRPCError({
       code: "INTERNAL_SERVER_ERROR",
       message: "Failed to verify the existing credential count",
     })
   }
   const existing: CredentialsListResponse = await listResponse.json()
   const existingForProject = (existing.credentials ?? []).filter(
     (c) => c.type === "ec2" && c.project_id === input.project_id
   )
   if (existingForProject.length >= EC2_CREDENTIALS_MAX_PER_PROJECT) {
     throw new TRPCError({ code: "CONFLICT", message: EC2_CREDENTIAL_LIMIT_REACHED })
   }
   ```
   При сбое листинга — **не создаём** (fail-closed), это осознанно.
3. Комментарием зафиксировать гонку:
   ```ts
   // Check-then-create, not atomic: Keystone offers no uniqueness/count constraint on
   // credentials, so two concurrent creates can both pass this check and leave three keys.
   // Deliberately not compensated by deleting the key we just made — all of a user's keys
   // in a project map to the same RGW identity, so one extra key grants nothing and costs
   // no quota, while a destructive rollback on a race is a strictly worse failure mode.
   // The UI additionally disables Create at the limit.
   ```
4. Обновить докблок `create` — упомянуть лимит.

**Expected outcome:** третий ключ отбивается `CONFLICT`/`EC2_CREDENTIAL_LIMIT_REACHED`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

---

### Step 6: Permission-ключ `storage:credentials:delete`

**Файлы:**
- `/packages/aurora/src/server/Storage/routers/permissionRouter.ts`
- `/apps/dashboard/src/policies/storage.json`
- `/packages/aurora/src/server/policies/createPermissionRouter.ts`
- `/packages/aurora/src/server/policies/createPermissionRouter.test.ts`

**Что сделать:**
1. В `STORAGE_MAPPINGS` в секцию `// Credential Operations` (:85-86) добавить:
   ```ts
   "storage:credentials:delete": { engine: "storage", rule: "storage:credential_delete" },
   ```
   Ключ соответствует `PERMISSION_KEY_PATTERN.md`: scope `storage` (не `ceph`), ресурс `credentials` (plural, snake_case), действие `delete` (стандартный CRUD-глагол).
2. Дополнить докблок над `STORAGE_MAPPINGS` (там уже есть абзац про viewer-tier у `credentials:create`):
   ```
   * - `storage:credentials:delete` is viewer-tier for the same reason as `create`: a user's
   *   EC2 credential is their own self-service artifact, and gating deletion above creation
   *   would trap a `storage_viewer` at the two-key limit with no way to rotate.
   ```
3. В `storage.json` сразу после `"storage:credential_create"` добавить `"storage:credential_delete": "rule:storage_viewer",`.

4. **Починить fail-closed в `createPermissionRouter`** (решение 1 разбора рисков — делается здесь, а не follow-up'ом). Сейчас `checkSinglePermission:130` вызывает `policy.check(mapping.rule)` без `try/catch`, а `canUser:163` прогоняет ключи через `.map` — значит бросок policy-engine (`policyEngine.ts:155`: `Rule 'X' not found and no _default rule available`; `_default` в `storage.json` отсутствует, проверено) роняет **весь** батч, а не один ключ. У `useCephPermissions`, который шлёт все 21 Ceph-ключа одним запросом, это скрывает весь домен.
   Обернуть вызов `policy.check` в `try/catch` с `return false` и `console.error`, докблоком объяснив: fail-closed должен быть **по ключу**, а не «в кирпич»; молчаливый `false` не спрячет от нас опечатку в правиле, потому что наш `storage.json` лежит в этом же репо и покрыт тестами. `TRPCError` про отсутствующий engine (`:122`) оставить как есть — это ошибка конфигурации роутера, а не политики.
5. Тест в `createPermissionRouter.test.ts`: движок без запрошенного правила и без `_default` → `canUser` с массивом ключей возвращает `false` на недостающем и корректные значения на остальных, не бросая.

**⚠️ К упоминанию в чейнджсете:** операторам с форкнутым `storage.json` стоит добавить `storage:credential_delete`, иначе кнопка Delete будет скрыта. После п.4 недостающее правило больше **не** роняет остальные действия домена — но upgrade note всё равно нужен.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/policies/createPermissionRouter.test.ts`.

---

### Step 7: Серверные тесты

**Файлы:**
- `/packages/aurora/src/server/Storage/routers/ceph/ec2CredentialRouter.test.ts` (448 строк, расширяем)
- `/packages/aurora/src/server/Storage/routers/ceph/containerRouter.test.ts`
- `/packages/aurora/src/server/Storage/types/ceph.test.ts` (🔴 обязательная правка: :322-332)

**Что сделать:**
1. `types/ceph.test.ts:322-332` — `s3StatusSchema` теперь требует `endpoint` и `region`: обновить три существующих ассерта (`{hasCredentials:true}` → `{hasCredentials:true, endpoint:"https://…", region:"…"}`), добавить кейсы «отсутствует endpoint → fail», «отсутствует region → fail».
2. `ec2CredentialRouter.test.ts` — новые `describe` в стиле файла (локальная фабрика `createMockContext` поверх `createBaseMockContext` из `./mockContext`, переопределяющая `ctx.mockIdentity.get/post/del`):
   - `ec2Credentials.reveal`:
     - возвращает `{id, access, secret, user_id, project_id}` для своего креда;
     - `NOT_FOUND`, когда `credential.user_id !== TEST_USER_ID` (чужой пользователь);
     - `NOT_FOUND`, когда `credential.project_id !== TEST_PROJECT_ID` (чужой проект);
     - `NOT_FOUND` на 404 от Keystone;
     - `UNAUTHORIZED` на 401, `FORBIDDEN` на 403;
     - `INTERNAL_SERVER_ERROR` на невалидном JSON в `blob`;
     - `UNAUTHORIZED` при `shouldFailAuth = true`;
     - **не** вызывает `del` (проверка, что reveal не мутирует).
   - `ec2Credentials.create` (лимит):
     - при нуле существующих кредов создаёт (`post` вызван);
     - при одном существующем креде создаёт;
     - при двух → бросает `CONFLICT` с `message === EC2_CREDENTIAL_LIMIT_REACHED` и **`post` не вызван**;
     - креды другого проекта в счёт не идут (два креда в `other-project` + ноль в текущем → создаёт);
     - сбой листинга (`{ok:false}`) → `INTERNAL_SERVER_ERROR` и `post` не вызван.
   - `ec2Credentials.delete` — существующие тесты должны остаться зелёными без правок (регресс-контроль рефактора из Step 3).
3. `containerRouter.test.ts` — новый `describe("containers.status")`: возвращает `hasCredentials: true` + `endpoint`/`region` из мок-контекста; при `hasCredentials: false` (опция `createMockContext({hasCredentials:false})`) — `hasCredentials:false`, но `endpoint`/`region` всё равно присутствуют (это и есть ключевое свойство: данные доступны без кредов).
   ⚠️ Учти: в `mockContext.ts` `ctx.cephRegion = TEST_CEPH_REGION` (`"ceph-objectstore-st1-test-region"`), а `endpoint` по умолчанию `"https://test-ceph.example.com"` (без `/swift/`, так что срезание не сработает — при желании добавить отдельный кейс с `endpoint: "https://rgw.example.com/swift/v1/AUTH_x"` и проверить срез).

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage`.

---

### Step 8: `canDeleteCredential` в `useCephPermissions`

**Файл:** `/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/hooks/useCephPermissions.ts`

**Что сделать:**
1. В интерфейс `CephPermissions` добавить `canDeleteCredential: boolean` (после `canCreateCredential`).
2. В `PERMISSION_MAP` добавить `canDeleteCredential: "storage:credentials:delete",`.
   Массивы `PERMISSION_KEYS` / `PERMISSION_REQUEST` и `DEFAULT_PERMISSIONS` выводятся из карты — править их не нужно, `satisfies` поймает рассинхрон.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

---

### Step 9: Тосты для кредов

**Файл (новый):** `/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Credentials/CredentialToastNotifications.tsx`

**Что сделать:** по образцу `BucketToastNotifications.tsx` (тот же каталог) экспортировать одну функцию:
```tsx
export const getCredentialDeletedToast = (accessKey: string): ToastReturnType => ({
  message: <Trans>Access key deleted</Trans>,
  description: <Trans>Access key "{accessKey}" was permanently deleted.</Trans>,
})
```
**Только удаление.** Для создания тоста **нет** (B.11: нельзя совмещать success-тост с инлайн-подтверждением — подтверждением создания служит показанный в модалке секрет). Ошибки create/delete/reveal — не тосты, а `<Message variant="error">` внутри модалки (B.16: actionable error ≠ toast).

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck`.

---

### Step 10: `ManageCredentialsModal`

**Файл (новый):** `/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Credentials/ManageCredentialsModal.tsx`

> Каталог `Buckets/` выбран потому, что там уже лежит `CredentialPrompt.tsx` и находится баррель `Buckets/index.tsx`, из которого реэкспортируются все Ceph-модалки. Отдельная папка `Ceph/Credentials/` — в Open Questions.

**Props:** `{ isOpen: boolean; onClose: () => void }`.

**Данные:**
```tsx
const projectId = useProjectId()
const utils = trpcReact.useUtils()
const { permissions, isLoading: isLoadingPermissions, isError: isPermissionsError } = useCephPermissions(projectId)

const { data: credentials = [], isLoading: isLoadingCredentials, error: listError } =
  trpcReact.storage.ceph.ec2Credentials.list.useQuery(
    { project_id: projectId }, { enabled: isOpen && !!projectId, retry: false }
  )

const { data: s3Status, error: statusError } =
  trpcReact.storage.ceph.containers.status.useQuery(
    { project_id: projectId }, { enabled: isOpen && !!projectId, retry: false, staleTime: Infinity }
  )
```
`enabled: isOpen` — не тянем ничего при простом открытии страницы бакетов. `staleTime: Infinity` у `status` — endpoint/region это константы деплоймента.

**Локальное состояние:**
```tsx
const [revealedSecrets, setRevealedSecrets] = useState<Record<string, string>>({})
const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null)
const [actionError, setActionError] = useState<string | null>(null)
```

**Мутации:**
- `revealMutation = trpcReact.storage.ceph.ec2Credentials.reveal.useMutation()` — вызов через `mutateAsync`, при успехе `setRevealedSecrets(p => ({...p, [id]: cred.secret}))`, затем сразу `revealMutation.reset()` (чтобы секрет не задерживался в mutation-state).
- `createMutation = …create.useMutation()` — `onSuccess(cred)`: `setRevealedSecrets(p => ({...p, [cred.id]: cred.secret}))` (новый ключ показываем сразу раскрытым — решение G), затем `utils.storage.ceph.ec2Credentials.list.invalidate()`, `utils.storage.ceph.containers.list.invalidate()`, `utils.storage.ceph.containers.status.invalidate()`. **Никакого `window.location.reload()`.**
  `onError(err)`: если `err.message === EC2_CREDENTIAL_LIMIT_REACHED` (импорт из `@/server/Storage/constants`) — показать человеческий текст про лимит, иначе — `err.message`; в обоих случаях в `setActionError`.
- `deleteMutation = …delete.useMutation()` — `onSuccess`: те же три инвалидации, `setRevealedSecrets` без удалённого id, `setPendingDeleteId(null)`, тост `getCredentialDeletedToast(accessKey)`. `onError`: `setActionError`.

**Аналитика:** `useModalTracking({ isOpen, actionPrefix: "storage.ceph.credentials.manage" })`; `markSubmitted()` в `handleCreate`, `trackClose()` + `resetTracking()` в `handleClose`.

**`handleClose`** (🔒 гигиена секретов): `trackClose(); setRevealedSecrets({}); setPendingDeleteId(null); setActionError(null); revealMutation.reset(); createMutation.reset(); deleteMutation.reset(); resetTracking(); onClose()`.

**Скелет (строго по B.5):**
```tsx
const isBusy = createMutation.isPending || deleteMutation.isPending || revealMutation.isPending
const atLimit = credentials.length >= EC2_CREDENTIALS_MAX_PER_PROJECT

<Modal
  title={t`Manage S3 Credentials`}
  open={isOpen}
  size="large"
  onCancel={handleClose}
  onConfirm={handleCreate}
  confirmButtonLabel={t`Create Access Key`}
  confirmButtonVariant="primary"
  cancelButtonLabel={t`Close`}
  disableConfirmButton={!permissions.canCreateCredential || atLimit || isBusy || isLoadingCredentials || isLoadingPermissions}
  disableCancelButton={isBusy}
  disableCloseButton={isBusy}
>
```
Ровно одна primary-кнопка (`Create Access Key`), `Close` слева от неё. `confirmButtonVariant="primary"`, не `primary-danger` — создание не деструктивно.

**Тело — `<Stack direction="vertical" gap="6">`:**

1. `{actionError && <Message variant="error" text={actionError} className="mb-4" onDismiss={() => setActionError(null)} />}`
2. **Connection Details** (всегда видна, работает при нуле ключей — решение F):
   - `<ContentHeading><Trans>Connection Details</Trans></ContentHeading>`
   - `statusError` → `<Status status="error" title={t\`Connection Details Unavailable\`} body={…} />`, но **список ключей продолжает рендериться**.
   - иначе `<DescriptionList>`: `Endpoint URL` → `<ClipboardText text={s3Status.endpoint} />`; `Region` → `<ClipboardText text={s3Status.region} />`.
     (`ClipboardText` — **default**-импорт: `import ClipboardText from "@/client/components/ClipboardText"`.)
3. **Access Keys**:
   - `<ContentHeading><Trans>Access Keys</Trans></ContentHeading>`
   - Постоянный `<Message variant="warning">`: `<Trans>An access key stops working the moment it is deleted. Any S3 client still configured with it loses access.</Trans>` (B.16: persistent constraint → Message, не тост; `warning`, не `danger` — это не подтверждение деструктивного действия, а постоянное предупреждение).
   - `{atLimit && <Message variant="info" text={t\`A project allows at most ${EC2_CREDENTIALS_MAX_PER_PROJECT} access keys per user. Delete an existing key to create a new one.\`} />}` — объяснение задизейбленной кнопки (B.8: permission/ограничение известно, фича доступна всем → disabled + объяснение).
   - `{!isLoadingPermissions && !permissions.canCreateCredential && <Message variant="info" title={t\`Insufficient Permissions\`}>…</Message>}` — аналогично для отсутствия права на создание.
   - `isLoadingCredentials` → `<Status status="progress" title={t\`Loading Access Keys...\`} />`.
   - `listError` → `<Status status="error" title={t\`Could Not Load Access Keys\`} body={listError.message} />`.
   - Иначе `<DataGrid columns={3}>`:
     - `<DataGridRow><DataGridHeadCell>Access Key ID</DataGridHeadCell><DataGridHeadCell>Secret Access Key</DataGridHeadCell><DataGridHeadCell /></DataGridRow>` (третья — колонка действий, без лейбла, B.15).
     - Пусто → одна строка `<DataGridCell colSpan={3}><Status status="empty" title={t\`No Access Keys\`} body={t\`Create an access key to connect an S3 client to this project.\`} /></DataGridCell>` (B.6: заголовки колонок остаются видимыми).
     - Строка ключа:
       - Access: `<ClipboardText text={cred.access} />`
       - Secret: если `revealedSecrets[cred.id]` — `<ClipboardText text={revealedSecrets[cred.id]} />` + `<Button size="small" variant="subdued" onClick={hide}><Trans>Hide</Trans></Button>`; иначе `<span aria-label={t\`Secret access key hidden\`}>••••••••••••</span>` + `<Button size="small" variant="subdued" progress={revealMutation.isPending && revealingId === cred.id} onClick={reveal}><Trans>Show</Trans></Button>`.
         ⚠️ Иконок `visibility`/`visibilityOff` в Juno 9.4.0 **нет** — только текстовые кнопки.
       - Действия: если `pendingDeleteId === cred.id` — инлайн-подтверждение `<Stack gap="2"><Button size="small" variant="primary-danger" progress={deleteMutation.isPending} onClick={confirmDelete}><Trans>Delete</Trans></Button><Button size="small" variant="subdued" onClick={() => setPendingDeleteId(null)}><Trans>Cancel</Trans></Button></Stack>`; иначе `{permissions.canDeleteCredential && <Button size="small" icon="deleteForever" title={t\`Delete Access Key\`} aria-label={t\`Delete Access Key\`} disabled={isBusy} onClick={() => setPendingDeleteId(cred.id)} data-testid={\`delete-credential-${cred.id}\`} />}`.
         Двухшаговое инлайн-подтверждение, а не вложенная модалка — B.5 запрещает стекать модалки; без таймаута (паттерн с 3-секундным таймаутом из #1247 был убран в #1303).
4. **CLI-сниппет** — рендерится **только** для раскрытых ключей (решение F), под таблицей:
   ```tsx
   <CodeBlock size="auto" wrap copy heading={t`AWS CLI`}>
     {`AWS_ACCESS_KEY_ID=${cred.access} \\\nAWS_SECRET_ACCESS_KEY=${secret} \\\naws --endpoint-url ${endpoint} --region ${region} s3 ls`}
   </CodeBlock>
   ```
   `CodeBlock` из `@cloudoperators/juno-ui-components` уже несёт кнопку Copy (`copy` по умолчанию `true`) — свой копировальщик не писать.

**Порядок импортов — B.13:** react → `@lingui/react/macro` → `@/client/trpcClient` → juno → `@/server/Storage/constants` → `@/client/hooks/…`, `@/client/components/ClipboardText` → `./CredentialToastNotifications` → `../hooks/useCephPermissions`.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora typecheck && pnpm --filter @cobaltcore-dev/aurora lint`.

---

### Step 11: Переписать `CredentialPrompt` в тонкую обёртку

**Файл (переезжает):** `/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/CredentialPrompt.tsx` → `/…/Ceph/Credentials/CredentialPrompt.tsx`

**Что сделать:** файл и имя компонента **сохраняем** (меньше churn, тест уже существует), контракт меняем:
1. Props: `{ onManageCredentials: () => void }` вместо `{ onSuccess: () => void }`.
2. Удалить целиком: `createMutation`, `utils`, `toast`, `useCephPermissions`, ветки `isLoadingPermissions` / `isPermissionsError` / `Insufficient permissions`. Вся логика прав и создания теперь живёт в модалке — вместо параллельной реализации гейта остаётся один источник правды (решение C).
3. Оставить: заголовок + пояснение + одна кнопка.
   ```tsx
   <Stack direction="vertical" gap="4" className="mt-8 max-w-lg">
     <h2 className="text-lg font-semibold"><Trans>S3 Object Storage: Setup Required</Trans></h2>
     <p className="text-theme-default">
       <Trans>Access to S3 Object Storage requires an access key (access key ID + secret access key). The key authenticates requests to the Ceph storage backend.</Trans>
     </p>
     <div>
       <Button variant="primary" onClick={onManageCredentials}><Trans>Manage Credentials</Trans></Button>
     </div>
   </Stack>
   ```
   Текст переписан под B.19: без «Click the button below», без «You only need to do this once» (с лимитом 2 это уже неправда), безличный залог.

**Expected outcome:** экран Setup Required и оверфлоу-меню ведут в одну и ту же модалку.

---

### Step 12: Перестроить `Ceph/Buckets/index.tsx` — единая точка монтирования + вход в меню

**Файл:** `/packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/index.tsx`

**Что сделать:**
1. Добавить состояние `const [credentialsModalOpen, setCredentialsModalOpen] = useState(false)`.
2. 🔴 **Убрать ранние `return`.** Сейчас их три ветки (`isLoading` :225-227, `NO_CEPH_CREDENTIALS` :234-236, прочие ошибки :242-260). Преобразовать в локальную функцию `renderContent()` (или переменную `content`), а единственный `return` компонента сделать таким:
   ```tsx
   return (
     <div className="relative">
       {renderContent()}
       <ManageCredentialsModal
         isOpen={credentialsModalOpen}
         onClose={() => setCredentialsModalOpen(false)}
       />
     </div>
   )
   ```
   Без этого модалка размонтируется, как только удаление последнего ключа переведёт страницу в состояние `NO_CEPH_CREDENTIALS`.
   ⚠️ Существующий основной `return` уже обёрнут в `<div className="relative">` — перенести обёртку наружу, не продублировать.
3. Ветку `NO_CEPH_CREDENTIALS` заменить на `<CredentialPrompt onManageCredentials={() => setCredentialsModalOpen(true)} />`. `window.location.reload()` удалить (решение G — обновление делают инвалидации внутри модалки).
4. В Zone 1 (:288-306) добавить оверфлоу-меню **слева** от `Create Bucket`, копируя `ObjectBrowserView.tsx:703-717`:
   ```tsx
   <Stack gap="0.5" alignment="center">
     <PopupMenu className="flex items-center">
       <PopupMenuToggle as="div">
         <Button icon="moreVert" title={t`More Actions`} aria-label={t`More Actions`} />
       </PopupMenuToggle>
       <PopupMenuOptions>
         {/* Not permission-gated: opening the modal is a read. Mutations inside it are gated
             (see the useCephPermissions docblock — reads are deliberately never gated). */}
         <PopupMenuItem
           label={t`Manage Credentials`}
           onClick={() => setCredentialsModalOpen(true)}
           data-testid="manage-credentials-action"
         />
       </PopupMenuOptions>
     </PopupMenu>
     {permissions.canCreateBucket && (
       <Button variant="primary" className="whitespace-nowrap" onClick={() => setCreateModalOpen(true)}>
         <Trans>Create Bucket</Trans>
       </Button>
     )}
   </Stack>
   ```
   `PopupMenu`, `PopupMenuToggle`, `PopupMenuOptions`, `PopupMenuItem` уже импортированы в файле (:13-16).
5. В баррель-реэкспорты (:36-45) добавить `export { ManageCredentialsModal } from "./ManageCredentialsModal"`.

**Expected outcome:** пользователь с кредами видит «Manage Credentials» в меню; пользователь без кредов — кнопку на экране Setup Required; обе ведут в одну модалку; после создания ключа список бакетов подгружается без перезагрузки страницы.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test src/client/routes/_auth/projects/\$projectId/storage/-components/Ceph/Buckets`.

---

### Step 13: действие в ветке невалидных кредов

**Файл:** тот же `index.tsx`, ветка :239-257.

Сейчас там написано «Your S3 credentials are invalid or expired. Please try creating new credentials» — но действовать нечем, и текст нарушает B.19 («Please», притяжательное «Your»). Предлагается:
- перевести ветку на `<Status status="error" title={…} body={…} action={<ButtonRow><Button onClick={() => setCredentialsModalOpen(true)}><Trans>Manage Credentials</Trans></Button></ButtonRow>} />` (B.6 требует actionable error-состояния);
- переписать копирайт безлично, без «Please».

**Слово «expired» из текста убрать.** Механизма истечения у EC2-кредов не существует: объект credential в Keystone не имеет ни `expires_at`, ни `created_at`. Ветка срабатывает на `InvalidAccessKeyId` от RGW, что означает «ключ удалён в Keystone (пользователем из другого места или админом) либо сломалась расшифровка `blob`» — причины не временные. Текст в духе «Your S3 credentials are no longer valid. They may have been deleted.» плюс кнопка.

Шаг **включён в скоуп** (решение 8 разбора рисков) — это третья точка входа сверх двух согласованных.

---

### Step 14: Клиентские тесты

**Файлы:**
- `/…/Ceph/Credentials/ManageCredentialsModal.test.tsx` (новый)
- `/…/Ceph/Credentials/CredentialPrompt.test.tsx` (переезжает и переписывается)
- `/…/Ceph/Buckets/index.test.tsx` (дополнить)

**Образцы стиля:** `CredentialPrompt.test.tsx` (vi.hoisted-моки tRPC, `vi.mock("@/client/hooks/useProjectId")`, мок `useCephPermissions` через изменяемые `let`-флаги, мок juno-`toast` через `importOriginal`) и `index.test.tsx` (vi.hoisted для Router/Route, моки дочерних компонентов). Окружение — `jsdom`.

**`ManageCredentialsModal.test.tsx`:**
- [ ] секреты по умолчанию замаскированы: в DOM есть маска, нет `TEST_SECRET`, у каждой строки есть кнопка `Show`;
- [ ] клик `Show` → вызван `reveal.mutateAsync` с `{project_id, credentialId}` → секрет отрендерен → кнопка стала `Hide`; клик `Hide` → секрет исчез из DOM;
- [ ] создание: клик по confirm-кнопке → вызван `create.mutate` → секрет нового ключа виден сразу → инвалидированы `ec2Credentials.list`, `containers.list`, `containers.status`; **тоста об успехе нет**;
- [ ] `create` c `message === "EC2_CREDENTIAL_LIMIT_REACHED"` → в модалке `Message variant="error"` с текстом про лимит, модалка не закрылась;
- [ ] при `credentials.length === 2` кнопка создания задизейблена и отрендерен info-`Message` про лимит;
- [ ] при `canCreateCredential === false` кнопка задизейблена + info-`Message` (не скрыта — B.8);
- [ ] удаление: первый клик по кнопке корзины → появилось инлайн-подтверждение, `delete.mutate` **не** вызван; клик `Delete` → вызван с нужным `credentialId` → тост `getCredentialDeletedToast` → три инвалидации; клик `Cancel` → подтверждение свёрнуто;
- [ ] при `canDeleteCredential === false` кнопки удаления нет;
- [ ] пустое состояние: нет ключей → `Status status="empty"` c «No Access Keys», заголовки колонок на месте;
- [ ] Connection Details: endpoint и region отрендерены и при нуле ключей; при ошибке `status` — `Status status="error"`, но таблица ключей рендерится;
- [ ] 🔒 закрытие модалки чистит секреты: `Show` → закрыть (`onCancel`) → открыть заново → секрет снова замаскирован, `reveal` не вызывался повторно автоматически;
- [ ] CLI-сниппет появляется только после раскрытия и содержит endpoint, region и access key.

**`CredentialPrompt.test.tsx`:** переписать целиком под новый контракт — рендерит заголовок/текст, клик по `Manage Credentials` вызывает `onManageCredentials`. Удалить всё, что касается мутации, toast и permissions (теперь этого в компоненте нет).

**`index.test.tsx`:** добавить — в Zone 1 есть пункт `Manage Credentials` (`data-testid="manage-credentials-action"`), клик открывает модалку; при `error.message === "NO_CEPH_CREDENTIALS"` рендерится `CredentialPrompt`, и модалка смонтирована в том же дереве (проверка, что рефактор ранних `return` состоялся); проверить, что `window.location.reload` больше не вызывается.

**Verification:** `pnpm --filter @cobaltcore-dev/aurora test`.

---

### Step 15: i18n, чейнджсет, документация

1. **i18n:** `pnpm check-i18n` (lingui extract + compile, только `packages/aurora`). Все новые строки — через `<Trans>` / `` t`…` `` из `@lingui/react/macro` / `@lingui/core/macro`; в `packages/aurora` это дополнительно enforce'ит `eslint-plugin-lingui`. Ожидай изменений в `.po`-каталогах — они часть диффа.
2. **Чейнджсет:** нужен, **`minor`** для `"@cobaltcore-dev/aurora"` — новая процедура `ec2Credentials.reveal`, новые обязательные поля в публичном `S3Status`/`s3StatusSchema`, новый permission-ключ, новое поведение `create` (лимит). Файл — `.changeset/<kebab-slug>.md` (например `ceph-s3-credentials-management.md`). Пакет `@cobaltcore-dev/dashboard` в чейнджсет **не включать**: по истории `apps/dashboard/CHANGELOG.md` он получает только `Updated dependencies`-записи, собственных чейнджсетов ему не пишут. Текущая версия `@cobaltcore-dev/aurora` — `2.1.0`, в `.changeset/` сейчас **ноль** ожидающих чейнджсетов.
   В тексте чейнджсета обязательно:
   - что именно появилось в UI;
   - лимит 2 ключа на пару (пользователь, проект);
   - **upgrade note для операторов:** форкнутый `storage.json` должен получить `"storage:credential_delete": "rule:storage_viewer"`, иначе весь Storage-`canUser` начнёт падать и скроет все Ceph-действия;
   - изменение формы `S3Status` (`endpoint`, `region`).
3. **Design doc:** `/packages/aurora/docs/009_ceph_s3_bff.md` — секция `### EC2 Credentials (storage.ceph.ec2Credentials)` (~:197) и блок про `containers.status` (~:330, ~:2003) описывают текущий контракт. Дописать `reveal`, лимит в `create`, новые поля `status`. Рекомендуется, но не обязательно для CI.

---

## Testing Plan

**Unit (server, `pnpm --filter @cobaltcore-dev/aurora test src/server/Storage`)**
- [ ] `reveal` отдаёт секрет владельцу
- [ ] `reveal` → `NOT_FOUND` при чужом `user_id`
- [ ] `reveal` → `NOT_FOUND` при чужом `project_id`
- [ ] `reveal` → `NOT_FOUND` на 404, `UNAUTHORIZED` на 401, `FORBIDDEN` на 403
- [ ] `reveal` не вызывает `del`
- [ ] `create` создаёт при 0 и при 1 существующем ключе
- [ ] `create` → `CONFLICT`/`EC2_CREDENTIAL_LIMIT_REACHED` при 2, `post` не вызван
- [ ] ключи чужого проекта не учитываются в лимите
- [ ] сбой листинга в пре-чеке → `INTERNAL_SERVER_ERROR`, `post` не вызван
- [ ] `delete` — существующие тесты зелёные без правок (регресс рефактора Step 3)
- [ ] `containers.status` отдаёт endpoint/region в т.ч. при `hasCredentials: false`
- [ ] `s3StatusSchema` требует все три поля

**Unit (client)** — см. чеклист Step 14.

**Integration / сквозные**
- [ ] `pnpm --filter @cobaltcore-dev/aurora test` целиком зелёный (убедиться, что расширение `PERMISSION_MAP` не сломало снапшоты/ассерты в других Ceph-тестах, завязанных на количество permission-ключей)
- [ ] `pnpm typecheck && pnpm lint && pnpm format:check && pnpm check-i18n && pnpm build`

**Manual verification** (dev-сервер `pnpm dev`, реальный или мок-бэкенд из `/Users/kirylmishchuk/projects/SAP/local-mock-backend/` — учти, что мок должен уметь `GET/POST/DELETE /v3/credentials`, иначе часть сценариев проверяется только на реальном Keystone):
1. Проект с существующим кредом → `/projects/<id>/storage/ceph/containers` → `moreVert` рядом с `Create Bucket` → `Manage Credentials`.
2. В модалке: Endpoint URL и Region на месте, копируются; секрет замаскирован; `Show` раскрывает; `Hide` прячет; копирование секрета работает; появляется CLI-сниппет с кнопкой Copy.
3. `Create Access Key` → новый ключ в списке, секрет виден сразу, **страница не перезагружается**; кнопка создания стала задизейбленной + info-`Message` про лимит 2.
4. Удаление: корзина → инлайн-подтверждение → `Delete` → строка исчезла, тост показан.
5. Удалить все ключи, закрыть модалку → страница сама переходит в «S3 Object Storage: Setup Required» без ручной перезагрузки; кнопка `Manage Credentials` там открывает ту же модалку; создание ключа из неё возвращает список бакетов без reload.
6. Скопированные endpoint/region/секрет реально работают: `AWS_ACCESS_KEY_ID=… AWS_SECRET_ACCESS_KEY=… aws --endpoint-url … --region … s3 ls`.
7. 🔒 Изоляция: в DevTools → Network подменить `credentialId` в запросе `reveal` на чужой → `NOT_FOUND`, секрет не утёк.
8. 🔒 React Query Devtools: после закрытия модалки ни в одном закэшированном запросе секрета нет (`ec2Credentials.list` его не содержит по определению, `reveal` в кэш не попадает).

---

## Acceptance Criteria

- [ ] Пользователь с существующим кредом видит его access key и может раскрыть секрет
- [ ] Секрет замаскирован по умолчанию; раскрытие — явное действие; при закрытии модалки состояние раскрытия сбрасывается
- [ ] 🔒 Секрет не попадает в кэш TanStack Query ни при каком сценарии
- [ ] Создание нового ключа показывает секрет прямо в модалке, без `window.location.reload()`
- [ ] Удаление работает, требует инлайн-подтверждения, обновляет список бакетов
- [ ] Лимит 2 enforce'ится на сервере (`CONFLICT`) и отражён в UI (задизейбленная кнопка + объяснение)
- [ ] Endpoint и region видны в UI, копируются, доступны даже при нуле ключей
- [ ] Есть готовый к копированию CLI-сниппет для раскрытого ключа
- [ ] Обе точки входа (оверфлоу-меню и Setup Required) открывают одну и ту же модалку; параллельной ветки создания креда в `CredentialPrompt` больше нет
- [ ] 🔒 Попытка прочитать чужой кред по id даёт `NOT_FOUND` (покрыто тестом)
- [ ] Метки «активный ключ» нет нигде (решение E)
- [ ] Swift-часть не затронута
- [ ] Все новые строки локализованы, `pnpm check-i18n` проходит
- [ ] Чейнджсет `minor` для `@cobaltcore-dev/aurora` с upgrade note про `storage:credential_delete`
- [ ] `resolveEC2Credential` выбирает кред детерминированно (сортировка по `id`), покрыто тестом
- [ ] `createPermissionRouter` не роняет весь батч из-за одного отсутствующего правила, покрыто тестом
- [ ] Файлы кредов лежат в `Ceph/Credentials/`, `CredentialPrompt` переехал туда вместе с тестом
- [ ] В ветке невалидных кредов есть кнопка Manage Credentials, слова «expired» и «Please» из текста убраны
- [ ] Follow-up'ы не заводились — всё сделано в рамках задачи
- [ ] Нет регрессий: `pnpm typecheck`, `pnpm lint`, `pnpm format:check`, `pnpm test`, `pnpm build` зелёные
- [ ] Соответствие `.github/copilot-instructions.md`: B.1 (Juno-компоненты, `CodeBlock`/`ClipboardText`/`DataGrid`/`Status`/`Message`), B.5 (одна primary-кнопка, `disableCancelButton`/`disableCloseButton` во время async, нет вложенных модалок), B.6 (actionable error-состояния), B.8 (`can<Verb><Noun>`, fail-closed, disabled+объяснение вместо скрытия для лимита/права на создание), B.10 (тост только через `CredentialToastNotifications.tsx`), B.11 (не совмещать success-тост с инлайн-подтверждением), B.13 (порядок импортов), B.14 (`aria-label` у icon-only кнопок), B.16 (actionable error → `Message`, не toast), B.19 (title case, без «Please»/«We»/восклицаний)

---

## Open Questions

**Все шесть закрыты в разборе с пользователем 29.09.2026** — решения зафиксированы в разделе «Принятые решения» вверху файла и разведены по шагам. Открытых вопросов не осталось.

### Отложено до ручной проверки: метки (`label`) у ключей

Не открытый вопрос плана, а **кандидат на расширение скоупа**. У креда нет ни имени,
ни описания, ни тегов, поэтому два ключа в списке различимы только по access key ID —
пользователь не может понять, для чего он создавал каждый. Единственное место под метку —
сам `blob`, который мы и составляем: `{access, secret, label}`. Наш код это стерпит
(проверено: `list` `:71-77`, `create` `:134-140`, `resolveEC2Credential` — везде
`JSON.parse` + явная проекция полей), но **стерпит ли Keystone и путь `/v3/ec2tokens` —
не проверено**, а цена ошибки высокая: ключ будет создаваться и не работать.

Проверяется руками по [runbooks/2026-09-29-ec2-credential-label-probe.md](../runbooks/2026-09-29-ec2-credential-label-probe.md).
Если проба проходит — правятся решение 6 (лимит 2 → 5: у именованных ключей появляется
назначение, и два становится произвольным числом), решение 10, `ec2CredentialSchema`
(`label` строго `.optional()` — у существующих кред метки нет) и `create`/`reveal`/модалка.
Если не проходит — раздел удаляется, план остаётся как есть.

| Был вопрос | Решение |
| --- | --- |
| 1. Permission-ключ на удаление: новый / защитить роутер / не гейтить / переиспользовать `create` | Новый ключ **и** защита роутера — оба в этом PR (Step 6) |
| 2. Step 13 — третья точка входа | Включён в скоуп, заодно правится копирайт про «expired» |
| 3. `reveal` — mutation или query | Mutation (прецедент `objects.generatePresignedUrl`) |
| 4. Расположение файлов | Новая папка `Ceph/Credentials/`, `CredentialPrompt` переезжает туда |
| 5. Удаление в один клик или с подтверждением | Инлайновое подтверждение |
| 6. Формат CLI-сниппета | Только AWS CLI + четыре значения по отдельности |

Сверх плана решено: `.find` в `resolveEC2Credential` заменяется на детерминированный выбор (Step 1), follow-up'ы не заводятся.

---

## Замечания к материалам

- **База знаний отстаёт сильнее, чем заявлено по версиям.** `DOCS/aurora-dashboard-kb/README.md` закреплён на `0169b4ad` и указывает `@cobaltcore-dev/aurora 1.3.0` / `@cobaltcore-dev/dashboard 1.2.13`; по факту в дереве — **2.1.0** и **1.2.15** (был major-релиз). На содержание плана это не повлияло (всё сверено по живому коду), но базу стоит обновить.
- **Неточность в докблоке `useCephPermissions.ts`:** утверждение, что fail-closed «covers operators whose `storage.json` is missing one of the newer Ceph rules», неверно — недостающее правило роняет весь запрос, а не даёт `false` по одному ключу. После Step 6 (п.4) утверждение станет верным — докблок надо привести в соответствие в том же шаге.
