---
name: create-plan
description: >-
  Analyze aurora-dashboard's architecture for a task and write a detailed
  implementation plan — decisions, risks, steps, testing, acceptance
  criteria — to ../DOCS/plans/, without implementing anything. Use when the
  user wants to plan a feature, fix or change first and review the plan
  before building it, including a plan for a GitHub issue or PR, or for an
  item in DOCS/FOLLOW-UPS.md, whatever language the request is in (the plan
  itself is always written in English). Not for
  building an existing plan (implement-plan) or reviewing a PR
  (triple-review).
---

# Create plan

Read-only with respect to the codebase: this skill never touches
`aurora-dashboard/` source. It does write one deliverable — the plan itself
— to `DOCS/plans/` next to the repo (outside it; per the workspace `CLAUDE.md`,
working notes like this don't belong inside a repo whose files are destined
for upstream PRs). To build the resulting plan, use `implement-plan` —
either now or in a later session, unedited or after the user has revised it.

## Paths

Everything this skill reads or writes besides the code lives in the `SAP/`
folder that holds this repo: `DOCS/`, the repo's `CLAUDE.md` in the main
checkout, `local-mock-backend/`. Resolve them once, before step 1, from the
repo's common git dir:

```bash
MAIN_ROOT="$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")"
SAP_DIR="$(dirname "$MAIN_ROOT")"
DOCS_DIR="$SAP_DIR/DOCS"
[ -f "$DOCS_DIR/CLAUDE.md" ] || echo "DOCS not found at $DOCS_DIR"
```

Why not `--show-toplevel`: in a linked worktree (`.claude/worktrees/<name>`)
the toplevel's parent is `.claude/worktrees`, so `$(dirname toplevel)/DOCS`
points at a folder that doesn't exist — and because `.claude/` is
git-ignored, nothing would flag a plan written there. The common git dir is
always the main checkout's `.git`, from any worktree (`temp-sync` resolves
its paths the same way). And never type a bare `../DOCS`: from a
subdirectory on macOS's case-insensitive filesystem it can land in this
repo's own git-tracked `docs/`. If the check above fails, stop and tell the
user instead of writing anywhere else.

## Steps

1. **Get the task.** If the user invoked this without a task description,
   ask for one before proceeding.

   If the task refers to an item in `DOCS/FOLLOW-UPS.md` ("follow-up 42",
   "item 42"), extract just that item and pass its text to the planner as
   part of the task. Don't hand the planner the whole registry — it's large
   and only this one item matters:

   ```bash
   FU="$DOCS_DIR/FOLLOW-UPS.md"
   awk -v n=42 '$0 ~ "^### "n"\\." {p=1; print; next} p && /^(### |## )/ {exit} p' "$FU"
   ```

   If the task names a GitHub issue or PR (a number, a link, "the Copilot
   comments on #1331"), fetch it yourself and pass the text to the planner,
   so the plan answers what was actually written rather than a paraphrase:

   ```bash
   gh issue view <n> --json title,state,url,body,comments \
     --jq '{title, state, url, body, comments: [.comments[] | {author: .author.login, createdAt, body}]}'
   gh pr view <n> --json title,state,url,body,comments,reviews \
     --jq '{title, state, url, body, comments: [.comments[] | {author: .author.login, createdAt, body}], reviews: [.reviews[] | {author: .author.login, state, submittedAt, body}]}'
   gh api --method GET --paginate \
     repos/cobaltcore-dev/aurora-dashboard/pulls/<n>/comments \
     --jq '.[] | {path, line: (.line // .original_line), outdated: (.line == null), user: .user.login, created_at, in_reply_to_id, html_url, body}'
                                         # PR: inline review comments
   ```

   Use `--json`, not `--comments`: when the output isn't a terminal (and for
   Claude it never is), `gh … view --comments` prints only the comments and
   drops the body, so an issue without comments comes back empty.

   Pass each review comment with its `path`, `line`, author and thread link
   (`html_url` ends in `#discussion_r<id>`), so the plan can answer it thread
   by thread. `outdated: true` means the code under the comment has changed
   since; `line` is then the line in the commit it was written on. If an earlier round of the same review already has a plan (a
   file in `$DOCS_DIR/plans` with the same `pr`), tell the planner which one,
   so it doesn't answer the old threads again. Always call `gh api` with
   `--method GET`: that form can only read, and it's the only one allowed
   without a permission prompt. The number goes into the plan's `pr`/`issue`
   property (step 4).

2. **Check KB freshness.** Before launching the planner, check how far the
   knowledge base lags behind `main`. Read the pinned commit from
   `$DOCS_DIR/aurora-dashboard-kb/README.md` and run `git log --oneline <pin>..origin/main -- packages/ apps/` (local
   only, no fetch needed). Compare against `origin/main`, not `HEAD`: the KB
   tracks `main`, and your own branch commits aren't KB lag.

   A handful of commits isn't worth mentioning — use judgment on what counts
   as "far behind." If it is far behind, the planner would otherwise build on
   an outdated picture of the architecture, so tell it in the launch prompt
   (step 3): "The KB is N commits behind origin/main in packages/ and apps/ —
   verify anything you take from it against the code." Also note it in the
   final report (step 7) so the user can judge whether to update the KB first
   (the workspace `CLAUDE.md` says a lagging KB should be flagged, not
   silently used as-is).

