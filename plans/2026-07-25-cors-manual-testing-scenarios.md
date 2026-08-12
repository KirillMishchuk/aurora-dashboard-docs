# CORS: два сценария ручной проверки (curl + локальный HTML)

**Дата:** 2026-07-25 · Компаньон к [2026-07-25-cors-configuration-testing-plan.md](./2026-07-25-cors-configuration-testing-plan.md) (сценарий M9/M14 в том плане проверяет только валидацию строки origin в форме, но не реальное срабатывание CORS в браузере — этот файл закрывает именно это).

## Зачем это нужно

Прямая навигация в адресной строке браузера (в т.ч. в инкогнито) **не** отправляет заголовок `Origin` и не подчиняется CORS вообще — это top-level navigation, а не кросс-доменный запрос со страницы. Поэтому открыть объект напрямую по ссылке — не тест CORS, он сработает всегда, независимо от настроенного правила. Реально CORS проверяется браузером только когда JS **с другого origin** делает `fetch`/`XHR` к ресурсу. Ниже — два способа это проверить: без браузера (curl) и с браузером (локальная HTML-страница на своём origin).

## Подготовка

1. В Aurora UI: Storage → Ceph → Buckets → выбрать бакет → кнопка **CORS** → добавить правило, например:
   - Allowed Origins: `https://example.com`
   - Allowed Methods: `GET`, `HEAD`
   - Max Age Seconds: `3600`
   - Save
2. Зафиксировать endpoint и путь к объекту, например (пример из реальной проверки):
   ```
   https://rgw.st1.qa-de-1.cloud.sap/631a3518e93d436fbdf57525babe8606:kiryl-test-bucket/V1.png
   ```
   Формат: `<RGW endpoint>/<project-id>:<bucket-name>/<object-key>`.

---

## Сценарий 1 — проверка через `curl` (без браузера)

Самый быстрый способ: RGW отдаёт объект всегда с кодом 200 (сам S3 не блокирует отдачу), но заголовки `Access-Control-Allow-*` в ответе появляются только если `Origin` запроса совпал с разрешённым правилом — именно эти заголовки браузер использует, чтобы решить, показывать ли ответ странице. curl их просто показывает напрямую, без интерпретации.

### Шаг 1 — разрешённый origin

```bash
curl -sI \
  -H "Origin: https://example.com" \
  "https://rgw.st1.qa-de-1.cloud.sap/631a3518e93d436fbdf57525babe8606:kiryl-test-bucket/V1.png" \
  | grep -i "^\(HTTP\|access-control\)"
```

**Ожидаемый результат** (если правило настроено на `https://example.com`):
```
HTTP/1.1 200 OK
access-control-allow-origin: https://example.com
```
(возможно, также `access-control-allow-methods`, `access-control-expose-headers`, `access-control-max-age` — зависит от того, что RGW возвращает для simple-запросов.)

### Шаг 2 — неразрешённый origin

```bash
curl -sI \
  -H "Origin: https://evil.example" \
  "https://rgw.st1.qa-de-1.cloud.sap/631a3518e93d436fbdf57525babe8606:kiryl-test-bucket/V1.png" \
  | grep -i "^\(HTTP\|access-control\)"
```

**Ожидаемый результат:**
```
HTTP/1.1 200 OK
```
— заголовка `access-control-allow-origin` нет вообще. Сам объект отдаётся (curl видит тело ответа, если убрать `-I`), но в реальном браузере такой ответ на кросс-доменный `fetch` будет заблокирован CORS-политикой на стороне браузера (curl этого не показывает — он не браузер и ничего не блокирует).

### Шаг 3 — preflight-запрос (для методов вроде PUT/DELETE)

Если правило разрешает, например, `PUT`, браузер перед реальным запросом сначала шлёт `OPTIONS` (preflight):

```bash
curl -sI -X OPTIONS \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: PUT" \
  -H "Access-Control-Request-Headers: content-type" \
  "https://rgw.st1.qa-de-1.cloud.sap/631a3518e93d436fbdf57525babe8606:kiryl-test-bucket/V1.png" \
  | grep -i "^\(HTTP\|access-control\)"
```

