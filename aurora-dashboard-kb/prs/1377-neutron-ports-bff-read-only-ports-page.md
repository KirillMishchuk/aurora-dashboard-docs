---
type: pr-report
date: 2026-10-17
status: open
pr: [1377]
issue: [1381, 1382]
author: mark-karnaukh-extern-sap
branch: mark-manage-ports-interface
---

# PR #1377: feat(aurora): add Neutron Ports BFF and read-only Ports page (list & details)

**Author:** mark-karnaukh-extern-sap · **Status:** draft · **Base:** `main` ← `mark-manage-ports-interface`
**Size:** 42 files, +5094 / −247 · **Created:** 2026-10-09 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

This is a well-structured feature. The BFF batches its name lookups and falls back to IDs when a name can't be resolved, and Routers now share the same helpers. The UI keeps search, sort and page in the URL, offers retries, and hides the Network column when the list is scoped to one network. Everything that #1381 and #1382 ask for is present, and all CI jobs pass.

Four 🟡 items block it:

- `network.ports.list` reads only the first page Neutron returns.
- The port details page shows 401 and 403 errors in the page instead of redirecting or using a page-level message.
- The details route fetches the same port twice.
- The branch conflicts with `main` (generated locale files) and with the open Networks PRs #1383 and #1385.

Two process to-dos remain: the PR is still a draft, and its description doesn't mention the change to the Router details tab. Confidence is Medium because of the draft state. The pagination impact also depends on how each deployment configures Neutron.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category     | Issue                                                                                          | Location                                                                                   |
| --- | ----------- | ------------ | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| CR1 | 🟡 Moderate | Bug          | Ports list reads one Neutron page only; ports and search hits beyond it silently disappear      | `packages/aurora/src/server/Network/routers/portsRouter.ts:65`                             |
| CR2 | 🟡 Moderate | UI/UX        | 401/403 rendered inline on the details page and as a list error (B.6 Reject)                    | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:64` |
| CR3 | 🟡 Moderate | Performance  | Details route fetches the port twice (loader + `useQuery`), ~8 Neutron requests per open        | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:127` |
| CR4 | 🟡 Moderate | Code Quality | Merge conflicts with `main` (locales) and with open PRs #1383 / #1385 (`routers/index.ts`)       | `packages/aurora/src/server/Network/routers/index.ts:17`                                   |
| P1  | —           | Process      | PR is still a draft                                                                             | PR state                                                                                   |
| P2  | —           | Process      | Description doesn't mention that the Router details tab now lives in the URL (`?tab=`)          | PR body                                                                                    |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Ports list ignores Neutron pagination** · Bug · `packages/aurora/src/server/Network/routers/portsRouter.ts:65`
`list` makes one `GET v2.0/ports` and parses only `{ ports }` (`PortListResponseSchema`, `types/port.ts:77`). There is no `limit`/`marker` input and nothing follows `ports_links`. The Neutron API reference ([Pagination](https://docs.openstack.org/api-ref/network/v2/index.html)) says: "To reduce load on the service, list operations will return a maximum number of items at a time." On a deployment that sets `pagination_max_limit`, a project with more ports gets a silently truncated list. The BFF-side search (`filterPortsBySearchTerm`) and the client-side pagination (`PortsList.tsx:96-98`) then work only on that first page, so a port the user searches for can go missing without any hint. With Neutron's default (no limit) this works. The existing Routers list has the same pattern.
_Fix:_ Follow the `next` link in `ports_links` (or loop with `limit` + `marker`) until it is exhausted before resolving names and searching.

**CR2 — 401/403 handled inline** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:64`
`PortLoadError` maps `FORBIDDEN` to "Access to this port is not permitted." and `UNAUTHORIZED` to "The session has expired. Log in again to continue." It renders both in `RouteIdLevelDefaultError` with Back/Home buttons (`$portId.tsx:64-75`, used at `:165-167`), with no redirect to sign-in and no info `Message`. The list does the same for 403: `PortsList.tsx:54-55` turns `FORBIDDEN` into `listError`, and `:115-116` renders it as an error `Status` with the raw BFF message. `copilot-instructions.md` B.6 says to reject "a 401/403 handled inline instead of via redirect / page-level info `Message`". The Routers details page and the Floating IP details page do the same.
_Fix:_ Send 401 into the sign-in redirect, and render 403 as the page-level permission state with an info `Message`.

**CR3 — Double fetch on the details route** · Performance · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:127`
The loader calls `context.trpcClient?.network.ports.getById.query(...)` only to set the page title (`:127-137`). The component then calls `trpcReact.network.ports.getById.useQuery(...)` with the same input (`:154-157`). The vanilla client and the React Query hook don't share a cache, so every open runs `getById` twice. Each run is one port GET plus three batched lookups (networks, subnets, security groups), so the page costs about eight Neutron requests instead of four, and the loader delays the first render. Copilot raised the same thing on Routers PR #1355 ([thread](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1355#discussion_r4206303342)). The maintainer replied that it follows `$flavorId.tsx` and would be fixed across routes separately, so expect that answer here.
_Fix:_ Drop the loader query and derive the title from the component's query, or prefetch through the shared query client (`ensureQueryData`) so both read one cache entry.

**CR4 — Merge conflicts** · Code Quality · `packages/aurora/src/server/Network/routers/index.ts:17`
`git merge-tree` against current `main` (`a21ba3ec`) conflicts in `packages/aurora/src/locales/{de,en}/messages.{po,ts}`. Against the open Networks PRs #1383 and #1385 it also conflicts in `Network/routers/index.ts`, where both register a router on the same lines. #1385 also conflicts in `routeTree.gen.ts` and `buildNavSections.test.ts`. #1385 contains byte-identical copies of the extracted `requestHelpers.ts` / `lookupHelpers.ts`, which merge cleanly. All of these are mechanical (keep both registrations, regenerate), but every one of the three PRs will need a rebase once another lands.
_Fix:_ Rebase on `main` and run `pnpm check-i18n` to regenerate the locales. Agree a merge order with #1383 / #1385, and keep both `ports` and `networks` in `routers/index.ts`.

**P1 — Draft** · Process · PR state
The PR is still marked as a draft.
_Fix:_ Mark it ready for review once the Required Changes are addressed.

**P2 — Description omits the Router tab change** · Process · PR body
The last commit (`512f01b1`, "keep router details tab in URL search params") adds `validateSearch` with a `tab` search param to `routers/$routerId.tsx` (`:135-138`). It also turns `RouterDetailsView`'s tab into a controlled prop. This changes Routers behaviour that users can see. The description's "Fix" section mentions only the `createFileRoute` string literal, and neither the changeset nor `0010_routers_bff.md` mentions the change.
_Fix:_ Add a line about it to the description (and to the changeset if it should appear in the release notes), or move it into its own PR.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category     | Issue                                                                     | Location                                                                                                     |
| --- | ---------- | ------------ | ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| I1  | 🟢 Low     | UI/UX        | "Log in again to continue." — Quick Reject wording (use "Sign in")         | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:71`                    |
| I2  | 🟢 Low     | Code Quality | `PopupMenu` without `PopupMenuToggle` trigger (Quick Reject)               | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:79`   |
| I3  | 🟢 Low     | Code Quality | `gap="1"` is not an approved spacing value (Quick Reject, B.3)             | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortDetailsView.tsx:51` |
| I4  | 🟢 Low     | UI/UX        | Status is the 6th of 7 columns; B.15 puts status near the left             | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:84` |
| I5  | 🟢 Low     | Docs         | Routers doc still says names come from "one request" — now chunked by 50    | `packages/aurora/docs/0010_routers_bff.md:80`                                                                |
| I6  | 🟢 Low     | Docs         | Ports doc error tables drop the `: {Neutron message}` suffix               | `packages/aurora/docs/0017_ports_bff.md:103`                                                                 |
| I7  | ⚪ Trivial | Code Quality | `useEffect` mirrors the `currentPage` prop into state                      | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:37` |
| I8  | ⚪ Trivial | Code Quality | `zod` imported after the Lingui imports (B.13 order)                       | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/index.tsx:4`                       |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — "Log in" wording** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:71`
The Quick Reject Checklist bans strings using `"Sign In"`/`"Log in"` (use `"Sign in"`), and B.19 repeats it. The 401 description reads "The session has expired. Log in again to continue." The same string is in `routers/$routerId.tsx:76`. It goes away if CR2 is fixed with a redirect.
_Fix:_ Change it to "The session has expired. Sign in again to continue."

**I2 — Bare `PopupMenu`** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:79`
Quick Reject: "`PopupMenu` without `PopupMenuToggle` as trigger". B.14 asks for `<PopupMenuToggle as="div"><Button icon="moreVert" … /></PopupMenuToggle>`. `FloatingIpTableRow.tsx` and `RouterTableRow.tsx` also rely on Juno's default trigger, and the maintainer kept it in #1355.
_Fix:_ Add an explicit `PopupMenuToggle` with a `moreVert` icon button and an `aria-label`.

**I3 — Ad-hoc spacing** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortDetailsView.tsx:51`
Quick Reject: "Ad-hoc spacing value not in the approved list (B.3)". The approved gaps are `0.5`, `2`, `4` and `6`. `gap="1"` is used here and at `PortTableRow.tsx:57`. `RouterTableRow.tsx` does the same.
_Fix:_ Use `gap="0.5"` or `gap="2"`.

**I4 — Status column position** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:84`
B.15 says "Status/state columns: near the left". Status is the 6th of 7 columns. Issue #1382 lists this exact column order, so it is probably intentional.
_Fix:_ Move Status after Name / ID, or confirm with the issue owner that the issue's order wins.

**I5 — Stale Routers doc** · Docs · `packages/aurora/docs/0010_routers_bff.md:80`
The Router name lookups now go through the shared `fetchSummaries` (`lookupHelpers.ts:30-39`), which splits IDs into chunks of `LOOKUP_CHUNK_SIZE = 50`. The doc still says "one request for external **and** private networks" (`:80`) and "two requests" (`:119`). The PR edited this doc elsewhere but left these lines.
_Fix:_ Say that the lookups send one request per 50 IDs.

**I6 — Ports doc error messages** · Docs · `packages/aurora/docs/0017_ports_bff.md:103`
`errorHandling.ts:25-54` appends `: ${response.statusText || "Unknown error"}` to every default message. The tables show "Invalid request data for Port" / "Unauthorized access to Port" without the suffix (`:103-104`, `:132`, `:196`, `:245`, `:282`), while `:195` does include `{Neutron message}`, so the doc contradicts itself.
_Fix:_ Add `: {Neutron message}` to the default-handler rows.

**I7 — Prop-to-state effect** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:37`
Part A says "Minimize useEffect … flag synchronizations". `useEffect(() => { setInputPage(currentPage.toString()) }, [currentPage])` mirrors a prop into state. `RouterListContainer.tsx` has the same code.
_Fix:_ Key the pagination input on `currentPage`, or derive the value during render.

**I8 — Import order** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/index.tsx:4`
B.13 puts `zod` in the framework group, before i18n. Here `import { z } from "zod"` comes after `@lingui/core/macro` and `@lingui/react/macro`.
_Fix:_ Move the `zod` import up, next to `@tanstack/react-router`.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

**BFF.** A new `network.ports` tRPC router has five project-scoped procedures (`list`, `getById`, `create`, `update`, `delete`) with Zod schemas for inputs and Neutron responses. `list` always sends the current `project_id` as a Neutron filter, can be narrowed to one network with `network_id`, and runs a case-insensitive search on the BFF. Both `list` and `getById` add network and subnet names, and `getById` also adds security group names. The names come from batched, best-effort lookups that fall back to IDs. Port-specific error handlers rewrite Neutron's 404 and 409 errors (IP or MAC in use, quota, port owned by a router) into clear messages. Only `list` and `getById` are used by the UI; the write procedures are BFF-only for now, as the description says.

**Shared helpers (refactor).** `requestOrThrow`, `pickDefined`, `chunk` and `withQuery` moved from the Routers files to `helpers/requestHelpers.ts`. The network and subnet name lookups moved to `helpers/lookupHelpers.ts`, which also gained a security group lookup, and the summary schemas moved to `types/index.ts`. Routers now use these shared versions. The only behaviour change for Routers is that name lookups are split into requests of 50 IDs each.

**UI.** The PR adds a Ports entry under Network in the side navigation and a Ports card on the project overview, both gated by `isEnabled("ports")`. The list page has the columns Name / ID, Description, Network, Fixed IPs / Subnet, Device Owner / ID and Status, a "Show Details" row action, and search, sort and page stored in the URL. The `Ports` component takes an optional `networkId`, which hides the Network column (prepared for the Ports tab of #1019). The details page lists every field from #1382, with copy-to-clipboard for the IDs, IPs and MAC.

**Routers fix (out of the Ports scope).** `routers/$routerId.tsx` now passes a string literal to `createFileRoute`, so the route generator works again. It also keeps the active details tab in a `?tab=` search param (see P2).

**Docs, tests, release.** New `docs/0017_ports_bff.md`, updates to `0010_routers_bff.md`, colocated tests for the schemas, helpers, router and components, and a `minor` changeset. All CI jobs pass on `512f01b1`.

**Acceptance criteria.** #1381 (Ports BFF): all procedures, Zod validation, project restriction and network filter, names with ID fallback, mapped errors, tests and docs are present. The list completeness gap is CR1. #1382 (list and details): navigation and overview entry, columns, URL-backed search/sort/pagination, the network-scoped variant, all detail fields and handling of missing data are present. "Follows the design system" is partly unmet (CR2, I2, I3).

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**List: one Neutron call, then names, then search** (`packages/aurora/src/server/Network/routers/portsRouter.ts:63`):

```ts
        // project_id is forwarded as a filter, so admin roles also only see the current project's ports here
        const queryParams = appendQueryParamsFromObject(openstackFilters, { keyMap: LIST_PORTS_QUERY_KEY_MAP })
        const response = await requestOrThrow(
          () => network.get(withQuery(PORTS_BASE_URL, queryParams)),
          PortErrorHandlers.list
        )

        const data = await response.json()
        const { ports } = parseOrThrow(PortListResponseSchema, data, "portsRouter.list")
```

`openstackFilters` is the input without `searchTerm`, so it still holds `project_id` from `projectScopedInputSchema`. The project restriction therefore comes from the Neutron filter, not from a check in the BFF. Names are resolved before the search so that search also matches network and subnet names (`portsRouter.ts:75-81`). `getById` does the same for a single port and also resolves security group names (`:97-105`).

**Batched best-effort lookups** (`packages/aurora/src/server/Network/helpers/lookupHelpers.ts:30`):

```ts
const fetchSummaries = async <T>(ids: string[], fetchChunk: (chunkIds: string[]) => Promise<T[]>): Promise<T[]> => {
  const uniqueIds = [...new Set(ids)]
  if (uniqueIds.length === 0) return []
  try {
    const chunks = await Promise.all(chunk(uniqueIds, LOOKUP_CHUNK_SIZE).map(fetchChunk))
    return chunks.flat()
  } catch {
    return []
  }
}
```

Each chunk is `GET v2.0/{networks|subnets|security-groups}?id=…&fields=id&fields=name`. Any failure makes the whole lookup return `[]`, and `applyPortNames` / `applySecurityGroupNames` (`portHelpers.ts:112-142`) then leave the names `undefined`, so the UI shows IDs instead.

**Port error handling** (`packages/aurora/src/server/Network/helpers/portHelpers.ts:25`):

```ts
const conflict = (message: string) => (response: ErrorResponse) =>
  new TRPCError({
    code: HTTP_STATUS_ERROR_MAP[409],
    message: /quota/i.test(response.statusText ?? "") ? QUOTA_EXCEEDED_MESSAGE : message,
  })
```

`requestOrThrow` (`requestHelpers.ts:19-36`) catches `SignalOpenstackApiError` and passes Neutron's own message as `statusText`, so this 409 override can tell a quota error apart from an IP/MAC conflict. `PortErrorHandlers` (`portHelpers.ts:44-69`) builds on the shared `ErrorHandler`, which handles 400/401/403/404/409/412 by default.

**Lenient response schema** (`packages/aurora/src/server/Network/types/port.ts:50`):

```ts
  // Plain string: Neutron documents ACTIVE, DOWN, BUILD and ERROR, but some backends report other values (e.g. N/A)
  status: z.string(),
```

Fields that come from Neutron extensions (`security_groups`, `allowed_address_pairs`, `port_security_enabled`, `dns_name`, `binding:*`) are optional, nullish or default to an empty value. `project_id` is required.

**List UI: the URL is the source of truth** (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:173`):

```tsx
  // The URL is the single source of truth for search, sort and page, so back/forward navigation
  // and links with different search params update the controls and the query.
  const searchTerm = searchParams.search ?? ""
  const sortBy: PortSortKey = searchParams.sortBy || "name"
  const sortDirection = searchParams.sortDirection || "asc"
  const currentPage = searchParams.page ?? 1
```

A promise is built in `useMemo` from those values (plus a `retryCount` for "Try Again") and passed through `useDeferredValue` (`:193-201`), so the old rows stay on screen while a new search or sort loads. `PortsContent` reads it with `use()` and paginates the full result on the client, 50 rows per page (`:96-98`). Sort is done by Neutron (`sort_key`/`sort_dir`) and search by the BFF. The `index.tsx` route validates the search params field by field and drops invalid values (`index.tsx:28-40`).

**Details route** (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:127`):

```tsx
  loader: async ({ context, params }) => {
    try {
      const port = await context.trpcClient?.network.ports.getById.query({
        project_id: params.projectId,
        port_id: params.portId,
      })
      return { portName: port?.name || null }
    } catch {
      return { portName: null }
    }
  },
```

The loader is only used for the page title. The component runs its own `trpcReact.network.ports.getById.useQuery` (`:154-157`, see CR3). On error it renders `PortLoadError`, which maps tRPC codes to an HTTP status, a title and a description, and offers "Try Again" only for retryable codes (`:32-40`, `:55-103`).

**Navigation wiring** (`packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:93`):

```ts
        ...(isEnabled("ports")
          ? [
              {
                service: "ports",
                label: t`Ports`,
                navigate: (nav: NavigateFn) => nav({ to: "/projects/$projectId/network/ports", params: { projectId } }),
                params: { projectId },
              },
            ]
          : []),
```

The overview card is added the same way inside the `serviceIndex["network"]` block (`$projectId/index.tsx:94-100`), and the router is registered as `ports: portsRouter` (`server/Network/routers/index.ts:17`).

**Router details tab in the URL** (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/$routerId.tsx:135`):

```tsx
  // Unknown tab values are dropped, so the view falls back to the default tab
  validateSearch: (search: Record<string, unknown>): RouterDetailsSearchParams => ({
    tab: isRouterDetailsTab(search.tab) ? search.tab : undefined,
  }),
```

`handleTabChange` (`:166`) navigates with `replace: true` and drops the default tab from the URL. `RouterDetailsView` now gets `activeTab`/`onTabChange` as props instead of keeping the tab in `useState`.

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

- **New tRPC surface:** `network.ports.{list,getById,create,update,delete}`. It is new, so nothing else in the monorepo calls it. The only consumers are the PR's own ports routes. Hosts that use `createServer` get the procedures automatically through `buildNetworkRouters`.
- **Moved internals:** `requestOrThrow`, `pickDefined` and `chunk` left `routerHelpers.ts`, and `NetworkSummary*` / `SubnetSummary*` left `types/router.ts`. `git grep` at the head finds no consumers outside `server/Network`, and none of these are exported from `packages/aurora/src/server/index.ts` (it exports only `parseOrThrow` from `Network/helpers`). The change is internal.
- **Routers behaviour:** name lookups are now chunked (50 IDs per request), and the details tab is reflected in `?tab=`. Links to `/network/routers/$routerId` without `tab` still open the default tab, and unknown values are dropped.
- **Service gating:** the new `ports` key goes through the existing `enabledServices` / `deniedServices` check. the `appConfig` types don't list service keys. `packages/aurora/README.md` does ("Service key reference", `:183`, and "Available service keys", `:210`), and so does `apps/dashboard/.env.example:11-12`. The PR updates none of them. Those lists were already missing `routers` and now also lack `ports`, which is a docs follow-up. Hosts that use an allow-list must add `ports` to see the page, as the changeset says.
- **Permissions:** the `network:ports:{read,list,create,update,delete}` keys already exist in `Network/routers/permissionRouter.ts:71-75`. The read-only UI doesn't call `canUser`.
- **Generated files:** `routeTree.gen.ts` and the `de`/`en` catalogs are regenerated, and they are where the conflicts with `main` and the sibling Networks PRs sit (CR4).

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Open a project that has the network service and has `ports` enabled. Check that "Ports" appears under Network in the side navigation and as a card on the project overview.
2. Open Network → Ports. Check the columns Name / ID, Description, Network, Fixed IPs / Subnet, Device Owner / ID and Status, and that network and subnet names appear (not IDs) for resources you can see.
3. Type part of a port name, an IP, a MAC, a subnet name or a device owner into the search. After about 500 ms the URL gets `?search=…` and the list narrows. Clear it and check the full list comes back.
4. Change the sort (Name / Status / Device Owner, ascending/descending). The URL updates, the page resets to 1, and the old rows stay visible until the new result arrives.
5. In a project with more than 50 ports, move between pages. Check that `?page=` updates and that browser Back/Forward moves between pages, each with the search and sort it had. Search and sort changes replace the history entry, so Back doesn't undo them.
6. Click a row (or ⋯ → Show Details). The details page shows Port ID, MAC, Network, IPs (with IPv4/IPv6 and subnet), Description, Name, Device Owner, Device ID, Created at, Updated at, Project ID, Status and Security Groups. The browser title and breadcrumb show the port name.
7. Use the copy buttons for the port ID, MAC, IPs, device ID and project ID.
8. Open Network → Routers → a router, switch to "Internal Networks", and check that the URL gets `?tab=internal`. A reload keeps the tab, and Back returns to the list instead of the previous tab.

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- A project with more ports than Neutron's `pagination_max_limit`: compare the list count with `openstack port list --project <id>`. The BFF returns only the first page, and search can't find later ports (CR1, `portsRouter.ts:65`).
- Open a port's details and watch the network panel. There are two `network.ports.getById` calls per open (CR3, `$portId.tsx:127`, `:154`).
- A port ID that doesn't exist: the page shows "Port Not Found", code 404, with no "Try Again" (`$portId.tsx:66-67`, `:81`).
- A user without `get_port` (403) on the details page or on the list: the details page shows an inline error page, and the list shows "Failed to Load Ports" with the raw BFF message (CR2, `$portId.tsx:68-69`, `PortsList.tsx:54-55`).
- An expired session while on the details page: the inline "Log in again" text is shown instead of a redirect (CR2/I1, `$portId.tsx:70-71`).
- A port without a name, without fixed IPs, or without a device: the list shows the ID or "–", and the details page shows "—" (`PortTableRow.tsx:47-75`, `PortDetailsView.tsx:59-68`).
- A network, subnet or security group the user can't see (e.g. a shared or external network): the ID is shown instead of a name, and the list doesn't fail (`lookupHelpers.ts:36-38`).
- A backend that reports a status other than ACTIVE/DOWN/BUILD/ERROR (e.g. `N/A`): the list still renders (`types/port.ts:50-51`).
- Invalid URL params (`?sortBy=foo&page=-1`): they are dropped back to the defaults without an error (`index.tsx:28-40`). A `page` beyond the last page resets to 1 once the current result is loaded (`PortsList.tsx:111-113`).
- A search with no matches: the empty-state text "No ports match your search…" appears, and "no ports in this project" appears only when there is no search (`PortListContainer.tsx:50-53`).
- A dual-stack port (IPv4 and IPv6): both IPs are listed in the row and in the details with their IP version (`PortDetailsView.tsx:49-57`).
- Switching projects while on the Ports page: the previous project's ports are not shown during loading (`ports/index.tsx:54`, `key={projectId}`).
- Router details with `?tab=bogus`: the default tab opens and the param is dropped (`$routerId.tsx:135-138`).

</details>

## Update — 2026-10-26, head `86a355a8`

_Reviewed at head [`86a355a8`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377/commits/86a355a8d6da94478e77c0869d9720efe6823e2a) · base `main` at `af14a6a0` · 2026-10-26 11:09 UTC_

### ⚖️ &nbsp; Verdict

Recommendation: **🟡 Approve with process to-dos** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

- **Still open from the earlier review:** P1

### Fixed since last analysis

- CR1 — portsRouter.list now follows `ports_links` next pages (visited-guarded loop) and returns the full list.
- CR3 — The route loader is gone; only the component's `useQuery` fetches the port.
- P2 — The description now covers the `?tab=` search param on the router details route.
- I1 — Copy now reads 'Sign in again to continue.'
- I2 — `PopupMenu` now has a `PopupMenuToggle` wrapping the icon Button.
- I3 — `gap="1"` is gone; PortDetailsView uses `0.5`, `2` and `6`, which B.3 allows.
- I4 — Status is now the 2nd column, right after Name / ID.
- I5 — Routers doc now says lookups are chunked into requests of at most 50 IDs.
- I6 — Error tables in the ports doc carry the `: {Neutron message}` suffix again.
- I7 — The `useEffect` is gone; `PageInput` is keyed on `currentPage` instead.
- I8 — `zod` is now imported right after the router import, before the Lingui imports.

**Partly fixed**

- CR2 — 403 is now a page-level info Message on both details and list. 401 is still not a redirect: the details page shows a 'Sign in' error page (I9) and the list falls into the generic error boundary with the raw BFF message (I11).

**Still open**

- P1 — PR is still a draft.

**No longer reviewed**

- CR4 — Merge conflicts are no longer part of this review; GitHub shows them.

### 🔧 &nbsp; Required Changes

None.

### 💡 &nbsp; Improvements

| #   | Severity | Category | Precedent | Issue                                                                                             | Location                                                                                                    |
| --- | -------- | -------- | --------- | ------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| I9  | 🟢 Low   | UI/UX    | —         | Port details still renders a 401 inline with a Sign in button to `/` instead of redirecting (B.6) | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:75`                  |
| I10 | 🟢 Low   | UI/UX    | —         | Status column renders the raw status string instead of a `Badge` (B.1)                            | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:51` |
| I11 | 🟢 Low   | UI/UX    | —         | Ports list handles only 403; a 401 or other error shows the raw BFF `error.message`               | `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:290`   |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I9 — 401 on the port details page is an inline error page, not a redirect to Sign-in** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:75`
The CR2 fix turns `UNAUTHORIZED` into a `RouteIdLevelDefaultError` with code 401 and a button that navigates to `/`, at `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:68`:

```tsx
if (errorCode === "UNAUTHORIZED") {
  return (
    <RouteIdLevelDefaultError
      code={401}
      errorTitle={t`Session Expired`}
      errorDescription={t`Your session has expired. Sign in again to continue.`}
      action={
        <Button variant="primary" onClick={() => navigate({ to: "/" })}>
          <Trans>Sign in</Trans>
        </Button>
      }
    />
```

B.6 lists "a 401/403 handled inline instead of via redirect" as a Reject and asks for a redirect to Sign-in that remembers the target and returns there after auth. Here the user lands on `/` and loses the port they were looking at; the comment above the branch also describes behaviour the code doesn't have.
_Fix:_ Redirect to the sign-in route with the current location as the return target (the way `_auth.tsx` does for a missing session) instead of rendering the error page, and update the comment.

**I10 — Port status is plain text in the list** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:51`
`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:51` renders `port.status` as text. B.1 maps status indicators to `Badge`; the delta moved this cell to the 2nd column, so it now sits prominently as unstyled text (`ACTIVE`, `DOWN`, `BUILD`).
_Fix:_ Render the status as a `Badge` with a variant per status (e.g. success for `ACTIVE`, danger for `ERROR`/`DOWN`); the router list can follow in the same or a later PR.

**I11 — Ports list shows the raw error message and no Sign in path on 401** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:290`
`createPortsPromise` converts only `FORBIDDEN` into the info Message; everything else, including `UNAUTHORIZED`, is rethrown:

```tsx
// 403 is an expected "no access" state, not a failure: render it as a page-level info message
// (B.6) rather than letting it reach the error boundary.
if (err instanceof TRPCClientError && err.data?.code === "FORBIDDEN") {
  return { ports: [], forbidden: true }
}
throw err
```

The error boundary then prints `error.message` as the body at `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:290`, so an expired session shows the BFF's text and no way to sign in. CR2 of the earlier review covered the list error as well; mark-karnaukh-extern-sap confirmed it in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6293554974 and listed it as fixed in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6295356006, but only the details page got the 401 handling.
_Fix:_ Handle `UNAUTHORIZED` in the list the same way as the details page (ideally a redirect to Sign-in, see I9) and show a generic translated message instead of `error.message` for the remaining errors.

</details>

### 🗨️ &nbsp; Review comments not taken up

Raised in the review discussion, checked at this head and not counted as findings:

| Raised by                                                                                                                | Claim                                                                                                                                                                                                                                                                                          | Why not a finding                                                                                                                                                                                                           |
| ------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| mark-karnaukh-extern-sap [comment](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377#issuecomment-6295356006) | Client-side search duplicates the BFF filterPortsBySearchTerm field list by hand (comment says 'mirroring'), and the BFF still accepts and runs search/sort/limit params that the UI no longer uses. The two implementations can drift and the BFF params are dead code for the only consumer. | PortsList.tsx:59 duplicates the BFF search field list, and the BFF params are unused by the UI. It is a deliberate perf decision the author raised as an open question, and a code-quality opinion with no concrete defect. |

### What changed

<details>
<summary><strong>What was done</strong></summary>

This update covers `512f01b1` to `86a355a8`. The PR is still a draft. CI on the head commit: 18 of 22 checks pass, 4 are skipped, none failed or pending.

**Ports list moves to client-side sorting and search.** The list now fetches the full port list once per project/network and sorts, searches and paginates it in the browser. Sort, search and page changes no longer send a request, and the `useDeferredValue`/stale-result handling is gone. The sort keys offered shrink to `name`, `status` and `device_owner`. Search filtering now runs on the locally typed text on every keystroke, while the URL is still updated with a debounce. The BFF `list` procedure still accepts `sort_key`, `sort_dir` and `searchTerm`, but the page no longer uses them.

**Routers get the same treatment in places the findings did not cover.** The Routers BFF `list` now also follows Neutron pagination through `routers_links`, with a new test. In the Routers list, the Status column moves to second position, the row action menu gets a visible `PopupMenuToggle` button, and a 403 now shows an info message "Insufficient Permissions" instead of the "Failed to Load Routers" error. The Router tests are updated to match.

**Port details page title is now static.** With the loader removed, the browser tab title is always "Port Details" and no longer shows the port name.

**Pagination plumbing.** `nextPageUrl` is a new shared helper in `requestHelpers.ts`, and `PortListResponseSchema` and `RouterListResponseSchema` gain an optional `*_links` field. Both list loops use a `visited` set as a guard against a non-advancing `next` link.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

Each list loop reuses only the query string of Neutron's absolute `next` href, against the known relative base path:

```ts
export const nextPageUrl = (baseUrl: string, links?: Array<{ rel: string; href: string }>): string | undefined => {
  const href = links?.find((link) => link.rel === "next")?.href
  if (!href) return undefined
  const queryIndex = href.indexOf("?")
  return queryIndex === -1 ? baseUrl : `${baseUrl}${href.slice(queryIndex)}`
}
```

The client-side list pipeline filters, then sorts, then pages:

```tsx
const visiblePorts = useMemo(
  () => sortPorts(filterPorts(ports, localSearchTerm), sortSettings.sortBy, sortSettings.sortDirection),
  [ports, localSearchTerm, sortSettings.sortBy, sortSettings.sortDirection]
)
```

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

- The Routers BFF `list` contract changes: it now issues several requests when Neutron paginates. `packages/aurora/docs/0010_routers_bff.md` was updated for this.
- Search, sort and pagination on the Ports list now run on the full list in the browser. For projects with many ports, the first load is heavier, and `filterPorts` in `PortsList.tsx` duplicates the BFF's `filterPortsBySearchTerm`, so the two must be kept in sync.
- `sort_key`, `sort_dir` and `searchTerm` on `ports.list` (`packages/aurora/src/server/Network/types/port.ts:115`) are now unused by the only client, but remain in the contract and docs.
- Router list and Router tests were edited as part of this update, although the Routers feature is outside the Ports scope in the PR description. The description does not mention the Routers list changes (Status column order, action toggle, 403 info message, pagination).

</details>

---

_Analyzed 2026-10-17 · commit `512f01b1` · read-only · CI from PR API · updated for `86a355a8` on 2026-10-26 · skill: review-and-comment-pr_
