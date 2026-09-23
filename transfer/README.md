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
| `1004-on-dc918d47.patch` | `dc918d47` | Ветка `kiryl-issue-1004-s3-version-pagination`, issue #1004: ограничение пагинации S3-версий и серверное определение состояния бакета (`containers.getState`, `checkDeletedContent` одним сканом префикса), плюс фикс «Delete Versions», сносившего весь бакет (`objects.deleteNonCurrentVersions`). 50 файлов, из них 6 новых и 1 удалённый. |
