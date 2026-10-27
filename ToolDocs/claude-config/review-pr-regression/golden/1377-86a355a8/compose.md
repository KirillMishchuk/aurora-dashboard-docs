# Compose findings — review-and-comment-pr

Write `texts.json` in the run folder (shape at the end), then run
`python3 .claude/skills/review-and-comment-pr/scripts/assemble.py --run <run folder> --texts`
and `render.py`. Scores, severity, category and location are the scorers' — don't change them.
Text rules, code placeholders and `[[ref:<id>]]` are in `references/findings-format.md`.
A finding's precedent (existing pattern / deferred) is the scorer's tag — render.py shows it; don't repeat it in the explanation.

## Findings

### `c1` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx | <Button variant="primary" onClick={() => navigate({ to: "/" })}>` · score 50
- **Claim** (finder-a): The 401 case in the port details error view is handled inline (an error page with a Sign in button that navigates to "/") instead of redirecting to Sign-in with the target remembered. The code comment claims this follows B.6, but B.6 requires a redirect and redirect-back after auth.
- **Scorer:** CR2 asked for 401 to go to sign-in; the head commit still renders the 401 inline (RouteIdLevelDefaultError) with a button to "/", and the comment above it says it sends the user to sign in 'instead of showing the error inline'. B.6 requires redirect with the target remembered and redirect back after auth, which this does not do, so CR2 is only half fixed. Low per the 401/403 inline precedent.
- **Evidence:**

B.6 Reject: "a 401/403 handled inline instead of via redirect / page-level info Message"; table row: "401 Unauthenticated | Redirect to Sign-in, remember target, redirect back after auth". Code: `if (errorCode === "UNAUTHORIZED") { return <RouteIdLevelDefaultError code={401} ... action={<Button ... onClick={() => navigate({ to: "/" })}>`


### `c3` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx | <DataGridCell>{port.status}</DataGridCell>` · score 50
- **Claim** (finder-a): The Status column renders the raw status string (`{port.status}` / `{router.status}`) in a DataGridCell instead of a Badge. The delta moves this cell, so it touches the line.
- **Scorer:** B.1 table lists 'Status indicators | Badge'; PortTableRow.tsx:51 and RouterTableRow.tsx:51 render the raw status string in a DataGridCell. Verified, but cosmetic and consistent with the details views, so Low.
- **Precedent:** Both lists already used plain text before this delta, and the details views also use plain text.
- **Evidence:**

B.1 table: "Status indicators | `Badge`". Same in routers/-components/RouterTableRow.tsx:51 (`<DataGridCell>{router.status}</DataGridCell>`).


### `c6` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx | body={error instanceof Error ? error.message : t`An unexpected error occurred.`}` · score 50
- **Claim** (finder-d): On the ports list page only 403 is turned into a friendly state. A 401 (expired session) and every other error reach the ErrorBoundary, which prints the raw error.message (the BFF text) as the body. Details page got a 'Sign in' action for 401 but the list did not, so the CR2 fix is only half applied there.
- **Scorer:** createPortsPromise converts only FORBIDDEN (PortsList.tsx:52); a 401 and other errors reach the ErrorBoundary, which prints the raw BFF error.message with no Sign in action. CR2 covered the list error too, and the fix handles it on the details page only. Low per the 401/403 precedent.
- **Precedent:** routers/$routerId.tsx:75 handles UNAUTHORIZED the same detail-page-only way.
- **Review discussion:** CR2 of the earlier review (list shows raw BFF message, 401/403 handled in-page); mark-karnaukh-extern-sap confirmed it in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6293554974 and listed it as fixed in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6295356006, but the list-page 401 / raw message path still applies.
- **Evidence:**

At 86a355a8, createPortsPromise rethrows everything except FORBIDDEN (lines 50-55); fallbackRender at line 283-290 shows error.message. UNAUTHORIZED is handled only in $portId.tsx:68. The fixes comment claims 'CR2: 401 -> Sign in action to /; 403 -> page-level info Message (details + list), no raw BFF text'; for the list, 401 is not handled.


## Scored below 50 (not in the report)

- `C2` 0: The port details route loader was removed, so the port is fetched only inside the component through a React Query call. A.3 says data critic
- `C4` 25: The new 403 info Message banners in the list views have no `mb-4`, so the spacing is not the approved Message banner margin.
- `C5` 25: The new pagination fix covers only the main ports/routers list request. The other Neutron collection reads in the same procedures still read
- `C7` 25: Client-side search duplicates the BFF filterPortsBySearchTerm field list by hand (comment says 'mirroring'), and the BFF still accepts and r
- `C8` 0: The delta rewrites the Port error tables to say the message ends in `{Neutron message}`, but the shared ErrorHandler appends the HTTP `statu
- `C9` 0: The PR now follows `*_links` `next` for the ports and routers lists, but the sibling Neutron list calls that feed the router list (router in
- `C10` 0: Pagination follows `next` by reusing only the query string of the absolute href against the BFF base path, and the list schemas accept `port
- `C11` 25: The new Neutron pagination loop in ports.list (and routers.list) has no upper bound on pages or accumulated items. The `visited` set only st
- `C12` 0: Acceptance criterion unmet: #1380: Create an AI agent skill for scaffolding new OpenStack resources (skill structure, intake, three phase gu
- `C13` 0: Stale caller of `sort_key / sort_dir / searchTerm on ports.list`: The Ports page no longer sends these to the BFF; the client mirrors the se

