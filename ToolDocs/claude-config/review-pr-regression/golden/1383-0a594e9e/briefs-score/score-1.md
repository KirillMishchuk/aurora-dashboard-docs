# Scorer 1 — review-and-comment-pr, aurora-dashboard PR #1383

- Run folder: `<RUN>` — `context.json` (metadata, changed files, flags), `pr.diff` (the PR diff; generated files are left out and listed in `pr.generated_files_not_in_diff`), `pr-body.md`, `discussion.json`, `copilot-instructions.md`, `issue-1019.md` (issue #1019 — acceptance criteria)
- headRefOid: `0a594e9eaf3055cb1c9a102f1aceae43420e7870`
- baseRefOid: `a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd`

Read code at `headRefOid`, never from disk (the working tree is another branch). The full diff of one file: `git diff a21ba3ecf60155f47d0e6a7fe98da20ecd59b6bd...0a594e9eaf3055cb1c9a102f1aceae43420e7870 -- <path>`.

## Your role: scorer 1 of 4

The candidates below were found by other agents; you didn't find them and must not take their word for them. Read the scoring rules first — `.claude/skills/review-and-comment-pr/references/scoring.md` — all of it, and follow it. Then, for each candidate, open the cited code at headRefOid, re-run any command the evidence rests on, and score it.

Two rules scorers have broken before — apply them as written:

- **Precedent-table rule.** If a candidate matches a row of "Severity precedents" and the code does what the row describes, it is verified: score it at least 50 with the row's severity. "I can't tell whether it is hit in practice" is already priced into that severity — not a reason for 25.
- **Evidence rule.** When a candidate quotes an official API reference or the review standards and the code does what the quote says it must not, it is verified — score it on its impact (50, 75 or 100). "Can't run it" or "can't reach the docs" is never a reason for 25.

## Same place

These candidates point at the same place. For each, set `same_as` (see the result shape): the same problem, or a different one.

- C2, C3

## Candidates

The evidence is as the finders reported it, unchanged.

### C1 — from finder-a
- **Claim:** The detail route's loader already fetches the network via getById, and RouteComponent then fetches the same network again with trpcReact getById.useQuery. The loader only uses the result for the page title, so every detail visit makes two identical requests.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:124`
- **Evidence:**

A.3: 'Data critical for rendering a page must be fetched via the route's loader function rather than loading it inside the component body.' Loader line 124 calls context.trpcClient?.network.networks.getById.query; line 149 calls trpcReact.network.networks.getById.useQuery with the same input.

### C2 — from finder-a
- **Claim:** A 401 is handled inline: NetworkLoadError renders an error message ('The session has expired...') in the page instead of redirecting to Sign-in. 403 also renders a plain error page without the page-level info Message explaining the lack of access.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:65`
- **Evidence:**

B.6 Reject: 'a 401/403 handled inline instead of via redirect / page-level info Message'. Lines 63-66 map FORBIDDEN and UNAUTHORIZED to error descriptions in RouteIdLevelDefaultError.

### C3 — from finder-a
- **Claim:** The UNAUTHORIZED copy says 'Log in again to continue.' The UX writing rule requires 'Sign in', and the recommended 401 copy is 'Authentication failed. Verify your credentials and try again.'
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/$networkId.tsx:66`
- **Evidence:**

Quick Reject: 'String using ... "Sign In"/"Log in" (use "Sign in")'. B.19: '"Sign in", not "Sign In" or "Log in"'.

### C4 — from finder-a
- **Claim:** A raw <button> is used for the 'Try Again' action in the subnets error state, where Juno's Button exists. It has no Juno styling or variant.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:69`
- **Evidence:**

B.1 Reject: 'any PR that introduces a plain <table>, <input>, <select>, or <button> where a Juno equivalent exists.' Line 69: action={<button onClick={() => refetch()}>{t`Try Again`}</button>}. Quick Reject: 'Raw HTML element (<div>, <table>, <button>) where a Juno component exists'.

### C5 — from finder-a
- **Claim:** Raw <div> elements are used as layout wrappers (break-all wrapper in DetailsList, relative wrapper around ErrorBoundary in Networks) where Juno Stack/Container are the primary layout primitive.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworksList.tsx:223`
- **Evidence:**

B.1: 'Primary layout primitive | Stack'; Quick Reject: 'Raw HTML element (<div>...) where a Juno component exists'. NetworksList.tsx:223 <div className="relative">; NetworkDetailsView.tsx:38 <div className="break-all">{value}</div>.

### C6 — from finder-a
- **Claim:** The active detail tab is held in useState instead of the URL search params, so the Subnets tab is not shareable and is lost on refresh.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkDetailsView.tsx:109`
- **Evidence:**

B.9: 'All persistent UI state must live in URL search params' with 'Active tab | tab'; 'Reject any useState for state that should survive a page refresh or be shareable via URL.' Line 109: const [activeTab, setActiveTab] = useState<NetworkDetailsTab>("overview"). Quick Reject: 'URL-worthy state held in useState instead of search params'.

### C7 — from finder-a
- **Claim:** The row action menu uses <PopupMenu> without a PopupMenuToggle trigger (default toggle), contrary to the required pattern <PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle>.
- **Location:** `packages/aurora/src/client/routes/_auth/projects/$projectId/network/networks/-components/NetworkTableRow.tsx:56`
- **Evidence:**

Quick Reject: 'PopupMenu without PopupMenuToggle as trigger'; B.14: 'Context menus must use <PopupMenuToggle as="div"><Button icon="moreVert" /></PopupMenuToggle> as the trigger.' Lines 56-60 render <PopupMenu><PopupMenuOptions>...</PopupMenuOptions></PopupMenu> with no PopupMenuToggle; PopupMenuToggle is not imported.

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
python3 .claude/skills/review-and-comment-pr/scripts/save.py --run <RUN> --as score-1 <<'JSON'
{ …your JSON… }
JSON
```

`save.py` checks the JSON (shape, locations, code placeholders). If it prints errors, fix them and run it again. Then reply with only the line it prints.

