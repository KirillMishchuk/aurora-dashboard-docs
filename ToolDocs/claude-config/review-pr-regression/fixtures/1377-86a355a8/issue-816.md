# #816: [EPIC](networking): Ports Management 001

State: OPEN · https://github.com/cobaltcore-dev/aurora-dashboard/issues/816

## Description

Implement comprehensive OpenStack Networking (Neutron) Ports and Fixed IPs management within the Aurora Dashboard.

**Architectural Note:** In OpenStack Neutron, Ports are **first-class resources** that exist independently within a project scope. A Port always belongs to exactly one Network, but Port management itself is not exclusively bound to the Network context. Ports can be created standalone (e.g. to reserve a fixed IP before a VM exists) and later attached to instances or other resources.

Therefore, this implementation provides:

1. **A standalone global Ports view** under `/networking/ports` for project-wide port management.
2. **An embedded Ports tab within the Network Detail view** that reuses the same underlying components, pre-filtered by `networkId`.

This dual-access pattern is achieved by implementing the Ports overview as a **reusable component** that accepts an optional `networkId` filter prop. This enables users to view, create, update, and delete network ports and their associated Fixed IPs both globally and in the context of a specific network.

All operations are project-scoped, utilize existing OpenStack Keystone tokens, and strictly respect access controls defined by the Aurora/OpenStack policy engine.

**API Description**: https://docs.openstack.org/api-ref/network/v2/index.html#ports

---

## Dependencies & Prerequisites

- **RELATED TO: Epic #1019 (OpenStack Networking Networks Management)**
  - The Network Detail view from Epic #1019 will embed the reusable Ports overview component as a tab.
  - This epic is **not blocked** by #1019 for the standalone view but requires coordination for the tab integration.

---

## Objectives

- Provide a complete tRPC-based BFF for Neutron Port operations (independent of Network context).
- Deliver a **reusable Ports overview component** that works both standalone and embedded.
- Implement a **standalone global Ports page** (`/networking/ports`).
- Integrate the same component as a **"Ports" tab in the Network Detail view**, once the Networks feature is implemented.
- Enable users to manage the lifecycle of network ports (Create, Read, Update, Delete).
- Provide visibility of Fixed IPs, Subnets, Device Owner/ID, and associated resources.
- Enforce strict RBAC using Aurora's policy engine (`network:port:*` permissions). All action-triggering UI elements (buttons, menu items, form controls) must be gated via `canUser(...)` checks against the corresponding policy rules.

---

## Acceptance Criteria

-  tRPC BFF is implemented with complete Zod schema validation.
-  Ports can be listed globally (all ports in the project) and filtered by `networkId`.
-  A standalone Ports page exists at `/networking/ports`.
-  The Network Detail page contains a "Ports" tab that reuses the same overview component.
-  The reusable component accepts an optional `networkId` prop to scope the list.
-  Users can list, view, create, update, and delete ports (P1, P2 & P3).
-  The "Create Port" modal:
  - In standalone view → user must select a Network.
  - In Network Detail tab → Network is pre-filled/hidden.
-  Fixed IPs (with subnet IDs and IP versions), Device Owner/ID, and Security Groups are clearly displayed.
-  All action-triggering UI elements (Create, Edit, Delete, etc.) are gated using `canUser(...)` against the corresponding `network:port:*` policy rules and are hidden/disabled for unauthorized users.
-  Comprehensive error handling provides user-friendly feedback for Neutron errors (including cases where Neutron itself rejects an operation, e.g. deletion of a port that is still attached).
-  All UI components follow the Aurora design system.
-  Complete testing coverage (unit, integration, E2E) is achieved.

---

## Technical Architecture & Request Flow

### System Architecture Flow

1. **UI Layer:** User navigates either to `/networking/ports` (global) or to `/networking/networks/:networkId` → "Ports" tab.
2. **BFF Layer (tRPC):** Validates input, applies optional `networkId` filter, checks permissions.
3. **Service Layer:** Uses the internal **`openstack-signal`** library to communicate with the Neutron API via standard HTTP methods (`GET`, `POST`, `PUT`, `DELETE`). All requests are authenticated with the current Keystone token.

### Request Flow Example (List Ports)

