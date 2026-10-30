---
type: pr-report
date: 2026-10-30
status: open
pr: [1406]
issue: []
author: edda
branch: edda-networks-brd-spec-guardrails
---

# PR #1406: docs(network): read-only Networks BRD + spec and project guardrails

**Author:** edda · **Status:** open · **Base:** `main` ← `edda-networks-brd-spec-guardrails`
**Size:** 4 files, +642 / −0 · **Created:** 2026-10-29 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

_Reviewed at head [`fd75255a`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406/commits/fd75255aba10148e60788fbd745ee74484640ff8) · base `main` at `948bd2a1` · 2026-10-30 09:37 UTC_

### ⚖️ &nbsp; Verdict

Recommendation: **🟡 Approve with changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **High**

- **Team call** (convention, existing pattern or deferred by a maintainer): CR1, CR2, CR3, CR4
- **Process:** P1

A documentation-only PR adding a comprehensive BRD, engineering spec and project guardrails for a new read-only Networks scope. The specifications are well-structured but contain several inaccuracies that would mislead implementers: a wrong context property name (`ctx.openstackSession` instead of `ctx.openstack`), incomplete router interface device owner types, and incorrect claims about TanStack Query's window-focus refresh behavior and ListToolbar's timestamp format. These documentation bugs won't affect the current codebase but will cause implementation issues when the spec is followed. CI is green; no changeset needed for a docs PR.

### 🔧 &nbsp; Required Changes

| #   | Severity    | Category | Precedent                                                                                       | Issue                                                                                               | Location                                            |
| --- | ----------- | -------- | ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| CR1 | 🟠 Major    | Docs     | —                                                                                               | The spec documents a non-existent context property for accessing the OpenStack session.             | `docs/specs/networks/networks-readonly-spec.md:99`  |
| CR2 | 🟠 Major    | Docs     | existing code                                                                                   | The spec omits distributed and HA router interface device owner types.                              | `docs/specs/networks/networks-readonly-brd.md:145`  |
| CR3 | 🟡 Moderate | Docs     | —                                                                                               | The spec claims window-focus refresh behavior that Aurora explicitly disables.                      | `docs/specs/networks/networks-readonly-spec.md:25`  |
| CR4 | 🟡 Moderate | Docs     | [deferred](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145186) | The spec claims ListToolbar provides relative timestamps when it actually uses absolute timestamps. | `docs/specs/networks/networks-readonly-spec.md:134` |
| P1  | —           | Process  | —                                                                                               | The PR description links no issue                                                                   | PR body                                             |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Wrong context property name in spec** · Docs · `docs/specs/networks/networks-readonly-spec.md:99`
The spec at `docs/specs/networks/networks-readonly-spec.md:99` instructs implementers to access the auth token via `ctx.openstackSession?.getToken()?.authToken`. However, the actual context property exposed by the procedure builders is `ctx.openstack`, not `ctx.openstackSession`. When an implementer copies this code, the token lookup returns `undefined` because the property does not exist, breaking authentication for all Neutron API calls. Copilot flagged this in the PR discussion.
_Fix:_ Replace `ctx.openstackSession` with `ctx.openstack` at line 99.

