# #1133: [EPIC](authorization):  OpenStack Key Manager (Barbican) — Secrets, Containers & Orders Management

State: OPEN · https://github.com/cobaltcore-dev/aurora-dashboard/issues/1133


## Description

Implement comprehensive OpenStack Key Manager (Barbican) management within the Aurora Dashboard. Barbican is OpenStack's dedicated service for managing sensitive data such as symmetric/asymmetric keys, certificates, and raw secrets, as well as related grouping constructs (Containers) and provisioning workflows (Orders).

The Barbican API exposes several resource groups. This epic focuses **exclusively** on the three most commonly used ones:

- **Secrets** (CRUD) — individual pieces of sensitive data (keys, certificates, passphrases, etc.) 
- **Containers** (CRUD) — logical groupings of related secrets (e.g. a certificate + its private key)
- **Orders** (CRUD) — asynchronous provisioning requests to have Barbican generate a secret or container on the user's behalf 

The following Barbican resources are **out of scope** for this epic and may be addressed in follow-up work: Secret Consumers, Secret Metadata, Secret Stores, Container Consumers, ACLs, and Quotas.

All three resource types are surfaced in a **single Key Manager page** organized as **tabs** (Secrets / Containers / Orders). The Side Navigation exposes only a single entry (**"Key Manager"**) inside the *Authorization* group; the sub-resources are reached exclusively via tabs within that page.

All operations are project-scoped, utilize existing OpenStack Keystone tokens, and strictly respect access controls defined by the Aurora/OpenStack policy engine.

**API Documentation:**
- Secrets API: https://docs.openstack.org/barbican/latest/api/reference/secrets.html 
- Containers API: https://docs.openstack.org/barbican/latest/api/reference/containers.html 
- Orders API: https://docs.openstack.org/barbican/latest/api/reference/orders.html 

---

## Dependencies & Prerequisites

- Aurora authentication / Keystone token handling is available.
- Aurora policy engine (`canUser(...)`) is available for `key-manager:*` permissions.
- Aurora side navigation supports adding an entry under the *Authorization* group.


---

## Objectives

- Provide a complete tRPC-based BFF for Barbican Secrets, Containers, and Orders operations.
- Deliver a **single Key Manager page** with three tabs: **Secrets**, **Containers**, **Orders**.
- Add exactly **one** entry ("Key Manager") to the Side Navigation, inside the *Authorization* group.
- Enable users to manage the full lifecycle (CRUD) of Secrets, Containers, and Orders.
- Enforce strict RBAC via Aurora's policy engine (`key-manager:secrets:*`, `key-manager:containers:*`, `key-manager:orders:*`). All action-triggering UI elements must be gated via `canUser(...)`.

---

## Acceptance Criteria

