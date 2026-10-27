# Scorer 4 — review-and-comment-pr, aurora-dashboard PR #1383

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `0a594e9eaf3055cb1c9a102f1aceae43420e7870`
- baseRefOid: `a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd...0a594e9eaf3055cb1c9a102f1aceae43420e7870 -- <path>`.

## Your role: scorer 4 of 4

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Candidates

The evidence is as the finders reported it, unchanged.

### C23 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: Comprehensive error handling provides user-friendly feedback for Neutron errors (e.g., preventing deletion of networks with active ports).
- **Location:** `packages/aurora/src/server/Network/helpers/networkHelpers.ts:8`
- **Evidence:**

Reads are covered: BFF `NetworkErrorHandlers` use the shared `ErrorHandler` (`networkHelpers.ts:8-12`). The detail page maps codes to messages with retry (`$networkId.tsx` `getErrorDescription`), and the list handles FORBIDDEN and the error boundary. Delete-time errors are not covered, since there is no delete (out of the read-only scope).

### C25 — from describer (stale caller)
- **Claim:** Stale caller of `isEnabled("networks") / project home service cards`: The project home page builds Network cards for securitygroups, floatingips and routers but not networks, so Networks appears in the sidebar but not on the home page.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx:87`
- **Evidence:**

The project home page builds Network cards for securitygroups, floatingips and routers but not networks, so Networks appears in the sidebar but not on the home page.

### C26 — from describer (stale caller)
- **Claim:** Stale caller of `Service key reference`: The README service-key list (also at line 210) does not include the new `networks` key, which is part of the public `enabledServices` contract. `routers` was already missing.
- **Location:** `packages/aurora/README.md:183`
- **Evidence:**

The README service-key list (also at line 210) does not include the new `networks` key, which is part of the public `enabledServices` contract. `routers` was already missing.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-4 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

