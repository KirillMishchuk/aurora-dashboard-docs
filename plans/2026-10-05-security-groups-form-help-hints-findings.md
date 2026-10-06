# Security Groups: help hints на полях форм — разбор замечания

**Дата:** 2026-10-05
**Status:** разбор, не реализовано
**База:** `aurora-dashboard` `main` @ `d01c26b4` (worktree `.claude/worktrees/sg-bugs-main`); Elektra `sapcc/elektra` @ `b3c7f021`
**Juno:** `@cloudoperators/juno-ui-components` 9.4.0 — `helptext` есть у `TextInput`, `Textarea`, `Select`, `Checkbox`, `RadioGroup`; доработка компонентов не нужна.

## Замечание

> Show validation information or other important information (e.g. what happens if a field is left empty) on form inputs in help hints, cross check with Elektra

## Коротко

- В Авроре почти нет `helptext`: важное либо в плейсхолдерах, которые пропадают при вводе, либо нигде.
- Elektra тоже скупа, но под ICMP, Port Range и IP Address подсказки есть, а в модалке правила справа — справочный блок по Type / Port Range / ICMP / Remote.
- Попутно найдены два поведения «пустого поля», прямо относящиеся к замечанию (Remote Security Group, Remote IP Prefix), и два отдельных бага (IPv6 CIDR, очистка description).

Пути ниже — относительно
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/securitygroups/`.

---

## 1. Как это сделано в Elektra

Код: `plugins/networking/app/javascript/widgets/security_groups/` (далее `SG/`).

**Общий механизм форм.** Клиентская валидация в Elektra сообщений не показывает — она только дизейблит Save
(`app/javascript/lib/elektra-form/components/form.tsx:87`, `submit_button.jsx:13`). Все тексты ошибок приходят
с сервера через `<Form.Errors/>` в виде `"<key>: <message>"`. `required` даёт только звёздочку.
Пустые значения сервер отбрасывает (`.delete_if { |_k, v| v.blank? }`) — отсюда «пусто = всё».

### Create / Edit Security Group (`SG/components/security_groups/new.jsx`, `edit.jsx`)

| Поле | Required | Подсказка | Валидация |
|---|---|---|---|
| Name | да | нет, плейсхолдера нет | клиент: непустое (только дизейбл Save); сервер: `presence` |
| Description | нет | нет | нет; пустое не отправляется |

- Edit в UI недоступен: `item.jsx:7` — `const canUpdate = false`. Очистить description через edit, судя по коду, тоже нельзя (`security_group.rb:19-24` выкидывает пустые значения) — *выведено из кода*.
- Для группы `default` меню действий скрыто целиком (`item.jsx:44-45`).

### Add Security Group Rule (`SG/components/security_group_rules/new.jsx`)

Начальные значения: `direction: "ingress"`, `remote_ip_prefix: "0.0.0.0/0"`, `ethertype: "ipv4"`, `remote_source: "ip"`.

| Поле | Видимость | Подсказка (дословно) | Пусто = |
|---|---|---|---|
| Type (пресет) | всегда | нет | UI-помощник, не отправляется |
| Protocol | всегда; select tcp/udp/icmp | нет | любой протокол |
| Direction | всегда | нет | — (дефолт ingress) |
| ICMP Type | только icmp | "ICMP Type is a number between 0 and 255" | все типы |
| ICMP Code | только icmp | "ICMP Code is a number between 0 and 15" (у Neutron 0–255) | все коды |
| Port Range | protocol ≠ icmp | "Example for range 1-80 and single port 80" | все порты |
| Remote Source | всегда; IP Address / Security Group | нет | — |
| Remote group | при Security Group; **required** | красное предупреждение, см. ниже | Save недоступен |
| IP Address | при IP; **required** | "Example for IPv4 0.0.0.0/0 and IPv6 ::/0" | Save недоступен |
| Ether Type | при IP; select | нет | — (дефолт IPv4); из CIDR не выводится |
| Description | всегда | нет | не отправляется |

Предупреждение под выбором группы:
"This should only be used if you operate within the documented boundaries. Please review the best practice for
security group design" — со ссылкой на
`https://documentation.global.cloud.sap/docs/customer/networking/security-groups/network-secgroup-design/`.

