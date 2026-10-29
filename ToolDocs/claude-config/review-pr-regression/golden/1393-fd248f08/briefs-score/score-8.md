# Scorer 8 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: scorer 8 of 9

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C54, C56, C58, C59, C60

## Candidates

The evidence is as the finders reported it, unchanged.

### C51 — from find-security
- **Claim:** Decrypted secret payload is fetched via a TanStack Query useQuery (enabled:false + refetch) and so stays in the client query cache after 'Hide' (default gcTime 5 min, also refetchable/shared across components), and is returned as `res.text()` which corrupts binary payloads. Plaintext secrets remaining in cache longer than needed is a data-protection concern; consider a mutation or gcTime:0 and clear on hide/unmount.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretDetailsView.tsx:34`
- **Evidence:**

setShowPayload(false) on Hide only toggles UI state; no cache removal or gcTime option on the query.

### C52 — from find-security
- **Claim:** ID/ref inputs interpolated into outbound Barbican paths are unvalidated `z.string()`; encodeURIComponent does not encode `.`, so `secretId`/`containerId`/`orderId`/`secretName` of `..` yields `v1/secrets/..` style paths that a URL normaliser collapses (e.g. DELETE v1/containers/.. -> v1/). Also secret_ref/secret_refs entries are arbitrary strings forwarded to Barbican, and `sort` is free text split into sort_key/sort_dir. Low impact (same project token, same service) but should be constrained with uuid()/regex.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:37`
- **Evidence:**

`const resourceIdInput = z.object({ secretId: z.string() })`, containerIdInput/orderIdInput the same; deleteContainerSecret uses `secretName: z.string()` in the path; addContainerSecret `secret_ref: z.string()`; pagination `offset`/`limit` are unbounded z.number() (no int/min/max).

### C53 — from find-security
- **Claim:** mapKmError attaches the raw upstream error as `cause` for every failure; if the tRPC error formatter or logger serialises causes this can expose OpenStack internals, and the secret payload in createSecret/updateSecret bodies could flow into logged errors. Worth confirming the error formatter strips `cause`.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:50`
- **Evidence:**

`return new TRPCError({ code: ..., message: ..., cause: error })`

### C54 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: tRPC BFF is implemented with complete Zod schema validation for Secrets, Containers, and Orders.
- **Location:** PR files
- **Evidence:**

`packages/aurora/src/server/KeyManager/types/keyManager.ts` defines schemas for all three, and list/get responses are parsed with `parseOrThrow`. But create/add-secret responses are cast (`data.secret_ref as string`) and the payload response has no schema. `updateSecret` only replaces payload, not metadata.

### C56 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: Users can list, view, create, update, and delete Secrets, Containers, and Orders (P1, P2 & P3).
- **Location:** PR files
- **Evidence:**

List, view, create and delete are implemented in the UI for all three. Update is missing in the UI: `updateSecret`, `addContainerSecret` and `deleteContainerSecret` exist on the server but no client code calls them, so there is no Edit Secret modal and no Manage Container Secrets flow. Create Secret has only name, type and payload (no algorithm, bit length, mode, content type or expiration); Create Container cannot attach secrets (`secret_refs: []`).

### C58 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: Comprehensive error handling provides user-friendly feedback for Barbican errors.
- **Location:** PR files
- **Evidence:**

Modals show `mutation.error.message` and lists show a `Status` error, but `mapKmError` in `keyManagerRouter.ts` discards Barbican's response body and returns a generic message like 'Key Manager delete container failed', so conflicts such as a container with secrets get no specific text.

### C59 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: All UI components follow the Aurora design system.
- **Location:** PR files
- **Evidence:**

Juno DataGrid, Modal and Status are used. Several visible strings in lists are not i18n-wrapped, for example 'Create Secret', 'Search by name...', 'Sort by' and the permission warning in `SecretsList.tsx`, and the sort labels in the `SORT_FIELDS` constant. Column header labels in `constants.ts` are plain strings too.

### C60 — from describer (acceptance)
- **Claim:** Acceptance criterion partly met: Complete testing coverage (unit, integration, E2E) is achieved.
- **Location:** PR files
- **Evidence:**

Unit tests are added for the router (`keyManagerRouter.test.ts`), the schemas (`keyManager.test.ts`) and the TableRow and ListContainer components of all three resources. No tests for the lists with permissions, modals, detail views, nav or the layout guard, and no E2E.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-8 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