**CR2 — Incomplete router interface device owners** · Docs · `docs/specs/networks/networks-readonly-brd.md:145`
The BRD at `docs/specs/networks/networks-readonly-brd.md:145` and spec at `docs/specs/networks/networks-readonly-spec.md:212` instruct filtering attached routers by checking only `device_owner === 'network:router_interface'`. The existing codebase in `packages/aurora/src/server/Network/helpers/routerHelpers.ts:224` already recognizes three types: `'network:router_interface'`, `'network:router_interface_distributed'`, and `'network:ha_router_replicated_interface'`. In deployments with distributed (DVR) or high-availability (HA) routers, the attached-routers list will show no routers even when router interfaces exist, breaking router discovery and deep-link features. Copilot flagged this in the PR discussion.
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/server/Network/helpers/routerHelpers.ts:223`.
_Fix:_ Reference the existing `ROUTER_INTERFACE_DEVICE_OWNERS` set from routerHelpers.ts or list all three device owner types at BRD lines 145, 173 and spec lines 212, 234.

**CR3 — Incorrect refetch-on-window-focus claim** · Docs · `docs/specs/networks/networks-readonly-spec.md:25`
Engineering decision E1 at `docs/specs/networks/networks-readonly-spec.md:25` states data loads 'via TanStack Query's default refetch-on-window-focus'. However, Aurora globally disables this at `packages/aurora/src/client/App.tsx:77` with `refetchOnWindowFocus: false`. When implementers rely on this stated behavior, expecting data to refresh when the user returns to the browser tab, the network/port status remains stale until manual navigation. Copilot flagged this in the PR discussion.
_Fix:_ Remove the refetch-on-window-focus claim from E1, or note that implementers would need to override the global default.

**CR4 — Incorrect ListToolbar timestamp format claim** · Docs · `docs/specs/networks/networks-readonly-spec.md:134`
The spec at `docs/specs/networks/networks-readonly-spec.md:25` requires the timestamp be 'rendered relative', and at `docs/specs/networks/networks-readonly-spec.md:134` states ListToolbar provides 'the count + last-updated row... out of the box' (though it does not explicitly claim relative formatting there). However, `packages/aurora/src/client/components/ListToolbar/index.tsx:68` formats timestamps with `toLocaleString()`, producing absolute timestamps like '10/30/2026, 9:20:25 AM' rather than relative ones like '2 minutes ago'. Copilot flagged this in the PR discussion.
_Precedent:_ a maintainer accepted or deferred the same point — [discussion](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145186).
_Fix:_ Either remove the relative timestamp claim, note that ListToolbar extension is required, or add relative timestamp support to scope.

**P1 — No linked issue** · Process · PR body
The description links no issue, so the acceptance criteria can't be verified.
_Fix:_ Add `Closes #<n>` (or `Part of #<n>`) to the description.

</details>

### 💡 &nbsp; Improvements

| #   | Severity | Category | Precedent | Issue                                                 | Location                                           |
| --- | -------- | -------- | --------- | ----------------------------------------------------- | -------------------------------------------------- |
| I1  | 🟢 Low   | Docs     | —         | Menu item labels use lowercase instead of Title Case. | `docs/specs/networks/networks-readonly-brd.md:130` |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Inconsistent menu item capitalization** · Docs · `docs/specs/networks/networks-readonly-brd.md:130`
The BRD at `docs/specs/networks/networks-readonly-brd.md:130` and spec at `docs/specs/networks/networks-readonly-spec.md:18` document 'View details' (lowercase) instead of 'View Details' (Title Case). This violates B.19 which mandates Title Case for button labels, and is inconsistent with the PR's own guardrails.md which correctly uses 'View Details' at `docs/guardrails/guardrails.md:9`. When implementers copy this string, the UI will be inconsistent with existing menu items like 'Edit Metadata' and 'Manage Access'.
_Fix:_ Change 'View details' to 'View Details' at BRD lines 130, 204 and spec lines 18, 123.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

This PR adds comprehensive documentation for a new **read-only Networks scope** in Aurora Dashboard, along with project-wide guardrails for list/detail view patterns. The change is documentation-only — no code or runtime behavior is affected. CI shows 18 passing checks with 4 skipped and no failures.

## Documentation additions

### Networks feature documentation (new `docs/specs/networks/` directory)

Two new specification documents define the requirements and engineering plan for displaying OpenStack Neutron networks in Aurora:

- **Business Requirements Document** (`networks-readonly-brd.md`, 364 lines) — stakeholder-facing definition of the Networks scope: business justification, target surface (Aurora built-in scope, Pattern A), user stories (project member viewing networks/subnets/ports), API information (Neutron v2.0), authentication/authorization (Keystone via BFF, project-scoped), release scope (MVP: list + detail with subnets; fast-follow: ports + router deep-link), and explicitly deferred rollout details

- **Engineering specification** (`networks-readonly-spec.md`, 261 lines) — implementation-ready epic with 7 sub-issues (API gate, routing scaffold, list page, detail metadata, subnets tab, ports tab, router deep-link), confirmed UX decisions (3-zone DataGrid toolbar with `ListToolbar`, clickable rows + overflow menu, directory-route detail page), confirmed engineering decisions (no refresh mechanism in phase 1, no pagination, client-side search/sort/filter, tRPC namespace `network.networks.*`), and a dependency graph showing MVP is sub-issues 1–5

