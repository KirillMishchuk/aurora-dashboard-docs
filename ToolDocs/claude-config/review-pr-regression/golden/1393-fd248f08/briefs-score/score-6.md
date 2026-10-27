# Scorer 6 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: scorer 6 of 9

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C26, C44
- C31, C32, C45

## Candidates

The evidence is as the finders reported it, unchanged.

### C25 — from finder-b
- **Claim:** getSecretPayload reads the secret with res.text() and returns it as a tRPC query result, so binary secrets (e.g. application/octet-stream, symmetric keys) are corrupted by UTF-8 decoding and shown as garbage; the plaintext payload also gets cached in the TanStack Query cache.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:103`
- **Evidence:**

keyManagerRouter.ts lines 102-104: `const text = await res.text(); return { payload: text, contentType }`; no Accept header is sent and no binary/base64 handling.

### C26 — from finder-b
- **Claim:** listOrders translates `sort` into sort_key/sort_dir query params, but Barbican's orders list API only supports offset and limit, so the orders sort control is likely a no-op.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:269`
- **Evidence:**

keyManagerRouter.ts lines 269-273 set sort_key/sort_dir; Barbican API reference for GET /v1/orders lists only limit and offset (from memory, not verified online).

### C44 — from finder-f
- **Claim:** listOrders translates `sort` into sort_key/sort_dir query params, which the Orders list does not document (it documents only offset and limit; the `sort` param of secrets uses `key:dir` in one `sort` param, not sort_key/sort_dir). The sort selector on the orders page therefore has no documented effect.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:269`
- **Evidence:**

Code: `const [sortKey, sortDir] = input.sort.split(":")` then `params.set("sort_key", sortKey)` / `params.set("sort_dir", sortDir)`. Reference (https://docs.openstack.org/barbican/latest/api/reference/orders.html, orders.rst 'GET /v1/orders' Parameters): only 'offset' and 'limit | The maximum number of records to return (up to 100). (Default is 10)'. Secrets.rst 'Sorting': 'The value of the ``sort`` parameter is a comma-separated list of sort keys... Each sort key may also include a direction... ``:asc`` / ``:desc``' - sort_key/sort_dir are not documented anywhere in the secrets/containers/orders reference files. UI offers only SORT_FIELDS = [{ value: "created" }] (OrdersList.tsx:19).

### C28 — from finder-c
- **Claim:** The project landing page (projects/$projectId/index.tsx) builds service cards per service with the same isEnabled gating, but the PR does not touch it, so Key Manager gets a nav entry but no card on the project overview. The key-manager layout beforeLoad also checks only the catalog, not enabled/denied services, so a denied service stays reachable by URL.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager.tsx:46`
- **Evidence:**

At base c65b36d0, routes/_auth/projects/$projectId/index.tsx lines 56-110 push a card (group Compute/Network/Storage/Services) for each service under isEnabled; `git diff --stat` for the PR shows no change to that index.tsx (only key-manager/*/index.tsx files). #1370 touched both buildNavSections.ts and this index.tsx together to keep them in sync.

### C30 — from finder-d
- **Claim:** Key Manager server procedures never evaluate the loaded policy; canUser is registered but each handler (incl. getSecretPayload, deleteContainerSecret, createSecret) only uses projectScopedProcedure, so permission gating is UI-only and a direct tRPC call bypasses Aurora policy.
- **Location:** `packages/aurora/src/server/KeyManager/routers/index.ts:8`
- **Evidence:**

git grep for policy|canUser|FORBIDDEN in server/KeyManager shows only permissionRouter wiring and mapKmError 403 mapping; no handler checks a rule.
- **Precedent:** Not checked whether Compute/Storage routers enforce server-side.
- **Review discussion:** Copilot inline r4360389025 (CRITICAL), no replies, still applies.

### C31 — from finder-d
- **Claim:** getSecretPayload (and other calls) use the session default Accept: application/json; Barbican's payload endpoint serves raw secret content and can return 406 for non-JSON payloads. The response is also read with res.text() with no Accept override.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`
- **Evidence:**

context.ts:116 sets default Accept: application/json; keyManagerRouter.ts:98 km.get(`v1/secrets/${id}/payload`) passes no headers.
- **Review discussion:** Copilot inline r4360389136, no replies, still applies. Behaviour with Barbican unverified live.

### C32 — from finder-d
- **Claim:** Secret payload plaintext can be logged: signal-openstack logs a bodyPreview for text responses when debug is on, and debug defaults to true outside production; getSecretPayload does not disable it.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`
- **Evidence:**

signal-openstack/src/client.ts:169-183 builds bodyPreview from text; context.ts:114 debug: config.debug ?? NODE_ENV !== "production".
- **Review discussion:** Copilot inline r4360389080 (CRITICAL), no replies, still applies in non-production.

### C45 — from finder-f
- **Claim:** getSecretPayload does not send an Accept header; the reference says the Accept header must be set to one of the secret's content_types for GET /payload. signal-openstack adds no Accept header, so the call can return 406 (mapped to INTERNAL_SERVER_ERROR) or the wrong content type. Also mapKmError has no mapping for 406/415, which the reference lists for these endpoints.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:98`
- **Evidence:**

Code: `km.get(`v1/secrets/${encodeURIComponent(input.secretId)}/payload`)` with no options/headers; grep of packages/signal-openstack/src/client.ts shows only a Content-Type default, no Accept. Reference (secrets.rst 'GET /v1/secrets/{uuid}/payload'): 'When making a request for a secret's payload, you must set the accept header to one of the values listed in the ``content_types`` attribute of a secret's metadata.' Status codes: '406 | Not Acceptable'; POST /v1/secrets lists '415 | Unsupported media-type'. mapKmError codeMap covers only 400/401/403/404/409 (lines 43-49).

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-6 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

