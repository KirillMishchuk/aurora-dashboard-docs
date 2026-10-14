---
name: document-pr
description: >-
  Document and review an open pull request against aurora-dashboard (by
  number, URL, or the current branch's PR) via `gh`, producing one
  English-language report that (1) describes what the PR does and how —
  with verbatim code excerpts and file:line citations — (2) traces what it
  impacts, including consumers elsewhere in the monorepo, and (3) reviews
  it for bugs, project-convention compliance, external-API contract and
  security issues, using confidence-scored findings. Saves the report in
  ../DOCS/aurora-dashboard-kb/prs/ and updates its index. Re-running it on
  a PR that already has a report updates that report (new commits, or the
  PR was merged or closed). Use when the user asks to document, разобрать,
  задокументировать, проанализировать a specific PR. Not for uncommitted
  local changes — that's `triple-review`.
---

# Document a pull request

Produce one markdown report per PR that a future reader — Kiryl or Claude in
a later session — can open instead of re-reading the PR on GitHub. It has two
halves: a descriptive walkthrough (what changed, how, what it touches) and a
review pass (real bugs and conventions issues, confidence-filtered so it
doesn't read like lint noise). Output goes to the knowledge base at
`../DOCS/aurora-dashboard-kb/prs/`, alongside the KB maintained by
`update-kb` — same repo, same audience, same "verify against real code, not
commit messages" discipline.

## Requirements

- **`gh`, signed in to GitHub.** Everything about the PR comes through it.
  If `gh pr view` in Step 1 fails with an auth error, stop and tell the
  user to run `gh auth login`.
- **The `DOCS` folder next to the repo** (`../DOCS/aurora-dashboard-kb/prs/`,
  resolved from the repo root as in Step 1). If it's missing, stop before
  any analysis — there is nowhere to write the report.
- **The `security-reviewer` agent** (`.claude/agents/security-reviewer.md`)
  for Step 5. Optional: without it, agent g uses the fallback described
  there.

## Hard rules

- **Never check out the PR branch or touch the user's working tree/HEAD.**
  Everything here is read-only: `gh pr view`/`gh pr diff` for metadata and
  diff, `git fetch origin <sha>` + `git show <sha>:<path>` / `git grep -n
  <pattern> <sha> -- <pathspec>` for reading the repo at the PR's head commit
  without checking it out. If the user is mid-work on another branch, this
  skill must not disturb that.
- **Verify against real code, not the PR description or commit message.**
  Descriptions oversell or drift; the diff and the files at the head commit
  are ground truth.
- **Code excerpts must be verbatim**, pulled from `git show <sha>:<path>` (or
  the diff itself), with accurate `file:line` citations — don't hand-compute
  line numbers from diff hunk headers, they lie once you're looking at
  the whole file. Get real line numbers from `git grep -n` against the head
  commit — `git grep -n '' <sha> -- <path>` prints a whole file numbered.
- **Findings need a confidence pass before they're reported as issues** (see
  Step 5). An unfiltered "here's everything that looks off" list is not a
  review, it's noise — this mirrors the `code-review` plugin (`/code-review`).
- Report body is English (`DOCS/CLAUDE.md` rule 1), whatever language the
  user asks in. Code, identifiers and file paths stay as-is.
- **Don't commit or push** — neither `DOCS` nor the repo. The skill stops
  at writing files (`DOCS/CLAUDE.md` rule 10); committing is the user's call.
- **Write commands the allowlist can match.** Put SHAs and paths literally
  into each command — no `VAR=…;` prefixes, no `cd … &&` chains (run from
  the repo root). Shell variables don't survive between commands anyway.
  Repeat this rule in the brief of every agent you launch (review agents,
  scorer, fact-checker): they start in the repo root already and must not
  `cd` there.

## Steps

### 1. Resolve the PR

Accept whatever the user gave you — a bare number (`1079`), a full URL, or
nothing (meaning "the PR for the current branch"). `gh pr view <arg>` accepts
all three forms directly, so you rarely need to parse it yourself.

```bash
gh pr view <arg> --json number,title,body,author,url,state,isDraft,\
baseRefName,headRefName,baseRefOid,headRefOid,mergedAt,mergeCommit,\
mergedBy,additions,deletions,changedFiles,files,createdAt
```

If `baseRefName` isn't `main`, don't refuse — note it prominently near the
top of the report (the skill's normal case is PRs into `main`, but a
different base is just a fact to surface, not a blocker).

**Scope: open PRs.** The full analysis is for open (including draft) PRs —
documenting a PR after it has landed has no use here. A merged or closed
PR only matters if it already has a report, whose status then needs
updating (below). If it has none, tell the user there is nothing to
document and stop.

**Where DOCS is.** Resolve it from the repo root, not from the shell's
current directory — a bare `../DOCS` typed from a subdirectory folds into
this repo's own git-tracked `docs/` folder on macOS:

```bash
git rev-parse --show-toplevel
```

`DOCS` is that path's parent directory + `/DOCS`. Note the absolute path
now and write it out literally in every later command and file path
(`<DOCS>` below) — shell variables don't survive from one command to the
next.

**Existing report?** Before any analysis, check whether this PR already
has one:

```bash
ls -d <DOCS>/aurora-dashboard-kb/prs
ls <DOCS>/aurora-dashboard-kb/prs/<number>-*.md
```

If the first `ls` fails, stop — there is nowhere to write the report (see
Requirements). If the second finds nothing, do the full run below. If a
report exists, read its frontmatter `status`, its `**Status:**` line (the
only place that says "draft") and its old head: the SHA after the last
`updated for` in the `Analyzed:` footer, otherwise the SHA after `commit`
— ignore SHAs marked "not analyzed" or "previous versions". Compare them
with what `gh pr view` just returned and take the matching path:

- **Same head, same status** — the report is current. Tell the user and
  ask whether to stop or re-run from scratch; a re-run overwrites the
  report, so only on an explicit yes.
- **Same head, only draft ↔ ready changed** — update the `**Status:**`
  line and the index row's Date cell (Step 7); nothing else. Then report
  back (Step 8).
- **Now merged or closed** — a status update only, which `DOCS/CLAUDE.md`
  rule 2 allows: set `status` in the frontmatter, the `**Status:**` line
  (e.g. `merged 2026-10-14`) and the index row's Date cell (Step 7), and
  append ` · status updated <today>: <merged | closed>` to the footer. If
  the head moved after the last analysis, add
  ` · last head <short sha> not analyzed`. Nothing else in the body
  changes, and no other step runs — report back (Step 8) and stop.
- **Different head** (new commits since the report) — don't rewrite the
  existing text (rule 2: reports are historical records). Fetch the new
  head (Step 2) and analyze only `git diff <old head>..<new head>`: Steps
  4–5 on that delta, the Step 6 fact-check on the new section. Append it
  before the footer in this shape:

  ```markdown
  ## Update — <today>, head `<short sha>`

  ### What changed
  <what the new commits do and how, with excerpts — same rules as Step 4>

  ### Fixed since last analysis
  <earlier findings the new commits fixed, by number; or "None">

  ### Review
  <findings ≥75 and "Below the bar", same format as the main Review>

  ### Proposed follow-ups
  <same format as the main list, for this Update's findings only>
  ```

  Update the status if it changed, the footer
  (`… · updated for <short sha> on <today>`) and the index row. If the
  old head is no longer reachable (a force-push rewrote history), tell
  the user and analyze the whole PR diff into the Update section instead.

### 2. Get the diff and the head commit locally

```bash
gh pr diff <number>
git fetch origin <headRefOid>
# if that fails: git fetch origin pull/<number>/head
```

The fetch makes `<headRefOid>` available locally as a plain object without
creating or checking out a branch — safe to do from whatever branch the user
currently has checked out. Use this SHA for every "what does the code
actually look like" lookup in the steps below (`git show <sha>:<path>`,
`git grep -n ... <sha> -- <pathspec>`).
If fetching by SHA fails (e.g. a PR from a fork), `git fetch origin
pull/<number>/head` gets the same commit through the ref GitHub keeps for
every PR — confirm `git rev-parse FETCH_HEAD` equals `<headRefOid>` before
using it.

