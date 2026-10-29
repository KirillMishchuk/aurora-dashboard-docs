# Scorer 3 — review-and-comment-pr, aurora-dashboard PR #1383

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `0a594e9eaf3055cb1c9a102f1aceae43420e7870`
- baseRefOid: `a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd...0a594e9eaf3055cb1c9a102f1aceae43420e7870 -- <path>`.

## Your role: scorer 3 of 4

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C15, C16, C18

## Candidates

The evidence is as the finders reported it, unchanged.

### C14 — from find-code-comments
- **Claim:** The PR adds a new `networks` service key to buildNavSections (gated by isEnabled("networks")), but the comment listing the available enabledServices keys was not updated, so operators reading it do not learn that `networks` can be whitelisted. A deployment that sets VITE_ENABLED_SERVICES per the documented list will silently hide the new Networks nav entry.
- **Location:** `apps/dashboard/.env.example:11`
- **Evidence:**

At the head commit, apps/dashboard/.env.example:11 reads '# Available keys: images, flavors, securitygroups, floatingips, containers, ceph-containers, pca'. packages/aurora/README.md:183 and :210 list the same set of service keys. The PR's changed files (context.json) touch neither. buildNavSections.ts:60 now uses isEnabled("networks").
- **Precedent:** Existing keys (securitygroups, floatingips) are all listed there; routers is also missing, so the list was already incomplete.

### C15 — from find-api-contract
- **Claim:** networks.list forwards project_id (from projectScopedInputSchema) to Neutron as a filter, so networks the user may see but does not own (shared networks, external/provider networks owned by another project) are hidden from the list.
- **Location:** `packages/aurora/src/server/Network/routers/networksRouter.ts:42`
- **Evidence:**

Code: `const { searchTerm, status, ...openstackFilters } = input` then `const queryParams = appendQueryParamsFromObject(openstackFilters)`; input extends projectScopedInputSchema (`project_id: z.string().trim().min(1, ...)`, trpc.ts:143-144), so project_id=<id> is sent. Reference (https://docs.openstack.org/api-ref/network/v2/#list-networks, networks.inc): 'Default policy settings return only networks that the project who submits the request owns, unless an administrative user submits the request. In addition, networks shared with the project who submits the request are also returned.' project_id is a documented filter (`project_id: project_id-query`), so filtering by it excludes shared networks and external networks owned by other projects. The same-PR-era securityGroupRouter works around this by fetching own and shared separately and unioning. Note also for admin tokens the unfiltered call would return all projects, so the filter is a behaviour choice that should be explicit.
- **Precedent:** securityGroupRouter.ts:80-87 fetches own (project_id, shared=false) plus shared (shared=true) and merges; floatingIpRouter lists external networks via router:external=true.

### C16 — from find-api-contract
- **Claim:** The list call sends no limit/marker and does not follow next links, so if Neutron pagination is enabled with a max page size, only the first page is shown with no indication of truncation.
- **Location:** `packages/aurora/src/server/Network/routers/networksRouter.ts:43`
- **Evidence:**

Code: `network.get(withQuery(NETWORKS_BASE_URL, queryParams))`, then `const { networks } = parseOrThrow(NetworkListResponseSchema, data, ...)`; schema has only `networks`, no `networks_links`. Reference (https://docs.openstack.org/api-ref/network/v2/#pagination, intro.inc): 'To reduce load on the service, list operations will return a maximum number of items at a time. To navigate the collection, the parameters limit, marker and page_reverse can be set in the URI.' ... 'If the client requests a limit beyond the maximum limit configured by the deployment, the server returns the maximum limit number of items.' ... 'list responses contain atom next links and previous links.' Also: 'Pagination is an optional feature ... If pagination is disabled, the pagination parameters will be ignored and return all the items.' The reference gives no numeric default or max (deployment configured). User sees only the first page when there are more networks, silently; subnet_count/search/status filters apply to that page only.

### C18 — from find-api-contract
- **Claim:** status filter is applied BFF-side although Neutron documents a server-side `status` filter for list networks; combined with no pagination, filtering only the first page.
- **Location:** `packages/aurora/src/server/Network/routers/networksRouter.ts:39`
- **Evidence:**

Code: `const { searchTerm, status, ...openstackFilters } = input` and helper `filterNetworksByBffParams` described as 'Filters Neutron doesn't support directly'. Reference (networks.inc List networks request params): `- status: network-status-query`; parameters.yaml: 'Filter the network list result by network status. Values are ACTIVE, DOWN, BUILD or ERROR.' So the comment in networkHelpers.ts is inaccurate; BFF could pass status through. (BFF compares case-insensitively, Neutron values are uppercase.)

### C17 — from find-api-contract
- **Claim:** NetworkSortKeySchema accepts `shared`, which Neutron's documented network sort keys do not include.
- **Location:** `packages/aurora/src/server/Network/types/network.ts:61`
- **Evidence:**

Code: `export const NetworkSortKeySchema = z.enum(["name", "status", "admin_state_up", "shared"])` with comment 'Sort keys supported by Neutron'. Reference (https://docs.openstack.org/api-ref/network/v2/#list-networks, parameters.yaml network-sort_key): 'The sort keys are limited to: admin_state_up, availability_zone_hints, id, mtu, name, status, tenant_id, project_id'. `shared` is not listed; sort_key=shared is forwarded to Neutron unchanged, so the comment is wrong and the request may be rejected or ignored. Also sorting is only honoured 'if Neutron configuration supports it with allow_sorting=true' (filtering-list.inc), and the BFF has no fallback sort.

### C19 — from find-api-contract
- **Claim:** listSubnets sends fields and network_id correctly but lists subnets with no pagination and under the same owner-only default policy, so subnets of a shared/external network owned by another project are not returned in the Subnets tab.
- **Location:** `packages/aurora/src/server/Network/routers/networksRouter.ts:92`
- **Evidence:**

Code: `appendQueryParamsFromObject({ network_id, fields: ["id","name","cidr","ip_version","gateway_ip","enable_dhcp"] })` then `service.get(withQuery(SUBNETS_BASE_URL, params))`. Reference (https://docs.openstack.org/api-ref/network/v2/#list-subnets, subnets.inc): 'Default policy settings return only subnets owned by the project of the user submitting the request, unless the user has administrative role.' (no 'shared' clause, unlike networks). network_id filter is documented (subnet-network_id-query). Fields check: all fields UI schema reads (id,name,cidr,ip_version,gateway_ip,enable_dhcp) are in the list, consistent. Pagination: no limit/marker/next as in the networks list (https://docs.openstack.org/api-ref/network/v2/#pagination).

### C20 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: tRPC BFF is implemented with complete Zod schema validation for Networks.
- **Location:** `packages/aurora/src/server/Network/types/network.ts:9`
- **Evidence:**

`packages/aurora/src/server/Network/types/network.ts:9-95` validates responses and inputs for list, get and subnets. Create, update and delete procedures and their schemas are missing. `pr-body.md` says "Read-only for now" and "Implements the read-view portion", so the missing writes are out of the PR's stated scope.

### C21 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: Users can list, view, create, update, and delete networks (P1 & P2).
- **Location:** `packages/aurora/src/server/Network/routers/networksRouter.ts:35`
- **Evidence:**

List (`networksRouter.ts:35`) and view (`networksRouter.ts:61`) are implemented. Create, update and delete (P2) are not. `pr-body.md`: "Read-only for now — no create/update/delete". The P2 part falls outside the stated read-view scope, and the P1 part is met.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-3 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

