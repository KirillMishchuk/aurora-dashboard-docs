# review-and-comment-pr — список доработок

Файл для записи улучшений скилла `review-and-comment-pr`.

---

## 1. Dependency-only PR запускают все finders впустую

**Дата:** 2026-10-29  
**Пример:** PR #1398

### Проблема

Когда PR меняет только lockfile/config/changeset (0 строк TypeScript кода), full mode всё равно запускает все 9 finders:
- find-diff-bugs
- find-standards
- find-code-comments
- find-history
- find-discussion
- find-security
- find-cross-boundary
- pr-description
- describer

Семь из них (все кроме `pr-description` и `describer`) ничего не находят, т.к. нет кода для анализа.

**Результат:** стоимость $5+ и 18 мин API time вместо возможных $1–2 и 5 мин.

### Предлагаемое решение

1. `collect.py` определяет dependency-only паттерн по списку файлов:
   - `*lock.yaml`, `pnpm-lock.yaml`, `package-lock.json`, `yarn.lock`
   - `package.json` (только если нет других `.ts`/`.tsx` файлов)
   - `.changeset/*.md`
   - `Cargo.lock`, `go.mod`, `go.sum`
   - `*.toml` (pyproject.toml, Cargo.toml)

2. Если все файлы попадают под паттерн → флаг `dependency_only: true` в `context.json`

3. `SKILL.md` Step 2 проверяет флаг:
   - Если `dependency_only: true` → пропускает code finders
   - Запускает только `pr-description` + `describer` (+ `find-api-contract` если `api_contract.needed`)

### Метрики для оценки

| Метрика | До | После (ожидаемо) |
|---------|----|----|
| Стоимость | $5.12 | ~$1–2 |
| API time | 18 мин | ~5 мин |
| Агентов | 10 (9 finders + factcheck) | 3–4 |

---

## 2. Стохастичность: find-discussion поднимает deferred паттерны как findings

**Дата:** 2026-10-30  
**Пример:** PR #1385, сравнение v3 и v4

### Проблема

При review PR #1385 (Networks BFF) прогон v3 поднял CR1/CR2 как Critical Security findings:
- "ID-based procedures don't verify network belongs to requested project"
- "listSubnets trusts client-supplied network_id without verifying ownership"

Прогон v4 того же PR эти findings **не поднял**.

### Расследование

1. **find-security** в обоих прогонах вернул 0 candidates — агент читал только первые 100 строк router, не дошёл до ID-based процедур

2. **find-discussion** в v3:
   - Прочитал Copilot comments из Routers PR #1355
   - Увидел что Copilot поднял cross-project access issue
   - Проверил код Networks PR — подтвердил тот же паттерн
   - Создал candidates C3, C4

3. **find-discussion** в v4:
   - Прочитал те же Copilot comments
   - Решил что "security groups comments not directly relevant to networks"
   - Не проверил код
   - Вернул 0 candidates

### Почему v4 правильнее

Проверка показала: **ни один роутер в проекте** не проверяет `project_id` после fetch:
- routersRouter.getById — нет проверки
- floatingIpRouter.getById — нет проверки  
- securityGroupRouter.getById — нет проверки
- imageRouter.getImageById — нет проверки
- и т.д.

Это **системный паттерн проекта**, а не баг конкретного PR. Copilot поднял это на Routers PR #1355, maintainer пометил как **deferred**. Networks PR просто следует существующему паттерну.

v3 ошибочно поднял deferred паттерн как Critical Security finding.
v4 правильно не поднял — но по неправильной причине (агент просто не проверил код).

### Вывод

Стохастичность агентов может работать в обе стороны:
- Иногда пропускают реальные баги
- Иногда поднимают ложные findings (deferred patterns, accepted conventions)

Brief не требует изменений — v4 дал правильный результат. Но это случайность, а не следование инструкции "deferred pattern is not a candidate".

---

## 3. find-security читает только начало файла

