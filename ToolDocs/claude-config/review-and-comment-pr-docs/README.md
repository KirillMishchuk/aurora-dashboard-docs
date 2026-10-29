# review-and-comment-pr — README

Подробное описание Claude-скилла `review-and-comment-pr` для проекта aurora-dashboard: что он делает, как устроен, какие файлы читает и пишет, какие проверки выполняют скрипты и что делать, когда что-то пошло не так.

Лежит в `DOCS/ToolDocs/claude-config/review-and-comment-pr-docs/` — вне папки скилла: по спецификации Agent Skills в папке скилла только то, что нужно агенту в работе. Рядом — `SPEC.md` (англ.): контракты, инварианты и журнал решений; этот README — подробный пересказ на русском.

Главный источник поведения — `SKILL.md` (runbook, шаги 1–9) и скрипты в `scripts/`. Этот README их пересказывает и сводит вместе; при расхождении прав код. Имена файлов, функций, полей, команд и статусов даны так, как они написаны в коде.

## Оглавление

1. [Назначение и принципы](#1-назначение-и-принципы)
2. [Быстрый старт](#2-быстрый-старт)
3. [Карта файлов](#3-карта-файлов)
4. [Режимы `collect.py`](#4-режимы-collectpy)
5. [Флоу по шагам 1–9](#5-флоу-по-шагам-19)
6. [Агенты](#6-агенты)
7. [Скрипты](#7-скрипты)
8. [Папка прогона: форматы файлов](#8-папка-прогона-форматы-файлов)
9. [Скоринг и вердикт](#9-скоринг-и-вердикт)
10. [Отчёт, индекс и комментарий в PR](#10-отчёт-индекс-и-комментарий-в-pr)
11. [Update-режим подробно](#11-update-режим-подробно)
12. [Release-PR](#12-release-pr)
13. [Зависимости, окружение, установка](#13-зависимости-окружение-установка)
14. [Проверка изменений скилла](#14-проверка-изменений-скилла)
15. [Типичные ошибки и что делать](#15-типичные-ошибки-и-что-делать)
16. [Известные ограничения и открытые вопросы](#16-известные-ограничения-и-открытые-вопросы)

---

## 1. Назначение и принципы

**Что делает.** Ревьюит открытый PR aurora-dashboard (номер, URL или PR текущей ветки) и пишет один отчёт, который коллега или следующая сессия Claude может прочитать вместо самого PR: вердикт о мерже с находками, на которых он основан, затем контекст (что сделано, как это проверить). Отчёт сохраняется в базу знаний `DOCS/aurora-dashboard-kb/prs/<n>-<slug>.md` (плюс строка в индексе `prs/README.md`), а в PR публикуется как комментарий **только после явного «да» пользователя**. Ответ «нет» на шаге публикации — и в GitHub ничего не уходит, поэтому скилл годится и просто чтобы задокументировать PR в `DOCS`.

**Принципы** (из `SKILL.md` и истории решений):

- **Детерминизм.** Прогон — фиксированный конвейер. Скрипты делают всё, что не требует суждения: сбор PR, брифы агентов, проверку и сохранение их результатов, группировку и пакетирование кандидатов, сборку и рендер отчёта, индекс, Related-ссылки, нарезку комментария и проверку на утечки. Каждый скрипт печатает, что делать дальше.
- **Одна задача — один узкий агент.** Брифы одинаковы на каждом прогоне и намеренно узкие; два брифа никогда не сливаются в одного агента. Новая проверка — новый узкий агент, а не довесок к оркестратору или к агенту с другой задачей (в истории скилла такие попытки не сработали).
- **Оркестратор только запускает и формулирует.** Оркестратор (сессия, выполняющая `SKILL.md`; по `review-and-comment-pr-remote-setup.md` — Opus, «Sonnet does not hold the runbook well») запускает ровно тех агентов, которых перечислил скрипт, выносит суждение там, где шаг этого просит (Confidence, слияние похожих находок, принятие правок fact-check), и пишет формулировки отчёта (`texts.json`). Он не делает работу скриптов и агентов: не вызывает `gh pr view`/`gh pr checks`/`git fetch`, не читает код PR и файлы папки прогона, кроме указанных шагом. Всё, что попало в его контекст, перечитывается на каждом следующем ходе — это деньги.
- **Агенты — Sonnet.** Все три типа агентов (`pr-reviewer`, `external-api-checker`, `security-reviewer`) объявлены с `model: sonnet`.
- **Только чтение.** Ветка PR никогда не чекаутится, рабочее дерево и HEAD пользователя не трогаются, рефы не создаются (никаких `git fetch … <src>:<dst>`, `git update-ref`, веток): коммиты берутся по SHA, код читается через `git show <sha>:<path>`, `git grep -n '' <sha> -- <path>`, `git blame -s -L a,b <sha> -- <path>`.
- **Истина — код, а не описание PR.** Описание и сообщения коммитов могут приукрашивать; правда — diff и файлы на head-коммите.
- **Код в отчёте — из репозитория, не набран руками.** В текстах код цитируется только плейсхолдерами `[[code:…]]`, строки — `[[at:…]]` или полным `path:line`; `render.py` вставляет код дословно из `headRefOid` и проверяет каждую ссылку.
- **Без проверки нет находки.** Каждый кандидат проходит оценщика (scorer); в отчёт попадает только то, что набрало 50+.
- **Отчёт показывает только то, с чем надо что-то делать.** Пройденная проверка (CI, безопасность, changeset, API-контракт) находкой не становится.
- **Никаких коммитов и пушей.** Единственная внешняя запись — комментарий в анализируемом PR после подтверждения. `DOCS` и репозиторий скилл не коммитит.
- Текст отчёта — на английском, на каком бы языке ни спросил пользователь. Код, идентификаторы, пути — как есть.

---

## 2. Быстрый старт

```text
/review-and-comment-pr 1393
/review-and-comment-pr https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393
/review-and-comment-pr            # PR текущей ветки
```

Команды запускаются из корня репозитория aurora-dashboard; папка `DOCS` должна лежать рядом с репозиторием.

**Что скилл может спросить:**

| Когда | Вопрос (печатает `collect.py`, exit 3) | Флаг для перезапуска |
| --- | --- | --- |
| PR не ссылается ни на одно issue (и это не release-PR) | `This PR links no issue. Give an issue/epic number to grade acceptance criteria against, or say none.` | `--issue <N>` или `--no-issue` (без возможности спросить — `--no-issue`) |
| Отчёт уже актуален (тот же head, тот же статус) | `The report <file> is current (head …, status …). Stop, or re-run from scratch (overwrites the report)?` | `--rerun` только на явное «да»; иначе — стоп |
| Шаг 8, перед публикацией | сводка `prepare_comment.py` (аккаунт, вердикт, счётчики, разделы) и вопрос, публиковать ли | — |
| Шаг 9, после ответа про публикацию | отдельный `AskUserQuestion`: заносить ли находки в `DOCS/FOLLOW-UPS.md` (`None` / `All Required Changes` / `All findings` / другое) | — |

Если в терминале есть TTY и не передан `--no-input`, `collect.py` задаёт первые два вопроса прямо в терминале (для rerun принимаются ответы `y`, `yes`, `rerun`, `да`).

**Что получится:**

- отчёт `DOCS/aurora-dashboard-kb/prs/<n>-<slug>.md` (или Update-блок в существующем отчёте);
- строка в индексе `DOCS/aurora-dashboard-kb/prs/README.md` и обновлённые Related-ссылки (`DOCS/tools/update-related.py`);
- папка прогона `<main repo>/.claude/runs/review-and-comment-pr/<n>-<sha8>/` со всеми промежуточными файлами (`.claude` в репозитории git-ignored);
- по согласию — комментарий в PR (`gh pr comment … --body-file /tmp/pr-<n>-comment.md`);
- по согласию — записи в `DOCS/FOLLOW-UPS.md` (только те, что назвал пользователь).

Итоговое сообщение оркестратора (шаг 9): какой PR, путь к файлу, вердикт (рекомендация + Confidence), число Required Changes (с severity) и Improvements или «чисто», опубликован ли комментарий (с URL) или почему нет; агенты, упавшие дважды, использованные fallback'и, предупреждения `Index:`/`Related:`.

---

## 3. Карта файлов

Пути от корня репозитория aurora-dashboard.

| Путь | Что это |
| --- | --- |
| `.claude/skills/review-and-comment-pr/SKILL.md` | runbook для оркестратора: требования, жёсткие правила, шаги 1–9 |
| `.claude/skills/review-and-comment-pr/scripts/collect.py` | шаг 1: сбор PR, выбор режима, папка прогона |
| `.claude/skills/review-and-comment-pr/scripts/briefs.py` | брифы агентов: `find`, `score`, `factcheck` |
| `.claude/skills/review-and-comment-pr/scripts/save.py` | проверка и сохранение результата агента в `out/<name>.json` |
| `.claude/skills/review-and-comment-pr/scripts/quotes.py` | плейсхолдеры кода и ссылки на строки, проверка «внутренних имён», прецеденты, разбор строк прежнего отчёта; используется как модуль и как CLI |
| `.claude/skills/review-and-comment-pr/scripts/assemble.py` | `compose.md` (проход 1) и `findings.json` из `texts.json` (проход 2, `--texts`) |
| `.claude/skills/review-and-comment-pr/scripts/render.py` | валидация `findings.json`, раскладка, нумерация, вердикт, рендер отчёта/Update-блока, запись в `DOCS`, индекс, Related |
| `.claude/skills/review-and-comment-pr/scripts/prepare_comment.py` | нарезка комментария, проверка на утечки и Markdown, сводка для передачи пользователю |
| `.claude/skills/review-and-comment-pr/references/briefs/*.md` | шаблоны брифов: `_header`, `_candidates`, `_output`, `describer`, `describer-update`, `find-*` (8 шт.), `pr-description`, `earlier-findings`, `scorer`, `factcheck` |
| `.claude/skills/review-and-comment-pr/references/scoring.md` | правила оценки (читает каждый scorer) |
| `.claude/skills/review-and-comment-pr/references/findings-format.md` | форматы `texts.json` / `findings.json`, плейсхолдеры, правила текста (оркестратор читает на шаге 6) |
| `.claude/skills/review-and-comment-pr/references/report-format.md` | справка о шаблоне отчёта и строке индекса (реализовано в `render.py`) |
| `.claude/agents/pr-reviewer.md` | тип агента для describer, `find-standards`, `find-diff-bugs`, `find-history`, `find-discussion`, `find-code-comments`, `find-cross-boundary`, `pr-description`, `earlier-findings`, scorers, fact-check |
| `.claude/agents/external-api-checker.md` | тип агента для find-api-contract |
| `.claude/agents/security-reviewer.md` | тип агента для find-security |
| `.claude/hooks/check_report_md.py` | hook проверки Markdown (и модуль, который импортируют `render.py`, `prepare_comment.py`) |
| `.claude/settings.local.json` | разрешения, hooks, env |
| `.claude/runs/review-and-comment-pr/<n>-<sha8>/` | папки прогонов |
| `../DOCS/aurora-dashboard-kb/prs/` | отчёты и индекс `README.md` |
| `../DOCS/tools/update-related.py` | генератор блоков Related в заметках DOCS (запускает `render.py`) |
| `../DOCS/ToolDocs/claude-config/aurora-dashboard-config/.claude/` | бэкап конфига (`.claude/` в репозитории git-ignored, это единственная версионируемая копия) |
| `../DOCS/ToolDocs/claude-config/review-and-comment-pr-docs/` | этот README и `SPEC.md` (англ.) |
| `../DOCS/ToolDocs/claude-config/review-pr-regression/` | регрессионный набор (`run.py`, `fixtures/`, `golden/`) |
| `../DOCS/ToolDocs/claude-config/review-and-comment-pr-remote-setup.md` | установка на другой машине |
| `../DOCS/ToolDocs/claude-config/cost-audit/` | аудит стоимости прогона (`audit_session.py`, `PROMPT.md`, `README.md`, эталоны `baseline-1383*.txt`) |
| `../DOCS/ToolDocs/claude-config/review-run-remote/` | тестовый прогон и его разбор на другой машине: `sync_install.py` (обновление скилла, агентов, hook и `settings.local.json` из DOCS), `run_review.py` (запуск + сбор логов, папки прогона и изменений DOCS вне DOCS), `check_run.py` (механические проверки → `checks.md`), `README.md` (как разобрать прогон и найти ошибки агентов), `PROMPT.md`, `baselines/`, `analyses/` (разборы прогонов, приходят на основную машину через DOCS) |

---

## 4. Режимы `collect.py`

`collect.py` читает PR через `gh pr view --json …`, ищет существующий отчёт `DOCS/aurora-dashboard-kb/prs/<n>-*.md`, разбирает его (`parse_report`: `status:` во frontmatter, строка `**Status:**`, последняя строка `_Analyzed…` и SHA последнего проанализированного head из неё) и выбирает режим функцией `decide_mode`:

| Ситуация | Режим | Что дальше |
| --- | --- | --- |
| PR открыт, отчёта нет | `full` | шаги 4–9; отчёт пишется по пути `Report:` из сводки |
| PR смёржен/закрыт, отчёта нет | `none` | «nothing to document», стоп |
| PR смёржен/закрыт, отчёт уже говорит то же | `none` | стоп |
| PR смёржен/закрыт, в отчёте другой статус | `status` | `render.py --run …` обновляет статус, футер, Date в индексе и Related; без публикации |
| PR открыт, head тот же, статус изменился (draft ↔ ready) | `status` | `render.py --run …` обновляет статус и Date в индексе (футер не меняется — он правится только у закрытого/смёрженного PR) |
| PR открыт, head тот же, статус тот же | `current` → вопрос (exit 3) | `--rerun` → `rerun`; отказ → `none` |
| PR открыт, head сдвинулся | `update` | шаги 4–9 по delta, Update-блок в отчёт |
| PR открыт, head сдвинулся, но в delta нет ни одной строки автора (новые коммиты только сливают `main`; изменения base вычтены, сгенерированные файлы не входят) | `update` → `none` | `collect.nothing_new` после расчёта delta: «the commits since … change none of the PR's own lines …», стоп без агентов, отчёт не меняется. В `context.json` уже есть `pr.diff`, `delta.diff`, `fetch`, нет `issue`/`ci`/`discussion` |
| PR открыт, отчёт есть, но в футере нет проанализированного коммита | — (exit 1) | «check the report by hand» (у закрытого/смёрженного PR эта проверка не делается) |
| Несколько отчётов на один PR | — (exit 1) | «merge or remove the extra one first» |

Подробности:

- **`rerun`** — как `full`, файл перезаписывается. Старый отчёт оркестратор не читает: это привязывает новый анализ к старому и переносит его ошибки.
- **`status`** для закрытого/смёрженного PR дописывает к футеру ` · status updated <today>: merged|closed`, а если head сдвинулся после отчёта — ещё ``  · last head `<sha8>` not analyzed ``.
- **`update`** — новые коммиты. Существующий текст не переписывается (отчёты — исторические записи). Если старый head недостижим из нового (force-push), `report.delta = "whole-pr"` и агенты анализируют весь PR (оркестратор сообщает об этом пользователю). Если статус тоже изменился, `status_update` применяется вместе с Update-блоком.
- **Release-PR** — не отдельный режим, а флаг (`flags.release`): head-ветка `changeset-release/main`, автор `cobaltcore-bot`/`app/cobaltcore-bot` или тело упоминает `changesets/action`. Агенты не запускаются, см. §12.

**Exit codes `collect.py`:**

| Код | Значение | Что делает оркестратор |
| --- | --- | --- |
| 0 | готово | действует по строке `Mode:` |
| 1 | не удалось собрать (`gh` не залогинен, нет `DOCS`, fetch не прошёл, несколько отчётов, PR сдвинулся во время fetch) | передаёт сообщение и останавливается; при ошибке авторизации — «run `gh auth login`» |
| 2 | неверные аргументы | исправляет вызов |
| 3 | нужен ответ пользователя | задаёт напечатанный вопрос один раз и перезапускает с названным флагом |

CLI: `collect.py [<pr>] [--issue N | --no-issue] [--rerun] [--run-dir DIR] [--no-input]`. `--issue` и `--no-issue` взаимоисключающие. `--run-dir` переопределяет папку прогона (по умолчанию `<main repo>/.claude/runs/review-and-comment-pr/<number>-<sha8>/`, где main repo — корень основного checkout'а, а не worktree: вычисляется через `git rev-parse --git-common-dir`). Путь берётся как есть и записывается в `context.json` → `run_dir`; `render.py` читает оттуда `discussion.json` (ссылки на комментарии, «not taken up»), поэтому при переносе папки прогона `run_dir` надо поправить.

---

## 5. Флоу по шагам 1–9

Все команды — из корня репозитория; пути, которые печатают скрипты, абсолютные, и `<run folder>` в последующих командах пишется буквально.

### Шаг 1. Сбор контекста — код

```bash
python3 .claude/skills/review-and-comment-pr/scripts/collect.py <arg>
```

- **Вход:** номер/URL/ничего; GitHub (через `gh`), git, существующий отчёт в `DOCS`.
- **Делает:** читает PR, находит `DOCS` и отчёт, выбирает режим; в режимах `full`/`rerun`/`update` удаляет из папки прогона оставшиеся с прошлого прогона `findings.json` и `report.md`; сначала (быстро) разбирается с issue, чтобы вопрос стоил секунды, затем делает медленную часть: fetch head и base по SHA, полный список файлов, `pr.diff`, `delta.diff` (update), CI, changeset, обсуждение, `copilot-instructions.md`, Process-пункты, provenance.
- **Выход:** `context.json`, `pr-body.md`, `pr.diff`, `issue-<N>.md`, `discussion.json`, `copilot-instructions.md`, `delta.diff` (update). `context.json` пишется атомарно (через `.json.tmp` + `os.replace`). В режимах `status`/ `none` пишутся только `context.json` и `pr-body.md`.
- **Оркестратор** читает только печатную сводку (не JSON). Пример сводки (реконструирован по `context.json` прогона `1393-64c47a99`, строки сокращены):

```text
PR #1393 feat(aurora): add Key Manager (Barbican) in-core plugin — open · main ← feat/key-manager-plugin
Head 64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7 · base cd8e674e2504b9de06d72e09ea4177f8f758bd8c
48 files +4486/−3 · mergeable: MERGEABLE
Mode: update — head moved fd248f08 → 64c47a99
Report: …/DOCS/aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md (exists)
Delta: fd248f08…..64c47a99…
Release PR: no · find-api-contract: yes (5 files) · Base: main
find-api-contract files: packages/aurora/src/server/KeyManager/routers/index.ts, …
CI: 13 pass, 0 fail, 5 pending
Changeset: MISSING — published code changed
Issue: #1133 (bare, open)
Discussion: 3 comments, 1 reviews, 19 inline threads (22 by bots) · 1 own earlier report(s)
Generated files left out of pr.diff: 3
Process: missing-changeset
Provenance: read-only
Context: …/.claude/runs/review-and-comment-pr/1393-64c47a99/context.json
```

- **Ошибки:** см. exit codes в §4.

### Шаг 2. Действие по режиму — оркестратор

`full`/`rerun` → шаги 4–9; `status` → `render.py --run <run folder>`, без публикации, отчёт пользователю (шаг 9); `update` → шаги 4–6 по delta плюс агент `earlier-findings` (§11); `none` → сказать и остановиться. Release-PR → вместо шагов 4–5 лёгкое ревью самим оркестратором (§12). База не `main` — `render.py` выносит это в шапку отчёта, это не блокер.

### Шаг 3. Что лежит в папке прогона — справка

Агенты читают папку сами: `context.json`, `pr.diff` (без сгенерированных файлов), `pr-body.md`, `issue-<N>.md` (критерии приёмки), `discussion.json`, `copilot-instructions.md` (стандарты ревью на `<headRefOid>`). Корневой `CLAUDE.md` есть только на диске и может быть новее PR — расхождение с ним контекст, а не нарушение. Агентам передаётся только путь к папке (это делают брифы), содержимое в промпт не вставляется.

### Шаг 4. Describer и finders — код + агенты (Sonnet)

```bash
python3 .claude/skills/review-and-comment-pr/scripts/briefs.py --run <run folder> find
```

- **Выход скрипта:** `briefs/<name>.md` для describer, finders `find-*` (`find-api-contract` — только если `flags.api_contract.needed`; в старых `context.json` — `flags.finder_f`), `pr-description` (если описание PR не пустое; §6.9) и на update ещё `earlier`, и список: имя, subagent type, путь к брифу (плюс пометка, если файла агента нет). Устаревшие `out/<name>.json` этих агентов удаляются.
- **Оркестратор** запускает ровно этих агентов **одним сообщением, в foreground** (`run_in_background: false`), каждому промпт `Read your brief: <path>` и указанный subagent type. Так все результаты приходят одним ходом; фоновые агенты будят оркестратор по одному разу на агента, и каждый такой ход перечитывает весь контекст. Брифы не дополнять и не переписывать.
- **Агенты** сохраняют результат через `save.py` в `out/<name>.json` и отвечают одной строкой `saved …`.
- **Ошибки:** агент ответил иначе или файла нет → перезапустить этого одного агента один раз с тем же промптом; снова неудача → отметить в итоговом сообщении и в `provenance_extra`. Тип агента отмечен как отсутствующий → general Sonnet agent с тем же брифом и запись `<agent> fallback used` в `provenance_extra`.
- Release-PR и режимы без анализа: скрипт печатает `Release PR: no agents — …` / `Mode …: no agents.` и выходит с 0.

### Шаг 5. Review pass — код + scorers (Sonnet) + оркестратор

Методология — плагина `code-review` (`/code-review`), адаптированная под отчёт: без проверки «eligibility/already reviewed» и без публикации отсюда.

1. **Score.** `briefs.py --run <run folder> score` собирает кандидатов (finders `find-*` + невыполненные/частично выполненные критерии приёмки и stale callers describer'а), нумерует `C1…`, группирует стоящие в одном месте, пакует в батчи по 8 и пишет `candidates.json` и `briefs/score-<n>.md`. Оркестратор запускает scorers так же, как в шаге 4. Каждый scorer читает `references/scoring.md`, оценивает каждого кандидата своего батча и решает через `same_as`, одна ли это проблема. Нет кандидатов — скрипт пишет `candidates.json` с `{"candidates": [], "batches": 0}` и печатает `No candidates — nothing to score. The review is clean apart from Process items.`, переходим к 2.
2. **Compose.** `assemble.py --run <run folder>` оставляет кандидатов со score ≥ 50, не являющихся `same_as`-дубликатами (улики дубликата прикладываются), сортирует, помечает похожие пары и пишет `compose.md`. Оркестратор читает его инструментом Read (не `cat`: длинный вывод обрезается).
3. **Verdict.** Рекомендацию выводит `render.py` (§9). Оркестратор выбирает только **Confidence to Merge** (`High`/`Medium`/`Low`): насколько он уверен, что PR здоров после устранения Required Changes; снижать за всё, что не удалось проверить (CI не прочитан, приёмку нельзя проверить, fallback security-reviewer). Draft не учитывается: его и так нельзя влить. Update тоже получает вердикт с учётом незакрытых прежних находок.

Сборки оркестратор сам не запускает: упавший или отсутствующий CI на `<headRefOid>` так и отражается, без находок, выведенных из ошибок сборки.

### Шаг 6. `texts.json`, рендер, fact-check — оркестратор + код + агент

1. Оркестратор читает `references/findings-format.md` и по `compose.md` пишет `<run folder>/texts.json` — **только формулировки** (score, severity, category, location, overview и QA-план — от агентов):
   - `summary` (2–4 предложения: общий вид, одна-две главные вещи, что закрывает вопрос; оценка приёмки — без issue «not verified», никогда не «pass»; непрочитанный CI, fallback агента, непрошедшая проверка);
   - `confidence`, `index_affected`;
   - по каждой находке `issue`, `title`, `explanation`, `fix` (в explanation: что не так, где, к чему ведёт; если поднималось в обсуждении — кто, где, что было; отсутствие теста на найденный баг — сюда, а не отдельной находкой; прецедент не повторять — его показывает `render.py`);
   - `edge_cases` — сценарий за каждой находкой категории Bug;
   - `merge` — похожая пара из `compose.md`, которая на деле одна проблема;
   - `process` — редко нужен: расхождения описания PR с кодом приходят от агента `pr-description` (в `compose.md`, переформулировать — только через `process_overrides.desc-<n>`), unlinked issue и missing changeset — из `collect.py`; draft — никогда не пункт;
   - на update вместо `summary`/`index_affected`/`edge_cases` — `earlier` (шаблон уже заполнен агентом `earlier-findings`) и `confidence`. Старый отчёт и `report-format.md` не открываются — макет, шапка, футер и индекс в коде.
2. Рендер:

   ```bash
   python3 .claude/skills/review-and-comment-pr/scripts/assemble.py --run <run folder> --texts && \
   python3 .claude/skills/review-and-comment-pr/scripts/render.py --run <run folder>
   ```

   Exit 1 любого из них перечисляет все проблемы по полям — исправить в `texts.json` (текст находки — напрямую; текст describer'а или location — записью в `fixes`) и запустить оба снова. Пока они не прошли, в `DOCS` ничего не попадает. При успехе `render.py` пишет отчёт в `DOCS`, добавляет/заменяет строку индекса и обновляет Related; черновик для fact-check — `<run folder>/report.md`.
3. Fact-check:

   ```bash
   python3 .claude/skills/review-and-comment-pr/scripts/briefs.py --run <run folder> factcheck
   ```

   Оркестратор запускает указанного агента в foreground. Тот проверяет описательные разделы (Solution Overview, QA Test Plan; на update — «What changed») против кода и сохраняет `out/factcheck.json`: каждое неверное утверждение с полем-источником, точной заменой `old` → `new` и уликами. Оркестратор читает этот файл, для каждой принятой записи копирует `field`, `old`, `new` в `fixes` в `texts.json` и снова запускает `assemble.py --texts` и `render.py` (на release-PR — правит `findings.json` и запускает `render.py`). Сам fact-check в отчёт не попадает.

### Шаг 7. Индекс и Related — код

Делает `render.py` на шаге 6. Если строка `Index:` говорит, что строка не обновлена, или `Related:` содержит предупреждение (например, дубликат pr-report), оркестратор передаёт это пользователю; индекс руками не правится, отчёты не удаляются и не сливаются.

### Шаг 8. Публикация — код + человек

```bash
python3 .claude/skills/review-and-comment-pr/scripts/prepare_comment.py <report path> <number> [--update]
```

- Нарезает комментарий в `/tmp/pr-<number>-comment.md`, сканирует на то, что нельзя публиковать, проверяет Markdown и печатает сводку (§10.6).
- **Любое срабатывание блокирует публикацию.** Оркестратор цитирует его пользователю с местом и даёт решить: отредактировать отчёт и перезапустить или опубликовать вручную. Молча вырезать и публиковать нельзя. Шаблоны ловят не всё — дополнительно глазами: реальные имена, идентификаторы клиентов/проектов, ссылки на приватные репозитории.
- Проблема Markdown → исправить там, где говорит шаг 6 (`texts.json`; на release-PR `findings.json`), перерендерить, перезапустить.
- **Hand-off обязателен, без обхода:** никакая постоянная инструкция «действуй автономно» этот шаг не покрывает. Оркестратор показывает сводку (вердикт, счётчики, разделы, `<owner>/<repo>` PR #`<number>`, аккаунт) и задаёт **только этот вопрос**. Публикация — только на явное «да» в ответ на него:

  ```bash
  gh pr comment <number> --repo <owner>/<repo> --body-file /tmp/pr-<number>-comment.md
  ```

  Всегда `--body-file`, никогда `--body` (shell портит обратные кавычки и `|`). Перед этой командой PreToolUse-hook `check_report_md.py` ещё раз проверяет Markdown файла и блокирует вызов при проблемах.
- **Ошибка публикации** (авторизация, «Resource not accessible…»): не повторять; сказать, что отчёт в `DOCS`, но не опубликован, и почему. Неудачная публикация не валит прогон — результат прогона это файл отчёта.

### Шаг 9. Отчёт пользователю — оркестратор

Кратко: PR, путь к файлу, вердикт + Confidence, счётчики (или «чисто»), опубликовано ли (URL) или почему нет; на `status` — что изменилось; на update — счётчики нового блока и что в нём «fixed». Плюс агенты, упавшие дважды, fallback'и, предупреждения `Index:`/`Related:`.

Затем, **после** ответа на вопрос о публикации, — отдельный `AskUserQuestion`: заносить ли находки в `DOCS/FOLLOW-UPS.md`. Варианты: `None`, `All Required Changes` (их номера в описании), `All findings`; другие — через «Other». На update предлагаются находки этого блока и прежние незакрытые. «Нет» на публикацию — не ответ на этот вопрос. В файл ничего не пишется, пока пользователь не сказал, что именно.

### Сводная таблица

| Шаг | Кто | Команда | Вход | Выход |
| --- | --- | --- | --- | --- |
| 1 | код | `collect.py <arg> [flags]` | GitHub, git, `DOCS` | `context.json`, `pr.diff`, `pr-body.md`, `issue-*.md`, `discussion.json`, `copilot-instructions.md`, `delta.diff` |
| 2 | оркестратор | (`render.py` на `status`) | сводка | решение |
| 4 | код + Sonnet | `briefs.py … find`; агенты → `save.py` | папка прогона | `briefs/*.md`, `out/describer.json`, `out/find-*.json`, `out/pr-description.json`, `out/earlier-findings.json` |
| 5.1 | код + Sonnet | `briefs.py … score`; scorers → `save.py` | `out/find-*.json`, `out/describer.json` | `candidates.json`, `briefs/score-*.md`, `out/score-*.json` |
| 5.2 | код | `assemble.py --run …` | `candidates.json`, `out/score-*.json`, `out/describer.json`, `out/pr-description.json`, `out/earlier-findings.json` | `compose.md` |
| 6 | оркестратор | Write `texts.json` | `compose.md`, `findings-format.md` | `texts.json` |
| 6 | код | `assemble.py --texts && render.py` | `texts.json` + всё выше | `findings.json`, `report.md`, отчёт в `DOCS`, индекс, Related |
| 6 | код + Sonnet | `briefs.py … factcheck`; агент → `save.py` | `report.md`, `findings.json` | `out/factcheck.json` → `fixes` → повтор рендера |
| 8 | код + человек | `prepare_comment.py …`; `gh pr comment … --body-file …` | отчёт | `/tmp/pr-<n>-comment.md`, комментарий в PR |
| 9 | оркестратор | `AskUserQuestion` | — | (по согласию) `DOCS/FOLLOW-UPS.md` |

---

## 6. Агенты

### 6.1 Типы агентов (`.claude/agents/`)

| Тип | Модель | Инструменты | Кто им работает |
| --- | --- | --- | --- |
| `pr-reviewer` | `sonnet` | Read, Bash, Grep, WebFetch, ToolSearch | describer, `find-standards`, `find-diff-bugs`, `find-history`, `find-discussion`, `find-code-comments`, `find-cross-boundary`, `pr-description`, `earlier-findings`, все scorers, fact-check |
| `external-api-checker` | `sonnet` | Read, Bash, Grep, WebFetch, ToolSearch | find-api-contract |
| `security-reviewer` | `sonnet` | Read, Bash, LSP, Grep | find-security |

`pr-reviewer` и `external-api-checker` сами несут правила «только чтение» и «читать код на коммите, не с диска» (`git grep -n '' <sha> -- <path>`, `git blame -s -L <from>,<to> <sha> -- <path>`, `git grep -n -A4 '<pattern>' <sha> -- <path>` — опции до паттерна и SHA; `git show <sha>:<path>` с путём от корня, без `./`/`../`; никогда не `cd`). Единственная разрешённая запись — команда `save.py` из брифа; временные файлы — только в `/tmp`. `security-reviewer` этих правил не несёт, поэтому `briefs.py` вставляет в бриф find-security два правила из `SKILL.md` дословно (функция `hard_rules()`; если она не находит их в `SKILL.md`, `briefs.py` падает с exit 1).

**Fallback.** `briefs.py` проверяет наличие `.claude/agents/<type>.md`; если файла нет, к строке агента добавляется `(agent missing — use a general Sonnet agent; add '<type> fallback used' to provenance_extra)`. Оркестратор запускает general Sonnet agent с тем же брифом и пишет запись в `provenance_extra` (она попадёт в футер отчёта).

### 6.2 Общая часть брифов

Каждый бриф собирается из шаблонов `references/briefs/` подстановкой `{{переменных}}` (неизвестная переменная — ошибка `unknown template variables`):

- `_header.md` — заголовок `# <role> — review-and-comment-pr, aurora-dashboard PR #<n>`, путь к папке прогона и её файлы (с `issue-<N>.md`, если есть), `headRefOid`, `baseRefOid`, на update — блок «Scope: this is an Update» (только `delta.diff` либо весь PR при force-push), напоминание читать код на `headRefOid`, а не с диска.
- `_candidates.md` — форма результата finder'а (см. §8.6) и правила: finders сообщают, а не судят (нарушение остаётся нарушением, даже если соседний код делает так же или мейнтейнер это принял — это `precedent`); кандидат по правилу стандарта (`B.<n>` или Quick Reject) обязан указать `example: <path:line>` — смёрженный код вне файлов PR, который правило соблюдает, или `example: none` (и тогда это прецедент); пройденные проверки не кандидаты; нет кандидатов — `{"candidates": []}`.
- `_output.md` — как сохранить результат: `save.py --run <run> --as <name> <<'JSON' … JSON`; при ошибках исправить и повторить; ответить только строкой, которую напечатал `save.py`.

### 6.3 Describer (`describer.md`, `pr-reviewer`)

Описывает изменение, не ревьюит. Группирует файлы по сути (серверные роутеры, клиентские маршруты/компоненты, общие пакеты, config/CI, docs) и пишет «что и как» по группам; на каждый существенный кусок — короткий фрагмент (3–15 строк) плейсхолдером и объяснение, зачем он. CI с упавшими/висящими джобами — кратко в `what` (и указать, если описание PR утверждает обратное). **Blast radius:** для каждого изменённого export, ключа tRPC-процедуры, экспортируемого компонента/хука, публичного типа — поиск потребителей вне файлов PR по всему монорепо на head (`git grep -n '<symbol>' <head> -- . ':!pnpm-lock.yaml' ':!**/CHANGELOG.md' ':!**/locales/**'`, включая `packages/aurora/README.md` и `apps/dashboard/src/policies/*.json`). **QA-план:** Core Path (нумерованный happy path) и Edge Cases (со ссылкой `file:line` на ветку кода). **Acceptance:** по каждому критерию из `issue-<N>.md` — `met` / `partly met` / `unmet` / `out of scope` с уликой `file:line`; `out of scope` — только если описание PR явно ограничивает PR частью issue (цитата ограничивающей строки в `evidence`); без issue — `"acceptance": []`. **Scope:** одна короткая строка вида `#816 — Phase 1, read-only`, если описание/issue ограничивает PR частью эпика; иначе `null`. Результат: `overview{what,how,affects}`, `qa{core_path,edge_cases}`, `acceptance[]`, `stale_callers[]`, `scope`.

### 6.4 Describer на update (`describer-update.md`)

Получает список находок существующего отчёта (`{{earlier_list}}`). Раскладывает delta на две кучи: (a) выполняет прежнюю находку (тест: существовало бы это изменение, если бы находку не написали?) и (b) всё остальное. Пишет **только (b)**: `what` — одно предложение про сам update (диапазон коротких SHA, draft или нет, CI на head; конфликты слияния не упоминать), затем по абзацу на область (b); если (b) пусто — «Every other change carries out an earlier finding.» `how`/`affects` — только для (b), иначе `""`. `qa.core_path` и `qa.edge_cases` — пустые списки (на update QA-плана нет).

### 6.5 Finders

Имена ролей — с 28.10 (типы агентов в `.claude/agents/` не менялись). Раньше: `finder-a` → `find-standards`, `finder-b` → `find-diff-bugs`, `finder-c` → `find-history`, `finder-d` → `find-discussion`, `finder-e` → `find-code-comments`, `finder-f` → `find-api-contract`, `finder-g` → `find-security`, `finder-h` → `find-cross-boundary`, `description` → `pr-description`, `earlier` → `earlier-findings`; флаг `context.json` `finder_f` → `api_contract` (старый читается). В старых логах, папках прогонов и KB-заметках — прежние имена.

| Имя | Тип | Что ищет |
| --- | --- | --- |
| `find-standards` — conventions | `pr-reviewer` | Аудит против `copilot-instructions.md` (стандарты на head; его «What NOT to Review» действует) и корневого `CLAUDE.md` (только как руководство, расхождение — контекст). Сначала «Quick Reject Checklist», потом каждая строка «**Reject**» в Part B, по одному пункту против каждого изменённого файла (UI-строки тоже), затем применимые правила Part A. Помимо `candidates` возвращает `checklist`: по строке на пункт — `violated`/`not violated`. |
| `find-diff-bugs` — bug scan | `pr-reviewer` | Поверхностный проход по `pr.diff` за очевидными крупными багами, без ухода в посторонний контекст; в `claim` — конкретный сценарий отказа (вход/состояние → неверный результат). |
| `find-history` — history | `pr-reviewer` | `git log`/`git blame` по изменённым файлам: баги, понятные только в свете истории. |
| `find-discussion` — review discussion | `pr-reviewer` | Все комментарии, ревью и inline-треды `discussion.json` (свои прежние отчёты `own_report` пропускает): на head — учтено, всё ещё актуально или изначально неверно. В `discussion` — кто первым поднял и url. Подтверждение/оспаривание прежней находки этого скилла — не место, где она поднята. Бот-комментарий — зацепка для проверки, не улика. Прежние PR: не больше одного `gh pr list --state merged --search … --limit 5` и комментарии не больше двух похожих попаданий одним вызовом. |
| `find-code-comments` — comment compliance | `pr-reviewer` | Комментарии в коде изменённых файлов («keep in sync with…», «must be called before…») и соблюдает ли их изменение. |
| `find-api-contract` — external API contract | `external-api-checker` | Только если PR меняет серверный код: файлы под `packages/aurora/src/server/` или `packages/signal-openstack/`, кроме `*.test.ts` (`api_contract_files` в `collect.py`). Каждый изменённый вызов OpenStack (`service("<name>")…`) или Ceph RGW через S3-клиент и каждая Zod-схема ответа — против официальных референсов, дословно, никогда по памяти; цитата с URL в `evidence`. |
| `find-security` — security | `security-reviewer` | Diff по чек-листу безопасности: procedure builders и project/domain scoping, серверные `canUser`, Zod-валидация входа и ID в URL OpenStack, токены/секреты в логах и ответах, raw HTML injection, fail-closed UI. Чтение через `git show <head>:<path>`. |
| `find-cross-boundary` — bugs across the PR's boundary | `pr-reviewer` | Ведёт каждое изменение **за пределы diff** — в существующий код на head, которому оно передаёт управление или на который опирается (редиректы и навигация, вход/сессия, обработка ошибок, кэш и ключи запросов, URL-параметры, общие хелперы, серверные процедуры) — и ищет сбои на стыке: циклы, устаревшее состояние, двойные запросы, потерянные параметры. Помимо `candidates` возвращает `boundaries` (`change`, `receiver`). `save.py`: в `evidence` каждого кандидата и в каждом `receiver` — `path:line` вне файлов PR, существующий на head. Добавлен 28.10: find-diff-bugs по брифу не выходит за diff, и цикл 401 в #1377 нашёлся лишь в одном прогоне из двух. |

**external-api-checker** читает OpenStack-референсы как reStructuredText-исходники через `curl` с `https://raw.githubusercontent.com/openstack/<…>/api-ref/source` (`index.rst` → `.. include::` → `<file>.inc`, `parameters.yaml`), потому что отрендеренные страницы `docs.openstack.org/api-ref/…` слишком длинные для WebFetch. Таблица путей: network `neutron-lib/master/api-ref/source/v2`, compute `nova/master/api-ref/source`, image `glance/master/api-ref/source/v2`, identity `keystone/master/api-ref/source/v3`, dns `designate/master/api-ref/source`, object-store `swift/master/api-ref/source`. Ceph RGW/S3 — `docs.ceph.com/en/latest/radosgw/s3/` и AWS S3 API reference. Для каждого изменённого list-вызова обязательны четыре проверки: пагинация, scope/visibility (фильтры владения против policy по умолчанию), ключи сортировки/фильтров, `fields`. Недоступный референс — так и сказать, не заполнять пробел по памяти.

### 6.6 `earlier-findings` (`earlier-findings.md`, `pr-reviewer`, только update)

Для каждой находки существующего отчёта проверяет код на head (весь код, не только diff) и ответы на неё в обсуждении (`discussion.json`: комментарии, ревью, треды после отчёта, где она названа) и ставит статус:

| Статус | Значение |
| --- | --- |
| `fixed` | код больше не делает того, что описано в находке |
| `partly` | часть исправлена, часть осталась; note говорит, какая |
| `open` | всё ещё верно как написано |
| `dropped` | только для находки о конфликтах слияния (с `main` или другими PR), о том, что PR — draft (это ревью их больше не покрывает), или для находки, которую мейнтейнер (ревьюер, не автор PR и не бот) в обсуждении попросил сделать иначе — note «Reversed by <login> in <url>.»; для Improvement/Process — и если автор или мейнтейнер в обсуждении явно оставил её как есть с причиной (note «Kept as is by <login>: <причина> (<url>).»); обязательную находку (CR) слово автора не закрывает — `save.py` отказывает в `dropped` для CR без заметки о конфликтах/draft/«Reversed by»; note — «Merge conflicts are no longer part of this review; GitHub shows them.» или «Draft state is no longer part of this review; a draft can't be merged anyway.» |

Номера строк в списке — со старого head: код ищется по описанию. Process-пункты: changeset — по `context.json` (`changeset`), утверждения про описание — по `pr-body.md`. Результат: `{"earlier": {"CR1": {"status", "note", "evidence"}}}`; каждая находка списка ровно один раз; note — одна строка, другие прежние находки по номеру (`CR2`).

### 6.7 Scorers (`scorer.md`, `pr-reviewer`)

- `briefs.py score` нумерует кандидатов `C1…` (finders в порядке `FINDERS`, затем describer), **группирует** стоящих в одном месте и **пакует** в батчи по 8, не разрывая группу (группа больше 8 целиком уходит в свой батч).
- Одно место: одна и та же метка (`PR body`, `PR state`, `PR files`, `CI`); или один файл, где у обоих нет строки; или один файл и строки в пределах 3 (`NEAR_LINES`). Группы транзитивны (union-find).
- Бриф содержит: обязательное чтение `references/scoring.md`, два явно повторённых правила (Precedent-table, Evidence), раздел «Same place» со списком групп батча, на update — список прежних находок с правилом «кандидат, возражающий против выполнения прежней находки, — 0 с именем этой находки в reason; сделано плохо — оценивать как обычно; кандидат из обсуждения (`discussion`) про файл вне `delta.diff` — 0 «Outside this update's changes» (иначе `save.py` отказывает: оценка ≥ 50 для такого кандидата на update — ошибка), он попадёт в «not taken up»; исключение — если об этом явно просил ревьюер, не автор PR и не бот (цитата в `discussion`): тогда оценивать как обычно и назвать в reason прежнюю находку, которую это отменяет», затем кандидатов с уликами **как их сообщили finders, без изменений**.
- Результат по каждому кандидату: `score` (0/25/50/75/100); для ≥50 — `severity`, `category`, `location` (существующая на head), `precedent` (обязателен для ≥50: `null`, `existing` — `ref` = `path:line` на base, строка, сама нарушающая то же правило; `deferred` — `ref` = URL комментария мейнтейнера; оба применимы → `deferred`); `reason` — 1–2 предложения для читателей PR (может быть опубликован); `same_as` — для кандидата в группе обязателен: id другого кандидата той же группы с той же проблемой (этот тогда отбрасывается) или `null`; вне группы — не указывать.

### 6.8 Fact-check (`factcheck.md`, `pr-reviewer`)

Читает `<run folder>/report.md` (на update — только новый блок) и проверяет **только описательные разделы**: три папки Solution Overview и QA Test Plan (на update — «What changed»). Каждое утверждение о поведении — против кода на head; каждое утверждение о потребителях — собственным `git grep`; каждое противопоставление описания PR и кода. Цитаты кода и ссылки на строки уже проверены скриптом. Возвращает только неверные утверждения: `{"wrong": [{"claim", "field", "old", "new", "evidence"}]}`, где `field` — поле-источник в `findings.json` (`overview.what|how|affects`, `qa.core_path[i]`, `qa.edge_cases[i]` с 0, `findings.<id>.issue|title|explanation|fix`), `old` — точный кусок текста этого поля (с плейсхолдерами как есть). Всё верно — `{"wrong": []}`.


### 6.9 `pr-description` — проверка описания PR (`pr-description.md`, `pr-reviewer`)

Одна задача: сверить, что описание PR (`pr-body.md`) говорит о PR, с кодом на head. Запускается в full/rerun/update, если описание не пустое. Два вида расхождений:

- `not in code` — описание обещает то, чего в коде нет или что сделано иначе (пример #1393: «add/remove secret refs» для контейнеров, а таких процедур нет). Каждое утверждение читается в пределах своего раздела: пункт под «BFF» — о сервере, под «UI» — о клиенте. Пример #1377: «Routers behaviour is unchanged except… pagination» стоит в разделе BFF и для сервера верна; изменения UI Routers описаны в своём разделе — это не расхождение (правило «X unchanged = расхождение, даже если описано в другом разделе» 28.10 дало ложный P3 в `1377-v4` и заменено). `quote` — дословная цитата из описания; `save.py` ищет её в `pr-body.md` (без учёта регистра, пробелов и Markdown-выделения) и отказывает, если не нашёл.
- `not described` — целая область, которую PR меняет, а описание не упоминает вообще (не отдельные файлы, тесты, переводы, форматирование). `location` — `path:line` изменения на head, проверяется.

Поля `issue` (одна строка, ≤ 120 символов), `explanation`, `fix` публикуются и проходят `public()`; `evidence` — только для проверки. На update: `not in code` — всё описание против кода на head; `not described` — только delta; расхождения, которые покрывают прежние находки (их список в брифе), не повторяются — их перепроверяет `earlier`.

Результат не оценивается scorers: `assemble.py` превращает каждое расхождение в Process-пункт `desc-<n>` (заголовок по виду: «The description claims what the code doesn't do» / «A change the description doesn't mention»), выкинуть его оркестратор не может, переформулировать — через `process_overrides.desc-<n>` (ключи `title`, `issue`, `location`, `explanation`, `fix`). Раньше эту сверку формально делал оркестратор (поле `process`), а фактически — никто.

---

## 7. Скрипты

Общее: все скрипты — Python 3.9+, без сторонних зависимостей; `briefs.py`, `save.py`, `assemble.py`, `render.py` ставят `sys.dont_write_bytecode = True` (нет `__pycache__` рядом со скриптами) и импортируют `quotes.py` из той же папки. `save.py`, `assemble.py`, `render.py`, `quotes.py` при exit 1 перечисляют **все** проблемы по полям — исправить и повторить. У `collect.py`, `briefs.py` и `prepare_comment.py` exit 1 означает «остановиться/спросить», а не «исправить и повторить».

### 7.1 `collect.py`

CLI и exit codes — §4. Ключевые функции:

| Функция | Что делает |
| --- | --- |
| `find_paths()` | корень worktree, корень основного checkout'а (`--git-common-dir`), `DOCS = <main root>/../DOCS`; нет `DOCS/aurora-dashboard-kb/prs` → exit 1 |
| `find_report()` | ищет `prs/<n>-*.md`; больше одного → exit 1 |
| `parse_report()` | статус во frontmatter и в `**Status:**`, последний футер `_Analyzed…`, старый head (последнее `` updated for `sha` `` или `` commit `sha` ``, кроме помеченных `not analyzed`/`previous version`) |
| `status_now()` | статус сейчас: `merged <date>` / `closed <date>` / `draft` / `open` и ячейка Date индекса (`<created> → merged <d>`, `<created> (open)` …) |
| `decide_mode()` | режим (§4) и `status_update` |
| `slugify()` | имя нового отчёта: убирает префикс `type(scope):`, скобки, стоп-слова (`add`, `and`, `the`, …), максимум 8 слов. Пример: `feat(aurora): add Key Manager (Barbican) in-core plugin` → `1393-key-manager-core-plugin.md` |
| `fetch_commit()` | коммит уже есть → `already local`; иначе `git fetch -q origin <oid>` → `fetched by SHA`; иначе `git fetch -q origin pull/<n>/head` и сверка `FETCH_HEAD` с ожидаемым SHA (иначе «the PR moved; re-run») |
| `changed_files()` | полный список файлов через `git diff --numstat --no-renames base...head` (у `gh` `files` ограничен 100); флаг `generated` |
| `delta_diff()` | `delta.diff` для update (§11.1) |
| `issue_candidates()` / `collect_issue()` | связанные issue: `closingIssuesReferences`, затем из тела PR (без HTML-комментариев и code-блоков) — `closes/fixes/resolves/part of #N`, URL `github.com/<repo>/issues/N`, `owner/repo#N`, голый `#N`; до 10 кандидатов резолвятся через `gh api repos/<repo>/issues/<n>`; PR среди них → `mentioned_prs`. Нет issue (и не release) → вопрос или `--issue`/`--no-issue`; issue, заданное пользователем в прошлый раз, переиспользуется из футера старого отчёта (`against #N supplied`) |
| `collect_ci()` | `gh pr checks <n> --json name,state,bucket,link,workflow`: счётчики `pass`/`fail`/`pending`/`skipping`/`cancel`, имена упавших (со ссылками) и висящих; ошибка чтения → `{"error": …}` и provenance `CI not read` |
| `collect_changeset()` | `.changeset/*.md` (кроме `README.md` и удалённых) в `base...head` и их bump'ы из frontmatter; `missing`, если PR трогает `packages/*/src/` и changeset'а нет |
| `collect_discussion()` | верхнеуровневые комментарии (`gh pr view --json comments`), ревью — через REST `gh api --paginate repos/<repo>/pulls/<n>/reviews` с `id` и `url` (`…#pullrequestreview-<id>`; не удалось — из `gh pr view --json reviews`, без них), inline-комментарии (`gh api --paginate repos/<repo>/pulls/<n>/comments`) деревом по `in_reply_to_id`; метка `bot` (`[bot]`, `copilot`, `github-actions`, `cobaltcore-bot`, `dependabot`, `renovate` или `user_type == "Bot"`); собственные отчёты (`## PR Review Report…` или `` ## Update — <date>, head `sha` ``) помечаются `own_report` и `own_kind` (`review`/`update`), их тело заменяется на `(earlier review-and-comment-pr report — omitted; see the url)`; ревью без тела в состоянии `COMMENTED` отбрасываются; в телах комментариев, ревью и inline-ответов цитируемые строки (`> …`) заменяются пометкой `[quoted N line(s) omitted]` (`strip_quotes`) — иначе ответ после «Quote reply» на наш отчёт тонет в цитате; inline не прочитались → `inline_read: false` и provenance `review threads not read` |

Сгенерированные файлы (`GENERATED`): `locales/<lang>/messages.ts|js` и `routeTree.gen.ts` — перечислены в `context.json` (`pr.generated_files_not_in_diff`), но исключены из `pr.diff`. Исходники каталогов (`.po`) остаются в diff: строки UI ревьюятся там.

Process-пункты, которые добавляет `collect.py` в `context.json` → `process`:

| id | Когда | where |
| --- | --- | --- |
| `no-linked-issue` | тело не ссылается на issue (не на release-PR) | `PR body` |
| `missing-changeset` | изменён код опубликованного пакета без `.changeset/*.md` (не на release-PR) | `PR files` |

### 7.2 `briefs.py`

```text
briefs.py --run <run-dir> find | score | factcheck
```

Exit: 0 — брифы записаны (или не нужны: release-PR/режимы без анализа, об этом сказано в stdout); 1 — сломан шаблон или контекст (а также `factcheck` без `report.md`/`findings.json`); 2 — usage.

- **`find`** — describer (на update — бриф `describer-update.md`), finders `find-*` (`find-api-contract` по флагу), `pr-description` (если описание PR не пустое), на update `earlier-findings`; пишет `briefs/<name>.md`, удаляет старые `out/<name>.json`, печатает `Launch these N agents in ONE message, in the foreground, …` и строки `<name> <subagent type> <path>`.
- **`score`** — `collect_candidates()`: кандидаты из `out/find-*.json` (с `source`), из `out/describer.json` — критерии `unmet`/`partly met` (`claim` = `Acceptance criterion <status>: <criterion>`, `location` — первая `` `path:line` `` из evidence или `PR files`) и `stale_callers` (`` Stale caller of `<symbol>`: <note> ``). Нумерация `C1…`; `location` вида `path | text` резолвится в `path:line`, короткое имя изменённого файла — в полный путь. Затем `group()`, батчи, `candidates.json`, `briefs/score-<n>.md`; старые `out/score-*.json` и `briefs/score-*.md` удаляются. Печатает `<N> candidates in <G> places. Launch these <B> scorers …` со списком id в каждом батче.
- **`factcheck`** — бриф `briefs/factcheck.md` над `<run>/report.md`; удаляет старый `out/factcheck.json`.
- `earlier_findings()` — строки прежних находок `- <n> <severity> — <issue> — <location>` из `quotes.earlier_rows()`.

### 7.3 `save.py`

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <run-dir> --as <name> <<'JSON'
{ … }
JSON
```

`<name>`: `describer`, `find-standards`, `find-diff-bugs`, `find-history`, `find-discussion`, `find-code-comments`, `find-api-contract`, `find-security`, `find-cross-boundary`, `pr-description`, `earlier-findings`, `score-<n>`, `factcheck`. Exit: 0 — сохранено в `out/<name>.json` и напечатано `saved out/<name>.json: <что>` (плюс `warnings`, если есть); 1 — невалидно (ошибки списком, ничего не записано; также «not valid JSON»); 2 — usage, неизвестное имя, нет `context.json`, `earlier` не на update.

Общие проверки:

- **Ключи:** неизвестный ключ — ошибка с перечнем допустимых.
- **Строки:** обязательные поля непустые; **сокращённый путь** (`…/` или `.../`) в любом текстовом поле — ошибка («write the full repo-relative path»).
- **Location** (`location()`): метка `PR body`/`PR state`/`PR files`/`CI`; или `path | text` (текст должен быть ровно на одной строке файла на head); или `path[:a[-b]]` — файл существует на head, строки в диапазоне. Короткое имя файла (`NetworksList.tsx`, `types/network.ts`) резолвится в единственный изменённый файл с таким окончанием.
- **`public()`** — для полей, которые могут попасть в публикуемый комментарий: `claim` кандидата, `reason` scorer'а, `note` агента `earlier-findings`. Ошибка, если вне code-блоков встречаются внутренние имена `quotes.INTERNAL` (см. §7.4).

По результату:

| Результат | Проверки |
| --- | --- |
| finder | `candidates` — список; у кандидата допустимы `claim`, `location`, `evidence`, `precedent`, `discussion`; `claim` + `public()`; `evidence`; `example()`; `precedent`/`discussion` — необязательные строки; location. У `find-cross-boundary` ещё обязательный список `boundaries` (`change`, `receiver` — `path:line` вне файлов PR, существующий на head), а в `evidence` каждого кандидата — хотя бы один такой `path:line`; кандидаты при пустом `boundaries` — ошибка. У `find-standards` ещё обязательный непустой `checklist` с `item`, `result` (`violated`/`not violated`), `where` |
| `example()` | если `evidence` или `claim` ссылаются на правило стандарта (`B.<n>` или `Quick Reject`), в `evidence` обязателен `example: <path:line>` или `example: none`; пример не может быть файлом этого PR, должен существовать на head или base, строка — в диапазоне |
| describer | ключи `overview`, `qa`, `acceptance`, `stale_callers`, `scope`; `overview.what` обязателен, `how`/`affects` обязательны кроме update; каждое поле overview проходит `quotes.resolve_text()` (плейсхолдеры, ручные code-блоки, внутренние имена, ссылки); `qa.core_path`/`qa.edge_cases` — непустые списки строк (на update допустимы `[]`), в них нельзя `[[code:…]]`; `acceptance[].status` ∈ `met`, `partly met`, `unmet`, `out of scope`; `scope` — одна строка ≤ 100 символов или `null`; `stale_callers[]` с `symbol`, `location` (проверяется), `note` |
| `score-<n>` | нужен `candidates.json`; каждый `id` из этого батча и ровно один раз; `score` ∈ {0,25,50,75,100}; при `same_as` пустые `score`/`reason` заполняются (`0`, `Same problem as <id>.`); `reason` + `public()`; кандидат в группе обязан иметь ключ `same_as` (`null` или другой id своей группы); цель `same_as` не может сама иметь `same_as` (цепочки и взаимные ссылки — ошибка); вне группы `same_as` не допускается; для score ≥ 50 без `same_as` — `severity` ∈ Critical/Major/Moderate/Low/Trivial, `category` ∈ Bug/Security/Accessibility/UI/UX/Code Quality/Performance/Docs/Test coverage, проверяемая `location`, обязательный ключ `precedent` (проверка `quotes.check_precedent`); все кандидаты батча оценены |
| `pr-description` | `{"mismatches": [...]}`; `kind` ∈ `not in code` / `not described`; `issue`/`explanation`/`fix` непустые и `public()`, `issue` — одна строка ≤ 120; `not in code` — `quote` дословно в `pr-body.md` (без учёта регистра, пробелов, `` ` `` `*` `_`), `location` пустой или `PR body`; `not described` — без `quote`, `location` — `path:line`, существующий на head |
| `earlier-findings` | только в режиме update; каждая прежняя находка (`quotes.earlier_rows`) ровно один раз, лишних нет; у каждой `status` ∈ `fixed`/`partly`/`open`/`dropped`, `note` (одна строка, `public()`), `evidence` |
| `factcheck` | нужен `findings.json`; `wrong` — список; у записи обязательны `claim`, `field`, `old`, `new`, `evidence`; `field` по шаблону `overview.(what\|how\|affects)`, `qa.(core_path\|edge_cases)[i]`, `findings.<id>.(issue\|title\|explanation\|fix)`; индекс в диапазоне; находка с таким id есть; `old` встречается в тексте поля ровно один раз |

### 7.4 `quotes.py`

Модуль, который используют `save.py`, `briefs.py`, `assemble.py`, `render.py`, и CLI.

**Плейсхолдеры** (`PLACEHOLDER = \[\[(code|at):(.+?)\]\](?!\])` — до первой `]]`, поэтому текст может содержать `]`, например `x["k"]`):

| Пишется | Превращается в |
| --- | --- |
| `[[code:<path>:<from>-<to>]]` (на отдельной строке) | эти строки на head как fenced-блок, с общим отступом срезанным, язык по расширению |
| `[[code:<path>:<line>]]` (на отдельной строке) | одна строка блоком |
| `[[code:<path> \| <text> \| <n>]]` (на отдельной строке) | `n` строк от единственной строки, содержащей `<text>` |
| `[[at:<path>:<line>]]` | `` `path:line` `` после проверки |
| `[[at:<path> \| <text>]]` | `` `path:N` ``, N — единственная строка с `<text>` |
| `location`: `<path> \| <text>` | `<path>:<line>` |
| `[[ref:<id>]]` (обрабатывает `render.py`) | номер находки `CR2`/`P1`/`I5` |

Правила и проверки `resolve_text()`:

- `[[code:…]]` должен стоять на отдельной строке и допустим только в `explanation`, `fix` и `overview` (не в `summary`, `issue`, `title`, QA).
- Текст `| <text>` должен встречаться ровно на одной строке файла; 0 совпадений — ошибка с тремя ближайшими строками (`difflib`), несколько — ошибка с номерами строк. Файл должен существовать на head; диапазон — в пределах файла; выдержка не длиннее 30 строк (`MAX_BLOCK`).
- **Ручные code-блоки** (`check_hand_blocks`) в тексте (кроме `fix` и блоков с языком `diff`, `text`, `console`, `sh`, `bash`, `shell`, `txt`) должны дословно (без учёта отступов и пустых строк; `...`/`…` как пропуск) находиться на head или base в изменённых файлах или в файлах, найденных `git grep -F` по первой строке. Первая строка `// <path>:<line>` (или `#`, `<!--`) — подпись: блок должен начинаться ровно с этой строки этого файла.
- **Ссылки** `` `path:line` `` / `` `path:a-b` `` вне code-блоков проверяются на head; файл, которого нет ни на head, ни на base, — только предупреждение (может быть файл другого PR); голое имя, не совпадающее с изменённым файлом, не проверяется.
- **Внутренние имена** (`INTERNAL`) вне code-блоков — ошибка: `headRefOid`, `baseRefOid`, `headRefName`, `baseRefName`, `context.json`, `discussion.json`, `candidates.json`, `findings.json`, `texts.json`, `describer.json`, `pr-body.md`, `compose.md`, `pr.diff`, `delta.diff`, `issue-<N>.md`, а также названия этапов этого ревью (`finder a`, `finders b and c`, имена ролей `find-*`, `pr-description`, `earlier-findings`, `scorer(s)`, `describer`, `fact-check(er)`). Вместо них — «the head commit», «the PR description», «the linked issue», «CI».
- Нераспознанный плейсхолдер (`[[code:`/`[[at:`, не закрытый на той же строке) — ошибка.

Другие функции: `resolve_findings()` (все поля `findings.json` разом; возвращает ошибки и предупреждения), `resolve_location()`, `check_precedent()` (прецедент: `null`; `{"kind": "existing", "ref": "<path:line>"}` — файл должен существовать на **base** и строка в диапазоне; `{"kind": "deferred", "ref": "<URL>"}` — URL вида `https://github.com/<owner>/<repo>/(pull|issues)/<n>…`), `earlier_rows()` (строки находок существующего отчёта, см. §11.3), класс `Repo` (чтение файлов на коммите через `git cat-file -p`, кеш, `resolve_name()`, `find()`, `grep_files()`).

CLI:

```text
quotes.py --run <run-dir> --report <file.md> [--update]   проверить готовый Markdown (с --update — только последний Update-блок);
                                                          всё после "<!-- related:auto" отбрасывается
quotes.py --run <run-dir> --describer                     out/describer.json -> <run-dir>/describer.md с разрешёнными плейсхолдерами
```

Exit: 0 — чисто (`Quotes and citations: OK`), 1 — проблемы, 2 — usage.

### 7.5 `assemble.py`

```text
assemble.py --run <run-dir>            -> compose.md
assemble.py --run <run-dir> --texts    texts.json -> findings.json
```

Exit: 0 — записано; 1 — нет входа (`no score for C… — a scorer didn't save (re-launch it)`, нет `texts.json`) или проблемы `texts.json` (списком); 2 — usage.

**Проход 1 (`compose`).** `kept()`: оценки ≥ 50 без `same_as`; кандидаты с `same_as` добавляются как дубликаты к корню цепочки (`root()`: идёт по `same_as`, пока у цели нет своего; цикл обрывается), если корень оставлен (их claim и evidence идут в `compose.md`). Сортировка — по severity (Critical → Trivial), затем по номеру C. `similar_pairs()`: пары одной категории с пересечением слов (Жаккар ≥ 0.3 без стоп-слов) или с общим идентификатором в обратных кавычках (≥ 4 символов) — раздел «Look alike — same problem?». `compose.md` содержит: инструкцию, похожие пары, по каждой находке заголовок `` `c<N>` — <severity> · <category> · `<location>` · score <n> `` (+ precedent), claim с источником, reason scorer'а, precedent и discussion finder'а, evidence, дубликаты, для Bug — напоминание добавить сценарий в `edge_cases`; список «Scored below 50 (not in the report)»; оценку приёмки (для summary); раздел «PR description vs code (Process items)» — пункты `desc-<n>` агента `pr-description` (или «None» / предупреждение, что результата нет); на update — раздел прежних находок со статусами агента `earlier-findings` (или предупреждение, что `out/earlier-findings.json` нет); в конце — шаблон `texts.json`. Id находок в `texts.json` — `c<N>` в нижнем регистре.

**Проход 2 (`build`).** Проверяет `texts.json`:

- допустимые ключи: `summary`, `confidence`, `index_affected`, `earlier`, `findings`, `edge_cases`, `merge`, `provenance_extra`, `overview`, `qa`, `process`, `process_overrides`, `fixes`, `scope`;
- `merge`: оба id — находки из `compose.md`, разные; у каждой не слитой находки непустые `issue`, `title`, `explanation`, `fix`; лишние id в `findings` — ошибка;
- update: `earlier` — непустой объект, `confidence` обязателен; не update: `summary`, `confidence`, `index_affected` обязательны, `earlier` запрещён;
- нет результата describer'а и нет `overview` в `texts.json` — ошибка («write overview and qa yourself»).

Затем собирает `findings.json`: из scorer'а — `id`, `score`, `severity`, `category`, `location`, `precedent`; тексты — из `texts.json`; `overview`/`qa` — describer'а, поверх — `texts.json`; `qa.edge_cases` = describer'а + `edge_cases` из `texts.json` (заготовка шаблона отбрасывается); применяет `fixes` (`apply_fix`: поле `overview.what|how|affects`, `qa.core_path[i]`, `qa.edge_cases[i]` или `findings.<id>.issue|title|explanation|fix|location`; `old` должен встретиться ровно один раз); `scope` — из `texts.json`, если ключ есть (`null` убирает), иначе describer'а; `process` — пункты `desc-<n>` агента `pr-description` (их `process_overrides` применяются здесь же и в `findings.json` не попадают; неизвестный ключ — ошибка), затем `process` из `texts.json`; на update — `earlier`; `dismissed` — все, чей корень (`root()`) не оставлен, по убыванию score: отсеянные кандидаты и их дубликаты; у дубликата `score` и `reason` — корня, `claim`, `location`, `discussion` — свои (`score`, `claim`, `location`, `reason`, `discussion`). Так ни один кандидат не пропадает без следа.

### 7.6 `render.py`

```text
render.py --run <run-dir> [--check | --dry-run]
```

- `--check` — только валидировать `findings.json`, ничего не писать;
- `--dry-run` — записать только `<run-dir>/report.md`, `DOCS` не трогать (печатает, чем закончится строка индекса или хвост Update).

Exit: 0 — записано; 1 — ошибки валидации или Markdown (списком; в `DOCS` ничего не записано), нет `findings.json`, режим не `full`/`rerun`/`update`/`status`; 2 — usage или нет `context.json`.

**Режим `status`** (`apply_status`): меняет `status:` во frontmatter и `**Status:**`, заменяет футер на `footer_new` (если футер изменился с момента `collect.py` — ошибка «re-run collect.py»), обновляет ячейку Date индекса, запускает Related. `findings.json` не нужен.

**Валидация** (`validate`), сверх `quotes.resolve_findings()`:

- Markdown каждого текстового поля через `check_report_md.check()` (`field_markdown_problems`), чтобы ошибка называла поле, а не строку `report.md`;
- `schema_version == 1`; известные ключи; `scope` — одна строка ≤ 100 символов (`SCOPE_MAX_CHARS`);
- update: `earlier` обязателен, у каждой прежней находки есть запись, лишних нет, каждая — ровно `{"status", "note"}`, `status` ∈ `fixed`/`partly`/`open`/`dropped`, note — одна строка без `[[code:`/`[[at:`; не update: `summary` обязателен, `earlier` запрещён;
- `confidence` ∈ High/Medium/Low;
- каждая находка: `score` ∈ {50,75,100} (ниже 50 — «leave the issue out»), `severity`, `category` (`Process` — «go to `process`»), `issue` одной строкой (> 120 символов — предупреждение), `title` одной строкой, `location` одной строкой — `path:line` от корня (не `/`, `./`, `../`), файл существует, строки в диапазоне, у каталога нет строк; `explanation`, `fix`; `precedent`;
- `process[]` — те же поля без score; `process_overrides` — только id из `context.json` и ключи `title`, `issue`, `location`, `explanation`, `fix`;
- `overview.what` обязателен; `how`/`affects` обязательны кроме release/update; `qa.core_path` обязателен кроме release/update; `qa.edge_cases` обязателен кроме update;
- `index_affected` обязателен кроме update, одна строка, не больше 45 слов (`AFFECTED_MAX_WORDS`; в сообщении — «about 40»), без слова `Verdict`;
- `id` находок — `[a-z0-9-]+`, уникальны (вместе с id Process-пунктов из `context.json`, кроме update);
- `[[ref:<id>]]` указывает на существующую находку или Process-пункт; на update Process-пункты из `context.json` не адресуемы, прежние находки — номером текстом;
- **жёсткие номера** `CR\d`, `P\d`, `I\d` вне кода — ошибка («give the finding an `id` and write `[[ref:<id>]]`»; если это не номер находки, например приоритет эпика, — в обратные кавычки); не проверяется в `overview.*`; на update допустимы номера прежних находок;
- сокращённые пути — ошибка;
- в ошибках `findings[3]` переписывается в `findings.<id>` — ключ, который правится в `texts.json`.

**Раскладка** (`layout`) и вердикт — §9; **рендер** отчёта и Update-блока — §10 и §11; запись:

- full/rerun: отчёт в `report.path` (перезапись), строка индекса (`upsert_index`), Related (`run_related`);
- update: `insert_update` — блок вставляется перед футером (`\n---\n\n_Analyzed`), прежний блок для того же head удаляется (`strip_update`), футер заменяется на `footer_new` (если ещё не содержит `` updated for `<sha>` ``), применяется `status_update`, в индексе — Date (если статус менялся) и хвост Update.

`run_related()` запускает `DOCS/tools/update-related.py` (если его нет — «skipped (say so when reporting back)»), из вывода берёт строки с `duplicate|warn|error`.

Пример вывода в full-режиме (формат по коду): `Report: …`, `Draft (for the fact-check): …/report.md`, `Verdict: 🔴 Request Changes · Confidence Medium`, `Findings: N Required Changes 🟠🟡…, P Process, M Improvements`, `Markdown: OK` (или `check skipped (hook not installed)`), `Warnings: …`, `Index: row inserted|replaced — Verdict: …`, `Related: ok`.

### 7.7 `prepare_comment.py`

```text
prepare_comment.py <report.md> <pr-number> [--update]
```

Exit: 0 — чисто; 1 — срабатывания сканера или проблемы Markdown; 2 — usage или ошибка нарезки (нет `## PR Review Report` / нет `## Update — …`). Детали нарезки, сканера и `fit()` — §10.6.

### 7.8 `check_report_md.py` (hook и модуль)

- **PostToolUse (Write/Edit; скрипт понимает и MultiEdit, но matcher в `settings.local.json` — `"Write|Edit"`):** проверяет отчёт, записанный в `DOCS/aurora-dashboard-kb/prs/*.md` (кроме `README.md`).
- **PreToolUse (Bash):** для `gh pr comment … --body-file <file>` проверяет файл и **блокирует** публикацию при проблемах.
- Проблема → exit 2 и текст в stderr (Claude его видит); любая ошибка самого скрипта → exit 0.
- Проверки `check(path)` (вне fenced-блоков): сокращённый путь в code span (`` `.../x` ``, `` `…/x` ``); экранированная обратная кавычка `` \` `` вне кода; незакрытый code span; raw HTML вне кода, кроме `details`, `summary`, `strong`, `br`, `sub`, `sup`; баланс `<details>`/`</details>`; незакрытый fenced-блок в конце файла.
- Подсказка в сообщении: inline-код, содержащий обратную кавычку, — более длинной оградой с пробелами (`` t`Try Again` ``) или fenced-блоком, никогда `` \` ``; HTML-подобный текст — в обратные кавычки; пути полностью.

---

## 8. Папка прогона: форматы файлов

Папка: `<main repo>/.claude/runs/review-and-comment-pr/<n>-<sha8>/` (sha8 — первые 8 символов head). Повторный прогон на том же head использует ту же папку; Update на новом head — новую папку.

### 8.1 Сводка файлов

| Файл | Пишет | Читает | Содержимое |
| --- | --- | --- | --- |
| `context.json` | `collect.py` | все скрипты, агенты | метаданные PR, режим, флаги, отчёт, CI, changeset, issue, обсуждение (сводка), Process, provenance |
| `pr-body.md` | `collect.py` | агенты | тело PR как есть |
| `pr.diff` | `collect.py` | агенты | `git diff base...head -- .` без сгенерированных файлов |
| `delta.diff` | `collect.py` (update, старый head достижим) | агенты | изменения PR между старым и новым head, только по файлам PR, без изменений, пришедших из base (§11.1) |
| `issue-<N>.md` | `collect.py` | describer, finders | `# #N: <title>`, `State: … · <url>`, тело issue |
| `discussion.json` | `collect.py` | find-discussion, `render.py` (ссылки, «not taken up») | комментарии, ревью, inline-треды |
| `copilot-instructions.md` | `collect.py` | find-standards, scorers | `.github/copilot-instructions.md` на head (если есть) |
| `briefs/<name>.md` | `briefs.py` | агенты | брифы `describer`, `find-*`, `pr-description`, `earlier-findings`, `score-<n>`, `factcheck` |
| `out/<name>.json` | `save.py` (по команде агента) | `briefs.py`, `assemble.py`, оркестратор (только `factcheck.json`) | результаты агентов |
| `candidates.json` | `briefs.py score` | `save.py` (scorer), `assemble.py` | кандидаты с id, группой, батчем |
| `compose.md` | `assemble.py` | оркестратор (Read) | материал для формулировок и шаблон `texts.json` |
| `texts.json` | оркестратор | `assemble.py --texts` | формулировки |
| `findings.json` | `assemble.py --texts` (на release-PR — оркестратор) | `render.py`, `save.py` (factcheck) | всё для рендера |
| `report.md` | `render.py` | fact-check, оркестратор | черновик: полный отчёт (full/rerun) или только Update-блок (update) |
| `describer.md` | `quotes.py --describer` (по запросу) | человек | результат describer'а с разрешёнными плейсхолдерами |

Вне папки: `/tmp/pr-<n>-comment.md` (`prepare_comment.py`).

### 8.2 `context.json`

Фрагмент из прогона `1393-64c47a99` (сокращён):

```json
{
 "schema_version": 1,
 "generated_at": "2026-10-26T12:57:12Z",
 "today": "2026-10-26",
 "repo": {"name_with_owner": "cobaltcore-dev/aurora-dashboard", "root": "<repo root>"},
 "docs": "<DOCS>",
 "run_dir": "<repo>/.claude/runs/review-and-comment-pr/1393-64c47a99",
 "pr": {
  "number": 1393, "title": "feat(aurora): add Key Manager (Barbican) in-core plugin", "author": "hodanoori",
  "state": "OPEN", "is_draft": false, "created": "2026-10-23", "merged_at": null, "closed_at": null,
  "base": {"ref": "main", "oid": "cd8e674e…"}, "head": {"ref": "feat/key-manager-plugin", "oid": "64c47a99…", "short": "64c47a99"},
  "additions": 4486, "deletions": 3, "changed_files": 48, "mergeable": "MERGEABLE",
  "files": [{"path": "packages/aurora/src/client/routeTree.gen.ts", "additions": 200, "deletions": 0, "generated": true}],
  "body_file": "pr-body.md", "diff_file": "pr.diff",
  "generated_files_not_in_diff": ["packages/aurora/src/client/routeTree.gen.ts", "…"]
 },
 "flags": {
  "base_not_main": false,
  "release": {"is_release": false, "matched": []},
  "api_contract": {"needed": true, "files": ["packages/aurora/src/server/KeyManager/routers/index.ts", "…"]},
  "touches_published_src": true
 },
 "mode": "update", "mode_reason": "head moved fd248f08 → 64c47a99",
 "report": {
  "path": "<DOCS>/aurora-dashboard-kb/prs/1393-key-manager-core-plugin.md", "exists": true,
  "status_frontmatter": "open", "status_line": "open", "old_head": "fd248f08",
  "footer": "_Analyzed 2026-10-25 · commit `fd248f08` · read-only · skill: review-and-comment-pr_",
  "old_head_reachable": true, "delta": "fd248f08…..64c47a99…", "status_update": null,
  "footer_new": "_Analyzed 2026-10-25 · commit `fd248f08` · read-only · updated for `64c47a99` on 2026-10-26 · skill: review-and-comment-pr_"
 },
 "status_now": {"frontmatter": "open", "line": "open", "index_date": "2026-10-23 (open)"},
 "process": [{"id": "missing-changeset", "where": "PR files", "text": "published package code changed without a .changeset/*.md"}],
 "provenance": ["read-only"],
 "fetch": {"head": "already local", "base": "already local"},
 "issue": {"linked": [{"number": 1133, "how": "bare", "title": "…", "state": "OPEN", "url": "…", "file": "issue-1133.md"}],
           "supplied": null, "source": "pr-body", "mentioned_prs": []},
 "ci": {"total": 22, "pass": 13, "fail": 0, "pending": 5, "skipping": 4, "cancel": 0, "failed": [], "pending_names": ["build", "test", "…"]},
 "changeset": {"files": [], "bumps": [], "missing": true},
 "discussion": {"comments": 3, "reviews": 1, "threads": 19, "bot_items": 22, "own_reports_excluded": 1, "inline_read": true, "file": "discussion.json"},
 "standards": {"copilot_instructions_file": "copilot-instructions.md", "claude_md": "<repo>/CLAUDE.md", "claude_md_exists": true}
}
```

Поля, не видные во фрагменте:

- `report.delta` = `"<old>..<head>"` | `"whole-pr"` (force-push) | `null`; `report.delta_base_changes_removed` — файлы, из дельты которых убраны изменения base (пишется текущим `collect.py` при достижимом старом head; в этом прогоне ключа нет — он создан более ранней версией скрипта).
- `report.status_update` (если статус изменился): `frontmatter_status`, `status_line`, `index_date`, `footer_old`, `footer_new` (последние два — только для закрытого/смёрженного PR в режиме `status`).
- `issue.source`: `pr-body` | `previous report` | `user` | `none`; `issue.supplied` — issue, заданное через `--issue`, ответом в терминале или взятое из футера прежнего отчёта (`source: previous report`).
- `ci.error` — если CI не прочитан; `ci.failed[]` — `{name, link}`.
- `changeset.bumps[]` — `{file, package, bump}`.
- В режимах `status`/`none` нет `fetch`, `issue`, `ci`, `changeset`, `discussion`, `standards`.

### 8.3 `discussion.json`

```json
{
 "comments": [{"author": "…", "created": "…", "url": "…#issuecomment-…", "body": "(earlier review-and-comment-pr report — omitted; see the url)",
               "bot": false, "own_report": true, "own_kind": "review"}],
 "reviews":  [{"id": 5670107878, "author": "TilmanHaupt", "state": "CHANGES_REQUESTED", "submitted": "…", "url": "…#pullrequestreview-…",
               "body": "…", "bot": false, "own_report": false}],
 "threads":  [{"id": 4360388743, "in_reply_to_id": null, "user": "Copilot", "user_type": "Bot", "path": "…", "line": null,
               "original_line": 15, "commit_id": "…", "created_at": "…", "url": "…#discussion_r…", "body": "…", "bot": true, "replies": []}],
 "inline_read": true
}
```

Отзывы (`reviews`) берутся через REST `gh api …/pulls/<n>/reviews` — с `id` и `url` (`…#pullrequestreview-<id>`), чтобы на тело ревью можно было сослаться; если вызов не удался — из `gh pr view --json reviews`, без `id`/`url`.

### 8.4 `delta.diff`

Обычный unified diff (сначала «как есть» для файлов, которых не касались изменения base, затем очищенные файлы по алфавиту). Подробно — §11.1.

### 8.5 `briefs/*.md`

Готовые брифы — шаблоны с подставленными путями, SHA, списками файлов (find-api-contract), критериями приёмки, правилами (find-security), списком прежних находок (update), группами и кандидатами (scorers). Пример заголовка:

```markdown
# Scorer 1 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<run>` — `context.json` (metadata, changed files, flags), `pr.diff` (…), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`
```

### 8.6 `out/*.json`

**`out/find-*.json`** (пример `find-diff-bugs`, прогон `1393-64c47a99`):

```json
{"candidates": [{
  "claim": "After switching Accept to application/octet-stream, getSecretPayload still reads the body with res.text(). For binary secrets … Reveal Payload and Copy show corrupted data …",
  "location": "packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:110",
  "evidence": "keyManagerRouter.ts lines 100-111 at 64c47a9: … `const text = await res.text()` …",
  "precedent": "The raw-text read was already there before this commit; …"}]}
```

`find-standards` дополнительно (пример из прогона `1393-fd248f08`): `"checklist": [{"item": "Raw HTML element (<div>, <table>, <button>) where a Juno component exists", "result": "violated", "where": "key-manager.tsx:91; …"}, …]`. Пусто: `{"candidates": []}`.

**`out/describer.json`**: `overview{what,how,affects}`, `qa{core_path[],edge_cases[]}`, `acceptance[{criterion,status,evidence}]`, `stale_callers[{symbol,location,note}]`, `scope`. Фрагмент `how` (прогон `1393-fd248f08`; в `1393-64c47a99` `how` пустой):

```text
**Layout route and service guard.** The `key-manager` layout checks the catalog in `beforeLoad` … 

[[code:packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx | const availableServices = await trpcClient | 7]]
```

**`out/score-<n>.json`**:

```json
{"scores": [
 {"id": "C1", "score": 75, "severity": "Low", "category": "Accessibility",
  "location": "packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:40",
  "reason": "The row toggle is `<Button icon=\"moreVert\" title={t`Secret actions`} />` with no `aria-label` … The Quick Reject Checklist says: …",
  "same_as": null,
  "precedent": {"kind": "existing", "ref": "packages/aurora/src/client/routes/_auth/projects/$projectId/network/floatingips/$floatingIpId/-components/-details/FloatingIpDetailsView.tsx:66"}},
 {"id": "C2", "score": 25, "reason": "The strings (\"Secret actions\") are tooltip/accessible names, not visible button labels, …", "same_as": null}
]}
```

**`out/earlier-findings.json`** (update):

```json
{"earlier": {
 "CR1": {"status": "fixed", "note": "getSecretPayload now sends Accept: application/octet-stream.",
         "evidence": "git show 64c47a99:keyManagerRouter.ts lines 98-104: headers: { Accept: \"application/octet-stream\" }, debug: false"},
 "CR3": {"status": "open", "note": "Still no success toast on create or delete of secrets, containers or orders.", "evidence": "git grep -n -i toast 64c47a99 -- … returned no matches; …"},
 "CR4": {"status": "partly", "note": "Reveal Payload is now gated by key-manager:secrets:payload; detail views still do not check the :get permissions.", "evidence": "…"}}}
```

**`out/factcheck.json`**: `{"wrong": [{"claim", "field": "overview.how", "old", "new", "evidence"}]}` или `{"wrong": []}`.

**`out/find-cross-boundary.json`**: как у finders, плюс `"boundaries": [{"change": "401 on the ports list reloads to /?redirect=…", "receiver": "packages/aurora/src/client/routes/index.tsx:32"}]`.

**`out/pr-description.json`**: `{"mismatches": [{"kind": "not in code" | "not described", "quote" (только `not in code`), "location" (только `not described`), "issue", "explanation", "fix", "evidence"}]}` или `{"mismatches": []}`.

### 8.7 `candidates.json`

```json
{"candidates": [{
  "claim": "The new row-action toggles are icon-only Buttons with only a title and no aria-label. …",
  "location": "packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:40",
  "evidence": "B.14 / Quick Reject: \"Icon-only button without `aria-label`\". … example: packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.tsx:67",
  "precedent": "FloatingIpDetailsView.tsx:66 also uses title only; …",
  "source": "find-standards", "id": "C1", "group": ["C1", "C2", "C16"], "batch": 1}],
 "batches": 3}
```

`source`: имя finder'а (`find-standards` …), `describer (acceptance)`, `describer (stale caller)`. `group` — `null`, если кандидат один в своём месте.

### 8.8 `compose.md`

Markdown для оркестратора (структура — §7.5). Пример заголовка находки:

```markdown
### `c8` — Major · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts | headers: { Accept: "application/octet-stream" },` · score 75
- **Claim** (find-api-contract): getSecretPayload hardcodes Accept: application/octet-stream. …
- **Scorer:** The update fixes CR1 by hardcoding … so this is scored as a new problem and not dropped as a repeat of CR1. …
- **Precedent:** …
- **Evidence:** …
- Bug: add its scenario to `edge_cases` in texts.json.
```

(Location здесь в сыром виде scorer'а; `render.py` разрешит `path | text` в `path:line`.)

### 8.9 `texts.json`

Full (форма шаблона из `compose.md`):

```json
{
 "summary": "2–4 sentences",
 "confidence": "High | Medium | Low",
 "index_affected": "touched surface, ≤ 40 words, no verdict",
 "findings": {"c8": {"issue": "", "title": "", "explanation": "", "fix": ""}},
 "edge_cases": ["scenario behind each Bug finding, citing [[ref:<id>]]"],
 "merge": {},
 "provenance_extra": []
}
```

Необязательные: `fixes` (`[{"field": "overview.how", "old": "…", "new": "…"}]`), `process`, `process_overrides`, `overview`, `qa`, `scope`. В прогоне `1393-fd248f08` использовались `merge` (`{"c24": "c13", "c57": "c11", "c28": "c41"}`) и три `fixes` из fact-check.

Update (`1393-64c47a99`): ключи `earlier`, `confidence`, `findings`, `merge`, `provenance_extra`:

```json
{"earlier": {
  "CR1": {"status": "partly", "note": "getSecretPayload now sends `Accept: application/octet-stream`, which fixes octet-stream secrets but still gets 406 for secrets stored with another content type — see [[ref:c8]]."},
  "CR2": {"status": "fixed", "note": "Order modal now validates algorithm and bit length …"}},
 "confidence": "Medium",
 "findings": {"c8": {"issue": "`getSecretPayload` hardcodes `Accept: application/octet-stream`, so non-octet-stream secrets still fail with 406",
                     "title": "Reveal Payload fails for secrets whose content type isn't `application/octet-stream`",
                     "explanation": "A user who stores a secret as `text/plain` … \n\n[[code:packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts | headers: { Accept: \"application/octet-stream\" } | 1]]\n\n…",
                     "fix": "…"}},
 "merge": {}, "provenance_extra": []}
```

### 8.10 `findings.json`

Ключи: `schema_version` (1), `summary`, `confidence`, `findings[]` (`id`, `score`, `severity`, `category`, `location`, `precedent`, `issue`, `title`, `explanation`, `fix`), `process[]`, `process_overrides{}`, `overview{}`, `qa{}`, `provenance_extra[]`, `index_affected`, `scope`, (`earlier{}` на update), `dismissed[]` (`{score, claim, location, reason, discussion}`). Плейсхолдеры в нём ещё не разрешены — это делает `render.py`. Пример записи `dismissed`:

```json
{"score": 25, "claim": "Accessible names/tooltips \"Secret actions\", … are not title case, …",
 "location": "packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:40",
 "reason": "The strings (\"Secret actions\") are tooltip/accessible names, not visible button labels, …", "discussion": ""}
```

### 8.11 `report.md`

Черновик, который пишет `render.py` до записи в `DOCS` (и при `--dry-run`): полный отчёт на full/rerun или только Update-блок на update. Над ним работает fact-check.

---

## 9. Скоринг и вердикт

### 9.1 Шкала (`references/scoring.md`)

Перед оценкой scorer открывает цитируемый код на `headRefOid`, перезапускает команды, на которых держится улика, и проверяет утверждение. Ставится ровно одно из значений:

| Score | Значение |
| --- | --- |
| 0 | не уверен совсем: ложное срабатывание или существовавшая до PR проблема |
| 25 | может быть реальным, может нет; код проверен, но решить нельзя; стилистика, явно не названная в стандартах |
| 50 | проверено, реально, но мелочь или редко встречается |
| 75 | высокая уверенность: проверено в коде, скорее всего встретится на практике, или проверенное нарушение правила из стандартов |
| 100 | абсолютная уверенность, прямая улика, будет случаться часто |

**Порог — 50:** ниже в отчёт как находка не попадает (уходит в `dismissed`).

Правила, корректирующие оценку:

- **Evidence rule.** Кандидат цитирует официальный API-референс или стандарт, и код делает то, что цитата запрещает, — проверено; оценка по влиянию (50/75/100). «Не могу запустить» / «не могу открыть доку» — не повод для 25.
- **Precedent-table rule.** Совпадение со строкой таблицы «Severity precedents» и код делает описанное — проверено: минимум 50 и severity из строки.
- **External-API claims.** Поведение OpenStack/Ceph/S3 — только по цитате find-api-contract или по референсу, прочитанному так, как описано в `external-api-checker.md`, не по памяти. Функция, молча не показывающая ожидаемые данные, считается «will likely be hit in practice».
- **Quick Reject rule.** Проверенное нарушение пункта «Quick Reject Checklist» из `copilot-instructions.md` — минимум 75, даже если такой паттерн уже есть в коде; пункт цитируется в reason. Раздел «What NOT to Review» по-прежнему важнее (например, хардкод строк в `packages/aurora` контролирует линтер).
- **Precedent rule.** Отказ мейнтейнера в том же на другом PR или та же проблема в существующем коде **не снижают** оценку проверенного кандидата — ставится тег `precedent` (`existing`: смёрженный код уже имеет ту же проблему, `ref` — `path:line` на `baseRefOid`; `deferred`: мейнтейнер принял/отложил, `ref` — URL комментария). Строки, которые PR не трогал, всё равно «pre-existing» и получают низкую оценку.
- **Usual false positives** (0–25): существовавшие проблемы; то, что выглядит как баг, но не баг; педантичные мелочи; то, что ловит линтер/тайпчекер/CI; общие мнения о качестве (тесты, docs, абстрактное «добавьте rate limiting»), если стандарты их явно не требуют; явно заглушённое в коде; намеренные изменения в рамках PR; реальные проблемы на нетронутых строках.

### 9.2 Severity (для score ≥ 50)

| Severity | Маркер | Значение |
| --- | --- | --- |
| Critical | 🔴 | ломает основной сценарий для всех, дыра в безопасности, потеря/порча данных |
| Major | 🟠 | ломает функцию или скрывает ожидаемые данные без простого обхода |
| Moderate | 🟡 | заметно, но ограниченно: деградация UX, пробел доступности, дублирующие запросы, нарушенное правило с видимым эффектом |
| Low | 🟢 | косметика, формулировки, редко заметное нарушение правила |
| Trivial | ⚪ | мелочь без эффекта для пользователя |

Score и severity — разные вопросы: нарушение Quick Reject — минимум 75, но может быть 🟢 Low.

**Severity precedents** (оценивать одинаково каждый раз):

| Случай | Severity |
| --- | --- |
| Фильтр списка скрывает ресурсы, которые политика сервиса по умолчанию разрешает видеть | 🟠 Major |
| Нет пагинации, а референс даёт конечный размер страницы по умолчанию | 🟡 Moderate |
| Нет пагинации, а API по умолчанию возвращает всё | 🟢 Low |
| Одни и те же данные загружаются дважды (loader + `useQuery`) | 🟡 Moderate |
| Состояние, которое стандарты хотят в URL (вкладка, фильтр), лежит в `useState` | 🟢 Low |
| 401/403 обрабатываются инлайн вместо редиректа/сообщения страницы | 🟢 Low |
| UI-правила Quick Reject (raw HTML, all-caps, «Please», порядок импортов) | 🟢 Low или ⚪ Trivial |
| Нет тестов на новый код, когда эпик или стандарты их требуют (иначе — false positive, 0–25) | 🟢 Low |
| Критерий issue в пределах заявленного scope PR выполнен частично | 🟢 Low |

### 9.3 Категории

Ровно одна: `Bug`, `Security`, `Accessibility`, `UI/UX`, `Code Quality`, `Performance`, `Docs`, `Test coverage`. Конфликты слияния (с `main` или другими PR) — не находки. `Process` — только для Process-пунктов (draft, расхождение описания с кодом, нет changeset, нет issue); их ставят `collect.py` и оркестратор, а не scorer.

### 9.4 Раскладка и нумерация (`render.layout`)

- Находки сортируются по severity, затем в исходном порядке.
- **Required Changes** — Critical/Major/Moderate, номера `CR1…`; **Process** — пункты из `context.json` (стандартные тексты `default_process` + `process_overrides`) и `findings.process`, номера `P1…`, показываются в таблице Required Changes после CR; **Improvements** — Low/Trivial, номера `I1…`.
- `[[ref:<id>]]` в текстах заменяются на номера, голые id комментариев (`comment <id>`, `issuecomment-<id>`, `r<id>`, 8+ цифр, есть в `discussion.json`) — на ссылки (`link_comments`; в code span, Markdown-ссылках и URL не трогаются).

### 9.5 Рекомендация

`blocks(f)` = категория `Bug` или `Security` **и** нет `precedent`. Правило:

| Условие | Рекомендация |
| --- | --- |
| есть Required Change, для которого `blocks()` | 🔴 Request Changes |
| есть Required Changes, но все — конвенции (UI/UX, Performance, Code Quality, …) или с тегом прецедента | 🟡 Approve with changes |
| Required Changes нет, есть Process | 🟡 Approve with process to-dos |
| только Improvements | 🟢 Approve with nits |
| ничего | 🟢 Approve |

Под строкой рекомендации — список «Before merge» (`before_merge`):

- `- **Must fix before merge** (<scope>): CR…` — блокирующие Required Changes, со `scope` describer'а, если есть;
- `- **Team call** (convention, existing pattern or deferred by a maintainer): CR…` — остальные Required Changes;
- на update: `- **Still open from the earlier review:** CR3, CR4 (partly) · P1` (§11.4);
- `- **Process:** P…`.

**Confidence to Merge** (`High`/`Medium`/`Low`) выбирает оркестратор (§5, шаг 5.3); draft не учитывается.

Пример (KB-отчёт #1393, полный разбор): `Recommendation: **🔴 Request Changes** … Confidence to Merge: **Medium**`, `Must fix before merge: CR1, CR4, CR6, CR7, CR8, CR9, CR10`, `Team call: CR2, CR3, CR5`, `Process: P1`.

---

## 10. Отчёт, индекс и комментарий в PR

### 10.1 Основной отчёт (full/rerun) — порядок

1. Frontmatter: `type: pr-report`, `date`, `status` (`open`/`merged`/`closed`), `pr: [<n>]`, `issue: [<связанные в теле PR>]` (issue, заданное пользователем, сюда не попадает), `author`, `branch`.
2. `# PR #<n>: <title>`; строка `` **Author:** … · **Status:** … · **Base:** `<base>` ← `<head>` ``; строка `**Size:** N files, +a / −d · **Created:** … · [View on GitHub](…)`.
3. Если база не `main` — `` > **Base branch is `<ref>`, not `main`.** ``.
4. `---`, `## PR Review Report by [review-and-comment-pr](<SKILL_URL>)` (ссылка на `SKILL.md` в бэкапе `KirillMishchuk/aurora-dashboard-docs`).
5. `` _Reviewed at head [`<sha8>`](<PR url>/commits/<oid>) · base `<ref>` at `<oid8>` · <YYYY-MM-DD HH:MM UTC>_ `` (время сбора из `generated_at`).
6. `### ⚖️ &nbsp; Verdict`: строка Recommendation + Confidence, список Before merge, summary простым текстом.
7. `### 🔧 &nbsp; Required Changes` — таблица `# | Severity | Category | Precedent | Issue | Location` (CR, затем P) и свёрнутый `<details>` «Explanation & Fix»: по каждой `**CR1 — <title>** · <Category> · <location>`, explanation, строка `_Precedent:_` (если тег), `_Fix:_ …`. Пусто — `None.`.
8. `### 💡 &nbsp; Improvements` — то же для I.
9. `### 🗨️ &nbsp; Review comments not taken up` — если есть (§10.3).
10. `---`, `## Solution Overview`: свёрнутые «What was done», «How it is implemented», «What it affects (blast radius)».
11. `---`, `## QA Test Plan`: свёрнутые «Core Path» (нумерованный) и «Edge Cases».
12. `---`, `## Checked and dismissed` — свёрнутая таблица кандидатов ниже 50 (`Score | Candidate | Location | Why`). **Только в KB, не публикуется.**
13. `---`, футер `` _Analyzed <today> · commit `<sha8>` · <provenance> · skill: review-and-comment-pr_ ``, где provenance = `context.provenance` (`read-only`, `acceptance graded against #N supplied by the reviewer`, `review threads not read`, `CI not read`) + `provenance_extra`.

Колонка Precedent: `—`, `existing code` или `[deferred](<url>)`; строка ``_Precedent:_ the same pattern is already in merged code — `<ref>`.`` или `_Precedent:_ a maintainer accepted or deferred the same point — [discussion](<url>).` Ячейки таблиц экранируют `|` как `\|`; ширина колонок выравнивается с учётом широких символов.

После всего `update-related.py` может дописать блок `<!-- related:auto … -->` в конце файла.

### 10.2 Строка индекса (`DOCS/aurora-dashboard-kb/prs/README.md`)

```markdown
| [#<n>](<url>) | <Date> | <title> | <index_affected> Verdict: <…> | [<file>](./<file>) |
```

- **Date:** `<created> (open)`, `<created> (draft)`, `<created> → merged <d>`, `<created> → closed <d>`.
- **Verdict** (`verdict_index`): `Verdict: Approve — clean` или `Verdict: <Request Changes | Approve with changes | Approve with process to-dos | Approve> — <k> Required Change(s) (<маркеры severity> + <p> process), <m> Improvement(s)` (число Required Changes включает Process; «Approve with nits» в индексе пишется как `Approve`).
- **Порядок:** новая строка вставляется по дате создания PR (новые сверху; при равенстве — больший номер выше); существующая строка этого PR заменяется, дубли удаляются. Full re-run переписывает строку целиком.
- В индексе должна уже быть таблица: если строк вида `| [#N](` нет, `render.py` не создаёт её, а сообщает `Index: row NOT updated — … add the table by hand first`.
- **Update** дописывает хвост ``· Update <date> (`<sha8>`): <рекомендация> — <k> Required Change(s) (…), <m> Improvement(s); <f> earlier fixed`` (или `no new findings`); следующий Update заменяет хвост. Реальный пример (#1393): `` … · Update 2026-10-26 (`64c47a99`): Request Changes — 1 Required Change (🟠), 3 Improvements; 7 earlier fixed ``.
- **status** меняет только ячейку Date.

### 10.3 «Review comments not taken up»

`not_taken_up()`: строка `dismissed` (отсеянный кандидат или его дубликат), чьё поле `discussion` ссылается на комментарий (`r<id>`, `discussion_r<id>`, `issuecomment-<id>` или `pullrequestreview-<id>` — тело ревью, 6+ цифр) из `discussion.json`, кроме собственных отчётов скилла, — строка таблицы `Raised by | Claim | Why not a finding` (claim — до 450 символов, причина — до 400; длинный текст обрезается по границе предложения с « …», по словам — только если первое предложение длиннее лимита; `render.short`) (`<автор> [r<id>](url)`, claim, reason scorer'а). Смысл: комментарий ревьюера (например, Copilot), который проверили и с которым не согласны, не выглядит проигнорированным. Секция публикуется (и в основном отчёте, и в Update-блоке).

### 10.4 Update-блок

Описан в §11.4.

### 10.5 Что публикуется, а что остаётся в KB

| Часть | В KB | В комментарии |
| --- | --- | --- |
| Frontmatter, заголовок, Author/Size | да | нет |
| `## PR Review Report …` → Verdict, Required Changes, Improvements, Review comments not taken up | да | да |
| Solution Overview | да | да (если комментарий > 60 000 символов — заменяется ссылкой на отчёт в KB) |
| QA Test Plan | да | да |
| Checked and dismissed | да | нет |
| Футер `_Analyzed …` | да | нет |
| Блок Related | да | нет |
| Update-блок (`--update`) | да | только последний блок |

### 10.6 `prepare_comment.py` подробно

- **Нарезка** (`slice_comment`): full — от `## PR Review Report` до футера `\n---\n\n_Analyzed` или до `\n---\n\n## Checked and dismissed`, что раньше; `--update` — последний `## Update — …` до футера или до следующего заголовка `## `, который не Update.
- **Длина** (`fit`): GitHub ограничивает комментарий 65 536 символами; если тело длиннее `MAX_COMMENT = 60000`, раздел Solution Overview заменяется на `Left out of this comment for length — see [the full report](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/aurora-dashboard-kb/prs/<file>).` Если Solution Overview нет — только заметка о длине.
- **Сканер** (`SCAN`), построчно, с названием раздела:

  | Вид | Что ловит |
  | --- | --- |
  | `secret` | `-----BEGIN … KEY-----`; `authorization`/`bearer` `:`/`=` 8+ символов; `password|passwd|secret|api_key|token` `:`/`=` 8+ символов; `AKIA…`; `ghp_…`/`github_pat_…`; длинные (40+) base64-подобные строки с буквами и цифрами |
  | `local path` | `/Users/<x>`, `/home/<x>`, `C:\Users\`, `/private/var/`, `/private/tmp/`, `/var/folders/` |
  | `internal host` | `*.internal|corp|local|lan`; `github.tools.sap`, `*.cloud.sap`, `*.sap.corp`, `jira.`, `confluence.`, `grafana.`, `wiki.` |
  | `private IP` | `10.x.x.x`, `192.168.x.x`, `172.16–31.x.x` |
  | `e-mail` | адреса e-mail |
  | `env data` | `OS_PASSWORD`, `OS_APPLICATION_CREDENTIAL_SECRET`, `OS_AUTH_TOKEN`, `AWS_SECRET_ACCESS_KEY` |

- **Markdown** — `check_report_md.check()`; hook не установлен → «check skipped … (not blocking)».
- **Сводка:** `Comment file: /tmp/pr-<n>-comment.md (<chars> chars, <lines> lines)`, `Length: …` (если сработал `fit`), `Post as: @<login>` (`gh api user --jq .login`), `Verdict: Recommendation: …`, на `--update` — `Before merge:`, `Reviewed: …`, `Findings: <CR> Required Changes, <P> Process, <I> Improvements`, `Sections: …`, `Links:`, затем `SAFETY HITS — posting is blocked until the user decides:` со строками `line <n> [<section>] <kind>: <match>` или `Safety scan: clean — …`, затем Markdown.

---

## 11. Update-режим подробно

Update — PR с существующим отчётом и новыми коммитами. Старый текст отчёта не меняется: перед футером добавляется блок `` ## Update — <today>, head `<sha8>` ``; повторный рендер на том же head заменяет этот блок.

### 11.1 Delta (`collect.delta_diff`)

1. Старый head берётся из футера отчёта (`old_head`), резолвится в полный SHA; проверяется, что он предок нового head (`git merge-base --is-ancestor`). Нет — `delta = "whole-pr"`, `delta.diff` не пишется, агенты смотрят весь PR, бриф говорит «the old head is unreachable (force-push)», сводка — `— old head unreachable (force-push?)`.
2. Да — `delta = "<old>..<head>"`, diff ограничен файлами PR (без сгенерированных).
3. **Изменения из влитого base не считаются работой автора.** Если merge-base старого и нового head с base различаются, для каждого файла PR, который base изменил между ними:
   - старая версия файла поднимается до нового base трёхсторонним `git merge-file -p` (ours = файл на старом head, base = на старом merge-base, theirs = на новом merge-base), и дельта берётся против результата;
   - если `merge-file` конфликтует или файл не текстовый — берётся обычный `old..head` diff файла, из которого выкидываются hunk'и, в точности совпадающие с изменением base (те же удалённые и добавленные строки). Список очищенных файлов — `report.delta_base_changes_removed`; сводка печатает `· base-branch changes left out of N file(s)`.
4. Агентам бриф говорит: анализировать только `delta.diff`, диапазон самим не диффать.

### 11.2 Агенты на update

- describer — бриф `describer-update.md` (§6.4): только то, что не покрыто прежними находками, без QA-плана;
- finders `find-*` — как обычно, но в `_header` блок Scope (только delta);
- `earlier-findings` — статус каждой прежней находки на новом head (§6.6);
- scorers — получают список прежних находок: кандидат, возражающий против того, что PR сделал по прежней находке, получает 0 с именем находки в reason; сделано плохо (ломает что-то или наполовину) — оценивается как обычно;
- fact-check — проверяет только «What changed» нового блока.

### 11.3 Прежние находки (`quotes.earlier_rows`)

Единый для всех скриптов разбор: строки таблиц отчёта вида `| CR<n> | … |`, `| P<n> | … |`, `| I<n> | … |` с 5 ячейками (или 6, с Precedent; `\|` внутри ячейки учитывается) — номер, severity, issue, location (и при `detail=True` ячейки Precedent и Category). Блок Update для **текущего** head исключается (чтобы перерендер не считал свои же находки «прежними»), а более ранние Update-блоки входят — их находки тоже «прежние».

### 11.4 Состав Update-блока (`render_update`)

1. `` ## Update — <today>, head `<sha8>` ``, строка `_Reviewed at head …_`.
2. `### ⚖️ &nbsp; Verdict` — Recommendation и Confidence **на текущем head** (`update_recommendation`) и Before merge.
3. `### Fixed since last analysis` — `- <n> — <note>` для `fixed` (или `None of the earlier findings is fixed yet.`).
4. `**Partly fixed**`, `**Still open**`, `**No longer reviewed**` (`dropped`) — только непустые.
5. `### 🔧 &nbsp; Required Changes` и `### 💡 &nbsp; Improvements` — находки delta, нумерация **продолжает** номера отчёта (`used_numbers`: максимальные CR/P/I в отчёте без блока этого head; например, после CR10 — CR11). Process-пункты из `context.json` в Update-блок **не добавляются** (`ctx_process=False`); незакрытые прежние P видны через статусы.
6. `### 🗨️ &nbsp; Review comments not taken up` — если есть.
7. `### What changed` — свёрнутые «What was done» и (если не пусты) «How it is implemented», «What it affects (blast radius)»; последним.

QA Test Plan и «Checked and dismissed» в Update-блок не входят. В тексте update допустимы номера прежних находок (`CR2`) текстом; свои находки — через `[[ref:<id>]]`; Process-пункты из `context.json` по `[[ref:]]` не адресуются.

### 11.5 Вердикт на update и `carried`

`update_recommendation()` применяет то же правило, что `layout()`, к объединению:

- находки этого блока;
- прежние находки со статусом не `fixed`/`dropped` и не `carried`; для прежних CR категория и прецедент берутся из ячеек Category/Precedent их строки в отчёте (строка не найдена — считается Bug, то есть блокирующей).

Итог: блокирующие → 🔴 Request Changes; иначе любые Required (новые или прежние CR) → 🟡 Approve with changes; иначе Process (новые или прежние P) → 🟡 Approve with process to-dos; иначе Improvements (новые или прежние I) → 🟢 Approve with nits; иначе 🟢 Approve.

**`carried`:** прежняя находка со статусом `partly`/`open`, чья note содержит `[[ref:<id>]]` на находку этого блока, — её остаток передан новой находке; считается только новая, не дважды. Пример из #1393: CR1 `partly` с note «… — see [[ref:c8]]» → новая CR11 блокирует, а CR1 в «Still open from the earlier review» не попадает.

Строка «Still open from the earlier review» перечисляет прежние CR и P (не I), не `fixed`/`dropped`/`carried`, с пометкой `(partly)`; формат `CR3, CR4 (partly), CR5 · P1`.

### 11.6 Что ещё меняет update

Футер: `` … · updated for `<sha8>` on <today> · skill: … `` (`footer_new` из `collect.py`); статус — если менялся; индекс — хвост Update (§10.2) и Date при смене статуса; Related. Публикуется только новый блок: `prepare_comment.py <report> <n> --update`. Follow-ups на шаге 9 предлагают находки блока и прежние незакрытые.

---

## 12. Release-PR

Флаг `Release PR: yes (...)` в сводке `collect.py` (§4). Release-PR только поднимает версии и changelog'и; скрипты не запускают агентов (`briefs.py find` печатает `Release PR: no agents — do the light review yourself (Step 2).`, `score` — `No scoring for this mode / release PR.`). Вместо шагов 4–5 — лёгкое ревью оркестратором:

- без Process-пункта о связанном issue (`collect.py` его не добавляет) и без агентов;
- проверить: каждый bump соответствует потреблённым changeset'ам; записи changelog рендерятся корректно; новой версии ещё нет в npm (`npm view <package> version`); не изменят ли тип bump'а ожидающие changeset'ы в других открытых PR;
- проблема changelog исправляется в `.changeset/*.md` на `main`, а не в этой ветке — бот перегенерирует.

Затем оркестратор сам пишет `<run folder>/findings.json` (все обязательные ключи из `findings-format.md`; из описательных — только `overview.what` и `qa.edge_cases`; без `dismissed`) и запускает только `render.py` (без `texts.json` и `assemble.py`). Отчёт содержит Verdict, Required Changes, Improvements, «What was done» и Edge Cases. Ошибки рендера, правки fact-check и проблемы Markdown правятся в `findings.json`, затем снова `render.py`.

---

## 13. Зависимости, окружение, установка

### 13.1 Требования (`SKILL.md`, setup-документ)

- **`gh`, залогиненный в GitHub** (чтение `cobaltcore-dev/aurora-dashboard`; права на комментарий — если публиковать). Через него идёт всё о PR. Ошибка авторизации в `collect.py` → остановиться и попросить `gh auth login`.
- **`git`**; **`python3` 3.9+** (без него скилл не может ни собрать, ни оценить, ни записать, ни опубликовать).
- **Папка `DOCS` рядом с репозиторием** (`<parent>/aurora-dashboard`, `<parent>/DOCS`, клон `KirillMishchuk/aurora-dashboard-docs`); `collect.py` её ищет и останавливается, если нет `DOCS/aurora-dashboard-kb/prs`.
- **Файлы скилла** (`scripts/*`, `references/*`).
- **Агенты** `pr-reviewer`, `external-api-checker`, `security-reviewer` в `.claude/agents/` — необязательны, у каждого fallback (general Sonnet agent с тем же брифом).
- **Сеть для референсов:** `curl` к `raw.githubusercontent.com`, `docs.ceph.com`, документация AWS — для find-api-contract и scorers. `npm` — только для release-PR.
- **Необязательно:** hook `check_report_md.py` (его же используют `render.py` и `prepare_comment.py`) и настройки проекта, удешевляющие прогон. Без них прогон работает, но медленнее и дороже: без hook проверка Markdown просто пропускается (`Markdown: check skipped`).

### 13.2 `settings.local.json` (что относится к скиллу)

- `permissions.allow`: `python3 .claude/skills/review-and-comment-pr/scripts/collect.py` (с аргументами и без), `render.py *`, `quotes.py *`, `briefs.py *`, `save.py *`, `assemble.py *`; `git show *`, `git grep *`, `git blame *`, `git fetch *`, `git rev-parse *`, `git diff *`, `git log *`, `git merge-base *` и др.; `gh pr view|list|diff|checks|status *`, `gh issue view|list *`, `gh search *`, `gh api --method GET *`, `gh api user *`, `gh pr comment *`; `python3 .claude/skills/review-and-comment-pr/scripts/prepare_comment.py *`; `curl -s https://raw.githubusercontent.com/openstack/*` (find-api-contract читает исходники api-ref; другие адреса `curl` спрашивают); `grep *`; `npm view *`; `Edit(//tmp/pr-*-comment.md)` и `Edit(//private/tmp/pr-*-comment.md)`; `Read(//<абсолютный путь к папке SAP>/**)` (на главной машине — путь пользователя); `WebFetch` для `docs.openstack.org`, `docs.ceph.com`, `docs.aws.amazon.com`.
- `permissions.deny`: `SendFeedback`, `ScheduleWakeup`, `ShareOnboardingGuide`.
- `enabledPlugins`: `code-review@claude-plugins-official`.
- `enableArtifact: false`, `disableWorkflows: true`, `disableClaudeAiConnectors: true`, `env.CLAUDE_CODE_FORK_SUBAGENT = "0"`.
- `hooks`: PostToolUse `Write|Edit` и PreToolUse `Bash` → `python3 "$CLAUDE_PROJECT_DIR"/.claude/hooks/check_report_md.py`.

Публикация не требует отдельного разрешения Claude Code (решение 28.10): `prepare_comment.py` и `gh pr comment` в `allow`, подтверждение — явное «да» в чате (шаг 8). Так же в `review-and-comment-pr-remote-setup.md`.

### 13.3 Где что хранится

| Что | Где |
| --- | --- |
| Прогоны | `aurora-dashboard/.claude/runs/review-and-comment-pr/<n>-<sha8>/` (git-ignored, `.claude` в `.gitignore`) |
| Отчёты и индекс | `DOCS/aurora-dashboard-kb/prs/<n>-<slug>.md`, `DOCS/aurora-dashboard-kb/prs/README.md` |
| Follow-ups | `DOCS/FOLLOW-UPS.md` (только по решению пользователя) |
| Комментарий перед публикацией | `/tmp/pr-<n>-comment.md` |
| Бэкап конфига | `DOCS/ToolDocs/claude-config/aurora-dashboard-config/.claude/` — синхронизировать после каждой правки скилла |

### 13.4 Установка на другой машине

По `DOCS/ToolDocs/claude-config/review-and-comment-pr-remote-setup.md`:

1. `git -C <parent>/DOCS pull`; Claude Code запускать в корне репозитория с доступом к DOCS: `cd <parent>/aurora-dashboard && claude --add-dir ../DOCS`.
2. Скопировать из бэкапа:

   ```bash
   SRC=../DOCS/ToolDocs/claude-config/aurora-dashboard-config/.claude
   mkdir -p .claude/agents .claude/hooks .claude/skills
   cp $SRC/agents/pr-reviewer.md $SRC/agents/external-api-checker.md \
      $SRC/agents/security-reviewer.md .claude/agents/
   cp $SRC/hooks/check_report_md.py .claude/hooks/
   rsync -a --delete $SRC/skills/review-and-comment-pr/ .claude/skills/review-and-comment-pr/
   ```

3. `settings.local.json` **не копировать целиком** (абсолютные пути главной машины): влить ключи из setup-документа, заменить `<parent>` на путь этой машины; на macOS добавить `Edit(//private/tmp/pr-*-comment.md)`. Показать пользователю итоговый файл перед сохранением.
4. Проверка: `/agents` показывает три агента, `/hooks` — два hook'а; пробный прогон с ответом «нет» на публикации, затем `/cost`. Ожидается отчёт в `DOCS/aurora-dashboard-kb/prs/`, строка в индексе, папка прогона; по документу — типично ~$2.6–3 и 7–10 минут.
5. На той машине скилл не правят: обновление — `git pull` DOCS и повтор шага 2.

---

## 14. Проверка изменений скилла

### 14.1 Регрессионный набор

`DOCS/ToolDocs/claude-config/review-pr-regression/` — воспроизводит все скриптовые шаги на сохранённых прогонах и сравнивает результат с `golden/`. Без агентов, без сети, без записи в `DOCS`. Запускать до и после каждой правки.

```bash
cd <SAP>/DOCS/ToolDocs/claude-config/review-pr-regression
PYTHONDONTWRITEBYTECODE=1 python3 -B run.py \
  --skill <SAP>/aurora-dashboard/.claude/skills/review-and-comment-pr \
  --repo  <SAP>/aurora-dashboard
# опции: --sap <SAP root> (по умолчанию родитель --repo), --only <fixture>, --update
```

Что воспроизводится на временной копии фикстуры: `delta.diff` и заметка (update, через `collect.delta_diff`, только git), `briefs.py find` (лог + брифы), `briefs.py score` (лог + брифы + `candidates.json`), `save.py` на каждом `out/*.json`, `assemble.py` (`compose.md`), `assemble.py --texts` (`findings.json`), `render.py --dry-run` (`report.md`), нарезка `prepare_comment` (`comment.md`, с `fit`), `briefs.py factcheck`. Пути, время в строке Reviewed и пометки «agent missing» нормализуются.

- `OK` по каждой фикстуре — правка не изменила ни одного вывода. Exit 0 — всё совпало, 1 — различия (unified diff по каждому файлу).
- Ожидаемое различие: проверить и записать новый golden `--update`. Неожиданное — регрессия.
- **Правило:** правка брифа, меняющая формат вывода агента, сохранёнными `out/*.json` не покрывается — добавить фикстуру (или поправить `out/` существующей) в новом формате.
- Для update-фикстур `report-before.md` — KB-отчёт до этого прогона; `{{SAP}}` в фикстурах подменяется на корень SAP; checkout aurora-dashboard должен содержать коммиты фикстур.

| Фикстура | Режим | Что покрывает |
| --- | --- | --- |
| `1393-fd248f08` | full | 7 finders, 9 батчей scorers, 31 находка (10 CR + 21 I) и Process P1, треды Copilot, «Review comments not taken up» |
| `1383-0a594e9e` | full | старый прогон: finders без `example:`, `render.py` останавливается на удалённой категории `Conflict` |
| `1377-86a355a8` | update | 14 прежних находок, в т.ч. `dropped` (CR4), бриф describer-update, вердикт с Confidence |
| `1393-64c47a99` | update | автор исправил находки (partly/fixed), новая находка, заменяющая прежнюю, URL тредов в `discussion` |

На 28.10 прогон набора по текущему скиллу дал `OK` по всем четырём фикстурам: `1377-86a355a8` — 28 файлов, `1383-0a594e9e` — 23, `1393-64c47a99` — 29, `1393-fd248f08` — 32. Сегодняшняя дата в выводе заменяется на `<TODAY>` (`normalize()` в `run.py`), иначе набор «падал» на следующий день. Ручные образцы новых форматов: `out/pr-description.json` в `1377-86a355a8`, `1393-64c47a99`, `1393-fd248f08` (реальные расхождения: Routers «unchanged», «add/remove secret refs») и `out/find-cross-boundary.json` в `1377-86a355a8` (только `boundaries`). В `1377-86a355a8` дубликат C9 → C5 (25) — реальный случай потерянной до 28.10 находки, теперь в `dismissed`.

Ручная проверка без живого прогона: скопировать папку прогона, поправить пути в `context.json` (`repo.root`, `docs`, `run_dir`), запускать скрипты с `PYTHONDONTWRITEBYTECODE=1` и `render.py --dry-run`; `quotes.py --run … --report …` проверяет готовый Markdown.

### 14.2 Аудит стоимости

`DOCS/ToolDocs/claude-config/cost-audit/`:

- `audit_session.py <session.jsonl> [<session dir>]` — обзор: стоимость по моделям из `cost-state` рядом с пересчётом по прайсу (обычный и long-context), проверка, что в логе один прогон, строка на агента (модель, effort, запросы, максимальный контекст, thinking, оценка стоимости), контекст оркестратора по запросам, вызовы инструментов, ошибки. `--agent "<name>"` (`describer`, `find-standards`, `scorer 2`, `fact-check`, `main`) — один агент по шагам.
- `README.md` — инструкция для агента на машине, где был прогон (найти лог в `~/.claude/projects/`, запустить скрипт, сравнить с эталоном `baseline-1383.txt`, проверить модели/провайдера, версию скилла и настройки, ходы оркестратора, повторы, размеры агентов, число агентов, calls per request, effort), отчёт в `~/review-cost-audit.md` вне `DOCS`.
- `PROMPT.md` — готовые промпты для запуска аудита. Это только диагностика: ничего не менять, не коммитить, логи в `DOCS` не класть.
- Эталон из `cost-audit/README.md`: #1383 на главной машине — $2.60 за 8.9 мин; оркестратор Opus $0.90, 22 запроса; 14 агентов Sonnet $1.70; агенты в foreground, одним сообщением на шаг; effort medium.

---

## 15. Типичные ошибки и что делать

| Сообщение | Источник | Что делать |
| --- | --- | --- |
| `` gh is not signed in to GitHub — run `gh auth login` `` | `collect.py`, exit 1 | остановиться, попросить пользователя `gh auth login` |
| `<DOCS>/aurora-dashboard-kb/prs not found — the DOCS folder must sit next to the repo` | `collect.py`, exit 1 | разместить `DOCS` рядом с репозиторием |
| `not inside a git repository — run from the aurora-dashboard repo` | `collect.py`, exit 1 | запускать из корня репозитория |
| `several reports for #N: … — merge or remove the extra one first` | `collect.py`, exit 1 | сообщить пользователю; отчёты самому не удалять и не сливать |
| `the existing report's footer names no analyzed commit — …` | `collect.py`, exit 1 | проверить отчёт вручную (пользователь) |
| `pull/N/head is …, expected … — the PR moved; re-run` / `can't fetch …` | `collect.py`, exit 1 | перезапустить; если повторяется — передать пользователю |
| `NEEDS INPUT: … Re-run with: …` | `collect.py`, exit 3 | задать вопрос один раз, перезапустить с флагом |
| `INVALID — N error(s), nothing saved; …` | `save.py`, exit 1 | (агент) исправить и повторить; оркестратор перезапускает агента один раз, если тот не сохранил |
| `…: abbreviated path (…/ or .../) — write the full repo-relative path` | `save.py`, `render.py`, hook | писать полный путь от корня репозитория |
| `…: names run-folder files or fields (…) — this text can be posted; …` | `save.py` (`public()`), `quotes.py`, `render.py` | заменить на «the head commit», «the PR description», «the linked issue», «CI» |
| `` …: cites a review-standard rule but names no `example: <path:line>` … `` | `save.py` | добавить `example: <path:line>` вне файлов PR или `example: none` + precedent |
| `…: '<text>' is on N lines of <path> (…)` / `is not in <path> at head — closest: …` | `quotes.py` | сделать текст уникальным или указать номер строки |
| `…: N lines quoted from … — keep an excerpt to 30 lines or fewer` | `quotes.py` | сократить выдержку |
| `…: [[code:…]] must stand on its own line` / `is only allowed in explanation, fix and overview` | `quotes.py` | перенести на отдельную строку / в допустимое поле |
| `…: hand-typed code block starting … is not verbatim at head or base — …` | `quotes.py` | цитировать через `[[code:…]]`; команды, вывод, чужой код — в ```` ```text ```` |
| `…: unparsed [[code:…]]/[[at:…]] placeholder — …` | `quotes.py` | плейсхолдер должен открываться и закрываться `]]` на одной строке |
| `…: C… shares a place with … — set same_as …` | `save.py` (scorer) | указать `same_as` (id группы или `null`) |
| `…same_as: C… is itself marked same_as C… — point …` | `save.py` (scorer) | указать `same_as` на кандидата, которого оцениваешь (без своего `same_as`) |
| `not scored: … — every candidate of the batch exactly once` | `save.py` (scorer) | оценить всех кандидатов батча |
| `….precedent: required for a score of 50 or more — …` / `… does not exist at base …` | `save.py`, `quotes.check_precedent` | `null` или корректный `existing` (строка на base) / `deferred` (URL GitHub) |
| `earlier: missing … — every finding in your brief's list exactly once` | `save.py` (`earlier-findings`) | дать статус каждой прежней находке |
| `earlier: missing … — give every earlier finding a status (template in compose.md)` | `render.py` | дописать статус в `texts.json` |
| `#N is not an issue in <repo>` / `not an issue number` | `collect.py`, exit 1 | `--issue` указывает на PR или несуществующее issue (или в терминале введено не число) — дать номер issue или `--no-issue` |
| `` ERROR: `earlier-findings` runs only on an Update `` | `save.py`, exit 2 | агент `earlier-findings` вне update не запускается |
| `no score for C… — a scorer didn't save (re-launch it)` | `assemble.py`, exit 1 | перезапустить нужного scorer'а |
| `WARNING: out/earlier-findings.json is missing — …` | `assemble.py` (update) | перезапустить агента `earlier-findings` (шаг 4) до `texts.json` |
| `INVALID texts.json — …` (`findings.<id>.<key>: missing or empty`, `merge.<id>: …`, `earlier: exists only on an Update`) | `assemble.py --texts`, exit 1 | исправить `texts.json` |
| `fixes[i].old: found N times in … — must match exactly once` | `assemble.py --texts` | взять уникальный точный фрагмент |
| `INVALID findings.json — …` | `render.py`, exit 1 | исправить в `texts.json` (текст находки напрямую; describer/location — через `fixes`), затем `assemble.py --texts` и `render.py` |
| `hard-coded finding number CRn — …` | `render.py` | `[[ref:<id>]]`; не номер находки — в обратные кавычки |
| `[[ref:x]] — no finding or Process item has that id` | `render.py` | исправить id; на update прежние находки — номером текстом |
| `index_affected: N words — keep it to about 40` / `leave the verdict out — …` | `render.py` | сократить / убрать вердикт |
| `MARKDOWN PROBLEMS in …/report.md — …` | `render.py`, exit 1 | исправить текст в `texts.json` (на release-PR в `findings.json`), повторить |
| `Index: row NOT updated — …: no index table rows found — add the table by hand first` | `render.py` (отчёт записан) | передать пользователю; индекс руками не править |
| `Related: update-related.py not found — skipped …` / предупреждения `duplicate` | `render.py` | передать пользователю |
| `footer in the report changed since collect.py read it — re-run collect.py` | `render.py` (status), exit 1 | перезапустить `collect.py` |
| `…: no '---' + '_Analyzed' footer to insert the Update before` | `render.py` (update), exit 1 | отчёт повреждён — передать пользователю |
| `ERROR: report.md / findings.json missing — run assemble.py --texts and render.py first` | `briefs.py factcheck`, exit 1 | сначала шаг 6.2 |
| `SAFETY HITS — posting is blocked until the user decides:` | `prepare_comment.py`, exit 1 | процитировать пользователю, пусть решит; молча не вырезать |
| `Blocked: the PR comment's Markdown would render broken on GitHub. …` | hook перед `gh pr comment` | исправить отчёт, перенарезать, повторить |
| `Resource not accessible…` / ошибка авторизации при `gh pr comment` | `gh` | не повторять; сказать, что отчёт в `DOCS`, но не опубликован |

---

## 16. Известные ограничения и открытые вопросы

### 16.1 Неочевидное поведение кода

- **`gh pr checks` может остановить сбор.** «CI not read» бывает только при неразборчивом JSON; код выхода `gh pr checks`, отличный от 0/1/8, роняет `collect.py` с exit 1.
- **Повтор на том же head** удаляет только `findings.json` и `report.md`; `texts.json`, `compose.md`, `candidates.json` и `out/*` остаются, пока их не перезапишут следующие шаги.
- **Сбой индекса не валит рендер.** В full-режиме `render.py` завершается с 0 и печатает `Index: row NOT updated`; в update отсутствие строки индекса — только сообщение «add it by hand».
- **Hook проверяет только `gh pr comment --body-file …`.** Публикация через `--body …` им не проверяется и не блокируется.
- **Блок кода с подписью `// path:line`** сверяется только с head (без отката на base, как у блоков без подписи).
- **`render.py --check` / `--dry-run` в режиме `status`** ничего не проверяют: печатают `would set …` и выходят с 0.

### 16.2 Ограничения и открытые вопросы

Подтверждённое кодом:

- **Update-блок без «Checked and dismissed» и без QA.** Отсеянные кандидаты update попадают в блок только через «Review comments not taken up»; `edge_cases`, если их передать в `texts.json` на update, в блок не выводятся.
- **Update-блок не добавляет Process-пункты из `context.json`** (нет changeset, нет issue): они видны только через статусы прежних P.
- **Прежние CR без найденной строки в отчёте** при расчёте рекомендации на update считаются Bug (блокирующими).
- **Индекс не создаётся с нуля**: без существующей таблицы строка не добавляется.
- **Группа кандидатов > 8** уходит в один батч больше лимита (группа не разрывается).
- **CI:** `context.json` → `ci` хранит имена упавших и висящих джоб, но не cancelled/skipped.
- **Сканер утечек даёт ложные срабатывания**: шаблон `secret: <8+ символов>` срабатывает на текст вроде `secret: Barbican`; решение — за пользователем при публикации.

Из истории решений (`Claude outputs/review-and-comment-pr/review-pr-handoff.md`), где подтверждается кодом или набором:

- Вживую (с `gh`) не проверены: `curl` у `find-api-contract` (28.10). Проверены в `1377-v3`/`1377-v4`: `find-cross-boundary`, `pr-description`, ссылки на ревью через REST, вырезание цитат, чтение ответов у `earlier-findings` («Kept as is»), «мейнтейнер важнее», правило «пункт из обсуждения вне delta → not taken up». Ранее: распознавание собственных комментариев по старому заголовку и по Update-блоку в `collect.py` (поле `own_kind` пока ничем не используется); очистка delta от изменений base внутри `collect.py` (функция `delta_diff` проверена регрессионным набором); путь release-PR; правило шага 9 (follow-up отдельным вопросом).
- Разброс finders между прогонами: одна и та же проблема находится не в каждом прогоне. Пример 28.10: цикл 401 в #1377 (`1377-v1` нашёл find-diff-bugs, `1377-v2` на том же head — нет; бриф find-diff-bugs запрещает выходить за diff). Ответ — find-cross-boundary (баги на стыке с кодом вне PR); вживую ещё не проверен.
- Отложенная косметика: полный путь повторяется трижды на находку, нет кликабельных ссылок на строки; дубли QA Edge Cases (describer + сценарии по каждому Bug) системного решения не имеют; f-string без плейсхолдеров в `briefs.py:86`.
- Длинный комментарий: решено оставить (всё свёрнуто), страховка — `fit()` в `prepare_comment.py`.

