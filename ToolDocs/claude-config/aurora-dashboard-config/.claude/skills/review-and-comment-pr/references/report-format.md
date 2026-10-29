# Report format — review-and-comment-pr

## Contents

- Report template (full report: Verdict, Required Changes, Improvements, Review comments not taken up, Solution Overview, QA Test Plan, Checked and dismissed, footer)
- Update block
- Index row

> Reference only: the full report, the Update block and the index row are
> implemented in `scripts/render.py`. Keep the two in sync when the
> format changes.

The sections below describe the template and the index row.

## Report template

**Structure and wording are fixed** — match the template exactly: the
section order, the headings and their emoji (`### ⚖️ Verdict`,
`### 🔧 Required Changes`, `### 💡 Improvements`), the `<details>` folds,
the Verdict line with Recommendation and Confidence together, then the
summary as plain text (no blockquote), the
per-table "Explanation & Fix" fold, and the five-level severity markers
(🔴 Critical · 🟠 Major · 🟡 Moderate · 🟢 Low · ⚪ Trivial). The only
emoji that carries meaning on the recommendation line is its colour: 🔴
Request Changes, 🟡 Approve with changes / with process to-dos, 🟢 Approve. Severity markers in the tables are the only other
colour. Don't add gates strips, score columns, or decorative emoji on the
other headings.

Paths are full and repo-relative (e.g.
`packages/aurora/src/server/Network/routers/networksRouter.ts:42`) — never
shortened with `.../`: the comment is public, and short paths are
ambiguous and not clickable.

Template:

```markdown
---
type: pr-report
date: <today, YYYY-MM-DD>
status: <merged | open | closed>
pr: [<number>]
issue: [<issues the PR body links (Closes/Fixes/Resolves/Part of/#N); empty if it links none — an issue the user supplied doesn't go here>]
author: <author>
branch: <headRefName>
---

# PR #<number>: <title>

**Author:** <author> · **Status:** <draft | open | merged YYYY-MM-DD | closed YYYY-MM-DD> · **Base:** `<baseRefName>` ← `<headRefName>`
**Size:** <changedFiles> files, +<additions> / −<deletions> · **Created:** <YYYY-MM-DD> · [View on GitHub](url)

> If `baseRefName` ≠ `main`, call that out explicitly on its own line here.

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

_Reviewed at head [`<short sha>`](<PR url>/commits/<headRefOid>) · base `<baseRefName>` at `<baseRefOid short>` · <collect time, YYYY-MM-DD HH:MM UTC>_

### ⚖️ &nbsp; Verdict

Recommendation: **<🔴 Request Changes | 🟡 Approve with changes | 🟡 Approve with process to-dos | 🟢 Approve with nits | 🟢 Approve>** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **<High | Medium | Low>**

- **Must fix before merge** (<scope, if any>): <Bug / Security Required Changes without a precedent tag>
- **Team call** (convention, existing pattern or deferred by a maintainer): <the other Required Changes>
- **Process:** <P items>

<2–4 sentence summary: the overall shape, the one or two things that matter, what clears it. If CI/security fell back or acceptance couldn't be verified, that belongs in this summary.>

### 🔧 &nbsp; Required Changes

| #   | Severity      | Category   | Precedent                              | Issue      | Location              |
| --- | ------------- | ---------- | -------------------------------------- | ---------- | --------------------- |
| CR1 | <🟡 Moderate> | <Category> | <— \| existing code \| [deferred](url)> | <one line> | `<file:line>`         |
| P1  | —             | Process    | —                                      | <one line> | <PR state \| PR body> |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — <title>** · <Category> · `<file:line>`
<what's wrong, where, what it leads to; if raised in review discussion, say who/where/what happened>
<_Precedent:_ line from `precedent`, if any>
_Fix:_ <one or two sentences; code block only when it clarifies>

**P2 — <title>** · Process · <where>
<why it matters>
_Fix:_ <one or two sentences>

</details>

<if the section is empty: write "None." and omit the fold>

### 💡 &nbsp; Improvements

| #   | Severity | Category   | Precedent   | Issue      | Location      |
| --- | -------- | ---------- | ----------- | ---------- | ------------- |
| I1  | <🟢 Low> | <Category> | <— \| …>    | <one line> | `<file:line>` |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — <title>** · <Category> · `<file:line>`
<rule or reason>
<_Precedent:_ line, if any>
_Fix:_ <one or two sentences>

</details>

<if the section is empty: write "None." and omit the fold>

### 🗨️ &nbsp; Review comments not taken up

<only if a dismissed candidate cites a review comment (r<id> / issuecomment-<id>) — render.py builds it>

| Raised by | Claim | Why not a finding |
| --------- | ----- | ----------------- |
| <author> [r<id>](<url>) | <candidate claim> | <scorer's reason> |

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

<narrative — the story of the change, grouped by area, not a file list>

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

<walkthrough with verbatim excerpts and file:line citations, at <headRefOid>>

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

<impact/blast-radius findings from Step 4 — consumers found elsewhere in the
monorepo, contract changes, anything left inconsistent>

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

<numbered happy-path walkthrough from Step 4>

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

<bulleted edge cases from Step 4, each with file:line where it comes from a specific branch>

</details>

---

## Checked and dismissed

<KB only, never posted; only if a candidate scored below 50 — render.py builds it>

<details>
<summary><strong>Candidates scored below 50 (<n>)</strong></summary>

| Score | Candidate | Location | Why |
| ----- | --------- | -------- | --- |
| <score> | <claim> | <location> | <scorer's reason> |

</details>

---

_Analyzed <today, YYYY-MM-DD> · commit `<headRefOid short sha>` · <provenance: "read-only"; add any of "CI not read", "review threads not read", "acceptance graded against #N supplied by the reviewer", "<agent> fallback used" that applied> · skill: review-and-comment-pr_
```

