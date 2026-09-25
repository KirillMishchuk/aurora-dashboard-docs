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
| `s3-version-pagination-on-18422781.patch` | `18422781` | Ветка `kiryl-s3-version-pagination`, PR #1331: третий раунд Copilot-ревью — смена версионирования теперь обновляет оба запроса статуса через новый `invalidateVersioningStatusQueries` (бейдж в шапке бакета больше не зависает на старом значении), плюс UI-мелочи: пункты меню Restore переименованы в Restore Folder / Restore Version, убран заголовок Actions над колонкой действий в истории версий. 16 файлов. |
