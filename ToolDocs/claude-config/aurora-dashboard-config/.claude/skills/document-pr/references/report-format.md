# Report format — document-pr

Read this at Step 6 (report) and Step 7 (index).

## Report template

Match the template: section order, headings and table columns are fixed.

Paths are full and repo-relative (e.g.
`packages/aurora/src/server/Network/routers/networksRouter.ts:42`) — never
shortened with `.../`; short paths are ambiguous.

Template:

```markdown
---
type: pr-report
date: <today, YYYY-MM-DD>
status: <merged | open | closed>
pr: [<number>]
issue: [<N from `Closes`/`Fixes`/`Resolves #N` in the PR body; omit the line if none or only a template placeholder like `#<epic-number>`>]
author: <author>
branch: <headRefName>
---
# PR #<number>: <title>

**Author:** <author> · **Status:** <open | draft | merged YYYY-MM-DD | closed YYYY-MM-DD> · **Created:** <YYYY-MM-DD>
**Branches:** `<headRefName>` → `<baseRefName>` (base `<baseRefOid short sha>`) · **Files:** <changedFiles> (+<additions>/-<deletions>)
**Link:** <url>
**CI:** <all green | failing: <job>, … | pending: <job>, … | no checks> (at `<headRefOid short sha>`)

> If `baseRefName` ≠ `main`, call that out explicitly here.

## What was done

<narrative — the story of the change, grouped by area, not a file list>

## How it is implemented

<walkthrough with verbatim excerpts and file:line citations, at <headRefOid>>

## What it affects

<impact/blast-radius findings from Step 4 — consumers found elsewhere in the
monorepo, contract changes, anything left inconsistent>

## Review

<if the `security-reviewer` agent was unavailable: "Security pass ran via the general-agent fallback.">

### Findings (confidence ≥75)

#### 1. <short title> — confidence <score> · severity <High | Medium>

<what is wrong, where (file:line), and what it leads to; excerpt if it helps>

**Suggested fix:** <one or two sentences>
**Why this score:** <the scorer's reason, covering both score and severity>
<if raised in the review discussion: who, where, what happened to it>

<or: "No High or Medium issues with confidence ≥75 found.">

### Rule violations (Low)

| Score | Finding | Rule | Suggested fix |
| --- | --- | --- | --- |
| <score> | <one-line description, file:line> | <the rule, quoted or named — e.g. Quick Reject "`PopupMenu` without `PopupMenuToggle`"> | <one line; add "expect pushback: <precedent>" when there is one> |

<confidence ≥75 with severity Low, highest score first; "None" if empty>

### Below the bar

| Score | Severity | Finding | Why this score |
| --- | --- | --- | --- |
| <score> | <High \| Medium \| Low; "—" below 50> | <one-line description, file:line> | <the scorer's reason> |

<every other scored issue, highest score first, down to 0; "None" if
nothing else was scored>

## Proposed follow-ups

- [ ] **<finding title>** — `<file:line>` → Review, finding <n>
- [ ] **Rule violations (Low): <n> items** → Review, "Rule violations (Low)"

<or: "None — no findings ≥75.">

---
Analyzed: <today's date, YYYY-MM-DD> · commit `<headRefOid short sha>`
```

## Index row

Maintain `<DOCS>/aurora-dashboard-kb/prs/README.md` as a lookup table:

```markdown
---
type: index
---
# PR reports

| PR | Date | Title | Affected | File |
| --- | --- | --- | --- | --- |
| [#1270](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1270) | 2026-09-03 → merged 2026-09-04 | fix(aurora): time doesn't match current timezone (#1236) | `formatSwiftDate` helper; Swift tables, sort comparators, `EditObjectMetadataModal`. Review: 1 finding (1 High) | [1270-time-doesnt-match-current-timezone.md](./1270-time-doesnt-match-current-timezone.md) |
```

If the file doesn't exist yet, create it with this header and one row.
Keep the full history — never trim old rows.

- **Date** — exactly one of: `<created> → merged <date>`,
  `<created> → closed <date>`, `<created> (open)`, `<created> (draft)`.
  Report updates go in the report's footer, not here.
- **Affected** — the touched surface only (procedures, routes, components,
  public exports), at most ~40 words, then `Review: <n> finding(s)
  (<count per severity>)`, e.g. `Review: 10 findings (1 Medium, 9 Low)`, or
  `Review: clean`. Rows written before severity existed keep their
  scores. Details live in the report.
- **Order** — newest PR on top by creation date (ties: higher number on
  top). Insert the row where it belongs, not always at the top: analyses
  don't happen in PR order.
- Escape any `|` inside a cell (code spans included) as `\|`.
- When a report's status changes (Step 1, "Existing report?"), update
  this row's Date cell too.