### Project guardrails (new `docs/guardrails/guardrails.md`)

A new home for project-specific UI patterns not yet covered by skills:

- **List Views**: render IDs beneath names in subdued text; make rows clickable when they have a detail view; add an overflow menu column containing actions (including "View Details" when applicable)
- **Detail Views**: use a TabBar to switch between multiple sub-tables

```markdown
## List Views

- Render the individual items' IDs in the name column underneath the name in a subdued text style if possible
- If the items have a detail view _DO_ make each whole row clickable to navigate to the detail view
- If any action can be performed on an item, _DO_ add a column with an overflow menu containing the actions as the last column. Note: If the item has a detail view, ensure the overflow menu contains a "View Details" item.

## Detail Views

- If you have multiple sub-tables showing lists of items, _DO_ use a TabBar to switch between the sub-tables
```

### Agent wiring (`AGENTS.md`)

Adds a "Guardrails" section referencing the new `docs/guardrails/guardrails.md` so agents pick it up as standing instruction `AGENTS.md:13`.

```markdown
## Guardrails

For project-specific guardrails not yet covered by a skill or other reference, see docs/guardrails/guardrails.md
```

## Relationship to existing codebase

The BRD explicitly positions Networks within Aurora's existing `network` scope alongside Routers, Floating IPs, and Security Groups `docs/specs/networks/networks-readonly-brd.md:73`.

The spec references existing Aurora patterns as implementation models:
- `floatingips` resource as the closest reference (directory-route detail page)
- `routers` detail view's TabBar pattern
- Existing `ListToolbar` component and its subcomponents (`SortInput`, `FiltersInput`, `SelectedFilters`)
- Permission checking via existing `network.canUser` pattern
- Catalog-gating via existing `getServiceIndex("network")` + `beforeLoad` guard

## Scope framing

Phase 1 is strictly read-only — no create/edit/delete; mutation is a separate later phase. The spec explicitly documents engineering decisions made during a "grilling session" (2026-10-27): no refresh mechanism (no `refetchInterval`, no SSE subscription, no manual refresh button), no pagination (all rows render, client-side filtering), and tRPC procedures scoped under `network.networks.*`.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

## How the change is structured

### Networks BRD (`docs/specs/networks/networks-readonly-brd.md`)

Follows a standard BRD template with document control, summary, business justification, target surface, out-of-scope items, user stories with acceptance criteria, API information (service catalog registration, authentication mode, error handling), and non-functional requirements (authorization, dependencies, rollout strategy).

Key sections:

**User stories** (§5.1) define four read-only interactions: list project networks (Story 1, with search/sort/filter), view network details (Story 2, metadata + relationships), view subnets of a network (Story 3, nested sub-table), and view ports/attached devices (Story 4, with device-owner type mapping and router deep-link exception).

```markdown
- [ ] Shows the network's **ports / attached devices** as a nested sub-table (see Story 4)
- [ ] Shows **attached routers** as a read-only linked list when present (derived from the network's ports where `device_owner` is `network:router_interface` — see Story 4 for the deep-link behavior); when no such ports exist, the attached-routers list renders an explicit empty state ("None")
- [ ] Floating IPs and Security Groups are **not** shown here

### Story 3: View subnets of a network

**As a** Project Member (Viewer)
**I want to** see the subnets belonging to a network
**So that** I can understand the network's addressing

**Acceptance Criteria:**

- [ ] Subnets are shown as a **nested sub-table inside the network detail** (there is no standalone project-wide subnet list in phase 1)
- [ ] For each subnet, show: Name, ID (copy affordance), CIDR, IP version (4/6), Gateway IP, DHCP enabled (yes/no), Allocation pools (start–end ranges), DNS nameservers, and **Host routes** (destination CIDR → nexthop pairs)
- [ ] Host routes render with an explicit empty state ("None") when absent — they are usually empty but materially change routing when present, which is exactly the non-obvious config a read-only viewer opens the detail to inspect
- [ ] An empty subnet set shows an inline empty state ("No subnets")

### Story 4: View ports / attached devices of a network

**As a** Project Member (Viewer)
**I want to** see the ports on a network and what they are attached to
**So that** I can see which devices are connected and how

**Acceptance Criteria:**
```

