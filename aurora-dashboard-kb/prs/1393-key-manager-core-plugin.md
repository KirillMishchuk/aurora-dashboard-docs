---
type: pr-report
date: 2026-10-25
status: open
pr: [1393]
issue: [1133]
author: hodanoori
branch: feat/key-manager-plugin
---

# PR #1393: feat(aurora): add Key Manager (Barbican) in-core plugin

**Author:** hodanoori · **Status:** open · **Base:** `main` ← `feat/key-manager-plugin`
**Size:** 48 files, +4439 / −3 · **Created:** 2026-10-23 · [View on GitHub](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393)

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

_Reviewed at head [`fd248f08`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393/commits/fd248f083f89fbe9caca6ad536106ffd08860159) · base `main` at `c65b36d0` · 2026-10-25 14:20 UTC_

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

- **Must fix before merge**: CR1, CR2, CR3, CR4, CR5, CR6, CR7, CR8, CR9, CR10
- **Process:** P1

The PR adds a full Key Manager (Barbican) area — BFF router with Zod schemas, a permission router, nav entry and Secrets/Containers/Orders tabs with list, detail, create and delete — and CI is green. What matters most is the Barbican contract: Reveal Payload sends no `Accept` matching the secret's content type, so typical secrets fail with 406, and removing a secret from a container and sorting orders use endpoints/params the reference does not document. On the client, the Reveal Payload action is not permission-gated, the nav entry ignores `enabledServices`/`deniedServices`, create forms mutate without validation, search navigates on every keystroke and CRUD success shows no toast. Against epic #1133 most criteria are only partly met (no update/manage-secrets UI, Orders columns, error text, tests), and a changeset is missing.

### 🔧 &nbsp; Required Changes

| #    | Severity    | Category    | Precedent | Issue                                                                                                     | Location                                                                                                                             |
| ---- | ----------- | ----------- | --------- | --------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| CR1  | 🟠 Major    | Bug         | —         | `getSecretPayload` sends the default `Accept: application/json`, so Barbican answers 406 for most secrets | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`                                                               |
| CR2  | 🟡 Moderate | UI/UX       | —         | Create modals mutate without validation; Bit Length is sent as `NaN` when empty                           | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:52`        |
| CR3  | 🟡 Moderate | UI/UX       | —         | Create and delete of secrets, containers and orders show no confirming toast                              | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:35`      |
| CR4  | 🟡 Moderate | Security    | —         | Reveal Payload and the detail views ignore `key-manager:secrets:payload` / `get` permissions              | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89` |
| CR5  | 🟡 Moderate | Performance | —         | Search inputs navigate on every keystroke, with no local state or debounce                                | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:109`      |
| CR6  | 🟡 Moderate | Bug         | —         | `deleteContainerSecret` calls an undocumented `DELETE /v1/containers/{id}/secrets/{name}`                 | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:252`                                                              |
| CR7  | 🟡 Moderate | Bug         | —         | Container `secret_refs[].name` is required `z.string()`, but Barbican allows unnamed refs                 | `packages/aurora/src/server/KeyManager/types/keyManager.ts:25`                                                                       |
| CR8  | 🟡 Moderate | Bug         | —         | Deleting the last row on the last page leaves an empty table with no pagination                           | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:126`      |
| CR9  | 🟡 Moderate | Bug         | —         | Key Manager nav entry and route ignore `enabledServices` / `deniedServices`                               | `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`                                               |
| CR10 | 🟡 Moderate | Bug         | —         | `listOrders` sends undocumented `sort_key`/`sort_dir`; the Orders sort control does nothing               | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:271`                                                              |
| P1   | —           | Process     | —         | Published package code changed without a `.changeset/*.md`                                                | PR files                                                                                                                             |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — Reveal Payload does not set `Accept` to the secret's content type** · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`
`getSecretPayload` fetches the payload with no headers:

```ts
const res = await km.get(`v1/secrets/${encodeURIComponent(input.secretId)}/payload`).catch((e: unknown) => {
```

The session's default headers send `Accept: application/json`, while the Barbican reference for `GET /v1/secrets/{uuid}/payload` says the accept header must be one of the values in the secret's `content_types`. For `text/plain` or `application/octet-stream` secrets — the common case — Barbican returns 406 Not Acceptable, and `mapKmError` has no 406 entry, so the user sees a generic internal error and Reveal Payload is broken. No test covers a non-JSON content type.
_Fix:_ Read the secret's metadata (or take its `content_types.default` from the client) and pass it as the `Accept` header on the payload request; map 406/415 in `mapKmError`.

