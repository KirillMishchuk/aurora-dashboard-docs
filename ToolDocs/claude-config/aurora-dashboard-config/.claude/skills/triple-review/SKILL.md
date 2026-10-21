---
name: triple-review
description: >-
  Review the current working changes in aurora-dashboard from three angles at
  once — security, performance, architecture — using the three specialized
  reviewer subagents in parallel, then combine into one summary. Use for a
  comprehensive review of pending changes; for a single-angle review use the
  relevant reviewer agent directly, and for a plain code-quality diff review
  use /code-review instead. Saves the combined report to ../DOCS/pr-reviews/
  and updates that folder's README index.
---

# Triple review

Runs `security-reviewer`, `performance-reviewer`, and `architecture-reviewer`
against the same set of changed files, in parallel, then merges their
findings into one report and saves it to `DOCS/pr-reviews/` — the pre-merge
review log. (Post-merge PR reports are a
different thing: `document-pr` writes those to `DOCS/aurora-dashboard-kb/prs/`;
don't touch that folder here.)

## Steps

1. **Find what changed.** Run `git status` and `git diff` (staged +
   unstaged) yourself to list changed TypeScript/JavaScript files. If that's
   empty — common right before opening a PR, when everything's already
   committed — fall back to `git diff main...HEAD --name-only` (the whole
   branch's changes vs. where it diverged from `main`) instead of assuming
   there's nothing to review. Only tell the user and stop if both are empty.
2. **Launch all three reviewers in parallel.** In a single message, make
   three `Agent` tool calls back-to-back (background is fine — wait for all
   three before continuing):
   - `security-reviewer`: review the changed files for auth/authorization
     (tRPC procedure builders, permission checks), input validation, secrets
     exposure — per its own instructions.
   - `performance-reviewer`: review the changed files for React rendering,
     TanStack Query/data-fetching, and OpenStack API call efficiency — per
     its own instructions.
   - `architecture-reviewer`: review the changed files for design patterns,
     module boundaries, and consistency with this repo's conventions — per
     its own instructions.

   Give each agent the actual file list with a one-line description of what
   changed in each, not just file paths.
3. **Wait for all three**, then combine into one report:
   - Group findings by severity across all three reviewers first (any
     Critical/High from security takes priority), then by reviewer.
   - Call out if zero findings came back from a reviewer — that's a
     signal to sanity-check the file list was right, not necessarily a
     clean bill of health.
   - Report total finding count and a one-line verdict per reviewer.
4. **Save the report to `DOCS/pr-reviews/`.** Resolve the folder from the
   repo's common git dir, never as a bare `../DOCS` typed from a
   subdirectory (on macOS's case-insensitive filesystem that folds into the
   repo's own git-tracked `docs/`), and so it also works from a linked
   worktree:

   ```bash
   REVIEWS_DIR="$(dirname "$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")")/DOCS/pr-reviews"
   ```

   - **File name.** `pr-<number>-review.md` if the branch has a PR — check
     with `gh pr list --head "$(git branch --show-current)" --state all --json number --limit 1`
     (if `gh` is missing or unauthenticated, skip the lookup); otherwise
     `<branch-slug>-review.md` with the personal `kiryl-` prefix dropped.
     If a file for a PR is later created under the slug name and the PR now
     exists, rename it to the `pr-<number>` form.
   - **One file per PR, latest review wins.** Re-running on the same PR
     overwrites the file. Start it with a short `## Supersedes` note giving
     the previous review's date and head SHA, and the status of each of its
     High/Critical findings at the new head (fixed / still present / out of
     scope) — the old text itself is not kept; git history in `DOCS` has it.
   - **Contents** (English):
     - a frontmatter block first — `type: pr-review`, `date: YYYY-MM-DD`,
       `pr: [<n>]` (omit without a PR), `branch: <branch>`, `head: <short sha>`
       — each as its own `key: value` line between two `---` lines;
     - `# PR #<n> Triple Review — <title>` (or `# <branch> Triple Review` without a PR);
     - header lines: ``Branch: `<branch>` vs `main` ``, ``Head SHA: `<full sha>` ``,
       `Reviewed: YYYY-MM-DD`, `Scope:` working tree or `main...HEAD`, and
       `Posted to PR: no` (this skill never posts);
     - the combined findings exactly as reported in step 3 — grouped by
       severity, each with file:line, the issue, the risk and the suggested
       fix, plus the reviewer that raised it;
     - the one-line verdict per reviewer and the total count.
   - **Update `$REVIEWS_DIR/README.md`.** The table there is the index,
     newest first. Insert a row directly below the header, or replace the
     existing row for the same PR (same file) and move it to the top:

     ```markdown
     | [#<n>](https://github.com/cobaltcore-dev/aurora-dashboard/pull/<n>) | `<branch>` vs `main` | YYYY-MM-DD | <one-sentence summary: counts by severity and the most important finding> | [<file>](./<file>) |
     ```

     — use `—` in the PR column when there is no PR yet. Write the row in
     English and escape any `|` inside a cell (also inside code spans) as `\|`.
   - If the file has a `pr`, run
     `python3 "$(dirname "$REVIEWS_DIR")/tools/update-related.py"` to refresh
     the vault's "Related" links (skip silently if the script is missing).
   - Do not commit or push `DOCS`, and don't create a plan or touch
     `DOCS/plans/` — whether to plan fixes is the user's call. Tell the user
     the file path.