**Global view:**
- Step 1: UI triggers `ports.list({})` (no filter).
- Step 2: BFF invokes `openstack-signal` → `GET /v2.0/ports?project_id={currentProject}`.

**Network Detail tab:**
- Step 1: UI triggers `ports.list({ networkId: X })`.
- Step 2: BFF invokes `openstack-signal` → `GET /v2.0/ports?network_id=X`.

### Request Flow Example (Create Port)

- Step 1: UI triggers `ports.create({ networkId, name, fixedIps?, securityGroups?, ... })`.
- Step 2: BFF validates input and permissions.
- Step 3: BFF invokes `openstack-signal` → `POST /v2.0/ports`.
- Step 4: Neutron creates the port and returns details.
- Step 5: BFF returns success; UI invalidates the port list cache (global + network-scoped).

---

## API Integration Mapping

All calls are performed by the BFF through the `openstack-signal` library.

| Feature | HTTP Method | Endpoint | Service | Priority |
|---------|-------------|----------|---------|----------|
| List ports (optionally filtered by network) | `GET` | `/v2.0/ports?network_id={id}` | Neutron | **P1** |
| Show port details | `GET` | `/v2.0/ports/{id}` | Neutron | **P1** |
| Create port | `POST` | `/v2.0/ports` | Neutron | **P2** |
| Update port | `PUT` | `/v2.0/ports/{id}` | Neutron | **P2** |
| Delete port | `DELETE` | `/v2.0/ports/{id}` | Neutron | **P3** |

---

## UI Specification

### Port List (Overview Table)

Columns (both in standalone view and Network Detail tab — the *Network* column may be hidden when embedded, since it is redundant in that context):

| Column | Content |
|--------|---------|
| **Port ID / Name** | UUID and Name (Name may be empty) |
| **Description** | Free-text description |
| **Network** | Network name + ID (hidden when embedded in Network Detail) |
| **Fixed IPs / Subnet** | List of IPs with Subnet IDs (IPv4 + IPv6) |
| **Device Owner / ID** | e.g. `compute:qa-de-1b` + Device UUID |
| **Status** | e.g. `ACTIVE`, `DOWN`, `BUILD` |

#### Screenshots (elektra)

<img width="1163" height="458" alt="Image" src="https://github.com/user-attachments/assets/3d5a0817-8557-46b1-a38f-60bcf655d82d" />

### Port Detail View

Displayed fields (example values):

| Field | Example Value |
|-------|---------------|
| Port ID | `xxxxxxxx-f61b-46ef-90f0-xxxxxxxxxxxx` |
| MAC | `fa:16:3e:50:a2:79` |
| Network | `dualstack-test` / `xxxxxxxx-4ee2-4bd7-9251-xxxxxxxxxxxx` |
| IPs | `10.180.242.42` (ipv4, subnet `dfcb9d57-…`)<br>`fd00:1234:feed:cafe::328` (ipv6, subnet `54ef3254-…`) |
| Description | *(free text)* |
| Name | *(free text)* |
| Device Owner | `compute:qa-de-1b` |
| Device ID | `xxxxxxxx-b89e-4f7e-92e0-xxxxxxxxxxxx` |
| Created at | `2025-02-28T14:36:21Z` |
| Updated at | `2025-02-28T14:36:21Z` |
| Project ID | `xxxxxxxxe4b3e9f2xxxxxxxxxxxx` |
| Status | `DOWN` |
| Security Groups | `default` / `xxxxxxxx-e6a6-4086-8d62-xxxxxxxxxxxx` |

All UUIDs, IPs and MAC addresses should support **copy-to-clipboard**.

#### Screenshots (elektra)

<img width="708" height="635" alt="Image" src="https://github.com/user-attachments/assets/3b6ac3e5-a768-4c94-9490-c6dc9d7d4fc6" />

---

## Permissions & Policy Enforcement

Access control for port operations is governed entirely by Aurora's policy engine using the `network:port:*` rule set (e.g. `network:port:list`, `network:port:get`, `network:port:create`, `network:port:update`, `network:port:delete`).

### UI Requirements

- Every action-triggering UI element **must** be gated via `canUser(...)`:
  - **"Create Port" button** → `canUser("network:port:create")`
  - **"Edit Port" action / button** → `canUser("network:port:update")`
  - **"Delete Port" action / button** → `canUser("network:port:delete")`
  - **Bulk actions** → gated against the corresponding rule.
