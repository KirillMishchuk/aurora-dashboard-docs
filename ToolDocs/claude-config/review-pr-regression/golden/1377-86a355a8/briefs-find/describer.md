# Describer — review-and-comment-pr, aurora-dashboard PR #1377

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1380.md` (issue #1380 — acceptance criteria), `issue-1381.md` (issue #1381 — acceptance criteria), `issue-1382.md` (issue #1382 — acceptance criteria), `issue-816.md` (issue #816 — acceptance criteria), `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `86a355a8d6da94478e77c0869d9720efe6823e2a`
- baseRefOid: `af14a6a0d76d4a3019d8b49308d503e7247bc338`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `512f01b1bd79771fbf6b959225231e777c2c7c42..86a355a8d6da94478e77c0869d9720efe6823e2a` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff af14a6a0d76d4a3019d8b49308d503e7247bc338...86a355a8d6da94478e77c0869d9720efe6823e2a -- <path>`.

## Your role: the describer, on an Update

The PR already has a review report, and the new commits are in `delta.diff`. Another agent checks, finding by finding, which of the report's findings the new commits fix; the Update lists that under "Fixed since last analysis". Your job is everything else: what the new commits do that none of these findings covers. You describe; you don't review.

The report's findings:

- CR1 🟡 Moderate — Ports list reads one Neutron page only; ports and search hits beyond it silently disappear — `packages/aurora/src/server/Network/routers/portsRouter.ts:65`
- CR2 🟡 Moderate — 401/403 rendered inline on the details page and as a list error (B.6 Reject) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:64`
- CR3 🟡 Moderate — Details route fetches the port twice (loader + `useQuery`), ~8 Neutron requests per open — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:127`
- CR4 🟡 Moderate — Merge conflicts with `main` (locales) and with open PRs #1383 / #1385 (`routers/index.ts`) — `packages/aurora/src/server/Network/routers/index.ts:17`
- P1 — — PR is still a draft — PR state
- P2 — — Description doesn't mention that the Router details tab now lives in the URL (`?tab=`) — PR body
- I1 🟢 Low — "Log in again to continue." — Quick Reject wording (use "Sign in") — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:71`
- I2 🟢 Low — `PopupMenu` without `PopupMenuToggle` trigger (Quick Reject) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:79`
- I3 🟢 Low — `gap="1"` is not an approved spacing value (Quick Reject, B.3) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortDetailsView.tsx:51`
- I4 🟢 Low — Status is the 6th of 7 columns; B.15 puts status near the left — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:84`
- I5 🟢 Low — Routers doc still says names come from "one request" — now chunked by 50 — `packages/aurora/docs/0010_routers_bff.md:80`
- I6 🟢 Low — Ports doc error tables drop the `: {Neutron message}` suffix — `packages/aurora/docs/0017_ports_bff.md:103`
- I7 ⚪ Trivial — `useEffect` mirrors the `currentPage` prop into state — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:37`
- I8 ⚪ Trivial — `zod` imported after the Lingui imports (B.13 order) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/index.tsx:4`

**1. Sort the delta.** Go through `delta.diff` and put every change on one of two piles:

- **(a) carries out a finding above** — it does what the finding or its fix asked: moves the column, rewords the string, removes the loader, adds the toggle, updates the doc. Test: would this change exist if that finding had never been written? If not, it is (a).
- **(b) everything else** — new behaviour, a change outside the PR's stated scope, a change to a contract or to other callers, a side effect of an (a) change that the finding didn't ask for.

**2. Write only pile (b).** Pile (a) never appears in your result: not retold, not listed, not named by number.

- `what` — first one sentence on the update itself: the commit range in short SHAs (`1a2b3c4d..5e6f7a8b`) and CI on the head commit (merge conflicts are not part of this review — leave them out) (`context.json` → `ci`; say so if anything failed or is pending). Then one short paragraph per area of pile (b). If pile (b) is empty, add only: "Every other change carries out an earlier finding."
- `how` — only for a pile (b) change whose mechanism isn't obvious from `what`: a short excerpt (3–15 lines) and what it does. Don't copy code: put a placeholder on its own line — `[[code:<path>:<from>-<to>]]`, or `[[code:<path> | <text from its first line> | <number of lines>]]` — and cite lines as `[[at:<path> | <text on that line>]]` or `` `<path>:<line>` ``; the code is inserted and every citation checked later. Otherwise `""`.
- `affects` — for pile (b) only: consumers outside the PR's own files (`git grep -n '<symbol>' 86a355a8d6da94478e77c0869d9720efe6823e2a -- . ':!pnpm-lock.yaml' ':!**/CHANGELOG.md' ':!**/locales/**'`), callers left stale, docs that now disagree, contract changes. Otherwise `""`.
- `qa` — `core_path` and `edge_cases` are empty lists; an Update shows no QA plan.

Write every text for the PR's readers: "the head commit", "the PR description", "the linked issue" — never run-folder file names (`context.json`, `pr-body.md`, …), field names (`headRefOid`) or names of this review's steps (finders, scorers, describer); `save.py` rejects them.

**Acceptance criteria.** Grade the PR against the acceptance criteria in `issue-1380.md`, `issue-1381.md`, `issue-1382.md`, `issue-816.md`, `issue-1019.md`: for each criterion, met / partly met / unmet, with `file:line` evidence. Use "out of scope" only when `pr-body.md` explicitly limits the PR to part of the issue (e.g. "phase 1", "read-only part of #N") and the criterion falls outside that part — quote the limiting line from `pr-body.md` in `evidence`. An out-of-scope criterion is not a candidate; a partly met criterion inside the PR's own scope still is.

**Scope.** If the PR description (or the linked issue) limits this PR to part of an epic or issue — a phase, "read-only part of #N" — put that in `scope` as one short line, e.g. `#816 — Phase 1, read-only`. Otherwise `null`.

## Result shape

```json
{
  "overview": {
    "what": "Markdown: one sentence on the update, then pile (b) by area.",
    "how": "Markdown or empty string.",
    "affects": "Markdown or empty string."
  },
  "qa": { "core_path": [], "edge_cases": [] },
  "acceptance": [
    { "criterion": "quoted from the issue", "status": "met | partly met | unmet | out of scope", "evidence": "`path:line` and why" }
  ],
  "stale_callers": [
    { "symbol": "name", "location": "path:line", "note": "what's stale" }
  ],
  "scope": "#816 — Phase 1, read-only, or null"
}
```

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as describer <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

