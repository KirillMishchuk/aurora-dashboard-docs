---
type: pr-report
date: 2026-10-15
status: open
pr: [1377]
author: mark-karnaukh-extern-sap
branch: mark-manage-ports-interface
---

# PR #1377: feat(aurora): add Neutron Ports BFF and read-only Ports page (list & details)

**Author:** mark-karnaukh-extern-sap · **Status:** draft · **Created:** 2026-10-09
**Branches:** `mark-manage-ports-interface` → `main` (base `6a8dad69`) · **Files:** 42 (+5094/-247)
**Link:** https://github.com/cobaltcore-dev/aurora-dashboard/pull/1377
**CI:** all green (at `512f01b`)

## What was done

This PR adds Neutron Ports management to Aurora Dashboard — a complete tRPC BFF for ports and a read-only UI with list and details views. Write procedures (`create`, `update`, `delete`) are implemented in the BFF but intentionally not yet exposed in the UI.

Key deliverables:
1. **BFF router** (`network.ports`) with five procedures: `list`, `getById`, `create`, `update`, `delete`
2. **List view** with search, sorting, and pagination — reusable component that can scope to a single network
3. **Details view** with copyable IDs, IP addresses, and MAC address
4. **Shared helpers extracted from routers** — `requestHelpers.ts`, `lookupHelpers.ts`, and shared summary types for network/subnet/security group name resolution
5. **Navigation integration** — "Ports" entry in the Network section and a card on the project overview
6. **Router details enhancement** — added URL-based tab state management to the existing router details page

The PR also fixes a TanStack Router issue where using a `ROUTE_ID` constant in `createFileRoute()` prevented route tree regeneration.

## How it is implemented

### Server: BFF Layer

The ports router (`packages/aurora/src/server/Network/routers/portsRouter.ts:55-157`) mounts as `network.ports` and uses `projectScopedProcedure` for all five procedures, ensuring token rescoping to the requested project:

```typescript
export const portsRouter = {
  list: projectScopedProcedure
    .input(PortQueryParametersSchema)
    .query(async ({ input, ctx }): Promise<PortListItem[]> => {
      // ...
      // project_id is forwarded as a filter, so admin roles also only see the current project's ports here
      const queryParams = appendQueryParamsFromObject(openstackFilters, { keyMap: LIST_PORTS_QUERY_KEY_MAP })
      const response = await requestOrThrow(
        () => network.get(withQuery(PORTS_BASE_URL, queryParams)),
        PortErrorHandlers.list
      )
      // ...
    }),
  // getById, create, update, delete follow the same pattern
}
```

**Name resolution** is batched and best-effort: the `list` procedure collects all referenced network and subnet IDs, then resolves names in parallel with `fetchNetworkSummaries` and `fetchSubnetSummaries` from the new `lookupHelpers.ts`. The `getById` procedure additionally resolves security group names. When lookups fail (e.g., external networks not visible to the user), the UI falls back to showing IDs.

**Zod schemas** (`packages/aurora/src/server/Network/types/port.ts`) validate all inputs and parse Neutron responses. Notable validations include IP address (`isValidIpAddress`), CIDR (`isValidIpAddressOrCidr`), MAC address regex, and 255-character limits on name/description matching Neutron's constraints.

**Error handling** follows the `ErrorHandler` factory pattern from routers. Port-specific overrides provide clear messages for common Neutron errors:
- 409: IP/MAC address in use, quota exceeded, port owned by router
- 404: Port/network/subnet/security group not found

### Server: Refactored Shared Helpers

The PR extracts utilities previously inline in `routersRouter.ts` into shared modules:

- `requestHelpers.ts` (`packages/aurora/src/server/Network/helpers/requestHelpers.ts:1-56`): `requestOrThrow`, `pickDefined`, `chunk`, `withQuery`
- `lookupHelpers.ts` (`packages/aurora/src/server/Network/helpers/lookupHelpers.ts:1-82`): `fetchNetworkSummaries`, `fetchSubnetSummaries`, `fetchSecurityGroupSummaries` with batched requests (chunks of 50 IDs)
- `types/index.ts` additions: `NetworkSummary`, `SubnetSummary`, `SecurityGroupSummary` schemas

The routers code is updated to import from the new locations; behavior is unchanged.

### Client: List View

The ports list (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortsList.tsx:1-212`) implements the `Promise + React use()` pattern for data fetching with `useDeferredValue` to keep the current list visible while loading:

```typescript
const portsPromise = useMemo(
  () => createPortsPromise(client, project, networkId, sortBy, sortDirection, searchTerm),
  [client, project, networkId, sortBy, sortDirection, searchTerm, retryCount]
)
const deferredPortsPromise = useDeferredValue(portsPromise)
```

URL state management stores search term, sort settings, and page number in search params. The component accepts an optional `networkId` prop to scope the list to a single network (hiding the Network column), preparing for a future "Ports" tab in network details.

The list container (`PortListContainer.tsx:1-126`) renders a `DataGrid` with columns: Name/ID, Description, Network, Fixed IPs/Subnet, Device Owner/ID, Status, and an action menu. Empty states distinguish "no ports in this project" from "no search results".

### Client: Details View

The port details route (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:1-175`) uses `trpcReact.network.ports.getById.useQuery` with retry logic for transient errors. The loader only fetches the port name for the page title; the full query runs in the component for proper caching and retry.

The details view (`PortDetailsView.tsx:1-91`) renders a `DescriptionList` with copyable text for IDs, IP addresses, and MAC address. Fixed IPs show the IP version badge and subnet name (or ID fallback).

### Client: Router Details Tab State

