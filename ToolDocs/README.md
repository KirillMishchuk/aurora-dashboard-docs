# ToolDocs

Хранилище (Obsidian vault) для заметок про инструменты, которыми Кирилл пользуется в работе — справочник, не привязанный к конкретному проекту (в отличие от `../aurora-dashboard-kb`, которая целиком про aurora-dashboard).

## Содержимое

| Папка | Что внутри |
| --- | --- |
| [`ClaudeDocs/`](./ClaudeDocs/) | Заметки про Claude Code: [claude-code-commands.md](./ClaudeDocs/claude-code-commands.md) (слэш-команды), [claude-code-plugins.md](./ClaudeDocs/claude-code-plugins.md) (плагины), [claude-code-skills.md](./ClaudeDocs/claude-code-skills.md) (скиллы) |
| [`claude-config/`](./claude-config/) | Конфиги Claude Code для репозитория aurora-dashboard — две копии: [`aurora-dashboard-config/`](./claude-config/aurora-dashboard-config/) (локальная сессия) и [`aurora-dashboard-config-remote/`](./claude-config/aurora-dashboard-config-remote/) (облачная сессия). Каждая — `CLAUDE.md` + `.claude/agents`, `.claude/skills`, `.claude/docs` + `docs/` (архитектурный обзор, semantic release). Не путать с `.claude/`/`CLAUDE.md` внутри самого `aurora-dashboard/` — те версии живут в репозитории и уходят в upstream-PR; эти — личные, вынесены сюда, чтобы не попасть в коммит |
| [`GitDocs/`](./GitDocs/) | Практический справочник по командам git: [git-commands.md](./GitDocs/git-commands.md) (setup, базовая работа, ветки, rebase, синхронизация с remote + аутентификация по HTTPS/PAT, история, отмена изменений, stash, теги, диагностика конфликтов) |

По мере появления заметок про другие инструменты — новая подпапка на верхнем уровне хранилища и строка в таблице выше.