**Ожидаемый результат** (если `PUT` в `AllowedMethods`):
```
HTTP/1.1 200 OK
access-control-allow-origin: https://example.com
access-control-allow-methods: PUT
access-control-allow-headers: content-type
```

Повтори с `Access-Control-Request-Method: DELETE` (или любым методом не из правила) — заголовков `access-control-allow-*` в ответе быть не должно.

### Итоговая таблица для отчёта

| Origin в запросе | Метод | Есть `Access-Control-Allow-Origin` в ответе? | Вывод |
| --- | --- | --- | --- |
| `https://example.com` (в правиле) | GET | да | правило работает |
| `https://evil.example` (не в правиле) | GET | нет | правило работает (блокировка) |
| `https://example.com` | PUT (в правиле) | да, + `Allow-Methods` | preflight проходит |
| `https://example.com` | DELETE (не в правиле) | нет | preflight отклонён |

---

## Сценарий 2 — реальный кросс-доменный fetch из браузера (curl не покажет то, что видит реальный браузер: заблокированный ответ, ошибку в консоли)

### Шаг 1 — создать тестовую HTML-страницу

```bash
mkdir -p /tmp/cors-test && cd /tmp/cors-test
cat > index.html <<'EOF'
<!doctype html>
<html>
<body>
  <h3>CORS test</h3>
  <button onclick="run()">Fetch object</button>
  <pre id="out"></pre>
  <script>
    const url = "https://rgw.st1.qa-de-1.cloud.sap/631a3518e93d436fbdf57525babe8606:kiryl-test-bucket/V1.png";
    function run() {
      const out = document.getElementById("out");
      out.textContent = "fetching from origin: " + location.origin + " ...";
      fetch(url)
        .then(r => { out.textContent += "\nOK, status " + r.status; })
        .catch(e => { out.textContent += "\nBLOCKED: " + e; });
    }
  </script>
</body>
</html>
EOF
```

### Шаг 2 — поднять локальный сервер

```bash
cd /tmp/cors-test
python3 -m http.server 8000
```
(если нет python3 — подойдёт `npx serve .` или любой другой статический сервер; смысл один — страница должна открываться по `http://` с конкретным портом, а не как `file://`).

### Шаг 3 — открыть страницу и снять показания

1. Открыть `http://localhost:8000` в браузере.
2. Открыть DevTools → вкладки **Network** и **Console**.
3. Нажать кнопку **Fetch object**.
4. В Network найти запрос к `V1.png` → вкладка Headers:
   - Request Headers: должен быть `Origin: http://localhost:8000`.
   - Response Headers: смотреть, есть ли `access-control-allow-origin`.
5. В Console: если origin не разрешён — будет явная ошибка вида
   `Access to fetch at '...' from origin 'http://localhost:8000' has been blocked by CORS policy: ...`.
   Если разрешён — ошибки нет, на странице появится `OK, status 200`.

### Шаг 4 — проверить оба случая

- **Негативный кейс (по умолчанию):** правило настроено на `https://example.com`, а страница открыта на `http://localhost:8000` → ожидаем блокировку (см. Console).
- **Позитивный кейс:** в Aurora UI отредактировать CORS-правило бакета, добавив `http://localhost:8000` в Allowed Origins → Save → повторить fetch → ожидаем `OK, status 200`, в Response Headers `access-control-allow-origin: http://localhost:8000`.

### Шаг 5 — очистка

```bash
# остановить сервер
# Ctrl+C в терминале, где крутился python3 -m http.server

rm -rf /tmp/cors-test
```
Если временно добавляли `http://localhost:8000` в правило только для теста — убрать его обратно в Aurora UI (или удалить правило полностью, если оно было создано только для этой проверки).

---

## Заметка про `file://` (без сервера)

Если открыть `index.html` двойным кликом (без сервера) — это тоже кросс-доменный запрос, но браузер отправит `Origin: null` (буквально строка `"null"`). Реальный `https://example.com` в правиле её не поймает — будет всегда заблокировано, если только не добавить в Allowed Origins буквально `null` (или `*`). Это самый быстрый способ проверить именно блокировку без поднятия сервера, но не подходит для проверки конкретного разрешённого домена/порта.