The PR enhances `packages/aurora/src/client/routes/_auth/projects/$projectId/network/routers/$routerId.tsx` to store the active tab in URL search params (`?tab=internal`), with `replace: true` navigation so tab switches don't add history entries.

## What it affects

### New tRPC surface
- `network.ports.list` — returns `PortListItem[]` with enriched network/subnet names
- `network.ports.getById` — returns `PortDetails` with security group names
- `network.ports.create`, `update`, `delete` — mutations (not yet exposed in UI)

### Permission keys
The PR adds mappings in `permissionRouter.ts:71-75`:
- `network:ports:read`, `network:ports:list` → `get_port`
- `network:ports:create` → `create_port`
- `network:ports:update` → `update_port`
- `network:ports:delete` → `delete_port`

### Navigation
- `buildNavSections.ts:93-100`: Adds "Ports" under Network when `ports` is in `enabledServices`
- `$projectId/index.tsx:94-99`: Adds "Ports" card to project overview

### Consumers
No external consumers of the new `network.ports` procedures outside this PR. The refactored helpers (`requestHelpers`, `lookupHelpers`) are only consumed within the Network domain. PR #1385 (Networks) performs the same refactoring and will merge cleanly — whichever lands first applies the extraction, the other becomes a no-op on rebase.

### Localization
69 new message IDs in `de/messages.po` and `en/messages.po` for ports UI strings.

## Review

### Findings (confidence ≥75)

#### 1. Import traversal beyond one level — confidence 75 · severity Low

`packages/aurora/src/server/Network/types/port.ts:2` uses `../../trpc` instead of the required `@/server/trpc` path alias:

```typescript
import { projectScopedInputSchema } from "../../trpc"
```

**Suggested fix:** Change to `import { projectScopedInputSchema } from "@/server/trpc"`.
**Why this score:** B.13 explicitly requires `@/` for traversal beyond one level; this is a direct Quick Reject Checklist violation. Severity Low because it's a code organization issue with no user-visible effect. Expect pushback: other Network type files (`router.ts`, `floatingIp.ts`) use the same pattern.

#### 2. Unapproved spacing value `gap="1"` — confidence 75 · severity Low

`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortDetailsView.tsx:51` and `PortTableRow.tsx:57` use `gap="1"` which is not in the B.3 approved list ("0.5", "2", "4", "6"):

```typescript
<Stack alignment="center" gap="1">
```

**Suggested fix:** Use `gap="0.5"` for tighter spacing or `gap="2"` for standard spacing.
**Why this score:** Direct violation of the Quick Reject Checklist item "Ad-hoc spacing value not in the approved list (B.3)". Severity Low because it's visual consistency, not functional. Expect pushback: `RouterTableRow.tsx:54,69` and 15+ other files use `gap="1"` — the approved list may be incomplete.

### Rule violations (Low)

| Score | Finding | Rule | Suggested fix |
| --- | --- | --- | --- |
| 75 | `gap="1"` in `PortDetailsView.tsx:51`, `PortTableRow.tsx:57` | Quick Reject: ad-hoc spacing not in B.3 | Use `gap="0.5"` or `gap="2"`; expect pushback: 15+ files use `gap="1"` |
| 75 | `../../trpc` import in `port.ts:2` | Quick Reject: `../../` traversal beyond one level | Use `@/server/trpc`; expect pushback: other Network types do the same |

### Below the bar

| Score | Severity | Finding | Why this score |
| --- | --- | --- | --- |
| 50 | Low | Zone 1 uses `distribution="end"` instead of `distribution="between"` (`PortsList.tsx:122`) | B.2 prescribes "between" for sort + create button, but this read-only view has no create button; "end" is appropriate for single-item zone |
| 25 | — | Status cell uses plain text instead of `Badge` (`PortTableRow.tsx:73`) | B.1 lists Badge for "status indicators" but existing `RouterTableRow` uses the same plain text pattern; unclear if required for all status columns |
| 25 | — | Missing Neutron pagination parameters (`marker`, `limit`, `page_reverse`) in `PortQueryParametersSchema` | BFF uses client-side pagination (`PAGE_SIZE = 50`); server-side pagination is a design choice, not required |
| 0 | — | CIDR validation missing lower bound check (`isValidCidr` in `router.ts`) | Regex `/^\d{1,3}$/` already rejects negative numbers; the claim is incorrect |
| 0 | — | Debounce timer race condition in `PortsList.tsx` | Standard React cleanup pattern with proper ref usage; no race condition exists |
| 0 | — | Project ownership validation missing in `getById`/`update`/`delete` | OpenStack Neutron enforces project isolation via scoped tokens; BFF validation is redundant |
| 0 | — | ErrorHandler used beyond list procedures (WORK_IN_PROGRESS comment violation) | Comment in `errorHandling.ts` is outdated — `routersRouter.ts` already uses ErrorHandler for all procedures |
| 0 | — | Missing server-side `canUser` permission checks on mutations | OpenStack Neutron enforces authorization at API layer via scoped tokens; BFF pre-checks would create TOCTOU race |
| 0 | — | `validateAndEncodeResourceId` error messages may leak details | External library function from `signal-openstack` used consistently across all routers; errors are user-friendly ("Port ID must be a non-empty string") |

## Proposed follow-ups

- [ ] **Import traversal `../../trpc`** — `port.ts:2` → Review, finding 1; batch-fix across all Network types if updating
- [ ] **Unapproved `gap="1"` spacing** — `PortDetailsView.tsx:51`, `PortTableRow.tsx:57` → Review, finding 2; consider adding `gap="1"` to B.3 approved list given widespread usage

---

Analyzed: 2026-10-15 · commit `512f01b`
