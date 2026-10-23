---
type: pr-report
date: 2026-10-17
status: open
pr: [1386]
issue: [1019]
author: TilmanHaupt
branch: hack-valid
---

# PR #1386: feat(core): network and verify DO NOT MERGE

**Author:** @TilmanHaupt · **Status:** draft · **Base:** `main` ← `hack-valid`
**Size:** 47 files, +4361 / −5 · **Created:** 2026-10-16 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1386)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Low**

This draft, titled "DO NOT MERGE", combines two unrelated changes:

- a Neutron Networks BFF with read-only list and detail pages;
- 29 `.claude/` agent and skill files (+3043 lines), made trackable by a `.gitignore` change.

The networks code has real defects:

- the tag-filter key map is passed in the wrong argument shape;
- a search with no matches removes the search box;
- the search is kept in local state instead of the URL;
- a "Create Network" button is shown to everyone and only calls `console.log`.

The PR also collides with open PRs #1385, #1383 and #1377, and makes an unrelated half-edit to `routers/$routerId.tsx`. CI's `test` job fails because `buildNavSections.test.ts` was not updated for the new nav entry. The PR links no issue, so I graded acceptance against the networks epic #1019 (Phase 1). The PR leaves out the Phase 1 list filters and pagination.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category     | Issue                                                                         | Location                                                                                        |
| --- | ----------- | ------------ | ----------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| CR1 | 🟡 Moderate | Bug          | Tag-filter key map passed as `options`, so `tags-any`/`not-tags*` never reach Neutron | `packages/aurora/src/server/Network/routers/networksRouter.ts:106`                              |
| CR2 | 🟡 Moderate | UI/UX        | A search with no matches unmounts the search box: the user can't clear it              | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:99` |
| CR3 | 🟡 Moderate | UI/UX        | "Create Network" button shown without a permission check; click only logs              | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:54`                                            |
| CR4 | 🟡 Moderate | UI/UX        | Search term held in `useState` instead of URL search params                   | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:30`                                            |
| CR5 | 🟡 Moderate | Code Quality | Merge conflicts with open PRs #1385, #1383 (same feature) and #1377           | PR files (`networks*`, `networksRouter.ts`, `routeTree.gen.ts`, locales)                        |
| CR6 | 🟡 Moderate | Code Quality | Unrelated partial edit: `ROUTE_ID` inlined at 2 of 3 uses in the routers detail route | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/$routerId.tsx:58`                                                            |
| CR7 | 🟡 Moderate | Code Quality | `.gitignore` reopened for `.claude/skills` and `.claude/agents`; 29 tooling files shipped in a feature PR | `.gitignore:12`                                                                                 |
| CR8 | 🟡 Moderate | Performance  | Detail route fetches the network twice (loader + `useQuery`)                  | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId/index.tsx:20`                                                    |
| CR9 | 🟡 Moderate | Bug          | List never follows `networks_links`, so it can be silently truncated                  | `packages/aurora/src/server/Network/routers/networksRouter.ts:108`                              |
| P1  | —           | Process      | Draft titled "DO NOT MERGE"; CI `test` job failing                            | PR state                                                                                        |
| P2  | —           | Process      | PR body ("Test-PR") links no issue                                            | PR body                                                                                         |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Tag-filter key map passed in the wrong shape** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:106`
`appendQueryParamsFromObject(neutronParams, LIST_NETWORKS_QUERY_KEY_MAP)` passes the bare map as the second argument. The helper's signature is `(source, options?: AppendQueryParamsOptions)` and it reads `const { keyMap } = options ?? {}` (`packages/aurora/src/server/helpers/queryParams.ts:26-31`), so `keyMap` is `undefined` and nothing is renamed. `tags_any`, `not_tags` and `not_tags_any` are accepted by the input schema (`types/network.ts:131-133`), but they are sent to Neutron with underscores. The [Neutron API reference](https://docs.openstack.org/api-ref/network/v2/index.html) names these filters `tags-any` ("Resources that match any tag in this list will be returned."), `not-tags` and `not-tags-any`. The call typechecks because `Record<string,string>` is assignable to the all-optional options type. No client sends these filters yet, so the bug is latent but part of the procedure's contract. The sibling call in `routersRouter.ts:178` does it correctly. No test covers the built URL.
_Fix:_ `appendQueryParamsFromObject(neutronParams, { keyMap: LIST_NETWORKS_QUERY_KEY_MAP })`. Add a router test that asserts the query string.

**CR2 — A search with no matches hides the search box** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:99`
When `networks.length === 0`, the component returns early with only `ContentHeader` and `Status`. With a search active, that status says "No networks match your search. Clear the search to view all networks." The `SearchInput` and its `onClear` exist only in the non-empty branch (`:131-140`), so the user has no control to clear the search and must reload or navigate away. This breaks copilot-instructions B.2: "Reject any structure that … skips Zone 2 when search is available". On #1355 (routers), Copilot flagged the same pattern: "replaces the entire list, including search/sort controls, with a fallback that cannot retry or reset".
_Fix:_ Always render Zone 1 and Zone 2 (create and search), and put the loading, empty and no-match `Status` in place of the DataGrid only.