**Дата:** 2026-10-30  
**Пример:** PR #1385 v4

### Проблема

find-security агент прочитал только первые 100 строк `networksRouter.ts`:
```bash
git show 9ed42505:packages/aurora/src/server/Network/routers/networksRouter.ts | head -100
```

ID-based процедуры (`getById`, `update`, `delete`, `setTags`, `listSubnets`) начинаются со строки ~103 и дальше — агент их не видел.

### Влияние

В данном случае это не привело к пропуску реальных багов (cross-project access — это accepted pattern). Но при других обстоятельствах агент мог бы пропустить реальную уязвимость в процедурах после 100-й строки.

### Возможное решение

Добавить в brief для find-security:
```
For router files over 100 lines, read the full file or specifically check 
ALL mutation procedures (create, update, delete) and ALL ID-based read 
procedures (getById, get*ById) for security issues.
```

---

## 4. Solution Overview слишком длинный

**Дата:** 2026-10-30  
**Пример:** PR #1385 v4

### Наблюдение

Report содержит ~350 строк в секции "How it is implemented" с большими code snippets (по 30-50 строк каждый). Это делает report тяжёлым для чтения.

### Возможное решение

Ограничить code snippets в Solution Overview до 10-15 строк каждый, или вынести детальную документацию в отдельную секцию/файл.

Не критично — информация полезная, но verbose.

---

## 5. Противоречие между Verdict и Confidence to Merge

**Дата:** 2026-10-30  
**Пример:** PR #1385 v4

### Проблема

Report показывает:
- **Verdict:** 🔴 Request Changes
- **Confidence to Merge:** High

Это выглядит противоречиво для читателя: "нужны изменения" + "высокая уверенность в merge".

### Текущая логика

- **Confidence to Merge** — оценка качества кода и готовности к merge *после исправления findings*
- **Request Changes** — есть конкретные баги которые нужно исправить

То есть подразумевается: "код хороший, но есть 2 бага — исправь и можно мержить".

### Почему это плохо

Читатель видит "High confidence" и думает что всё хорошо, но verdict красный. Метрики не согласованы между собой.

### Возможные решения

1. **Переименовать метрику** — "Confidence to Merge" → "Code Quality" или "Readiness After Fixes"

2. **Связать метрики логически** — если Verdict = Request Changes, то Confidence ≤ Medium

3. **Убрать Confidence** — оставить только Verdict, он достаточен

---

## 6. Стохастичность: разные прогоны пропускают разные findings

**Дата:** 2026-10-30  
**Пример:** PR #1385, сравнение v4 с предыдущими прогонами (document-pr 03:14, review-and-comment-pr 04:51)

### Проблема

v4 прогон нашёл 4 findings (CR1-CR3, I1), но **пропустил 6 реальных issues**, которые были найдены предыдущими прогонами того же PR:

| Пропущенный issue | Severity | Где был найден | Статус |
|-------------------|----------|----------------|--------|
| Descending sort null-MTU bug | 🟡 Moderate | CR3 в 04:51 | CONFIRMED |
| Status as plain text, not Badge | 🟡 Moderate | I1 в 03:14 | CONFIRMED |
| Action cell missing minWidth | 🟢 Low (B.15 CRITICAL) | I3 в 03:14 | CONFIRMED |
| Raw error.message as title | 🟢 Low | I4 в 03:14, I1 в 04:51 | CONFIRMED |
| Import order violations | ⚪ Trivial | I6/I7 в 03:14, I2 в 04:51 | CONFIRMED |
| README missing service keys | 🟢 Low | I8 в 03:14, I3 в 04:51 | CONFIRMED |

### Детали пропущенных багов

1. **Descending sort null-MTU** (`networkHelpers.ts:142`) — `sortNetworks` умножает результат `compareValues` на `direction`. Когда `direction=-1` (desc) и значение null, получаем `-1 * 1 = -1`, что ставит null ПЕРВЫМ, а не последним. JSDoc говорит "Missing values sort last" — нарушено для descending.