**Release scope** (§6) explicitly sequences MVP (network list + detail + subnets) separately from fast-follow (ports + router deep-link), with rationale: ports are headline functionality but most complex and not required to answer "what networks/subnets do I have?"

```markdown
> ⚠️ **Still needed**: exact links to the Neutron API docs and spec (nice-to-have — the API itself is well-known and stable).

### Authentication Mode

Keystone token via Aurora's **BFF (Backend-for-Frontend) pattern**. The client calls server-side
tRPC procedures using `projectScopedProcedure`; the server injects the `X-Auth-Token` header via
`signal-openstack`. **The browser never handles the raw Keystone token.** All reads are
project-scoped to the active project.

### Rate Limits / Throttling

Backing calls are the standard Neutron list/show endpoints. Each view issues a single list call
(networks, or subnets/ports for a given network) with no per-item fan-out, so request volume is
low. No special throttling handling is anticipated for phase 1.
```

**API information** (§7) confirms Neutron v2.0, BFF authentication (Keystone token via `projectScopedProcedure`, server injects `X-Auth-Token`, browser never handles token), and error states (no networks vs 403 vs 5xx, partial failure scoped to sub-tables).

```markdown
Via the Keystone catalog. The navigation entry appears only when the `network` service is in the
catalog, using Aurora's `getServiceIndex("network")` check plus the `beforeLoad` catalog guard in
`network.tsx` — the same guard the existing Floating IPs / Routers / Security Groups views use.

---
```

**Authorization** (§8) specifies behavioral capability-validation (Aurora's `canI`-style checks against Neutron's oslo.policy) rather than hard-coded role names, consistent with the pattern used elsewhere in Aurora.

```markdown
**Cross-team approvals needed**

> **Deferred (non-blocking):** whether Aurora core-team sign-off is required to add a new built-in scope has not been confirmed (Q-N2). This is a process question, not an engineering gap, and does not block the BRD from review.

---
```

### Networks engineering spec (`docs/specs/networks/networks-readonly-spec.md`)

Structured as an epic with confirmed UX/component decisions, confirmed engineering decisions, an epic index table, a dependency graph, and 7 detailed sub-issue specifications.

**Confirmed UX decisions** ground the implementation in Juno UX docs and Aurora's existing patterns:

**Confirmed UX decisions** ground the implementation in Juno UX docs and Aurora's existing patterns:

1. **3-zone DataGrid toolbar** with `ListToolbar`, clickable rows, overflow menu
2. **Subdued ID text** beneath names in list views
3. **Detail page as directory route** at `/projects/$projectId/network/networks/$networkId` (like `floatingips`), deep-linkable and bookmarkable

**Confirmed engineering decisions** (E1–E6) resolve ambiguities from the BRD:
- E1: no refresh mechanism in phase 1 (resolves BRD Q-F7)
- E2: "owning project" = UUID + copy affordance (no Keystone lookup)
- E3: status sort order is attention-first (`ERROR` → `BUILD` → `DOWN` → `ACTIVE`)
- E4: tRPC namespace `network.networks.*` with procedures `list`, `getById`, `listSubnets`, `listPorts`
- E5: no pagination (diverges from original BRD Story-1 AC, marked superseded)
- E6: Shared/External filters are boolean (true/false/unselected)

```markdown
- **E1 — No refresh mechanism in phase 1.** No `refetchInterval` auto-poll, no SSE subscription, and no manual refresh button. Rationale: `refetchInterval` is unused anywhere in Aurora today; the only real-time pattern (tRPC-over-SSE subscriptions) is purpose-built for in-process upload/download progress and does not watch OpenStack resource state; and a manual refresh button is likewise not an established pattern in the sibling list/detail views. Data loads on route navigation / component mount (and via TanStack Query's default refetch-on-window-focus). The Zone-3 **last-updated timestamp is retained**, fed from the query's `dataUpdatedAt` and rendered relative. Refresh is deferred to a later phase. _(Resolves BRD Q-F7.)_
- **E2 — "Owning project" = `project_id` (UUID) + copy affordance.** For a shared network, the Shared column shows the owning project's `project_id` with a copy-to-clipboard affordance — **no Keystone name lookup** (consistent with the no-name-resolution / no-N+1 principle applied to `device_id`).
- **E3 — Status sort order:** `ERROR` → `BUILD` → `DOWN` → `ACTIVE` (attention-first); the sort-direction toggle flips it. Sorting by status is treated as "surface what needs attention first".
- **E4 — tRPC namespace `network.networks.*`**, procedures `list`, `getById`, `listSubnets`, `listPorts`. Subnets and ports are **procedures on the networks router** (no separate `subnets` router), because phase 1 has no standalone project-wide subnet or port list — they are only ever viewed nested inside a network. Procedure naming follows the sibling convention (`getById`, not `get`).
- **E5 — No pagination in phase 1.** The list renders all rows; search / sort / filter are entirely client-side over the single `network.networks.list` response. None of the sibling list views (`floatingips`, `routers`, `securitygroups`) implement pagination, and project-scoped network counts are typically small. Revisit only if real projects show large network counts. _(Divergence from the original BRD Story-1 pagination AC, which has been marked superseded in the BRD.)_
- **E6 — Shared / External filters are boolean.** `shared` and `router:external` are booleans on the Neutron network object, so each filter `Select` offers **true / false** only; leaving a filter unselected means "any" (no pill, no filtering).
```

