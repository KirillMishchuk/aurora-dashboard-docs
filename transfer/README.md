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
| `main-on-fe1fa280.patch` | `fe1fa280` | Ветка `main`, локальные правки без issue. Модалка «Manage S3 Credentials» для Ceph: просмотр своих EC2-кредов с секретом, создание (лимит 2 на пользователя в проекте) и удаление; новый permission-ключ `storage:credentials:delete`; `containers.status` отдаёт endpoint/region; починен `createPermissionRouter` — отсутствующее правило больше не роняет весь батч `canUser`. 37 файлов. |