## Acceptance grading (for the summary)

- unmet: #1380: Create an AI agent skill for scaffolding new OpenStack resources (skill structure, intake, three phase guides, templates)
- met: #1381: All procedures above are available, and both input and Neutron responses are validated with Zod.
- met: #1381: Lists are restricted to the current project and can be narrowed to one network.
- met: #1381: List and details responses contain everything the list and details views need, including related resource names.
- met: #1381: Missing related names (e.g. lookups not permitted) don't break the list or details; IDs are returned instead.
- met: #1381: Neutron errors are mapped to tRPC errors with clear messages.
- met: #1381: Tests cover success and error cases.
- met: #1381: Documentation is added alongside the existing service docs.
- met: #1382: The page is reachable from the side navigation and the project overview.
- met: #1382: The list view shows the agreed columns for the current project, with working search, sorting and pagination.
- met: #1382: The list can be rendered for a single network without the Network column.
- met: #1382: The details view shows all fields listed above.
- met: #1382: Missing data (e.g. unresolvable names, ports without IPs or device) is handled gracefully.
- met: #1382: UI follows the design system and existing list/detail patterns.
- met: #816: Ports can be listed globally (all ports in the project) and filtered by `networkId`.
- out of scope: #816: Users can list, view, create, update, and delete ports (P1, P2 & P3).
- out of scope: #816: The Network Detail page contains a "Ports" tab that reuses the same overview component.
- out of scope: #816: All action-triggering UI elements are gated using `canUser(...)` against `network:port:*` policy.
- out of scope: #1019: Network Detail view clearly lists associated Subnets and provides visibility of Ports.

## Earlier findings (for `earlier`)

The `earlier` agent checked each of them at the new head; its status, note and evidence are below and already in the template. Keep the statuses — change one only if another agent's result shows it wrong, and say why in the note — and reword a note only for the reader. Don't open the code yourself. In a note, name earlier findings by number (`CR2`), this Update's own by `[[ref:<id>]]`. render.py refuses a list with one left out.

- CR1 🟡 Moderate — Ports list reads one Neutron page only; ports and search hits beyond it silently disappear — `packages/aurora/src/server/Network/routers/portsRouter.ts:65`
  - **fixed** — portsRouter.list now follows ports_links next pages (visited-guarded loop) and returns the full list. _(evidence: git grep portsRouter.ts at 86a355a8: 'while (nextUrl && !visited.has(nextUrl))' ... 'nextUrl = nextPageUrl(PORTS_BASE_URL, ports_links)')_
- CR2 🟡 Moderate — 401/403 rendered inline on the details page and as a list error (B.6 Reject) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:64`
  - **partly** — 403 is now a page-level info Message on both details and list; 401 is still not a redirect: details shows a 'Sign in' error page, list falls into the generic 'Failed to Load Ports' boundary. _(evidence: $portId.tsx: 'if (errorCode === "UNAUTHORIZED") return <RouteIdLevelDefaultError code={401} ... navigate({ to: "/" })'; 'FORBIDDEN' -> <Message variant="info">; PortsList.tsx: only FORBIDDEN is caught in createPortsPromise, 401 reaches ErrorBoundary)_
- CR3 🟡 Moderate — Details route fetches the port twice (loader + `useQuery`), ~8 Neutron requests per open — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:127`
  - **fixed** — The route loader is gone; only the component's useQuery fetches the port. _(evidence: $portId.tsx Route has comment 'No loader fetch: the component's query is the single source for the port' and no loader property)_
- CR4 🟡 Moderate — Merge conflicts with `main` (locales) and with open PRs #1383 / #1385 (`routers/index.ts`) — `packages/aurora/src/server/Network/routers/index.ts:17`
  - **dropped** — Merge conflicts are no longer part of this review; GitHub shows them. _(evidence: n/a)_
- P1 — — PR is still a draft — PR state
  - **open** — PR is still a draft. _(evidence: context.json: pr.is_draft = true)_
- P2 — — Description doesn't mention that the Router details tab now lives in the URL (`?tab=`) — PR body
  - **fixed** — The description now covers the ?tab= search param on routers/$routerId.tsx. _(evidence: grep -n tab pr-body.md line 28: 'the active details tab is now kept in the URL as a `?tab=` search param (via `validateSearch`)')_
