# Runbook: проба «метка в blob EC2-креда»

**Дата:** 2026-09-29 · **Для:** плана [2026-09-29-ceph-s3-credentials-management-ui.md](../plans/2026-09-29-ceph-s3-credentials-management-ui.md) · **Где выполнять:** удалённая машина с доступом в сеть (VPN/бастион)

## Зачем

У EC2-креда в Keystone нет ни имени, ни описания, ни тегов — объект целиком это
`{id, type, user_id, project_id, blob}`. Единственное место, куда можно положить
человекочитаемую метку («backups», «CI», «ноутбук»), — сам `blob`, который
Aurora составляет сама:

```json
{ "access": "…", "secret": "…", "label": "backups" }
```

Со стороны Aurora это безопасно — проверено по коду: `list`
(`ec2CredentialRouter.ts:71-77`), `create` (`:134-140`) и
`resolveEC2Credential.ts` делают `JSON.parse` и затем явно выбирают поля в
проекцию под `safeParse`, то есть лишний ключ проходит насквозь.

Непроверено и проверяется этим runbook-ом:

1. **Примет ли Keystone** креду с лишним полем в blob и **сохранит ли** его.
2. **Не сломает ли** это аутентификацию — подпись S3 идёт в RGW, а тот несёт её
   в Keystone на `/v3/ec2tokens`, который читает тот же blob.

Цена ошибки высокая: если валидация всё же есть, сломается не отображение, а
сам ключ — пользователь получит креду, которая не работает. Поэтому проверяем
руками до того, как закладывать метки в план.

## Что понадобится на машине

| Инструмент | Зачем | Если нет |
| --- | --- | --- |
| `curl` | все запросы к Keystone | есть везде |
| `jq` | сборка/разбор JSON | `sudo apt install jq` / `sudo dnf install jq`, либо см. «Без jq» в конце |
| `openssl` | сгенерировать случайные access/secret | есть везде |
| `aws` (AWS CLI v2) | только для части 2 | `pip3 install --user awscli`, либо см. «Установка AWS CLI» |

Проверить одной строкой:

```bash
for t in curl jq openssl aws; do command -v "$t" >/dev/null && echo "$t: ok" || echo "$t: НЕТ"; done
```

Без `aws` можно выполнить часть 1 — она отвечает на главный вопрос. Часть 2
желательна, но не блокирует решение.

## Прежде чем начать

**Проба создаёт настоящий рабочий ключ к вашему проекту.** Не к тестовому — к
тому, в котором вы работаете. Отсюда три правила:

1. **Запишите `CRED_ID` сразу, как получите.** Если сессия оборвётся, ключ
   останется жить в Keystone. В разделе «Уборка» есть команда, которая находит
   забытые пробные креды по метке.
2. **Ничего не писать в файлы.** Ни `~/.aws/credentials`, ни временных файлов с
   токеном — всё живёт только в переменных окружения текущего шелла. На общей
   машине это существенно.
3. **Отключите историю шелла на время пробы** — пароль вводится через
   `read -rs` и в историю не попадёт, но остальное лучше тоже не оставлять:

   ```bash
   set +o history        # bash
   unset HISTFILE        # zsh / на всякий случай
   ```

   Обратно — `set -o history`, либо просто закройте сессию.

Окружение — **QA** (`qa-de-1`), не прод. Значения взяты из
`apps/dashboard/.env` рабочей копии: `IDENTITY_ENDPOINT=https://identity-3.qa-de-1.cloud.sap/v3`,
`CEPH_REGION=ceph-objectstore-ec-st1-qa-de-1`. Если на удалённой машине
окружение другое — подставьте свои.

## Часть 1. Принимает ли Keystone лишнее поле

### Шаг 1. Связность

```bash
curl -s -o /dev/null -w '%{http_code}\n' --max-time 10 https://identity-3.qa-de-1.cloud.sap/v3
```

- `200` или `300` — хорошо, идём дальше.
- `000` — сети до Keystone нет: VPN не поднят, либо машина не в том сегменте.
  Останавливаемся, дальше ничего не заработает.

### Шаг 2. Токен, scoped на проект

`PROJECT_ID` берётся прямо из URL дашборда: `/projects/<PROJECT_ID>/storage/...`.
`USER_DOMAIN` — домен, в котором вы логинитесь (например `monsoon3`).

