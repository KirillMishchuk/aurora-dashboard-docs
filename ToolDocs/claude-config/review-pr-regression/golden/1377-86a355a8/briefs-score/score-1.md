# Scorer 1 — review-and-comment-pr, aurora-dashboard PR #1377

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1380.md` (issue #1380 — acceptance criteria), `issue-1381.md` (issue #1381 — acceptance criteria), `issue-1382.md` (issue #1382 — acceptance criteria), `issue-816.md` (issue #816 — acceptance criteria), `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `86a355a8d6da94478e77c0869d9720efe6823e2a`
- baseRefOid: `af14a6a0d76d4a3019d8b49308d503e7247bc338`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `512f01b1bd79771fbf6b959225231e777c2c7c42..86a355a8d6da94478e77c0869d9720efe6823e2a` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff af14a6a0d76d4a3019d8b49308d503e7247bc338...86a355a8d6da94478e77c0869d9720efe6823e2a -- <path>`.

## Your role: scorer 1 of 2

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C5, C9

## Earlier findings of this report

This is an Update: the report it extends already raised the findings below. A candidate that objects to the PR doing what one of them asked (it moved a column, renamed a string, restructured code as an earlier finding requested) is not a new problem: score it 0 and name the earlier finding in the reason. If the change was made badly — it breaks something or does only half of it — score that as usual. Exception: when a reviewer other than the PR's author (not a bot) asked for it in the review discussion — the candidate's `discussion` quotes them — score it as usual: their call outranks this report's earlier finding. Name the earlier finding it reverses in the reason.

A candidate raised in the review discussion (it has a `discussion`) about a file the new commits don't touch (not in `delta.diff`) is outside this Update: score it 0 and say so in the reason — "Outside this update's changes" plus what happened to it in the thread (e.g. the author deferred it to a follow-up, with the url). It is then answered under "Review comments not taken up". `save.py` refuses 50 or more for it.

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

### C1 — from find-standards
- **Claim:** The 401 case in the port details error view is handled inline (an error page with a Sign in button that navigates to "/") instead of redirecting to Sign-in with the target remembered. The code comment claims this follows B.6, but B.6 requires a redirect and redirect-back after auth.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:68`
- **Evidence:**

B.6 Reject: "a 401/403 handled inline instead of via redirect / page-level info Message"; table row: "401 Unauthenticated | Redirect to Sign-in, remember target, redirect back after auth". Code: `if (errorCode === "UNAUTHORIZED") { return <RouteIdLevelDefaultError code={401} ... action={<Button ... onClick={() => navigate({ to: "/" })}>`

### C2 — from find-standards
- **Claim:** The port details route loader was removed, so the port is fetched only inside the component through a React Query call. A.3 says data critical for rendering must come from the route loader. The head title also no longer shows the port name and is a hardcoded, untranslated "Port Details".
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:155`
- **Evidence:**

A.3: "Data critical for rendering a page must be fetched via the route's `loader` function rather than loading it inside the component body." Delta removes `loader: async ({ context, params }) => { ... getById.query ... }` and sets `head: () => ({ meta: [{ title: "Port Details" }] })`.
- **Precedent:** The flavors detail route (the B reference implementation) keeps its data fetch in the route layer. The removal is justified in the PR comment as avoiding a double request.

### C3 — from find-standards
- **Claim:** The Status column renders the raw status string (`{port.status}` / `{router.status}`) in a DataGridCell instead of a Badge. The delta moves this cell, so it touches the line.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:51`
- **Evidence:**

B.1 table: "Status indicators | `Badge`". Same in routers/-components/RouterTableRow.tsx:51 (`<DataGridCell>{router.status}</DataGridCell>`).
- **Precedent:** Both lists already used plain text before this delta, and the details views also use plain text.