- I1 🟢 Low — "Log in again to continue." — Quick Reject wording (use "Sign in") — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:71`
  - **fixed** — Copy now reads 'Sign in again to continue.' _(evidence: $portId.tsx: t`Your session has expired. Sign in again to continue.`)_
- I2 🟢 Low — `PopupMenu` without `PopupMenuToggle` trigger (Quick Reject) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:79`
  - **fixed** — PopupMenu now has a PopupMenuToggle wrapping the icon Button. _(evidence: PortTableRow.tsx: '<PopupMenu> <PopupMenuToggle as="div"> <Button icon="moreVert" ...')_
- I3 🟢 Low — `gap="1"` is not an approved spacing value (Quick Reject, B.3) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortDetailsView.tsx:51`
  - **fixed** — gap="1" is gone; PortDetailsView uses "0.5", "2", "6", which the B.3 table allows. _(evidence: git grep 'gap="1"' in the ports folder at 86a355a8: no matches; PortDetailsView.tsx uses gap="0.5"/"2"/"6")_
- I4 🟢 Low — Status is the 6th of 7 columns; B.15 puts status near the left — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:84`
  - **fixed** — Status is now the 2nd column, right after Name / ID. _(evidence: PortListContainer.tsx header order: Name / ID, Status, Description, Network, Fixed IPs / Subnet, Device Owner / ID)_
- I5 🟢 Low — Routers doc still says names come from "one request" — now chunked by 50 — `packages/aurora/docs/0010_routers_bff.md:80`
  - **fixed** — Routers doc now says lookups are chunked into requests of at most 50 IDs. _(evidence: 0010_routers_bff.md:82 'one lookup (chunked into requests of at most 50 IDs)'; :121 'each chunked into requests of at most 50 IDs')_
- I6 🟢 Low — Ports doc error tables drop the `: {Neutron message}` suffix — `packages/aurora/docs/0017_ports_bff.md:103`
  - **fixed** — Error tables in the ports doc carry the ': {Neutron message}' suffix again. _(evidence: 0017_ports_bff.md:105-108 'Invalid request data for Port: {Neutron message}' etc.)_
- I7 ⚪ Trivial — `useEffect` mirrors the `currentPage` prop into state — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:37`
  - **fixed** — The useEffect is gone; PageInput is keyed on currentPage instead. _(evidence: PortListContainer.tsx: '<PageInput key={currentPage} ...' ; no useEffect match)_
- I8 ⚪ Trivial — `zod` imported after the Lingui imports (B.13 order) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/index.tsx:4`
  - **fixed** — zod is now imported right after the router import, before the Lingui imports. _(evidence: ports/index.tsx lines 1-4: createFileRoute, zod, @lingui/core/macro, @lingui/react/macro)_

## texts.json shape

Optional: `fixes` — exact replacements after the fact-check, copied from `out/factcheck.json`: `[{"field": "overview.how", "old": "…", "new": "…"}]` (fields as in findings.json: overview.what/how/affects, qa.core_path[i], qa.edge_cases[i], findings.<id>.issue/title/explanation/fix); `process` / `process_overrides` as in findings-format.md.

```json
{
 "earlier": {
  "CR1": {
   "status": "fixed",
   "note": "portsRouter.list now follows ports_links next pages (visited-guarded loop) and returns the full list."
  },
  "CR2": {
   "status": "partly",
   "note": "403 is now a page-level info Message on both details and list; 401 is still not a redirect: details shows a 'Sign in' error page, list falls into the generic 'Failed to Load Ports' boundary."
  },
  "CR3": {
   "status": "fixed",
   "note": "The route loader is gone; only the component's useQuery fetches the port."
  },
  "CR4": {
   "status": "dropped",
   "note": "Merge conflicts are no longer part of this review; GitHub shows them."
  },
  "P1": {
   "status": "open",
   "note": "PR is still a draft."
  },
  "P2": {
   "status": "fixed",
   "note": "The description now covers the ?tab= search param on routers/$routerId.tsx."
  },
  "I1": {
   "status": "fixed",
   "note": "Copy now reads 'Sign in again to continue.'"
  },
  "I2": {
   "status": "fixed",
   "note": "PopupMenu now has a PopupMenuToggle wrapping the icon Button."
  },
  "I3": {
   "status": "fixed",
   "note": "gap=\"1\" is gone; PortDetailsView uses \"0.5\", \"2\", \"6\", which the B.3 table allows."
  },
  "I4": {
   "status": "fixed",
   "note": "Status is now the 2nd column, right after Name / ID."
  },
  "I5": {
   "status": "fixed",
   "note": "Routers doc now says lookups are chunked into requests of at most 50 IDs."
  },
  "I6": {
   "status": "fixed",
   "note": "Error tables in the ports doc carry the ': {Neutron message}' suffix again."
  },
  "I7": {
   "status": "fixed",
   "note": "The useEffect is gone; PageInput is keyed on currentPage instead."
  },
  "I8": {
   "status": "fixed",
   "note": "zod is now imported right after the router import, before the Lingui imports."
  }
 },
 "confidence": "High | Medium | Low",
 "findings": {
  "c1": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c3": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c6": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  }
 },
 "merge": {},
 "provenance_extra": []
}
```