3. **Plan.** Launch the `dev-planner` agent (foreground) with the task
   description. `dev-planner` does its own architecture analysis (it has
   Read/Bash/Grep — no need to pre-fetch files for it); just make sure it
   knows this is aurora-dashboard (pnpm/Turborepo monorepo, Fastify + tRPC
   BFF, React 19 client) so it grounds itself via `CLAUDE.md` and the KB per
   its own step 0. Give it these as absolute paths — `$MAIN_ROOT/CLAUDE.md`,
   `$DOCS_DIR/aurora-dashboard-kb/`, `$SAP_DIR/local-mock-backend/` — since
   in a worktree the repo has neither `CLAUDE.md` (git-ignored) nor
   `../DOCS`. Instruct it to follow its own plan structure (Overview,
   Decisions, Architecture Analysis, Potential Problems & Mitigations,
   Prerequisites, Implementation Steps, Testing Plan, Acceptance Criteria,
   Open Questions, Proposed follow-ups).

   **Decisions loop.** `dev-planner` can't ask the user anything (subagents
   don't get `AskUserQuestion`), so you relay. If it returns
   `## Decisions needed` instead of a plan:
   1. Ask the user those questions with `AskUserQuestion` — keep the
      planner's options and mark its recommendation. The tool takes at most
      4 questions per call and 2–4 options per question: ask in batches of
      4, and if a decision has more than 4 options, keep the recommended one
      and the 3 most distinct (the user can still answer "Other").
   2. Continue the **same** planner with `SendMessage` (its agent ID from the
      launch result; if `SendMessage` isn't loaded yet, load it with
      `ToolSearch` first), passing the answers. Don't launch a new one while
      the old one can be continued — a new one loses the code analysis and
      redoes it. Only if it can't be continued, launch a new planner with the
      task, the previous `## Decisions needed` block and the answers, and say
      in the report that the analysis was redone.
   3. Repeat until it returns the full plan.

   **Review.** A planner checks its own plan with the author's eyes, and
   contradictions between distant sections or misremembered API details
   slip through. So when the plan has 8 or more implementation steps, or
   depends on how an OpenStack service behaves (endpoints, microversions,
   pagination, allowed states), or the user asks for it, launch the
   `plan-reviewer` agent (foreground). Give it only the full plan text and
   the absolute paths — repo root `$MAIN_ROOT`, `$MAIN_ROOT/CLAUDE.md`,
   `$DOCS_DIR/aurora-dashboard-kb/` — not the planner's reasoning: its
   value is a fresh look. If it reports findings:
   1. Findings marked as coming from a user decision: ask the user with
      `AskUserQuestion` whether to change that decision (keep the batching
      rule above). Don't change a user decision on the reviewer's word.
   2. Send the other findings, plus the user's answers, to the **same**
      planner with `SendMessage`: fix the plan, return the full revised plan
      and one line per finding — fixed, or not fixed and why.
   3. One round only: don't run the reviewer again. Findings the planner
      didn't fix go into the plan's Open Questions.

   Keep the counts for the plan header (step 4). If the review didn't run,
   leave that line out.

