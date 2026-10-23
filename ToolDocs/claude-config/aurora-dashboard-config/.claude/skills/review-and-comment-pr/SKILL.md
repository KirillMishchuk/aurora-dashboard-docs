---
name: review-and-comment-pr
description: >-
  Review an open aurora-dashboard PR (number, URL, or current branch) and
  post a merge verdict with required changes and improvements as a PR
  comment, after the user confirms. Use when asked to review, give a
  verdict on, or comment on a PR, or to document a PR in `DOCS` — answer
  no at the posting step and nothing reaches GitHub.
---

<!-- prettier-ignore-start -->

# Review and comment on a pull request

Review an open PR and produce one report a teammate or a later Claude
session can read instead of the PR itself: a merge verdict with the
findings behind it, then the context (what changed, how to test it).
Write it to `DOCS`, and post it to the PR only after the user confirms.

The run is a fixed pipeline. Scripts do everything that needs no
judgment — collecting the PR, writing the agents' briefs, checking and
saving their results, grouping and batching candidates, assembling and
rendering the report. You run the steps below in order, launch exactly
the agents the scripts list, judge where a step asks you to, and write
the report's wording. Every script prints what to do next. When
`save.py`, `assemble.py`, `render.py` or `quotes.py` exits 1, it lists
every problem by field: fix those and run it again. `collect.py`,
`briefs.py` and `prepare_comment.py` have their own exit-1 rules in their
steps — they mean stop or ask the user, not fix and retry.

Run every command from the repo root. The paths the scripts print are
absolute — `<run folder>` below is the one `collect.py` prints; write
them out literally in every later command.

## Requirements

- **`gh`, signed in to GitHub.** Everything about the PR comes through it.
  If `collect.py` in Step 1 reports an auth error, stop and tell the
  user to run `gh auth login`.
- **The `DOCS` folder next to the repo** — `collect.py` finds it and
  stops if it's missing.
- **This skill's own files** — `scripts/collect.py`, `briefs.py`,
  `save.py`, `assemble.py`, `quotes.py`, `render.py`,
  `prepare_comment.py`; `references/briefs/`, `scoring.md`,
  `findings-format.md`, `report-format.md` (reference only — render.py
  implements it).
  The scripts need `python3` 3.9+. If one is missing, stop and tell the
  user: the skill can't collect, score, write or post without it.
- **Agents** — `pr-reviewer`, `external-api-checker` and
  `security-reviewer` in `.claude/agents/`. Optional: each has a fallback
  (a general Sonnet agent with the same brief from `briefs.py`).
- **Network for the API references** — `curl` to
  `raw.githubusercontent.com` (OpenStack reference sources) and
  `docs.ceph.com` / AWS docs, for finder f and the scorers.
- **Optional:** the Markdown hook `.claude/hooks/check_report_md.py`
  (also used by render.py and prepare_comment.py) and the project
  settings that make the run cheaper (agents waited for in one turn,
  unused tools off). Without them the run still works, only slower and
  costlier.

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
- **Reading code at a commit.** Run every command from the repo root
  (agents start there — never `cd`), with SHAs and paths written out
  literally:
  - a whole file, numbered: `git grep -n '' <sha> -- <path>`;
  - a line range, numbered: `git blame -s -L <from>,<to> <sha> -- <path>`
    — each line comes as `<commit> <n>) <code>`; quote only the code;
  - a match with context: `git grep -n -A4 '<pattern>' <sha> -- <path>` —
    options go before the pattern and the SHA; after them git reads an
    option as a revision and fails;
  - `git show <sha>:<path>` takes a repo-root path — `./` and `../` are
    not resolved and fail.
  Agent types and briefs come from `briefs.py` (Step 4): it pastes these
  two rules into the `security-reviewer` brief, which doesn't carry them;
  `pr-reviewer` and `external-api-checker` do.
- **Verify against real code, not the PR description or commit message.**
  Descriptions oversell or drift; the diff and the files at the head commit
  are ground truth.
- **Code in the report comes from the repo, not from typing.** Agents
  read code with the commands above — never compute line numbers from
  diff hunk headers. In the report's text (the describer's result,
  `texts.json`), quote repo code only as `[[code:…]]` and cite lines as
  `[[at:…]]` or a full `path:line`: render.py inserts the code verbatim
  from `<headRefOid>` and checks every citation, and rejects a hand-typed
  block that isn't verbatim at head or base (`references/findings-format.md`).