- Elements for which the user lacks permission must be **hidden or disabled** (with a tooltip where appropriate). No action must be reachable through the UI if the policy denies it.
- Read-only elements (list, detail view) require the corresponding `list` / `get` permissions; if denied, the view degrades gracefully (empty state or access-denied message).

### BFF Enforcement

The BFF enforces the same policy rules server-side on every tRPC procedure. UI-side `canUser(...)` checks are a UX aid; the BFF remains the source of truth. Any operation rejected by policy or by Neutron itself surfaces as a user-friendly error in the UI.

---

## Subtasks (Implementation Plan)

_Tasks will be converted to GitHub issues during sprint planning._

### Phase 1: Foundation & Read Operations (P1)

- [ ]  **(BFF)** Define Zod schemas (`Port`, `FixedIP`, `AllowedAddressPair`, `SecurityGroupRef`).
- [ ]  **(BFF)** Implement `ports.list` procedure with **optional** `networkId` filter (via `openstack-signal`: `GET /v2.0/ports`).
- [ ]  **(BFF)** Implement `ports.get` procedure (via `openstack-signal`: `GET /v2.0/ports/{id}`).
- [ ]  **(UI)** Build **reusable `PortsOverview` component** accepting optional `networkId` prop.
  - Configurable column set (hide "Network" column when embedded).
  - Pagination, sorting, and basic filters (status, device owner).
- [ ]  **(UI)** Create standalone page at `/networking/ports` using the reusable component.
- [ ]  **(UI)** Integrate reusable component as "Ports" tab inside Network Detail page (Epic #1019).
- [ ]  **(UI)** Create Port Detail view (slide-out panel or sub-route) displaying all fields listed above.

### Phase 2: Write Operations — Create & Update (P2)

- [ ] **(BFF)** Add write endpoints to `openstack-signal` (`POST /v2.0/ports`, `PUT /v2.0/ports/{id}`).
- [ ] **(BFF)** Implement `ports.create` procedure.
- [ ] **(BFF)** Implement `ports.update` procedure.
- [ ] **(UI)** Build "Create Port" modal:
  - Network selector (**required** in standalone view, **pre-filled/hidden** in Network tab).
  - Subnet + IP configuration (auto / specify).
  - Name, Description, Security Groups.
  - "Create Port" button gated via `canUser("network:port:create")`.
- [ ] **(UI)** Build "Edit Port" modal (Name, Description, Security Groups).
  - "Edit" action gated via `canUser("network:port:update")`.

### Phase 3: Write Operations — Delete (P3)

- [ ] **(BFF)** Add delete endpoint to `openstack-signal` (`DELETE /v2.0/ports/{id}`).
- [ ] **(BFF)** Implement `ports.delete` procedure.
- [ ] **(UI)** Implement "Delete Port" flow with confirmation dialog.
  - "Delete" action gated via `canUser("network:port:delete")`.
- [ ] **(UI)** Surface Neutron errors (e.g. port still attached) as clear, user-friendly messages.
- [ ] **(UI)** Implement bulk deletion (multi-select), gated via `canUser("network:port:delete")`.

### Phase 4: Advanced Features & Polish

- [ ] **(UI)** Add Port Security enable/disable toggle with warning states.
- [ ] **(UI)** Add Tag management editor to Port Detail view.
- [ ] **(UI)** Add Allowed Address Pairs management.
- [ ] **(BFF)** Ensure strict server-side policy enforcement on every procedure (`network:port:list`, `get`, `create`, `update`, `delete`).
- [ ] **(UI)** Audit all action-triggering elements to confirm they are gated via `canUser(...)` against the correct policy rule.
- [ ] **(QA)** Write component tests for the reusable overview component (standalone + embedded modes).
- [ ] **(QA)** Write component tests for list, detail, and forms.
- [ ] **(QA)** Write E2E tests for both flows:
  - Global: Navigate to Ports → Create → Update → Delete.
  - Embedded: Navigate to Network → Ports Tab → Create → Update → Delete.
- [ ] **(QA)** Write tests verifying that UI actions are hidden/disabled when the corresponding policy denies access.
