# Compose findings — review-and-comment-pr

Write `texts.json` in the run folder (shape at the end), then run
`python3 .claude/skills/review-and-comment-pr/scripts/assemble.py --run <run folder> --texts`
and `render.py`. Scores, severity, category and location are the scorers' — don't change them.
Text rules, code placeholders and `[[ref:<id>]]` are in `references/findings-format.md`.
A finding's precedent (existing pattern / deferred) is the scorer's tag — render.py shows it; don't repeat it in the explanation.

## Look alike — same problem?

If a pair below is one problem, put `"merge": {"<drop id>": "<keep id>"}` in texts.json and give the kept one the other's evidence; otherwise leave both.

- `c14` and `c26` — shares `networks`

## Findings

### `c15` — Major · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:42` · score 75
- **Claim** (finder-f): networks.list forwards project_id (from projectScopedInputSchema) to Neutron as a filter, so networks the user may see but does not own (shared networks, external/provider networks owned by another project) are hidden from the list.
- **Scorer:** list destructures only searchTerm/status, so project_id from projectScopedInputSchema stays in openstackFilters and is sent to Neutron as a filter at line 42. The API reference says the default policy also returns networks shared with the project, so the filter hides shared and external networks that the default policy lets the user see (precedent: list filter hides visible resources = Major).
- **Precedent:** securityGroupRouter.ts:80-87 fetches own (project_id, shared=false) plus shared (shared=true) and merges; floatingIpRouter lists external networks via router:external=true.
- **Evidence:**

