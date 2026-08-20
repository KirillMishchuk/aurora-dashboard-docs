---
name: implement-plan
description: >-
  Build an aurora-dashboard implementation plan that already exists — from
  create-plan earlier in this conversation, from a previous session, or
  written by hand — via dev-executor, then a focused security pass. Use when
  the user has a plan and wants it built now. If the user wants both
  planning and building from scratch in one request and no plan exists yet,
  run create-plan first, then this skill on its output.
---

# Implement plan

Takes an existing plan as input and builds it. This is the execution half of
the planning/execution split — `dev-planner` and `dev-executor` already treat
the plan as a contract between them (see their own agent instructions); this
skill just owns the execution side of that contract so a plan can be
reviewed, edited, or handed off before anything gets written.

## Steps

1. **Get the plan.**
   - If one was just produced by `create-plan` earlier in this conversation,
     use it directly.
   - If the user pastes a plan or points at a file, read it.
   - If the user refers to a plan by task name/description rather than a
     path (e.g. "implement the ceph lifecycle plan from last week"), resolve
     the plans directory the same unambiguous way `create-plan` does —
     `PLANS_DIR="$(dirname "$(git rev-parse --show-toplevel)")/DOCS/plans"`
     — not a bare `../DOCS/plans` typed from wherever the shell happens to
     be, for the same case-insensitive-filesystem reason documented in
     `create-plan`. Check `$PLANS_DIR/README.md` for a matching row and read
     that file — don't make the user go find the path themselves.
   - If no plan exists yet and the user's request implies both planning and
     building ("plan and implement X", "build X, plan it first"), invoke
     `create-plan` first, then continue here with its output — don't ask the
     user to do that invocation themselves.
2. **Check the plan is actually ready to execute.** If it has open questions
   or unresolved ambiguity, stop and surface them to the user — don't
   execute against an incomplete plan.
3. **Confirm before writing.** Unless the user already explicitly approved
   this exact plan moments ago in this conversation (e.g. they just said
   "build it" right after seeing it), show a brief summary (step count,
   High-severity risks) and wait for go-ahead — this phase writes real files
   to the working tree, same as any other action with real side effects.
4. **Implement.** Launch the `dev-executor` agent (foreground) and pass it
   the full plan verbatim (overview, architecture context, risks, all
   implementation steps with file paths, testing plan, acceptance criteria).
   Instruct it to execute steps sequentially, follow existing code patterns,
   test as it goes, and ask the user if something conflicts with the plan or
   the codebase.
5. If the executor reports blockers or deviations, relay them to the user
   before continuing.
6. **Security check.** Launch the `security-reviewer` agent (foreground)
   scoped to just the files the executor modified/created. Ask for a
   focused pass on auth/authorization (tRPC procedure builders, permission
   checks), input validation, and data exposure — not a full audit.
7. If it reports Critical or High findings, surface them clearly and don't
   present the task as done until the user has seen them.
8. **Close the loop on the plan file.** If the plan came from a file under
   `$PLANS_DIR`, update its `**Status:**` line (`not implemented` →
   `implemented <date>`, or `partially implemented <date>` if there were
   deviations/skipped steps) and, in `$PLANS_DIR/README.md`, set that same
   value in the row's dedicated `Status` column only — leave `Risks` and
   `File` untouched. If an older row predates the `Status` column and only
   has `Date | Task | Risks | File`, add the column rather than overloading
   an existing one. Skip this whole step if the plan wasn't sourced from a
   file — nothing to update.

## Final report

Summarize: what was built, files changed/created, test results
(`pnpm typecheck`/`lint`/`test` status if the executor ran them), any
deviations from the plan, and the security check outcome.