**CR2 — Create Order/Secret/Container forms have no validation or inline errors** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:52`
The Create Order modal sends `parseInt(bitLength, 10)` (NaN for an empty field; zero and negative values are accepted), the algorithm may be empty, and the confirm button is disabled only while the mutation is pending:

```tsx
meta: { algorithm, bit_length: parseInt(bitLength, 10) },
```

The secret and container create modals have no validator either. This breaks B.5/B.11 (confirm disabled while required fields are empty or invalid) — bad input reaches Barbican and only comes back as a message at the top of the form. Copilot raised the bit-length case on `OrderModals.tsx:52`; no reply.
_Fix:_ Validate required fields and a positive integer bit length (react-form + Zod, as elsewhere), show inline errors and keep Create disabled until the form is valid.

**CR3 — CRUD success is silent** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:35`
On success the modals only invalidate the query and close; there is no `toast` and no `*ToastNotifications` helper anywhere under `key-manager/`. B.16/B.10 require a transient confirming toast for create/update/delete, extracted into a `<Resource>ToastNotifications.tsx`.
_Fix:_ Add `SecretToastNotifications`/`ContainerToastNotifications`/`OrderToastNotifications` helpers and show a toast from each mutation's `onSuccess`.

**CR4 — Reveal Payload is not permission-gated (not fail-closed)** · Security · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89`
The Reveal Payload button is rendered unconditionally:

```tsx
<Button variant="subdued" onClick={handleRevealPayload} disabled={payloadFetching}>
```

`key-manager:secrets:payload` is defined in the permission router and the hook's types but no client code reads it; none of the `*DetailsView` files call the permissions hook. Users without payload rights see a working control that triggers a plaintext fetch — only Barbican's own ACLs stop it. This violates the Quick Reject rule on controls shown before permissions resolve and leaves the epic's "all action-triggering elements gated" criterion partly met. Copilot flagged it as CRITICAL (r4360388886); no reply.
_Fix:_ Check `key-manager:secrets:payload` (and `get` for the detail routes) via the permissions hook, defaulting to false while loading, and hide or disable the button until allowed.

**CR5 — Secrets/Containers search fires a navigation and a request per character** · Performance · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:109`
`SearchInput` calls `onSearchChange` on every input event:

```tsx
onInput={(e) => onSearchChange((e.target as HTMLInputElement).value)}
```

`handleSearch` in `secrets/index.tsx` calls `navigate()` without debounce or `replace`, so each keystroke changes the URL, resets the page, adds a history entry and fires a new `listSecrets` request. Same in `ContainersList.tsx:74`. B.9 asks for a local mirror state with debounce, as the flavors list does (500 ms).
_Fix:_ Keep the input value in local state, debounce the navigation (and use `replace: true`), and sync back from the URL in a `useEffect`.

**CR6 — Removing a secret from a container uses the wrong Barbican endpoint** · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:252`
The procedure deletes by path segment and takes only `containerId` and `secretName`:

```ts
.del(`v1/containers/${encodeURIComponent(input.containerId)}/secrets/${encodeURIComponent(input.secretName)}`)
```

The Barbican containers reference documents removal only as `DELETE /v1/containers/{container_uuid}/secrets` with a JSON body `{ "name", "secret_ref" }`, where `secret_ref` is required (400 "Missing secret_ref"). The path form is not in the reference, so the call will fail once a UI uses it; the router test asserts the same wrong URL. Copilot raised it (r4360389656); no reply.
_Fix:_ Send `DELETE v1/containers/{id}/secrets` with a body `{ name, secret_ref }`, add `secret_ref` to the input schema, and update the test.

**CR7 — An unnamed secret reference makes the whole container response fail validation** · Bug · `packages/aurora/src/server/KeyManager/types/keyManager.ts:25`
```ts
secret_refs: z.array(z.object({ name: z.string(), secret_ref: z.string() })),
```

`name` is optional for container secret references in the reference, and sibling `name` fields in this file are `.nullable()`. A container with an unnamed ref returns `name: null`, `parseOrThrow` rejects it, and the whole container list fails to load. Copilot raised it (r4360389713); no reply.
_Fix:_ Make it `name: z.string().nullable().optional()` and render a fallback in the UI.

**CR8 — List `page` is not clamped after a delete** · Bug · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:126`
`offset` is `(page - 1) * PAGE_SIZE` and `totalPages` comes from `data.total`, but nothing clamps `page` when the total shrinks. Pagination is hidden when there is one page:

```tsx
{totalPages > 1 && (
```

So after deleting the only row of the last page the user sees an empty table with no way back. Same in the Containers and Orders lists; Copilot raised all three (r4360389532, r4360389254, r4360389387), no replies.
_Fix:_ When `page > totalPages` after data loads, navigate to `max(totalPages, 1)` with `replace: true`.

**CR9 — Key Manager can't be hidden through service-visibility config** · Bug · `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`
The new nav item is gated only on the catalog:

[[code:packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts | ...(serviceIndex["key-manager"]?.["barbican"] | 1]]

Every other built-in item uses `&& isEnabled(...)`, whose comment says deny always wins. A host cannot hide Key Manager via `deniedServices` or leave it out of an `enabledServices` allowlist, and the `key-manager.tsx` `beforeLoad` also checks only the catalog, so a denied service stays reachable by URL. The project overview (`projects/$projectId/index.tsx`) gets no Key Manager card either.
_Fix:_ Add `&& isEnabled("key-manager")` to the nav item, apply the same check in the route `beforeLoad`, add the card on the project overview and document the service key in the README.

**CR10 — Orders sort uses parameters Barbican doesn't support** · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:271`
```ts
if (input.sort) {
  const [sortKey, sortDir] = input.sort.split(":")
  if (sortKey) params.set("sort_key", sortKey)
  if (sortDir) params.set("sort_dir", sortDir)
}
```

The Barbican reference for `GET /v1/orders` documents only `offset` and `limit`; `sort_key`/`sort_dir` appear nowhere in the secrets, containers or orders references. The Sort by / direction controls in `OrdersList.tsx` are visible but have no documented effect.
_Fix:_ Remove the sort control from the Orders tab (or sort client-side within the page) and drop the sort params from `listOrders`.

**P1 — No changeset** · Process · PR files
The PR changes published code under `packages/aurora/src` but adds no changeset, so the change gets no version bump or changelog entry.
_Fix:_ Run `pnpm changeset`, pick the bump type and commit the generated `.changeset/*.md`.

</details>

### 💡 &nbsp; Improvements

| #   | Severity   | Category      | Precedent     | Issue                                                                                             | Location                                                                                                                               |
| --- | ---------- | ------------- | ------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| I1  | 🟢 Low     | Code Quality  | —             | Permission props are named `canDelete` instead of `can<Verb><Noun>`                               | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:15`      |
| I2  | 🟢 Low     | Accessibility | —             | Row `PopupMenu` has no `PopupMenuToggle` with a labelled `moreVert` button                        | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:35`      |
| I3  | 🟢 Low     | UI/UX         | —             | Row menu items `Show Details` / `Delete` lack the entity name and a separator before Delete       | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:38`      |
| I4  | 🟢 Low     | UI/UX         | —             | Delete modals put the name/ID in the title and use a bare `Delete` confirm label                  | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:129`       |
| I5  | 🟢 Low     | UI/UX         | —             | Modals disable Cancel but not the close-X while a mutation is pending                             | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:136`       |
| I6  | 🟢 Low     | Code Quality  | —             | Create modals use `useState` without react-form, `autoFocus` or disabled inputs in flight         | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:30`  |
| I7  | 🟢 Low     | Code Quality  | —             | Sort uses raw `Select` + `SortButton` instead of `SortInput`; toolbar uses `distribution="end"`   | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:93`         |
| I8  | 🟢 Low     | UI/UX         | —             | 403 on list pages is an inline warning `Message` with hard-coded English                          | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:72`         |
| I9  | 🟢 Low     | Code Quality  | —             | Detail routes fetch in the component (twice) instead of in the route `loader`                     | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/$containerId.tsx:19`                 |
| I10 | 🟢 Low     | UI/UX         | existing code | Ad-hoc spacing/styling classes (`my-6`, `mt-4`, `p-3`, `opacity-60`) outside the approved lists   | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:79`   |
| I11 | 🟢 Low     | Code Quality  | existing code | Raw `<div>`, `<p>`, `<pre>` used where Juno components exist                                      | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx:104`                                        |
| I12 | 🟢 Low     | Code Quality  | —             | Generic names: `usePermissions`, bundled `*Modals.tsx`, `utils.ts`, `constants.ts`                | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:21`               |
| I13 | 🟢 Low     | UI/UX         | —             | Empty state suggests creating even when a search returned no results                              | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:59` |
| I14 | 🟢 Low     | UI/UX         | —             | Error states show the raw `error.message` as title with no body or retry                          | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:33` |
| I15 | 🟢 Low     | Bug           | —             | `getSecretPayload` decodes binary payloads with `res.text()`                                      | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:103`                                                                |
| I16 | 🟢 Low     | Security      | —             | Secret plaintext can land in server logs via signal-openstack's debug body preview                | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`                                                                 |
| I17 | 🟢 Low     | UI/UX         | —             | Orders list lacks the Name column from the epic's UI spec                                         | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/constants.ts:1`              |
| I18 | 🟢 Low     | Code Quality  | —             | No update UI: `updateSecret`, `addContainerSecret`, `deleteContainerSecret` have no client caller | PR files                                                                                                                               |
| I19 | 🟢 Low     | UI/UX         | —             | `mapKmError` drops Barbican's error body; users see generic `Key Manager … failed`                | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:52`                                                                 |
| I20 | 🟢 Low     | Test coverage | —             | No tests for lists with permissions, modals, detail views, nav or layout guard; no E2E            | PR files                                                                                                                               |
| I21 | ⚪ Trivial | Code Quality  | —             | Import order and `../../` relative imports break B.13                                             | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:14`         |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — Permission prop naming** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:15`
`SecretTableRow.tsx:15` has `canDelete: boolean`; the same in `ContainerTableRow`, `OrderTableRow` and the three `*ListContainer.tsx`. B.8 requires `canDeleteSecret` etc. Copilot raised it on all six files; no replies.
_Fix:_ Rename to `canDeleteSecret`, `canDeleteContainer`, `canDeleteOrder`.

**I2 — Row action menus lack the standard toggle** · Accessibility · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:35`
`SecretTableRow.tsx:35` renders `<PopupMenu><PopupMenuOptions>` with no `PopupMenuToggle`, so the default toggle is used without an accessible label (also `ContainerTableRow.tsx:34`, `OrderTableRow.tsx:33`). B.14 requires `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>`. Copilot raised it (r4360388832).
_Fix:_ Use `PopupMenuToggle` with an icon `Button` carrying an `aria-label`, as the network views do.

**I3 — Row menu labels and Delete separator** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:38`
`SecretTableRow.tsx:37-38` lists `Show Details` then `Delete` with no `PopupMenuSectionSeparator`; same in the container and order rows. B.18 asks to name the entity in labels and separate Delete with a divider.
_Fix:_ Label as `Show Secret Details` / `Delete Secret` and add a `PopupMenuSectionSeparator` before Delete.

**I4 — Delete modal wording** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:129`
`SecretModals.tsx:129` uses ``title={t`Delete Secret "${secretName}"`}`` while the body doesn't name the entity and the confirm label is `Delete`; the order modal title shows a raw UUID (`OrderModals.tsx:125`, `ContainerModals.tsx:109`). B.5 puts the object name in the body and asks for verb + object labels.
_Fix:_ Title `Delete Secret`, name the entity in the body, confirm label `Delete Secret`.

**I5 — Missing `disableCloseButton` during async operations** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:136`
All six modals pass only `disableCancelButton={…isPending}` (e.g. `SecretModals.tsx:136`, `:60`), so the user can dismiss mid-request. B.5 / Quick Reject require disabling close-X and Cancel together, as `DeleteFlavorModal` does.
_Fix:_ Add `disableCloseButton={mutation.isPending}` to every create and delete modal.

**I6 — Create forms don't follow the form standard** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:30`
`ContainerModals.tsx:30` keeps `name` in `useState`; no create modal uses `@tanstack/react-form` + Zod, sets `autoFocus` on the primary input, or disables inputs while the mutation runs (B.11). Validation itself is CR2.
_Fix:_ Move the create forms to react-form with Zod validators, add `autoFocus` and `disabled={isPending}` on inputs.

**I7 — List toolbar doesn't use `SortInput`** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:93`
`SecretsList.tsx:93` and `OrdersList.tsx:76` build sorting from `Select` and `SortButton` in a `Stack distribution="end"`; B.1/B.2 require `SortInput` from `@/client/components/ListToolbar/SortInput` and `distribution="between"`. The Containers list has no sort control at all.
_Fix:_ Replace with `SortInput` and use `distribution="between"` for the toolbar.

**I8 — Permission-denied state is not page-level** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:72`
`SecretsList.tsx:72`, `ContainersList.tsx:50` and `OrdersList.tsx:55` render `<Message variant="warning">You do not have permission to view …</Message>` without `mb-4` and without Lingui. B.6 expects a page-level info `Message` for 403.
_Fix:_ Use a translated page-level info `Message` (with `mb-4`), matching the recommended 403 copy.

**I9 — Detail data not loaded in the route loader** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/$containerId.tsx:19`
`containers/$containerId.tsx:19` and `ContainerDetailsView` both call `getContainer.useQuery` (same for secrets and orders), and the routes have no `loader`. React Query dedupes the request, but A.3 asks for page-critical data in the loader.
_Fix:_ Fetch in the route `loader` and pass the data (or rely on one query) to the details view.

**I10 — Off-standard spacing and muted text** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:79`
E.g. `className="my-6"` on the detail stacks, `opacity-60` instead of `text-theme-light` at `SecretDetailsView.tsx:97`, and `mt-4` in `key-manager.tsx`. B.3/B.4 reject classes outside the approved lists.
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ActivateImagesModal.tsx:52`.
_Fix:_ Use the approved spacing (`mt-6` detail offset) and `text-theme-light` for muted text.

**I11 — Raw HTML instead of Juno layout primitives** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx:104`
`key-manager.tsx` wraps content in `<div className="mt-4">`, rows and pagination use `<div>`s, and `SecretDetailsView.tsx` wraps the button in a `<div>`. Quick Reject / B.1 prefer `Stack` and other Juno components.
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ActivateImagesModal.tsx:52`.
_Fix:_ Replace the wrappers with `Stack`/`Container` and the text elements with Juno equivalents.

**I12 — File and hook naming** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:21`
`usePermissions.ts:21` exports a generic `usePermissions(projectId, permissions)`; B.8 asks for `useKeyManagerPermissions(projectId)`. `SecretModals.tsx` etc. bundle several modals where B.12 wants `<Verb><Resource>Modal.tsx`. Copilot asked for `useKeyManagerPermissions` (r4360389782).
_Fix:_ Rename the hook to `useKeyManagerPermissions` and split modals into `CreateSecretModal.tsx`, `DeleteSecretModal.tsx`, …

**I13 — Empty state doesn't distinguish no data from no matches** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:59`
`SecretListContainer.tsx:59` always shows the create hint and doesn't receive `search`; same in `ContainerListContainer.tsx:58`. The hint is also shown to users without create permission. B.6 asks to distinguish the two reasons.
_Fix:_ Pass `search` in and show "No results — clear the search" when filtering.

**I14 — Error state lacks explanation and retry** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:33`
``<Status status="error" title={error?.message ?? t`Failed to Load Secrets`} />`` at `SecretListContainer.tsx:33`, and the same in the other list containers and detail views. B.6 asks for a course of action (retry) where feasible.
_Fix:_ Use a fixed translated title, the message as body and a retry action.

**I15 — Binary secrets are corrupted when revealed** · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:103`
```ts
const contentType = res.headers?.get?.("content-type") ?? "text/plain"
const text = await res.text()
return { payload: text, contentType }
```

An `application/octet-stream` secret (e.g. a symmetric key) is UTF-8-decoded and shown as garbage in the `<pre>`; there is no base64 path.
_Fix:_ For non-text content types read `arrayBuffer()` and return base64 with a flag so the UI can label it.

**I16 — Payload logged in non-production debug mode** · Security · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`
Debug is on by default outside production (`context.ts:114`), and signal-openstack logs a `bodyPreview` for text responses, so a `text/plain` secret fetched by `getSecretPayload` is written to the logs (truncated). Copilot flagged it as CRITICAL (r4360389080); no reply.
_Fix:_ Disable body preview for the payload request (or redact `/payload` responses in the client's debug logging).

**I17 — Orders columns don't match the spec** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/constants.ts:1`
Epic #1133 lists Orders columns Name / ID, Type, Status; `orders/-components/constants.ts:1` has `ID`, `Status`, `Type` and the row shows no name or reference.
_Fix:_ Show the order's name/secret reference alongside the ID, or note the deviation in the epic.

**I18 — Update / manage-container-secrets flows are missing** · Code Quality · PR files
The epic criterion is list, view, create, update and delete. The server procedures exist but no client code calls them — no Edit Secret modal, no way to attach secrets to a container (`secret_refs: []` on create), and Create Secret offers only name, type and payload.
_Fix:_ Add the update/manage flows, or state in the PR which part of #1133 this delivers and track the rest.

**I19 — Error messages aren't user-friendly** · UI/UX · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:52`
`keyManagerRouter.ts:52` builds the message as `Key Manager ${operation} failed` and the `!res.ok` paths pass only the status code, so a 409 (e.g. deleting a container in use) gets no specific text. The epic asks for user-friendly feedback for Barbican errors.
_Fix:_ Read Barbican's `description`/`title` from the error body and include it in the TRPCError message.

**I20 — Test coverage below the epic's criterion** · Test coverage · PR files
Tests cover the router, the schemas and the TableRow/ListContainer components only; the epic asks for unit, integration and E2E coverage.
_Fix:_ Add component tests for lists (permission states), modals and details, a nav/guard test and a basic E2E.

**I21 — Import order and path aliases** · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:14`
`SecretsList.tsx` imports `@/client/trpcClient` after Juno and `usePermissions` via `../../-components/usePermissions`; `SecretModals.tsx` imports `useState` after Juno. B.13 orders react, i18n, tRPC, Juno and forbids `../../` traversal.
_Fix:_ Reorder imports and switch to `@/` aliases.

</details>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

Adds an in-core Key Manager (OpenStack Barbican) plugin: 48 files, about 4.4k added lines, almost all new. CI on headRefOid: 17 pass, 0 fail, 0 pending, 4 skipped, 1 cancelled (`context.json` ci). The PR body checklist leaves the test and tests-pass boxes unticked, and its testing steps are only `pnpm i` and `pnpm run test`.

**Server.** A new `packages/aurora/src/server/KeyManager/` domain has a `keyManagerRouter` (secrets: list/get/getPayload/create/update/delete; containers: list/get/create/delete/addSecret/deleteSecret; orders: list/get/create/delete), Zod schemas, and a `canUser` permission router built with `createPermissionRouter`. It is mounted as `keyManager` in `server/routers.ts`. A policy file `apps/dashboard/src/policies/key-manager.json` is added.

**Client.** A `key-manager` layout route under `authorization/` has a tab bar (Secrets / Containers / Orders). Each tab is its own sub-route with an index list route and a `$id` detail route. Lists use the Juno DataGrid three-zone pattern (sort, search, pagination, with state in URL search params). There are Create and Delete modals for all three resources. `buildNavSections` gets a new Authorization section with one Key Manager entry, shown only if the catalog has `key-manager`/`barbican`.

**Generated / i18n.** `routeTree.gen.ts` and the `en`/`de` locale catalogs are regenerated.

**Gaps against the issue.** The server exposes `updateSecret`, `addContainerSecret` and `deleteContainerSecret`, but no client code calls them. There is no Edit Secret modal, no Manage Container Secrets flow, no bulk delete, and no tab hiding by permission. The Create Container modal always sends `secret_refs: []`.

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

**Layout route and service guard.** The `key-manager` layout checks the catalog in `beforeLoad` and redirects to the project page when Barbican is absent. Any error is also turned into a redirect. The tabs are URL-driven by `useMatch`, so each tab is a real route rather than component state.

```tsx
  const availableServices = await trpcClient?.auth.getAvailableServices.query()
  const serviceIndex = getServiceIndex(availableServices ?? [])
  if (!serviceIndex["key-manager"]?.["barbican"]) {
    throw redirect({ to: "/projects/$projectId", params: { projectId } })
  }
} catch (err) {
  if (isRedirect(err)) throw err
```

**Navigation.** The same catalog predicate gates the nav entry at `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`. The Authorization section is seeded in the section map with an empty `services` list when Barbican is absent, but `buildNavSections` ends with `.filter((s) => s.services.length > 0)`, so the empty section is dropped from the returned nav model.

**Server procedures.** Every procedure follows one shape. It resolves `ctx.openstack?.service("key-manager")`, calls Barbican, maps failures through `mapKmError` (status code to TRPCError code), and validates the response with `parseOrThrow` and a Zod schema. The payload route is the exception. It returns raw `text` plus the content type, with no schema.

```ts
listSecrets: projectScopedProcedure
  .input(projectScopedInputSchema.extend({ ...paginationInput.shape, ...secretsSearchInput.shape }))
  .query(async ({ input, ctx }) => {
    const km = ctx.openstack?.service("key-manager")
    validateOpenstackService(km, "key-manager")
    const params = new URLSearchParams()
    params.set("offset", String(input.offset))
    params.set("limit", String(input.limit))
    if (input.name) params.set("name", input.name)
    if (input.sort) params.set("sort", input.sort)
    const res = await km.get(`v1/secrets?${params}`).catch((e: unknown) => {
      throw mapKmError(e, "list secrets")
    })
    if (!res.ok) throw mapKmError({ statusCode: res.status }, "list secrets")
    return parseOrThrow(SecretsListSchema, await res.json(), "keyManager.listSecrets")
```

All procedures use `projectScopedProcedure`, so token rescoping comes from the existing builder. No procedure calls the policy engine itself. Permission checks exist only through the separate `canUser` query, which the UI calls.

**Permission router.** `permissionRouter.ts` maps 16 `key-manager:*` keys 1:1 to rules in the new policy JSON, using the shared factory.

```ts
export const buildKeyManagerPermissionRouter = (policyDir: string) =>
  createPermissionRouter({
    policyDir,
    engines: {
      keyManager: { fileName: "key-manager.json" },
    },
    mappings: KEY_MANAGER_MAPPINGS,
  })
```

**Client permission gating.** A local `usePermissions` hook calls `keyManager.canUser` once per list with `staleTime: Infinity`. Lists gate their query with `enabled: permissions[...:list]`, show a warning Message when list is denied (`packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:71`), and hide Create/Delete when those are denied.

**Payload reveal.** `SecretDetailsView.tsx:34` fetches the payload lazily (`enabled: false`) on button click (`:90`). The Reveal button is not gated by `canUser`, although the issue asks for `key-manager:secrets:get`.

**List columns.** Column order is Name/ID, Status, Type, (Content Types), actions. This follows the DataGridSpec note in the PR body (status right after the primary column) but differs from the issue's column order. Orders have no name column, only the ID.

```ts
export const SECRETS_COLUMNS = ["Name / ID", "Status", "Type", "Content Types", ""] as const
```

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

**New public tRPC surface.** `AuroraRouter` gains a `keyManager` namespace (`server/routers.ts` mounts `buildKeyManagerRouters(policyDir)`). Consumers who build on `AuroraRouter` types get the new keys. No existing procedure or export is changed. The only edits to existing files are `routers.ts`, `buildNavSections.ts`, the generated route tree and locale catalogs.

**Code consumers outside the PR.** None: the new symbols are used only by files in this PR. `usePermissions` and `uuidFromRef` are local to the key-manager route folder. `uuidFromRef` is also duplicated in `keyManagerRouter.ts`.

**Policy file.** `apps/dashboard/src/policies/key-manager.json` is picked up through `policyDir`, like the other policy files. Any host app that supplies its own `policyDir` must also ship `key-manager.json`. Otherwise the engine load behind `keyManager.canUser` fails, so every list shows the permission-denied warning.

**Nav.** The Authorization section is seeded in the section map, but the existing final `.filter((s) => s.services.length > 0)` removes it when it has no services, so without Barbican the nav is unchanged. With Barbican present, a new Authorization section appears.

**Docs.** No documentation changed. `packages/aurora/README.md` and the repo docs have no Key Manager mention, and the KB lists no Barbican domain. The new nav section and policy file are not described anywhere.

**Stale or unused.** Server procedures `updateSecret`, `addContainerSecret`, `deleteContainerSecret` and the permission keys `key-manager:secrets:update`, `key-manager:containers:update`, `key-manager:secrets:payload` have no client caller (`usePermissions.ts` only lists them in a type).

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

1. On a project whose catalog has key-manager/barbican, open the side nav and confirm an Authorization section with a single Key Manager entry; click it and land on the Secrets tab
2. On the Secrets tab, check columns Name/ID, Status, Type, Content Types; click the copy icon on a UUID and paste it to confirm it is the bare UUID, not the full ref URL
3. Search by name, change Sort by and direction, and page through results (page size 50); confirm the URL search params (`search`, `sort`, `page`) update and survive a reload
4. Create a Secret (name, type, payload) and confirm it appears in the list; open its row menu, choose Show Details, and check all fields and the Back button
5. On the secret detail page click Reveal Payload, verify content type and text, use Copy and Hide
6. Delete the secret via the row menu and confirm the dialog; confirm the row disappears
7. Switch to Containers: create a generic container, open its details (it will have no secrets, so the empty-state row shows), then delete it
8. Switch to Orders: create a key order (aes/256), open its details and wait for status/secret_ref to change; then delete it
9. Log in as a viewer-only user (role keymanager_viewer) and confirm Create and Delete are hidden but lists and details work

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

- Project without a Barbican catalog entry: nav entry absent, and a direct URL to `/authorization/key-manager/...` redirects to the project page (`key-manager.tsx` beforeLoad)
- Catalog lookup fails (network or tRPC error): silently redirects to the project page instead of showing the error component (`key-manager.tsx` catch branch)
- User without `key-manager:secrets:list`: the Message 'You do not have permission to view secrets.' is shown (`SecretsList.tsx:71`), but the tab itself stays visible, and the message is hard-coded English, not i18n
- Secrets, containers or orders with null name: list shows an italic 'unnamed' fallback, and the detail page falls back to the id as title; orders list shows only the UUID
- Secret with null `content_types`, algorithm, bit_length or mode: renders '- -'; null expiration renders 'Never'
- Reveal payload for a binary or non-text secret, or one with no payload yet (PENDING): the server reads `res.text()`, so check garbled output and the error Message 'Failed to load payload.'
- Reveal payload as a user who has list/get but not the payload right: the button is still shown (no `canUser` gate at `SecretDetailsView.tsx:90`); confirm the server error surfaces
- Delete a container that still has secrets or consumers (Barbican error): `mapKmError` returns a generic 'Key Manager delete container failed', so check whether the user sees a useful message
- Search typing: `onInput` and `onSearch` both navigate, so every keystroke changes the URL and refetches; check for history spam and flicker, and that page resets to 1
- Orders sort: the sort string `created:desc` is split into `sort_key`/`sort_dir` on the server; check that the Sort by options match the keys Barbican accepts for orders
- Create Order with a non-numeric or empty bit length: `parseInt` gives NaN, and `meta.bit_length` is sent as NaN; for type 'asymmetric' or 'certificate' the meta fields are still just algorithm/bit_length
- Deep-link to a detail route with an unknown id: the detail view shows the server error message through `Status status="error"`, and the breadcrumb falls back to the id
- Switch tabs while on a detail page: tab state comes from `useMatch` on the index and detail routes, so Containers and Orders detail pages keep their tab highlighted
- Reveal Payload on a `text/plain` or `application/octet-stream` secret: Barbican should return 406 because `Accept: application/json` is sent (CR1); a binary secret that does load shows garbled text (I15).
- Remove a secret from a generic container via `deleteContainerSecret`: the path-segment DELETE is not a documented endpoint and should fail (CR6).
- Load a container whose `secret_refs` contains an unnamed reference (`name: null`): the containers list fails validation (CR7).
- With more than 50 secrets, go to the last page holding a single item and delete it: an empty table with no pagination remains (CR8).
- Set `deniedServices` to include `key-manager` (or an `enabledServices` list without it): the Key Manager nav entry still shows and the route is reachable by URL (CR9).
- On the Orders tab change Sort by / direction: the order of rows should not change, since Barbican ignores `sort_key`/`sort_dir` (CR10).
- As a user without `key-manager:secrets:payload`, open a secret's details: Reveal Payload is still shown and clickable (CR4).

</details>

---

## Checked and dismissed

<details>
<summary><strong>Candidates scored below 50 (15)</strong></summary>

| Score | Candidate                                                                                                                                    | Location                                                                                                                             | Why                                                                                                                                                                                                      |
| ----- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 25    | User-facing strings are not translated: JSX button/placeholder/label literals (`Create Secret`, `Search by name...`, `Sort by`,…             | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/constants.ts:1`           | Strings such as `Create Secret`, `Sort by`, `Search by name...` and the column arrays are plain English in packages/aurora, but the review standards (B.14, What NOT to Review) say hardcoded strings…   |
| 25    | The PR body checklist leaves the tests, docs, warnings and 'commented my code' items unchecked even though tests are added, and the Testing… | PR body                                                                                                                              | Unchecked checklist boxes in the PR body are a process/docs nitpick; no standard requires them and the code is unaffected.                                                                               |
| 25    | listContainers sends a `name` filter, but the Containers list documents only offset and limit.                                               | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:167`                                                              | Containers list reference documents only offset/limit, so name is likely ignored, but the client's ContainersList does not appear to send a name search, so I could not confirm any user-visible effect. |
| 25    | updateSecret uses PUT /v1/secrets/{id}, which the reference restricts to metadata-only secrets without a payload; the router offers it for…  | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:137`                                                              | The reference restricts PUT /v1/secrets/{uuid} to payload-less secrets, but I found no client caller of updateSecret, and the failure would just surface Barbican's error; impact unclear.               |
| 25    | CreateOrderInputSchema accepts type "certificate", but the Orders reference documents only key and asymmetric as valid order types.          | `packages/aurora/src/server/KeyManager/types/keyManager.ts:91`                                                                       | orders.rst says valid types are key and asymmetric, but Barbican also supports certificate orders (documented elsewhere) and the UI deliberately offers it; the reference page alone does not show it…   |
| 25    | List calls accept any numeric limit/offset (z.number() without .max(100)/.min(0)); Barbican caps limit at 100, so a client-supplied larger…  | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:21`                                                               | limit: z.number().default(20) at line 21 has no max, but Barbican clamps to 100 and the UI uses 50; no concrete user-visible effect.                                                                     |
| 25    | None of the KeyManager mutations or the payload query enforce a server-side canUser/policy check; they rely only on projectScopedProcedure…  | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:93`                                                               | No KeyManager mutation checks the policy engine; permissionRouter only exposes canUser.                                                                                                                  |
| 25    | Decrypted secret payload is fetched via a TanStack Query useQuery (enabled:false + refetch) and so stays in the client query cache after…    | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:34` | SecretDetailsView.tsx:34 uses useQuery with enabled:false, so the payload stays in the query cache after Hide.                                                                                           |
| 25    | ID/ref inputs interpolated into outbound Barbican paths are unvalidated `z.string()`; encodeURIComponent does not encode `.`, so…            | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:37`                                                               | keyManagerRouter.ts:37-39 use z.string() ids and :19-22 use unbounded z.number().                                                                                                                        |
| 25    | Acceptance criterion partly met: tRPC BFF is implemented with complete Zod schema validation for Secrets, Containers, and Orders.            | PR files                                                                                                                             | The create response is cast at keyManagerRouter.ts:128 (data.secret_ref as string), and list/get responses are parsed with parseOrThrow.                                                                 |
| 25    | Stale caller of `updateSecret / addContainerSecret / deleteContainerSecret`: Server procedures with no client caller, and no UI flow behind… | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:61`                                                               | updateSecret/addContainerSecret/deleteContainerSecret exist in the router with no client caller, but the PR body lists them as server procedures and unused API surface is not a defect; whether…        |
| 25    | Stale caller of `key-manager:secrets:update / key-manager:containers:update / key-manager:secrets:payload`: Permission keys defined and…     | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:6`              | usePermissions.ts:6 defines secrets:update/containers:update/payload keys never checked; unused update keys follow from there being no update UI, and the payload-gating part is already covered by C57. |
| 0     | Key Manager server procedures never evaluate the loaded policy; canUser is registered but each handler (incl.                                | `packages/aurora/src/server/KeyManager/routers/index.ts:8`                                                                           | Checked: no Compute or Storage router enforces the policy engine in handlers either (only the canUser permission routers reference it), and the Key Manager calls run with the user's rescoped token,…   |
| 0     | mapKmError attaches the raw upstream error as `cause` for every failure; if the tRPC error formatter or logger serialises causes this can…   | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:50`                                                               | keyManagerRouter.ts:53 sets cause: error.                                                                                                                                                                |
| 0     | Acceptance criterion partly met: All UI components follow the Aurora design system.                                                          | PR files                                                                                                                             | The unwrapped strings in SecretsList.tsx (lines 84, 97, 105) are in packages/aurora, where eslint-plugin-lingui enforces i18n.                                                                           |

</details>

---

_Analyzed 2026-10-25 · commit `fd248f08` · read-only · skill: review-and-comment-pr_
