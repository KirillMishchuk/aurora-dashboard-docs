---
name: review-and-comment-pr
description: >-
  Review an open aurora-dashboard PR (number, URL, or current branch) and
  post a merge verdict with required changes and improvements as a PR
  comment, after the user confirms. Use when asked to review, give a
  verdict on, or comment on a PR. For a report without a verdict or
  posting, use `document-pr`.
---

# Review and comment on a pull request

Produce one markdown report per PR that a future reader — a teammate or
Claude in a later session — can open instead of re-reading the PR on GitHub.
It leads with a **merge verdict** (recommendation + confidence) and the two
finding tables behind it — **Required Changes** (blockers + process to-dos)
and **Improvements** (non-blocking) — each with a per-finding "Explanation &
Fix". Below that, collapsible reference: a **Solution Overview** (what
changed, how, what it touches) and a **QA Test Plan**. The report shows only
what to act on: a check that passed gets no line, scores stay internal, and
findings are verified so it doesn't read like lint noise.

## Requirements

- **`gh`, signed in to GitHub.** Everything about the PR comes through it.
  If `gh pr view` in Step 1 fails with an auth error, stop and tell the
  user to run `gh auth login`.
- **The `DOCS` folder next to the repo** — Step 1 finds it and stops if
  it's missing.
- **The `security-reviewer` agent** (`.claude/agents/security-reviewer.md`)
  — optional; Step 5 has a fallback.

## Hard rules

- **Never check out the PR branch or touch the user's working tree/HEAD.**
  Everything here is read-only: `gh pr view`/`gh pr diff` for metadata and
  diff, `git fetch origin <sha>` + `git show <sha>:<path>` / `git grep -n
<pattern> <sha> -- <pathspec>` for reading the repo at the PR's head commit
  without checking it out. If the user is mid-work on another branch, this
  skill must not disturb that. Never create refs either: no
  `git fetch … <src>:<dst>`, no `git update-ref`, no branches — fetch by
  SHA (or into `FETCH_HEAD`) and address commits by SHA. Anything left in
  `refs/` outlives the run.
- **Verify against real code, not the PR description or commit message.**
  Descriptions oversell or drift; the diff and the files at the head commit
  are ground truth.
- **Code excerpts must be verbatim**, pulled from `git show <sha>:<path>` (or
  the diff itself), with accurate `file:line` citations — don't hand-compute
  line numbers from diff hunk headers, they lie once you're looking at
  the whole file. Get real line numbers from `git grep -n` against the head
  commit — `git grep -n '' <sha> -- <path>` prints a whole file numbered.
- **Findings need a verification pass before they're reported as issues**
  (see Step 5). An unfiltered "here's everything that looks off" list is not
  a review, it's noise.
- Report body is English, whatever language the
  user asks in. Code, identifiers and file paths stay as-is.
- **Don't commit or push, and don't touch git state.** The only external
  write the skill makes is posting its report as a comment on the PR it
  analysed (Step 8), and only after the user confirms. It never commits or
  pushes `DOCS` or the repo — that stays the user's call.
- **Write commands the allowlist can match.** Put SHAs and paths literally
  into each command — no `VAR=…;` prefixes, no `cd … &&` chains (run from
  the repo root). Shell variables don't survive between commands anyway.
  Repeat this rule and the first one (read-only, no checkout, no refs) in
  the brief of every agent you launch (review agents, scorer,
  fact-checker): they start in the repo root already and must not `cd`
  there.

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

**Release PRs.** If the PR author is `cobaltcore-bot` or the body says it
was opened by `changesets/action`, it only bumps versions and changelogs.
Do Steps 2–3 as usual, then replace Steps 4–5 with a light review:

- skip the linked-issue check (no Process item) and the review agents;
- check yourself: each bump matches the consumed changesets, the changelog
  entries render correctly, the new version isn't on npm yet
  (`npm view <package> version`), and whether pending changesets in other
  open PRs would change the bump type;
- a changelog problem is fixed in the `.changeset/*.md` on `main`, not on
  this branch — the bot regenerates it.