-  tRPC BFF is implemented with complete Zod schema validation for Secrets, Containers, and Orders.
-  A single **"Key Manager"** entry is added to the Side Navigation under the *Authorization* group.
-  The Key Manager page exposes three tabs: **Secrets**, **Containers**, **Orders**.
-  Each tab renders its own overview list with the columns specified in the [UI Specification](#ui-specification).
-  Users can list, view, create, update, and delete Secrets, Containers, and Orders (P1, P2 & P3).
-  Detail views are provided for each resource type (slide-out panel or sub-route).
-  All action-triggering UI elements (Create, Edit, Delete, etc.) are gated using `canUser(...)` against the corresponding `key-manager:*` policy rules and are hidden/disabled for unauthorized users.
-  Comprehensive error handling provides user-friendly feedback for Barbican errors.
-  All UI components follow the Aurora design system.
-  Complete testing coverage (unit, integration, E2E) is achieved.

---

## Technical Architecture & Request Flow

### System Architecture Flow

1. **UI Layer:** User navigates to *Authorization → Key Manager* and selects one of the tabs (Secrets / Containers / Orders).
2. **BFF Layer (tRPC):** Validates input, checks permissions.
3. **Service Layer:** Uses the internal **`openstack-signal`** library to communicate with the Barbican API via standard HTTP methods (`GET`, `POST`, `PUT`, `DELETE`). All requests are authenticated with the current Keystone token.

### Request Flow Example (List Secrets)

- Step 1: UI (Secrets tab) triggers `secrets.list({})`.
- Step 2: BFF validates input and permissions.
- Step 3: BFF invokes `openstack-signal` → `GET /v1/secrets`.
- Step 4: Barbican returns paginated secret list.
- Step 5: BFF returns the parsed/validated result to the UI.

### Request Flow Example (Create Order)

- Step 1: UI triggers `orders.create({ type, meta, ... })`.
- Step 2: BFF validates input and permissions.
- Step 3: BFF invokes `openstack-signal` → `POST /v1/orders`. 
- Step 4: Barbican accepts the order and returns its reference.
- Step 5: BFF returns success; UI invalidates the orders list cache.

---

## API Integration Mapping

All calls are performed by the BFF through the `openstack-signal` library.

### Secrets 

| Feature | HTTP Method | Endpoint | Priority |
|---------|-------------|----------|----------|
| List secrets | `GET` | `/v1/secrets` | **P1** |
| Get secret details | `GET` | `/v1/secrets/{uuid}` | **P1** |
| Get secret payload | `GET` | `/v1/secrets/{uuid}/payload` | **P1** |
| Create secret | `POST` | `/v1/secrets` | **P2** |
| Update secret | `PUT` | `/v1/secrets/{uuid}` | **P2** |
| Delete secret | `DELETE` | `/v1/secrets/{uuid}` | **P3** |

### Containers 

| Feature | HTTP Method | Endpoint | Priority |
|---------|-------------|----------|----------|
| List containers | `GET` | `/v1/containers` | **P1** |
| Get container details | `GET` | `/v1/containers/{uuid}` | **P1** |
| Create container | `POST` | `/v1/containers` | **P2** |
| Delete container | `DELETE` | `/v1/containers/{uuid}` | **P3** |

*Note: Barbican does not expose a direct `PUT /v1/containers/{uuid}` endpoint. "Edit" for containers is limited to managing associated secrets via `POST/DELETE /v1/containers/{container_uuid}/secrets`. If a general container update is not supported by the API, the "Edit" action in the UI is scoped to secret associations only.*

### Orders

| Feature | HTTP Method | Endpoint | Priority |
|---------|-------------|----------|----------|
| List orders | `GET` | `/v1/orders` | **P1** |
| Get order details | `GET` | `/v1/orders/{uuid}` | **P1** |
| Create order | `POST` | `/v1/orders` | **P2** |
| Delete order | `DELETE` | `/v1/orders/{uuid}` | **P3** |

*Note: Barbican does not expose a `PUT /v1/orders/{uuid}` endpoint — orders are immutable provisioning requests. The "Update" action is therefore not applicable to Orders.*

---

## UI Specification

### Navigation

- **Side Navigation:** A single entry **"Key Manager"** is added under the *Authorization* group. This is the only navigation entry for this epic.
- **Page Layout:** The Key Manager page contains a tab bar with three tabs:
  - **Secrets** (default active tab)
  - **Containers**
  - **Orders**

### Secrets Tab — Overview Table

| Column | Content |
|--------|---------|
| **Name / ID** | Secret name and UUID |
| **Type** | Secret type (e.g. `symmetric`, `public`, `private`, `passphrase`, `certificate`, `opaque`) |
| **Content Types** | e.g. `application/octet-stream`, `text/plain` |
| **Status** | e.g. `ACTIVE`, `PENDING`, `ERROR` |

### Containers Tab — Overview Table

| Column | Content |
|--------|---------|
| **Name / ID** | Container name and UUID |
| **Type** | Container type (e.g. `generic`, `rsa`, `certificate`) |
| **Status** | e.g. `ACTIVE`, `PENDING`, `ERROR` |

### Orders Tab — Overview Table

| Column | Content |
|--------|---------|
| **Name / ID** | Order name / reference and UUID |
| **Type** | Order type (e.g. `key`, `asymmetric`, `certificate`) |
| **Status** | e.g. `ACTIVE`, `PENDING`, `ERROR` |

### Detail Views

Each resource type has its own detail view (slide-out panel or sub-route) showing all attributes returned by Barbican, including timestamps, references, associated resources, and (for Secrets) an option to reveal the payload where permitted.

All UUIDs and references support **copy-to-clipboard**.

---

## Permissions & Policy Enforcement

Access control is governed entirely by Aurora's policy engine using the `key-manager:*` rule set:

- `key-manager:secrets:list` / `get` / `create` / `update` / `delete`
- `key-manager:containers:list` / `get` / `create` / `delete`
- `key-manager:orders:list` / `get` / `create` / `delete`

### Policy File

```json
{
  "context_is_cloud_keymanager_admin": "role:cloud_keymanager_admin",
  "member": "role:member or role:Member",
  "keymanager_viewer": "role:keymanager_viewer",
  "keymanager_admin": "role:keymanager_admin",
  "context_is_keymanager_admin": "rule:context_is_cloud_keymanager_admin or rule:keymanager_admin",
  "context_is_keymanager_editor": "(rule:context_is_keymanager_admin) and not project_id:nil",
  "context_is_keymanager_viewer": "(rule:context_is_keymanager_editor or rule:keymanager_viewer) and not project_id:nil",

  "key-manager:secrets:list": "rule:context_is_keymanager_viewer",
  "key-manager:secrets:get": "rule:context_is_keymanager_viewer",
  "key-manager:secrets:payload": "rule:context_is_keymanager_viewer",
  "key-manager:secrets:create": "rule:context_is_keymanager_editor",
  "key-manager:secrets:delete": "rule:context_is_keymanager_editor",
  "key-manager:secrets:update": "rule:context_is_keymanager_editor",

  "key-manager:containers:list": "rule:context_is_keymanager_viewer",
  "key-manager:containers:get": "rule:context_is_keymanager_viewer",
  "key-manager:containers:create": "rule:context_is_keymanager_editor",
  "key-manager:containers:delete": "rule:context_is_keymanager_editor",
  "key-manager:containers:update": "rule:context_is_keymanager_editor",

  "key-manager:orders:list": "rule:context_is_keymanager_viewer",
  "key-manager:orders:get": "rule:context_is_keymanager_viewer",
  "key-manager:orders:create": "rule:context_is_keymanager_editor",
  "key-manager:orders:delete": "rule:context_is_keymanager_editor",
  "key-manager:orders:update": "rule:context_is_keymanager_editor"
}
```

### UI Requirements

- Every action-triggering UI element **must** be gated via `canUser(...)`:
  - **"Create Secret / Container / Order" button** → `canUser("key-manager:<resource>:create")`
  - **"Edit Secret" action** → `canUser("key-manager:secrets:update")`
  - **"Delete" action** → `canUser("key-manager:<resource>:delete")`
  - **"Reveal payload" action** (Secrets) → `canUser("key-manager:secrets:get")` (or a dedicated payload permission where applicable)
  - **Bulk actions** → gated against the corresponding rule.
- Elements for which the user lacks permission must be **hidden or disabled** (with a tooltip where appropriate).
- Read-only elements (list, detail view) require the corresponding `list` / `get` permissions; if denied, the view degrades gracefully.
- If a whole tab is not permitted for the user (e.g. no `list` permission on Orders), the tab is hidden or renders an access-denied state.

### BFF Enforcement

The BFF enforces the same policy rules server-side on every tRPC procedure. UI-side `canUser(...)` checks are a UX aid; the BFF remains the source of truth. Any operation rejected by policy or by Barbican itself surfaces as a user-friendly error in the UI.

---

## Subtasks (Implementation Plan)

_Tasks will be converted to GitHub issues during sprint planning._

### Phase 1: Foundation & Read Operations (P1)

  - `Secret` (fields: `secret_ref`, `name`, `secret_type`, `algorithm`, `bit_length`, `mode`, `content_types`, `status`, `created`, `updated`, `creator_id`, `expiration`) [1]
  - `Container` (fields: `container_ref`, `name`, `type`, `status`, `secret_refs`, `consumers`, `created`, `updated`) [2]
  - `Order` (fields: `order_ref`, `type`, `status`, `sub_status`, `sub_status_message`, `meta`, `secret_ref`, `created`, `updated`, `creator_id`) [3]
- [x] **(BFF)** Implement `secrets.list` and `secrets.get` procedures.
- [ ] **(BFF)** Implement `secrets.getPayload` procedure (separate procedure since payload retrieval is a distinct Barbican endpoint) [1].
- [ ] **(BFF)** Implement `containers.list` and `containers.get` procedures.
- [ ] **(BFF)** Implement `orders.list` and `orders.get` procedures.
- [ ] **(UI)** Add **"Key Manager"** entry to the Side Navigation under the *Authorization* group.
- [ ] **(UI)** Build the Key Manager page shell with a tab bar (Secrets / Containers / Orders); default active tab is **Secrets**.
- [ ] **(UI)** Build the **Secrets** overview list with columns: *Name/ID*, *Type*, *Content Types*, *Status* [1].
- [ ] **(UI)** Build the **Containers** overview list with columns: *Name/ID*, *Type*, *Status* [2].
- [ ] **(UI)** Build the **Orders** overview list with columns: *Name/ID*, *Type*, *Status* [3].
- [ ] **(UI)** Implement detail views (slide-out panel or sub-route) for Secrets, Containers, and Orders showing all attributes returned by Barbican.
- [ ] **(UI)** For Secrets, include a "Reveal Payload" action in the detail view, gated via `canUser("key-manager:secrets:get")` [1].
- [ ] **(UI)** Implement copy-to-clipboard for all UUIDs and references (`secret_ref`, `container_ref`, `order_ref`).

#### Screenshots (elektra)
**Secrets**
<img width="1152" height="459" alt="Image" src="https://github.com/user-attachments/assets/80ec295f-62bd-4d5e-a4e2-02f54570c041" />

**Containers**
<img width="1211" height="457" alt="Image" src="https://github.com/user-attachments/assets/022ca8fc-ccfc-47ef-842a-3ad8fb8c2438" />

**Orders**
<img width="1169" height="452" alt="Image" src="https://github.com/user-attachments/assets/fd86122f-a259-4d02-8586-8225d1c78145" />

### Phase 2: Write Operations — Create & Update (P2)

- [ ] **(BFF)** Implement `secrets.create` and `secrets.update` procedures.
- [ ] **(BFF)** Implement `containers.create` procedure.
- [ ] **(BFF)** Implement `containers.updateSecrets` procedure — wraps `POST /v1/containers/{container_uuid}/secrets` and `DELETE /v1/containers/{container_uuid}/secrets` to add/remove secret associations [2].
- [ ] **(BFF)** Implement `orders.create` procedure.
- [ ] **(UI)** Build "Create Secret" modal (Name, Type, Algorithm, Bit Length, Mode, Payload, Content Type, Expiration).
  - "Create" button gated via `canUser("key-manager:secrets:create")`.
- [ ] **(UI)** Build "Edit Secret" modal (metadata fields).
  - "Edit" action gated via `canUser("key-manager:secrets:update")`.
- [ ] **(UI)** Build "Create Container" modal (Name, Type: `generic` / `rsa` / `certificate`, Secret associations).
  - "Create" button gated via `canUser("key-manager:containers:create")`.
- [ ] **(UI)** Build "Manage Container Secrets" flow for adding/removing secret references on an existing container.
  - Actions gated via `canUser("key-manager:containers:update")` (or the applicable rule).
- [ ] **(UI)** Build "Create Order" modal (Type: `key` / `asymmetric` / `certificate`, and type-specific meta fields).
  - "Create" button gated via `canUser("key-manager:orders:create")`.
- [ ] **(UI)** Note: Orders are immutable — no "Edit Order" flow is implemented [3].

### Phase 3: Write Operations — Delete (P3)

- [ ] **(BFF)** Implement `secrets.delete`, `containers.delete`, and `orders.delete` procedures.
- [ ] **(UI)** Implement "Delete" flow with confirmation dialog for each resource type.
  - "Delete" action gated via `canUser("key-manager:<resource>:delete")`.
- [ ] **(UI)** Surface Barbican errors (e.g. container still has associated secrets or consumers) as clear, user-friendly messages.
- [ ] **(UI)** Implement bulk deletion (multi-select) per tab, gated via the corresponding delete permission.

### Phase 4: Polish & Permissions

- [ ] **(BFF)** Ensure strict server-side policy enforcement on every procedure (`key-manager:secrets:*`, `key-manager:containers:*`, `key-manager:orders:*`).
- [ ] **(UI)** Audit all action-triggering elements to confirm they are gated via `canUser(...)` against the correct policy rule.
- [ ] **(UI)** Hide entire tabs when the user lacks the corresponding `list` permission for that resource type.

