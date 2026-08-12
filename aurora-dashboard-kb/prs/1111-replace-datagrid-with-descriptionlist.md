# PR #1111: refactor(ui): replace data-grid with description-list

**Автор:** vlad-schur-external-sap · **Статус:** смержен 30.07.2026 (`cf2e0ad0`)
**Ветки:** `vlad-replace-datagrid-with-descriptionlist` → `main` · **Файлов:** 20 (+461/-658)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1111

## Что сделано

Широкий UI-рефакторинг: замена табличной вёрстки `DataGrid`/`DataGridRow`/`DataGridCell`/`DataGridHeadCell` на key/value-вёрстку `DescriptionList`/`DescriptionTerm`/`DescriptionDefinition` в деталках и модалках Flavors, Images, Security Groups:

1. **Flavors** — `DeleteFlavorModal`, `EditSpecModal` (таблица extra specs), `SpecFormRow`, `SpecRow`, `FlavorDetailsView`.
2. **Images** — `ActivateImageModal`, `DeactivateImageModal`, `DeleteImageModal`, `EditImageMetadataModal`, `ImageDetailsView`.
3. **Security Groups** — `SecurityGroupBasicInfo` (была 4-колоночная `DataGrid`).
4. **Общий компонент**: `TwoColumnDescriptionList` (раньше жил только в `network/floatingips/$floatingIpId/-components/`) вынесен в общее место `packages/aurora/src/client/components/TwoColumnDescriptionList.tsx`, тип `DetailListItem` расширен (`label`/`value` теперь принимают `ReactNode`, добавлено опциональное `id` для React-ключей вместо `key={label}`):
   ```tsx
   // TwoColumnDescriptionList.tsx:4-16
   export type DetailListItem = {
     id?: string
     label: string | ReactNode
     value: string | number | ReactNode | undefined
   }
   ...
   export const TwoColumnDescriptionList = ({ items }: TwoColumnDescriptionListProps) => {
     const mid = Math.ceil(items.length / 2)
     const firstColumn = items.slice(0, mid)
     const secondColumn = items.slice(mid)
   ```
5. Побочно: удалён неиспользуемый barrel-реэкспорт `RBACPolicyRow` из `securitygroups/.../-details/index.ts` (проверено — единственный потребитель импортирует напрямую из `./RBACPolicyRow`, реэкспорт был мёртвым) и внесена не связанная с темой PR правка в Swift `EmptyContainerModal.tsx` (`max-w-[400px]` → `max-w-100`, `max-w-[200px]` → `max-w-50`).

## Как это реализовано

`EditSpecModal.tsx` добавляет guard от двойной отправки формы (раньше отсутствовал):
```tsx
// EditSpecModal.tsx:121, 129, 155-157
if (isSavingSpec) return
...
try {
  setIsSavingSpec(true)
  ...
} finally {
  setIsSavingSpec(false)
}
```
и передаёт это состояние в `SpecFormRow` как `isLoading={isSavingSpec}` (раньше был захардкожен `isLoading={false}`) — форма теперь корректно блокируется на время запроса.

`SecurityGroupBasicInfo.tsx` — было (4-колоночная таблица с truncation):
```tsx
// база e04eed1:26-42
<DataGrid columns={4} gridColumnTemplate="15% 35% 15% 35%">
  <DataGridRow>
    <DataGridHeadCell>{t`Description`}</DataGridHeadCell>
    <DataGridCell colSpan={3}>
      <div className="overflow-hidden text-ellipsis whitespace-nowrap" title={securityGroup.description || undefined}>
        {securityGroup.description || t`—`}
      </div>
    </DataGridCell>
  </DataGridRow>
```
стало:
```tsx
// SecurityGroupBasicInfo.tsx:15-23, 35
const securityGroupItems = [
  { label: t`Description`, value: securityGroup.description || t`—` },
  { label: t`ID`, value: securityGroup.id },
  { label: t`Tags`, value: securityGroup.tags?.join(", ") || t`—` },
  ...
]
...
<TwoColumnDescriptionList items={securityGroupItems} />
```

## Что затронуло

