---
name: create-plan
description: >-
  Analyze aurora-dashboard's architecture for a task and write a detailed
  implementation plan — decisions, risks, steps, testing, acceptance
  criteria — to ../DOCS/plans/, without implementing anything. Two modes:
  a new plan for an issue, a follow-up item or someone else's PR; or a
  round of fixes for the user's own PR from its review (review-and-comment-pr
  report, triple-review, Copilot or reviewer comments), appended to that
  PR's fixes file. The plan is always written in English. Not for building
  a plan (implement-plan) or reviewing code (review-and-comment-pr,
  triple-review).
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
checkout, `local-mock-backend/`. The script resolves them from the repo's
common git dir and `collect` prints them (`MAIN_ROOT`, `SAP_DIR`,
`DOCS_DIR`). The common git dir is always the main checkout's `.git`, from
any worktree; a worktree's toplevel isn't (its parent is
`.claude/worktrees`), and a bare `../DOCS` typed from a subdirectory can
land in the repo's own git-tracked `docs/` on macOS. So never build these
paths by hand. If the script says DOCS wasn't found, stop and tell the user
instead of writing anywhere else.

The mechanical work is done by `scripts/plan.py` (`collect`, `save`,
`write`, `followups`); run it from the repo root. You launch the agents,
ask the user, and write the few lines of wording the script asks for.

## Steps

