# Summary

Adds an in-core `networks` plugin under the **Network** section, giving a read-only
view of OpenStack Neutron networks (Layer 2 segments). It mirrors the existing
Routers resource in structure and conventions. Implements the read-view portion of
the Networks Management epic (#1019).

# Changes Made

**Server** (`packages/aurora/src/server/Network/`)
- `types/network.ts` — Zod schemas for Neutron networks + subnets, and a
  `NetworkListItem` shape that derives `external` (from `router:external`) and
  `subnet_count` (from `subnets[]`) so the UI stays free of OpenStack-specific keys.
- `helpers/networkHelpers.ts` — `NetworkErrorHandlers`, `toNetworkListItem`, and a
  BFF-side status filter.
- `routers/networksRouter.ts` — `list` (GET `/v2.0/networks`, Neutron-side sort +
  BFF search/status filter), `getById` (GET `/v2.0/networks/{id}`), and `listSubnets`
  (GET `/v2.0/subnets?network_id=…` for the detail Subnets tab).
- Wired `networks: networksRouter` into `Network/routers/index.ts`.

**Client** (`.../network/networks/`)
- `networks.tsx` — thin layout route (`<Outlet/>` + errorComponent).
- `networks/index.tsx` — list page (ContentHeader + sort + search + pagination).
- `networks/$networkId.tsx` — detail page with retryable error handling.
- `-components/` — `NetworksList`, `NetworkListContainer`
  (columns: Name/ID · Status · Shared · MTU · Admin State · Subnets · Port Security),
  `NetworkTableRow`, and `NetworkDetailsView` (Overview tab + Subnets tab).

**Navigation**
- Added a "Networks" entry to the Network sidebar section in `buildNavSections.ts`.

Read-only for now — no create/update/delete. Permission mappings
(`network:networks:read/list`) already existed in the Network permission router.

# Related Issues

- Epic: cobaltcore-dev/aurora-dashboard#1019

# Screenshots (if applicable)

<!-- TODO: add list + detail screenshots once run against a Neutron endpoint -->

# Testing Instructions

1. `pnpm i`
2. `pnpm dev` and open a project with the Neutron (`network`) service in its catalog.
3. In the sidebar under **Network**, open **Networks**; verify the list loads with
   sort (Name/Status) and search, and pagination at >50 rows.
4. Open a network; verify the **Overview** tab (status, MTU, admin state, shared,
   external, port security, project ID with copy) and the **Subnets** tab.

# Checklist

- [x] I have performed a self-review of my code.
- [x] I have commented my code, particularly in hard-to-understand areas.
- [ ] I have added tests that prove my fix is effective or that my feature works.
- [ ] New and existing unit tests pass locally with my changes.
- [ ] I have made corresponding changes to the documentation (if applicable).
- [x] My changes generate no new warnings or errors.