**Epic index and dependency graph** show the critical path to MVP (1 → 2 → 3 → 4 → 5) and fast-follow extensions (4 → 6 → 7), with sub-issues 5 (subnets) and 6 (ports) independent of each other.

````markdown
## Epic index

| Sub-issue | Title                                       |   In MVP?   | Blocked by |
| --------- | ------------------------------------------- | :---------: | ---------- |
| 1         | API & environment gate                      |   prereq    | —          |
| 2         | Scope scaffold, routing & auth wiring       |   prereq    | 1          |
| 3         | List project networks                       |   ✅ MVP    | 1, 2       |
| 4         | Network detail — metadata (full route page) |   ✅ MVP    | 3          |
| 5         | Subnets sub-table                           |   ✅ MVP    | 4          |
| 6         | Ports sub-table + attached-routers list     | fast-follow | 4          |
| 7         | Router deep-link from ports                 | fast-follow | 6          |

## Dependency graph

```
1  API & environment gate
└─ 2  Scope scaffold, routing & auth wiring
   └─ 3  List networks ───────────────────────────── (MVP releasable: 3 + 4 + 5)
      └─ 4  Network detail — metadata
         ├─ 5  Subnets sub-table          ── independent of 6
         └─ 6  Ports sub-table + attached-routers list
            └─ 7  Router deep-link
```

Critical path to MVP: **1 → 2 → 3 → 4 → 5**. Fast-follow extends **4 → 6 → 7**. Sub-issues 5 and 6 are independent of each other. The single ports fetch introduced in sub-issue 6 feeds **both** the ports sub-table and the attached-routers list.
````

Each sub-issue follows a consistent structure: what to build, blocked-by, status, user story (where applicable), acceptance criteria (referencing BRD sections), Aurora/Juno implementation notes (specific component names, patterns, prior art), and BRD reference.

**Sub-issue 3 (List networks)** shows the acceptance criteria format, referencing BRD Story 1 and adding implementation details:

```markdown
- [ ] Lists all networks in the current project. Each row shows:
  - [ ] **Name** — with the network's **ID shown beneath the name** (no separate ID column); the ID has a **copy-to-clipboard affordance**
  - [ ] **Status** — a visible status indicator; possible values: `ACTIVE`, `DOWN`, `BUILD`, `ERROR`
  - [ ] **Admin State** — up / down
  - [ ] **Shared** — when the network is shared, this column shows the **owning project's `project_id` (UUID) with a copy affordance** (E2; not merely "yes", and not a resolved project name)
  - [ ] **External** — yes / no
  - [ ] **Subnet count** — derived from the network object's embedded `subnets` array (`subnets.length`); no extra API call
  - [ ] a **row overflow menu** (last column) with a single **"View details"** item (phase-1 extension point)
- [ ] The whole row is clickable and navigates to the network detail route; nested interactive elements (ID copy, overflow menu) call `event.stopPropagation()`
- [ ] **Searchable** by name and ID (search box placeholder makes the matched fields clear)
- [ ] **Sortable** by name, status, and subnet count. Status sorts in the order `ERROR` → `BUILD` → `DOWN` → `ACTIVE`, flipped by the direction toggle (E3)
- [ ] **Filterable** by status and by the Shared and External flags (each a boolean true/false `Select`, unselected = any — E6), with active-filter pills + "clear all"
- [ ] MTU and provider/segmentation details are **not** shown in the list — they live in the detail view
- [ ] **No pagination** (E5): all rows render; search/sort/filter are client-side over the single `network.networks.list` response
- [ ] **States:** DataGrid-scoped loading indicator; a friendly empty state ("No networks in this project") distinct from a filtered-empty state ("No networks match your filters"); a DataGrid-scoped error state with a **retry** affordance on backend/5xx/timeout (never a blank page/stack trace); the standard unauthorized state on 403
```

