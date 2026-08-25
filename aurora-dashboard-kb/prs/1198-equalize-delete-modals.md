# PR #1198: refactor(portal): equalize delete modals

**Автор:** TilmanHaupt · **Статус:** смержен 24.08.2026 (коммит `1513d972`; создан 21.08.2026)
**Ветки:** `til-del-mod` → `main` · **Файлов:** 13 (+453/-362)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1198

## Что сделано

PR приводит три "удаляющих" модалки Compute-раздела (Flavors, single/bulk Images) и одну Storage-модалку (Swift `DeleteContainerModal`) к единому паттерну, уже принятому в Ceph (`DeleteObjectsModal` и т.п.): вместо самодельного `ModalFooter`/`ButtonRow`/`Button` — встроенные пропы `Modal` (`confirmButtonLabel`, `confirmButtonVariant`, `onConfirm`, `disableConfirmButton`/`disableCancelButton`/`disableCloseButton`). Для необратимых удалений (Flavor, single Image, bulk Images) добавлено типизированное подтверждение — `TextInput` с плейсхолдером `delete`, кнопка подтверждения задизейблена, пока введённый текст не совпадёт со словом `delete`. `DeleteFlavorModal` заодно переведён с `TwoColumnDescriptionList` на одноколоночный `DescriptionList` (для единообразия с Images/Storage), а `DeleteImagesModal` — с плоского списка ID на заявленный двухшаговый флоу «подтверждение → экран результатов с ошибками». Есть сопутствующий changeset (`patch`) и правки локализации (en/de).

## Как это реализовано

**Общий паттерн подтверждения** (`DeleteFlavorModal.tsx:193-194`, `DeleteImageModal.tsx:430-431`, `DeleteImagesModal.tsx` аналогично):

```tsx
const isConfirmValid = confirmText === "delete"
const confirmLabel = isLoading ? t`Deleting...` : t`Delete Flavor`
...
disableConfirmButton={!isConfirmValid || isLoading}
```

`DeleteFlavorModal` (`DeleteFlavorModal.tsx:52-73`) теперь сам вызывает `client.compute.deleteFlavor.mutate(...)`, ловит ошибку, показывает её инлайн (`role="alert"`) и остаётся открытым при отказе — раньше `flavor.swap` показывался в списке `TwoColumnDescriptionList` только если он truthy, теперь строка `Swap` рендерится всегда:

```tsx
// DeleteFlavorModal.tsx:127
{flavor.swap === 0 || flavor.swap === "" ? <Trans>None</Trans> : `${Number(flavor.swap)} MiB`}
```

**`DeleteImagesModal`** (единственная модалка, где реализован именно двухшаговый флоу) хранит `result` в локальном состоянии и переключает вид модалки по нему (`DeleteImagesModal.tsx:14-33`):

```tsx
interface DeleteResult {
  deletedCount: number
  errorCount: number
  errors: Array<{ imageId: string; message: string }>
}
...
const [result, setResult] = useState<DeleteResult | null>(null)
```

`handleConfirm` (`DeleteImagesModal.tsx:44-51`):

```tsx
const handleConfirm = () => {
  if (result === null) {
    // Step A: Confirm
    onDelete(deletableImages)
    // Note: Parent component should call setResult after getting backend response
  } else {
    // Step B: Close results view
    handleClose()
  }
}
```

`DeleteContainerModal` (Swift) переведён на встроенные пропы и для ветки "в контейнере есть объекты" — раньше отдельная кнопка `Close` через `modalFooter`/`data-testid="delete-has-objects-close-button"`, теперь просто `confirmButtonLabel={hasObjects ? t\`Close\` : t\`Delete\`}` (`DeleteContainerModal.tsx:129-131`).

## Что затронуло

Все четыре модалки — только внутреннее использование, у каждой ровно один потребитель:

- `DeleteFlavorModal` ← `FlavorListContainer.tsx`, `compute/flavors/$flavorId.tsx`
- `DeleteImageModal` ← `ImageListView.tsx`, `compute/images/$imageId.tsx`
- `DeleteImagesModal` ← `ImageListView.tsx` (единственный, `ImageListView.tsx:777-784`)
- `DeleteContainerModal` ← `ContainerTableView.tsx`

Пропы этих компонентов (кроме `DeleteImagesModal`, см. ревью) не менялись — контрактных изменений наружу нет, changeset корректно помечен `patch`.

## Ревью

Пайплайн (CLAUDE.md-соответствие, беглый поиск багов, исторический контекст git blame/log, прежние PR-комментарии CodeRabbit/Copilot на этот PR, соответствие кодовым комментариям) плюс независимый confidence-scoring дал две находки с уверенностью ≥80:

