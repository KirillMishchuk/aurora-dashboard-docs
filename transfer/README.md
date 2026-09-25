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
| `revert-storage-server-search-on-6ce6aeac.patch` | `6ce6aeac` | Ветка `kiryl-revert-storage-server-search`. Откат сторадж-части PR #1320: Ceph Buckets и Swift Containers возвращены к клиентской фильтрации (состояние `dc918d47`) — `searchTerm` убран из обеих `listContainersInputSchema` и из роутеров, на клиенте восстановлены фильтр по имени и счётчик «X of Y», сброс выбора при поиске удалён, два msgid возвращены в `en`/`de`. Flavors, Images, Projects, Floating IPs и `filterBySearchParams` не тронуты. 12 файлов. |