**Sub-issue 7 (Router deep-link)** shows the cross-scope navigation pattern with graceful degradation:

The router deep-link sub-issue shows the cross-scope navigation pattern:

- When `device_owner = network:router_interface`, render a deep-link to the router's detail view
- The link requires only route construction — no extra API call and no name resolution
- If the Routers scope is unavailable, degrade gracefully to showing just the ID

### Guardrails document (`docs/guardrails/guardrails.md`)

A lightweight, pattern-oriented file collecting conventions not yet formalized in skills. Two sections (List Views, Detail Views) with brief, directive rules. The Detail Views section references `TabBar` `docs/guardrails/guardrails.md:13`, which aligns with the spec's confirmed UX decision 3.

### Agent wiring (`AGENTS.md`)

Adds four lines after the existing `<!-- intent-skills:end -->` marker: a "## Guardrails" heading and a reference to the new guardrails file.

```markdown
## Guardrails

For project-specific guardrails not yet covered by a skill or other reference, see docs/guardrails/guardrails.md
```

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

## Impact and blast radius

This is a documentation-only change with no code consumers. The added files establish a contract for future implementation but do not modify any exported symbols, tRPC procedures, React components, or public types.

### New documentation files (no code consumers yet)

The two Networks spec files and the guardrails document are referenced only within the PR itself:

- `docs/specs/networks/networks-readonly-brd.md` — referenced by the spec's "Source BRD" frontmatter link
- `docs/specs/networks/networks-readonly-spec.md` — no code references; this is an implementation blueprint
- `docs/guardrails/guardrails.md` — referenced by `AGENTS.md:15` as a standing instruction for agents

### Modified file (`AGENTS.md`)

`AGENTS.md` is a project-instructions file read by Claude Code. The addition of the Guardrails section extends the standing instructions agents receive when working in this repository. No code imports or runtime logic depends on this file.

### Component/pattern references within the specs

The spec references several existing Aurora components and patterns as implementation targets:

- **`ListToolbar`** (`packages/aurora/src/client/components/ListToolbar/index.tsx`) — the spec states it will be used for the 3-zone toolbar `docs/specs/networks/networks-readonly-spec.md:14`. Existing consumers: `floatingips`, `images`, `flavors`. A Copilot review comment notes the current `ListToolbar` does not provide the prescribed 3-zone layout or relative timestamp unchanged, suggesting extension or composition will be needed.

- **`TabBar`** — the guardrails and spec reference this component for detail-view sub-tables. A Copilot review comment flagged that Aurora has no component named `TabBar`; it uses Juno's `TabNavigation`/`TabNavigationItem`. A human reviewer (franzheidl) replied that `TabNavigation` is deprecated in ui-components and `TabBar` is the correct component to use, resolving the concern.

- **tRPC namespace `network.networks.*`** — the spec defines four procedures (`list`, `getById`, `listSubnets`, `listPorts`) `docs/specs/networks/networks-readonly-spec.md:100`. These do not exist yet. The spec references the existing `Network/routers/` structure as the pattern to follow.

- **Permission pattern `network.canUser`** — the spec references the existing permission router for the `network` scope. A Copilot review comment (discussion [r4422145137](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145137)) notes an error in the spec: the documented `ctx.openstackSession` should be `ctx.openstack` (the actual context property name in `server/trpc.ts`).

### Potential inconsistencies flagged by Copilot reviews

Five Copilot review comments flag documentation inaccuracies that could lead implementers astray:

1. **Refresh behavior** ([r4422145096](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145096)): the spec states data refetches on window focus, but Aurora sets `refetchOnWindowFocus: false` globally in `packages/aurora/src/client/App.tsx:74–77`. The spec's E1 decision correctly excludes all refresh mechanisms, but a stale statement at line 25 contradicts it.

