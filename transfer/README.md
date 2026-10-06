# transfer

Незакоммиченные изменения aurora-dashboard, которые едут между машинами через этот репозиторий.
Каждый файл — `git diff --cached --binary`, снятый с рабочего дерева; имя содержит базовый коммит.

## Как применить

```bash
cd <путь к aurora-dashboard>
git fetch origin
git checkout <база из имени патча>          # напр. 9775e4bb
git apply <путь к DOCS>/transfer/<файл>.patch
```

Полезное:

- `git apply --check <файл>.patch` — проверить, ляжет ли, ничего не меняя.
- `git apply --index <файл>.patch` — применить сразу в индекс (как было на исходной машине).
- `git apply --3way <файл>.patch` — если база разъехалась: смержит вместо отказа.

## Патчи

| Патч | База | Что внутри |
| --- | --- | --- |
| `security-groups-form-hints-on-9b3ff989.patch` | `9b3ff989` | Ветка `kiryl-security-groups-form-hints`, PR #1368, поверх коммитов PR: правки по замечаниям Copilot — поиск по колонке Remote, ошибка ICMP type под Code, required-ошибки у Select'ов Rule Type и Remote Security Group, подсказки у Description и очистка описания в Edit. 18 файлов. |
