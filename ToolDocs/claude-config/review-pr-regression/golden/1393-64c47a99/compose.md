# Compose findings — review-and-comment-pr

Write `texts.json` in the run folder (shape at the end), then run
`python3 .claude/skills/review-and-comment-pr/scripts/assemble.py --run <run folder> --texts`
and `render.py`. Scores, severity, category and location are the scorers' — don't change them.
Text rules, code placeholders and `[[ref:<id>]]` are in `references/findings-format.md`.
A finding's precedent (existing pattern / deferred) is the scorer's tag — render.py shows it; don't repeat it in the explanation.

## Findings

### `c8` — Major · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts | headers: { Accept: "application/octet-stream" },` · score 75
- **Claim** (find-api-contract): getSecretPayload hardcodes Accept: application/octet-stream. Barbican requires the Accept header on /payload to be one of the values in the secret's content_types, so a secret stored with another type (for example text/plain) can get 406 Not Acceptable. mapKmError turns that into INTERNAL_SERVER_ERROR, and the user sees 'Key Manager get secret payload failed' when revealing the payload. It works only for secrets whose content type is application/octet-stream.
- **Scorer:** The update fixes CR1 by hardcoding `Accept: application/octet-stream` (line 102), but the Barbican secrets reference says the Accept header on /payload must be one of the secret's `content_types`, and lists 406 Not Acceptable. A secret stored as text/plain therefore still gets 406, which `mapKmError` turns into a generic failure. Reveal Payload only works for octet-stream secrets. The fix is half done, so this is scored as a new problem and not dropped as a repeat of CR1. Use the secret's `content_types.default`, or fetch the secret first.
- **Precedent:** Other KM calls (getSecret, listSecrets) send no Accept header; the docs show Accept: application/json on those metadata calls.
- **Evidence:**

