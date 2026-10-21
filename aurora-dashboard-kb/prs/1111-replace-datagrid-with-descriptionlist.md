---
type: pr-report
date: 2026-07-29
status: merged
pr: [1111]
author: vlad-schur-external-sap
branch: vlad-replace-datagrid-with-descriptionlist
---
# PR #1111: refactor(ui): replace data-grid with description-list

**Author:** vlad-schur-external-sap · **Status:** merged 2026-07-30 (`cf2e0ad0`)
**Branches:** `vlad-replace-datagrid-with-descriptionlist` → `main` · **Files:** 20 (+461/-658)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1111

## What was done

A broad UI refactoring: replacing the tabular `DataGrid`/`DataGridRow`/`DataGridCell`/`DataGridHeadCell` layout with the key/value `DescriptionList`/`DescriptionTerm`/`DescriptionDefinition` layout in the detail views and modals of Flavors, Images, Security Groups:

1. **Flavors** — `DeleteFlavorModal`, `EditSpecModal` (extra specs table), `SpecFormRow`, `SpecRow`, `FlavorDetailsView`.
2. **Images** — `ActivateImageModal`, `DeactivateImageModal`, `DeleteImageModal`, `EditImageMetadataModal`, `ImageDetailsView`.
3. **Security Groups** — `SecurityGroupBasicInfo` (was a 4-column `DataGrid`).
4. **Shared component**: `TwoColumnDescriptionList` (previously lived only in `network/floatingips/$floatingIpId/-components/`) was moved to a shared location `packages/aurora/src/client/components/TwoColumnDescriptionList.tsx`, and the `DetailListItem` type was extended (`label`/`value` now accept `ReactNode`, an optional `id` was added for React keys instead of `key={label}`):
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
5. As a side change: the unused barrel re-export of `RBACPolicyRow` from `securitygroups/.../-details/index.ts` was removed (verified — the only consumer imports directly from `./RBACPolicyRow`, so the re-export was dead), and an edit unrelated to the PR's topic was made in Swift `EmptyContainerModal.tsx` (`max-w-[400px]` → `max-w-100`, `max-w-[200px]` → `max-w-50`).

## How it is implemented

`EditSpecModal.tsx` adds a guard against double form submission (previously missing):
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
and passes this state to `SpecFormRow` as `isLoading={isSavingSpec}` (previously hardcoded as `isLoading={false}`) — the form is now correctly locked for the duration of the request.

`SecurityGroupBasicInfo.tsx` — before (a 4-column table with truncation):
```tsx
// base e04eed1:26-42
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
after:
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

## What it affects

- **An internal change to presentational components**, with no change to public props/API facing outward. `TwoColumnDescriptionList` is now used by 5 files (`DeleteFlavorModal`, `FlavorDetailsView`, `ImageDetailsView`, `FloatingIpDetailsView`, `SecurityGroupBasicInfo`) — verified that the broader `DetailListItem` type (accepting `ReactNode`/`number`/`undefined`) does not break the only previous consumer `FloatingIpDetailsView` (it passes only strings, compatible); changing the React key strategy from `key={label}` to `` key={id ?? `left-${index}`} `` is also safe for it (static list, never reordered).
- **Missing changeset**: the PR touches 20 user-facing UI files but adds no `.changeset/*.md` — this violates established practice (all comparable recent PRs added one: #1099, #1090, #1086, #1088, #952).
- **The PR description inaccurately** characterizes the original layout as "single column layouts" — in fact `EditSpecModal.tsx` (3-column `DataGrid`), `EditImageMetadataModal.tsx` (3-column) and `SecurityGroupBasicInfo.tsx` (4-column, `gridColumnTemplate="15% 35% 15% 35%"`) were already multi-column tables before this PR.
- **Two comments from automated GitHub bots (Copilot/CodeRabbit) on the PR itself turned out to be outdated** when checked against the current head commit:
  - CodeRabbit pointed out a "double-submit risk" due to the hardcoded `isLoading={false}` in `EditSpecModal.tsx` — the comment refers to an earlier commit in this PR's push history (`original_line: 222`); in the current head commit this is already fixed via `isSavingSpec` (see "How it is implemented" above).
  - Copilot pointed out that a `<p>` is rendered directly inside `<DescriptionList>` (`<dl>`) in `EditImageMetadataModal.tsx` — GitHub itself marked the comment as *outdated* (`line: None`, `original_line: 387`); in the current code `<p>` and `<DescriptionList>` are alternatives of a ternary operator, not nested.
  - Copilot's remark about `max-w-100` ("not a standard Tailwind utility") in `EmptyContainerModal.tsx` is probably also a false positive: the project uses Tailwind v4.1.7, where an arbitrary numeric value `N` for spacing utilities is translated to `calc(var(--spacing) * N)` (default `--spacing: 0.25rem`) — `max-w-100` = 400px, `max-w-50` = 200px, which mathematically matches the old `max-w-[400px]`/`max-w-[200px]` exactly.

## Review

Of the 4 hypotheses checked, one passed the confidence ≥80 threshold:

**1. [100] The German translation of the image deactivation string was blanked (`msgstr ""`) with a byte-identical `msgid` — data lost**
- `packages/aurora/src/locales/de/messages.po:859` — `msgid "Deactivating this image will prevent it from being used to launch new instances. Existing instances will not be affected."` had a full translation in the base commit (`msgstr "Durch die Deaktivierung dieses Images kann es nicht mehr zum Starten neuer Instances verwendet werden. Bestehende Instances sind nicht betroffen."`), and in the head commit — `msgstr ""`.
- Verified byte-for-byte (md5) — the `msgid` itself did not change by a single character between base and head, so this is not a text change but precisely a loss of translation when regenerating the catalog — probably a side effect of replacing `<Trans>...multiline JSX...</Trans>` with `` t`...` `` inside `<Message text={...}>` in `DeactivateImageModal.tsx`.
- This is the only translation in the entire locale diff that was blanked (the other changes are new strings, which by definition have no translation yet). Also confirmed by a live comment from the Copilot bot directly on this PR.
- Bottom line: German-speaking users opening the image deactivation modal will see untranslated text (fallback to English) — a deterministic, not hypothetical, effect.

Rejected below 80 (not formal issues; mentioned in "What it affects" as real but less critical observations):
- [75] Truncation+tooltip regression in `SecurityGroupBasicInfo.tsx` — the `overflow-hidden text-ellipsis whitespace-nowrap` layout + `title` tooltip for Description/ID/Tags/Name/Owning Project ID was lost; it had been added deliberately in PR #713 ("feat: add text ellipsis for long content in SecurityGroupBasicInfo"), not by accident. Neither the shared `TwoColumnDescriptionList` component nor the library `DescriptionDefinition` from `@cloudoperators/juno-ui-components` supports truncation/tooltips at all — long descriptions/tag lists will overflow or wrap with no way to see the full value on hover.
- [75] Missing changeset for a 20-file user-facing UI refactoring.
- [75] Inaccuracy in the PR description about "single column layouts" — in fact these were 3-/4-column `DataGrid`s.

---
Analyzed: 2026-07-29 · commit `712e45e3f`
