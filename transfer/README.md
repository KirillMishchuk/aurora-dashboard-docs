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
| `security-groups-form-hints-on-d01c26b4.patch` | `d01c26b4` | Ветка `kiryl-security-groups-form-hints`: help hints и валидация во всех формах Security Groups (по замечанию ревью, сверка с Elektra), обязательная remote-группа, ethertype из CIDR, колонка Remote, ошибки только в модалке со сбросом при закрытии, без Edit/Delete у группы `default`. 52 файла. |
