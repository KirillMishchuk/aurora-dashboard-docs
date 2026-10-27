# Scorer 2 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7`
- baseRefOid: `cd8e674e2504b9de06d72e09ea4177f8f758bd8c`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `fd248f083f89fbe9caca6ad536106ffd08860159..64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff cd8e674e2504b9de06d72e09ea4177f8f758bd8c...64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7 -- <path>`.

## Your role: scorer 2 of 3

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Earlier findings of this report

This is an Update: the report it extends already raised the findings below. A candidate that objects to the PR doing what one of them asked (it moved a column, renamed a string, restructured code as an earlier finding requested) is not a new problem: score it 0 and name the earlier finding in the reason. If the change was made badly — it breaks something or does only half of it — score that as usual.

- CR1 🟠 Major — `getSecretPayload` sends the default `Accept: application/json`, so Barbican answers 406 for most secrets — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`
- CR2 🟡 Moderate — Create modals mutate without validation; Bit Length is sent as `NaN` when empty — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:52`
- CR3 🟡 Moderate — Create and delete of secrets, containers and orders show no confirming toast — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:35`
- CR4 🟡 Moderate — Reveal Payload and the detail views ignore `key-manager:secrets:payload` / `get` permissions — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89`
- CR5 🟡 Moderate — Search inputs navigate on every keystroke, with no local state or debounce — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:109`
- CR6 🟡 Moderate — `deleteContainerSecret` calls an undocumented `DELETE /v1/containers/{id}/secrets/{name}` — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:252`
- CR7 🟡 Moderate — Container `secret_refs[].name` is required `z.string()`, but Barbican allows unnamed refs — `packages/aurora/src/server/KeyManager/types/keyManager.ts:25`
- CR8 🟡 Moderate — Deleting the last row on the last page leaves an empty table with no pagination — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:126`
- CR9 🟡 Moderate — Key Manager nav entry and route ignore `enabledServices` / `deniedServices` — `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`
- CR10 🟡 Moderate — `listOrders` sends undocumented `sort_key`/`sort_dir`; the Orders sort control does nothing — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:271`
- P1 — — Published package code changed without a `.changeset/*.md` — PR files
- I1 🟢 Low — Permission props are named `canDelete` instead of `can<Verb><Noun>` — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:15`
- I2 🟢 Low — Row `PopupMenu` has no `PopupMenuToggle` with a labelled `moreVert` button — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:35`
- I3 🟢 Low — Row menu items `Show Details` / `Delete` lack the entity name and a separator before Delete — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:38`
- I4 🟢 Low — Delete modals put the name/ID in the title and use a bare `Delete` confirm label — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:129`
- I5 🟢 Low — Modals disable Cancel but not the close-X while a mutation is pending — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:136`
- I6 🟢 Low — Create modals use `useState` without react-form, `autoFocus` or disabled inputs in flight — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:30`
- I7 🟢 Low — Sort uses raw `Select` + `SortButton` instead of `SortInput`; toolbar uses `distribution="end"` — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:93`
- I8 🟢 Low — 403 on list pages is an inline warning `Message` with hard-coded English — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:72`
- I9 🟢 Low — Detail routes fetch in the component (twice) instead of in the route `loader` — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/$containerId.tsx:19`
- I10 🟢 Low — Ad-hoc spacing/styling classes (`my-6`, `mt-4`, `p-3`, `opacity-60`) outside the approved lists — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:79`
- I11 🟢 Low — Raw `<div>`, `<p>`, `<pre>` used where Juno components exist — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx:104`
- I12 🟢 Low — Generic names: `usePermissions`, bundled `*Modals.tsx`, `utils.ts`, `constants.ts` — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:21`
- I13 🟢 Low — Empty state suggests creating even when a search returned no results — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:59`
- I14 🟢 Low — Error states show the raw `error.message` as title with no body or retry — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:33`
- I15 🟢 Low — `getSecretPayload` decodes binary payloads with `res.text()` — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:103`
- I16 🟢 Low — Secret plaintext can land in server logs via signal-openstack's debug body preview — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`
- I17 🟢 Low — Orders list lacks the Name column from the epic's UI spec — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/constants.ts:1`
- I18 🟢 Low — No update UI: `updateSecret`, `addContainerSecret`, `deleteContainerSecret` have no client caller — PR files
- I19 🟢 Low — `mapKmError` drops Barbican's error body; users see generic `Key Manager … failed` — `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:52`
- I20 🟢 Low — No tests for lists with permissions, modals, detail views, nav or layout guard; no E2E — PR files
- I21 ⚪ Trivial — Import order and `../../` relative imports break B.13 — `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:14`

