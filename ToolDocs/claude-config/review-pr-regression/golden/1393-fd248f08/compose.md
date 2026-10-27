# Compose findings — review-and-comment-pr

Write `texts.json` in the run folder (shape at the end), then run
`python3 .claude/skills/review-and-comment-pr/scripts/assemble.py --run <run folder> --texts`
and `render.py`. Scores, severity, category and location are the scorers' — don't change them.
Text rules, code placeholders and `[[ref:<id>]]` are in `references/findings-format.md`.
A finding's precedent (existing pattern / deferred) is the scorer's tag — render.py shows it; don't repeat it in the explanation.

## Look alike — same problem?

If a pair below is one problem, put `"merge": {"<drop id>": "<keep id>"}` in texts.json and give the kept one the other's evidence; otherwise leave both.

- `c3` and `c4` — shares `Delete`
- `c7` and `c17` — shares `useState`

## Findings

### `c45` — Major · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98` · score 75
- **Claim** (finder-f): getSecretPayload does not send an Accept header; the reference says the Accept header must be set to one of the secret's content_types for GET /payload. signal-openstack adds no Accept header, so the call can return 406 (mapped to INTERNAL_SERVER_ERROR) or the wrong content type. Also mapKmError has no mapping for 406/415, which the reference lists for these endpoints.
- **Scorer:** Verified: getSecretPayload calls km.get on the secret payload path with no headers, and the session default headers (context.ts:116) send Accept: application/json, whereas the reference requires Accept to be one of the secret's content_types; for text/plain or binary secrets Barbican answers 406, which mapKmError (lines 43-49, no 406 entry) turns into INTERNAL_SERVER_ERROR, so Reveal Payload fails for typical secrets. Major since the core reveal feature breaks with no in-app workaround. C31 is the same problem.
- **Evidence:**

Code: `km.get(`v1/secrets/${encodeURIComponent(input.secretId)}/payload`)` with no options/headers; grep of packages/signal-openstack/src/client.ts shows only a Content-Type default, no Accept. Reference (secrets.rst 'GET /v1/secrets/{uuid}/payload'): 'When making a request for a secret's payload, you must set the accept header to one of the values listed in the ``content_types`` attribute of a secret's metadata.' Status codes: '406 | Not Acceptable'; POST /v1/secrets lists '415 | Unsupported media-type'. mapKmError codeMap covers only 400/401/403/404/409 (lines 43-49).

- **Same problem, also from finder-d:** getSecretPayload (and other calls) use the session default Accept: application/json; Barbican's payload endpoint serves raw secret content and can return 406 for non-JSON payloads. The response is also read with res.text() with no Accept override.

context.ts:116 sets default Accept: application/json; keyManagerRouter.ts:98 km.get(`v1/secrets/${id}/payload`) passes no headers.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c6` — Moderate · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:52` · score 75
- **Claim** (finder-a): The create modals mutate with no form validation and no inline errors: the confirm button is only disabled while pending. Bit Length is parsed with parseInt (NaN on empty), Algorithm may be empty, and fields are not marked required. Validation errors on the server show only as a Message at form top.
- **Scorer:** Verified: line 52 `bit_length: parseInt(bitLength, 10)` (NaN on empty), line 57 `disableConfirmButton={createMutation.isPending}` only, no validator, no inline errors, no required marks. Violates Quick Reject 'any form that mutates without validation' and B.5 'keep the primary/confirm button disabled while any required field is empty or any field fails validation'. Moderate: bad input goes to the server and shows only as a top Message.
- **Review discussion:** Copilot thread on OrderModals.tsx:52 (bit length validation).
- **Evidence:**

B.11 Reject: "any form that mutates without validation"; B.5: "keep the primary/confirm button disabled while any required field is empty or any field fails validation". Code: `meta: { algorithm, bit_length: parseInt(bitLength, 10) }`, `disableConfirmButton={createMutation.isPending}`; no @tanstack/react-form / zod used. Secret and container create modals use useState with no validator at all.

- **Same problem, also from finder-d:** Create Order modal does not validate Bit Length: parseInt of empty or invalid input yields NaN, zero/negative values are accepted, and Create stays enabled; no inline error.

Line 52 meta: { algorithm, bit_length: parseInt(bitLength, 10) }; disableConfirmButton only on isPending (line 57); no server-side check (meta is unrestricted).


### `c8` — Moderate · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:35` · score 75
- **Claim** (finder-a): Create/delete success is silent: no toast is shown for create or delete of secrets, containers or orders; the modal just closes. The standard requires a confirming toast delegated to a `*ToastNotifications` helper for CRUD actions.
- **Scorer:** Verified: grep for 'toast' across the key-manager folder at headRefOid finds nothing. B.16 table says CRUD action confirmed -> toast, and B.10 requires a *ToastNotifications helper; on success the modals only invalidate and close, so users get no confirmation of create or delete.
- **Precedent:** Network plugins ship *ToastNotifications files.
- **Evidence:**

B.16 table: "CRUD action confirmed (create, delete, update) | toast (transient)"; B.10: "All toast messages must be extracted to a dedicated <Resource>ToastNotifications.tsx"; B.11: "(modal) close and show a confirming toast". grep of the PR diff finds no `toast` and no *ToastNotifications file. onSuccess only calls invalidate()/onClose().


### `c11` — Moderate · Security · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx | <Button variant="subdued" onClick={handleRevealPayload} disabled={payloadFetching}>` · score 75
- **Claim** (finder-a): Reveal Payload button, secret detail and the other detail routes do not check any permission (`key-manager:secrets:payload` / `get`); the control is rendered functional before permissions are known (not fail-closed).
- **Scorer:** SecretDetailsView.tsx:89 renders the Reveal Payload button unconditionally; the file never imports usePermissions, and key-manager:secrets:payload is defined but unused (only the three List components call usePermissions). Quick Reject: 'UI control shown before permissions are resolved (not fail-closed)'. Moderate rather than Major because Barbican ACLs still reject the fetch server-side.
- **Review discussion:** Copilot thread r4360388886 (CRITICAL).
- **Evidence:**

