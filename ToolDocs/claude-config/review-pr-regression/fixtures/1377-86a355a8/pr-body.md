# Summary

Adds Neutron Ports management to Aurora Dashboard: a tRPC BFF for ports and a read-only UI with a list view and a details view. Write procedures (`create`, `update`, `delete`) are available in the BFF but not yet exposed in the UI.

# Changes Made

**BFF (`packages/aurora/src/server/Network`)**

- `routers/portsRouter.ts`: new router mounted as `network.ports`, with `list`, `getById`, `create`, `update` and `delete`
  - `list` is always filtered by the current project and optionally by `network_id`; BFF-side search across ID, name, description, network, IPs, subnets, MAC and device
  - `list` follows Neutron's pagination (`ports_links` `next`) and returns the complete list, so searching and paging never silently miss ports beyond the first page
- `types/port.ts`: Zod schemas for port requests and responses (fixed IPs, security groups, allowed address pairs, IP/CIDR/MAC validation)
- `helpers/portHelpers.ts`: error handlers on the shared `ErrorHandler` (IP/MAC in use, port owned by a router, quota exceeded), request body builder, response shaping
- Network, subnet and security group names are resolved with batched, best-effort lookups (chunks of 50 IDs, IDs as fallback); the IP version is derived from each address
- Shared helpers extracted from Routers so both resources use them: `helpers/requestHelpers.ts` (`requestOrThrow`, `pickDefined`, `chunk`, `withQuery`, `nextPageUrl`) and `helpers/lookupHelpers.ts` (network, subnet and security group name lookups). Routers behaviour is unchanged except that its list now also follows Neutron pagination.
- Registration in `routers/index.ts`; docs in `packages/aurora/docs/0017_ports_bff.md`

**UI (`packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports`)**

- "Ports" navigation entry and project overview card
- List view: Name / ID, Status, Description, Network, Fixed IPs / Subnet, Device Owner / ID; search, sorting and pagination in URL params. The full list is fetched once per project/network and sorted, searched and paginated client-side (no refetch on sort/search). "Show Details" is the only row action.
- The list component takes an optional `networkId`, which scopes the query to that network and hides the Network column (prepared for the "Ports" tab of #1019)
- Details view: Port ID, MAC, Network, IPs (with IP version and subnet), Description, Name, Device Owner, Device ID, Created at, Updated at, Project ID, Status, Security Groups; IDs, IPs and MAC are copyable. 401 redirects to sign-in; 403 is shown as a page-level info message.

**Fix (outside the Ports scope)**

- `routers/$routerId.tsx`: `createFileRoute()` now receives a string literal. The TanStack route generator rejected the `ROUTE_ID` constant, which stopped `routeTree.gen.ts` from being regenerated.
- `routers/$routerId.tsx`: the active details tab is now kept in the URL as a `?tab=` search param (via `validateSearch`), so it survives reloads and is shareable. `RouterDetailsView` receives the active tab as a controlled prop instead of holding it in local `useState`; unknown tab values fall back to the default tab. (Called out in the changeset.)

**Design decisions**

- Network and subnets show names and fall back to the ID only when the name can't be resolved.
- The device ID is shown below the device owner in the list, as in elektra and the epic; there is no name lookup for devices.
- Timestamps are shown as returned by Neutron (ISO 8601, UTC), as in the epic.
- Port status is accepted as any string, so unexpected values from some backends (e.g. `N/A`) don't break the list.
- The existing permission keys `network:ports:*` are used (the epic mentions `network:port:*`).

**Not included / follow-ups**

- Create, edit, delete and bulk delete in the UI
- "Ports" tab in the network details view (#1019)
- List filters (status, device owner)
- Port security toggle, tag editor and allowed address pairs management

# Related Issues

- Part of #816
- Closes #1381
- Closes #1382

# Screenshots (if applicable)

<!-- List view -->
<!-- Details view -->

# Testing Instructions

1. `pnpm i`
2. `pnpm run test`
3. Add `ports` to `enabledServices` if your environment restricts the enabled services.
4. `pnpm dev` and open a project → Network → Ports; check the list (search, sorting, pagination), then open a port and check the details view.

# Checklist

- [x] I have performed a self-review of my code.
- [x] I have commented my code, particularly in hard-to-understand areas.
- [x] I have added tests that prove my fix is effective or that my feature works.
- [x] New and existing unit tests pass locally with my changes.
- [x] I have made corresponding changes to the documentation (if applicable).
- [x] My changes generate no new warnings or errors.

