# PR #1180: fix(portal): use positive phrasing for quota validation message

**Автор:** mark-karnaukh-extern-sap · **Статус:** открыт, не смержен (создан 18.08.2026; 1 из 2 требуемых аппрувов получен — KirylSAP)
**Ветки:** `mark-use-positive-quota-validation-message` → `main` · **Файлов:** 7 (+40/-16)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1180

## Что сделано

Правит сообщение об ошибке валидации квот Swift-контейнера (issue #1164, "Bug: use positive instruction, not double-negative"): вместо двойного отрицания "Must be a non-negative integer" — прямая инструкция "Must be a whole number, 0 or greater" (рус. по смыслу: «Должно быть целым числом, 0 или больше»). Затронуты оба поля квоты — `quota-bytes` (Total size quota) и `quota-count` (Object count quota) — в модалке `EditContainerMetadataModal` (Storage → Swift → Containers).

PR состоит из 4 коммитов: сама смена формулировки (`cdd7d55`), обновление переводов (`ae0dc58`), **отдельный фикс-коммит `f7f577c` "reject non-integer quota values"**, добавляющий проверку `Number.isInteger` — то есть до этого коммита валидация пропускала дробные значения типа `1.5`, и это было исправлено в рамках того же PR, — и, наконец, changeset (`2aeef4c`, текущий head).

## Как это реализовано

`validateQuotas` (`EditContainerMetadataModal.tsx:209-230`) проверяет оба поля тремя условиями вместо двух:

```ts
// EditContainerMetadataModal.tsx:211-219
if (
  quotaBytes !== "" &&
  (isNaN(Number(quotaBytes)) || !Number.isInteger(Number(quotaBytes)) || Number(quotaBytes) < 0)
) {
  setQuotaBytesError(t`Must be a whole number, 0 or greater`)
  valid = false
} else {
  setQuotaBytesError(null)
}
```

Симметричный блок для `quotaCount` — `EditContainerMetadataModal.tsx:220-228`, та же троица проверок и тот же текст ошибки. Оба поля — обычные `TextInput` (не `type="number"`, `EditContainerMetadataModal.tsx:498-510`), состояние — строки (`useState("")`, строки 116/118), так что вся защита от нецелых/отрицательных значений держится на этой ручной проверке. На сохранении (`EditContainerMetadataModal.tsx:328` — `if (!validateQuotas()) return`) форма блокируется при ошибке; при успехе значение уходит в мутацию как `Number(quotaBytes)` (`EditContainerMetadataModal.tsx:377`) — уже безопасно, раз `Number.isInteger` прошёл проверку на этапе валидации.

Тесты (`EditContainerMetadataModal.test.tsx`) обновлены на новый текст ошибки везде, где он проверялся (было "Must be a non-negative integer"), и добавлен новый кейс "shows validation error for decimal quota-bytes" (ввод `"1.5"` для Total size quota) — но симметричного теста на дробное значение для `quotaCount` не добавлено, хотя код обрабатывает оба поля одинаково.

Переводы: `packages/aurora/src/locales/{en,de}/messages.po` — старая строка `msgid "Must be a non-negative integer"` удалена, добавлена новая `msgid "Must be a whole number, 0 or greater"` (нем. `"Muss eine ganze Zahl sein, 0 oder größer"`); скомпилированные `messages.ts` регенерированы вместе с ней. Changeset `.changeset/witty-numbers-poke.md` — `patch` для `@cobaltcore-dev/aurora`, корректно (текстовая правка + расширение валидации, без изменения публичного контракта).

## Что затронуло

`EditContainerMetadataModal` не экспортируется из пакета — единственный потребитель найден в той же папке, `ContainerTableView.tsx` (`import { EditContainerMetadataModal } from "./EditContainerMetadataModal"`). Изменение полностью внутреннее, наружу (за пределы Swift Containers UI) не ripple-ит.

Поиск по остальному монорепо на похожие формулировки валидации количества (`non-negative`, `isInteger`) нашёл только несвязанный сосед — `EditImageDetailsModal.tsx` (Compute/Images, поля `min_disk`/`min_ram`) использует свой текст «Minimum disk/RAM must be 0 or greater», уже позитивный и не тронутый этим PR — не тот же текст, что менялся здесь, так что это не пропущенный дубликат, а изначально другая формулировка; упоминаю только чтобы явно исключить как ложную находку.

**Важно для читателя отчёта:** описание PR (раздел "Notes") утверждает, что «валидатор не проверяет целочисленность» и характеризует это как нерешённый follow-up для будущего UX-ревью. Это устарело относительно текущего head-коммита — коммит `f7f577c`, уже входящий в этот PR, добавил именно эту проверку (`!Number.isInteger(...)`) до создания changeset'а. На момент анализа (head `2aeef4c`) валидация целочисленности реализована и покрыта тестом.

## Ревью

Проблем с уверенностью ≥80 не найдено. Логика симметрична для обоих полей, конвертация в payload (`Number(quotaBytes)`) безопасна благодаря предшествующей проверке `Number.isInteger`, коммит-сообщения и scope (`portal`) соответствуют `commitlint.config.mjs`, changeset корректен по типу (`patch`). Ниже порога: отсутствие теста на дробное значение для `quotaCount` (код идентичен `quotaBytes`, тестовая асимметрия не влияет на поведение) — нитпик, не репортится как находка.

---
Проанализировано: 18.08.2026 · коммит `2aeef4c`
