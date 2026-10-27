# Scorer 2 — review-and-comment-pr, aurora-dashboard PR #1377

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1380.md` (issue #1380 — acceptance criteria), `issue-1381.md` (issue #1381 — acceptance criteria), `issue-1382.md` (issue #1382 — acceptance criteria), `issue-816.md` (issue #816 — acceptance criteria), `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `86a355a8d6da94478e77c0869d9720efe6823e2a`
- baseRefOid: `af14a6a0d76d4a3019d8b49308d503e7247bc338`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `512f01b1bd79771fbf6b959225231e777c2c7c42..86a355a8d6da94478e77c0869d9720efe6823e2a` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff af14a6a0d76d4a3019d8b49308d503e7247bc338...86a355a8d6da94478e77c0869d9720efe6823e2a -- <path>`.

## Your role: scorer 2 of 2

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C10, C11

## Earlier findings of this report

This is an Update: the report it extends already raised the findings below. A candidate that objects to the PR doing what one of them asked (it moved a column, renamed a string, restructured code as an earlier finding requested) is not a new problem: score it 0 and name the earlier finding in the reason. If the change was made badly — it breaks something or does only half of it — score that as usual.

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

## Candidates

The evidence is as the finders reported it, unchanged.

### C8 — from finder-e
- **Claim:** The delta rewrites the Port error tables to say the message ends in `{Neutron message}`, but the shared ErrorHandler appends the HTTP `statusText` (or "Unknown error"), not the Neutron response body message. The docs therefore describe behaviour the code does not have.
- **Location:** `packages/aurora/docs/0017_ports_bff.md:105`
- **Evidence:**

errorHandling.ts at 86a355a8: `message: `Unauthorized access to ${resourceLabel}: ${response.statusText || "Unknown error"}``, same for 400/403/default (Failed to process). errorHandling.ts is not changed in the PR, and requestOrThrow passes the response to the handler, so no Neutron body message is used. delta.diff lines 41-142 add `{Neutron message}` to the 401/403/default/412 rows.
- **Precedent:** The pre-existing 400 rows for create/update already said {Neutron message}, so the doc inaccuracy was present before and this delta extends it to more rows.

### C10 — from finder-f
- **Claim:** Pagination follows `next` by reusing only the query string of the absolute href against the BFF base path, and the list schemas accept `ports_links`/`routers_links` as optional arrays. Reference documents the links field as `*_links` with rel next/previous; consistent. However the guard `visited` silently stops and returns a partial list (no error) if Neutron returns a repeating next URL, so the user sees a truncated list without any signal.
- **Location:** `packages/aurora/src/server/Network/routers/portsRouter.ts:73`
- **Evidence:**

Code: `while (nextUrl && !visited.has(nextUrl)) { visited.add(nextUrl) ...`; same loop in routersRouter.ts. Reference https://docs.openstack.org/api-ref/network/v2/#pagination: 'The last page in the list requested with page_reverse=False will not contain next link' - the documented termination is the absence of `next`; the code adds a silent cut-off on a repeated URL instead of failing. Also no `limit` is sent, so the page size is the deployment default/maximum (doc: 'the server returns the maximum limit number of items'); a project with many ports means many sequential requests (no upper bound on pages) before any response is returned.

### C11 — from finder-g
- **Claim:** The new Neutron pagination loop in ports.list (and routers.list) has no upper bound on pages or accumulated items. The `visited` set only stops a repeated identical URL, so a `next` link whose marker keeps changing (or a very large project) makes one tRPC query issue unbounded sequential Neutron requests and buffer every result in BFF memory before the network/subnet lookups. Any authenticated user can trigger it by opening the list page.
- **Location:** `packages/aurora/src/server/Network/routers/portsRouter.ts:73`
- **Evidence:**

git show 86a355a8:packages/aurora/src/server/Network/routers/portsRouter.ts: loop pushes `...pagePorts` into `ports` until `nextPageUrl` returns undefined or a URL repeats; no max-page or max-item cap. Same pattern in routersRouter.ts list. nextPageUrl (requestHelpers.ts) reuses only the query from Neutron's absolute `next` href against the fixed base path, so there is no host/path injection; the concern is only resource exhaustion.
- **Precedent:** Both ports and routers list share the identical loop.

### C12 — from describer (acceptance)
- **Claim:** Acceptance criterion unmet: #1380: Create an AI agent skill for scaffolding new OpenStack resources (skill structure, intake, three phase guides, templates)
- **Location:** PR files
- **Evidence:**

The PR adds no agent skill; the PR description does not reference #1380 and it is not in the Related Issues.

### C13 — from describer (stale caller)
- **Claim:** Stale caller of `sort_key / sort_dir / searchTerm on ports.list`: The Ports page no longer sends these to the BFF; the client mirrors the search in `filterPorts` instead. The input fields and docs still describe server-side sort and search.
- **Location:** `packages/aurora/src/server/Network/types/port.ts:115`
- **Evidence:**

The Ports page no longer sends these to the BFF; the client mirrors the search in `filterPorts` instead. The input fields and docs still describe server-side sort and search.

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