## Candidates

The evidence is as the finders reported it, unchanged.

### C8 — from finder-f
- **Claim:** getSecretPayload hardcodes Accept: application/octet-stream. Barbican requires the Accept header on /payload to be one of the values in the secret's content_types, so a secret stored with another type (for example text/plain) can get 406 Not Acceptable. mapKmError turns that into INTERNAL_SERVER_ERROR, and the user sees 'Key Manager get secret payload failed' when revealing the payload. It works only for secrets whose content type is application/octet-stream.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:102`
- **Evidence:**

Code at 64c47a99, keyManagerRouter.ts:100-104: `.get(`v1/secrets/${encodeURIComponent(input.secretId)}/payload`, { headers: { Accept: "application/octet-stream" }, debug: false })`. Reference (barbican doc/source/api/reference/secrets.rst, raw github, section 'GET /v1/secrets/{uuid}/payload', rendered at https://docs.openstack.org/barbican/latest/api/reference/secrets.html#get-secrets-uuid-payload): "When making a request for a secret's payload, you must set the accept header to one of the values listed in the ``content_types`` attribute of a secret's metadata." The documented example sends `Accept: text/plain`, and the status table lists `406 | Not Acceptable`. The secret metadata example shows `"content_types": {"default": "application/octet-stream"}` for opaque secrets only. The client already reads secret.content_types (SecretDetailsView.tsx:51), so the server could use content_types.default or fetch the secret first. Barbican source barbican/api/controllers/secrets.py: when there is no Accept header it defaults to 'application/octet-stream', otherwise it uses the header value. In signal-openstack at 64c47a99, grep for 'accept' in packages/signal-openstack/src finds nothing, so the in-code comment claiming a default 'Accept: application/json' is not backed by that client. I could not check what undici/fetch sends by default. Secondary: the body is read with res.text() (line 110), which corrupts binary payloads.
- **Precedent:** Other KM calls (getSecret, listSecrets) send no Accept header; the docs show Accept: application/json on those metadata calls.

### C9 — from finder-f
- **Claim:** The container secret reference schema was loosened to name nullable, but the Barbican docs only show named references; the docs do not say a null name is allowed. The new test comment 'Barbican allows unnamed references' has no support in the container reference. The docs say a generic container's reference name is not restricted ('no specific restrictions are enforced on the contents name attribute'), but they do not document null.
- **Location:** `packages/aurora/src/server/KeyManager/types/keyManager.ts:25`
- **Evidence:**

Code: `secret_refs: z.array(z.object({ name: z.string().nullable(), secret_ref: z.string() }))`. Reference (barbican doc/source/api/reference/containers.rst, https://docs.openstack.org/barbican/latest/api/reference/containers.html): 'This type of container holds any number of references to secrets. Each secret reference is accompanied by a name. Unlike other container types, no specific restrictions are enforced on the contents name attribute.' All response examples show `"name": "private_key"`. I found no doc text saying name may be null. Low severity: the lenient schema is safe at runtime, but the claim in the test title is unverified. I did not check the Barbican source for null names.
- **Precedent:** none

### C10 — from finder-g
- **Claim:** The new payload gating (key-manager:secrets:payload via canUser) is client-only. The getSecretPayload procedure is a plain projectScopedProcedure with no server-side canUser/policy check, so anyone calling the tRPC endpoint directly skips the UI gate; only Barbican's own policy then decides. Same holds for the delete/create procedures whose buttons are now hidden by canUser.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:93`
- **Evidence:**

keyManagerRouter.ts:93-111 getSecretPayload: projectScopedProcedure, input schema, then a km.get of the payload path with no canUser/policy evaluation. The delta (SecretDetailsView.tsx) hides the Reveal Payload UI behind useKeyManagerPermissions only. The policy rule key-manager:secrets:payload exists in apps/dashboard/src/policies/key-manager.json:12 (rule:context_is_keymanager_viewer) and packages/aurora/src/server/KeyManager/routers/permissionRouter.ts:6, but is used only by the canUser query. Barbican enforces its own RBAC with the rescoped token, so this is defense-in-depth rather than a direct bypass. The handler code predates the delta; the delta adds only the client gate and debug:false.
- **Precedent:** Other domains (Compute/Network/Storage) also gate mainly in the UI via canUser; not checked whether any enforces it server-side in mutations.

### C11 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: tRPC BFF is implemented with complete Zod schema validation for Secrets, Containers, and Orders.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:64`
- **Evidence:**

`packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:64` to `:277` cover list/get/create/delete for all three resources plus `updateSecret` (`:138`) and the payload query (`:93`), all with Zod schemas. Container secret association (`containers.updateSecrets`, Phase 2) is no longer implemented after `addContainerSecret` was removed in this update.

### C12 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: Each tab renders its own overview list with the columns specified in the UI Specification.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/constants.ts:1`
- **Evidence:**

Secrets and Containers have Name / ID, Status, Type (and Content Types for secrets) in `secrets/-components/constants.ts:1` and `containers/-components/constants.ts:1`. Orders show `ID` instead of a name / reference column (`orders/-components/constants.ts:1`).

### C13 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: Users can list, view, create, update, and delete Secrets, Containers, and Orders (P1, P2 & P3).
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:138`
- **Evidence:**

List, view, create and delete work for all three. Secret update exists only as the `updateSecret` procedure (`keyManagerRouter.ts:138`) with no UI. Container secret association has no server procedure any more.

### C14 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: All action-triggering UI elements (Create, Edit, Delete, etc.) are gated using canUser(...) against the corresponding key-manager:* policy rules and are hidden/disabled for unauthorized users.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/useKeyManagerPermissions.ts:25`
- **Evidence:**

Create and Delete are gated in the three `*List.tsx` files through `useKeyManagerPermissions` (`key-manager/-components/useKeyManagerPermissions.ts:25`), and Reveal Payload now depends on `key-manager:secrets:payload` in `SecretDetailsView.tsx`. There is no Edit action or UI, so that gate does not exist.

## Result shape

```json
{
  "scores": [
    {
      "id": "C1",
      "score": 75,
      "severity": "Moderate",
      "category": "Performance",
      "location": "path:line, verified at headRefOid",
      "reason": "One or two sentences: what you checked and found (file:line, quote, behaviour) and why this score and severity. Written for the PR's readers — it can be posted: \"the head commit\", \"the PR description\", not run-folder file names.",
      "same_as": null,
      "precedent": null
    }
  ]
}
```

- One entry per candidate, every candidate exactly once.
- `score`: 0, 25, 50, 75 or 100. For 50 and up, `severity` (Critical, Major, Moderate, Low, Trivial), `category` (Bug, Security, Accessibility, UI/UX, Code Quality, Performance, Docs, Test coverage) and a `location` that exists at headRefOid (`path:line`, `path | text on that line`, or `PR body` / `PR state` / `PR files` / `CI`). Below 50, leave them out.
- `precedent`: required for 50 and up — the reader's tag, it never changes the score. `{"kind": "existing", "ref": "path:line"}` when merged code already has the same problem — `ref` is a line that itself breaks the same rule. Sibling code that does it right (e.g. a list that already debounces) is not a precedent: it's evidence for the finding, put it in `reason`. Find that line at baseRefOid (`git grep -n '<pattern>' <baseRefOid> -- <pathspec>`). `{"kind": "deferred", "ref": "<URL>"}` when a maintainer accepted or postponed the same point, on another PR or in `discussion.json`: open the thread, `ref` is the comment's GitHub URL. Both apply → `deferred`. Neither, or you couldn't confirm the candidate's `precedent` → `null`.
- `same_as`: required for a candidate in a group above — the id of the candidate in the same group that describes the same problem (score that one; this one is then dropped — `score` and `reason` may be left out for it), or `null` if it is a different problem. Elsewhere leave it out.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-2 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

