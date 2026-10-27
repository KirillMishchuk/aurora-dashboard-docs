# Scorer 4 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: scorer 4 of 9

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C16, C38
- C18, C55

## Candidates

The evidence is as the finders reported it, unchanged.

### C16 — from finder-a
- **Claim:** Files do not follow the B.12 naming table: the modal files bundle two modals each (`SecretModals.tsx`, `ContainerModals.tsx`, `OrderModals.tsx` instead of `CreateSecretModal.tsx` / `DeleteSecretModal.tsx`), the hook file is a generic `usePermissions.ts` instead of `useKeyManagerPermissions.ts`, and `utils.ts` / `constants.ts` are generic names.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:21`
- **Evidence:**

B.12: "Modal | <Verb><Resource>Modal.tsx"; "Hook | use<PascalCase>.ts (useCephPermissions.ts)"; Reject: "generic names (Modal.tsx, Table.tsx)"; B.8: "a use<Feature>Permissions(projectId) hook". Hook is exported as `usePermissions(projectId, permissions)` and takes a permission list rather than projectId only.
- **Precedent:** Network plugin has per-modal files.
- **Review discussion:** Copilot thread r4360389782 asked for useKeyManagerPermissions.

### C38 — from finder-d
- **Claim:** Hook is named generically usePermissions though it is Key Manager specific; the convention is use<Feature>Permissions (useKeyManagerPermissions).
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/-components/usePermissions.ts:21`
- **Evidence:**

export function usePermissions(...) at line 21; copilot-instructions B.8 line 328.
- **Review discussion:** Copilot inline r4360389782, no replies, unchanged.

### C17 — from finder-a
- **Claim:** Import order and path rules are broken: Juno imports come before `@lingui` imports (and `useState` after Juno in SecretModals), and `../../-components/...` relative traversal two levels up is used instead of `@/` aliases.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:13`
- **Evidence:**

B.13: order is react, i18n, tRPC, Juno; "All imports must use @/ path aliases. No relative ../../ traversal beyond one level." Code: SecretModals.tsx imports Juno (l.1-12) then `useState` from react (l.13); key-manager.tsx:2-4 Juno, server, then lingui. `import { uuidFromRef } from "../../-components/utils"` in all *Modals/*TableRow/*DetailsView files and `import { usePermissions } from "../../-components/usePermissions"` in all *List files; secrets/index.tsx:5 `../-components/utils`.

### C18 — from finder-a
- **Claim:** User-facing strings are not translated: JSX button/placeholder/label literals (`Create Secret`, `Search by name...`, `Sort by`, `Created At`), the permission-denied Messages, and the DataGrid column header arrays in constants.ts (`Name / ID`, `Status`, `Type`, ...) are plain English, so the de locale will show English.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/constants.ts:1`
- **Evidence:**

B.14: "All user-facing strings must be wrapped in <Trans> or t` etc`" (the review scope says lingui lint covers aurora, but these aren't caught). `export const SECRETS_COLUMNS = ["Name / ID", "Status",  etc]`; SecretsList.tsx:97 `Create Secret`, :105 `placeholder="Search by name etc"`, :84 `label="Sort by"`; `msgid "Name / ID"` and `msgid "Search by name"` are absent from en/messages.po at head (git show | grep).
- **Precedent:** Low priority: out of the stated review scope if lint is assumed to catch it.

### C55 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: Each tab renders its own overview list with the columns specified in the UI Specification.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/constants.ts:1`
- **Evidence:**

Secrets list (`secrets/-components/constants.ts:1`) has Name/ID, Status, Type, Content Types. Containers list shows name/ID, status, type. Orders list (`orders/-components/constants.ts:1`) has ID only, with no order name or reference. Column order differs from the spec (Status is second, by design per the PR body).

### C19 — from finder-a
- **Claim:** Empty-state wording does not distinguish `no data` from `no filter results`: with an active search the secrets/containers list shows `There are no secrets in this project. Create one to get started.`
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:58`
- **Evidence:**

B.6: "Distinguish empty reasons: 'no data' -> suggest creating; 'no filter results' -> suggest clearing filters." Code shows the same `No Secrets Found` / create body whether or not `search` is set (the list container does not receive `search`). Same in ContainerListContainer.tsx:58, and the empty Create hint is shown even to users without create permission.

### C20 — from finder-a
- **Claim:** Error states render the raw `error.message` as the Status title (`error?.message ?? t`Failed to Load Secret``), with no retry action or explanatory body.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretListContainer.tsx:33`
- **Evidence:**

B.6: "Always communicate the state and a possible course of action (retry link where feasible)"; "any empty/broken state without explanatory title/body". Code: `<Status status="error" title={error?.message ?? t`Failed to Load Secrets`} />`; same in all list containers and DetailsViews (e.g. ContainerDetailsView.tsx:37). Detail pages also have no `errorComponent`/403 handling of their own.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-4 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

