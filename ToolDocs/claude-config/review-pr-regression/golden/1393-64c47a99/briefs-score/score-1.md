# Scorer 1 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7`
- baseRefOid: `cd8e674e2504b9de06d72e09ea4177f8f758bd8c`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `fd248f083f89fbe9caca6ad536106ffd08860159..64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff cd8e674e2504b9de06d72e09ea4177f8f758bd8c...64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7 -- <path>`.

## Your role: scorer 1 of 3

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C1, C2, C16

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

### C1 — from finder-a
- **Claim:** The new row-action toggles are icon-only Buttons with only a title and no aria-label. Screen readers may announce nothing reliable for the control in every key-manager list row.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:40`
- **Evidence:**

B.14 / Quick Reject: "Icon-only button without `aria-label`". Code: <Button icon="moreVert" title={t`Secret actions`} /> (same in ContainerTableRow.tsx:39, OrderTableRow.tsx:38). example: packages/aurora/src/client/routes/_auth/projects/$projectId/storage/-components/Ceph/Buckets/BucketHeaderActions.tsx:67
- **Precedent:** FloatingIpDetailsView.tsx:66 also uses title only; Ceph and flavors pair title with aria-label.

### C2 — from finder-a
- **Claim:** Accessible names/tooltips "Secret actions", "Container actions", "Order actions" are not title case, unlike sibling labels "Bucket actions"-style/"More Actions" in the reference modules.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:40`
- **Evidence:**

B.19: "Title case for ... button labels". example: packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/$flavorId.tsx:227 ("More Actions")
- **Precedent:** Ceph BucketHeaderActions.tsx:67 uses lowercase "Bucket actions" too.

### C16 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: All UI components follow the Aurora design system.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:39`
- **Evidence:**

Row menus now have a labelled toggle and a separator before Delete (`secrets/-components/SecretTableRow.tsx:39`), but earlier findings on sort input, spacing classes and raw HTML elements are not all addressed in this update.

### C3 — from finder-a
- **Claim:** CreateOrderModal shows validation errors as the user types, derived on every render, instead of on blur / submit. Clearing the Algorithm field immediately paints an error before the field is left, and the Create button is disabled with no submit-time revalidation.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:43`
- **Evidence:**

B.11: "Validate **on blur** by default; always re-validate all fields **on submit**. Validate **as-you-type** only for strict-format fields"; Algorithm and Bit Length are not strict-format fields. Errors are computed from state at lines 43-46 and passed to errortext (94-107) with no touched/blur tracking. example: packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/CreateFlavorModal.tsx:225
- **Precedent:** Not a Reject-line violation by itself (initial defaults are valid, so nothing shows before interaction).

### C4 — from finder-a
- **Claim:** Each list adds a useEffect that calls onPageChange when the current page becomes empty. This is event-driven state sync that could be done in the delete handler or by clamping the page, and it runs in three components.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:71`
- **Evidence:**

A.1: "Critically evaluate every `useEffect` ... Flag synchronizations, computed states, or event-driven triggers ... that can be handled during rendering or inside event handlers". Effect: if (!isLoading && !isError && page > 1 && (data?.secrets.length ?? 0) === 0) onPageChange(page - 1). Same in OrdersList.tsx:53 and ContainersList.tsx:48. The trigger is the delete mutation's onSuccess in the Delete*Modal.

### C5 — from finder-a
- **Claim:** The new useKeyManagerPermissions import uses a two-level relative path (`../../`) in the changed lines instead of the `@/` alias.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:14`
- **Evidence:**

Quick Reject: "Import using `../../` traversal beyond one level instead of `@/`"; B.13: "No relative `../../` traversal beyond one level". Lines: import { useKeyManagerPermissions } from "../../-components/useKeyManagerPermissions" (also ContainersList.tsx:4, OrdersList.tsx:12, SecretDetailsView.tsx:8). example: packages/aurora/src/client/routes/_auth/projects/$projectId/compute/flavors/-components/CreateFlavorModal.tsx:17
- **Precedent:** The old usePermissions import used the same ../../ path; the PR renamed it but kept it.

### C6 — from finder-b
- **Claim:** After switching Accept to application/octet-stream, getSecretPayload still reads the body with res.text(). For binary secrets (e.g. application/octet-stream keys, PKCS12 certificates) the bytes are decoded as UTF-8, so Reveal Payload and Copy show corrupted data (replacement characters). Text payloads are unaffected.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:110`
- **Evidence:**

keyManagerRouter.ts lines 100-111 at 64c47a9: request with Accept: application/octet-stream, then `const text = await res.text()` and `return { payload: text, contentType }`. The delta does not touch the read path or base64-encode non-text content types.
- **Precedent:** The raw-text read was already there before this commit; the Accept change is what makes binary bodies reachable.

### C7 — from finder-d
- **Claim:** The Key Manager canUser router only reports policy decisions. None of the tRPC procedures (getSecretPayload, deleteSecret, deleteContainer, deleteOrder, create*, update*) checks the policy before calling Barbican. A caller can use the tRPC API directly to run an action the UI hides and Aurora's policy denies, whenever Barbican itself allows it. This includes revealing secret payloads, since the hidden control is only a client-side gate.
- **Location:** `packages/aurora/src/server/KeyManager/routers/index.ts:8`
- **Evidence:**

At the head commit, keyManagerRouter.ts procedures use projectScopedProcedure and go straight to km.get/post/del with no policy check (e.g. getSecretPayload lines 93-112, deleteSecret 153-162). The permission router is only spread in at index.ts:7-8. The only server-side policy code is in the permissionRouter.ts files and createPermissionRouter.ts, so nothing enforces a decision. The delta did not add a guard.
- **Precedent:** Compute, Network and Storage routers do not enforce policy server-side either. Only their permissionRouter.ts files and createPermissionRouter.ts use the engine, so the pattern is accepted elsewhere.
- **Review discussion:** Raised by Copilot in https://github.com/cobaltcore-dev/aurora-dashboard/pull/1393#discussion_r4360389025 (CRITICAL, unanswered). Still applies at 64c47a99. Other Copilot threads were checked at head and look addressed: Accept header and debug:false on payload (keyManagerRouter.ts:98-104), isEnabled on the nav entry (buildNavSections.ts:154), nullable secret_refs name (keyManager.ts:25), canDelete renamed to canDeleteContainer/Secret/Order, hook renamed to useKeyManagerPermissions, payload gating via canRevealPayload (SecretDetailsView.tsx:21-22), bit length validation (OrderModals.tsx:42-46), menu toggle label and separator, and page step-back on an empty page (SecretsList.tsx:70-75). The container-secret DELETE endpoint no longer exists in the router.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-1 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