**CR3 — "Create Network" button without a permission check** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:54`
Lines 53-54 contain `// Check permissions (TODO: implement permission checking)` and `const canCreate = true // Placeholder`. The handler at `:56-59` only calls `console.log("Create network clicked")`, and `:121-127` renders the primary button for every user. This violates two Quick Reject items: "'Create' button rendered without permission check" and "UI control shown before permissions are resolved (not fail-closed)". The permission keys `network:networks:create|update|delete` already exist (`Network/routers/permissionRouter.ts:19-23`). The empty state at `:109` also says networks "can be created through the API or CLI", which contradicts the button.
_Fix:_ Drop the button until the create modal exists (Phase 2). Otherwise, gate it on `canUser` for `network:networks:create`, defaulting to `false` while loading.

**CR4 — Search state not in the URL** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:30`
`searchInput` and `searchTerm` live in `useState`, and the route declares no `validateSearch`. A refresh, a shared link or coming back from a network's detail page loses the search. This violates the Quick Reject item "URL-worthy state held in `useState` instead of search params", and B.9 lists `search`. The sibling `RoutersList` and the Floating IPs list keep search in URL params.
_Fix:_ Add `validateSearch` with `search` on the list route and derive the query input from `Route.useSearch()`.

**CR5 — Collides with other open PRs** · Code Quality · PR files
I checked each PR with `git merge-tree --write-tree --name-only` against this head:

- **#1385** (head `9ed42505`) and **#1383** (head `3e32ab04`) are competing implementations of the same feature. Both report add/add conflicts in `networks.tsx`, `NetworksList.tsx`, `networks/index.tsx`, `networkHelpers.ts`, `networksRouter.ts`, `types/network.ts` and the locales.
- **#1377** (Ports) conflicts in `routeTree.gen.ts`, `routers/$routerId.tsx`, `Network/routers/index.ts` and the locales.

Only one networks implementation can land.
_Fix:_ Decide which networks PR is the vehicle, and close or rebase the others. Drop the `$routerId.tsx` edit (CR6) to remove the conflict with #1377.

**CR6 — Unrelated half-edit to the routers detail route** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/$routerId.tsx:58`
The PR replaces `ROUTE_ID` with the string literal at `:58` (`useParams`) and `:117` (`createFileRoute`). The constant is still declared at `:11` and used at `:146`. `ROUTE_ID` was introduced in #1355 as the single source of truth. The edit is not needed for networks, and it also conflicts with #1377. It is likely a side effect of the route generator.
_Fix:_ Revert this file.