Code: `const { searchTerm, status, ...openstackFilters } = input` then `const queryParams = appendQueryParamsFromObject(openstackFilters)`; input extends projectScopedInputSchema (`project_id: z.string().trim().min(1, ...)`, trpc.ts:143-144), so project_id=<id> is sent. Reference (https://docs.openstack.org/api-ref/network/v2/#list-networks, networks.inc): 'Default policy settings return only networks that the project who submits the request owns, unless an administrative user submits the request. In addition, networks shared with the project who submits the request are also returned.' project_id is a documented filter (`project_id: project_id-query`), so filtering by it excludes shared networks and external networks owned by other projects. The same-PR-era securityGroupRouter works around this by fetching own and shared separately and unioning. Note also for admin tokens the unfiltered call would return all projects, so the filter is a behaviour choice that should be explicit.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c1` — Moderate · Performance · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:124` · score 75
- **Claim** (finder-a): The detail route's loader already fetches the network via getById, and RouteComponent then fetches the same network again with trpcReact getById.useQuery. The loader only uses the result for the page title, so every detail visit makes two identical requests.
- **Scorer:** Loader calls network.networks.getById.query (l.124) only for the title, and RouteComponent calls trpcReact getById.useQuery with the same input (l.149), so each detail visit fetches the same network twice. Matches the precedent row 'same data fetched twice (loader + useQuery)'.
- **Evidence:**

A.3: 'Data critical for rendering a page must be fetched via the route's loader function rather than loading it inside the component body.' Loader line 124 calls context.trpcClient?.network.networks.getById.query; line 149 calls trpcReact.network.networks.getById.useQuery with the same input.


### `c13` — Moderate · Conflict · `PR files` · score 75
- **Claim** (finder-c): Same work as open draft PR #1385 (Neutron Networks BFF + read-only Networks list/details). Both add the same networks.tsx, networks/index.tsx, $networkId.tsx, -components/*, networksRouter.ts, networkHelpers.ts, types/network.ts and the nav entry. Whichever merges second hits real conflicts in 9 non-generated files, so one of them is wasted effort.
- **Scorer:** context.json overlapping_prs lists open draft PR #1385 sharing the same networks routes, components, networkHelpers.ts and nav files. Work duplicated in another open PR is the Moderate 'Conflict' precedent. It is a different problem from C22 and C24.
- **Review discussion:** Nothing in the discussion mentions #1385.
- **Evidence:**

context.json overlapping_prs: #1385 shares 18 files, merge conflicts in 9 non-generated files (networksRouter.ts, types/network.ts, networkHelpers.ts, NetworksList.tsx, NetworkDetailsView.tsx, etc.), conclusion conflicts_only_generated=False. git diff --stat of #1385 head 9ed42505 shows a superset: a changeset, docs/0017_networks_bff.md and tests for components, router, helpers and types. This PR adds no tests or changeset. The PR body does not mention #1385.


### `c2` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:65` · score 50
- **Claim** (finder-a): A 401 is handled inline: NetworkLoadError renders an error message ('The session has expired...') in the page instead of redirecting to Sign-in. 403 also renders a plain error page without the page-level info Message explaining the lack of access.
- **Scorer:** UNAUTHORIZED and FORBIDDEN are mapped to inline error descriptions (l.63-66) rendered by NetworkLoadError, with no redirect to Sign-in or page-level info Message. Matches the precedent row '401/403 handled inline instead of redirect / page-level message' (Low). The parent _auth route may also handle sessions, so impact is limited. This is a different problem from the C3 copy wording.
- **Evidence:**

B.6 Reject: 'a 401/403 handled inline instead of via redirect / page-level info Message'. Lines 63-66 map FORBIDDEN and UNAUTHORIZED to error descriptions in RouteIdLevelDefaultError.


### `c3` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:66` · score 75
- **Claim** (finder-a): The UNAUTHORIZED copy says 'Log in again to continue.' The UX writing rule requires 'Sign in', and the recommended 401 copy is 'Authentication failed. Verify your credentials and try again.'
- **Scorer:** l.66 reads 'The session has expired. Log in again to continue.' Quick Reject lists strings using 'Log in' (use 'Sign in'), so this is a verified checklist violation scoring at least 75. It is only wording, so Low. It is a different problem from C2's inline-vs-redirect handling.
- **Evidence:**

Quick Reject: 'String using ... "Sign In"/"Log in" (use "Sign in")'. B.19: '"Sign in", not "Sign In" or "Log in"'.


### `c4` — Low · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:69` · score 75
- **Claim** (finder-a): A raw <button> is used for the 'Try Again' action in the subnets error state, where Juno's Button exists. It has no Juno styling or variant.
- **Scorer:** l.69 uses a raw <button onClick={() => refetch()}> as the Status action, while Juno Button is available (and used in $networkId.tsx). This violates the Quick Reject item 'Raw HTML element (<div>, <table>, <button>) where a Juno component exists'. Severity Low per precedent.
- **Evidence:**

B.1 Reject: 'any PR that introduces a plain <table>, <input>, <select>, or <button> where a Juno equivalent exists.' Line 69: action={<button onClick={() => refetch()}>{t`Try Again`}</button>}. Quick Reject: 'Raw HTML element (<div>, <table>, <button>) where a Juno component exists'.


### `c6` — Low · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:109` · score 75
- **Claim** (finder-a): The active detail tab is held in useState instead of the URL search params, so the Subnets tab is not shareable and is lost on refresh.
- **Scorer:** l.109 `const [activeTab, setActiveTab] = useState<NetworkDetailsTab>("overview")` keeps the active tab in useState, so it is lost on refresh and can't be shared. This violates the Quick Reject item 'URL-worthy state held in useState instead of search params' and B.9 lists 'Active tab'. Severity Low per precedent.
- **Evidence:**

B.9: 'All persistent UI state must live in URL search params' with 'Active tab | tab'; 'Reject any useState for state that should survive a page refresh or be shareable via URL.' Line 109: const [activeTab, setActiveTab] = useState<NetworkDetailsTab>("overview"). Quick Reject: 'URL-worthy state held in useState instead of search params'.


### `c7` — Low · Accessibility · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:56` · score 75
- **Claim** (finder-a): The row action menu uses <PopupMenu> without a PopupMenuToggle trigger (default toggle), contrary to the required pattern <PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>.
- **Scorer:** l.56-60 render <PopupMenu><PopupMenuOptions> with no PopupMenuToggle (not imported). This violates the Quick Reject item '`PopupMenu` without `PopupMenuToggle` as trigger' and B.14. The default toggle works visually, so Low.
- **Evidence:**

Quick Reject: 'PopupMenu without PopupMenuToggle as trigger'; B.14: 'Context menus must use <PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle> as the trigger.' Lines 56-60 render <PopupMenu><PopupMenuOptions>...</PopupMenuOptions></PopupMenu> with no PopupMenuToggle; PopupMenuToggle is not imported.


### `c8` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:43` · score 75
- **Claim** (finder-a): Network status is rendered as plain text in the list (and detail Overview) instead of a Badge status indicator.
- **Scorer:** Line 43 renders `<DataGridCell>{network.status}</DataGridCell>` as plain text, and NetworkDetailsView.tsx:116 does the same. copilot-instructions B.1 says status indicators use `Badge`, so this is a verified standards violation with cosmetic impact.
- **Evidence:**

B.1: 'Status indicators | Badge'. Line 43: <DataGridCell>{network.status}</DataGridCell>; NetworkDetailsView.tsx:116 value: network.status.


### `c9` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:46` · score 75
- **Claim** (finder-a): Admin state is shown as 'UP' / 'DOWN', all-caps strings, which the UX writing rule forbids.
- **Scorer:** Line 46 renders t`UP` / t`DOWN` (same at NetworkDetailsView.tsx:117). The Quick Reject checklist lists a 'String using ... all-caps' item, and the UX writing rules say 'Never all-caps (ever)'. This is a different problem from C8 (wording, not component choice); Low per the precedent table.
- **Evidence:**

Quick Reject: 'String using ... all-caps'; B.19: 'Never all-caps (ever)'. Line 46: network.admin_state_up ? t`UP` : t`DOWN`; same in NetworkDetailsView.tsx:117.


### `c10` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:132` · score 50
- **Claim** (finder-a): The label 'Created At' and 'Updated At' capitalise the short preposition 'At', which title-case rules require lowercase.
- **Scorer:** Lines 132-133 use t`Created At` and t`Updated At`. The title-case rule keeps short prepositions such as 'at' lowercase, so this is verified. It is only a wording nit, so 50 and Low.
- **Evidence:**

B.19: 'Lowercase ... short prepositions (max 5 letters: at, by, for, in, of, on, to, up...)'. Lines 132-133: t`Created At`, t`Updated At`.


### `c11` — Low · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkListContainer.tsx:36` · score 75
- **Claim** (finder-a): NetworkListContainer mirrors the currentPage prop into inputPage state through a useEffect. This synchronisation can be handled during render or by keying, and costs an extra render on every page change.
- **Scorer:** Lines 36-38 use a useEffect to copy the currentPage prop into inputPage state. This is the prop-to-state sync that copilot-instructions A.1 ('Minimize useEffect') says to flag. The only cost is an extra render, so Low.
- **Evidence:**

A.1: 'Critically evaluate every useEffect hook. Flag synchronizations, computed states ... that can be handled during rendering'. Lines 36-38: useEffect(() => { setInputPage(currentPage.toString()) }, [currentPage]).


### `c14` — Low · Docs · `apps/dashboard/.env.example:11` · score 50
- **Claim** (finder-e): The PR adds a new `networks` service key to buildNavSections (gated by isEnabled("networks")), but the comment listing the available enabledServices keys was not updated, so operators reading it do not learn that `networks` can be whitelisted. A deployment that sets VITE_ENABLED_SERVICES per the documented list will silently hide the new Networks nav entry.
- **Scorer:** Line 11 still reads '# Available keys: images, flavors, securitygroups, floatingips, containers, ceph-containers, pca'; the PR adds isEnabled("networks") but not the key here, so an operator following the list would hide the Networks nav. Rare and cosmetic; routers was already missing.
- **Precedent:** Existing keys (securitygroups, floatingips) are all listed there; routers is also missing, so the list was already incomplete.
- **Evidence:**

At the head commit, apps/dashboard/.env.example:11 reads '# Available keys: images, flavors, securitygroups, floatingips, containers, ceph-containers, pca'. packages/aurora/README.md:183 and :210 list the same set of service keys. The PR's changed files (context.json) touch neither. buildNavSections.ts:60 now uses isEnabled("networks").


### `c16` — Low · Performance · `packages/aurora/src/server/Network/routers/networksRouter.ts:44` · score 50
- **Claim** (finder-f): The list call sends no limit/marker and does not follow next links, so if Neutron pagination is enabled with a max page size, only the first page is shown with no indication of truncation.
- **Scorer:** The list call sends no limit/marker and ignores next links. The quoted reference says pagination is optional and gives no finite default, so Neutron returns everything by default and only a deployment-configured cap truncates silently (precedent: API returns everything by default = Low). It is a different problem from C15 (page size vs owner filter).
- **Evidence:**

Code: `network.get(withQuery(NETWORKS_BASE_URL, queryParams))`, then `const { networks } = parseOrThrow(NetworkListResponseSchema, data, ...)`; schema has only `networks`, no `networks_links`. Reference (https://docs.openstack.org/api-ref/network/v2/#pagination, intro.inc): 'To reduce load on the service, list operations will return a maximum number of items at a time. To navigate the collection, the parameters limit, marker and page_reverse can be set in the URI.' ... 'If the client requests a limit beyond the maximum limit configured by the deployment, the server returns the maximum limit number of items.' ... 'list responses contain atom next links and previous links.' Also: 'Pagination is an optional feature ... If pagination is disabled, the pagination parameters will be ignored and return all the items.' The reference gives no numeric default or max (deployment configured). User sees only the first page when there are more networks, silently; subnet_count/search/status filters apply to that page only.


### `c17` — Low · Bug · `packages/aurora/src/server/Network/types/network.ts:61` · score 50
- **Claim** (finder-f): NetworkSortKeySchema accepts `shared`, which Neutron's documented network sort keys do not include.
- **Scorer:** NetworkSortKeySchema allows 'shared' (line 61) with the comment 'supported by Neutron', while the reference limits sort keys to admin_state_up, availability_zone_hints, id, mtu, name, status, tenant_id, project_id. sort_key=shared would be forwarded and be rejected or ignored; it only matters if the UI offers that sort, so Low.
- **Evidence:**

Code: `export const NetworkSortKeySchema = z.enum(["name", "status", "admin_state_up", "shared"])` with comment 'Sort keys supported by Neutron'. Reference (https://docs.openstack.org/api-ref/network/v2/#list-networks, parameters.yaml network-sort_key): 'The sort keys are limited to: admin_state_up, availability_zone_hints, id, mtu, name, status, tenant_id, project_id'. `shared` is not listed; sort_key=shared is forwarded to Neutron unchanged, so the comment is wrong and the request may be rejected or ignored. Also sorting is only honoured 'if Neutron configuration supports it with allow_sorting=true' (filtering-list.inc), and the BFF has no fallback sort.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c24` — Low · Test coverage · `PR files` · score 50
- **Claim** (describer (acceptance)): Acceptance criterion unmet: Complete testing coverage (unit, integration, E2E) is achieved.
- **Scorer:** Issue #1019 lists 'Complete testing coverage' as an acceptance criterion and a QA task, so the standards of the epic require tests. The PR adds no tests for the router, helpers or components, and the PR body does not limit the scope for tests. Low per the precedent table.
- **Evidence:**

The diff has no tests for `networksRouter.ts`, `networkHelpers.ts` or any new component. Only `buildNavSections.test.ts` changed, and the unchecked boxes in `pr-body.md` confirm "I have added tests" is unticked. No E2E was added. `pr-body.md` does not limit scope for testing.


### `c25` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/index.tsx:87` · score 50
- **Claim** (describer (stale caller)): Stale caller of `isEnabled("networks") / project home service cards`: The project home page builds Network cards for securitygroups, floatingips and routers but not networks, so Networks appears in the sidebar but not on the home page.
- **Scorer:** The Network cards at index.tsx:73-93 cover securitygroups, floatingips and routers, with no isEnabled("networks") card. buildNavSections.ts:60 does add the networks entry to the sidebar, so the home page is out of step with it. The effect is cosmetic and the sidebar still reaches Networks.
- **Evidence:**

The project home page builds Network cards for securitygroups, floatingips and routers but not networks, so Networks appears in the sidebar but not on the home page.


### `c26` — Low · Docs · `packages/aurora/README.md:183` · score 50
- **Claim** (describer (stale caller)): Stale caller of `Service key reference`: The README service-key list (also at line 210) does not include the new `networks` key, which is part of the public `enabledServices` contract. `routers` was already missing.
- **Scorer:** README.md:183 and :210 list the service keys without the new "networks" key, which this PR uses in isEnabled("networks") and which is part of the public enabledServices contract. The README is the stated source of truth for AuroraApp props. The omission is a docs gap only, and routers was already missing before this PR.
- **Evidence:**

The README service-key list (also at line 210) does not include the new `networks` key, which is part of the public `enabledServices` contract. `routers` was already missing.


## Scored below 50 (not in the report)

- `C5` 25: Raw <div> elements are used as layout wrappers (break-all wrapper in DetailsList, relative wrapper around ErrorBoundary in Networks) where J
- `C12` 25: A useEffect corrects an out-of-range page by calling onPageChange(1). This is derived state: safePage is already clamped during render, so t
- `C18` 25: status filter is applied BFF-side although Neutron documents a server-side `status` filter for list networks; combined with no pagination, f
- `C19` 25: listSubnets sends fields and network_id correctly but lists subnets with no pagination and under the same owner-only default policy, so subn
- `C20` 0: Acceptance criterion partly met: tRPC BFF is implemented with complete Zod schema validation for Networks.
- `C21` 0: Acceptance criterion partly met: Users can list, view, create, update, and delete networks (P1 & P2).
- `C22` 0: Acceptance criterion partly met: Advanced properties like MTU, Admin State, and Shared status are visible and manageable where appropriate (
- `C23` 0: Acceptance criterion partly met: Comprehensive error handling provides user-friendly feedback for Neutron errors (e.g., preventing deletion 

## Acceptance grading (for the summary)

- partly met: tRPC BFF is implemented with complete Zod schema validation for Networks.
- partly met: Users can list, view, create, update, and delete networks (P1 & P2).
- met: Network Detail view clearly lists associated Subnets (read-only reference or linked).
- partly met: Advanced properties like MTU, Admin State, and Shared status are visible and manageable where appropriate (P3).
- out of scope: Permission system correctly hides/disables actions for unauthorized users (e.g., creating shared/external networks usually requires admin rights).
- partly met: Comprehensive error handling provides user-friendly feedback for Neutron errors (e.g., preventing deletion of networks with active ports).
- met: All UI components follow the Aurora design system.
- unmet: Complete testing coverage (unit, integration, E2E) is achieved.

## texts.json shape

Optional: `fixes` — exact replacements after the fact-check, copied from `out/factcheck.json`: `[{"field": "overview.how", "old": "…", "new": "…"}]` (fields as in findings.json: overview.what/how/affects, qa.core_path[i], qa.edge_cases[i], findings.<id>.issue/title/explanation/fix); `process` / `process_overrides` as in findings-format.md.

```json
{
 "summary": "2–4 sentences",
 "confidence": "High | Medium | Low",
 "index_affected": "touched surface, ≤ 40 words, no verdict",
 "findings": {
  "c15": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c1": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c13": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c2": {
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
  "c4": {
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
  },
  "c7": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c8": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c9": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c10": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c11": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c14": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c16": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c17": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c24": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c25": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c26": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  }
 },
 "edge_cases": [
  "scenario behind each Bug finding, citing [[ref:<id>]]"
 ],
 "merge": {},
 "provenance_extra": []
}
```
