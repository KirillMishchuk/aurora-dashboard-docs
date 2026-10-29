# review-and-comment-pr — Specification

The design contract of the Claude Code skill `review-and-comment-pr` for the
aurora-dashboard repo: what it guarantees, how it is built, and why. It
describes contracts and invariants, not code line by line — for a detailed
walkthrough of every script and file (in Russian) see `README.md` next to this
file. When this spec and the code disagree, the code is right and this file is
out of date.

Last updated: 2026-10-28 (evening).

## Contents

1. Purpose and scope
2. Design principles
3. Where the files live
4. Pipeline
5. Roles
6. Run folder and data contracts
7. Verdict
8. Invariants and where they are enforced
9. Publishing and safety
10. Testing
11. Decision log
12. Known limitations

---

## 1. Purpose and scope

Given an aurora-dashboard pull request (number, URL, or the current branch),
the skill produces **one report** that a teammate or a later Claude session can
read instead of the PR itself:

- a merge **verdict** (recommendation + confidence) with the findings behind it
  — Required Changes, Improvements, Process to-dos;
- the context: what changed, how it is implemented, what it affects, how to
  test it.

The report is written to the knowledge base (`DOCS/aurora-dashboard-kb/prs/`,
plus a row in the index `prs/README.md`). The review part is posted to the PR
as a comment **only after an explicit "yes" from the user**. On new commits the
skill appends an **Update block** to the existing report instead of rewriting it.

Out of scope: running builds or tests, fixing code, committing or pushing
anything, reviewing repositories other than aurora-dashboard.

## 2. Design principles

1. **Deterministic where possible.** Scripts do everything that needs no
   judgment: collecting the PR, choosing the mode, writing briefs, checking
   and saving agent results, grouping and batching candidates, numbering,
   the verdict, layout, rendering, the index, slicing the comment.
2. **The orchestrator only orchestrates and words.** Claude (Opus) runs the
   steps in `SKILL.md`, launches exactly the agents a script lists, and writes
   the report's wording (`texts.json`). It does not read code, re-score, or
   add checks of its own.
3. **One task — one narrow agent.** Every check is a separate Sonnet agent with
   a fixed brief. Adding a check to the orchestrator or to an agent that has
   another task proved unreliable (Oct 23–26) and is not done.
4. **Behaviour changes through briefs or code checks.** An agent's output is
   changed reliably only by (a) a narrow brief, or (b) a check in
   `save.py` / `assemble.py` / `render.py` that refuses the result and makes
   the agent or the orchestrator fix it.
5. **Verify before reporting.** Finders propose candidates; independent
   scorers verify each against the code at the PR head. Unverified suspicions
   never become findings.
6. **Code in the report comes from the repo.** Code excerpts are placeholders
   (`[[code:…]]`) filled from the head commit; line citations are checked.
7. **Read-only.** No checkout, no new refs, no commits, no pushes. The only
   external write is the PR comment, after the user's "yes".
8. **Reports are historical records.** Updates append; they never rewrite
   earlier text.

## 3. Where the files live

| What | Where |
| --- | --- |
| The skill (runtime files only) | `aurora-dashboard/.claude/skills/review-and-comment-pr/` — `SKILL.md`, `scripts/`, `references/` (incl. `references/briefs/`) |
| Agent types | `aurora-dashboard/.claude/agents/` — `pr-reviewer`, `external-api-checker`, `security-reviewer` |
| Markdown hook (also a module of the scripts) | `aurora-dashboard/.claude/hooks/check_report_md.py` |
| Permissions, hooks, env | `aurora-dashboard/.claude/settings.local.json` |
| Run folders | `aurora-dashboard/.claude/runs/review-and-comment-pr/<pr>-<sha8>/` |
| Reports and index | `DOCS/aurora-dashboard-kb/prs/` |
| Versioned copy for others to install | `DOCS/ToolDocs/claude-config/aurora-dashboard-config/.claude/` (`.claude/` is git-ignored in the app repo) |
| This spec and the Russian README | `DOCS/ToolDocs/claude-config/review-and-comment-pr-docs/` |
| Regression set | `DOCS/ToolDocs/claude-config/review-pr-regression/` |
| Install on another machine | `DOCS/ToolDocs/claude-config/review-and-comment-pr-remote-setup.md` |
| Cost audit | `DOCS/ToolDocs/claude-config/cost-audit/` |

