# Scorer 5 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: scorer 5 of 9

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C21, C27, C35, C41
- C22, C39

## Candidates

The evidence is as the finders reported it, unchanged.

### C21 — from find-standards
- **Claim:** The Authorization nav entry does not honour service-visibility configuration (`isEnabled` / enabledServices / deniedServices) like the other in-core entries.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:153`
- **Evidence:**

Code: ` etc(serviceIndex["key-manager"]?.["barbican"] ? [{ etc}] : [])` with no isEnabled call. Part A/CLAUDE.md: `enabledServices` whitelists which services show in the nav.
- **Precedent:** Other in-core entries use isEnabled in the same file.
- **Review discussion:** Copilot thread r4360389607.

### C27 — from find-history
- **Claim:** The new Authorization > Key Manager nav entry is gated only on the catalog (serviceIndex["key-manager"]["barbican"]) and skips isEnabled(...). Since #1370, every built-in item and every extension is filtered by enabledServices/deniedServices, so a consumer cannot hide Key Manager via appConfig deny list or enabledServices allowlist (the allowlist would still show it).
- **Location:** `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`
- **Evidence:**

At base c65b36d0, buildNavSections.ts lines 29-33 define isEnabled with the comment 'Deny always wins and applies even without an allow/enabled list'; images, flavors, securitygroups, floatingips, routers, containers and ceph-containers all use `&& isEnabled("<key>")`, and extensions check enabledServices/deniedServices (lines 154-155, added in b4b47df6 #1370). The PR diff for this file adds the key-manager item with no isEnabled call. The PR does not touch README 'Service key reference' either.
- **Precedent:** routers/securitygroups/floatingips entries in the same file use isEnabled.

### C35 — from find-discussion
- **Claim:** Key Manager nav entry ignores isEnabled, so enabledServices/deniedServices cannot hide it, unlike the other entries.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`
- **Evidence:**

Line 154: serviceIndex["key-manager"]?.["barbican"] ? ... with no && isEnabled(...); other entries at lines 36,46,60,71,82,97,119 use isEnabled.
- **Review discussion:** Copilot inline r4360389607, no replies, still applies.

### C41 — from find-code-comments
- **Claim:** The new Key Manager nav item is gated only on the service catalog and skips isEnabled("key-manager"). The comment above isEnabled says deny always wins and a service can be hidden by deniedServices alone, but enabledServices/deniedServices have no effect on Key Manager, so an operator cannot hide it or exclude it from an allowlist.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/-components/buildNavSections.ts:154`
- **Evidence:**

Comment at lines 29-31 at fd248f08: "Deny always wins and applies even without an allow/enabled list, so a service can be hidden by deniedServices alone ... see resolveServiceVisibility." Every other built-in item uses `&& isEnabled(...)` (images, flavors, securitygroups, floatingips, routers, containers, ceph-containers). The new entry uses only `serviceIndex["key-manager"]?.["barbican"]`. The route beforeLoad in key-manager.tsx also checks only the catalog, so a denied service stays reachable by URL.
- **Precedent:** Extensions at lines 176-178 check both enabledServices and deniedServices.

### C22 — from find-standards
- **Claim:** Page-state recovery after deletion: list URL `page` is not clamped when the last row of the last page is deleted, leaving an empty table with no pagination.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:126`
- **Evidence:**

B.9 (URL state must stay consistent) ; Code: `{totalPages > 1 && (<Pagination  etc/>)}` with `page` coming from the URL and no clamp after invalidate.
- **Review discussion:** Copilot threads r4360389254, r4360389387, r4360389532.

### C39 — from find-discussion
- **Claim:** After deleting the last item on the final page the URL page stays beyond the new total; pagination is hidden (totalPages <= 1) and the table is empty with no way back. Same in Secrets, Containers and Orders lists.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:126`
- **Evidence:**

SecretsList.tsx:62 offset=(page-1)*PAGE_SIZE, line 75 totalPages from data.total, line 126 {totalPages > 1 && Pagination}; no clamp/reset of page on delete or total shrink.
- **Review discussion:** Copilot inline r4360389532, r4360389254 (ContainersList:91), r4360389387 (OrdersList:97); no replies.

### C23 — from find-standards
- **Claim:** The PR body checklist leaves the tests, docs, warnings and 'commented my code' items unchecked even though tests are added, and the Testing Instructions are only generic commands. No changeset is mentioned (memory: house style says no changesets in descriptions).
- **Location:** PR body
- **Evidence:**

pr-body.md Checklist: `- [ ] I have added tests that prove my fix is effective or that my feature works.` and `- [ ] New and existing unit tests pass locally with my changes.` while the PR adds *.test.ts(x) files.

### C24 — from find-diff-bugs
- **Claim:** SearchInput wires both onSearch and onInput to onSearchChange, and onSearchChange navigates, so every keystroke changes the URL, resets page and fires a new listSecrets request (and likely adds a history entry per character). Typing a name causes request churn and a polluted back-history.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretsList.tsx:109`
- **Evidence:**

SecretsList.tsx: SearchInput has onSearch, onClear and onInput all calling onSearchChange; handleSearch in secrets/index.tsx calls navigate({search:{search:value,...}}) with no debounce or replace. Same pattern likely in containers list.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-5 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

