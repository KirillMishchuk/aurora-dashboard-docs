# PR #1085: fix(core): move react dependent packages to peerDeps and resolve workspace sources in dev

**Автор:** taymoor89 (Taimoor Aslam) · **Статус:** смержен 24.07.2026 (`8b44234f`; создан 21.07.2026)
**Ветки:** `1084-move-dependencies` → `main` · **Файлов:** 11 (+180/-61)
**Ссылка:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1085

## Что сделано

PR реализует issue #1084 и решает две связанные проблемы монорепо-конфигурации:

**Дублирующийся React из-за неверной классификации зависимостей.** `packages/aurora/package.json` держал пакеты, использующие React-контекст/хуки (`@lingui/react`, `@tanstack/react-query`, `@tanstack/react-router`, `@headlessui/react`, `focus-trap-react`, `react-error-boundary`, `react-icons`, `@trpc/react-query`, `@tanstack/react-form`, `@tanstack/react-virtual`) в обычных `dependencies`. pnpm ставил им приватную копию внутри `node_modules` пакета `aurora`, из-за чего у потребителя (`apps/dashboard`) оказывалось два экземпляра React/контекстов одновременно — отсюда "Invalid hook call" и тихо отвалившиеся Provider'ы. PR переносит все такие пакеты в `peerDependencies` и явно объявляет их как прямые `dependencies` в `apps/dashboard/package.json` (то есть теперь хост-приложение обязано их поставлять само).

**Отсутствие hot-reload для серверных workspace-пакетов в dev-режиме.** `packages/policy-engine` и `packages/signal-openstack` — приватные, никогда не публикуются, — но имели поле `exports`, которое заставляло Node всегда резолвить их из собранного `dist/`, игнорируя tsconfig path mapping. PR убирает `exports` из обоих (оставляя `main`/`module`/`types` на верхнем уровне), добавляет `apps/dashboard/tsconfig.server.json` с path-алиасами на исходники этих пакетов и `packages/aurora/src/server`, и заменяет прежнюю команду `dev` (`tsx watch --env-file=.env src/server/server.ts`) на новый `apps/dashboard/scripts/dev.sh`, который явно ставит эти пути на `--include` для `tsx watch`. Заодно `apps/dashboard/turbo.json`'s `dev`-таск лишился `dependsOn: ["@cobaltcore-dev/aurora#build"]` — сборка перед dev больше не нужна, всё резолвится из исходников.

Добавлен `packages/aurora/docs/0014_dependency_classification.md` — документирует правило классификации (peer, если пакет держит React-контекст/hook-состояние или singleton-состояние; dependency — если чистая утилита или server-only) и грепы для проверки нового пакета на использование React. Плюс мелочь: `packages/aurora/eslint.config.mjs` добавил `src/locales/**` в игноры (сгенерированные Lingui-локали).

## Как это реализовано

**Смена классификации** — `packages/aurora/package.json:52-68`:
```json
"peerDependencies": {
  "@headlessui/react": "^2.0.0",
  "@lingui/core": "^5.0.0",
  ...
  "fastify": "^5.0.0",
  "focus-trap-react": "^12.0.0",
  "react": "^19.0.0",
  "react-dom": "^19.0.0",
  "react-error-boundary": "^6.0.0",
  "react-icons": "^5.0.0"
},
```
Симметрично в `apps/dashboard/package.json:21-33` эти же пакеты появляются как обычные (и в основном без каретки, зафиксированные точной версией) `dependencies`.

**Новый dev-скрипт** — `apps/dashboard/scripts/dev.sh:15-24`:
```sh
exec node_modules/.bin/tsx watch \
  --env-file=.env \
  --tsconfig tsconfig.server.json \
  --watch-kill-signal=SIGKILL \
  --include ../../packages/aurora/src/server \
  --include ../../packages/aurora/src/types \
  --include ../../packages/policy-engine/src \
  --include ../../packages/signal-openstack/src \
  --exclude '**/*.test.ts' \
  --exclude '**/dist/**' \
  src/server/server.ts
```
Причина именно shell-скрипта, а не строки в `package.json` — комментарий в файле объясняет, что Turbo коверкает многофлаговые команды при прогоне через свой таск-раннер. `--include` перечисляет ровно те директории, куда указывают новые path-алиасы `apps/dashboard/tsconfig.server.json:9-12` — оба файла согласованы между собой.