### C4 — from find-standards
- **Claim:** The new 403 info Message banners in the list views have no `mb-4`, so the spacing is not the approved Message banner margin.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:160`
- **Evidence:**

B.3 Margin table: "`Message` banners | `mb-4`". `<Message variant="info" title={t`Insufficient Permissions`}>` has no className. The same applies to routers/-components/RoutersList.tsx:105 and ports/$portId.tsx:87, where the Stack has `mt-6` and the Message has no `mb-4`.
- **Precedent:** The Message is the only content on the page in the list views, so the visual impact is small.

### C5 — from find-history
- **Claim:** The new pagination fix covers only the main ports/routers list request. The other Neutron collection reads in the same procedures still read one page: the router interface-port lookup (fetchRouterInterfacePorts, chunks of router IDs, fields-filtered /v2.0/ports) and the batched name lookups (fetchNetworkSummaries / fetchSubnetSummaries / fetchSecurityGroupSummaries, 50 IDs per request). On a deployment with pagination_max_limit, the router list now returns every router but silently drops private networks (or names) beyond the first page. This is the same failure the fix claims to remove.
- **Location:** `packages/aurora/src/server/Network/routers/routersRouter.ts:85`
- **Evidence:**

At 86a355a8 fetchRouterInterfacePorts does `network.get(withQuery(PORTS_BASE_URL, params))` and parses `.ports` without reading `ports_links`. lookupHelpers.ts getJson/fetchSummaries likewise never follow `*_links`. grep of `_links` under packages/aurora/src/server shows it is used only in the two list loops, requestHelpers.nextPageUrl and the two list schemas. The new docs/0010 sentence says 'The BFF-side search and filters therefore see every router', but the private-network enrichment still depends on a single-page response.
- **Precedent:** Router list loop in routersRouter.ts:131-150 and ports list loop in portsRouter.ts:66-84 (the new code) do follow `next`.
- **Review discussion:** Not raised. CR1 in mark-karnaukh-extern-sap's 2026-10-20 verification only covered the main ports list.

### C9 — from find-api-contract
- **Claim:** The PR now follows `*_links` `next` for the ports and routers lists, but the sibling Neutron list calls that feed the router list (router interface ports by device_id) and the lookups by id (networks, subnets, security-groups) still read only the first page. With a `pagination_max_limit` lower than the 50-id chunk (or a router with several interfaces: 50 routers x N interface ports), results are silently truncated: private networks / names go missing in the router list, and the lookups return a partial list that is treated as complete (best-effort fallback to IDs). The new docs/comments claim the returned list is complete on paginated deployments.
- **Location:** `packages/aurora/src/server/Network/routers/routersRouter.ts:85`
- **Evidence:**

Code at 86a355a8: fetchRouterInterfacePorts does `const response = await network.get(withQuery(PORTS_BASE_URL, params))` then `parseOrThrow(RouterInterfacePortSummaryListResponseSchema, data, ...).ports` with no `next` handling; listInterfaces (routersRouter.ts:359-366) does `network.get(withQuery(PORTS_BASE_URL, portParams))` and `const { ports } = parseOrThrow(RouterPortListResponseSchema, ...)` likewise; lookupHelpers.ts fetchNetworkSummaries/fetchSubnetSummaries/fetchSecurityGroupSummaries each issue one GET per chunk of 50 ids and read only `.networks`/`.subnets`/`.security_groups`. Reference (https://docs.openstack.org/api-ref/network/v2/#pagination, read from neutron-lib api-ref/source/v2/intro.inc): "To reduce load on the service, list operations will return a maximum number of items at a time." and "If the client requests a limit beyond the maximum limit configured by the deployment, the server returns the maximum limit number of items." and "For convenience, list responses contain atom ``next`` links and ``previous`` links. The last page in the list requested with ``page_reverse=False`` will not contain ``next`` link". The id filter on list calls does not lift the cap. Only the ports/routers top-level lists got the loop in this PR (delta: requestHelpers.nextPageUrl, portsRouter.ts, routersRouter.ts). Note: these lines are not in delta.diff (listInterfaces blame ca33c0169); they matter because the PR adds the claim 'the returned list is complete' (docs/0010_routers_bff.md) and the ports list reuses the same lookups.
- **Precedent:** The PR's own loop in routersRouter.list / portsRouter.list shows the intended pattern.

### C6 — from find-discussion
- **Claim:** On the ports list page only 403 is turned into a friendly state. A 401 (expired session) and every other error reach the ErrorBoundary, which prints the raw error.message (the BFF text) as the body. Details page got a 'Sign in' action for 401 but the list did not, so the CR2 fix is only half applied there.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:290`
- **Evidence:**

At 86a355a8, createPortsPromise rethrows everything except FORBIDDEN (lines 50-55); fallbackRender at line 283-290 shows error.message. UNAUTHORIZED is handled only in $portId.tsx:68. The fixes comment claims 'CR2: 401 -> Sign in action to /; 403 -> page-level info Message (details + list), no raw BFF text'; for the list, 401 is not handled.
- **Precedent:** routers/$routerId.tsx:75 handles UNAUTHORIZED the same detail-page-only way.
- **Review discussion:** CR2 of the earlier review (list shows raw BFF message, 401/403 handled in-page); mark-karnaukh-extern-sap confirmed it in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6293554974 and listed it as fixed in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6295356006, but the list-page 401 / raw message path still applies.

### C7 — from find-discussion
- **Claim:** Client-side search duplicates the BFF filterPortsBySearchTerm field list by hand (comment says 'mirroring'), and the BFF still accepts and runs search/sort/limit params that the UI no longer uses. The two implementations can drift and the BFF params are dead code for the only consumer.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:60`
- **Evidence:**

PortsList.tsx:59-70 'Fields the search matches, mirroring the BFF's filterPortsBySearchTerm'; portsRouter.ts:94 still calls filterPortsBySearchTerm(..., searchTerm), while the client queries only { project_id, network_id } (PortsList.tsx:47).
- **Review discussion:** Raised by the author as the 'Perf' change and open decision 1 in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6295356006 ('BFF still accepts the params for API/tests'); no reviewer response.

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
- `same_as`: required for a candidate in a group above — the id of the candidate in the same group that describes the same problem (score that one, and leave its own `same_as` null — never point at another duplicate; this one is then dropped — `score` and `reason` may be left out for it), or `null` if it is a different problem. Elsewhere leave it out.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-1 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

