---
name: create-plan
description: >-
  Analyze aurora-dashboard's architecture for a given task and produce a
  detailed implementation plan (risks, steps, testing, acceptance criteria)
  WITHOUT implementing anything, saved as a markdown file in ../DOCS/plans/
  for review. Use when the user wants to plan a feature or change first and
  review the plan — in the conversation or later as a file — before deciding
  whether to build it.
---

# Create plan

Read-only with respect to the codebase: this skill never touches
`aurora-dashboard/` source. It does write one deliverable — the plan itself
— to `../DOCS/plans/` (outside the repo; per the workspace `CLAUDE.md`,
working notes like this don't belong inside a repo whose files are destined
for upstream PRs). To build the resulting plan, use `implement-plan` —
either now or in a later session, unedited or after the user has revised it.

## Steps

1. **Get the task.** If the user invoked this without a task description,
   ask for one before proceeding.
2. **Plan.** Launch the `dev-planner` agent (foreground) with the task
   description. `dev-planner` does its own architecture analysis (it has
   Read/Bash/Grep — no need to pre-fetch files for it); just make sure it
   knows this is aurora-dashboard (pnpm/Turborepo monorepo, Fastify + tRPC
   BFF, React 19 client) so it grounds itself via `AGENTS.md` and the KB per
   its own step 0. Instruct it to follow its own plan structure (Overview,
   Architecture Analysis, Potential Problems & Mitigations, Prerequisites,
   Implementation Steps, Testing Plan, Acceptance Criteria, Open Questions)
   and to use `AskUserQuestion` itself if something is ambiguous.

   Before launching, do a cheap KB-staleness check: read the pinned commit
   from `../DOCS/aurora-dashboard-kb/README.md`'s header and run
   `git log --oneline <pin>..HEAD -- packages/ apps/` (local only, no fetch
   needed). If that's a large number of commits, the plan may be built on an
   outdated picture of the architecture — note this in the final report
   (step 5) so the user can judge whether to update the KB first (per the
   workspace `CLAUDE.md`'s own rule that a lagging KB should be flagged, not
   silently used as-is). A handful of commits behind isn't worth mentioning
   — use judgment on what counts as "far behind."
3. **Write the plan file.** Resolve the target directory from the actual
   repo root, not a bare relative path typed from wherever the shell happens
   to be — on macOS's default case-insensitive filesystem, a careless
   `../DOCS/plans` can fold into this repo's own git-tracked `docs/` folder
   instead of the sibling directory one level up:

   ```bash
   REPO_ROOT=$(git rev-parse --show-toplevel)
   PLANS_DIR="$(dirname "$REPO_ROOT")/DOCS/plans"
   mkdir -p "$PLANS_DIR"
   ```

   Write into `$PLANS_DIR` (an unambiguous absolute path), and afterward run
   `git status` in the repo to confirm nothing under `docs/` picked up an
   untracked file — that's the tell if the collision happened anyway.
   File name: `<YYYY-MM-DD>-<kebab-slug-of-task>.md`, e.g.
   `2026-07-23-ceph-lifecycle-policies-endpoint.md`. Content: dev-planner's
   plan verbatim under a short header:

   ```markdown
   # Plan: <short task title>

   **Date:** <today, YYYY-MM-DD> · **Status:** not implemented

   <dev-planner's full plan output, unchanged>
   ```

4. **Update the index.** Maintain `$PLANS_DIR/README.md` as a lookup
   table, newest first — create it with this header if it doesn't exist,
   otherwise insert the new row directly below the header. `Status` is its
   own column, always exactly `not implemented` at creation time — don't
   fold it into `Risks` or `File`, that's ambiguous for whatever updates it
   later (see `implement-plan`'s step 8):

   ```markdown
   # Plans

   | Date | Task | Risks | Status | File |
   | --- | --- | --- | --- | --- |
   | 2026-07-23 | Ceph bucket lifecycle policies endpoint | 1 High | not implemented | [2026-07-23-ceph-lifecycle-policies-endpoint.md](./2026-07-23-ceph-lifecycle-policies-endpoint.md) |
   ```

5. **Report.** Tell the user the file path, and give a short inline summary
   (step count, any High-severity risks) so they can decide whether to open
   it — don't necessarily paste the whole plan into the conversation if it's
   long, the file is now the source of truth. If the plan has open
   questions, surface them prominently regardless — don't let those get
   buried in a file the user might not open right away. If step 2's
   KB-staleness check found the KB lagging far behind, mention that here too
   — a plan built on outdated architectural understanding is worth a caveat
   even if everything else about it looks solid.
