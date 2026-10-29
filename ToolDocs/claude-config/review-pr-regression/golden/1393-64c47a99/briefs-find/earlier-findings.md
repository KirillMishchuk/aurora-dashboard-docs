# earlier-findings — status of the earlier findings — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7`
- baseRefOid: `cd8e674e2504b9de06d72e09ea4177f8f758bd8c`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `fd248f083f89fbe9caca6ad536106ffd08860159..64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff cd8e674e2504b9de06d72e09ea4177f8f758bd8c...64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7 -- <path>`.

## Your role: the earlier findings

This is an Update: the report it extends already raised the findings below, at an older head. You do one thing — for each of them, check the code at headRefOid (the code as it is now, not only the diff) and the replies to it in the review discussion (`discussion.json`: comments, reviews and threads after the report that name it — "I14", the finding's subject), and say whether it still holds:

- `fixed` — the code no longer does what the finding says;
- `partly` — part of it is fixed and part still holds; the note says which part is left;
- `open` — it still holds as written;
- `dropped` — only in three cases: a finding about merge conflicts (with `main` or with other open PRs) or about the PR being a draft — this review no longer covers them; don't check it, the note is "Merge conflicts are no longer part of this review; GitHub shows them." or "Draft state is no longer part of this review; a draft can't be merged anyway." — or a finding a maintainer (a reviewer other than the PR's author, not a bot) asked to do differently in the review discussion (`discussion.json`): the note is "Reversed by <login> in <url>." with the comment's or review's url — or an Improvement (`I…`) or Process item (`P…`) that the author or a maintainer explicitly kept as is in the discussion, with a reason (intentional, documented, out of scope, follow-up): the note is "Kept as is by <login>: <their reason in a few words> (<url>)." A Required Change (`CR…`) is not closed by the author's word: it stays `open` (or `partly`), and the note may add the author's position with the url.

Line numbers in the list are from the older head and may have moved: find the code by what the finding describes, not by the number. Process items: changeset against `context.json` (`changeset`), claims about the PR description against `pr-body.md`.

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

## Result shape

```json
{
  "earlier": {
    "CR1": {"status": "fixed", "note": "One line: what changed, or what is left.", "evidence": "The command you ran and the lines of its output that show it."}
  }
}
```

- Every finding listed above exactly once — `save.py` refuses a result with one left out or one that isn't listed.
- `note` is one line for the report's reader. Name other earlier findings by their number (`CR2`); don't make up numbers.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as earlier-findings <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