In the report keep Verdict, Required Changes and Improvements; under
Solution Overview only "What was done"; under QA Test Plan only Edge Cases.

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
ls <DOCS>/aurora-dashboard-kb/prs
```

No wildcard: zsh treats a pattern with no match as an error. If `ls`
fails, stop — there is nowhere to write the report (see Requirements).
Otherwise look in its output for a file named `<number>-*.md`; if there is
none, do the full run below. If a
report exists, read its frontmatter `status`, its `**Status:**` line (the
only place that says "draft") and its old head: the SHA after the last
`updated for` in the `Analyzed` footer, otherwise the SHA after `commit`
in the footer
— ignore SHAs marked "not analyzed" or "previous versions". Compare them
with what `gh pr view` just returned and take the matching path:

- **Same head, same status** — the report is current. Tell the user and
  ask whether to stop or re-run from scratch; a re-run overwrites the
  report, so only on an explicit yes. A re-run is a fresh analysis: don't
  read the old report's body — Steps 4–6 start from the code as if no
  report existed. Reading it anchors the new analysis on the old one and
  carries its mistakes and gaps forward; the frontmatter, `**Status:**`
  line and footer you already read are all this path needs.
- **Same head, only draft ↔ ready changed** — update the `**Status:**`
  line (and frontmatter `status`) and the index row's Date cell (Step 7);
  nothing else; don't post. Then report back (Step 9).
- **Now merged or closed** — a status update only: set `status` in the
  frontmatter, the `**Status:**` line
  (e.g. `merged 2026-10-14`) and the index row's Date cell (Step 7), and
  append ` · status updated <today>: <merged | closed>` to the footer. If
  the head moved after the last analysis, add
  ` · last head <short sha> not analyzed`. Nothing else in the body
  changes, and no other step runs — report back (Step 9) and stop.
- **Different head** (new commits since the report) — don't rewrite the
  existing text (reports are historical records). Fetch the new
  head (Step 2) and analyze only `git diff <old head>..<new head>`: Steps
  4–5 on that delta, the Step 6 fact-check on the new section. Append it
  before the footer in this shape:

  ```markdown
  ## Update — <today>, head `<short sha>`

  ### What changed

  <what the new commits do and how, with excerpts — same rules as Step 4>

  ### Fixed since last analysis

  <earlier findings the new commits fixed, by CR/I number; or "None">

  ### 🔧 Required Changes / 💡 Improvements

  <the delta's findings, same tables and severity markers as the main Review>
  ```

  For "Fixed since last analysis", read only the old report's Required
  Changes / Improvements, not its descriptive sections: the Update
  describes the new commits from the code.

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

**Changeset.** Check whether the PR adds a Changeset:

```bash
git ls-tree --name-only <headRefOid> .changeset/
```

Ignore `README.md` and `config.json`. If the PR adds a `.changeset/<name>.md`,
read it (`git show <headRefOid>:.changeset/<name>.md`) and note the bump type
(`major`/`minor`/`patch`). A changeset that is present and correct is **not**
reported (clean checks don't get a line). A **missing** changeset on a PR that
changes published package code (anything under `packages/*/src`) becomes a
Process item in Step 5.

**Linked issue / acceptance criteria.** Read the PR body (from Step 1) for an
issue link: `Closes #N`, `Fixes #N`, `Resolves #N`, `Part of #N`, or a bare
`#N` that is **not** a template placeholder (`#<epic-number>`,
`#<bff-issue-number>`, etc. are placeholders, not links).

- **A real link is found** — `gh issue view <N> --json title,body,state` and
  pull its acceptance criteria; Step 4 grades the PR against them.
- **No link** — the PR links no issue. Prompt the user **once**: "This PR
  links no issue. Give an issue/epic number to grade acceptance criteria
  against, or say none." If the user gives one, fetch and grade it **and**
  still record a Process item that the PR body itself links nothing (supplying
  it here ≠ linking it in the PR). If the user says none — or the skill runs
  unattended with no way to ask — record the Process item and set acceptance
  to "not verified: no issue to grade against", naming any related-but-not-
  direct epics the user mentioned (they are context, not the AC source).

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
component/hook, or public type in the diff, search for consumers _outside_
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

**QA test plan.** From the code you read, derive a manual test plan a
reviewer can run — things unit tests can't easily cover (real OpenStack
data, URL state, cross-view consistency, fallback rendering). Produce two
lists for the report's "QA Test Plan" section:

- **Core Path** — a numbered happy-path walkthrough, end to end, through
  the feature's main screens/actions.
- **Edge Cases** — a bulleted list of states the code reveals: empty or
  missing fields, fallbacks, error routes, and the exact scenario behind
  every Bug finding. Cite `file:line` where a case comes from a specific
  branch in the code.

**Acceptance criteria.** If Step 2 found a real linked issue (or the user
supplied one), grade the PR against that issue's acceptance criteria: note
each unmet criterion as a finding — a Required Change if a required
capability is missing, an Improvement if it's a shippable gap. If no issue
is linked, acceptance is "not verified" (a `P*` Process item from Step 2),
never a pass.

### 5. Review pass

Reuse the review methodology from the `code-review` plugin (`/code-review`)
(`gh`-based PR review), adapted to feed this report — don't redo the
eligibility/"already reviewed" gating from that command, and don't post
from here: the only GitHub write is Step 8, after the user confirms.

1. Launch the review agents below in parallel, on Sonnet. Give each the
   two SHAs, the changed-file list, the review standards from Step 3 and
   its own brief — not the diff: it reads
   `git diff <baseRefOid>...<headRefOid> -- <path>` for the files its check
   needs. One agent per letter — a through g, f only when its condition
   holds — and never two letters in one agent: each brief is narrow on
   purpose, and a merged agent does one of its checks shallowly.
   Finders report, they don't judge: a violation stays a violation when
   sibling code does the same or a maintainer accepted it on another PR —
   report it as a candidate and add the precedent as context. Dropping or
   downgrading candidates is the scorer's job (Step 5.2).
   a. **Conventions compliance** — audit against the review standards from
   Step 3. `copilot-instructions.md` is an explicit review checklist, and
   its "What NOT to Review" scope applies here too; `CLAUDE.md` is
   guidance for writing code, so not every line of it applies to review.
   Start with its "Quick Reject Checklist", then every "**Reject**" line
   in Part B — most B sections end with one, and several name rules the
   checklist doesn't (a 401/403 handled inline in B.6, a dismissible
   `Message` without `onDismiss`, a form without validation). Take the
   items one by one, check each against every changed file — UI strings
   included (casing, punctuation, wording) — and return one line per
   item, either a violation with `file:line` and the item quoted, or
   "not violated". A Reject clause that repeats a checklist item can
   point to it ("see checklist item n"). A general read of the standards
   misses items; the per-item pass doesn't.
   b. **Bug scan** — shallow scan of the diff itself for obvious bugs. Don't
   wander into unrelated context; focus on large bugs, skip nitpicks.
   c. **Historical context** — `git log`/`git blame` on the modified files
   to catch bugs that only make sense in light of history. Also check
   the PR against other open PRs: list those that touch the same files
   (`gh pr list --state open --json number,title,headRefOid,files`); when the
   description claims the PR is compatible with another one ("doesn't
   conflict", "same commit as on branch X"), test it —
   `git fetch origin <their headRefOid>` (or `git fetch origin
pull/<n>/head`, without a `:<ref>` part), then
   `git merge-tree --write-tree --name-only <headRefOid> <their headRefOid>`
   — always by SHA, never by a ref name you created.
   A conflict the description denies is a candidate issue.
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
   with the PR, the review standards from Step 3 and `<headRefOid>`. Pass
   each issue as the finder reported it: the claim, its `file:line`, and its
   evidence as-is — commands with their output, doc quotes with URLs. Don't
   soften the evidence ("reportedly") and don't add your own view of how
   much the issue matters; that is the scorer's call. Give the scorer every
   rule in this step verbatim — the rubric, the Severity scale, the Evidence
   rule, External-API
   claims, the Quick Reject and Precedent rules and the "Usual false
   positives" list — not a summary. The scorer didn't find these issues
   and must not take the finders' word for them: for each one it opens the
   cited code with `git show <headRefOid>:<path>`, re-runs any command the
   evidence rests on, and checks the claim before scoring.
   Score each issue using this rubric (give it verbatim, including this
   paragraph). Use exactly one of 0, 25, 50, 75 or 100 — no values in
   between. When an issue sits between two levels, pick one and say in the
   reason what kept it from the other.
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
     External-API claims: when an issue rests on how OpenStack, Ceph or S3
     behave, the scorer uses the doc quote agent f attached, or opens the
     reference itself — never its memory. "From memory" is no basis for 25
     or for a lower impact. A feature that silently leaves out data users
     expect to see counts as "will likely be hit in practice".
     Quick Reject rule: `copilot-instructions.md` has a "Quick Reject
     Checklist" — violations the project says should stop a PR in review.
     The scorer checks every issue against it, and a verified violation of
     a checklist item scores at least 75, even when the same pattern already
     exists elsewhere in the code: the project has ruled it out for new
     code. Quote the checklist item in the reason. Its "What NOT to Review"
     scope still wins (e.g. hardcoded strings in `packages/aurora` are
     lint-enforced, not a finding).
     Precedent rule: a maintainer declining the same change on another PR,
     or the same pattern already existing elsewhere in the code, never
     lowers the score of a verified issue — this PR adds new code, and the
     standards apply to it. Put the precedent in the reason instead, so the
     reader knows to expect pushback. (Lines this PR didn't touch are still
     "pre-existing" and score low — see "Usual false positives".)
     Severity — for every issue scored 50 or more, the scorer also rates how
     bad it is if left in, independently of the score, on a five-level scale
     with its marker (give this verbatim too):
   - 🔴 **Critical**: breaks a core flow for all users, opens a security
     hole, or loses/corrupts data.
   - 🟠 **Major**: breaks a feature or hides data users expect, with no
     easy workaround.
   - 🟡 **Moderate**: noticeable but bounded — degraded UX, an
     accessibility gap, duplicate requests, a merge conflict with another
     open PR, a broken project rule with a visible effect.
   - 🟢 **Low**: cosmetic, wording, a rule violation users rarely notice.
   - ⚪ **Trivial**: a nit with no user-facing effect (import order, a
     contradicted JSDoc on a rarely-hit path).
     Score and severity answer different questions: a Quick Reject
     violation scores at least 75 but can be 🟢 Low. Issues scored 0 or 25
     get no severity.
     Category — the scorer also tags each issue scored ≥50 with exactly one
     kind: `Bug`, `Security`, `Accessibility`, `UI/UX`, `Code Quality`,
     `Performance`, `Docs`, or `Test coverage`. (Process items — draft,
     description-vs-code mismatch, missing changeset, unlinked issue — are
     tagged `Process`; they come from Steps 1–2, not the scorer.)
     For each issue the scorer returns the score, the severity (score ≥50),
     the category, and a one- or two-sentence reason naming what it checked
     and what it found (file:line, quote, behaviour) and why that severity —
     the report shows this reason in the finding's "Explanation & Fix".
3. Turn the scored issues into the report's two finding tables. The 0-100
   score stays internal — it is the gate, and it does **not** appear in the
   report. Each table row shows `#`, severity (with marker), category, a
   one-line issue, and `file:line`.
   - **Drop anything scored below 50.** False positives, pre-existing
     issues and unconfirmable nitpicks do not appear in the report at all.
     (This is a deliberate change from a "below the bar" list: the report
     shows only what to act on. The dropped set still exists in the
     scorer's output if the user asks.)
   - **Required Changes** (`### 🔧 Required Changes`) — issues scored ≥50
     whose severity is 🟡 Moderate or worse (Moderate / Major / Critical),
     numbered `CR1`, `CR2`, … plus every **Process** item from Steps 1–2
     (still a draft; description claims a change not in the diff; missing
     changeset where published code changed; no linked issue / acceptance
     not verifiable), numbered `P1`, `P2`, …. Process rows have no severity
     marker (`—`).
   - **Improvements** (`### 💡 Improvements`) — issues scored ≥50 with
     severity 🟢 Low or ⚪ Trivial, numbered `I1`, `I2`, …
   - A missing test is **not** its own finding when it is a test for a bug
     already listed — fold "no test covers this" into that finding's
     Explanation. A pure coverage gap on otherwise-correct code is its own
     Improvement (category `Test coverage`).
   - If a finding was already raised in the review discussion, say so in
     its Explanation: who raised it, where, and what happened (fixed, no
     reply, dismissed).
4. **Verdict.** Derive the recommendation from Required Changes:
   - any code `CR*` at 🟡 Moderate or worse → **Request Changes**;
   - no code `CR*`, only `P*` process items → **Approve — process to-dos
     first**;
   - nothing in Required Changes, only Improvements (or clean) →
     **Approve** (add "with nits" if there are Improvements).
     **Confidence to Merge** (High / Medium / Low) is how sure you are the PR
     is sound once the Required Changes are cleared — lower it for anything
     you could not verify (CI unreadable, acceptance not checkable, draft,
     security-reviewer fallback used).

Usual false positives — the scorer gives these 0–25, so they stay out of
the report (adapted from the list `code-review` uses):
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

The report is **input-driven**: every section is populated from the earlier
steps — Step 1 (metadata, status, linked issue), Step 2 (CI, changeset,
review discussion), Step 4 (What/How/Affects, QA plan, acceptance), Step 5
(scored findings → Verdict, Required Changes, Improvements). Don't
re-derive anything here; assemble it. If a value an earlier step was
supposed to produce is missing, go get it (don't leave a blank) — e.g. the
changeset check (Step 2) or the QA plan (Step 4).

The report shows **only what to act on and the context behind it**. There
is no score column, no "below the bar" list, and no row for a check that
passed — a clean CI / security / changeset / API-contract gate gets no
line at all (it only surfaces as a finding when it has a problem).

**Fact-check before finishing.** Nothing else re-reads the walkthrough —
the review agents look at the code, not at what you wrote about it. Hand
the draft to one Sonnet fact-check agent together with the diff and
`<headRefOid>`. It checks the descriptive sections (the three
"Solution Overview" folds and the "QA Test Plan" — or "What changed" in an
Update), not the Review:

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

**Structure and wording are fixed** — match the template exactly: the
section order, the headings and their emoji (`### ⚖️ Verdict`,
`### 🔧 Required Changes`, `### 💡 Improvements`), the `<details>` folds,
the Verdict line with Recommendation and Confidence together, then the
summary as plain text (no blockquote), the
per-table "Explanation & Fix" fold, and the five-level severity markers
(🔴 Critical · 🟠 Major · 🟡 Moderate · 🟢 Low · ⚪ Trivial). The only
emoji that carries meaning on the recommendation line is 🔴 for Request
Changes (🟢 for Approve). Severity markers in the tables are the only other
colour. Don't add gates strips, score columns, or decorative emoji on the
other headings.

Template:

```markdown
---
type: pr-report
date: <today, YYYY-MM-DD>
status: <merged | open | closed>
pr: [<number>]
issue: [<linked issue number(s), or empty>]
author: <author>
branch: <headRefName>
---

# PR #<number>: <title>

**Author:** <author> · **Status:** <draft | open | merged YYYY-MM-DD | closed YYYY-MM-DD> · **Base:** `<baseRefName>` ← `<headRefName>`
**Size:** <changedFiles> files, +<additions> / −<deletions> · **Created:** <YYYY-MM-DD> · [View on GitHub](url)

> If `baseRefName` ≠ `main`, call that out explicitly on its own line here.

---

## PR Review Report by [review-and-comment-pr](https://github.com/KirillMishchuk/aurora-dashboard-docs/blob/main/ToolDocs/claude-config/aurora-dashboard-config/.claude/skills/review-and-comment-pr/SKILL.md)

### ⚖️ &nbsp; Verdict

Recommendation: **<🔴 Request Changes | 🟢 Approve | Approve — process to-dos first>** &nbsp;&nbsp;&nbsp;&nbsp; Confidence to Merge: **<High | Medium | Low>**

<2–4 sentence summary: the overall shape, the one or two things that matter, what clears it. If CI/security fell back or acceptance couldn't be verified, that belongs in this summary.>

### 🔧 &nbsp; Required Changes

| #   | Severity      | Category   | Issue      | Location              |
| --- | ------------- | ---------- | ---------- | --------------------- |
| CR1 | <🟡 Moderate> | <Category> | <one line> | `<file:line>`         |
| P1  | —             | Process    | <one line> | <PR state \| PR body> |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**CR1 — <title>** · <Category> · `<file:line>`
<what's wrong, where, what it leads to; add precedent as context if sibling code does the same; if raised in review discussion, say who/where/what happened>
_Fix:_ <one or two sentences; code block only when it clarifies>

**P2 — <title>** · Process · <where>
<why it matters>
_Fix:_ <one or two sentences>

</details>

<if the section is empty: write "None." and omit the fold>

### 💡 &nbsp; Improvements

| #   | Severity | Category   | Issue      | Location      |
| --- | -------- | ---------- | ---------- | ------------- |
| I1  | <🟢 Low> | <Category> | <one line> | `<file:line>` |

<details><summary><strong>Explanation &amp; Fix</strong></summary>

**I1 — <title>** · <Category> · `<file:line>`
<rule or reason; precedent as context>
_Fix:_ <one or two sentences>

</details>

<if the section is empty: write "None." and omit the fold>

---

## Solution Overview

<details>
<summary><strong>What was done</strong></summary>

<narrative — the story of the change, grouped by area, not a file list>

</details>

<details>
<summary><strong>How it is implemented</strong></summary>

<walkthrough with verbatim excerpts and file:line citations, at <headRefOid>>

</details>

<details>
<summary><strong>What it affects (blast radius)</strong></summary>

<impact/blast-radius findings from Step 4 — consumers found elsewhere in the
monorepo, contract changes, anything left inconsistent>

</details>

---

## QA Test Plan

<details>
<summary><strong>Core Path</strong></summary>

<numbered happy-path walkthrough from Step 4>

</details>

<details>
<summary><strong>Edge Cases</strong></summary>

<bulleted edge cases from Step 4, each with file:line where it comes from a specific branch>

</details>

---

_Analyzed <today, YYYY-MM-DD> · commit `<headRefOid short sha>` · <provenance: "read-only"; add any of "CI from PR API", "review threads not read", "security-reviewer fallback used" that applied> · skill: review-and-comment-pr_
```

On an **Update** (Step 1, different head), keep the existing report and
append the Update block described there, reusing these same Required
Changes / Improvements tables and severity markers for the delta's
findings.

### 7. Update the index

Maintain `<DOCS>/aurora-dashboard-kb/prs/README.md` as a lookup table:

```markdown
---
type: index
---

# PR reports

| PR                                                                    | Date                           | Title                                                    | Affected                                                                                                                                               | File                                                                                       |
| --------------------------------------------------------------------- | ------------------------------ | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------ |
| [#1270](https://github.com/cobaltcore-dev/aurora-dashboard/pull/1270) | 2026-09-03 → merged 2026-09-04 | fix(aurora): time doesn't match current timezone (#1236) | `formatSwiftDate` helper; Swift tables, sort comparators, `EditObjectMetadataModal`. Verdict: Request Changes — 1 Required Change (🟡), 2 Improvements | [1270-time-doesnt-match-current-timezone.md](./1270-time-doesnt-match-current-timezone.md) |
```

If the file doesn't exist yet, create it with this header and one row.
Keep the full history — never trim old rows.

- **Date** — exactly one of: `<created> → merged <date>`,
  `<created> → closed <date>`, `<created> (open)`, `<created> (draft)`.
  Report updates go in the report's footer, not here.
- **Affected** — the touched surface only (procedures, routes, components,
  public exports), at most ~40 words, then the verdict and finding counts:
  `Verdict: <Request Changes | Approve> — <n> Required Change(s) (<severity
markers>), <m> Improvement(s)`, or `Verdict: Approve — clean`. Rows
  written under the old scheme keep their wording. Details live in the
  report.
- **Order** — newest PR on top by creation date (ties: higher number on
  top). Insert the row where it belongs, not always at the top: analyses
  don't happen in PR order.
- Escape any `|` inside a cell (code spans included) as `\|`.
- When a report's status changes (Step 1, "Existing report?"), update
  this row's Date cell too.

Then run `python3 <DOCS>/tools/update-related.py` to refresh the vault's
"Related" links (skip it if the script is missing, and say so when you
report back). If it prints a duplicate pr-report warning, pass it on
when you report back — don't delete or merge reports yourself.

### 8. Post the report to the PR

Post the report back onto the PR it analysed, as a single PR comment.

**Scope — the review portion only.** Post from the `## PR Review Report`
heading down to the end of the "QA Test Plan" section — not the `---`
and `_Analyzed …_` footer after it (local provenance, not for the PR).
Leave out everything above the heading too: the YAML frontmatter, the
`# PR #<number>: <title>` title and the `**Author:** … **Size:** …` line
(that context is already on the PR page). The `<details>` folds and
tables render natively in GitHub comments.

**Safety scan before posting — strict; a hit blocks the post.** The PR is
a public forum. Read the exact text you are about to post — every line,
inside `<details>` folds and fenced code blocks included — and scan for
anything that must not go public. If you find **any** of the following, do
**not** post: warn the user, quote the offending text with where it sits
(section / finding / line), explain why it's sensitive, and let them decide
(redact it in the report file and re-run this step, or post manually).
Never silently strip-and-post — the user chooses.

- **Secrets / credentials** — tokens, API keys, passwords, bearer/`Authorization`
  headers, OpenStack application credentials, connection strings, anything
  matching `-----BEGIN … KEY-----`, or long high-entropy hex/base64 blobs.
  This holds even inside a verbatim code excerpt: if real secret material
  sits in the diff, that is itself a finding (category Security) — report
  it, but never paste the secret into the comment.
- **Local filesystem paths that identify a person or machine** —
  `/Users/<name>/…`, `/home/<name>/…`, `C:\Users\<name>\…`, temp paths with
  a username. The report must cite **repo-relative** paths only; an absolute
  path leaking the runner's home dir reveals their identity.
- **Internal-only hosts and URLs** — enterprise GitHub, internal Jira/Confluence/Grafana/wiki, VPN-only hostnames,
  `*.internal` / `*.corp`, private IPs (`10.`, `192.168.`, `172.16–31.`),
  and links to **private** repos — including the skill link in the
  `## PR Review Report by [review-and-comment-pr](…)` heading if that repo
  is private. Drop or genericise these.
- **Personal data beyond public GitHub handles** — real names, email
  addresses or usernames pulled from `git log` / `git blame` / commit
  authorship or review threads. Keep people as their public `@handle`;
  strip emails and real names.
- **Environment-specific real data** — tenant/customer identifiers, real
  project IDs, account IDs, or sample tokens from test fixtures that happen
  to be real.
- **Anything from an ignored or secret file** — contents of `.env`,
  `*.pem`, credentials files, or any path the repo's `.gitignore` covers.

When nothing is found, say so in one line (so the user knows the scan ran)
and continue.

**Human oversight is mandatory — always.** Publishing to the PR is never
automatic and has **no bypass**: there is no "post without asking" setting
that applies here, and a standing instruction to act autonomously does not
cover this step. Do everything else first — write the report (Step 6),
update the index (Step 7), run the safety scan above — and only then stop
and hand the decision to the user. In that hand-off, state, in this order:

1. **Exactly what will be posted** — the full sliced text verbatim (or, if
   long, the Verdict block in full plus the headings and finding counts),
   so the user sees the real content, not a paraphrase.
2. **Where and as whom** — `<owner>/<repo>` PR #`<number>`, under the
   account from `gh api user --jq .login`.
3. **The safety-check result** — run the scan a **second time** on the
   exact bytes you are about to post (double-check), and report it: either
   "clean — scanned for secrets, local paths, internal hosts/URLs, personal
   data, env data; none found" or the blocking hits (in which case you do
   not offer to post at all until they're resolved).

Post **only** after the user explicitly says to, in response to that
hand-off. Silence, an unrelated reply, or a prior general "go ahead" is not
consent for this publish. If the safety scan found anything, posting is off
the table until the user redacts the report and you re-run this step clean.

**How.** Slice the review portion into a temp file **outside the repo and
outside `DOCS`** (e.g. `/tmp/pr-<number>-comment.md`) so no stray file
lands in a tracked tree, then:

```bash
gh pr comment <number> --repo <owner>/<repo> --body-file /tmp/pr-<number>-comment.md
```

Use `--body-file`, never `--body` with the text inline — the report has
backticks, code fences and `|` that a shell would mangle. On an **Update**
run (Step 1), post only the new `## Update — <today>, …` block, not the
whole report again.

**If it fails.** A `gh` auth error or `Resource not accessible by personal
access token` means the account lacks comment permission on the repo —
don't retry blindly. Tell the user the report was written to `DOCS` but not
posted, and why (so they can re-auth with `gh auth login` or post it
themselves). A failed post never fails the run — the report file is the
deliverable; the comment is a convenience.

### 9. Report back

Tell the user, briefly: what PR was analyzed, the file path you wrote, the
verdict (recommendation + confidence), the finding counts — how many
Required Changes (with severities) and Improvements, or that the review was
clean — and whether the report was posted to the PR (with the comment URL)
or not (and why). On a status-only update (Step 1), say what changed instead.
