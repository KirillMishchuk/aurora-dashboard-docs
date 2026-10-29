# Scorer 2 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: scorer 2 of 9

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C6, C40

## Candidates

The evidence is as the finders reported it, unchanged.

### C6 — from find-standards
- **Claim:** The create modals mutate with no form validation and no inline errors: the confirm button is only disabled while pending. Bit Length is parsed with parseInt (NaN on empty), Algorithm may be empty, and fields are not marked required. Validation errors on the server show only as a Message at form top.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:52`
- **Evidence:**

B.11 Reject: "any form that mutates without validation"; B.5: "keep the primary/confirm button disabled while any required field is empty or any field fails validation". Code: `meta: { algorithm, bit_length: parseInt(bitLength, 10) }`, `disableConfirmButton={createMutation.isPending}`; no @tanstack/react-form / zod used. Secret and container create modals use useState with no validator at all.
- **Review discussion:** Copilot thread on OrderModals.tsx:52 (bit length validation).

### C40 — from find-discussion
- **Claim:** Create Order modal does not validate Bit Length: parseInt of empty or invalid input yields NaN, zero/negative values are accepted, and Create stays enabled; no inline error.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/orders/-components/OrderModals.tsx:52`
- **Evidence:**

Line 52 meta: { algorithm, bit_length: parseInt(bitLength, 10) }; disableConfirmButton only on isPending (line 57); no server-side check (meta is unrestricted).
- **Review discussion:** Copilot inline r4360389321, no replies, still applies.

### C7 — from find-standards
- **Claim:** The create modals do not follow the form standard (state in `useState` instead of @tanstack/react-form + Zod, no `autoFocus` on the primary input, inputs are not `disabled` while the mutation is in flight, no `required` markers).
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/containers/-components/ContainerModals.tsx:30`
- **Evidence:**

B.11: "Preferred: @tanstack/react-form with Zod schema validators", "`autoFocus` on the primary input. `disabled={isMutating}` on all inputs during in-flight mutations." Code: `const [name, setName] = useState("")`  etc TextInput has no autoFocus/disabled.

### C8 — from find-standards
- **Claim:** Create/delete success is silent: no toast is shown for create or delete of secrets, containers or orders; the modal just closes. The standard requires a confirming toast delegated to a `*ToastNotifications` helper for CRUD actions.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:35`
- **Evidence:**

B.16 table: "CRUD action confirmed (create, delete, update) | toast (transient)"; B.10: "All toast messages must be extracted to a dedicated <Resource>ToastNotifications.tsx"; B.11: "(modal) close and show a confirming toast". grep of the PR diff finds no `toast` and no *ToastNotifications file. onSuccess only calls invalidate()/onClose().
- **Precedent:** Network plugins ship *ToastNotifications files.

### C9 — from find-standards
- **Claim:** Row/list sort control is built from raw `Select` + `SortButton` instead of the required `SortInput` from `@/client/components/ListToolbar/SortInput`; Zone 1 is also `distribution="end"` rather than `"between"`.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:83`
- **Evidence:**

B.1 table: "Sort control | SortInput from @/client/components/ListToolbar/SortInput"; B.2: "Sort controls (SortInput) + primary action Button  etc distribution=\"between\"". Code uses `<Select label="Sort by"  etc>` + `<SortButton  etc/>` in `<Stack distribution="end"  etc className="jn:pb-2">`. Same in OrdersList.tsx:66. Containers list has no sort control at all although the PR body advertises sort for the lists.
- **Precedent:** floatingips/-components/FloatingIpsList.tsx and routers/-components/RoutersList.tsx import SortInput.

### C10 — from find-standards
- **Claim:** The permission-denied state for the list pages is rendered inline as a non-page-level warning `Message` with hardcoded English and no `mb-4`, instead of a 403 page-level error with an info `Message`; the copy also differs from the recommended 403 text.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:72`
- **Evidence:**

B.6 Reject: "a 401/403 handled inline instead of via redirect / page-level info Message"; 403 row: "plus an info Message explaining lack of access". Code: `<Message variant="warning">You do not have permission to view secrets.</Message>`. Same ContainersList.tsx:50, OrdersList.tsx:55. B.3 requires `mb-4` on Message banners.
- **Precedent:** Network lists use a Message for the same case ("You do not have permission to view security groups" in messages.po), so this may be accepted locally.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-2 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