1. **Экран результатов `DeleteImagesModal` недостижим — `result` никогда не устанавливается** (confidence 100) — `DeleteImagesModal.tsx:44-51`, потребитель `ImageListView.tsx:470-471,777-784`. `handleConfirm` при `result === null` вызывает `onDelete(deletableImages)` и полагается на комментарий «Parent component should call setResult after getting backend response» — но `result`/`setResult` это приватное состояние компонента, `DeleteImagesModalProps` не содержит ни коллбэка, ни проп для передачи результата обратно. Единственный потребитель, `ImageListView.handleBulkDelete` (`ImageListView.tsx:470-496`), в первой же строке делает `setDeleteAllModalOpen(false)` — то есть закрывает модалку (`isOpen` становится `false`) ещё до того, как мутация отработает — и сообщает об итоге через уже существующие тосты (`toast.success`/`error`/`warning`), а не через модалку. В результате `result` навсегда остаётся `null`, весь код «Step B: Results view» (строки `DeleteImagesModal.tsx:56-120`, включая обработку `errors`/`hiddenErrorCount`) — мёртвый, пользователь никогда не увидит экран результатов, заявленный в описании PR как основная фича («two-step flow: confirmation input → results view with error reporting»). Независимо подтверждено двумя ботами на этом же PR (CodeRabbit, severity "Major": «`result` remains `null` and the results view is unreachable after every bulk deletion»; Copilot: то же самое, с предложенным фиксом — либо `onDelete` возвращает `Promise<DeleteResult>` и `handleConfirm` его `await`-ит, либо результат передаётся в модалку новым пропом, по аналогии с Ceph `DeleteObjectsModal`) — эти комментарии всё ещё указывают на текущий head (`a613b137`), то есть не устарели и не были закрыты последующими коммитами.
2. **Отображение `Swap` в `DeleteFlavorModal` даёт `NaN MiB`/`0 MiB` вместо `None` для реальных значений API** (confidence 90) — `DeleteFlavorModal.tsx:127`, тип `flavor.swap` — `packages/aurora/src/server/Compute/types/flavor.ts:8-19` (`swap: z.union([z.string(), z.number()]).optional()`). Проверка `flavor.swap === 0 || flavor.swap === ""` ловит только числовой `0` и пустую строку. Она не ловит: (а) `flavor.swap === undefined` — Zod-схема делает поле `optional()`, и в этом случае `${Number(flavor.swap)} MiB"` даёт `${Number(undefined)}` = `"NaN MiB"`; (б) строковый `"0"` — судя по фикстурам `flavorHelpers.test.ts:47,58,69` (`swap: "0"`), это типичное значение, которое реально отдаёт Nova для флейворов без свопа на части OpenStack-версий, и `Number("0")` даёт `0`, так что ветка `None` не срабатывает — рендерится `"0 MiB"`, то есть ровно то поведение, которое changeset этого PR заявляет как исправленное («fix swap display to show "None" instead of "0 MiB"»). До PR строка `Swap` в этом случае просто не показывалась (`...(flavor?.swap ? [...] : [])` — falsy-check пропускал и `0`, и `"0"`, и `undefined`), так что для этих двух реалистичных случаев это в чистом виде регрессия отображения, а не только недоделанный фикс. Соседний компонент того же домена, `FlavorListContainer.tsx:180`, использует общий приём `flavor.swap || "–"`, что подтверждает: falsy-значения `swap` (включая `"0"`) — ожидаемый, а не краевой случай в этой кодовой базе.

Ниже порога (не репортится): в `DeleteContainerModal.test.tsx` тест «renders Close button instead of Delete» проверяет `screen.getAllByRole("button", { name: /^Close$/i }).length).toBeGreaterThan(0)` — по клону Juno (`Modal.test.tsx:211`) собственная кнопка-крестик модалки имеет `aria-label="close"`, которая тоже подпадает под этот регистронезависимый паттерн, так что тест прошёл бы, даже если бы новая кнопка подтверждения `Close` вообще не отрендерилась; чисто тестовая недостаточность, не влияет на прод-поведение (confidence 50). Отсутствие немецких переводов для новых строк (`de/messages.po`, отмечено CodeRabbit) не репортится отдельно — в этом репозитории пустой `msgstr` для новых строк на момент PR является обычной практикой (переводы добавляются отдельным проходом), а не блокирующим дефектом.

---
Проанализировано: 24.08.2026 · коммит `a613b137`
