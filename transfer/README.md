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
| `ceph-credentials-on-e28580d4.patch` | `e28580d4` | Ветка `kiryl-ceph-credentials`, PR #1362 (issue #1358): правки по фидбэку ревьюера: ошибки бакетов через `Status` (Access Denied, S3 Authentication Failed), новые ключи сверху списка, toast создания 10 с, сокращённый changeset и исправленные комментарии; 15 файлов. |