**Review discussion.** Also pull everything reviewers already said on this
PR — Copilot, other bots, people:

```bash
gh pr view <number> --json comments,reviews
gh api --method GET --paginate "repos/{owner}/{repo}/pulls/<number>/comments" \
  --jq '.[] | {id, in_reply_to_id, user: .user.login, path, line, original_line, commit_id, body}'
```

The first gives top-level comments and review summaries, the second the
inline threads (a reply points to its parent via `in_reply_to_id`). `line` is
null when the comment sits on code the PR later changed — then
`original_line` at `commit_id` is where it pointed. Hand this to Step 5.

**CI status.**

```bash
gh pr checks <number>
```

A non-zero exit is not an error here: `gh` exits 1 when a check failed
and 8 when checks are still pending — read the output either way. Note
which jobs failed or are pending on `<headRefOid>`. If CI is failing, say so briefly
in "What was done" — and point it out if the PR description claims the
opposite ("all tests pass").

### 3. Gather the review standards

Two files define what this project's code is held to. Note where they are
now; read them when Step 4 or 5 needs to check a specific claim — no need to
load everything up front.

- **`.github/copilot-instructions.md`** — the guidelines GitHub Copilot
  reviews PRs against: a "What NOT to Review" scope, a quick-reject
  checklist, Part A (architecture & code quality) and Part B (UI patterns &
  component standards). It is tracked and still gets revised, so read the
  version the PR was written against:
  `git show <headRefOid>:.github/copilot-instructions.md`.