2. **Context property name** ([r4422145137](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145137)): the spec documents `ctx.openstackSession?.getToken()?.authToken` at line 99, but the actual context exposes `ctx.openstack`, not `ctx.openstackSession`.

3. **`ListToolbar` capabilities** ([r4422145186](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145186)): the spec states `ListToolbar` provides the 3-zone layout and relative timestamp out of the box, but the existing component does not — it puts filters/sort/search in one row and formats timestamps with `toLocaleString()`.

4. **Router interface device owners** ([r4422145250](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145250)): the spec restricts router discovery to `network:router_interface`, but this omits DVR and HA router interfaces. Existing code in `server/Network/helpers/routerHelpers.ts:223–230` uses a set of three owners: `network:router_interface`, `network:router_interface_distributed`, and `network:ha_router_replicated_interface`. The spec should reference this set at lines 212, 234, and in the BRD at lines 145, 173.

5. **TabBar vs TabNavigation** ([r4422145017](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145017)): resolved by human reviewer — `TabBar` is correct, `TabNavigation` is deprecated.

### No stale callers

Because this is a documentation-only change, there are no stale callers — the code described does not yet exist.

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. Clone the repository and check out the head commit (fd75255a)
2. Verify the new files exist: `docs/specs/networks/networks-readonly-brd.md`, `docs/specs/networks/networks-readonly-spec.md`, `docs/guardrails/guardrails.md`
3. Verify `AGENTS.md` contains the new "Guardrails" section at lines 13–15
4. Open `docs/specs/networks/networks-readonly-brd.md` and confirm it follows the BRD template (document control, summary, justification, user stories, API info, non-functional requirements)
5. Open `docs/specs/networks/networks-readonly-spec.md` and confirm it has 7 sub-issues with acceptance criteria, confirmed UX decisions, and confirmed engineering decisions
6. Verify the spec's BRD reference link resolves correctly (line 3: `Source BRD: [networks-readonly-brd.md](networks-readonly-brd.md)`)
7. Open `docs/guardrails/guardrails.md` and confirm it has two sections (List Views, Detail Views) with directive rules
8. Verify the guardrails document is referenced from `AGENTS.md` at line 15

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- Confirm the BRD's "Out-of-Scope" section (§4, line 78) explicitly excludes mutation — this ensures implementers know phase 1 is read-only
- Verify the spec's engineering decision E1 (line 24) states no refresh mechanism, but check line 25 for any contradictory statements about `refetchOnWindowFocus` (Copilot flagged this at discussion [r4422145096](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145096))
- Check the spec's implementation note at line 99 for the context property name — should be `ctx.openstack`, not `ctx.openstackSession` (Copilot flagged this at discussion [r4422145137](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145137))
- Verify the spec references the correct set of router interface device owners (should include DVR and HA variants, not just `network:router_interface`) at lines 212, 234, and in the BRD at lines 145, 173 (Copilot flagged this at discussion [r4422145250](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1406#discussion_r4422145250))
- Confirm the guardrails document's TabBar reference (line 13) aligns with the human reviewer's correction that `TabBar` is correct and `TabNavigation` is deprecated
- Check that the spec's MVP/fast-follow sequencing (§6 in BRD, lines 236–250; epic index in spec, lines 32–56) is consistent across both documents
- Verify the BRD's deferred items (rollout strategy Q-N1, submitter/target quarter Q-N4) are clearly marked as non-blocking at lines 15, 339, 350
- Confirm the spec's "Open items roll-up" section (lines 249–261) shows which items were resolved during the grilling session and which remain residual

</details>

---

## Checked and dismissed

<details>
<summary><strong>Candidates scored below 50 (1)</strong></summary>

| Score | Candidate                                                                                                                  | Location                          | Why                                                                                                                                                             |
| ----- | -------------------------------------------------------------------------------------------------------------------------- | --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 25    | The guardrails mandate showing IDs underneath names in list views, but most existing list views don't follow this pattern. | `docs/guardrails/guardrails.md:7` | The guardrails mandate showing IDs underneath names in list views (line 7), but this is a forward-looking pattern, not documenting existing universal practice. |

</details>

---

_Analyzed 2026-10-30 · commit `fd75255a` · read-only · skill: review-and-comment-pr_
