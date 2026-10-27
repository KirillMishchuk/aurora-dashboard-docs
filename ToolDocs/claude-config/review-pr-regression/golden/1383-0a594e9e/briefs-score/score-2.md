# Scorer 2 — review-and-comment-pr, aurora-dashboard PR #1383

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `0a594e9eaf3055cb1c9a102f1aceae43420e7870`
- baseRefOid: `a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd...0a594e9eaf3055cb1c9a102f1aceae43420e7870 -- <path>`.

## Your role: scorer 2 of 4

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C8, C9
- C13, C22, C24

## Candidates

The evidence is as the finders reported it, unchanged.

### C8 — from finder-a
- **Claim:** Network status is rendered as plain text in the list (and detail Overview) instead of a Badge status indicator.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:43`
- **Evidence:**

B.1: 'Status indicators | Badge'. Line 43: <DataGridCell>{network.status}</DataGridCell>; NetworkDetailsView.tsx:116 value: network.status.

### C9 — from finder-a
- **Claim:** Admin state is shown as 'UP' / 'DOWN', all-caps strings, which the UX writing rule forbids.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:46`
- **Evidence:**

Quick Reject: 'String using ... all-caps'; B.19: 'Never all-caps (ever)'. Line 46: network.admin_state_up ? t`UP` : t`DOWN`; same in NetworkDetailsView.tsx:117.

### C10 — from finder-a
- **Claim:** The label 'Created At' and 'Updated At' capitalise the short preposition 'At', which title-case rules require lowercase.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:132`
- **Evidence:**

B.19: 'Lowercase ... short prepositions (max 5 letters: at, by, for, in, of, on, to, up...)'. Lines 132-133: t`Created At`, t`Updated At`.

### C11 — from finder-a
- **Claim:** NetworkListContainer mirrors the currentPage prop into inputPage state through a useEffect. This synchronisation can be handled during render or by keying, and costs an extra render on every page change.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkListContainer.tsx:36`
- **Evidence:**

A.1: 'Critically evaluate every useEffect hook. Flag synchronizations, computed states ... that can be handled during rendering'. Lines 36-38: useEffect(() => { setInputPage(currentPage.toString()) }, [currentPage]).

### C12 — from finder-a
- **Claim:** A useEffect corrects an out-of-range page by calling onPageChange(1). This is derived state: safePage is already clamped during render, so the effect only exists to rewrite the URL.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:97`
- **Evidence:**

A.1: 'Flag synchronizations, computed states, or event-driven triggers ... that can be handled during rendering or inside event handlers'. Lines 97-99: useEffect(() => { if (!isStale && currentPage > totalPages) onPageChange(1) }, ...).

### C13 — from finder-c
- **Claim:** Same work as open draft PR #1385 (Neutron Networks BFF + read-only Networks list/details). Both add the same networks.tsx, networks/index.tsx, $networkId.tsx, -components/*, networksRouter.ts, networkHelpers.ts, types/network.ts and the nav entry. Whichever merges second hits real conflicts in 9 non-generated files, so one of them is wasted effort.
- **Location:** PR files
- **Evidence:**

context.json overlapping_prs: #1385 shares 18 files, merge conflicts in 9 non-generated files (networksRouter.ts, types/network.ts, networkHelpers.ts, NetworksList.tsx, NetworkDetailsView.tsx, etc.), conclusion conflicts_only_generated=False. git diff --stat of #1385 head 9ed42505 shows a superset: a changeset, docs/0017_networks_bff.md and tests for components, router, helpers and types. This PR adds no tests or changeset. The PR body does not mention #1385.
- **Review discussion:** Nothing in the discussion mentions #1385.

### C22 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: Advanced properties like MTU, Admin State, and Shared status are visible and manageable where appropriate (P3).
- **Location:** PR files
- **Evidence:**

MTU, admin state, shared, external and port security are visible in `NetworkDetailsView.tsx` `overviewItems` and in the list columns. They are not editable, so the manageable half is not done. `pr-body.md` limits the PR to the read-only part, so that half is out of scope. Tags are shown read-only when present.

### C24 — from describer (acceptance)
- **Claim:** Acceptance criterion unmet: Complete testing coverage (unit, integration, E2E) is achieved.
- **Location:** PR files
- **Evidence:**

The diff has no tests for `networksRouter.ts`, `networkHelpers.ts` or any new component. Only `buildNavSections.test.ts` changed, and the unchecked boxes in `pr-body.md` confirm "I have added tests" is unticked. No E2E was added. `pr-body.md` does not limit scope for testing.

## Result shape

```json
{
  "scores": [
    {
      "id": "C1",
      "score": 75,
      "severity": "Moderate",
      "category": "Performance",
      "location": "path:line, verified at headRefOid",
      "reason": "One or two sentences: what you checked and found (file:line, quote, behaviour) and why this score and severity. Written for the PR's readers — it can be posted: \"the head commit\", \"the PR description\", not run-folder file names.",
      "same_as": null,
      "precedent": null
    }
  ]
}
```

- One entry per candidate, every candidate exactly once.
- `score`: 0, 25, 50, 75 or 100. For 50 and up, `severity` (Critical, Major, Moderate, Low, Trivial), `category` (Bug, Security, Accessibility, UI/UX, Code Quality, Performance, Docs, Test coverage) and a `location` that exists at headRefOid (`path:line`, `path | text on that line`, or `PR body` / `PR state` / `PR files` / `CI`). Below 50, leave them out.
- `precedent`: required for 50 and up — the reader's tag, it never changes the score. `{"kind": "existing", "ref": "path:line"}` when merged code already has the same problem — `ref` is a line that itself breaks the same rule. Sibling code that does it right (e.g. a list that already debounces) is not a precedent: it's evidence for the finding, put it in `reason`. Find that line at baseRefOid (`git grep -n '<pattern>' <baseRefOid> -- <pathspec>`). `{"kind": "deferred", "ref": "<URL>"}` when a maintainer accepted or postponed the same point, on another PR or in `discussion.json`: open the thread, `ref` is the comment's GitHub URL. Both apply → `deferred`. Neither, or you couldn't confirm the candidate's `precedent` → `null`.
- `same_as`: required for a candidate in a group above — the id of the candidate in the same group that describes the same problem (score that one; this one is then dropped — `score` and `reason` may be left out for it), or `null` if it is a different problem. Elsewhere leave it out.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-2 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