- **Root `CLAUDE.md`** — git-ignored (`CLAUDE*` in `.gitignore`), so it
  exists only in the working tree and never at `<headRefOid>`: read it from
  disk, not via `git show`. It describes today's code and may be newer than
  the PR, so treat a mismatch between it and the PR as context, not as a
  violation. (The repo has no nested `CLAUDE.md` files today; if one appears
  under a changed directory, treat it the same way.)

### 4. Descriptive analysis — what, how, and what it touches

Group the changed files by what they are (server routers, client
routes/components, shared packages, config/CI, docs) and write the "what and
how" narrative per group, not file-by-file — a PR that adds one tRPC
procedure and wires it into two components reads better as one story than
three disconnected file summaries.

For each meaningful piece of the change, pull a short verbatim excerpt
(3-15 lines, fenced code block) from the actual file at `<headRefOid>` with
its real `file:line` citation, and explain what it does in context — not
just "this function was added" but why it matters (e.g. "this closes a race
where two components could refresh the same session token — see the
`sessionRescopes` cache added at `context.ts:280`").

**Impact / blast radius** — this is the part a plain diff can't tell you.
For every changed export, tRPC procedure key, exported React
component/hook, or public type in the diff, search for consumers *outside*
the PR's own changed files, across the whole monorepo at `<headRefOid>`:

```bash
git grep -n '<symbolName>' <headRefOid> -- . \
  ':!pnpm-lock.yaml' ':!**/CHANGELOG.md' ':!**/locales/**'
```

Search the whole tree, not just `*.ts`/`*.tsx`: `packages/aurora/README.md`
is the consumer-facing contract for public exports and `AuroraApp` props,
and the policy files (`apps/dashboard/src/policies/*.json`) hold the
permission keys. Report code consumers and documentation that describes
the changed surface separately.

Report what you find: which other packages/apps/routes depend on the
changed surface, whether the PR updated all of them consistently or left a
caller stale (that's worth flagging even outside the formal review pass —
it's exactly the kind of thing a descriptive walkthrough should catch), and
whether the change is internal-only (no outside consumers found) versus a
contract change that ripples outward (e.g. changes to `AuroraRouter`,
anything under `packages/aurora/src/server/*/routers/`, or exported client
hooks/components other apps import).

### 5. Review pass

Reuse the review methodology from the `code-review` plugin (`/code-review`)
(`gh`-based PR review), adapted to feed a report instead of a PR comment —
don't redo the eligibility/"already reviewed" gating from that command
(irrelevant here: the report documents the PR rather than gating its
merge), and don't post anything to GitHub.

1. Launch the review agents below in parallel, on Sonnet, against the diff
   + the review standards from Step 3 (give them the diff directly, they
   don't need to re-fetch it):
   a. **Conventions compliance** — audit against the review standards from
      Step 3. `copilot-instructions.md` is an explicit review checklist, and
      its "What NOT to Review" scope applies here too; `CLAUDE.md` is
      guidance for writing code, so not every line of it applies to review.
   b. **Bug scan** — shallow scan of the diff itself for obvious bugs. Don't
      wander into unrelated context; focus on large bugs, skip nitpicks.
   c. **Historical context** — `git log`/`git blame` on the modified files
      to catch bugs that only make sense in light of history.
   d. **Review discussion** — go through the comments collected in Step 2.
      For each, check at `<headRefOid>` whether it was addressed, still
      applies, or was wrong in the first place. One that still applies
      becomes a candidate issue like any other — a bot comment is a lead to
      verify, not evidence. Best-effort, also check earlier PRs touching the
      same files (`gh pr list --search`, `git log`) for review comments that
      still apply; don't spend long if nothing turns up quickly.
   e. **Comment compliance** — read code comments in the modified files,
      check the change complies with any guidance those comments state.
   f. **External API contract** — only when the PR changes anything (other
      than `*.test.ts`) under `packages/aurora/src/server/` or
      `packages/signal-openstack/`; skip it otherwise. Check every changed
      call to OpenStack (`service("<name>")…`) or to Ceph RGW through the S3
      client (`Storage/clients`, `Storage/routers/ceph`), and every changed
      Zod schema describing an API response, against the service's official
      API reference: method and path, required parameters, pagination
      (`limit`/`marker`, `next` links), microversion headers, response
      fields, status codes and error shapes. Also compare it with how
      existing code already calls the same endpoint. References:
      `https://docs.openstack.org/api-ref/<compute|image|identity|network|object-store|dns>/`;
      for Ceph, `https://docs.ceph.com/en/latest/radosgw/s3/` plus the AWS S3
      API reference for the semantics RGW inherits. Every finding must quote
      the doc passage with its URL — that quote is what lets the scorer
      verify it instead of guessing.
   g. **Security** — launch the project's `security-reviewer` agent
      (`.claude/agents/security-reviewer.md`, subagent type
      `security-reviewer`) on the diff. It already knows this stack's auth
      model and its known-intentional patterns. Tell it the code under
      review is at `<headRefOid>`, not in the working tree — read files with
      `git show <headRefOid>:<path>`, never from disk. Run it on every PR:
      client-only changes still carry the rules it checks (permissions
      enforced server-side, fail-closed UI, no raw HTML injection). Its
      findings go through the same scoring and ≥75 bar as the others.
      If no `security-reviewer` agent is available (another machine, a
      fresh checkout), run a general Sonnet agent with the same brief —
      procedure builders and scoping, server-side `canUser` checks, Zod
      input validation and IDs interpolated into OpenStack URLs, tokens and
      secrets in logs or responses, raw HTML injection — and note in the
      report that the dedicated reviewer was missing.
   Each agent returns a list of issues with the reason each was flagged.
2. Collect the issues from all agents and merge duplicates (one problem
   found by several agents is one issue — keep each agent's reasoning).
   Hand the list to a Sonnet scoring agent — one per up to ~12 issues — together
   with the PR, the review standards from Step 3 and `<headRefOid>`. The scorer
   didn't find these issues and must not take the finders' word for them:
   for each one it opens the cited code with
   `git show <headRefOid>:<path>` and checks the claim before scoring.
   Score 0-100 using this rubric (give it verbatim):
   - **0**: not confident at all — false positive or pre-existing issue.
   - **25**: might be real, might not; the scorer checked the code and
     still can't tell. If stylistic, not explicitly called out in the
     review standards.
   - **50**: verified real, but a nitpick or rare in practice; not very
     important relative to the rest of the PR.
   - **75**: highly confident — verified in the code, will likely be hit
     in practice, existing approach is insufficient, or a verified
     violation of a rule quoted from the review standards.
   - **100**: absolutely certain, confirmed by direct evidence, will happen
     frequently.
   Evidence rule: when an issue quotes an official API reference or the
   review standards, and the code at `<headRefOid>` does what the quote
   says it must not, the issue is verified — score it on its impact (50,
   75 or 100). "Can't run it" or "can't reach the docs" is never a reason
   for 25 when the quote and the code are in front of the scorer.
   For each issue the scorer returns the score and a one- or two-sentence
   reason naming what it checked and what it found (file:line, quote,
   behaviour) — the report shows this reason next to the score.
3. Report every scored issue — nothing that was scored is dropped silently.
   Issues at ≥75 are findings and each gets its own write-up. Everything
   below 75, down to 0, goes into the "Below the bar" table with its score
   and the scorer's reason, so a reader sees what was checked and why it
   was dismissed — false positives and wrong bot comments included. If
   nothing reaches 75, say so plainly; don't inflate a score or manufacture
   nitpicks to fill the findings section.
   If a finding was already raised in the review discussion, say so: who
   raised it, where, and what happened to it (fixed, no reply, dismissed).

Usual false positives — the scorer gives these 0–25, and they still
appear in "Below the bar" (adapted from the list `code-review` uses):
pre-existing issues; things that look like bugs but aren't; pedantic
nitpicks a senior engineer wouldn't raise; anything a linter, typechecker
or CI would catch; general code-quality opinions (test coverage, docs,
generic security hardening such as "add rate limiting" with no concrete
exploit path in this PR) unless the review standards explicitly require
them; issues explicitly silenced in code (lint-ignore comments);
intentional changes that are clearly part of the broader PR; real issues
on lines the PR didn't touch.

Don't run builds yourself. If CI is failing or hasn't run on
`<headRefOid>`, that goes in the report's CI line (Step 2), not into
findings re-derived from the build errors.

### 6. Write the report

File name: `<number>-<kebab-slug-of-title>.md`, e.g.
`1079-slot-support-login.md`, in `<DOCS>/aurora-dashboard-kb/prs/`. Write
the full draft straight into that file, using the template below.

**Proposed follow-ups.** Don't file anything in `DOCS/FOLLOW-UPS.md` —
only propose it in the report; the user decides whether a finding gets
fixed in this PR before merge or filed in the registry later. For each
finding that scored ≥75, add one line to "Proposed follow-ups": the
finding's title, its `file:line` at `<headRefOid>`, and a pointer back to
the finding. Don't restate the problem or the fix — both live in the
finding. On an Update (Step 1), these lines go into the Update's own list.

**Fact-check before finishing.** Nothing else re-reads the walkthrough —
the review agents look at the code, not at what you wrote about it. Hand
the draft to one Sonnet fact-check agent together with the diff and
`<headRefOid>`. It checks the descriptive sections ("What was done", "How
it is implemented", "What it affects" — or "What changed" in an Update),
not the Review:

- every code excerpt is verbatim at `<headRefOid>`, and its `file:line`
  points at the excerpt's first line;
- every claim about behaviour ("X now calls Y", "the cache is keyed by …")
  matches the code;
- every consumer claim ("no consumers outside the PR", "all callers were
  updated") holds on its own `git grep` at `<headRefOid>`;
- every place the report contrasts the PR description with the code is
  right.

It returns only the claims that are wrong, each with its evidence. Fix
those in the file. The fact-check itself doesn't go into the report.

Template:

```markdown
---
type: pr-report
date: <today, YYYY-MM-DD>
status: <merged | open | closed>
pr: [<number>]
author: <author>
branch: <headRefName>
---
# PR #<number>: <title>

**Author:** <author> · **Status:** <open | draft | merged YYYY-MM-DD | closed YYYY-MM-DD> · **Created:** <YYYY-MM-DD>
**Branches:** `<headRefName>` → `<baseRefName>` (base `<baseRefOid short sha>`) · **Files:** <changedFiles> (+<additions>/-<deletions>)
**Link:** <url>
**CI:** <all green | failing: <job>, … | pending: <job>, … | no checks> (at `<headRefOid short sha>`)

> If `baseRefName` ≠ `main`, call that out explicitly here.

## What was done

<narrative — the story of the change, grouped by area, not a file list>

## How it is implemented

<walkthrough with verbatim excerpts and file:line citations, at <headRefOid>>

## What it affects

<impact/blast-radius findings from Step 4 — consumers found elsewhere in the
monorepo, contract changes, anything left inconsistent>

## Review

<if the `security-reviewer` agent was unavailable: "Security pass ran via the general-agent fallback.">

### Findings (confidence ≥75)

#### 1. <short title> — confidence <score>

<what is wrong, where (file:line), and what it leads to; excerpt if it helps>

**Suggested fix:** <one or two sentences>
**Why this score:** <the scorer's reason>
<if raised in the review discussion: who, where, what happened to it>

<or: "No issues with confidence ≥75 found.">

### Below the bar

| Score | Finding | Why this score |
| --- | --- | --- |
| <score> | <one-line description, file:line> | <the scorer's reason> |

<every other scored issue, highest score first, down to 0; "None" if
nothing else was scored>

## Proposed follow-ups

- [ ] **<finding title>** — `<file:line>` → Review, finding <n>

<or: "None — no findings ≥75.">

---
Analyzed: <today's date, YYYY-MM-DD> · commit `<headRefOid short sha>`
```

### 7. Update the index

Maintain `<DOCS>/aurora-dashboard-kb/prs/README.md` as a lookup table:

```markdown
---
type: index
---
# PR reports

| PR | Date | Title | Affected | File |
| --- | --- | --- | --- | --- |
| [#1270](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1270) | 2026-09-03 → merged 2026-09-04 | fix(aurora): time doesn't match current timezone (#1236) | `formatSwiftDate` helper; Swift tables, sort comparators, `EditObjectMetadataModal`. Review: 1 finding (100) | [1270-time-doesnt-match-current-timezone.md](./1270-time-doesnt-match-current-timezone.md) |
```

If the file doesn't exist yet, create it with this header and one row.
Keep the full history — never trim old rows.

- **Date** — exactly one of: `<created> → merged <date>`,
  `<created> → closed <date>`, `<created> (open)`, `<created> (draft)`.
  Report updates go in the report's footer, not here.
- **Affected** — the touched surface only (procedures, routes, components,
  public exports), at most ~40 words, then `Review: <n> finding(s)
  (<scores>)` or `Review: clean`. Details live in the report.
- **Order** — newest PR on top by creation date (ties: higher number on
  top). Insert the row where it belongs, not always at the top: analyses
  don't happen in PR order.
- Escape any `|` inside a cell (code spans included) as `\|` —
  `DOCS/CLAUDE.md` rule 4.
- When a report's status changes (Step 1, "Existing report?"), update
  this row's Date cell too.

Then run `python3 <DOCS>/tools/update-related.py` to refresh the vault's
"Related" links (skip it if the script is missing, and say so when you
report back).

### 8. Report back

Tell the user, briefly: what PR was analyzed, the file path you wrote,
one line on what the review pass found (or that nothing cleared the
confidence bar), and how many follow-ups were proposed.