4. **Write the plan file** into `PLANS_DIR="$DOCS_DIR/plans"` (see Paths —
   an absolute path, never a relative `../DOCS/plans`).
   Record what code the plan was built on: `git rev-parse --abbrev-ref HEAD`
   and `git rev-parse --short HEAD`; if `git status --porcelain` shows
   changes, add `+ uncommitted changes`.
   File name: `<YYYY-MM-DD>-<kebab-slug-of-task>.md`, e.g.
   `2026-07-23-ceph-lifecycle-policies-endpoint.md`. The plan is written in
   English, whatever language the conversation is in — ask `dev-planner` for
   English output. Content: dev-planner's plan verbatim under a short header:

   ```markdown
   ---
   type: plan
   date: <today, YYYY-MM-DD>
   status: not-implemented
   pr: [<number>]        # see below; omit the line if there is none
   issue: [<number>]     # see below; omit the line if there is none
   ---
   # Plan: <short task title>

   **Date:** <today, YYYY-MM-DD> · **Status:** not implemented
   **Base:** `<branch>` @ `<short-sha>`[ + uncommitted changes]
   **Reviewed:** <N> findings, <M> fixed   # only if the review ran

   <dev-planner's full plan output, unchanged>
   ```

   `pr`/`issue` link the plan to the other notes about the same PR or issue
   (the vault's "Related" blocks and Bases are built from them). Take numbers
   only from what the task or conversation states explicitly — "PR #1178",
   "issue 1004", a GitHub link, "epic #1327"; several go in one list, e.g.
   `issue: [1321, 1323, 1325]`. Don't infer them from the branch name or from
   issues the plan merely mentions: a wrong link is worse than none, and the
   field can be added later when a PR exists.

   If the planner concluded that no code should change — its Implementation
   Steps are empty because every finding was rejected or deferred to
   follow-ups — the result is an analysis, not a plan: write
   `status: analysis` and `**Status:** analysis` instead, so `implement-plan`
   isn't pointed at a file with nothing to build.

5. **Update the index.** Maintain `$PLANS_DIR/README.md` as a lookup
   table, newest first — create it with this header if it doesn't exist.
   If it exists, keep its current format exactly (frontmatter, notes above
   the table, separator style) — the header below is only for a new file —
   and insert the new row directly below the table's separator line. `Status` is its
   own column, always exactly `not implemented` at creation time (`analysis`
   for an analysis, see step 4) — don't
   fold it into `Risks` or `File`, that's ambiguous for whatever updates it
   later (see `implement-plan`'s step 8). Keep the row scannable — the index
   is read to find a plan, not to learn it: `Task` is one sentence on what and
   why (about 150 characters at most) plus the step count; `Risks` is the
   count by severity plus the single most important one in a few words (e.g.
   `1 High: notFound() only from loader`). Everything else is in the plan.
   Write the row in English, whatever
   language the conversation is in, and escape any `|` inside a cell —
   including inside code spans — as `\|`, otherwise it splits the column:

   ```markdown
   # Plans

   | Date       | Task                                    | Risks  | Status          | File                                                                                               |
   | ---------- | --------------------------------------- | ------ | --------------- | -------------------------------------------------------------------------------------------------- |
   | 2026-07-23 | Ceph bucket lifecycle policies endpoint | 1 High | not implemented | [2026-07-23-ceph-lifecycle-policies-endpoint.md](./2026-07-23-ceph-lifecycle-policies-endpoint.md) |
   ```

   Then run `python3 "$(dirname "$PLANS_DIR")/tools/update-related.py"` —
   always, not only when the plan has `pr`/`issue`: `DOCS/CLAUDE.md` asks for
   it after adding any note, and it only regenerates auto blocks and file
   lists. Skip silently if the script is missing.

6. **File follow-ups.** If the plan has a `## Proposed follow-ups`
   section, these are things the planner found but deliberately left out.
   `DOCS/FOLLOW-UPS.md` is the only place deferred work is recorded, and the
   user decides what goes in, so:

   1. Read only the registry's summary table, not the whole file:
      `awk '/^## Summary/{p=1; print; next} p && /^## /{exit} p' "$FU"`.
      For each candidate, check whether an item on the same thing already
      exists — if so, it's not a new follow-up, just a reference to item N.
      When a one-line topic isn't enough to tell, read that one item in full
      (the same `awk` as in step 1) rather than the whole registry. If a
      candidate only partly overlaps an existing item, file just the new
      part and reference the existing item for the rest.
   2. Ask the user with `AskUserQuestion` (multi-select) which candidates to
      file — title plus one line each. The tool takes at most 4 options per
      question; with more candidates, split them across several
      multi-select questions of up to 4.
   3. File each approved one. Take the number at write time —
      `grep -oE '^### [0-9]+' "$FU" | awk '{print $2}' | sort -n | tail -1`,
      plus one. Numbers are permanent and never reused, so never guess one
      or pick it earlier. Write the item in English, in the registry's
      format, at the end of the area section it fits (`## A.` …) or in a
      new lettered section if none does: `### N. <title>`, then
      **Where:**, **What:**, **How to fix:**, **Why not done right away:**,
      **Source:** `plan [<file>](./plans/<file>)`, **Status:** open. Add its
      row `| N | <topic> | <area> | open |` to the Summary table next to the
      rows of the same area, and set the `Updated:` line at the end of the
      file to today's date.
   4. In the plan file, replace the `## Proposed follow-ups` section with
      `## Follow-ups` holding references only —
      `- [FOLLOW-UPS.md → item N](../FOLLOW-UPS.md) — <title>` — and one
      line `Not filed: <title>` per rejected candidate. The registry keeps
      the only copy of the text, so two copies never drift apart.

   If the task itself was an existing item, remind the user in the report
   to set it to `done` (with the PR link) once the PR is merged.

7. **Report.** Tell the user the file path and, if the review ran, what it
   found and what was fixed. Give a short inline summary
   (step count, any High-severity risks) so they can decide whether to open
   it — don't necessarily paste the whole plan into the conversation if it's
   long, the file is now the source of truth. If the plan has open
   questions, surface them prominently regardless — don't let those get
   buried in a file the user might not open right away. If step 2's
   KB-staleness check found the KB lagging far behind, mention that here too
   — a plan built on outdated architectural understanding is worth a caveat
   even if everything else about it looks solid.
