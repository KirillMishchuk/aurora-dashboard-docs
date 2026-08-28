# PR #1211: refactor(portal): refactor all modals to the same layout

**Автор:** TilmanHaupt · **Статус:** open (не смержен; создан 27.08.2026)
**Ветки:** `til-modal` → `main` · **Файлов:** 33 (+689/-763)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1211

> Closes #1169, #1141. Прямое продолжение паттерна из PR #1198 ("equalize delete modals", смержен 24.08.2026) — оба про унификацию UX модалок подтверждения удаления, и #1211 повторно трогает часть тех же файлов (`DeleteFlavorModal.tsx`, `DeleteImagesModal.tsx`) всего через 3 дня после #1198.
>
> **Повторная проверка 28.08.2026:** головной коммит PR не изменился (`0cb05e66`, подтверждено `git ls-remote` напрямую, в обход кэша API) — с момента первой версии этого отчёта в PR не запушено ни одного нового коммита, так что содержательно перепроверять нечего. За прошедшее время появилась дополнительная живая дискуссия на самом PR: собственный автоматический ревью CodeRabbit независимо поднял два из трёх находок этого отчёта (находки №1 и №3 ниже, дословно теми же словами) плюс детализировал находку по `EmptyContainerModal`; и автор (TilmanHaupt) явно ответил в треде по чекбоксу `ImageListView` — "no current behaviour is intended", что читается как подтверждение того, что текущее поведение — баг, а не осознанный выбор (сняло двусмысленность, которая была в первой версии этого отчёта). Отчёт ниже обновлён с учётом этого; сама находка и её обоснование не изменились.

## Что сделано

Issue #1141 просил привести все модалки удаления/действий к визуальной консистентности с уже существующими Ceph-модалками; issue #1169 просил убрать чекбоксы bulk-действий из хедер-ячеек `DataGrid` (по скриншоту — счёл их неуместными там). PR вводит новый общий хук `useDeleteConfirmation` (`packages/aurora/src/client/hooks/useDeleteConfirmation.ts`, новый файл, оборачивает уже существующий `useModalTracking`) и переводит на него ~15 модалок подтверждения удаления/detach/release/remove по всему приложению: Compute (`DeleteFlavorModal`, `DeleteImageModal`, `DeleteImagesModal`, `DeactivateImagesModal`), Network (`DetachFloatingIpModal`, `ReleaseFloatingIpModal`, `DeleteRBACPolicyDialog`, `DeleteRuleDialog`, `DeleteSecurityGroupDialog`), Storage (`DeleteContainerModal`, `EmptyContainerModal`, `DeleteObjectsModal` — Swift; `DeleteObjectModal` — Ceph, только визуально; `DeleteLifecycleRuleModal`/`DeleteLifecycleRulesModal` — только lint-правки). Большинство модалок, использовавших `@tanstack/react-form`+zod или ручной `useState`/`useEffect`, переведены на единый хук с общей логикой `confirmText`/`isConfirmed`/`error`/analytics-трекинга.

Попутно: Ceph `DeleteObjectModal` переведён с самодельной вёрстки на `DescriptionList`; Swift `EmptyContainerModal` — список объектов с `DataGrid`-таблицы на простой скроллящийся `Stack` (по образцу Images) и кнопка `Empty` → `Empty Container`; `DeactivateImagesModal` лишился summary-блока; `ImageListView` лишилась импорта `Checkbox` — но не как заявлено в описании PR (см. "Ревью", находка №1).

## Как это реализовано

### Общий хук `useDeleteConfirmation`

```ts
// packages/aurora/src/client/hooks/useDeleteConfirmation.ts (новый файл)
export const useDeleteConfirmation = ({ isOpen, confirmWord = "delete", trackingPrefix }) => {
  const [confirmText, setConfirmText] = useState("")
  const [error, setError] = useState<string | null>(null)
  const { trackClose, markSubmitted, resetTracking } = useModalTracking({
    isOpen,
    actionPrefix: `${trackingPrefix}.${confirmWord === "delete" ? "delete" : confirmWord}`,
  })
  const isConfirmed = confirmText.trim() === confirmWord
  useEffect(() => { if (!isOpen) { setConfirmText(""); setError(null); resetTracking() } }, [isOpen, resetTracking])
  return { confirmText, setConfirmText, isConfirmed, error, setError, trackClose, markSubmitted }
}
```

