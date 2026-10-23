---
type: plan
date: 2026-10-12
status: analysis
issue: [1019]
---
# Analysis: Networks Management epic #1019

**Base:** `main` @ `6a8dad69`. Companion to the Phase 1 plan [2026-10-12-networks-phase-1-read-operations.md](./2026-10-12-networks-phase-1-read-operations.md).

This note examines the whole epic (P1–P4) along six lines: behavior, filtering and sorting, Juno/UX patterns, code conventions, edge cases, and the evidence needed for acceptance. It draws on:

- the Neutron api-ref and Neutron/neutron-lib `master` source;
- the repo's `networking.json` policy;
- every existing list and detail page;
- `.github/copilot-instructions.md` Part B;
- Juno `@cloudoperators/juno-ui-components@9.4.0`, the pinned version (`packages/aurora/package.json:86`).

Paths are relative to `packages/aurora/src/` unless stated otherwise. `C` = `client/routes/_auth/projects/$projectId`.

## Verdict

- **The epic is sound in intent but should not be implemented as written.**
- **Its code drafts conflict with the repo on all 13 points checked.** One of them is a security hole: the context reads `x-project-id`/`x-auth-token` headers.
- **Its permission keys are wrong:** it uses `network:network:*`, the repo uses `network:networks:*`.
- **Two acceptance criteria rest on wrong Neutron assumptions:**
  - delete "blocked if subnets exist": Neutron auto-deletes subnets;
  - create "for users": in this deployment create, update and delete require `network_admin`.
