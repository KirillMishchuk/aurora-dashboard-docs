## Update — <TODAY>, head `64c47a99`

_Reviewed at head [`64c47a99`](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393/commits/64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7) · base `main` at `cd8e674e` · <TIME>_

### ⚖️ &nbsp; Verdict

Recommendation: **🔴 Request Changes** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **Medium**

- **Must fix before merge**: CR11
- **Still open from the earlier review:** CR3, CR4 (partly), CR5, CR9 (partly), CR10 · P1
- **Process:** P2

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
| P2   | —        | Process  | —         | The description lists add/remove secret refs for containers; no procedure implements them                        | PR body                                                                 |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR11 — Reveal Payload fails for secrets whose content type isn't `application/octet-stream`** · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:102`
A user who stores a secret as `text/plain` (the common case for passwords and API keys created via the CLI) and clicks Reveal Payload gets the generic `Key Manager get secret payload failed` error instead of the value. The CR1 fix replaced the default Accept header with a hardcoded one:

```ts
headers: { Accept: "application/octet-stream" },
```

Barbican only serves the payload in one of the secret's `content_types`; anything else is answered with `406 Not Acceptable`, which `mapKmError` turns into an `INTERNAL_SERVER_ERROR`. Only opaque (octet-stream) secrets work. No test covers a non-octet-stream secret. Reference: [Barbican secrets API — GET /v1/secrets/{uuid}/payload](https://docs.openstack.org/barbican/latest/api/reference/secrets.html#get-secrets-uuid-payload): "you must set the accept header to one of the values listed in the `content_types` attribute of a secret's metadata".
_Fix:_ Fetch the secret's metadata first (or accept its content type as input from the client, which already reads `secret.content_types` in `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:51`) and send `content_types.default` as the Accept header; add a router test for a `text/plain` secret.

**P2 — The description claims what the code doesn't do** · Process · PR body
The description says the containers API covers adding and removing secret refs, but `keyManagerRouter` has only `listContainers`, `getContainer`, `createContainer` and `deleteContainer` for containers.
_Fix:_ Drop "add/remove secret refs" from the description, or add the two procedures if they belong in this PR.

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

| Raised by                                                                                                  | Claim                                                                                                                                                                                                                                                                                                                                                                                                                                                    | Why not a finding                                                                                                                                                                                                                                                                                                                                   |
| ---------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Copilot [r4360389025](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389025) | The Key Manager canUser router only reports policy decisions. None of the tRPC procedures (getSecretPayload, deleteSecret, deleteContainer, deleteOrder, create*, update*) checks the policy before calling Barbican. A caller can use the tRPC API directly to run an action the UI hides and Aurora's policy denies, whenever Barbican itself allows it. This includes revealing secret payloads, since the hidden control is only a client-side gate. | Verified that keyManagerRouter procedures go straight to Barbican without a policy check. The Compute, Network and Storage routers do the same, and Barbican enforces its own policy server-side, so this is generic hardening with no concrete exploit in this PR. Copilot's thread is unanswered, so it may still be worth a maintainer decision. |

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
