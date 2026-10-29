# Scorer 1 — review-and-comment-pr, aurora-dashboard PR #1393

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1133.md` (issue #1133 — acceptance criteria)
- headRefOid: `fd248f083f89fbe9caca6ad536106ffd08860159`
- baseRefOid: `c65b36d0e901a4bc41727d3a04317680175c05da`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff c65b36d0e901a4bc41727d3a04317680175c05da...fd248f083f89fbe9caca6ad536106ffd08860159 -- <path>`.

## Your role: scorer 1 of 9

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C1, C36
- C2, C3, C37

## Candidates

The evidence is as the finders reported it, unchanged.

### C1 — from find-standards
- **Claim:** Permission props are named `canDelete` instead of `can<Verb><Noun>` (canDeleteSecret / canDeleteContainer / canDeleteOrder), in the row and list-container props of all three resources.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:15`
- **Evidence:**

Quick Reject: "Permission prop not named `can<Verb><Noun>`"; B.8: "Boolean permission props must be named can<Verb><Noun> (e.g., canDeleteFlavor  etc)". Code: `canDelete: boolean`. Same in ContainerTableRow.tsx:15, OrderTableRow.tsx:15 and the three *ListContainer.tsx:12.
- **Precedent:** Network plugin uses `canDeleteRule` (SecurityGroupRulesTable).
- **Review discussion:** Copilot raised it on all six files (threads r4360388743, r4360388949, r4360389203, r4360389452, r4360389872, r4360389932).

### C36 — from find-discussion
- **Claim:** Boolean permission props are named canDelete instead of can<Verb><Noun> (canDeleteContainer/canDeleteSecret/canDeleteOrder), violating B.8.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:15`
- **Evidence:**

canDelete in Secret/Container/Order TableRow (line 15), ListContainer (line 12) and passed from Lists; copilot-instructions line 329 requires can<Verb><Noun>.
- **Review discussion:** Copilot inline threads r4360388743, r4360388949, r4360389203, r4360389452, r4360389872, r4360389932; no replies, unchanged.

### C2 — from find-standards
- **Claim:** Row action menus use `<PopupMenu>` without a `PopupMenuToggle` trigger, so the default toggle is used with no `<Button icon="moreVert" aria-label>`; the icon-only trigger has no accessible label.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:35`
- **Evidence:**

Quick Reject: "`PopupMenu` without `PopupMenuToggle` as trigger"; B.14: "Context menus must use <PopupMenuToggle as=\"div\"><Button icon=\"moreVert\" /></PopupMenuToggle>". Code: `<PopupMenu><PopupMenuOptions> etc`. Same in ContainerTableRow.tsx:34 and OrderTableRow.tsx:33.
- **Precedent:** Network floating IP / security group views import PopupMenuToggle.
- **Review discussion:** Copilot thread r4360388832 (OrderTableRow).

### C3 — from find-standards
- **Claim:** Delete menu item is neither labelled with the entity nor separated by a divider from the other item (single-entity menu): labels are `Delete` / `Show Details` rather than `Delete Secret` / `Show Secret Details`, and there is no `PopupMenuSectionSeparator` before Delete.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:38`
- **Evidence:**

B.18: "Single-entity menus  etc: separate the Delete action from the rest with a divider." and "Include the referenced entity in labels". Code: `{canDelete && <PopupMenuItem label={t`Delete`}  etc/>}` directly after `Show Details`. Same in Container/Order rows (line 37/36).
- **Review discussion:** Copilot r4360388832 mentions the separator.

### C37 — from find-discussion
- **Claim:** Row action PopupMenu has no PopupMenuToggle trigger (labelled more-actions button) and no PopupMenuSectionSeparator before destructive Delete, in the secret, container and order rows.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretTableRow.tsx:35`
- **Evidence:**

SecretTableRow.tsx:35-40 <PopupMenu><PopupMenuOptions> with Show Details and Delete only; imports lack PopupMenuToggle. copilot-instructions line 457 requires PopupMenuToggle as trigger.
- **Review discussion:** Copilot inline r4360388832 on OrderTableRow; same pattern in other rows.

### C4 — from find-standards
- **Claim:** Delete modals put the object name/ID in the title (`Delete Secret "${secretName}"`, `Delete Order "${orderId}"`) and the confirm label is a bare `Delete` / `Deleting...`; the standard says the object goes in the body and the confirm label should be verb + object type. The body doesn't name the entity at all (container/secret), and the order modal title shows a raw UUID.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:129`
- **Evidence:**

B.5: "Put the object name in the body, not the title.  etc Reference the affected entity by name/identifier in the body"; "Confirm labels: prefer verb + object type: Delete Image". Code: title={t`Delete Secret "${secretName}"`}, body `This action cannot be undone. The secret will be permanently deleted.` Same at ContainerModals.tsx:109, OrderModals.tsx:125.

### C5 — from find-standards
- **Claim:** None of the six modals pass `disableCloseButton` while the mutation is pending, so the close-X stays active and the user can dismiss the modal mid-request, while Cancel is disabled (they must be disabled together).
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/authorization/key-manager/secrets/-components/SecretModals.tsx:136`
- **Evidence:**

Quick Reject: "Modal without `disableCancelButton` / `disableCloseButton` during async operations"; B.5: "disable close-X and Cancel together". Code has `disableCancelButton={deleteMutation.isPending}` only. Same in SecretModals.tsx:60, ContainerModals.tsx:50/116, OrderModals.tsx:58/132.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-1 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

