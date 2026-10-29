# earlier-findings — status of the earlier findings — review-and-comment-pr, aurora-dashboard PR #1377

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1380.md` (issue #1380 — acceptance criteria), `issue-1381.md` (issue #1381 — acceptance criteria), `issue-1382.md` (issue #1382 — acceptance criteria), `issue-816.md` (issue #816 — acceptance criteria), `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `86a355a8d6da94478e77c0869d9720efe6823e2a`
- baseRefOid: `af14a6a0d76d4a3019d8b49308d503e7247bc338`
- **Scope: this is an Update.** Analyze only the new commits — `delta.diff`: the range `512f01b1bd79771fbf6b959225231e777c2c7c42..86a355a8d6da94478e77c0869d9720efe6823e2a` limited to the PR's own files, with what a merge of the base branch changed in them taken out, so code that came in with a merge of the base branch is left out — don't diff the range yourself.

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff af14a6a0d76d4a3019d8b49308d503e7247bc338...86a355a8d6da94478e77c0869d9720efe6823e2a -- <path>`.

## Your role: the earlier findings

This is an Update: the report it extends already raised the findings below, at an older head. You do one thing — for each of them, check the code at headRefOid (the code as it is now, not only the diff) and the replies to it in the review discussion (`discussion.json`: comments, reviews and threads after the report that name it — "I14", the finding's subject), and say whether it still holds:

- `fixed` — the code no longer does what the finding says;
- `partly` — part of it is fixed and part still holds; the note says which part is left;
- `open` — it still holds as written;
- `dropped` — only in three cases: a finding about merge conflicts (with `main` or with other open PRs) or about the PR being a draft — this review no longer covers them; don't check it, the note is "Merge conflicts are no longer part of this review; GitHub shows them." or "Draft state is no longer part of this review; a draft can't be merged anyway." — or a finding a maintainer (a reviewer other than the PR's author, not a bot) asked to do differently in the review discussion (`discussion.json`): the note is "Reversed by <login> in <url>." with the comment's or review's url — or an Improvement (`I…`) or Process item (`P…`) that the author or a maintainer explicitly kept as is in the discussion, with a reason (intentional, documented, out of scope, follow-up): the note is "Kept as is by <login>: <their reason in a few words> (<url>)." A Required Change (`CR…`) is not closed by the author's word: it stays `open` (or `partly`), and the note may add the author's position with the url.

Line numbers in the list are from the older head and may have moved: find the code by what the finding describes, not by the number. Process items: changeset against `context.json` (`changeset`), claims about the PR description against `pr-body.md`.

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

## Result shape

```json
{
  "earlier": {
    "CR1": {"status": "fixed", "note": "One line: what changed, or what is left.", "evidence": "The command you ran and the lines of its output that show it."}
  }
}
```

- Every finding listed above exactly once — `save.py` refuses a result with one left out or one that isn't listed.
- `note` is one line for the report's reader. Name other earlier findings by their number (`CR2`); don't make up numbers.

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as earlier-findings <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