Потребители задают свой `confirmWord` ("delete"/"detach"/"release"/"remove") и `trackingPrefix`. Большинство модалок используют `isConfirmed` напрямую для гейтинга кнопки подтверждения (`disableConfirmButton={!isConfirmed || isLoading}`) — проверено по каждой из них, гейтинг везде вёрно подключен. Две модалки (`EmptyContainerModal`, `DeleteContainerModal` — Swift) требуют ввода ИМЕНИ контейнера, а не слова "delete"; они инстанциируют хук с `confirmWord: "delete"` только ради ярлыка трекинга, но гейтинг делают вручную через `confirmText.trim() !== container.name` — `isConfirmed` от хука там нигде не читается (проверено), так что подмены семантики не происходит.

### Регресс в `ImageListView.tsx` — чекбокс "выбрать всё" (см. находку №1 в "Ревью")

Внутри самого PR чекбокс header-ячейки сначала был убран (промежуточный коммит `4620dd24`, закрывая #1169 буквально), а затем **возвращён обратно** последним коммитом `4c7aaa3e` ("...add select-all checkbox to ImageListView", без описания) — уже в виде голого `<input type="checkbox">` со сравнением по количеству вместо по id, вместо прежнего `Checkbox` из Juno.

## Что затронуло

Все затронутые модалки — компоненты с ровно одним потребителем каждая (внутреннее использование), контрактных изменений наружу пакета нет. Единственное по-настоящему widespread изменение — сам хук `useDeleteConfirmation`, но он новый и никем, кроме этого PR, ещё не используется вне этих модалок.

`DeleteFlavorModal.tsx` и `DeleteImagesModal.tsx` — те же файлы, что чинил PR #1198 три дня назад. Из двух известных находок ≥80 отчёта по #1198: баг с `flavor.swap` (`undefined`/строковый `"0"` → "NaN MiB"/"0 MiB" вместо "None") — не тронут этим PR, всё ещё присутствует (не репортится здесь: строка вне диффа #1211). Недостижимый экран результатов `DeleteImagesModal` (`result` никогда не устанавливается, `onDelete` не имеет колбэка/пропа для передачи результата назад) — тоже не тронут: `handleConfirm` по-прежнему вызывает `onDelete(deletableImages)` с тем же комментарием "Parent component should call setResult...", несмотря на то что файл снова редактировался в этом PR (только ради подключения нового хука). Обе — не находки этого PR (они вне диффа), но раз файл трогали второй раз за неделю и снова не заметили — стоит знать.

## Ревью

**Найдено (confidence ≥ 80):**

1. **`ImageListView.tsx` — чекбокс "выбрать всё" в хедере `DataGrid` ломает мультистраничный выбор и показывает неверное состояние.** (confidence 98)
   ```tsx
   // ДО (Checkbox из Juno, page-aware, сохраняет выбор с других страниц):
   checked={currentPageIds.length > 0 && currentPageIds.every((id) => selectedImages.includes(id))}
   onChange={() => allSelected
     ? setSelectedImages(selectedImages.filter((id) => !currentPageIds.includes(id)))
     : setSelectedImages([...new Set([...selectedImages, ...currentPageIds])])}

   // ПОСЛЕ (голый <input>, сравнение по количеству):
   checked={selectedImages.length === images.length && images.length > 0}
   onChange={(e) => e.target.checked ? setSelectedImages(images.map((img) => img.id)) : setSelectedImages([])}
   ```
   `images` внутри `ImageListView` — это `paginatedImages` (срез ТЕКУЩЕЙ страницы, `PAGE_SIZE = 50`, `Images/List.tsx:31`), а `selectedImages` — состояние уровня роута, накапливающееся МЕЖДУ страницами (не сбрасывается при смене страницы). Отсюда два независимо воспроизводимых сценария: (а) выбрать 50 изображений на странице 1, перейти на страницу 2 (тоже 50 штук) — чекбокс покажется отмеченным, хотя ни один элемент страницы 2 не выбран (`50 === 50`); (б) отметить чекбокс на любой странице стирает ВЕСЬ кросс-страничный выбор и заменяет его только текущей страницей (`setSelectedImages(images.map(...))`), снять галочку — обнуляет выбор на ВСЕХ страницах (`setSelectedImages([])`), а не только текущей.
   Это не гипотетический риск: рядом, в `List.tsx` (не тронут этим PR), есть свой корректный чекбокс "выбрать всё" в Zone 3 тулбаре — с `indeterminate`, объединением/вычитанием только id текущей страницы — то есть рабочий референс поведения лежит в той же кодовой базе. Более того, `git blame` показывает, что старая cross-page-safe логика была не случайной — это осознанный фикс из PR #785 (коммит `6c5cc29a`, "fix cross-page select-all checkbox... enabling correct cross-page selection"), который #1211 отменяет, реинтродуцируя тот же класс бага, что уже однажды чинили в этом коде.
   Подтверждено независимо: живые комментарии Copilot и CodeRabbit на самом PR #1211 (`ImageListView.tsx:612/617/623`) указывают на то же — чекбокс в хедере вообще противоречит issue #1169, на который ссылается PR ("Remove the header bulk-selection control... Issue #1169 requires removal of bulk-action checkboxes from DataGrid header cells. This change leaves that control in place"), и ломает мультистраничный выбор ("discards selections from other pages... changes behavior from 'toggle current page' to 'toggle everything'"). Автор (TilmanHaupt) ответил на этот тред "no current behaviour is intended" — читаем как подтверждение того, что текущее поведение не задумано (то есть баг признан), а не как защиту решения; вопрос при этом остаётся открытым — фикса на момент повторной проверки (28.08.2026, тот же коммит `0cb05e66`) всё ещё нет.
   Файлы: `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Images/-components/ImageListView.tsx:610-627`, `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Images/List.tsx:150-151,300-320` (референс корректного поведения, не тронут).

2. **`.changeset/swift-ceph-delete-modals.md` заметно недооценивает реальный охват PR.** (confidence 85)
   Changeset называет 4 пункта: Swift `DeleteObjectModal` (confirm-инпут), Ceph `DeleteObjectModal` (DescriptionList), Swift `EmptyContainerModal` (лейбл/список), Images (неиспользуемый импорт Checkbox). Ни слова о новом хуке `useDeleteConfirmation` и его подключении к `DeleteFlavorModal`, `DeleteImageModal`, `DeleteImagesModal`, `DetachFloatingIpModal`, `ReleaseFloatingIpModal`, `DeleteRBACPolicyDialog`, `DeleteRuleDialog`, `DeleteSecurityGroupDialog`, `DeleteContainerModal` (Swift), ни об удалении summary-блока в `DeactivateImagesModal` — это порядка 20+ из 33 изменённых файлов. Читатель changelog не узнает, что PR поменял поведение подтверждения удаления в Compute, Network и большей части Storage. Тот же паттерн, что уже отмечался в этой базе знаний для PR #1172 ("changeset обещает CORS UI, но коммит переименовывает лейблы во всех Ceph Buckets/Objects компонентах").
   Файл: `.changeset/swift-ceph-delete-modals.md`.

3. **`DeleteImageModal.tsx` не вызывает `markSubmitted()` — трекинг отправки удаления образа молча не срабатывает.** (confidence 80)
   Хук `useDeleteConfirmation` документирован как обрабатывающий «confirmation text validation, error state, **and analytics tracking**» и его собственный `@example` в JSDoc показывает деструктуризацию `trackClose`/`markSubmitted` наравне (пример скопирован из `DeleteFlavorModal`, которая обе функции действительно вызывает). `DeleteImageModal.tsx` же деструктурирует только `trackClose` — `handleConfirm` вызывает `onDelete(image); handleClose()` и никогда `markSubmitted()`. В отличие от `DeleteFlavorModal`/`DeleteImagesModal`/большинства других потребителей хука (которые вызывают `markSubmitted()` перед отправкой действия), удаление одиночного образа не фиксируется как «submitted»-событие в аналитике — трекается только закрытие модалки. Не влияет на функциональность удаления, но незаметно ломает часть контракта, который хук заявляет предоставлять, и который у самого хука есть пример правильного использования.
   Файл: `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/-components/Images/-components/DeleteImageModal.tsx:36-48`. Независимо подтверждено собственным автоматическим ревью CodeRabbit на этом PR, дословно тем же выводом: «`handleConfirm` calls `onDelete(image)` and then `handleClose()`. Because `markSubmitted()` is not called, `trackClose()` emits `compute.image.delete.close`. Call `markSubmitted()` before `onDelete(image)`» — не закрыто на момент повторной проверки.

**Также замечено (confidence 50-79, не набрало полной уверенности):**
- **[75]** `DeleteFlavorModal.tsx:87` — заголовок `t\`Delete Flavor "${flavorName}"\`` не защищён от `flavor === null` (пропс `flavor: Flavor | null`); при null `flavorName` — `undefined`, заголовок буквально показывает `Delete Flavor "undefined"`. Тело модалки такую защиту имеет (`{flavor && (...)}`), заголовок — нет. Живой комментарий Copilot на этом PR указывает то же самое ("the title should also gracefully fall back"), до сих пор не закрыт; реальная воспроизводимость ограничена узким окном (переходная анимация закрытия модалки, если `flavor` сбрасывается раньше, чем `isOpen` становится `false`), поэтому не поднято до headline-находки. Отдельно от этого CodeRabbit оставил на той же строке чисто lint-комментарий (вынести `flavor?.name` в переменную ради правила `eslint-plugin-lingui`'s `no-expression-in-message`) — это другой, не функциональный повод, и именно его автор пометил "declined"; к null-safety заголовка это решение не относится, вопрос остаётся открытым.
- **[70]** Swift Objects `DeleteObjectModal.tsx` — новый инпут подтверждения (добавлен именно этим PR, локальный `useState`, не через общий хук) использует `confirmText === "delete"` без `.trim()`, в отличие от самого хука `useDeleteConfirmation` (который через `.trim()` прощает случайные пробелы). Живой комментарий CodeRabbit на этом PR (с готовым однострочным фиксом), не закрыт.
- **[65]** `EmptyContainerModal.tsx` — сообщение "Showing first N of total" опирается на потенциально устаревший `container.count` относительно жёсткого лимита показа в 100 объектов: если реальных объектов ровно 100+ и `container.count` отстаёт (≤100), модалка покажет усечённый список без предупреждения об усечении. Живой комментарий CodeRabbit на этом PR с конкретным предложением фикса (запросить на один объект больше лимита или использовать метаданные пагинации вместо `container.count`), не закрыт.
- **[60]** Описание PR "DeactivateImagesModal: Removed redundant summary section (count already shown in section headers)" верно только для `activeCount` (реально дублируется в заголовке "Images to be deactivated (N)"); `deactivatedCount` — счётчик «уже деактивированных, будут пропущены» — нигде больше не отображается после удаления блока, то есть теряется, а не дублируется.

**Не репортится отдельно** (по установленной в этой базе знаний практике, см. отчёт по #1198): новые/изменившиеся заголовки/лейблы (`Delete Flavor "{flavorName}"`, `Detach Floating IP "{floating_ip_address}"` и т.п.) поставлены с пустым `msgstr` в `de/messages.po` — для части из них (Floating IP модалки) это фактически регресс отображения (раньше немецкий текст был, теперь пуст, потому что изменился msgid), но переводы в этом репозитории добавляются отдельным проходом, и это не считается блокирующим дефектом по прежней практике ревью.

---
Проанализировано: 27.08.2026 · коммит `0cb05e66` · повторно проверено 28.08.2026 (тот же коммит, новых изменений кода нет — обновлена только живая дискуссия на PR)