On an **Update** (Step 2, mode `update`), keep the existing report and
append the Update block described there, reusing these same Required
Changes / Improvements tables and severity markers for the delta's
findings. render.py builds it: Verdict, earlier findings by status,
Required Changes / Improvements, Review comments not taken up, What
changed — no QA Test Plan and no Checked and dismissed.

## Index row

Maintain `<DOCS>/aurora-dashboard-kb/prs/README.md` as a lookup table:

```markdown
---
type: index
---

# PR reports

| PR                                                                    | Date                           | Title                                                    | Affected                                                                                                                                               | File                                                                                       |
| --------------------------------------------------------------------- | ------------------------------ | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| [#1270](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1270) | 2026-09-03 → merged 2026-09-04 | fix(aurora): time doesn't match current timezone (#1236) | `formatSwiftDate` helper; Swift tables, sort comparators, `EditObjectMetadataModal`. Verdict: Request Changes — 1 Required Change (🟡), 2 Improvements | [1270-time-doesnt-match-current-timezone.md](./1270-time-doesnt-match-current-timezone.md) |
```

render.py doesn't create the file or the table: with no rows yet it stops
("no index table rows found") — add this header and table by hand first.
Keep the full history — never trim old rows.

- **Date** — exactly one of: `<created> → merged <date>`,
  `<created> → closed <date>`, `<created> (open)`, `<created> (draft)`.
  Report updates go in the report's footer, not here.
- **Affected** — the touched surface only (procedures, routes, components,
  public exports), at most ~40 words, then the verdict and finding counts:
  `Verdict: <Request Changes | Approve with changes | Approve with process to-dos | Approve> — <n> Required Change(s) (<severity
markers>), <m> Improvement(s)`, or `Verdict: Approve — clean`. Process
  items add ` + <n> process` to the markers; "Approve with nits" is
  written as `Approve`. Rows
  written under the old scheme keep their wording. Details live in the
  report.
  After an Update, render.py appends what the latest Update block added:
  `· Update <date> (`<short sha>`): <recommendation> — <n> Required Change(s) (<markers>),
  <m> Improvement(s)` (or `no new findings`), then `; <k> earlier fixed`;
  the next Update replaces
  that tail, a full re-run rewrites the whole row.
- **Order** — newest PR on top by creation date (ties: higher number on
  top). Insert the row where it belongs, not always at the top: analyses
  don't happen in PR order.
- Escape any `|` inside a cell (code spans included) as `\|`.
- When a report's status changes (Step 2, mode `status`), update
  this row's Date cell too.
