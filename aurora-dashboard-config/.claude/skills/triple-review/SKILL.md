---
name: triple-review
description: >-
  Review the current working changes in aurora-dashboard from three angles at
  once — security, performance, architecture — using the three specialized
  reviewer subagents in parallel, then combine into one summary. Use for a
  comprehensive review of pending changes; for a single-angle review use the
  relevant reviewer agent directly, and for a plain code-quality diff review
  use /code-review instead.
---

# Triple review

Runs `security-reviewer`, `performance-reviewer`, and `architecture-reviewer`
against the same set of changed files, in parallel, then merges their
findings into one report.

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