Справочный блок справа (`SG/constants.js:29-35`, показывается по протоколу):

- "Rules define which traffic is allowed to instances assigned to the security group. A security group rule consists of three main parts: Type, Port Range and Remote Source."
- **Type:** "You can specify the desired rule template or use custom rules, the options are Custom TCP Rule, Custom UDP Rule, or Custom ICMP Rule."
- **Port Range:** "For TCP and UDP rules you may choose to open either a single port or a range of ports. For as range provide the starting and ending ports devided by minus (e.g. 0-80)."
- **ICMP:** "For ICMP rules you should specify an ICMP type and code in the spaces provided."
- **Remote:** "You must specify the source of the traffic to be allowed via this rule. You may do so either in the form of an IP address block (CIDR, recommended) or via a source group (Security Group, not recommended). Selecting a security group as the source will allow any other instance in that security group access."

Клиентская валидация правила: только `direction` и непустой remote (CIDR или выбранная группа). CIDR проверяется
на сервере через `IPAddr` → "Please enter a valid IP Address".

### Share (RBAC, "Access Control") (`SG/components/rbacs/list.jsx`)

- Автокомплит проекта, плейсхолдер "Project name or ID"; action захардкожен `access_as_shared`.
- Если введённый ID не найден в кеше — "No project found with ID …"; без ID — "No project ID provided".

---

## 2. Аврора: поле за полем

| Форма / поле | Файл:строка | Сейчас | Пусто = | Предлагаемый `helptext` (EN, через `t`) |
|---|---|---|---|---|
| SG · Name | `-components/-modals/CreateSecurityGroupModal.tsx:143-153`, `EditSecurityGroupModal.tsx:156-166` | required, плейсхолдер "Type name" | ошибка "Security group name is required" | Required. Up to 255 characters. *(+ про `default`, если подтвердится — см. §4)* |
| SG · Description | `CreateSecurityGroupModal.tsx:157-166`, `EditSecurityGroupModal.tsx:170-179` | плейсхолдер "Description" | не отправляется | Optional. Up to 255 characters. |
| SG · Stateful | `CreateSecurityGroupModal.tsx:170-178` | helptext есть: "…cannot be changed after creation." | — | Дописать: в stateless-группе обратный трафик нужно разрешать отдельными правилами. |
| Rule · Rule Type | `$securityGroupId/-modals/AddRuleModal/sections/RuleTypeSection.tsx:18-75` | ничего | остальные поля скрыты, Add недоступен | A preset fills in protocol and ports. Choose a Custom rule to set them yourself. |
| Rule · Direction | `sections/DirectionEthertypeSection.tsx:17-29` | ничего | — (ingress) | Ingress: traffic coming in to instances. Egress: traffic going out. |
| Rule · Protocol (Other) | `sections/ProtocolSection.tsx:17-26` | плейсхолдер "tcp, udp, icmp, or protocol number" | ошибка "Protocol is required" | Protocol name (e.g. tcp, udp, icmp, gre) or IP protocol number 0–255. |
| Rule · Port from / to | `sections/PortRangeSection.tsx:31-81`, текст `:92-94` | текст обычным `<p>`, не `helptext` | from — ошибка; to — один порт | Перенести в `helptext`, добавить «1–65535». |
| Rule · ICMP Type / Code | `sections/IcmpSection.tsx:19-44` | только плейсхолдеры "Leave empty for all types/codes" | все типы / коды | 0–255. Leave empty to allow all. Type is required when Code is set. |
| Rule · Remote Source | `sections/RemoteSourceSection.tsx:21-40` | ничего | — (cidr) | CIDR (recommended) or Security Group: allows traffic from any instance in that group. + ссылка на SAP-гайд, как в Elektra. |
| Rule · Remote IP Prefix | `sections/RemoteSourceSection.tsx:54-63` | значение `0.0.0.0/0`, плейсхолдер — дефолтный CIDR | **уходит без префикса = любой адрес** | Пример IPv4/IPv6 + явное «Leave empty to allow any address» — либо сделать обязательным, как в Elektra (решить). |
| Rule · Remote Security Group | `sections/RemoteSourceSection.tsx:80-92` | ничего, нет валидации | **уходит без remote = любой адрес** (см. §3.1) | Required + текст про «любой инстанс этой группы». |
| Rule · IP Version | `sections/DirectionEthertypeSection.tsx:48-60` | ничего; виден только при Security Group | — (IPv4) | Whether the rule applies to IPv4 or IPv6 traffic. При CIDR выводится из адреса. *(см. §3.2, исправлено)* |
| Rule · Description | `sections/DescriptionSection.tsx:17-26` | плейсхолдер "Optional description" | не отправляется | Optional. Up to 255 characters. |
| RBAC · Target Project ID | `$securityGroupId/-modals/AddRBACPolicyModal.tsx:166-179` | helptext есть, валидация формата есть | ошибка "Target project ID is required" | Не менять. |

