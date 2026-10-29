# pr-description — PR description vs code — review-and-comment-pr, aurora-dashboard PR #1377

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1380.md` (issue #1380 — acceptance criteria), `issue-1381.md` (issue #1381 — acceptance criteria), `issue-1382.md` (issue #1382 — acceptance criteria), `issue-816.md` (issue #816 — acceptance criteria), `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `86a355a8d6da94478e77c0869d9720efe6823e2a`
- baseRefOid: `af14a6a0d76d4a3019d8b49308d503e7247bc338`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `512f01b1bd79771fbf6b959225231e777c2c7c42..86a355a8d6da94478e77c0869d9720efe6823e2a` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff af14a6a0d76d4a3019d8b49308d503e7247bc338...86a355a8d6da94478e77c0869d9720efe6823e2a -- <path>`.

## Your role: the PR description check

You do one thing: compare what the PR description (`pr-body.md`) says the PR does with what the code at headRefOid does. You don't review the code itself — other agents do that. Two kinds of mismatch:

- `not in code` — the description claims a change, behaviour or fix that the code doesn't have, or has differently (e.g. it lists an operation no procedure implements, or says an area is "unchanged" when the PR changes it). Copy the claim into `quote` verbatim from `pr-body.md`, one sentence or list item at most — `save.py` refuses a quote it can't find there.
- `not described` — a whole area the PR changes that the description doesn't mention at all (e.g. a Ports PR that also reworks the Routers list). Not single files, refactoring inside a described feature, tests, docs, translation catalogs, lockfiles, generated files or formatting. `location` is one `path:line` of that change at headRefOid.

Read each claim within the section it sits in: a bullet under a "BFF" or "server" heading speaks about the server code, one under "UI" about the client. "X is unchanged except …" under the BFF heading is true when X's server code changes only in that way, even if X's UI changes — and the UI changes are then described elsewhere, not contradicted. A claim is a mismatch only when the code contradicts it within its own section's scope; check such "unchanged" / "only" sentences against the diff of that part of the code.

Not a mismatch: wording vaguer than the code; a claim the code meets in another way; claims about tests or CI (CI is reported elsewhere); plans for later PRs ("in a follow-up", "phase 2"); the linked issue's acceptance criteria (graded elsewhere).

**This is an Update.** `not in code`: check the whole description against the code at headRefOid — the author may have edited either. `not described`: only areas the new commits (`delta.diff`) change. The report already raised the findings below; leave out a mismatch one of them covers (another agent rechecks those):

- CR1 🟡 Moderate — Ports list reads one Neutron page only; ports and search hits beyond it silently disappear — `packages/aurora/src/server/Network/routers/portsRouter.ts:65`
- CR2 🟡 Moderate — 401/403 rendered inline on the details page and as a list error (B.6 Reject) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:64`
- CR3 🟡 Moderate — Details route fetches the port twice (loader + `useQuery`), ~8 Neutron requests per open — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:127`
- CR4 🟡 Moderate — Merge conflicts with `main` (locales) and with open PRs #1383 / #1385 (`routers/index.ts`) — `packages/aurora/src/server/Network/routers/index.ts:17`
- P1 — — PR is still a draft — PR state
- P2 — — Description doesn't mention that the Router details tab now lives in the URL (`?tab=`) — PR body
- I1 🟢 Low — "Log in again to continue." — Quick Reject wording (use "Sign in") — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/$portId.tsx:71`
- I2 🟢 Low — `PopupMenu` without `PopupMenuToggle` trigger (Quick Reject) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortTableRow.tsx:79`
- I3 🟢 Low — `gap="1"` is not an approved spacing value (Quick Reject, B.3) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortDetailsView.tsx:51`
- I4 🟢 Low — Status is the 6th of 7 columns; B.15 puts status near the left — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:84`
- I5 🟢 Low — Routers doc still says names come from "one request" — now chunked by 50 — `packages/aurora/docs/0010_routers_bff.md:80`
- I6 🟢 Low — Ports doc error tables drop the `: {Neutron message}` suffix — `packages/aurora/docs/0017_ports_bff.md:103`
- I7 ⚪ Trivial — `useEffect` mirrors the `currentPage` prop into state — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/-components/PortListContainer.tsx:37`
- I8 ⚪ Trivial — `zod` imported after the Lingui imports (B.13 order) — `packages/aurora/src/client/routes/_auth/projects/$projectId/network/ports/index.tsx:4`

Check each claim in the code, not in the diff summary: `git show 86a355a8d6da94478e77c0869d9720efe6823e2a:<path>`, `git grep -n '<text>' 86a355a8d6da94478e77c0869d9720efe6823e2a -- <path>`. Go through the description claim by claim, then through the changed areas (`git diff --stat af14a6a0d76d4a3019d8b49308d503e7247bc338...86a355a8d6da94478e77c0869d9720efe6823e2a`, or `delta.diff` on an Update) for ones it doesn't mention.

## Result shape

```json
{
  "mismatches": [
    {
      "kind": "not in code",
      "quote": "Verbatim from the PR description (only for `not in code`).",
      "location": "path:line (only for `not described`)",
      "issue": "One line, at most 120 characters: what doesn't match.",
      "explanation": "One or two sentences for the PR's readers: what the description says and what the code does, with `path:line`.",
      "fix": "What to change: usually the description (mention the area, drop or correct the claim); the code only when the description is clearly the intent.",
      "evidence": "The commands you ran and the lines of their output that show it."
    }
  ]
}
```

- Every field except `evidence` can be posted: write "the PR description", "the head commit" — never run-folder file names or this review's step names; `save.py` rejects them.
- No mismatches: `{"mismatches": []}`.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as pr-description <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