Quick Reject: "UI control shown before permissions are resolved (not fail-closed)"; B.7/B.8: "Never optimistically show actions before permissions resolve." Code: `<Button variant="subdued" onClick={handleRevealPayload} disabled={payloadFetching}>`; usePermissions is never imported in the *DetailsView files. The `payload` permission is defined in usePermissions.ts:6 and the policy but unused.

- **Same problem, also from finder-d:** Reveal Payload button is rendered and fetches secret material without checking the separately defined key-manager:secrets:payload permission (the key exists in permissionRouter but is never used client-side). Users without the permission see a working control; not fail-closed.

git grep at head: SecretDetailsView.tsx has no permission lookup/usePermissions; permissionRouter.ts:6 defines "key-manager:secrets:payload". copilot-instructions B.7/B.8: permissions default false while loading, reject controls shown before permissions confirmed.

- **Same problem, also from finder-g:** The Reveal Payload button (and the detail views generally) is not gated by the `key-manager:secrets:payload` permission, which is mapped server-side but never read by any client code. A user without payload rights still sees the button and the server procedure fetches the plaintext secret; only Barbican's own ACLs stop it.

git grep of usePermissions/permissions[ under key-manager/ (at head) shows usage only in ContainersList, OrdersList and SecretsList (list/create/delete); SecretDetailsView, ContainerDetailsView and OrderDetailsView have none. `key-manager:secrets:payload` appears only in usePermissions.ts type and permissionRouter mappings.


### `c13` — Moderate · Performance · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx | onInput={(e) => onSearchChange((e.target as HTMLInputElement).value)}` · score 75
- **Claim** (finder-a): Search input navigates on every keystroke (`onInput` -> navigate) with no local mirror state / debounce, producing a router navigation and a server request per character.
- **Scorer:** SecretsList.tsx:109 and ContainersList.tsx:74 call onSearchChange on every input event, and handleSearch navigates and so refetches per keystroke, with no local mirror state or debounce (B.9 violation). The flavors List at base debounces 500ms with local state, showing the expected pattern.
- **Evidence:**

B.9: "Use a local mirror state for debounced search inputs; sync back on external navigation via useEffect." Code: `onInput={(e) => onSearchChange((e.target as HTMLInputElement).value)}` where onSearchChange calls `navigate({ etc search: { search: value || undefined  etc}})`. Same ContainersList.tsx:74.


### `c24` — Moderate · Performance · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx | onInput={(e) => onSearchChange((e.target as HTMLInputElement).value)}` · score 75
- **Claim** (finder-b): SearchInput wires both onSearch and onInput to onSearchChange, and onSearchChange navigates, so every keystroke changes the URL, resets page and fires a new listSecrets request (and likely adds a history entry per character). Typing a name causes request churn and a polluted back-history.
- **Scorer:** Verified: line 109 calls onSearchChange on every input event, and handleSearch in secrets/index.tsx (line 32) calls navigate() with no debounce and no replace. Each keystroke changes the URL, adds a history entry and triggers a new listSecrets query. The flavors List debounces by 500ms (it does this correctly), so duplicate requests are avoidable.
- **Evidence:**

SecretsList.tsx: SearchInput has onSearch, onClear and onInput all calling onSearchChange; handleSearch in secrets/index.tsx calls navigate({search:{search:value,...}}) with no debounce or replace. Same pattern likely in containers list.


### `c33` — Moderate · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:252` · score 75
- **Claim** (finder-d): deleteContainerSecret DELETEs v1/containers/{id}/secrets/{secretName}; Barbican's removal endpoint is DELETE /v1/containers/{uuid}/secrets with name and secret_ref in a JSON body, so association removal will fail.
- **Scorer:** Line 252 issues DELETE v1/containers/{id}/secrets/{secretName}; the Barbican containers reference documents only DELETE /v1/containers/{container_uuid}/secrets with a JSON body {name, secret_ref} (secret_ref required, 400 'Missing secret_ref'), and the input schema has no secret_ref. The path-segment form is undocumented so the call will fail. Moderate rather than Major because no client component calls deleteContainerSecret yet. C42 describes the same problem.
- **Review discussion:** Copilot inline r4360389656, no replies, still applies.
- **Evidence:**

Line 252: .del(`v1/containers/${containerId}/secrets/${secretName}`) with input only containerId+secretName; the test asserts the same URL.

- **Same problem, also from finder-f:** deleteContainerSecret calls DELETE /v1/containers/{id}/secrets/{secretName}; Barbican documents removal as DELETE /v1/containers/{container_uuid}/secrets with a JSON body {name, secret_ref}. The path-segment form is not in the reference, so removing a secret from a container likely fails (404/405) and the UI action is broken.

Code at fd248f08: `.del(`v1/containers/${encodeURIComponent(input.containerId)}/secrets/${encodeURIComponent(input.secretName)}`)`; input has only containerId and secretName, no secret_ref. Reference (https://docs.openstack.org/barbican/latest/api/reference/containers.html, source https://raw.githubusercontent.com/openstack/barbican/master/doc/source/api/reference/containers.rst, section 'DELETE /v1/containers/{container_uuid}/secrets'): 'Remove a secret from a container.  This is only supported on generic containers.' Request attributes: 'secret_ref | uri | (required) Full URI reference to an existing secret.' Request: 'DELETE /v1/containers/{container_uuid}/secrets ... Content: { "name": "private key", "secret_ref": "https://{barbican_host}/v1/secrets/{secret_uuid}" }'; 400 'Missing secret_ref'. No `/secrets/{name}` path appears in that file.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c34` — Moderate · Bug · `packages/aurora/src/server/KeyManager/types/keyManager.ts:25` · score 50
- **Claim** (finder-d): Container secret_refs schema requires name: string, but Barbican may return name: null for unnamed references; parseOrThrow would then reject the whole container/list response.
- **Scorer:** secret_refs items use name: z.string() while the reference marks name as optional for container secret refs, and sibling name fields are nullable; an unnamed ref returning null would make parseOrThrow reject the whole container/list response. Rare in practice, hence 50.
- **Review discussion:** Copilot inline r4360389713, no replies, still applies.
- **Evidence:**

Line 25: secret_refs: z.array(z.object({ name: z.string(), secret_ref: z.string() })), while sibling name fields use .nullable().

- Bug: add its scenario to `edge_cases` in texts.json.

### `c39` — Moderate · Bug · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx | {totalPages > 1 && (` · score 50
- **Claim** (finder-d): After deleting the last item on the final page the URL page stays beyond the new total; pagination is hidden (totalPages <= 1) and the table is empty with no way back. Same in Secrets, Containers and Orders lists.
- **Scorer:** Verified: offset is (page-1)*PAGE_SIZE (line 62) and totalPages comes from data.total (line 75), with no clamp. If the last row of the last page is deleted, page stays above totalPages, Pagination is hidden (line 126) and the table is empty with no in-UI way back. Kept at 50 because PAGE_SIZE is 50, so it needs more than 50 items and is rare in practice.
- **Review discussion:** Copilot inline r4360389532, r4360389254 (ContainersList:91), r4360389387 (OrdersList:97); no replies.
- **Evidence:**

SecretsList.tsx:62 offset=(page-1)*PAGE_SIZE, line 75 totalPages from data.total, line 126 {totalPages > 1 && Pagination}; no clamp/reset of page on delete or total shrink.

- **Same problem, also from finder-a:** Page-state recovery after deletion: list URL `page` is not clamped when the last row of the last page is deleted, leaving an empty table with no pagination.

B.9 (URL state must stay consistent) ; Code: `{totalPages > 1 && (<Pagination  etc/>)}` with `page` coming from the URL and no clamp after invalidate.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c41` — Moderate · Bug · `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts | ...(serviceIndex["key-manager"]?.["barbican"]` · score 75
- **Claim** (finder-e): The new Key Manager nav item is gated only on the service catalog and skips isEnabled("key-manager"). The comment above isEnabled says deny always wins and a service can be hidden by deniedServices alone, but enabledServices/deniedServices have no effect on Key Manager, so an operator cannot hide it or exclude it from an allowlist.
- **Scorer:** Verified at fd248f08: line 154 gates the Key Manager entry only on the catalog, while images, flavors, securitygroups, floatingips, routers, containers and ceph-containers all use `&& isEnabled(...)` (lines 36-119) and extensions check enabledServices/deniedServices. An operator cannot hide Key Manager via deniedServices or leave it out of an allowlist; a broken project rule with a visible effect, so Moderate.
- **Precedent:** Extensions at lines 176-178 check both enabledServices and deniedServices.
- **Evidence:**

Comment at lines 29-31 at fd248f08: "Deny always wins and applies even without an allow/enabled list, so a service can be hidden by deniedServices alone ... see resolveServiceVisibility." Every other built-in item uses `&& isEnabled(...)` (images, flavors, securitygroups, floatingips, routers, containers, ceph-containers). The new entry uses only `serviceIndex["key-manager"]?.["barbican"]`. The route beforeLoad in key-manager.tsx also checks only the catalog, so a denied service stays reachable by URL.

- **Same problem, also from finder-a:** The Authorization nav entry does not honour service-visibility configuration (`isEnabled` / enabledServices / deniedServices) like the other in-core entries.

Code: ` etc(serviceIndex["key-manager"]?.["barbican"] ? [{ etc}] : [])` with no isEnabled call. Part A/CLAUDE.md: `enabledServices` whitelists which services show in the nav.

- **Same problem, also from finder-c:** The new Authorization > Key Manager nav entry is gated only on the catalog (serviceIndex["key-manager"]["barbican"]) and skips isEnabled(...). Since #1370, every built-in item and every extension is filtered by enabledServices/deniedServices, so a consumer cannot hide Key Manager via appConfig deny list or enabledServices allowlist (the allowlist would still show it).

At base c65b36d0, buildNavSections.ts lines 29-33 define isEnabled with the comment 'Deny always wins and applies even without an allow/enabled list'; images, flavors, securitygroups, floatingips, routers, containers and ceph-containers all use `&& isEnabled("<key>")`, and extensions check enabledServices/deniedServices (lines 154-155, added in b4b47df6 #1370). The PR diff for this file adds the key-manager item with no isEnabled call. The PR does not touch README 'Service key reference' either.

- **Same problem, also from finder-d:** Key Manager nav entry ignores isEnabled, so enabledServices/deniedServices cannot hide it, unlike the other entries.

Line 154: serviceIndex["key-manager"]?.["barbican"] ? ... with no && isEnabled(...); other entries at lines 36,46,60,71,82,97,119 use isEnabled.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c44` — Moderate · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:271` · score 75
- **Claim** (finder-f): listOrders translates `sort` into sort_key/sort_dir query params, which the Orders list does not document (it documents only offset and limit; the `sort` param of secrets uses `key:dir` in one `sort` param, not sort_key/sort_dir). The sort selector on the orders page therefore has no documented effect.
- **Scorer:** Verified: listOrders sends sort_key/sort_dir (lines 269-273); the Barbican orders reference documents only offset and limit, so the Sort by and direction controls in OrdersList.tsx (lines 67-76) have no documented effect and likely change nothing. Per the evidence rule the code does what the reference does not support; Moderate because the control is visible but misleading, not data-losing. C26 is the same problem.
- **Evidence:**

Code: `const [sortKey, sortDir] = input.sort.split(":")` then `params.set("sort_key", sortKey)` / `params.set("sort_dir", sortDir)`. Reference (https://docs.openstack.org/barbican/latest/api/reference/orders.html, orders.rst 'GET /v1/orders' Parameters): only 'offset' and 'limit | The maximum number of records to return (up to 100). (Default is 10)'. Secrets.rst 'Sorting': 'The value of the ``sort`` parameter is a comma-separated list of sort keys... Each sort key may also include a direction... ``:asc`` / ``:desc``' - sort_key/sort_dir are not documented anywhere in the secrets/containers/orders reference files. UI offers only SORT_FIELDS = [{ value: "created" }] (OrdersList.tsx:19).

- **Same problem, also from finder-b:** listOrders translates `sort` into sort_key/sort_dir query params, but Barbican's orders list API only supports offset and limit, so the orders sort control is likely a no-op.

keyManagerRouter.ts lines 269-273 set sort_key/sort_dir; Barbican API reference for GET /v1/orders lists only limit and offset (from memory, not verified online).

- Bug: add its scenario to `edge_cases` in texts.json.

### `c1` — Low · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:15` · score 75
- **Claim** (finder-a): Permission props are named `canDelete` instead of `can<Verb><Noun>` (canDeleteSecret / canDeleteContainer / canDeleteOrder), in the row and list-container props of all three resources.
- **Scorer:** SecretTableRow.tsx:15 has `canDelete: boolean` (same in Container/Order rows and ListContainers); Quick Reject 'Permission prop not named can<Verb><Noun>' and B.8 require canDeleteSecret etc. Verified violation, naming only so Low.
- **Precedent:** Network plugin uses `canDeleteRule` (SecurityGroupRulesTable).
- **Review discussion:** Copilot raised it on all six files (threads r4360388743, r4360388949, r4360389203, r4360389452, r4360389872, r4360389932).
- **Evidence:**

Quick Reject: "Permission prop not named `can<Verb><Noun>`"; B.8: "Boolean permission props must be named can<Verb><Noun> (e.g., canDeleteFlavor  etc)". Code: `canDelete: boolean`. Same in ContainerTableRow.tsx:15, OrderTableRow.tsx:15 and the three *ListContainer.tsx:12.

- **Same problem, also from finder-d:** Boolean permission props are named canDelete instead of can<Verb><Noun> (canDeleteContainer/canDeleteSecret/canDeleteOrder), violating B.8.

canDelete in Secret/Container/Order TableRow (line 15), ListContainer (line 12) and passed from Lists; copilot-instructions line 329 requires can<Verb><Noun>.


### `c2` — Low · Accessibility · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:35` · score 75
- **Claim** (finder-a): Row action menus use `<PopupMenu>` without a `PopupMenuToggle` trigger, so the default toggle is used with no `<Button icon="moreVert" aria-label>`; the icon-only trigger has no accessible label.
- **Scorer:** SecretTableRow.tsx:35-36 renders `<PopupMenu><PopupMenuOptions>` with no PopupMenuToggle; Quick Reject 'PopupMenu without PopupMenuToggle as trigger' and B.14 are violated (same in Container/Order rows). Default toggle is used, so Low.
- **Precedent:** Network floating IP / security group views import PopupMenuToggle.
- **Review discussion:** Copilot thread r4360388832 (OrderTableRow).
- **Evidence:**

Quick Reject: "`PopupMenu` without `PopupMenuToggle` as trigger"; B.14: "Context menus must use <PopupMenuToggle as=\"div\"><Button icon=\"moreVert\" /></PopupMenuToggle>". Code: `<PopupMenu><PopupMenuOptions> etc`. Same in ContainerTableRow.tsx:34 and OrderTableRow.tsx:33.

- **Same problem, also from finder-d:** Row action PopupMenu has no PopupMenuToggle trigger (labelled more-actions button) and no PopupMenuSectionSeparator before destructive Delete, in the secret, container and order rows.

SecretTableRow.tsx:35-40 <PopupMenu><PopupMenuOptions> with Show Details and Delete only; imports lack PopupMenuToggle. copilot-instructions line 457 requires PopupMenuToggle as trigger.


### `c3` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:38` · score 75
- **Claim** (finder-a): Delete menu item is neither labelled with the entity nor separated by a divider from the other item (single-entity menu): labels are `Delete` / `Show Details` rather than `Delete Secret` / `Show Secret Details`, and there is no `PopupMenuSectionSeparator` before Delete.
- **Scorer:** SecretTableRow.tsx:37-38 has `Show Details` and `Delete` with no entity in labels and no PopupMenuSectionSeparator before Delete (separator is used elsewhere, e.g. flavors/$flavorId.tsx); violates B.18. Distinct from the missing toggle.
- **Review discussion:** Copilot r4360388832 mentions the separator.
- **Evidence:**

B.18: "Single-entity menus  etc: separate the Delete action from the rest with a divider." and "Include the referenced entity in labels". Code: `{canDelete && <PopupMenuItem label={t`Delete`}  etc/>}` directly after `Show Details`. Same in Container/Order rows (line 37/36).


### `c4` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:129` · score 50
- **Claim** (finder-a): Delete modals put the object name/ID in the title (`Delete Secret "${secretName}"`, `Delete Order "${orderId}"`) and the confirm label is a bare `Delete` / `Deleting...`; the standard says the object goes in the body and the confirm label should be verb + object type. The body doesn't name the entity at all (container/secret), and the order modal title shows a raw UUID.
- **Scorer:** SecretModals.tsx:129 title is `Delete Secret "${secretName}"`, body at :140 does not name the entity and the confirm label is bare `Delete`; contradicts B.5 (name in body, verb+object label). Not a Quick Reject item, wording only.
- **Evidence:**

B.5: "Put the object name in the body, not the title.  etc Reference the affected entity by name/identifier in the body"; "Confirm labels: prefer verb + object type: Delete Image". Code: title={t`Delete Secret "${secretName}"`}, body `This action cannot be undone. The secret will be permanently deleted.` Same at ContainerModals.tsx:109, OrderModals.tsx:125.


### `c5` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:136` · score 75
- **Claim** (finder-a): None of the six modals pass `disableCloseButton` while the mutation is pending, so the close-X stays active and the user can dismiss the modal mid-request, while Cancel is disabled (they must be disabled together).
- **Scorer:** Only `disableCancelButton={deleteMutation.isPending}` at SecretModals.tsx:136 (and :60), no disableCloseButton anywhere in the folder; Quick Reject 'Modal without disableCancelButton / disableCloseButton during async operations'. Other modals (DeleteFlavorModal.tsx:119) pass disableCloseButton. Close-X still active mid-request, so Low.
- **Evidence:**

Quick Reject: "Modal without `disableCancelButton` / `disableCloseButton` during async operations"; B.5: "disable close-X and Cancel together". Code has `disableCancelButton={deleteMutation.isPending}` only. Same in SecretModals.tsx:60, ContainerModals.tsx:50/116, OrderModals.tsx:58/132.


### `c7` — Low · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:30` · score 75
- **Claim** (finder-a): The create modals do not follow the form standard (state in `useState` instead of @tanstack/react-form + Zod, no `autoFocus` on the primary input, inputs are not `disabled` while the mutation is in flight, no `required` markers).
- **Scorer:** Verified: ContainerModals.tsx:30 uses `useState("")` for name; grep of key-manager finds no react-form and no autoFocus. B.11 wants react-form + Zod, autoFocus and disabled={isMutating} on inputs. Low: cosmetic or form-structure rule with little user-visible effect; validation itself is covered by C6.
- **Evidence:**

B.11: "Preferred: @tanstack/react-form with Zod schema validators", "`autoFocus` on the primary input. `disabled={isMutating}` on all inputs during in-flight mutations." Code: `const [name, setName] = useState("")`  etc TextInput has no autoFocus/disabled.


### `c9` — Low · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:93` · score 75
- **Claim** (finder-a): Row/list sort control is built from raw `Select` + `SortButton` instead of the required `SortInput` from `@/client/components/ListToolbar/SortInput`; Zone 1 is also `distribution="end"` rather than `"between"`.
- **Scorer:** Verified: SecretsList.tsx:93 and OrdersList.tsx:76 use raw Select + SortButton, with `distribution="end"` at SecretsList.tsx:81; B.1 requires SortInput from @/client/components/ListToolbar/SortInput (used by FloatingIpsList and RoutersList at base). Containers list has no sort control (ContainersList imports none). Low: visual and consistency only.
- **Precedent:** floatingips/-components/FloatingIpsList.tsx and routers/-components/RoutersList.tsx import SortInput.
- **Evidence:**

B.1 table: "Sort control | SortInput from @/client/components/ListToolbar/SortInput"; B.2: "Sort controls (SortInput) + primary action Button  etc distribution=\"between\"". Code uses `<Select label="Sort by"  etc>` + `<SortButton  etc/>` in `<Stack distribution="end"  etc className="jn:pb-2">`. Same in OrdersList.tsx:66. Containers list has no sort control at all although the PR body advertises sort for the lists.


### `c10` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:72` · score 75
- **Claim** (finder-a): The permission-denied state for the list pages is rendered inline as a non-page-level warning `Message` with hardcoded English and no `mb-4`, instead of a 403 page-level error with an info `Message`; the copy also differs from the recommended 403 text.
- **Scorer:** Verified: SecretsList.tsx:72, ContainersList.tsx:50 and OrdersList.tsx:55 render the 403 inline as `<Message variant="warning">` instead of a page-level info Message. This matches the Quick Reject item 'a 401/403 handled inline instead of via redirect / page-level info Message', and the severity precedent for it is Low.
- **Precedent:** Network lists use a Message for the same case ("You do not have permission to view security groups" in messages.po), so this may be accepted locally.
- **Evidence:**

B.6 Reject: "a 401/403 handled inline instead of via redirect / page-level info Message"; 403 row: "plus an info Message explaining lack of access". Code: `<Message variant="warning">You do not have permission to view secrets.</Message>`. Same ContainersList.tsx:50, OrdersList.tsx:55. B.3 requires `mb-4` on Message banners.


### `c12` — Low · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/$containerId.tsx | const { data: container } = trpcReact.keyManager.getContainer.useQuery({ project_id: projectId, containerId })` · score 50
- **Claim** (finder-a): Detail data is fetched in the component twice (route component and *DetailsView both call the same getX.useQuery) rather than in the route `loader`; the route has no loader, and the breadcrumb is set from a separately fetched copy.
- **Scorer:** Route has no loader; $containerId.tsx:19 and ContainerDetailsView both call the same getContainer.useQuery (same for secret/order), contrary to A.3. Same query key means React Query dedupes to one request, so no duplicate network call; hence Low, not the Moderate duplicate-fetch precedent.
- **Evidence:**

A.3: "Data critical for rendering a page must be fetched via the route's loader function rather than loading it inside the component body." and (task) data the loader already fetched is not fetched again. Code: `$containerId.tsx:19 trpcReact.keyManager.getContainer.useQuery( etc)` and `ContainerDetailsView.tsx:31 trpcReact.keyManager.getContainer.useQuery( etc)`. Same for $secretId.tsx:19 / SecretDetailsView.tsx:24 and $orderId.tsx:19 / OrderDetailsView.tsx:22. B.7 allows tRPC useQuery, so severity is a judgement call.


### `c14` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx | <Stack direction="vertical" gap="6" className="my-6">` · score 50 · precedent: existing (packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ActivateImagesModal.tsx:52)
- **Claim** (finder-a): Ad-hoc spacing and styling classes outside the approved lists: `my-6` on the detail Stack, `mt-4` wrapper, `p-3`/`rounded`/`max-h-48` and `text-xs opacity-60` on payload/ID text, `items-end pr-0`, `jn:min-w-40`; `opacity-60` is used instead of a `text-theme-light` token.
- **Scorer:** Verified: className="my-6" at SecretDetailsView.tsx:79, opacity-60 at :97 (instead of text-theme-light), and key-manager.tsx:104 mt-4, all outside the B.3/B.4 approved lists. Cosmetic, so Low.
- **Evidence:**

B.3: "Reject any use of ad-hoc mt-3, mb-5, px-6, etc. not listed above" (detail top offset is `mt-6`); B.4: "Muted / secondary text | text-theme-light". Code: `className="my-6"` (also ContainerDetailsView.tsx:62, OrderDetailsView.tsx:67), `<p className="text-sm opacity-60">` :97, `<pre className="bg-theme-background-lvl-2 max-h-48 overflow-auto rounded p-3 text-xs">` :98, key-manager.tsx:104 `className="mt-4"`, rows `text-xs opacity-60`.


### `c15` — Low · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx | <div className="mt-4">` · score 75 · precedent: existing (packages/aurora/src/client/routes/_auth/projects/$projectId/compute/images/-components/ActivateImagesModal.tsx:52)
- **Claim** (finder-a): Raw HTML elements are used where Juno components exist: `<div>` wrappers (layout, row cells, pagination wrapper), `<p>` bodies in modals and `<pre>` for the payload.
- **Scorer:** key-manager.tsx:91/104 and SecretDetailsView.tsx:88 use raw <div> wrappers, plus <pre>/<p> for payload; Quick Reject 'Raw HTML element where a Juno component exists' (Stack available) scores at least 75. Low per the Quick Reject UI precedent.
- **Evidence:**

Quick Reject: "Raw HTML element (<div>, <table>, <button>) where a Juno component exists"; B.1 "Primary layout primitive | Stack". Code: `<div><ContentHeader  etc/>  etc <div className="mt-4">`; SecretTableRow.tsx:26-27 `<div>{secret.name  etc}</div><div className="text-xs opacity-60">`; SecretsList.tsx:127 `<div className="flex justify-center py-4">`; SecretDetailsView.tsx:88 `<div>` around the button.


### `c16` — Low · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:21` · score 75
- **Claim** (finder-a): Files do not follow the B.12 naming table: the modal files bundle two modals each (`SecretModals.tsx`, `ContainerModals.tsx`, `OrderModals.tsx` instead of `CreateSecretModal.tsx` / `DeleteSecretModal.tsx`), the hook file is a generic `usePermissions.ts` instead of `useKeyManagerPermissions.ts`, and `utils.ts` / `constants.ts` are generic names.
- **Scorer:** Verified at head: `export function usePermissions(projectId, permissions)` is a generic name where B.8 asks for `use<Feature>Permissions(projectId)` (useKeyManagerPermissions); SecretModals.tsx/ContainerModals.tsx/OrderModals.tsx bundle several modals while B.12 wants `<Verb><Resource>Modal.tsx`; `utils.ts`/`constants.ts` are generic. Naming rule violation with no user-facing effect, so Low.
- **Precedent:** Network plugin has per-modal files.
- **Review discussion:** Copilot thread r4360389782 asked for useKeyManagerPermissions.
- **Evidence:**

B.12: "Modal | <Verb><Resource>Modal.tsx"; "Hook | use<PascalCase>.ts (useCephPermissions.ts)"; Reject: "generic names (Modal.tsx, Table.tsx)"; B.8: "a use<Feature>Permissions(projectId) hook". Hook is exported as `usePermissions(projectId, permissions)` and takes a permission list rather than projectId only.

- **Same problem, also from finder-d:** Hook is named generically usePermissions though it is Key Manager specific; the convention is use<Feature>Permissions (useKeyManagerPermissions).

export function usePermissions(...) at line 21; copilot-instructions B.8 line 328.


### `c19` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:59` · score 75
- **Claim** (finder-a): Empty-state wording does not distinguish `no data` from `no filter results`: with an active search the secrets/containers list shows `There are no secrets in this project. Create one to get started.`
- **Scorer:** B.6 says to distinguish empty reasons (no data suggests creating, no filter results suggests clearing filters). SecretListContainer has one empty state, `No Secrets Found` / `Create one to get started.`, and SecretsList passes it no search value, so a search with no hits gets the create hint. Wording only, so Low.
- **Evidence:**

B.6: "Distinguish empty reasons: 'no data' -> suggest creating; 'no filter results' -> suggest clearing filters." Code shows the same `No Secrets Found` / create body whether or not `search` is set (the list container does not receive `search`). Same in ContainerListContainer.tsx:58, and the empty Create hint is shown even to users without create permission.


### `c20` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:33` · score 50
- **Claim** (finder-a): Error states render the raw `error.message` as the Status title (`error?.message ?? t`Failed to Load Secret``), with no retry action or explanatory body.
- **Scorer:** Verified: `<Status status="error" title={error?.message ?? t`Failed to Load Secrets`} />` with no body or retry, same in DetailsViews. B.6 asks for a course of action only 'where feasible' and the message does give some explanation, so this is a nitpick, not a clear Reject.
- **Evidence:**

B.6: "Always communicate the state and a possible course of action (retry link where feasible)"; "any empty/broken state without explanatory title/body". Code: `<Status status="error" title={error?.message ?? t`Failed to Load Secrets`} />`; same in all list containers and DetailsViews (e.g. ContainerDetailsView.tsx:37). Detail pages also have no `errorComponent`/403 handling of their own.


### `c25` — Low · Bug · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:103` · score 50
- **Claim** (finder-b): getSecretPayload reads the secret with res.text() and returns it as a tRPC query result, so binary secrets (e.g. application/octet-stream, symmetric keys) are corrupted by UTF-8 decoding and shown as garbage; the plaintext payload also gets cached in the TanStack Query cache.
- **Scorer:** Verified: `const text = await res.text(); return { payload: text, contentType }` and SecretDetailsView renders it in a pre element, so binary payloads (octet-stream) are UTF-8-mangled; there is no base64/binary path. Binary content is unreadable in a text view anyway and the caching point is generic, so rare and bounded rather than higher.
- **Evidence:**

keyManagerRouter.ts lines 102-104: `const text = await res.text(); return { payload: text, contentType }`; no Accept header is sent and no binary/base64 handling.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c28` — Low · Bug · `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154` · score 50
- **Claim** (finder-c): The project landing page (projects/$projectId/index.tsx) builds service cards per service with the same isEnabled gating, but the PR does not touch it, so Key Manager gets a nav entry but no card on the project overview. The key-manager layout beforeLoad also checks only the catalog, not enabled/denied services, so a denied service stays reachable by URL.
- **Scorer:** Verified: the Key Manager nav entry is gated only by the catalog (serviceIndex key-manager barbican), while every other service in this file uses isEnabled(...) (enabledServices/deniedServices), and key-manager.tsx beforeLoad:46 also checks only the catalog. So an AppConfig deny/allow list cannot hide Key Manager and the route stays reachable by URL; the missing landing-page card (index.tsx has none) is a minor part. Low because it only matters for hosts using visibility config.
- **Evidence:**

At base c65b36d0, routes/_auth/projects/$projectId/index.tsx lines 56-110 push a card (group Compute/Network/Storage/Services) for each service under isEnabled; `git diff --stat` for the PR shows no change to that index.tsx (only key-manager/*/index.tsx files). #1370 touched both buildNavSections.ts and this index.tsx together to keep them in sync.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c32` — Low · Security · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98` · score 50
- **Claim** (finder-d): Secret payload plaintext can be logged: signal-openstack logs a bodyPreview for text responses when debug is on, and debug defaults to true outside production; getSecretPayload does not disable it.
- **Scorer:** Verified: context.ts:114 sets debug on outside production, and signal-openstack client.ts:175-178 logs a bodyPreview for any text response, so a text/plain secret payload fetched here is written to server logs (up to maxBodyPreviewLength). Different problem from the Accept header; Low because it is on by default only in non-production and truncated.
- **Review discussion:** Copilot inline r4360389080 (CRITICAL), no replies, still applies in non-production.
- **Evidence:**

signal-openstack/src/client.ts:169-183 builds bodyPreview from text; context.ts:114 debug: config.debug ?? NODE_ENV !== "production".


### `c55` — Low · UI/UX · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/constants.ts:1` · score 50
- **Claim** (describer (acceptance)): Acceptance criterion partly met: Each tab renders its own overview list with the columns specified in the UI Specification.
- **Scorer:** Issue #1133 spec lists Orders columns Name / ID, Type, Status; head has `ORDERS_COLUMNS = ["ID", "Status", "Type", ""]` and the row renders no order name/reference. Secrets and Containers match the spec (column order aside, deliberate). A criterion partly delivered, so Low.
- **Evidence:**

Secrets list (`secrets/-components/constants.ts:1`) has Name/ID, Status, Type, Content Types. Containers list shows name/ID, status, type. Orders list (`orders/-components/constants.ts:1`) has ID only, with no order name or reference. Column order differs from the spec (Status is second, by design per the PR body).


### `c56` — Low · Code Quality · `PR files` · score 50
- **Claim** (describer (acceptance)): Acceptance criterion partly met: Users can list, view, create, update, and delete Secrets, Containers, and Orders (P1, P2 & P3).
- **Scorer:** git grep at headRefOid finds no use of updateSecret, addContainerSecret or deleteContainerSecret under packages/aurora/src/client. So there is no edit-secret or manage-container-secrets UI, which only partly delivers the update criterion. Low per the partly-delivered-criterion precedent.
- **Evidence:**

List, view, create and delete are implemented in the UI for all three. Update is missing in the UI: `updateSecret`, `addContainerSecret` and `deleteContainerSecret` exist on the server but no client code calls them, so there is no Edit Secret modal and no Manage Container Secrets flow. Create Secret has only name, type and payload (no algorithm, bit length, mode, content type or expiration); Create Container cannot attach secrets (`secret_refs: []`).


### `c57` — Low · Bug · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89` · score 75
- **Claim** (describer (acceptance)): Acceptance criterion partly met: All action-triggering UI elements (Create, Edit, Delete, etc.) are gated using canUser(...) against the corresponding key-manager:* policy rules and are hidden/disabled for unauthorized users.
- **Scorer:** Verified: the Reveal Payload button (SecretDetailsView.tsx:89) calls getSecretPayload with no canUser check, although key-manager:secrets:payload is defined and mapped; epic #1133 requires all action-triggering elements gated. Create/Delete and list queries are gated, so the criterion is only partly delivered (precedent table: Low).
- **Evidence:**

Create and Delete are gated in the lists (`SecretsList.tsx:67` and siblings, and `canDelete` in the row components). Reveal Payload is not gated (`SecretDetailsView.tsx:90`), and there are no Edit or Manage-secrets actions to gate. Detail views do not check `get` permission. The server procedures do no policy check of their own.

- Bug: add its scenario to `edge_cases` in texts.json.

### `c58` — Low · UI/UX · `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:52` · score 50
- **Claim** (describer (acceptance)): Acceptance criterion partly met: Comprehensive error handling provides user-friendly feedback for Barbican errors.
- **Scorer:** mapKmError builds the message as `Key Manager ${operation} failed`. The !res.ok paths pass only {statusCode}, so Barbican's response body is dropped and users see generic text, for example for a 409 conflict. The error-handling criterion is only partly met, so Low.
- **Evidence:**

Modals show `mutation.error.message` and lists show a `Status` error, but `mapKmError` in `keyManagerRouter.ts` discards Barbican's response body and returns a generic message like 'Key Manager delete container failed', so conflicts such as a container with secrets get no specific text.


### `c60` — Low · Test coverage · `PR files` · score 50
- **Claim** (describer (acceptance)): Acceptance criterion partly met: Complete testing coverage (unit, integration, E2E) is achieved.
- **Scorer:** The PR has only router and schema tests plus TableRow/ListContainer tests. There are no tests for the lists with permissions, modals, detail views or layout guard, and no E2E, so the testing criterion is only partly delivered. Low per the precedent for no tests when the epic requires them.
- **Evidence:**

Unit tests are added for the router (`keyManagerRouter.test.ts`), the schemas (`keyManager.test.ts`) and the TableRow and ListContainer components of all three resources. No tests for the lists with permissions, modals, detail views, nav or the layout guard, and no E2E.


### `c17` — Trivial · Code Quality · `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx | import { usePermissions } from "../../-components/usePermissions"` · score 75
- **Claim** (finder-a): Import order and path rules are broken: Juno imports come before `@lingui` imports (and `useState` after Juno in SecretModals), and `../../-components/...` relative traversal two levels up is used instead of `@/` aliases.
- **Scorer:** B.13 and Quick Reject name import order: SecretsList.tsx puts `@/client/trpcClient` after the Juno import block (tRPC must come before Juno), and uses `../../-components/usePermissions` although B.13 says all imports must use `@/` aliases with no `../../` traversal. Verified; no runtime effect.
- **Evidence:**

B.13: order is react, i18n, tRPC, Juno; "All imports must use @/ path aliases. No relative ../../ traversal beyond one level." Code: SecretModals.tsx imports Juno (l.1-12) then `useState` from react (l.13); key-manager.tsx:2-4 Juno, server, then lingui. `import { uuidFromRef } from "../../-components/utils"` in all *Modals/*TableRow/*DetailsView files and `import { usePermissions } from "../../-components/usePermissions"` in all *List files; secrets/index.tsx:5 `../-components/utils`.


## Scored below 50 (not in the report)

- `C18` 25: User-facing strings are not translated: JSX button/placeholder/label literals (`Create Secret`, `Search by name...`, `Sort by`, `Created At`
- `C23` 25: The PR body checklist leaves the tests, docs, warnings and 'commented my code' items unchecked even though tests are added, and the Testing 
- `C26` 0: listOrders translates `sort` into sort_key/sort_dir query params, but Barbican's orders list API only supports offset and limit, so the orde
- `C29` 0: Reveal Payload button is rendered and fetches secret material without checking the separately defined key-manager:secrets:payload permission
- `C30` 0: Key Manager server procedures never evaluate the loaded policy; canUser is registered but each handler (incl. getSecretPayload, deleteContai
- `C31` 0: getSecretPayload (and other calls) use the session default Accept: application/json; Barbican's payload endpoint serves raw secret content a
- `C36` 0: Boolean permission props are named canDelete instead of can<Verb><Noun> (canDeleteContainer/canDeleteSecret/canDeleteOrder), violating B.8.
- `C37` 0: Row action PopupMenu has no PopupMenuToggle trigger (labelled more-actions button) and no PopupMenuSectionSeparator before destructive Delet
- `C38` 0: Hook is named generically usePermissions though it is Key Manager specific; the convention is use<Feature>Permissions (useKeyManagerPermissi
- `C40` 0: Create Order modal does not validate Bit Length: parseInt of empty or invalid input yields NaN, zero/negative values are accepted, and Creat
- `C43` 25: listContainers sends a `name` filter, but the Containers list documents only offset and limit. The search box would be silently ignored by B
- `C46` 25: updateSecret uses PUT /v1/secrets/{id}, which the reference restricts to metadata-only secrets without a payload; the router offers it for a
- `C47` 25: CreateOrderInputSchema accepts type "certificate", but the Orders reference documents only key and asymmetric as valid order types.
- `C48` 25: List calls accept any numeric limit/offset (z.number() without .max(100)/.min(0)); Barbican caps limit at 100, so a client-supplied larger v
- `C49` 0: The Reveal Payload button (and the detail views generally) is not gated by the `key-manager:secrets:payload` permission, which is mapped ser
- `C50` 25: None of the KeyManager mutations or the payload query enforce a server-side canUser/policy check; they rely only on projectScopedProcedure a
- `C51` 25: Decrypted secret payload is fetched via a TanStack Query useQuery (enabled:false + refetch) and so stays in the client query cache after 'Hi
- `C52` 25: ID/ref inputs interpolated into outbound Barbican paths are unvalidated `z.string()`; encodeURIComponent does not encode `.`, so `secretId`/
- `C53` 0: mapKmError attaches the raw upstream error as `cause` for every failure; if the tRPC error formatter or logger serialises causes this can ex
- `C54` 25: Acceptance criterion partly met: tRPC BFF is implemented with complete Zod schema validation for Secrets, Containers, and Orders.
- `C59` 0: Acceptance criterion partly met: All UI components follow the Aurora design system.
- `C61` 25: Stale caller of `updateSecret / addContainerSecret / deleteContainerSecret`: Server procedures with no client caller, and no UI flow behind 
- `C62` 25: Stale caller of `key-manager:secrets:update / key-manager:containers:update / key-manager:secrets:payload`: Permission keys defined and mapp

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
- partly met: Complete testing coverage (unit, integration, E2E) is achieved.

## texts.json shape

Optional: `fixes` — exact replacements after the fact-check, copied from `out/factcheck.json`: `[{"field": "overview.how", "old": "…", "new": "…"}]` (fields as in findings.json: overview.what/how/affects, qa.core_path[i], qa.edge_cases[i], findings.<id>.issue/title/explanation/fix); `process` / `process_overrides` as in findings-format.md.

```json
{
 "summary": "2–4 sentences",
 "confidence": "High | Medium | Low",
 "index_affected": "touched surface, ≤ 40 words, no verdict",
 "findings": {
  "c45": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c6": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c8": {
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
  },
  "c13": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c24": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c33": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c34": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c39": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c41": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c44": {
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
  "c2": {
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
  "c4": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c5": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c7": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c9": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c10": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c12": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c14": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c15": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c16": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c19": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c20": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c25": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c28": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c32": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c55": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c56": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c57": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c58": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c60": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  },
  "c17": {
   "issue": "",
   "title": "",
   "explanation": "",
   "fix": ""
  }
 },
 "edge_cases": [
  "scenario behind each Bug finding, citing [[ref:<id>]]"
 ],
 "merge": {},
 "provenance_extra": []
}
```