**Убранный `exports`** — `packages/policy-engine/package.json:11-17` и `packages/signal-openstack/package.json:9-15` теряют блок `exports` (маппинг на `dist/{cjs,esm,types}`), оставляя только `main`/`module`/`types` на верхнем уровне пакета — этого достаточно для резолва, поскольку оба пакета `"private": true` и никогда не публикуются.

## Что затронуло

Изменение затрагивает **только dev-workflow и метаданные пакетов** — рантайм-код и публичный API `AuroraApp`/tRPC-роутеров не тронуты. Проверка через `git grep` на головном коммите PR (`132d5fa356af4299ff9594247bf1f5a99cef7565`) на предмет других потребителей `policy-engine`/`signal-openstack`/переносимых React-пакетов вне изменённых файлов ничего постороннего не нашла — единственный потребитель `packages/aurora` и `apps/dashboard`, которые PR и обновляет согласованно.

Production-сборка (`vite build`, `tsup`) не меняется этим PR — она уже резолвит `packages/aurora/client` из исходников через алиас в `vite.config.mjs`, а сервер бандлит `policy-engine`/`signal-openstack` через `tsup` с `noExternal`, где резолв идёт по `main` независимо от `exports` (esbuild с `platform: "node"` использует `mainFields: ["main", "module"]`). Так что удаление `exports` не меняет поведение прод-сборки — эффект только в dev-режиме (`tsx watch`), для которого он и задуман.

Единственная точка, которую сборка потенциально не покрывает — если в будущем появится ещё один server-side workspace-пакет (`packages/config`, новый), про него придётся не забыть добавить и в `--include` `dev.sh`, и в `paths` `tsconfig.server.json`; сейчас это ручная синхронизация двух файлов, ничего не проверяет их рассинхронизацию автоматически, но на 11 файлах и 2 пакетах в PR это не проблема — просто не абсолютная защита от будущего дрейфа.

## Ревью

**Найдено (confidence ≥ 80):** проблем с такой уверенностью не найдено.

**Также замечено (confidence 50-79, подтверждено, но не набрало порога):**

1. **Комментарий про `--watch-kill-signal=SIGKILL` описывает несуществующее поведение.** (confidence 75)
   `apps/dashboard/scripts/dev.sh:17-18` объясняет: флаг "kills the old process immediately on restart... avoids 'address already in use' errors". На деле `--watch-kill-signal` — это флаг нативного `node --watch`, а не `tsx watch`; `tsx watch --help` (версия `4.21.0`, закреплённая в `package.json`) распознаёт только `--clear-screen, --exclude, --ignore, --include, --no-cache, --tsconfig`. `tsx` использует собственную логику рестарта: всегда шлёт `SIGTERM` и ждёт фиксированные 5 секунд перед `SIGKILL`, независимо от этого флага — он тихо игнорируется (нет ошибки CLI, поведение не меняется). Заявленная в комментарии цель (избежать "address already in use") этой строкой не достигается. Не влияет на работоспособность скрипта — просто мёртвая строка с вводящим в заблуждение комментарием.
   Файл: `apps/dashboard/scripts/dev.sh:17-18, 23`.

Дополнительно, ревью CodeRabbit на самом PR независимо отметило две мелкие неточности в `packages/aurora/docs/0014_dependency_classification.md` (пример с `useState` вместо `useContext`/`createContext` как признак "доступа к контексту"; и эвристика на `grep "Provider"`, которая ловит произвольный текст, а не конкретно React-импорты/хуки) — оба чисто про формулировки в новом doc-файле, не про поведение кода.

---
Проанализировано: 23.07.2026 · коммит `132d5fa356af4299ff9594247bf1f5a99cef7565`
