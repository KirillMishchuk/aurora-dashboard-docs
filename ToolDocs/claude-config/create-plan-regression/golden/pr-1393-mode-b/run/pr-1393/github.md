# PR #1393 — GitHub review comments

## Conversation

### KirillMishchuk · 2026-10-26

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

_Reviewed at head [`fd248f08`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393/commits/fd248f083f89fbe9caca6ad536106ffd08860159) · base `main` at `c65b36d0` · 2026-10-25 14:20 UTC_

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

- **Must fix before merge**: CR1, CR4, CR6, CR7, CR8, CR9, CR10
- **Team call** (convention, existing pattern or deferred by a maintainer): CR2, CR3, CR5
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

`key-manager:secrets:payload` is defined in the permission router and the hook's types but no client code reads it; none of the `*DetailsView` files call the permissions hook. Users without payload rights see a working control that triggers a plaintext fetch — only Barbican's own ACLs stop it. This violates the Quick Reject rule on controls shown before permissions resolve and leaves the epic's "all action-triggering elements gated" criterion partly met. Copilot flagged it as CRITICAL ([r4360388886](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388886)); no reply.
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

The Barbican containers reference documents removal only as `DELETE /v1/containers/{container_uuid}/secrets` with a JSON body `{ "name", "secret_ref" }`, where `secret_ref` is required (400 "Missing secret_ref"). The path form is not in the reference, so the call will fail once a UI uses it; the router test asserts the same wrong URL. Copilot raised it ([r4360389656](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389656)); no reply.
_Fix:_ Send `DELETE v1/containers/{id}/secrets` with a body `{ name, secret_ref }`, add `secret_ref` to the input schema, and update the test.

**CR7 — An unnamed secret reference makes the whole container response fail validation** · Bug · `packages/aurora/src/server/KeyManager/types/keyManager.ts:25`
```ts
secret_refs: z.array(z.object({ name: z.string(), secret_ref: z.string() })),
```

`name` is optional for container secret references in the reference, and sibling `name` fields in this file are `.nullable()`. A container with an unnamed ref returns `name: null`, `parseOrThrow` rejects it, and the whole container list fails to load. Copilot raised it ([r4360389713](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389713)); no reply.
_Fix:_ Make it `name: z.string().nullable().optional()` and render a fallback in the UI.