```bash
IDENTITY=https://identity-3.qa-de-1.cloud.sap/v3
USER_NAME=<ваш логин>
USER_DOMAIN=<ваш домен>
PROJECT_ID=<id проекта из URL дашборда>

read -rs -p "password: " OS_PASSWORD; echo

RESP=$(curl -si -X POST "$IDENTITY/auth/tokens" -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg u "$USER_NAME" --arg d "$USER_DOMAIN" --arg p "$OS_PASSWORD" --arg pid "$PROJECT_ID" \
    '{auth:{identity:{methods:["password"],password:{user:{name:$u,domain:{name:$d},password:$p}}},scope:{project:{id:$pid}}}}')")

TOKEN=$(printf '%s' "$RESP" | tr -d '\r' | awk 'tolower($1)=="x-subject-token:"{print $2}')
USER_ID=$(printf '%s' "$RESP" | sed -n '/^{/,$p' | jq -r '.token.user.id')

echo "token: ${TOKEN:+ok}   user_id: $USER_ID"
```

Ожидаем `token: ok` и непустой `user_id`.

Если пусто — посмотрите первую строку ответа и текст ошибки:

```bash
printf '%s' "$RESP" | head -1
printf '%s' "$RESP" | sed -n '/^{/,$p' | jq -r '.error.message? // empty'
```

`401` — логин/пароль/домен. `404` на scope — неверный `PROJECT_ID`.
`403` — у пользователя нет роли в этом проекте.

Пароль больше не нужен, уберите его из шелла:

```bash
unset OS_PASSWORD
```

### Шаг 3. Создать пробную креду с меткой

```bash
ACCESS=$(openssl rand -hex 20 | tr 'a-z' 'A-Z')
SECRET=$(openssl rand -base64 40)

CRED=$(curl -s -X POST "$IDENTITY/credentials" \
  -H "X-Auth-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d "$(jq -nc --arg a "$ACCESS" --arg s "$SECRET" --arg p "$PROJECT_ID" --arg u "$USER_ID" \
    '{credential:{type:"ec2",project_id:$p,user_id:$u,blob:({access:$a,secret:$s,label:"aurora-label-probe"}|tostring)}}')")

CRED_ID=$(printf '%s' "$CRED" | jq -r '.credential.id // empty')
echo "CRED_ID=$CRED_ID"
```

**Запишите `CRED_ID` куда-нибудь вне шелла прямо сейчас.** Это то, что придётся
удалить.

Если `CRED_ID` пустой — Keystone отверг запрос, и это уже ответ:

```bash
printf '%s' "$CRED" | jq .
```

Формат access/secret здесь ровно тот же, что генерит Aurora
(`ec2CredentialRouter.ts:110-111`): 20 случайных байт в hex верхнего регистра и
40 случайных байт в base64. Это намеренно — проба должна быть неотличима от
боевого ключа во всём, кроме лишнего поля.

### Шаг 4. Перечитать и убедиться, что метка хранится

Критично делать отдельным запросом: ответ на POST может просто отражать то, что
мы послали, а нас интересует, что реально легло в базу.

```bash
curl -s "$IDENTITY/credentials/$CRED_ID" -H "X-Auth-Token: $TOKEN" | jq -r '.credential.blob'
```

**Как читать результат:**

| Что видим | Вывод |
| --- | --- |
| `{"access":"…","secret":"…","label":"aurora-label-probe"}` | Keystone поле хранит — главный вопрос закрыт положительно |
| blob без `label` | поле молча срезается — метки в blob невозможны, идея закрыта |
| POST вернул 400/ошибку валидации | Keystone валидирует blob — идея закрыта |

Если метка не уцелела — переходите сразу к «Уборке», часть 2 не нужна.

## Часть 2. Не ломается ли подпись S3

Отвечает на второй вопрос: RGW несёт подпись в Keystone на `/v3/ec2tokens`, и
тот читает тот же blob. Если лишнее поле споткнёт этот путь — ключ будет
создаваться, но не работать, что хуже, чем не иметь меток вовсе.

### Шаг 5. Найти S3-эндпоинт

Сервис в каталоге называется `ceph` (`cephProcedure.ts:24`), а хвост
`/swift/...` надо отрезать — ровно это делает `resolveS3Config`:

```bash
S3=$(printf '%s' "$RESP" | sed -n '/^{/,$p' \
  | jq -r '.token.catalog[] | select(.name=="ceph") | .endpoints[] | select(.interface=="public") | .url' \
  | head -1 | sed 's#/swift/.*##')

echo "S3=$S3"
```

Пусто — значит в каталоге этого проекта нет сервиса `ceph`; тогда и сам Ceph в
дашборде для этого проекта не работает, проверьте `PROJECT_ID`.

### Шаг 6. Дёрнуть S3 пробным ключом

Ключи передаём через окружение одной команды — чтобы ничего не осело в
`~/.aws/`:

