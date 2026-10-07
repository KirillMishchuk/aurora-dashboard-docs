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
| `security-groups-detail-page-on-c084f6ad.patch` | `c084f6ad` | Ветка `kiryl-security-groups-detail-page`: страница деталей Security Group под Juno — заголовок `h2` и порядок полей, раскладка `TwoColumnDescriptionList` на flex, обычные кнопки Add Rule/Share, вкладки на управляемом `TabNavigation` с откатом на Rules при пропаже RBAC. 14 файлов. |