Code at 64c47a99, keyManagerRouter.ts:100-104: `.get(`v1/secrets/${encodeURIComponent(input.secretId)}/payload`, { headers: { Accept: "application/octet-stream" }, debug: false })`. Reference (barbican doc/source/api/reference/secrets.rst, raw github, section 'GET /v1/secrets/{uuid}/payload', rendered at https://docs.openstack.org/barbican/latest/api/reference/secrets.html#get-secrets-uuid-payload): "When making a request for a secret's payload, you must set the accept header to one of the values listed in the ``content_types`` attribute of a secret's metadata." The documented example sends `Accept: text/plain`, and the status table lists `406 | Not Acceptable`. The secret metadata example shows `"content_types": {"default": "application/octet-stream"}` for opaque secrets only. The client already reads secret.content_types (SecretDetailsView.tsx:51), so the server could use content_types.default or fetch the secret first. Barbican source barbican/api/controllers/secrets.py: when there is no Accept header it defaults to 'application/octet-stream', otherwise it uses the header value. In signal-openstack at 64c47a99, grep for 'accept' in packages/signal-openstack/src finds nothing, so the in-code comment claiming a default 'Accept: application/json' is not backed by that client. I could not check what undici/fetch sends by default. Secondary: the body is read with res.text() (line 110), which corrupts binary payloads.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c1` — Low · Accessibility · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:40` · score 75 · precedent: existing (packages/aurora/src/client/routes/_auth/projects/$projectId/network/floatingips/$floatingIpId/-components/-details/FloatingIpDetailsView.tsx:66)
- **Claim** (find-standards): The new row-action toggles are icon-only Buttons with only a title and no aria-label. Screen readers may announce nothing reliable for the control in every key-manager list row.
- **Scorer:** The row toggle is `<Button icon="moreVert" title={t`Secret actions`} />` with no `aria-label` (same in ContainerTableRow.tsx:39 and OrderTableRow.tsx:38). The Quick Reject Checklist says: "Icon-only button without `aria-label`". Severity is Low because `title` still gives most screen readers a fallback name, and Ceph and flavors pair `title` with `aria-label`.
- **Precedent:** FloatingIpDetailsView.tsx:66 also uses title only; Ceph and flavors pair title with aria-label.
- **Evidence:**

B.14 / Quick Reject: "Icon-only button without `aria-label`". Code: <Button icon="moreVert" title={t`Secret actions`} /> (same in ContainerTableRow.tsx:39, OrderTableRow.tsx:38). example: packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.tsx:67


### `c3` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:43` · score 50
- **Claim** (find-standards): CreateOrderModal shows validation errors as the user types, derived on every render, instead of on blur / submit. Clearing the Algorithm field immediately paints an error before the field is left, and the Create button is disabled with no submit-time revalidation.
- **Scorer:** OrderModals.tsx:43-46 derives `algorithmError`/`bitLengthError` from state on every render and passes them to `errortext`, with no blur or touched tracking. B.11 says "Validate on blur by default", and Algorithm and Bit Length are not strict-format fields. Initial defaults are valid, so the effect is small. The update does what CR2 asked, so this is about when the errors show, not whether.
- **Precedent:** Not a Reject-line violation by itself (initial defaults are valid, so nothing shows before interaction).
- **Evidence:**

B.11: "Validate **on blur** by default; always re-validate all fields **on submit**. Validate **as-you-type** only for strict-format fields"; Algorithm and Bit Length are not strict-format fields. Errors are computed from state at lines 43-46 and passed to errortext (94-107) with no touched/blur tracking. example: packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/CreateFlavorModal.tsx:225


### `c11` — Low · Code Quality · `PR files` · score 50
- **Claim** (describer (acceptance)): Acceptance criterion partly met: tRPC BFF is implemented with complete Zod schema validation for Secrets, Containers, and Orders.
- **Scorer:** The Phase 2 container secret association (`containers.updateSecrets`) is no longer implemented, because the update removed `addContainerSecret` and `deleteContainerSecret`. The issue lists it as the container 'Edit' scope (POST/DELETE /v1/containers/{id}/secrets), and the PR body states no scope exclusion. The acceptance criterion is only partly delivered.
- **Evidence:**

`packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:64` to `:277` cover list/get/create/delete for all three resources plus `updateSecret` (`:138`) and the payload query (`:93`), all with Zod schemas. Container secret association (`containers.updateSecrets`, Phase 2) is no longer implemented after `addContainerSecret` was removed in this update.


## Scored below 50 (not in the report)

- `C2` 25: Accessible names/tooltips "Secret actions", "Container actions", "Order actions" are not title case, unlike sibling labels "Bucket actions"-
- `C4` 0: Each list adds a useEffect that calls onPageChange when the current page becomes empty. This is event-driven state sync that could be done i
- `C5` 0: The new useKeyManagerPermissions import uses a two-level relative path (`../../`) in the changed lines instead of the `@/` alias.
- `C6` 0: After switching Accept to application/octet-stream, getSecretPayload still reads the body with res.text(). For binary secrets (e.g. applicat
- `C7` 25: The Key Manager canUser router only reports policy decisions. None of the tRPC procedures (getSecretPayload, deleteSecret, deleteContainer, 
- `C9` 0: The container secret reference schema was loosened to name nullable, but the Barbican docs only show named references; the docs do not say a
- `C10` 0: The new payload gating (key-manager:secrets:payload via canUser) is client-only. The getSecretPayload procedure is a plain projectScopedProc
- `C12` 0: Acceptance criterion partly met: Each tab renders its own overview list with the columns specified in the UI Specification.
- `C13` 0: Acceptance criterion partly met: Users can list, view, create, update, and delete Secrets, Containers, and Orders (P1, P2 & P3).
- `C14` 0: Acceptance criterion partly met: All action-triggering UI elements (Create, Edit, Delete, etc.) are gated using canUser(...) against the cor
- `C15` 0: Acceptance criterion partly met: Comprehensive error handling provides user-friendly feedback for Barbican errors.
- `C16` 0: Acceptance criterion partly met: All UI components follow the Aurora design system.
- `C17` 0: Acceptance criterion unmet: Complete testing coverage (unit, integration, E2E) is achieved.

## Acceptance grading (for the summary)

- partly met: tRPC BFF is implemented with complete Zod schema validation for Secrets, Containers, and Orders.
- met: A single "Key Manager" entry is added to the Side Navigation under the Authorization group.
- met: The Key Manager page exposes three tabs: Secrets, Containers, Orders.
- partly met: Each tab renders its own overview list with the columns specified in the UI Specification.
- partly met: Users can list, view, create, update, and delete Secrets, Containers, and Orders (P1, P2 & P3).
- met: Detail views are provided for each resource type (slide-out panel or sub-route).
- partly met: All action-triggering UI elements (Create, Edit, Delete, etc.) are gated using canUser(...) against the corresponding key-manager:* policy rules and are hidden/disabled for unauthorized users.
- partly met: Comprehensive error handling provides user-friendly feedback for Barbican errors.
- partly met: All UI components follow the Aurora design system.
- unmet: Complete testing coverage (unit, integration, E2E) is achieved.

## Earlier findings (for `earlier`)

The `earlier-findings` agent checked each of them at the new head; its status, note and evidence are below and already in the template. Keep the statuses — change one only if another agent's result shows it wrong, and say why in the note — and reword a note only for the reader. Don't open the code yourself. In a note, name earlier findings by number (`CR2`), this Update's own by `[[ref:<id>]]`. render.py refuses a list with one left out.

- CR1 🟠 Major — `getSecretPayload` sends the default `Accept: application/json`, so Barbican answers 406 for most secrets — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`
  - **fixed** — getSecretPayload now sends Accept: application/octet-stream. _(evidence: git show 64c47a99:keyManagerRouter.ts lines 98-104: headers: { Accept: "application/octet-stream" }, debug: false)_
- CR2 🟡 Moderate — Create modals mutate without validation; Bit Length is sent as `NaN` when empty — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:52`
  - **fixed** — Order modal now validates algorithm and bit length (positive integer) and disables Create; secret/container modals have only optional fields. _(evidence: OrderModals.tsx 42-55: bitLengthError = !Number.isInteger(parsedBitLength) || parsedBitLength <= 0 ...; handleConfirm returns if !isValid; disableConfirmButton={... || !isValid})_
- CR3 🟡 Moderate — Create and delete of secrets, containers and orders show no confirming toast — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:35`
  - **open** — Still no success toast on create or delete of secrets, containers or orders. _(evidence: git grep -n -i toast 64c47a99 -- packages/aurora/src/client/routes returned no matches; mutation onSuccess only invalidates and closes (SecretModals.tsx 35-40, 118-123))_
- CR4 🟡 Moderate — Reveal Payload and the detail views ignore `key-manager:secrets:payload` / `get` permissions — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89`
  - **partly** — Reveal Payload is now gated by key-manager:secrets:payload; detail views still do not check the :get permissions. _(evidence: SecretDetailsView.tsx 21-22 useKeyManagerPermissions(projectId, ["key-manager:secrets:payload"]); no :get check there; grep permission in ContainerDetailsView.tsx returned nothing)_
- CR5 🟡 Moderate — Search inputs navigate on every keystroke, with no local state or debounce — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:109`
  - **open** — SearchInput still calls onSearchChange (a navigate) on every onInput keystroke, with no local state or debounce. _(evidence: SecretsList.tsx 111-117: value={search} onInput={(e) => onSearchChange(...)}; secrets/index.tsx 32-38 handleSearch calls navigate)_
- CR6 🟡 Moderate — `deleteContainerSecret` calls an undocumented `DELETE /v1/containers/{id}/secrets/{name}` — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:252`
  - **fixed** — deleteContainerSecret (and addContainerSecret) were removed from the router. _(evidence: git grep -E 'addContainerSecret|deleteContainerSecret' 64c47a99 -- packages: no matches; router ends with deleteOrder)_
- CR7 🟡 Moderate — Container `secret_refs[].name` is required `z.string()`, but Barbican allows unnamed refs — `packages/aurora/src/server/KeyManager/types/keyManager.ts:25`
  - **fixed** — secret_refs[].name is now nullable. _(evidence: keyManager.ts line 25: secret_refs: z.array(z.object({ name: z.string().nullable(), secret_ref: z.string() })))_
- CR8 🟡 Moderate — Deleting the last row on the last page leaves an empty table with no pagination — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:126`
  - **fixed** — An effect steps back one page when a page after the first comes back empty. _(evidence: SecretsList.tsx 70-75: if (!isLoading && !isError && page > 1 && (data?.secrets.length ?? 0) === 0) onPageChange(page - 1))_
- CR9 🟡 Moderate — Key Manager nav entry and route ignore `enabledServices` / `deniedServices` — `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`
  - **partly** — Nav entry now honours enabledServices/deniedServices via isEnabled; the key-manager route beforeLoad still only checks the service catalog. _(evidence: buildNavSections.ts 154: serviceIndex["key-manager"]?.["barbican"] && isEnabled("key-manager"); key-manager.tsx 40-54 beforeLoad checks only getServiceIndex)_
- CR10 🟡 Moderate — `listOrders` sends undocumented `sort_key`/`sort_dir`; the Orders sort control does nothing — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:271`
  - **open** — listOrders still sends sort_key/sort_dir and the Orders list still renders the sort control. _(evidence: keyManagerRouter.ts 236-240 params.set("sort_key"...)/params.set("sort_dir"...); OrdersList.tsx 19-83 Select + SortButton; test line 473 asserts the split)_
- P1 — — Published package code changed without a `.changeset/*.md` — PR files
  - **open** — No changeset in the PR. _(evidence: context.json changeset: {'files': [], 'bumps': [], 'missing': True})_
- I1 🟢 Low — Permission props are named `canDelete` instead of `can<Verb><Noun>` — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:15`
  - **fixed** — Prop renamed to canDeleteSecret. _(evidence: SecretTableRow.tsx 18: canDeleteSecret: boolean)_
- I2 🟢 Low — Row `PopupMenu` has no `PopupMenuToggle` with a labelled `moreVert` button — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:35`
  - **fixed** — Row menu now has PopupMenuToggle with a titled moreVert button. _(evidence: SecretTableRow.tsx 39-41: <PopupMenuToggle as="div"><Button icon="moreVert" title={t`Secret actions`} />)_
- I3 🟢 Low — Row menu items `Show Details` / `Delete` lack the entity name and a separator before Delete — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:38`
  - **partly** — Separator before Delete added; labels are still bare Show Details / Delete without the entity name. _(evidence: SecretTableRow.tsx 43-47: <PopupMenuItem label={t`Show Details`} onClick/> <PopupMenuSectionSeparator /> <PopupMenuItem label={t`Delete`} onClick/>)_
- I4 🟢 Low — Delete modals put the name/ID in the title and use a bare `Delete` confirm label — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:129`
  - **open** — Delete modal still puts the name in the title and uses a bare Delete confirm label. _(evidence: SecretModals.tsx 129 title={t`Delete Secret "${secretName}"`}; 132 t`Delete`)_
- I5 🟢 Low — Modals disable Cancel but not the close-X while a mutation is pending — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:136`
  - **open** — Only Cancel is disabled while pending; the close-X is not. _(evidence: SecretModals.tsx 135-136: disableConfirmButton / disableCancelButton only)_
- I6 🟢 Low — Create modals use `useState` without react-form, `autoFocus` or disabled inputs in flight — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:30`
  - **open** — Create modals still use plain useState, no autoFocus, inputs not disabled in flight. _(evidence: ContainerModals.tsx 30-33 useState; SecretModals.tsx 31-33; git grep -E 'autoFocus|useForm' under authorization: no matches)_
- I7 🟢 Low — Sort uses raw `Select` + `SortButton` instead of `SortInput`; toolbar uses `distribution="end"` — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:93`
  - **open** — Still raw Select + SortButton and distribution="end" toolbar. _(evidence: SecretsList.tsx 90-100 Select/SortButton; 110 <Stack distribution="end" ...>)_
- I8 🟢 Low — 403 on list pages is an inline warning `Message` with hard-coded English — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:72`
  - **open** — 403 on list pages is still an inline warning Message with hard-coded English. _(evidence: SecretsList.tsx 79: <Message variant="warning">You do not have permission to view secrets.</Message>)_
- I9 🟢 Low — Detail routes fetch in the component (twice) instead of in the route `loader` — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/$containerId.tsx:19`
  - **open** — Detail routes still fetch in the component, and the view fetches again. _(evidence: secrets/$secretId.tsx 19 getSecret.useQuery in the page; SecretDetailsView.tsx 24-32 same query again; no loader)_
- I10 🟢 Low — Ad-hoc spacing/styling classes (`my-6`, `mt-4`, `p-3`, `opacity-60`) outside the approved lists — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:79`
  - **open** — Ad-hoc classes still present. _(evidence: SecretDetailsView.tsx 85 className="my-6"; 104 "text-sm opacity-60"; 105 "... p-3 text-xs"; key-manager.tsx 104 "mt-4"; SecretTableRow.tsx 30 "text-xs opacity-60")_
- I11 🟢 Low — Raw `<div>`, `<p>`, `<pre>` used where Juno components exist — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx:104`
  - **open** — Raw div/p/pre still used. _(evidence: key-manager.tsx 91,104 <div>; SecretDetailsView.tsx 95 <div>, 104 <p>, 105 <pre>; SecretModals.tsx 140 <p>)_
- I12 🟢 Low — Generic names: `usePermissions`, bundled `*Modals.tsx`, `utils.ts`, `constants.ts` — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:21`
  - **partly** — usePermissions renamed to useKeyManagerPermissions; bundled *Modals.tsx, utils.ts and constants.ts remain. _(evidence: git ls-tree: key-manager/-components/useKeyManagerPermissions.ts, -components/utils.ts, secrets/-components/SecretModals.tsx, constants.ts)_
- I13 🟢 Low — Empty state suggests creating even when a search returned no results — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:59`
  - **open** — Empty state still says to create a secret even when a search returned nothing. _(evidence: SecretListContainer.tsx 56-60: title No Secrets Found, body 'There are no secrets in this project. Create one to get started.'; no search prop)_
- I14 🟢 Low — Error states show the raw `error.message` as title with no body or retry — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:33`
  - **open** — Error state still shows raw error.message as title, no body or retry. _(evidence: SecretListContainer.tsx 33: <Status status="error" title={error?.message ?? t`Failed to Load Secrets`} />)_
- I15 🟢 Low — `getSecretPayload` decodes binary payloads with `res.text()` — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:103`
  - **open** — Payload is still decoded with res.text(), so binary secrets are corrupted. _(evidence: keyManagerRouter.ts 110: const text = await res.text())_
- I16 🟢 Low — Secret plaintext can land in server logs via signal-openstack's debug body preview — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`
  - **fixed** — Payload request now passes debug:false. _(evidence: keyManagerRouter.ts 99 comment and 103: debug: false)_
- I17 🟢 Low — Orders list lacks the Name column from the epic's UI spec — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/constants.ts:1`
  - **open** — Orders columns are still ID, Status, Type; no Name column. _(evidence: orders/-components/constants.ts: ORDERS_COLUMNS = ["ID", "Status", "Type", ""])_
- I18 🟢 Low — No update UI: `updateSecret`, `addContainerSecret`, `deleteContainerSecret` have no client caller — PR files
  - **partly** — addContainerSecret and deleteContainerSecret removed; updateSecret remains with no client caller. _(evidence: git grep updateSecret 64c47a99 -- packages (non-test): only keyManagerRouter.ts:138)_
- I19 🟢 Low — `mapKmError` drops Barbican's error body; users see generic `Key Manager … failed` — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:52`
  - **open** — mapKmError still drops Barbican's error body. _(evidence: keyManagerRouter.ts 50-54: message: `Key Manager ${operation} failed`, cause: error)_
- I20 🟢 Low — No tests for lists with permissions, modals, detail views, nav or layout guard; no E2E — PR files
  - **partly** — Tests were added for secret/container/order list containers, table rows, router and schemas; no tests for modals, detail views, nav entry or layout guard, and no E2E. _(evidence: delta adds *ListContainer.test.tsx and *TableRow.test.tsx; no Modals/DetailsView tests; git grep -c key-manager in buildNavSections.test.ts and e2e: no matches)_
- I21 ⚪ Trivial — Import order and `../../` relative imports break B.13 — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:14`
  - **open** — Import order and ../../ relative imports unchanged. _(evidence: SecretsList.tsx 13-17: @/ import, then ../../-components/..., ./..., then type import; SecretTableRow.tsx 12 ../../-components/utils)_

## PR description vs code (Process items)

These go into the report as Process items as written — you can't drop one. To reword one for the reader, put `"process_overrides": {"<id>": {"issue": "…", "explanation": "…", "fix": "…"}}` in texts.json; name one in a text as `[[ref:<id>]]`.

- `desc-1` — The description claims what the code doesn't do · PR body: The description lists add/remove secret refs for containers; no procedure implements them
  - Quote: "(list/get/create/delete, add/remove secret refs)"
  - The description says the containers API covers adding and removing secret refs, but `keyManagerRouter` has only `listContainers`, `getContainer`, `createContainer` and `deleteContainer` for containers.
  - _Fix:_ Drop "add/remove secret refs" from the description, or add the two procedures if they belong in this PR.

## texts.json shape

Optional: `fixes` — exact replacements after the fact-check, copied from `out/factcheck.json`: `[{"field": "overview.how", "old": "…", "new": "…"}]` (fields as in findings.json: overview.what/how/affects, qa.core_path[i], qa.edge_cases[i], findings.<id>.issue/title/explanation/fix); `process` / `process_overrides` as in findings-format.md.

```json
{
 "earlier": {
  "CR1": {
   "status": "fixed",
   "note": "getSecretPayload now sends Accept: application/octet-stream."
  },
  "CR2": {
   "status": "fixed",
   "note": "Order modal now validates algorithm and bit length (positive integer) and disables Create; secret/container modals have only optional fields."
  },
  "CR3": {
   "status": "open",
   "note": "Still no success toast on create or delete of secrets, containers or orders."
  },
  "CR4": {
   "status": "partly",
   "note": "Reveal Payload is now gated by key-manager:secrets:payload; detail views still do not check the :get permissions."
  },
  "CR5": {
   "status": "open",
   "note": "SearchInput still calls onSearchChange (a navigate) on every onInput keystroke, with no local state or debounce."
  },
  "CR6": {
   "status": "fixed",
   "note": "deleteContainerSecret (and addContainerSecret) were removed from the router."
  },
  "CR7": {
   "status": "fixed",
   "note": "secret_refs[].name is now nullable."
  },
  "CR8": {
   "status": "fixed",
   "note": "An effect steps back one page when a page after the first comes back empty."
  },
  "CR9": {
   "status": "partly",
   "note": "Nav entry now honours enabledServices/deniedServices via isEnabled; the key-manager route beforeLoad still only checks the service catalog."
  },
  "CR10": {
   "status": "open",
   "note": "listOrders still sends sort_key/sort_dir and the Orders list still renders the sort control."
  },
  "P1": {
   "status": "open",
   "note": "No changeset in the PR."
  },
  "I1": {
   "status": "fixed",
   "note": "Prop renamed to canDeleteSecret."
  },
  "I2": {
   "status": "fixed",
   "note": "Row menu now has PopupMenuToggle with a titled moreVert button."
  },
  "I3": {
   "status": "partly",
   "note": "Separator before Delete added; labels are still bare Show Details / Delete without the entity name."
  },
  "I4": {
   "status": "open",
   "note": "Delete modal still puts the name in the title and uses a bare Delete confirm label."
  },
  "I5": {
   "status": "open",
   "note": "Only Cancel is disabled while pending; the close-X is not."
  },
  "I6": {
   "status": "open",
   "note": "Create modals still use plain useState, no autoFocus, inputs not disabled in flight."
  },
  "I7": {
   "status": "open",
   "note": "Still raw Select + SortButton and distribution=\"end\" toolbar."
  },
  "I8": {
   "status": "open",
   "note": "403 on list pages is still an inline warning Message with hard-coded English."
  },
  "I9": {
   "status": "open",
   "note": "Detail routes still fetch in the component, and the view fetches again."
  },
  "I10": {
   "status": "open",
   "note": "Ad-hoc classes still present."
  },
  "I11": {
   "status": "open",
   "note": "Raw div/p/pre still used."
  },
  "I12": {
   "status": "partly",
   "note": "usePermissions renamed to useKeyManagerPermissions; bundled *Modals.tsx, utils.ts and constants.ts remain."
  },
  "I13": {
   "status": "open",
   "note": "Empty state still says to create a secret even when a search returned nothing."
  },
  "I14": {
   "status": "open",
   "note": "Error state still shows raw error.message as title, no body or retry."
  },
  "I15": {
   "status": "open",
   "note": "Payload is still decoded with res.text(), so binary secrets are corrupted."
  },
  "I16": {
   "status": "fixed",
   "note": "Payload request now passes debug:false."
  },
  "I17": {
   "status": "open",
   "note": "Orders columns are still ID, Status, Type; no Name column."
  },
  "I18": {
   "status": "partly",
   "note": "addContainerSecret and deleteContainerSecret removed; updateSecret remains with no client caller."
  },
  "I19": {
   "status": "open",
   "note": "mapKmError still drops Barbican's error body."
  },
  "I20": {
   "status": "partly",
   "note": "Tests were added for secret/container/order list containers, table rows, router and schemas; no tests for modals, detail views, nav entry or layout guard, and no E2E."
  },
  "I21": {
   "status": "open",
   "note": "Import order and ../../ relative imports unchanged."
  }
 },
 "confidence": "High | Medium | Low",
 "findings": {
  "c8": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c1": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c3": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c11": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  }
 },
 "merge": {},
 "provenance_extra": []
}
```
