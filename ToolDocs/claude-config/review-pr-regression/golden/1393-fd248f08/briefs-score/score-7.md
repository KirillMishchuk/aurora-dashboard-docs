# Scorer 7 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: scorer 7 of 9

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C33, C42

## Candidates

The evidence is as the finders reported it, unchanged.

### C33 — from finder-d
- **Claim:** deleteContainerSecret DELETEs v1/containers/{id}/secrets/{secretName}; Barbican's removal endpoint is DELETE /v1/containers/{uuid}/secrets with name and secret_ref in a JSON body, so association removal will fail.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:252`
- **Evidence:**

Line 252: .del(`v1/containers/${containerId}/secrets/${secretName}`) with input only containerId+secretName; the test asserts the same URL.
- **Review discussion:** Copilot inline r4360389656, no replies, still applies.

### C42 — from finder-f
- **Claim:** deleteContainerSecret calls DELETE /v1/containers/{id}/secrets/{secretName}; Barbican documents removal as DELETE /v1/containers/{container_uuid}/secrets with a JSON body {name, secret_ref}. The path-segment form is not in the reference, so removing a secret from a container likely fails (404/405) and the UI action is broken.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:252`
- **Evidence:**

Code at fd248f08: `.del(`v1/containers/${encodeURIComponent(input.containerId)}/secrets/${encodeURIComponent(input.secretName)}`)`; input has only containerId and secretName, no secret_ref. Reference (https://docs.openstack.org/barbican/latest/api/reference/containers.html, source https://raw.githubusercontent.com/openstack/barbican/master/doc/source/api/reference/containers.rst, section 'DELETE /v1/containers/{container_uuid}/secrets'): 'Remove a secret from a container.  This is only supported on generic containers.' Request attributes: 'secret_ref | uri | (required) Full URI reference to an existing secret.' Request: 'DELETE /v1/containers/{container_uuid}/secrets ... Content: { "name": "private key", "secret_ref": "https://{barbican_host}/v1/secrets/{secret_uuid}" }'; 400 'Missing secret_ref'. No `/secrets/{name}` path appears in that file.

### C34 — from finder-d
- **Claim:** Container secret_refs schema requires name: string, but Barbican may return name: null for unnamed references; parseOrThrow would then reject the whole container/list response.
- **Location:** `packages/aurora/src/server/KeyManager/types/keyManager.ts:25`
- **Evidence:**

Line 25: secret_refs: z.array(z.object({ name: z.string(), secret_ref: z.string() })), while sibling name fields use .nullable().
- **Review discussion:** Copilot inline r4360389713, no replies, still applies.

### C43 — from finder-f
- **Claim:** listContainers sends a `name` filter, but the Containers list documents only offset and limit. The search box would be silently ignored by Barbican (or the BFF would need to filter itself), so users see unfiltered results.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:167`
- **Evidence:**

Code: `if (input.name) params.set("name", input.name)` in listContainers. Reference (containers.rst, 'GET /v1/containers' Parameters table): only 'offset | integer | The starting index within the total list of the containers...' and 'limit | integer | The maximum number of containers to return (up to 100). The default limit is 10.' No name filter. By contrast the Secrets list documents 'name | string | Selects all secrets with name similar to this value.' (secrets.rst).

### C46 — from finder-f
- **Claim:** updateSecret uses PUT /v1/secrets/{id}, which the reference restricts to metadata-only secrets without a payload; the router offers it for any secret, so editing a secret that already has a payload fails (400/409), surfacing as a generic error. It also never sends Content-Encoding, so binary/base64 payloads cannot be stored.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:137`
- **Evidence:**

Code: `.put(`v1/secrets/${encodeURIComponent(input.secretId)}`, input.payload, { headers: { "Content-Type": input.payload_content_type } })`. Reference (secrets.rst 'PUT /v1/secrets/{uuid}'): 'Add the payload to an existing metadata-only secret, such as one made by sending a POST /v1/secrets request that does not include the ``payload`` attribute.' and note 'This action can only be done for a secret that doesn't have a payload.' Headers table lists optional 'Content-Encoding'. Documented status codes: 204, 401, 404 only.

### C47 — from finder-f
- **Claim:** CreateOrderInputSchema accepts type "certificate", but the Orders reference documents only key and asymmetric as valid order types.
- **Location:** `packages/aurora/src/server/KeyManager/types/keyManager.ts:91`
- **Evidence:**

Code: `type: z.enum(["key", "asymmetric", "certificate"])`. Reference (orders.rst 'POST /v1/orders' Parameters): 'type | string | The type of key to be generated. Valid types are key and asymmetric'. (Other Barbican docs may describe certificate orders; this orders reference page does not.)

### C48 — from finder-f
- **Claim:** List calls accept any numeric limit/offset (z.number() without .max(100)/.min(0)); Barbican caps limit at 100, so a client-supplied larger value is silently clamped and `total`-based paging math (PAGE_SIZE) would be off. Current UI uses 50 so impact is only for other callers.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:21`
- **Evidence:**

Code: `limit: z.number().default(20)`. Reference (secrets.rst/containers.rst/orders.rst): 'limit | integer | The maximum number of records to return (up to 100). The default limit is 10.' Pagination: code sends offset/limit (consistent with the documented offset/limit), UI page size 50 (OrdersList.tsx:17); `next`/`previous` are parsed in the schema but unused.

### C50 — from finder-g
- **Claim:** None of the KeyManager mutations or the payload query enforce a server-side canUser/policy check; they rely only on projectScopedProcedure and Barbican's own authorization. The policy file key-manager.json (viewer/editor split) is therefore advisory UI-hiding only, including for getSecretPayload (plaintext key material) and delete/create/update.
- **Location:** `packages/aurora/src/server/KeyManager/routers/keyManagerRouter.ts:93`
- **Evidence:**

All procedures in keyManagerRouter.ts go straight from projectScopedProcedure to km.get/post/put/del with no call to the policy engine; permissionRouter.ts only exposes the canUser query.
- **Precedent:** Network routers (e.g. floatingIpRouter) also do not call the policy engine in mutations, so this matches existing convention, but the review rubric requires server enforcement.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-7 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