**CR7 — `.claude/` tooling shipped in a feature PR** · Code Quality · `.gitignore:12`
On the base, `.gitignore` ignored `.claude` entirely and no `.claude` files were tracked. This PR changes the rule to `.claude/*` + `!.claude/skills/` + `!.claude/agents/`, and adds 29 files (+3043 lines of agent/skill markdown and shell scripts). It also adds the unrelated ignore entries `tmp/aurora-reviews/`, `screenshots/` and `.playwright-mcp/`. Every contributor's local skills and agents become committable. Two files are near-duplicates (`.claude/agents/sap_juno_lookup.md` and `.claude/skills/verifyUI/agents/sap_juno_lookup.md`). No repo standard forbids this, but it reverses a deliberate ignore and is out of scope for a networks feature.
_Fix:_ Move the `.gitignore` and `.claude/**` changes to their own PR, where maintainers can decide whether the repo should track shared agent tooling.

**CR8 — Detail route double-fetches the network** · Performance · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId/index.tsx:20`
The loader (`:20-26`) calls `context.trpcClient?.network.networks.getById.query(...)`, but only to derive the page title. The component then calls `trpcReact.network.networks.getById.useQuery(...)` again (`:57-65`). The vanilla client and React Query don't share a cache, so every detail view runs two network GETs and two subnet GETs. Context: the routers and security group detail routes use the same loader-for-title pattern.
_Fix:_ Return the network from the loader and read it with `Route.useLoaderData()`. Alternatively, prefetch through the React Query utils so both reads hit one cache entry.

**CR9 — List does not paginate** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:108`
`list` makes one `GET v2.0/networks`, and `NetworkListResponseSchema` drops `networks_links`. The [API reference](https://docs.openstack.org/api-ref/network/v2/index.html) says "Pagination is an optional feature of OpenStack Networking API, and it might be disabled". When an operator sets a page limit, only the first page is returned, with no indication. The BFF-side `searchTerm` also searches only that page. Epic #1019 Phase 1 lists "DataGrid, pagination, and filters". Context: the other Network routers also make a single GET.
_Fix:_ Follow `next` links (or expose `limit`/`marker`) and add pagination to the list.

**P1 — Not mergeable as submitted** · Process · PR state
The PR is a draft titled "DO NOT MERGE", with the body "Test-PR". CI's `test` job fails because `buildNavSections.test.ts` asserts the exact network nav list (e.g. `["securitygroups", "floatingips", "routers"]`), and the new `networks` entry is now first. All other checks pass.
_Fix:_ Update `buildNavSections.test.ts`, write a real description and title, then mark the PR ready.

**P2 — No linked issue** · Process · PR body
The body links nothing. I graded acceptance against epic #1019 (Phase 1, at the reviewer's request), which the PR does not reference.

The PR meets these Phase 1 items:

- Zod schemas;
- `list` and `get` procedures (`getById`);
- a detail page with Status, MTU and Admin State;
- copy-to-clipboard for IDs.

It leaves these out:

- list filters for Status and Shared (I8);
- pagination (CR9).

The epic AC "Permission system correctly hides/disables actions" is contradicted by CR3. The PR also adds Phase 2 mutations (`create`, `update`, `delete`) with no UI.
_Fix:_ Add `Part of #1019` (or the Phase 1 sub-issue) to the body.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category     | Issue                                                                 | Location                                                                     |
| --- | ---------- | ------------ | --------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| I1  | 🟢 Low     | Docs         | Changeset claims an ErrorBoundary and a removed key map, neither of which is true | `.changeset/networks-management-phase1.md:9`                                 |
| I2  | 🟢 Low     | Bug          | Subnet lookup failure is shown as "No Subnets"                           | `packages/aurora/src/server/Network/routers/networksRouter.ts:56`            |
| I3  | 🟢 Low     | UI/UX        | 403 handled inline; raw `error.message` shown untranslated               | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:79`                         |
| I4  | 🟢 Low     | UI/UX        | `"- -"` placeholder with an unsupported "Juno house rule" comment; siblings use `—` | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId/-components/NetworkDetailsView.tsx:28`        |
| I5  | 🟢 Low     | UI/UX        | Placeholder says "Search by name" but the search also matches description       | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:139`                        |
| I6  | 🟢 Low     | UI/UX        | Dead `disabled={isLoading}`; no indicator while a new search loads        | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:149`                        |
| I7  | 🟢 Low     | Code Quality | Item count pluralised by concatenation instead of Lingui `plural`         | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:147`                        |
| I8  | 🟢 Low     | UI/UX        | Epic #1019 Phase 1 asks for Name/Status/Shared filters; only text search exists | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:129`                        |
| I9  | ⚪ Trivial | Code Quality | Import order deviates from B.13                                       | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId/index.tsx:1`                                  |
| I10 | ⚪ Trivial | Docs         | JSDoc promises "subnet and port details"; only subnets exist          | `packages/aurora/src/server/Network/types/network.ts:209`                    |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Changeset text doesn't match the code** · Docs · `.changeset/networks-management-phase1.md:9`
Three changeset claims don't hold:

- "Detail page includes … ErrorBoundary wrapper" (`:9`): no networks file uses an ErrorBoundary. The only error handling is the route `errorComponent` in `networks.tsx`.
- "Remove redundant query key mapping in networksRouter" (`:11`): the map is still at `networksRouter.ts:26` and used at `:106` (see CR1).
- The bullets read as a delta ("now shows", "now replace") for a feature that doesn't exist on the base.

The text becomes the public CHANGELOG entry.
_Fix:_ Rewrite the changeset as a plain description of the new feature.

**I2 — Subnet errors look like "no subnets"** · Bug · `packages/aurora/src/server/Network/routers/networksRouter.ts:56`
`fetchSubnetDetails` returns `[]` from `catch {}` on any failure. Its `if (!response.ok) return []` at `:53` never runs, because signal-openstack throws on non-2xx (see the `requestOrThrow` JSDoc in `routerHelpers.ts`). `NetworkDetailsView.tsx:84-89` then shows "No Subnets — This network has no subnets…" even when `network.subnets` is non-empty. The failure is rare, since the same token just read the network, but the message is wrong when it happens.
_Fix:_ Return a flag (e.g. `subnet_details: null` on failure) and render an error or "IDs only" fallback when `network.subnets.length > 0`.

**I3 — 403 handled inline** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:79`
A `FORBIDDEN` error is mapped to "You do not have permission to view networks." inside a component `Status`. Other errors show the raw `error?.message` (`:81`, and `$networkId/index.tsx:92`). B.6 says "Reject … a 401/403 handled inline instead of via redirect / page-level info Message". This is a partial match, because B.6 scopes component render errors to the component. Context: flavors and images handle FORBIDDEN inline too.
_Fix:_ Use the shared error-translation helper and the standard 403 copy.

**I4 — Placeholder value and comment** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId/-components/NetworkDetailsView.tsx:28`
`/** Empty-value placeholder (Juno house rule). */ const PLACEHOLDER = "- -"`. I found no such rule in Juno, and `"- -"` appears nowhere else in `packages/aurora/src`. The Floating IP views and tests use `—`.
_Fix:_ Use `—`, matching the sibling views, and drop the "house rule" claim.

**I5 — Search placeholder undersells the search** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:139`
The placeholder is "Search by name", but `filterNetworksByBffParams` (`networksRouter.ts:70-78`) matches `name` and `description`.
_Fix:_ "Search by name or description".

**I6 — Loading feedback** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:149`
`disabled={isLoading}` on Refresh is always false, because the loading branch returns at `:68`. `placeholderData: (prev) => prev` (`:46`) also keeps the previous results on screen, with no indicator, while a new search loads.
_Fix:_ Use `isFetching` for the Refresh button and for a subtle loading hint.

**I7 — Pluralisation** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:147`
`` {networks.length} {networks.length === 1 ? t`Network` : t`Networks`} `` is not safe for languages with more plural forms. The repo already uses Lingui `plural` (e.g. `CorsRulesTab.tsx`).
_Fix:_ `plural(networks.length, { one: "# Network", other: "# Networks" })`.

**I8 — Phase 1 filters missing** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:129`
Epic #1019 Phase 1: "Create Networks List View with DataGrid, pagination, and filters (Name, Status, Shared)". The BFF accepts `status` and `shared`, but the UI offers only a text search.
_Fix:_ Add Status and Shared filters, or record them as follow-up scope in the linked issue.

**I9 — Import order** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId/index.tsx:1`
The Juno import comes first, and `@/client/hooks/useSetBreadcrumb` (`:10`) comes after the local `./-components` import. In `NetworksList.tsx:1-17`, `trpcClient` comes after Juno. B.13 sets the required order.
_Fix:_ Reorder per B.13.

**I10 — Stale JSDoc** · Docs · `packages/aurora/src/server/Network/types/network.ts:209`
"enriched with subnet and port details", but `NetworkDetails` only adds `subnet_details`.
_Fix:_ Drop "and port".

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

The PR contains three unrelated groups of change.

**1. Networks feature (product code, `packages/aurora`).**

- A new `networksRouter` is registered as `network.networks`. It exposes `list`, `getById`, `create`, `update` and `delete` on Neutron `v2.0/networks`, with Zod request/response schemas and resource-specific error handlers.
- `getById` enriches the network with subnet details from `v2.0/subnets?id=…`.
- On the client there is a new `network/networks` route group:
  - a list page (`NetworksList`): name, ID with copy, status, admin state, shared, external; text search, item count, Refresh and a placeholder "Create Network" button;
  - a detail page (`NetworkDetailsView`): an info list, a subnets table, and a provider section shown only when provider attributes are present.
- "Networks" is added first in the Network nav group (`buildNavSections.ts`).
- Lingui catalogs and `routeTree.gen.ts` are regenerated, and a `minor` changeset is added.
- Only `list` and `getById` are used by the UI. `create`, `update` and `delete` have no consumer yet.

**2. Unrelated edits.** `routers/$routerId.tsx` swaps the `ROUTE_ID` constant for an inline literal in two of its three uses.

**3. Agent tooling.** The PR adds 29 files under `.claude/agents` and `.claude/skills`:

- `aurora-bff-review`, `aurora-ui-review` (including a 764-line `build-datagrid` skill), `security-and-hardening`, `verify`, and `verifyUI` (with its `sap_juno_appkit` sub-skill);
- the `sap_juno_lookup` agent;
- three small shell scripts.

The `.gitignore` change un-ignores those two folders and ignores local review artifacts.

**CI:** every check passes except `test`. Two assertions in `src/client/routes/_auth/projects/-components/buildNavSections.test.ts` fail, because the expected network nav lists don't include `networks`.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**Server: router wiring.** The router is added to the existing Network domain tree, so its procedures are `network.networks.*`:

`packages/aurora/src/server/Network/routers/index.ts:16`

```ts
    routers: routersRouter,
    networks: networksRouter,
    ...buildNetworkPermissionRouter(policyDir),
```

**Server: list.** The list strips the BFF-only fields and forwards the rest as Neutron query params. A search term is then applied BFF-side over name and description. The second argument to `appendQueryParamsFromObject` is the bare key map, which is the defect in CR1:

`packages/aurora/src/server/Network/routers/networksRouter.ts:103`

```ts
        // Build query params for Neutron API (forward applicable filters)
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { project_id, searchTerm, ...neutronParams } = input
        const params = appendQueryParamsFromObject(neutronParams, LIST_NETWORKS_QUERY_KEY_MAP)

        const response = await requestOrThrow(
          () => network.get(withQuery(NETWORKS_BASE_URL, params)),
          NetworkErrorHandlers.list
        )
```

**Server: detail with subnet enrichment.** The network ID is validated and encoded through `validateAndEncodeResourceId` (`networkUrl`, `:37-40`). Subnets are fetched in one call with repeated `id` params, and any failure becomes `[]` (I2):

`packages/aurora/src/server/Network/routers/networksRouter.ts:48`

```ts
const fetchSubnetDetails = async (network: NetworkService, subnetIds: string[]): Promise<SubnetDetail[]> => {
  if (subnetIds.length === 0) return []
  try {
    const params = appendQueryParamsFromObject({ id: subnetIds })
    const response = await network.get(withQuery(SUBNETS_BASE_URL, params))
    if (!response.ok) return []
    const data = await response.json()
    return parseOrThrow(SubnetListResponseSchema, data, "networksRouter.subnets").subnets
  } catch {
    return []
  }
}
```

**Server: mutations.** `create` and `update` build the body with `pickDefined` and deliberately omit `project_id`, so Neutron derives ownership from the rescoped token. All five procedures use `projectScopedProcedure`, and none consult the policy engine. That matches the other Network routers. Error handlers in `networkHelpers.ts` map 400/404/409 to tRPC codes per operation.

**Server: schemas.** `NetworkSchema` keeps `status` as `z.string()`, so an unknown Neutron status does not break list parsing, and it defaults arrays and optional strings:

`packages/aurora/src/server/Network/types/network.ts:27`

```ts
  // Response field stays loose: an unknown Neutron status must not break the whole list parse
  status: z.string(),
  admin_state_up: z.boolean(),
  // Network type fields
  shared: z.boolean().default(false),
```

**Client: list page.** Search uses two pieces of local state, so the query re-runs only on submit. Loading, error and empty each return early, replacing the whole page body (CR2):

`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:99`

```tsx
  if (networks.length === 0) {
    return (
      <Stack direction="vertical" gap="4">
        <ContentHeader title={t`Networks`} projectId={projectId} />
        <Status
          status={hasSearch ? "no-matches" : "empty"}
          title={hasSearch ? t`No Matching Networks` : t`No Networks Found`}
```

The create control is a placeholder (CR3):

`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:53`

```tsx
  // Check permissions (TODO: implement permission checking)
  const canCreate = true // Placeholder

  const handleCreateClick = () => {
    // TODO: Open create network modal
    console.log("Create network clicked")
  }
```

Rows navigate to the detail route on click. `ClipboardText` stops propagation, so copying an ID doesn't navigate.

**Client: detail route.** `beforeLoad` redirects to the list if Neutron isn't in the service catalog. The loader fetches the network only for the page title, and the component fetches it again with `useQuery` (CR8):

`packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId/index.tsx:20`

```tsx
  loader: async ({ context, params }) => {
    const network = await context.trpcClient?.network.networks.getById.query({
      project_id: params.projectId,
      network_id: params.networkId,
    })
    return { networkTitle: network?.name || network?.id || null }
  },
```

`NetworkDetailsView` renders a `DescriptionList` with ID, name, description, status, admin state, shared, external, MTU and port security. It then shows a subnets `DataGrid` (name, CIDR, IP version, gateway, allocation pools, DHCP) or an empty `Status`. The provider section appears only when `provider:*` fields are present, and these are normally admin-only.

**Client: navigation.** `buildNavSections.ts:60` inserts `networks` before `securitygroups`, gated by `isEnabled("networks")`.

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

- **New tRPC surface `network.networks.*`.** The only consumers are this PR's own client files: `NetworksList.tsx` uses `list`, and `$networkId/index.tsx` uses `getById`. `create`, `update` and `delete` have no caller anywhere in the monorepo. Because the router is merged into the app router type, `AuroraRouter` gains these procedures for any consumer app.
- **Permission keys.** `network:networks:{read,list,create,update,delete}` already exist in `Network/routers/permissionRouter.ts:19-23`, mapped to the `networking.json` rules. The PR uses none of them.
- **Service key `"networks"`.** This is new in the nav (`buildNavSections.ts`) and in the routes' `staticData.service`. `packages/aurora/README.md`'s "Available service keys" list doesn't mention it (it doesn't list `routers` either). The project overview page (`$projectId/index.tsx`), which lists `securitygroups` and `routers` cards, was not updated.
- **Stale test.** `buildNavSections.test.ts` asserts exact network nav lists and was not updated, which is why CI fails.
- **Routers detail route.** It is touched without a functional change (CR6), and this creates a conflict with #1377.
- **Repository policy.** The `.gitignore` change affects every contributor: files under `.claude/skills/` and `.claude/agents/` now show up in `git status` and can be committed.
- **Competing PRs.** #1385 and #1383 implement the same feature under the same route paths and router key, so at most one of the three can land as is.

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Open a project that has Neutron. Under Network in the side nav, confirm "Networks" appears first.
2. Open Networks. Confirm the list shows Name, ID (truncated, with copy), Status, Admin State, Shared and External, plus the item count.
3. Copy an ID from a row. Confirm the clipboard has the full ID and the page does not navigate.
4. Search for part of a network name, then part of a description, and press Enter. Confirm both narrow the list. Clear the search and confirm the full list returns.
5. Click Refresh and confirm the list re-fetches.
6. Click a row. Confirm the detail page shows the header with the name, "Back to Networks", the Network Information list, the Subnets table (CIDR, IP version, gateway, allocation pools, DHCP) and, for admin users, Provider Network.
7. Check the browser tab title and the breadcrumb on the detail page.
8. Click "Back to Networks" and confirm you land on the list.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- **Search with no matches** (`NetworksList.tsx:99-114`): confirm the search box disappears and the search can't be cleared (CR2).
- **Search and refresh:** refresh the page or come back from a detail page after searching. The search term is lost (CR4).
- **Create button** (`NetworksList.tsx:121-127`): log in as a reader-only user. The button is still shown, and clicking it only logs to the console (CR3).
- **Project with no networks:** expect "No Networks Found". Note that the Create button and search are gone too.
- **Network without a name:** the list shows the ID in the Name column (`:167`), and the detail header uses the ID.
- **Network with no subnets:** expect "No Subnets".
- **Subnet API failure** (block `v2.0/subnets`): the detail page still says "No Subnets" (I2, `networksRouter.ts:53-57`).
- **Non-existent network ID in the URL:** the loader throws, and `NetworksErrorComponent` (`networks.tsx:8-25`) shows the route error with "Back to Networks".
- **Neutron missing from the catalog** (`$networkId/index.tsx:37-42`): the detail route redirects to the list.
- **403 on list:** expect "You do not have permission to view networks." inline (I3).
- **Network tab:** check that each detail view issues two `getById` calls (CR8).
- **Deployment with Neutron pagination** (`pagination_max_limit`): the list shows only the first page, and search misses networks on later pages (CR9).
- **`tags_any` passed via tRPC directly:** Neutron receives the unmapped `tags_any=<value>` and does not filter (CR1).
- **Shared or external networks from other projects:** check that Shared and External show "Yes".
- **Routers detail page** (`routers/$routerId.tsx`): check that it still loads and shows its error state. This is a regression check for CR6.

</details>

---

_Analyzed 2026-10-17 · commit `e6b1e69` · read-only, CI from PR API, earlier automated report comment excluded from review discussion · skill: review-and-comment-pr_

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-10-12 · [2026-10-12-networks-epic-1019-analysis](../../plans/2026-10-12-networks-epic-1019-analysis.md)
- plan · 2026-10-12 · [2026-10-12-networks-phase-1-read-operations](../../plans/2026-10-12-networks-phase-1-read-operations.md)
- pr-report · 2026-10-17 · [1385-neutron-networks-bff-read-only-networks-page](1385-neutron-networks-bff-read-only-networks-page.md)
- pr-report · 2026-10-23 · [1383-neutron-networks-bff-read-only-networks-page](1383-neutron-networks-bff-read-only-networks-page.md)
