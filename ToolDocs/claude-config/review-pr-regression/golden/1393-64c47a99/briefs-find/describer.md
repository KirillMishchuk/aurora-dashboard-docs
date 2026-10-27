# Describer — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7`
- baseRefOid: `cd8e674e2504b9de06d72e09ea4177f8f758bd8c`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `fd248f083f89fbe9caca6ad536106ffd08860159..64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff cd8e674e2504b9de06d72e09ea4177f8f758bd8c...64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7 -- <path>`.

## Your role: the describer, on an Update

The PR already has a review report, and the new commits are in `delta.diff`. Another agent checks, finding by finding, which of the report's findings the new commits fix; the Update lists that under "Fixed since last analysis". Your job is everything else: what the new commits do that none of these findings covers. You describe; you don't review.

The report's findings:

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

**1. Sort the delta.** Go through `delta.diff` and put every change on one of two piles:

- **(a) carries out a finding above** — it does what the finding or its fix asked: moves the column, rewords the string, removes the loader, adds the toggle, updates the doc. Test: would this change exist if that finding had never been written? If not, it is (a).
- **(b) everything else** — new behaviour, a change outside the PR's stated scope, a change to a contract or to other callers, a side effect of an (a) change that the finding didn't ask for.

**2. Write only pile (b).** Pile (a) never appears in your result: not retold, not listed, not named by number.

- `what` — first one sentence on the update itself: the commit range in short SHAs (`1a2b3c4d..5e6f7a8b`), whether the PR is a draft, and CI on the head commit (merge conflicts are not part of this review — leave them out) (`context.json` → `ci`; say so if anything failed or is pending). Then one short paragraph per area of pile (b). If pile (b) is empty, add only: "Every other change carries out an earlier finding."
- `how` — only for a pile (b) change whose mechanism isn't obvious from `what`: a short excerpt (3–15 lines) and what it does. Don't copy code: put a placeholder on its own line — `[[code:<path>:<from>-<to>]]`, or `[[code:<path> | <text from its first line> | <number of lines>]]` — and cite lines as `[[at:<path> | <text on that line>]]` or `` `<path>:<line>` ``; the code is inserted and every citation checked later. Otherwise `""`.
- `affects` — for pile (b) only: consumers outside the PR's own files (`git grep -n '<symbol>' 64c47a995507e7e7f9bf4ba02c0cd8ba6d3f3fd7 -- . ':!pnpm-lock.yaml' ':!**/CHANGELOG.md' ':!**/locales/**'`), callers left stale, docs that now disagree, contract changes. Otherwise `""`.
- `qa` — `core_path` and `edge_cases` are empty lists; an Update shows no QA plan.

Write every text for the PR's readers: "the head commit", "the PR description", "the linked issue" — never run-folder file names (`context.json`, `pr-body.md`, …), field names (`headRefOid`) or names of this review's steps (finders, scorers, describer); `save.py` rejects them.

**Acceptance criteria.** Grade the PR against the acceptance criteria in `issue-1133.md`: for each criterion, met / partly met / unmet, with `file:line` evidence. Use "out of scope" only when `pr-body.md` explicitly limits the PR to part of the issue (e.g. "phase 1", "read-only part of #N") and the criterion falls outside that part — quote the limiting line from `pr-body.md` in `evidence`. An out-of-scope criterion is not a candidate; a partly met criterion inside the PR's own scope still is.

**Scope.** If the PR description (or the linked issue) limits this PR to part of an epic or issue — a phase, "read-only part of #N" — put that in `scope` as one short line, e.g. `#816 — Phase 1, read-only`. Otherwise `null`.

## Result shape

```json
{
  "overview": {
    "what": "Markdown: one sentence on the update, then pile (b) by area.",
    "how": "Markdown or empty string.",
    "affects": "Markdown or empty string."
  },
  "qa": { "core_path": [], "edge_cases": [] },
  "acceptance": [
    { "criterion": "quoted from the issue", "status": "met | partly met | unmet | out of scope", "evidence": "`path:line` and why" }
  ],
  "stale_callers": [
    { "symbol": "name", "location": "path:line", "note": "what's stale" }
  ],
  "scope": "#816 — Phase 1, read-only, or null"
}
```

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as describer <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