- **Внутреннее изменение presentational-компонентов**, без изменения публичных пропсов/API наружу. `TwoColumnDescriptionList` теперь используется 5 файлами (`DeleteFlavorModal`, `FlavorDetailsView`, `ImageDetailsView`, `FloatingIpDetailsView`, `SecurityGroupBasicInfo`) — проверено, что более широкий тип `DetailListItem` (принимающий `ReactNode`/`number`/`undefined`) не ломает единственного прежнего потребителя `FloatingIpDetailsView` (передаёт только строки, совместимо); смена стратегии React-ключа с `key={label}` на `key={id ?? \`left-${index}\`}` тоже безопасна для него (статичный список, не переупорядочивается).
- **Отсутствует changeset**: PR затрагивает 20 файлов пользовательского UI, но не добавляет `.changeset/*.md` — нарушает устоявшуюся практику (все сопоставимые недавние PR добавляли свой: #1099, #1090, #1086, #1088, #952).
- **Описание PR неточно** характеризует исходную вёрстку как "single column layouts" — на деле `EditSpecModal.tsx` (3-колоночная `DataGrid`), `EditImageMetadataModal.tsx` (3-колоночная) и `SecurityGroupBasicInfo.tsx` (4-колоночная, `gridColumnTemplate="15% 35% 15% 35%"`) уже были многоколоночными таблицами до этого PR.
- **Два замечания автоматических ботов GitHub (Copilot/CodeRabbit) в самом PR оказались неактуальны** при проверке против текущего head-коммита:
  - CodeRabbit указывал на "double-submit risk" из-за захардкоженного `isLoading={false}` в `EditSpecModal.tsx` — комментарий относится к более раннему коммиту в истории пушей этого PR (`original_line: 222`); в текущем head-коммите это уже исправлено через `isSavingSpec` (см. "Как это реализовано" выше).
  - Copilot указывал, что `<p>` рендерится прямо внутри `<DescriptionList>` (`<dl>`) в `EditImageMetadataModal.tsx` — GitHub сам пометил комментарий как *outdated* (`line: None`, `original_line: 387`); в текущем коде `<p>` и `<DescriptionList>` — альтернативы тернарного оператора, а не вложенность.
  - Замечание Copilot про `max-w-100` ("не стандартная Tailwind-утилита") в `EmptyContainerModal.tsx`, вероятно, тоже ложное срабатывание: проект использует Tailwind v4.1.7, где произвольное числовое значение `N` для spacing-утилит транслируется как `calc(var(--spacing) * N)` (по умолчанию `--spacing: 0.25rem`) — `max-w-100` = 400px, `max-w-50` = 200px, что математически точно совпадает со старыми `max-w-[400px]`/`max-w-[200px]`.

## Ревью

Из 4 проверенных гипотез порог уверенности ≥80 прошла одна:

**1. [100] Немецкий перевод строки об деактивации образа обнулился (`msgstr ""`) при байт-идентичном `msgid` — данные потеряны**
- `packages/aurora/src/locales/de/messages.po:859` — `msgid "Deactivating this image will prevent it from being used to launch new instances. Existing instances will not be affected."` в базовом коммите имел полный перевод (`msgstr "Durch die Deaktivierung dieses Images kann es nicht mehr zum Starten neuer Instances verwendet werden. Bestehende Instances sind nicht betroffen."`), в head-коммите — `msgstr ""`.
- Проверено побайтово (md5) — сам `msgid` не изменился ни на символ между базой и head, то есть это не смена текста, а именно потеря перевода при регенерации каталога — вероятно, побочный эффект замены `<Trans>...multiline JSX...</Trans>` на `t\`...\`` внутри `<Message text={...}>` в `DeactivateImageModal.tsx`.
- Это единственный перевод во всём locale-диффе, который был обнулён (остальные изменения — новые строки, которым перевод по определению не положен). Подтверждено также живым комментарием бота Copilot прямо в этом PR.
- Итог: немецкоязычные пользователи при открытии модалки деактивации образа увидят непереведённый текст (fallback на английский) — детерминированный, не гипотетический эффект.

Отклонённые ниже 80 (не формальные issues, упомянуты в "Что затронуло" как реальные, но менее критичные наблюдения):
- [75] Регрессия truncation+tooltip в `SecurityGroupBasicInfo.tsx` — потеряна вёрстка `overflow-hidden text-ellipsis whitespace-nowrap` + `title`-тултип для Description/ID/Tags/Name/Owning Project ID, добавленная целенаправленно в PR #713 ("feat: add text ellipsis for long content in SecurityGroupBasicInfo"), а не случайно. Общий компонент `TwoColumnDescriptionList` и библиотечный `DescriptionDefinition` из `@cloudoperators/juno-ui-components` truncation/tooltip не поддерживают вообще — длинные описания/списки тегов будут переполнять или переноситься без возможности увидеть полное значение по наведению.
- [75] Отсутствие changeset для 20-файлового пользовательского UI-рефакторинга.
- [75] Неточность описания PR про "single column layouts" — на деле были 3-/4-колоночные `DataGrid`.

---
Проанализировано: 2026-07-29 · коммит `712e45e3f`