- **Findings need a verification pass before they're reported as issues**
  (the scorers, Step 5). An unfiltered "here's everything that looks off"
  list is not a review, it's noise.
- **Don't do the scripts' or the agents' work yourself.** No `gh pr view`,
  `gh pr checks`, `git fetch` or listing of the reports folder (Step 1
  did it), and don't read the PR's code or the run folder's files
  (`context.json`, `pr-body.md`, `discussion.json`, `issue-*.md`,
  `candidates.json`, `out/*.json`) unless a step tells you to (a release
  PR, the fact-check result) — everything you load stays in
  your context and is re-read on every later turn.
- Report body is English, whatever language the user asks in. Code,
  identifiers and file paths stay as-is.
- **Don't commit or push, and don't touch git state.** The only external
  write the skill makes is posting its report as a comment on the PR it
  analysed (Step 8), and only after the user confirms. It never commits or
  pushes `DOCS` or the repo — that stays the user's call.

## Steps

### 1. Collect the PR context

From the repo root:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/collect.py <arg>
```

`<arg>` is whatever the user gave — a number, a URL, or nothing (the PR
for the current branch). It reads the PR, finds `DOCS` and any existing
report, picks the run mode, fetches the head commit by SHA, and saves the
diff, review discussion, CI, changeset, linked issue and review standards
into the run folder. Read its summary (not the
JSON).

- **exit 0** — act on `Mode:` (Step 2).
- **exit 3** — it needs an answer. Ask the user the printed question
  once, as printed, and re-run with the flag it names:
  - no linked issue → `--issue <N>` or `--no-issue`; unattended, with no
    way to ask, `--no-issue`;
  - the report is already current → `--rerun` only on an explicit yes
    (a re-run overwrites the report); anything else means stop — report
    back (Step 9).
- **exit 1** — it couldn't collect (`gh` not signed in, `DOCS` missing,
  fetch failed, several reports for one PR). Pass its message on and
  stop; on an auth error tell the user to run `gh auth login`.
- **exit 2** — wrong arguments; fix the call.

### 2. Act on the mode

- **`full`** — open PR, no report yet: Steps 4–9. The report goes to the
  `Report:` path from the summary.
- **`rerun`** — the user confirmed re-running a current report: as
  `full`, overwriting the file. Don't read the old report's body — it
  anchors the new analysis on the old one and carries its mistakes
  forward.
- **`status`** — draft ↔ ready changed, or the PR was merged or closed
  since the report. Run
  `python3 .claude/skills/review-and-comment-pr/scripts/render.py --run <run folder>`:
  it writes the new status into the report and its index row and
  refreshes the Related links. Don't post; report back (Step 9).
- **`update`** — new commits since the report. Don't rewrite the
  existing text (reports are historical records). Steps 4–6 run as for
  `full`, but the agents analyze only the delta (`delta.diff`;
  `Delta: whole-pr` means a force-push made the old head unreachable —
  tell the user). In `texts.json` write `fixed_since` — the earlier
  findings the new commits fixed, by CR/I number, or "None", from the
  "Earlier findings" list in `compose.md` — instead of `summary`,
  `confidence`, `index_affected` and `edge_cases`. render.py inserts an
  `## Update — <today>, head <sha>` block before the report's footer
  (What changed, Fixed since last analysis, the delta's findings numbered
  after the report's earlier ones; a re-render replaces it), and updates
  the footer, the status and the index row's Date cell.
- **`none`** — merged or closed without a report, or already up to
  date, or the user chose to stop: nothing to document. Say so and stop.

**Release PR** (`Release PR: yes`) — it only bumps versions and
changelogs, and the scripts launch no agents for it. Replace Steps 4–5
with a light review of your own:

- no linked-issue Process item and no review agents;
- check: each bump matches the consumed changesets, the changelog entries
  render correctly, the new version isn't on npm yet
  (`npm view <package> version`), and whether pending changesets in other
  open PRs would change the bump type;
- a changelog problem is fixed in the `.changeset/*.md` on `main`, not on
  this branch — the bot regenerates it.

Then write `<run folder>/findings.json` yourself — every required key
in the "findings.json" section of `references/findings-format.md`; of
the descriptive parts only `overview.what` and `qa.edge_cases` — and run
`python3 .claude/skills/review-and-comment-pr/scripts/render.py --run <run folder>`
alone (no texts.json, no assemble.py). The report keeps Verdict,
Required Changes, Improvements, "What was done" and Edge Cases. Its
errors, the fact-check's fixes (Step 6) and Markdown problems (Step 8)
are fixed in `findings.json`, then render.py runs again.

A base branch other than `main` is called out at the top of the report
by render.py; it is not a blocker.

### 3. What the run folder holds

The agents read it themselves: `context.json` (metadata, SHAs, changed
files, flags, CI, changeset, issues, Process items,
provenance), `pr.diff` (without generated files), `pr-body.md`,
`issue-<N>.md` (acceptance criteria), `discussion.json`,
`copilot-instructions.md` (the review standards at `<headRefOid>`; root
`CLAUDE.md` exists only on disk, may be newer than the PR, and a mismatch
with it is context, not a violation). Brief agents with the folder's
path only — the scripts do — never paste its content.

### 4. Launch the describer and the finders

```bash
python3 .claude/skills/review-and-comment-pr/scripts/briefs.py --run <run folder> find
```

It writes one brief per agent into `<run folder>/briefs/` — the describer
and finders a–g (f only when the PR changes server code; none on a
release PR) — and prints each agent with its subagent type. Launch
exactly those agents in **one** message, in the foreground
(`run_in_background: false`), each with the prompt
`Read your brief: <path>` and its subagent type. Their results then come
back in one turn; background agents wake you once per agent, and each of
those turns re-reads your whole context for nothing. Don't add to or
rewrite the briefs: they are the same on every run on purpose, and each
is narrow on purpose — never merge two into one agent.

Each agent checks and saves its result with `save.py` into
`<run folder>/out/<name>.json` and replies with one `saved …` line. If an
agent replies otherwise or its file is missing, re-launch that one agent
once with the same prompt; if it fails again, note it in the summary and
in `provenance_extra`. If the list marks an agent type as missing, use a
general Sonnet agent with the same brief and add the fallback to
`provenance_extra`.

### 5. Review pass

The methodology is the `code-review` plugin's (`/code-review`), adapted
to feed this report — no eligibility/"already reviewed" gating, and no
posting from here: the only GitHub write is Step 8.

1. **Score.**

   ```bash
   python3 .claude/skills/review-and-comment-pr/scripts/briefs.py --run <run folder> score
   ```

   It collects the candidates (finders a–g, plus the describer's unmet
   acceptance criteria and stale callers), groups those at the same
   place, packs them into batches and writes one scorer brief per batch,
   with the evidence exactly as the finders reported it. Launch the
   scorers it lists exactly as in Step 4. Each reads
   `references/scoring.md` itself, scores every candidate of its batch
   and decides with `same_as` whether candidates at one place are one
   problem; `save.py` refuses a result that skips either. If the script
   reports no candidates, go on with 2.
2. **Compose.**

   ```bash
   python3 .claude/skills/review-and-comment-pr/scripts/assemble.py --run <run folder>
   ```

   It keeps every candidate scored 50 or more that isn't a `same_as`
   duplicate (the duplicate's evidence goes along), sorts them, flags
   pairs that look like one problem, and writes `<run folder>/compose.md`.
   Read it with the Read tool (not `cat`: long output gets cut).
3. **Verdict** (not on an Update — its block has none). render.py derives the recommendation from Required
   Changes (any code finding at 🟡 Moderate or worse without a precedent
   tag → Request Changes; only tagged ones → Approve — team call first;
   only Process items → Approve — process to-dos first; otherwise Approve,
   "with nits" if there are Improvements) and lists them under it — Must
   fix before merge (with the describer's `scope`), Team call, Process.
   You choose only **Confidence to
   Merge** (High / Medium / Low): how sure you are the PR is sound once the
   Required Changes are cleared — lower it for anything you could not
   verify (CI unreadable, acceptance not checkable, draft,
   security-reviewer fallback used).

Don't run builds yourself. A failing or missing CI run on `<headRefOid>`
is reported as such, not as findings re-derived from the build errors.

### 6. Write texts.json and render the report

Read `.claude/skills/review-and-comment-pr/references/findings-format.md`
now. From `compose.md` write `<run folder>/texts.json` — the wording
only; scores, severity, category, location, the overview and the QA plan
come from the agents:

- `summary` — 2–4 sentences: the overall shape, the one or two things
  that matter, what clears it; the acceptance grading (with no issue to
  grade against: "not verified", never a pass); CI that couldn't be read,
  any agent fallback or check that couldn't run (failing CI is already in
  the describer's "What was done");
- `confidence`, `index_affected`;
- per finding `issue`, `title`, `explanation`, `fix`. In the
  explanation: what's wrong, where, what it leads to (the precedent tag
  is the scorer's, render.py shows it); if the review discussion raised it, who,
  where and what happened; a missing test for a listed bug goes here,
  not into its own finding;
- `edge_cases` — the scenario behind every Bug finding;
- `merge` — a look-alike pair from `compose.md` that is one problem;
- `process` — only a Process item you add yourself (the description
  claims a change that isn't in the diff); draft, unlinked issue and
  missing changeset come from `collect.py`.

The report shows only what to act on: a check that passed (CI, security,
changeset, API contract) gets no finding. Don't open the old report or
`report-format.md` — layout, header, footer and index are code. Then:

```bash
python3 .claude/skills/review-and-comment-pr/scripts/assemble.py --run <run folder> --texts && \
python3 .claude/skills/review-and-comment-pr/scripts/render.py --run <run folder>
```

Either one's exit 1 lists every problem by field — fix it in
`texts.json` (a finding's text directly; the describer's text or a
location with a `fixes` entry, as in `findings-format.md`) and run both
again; nothing reaches `DOCS` until they pass. On success
render.py writes the report to `DOCS`, adds or replaces the PR's index
row and refreshes the Related links.

**Fact-check.** Nothing else re-reads the walkthrough.

```bash
python3 .claude/skills/review-and-comment-pr/scripts/briefs.py --run <run folder> factcheck
```

Launch the agent it lists, in the foreground, with
`Read your brief: <path>` and the subagent type it shows. It checks the descriptive sections (Solution
Overview, QA Test Plan — on an Update, "What changed") against the code
and saves `out/factcheck.json`: each wrong claim with the field it comes
from, an exact `old` → `new` replacement and the evidence. Read that
file; for each entry you accept, copy `field`, `old`, `new` into
`fixes` in `texts.json` and run both scripts again (on a release PR,
apply it in `findings.json` and run render.py). The fact-check itself doesn't go into the report.

### 7. Index and related links

Done by render.py in Step 6. If its `Index:` line says the row was not
updated, or `Related:` shows a warning (e.g. a duplicate pr-report), pass
it on when you report back — don't edit the index by hand, and don't
delete or merge reports.

### 8. Post the report to the PR

Post the review portion of the report as one PR comment — only after the
user says so.

**Prepare.** From the repo root run
`python3 .claude/skills/review-and-comment-pr/scripts/prepare_comment.py <report path> <number>`
(add `--update` on an Update run: only the newest `## Update — …` block is
posted). It slices the comment — from `## PR Review Report` to the end of
the QA Test Plan, without frontmatter, title or the `_Analyzed` footer —
into `/tmp/pr-<number>-comment.md`, scans it for what must not go public
(secrets, local paths, internal hosts and private IPs, e-mail addresses,
env data), checks the Markdown, and prints the account, verdict, finding
counts, sections, links and every hit with its line. Patterns don't catch
everything: also skim for real names, customer or project identifiers,
and links to private repos.

**Any hit blocks the post.** Quote it to the user with where it sits and
let them decide — redact the report and re-run, or post manually. Never
strip-and-post silently. A Markdown problem: fix it where Step 6 says
(`texts.json`; on a release PR `findings.json`),
re-render, re-run.

**Hand-off — mandatory, no bypass.** No standing instruction to act
autonomously covers this step. Show the user the script's summary
(verdict, counts, sections, `<owner>/<repo>` PR #`<number>` and the
account) and ask. Post only on an explicit yes given in reply to this
hand-off:

    gh pr comment <number> --repo <owner>/<repo> --body-file /tmp/pr-<number>-comment.md

Always `--body-file`, never `--body`: the shell mangles backticks and `|`.

**If it fails** (auth error, "Resource not accessible…"): don't retry;
tell the user the report is in `DOCS` but not posted, and why. A failed
post never fails the run — the report file is the deliverable.

### 9. Report back

Tell the user, briefly: what PR was analyzed, the file path you wrote, the
verdict (recommendation + confidence), the finding counts — how many
Required Changes (with severities) and Improvements, or that the review was
clean — and whether the report was posted to the PR (with the comment URL)
or not (and why). On a status-only update (Step 2), say what changed
instead; on an Update, the new block's counts and what it lists as fixed. Pass on any agent that failed twice, any fallback used, and any
`Index:` / `Related:` warning from Step 6.

Then ask once whether any Required Change or Improvement should be filed
in `DOCS/FOLLOW-UPS.md` — name them by number and title. Never write to
that file unless the user says which ones; filing them is the user's call.

<!-- prettier-ignore-end -->