Human-facing documentation stays outside the skill folder: by the Agent Skills
convention the skill folder holds only what the agent needs at run time.

## 4. Pipeline

### Modes (chosen by `collect.py`)

| Mode | When | What runs |
| --- | --- | --- |
| `full` | open PR, no report yet | Steps 4–9 |
| `rerun` | report is current, user explicitly asked to redo it | as `full`, overwriting the report |
| `update` | new commits since the report | Steps 4–9 on the delta; an Update block is appended |
| `status` | draft ↔ ready, merged or closed since the report | `render.py` refreshes status and index; nothing posted |
| `none` | nothing to document | stop |

`collect.py` exits 3 with a question when it needs the user (no linked issue;
report already current). A **release PR** (only version bumps and changelogs)
gets no agents: the orchestrator does a light review and writes
`findings.json` itself.

### Steps

1. **Collect** (`collect.py`) — PR metadata, diff (generated files left out),
   PR description, linked issues, review discussion (comments, reviews with
   their URLs, inline threads), CI, changeset, review standards at the head;
   on an Update also `delta.diff` — the PR's own changes since the reported
   head, with what a merge of the base branch brought in taken out.
2. **Act on the mode.**
3. (The run folder is the agents' only input.)
4. **Find** (`briefs.py find`) — one brief per role (section 5); all agents are
   launched in one message, in the foreground. Each saves its result through
   `save.py`.
5. **Score** (`briefs.py score`) — candidates from all finders plus the
   describer's unmet acceptance criteria and stale callers are numbered
   `C1…`, grouped by place (same file within 3 lines, same file without a line,
   or the same label) and packed into batches of up to 8 without splitting a
   group. One scorer per batch. Then **compose** (`assemble.py`) keeps every
   candidate scored ≥ 50 that is not a `same_as` duplicate and writes
   `compose.md` for the orchestrator.
6. **Write and render** — the orchestrator writes `texts.json`;
   `assemble.py --texts` builds `findings.json`; `render.py` validates it,
   numbers findings, derives the verdict, renders the report (or Update block)
   into `DOCS`, updates the index and Related links. A **fact-check** agent then
   checks the descriptive sections; accepted corrections go back as exact
   `fixes` and the report is rendered again.
7. **Index and Related** — done by `render.py`.
8. **Post** — `prepare_comment.py` slices the comment (on an Update, only the
   newest block), scans it for secrets, local paths, internal hosts, private
   IPs, e-mails and env data, checks Markdown, and trims Solution Overview to a
   link if the comment exceeds 60 000 characters. The user approves; then
   `gh pr comment --body-file`.
9. **Report back**, then a separate question whether to file findings in
   `DOCS/FOLLOW-UPS.md`.

## 5. Roles

Role names are the names of briefs (`references/briefs/<role>.md`) and of
result files (`out/<role>.json`). Agent types are the `.claude/agents/`
definitions; a missing type falls back to a general Sonnet agent with the same
brief (recorded in the report's provenance).

| Role | Agent type | Task | Result contract (enforced by `save.py`) |
| --- | --- | --- | --- |
| `describer` | pr-reviewer | What/how/affects narrative, QA plan, acceptance grading against the linked issue, stale callers, scope | placeholders resolve; citations exist at head; internal names rejected |
| `describer` (Update) | pr-reviewer | Same, only for what earlier findings don't cover; no QA plan | as above, `how`/`affects` may be empty |
| `find-standards` | pr-reviewer | Review standards (`copilot-instructions.md`, root `CLAUDE.md` as guidance) | candidates + a non-empty checklist (one row per standard checked) |
| `find-diff-bugs` | pr-reviewer | Obvious bugs in the diff itself | candidates |
| `find-history` | pr-reviewer | Bugs visible only through `git log` / `git blame` | candidates |
| `find-discussion` | pr-reviewer | Review discussion: what still applies; who raised it, with URL | candidates |
| `find-code-comments` | pr-reviewer | Compliance with guidance in code comments | candidates |
| `find-api-contract` | external-api-checker | Changed OpenStack / Ceph RGW calls and schemas against the official references (only when server code changed) | candidates with verbatim doc quotes and URLs |
| `find-security` | security-reviewer | Security checklist (scoping, server-side permission checks, validation, secrets, HTML injection, fail-closed UI) | candidates |
| `find-cross-boundary` | pr-reviewer | Follows each changed behaviour out of the diff into the existing code it hands off to; failures across that boundary | candidates whose evidence cites a `path:line` outside the PR; a `boundaries` list with one such receiver per hand-off point |
| `pr-description` | pr-reviewer | PR description vs code, each claim read within its section (a BFF bullet is about the server, a UI bullet about the client): claims not in the code; whole areas changed but not described | `not in code`: the quote is found verbatim in the description; `not described`: a valid `path:line` at head |
| `earlier-findings` | pr-reviewer | Update only: status of every earlier finding at the new head; reads the code and the replies in the discussion; `dropped` only for merge conflicts, draft, a finding a maintainer asked to do differently ("Reversed by <login> in <url>"), or an Improvement/Process item the author or a maintainer kept as is with a reason ("Kept as is by …"); a Required Change is never closed by the author's word | every earlier finding exactly once; status ∈ fixed / partly / open / dropped; a dropped `CR` only with a conflicts / draft / "Reversed by" note |
| `score-<n>` | pr-reviewer | Verify and score each candidate of a batch (0/25/50/75/100); severity, category, precedent; `same_as` for candidates at one place | every candidate of the batch once; `same_as` required in a group and must point at a candidate without its own `same_as`; for ≥ 50: valid severity, category, location, precedent; on an Update, a candidate from the review discussion about a file the new commits don't touch can't score ≥ 50 |
| `factcheck` | pr-reviewer | Descriptive sections against the code | exact `old` → `new` replacements that occur once |

Every finder candidate: `claim` (consequence for the user or the system, and
when it happens), `location`, `evidence`; optional `precedent`, `discussion`.
A candidate citing a review-standard rule must name merged code outside the PR
that follows it (`example: path:line`) or say `example: none`.

## 6. Run folder and data contracts

| File | Written by | Read by |
| --- | --- | --- |
| `context.json` | collect | all scripts, agents |
| `pr.diff`, `delta.diff`, `pr-body.md`, `issue-<N>.md`, `discussion.json`, `copilot-instructions.md` | collect | agents |
| `briefs/<role>.md` | briefs | agents |
| `out/<role>.json` | save (on an agent's call) | briefs, assemble |
| `candidates.json` | briefs score | scorers (via briefs), assemble |
| `compose.md` | assemble | orchestrator |
| `texts.json` | orchestrator | assemble |
| `findings.json` | assemble (`--texts`); orchestrator on a release PR | render |
| `report.md` | render (draft of what goes to `DOCS`) | fact-check, regression set |

Process items have ids: `no-linked-issue`, `missing-changeset` (from
`collect.py`), `desc-<n>` (from `pr-description`, added by `assemble.py`),
and any the orchestrator adds in `texts.json`. Findings have ids `c<N>`;
`render.py` assigns the public numbers `CR<n>`, `P<n>`, `I<n>` (an Update
continues after the report's numbers). Texts refer to findings only as
`[[ref:<id>]]`.

## 7. Verdict

Derived by `render.py`; the orchestrator chooses only Confidence.

- **Required Changes** — severity Critical, Major or Moderate. **Improvements**
  — Low or Trivial. **Process** — no severity.
- **Must fix** — a Required Change in category Bug or Security without a
  precedent tag. Other Required Changes are a **Team call** (convention,
  existing pattern, or deferred by a maintainer).

| Condition | Recommendation |
| --- | --- |
| any Must fix | 🔴 Request Changes |
| Required Changes, none Must fix | 🟡 Approve with changes |
| only Process items | 🟡 Approve with process to-dos |
| only Improvements | 🟢 Approve with nits |
| nothing | 🟢 Approve |

On an Update the same rule counts the Update's findings plus the earlier ones
not `fixed` or `dropped`. An earlier `partly`/`open` finding whose note names a
new finding (`[[ref:…]]`) is counted through that new finding, not twice.

**Confidence to Merge** (High / Medium / Low) — how sure the orchestrator is
the PR is sound once Required Changes are cleared; lowered for what could not be
verified (CI unreadable, acceptance not checkable, agent fallback). Draft state
does not count.

## 8. Invariants and where they are enforced

| Invariant | Enforced by |
| --- | --- |
| No candidate disappears: each is a finding, a duplicate attached to one, or a row in "Checked and dismissed" (a duplicate of a dropped candidate goes there with it) | `assemble.py` (`root()`, `dismissed`); `save.py` refuses `same_as` chains and loops |
| Every agent result has the agreed shape; locations exist at the head | `save.py` |
| Published texts never name run-folder files, field names or this review's roles | `quotes.INTERNAL` via `save.public()`, `quotes.resolve_text`, `render.py` |
| Code in the report is verbatim from the head (or base) commit; every `path:line` is in range | `quotes.py`, `render.py` |
| Every earlier finding gets exactly one status on an Update | `save.py` (`earlier-findings`), `render.py` |
| Every `pr-description` mismatch reaches the report as a Process item; it can be reworded, not dropped | `assemble.py` |
| A reviewer comment that was checked and not taken up is answered in the posted comment | `render.not_taken_up` (comment, inline thread or review URL in `discussion`) |
| A maintainer's request outranks this report's earlier finding | scorer brief on an Update (exception to "objects to an earlier finding → 0"); `earlier-findings` marks a reversed finding `dropped` |
| An Update reviews the new commits: a review-discussion point about untouched files is answered under "not taken up", not turned into a finding | `save.py` (score ≥ 50 refused), scorer brief, `scoring.md` |
| Nothing is posted without the user's explicit "yes"; a scanner hit blocks the post | `SKILL.md` Step 8, `prepare_comment.py`, hook |
| No git state changes, no commits, no pushes | `SKILL.md` hard rules; read-only commands only in `settings.local.json` |

## 9. Publishing and safety

- The comment is posted from a file (`--body-file`), never inline.
- Before posting, `prepare_comment.py` scans for secrets, local paths,
  internal hosts, private IPs, e-mail addresses and env data; any hit is shown
  to the user and blocks the post until they decide.
- Posting needs no separate Claude Code permission prompt: `prepare_comment.py`
  and `gh pr comment` are allowed in settings, and the user's "yes" in the chat
  is the approval.
- `curl` is allowed only for `https://raw.githubusercontent.com/openstack/*`
  (OpenStack API reference sources); other documentation is read with WebFetch
  on an allow-list of domains.
- The knowledge base is public: no secrets or session logs go into `DOCS`.

## 10. Testing

- **Regression set** (`review-pr-regression/run.py`) — replays every scripted
  step on saved runs (two full, two Update fixtures) and compares with
  `golden/`. No agents, no network, no writes to `DOCS`; about a minute. Run
  before and after every change; an expected diff is accepted with `--update`.
  Today's date is normalized to `<TODAY>`. A brief change that alters an
  agent's output format needs a hand-written sample in a fixture's `out/`.
- **Synthetic checks** for refusals in `save.py` / `assemble.py` that real
  fixtures don't exercise (done ad hoc when a check is added).
- **Live runs** — the only test of agent behaviour. Run by the user; logs are
  kept with a version label; cost and calls are reviewed with
  `cost-audit/audit_session.py`, and findings are checked against the code.
  Typical cost: about $3 for an Update, about $4.7 for a full review.

## 11. Decision log

| Date | Decision | Why |
| --- | --- | --- |
| Oct 23–26 | One task — one agent; no checks added to the orchestrator or to an agent with another task | such additions were ignored or done inconsistently in live runs |
| Oct 26 | Merge conflicts are not part of the review; old conflict findings → `dropped` | GitHub and CI show them |
| Oct 26 | Update block has the same order as the full report: Verdict → earlier statuses → findings → not taken up → What changed | readers need the state at this head first |
| Oct 26 | The delta subtracts changes a merge of the base branch brought in | otherwise merged `main` code is reviewed as the author's |
| Oct 26 | Standards findings must name merged example code (`example:`) | a rule without a model to copy is hard to act on |
| Oct 28 | `same_as` chains refused; a duplicate of a dropped candidate is listed with it | a candidate could vanish without trace (real case in #1377) |
| Oct 28 | Draft state is not a finding and does not cap Confidence | CI does not let a draft be merged |
| Oct 28 | Posting needs no extra permission prompt; the "yes" in chat is the approval | the user publishes anyway; a second prompt adds nothing |
| Oct 28 | New role `pr-description` (description vs code → Process) | the orchestrator was formally responsible but never did it |
| Oct 28 | Reviews are collected with their URLs; a maintainer's request outranks an earlier finding | a CHANGES_REQUESTED review was invisible in "not taken up" and scored 0 |
| Oct 28 | New role `find-cross-boundary` | `find-diff-bugs` is told to stay in the diff; a redirect loop across files was found in one live run of two |
| Oct 28 | An earlier finding a maintainer reversed is `dropped` ("Reversed by …"), not `open` | live run `1377-v3`: an earlier "use a Badge" stayed open after the maintainer asked for plain text |
| Oct 28 | `pr-description` reads each claim within its section | a rule added the same day ("X unchanged" is a mismatch even if described elsewhere) produced a false Process item in `1377-v4`: "Routers behaviour is unchanged except pagination" sits under the BFF heading and is true for the server; the UI changes were described in their own section. Rule replaced |
| Oct 28 | On an Update, a review-discussion point about a file the new commits don't touch is not a new finding (score 0, "Outside this update's changes"; answered under "not taken up") | the same deferred Copilot point (by-ID `project_id`) was Low, dismissed and Moderate Security in three runs on the same code, and flipped the verdict |
| Oct 28 | `earlier-findings` reads the replies in the discussion: an Improvement or Process item the author/maintainer kept as is with a reason is `dropped` ("Kept as is by …"); a Required Change needs a maintainer. `collect.py` replaces quoted lines in comments with a marker | the author's "I14 is intentional and documented" sat under a 10k-character quote of our report, and the agent checked only the code |
| Oct 28 | Roles renamed from letters to descriptive names (`finder-a…h` → `find-*`, `description` → `pr-description`, `earlier` → `earlier-findings`); agent types unchanged | names say what the role does |
| Oct 28 | Human docs (this spec, the README) live outside the skill folder | Agent Skills convention: the skill folder holds runtime files only |

## 12. Known limitations

- Finder results vary between runs; a real problem can be found in one run and
  missed in the next.
- The Update block has no QA plan and no "Checked and dismissed"; dismissed
  candidates appear only if a review comment raised them.
- The Update block does not add Process items from `context.json`; they show
  only through earlier findings' statuses.
- The index row is never created from scratch: the table must exist.
- Verified in live runs `1377-v3` / `1377-v4` (Oct 28): `find-cross-boundary`,
  `pr-description`, review URLs from the
  REST API, quote stripping, `earlier-findings` reading replies ("Kept as is"),
  the maintainer-outranks-earlier rule, the "discussion point outside the
  delta" rule. Not yet verified: `curl` permission for `find-api-contract`,
  the release-PR path, a delta without a reachable base.