**CR8 — List `page` is not clamped after a delete** · Bug · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:126`
`offset` is `(page - 1) * PAGE_SIZE` and `totalPages` comes from `data.total`, but nothing clamps `page` when the total shrinks. Pagination is hidden when there is one page:

```tsx
{totalPages > 1 && (
```

So after deleting the only row of the last page the user sees an empty table with no way back. Same in the Containers and Orders lists; Copilot raised all three ([r4360389532](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389532), [r4360389254](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389254), [r4360389387](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389387)), no replies.
_Fix:_ When `page > totalPages` after data loads, navigate to `max(totalPages, 1)` with `replace: true`.

**CR9 — Key Manager can't be hidden through service-visibility config** · Bug · `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`
The new nav item is gated only on the catalog:

```ts
...(serviceIndex["key-manager"]?.["barbican"]
```

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
`SecretTableRow.tsx:35` renders `<PopupMenu><PopupMenuOptions>` with no `PopupMenuToggle`, so the default toggle is used without an accessible label (also `ContainerTableRow.tsx:34`, `OrderTableRow.tsx:33`). B.14 requires `<PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>`. Copilot raised it ([r4360388832](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388832)).
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
`usePermissions.ts:21` exports a generic `usePermissions(projectId, permissions)`; B.8 asks for `useKeyManagerPermissions(projectId)`. `SecretModals.tsx` etc. bundle several modals where B.12 wants `<Verb><Resource>Modal.tsx`. Copilot asked for `useKeyManagerPermissions` ([r4360389782](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389782)).
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
Debug is on by default outside production (`context.ts:114`), and signal-openstack logs a `bodyPreview` for text responses, so a `text/plain` secret fetched by `getSecretPayload` is written to the logs (truncated). Copilot flagged it as CRITICAL ([r4360389080](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389080)); no reply.
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

### 🗨️ &nbsp; Review comments not taken up

Raised in the review discussion, checked at this head and not counted as findings:

| Raised by                                                                                                  | Claim                                                                                                                                                                                                                                                                                 | Why not a finding                                                                                                                                                                                                                                                                                                                                                                            |
| ---------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Copilot [r4360389025](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389025) | Key Manager server procedures never evaluate the loaded policy; canUser is registered but each handler (incl. getSecretPayload, deleteContainerSecret, createSecret) only uses projectScopedProcedure, so permission gating is UI-only and a direct tRPC call bypasses Aurora policy. | Checked: no Compute or Storage router enforces the policy engine in handlers either (only the canUser permission routers reference it), and the Key Manager calls run with the user's rescoped token, so Barbican enforces its own policy server-side; the Aurora policy is a UI hint, so a direct tRPC call bypasses nothing real. Not a verified hole and consistent with existing design. |

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

Adds an in-core Key Manager (OpenStack Barbican) plugin: 48 files, about 4.4k added lines, almost all new. CI on the head commit: 17 pass, 0 fail, 0 pending, 4 skipped, 1 cancelled. The PR body checklist leaves the test and tests-pass boxes unticked, and its testing steps are only `pnpm i` and `pnpm run test`.

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

### github-actions[bot] · 2026-10-26

🚀 **Preview deployed!**
👉 [PR #1393](https://pr-1393.aurora-previews.d.c.eu-nl-1.cloud.sap)

Commit: `fd248f083f89fbe9caca6ad536106ffd08860159`

### github-actions[bot] · 2026-10-26

🚀 **Preview deployed!**
👉 [PR #1393](https://pr-1393.aurora-previews.d.c.eu-nl-1.cloud.sap)

Commit: `3bfdb1287446a682163955c11f5defdbacd83523`

### github-actions[bot] · 2026-10-26

🚀 **Preview deployed!**
👉 [PR #1393](https://pr-1393.aurora-previews.d.c.eu-nl-1.cloud.sap)

Commit: `64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7`

### KirillMishchuk · 2026-10-26

## Update — 2026-10-26, head `64c47a99`

_Reviewed at head [`64c47a99`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393/commits/64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7) · base `main` at `cd8e674e` · 2026-10-26 12:57 UTC_

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

- **Must fix before merge**: CR11
- **Still open from the earlier review:** CR3, CR4 (partly), CR5, CR9 (partly), CR10 · P1

### Fixed since last analysis

- CR2 — Order modal now validates algorithm and bit length (positive integer) and disables Create; secret/container modals have only optional fields.
- CR6 — deleteContainerSecret (and addContainerSecret) were removed from the router.
- CR7 — secret_refs[].name is now nullable.
- CR8 — An effect steps back one page when a page after the first comes back empty.
- I1 — Prop renamed to canDeleteSecret.
- I2 — Row menu now has PopupMenuToggle with a titled moreVert button.
- I16 — Payload request now passes debug:false.

**Partly fixed**

- CR1 — getSecretPayload now sends `Accept: application/octet-stream`, which fixes octet-stream secrets but still gets 406 for secrets stored with another content type — see CR11.
- CR4 — Reveal Payload is now gated by key-manager:secrets:payload; detail views still do not check the :get permissions.
- CR9 — Nav entry now honours enabledServices/deniedServices via isEnabled; the key-manager route beforeLoad still only checks the service catalog.
- I3 — Separator before Delete added; labels are still bare Show Details / Delete without the entity name.
- I12 — usePermissions renamed to useKeyManagerPermissions; bundled *Modals.tsx, utils.ts and constants.ts remain.
- I18 — addContainerSecret and deleteContainerSecret removed; updateSecret remains with no client caller.
- I20 — Tests were added for secret/container/order list containers, table rows, router and schemas; no tests for modals, detail views, nav entry or layout guard, and no E2E.

**Still open**

- CR3 — Still no success toast on create or delete of secrets, containers or orders.
- CR5 — SearchInput still calls onSearchChange (a navigate) on every onInput keystroke, with no local state or debounce.
- CR10 — listOrders still sends sort_key/sort_dir and the Orders list still renders the sort control.
- P1 — No changeset in the PR.
- I4 — Delete modal still puts the name in the title and uses a bare Delete confirm label.
- I5 — Only Cancel is disabled while pending; the close-X is not.
- I6 — Create modals still use plain useState, no autoFocus, inputs not disabled in flight.
- I7 — Still raw Select + SortButton and distribution="end" toolbar.
- I8 — 403 on list pages is still an inline warning Message with hard-coded English.
- I9 — Detail routes still fetch in the component, and the view fetches again.
- I10 — Ad-hoc classes still present.
- I11 — Raw div/p/pre still used.
- I13 — Empty state still says to create a secret even when a search returned nothing.
- I14 — Error state still shows raw error.message as title, no body or retry.
- I15 — Payload is still decoded with res.text(), so binary secrets are corrupted.
- I17 — Orders columns are still ID, Status, Type; no Name column.
- I19 — mapKmError still drops Barbican's error body.
- I21 — Import order and ../../ relative imports unchanged.

### 🔧 &nbsp; Required Changes

| #    | Severity | Category | Precedent | Issue                                                                                                            | Location                                                                |
| ---- | -------- | -------- | --------- | ---------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| CR11 | 🟠 Major | Bug      | —         | `getSecretPayload` hardcodes `Accept: application/octet-stream`, so non-octet-stream secrets still fail with 406 | `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:102` |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR11 — Reveal Payload fails for secrets whose content type isn't `application/octet-stream`** · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:102`
A user who stores a secret as `text/plain` (the common case for passwords and API keys created via the CLI) and clicks Reveal Payload gets the generic `Key Manager get secret payload failed` error instead of the value. The CR1 fix replaced the default Accept header with a hardcoded one:

```ts
headers: { Accept: "application/octet-stream" },
```

Barbican only serves the payload in one of the secret's `content_types`; anything else is answered with `406 Not Acceptable`, which `mapKmError` turns into an `INTERNAL_SERVER_ERROR`. Only opaque (octet-stream) secrets work. No test covers a non-octet-stream secret. Reference: [Barbican secrets API — GET /v1/secrets/{uuid}/payload](https://docs.openstack.org/barbican/latest/api/reference/secrets.html#get-secrets-uuid-payload): "you must set the accept header to one of the values listed in the `content_types` attribute of a secret's metadata".
_Fix:_ Fetch the secret's metadata first (or accept its content type as input from the client, which already reads `secret.content_types` in `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:51`) and send `content_types.default` as the Accept header; add a router test for a `text/plain` secret.

</details>

### 💡 &nbsp; Improvements

| #   | Severity | Category      | Precedent     | Issue                                                                                                    | Location                                                                                                                          |
| --- | -------- | ------------- | ------------- | -------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| I22 | 🟢 Low   | Accessibility | existing code | Icon-only `moreVert` row-action toggles have a `title` but no `aria-label`                               | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:40` |
| I23 | 🟢 Low   | UI/UX         | —             | Create Order validation errors show as the user types instead of on blur / submit                        | `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:43`     |
| I24 | 🟢 Low   | Code Quality  | —             | Container secret association (issue #1133 container Edit scope) was dropped with no scope note in the PR | PR files                                                                                                                          |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I22 — Row-action toggles lack an `aria-label`** · Accessibility · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:40`
Screen-reader users get an unreliable name for the row-action button in every Key Manager list row, since `title` is only a fallback. The toggle is `<Button icon="moreVert" title={t`Secret actions`} />` at `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:40`, and the same in `ContainerTableRow.tsx:39` and `OrderTableRow.tsx:38`. B.14 / Quick Reject: "Icon-only button without `aria-label`".
_Precedent:_ the same pattern is already in merged code — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/floatingips/$floatingIpId/-components/-details/FloatingIpDetailsView.tsx:66`.
_Fix:_ Add a matching `aria-label` next to `title` on all three toggles, as in `packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.tsx:67`.

**I23 — Create Order modal validates as-you-type** · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:43`
Clearing the Algorithm or Bit Length field paints an error immediately, before the user has left the field. `algorithmError` and `bitLengthError` are derived from state on every render (`packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:43`) and passed straight to `errortext`, with no touched/blur tracking. B.11: validate on blur by default and re-validate on submit; as-you-type only for strict-format fields, which these aren't. The defaults are valid, so nothing shows before interaction.
_Fix:_ Track touched fields and show the error only after blur or a submit attempt, as `packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/CreateFlavorModal.tsx:225` does.

**I24 — Container secret association is no longer delivered** · Code Quality · PR files
Users can't add or remove secrets in an existing container, which issue #1133 lists as the container Edit scope (`POST`/`DELETE /v1/containers/{id}/secrets`). This update removed `addContainerSecret` and `deleteContainerSecret` (fixing CR6), so the BFF covers list/get/create/delete for all three resources plus `updateSecret` and the payload query, but not container secret association. The PR body doesn't say this part is out of scope, so the acceptance criterion "tRPC BFF … for Secrets, Containers, and Orders" is only partly met.
_Fix:_ Either reimplement association with the documented `POST /v1/containers/{id}/secrets` / `DELETE /v1/containers/{id}/secrets` (body with `secret_ref`), or state in the PR body that it's deferred and link a follow-up issue.

</details>

### 🗨️ &nbsp; Review comments not taken up

Raised in the review discussion, checked at this head and not counted as findings:

| Raised by                                                                                                  | Claim                                                                                                                                                                                                                                                                                                    | Why not a finding                                                                                                                                                                                                                                                                                                                                   |
| ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Copilot [r4360389025](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389025) | The Key Manager canUser router only reports policy decisions. None of the tRPC procedures (getSecretPayload, deleteSecret, deleteContainer, deleteOrder, create*, update*) checks the policy before calling Barbican. A caller can use the tRPC API directly to run an action the UI hides and Aurora's… | Verified that keyManagerRouter procedures go straight to Barbican without a policy check. The Compute, Network and Storage routers do the same, and Barbican enforces its own policy server-side, so this is generic hardening with no concrete exploit in this PR. Copilot's thread is unanswered, so it may still be worth a maintainer decision. |

### What changed

<details>
<summary><strong>What was done</strong></summary>

This update covers `fd248f083f89fbe9caca6ad536106ffd08860159..64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7`. The PR is not a draft. On the head commit 13 checks passed, none failed, 4 were skipped and 5 are still pending (build, test, type-check, check-i18n, preview).

**Container secret association.** The server procedure `addContainerSecret` (`POST /v1/containers/{id}/secrets`) was removed together with its unit test. This endpoint is documented by Barbican and is listed in the linked issue's Phase 2 ("Manage Container Secrets" / `containers.updateSecrets`). With it gone, the PR has no server procedure for adding or removing secret references on an existing container.

**Translation catalogs.** The English and German `messages.po` files also changed for strings unrelated to Key Manager: the image-service rejection messages, "No Project Access", "Project not found.", "This property is reserved and cannot be modified." and a removed "Unnamed" entry. These look like a catalog re-extract after merging the base branch, not part of the Key Manager work.

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

The PR description still lists "add/remove secret refs" among the container procedures, which no longer exists on the server. The linked issue's Phase 2 items for container secret association (`containers.updateSecrets` and the "Manage Container Secrets" flow) now have no server-side basis. Nothing else in the repository referenced `addContainerSecret` or `deleteContainerSecret` at the head commit.

</details>

### github-actions[bot] · 2026-10-26

🚀 **Preview deployed!**
👉 [PR #1393](https://pr-1393.aurora-previews.d.c.eu-nl-1.cloud.sap)

Commit: `8763f93bc0ad314073ddc5c69bbbf1e34201029f`

## Reviews

### copilot-pull-request-reviewer[bot] · 2026-10-23

<!-- ccr-overview-v2 -->

### 🟡 Changes recommended

One or more issues must be addressed before approval.

<details open>
<summary><strong>19 open issues</strong></summary>

- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.png" alt="High severity" width="62" height="18" align="texttop"></picture> [Rename permission prop to canDeleteContainer](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388743) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.png" alt="High severity" width="62" height="18" align="texttop"></picture> [Add labeled menu toggle and separator before Delete](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388832) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.png" alt="High severity" width="62" height="18" align="texttop"></picture> [Gate Reveal Payload on payload permission](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388886) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.png" alt="High severity" width="62" height="18" align="texttop"></picture> [Rename permission prop to canDeleteSecret](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388949) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.png" alt="High severity" width="62" height="18" align="texttop"></picture> [Enforce Key Manager policy in every server operation](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389025) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.png" alt="High severity" width="62" height="18" align="texttop"></picture> [Disable transport debugging during payload retrieval](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389080) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/high-v2-light.png" alt="High severity" width="62" height="18" align="texttop"></picture> [Override Accept header for payload retrieval](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389136) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture> [Rename permission to canDeleteContainer](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389203) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture> [Reset pagination after deleting the final page item](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389254) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture> [Validate algorithm and bit length before mutation](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389321) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture> [Reset pagination after deleting the final order](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389387) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture> [Use resource-specific canDeleteSecret permission](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389452) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture> [Reset pagination after deleting the final secret](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389532) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture> [Apply isEnabled to the Key Manager catalog entry](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389607) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture> [Use Barbican&#39;s container-secret removal contract](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389656) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/medium-v2-light.png" alt="Medium severity" width="62" height="18" align="texttop"></picture> [Allow null names on returned secret references](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389713) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.png" alt="Low severity" width="62" height="18" align="texttop"></picture> [Rename hook to useKeyManagerPermissions](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389782) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.png" alt="Low severity" width="62" height="18" align="texttop"></picture> [Expose deletion permission as canDeleteOrder](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389872) · New
- <picture><source media="(prefers-color-scheme: dark)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-dark.svg"><source media="(prefers-color-scheme: light)" srcset="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.svg"><img src="https://github.githubassets.com/static/images/icons/copilot-code-review/low-v2-light.png" alt="Low severity" width="62" height="18" align="texttop"></picture> [Rename authorization prop to canDeleteOrder](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389932) · New
</details>

<details>
<summary><strong>What changed in this PR</strong></summary>

Adds an in-core Barbican integration to Aurora, exposing project-scoped Secrets, Containers, and Orders through a single Key Manager navigation entry and tabbed interface.

**Changes:**
- Adds tRPC resource procedures, validation schemas, and permission mappings.
- Introduces catalog-guarded navigation, resource lists/details, and create/delete workflows.
- Adds router, schema, and DataGrid unit tests plus translation entries.

Review identified blocking authorization and payload-handling issues, alongside API-contract and UI-state problems. Project tests were not run; an isolated binary round-trip check confirmed payload corruption from text decoding.

| File | Description |
| ---- | ----------- |
| packages/​aurora/​src/​server/​routers.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​server/​KeyManager/​types/​keyManager.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​server/​KeyManager/​types/​keyManager.test.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​server/​KeyManager/​routers/​permissionRouter.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​server/​KeyManager/​routers/​keyManagerRouter.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​server/​KeyManager/​routers/​keyManagerRouter.test.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​server/​KeyManager/​routers/​index.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​locales/​en/​messages.po | Updated as part of this pull request. |
| packages/​aurora/​src/​locales/​de/​messages.po | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routeTree.gen.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​index.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​$secretId.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​-components/​SecretTableRow.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​-components/​SecretTableRow.test.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​-components/​SecretsList.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​-components/​SecretModals.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​-components/​SecretListContainer.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​-components/​SecretListContainer.test.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​-components/​SecretDetailsView.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​secrets/​-components/​constants.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​index.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​$orderId.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​-components/​OrderTableRow.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​-components/​OrderTableRow.test.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​-components/​OrdersList.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​-components/​OrderModals.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​-components/​OrderListContainer.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​-components/​OrderListContainer.test.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​-components/​OrderDetailsView.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​orders/​-components/​constants.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​index.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​index.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​$containerId.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​-components/​ContainerTableRow.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​-components/​ContainerTableRow.test.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​-components/​ContainersList.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​-components/​ContainerModals.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​-components/​ContainerListContainer.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​-components/​ContainerListContainer.test.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​-components/​ContainerDetailsView.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​containers/​-components/​constants.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​-components/​utils.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager/​-components/​usePermissions.ts | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​$projectId/​authorization/​key-manager.tsx | Updated as part of this pull request. |
| packages/​aurora/​src/​client/​routes/​_auth/​projects/​-components/​buildNavSections.ts | Updated as part of this pull request. |
| apps/​dashboard/​src/​policies/​key-manager.json | Updated as part of this pull request. |
</details>

<sub>Review effort: Balanced</sub>

## Inline review threads

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerTableRow.tsx:15` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388743

[STYLE] Rename the permission prop to `canDeleteContainer: boolean` and propagate it through callers/tests. Permission props must name the authorized resource as well as the verb, so the destructive container action does not depend on an ambiguously named `canDelete` value.

This issue also appears in the following locations of the same file:
- line 34
- line 36

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderTableRow.tsx:36` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388832

[STANDARD] Add the prescribed `PopupMenuToggle` containing an aria-labeled more-actions Button and a `PopupMenuSectionSeparator` before Delete. This single-order menu currently puts deletion immediately next to navigation without the required destructive-action separation.

This issue also appears on line 35 of the same file.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:91` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388886

[CRITICAL] Gate Reveal Payload with the separately defined `key-manager:secrets:payload` permission, defaulting to false until it resolves. This view never checks that permission, so even a direct visit renders a functional control that requests secret material. Disable or omit the control for unauthorized users and guard the handler as well.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:15` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360388949

[STYLE] Rename this permission prop to `canDeleteSecret: boolean` and update its callers/tests. Permission props must identify both the verb and resource; the generic `canDelete` loses which authorization check this destructive action depends on.

This issue also appears in the following locations of the same file:
- line 35
- line 37

### `packages/aurora/src/server/KeyManager/routers/index.ts:8` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389025

[CRITICAL] Registering `canUser` alongside the resource procedures does not enforce its decisions. `projectScopedProcedure` only authenticates and rescopes the token, and none of the Key Manager handlers checks the loaded policy. A caller can invoke an operation that Aurora denies whenever Barbican permits it. Add a server-side guard for each operation before issuing its service request, e.g. `if (!policy.check(rule)) throw new TRPCError({ code: "FORBIDDEN" })`, including payload retrieval and container association changes.

### `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:96` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389080

[CRITICAL] Disable transport debugging for payload retrieval. Signal-openstack logs a response `bodyPreview` for text responses, and that string is not redacted. Since debugging is enabled by default outside production, revealing a text secret also copies its plaintext into server logs.

### `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389136

Override Accept for payload retrieval. The session defaults to `Accept: application/json` in `server/context.ts:115-117`, and signal-openstack preserves that header here. Barbican's payload endpoint returns secret material rather than JSON, so ordinary text/binary secrets fail content negotiation with 406. Request a payload media type instead.

This issue also appears in the following locations of the same file:
- line 103
- line 107
- line 110
- line 134

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerListContainer.tsx:12` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389203

[STYLE] Name this permission `canDeleteContainer: boolean` rather than `canDelete`. The container's public contract must follow `can<Verb><Noun>` so the specific RBAC capability remains visible while it is forwarded to rows.

This issue also appears on line 59 of the same file.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainersList.tsx:98` · Copilot · 2026-10-23

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389254

Recover the URL page when deletion empties the final page. Deleting the only container on page 2 leaves page=2/offset=50 after invalidation, while the reduced total hides pagination here. The table then reports no containers despite the remaining first page, with no pagination control to recover. Clamp/reset the page after deletion or after a total reduction.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:52` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389321

[STANDARD] Validate bit length and algorithm before calling the mutation. Clearing Bit Length yields NaN from `parseInt`, and values such as zero, negatives, or fractional input are neither rejected nor explained inline; Create remains enabled. The BFF's unrestricted `meta` record does not supply this validation either. Validate on blur and submit, require a positive integer compatible with the algorithm, and disable Create for invalid values.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrdersList.tsx:104` · Copilot · 2026-10-23

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389387

Recover the URL page when deletion empties the final page. Deleting the only order on page 2 leaves page=2/offset=50 after invalidation, while the reduced total hides pagination here. Users are stranded on an empty table even though page 1 still contains orders. Clamp/reset the page after deletion or when the refreshed total shrinks.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:12` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389452

[STYLE] Use the resource-specific permission name `canDeleteSecret: boolean` throughout this container contract. The required `can<Verb><Noun>` form makes it explicit that the value authorizes deleting secrets rather than another resource's delete operation.

This issue also appears on line 59 of the same file.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:133` · Copilot · 2026-10-23

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389532

Recover the URL page after deleting the last item on the final page. For example, deleting item 51 while on page 2 invalidates the list but leaves offset 50; the new total is 50, so this condition also removes pagination. The user sees an empty table with no way to return to the remaining secrets. Clamp/reset the page after deletion or when the refreshed total shrinks.

### `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389607

Apply `isEnabled` to this catalog check as the other in-core entries do. Otherwise Key Manager remains visible even when excluded by `enabledServices` or explicitly listed in `deniedServices`, bypassing the deployment's service-visibility configuration.

### `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:252` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389656

Use Barbican's container-secret removal contract: DELETE targets `/v1/containers/{container_uuid}/secrets` with the secret reference in a JSON body, not `/secrets/{secretName}`. The current URL addresses no such operation and cannot remove an association. Accept the reference, send it in the DELETE body, and update the test that currently asserts this incorrect URL.

### `packages/aurora/src/server/KeyManager/types/keyManager.ts:25` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389713

Allow a null name on returned secret references. Barbican permits unnamed references in generic containers and returns `name: null` for them. Requiring a string makes `parseOrThrow` reject both the container detail and any list containing that otherwise valid container; the detail renderer already handles a missing display name.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:21` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389782

[STYLE] Rename this hook/file to `useKeyManagerPermissions`. It implements Key Manager-specific permission keys and the feature-area hook contract requires the feature in its name; generic `usePermissions` obscures that scope at imports and call sites.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderListContainer.tsx:12` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389872

[STYLE] Expose this capability as `canDeleteOrder: boolean`, following the required `can<Verb><Noun>` permission contract. Keeping the resource in the name prevents ambiguous authorization flags as capabilities are passed through the list and row layers.

### `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderTableRow.tsx:15` · Copilot · 2026-10-23 · outdated (the code under it has changed)

https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389932

[STYLE] Rename this authorization prop to `canDeleteOrder: boolean` and update consumers/tests. The required verb-plus-resource naming makes the permission governing order deletion explicit instead of passing a generic `canDelete` flag.
