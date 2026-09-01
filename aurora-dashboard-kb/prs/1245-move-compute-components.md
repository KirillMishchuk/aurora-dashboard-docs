# PR #1245: refactor(aurora): move compute components to their feature directories

**Автор:** andypf · **Статус:** open (не смержен; создан 01.09.2026)
**Ветки:** `andypf/refactor-compute-components-1244` → `main` · **Файлов:** 80 (+37/-810)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1245

> Closes #1244.

## Что сделано

Чисто структурный рефакторинг без изменения поведения: `Flavors`/`Images` компоненты переезжают из общей папки `compute/-components/` в подпапки самих feature-роутов — `compute/flavors/-components/` и `compute/images/-components/` соответственно (63 файла, git корректно распознал как rename с сохранением истории, similarity 98-100%). Мотивация — колокация: компоненты теперь лежат рядом с route-файлами, которые их используют (`flavors/index.tsx`, `flavors/$flavorId.tsx`, `images/index.tsx`, `images/$imageId.tsx`), а не в отдельном дереве на уровень выше. Заодно удалены три полностью неиспользуемые директории: `compute/-components/Instances/`, `compute/-components/KeyPairs/`, `compute/-components/ServerGroups/` (9 файлов, чистое удаление, не переезд) — см. "Ревью" на предмет того, был ли этот код действительно мёртв.

Остаются на месте (не Flavors/Images-специфичны): `compute/-components/ActivitySummary.tsx`, `compute/-components/Overview.tsx`.

## Как это реализовано

Move выполнен консистентно: все относительные импорты внутри переехавших файлов пересчитаны под новую глубину вложенности. Пример:

```tsx
// packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ImageListView.tsx
// было (на уровень глубже): "../../../-constants/filters"
import { IMAGE_STATUSES } from "../../-constants/filters"
```
Старый путь `compute/-components/Images/-components/ImageListView.tsx` был на 4 уровня ниже `compute/`, новый `compute/images/-components/ImageListView.tsx` — на 3; `../../../` → `../../` корректно указывает на тот же `compute/-constants/filters` в обоих случаях — проверено для всех файлов с непустым диффом (не только переименованных без изменений).

Route-файлы (`flavors/index.tsx`, `flavors/$flavorId.tsx`, `images/index.tsx`, `images/$imageId.tsx`) обновили импорты с абсолютных на пакета `../-components/Flavors/...`/`../-components/Images/...` на локальные `./-components/...` — тоже корректно, компоненты теперь буквально в их собственной `-components/` подпапке (соответствует конвенции CLAUDE.md: префикс `-` исключает папку из генерации роутов).

## Что затронуло

Только внутреннее использование — ни один из переехавших/удалённых файлов не имеет потребителей за пределами `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/`. Проверено:
- Ни одной оставшейся ссылки на старые пути (`compute/-components/Flavors`, `compute/-components/Images`) в кодовой базе на головном коммите не осталось.
- `routeTree.gen.ts` в диффе не участвует — ожидаемо, поскольку сами пути роутов (`/compute/flavors`, `/compute/images/$imageId` и т.д.) не менялись, переехали только `-`-папки, исключённые из генерации роутов.
- Удалённые `Instances`/`KeyPairs`/`ServerGroups` уже были orphan code до этого PR: ни в базовом коммите (до PR), ни в текущем нет ни одного route-файла `compute/instances`/`compute/keypairs`/`compute/servergroups`, и ни один другой файл их `List.tsx`/`-components/*` не импортировал — эти три директории не использовались уже как минимум с PR #1222 (последний коммит, трогавший эти файлы, три недели назад), просто до сих пор не были удалены.
- Строки, убранные из `de`/`en` `messages.po` (по 57 в каждом: "CPU", "Fingerprint", "Group Name", "IPv4"/"IPv6", "Key Name", "Loading Instances...", "Members", "Policy", "Restart", "Server Name", "Type", "View Details" и т.д.) — все они принадлежали удалённым компонентам; для каждой проверено, что после PR ни один `t\`...\`\`/`<Trans>` с точно таким же исходным текстом нигде в кодовой базе больше не встречается, то есть `pnpm check-i18n` отработал корректно и не задел ничего, что всё ещё используется.

## Ревью

Проблем с уверенностью ≥80 не найдено. Отдельно проверены места, где подобный move обычно ломается:
- Арифметика относительных импортов (`../../../` → `../../` и т.п.) во всех файлах с непустым диффом — совпадает с новой глубиной вложенности.
- Полнота обновления импортов — ни одной оставшейся ссылки на старые пути `compute/-components/Flavors|Images` в репозитории не найдено.
- Действительная "мертвизна" удалённых `Instances`/`KeyPairs`/`ServerGroups` — подтверждена отсутствием потребителей и в базовом, и в головном коммите (не просто "PR удаляет то, что сам же и перестаёт использовать").
- i18n-каталоги — убранные строки не имеют оставшихся потребителей в коде.

---
Проанализировано: 01.09.2026 · коммит `26bd222e`