2. **Status as plain text** (`NetworkTableRow.tsx:49`, `NetworkDetailsView.tsx:77`) — `network.status` рендерится как plain text, B.1 требует Badge для status indicators.

3. **Action cell minWidth** (`NetworkTableRow.tsx:67`) — DataGridCell для actions без `style={{ minWidth }}`, B.15 помечен как CRITICAL.

4. **Raw error.message** (`NetworkSubnetsTable.tsx:35`) — `error?.message` используется как title, B.6 требует static controlled strings.

5. **Import order** (`networks/index.tsx:4`, `NetworksList.tsx:5`) — `zod` и `@trpc/client` после i18n imports, B.13 требует Group 1 перед i18n.

6. **README service keys** (`packages/aurora/README.md:183, :210`) — не документированы `networks`, `routers`, `compute`.

### Почему это произошло

Стохастичность агентов-finders:
- Каждый finder читает разные части кода в разных прогонах
- find-standards может проверить одни файлы, но пропустить другие
- Нет детерминированного покрытия — какие файлы/строки проверяются зависит от "настроения" модели

### Влияние

- **v4 опубликован** с 4 findings вместо потенциальных 10
- Один **Moderate bug** (descending sort) не был поднят
- Несколько **B.* rule violations** не были поднят

### Возможные решения

1. **Детерминированные checks** — для B.* правил можно использовать статический анализ (ESLint rules, grep patterns) вместо LLM

2. **Multi-pass review** — запускать finders несколько раз и объединять findings

3. **Checklist-driven review** — brief требует проверить конкретный checklist для каждого файла, а не "найти проблемы"

4. **Historical findings** — если предыдущий прогон нашёл issue, новый прогон должен явно проверить его статус (fixed/still exists)

---

## 8. Docs-only PR запускают code-focused finders впустую

**Дата:** 2026-10-30  
**Пример:** PR #1406

### Проблема

PR #1406 меняет только 4 markdown файла (BRD, spec, guardrails, AGENTS.md), но full mode запустил все finders включая:
- `find-history` — 57 Bash команд, искал git history по TypeScript файлам
- `find-code-comments` — 40+ Bash команд, искал code comments в `packages/aurora/src/**`
- `find-security` — искал security issues в документации

Эти агенты не нашли ничего релевантного (0 candidates), но потратили время и токены.

### Отличие от #1 (dependency-only)

В #1 описан паттерн для lockfile/config PR где нет кода вообще. Здесь PR содержит контент (markdown specs), но этот контент — документация, а не код. Code-focused finders всё равно бесполезны.

### Предлагаемое решение

1. `collect.py` определяет docs-only паттерн:
   - Все файлы — `.md`, `.mdx`, `.txt`, `.rst`
   - Или все файлы в `docs/`, `DOCS/`, `.github/` директориях
   - Или только `README.md`, `CHANGELOG.md`, `AGENTS.md`, `CLAUDE.md`

2. Если `docs_only: true` → пропускать:
   - `find-history` (или ограничить только history самих docs файлов)
   - `find-code-comments` 
   - `find-security` (или специализировать на docs security — secrets в примерах кода)
   - `find-cross-boundary`

3. Оставить:
   - `find-diff-bugs` — может найти ошибки в документации (неправильные ссылки, несуществующие пути)
   - `find-standards` — может найти нарушения formatting/naming conventions
   - `find-discussion` — проверяет Copilot/human comments
   - `pr-description`, `describer`

### Метрики для оценки

| Метрика | До | После (ожидаемо) |
|---------|----|----|
| Агентов-finders | 7 | 3-4 |
| Bash commands | 150+ | ~50 |

---

## 9. Describer: невалидные `[[code:]]` плейсхолдеры вызывают retries

**Дата:** 2026-10-30  
**Пример:** PR #1406

### Проблема