- **The Phase 1 plan is broadly correct.** It has 2 real bugs, 1 admin-visibility gap that is more serious than the risk it does flag, and several Part B deviations. All are listed in [§7](#7-corrections-to-the-phase-1-plan).

## 1. Behavior (Neutron semantics)

### 1.1 Visibility

- **Member token.** A plain `GET /v2.0/networks` returns:
  - own networks;
  - networks with an `access_as_shared` or `access_as_external` RBAC rule targeting `*` or this project.

  Source: neutron-lib `model_query.py:155-163`, `external_net_db.py:40`.
- **Admin context.** It skips the project scope entirely, so an unfiltered GET returns every project's networks.
- **This deployment** (`apps/dashboard/src/policies/networking.json:2`):
  - `context_is_admin` = `role:network_admin`, with no owner check.
  - Any project-scoped user with `network_admin` gets an admin context.
  - So the #1321 leak class is a normal case for those users, not an edge case.
- **`shared` is computed per caller.** It is true for a `*` rule **or a rule targeting the caller's project** (`db_base_plugin_common.py:343-356`).
  - The `shared=true` filter uses the same check against the rescoped project, for admin tokens too (`model_query.py:253-288`).
  - So targeted-RBAC networks *are* returned by `shared=true`, and admin tokens do **not** get other projects' shared-to-someone-else networks.
  - The Phase 1 plan's Medium risk row 2 and its live check #2 are therefore wrong; see §7.
- **`router:external=true` is the real admin leak.** It is a property of the network and is applied as a plain result filter (`external_net_db.py:44-50`).
  - An admin token gets **every** external network, including those an operator restricted to other projects with a targeted `access_as_external` rule.
  - Setting `router:external` auto-creates a `*` rule (`external_net_db.py:116`), so this only affects networks that were deliberately restricted.
- **The three-request union is otherwise correct and complete.** Only two RBAC actions exist for networks. It is also Horizon's approach.
- **`get_network` = `rule:default_viewer` = `context_is_viewer or shared`.** There is **no** `rule:external` (`networking.json:34,68`, verified); upstream includes it.
  - Neutron drops list items that fail `get_network`, so members may never see non-shared external networks.
  - Verify this on a live environment. If it holds, the External filter is admin-only in practice.
- **`getById` has no visibility guard.** With an admin token, `GET /v2.0/networks/{id}` returns any project's private network by URL. The list scoping does not protect the detail route.

### 1.2 Attributes

- **Core:** `id`, `name`, `project_id`/`tenant_id`, `admin_state_up`, `status`, `shared`, `subnets`.
- **Extension attributes:** everything else (api-ref "Networks" intro), any of which can be absent:
  - `mtu` (`net-mtu`; writable only with `net-mtu-writable`);
  - `port_security_enabled`;
  - `availability_zone(s|_hints)`;
  - `dns_domain`;
  - `qos_policy_id`;
  - `router:external`;
  - `is_default`;
  - `l2_adjacency`;
  - `ipv4/ipv6_address_scope`;
  - `provider:*`, or `segments` (multi-provider; mutually exclusive with `provider:*`);
  - `tags`;
  - `revision_number`;
  - `created_at`/`updated_at`;
  - `description`.
- **Admin-only fields are absent for non-admins, not null.** Upstream, `provider:*` and `segments` are admin-only. The repo JSON makes them viewer-readable (`networking.json:69-73`), which is SAP-specific.
- **`status` and `admin_state_up` are independent.** ML2 sets `status=ACTIVE` at creation (`db_base_plugin_v2.py:483`) and never derives it from admin state. A network that is administratively down normally still shows `ACTIVE`.
  - The UI must show them as two separate facts.
  - Tests must not assume they move together.

### 1.3 Writes (P2)

- **Create.** Fields: `name`, `description`, `admin_state_up`, `mtu`, `port_security_enabled`, `dns_domain`, `qos_policy_id`, `availability_zone_hints`.
  - Admin-only: `shared`, `router:external`, `is_default`, `provider:*`, `segments`.
- **Update.** Updatable: the same fields minus `availability_zone_hints`. The same fields are admin-only.
- **Permissions** (`networking.json:67,86,95`):
  - `create_network`, `update_network` and `delete_network` all need `context_is_network_admin`, i.e. `network_admin`, globally or on the owning project.
  - Plain members cannot manage networks at all.
  - The flags (`:79-80,88,92`) need `context_is_admin`.
- **MTU:**
  - minimum 68, or 1280 if the network has IPv6 subnets (`db_base_plugin_v2.py:550-570`);
  - maximum is the deployment's physical MTU, and exceeding it returns 400;
  - existing instances need a hard reboot to pick up a change (api-ref).
- **Error cases:**
  - `shared` true→false returns 409 `InvalidSharedSetting` if other projects use the network.
  - `router:external` true→false is blocked by gateway ports and floating IPs.
  - `revision-if-match`: `If-Match: revision_number=N` → 412 on conflict. A 412 handler already exists.
- **Delete** (`db_base_plugin_v2.py:572-620`):
  - **Subnets are deleted automatically.**
  - Ports whose `device_owner` is in `AUTO_DELETE_PORT_OWNERS` (`network:dhcp`, `network:distributed`, `network:floatingip_agent_gateway`) are deleted too.
  - Any other port causes 409 `NetworkInUse`, and the message lists the port IDs. Examples: router interfaces, VMs, load balancers, other projects' ports on a shared network.
  - The meaningful pre-check is `GET /v2.0/ports?network_id=X` minus the auto-delete owners, grouped by `device_owner`. It is still racy, so a 409 must always be handled.
  - Optional `network-cascade-delete` extension (`cascade=true`); detect it via `/v2.0/extensions`.
- **Bulk delete:** Neutron has no bulk DELETE, so the BFF fans out per ID. Each result is one of:
  - 204 → success;
  - 404 → already gone, treat as success;
  - 409 → in use, show the ports;
  - 403 → not allowed.
- **404 vs 403:** Neutron returns **404** for objects the caller may not see; 403 appears mostly for action or field-level denials. The detail page's 403 branch will rarely fire.

### 1.4 Tags (P3)

- **Endpoints:**
  - `PUT /networks/{id}/tags` with `{"tags":[…]}` replaces the list (200);
  - `PUT …/tags/{tag}` adds one tag (201);
  - `DELETE …/tags/{tag}` removes one tag (204);
  - `DELETE …/tags` removes all tags (204).
- **Limits:** at most **50 tags** per resource, each at most 255 characters, all unique (`tagging.py:55-56,112-116`).
- **Commas** are accepted on write but are the filter separator, so a tag containing one can never be filtered on.
- **URL-unsafe characters** break the single-tag endpoints. Prefer PUT with the full list.
- **Concurrency:** last writer wins.
- **Policy:** the repo names the rules `get/update/delete_networks_tags` (`networking.json:77,93,96`). Update and delete need `network_admin`. Upstream 2025.1 renamed them to `*_network:tags`, keeping the old names as aliases.

### 1.5 Subnets and ports tabs (P3)

- **Subnets.** Visibility follows the network (`db_base_plugin_common.py:199-202`), so `GET /v2.0/subnets?network_id=X` is safe.
- **Ports:**
  - A member sees their own ports plus every port on networks they own (`db_base_plugin_v2.py:118-131`).
  - An **admin token sees all projects' ports**. That is #1321 again on shared or external networks, so filter by `project_id` unless the network is owned by the current project.
- **IP availability.** `network-ip-availability` is admin-only upstream (non-admins get 404). The repo JSON allows viewers (`networking.json:75-76`). Treat it as optional.

## 2. Filtering, sorting, pagination

### 2.1 Neutron's capabilities

- **Filters are equality only.** Repeated parameters are ORed; different parameters are ANDed.
  - `name=` is **exact**. The epic's "Name filter" must be a BFF substring search, like Routers and Security Groups.
- **Unknown filter keys → 400** when `filter-validation` is on (the default).
- **Tags:** `tags`, `tags-any`, `not-tags`, `not-tags-any`, with comma-separated values.
- **Sortable keys:** `admin_state_up`, `availability_zone_hints`, `id`, `mtu`, `name`, `status`, `project_id`. Extension attributes such as `router:external` can't be sorted. Over a three-request union only BFF sorting is meaningful anyway.
- **`pagination_max_limit`** silently caps **each** of the three requests on its own. The fix is cheap: follow `networks_links` `next` inside the fetch helper.

### 2.2 How the repo's lists do it

| List | Fetch | Filters | Search | Sort | Pagination | URL |
| --- | --- | --- | --- | --- | --- | --- |
| Routers (newest, #1355) | `use()` + Suspense | BFF, no UI | BFF id/name/description, trimmed | Neutron-side | client, 50 | per-field fallback; sort/search `replace`, page push |
| Security Groups | `useQuery` + `placeholderData` | own ∪ shared union in BFF; typed `filterConfig` | BFF, not trimmed in schema | BFF, Name only | none | **no `validateSearch`**; `replace` |
| Floating IPs | `useQuery` + `placeholderData` | Neutron-side status | BFF | Neutron-side, default status | none | `validateSearch`, sort/filter **push** |
| Images | Suspense | Glance-side + multi-value `in:` | BFF name | Glance-side | **server marker**, 50 | no `validateSearch` |
| Flavors | Suspense | public ∪ private, **degrades on partial failure** (`server/Compute/routers/flavorRouter.ts:125-140`) | BFF | BFF | client, 50 | `replace` |
| Swift/Ceph | `useQuery` | none | client, untrimmed (FOLLOW-UPS 25) | client | none | strict `z.object` |

**The house pattern for a union list:**
- BFF union → dedupe → filter → search → sort, as in Security Groups;
- a typed single-value `filterConfig`;
- search debounced at 500 ms;
- client pagination of 50 with `page` in the URL;
- `replace` for sort, filter and search, `push` for page changes.

The Phase 1 plan matches this pattern.

**Choices the networks page must make deliberately:**
- **Fetch model:** `useQuery` (Security Groups, Floating IPs) or Suspense (Routers, Flavors, Images; the Part B references are Flavors and Ceph). Either works; state the reason in the plan.
- **Partial failure:** Flavors already degrades when one of its requests fails. That is house precedent *against* the plan's "fail the whole list, as Security Groups does".
- **Retry on error:** Routers offers "Try Again"; the Security Groups grid error has none. Part B rule B.6 asks for a retry.

## 3. Juno / UX patterns

### 3.1 Part B rules that apply

| Rule | Repo practice | What the epic needs |
| --- | --- | --- |
| **B.1 status as `Badge`** | Network pages show status three ways: Routers plain text, Floating IPs icon + hex colours, Ceph a `Badge` | `Badge` plus text label (B.14: not colour alone). ACTIVE→success, BUILD→info, DOWN→warning, ERROR→error, unknown→default. On the detail page put it in `ContentHeader badges`. |
| Empty value | em dash `"—"` 26×, en dash `"–"` 14× (Routers and Flavors are mixed) | Use `"—"` everywhere |
| B.19 casing | Title-case headers; no ALL CAPS. Routers' `UP`/`DOWN` breaks this. | `Up`/`Down` |
| B.2 list zones | Only Security Groups wraps zones 1–2 in `juno-pattern-datagrid-header` inside `-outer` (`SecurityGroupsList.tsx:248-249`; FOLLOW-UPS 35) | Both wrappers |
| B.6 states | Loading, error and empty go inside grid rows. Juno 9.4.0 `Status` has `no-matches`. A page-level 403 is an **info** `Message` with the standard copy. | `no-matches` when a filter or search is active; error with retry |
| B.15 rows and actions | Row click; action cell `onClick=stopPropagation`, `className="items-end pr-0"`, `PopupMenu` | Same |
| B.8 permissions | `use<Feature>Permissions`, `staleTime: Infinity`, default false, props `can<Verb><Noun>`. Disable with an explanation when most users have the feature; hide when it is privileged. The repo hides in about 64 places and disables in 2. | Network CRUD is `network_admin`-only, i.e. privileged, so **hide** |
| B.9 URL state | Tabs in the URL. Only Images declares `tab`, and even it doesn't read it. | P3 tabs: `tab` in the URL |
| B.5 modals | Name in the body, not the title. The Security Groups delete dialog breaks this; don't copy it. | — |
| B.11 forms | `@tanstack/react-form` + Zod preferred. Security Groups uses hand-rolled validation. | Create/Edit modals use react-form + Zod |

### 3.2 Models to copy per phase

- **Detail page actions (P2):** `ContentHeader actions` holding a `PopupMenu` (`moreVert` + `aria-label`), with Delete after a separator (`C/compute/flavors/$flavorId.tsx:217-251`).
- **Delete with pre-check (P2):** `storage/-components/Swift/Containers/DeleteContainerModal.tsx:55-202`:
  - a live query runs when the modal opens;
  - a `Status progress` shows while it checks;
  - a blocked delete turns Confirm into a primary `Close`;
  - a pre-check error shows as `role="alert"` and disables Confirm;
  - an extra-risk `Checkbox` covers the risky case.

  Typed-`delete` confirmation for high severity: `DeleteSecurityGroupDialog.tsx`, `ReleaseFloatingIpModal.tsx`.
- **Admin State control (P2):** the repo uses `Checkbox` for booleans (`CreateSecurityGroupModal.tsx:171`). Juno 9.4.0 also has `Switch`, which no repo page uses yet. Choose one.
- **Subnets/Ports tabs (P3):**
  - `RouterDetailsView.tsx:113-139` + `RouterInterfacesTable`: a sub-list with its own query, retry and empty state.
  - Controlled tabs as in `SecurityGroupTabs.tsx:18-28`.
  - Set `tabStyle="content"` (FOLLOW-UPS 42). Routers' `TabNavigation` is a 6th instance that item 42 doesn't list.
- **Bulk delete (P3):** Juno 9.4.0 has **no** row selection, only `isSelected` styling. Copy `compute/images/-components/List.tsx:326-380`:
  - a `Checkbox` cell;
  - a tri-state select-all scoped to the current page;
  - a bulk `PopupMenu`, shown only with permission;
  - a results modal (`DeleteImagesModal`).

  On the server, reuse `processBulkOperation` (`server/Compute/helpers/imageHelpers.ts:631`). The Security Groups list already has a disabled `hasAnyBulkAction` scaffold.
- **Tag editor (P3):** Juno has no tag input, only `Pill`. Promote `storage/-components/Ceph/Buckets/TagInput.tsx` to `client/components/`. Its "This value already exists" string isn't translated. `EditImageDetailsModal.tsx:139-249` is a second precedent.

## 4. Code conventions

### 4.1 The epic's draft code vs the repo

| # | Draft | Repo convention |
| --- | --- | --- |
| 1 | `context.ts` reads `x-user-id`/`x-project-id`/`x-auth-token` headers and `NEUTRON_URL` | `AuroraPortalContext` with an `openstack` session; the endpoint comes from the catalog. **Trusting headers would be a security hole.** |
| 2 | `inferAsyncReturnType` | deprecated in tRPC v11 |
| 3 | `routers/networks/{router,types,service}.ts` | `server/Network/{routers,types,helpers}/` with colocated tests |
| 4 | `router` from `../../trpc/trpc` | `auroraRouter` / plain router objects in `server/trpc.ts` |
| 5 | `protectedProcedure` | `projectScopedProcedure`; without `project_id` there is no token rescoping |
| 6 | `NetworkService` class | no service classes: `getNetworkService(ctx)` + helpers |
| 7 | camelCase `adminStateUp`, `portSecurityEnabled` | snake_case Neutron names |
| 8 | `id` | `network_id` with `resourceIdSchema` + `validateAndEncodeResourceId` |
| 9 | `name: z.string()` | `nameSchema` (trim, max 255; `types/router.ts:26,29`) |
| 10 | strict `status` enum, required `mtu`/`subnets`, no `project_id` | tolerant schema; extension fields optional |
| 11 | no error handling | `withErrorHandling` + `ErrorHandler` + `requestOrThrow` + `parseOrThrow` |
| 12 | list `name` input | exact match in Neutron, so BFF search instead |
| 13 | `network:network:*` | `network:networks:*` (`PERMISSION_KEY_PATTERN.md`; resources are plural) |

### 4.2 Permissions

- **Existing keys:** `network:networks:{read,list,create,update,delete}` (`server/Network/routers/permissionRouter.ts:19-23`). They map to `get_`, `create_`, `update_` and `delete_network`.
- **P2–P4 need new keys** (names to settle): `create_shared`, `create_external`, `update_shared`, `update_external`, `update_tags`, `delete_tags`.
- **`canUser` passes no target** (`policies/createPermissionRouter.ts:51,154`). So:
  - it can't evaluate owner-dependent decisions for a specific network, such as "is this a shared or external network from another project";
  - the UI must also gate on `network.project_id === projectId` (as Security Groups does with `isReadOnly`, `SecurityGroupTableRow.tsx:51,88-90`).
- **P4's "BFF strict policy checks" has no precedent.** No router enforces policy in the BFF (FOLLOW-UPS 12). Either drop it, since Neutron enforces policy itself, or design it together with item 12.

### 4.3 Other conventions

- **Tests:** mock Neutron errors as **rejections with `SignalOpenstackApiError`**, as `routersRouter.test.ts:105,134` does. The Security Groups and Floating IP tests use `{ok:false}` mocks, which hide real behavior (FOLLOW-UPS 30).
- **Every BFF feature PR in the repo ships:**
  - a `.changeset/*.md`;
  - a design doc in `packages/aurora/docs/` (Routers added `0010_routers_bff.md`). The next free number is **0017**; 0015 is used twice.
- **Service key lists are maintained by hand in four places:**
  - `buildNavSections.ts`;
  - `$projectId/index.tsx`;
  - `packages/aurora/README.md:183,210`;
  - **`apps/dashboard/.env.example:11-12`**, which the Phase 1 plan misses; it also lacks `routers` and still lists `pca`.
- **Naming is inconsistent across sub-routers.** Settle these once for networks:
  - procedure `delete` (Routers) vs `deleteById` (Security Groups);
  - ID fields `router_id` vs `securityGroupId`; use `network_id`.
- **Commit scopes:** `bff` (server), `aurora` (client), `portal` for the PR title. All are allowed in `commitlint.config.mjs`.

## 5. Edge cases

| Area | Case | Expected behavior |
| --- | --- | --- |
| Visibility | Admin-context token (incl. project `network_admin`) | List shows no other project's private networks and no external networks restricted to other projects |
| Visibility | Admin token opens `/network/networks/<foreign-private-id>` | Not found (BFF guard), not the network |
| Visibility | Network shared via targeted RBAC to this project | Listed, Shared = Yes |
| Visibility | Member, external network without `shared` | Possibly invisible (`get_network` lacks `rule:external`); verify live |
| Data | Empty or duplicate name | Shown by ID; all routing by ID |
| Data | Missing `mtu`, `port_security_enabled`, AZs, `router:external` | "—"; parse doesn't fail |
| Data | Admin-only fields absent (not null) | Parse OK |
| Data | `status` ACTIVE with `admin_state_up=false` | Two independent columns |
| Data | Unknown status value | Default badge with the raw text |
| Data | Multi-segment network (`segments[]`, no `provider:*`) | Parse OK |
| Scale | `pagination_max_limit` set | Each request follows `networks_links`; no silent truncation |
| Scale | Part of the union fails (e.g. 403 on the external request) | Decision: degrade (Flavors precedent) or fail with a readable error |
| URL | Hand-typed `?shared=false` | Parsed: TanStack JSON-parses search values into boolean `false`, which a `z.enum(["true","false"])` schema rejects |
| URL | Deep link `?page=2` on a cold load | Stays on page 2 |
| URL | Search of only spaces | Treated as no search |
| P2 delete | Network has only DHCP/metadata ports + subnets | Allowed; warns that N subnets will be deleted |
| P2 delete | Router interface / VM / foreign-project ports | Blocked in pre-check; a 409 lists the port IDs |
| P2 delete | Network deleted meanwhile | 404 → success / toast |
| P2 update | MTU < 68, < 1280 with IPv6, > physical | Validation / readable 400; reboot warning |
| P2 update | Unshare while other projects use it | 409 explained |
| P2 update | Concurrent edit | `If-Match` → 412 explained (if adopted) |
| P2/P4 | Shared or external network from another project | Edit, Delete and Tags hidden |
| P2/P4 | Member without `network_admin` | No Create, Edit or Delete controls |
| P3 tags | 51st tag, >255 characters, duplicate, comma | Rejected client-side |
| P3 ports tab | Admin token on a shared network | Only this project's ports |
| P3 bulk | Mixed results | Per-row result; 404 counts as success |

## 6. Evidence for acceptance

How each acceptance criterion of the epic can be shown to be met, and whether it needs rewording.

| Epic criterion | Evidence that proves it | Rewording needed |
| --- | --- | --- |
| tRPC BFF with full Zod validation | `network.test.ts` (full, minimal, unknown-status and admin-field-absent payloads); router tests assert `PARSE_ERROR` on a malformed response; inputs use `resourceIdSchema`/`nameSchema` | — |
| List / view / create / update / delete | Router unit tests per procedure that assert the exact Neutron URL, query, body and headers; component tests per modal; manual check on DevStack, since the mock is GET-only for networks | Name the actor: in this deployment create, update and delete are `network_admin`-only |
| Detail lists associated subnets | Sub-list test (loading, empty, error, retry); Neutron query `subnets?network_id=` asserted | — |
| MTU / Admin State / Shared visible and manageable | Details view test; edit modal test incl. MTU bounds; admin-only flags rendered only with the permission | "Manageable" for Shared/External = admin only |
| Permissions hide or disable actions | `useNetworkPermissions` test (default false); row and header tests with permission × ownership matrix; manual check as member, `network_admin` and cloud admin | Specify **hide** (B.8, privileged) and the ownership rule |
| User-friendly Neutron errors | Tests mapping 400/403/404/409/412 to messages via `NetworkErrorHandlers`, using **rejected** `SignalOpenstackApiError` mocks; 409 with the port list on delete | Replace "networks with active ports" with "non-auto-deleted ports"; subnets don't block |
| Aurora design system | Part B checklist in the PR description (B.1 Badge, B.2 zones, B.6 states, B.8, B.15, B.19); screenshots light and dark | — |
| Unit / integration / E2E coverage | `pnpm test` counts per suite; Playwright create → update → delete flow against DevStack (P4); the mock can't do writes | Name E2E as P4-only and environment-bound |
| *(missing)* Admin-token safety | Router test asserting the exact three query strings + no unscoped call; `getById` guard test; live check with a `network_admin` user | **Add this criterion** |

**Environment limits for evidence:**
- The local mock behaves like an admin token, which is good for leak tests.
- It stores `shared` as a plain boolean, with no RBAC computation.
- It ignores `limit` and `marker`.
- It returns `[]` instead of 400 for unknown filters.
- It has no network POST/PUT/DELETE and no tags.
- So RBAC semantics, writes, tags, the `pagination_max_limit` check, and the `get_network`-without-`external` effect can only be shown on DevStack or a live environment.

## 7. Corrections to the Phase 1 plan

The plan file is a historical record. These go into a revision of it, or are applied during implementation.

1. **[High, security] Guard `getById`.** Return NOT_FOUND unless the network is:
   - owned by `project_id`;
   - `shared`; or
   - external and allowed for this project.

   Add a test for it.
2. **[High, security] Restricted external networks leak to admin tokens through the `router:external=true` request.** Keep an external row only if any of these holds:
   - `project_id` is this project;
   - it is `shared`;
   - an `access_as_external` RBAC rule targets `*` or this project (`GET /v2.0/rbac-policies?object_type=network&action=access_as_external`).

   Or at minimum document the leak and live-check it.
3. **Risk row 2 and live check #2 are wrong** (§1.1). Replace them with: "an admin sees restricted external networks of other projects".
4. **Bug: deep-linked pages are reset.** The page clamp `!isPlaceholderData && page > totalPages` fires on the first load: `data` is undefined, so `totalPages = 1`. Also require `data !== undefined` and no error.
5. **Bug: boolean URL params.** TanStack's default `parseSearch` JSON-parses values, so a hand-typed `?shared=false` becomes boolean `false` and `z.enum(["true","false"])` drops it. Accept `boolean | "true" | "false"` and normalize. Security Groups has the same latent bug, worth a follow-up.
6. **Follow `networks_links`** in `fetchNetworks`. `pagination_max_limit` truncates each request on its own.
7. **Status as `Badge`** (B.1), placed in `ContentHeader badges` on the detail page. This resolves the plan's open question.
8. **Use `"—"` everywhere.** The plan mixes `–` and `—`.
9. **Add the `juno-pattern-datagrid-header` wrapper** (FOLLOW-UPS 35).
10. **Use the `no-matches` status** when filtered.
11. **Add a retry on the grid error.**
12. **Use B.6 copy for 403.**
13. **Add `className="items-end pr-0"`** to the action cell.
14. **Base "search active" on `search.trim()`** (FOLLOW-UPS 25/47).
15. **Partial failure:** the Flavors precedent exists. Decide between degrade and fail; don't present "Security Groups parity" as the house pattern.
16. **Missing deliverables:**
    - a `.changeset` entry (the repo ships one per BFF feature);
    - `packages/aurora/docs/0017_networks_bff.md`;
    - `apps/dashboard/.env.example` key list.

    The planner was told to skip the changeset because I misread a memory note, which only bans mentioning changesets in PR descriptions.
17. **Tests use rejecting `SignalOpenstackApiError` mocks**, not `{ok:false}`. State this explicitly.
18. **The 403 branch on the detail page rarely fires.** Neutron returns 404 for invisible networks. Keep the branch, but don't build tests around a 403 from GET.
19. **Status and Admin State are independent.** The DOWN + `admin_state_up:false` fixture is fine, but add an ACTIVE + admin-down fixture.

## 8. Proposed edits to the epic text

- **Permission keys:** `network:network:*` → `network:networks:*`. List the new flag and tag keys.
- **Drop the reference implementation**, or replace it with a pointer to the repo conventions (§4.1).
- **Remove the Phase 1 subtask** "Create/Extend Neutron client wrapper in `openstack-signal`": `ctx.openstack.service("network")` already exists.
- **Delete pre-check:** "warn that subnets will be deleted; block only on non-auto-deleted ports; show the port IDs from a 409".
- **State that network create, update and delete are `network_admin`-only in this deployment.** "Hide for unauthorized users" then means most users see a read-only page.
- **Add an acceptance criterion:** admin-context tokens never show other projects' private or restricted networks or ports, in the list, the detail page or the Ports tab.
- **Name the limits:** MTU bounds with the reboot warning; at most 50 tags of up to 255 characters, no commas; bulk delete reports per-item results.
- **P4 "BFF strict policy checks":** reword to "UI gating via `canUser` + ownership", unless BFF enforcement is designed with FOLLOW-UPS 12.

## 9. Decisions needed

1. **External networks in the list.** Add the RBAC-based restriction now (one extra request), or document the leak and live-check it first?
2. **Partial failure of the union.** Degrade (Flavors) or fail (Security Groups)?
3. **Fetch model.** `useQuery` (Security Groups) or Suspense (Routers, the newest)?
4. **Phase 1 plan.** Revise it with §7, or keep it and apply §7 during implementation?
5. **Epic text.** Propose the §8 edits upstream as an issue comment, or keep them local?
6. **Later phases:**
   - Admin State control: `Checkbox` or `Switch`;
   - optimistic concurrency with `If-Match`;
   - cascade delete when the extension is present;
   - where the tag editor lives.

<!-- related:auto — generated from pr/issue properties by tools/update-related.py; do not edit by hand -->
## Related

- plan · 2026-10-12 · [2026-10-12-networks-phase-1-read-operations](2026-10-12-networks-phase-1-read-operations.md)
- pr-report · 2026-10-17 · [1385-neutron-networks-bff-read-only-networks-page](../aurora-dashboard-kb/prs/1385-neutron-networks-bff-read-only-networks-page.md)
- pr-report · 2026-10-17 · [1386-network-and-verify-do-not-merge](../aurora-dashboard-kb/prs/1386-network-and-verify-do-not-merge.md)
- pr-report · 2026-10-23 · [1383-neutron-networks-bff-read-only-networks-page](../aurora-dashboard-kb/prs/1383-neutron-networks-bff-read-only-networks-page.md)
