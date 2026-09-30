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
| `main-on-fe1fa280.patch` | `fe1fa280` | Ветка `main`, без issue. Управление S3-кредами (Ceph): модалка Manage Credentials — список ключей с секретами, создание с лимитом 2 на проект и тостом «где найти ключ», удаление, endpoint/region; новая процедура `ec2Credentials.reveal`, permission-ключ `storage:credentials:delete`, детерминированный выбор креда в `resolveEC2Credential`, `createPermissionRouter` больше не роняет весь батч из-за одного отсутствующего правила. 37 файлов. |