Describer выдал `[[code:]]` плейсхолдеры с диапазонами строк которые render.py не смог расширить:
- `[[code:docs/specs/networks/networks-readonly-spec.md:14-20]]`
- `[[code:docs/specs/networks/networks-readonly-spec.md:234-238]]`

**Результат:** 5 циклов edit texts.json → assemble.py → render.py пока orchestrator вручную не заменил плейсхолдеры на inline текст.

### Причина

Describer не верифицирует что:
1. Указанные строки существуют в файле
2. Содержимое строк соответствует тому что он описывает
3. Диапазон не выходит за пределы файла

### Предлагаемое решение

1. **Brief для describer** — добавить инструкцию:
   ```
   Before using [[code:path:lines]], verify:
   - The file exists at the commit being reviewed
   - The line range is within the file's total lines
   - The content at those lines matches what you're describing
   
   If unsure, inline the relevant snippet directly instead of using a placeholder.
   ```

2. **Validation в save.py** — при сохранении describer output проверять все `[[code:]]` плейсхолдеры и выдавать warning если строки не существуют

3. **Fallback в render.py** — если `[[code:]]` не может быть расширен, выдавать более понятную ошибку с actual line count файла

---

## 10. Describer: несуществующие номера строк в qa.edge_cases

**Дата:** 2026-10-30  
**Пример:** PR #1406

### Проблема

Describer выдал qa.edge_cases с номерами строк которые не существуют:
```
"Verify the BRD's deferred items ... at lines 52, 369, 387"
```

BRD файл имеет только 364 строки — строки 369 и 387 не существуют.

Также:
```
"Open items roll-up section (lines 251–261)"
```
Секция начинается на строке 249, не 251.

### Влияние

- Factcheck потратил время на исправление этих ошибок
- Если бы factcheck пропустил, QA план был бы невыполним

### Предлагаемое решение

1. **Brief для describer** — при указании номеров строк в qa sections, верифицировать их через `git show <commit>:<file> | wc -l` или `sed -n '<line>p'`

2. **Validation в save.py** — парсить qa.edge_cases и проверять все упоминания "line(s) N" / "at line N" что они в пределах файла

---

## 7. `rerun` mode не проверяет findings предыдущих прогонов

**Дата:** 2026-10-30  
**Пример:** PR #1385 v4

### Проблема

В скилле есть агент `earlier-findings` который проверяет findings из существующего репорта на новом коммите. Но он запускается **только в режиме `update`**, не в `rerun`.

### Логика режимов (из `collect.py:decide_mode`)

| Режим | Условие | Агенты |
|-------|---------|--------|
| `full` | Нет репорта | Все finders |
| `update` | Есть репорт, head изменился | `earlier-findings` + finders на delta.diff |
| `rerun` | Есть репорт, head тот же, пользователь подтвердил | Все finders заново, **БЕЗ `earlier-findings`** |

### Что произошло в v4

```json
"mode": "rerun",
"mode_reason": "re-run of a current report, confirmed"
```

- Репорт от предыдущих прогонов уже существовал
- Head commit не изменился (9ed42505)
- Пользователь подтвердил rerun
- Режим стал `rerun` → `earlier-findings` не запустился
- Findings из 03:14 и 04:51 прогонов не были проверены

### Связь с #6

Это объясняет почему v4 пропустил 6 findings: режим `rerun` запускает finders с нуля, полагаясь на их стохастичную работу, вместо того чтобы явно проверить известные issues.

### Возможные решения

1. **Запускать `earlier-findings` и в `rerun`** — если есть предыдущий репорт с findings, проверить их статус независимо от режима

2. **Передавать findings в finders** — brief для finders включает список известных findings которые нужно проверить/подтвердить

3. **Union findings** — финальный репорт объединяет findings из нового прогона с confirmed findings из предыдущего

4. **Предупреждение пользователю** — при `rerun` показывать: "Предыдущий репорт содержит N findings которые не будут автоматически проверены"