---

## 3. Найдено попутно

### 3.1. Remote = Security Group с пустым выбором создаёт правило «для всех» — относится к замечанию

- `AddRuleModal.tsx:126-130`: `remote_group_id` ставится только если `remoteSecurityGroupId` непуст, иначе remote в payload нет вовсе.
- `validation/formSchema.ts` не проверяет `remoteSecurityGroupId`.
- Итог: пользователь выбрал «Security Group», группу не выбрал, нажал Add — Neutron создаёт правило без remote, то есть открытое для любого адреса. Elektra это блокирует (поле required).
- **Предложение:** сделать обязательным в этом же PR — это ровно «что будет, если поле оставить пустым».

### 3.2. Правило с IPv6 CIDR создать невозможно — исправлено

- Было: `EthertypeSection` виден только при `remoteSourceType === "security_group"`, при переключении на CIDR `ethertype` принудительно ставился в `IPv4` (`RemoteSourceSection.tsx`), а `formSchema.ts` на `::/0` выдавал "CIDR family (IPv6) must match Ethertype (IPv4)" — ошибку про поле, которого пользователь не видит.
- Когда нужен ethertype: при CIDR он однозначно задаётся адресом (и обязан с ним совпадать), при Security Group вывести его неоткуда — группа может содержать инстансы обоих семейств (в `default` есть пары self-правил IPv4 + IPv6).
- Horizon (`openstack_dashboard/dashboards/project/security_groups/forms.py:242-252, 456-459`): Ether Type только при Security Group, при CIDR выводится из адреса — «When cidr is used ethertype is determined from IP version of cidr. When source group, ethertype needs to be specified explicitly.»
- Elektra (`security_group_rules/new.jsx:178-187, 270-275`) — наоборот: Ether Type select при IP Address (можно выбрать `::/0` + IPv4, ошибку вернёт Neutron), при Security Group ethertype не отправляется → всегда IPv4 по умолчанию Neutron, IPv6-правило на группу создать нельзя.
- **Сделано (сознательно как в Horizon, не как в Elektra):** IP Version по-прежнему только при Security Group, с helptext; при CIDR ethertype выводится из адреса при сабмите (пусто → IPv4); принудительный сброс в IPv4 и проверка совпадения семейства убраны; helptext CIDR упоминает IPv6. Тесты на IPv6 CIDR, пустой CIDR и IPv6 для группы.

### 3.3. В редактировании SG нельзя очистить description — отдельный баг

- `EditSecurityGroupModal.tsx:101`: `description: properties.description.trim() || undefined`.
- Сервер (`server/Network/routers/securityGroupRouter.ts:175`) передаёт description только если `!== undefined` → пустое поле не уходит, старое описание остаётся.
- В Elektra то же самое (и Edit там в UI вообще выключен).
- **Варианты:** в Edit отправлять `""` при очищенном поле (Create оставить как есть).

### 3.4. Группа без имени: пустая ячейка Name в списке — отдельная правка

Обнаружено на моке (группа `name: ""`, `local-mock-backend/fake-backend.js`, `extraSecurityGroups`).

- **Создавать группы без имени не разрешаем.** В Create (`CreateSecurityGroupModal.tsx:73-75`) и Edit (`EditSecurityGroupModal.tsx:82-84`) имя остаётся обязательным: так же в Elektra, Create и Edit ведут себя одинаково, а если кто-то редактирует безымянную группу, попросить его дать ей имя — нормально.
- **Показывать такие группы нужно.** Neutron принимает пустое имя, и группа может появиться в обход UI: CLI (`openstack security group create ""`), API, Terraform.
- Сейчас UI показывает такую группу по-разному:

| Где | Видно | Код |
|---|---|---|
| Список, колонка Name | **пустая ячейка** | `-components/SecurityGroupTableRow.tsx:68` — `{sg.name}` |
| Заголовок деталей | ID | `$securityGroupId/index.tsx:283` — `name \|\| id` |
| Basic Info → Name | `—` | `$securityGroupId/-components/-details/SecurityGroupBasicInfo.tsx:16` |
| Удаление, тосты, выбор remote group | ID | `name \|\| id` |
| Хлебная крошка | без имени | `$securityGroupId/index.tsx:167` — `name ?? undefined` |

- **Предложение:** в ячейке Name списка показывать ID приглушённым стилем, если имени нет, как в остальных местах. Хлебную крошку тоже стоит выровнять (`name || id`).

### 3.6. Remote Security Group: текущую группу нельзя выбрать — исправлено в этом PR

- `$securityGroupId/index.tsx:173` (было): `.filter((sg) => sg.id !== securityGroupId) // Exclude current group` — с первой версии (`312d5b67`, #601), причина не указана.
- Ссылка группы на саму себя — штатный случай Neutron: так устроена `default` («инстансы группы общаются между собой»), так же разрешают трафик внутри кластера. Neutron принимает `remote_group_id == security_group_id`; Elektra текущую группу не исключает (`security_group_rules/new.jsx`, перебор всех `securityGroups.items`).
- **Сделано:** фильтр убран, текущая группа в списке подписана `<name> (this group)`.

### 3.7. В таблице правил нет колонки Remote — сделано в этом PR

- Колонки Direction, Description, Ethertype, Protocol, Range (`SecurityGroupRulesTable.tsx:234-238`); remote виден только в диалоге удаления, группа — ID. Не было с первой версии (#586).
- Пользователь не видит, для кого открыто правило; в Elektra колонка есть.
- Заведено: `FOLLOW-UPS.md` → пункт 38.
- **Сделано:** колонка Remote текстом (CIDR, имя группы, `(this group)`, ID для групп вне списка, address group, `Any`), без ссылки на группу; Description перенесена в конец. В `DeleteRuleDialog` одна строка `Remote` с тем же значением; поиск по правилам ищет по CIDR и имени remote-группы. Хелпер `$securityGroupId/-components/ruleRemote.ts`. Пункт 38 закрыт.

### 3.5. Мелочи

- Сообщения в `validation/formSchema.ts` и `validationHelpers.ts` — захардкоженный английский, не через Lingui (в отличие от `AddRBACPolicyModal`, где схема строится внутри компонента с `t`).
- `formSchema.ts:97-102`: одинаковые Port from и Port to отклоняются ("must be less than"), хотя Neutron принимает `min == max`; одиночный порт работает только при пустом «to».
- `PortRangeSection` показывает ошибки отдельным блоком через `invalid`, а не `errortext`, — при переносе текста в `helptext` стоит выровнять с остальными полями.

---

## 4. Не проверено

- Запрещает ли Neutron создавать группу с именем `default` (ожидаемо — валидатор `name_not_default` в API-определении security groups). Проверить на DevStack: `openstack security group create default`. Если да — указать в helptext Name.
- Длины 255 для name/description — по Neutron `NAME_FIELD_SIZE` / `DESCRIPTION_FIELD_SIZE`; в Авроре на клиенте и сервере не ограничены.
- Поведение Neutron для правила без remote и без ethertype при Security Group (ожидаемо IPv4 по умолчанию).

## 5. Предлагаемый скоуп

| Пункт | Где |
|---|---|
| §2 — `helptext` по таблице | этот PR |
| §3.1 — Remote Security Group обязателен | этот PR |
| §3.2 — IPv6 CIDR | исправлено в этом PR (логика Horizon) |
| §3.3 — очистка description | отдельный issue / follow-up в `FOLLOW-UPS.md` |
| §3.4 — ID вместо пустого имени в списке (и в хлебной крошке) | решить: этот PR или follow-up |
| §3.5 — i18n схемы, `min == max`, ошибки портов | решить: этот PR или follow-up |

Решение по скоупу за пользователем; follow-up'ы ещё не заведены.