1. **Collect the task.** If the user invoked this without a task, ask for
   one first. Then:

   ```bash
   python3 .claude/skills/create-plan/scripts/plan.py collect <what the user gave>
   ```

   — an issue or PR number or link, or `follow-up <n>`. A task given in
   words: `plan.py collect --text --label <short-slug> <<'TASK'` … `TASK`.

   It writes the task for the planner to `<run folder>/task.md`, so the plan
   answers what was written rather than a paraphrase: the issue with its
   comments and its parent epic (labelled as context — the plan covers the
   issue only); a follow-up item alone, not the whole registry; or the PR
   with its description, closed issues and discussion. It downloads the
   images in that text into `<run folder>/images/` (inside the repo, so
   reading them needs no permission prompt) and lists them in `task.md`
   with the sentence each came from. It runs `git fetch origin main` and
   measures how far the working copy and the KB lag behind it. Read its
   summary, not the files it wrote.

   The mode:

   - **A — a new plan**: an issue, a follow-up item, a task in words, or
     someone else's PR (its code is fetched to `origin/pr/<n>` too).
   - **B — a round of fixes for the user's own PR** (author = `gh api
     user`). It fetches the PR head to `origin/pr/<n>` (only that
     remote-tracking ref changes; the working tree and branch don't), writes
     the GitHub comments, reviews and inline threads (path, line, author,
     link, outdated) to `<run folder>/github.md`, lists the review reports in
     `DOCS` (`review-and-comment-pr`, `triple-review`), and looks for the
     original plan (`pr:`, then `issue:` from the PR's closing issues) and
     the PR's fixes file with earlier rounds.

   Exit codes: **0** — go on with step 2; **3** — it couldn't tell whose
   PR it is (no `gh`): ask the user and re-run with `--mine` or
   `--not-mine`; **1** — it couldn't collect (GitHub error, no such issue,
   DOCS missing): pass the message on and stop; **2** — wrong arguments.

2. **Ask what `collect` lists** under `Ask the user:`, with
   `AskUserQuestion`:

   - *Code lag* (mode A): the working copy is behind `origin/main` — plan on
     the current code (step 4 records the lag in **Base**), or stop so they
     can update first.
   - *Reviews* (mode B, multi-select): which to plan from; the user may name
     another file.
   - *Original plan* (mode B, none or several found): which one, or none —
     it goes to `--original-plan` in step 4.

   Also from the summary: if `git fetch` failed, or the KB lags far behind
   `origin/main` (a handful of commits isn't worth mentioning — use
   judgment), tell the planner in step 3 ("The KB is N commits behind
   origin/main in packages/ and apps/ — verify anything you take from it
   against the code") and say so in the report (step 7): the workspace
   `CLAUDE.md` says a lagging KB should be flagged, not silently used as-is.

3. **Plan.** Launch the `dev-planner` agent (foreground). Give it the task
   file, `<run folder>/task.md` — it reads it itself, so don't paste or
   summarize it. `dev-planner` does its own architecture analysis (it has
   Read/Bash/Grep — no need to pre-fetch files for it); just make sure it
   knows this is aurora-dashboard (pnpm/Turborepo monorepo, Fastify + tRPC
   BFF, React 19 client) so it grounds itself via `CLAUDE.md` and the KB per
   its own step 0. Give it these as absolute paths, from `collect`'s
   `Paths:` line — `$MAIN_ROOT/CLAUDE.md`, `$DOCS_DIR/aurora-dashboard-kb/`,
   `$SAP_DIR/local-mock-backend/` — since in a worktree the repo has
   neither `CLAUDE.md` (git-ignored) nor `../DOCS`. Instruct it to follow
   its own plan structure (Overview, Decisions, Architecture Analysis,
   Potential Problems & Mitigations, Prerequisites, Implementation Steps,
   Testing Plan, Acceptance Criteria, Open Questions, Proposed follow-ups),
   in English, and paste the save command from `collect`'s summary into the
   prompt: the planner saves the plan with it (the script checks the
   structure, the paths and that nothing follows the last section, and
   writes `<run folder>/plan.md`) and replies with one `saved …` line.
   Don't read `plan.md` yourself — step 4 prints what the report needs.

   In mode B, also give it the paths of the chosen reviews (`github.md` and
   the `DOCS` reports from `collect`'s list), of the original plan and of
   the fixes file with earlier rounds (if any) — so it doesn't answer the
   same findings again — and the PR ref `origin/pr/<n>`, and tell it: the PR's code is the starting point — read
   it from that ref, not from the working tree; answer every finding
   (fix, or reject with the reason), and keep scope to the findings.

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
   3. Repeat until it replies with the `saved …` line.

   **Review.** A planner checks its own plan with the author's eyes, and
   contradictions between distant sections or misremembered API details
   slip through. So when the plan has 8 or more implementation steps, or
   depends on how an OpenStack service behaves (endpoints, microversions,
   pagination, allowed states), or the user asks for it, launch the
   `plan-reviewer` agent (foreground). Give it only the plan's path,
   `<run folder>/plan.md`, and the absolute paths — repo root `$MAIN_ROOT`, `$MAIN_ROOT/CLAUDE.md`,
   `$DOCS_DIR/aurora-dashboard-kb/` — not the planner's reasoning: its
   value is a fresh look. If it reports findings:
   1. Findings marked as coming from a user decision: ask the user with
      `AskUserQuestion` whether to change that decision (keep the batching
      rule above). Don't change a user decision on the reviewer's word.
   2. Send the other findings, plus the user's answers, to the **same**
      planner with `SendMessage`: fix the plan, save it again with the same
      command, and reply with the `saved …` line and one line per finding —
      fixed, or not fixed and why.
   3. One round only: don't run the reviewer again. Findings the planner
      didn't fix go into the plan's Open Questions.

   Keep the counts for `--reviewed` (step 4). If the review didn't run,
   leave it out.

4. **Write the plan file, the index row and Related.**

   ```bash
   python3 .claude/skills/create-plan/scripts/plan.py write --run <run folder> \
     --title "<short task title>" --slug <kebab-slug-of-task> \
     [--issue <n> …] [--pr <n> …] [--reviewed <N>/<M>] \
     --task "<index Task>" --top-risk "<the most important risk, a few words>"
   ```

   It checks `plan.md` again and writes `$DOCS_DIR/plans/<today>-<slug>.md`:
   frontmatter, `# Plan: <title>`, `**Date:** · **Status:**`, `**Base:**`
   from git (branch @ short SHA, `+ uncommitted changes`,
   `· N commits behind origin/main`), `**Reviewed:**` only with
   `--reviewed`, then the plan verbatim. A plan without implementation
   steps is an analysis, not a plan: it gets `status: analysis`, so
   `implement-plan` isn't pointed at a file with nothing to build. Then it
   adds the row to `$DOCS_DIR/plans/README.md` (newest first, the step and
   risk counts added to your text), runs `update-related.py`, and prints
   the summary for the report and the follow-up candidates. Exit 1 lists
   the problems: one in `plan.md` goes to the planner (`SendMessage`), the
   rest are in your arguments. A taken file name — pick another slug;
   `--overwrite` only if the user asked to replace that plan.

   - `--title`, `--slug`: e.g. `Ceph bucket lifecycle policies endpoint`,
     `ceph-lifecycle-policies-endpoint`.
   - `--task`: one sentence in English on what and why, about 150
     characters — the index is read to find a plan, not to learn it.
     `--top-risk`: the single most important risk in a few words (e.g.
     `notFound() only from loader`).
   - `issue`/`pr` link the plan to the other notes about the same PR or
     issue (the vault's "Related" blocks and Bases are built from them).
     They default to what `collect` found — the issue, the PR, the PR's
     closing issues. Add `--issue`/`--pr` (they replace the defaults) only
     for numbers the user or task states explicitly — "PR #1178", "issue
     1004", a GitHub link, "epic #1327". Don't infer them from the branch
     name or from issues the plan merely mentions: a wrong link is worse
     than none, and the field can be added later when a PR exists.

   **Mode B** — instead of `--title`/`--slug`: `--sources "<the chosen
   reviews, e.g. review-and-comment-pr report, Copilot>"`; on round 1 also
   `--original-plan <file name, or none>` when `collect` didn't find exactly
   one. The PR number, title and closing issues come from `collect`. The
   script writes to the PR's
   one fixes file, `<date of the first round>-pr-<n>-fixes.md`: creates it
   (`# Fixes: PR #<n> — <title>`, `**Original plan:**`, `**Status:**`) or
   appends `## Round <k> — <today> · <sources>` before the `Related` block,
   with `**Base:** origin/pr/<n> @ <sha>` and the plan one heading level
   deeper; sets `status`/`**Status:**` for round k, adds or updates the
   file's single index row (`PR #<n> fixes, round <k>: …`), and adds
   `pr: [<n>]` to the original plan. Earlier rounds aren't touched.

5. **Index and Related** — done by `write`. If its `Index:` or `Related:`
   line shows a warning, pass it on in the report; don't edit the index by
   hand.

6. **File follow-ups.** If `write` listed follow-up candidates — things the
   planner found but deliberately left out. `DOCS/FOLLOW-UPS.md` is the
   only place deferred work is recorded, and the user decides what goes in,
   so:

   1. `write` printed the registry's summary table and its sections. For
      each candidate, check whether an item on the same thing already exists
      — if so, it's not a new follow-up, just a reference to item N. When a
      one-line topic isn't enough to tell, read that one item in full —
      `awk -v n=<N> '$0 ~ "^### "n"\\." {p=1; print; next} p && /^(### |## )/ {exit} p' "$DOCS_DIR/FOLLOW-UPS.md"`
      — rather than the whole registry. If a candidate only
      partly overlaps an item, say so in the question below.
   2. Ask the user with `AskUserQuestion` (multi-select) which candidates to
      file — title plus one line each. The tool takes at most 4 options per
      question; with more candidates, split them across several
      multi-select questions of up to 4.
   3. Run, with every candidate (numbered as `write` printed them) in
      exactly one option:

      ```bash
      python3 .claude/skills/create-plan/scripts/plan.py followups --run <run folder> \
        --file 1=K [--topic "1=<short topic>"] --ref 2=43 --skip 3
      ```

      `--file <i>=<letter>` — file it at the end of that area section
      (`<i>=new:<area name>` for a new lettered section); `--topic` — the
      summary table's short topic, if the title is long; `--ref <i>=<N>` —
      already item N; `--skip <i>` — the user didn't approve it. The script
      takes the next free numbers (never reused), writes each item in the
      registry's format, adds its summary row next to the same area, sets
      `Updated:`, and replaces the plan's `Proposed follow-ups` with
      `Follow-ups` holding links only (in mode B, in the new round). Don't
      edit the registry or the plan's section by hand.

   If the task itself was an existing item (`collect` prints a note), remind
   the user in the report to set it to `done` (with the PR link) once the PR
   is merged.

7. **Report.** Tell the user the file path and, if the review ran, what it
   found and what was fixed. Give a short inline summary from `write`'s
   output (step count, any High-severity risks) so they can decide whether
   to open it — don't necessarily paste the whole plan into the conversation if it's
   long, the file is now the source of truth. If the plan has open
   questions, surface them prominently regardless — don't let those get
   buried in a file the user might not open right away. If step 2
   found the KB lagging far behind, or the code lagging `origin/main` (the
   user chose to plan on it anyway), or `git fetch` failed, mention that here too
   — a plan built on outdated architectural understanding is worth a caveat
   even if everything else about it looks solid.
