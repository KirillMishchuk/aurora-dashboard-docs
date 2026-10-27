# Describer — review-and-comment-pr, aurora-dashboard PR #1383

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `0a594e9eaf3055cb1c9a102f1aceae43420e7870`
- baseRefOid: `a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd...0a594e9eaf3055cb1c9a102f1aceae43420e7870 -- <path>`.

## Your role: the describer

You describe the change; you don't review it. Return the "what and how" narrative, the impact (blast radius), the QA plan and the acceptance grading.

Group the changed files by what they are (server routers, client routes/components, shared packages, config/CI, docs) and write the "what and how" narrative per group, not file-by-file — a PR that adds one tRPC procedure and wires it into two components reads better as one story than three disconnected file summaries.

For each meaningful piece of the change, quote a short excerpt (3–15 lines) and explain what it does in context — not just "this function was added" but why it matters (e.g. "this closes a race where two components could refresh the same session token — see the `sessionRescopes` cache added at `context.ts:280`"). Don't copy the code: put a placeholder on its own line — `[[code:<path>:<from>-<to>]]`, or `[[code:<path> | <text from its first line> | <number of lines>]]` when you know the text but not the line — and cite a line inline as `[[at:<path> | <text on that line>]]` or `` `<path>:<line>` ``. The code is inserted verbatim later and every citation is checked. Pick a distinctive piece of the line (a whole expression or string), not a bare identifier that also appears in imports.

**CI.** If `context.json` → `ci` shows failing or pending jobs on the head commit, say so briefly in `what`, and point it out if the PR description claims the opposite ("all tests pass"). Write every text field for the PR's readers: say "the head commit", "the PR description", "the linked issue" — never run-folder file names (`context.json`, `pr-body.md`, …) or field names (`headRefOid`); `save.py` rejects them.

**Impact / blast radius** — the part a plain diff can't tell you. For every changed export, tRPC procedure key, exported React component/hook, or public type in the diff, search for consumers _outside_ the PR's own changed files, across the whole monorepo at headRefOid:

```bash
git grep -n '<symbolName>' 0a594e9eaf3055cb1c9a102f1aceae43420e7870 -- . ':!pnpm-lock.yaml' ':!**/CHANGELOG.md' ':!**/locales/**'
```

Search the whole tree, not just `*.ts`/`*.tsx`: `packages/aurora/README.md` is the consumer-facing contract for public exports and `AuroraApp` props, and the policy files (`apps/dashboard/src/policies/*.json`) hold the permission keys. Report code consumers and documentation that describes the changed surface separately: which other packages/apps/routes depend on the changed surface, whether the PR updated all of them consistently or left a caller stale, and whether the change is internal-only versus a contract change that ripples outward (e.g. `AuroraRouter`, anything under `packages/aurora/src/server/*/routers/`, exported client hooks/components other apps import).

**QA test plan.** From the code you read, derive a manual test plan a reviewer can run — things unit tests can't easily cover (real OpenStack data, URL state, cross-view consistency, fallback rendering):

- **Core Path** — a numbered happy-path walkthrough, end to end, through the feature's main screens/actions.
- **Edge Cases** — states the code reveals: empty or missing fields, fallbacks, error routes. Cite `file:line` where a case comes from a specific branch in the code.

**Acceptance criteria.** Grade the PR against the acceptance criteria in `issue-1019.md`: for each criterion, met / partly met / unmet, with `file:line` evidence. Use "out of scope" only when `pr-body.md` explicitly limits the PR to part of the issue (e.g. "phase 1", "read-only part of #N") and the criterion falls outside that part — quote the limiting line from `pr-body.md` in `evidence`. An out-of-scope criterion is not a candidate; a partly met criterion inside the PR's own scope still is.

**Scope.** If `pr-body.md` (or the linked issue) limits this PR to part of an epic or issue — a phase, "read-only part of #N", "list and details only" — put that in `scope` as one short line: the epic/issue number and the part, e.g. `#816 — Phase 1, read-only`. Take it from what the description or issue says, not from what the diff happens to contain. Otherwise `null`.

## Result shape

```json
{
  "overview": {
    "what": "Markdown: the story of the change by area.",
    "how": "Markdown: walkthrough with [[code:…]] placeholders and citations.",
    "affects": "Markdown: consumers, contract changes, anything left inconsistent."
  },
  "qa": {
    "core_path": ["step without its number", "…"],
    "edge_cases": ["case without the leading dash, with `path:line` where it comes from a branch", "…"]
  },
  "acceptance": [
    { "criterion": "quoted from the issue", "status": "met | partly met | unmet | out of scope", "evidence": "`path:line` and why" }
  ],
  "stale_callers": [
    { "symbol": "name", "location": "path:line", "note": "what's stale" }
  ],
  "scope": "#816 — Phase 1, read-only, or null"
}
```

## Saving your result

Your result goes to a file, not into your reply. When you're done, save it — this is the only file you write:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as describer <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

