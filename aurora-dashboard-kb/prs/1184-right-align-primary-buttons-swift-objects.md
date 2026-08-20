# PR #1184: fix(portal): right-align primary buttons / fix button order (#1183)

**Автор:** mark-karnaukh-extern-sap · **Статус:** смержен 18.08.2026 (коммит `9cdf0ae`; создан 18.08.2026)
**Ветки:** `mark-right-align-primary-buttons` → `main` · **Файлов:** 2 (+9/-3)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1184

## Что сделано

Закрывает issue #1183 (AC: primary create-действие должно быть последней кнопкой, все primary-кнопки — выровнены по правому краю). В тулбаре Swift Objects (Zone 1) кнопки "Create Folder" (primary) и "Upload Object" стояли в порядке "Create Folder → Upload Object" — primary-кнопка была не последней. PR меняет порядок на "Upload Object → Create Folder", ничего больше не трогая: сам JSX, обработчики и структура `Stack` идентичны, поменялись только две соседние строки.

```tsx
// SwiftObjects/index.tsx:424-429 (после правки)
<Button className="whitespace-nowrap" onClick={() => setUploadModalOpen(true)}>
  <Trans>Upload Object</Trans>
</Button>
<Button variant="primary" className="whitespace-nowrap" onClick={() => setCreateFolderModalOpen(true)}>
  <Trans>Create Folder</Trans>
</Button>
```

Changeset `.changeset/open-maps-burn.md` (`patch`, `@cobaltcore-dev/aurora`) идёт в этом же PR — в отличие от #1181, здесь он был добавлен сразу, а не отдельным поздним коммитом.

## Что затронуло

Описание PR утверждает, что `SwiftContainers` уже удовлетворяет требованиям issue — проверено по коду (`Swift/Containers/index.tsx:295-311`): там всего одна кнопка ("Create Container", `variant="primary"`) в `Stack distribution="end"`, она тривиально последняя и правее всех. Утверждение верное.

Дальше issue сформулирован широко ("all primary buttons are right-aligned consistently across the layout"), хотя заголовок помечен `[Bug](Swift)`, так что стоило проверить, не остался ли где-то ещё в приложении тот же паттерн "primary-кнопка не последняя". Прошёлся по всем аналогичным тулбарам (Zone 1 "sort + create") в Compute/Network/Storage: `Flavors/List.tsx`, `Images/List.tsx`, `FloatingIpsList.tsx`, `SecurityGroupsList.tsx`, `Ceph/Buckets/index.tsx` — везде ровно одна primary-кнопка ("Create ...") в `Stack distribution="end"`, тривиально последняя и правая. Единственное другое место с *двумя* кнопками в одной зоне — Ceph-аналог того же экрана, `Ceph/Objects/ObjectBrowserView.tsx:644-659` — там порядок уже правильный: `Upload Object` первой, `Create Folder` (primary) последней. Похоже, именно с этого Ceph-паттерна и была скопирована Swift-версия, но при копировании порядок кнопок перепутали — этот PR просто приводит Swift к уже существующему в Ceph эталону. Пропущенных мест с той же проблемой не найдено.

## Ревью

Проблем с уверенностью ≥80 не найдено. Изменение минимальное и точное (две строки поменялись местами, никакой другой логики не тронуто), changeset на месте и соответствует масштабу (`patch`), сопоставление с Ceph-аналогом подтверждает и корректность, и полноту исправления. Существующие тесты (`index.test.tsx`) находят кнопки через `getByRole("button", { name: ... })` — они не зависят от DOM-порядка и не проверяют его; новый тест на сам порядок кнопок не добавлен, но это ниже порога (CLAUDE.md не требует тестов на визуальный порядок, а поведение кнопок не изменилось).

---
Проанализировано: 18.08.2026 · коммит `dd74644`
