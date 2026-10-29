# Scorer 3 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: scorer 3 of 9

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C11, C29, C49

## Candidates

The evidence is as the finders reported it, unchanged.

### C11 — from find-standards
- **Claim:** Reveal Payload button, secret detail and the other detail routes do not check any permission (`key-manager:secrets:payload` / `get`); the control is rendered functional before permissions are known (not fail-closed).
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89`
- **Evidence:**

Quick Reject: "UI control shown before permissions are resolved (not fail-closed)"; B.7/B.8: "Never optimistically show actions before permissions resolve." Code: `<Button variant="subdued" onClick={handleRevealPayload} disabled={payloadFetching}>`; usePermissions is never imported in the *DetailsView files. The `payload` permission is defined in usePermissions.ts:6 and the policy but unused.
- **Review discussion:** Copilot thread r4360388886 (CRITICAL).

### C29 — from find-discussion
- **Claim:** Reveal Payload button is rendered and fetches secret material without checking the separately defined key-manager:secrets:payload permission (the key exists in permissionRouter but is never used client-side). Users without the permission see a working control; not fail-closed.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:90`
- **Evidence:**

git grep at head: SecretDetailsView.tsx has no permission lookup/usePermissions; permissionRouter.ts:6 defines "key-manager:secrets:payload". copilot-instructions B.7/B.8: permissions default false while loading, reject controls shown before permissions confirmed.
- **Review discussion:** Copilot inline comment r4360388886 (CRITICAL), no replies, not addressed at head.

### C49 — from find-security
- **Claim:** The Reveal Payload button (and the detail views generally) is not gated by the `key-manager:secrets:payload` permission, which is mapped server-side but never read by any client code. A user without payload rights still sees the button and the server procedure fetches the plaintext secret; only Barbican's own ACLs stop it.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:89`
- **Evidence:**

git grep of usePermissions/permissions[ under key-manager/ (at head) shows usage only in ContainersList, OrdersList and SecretsList (list/create/delete); SecretDetailsView, ContainerDetailsView and OrderDetailsView have none. `key-manager:secrets:payload` appears only in usePermissions.ts type and permissionRouter mappings.

### C12 — from find-standards
- **Claim:** Detail data is fetched in the component twice (route component and *DetailsView both call the same getX.useQuery) rather than in the route `loader`; the route has no loader, and the breadcrumb is set from a separately fetched copy.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/$containerId.tsx:19`
- **Evidence:**

A.3: "Data critical for rendering a page must be fetched via the route's loader function rather than loading it inside the component body." and (task) data the loader already fetched is not fetched again. Code: `$containerId.tsx:19 trpcReact.keyManager.getContainer.useQuery( etc)` and `ContainerDetailsView.tsx:31 trpcReact.keyManager.getContainer.useQuery( etc)`. Same for $secretId.tsx:19 / SecretDetailsView.tsx:24 and $orderId.tsx:19 / OrderDetailsView.tsx:22. B.7 allows tRPC useQuery, so severity is a judgement call.

### C13 — from find-standards
- **Claim:** Search input navigates on every keystroke (`onInput` -> navigate) with no local mirror state / debounce, producing a router navigation and a server request per character.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:104`
- **Evidence:**

B.9: "Use a local mirror state for debounced search inputs; sync back on external navigation via useEffect." Code: `onInput={(e) => onSearchChange((e.target as HTMLInputElement).value)}` where onSearchChange calls `navigate({ etc search: { search: value || undefined  etc}})`. Same ContainersList.tsx:74.

### C14 — from find-standards
- **Claim:** Ad-hoc spacing and styling classes outside the approved lists: `my-6` on the detail Stack, `mt-4` wrapper, `p-3`/`rounded`/`max-h-48` and `text-xs opacity-60` on payload/ID text, `items-end pr-0`, `jn:min-w-40`; `opacity-60` is used instead of a `text-theme-light` token.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:79`
- **Evidence:**

B.3: "Reject any use of ad-hoc mt-3, mb-5, px-6, etc. not listed above" (detail top offset is `mt-6`); B.4: "Muted / secondary text | text-theme-light". Code: `className="my-6"` (also ContainerDetailsView.tsx:62, OrderDetailsView.tsx:67), `<p className="text-sm opacity-60">` :97, `<pre className="bg-theme-background-lvl-2 max-h-48 overflow-auto rounded p-3 text-xs">` :98, key-manager.tsx:104 `className="mt-4"`, rows `text-xs opacity-60`.

### C15 — from find-standards
- **Claim:** Raw HTML elements are used where Juno components exist: `<div>` wrappers (layout, row cells, pagination wrapper), `<p>` bodies in modals and `<pre>` for the payload.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx:91`
- **Evidence:**

Quick Reject: "Raw HTML element (<div>, <table>, <button>) where a Juno component exists"; B.1 "Primary layout primitive | Stack". Code: `<div><ContentHeader  etc/>  etc <div className="mt-4">`; SecretTableRow.tsx:26-27 `<div>{secret.name  etc}</div><div className="text-xs opacity-60">`; SecretsList.tsx:127 `<div className="flex justify-center py-4">`; SecretDetailsView.tsx:88 `<div>` around the button.

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
- `same_as`: required for a candidate in a group above — the id of the candidate in the same group that describes the same problem (score that one, and leave its own `same_as` null — never point at another duplicate; this one is then dropped — `score` and `reason` may be left out for it), or `null` if it is a different problem. Elsewhere leave it out.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-3 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