```bash
AWS_ACCESS_KEY_ID="$ACCESS" AWS_SECRET_ACCESS_KEY="$SECRET" \
AWS_EC2_METADATA_DISABLED=true \
  aws --endpoint-url "$S3" --region ceph-objectstore-ec-st1-qa-de-1 s3 ls
```

| Что видим | Вывод |
| --- | --- |
| список бакетов, либо пустой вывод без ошибки | подпись прошла — лишнее поле ни на что не влияет |
| `InvalidAccessKeyId` | Keystone не признал ключ по этому пути — идея закрыта |
| `SignatureDoesNotMatch` | сначала перепроверьте регион и что `$SECRET` не покалечен шеллом (в нём бывают `+` и `/`), и только потом делайте вывод |
| `Could not connect` | до RGW нет сети, хотя до Keystone есть — это про сеть, а не про метку |

## Уборка (обязательно)

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X DELETE "$IDENTITY/credentials/$CRED_ID" -H "X-Auth-Token: $TOKEN"
```

`204` — удалено. `404` — уже удалено, тоже нормально.

Проверить, что пробных кред не осталось (в том числе от оборвавшейся попытки):

```bash
curl -s "$IDENTITY/credentials?user_id=$USER_ID&type=ec2" -H "X-Auth-Token: $TOKEN" \
  | jq -r '.credentials[] | select(.blob | contains("aurora-label-probe")) | .id'
```

Вывод должен быть пустым. Если что-то нашлось — удалите тем же DELETE по этому
`id`.

Заодно убедитесь, что ваши **боевые** креды на месте и их столько же, сколько
было до пробы:

```bash
curl -s "$IDENTITY/credentials?user_id=$USER_ID&type=ec2" -H "X-Auth-Token: $TOKEN" \
  | jq -r --arg p "$PROJECT_ID" '[.credentials[] | select(.type=="ec2" and .project_id==$p)] | length'
```

И подчистить шелл:

```bash
unset TOKEN ACCESS SECRET CRED CRED_ID RESP
set -o history
```

## Что сообщить обратно

Достаточно двух строк:

1. Уцелело ли `"label":"aurora-label-probe"` в перечитанном blob (шаг 4).
2. Прошёл ли `aws s3 ls` (шаг 6), и если нет — с какой именно ошибкой.

**Секрет, access key и токен присылать не надо** — они ни на что в решении не
влияют, а переслать их значит размножить их по логам и чатам.

## Приложение

### Установка AWS CLI, если её нет

```bash
# Linux x86_64, официальный установщик, без root:
curl -s "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscliv2.zip
unzip -q /tmp/awscliv2.zip -d /tmp && /tmp/aws/install -i ~/.local/aws-cli -b ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"

# либо, если есть pip:
pip3 install --user awscli
```

### Без jq

`jq` используется только для сборки и разбора JSON; `python3` есть почти везде и
заменяет его. Токен:

```bash
BODY=$(python3 -c 'import json,sys,os
print(json.dumps({"auth":{"identity":{"methods":["password"],"password":{"user":{
 "name":os.environ["USER_NAME"],"domain":{"name":os.environ["USER_DOMAIN"]},
 "password":os.environ["OS_PASSWORD"]}}},"scope":{"project":{"id":os.environ["PROJECT_ID"]}}}}))')
```

(переменные должны быть экспортированы: `export USER_NAME USER_DOMAIN PROJECT_ID OS_PASSWORD`)

Разбор blob:

```bash
curl -s "$IDENTITY/credentials/$CRED_ID" -H "X-Auth-Token: $TOKEN" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["credential"]["blob"])'
```

### Если проба прошла — что меняется в плане

Не делать заранее, только после положительного результата:

- Решение 6 (лимит 2 ключа) — поднять до 5. Лимит 2 был взят по образцу AWS
  именно потому, что ключи взаимозаменяемы и два нужны лишь для беспростойной
  ротации; у именованных ключей появляется назначение, и два становится
  произвольным числом.
- Решение 10 (содержимое модалки) — метка становится основным способом отличать
  ключи, показ полного access key остаётся, но уходит на второй план.
- `ec2CredentialSchema` — `label: z.string().max(…).optional()`; опциональность
  обязательна: у всех уже существующих кред, а также у созданных через
  `openstack ec2 credentials create`, метки нет и не будет.
- `create` — принимать метку на входе; редактирование метки — это
  `PATCH /v3/credentials/{id}` с перезаписью **всего** blob, то есть сервер
  обязан прочитать текущий blob и записать его обратно вместе с секретом.
