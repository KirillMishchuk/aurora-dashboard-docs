---
type: index
---
# Home

Current state of the work, built live from note properties (Obsidian Bases). Map of folders: [README.md](./README.md) · agent rules: [CLAUDE.md](./CLAUDE.md) · deferred work: [FOLLOW-UPS.md](./FOLLOW-UPS.md) · full boards: [Plans](./bases/Plans.base), [PR timeline](./bases/PR%20timeline.base).

## Open plans

```base
filters:
  and:
    - note.type == "plan"
    - '!file.inFolder("templates")'
    - or:
        - note.status == "not-implemented"
        - note.status == "in-progress"
        - note.status == "partially-implemented"
        - note.status == "analysis"
views:
  - type: table
    name: Open plans
    order:
      - file.name
      - note.date
      - note.status
      - note.pr
      - note.issue
    sort:
      - property: note.date
        direction: DESC
```

## Open PRs

```base
filters:
  and:
    - note.type == "pr-report"
    - note.status == "open"
views:
  - type: table
    name: Open PR reports
    order:
      - file.name
      - note.date
      - note.pr
      - note.branch
    sort:
      - property: note.date
        direction: DESC
```

## Recently changed

```base
filters:
  and:
    - file.ext == "md"
    - '!file.inFolder("templates")'
    - '!file.inFolder("ToolDocs/claude-config")'
    - '!file.inFolder("ai-dev-tasks")'
views:
  - type: table
    name: Recently changed
    limit: 15
    order:
      - file.name
      - note.type
      - file.mtime
      - file.folder
    sort:
      - property: file.mtime
        direction: DESC
```
